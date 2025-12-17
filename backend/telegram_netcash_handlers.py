"""Handlers de Telegram para NetCash V1 - FLUJO REORDENADO

Este módulo contiene SOLO la interfaz conversacional de Telegram.
TODA la lógica de negocio vive en netcash_service.py.

NUEVO ORDEN DEL FLUJO:
1. Paso 1: Comprobantes (multi-file, fallar rápido)
2. Paso 2: Beneficiario + IDMEX (con frecuentes)
3. Paso 3: Ligas NetCash
4. Paso 4: Resumen y Confirmación

Filosofía:
- El bot pregunta y muestra
- El motor valida y decide
- Sin duplicar lógica de negocio
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from pathlib import Path
import aiohttp

from netcash_service import netcash_service
from netcash_models import SolicitudCreate, SolicitudUpdate, CanalOrigen, CanalMetadata
from cuenta_deposito_service import cuenta_deposito_service
from beneficiarios_frecuentes_service import beneficiarios_frecuentes_service

logger = logging.getLogger(__name__)

# Estados del flujo conversacional NetCash V1 - REORDENADO
NC_ESPERANDO_COMPROBANTE = 20  # Paso 1: Comprobantes
NC_ESPERANDO_BENEFICIARIO = 21  # Paso 2a: Beneficiario (o selección frecuente)
NC_ESPERANDO_IDMEX = 22  # Paso 2b: IDMEX (si no usó frecuente)
NC_ESPERANDO_LIGAS = 23  # Paso 3: Ligas
NC_ESPERANDO_CONFIRMACION = 24  # Paso 4: Confirmación

# Estados para captura manual por fallo OCR
NC_ESPERANDO_MONTO_MANUAL = 29  # Espera monto manual de un comprobante específico
NC_MANUAL_NUM_COMPROBANTES = 30  # Captura manual: Número de comprobantes
NC_MANUAL_MONTO_TOTAL = 31  # Captura manual: Monto total
NC_MANUAL_ELEGIR_BENEFICIARIO = 32  # Captura manual: Elegir beneficiario (frecuente o nuevo)
NC_MANUAL_CAPTURAR_BENEFICIARIO = 33  # Captura manual: Capturar nombre beneficiario nuevo
NC_MANUAL_CAPTURAR_IDMEX_BENEFICIARIO = 34  # Captura manual: Capturar IDMEX del beneficiario nuevo
NC_MANUAL_GUARDAR_FRECUENTE = 35  # Captura manual: Preguntar si guardar como frecuente
NC_MANUAL_NUM_LIGAS = 36  # Captura manual: Número de ligas


class TelegramNetCashHandlers:
    """Clase con todos los handlers para NetCash V1 en Telegram - FLUJO REORDENADO"""
    
    def __init__(self, bot_instance):
        """
        Args:
            bot_instance: Instancia del bot principal (para acceder a es_cliente_activo, etc.)
        """
        self.bot = bot_instance
    
    # ==================== MENÚ PRINCIPAL ====================
    
    async def mostrar_menu_netcash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Muestra el menú principal de NetCash para clientes activos.
        
        Este método debe ser llamado después de verificar que el usuario
        es un cliente activo.
        """
        user = update.effective_user if update.effective_user else update.callback_query.from_user
        
        mensaje = f"Hola {user.first_name} 👋\n\n"
        mensaje += "¿Qué necesitas hacer hoy?\n"
        
        keyboard = [
            [InlineKeyboardButton("🧾 Crear nueva operación NetCash", callback_data="nc_crear_operacion")],
            [InlineKeyboardButton("💳 Ver cuenta para depósitos", callback_data="nc_ver_cuenta")],
            [InlineKeyboardButton("📂 Ver mis solicitudes", callback_data="nc_ver_solicitudes")],
            [InlineKeyboardButton("❓ Ayuda", callback_data="ayuda")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(mensaje, reply_markup=reply_markup)
        else:
            await update.message.reply_text(mensaje, reply_markup=reply_markup)
    
    # ==================== VER CUENTA ====================
    
    async def ver_cuenta_depositos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra la cuenta concertadora activa para depósitos"""
        query = update.callback_query
        await query.answer()
        
        try:
            # Verificar que solo haya UNA cuenta concertadora activa
            from motor.motor_asyncio import AsyncIOMotorClient
            import os
            mongo_url = os.getenv('MONGO_URL')
            db_name = os.getenv('DB_NAME', 'netcash_mbco')
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            
            cuentas_activas = await db.config_cuentas_netcash.count_documents({
                "tipo": "concertadora",
                "activa": True
            })
            
            if cuentas_activas > 1:
                logger.error(f"[NC Telegram] Error: {cuentas_activas} cuentas concertadora activas (debe haber solo 1)")
                mensaje = "⚠️ **Error de configuración**\n\n"
                mensaje += "Por el momento no puedo mostrar la cuenta de depósito NetCash porque hay más de una cuenta activa configurada.\n\n"
                mensaje += "Por favor avísale a Ana para que lo revisen."
                
                keyboard = [[InlineKeyboardButton("⬅️ Volver al menú", callback_data="nc_menu_principal")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
                return
            
            # Obtener cuenta concertadora activa del motor
            cuenta = await cuenta_deposito_service.obtener_cuenta_activa()
            logger.info(f"[NC Telegram] cuenta_activa usada en ver_cuenta_depositos: {cuenta}")
            
            if not cuenta:
                logger.warning(f"[NC Telegram] No hay cuenta concertadora activa configurada")
                mensaje = "⚠️ No hay cuenta de depósito configurada.\n\n"
                mensaje += "Por favor contacta a tu ejecutivo para obtener los datos de pago."
            else:
                logger.info(f"[NC Telegram] Mostrando cuenta: {cuenta.get('banco')} / {cuenta.get('clabe')}")
                mensaje = "🏦 **Cuenta autorizada para tus depósitos NetCash:**\n\n"
                mensaje += f"**Banco:** {cuenta.get('banco')}\n"
                mensaje += f"**CLABE:** {cuenta.get('clabe')}\n"
                mensaje += f"**Beneficiario:** {cuenta.get('beneficiario')}\n\n"
                mensaje += "💡 Realiza tu depósito a esta cuenta y después envíame los comprobantes."
            
            # Botón para regresar al menú
            keyboard = [[InlineKeyboardButton("⬅️ Volver al menú", callback_data="nc_menu_principal")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"[NC Telegram] Error mostrando cuenta: {str(e)}")
            import traceback
            logger.error(f"[NC Telegram] Traceback: {traceback.format_exc()}")
            await query.edit_message_text(
                "❌ Error obteniendo información de la cuenta. Intenta de nuevo.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver al menú", callback_data="nc_menu_principal")
                ]])
            )
    
    # ==================== CREAR OPERACIÓN - PASO 1: COMPROBANTES ====================
    
    async def iniciar_crear_operacion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Inicia el flujo de crear operación NetCash.
        
        PASO 1: Crear solicitud en el motor y pedir comprobantes PRIMERO
        """
        query = update.callback_query
        await query.answer()
        
        chat_id = str(update.effective_chat.id)
        user = update.effective_user
        telegram_id = str(user.id)
        
        try:
            # Verificar que sea cliente activo
            es_activo, usuario, cliente = await self.bot.es_cliente_activo(telegram_id, chat_id)
            
            if not es_activo or not cliente:
                await query.edit_message_text(
                    "⚠️ Para crear una operación NetCash primero necesitas estar dado de alta como cliente activo.\n\n"
                    "Por favor contacta a Ana para completar tu registro."
                )
                return ConversationHandler.END
            
            # Crear solicitud en el motor (estado: borrador)
            solicitud_data = SolicitudCreate(
                canal=CanalOrigen.TELEGRAM,
                cliente_id=cliente.get("id"),
                cliente_nombre=cliente.get("nombre"),
                canal_metadata=CanalMetadata(
                    telegram_chat_id=chat_id,
                    telegram_message_id=str(query.message.message_id)
                )
            )
            
            solicitud = await netcash_service.crear_solicitud(solicitud_data)
            
            if not solicitud:
                raise Exception("No se pudo crear la solicitud en el motor")
            
            # Guardar solicitud_id en el contexto
            context.user_data['nc_solicitud_id'] = solicitud.get('id')
            context.user_data['nc_paso_actual'] = 'comprobantes'
            
            logger.info(f"[NC Telegram] Solicitud creada: {solicitud.get('id')} para cliente {cliente.get('id')}")
            
            # Verificar que solo haya UNA cuenta concertadora activa
            from motor.motor_asyncio import AsyncIOMotorClient
            import os
            mongo_url = os.getenv('MONGO_URL')
            db_name = os.getenv('DB_NAME', 'netcash_mbco')
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            
            cuentas_activas = await db.config_cuentas_netcash.count_documents({
                "tipo": "concertadora",
                "activa": True
            })
            
            if cuentas_activas > 1:
                logger.error(f"[NC Telegram] Error: {cuentas_activas} cuentas concertadora activas al crear operación")
                await query.edit_message_text(
                    "⚠️ **Error de configuración**\n\n"
                    "No puedo iniciar la operación porque hay más de una cuenta activa configurada.\n\n"
                    "Por favor avísale a Ana para que lo revisen.",
                    parse_mode="Markdown"
                )
                return ConversationHandler.END
            
            # Obtener y mostrar cuenta concertadora
            cuenta = await cuenta_deposito_service.obtener_cuenta_activa()
            
            mensaje = "✅ **Iniciemos tu operación NetCash**\n\n"
            
            if cuenta:
                logger.info(f"[NC Telegram] Mostrando cuenta al inicio: {cuenta.get('banco')} / {cuenta.get('clabe')}")
                mensaje += "🏦 **Cuenta para tu depósito:**\n"
                mensaje += f"• Banco: {cuenta.get('banco')}\n"
                mensaje += f"• CLABE: {cuenta.get('clabe')}\n"
                mensaje += f"• Beneficiario: {cuenta.get('beneficiario')}\n\n"
            else:
                logger.warning(f"[NC Telegram] No hay cuenta concertadora activa al crear operación")
            
            mensaje += "🧾 **Paso 1 de 3: Comprobantes de depósito**\n\n"
            mensaje += "Envíame uno o varios comprobantes de tus depósitos NetCash.\n"
            mensaje += "Puedes adjuntar:\n"
            mensaje += "• Varios archivos en un solo envío (álbum/selección múltiple)\n"
            mensaje += "• O enviarlos en mensajes separados, uno tras otro\n\n"
            mensaje += "Formatos aceptados:\n"
            mensaje += "• Archivo PDF\n"
            mensaje += "• Imagen (JPG, PNG)\n\n"
            mensaje += "⚠️ **Importante:** Los comprobantes deben corresponder a la cuenta NetCash autorizada mostrada arriba.\n\n"
            mensaje += "Cuando termines de subir todos tus comprobantes, pulsa **\"➡️ Continuar\"**."
            
            # Agregar botón de cancelar
            keyboard = [
                [InlineKeyboardButton("❌ Cancelar operación", callback_data="nc_cancelar_operacion_inicio")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
            
            return NC_ESPERANDO_COMPROBANTE
            
        except Exception as e:
            logger.error(f"[NC Telegram] Error iniciando operación: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            await query.edit_message_text(
                "❌ Error al iniciar la operación. Por favor intenta de nuevo más tarde."
            )
            return ConversationHandler.END
    
    async def cancelar_operacion_inicio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Cancela la operación recién iniciada y regresa al menú principal.
        Elimina el borrador si existe.
        """
        query = update.callback_query
        await query.answer()
        
        # Obtener solicitud_id si existe
        solicitud_id = context.user_data.get('nc_solicitud_id')
        
        try:
            if solicitud_id:
                # Eliminar el borrador de la BD
                from motor.motor_asyncio import AsyncIOMotorClient
                import os
                mongo_url = os.getenv('MONGO_URL')
                db_name = os.getenv('DB_NAME', 'netcash_mbco')
                client = AsyncIOMotorClient(mongo_url)
                db = client[db_name]
                
                result = await db.solicitudes_netcash.delete_one({"id": solicitud_id})
                if result.deleted_count > 0:
                    logger.info(f"[NC Telegram] Borrador {solicitud_id} eliminado por cancelación del usuario")
            
            # Limpiar datos del contexto
            context.user_data.pop('nc_solicitud_id', None)
            context.user_data.pop('nc_paso_actual', None)
            
            # Mostrar mensaje de cancelación y volver al menú
            mensaje = "✅ **Operación cancelada**\n\n"
            mensaje += "No se ha creado ninguna operación.\n"
            mensaje += "Puedes iniciar una nueva cuando lo desees."
            
            keyboard = [
                [InlineKeyboardButton("🏠 Volver al menú principal", callback_data="nc_menu_principal")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"[NC Telegram] Error cancelando operación: {str(e)}")
            await query.edit_message_text("❌ Error al cancelar. Intenta de nuevo.")
            return ConversationHandler.END
    
    async def solicitar_monto_comprobante(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handler para solicitar el monto manual de un comprobante específico.
        Se activa cuando el usuario presiona "Ingresar monto manual".
        """
        query = update.callback_query
        await query.answer()
        
        # Extraer solicitud_id e índice del callback_data: nc_editar_monto_{solicitud_id}_{idx}
        try:
            parts = query.data.replace("nc_editar_monto_", "").rsplit("_", 1)
            solicitud_id = parts[0]
            comp_idx = int(parts[1])
            
            # Guardar en contexto para el siguiente paso
            context.user_data['nc_solicitud_id'] = solicitud_id
            context.user_data['nc_comp_editar_idx'] = comp_idx
            
            logger.info(f"[NC Telegram] Solicitando monto manual para comprobante {comp_idx} de solicitud {solicitud_id}")
            
            mensaje = "📝 **Ingresa el monto del comprobante**\n\n"
            mensaje += "Escribe el monto total que aparece en el comprobante.\n\n"
            mensaje += "**Ejemplos:**\n"
            mensaje += "• 50000\n"
            mensaje += "• 125000.50\n"
            mensaje += "• 1000000\n\n"
            mensaje += "_Envía solo el número, sin símbolos ni comas._"
            
            await query.edit_message_text(mensaje, parse_mode="Markdown")
            
            # Cambiar al estado de esperar monto
            return NC_ESPERANDO_MONTO_MANUAL
            
        except Exception as e:
            logger.error(f"[NC Telegram] Error solicitando monto manual: {str(e)}")
            await query.edit_message_text("❌ Error. Por favor intenta de nuevo.")
            return NC_ESPERANDO_COMPROBANTE
    
    async def recibir_monto_comprobante_manual(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handler para recibir el monto manual de un comprobante específico.
        """
        solicitud_id = context.user_data.get('nc_solicitud_id')
        comp_idx = context.user_data.get('nc_comp_editar_idx')
        
        if not solicitud_id or comp_idx is None:
            await update.message.reply_text("❌ Sesión expirada. Inicia de nuevo con /start")
            return ConversationHandler.END
        
        try:
            # Validar que sea un número
            monto_str = update.message.text.strip().replace(',', '').replace('$', '')
            try:
                monto = float(monto_str)
            except ValueError:
                await update.message.reply_text(
                    "❌ Por favor envía solo el monto numérico.\n\n**Ejemplos:** 50000 o 125000.50",
                    parse_mode="Markdown"
                )
                return NC_ESPERANDO_MONTO_MANUAL
            
            # Validar que sea mayor a 0
            if monto <= 0:
                await update.message.reply_text(
                    "❌ El monto debe ser mayor a 0.\n\n**Ejemplo:** 50000",
                    parse_mode="Markdown"
                )
                return NC_ESPERANDO_MONTO_MANUAL
            
            # Actualizar el comprobante con el monto manual
            solicitud = await netcash_service.obtener_solicitud(solicitud_id)
            comprobantes = solicitud.get("comprobantes", [])
            
            if comp_idx >= len(comprobantes):
                await update.message.reply_text("❌ Error: Comprobante no encontrado.")
                return NC_ESPERANDO_COMPROBANTE
            
            # Actualizar el comprobante
            comprobantes[comp_idx]["monto"] = monto
            comprobantes[comp_idx]["monto_detectado"] = monto
            comprobantes[comp_idx]["es_valido"] = True  # Ahora es válido con monto manual
            comprobantes[comp_idx]["editado_manualmente"] = True
            comprobantes[comp_idx]["ocr_data"]["captura_manual_monto"] = True
            
            # Guardar en BD
            from motor.motor_asyncio import AsyncIOMotorClient
            import os
            client = AsyncIOMotorClient(os.environ.get('MONGO_URL'))
            db = client[os.environ.get('DB_NAME', 'netcash_mbco')]
            
            await db.solicitudes_netcash.update_one(
                {"id": solicitud_id},
                {"$set": {"comprobantes": comprobantes}}
            )
            
            logger.info(f"[NC Telegram] ✅ Monto manual guardado: ${monto:,.2f} para comprobante {comp_idx}")
            
            # Contar comprobantes válidos
            validos = [c for c in comprobantes if c.get("es_valido")]
            
            mensaje = f"✅ **Monto guardado: ${monto:,.2f}**\n\n"
            mensaje += f"Llevamos **{len(comprobantes)}** comprobante(s) ({len(validos)} válido(s)).\n\n"
            mensaje += "¿Quieres subir otro comprobante o continuar al siguiente paso?"
            
            keyboard = [
                [InlineKeyboardButton("➕ Agregar otro comprobante", callback_data=f"nc_mas_comprobantes_{solicitud_id}")],
                [InlineKeyboardButton("➡️ Continuar", callback_data=f"nc_continuar_paso1_{solicitud_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
            
            # Limpiar contexto de edición
            context.user_data.pop('nc_comp_editar_idx', None)
            
            return NC_ESPERANDO_COMPROBANTE
            
        except Exception as e:
            logger.error(f"[NC Telegram] Error guardando monto manual: {str(e)}")
            await update.message.reply_text("❌ Error al guardar. Por favor intenta de nuevo.")
            return NC_ESPERANDO_MONTO_MANUAL
    
    # ==================== PASO 1: RECIBIR COMPROBANTES ====================
    
    async def recibir_comprobante(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Recibe y procesa comprobante(s) - Paso 1
        
        REFORZADO: Try/catch robusto con logging detallado y manejo de errores específico
        """
        solicitud_id = context.user_data.get('nc_solicitud_id')
        
        if not solicitud_id:
            await update.message.reply_text("❌ Sesión expirada. Inicia de nuevo con /start")
            return ConversationHandler.END
        
        # Variables para logging detallado en caso de error
        telegram_user_id = None
        nombre_archivo = None
        file_path = None
        error_id = None
        
        try:
            # Obtener telegram_user_id para logging
            telegram_user_id = update.effective_user.id if update.effective_user else "UNKNOWN"
            
            logger.info(f"[RECIBIR_COMP] Iniciando para solicitud {solicitud_id}, telegram_user_id: {telegram_user_id}")
            # Determinar si es documento o foto
            if update.message.document:
                file = await update.message.document.get_file()
                nombre_archivo = update.message.document.file_name
            elif update.message.photo:
                file = await update.message.photo[-1].get_file()
                nombre_archivo = f"comprobante_{file.file_id}.jpg"
            else:
                await update.message.reply_text(
                    "❌ Por favor envía un archivo PDF o una imagen (JPG/PNG)."
                )
                return NC_ESPERANDO_COMPROBANTE
            
            # Descargar archivo
            upload_dir = Path("/app/backend/uploads/comprobantes_telegram")
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = upload_dir / f"{solicitud_id}_{nombre_archivo}"
            await file.download_to_drive(file_path)
            
            # Detectar si es un archivo ZIP
            es_zip = nombre_archivo.lower().endswith('.zip')
            
            if es_zip:
                # Procesar como archivo ZIP
                await update.message.reply_text("📦 Procesando archivo ZIP...")
                
                # Procesar el ZIP usando el servicio
                resultado_zip = await netcash_service.procesar_archivo_zip(
                    solicitud_id,
                    str(file_path),
                    nombre_archivo
                )
                
                # Construir mensaje de resultado
                total = resultado_zip.get("total_archivos", 0)
                validos = resultado_zip.get("validos", 0)
                invalidos = resultado_zip.get("invalidos", 0)
                sin_texto = resultado_zip.get("sin_texto_legible", 0)
                duplicados = resultado_zip.get("duplicados", 0)
                no_legibles = resultado_zip.get("no_legibles", 0)
                
                if total == 0:
                    mensaje = "⚠️ **El archivo ZIP está vacío o no contiene archivos.**\n\n"
                    mensaje += "Por favor, envía un ZIP con comprobantes (PDF/JPG/PNG)."
                elif validos == 0:
                    mensaje = "⚠️ **No se encontraron comprobantes válidos dentro del archivo ZIP.**\n\n"
                    mensaje += f"• {total} archivo(s) encontrado(s) dentro\n"
                    if sin_texto > 0:
                        mensaje += f"• {sin_texto} comprobante(s) sin texto legible (imagen escaneada) ⚠️\n"
                    if invalidos > 0:
                        mensaje += f"• {invalidos} comprobante(s) no coinciden con la cuenta NetCash activa\n"
                    if duplicados > 0:
                        mensaje += f"• {duplicados} comprobante(s) duplicado(s)\n"
                    if no_legibles > 0:
                        mensaje += f"• {no_legibles} archivo(s) no legible(s) o con formato no soportado\n"
                    
                    if sin_texto > 0:
                        mensaje += "\n⚠️ **Nota importante:** Los comprobantes deben ser documentos originales donde se pueda seleccionar el texto. "
                        mensaje += "Las capturas de pantalla o PDFs escaneados sin texto no son válidos.\n"
                    
                    mensaje += "\nAsegúrate de que el ZIP contenga PDFs o imágenes de comprobantes para la cuenta NetCash autorizada."
                else:
                    mensaje = f"✅ **Se procesó tu archivo ZIP.**\n\n"
                    mensaje += f"• {total} archivo(s) encontrado(s) dentro\n"
                    mensaje += f"• {validos} comprobante(s) válido(s) ✅\n"
                    if sin_texto > 0:
                        mensaje += f"• {sin_texto} comprobante(s) sin texto legible (no se incluyeron) ⚠️\n"
                    if invalidos > 0:
                        mensaje += f"• {invalidos} comprobante(s) inválido(s) (no se incluyeron)\n"
                    if duplicados > 0:
                        mensaje += f"• {duplicados} comprobante(s) duplicado(s) (no se incluyeron)\n"
                    if no_legibles > 0:
                        mensaje += f"• {no_legibles} archivo(s) no legible(s) o con formato no soportado (no se incluyeron)\n"
                
                # Obtener solicitud actualizada para mostrar total
                solicitud = await netcash_service.obtener_solicitud(solicitud_id)
                comprobantes = solicitud.get("comprobantes", [])
                
                # Calcular total de depósitos válidos
                total_depositos = 0.0
                for comp in comprobantes:
                    if comp.get("es_valido") and not comp.get("es_duplicado"):
                        monto = comp.get("monto_detectado")
                        if monto:
                            total_depositos += monto
                
                if validos > 0:
                    mensaje += f"\n💰 **Total de depósitos detectados hasta ahora: ${total_depositos:,.2f}**"
                
                await update.message.reply_text(mensaje, parse_mode='Markdown')
                
                # Para ZIPs, mostrar botones solo si hay comprobantes válidos
                if validos > 0:
                    # Mostrar botones de continuar/finalizar
                    keyboard = [
                        [
                            InlineKeyboardButton("📎 Subir otro", callback_data=f"nc_otro_{solicitud_id}"),
                            InlineKeyboardButton("✅ Continuar", callback_data=f"nc_continuar_{solicitud_id}")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    sent_msg = await update.message.reply_text(
                        "¿Quieres subir otro comprobante o continuar?",
                        reply_markup=reply_markup
                    )
                    context.user_data['nc_last_comprobante_message_id'] = sent_msg.message_id
                else:
                    # ZIP sin comprobantes válidos, permitir reintentar
                    keyboard = [
                        [InlineKeyboardButton("📎 Intentar otro archivo", callback_data=f"nc_otro_{solicitud_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(
                        "Puedes intentar con otro archivo:",
                        reply_markup=reply_markup
                    )
                
                return NC_ESPERANDO_COMPROBANTE
                
            else:
                # Procesar como comprobante individual (lógica existente)
                await update.message.reply_text("🔍 Procesando comprobante...")
                
                # Enviar al motor para agregar (retorna: agregado, razon)
                agregado, razon = await netcash_service.agregar_comprobante(
                    solicitud_id,
                    str(file_path),
                    nombre_archivo
                )
            
                # Obtener solicitud actualizada para contar comprobantes
                solicitud = await netcash_service.obtener_solicitud(solicitud_id)
                comprobantes = solicitud.get("comprobantes", [])
                num_comprobantes = len(comprobantes)
                
                # ⭐ MEJORADO: Si OCR no es confiable, permitir edición manual del monto específico
                # en lugar de interrumpir todo el flujo
                if razon == "requiere_captura_manual":
                    logger.warning(f"[NC Telegram] OCR NO confiable para comprobante {num_comprobantes - 1}")
                    
                    # Obtener el último comprobante (el que acaba de fallar OCR)
                    ultimo_comp = comprobantes[-1] if comprobantes else None
                    ocr_data = ultimo_comp.get("ocr_data", {}) if ultimo_comp else {}
                    advertencias = ocr_data.get("advertencias", [])
                    
                    mensaje = "⚠️ **Comprobante recibido pero no se pudo leer completamente**\n\n"
                    mensaje += f"📄 Archivo: {nombre_archivo}\n\n"
                    
                    if advertencias:
                        mensaje += "**Problema detectado:**\n"
                        for adv in advertencias[:2]:  # Mostrar máximo 2 advertencias
                            mensaje += f"• {adv}\n"
                        mensaje += "\n"
                    
                    mensaje += "**Opciones:**\n"
                    mensaje += "• 📝 Ingresa el monto manualmente\n"
                    mensaje += "• 📎 Sube otro comprobante diferente\n"
                    mensaje += "• ➡️ Continúa si tienes otros comprobantes válidos\n\n"
                    mensaje += f"Llevamos **{num_comprobantes}** comprobante(s) en total.\n"
                    
                    # Guardar índice del comprobante que necesita edición
                    context.user_data['nc_comp_editar_idx'] = num_comprobantes - 1
                    
                    # Botones con opción de editar monto
                    keyboard = [
                        [InlineKeyboardButton("📝 Ingresar monto manual", callback_data=f"nc_editar_monto_{solicitud_id}_{num_comprobantes - 1}")],
                        [InlineKeyboardButton("➕ Subir otro comprobante", callback_data=f"nc_mas_comprobantes_{solicitud_id}")],
                        [InlineKeyboardButton("➡️ Continuar sin este", callback_data=f"nc_continuar_paso1_{solicitud_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
                    return NC_ESPERANDO_COMPROBANTE
            
            # UX MEJORADA: Eliminar botones del mensaje anterior (si existe)
            last_message_id = context.user_data.get('nc_last_comprobante_message_id')
            if last_message_id:
                try:
                    # Quitar los botones del mensaje anterior
                    await self.bot.app.bot.edit_message_reply_markup(
                        chat_id=update.effective_chat.id,
                        message_id=last_message_id,
                        reply_markup=None
                    )
                except Exception as e:
                    # Si falla (mensaje muy antiguo o ya editado), continuar sin problema
                    logger.warning(f"[NC Telegram] No se pudo editar mensaje anterior: {str(e)}")
            
            # Mensaje de confirmación (diferenciar entre duplicado local, global y único)
            if razon and razon.startswith("duplicado_global:"):
                # Comprobante duplicado GLOBAL (en otra operación)
                folio_original = razon.split(":")[1]
                mensaje = "⚠️ **Comprobante ya utilizado anteriormente**\n\n"
                mensaje += f"Este comprobante ya fue utilizado en otra operación NetCash (folio **{folio_original}**).\n\n"
                mensaje += f"No lo vamos a contar de nuevo en el total de depósitos.\n\n"
                mensaje += f"Llevamos **{num_comprobantes}** archivo(s) en total.\n\n"
                mensaje += "¿Quieres subir otro comprobante o continuar?"
            elif razon == "duplicado_local":
                # Comprobante duplicado LOCAL (en esta operación)
                mensaje = "⚠️ **Comprobante duplicado detectado**\n\n"
                mensaje += f"Este archivo parece ser el mismo que otro que ya subiste en esta operación.\n"
                mensaje += f"No lo vamos a contar de nuevo en el total de depósitos.\n\n"
                mensaje += f"Llevamos **{num_comprobantes}** archivo(s) en total.\n\n"
                mensaje += "¿Quieres subir otro comprobante o continuar?"
            else:
                # Comprobante único (válido o inválido)
                # Verificar si es válido para mostrar el monto detectado
                ultimo_comp = comprobantes[-1] if comprobantes else None
                monto_det = ultimo_comp.get("monto_detectado") if ultimo_comp else None
                
                mensaje = f"✅ Comprobante recibido"
                if monto_det and monto_det > 0:
                    mensaje += f" - Monto: **${monto_det:,.2f}**"
                mensaje += f"\n"
                mensaje += f"Llevamos **{num_comprobantes}** comprobante(s) adjunto(s) a esta operación.\n\n"
                mensaje += "¿Quieres subir otro comprobante o continuar al siguiente paso?"
            
            # Botones inline
            keyboard = [
                [InlineKeyboardButton("➕ Agregar otro comprobante", callback_data=f"nc_mas_comprobantes_{solicitud_id}")],
                [InlineKeyboardButton("➡️ Continuar", callback_data=f"nc_continuar_paso1_{solicitud_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Enviar nuevo mensaje con botones
            sent_message = await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
            
            # Guardar el message_id del nuevo mensaje para la próxima vez
            context.user_data['nc_last_comprobante_message_id'] = sent_message.message_id
            
            # Mantener el estado en NC_ESPERANDO_COMPROBANTE
            return NC_ESPERANDO_COMPROBANTE
            
        except Exception as e:
            # MANEJO ROBUSTO DE ERRORES - Similar al P0 del botón "Continuar"
            from datetime import datetime
            import random
            import traceback
            
            # Generar ID único de error
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            random_suffix = random.randint(1000, 9999)
            error_id = f"ERR_COMP_{timestamp}_{random_suffix}"
            
            # LOG DETALLADO DEL ERROR
            logger.error(f"=" * 70)
            logger.error(f"[{error_id}] ERROR AL PROCESAR COMPROBANTE")
            logger.error(f"=" * 70)
            logger.error(f"[{error_id}] Solicitud ID: {solicitud_id}")
            logger.error(f"[{error_id}] Telegram User ID: {telegram_user_id}")
            logger.error(f"[{error_id}] Nombre archivo: {nombre_archivo}")
            logger.error(f"[{error_id}] Ruta archivo: {file_path}")
            logger.error(f"[{error_id}] Tipo de error: {type(e).__name__}")
            logger.error(f"[{error_id}] Mensaje de error: {str(e)}")
            logger.error(f"[{error_id}] Stack trace completo:")
            logger.error(traceback.format_exc())
            logger.error(f"=" * 70)
            
            # Marcar solicitud como requiere revisión manual
            try:
                from motor.motor_asyncio import AsyncIOMotorClient
                import os
                mongo_url = os.getenv('MONGO_URL')
                db_name = os.getenv('DB_NAME', 'netcash_mbco')
                client = AsyncIOMotorClient(mongo_url)
                db = client[db_name]
                
                await db.solicitudes_netcash.update_one(
                    {"id": solicitud_id},
                    {
                        "$set": {
                            "requiere_revision_manual": True,
                            "error_id": error_id,
                            "error_timestamp": datetime.now().isoformat(),
                            "error_detalle": {
                                "handler": "recibir_comprobante",
                                "tipo": type(e).__name__,
                                "mensaje": str(e),
                                "telegram_user_id": telegram_user_id,
                                "archivo": nombre_archivo
                            }
                        }
                    }
                )
                logger.info(f"[{error_id}] ✅ Solicitud marcada para revisión manual")
            except Exception as db_error:
                logger.error(f"[{error_id}] ❌ No se pudo marcar solicitud para revisión: {str(db_error)}")
            
            # MENSAJE ESPECÍFICO AL USUARIO según el tipo de error
            mensaje_error = ""
            
            # Identificar tipos de error comunes y dar mensajes específicos
            error_tipo = type(e).__name__
            error_mensaje = str(e).lower()
            
            if "pdf" in error_mensaje or "read" in error_mensaje or "corrupt" in error_mensaje:
                # Error de lectura del PDF
                mensaje_error = "⚠️ **No pudimos leer correctamente tu comprobante.**\n\n"
                mensaje_error += "Esto puede ocurrir si:\n"
                mensaje_error += "• El PDF está dañado o corrupto\n"
                mensaje_error += "• Es una imagen escaneada sin texto seleccionable\n"
                mensaje_error += "• El archivo no es un PDF válido\n\n"
                mensaje_error += "💡 **Solución:**\n"
                mensaje_error += "Por favor, intenta:\n"
                mensaje_error += "1. Exportar el comprobante nuevamente desde tu banca en línea\n"
                mensaje_error += "2. Tomar una captura de pantalla clara del comprobante\n"
                mensaje_error += "3. Asegurarte de que el archivo esté completo y se pueda abrir\n\n"
            elif "vault" in error_mensaje or "validador" in error_mensaje:
                # Error en el validador
                mensaje_error = "⚠️ **Tuvimos un problema al validar tu comprobante.**\n\n"
                mensaje_error += "El archivo se recibió correctamente, pero nuestro sistema de validación encontró un problema.\n\n"
                mensaje_error += "💡 **No te preocupes:**\n"
                mensaje_error += "• Tu comprobante SÍ está guardado\n"
                mensaje_error += "• Ana o un enlace de nuestro equipo lo revisará manualmente\n"
                mensaje_error += "• Te contactaremos para continuar con tu operación\n\n"
            else:
                # Error genérico pero con más info
                mensaje_error = "⚠️ **Tuvimos un problema técnico al procesar tu comprobante.**\n\n"
                mensaje_error += "✅ **Tu archivo SÍ se recibió** y está guardado de forma segura.\n\n"
                mensaje_error += "👤 Ana o un enlace de nuestro equipo revisará tu comprobante manualmente y te contactará pronto para continuar con tu operación.\n\n"
            
            mensaje_error += f"📋 **ID de seguimiento:** `{error_id}`\n\n"
            mensaje_error += "Por favor comparte este ID si contactas a soporte."
            
            try:
                await update.message.reply_text(mensaje_error, parse_mode="Markdown")
            except Exception as msg_error:
                logger.error(f"[{error_id}] No se pudo enviar mensaje de error al usuario: {str(msg_error)}")
                # Intentar sin markdown
                try:
                    await update.message.reply_text(
                        f"⚠️ Tuvimos un problema al procesar tu comprobante.\n\n"
                        f"Tu archivo está guardado y será revisado manualmente.\n\n"
                        f"ID de seguimiento: {error_id}"
                    )
                except:
                    pass
            
            return NC_ESPERANDO_COMPROBANTE
    
    async def agregar_otro_comprobante(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para el botón 'Agregar otro comprobante'"""
        query = update.callback_query
        await query.answer()
        
        mensaje = "Perfecto.\n\n"
        mensaje += "Tómate tu tiempo para buscar el siguiente comprobante y envíamelo cuando lo tengas listo.\n"
        mensaje += "No pasa nada si tardas unos minutos."
        
        # Eliminar los botones del mensaje actual al editarlo
        await query.edit_message_text(mensaje, parse_mode="Markdown")
        
        # Limpiar el message_id guardado ya que este mensaje ya no tiene botones
        context.user_data['nc_last_comprobante_message_id'] = None
        
        # Mantener en el estado NC_ESPERANDO_COMPROBANTE
        return NC_ESPERANDO_COMPROBANTE
    
    async def continuar_desde_paso1(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handler para el botón 'Continuar' desde Paso 1 (Comprobantes)
        
        REFORZADO P0: Try/catch global con logging detallado y manejo robusto de errores
        """
        query = update.callback_query
        await query.answer()
        
        # Extraer solicitud_id del callback_data
        solicitud_id = query.data.replace("nc_continuar_paso1_", "")
        
        # Variables para logging detallado en caso de error
        telegram_user_id = None
        comprobantes_nombres = []
        total_depositado = 0.0
        error_id = None
        
        try:
            # Obtener telegram_user_id para logging
            telegram_user_id = query.from_user.id if query.from_user else "UNKNOWN"
            
            logger.info(f"[CONTINUAR_P1] Iniciando para solicitud {solicitud_id}, telegram_user_id: {telegram_user_id}")
            
            # Verificar cuántos comprobantes tiene la solicitud
            solicitud = await netcash_service.obtener_solicitud(solicitud_id)
            comprobantes = solicitud.get("comprobantes", [])
            num_comprobantes = len(comprobantes)
            
            # Capturar nombres de archivos para logging
            comprobantes_nombres = [c.get("nombre_archivo", "SIN_NOMBRE") for c in comprobantes]
            logger.info(f"[CONTINUAR_P1] Comprobantes en solicitud: {comprobantes_nombres}")
            
            if num_comprobantes == 0:
                # No hay comprobantes - mostrar error y mantener en el mismo estado
                logger.warning(f"[CONTINUAR_P1] No hay comprobantes en solicitud {solicitud_id}")
                mensaje = "⚠️ Para continuar, debes adjuntar por lo menos un comprobante de depósito.\n\n"
                mensaje += "Por favor sube al menos uno."
                
                await query.edit_message_text(mensaje, parse_mode="Markdown")
                return NC_ESPERANDO_COMPROBANTE
            
            # Validar comprobantes antes de avanzar
            logger.info(f"[CONTINUAR_P1] Validando solicitud completa...")
            todas_validas, validaciones = await netcash_service.validar_solicitud_completa(solicitud_id)
            validacion_comprobante = validaciones.get("comprobante", {})
            
            # Contar comprobantes válidos y duplicados
            comprobantes_validos = [c for c in comprobantes if c.get("es_valido", False)]
            comprobantes_duplicados = [c for c in comprobantes if c.get("es_duplicado", False)]
            
            logger.info(f"[CONTINUAR_P1] Comprobantes válidos: {len(comprobantes_validos)}, duplicados: {len(comprobantes_duplicados)}")
            
            if len(comprobantes_validos) == 0:
                # NO hay comprobantes válidos - analizar razones para mensaje claro
                logger.warning(f"[CONTINUAR_P1] No hay comprobantes válidos en solicitud {solicitud_id}")
                razon = validacion_comprobante.get("razon", "Comprobantes no válidos")
                
                num_unicos = num_comprobantes - len(comprobantes_duplicados)
                
                # Contar comprobantes por tipo de error
                comprobantes_sin_texto = 0
                comprobantes_no_coinciden = 0
                
                for comp in comprobantes:
                    if comp.get("es_duplicado"):
                        continue  # Ya contados aparte
                    
                    detalle = comp.get("validacion_detalle", {})
                    razon_comp = detalle.get("razon", "")
                    
                    if razon_comp == "pdf_sin_texto_legible":
                        comprobantes_sin_texto += 1
                    elif not comp.get("es_valido"):
                        comprobantes_no_coinciden += 1
                
                # Construir mensaje según el tipo de error predominante
                mensaje = f"❌ **Se recibieron {num_comprobantes} comprobante(s)"
                if len(comprobantes_duplicados) > 0:
                    mensaje += f" ({len(comprobantes_duplicados)} duplicado(s))"
                mensaje += f", pero ninguno es válido.**\n\n"
                
                # Detalle específico según el tipo de error
                if comprobantes_sin_texto > 0:
                    mensaje += f"**Detalle:**\n"
                    mensaje += f"• {comprobantes_sin_texto} comprobante(s) sin texto legible (imagen escaneada o captura)\n"
                    if comprobantes_no_coinciden > 0:
                        mensaje += f"• {comprobantes_no_coinciden} comprobante(s) no coinciden con la cuenta NetCash autorizada\n"
                    mensaje += f"\n"
                    mensaje += f"⚠️ **Los comprobantes deben ser documentos originales** donde se pueda seleccionar el texto "
                    mensaje += f"(beneficiario y CLABE). Las capturas de pantalla o PDFs escaneados sin texto no son válidos.\n\n"
                elif comprobantes_no_coinciden > 0:
                    mensaje += f"**Detalle:** Ningún comprobante coincide con la cuenta NetCash autorizada.\n\n"
                else:
                    mensaje += f"**Detalle:** {razon}\n\n"
                
                # Obtener cuenta activa para mostrar
                cuenta = await cuenta_deposito_service.obtener_cuenta_activa()
                if cuenta:
                    mensaje += "**La cuenta NetCash autorizada es:**\n"
                    mensaje += f"• Banco: {cuenta.get('banco')}\n"
                    mensaje += f"• CLABE: {cuenta.get('clabe')}\n"
                    mensaje += f"• Beneficiario: {cuenta.get('beneficiario')}\n\n"
                
                mensaje += "Por favor envía comprobantes que correspondan a esta cuenta."
                
                await query.edit_message_text(mensaje, parse_mode="Markdown")
                return NC_ESPERANDO_COMPROBANTE
            
            # Hay al menos 1 comprobante válido - MOSTRAR RESUMEN INTERMEDIO
            # Calcular suma de montos de comprobantes válidos
            logger.info(f"[CONTINUAR_P1] Calculando total de depósitos...")
            total_depositado = 0.0
            resumen_comprobantes = []
            
            for comp in comprobantes_validos:
                monto = comp.get("monto_detectado")
                nombre = comp.get("nombre_archivo", "Sin nombre")
                if monto and monto > 0:
                    total_depositado += monto
                    resumen_comprobantes.append(f"  • {nombre}: ${monto:,.2f}")
                else:
                    resumen_comprobantes.append(f"  • {nombre}: (Monto no detectado)")
            
            # LOG ESPECÍFICO PARA MONTOS GRANDES (≥ 1,000,000)
            if total_depositado >= 1000000:
                logger.info(f"[DEBUG_CONTINUAR] ⚠️ Monto alto detectado: ${total_depositado:,.2f} en solicitud {solicitud_id}")
                logger.info(f"[DEBUG_CONTINUAR] Comprobantes con montos grandes: {comprobantes_nombres}")
            
            logger.info(f"[CONTINUAR_P1] Total depositado calculado: ${total_depositado:,.2f}")
            
            # Construir mensaje de resumen intermedio
            # IMPORTANTE: Usar HTML en lugar de Markdown para evitar problemas con $ y otros caracteres especiales
            mensaje_resumen = "✅ <b>Comprobantes validados correctamente</b>\n\n"
            mensaje_resumen += f"📊 <b>Resumen de depósitos detectados:</b>\n\n"
            
            if len(resumen_comprobantes) > 0:
                # Formatear comprobantes (sin markdown, solo texto plano)
                for comp_linea in resumen_comprobantes:
                    # Remover cualquier markdown del nombre de archivo
                    mensaje_resumen += comp_linea + "\n"
                
                # Escapar el símbolo $ para HTML (aunque en HTML no es necesario, lo hacemos por consistencia)
                mensaje_resumen += f"\n💰 <b>Total de depósitos detectados:</b> ${total_depositado:,.2f}\n"
                
                # Mostrar información de duplicados si hay (diferenciar locales vs globales)
                if len(comprobantes_duplicados) > 0:
                    duplicados_locales = [c for c in comprobantes_duplicados if c.get("tipo_duplicado") == "local"]
                    duplicados_globales = [c for c in comprobantes_duplicados if c.get("tipo_duplicado") == "global"]
                    
                    mensaje_resumen += f"\n⚠️ <b>Nota:</b>"
                    if len(duplicados_locales) > 0:
                        mensaje_resumen += f" {len(duplicados_locales)} comprobante(s) duplicado(s) en esta operación"
                    if len(duplicados_globales) > 0:
                        if len(duplicados_locales) > 0:
                            mensaje_resumen += " y"
                        mensaje_resumen += f" {len(duplicados_globales)} ya utilizado(s) en otras operaciones NetCash"
                    mensaje_resumen += " no se incluyeron en el total.\n"
                
                mensaje_resumen += "\n"
            else:
                mensaje_resumen += "No se pudo detectar monto en los comprobantes.\n\n"
            
            mensaje_resumen += "Continuaremos con el siguiente paso..."
            
            logger.info(f"[CONTINUAR_P1] Mostrando resumen al usuario...")
            await query.edit_message_text(mensaje_resumen, parse_mode="HTML")
            
            # Pequeña pausa para que el usuario vea el resumen
            import asyncio
            await asyncio.sleep(2)
            
            # Mostrar Paso 2: Beneficiarios frecuentes
            logger.info(f"[CONTINUAR_P1] Avanzando al Paso 2 (beneficiarios)...")
            await self._mostrar_paso2_beneficiarios(query, context, solicitud_id)
            
            logger.info(f"[CONTINUAR_P1] ✅ Proceso completado exitosamente para solicitud {solicitud_id}")
            return NC_ESPERANDO_BENEFICIARIO
            
        except Exception as e:
            # MANEJO ROBUSTO DE ERRORES P0
            from datetime import datetime
            import random
            import traceback
            
            # Generar ID único de error
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            random_suffix = random.randint(1000, 9999)
            error_id = f"ERR_CONTINUAR_{timestamp}_{random_suffix}"
            
            # LOG DETALLADO DEL ERROR
            logger.error(f"=" * 70)
            logger.error(f"[{error_id}] ERROR EN BOTÓN CONTINUAR")
            logger.error(f"=" * 70)
            logger.error(f"[{error_id}] Solicitud ID: {solicitud_id}")
            logger.error(f"[{error_id}] Telegram User ID: {telegram_user_id}")
            logger.error(f"[{error_id}] Comprobantes: {comprobantes_nombres}")
            logger.error(f"[{error_id}] Total depositado calculado: ${total_depositado:,.2f}")
            logger.error(f"[{error_id}] Tipo de error: {type(e).__name__}")
            logger.error(f"[{error_id}] Mensaje de error: {str(e)}")
            logger.error(f"[{error_id}] Stack trace completo:")
            logger.error(traceback.format_exc())
            logger.error(f"=" * 70)
            
            # Marcar solicitud como requiere revisión manual (sin perder avance)
            try:
                from motor.motor_asyncio import AsyncIOMotorClient
                import os
                mongo_url = os.getenv('MONGO_URL')
                db_name = os.getenv('DB_NAME', 'netcash_mbco')
                client = AsyncIOMotorClient(mongo_url)
                db = client[db_name]
                
                await db.solicitudes_netcash.update_one(
                    {"id": solicitud_id},
                    {
                        "$set": {
                            "requiere_revision_manual": True,
                            "error_id": error_id,
                            "error_timestamp": datetime.now().isoformat(),
                            "error_detalle": {
                                "handler": "continuar_desde_paso1",
                                "tipo": type(e).__name__,
                                "mensaje": str(e),
                                "telegram_user_id": telegram_user_id
                            }
                        }
                    }
                )
                logger.info(f"[{error_id}] ✅ Solicitud marcada para revisión manual")
            except Exception as db_error:
                logger.error(f"[{error_id}] ❌ No se pudo marcar solicitud para revisión: {str(db_error)}")
            
            # MENSAJE CLARO Y ÚTIL AL CLIENTE (HTML para evitar errores de parsing)
            mensaje_error = "❌ <b>Tuvimos un problema interno al continuar con tu solicitud.</b>\n\n"
            mensaje_error += "✅ <b>Tus comprobantes SÍ se guardaron</b> y están a salvo.\n\n"
            mensaje_error += "👤 Ana o un enlace de nuestro equipo te contactarán pronto para ayudarte a continuar con tu operación.\n\n"
            mensaje_error += f"📋 <b>ID de seguimiento:</b> <code>{error_id}</code>\n\n"
            mensaje_error += "Por favor comparte este ID si contactas a soporte."
            
            try:
                await query.edit_message_text(mensaje_error, parse_mode="HTML")
            except Exception as msg_error:
                logger.error(f"[{error_id}] No se pudo enviar mensaje de error al usuario: {str(msg_error)}")
                # Fallback: intentar sin formato si HTML también falla
                try:
                    mensaje_simple = f"⚠️ Tuvimos un problema al continuar.\n\nTus comprobantes están guardados.\n\nID: {error_id}"
                    await query.edit_message_text(mensaje_simple)
                except:
                    pass
            
            return NC_ESPERANDO_COMPROBANTE
    
    # ==================== PASO 2: BENEFICIARIO + IDMEX (CON FRECUENTES) ====================
    
    async def _mostrar_paso2_beneficiarios(self, query, context, solicitud_id):
        """Muestra el Paso 2: Beneficiarios frecuentes o captura manual"""
        try:
            # Obtener cliente_id de la solicitud
            solicitud = await netcash_service.obtener_solicitud(solicitud_id)
            cliente_id = solicitud.get("cliente_id")
            
            # Consultar beneficiarios frecuentes (últimas 5 solicitudes exitosas)
            from motor.motor_asyncio import AsyncIOMotorClient
            import os
            mongo_url = os.getenv('MONGO_URL')
            db_name = os.getenv('DB_NAME', 'netcash_mbco')
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            
            # Buscar beneficiarios en operaciones válidas (no rechazadas ni canceladas)
            estados_validos = ["lista_para_mbc", "en_proceso_mbc", "completada", "enviado_a_tesoreria", "orden_interna_generada"]
            
            solicitudes_historicas = await db.solicitudes_netcash.find(
                {
                    "cliente_id": cliente_id,
                    "estado": {"$in": estados_validos},
                    "beneficiario_reportado": {"$exists": True, "$ne": None, "$ne": ""},
                    "idmex_reportado": {"$exists": True, "$ne": None, "$ne": ""}
                },
                {"_id": 0, "beneficiario_reportado": 1, "idmex_reportado": 1, "created_at": 1}
            ).sort("created_at", -1).limit(20).to_list(20)  # Buscar más para asegurar variedad
            
            # Deduplicar beneficiarios (mismo beneficiario + idmex) manteniendo orden cronológico
            beneficiarios_frecuentes = {}
            for sol in solicitudes_historicas:
                benef = sol.get("beneficiario_reportado")
                idmex = sol.get("idmex_reportado")
                
                # Validar que tenga valores válidos
                if not benef or not idmex:
                    continue
                
                key = f"{benef}_{idmex}"
                if key not in beneficiarios_frecuentes:
                    beneficiarios_frecuentes[key] = {
                        "beneficiario": benef,
                        "idmex": idmex,
                        "created_at": sol.get("created_at")
                    }
            
            # Tomar los 3 más recientes únicos
            frecuentes_list = list(beneficiarios_frecuentes.values())
            # Ordenar por fecha más reciente
            frecuentes_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            # Tomar hasta 3
            frecuentes = frecuentes_list[:3]
            
            logger.info(f"[NC Telegram] Beneficiarios frecuentes encontrados: {len(frecuentes)}")
            for idx, freq in enumerate(frecuentes, 1):
                logger.info(f"  {idx}. {freq['beneficiario']} - IDMEX: {freq['idmex']}")
            
            mensaje = "👤 <b>Paso 2 de 3: Beneficiario + IDMEX</b>\n\n"
            
            if frecuentes:
                mensaje += "🔁 <b>Beneficiarios frecuentes:</b>\n\n"
                for idx, freq in enumerate(frecuentes, 1):
                    mensaje += f"{idx}. {freq['beneficiario']} – IDMEX: {freq['idmex']}\n"
                
                mensaje += "\nPuedes elegir uno de la lista o escribir un beneficiario nuevo.\n"
                mensaje += "Si prefieres escribir uno nuevo, simplemente envía el nombre completo del beneficiario."
                
                # Botones para beneficiarios frecuentes
                keyboard = []
                for freq in frecuentes:
                    button_text = f"{freq['beneficiario'][:30]}... (IDMEX {freq['idmex']})"
                    callback_data = f"nc_benef_freq_{freq['idmex']}"
                    # Guardar en contexto para recuperar después
                    context.user_data[f"benef_freq_{freq['idmex']}"] = freq
                    keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(mensaje, parse_mode="HTML", reply_markup=reply_markup)
            else:
                # No hay frecuentes - captura manual directa
                mensaje += "Por favor envíame el <b>nombre completo del beneficiario</b>.\n\n"
                mensaje += "El nombre debe tener:\n"
                mensaje += "• Mínimo 3 palabras (nombre + dos apellidos)\n"
                mensaje += "• Sin números\n\n"
                mensaje += "<b>Ejemplo:</b> ANDRÉS MANUEL LÓPEZ OBRADOR"
                
                await query.edit_message_text(mensaje, parse_mode="HTML")
        
        except Exception as e:
            logger.error(f"[NC Telegram] Error mostrando paso 2: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def seleccionar_beneficiario_frecuente(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler cuando el usuario selecciona un beneficiario frecuente"""
        query = update.callback_query
        await query.answer()
        
        # Extraer IDMEX del callback_data
        idmex = query.data.replace("nc_benef_freq_", "")
        
        # Recuperar datos del contexto
        benef_data = context.user_data.get(f"benef_freq_{idmex}")
        
        if not benef_data:
            await query.edit_message_text("❌ Error recuperando datos. Por favor intenta de nuevo.")
            return NC_ESPERANDO_BENEFICIARIO
        
        solicitud_id = context.user_data.get('nc_solicitud_id')
        
        try:
            # Actualizar solicitud con beneficiario + IDMEX
            await netcash_service.actualizar_solicitud(
                solicitud_id,
                SolicitudUpdate(
                    beneficiario_reportado=benef_data['beneficiario'],
                    idmex_reportado=benef_data['idmex']
                )
            )
            
            # Mensaje de confirmación
            mensaje = f"✅ **Usaremos:**\n\n"
            mensaje += f"• Beneficiario: {benef_data['beneficiario']}\n"
            mensaje += f"• IDMEX: {benef_data['idmex']}\n\n"
            mensaje += "Pasando al siguiente paso..."
            
            await query.edit_message_text(mensaje, parse_mode="Markdown")
            
            # Pasar directamente al Paso 3 (Ligas)
            await self._mostrar_paso3_ligas(query, context, solicitud_id)
            
            return NC_ESPERANDO_LIGAS
            
        except Exception as e:
            logger.error(f"[NC Telegram] Error seleccionando beneficiario frecuente: {str(e)}")
            await query.edit_message_text("❌ Error procesando tu selección. Intenta de nuevo.")
            return NC_ESPERANDO_BENEFICIARIO
    
    async def recibir_beneficiario(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Recibe y valida el nombre del beneficiario - Paso 2a"""
        beneficiario = update.message.text.strip().upper()
        solicitud_id = context.user_data.get('nc_solicitud_id')
        
        if not solicitud_id:
            await update.message.reply_text(
                "❌ Sesión expirada. Por favor inicia de nuevo con /start"
            )
            return ConversationHandler.END
        
        try:
            # Actualizar solicitud en el motor
            await netcash_service.actualizar_solicitud(
                solicitud_id,
                SolicitudUpdate(beneficiario_reportado=beneficiario)
            )
            
            # Validar solo este campo con el motor
            todas_validas, validaciones = await netcash_service.validar_solicitud_completa(solicitud_id)
            validacion_beneficiario = validaciones.get("beneficiario", {})
            
            if not validacion_beneficiario.get("valido"):
                # No válido - explicar error y pedir de nuevo
                razon = validacion_beneficiario.get("razon", "Formato incorrecto")
                mensaje = f"❌ **{razon}**\n\n"
                mensaje += "Por favor envíame el nombre correcto.\n"
                mensaje += "Recuerda: mínimo 3 palabras (nombre + dos apellidos), sin números.\n\n"
                mensaje += "**Ejemplo:** ANDRÉS MANUEL LÓPEZ OBRADOR"
                
                await update.message.reply_text(mensaje, parse_mode="Markdown")
                return NC_ESPERANDO_BENEFICIARIO
            
            # Válido - pasar al Paso 2b (IDMEX)
            context.user_data['nc_paso_actual'] = 'idmex'
            
            mensaje = f"✅ Beneficiario registrado: **{beneficiario}**\n\n"
            mensaje += "📝 **Paso 2b: IDMEX**\n\n"
            mensaje += "Ahora envíame el **IDMEX del beneficiario** (10 dígitos).\n\n"
            mensaje += "**Ejemplo:** 1234567890"
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
            return NC_ESPERANDO_IDMEX
            
        except Exception as e:
            logger.error(f"[NC Telegram] Error procesando beneficiario: {str(e)}")
            await update.message.reply_text(
                "❌ Error procesando tu información. Por favor intenta de nuevo."
            )
            return NC_ESPERANDO_BENEFICIARIO
    
    async def recibir_idmex(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Recibe y valida el IDMEX - Paso 2b"""
        idmex = update.message.text.strip()
        solicitud_id = context.user_data.get('nc_solicitud_id')
        
        if not solicitud_id:
            await update.message.reply_text("❌ Sesión expirada. Inicia de nuevo con /start")
            return ConversationHandler.END
        
        try:
            # Actualizar en el motor
            await netcash_service.actualizar_solicitud(
                solicitud_id,
                SolicitudUpdate(idmex_reportado=idmex)
            )
            
            # Validar
            todas_validas, validaciones = await netcash_service.validar_solicitud_completa(solicitud_id)
            validacion_idmex = validaciones.get("idmex", {})
            
            if not validacion_idmex.get("valido"):
                razon = validacion_idmex.get("razon", "Formato incorrecto")
                mensaje = f"❌ **{razon}**\n\n"
                mensaje += "Por favor envíame el IDMEX correcto (10 dígitos).\n\n"
                mensaje += "**Ejemplo:** 1234567890"
                
                await update.message.reply_text(mensaje, parse_mode="Markdown")
                return NC_ESPERANDO_IDMEX
            
            # Válido - pasar al Paso 3 (Ligas)
            mensaje = f"✅ IDMEX registrado: **{idmex}**\n\n"
            mensaje += "Pasando al siguiente paso..."
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
            
            # Mostrar Paso 3
            await self._mostrar_paso3_ligas(update, context, solicitud_id)
            
            return NC_ESPERANDO_LIGAS
            
        except Exception as e:
            logger.error(f"[NC Telegram] Error procesando IDMEX: {str(e)}")
            await update.message.reply_text(
                "❌ Error procesando tu información. Intenta de nuevo."
            )
            return NC_ESPERANDO_IDMEX
    
    # ==================== PASO 3: LIGAS NETCASH ====================
    
    async def _mostrar_paso3_ligas(self, update_or_query, context, solicitud_id):
        """Muestra el Paso 3: Cantidad de ligas NetCash"""
        mensaje = "🎫 **Paso 3 de 3: Cantidad de ligas NetCash**\n\n"
        mensaje += "¿Cuántas **ligas NetCash** necesitas?\n\n"
        mensaje += "Envíame solo el número (debe ser mayor a 0).\n\n"
        mensaje += "**Ejemplo:** 3"
        
        if hasattr(update_or_query, 'callback_query'):
            # Es un update
            await update_or_query.message.reply_text(mensaje, parse_mode="Markdown")
        else:
            # Es un query
            await update_or_query.message.reply_text(mensaje, parse_mode="Markdown")
    
    async def recibir_ligas(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Recibe y valida la cantidad de ligas - Paso 3"""
        ligas_text = update.message.text.strip()
        solicitud_id = context.user_data.get('nc_solicitud_id')
        
        if not solicitud_id:
            await update.message.reply_text("❌ Sesión expirada. Inicia de nuevo con /start")
            return ConversationHandler.END
        
        try:
            # Convertir a entero
            try:
                ligas = int(ligas_text)
            except ValueError:
                await update.message.reply_text(
                    "❌ Por favor envía solo un número.\n\n**Ejemplo:** 3"
                )
                return NC_ESPERANDO_LIGAS
            
            # Actualizar en el motor
            await netcash_service.actualizar_solicitud(
                solicitud_id,
                SolicitudUpdate(cantidad_ligas_reportada=ligas)
            )
            
            # Validar
            todas_validas, validaciones = await netcash_service.validar_solicitud_completa(solicitud_id)
            validacion_ligas = validaciones.get("ligas", {})
            
            if not validacion_ligas.get("valido"):
                razon = validacion_ligas.get("razon", "Cantidad inválida")
                mensaje = f"❌ **{razon}**\n\n"
                mensaje += "Por favor envía la cantidad correcta (número mayor a 0)."
                
                await update.message.reply_text(mensaje, parse_mode="Markdown")
                return NC_ESPERANDO_LIGAS
            
            # Válido - pasar al Paso 4 (Resumen y Confirmación)
            mensaje = f"✅ Cantidad de ligas: **{ligas}**\n\n"
            mensaje += "Generando resumen de tu operación..."
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
            
            # Generar resumen completo
            await self._mostrar_resumen_y_confirmar(update, context, solicitud_id)
            
            return NC_ESPERANDO_CONFIRMACION
            
        except Exception as e:
            logger.error(f"[NC Telegram] Error procesando ligas: {str(e)}")
            await update.message.reply_text("❌ Error procesando tu información. Intenta de nuevo.")
            return NC_ESPERANDO_LIGAS
    
    # ==================== PASO 4: RESUMEN Y CONFIRMACIÓN ====================
    
    async def _mostrar_resumen_y_confirmar(self, update, context, solicitud_id):
        """
        Muestra el resumen 'Esto es lo que entendí' y botones de confirmación.
        
        Este método usa el motor para generar el resumen y lo presenta de forma amigable.
        INCLUYE CÁLCULOS DE TOTALES Y COMISIONES.
        """
        try:
            # Obtener resumen del motor
            resumen = await netcash_service.generar_resumen_cliente(solicitud_id)
            
            if not resumen:
                raise Exception("No se pudo generar resumen")
            
            # Obtener solicitud para calcular totales
            solicitud = await netcash_service.obtener_solicitud(solicitud_id)
            comprobantes = solicitud.get("comprobantes", [])
            comprobantes_validos_list = [c for c in comprobantes if c.get("es_valido", False)]
            
            # CALCULAR SUMA DE TODOS LOS COMPROBANTES VÁLIDOS
            total_comprobantes_validos = 0.0
            for comp in comprobantes_validos_list:
                monto = comp.get("monto_detectado")
                if monto and monto > 0:
                    total_comprobantes_validos += monto
            
            # CALCULAR COMISIONES
            porcentaje_comision = 1.00  # 1.00%
            comision_cliente = total_comprobantes_validos * (porcentaje_comision / 100)
            monto_ligas = total_comprobantes_validos - comision_cliente
            
            # Construir mensaje
            mensaje = "📋 **Esto es lo que entendí de tu operación NetCash:**\n\n"
            
            # Campos detectados
            campos = resumen.campos_detectados
            campos_validos = resumen.campos_validos
            
            # Beneficiario
            beneficiario = campos.get("beneficiario", "No detectado")
            icono_benef = "✅" if "beneficiario" in campos_validos else "❌"
            mensaje += f"• Beneficiario: {beneficiario} {icono_benef}\n"
            
            # IDMEX
            idmex = campos.get("idmex", "No detectado")
            icono_idmex = "✅" if "idmex" in campos_validos else "❌"
            mensaje += f"• IDMEX: {idmex} {icono_idmex}\n"
            
            # Ligas
            ligas = campos.get("ligas", "No detectado")
            icono_ligas = "✅" if "ligas" in campos_validos else "❌"
            mensaje += f"• Ligas NetCash: {ligas} {icono_ligas}\n"
            
            # Comprobante - MEJORADO para diferenciar casos
            num_comprobantes = campos.get("comprobantes", 0)
            
            if num_comprobantes == 0:
                # Caso A: Sin archivos
                icono_comp = "❌"
                mensaje += f"• Comprobantes: 0 archivo(s) {icono_comp}\n"
            elif len(comprobantes_validos_list) == 0:
                # Caso B: Archivos recibidos pero ninguno válido
                icono_comp = "❌"
                mensaje += f"• Comprobantes: {num_comprobantes} archivo(s) {icono_comp}\n"
            else:
                # Caso C: Al menos uno válido - MOSTRAR TOTALES
                icono_comp = "✅"
                mensaje += f"• Comprobantes: {num_comprobantes} archivo(s) ({len(comprobantes_validos_list)} válido(s)) {icono_comp}\n"
                
                # AGREGAR CÁLCULOS FINANCIEROS
                mensaje += f"\n💰 **Resumen financiero:**\n"
                mensaje += f"  • Total depósitos detectados: ${total_comprobantes_validos:,.2f}\n"
                mensaje += f"  • Comisión NetCash ({porcentaje_comision:.2f}%): ${comision_cliente:,.2f}\n"
                mensaje += f"  • Monto a enviar en ligas NetCash: ${monto_ligas:,.2f}\n"
            
            # Mostrar errores si hay - MEJORADO
            if resumen.campos_invalidos:
                mensaje += "\n⚠️ **Problemas detectados:**\n"
                for error in resumen.campos_invalidos:
                    campo = error.get("campo", "desconocido")
                    razon = error.get("razon", "")
                    
                    # Mejorar mensaje para comprobantes
                    if campo == "comprobante":
                        if num_comprobantes == 0:
                            razon = "No se recibió ningún comprobante."
                        elif len(comprobantes_validos_list) == 0:
                            razon = "Se recibieron comprobantes, pero ninguno coincide con la cuenta NetCash autorizada."
                    
                    mensaje += f"• {campo.capitalize()}: {razon}\n"
            
            # Si todo está válido
            hay_errores = len(resumen.campos_invalidos) > 0 or len(resumen.campos_faltantes) > 0
            
            if not hay_errores:
                mensaje += "\n✅ **¡Todo en orden!**\n\n"
                mensaje += "Si los datos son correctos, confirma para enviar a proceso MBco."
                
                keyboard = [
                    [InlineKeyboardButton("✅ Confirmar y enviar a MBco", callback_data=f"nc_confirmar_{solicitud_id}")],
                    [InlineKeyboardButton("✏️ Corregir datos", callback_data=f"nc_corregir_{solicitud_id}")],
                    [InlineKeyboardButton("❌ Cancelar", callback_data="nc_cancelar")]
                ]
            else:
                mensaje += "\n❌ **Hay errores que debes corregir.**\n\n"
                mensaje += "Por favor corrige los datos marcados con ❌ y vuelve a intentar."
                
                keyboard = [
                    [InlineKeyboardButton("✏️ Corregir datos", callback_data=f"nc_corregir_{solicitud_id}")],
                    [InlineKeyboardButton("❌ Cancelar", callback_data="nc_cancelar")]
                ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.message:
                await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
            elif update.callback_query:
                await update.callback_query.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"[NC Telegram] Error mostrando resumen: {str(e)}")
            raise
    
    async def confirmar_operacion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Confirma la operación y la envía al motor para validación final.
        
        Si TODO está bien, el motor cambia a lista_para_mbc y genera folio.
        """
        query = update.callback_query
        await query.answer()
        
        # Extraer solicitud_id del callback_data
        solicitud_id = query.data.replace("nc_confirmar_", "")
        
        try:
            await query.edit_message_text("⏳ Procesando tu operación NetCash...")
            
            # Llamar al motor para validar y procesar
            exitoso, mensaje_motor = await netcash_service.procesar_solicitud_automaticamente(solicitud_id)
            
            if exitoso:
                # Obtener solicitud actualizada con folio
                solicitud = await netcash_service.obtener_solicitud(solicitud_id)
                folio = solicitud.get("folio_mbco", "N/A")
                
                # Calcular totales de comprobantes válidos
                comprobantes = solicitud.get("comprobantes", [])
                comprobantes_validos = [c for c in comprobantes if c.get("es_valido", False)]
                total_comprobantes_validos = sum(c.get("monto_detectado", 0) for c in comprobantes_validos if c.get("monto_detectado"))
                
                # Obtener comisiones calculadas
                comision_cliente = solicitud.get("comision_cliente", 0)
                monto_ligas = solicitud.get("monto_ligas", 0)
                
                mensaje = "🎉 **¡Tu operación NetCash fue registrada correctamente!**\n\n"
                mensaje += f"📋 **Folio:** {folio}\n"
                mensaje += f"👤 **Beneficiario:** {solicitud.get('beneficiario_reportado')}\n"
                mensaje += f"🆔 **IDMEX:** {solicitud.get('idmex_reportado')}\n"
                mensaje += f"🎫 **Ligas NetCash:** {solicitud.get('cantidad_ligas_reportada')}\n\n"
                
                mensaje += f"💰 **Resumen financiero:**\n"
                mensaje += f"  • Total depósitos detectados: ${total_comprobantes_validos:,.2f}\n"
                mensaje += f"  • Comisión NetCash (1.00%): ${comision_cliente:,.2f}\n"
                mensaje += f"  • Monto a enviar en ligas: ${monto_ligas:,.2f}\n"
                
                mensaje += f"\n✅ **Estado:** Lista para proceso interno MBco\n\n"
                mensaje += "Te avisaremos cuando tus ligas NetCash estén listas. 🚀"
                
                # Limpiar contexto
                context.user_data.clear()
                
                keyboard = [[InlineKeyboardButton("⬅️ Volver al menú", callback_data="nc_menu_principal")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
                return ConversationHandler.END
                
            else:
                # Hubo errores en la validación final
                mensaje = "❌ **Tu operación NO pudo ser procesada.**\n\n"
                mensaje += f"**Razón:** {mensaje_motor}\n\n"
                mensaje += "Por favor corrige los errores y vuelve a intentar."
                
                keyboard = [
                    [InlineKeyboardButton("✏️ Corregir datos", callback_data=f"nc_corregir_{solicitud_id}")],
                    [InlineKeyboardButton("❌ Cancelar", callback_data="nc_cancelar")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
                return NC_ESPERANDO_CONFIRMACION
                
        except Exception as e:
            logger.error(f"[NC Telegram] Error confirmando operación: {str(e)}")
            await query.edit_message_text(
                "❌ Error procesando tu operación. Por favor contacta a soporte."
            )
            return ConversationHandler.END
    
    async def corregir_datos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Permite corregir datos de la operación"""
        query = update.callback_query
        await query.answer()
        
        mensaje = "✏️ **Corrección de datos**\n\n"
        mensaje += "Para corregir tu operación, por favor inicia de nuevo con:\n"
        mensaje += "/start → Crear nueva operación\n\n"
        mensaje += "Esta operación quedará marcada como borrador."
        
        keyboard = [[InlineKeyboardButton("⬅️ Volver al menú", callback_data="nc_menu_principal")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
        
        # Limpiar contexto
        context.user_data.clear()
        return ConversationHandler.END
    
    async def cancelar_operacion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancela la operación en curso"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "❌ Operación cancelada.\n\nUsa /start cuando quieras crear una nueva operación.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Volver al menú", callback_data="nc_menu_principal")
            ]])
        )
        
        context.user_data.clear()
        return ConversationHandler.END
    
    # ==================== VER SOLICITUDES ====================
    
    async def ver_solicitudes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra las últimas solicitudes NetCash del cliente"""
        query = update.callback_query
        await query.answer()
        
        chat_id = str(update.effective_chat.id)
        user = update.effective_user
        telegram_id = str(user.id)
        
        try:
            # Verificar cliente activo
            es_activo, usuario, cliente = await self.bot.es_cliente_activo(telegram_id, chat_id)
            
            if not es_activo or not cliente:
                await query.edit_message_text(
                    "⚠️ Para ver tus solicitudes necesitas estar dado de alta como cliente activo."
                )
                return
            
            # Obtener solicitudes del motor
            solicitudes = await netcash_service.listar_solicitudes_cliente(
                cliente.get("id"),
                solo_validas=False,
                limite=10
            )
            
            if not solicitudes or len(solicitudes) == 0:
                mensaje = "📂 **No tienes solicitudes NetCash registradas.**\n\n"
                mensaje += "Cuando crees tu primera operación, la verás aquí."
            else:
                mensaje = f"📂 **Tus últimas solicitudes NetCash** ({len(solicitudes)}):\n\n"
                
                for sol in solicitudes:
                    folio = sol.get("folio_mbco", "(sin folio)")
                    ligas = sol.get("cantidad_ligas_reportada", "N/A")
                    estado = sol.get("estado", "desconocido").replace("_", " ").title()
                    
                    # Íconos por estado
                    if sol.get("estado") == "lista_para_mbc":
                        icono = "✅"
                    elif sol.get("estado") == "rechazada":
                        icono = "❌"
                    else:
                        icono = "⏳"
                    
                    mensaje += f"{icono} **{folio}** - {ligas} ligas - {estado}\n"
                
                mensaje += "\n💡 Para ver más detalles de una solicitud específica, anota el folio y contacta a soporte."
            
            keyboard = [[InlineKeyboardButton("⬅️ Volver al menú", callback_data="nc_menu_principal")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"[NC Telegram] Error mostrando solicitudes: {str(e)}")
            await query.edit_message_text(
                "❌ Error consultando tus solicitudes. Intenta de nuevo.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Volver al menú", callback_data="nc_menu_principal")
                ]])
            )

    
    # ==================== FLUJO DE CAPTURA MANUAL POR FALLO OCR ====================
    
    async def _iniciar_captura_manual(self, update: Update, context: ContextTypes.DEFAULT_TYPE, solicitud_id: str):
        """
        Inicia el flujo de captura manual cuando el OCR falla
        
        Args:
            update: Update de Telegram
            context: Contexto de la conversación
            solicitud_id: ID de la solicitud
        """
        logger.info(f"[NC Manual] Iniciando captura manual para solicitud {solicitud_id}")
        
        mensaje = "⚠️ **Tuvimos dificultad para leer algunos datos de tu comprobante.**\n\n"
        mensaje += "Para poder continuar con tu operación, necesito que me proporciones la siguiente información:\n\n"
        mensaje += "📝 **Paso 1:** ¿Cuántos comprobantes estás enviando en total?\n\n"
        mensaje += "Por favor envíame solo el número.\n\n"
        mensaje += "**Ejemplo:** 3"
        
        await update.message.reply_text(mensaje, parse_mode="Markdown")
    
    async def recibir_num_comprobantes_manual(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para recibir el número de comprobantes en captura manual"""
        solicitud_id = context.user_data.get('nc_solicitud_id')
        
        if not solicitud_id:
            await update.message.reply_text("❌ Sesión expirada. Inicia de nuevo con /start")
            return ConversationHandler.END
        
        try:
            # Validar que sea un número
            num_str = update.message.text.strip()
            try:
                num_comprobantes = int(num_str)
            except ValueError:
                await update.message.reply_text(
                    "❌ Por favor envía solo un número.\n\n**Ejemplo:** 3",
                    parse_mode="Markdown"
                )
                return NC_MANUAL_NUM_COMPROBANTES
            
            # Validar que sea mayor a 0
            if num_comprobantes <= 0:
                await update.message.reply_text(
                    "❌ El número de comprobantes debe ser mayor a 0.\n\n**Ejemplo:** 3",
                    parse_mode="Markdown"
                )
                return NC_MANUAL_NUM_COMPROBANTES
            
            # Guardar en contexto
            context.user_data['nc_manual_num_comprobantes'] = num_comprobantes
            
            logger.info(f"[NC Manual] Número de comprobantes capturado: {num_comprobantes}")
            
            # Siguiente pregunta: Monto total
            mensaje = f"✅ {num_comprobantes} comprobante(s) registrado(s).\n\n"
            mensaje += "📝 **Paso 2:** ¿Cuál es el monto TOTAL que amparan todos los comprobantes juntos?\n\n"
            mensaje += "Envíame el monto sin símbolos ni comas.\n\n"
            mensaje += "**Ejemplos:**\n"
            mensaje += "• 50000\n"
            mensaje += "• 125000.50\n"
            mensaje += "• 1000000"
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
            
            return NC_MANUAL_MONTO_TOTAL
            
        except Exception as e:
            logger.error(f"[NC Manual] Error procesando número de comprobantes: {str(e)}")
            await update.message.reply_text(
                "❌ Error procesando tu información. Por favor intenta de nuevo."
            )
            return NC_MANUAL_NUM_COMPROBANTES
    
    async def recibir_monto_total_manual(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para recibir el monto total en captura manual"""
        solicitud_id = context.user_data.get('nc_solicitud_id')
        
        if not solicitud_id:
            await update.message.reply_text("❌ Sesión expirada. Inicia de nuevo con /start")
            return ConversationHandler.END
        
        try:
            # Validar que sea un número
            monto_str = update.message.text.strip().replace(',', '').replace('$', '')
            try:
                monto_total = float(monto_str)
            except ValueError:
                await update.message.reply_text(
                    "❌ Por favor envía solo el monto numérico.\n\n**Ejemplos:** 50000 o 125000.50",
                    parse_mode="Markdown"
                )
                return NC_MANUAL_MONTO_TOTAL
            
            # Validar que sea mayor a 0
            if monto_total <= 0:
                await update.message.reply_text(
                    "❌ El monto debe ser mayor a 0.\n\n**Ejemplo:** 50000",
                    parse_mode="Markdown"
                )
                return NC_MANUAL_MONTO_TOTAL
            
            # Guardar en contexto
            context.user_data['nc_manual_monto_total'] = monto_total
            
            logger.info(f"[NC Manual] Monto total capturado: ${monto_total:,.2f}")
            
            # Siguiente paso: Elegir beneficiario (frecuente o nuevo)
            await self._mostrar_beneficiarios_manual(update, context, solicitud_id)
            
            return NC_MANUAL_ELEGIR_BENEFICIARIO
            
        except Exception as e:
            logger.error(f"[NC Manual] Error procesando monto total: {str(e)}")
            await update.message.reply_text(
                "❌ Error procesando tu información. Por favor intenta de nuevo."
            )
            return NC_MANUAL_MONTO_TOTAL
    
    async def _mostrar_beneficiarios_manual(self, update: Update, context: ContextTypes.DEFAULT_TYPE, solicitud_id: str):
        """
        Muestra los beneficiarios frecuentes o pregunta por uno nuevo
        
        Args:
            update: Update de Telegram
            context: Contexto de la conversación
            solicitud_id: ID de la solicitud
        """
        try:
            # Obtener solicitud para obtener cliente info
            solicitud = await netcash_service.obtener_solicitud(solicitud_id)
            cliente_id = solicitud.get("cliente_id")
            
            # Obtener cliente para obtener IDMEX
            from motor.motor_asyncio import AsyncIOMotorClient
            import os
            mongo_url = os.getenv('MONGO_URL')
            db_name = os.getenv('DB_NAME', 'netcash_mbco')
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            
            cliente = await db.clientes.find_one({"id": cliente_id}, {"_id": 0})
            
            # Obtener telegram_chat_id de la solicitud
            telegram_chat_id = solicitud.get("canal_metadata", {}).get("telegram_chat_id")
            
            # Usar IDMEX del cliente si existe, sino usar telegram_id como llave alternativa
            idmex_cliente = cliente.get("idmex") if cliente else None
            llave_busqueda = idmex_cliente if idmex_cliente else f"tg_{telegram_chat_id}"
            
            logger.info(f"[NC Manual-BenefFrec] Buscando beneficiarios frecuentes con llave: {llave_busqueda}")
            
            # Buscar beneficiarios frecuentes
            beneficiarios = await beneficiarios_frecuentes_service.obtener_beneficiarios_frecuentes(llave_busqueda, limite=3)
            
            monto_total = context.user_data.get('nc_manual_monto_total', 0)
            
            mensaje = f"✅ Monto total registrado: **${monto_total:,.2f}**\n\n"
            mensaje += "📝 **Paso 3:** Beneficiario\n\n"
            
            if beneficiarios and len(beneficiarios) > 0:
                mensaje += "He encontrado beneficiarios frecuentes:\n\n"
                
                # Guardar beneficiarios en contexto con índice
                context.user_data['beneficiarios_lista'] = {}
                for idx, benef in enumerate(beneficiarios, 1):
                    nombre = benef.get('nombre_beneficiario', '')
                    mensaje += f"{idx}. {nombre}\n"
                    # Guardar en contexto para selección por número
                    context.user_data['beneficiarios_lista'][str(idx)] = benef
                
                mensaje += "\n**Si quieres usar uno, responde solo con el número.**\n"
                mensaje += "**Si es un beneficiario nuevo, escribe el nombre completo** (nombre y dos apellidos).\n\n"
                mensaje += "Ejemplo: SERGIO CORTES LEYVA"
                
                await update.message.reply_text(mensaje, parse_mode="Markdown")
            else:
                # No hay frecuentes, pedir captura manual directa
                await self._pedir_beneficiario_manual_directo(update, context)
                
        except Exception as e:
            logger.error(f"[NC Manual] Error mostrando beneficiarios: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            await update.message.reply_text(
                "❌ Error al consultar beneficiarios. Continuaremos con captura manual."
            )
            await self._pedir_beneficiario_manual_directo(update, context)
    
    async def _pedir_beneficiario_manual_directo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pide el nombre del beneficiario directamente (sin frecuentes)"""
        monto_total = context.user_data.get('nc_manual_monto_total', 0)
        
        mensaje = f"✅ Monto total registrado: **${monto_total:,.2f}**\n\n"
        mensaje += "📝 **Paso 3:** Escribe el nombre completo del beneficiario que debe aparecer en las ligas.\n\n"
        mensaje += "El nombre debe tener:\n"
        mensaje += "• Mínimo 3 palabras (nombre + dos apellidos)\n"
        mensaje += "• Sin números\n\n"
        mensaje += "**Ejemplo:** JUAN CARLOS PÉREZ GÓMEZ"
        
        await update.message.reply_text(mensaje, parse_mode="Markdown")
    
    async def seleccionar_beneficiario_frecuente_manual(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler cuando el usuario selecciona un beneficiario frecuente en captura manual"""
        query = update.callback_query
        await query.answer()
        
        solicitud_id = context.user_data.get('nc_solicitud_id')
        
        if not solicitud_id:
            await query.edit_message_text("❌ Sesión expirada. Inicia de nuevo con /start")
            return ConversationHandler.END
        
        try:
            # Extraer ID del beneficiario del callback_data
            benef_id = query.data.replace("nc_manual_benef_freq_", "")
            
            # Recuperar datos del contexto
            benef_data = context.user_data.get(f"benef_freq_{benef_id}")
            
            if not benef_data:
                await query.edit_message_text("❌ Error recuperando datos. Por favor intenta de nuevo.")
                return NC_MANUAL_ELEGIR_BENEFICIARIO
            
            # Guardar en contexto
            context.user_data['nc_manual_beneficiario'] = benef_data.get('nombre_beneficiario')
            context.user_data['nc_manual_clabe'] = benef_data.get('clabe')
            context.user_data['nc_manual_id_beneficiario_frecuente'] = benef_id
            
            # Actualizar última vez usado
            await beneficiarios_frecuentes_service.actualizar_ultima_vez_usado(benef_id)
            
            logger.info(f"[NC Manual] Beneficiario frecuente seleccionado: {benef_data.get('nombre_beneficiario')}")
            
            # Siguiente paso: Número de ligas
            await self._pedir_num_ligas_manual(query, context)
            
            return NC_MANUAL_NUM_LIGAS
            
        except Exception as e:
            logger.error(f"[NC Manual] Error seleccionando beneficiario frecuente: {str(e)}")
            await query.edit_message_text("❌ Error procesando tu selección. Intenta de nuevo.")
            return NC_MANUAL_ELEGIR_BENEFICIARIO
    
    async def iniciar_captura_beneficiario_nuevo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para iniciar captura de beneficiario nuevo"""
        query = update.callback_query
        await query.answer()
        
        mensaje = "📝 **Captura de beneficiario nuevo**\n\n"
        mensaje += "Escribe el nombre completo del beneficiario.\n\n"
        mensaje += "El nombre debe tener:\n"
        mensaje += "• Mínimo 3 palabras (nombre + dos apellidos)\n"
        mensaje += "• Sin números\n\n"
        mensaje += "**Ejemplo:** JUAN CARLOS PÉREZ GÓMEZ"
        
        await query.edit_message_text(mensaje, parse_mode="Markdown")
        
        return NC_MANUAL_CAPTURAR_BENEFICIARIO
    
    async def recibir_beneficiario_nuevo_manual(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para recibir selección de beneficiario (número o nombre nuevo)"""
        solicitud_id = context.user_data.get('nc_solicitud_id')
        
        if not solicitud_id:
            await update.message.reply_text("❌ Sesión expirada. Inicia de nuevo con /start")
            return ConversationHandler.END
        
        try:
            texto = update.message.text.strip()
            
            # Verificar si es un número (selección de beneficiario frecuente)
            if texto.isdigit():
                numero = texto
                beneficiarios_lista = context.user_data.get('beneficiarios_lista', {})
                
                if numero in beneficiarios_lista:
                    # Selección de beneficiario frecuente
                    benef_data = beneficiarios_lista[numero]
                    
                    # Guardar en contexto
                    # NOTA: idmex_beneficiario es el IDMEX del beneficiario (persona física)
                    # idmex es la llave del cliente (puede ser tg_XXXXX si no tiene IDMEX)
                    context.user_data['nc_manual_beneficiario'] = benef_data.get('nombre_beneficiario')
                    context.user_data['nc_manual_idmex_beneficiario'] = benef_data.get('idmex_beneficiario')  # CORREGIDO: usar idmex_beneficiario
                    context.user_data['nc_manual_id_beneficiario_frecuente'] = benef_data.get('id')
                    
                    # Actualizar última vez usado
                    await beneficiarios_frecuentes_service.actualizar_ultima_vez_usado(benef_data.get('id'))
                    
                    logger.info(f"[NC Manual] Beneficiario frecuente #{numero} seleccionado: {benef_data.get('nombre_beneficiario')} - IDMEX: {benef_data.get('idmex_beneficiario')}")
                    
                    # Siguiente paso: Número de ligas
                    await self._pedir_num_ligas_manual_directo(update, context)
                    return NC_MANUAL_NUM_LIGAS
                else:
                    await update.message.reply_text(
                        f"❌ Número inválido. Por favor elige un número de la lista o escribe un nombre completo.",
                        parse_mode="Markdown"
                    )
                    return NC_MANUAL_ELEGIR_BENEFICIARIO
            
            # Si no es número, es un beneficiario nuevo
            beneficiario = texto.upper()
            
            # Validar beneficiario (mínimo 3 palabras, sin números)
            import re
            palabras = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]+", beneficiario)
            
            if len(palabras) < 3:
                await update.message.reply_text(
                    f"❌ El beneficiario debe tener mínimo 3 palabras (nombre + 2 apellidos).\n\n"
                    f"Detectadas: {len(palabras)} palabra(s)\n\n"
                    f"**Ejemplo:** SERGIO CORTES LEYVA",
                    parse_mode="Markdown"
                )
                return NC_MANUAL_ELEGIR_BENEFICIARIO
            
            if re.search(r'\d', beneficiario):
                await update.message.reply_text(
                    "❌ El nombre del beneficiario no debe contener números.\n\n"
                    "**Ejemplo:** SERGIO CORTES LEYVA",
                    parse_mode="Markdown"
                )
                return NC_MANUAL_ELEGIR_BENEFICIARIO
            
            # Guardar en contexto
            context.user_data['nc_manual_beneficiario'] = beneficiario
            
            logger.info(f"[NC Manual] Beneficiario nuevo capturado: {beneficiario}")
            
            # Pedir IDMEX del beneficiario (OBLIGATORIO)
            mensaje = f"✅ Beneficiario registrado: **{beneficiario}**\n\n"
            mensaje += "📝 **Paso siguiente:** Escribe el **IDMEX del beneficiario**.\n\n"
            mensaje += "Este dato es obligatorio para registrar a la persona física como beneficiario frecuente."
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
            
            return NC_MANUAL_CAPTURAR_IDMEX_BENEFICIARIO
            
        except Exception as e:
            logger.error(f"[NC Manual] Error procesando beneficiario: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            await update.message.reply_text(
                "❌ Error procesando tu información. Por favor intenta de nuevo."
            )
            return NC_MANUAL_ELEGIR_BENEFICIARIO
    
    async def recibir_idmex_beneficiario_manual(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para recibir IDMEX del beneficiario en captura manual"""
        solicitud_id = context.user_data.get('nc_solicitud_id')
        
        if not solicitud_id:
            await update.message.reply_text("❌ Sesión expirada. Inicia de nuevo con /start")
            return ConversationHandler.END
        
        try:
            idmex_beneficiario = update.message.text.strip()
            
            # Validar que no esté vacío
            if not idmex_beneficiario or len(idmex_beneficiario) < 6:
                await update.message.reply_text(
                    "❌ El IDMEX debe tener al menos 6 caracteres.\n\n"
                    "Por favor escribe el IDMEX del beneficiario.",
                    parse_mode="Markdown"
                )
                return NC_MANUAL_CAPTURAR_IDMEX_BENEFICIARIO
            
            # Validar largo máximo razonable
            if len(idmex_beneficiario) > 20:
                await update.message.reply_text(
                    "❌ El IDMEX no puede tener más de 20 caracteres.\n\n"
                    "Por favor verifica e intenta de nuevo.",
                    parse_mode="Markdown"
                )
                return NC_MANUAL_CAPTURAR_IDMEX_BENEFICIARIO
            
            # Guardar en contexto
            context.user_data['nc_manual_idmex_beneficiario'] = idmex_beneficiario
            
            logger.info(f"[NC Manual] IDMEX del beneficiario capturado: {idmex_beneficiario}")
            
            # Preguntar si quiere guardar como frecuente
            await self._preguntar_guardar_frecuente(update, context)
            
            return NC_MANUAL_GUARDAR_FRECUENTE
            
        except Exception as e:
            logger.error(f"[NC Manual] Error procesando IDMEX: {str(e)}")
            await update.message.reply_text(
                "❌ Error procesando tu información. Por favor intenta de nuevo."
            )
            return NC_MANUAL_CAPTURAR_IDMEX_BENEFICIARIO
    
    async def _preguntar_guardar_frecuente(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pregunta al usuario si quiere guardar el beneficiario como frecuente"""
        beneficiario = context.user_data.get('nc_manual_beneficiario')
        idmex_beneficiario = context.user_data.get('nc_manual_idmex_beneficiario')
        
        mensaje = f"✅ Datos del beneficiario capturados correctamente.\n\n"
        mensaje += f"**Beneficiario:** {beneficiario}\n"
        mensaje += f"**IDMEX:** {idmex_beneficiario}\n\n"
        
        mensaje += "💾 ¿Quieres guardar este beneficiario como frecuente para futuras operaciones?\n\n"
        mensaje += "Esto te permitirá seleccionarlo rápidamente la próxima vez."
        
        keyboard = [
            [InlineKeyboardButton("✅ Sí, guardar como frecuente", callback_data="nc_manual_guardar_si")],
            [InlineKeyboardButton("➡️ No, continuar sin guardar", callback_data="nc_manual_guardar_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
    
    async def procesar_guardar_frecuente(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para procesar la decisión de guardar como frecuente"""
        query = update.callback_query
        await query.answer()
        
        solicitud_id = context.user_data.get('nc_solicitud_id')
        
        if not solicitud_id:
            await query.edit_message_text("❌ Sesión expirada. Inicia de nuevo con /start")
            return ConversationHandler.END
        
        try:
            guardar = query.data == "nc_manual_guardar_si"
            
            if guardar:
                # Obtener datos del beneficiario
                beneficiario = context.user_data.get('nc_manual_beneficiario')
                idmex_beneficiario = context.user_data.get('nc_manual_idmex_beneficiario')
                
                # Obtener cliente info
                solicitud = await netcash_service.obtener_solicitud(solicitud_id)
                cliente_id = solicitud.get("cliente_id")
                telegram_chat_id = solicitud.get("canal_metadata", {}).get("telegram_chat_id")
                
                # Obtener IDMEX del cliente (para la asociación)
                from motor.motor_asyncio import AsyncIOMotorClient
                import os
                mongo_url = os.getenv('MONGO_URL')
                db_name = os.getenv('DB_NAME', 'netcash_mbco')
                client = AsyncIOMotorClient(mongo_url)
                db = client[db_name]
                
                cliente = await db.clientes.find_one({"id": cliente_id}, {"_id": 0})
                idmex_cliente = cliente.get("idmex") if cliente else None
                
                # Usar IDMEX del cliente si existe, sino usar telegram_id como llave alternativa
                llave_cliente = idmex_cliente if idmex_cliente else f"tg_{telegram_chat_id}"
                
                logger.info(f"[NC Manual-BenefFrec] Guardando beneficiario frecuente con llave: {llave_cliente}")
                
                # Crear beneficiario frecuente
                benef_creado = await beneficiarios_frecuentes_service.crear_beneficiario_frecuente(
                    idmex=llave_cliente,  # IDMEX del cliente o telegram_id alternativo
                    cliente_id=cliente_id,
                    nombre_beneficiario=beneficiario,
                    idmex_beneficiario=idmex_beneficiario  # IDMEX del beneficiario
                )
                
                if benef_creado:
                    context.user_data['nc_manual_id_beneficiario_frecuente'] = benef_creado.get('id')
                    logger.info(f"[NC Manual-BenefFrec] ✅ Beneficiario guardado: {benef_creado.get('id')}")
                    await query.edit_message_text(
                        "✅ Beneficiario guardado como frecuente.\n\nContinuando...",
                        parse_mode="Markdown"
                    )
                else:
                    # Solo log interno, NO mostrar mensaje técnico al usuario
                    logger.warning(f"[NC Manual-BenefFrec] No se pudo guardar beneficiario frecuente (continuando operación)")
                    await query.edit_message_text(
                        "✅ Continuando con tu operación...",
                        parse_mode="Markdown"
                    )
            else:
                logger.info(f"[NC Manual] Usuario decidió NO guardar como frecuente")
                await query.edit_message_text(
                    "✅ Entendido. Continuando sin guardar...",
                    parse_mode="Markdown"
                )
            
            # Siguiente paso: Número de ligas
            await self._pedir_num_ligas_manual(query, context, is_callback=False)
            
            return NC_MANUAL_NUM_LIGAS
            
        except Exception as e:
            logger.error(f"[NC Manual] Error procesando guardar frecuente: {str(e)}")
            await query.edit_message_text("❌ Error. Continuaremos con tu operación.")
            await self._pedir_num_ligas_manual(query, context, is_callback=False)
            return NC_MANUAL_NUM_LIGAS
    
    async def _pedir_num_ligas_manual(self, update_or_query, context: ContextTypes.DEFAULT_TYPE, is_callback: bool = True):
        """Pide el número de ligas en captura manual"""
        mensaje = "📝 **Paso final:** ¿Cuántas ligas NetCash necesitas?\n\n"
        mensaje += "Envíame solo el número (debe ser mayor a 0).\n\n"
        mensaje += "**Ejemplo:** 5"
        
        if is_callback:
            await update_or_query.message.reply_text(mensaje, parse_mode="Markdown")
        else:
            # Es un query de callback
            await update_or_query.message.reply_text(mensaje, parse_mode="Markdown")
    
    async def _pedir_num_ligas_manual_directo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pide el número de ligas directamente (sin query)"""
        mensaje = "📝 **Paso final:** ¿Cuántas ligas NetCash necesitas?\n\n"
        mensaje += "Envíame solo el número (debe ser mayor a 0).\n\n"
        mensaje += "**Ejemplo:** 5"
        
        await update.message.reply_text(mensaje, parse_mode="Markdown")
    
    async def recibir_num_ligas_manual(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para recibir número de ligas en captura manual"""
        solicitud_id = context.user_data.get('nc_solicitud_id')
        
        if not solicitud_id:
            await update.message.reply_text("❌ Sesión expirada. Inicia de nuevo con /start")
            return ConversationHandler.END
        
        try:
            # Validar que sea un número
            ligas_str = update.message.text.strip()
            try:
                num_ligas = int(ligas_str)
            except ValueError:
                await update.message.reply_text(
                    "❌ Por favor envía solo un número.\n\n**Ejemplo:** 5",
                    parse_mode="Markdown"
                )
                return NC_MANUAL_NUM_LIGAS
            
            # Validar que sea mayor a 0
            if num_ligas <= 0:
                await update.message.reply_text(
                    "❌ El número de ligas debe ser mayor a 0.\n\n**Ejemplo:** 5",
                    parse_mode="Markdown"
                )
                return NC_MANUAL_NUM_LIGAS
            
            # Guardar todos los datos capturados manualmente
            num_comprobantes = context.user_data.get('nc_manual_num_comprobantes')
            monto_total = context.user_data.get('nc_manual_monto_total')
            beneficiario = context.user_data.get('nc_manual_beneficiario')
            idmex_beneficiario = context.user_data.get('nc_manual_idmex_beneficiario')
            id_benef_frecuente = context.user_data.get('nc_manual_id_beneficiario_frecuente')
            
            logger.info(f"[NC Manual] Guardando datos capturados manualmente para {solicitud_id}")
            logger.info(f"[NC Manual] Comprobantes: {num_comprobantes}, Monto: ${monto_total:,.2f}, Ligas: {num_ligas}")
            logger.info(f"[NC Manual] Beneficiario: {beneficiario}, IDMEX: {idmex_beneficiario}")
            
            # Guardar en el servicio
            logger.info(f"[Netcash-P0] Iniciando guardado captura manual para {solicitud_id}")
            guardado = await netcash_service.guardar_datos_captura_manual(
                solicitud_id=solicitud_id,
                num_comprobantes=num_comprobantes,
                monto_total=monto_total,
                beneficiario=beneficiario,
                num_ligas=num_ligas,
                idmex_beneficiario=idmex_beneficiario
            )
            
            if not guardado:
                logger.error(f"[Netcash-P0][ERROR] No se pudo guardar captura manual para {solicitud_id}")
                await update.message.reply_text(
                    "❌ Error guardando los datos. Por favor contacta a soporte.",
                    parse_mode="Markdown"
                )
                return ConversationHandler.END
            
            logger.info(f"[Netcash-P0] ✅ Datos de captura manual guardados correctamente")
            
            # Mostrar resumen al usuario
            mensaje = "✅ **Datos capturados correctamente**\n\n"
            mensaje += "📋 **Resumen de tu operación:**\n\n"
            mensaje += f"• Número de comprobantes: {num_comprobantes}\n"
            mensaje += f"• Monto total: ${monto_total:,.2f}\n"
            mensaje += f"• Beneficiario: {beneficiario}\n"
            if idmex_beneficiario:
                mensaje += f"• IDMEX del beneficiario: {idmex_beneficiario}\n"
            mensaje += f"• Número de ligas: {num_ligas}\n\n"
            mensaje += "📌 **Importante:** Tu operación será revisada por nuestro equipo antes de procesarse.\n\n"
            mensaje += "Te notificaremos cuando Ana valide tu información."
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
            
            # ⭐ NUEVO: Notificar a Ana después de completar captura manual
            try:
                logger.info(f"[Netcash-P0] Notificando a Ana sobre captura manual completada")
                
                # Obtener solicitud actualizada
                solicitud = await netcash_service.obtener_solicitud(solicitud_id)
                
                if solicitud:
                    # Obtener usuario (cliente)
                    from motor.motor_asyncio import AsyncIOMotorClient
                    import os
                    mongo_url = os.getenv('MONGO_URL')
                    db_name = os.getenv('DB_NAME', 'netcash_mbco')
                    client_db = AsyncIOMotorClient(mongo_url)
                    db = client_db[db_name]
                    
                    cliente_id = solicitud.get("cliente_id")
                    usuario = await db.usuarios_netcash.find_one({"cliente_id": cliente_id}, {"_id": 0})
                    
                    # Importar handlers de Ana
                    from telegram_ana_handlers import telegram_ana_handlers
                    
                    # Notificar a Ana
                    await telegram_ana_handlers.notificar_nueva_solicitud_para_mbco(solicitud, usuario)
                    
                    logger.info(f"[Netcash-P0] ✅ Solicitud {solicitud_id} actualizada y enviada a Ana")
                else:
                    logger.error(f"[Netcash-P0][ERROR] No se pudo obtener solicitud {solicitud_id} para notificar a Ana")
                    
            except Exception as e_ana:
                logger.error(f"[Netcash-P0][ERROR] No se pudo notificar a Ana: {str(e_ana)}")
                import traceback
                logger.error(traceback.format_exc())
                # No bloquear el flujo por error de notificación
            
            # Limpiar contexto
            context.user_data.clear()
            
            logger.info(f"[Netcash-P0] ✅ Captura manual completada exitosamente para {solicitud_id}")
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"[NC Manual] Error procesando número de ligas: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            await update.message.reply_text(
                "❌ Error procesando tu información. Por favor contacta a soporte."
            )
            return ConversationHandler.END

