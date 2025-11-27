"""Servicio de notificaciones para Ana (Telegram + Email)"""
import os
import logging
import aiohttp
from typing import Dict, Any

logger = logging.getLogger(__name__)

ANA_TELEGRAM_CHAT_ID = os.getenv("ANA_TELEGRAM_CHAT_ID", "1720830607")
ANA_EMAIL = os.getenv("ANA_EMAIL", "gestion.ngdl@gmail.com")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


async def notificar_ana_telegram(operacion: Dict[str, Any]) -> bool:
    """
    Envía notificación a Ana por Telegram cuando una operación necesita clave MBControl.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN no configurado")
        return False
    
    try:
        folio = operacion.get("folio_mbco", "N/A")
        cliente = operacion.get("cliente_nombre", "N/A")
        monto_total = operacion.get("monto_total_comprobantes", 0)
        fecha = operacion.get("fecha_creacion", "N/A")
        operacion_id = operacion.get("id", "")
        
        # Calcular montos para mostrar
        comision = operacion.get("comision_cobrada", 0)
        capital = operacion.get("capital_netcash", 0)
        
        mensaje = f"🔔 **Nueva operación NetCash pendiente de clave MBco**\n\n"
        mensaje += f"🔑 **Clave NetCash:** `{folio}`\n"
        mensaje += f"👤 **Cliente:** {cliente}\n"
        mensaje += f"💵 **Total comprobantes:** ${monto_total:,.2f}\n"
        mensaje += f"💸 **Comisión:** ${comision:,.2f}\n"
        mensaje += f"🏦 **Capital NetCash:** ${capital:,.2f}\n"
        mensaje += f"📅 **Fecha:** {fecha[:10] if len(fecha) > 10 else fecha}\n"
        mensaje += f"🆔 **ID interno:** `{operacion_id}`\n\n"
        mensaje += "✏️ **Para registrar la clave MBco de esta operación:**\n"
        mensaje += "Usa el comando:\n"
        mensaje += f"`/mbco {folio} CLAVE_MBCO`\n\n"
        mensaje += "**Ejemplo:**\n"
        mensaje += f"`/mbco {folio} MBC-2025-00089`"
        
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": ANA_TELEGRAM_CHAT_ID,
                "text": mensaje,
                "parse_mode": "Markdown"
            }
            
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Notificación Telegram enviada a Ana para operación {folio}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Error enviando notificación Telegram a Ana: {error_text}")
                    return False
                    
    except Exception as e:
        logger.error(f"Error en notificar_ana_telegram: {str(e)}")
        return False


async def notificar_ana_email(operacion: Dict[str, Any], backend_url: str = "") -> bool:
    """
    Envía notificación a Ana por email cuando una operación necesita clave MBControl.
    
    NOTA: Requiere configuración SMTP en .env para funcionar.
    """
    # Por ahora solo logueamos, ya que requiere SMTP configurado
    folio = operacion.get("folio_mbco", "N/A")
    logger.info(f"[PENDIENTE SMTP] Notificación email a Ana para operación {folio}")
    logger.info(f"Destinatario: {ANA_EMAIL}")
    logger.info(f"Asunto: Nueva operación NetCash lista - {folio}")
    
    # TODO: Implementar envío real cuando SMTP esté configurado
    # Por ahora retorna False indicando que no se envió
    return False
