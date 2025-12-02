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
        Procesa la respuesta de Tesorería para una operación específica - P4A
        
        Flujo P4A:
        1. Descargar comprobantes
        2. Validar capital, comisión y concepto
        3a. Si OK → Guardar y enviar a DNS
        3b. Si error → Responder a Tesorería con detalles
        
        Args:
            operacion_id: ID de la solicitud NetCash
            mensaje_data: Datos del mensaje parseado
            message_id: ID del mensaje de Gmail
        
        Returns:
            True si se procesó correctamente
        """
        logger.info(f"[EmailMonitor-P4A] ========== INICIANDO PROCESAMIENTO P4A ==========")
        logger.info(f"[EmailMonitor-P4A] Operación: {operacion_id}")
        logger.info(f"[EmailMonitor-P4A] Message ID: {message_id}")
        
        try:
            # 1. Obtener datos de la operación
            solicitud = await db.solicitudes_netcash.find_one(
                {"id": operacion_id},
                {"_id": 0}
            )
            
            if not solicitud:
                logger.error(f"[EmailMonitor-P4A] ❌ Operación {operacion_id} no encontrada")
                return False
            
            logger.info(f"[EmailMonitor-P4A] Estado actual: {solicitud.get('estado')}")
            logger.info(f"[EmailMonitor-P4A] Folio MBco: {solicitud.get('folio_mbco')}")
            
            # 2. Descargar comprobantes adjuntos
            adjuntos = mensaje_data.get('attachments', [])
            
            if not adjuntos:
                logger.warning(f"[EmailMonitor-P4A] ⚠️ No hay adjuntos en la respuesta")
                return False
            
            logger.info(f"[EmailMonitor-P4A] Descargando {len(adjuntos)} adjunto(s)...")
            
            comprobantes_paths = []
            upload_dir = Path("/app/backend/uploads/comprobantes_pago_proveedor")
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            folio_concepto = solicitud.get('folio_mbco', '').replace('-', 'x')
            
            for idx, adjunto in enumerate(adjuntos, 1):
                # Solo PDFs
                if not adjunto['filename'].lower().endswith('.pdf'):
                    logger.info(f"[EmailMonitor-P4A] Saltando no-PDF: {adjunto['filename']}")
                    continue
                
                logger.info(f"[EmailMonitor-P4A] Descargando: {adjunto['filename']}")
                
                # Descargar
                file_data = self.gmail_service.get_attachment(message_id, adjunto['attachment_id'])
                
                if not file_data:
                    logger.error(f"[EmailMonitor-P4A] ❌ No se pudo descargar {adjunto['filename']}")
                    continue
                
                # Guardar con nombre según P4A: {folio_concepto}_pago_proveedor_{N}.pdf
                extension = Path(adjunto['filename']).suffix
                safe_filename = f"{folio_concepto}_pago_proveedor_{idx}{extension}"
                file_path = upload_dir / safe_filename
                
                with open(file_path, 'wb') as f:
                    f.write(file_data)
                
                logger.info(f"[EmailMonitor-P4A] ✅ Guardado: {safe_filename}")
                
                comprobantes_paths.append(str(file_path))
            
            if not comprobantes_paths:
                logger.error(f"[EmailMonitor-P4A] ❌ No se descargó ningún comprobante PDF")
                return False
            
            # 3. ⭐ VALIDACIONES P4A ⭐
            logger.info(f"[EmailMonitor-P4A] ========== INICIANDO VALIDACIONES ==========")
            
            # Importar servicio de validación
            from comprobante_pago_validator_service import comprobante_pago_validator
            from decimal import Decimal
            
            # Obtener datos esperados de la solicitud
            capital_esperado = Decimal(str(solicitud.get('monto_ligas', 0)))
            comision_esperada = Decimal(str(solicitud.get('comision_dns_calculada', 0)))
            
            logger.info(f"[EmailMonitor-P4A] Validando contra:")
            logger.info(f"[EmailMonitor-P4A] - Capital esperado: ${capital_esperado}")
            logger.info(f"[EmailMonitor-P4A] - Comisión esperada: ${comision_esperada}")
            logger.info(f"[EmailMonitor-P4A] - Concepto esperado: {folio_concepto}")
            
            # Validar cada comprobante (o todos juntos si es uno solo)
            # Para simplificar, validamos el primer PDF (el principal)
            es_valido, errores, datos_extraidos = comprobante_pago_validator.validar_comprobante(
                pdf_path=comprobantes_paths[0],
                capital_esperado=capital_esperado,
                comision_esperada=comision_esperada,
                folio_concepto=folio_concepto
            )
            
            logger.info(f"[EmailMonitor-P4A] ========== RESULTADO VALIDACIÓN ==========")
            logger.info(f"[EmailMonitor-P4A] Válido: {es_valido}")
            if errores:
                logger.error(f"[EmailMonitor-P4A] Errores: {errores}")
            
            # 4a. Si las validaciones PASAN → Enviar a DNS
            if es_valido:
                logger.info(f"[EmailMonitor-P4A] ✅ Todas las validaciones pasaron")
                logger.info(f"[EmailMonitor-P4A] Procediendo a enviar correo a DNS...")
                
                # Importar servicio DNS
                from dns_email_service import dns_email_service
                
                # Enviar correo a DNS con comprobantes
                envio_exitoso = await dns_email_service.enviar_comprobantes_a_dns(
                    solicitud=solicitud,
                    comprobantes_paths=comprobantes_paths
                )
                
                if envio_exitoso:
                    # Actualizar estado en BD
                    await db.solicitudes_netcash.update_one(
                        {"id": operacion_id},
                        {
                            "$set": {
                                "estado": "correo_enviado_a_proveedor",
                                "pagado_a_dns": True,
                                "pagos_proveedor": {
                                    "fecha_recepcion": datetime.now(timezone.utc).isoformat(),
                                    "correo_tesoreria": mensaje_data.get('from'),
                                    "comprobantes": [Path(p).name for p in comprobantes_paths],
                                    "capital_total_pdf": datos_extraidos.get('capital_total_pdf'),
                                    "comision_total_pdf": datos_extraidos.get('comision_total_pdf')
                                },
                                "email_respuesta_tesoreria": {
                                    "message_id": message_id,
                                    "thread_id": mensaje_data.get('thread_id'),
                                    "from": mensaje_data.get('from'),
                                    "subject": mensaje_data.get('subject'),
                                    "fecha_recibido": datetime.now(timezone.utc).isoformat()
                                },
                                "validacion_pagos_proveedor": {
                                    "estado": "validado",
                                    "fecha_validacion": datetime.now(timezone.utc).isoformat(),
                                    "datos_extraidos": datos_extraidos
                                }
                            }
                        }
                    )
                    
                    logger.info(f"[EmailMonitor-P4A] ✅✅ PROCESO COMPLETADO EXITOSAMENTE ✅✅")
                    logger.info(f"[EmailMonitor-P4A] - Comprobantes guardados: {len(comprobantes_paths)}")
                    logger.info(f"[EmailMonitor-P4A] - Correo enviado a DNS")
                    logger.info(f"[EmailMonitor-P4A] - Estado actualizado: correo_enviado_a_proveedor")
                    
                    return True
                else:
                    logger.error(f"[EmailMonitor-P4A] ❌ Error al enviar correo a DNS")
                    # Guardar flag de pendiente
                    await db.solicitudes_netcash.update_one(
                        {"id": operacion_id},
                        {"$set": {"correo_dns_pendiente": True}}
                    )
                    return False
            
            # 4b. Si las validaciones FALLAN → Responder a Tesorería con errores
            else:
                logger.error(f"[EmailMonitor-P4A] ❌ Validaciones fallaron")
                logger.error(f"[EmailMonitor-P4A] Respondiendo a Tesorería con detalles de errores...")
                
                # Importar servicio DNS (maneja respuestas de error también)
                from dns_email_service import dns_email_service
                
                # Responder a Tesorería en el mismo hilo
                respuesta_exitosa = await dns_email_service.responder_a_tesoreria_con_error(
                    thread_id=mensaje_data.get('thread_id'),
                    message_id=message_id,
                    folio_netcash=solicitud.get('id'),
                    folio_mbco=solicitud.get('folio_mbco'),
                    cliente_nombre=solicitud.get('cliente_nombre', 'N/A'),
                    idmex=solicitud.get('idmex_reportado', 'N/A'),
                    errores=errores
                )
                
                # Guardar errores en BD (sin avanzar estado)
                await db.solicitudes_netcash.update_one(
                    {"id": operacion_id},
                    {
                        "$set": {
                            "validacion_pagos_proveedor": {
                                "estado": "error",
                                "errores": errores,
                                "fecha_ultima_validacion": datetime.now(timezone.utc).isoformat(),
                                "capital_total_pdf": datos_extraidos.get('capital_total_pdf'),
                                "comision_total_pdf": datos_extraidos.get('comision_total_pdf'),
                                "conceptos_pdf": datos_extraidos.get('conceptos_pdf', [])
                            },
                            "comprobantes_pago_proveedor_rechazados": [Path(p).name for p in comprobantes_paths]
                        }
                    }
                )
                
                if respuesta_exitosa:
                    logger.info(f"[EmailMonitor-P4A] ✅ Respuesta de error enviada a Tesorería")
                else:
                    logger.error(f"[EmailMonitor-P4A] ❌ No se pudo enviar respuesta de error a Tesorería")
                
                # Retornar False porque no se completó el proceso
                return False
        
        except Exception as e:
            logger.exception(f"[EmailMonitor-P4A] ❌❌ Error crítico en procesamiento P4A")
            
            # Intentar responder a Tesorería con error técnico
            try:
                from dns_email_service import dns_email_service
                await dns_email_service.responder_a_tesoreria_con_error(
                    thread_id=mensaje_data.get('thread_id'),
                    message_id=message_id,
                    folio_netcash=operacion_id,
                    folio_mbco=solicitud.get('folio_mbco', 'N/A') if solicitud else 'N/A',
                    cliente_nombre='N/A',
                    idmex='N/A',
                    errores=[f"Error técnico al procesar comprobante: {str(e)}"]
                )
            except:
                logger.error(f"[EmailMonitor-P4A] No se pudo enviar respuesta de error técnico")
            
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
