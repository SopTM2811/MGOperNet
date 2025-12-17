"""Motor Central NetCash - Lógica de Negocio Unificada

Este módulo contiene TODA la lógica de negocio para NetCash V1.
Todos los canales (Telegram, Email, Manual) delegan aquí.

Responsabilidades:
- Crear y actualizar solicitudes NetCash
- Aplicar REGLAS DURAS de validación
- Gestionar transiciones de estado
- Generar resúmenes para clientes
- Generar folios MBco secuenciales

Reglas Duras (Etapa 1):
1. Cliente válido (activo en catálogo)
2. Beneficiario válido (3+ palabras, sin números)
3. IDMEX válido (exactamente 10 dígitos)
4. Ligas válidas (número entero > 0)
5. Comprobante válido (CLABE completa + beneficiario de cuenta concertadora activa)
"""

import logging
import re
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os
from decimal import Decimal

# Servicios de OCR mejorado
from banco_specific_parsers import banco_parser_factory
from ocr_confidence_validator import ocr_confidence_validator

# Servicio de aprendizaje (P2)
from netcash_pdf_learning_service import netcash_pdf_learning_service

from netcash_models import (
    SolicitudNetCash, SolicitudCreate, SolicitudUpdate, ResumenCliente,
    CanalOrigen, EstadoSolicitud, ValidacionCampo,
    ComprobanteDetalle, HistoricoEstado, CanalMetadata
)
from cuenta_deposito_service import cuenta_deposito_service
from validador_comprobantes_service import ValidadorComprobantes

logger = logging.getLogger(__name__)

# Conexión MongoDB
mongo_url = os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'netcash_mbco')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

COLLECTION_NAME = 'solicitudes_netcash'


class NetCashService:
    """Servicio central para gestión de solicitudes NetCash"""
    
    def __init__(self):
        self.validador_comprobantes = ValidadorComprobantes()
    
    async def _generar_folio_mbco(self) -> str:
        """
        Genera un folio secuencial para operaciones NetCash (ej: NC-000123).
        Busca en AMBAS colecciones para mantener secuencia global.
        """
        ultimo_numero = 0
        
        # Buscar el último folio en operaciones (web)
        ultima_web = await db.operaciones.find_one(
            {"folio_mbco": {"$exists": True, "$ne": None}},
            {"_id": 0, "folio_mbco": 1},
            sort=[("folio_mbco", -1)]
        )
        
        if ultima_web and ultima_web.get("folio_mbco"):
            try:
                num_web = int(ultima_web["folio_mbco"].split("-")[1])
                ultimo_numero = max(ultimo_numero, num_web)
            except (IndexError, ValueError):
                pass
        
        # Buscar el último folio en solicitudes_netcash (Telegram)
        ultima_telegram = await db.solicitudes_netcash.find_one(
            {"folio_mbco": {"$exists": True, "$ne": None}},
            {"_id": 0, "folio_mbco": 1},
            sort=[("folio_mbco", -1)]
        )
        
        if ultima_telegram and ultima_telegram.get("folio_mbco"):
            try:
                num_telegram = int(ultima_telegram["folio_mbco"].split("-")[1])
                ultimo_numero = max(ultimo_numero, num_telegram)
            except (IndexError, ValueError):
                pass
        
        # Generar nuevo folio
        nuevo_numero = ultimo_numero + 1
        return f"NC-{nuevo_numero:06d}"
    
    # ==================== CREACIÓN Y ACTUALIZACIÓN ====================
    
    async def crear_solicitud(self, datos: SolicitudCreate) -> Optional[Dict]:
        """
        Crea una nueva solicitud NetCash en estado BORRADOR.
        
        Args:
            datos: Datos básicos de la solicitud
        
        Returns:
            Solicitud creada o None si hay error
        """
        try:
            logger.info(f"[NetCash] ========== CREAR SOLICITUD ==========")
            logger.info(f"[NetCash] Canal: {datos.canal}")
            logger.info(f"[NetCash] Cliente: {datos.cliente_nombre} ({datos.cliente_id})")
            
            # Generar ID interno
            timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
            solicitud_id = f"nc-{timestamp}"
            
            # Generar folio secuencial NC-XXXXXX
            folio_mbco = await self._generar_folio_mbco()
            logger.info(f"[NetCash] Folio generado: {folio_mbco}")
            
            # Crear solicitud base
            solicitud = {
                "id": solicitud_id,
                "folio_mbco": folio_mbco,  # Ahora se genera al crear
                "canal": datos.canal.value,
                "cliente_id": datos.cliente_id,
                "cliente_nombre": datos.cliente_nombre,
                "beneficiario_reportado": datos.beneficiario_reportado,
                "idmex_reportado": datos.idmex_reportado,
                "cantidad_ligas_reportada": datos.cantidad_ligas_reportada,
                "comprobantes": [],
                "estado": EstadoSolicitud.BORRADOR.value,
                "validacion": {
                    "cliente": {"valido": False, "razon": "No validado"},
                    "beneficiario": {"valido": False, "razon": "No validado"},
                    "idmex": {"valido": False, "razon": "No validado"},
                    "ligas": {"valido": False, "razon": "No validado"},
                    "comprobante": {"valido": False, "razon": "No validado"}
                },
                "monto_depositado_cliente": None,
                "porcentaje_comision_cliente": None,
                "monto_comision_mbco": None,
                "monto_capital_proveedor": None,
                "canal_metadata": datos.canal_metadata.dict() if datos.canal_metadata else {},
                "legacy": False,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "estado_historico": [
                    {
                        "estado": EstadoSolicitud.BORRADOR.value,
                        "en": datetime.now(timezone.utc),
                        "por": "sistema",
                        "notas": f"Creada desde {datos.canal.value}"
                    }
                ]
            }
            
            await db[COLLECTION_NAME].insert_one(solicitud)
            logger.info(f"[NetCash] ✅ Solicitud creada: {solicitud_id}")
            
            # Retornar sin _id
            if '_id' in solicitud:
                del solicitud['_id']
            
            return solicitud
            
        except Exception as e:
            logger.error(f"[NetCash] ❌ Error creando solicitud: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def actualizar_solicitud(self, solicitud_id: str, datos: SolicitudUpdate) -> bool:
        """
        Actualiza datos de una solicitud existente.
        
        Args:
            solicitud_id: ID de la solicitud
            datos: Datos a actualizar
        
        Returns:
            True si se actualizó correctamente
        """
        try:
            update_data = {}
            if datos.beneficiario_reportado is not None:
                update_data["beneficiario_reportado"] = datos.beneficiario_reportado
            if datos.idmex_reportado is not None:
                update_data["idmex_reportado"] = datos.idmex_reportado
            if datos.cantidad_ligas_reportada is not None:
                update_data["cantidad_ligas_reportada"] = datos.cantidad_ligas_reportada
            if datos.monto_depositado_cliente is not None:
                update_data["monto_depositado_cliente"] = datos.monto_depositado_cliente
            
            if not update_data:
                return True
            
            update_data["updated_at"] = datetime.now(timezone.utc)
            
            result = await db[COLLECTION_NAME].update_one(
                {"id": solicitud_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"[NetCash] Solicitud {solicitud_id} actualizada")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"[NetCash] Error actualizando solicitud: {str(e)}")
            return False
    
    async def agregar_comprobante(self, solicitud_id: str, archivo_url: str, 
                                 nombre_archivo: str) -> Tuple[bool, Optional[str]]:
        """
        Agrega un comprobante a una solicitud y lo valida.
        Detecta duplicados usando hash SHA-256 del contenido.
        
        Args:
            solicitud_id: ID de la solicitud
            archivo_url: Ruta del archivo
            nombre_archivo: Nombre original del archivo
        
        Returns:
            Tupla (agregado: bool, razon: str o None)
            - Si es duplicado: (False, "duplicado")
            - Si es válido: (True, None)
            - Si es inválido: (True, None) (se agrega pero marcado como inválido)
        """
        try:
            logger.info(f"[NetCash] Agregando comprobante a {solicitud_id}: {nombre_archivo}")
            
            # PASO 1: Calcular hash SHA-256 del archivo
            import hashlib
            file_hash = self._calcular_hash_archivo(archivo_url)
            logger.info(f"[NetCash] Hash del archivo: {file_hash}")
            
            # PASO 2: Obtener solicitud actual
            solicitud = await db[COLLECTION_NAME].find_one({"id": solicitud_id}, {"_id": 0})
            if not solicitud:
                logger.error(f"[NetCash] Solicitud {solicitud_id} no encontrada")
                return False, "solicitud_no_encontrada"
            
            cliente_id = solicitud.get("cliente_id")
            comprobantes_existentes = solicitud.get("comprobantes", [])
            
            # PASO 2A: Verificar duplicado LOCAL (dentro de la misma operación)
            for comp in comprobantes_existentes:
                if comp.get("archivo_hash") == file_hash:
                    logger.warning(f"[NetCash] ⚠️ COMPROBANTE DUPLICADO LOCAL detectado: {nombre_archivo}")
                    logger.warning(f"[NetCash] Hash duplicado: {file_hash}")
                    logger.warning(f"[NetCash] Original: {comp.get('nombre_archivo')}")
                    
                    # Agregar el comprobante pero marcado como duplicado local
                    comprobante_duplicado = {
                        "archivo_url": archivo_url,
                        "nombre_archivo": nombre_archivo,
                        "archivo_hash": file_hash,
                        "es_valido": False,
                        "es_duplicado": True,
                        "tipo_duplicado": "local",
                        "duplicado_de": comp.get("nombre_archivo"),
                        "validacion_detalle": {
                            "razon": f"Comprobante duplicado de '{comp.get('nombre_archivo')}' en esta operación",
                        },
                        "cuenta_detectada": None,
                        "monto_detectado": None
                    }
                    
                    await db[COLLECTION_NAME].update_one(
                        {"id": solicitud_id},
                        {
                            "$push": {"comprobantes": comprobante_duplicado},
                            "$set": {"updated_at": datetime.now(timezone.utc)}
                        }
                    )
                    
                    return False, "duplicado_local"
            
            # PASO 2B: Verificar duplicado GLOBAL (en otras operaciones del mismo cliente)
            # Buscar si este hash ya existe en otras solicitudes del cliente
            # Excluir estados: rechazada, demo, cancelada (permiten reutilizar comprobante)
            estados_que_bloquean_duplicados = [
                "comprobantes_recibidos",  # Operación activa recibiendo comprobantes
                "lista_para_mbc",          # Operación lista para procesar
                "en_proceso_mbc",           # Operación en proceso
                "completada",               # Operación completada
                "borrador"                  # Operación en borrador
            ]
            
            otras_solicitudes = await db[COLLECTION_NAME].find(
                {
                    "cliente_id": cliente_id,
                    "id": {"$ne": solicitud_id},  # Excluir la solicitud actual
                    "estado": {"$in": estados_que_bloquean_duplicados},
                    "comprobantes.archivo_hash": file_hash  # Buscar por hash en array
                },
                {"_id": 0, "id": 1, "folio_mbco": 1, "estado": 1, "comprobantes": 1}
            ).to_list(10)
            
            if otras_solicitudes:
                # Encontrado en otra operación
                solicitud_original = otras_solicitudes[0]
                folio_original = solicitud_original.get("folio_mbco", "Sin folio")
                id_original = solicitud_original.get("id")
                
                # Buscar el comprobante específico con ese hash
                nombre_original = None
                for comp in solicitud_original.get("comprobantes", []):
                    if comp.get("archivo_hash") == file_hash:
                        nombre_original = comp.get("nombre_archivo")
                        break
                
                logger.warning(f"[NetCash] ⚠️ COMPROBANTE DUPLICADO GLOBAL detectado: {nombre_archivo}")
                logger.warning(f"[NetCash] Ya usado en operación: {folio_original} (ID: {id_original})")
                logger.warning(f"[NetCash] Archivo original: {nombre_original}")
                
                # Agregar el comprobante pero marcado como duplicado global
                comprobante_duplicado_global = {
                    "archivo_url": archivo_url,
                    "nombre_archivo": nombre_archivo,
                    "archivo_hash": file_hash,
                    "es_valido": False,
                    "es_duplicado": True,
                    "tipo_duplicado": "global",
                    "operacion_original": folio_original,
                    "id_solicitud_original": id_original,
                    "duplicado_de": nombre_original,
                    "validacion_detalle": {
                        "razon": f"Comprobante ya utilizado en operación {folio_original}",
                    },
                    "cuenta_detectada": None,
                    "monto_detectado": None
                }
                
                await db[COLLECTION_NAME].update_one(
                    {"id": solicitud_id},
                    {
                        "$push": {"comprobantes": comprobante_duplicado_global},
                        "$set": {"updated_at": datetime.now(timezone.utc)}
                    }
                )
                
                return False, f"duplicado_global:{folio_original}"
            
            # PASO 3: No es duplicado, procesar normalmente
            logger.info(f"[NetCash] Comprobante único, procesando validación...")
            
            # Validar comprobante contra cuenta concertadora activa
            cuenta_activa = await cuenta_deposito_service.obtener_cuenta_activa()
            
            if not cuenta_activa:
                logger.error(f"[NetCash] No hay cuenta concertadora activa")
                return False, "sin_cuenta_activa"
            
            # Determinar MIME type
            mime_type = "application/pdf" if archivo_url.lower().endswith(".pdf") else "image/jpeg"
            if archivo_url.lower().endswith(".png"):
                mime_type = "image/png"
            
            # LOG EXPLÍCITO - Para correlacionar con logs del validador
            logger.info(f"[NC TELEGRAM] Procesando comprobante: {nombre_archivo}")
            logger.info(f"[NC TELEGRAM] Cuenta activa: banco={cuenta_activa.get('banco')} clabe={cuenta_activa.get('clabe')}")
            
            # ⭐ UNIFICADO: Usar el mismo OCR de Web (Gemini Vision) para Telegram
            from ocr_service import ocr_service
            
            logger.info(f"[NetCash-OCR] Usando OCR unificado (Gemini Vision)...")
            datos_ocr = await ocr_service.leer_comprobante(archivo_url, mime_type)
            
            # Verificar si hubo error en OCR
            if datos_ocr.get("error"):
                logger.warning(f"[NetCash-OCR] Error en OCR: {datos_ocr.get('error')}")
                es_confiable = False
                motivo_fallo = "error_ocr"
                advertencias = [datos_ocr.get("error")]
            else:
                es_confiable = True
                motivo_fallo = None
                advertencias = []
            
            # Extraer datos del OCR unificado
            monto_detectado = datos_ocr.get('monto')
            banco_detectado = datos_ocr.get('banco_emisor')
            clave_rastreo = datos_ocr.get('clave_rastreo')
            cuenta_beneficiaria = datos_ocr.get('cuenta_beneficiaria')
            nombre_beneficiario = datos_ocr.get('nombre_beneficiario')
            fecha_operacion = datos_ocr.get('fecha')
            referencia = datos_ocr.get('referencia')
            
            logger.info(f"[NetCash-OCR] Datos extraídos: monto={monto_detectado}, banco={banco_detectado}, clave={clave_rastreo}")
            
            # Validar si el comprobante es válido (CLABE coincide con cuenta activa)
            clabe_activa = cuenta_activa.get('clabe', '')
            es_valido = False
            razon = "CLABE no coincide con cuenta activa"
            
            if cuenta_beneficiaria:
                # Limpiar y comparar CLABEs
                cuenta_limpia = str(cuenta_beneficiaria).replace(" ", "").replace("-", "").replace("*", "")
                if clabe_activa in cuenta_limpia or cuenta_limpia in clabe_activa:
                    es_valido = True
                    razon = "CLABE coincide con cuenta activa"
                elif len(cuenta_limpia) >= 4 and clabe_activa[-4:] == cuenta_limpia[-4:]:
                    es_valido = True
                    razon = "Últimos 4 dígitos de CLABE coinciden"
            
            # Si no se detectó monto, marcar como no confiable
            if not monto_detectado or monto_detectado == 0:
                es_confiable = False
                motivo_fallo = "sin_monto_detectado"
                advertencias.append("No se pudo detectar el monto del comprobante")
            
            cuenta_detectada = {
                "clabe": cuenta_beneficiaria,
                "beneficiario": nombre_beneficiario
            } if cuenta_beneficiaria else None
            
            # Crear detalle del comprobante (con hash para detección de duplicados)
            # ⭐ UNIFICADO: Misma estructura que comprobantes Web
            comprobante_detalle = {
                "archivo_url": archivo_url,
                "file_url": archivo_url,  # Alias para compatibilidad con frontend
                "nombre_archivo": nombre_archivo,
                "archivo_hash": file_hash,  # Hash SHA-256 para detección de duplicados
                "es_valido": es_valido,
                "es_duplicado": False,  # Este NO es duplicado
                # Datos extraídos por OCR (igual que Web)
                "monto": monto_detectado,
                "monto_detectado": monto_detectado,  # Mantener por compatibilidad
                "banco_origen": banco_detectado,
                "clave_rastreo": clave_rastreo,
                "cuenta_origen": cuenta_beneficiaria,
                "nombre_beneficiario": nombre_beneficiario,
                "fecha_operacion": fecha_operacion,
                "referencia": referencia,
                # Datos de validación
                "validacion_detalle": {
                    "razon": razon,
                    "cuenta_activa_esperada": cuenta_activa.get('clabe'),
                },
                "cuenta_detectada": cuenta_detectada,
                # Datos de validación OCR
                "ocr_data": {
                    "banco_detectado": banco_detectado,
                    "es_confiable": es_confiable,
                    "motivo_fallo": motivo_fallo if not es_confiable else None,
                    "advertencias": advertencias,
                    "datos_completos": datos_ocr  # Guardar respuesta completa de OCR
                }
            }
            
            # ⭐ NUEVO: Determinar si requiere captura manual
            # Si algún comprobante tiene OCR no confiable, marcar la solicitud
            update_fields = {
                "updated_at": datetime.now(timezone.utc),
                "monto_depositado_cliente": monto_detectado  # Actualizar monto si se detectó
            }
            
            # Si este es el primer comprobante y el OCR no es confiable, activar modo manual
            if not es_confiable and len(comprobantes_existentes) == 0:
                logger.warning(f"[NetCash-OCR] ⚠️ Activando modo captura manual")
                update_fields["modo_captura"] = "manual_por_fallo_ocr"
                update_fields["origen_montos"] = "pendiente_manual"  # Se actualizará cuando el usuario responda
                update_fields["validacion_ocr"] = {
                    "es_confiable": es_confiable,
                    "motivo_fallo": motivo_fallo,
                    "advertencias": advertencias,
                    "banco_detectado": datos_parseados.get('banco')
                }
            
            # Agregar a la solicitud
            result = await db[COLLECTION_NAME].update_one(
                {"id": solicitud_id},
                {
                    "$push": {"comprobantes": comprobante_detalle},
                    "$set": update_fields
                }
            )
            
            logger.info(f"[NetCash] ✅ Comprobante agregado: válido={es_valido}, monto={monto_detectado}, ocr_confiable={es_confiable}")
            
            # Retornar información adicional para que el bot pueda actuar
            return True, ("requiere_captura_manual" if not es_confiable and len(comprobantes_existentes) == 0 else None)
            
        except Exception as e:
            logger.error(f"[NetCash] Error agregando comprobante: {str(e)}")
            return False, "error"
    
    async def procesar_archivo_zip(self, solicitud_id: str, archivo_zip_path: str, 
                                   nombre_zip: str) -> Dict:
        """
        Procesa un archivo ZIP extrayendo y validando cada comprobante interno.
        
        Args:
            solicitud_id: ID de la solicitud
            archivo_zip_path: Ruta al archivo ZIP
            nombre_zip: Nombre original del archivo ZIP
        
        Returns:
            Dict con estadísticas del procesamiento:
            {
                "total_archivos": int,
                "validos": int,
                "invalidos": int,
                "duplicados": int,
                "no_legibles": int,
                "archivos_procesados": List[str]
            }
        """
        import zipfile
        import tempfile
        import shutil
        from pathlib import Path
        
        logger.info(f"[NetCash ZIP] Procesando archivo ZIP: {nombre_zip}")
        
        resultado = {
            "total_archivos": 0,
            "validos": 0,
            "invalidos": 0,
            "sin_texto_legible": 0,  # PDFs/imágenes sin texto extraíble
            "duplicados": 0,
            "no_legibles": 0,
            "archivos_procesados": []
        }
        
        # Crear directorio temporal para extraer el ZIP
        temp_dir = None
        
        try:
            # Verificar que el archivo ZIP es válido
            if not zipfile.is_zipfile(archivo_zip_path):
                logger.error(f"[NetCash ZIP] El archivo no es un ZIP válido: {archivo_zip_path}")
                return resultado
            
            # Crear directorio temporal
            temp_dir = tempfile.mkdtemp(prefix="netcash_zip_")
            logger.info(f"[NetCash ZIP] Directorio temporal creado: {temp_dir}")
            
            # Extraer el ZIP
            with zipfile.ZipFile(archivo_zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                archivos_en_zip = zip_ref.namelist()
                logger.info(f"[NetCash ZIP] {len(archivos_en_zip)} archivo(s) encontrado(s) en el ZIP")
            
            # Extensiones soportadas
            extensiones_soportadas = {'.pdf', '.jpg', '.jpeg', '.png'}
            
            # Procesar cada archivo en el ZIP
            for archivo_interno in Path(temp_dir).rglob('*'):
                if archivo_interno.is_file():
                    resultado["total_archivos"] += 1
                    nombre_interno = archivo_interno.name
                    extension = archivo_interno.suffix.lower()
                    
                    logger.info(f"[NetCash ZIP] Procesando archivo interno: {nombre_interno}")
                    
                    # Verificar si la extensión es soportada
                    if extension not in extensiones_soportadas:
                        logger.warning(f"[NetCash ZIP] Extensión no soportada: {nombre_interno} ({extension})")
                        resultado["no_legibles"] += 1
                        resultado["archivos_procesados"].append({
                            "nombre": nombre_interno,
                            "estado": "no_soportado",
                            "razon": f"Extensión {extension} no soportada"
                        })
                        continue
                    
                    # Intentar agregar el comprobante usando la lógica existente
                    try:
                        agregado, razon = await self.agregar_comprobante(
                            solicitud_id,
                            str(archivo_interno),
                            f"{nombre_zip}/{nombre_interno}"  # Prefijo con nombre del ZIP
                        )
                        
                        if agregado:
                            # Agregado exitosamente (puede ser válido o inválido)
                            # Verificar si es válido consultando la solicitud
                            solicitud = await db[COLLECTION_NAME].find_one(
                                {"id": solicitud_id},
                                {"_id": 0, "comprobantes": 1}
                            )
                            
                            # Buscar el comprobante recién agregado
                            comprobantes = solicitud.get("comprobantes", [])
                            comprobante_agregado = None
                            for comp in reversed(comprobantes):  # Buscar desde el final (más reciente)
                                if comp.get("nombre_archivo") == f"{nombre_zip}/{nombre_interno}":
                                    comprobante_agregado = comp
                                    break
                            
                            if comprobante_agregado and comprobante_agregado.get("es_valido"):
                                resultado["validos"] += 1
                                resultado["archivos_procesados"].append({
                                    "nombre": nombre_interno,
                                    "estado": "valido",
                                    "monto": comprobante_agregado.get("monto_detectado")
                                })
                            else:
                                # Clasificar por tipo de error
                                razon_invalido = comprobante_agregado.get("validacion_detalle", {}).get("razon") if comprobante_agregado else "No se pudo validar"
                                
                                if razon_invalido == "pdf_sin_texto_legible":
                                    resultado["sin_texto_legible"] += 1
                                    resultado["archivos_procesados"].append({
                                        "nombre": nombre_interno,
                                        "estado": "sin_texto_legible",
                                        "razon": "PDF/imagen sin texto seleccionable"
                                    })
                                else:
                                    resultado["invalidos"] += 1
                                    resultado["archivos_procesados"].append({
                                        "nombre": nombre_interno,
                                        "estado": "invalido",
                                        "razon": razon_invalido
                                    })
                        else:
                            # No agregado (duplicado)
                            resultado["duplicados"] += 1
                            tipo_duplicado = "local" if razon == "duplicado_local" else "global"
                            resultado["archivos_procesados"].append({
                                "nombre": nombre_interno,
                                "estado": "duplicado",
                                "tipo": tipo_duplicado
                            })
                            
                    except Exception as e:
                        logger.error(f"[NetCash ZIP] Error procesando {nombre_interno}: {str(e)}")
                        resultado["no_legibles"] += 1
                        resultado["archivos_procesados"].append({
                            "nombre": nombre_interno,
                            "estado": "error",
                            "razon": str(e)
                        })
            
            logger.info(f"[NetCash ZIP] Procesamiento completado: {resultado}")
            return resultado
            
        except Exception as e:
            logger.error(f"[NetCash ZIP] Error procesando ZIP: {str(e)}")
            import traceback
            traceback.print_exc()
            return resultado
            
        finally:
            # Limpiar directorio temporal
            if temp_dir and Path(temp_dir).exists():
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"[NetCash ZIP] Directorio temporal eliminado: {temp_dir}")
                except Exception as e:
                    logger.warning(f"[NetCash ZIP] No se pudo eliminar directorio temporal: {str(e)}")
    
    
    async def guardar_datos_captura_manual(
        self,
        solicitud_id: str,
        num_comprobantes: int,
        monto_total: float,
        beneficiario: str,
        num_ligas: int,
        idmex_beneficiario: Optional[str] = None
    ) -> bool:
        """
        Guarda los datos capturados manualmente del usuario cuando el OCR falla
        
        Args:
            solicitud_id: ID de la solicitud
            num_comprobantes: Número de comprobantes declarado por el usuario
            monto_total: Monto total declarado
            beneficiario: Beneficiario declarado
            num_ligas: Número de ligas solicitadas
            idmex_beneficiario: IDMEX del beneficiario (persona física)
        
        Returns:
            True si se guardó exitosamente
        """
        logger.info(f"[NetCash-Manual] Guardando datos de captura manual para {solicitud_id}")
        logger.info(f"[NetCash-Manual] Comprobantes: {num_comprobantes}, Monto: ${monto_total:,.2f}")
        logger.info(f"[NetCash-Manual] Beneficiario: {beneficiario}, IDMEX: {idmex_beneficiario}, Ligas: {num_ligas}")
        
        try:
            update_data = {
                "estado": "esperando_validacion_ana",  # ⭐ Estado correcto para que aparezca en web
                "origen_montos": "manual_cliente",
                "num_comprobantes_declarado": num_comprobantes,
                "monto_total_declarado": monto_total,
                "beneficiario_declarado": beneficiario,
                "beneficiario_reportado": beneficiario,  # Para compatibilidad con vista web
                "cantidad_ligas_reportada": num_ligas,
                "ligas_solicitadas": num_ligas,
                "validado_por_ana": False,  # Pendiente de validación
                "updated_at": datetime.now(timezone.utc)
            }
            
            # Agregar IDMEX del beneficiario si existe
            if idmex_beneficiario:
                update_data["idmex_beneficiario_declarado"] = idmex_beneficiario
                update_data["idmex_reportado"] = idmex_beneficiario  # Para compatibilidad
            
            logger.info(f"[NetCash-Manual] Actualizando estado a 'esperando_validacion_ana'")
            
            result = await db[COLLECTION_NAME].update_one(
                {"id": solicitud_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"[NetCash-Manual] ✅ Datos guardados correctamente")
                
                # ⭐ IMPORTANTE: Actualizar los comprobantes con el monto declarado
                # Esto es necesario para que los cálculos funcionen
                solicitud = await self.obtener_solicitud(solicitud_id)
                if solicitud:
                    comprobantes = solicitud.get("comprobantes", [])
                    if comprobantes and num_comprobantes > 0:
                        # Distribuir el monto total entre los comprobantes
                        monto_por_comprobante = monto_total / len(comprobantes) if len(comprobantes) > 0 else monto_total
                        
                        for comp in comprobantes:
                            # Si el comprobante no tiene monto detectado, asignarle uno
                            if not comp.get("monto_detectado") and not comp.get("monto"):
                                comp["monto"] = monto_por_comprobante
                                comp["monto_detectado"] = monto_por_comprobante
                                comp["es_valido"] = True
                                comp["captura_manual"] = True
                        
                        # Guardar comprobantes actualizados
                        await db[COLLECTION_NAME].update_one(
                            {"id": solicitud_id},
                            {"$set": {
                                "comprobantes": comprobantes,
                                "monto_depositado_cliente": monto_total
                            }}
                        )
                        logger.info(f"[NetCash-Manual] Comprobantes actualizados con monto declarado: ${monto_por_comprobante:,.2f} c/u")
                
                # P2: Registrar en colección de aprendizaje
                try:
                    if solicitud:
                        await netcash_pdf_learning_service.registrar_caso_aprendizaje(
                            solicitud=solicitud,
                            validado_por_ana=False
                        )
                except Exception as e:
                    logger.warning(f"[NetCash-Manual] No se pudo registrar en learning: {str(e)}")
                
                return True
            else:
                logger.error(f"[NetCash-Manual] ❌ No se pudo guardar (solicitud no encontrada?)")
                return False
                
        except Exception as e:
            logger.exception(f"[NetCash-Manual] Error guardando datos: {str(e)}")
            return False
    

    def _calcular_hash_archivo(self, archivo_url: str) -> str:
        """
        Calcula hash SHA-256 del contenido de un archivo.
        
        Args:
            archivo_url: Ruta al archivo
        
        Returns:
            Hash SHA-256 en formato hexadecimal
        """
        import hashlib
        
        try:
            with open(archivo_url, 'rb') as f:
                file_hash = hashlib.sha256()
                # Leer en chunks para archivos grandes
                while chunk := f.read(8192):
                    file_hash.update(chunk)
                return file_hash.hexdigest()
        except Exception as e:
            logger.error(f"[NetCash] Error calculando hash: {str(e)}")
            # Retornar hash basado en nombre+timestamp como fallback
            import time
            fallback = f"{archivo_url}_{time.time()}"
            return hashlib.sha256(fallback.encode()).hexdigest()
    
    # ==================== VALIDACIONES (REGLAS DURAS) ====================
    
    async def validar_solicitud_completa(self, solicitud_id: str) -> Tuple[bool, Dict]:
        """
        Aplica TODAS las reglas duras a una solicitud.
        
        Este es el corazón del motor NetCash. Valida:
        1. Cliente activo
        2. Beneficiario (3+ palabras, sin números)
        3. IDMEX (10 dígitos exactos)
        4. Ligas (> 0)
        5. Comprobante (CLABE completa + beneficiario de cuenta activa)
        
        Args:
            solicitud_id: ID de la solicitud
        
        Returns:
            Tupla (todas_validas: bool, validaciones: dict)
        """
        logger.info(f"[NetCash] ========== VALIDAR SOLICITUD COMPLETA ==========")
        logger.info(f"[NetCash] Solicitud: {solicitud_id}")
        
        # Obtener solicitud
        solicitud = await db[COLLECTION_NAME].find_one({"id": solicitud_id}, {"_id": 0})
        if not solicitud:
            logger.error(f"[NetCash] Solicitud {solicitud_id} no encontrada")
            return False, {}
        
        validaciones = {}
        
        # 1. Validar cliente
        validaciones["cliente"] = await self._validar_cliente(
            solicitud.get("cliente_id")
        )
        
        # 2. Validar beneficiario
        validaciones["beneficiario"] = self._validar_beneficiario(
            solicitud.get("beneficiario_reportado")
        )
        
        # 3. Validar IDMEX
        validaciones["idmex"] = self._validar_idmex(
            solicitud.get("idmex_reportado")
        )
        
        # 4. Validar ligas
        validaciones["ligas"] = self._validar_ligas(
            solicitud.get("cantidad_ligas_reportada")
        )
        
        # 5. Validar comprobante
        validaciones["comprobante"] = self._validar_comprobantes_solicitud(
            solicitud.get("comprobantes", [])
        )
        
        # Actualizar validaciones en BD
        await db[COLLECTION_NAME].update_one(
            {"id": solicitud_id},
            {"$set": {
                "validacion": validaciones,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        # Verificar si TODAS son válidas
        todas_validas = all(v.get("valido", False) for v in validaciones.values())
        
        logger.info(f"[NetCash] Resultado validación: {'✅ TODAS VÁLIDAS' if todas_validas else '❌ HAY ERRORES'}")
        for campo, val in validaciones.items():
            status = "✅" if val.get("valido") else "❌"
            logger.info(f"[NetCash]   {status} {campo}: {val.get('razon')}")
        
        return todas_validas, validaciones
    
    async def _validar_cliente(self, cliente_id: str) -> Dict:
        """Valida que el cliente exista y esté activo"""
        try:
            cliente = await db.clientes.find_one({"id": cliente_id}, {"_id": 0})
            
            if not cliente:
                return {"valido": False, "razon": "Cliente no encontrado en catálogo"}
            
            if cliente.get("estado") != "activo":
                return {"valido": False, "razon": f"Cliente no está activo (estado: {cliente.get('estado')})"}
            
            return {"valido": True, "razon": "Cliente activo encontrado"}
            
        except Exception as e:
            logger.error(f"[NetCash] Error validando cliente: {str(e)}")
            return {"valido": False, "razon": f"Error: {str(e)}"}
    
    def _validar_beneficiario(self, beneficiario: Optional[str]) -> Dict:
        """
        Valida beneficiario: mínimo 3 palabras, sin números.
        Ejemplo válido: DANIEL FELIPE GALVEZ MAGALLON
        """
        if not beneficiario or not beneficiario.strip():
            return {"valido": False, "razon": "Beneficiario no proporcionado"}
        
        # Limpiar y contar palabras (solo letras)
        palabras = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]+", beneficiario)
        
        if len(palabras) < 3:
            return {
                "valido": False,
                "razon": f"Beneficiario debe tener mínimo 3 palabras (nombre + 2 apellidos). Detectadas: {len(palabras)}"
            }
        
        # Verificar que no tenga números
        if re.search(r'\d', beneficiario):
            return {"valido": False, "razon": "Beneficiario no debe contener números"}
        
        return {"valido": True, "razon": f"Beneficiario válido ({len(palabras)} palabras)"}
    
    def _validar_idmex(self, idmex: Optional[str]) -> Dict:
        """Valida IDMEX: exactamente 10 dígitos"""
        if not idmex:
            return {"valido": False, "razon": "IDMEX no proporcionado"}
        
        # Limpiar espacios
        idmex_limpio = idmex.strip()
        
        # Verificar que tenga exactamente 10 dígitos
        if not re.match(r'^[0-9]{10}$', idmex_limpio):
            longitud = len(idmex_limpio) if idmex_limpio.isdigit() else "no numérico"
            return {
                "valido": False,
                "razon": f"IDMEX debe tener exactamente 10 dígitos. Recibido: {longitud}"
            }
        
        return {"valido": True, "razon": "IDMEX válido (10 dígitos)"}
    
    def _validar_ligas(self, cantidad: Optional[int]) -> Dict:
        """Valida cantidad de ligas: debe ser entero > 0"""
        if cantidad is None:
            return {"valido": False, "razon": "Cantidad de ligas no proporcionada"}
        
        try:
            cantidad_int = int(cantidad)
            if cantidad_int <= 0:
                return {"valido": False, "razon": f"Cantidad de ligas debe ser mayor a 0. Recibido: {cantidad_int}"}
            
            return {"valido": True, "razon": f"Cantidad válida: {cantidad_int} ligas"}
            
        except (ValueError, TypeError):
            return {"valido": False, "razon": f"Cantidad de ligas debe ser un número entero. Recibido: {cantidad}"}
    
    def _validar_comprobantes_solicitud(self, comprobantes: List[Dict]) -> Dict:
        """Valida que haya al menos un comprobante válido"""
        if not comprobantes or len(comprobantes) == 0:
            return {"valido": False, "razon": "No hay comprobantes adjuntos"}
        
        comprobantes_validos = [c for c in comprobantes if c.get("es_valido", False)]
        
        if len(comprobantes_validos) == 0:
            razones = [c.get("validacion_detalle", {}).get("razon", "Sin razón") 
                      for c in comprobantes]
            return {
                "valido": False,
                "razon": f"Ningún comprobante es válido. Razones: {'; '.join(razones)}"
            }
        
        return {
            "valido": True,
            "razon": f"{len(comprobantes_validos)} comprobante(s) válido(s)"
        }
    
    # ==================== GESTIÓN DE ESTADOS ====================
    
    async def cambiar_estado(self, solicitud_id: str, nuevo_estado: EstadoSolicitud,
                            notas: Optional[str] = None) -> bool:
        """
        Cambia el estado de una solicitud.
        Si el nuevo estado es LISTA_PARA_MBC y no tiene folio, lo genera.
        
        Args:
            solicitud_id: ID de la solicitud
            nuevo_estado: Nuevo estado
            notas: Notas opcionales sobre el cambio
        
        Returns:
            True si se cambió correctamente
        """
        try:
            solicitud = await db[COLLECTION_NAME].find_one({"id": solicitud_id})
            if not solicitud:
                logger.error(f"[NetCash] Solicitud {solicitud_id} no encontrada")
                return False
            
            estado_actual = solicitud.get("estado")
            
            logger.info(f"[NetCash] Cambio de estado: {estado_actual} -> {nuevo_estado.value}")
            
            # Preparar actualización
            update_data = {
                "estado": nuevo_estado.value,
                "updated_at": datetime.now(timezone.utc)
            }
            
            # Si pasa a LISTA_PARA_MBC y no tiene folio, generar
            if nuevo_estado == EstadoSolicitud.LISTA_PARA_MBC and not solicitud.get("folio_mbco"):
                folio = await self._generar_folio_mbco()
                update_data["folio_mbco"] = folio
                logger.info(f"[NetCash] Folio generado: {folio}")
            
            # Agregar al histórico
            historico_entry = {
                "estado": nuevo_estado.value,
                "en": datetime.now(timezone.utc),
                "por": "sistema",
                "notas": notas or f"Cambio automático a {nuevo_estado.value}"
            }
            
            await db[COLLECTION_NAME].update_one(
                {"id": solicitud_id},
                {
                    "$set": update_data,
                    "$push": {"estado_historico": historico_entry}
                }
            )
            
            logger.info(f"[NetCash] ✅ Estado actualizado a {nuevo_estado.value}")
            return True
            
        except Exception as e:
            logger.error(f"[NetCash] Error cambiando estado: {str(e)}")
            return False
    
    async def procesar_solicitud_automaticamente(self, solicitud_id: str) -> Tuple[bool, str]:
        """
        Procesa una solicitud automáticamente:
        1. Valida todos los campos
        2. Si TODO está bien -> Calcula totales y comisiones, guarda en BD, LISTA_PARA_MBC
        3. Si algo falla -> RECHAZADA
        
        Args:
            solicitud_id: ID de la solicitud
        
        Returns:
            Tupla (exitoso, mensaje)
        """
        logger.info(f"[NetCash] Procesando solicitud automáticamente: {solicitud_id}")
        
        # Validar completamente
        todas_validas, validaciones = await self.validar_solicitud_completa(solicitud_id)
        
        if todas_validas:
            # Obtener solicitud para calcular totales
            solicitud = await db[COLLECTION_NAME].find_one({"id": solicitud_id}, {"_id": 0})
            
            # Calcular suma de todos los comprobantes válidos
            comprobantes = solicitud.get("comprobantes", [])
            comprobantes_validos = [c for c in comprobantes if c.get("es_valido", False)]
            comprobantes_invalidos = [c for c in comprobantes if not c.get("es_valido", False)]
            
            total_comprobantes_validos = 0.0
            for comp in comprobantes_validos:
                monto = comp.get("monto_detectado")
                if monto and monto > 0:
                    total_comprobantes_validos += monto
            
            # Calcular comisiones
            porcentaje_comision_cliente = 1.00  # 1.00%
            comision_cliente = total_comprobantes_validos * (porcentaje_comision_cliente / 100)
            monto_ligas = total_comprobantes_validos - comision_cliente
            
            # Obtener cuenta NetCash utilizada
            cuenta_activa = await cuenta_deposito_service.obtener_cuenta_activa()
            cuenta_netcash_info = None
            if cuenta_activa:
                cuenta_netcash_info = {
                    "banco": cuenta_activa.get("banco"),
                    "clabe": cuenta_activa.get("clabe"),
                    "beneficiario": cuenta_activa.get("beneficiario")
                }
            
            # Actualizar solicitud con todos los datos completos
            update_data = {
                "total_comprobantes_validos": total_comprobantes_validos,
                "num_comprobantes_validos": len(comprobantes_validos),
                "num_comprobantes_invalidos": len(comprobantes_invalidos),
                "porcentaje_comision_cliente": porcentaje_comision_cliente,
                "comision_cliente": comision_cliente,
                "monto_ligas": monto_ligas,
                "cuenta_netcash_usada": cuenta_netcash_info,
                "updated_at": datetime.now(timezone.utc)
            }
            
            await db[COLLECTION_NAME].update_one(
                {"id": solicitud_id},
                {"$set": update_data}
            )
            
            logger.info(f"[NetCash] Totales calculados y guardados: total=${total_comprobantes_validos:,.2f}, comisión=${comision_cliente:,.2f}, monto_ligas=${monto_ligas:,.2f}")
            
            # TODO OK -> LISTA_PARA_MBC
            await self.cambiar_estado(
                solicitud_id,
                EstadoSolicitud.LISTA_PARA_MBC,
                "Todas las validaciones pasaron"
            )
            
            # Notificar a Ana que hay una nueva solicitud lista para MBco
            logger.info(f"[NetCash] Obteniendo solicitud actualizada para notificar a Ana...")
            solicitud_actualizada = await db[COLLECTION_NAME].find_one({"id": solicitud_id}, {"_id": 0})
            logger.info(f"[NetCash] Llamando a _notificar_ana_solicitud_lista() para solicitud {solicitud_id}")
            await self._notificar_ana_solicitud_lista(solicitud_actualizada)
            logger.info(f"[NetCash] Notificación a Ana completada (o fallida, ver logs [NOTIF_ANA])")
            
            return True, "Solicitud válida y lista para proceso MBco"
        else:
            # Hay errores -> RECHAZADA
            errores = [f"{campo}: {val.get('razon')}" 
                      for campo, val in validaciones.items() 
                      if not val.get("valido")]
            
            await self.cambiar_estado(
                solicitud_id,
                EstadoSolicitud.RECHAZADA,
                f"Validaciones fallidas: {'; '.join(errores)}"
            )
            return False, f"Solicitud rechazada: {'; '.join(errores)}"
    
    # ==================== GENERACIÓN DE RESÚMENES ====================
    
    async def generar_resumen_cliente(self, solicitud_id: str) -> Optional[ResumenCliente]:
        """
        Genera un resumen amigable para mostrar al cliente.
        
        Este es el formato estándar que usan todos los canales.
        
        Returns:
            ResumenCliente con los 3 bloques:
            1. "Esto es lo que entendí"
            2. "Esto falta o está mal"
            3. "Qué sigue"
        """
        try:
            solicitud = await db[COLLECTION_NAME].find_one({"id": solicitud_id}, {"_id": 0})
            if not solicitud:
                return None
            
            validacion = solicitud.get("validacion", {})
            
            # Bloque 1: Campos detectados y cuáles son válidos
            campos_detectados = {
                "beneficiario": solicitud.get("beneficiario_reportado", "No detectado"),
                "idmex": solicitud.get("idmex_reportado", "No detectado"),
                "ligas": solicitud.get("cantidad_ligas_reportada", "No detectado"),
                "comprobantes": len(solicitud.get("comprobantes", []))
            }
            
            campos_validos = [campo for campo, val in validacion.items() 
                            if val.get("valido", False)]
            
            # Bloque 2: Campos faltantes e inválidos
            campos_faltantes = []
            campos_invalidos = []
            
            for campo, val in validacion.items():
                if not val.get("valido", False):
                    razon = val.get("razon", "Sin razón")
                    if "no proporcionado" in razon.lower() or "no detectado" in razon.lower():
                        campos_faltantes.append(campo)
                    else:
                        campos_invalidos.append({"campo": campo, "razon": razon})
            
            # Bloque 3: Mensaje de siguiente paso
            estado = solicitud.get("estado")
            if estado == EstadoSolicitud.LISTA_PARA_MBC.value:
                mensaje_siguiente = f"✅ Tu solicitud está registrada y lista para proceso. Folio: {solicitud.get('folio_mbco')}"
            elif estado == EstadoSolicitud.RECHAZADA.value:
                mensaje_siguiente = "❌ Tu solicitud tiene errores. Por favor corrige lo indicado y vuelve a enviar."
            else:
                mensaje_siguiente = "Estamos procesando tu información. Te avisaremos del resultado."
            
            # Obtener cuenta concertadora
            cuenta = await cuenta_deposito_service.obtener_cuenta_activa()
            cuenta_info = None
            if cuenta:
                cuenta_info = {
                    "banco": cuenta.get("banco"),
                    "clabe": cuenta.get("clabe"),
                    "beneficiario": cuenta.get("beneficiario")
                }
            
            resumen = ResumenCliente(
                solicitud_id=solicitud_id,
                folio_mbco=solicitud.get("folio_mbco"),
                estado=EstadoSolicitud(estado),
                campos_detectados=campos_detectados,
                campos_validos=campos_validos,
                campos_faltantes=campos_faltantes,
                campos_invalidos=campos_invalidos,
                mensaje_siguiente_paso=mensaje_siguiente,
                cuenta_concertadora=cuenta_info
            )
            
            return resumen
            
        except Exception as e:
            logger.error(f"[NetCash] Error generando resumen: {str(e)}")
            return None
    
    # ==================== UTILIDADES ====================
    
    async def _generar_folio_mbco(self) -> str:
        """
        Genera un folio NetCash secuencial (NC-000001, NC-000002, ...)
        
        Returns:
            Folio en formato NC-XXXXXX
        """
        try:
            # Buscar el último folio generado
            ultima_solicitud = await db[COLLECTION_NAME].find_one(
                {"folio_mbco": {"$exists": True, "$ne": None}},
                {"folio_mbco": 1},
                sort=[("folio_mbco", -1)]
            )
            
            if ultima_solicitud and ultima_solicitud.get("folio_mbco"):
                ultimo_folio = ultima_solicitud.get("folio_mbco")
                # Extraer número (NC-000048 -> 48)
                numero = int(ultimo_folio.split("-")[1])
                nuevo_numero = numero + 1
            else:
                # Primera solicitud
                nuevo_numero = 1
            
            folio = f"NC-{nuevo_numero:06d}"
            logger.info(f"[NetCash] Folio generado: {folio}")
            return folio
            
        except Exception as e:
            logger.error(f"[NetCash] Error generando folio: {str(e)}")
            # Fallback: usar timestamp
            timestamp = int(datetime.now(timezone.utc).timestamp())
            return f"NC-{timestamp}"
    
    def _extraer_clabes_del_texto(self, texto: str) -> List[str]:
        """Extrae CLABEs (18 dígitos) del texto"""
        if not texto:
            return []
        clabes = re.findall(r'\b(\d{18})\b', texto)
        return clabes
    
    def _extraer_monto_del_texto(self, texto: str) -> Optional[float]:
        """Intenta extraer un monto del texto del comprobante"""
        if not texto:
            return None
        
        # Buscar patrones como: $10,000.00, $10000, etc.
        patrones = [
            r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'(?:monto|importe|total)[\s:]+\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        ]
        
        for patron in patrones:
            matches = re.findall(patron, texto, re.IGNORECASE)
            if matches:
                try:
                    # Limpiar formato y convertir
                    monto_str = matches[0].replace(',', '')
                    return float(monto_str)
                except:
                    continue
        
        return None
    
    # ==================== CONSULTAS ====================
    
    async def obtener_solicitud(self, solicitud_id: str) -> Optional[Dict]:
        """Obtiene una solicitud por ID"""
        solicitud = await db[COLLECTION_NAME].find_one({"id": solicitud_id}, {"_id": 0})
        return solicitud
    
    async def listar_solicitudes_cliente(self, cliente_id: str, 
                                        solo_validas: bool = False,
                                        limite: int = 20) -> List[Dict]:
        """
        Lista solicitudes de un cliente.
        
        Args:
            cliente_id: ID del cliente
            solo_validas: Si True, solo muestra las que están en lista_para_mbc
            limite: Número máximo de resultados
        
        Returns:
            Lista de solicitudes
        """
        try:
            filtro = {"cliente_id": cliente_id, "legacy": False}
            
            if solo_validas:
                filtro["estado"] = EstadoSolicitud.LISTA_PARA_MBC.value
            
            solicitudes = await db[COLLECTION_NAME].find(
                filtro,
                {"_id": 0}
            ).sort("created_at", -1).limit(limite).to_list(limite)
            
            return solicitudes
            
        except Exception as e:
            logger.error(f"[NetCash] Error listando solicitudes: {str(e)}")
            return []
    
    async def verificar_folio_mbco_existe(self, folio_mbco: str) -> bool:
        """
        Verifica si un folio MBco ya está asignado a alguna solicitud
        
        Args:
            folio_mbco: Folio MBco a verificar
            
        Returns:
            True si el folio ya existe, False si no
        """
        try:
            solicitud = await db[COLLECTION_NAME].find_one(
                {"folio_mbco": folio_mbco},
                {"_id": 0, "id": 1}
            )
            return solicitud is not None
        except Exception as e:
            logger.error(f"[NetCash] Error verificando folio MBco: {str(e)}")
            return False
    
    async def asignar_folio_mbco_y_generar_orden_interna(
        self,
        solicitud_id: str,
        folio_mbco: str,
        usuario_asigna: str
    ) -> Dict:
        """
        Asigna folio MBco a una solicitud y genera la orden interna para Tesorería
        
        Este es el punto de orquestación que:
        1. Asigna el folio MBco a la solicitud
        2. Cambia estado a 'orden_interna_generada'
        3. Genera la orden interna (estructura de datos para Tesorería)
        4. Envía correo a Tesorería con layout + comprobantes
        5. Notifica a Tesorería por Telegram
        
        Args:
            solicitud_id: ID de la solicitud
            folio_mbco: Folio MBco asignado por Ana
            usuario_asigna: Username o ID del usuario que asigna (Ana)
            
        Returns:
            Dict con resultado:
            {
                "success": bool,
                "solicitud": dict (si success),
                "orden_interna": dict (si success),
                "error": str (si no success)
            }
        """
        try:
            logger.info(f"[NetCash] Iniciando asignación folio MBco: {folio_mbco} para solicitud {solicitud_id}")
            
            # 1. Obtener solicitud actual
            solicitud = await db[COLLECTION_NAME].find_one({"id": solicitud_id}, {"_id": 0})
            
            if not solicitud:
                return {"success": False, "error": "Solicitud no encontrada"}
            
            # Verificar estado correcto
            if solicitud.get("estado") != "lista_para_mbc":
                return {
                    "success": False, 
                    "error": f"Solicitud no está en estado 'lista_para_mbc' (estado actual: {solicitud.get('estado')})"
                }
            
            # 2. Actualizar solicitud con folio MBco
            ahora = datetime.now(timezone.utc)
            
            update_data = {
                "folio_mbco": folio_mbco,
                "estado": "orden_interna_generada",
                "fecha_asignacion_mbco": ahora,
                "usuario_asigna_mbco": usuario_asigna,
                "updated_at": ahora
            }
            
            await db[COLLECTION_NAME].update_one(
                {"id": solicitud_id},
                {"$set": update_data}
            )
            
            logger.info(f"[NetCash] Folio MBco asignado: {folio_mbco}")
            
            # 3. NUEVO FLUJO: Procesar operación de tesorería individual
            # (Layout CSV + correo por operación + estado enviado_a_tesoreria)
            try:
                logger.info(f"[NetCash] Iniciando proceso de tesorería por operación para {solicitud_id}")
                
                from tesoreria_operacion_service import tesoreria_operacion_service
                resultado_tesoreria = await tesoreria_operacion_service.procesar_operacion_tesoreria(solicitud_id)
                
                if resultado_tesoreria and resultado_tesoreria.get('success'):
                    logger.info(f"[NetCash] ✅ Tesorería por operación procesada exitosamente")
                else:
                    logger.warning(f"[NetCash] ⚠️ Problema procesando tesorería por operación")
                    # NO fallar todo el flujo, solo advertir
                    
            except Exception as e:
                logger.error(f"[NetCash] ❌ Error en tesorería por operación: {str(e)}")
                import traceback
                traceback.print_exc()
                # NO fallar todo el flujo, continuar
            
            # 6. Obtener solicitud actualizada
            solicitud_actualizada = await db[COLLECTION_NAME].find_one({"id": solicitud_id}, {"_id": 0})
            
            return {
                "success": True,
                "solicitud": solicitud_actualizada
            }
            
        except Exception as e:
            logger.error(f"[NetCash] Error asignando folio MBco: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def _generar_orden_interna_tesoreria(self, solicitud_id: str, folio_mbco: str) -> Dict:
        """
        Genera la orden interna que Tesorería usará para enviar las ligas
        
        Args:
            solicitud_id: ID de la solicitud
            folio_mbco: Folio MBco asignado
            
        Returns:
            Dict con la orden interna generada
        """
        # Obtener solicitud
        solicitud = await db[COLLECTION_NAME].find_one({"id": solicitud_id}, {"_id": 0})
        
        if not solicitud:
            raise ValueError(f"Solicitud {solicitud_id} no encontrada")
        
        # Calcular totales
        comprobantes = solicitud.get("comprobantes", [])
        total_depositos = sum(
            c.get("monto_detectado", 0) 
            for c in comprobantes 
            if c.get("es_valido") and not c.get("es_duplicado")
        )
        
        comision_netcash = solicitud.get("comision_cliente", total_depositos * 0.01)
        monto_ligas = total_depositos - comision_netcash
        num_ligas = solicitud.get("num_ligas", 0)
        
        # Crear orden interna
        from uuid import uuid4
        orden_interna = {
            "id": f"OI-{uuid4().hex[:8]}",
            "folio_mbco": folio_mbco,
            "solicitud_id": solicitud_id,
            "estado": "pendiente_envio_ligas",  # Estados: pendiente_envio_ligas, ligas_enviadas, completada
            "beneficiario": solicitud.get("beneficiario"),
            "idmex": solicitud.get("idmex"),
            "num_ligas": num_ligas,
            "monto_total_ligas": monto_ligas,
            "monto_por_liga": monto_ligas / num_ligas if num_ligas > 0 else 0,
            "comprobantes_adjuntos": [
                {
                    "nombre": c.get("nombre_archivo"),
                    "url": c.get("archivo_url"),
                    "monto": c.get("monto_detectado")
                }
                for c in comprobantes
                if c.get("es_valido") and not c.get("es_duplicado")
            ],
            "created_at": datetime.now(timezone.utc),
            "created_by": "ana_mbco"
        }
        
        # Guardar en colección de órdenes internas
        await db["ordenes_internas_tesoreria"].insert_one(orden_interna)
        
        logger.info(f"[NetCash] Orden interna generada: {orden_interna['id']}")
        
        return orden_interna
    
    async def _enviar_correo_tesoreria(self, solicitud_id: str, orden_interna: Dict):
        """
        Envía correo a Tesorería con layout + comprobantes adjuntos
        
        Args:
            solicitud_id: ID de la solicitud
            orden_interna: Dict con la orden interna generada
        """
        # TODO: Implementar envío de correo
        # Por ahora, solo logueamos
        logger.info(f"[NetCash] 📧 Correo a Tesorería (MOCK)")
        logger.info(f"  - Para: tesoreria@mbco.com")
        logger.info(f"  - Asunto: Orden Interna {orden_interna['id']} - {orden_interna['folio_mbco']}")
        logger.info(f"  - Layout: {orden_interna['num_ligas']} liga(s) x ${orden_interna['monto_por_liga']:,.2f}")
        logger.info(f"  - Comprobantes adjuntos: {len(orden_interna['comprobantes_adjuntos'])}")
        
        # Hook para implementación futura
        # await enviar_correo_smtp(
        #     destinatario="tesoreria@mbco.com",
        #     asunto=f"Orden Interna {orden_interna['id']} - {orden_interna['folio_mbco']}",
        #     cuerpo=self._generar_layout_correo(orden_interna),
        #     adjuntos=[c['url'] for c in orden_interna['comprobantes_adjuntos']]
        # )
    
    async def _notificar_tesoreria_telegram(self, solicitud_id: str, orden_interna: Dict):
        """
        Notifica a Tesorería por Telegram sobre nueva orden interna
        
        Notifica a todos los usuarios con permiso "recibe_alertas_tesoreria"
        
        Args:
            solicitud_id: ID de la solicitud
            orden_interna: Dict con la orden interna generada
        """
        # Obtener usuarios de tesorería desde el catálogo
        from usuarios_repo import usuarios_repo
        
        usuarios_tesoreria = await usuarios_repo.obtener_usuarios_por_permiso("recibe_alertas_tesoreria", True)
        
        if not usuarios_tesoreria:
            logger.warning(f"[NetCash] No se encontraron usuarios con permiso 'recibe_alertas_tesoreria'")
            return
        
        # Importar handlers
        from telegram_tesoreria_handlers import telegram_tesoreria_handlers
        
        if not telegram_tesoreria_handlers:
            logger.warning(f"[NetCash] telegram_tesoreria_handlers no inicializado, notificación no enviada")
            return
        
        # Enviar notificación a cada usuario de tesorería
        for usuario in usuarios_tesoreria:
            if not usuario.get("telegram_id"):
                logger.warning(f"[NetCash] Usuario {usuario.get('nombre')} ({usuario.get('rol_negocio')}) no tiene telegram_id configurado")
                continue
            
            try:
                await telegram_tesoreria_handlers.notificar_nueva_orden_interna(orden_interna, usuario)
                logger.info(f"[NetCash] Notificación enviada a {usuario.get('nombre')} (Tesorería)")
            except Exception as e:
                logger.error(f"[NetCash] Error enviando notificación a {usuario.get('nombre')}: {str(e)}")
    
    async def _notificar_ana_solicitud_lista(self, solicitud: Dict):
        """
        Notifica a Ana cuando una solicitud queda lista para MBco.
        
        NOTA: Usa directamente la API de Telegram (httpx) para evitar
        dependencias circulares con telegram_ana_handlers que puede no
        estar inicializado cuando se llama desde el motor.
        
        Args:
            solicitud: Dict con los datos de la solicitud
        """
        import httpx
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        folio_mbco = solicitud.get('folio_mbco', 'N/A')
        solicitud_id = solicitud.get('id')
        
        logger.info(f"[NOTIF_ANA] ========== INICIO NOTIFICACIÓN A ANA ==========")
        logger.info(f"[NOTIF_ANA] Solicitud: {folio_mbco}")
        
        # Obtener usuario Ana desde el catálogo
        from usuarios_repo import usuarios_repo
        
        logger.info(f"[NOTIF_ANA] Consultando usuario con rol 'admin_netcash' en catálogo...")
        ana = await usuarios_repo.obtener_usuario_por_rol("admin_netcash")
        
        if not ana:
            logger.error(f"[NOTIF_ANA] ERROR: No se encontró usuario con rol 'admin_netcash' en el catálogo")
            return
        
        logger.info(f"[NOTIF_ANA] Usuario encontrado: {ana.get('nombre')}")
        
        telegram_id = ana.get("telegram_id")
        if not telegram_id:
            logger.error(f"[NOTIF_ANA] ERROR: Usuario {ana.get('nombre')} no tiene telegram_id configurado")
            return
        
        logger.info(f"[NOTIF_ANA] Preparando mensaje para Ana | chat_id={telegram_id}")
        
        # Construir el mensaje (mismo formato que en telegram_ana_handlers)
        cliente_nombre = solicitud.get("cliente_nombre", "N/A")
        beneficiario = solicitud.get("beneficiario_reportado", "N/A")
        idmex = solicitud.get("idmex_reportado", "N/A")
        num_ligas = solicitud.get("cantidad_ligas_reportada", 0)
        
        # Calcular totales
        comprobantes = solicitud.get("comprobantes", [])
        total_depositos = sum(
            c.get("monto_detectado", 0) 
            for c in comprobantes 
            if c.get("es_valido") and not c.get("es_duplicado")
        )
        
        comision_netcash = solicitud.get("comision_cliente", total_depositos * 0.01)
        monto_ligas = total_depositos - comision_netcash
        
        created_at = solicitud.get("created_at")
        fecha_str = created_at.strftime("%d/%m/%Y %H:%M") if created_at else "N/A"
        
        # Detectar origen de datos
        modo_captura = solicitud.get("modo_captura", "ocr_ok")
        
        mensaje = "🧾 *Nueva solicitud NetCash lista para MBco*\n\n"
        mensaje += f"📋 *Folio NetCash:* {folio_mbco}\n"
        mensaje += f"🧑‍💼 *Cliente:* {cliente_nombre}\n"
        
        if modo_captura == "manual_por_fallo_ocr":
            mensaje += "\n⚠️ *CAPTURA MANUAL* - OCR no pudo leer comprobante\n"
            mensaje += f"📊 *Origen datos:* Manual (capturado por cliente)\n\n"
        else:
            mensaje += f"✅ *Origen datos:* Robot (OCR confiable)\n\n"
        
        mensaje += f"👤 *Beneficiario:* {beneficiario}\n"
        mensaje += f"🆔 *IDMEX:* {idmex}\n"
        mensaje += f"💰 *Total depósitos:* ${total_depositos:,.2f}\n"
        mensaje += f"📊 *Comisión NetCash (1%):* ${comision_netcash:,.2f}\n"
        mensaje += f"💸 *Monto a enviar (ligas):* ${monto_ligas:,.2f}\n"
        mensaje += f"🔗 *Número de ligas:* {num_ligas}\n"
        mensaje += f"📅 *Fecha creación:* {fecha_str}\n"
        
        # Botones inline
        inline_keyboard = [
            [{"text": "✅ Validar y asignar folio MBco", "callback_data": f"ana_asignar_folio_{solicitud_id}"}],
            [{"text": "❌ Rechazar operación", "callback_data": f"ana_rechazar_{solicitud_id}"}]
        ]
        
        # Enviar usando API directa de Telegram
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not telegram_token:
            logger.error(f"[NOTIF_ANA] ERROR: TELEGRAM_BOT_TOKEN no configurado")
            return
        
        try:
            async with httpx.AsyncClient() as client:
                url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                payload = {
                    "chat_id": telegram_id,
                    "text": mensaje,
                    "parse_mode": "Markdown",
                    "reply_markup": {"inline_keyboard": inline_keyboard}
                }
                
                response = await client.post(url, json=payload, timeout=30.0)
                
                if response.status_code == 200:
                    logger.info(f"[NOTIF_ANA] ✅ Mensaje enviado exitosamente a Ana (chat_id={telegram_id})")
                else:
                    logger.error(f"[NOTIF_ANA] ERROR: Telegram API respondió {response.status_code}: {response.text}")
                    
        except Exception as e:
            logger.error(f"[NOTIF_ANA] ERROR enviando notificación: {str(e)}")
            import traceback
            logger.error(f"[NOTIF_ANA] Traceback: {traceback.format_exc()}")
        
        logger.info(f"[NOTIF_ANA] ========== FIN NOTIFICACIÓN A ANA ==========")


# Instancia global del servicio
netcash_service = NetCashService()
