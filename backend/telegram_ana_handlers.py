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
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from netcash_service import netcash_service
from motor.motor_asyncio import AsyncIOMotorClient

# P2: Servicio de aprendizaje
from netcash_pdf_learning_service import netcash_pdf_learning_service

logger = logging.getLogger(__name__)

# Conexión MongoDB
mongo_url = os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'netcash_mbco')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

# Estados del flujo de Ana
ANA_ESPERANDO_FOLIO_MBCO = 100
ANA_ESPERANDO_MOTIVO_RECHAZO = 101  # P1: Estado para capturar motivo de rechazo

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
            cliente_nombre = solicitud.get("cliente_nombre", "N/A")
            
            # ⭐ NUEVO P1: Detectar origen de datos (OCR vs Manual)
            modo_captura = solicitud.get("modo_captura", "ocr_ok")
            origen_montos = solicitud.get("origen_montos", "robot")
            validacion_ocr = solicitud.get("validacion_ocr", {})
            id_benef_frecuente = solicitud.get("id_beneficiario_frecuente")
            
            mensaje = "🧾 **Nueva solicitud NetCash lista para MBco**\n\n"
            mensaje += f"📋 **Folio NetCash:** {folio_mbco}\n"
            mensaje += f"🧑‍💼 **Cliente:** {cliente_nombre}\n"
            
            # ⭐ NUEVO P1: Indicador de origen de datos
            if modo_captura == "manual_por_fallo_ocr":
                mensaje += "\n⚠️ **CAPTURA MANUAL** - OCR no pudo leer comprobante\n"
                mensaje += f"📊 **Origen datos:** Manual (capturado por cliente)\n"
                
                # Mostrar motivo del fallo OCR
                if validacion_ocr.get("motivo_fallo"):
                    mensaje += f"❌ **Motivo fallo OCR:** {validacion_ocr.get('motivo_fallo')}\n"
                
                # Mostrar advertencias si existen
                if validacion_ocr.get("advertencias"):
                    advertencias = validacion_ocr.get("advertencias")
                    if isinstance(advertencias, list) and len(advertencias) > 0:
                        mensaje += f"⚠️ **Advertencias:** {', '.join(advertencias[:2])}\n"
                
                mensaje += "\n"
            else:
                mensaje += f"✅ **Origen datos:** Robot (OCR confiable)\n\n"
            
            mensaje += f"👤 **Beneficiario:** {beneficiario}\n"
            
            # ⭐ NUEVO P1: Indicar si es beneficiario frecuente
            if id_benef_frecuente:
                mensaje += f"🔁 **Beneficiario frecuente:** SÍ (id: {id_benef_frecuente})\n"
            else:
                mensaje += f"🆕 **Beneficiario frecuente:** NO (nuevo)\n"
            
            mensaje += f"🆔 **IDMEX:** {idmex}\n"
            mensaje += f"💰 **Total depósitos:** ${total_depositos:,.2f}\n"
            mensaje += f"📊 **Comisión NetCash (1%):** ${comision_netcash:,.2f}\n"
            mensaje += f"💸 **Monto a enviar (ligas):** ${monto_ligas:,.2f}\n"
            mensaje += f"🔗 **Número de ligas:** {num_ligas}\n"
            mensaje += f"📅 **Fecha creación:** {fecha_str}\n"
            
            # Botones
            keyboard = [
                [InlineKeyboardButton("✅ Validar y asignar folio MBco", callback_data=f"ana_asignar_folio_{solicitud_id}")],
                [InlineKeyboardButton("❌ Rechazar operación", callback_data=f"ana_rechazar_{solicitud_id}")],
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
        
        # Obtener datos de la solicitud para mostrar confirmación
        try:
            solicitud = await db.solicitudes_netcash.find_one(
                {'id': solicitud_id},
                {'_id': 0}
            )
            
            if not solicitud:
                await query.edit_message_text("❌ No se encontró la solicitud.")
                return ConversationHandler.END
            
            # Extraer datos clave
            folio_nc = solicitud.get('id', 'N/A')
            cliente = solicitud.get('cliente_nombre', 'N/A')
            beneficiario = solicitud.get('beneficiario_reportado', 'N/A')
            total_depositos = solicitud.get('total_comprobantes_validos', 0)
            
            # Solicitar folio con confirmación de la solicitud
            mensaje = "📝 **Asignación de folio MBco**\n\n"
            mensaje += "🎯 **Vas a asignar folio a esta solicitud:**\n\n"
            mensaje += f"📋 Folio NetCash: `{folio_nc}`\n"
            mensaje += f"👤 Cliente: {cliente}\n"
            mensaje += f"👥 Beneficiario: {beneficiario}\n"
            mensaje += f"💰 Total depósitos: ${total_depositos:,.2f}\n\n"
            mensaje += "───────────────────────\n\n"
            mensaje += "📝 **Escribe el folio MBco:**\n\n"
            mensaje += "**Formato:** #####-###-[D|S|R|M]-##\n"
            mensaje += "**Ejemplo:** `23456-209-M-11`\n\n"
            mensaje += "ℹ️ 5 dígitos – 3 dígitos – 1 letra (D, S, R o M) – 2 dígitos\n"
            mensaje += "ℹ️ El folio debe ser único."
            
            await query.edit_message_text(mensaje, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"[Ana] Error obteniendo solicitud: {str(e)}")
            await query.edit_message_text("❌ Error al cargar los datos de la solicitud.")
            return ConversationHandler.END
        
        return ANA_ESPERANDO_FOLIO_MBCO
    
    async def recibir_folio_mbco(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handler cuando Ana envía el folio MBco
        """
        folio_mbco = update.message.text.strip()
        solicitud_id = context.user_data.get('ana_solicitud_id_actual')
        
        if not solicitud_id:
            await update.message.reply_text("❌ No se encontró la solicitud. Por favor inicia el proceso de nuevo.")
            return ConversationHandler.END
        
        # Validación de formato: 4 o 5 dígitos iniciales (compatibilidad histórica)
        # Formato nuevo: ^\d{5}-\d{3}-[DSRM]-\d{2}$
        # Formato viejo: ^\d{4}-\d{3}-[DSRM]-\d{2}$
        import re
        patron_folio_nuevo = r'^\d{5}-\d{3}-[DSRM]-\d{2}$'
        patron_folio_viejo = r'^\d{4}-\d{3}-[DSRM]-\d{2}$'
        
        if not (re.match(patron_folio_nuevo, folio_mbco) or re.match(patron_folio_viejo, folio_mbco)):
            await update.message.reply_text(
                "❌ **El folio no tiene el formato correcto.**\n\n"
                "**Formato esperado:** #####-###-[D|S|R|M]-##\n"
                "**Ejemplo:** `23456-209-M-11`\n\n"
                "ℹ️ 5 dígitos – 3 dígitos – 1 letra (D, S, R o M) – 2 dígitos\n\n"
                "Por favor, escribe un folio válido:",
                parse_mode='Markdown'
            )
            return ANA_ESPERANDO_FOLIO_MBCO
        
        # Verificar que el folio no exista
        logger.info(f"[Ana] Validando unicidad del folio: {folio_mbco}")
        try:
            folio_existente = await netcash_service.verificar_folio_mbco_existe(folio_mbco)
            if folio_existente:
                logger.warning(f"[Ana] Folio {folio_mbco} ya está en uso")
                await update.message.reply_text(
                    f"❌ **Este folio MBco ya está asignado a otra solicitud.**\n\n"
                    f"Folio: `{folio_mbco}`\n\n"
                    "Por favor, ingresa un folio distinto:",
                    parse_mode='Markdown'
                )
                return ANA_ESPERANDO_FOLIO_MBCO
            
            logger.info(f"[Ana] Folio {folio_mbco} está disponible")
            
        except Exception as e:
            logger.error(f"[Ana] Error verificando folio: {str(e)}")
            import traceback
            traceback.print_exc()
            await update.message.reply_text("❌ No se pudo verificar el folio. Intenta de nuevo.")
            return ANA_ESPERANDO_FOLIO_MBCO
        
        # Asignar folio y generar orden interna
        logger.info(f"[ANA_FOLIO] Mensaje de folio recibido: {folio_mbco}")
        
        # Obtener información del usuario correctamente
        user = update.effective_user
        telegram_id = user.id if user else None
        username = user.username if user else None
        
        logger.info(f"[ANA_FOLIO] Usuario Telegram ID: {telegram_id}")
        logger.info(f"[Ana] Iniciando asignación de folio {folio_mbco} a solicitud {solicitud_id}")
        
        await update.message.reply_text("⏳ Asignando folio y generando orden interna...")
        
        try:
            # Llamar al servicio de dominio
            logger.info(f"[Ana] Llamando a asignar_folio_mbco_y_generar_orden_interna()")
            resultado = await netcash_service.asignar_folio_mbco_y_generar_orden_interna(
                solicitud_id=solicitud_id,
                folio_mbco=folio_mbco,
                usuario_asigna=username or str(telegram_id) if telegram_id else "unknown"
            )
            logger.info(f"[Ana] Resultado del servicio: success={resultado.get('success')}")
            
            if resultado.get("success"):
                solicitud = resultado.get("solicitud")
                
                # Mensaje de confirmación
                mensaje = "✅ **Folio MBco asignado correctamente.**\n\n"
                mensaje += f"📋 **Solicitud:** {solicitud.get('id')}\n"
                mensaje += f"🧾 **Folio MBco:** {folio_mbco}\n"
                mensaje += f"🧑‍💼 **Cliente:** {solicitud.get('cliente_nombre', 'N/A')}\n"
                mensaje += f"👤 **Beneficiario:** {solicitud.get('beneficiario_reportado')}\n"
                
                # Calcular total
                comprobantes = solicitud.get("comprobantes", [])
                total_depositos = sum(
                    c.get("monto_detectado", 0) 
                    for c in comprobantes 
                    if c.get("es_valido") and not c.get("es_duplicado")
                )
                mensaje += f"💰 **Total depósitos:** ${total_depositos:,.2f}\n\n"
                mensaje += "📦 **Se generó la orden interna para Tesorería.**"
                
                await update.message.reply_text(mensaje, parse_mode='Markdown')
                logger.info(f"[Ana] Folio {folio_mbco} asignado exitosamente a solicitud {solicitud_id}")
                
                # P2: Registrar en colección de aprendizaje si fue captura manual
                try:
                    if solicitud.get("modo_captura") == "manual_por_fallo_ocr":
                        logger.info(f"[Ana-P2] Registrando validación de captura manual en learning")
                        await netcash_pdf_learning_service.registrar_caso_aprendizaje(
                            solicitud=solicitud,
                            validado_por_ana=True,
                            estado_validacion_ana="aprobado"
                        )
                except Exception as e:
                    logger.warning(f"[Ana-P2] No se pudo registrar en learning: {str(e)}")
                
                # NUEVO: Procesar operación de tesorería inmediatamente
                try:
                    logger.info(f"[Ana] Iniciando proceso de tesorería para operación {solicitud_id}")
                    
                    # Mensaje a ANA (confirmación de que se está procesando)
                    await update.message.reply_text("⏳ Procesando orden interna para Tesorería...")
                    
                    from tesoreria_operacion_service import tesoreria_operacion_service
                    resultado_tesoreria = await tesoreria_operacion_service.procesar_operacion_tesoreria(solicitud_id)
                    
                    # Obtener chat_id de Tesorería
                    tesoreria_chat_id = os.getenv('TELEGRAM_TESORERIA_CHAT_ID')
                    logger.info(f"[Ana] TELEGRAM_TESORERIA_CHAT_ID configurado: {tesoreria_chat_id}")
                    
                    if resultado_tesoreria and resultado_tesoreria.get('success'):
                        # Mensaje a ANA (resumen simple)
                        folio_mbco = resultado_tesoreria.get('folio_mbco', 'N/A')
                        await update.message.reply_text(
                            "✅ **Orden procesada correctamente.**\n\n"
                            f"Folio MBco: **{folio_mbco}**\n\n"
                            "El layout fue generado y enviado a Tesorería."
                        )
                        
                        # ⚠️ P3: Notificación OBLIGATORIA a TESORERÍA por Telegram
                        # Esto SIEMPRE debe ejecutarse si la orden se procesó exitosamente
                        logger.info(f"[Tesorería-P3] Iniciando envío de notificación Telegram a Tesorería")
                        logger.info(f"[Tesorería-P3] Chat ID: {tesoreria_chat_id}, Folio MBco: {folio_mbco}, Solicitud ID: {solicitud_id}")
                        
                        try:
                            # Validar que tengamos un chat_id válido
                            if not tesoreria_chat_id or tesoreria_chat_id == "PENDIENTE_CONFIGURAR":
                                logger.error(f"[Tesorería-P3] ❌ TELEGRAM_TESORERIA_CHAT_ID no está configurado correctamente: '{tesoreria_chat_id}'")
                                logger.error(f"[Tesorería-P3] NO se puede enviar notificación a Tesorería")
                            else:
                                # Obtener datos de la solicitud para el mensaje
                                solicitud_data = await db.solicitudes_netcash.find_one(
                                    {'id': solicitud_id},
                                    {'_id': 0}
                                )
                                
                                if not solicitud_data:
                                    logger.error(f"[Tesorería-P3] ❌ No se encontró solicitud {solicitud_id} en BD para notificación")
                                else:
                                    # Extraer datos necesarios
                                    cliente_nombre = solicitud_data.get('cliente_nombre', 'N/A')
                                    beneficiario = solicitud_data.get('beneficiario_reportado', 'N/A')
                                    idmex = solicitud_data.get('idmex_reportado', 'N/A')
                                    total_depositos = solicitud_data.get('total_comprobantes_validos', 0)
                                    capital = solicitud_data.get('monto_ligas', 0)
                                    comision_dns = solicitud_data.get('comision_dns_calculada', 0)
                                    total_proveedor = capital + comision_dns
                                    
                                    # P3: Mensaje según especificación exacta del usuario
                                    mensaje_tesoreria = (
                                        "🆕 **Nueva orden interna NetCash lista para Tesorería**\n\n"
                                        f"📋 Folio NetCash: `{solicitud_id}`\n"
                                        f"📋 Folio MBco: `{folio_mbco}`\n"
                                        f"👤 Cliente: {cliente_nombre}\n"
                                        f"👥 Beneficiario: {beneficiario}\n"
                                        f"🆔 IDMEX: {idmex}\n"
                                        f"💰 Total depósitos detectados: ${total_depositos:,.2f}\n"
                                        f"💵 Monto a enviar en ligas: ${capital:,.2f}\n\n"
                                        f"📎 Comprobantes del cliente y layout fueron enviados por correo a Tesorería."
                                    )
                                    
                                    logger.info(f"[Tesorería-P3] Enviando mensaje a chat_id={tesoreria_chat_id}")
                                    logger.info(f"[Tesorería-P3] Contenido: Folio NetCash={solicitud_id}, Folio MBco={folio_mbco}, Cliente={cliente_nombre}")
                                    
                                    await context.bot.send_message(
                                        chat_id=tesoreria_chat_id,
                                        text=mensaje_tesoreria,
                                        parse_mode="Markdown"
                                    )
                                    
                                    logger.info(f"[Tesorería-P3] ✅ Notificación Telegram enviada exitosamente a {tesoreria_chat_id} para folio {folio_mbco}")
                                    
                        except Exception as e_tesoreria:
                            # Error al enviar notificación a Tesorería NO debe afectar el mensaje a Ana
                            logger.exception(f"[Tesorería-P3] ❌ Error al enviar notificación Telegram a Tesorería")
                            logger.error(f"[Tesorería-P3] Chat ID intentado: {tesoreria_chat_id}")
                            logger.error(f"[Tesorería-P3] Folio MBco: {folio_mbco}")
                            logger.error(f"[Tesorería-P3] Solicitud ID: {solicitud_id}")
                            logger.error(f"[Tesorería-P3] Detalle del error: {str(e_tesoreria)}")
                            logger.error(f"[Tesorería-P3] NOTA: El correo a Tesorería ya fue enviado correctamente. Este error solo afecta la notificación por Telegram.")
                        
                        logger.info(f"[Ana] ✅ Operación de tesorería procesada exitosamente")
                    else:
                        # Mensaje a ANA cuando NO se pudo procesar la orden
                        await update.message.reply_text(
                            "⚠️ **No se pudo enviar la orden a Tesorería.**\n\n"
                            "Intenta más tarde o contacta al área técnica."
                        )
                        
                        # Notificación a TESORERÍA sobre problema
                        if tesoreria_chat_id and tesoreria_chat_id != "PENDIENTE_CONFIGURAR":
                            folio_mbco = resultado_tesoreria.get('folio_mbco', 'N/A') if resultado_tesoreria else 'N/A'
                            mensaje_tesoreria_error = (
                                "⚠️ **Advertencia en orden interna**\n\n"
                                f"📋 Folio MBco: **{folio_mbco}**\n"
                                f"❌ Hubo un problema al generar o enviar el correo.\n\n"
                                f"Por favor, revisar manualmente."
                            )
                            
                            try:
                                await context.bot.send_message(
                                    chat_id=tesoreria_chat_id,
                                    text=mensaje_tesoreria_error,
                                    parse_mode="Markdown"
                                )
                            except Exception as e_notif:
                                logger.error(f"[Tesorería] Error enviando notificación: {str(e_notif)}")
                        
                        logger.warning(f"[Ana] ⚠️ Error procesando tesorería para {solicitud_id}")
                        
                except Exception as e:
                    logger.error(f"[Ana] Exception en proceso de tesorería: {str(e)}")
                    logger.error(f"[Ana] Tipo de error: {type(e).__name__}")
                    import traceback
                    logger.error(f"[Ana] Traceback completo:\n{traceback.format_exc()}")
                    
                    # Mensaje a ANA (sin detalles técnicos)
                    await update.message.reply_text(
                        "⚠️ **No se pudo enviar la orden a Tesorería.**\n\n"
                        "Intenta más tarde o contacta al área técnica."
                    )
                
            else:
                error = resultado.get("error", "Error desconocido")
                logger.error(f"[Ana] Error al asignar folio: {error}")
                await update.message.reply_text("❌ **No se pudo asignar el folio.**\n\nPor favor, intenta de nuevo o contacta a soporte técnico.")
            
        except Exception as e:
            logger.error(f"[Ana] Excepción asignando folio: {str(e)}")
            import traceback
            logger.error(f"[Ana] Traceback:\n{traceback.format_exc()}")
            await update.message.reply_text(
                "❌ **Error al asignar el folio.**\n\n"
                "Por favor, contacta a soporte técnico."
            )
        
        # Limpiar contexto
        context.user_data.pop('ana_solicitud_id_actual', None)
        
        return ConversationHandler.END
    
    async def cancelar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para cancelar el proceso"""
        await update.message.reply_text("❌ Proceso cancelado.")
        context.user_data.pop('ana_solicitud_id_actual', None)
        return ConversationHandler.END


    
    # ==================== P1: RECHAZAR OPERACIÓN ====================
    
    async def iniciar_rechazo_operacion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handler cuando Ana presiona [Rechazar operación]
        """
        query = update.callback_query
        await query.answer()
        
        telegram_id = query.from_user.id
        
        # Verificar permisos
        logger.info(f"[ANA_RECHAZO] Callback Rechazar desde chat_id={telegram_id}")
        
        from usuarios_repo import usuarios_repo
        usuario = await usuarios_repo.obtener_usuario_por_telegram_id(telegram_id)
        
        if not usuario or not usuario.get("activo"):
            await query.edit_message_text("❌ No tienes permisos para esta acción.")
            return ConversationHandler.END
        
        puede_asignar = usuario.get("permisos", {}).get("puede_asignar_folio_mbco", False)
        
        if not puede_asignar:
            await query.edit_message_text("❌ No tienes permisos para esta acción.")
            return ConversationHandler.END
        
        # Extraer solicitud_id del callback_data
        solicitud_id = query.data.replace("ana_rechazar_", "")
        
        # Guardar solicitud_id en contexto
        context.user_data['ana_solicitud_rechazar'] = solicitud_id
        
        logger.info(f"[ANA_RECHAZO] Iniciando rechazo de solicitud {solicitud_id}")
        
        # Pedir motivo del rechazo
        mensaje = "❌ **Rechazar operación**\n\n"
        mensaje += "Por favor escribe el **motivo del rechazo**.\n\n"
        mensaje += "Este mensaje se enviará al cliente.\n\n"
        mensaje += "**Ejemplos:**\n"
        mensaje += "• Comprobantes no válidos\n"
        mensaje += "• Montos no coinciden\n"
        mensaje += "• Beneficiario incorrecto\n"
        mensaje += "• Datos incompletos"
        
        await query.edit_message_text(mensaje, parse_mode="Markdown")
        
        return ANA_ESPERANDO_MOTIVO_RECHAZO
    
    async def recibir_motivo_rechazo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para recibir el motivo del rechazo"""
        solicitud_id = context.user_data.get('ana_solicitud_rechazar')
        
        if not solicitud_id:
            await update.message.reply_text("❌ Sesión expirada. Por favor intenta de nuevo.")
            return ConversationHandler.END
        
        motivo = update.message.text.strip()
        
        if not motivo or len(motivo) < 5:
            await update.message.reply_text(
                "❌ El motivo debe tener al menos 5 caracteres.\n\n"
                "Por favor escribe un motivo claro del rechazo.",
                parse_mode="Markdown"
            )
            return ANA_ESPERANDO_MOTIVO_RECHAZO
        
        try:
            # Obtener solicitud
            from netcash_service import netcash_service
            solicitud = await netcash_service.obtener_solicitud(solicitud_id)
            
            if not solicitud:
                await update.message.reply_text("❌ Error: Solicitud no encontrada.")
                return ConversationHandler.END
            
            # Actualizar estado a rechazada
            from motor.motor_asyncio import AsyncIOMotorClient
            import os
            from datetime import datetime, timezone
            
            mongo_url = os.getenv('MONGO_URL')
            db_name = os.getenv('DB_NAME', 'netcash_mbco')
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            
            await db.solicitudes_netcash.update_one(
                {"id": solicitud_id},
                {
                    "$set": {
                        "estado": "rechazada",
                        "motivo_rechazo": motivo,
                        "rechazada_por": update.effective_user.first_name,
                        "fecha_rechazo": datetime.now(timezone.utc),
                        "validado_por_ana": False
                    }
                }
            )
            
            logger.info(f"[ANA_RECHAZO] ✅ Solicitud {solicitud_id} rechazada. Motivo: {motivo}")
            
            # Notificar al cliente
            telegram_chat_id = solicitud.get("canal_metadata", {}).get("telegram_chat_id")
            
            if telegram_chat_id:
                try:
                    folio = solicitud.get("folio_mbco", solicitud_id)
                    mensaje_cliente = f"❌ **Operación NetCash rechazada**\n\n"
                    mensaje_cliente += f"📋 **Folio:** {folio}\n\n"
                    mensaje_cliente += f"**Motivo:** {motivo}\n\n"
                    mensaje_cliente += "Por favor contacta a tu ejecutivo para más información."
                    
                    await self.bot.app.bot.send_message(
                        chat_id=telegram_chat_id,
                        text=mensaje_cliente,
                        parse_mode="Markdown"
                    )
                    
                    logger.info(f"[ANA_RECHAZO] Cliente notificado en chat_id={telegram_chat_id}")
                except Exception as e:
                    logger.error(f"[ANA_RECHAZO] Error notificando al cliente: {str(e)}")
            
            # Confirmar a Ana
            mensaje_ana = f"✅ **Operación rechazada correctamente**\n\n"
            mensaje_ana += f"📋 **Solicitud:** {solicitud_id}\n"
            mensaje_ana += f"❌ **Motivo:** {motivo}\n\n"
            if telegram_chat_id:
                mensaje_ana += "El cliente ha sido notificado."
            else:
                mensaje_ana += "⚠️ No se pudo notificar al cliente (sin chat_id)."
            
            await update.message.reply_text(mensaje_ana, parse_mode="Markdown")
            
            # Limpiar contexto
            context.user_data.clear()
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"[ANA_RECHAZO] Error rechazando solicitud: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            await update.message.reply_text(
                "❌ Error al procesar el rechazo. Por favor intenta de nuevo."
            )
            return ConversationHandler.END


# Instancia global (se inicializa desde telegram_bot.py)
telegram_ana_handlers = None

def init_ana_handlers(bot_app):
    """Inicializa los handlers de Ana"""
    global telegram_ana_handlers
    telegram_ana_handlers = TelegramAnaHandlers(bot_app)
    return telegram_ana_handlers
