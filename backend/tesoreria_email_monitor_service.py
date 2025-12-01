"""
Servicio de Monitoreo de Emails de Tesorería - Fase 2

Este servicio detecta respuestas de Tesorería a los correos de operaciones NetCash,
descarga los comprobantes de dispersión adjuntos, actualiza el estado de la operación
y notifica a Ana y al cliente.

Flujo:
1. Monitorear inbox de Gmail para detectar respuestas de Tesorería
2. Identificar a qué operación corresponde (usando Thread-ID o folio_mbco en asunto)
3. Descargar comprobantes adjuntos (PDFs de dispersión)
4. Actualizar estado de la operación a 'dispersada_proveedor'
5. Notificar a Ana (Telegram)
6. Notificar al cliente (Telegram)
"""

import os
import re
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

from gmail_service import GmailService

logger = logging.getLogger(__name__)

# Variables de entorno para configuración
MONGO_URL = os.getenv('MONGO_URL')
DB_NAME = os.getenv('DB_NAME', 'netcash_mbco')
TESORERIA_GMAIL_USER = os.getenv('TESORERIA_GMAIL_USER')  # Email de Toño o destinatario de Tesorería

# Conectar a MongoDB
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]


class TesoreriaEmailMonitorService:
    """Servicio para monitorear respuestas de Tesorería vía Gmail"""
    
    def __init__(self):
        self.gmail_service = None
        self.gmail_configured = self._check_gmail_configuration()
        
        if self.gmail_configured:
            try:
                self.gmail_service = GmailService()
                logger.info("[EmailMonitor] Servicio de Gmail configurado correctamente")
            except Exception as e:
                logger.error(f"[EmailMonitor] Error inicializando Gmail: {str(e)}")
                self.gmail_configured = False
        else:
            logger.warning("[EmailMonitor] Gmail NO configurado - los emails no se monitorearán")
            logger.warning("[EmailMonitor] Para habilitar, configura las variables de entorno: GMAIL_USER, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN")
    
    def _check_gmail_configuration(self) -> bool:
        """Verifica si las credenciales de Gmail están configuradas"""
        required_vars = ['GMAIL_USER', 'GMAIL_CLIENT_ID', 'GMAIL_CLIENT_SECRET', 'GMAIL_REFRESH_TOKEN']
        missing = [var for var in required_vars if not os.getenv(var)]
        
        if missing:
            logger.warning(f"[EmailMonitor] Variables de entorno faltantes para Gmail: {', '.join(missing)}")
            return False
        
        return True
    
    async def procesar_respuestas_pendientes(self):
        """
        Procesa todas las respuestas pendientes de Tesorería
        
        Este método:
        1. Lee emails no leídos del inbox
        2. Identifica cuáles son respuestas de operaciones NetCash
        3. Descarga comprobantes adjuntos
        4. Actualiza estados
        5. Notifica a los involucrados
        """
        if not self.gmail_configured or not self.gmail_service:
            logger.info("[EmailMonitor] Gmail no configurado - saltando procesamiento")
            return
        
        logger.info("[EmailMonitor] ========== INICIANDO PROCESAMIENTO DE RESPUESTAS ==========")
        logger.info(f"[EmailMonitor] Hora: {datetime.now(timezone.utc)}")
        
        try:
            # 1. Obtener mensajes no leídos que puedan ser respuestas de operaciones
            # Buscar emails con palabras clave relacionadas con NetCash o folios
            query = "label:INBOX is:unread"  # Procesar todos los no leídos
            mensajes = self.gmail_service.list_unread_messages(query)
            
            if not mensajes:
                logger.info("[EmailMonitor] No hay mensajes no leídos para procesar")
                return
            
            logger.info(f"[EmailMonitor] 📧 {len(mensajes)} mensaje(s) no leído(s) encontrado(s)")
            
            procesados = 0
            errores = 0
            
            for msg in mensajes:
                try:
                    # Obtener mensaje completo
                    mensaje_completo = self.gmail_service.get_message(msg['id'])
                    
                    if not mensaje_completo:
                        logger.warning(f"[EmailMonitor] No se pudo obtener mensaje {msg['id']}")
                        continue
                    
                    # Parsear mensaje
                    mensaje_data = self.gmail_service.parse_message(mensaje_completo)
                    
                    # Intentar asociar con una operación
                    operacion_id = await self._identificar_operacion(mensaje_data)
                    
                    if operacion_id:
                        logger.info(f"[EmailMonitor] ✅ Mensaje {msg['id']} asociado con operación {operacion_id}")
                        
                        # Procesar el mensaje (descargar adjuntos, actualizar estado, notificar)
                        exito = await self._procesar_respuesta_operacion(
                            operacion_id, 
                            mensaje_data, 
                            msg['id']
                        )
                        
                        if exito:
                            # Marcar como leído y etiquetar
                            self.gmail_service.mark_as_read(msg['id'])
                            self.gmail_service.add_label(msg['id'], 'NETCASH/PROCESADO')
                            procesados += 1
                        else:
                            errores += 1
                    else:
                        # No es una respuesta de operación NetCash - dejar sin leer
                        logger.debug(f"[EmailMonitor] Mensaje {msg['id']} no es respuesta de operación NetCash")
                
                except Exception as e:
                    logger.error(f"[EmailMonitor] Error procesando mensaje {msg['id']}: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    errores += 1
            
            logger.info(f"[EmailMonitor] ========== RESUMEN ==========")
            logger.info(f"[EmailMonitor] Mensajes procesados: {procesados}")
            logger.info(f"[EmailMonitor] Errores: {errores}")
            logger.info(f"[EmailMonitor] ========== FIN PROCESAMIENTO ==========")
        
        except Exception as e:
            logger.error(f"[EmailMonitor] Error general en procesamiento: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _identificar_operacion(self, mensaje_data: Dict) -> Optional[str]:
        """
        Identifica a qué operación corresponde un email basándose en:
        1. Thread-ID (si el email es respuesta al thread original)
        2. folio_mbco en el asunto o cuerpo
        
        Args:
            mensaje_data: Datos del mensaje parseado
        
        Returns:
            ID de la solicitud si se encuentra, None si no
        """
        thread_id = mensaje_data.get('thread_id')
        subject = mensaje_data.get('subject', '')
        body = mensaje_data.get('body', '')
        
        # Estrategia 1: Buscar por Thread-ID
        # Buscar operaciones que tengan este thread_id guardado
        if thread_id:
            solicitud = await db.solicitudes_netcash.find_one(
                {"email_thread_id": thread_id, "estado": "enviado_a_tesoreria"},
                {"_id": 0, "id": 1}
            )
            
            if solicitud:
                logger.info(f"[EmailMonitor] Operación encontrada por thread_id: {solicitud['id']}")
                return solicitud['id']
        
        # Estrategia 2: Buscar folio_mbco en asunto o cuerpo
        # Patrón para folios: TEST-001-T-43, MBCO-0001-T-11, etc.
        patron_folio = r'[A-Z]{4}-\d{4}-[A-Z]-\d{2}'
        
        folios_encontrados = []
        folios_encontrados.extend(re.findall(patron_folio, subject))
        folios_encontrados.extend(re.findall(patron_folio, body))
        
        if folios_encontrados:
            # Usar el primer folio encontrado
            folio_mbco = folios_encontrados[0]
            logger.info(f"[EmailMonitor] folio_mbco detectado en email: {folio_mbco}")
            
            solicitud = await db.solicitudes_netcash.find_one(
                {"folio_mbco": folio_mbco, "estado": "enviado_a_tesoreria"},
                {"_id": 0, "id": 1}
            )
            
            if solicitud:
                logger.info(f"[EmailMonitor] Operación encontrada por folio_mbco: {solicitud['id']}")
                return solicitud['id']
        
        # Estrategia 3: Verificar si el remitente es alguien de Tesorería y hay adjuntos PDF
        # Esto es un fallback para casos donde el hilo se rompió
        remitente = mensaje_data.get('from', '').lower()
        adjuntos = mensaje_data.get('attachments', [])
        
        if TESORERIA_GMAIL_USER and TESORERIA_GMAIL_USER.lower() in remitente:
            # Es de Tesorería - verificar si tiene adjuntos PDF
            tiene_pdf = any(att['filename'].lower().endswith('.pdf') for att in adjuntos)
            
            if tiene_pdf:
                logger.warning(f"[EmailMonitor] Email de Tesorería con PDF pero sin folio identificable")
                logger.warning(f"[EmailMonitor] Subject: {subject}")
                logger.warning(f"[EmailMonitor] Este caso requiere revisión manual")
        
        return None
    
    async def _procesar_respuesta_operacion(
        self, 
        operacion_id: str, 
        mensaje_data: Dict,
        message_id: str
    ) -> bool:
        """
        Procesa la respuesta de Tesorería para una operación específica
        
        Args:
            operacion_id: ID de la solicitud NetCash
            mensaje_data: Datos del mensaje parseado
            message_id: ID del mensaje de Gmail
        
        Returns:
            True si se procesó correctamente
        """
        logger.info(f"[EmailMonitor] Procesando respuesta para operación {operacion_id}")
        
        try:
            # 1. Verificar que la operación esté en estado correcto
            solicitud = await db.solicitudes_netcash.find_one(
                {"id": operacion_id},
                {"_id": 0}
            )
            
            if not solicitud:
                logger.error(f"[EmailMonitor] Operación {operacion_id} no encontrada")
                return False
            
            if solicitud.get('estado') != 'enviado_a_tesoreria':
                logger.warning(f"[EmailMonitor] Operación {operacion_id} no está en estado 'enviado_a_tesoreria' (actual: {solicitud.get('estado')})")
                # Continuar de todas formas para guardar los adjuntos
            
            # 2. Descargar y guardar comprobantes adjuntos
            adjuntos = mensaje_data.get('attachments', [])
            
            if not adjuntos:
                logger.warning(f"[EmailMonitor] No hay adjuntos en la respuesta para operación {operacion_id}")
                # Podría ser una respuesta sin comprobantes (consulta, etc.)
                return False
            
            logger.info(f"[EmailMonitor] Descargando {len(adjuntos)} adjunto(s)...")
            
            comprobantes_dispersion = []
            upload_dir = Path("/app/backend/uploads/comprobantes_dispersion")
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            for adjunto in adjuntos:
                # Solo descargar PDFs (comprobantes)
                if not adjunto['filename'].lower().endswith('.pdf'):
                    logger.info(f"[EmailMonitor] Saltando adjunto no-PDF: {adjunto['filename']}")
                    continue
                
                logger.info(f"[EmailMonitor] Descargando: {adjunto['filename']}")
                
                # Descargar adjunto
                file_data = self.gmail_service.get_attachment(message_id, adjunto['attachment_id'])
                
                if not file_data:
                    logger.error(f"[EmailMonitor] No se pudo descargar {adjunto['filename']}")
                    continue
                
                # Guardar archivo
                safe_filename = f"{operacion_id}_{adjunto['filename']}"
                file_path = upload_dir / safe_filename
                
                with open(file_path, 'wb') as f:
                    f.write(file_data)
                
                logger.info(f"[EmailMonitor] ✅ Guardado: {file_path}")
                
                comprobantes_dispersion.append({
                    "nombre_archivo": adjunto['filename'],
                    "ruta": str(file_path),
                    "tamano_bytes": len(file_data),
                    "fecha_descarga": datetime.now(timezone.utc).isoformat()
                })
            
            if not comprobantes_dispersion:
                logger.warning(f"[EmailMonitor] No se descargó ningún comprobante PDF para operación {operacion_id}")
                return False
            
            # 3. Actualizar estado de la operación
            logger.info(f"[EmailMonitor] Actualizando estado de operación {operacion_id} a 'dispersada_proveedor'")
            
            await db.solicitudes_netcash.update_one(
                {"id": operacion_id},
                {
                    "$set": {
                        "estado": "dispersada_proveedor",
                        "comprobantes_dispersion": comprobantes_dispersion,
                        "fecha_dispersion_proveedor": datetime.now(timezone.utc),
                        "email_respuesta_tesoreria": {
                            "message_id": message_id,
                            "thread_id": mensaje_data.get('thread_id'),
                            "from": mensaje_data.get('from'),
                            "subject": mensaje_data.get('subject'),
                            "fecha_recibido": datetime.now(timezone.utc).isoformat()
                        }
                    }
                }
            )
            
            logger.info(f"[EmailMonitor] ✅ Estado actualizado correctamente")
            
            # 4. Notificar a Ana y al cliente
            await self._notificar_dispersion(solicitud, comprobantes_dispersion)
            
            return True
        
        except Exception as e:
            logger.error(f"[EmailMonitor] Error procesando respuesta para {operacion_id}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def _notificar_dispersion(self, solicitud: Dict, comprobantes: List[Dict]):
        """
        Notifica a Ana y al cliente que la dispersión fue completada
        
        Args:
            solicitud: Datos de la solicitud
            comprobantes: Lista de comprobantes de dispersión descargados
        """
        operacion_id = solicitud.get('id')
        folio_mbco = solicitud.get('folio_mbco', 'SIN_FOLIO')
        
        logger.info(f"[EmailMonitor] Notificando dispersión para operación {operacion_id}")
        
        # Obtener cliente para notificación
        cliente_id = solicitud.get('cliente_id')
        cliente = await db.clientes.find_one({"id": cliente_id}, {"_id": 0})
        
        # Importar el bot de Telegram para enviar notificaciones
        try:
            from telegram_bot import telegram_bot
            
            # Notificación a Ana
            ana_chat_id = os.getenv('ANA_TELEGRAM_CHAT_ID')
            if ana_chat_id and telegram_bot.application:
                mensaje_ana = f"✅ **Operación dispersada al proveedor**\n\n"
                mensaje_ana += f"📋 **Folio:** {folio_mbco}\n"
                mensaje_ana += f"👤 **Cliente:** {cliente.get('nombre_completo', 'N/A') if cliente else 'N/A'}\n"
                mensaje_ana += f"💰 **Total:** ${solicitud.get('total_depositado', 0):,.2f}\n"
                mensaje_ana += f"📎 **Comprobantes recibidos:** {len(comprobantes)}\n\n"
                mensaje_ana += f"Los comprobantes de dispersión se recibieron de Tesorería y la operación está lista para continuar."
                
                try:
                    await telegram_bot.application.bot.send_message(
                        chat_id=ana_chat_id,
                        text=mensaje_ana,
                        parse_mode='Markdown'
                    )
                    logger.info(f"[EmailMonitor] ✅ Notificación enviada a Ana")
                except Exception as e:
                    logger.error(f"[EmailMonitor] Error enviando notificación a Ana: {str(e)}")
            
            # Notificación al cliente (si tiene telegram_id)
            if cliente and cliente.get('telegram_id'):
                telegram_id = cliente.get('telegram_id')
                
                mensaje_cliente = f"✅ **¡Tu operación NetCash está en proceso!**\n\n"
                mensaje_cliente += f"📋 **Folio:** {folio_mbco}\n"
                mensaje_cliente += f"💰 **Total:** ${solicitud.get('total_depositado', 0):,.2f}\n\n"
                mensaje_cliente += f"Tus depósitos ya fueron enviados a NetCash para la generación de ligas.\n\n"
                mensaje_cliente += f"Te notificaremos cuando tus ligas estén listas."
                
                try:
                    await telegram_bot.application.bot.send_message(
                        chat_id=telegram_id,
                        text=mensaje_cliente,
                        parse_mode='Markdown'
                    )
                    logger.info(f"[EmailMonitor] ✅ Notificación enviada al cliente {cliente_id}")
                except Exception as e:
                    logger.error(f"[EmailMonitor] Error enviando notificación al cliente: {str(e)}")
        
        except Exception as e:
            logger.error(f"[EmailMonitor] Error enviando notificaciones Telegram: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())


# Instancia global del servicio
tesoreria_email_monitor = TesoreriaEmailMonitorService()
