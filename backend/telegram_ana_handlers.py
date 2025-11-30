"""Handlers de Telegram para Ana (Administradora MBco)

Flujo:
1. Ana recibe notificación de solicitud lista para MBco
2. Ana presiona [Asignar folio MBco]
3. Ana escribe el folio MBco
4. Sistema valida y asigna el folio
5. Sistema genera orden interna para Tesorería
6. Sistema notifica a Tesorería
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from netcash_service import netcash_service

logger = logging.getLogger(__name__)

# Estados del flujo de Ana
ANA_ESPERANDO_FOLIO_MBCO = 100

class TelegramAnaHandlers:
    """Handlers para el flujo de Ana (admin MBco)"""
    
    def __init__(self, bot_app):
        self.bot = bot_app
    
    async def notificar_nueva_solicitud_para_mbco(self, solicitud: dict, usuario: dict):
        """
        Envía notificación a Ana cuando una solicitud queda lista para MBco
        
        Args:
            solicitud: Dict con los datos de la solicitud
            usuario: Dict con datos del usuario (desde catálogo)
        """
        try:
            folio_mbco = solicitud.get("folio_mbco", "N/A")
            telegram_id = usuario.get("telegram_id")
            
            logger.info(f"[Ana Telegram] Preparando notificación para {usuario.get('nombre')}")
            logger.info(f"[Ana Telegram] Folio: {folio_mbco} | Chat ID: {telegram_id}")
            
            if not telegram_id:
                logger.error(f"[Ana Telegram] ERROR: Usuario {usuario.get('nombre')} no tiene telegram_id")
                return
            
            solicitud_id = solicitud.get("id")
            cliente_id = solicitud.get("cliente_id")
            beneficiario = solicitud.get("beneficiario_reportado", "N/A")
            idmex = solicitud.get("idmex_reportado", "N/A")
            
            # Calcular totales
            comprobantes = solicitud.get("comprobantes", [])
            total_depositos = sum(
                c.get("monto_detectado", 0) 
                for c in comprobantes 
                if c.get("es_valido") and not c.get("es_duplicado")
            )
            
            comision_netcash = solicitud.get("comision_cliente", total_depositos * 0.01)
            monto_ligas = total_depositos - comision_netcash
            num_ligas = solicitud.get("cantidad_ligas_reportada", 0)
            
            created_at = solicitud.get("created_at")
            fecha_str = created_at.strftime("%d/%m/%Y %H:%M") if created_at else "N/A"
            
            # Construir mensaje
            mensaje = "🧾 **Nueva solicitud NetCash lista para MBco**\n\n"
            mensaje += f"📋 **Folio NetCash:** {folio_mbco}\n"
            mensaje += f"👤 **Cliente ID:** {cliente_id}\n"
            mensaje += f"🏢 **Beneficiario:** {beneficiario}\n"
            mensaje += f"🆔 **IDMEX:** {idmex}\n"
            mensaje += f"💰 **Total depósitos:** ${total_depositos:,.2f}\n"
            mensaje += f"📊 **Comisión NetCash (1%):** ${comision_netcash:,.2f}\n"
            mensaje += f"💸 **Monto a enviar (ligas):** ${monto_ligas:,.2f}\n"
            mensaje += f"🔗 **Número de ligas:** {num_ligas}\n"
            mensaje += f"📅 **Fecha creación:** {fecha_str}\n"
            
            # Botones
            keyboard = [
                [InlineKeyboardButton("📝 Asignar folio MBco", callback_data=f"ana_asignar_folio_{solicitud_id}")],
                [InlineKeyboardButton("🌐 Ver en la web", url=f"https://app.example.com/solicitud/{solicitud_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Enviar al usuario (Ana)
            logger.info(f"[Ana Telegram] Enviando mensaje a Telegram...")
            logger.info(f"[Ana Telegram] Chat ID: {telegram_id}")
            logger.info(f"[Ana Telegram] Folio: {folio_mbco}")
            
            await self.bot.app.bot.send_message(
                chat_id=telegram_id,
                text=mensaje,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
            logger.info(f"[Ana Telegram] ✅ Mensaje enviado exitosamente a chat_id={telegram_id}")
            logger.info(f"[Ana Telegram] Notificación completada para solicitud {folio_mbco}")
            
        except Exception as e:
            logger.error(f"[Ana Telegram] Error enviando notificación: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def iniciar_asignacion_folio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handler cuando Ana presiona [Asignar folio MBco]
        """
        query = update.callback_query
        await query.answer()
        
        telegram_id = query.from_user.id
        
        # Verificar permisos usando catálogo usuarios_netcash
        logger.info(f"[ANA_PERMISOS] Callback AsignarFolio desde chat_id={telegram_id}")
        
        from usuarios_repo import usuarios_repo
        usuario = await usuarios_repo.obtener_usuario_por_telegram_id(telegram_id)
        
        logger.info(f"[ANA_PERMISOS] Usuario encontrado en catálogo: {usuario.get('nombre') if usuario else None}")
        
        if not usuario:
            logger.warning(f"[ANA_PERMISOS] Acceso denegado: Usuario con telegram_id={telegram_id} NO encontrado en catálogo")
            await query.edit_message_text("❌ No tienes permisos para esta acción.")
            return ConversationHandler.END
        
        if not usuario.get("activo"):
            logger.warning(f"[ANA_PERMISOS] Acceso denegado: Usuario {usuario.get('nombre')} NO está activo")
            await query.edit_message_text("❌ No tienes permisos para esta acción.")
            return ConversationHandler.END
        
        puede_asignar = usuario.get("permisos", {}).get("puede_asignar_folio_mbco", False)
        logger.info(f"[ANA_PERMISOS] Permiso puede_asignar_folio_mbco={puede_asignar}")
        
        if not puede_asignar:
            logger.warning(f"[ANA_PERMISOS] Acceso denegado: Usuario {usuario.get('nombre')} NO tiene permiso 'puede_asignar_folio_mbco'")
            await query.edit_message_text("❌ No tienes permisos para esta acción.")
            return ConversationHandler.END
        
        logger.info(f"[ANA_PERMISOS] ✅ Acceso concedido a {usuario.get('nombre')} ({usuario.get('rol_negocio')})")
        
        # Extraer solicitud_id del callback_data
        solicitud_id = query.data.replace("ana_asignar_folio_", "")
        
        # Guardar en contexto
        context.user_data['ana_solicitud_id_actual'] = solicitud_id
        
        # Solicitar folio
        mensaje = "📝 **Asignación de folio MBco**\n\n"
        mensaje += "Por favor, escribe el folio de operación MBco para esta solicitud.\n\n"
        mensaje += "**Formato:** 4 dígitos – 3 dígitos – 1 letra (D, S, R o M) – 2 dígitos\n"
        mensaje += "**Ejemplo:** `1234-209-M-11`\n\n"
        mensaje += "ℹ️ El folio debe ser único y no estar asignado a otra solicitud."
        
        await query.edit_message_text(mensaje, parse_mode='Markdown')
        
        return ANA_ESPERANDO_FOLIO_MBCO
    
    async def recibir_folio_mbco(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handler cuando Ana envía el folio MBco
        """
        folio_mbco = update.message.text.strip()
        solicitud_id = context.user_data.get('ana_solicitud_id_actual')
        
        if not solicitud_id:
            await update.message.reply_text("❌ Error: No se encontró la solicitud. Por favor inicia el proceso de nuevo.")
            return ConversationHandler.END
        
        # Validaciones básicas
        if not folio_mbco or len(folio_mbco) < 3:
            await update.message.reply_text(
                "❌ El folio MBco no es válido. Debe tener al menos 3 caracteres.\n\n"
                "Por favor, escribe un folio válido (ejemplo: MB-2025-0007):"
            )
            return ANA_ESPERANDO_FOLIO_MBCO
        
        # Verificar que el folio no exista
        try:
            folio_existente = await netcash_service.verificar_folio_mbco_existe(folio_mbco)
            if folio_existente:
                await update.message.reply_text(
                    f"❌ El folio `{folio_mbco}` ya está asignado a otra solicitud.\n\n"
                    "Por favor, escribe un folio diferente:",
                    parse_mode='Markdown'
                )
                return ANA_ESPERANDO_FOLIO_MBCO
        except Exception as e:
            logger.error(f"[Ana] Error verificando folio: {str(e)}")
            await update.message.reply_text("❌ Error al verificar el folio. Intenta de nuevo.")
            return ANA_ESPERANDO_FOLIO_MBCO
        
        # Asignar folio y generar orden interna
        await update.message.reply_text("⏳ Asignando folio y generando orden interna...")
        
        try:
            # Llamar al servicio de dominio
            resultado = await netcash_service.asignar_folio_mbco_y_generar_orden_interna(
                solicitud_id=solicitud_id,
                folio_mbco=folio_mbco,
                usuario_asigna=update.from_user.username or str(update.from_user.id)
            )
            
            if resultado.get("success"):
                solicitud = resultado.get("solicitud")
                
                # Mensaje de confirmación
                mensaje = "✅ **Folio MBco registrado exitosamente**\n\n"
                mensaje += f"📋 **Folio NetCash:** {solicitud.get('folio_mbco')}\n"
                mensaje += f"🏢 **Folio MBco:** {folio_mbco}\n"
                mensaje += f"👤 **Beneficiario:** {solicitud.get('beneficiario_reportado')}\n"
                
                # Calcular total
                comprobantes = solicitud.get("comprobantes", [])
                total_depositos = sum(
                    c.get("monto_detectado", 0) 
                    for c in comprobantes 
                    if c.get("es_valido") and not c.get("es_duplicado")
                )
                mensaje += f"💰 **Total depósitos:** ${total_depositos:,.2f}\n\n"
                mensaje += "📦 La orden interna para Tesorería ha sido generada.\n"
                mensaje += "📧 Se envió correo a Tesorería con el layout y comprobantes.\n"
                mensaje += "📱 Tesorería fue notificada por Telegram."
                
                await update.message.reply_text(mensaje, parse_mode='Markdown')
                
            else:
                error = resultado.get("error", "Error desconocido")
                await update.message.reply_text(f"❌ Error al asignar folio: {error}")
            
        except Exception as e:
            logger.error(f"[Ana] Error asignando folio: {str(e)}")
            import traceback
            traceback.print_exc()
            await update.message.reply_text("❌ Error al asignar el folio. Contacta a soporte técnico.")
        
        # Limpiar contexto
        context.user_data.pop('ana_solicitud_id_actual', None)
        
        return ConversationHandler.END
    
    async def cancelar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para cancelar el proceso"""
        await update.message.reply_text("❌ Proceso cancelado.")
        context.user_data.pop('ana_solicitud_id_actual', None)
        return ConversationHandler.END


# Instancia global (se inicializa desde telegram_bot.py)
telegram_ana_handlers = None

def init_ana_handlers(bot_app):
    """Inicializa los handlers de Ana"""
    global telegram_ana_handlers
    telegram_ana_handlers = TelegramAnaHandlers(bot_app)
    return telegram_ana_handlers
