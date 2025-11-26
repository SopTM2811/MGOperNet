"""
BLOQUE 3: Monitor de inactividad para operaciones en Telegram
Revisa cada minuto las operaciones en estados de captura y cancela las que tienen más de 3 minutos sin actividad
"""
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[os.environ.get('DB_NAME', 'netcash_mbco')]

ESTADOS_EN_CAPTURA = [
    "EN_CAPTURA",
    "ESPERANDO_COMPROBANTES",
    "ESPERANDO_DATOS_TITULAR"
]

TIMEOUT_MINUTOS = 3


async def revisar_operaciones_inactivas():
    """Revisa operaciones en captura y cancela las que tienen más de 3 minutos de inactividad"""
    try:
        # Calcular timestamp de hace 3 minutos
        limite_inactividad = datetime.now(timezone.utc) - timedelta(minutes=TIMEOUT_MINUTOS)
        
        # Buscar operaciones en captura con origen telegram y sin actividad reciente
        query = {
            "origen_operacion": "telegram",
            "estado": {"$in": ESTADOS_EN_CAPTURA},
            "$or": [
                {"ultimo_mensaje_cliente": {"$exists": False}},
                {"ultimo_mensaje_cliente": {"$lt": limite_inactividad.isoformat()}}
            ]
        }
        
        operaciones_inactivas = await db.operaciones.find(query, {"_id": 0}).to_list(100)
        
        if operaciones_inactivas:
            logger.info(f"Encontradas {len(operaciones_inactivas)} operaciones inactivas")
            
            for op in operaciones_inactivas:
                folio = op.get("folio_mbco", "N/A")
                operacion_id = op.get("id")
                
                # Actualizar estado a cancelada
                await db.operaciones.update_one(
                    {"id": operacion_id},
                    {"$set": {
                        "estado": "CANCELADA_POR_INACTIVIDAD",
                        "fecha_cancelacion": datetime.now(timezone.utc).isoformat(),
                        "motivo_cancelacion": f"Inactividad mayor a {TIMEOUT_MINUTOS} minutos"
                    }}
                )
                
                # Marcar comprobantes como descartados
                comprobantes = op.get("comprobantes", [])
                if comprobantes:
                    comprobantes_descartados = []
                    for c in comprobantes:
                        c["descartado"] = True
                        c["motivo_descarte"] = "Operación cancelada por inactividad"
                        comprobantes_descartados.append(c)
                    
                    await db.operaciones.update_one(
                        {"id": operacion_id},
                        {"$set": {"comprobantes": comprobantes_descartados}}
                    )
                
                logger.info(f"Operación {folio} cancelada por inactividad ({TIMEOUT_MINUTOS} min)")
                
                # Notificar al cliente por Telegram
                chat_id = op.get("cliente_telegram_id")
                if chat_id:
                    try:
                        # Buscar el chat_id del usuario de telegram
                        usuario_telegram = await db.usuarios_telegram.find_one(
                            {"id_cliente": op.get("id_cliente")},
                            {"_id": 0}
                        )
                        
                        if usuario_telegram and usuario_telegram.get("chat_id"):
                            # Enviar notificación usando la API de Telegram directamente
                            import aiohttp
                            telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
                            
                            if telegram_token:
                                mensaje = f"⏰ **Operación cancelada por inactividad**\n\n"
                                mensaje += f"**Folio MBco:** {folio}\n\n"
                                mensaje += "Tu operación fue cancelada automáticamente porque no recibimos actividad en los últimos 3 minutos.\n\n"
                                mensaje += "Si aún necesitas crear esta operación, por favor:\n"
                                mensaje += "• Escribe /start\n"
                                mensaje += "• Selecciona 'Crear nueva operación NetCash'\n"
                                mensaje += "• Envía tus comprobantes de forma continua"
                                
                                async with aiohttp.ClientSession() as session:
                                    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                                    payload = {
                                        "chat_id": usuario_telegram["chat_id"],
                                        "text": mensaje,
                                        "parse_mode": "Markdown"
                                    }
                                    await session.post(url, json=payload)
                                
                                logger.info(f"Notificación de cancelación enviada al cliente {op.get('id_cliente')}")
                    except Exception as notif_error:
                        logger.error(f"Error enviando notificación de cancelación: {str(notif_error)}")
        
    except Exception as e:
        logger.error(f"Error revisando operaciones inactivas: {str(e)}")


async def main():
    """Loop principal que revisa cada minuto"""
    logger.info(f"Monitor de inactividad iniciado (timeout: {TIMEOUT_MINUTOS} minutos)")
    
    while True:
        await revisar_operaciones_inactivas()
        await asyncio.sleep(60)  # Revisar cada minuto


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Monitor detenido")
