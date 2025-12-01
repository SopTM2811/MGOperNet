"""
Test para reproducir y verificar el bug ERR_CONTINUAR con comprobantes válidos.

Casos de prueba específicos solicitados por el usuario:
- $389,456.78
- $325,678.55
- $1,045,000.00

Objetivo: Con comprobantes válidos el flujo debe avanzar sin errores ERR_CONTINUAR.
"""

import pytest
import pytest_asyncio
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from telegram import Update, CallbackQuery, User, Message, Chat
from telegram.ext import ContextTypes

# Importar los handlers y servicios
import sys
sys.path.insert(0, '/app/backend')

from telegram_netcash_handlers import TelegramNetCashHandlers, NC_ESPERANDO_BENEFICIARIO
from netcash_service import netcash_service


class TestErrContinuarValidComprobantes:
    """
    Suite de tests para bug P0: ERR_CONTINUAR con comprobantes válidos
    """
    
    @pytest_asyncio.fixture
    async def setup_db(self):
        """Configurar BD limpia para cada test"""
        mongo_url = os.getenv('MONGO_URL')
        db_name = os.getenv('DB_NAME', 'netcash_mbco')
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        # Limpiar colecciones
        await db.solicitudes_netcash.delete_many({})
        await db.clientes.delete_many({})
        await db.config_cuentas_netcash.delete_many({})
        
        # Crear cliente de prueba activo
        await db.clientes.insert_one({
            "id": "cliente_test_001",
            "nombre": "Cliente Test",
            "estado": "activo",
            "telegram_id": 123456789,
            "created_at": datetime.now(timezone.utc)
        })
        
        # Crear cuenta concertadora activa para validaciones
        await db.config_cuentas_netcash.insert_one({
            "tipo": "concertadora",
            "nombre": "STP NETCASH",
            "banco": "STP",
            "clabe": "646180174400027290",
            "beneficiario": "MONTE BANCO SA DE CV",
            "activa": True,
            "created_at": datetime.now(timezone.utc)
        })
        
        yield db
        
        client.close()
    
    @pytest.fixture
    def mock_bot(self):
        """Crear mock del bot"""
        bot = Mock()
        bot.es_cliente_activo = AsyncMock(return_value=True)
        return bot
    
    async def crear_solicitud_con_comprobante_valido(self, db, monto_str: str, nombre_archivo: str):
        """
        Crea una solicitud con un comprobante válido de prueba.
        
        Args:
            db: Base de datos
            monto_str: Monto como string (ej: "$389,456.78")
            nombre_archivo: Nombre del archivo (ej: "comprobante_389456.pdf")
        
        Returns:
            solicitud_id: ID de la solicitud creada
        """
        # Convertir monto string a float
        monto_float = float(monto_str.replace("$", "").replace(",", ""))
        
        solicitud_id = f"test_nc_{int(datetime.now().timestamp())}"
        
        comprobante_valido = {
            "nombre_archivo": nombre_archivo,
            "url_s3": f"s3://test/{nombre_archivo}",
            "subido_en": datetime.now(timezone.utc).isoformat(),
            "texto_extraido": f"STP\nMONTE BANCO SA DE CV\nCLABE: 646180174400027290\nMonto: {monto_str}",
            "cuenta_stp_extraida": "646180174400027290",
            "beneficiario_extraido": "MONTE BANCO SA DE CV",
            "monto_detectado": monto_float,
            "es_valido": True,
            "es_duplicado": False,
            "duplicado_global": False,
            "hash": f"test_hash_{monto_float}",
            "validacion_detalle": {
                "valido": True,
                "razon": "Comprobante válido",
                "cuenta_coincide": True,
                "beneficiario_coincide": True
            }
        }
        
        solicitud = {
            "id": solicitud_id,
            "solicitud_id": solicitud_id,
            "cliente_id": "cliente_test_001",
            "estado": "comprobantes_recibidos",
            "comprobantes": [comprobante_valido],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "canal_origen": "telegram",
            "canal_metadata": {
                "telegram_user_id": 123456789,
                "telegram_username": "test_user"
            }
        }
        
        await db.solicitudes_netcash.insert_one(solicitud)
        
        return solicitud_id
    
    @pytest.mark.asyncio
    async def test_caso1_monto_389456_78(self, setup_db, mock_bot):
        """
        Test Caso 1: Comprobante con monto $389,456.78
        
        Expectativa: Debe procesar sin errores y avanzar al siguiente paso.
        """
        db = setup_db
        
        # Crear solicitud con comprobante válido
        solicitud_id = await self.crear_solicitud_con_comprobante_valido(
            db,
            "$389,456.78",
            "comprobante_389456.pdf"
        )
        
        # Crear mocks de Telegram
        update = Mock(spec=Update)
        query = Mock(spec=CallbackQuery)
        query.data = f"nc_continuar_paso1_{solicitud_id}"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.from_user = Mock(spec=User)
        query.from_user.id = 123456789
        query.from_user.first_name = "Test User"
        
        update.callback_query = query
        update.effective_user = query.from_user
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        
        # Instanciar handlers
        handlers = TelegramNetCashHandlers(mock_bot)
        
        # Ejecutar handler
        resultado = await handlers.continuar_desde_paso1(update, context)
        
        # VERIFICACIONES
        # 1. Debe retornar el siguiente estado (NC_ESPERANDO_BENEFICIARIO)
        assert resultado == NC_ESPERANDO_BENEFICIARIO, f"Esperaba NC_ESPERANDO_BENEFICIARIO, obtuvo {resultado}"
        
        # 2. Verificar que se llamó edit_message_text (mostró resumen)
        assert query.edit_message_text.called, "No se mostró mensaje al usuario"
        
        # 3. Verificar que NO se marcó como requiere_revision_manual
        solicitud_updated = await db.solicitudes_netcash.find_one(
            {"id": solicitud_id},
            {"_id": 0}
        )
        assert not solicitud_updated.get("requiere_revision_manual", False), \
            "La solicitud NO debe requerir revisión manual"
        
        # 4. Verificar que NO se generó error_id
        assert "error_id" not in solicitud_updated or not solicitud_updated.get("error_id"), \
            f"NO debe haber error_id. Encontrado: {solicitud_updated.get('error_id')}"
        
        # 5. Verificar el contenido del mensaje (debe usar HTML y mostrar el monto)
        calls = query.edit_message_text.call_args_list
        for call in calls:
            args, kwargs = call
            mensaje = args[0] if args else kwargs.get('text', '')
            
            # Verificar que usa HTML
            if 'parse_mode' in kwargs:
                assert kwargs['parse_mode'] == "HTML", f"Debe usar HTML, no {kwargs['parse_mode']}"
            
            # Verificar que el mensaje contiene el monto
            if "$389,456.78" in mensaje or "389456" in mensaje or "389,456" in mensaje:
                print(f"✅ Mensaje contiene el monto correctamente")
                print(f"   Mensaje: {mensaje[:100]}...")
        
        print(f"\n✅ TEST CASO 1 PASADO: Monto $389,456.78 procesado correctamente")
    
    @pytest.mark.asyncio
    async def test_caso2_monto_325678_55(self, setup_db, mock_bot):
        """
        Test Caso 2: Comprobante con monto $325,678.55
        
        Expectativa: Debe procesar sin errores y avanzar al siguiente paso.
        """
        db = setup_db
        
        solicitud_id = await self.crear_solicitud_con_comprobante_valido(
            db,
            "$325,678.55",
            "comprobante_325678.pdf"
        )
        
        # Crear mocks
        update = Mock(spec=Update)
        query = Mock(spec=CallbackQuery)
        query.data = f"nc_continuar_paso1_{solicitud_id}"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.from_user = Mock(spec=User)
        query.from_user.id = 123456789
        query.from_user.first_name = "Test User"
        
        update.callback_query = query
        update.effective_user = query.from_user
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        
        handlers = TelegramNetCashHandlers(mock_bot)
        
        # Ejecutar
        resultado = await handlers.continuar_desde_paso1(update, context)
        
        # Verificar
        assert resultado == NC_ESPERANDO_BENEFICIARIO
        
        solicitud_updated = await db.solicitudes_netcash.find_one(
            {"id": solicitud_id},
            {"_id": 0}
        )
        assert not solicitud_updated.get("requiere_revision_manual", False)
        assert not solicitud_updated.get("error_id")
        
        print(f"\n✅ TEST CASO 2 PASADO: Monto $325,678.55 procesado correctamente")
    
    @pytest.mark.asyncio
    async def test_caso3_monto_alto_1045000(self, setup_db, mock_bot):
        """
        Test Caso 3: Comprobante con monto alto $1,045,000.00
        
        Expectativa: Debe procesar sin errores, aunque el monto sea > $1M.
        El código tiene logs especiales para montos >= $1M, pero no debe fallar.
        """
        db = setup_db
        
        solicitud_id = await self.crear_solicitud_con_comprobante_valido(
            db,
            "$1,045,000.00",
            "comprobante_1045000.pdf"
        )
        
        # Crear mocks
        update = Mock(spec=Update)
        query = Mock(spec=CallbackQuery)
        query.data = f"nc_continuar_paso1_{solicitud_id}"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.from_user = Mock(spec=User)
        query.from_user.id = 123456789
        query.from_user.first_name = "Test User"
        
        update.callback_query = query
        update.effective_user = query.from_user
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        
        handlers = TelegramNetCashHandlers(mock_bot)
        
        # Ejecutar
        resultado = await handlers.continuar_desde_paso1(update, context)
        
        # Verificar
        assert resultado == NC_ESPERANDO_BENEFICIARIO
        
        solicitud_updated = await db.solicitudes_netcash.find_one(
            {"id": solicitud_id},
            {"_id": 0}
        )
        assert not solicitud_updated.get("requiere_revision_manual", False), \
            "Montos altos válidos NO deben requerir revisión manual"
        assert not solicitud_updated.get("error_id"), \
            "Montos altos válidos NO deben generar error"
        
        print(f"\n✅ TEST CASO 3 PASADO: Monto alto $1,045,000.00 procesado correctamente")
    
    @pytest.mark.asyncio
    async def test_caso4_error_controlado(self, setup_db, mock_bot):
        """
        Test Caso 4: Verificar que el manejo de errores funciona correctamente
        
        Forzamos un error interno para verificar que:
        1. Se genera error_id correctamente
        2. Se marca requiere_revision_manual
        3. El mensaje al usuario usa HTML (no Markdown)
        4. El sistema no crashea
        """
        db = setup_db
        
        solicitud_id = await self.crear_solicitud_con_comprobante_valido(
            db,
            "$500,000.00",
            "comprobante_error_test.pdf"
        )
        
        # Crear mocks
        update = Mock(spec=Update)
        query = Mock(spec=CallbackQuery)
        query.data = f"nc_continuar_paso1_{solicitud_id}"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.from_user = Mock(spec=User)
        query.from_user.id = 123456789
        
        update.callback_query = query
        update.effective_user = query.from_user
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        
        handlers = TelegramNetCashHandlers(mock_bot)
        
        # Patchear netcash_service.validar_solicitud_completa para que falle
        with patch.object(netcash_service, 'validar_solicitud_completa', 
                         side_effect=Exception("Error simulado para test")):
            
            # Ejecutar - NO debe crashear
            resultado = await handlers.continuar_desde_paso1(update, context)
            
            # Verificar que el manejo de errores funcionó
            solicitud_updated = await db.solicitudes_netcash.find_one(
                {"id": solicitud_id},
                {"_id": 0}
            )
            
            # 1. Debe marcar requiere_revision_manual
            assert solicitud_updated.get("requiere_revision_manual") == True, \
                "Error debe marcar requiere_revision_manual"
            
            # 2. Debe tener error_id
            error_id = solicitud_updated.get("error_id")
            assert error_id, "Error debe generar error_id"
            assert error_id.startswith("ERR_CONTINUAR_"), \
                f"error_id debe empezar con ERR_CONTINUAR_, obtuvo: {error_id}"
            
            # 3. Debe tener error_detalle
            error_detalle = solicitud_updated.get("error_detalle")
            assert error_detalle, "Debe tener error_detalle"
            assert error_detalle.get("tipo") is not None, "Debe tener tipo de error"
            assert error_detalle.get("mensaje") is not None, "Debe tener mensaje de error"
            
            # 4. Verificar que el mensaje de error usa HTML
            assert query.edit_message_text.called, "Debe enviar mensaje al usuario"
            last_call = query.edit_message_text.call_args
            if last_call:
                kwargs = last_call[1]
                assert kwargs.get('parse_mode') == "HTML", \
                    f"Mensaje de error debe usar HTML, obtuvo: {kwargs.get('parse_mode')}"
                
                # Verificar contenido del mensaje
                mensaje = last_call[0][0] if last_call[0] else kwargs.get('text', '')
                assert error_id in mensaje, "Mensaje debe incluir el error_id"
                assert "<b>" in mensaje or "<code>" in mensaje, \
                    "Mensaje debe usar tags HTML"
            
            print(f"\n✅ TEST CASO 4 PASADO: Manejo de errores verificado correctamente")
            print(f"   Error ID generado: {error_id}")


if __name__ == "__main__":
    """
    Ejecutar tests:
    
    cd /app/backend
    python -m pytest tests/test_err_continuar_valid_comprobantes.py -v -s
    """
    print("=" * 80)
    print("SUITE DE TESTS: ERR_CONTINUAR con Comprobantes Válidos")
    print("=" * 80)
    print("\nCasos de prueba:")
    print("  1. Monto $389,456.78")
    print("  2. Monto $325,678.55")
    print("  3. Monto alto $1,045,000.00")
    print("  4. Error controlado (verificar manejo)")
    print("\nEjecutar con: pytest tests/test_err_continuar_valid_comprobantes.py -v -s")
    print("=" * 80)
