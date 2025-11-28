#!/usr/bin/env python3
"""
Pruebas específicas del bot de Telegram para el usuario 19440987
Simula el flujo completo del bot para verificar que funciona correctamente
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from datetime import datetime, timezone

# Agregar el directorio backend al path para importar módulos
sys.path.append('/app/backend')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/var/log/telegram_bot_test.log')
    ]
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv('/app/backend/.env')

# Configuración
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'netcash_mbco')

# Datos del usuario de prueba
TEST_USER = {
    "telegram_id": "19440987",
    "chat_id": "19440987",
    "rol": "cliente_activo",
    "id_cliente": "d9115936-733e-4598-a23c-2ae7633216f9"
}

class TelegramBotTester:
    def __init__(self):
        self.mongo_client = None
        self.db = None
        self.bot_instance = None
        
    async def setup(self):
        """Configuración inicial"""
        self.mongo_client = AsyncIOMotorClient(MONGO_URL)
        self.db = self.mongo_client[DB_NAME]
        
        # Importar y crear instancia del bot
        try:
            from telegram_bot import TelegramBotNetCash
            self.bot_instance = TelegramBotNetCash()
            logger.info("✅ Bot instance creada correctamente")
        except Exception as e:
            logger.error(f"❌ Error creando instancia del bot: {str(e)}")
            raise
        
        logger.info("✅ Setup completado")
        
    async def cleanup(self):
        """Limpieza final"""
        if self.mongo_client:
            self.mongo_client.close()
        logger.info("✅ Cleanup completado")
    
    async def test_verificar_datos_usuario(self):
        """Test 1: Verificar que los datos del usuario están correctos en BD"""
        logger.info("🔍 Test 1: Verificando datos del usuario en BD...")
        
        try:
            # Verificar usuario en usuarios_telegram
            usuario = await self.db.usuarios_telegram.find_one(
                {"telegram_id": TEST_USER["telegram_id"]}, 
                {"_id": 0}
            )
            
            if not usuario:
                logger.error(f"❌ Usuario {TEST_USER['telegram_id']} NO encontrado en usuarios_telegram")
                return False
            
            logger.info(f"✅ Usuario encontrado: {usuario.get('nombre', 'N/A')}")
            logger.info(f"   - telegram_id: {usuario.get('telegram_id')}")
            logger.info(f"   - chat_id: {usuario.get('chat_id')}")
            logger.info(f"   - rol: {usuario.get('rol')}")
            logger.info(f"   - id_cliente: {usuario.get('id_cliente')}")
            
            # Verificar cliente en clientes
            if usuario.get('id_cliente'):
                cliente = await self.db.clientes.find_one(
                    {"id": usuario['id_cliente']}, 
                    {"_id": 0}
                )
                
                if not cliente:
                    logger.error(f"❌ Cliente {usuario['id_cliente']} NO encontrado en clientes")
                    return False
                
                logger.info(f"✅ Cliente encontrado: {cliente.get('nombre', 'N/A')}")
                logger.info(f"   - estado: {cliente.get('estado')}")
                logger.info(f"   - comisión: {cliente.get('porcentaje_comision_cliente')}%")
                
                if cliente.get('estado') != 'activo':
                    logger.error(f"❌ Cliente NO está activo (estado: {cliente.get('estado')})")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en test_verificar_datos_usuario: {str(e)}")
            return False
    
    async def test_funcion_es_cliente_activo(self):
        """Test 2: Probar la función es_cliente_activo directamente"""
        logger.info("🔍 Test 2: Probando función es_cliente_activo...")
        
        try:
            telegram_id = TEST_USER["telegram_id"]
            chat_id = TEST_USER["chat_id"]
            
            logger.info(f"   Llamando es_cliente_activo con telegram_id='{telegram_id}', chat_id='{chat_id}'")
            
            # Llamar la función directamente
            es_activo, usuario, cliente = await self.bot_instance.es_cliente_activo(telegram_id, chat_id)
            
            logger.info(f"   Resultado: es_activo={es_activo}")
            
            if usuario:
                logger.info(f"   Usuario encontrado: {usuario.get('nombre', 'N/A')} (rol: {usuario.get('rol')})")
            else:
                logger.warning("   Usuario NO encontrado")
            
            if cliente:
                logger.info(f"   Cliente encontrado: {cliente.get('nombre', 'N/A')} (estado: {cliente.get('estado')})")
            else:
                logger.warning("   Cliente NO encontrado")
            
            if not es_activo:
                logger.error("❌ La función es_cliente_activo devolvió False")
                return False
            
            logger.info("✅ Función es_cliente_activo funciona correctamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en test_funcion_es_cliente_activo: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def test_simular_comando_start(self):
        """Test 3: Simular comando /start"""
        logger.info("🔍 Test 3: Simulando comando /start...")
        
        try:
            # Crear mock objects para simular Telegram Update
            class MockUser:
                def __init__(self):
                    self.id = int(TEST_USER["telegram_id"])
                    self.first_name = "JAVIER"
                    self.last_name = "TELEGRAM"
                    self.username = "javier_test"
            
            class MockChat:
                def __init__(self):
                    self.id = int(TEST_USER["chat_id"])
            
            class MockMessage:
                def __init__(self):
                    self.reply_text_calls = []
                
                async def reply_text(self, text, reply_markup=None, parse_mode=None):
                    self.reply_text_calls.append({
                        'text': text,
                        'reply_markup': reply_markup,
                        'parse_mode': parse_mode
                    })
                    logger.info(f"   📤 Bot respondería: {text[:100]}...")
            
            class MockUpdate:
                def __init__(self):
                    self.effective_user = MockUser()
                    self.effective_chat = MockChat()
                    self.message = MockMessage()
            
            class MockContext:
                def __init__(self):
                    self.user_data = {}
            
            # Simular el comando /start
            update = MockUpdate()
            context = MockContext()
            
            logger.info(f"   Simulando /start para user_id={update.effective_user.id}, chat_id={update.effective_chat.id}")
            
            # Llamar la función start del bot
            await self.bot_instance.start(update, context)
            
            # Verificar que se llamó reply_text
            if update.message.reply_text_calls:
                logger.info(f"✅ Bot respondió {len(update.message.reply_text_calls)} mensaje(s)")
                for i, call in enumerate(update.message.reply_text_calls):
                    logger.info(f"   Mensaje {i+1}: {call['text'][:200]}...")
                return True
            else:
                logger.error("❌ Bot no respondió ningún mensaje")
                return False
            
        except Exception as e:
            logger.error(f"❌ Error en test_simular_comando_start: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def test_simular_boton_nueva_operacion(self):
        """Test 4: Simular clic en botón 'Crear nueva operación'"""
        logger.info("🔍 Test 4: Simulando clic en botón 'Crear nueva operación'...")
        
        try:
            # Crear mock objects para simular callback query
            class MockUser:
                def __init__(self):
                    self.id = int(TEST_USER["telegram_id"])
                    self.first_name = "JAVIER"
                    self.last_name = "TELEGRAM"
            
            class MockChat:
                def __init__(self):
                    self.id = int(TEST_USER["chat_id"])
            
            class MockCallbackQuery:
                def __init__(self):
                    self.data = "nueva_operacion"
                    self.edit_message_text_calls = []
                
                async def answer(self):
                    logger.info("   📞 Callback query answered")
                
                async def edit_message_text(self, text, parse_mode=None):
                    self.edit_message_text_calls.append({
                        'text': text,
                        'parse_mode': parse_mode
                    })
                    logger.info(f"   📝 Bot editaría mensaje: {text[:100]}...")
            
            class MockUpdate:
                def __init__(self):
                    self.effective_user = MockUser()
                    self.effective_chat = MockChat()
                    self.callback_query = MockCallbackQuery()
            
            class MockContext:
                def __init__(self):
                    self.user_data = {}
            
            # Simular el clic en el botón
            update = MockUpdate()
            context = MockContext()
            
            logger.info(f"   Simulando callback 'nueva_operacion' para user_id={update.effective_user.id}, chat_id={update.effective_chat.id}")
            
            # Llamar la función nueva_operacion del bot
            await self.bot_instance.nueva_operacion(update, context)
            
            # Verificar que se editó el mensaje
            if update.callback_query.edit_message_text_calls:
                logger.info(f"✅ Bot editó mensaje {len(update.callback_query.edit_message_text_calls)} vez(es)")
                for i, call in enumerate(update.callback_query.edit_message_text_calls):
                    logger.info(f"   Mensaje {i+1}: {call['text'][:200]}...")
                
                # Verificar si el mensaje contiene información de operación creada
                mensaje = update.callback_query.edit_message_text_calls[0]['text']
                if "operación NetCash" in mensaje and "Folio" in mensaje:
                    logger.info("✅ Mensaje contiene información de operación creada")
                    return True
                elif "registrarme como cliente" in mensaje.lower():
                    logger.error("❌ Bot pidió registrarse como cliente (ERROR)")
                    return False
                else:
                    logger.warning("⚠️ Mensaje no contiene información esperada")
                    return False
            else:
                logger.error("❌ Bot no editó ningún mensaje")
                return False
            
        except Exception as e:
            logger.error(f"❌ Error en test_simular_boton_nueva_operacion: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def test_simular_boton_ver_operaciones(self):
        """Test 5: Simular clic en botón 'Ver mis operaciones'"""
        logger.info("🔍 Test 5: Simulando clic en botón 'Ver mis operaciones'...")
        
        try:
            # Crear mock objects similares al test anterior
            class MockUser:
                def __init__(self):
                    self.id = int(TEST_USER["telegram_id"])
                    self.first_name = "JAVIER"
                    self.last_name = "TELEGRAM"
            
            class MockChat:
                def __init__(self):
                    self.id = int(TEST_USER["chat_id"])
            
            class MockCallbackQuery:
                def __init__(self):
                    self.data = "ver_operaciones"
                    self.edit_message_text_calls = []
                
                async def answer(self):
                    logger.info("   📞 Callback query answered")
                
                async def edit_message_text(self, text, parse_mode=None):
                    self.edit_message_text_calls.append({
                        'text': text,
                        'parse_mode': parse_mode
                    })
                    logger.info(f"   📝 Bot editaría mensaje: {text[:100]}...")
            
            class MockUpdate:
                def __init__(self):
                    self.effective_user = MockUser()
                    self.effective_chat = MockChat()
                    self.callback_query = MockCallbackQuery()
            
            class MockContext:
                def __init__(self):
                    self.user_data = {}
            
            # Simular el clic en el botón
            update = MockUpdate()
            context = MockContext()
            
            logger.info(f"   Simulando callback 'ver_operaciones' para user_id={update.effective_user.id}, chat_id={update.effective_chat.id}")
            
            # Llamar la función ver_operaciones del bot
            await self.bot_instance.ver_operaciones(update, context)
            
            # Verificar que se editó el mensaje
            if update.callback_query.edit_message_text_calls:
                logger.info(f"✅ Bot editó mensaje {len(update.callback_query.edit_message_text_calls)} vez(es)")
                for i, call in enumerate(update.callback_query.edit_message_text_calls):
                    logger.info(f"   Mensaje {i+1}: {call['text'][:200]}...")
                
                # Verificar si el mensaje contiene información de operaciones o mensaje de sin operaciones
                mensaje = update.callback_query.edit_message_text_calls[0]['text']
                if "operaciones NetCash" in mensaje or "no tengo operaciones" in mensaje:
                    logger.info("✅ Mensaje contiene información de operaciones")
                    return True
                elif "registrarme como cliente" in mensaje.lower():
                    logger.error("❌ Bot pidió registrarse como cliente (ERROR)")
                    return False
                else:
                    logger.warning("⚠️ Mensaje no contiene información esperada")
                    return False
            else:
                logger.error("❌ Bot no editó ningún mensaje")
                return False
            
        except Exception as e:
            logger.error(f"❌ Error en test_simular_boton_ver_operaciones: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def test_verificar_logs_telegram(self):
        """Test 6: Verificar logs del bot de Telegram"""
        logger.info("🔍 Test 6: Verificando logs del bot de Telegram...")
        
        try:
            log_file = Path("/var/log/telegram_bot.log")
            
            if not log_file.exists():
                logger.warning("⚠️ Archivo de log /var/log/telegram_bot.log no existe")
                return True  # No es error crítico
            
            # Leer las últimas 50 líneas del log
            with open(log_file, 'r') as f:
                lines = f.readlines()
                recent_lines = lines[-50:] if len(lines) > 50 else lines
            
            logger.info(f"✅ Log file encontrado con {len(lines)} líneas totales")
            logger.info("   Últimas líneas relevantes:")
            
            # Buscar líneas relevantes para nuestro usuario
            relevant_lines = []
            for line in recent_lines:
                if "19440987" in line or "es_cliente_activo" in line or "nueva_operacion" in line or "ver_operaciones" in line:
                    relevant_lines.append(line.strip())
            
            if relevant_lines:
                for line in relevant_lines[-10:]:  # Mostrar últimas 10 líneas relevantes
                    logger.info(f"   📋 {line}")
            else:
                logger.info("   📋 No se encontraron líneas relevantes recientes")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en test_verificar_logs_telegram: {str(e)}")
            return False
    
    async def run_all_tests(self):
        """Ejecutar todos los tests"""
        logger.info("🚀 Iniciando pruebas del bot de Telegram para usuario 19440987")
        logger.info("=" * 70)
        
        tests = [
            ("Verificar datos del usuario en BD", self.test_verificar_datos_usuario),
            ("Probar función es_cliente_activo", self.test_funcion_es_cliente_activo),
            ("Simular comando /start", self.test_simular_comando_start),
            ("Simular botón 'Crear nueva operación'", self.test_simular_boton_nueva_operacion),
            ("Simular botón 'Ver mis operaciones'", self.test_simular_boton_ver_operaciones),
            ("Verificar logs del bot", self.test_verificar_logs_telegram)
        ]
        
        results = []
        
        for test_name, test_func in tests:
            logger.info(f"\n{'='*20} {test_name} {'='*20}")
            try:
                result = await test_func()
                results.append((test_name, result))
                if result:
                    logger.info(f"✅ {test_name}: PASÓ")
                else:
                    logger.error(f"❌ {test_name}: FALLÓ")
            except Exception as e:
                logger.error(f"💥 {test_name}: ERROR - {str(e)}")
                results.append((test_name, False))
        
        # Resumen final
        logger.info("\n" + "="*70)
        logger.info("📊 RESUMEN DE PRUEBAS DEL BOT DE TELEGRAM")
        logger.info("="*70)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASÓ" if result else "❌ FALLÓ"
            logger.info(f"{status:<10} {test_name}")
        
        logger.info(f"\n🎯 RESULTADO FINAL: {passed}/{total} pruebas pasaron")
        
        if passed == total:
            logger.info("🎉 ¡TODAS LAS PRUEBAS DEL BOT PASARON!")
            logger.info("✅ El flujo del bot funciona correctamente para el usuario 19440987")
        else:
            logger.warning(f"⚠️ {total - passed} pruebas fallaron")
            logger.warning("❌ Hay problemas en el flujo del bot que necesitan ser corregidos")
        
        return results

async def main():
    """Función principal"""
    tester = TelegramBotTester()
    
    try:
        await tester.setup()
        results = await tester.run_all_tests()
        return results
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())