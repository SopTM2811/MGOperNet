"""Monitor de correos de Gmail para NetCash
SOLO crea operaciones cuando TODO es válido (reglas duras)
"""

import os
import re
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
from validador_comprobantes_service import validador_comprobantes

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

ATTACHMENTS_DIR = Path("/app/backend/uploads/email_attachments")
ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)

ANA_EMAIL = "gestion.ngdl@gmail.com"
ANA_WHATSAPP = "+52 33 1218 6685"


class EmailMonitor:
    """Monitor que procesa correos - SOLO crea operaciones cuando TODO es válido"""
    
    def __init__(self):
        self.gmail = gmail_service
        if not self.gmail:
            raise Exception("Gmail service no inicializado")
    
    async def process_emails(self):
        """Procesa todos los correos no leídos"""
        try:
            logger.info("[EmailMonitor] Iniciando procesamiento...")
            messages = self.gmail.list_unread_messages()
            
            if not messages:
                logger.info("[EmailMonitor] No hay correos nuevos")
                return
            
            logger.info(f"[EmailMonitor] Procesando {len(messages)} correos...")
            
            for msg_summary in messages:
                try:
                    await self.process_single_email(msg_summary['id'])
                except Exception as e:
                    logger.error(f"[EmailMonitor] Error procesando {msg_summary['id']}: {str(e)}")
            
            logger.info("[EmailMonitor] Procesamiento completado")
        except Exception as e:
            logger.error(f"[EmailMonitor] Error: {str(e)}")
    
    async def process_single_email(self, message_id: str):
        """Procesa un correo individual CON REGLAS DURAS"""
        logger.info(f"[EmailMonitor] 📧 Procesando mensaje {message_id}")
        
        message = self.gmail.get_message(message_id)
        if not message:
            logger.error(f"[EmailMonitor] No se pudo obtener el mensaje")
            return
        
        msg_data = self.gmail.parse_message(message)
        email_cliente = self._extract_email(msg_data['from'])
        
        logger.info(f"[EmailMonitor] De: {email_cliente}")
        logger.info(f"[EmailMonitor] Asunto: {msg_data['subject']}")
        
        # REGLA 1: Asunto debe contener "NetCash"
        if not self._has_netcash_in_subject(msg_data['subject']):
            logger.warning("[EmailMonitor] ❌ Asunto sin 'NetCash'")
            await self._send_subject_missing_response(email_cliente, msg_data['subject'], msg_data['thread_id'])
            self.gmail.mark_as_read(message_id)
            self.gmail.add_label(message_id, "NETCASH/ASUNTO_INCORRECTO")
            return
        
        # REGLA 2: Cliente debe estar activo
        cliente = await self._buscar_cliente_por_email(email_cliente)
        if not cliente:
            logger.warning(f"[EmailMonitor] ❌ Cliente NO identificado: {email_cliente}")
            await self._send_cliente_no_identificado(email_cliente, msg_data['subject'], msg_data['thread_id'])
            self.gmail.mark_as_read(message_id)
            self.gmail.add_label(message_id, "NETCASH/CLIENTE_NO_IDENTIFICADO")
            return
        
        logger.info(f"[EmailMonitor] ✅ Cliente: {cliente.get('nombre')}")
        
        # Descargar adjuntos
        archivos_adjuntos = await self._download_attachments(message_id, msg_data['attachments'], email_cliente)
        
        # Extraer info del cuerpo
        info_extraida = self._extract_info_mejorado(msg_data['body'])
        
        # Obtener cuenta activa para validación
        cuenta_activa = await cuenta_deposito_service.obtener_cuenta_activa()
        
        # VALIDACIÓN COMPLETA CON REGLAS DURAS
        validacion = await self._validar_todo_estricto(
            cliente=cliente,
            archivos=archivos_adjuntos,
            info=info_extraida,
            cuenta_activa=cuenta_activa
        )
        
        logger.info(f"[EmailMonitor] Validación: {validacion['todo_valido']}")
        logger.info(f"[EmailMonitor] Campos válidos: {validacion['campos_validos']}")
        logger.info(f"[EmailMonitor] Campos faltantes: {validacion['campos_faltantes']}")
        logger.info(f"[EmailMonitor] Campos inválidos: {validacion['campos_invalidos']}")
        
        if validacion['todo_valido']:
            # TODO VÁLIDO: Crear operación
            operacion = await self._create_operacion_valida(
                email_cliente=email_cliente,
                cliente_id=cliente.get('id'),
                cliente_nombre=cliente.get('nombre'),
                asunto=msg_data['subject'],
                cuerpo=msg_data['body'],
                archivos=archivos_adjuntos,
                info=info_extraida,
                mensaje_id=message_id,
                thread_id=msg_data['thread_id'],
                validacion=validacion
            )
            
            await self._send_exito(email_cliente, msg_data['subject'], msg_data['thread_id'], operacion['clave_operacion'])
            self.gmail.add_label(message_id, "NETCASH/PROCESADO")
            logger.info(f"[EmailMonitor] ✅✅ Operación {operacion['clave_operacion']} CREADA Y VÁLIDA")
        else:
            # ALGO FALTA O ES INVÁLIDO: NO crear operación, solo guiar
            await self._send_falta_o_invalido(
                email_cliente,
                msg_data['subject'],
                msg_data['thread_id'],
                validacion,
                cuenta_activa
            )
            self.gmail.add_label(message_id, "NETCASH/FALTA_INFO_O_INVALIDO")
            logger.info("[EmailMonitor] ❌ NO se creó operación - falta o es inválido")
        
        self.gmail.mark_as_read(message_id)
    
    def _has_netcash_in_subject(self, subject: str) -> bool:
        return 'netcash' in subject.lower()
    
    def _extract_email(self, from_header: str) -> str:
        match = re.search(r'<([^>]+)>', from_header)
        return match.group(1) if match else from_header
    
    async def _buscar_cliente_por_email(self, email: str) -> Optional[Dict]:
        try:
            return await db.clientes.find_one({"email": email, "estado": "activo"}, {"_id": 0})
        except Exception as e:
            logger.error(f"[EmailMonitor] Error buscando cliente: {str(e)}")
            return None
    
    async def _download_attachments(self, message_id: str, attachments: List[Dict], email: str) -> List[Dict]:
        archivos = []
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
                
                logger.info(f"[EmailMonitor] 📎 Adjunto guardado: {filename}")
            except Exception as e:
                logger.error(f"[EmailMonitor] Error con adjunto: {str(e)}")
        
        return archivos
    
    def _extract_info_mejorado(self, body: str) -> Dict:
        """Extrae info con reglas estrictas"""
        info = {
            'beneficiario': None,
            'idmex': None,
            'cantidad_ligas': None,
            'monto': None
        }
        
        # IDMEX: exactamente 10 dígitos
        matches_10 = re.findall(r'\b(\d{10})\b', body)
        if matches_10:
            info['idmex'] = matches_10[0]
            logger.info(f"[Parser] IDMEX detectado: {info['idmex']}")
        
        # Beneficiario: 3+ palabras sin números
        lineas = body.split('\n')
        for linea in lineas:
            linea = linea.strip()
            if not linea or re.search(r'\d', linea):
                continue
            palabras = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]+", linea)
            if len(palabras) >= 3:
                info['beneficiario'] = linea
                logger.info(f"[Parser] Beneficiario detectado: {info['beneficiario']}")
                break
        
        # Ligas
        patterns = [
            r'(\d+)\s*(?:liga|ligas)',
            r'(?:liga|ligas)\s*(\d+)',
            r'(\d+)\s*(?:línea|linea|líneas|lineas)(?:\s*de)?(?:\s*captura)?',
            r'(?:línea|linea|líneas|lineas)(?:\s*de)?(?:\s*captura)?\s*(\d+)',
            r'(\d+)\s*(?:line|lines)(?:\s*de)?(?:\s*captura)?',
            r'(?:line|lines)(?:\s*de)?(?:\s*captura)?\s*(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, body.lower())
            if match:
                try:
                    info['cantidad_ligas'] = int(match.group(1))
                    logger.info(f"[Parser] Ligas detectadas: {info['cantidad_ligas']}")
                    break
                except:
                    pass
        
        return info
    
    async def _validar_todo_estricto(self, cliente: Dict, archivos: List, info: Dict, cuenta_activa: Optional[Dict]) -> Dict:
        """Valida TODO con REGLAS DURAS - devuelve dict con resultado completo"""
        
        validacion = {
            'todo_valido': False,
            'campos_validos': [],
            'campos_faltantes': [],
            'campos_invalidos': []
        }
        
        # 1. Cliente (ya validado antes)
        validacion['campos_validos'].append('cliente_activo')
        
        # 2. Comprobantes
        if not archivos or len(archivos) == 0:
            validacion['campos_faltantes'].append('comprobante')
        else:
            # Validar comprobantes contra cuenta activa
            al_menos_uno_valido, validaciones = validador_comprobantes.validar_todos_comprobantes(archivos, cuenta_activa)
            
            if al_menos_uno_valido:
                validacion['campos_validos'].append('comprobante_valido')
                validacion['detalle_comprobantes'] = validaciones
            else:
                validacion['campos_invalidos'].append({'campo': 'comprobante', 'razon': 'No corresponde a la cuenta NetCash activa', 'detalle': validaciones})
        
        # 3. Nombre beneficiario
        if not info.get('beneficiario'):
            validacion['campos_faltantes'].append('beneficiario')
        else:
            palabras = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]+", info['beneficiario'])
            if len(palabras) >= 3:
                validacion['campos_validos'].append('beneficiario')
            else:
                validacion['campos_invalidos'].append({'campo': 'beneficiario', 'razon': f"Debe tener mínimo 3 palabras (nombre + 2 apellidos), tiene {len(palabras)}"})
        
        # 4. IDMEX
        if not info.get('idmex'):
            validacion['campos_faltantes'].append('idmex')
        else:
            if re.match(r'^[0-9]{10}$', str(info['idmex'])):
                validacion['campos_validos'].append('idmex')
            else:
                validacion['campos_invalidos'].append({'campo': 'idmex', 'razon': f"Debe ser exactamente 10 dígitos, tiene {len(str(info['idmex']))}"})
        
        # 5. Ligas
        if not info.get('cantidad_ligas'):
            validacion['campos_faltantes'].append('cantidad_ligas')
        else:
            if info['cantidad_ligas'] > 0:
                validacion['campos_validos'].append('cantidad_ligas')
            else:
                validacion['campos_invalidos'].append({'campo': 'cantidad_ligas', 'razon': 'Debe ser mayor a 0'})
        
        # TODO VÁLIDO solo si:
        # - No hay campos faltantes
        # - No hay campos inválidos
        # - Tiene los 5 campos válidos
        validacion['todo_valido'] = (
            len(validacion['campos_faltantes']) == 0 and
            len(validacion['campos_invalidos']) == 0 and
            len(validacion['campos_validos']) >= 5
        )
        
        return validacion
    
    async def _create_operacion_valida(self, email_cliente: str, cliente_id: str, cliente_nombre: str,
                                       asunto: str, cuerpo: str, archivos: List, info: Dict,
                                       mensaje_id: str, thread_id: str, validacion: Dict) -> Dict:
        """Crea operación SOLO cuando TODO es válido"""
        
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
            "valida_para_proceso": True,
            "beneficiario_reportado": info.get('beneficiario'),
            "idmex_reportado": info.get('idmex'),
            "cantidad_ligas_reportada": info.get('cantidad_ligas'),
            "monto_reportado_por_mail": info.get('monto'),
            "archivos_adjuntos": archivos,
            "validacion_completa": validacion,
            "comprobantes": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.operaciones.insert_one(operacion)
        logger.info(f"[EmailMonitor] ✅ Operación {clave_operacion} creada (TODO VÁLIDO)")
        
        return operacion
    
    async def _send_exito(self, to: str, subject: str, thread_id: str, clave: str):
        cuenta = await cuenta_deposito_service.obtener_cuenta_activa()
        cuenta_texto = self._format_cuenta(cuenta)
        
        asunto = f"Re: {subject}"
        body = f"""Hola,

Estamos dando seguimiento a tu correo con asunto: "{subject}".

Recibimos tu correo y tus comprobantes.

Tu operación NetCash ha sido registrada con el código: {clave}

Esta operación está en proceso de validación interna.

{cuenta_texto}

Gracias por usar NetCash.

Equipo NetCash"""
        
        self.gmail.send_reply(to, asunto, body, thread_id)
        logger.info(f"[EmailMonitor] 📧 Correo de éxito enviado")
    
    async def _send_falta_o_invalido(self, to: str, subject: str, thread_id: str, validacion: Dict, cuenta: Optional[Dict]):
        """Envía correo explicando qué falta o es inválido - NO crea operación"""
        
        cuenta_texto = self._format_cuenta(cuenta)
        
        asunto = f"Re: {subject}"
        
        body = f"""Hola,

Estamos dando seguimiento a tu correo con asunto: "{subject}".

Recibimos tu correo, pero para poder registrar tu operación NetCash todavía falta o es inválido lo siguiente:

"""
        
        # Listar campos FALTANTES
        if validacion['campos_faltantes']:
            for campo in validacion['campos_faltantes']:
                if campo == 'comprobante':
                    body += "• Comprobantes claros y legibles en PDF, JPG o PNG (adjunta todos los relacionados con la operación).\n"
                elif campo == 'beneficiario':
                    body += "• El nombre completo del beneficiario (nombre y dos apellidos, por ejemplo: Juan Pérez García).\n"
                elif campo == 'idmex':
                    body += "• El IDMEX de 10 dígitos (identificador de la operación que usas con MBco).\n"
                elif campo == 'cantidad_ligas':
                    body += "• La cantidad de ligas NetCash que necesitas para esta operación.\n"
        
        # Listar campos INVÁLIDOS
        if validacion['campos_invalidos']:
            body += "\n⚠️  Además, lo siguiente es inválido:\n"
            for item in validacion['campos_invalidos']:
                campo = item['campo']
                razon = item['razon']
                
                if campo == 'comprobante':
                    body += f"• Comprobante: {razon}.\n"
                    body += f"  Por favor verifica que el depósito se haya realizado a la cuenta NetCash autorizada:\n"
                    if cuenta:
                        body += f"  Banco: {cuenta.get('banco')}\n"
                        body += f"  CLABE: {cuenta.get('clabe')}\n"
                        body += f"  Beneficiario: {cuenta.get('beneficiario')}\n"
                elif campo == 'beneficiario':
                    body += f"• Nombre del beneficiario: {razon}.\n"
                elif campo == 'idmex':
                    body += f"• IDMEX: {razon}.\n"
                elif campo == 'cantidad_ligas':
                    body += f"• Cantidad de ligas: {razon}.\n"
        
        body += f"""\nSi necesitas apoyo, responde con la palabra "AYUDA".

{cuenta_texto}

────────────────────────────────
Para ayudarte mejor, puedes responder usando esta plantilla:

Nombre del beneficiario (nombre y dos apellidos):
IDMEX (10 dígitos):
Cantidad de ligas NetCash:
(Adjunta los comprobantes en PDF, JPG o PNG a la cuenta autorizada)
────────────────────────────────

Quedamos al pendiente.

Equipo NetCash"""
        
        self.gmail.send_reply(to, asunto, body, thread_id)
        logger.info("[EmailMonitor] 📧 Correo de falta/inválido enviado")
    
    async def _send_subject_missing_response(self, to: str, subject: str, thread_id: str):
        asunto = f"Re: {subject}"
        body = """Hola,

Recibimos tu correo, pero para poder procesar tu solicitud en NetCash es necesario que el asunto incluya la palabra "NetCash".

Por favor vuelve a enviar tu correo asegurándote de que el asunto contenga "NetCash".

Ejemplos:
• NetCash – Pago proveedor
• NetCash – Nómina semana 15

Equipo NetCash"""
        
        self.gmail.send_reply(to, asunto, body, thread_id)
    
    async def _send_cliente_no_identificado(self, to: str, subject: str, thread_id: str):
        asunto = f"Re: {subject}"
        body = f"""Hola,

Estamos dando seguimiento a tu correo con asunto: "{subject}".

Para poder operar con NetCash es necesario que primero estés dado de alta como cliente.

Por favor contacta a Ana para realizar tu registro:
• Correo: {ANA_EMAIL}
• WhatsApp: {ANA_WHATSAPP}

Una vez que Ana te confirme tu alta, podrás usar este correo sin problema.

Equipo NetCash"""
        
        self.gmail.send_reply(to, asunto, body, thread_id)
    
    def _format_cuenta(self, cuenta: Optional[Dict]) -> str:
        if not cuenta:
            return "Recuerda que los depósitos para NetCash deben realizarse a la cuenta autorizada. Consúltala con tu ejecutivo."
        
        texto = "Recuerda realizar tu depósito a la cuenta autorizada:\n"
        texto += f"Banco: {cuenta.get('banco', 'N/A')}\n"
        texto += f"CLABE: {cuenta.get('clabe', 'N/A')}\n"
        texto += f"Beneficiario: {cuenta.get('beneficiario', 'N/A')}"
        return texto


async def main():
    logger.info("[EmailMonitor] Iniciando monitor NetCash (REGLAS DURAS)...")
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
