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
    
    async def procesar_lote_wrapper(self):
        """
        Wrapper para ejecutar el proceso de lotes
        Maneja excepciones para que el scheduler no se detenga
        """
        try:
            logger.info("[Scheduler Tesorería] ========== INICIO CICLO ==========")
            logger.info(f"[Scheduler Tesorería] Hora: {datetime.now()}")
            
            from tesoreria_service import tesoreria_service
            resultado = await tesoreria_service.procesar_lote_tesoreria()
            
            if resultado:
                logger.info(f"[Scheduler Tesorería] Lote procesado: {resultado['id']}")
            else:
                logger.info("[Scheduler Tesorería] No hay solicitudes pendientes")
            
            logger.info("[Scheduler Tesorería] ========== FIN CICLO ==========")
            
        except Exception as e:
            logger.error(f"[Scheduler Tesorería] Error en ciclo: {str(e)}")
            import traceback
            logger.error(f"[Scheduler Tesorería] Traceback:\n{traceback.format_exc()}")
    
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
        
        logger.info("[Scheduler Tesorería] Iniciado - Ejecutará cada 15 minutos")
    
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
