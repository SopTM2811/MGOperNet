"""
API para gestión de usuarios de Telegram
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
import logging
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import aiohttp

load_dotenv()

logger = logging.getLogger(__name__)

# Router
router = APIRouter(prefix="/telegram", tags=["telegram"])

# MongoDB
mongo_client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
db = mongo_client[os.environ.get("DB_NAME", "netcash_mbco")]

# Token del bot
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")


class AltaClienteTelegramRequest(BaseModel):
    email: EmailStr
    nombre: str
    telegram_id: str
    comision_pct: float


@router.post("/alta_desde_web")
async def alta_cliente_telegram(data: AltaClienteTelegramRequest):
    """
    Endpoint para dar de alta un cliente desde la web, vinculando su Telegram ID
    y enviando mensaje de bienvenida por el bot
    """
    try:
        logger.info(f"[NetCash][AltaWeb] Iniciando alta - Email: {data.email}, TG ID: {data.telegram_id}")
        
        # Validar comisión mínima
        if data.comision_pct < 0.375:
            raise HTTPException(
                status_code=400,
                detail=f"La comisión no puede ser menor a 0.375%. Recibido: {data.comision_pct}%"
            )
        
        # 1. Buscar o crear cliente por email
        cliente = await db.clientes.find_one({"email": data.email}, {"_id": 0})
        
        if cliente:
            cliente_id = cliente.get("id")
            logger.info(f"[NetCash][AltaWeb] Cliente existente encontrado: {cliente_id}")
        else:
            # Crear cliente nuevo
            from uuid import uuid4
            cliente_id = str(uuid4())
            
            nuevo_cliente = {
                "id": cliente_id,
                "nombre": data.nombre,
                "email": data.email,
                "telegram_id": data.telegram_id,
                "porcentaje_comision_cliente": data.comision_pct,
                "estado": "activo",
                "fecha_creacion": datetime.now(timezone.utc).isoformat(),
                "fecha_aprobacion": datetime.now(timezone.utc).isoformat(),
                "notas": f"Cliente dado de alta desde web con comisión {data.comision_pct}%"
            }
            
            await db.clientes.insert_one(nuevo_cliente)
            logger.info(f"[NetCash][AltaWeb] Cliente nuevo creado: {cliente_id}")
        
        # 2. Actualizar comisión del cliente (si ya existía)
        await db.clientes.update_one(
            {"id": cliente_id},
            {"$set": {
                "porcentaje_comision_cliente": data.comision_pct,
                "estado": "activo",
                "telegram_id": data.telegram_id,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # 3. Crear o actualizar usuario en usuarios_telegram
        usuario_telegram = await db.usuarios_telegram.find_one(
            {"telegram_id": data.telegram_id},
            {"_id": 0}
        )
        
        if usuario_telegram:
            # Actualizar usuario existente
            await db.usuarios_telegram.update_one(
                {"telegram_id": data.telegram_id},
                {"$set": {
                    "rol": "cliente_activo",
                    "id_cliente": cliente_id,
                    "nombre": data.nombre,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            logger.info(f"[NetCash][AltaWeb] Usuario Telegram actualizado: {data.telegram_id}")
        else:
            # Crear usuario nuevo
            nuevo_usuario_telegram = {
                "telegram_id": data.telegram_id,
                "chat_id": None,  # Se llenará cuando el usuario escriba al bot
                "nombre": data.nombre,
                "telefono": None,
                "rol": "cliente_activo",
                "id_cliente": cliente_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db.usuarios_telegram.insert_one(nuevo_usuario_telegram)
            logger.info(f"[NetCash][AltaWeb] Usuario Telegram creado: {data.telegram_id}")
        
        # 4. Enviar mensaje de bienvenida por Telegram
        mensaje = (
            f"Hola {data.nombre} 👋\n\n"
            "Te acabo de vincular a NetCash MBco.\n"
            "Ya puedes crear operaciones y mandarme tus comprobantes.\n\n"
            "Escribe /start para ver el menú."
        )
        
        mensaje_enviado = False
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": data.telegram_id,
                    "text": mensaje
                }
                
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"[NetCash][AltaWeb] Mensaje de bienvenida enviado a {data.telegram_id}")
                        mensaje_enviado = True
                    else:
                        error_text = await response.text()
                        logger.warning(f"[NetCash][AltaWeb] No se pudo enviar mensaje Telegram: {response.status} - {error_text}")
        except Exception as telegram_error:
            logger.warning(f"[NetCash][AltaWeb] Error enviando mensaje Telegram: {str(telegram_error)}")
        
        return {
            "ok": True,
            "mensaje": "Cliente vinculado correctamente" + (" y mensaje enviado por Telegram" if mensaje_enviado else " (mensaje no enviado - el usuario debe escribir al bot primero)"),
            "cliente_id": cliente_id,
            "telegram_id": data.telegram_id,
            "mensaje_enviado": mensaje_enviado
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[NetCash][AltaWeb][ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"[NetCash][AltaWeb][ERROR] Traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
