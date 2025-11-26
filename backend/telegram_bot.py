import os
import logging
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
from dotenv import load_dotenv
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone

from models import OperacionNetCash, EstadoOperacion, Propietario
from config import MENSAJE_BIENVENIDA_CUENTA, MENSAJE_MANTENIMIENTO, MODO_MANTENIMIENTO, CONTACTOS

load_dotenv()

# Estados del flujo conversacional
ESPERANDO_TELEFONO, ESPERANDO_EMAIL = range(2)

# Mapeo de teléfonos a roles internos
TELEFONO_A_ROL = {
    "+523312186685": {"rol": "admin_mbco", "nombre": "Ana", "descripcion": "Administración NetCash"},
    "+523325362673": {"rol": "tesoreria", "nombre": "Toño", "descripcion": "Tesorería"},
    "+523332584721": {"rol": "supervisor_tesoreria", "nombre": "Javier", "descripcion": "Supervisor de Tesorería"},
    "+523317173461": {"rol": "direccion", "nombre": "Samuel", "descripcion": "Dirección MBco"},
    "+523311320098": {"rol": "direccion", "nombre": "Daniel", "descripcion": "Dirección MBco"},
    "+573013933477": {"rol": "control_operaciones", "nombre": "Claudia", "descripcion": "Control de Operaciones"},
    "+524428163215": {"rol": "proveedor_supervisor", "nombre": "Alonzo", "descripcion": "Supervisor Proveedor"},
    "+524423475954": {"rol": "proveedor_operaciones", "nombre": "Ximena", "descripcion": "Operadora Proveedor"},
    "+524427068087": {"rol": "proveedor_gerente", "nombre": "Rodrigo", "descripcion": "Gerente Proveedor"},
    "+524421603030": {"rol": "proveedor_direccion", "nombre": "Nash", "descripcion": "Dirección Proveedor"},
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('/var/log/telegram_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[os.environ.get('DB_NAME', 'netcash_mbco')]


class TelegramBotNetCash:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN no configurado")
            raise ValueError("TELEGRAM_BOT_TOKEN es requerido")
        
        self.app = None
        self.ana_telegram_id = os.getenv("ANA_TELEGRAM_CHAT_ID")
        logger.info(f"Bot inicializado. Ana chat ID: {self.ana_telegram_id}")
    
    def normalizar_telefono(self, telefono: str) -> str:
        """Normaliza un teléfono removiendo espacios, guiones, paréntesis"""
        if not telefono:
            return ""
        telefono = ''.join(c for c in telefono if c.isdigit() or c == '+')
        return telefono
    
    async def notificar_ana_nuevo_cliente(self, cliente: dict):
        """Envía notificación a Ana cuando se crea un nuevo cliente desde Telegram"""
        if not self.ana_telegram_id:
            logger.warning("ANA_TELEGRAM_CHAT_ID no configurado, no se envía notificación")
            return
        
        try:
            mensaje = f"🆕 **Nuevo cliente creado desde Telegram**\n\n"
            mensaje += f"**Nombre:** {cliente.get('nombre')}\n"
            mensaje += f"**Teléfono:** {cliente.get('telefono_completo')}\n"
            mensaje += f"**Email:** {cliente.get('email') or 'No proporcionado'}\n"
            mensaje += f"**Cliente ID:** `{cliente.get('id')}`\n"
            mensaje += f"**Fecha:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
            
            await self.app.bot.send_message(
                chat_id=self.ana_telegram_id,
                text=mensaje,
                parse_mode="Markdown"
            )
            logger.info(f"Notificación enviada a Ana sobre nuevo cliente: {cliente.get('id')}")
        except Exception as e:
            logger.error(f"Error enviando notificación a Ana: {str(e)}")
    
    async def obtener_o_crear_usuario(self, chat_id: str, telefono: str = None, nombre: str = None):
        """Obtiene o crea un usuario en la BD"""
        usuario = await db.usuarios_telegram.find_one({"chat_id": chat_id}, {"_id": 0})
        
        if usuario:
            return usuario
        
        if not telefono:
            return None
        
        telefono_normalizado = self.normalizar_telefono(telefono)
        
        # Determinar rol
        rol_info = None
        rol = "desconocido"
        id_cliente = None
        
        # Buscar en mapeo de roles conocidos
        for tel_key, info in TELEFONO_A_ROL.items():
            tel_normalizado = self.normalizar_telefono(tel_key)
            if telefono_normalizado == tel_normalizado:
                rol_info = info
                rol = info["rol"]
                break
        
        # Si no está en roles conocidos, buscar en clientes
        if not rol_info:
            cliente = await db.clientes.find_one(
                {"$or": [
                    {"telefono_completo": telefono},
                    {"telefono_completo": telefono_normalizado},
                    {"telefono": telefono_normalizado.replace("+52", "")}
                ]},
                {"_id": 0}
            )
            
            if cliente:
                rol = "cliente"
                id_cliente = cliente.get("id")
                rol_info = {
                    "nombre": cliente.get("nombre"),
                    "descripcion": "Cliente NetCash"
                }
        
        # Crear usuario de telegram
        nuevo_usuario = {
            "chat_id": chat_id,
            "telefono": telefono_normalizado,
            "nombre_telegram": nombre or "Usuario",
            "rol": rol,
            "id_cliente": id_cliente,
            "rol_info": rol_info,
            "fecha_registro": datetime.now(timezone.utc).isoformat()
        }
        
        await db.usuarios_telegram.insert_one(nuevo_usuario)
        logger.info(f"Usuario creado: {chat_id} - Rol: {rol}")
        
        return nuevo_usuario
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        user = update.effective_user
        chat_id = str(update.effective_chat.id)
        
        logger.info(f"/start recibido de {user.first_name} (chat_id: {chat_id})")
        
        # Verificar modo mantenimiento
        if MODO_MANTENIMIENTO == "ON":
            await update.message.reply_text(MENSAJE_MANTENIMIENTO)
            return
        
        # Verificar si el usuario ya está registrado
        usuario = await db.usuarios_telegram.find_one({"chat_id": chat_id}, {"_id": 0})
        
        if not usuario:
            # Primera vez - pedir teléfono con botón de compartir contacto
            mensaje = f"Hola {user.first_name} 😊\n\n"
            mensaje += "¡Bienvenido a NetCash MBco!\n\n"
            mensaje += "Para identificarte, necesito tu número de celular.\n\n"
            mensaje += "👇 Por favor toca el botón de abajo para compartirlo:"
            
            keyboard = [[KeyboardButton("📱 Compartir mi teléfono", request_contact=True)]]
            reply_markup = ReplyKeyboardMarkup(
                keyboard,
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            await update.message.reply_text(mensaje, reply_markup=reply_markup)
            return
        
        # Usuario ya registrado - mostrar menú según rol
        await self.mostrar_menu_principal(update, usuario)
    
    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja cuando el usuario comparte su contacto"""
        contact = update.message.contact
        chat_id = str(update.effective_chat.id)
        
        telefono = contact.phone_number
        if not telefono.startswith("+"):
            telefono = f"+{telefono}"
        
        nombre = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
        
        logger.info(f"Contacto recibido: {telefono} de {nombre} (chat_id: {chat_id})")
        
        # Crear o actualizar usuario
        usuario = await self.obtener_o_crear_usuario(chat_id, telefono, nombre)
        
        if usuario:
            await update.message.reply_text(
                "✅ ¡Gracias por compartir tu teléfono!",
                reply_markup=ReplyKeyboardRemove()
            )
            await asyncio.sleep(0.5)
            await self.mostrar_menu_principal(update, usuario)
        else:
            await update.message.reply_text(
                "Hubo un error al registrarte. Por favor intenta de nuevo con /start",
                reply_markup=ReplyKeyboardRemove()
            )
    
    async def mostrar_menu_principal(self, update: Update, usuario: dict):
        """Muestra el menú principal según el rol del usuario"""
        user = update.effective_user
        rol = usuario.get("rol", "desconocido")
        id_cliente = usuario.get("id_cliente")
        
        if id_cliente and rol == "cliente":
            # Cliente registrado
            mensaje = f"Hola {user.first_name} 😊\n\n"
            mensaje += "¿Qué deseas hacer?\n"
            
            keyboard = [
                [InlineKeyboardButton("📎 Crear nueva operación NetCash", callback_data="nueva_operacion")],
                [InlineKeyboardButton("📊 Ver mis operaciones", callback_data="ver_operaciones")],
                [InlineKeyboardButton("❓ Ayuda", callback_data="ayuda")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(mensaje, reply_markup=reply_markup)
        
        elif rol in ["admin_mbco", "tesoreria", "supervisor_tesoreria", "direccion", "control_operaciones", "proveedor_supervisor", "proveedor_operaciones", "proveedor_gerente", "proveedor_direccion"]:
            # Usuario interno o proveedor
            rol_info = usuario.get("rol_info", {})
            nombre = rol_info.get("nombre", user.first_name)
            descripcion = rol_info.get("descripcion", "Usuario interno")
            
            mensaje = f"Hola {nombre} 👋\n\n"
            mensaje += f"Te identifico como: **{descripcion}**\n\n"
            mensaje += "En próximas fases tendrás opciones específicas para tu rol.\n\n"
            mensaje += "Por ahora usa /ayuda para más información."
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
        
        else:
            # Usuario sin cliente registrado - ofrecer registro
            mensaje = f"Hola {user.first_name} 😊\n\n"
            mensaje += "¡Bienvenido a NetCash MBco! 🎉\n\n"
            mensaje += "¿Qué deseas hacer?\n"
            
            keyboard = [
                [InlineKeyboardButton("1️⃣ Registrarme como cliente NetCash", callback_data="registrar_cliente")],
                [InlineKeyboardButton("2️⃣ Crear nueva operación NetCash", callback_data="nueva_operacion")],
                [InlineKeyboardButton("3️⃣ Ver mis operaciones", callback_data="ver_operaciones")],
                [InlineKeyboardButton("❓ Ayuda", callback_data="ayuda")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(mensaje, reply_markup=reply_markup)
    
    async def iniciar_registro_cliente(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inicia el flujo de registro de cliente"""
        query = update.callback_query
        await query.answer()
        
        chat_id = str(update.effective_chat.id)
        user = update.effective_user
        
        # Verificar si ya está registrado
        usuario = await db.usuarios_telegram.find_one({"chat_id": chat_id}, {"_id": 0})
        cliente_existente = None
        if usuario and usuario.get("id_cliente"):
            cliente_existente = await db.clientes.find_one({"id": usuario["id_cliente"]}, {"_id": 0})
        
        if cliente_existente:
            await query.edit_message_text("Ya estás registrado como cliente. Puedes crear operaciones.")
            return ConversationHandler.END
        
        # Tomar nombre del perfil de Telegram
        nombre_telegram = f"{user.first_name} {user.last_name or ''}".strip()
        context.user_data['nombre_cliente'] = nombre_telegram
        context.user_data['telefono_cliente'] = usuario.get("telefono") if usuario else None
        
        # Pedir teléfono si no lo tenemos
        if not context.user_data['telefono_cliente']:
            mensaje = f"Para registrarte como cliente NetCash, necesito algunos datos.\n\n"
            mensaje += f"**Nombre:** {nombre_telegram}\n\n"
            mensaje += "📱 Por favor mándame tu número de celular con LADA\n"
            mensaje += "Ejemplo: +52 33 1234 5678"
            
            await query.edit_message_text(mensaje, parse_mode="Markdown")
            return ESPERANDO_TELEFONO
        else:
            # Ya tenemos teléfono, pedir email
            mensaje = f"Perfecto, estos son tus datos:\n\n"
            mensaje += f"**Nombre:** {nombre_telegram}\n"
            mensaje += f"**Teléfono:** {context.user_data['telefono_cliente']}\n\n"
            mensaje += "📧 Si quieres, mándame tu correo electrónico para enviarte notificaciones.\n"
            mensaje += "O escribe **'no'** para saltar este paso."
            
            await query.edit_message_text(mensaje, parse_mode="Markdown")
            return ESPERANDO_EMAIL
    
    async def recibir_telefono(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Recibe el teléfono del usuario"""
        telefono = update.message.text.strip()
        
        # Validar formato básico
        telefono_normalizado = self.normalizar_telefono(telefono)
        if len(telefono_normalizado) < 10:
            await update.message.reply_text(
                "❌ El teléfono no parece válido. Por favor envía un número con LADA.\n"
                "Ejemplo: +52 33 1234 5678"
            )
            return ESPERANDO_TELEFONO
        
        context.user_data['telefono_cliente'] = telefono_normalizado
        
        mensaje = f"Perfecto, estos son tus datos:\n\n"
        mensaje += f"**Nombre:** {context.user_data['nombre_cliente']}\n"
        mensaje += f"**Teléfono:** {telefono_normalizado}\n\n"
        mensaje += "📧 Si quieres, mándame tu correo electrónico para enviarte notificaciones.\n"
        mensaje += "O escribe **'no'** para saltar este paso."
        
        await update.message.reply_text(mensaje, parse_mode="Markdown")
        return ESPERANDO_EMAIL
    
    async def recibir_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Recibe el email del usuario y completa el registro"""
        email_input = update.message.text.strip().lower()
        
        email = None
        if email_input != "no" and "@" in email_input:
            email = email_input
        
        context.user_data['email_cliente'] = email
        
        # Crear cliente
        try:
            chat_id = str(update.effective_chat.id)
            
            nuevo_cliente = {
                "id": str(uuid.uuid4()),
                "nombre": context.user_data['nombre_cliente'],
                "email": email,
                "pais": "MX",
                "prefijo_telefono": "+52",
                "telefono": context.user_data['telefono_cliente'].replace("+52", ""),
                "telefono_completo": context.user_data['telefono_cliente'],
                "telegram_id": str(update.effective_user.id),
                "porcentaje_comision_cliente": 2.5,  # Default
                "canal_preferido": "Telegram",
                "propietario": "M",  # Ana por defecto
                "rfc": None,
                "notas": f"Cliente creado desde Telegram (alta automática) - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
                "fecha_alta": datetime.now(timezone.utc).isoformat(),
                "activo": True
            }
            
            await db.clientes.insert_one(nuevo_cliente)
            
            # Actualizar usuario de telegram
            await db.usuarios_telegram.update_one(
                {"chat_id": chat_id},
                {"$set": {
                    "rol": "cliente",
                    "id_cliente": nuevo_cliente["id"],
                    "rol_info": {"nombre": nuevo_cliente["nombre"], "descripcion": "Cliente NetCash"}
                }},
                upsert=True
            )
            
            logger.info(f"Cliente registrado: {nuevo_cliente['id']} - {nuevo_cliente['nombre']}")
            
            # Notificar a Ana
            await self.notificar_ana_nuevo_cliente(nuevo_cliente)
            
            mensaje = "✅ ¡Listo! Ya te di de alta como cliente NetCash MBco.\n\n"
            mensaje += f"**Nombre:** {nuevo_cliente['nombre']}\n"
            mensaje += f"**Teléfono:** {nuevo_cliente['telefono_completo']}\n"
            if email:
                mensaje += f"**Email:** {email}\n"
            mensaje += "\nAhora ya puedes crear operaciones y mandarme tus comprobantes para procesarlos.\n\n"
            mensaje += "Usa /start para ver el menú."
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
            
            # Limpiar datos temporales
            context.user_data.clear()
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Error registrando cliente: {str(e)}")
            await update.message.reply_text(
                "Hubo un error al registrarte. Por favor intenta de nuevo con /start"
            )
            context.user_data.clear()
            return ConversationHandler.END
    
    async def cancelar_registro(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancela el flujo de registro"""
        context.user_data.clear()
        await update.message.reply_text(
            "Registro cancelado. Usa /start cuando quieras registrarte."
        )
        return ConversationHandler.END
    
    async def nueva_operacion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Crea una nueva operación"""
        query = update.callback_query
        await query.answer()
        
        chat_id = str(update.effective_chat.id)
        user = update.effective_user
        telegram_id = str(user.id)
        
        # Verificar que esté registrado como cliente
        usuario = await db.usuarios_telegram.find_one({"chat_id": chat_id}, {"_id": 0})
        
        if not usuario or not usuario.get("id_cliente"):
            mensaje = "⚠️ **Para crear una operación primero necesito darte de alta como cliente.**\n\n"
            mensaje += "Elige la opción **1️⃣ Registrarme como cliente NetCash**.\n\n"
            mensaje += "Usa /start para ver el menú."
            await query.edit_message_text(mensaje, parse_mode="Markdown")
            return
        
        # Buscar cliente
        cliente = await db.clientes.find_one({"id": usuario["id_cliente"]}, {"_id": 0})
        
        if not cliente:
            mensaje = "Error: No se encontró tu registro de cliente. Contacta a Ana:\n\n"
            mensaje += "📧 gestion.ngdl@gmail.com\n📱 +52 33 1218 6685"
            await query.edit_message_text(mensaje)
            return
        
        # Crear nueva operación
        operacion = OperacionNetCash(
            id_cliente=cliente["id"],
            cliente_nombre=cliente.get("nombre"),
            cliente_email=cliente.get("email"),
            cliente_telefono_completo=cliente.get("telefono_completo"),
            cliente_telegram_id=telegram_id,
            porcentaje_comision_usado=cliente.get("porcentaje_comision_cliente"),
            propietario=cliente.get("propietario"),
            estado=EstadoOperacion.ESPERANDO_COMPROBANTES
        )
        
        doc = operacion.model_dump()
        doc['fecha_creacion'] = doc['fecha_creacion'].isoformat()
        await db.operaciones.insert_one(doc)
        
        context.user_data['operacion_actual'] = operacion.id
        
        mensaje = f"✅ **Creé tu operación NetCash**\n\n"
        mensaje += f"**ID:** `{operacion.id}`\n\n"
        mensaje += "Ahora mándame el comprobante del depósito (PDF o imagen) para procesarlo.\n\n"
        mensaje += f"**Recuerda:** El depósito debe ser a la cuenta:\n"
        mensaje += f"JARDINERIA Y COMERCIO THABYETHA SA DE CV\n"
        mensaje += f"CLABE: 646180139409481462"
        
        await query.edit_message_text(mensaje, parse_mode="Markdown")
        
        logger.info(f"Operación creada: {operacion.id} para cliente {cliente['id']}")
    
    async def ver_operaciones(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra las operaciones del usuario"""
        query = update.callback_query
        await query.answer()
        
        chat_id = str(update.effective_chat.id)
        
        usuario = await db.usuarios_telegram.find_one({"chat_id": chat_id}, {"_id": 0})
        
        if not usuario or not usuario.get("id_cliente"):
            await query.edit_message_text("Primero necesitas registrarte como cliente. Usa /start")
            return
        
        operaciones = await db.operaciones.find(
            {"id_cliente": usuario["id_cliente"]},
            {"_id": 0}
        ).sort("fecha_creacion", -1).limit(10).to_list(10)
        
        if not operaciones:
            await query.edit_message_text("Aún no tienes operaciones NetCash.")
            return
        
        mensaje = "**Tus operaciones NetCash:**\n\n"
        
        for op in operaciones:
            estado = op.get("estado", "DESCONOCIDO")
            fecha = op.get("fecha_creacion", "")
            if isinstance(fecha, str):
                fecha = datetime.fromisoformat(fecha).strftime("%d/%m/%Y %H:%M")
            
            mensaje += f"• `{op['id'][:8]}...` - {estado}\n"
            mensaje += f"  Fecha: {fecha}\n\n"
        
        await query.edit_message_text(mensaje, parse_mode="Markdown")
    
    async def ayuda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /ayuda"""
        mensaje = "**Ayuda - Asistente NetCash MBco** 🤖\n\n"
        mensaje += "Puedo ayudarte a:\n\n"
        mensaje += "1️⃣ **Registrarte como cliente**\n"
        mensaje += "   - Te pediré nombre, teléfono y email\n\n"
        mensaje += "2️⃣ **Crear operaciones NetCash**\n"
        mensaje += "   - Necesitas estar registrado primero\n\n"
        mensaje += "3️⃣ **Procesar tus comprobantes**\n"
        mensaje += "   - Envía PDF o imagen del depósito\n\n"
        mensaje += "📌 **Cuenta para depósitos:**\n"
        mensaje += "Razón social: JARDINERIA Y COMERCIO THABYETHA SA DE CV\n"
        mensaje += "Banco: STP\n"
        mensaje += "CLABE: 646180139409481462\n\n"
        mensaje += "📞 **Ayuda personalizada:**\n"
        mensaje += "Contacta a Ana:\n"
        mensaje += "📧 gestion.ngdl@gmail.com\n"
        mensaje += "📱 +52 33 1218 6685"
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(mensaje, parse_mode="Markdown")
        else:
            await update.message.reply_text(mensaje, parse_mode="Markdown")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja los callbacks de botones"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "nueva_operacion":
            await self.nueva_operacion(update, context)
        elif query.data == "ver_operaciones":
            await self.ver_operaciones(update, context)
        elif query.data == "ayuda":
            await self.ayuda(update, context)
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja documentos enviados (comprobantes)"""
        operacion_id = context.user_data.get('operacion_actual')
        
        if not operacion_id:
            await update.message.reply_text(
                "Primero crea una operación con /start y selecciona 'Crear nueva operación NetCash'."
            )
            return
        
        await update.message.reply_text("🔍 Procesando comprobante...")
        
        # Aquí iría la lógica para descargar y procesar el archivo
        await update.message.reply_text(
            "**⚠️ Nota:** La funcionalidad de procesamiento de comprobantes desde Telegram se activará en la siguiente fase.\n\n"
            "Por ahora, usa la interfaz web para subir comprobantes.",
            parse_mode="Markdown"
        )
    
    async def handle_mensaje_no_reconocido(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja mensajes de texto no reconocidos"""
        mensaje_respuesta = "Soy el Asistente NetCash 🤖\n\n"
        mensaje_respuesta += "Puedo ayudarte a:\n"
        mensaje_respuesta += "• Registrarte como cliente NetCash\n"
        mensaje_respuesta += "• Crear una nueva operación\n"
        mensaje_respuesta += "• Dar seguimiento a tus operaciones\n\n"
        mensaje_respuesta += "👉 Escribe /start para ver el menú."
        
        await update.message.reply_text(mensaje_respuesta)
    
    def run(self):
        """Inicia el bot de Telegram"""
        if not self.token:
            logger.error("No se puede iniciar el bot sin TELEGRAM_BOT_TOKEN")
            return
        
        # Crear aplicación
        self.app = Application.builder().token(self.token).build()
        
        # Handler del flujo de registro de cliente (conversación)
        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.iniciar_registro_cliente, pattern='^registrar_cliente$')],
            states={
                ESPERANDO_TELEFONO: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.recibir_telefono)],
                ESPERANDO_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.recibir_email)],
            },
            fallbacks=[CommandHandler('start', self.start)],
        )
        
        # Agregar handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("ayuda", self.ayuda))
        self.app.add_handler(conv_handler)
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.CONTACT, self.handle_contact))
        self.app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_mensaje_no_reconocido))
        
        logger.info("Bot iniciado correctamente. Esperando mensajes...")
        
        # Iniciar el bot
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    bot = TelegramBotNetCash()
    bot.run()
