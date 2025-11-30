"""
Handlers de Telegram para Tesorería

Flujo:
1. Tesorería recibe notificación de orden interna pendiente
2. Tesorería revisa la orden y los comprobantes
3. Tesorería confirma envío de ligas a proveedor (próximo paso, no implementado)

Hook para futuro:
- Botón [Confirmar envío de ligas]
- Estado cambia a 'ligas_enviadas'
- Se notifica al siguiente paso del flujo
"""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram_config import TELEGRAM_ID_TESORERIA

logger = logging.getLogger(__name__)

class TelegramTesoreriaHandlers:
    """Handlers para el flujo de Tesorería"""
    
    def __init__(self, bot_app):
        self.bot = bot_app
    
    async def notificar_nueva_orden_interna(self, orden_interna: dict, usuario: dict):
        """
        Envía notificación a Tesorería sobre nueva orden interna pendiente
        
        Args:
            orden_interna: Dict con los datos de la orden interna
            usuario: Dict con datos del usuario (desde catálogo)
        """
        try:
            telegram_id = usuario.get("telegram_id")
            if not telegram_id:
                logger.warning(f"[Tesorería Telegram] Usuario {usuario.get('nombre')} no tiene telegram_id")
                return
            orden_id = orden_interna.get("id")
            folio_netcash = orden_interna.get("folio_netcash")
            folio_mbco = orden_interna.get("folio_mbco")
            beneficiario = orden_interna.get("beneficiario")
            idmex = orden_interna.get("idmex")
            num_ligas = orden_interna.get("num_ligas", 0)
            monto_total_ligas = orden_interna.get("monto_total_ligas", 0)
            monto_por_liga = orden_interna.get("monto_por_liga", 0)
            
            created_at = orden_interna.get("created_at")
            fecha_str = created_at.strftime("%d/%m/%Y %H:%M") if created_at else "N/A"
            
            num_comprobantes = len(orden_interna.get("comprobantes_adjuntos", []))
            
            # Construir mensaje
            mensaje = "📦 **Nueva orden interna de Tesorería**\n\n"
            mensaje += f"🆔 **Orden Interna:** {orden_id}\n"
            mensaje += f"📋 **Folio NetCash:** {folio_netcash}\n"
            mensaje += f"🏢 **Folio MBco:** {folio_mbco}\n"
            mensaje += f"👤 **Beneficiario:** {beneficiario}\n"
            mensaje += f"🆔 **IDMEX:** {idmex}\n\n"
            
            mensaje += "💰 **Detalle de pago:**\n"
            mensaje += f"  • Total a enviar: ${monto_total_ligas:,.2f}\n"
            mensaje += f"  • Número de ligas: {num_ligas}\n"
            mensaje += f"  • Monto por liga: ${monto_por_liga:,.2f}\n\n"
            
            mensaje += f"📎 **Comprobantes adjuntos:** {num_comprobantes}\n"
            mensaje += f"📅 **Fecha creación:** {fecha_str}\n\n"
            
            mensaje += "📧 **Revisa tu correo** para el layout completo y los comprobantes adjuntos.\n\n"
            mensaje += "ℹ️ Una vez que hayas enviado las ligas al proveedor, podrás confirmar el envío aquí."
            
            # Botones (preparar hooks para futuro)
            keyboard = [
                [InlineKeyboardButton("📋 Ver detalles", callback_data=f"tesor_ver_orden_{orden_id}")],
                # [InlineKeyboardButton("✅ Confirmar envío ligas", callback_data=f"tesor_confirmar_{orden_id}")],  # Futuro
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Enviar al usuario de Tesorería
            await self.bot.bot.send_message(
                chat_id=telegram_id,
                text=mensaje,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
            logger.info(f"[Tesorería Telegram] Notificación enviada para orden {orden_id}")
            
        except Exception as e:
            logger.error(f"[Tesorería Telegram] Error enviando notificación: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def ver_detalles_orden(self, update, context):
        """
        Handler cuando Tesorería presiona [Ver detalles]
        """
        query = update.callback_query
        await query.answer()
        
        # Extraer orden_id del callback_data
        orden_id = query.data.replace("tesor_ver_orden_", "")
        
        # TODO: Obtener orden de BD y mostrar detalles completos
        mensaje = f"📋 **Detalles de orden {orden_id}**\n\n"
        mensaje += "🔄 *Funcionalidad en desarrollo*\n\n"
        mensaje += "Mientras tanto, revisa tu correo para:\n"
        mensaje += "  • Layout completo de ligas\n"
        mensaje += "  • Comprobantes adjuntos\n"
        mensaje += "  • Instrucciones de envío"
        
        await query.edit_message_text(mensaje, parse_mode='Markdown')
    
    # ========== HOOKS PARA FUTURO (NO IMPLEMENTAR AÚN) ==========
    
    async def confirmar_envio_ligas(self, update, context):
        """
        HOOK PARA FUTURO: Handler cuando Tesorería confirma que envió ligas
        
        Flujo futuro:
        1. Tesorería confirma envío
        2. Sistema cambia estado a 'ligas_enviadas'
        3. Se notifica al siguiente paso (proveedor envía a cliente)
        """
        # TODO: Implementar en siguiente fase
        pass


# Instancia global (se inicializa desde telegram_bot.py)
telegram_tesoreria_handlers = None

def init_tesoreria_handlers(bot_app):
    """Inicializa los handlers de Tesorería"""
    global telegram_tesoreria_handlers
    telegram_tesoreria_handlers = TelegramTesoreriaHandlers(bot_app)
    return telegram_tesoreria_handlers
