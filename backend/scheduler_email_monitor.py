"""
Scheduler para Monitoreo de Emails de Tesorería - Fase 2

Este scheduler ejecuta periódicamente el servicio de monitoreo de emails
para detectar respuestas de Tesorería con comprobantes de dispersión.

Frecuencia recomendada: Cada 15 minutos (igual que el scheduler de recordatorios)
"""

import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from tesoreria_email_monitor_service import tesoreria_email_monitor

logger = logging.getLogger(__name__)


class EmailMonitorScheduler:
    """Scheduler para ejecutar el monitoreo de emails periódicamente"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.intervalo_minutos = 15  # Cada 15 minutos
        logger.info(f"[EmailMonitorScheduler] Inicializado - intervalo: {self.intervalo_minutos} minutos")
    
    async def job_monitorear_emails(self):
        """
        Job que se ejecuta periódicamente para monitorear emails
        """
        try:
            logger.info("[EmailMonitorScheduler] Ejecutando job de monitoreo de emails...")
            await tesoreria_email_monitor.procesar_respuestas_pendientes()
            logger.info("[EmailMonitorScheduler] Job completado")
        except Exception as e:
            logger.error(f"[EmailMonitorScheduler] Error en job: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    def start(self):
        """Inicia el scheduler"""
        try:
            # Agregar job para monitoreo de emails cada X minutos
            self.scheduler.add_job(
                self.job_monitorear_emails,
                'interval',
                minutes=self.intervalo_minutos,
                id='monitoreo_emails_tesoreria',
                replace_existing=True
            )
            
            self.scheduler.start()
            
            logger.info(f"[EmailMonitorScheduler] ✅ Iniciado - procesará cada {self.intervalo_minutos} minutos")
            logger.info(f"[EmailMonitorScheduler] Detecta respuestas de Tesorería y actualiza estados a 'dispersada_proveedor'")
            
        except Exception as e:
            logger.error(f"[EmailMonitorScheduler] ❌ Error iniciando scheduler: {str(e)}")
            raise
    
    def shutdown(self):
        """Detiene el scheduler"""
        try:
            self.scheduler.shutdown()
            logger.info("[EmailMonitorScheduler] Scheduler detenido")
        except Exception as e:
            logger.error(f"[EmailMonitorScheduler] Error deteniendo scheduler: {str(e)}")


# Instancia global del scheduler
email_monitor_scheduler = EmailMonitorScheduler()
