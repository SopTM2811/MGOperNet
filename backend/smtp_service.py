"""
Servicio SMTP unificado para envío de correos con App Password
Reemplaza Gmail OAuth que tiene problemas de expiración de tokens
"""

import os
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from typing import List, Optional, Dict
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SMTPService:
    """Servicio unificado para envío de correos via SMTP con App Password"""
    
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_pass = os.getenv("SMTP_PASSWORD", "")
        
        self.configured = bool(self.smtp_user and self.smtp_pass)
        
        if self.configured:
            logger.info(f"[SMTP] Servicio configurado: {self.smtp_user}")
        else:
            logger.warning("[SMTP] Servicio NO configurado - faltan SMTP_USER o SMTP_PASSWORD")
    
    def enviar_correo(
        self,
        destinatario: str,
        asunto: str,
        cuerpo: str,
        adjuntos: List[str] = None,
        html: bool = False
    ) -> bool:
        """
        Envía un correo electrónico via SMTP.
        
        Args:
            destinatario: Email del destinatario
            asunto: Asunto del correo
            cuerpo: Cuerpo del mensaje (texto plano o HTML)
            adjuntos: Lista de rutas de archivos a adjuntar
            html: Si True, el cuerpo se envía como HTML
        
        Returns:
            bool: True si se envió correctamente
        """
        if not self.configured:
            logger.warning(f"[SMTP] No configurado. Correo no enviado a {destinatario}")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = destinatario
            msg['Subject'] = asunto
            
            # Agregar cuerpo
            content_type = 'html' if html else 'plain'
            msg.attach(MIMEText(cuerpo, content_type))
            
            # Agregar adjuntos si hay
            if adjuntos:
                for archivo_path in adjuntos:
                    if os.path.exists(archivo_path):
                        with open(archivo_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                        encoders.encode_base64(part)
                        filename = Path(archivo_path).name
                        part.add_header('Content-Disposition', f'attachment; filename={filename}')
                        msg.attach(part)
                        logger.info(f"[SMTP] Adjunto agregado: {filename}")
                    else:
                        logger.warning(f"[SMTP] Archivo no encontrado: {archivo_path}")
            
            # Enviar
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            
            logger.info(f"[SMTP] Correo enviado a {destinatario}: {asunto}")
            return True
            
        except Exception as e:
            logger.error(f"[SMTP] Error enviando correo: {str(e)}")
            return False
    
    async def enviar_correo_con_adjuntos(
        self,
        destinatario: str,
        asunto: str,
        cuerpo: str,
        adjuntos: List[str] = None
    ) -> Optional[Dict]:
        """
        Versión async compatible con la interfaz de gmail_service.
        
        Returns:
            Dict con info del correo enviado o None si falló
        """
        exito = self.enviar_correo(destinatario, asunto, cuerpo, adjuntos)
        if exito:
            return {
                "success": True,
                "to": destinatario,
                "subject": asunto
            }
        return None
    
    def send_reply(self, destinatario: str, asunto: str, cuerpo: str, thread_id=None) -> bool:
        """Método compatible con gmail_service.send_reply"""
        return self.enviar_correo(destinatario, asunto, cuerpo)


# Instancia global
smtp_service = SMTPService()
