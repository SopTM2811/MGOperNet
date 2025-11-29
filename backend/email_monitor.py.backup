"""Monitor de correos de Gmail para NetCash
Procesa correos entrantes y crea operaciones NetCash
"""

import os
import re
import time
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from gmail_service import gmail_service

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/email_monitor.log'),
        logging.StreamHandler()
    ]
)

# Conexión a MongoDB
mongo_url = os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'netcash_mbco')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

# Directorio para guardar adjuntos
ATTACHMENTS_DIR = Path("/app/backend/uploads/email_attachments")
ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)


class EmailMonitor:
    """Monitor que procesa correos de Gmail para NetCash"""
    
    def __init__(self):
        self.gmail = gmail_service
        
        if not self.gmail:
            raise Exception("Gmail service no inicializado")
    
    async def process_emails(self):
        """Procesa todos los correos no leídos"""
        try:
            logger.info("[EmailMonitor] Iniciando procesamiento de correos...")
            
            # Listar mensajes no leídos
            messages = self.gmail.list_unread_messages()
            
            if not messages:
                logger.info("[EmailMonitor] No hay correos nuevos")
                return
            
            logger.info(f"[EmailMonitor] Procesando {len(messages)} correos...")
            
            for msg_summary in messages:
                try:
                    await self.process_single_email(msg_summary['id'])
                except Exception as e:
                    logger.error(f"[EmailMonitor] Error procesando mensaje {msg_summary['id']}: {str(e)}")
                    continue
            
            logger.info("[EmailMonitor] Procesamiento completado")
            
        except Exception as e:
            logger.error(f"[EmailMonitor] Error en process_emails: {str(e)}")
    
    async def process_single_email(self, message_id: str):
        """Procesa un correo individual"""
        logger.info(f"[EmailMonitor] Procesando mensaje {message_id}...")
        
        # Obtener mensaje completo
        message = self.gmail.get_message(message_id)
        if not message:
            logger.error(f"[EmailMonitor] No se pudo obtener el mensaje {message_id}")
            return
        
        # Parsear mensaje
        msg_data = self.gmail.parse_message(message)
        
        # Extraer email del remitente
        email_cliente = self._extract_email(msg_data['from'])
        
        logger.info(f"[EmailMonitor] Email de: {email_cliente}")
        logger.info(f"[EmailMonitor] Asunto: {msg_data['subject']}")
        logger.info(f"[EmailMonitor] Adjuntos: {len(msg_data['attachments'])}")
        
        # Extraer información del cuerpo
        info_extraida = self._extract_info_from_body(msg_data['body'])
        
        # Descargar adjuntos
        archivos_adjuntos = await self._download_attachments(
            message_id, 
            msg_data['attachments']
        )
        
        # Validar si la información es suficiente
        info_completa = self._validate_info(
            email_cliente,
            archivos_adjuntos,
            info_extraida
        )
        
        # Crear operación NetCash
        operacion = await self._create_netcash_operation(
            email_cliente=email_cliente,
            asunto=msg_data['subject'],
            cuerpo=msg_data['body'],
            archivos_adjuntos=archivos_adjuntos,
            info_extraida=info_extraida,
            mensaje_id=message_id,
            thread_id=msg_data['thread_id']
        )
        
        # Enviar respuesta automática
        if info_completa:
            await self._send_success_response(
                email_cliente,
                msg_data['thread_id'],
                operacion['clave_operacion']
            )
            self.gmail.add_label(message_id, "NETCASH/PROCESADO")
        else:
            await self._send_incomplete_response(
                email_cliente,
                msg_data['thread_id']
            )
            self.gmail.add_label(message_id, "NETCASH/FALTA_INFO")
        
        # Marcar como leído
        self.gmail.mark_as_read(message_id)
        
        logger.info(f"[EmailMonitor] Operación {operacion['clave_operacion']} creada desde email")
    
    def _extract_email(self, from_header: str) -> str:
        """Extrae el email del header From"""
        match = re.search(r'<([^>]+)>', from_header)
        if match:
            return match.group(1)
        return from_header
    
    def _extract_info_from_body(self, body: str) -> Dict:
        """Extrae información relevante del cuerpo del correo"""
        info = {
            'monto': None,
            'idmex': None,
            'referencia': None
        }
        
        # Buscar monto
        monto_match = re.search(r'monto[:\s]+\$?([0-9,]+(?:\.[0-9]{2})?)', body, re.IGNORECASE)
        if monto_match:
            monto_str = monto_match.group(1).replace(',', '')
            try:
                info['monto'] = float(monto_str)
            except:
                pass
        
        # Buscar IDMEX
        idmex_match = re.search(r'IDMEX[:\s]+([0-9]+)', body, re.IGNORECASE)
        if idmex_match:
            info['idmex'] = idmex_match.group(1)
        
        # Buscar referencia
        ref_match = re.search(r'(?:referencia|operaci[oó]n)[:\s]+([A-Za-z0-9-]+)', body, re.IGNORECASE)
        if ref_match:
            info['referencia'] = ref_match.group(1)
        
        return info
    
    async def _download_attachments(self, message_id: str, attachments: List[Dict]) -> List[Dict]:
        """Descarga los adjuntos del correo"""
        archivos = []
        
        for att in attachments:
            try:
                # Descargar adjunto
                file_data = self.gmail.get_attachment(message_id, att['attachment_id'])
                
                if not file_data:
                    continue
                
                # Generar nombre único
                filename = f"{uuid4()}_{att['filename']}"
                file_path = ATTACHMENTS_DIR / filename
                
                # Guardar archivo
                with open(file_path, 'wb') as f:
                    f.write(file_data)
                
                archivos.append({
                    'nombre_original': att['filename'],
                    'nombre_guardado': filename,
                    'ruta': str(file_path),
                    'mime_type': att['mime_type'],
                    'tamaño': att['size']
                })
                
                logger.info(f"[EmailMonitor] Adjunto descargado: {filename}")
                
            except Exception as e:
                logger.error(f"[EmailMonitor] Error descargando adjunto {att['filename']}: {str(e)}")
        
        return archivos
    
    def _validate_info(self, email_cliente: str, archivos: List, info_extraida: Dict) -> bool:
        """Valida si la información es suficiente para procesar la operación"""
        # Criterios básicos para Fase 1:
        # 1. Debe tener email
        # 2. Debe tener al menos un adjunto
        
        if not email_cliente:
            return False
        
        if len(archivos) == 0:
            return False
        
        return True
    
    async def _create_netcash_operation(self,
                                        email_cliente: str,
                                        asunto: str,
                                        cuerpo: str,
                                        archivos_adjuntos: List[Dict],
                                        info_extraida: Dict,
                                        mensaje_id: str,
                                        thread_id: str) -> Dict:
        """Crea una operación NetCash en la base de datos"""
        
        # Generar clave de operación
        count = await db.operaciones.count_documents({})
        clave_operacion = f"NC-EMAIL-{count + 1:06d}"
        
        # Crear documento de operación
        operacion = {
            "id": str(uuid4()),
            "clave_operacion": clave_operacion,
            "medio_origen": "email",
            "email_cliente": email_cliente,
            "asunto_email": asunto,
            "cuerpo_email": cuerpo,
            "gmail_message_id": mensaje_id,
            "gmail_thread_id": thread_id,
            "estado_operacion": "en_revision_por_mail",
            "monto_reportado_por_mail": info_extraida.get('monto'),
            "idmex_reportado": info_extraida.get('idmex'),
            "referencia_reportada": info_extraida.get('referencia'),
            "archivos_adjuntos": archivos_adjuntos,
            "comprobantes": [],  # Se procesarán después
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Guardar en la base de datos
        await db.operaciones.insert_one(operacion)
        
        logger.info(f"[EmailMonitor] Operación {clave_operacion} creada en BD")
        
        return operacion
    
    async def _send_success_response(self, to: str, thread_id: str, clave_operacion: str):
        """Envía respuesta de éxito al cliente"""
        subject = "NetCash – Operación registrada"
        body = f"""Hola,

Recibimos tu correo y tus comprobantes.

Tu operación NetCash ha sido registrada con el código: {clave_operacion}

Esta operación está en proceso de validación interna.
En caso de requerir información adicional, nos pondremos en contacto contigo.

Gracias por usar NetCash.

Equipo NetCash"""
        
        self.gmail.send_reply(to, subject, body, thread_id)
        logger.info(f"[EmailMonitor] Respuesta de éxito enviada a {to}")
    
    async def _send_incomplete_response(self, to: str, thread_id: str):
        """Envía respuesta de información incompleta al cliente"""
        subject = "NetCash – Hace falta información para tu operación"
        body = """Hola,

Recibimos tu correo para operar con NetCash, pero todavía nos falta información para poder registrar correctamente la operación.

En tu próximo correo por favor incluye:
• Comprobantes claros y legibles en PDF, JPG o PNG (si son varios, adjunta todos los relacionados con la operación).
• La cantidad de ligas NetCash que necesitas para esta operación.

Si necesitas apoyo para completar la información, simplemente responde a este mismo correo escribiendo la palabra "AYUDA" y nuestro equipo se pondrá en contacto contigo.

En cuanto tengamos la información completa, registramos la operación y te confirmamos por este mismo medio.

Quedamos al pendiente.

Equipo NetCash"""
        
        self.gmail.send_reply(to, subject, body, thread_id)
        logger.info(f"[EmailMonitor] Respuesta de info incompleta enviada a {to}")


async def main():
    """Función principal del monitor"""
    logger.info("[EmailMonitor] Iniciando monitor de correos NetCash...")
    
    monitor = EmailMonitor()
    
    # Loop infinito que revisa correos cada 2 minutos
    while True:
        try:
            await monitor.process_emails()
        except Exception as e:
            logger.error(f"[EmailMonitor] Error en el ciclo principal: {str(e)}")
        
        # Esperar 2 minutos antes de revisar de nuevo
        logger.info("[EmailMonitor] Esperando 2 minutos antes de la próxima revisión...")
        await asyncio.sleep(120)


if __name__ == "__main__":
    asyncio.run(main())
