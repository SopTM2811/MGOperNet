"""
Servicio de Gmail API para NetCash
Maneja envío y lectura de correos usando OAuth 2.0

CONFIGURACIÓN REQUERIDA:
1. Archivo credentials.json (proporcionado por el usuario)
2. Primera vez: ejecutar oauth_flow() para generar token.json
3. Scopes necesarios:
   - https://www.googleapis.com/auth/gmail.send
   - https://www.googleapis.com/auth/gmail.readonly
"""

import os
import base64
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

logger = logging.getLogger(__name__)

# Rutas de configuración
CREDENTIALS_FILE = Path("/app/backend/config/gmail_credentials.json")
TOKEN_FILE = Path("/app/backend/config/gmail_token.json")

# Scopes requeridos
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly'
]


class GmailService:
    """Servicio para enviar y leer correos con Gmail API"""
    
    def __init__(self):
        self.service = None
        self.credentials = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Inicializa el servicio de Gmail API"""
        try:
            # Importar librerías de Google (deben instalarse)
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            
            # Cargar credenciales desde token.json si existe
            if TOKEN_FILE.exists():
                self.credentials = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
            
            # Si no hay credenciales válidas, necesita autenticación
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    logger.info("Token expirado, refrescando...")
                    self.credentials.refresh(Request())
                else:
                    logger.warning("No hay token válido. Ejecuta oauth_flow() primero.")
                    return
                
                # Guardar token actualizado
                TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(TOKEN_FILE, 'w') as token:
                    token.write(self.credentials.to_json())
            
            # Construir servicio
            self.service = build('gmail', 'v1', credentials=self.credentials)
            logger.info("Gmail API inicializada correctamente")
            
        except ImportError:
            logger.error("Librerías de Google no instaladas. Ejecuta: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        except Exception as e:
            logger.error(f"Error inicializando Gmail API: {str(e)}")
    
    def oauth_flow(self):
        """
        Ejecuta el flujo de autenticación OAuth.
        SOLO EJECUTAR LA PRIMERA VEZ para generar token.json
        
        Abre navegador para que el usuario autorice la aplicación.
        """
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            
            if not CREDENTIALS_FILE.exists():
                logger.error(f"No se encontró {CREDENTIALS_FILE}")
                logger.error("Coloca el archivo credentials.json en /app/backend/config/")
                return False
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            
            # Ejecuta el servidor local y abre navegador
            self.credentials = flow.run_local_server(port=0)
            
            # Guarda el token
            TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(TOKEN_FILE, 'w') as token:
                token.write(self.credentials.to_json())
            
            logger.info(f"Token guardado en {TOKEN_FILE}")
            
            # Reinicializar servicio
            self._initialize_service()
            return True
            
        except Exception as e:
            logger.error(f"Error en OAuth flow: {str(e)}")
            return False
    
    def enviar_correo(
        self,
        destinatario: str,
        asunto: str,
        cuerpo_html: str,
        adjuntos: Optional[List[Dict[str, Any]]] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> bool:
        """
        Envía un correo usando Gmail API
        
        Args:
            destinatario: Email del destinatario
            asunto: Asunto del correo
            cuerpo_html: Contenido HTML del correo
            adjuntos: Lista de dicts con 'filename' y 'content' (bytes)
            cc: Lista de correos en copia
            bcc: Lista de correos en copia oculta
        
        Returns:
            bool: True si se envió correctamente
        """
        if not self.service:
            logger.error("Gmail API no inicializada. Ejecuta oauth_flow() primero.")
            return False
        
        try:
            # Crear mensaje MIME
            message = MIMEMultipart()
            message['to'] = destinatario
            message['subject'] = asunto
            
            if cc:
                message['cc'] = ', '.join(cc)
            if bcc:
                message['bcc'] = ', '.join(bcc)
            
            # Agregar cuerpo HTML
            message.attach(MIMEText(cuerpo_html, 'html'))
            
            # Agregar adjuntos si existen
            if adjuntos:
                for adjunto in adjuntos:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(adjunto['content'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {adjunto["filename"]}'
                    )
                    message.attach(part)
            
            # Codificar mensaje en base64
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Enviar
            send_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            logger.info(f"Correo enviado a {destinatario}. ID: {send_message.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando correo: {str(e)}")
            return False
    
    def leer_correos_pendientes(
        self,
        etiqueta: str = "NETCASH_INBOX",
        max_resultados: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Lee correos pendientes de procesar
        
        Args:
            etiqueta: Etiqueta de Gmail para filtrar (default: NETCASH_INBOX)
            max_resultados: Máximo de correos a retornar
        
        Returns:
            Lista de dicts con: id, remitente, asunto, tiene_adjuntos, fecha
        """
        if not self.service:
            logger.error("Gmail API no inicializada")
            return []
        
        try:
            # Buscar mensajes con la etiqueta
            results = self.service.users().messages().list(
                userId='me',
                labelIds=[etiqueta],
                maxResults=max_resultados
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                logger.info("No hay correos pendientes")
                return []
            
            correos_pendientes = []
            
            for msg in messages:
                # Obtener detalles del mensaje
                mensaje = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                headers = {h['name']: h['value'] for h in mensaje['payload']['headers']}
                
                correo_info = {
                    'id': msg['id'],
                    'remitente': headers.get('From', 'Desconocido'),
                    'asunto': headers.get('Subject', 'Sin asunto'),
                    'fecha': headers.get('Date', ''),
                    'tiene_adjuntos': bool(mensaje['payload'].get('parts'))
                }
                
                correos_pendientes.append(correo_info)
            
            logger.info(f"Encontrados {len(correos_pendientes)} correos pendientes")
            return correos_pendientes
            
        except Exception as e:
            logger.error(f"Error leyendo correos: {str(e)}")
            return []
    
    def marcar_como_procesado(self, mensaje_id: str) -> bool:
        """
        Marca un correo como procesado (remueve etiqueta NETCASH_INBOX)
        
        Args:
            mensaje_id: ID del mensaje de Gmail
        
        Returns:
            bool: True si se marcó correctamente
        """
        if not self.service:
            logger.error("Gmail API no inicializada")
            return False
        
        try:
            self.service.users().messages().modify(
                userId='me',
                id=mensaje_id,
                body={
                    'removeLabelIds': ['NETCASH_INBOX'],
                    'addLabelIds': ['NETCASH_PROCESADO']
                }
            ).execute()
            
            logger.info(f"Mensaje {mensaje_id} marcado como procesado")
            return True
            
        except Exception as e:
            logger.error(f"Error marcando mensaje: {str(e)}")
            return False


# Instancia global (se inicializará cuando haya token.json)
gmail_service = GmailService()


# Función de utilidad para verificar estado
def verificar_configuracion_gmail() -> Dict[str, bool]:
    """
    Verifica el estado de la configuración de Gmail API
    
    Returns:
        Dict con estado de cada componente
    """
    return {
        "credentials_existe": CREDENTIALS_FILE.exists(),
        "token_existe": TOKEN_FILE.exists(),
        "servicio_inicializado": gmail_service.service is not None,
        "ruta_credentials": str(CREDENTIALS_FILE),
        "ruta_token": str(TOKEN_FILE)
    }
