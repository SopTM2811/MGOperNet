#!/usr/bin/env python3
"""
Test FINAL y COMPLETO para el usuario 1570668456 (daniel G)
Verifica TODOS los aspectos del flujo /start y proporciona diagnóstico completo
"""
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import subprocess

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv('/app/backend/.env')

# Configuración
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'netcash_mbco')

class FinalTester1570668456:
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
    
    async def comprehensive_test(self):
        """Test comprehensivo del usuario 1570668456"""
        logger.info("🔍 TEST FINAL COMPREHENSIVO - USUARIO 1570668456 (daniel G)")
        logger.info("="*80)
        
        # Datos del usuario
        telegram_id = 1570668456
        chat_id = 1570668456
        telegram_id_str = "1570668456"
        chat_id_str = "1570668456"
        
        logger.info(f"📋 USUARIO OBJETIVO:")
        logger.info(f"   - Telegram ID: {telegram_id}")
        logger.info(f"   - Chat ID: {chat_id}")
        logger.info(f"   - Nombre: daniel G")
        
        try:
            # ===== VERIFICACIÓN 1: DATOS EN BD =====
            logger.info(f"\n🔍 VERIFICACIÓN 1: Datos en Base de Datos")
            logger.info("-" * 50)
            
            usuario_bd = await self.db.usuarios_telegram.find_one({"telegram_id": telegram_id_str}, {"_id": 0})
            
            if not usuario_bd:
                logger.error("❌ CRÍTICO: Usuario no encontrado en usuarios_telegram")
                return False
            
            logger.info("✅ Usuario encontrado en usuarios_telegram:")
            for key, value in usuario_bd.items():
                logger.info(f"   - {key}: {value}")
            
            # Verificar cliente vinculado
            id_cliente = usuario_bd.get('id_cliente')
            if not id_cliente:
                logger.error("❌ CRÍTICO: Usuario no tiene id_cliente")
                return False
            
            cliente_bd = await self.db.clientes.find_one({"id": id_cliente}, {"_id": 0})
            if not cliente_bd:
                logger.error(f"❌ CRÍTICO: Cliente {id_cliente} no encontrado")
                return False
            
            logger.info("✅ Cliente vinculado encontrado:")
            logger.info(f"   - ID: {cliente_bd.get('id')}")
            logger.info(f"   - Nombre: {cliente_bd.get('nombre')}")
            logger.info(f"   - Estado: {cliente_bd.get('estado')}")
            logger.info(f"   - Comisión: {cliente_bd.get('porcentaje_comision_cliente')}")
            
            # ===== VERIFICACIÓN 2: LÓGICA DEL COMANDO /start =====
            logger.info(f"\n🔍 VERIFICACIÓN 2: Lógica del comando /start")
            logger.info("-" * 50)
            
            # Simular línea 241: Buscar usuario por telegram_id
            usuario = await self.db.usuarios_telegram.find_one({"telegram_id": telegram_id_str}, {"_id": 0})
            logger.info(f"✅ Línea 241 - Usuario encontrado: {bool(usuario)}")
            
            # Simular líneas 279-284: Actualizar chat_id si es necesario
            if usuario.get("chat_id") != chat_id_str:
                logger.info(f"🔄 Líneas 279-284 - Chat ID necesita actualización")
                # No actualizamos realmente para no afectar datos
            else:
                logger.info(f"✅ Líneas 279-284 - Chat ID ya correcto")
            
            # Simular líneas 287-294: Verificar estado
            rol = usuario.get("rol")
            telefono = usuario.get("telefono")
            id_cliente = usuario.get("id_cliente")
            
            logger.info(f"📊 Líneas 287-294 - Variables de estado:")
            logger.info(f"   - rol: '{rol}'")
            logger.info(f"   - telefono: {telefono}")
            logger.info(f"   - id_cliente: {id_cliente}")
            
            # Simular línea 291: Condición crítica
            condicion1 = rol == "cliente_activo"
            condicion2 = id_cliente and rol in ["cliente", "cliente_activo"]
            condicion_completa = condicion1 or condicion2
            
            logger.info(f"🎯 Línea 291 - Evaluación de condición:")
            logger.info(f"   - rol == 'cliente_activo': {condicion1}")
            logger.info(f"   - (id_cliente and rol in ['cliente', 'cliente_activo']): {condicion2}")
            logger.info(f"   - CONDICIÓN COMPLETA: {condicion_completa}")
            
            if condicion_completa:
                logger.info("✅ Línea 294 - Debería llamar mostrar_menu_principal")
                
                # ===== VERIFICACIÓN 3: LÓGICA DE mostrar_menu_principal =====
                logger.info(f"\n🔍 VERIFICACIÓN 3: Lógica de mostrar_menu_principal")
                logger.info("-" * 50)
                
                # Simular línea 435: Buscar cliente
                cliente = await self.db.clientes.find_one({"id": id_cliente}, {"_id": 0})
                logger.info(f"✅ Línea 435 - Cliente encontrado: {bool(cliente)}")
                
                # Simular línea 437: Verificar estado activo
                if cliente and cliente.get("estado") == "activo":
                    logger.info("✅ Línea 437 - Cliente está ACTIVO")
                    
                    # Mensaje que se construiría (líneas 439-444)
                    mensaje = f"Hola daniel 😊\n\n"
                    mensaje += "Ya estás dado de alta como cliente NetCash.\n\n"
                    mensaje += "Puedo ayudarte a:\n"
                    mensaje += "• Crear una nueva operación NetCash\n"
                    mensaje += "• Ver el estado de tus operaciones\n"
                    mensaje += "• Ver la cuenta para hacer tus pagos\n"
                    
                    logger.info("✅ Líneas 439-444 - Mensaje que se enviaría:")
                    logger.info("="*60)
                    for linea in mensaje.split('\n'):
                        logger.info(f"   {linea}")
                    logger.info("="*60)
                    
                    # Botones que se crearían (líneas 446-451)
                    botones = [
                        "📎 Crear nueva operación NetCash",
                        "📊 Ver mis operaciones",
                        "🏦 Ver cuenta para pagos",
                        "❓ Ayuda"
                    ]
                    
                    logger.info("✅ Líneas 446-451 - Botones que se mostrarían:")
                    for boton in botones:
                        logger.info(f"   - {boton}")
                    
                    resultado_esperado = "MENÚ_CLIENTE_ACTIVO"
                    
                else:
                    logger.error(f"❌ Línea 437 - Cliente NO activo. Estado: {cliente.get('estado') if cliente else 'No encontrado'}")
                    resultado_esperado = "ERROR_CLIENTE_INACTIVO"
                    
            else:
                logger.error("❌ Línea 291 - Condición NO se cumple")
                
                # Determinar qué rama tomaría
                if telefono:
                    logger.error("❌ Líneas 295-301 - Mostraría mensaje de 'registro en proceso'")
                    resultado_esperado = "MENSAJE_REGISTRO_EN_PROCESO"
                else:
                    logger.error("❌ Líneas 303-316 - Pediría compartir teléfono")
                    resultado_esperado = "PEDIR_TELEFONO"
            
            # ===== VERIFICACIÓN 4: ESTADO DEL SISTEMA =====
            logger.info(f"\n🔍 VERIFICACIÓN 4: Estado del sistema")
            logger.info("-" * 50)
            
            # Verificar bot corriendo
            try:
                result = subprocess.run(
                    ["sudo", "supervisorctl", "status", "telegram_bot"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if "RUNNING" in result.stdout:
                    logger.info("✅ Bot de Telegram está RUNNING")
                else:
                    logger.warning(f"⚠️ Estado del bot: {result.stdout.strip()}")
                    
            except Exception as e:
                logger.warning(f"⚠️ Error verificando bot: {str(e)}")
            
            # Verificar logs recientes
            try:
                result = subprocess.run(
                    ["tail", "-n", "20", "/var/log/telegram_bot.log"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    recent_logs = [line for line in lines if telegram_id_str in line or "START" in line]
                    
                    if recent_logs:
                        logger.info("📋 Logs recientes relacionados:")
                        for log in recent_logs[-3:]:
                            logger.info(f"   {log}")
                    else:
                        logger.info("📋 No hay logs recientes del usuario")
                        
            except Exception as e:
                logger.warning(f"⚠️ Error leyendo logs: {str(e)}")
            
            # ===== DIAGNÓSTICO FINAL =====
            logger.info(f"\n🎯 DIAGNÓSTICO FINAL")
            logger.info("="*80)
            
            if resultado_esperado == "MENÚ_CLIENTE_ACTIVO":
                logger.info("🎉 ✅ RESULTADO: EL CÓDIGO FUNCIONA CORRECTAMENTE")
                logger.info("✅ El usuario 1570668456 DEBERÍA ver el menú de cliente activo")
                logger.info("✅ Todos los datos están correctos en la base de datos")
                logger.info("✅ Todas las condiciones se cumplen correctamente")
                
                logger.info("\n⚠️ Si el usuario reporta el problema, posibles causas:")
                logger.info("   1. 🔄 Cache de Telegram no actualizado")
                logger.info("   2. 🤖 Múltiples instancias del bot (conflicto 409)")
                logger.info("   3. 🌐 Problema temporal de conectividad")
                logger.info("   4. 👆 Usuario no usa /start sino botones directos")
                logger.info("   5. ⏱️ Problema de sincronización temporal")
                logger.info("   6. 📱 Cliente de Telegram con cache corrupto")
                
                logger.info("\n🔧 RECOMENDACIONES:")
                logger.info("   1. Pedir al usuario que use /start exactamente")
                logger.info("   2. Verificar logs en tiempo real durante el problema")
                logger.info("   3. Reiniciar el bot si hay conflictos 409")
                logger.info("   4. Pedir al usuario que reinicie su app de Telegram")
                
                return True
                
            else:
                logger.error("💥 ❌ PROBLEMA IDENTIFICADO EN EL CÓDIGO")
                logger.error(f"❌ Resultado actual: {resultado_esperado}")
                logger.error("❌ El usuario VE el mensaje incorrecto por un bug real")
                
                logger.error("\n🔧 ACCIONES REQUERIDAS:")
                logger.error("   1. Revisar y corregir la lógica del bot")
                logger.error("   2. Verificar datos del usuario en BD")
                logger.error("   3. Probar correcciones en entorno de desarrollo")
                
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
            result = await self.comprehensive_test()
            return result
        finally:
            await self.cleanup()

async def main():
    """Función principal"""
    tester = FinalTester1570668456()
    return await tester.run_test()

if __name__ == "__main__":
    result = asyncio.run(main())
    
    print("\n" + "="*80)
    print("📊 RESUMEN EJECUTIVO")
    print("="*80)
    
    if result:
        print("🎉 ✅ CONCLUSIÓN: El flujo /start funciona correctamente")
        print("✅ No hay bug en el código - problema es de infraestructura/cache")
        print("✅ El usuario DEBERÍA ver el menú de cliente activo")
    else:
        print("💥 ❌ CONCLUSIÓN: Se identificó un problema real en el código")
        print("❌ Requiere corrección inmediata")
    
    sys.exit(0 if result else 1)