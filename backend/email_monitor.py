"""Monitor de correos de Gmail para NetCash
Procesa correos entrantes y crea operaciones NetCash
"""

import os
import re
import time
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional
from uuid import uuid4
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from gmail_service import gmail_service
from cuenta_deposito_service import cuenta_deposito_service

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
        
        # NUEVA VALIDACIÓN 1: Verificar que el asunto contenga "NetCash"
        if not self._has_netcash_in_subject(msg_data['subject']):
            logger.warning(f"[EmailMonitor] Asunto sin 'NetCash' - enviando correo de ajuste")
            await self._send_subject_missing_response(
                email_cliente,
                msg_data['thread_id']
            )
            self.gmail.mark_as_read(message_id)
            self.gmail.add_label(message_id, "NETCASH/ASUNTO_INCORRECTO")
            return
        
        # Extraer información del cuerpo
        info_extraida = self._extract_info_from_body(msg_data['body'])
        
        # Descargar adjuntos
        archivos_adjuntos = await self._download_attachments(
            message_id, 
            msg_data['attachments']
        )
        
        # NUEVA VALIDACIÓN 2: Validar campos y obtener lista de faltantes
        info_completa, campos_faltantes = await self._validate_info_detailed(
            email_cliente,
            archivos_adjuntos,
            info_extraida
        )
        
        logger.info(f"[EmailMonitor] Info completa: {info_completa}")
        if not info_completa:
            logger.info(f"[EmailMonitor] Campos faltantes: {campos_faltantes}")
        
        # Si la información está completa, crear operación
        if info_completa:
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
            
            # Enviar respuesta de éxito
            await self._send_success_response(
                email_cliente,
                msg_data['thread_id'],
                operacion['clave_operacion']
            )
            self.gmail.add_label(message_id, "NETCASH/PROCESADO")
            
            logger.info(f"[EmailMonitor] Operación {operacion['clave_operacion']} creada desde email")
        else:
            # Enviar respuesta dinámica de información incompleta
            await self._send_incomplete_response_dynamic(
                email_cliente,
                msg_data['thread_id'],
                campos_faltantes
            )
            self.gmail.add_label(message_id, "NETCASH/FALTA_INFO")
        
        # Marcar como leído
        self.gmail.mark_as_read(message_id)
    
    def _has_netcash_in_subject(self, subject: str) -> bool:
        """Verifica si el asunto contiene la palabra 'NetCash' (case-insensitive)"""
        return 'netcash' in subject.lower()
    
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
            'referencia': None,
            'beneficiario': None,
            'cantidad_ligas': None
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
        idmex_match = re.search(r'IDMEX[:\s]+([0-9A-Za-z-]+)', body, re.IGNORECASE)
        if idmex_match:
            info['idmex'] = idmex_match.group(1)
        
        # Buscar referencia
        ref_match = re.search(r'(?:referencia|operación)[:\s]+([A-Za-z0-9-]+)', body, re.IGNORECASE)
        if ref_match:
            info['referencia'] = ref_match.group(1)
        
        # Buscar beneficiario
        beneficiario_match = re.search(r'(?:beneficiario|titular|nombre)[:\s]+([A-Za-zÁÉÍÓÚáéíóúÑñ\s]+(?:[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+)?)', body, re.IGNORECASE)
        if beneficiario_match:
            info['beneficiario'] = beneficiario_match.group(1).strip()
        
        # Buscar cantidad de ligas
        ligas_match = re.search(r'(?:liga|ligas|cantidad de ligas|número de ligas)[:\s]+([0-9]+)', body, re.IGNORECASE)
        if ligas_match:
            try:
                info['cantidad_ligas'] = int(ligas_match.group(1))
            except:
                pass
        
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
    
    async def _validate_info_detailed(self, 
                                      email_cliente: str, 
                                      archivos: List, 
                                      info_extraida: Dict) -> Tuple[bool, List[str]]:
        """Valida información y devuelve lista de campos faltantes"""
        campos_faltantes = []
        
        # 1. Validar adjuntos (comprobantes)
        if len(archivos) == 0:
            campos_faltantes.append('adjuntos')
        
        # 2. Validar nombre beneficiario
        if not info_extraida.get('beneficiario'):
            campos_faltantes.append('beneficiario')
        
        # 3. Validar IDMEX
        if not info_extraida.get('idmex'):
            campos_faltantes.append('idmex')
        
        # 4. Validar cantidad de ligas
        if not info_extraida.get('cantidad_ligas'):
            campos_faltantes.append('cantidad_ligas')
        
        info_completa = len(campos_faltantes) == 0
        
        return info_completa, campos_faltantes
    
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
            "beneficiario_reportado": info_extraida.get('beneficiario'),
            "cantidad_ligas_reportada": info_extraida.get('cantidad_ligas'),
            "archivos_adjuntos": archivos_adjuntos,
            "comprobantes": [],  # Se procesarán después
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Guardar en la base de datos
        await db.operaciones.insert_one(operacion)
        
        logger.info(f"[EmailMonitor] Operación {clave_operacion} creada en BD")
        
        return operacion
    
    async def _get_cuenta_pago(self) -> Optional[Dict]:
        """Obtiene la cuenta de pago activa para recepción de clientes"""
        try:
            cuenta = await cuenta_deposito_service.obtener_cuenta_activa()
            return cuenta
        except Exception as e:
            logger.error(f"[EmailMonitor] Error obteniendo cuenta de pago: {str(e)}")
            return None
    
    def _format_cuenta_pago(self, cuenta: Optional[Dict]) -> str:
        """Formatea la información de la cuenta de pago"""
        if not cuenta:
            return "Recuerda que los depósitos para NetCash deben realizarse a la cuenta autorizada de recepción. Si aún no la tienes a la mano, por favor consúltala en tu panel de NetCash o con tu ejecutivo."
        
        # Formatear usando el servicio
        texto = "Recuerda realizar tu depósito a la cuenta autorizada:\n"
        texto += f"Banco: {cuenta.get('banco', 'N/A')}\n"
        texto += f"CLABE: {cuenta.get('clabe', 'N/A')}\n"
        texto += f"Beneficiario: {cuenta.get('beneficiario', 'N/A')}"
        
        return texto
    
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
    
    async def _send_incomplete_response_dynamic(self, to: str, thread_id: str, campos_faltantes: List[str]):
        """Envía respuesta dinámica de información incompleta según campos faltantes"""
        
        # Construir lista dinámica de faltantes
        lista_faltantes = []
        
        if 'adjuntos' in campos_faltantes:
            lista_faltantes.append("• Comprobantes claros y legibles en PDF, JPG o PNG (adjunta todos los relacionados con la operación).")
        
        if 'beneficiario' in campos_faltantes:
            lista_faltantes.append("• El nombre completo del beneficiario al que se aplicará el pago.")
        
        if 'idmex' in campos_faltantes:
            lista_faltantes.append("• El IDMEX o identificador de la operación que usas con MBco.")
        
        if 'cantidad_ligas' in campos_faltantes:
            lista_faltantes.append("• La cantidad de ligas NetCash que necesitas para esta operación.")
        
        # Construir mensaje
        subject = "NetCash – Hace falta información para tu operación"
        
        body = """Hola,

Recibimos tu correo para operar con NetCash, pero todavía nos falta información para poder registrar correctamente la operación.

En tu próximo correo por favor incluye lo siguiente que nos falta:
"""
        
        # Agregar lista de faltantes
        for item in lista_faltantes:
            body += item + "\n"
        
        # Obtener y agregar información de cuenta de pago
        cuenta = await self._get_cuenta_pago()
        cuenta_texto = self._format_cuenta_pago(cuenta)
        
        body += f"""
Si necesitas apoyo para completar la información, simplemente responde a este mismo correo escribiendo la palabra "AYUDA" y nuestro equipo se pondrá en contacto contigo.

{cuenta_texto}

En cuanto tengamos la información completa, registramos la operación y te confirmamos por este mismo medio.

Quedamos al pendiente.

Equipo NetCash"""
        
        self.gmail.send_reply(to, subject, body, thread_id)
        logger.info(f"[EmailMonitor] Respuesta dinámica de info incompleta enviada a {to}")
        logger.info(f"[EmailMonitor] Campos faltantes notificados: {campos_faltantes}")
    
    async def _send_subject_missing_response(self, to: str, thread_id: str):
        """Envía respuesta cuando el asunto no contiene 'NetCash'"""
        subject = "NetCash – Ajuste en el asunto de tu correo"
        body = """Hola,

Recibimos tu correo, pero para poder procesar correctamente tu solicitud en NetCash es necesario que el asunto incluya la palabra "NetCash".

Por favor vuelve a enviar tu correo a esta misma dirección, asegurándote de que el asunto contenga "NetCash" (puede ir acompañado de la referencia que tú quieras).

Ejemplos:
• NetCash – Pago proveedor
• NetCash – Nómina semana 15

Una vez que recibamos tu correo con el asunto correcto, podremos continuar con el proceso.

Equipo NetCash"""
        
        self.gmail.send_reply(to, subject, body, thread_id)
        logger.info(f"[EmailMonitor] Respuesta de asunto incorrecto enviada a {to}")


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
