"""Servicio para notificar cambios de cuenta de depósito NetCash"""

import os
import logging
from typing import Dict, List
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

# Conexión a MongoDB
mongo_url = os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'netcash_mbco')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

# SMTP service (reemplaza Gmail OAuth que expira)
try:
    from smtp_service import smtp_service
except:
    smtp_service = None
    logger.warning("[NotificacionCuenta] SMTP service no disponible")


async def enviar_notificacion_cambio_cuenta(cuenta: Dict):
    """
    Envía notificación por email a todos los clientes activos
    cuando se activa una nueva cuenta de depósito.
    
    Args:
        cuenta: Dict con banco, clabe, beneficiario
    """
    if not smtp_service or not smtp_service.configured:
        logger.error("[NotificacionCuenta] SMTP service no disponible o no configurado")
        return
    
    try:
        # Obtener todos los clientes activos
        clientes = await db.clientes.find(
            {"estado": "activo"},
            {"_id": 0, "email": 1, "nombre": 1}
        ).to_list(1000)
        
        logger.info(f"[NotificacionCuenta] Enviando notificación a {len(clientes)} clientes activos")
        
        # Construir mensaje
        banco = cuenta.get('banco', 'N/A')
        clabe = cuenta.get('clabe', 'N/A')
        beneficiario = cuenta.get('beneficiario', 'N/A')
        
        asunto = "NetCash – Actualización de cuenta para depósitos"
        
        enviados = 0
        errores = 0
        
        for cliente in clientes:
            email = cliente.get('email')
            if not email:
                continue
            
            try:
                cuerpo = f"""Hola,

Te informamos que a partir de hoy la cuenta autorizada para recibir tus depósitos NetCash es:

Banco: {banco}
CLABE: {clabe}
Beneficiario: {beneficiario}

Por favor actualiza esta información en tus registros para evitar errores en futuros depósitos.

Cualquier duda, estamos a tus órdenes.

Equipo NetCash"""
                
                # Enviar email via SMTP
                exito = smtp_service.enviar_correo(email, asunto, cuerpo)
                
                if exito:
                    enviados += 1
                else:
                    errores += 1
                    
            except Exception as e:
                logger.error(f"[NotificacionCuenta] Error enviando a {email}: {str(e)}")
                errores += 1
        
        logger.info(f"[NotificacionCuenta] Notificaciones completadas: {enviados} enviados, {errores} errores")
        
        # También enviar a emails internos configurables
        emails_internos = os.getenv('EMAILS_NOTIFICACION_CUENTA', 'gestion.ngdl@gmail.com').split(',')
        
        for email_interno in emails_internos:
            email_interno = email_interno.strip()
            if email_interno:
                try:
                    cuerpo_interno = f"""Hola equipo,

Se ha activado una nueva cuenta de depósito NetCash:

Banco: {banco}
CLABE: {clabe}
Beneficiario: {beneficiario}

Se han enviado notificaciones a {enviados} clientes activos.

Sistema NetCash"""
                    
                    smtp_service.enviar_correo(email_interno, asunto, cuerpo_interno)
                    logger.info(f"[NotificacionCuenta] Notificación interna enviada a {email_interno}")
                except Exception as e:
                    logger.error(f"[NotificacionCuenta] Error enviando notificación interna: {str(e)}")
        
    except Exception as e:
        logger.error(f"[NotificacionCuenta] Error general: {str(e)}")
        raise
