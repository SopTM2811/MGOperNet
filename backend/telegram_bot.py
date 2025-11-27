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
# Estados para flujo de operación extendido
ESPERANDO_MAS_COMPROBANTES, ESPERANDO_CANTIDAD_LIGAS, ESPERANDO_NOMBRE_LIGAS, ESPERANDO_IDMEX = range(10, 14)

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
            mensaje = f"🆕 **Nuevo cliente creado desde Telegram (pendiente de validación)**\n\n"
            mensaje += f"**Nombre:** {cliente.get('nombre')}\n"
            mensaje += f"**Teléfono:** {cliente.get('telefono_completo')}\n"
            mensaje += f"**Email:** {cliente.get('email') or 'No proporcionado'}\n"
            mensaje += f"**Cliente ID:** `{cliente.get('id')}`\n"
            mensaje += f"**Estado:** Pendiente de validación\n"
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
            # Cliente registrado - verificar estado
            cliente = await db.clientes.find_one({"id": id_cliente}, {"_id": 0})
            
            if cliente and cliente.get("estado") == "activo":
                # Cliente ACTIVO - mensaje personalizado
                mensaje = f"Hola {user.first_name} 😊\n\n"
                mensaje += "Ya estás dado de alta como cliente NetCash.\n\n"
                mensaje += "Puedo ayudarte a:\n"
                mensaje += "• Crear una nueva operación NetCash\n"
                mensaje += "• Ver el estado de tus operaciones\n"
                mensaje += "• Ver la cuenta para hacer tus pagos\n"
                
                keyboard = [
                    [InlineKeyboardButton("📎 Crear nueva operación NetCash", callback_data="nueva_operacion")],
                    [InlineKeyboardButton("📊 Ver mis operaciones", callback_data="ver_operaciones")],
                    [InlineKeyboardButton("🏦 Ver cuenta para pagos", callback_data="ver_cuenta_pagos")],
                    [InlineKeyboardButton("❓ Ayuda", callback_data="ayuda")]
                ]
            else:
                # Cliente pendiente de validación
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
            # Usuario sin cliente registrado - ofrecer registro
            mensaje = f"Hola {user.first_name} 😊\n\n"
            mensaje += "¡Bienvenido a NetCash MBco! 🎉\n\n"
            mensaje += "Para comenzar, necesito registrarte como cliente.\n"
            
            keyboard = [
                [InlineKeyboardButton("1️⃣ Registrarme como cliente NetCash", callback_data="registrar_cliente")],
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
        
        # VALIDAR ESTADO DEL CLIENTE (BLOQUE 1)
        if cliente.get("estado") != "activo":
            mensaje = "⚠️ **Tu alta como cliente NetCash está en revisión.**\n\n"
            mensaje += "Ana debe validar tus datos antes de que puedas crear operaciones.\n\n"
            mensaje += "En cuanto estés **ACTIVO** te avisaremos y ya podrás mandar tus comprobantes."
            await query.edit_message_text(mensaje, parse_mode="Markdown")
            logger.info(f"Cliente {cliente['id']} intentó crear operación con estado: {cliente.get('estado')}")
            return
        
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
                        mensaje += f"**Recuerda:** El depósito debe ser a la cuenta:\n"
                        mensaje += f"JARDINERIA Y COMERCIO THABYETHA SA DE CV\n"
                        mensaje += f"CLABE: 646180139409481462"
                        
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
        
        # Verificar si está vinculado a un cliente
        usuario = await db.usuarios_telegram.find_one({"chat_id": chat_id}, {"_id": 0})
        
        if not usuario or not usuario.get("id_cliente"):
            mensaje = "⚠️ **Aún no encuentro un cliente vinculado a tu número.**\n\n"
            mensaje += "Primero necesito darte de alta como cliente NetCash.\n"
            mensaje += "Elige la opción **'Registrarme como cliente NetCash'** en el menú."
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
        """
        Comando /mbco para que Ana registre la clave MBControl de una operación
        Formato: /mbco NC-000016 MBC-2025-00089
        """
        from_user_id = update.effective_user.id
        from_user_name = update.effective_user.first_name
        mensaje_texto = update.message.text
        
        logger.info(f"[NetCash][MBCO] Comando /mbco recibido")
        logger.info(f"[NetCash][MBCO] from_user.id = {from_user_id}, text = '{mensaje_texto}'")
        
        # Obtener ANA_TELEGRAM_CHAT_ID del env
        ana_chat_id_env = self.ana_telegram_id
        ana_id_int = int(ana_chat_id_env) if ana_chat_id_env else None
        
        # Verificar permisos: Ana por chat_id O admin_mbco por rol
        chat_id = str(update.effective_chat.id)
        usuario = await db.usuarios_telegram.find_one({"chat_id": chat_id}, {"_id": 0})
        
        is_ana_by_chatid = (ana_id_int and from_user_id == ana_id_int)
        is_admin_mbco = (usuario and usuario.get("rol") == "admin_mbco")
        
        logger.info(f"[NetCash][MBCO] is_ana_by_chatid={is_ana_by_chatid}, is_admin_mbco={is_admin_mbco}")
        
        if not (is_ana_by_chatid or is_admin_mbco):
            logger.warning(f"[NetCash][MBCO] Usuario {from_user_name} (ID {from_user_id}) sin permisos para /mbco")
            await update.message.reply_text(
                "⛔ Este comando solo puede usarlo Ana / admin_mbco.\n"
                "Si necesitas ayuda, contacta a Ana."
            )
            return
        
        # Parsear parámetros: /mbco NC-000016 MBC-2025-00089
        # maxsplit=2 permite que la clave MBControl tenga espacios si fuera necesario
        try:
            partes = mensaje_texto.split(maxsplit=2)
            
            if len(partes) < 3:
                mensaje = "⚠️ **Formato incorrecto.**\n\n"
                mensaje += "**Usa:** `/mbco CLAVE_NETCASH CLAVE_MBCO`\n\n"
                mensaje += "**Ejemplo:** `/mbco NC-000016 MBC-2025-00089`\n\n"
                mensaje += "Esto registrará la clave MBControl para esa operación."
                await update.message.reply_text(mensaje, parse_mode="Markdown")
                return
            
            _, clave_netcash, clave_mbco = partes
            clave_netcash = clave_netcash.strip()
            clave_mbco = clave_mbco.strip()
            
            # Buscar operación por folio NetCash
            operacion = await db.operaciones.find_one({"folio_mbco": clave_netcash}, {"_id": 0})
            
            if not operacion:
                await update.message.reply_text(
                    f"❌ No encontré ninguna operación con la clave NetCash `{clave_netcash}`.",
                    parse_mode="Markdown"
                )
                return
            
            operacion_id = operacion.get("id")
            
            logger.info(f"[NetCash][MBCO] Guardando clave '{clave_mbco}' para operación {clave_netcash} (ID: {operacion_id})")
            
            # Guardar clave MBControl directamente en la operación
            resultado = await db.operaciones.update_one(
                {"id": operacion_id},
                {
                    "$set": {
                        "clave_operacion_mbcontrol": clave_mbco,
                        "estado": "CON_CLAVE_MBCO",
                        "timestamp_mbcontrol": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            
            logger.info(f"[NetCash][MBCO] Update result: matched={resultado.matched_count}, modified={resultado.modified_count}")
            logger.info(f"[NetCash][MBCO] Clave '{clave_mbco}' guardada exitosamente para {clave_netcash}")
            
            # Confirmar a Ana
            mensaje = "✅ **Clave MBco registrada correctamente.**\n\n"
            mensaje += f"🔑 **NetCash:** `{clave_netcash}`\n"
            mensaje += f"🔐 **MBControl:** `{clave_mbco}`\n\n"
            mensaje += f"🆔 **ID interno:** {operacion_id}\n"
            mensaje += f"👤 **Cliente:** {operacion.get('cliente_nombre', 'N/A')}\n"
            mensaje += f"💵 **Monto:** ${operacion.get('monto_total_comprobantes', 0):,.2f}"
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
            logger.info(f"[NetCash][MBCO] Confirmación enviada a Ana")
            
        except Exception as e:
            logger.error(f"Error en comando /mbco: {str(e)}")
            await update.message.reply_text(
                "❌ Ocurrió un error al guardar la clave MBco.\n"
                "Verifica el formato:\n"
                "`/mbco CLAVE_NETCASH CLAVE_MBCO`",
                parse_mode="Markdown"
            )
    
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
    
    async def ver_cuenta_pagos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra la cuenta para realizar pagos"""
        query = update.callback_query
        await query.answer()
        
        mensaje = "🏦 **Cuenta para depósitos NetCash**\n\n"
        mensaje += "**Razón social:**\n"
        mensaje += "JARDINERIA Y COMERCIO THABYETHA SA DE CV\n\n"
        mensaje += "**Banco:** STP\n"
        mensaje += "**CLABE:** 646180139409481462\n\n"
        mensaje += "ℹ️ Realiza tu depósito a esta cuenta y después envíame los comprobantes."
        
        await query.edit_message_text(mensaje, parse_mode="Markdown")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja los callbacks de botones"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "nueva_operacion":
            await self.nueva_operacion(update, context)
        elif query.data == "ver_operaciones":
            await self.ver_operaciones(update, context)
        elif query.data == "ver_cuenta_pagos":
            await self.ver_cuenta_pagos(update, context)
        elif query.data == "ayuda":
            await self.ayuda(update, context)
    
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
                            
                            # Manejar respuesta de comprobante individual
                            comprobante = result.get("comprobante", {})
                            
                            if comprobante.get("es_duplicado"):
                                mensaje = "⚠️ **Este comprobante parece estar duplicado de una operación anterior.**\n\n"
                                mensaje += "Por favor confirma con Ana antes de continuar."
                                await update.message.reply_text(mensaje, parse_mode="Markdown")
                            elif comprobante.get("es_valido"):
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
                                
                                # BLOQUE 1: NO preguntar por más comprobantes, esperar "listo"
                                await asyncio.sleep(0.5)
                                await update.message.reply_text(
                                    "Puedes enviar más comprobantes o escribe **'listo'** cuando hayas terminado.",
                                    parse_mode="Markdown"
                                )
                            else:
                                mensaje = "⚠️ **No pude leer bien el comprobante.**\n\n"
                                mensaje += "Intenta enviarlo de nuevo con mejor calidad o súbelo por el panel web."
                                await update.message.reply_text(mensaje, parse_mode="Markdown")
                            
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
        """Maneja fotos enviadas (comprobantes en imagen)"""
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
            # Descargar foto (la de mayor resolución)
            photo = update.message.photo[-1]
            file = await photo.get_file()
            file_path = Path("/tmp") / f"comprobante_{operacion_id}_{file.file_id}.jpg"
            await file.download_to_drive(file_path)
            
            # Subir al backend para procesamiento con OCR
            async with aiohttp.ClientSession() as session:
                with open(file_path, 'rb') as f:
                    form = aiohttp.FormData()
                    form.add_field('file', f, filename=f"comprobante_{operacion_id}.jpg", content_type='image/jpeg')
                    
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
                            
                            # Manejar respuesta de comprobante individual
                            comprobante = result.get("comprobante", {})
                            
                            if comprobante.get("es_duplicado"):
                                mensaje = "⚠️ **Este comprobante parece estar duplicado de una operación anterior.**\n\n"
                                mensaje += "Por favor confirma con Ana antes de continuar."
                                await update.message.reply_text(mensaje, parse_mode="Markdown")
                            elif comprobante.get("es_valido"):
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
                                
                                # BLOQUE 1: NO preguntar por más comprobantes, esperar "listo"
                                await asyncio.sleep(0.5)
                                await update.message.reply_text(
                                    "Puedes enviar más comprobantes o escribe **'listo'** cuando hayas terminado.",
                                    parse_mode="Markdown"
                                )
                            else:
                                mensaje = "⚠️ **No pude leer bien el comprobante.**\n\n"
                                mensaje += "Intenta enviarlo de nuevo con mejor calidad o súbelo por el panel web."
                                await update.message.reply_text(mensaje, parse_mode="Markdown")
                            
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
    
    async def handle_mensaje_no_reconocido(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja mensajes de texto no reconocidos y flujo extendido de operación (BLOQUES 1, 2, 3)"""
        texto = update.message.text.strip()
        user_name = update.effective_user.first_name
        
        # Actualizar timestamp de último mensaje si hay operación en curso
        if context.user_data.get('operacion_actual'):
            operacion_id = context.user_data['operacion_actual']
            await db.operaciones.update_one(
                {"id": operacion_id},
                {"$set": {
                    "ultimo_mensaje_cliente": datetime.now(timezone.utc),
                    "timestamp_actualizacion": datetime.now(timezone.utc)
                }}
            )
        
        # ⚡ PRIORIDAD 1: Detectar sinónimos de "listo" ANTES de otros handlers
        if context.user_data.get('recibiendo_comprobantes'):
            import unicodedata
            texto_lower = texto.lower().strip()
            texto_normalizado = ''.join(
                c for c in unicodedata.normalize('NFD', texto_lower)
                if unicodedata.category(c) != 'Mn'
            )
            
            palabras_cierre = [
                'listo', 'lista', 'ya quedo', 'ya quede', 'ya esta', 'ya estas',
                'ok', 'de acuerdo', 'terminado', 'termine', 'termino',
                'eso es todo', 'ya', 'vale', 'perfecto', 'ya termine',
                'ya termino', 'es todo'
            ]
            
            if texto_normalizado in palabras_cierre:
                logger.info(f"Sinónimo detectado: '{texto}' → cerrando comprobantes")
                await self.cerrar_comprobantes_y_continuar(update, context)
                return
        
        # Convertir a lowercase para comparaciones posteriores
        texto_lower = texto.lower()
        
        # Manejo de selección de operación
        if context.user_data.get('esperando_seleccion_operacion'):
            operaciones_lista = context.user_data.get('operaciones_lista', [])
            
            # Verificar si es un número (índice)
            if texto_lower.isdigit():
                idx = int(texto) - 1
                if 0 <= idx < len(operaciones_lista):
                    operacion = operaciones_lista[idx]
                    await self.mostrar_detalle_operacion(update, context, operacion)
                    context.user_data['esperando_seleccion_operacion'] = False
                    return
            
            # Verificar si es un folio (ej. NC-000009)
            if texto_lower.startswith('nc-'):
                chat_id = str(update.effective_chat.id)
                usuario = await db.usuarios_telegram.find_one({"chat_id": chat_id}, {"_id": 0})
                if usuario:
                    operacion = await db.operaciones.find_one(
                        {"folio_mbco": texto.upper(), "id_cliente": usuario.get("id_cliente")},
                        {"_id": 0}
                    )
                    if operacion:
                        await self.mostrar_detalle_operacion(update, context, operacion)
                        context.user_data['esperando_seleccion_operacion'] = False
                        return
            
            # No se encontró la operación
            await update.message.reply_text(
                "⚠️ No encontré esa operación. Por favor verifica el número o folio.\n"
                "Escribe /start para ver tus operaciones de nuevo."
            )
            context.user_data['esperando_seleccion_operacion'] = False
            return
        
        # BLOQUE 2: Captura de cantidad de ligas
        if context.user_data.get('esperando_cantidad_ligas'):
            try:
                cantidad = int(texto_lower)
                if cantidad < 1:
                    await update.message.reply_text("Por favor ingresa un número válido mayor a 0.")
                    return
                
                context.user_data['esperando_cantidad_ligas'] = False
                context.user_data['cantidad_ligas'] = cantidad
                context.user_data['esperando_nombre_ligas'] = True
                
                # Buscar beneficiarios frecuentes del cliente
                chat_id = str(update.effective_chat.id)
                usuario = await db.usuarios_telegram.find_one({"chat_id": chat_id}, {"_id": 0})
                
                beneficiarios_frecuentes = []
                if usuario and usuario.get('id_cliente'):
                    # Buscar operaciones previas del cliente con titular
                    operaciones_previas = await db.operaciones.find(
                        {
                            "id_cliente": usuario['id_cliente'],
                            "nombre_ligas": {"$exists": True, "$ne": None}
                        },
                        {"_id": 0, "nombre_ligas": 1, "titular_idmex": 1}
                    ).to_list(10)
                    
                    # Crear diccionario para evitar duplicados
                    beneficiarios_dict = {}
                    for op in operaciones_previas:
                        nombre = op.get('nombre_ligas', '').strip()
                        idmex = op.get('titular_idmex', '').strip()
                        if nombre and idmex:
                            key = f"{nombre}_{idmex}"
                            if key not in beneficiarios_dict:
                                beneficiarios_dict[key] = {"nombre": nombre, "idmex": idmex}
                    
                    beneficiarios_frecuentes = list(beneficiarios_dict.values())[:3]
                
                # BLOQUE 2: Mensaje adaptado singular/plural + beneficiarios frecuentes
                if cantidad == 1:
                    mensaje_ligas = "👤 Por favor dime el **nombre completo de la persona que va a cobrar la liga NetCash**.\n"
                else:
                    mensaje_ligas = "👤 Por favor dime el **nombre completo de la persona que va a cobrar las ligas NetCash**.\n"
                
                if beneficiarios_frecuentes:
                    mensaje_ligas += "\n📋 **Te recuerdo tus beneficiarios frecuentes:**\n"
                    for idx, benef in enumerate(beneficiarios_frecuentes, 1):
                        mensaje_ligas += f"{idx}) {benef['nombre']} — IDMEX {benef['idmex']}\n"
                    mensaje_ligas += "\nResponde con el **número** si quieres usar uno de ellos, o escribe un nombre nuevo.\n"
                    mensaje_ligas += "Recuerda: nombre y dos apellidos (mínimo 3 palabras)."
                    context.user_data['beneficiarios_frecuentes'] = beneficiarios_frecuentes
                else:
                    mensaje_ligas += "Escribe nombre y dos apellidos (mínimo 3 palabras)."
                    if cantidad > 1:
                        mensaje_ligas += "\nSi tienes varios beneficiarios, mándame el principal y coordina los demás con Ana."
                
                await update.message.reply_text(mensaje_ligas, parse_mode="Markdown")
                return
            except ValueError:
                await update.message.reply_text("Por favor responde solo con un número (ejemplo: 1, 2, 3...).")
                return
        
        if context.user_data.get('esperando_nombre_ligas'):
            respuesta = update.message.text.strip()
            
            # Verificar si el usuario respondió con un número (selección de beneficiario frecuente)
            if respuesta.isdigit() and context.user_data.get('beneficiarios_frecuentes'):
                idx = int(respuesta) - 1
                beneficiarios = context.user_data.get('beneficiarios_frecuentes', [])
                
                if 0 <= idx < len(beneficiarios):
                    # Usar beneficiario frecuente
                    beneficiario_seleccionado = beneficiarios[idx]
                    context.user_data['nombre_ligas'] = beneficiario_seleccionado['nombre']
                    context.user_data['titular_idmex_guardado'] = beneficiario_seleccionado['idmex']
                    context.user_data['esperando_nombre_ligas'] = False
                    context.user_data['esperando_idmex'] = False
                    
                    # Continuar con resumen
                    await self.finalizar_captura_operacion(update, context)
                    return
            
            # Validar que solo contenga letras y espacios (sin números)
            import re
            if re.search(r'\d', respuesta):
                await update.message.reply_text(
                    "⚠️ Veo números en el nombre.\n"
                    "Por favor envíame SOLO el nombre y dos apellidos (mínimo 3 palabras), sin el IDMEX."
                )
                return
            
            # Validar mínimo 3 palabras
            palabras = respuesta.split()
            if len(palabras) < 3:
                await update.message.reply_text(
                    "⚠️ El nombre debe tener al menos 3 palabras (nombre y dos apellidos).\n"
                    "Por favor envíalo completo."
                )
                return
            
            # Validar longitud razonable
            if len(respuesta) > 80:
                await update.message.reply_text(
                    "⚠️ El nombre es demasiado largo. Por favor verifica que sea correcto."
                )
                return
            
            context.user_data['esperando_nombre_ligas'] = False
            context.user_data['nombre_ligas'] = respuesta
            context.user_data['esperando_idmex'] = True
            
            # BLOQUE 2: Texto actualizado para IDMEX de INE
            await update.message.reply_text(
                "🆔 Ahora mándame el IDMEX de la INE de esa persona.\n"
                "Si son varios IDMEX, envíalos separados por coma."
            )
            return
        
        if context.user_data.get('esperando_idmex'):
            context.user_data['esperando_idmex'] = False
            idmex = update.message.text.strip()
            context.user_data['titular_idmex_guardado'] = idmex
            
            # Finalizar captura
            await self.finalizar_captura_operacion(update, context)
            return
    
    async def finalizar_captura_operacion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Finaliza la captura de operación y muestra resumen con desglose económico"""
        operacion_id = context.user_data.get('operacion_actual')
        folio = context.user_data.get('folio_actual', 'N/A')
        cantidad_ligas = context.user_data.get('cantidad_ligas')
        nombre_ligas = context.user_data.get('nombre_ligas')
        idmex = context.user_data.get('titular_idmex_guardado')
        
        try:
            # Actualizar operación en la base de datos
            await db.operaciones.update_one(
                {"id": operacion_id},
                {"$set": {
                    "cantidad_ligas": cantidad_ligas,
                    "nombre_ligas": nombre_ligas,
                    "titular_idmex": idmex
                }}
            )
            
            # Obtener operación actualizada para calcular desglose económico
            operacion = await db.operaciones.find_one({"id": operacion_id}, {"_id": 0})
            comprobantes_validos = [c for c in operacion.get("comprobantes", []) if c.get("es_valido")]
            monto_total = sum(c.get("monto", 0) for c in comprobantes_validos)
            cliente_nombre = operacion.get("cliente_nombre", "N/A")
            
            # Calcular desglose económico
            comision_porcentaje = operacion.get("porcentaje_comision_usado", 0.65)
            comision_cobrada = round(monto_total * (comision_porcentaje / 100), 2)
            capital_netcash = round(monto_total - comision_cobrada, 2)
            
            # Calcular costo proveedor DNS (0.375% del capital) - SOLO INTERNO
            costo_proveedor_pct = operacion.get("costo_proveedor_pct", 0.00375)
            costo_proveedor_monto = round(capital_netcash * costo_proveedor_pct, 2)
            utilidad_neta = round(comision_cobrada - costo_proveedor_monto, 2)
            
            # Guardar cálculos en la operación
            await db.operaciones.update_one(
                {"id": operacion_id},
                {"$set": {
                    "estado": "DATOS_COMPLETOS",
                    "monto_total_comprobantes": monto_total,
                    "comision_cobrada": comision_cobrada,
                    "capital_netcash": capital_netcash,
                    "costo_proveedor_monto": costo_proveedor_monto,
                    "utilidad_neta": utilidad_neta
                }}
            )
            
            # 🔔 NOTIFICAR A ANA de nueva operación lista
            operacion_actualizada = await db.operaciones.find_one({"id": operacion_id}, {"_id": 0})
            if operacion_actualizada:
                from notificaciones_ana import notificar_ana_telegram
                await notificar_ana_telegram(operacion_actualizada)
            
            # BLOQUE 6: Resumen con desglose económico
            mensaje = "📋 **Resumen de tu operación NetCash**\n\n"
            mensaje += f"**Folio MBco:** {folio}\n"
            mensaje += f"**Cliente:** {cliente_nombre}\n\n"
            mensaje += f"💵 **Total comprobantes:** ${monto_total:,.2f}\n"
            mensaje += f"📊 **Comisión cobrada al cliente ({comision_porcentaje}%):** ${comision_cobrada:,.2f}\n"
            mensaje += f"💰 **Capital NetCash (a dispersar):** ${capital_netcash:,.2f}\n\n"
            mensaje += f"**Cantidad de ligas:** {cantidad_ligas}\n"
            mensaje += f"**Nombre en ligas:** {nombre_ligas}\n"
            mensaje += f"**IDMEX:** {idmex}\n\n"
            mensaje += "Si hay algún error en estos datos, avísale a Ana para corregirlo.\n\n"
            mensaje += "✅ **Recibimos con éxito tu operación.**\n"
            mensaje += "Vamos a validar tus comprobantes y, cuando tus ligas NetCash estén listas, te avisaremos por este mismo chat.\n\n"
            mensaje += "Mientras tanto, puedes:\n"
            mensaje += "• Crear otra operación NetCash\n"
            mensaje += "• Ver tus operaciones en curso con \"Ver mis operaciones\" o /start."
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
            
            # Limpiar context
            context.user_data.clear()
            
            logger.info(f"Operación {operacion_id} completada con {len(comprobantes_validos)} comprobantes, {cantidad_ligas} ligas")
        except Exception as e:
            logger.error(f"Error guardando datos de operación: {str(e)}")
            await update.message.reply_text("Error al guardar los datos. Por favor contacta a Ana.")
            return
        
        # Mensaje por defecto para mensajes no reconocidos
        mensaje_respuesta = f"Hola, {user_name} 😊\n"
        mensaje_respuesta += "Soy el Asistente NetCash 🤖\n\n"
        mensaje_respuesta += "Puedo ayudarte a:\n"
        mensaje_respuesta += "• Registrarte como cliente NetCash\n"
        mensaje_respuesta += "• Crear una nueva operación\n"
        mensaje_respuesta += "• Dar seguimiento a tus operaciones\n\n"
        mensaje_respuesta += "👉 Escribe /start o usa el menú para comenzar."
        
        await update.message.reply_text(mensaje_respuesta)
    
    async def cerrar_comprobantes_y_continuar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """BLOQUE 1: Cierra la captura de comprobantes y continúa directamente a captura extendida"""
        operacion_id = context.user_data.get('operacion_actual')
        folio = context.user_data.get('folio_actual', 'N/A')
        
        # Obtener operación para calcular resumen
        operacion = await db.operaciones.find_one({"id": operacion_id}, {"_id": 0})
        if not operacion:
            await update.message.reply_text("Error: No se encontró la operación. Usa /start para comenzar de nuevo.")
            return
        
        comprobantes = operacion.get("comprobantes", [])
        comprobantes_validos = [c for c in comprobantes if isinstance(c, dict) and c.get("es_valido")]
        
        # Validar que haya al menos un comprobante válido
        if not comprobantes_validos:
            await update.message.reply_text(
                "⚠️ No has enviado ningún comprobante válido. Por favor envía al menos un comprobante antes de escribir 'listo'."
            )
            return
        
        monto_total = sum(c.get("monto", 0) for c in comprobantes_validos)
        
        # Actualizar estado de operación
        await db.operaciones.update_one(
            {"id": operacion_id},
            {
                "$set": {
                    "estado": "COMPROBANTES_CERRADOS",
                    "ultimo_mensaje_cliente": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Mostrar resumen y pasar directamente a captura extendida
        mensaje = f"✅ **Comprobantes recibidos correctamente**\n\n"
        mensaje += f"**Folio MBco:** {folio}\n"
        mensaje += f"**Comprobantes válidos:** {len(comprobantes_validos)}\n"
        mensaje += f"**Monto total:** ${monto_total:,.2f}\n\n"
        
        await update.message.reply_text(mensaje, parse_mode="Markdown")
        await asyncio.sleep(0.5)
        
        # Pasar directamente a solicitar cantidad de ligas (sin confirmación extra)
        context.user_data['recibiendo_comprobantes'] = False
        context.user_data['esperando_cantidad_ligas'] = True
        
        await update.message.reply_text(
            "🔗 ¿Cuántas ligas NetCash necesitas para esta operación?\n"
            "Responde solo con un número (ejemplo: 1, 2, 3...)."
        )
    
    async def mostrar_detalle_operacion(self, update: Update, context: ContextTypes.DEFAULT_TYPE, operacion: dict):
        """Muestra el detalle completo de una operación"""
        folio = operacion.get("folio_mbco", "N/A")
        estado = operacion.get("estado", "DESCONOCIDO").replace("_", " ").title()
        
        # Calcular montos
        comprobantes = operacion.get("comprobantes", [])
        comprobantes_validos = [c for c in comprobantes if isinstance(c, dict) and c.get("es_valido")]
        monto_total = operacion.get("monto_total_comprobantes") or sum(c.get("monto", 0) for c in comprobantes_validos)
        comision_cobrada = operacion.get("comision_cobrada", 0)
        capital_netcash = operacion.get("capital_netcash", 0)
        comision_porcentaje = operacion.get("porcentaje_comision_usado", 0.65)
        
        # Si no hay cálculos guardados, calcularlos
        if not comision_cobrada and monto_total:
            comision_cobrada = round(monto_total * (comision_porcentaje / 100), 2)
            capital_netcash = round(monto_total - comision_cobrada, 2)
        
        mensaje = f"📊 **Detalle de Operación {folio}**\n\n"
        mensaje += f"**Estado:** {estado}\n"
        mensaje += f"**Cliente:** {operacion.get('cliente_nombre', 'N/A')}\n\n"
        
        if monto_total > 0:
            mensaje += f"💵 **Total comprobantes:** ${monto_total:,.2f}\n"
            mensaje += f"📊 **Comisión ({comision_porcentaje}%):** ${comision_cobrada:,.2f}\n"
            mensaje += f"💰 **Capital NetCash:** ${capital_netcash:,.2f}\n\n"
        
        mensaje += f"**Comprobantes válidos:** {len(comprobantes_validos)}\n"
        
        if operacion.get("cantidad_ligas"):
            mensaje += f"**Cantidad de ligas:** {operacion.get('cantidad_ligas')}\n"
        if operacion.get("nombre_ligas"):
            mensaje += f"**Nombre en ligas:** {operacion.get('nombre_ligas')}\n"
        if operacion.get("titular_idmex"):
            mensaje += f"**IDMEX:** {operacion.get('titular_idmex')}\n"
        
        mensaje += "\nEscribe /start para ver el menú principal."
        
        await update.message.reply_text(mensaje, parse_mode="Markdown")
    
    async def notificar_cancelacion_por_inactividad(self, operacion_id: str, folio: str, chat_id: str):
        """Envía notificación al cliente cuando su operación es cancelada por inactividad"""
        try:
            mensaje = f"⏰ **Operación cancelada por inactividad**\n\n"
            mensaje += f"**Folio MBco:** {folio}\n\n"
            mensaje += "Tu operación fue cancelada automáticamente porque no recibimos actividad en los últimos 3 minutos.\n\n"
            mensaje += "Si aún necesitas crear esta operación, por favor:\n"
            mensaje += "• Escribe /start\n"
            mensaje += "• Selecciona 'Crear nueva operación NetCash'\n"
            mensaje += "• Envía tus comprobantes de forma continua"
            
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=mensaje,
                parse_mode="Markdown"
            )
            
            logger.info(f"Notificación de cancelación enviada para operación {operacion_id}")
        except Exception as e:
            logger.error(f"Error enviando notificación de cancelación: {str(e)}")
    
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
                ESPERANDO_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.recibir_email)],
            },
            fallbacks=[CommandHandler('start', self.start)],
        )
        
        # Agregar handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("ayuda", self.ayuda))
        self.app.add_handler(CommandHandler("mbco", self.comando_mbco))
        self.app.add_handler(conv_handler)
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.CONTACT, self.handle_contact))
        self.app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_mensaje_no_reconocido))
        
        logger.info("Bot iniciado correctamente. Esperando mensajes...")
        
        # Iniciar el bot
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    bot = TelegramBotNetCash()
    bot.run()
