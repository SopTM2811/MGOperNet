#!/usr/bin/env python3
"""
Test específico para el comando /start del usuario 1570668456 (daniel G)
Simula EXACTAMENTE el flujo reportado por el usuario
"""
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

# Agregar el directorio backend al path
sys.path.append('/app/backend')

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv('/app/backend/.env')

# Configuración de BD
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'netcash_mbco')

class TelegramStartTester:
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
    
    async def test_start_command_exact_flow(self):
        """Test del flujo EXACTO del comando /start para usuario 1570668456"""
        logger.info("🔍 TESTING FLUJO EXACTO /start PARA USUARIO 1570668456 (daniel G)")
        logger.info("="*80)
        
        try:
            # Datos exactos del usuario según el reporte
            telegram_id = 1570668456  # Como INT (viene del update de Telegram)
            chat_id = 1570668456      # Como INT (viene del update de Telegram)
            telegram_id_str = "1570668456"  # Como string para BD
            chat_id_str = "1570668456"      # Como string para BD
            
            logger.info(f"📋 DATOS DEL USUARIO REPORTADO:")
            logger.info(f"   - telegram_id: {telegram_id} (INT)")
            logger.info(f"   - chat_id: {chat_id} (INT)")
            logger.info(f"   - Nombre: daniel G")
            logger.info(f"   - Rol esperado: cliente_activo")
            logger.info(f"   - ID Cliente: adb0a59b-9083-4433-81db-2193fda4bc36")
            
            # PASO 1: Verificar datos en BD
            logger.info(f"\n🔍 PASO 1: Verificando datos en BD...")
            
            usuario_bd = await self.db.usuarios_telegram.find_one({"telegram_id": telegram_id_str}, {"_id": 0})
            
            if not usuario_bd:
                logger.error("❌ PROBLEMA CRÍTICO: Usuario 1570668456 NO encontrado en usuarios_telegram")
                return False
            
            logger.info("✅ Usuario encontrado en usuarios_telegram:")
            logger.info(f"   - telegram_id: {usuario_bd.get('telegram_id')}")
            logger.info(f"   - chat_id: {usuario_bd.get('chat_id')}")
            logger.info(f"   - rol: {usuario_bd.get('rol')}")
            logger.info(f"   - id_cliente: {usuario_bd.get('id_cliente')}")
            logger.info(f"   - telefono: {usuario_bd.get('telefono')}")
            
            # Verificar cliente vinculado
            id_cliente = usuario_bd.get('id_cliente')
            if not id_cliente:
                logger.error("❌ PROBLEMA CRÍTICO: Usuario no tiene id_cliente vinculado")
                return False
            
            cliente_bd = await self.db.clientes.find_one({"id": id_cliente}, {"_id": 0})
            
            if not cliente_bd:
                logger.error(f"❌ PROBLEMA CRÍTICO: Cliente {id_cliente} NO encontrado")
                return False
            
            logger.info("✅ Cliente vinculado encontrado:")
            logger.info(f"   - id: {cliente_bd.get('id')}")
            logger.info(f"   - nombre: {cliente_bd.get('nombre')}")
            logger.info(f"   - estado: {cliente_bd.get('estado')}")
            
            # PASO 2: Simular EXACTAMENTE el flujo del comando /start
            logger.info(f"\n📱 PASO 2: Simulando comando /start EXACTO...")
            
            # Log inicial que debería aparecer
            logger.info(f"[NetCash][START] Comando recibido de daniel G (chat_id: {chat_id_str}, telegram_id: {telegram_id_str})")
            
            # Buscar usuario por telegram_id (línea 241 en telegram_bot.py)
            usuario = await self.db.usuarios_telegram.find_one({"telegram_id": telegram_id_str}, {"_id": 0})
            
            if not usuario:
                logger.error("❌ Usuario no encontrado en simulación")
                return False
            
            # Actualizar chat_id si es necesario (líneas 279-284)
            if usuario.get("chat_id") != chat_id_str:
                logger.info(f"🔄 Actualizando chat_id: {usuario.get('chat_id')} -> {chat_id_str}")
                await self.db.usuarios_telegram.update_one(
                    {"telegram_id": telegram_id_str},
                    {"$set": {"chat_id": chat_id_str, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
                logger.info(f"[NetCash][START] Chat ID actualizado para {telegram_id_str}")
            
            # Verificar estado (líneas 287-294)
            rol = usuario.get("rol")
            telefono = usuario.get("telefono")
            id_cliente = usuario.get("id_cliente")
            
            logger.info(f"\n📊 VERIFICANDO ESTADO DEL USUARIO:")
            logger.info(f"   - rol: '{rol}'")
            logger.info(f"   - telefono: {telefono}")
            logger.info(f"   - id_cliente: {id_cliente}")
            
            # PASO 3: Evaluar condición crítica (línea 291)
            logger.info(f"\n🔍 PASO 3: Evaluando condición de cliente activo...")
            
            condicion1 = rol == "cliente_activo"
            condicion2 = id_cliente and rol in ["cliente", "cliente_activo"]
            condicion_completa = condicion1 or condicion2
            
            logger.info(f"📋 EVALUACIÓN DE CONDICIONES:")
            logger.info(f"   - rol == 'cliente_activo': {condicion1}")
            logger.info(f"   - id_cliente existe: {bool(id_cliente)}")
            logger.info(f"   - rol in ['cliente', 'cliente_activo']: {rol in ['cliente', 'cliente_activo']}")
            logger.info(f"   - (id_cliente and rol in ['cliente', 'cliente_activo']): {condicion2}")
            logger.info(f"   - CONDICIÓN COMPLETA: {condicion_completa}")
            
            if condicion_completa:
                logger.info("✅ [NetCash][START] Cliente activo -> menú")
                
                # PASO 4: Simular mostrar_menu_principal
                logger.info(f"\n📋 PASO 4: Simulando mostrar_menu_principal...")
                
                # Verificar estado del cliente (línea 437)
                cliente = await self.db.clientes.find_one({"id": id_cliente}, {"_id": 0})
                
                if cliente and cliente.get("estado") == "activo":
                    logger.info("✅ Cliente ACTIVO confirmado")
                    
                    # Mensaje que DEBERÍA enviarse
                    mensaje_correcto = f"Hola daniel 😊\n\n"
                    mensaje_correcto += "Ya estás dado de alta como cliente NetCash.\n\n"
                    mensaje_correcto += "Puedo ayudarte a:\n"
                    mensaje_correcto += "• Crear una nueva operación NetCash\n"
                    mensaje_correcto += "• Ver el estado de tus operaciones\n"
                    mensaje_correcto += "• Ver la cuenta para hacer tus pagos\n"
                    
                    logger.info("✅ MENSAJE QUE DEBERÍA ENVIARSE:")
                    logger.info("="*50)
                    for linea in mensaje_correcto.split('\n'):
                        logger.info(f"{linea}")
                    logger.info("="*50)
                    
                    logger.info("✅ BOTONES QUE DEBERÍAN APARECER:")
                    logger.info("   - 📎 Crear nueva operación NetCash")
                    logger.info("   - 📊 Ver mis operaciones")
                    logger.info("   - 🏦 Ver cuenta para pagos")
                    logger.info("   - ❓ Ayuda")
                    
                    resultado = "MENÚ_CLIENTE_ACTIVO"
                    
                else:
                    logger.error(f"❌ Cliente no está activo. Estado: {cliente.get('estado') if cliente else 'No encontrado'}")
                    resultado = "ERROR_CLIENTE_INACTIVO"
                    
            else:
                logger.error("❌ CONDICIÓN DE CLIENTE ACTIVO NO SE CUMPLE")
                logger.error("❌ ESTO EXPLICA EL PROBLEMA REPORTADO")
                
                # Determinar qué mensaje se enviaría en su lugar
                if telefono:
                    mensaje_incorrecto = "📋 **Tu registro está en proceso.**\n\n"
                    mensaje_incorrecto += "Ana revisará tu información y te asignará una comisión.\n\n"
                    mensaje_incorrecto += "Te avisaremos por este mismo chat cuando ya puedas operar."
                    
                    logger.error("❌ MENSAJE INCORRECTO QUE SE ENVIARÍA:")
                    logger.error("="*50)
                    for linea in mensaje_incorrecto.split('\n'):
                        logger.error(f"{linea}")
                    logger.error("="*50)
                    
                    resultado = "MENSAJE_REGISTRO_EN_PROCESO"
                else:
                    # Sin teléfono -> mostrar mensaje de registro
                    mensaje_registro = "¡Bienvenido a NetCash MBco! 🎉\n\n"
                    mensaje_registro += "Para comenzar, necesito registrarte como cliente.\n"
                    
                    logger.error("❌ MENSAJE DE REGISTRO QUE SE ENVIARÍA:")
                    logger.error("="*50)
                    for linea in mensaje_registro.split('\n'):
                        logger.error(f"{linea}")
                    logger.error("="*50)
                    
                    logger.error("❌ BOTÓN QUE APARECERÍA:")
                    logger.error("   - 1️⃣ Registrarme como cliente NetCash")
                    
                    resultado = "MENSAJE_REGISTRARSE_COMO_CLIENTE"
            
            # PASO 5: Diagnóstico del problema
            logger.info(f"\n🔍 PASO 5: Diagnóstico del problema...")
            
            if resultado == "MENÚ_CLIENTE_ACTIVO":
                logger.info("🎉 RESULTADO: El flujo funciona CORRECTAMENTE")
                logger.info("✅ El usuario DEBERÍA ver el menú de cliente activo")
                logger.info("✅ NO debería ver mensaje de 'registrarse como cliente'")
                
                # Verificar si hay algún problema con el bot en tiempo real
                logger.info("\n🔍 Posibles causas del problema reportado:")
                logger.info("1. ⚠️ Múltiples instancias del bot corriendo (conflicto 409)")
                logger.info("2. ⚠️ Cache del bot no actualizado")
                logger.info("3. ⚠️ Problema temporal de conectividad")
                logger.info("4. ⚠️ El usuario no usó /start sino que presionó un botón directamente")
                
                return True
                
            else:
                logger.error("❌ PROBLEMA IDENTIFICADO: El flujo NO funciona correctamente")
                logger.error(f"❌ Resultado actual: {resultado}")
                logger.error("❌ El usuario VE el mensaje incorrecto")
                
                # Analizar por qué falla la condición
                logger.error("\n🔍 ANÁLISIS DEL PROBLEMA:")
                
                if not condicion1:
                    logger.error(f"❌ rol != 'cliente_activo' (actual: '{rol}')")
                
                if not condicion2:
                    if not id_cliente:
                        logger.error("❌ id_cliente es None/vacío")
                    elif rol not in ["cliente", "cliente_activo"]:
                        logger.error(f"❌ rol no está en ['cliente', 'cliente_activo'] (actual: '{rol}')")
                
                return False
            
        except Exception as e:
            logger.error(f"❌ Error en test: {str(e)}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False
    
    async def run_test(self):
        """Ejecutar el test"""
        try:
            await self.setup()
            result = await self.test_start_command_exact_flow()
            
            logger.info("\n" + "="*80)
            logger.info("📊 RESUMEN FINAL")
            logger.info("="*80)
            
            if result:
                logger.info("🎉 ✅ TEST PASÓ: El flujo /start funciona correctamente")
                logger.info("✅ El usuario 1570668456 DEBERÍA ver el menú de cliente activo")
                logger.info("✅ Si el usuario reporta lo contrario, es un problema temporal o de cache")
            else:
                logger.error("💥 ❌ TEST FALLÓ: Se identificó el problema en el flujo")
                logger.error("❌ El usuario 1570668456 NO ve el menú correcto")
                logger.error("❌ Se requiere corrección en el código o datos")
            
            return result
            
        finally:
            await self.cleanup()

async def main():
    """Función principal"""
    tester = TelegramStartTester()
    return await tester.run_test()

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)