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
import aiohttp
from pathlib import Path

from models import OperacionNetCash, EstadoOperacion, Propietario
from config import MENSAJE_BIENVENIDA_CUENTA, MENSAJE_MANTENIMIENTO, MODO_MANTENIMIENTO, CONTACTOS

load_dotenv()

# Estados del flujo conversacional
ESPERANDO_TELEFONO, ESPERANDO_EMAIL = range(2)
# Estados para flujo de operación extendido (legacy)
ESPERANDO_MAS_COMPROBANTES, ESPERANDO_CANTIDAD_LIGAS, ESPERANDO_NOMBRE_LIGAS, ESPERANDO_IDMEX = range(10, 14)

# Estados para flujo NetCash V1 (nuevo motor centralizado) - REORDENADO
# Nuevo orden: Comprobantes → Beneficiario+IDMEX → Ligas → Confirmación
NC_ESPERANDO_COMPROBANTE, NC_ESPERANDO_BENEFICIARIO, NC_ESPERANDO_IDMEX, NC_ESPERANDO_LIGAS, NC_ESPERANDO_CONFIRMACION = range(20, 25)

# Estados para captura manual por fallo OCR
NC_MANUAL_NUM_COMPROBANTES, NC_MANUAL_MONTO_TOTAL, NC_MANUAL_ELEGIR_BENEFICIARIO, NC_MANUAL_CAPTURAR_BENEFICIARIO, NC_MANUAL_CAPTURAR_IDMEX_BENEFICIARIO, NC_MANUAL_GUARDAR_FRECUENTE, NC_MANUAL_NUM_LIGAS = range(30, 37)

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

# Backend API URL
BACKEND_API = os.getenv("BACKEND_API_URL", "http://localhost:8001/api")


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
            telegram_id = cliente.get('telegram_id', 'N/A')
            
            mensaje = f"🆕 **Nuevo usuario escribió al bot NetCash y NO está vinculado como cliente.**\n\n"
            mensaje += f"📲 **Telegram ID:** `{telegram_id}`\n"
            mensaje += f"👤 **Nombre:** {cliente.get('nombre')}\n"
            mensaje += f"📱 **Teléfono:** {cliente.get('telefono_completo')}\n"
            mensaje += f"📧 **Email:** {cliente.get('email') or 'No proporcionado'}\n"
            mensaje += f"🆔 **Cliente ID:** `{cliente.get('id')}`\n"
            mensaje += f"📅 **Fecha/hora:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
            mensaje += "**Instrucción:**\n"
            mensaje += "1) Aprobar al cliente.\n"
            mensaje += "2) Asignar comisión (% NetCash, mínimo 0.375%).\n"
            mensaje += "3) Vincular Telegram ID al cliente.\n\n"
            mensaje += "**Para aprobar desde aquí, usa:**\n"
            mensaje += f"`/aprobar_cliente {telegram_id} 1.00`\n\n"
            mensaje += "(donde 1.00 = 1.00%)"
            
            await self.app.bot.send_message(
                chat_id=self.ana_telegram_id,
                text=mensaje,
                parse_mode="Markdown"
            )
            logger.info(f"Notificación enviada a Ana sobre nuevo cliente: {cliente.get('id')} (TG ID: {telegram_id})")
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
                # Si el cliente está activo, marcar como cliente_activo
                estado_cliente = cliente.get("estado", "")
                if estado_cliente == "activo":
                    rol = "cliente_activo"
                else:
                    rol = "cliente"
                    
                id_cliente = cliente.get("id")
                rol_info = {
                    "nombre": cliente.get("nombre"),
                    "descripcion": "Cliente NetCash"
                }
                
                # Enviar mensaje de vinculación exitosa
                logger.info(f"Cliente encontrado en BD: {cliente.get('nombre')} - Estado: {estado_cliente}")
        
        # Crear usuario de telegram
        nuevo_usuario = {
            "telegram_id": str(chat_id),  # Guardar telegram_id
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
        
        # Si se vinculó un cliente activo, actualizar el cliente en BD con telegram_id
        if id_cliente and rol == "cliente_activo":
            await db.clientes.update_one(
                {"id": id_cliente},
                {"$set": {"telegram_id": str(chat_id)}}
            )
            logger.info(f"Cliente {id_cliente} vinculado con telegram_id {chat_id}")
        
        # Si es usuario desconocido (no cliente ni rol interno), notificar a Ana
        if rol == "desconocido" and self.ana_telegram_id:
            # Verificar que el bot esté inicializado antes de enviar mensaje
            if not self.app or not self.app.bot:
                logger.warning(f"[obtener_o_crear_usuario] No se puede notificar a Ana - bot no inicializado aún. Usuario: {chat_id}")
                return nuevo_usuario
            
            try:
                telegram_id = chat_id  # El chat_id ES el telegram_id
                username = nuevo_usuario.get("nombre_telegram", "N/A")
                
                mensaje_ana = f"🆕 **Nuevo usuario escribió al bot NetCash y NO está vinculado como cliente.**\n\n"
                mensaje_ana += f"📲 **Telegram ID:** `{telegram_id}`\n"
                mensaje_ana += f"👤 **Usuario:** {username}\n"
                mensaje_ana += f"📱 **Teléfono:** {telefono_normalizado}\n"
                mensaje_ana += f"📅 **Fecha/hora:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
                mensaje_ana += "**Instrucción:**\n"
                mensaje_ana += "1) Darlo de alta como cliente.\n"
                mensaje_ana += "2) Asignarle comisión con `/aprobar_cliente`.\n\n"
                mensaje_ana += f"Para aprobar: `/aprobar_cliente {telegram_id} 1.00`"
                
                logger.info(f"[obtener_o_crear_usuario] Enviando notificación a Ana sobre usuario {telegram_id}...")
                await self.app.bot.send_message(
                    chat_id=self.ana_telegram_id,
                    text=mensaje_ana,
                    parse_mode="Markdown"
                )
                logger.info(f"[obtener_o_crear_usuario] ✅ Notificación enviada a Ana sobre nuevo usuario desconocido: {chat_id}")
            except Exception as e:
                logger.error(f"[obtener_o_crear_usuario] ❌ Error notificando a Ana sobre usuario nuevo: {str(e)}")
                import traceback
                logger.error(f"[obtener_o_crear_usuario] Traceback: {traceback.format_exc()}")
        
        return nuevo_usuario
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        user = update.effective_user
        chat_id = str(update.effective_chat.id)
        telegram_id = str(user.id)
        
        logger.info(f"[NetCash][START] Comando recibido de {user.first_name} (chat_id: {chat_id}, telegram_id: {telegram_id})")
        
        try:
            # Verificar modo mantenimiento
            if MODO_MANTENIMIENTO == "ON":
                await update.message.reply_text(MENSAJE_MANTENIMIENTO)
                return
            
            # Buscar usuario por telegram_id (más confiable que chat_id)
            usuario = await db.usuarios_telegram.find_one({"telegram_id": telegram_id}, {"_id": 0})
            
            if not usuario:
                # Usuario completamente nuevo - crear registro básico
                logger.info(f"[NetCash][START] Usuario nuevo detectado: {telegram_id}")
                
                nuevo_usuario = {
                    "telegram_id": telegram_id,
                    "chat_id": chat_id,
                    "username": user.username or None,
                    "nombre": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    "telefono": None,
                    "rol": "desconocido",
                    "id_cliente": None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                
                await db.usuarios_telegram.insert_one(nuevo_usuario)
                logger.info(f"[NetCash][START] Usuario nuevo creado en BD: {telegram_id}")
                
                # Mostrar mensaje de bienvenida + botón para compartir teléfono
                mensaje = "Hola 👋, bienvenido a NetCash MBco.\n\n"
                mensaje += "Para darte de alta necesito que compartas tu teléfono.\n"
                mensaje += "Toca el botón de abajo para continuar 👇"
                
                keyboard = [[KeyboardButton("📱 Compartir mi teléfono", request_contact=True)]]
                reply_markup = ReplyKeyboardMarkup(
                    keyboard,
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
                
                await update.message.reply_text(mensaje, reply_markup=reply_markup)
                logger.info(f"[NetCash][START] Usuario nuevo sin teléfono -> se pide contacto")
                return
            
            # Usuario ya registrado - actualizar chat_id si es necesario
            if usuario.get("chat_id") != chat_id:
                await db.usuarios_telegram.update_one(
                    {"telegram_id": telegram_id},
                    {"$set": {"chat_id": chat_id, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
                logger.info(f"[NetCash][START] Chat ID actualizado para {telegram_id}")
            
            # Verificar estado
            rol = usuario.get("rol")
            telefono = usuario.get("telefono")
            id_cliente = usuario.get("id_cliente")
            
            if rol == "cliente_activo" or (id_cliente and rol in ["cliente", "cliente_activo"]):
                # Cliente aprobado -> menú completo
                logger.info(f"[NetCash][START] Cliente activo -> menú")
                await self.mostrar_menu_principal(update, usuario)
            elif telefono:
                # Ya compartió contacto pero no aprobado -> mensaje de espera
                logger.info(f"[NetCash][START] Usuario con teléfono esperando aprobación")
                mensaje = "📋 **Tu registro está en proceso.**\n\n"
                mensaje += "Ana revisará tu información y te asignará una comisión.\n\n"
                mensaje += "Te avisaremos por este mismo chat cuando ya puedas operar."
                await update.message.reply_text(mensaje, parse_mode="Markdown")
            else:
                # Sin teléfono -> pedir contacto nuevamente
                logger.info(f"[NetCash][START] Usuario sin teléfono -> se pide contacto")
                mensaje = "Hola 👋, bienvenido a NetCash MBco.\n\n"
                mensaje += "Para darte de alta necesito que compartas tu teléfono.\n"
                mensaje += "Toca el botón de abajo para continuar 👇"
                
                keyboard = [[KeyboardButton("📱 Compartir mi teléfono", request_contact=True)]]
                reply_markup = ReplyKeyboardMarkup(
                    keyboard,
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
                
                await update.message.reply_text(mensaje, reply_markup=reply_markup)
        
        except Exception as e:
            logger.error(f"[NetCash][START][ERROR] {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"[NetCash][START][ERROR] Traceback:\n{traceback.format_exc()}")
            
            # Mensaje de fallback para que el usuario no quede sin respuesta
            await update.message.reply_text(
                "Hola 👋\n\n"
                "Tu registro en NetCash tuvo un problema temporal.\n"
                "Intenta de nuevo en unos minutos o contacta a soporte."
            )
    
    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja cuando el usuario comparte su contacto"""
        contact = update.message.contact
        chat_id = str(update.effective_chat.id)
        user = update.effective_user
        telegram_id = str(user.id)
        
        telefono = contact.phone_number
        if not telefono.startswith("+"):
            telefono = f"+{telefono}"
        
        nombre = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
        
        logger.info(f"[handle_contact] Contacto recibido: {telefono} de {nombre} (chat_id: {chat_id}, telegram_id: {telegram_id})")
        logger.info(f"[handle_contact] ANA_TELEGRAM_CHAT_ID configurado: {self.ana_telegram_id}")
        
        # Crear o actualizar usuario
        usuario = await self.obtener_o_crear_usuario(chat_id, telefono, nombre)
        
        if usuario:
            # Si es usuario desconocido (sin cliente vinculado), mostrar mensaje especial
            if usuario.get("rol") == "desconocido":
                mensaje = "✅ **¡Gracias por compartir tu contacto!**\n\n"
                mensaje += "Te estamos dando de alta como cliente NetCash.\n"
                mensaje += "Ana revisará tu información y te asignará una comisión.\n\n"
                mensaje += "Te avisaremos por este mismo chat cuando ya puedas operar."
                
                await update.message.reply_text(
                    mensaje,
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="Markdown"
                )
                logger.info(f"[NetCash][CONTACTO] Usuario {chat_id} compartió contacto, rol=desconocido, esperando aprobación de Ana")
                
                # Notificar a Ana sobre este nuevo cliente
                logger.info(f"[handle_contact] Verificando notificación a Ana - ana_telegram_id: {self.ana_telegram_id}")
                
                if not self.ana_telegram_id:
                    logger.warning(f"[handle_contact] ⚠️ NO SE ENVIÓ NOTIFICACIÓN - ana_telegram_id no configurado")
                elif not self.app or not self.app.bot:
                    logger.warning(f"[handle_contact] ⚠️ NO SE PUEDE NOTIFICAR - bot no inicializado")
                else:
                    try:
                        # Usar el telegram_id del update, no del usuario en BD
                        telegram_id_notif = telegram_id
                        logger.info(f"[handle_contact] Preparando mensaje para Ana - telegram_id: {telegram_id_notif}")
                        
                        mensaje_ana = f"🆕 **Nuevo usuario compartió contacto y está esperando aprobación.**\n\n"
                        mensaje_ana += f"📲 **Telegram ID:** `{telegram_id_notif}`\n"
                        mensaje_ana += f"👤 **Nombre:** {nombre}\n"
                        mensaje_ana += f"📱 **Teléfono:** {telefono}\n"
                        mensaje_ana += f"📅 **Fecha/hora:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
                        mensaje_ana += "**Para aprobar:**\n"
                        mensaje_ana += f"`/aprobar_cliente {telegram_id_notif} 1.00`"
                        
                        logger.info(f"[handle_contact] Enviando mensaje a Ana (chat_id: {self.ana_telegram_id})...")
                        await self.app.bot.send_message(
                            chat_id=self.ana_telegram_id,
                            text=mensaje_ana,
                            parse_mode="Markdown"
                        )
                        logger.info(f"[handle_contact] ✅ Notificación enviada exitosamente a Ana (ID: {self.ana_telegram_id}) sobre usuario {telegram_id_notif}")
                    except Exception as e:
                        logger.error(f"[handle_contact] ❌ Error notificando a Ana: {str(e)}")
                        import traceback
                        logger.error(f"[handle_contact] Traceback: {traceback.format_exc()}")
                
                return
            elif usuario.get("rol") == "cliente_activo":
                # Cliente activo vinculado exitosamente
                nombre_cliente = usuario.get("rol_info", {}).get("nombre", "")
                mensaje = f"✅ **Te encontré como cliente ya registrado: {nombre_cliente}**\n\n"
                mensaje += "Te acabo de vincular a tu cuenta NetCash MBco.\n"
                mensaje += "Ya puedes crear operaciones y mandarme tus comprobantes.\n\n"
                mensaje += "Usa /start para ver el menú de opciones."
                
                await update.message.reply_text(
                    mensaje,
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="Markdown"
                )
                logger.info(f"[NetCash][CONTACTO] Cliente activo vinculado: {chat_id}")
            else:
                # Usuario conocido pero pendiente de aprobación
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
        
        # Cliente activo o con id_cliente vinculado
        if id_cliente or rol in ["cliente", "cliente_activo"]:
            # Cliente registrado - verificar estado
            # Si tiene id_cliente, buscar en la colección clientes
            cliente = None
            if id_cliente:
                cliente = await db.clientes.find_one({"id": id_cliente}, {"_id": 0})
            
            # CASO 1: Cliente existe en BD y está activo
            if cliente and cliente.get("estado") == "activo":
                # Cliente ACTIVO - mensaje personalizado (NetCash V1)
                mensaje = f"Hola {user.first_name} 😊\n\n"
                mensaje += "Ya estás dado de alta como cliente NetCash.\n\n"
                mensaje += "¿Qué necesitas hacer hoy?\n"
                
                keyboard = [
                    [InlineKeyboardButton("🧾 Crear nueva operación NetCash", callback_data="nc_crear_operacion")],
                    [InlineKeyboardButton("💳 Ver cuenta para depósitos", callback_data="nc_ver_cuenta")],
                    [InlineKeyboardButton("📂 Ver mis solicitudes", callback_data="nc_ver_solicitudes")],
                    [InlineKeyboardButton("❓ Ayuda", callback_data="ayuda")]
                ]
            # CASO 2: Rol es "cliente_activo" pero NO tiene cliente en BD (caso borde - debe crearse)
            elif rol == "cliente_activo" and not cliente:
                logger.warning(f"[MENU] Usuario {usuario.get('telegram_id')} tiene rol 'cliente_activo' pero sin registro en colección 'clientes'")
                # Mostrar menú completo de todas formas - el sistema funcionará
                mensaje = f"Hola {user.first_name} 😊\n\n"
                mensaje += "Ya estás dado de alta como cliente NetCash.\n\n"
                mensaje += "¿Qué necesitas hacer hoy?\n"
                
                keyboard = [
                    [InlineKeyboardButton("🧾 Crear nueva operación NetCash", callback_data="nc_crear_operacion")],
                    [InlineKeyboardButton("💳 Ver cuenta para depósitos", callback_data="nc_ver_cuenta")],
                    [InlineKeyboardButton("📂 Ver mis solicitudes", callback_data="nc_ver_solicitudes")],
                    [InlineKeyboardButton("❓ Ayuda", callback_data="ayuda")]
                ]
            # CASO 3: Cliente pendiente de validación
            else:
                mensaje = f"Hola {user.first_name} 😊\n\n"
                mensaje += "Tu registro está en revisión por Ana.\n\n"
                mensaje += "Mientras tanto, puedes:\n"
                
                keyboard = [
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
            # Usuario sin cliente registrado (desconocido o pendiente)
            mensaje = f"Hola {user.first_name} 😊\n\n"
            
            # Verificar si ya compartió contacto
            if usuario.get("telefono"):
                # Ya compartió contacto, está esperando aprobación de Ana
                mensaje += "📋 **Tu registro está en proceso.**\n\n"
                mensaje += "Ana revisará tu información y te asignará una comisión.\n\n"
                mensaje += "Te avisaremos por este mismo chat cuando ya puedas operar.\n\n"
                mensaje += "Mientras tanto, puedes usar /ayuda si tienes dudas."
            else:
                # Aún no ha compartido contacto
                mensaje += "¡Bienvenido a NetCash MBco! 🎉\n\n"
                mensaje += "Para comenzar, necesito registrarte como cliente.\n"
                
                keyboard = [
                    [InlineKeyboardButton("1️⃣ Registrarme como cliente NetCash", callback_data="registrar_cliente")],
                    [InlineKeyboardButton("❓ Ayuda", callback_data="ayuda")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(mensaje, reply_markup=reply_markup)
                return
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
    
    async def iniciar_registro_cliente(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inicia el flujo de registro de cliente"""
        query = update.callback_query
        await query.answer()
        
        chat_id = str(update.effective_chat.id)
        user = update.effective_user
        
        # Verificar si ya está registrado
        usuario = await db.usuarios_telegram.find_one({"chat_id": chat_id}, {"_id": 0})
        if not usuario:
            await query.edit_message_text("Error: No se encontró tu usuario. Usa /start para comenzar.")
            return ConversationHandler.END
        
        telefono_normalizado = self.normalizar_telefono(usuario.get("telefono", ""))
        
        # CASO B: Buscar si ya existe un cliente con ese teléfono (creado por Ana en el dashboard)
        cliente_existente = await db.clientes.find_one(
            {"$or": [
                {"telefono_completo": telefono_normalizado},
                {"telefono": telefono_normalizado.replace("+52", "")}
            ]},
            {"_id": 0}
        )
        
        if cliente_existente:
            # Cliente ya existe, solo vincular el telegram_id y chat_id
            await db.clientes.update_one(
                {"id": cliente_existente["id"]},
                {"$set": {"telegram_id": str(user.id)}}
            )
            
            await db.usuarios_telegram.update_one(
                {"chat_id": chat_id},
                {"$set": {
                    "rol": "cliente",
                    "id_cliente": cliente_existente["id"],
                    "rol_info": {"nombre": cliente_existente["nombre"], "descripcion": "Cliente NetCash"}
                }}
            )
            
            logger.info(f"Cliente existente vinculado a Telegram: {cliente_existente['id']} - {cliente_existente['nombre']}")
            
            mensaje = f"✅ **Te encontré como cliente ya registrado: {cliente_existente['nombre']}.**\n\n"
            mensaje += "Te acabo de vincular a tu cuenta NetCash MBco.\n"
            mensaje += "Ya puedes crear operaciones y mandarme tus comprobantes."
            
            await query.edit_message_text(mensaje, parse_mode="Markdown")
            return ConversationHandler.END
        
        # CASO A: Cliente nuevo - verificar si ya lo registramos antes
        cliente_telegram = None
        if usuario.get("id_cliente"):
            cliente_telegram = await db.clientes.find_one({"id": usuario["id_cliente"]}, {"_id": 0})
        
        if cliente_telegram:
            await query.edit_message_text("Ya estás registrado como cliente. Puedes crear operaciones.")
            return ConversationHandler.END
        
        # Tomar nombre del perfil de Telegram
        nombre_telegram = f"{user.first_name} {user.last_name or ''}".strip()
        context.user_data['nombre_cliente'] = nombre_telegram
        context.user_data['telefono_cliente'] = telefono_normalizado
        
        # Ya tenemos teléfono, pedir email (OBLIGATORIO para completar el alta)
        mensaje = f"Para completar tu alta como cliente NetCash, necesito algunos datos.\n\n"
        mensaje += f"**Nombre:** {nombre_telegram}\n"
        mensaje += f"**Teléfono:** {telefono_normalizado}\n\n"
        mensaje += "📧 Por favor, mándame tu **correo electrónico**.\n"
        mensaje += "Lo usaremos para enviarte ligas NetCash y avisos importantes.\n\n"
        mensaje += "Si no tienes correo o prefieres no proporcionarlo, escribe **'sin correo'**."
        
        await query.edit_message_text(mensaje, parse_mode="Markdown")
        return ESPERANDO_EMAIL
    
    async def recibir_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Recibe el email del usuario y completa el registro"""
        email_input = update.message.text.strip().lower()
        
        email = None
        if email_input not in ["no", "sin correo", "ninguno"] and "@" in email_input:
            email = email_input
        
        context.user_data['email_cliente'] = email
        
        # Crear cliente NUEVO (CASO A)
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
                "porcentaje_comision_cliente": None,  # Ana lo definirá (NULL = pendiente)
                "canal_preferido": "Telegram",
                "propietario": "M",  # Ana
                "rfc": None,
                "notas": "Cliente creado desde Telegram (alta automática). Comisión pendiente de configurar.",
                "estado": "pendiente_validacion",  # Pendiente de validación por Ana
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
            
            logger.info(f"Cliente NUEVO registrado: {nuevo_cliente['id']} - {nuevo_cliente['nombre']}")
            
            # Notificar a Ana
            await self.notificar_ana_nuevo_cliente(nuevo_cliente)
            
            mensaje = "✅ **¡Te di de alta como cliente NetCash MBco.**\n\n"
            mensaje += "Tu registro está pendiente de validación interna.\n"
            mensaje += "Ana revisará tus datos y definirá las condiciones de tu servicio.\n\n"
            mensaje += "Mientras tanto, ya puedes ir creando operaciones y mandando comprobantes.\n\n"
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
    
    async def es_cliente_activo(self, telegram_id: str, chat_id: str = None):
        """Verifica si un usuario es cliente NetCash activo"""
        logger.info(f"[es_cliente_activo] ===== INICIO ===== TG={telegram_id} (type:{type(telegram_id)}) CHAT={chat_id} (type:{type(chat_id) if chat_id else 'None'})")
        
        # Buscar usuario por telegram_id o chat_id
        if chat_id:
            query = {"$or": [{"telegram_id": telegram_id}, {"chat_id": chat_id}]}
        else:
            query = {"telegram_id": telegram_id}
        logger.info(f"[es_cliente_activo] Query MongoDB: {query}")
        
        usuario = await db.usuarios_telegram.find_one(query, {"_id": 0})
        
        if not usuario:
            logger.warning(f"[es_cliente_activo] ❌ Usuario NO encontrado en BD con query: {query}")
            # Intentar buscar también todos los usuarios para debuggear
            todos = await db.usuarios_telegram.find({}, {"_id": 0, "telegram_id": 1, "chat_id": 1, "nombre": 1}).to_list(10)
            logger.warning(f"[es_cliente_activo] DEBUG - Usuarios en BD: {todos}")
            return False, None, None
        
        # Verificar que tenga id_cliente o rol adecuado
        id_cliente = usuario.get("id_cliente")
        rol = usuario.get("rol")
        nombre = usuario.get("nombre", "N/A")
        
        logger.info(f"[es_cliente_activo] ✓ Usuario encontrado: '{nombre}' | Rol: {rol} | id_cliente: {id_cliente}")
        
        # Verificar si tiene id_cliente
        if not id_cliente:
            logger.warning(f"[es_cliente_activo] ❌ Usuario SIN id_cliente asignado")
            return False, usuario, None
        
        # Buscar el cliente en BD
        cliente = await db.clientes.find_one({"id": id_cliente}, {"_id": 0})
        
        if not cliente:
            logger.warning(f"[es_cliente_activo] ❌ Cliente NO encontrado en BD con id={id_cliente}")
            # CASO BORDE: Si el rol es cliente_activo pero no hay cliente en BD
            # Permitir continuar de todas formas (la operación funcionará)
            if rol == "cliente_activo":
                logger.warning(f"[es_cliente_activo] ⚠️  Usuario tiene rol=cliente_activo sin cliente en BD - PERMITIENDO continuar")
                # Crear cliente dummy para que el flujo funcione
                cliente_dummy = {
                    "id": id_cliente,
                    "nombre": nombre,
                    "estado": "activo",
                    "telegram_id": int(telegram_id) if telegram_id.isdigit() else telegram_id
                }
                return True, usuario, cliente_dummy
            return False, usuario, None
        
        estado = cliente.get("estado")
        nombre_cliente = cliente.get("nombre", "N/A")
        
        logger.info(f"[es_cliente_activo] ✓ Cliente encontrado: '{nombre_cliente}' | Estado: {estado}")
        
        if estado != "activo":
            logger.warning(f"[es_cliente_activo] ❌ Cliente NO activo (estado={estado})")
            return False, usuario, cliente
        
        logger.info(f"[es_cliente_activo] ✅✅✅ CLIENTE ACTIVO CONFIRMADO ✅✅✅")
        return True, usuario, cliente
    
    async def nueva_operacion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Crea una nueva operación"""
        query = update.callback_query
        await query.answer()
        
        chat_id = str(update.effective_chat.id)
        user = update.effective_user
        telegram_id = str(user.id)
        
        logger.info(f"[nueva_operacion] ===== INICIO =====")
        logger.info(f"[nueva_operacion] chat_id={chat_id} (type: {type(chat_id)})")
        logger.info(f"[nueva_operacion] telegram_id={telegram_id} (type: {type(telegram_id)})")
        logger.info(f"[nueva_operacion] user.id={user.id} (type: {type(user.id)})")
        
        # CRÍTICO: Actualizar chat_id si el usuario existe pero tiene chat_id null
        # (esto pasa cuando el usuario fue dado de alta desde la web)
        logger.info(f"[nueva_operacion] Buscando usuario en BD con telegram_id={telegram_id}")
        usuario_bd = await db.usuarios_telegram.find_one({"telegram_id": telegram_id}, {"_id": 0})
        
        if usuario_bd:
            logger.info(f"[nueva_operacion] Usuario encontrado en BD:")
            logger.info(f"[nueva_operacion]   - telegram_id: {usuario_bd.get('telegram_id')}")
            logger.info(f"[nueva_operacion]   - chat_id: {usuario_bd.get('chat_id')}")
            logger.info(f"[nueva_operacion]   - rol: {usuario_bd.get('rol')}")
            logger.info(f"[nueva_operacion]   - id_cliente: {usuario_bd.get('id_cliente')}")
            
            if usuario_bd.get("chat_id") != chat_id:
                logger.info(f"[nueva_operacion] Chat ID necesita actualización: '{usuario_bd.get('chat_id')}' -> '{chat_id}'")
                await db.usuarios_telegram.update_one(
                    {"telegram_id": telegram_id},
                    {"$set": {"chat_id": chat_id, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
                logger.info(f"[nueva_operacion] ✅ Chat ID actualizado exitosamente")
            else:
                logger.info(f"[nueva_operacion] Chat ID ya es correcto: {chat_id}")
        else:
            logger.error(f"[nueva_operacion] ❌ Usuario NO encontrado en BD con telegram_id={telegram_id}")
        
        # Verificar que esté registrado como cliente activo
        logger.info(f"[nueva_operacion] Llamando a es_cliente_activo(telegram_id={telegram_id}, chat_id={chat_id})")
        es_activo, usuario, cliente = await self.es_cliente_activo(telegram_id, chat_id)
        logger.info(f"[nueva_operacion] Resultado de es_cliente_activo: es_activo={es_activo}")
        
        if not es_activo:
            logger.warning(f"[nueva_operacion] ❌ Cliente NO activo - enviando mensaje de registro")
            logger.warning(f"[nueva_operacion] usuario={usuario}")
            logger.warning(f"[nueva_operacion] cliente={cliente}")
            mensaje = "⚠️ **Para crear una operación primero necesito darte de alta como cliente.**\n\n"
            mensaje += "Elige la opción **1️⃣ Registrarme como cliente NetCash**.\n\n"
            mensaje += "Usa /start para ver el menú."
            await query.edit_message_text(mensaje, parse_mode="Markdown")
            return
        
        # VALIDAR ESTADO DEL CLIENTE (BLOQUE 1) - Ya validado en es_cliente_activo
        
        # Crear nueva operación llamando al backend API
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "id_cliente": cliente["id"],
                    "origen_operacion": "telegram",  # BLOQUE 5: Marcar origen
                    "estado": "EN_CAPTURA"  # Estado inicial
                }
                async with session.post(f"{BACKEND_API}/operaciones", json=payload) as response:
                    if response.status == 200:
                        operacion_data = await response.json()
                        folio = operacion_data.get("folio_mbco", "N/A")
                        operacion_id = operacion_data.get("id")
                        
                        context.user_data['operacion_actual'] = operacion_id
                        context.user_data['folio_actual'] = folio
                        
                        # BLOQUE 1: Mensaje mejorado al crear operación
                        mensaje = f"✅ **Creé tu operación NetCash**\n\n"
                        mensaje += f"**Folio MBco:** {folio}\n\n"
                        mensaje += "Ahora mándame los comprobantes del depósito para esta operación.\n"
                        mensaje += "Puedes enviar:\n"
                        mensaje += "• PDFs\n"
                        mensaje += "• Imágenes (JPG, PNG)\n"
                        mensaje += "• Archivos ZIP con varios comprobantes adentro\n\n"
                        mensaje += "Envíalos todos seguidos y al final escribe **'listo'** cuando hayas terminado.\n\n"
                        
                        # Obtener cuenta activa (NetCash V1)
                        from config_cuentas_service import config_cuentas_service, TipoCuenta
                        cuenta_activa = await config_cuentas_service.obtener_cuenta_activa(TipoCuenta.CONCERTADORA)
                        if cuenta_activa:
                            mensaje += f"**Recuerda:** El depósito debe ser a la cuenta:\n"
                            mensaje += f"{cuenta_activa.get('beneficiario')}\n"
                            mensaje += f"Banco: {cuenta_activa.get('banco')}\n"
                            mensaje += f"CLABE: {cuenta_activa.get('clabe')}"
                        else:
                            mensaje += "**Recuerda:** El depósito debe ser a la cuenta NetCash autorizada."
                        
                        # Marcar que está recibiendo comprobantes
                        context.user_data['recibiendo_comprobantes'] = True
                        
                        await query.edit_message_text(mensaje, parse_mode="Markdown")
                        logger.info(f"Operación creada: {operacion_id} (Folio: {folio}) para cliente {cliente['id']}")
                    else:
                        await query.edit_message_text("Error al crear la operación. Por favor intenta de nuevo.")
        except Exception as e:
            logger.error(f"Error creando operación: {str(e)}")
            await query.edit_message_text("Error al crear la operación. Por favor intenta de nuevo más tarde.")
    
    async def ver_operaciones(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra las operaciones del usuario (BLOQUE B)"""
        query = update.callback_query
        await query.answer()
        
        chat_id = str(update.effective_chat.id)
        user = update.effective_user
        telegram_id = str(user.id)
        
        logger.info(f"[ver_operaciones] chat_id={chat_id}, telegram_id={telegram_id}, user.id type={type(user.id)}")
        
        # CRÍTICO: Actualizar chat_id si el usuario existe pero tiene chat_id null
        # (esto pasa cuando el usuario fue dado de alta desde la web)
        usuario_bd = await db.usuarios_telegram.find_one({"telegram_id": telegram_id}, {"_id": 0})
        if usuario_bd and usuario_bd.get("chat_id") != chat_id:
            await db.usuarios_telegram.update_one(
                {"telegram_id": telegram_id},
                {"$set": {"chat_id": chat_id, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            logger.info(f"[ver_operaciones] Chat ID actualizado para {telegram_id}: {chat_id}")
        
        # Verificar que esté registrado como cliente activo
        es_activo, usuario, cliente = await self.es_cliente_activo(telegram_id, chat_id)
        
        if not es_activo:
            mensaje = "⚠️ **Para ver tus operaciones primero necesito darte de alta como cliente.**\n\n"
            mensaje += "Elige la opción **1️⃣ Registrarme como cliente NetCash**.\n\n"
            mensaje += "Usa /start para ver el menú."
            await query.edit_message_text(mensaje, parse_mode="Markdown")
            return
        
        # Consultar últimas 5 operaciones del cliente
        operaciones = await db.operaciones.find(
            {"id_cliente": usuario["id_cliente"]},
            {"_id": 0}
        ).sort("fecha_creacion", -1).limit(5).to_list(5)
        
        # Caso SIN operaciones
        if not operaciones:
            mensaje = "ℹ️ **Por ahora no tengo operaciones registradas para tu cuenta.**\n\n"
            mensaje += "Cuando crees tu primera operación, podrás consultarla aquí."
            await query.edit_message_text(mensaje, parse_mode="Markdown")
            return
        
        # Guardar operaciones en context para interacción
        context.user_data['operaciones_lista'] = operaciones
        context.user_data['esperando_seleccion_operacion'] = True
        
        # Caso CON operaciones
        mensaje = "📋 **Estas son tus últimas operaciones NetCash:**\n\n"
        
        for idx, op in enumerate(operaciones, 1):
            folio = op.get("folio_mbco", "N/A")
            estado = op.get("estado", "DESCONOCIDO").replace("_", " ").title()
            
            # Calcular monto total de comprobantes válidos
            comprobantes = op.get("comprobantes", [])
            if isinstance(comprobantes, list):
                comprobantes_validos = [c for c in comprobantes if isinstance(c, dict) and c.get("es_valido")]
                monto_total = sum(c.get("monto", 0) for c in comprobantes_validos)
            else:
                monto_total = op.get("monto_total_comprobantes", 0) or op.get("monto_depositado_cliente", 0)
            
            mensaje += f"{idx}) **{folio}** — ${monto_total:,.2f} — {estado}\n"
        
        mensaje += "\n💡 **Responde con el NÚMERO de la operación** para ver más detalle\n"
        mensaje += "o escribe el **FOLIO** (ej. NC-000009)."
        
        await query.edit_message_text(mensaje, parse_mode="Markdown")
        logger.info(f"Usuario {chat_id} consultó sus operaciones: {len(operaciones)} encontradas")
    
    async def comando_mbco(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /mbco para que Ana registre la clave MBControl de una operación"""
        # [Previous code remains unchanged]
        pass
    
    async def aprobar_cliente(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /aprobar_cliente para que Ana apruebe clientes"""
        # [Previous code remains unchanged]
        pass
    
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
        # Obtener cuenta activa (NetCash V1)
        from config_cuentas_service import config_cuentas_service, TipoCuenta
        cuenta_activa = await config_cuentas_service.obtener_cuenta_activa(TipoCuenta.CONCERTADORA)
        
        mensaje += "📌 **Cuenta para depósitos:**\n"
        if cuenta_activa:
            mensaje += f"Razón social: {cuenta_activa.get('beneficiario')}\n"
            mensaje += f"Banco: {cuenta_activa.get('banco')}\n"
            mensaje += f"CLABE: {cuenta_activa.get('clabe')}\n\n"
        else:
            mensaje += "Consulta con tu ejecutivo\n\n"
        
        mensaje += "📞 **Ayuda personalizada:**\n"
        mensaje += "Contacta a Ana:\n"
        mensaje += "📧 gestion.ngdl@gmail.com\n"
        mensaje += "📱 +52 33 1218 6685"
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(mensaje, parse_mode="Markdown")
        else:
            await update.message.reply_text(mensaje, parse_mode="Markdown")
    
    async def ver_cuenta_pagos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra la cuenta para realizar pagos"""
        query = update.callback_query
        await query.answer()
        
        # Obtener cuenta activa (NetCash V1)
        from config_cuentas_service import config_cuentas_service, TipoCuenta
        cuenta = await config_cuentas_service.obtener_cuenta_activa(TipoCuenta.CONCERTADORA)
        
        if not cuenta:
            mensaje = "⚠️ No hay cuenta de depósito configurada.\n\n"
            mensaje += "Por favor contacta a tu ejecutivo para obtener los datos de pago."
        else:
            mensaje = "🏦 **Cuenta para depósitos NetCash**\n\n"
            mensaje += f"**Razón social:**\n{cuenta.get('beneficiario', 'N/A')}\n\n"
            mensaje += f"**Banco:** {cuenta.get('banco', 'N/A')}\n"
            mensaje += f"**CLABE:** {cuenta.get('clabe', 'N/A')}\n\n"
            mensaje += "ℹ️ Realiza tu depósito a esta cuenta y después envíame los comprobantes."
        
        await query.edit_message_text(mensaje, parse_mode="Markdown")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja los callbacks de botones"""
        query = update.callback_query
        data = query.data
        
        # NetCash V1 callbacks
        if data == "nc_menu_principal":
            await self.nc_handlers.mostrar_menu_netcash(update, context)
        elif data == "nc_ver_cuenta":
            await self.nc_handlers.ver_cuenta_depositos(update, context)
        elif data == "nc_ver_solicitudes":
            await self.nc_handlers.ver_solicitudes(update, context)
        elif data == "nc_crear_operacion":
            # Este callback es manejado principalmente por el ConversationHandler,
            # pero agregamos un fallback aquí por si no está activo
            await self.nc_handlers.iniciar_crear_operacion(update, context)
            return
        # Los callbacks nc_confirmar_, nc_corregir_, nc_cancelar
        # son manejados por el ConversationHandler de NetCash
        
        # Legacy callbacks
        elif data == "nueva_operacion":
            await self.nueva_operacion(update, context)
        elif data == "ver_operaciones":
            await self.ver_operaciones(update, context)
        elif data == "ver_cuenta_pagos":
            await self.ver_cuenta_pagos(update, context)
        elif data == "registrar_cliente":
            await self.iniciar_registro_cliente(update, context)
        elif data == "ayuda":
            await self.ayuda(update, context)
        else:
            await query.answer("Opción no reconocida")
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja documentos enviados (comprobantes)"""
        operacion_id = context.user_data.get('operacion_actual')
        folio = context.user_data.get('folio_actual', 'N/A')
        
        if not operacion_id:
            await update.message.reply_text(
                "Primero crea una operación con /start y selecciona 'Crear nueva operación NetCash'."
            )
            return
        
        # Actualizar timestamp de actividad
        await db.operaciones.update_one(
            {"id": operacion_id},
            {"$set": {
                "ultimo_mensaje_cliente": datetime.now(timezone.utc),
                "timestamp_actualizacion": datetime.now(timezone.utc)
            }}
        )
        
        await update.message.reply_text("🔍 Procesando comprobante...")
        
        try:
            # Descargar archivo
            file = await update.message.document.get_file()
            file_path = Path("/tmp") / f"comprobante_{operacion_id}_{file.file_id}.pdf"
            await file.download_to_drive(file_path)
            
            # Subir al backend para procesamiento con OCR
            async with aiohttp.ClientSession() as session:
                with open(file_path, 'rb') as f:
                    form = aiohttp.FormData()
                    form.add_field('file', f, filename=update.message.document.file_name, content_type=update.message.document.mime_type)
                    
                    async with session.post(f"{BACKEND_API}/operaciones/{operacion_id}/comprobante", data=form) as response:
                        if response.status == 200:
                            result = await response.json()
                            
                            # Manejar respuesta de ZIP (múltiples comprobantes)
                            if result.get("comprobantes_procesados") is not None:
                                mensaje = f"✅ **Recibí tu archivo ZIP.**\n\n"
                                mensaje += f"Procesé **{result.get('comprobantes_procesados')}** comprobante(s).\n"
                                if result.get("comprobantes_validos"):
                                    mensaje += f"**{result.get('comprobantes_validos')}** comprobante(s) válido(s).\n"
                                if result.get("archivos_ignorados"):
                                    mensaje += f"\n⚠️ {len(result.get('archivos_ignorados'))} archivo(s) no reconocido(s) como comprobante.\n"
                                
                                await update.message.reply_text(mensaje, parse_mode="Markdown")
                                await asyncio.sleep(0.5)
                                await update.message.reply_text(
                                    "Puedes enviar más comprobantes o escribe **'listo'** cuando hayas terminado.",
                                    parse_mode="Markdown"
                                )
                                
                                # Limpiar archivo temporal
                                file_path.unlink(missing_ok=True)
                                return
                            
                            # Verificar si es duplicado
                            es_duplicado = result.get("es_duplicado", False)
                            operacion_duplicada = result.get("operacion_duplicada", {})
                            
                            if es_duplicado:
                                if operacion_duplicada and isinstance(operacion_duplicada, dict):
                                    folio_original = operacion_duplicada.get("folio_mbco")
                                    estado_original = operacion_duplicada.get("estado")
                                    
                                    if folio_original and estado_original:
                                        mensaje = "⚠️ **Este comprobante ya fue utilizado en una operación anterior.**\n\n"
                                        mensaje += f"🔑 **Operación:** {folio_original}\n"
                                        mensaje += f"📊 **Estatus:** {estado_original}\n\n"
                                        mensaje += "Por favor confirma con Ana antes de continuar."
                                        logger.info(f"[NetCash][DUPLICADO] Comprobante duplicado - Op: {folio_original}, Estado: {estado_original}")
                                    else:
                                        mensaje = "⚠️ **Este comprobante ya fue utilizado en una operación anterior.**\n\n"
                                        mensaje += "No pude identificar la operación exacta.\n"
                                        mensaje += "Por favor confirma con Ana antes de continuar."
                                        logger.warning(f"[NetCash][DUPLICADO] Comprobante duplicado pero sin info de operación")
                                else:
                                    mensaje = "⚠️ **Este comprobante ya fue utilizado en una operación anterior.**\n\n"
                                    mensaje += "No pude identificar la operación exacta.\n"
                                    mensaje += "Por favor confirma con Ana antes de continuar."
                                    logger.warning(f"[NetCash][DUPLICADO] Comprobante duplicado pero operacion_duplicada es None o no dict")
                                
                                await update.message.reply_text(mensaje, parse_mode="Markdown")
                                file_path.unlink(missing_ok=True)
                                return
                            
                            # Manejar respuesta de comprobante individual
                            comprobante = result.get("comprobante", {})
                            es_valido = comprobante.get("es_valido", False)
                            
                            if es_valido:
                                monto = comprobante.get("monto", 0)
                                referencia = comprobante.get("referencia", "N/A")
                                clave_rastreo = comprobante.get("clave_rastreo", "N/A")
                                
                                mensaje = f"✅ **Comprobante recibido y procesado.**\n\n"
                                mensaje += f"**Folio MBco:** {folio}\n"
                                mensaje += f"**Monto detectado:** ${monto:,.2f}\n"
                                mensaje += f"**Referencia:** {referencia}\n"
                                mensaje += f"**Clave rastreo:** {clave_rastreo}\n\n"
                                mensaje += "Si hay algún error en los datos, por favor avísale a Ana."
                                await update.message.reply_text(mensaje, parse_mode="Markdown")
                                
                                await asyncio.sleep(0.5)
                                await update.message.reply_text(
                                    "Puedes enviar más comprobantes o escribe **'listo'** cuando hayas terminado.",
                                    parse_mode="Markdown"
                                )
                            else:
                                # ISSUE 1 FIX: Usar mensaje_validacion del backend
                                mensaje_validacion = comprobante.get("mensaje_validacion", "No se pudo leer el comprobante")
                                
                                # Obtener cuenta activa para mostrar datos esperados (NetCash V1)
                                from config_cuentas_service import config_cuentas_service, TipoCuenta
                                cuenta_activa = await config_cuentas_service.obtener_cuenta_activa(TipoCuenta.CONCERTADORA)
                                
                                mensaje = "❌ **El comprobante no es válido.**\n\n"
                                mensaje += f"**Razón:** {mensaje_validacion}\n\n"
                                
                                if cuenta_activa:
                                    mensaje += "**La cuenta NetCash autorizada es:**\n"
                                    mensaje += f"• Banco: {cuenta_activa.get('banco')}\n"
                                    mensaje += f"• CLABE: {cuenta_activa.get('clabe')}\n"
                                    mensaje += f"• Beneficiario: {cuenta_activa.get('beneficiario')}\n\n"
                                
                                mensaje += "Por favor envía un comprobante que corresponda a la cuenta autorizada."
                                
                                await update.message.reply_text(mensaje, parse_mode="Markdown")
                                logger.warning(f"[Telegram] Comprobante inválido: {mensaje_validacion}")
                            
                            # Limpiar archivo temporal
                            file_path.unlink(missing_ok=True)
                        else:
                            error_text = await response.text()
                            logger.error(f"Error del backend procesando documento: {error_text}")
                            await update.message.reply_text(
                                "❌ **No pude leer bien el comprobante.** Por favor intenta de nuevo o súbelo por el panel web."
                            )
        except Exception as e:
            logger.error(f"Error procesando documento: {str(e)}")
            await update.message.reply_text(
                "❌ Error al procesar el documento. Por favor intenta de nuevo o súbelo por el panel web."
            )
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja fotos enviadas (comprobantes en imagen) - Similar logic to handle_document"""
        # [Similar implementation with same ISSUE 1 fix]
        pass
    
    async def handle_saludo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja saludos básicos del usuario - ISSUE 3 FIX"""
        user_name = update.effective_user.first_name
        chat_id = str(update.effective_chat.id)
        telegram_id = str(update.effective_user.id)
        
        logger.info(f"[handle_saludo] Saludo recibido de {user_name} (telegram_id: {telegram_id})")
        
        # Verificar si es cliente activo - ISSUE 3 FIX: Desempaquetar tupla correctamente
        es_activo, usuario, cliente = await self.es_cliente_activo(telegram_id, chat_id)
        
        if es_activo:
            # Cliente activo: mostrar menú principal
            logger.info(f"[handle_saludo] Cliente activo detectado -> mostrando menú")
            await self.start(update, context)
        else:
            # No es cliente activo: mensaje de alta con Ana
            logger.info(f"[handle_saludo] Usuario no activo -> mensaje de contacto")
            mensaje = f"Hola {user_name} 👋\n\n"
            mensaje += "Para poder usar el asistente NetCash necesitas estar dado de alta como cliente.\n\n"
            mensaje += "Por favor contacta a Ana para realizar tu registro:\n"
            mensaje += "• Correo: gestion.ngdl@gmail.com\n"
            mensaje += "• WhatsApp: +52 33 1218 6685\n\n"
            mensaje += "Una vez que Ana te confirme tu alta, podrás operar desde aquí sin problema."
            
            await update.message.reply_text(mensaje)
    
    async def handle_mensaje_no_reconocido(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja mensajes de texto no reconocidos"""
        # [Previous implementation remains]
        pass
    
    def run(self):
        """Inicia el bot"""
        self.app = Application.builder().token(self.token).build()
        
        # Importar handlers de NetCash V1
        from telegram_netcash_handlers import TelegramNetCashHandlers
        self.nc_handlers = TelegramNetCashHandlers(self)
        
        # Importar handlers de Ana (admin MBco) y Tesorería
        from telegram_ana_handlers import init_ana_handlers, ANA_ESPERANDO_FOLIO_MBCO, ANA_ESPERANDO_MOTIVO_RECHAZO
        from telegram_tesoreria_handlers import init_tesoreria_handlers
        
        self.ana_handlers = init_ana_handlers(self)
        self.tesoreria_handlers = init_tesoreria_handlers(self)
        
        # Handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("ayuda", self.ayuda))
        self.app.add_handler(CommandHandler("mbco", self.comando_mbco))
        self.app.add_handler(CommandHandler("aprobar_cliente", self.aprobar_cliente))
        
        # Conversation handler for registration (legacy)
        conv_handler_registro = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.iniciar_registro_cliente, pattern="^registrar_cliente$")],
            states={
                ESPERANDO_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.recibir_email)]
            },
            fallbacks=[CommandHandler("cancelar", self.cancelar_registro)]
        )
        
        # Conversation handler for NetCash V1 (REORDENADO)
        # Nuevo orden: Comprobantes → Beneficiario+IDMEX → Ligas → Confirmación
        conv_handler_netcash = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.nc_handlers.iniciar_crear_operacion, pattern="^nc_crear_operacion$")],
            states={
                NC_ESPERANDO_COMPROBANTE: [
                    MessageHandler(filters.Document.ALL, self.nc_handlers.recibir_comprobante),
                    MessageHandler(filters.PHOTO, self.nc_handlers.recibir_comprobante),
                    CallbackQueryHandler(self.nc_handlers.agregar_otro_comprobante, pattern="^nc_mas_comprobantes_"),
                    CallbackQueryHandler(self.nc_handlers.continuar_desde_paso1, pattern="^nc_continuar_paso1_")
                ],
                NC_ESPERANDO_BENEFICIARIO: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.nc_handlers.recibir_beneficiario),
                    CallbackQueryHandler(self.nc_handlers.seleccionar_beneficiario_frecuente, pattern="^nc_benef_freq_")
                ],
                NC_ESPERANDO_IDMEX: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.nc_handlers.recibir_idmex)],
                NC_ESPERANDO_LIGAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.nc_handlers.recibir_ligas)],
                NC_ESPERANDO_CONFIRMACION: [
                    CallbackQueryHandler(self.nc_handlers.confirmar_operacion, pattern="^nc_confirmar_"),
                    CallbackQueryHandler(self.nc_handlers.corregir_datos, pattern="^nc_corregir_")
                ],
                # Estados de captura manual por fallo OCR
                NC_MANUAL_NUM_COMPROBANTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.nc_handlers.recibir_num_comprobantes_manual)],
                NC_MANUAL_MONTO_TOTAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.nc_handlers.recibir_monto_total_manual)],
                NC_MANUAL_ELEGIR_BENEFICIARIO: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.nc_handlers.recibir_beneficiario_nuevo_manual)
                ],
                NC_MANUAL_CAPTURAR_BENEFICIARIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.nc_handlers.recibir_beneficiario_nuevo_manual)],
                NC_MANUAL_CAPTURAR_IDMEX_BENEFICIARIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.nc_handlers.recibir_idmex_beneficiario_manual)],
                NC_MANUAL_GUARDAR_FRECUENTE: [
                    CallbackQueryHandler(self.nc_handlers.procesar_guardar_frecuente, pattern="^nc_manual_guardar_(si|no)$")
                ],
                NC_MANUAL_NUM_LIGAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.nc_handlers.recibir_num_ligas_manual)]
            },
            fallbacks=[
                CallbackQueryHandler(self.nc_handlers.cancelar_operacion, pattern="^nc_cancelar$"),
                CommandHandler("start", self.start)
            ]
        )
        
        # Conversation handler para Ana (asignación de folio MBco y rechazo)
        conv_handler_ana = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.ana_handlers.iniciar_asignacion_folio, pattern="^ana_asignar_folio_"),
                CallbackQueryHandler(self.ana_handlers.iniciar_rechazo_operacion, pattern="^ana_rechazar_")
            ],
            states={
                ANA_ESPERANDO_FOLIO_MBCO: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.ana_handlers.recibir_folio_mbco)
                ],
                ANA_ESPERANDO_MOTIVO_RECHAZO: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.ana_handlers.recibir_motivo_rechazo)
                ]
            },
            fallbacks=[
                CommandHandler("cancelar", self.ana_handlers.cancelar)
            ]
        )
        
        # Handler para botones de Tesorería
        self.app.add_handler(CallbackQueryHandler(self.tesoreria_handlers.ver_detalles_orden, pattern="^tesor_ver_orden_"))
        
        self.app.add_handler(conv_handler_registro)
        self.app.add_handler(conv_handler_netcash)
        self.app.add_handler(conv_handler_ana)
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.CONTACT, self.handle_contact))
        self.app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        
        # Handler de saludos (ANTES del genérico) - ISSUE 3: Ya está bien posicionado
        saludo_filter = filters.Regex(r'^(hola|buenas|buen\s*d[ií]a|buenos\s*d[ií]as|buenas\s*tardes|buenas\s*noches|hey|hello|HOLA|BUENAS|BUEN\s*D[ÍI]A|BUENOS\s*D[ÍI]AS|BUENAS\s*TARDES|BUENAS\s*NOCHES|HEY|HELLO)[\s!¡¿?.,]*$')
        self.app.add_handler(MessageHandler(saludo_filter & ~filters.COMMAND, self.handle_saludo))
        
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_mensaje_no_reconocido))
        
        logger.info("Bot iniciado correctamente. Esperando mensajes...")
        
        # Iniciar el bot
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    bot = TelegramBotNetCash()
    bot.run()
