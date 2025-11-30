"""
Scheduler para procesos recurrentes de Tesorería

Ejecuta el proceso de lotes cada 15 minutos
"""

import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

logger = logging.getLogger(__name__)

class TesoreriaScheduler:
    """Scheduler para procesos de Tesorería"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        logger.info("[Scheduler Tesorería] Inicializado")
    
    async def enviar_recordatorio_pendientes(self):
        """
        Envía recordatorio de operaciones pendientes de dispersar
        (Solo recordatorio, NO genera nuevos layouts - eso lo hace Ana cuando asigna folio)
        """
        try:
            logger.info("[Scheduler Tesorería] ========== RECORDATORIO PENDIENTES ==========")
            logger.info(f"[Scheduler Tesorería] Hora: {datetime.now()}")
            
            from motor.motor_asyncio import AsyncIOMotorClient
            import os
            
            mongo_url = os.getenv('MONGO_URL')
            db_name = os.getenv('DB_NAME', 'netcash_mbco')
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            
            # Buscar operaciones en estado enviado_a_tesoreria sin comprobantes de dispersión
            pendientes = await db.solicitudes_netcash.find(
                {
                    'estado': 'enviado_a_tesoreria',
                    'comprobantes_dispersion': {'$exists': False}
                },
                {'_id': 0, 'id': 1, 'folio_mbco': 1, 'cliente_nombre': 1, 'total_comprobantes_validos': 1}
            ).to_list(100)
            
            client.close()
            
            if not pendientes:
                logger.info("[Scheduler Tesorería] ✅ No hay operaciones pendientes de dispersar")
                logger.info("[Scheduler Tesorería] ========== FIN RECORDATORIO ==========")
                return
            
            logger.info(f"[Scheduler Tesorería] 📋 Encontradas {len(pendientes)} operación(es) pendiente(s)")
            
            # Enviar recordatorio por Telegram
            await self._enviar_recordatorio_telegram(pendientes)
            
            logger.info("[Scheduler Tesorería] ========== FIN RECORDATORIO ==========")
            
        except Exception as e:
            logger.error(f"[Scheduler Tesorería] Error en recordatorio: {str(e)}")
            import traceback
            logger.error(f"[Scheduler Tesorería] Traceback:\n{traceback.format_exc()}")
    
    async def _enviar_recordatorio_telegram(self, pendientes: list):
        """Envía mensaje de recordatorio por Telegram a Tesorería"""
        try:
            from usuarios_repo import usuarios_repo
            import aiohttp
            import os
            
            # Obtener usuarios con permiso de alertas de tesorería
            usuarios = await usuarios_repo.obtener_usuarios_por_permiso('recibe_alertas_tesoreria', True)
            
            if not usuarios:
                logger.warning("[Scheduler Tesorería] No hay usuarios para recibir recordatorio")
                return
            
            # Construir mensaje
            mensaje = "📬 **Operaciones NetCash pendientes de dispersar**\n\n"
            mensaje += f"Estas {len(pendientes)} solicitud(es) ya tienen layout enviado a Tesorería, "
            mensaje += "pero aún no hemos recibido comprobantes de dispersión al proveedor:\n\n"
            
            for op in pendientes[:10]:  # Mostrar máximo 10
                folio = op.get('folio_mbco', 'N/A')
                cliente = op.get('cliente_nombre', 'N/A')[:25]
                monto = op.get('total_comprobantes_validos', 0)
                mensaje += f"• {folio} – {cliente} – ${monto:,.2f}\n"
            
            if len(pendientes) > 10:
                mensaje += f"• ... y {len(pendientes) - 10} más\n"
            
            mensaje += "\n📧 Revisa tu correo: en cada hilo tienes el layout CSV y los comprobantes del cliente.\n"
            mensaje += "Cuando termines la dispersión, responde a cada correo adjuntando los comprobantes de salida."
            
            # Enviar a cada usuario
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not bot_token:
                logger.error("[Scheduler Tesorería] TELEGRAM_BOT_TOKEN no configurado")
                return
            
            for usuario in usuarios:
                telegram_id = usuario.get('telegram_id')
                nombre = usuario.get('nombre', 'Usuario')
                
                if not telegram_id:
                    continue
                
                try:
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    payload = {
                        'chat_id': telegram_id,
                        'text': mensaje,
                        'parse_mode': 'Markdown'
                    }
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, json=payload) as response:
                            if response.status == 200:
                                logger.info(f"[Scheduler Tesorería] ✅ Recordatorio enviado a {nombre}")
                            else:
                                error_text = await response.text()
                                logger.error(f"[Scheduler Tesorería] ❌ Error enviando a {nombre}: {response.status}")
                                
                except Exception as e:
                    logger.error(f"[Scheduler Tesorería] Error notificando a {nombre}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"[Scheduler Tesorería] Error en recordatorio Telegram: {str(e)}")
    
    async def procesar_lote_wrapper(self):
        """
        DEPRECATED: Mantener por compatibilidad con código viejo
        Ahora solo llama al recordatorio de pendientes
        """
        await self.enviar_recordatorio_pendientes()
    
    def start(self):
        """Inicia el scheduler"""
        if self.is_running:
            logger.warning("[Scheduler Tesorería] Ya está corriendo")
            return
        
        # Agregar job cada 15 minutos
        self.scheduler.add_job(
            self.procesar_lote_wrapper,
            trigger=IntervalTrigger(minutes=15),
            id='proceso_lotes_tesoreria',
            name='Proceso de Lotes Tesorería',
            replace_existing=True
        )
        
        self.scheduler.start()
        self.is_running = True
        
        logger.info("[Scheduler Tesorería] Iniciado - Enviará recordatorios cada 15 minutos")
        logger.info("[Scheduler Tesorería] NOTA: Layouts se generan automáticamente cuando Ana asigna folio")
    
    def stop(self):
        """Detiene el scheduler"""
        if not self.is_running:
            return
        
        self.scheduler.shutdown()
        self.is_running = False
        
        logger.info("[Scheduler Tesorería] Detenido")
    
    async def ejecutar_ahora(self):
        """Ejecuta el proceso inmediatamente (útil para testing)"""
        logger.info("[Scheduler Tesorería] Ejecución manual solicitada")
        await self.procesar_lote_wrapper()


# Instancia global
scheduler_tesoreria = TesoreriaScheduler()
