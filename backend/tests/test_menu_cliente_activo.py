"""
Tests para verificar el menú de /start según el estado del cliente.

Estos tests verifican que:
1. Clientes activos ven el menú completo con opción de crear operaciones
2. Clientes pendientes ven mensaje de "registro en revisión"
3. Un cliente activo con solicitud en revisión manual SIGUE viendo el menú completo
"""

import pytest
import pytest_asyncio
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

# Importar el bot
import sys
sys.path.insert(0, '/app/backend')

from telegram_bot import NetCashBot
from telegram import Update, User, Message, Chat, InlineKeyboardButton


class TestMenuClienteActivo:
    """
    Suite de tests para verificar el menú de /start
    """
    
    @pytest_asyncio.fixture
    async def setup_db(self):
        """Configurar BD limpia para cada test"""
        mongo_url = os.getenv('MONGO_URL')
        db_name = os.getenv('DB_NAME', 'netcash_mbco')
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        # Limpiar colecciones
        await db.usuarios_telegram.delete_many({"telegram_id": {"$regex": "^test_"}})
        await db.clientes.delete_many({"id": {"$regex": "^test_"}})
        await db.solicitudes_netcash.delete_many({"id": {"$regex": "^test_"}})
        
        yield db
        
        client.close()
    
    @pytest.mark.asyncio
    async def test_start_cliente_activo_muestra_menu_completo(self, setup_db):
        """
        Test 1: Cliente activo debe ver menú completo con opción de crear operaciones
        """
        db = setup_db
        
        telegram_id = "test_cliente_activo_001"
        cliente_id = "test_cliente_001"
        
        # Crear cliente activo en BD
        await db.clientes.insert_one({
            "id": cliente_id,
            "nombre": "Cliente Test Activo",
            "estado": "activo",
            "telegram_id": int(telegram_id.replace("test_cliente_activo_", "")),
            "telefono": "+525512345678",
            "created_at": datetime.now(timezone.utc)
        })
        
        # Crear usuario de Telegram con rol cliente_activo
        await db.usuarios_telegram.insert_one({
            "telegram_id": telegram_id,
            "chat_id": "123456",
            "nombre": "Cliente Test",
            "rol": "cliente_activo",
            "id_cliente": cliente_id,
            "telefono": "+525512345678",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Crear mocks de Telegram
        update = Mock(spec=Update)
        message = Mock(spec=Message)
        chat = Mock(spec=Chat)
        user = Mock(spec=User)
        
        user.id = 123456
        user.first_name = "Cliente"
        user.last_name = "Test"
        user.username = "clientetest"
        
        chat.id = 123456
        message.chat = chat
        message.reply_text = AsyncMock()
        
        update.message = message
        update.effective_user = user
        update.effective_chat = chat
        
        context = Mock()
        
        # Crear bot y ejecutar handler de start
        bot = NetCashBot()
        await bot.start(update, context)
        
        # Verificar que se llamó reply_text
        assert message.reply_text.called, "No se envió mensaje al usuario"
        
        # Obtener el mensaje y los botones enviados
        call_args = message.reply_text.call_args
        mensaje_enviado = call_args[0][0] if call_args[0] else call_args[1].get('text', '')
        reply_markup = call_args[1].get('reply_markup') if call_args else None
        
        # VERIFICACIONES
        # 1. El mensaje NO debe contener "registro en revisión"
        assert "revisión" not in mensaje_enviado.lower(), \
            f"Cliente activo NO debe ver mensaje de revisión. Mensaje: {mensaje_enviado}"
        
        # 2. Debe tener botones (InlineKeyboardMarkup)
        assert reply_markup is not None, "Debe tener botones"
        
        # 3. Verificar que contiene el botón de crear operación
        botones_texto = []
        if hasattr(reply_markup, 'inline_keyboard'):
            for fila in reply_markup.inline_keyboard:
                for boton in fila:
                    botones_texto.append(boton.text)
        
        tiene_crear_operacion = any("crear" in btn.lower() and "operación" in btn.lower() 
                                     for btn in botones_texto)
        tiene_ver_cuenta = any("cuenta" in btn.lower() for btn in botones_texto)
        tiene_ver_solicitudes = any("solicitudes" in btn.lower() or "operaciones" in btn.lower() 
                                     for btn in botones_texto)
        
        assert tiene_crear_operacion, \
            f"Debe tener botón 'Crear operación'. Botones encontrados: {botones_texto}"
        assert tiene_ver_cuenta, \
            f"Debe tener botón 'Ver cuenta'. Botones encontrados: {botones_texto}"
        assert tiene_ver_solicitudes, \
            f"Debe tener botón 'Ver solicitudes'. Botones encontrados: {botones_texto}"
        
        print(f"\n✅ TEST 1 PASADO: Cliente activo ve menú completo")
        print(f"   Botones: {botones_texto}")
    
    @pytest.mark.asyncio
    async def test_start_cliente_pendiente_muestra_mensaje_revision(self, setup_db):
        """
        Test 2: Cliente pendiente debe ver mensaje de "registro en revisión"
        """
        db = setup_db
        
        telegram_id = "test_cliente_pendiente_002"
        
        # Crear usuario de Telegram pendiente (sin id_cliente o rol desconocido)
        await db.usuarios_telegram.insert_one({
            "telegram_id": telegram_id,
            "chat_id": "234567",
            "nombre": "Cliente Pendiente",
            "rol": "desconocido",
            "id_cliente": None,
            "telefono": "+525512345679",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Crear mocks
        update = Mock(spec=Update)
        message = Mock(spec=Message)
        chat = Mock(spec=Chat)
        user = Mock(spec=User)
        
        user.id = 234567
        user.first_name = "Pendiente"
        user.username = "pendiente"
        
        chat.id = 234567
        message.chat = chat
        message.reply_text = AsyncMock()
        
        update.message = message
        update.effective_user = user
        update.effective_chat = chat
        
        context = Mock()
        
        # Ejecutar handler
        bot = NetCashBot()
        await bot.start(update, context)
        
        # Obtener mensaje
        call_args = message.reply_text.call_args
        mensaje_enviado = call_args[0][0] if call_args[0] else call_args[1].get('text', '')
        reply_markup = call_args[1].get('reply_markup') if call_args else None
        
        # VERIFICACIONES
        # 1. Debe contener mensaje de revisión o proceso
        assert "revisión" in mensaje_enviado.lower() or "proceso" in mensaje_enviado.lower(), \
            f"Cliente pendiente debe ver mensaje de revisión. Mensaje: {mensaje_enviado}"
        
        # 2. NO debe tener botón de crear operación
        botones_texto = []
        if reply_markup and hasattr(reply_markup, 'inline_keyboard'):
            for fila in reply_markup.inline_keyboard:
                for boton in fila:
                    botones_texto.append(boton.text)
        
        tiene_crear_operacion = any("crear" in btn.lower() and "operación" in btn.lower() 
                                     for btn in botones_texto)
        
        assert not tiene_crear_operacion, \
            f"Cliente pendiente NO debe ver botón 'Crear operación'. Botones: {botones_texto}"
        
        print(f"\n✅ TEST 2 PASADO: Cliente pendiente ve mensaje de revisión")
        print(f"   Mensaje contiene: 'revisión' o 'proceso'")
    
    @pytest.mark.asyncio
    async def test_cliente_activo_con_solicitud_en_revision_sigue_pudiendo_crear_operacion(self, setup_db):
        """
        Test 3: Cliente activo con solicitud en revisión manual SIGUE viendo menú completo
        
        IMPORTANTE: requiere_revision_manual es por OPERACIÓN, no por CLIENTE
        """
        db = setup_db
        
        telegram_id = "test_cliente_con_solicitud_003"
        cliente_id = "test_cliente_003"
        
        # Crear cliente activo
        await db.clientes.insert_one({
            "id": cliente_id,
            "nombre": "Cliente Con Solicitud Revisión",
            "estado": "activo",
            "telegram_id": int(telegram_id.replace("test_cliente_con_solicitud_", "")),
            "telefono": "+525512345680",
            "created_at": datetime.now(timezone.utc)
        })
        
        # Crear usuario de Telegram
        await db.usuarios_telegram.insert_one({
            "telegram_id": telegram_id,
            "chat_id": "345678",
            "nombre": "Cliente Test",
            "rol": "cliente_activo",
            "id_cliente": cliente_id,
            "telefono": "+525512345680",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Crear una solicitud con requiere_revision_manual = True
        await db.solicitudes_netcash.insert_one({
            "id": "test_solicitud_revision_001",
            "solicitud_id": "test_solicitud_revision_001",
            "cliente_id": cliente_id,
            "estado": "comprobantes_recibidos",
            "requiere_revision_manual": True,  # ⬅️ Solicitud marcada para revisión
            "error_id": "ERR_TEST_123",
            "comprobantes": [],
            "created_at": datetime.now(timezone.utc)
        })
        
        # Crear mocks
        update = Mock(spec=Update)
        message = Mock(spec=Message)
        chat = Mock(spec=Chat)
        user = Mock(spec=User)
        
        user.id = 345678
        user.first_name = "Cliente"
        user.username = "cliente"
        
        chat.id = 345678
        message.chat = chat
        message.reply_text = AsyncMock()
        
        update.message = message
        update.effective_user = user
        update.effective_chat = chat
        
        context = Mock()
        
        # Ejecutar handler
        bot = NetCashBot()
        await bot.start(update, context)
        
        # Obtener mensaje y botones
        call_args = message.reply_text.call_args
        mensaje_enviado = call_args[0][0] if call_args[0] else call_args[1].get('text', '')
        reply_markup = call_args[1].get('reply_markup') if call_args else None
        
        # VERIFICACIONES
        # 1. NO debe ver mensaje de revisión (el cliente está activo)
        assert "revisión" not in mensaje_enviado.lower(), \
            f"Cliente activo NO debe ver mensaje de revisión aunque tenga solicitud en revisión. Mensaje: {mensaje_enviado}"
        
        # 2. DEBE poder crear nuevas operaciones
        botones_texto = []
        if reply_markup and hasattr(reply_markup, 'inline_keyboard'):
            for fila in reply_markup.inline_keyboard:
                for boton in fila:
                    botones_texto.append(boton.text)
        
        tiene_crear_operacion = any("crear" in btn.lower() and "operación" in btn.lower() 
                                     for btn in botones_texto)
        
        assert tiene_crear_operacion, \
            f"Cliente activo debe poder crear operaciones aunque tenga una solicitud en revisión. Botones: {botones_texto}"
        
        # Verificar que la solicitud en revisión sigue en la BD
        solicitud = await db.solicitudes_netcash.find_one(
            {"id": "test_solicitud_revision_001"},
            {"_id": 0}
        )
        assert solicitud.get("requiere_revision_manual") == True, \
            "La solicitud debe seguir marcada para revisión"
        
        print(f"\n✅ TEST 3 PASADO: Cliente activo con solicitud en revisión sigue viendo menú completo")
        print(f"   Puede crear nuevas operaciones")
        print(f"   La revisión es por operación, NO por cliente")


if __name__ == "__main__":
    """
    Ejecutar tests:
    
    cd /app/backend
    python -m pytest tests/test_menu_cliente_activo.py -v -s
    """
    print("=" * 80)
    print("SUITE DE TESTS: Menú Cliente Activo (/start)")
    print("=" * 80)
    print("\nTests:")
    print("  1. Cliente activo ve menú completo")
    print("  2. Cliente pendiente ve mensaje de revisión")
    print("  3. Cliente activo con solicitud en revisión sigue pudiendo crear operaciones")
    print("\nEjecutar con: pytest tests/test_menu_cliente_activo.py -v -s")
    print("=" * 80)
