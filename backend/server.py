from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from typing import List, Optional
import shutil
from datetime import datetime, timezone
import hashlib

from models import (
    OperacionNetCash,
    OperacionNetCashCreate,
    Cliente,
    ClienteCreate,
    EstadoOperacion,
    ComprobanteDepositoOCR,
    CalculosNetCash
)
from config import CUENTA_DEPOSITO_CLIENTE, MODO_MANTENIMIENTO, MENSAJE_BIENVENIDA_CUENTA
from ocr_service import ocr_service
from calculos_service import calculos_service
from layout_service import layout_service
from plataformas_config import consejero_plataformas
from zip_handler import zip_handler
from gmail_service import gmail_service
from cuenta_deposito_service import cuenta_deposito_service


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'netcash_mbco')]

# Create the main app
app = FastAPI(title="Asistente NetCash MBco API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================
# FUNCIONES AUXILIARES
# ============================================

async def procesar_zip_comprobantes(operacion_id: str, zip_path: Path, operacion: dict, zip_hash: str = None) -> dict:
    """
    Procesa un archivo ZIP que contiene múltiples comprobantes.
    """
    try:
        # Extraer archivos del ZIP
        extract_dir = Path("/app/backend/uploads/comprobantes") / f"extracted_{operacion_id}"
        resultado_extraccion = zip_handler.extraer_comprobantes_de_zip(zip_path, extract_dir)
        
        archivos_validos = resultado_extraccion["archivos_validos"]
        archivos_ignorados = resultado_extraccion["archivos_ignorados"]
        errores = resultado_extraccion["errores"]
        
        if not archivos_validos:
            return {
                "success": False,
                "message": "El ZIP no contiene archivos de comprobantes válidos (PDF, JPG, PNG)",
                "archivos_ignorados": archivos_ignorados,
                "errores": errores
            }
        
        # Procesar cada archivo válido
        comprobantes_procesados = []
        comprobantes_con_error = []
        
        for archivo_info in archivos_validos:
            try:
                # Calcular hash del archivo extraído
                file_hash = calcular_hash_archivo(Path(archivo_info["path"]))
                
                # Verificar duplicado
                resultado_duplicado = await verificar_duplicado_por_hash(file_hash)
                if resultado_duplicado["es_duplicado"]:
                    logger.warning(f"Archivo {archivo_info['nombre']} del ZIP es duplicado")
                    comprobantes_con_error.append(f"{archivo_info['nombre']} (duplicado en {resultado_duplicado['folio_mbco']})")
                    continue
                
                # Procesar con OCR
                datos_ocr = await ocr_service.leer_comprobante(
                    archivo_info["path"],
                    archivo_info["mime_type"]
                )
                
                # Construir file_url relativa
                file_url = f"/uploads/comprobantes/extracted_{operacion_id}/{archivo_info['nombre']}"
                
                # Validar
                es_valido = False
                mensaje_validacion = ""
                
                if "error" in datos_ocr:
                    mensaje_validacion = datos_ocr["error"]
                else:
                    # Validar cuenta y beneficiario
                    cuenta_valida = ocr_service.validar_cuenta_beneficiaria(
                        datos_ocr.get("cuenta_beneficiaria", ""),
                        CUENTA_DEPOSITO_CLIENTE["clabe"]
                    )
                    nombre_valido = ocr_service.validar_nombre_beneficiario(
                        datos_ocr.get("nombre_beneficiario", ""),
                        CUENTA_DEPOSITO_CLIENTE["razon_social"]
                    )
                    
                    if cuenta_valida and nombre_valido:
                        es_valido = True
                        mensaje_validacion = "Comprobante válido"
                    else:
                        mensaje_validacion = "La cuenta o el beneficiario no coinciden"
                
                # Crear comprobante con hash
                comprobante_dict = {
                    **datos_ocr,
                    "archivo_original": archivo_info["nombre"],
                    "nombre_archivo": archivo_info["nombre"],
                    "file_url": file_url,
                    "file_path": archivo_info["path"],
                    "file_hash": file_hash,
                    "es_valido": es_valido,
                    "es_duplicado": False,
                    "mensaje_validacion": mensaje_validacion
                }
                
                comprobantes_procesados.append(comprobante_dict)
                
            except Exception as e:
                logger.error(f"Error procesando {archivo_info['nombre']}: {str(e)}")
                comprobantes_con_error.append(archivo_info["nombre"])
        
        # Actualizar operación con todos los comprobantes
        if comprobantes_procesados:
            comprobantes_existentes = operacion.get("comprobantes", [])
            comprobantes_existentes.extend(comprobantes_procesados)
            
            comprobantes_validos = [c for c in comprobantes_procesados if c.get("es_valido")]
            nuevo_estado = EstadoOperacion.ESPERANDO_DATOS_TITULAR if comprobantes_validos else EstadoOperacion.ESPERANDO_COMPROBANTES
            
            await db.operaciones.update_one(
                {"id": operacion_id},
                {
                    "$set": {
                        "comprobantes": comprobantes_existentes,
                        "estado": nuevo_estado
                    }
                }
            )
        
        # Construir mensaje de respuesta
        mensaje = f"Procesé {len(comprobantes_procesados)} comprobantes del ZIP."
        if archivos_ignorados:
            mensaje += f" {len(archivos_ignorados)} archivo(s) ignorado(s) (formato no soportado)."
        if comprobantes_con_error:
            mensaje += f" {len(comprobantes_con_error)} archivo(s) con error de procesamiento."
        
        logger.info(f"ZIP procesado: {len(comprobantes_procesados)} comprobantes extraídos")
        
        return {
            "success": True,
            "message": mensaje,
            "comprobantes_procesados": len(comprobantes_procesados),
            "comprobantes_validos": len([c for c in comprobantes_procesados if c.get("es_valido")]),
            "archivos_ignorados": archivos_ignorados,
            "comprobantes_con_error": comprobantes_con_error,
            "comprobantes": comprobantes_procesados
        }
        
    except Exception as e:
        logger.error(f"Error procesando ZIP: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error procesando ZIP: {str(e)}")


def calcular_hash_archivo(file_path: Path) -> str:
    """Calcula hash SHA-256 de un archivo para detectar duplicados"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Leer archivo en chunks para no saturar memoria
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


async def verificar_duplicado_por_hash(file_hash: str) -> dict:
    """
    Verifica si un comprobante con el mismo hash ya existe.
    Returns: dict con 'es_duplicado', 'operacion_id', 'folio_mbco', 'estado'
    """
    # Buscar en todas las operaciones si existe un comprobante con este hash
    operacion_existente = await db.operaciones.find_one(
        {"comprobantes.file_hash": file_hash},
        {"_id": 0, "id": 1, "folio_mbco": 1, "cliente_nombre": 1, "estado": 1}
    )
    
    if operacion_existente:
        return {
            "es_duplicado": True,
            "operacion_id": operacion_existente.get("id"),
            "folio_mbco": operacion_existente.get("folio_mbco", "N/A"),
            "cliente_nombre": operacion_existente.get("cliente_nombre", "N/A"),
            "estado": operacion_existente.get("estado", "DESCONOCIDO")
        }
    
    return {"es_duplicado": False}


async def generar_folio_mbco() -> str:
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


# ============================================
# RUTAS DE OPERACIONES NETCASH
# ============================================

@api_router.get("/")
async def root():
    return {
        "message": "Asistente NetCash MBco API",
        "version": "1.0.0 - Fase 1",
        "modo_mantenimiento": MODO_MANTENIMIENTO
    }


@api_router.get("/operaciones")
async def obtener_operaciones():
    """
    Obtiene todas las operaciones NetCash UNIFICADAS.
    Combina operaciones manuales (web) y solicitudes de Telegram.
    Retorna lista de diccionarios sin validación estricta de modelo.
    """
    operaciones_unificadas = []
    
    # 1. Obtener operaciones manuales (web)
    operaciones_web = await db.operaciones.find({}, {"_id": 0}).to_list(1000)
    
    for op in operaciones_web:
        # Convertir timestamps ISO a datetime
        if isinstance(op.get('fecha_creacion'), str):
            op['fecha_creacion'] = datetime.fromisoformat(op['fecha_creacion'])
        for field in ['timestamp_confirmacion_cliente', 'timestamp_codigo_sistema', 
                      'timestamp_pago_proveedor', 'timestamp_ligas_recibidas', 
                      'timestamp_entrega_cliente']:
            if op.get(field) and isinstance(op[field], str):
                op[field] = datetime.fromisoformat(op[field])
        
        # Marcar origen
        op['origen'] = op.get('origen', 'web')
        operaciones_unificadas.append(op)
    
    # 2. Obtener solicitudes de Telegram
    solicitudes_telegram = await db.solicitudes_netcash.find({}, {"_id": 0}).to_list(1000)
    
    for sol in solicitudes_telegram:
        # Normalizar comprobantes: mapear campos para compatibilidad con frontend
        comprobantes_normalizados = []
        for comp in sol.get("comprobantes", []):
            comp_normalizado = dict(comp)
            # Mapear monto_detectado a monto para que el frontend lo encuentre
            if "monto_detectado" in comp_normalizado and "monto" not in comp_normalizado:
                comp_normalizado["monto"] = comp_normalizado.get("monto_detectado", 0)
            # Normalizar archivo_url/file_url para que sea accesible desde el frontend
            archivo_path = comp_normalizado.get("archivo_url") or comp_normalizado.get("file_url")
            if archivo_path:
                # Convertir ruta absoluta del servidor a URL relativa accesible
                if archivo_path.startswith("/app/backend/uploads/"):
                    archivo_path = archivo_path.replace("/app/backend/uploads/", "/api/uploads/")
                elif archivo_path.startswith("/uploads/"):
                    archivo_path = "/api" + archivo_path
                comp_normalizado["file_url"] = archivo_path
                comp_normalizado["archivo_url"] = archivo_path
            comprobantes_normalizados.append(comp_normalizado)
        
        # Mapear campos de solicitud a estructura de operación
        operacion_normalizada = {
            "id": sol.get("id"),
            "folio_mbco": sol.get("folio_mbco"),
            "cliente_id": sol.get("cliente_id"),
            "cliente_nombre": sol.get("cliente_nombre"),
            "titular_nombre_completo": sol.get("beneficiario_reportado"),
            "titular_idmex": sol.get("idmex_reportado"),
            "numero_ligas": sol.get("cantidad_ligas_reportada", 0),
            "comprobantes": comprobantes_normalizados,
            "estado": _mapear_estado_solicitud(sol.get("estado", "borrador")),
            "fecha_creacion": sol.get("created_at"),
            "monto_depositado_cliente": sol.get("monto_depositado_cliente", 0),
            "monto_total_comprobantes": sol.get("monto_depositado_cliente", 0),
            "comision_cobrada": sol.get("comision_cliente", 0) or sol.get("comision_cobrada", 0),
            "porcentaje_comision_usado": sol.get("comision_cliente_porcentaje", 1.0) or sol.get("porcentaje_comision_usado", 1.0),
            "origen": "telegram",
            "modo_captura": sol.get("modo_captura", "ocr_ok"),
            # Campos adicionales de Telegram
            "telegram_id": sol.get("telegram_id"),
            "idmex_beneficiario_declarado": sol.get("idmex_beneficiario_declarado"),
            # Campos de cálculos para compatibilidad con frontend
            "capital_netcash": sol.get("capital_netcash"),
            "costo_proveedor_monto": sol.get("costo_proveedor_monto"),
            "costo_proveedor_pct": sol.get("costo_proveedor_pct"),
            "total_egreso": sol.get("total_egreso"),
            "calculos": sol.get("calculos"),
        }
        
        # Calcular monto si hay comprobantes válidos
        if not operacion_normalizada["monto_depositado_cliente"]:
            monto_total = sum(
                c.get("monto", 0) or c.get("monto_detectado", 0)
                for c in comprobantes_normalizados 
                if c.get("es_valido") and not c.get("es_duplicado")
            )
            operacion_normalizada["monto_depositado_cliente"] = monto_total
            operacion_normalizada["monto_total_comprobantes"] = monto_total
        
        operaciones_unificadas.append(operacion_normalizada)
    
    # Función auxiliar para normalizar fechas para ordenamiento
    def get_fecha_para_sort(x):
        fecha = x.get('fecha_creacion')
        if fecha is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if isinstance(fecha, str):
            try:
                fecha = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
            except:
                return datetime.min.replace(tzinfo=timezone.utc)
        # Si no tiene timezone, agregar UTC
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return fecha
    
    # Ordenar por fecha de creación (más recientes primero)
    operaciones_unificadas.sort(key=get_fecha_para_sort, reverse=True)
    
    return operaciones_unificadas


def _mapear_estado_solicitud(estado_telegram: str) -> str:
    """Mapea estados de solicitud Telegram a estados de operación web"""
    mapeo = {
        "borrador": "ESPERANDO_COMPROBANTES",
        "pendiente_comprobantes": "ESPERANDO_COMPROBANTES",
        "pendiente_datos": "ESPERANDO_DATOS_TITULAR",
        "pendiente_confirmacion": "ESPERANDO_CONFIRMACION_CLIENTE",
        "pendiente_validacion_admin": "VALIDANDO_COMPROBANTES",
        "lista_para_mbco": "ESPERANDO_CODIGO_SISTEMA",
        "enviada_tesoreria": "ESPERANDO_TESORERIA",
        "completada": "COMPLETADO",
        "rechazada": "CANCELADA_POR_INACTIVIDAD",
        "cancelada": "CANCELADA_POR_INACTIVIDAD",
        # Estados adicionales del bot de Telegram
        "esperando_validacion_ana": "VALIDANDO_COMPROBANTES",
        "ESPERANDO_VALIDACION_ANA": "VALIDANDO_COMPROBANTES",
        "lista_para_confirmacion": "ESPERANDO_CONFIRMACION_CLIENTE",
        "LISTA_PARA_CONFIRMACION": "ESPERANDO_CONFIRMACION_CLIENTE",
        "lista_para_mbc": "DATOS_COMPLETOS",
        "LISTA_PARA_MBC": "DATOS_COMPLETOS",
        "enviado_a_tesoreria": "ESPERANDO_TESORERIA",
        "ENVIADO_A_TESORERIA": "ESPERANDO_TESORERIA",
        "orden_interna_generada": "ESPERANDO_CODIGO_SISTEMA",
        "ORDEN_INTERNA_GENERADA": "ESPERANDO_CODIGO_SISTEMA",
        "dispersada_proveedor": "COMPLETADO",
        "DISPERSADA_PROVEEDOR": "COMPLETADO",
    }
    return mapeo.get(estado_telegram, "ESPERANDO_COMPROBANTES")


@api_router.get("/operaciones/{operacion_id}")
async def obtener_operacion(operacion_id: str):
    """
    Obtiene una operación específica por ID.
    Busca en ambas colecciones (web y Telegram) para vista unificada.
    """
    # Primero buscar en operaciones web
    operacion = await db.operaciones.find_one({"id": operacion_id}, {"_id": 0})
    origen = "web"
    
    if not operacion:
        # Buscar en solicitudes Telegram
        operacion = await db.solicitudes_netcash.find_one({"id": operacion_id}, {"_id": 0})
        origen = "telegram"
        
        if operacion:
            # Normalizar comprobantes: mapear campos para compatibilidad con frontend
            comprobantes_normalizados = []
            for comp in operacion.get("comprobantes", []):
                comp_normalizado = dict(comp)
                # Mapear monto_detectado a monto para que el frontend lo encuentre
                if "monto_detectado" in comp_normalizado and "monto" not in comp_normalizado:
                    comp_normalizado["monto"] = comp_normalizado.get("monto_detectado", 0)
                # Normalizar archivo_url/file_url para que sea accesible desde el frontend
                archivo_path = comp_normalizado.get("archivo_url") or comp_normalizado.get("file_url")
                if archivo_path:
                    # Convertir ruta absoluta del servidor a URL relativa accesible
                    if archivo_path.startswith("/app/backend/uploads/"):
                        archivo_path = archivo_path.replace("/app/backend/uploads/", "/api/uploads/")
                    elif archivo_path.startswith("/uploads/"):
                        archivo_path = "/api" + archivo_path
                    comp_normalizado["file_url"] = archivo_path
                    comp_normalizado["archivo_url"] = archivo_path
                comprobantes_normalizados.append(comp_normalizado)
            
            # Obtener datos completos del cliente desde el catálogo
            cliente_id = operacion.get("cliente_id")
            cliente_data = await db.clientes.find_one({"id": cliente_id}, {"_id": 0}) if cliente_id else None
            
            # Normalizar campos de Telegram a estructura web
            operacion = {
                "id": operacion.get("id"),
                "folio_mbco": operacion.get("folio_mbco"),
                "cliente_id": operacion.get("cliente_id"),
                "cliente_nombre": operacion.get("cliente_nombre"),
                # Datos del cliente desde catálogo
                "propietario": cliente_data.get("propietario") if cliente_data else None,
                "cliente_email": cliente_data.get("email") if cliente_data else None,
                "cliente_telegram_id": cliente_data.get("telegram_id") if cliente_data else None,
                "cliente_telefono_completo": cliente_data.get("telefono_completo") if cliente_data else None,
                "porcentaje_comision_cliente": cliente_data.get("porcentaje_comision_cliente", 1.0) if cliente_data else 1.0,
                # Datos del titular/beneficiario
                "titular_nombre_completo": operacion.get("beneficiario_reportado"),
                "titular_idmex": operacion.get("idmex_reportado") or operacion.get("idmex_beneficiario_declarado"),
                "numero_ligas": operacion.get("cantidad_ligas_reportada", 0),
                "comprobantes": comprobantes_normalizados,
                "estado": _mapear_estado_solicitud(operacion.get("estado", "borrador")),
                "fecha_creacion": operacion.get("created_at"),
                "monto_depositado_cliente": operacion.get("monto_depositado_cliente", 0),
                "monto_total_comprobantes": operacion.get("monto_depositado_cliente", 0),
                "comision_cobrada": operacion.get("comision_cliente", 0),
                "porcentaje_comision_usado": operacion.get("comision_cliente_porcentaje", 1.0),
                "origen": "telegram",
                "origen_operacion": "telegram",
                "modo_captura": operacion.get("modo_captura", "ocr_ok"),
                "telegram_id": operacion.get("telegram_id"),
                "idmex_beneficiario_declarado": operacion.get("idmex_beneficiario_declarado"),
                # Datos de captura manual (cuando OCR falla)
                "captura_manual": {
                    "origen_montos": operacion.get("origen_montos"),
                    "num_comprobantes_declarado": operacion.get("num_comprobantes_declarado"),
                    "monto_total_declarado": operacion.get("monto_total_declarado"),
                    "beneficiario_declarado": operacion.get("beneficiario_declarado"),
                } if operacion.get("modo_captura") == "manual_por_fallo_ocr" else None,
                # Campos de cálculos (si ya se calcularon)
                "capital_netcash": operacion.get("capital_netcash"),
                "costo_proveedor_monto": operacion.get("costo_proveedor_monto"),
                "costo_proveedor_pct": operacion.get("costo_proveedor_pct"),
                "total_egreso": operacion.get("total_egreso"),
                "calculos": operacion.get("calculos")
            }
            
            # Calcular monto de comprobantes
            if not operacion["monto_depositado_cliente"]:
                monto_total = sum(
                    c.get("monto", 0) or c.get("monto_detectado", 0)
                    for c in comprobantes_normalizados 
                    if c.get("es_valido") and not c.get("es_duplicado")
                )
                operacion["monto_depositado_cliente"] = monto_total
                operacion["monto_total_comprobantes"] = monto_total
    
    if not operacion:
        raise HTTPException(status_code=404, detail="Operación no encontrada")
    
    # Marcar origen
    operacion["origen"] = origen
    
    # Convertir timestamps
    if isinstance(operacion.get('fecha_creacion'), str):
        try:
            operacion['fecha_creacion'] = datetime.fromisoformat(operacion['fecha_creacion'].replace('Z', '+00:00'))
        except:
            pass
    
    return operacion


@api_router.post("/operaciones", response_model=OperacionNetCash)
async def crear_operacion(operacion_input: OperacionNetCashCreate):
    """
    Crea una nueva operación NetCash vinculada a un cliente.
    """
    # Buscar el cliente
    cliente = await db.clientes.find_one({"id": operacion_input.id_cliente}, {"_id": 0})
    
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Crear operación con datos del cliente
    operacion_dict = operacion_input.model_dump()
    
    # Copiar datos del cliente a la operación
    operacion_dict["cliente_nombre"] = cliente.get("nombre")
    operacion_dict["cliente_email"] = cliente.get("email")
    operacion_dict["cliente_telefono_completo"] = cliente.get("telefono_completo")
    operacion_dict["cliente_telegram_id"] = cliente.get("telegram_id")
    operacion_dict["propietario"] = cliente.get("propietario")
    
    # Si no se especificó comisión, usar la del cliente
    if operacion_dict.get("porcentaje_comision_usado") is None:
        operacion_dict["porcentaje_comision_usado"] = cliente.get("porcentaje_comision_cliente", 0.65)
    
    # Generar folio MBco
    folio = await generar_folio_mbco()
    operacion_dict["folio_mbco"] = folio
    
    operacion = OperacionNetCash(**operacion_dict)
    
    # Convertir a dict y serializar datetime
    doc = operacion.model_dump()
    doc['fecha_creacion'] = doc['fecha_creacion'].isoformat()
    
    # Inicializar timestamp de actividad para monitor de inactividad
    doc['timestamp_actualizacion'] = datetime.now(timezone.utc)
    doc['ultimo_mensaje_cliente'] = datetime.now(timezone.utc)
    
    await db.operaciones.insert_one(doc)
    
    logger.info(f"Operación creada: {operacion.id} (Folio: {folio}) para cliente {cliente.get('nombre')}")
    return operacion


@api_router.post("/operaciones/{operacion_id}/comprobante")
async def procesar_comprobante(
    operacion_id: str,
    file: UploadFile = File(...)
):
    """
    Procesa un comprobante de depósito para una operación.
    Soporta archivos individuales (PDF, JPG, PNG) y archivos ZIP con múltiples comprobantes.
    """
    try:
        # Verificar que la operación exista
        operacion = await db.operaciones.find_one({"id": operacion_id}, {"_id": 0})
        if not operacion:
            raise HTTPException(status_code=404, detail="Operación no encontrada")
        
        # Guardar archivo de forma permanente
        upload_dir = Path("/app/backend/uploads/comprobantes")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generar nombre único para el archivo
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{operacion_id}_{timestamp}_{file.filename}"
        file_path = upload_dir / safe_filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 🔐 CALCULAR HASH para detectar duplicados
        file_hash = calcular_hash_archivo(file_path)
        logger.info(f"Hash calculado para {file.filename}: {file_hash[:16]}...")
        
        # Verificar si es duplicado EXACTO (mismo archivo)
        resultado_duplicado = await verificar_duplicado_por_hash(file_hash)
        if resultado_duplicado["es_duplicado"]:
            logger.warning(f"Comprobante duplicado detectado (hash). Ya usado en {resultado_duplicado['folio_mbco']}")
            # Eliminar archivo duplicado
            file_path.unlink(missing_ok=True)
            return {
                "success": False,
                "es_duplicado": True,
                "mensaje": f"Este comprobante ya fue usado en la operación {resultado_duplicado['folio_mbco']} del cliente {resultado_duplicado['cliente_nombre']}. Por favor envía un comprobante distinto.",
                "operacion_duplicada": {
                    "folio_mbco": resultado_duplicado['folio_mbco'],
                    "estado": resultado_duplicado['estado'],
                    "cliente_nombre": resultado_duplicado['cliente_nombre']
                }
            }
        
        # Determinar tipo MIME
        mime_type = file.content_type or "application/octet-stream"
        
        # ⚡ SOPORTE ZIP: Detectar si es un archivo ZIP
        if mime_type == "application/zip" or file.filename.lower().endswith('.zip'):
            logger.info(f"Archivo ZIP detectado: {file.filename}")
            return await procesar_zip_comprobantes(operacion_id, file_path, operacion, file_hash)
        
        # Construir URL pública del archivo (relativa al backend)
        file_url = f"/uploads/comprobantes/{safe_filename}"
        
        # Procesar con OCR
        logger.info(f"Procesando comprobante para operación {operacion_id}")
        datos_ocr = await ocr_service.leer_comprobante(str(file_path), mime_type)
        
        # Validar cuenta beneficiaria y detectar duplicados
        es_valido = False
        es_duplicado = False
        mensaje_validacion = ""
        
        if "error" in datos_ocr:
            mensaje_validacion = datos_ocr["error"]
        else:
            # PASO 1: Verificar si es un comprobante duplicado por clave_rastreo
            clave_rastreo = datos_ocr.get("clave_rastreo")
            
            if clave_rastreo:
                # Buscar en todas las operaciones si ya existe esta clave_rastreo
                operacion_con_duplicado = await db.operaciones.find_one(
                    {"comprobantes.clave_rastreo": clave_rastreo},
                    {"_id": 0, "id": 1, "cliente_nombre": 1}
                )
                
                if operacion_con_duplicado:
                    es_duplicado = True
                    es_valido = False
                    mensaje_validacion = f"Este comprobante ya había sido registrado anteriormente en la operación {operacion_con_duplicado['id'][:8]}... No es necesario procesarlo de nuevo."
                    logger.warning(f"Comprobante duplicado detectado: clave_rastreo={clave_rastreo}")
            
            # PASO 2: Si NO es duplicado, validar contra CUENTA ACTIVA
            if not es_duplicado:
                # Obtener cuenta activa
                cuenta_activa = await cuenta_deposito_service.obtener_cuenta_activa()
                
                if not cuenta_activa:
                    es_valido = False
                    mensaje_validacion = "No hay cuenta de depósito activa configurada"
                    logger.error("[Comprobante] No hay cuenta activa configurada")
                else:
                    logger.info(f"[Comprobante] Validando contra cuenta activa: {cuenta_activa.get('banco')} - {cuenta_activa.get('clabe')}")
                    
                    # Validar usando el servicio de validación
                    from validador_comprobantes_service import validador_comprobantes
                    archivo_info = {
                        'ruta': str(file_path),
                        'mime_type': mime_type
                    }
                    
                    es_valido, razon_validacion = validador_comprobantes.validar_comprobante(
                        str(file_path),
                        mime_type,
                        cuenta_activa
                    )
                    
                    if es_valido:
                        mensaje_validacion = "Comprobante válido"
                        logger.info(f"[Comprobante] ✅ Válido: {razon_validacion}")
                    else:
                        mensaje_validacion = f"El comprobante no corresponde a la cuenta NetCash autorizada (Banco {cuenta_activa.get('banco')}, CLABE {cuenta_activa.get('clabe')}, Beneficiario {cuenta_activa.get('beneficiario')})"
                        logger.warning(f"[Comprobante] ❌ Inválido: {razon_validacion}")
        
        # Crear comprobante con file_url y hash
        comprobante_dict = {
            **datos_ocr,
            "archivo_original": file.filename,
            "nombre_archivo": file.filename,
            "file_url": file_url,
            "file_path": str(file_path),
            "file_hash": file_hash,
            "es_valido": es_valido,
            "es_duplicado": es_duplicado,
            "mensaje_validacion": mensaje_validacion
        }
        comprobante = ComprobanteDepositoOCR(**comprobante_dict)
        
        # Actualizar operación
        comprobantes = operacion.get("comprobantes", [])
        comprobantes.append(comprobante.model_dump())
        
        # Recalcular monto total de comprobantes válidos
        nuevo_monto_total = sum(
            c.get("monto", 0) or c.get("monto_detectado", 0)
            for c in comprobantes
            if c.get("es_valido") and not c.get("es_duplicado")
        )
        
        nuevo_estado = EstadoOperacion.ESPERANDO_DATOS_TITULAR if es_valido else EstadoOperacion.ESPERANDO_COMPROBANTES
        
        await db.operaciones.update_one(
            {"id": operacion_id},
            {
                "$set": {
                    "comprobantes": comprobantes,
                    "estado": nuevo_estado,
                    "monto_depositado_cliente": nuevo_monto_total,
                    "monto_total_comprobantes": nuevo_monto_total,
                    "num_comprobantes_validos": len([c for c in comprobantes if c.get("es_valido")])
                }
            }
        )
        
        logger.info(f"Comprobante procesado para operación {operacion_id}: {mensaje_validacion}. Monto total: {nuevo_monto_total}")
        
        return {
            "success": True,
            "comprobante": comprobante.model_dump(),
            "operacion_id": operacion_id
        }
        
    except Exception as e:
        logger.error(f"Error procesando comprobante: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error procesando comprobante: {str(e)}")


@api_router.post("/operaciones/{operacion_id}/titular")
async def agregar_datos_titular(
    operacion_id: str,
    titular_nombre_completo: str = Form(...),
    titular_idmex: str = Form(...),
    numero_ligas: int = Form(...)
):
    """
    Agrega datos del titular de las ligas.
    """
    try:
        # Validar que el nombre tenga al menos 3 palabras
        palabras = titular_nombre_completo.strip().split()
        if len(palabras) < 3:
            raise HTTPException(
                status_code=400,
                detail="El nombre debe incluir al menos nombre y dos apellidos (mínimo 3 palabras)"
            )
        
        # Actualizar operación
        result = await db.operaciones.update_one(
            {"id": operacion_id},
            {
                "$set": {
                    "titular_nombre_completo": titular_nombre_completo.upper(),
                    "titular_idmex": titular_idmex,
                    "numero_ligas": numero_ligas,
                    "estado": EstadoOperacion.ESPERANDO_CONFIRMACION_CLIENTE
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Operación no encontrada")
        
        logger.info(f"Datos de titular agregados para operación {operacion_id}")
        
        return {
            "success": True,
            "operacion_id": operacion_id,
            "mensaje": "Datos del titular guardados correctamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error agregando datos de titular: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/operaciones/{operacion_id}")
async def eliminar_operacion(operacion_id: str):
    """
    Elimina una operación de la base de datos.
    Funciona tanto para operaciones web como de Telegram.
    """
    try:
        # Primero intentar eliminar de operaciones (web)
        result_web = await db.operaciones.delete_one({"id": operacion_id})
        
        if result_web.deleted_count > 0:
            logger.info(f"Operación web eliminada: {operacion_id}")
            return {"success": True, "message": "Operación eliminada correctamente", "origen": "web"}
        
        # Si no estaba en operaciones, buscar en solicitudes_netcash (Telegram)
        result_telegram = await db.solicitudes_netcash.delete_one({"id": operacion_id})
        
        if result_telegram.deleted_count > 0:
            logger.info(f"Solicitud Telegram eliminada: {operacion_id}")
            return {"success": True, "message": "Solicitud eliminada correctamente", "origen": "telegram"}
        
        raise HTTPException(status_code=404, detail="Operación no encontrada")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando operación: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/operaciones/{operacion_id}/comprobantes/{comprobante_idx}")
async def eliminar_comprobante(operacion_id: str, comprobante_idx: int):
    """
    Elimina un comprobante específico de una operación.
    """
    try:
        # Primero buscar en operaciones web
        operacion = await db.operaciones.find_one({"id": operacion_id}, {"_id": 0})
        collection = db.operaciones
        
        if not operacion:
            # Buscar en solicitudes Telegram
            operacion = await db.solicitudes_netcash.find_one({"id": operacion_id}, {"_id": 0})
            collection = db.solicitudes_netcash
        
        if not operacion:
            raise HTTPException(status_code=404, detail="Operación no encontrada")
        
        comprobantes = operacion.get("comprobantes", [])
        
        if comprobante_idx < 0 or comprobante_idx >= len(comprobantes):
            raise HTTPException(status_code=400, detail="Índice de comprobante inválido")
        
        # Eliminar el comprobante del array
        comprobantes.pop(comprobante_idx)
        
        # Recalcular monto total de comprobantes válidos
        nuevo_monto_total = sum(
            c.get("monto", 0) or c.get("monto_detectado", 0)
            for c in comprobantes
            if c.get("es_valido") and not c.get("es_duplicado")
        )
        
        # Actualizar en la base de datos con el nuevo monto
        update_data = {
            "comprobantes": comprobantes,
            "monto_depositado_cliente": nuevo_monto_total,
            "monto_total_comprobantes": nuevo_monto_total,
            "total_comprobantes_validos": nuevo_monto_total,
            "num_comprobantes_validos": len([c for c in comprobantes if c.get("es_valido")]),
            # Limpiar cálculos previos ya que el monto cambió
            "calculos": None,
            "capital_netcash": None,
            "costo_proveedor_monto": None,
            "total_egreso": None
        }
        
        await collection.update_one(
            {"id": operacion_id},
            {"$set": update_data}
        )
        
        logger.info(f"Comprobante {comprobante_idx} eliminado de operación {operacion_id}. Nuevo monto total: {nuevo_monto_total}")
        
        return {
            "success": True,
            "message": "Comprobante eliminado correctamente",
            "comprobantes_restantes": len(comprobantes),
            "nuevo_monto_total": nuevo_monto_total
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando comprobante: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@api_router.post("/operaciones/{operacion_id}/comprobantes/{comprobante_idx}/reocr")
async def reintentar_ocr_comprobante(operacion_id: str, comprobante_idx: int):
    """
    Re-intenta el procesamiento OCR de un comprobante específico.
    """
    try:
        # Buscar en operaciones web
        operacion = await db.operaciones.find_one({"id": operacion_id}, {"_id": 0})
        collection = "operaciones"
        
        if not operacion:
            # Buscar en solicitudes Telegram
            operacion = await db.solicitudes_netcash.find_one({"id": operacion_id}, {"_id": 0})
            collection = "solicitudes_netcash"
        
        if not operacion:
            raise HTTPException(status_code=404, detail="Operación no encontrada")
        
        comprobantes = operacion.get("comprobantes", [])
        if comprobante_idx < 0 or comprobante_idx >= len(comprobantes):
            raise HTTPException(status_code=404, detail="Comprobante no encontrado")
        
        comprobante = comprobantes[comprobante_idx]
        file_url = comprobante.get("file_url") or comprobante.get("archivo_url") or comprobante.get("archivo")
        
        if not file_url:
            raise HTTPException(status_code=400, detail="El comprobante no tiene archivo asociado")
        
        # Construir ruta del archivo (puede ser ruta absoluta o relativa)
        if file_url.startswith("/app/backend"):
            file_path = Path(file_url)
        elif file_url.startswith("/"):
            file_path = Path(f"/app/backend{file_url}")
        else:
            file_path = Path(f"/app/backend/uploads/{file_url}")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {file_url}")
        
        # Re-procesar con OCR (usando el servicio unificado)
        from ocr_service import ocr_service
        
        # Determinar MIME type
        mime_type = "application/pdf" if str(file_path).lower().endswith(".pdf") else "image/jpeg"
        if str(file_path).lower().endswith(".png"):
            mime_type = "image/png"
        
        resultado_ocr = await ocr_service.leer_comprobante(str(file_path), mime_type)
        
        # Verificar si hubo error
        if resultado_ocr.get("error"):
            return {
                "success": False,
                "mensaje": f"Error en OCR: {resultado_ocr.get('error')}",
                "monto_detectado": 0,
                "es_valido": False
            }
        
        # Obtener nuevo monto y validar que sea un valor numérico válido
        nuevo_monto_raw = resultado_ocr.get("monto", 0)
        
        # Manejar caso donde OCR devuelve múltiples valores o formato inválido
        if isinstance(nuevo_monto_raw, list):
            # Si es una lista, tomar el primer valor numérico o marcar como inválido
            nuevo_monto = nuevo_monto_raw[0] if nuevo_monto_raw and isinstance(nuevo_monto_raw[0], (int, float)) else 0
            logger.warning(f"[Re-OCR] Monto detectado como lista, usando primer valor: {nuevo_monto}")
        elif isinstance(nuevo_monto_raw, str):
            # Intentar parsear string a número
            try:
                nuevo_monto = float(nuevo_monto_raw.replace(",", "").replace("$", "").strip())
            except ValueError:
                nuevo_monto = 0
                logger.warning(f"[Re-OCR] No se pudo parsear monto string: {nuevo_monto_raw}")
        else:
            nuevo_monto = nuevo_monto_raw if isinstance(nuevo_monto_raw, (int, float)) else 0
        
        es_valido = nuevo_monto is not None and isinstance(nuevo_monto, (int, float)) and nuevo_monto > 0
        mensaje_validacion = ""
        
        # Validar contra cuenta bancaria autorizada (igual que en comprobante nuevo)
        if es_valido:
            cuenta_activa = await cuenta_deposito_service.obtener_cuenta_activa()
            
            if cuenta_activa:
                from validador_comprobantes_service import validador_comprobantes
                
                es_valido, mensaje_validacion = validador_comprobantes.validar_comprobante(
                    str(file_path), mime_type, cuenta_activa
                )
                
                if not es_valido:
                    logger.warning(f"[Re-OCR] Comprobante inválido: {mensaje_validacion}")
                else:
                    mensaje_validacion = "Comprobante válido"
                    logger.info(f"[Re-OCR] ✅ Comprobante válido")
            else:
                logger.warning("[Re-OCR] No hay cuenta activa configurada para validar")
        
        # Actualizar comprobante con nuevos datos
        comprobantes[comprobante_idx].update({
            "monto": nuevo_monto,
            "monto_detectado": nuevo_monto,
            "banco_origen": resultado_ocr.get("banco_emisor", ""),
            "clave_rastreo": resultado_ocr.get("clave_rastreo", ""),
            "cuenta_origen": resultado_ocr.get("cuenta_beneficiaria", ""),
            "nombre_beneficiario": resultado_ocr.get("nombre_beneficiario", ""),
            "fecha_operacion": resultado_ocr.get("fecha"),
            "referencia": resultado_ocr.get("referencia"),
            "es_valido": es_valido,
            "mensaje_validacion": mensaje_validacion,
            "ocr_data": {
                "datos_completos": resultado_ocr,
                "es_confiable": es_valido,
                "motivo_fallo": None if es_valido else (mensaje_validacion or "sin_monto")
            },
            "reprocessed_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Recalcular monto total de comprobantes válidos
        nuevo_monto_total = sum(
            c.get("monto", 0) or c.get("monto_detectado", 0)
            for c in comprobantes
            if c.get("es_valido") and not c.get("es_duplicado")
        )
        
        # Preparar datos de actualización
        update_data = {
            "comprobantes": comprobantes,
            "monto_depositado_cliente": nuevo_monto_total,
            "monto_total_comprobantes": nuevo_monto_total,
            "total_comprobantes_validos": nuevo_monto_total,
            "num_comprobantes_validos": len([c for c in comprobantes if c.get("es_valido")]),
            # Limpiar cálculos previos ya que el monto cambió
            "calculos": None,
            "capital_netcash": None,
            "costo_proveedor_monto": None,
            "total_egreso": None
        }
        
        # Guardar en BD
        db_collection = db.operaciones if collection == "operaciones" else db.solicitudes_netcash
        await db_collection.update_one(
            {"id": operacion_id},
            {"$set": update_data}
        )
        
        logger.info(f"Re-OCR completado para comprobante {comprobante_idx} de operación {operacion_id}. Monto total: {nuevo_monto_total}")
        
        return {
            "success": es_valido,
            "mensaje": f"Monto detectado: ${nuevo_monto:,.2f}" if es_valido else (mensaje_validacion or "OCR no pudo extraer datos válidos"),
            "monto_detectado": nuevo_monto,
            "es_valido": es_valido,
            "nuevo_monto_total": nuevo_monto_total
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en re-OCR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.patch("/operaciones/{operacion_id}/comprobantes/{comprobante_idx}")
async def actualizar_comprobante_manual(
    operacion_id: str,
    comprobante_idx: int,
    monto: Optional[float] = None,
    banco_origen: Optional[str] = None,
    clave_rastreo: Optional[str] = None,
    cuenta_origen: Optional[str] = None
):
    """
    Actualiza manualmente los datos de un comprobante específico.
    """
    try:
        # Buscar en operaciones web
        operacion = await db.operaciones.find_one({"id": operacion_id}, {"_id": 0})
        collection = "operaciones"
        
        if not operacion:
            # Buscar en solicitudes Telegram
            operacion = await db.solicitudes_netcash.find_one({"id": operacion_id}, {"_id": 0})
            collection = "solicitudes_netcash"
        
        if not operacion:
            raise HTTPException(status_code=404, detail="Operación no encontrada")
        
        comprobantes = operacion.get("comprobantes", [])
        if comprobante_idx < 0 or comprobante_idx >= len(comprobantes):
            raise HTTPException(status_code=404, detail="Comprobante no encontrado")
        
        # Actualizar campos proporcionados
        update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
        
        if monto is not None:
            comprobantes[comprobante_idx]["monto"] = monto
            comprobantes[comprobante_idx]["monto_detectado"] = monto
            comprobantes[comprobante_idx]["es_valido"] = monto > 0
        
        if banco_origen is not None:
            comprobantes[comprobante_idx]["banco_origen"] = banco_origen
        
        if clave_rastreo is not None:
            comprobantes[comprobante_idx]["clave_rastreo"] = clave_rastreo
        
        if cuenta_origen is not None:
            comprobantes[comprobante_idx]["cuenta_origen"] = cuenta_origen
        
        comprobantes[comprobante_idx]["editado_manualmente"] = True
        comprobantes[comprobante_idx]["editado_at"] = datetime.now(timezone.utc).isoformat()
        
        # Recalcular monto total de comprobantes válidos
        nuevo_monto_total = sum(
            c.get("monto", 0) or c.get("monto_detectado", 0)
            for c in comprobantes
            if c.get("es_valido") and not c.get("es_duplicado")
        )
        
        # Preparar datos de actualización
        update_data = {
            "comprobantes": comprobantes,
            "monto_depositado_cliente": nuevo_monto_total,
            "monto_total_comprobantes": nuevo_monto_total,
            "total_comprobantes_validos": nuevo_monto_total,
            "num_comprobantes_validos": len([c for c in comprobantes if c.get("es_valido")]),
            # Limpiar cálculos previos ya que el monto cambió
            "calculos": None,
            "capital_netcash": None,
            "costo_proveedor_monto": None,
            "total_egreso": None
        }
        
        # Guardar en BD
        db_collection = db.operaciones if collection == "operaciones" else db.solicitudes_netcash
        await db_collection.update_one(
            {"id": operacion_id},
            {"$set": update_data}
        )
        
        logger.info(f"Comprobante {comprobante_idx} actualizado manualmente para operación {operacion_id}. Monto total: {nuevo_monto_total}")
        
        return {
            "success": True,
            "message": "Comprobante actualizado correctamente",
            "nuevo_monto_total": nuevo_monto_total
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando comprobante: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))




@api_router.patch("/operaciones/{operacion_id}/datos-manuales")
async def actualizar_datos_manuales(
    operacion_id: str,
    monto_total: Optional[float] = None,
    num_comprobantes: Optional[int] = None,
    beneficiario: Optional[str] = None
):
    """
    Actualiza los datos capturados manualmente de una operación de Telegram.
    Solo aplica para operaciones con modo_captura = 'manual_por_fallo_ocr'
    """
    try:
        # Solo buscar en solicitudes Telegram
        operacion = await db.solicitudes_netcash.find_one({"id": operacion_id}, {"_id": 0})
        
        if not operacion:
            raise HTTPException(status_code=404, detail="Operación no encontrada")
        
        if operacion.get("modo_captura") != "manual_por_fallo_ocr":
            raise HTTPException(status_code=400, detail="Esta operación no tiene captura manual")
        
        # Construir update
        update_data = {"updated_at": datetime.now(timezone.utc)}
        
        if monto_total is not None:
            update_data["monto_total_declarado"] = monto_total
            update_data["monto_depositado_cliente"] = monto_total
        
        if num_comprobantes is not None:
            update_data["num_comprobantes_declarado"] = num_comprobantes
        
        if beneficiario is not None:
            update_data["beneficiario_declarado"] = beneficiario
            update_data["beneficiario_reportado"] = beneficiario
        
        # Actualizar
        await db.solicitudes_netcash.update_one(
            {"id": operacion_id},
            {"$set": update_data}
        )
        
        logger.info(f"Datos manuales actualizados para operación {operacion_id}")
        
        return {
            "success": True,
            "message": "Datos actualizados correctamente",
            "campos_actualizados": list(update_data.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando datos manuales: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@api_router.post("/operaciones/{operacion_id}/calcular")
async def calcular_operacion(
    operacion_id: str,
    comision_cliente_porcentaje: Optional[float] = None
):
    """
    Calcula los montos de una operación NetCash.
    Busca en operaciones web y solicitudes Telegram.
    """
    try:
        # Obtener operación (buscar en ambas colecciones)
        collection = "operaciones"
        operacion = await db.operaciones.find_one({"id": operacion_id}, {"_id": 0})
        
        if not operacion:
            # Buscar en solicitudes Telegram
            operacion = await db.solicitudes_netcash.find_one({"id": operacion_id}, {"_id": 0})
            collection = "solicitudes_netcash"
        
        if not operacion:
            raise HTTPException(status_code=404, detail="Operación no encontrada")
        
        # Verificar que haya comprobantes válidos
        comprobantes = operacion.get("comprobantes", [])
        comprobantes_validos = [c for c in comprobantes if c.get("es_valido", False)]
        
        if not comprobantes_validos:
            raise HTTPException(status_code=400, detail="No hay comprobantes válidos")
        
        # Sumar montos de comprobantes (usar monto o monto_detectado)
        monto_total = sum(
            c.get("monto") or c.get("monto_detectado") or 0 
            for c in comprobantes_validos
        )
        
        # Si aún es 0, usar monto_depositado_cliente de la operación (captura manual)
        if monto_total <= 0:
            monto_total = operacion.get("monto_depositado_cliente") or operacion.get("monto_total_declarado") or 0
        
        if monto_total <= 0:
            raise HTTPException(status_code=400, detail="El monto total debe ser mayor a 0. Verifica que los comprobantes tengan monto asignado.")
        
        # Usar comisión proporcionada o la que está guardada en la operación
        if comision_cliente_porcentaje is None:
            # Usar la comisión guardada en la operación
            comision_cliente_porcentaje = operacion.get("porcentaje_comision_usado", 0.65)
        
        # Convertir de porcentaje a decimal si es necesario
        # Si es > 1, asumir que está en porcentaje (ej: 0.65) y dividir entre 100
        if comision_cliente_porcentaje > 1:
            comision_cliente_porcentaje = comision_cliente_porcentaje / 100
        
        # Realizar cálculos (con las fórmulas correctas)
        calculos_dict = calculos_service.calcular_operacion(
            monto_depositado_cliente=monto_total,
            comision_cliente_porcentaje=comision_cliente_porcentaje
        )
        
        # Actualizar operación con los campos calculados (nombres alineados con CalculosNetCash)
        update_data = {
            "monto_depositado_cliente": calculos_dict["monto_depositado_cliente"],
            "porcentaje_comision_usado": calculos_dict["comision_cliente_porcentaje"],
            "comision_cobrada": calculos_dict["comision_cliente_cobrada"],
            "costo_proveedor_pct": calculos_dict["comision_proveedor_porcentaje"] / 100,
            "costo_proveedor_monto": calculos_dict["comision_proveedor"],
            "capital_netcash": calculos_dict["capital_netcash"],
            "total_egreso": calculos_dict["total_egreso"],
            "calculos": calculos_dict
        }
        
        # Guardar en la colección correcta y actualizar estado
        if collection == "operaciones":
            update_data["estado"] = "ESPERANDO_CONFIRMACION_CLIENTE"
            await db.operaciones.update_one({"id": operacion_id}, {"$set": update_data})
        else:
            # Para Telegram, también actualizar campos con nombres compatibles
            update_data["comision_cliente"] = calculos_dict["comision_cliente_cobrada"]
            update_data["comision_cliente_porcentaje"] = calculos_dict["comision_cliente_porcentaje"]
            update_data["estado"] = "lista_para_confirmacion"  # Estado Telegram equivalente
            await db.solicitudes_netcash.update_one({"id": operacion_id}, {"$set": update_data})
        
        logger.info(f"Cálculos realizados para operación {operacion_id}")
        
        return {
            "success": True,
            "operacion_id": operacion_id,
            "calculos": calculos_dict
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculando operación: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/operaciones/{operacion_id}/confirmar")
async def confirmar_operacion(operacion_id: str):
    """
    Confirma una operación y la pasa al estado DATOS_COMPLETOS.
    Después aparecerá en Pendientes MBControl para ingresar la clave.
    """
    try:
        result = await db.operaciones.update_one(
            {"id": operacion_id},
            {
                "$set": {
                    "estado": EstadoOperacion.DATOS_COMPLETOS,
                    "timestamp_confirmacion_cliente": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Operación no encontrada")
        
        logger.info(f"Operación {operacion_id} confirmada - Estado: DATOS_COMPLETOS")
        
        return {
            "success": True,
            "operacion_id": operacion_id,
            "mensaje": "Operación confirmada. Pasa a Pendientes MBControl para ingresar clave."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirmando operación: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# RUTAS DE CLIENTES
# ============================================

@api_router.get("/clientes")
async def obtener_clientes():
    """
    Obtiene todos los clientes.
    """
    clientes = await db.clientes.find({}, {"_id": 0}).to_list(1000)
    
    for cliente in clientes:
        if isinstance(cliente.get('fecha_alta'), str):
            cliente['fecha_alta'] = datetime.fromisoformat(cliente['fecha_alta']).isoformat()
        elif isinstance(cliente.get('fecha_alta'), datetime):
            cliente['fecha_alta'] = cliente['fecha_alta'].isoformat()
    
    return clientes


@api_router.post("/clientes", response_model=Cliente)
async def crear_cliente(cliente_input: ClienteCreate):
    """
    Crea un nuevo cliente.
    """
    cliente_dict = cliente_input.model_dump()
    cliente = Cliente(**cliente_dict)
    
    doc = cliente.model_dump()
    doc['fecha_alta'] = doc['fecha_alta'].isoformat()
    
    await db.clientes.insert_one(doc)
    
    logger.info(f"Cliente creado: {cliente.id} - {cliente.nombre}")
    return cliente


@api_router.put("/clientes/{cliente_id}", response_model=Cliente)
async def actualizar_cliente(cliente_id: str, cliente_input: dict):
    """
    Actualiza un cliente existente.
    """
    cliente_existente = await db.clientes.find_one({"id": cliente_id}, {"_id": 0})
    
    if not cliente_existente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Actualizar campos permitidos
    campos_actualizables = [
        "nombre", "email", "telefono", "rfc", "notas", 
        "porcentaje_comision_cliente", "propietario", "estado", "activo"
    ]
    
    update_data = {}
    for campo in campos_actualizables:
        if campo in cliente_input:
            update_data[campo] = cliente_input[campo]
    
    if update_data:
        await db.clientes.update_one(
            {"id": cliente_id},
            {"$set": update_data}
        )
    
    # Obtener cliente actualizado
    cliente_actualizado = await db.clientes.find_one({"id": cliente_id}, {"_id": 0})
    
    if isinstance(cliente_actualizado.get('fecha_alta'), str):
        cliente_actualizado['fecha_alta'] = datetime.fromisoformat(cliente_actualizado['fecha_alta'])
    
    logger.info(f"Cliente actualizado: {cliente_id} - {cliente_actualizado.get('nombre')}")
    return cliente_actualizado


@api_router.get("/clientes/buscar")
async def buscar_clientes(q: str = ""):
    """
    Busca clientes por nombre, email o teléfono.
    """
    if not q:
        # Si no hay búsqueda, devolver todos
        clientes = await db.clientes.find({}, {"_id": 0}).limit(50).to_list(50)
    else:
        # Búsqueda por nombre, email o teléfono
        query = {
            "$or": [
                {"nombre": {"$regex": q, "$options": "i"}},
                {"email": {"$regex": q, "$options": "i"}},
                {"telefono_completo": {"$regex": q, "$options": "i"}},
                {"telefono": {"$regex": q, "$options": "i"}}
            ]
        }
        clientes = await db.clientes.find(query, {"_id": 0}).limit(20).to_list(20)
    
    # Convertir timestamps
    for cliente in clientes:
        if isinstance(cliente.get('fecha_alta'), str):
            cliente['fecha_alta'] = datetime.fromisoformat(cliente['fecha_alta'])
    
    return clientes


# ============================================
# RUTAS DE CONFIGURACIÓN
# ============================================

@api_router.get("/config/cuenta-deposito")
async def obtener_cuenta_deposito():
    """
    Obtiene la información de la cuenta de depósito.
    """
    return {
        "cuenta": CUENTA_DEPOSITO_CLIENTE,
        "mensaje_bienvenida": MENSAJE_BIENVENIDA_CUENTA
    }


@api_router.get("/config/modo-mantenimiento")
async def obtener_modo_mantenimiento():
    """
    Obtiene el estado del modo mantenimiento.
    """
    return {
        "modo_mantenimiento": MODO_MANTENIMIENTO,
        "activo": MODO_MANTENIMIENTO == "ON"
    }


# ============================================
# RUTAS DE FLUJO MBCONTROL Y LAYOUT SPEI
# ============================================

@api_router.post("/operaciones/{operacion_id}/mbcontrol")
async def registrar_clave_mbcontrol(
    operacion_id: str,
    clave_mbcontrol: str = Form(...)
):
    """
    Registra la clave de MBControl para una operación y genera el layout SPEI.
    """
    try:
        # Verificar que la operación exista
        operacion = await db.operaciones.find_one({"id": operacion_id}, {"_id": 0})
        
        if not operacion:
            raise HTTPException(status_code=404, detail="Operación no encontrada")
        
        # Obtener campos compatibles (Web vs Telegram)
        cantidad_ligas = operacion.get("cantidad_ligas") or operacion.get("numero_ligas") or 1
        nombre_titular = operacion.get("nombre_ligas") or operacion.get("titular_nombre_completo") or "TITULAR"
        
        # Validar que la operación tenga datos completos
        if not nombre_titular or nombre_titular == "TITULAR":
            raise HTTPException(
                status_code=400,
                detail="La operación no tiene datos completos del titular"
            )
        
        # Actualizar clave MBControl
        await db.operaciones.update_one(
            {"id": operacion_id},
            {
                "$set": {
                    "clave_operacion_mbcontrol": clave_mbcontrol,
                    "estado": "PENDIENTE_ENVIO_LAYOUT",
                    "timestamp_mbcontrol": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Obtener datos de comprobantes para calcular monto total
        comprobantes_validos = [c for c in operacion.get("comprobantes", []) if c.get("es_valido")]
        monto_total = sum(c.get("monto") or c.get("monto_detectado") or 0 for c in comprobantes_validos)
        
        # Fallback para captura manual
        if monto_total <= 0:
            monto_total = operacion.get("monto_depositado_cliente") or operacion.get("monto_total_declarado") or 0
        
        # Preparar beneficiarios para el layout
        # SUPUESTO: Por ahora generamos una liga por el monto total
        # En una fase posterior, Ana podrá dividir en múltiples beneficiarios
        monto_por_liga = monto_total / cantidad_ligas if cantidad_ligas > 0 else monto_total
        
        beneficiarios = []
        for i in range(cantidad_ligas):
            beneficiarios.append({
                "clabe": "646180139409481462",  # CLABE de MBco - debe venir de config
                "titular": nombre_titular,
                "monto": monto_por_liga
            })
        
        # Generar layout Excel
        folio = operacion.get("folio_mbco", "N/A")
        layout_path = layout_service.generar_layout_spei(
            folio_mbco=folio,
            clave_mbcontrol=clave_mbcontrol,
            beneficiarios=beneficiarios
        )
        
        # Intentar enviar por correo
        enviado = layout_service.enviar_layout_por_correo(
            layout_path=layout_path,
            folio_mbco=folio,
            clave_mbcontrol=clave_mbcontrol
        )
        
        # Actualizar estado según si se envió o no
        nuevo_estado = "LAYOUT_ENVIADO" if enviado else "PENDIENTE_ENVIO_LAYOUT"
        await db.operaciones.update_one(
            {"id": operacion_id},
            {
                "$set": {
                    "estado": nuevo_estado,
                    "layout_path": layout_path,
                    "layout_enviado": enviado,
                    "timestamp_layout": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        logger.info(f"Clave MBControl registrada para operación {operacion_id}. Layout generado: {layout_path}")
        
        mensaje = "Layout SPEI generado correctamente."
        if enviado:
            mensaje += " El layout fue enviado por correo a Tesorería."
        else:
            mensaje += " El layout fue generado pero no se pudo enviar por correo (configura SMTP en .env)."
        
        return {
            "success": True,
            "operacion_id": operacion_id,
            "clave_mbcontrol": clave_mbcontrol,
            "layout_path": layout_path,
            "enviado": enviado,
            "mensaje": mensaje
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registrando clave MBControl: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/plataformas/recomendar")
async def recomendar_plataforma(
    tipo_operacion: str = "operaciones_netcash",
    monto: float = 0,
    urgencia: str = "normal"
):
    """
    Recomienda la mejor plataforma/cuenta para realizar un layout.
    """
    try:
        recomendacion = consejero_plataformas.recomendar_plataforma(
            tipo_operacion=tipo_operacion,
            monto_total=monto,
            urgencia=urgencia
        )
        
        return recomendacion
        
    except Exception as e:
        logger.error(f"Error recomendando plataforma: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# RUTAS DE GMAIL API
# ============================================

@api_router.get("/gmail/status")
async def verificar_gmail_status():
    """
    Verifica el estado de la configuración de Gmail API
    """
    if gmail_service:
        return {"status": "ok", "configured": True}
    else:
        return {"status": "error", "configured": False}


@api_router.post("/gmail/enviar-prueba")
async def enviar_correo_prueba(
    destinatario: str,
    asunto: str = "Correo de prueba NetCash",
    cuerpo: str = "Este es un correo de prueba del sistema NetCash"
):
    """
    Envía un correo de prueba para verificar que Gmail API funciona
    """
    try:
        exito = gmail_service.enviar_correo(
            destinatario=destinatario,
            asunto=asunto,
            cuerpo_html=f"<html><body><p>{cuerpo}</p></body></html>"
        )
        
        if exito:
            return {"success": True, "mensaje": f"Correo enviado a {destinatario}"}
        else:
            return {"success": False, "mensaje": "Error enviando correo. Revisa logs."}
            
    except Exception as e:
        logger.error(f"Error en enviar_correo_prueba: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/gmail/correos-pendientes")
async def listar_correos_pendientes(etiqueta: str = "NETCASH_INBOX"):
    """
    Lista correos pendientes de procesar
    """
    try:
        correos = gmail_service.leer_correos_pendientes(etiqueta=etiqueta)
        return {
            "total": len(correos),
            "correos": correos
        }
    except Exception as e:
        logger.error(f"Error listando correos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# RUTAS DE CONFIGURACIÓN - CUENTA DEPÓSITO NETCASH
# ============================================

@api_router.get("/config/cuenta-deposito-activa")
async def obtener_cuenta_deposito_activa():
    """
    Obtiene la cuenta de depósito NetCash actualmente activa.
    Esta es la cuenta que se muestra a los clientes para hacer depósitos.
    """
    try:
        cuenta = await cuenta_deposito_service.obtener_cuenta_activa()
        
        if not cuenta:
            raise HTTPException(
                status_code=404,
                detail="No hay cuenta de depósito activa configurada"
            )
        
        return cuenta
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo cuenta activa: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/config/cuentas-deposito")
async def listar_cuentas_deposito(incluir_inactivas: bool = True):
    """
    Lista todas las cuentas de depósito (historial).
    """
    try:
        cuentas = await cuenta_deposito_service.listar_todas_cuentas(incluir_inactivas)
        return {
            "total": len(cuentas),
            "cuentas": cuentas
        }
        
    except Exception as e:
        logger.error(f"Error listando cuentas: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/config/cuenta-deposito")
async def crear_cuenta_deposito(
    banco: str = Form(...),
    clabe: str = Form(...),
    beneficiario: str = Form(...),
    activar_inmediatamente: bool = Form(True)
):
    """
    Crea una nueva cuenta de depósito NetCash.
    Si activar_inmediatamente=True, desactiva las demás cuentas.
    """
    try:
        cuenta = await cuenta_deposito_service.crear_cuenta(
            banco=banco,
            clabe=clabe,
            beneficiario=beneficiario,
            activar_inmediatamente=activar_inmediatamente
        )
        
        return {
            "success": True,
            "cuenta": cuenta,
            "message": "Cuenta creada exitosamente"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creando cuenta: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.put("/config/cuenta-deposito/{cuenta_id}/activar")
async def activar_cuenta_deposito(cuenta_id: str, notificar_clientes: bool = True):
    """
    Activa una cuenta específica y desactiva las demás.
    Opcionalmente envía notificación a todos los clientes activos.
    """
    try:
        exito = await cuenta_deposito_service.activar_cuenta(cuenta_id)
        
        if not exito:
            raise HTTPException(
                status_code=404,
                detail="Cuenta no encontrada"
            )
        
        # Enviar notificaciones si está habilitado
        if notificar_clientes:
            try:
                from notificacion_cuenta_service import enviar_notificacion_cambio_cuenta
                cuenta = await cuenta_deposito_service.obtener_cuenta_activa()
                
                if cuenta:
                    await enviar_notificacion_cambio_cuenta(cuenta)
                    logger.info(f"[ConfigCuenta] Notificaciones enviadas para cuenta {cuenta_id}")
            except Exception as e:
                logger.error(f"[ConfigCuenta] Error enviando notificaciones: {str(e)}")
                # No fallar la activación si falla la notificación
        
        return {
            "success": True,
            "message": "Cuenta activada exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activando cuenta: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.put("/config/cuenta-deposito/{cuenta_id}")
async def actualizar_cuenta_deposito(
    cuenta_id: str,
    banco: Optional[str] = Form(None),
    clabe: Optional[str] = Form(None),
    beneficiario: Optional[str] = Form(None)
):
    """
    Actualiza los datos de una cuenta existente.
    """
    try:
        exito = await cuenta_deposito_service.actualizar_cuenta(
            cuenta_id=cuenta_id,
            banco=banco,
            clabe=clabe,
            beneficiario=beneficiario
        )
        
        if not exito:
            raise HTTPException(
                status_code=404,
                detail="Cuenta no encontrada o sin cambios"
            )
        
        return {
            "success": True,
            "message": "Cuenta actualizada exitosamente"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando cuenta: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# RUTAS DE BENEFICIARIOS FRECUENTES
# ============================================

@api_router.get("/beneficiarios-frecuentes")
async def listar_beneficiarios_frecuentes(cliente_id: Optional[str] = None):
    """
    Lista todos los beneficiarios frecuentes.
    Opcionalmente filtra por cliente_id.
    """
    try:
        query = {"activo": True}
        if cliente_id:
            query["cliente_id"] = cliente_id
        
        beneficiarios = await db.netcash_beneficiarios_frecuentes.find(
            query, {"_id": 0}
        ).sort("nombre_beneficiario", 1).to_list(1000)
        
        return beneficiarios
        
    except Exception as e:
        logger.error(f"Error listando beneficiarios: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/beneficiarios-frecuentes")
async def crear_beneficiario_frecuente(
    cliente_id: str = Form(...),
    nombre_beneficiario: str = Form(...),
    idmex_beneficiario: str = Form(...)
):
    """
    Crea un nuevo beneficiario frecuente para un cliente.
    """
    try:
        from uuid import uuid4
        
        # Validar que el cliente existe
        cliente = await db.clientes.find_one({"id": cliente_id}, {"_id": 0})
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
        # Validar IDMEX (10 dígitos)
        if not idmex_beneficiario or len(idmex_beneficiario) != 10 or not idmex_beneficiario.isdigit():
            raise HTTPException(status_code=400, detail="IDMEX debe tener exactamente 10 dígitos")
        
        # Verificar si ya existe
        existing = await db.netcash_beneficiarios_frecuentes.find_one({
            "cliente_id": cliente_id,
            "nombre_beneficiario": nombre_beneficiario.upper(),
            "activo": True
        })
        
        if existing:
            raise HTTPException(status_code=400, detail="Este beneficiario ya existe para el cliente")
        
        beneficiario_id = f"bf_{uuid4().hex[:8]}"
        
        beneficiario = {
            "id": beneficiario_id,
            "cliente_id": cliente_id,
            "idmex": cliente.get("telegram_id", ""),  # IDMEX del cliente
            "nombre_beneficiario": nombre_beneficiario.upper(),
            "idmex_beneficiario": idmex_beneficiario,
            "alias_mostrar": nombre_beneficiario.upper(),
            "clabe": None,
            "terminacion": None,
            "banco": None,
            "fecha_creacion": datetime.now(timezone.utc),
            "ultima_vez_usado": datetime.now(timezone.utc),
            "activo": True
        }
        
        await db.netcash_beneficiarios_frecuentes.insert_one(beneficiario)
        
        logger.info(f"Beneficiario creado: {beneficiario_id} para cliente {cliente_id}")
        
        if "_id" in beneficiario:
            del beneficiario["_id"]
        return beneficiario
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando beneficiario: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.put("/beneficiarios-frecuentes/{beneficiario_id}")
async def actualizar_beneficiario_frecuente(
    beneficiario_id: str,
    nombre_beneficiario: Optional[str] = Form(None),
    idmex_beneficiario: Optional[str] = Form(None)
):
    """
    Actualiza un beneficiario frecuente existente.
    """
    try:
        # Verificar que existe
        beneficiario = await db.netcash_beneficiarios_frecuentes.find_one(
            {"id": beneficiario_id, "activo": True}
        )
        
        if not beneficiario:
            raise HTTPException(status_code=404, detail="Beneficiario no encontrado")
        
        update_data = {"ultima_vez_usado": datetime.now(timezone.utc)}
        
        if nombre_beneficiario:
            update_data["nombre_beneficiario"] = nombre_beneficiario.upper()
            update_data["alias_mostrar"] = nombre_beneficiario.upper()
        
        if idmex_beneficiario:
            if len(idmex_beneficiario) != 10 or not idmex_beneficiario.isdigit():
                raise HTTPException(status_code=400, detail="IDMEX debe tener exactamente 10 dígitos")
            update_data["idmex_beneficiario"] = idmex_beneficiario
        
        await db.netcash_beneficiarios_frecuentes.update_one(
            {"id": beneficiario_id},
            {"$set": update_data}
        )
        
        logger.info(f"Beneficiario actualizado: {beneficiario_id}")
        
        return {"success": True, "message": "Beneficiario actualizado"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando beneficiario: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/beneficiarios-frecuentes/{beneficiario_id}")
async def eliminar_beneficiario_frecuente(beneficiario_id: str):
    """
    Elimina (desactiva) un beneficiario frecuente.
    """
    try:
        result = await db.netcash_beneficiarios_frecuentes.update_one(
            {"id": beneficiario_id},
            {"$set": {"activo": False}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Beneficiario no encontrado")
        
        logger.info(f"Beneficiario eliminado: {beneficiario_id}")
        
        return {"success": True, "message": "Beneficiario eliminado"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando beneficiario: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Montar archivos estáticos para comprobantes
uploads_dir = Path("/app/backend/uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)
# Montar archivos estáticos en /api/uploads para compatibilidad con ingress
app.mount("/api/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Include routers in the main app
app.include_router(api_router)

# Import and include telegram router
from api_telegram import router as telegram_router
app.include_router(telegram_router, prefix="/api")

# Import and include NetCash V1 router
from routes.netcash_routes import router as netcash_router
from routes.usuarios_routes import router as usuarios_router

app.include_router(netcash_router, prefix="/api")
app.include_router(usuarios_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Inicialización al arrancar el servidor"""
    # Sembrar usuarios iniciales si no existen
    from usuarios_repo import usuarios_repo
    await usuarios_repo.sembrar_usuarios_iniciales()
    
    # Sembrar cuentas de proveedor iniciales si no existen
    from cuentas_proveedor_service import cuentas_proveedor_service
    await cuentas_proveedor_service.sembrar_cuentas_iniciales()
    
    # Iniciar scheduler de Tesorería (recordatorios cada 15 minutos)
    from scheduler_tesoreria import scheduler_tesoreria
    scheduler_tesoreria.start()
    logger.info("[Server] Scheduler de Tesorería iniciado")
    
    # Iniciar scheduler de Monitoreo de Emails (Fase 2 - cada 15 minutos)
    from scheduler_email_monitor import email_monitor_scheduler
    email_monitor_scheduler.start()
    logger.info("[Server] Scheduler de Monitoreo de Emails iniciado")


@app.on_event("shutdown")
async def shutdown_db_client():
    # Detener schedulers
    from scheduler_tesoreria import scheduler_tesoreria
    scheduler_tesoreria.stop()
    logger.info("[Server] Scheduler de Tesorería detenido")
    
    from scheduler_email_monitor import email_monitor_scheduler
    email_monitor_scheduler.shutdown()
    logger.info("[Server] Scheduler de Monitoreo de Emails detenido")
    
    client.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)