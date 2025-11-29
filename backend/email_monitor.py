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

# Contacto Ana
ANA_EMAIL = "gestion.ngdl@gmail.com"
ANA_WHATSAPP = "+52 33 1218 6685"


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
        
        message = self.gmail.get_message(message_id)
        if not message:
            logger.error(f"[EmailMonitor] No se pudo obtener el mensaje {message_id}")
            return
        
        msg_data = self.gmail.parse_message(message)
        email_cliente = self._extract_email(msg_data['from'])
        
        logger.info(f"[EmailMonitor] ✉️  Email de: {email_cliente}")
        logger.info(f"[EmailMonitor] 📝 Asunto: {msg_data['subject']}")
        logger.info(f"[EmailMonitor] 📎 Adjuntos: {len(msg_data['attachments'])}")
        
        # VALIDACIÓN 1: Verificar que el asunto contenga "NetCash"
        if not self._has_netcash_in_subject(msg_data['subject']):
            logger.warning(f"[EmailMonitor] ⚠️  Asunto sin 'NetCash'")
            await self._send_subject_missing_response(
                email_cliente,
                msg_data['subject'],
                msg_data['thread_id']
            )
            self.gmail.mark_as_read(message_id)
            self.gmail.add_label(message_id, "NETCASH/ASUNTO_INCORRECTO")
            return
        
        # VALIDACIÓN 2: Verificar que el cliente esté dado de alta
        cliente = await self._buscar_cliente_por_email(email_cliente)
        
        if not cliente:
            logger.warning(f"[EmailMonitor] ⛔ Cliente NO identificado: {email_cliente}")
            await self._send_cliente_no_identificado_response(
                email_cliente,
                msg_data['subject'],
                msg_data['thread_id']
            )
            self.gmail.mark_as_read(message_id)
            self.gmail.add_label(message_id, "NETCASH/CLIENTE_NO_IDENTIFICADO")
            return
        
        logger.info(f"[EmailMonitor] ✅ Cliente identificado: {cliente.get('nombre')} (estado: {cliente.get('estado')})")
        
        # Descargar adjuntos
        archivos_adjuntos = await self._download_attachments(
            message_id, 
            msg_data['attachments'],
            email_cliente
        )
        
        # Extraer información del cuerpo con reglas mejoradas
        info_extraida = self._extract_info_from_body_mejorado(msg_data['body'])
        
        # CONVERSACIÓN GUIADA: Verificar si ya existe operación
        operacion_existente = await self._buscar_operacion_por_thread(msg_data['thread_id'])
        
        # Condiciones mínimas para crear operación
        cumple_minimos = self._cumple_minimos_para_operacion(
            archivos_adjuntos,
            info_extraida
        )
        
        if operacion_existente:
            logger.info(f"[EmailMonitor] 🔄 Thread existente - actualizando operación {operacion_existente['clave_operacion']}")
            info_completa, campos_faltantes = await self._validate_info_consolidada(
                operacion_existente,
                archivos_adjuntos,
                info_extraida
            )
            
            if info_completa:
                await self._actualizar_operacion(
                    operacion_existente['id'],
                    archivos_adjuntos,
                    info_extraida
                )
                
                await self._send_success_response(
                    email_cliente,
                    msg_data['subject'],
                    msg_data['thread_id'],
                    operacion_existente['clave_operacion']
                )
                self.gmail.add_label(message_id, "NETCASH/PROCESADO")
                logger.info(f"[EmailMonitor] ✅ Operación {operacion_existente['clave_operacion']} completada")
            else:
                await self._send_incomplete_response_dynamic(
                    email_cliente,
                    msg_data['subject'],
                    msg_data['thread_id'],
                    campos_faltantes
                )
                self.gmail.add_label(message_id, "NETCASH/FALTA_INFO")
        else:
            # Primera vez
            if not cumple_minimos:
                logger.warning(f"[EmailMonitor] ⚠️  No cumple mínimos para crear operación")
                await self._send_guia_minimos_response(
                    email_cliente,
                    msg_data['subject'],
                    msg_data['thread_id'],
                    archivos_adjuntos,
                    info_extraida
                )
                self.gmail.mark_as_read(message_id)
                self.gmail.add_label(message_id, "NETCASH/INCOMPLETO_SIN_OPERACION")
                return
            
            # Validación detallada
            info_completa, campos_faltantes = await self._validate_info_detailed(
                email_cliente,
                archivos_adjuntos,
                info_extraida
            )
            
            logger.info(f"[EmailMonitor] Info completa: {info_completa}")
            if not info_completa:
                logger.info(f"[EmailMonitor] Campos faltantes: {campos_faltantes}")
            
            if info_completa:
                operacion = await self._create_netcash_operation(
                    email_cliente=email_cliente,
                    cliente_id=cliente.get('id'),
                    cliente_nombre=cliente.get('nombre'),
                    asunto=msg_data['subject'],
                    cuerpo=msg_data['body'],
                    archivos_adjuntos=archivos_adjuntos,
                    info_extraida=info_extraida,
                    mensaje_id=message_id,
                    thread_id=msg_data['thread_id']
                )
                
                await self._send_success_response(
                    email_cliente,
                    msg_data['subject'],
                    msg_data['thread_id'],
                    operacion['clave_operacion']
                )
                self.gmail.add_label(message_id, "NETCASH/PROCESADO")
                
                logger.info(f"[EmailMonitor] ✅ Operación {operacion['clave_operacion']} creada")
            else:
                # Crear operación parcial
                operacion = await self._create_netcash_operation(
                    email_cliente=email_cliente,
                    cliente_id=cliente.get('id'),
                    cliente_nombre=cliente.get('nombre'),
                    asunto=msg_data['subject'],
                    cuerpo=msg_data['body'],
                    archivos_adjuntos=archivos_adjuntos,
                    info_extraida=info_extraida,
                    mensaje_id=message_id,
                    thread_id=msg_data['thread_id']
                )
                
                await self._send_incomplete_response_dynamic(
                    email_cliente,
                    msg_data['subject'],
                    msg_data['thread_id'],
                    campos_faltantes
                )
                self.gmail.add_label(message_id, "NETCASH/FALTA_INFO")
        
        self.gmail.mark_as_read(message_id)
    
    def _has_netcash_in_subject(self, subject: str) -> bool:
        """Verifica si el asunto contiene 'NetCash'"""
        return 'netcash' in subject.lower()
    
    def _extract_email(self, from_header: str) -> str:
        """Extrae email del header From"""
        match = re.search(r'<([^>]+)>', from_header)
        return match.group(1) if match else from_header
    
    def _cumple_minimos_para_operacion(self, archivos: List, info: Dict) -> bool:
        """Verifica condiciones mínimas para crear operación"""
        tiene_adjunto = len(archivos) > 0
        tiene_idmex = self._es_idmex_valido(info.get('idmex'))
        tiene_ligas = info.get('cantidad_ligas') is not None
        
        return tiene_adjunto or (tiene_idmex and tiene_ligas)
    
    def _es_idmex_valido(self, idmex: str) -> bool:
        """Valida IDMEX: exactamente 10 dígitos"""
        if not idmex:
            return False
        return bool(re.match(r'^[0-9]{10}$', str(idmex)))
    
    def _es_nombre_valido(self, nombre: str) -> bool:
        """Valida nombre: mínimo 3 palabras (nombre + 2 apellidos)"""
        if not nombre:
            return False
        
        palabras = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]+", nombre)
        return len(palabras) >= 3
    
    def _detectar_ligas(self, texto: str) -> Optional[int]:
        """Detecta cantidad de ligas con keywords"""
        texto_lower = texto.lower()
        
        # Patterns para detectar ligas
        patterns = [
            r'(\d+)\s*(?:liga|ligas)',
            r'(?:liga|ligas)\s*(\d+)',
            r'(\d+)\s*(?:línea|linea|líneas|lineas)(?:\s*de)?(?:\s*captura)?',
            r'(?:línea|linea|líneas|lineas)(?:\s*de)?(?:\s*captura)?\s*(\d+)',
            r'(\d+)\s*(?:line|lines)(?:\s*de)?(?:\s*captura)?',
            r'(?:line|lines)(?:\s*de)?(?:\s*captura)?\s*(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, texto_lower)
            if match:
                try:
                    return int(match.group(1))
                except:
                    pass
        
        return None
    
    def _extract_info_from_body_mejorado(self, body: str) -> Dict:
        """Extrae información con reglas mejoradas"""
        info = {
            'monto': None,
            'idmex': None,
            'referencia': None,
            'beneficiario': None,
            'cantidad_ligas': None
        }
        
        # IDMEX: exactamente 10 dígitos
        idmex_matches = re.findall(r'\b(\d{10})\b', body)
        if idmex_matches:
            info['idmex'] = idmex_matches[0]
            logger.info(f"[Parser] IDMEX detectado: {info['idmex']}")
        
        # Nombre beneficiario: buscar secuencias de 3+ palabras
        # Buscar líneas que tengan nombres completos
        lineas = body.split('\n')
        for linea in lineas:
            linea = linea.strip()
            if self._es_nombre_valido(linea):
                # Filtrar si no tiene números (para evitar confundir con otros datos)
                if not re.search(r'\d', linea):
                    info['beneficiario'] = linea
                    logger.info(f"[Parser] Beneficiario detectado: {info['beneficiario']}")
                    break
        
        # Si no se encontró en líneas, buscar con regex más amplio
        if not info['beneficiario']:
            beneficiario_match = re.search(
                r'(?:beneficiario|titular|nombre)[:\s]+([a-zA-ZáéíóúÁÉÍÓÚñÑ\s]{6,})',
                body,
                re.IGNORECASE
            )
            if beneficiario_match:
                candidato = beneficiario_match.group(1).strip()
                if self._es_nombre_valido(candidato):
                    info['beneficiario'] = candidato
                    logger.info(f"[Parser] Beneficiario detectado (con keyword): {info['beneficiario']}")
        
        # Cantidad de ligas
        ligas = self._detectar_ligas(body)
        if ligas:
            info['cantidad_ligas'] = ligas
            logger.info(f"[Parser] Ligas detectadas: {info['cantidad_ligas']}")
        
        # Monto
        monto_match = re.search(r'(?:monto|cantidad)[:\s]+\$?([0-9,]+(?:\.[0-9]{2})?)', body, re.IGNORECASE)
        if monto_match:
            try:
                info['monto'] = float(monto_match.group(1).replace(',', ''))
                logger.info(f"[Parser] Monto detectado: {info['monto']}")
            except:
                pass
        
        return info
    
    async def _buscar_cliente_por_email(self, email: str) -> Optional[Dict]:
        """Busca cliente activo por email"""
        try:
            cliente = await db.clientes.find_one(
                {"email": email, "estado": "activo"},
                {"_id": 0}
            )
            return cliente
        except Exception as e:
            logger.error(f"[EmailMonitor] Error buscando cliente: {str(e)}")
            return None
    
    async def _download_attachments(self, message_id: str, attachments: List[Dict], email_cliente: str) -> List[Dict]:
        """Descarga adjuntos"""
        archivos = []
        
        logger.info(f"[EmailMonitor] 📎 Procesando {len(attachments)} adjuntos")
        
        for att in attachments:
            try:
                file_data = self.gmail.get_attachment(message_id, att['attachment_id'])
                if not file_data:
                    continue
                
                filename = f"{uuid4()}_{att['filename']}"
                file_path = ATTACHMENTS_DIR / filename
                
                with open(file_path, 'wb') as f:
                    f.write(file_data)
                
                archivos.append({
                    'nombre_original': att['filename'],
                    'nombre_guardado': filename,
                    'ruta': str(file_path),
                    'mime_type': att['mime_type'],
                    'tamaño': att['size']
                })
                
                logger.info(f"[EmailMonitor] ✅ Adjunto: {filename} ({att['size']} bytes)")
            except Exception as e:
                logger.error(f"[EmailMonitor] ❌ Error con adjunto {att['filename']}: {str(e)}")
        
        logger.info(f"[EmailMonitor] 📦 Total guardados: {len(archivos)}")
        return archivos
    
    async def _buscar_operacion_por_thread(self, thread_id: str) -> Optional[Dict]:
        """Busca operación por thread_id"""
        try:
            return await db.operaciones.find_one(
                {"gmail_thread_id": thread_id, "medio_origen": "email"},
                {"_id": 0}
            )
        except Exception as e:
            logger.error(f"[EmailMonitor] Error buscando operación: {str(e)}")
            return None
    
    async def _validate_info_detailed(self, email_cliente: str, archivos: List, info: Dict) -> Tuple[bool, List[str]]:
        """Valida info con reglas mejoradas"""
        campos_faltantes = []
        
        if len(archivos) == 0:
            campos_faltantes.append('adjuntos')
        
        if not self._es_nombre_valido(info.get('beneficiario')):
            campos_faltantes.append('beneficiario')
        
        if not self._es_idmex_valido(info.get('idmex')):
            campos_faltantes.append('idmex')
        
        if not info.get('cantidad_ligas'):
            campos_faltantes.append('cantidad_ligas')
        
        return len(campos_faltantes) == 0, campos_faltantes
    
    async def _validate_info_consolidada(self, operacion: Dict, nuevos_archivos: List, nueva_info: Dict) -> Tuple[bool, List[str]]:
        """Valida info consolidada"""
        campos_faltantes = []
        
        archivos_existentes = operacion.get('archivos_adjuntos', [])
        if len(archivos_existentes) == 0 and len(nuevos_archivos) == 0:
            campos_faltantes.append('adjuntos')
        
        beneficiario = operacion.get('beneficiario_reportado') or nueva_info.get('beneficiario')
        if not self._es_nombre_valido(beneficiario):
            campos_faltantes.append('beneficiario')
        
        idmex = operacion.get('idmex_reportado') or nueva_info.get('idmex')
        if not self._es_idmex_valido(idmex):
            campos_faltantes.append('idmex')
        
        ligas = operacion.get('cantidad_ligas_reportada') or nueva_info.get('cantidad_ligas')
        if not ligas:
            campos_faltantes.append('cantidad_ligas')
        
        logger.info(f"[EmailMonitor] Validación consolidada - Faltan: {campos_faltantes}")
        
        return len(campos_faltantes) == 0, campos_faltantes
    
    async def _actualizar_operacion(self, operacion_id: str, nuevos_archivos: List[Dict], nueva_info: Dict):
        """Actualiza operación"""
        try:
            update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
            
            if len(nuevos_archivos) > 0:
                operacion = await db.operaciones.find_one({"id": operacion_id})
                archivos_existentes = operacion.get('archivos_adjuntos', [])
                archivos_existentes.extend(nuevos_archivos)
                update_data['archivos_adjuntos'] = archivos_existentes
            
            if nueva_info.get('beneficiario'):
                update_data['beneficiario_reportado'] = nueva_info['beneficiario']
            
            if nueva_info.get('idmex'):
                update_data['idmex_reportado'] = nueva_info['idmex']
            
            if nueva_info.get('cantidad_ligas'):
                update_data['cantidad_ligas_reportada'] = nueva_info['cantidad_ligas']
            
            if nueva_info.get('monto'):
                update_data['monto_reportado_por_mail'] = nueva_info['monto']
            
            update_data['estado_operacion'] = 'en_revision_por_mail'
            
            await db.operaciones.update_one(
                {"id": operacion_id},
                {"$set": update_data}
            )
            
            logger.info(f"[EmailMonitor] Operación {operacion_id} actualizada")
        except Exception as e:
            logger.error(f"[EmailMonitor] Error actualizando: {str(e)}")
    
    async def _create_netcash_operation(self, email_cliente: str, cliente_id: str, cliente_nombre: str,
                                        asunto: str, cuerpo: str, archivos_adjuntos: List[Dict],
                                        info_extraida: Dict, mensaje_id: str, thread_id: str) -> Dict:
        """Crea operación NetCash"""
        count = await db.operaciones.count_documents({})
        clave_operacion = f"NC-EMAIL-{count + 1:06d}"
        
        operacion = {
            "id": str(uuid4()),
            "clave_operacion": clave_operacion,
            "medio_origen": "email",
            "cliente_id": cliente_id,
            "cliente_nombre": cliente_nombre,
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
            "comprobantes": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.operaciones.insert_one(operacion)
        
        logger.info(f"[EmailMonitor] Operación {clave_operacion} creada - Adjuntos: {len(archivos_adjuntos)}")
        
        return operacion
    
    async def _get_cuenta_pago(self) -> Optional[Dict]:
        """Obtiene cuenta activa"""
        try:
            cuenta = await cuenta_deposito_service.obtener_cuenta_activa()
            if cuenta:
                logger.info(f"[EmailMonitor] 🏦 Cuenta: {cuenta.get('banco')} - {cuenta.get('clabe')}")
            return cuenta
        except Exception as e:
            logger.error(f"[EmailMonitor] Error obteniendo cuenta: {str(e)}")
            return None
    
    def _format_cuenta_pago(self, cuenta: Optional[Dict]) -> str:
        """Formatea cuenta"""
        if not cuenta:
            return "Recuerda que los depósitos para NetCash deben realizarse a la cuenta autorizada. Consúltala con tu ejecutivo."
        
        texto = "Recuerda realizar tu depósito a la cuenta autorizada:\n"
        texto += f"Banco: {cuenta.get('banco', 'N/A')}\n"
        texto += f"CLABE: {cuenta.get('clabe', 'N/A')}\n"
        texto += f"Beneficiario: {cuenta.get('beneficiario', 'N/A')}"
        
        return texto
    
    async def _send_success_response(self, to: str, original_subject: str, thread_id: str, clave_operacion: str):
        """Envía respuesta de éxito"""
        cuenta = await self._get_cuenta_pago()
        cuenta_texto = self._format_cuenta_pago(cuenta)
        
        subject = f"Re: {original_subject}"
        body = f"""Hola,

Estamos dando seguimiento a tu correo con asunto: "{original_subject}".

Recibimos tu correo y tus comprobantes.

Tu operación NetCash ha sido registrada con el código: {clave_operacion}

Esta operación está en proceso de validación interna.
En caso de requerir información adicional, nos pondremos en contacto contigo.

{cuenta_texto}

Gracias por usar NetCash.

Equipo NetCash"""
        
        self.gmail.send_reply(to, subject, body, thread_id)
        logger.info(f"[EmailMonitor] Respuesta éxito enviada a {to}")
    
    async def _send_incomplete_response_dynamic(self, to: str, original_subject: str, thread_id: str, campos_faltantes: List[str]):
        """Envía respuesta de info incompleta con plantilla"""
        lista_faltantes = []
        
        if 'adjuntos' in campos_faltantes:
            lista_faltantes.append("• Comprobantes claros y legibles en PDF, JPG o PNG (adjunta todos los relacionados con la operación).")
        
        if 'beneficiario' in campos_faltantes:
            lista_faltantes.append("• El nombre completo del beneficiario (nombre y dos apellidos, por ejemplo: Juan Pérez García).")
        
        if 'idmex' in campos_faltantes:
            lista_faltantes.append("• El IDMEX de 10 dígitos (identificador de la operación que usas con MBco).")
        
        if 'cantidad_ligas' in campos_faltantes:
            lista_faltantes.append("• La cantidad de ligas NetCash que necesitas para esta operación.")
        
        subject = f"Re: {original_subject}"
        
        body = f"""Hola,

Estamos dando seguimiento a tu correo con asunto: "{original_subject}".

Recibimos tu correo para operar con NetCash, pero todavía nos falta información para poder registrar correctamente la operación.

En tu próximo correo por favor incluye lo siguiente que nos falta:
"""
        
        for item in lista_faltantes:
            body += item + "\n"
        
        cuenta = await self._get_cuenta_pago()
        cuenta_texto = self._format_cuenta_pago(cuenta)
        
        body += f"""
Si necesitas apoyo, responde con la palabra "AYUDA" y nuestro equipo se pondrá en contacto contigo.

{cuenta_texto}

────────────────────────────────
Para ayudarte mejor, puedes responder usando esta plantilla:

Nombre del beneficiario (nombre y dos apellidos):
IDMEX (10 dígitos):
Cantidad de ligas NetCash:
(Adjunta los comprobantes en PDF, JPG o PNG)
────────────────────────────────

En cuanto tengamos la información completa, registramos la operación y te confirmamos.

Quedamos al pendiente.

Equipo NetCash"""
        
        self.gmail.send_reply(to, subject, body, thread_id)
        logger.info(f"[EmailMonitor] Respuesta incompleta enviada a {to}")
    
    async def _send_subject_missing_response(self, to: str, original_subject: str, thread_id: str):
        """Respuesta para asunto sin NetCash"""
        subject = f"Re: {original_subject}"
        body = """Hola,

Recibimos tu correo, pero para poder procesar tu solicitud en NetCash es necesario que el asunto incluya la palabra "NetCash".

Por favor vuelve a enviar tu correo asegurándote de que el asunto contenga "NetCash".

Ejemplos:
• NetCash – Pago proveedor
• NetCash – Nómina semana 15

Equipo NetCash"""
        
        self.gmail.send_reply(to, subject, body, thread_id)
        logger.info(f"[EmailMonitor] Respuesta asunto incorrecto enviada")
    
    async def _send_cliente_no_identificado_response(self, to: str, original_subject: str, thread_id: str):
        """Respuesta para cliente no identificado"""
        subject = f"Re: {original_subject}"
        body = f"""Hola,

Estamos dando seguimiento a tu correo con asunto: "{original_subject}".

Para poder operar con NetCash es necesario que primero estés dado de alta como cliente.

Por favor contacta a Ana para realizar tu registro:
• Correo: {ANA_EMAIL}
• WhatsApp: {ANA_WHATSAPP}

Una vez que Ana te confirme tu alta, podrás usar este correo sin problema.

Equipo NetCash"""
        
        self.gmail.send_reply(to, subject, body, thread_id)
        logger.info(f"[EmailMonitor] Respuesta no identificado enviada")
    
    async def _send_guia_minimos_response(self, to: str, original_subject: str, thread_id: str, archivos: List, info: Dict):
        """Guía cuando no cumple mínimos"""
        cuenta = await self._get_cuenta_pago()
        cuenta_texto = self._format_cuenta_pago(cuenta)
        
        subject = f"Re: {original_subject}"
        body = f"""Hola,

Estamos dando seguimiento a tu correo con asunto: "{original_subject}".

Para poder crear una operación NetCash necesitamos al menos:
• Un comprobante de pago adjunto (PDF, JPG o PNG)
O bien:
• IDMEX (10 dígitos) + Cantidad de ligas NetCash

{cuenta_texto}

────────────────────────────────
Puedes responder usando esta plantilla:

Nombre del beneficiario (nombre y dos apellidos):
IDMEX (10 dígitos):
Cantidad de ligas NetCash:
(Adjunta los comprobantes en PDF, JPG o PNG)
────────────────────────────────

Quedamos al pendiente.

Equipo NetCash"""
        
        self.gmail.send_reply(to, subject, body, thread_id)
        logger.info(f"[EmailMonitor] Guía mínimos enviada")


async def main():
    """Función principal"""
    logger.info("[EmailMonitor] Iniciando monitor NetCash...")
    
    monitor = EmailMonitor()
    
    while True:
        try:
            await monitor.process_emails()
        except Exception as e:
            logger.error(f"[EmailMonitor] Error en ciclo: {str(e)}")
        
        logger.info("[EmailMonitor] Esperando 20 segundos...")
        await asyncio.sleep(20)


if __name__ == "__main__":
    asyncio.run(main())
