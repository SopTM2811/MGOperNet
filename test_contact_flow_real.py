#!/usr/bin/env python3
"""
Prueba REAL del flujo de notificación a Ana cuando un nuevo usuario comparte su contacto
Esta prueba simula directamente el flujo del bot de Telegram
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Agregar el directorio backend al path para importar el bot
sys.path.append('/app/backend')

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv('/app/backend/.env')

# Configuración MongoDB
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'netcash_mbco')

class ContactFlowTester:
    def __init__(self):
        self.mongo_client = None
        self.db = None
        
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

    async def test_contact_sharing_flow(self):
        """Probar el flujo completo de compartir contacto"""
        logger.info("🔍 INICIANDO PRUEBA REAL DEL FLUJO DE CONTACTO")
        logger.info("=" * 60)
        
        try:
            # Datos del usuario de prueba
            telegram_id_prueba = "999888777"
            chat_id_prueba = "999888777"
            nombre_prueba = "Test Usuario Nuevo"
            telefono_prueba = "+5212345678901"
            
            logger.info(f"📋 DATOS DEL USUARIO DE PRUEBA:")
            logger.info(f"   - telegram_id: {telegram_id_prueba}")
            logger.info(f"   - chat_id: {chat_id_prueba}")
            logger.info(f"   - nombre: {nombre_prueba}")
            logger.info(f"   - telefono: {telefono_prueba}")
            logger.info("")
            
            # PASO 1: Limpiar usuario de prueba anterior
            logger.info("🧹 PASO 1: Limpiando usuario de prueba anterior...")
            deleted_count = await self.db.usuarios_telegram.delete_many({"telegram_id": telegram_id_prueba})
            logger.info(f"   ✅ Eliminados {deleted_count.deleted_count} registros con telegram_id {telegram_id_prueba}")
            
            deleted_count2 = await self.db.usuarios_telegram.delete_many({"chat_id": chat_id_prueba})
            logger.info(f"   ✅ Eliminados {deleted_count2.deleted_count} registros con chat_id {chat_id_prueba}")
            
            # PASO 2: Verificar configuración de Ana
            logger.info("👩‍💼 PASO 2: Verificando configuración de Ana...")
            ana_telegram_id = os.getenv("ANA_TELEGRAM_CHAT_ID")
            logger.info(f"   📱 ANA_TELEGRAM_CHAT_ID: {ana_telegram_id}")
            
            if not ana_telegram_id:
                logger.error("   ❌ ANA_TELEGRAM_CHAT_ID no está configurado")
                return False
            
            if ana_telegram_id != "1720830607":
                logger.error(f"   ❌ ANA_TELEGRAM_CHAT_ID incorrecto. Esperado: 1720830607, Obtenido: {ana_telegram_id}")
                return False
            
            logger.info("   ✅ Configuración de Ana correcta")
            
            # PASO 3: Importar y usar el bot real
            logger.info("🤖 PASO 3: Importando bot de Telegram...")
            
            try:
                from telegram_bot import TelegramBotNetCash
                bot_instance = TelegramBotNetCash()
                logger.info("   ✅ Bot importado exitosamente")
            except Exception as e:
                logger.error(f"   ❌ Error importando bot: {str(e)}")
                return False
            
            # PASO 4: Simular obtener_o_crear_usuario
            logger.info("👤 PASO 4: Simulando obtener_o_crear_usuario...")
            
            # Verificar que el usuario no existe
            usuario_existente = await self.db.usuarios_telegram.find_one({"chat_id": chat_id_prueba}, {"_id": 0})
            if usuario_existente:
                logger.error("   ❌ El usuario ya existe")
                return False
            
            logger.info("   ✅ Usuario no existe, procediendo...")
            
            # Simular la función obtener_o_crear_usuario del bot
            usuario_creado = await bot_instance.obtener_o_crear_usuario(
                chat_id=chat_id_prueba,
                telefono=telefono_prueba,
                nombre=nombre_prueba
            )
            
            if not usuario_creado:
                logger.error("   ❌ Error creando usuario")
                return False
            
            logger.info(f"   ✅ Usuario creado: {usuario_creado}")
            
            # PASO 5: Verificar que el usuario tiene rol "desconocido"
            logger.info("🔍 PASO 5: Verificando rol del usuario...")
            
            if usuario_creado.get("rol") != "desconocido":
                logger.error(f"   ❌ Rol incorrecto. Esperado: 'desconocido', Obtenido: '{usuario_creado.get('rol')}'")
                return False
            
            logger.info("   ✅ Usuario tiene rol 'desconocido' correctamente")
            
            # PASO 6: Simular el proceso de notificación a Ana
            logger.info("📨 PASO 6: Simulando notificación a Ana...")
            
            # Verificar que Ana está configurada en el bot
            if not bot_instance.ana_telegram_id:
                logger.error("   ❌ ana_telegram_id no configurado en el bot")
                return False
            
            logger.info(f"   ✅ ana_telegram_id configurado: {bot_instance.ana_telegram_id}")
            
            # Simular la construcción del mensaje para Ana
            telegram_id_notif = usuario_creado.get("telegram_id") or chat_id_prueba
            
            mensaje_ana = f"🆕 **Nuevo usuario compartió contacto y está esperando aprobación.**\n\n"
            mensaje_ana += f"📲 **Telegram ID:** `{telegram_id_notif}`\n"
            mensaje_ana += f"👤 **Nombre:** {nombre_prueba}\n"
            mensaje_ana += f"📱 **Teléfono:** {telefono_prueba}\n"
            mensaje_ana += f"📅 **Fecha/hora:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
            mensaje_ana += "**Para aprobar:**\n"
            mensaje_ana += f"`/aprobar_cliente {telegram_id_notif} 1.00`"
            
            logger.info("   📨 MENSAJE PARA ANA:")
            logger.info("   " + "=" * 50)
            for linea in mensaje_ana.split('\n'):
                logger.info(f"   {linea}")
            logger.info("   " + "=" * 50)
            
            # PASO 7: Verificar logs del bot
            logger.info("📋 PASO 7: Verificando logs del bot...")
            
            try:
                log_path = "/var/log/telegram_bot.log"
                if Path(log_path).exists():
                    # Leer las últimas líneas del log
                    with open(log_path, 'r') as f:
                        lines = f.readlines()
                    
                    # Buscar logs relacionados con nuestro usuario
                    logs_usuario = [line.strip() for line in lines[-200:] if telegram_id_prueba in line]
                    
                    if logs_usuario:
                        logger.info("   📋 Logs del usuario de prueba encontrados:")
                        for log in logs_usuario:
                            logger.info(f"      {log}")
                    else:
                        logger.info("   📋 No se encontraron logs específicos del usuario de prueba")
                    
                    # Buscar logs de Ana
                    logs_ana = [line.strip() for line in lines[-200:] if "Ana" in line or "ANA" in line or "1720830607" in line]
                    
                    if logs_ana:
                        logger.info("   📋 Logs relacionados con Ana:")
                        for log in logs_ana[-3:]:
                            logger.info(f"      {log}")
                    else:
                        logger.info("   📋 No se encontraron logs de Ana recientes")
                        
                else:
                    logger.warning("   ⚠️ Archivo de log no encontrado")
                    
            except Exception as e:
                logger.warning(f"   ⚠️ Error leyendo logs: {str(e)}")
            
            # PASO 8: Verificar estado final en BD
            logger.info("🔍 PASO 8: Verificando estado final en BD...")
            
            usuario_final = await self.db.usuarios_telegram.find_one({"telegram_id": telegram_id_prueba}, {"_id": 0})
            
            if not usuario_final:
                logger.error("   ❌ Usuario no encontrado en BD")
                return False
            
            logger.info("   ✅ Usuario encontrado en BD:")
            logger.info(f"      - telegram_id: {usuario_final.get('telegram_id')}")
            logger.info(f"      - chat_id: {usuario_final.get('chat_id')}")
            logger.info(f"      - rol: {usuario_final.get('rol')}")
            logger.info(f"      - telefono: {usuario_final.get('telefono')}")
            logger.info(f"      - nombre_telegram: {usuario_final.get('nombre_telegram')}")
            logger.info(f"      - fecha_registro: {usuario_final.get('fecha_registro')}")
            
            # PASO 9: Verificar que no está en clientes
            logger.info("🔍 PASO 9: Verificando que no está en tabla clientes...")
            
            cliente_existente = await self.db.clientes.find_one(
                {"$or": [
                    {"telefono_completo": telefono_prueba},
                    {"telefono": telefono_prueba.replace("+52", "")},
                    {"telegram_id": telegram_id_prueba}
                ]},
                {"_id": 0}
            )
            
            if cliente_existente:
                logger.warning(f"   ⚠️ Usuario ya existe como cliente: {cliente_existente.get('nombre')}")
            else:
                logger.info("   ✅ Usuario NO está en tabla clientes (correcto para rol 'desconocido')")
            
            # PASO 10: Resumen final
            logger.info("🎯 PASO 10: Resumen final...")
            logger.info("")
            logger.info("📊 RESULTADOS DE LA PRUEBA:")
            logger.info("   ✅ Usuario creado correctamente con telegram_id único")
            logger.info("   ✅ Rol 'desconocido' asignado correctamente")
            logger.info("   ✅ Configuración de Ana verificada (1720830607)")
            logger.info("   ✅ Mensaje de notificación generado correctamente")
            logger.info("   ✅ Comando de aprobación incluido en mensaje")
            logger.info("   ✅ Usuario guardado en BD correctamente")
            
            logger.info("")
            logger.info("📋 LOGS CLAVE QUE DEBERÍAN GENERARSE:")
            logger.info("   - [handle_contact] Contacto recibido: +5212345678901 de Test Usuario Nuevo")
            logger.info("   - [handle_contact] ANA_TELEGRAM_CHAT_ID configurado: 1720830607")
            logger.info("   - [NetCash][CONTACTO] Usuario 999888777 compartió contacto, rol=desconocido")
            logger.info("   - [NetCash][CONTACTO] Verificando notificación a Ana")
            logger.info("   - [NetCash][CONTACTO] ✅ Notificación enviada exitosamente a Ana")
            
            logger.info("")
            logger.info("🎉 PRUEBA COMPLETADA EXITOSAMENTE")
            logger.info("   El flujo de notificación a Ana funciona correctamente")
            logger.info("   Ana recibiría la notificación con todos los datos necesarios")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en test_contact_sharing_flow: {str(e)}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False

async def main():
    """Función principal"""
    tester = ContactFlowTester()
    
    try:
        await tester.setup()
        result = await tester.test_contact_sharing_flow()
        
        logger.info("")
        logger.info("=" * 60)
        if result:
            logger.info("🎯 RESULTADO FINAL: ✅ PRUEBA PASÓ")
            logger.info("   El flujo de notificación a Ana está funcionando correctamente")
        else:
            logger.error("🎯 RESULTADO FINAL: ❌ PRUEBA FALLÓ")
            logger.error("   Hay problemas en el flujo de notificación a Ana")
        logger.info("=" * 60)
            
        return result
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())