import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from dotenv import load_dotenv
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone

from models import OperacionNetCash, EstadoOperacion, Propietario
from config import MENSAJE_BIENVENIDA_CUENTA, MENSAJE_MANTENIMIENTO, MODO_MANTENIMIENTO, CONTACTOS

load_dotenv()

# Mapeo de teléfonos a roles
TELEFONO_A_ROL = {
    # Internos MBco
    "+5233121866 85": {"rol": "admin_mbco", "nombre": "Ana", "descripcion": "Administración NetCash"},
    "+523325362673": {"rol": "tesoreria", "nombre": "Toño", "descripcion": "Tesorería"},
    "+523332584721": {"rol": "supervisor_tesoreria", "nombre": "Javier", "descripcion": "Supervisor de Tesorería"},
    "+523317173461": {"rol": "direccion", "nombre": "Samuel", "descripcion": "Dirección MBco"},
    "+523311320098": {"rol": "direccion", "nombre": "Daniel", "descripcion": "Dirección MBco"},
    "+573013933477": {"rol": "control_operaciones", "nombre": "Claudia", "descripcion": "Control de Operaciones"},
    
    # Proveedor NetCash
    "+524428163215": {"rol": "proveedor_supervisor", "nombre": "Alonzo", "descripcion": "Supervisor Proveedor"},
    "+524423475954": {"rol": "proveedor_operaciones", "nombre": "Ximena", "descripcion": "Operadora Proveedor"},
    "+524427068087": {"rol": "proveedor_gerente", "nombre": "Rodrigo", "descripcion": "Gerente Proveedor"},
    "+524421603030": {"rol": "proveedor_direccion", "nombre": "Nash", "descripcion": "Dirección Proveedor"},
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
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
            logger.warning("TELEGRAM_BOT_TOKEN no configurado")
        
        self.app = None
    
    def normalizar_telefono(self, telefono: str) -> str:
        """Normaliza un teléfono removiendo espacios, guiones, paréntesis"""
        if not telefono:
            return ""
        # Remover todos los caracteres no numéricos excepto el +
        telefono = ''.join(c for c in telefono if c.isdigit() or c == '+')
        return telefono
    
    async def obtener_o_crear_usuario(self, chat_id: str, telefono: str = None, nombre: str = None):
        """Obtiene o crea un usuario en la BD"""
        usuario = await db.usuarios_telegram.find_one({"chat_id": chat_id}, {"_id": 0})
        
        if usuario:
            return usuario
        
        if not telefono:
            return None
        
        # Normalizar teléfono
        telefono_normalizado = self.normalizar_telefono(telefono)
        
        # Determinar rol
        rol_info = None
        rol = "desconocido"
        es_interno = False
        id_cliente = None
        
        # Buscar en mapeo de roles conocidos
        for tel_key, info in TELEFONO_A_ROL.items():
            tel_normalizado = self.normalizar_telefono(tel_key)
            if telefono_normalizado == tel_normalizado:
                rol_info = info
                rol = info["rol"]
                es_interno = rol in ["admin_mbco", "tesoreria", "supervisor_tesoreria", "direccion", "control_operaciones"]
                break
        
        # Si no está en roles conocidos, buscar en clientes
        if not rol_info:
            cliente = await db.clientes.find_one(
                {"$or": [
                    {"telefono_completo": telefono},
                    {"telefono_completo": telefono_normalizado}
                ]},
                {"_id": 0}
            )
            
            if cliente:
                rol = "cliente"
                id_cliente = cliente.get("id")
                rol_info = {"nombre": cliente.get("nombre"), "descripcion": "Cliente NetCash"}
        
        # Crear usuario
        nuevo_usuario = {
            "chat_id": chat_id,
            "telefono": telefono_normalizado,
            "nombre_telegram": nombre,
            "rol": rol,
            "es_interno": es_interno,
            "id_cliente": id_cliente,
            "rol_info": rol_info,
            "fecha_registro": datetime.now(timezone.utc).isoformat()
        }
        
        await db.usuarios_telegram.insert_one(nuevo_usuario)
        logger.info(f"Usuario creado: {chat_id} - Rol: {rol}")
        
        return nuevo_usuario
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Comando /start - Saludo inicial con identificación.
        """
        user = update.effective_user
        chat_id = str(update.effective_chat.id)
        
        # Verificar modo mantenimiento
        if MODO_MANTENIMIENTO == "ON":
            # Verificar si es Daniel (puede cambiar el modo)
            if not chat_id.endswith("0098"):
                await update.message.reply_text(MENSAJE_MANTENIMIENTO)
                return
        
        # Verificar si el usuario ya está registrado
        usuario = await self.obtener_o_crear_usuario(chat_id)
        
        if not usuario:
            # Primera vez - pedir teléfono
            from telegram import KeyboardButton, ReplyKeyboardMarkup
            
            mensaje = f"Hola {user.first_name} 😊\n\n"
            mensaje += "Para identificarte y darte el menú correcto de NetCash, necesito tu número de celular.\n\n"
            mensaje += "👇 Por favor toca el botón de abajo para compartirlo:"
            
            keyboard = [[KeyboardButton("📱 Compartir mi teléfono", request_contact=True)]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            
            await update.message.reply_text(mensaje, reply_markup=reply_markup)
            return
        
        # Usuario ya registrado - mostrar menú según rol
        await self.mostrar_menu_segun_rol(update, usuario)
    
    async def mostrar_menu_segun_rol(self, update: Update, usuario: dict):
        """Muestra el menú apropiado según el rol del usuario"""
        user = update.effective_user
        rol = usuario.get("rol", "desconocido")
        rol_info = usuario.get("rol_info", {})
        
        if rol == "cliente":
            # Menú para clientes
            mensaje = f"Hola {user.first_name} 😊\n\n{MENSAJE_BIENVENIDA_CUENTA}"
            
            keyboard = [
                [InlineKeyboardButton("📎 Nueva operación NetCash", callback_data="nueva_operacion")],
                [InlineKeyboardButton("📊 Ver mis operaciones", callback_data="ver_operaciones")],
                [InlineKeyboardButton("❓ Ayuda", callback_data="ayuda")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(mensaje, reply_markup=reply_markup)
            
        elif rol in ["admin_mbco", "tesoreria", "supervisor_tesoreria", "direccion", "control_operaciones"]:
            # Menú para internos MBco
            nombre = rol_info.get("nombre", user.first_name)
            descripcion = rol_info.get("descripcion", "Equipo MBco")
            
            mensaje = f"Hola {nombre} 👋\n\n"
            mensaje += f"Te identifico como: **{descripcion}**\n\n"
            mensaje += "En próximas fases tendrás opciones internas específicas para tu rol.\n\n"
            mensaje += "Por ahora puedes usar:\n"
            mensaje += "• /start - Ver este menú\n"
            mensaje += "• /ayuda - Información general\n"
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
            
        elif rol.startswith("proveedor_"):
            # Menú para proveedor NetCash
            nombre = rol_info.get("nombre", user.first_name) if rol_info else user.first_name
            
            mensaje = f"Hola {nombre} 👋\n\n"
            mensaje += "Te identifico como parte del **Proveedor NetCash**.\n\n"
            mensaje += "En próximas versiones podrás:\n"
            mensaje += "• Ver solicitudes de ligas pendientes\n"
            mensaje += "• Consultar tiempos de respuesta\n"
            mensaje += "• Recibir notificaciones de pagos\n\n"
            mensaje += "Por ahora usa /ayuda para más información."
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
            
        else:
            # Desconocido
            mensaje = f"Hola {user.first_name} 😊\n\n"
            mensaje += "Es tu primera operación con NetCash 🎉\n\n"
            mensaje += "Para continuar, necesito que te des de alta. Por favor contacta a Ana:\n\n"
            mensaje += "📧 gestion.ngdl@gmail.com\n"
            mensaje += "📱 +52 33 1218 6685\n\n"
            mensaje += "Menciona que quieres usar el Asistente NetCash."
            
            await update.message.reply_text(mensaje)
    
    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja cuando el usuario comparte su contacto"""
        contact = update.message.contact
        chat_id = str(update.effective_chat.id)
        
        # Obtener teléfono y nombre
        telefono = contact.phone_number
        nombre = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
        
        # Crear o actualizar usuario
        usuario = await self.obtener_o_crear_usuario(chat_id, telefono, nombre)
        
        if usuario:
            # Agradecer y mostrar menú
            mensaje = "✅ ¡Gracias por compartir tu teléfono!\n\n"
            
            from telegram import ReplyKeyboardRemove
            await update.message.reply_text(mensaje, reply_markup=ReplyKeyboardRemove())
            
            # Mostrar menú según rol
            await self.mostrar_menu_segun_rol(update, usuario)
        else:
            await update.message.reply_text("Hubo un error al registrarte. Por favor intenta de nuevo.")
    
    async def ayuda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Comando /ayuda - Información de ayuda.
        """
        mensaje = """**Asistente NetCash MBco** 🤖

Puedo ayudarte a:

1️⃣ **Procesar tus depósitos NetCash**
   - Envíame tu comprobante (PDF, imagen o ZIP)
   - Validaré que sea a la cuenta correcta
   - Calcularé tu capital y comisiones
   - Gestionaré las ligas con el proveedor

2️⃣ **Ver el estado de tus operaciones**
   - Consulta en qué paso va tu solicitud
   - Recibe actualizaciones automáticas

📌 **Cuenta para depósitos:**
Razón social: JARDINERIA Y COMERCIO THABYETHA SA DE CV
Banco: STP
CLABE: 646180139409481462

📞 **¿Necesitas ayuda personalizada?**
Contacta a Ana:
📧 gestion.ngdl@gmail.com
📱 +52 33 1218 6685

"""
        
        await update.message.reply_text(mensaje, parse_mode="Markdown")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Maneja los callbacks de botones.
        """
        query = update.callback_query
        await query.answer()
        
        if query.data == "nueva_operacion":
            await self.nueva_operacion(update, context)
        elif query.data == "ver_operaciones":
            await self.ver_operaciones(update, context)
        elif query.data == "ayuda":
            mensaje = """**Ayuda - Asistente NetCash**

Para iniciar una nueva operación:
1️⃣ Envía tu comprobante de depósito
2️⃣ Te pediré los datos del titular
3️⃣ Calcularé los montos
4️⃣ Gestionaré las ligas

Contacto: gestion.ngdl@gmail.com"""
            await query.edit_message_text(mensaje, parse_mode="Markdown")
    
    async def nueva_operacion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Inicia una nueva operación NetCash.
        """
        query = update.callback_query
        user = update.effective_user
        telegram_id = str(user.id)
        
        # Buscar o crear cliente
        cliente = await db.clientes.find_one({"telegram_id": telegram_id}, {"_id": 0})
        
        if not cliente:
            # Cliente nuevo - necesita alta
            mensaje = """Es tu primera operación con NetCash 🎉

Para continuar, necesito que te des de alta. Por favor contacta a Ana:

📧 gestion.ngdl@gmail.com
📱 +52 33 1218 6685

Menciona que quieres usar el Asistente NetCash."""
            await query.edit_message_text(mensaje)
            return
        
        # Crear nueva operación
        operacion = OperacionNetCash(
            cliente_telegram_id=telegram_id,
            cliente_nombre=cliente.get("nombre"),
            cliente_telefono=cliente.get("telefono"),
            propietario=cliente.get("propietario"),
            estado=EstadoOperacion.ESPERANDO_COMPROBANTES
        )
        
        doc = operacion.model_dump()
        doc['fecha_creacion'] = doc['fecha_creacion'].isoformat()
        await db.operaciones.insert_one(doc)
        
        # Guardar ID de operación en contexto
        context.user_data['operacion_actual'] = operacion.id
        
        mensaje = f"""Operación iniciada ✅

**ID:** `{operacion.id}`

Ahora envíame tu comprobante de depósito:
• PDF del banco
• Captura de pantalla
• Archivo ZIP con varios comprobantes

Validaré que el depósito sea a la cuenta correcta de MBco."""
        
        await query.edit_message_text(mensaje, parse_mode="Markdown")
    
    async def ver_operaciones(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Muestra las operaciones del usuario.
        """
        query = update.callback_query
        user = update.effective_user
        telegram_id = str(user.id)
        
        # Buscar operaciones del usuario
        operaciones = await db.operaciones.find(
            {"cliente_telegram_id": telegram_id},
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
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Maneja documentos enviados (comprobantes).
        """
        # Verificar si hay operación actual
        operacion_id = context.user_data.get('operacion_actual')
        
        if not operacion_id:
            await update.message.reply_text(
                "Primero inicia una operación con /start y selecciona 'Nueva operación NetCash'."
            )
            return
        
        await update.message.reply_text("🔍 Procesando comprobante...")
        
        # Por ahora, simular procesamiento
        # En producción, aquí se descargaría el archivo y se llamaría al API
        
        await update.message.reply_text(
            "**⚠️ Nota:** La funcionalidad de procesamiento de comprobantes desde Telegram se activará en la siguiente fase.\n\n"
            "Por ahora, usa la interfaz web para subir comprobantes.",
            parse_mode="Markdown"
        )
    
    async def handle_mensaje_no_reconocido(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Maneja cualquier mensaje de texto que no coincida con comandos o flujos conocidos.
        NUNCA deja un mensaje sin respuesta.
        """
        mensaje_respuesta = "Soy el Asistente NetCash 🤖\n\n"
        mensaje_respuesta += "Puedo ayudarte a:\n"
        mensaje_respuesta += "• Crear una nueva operación NetCash\n"
        mensaje_respuesta += "• Dar seguimiento a tus operaciones\n"
        mensaje_respuesta += "• Explicarte cómo mandar tus comprobantes\n\n"
        mensaje_respuesta += "👉 Escribe /start o toca una de las opciones del menú para continuar."
        
        await update.message.reply_text(mensaje_respuesta)
    
    def run(self):
        """
        Inicia el bot de Telegram.
        """
        if not self.token:
            logger.error("No se puede iniciar el bot sin TELEGRAM_BOT_TOKEN")
            return
        
        # Crear aplicación
        self.app = Application.builder().token(self.token).build()
        
        # Agregar handlers (el orden importa - los más específicos primero)
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("ayuda", self.ayuda))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.CONTACT, self.handle_contact))
        self.app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_document))
        
        # Handler catch-all para mensajes de texto no reconocidos (DEBE IR AL FINAL)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_mensaje_no_reconocido))
        
        # Iniciar bot
        logger.info("Bot de Telegram iniciado")
        self.app.run_polling()


if __name__ == "__main__":
    bot = TelegramBotNetCash()
    bot.run()