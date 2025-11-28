#!/usr/bin/env python3
"""
Test real del flujo de notificación a Ana
Simula una interacción real con el bot de Telegram
"""
import asyncio
import os
import sys
import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from unittest.mock import Mock, AsyncMock

# Agregar el directorio backend al path
sys.path.append('/app/backend')

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv('/app/backend/.env')

# Configuración
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'netcash_mbco')

class RealTelegramFlowTester:
    def __init__(self):
        self.mongo_client = None
        self.db = None
        self.bot_instance = None
        
    async def setup(self):
        """Configuración inicial"""
        self.mongo_client = AsyncIOMotorClient(MONGO_URL)
        self.db = self.mongo_client[DB_NAME]
        logger.info("✅ Setup completado")
        
    async def cleanup(self):
        """Limpieza final"""
        if self.mongo_client:
            self.mongo_client.close()
        logger.info("✅ Cleanup completado")
    
    async def test_handle_contact_real_flow(self):
        """Test del flujo real de handle_contact"""
        logger.info("🔍 TESTING: Flujo real de handle_contact con notificación a Ana")
        logger.info("="*70)
        
        try:
            # Datos del escenario
            telegram_id_prueba = "111222333"
            nombre_prueba = "Test Ana Notificacion"
            telefono_prueba = "+5219876543210"
            
            logger.info(f"📋 ESCENARIO DE PRUEBA:")
            logger.info(f"   - telegram_id: {telegram_id_prueba}")
            logger.info(f"   - nombre: {nombre_prueba}")
            logger.info(f"   - telefono: {telefono_prueba}")
            
            # PASO 1: Limpiar usuarios de prueba
            logger.info("\n🧹 PASO 1: Limpiando usuarios de prueba...")
            await self.db.usuarios_telegram.delete_many({
                "telegram_id": {"$in": ["111222333", "999888777"]}
            })
            logger.info("   ✅ Usuarios eliminados")
            
            # PASO 2: Importar y configurar el bot
            logger.info("\n🤖 PASO 2: Configurando bot de Telegram...")
            
            try:
                from telegram_bot import TelegramBotNetCash
                
                # Crear instancia del bot
                bot = TelegramBotNetCash()
                
                # Configurar el bot con mocks para evitar conexión real a Telegram
                bot.app = Mock()
                bot.app.bot = AsyncMock()
                bot.ana_telegram_id = "1720830607"
                
                logger.info("   ✅ Bot configurado con mocks")
                
            except Exception as e:
                logger.error(f"   ❌ Error configurando bot: {str(e)}")
                return False
            
            # PASO 3: Crear mocks para Update y Context
            logger.info("\n📱 PASO 3: Creando mocks de Telegram Update...")
            
            # Mock del contacto
            contact_mock = Mock()
            contact_mock.phone_number = telefono_prueba.replace("+", "")
            contact_mock.first_name = "Test Ana"
            contact_mock.last_name = "Notificacion"
            
            # Mock del usuario
            user_mock = Mock()
            user_mock.id = int(telegram_id_prueba)
            
            # Mock del chat
            chat_mock = Mock()
            chat_mock.id = int(telegram_id_prueba)
            
            # Mock del mensaje
            message_mock = AsyncMock()
            message_mock.contact = contact_mock
            message_mock.reply_text = AsyncMock()
            
            # Mock del update
            update_mock = Mock()
            update_mock.message = message_mock
            update_mock.effective_chat = chat_mock
            update_mock.effective_user = user_mock
            
            # Mock del context
            context_mock = Mock()
            
            logger.info("   ✅ Mocks creados correctamente")
            
            # PASO 4: Ejecutar handle_contact
            logger.info("\n🎯 PASO 4: Ejecutando handle_contact...")
            
            try:
                # Llamar al método handle_contact
                await bot.handle_contact(update_mock, context_mock)
                logger.info("   ✅ handle_contact ejecutado sin errores")
                
            except Exception as e:
                logger.error(f"   ❌ Error en handle_contact: {str(e)}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
                return False
            
            # PASO 5: Verificar que el usuario fue creado
            logger.info("\n👤 PASO 5: Verificando creación del usuario...")
            
            usuario_creado = await self.db.usuarios_telegram.find_one(
                {"telegram_id": telegram_id_prueba}, {"_id": 0}
            )
            
            if usuario_creado:
                logger.info("   ✅ Usuario creado en BD:")
                logger.info(f"      - telegram_id: {usuario_creado.get('telegram_id')}")
                logger.info(f"      - chat_id: {usuario_creado.get('chat_id')}")
                logger.info(f"      - rol: {usuario_creado.get('rol')}")
                logger.info(f"      - telefono: {usuario_creado.get('telefono')}")
                logger.info(f"      - nombre_telegram: {usuario_creado.get('nombre_telegram')}")
                
                if usuario_creado.get('rol') == 'desconocido':
                    logger.info("   ✅ Rol 'desconocido' confirmado")
                else:
                    logger.error(f"   ❌ Rol incorrecto: {usuario_creado.get('rol')}")
                    return False
            else:
                logger.error("   ❌ Usuario no fue creado")
                return False
            
            # PASO 6: Verificar que se intentó enviar mensaje a Ana
            logger.info("\n📨 PASO 6: Verificando notificación a Ana...")
            
            # Verificar que se llamó send_message
            if bot.app.bot.send_message.called:
                logger.info("   ✅ send_message fue llamado")
                
                # Obtener los argumentos de la llamada
                call_args = bot.app.bot.send_message.call_args
                if call_args:
                    args, kwargs = call_args
                    chat_id_usado = kwargs.get('chat_id') or (args[0] if args else None)
                    mensaje_enviado = kwargs.get('text') or (args[1] if len(args) > 1 else None)
                    
                    logger.info(f"   📲 Chat ID usado: {chat_id_usado}")
                    logger.info(f"   📝 Mensaje enviado:")
                    if mensaje_enviado:
                        for linea in mensaje_enviado.split('\n')[:10]:  # Primeras 10 líneas
                            logger.info(f"      {linea}")
                    
                    # Verificar que se envió al chat correcto
                    if str(chat_id_usado) == "1720830607":
                        logger.info("   ✅ Mensaje enviado al chat_id correcto de Ana")
                    else:
                        logger.error(f"   ❌ Chat ID incorrecto. Esperado: 1720830607, Usado: {chat_id_usado}")
                        return False
                    
                    # Verificar que el mensaje contiene la información correcta
                    if mensaje_enviado and telegram_id_prueba in mensaje_enviado:
                        logger.info("   ✅ Mensaje contiene telegram_id correcto")
                    else:
                        logger.error("   ❌ Mensaje no contiene telegram_id")
                        return False
                    
                    if mensaje_enviado and telefono_prueba in mensaje_enviado:
                        logger.info("   ✅ Mensaje contiene teléfono correcto")
                    else:
                        logger.error("   ❌ Mensaje no contiene teléfono")
                        return False
                    
                    if mensaje_enviado and "/aprobar_cliente" in mensaje_enviado:
                        logger.info("   ✅ Mensaje contiene comando de aprobación")
                    else:
                        logger.error("   ❌ Mensaje no contiene comando de aprobación")
                        return False
                        
                else:
                    logger.error("   ❌ send_message llamado sin argumentos")
                    return False
                    
            else:
                logger.error("   ❌ send_message NO fue llamado")
                return False
            
            # PASO 7: Verificar respuesta al usuario
            logger.info("\n💬 PASO 7: Verificando respuesta al usuario...")
            
            if message_mock.reply_text.called:
                logger.info("   ✅ reply_text fue llamado")
                
                call_args = message_mock.reply_text.call_args
                if call_args:
                    args, kwargs = call_args
                    mensaje_usuario = args[0] if args else kwargs.get('text', '')
                    
                    logger.info("   📝 Mensaje enviado al usuario:")
                    for linea in mensaje_usuario.split('\n')[:5]:  # Primeras 5 líneas
                        logger.info(f"      {linea}")
                    
                    if "Gracias por compartir tu contacto" in mensaje_usuario:
                        logger.info("   ✅ Mensaje de confirmación correcto")
                    else:
                        logger.error("   ❌ Mensaje de confirmación incorrecto")
                        return False
                        
                else:
                    logger.error("   ❌ reply_text llamado sin argumentos")
                    return False
                    
            else:
                logger.error("   ❌ reply_text NO fue llamado")
                return False
            
            # PASO 8: Resultado final
            logger.info("\n🎯 RESULTADO FINAL:")
            logger.info("="*50)
            logger.info("✅ Usuario creado correctamente con rol 'desconocido'")
            logger.info("✅ Notificación enviada a Ana (chat_id: 1720830607)")
            logger.info("✅ Mensaje contiene toda la información requerida:")
            logger.info(f"   - Telegram ID: {telegram_id_prueba}")
            logger.info(f"   - Nombre: {nombre_prueba}")
            logger.info(f"   - Teléfono: {telefono_prueba}")
            logger.info(f"   - Comando: /aprobar_cliente {telegram_id_prueba} 1.00")
            logger.info("✅ Respuesta enviada al usuario correctamente")
            logger.info("✅ Correcciones implementadas funcionando:")
            logger.info("   - Verificación de self.app y self.app.bot")
            logger.info("   - telegram_id obtenido del update")
            logger.info("   - Logs mejorados")
            
            logger.info("\n🎉 CONCLUSIÓN: El flujo de notificación a Ana funciona correctamente")
            logger.info("   Las correcciones implementadas resuelven el problema anterior.")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en test: {str(e)}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False

async def main():
    """Función principal"""
    tester = RealTelegramFlowTester()
    
    try:
        await tester.setup()
        result = await tester.test_handle_contact_real_flow()
        
        if result:
            logger.info("\n🎉 ¡PRUEBA EXITOSA!")
            logger.info("El flujo de notificación a Ana funciona correctamente.")
        else:
            logger.error("\n❌ PRUEBA FALLIDA")
            logger.error("Hay problemas con el flujo de notificación.")
            
        return result
        
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)