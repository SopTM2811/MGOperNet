"""
Test simple para verificar que el flujo continuar_desde_paso1 
procesa correctamente diferentes montos sin errores.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, MagicMock
from telegram import Update, CallbackQuery, User
from telegram.ext import ContextTypes

# Importar handlers
import sys
sys.path.insert(0, '/app/backend')

from telegram_netcash_handlers import TelegramNetCashHandlers, NC_ESPERANDO_BENEFICIARIO


async def test_montos():
    """Test simple de montos"""
    
    mongo_url = os.getenv('MONGO_URL')
    db_name = os.getenv('DB_NAME', 'netcash_mbco')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Limpiar y setup
    await db.solicitudes_netcash.delete_many({})
    await db.clientes.delete_many({})
    await db.config_cuentas_netcash.delete_many({})
    
    await db.clientes.insert_one({
        "id": "cliente_test",
        "estado": "activo",
        "telegram_id": 123456789
    })
    
    await db.config_cuentas_netcash.insert_one({
        "tipo": "concertadora",
        "banco": "STP",
        "clabe": "646180174400027290",
        "beneficiario": "MONTE BANCO SA DE CV",
        "activa": True
    })
    
    # Casos de prueba
    montos_test = [
        (389456.78, "comprobante_389456.pdf"),
        (325678.55, "comprobante_325678.pdf"),
        (1045000.00, "comprobante_1045000.pdf"),
    ]
    
    resultados = []
    
    for monto, nombre_archivo in montos_test:
        # Crear solicitud
        solicitud_id = f"test_nc_{int(datetime.now().timestamp() * 1000)}"
        
        comprobante_valido = {
            "nombre_archivo": nombre_archivo,
            "url_s3": f"s3://test/{nombre_archivo}",
            "subido_en": datetime.now(timezone.utc).isoformat(),
            "texto_extraido": f"STP\nMONTE BANCO SA DE CV\nCLABE: 646180174400027290\nMonto: ${monto:,.2f}",
            "cuenta_stp_extraida": "646180174400027290",
            "beneficiario_extraido": "MONTE BANCO SA DE CV",
            "monto_detectado": monto,
            "es_valido": True,
            "es_duplicado": False,
            "duplicado_global": False,
            "hash": f"test_hash_{monto}",
            "validacion_detalle": {
                "valido": True,
                "razon": "Comprobante válido"
            }
        }
        
        solicitud = {
            "id": solicitud_id,
            "solicitud_id": solicitud_id,
            "cliente_id": "cliente_test",
            "estado": "comprobantes_recibidos",
            "comprobantes": [comprobante_valido],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        await db.solicitudes_netcash.insert_one(solicitud)
        
        # Crear mocks de Telegram con message mock
        update = Mock(spec=Update)
        query = Mock(spec=CallbackQuery)
        query.data = f"nc_continuar_paso1_{solicitud_id}"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        
        # Agregar message mock para evitar el error del anterior
        message_mock = Mock()
        message_mock.reply_text = AsyncMock()
        query.message = message_mock
        
        query.from_user = Mock(spec=User)
        query.from_user.id = 123456789
        query.from_user.first_name = "Test"
        
        update.callback_query = query
        update.effective_user = query.from_user
        
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        
        # Crear mock del bot
        bot = Mock()
        bot.es_cliente_activo = AsyncMock(return_value=True)
        
        # Ejecutar handler
        handlers = TelegramNetCashHandlers(bot)
        
        try:
            resultado = await handlers.continuar_desde_paso1(update, context)
            
            # Verificar resultado
            sol_updated = await db.solicitudes_netcash.find_one(
                {"id": solicitud_id},
                {"_id": 0}
            )
            
            error_id = sol_updated.get("error_id")
            requiere_revision = sol_updated.get("requiere_revision_manual", False)
            
            if resultado == NC_ESPERANDO_BENEFICIARIO and not error_id and not requiere_revision:
                resultados.append({
                    "monto": monto,
                    "archivo": nombre_archivo,
                    "estado": "✅ PASÓ",
                    "resultado": resultado,
                    "error_id": None
                })
            else:
                resultados.append({
                    "monto": monto,
                    "archivo": nombre_archivo,
                    "estado": "❌ FALLÓ",
                    "resultado": resultado,
                    "error_id": error_id,
                    "requiere_revision": requiere_revision
                })
        except Exception as e:
            resultados.append({
                "monto": monto,
                "archivo": nombre_archivo,
                "estado": "❌ EXCEPTION",
                "error": str(e)
            })
        
        # Pequeña pausa entre tests
        await asyncio.sleep(0.1)
    
    # Mostrar resultados
    print("\n" + "="*80)
    print("RESULTADOS DE TESTS: ERR_CONTINUAR con Comprobantes Válidos")
    print("="*80)
    
    for res in resultados:
        print(f"\n{res['estado']} Monto: ${res['monto']:,.2f}")
        print(f"   Archivo: {res['archivo']}")
        if 'error_id' in res:
            print(f"   Error ID: {res['error_id']}")
        if 'error' in res:
            print(f"   Error: {res['error']}")
    
    print("\n" + "="*80)
    
    # Verificar que todos pasaron
    todos_pasaron = all(r['estado'] == '✅ PASÓ' for r in resultados)
    
    if todos_pasaron:
        print("✅ TODOS LOS TESTS PASARON")
        print("\n🎉 BUG P0 CORREGIDO: Los comprobantes válidos ahora procesan sin errores")
    else:
        print("❌ ALGUNOS TESTS FALLARON")
    
    print("="*80 + "\n")
    
    client.close()
    
    return todos_pasaron


if __name__ == "__main__":
    resultado = asyncio.run(test_montos())
    exit(0 if resultado else 1)
