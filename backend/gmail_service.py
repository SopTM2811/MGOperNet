"""
Servicio de Gmail API para NetCash
Maneja la comunicación con Gmail para recibir y enviar correos
"""

import os
import base64
import logging
from typing import Dict, List, Optional
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GmailService:
    """Servicio para interactuar con Gmail API"""
    
    def __init__(self):
        self.gmail_user = os.getenv("GMAIL_USER")
        self.client_id = os.getenv("GMAIL_CLIENT_ID")
        self.client_secret = os.getenv("GMAIL_CLIENT_SECRET")
        self.refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
        
        if not all([self.gmail_user, self.client_id, self.client_secret, self.refresh_token]):
            raise ValueError("Faltan credenciales de Gmail en variables de entorno")
        
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Inicializa el servicio de Gmail API"""
        try:
            creds = Credentials(
                token=None,
                refresh_token=self.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=[
                    'https://www.googleapis.com/auth/gmail.modify',
                    'https://www.googleapis.com/auth/gmail.send',
                    'https://www.googleapis.com/auth/gmail.labels'
                ]
            )
            
            # Refrescar el token
            creds.refresh(Request())
            
            # Crear servicio
            self.service = build('gmail', 'v1', credentials=creds)
            logger.info(f"[Gmail] Servicio inicializado para {self.gmail_user}")
            
        except Exception as e:
            logger.error(f"[Gmail] Error inicializando servicio: {str(e)}")
            raise
    
    def list_unread_messages(self, query: str = None) -> List[Dict]:
        """
        Lista mensajes no leídos en INBOX
        
        Args:
            query: Query de búsqueda de Gmail (default: "label:INBOX is:unread")
        
        Returns:
            Lista de mensajes con id y threadId
        """
        try:
            if query is None:
                # Query por defecto: INBOX, no leídos, con adjuntos o asunto NetCash
                query = "label:INBOX is:unread (has:attachment OR subject:NetCash)"
            
            logger.info(f"[Gmail] Buscando mensajes con query: {query}")
            
            results = self.service.users().messages().list(
                userId='me',
                q=query
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"[Gmail] Se encontraron {len(messages)} mensajes no leídos")
            
            return messages
            
        except HttpError as error:
            logger.error(f"[Gmail] Error listando mensajes: {error}")
            return []
    
    def get_message(self, message_id: str) -> Optional[Dict]:
        """
        Obtiene un mensaje completo por su ID
        
        Args:
            message_id: ID del mensaje
        
        Returns:
            Diccionario con los datos del mensaje
        """
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            return message
            
        except HttpError as error:
            logger.error(f"[Gmail] Error obteniendo mensaje {message_id}: {error}")
            return None
    
    def parse_message(self, message: Dict) -> Dict:
        """
        Parsea un mensaje de Gmail y extrae información relevante
        
        Returns:
            Diccionario con: from, subject, body, attachments
        """
        headers = message['payload']['headers']
        
        # Extraer headers importantes
        msg_data = {
            'id': message['id'],
            'thread_id': message['threadId'],
            'from': '',
            'subject': '',
            'body': '',
            'attachments': []
        }
        
        for header in headers:
            name = header['name'].lower()
            if name == 'from':
                msg_data['from'] = header['value']
            elif name == 'subject':
                msg_data['subject'] = header['value']
        
        # Extraer cuerpo y adjuntos
        self._parse_parts(message['payload'], msg_data)
        
        logger.info(f"[Gmail] Mensaje parseado - From: {msg_data['from']}, Subject: {msg_data['subject']}, Adjuntos: {len(msg_data['attachments'])}")
        
        return msg_data
    
    def _parse_parts(self, payload: Dict, msg_data: Dict):
        """Parsea recursivamente las partes del mensaje"""
        if 'parts' in payload:
            for part in payload['parts']:
                self._parse_parts(part, msg_data)
        else:
            # Extraer cuerpo de texto
            mime_type = payload.get('mimeType', '')
            if mime_type == 'text/plain' or mime_type == 'text/html':
                if 'data' in payload['body']:
                    body_data = payload['body']['data']
                    body_text = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                    if not msg_data['body'] or len(body_text) > len(msg_data['body']):
                        msg_data['body'] = body_text
            
            # Extraer adjuntos
            if 'filename' in payload and payload['filename']:
                attachment_id = payload['body'].get('attachmentId')
                if attachment_id:
                    msg_data['attachments'].append({
                        'filename': payload['filename'],
                        'mime_type': payload.get('mimeType', ''),
                        'attachment_id': attachment_id,
                        'size': payload['body'].get('size', 0)
                    })
    
    def get_attachment(self, message_id: str, attachment_id: str) -> Optional[bytes]:
        """
        Descarga un adjunto
        
        Args:
            message_id: ID del mensaje
            attachment_id: ID del adjunto
        
        Returns:
            Bytes del adjunto
        """
        try:
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            data = attachment['data']
            file_data = base64.urlsafe_b64decode(data)
            
            return file_data
            
        except HttpError as error:
            logger.error(f"[Gmail] Error descargando adjunto: {error}")
            return None
    
    def send_reply(self, to: str, subject: str, body: str, thread_id: str = None) -> bool:
        """
        Envía un correo de respuesta
        
        Args:
            to: Destinatario
            subject: Asunto
            body: Cuerpo del mensaje
            thread_id: ID del thread (para respuestas)
        
        Returns:
            True si se envió correctamente
        """
        try:
            message = MIMEText(body, 'plain', 'utf-8')
            message['to'] = to
            message['from'] = self.gmail_user
            message['subject'] = subject
            
            # Crear el mensaje raw
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            send_params = {
                'userId': 'me',
                'body': {'raw': raw_message}
            }
            
            # Si es una respuesta, incluir threadId
            if thread_id:
                send_params['body']['threadId'] = thread_id
            
            sent_message = self.service.users().messages().send(**send_params).execute()
            
            logger.info(f"[Gmail] Correo enviado exitosamente a {to} - ID: {sent_message['id']}")
            return True
            
        except HttpError as error:
            logger.error(f"[Gmail] Error enviando correo: {error}")
            return False
    
    def mark_as_read(self, message_id: str) -> bool:
        """Marca un mensaje como leído"""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            
            logger.info(f"[Gmail] Mensaje {message_id} marcado como leído")
            return True
            
        except HttpError as error:
            logger.error(f"[Gmail] Error marcando mensaje como leído: {error}")
            return False
    
    def add_label(self, message_id: str, label_name: str) -> bool:
        """
        Agrega una etiqueta a un mensaje
        
        Args:
            message_id: ID del mensaje
            label_name: Nombre de la etiqueta (ej: "NETCASH/PROCESADO")
        
        Returns:
            True si se agregó correctamente
        """
        try:
            # Buscar o crear la etiqueta
            label_id = self._get_or_create_label(label_name)
            
            if not label_id:
                return False
            
            # Agregar la etiqueta al mensaje
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': [label_id]}
            ).execute()
            
            logger.info(f"[Gmail] Etiqueta '{label_name}' agregada al mensaje {message_id}")
            return True
            
        except HttpError as error:
            logger.error(f"[Gmail] Error agregando etiqueta: {error}")
            return False
    
    def _get_or_create_label(self, label_name: str) -> Optional[str]:
        """Busca una etiqueta por nombre o la crea si no existe"""
        try:
            # Listar todas las etiquetas
            results = self.service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])
            
            # Buscar la etiqueta
            for label in labels:
                if label['name'] == label_name:
                    return label['id']
            
            # Si no existe, crearla
            logger.info(f"[Gmail] Creando etiqueta '{label_name}'")
            
            label_object = {
                'name': label_name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
            
            created_label = self.service.users().labels().create(
                userId='me',
                body=label_object
            ).execute()
            
            return created_label['id']
            
        except HttpError as error:
            logger.error(f"[Gmail] Error gestionando etiqueta: {error}")
            return None


# Instancia global del servicio
try:
    gmail_service = GmailService()
except Exception as e:
    logger.error(f"[Gmail] No se pudo inicializar el servicio: {str(e)}")
    gmail_service = None
