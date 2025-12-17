"""
Servicio de envío de correos a DNS (Proveedor) - P4A

Este servicio envía automáticamente los comprobantes de pago al proveedor DNS
cuando Tesorería ha pagado correctamente (después de validar el comprobante).
"""

import os
import logging
from typing import Dict, List
from pathlib import Path

# Usar SMTP en lugar de Gmail OAuth (no expira)
from smtp_service import smtp_service

logger = logging.getLogger(__name__)

# Variables de entorno
DNS_EMAIL = os.getenv('NETCASH_DNS_EMAIL', 'dns@proveedor.com')  # Configurable
NETCASH_INTERNAL_EMAIL = os.getenv('NETCASH_INTERNAL_EMAIL', 'netcash@mbco.mx')  # Para CC


class DNSEmailService:
    """Servicio para enviar correos al proveedor DNS"""
    
    def __init__(self):
        self.dns_email = DNS_EMAIL
        self.internal_email = NETCASH_INTERNAL_EMAIL
        logger.info(f"[DNSEmail-P4A] Servicio inicializado")
        logger.info(f"[DNSEmail-P4A] Email DNS: {self.dns_email}")
        logger.info(f"[DNSEmail-P4A] Email interno: {self.internal_email}")
    
    async def enviar_comprobantes_a_dns(
        self,
        solicitud: Dict,
        comprobantes_paths: List[str]
    ) -> bool:
        """
        Envía correo al proveedor DNS con los comprobantes de pago
        
        Args:
            solicitud: Dict con datos de la solicitud NetCash
            comprobantes_paths: Lista de rutas a los archivos de comprobantes
        
        Returns:
            True si se envió correctamente
        """
        logger.info(f"[DNSEmail-P4A] Iniciando envío de correo a DNS")
        logger.info(f"[DNSEmail-P4A] Operación: {solicitud.get('id')}")
        logger.info(f"[DNSEmail-P4A] Folio MBco: {solicitud.get('folio_mbco')}")
        
        try:
            # Extraer datos de la solicitud
            folio_netcash = solicitud.get('id', 'N/A')
            folio_mbco = solicitud.get('folio_mbco', 'N/A')
            cliente_nombre = solicitud.get('cliente_nombre', 'N/A')
            idmex = solicitud.get('idmex_reportado', 'N/A')
            capital_total = solicitud.get('monto_ligas', 0)
            comision_total = solicitud.get('comision_dns_calculada', 0)
            numero_ligas = solicitud.get('cantidad_ligas_reportada', 0)
            
            # Construir asunto
            asunto = f"NetCash – Pago a proveedor – {folio_netcash} / MBco {folio_mbco}"
            
            # Construir cuerpo del correo
            cuerpo = self._generar_cuerpo_correo_dns(
                folio_netcash=folio_netcash,
                folio_mbco=folio_mbco,
                cliente_nombre=cliente_nombre,
                idmex=idmex,
                capital_total=capital_total,
                comision_total=comision_total,
                numero_ligas=numero_ligas
            )
            
            # Enviar correo con adjuntos
            logger.info(f"[DNSEmail-P4A] Enviando correo a {self.dns_email}")
            logger.info(f"[DNSEmail-P4A] Adjuntos: {len(comprobantes_paths)}")
            
            email_info = await gmail_service.enviar_correo_con_adjuntos(
                destinatario=self.dns_email,
                asunto=asunto,
                cuerpo=cuerpo,
                adjuntos=comprobantes_paths,
                cc=[self.internal_email] if self.internal_email else None
            )
            
            if email_info:
                logger.info(f"[DNSEmail-P4A] ✅ Correo enviado exitosamente a DNS")
                logger.info(f"[DNSEmail-P4A] Thread ID: {email_info.get('thread_id')}")
                logger.info(f"[DNSEmail-P4A] Message ID: {email_info.get('message_id')}")
                return True
            else:
                logger.error(f"[DNSEmail-P4A] ❌ No se obtuvo confirmación de envío")
                return False
            
        except Exception as e:
            logger.exception(f"[DNSEmail-P4A] ❌ Error al enviar correo a DNS")
            return False
    
    def _generar_cuerpo_correo_dns(
        self,
        folio_netcash: str,
        folio_mbco: str,
        cliente_nombre: str,
        idmex: str,
        capital_total: float,
        comision_total: float,
        numero_ligas: int
    ) -> str:
        """
        Genera el cuerpo del correo para DNS según especificación P4A
        
        Returns:
            Cuerpo del correo en formato HTML
        """
        cuerpo = "<html><body>"
        cuerpo += "<p>Hola,</p>"
        cuerpo += "<p>Les compartimos los pagos realizados correspondientes a la siguiente operación NetCash:</p>"
        cuerpo += "<br>"
        cuerpo += "<ul>"
        cuerpo += f"<li><strong>Folio NetCash:</strong> {folio_netcash}</li>"
        cuerpo += f"<li><strong>Folio MBco:</strong> {folio_mbco}</li>"
        cuerpo += f"<li><strong>Cliente:</strong> {cliente_nombre}</li>"
        cuerpo += f"<li><strong>IDMEX:</strong> {idmex}</li>"
        cuerpo += f"<li><strong>Monto total enviado al proveedor (capital):</strong> ${capital_total:,.2f}</li>"
        cuerpo += f"<li><strong>Comisión DNS:</strong> ${comision_total:,.2f}</li>"
        cuerpo += f"<li><strong>Número de ligas solicitadas:</strong> {numero_ligas}</li>"
        cuerpo += "</ul>"
        cuerpo += "<br>"
        cuerpo += "<p>Se adjuntan los comprobantes de pago realizados desde MBco para que puedan generar las ligas NetCash correspondientes.</p>"
        cuerpo += "<br>"
        cuerpo += "<p><strong>Por favor, respondan este mismo correo adjuntando el PDF con las ligas NetCash generadas para esta operación.</strong></p>"
        cuerpo += "<br>"
        cuerpo += "<p>Gracias,<br>Tesorería MBco</p>"
        cuerpo += "</body></html>"
        
        return cuerpo
    
    async def responder_a_tesoreria_con_error(
        self,
        thread_id: str,
        message_id: str,
        folio_netcash: str,
        folio_mbco: str,
        cliente_nombre: str,
        idmex: str,
        errores: List[str]
    ) -> bool:
        """
        Responde a Tesorería en el mismo hilo indicando errores de validación
        
        Args:
            thread_id: ID del hilo del correo original
            message_id: ID del mensaje al que se responde
            folio_netcash: Folio NetCash
            folio_mbco: Folio MBco
            cliente_nombre: Nombre del cliente
            idmex: IDMEX
            errores: Lista de mensajes de error
        
        Returns:
            True si se envió correctamente
        """
        logger.info(f"[DNSEmail-P4A] Enviando respuesta de error a Tesorería")
        logger.info(f"[DNSEmail-P4A] Thread ID: {thread_id}")
        logger.info(f"[DNSEmail-P4A] Errores: {len(errores)}")
        
        try:
            # Construir asunto
            asunto = f"Error en validación de comprobante – {folio_netcash} / MBco {folio_mbco}"
            
            # Construir cuerpo con lista de errores
            cuerpo = "<html><body>"
            cuerpo += "<p>Hola,</p>"
            cuerpo += "<p>Al validar el comprobante de pago de la operación:</p>"
            cuerpo += "<br>"
            cuerpo += "<ul>"
            cuerpo += f"<li><strong>Folio NetCash:</strong> {folio_netcash}</li>"
            cuerpo += f"<li><strong>Folio MBco:</strong> {folio_mbco}</li>"
            cuerpo += f"<li><strong>Cliente:</strong> {cliente_nombre}</li>"
            cuerpo += f"<li><strong>IDMEX:</strong> {idmex}</li>"
            cuerpo += "</ul>"
            cuerpo += "<br>"
            cuerpo += "<p><strong>Se detectaron los siguientes errores:</strong></p>"
            cuerpo += "<ul>"
            for error in errores:
                cuerpo += f"<li>{error}</li>"
            cuerpo += "</ul>"
            cuerpo += "<br>"
            cuerpo += "<p>Por favor, corrige el pago o el comprobante y vuelve a enviarlo para que podamos continuar con el proceso de ligas NetCash.</p>"
            cuerpo += "<br>"
            cuerpo += "<p>Gracias,<br>Sistema NetCash MBco</p>"
            cuerpo += "</body></html>"
            
            # Enviar respuesta en el mismo hilo
            logger.info(f"[DNSEmail-P4A] Enviando respuesta a Tesorería")
            
            email_info = await gmail_service.enviar_correo_respuesta(
                thread_id=thread_id,
                message_id=message_id,
                asunto=asunto,
                cuerpo=cuerpo
            )
            
            if email_info:
                logger.info(f"[DNSEmail-P4A] ✅ Respuesta de error enviada a Tesorería")
                return True
            else:
                logger.error(f"[DNSEmail-P4A] ❌ No se pudo enviar respuesta de error")
                return False
            
        except Exception as e:
            logger.exception(f"[DNSEmail-P4A] ❌ Error al enviar respuesta de error a Tesorería")
            return False


# Instancia global del servicio
dns_email_service = DNSEmailService()
