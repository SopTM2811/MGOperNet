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
from gmail_service import gmail_service, verificar_configuracion_gmail


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
    """Genera un folio secuencial para operaciones NetCash (ej: NC-000123)"""
    # Buscar el último folio usado
    ultima_operacion = await db.operaciones.find_one(
        {"folio_mbco": {"$exists": True, "$ne": None}},
        {"_id": 0, "folio_mbco": 1},
        sort=[("folio_mbco", -1)]
    )
    
    if ultima_operacion and ultima_operacion.get("folio_mbco"):
        # Extraer el número del último folio (ej: "NC-000123" -> 123)
        try:
            ultimo_numero = int(ultima_operacion["folio_mbco"].split("-")[1])
            nuevo_numero = ultimo_numero + 1
        except (IndexError, ValueError):
            # Si hay error parseando, empezar desde 1
            nuevo_numero = 1
    else:
        # Primera operación
        nuevo_numero = 1
    
    # Formatear con 6 dígitos (ej: NC-000001)
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


@api_router.get("/operaciones", response_model=List[OperacionNetCash])
async def obtener_operaciones():
    """
    Obtiene todas las operaciones NetCash.
    """
    operaciones = await db.operaciones.find({}, {"_id": 0}).to_list(1000)
    
    # Convertir timestamps ISO a datetime
    for op in operaciones:
        if isinstance(op.get('fecha_creacion'), str):
            op['fecha_creacion'] = datetime.fromisoformat(op['fecha_creacion'])
        for field in ['timestamp_confirmacion_cliente', 'timestamp_codigo_sistema', 
                      'timestamp_pago_proveedor', 'timestamp_ligas_recibidas', 
                      'timestamp_entrega_cliente']:
            if op.get(field) and isinstance(op[field], str):
                op[field] = datetime.fromisoformat(op[field])
    
    return operaciones


@api_router.get("/operaciones/{operacion_id}", response_model=OperacionNetCash)
async def obtener_operacion(operacion_id: str):
    """
    Obtiene una operación específica por ID.
    """
    operacion = await db.operaciones.find_one({"id": operacion_id}, {"_id": 0})
    
    if not operacion:
        raise HTTPException(status_code=404, detail="Operación no encontrada")
    
    # Convertir timestamps
    if isinstance(operacion.get('fecha_creacion'), str):
        operacion['fecha_creacion'] = datetime.fromisoformat(operacion['fecha_creacion'])
    
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
                "operacion_duplicada": resultado_duplicado['folio_mbco']
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
            
            # PASO 2: Si NO es duplicado, validar cuenta y beneficiario
            if not es_duplicado:
                # Validar cuenta
                cuenta_valida = ocr_service.validar_cuenta_beneficiaria(
                    datos_ocr.get("cuenta_beneficiaria", ""),
                    CUENTA_DEPOSITO_CLIENTE["clabe"]
                )
                
                # Validar nombre beneficiario
                nombre_valido = ocr_service.validar_nombre_beneficiario(
                    datos_ocr.get("nombre_beneficiario", ""),
                    CUENTA_DEPOSITO_CLIENTE["razon_social"]
                )
                
                if cuenta_valida and nombre_valido:
                    es_valido = True
                    mensaje_validacion = "Comprobante válido"
                else:
                    mensaje_validacion = "La cuenta o el beneficiario no coinciden con la cuenta NetCash esperada"
        
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
        
        nuevo_estado = EstadoOperacion.ESPERANDO_DATOS_TITULAR if es_valido else EstadoOperacion.ESPERANDO_COMPROBANTES
        
        await db.operaciones.update_one(
            {"id": operacion_id},
            {
                "$set": {
                    "comprobantes": comprobantes,
                    "estado": nuevo_estado
                }
            }
        )
        
        logger.info(f"Comprobante procesado para operación {operacion_id}: {mensaje_validacion}")
        
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


@api_router.post("/operaciones/{operacion_id}/calcular")
async def calcular_operacion(
    operacion_id: str,
    comision_cliente_porcentaje: Optional[float] = None
):
    """
    Calcula los montos de una operación NetCash.
    """
    try:
        # Obtener operación
        operacion = await db.operaciones.find_one({"id": operacion_id}, {"_id": 0})
        
        if not operacion:
            raise HTTPException(status_code=404, detail="Operación no encontrada")
        
        # Verificar que haya comprobantes válidos
        comprobantes = operacion.get("comprobantes", [])
        comprobantes_validos = [c for c in comprobantes if c.get("es_valido", False)]
        
        if not comprobantes_validos:
            raise HTTPException(status_code=400, detail="No hay comprobantes válidos")
        
        # Sumar montos de comprobantes
        monto_total = sum(c.get("monto", 0) for c in comprobantes_validos)
        
        if monto_total <= 0:
            raise HTTPException(status_code=400, detail="El monto total debe ser mayor a 0")
        
        # Usar comisión proporcionada o la que está guardada en la operación
        if comision_cliente_porcentaje is None:
            # Usar la comisión guardada en la operación
            comision_cliente_porcentaje = operacion.get("porcentaje_comision_usado", 0.65)
        
        # Convertir de porcentaje a decimal si es necesario
        # Si es > 1, asumir que está en porcentaje (ej: 0.65) y dividir entre 100
        if comision_cliente_porcentaje > 1:
            comision_cliente_porcentaje = comision_cliente_porcentaje / 100
        
        # Realizar cálculos
        calculos_dict = calculos_service.calcular_operacion(
            monto_depositado_cliente=monto_total,
            comision_cliente_porcentaje=comision_cliente_porcentaje
        )
        
        calculos = CalculosNetCash(**calculos_dict)
        
        # Actualizar operación
        await db.operaciones.update_one(
            {"id": operacion_id},
            {
                "$set": {
                    "calculos": calculos.model_dump()
                }
            }
        )
        
        logger.info(f"Cálculos realizados para operación {operacion_id}")
        
        return {
            "success": True,
            "operacion_id": operacion_id,
            "calculos": calculos.model_dump()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculando operación: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/operaciones/{operacion_id}/confirmar")
async def confirmar_operacion(operacion_id: str):
    """
    Confirma una operación y la pasa al siguiente estado.
    """
    try:
        result = await db.operaciones.update_one(
            {"id": operacion_id},
            {
                "$set": {
                    "estado": EstadoOperacion.ESPERANDO_CODIGO_SISTEMA,
                    "timestamp_confirmacion_cliente": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Operación no encontrada")
        
        logger.info(f"Operación {operacion_id} confirmada por cliente")
        
        return {
            "success": True,
            "operacion_id": operacion_id,
            "mensaje": "Operación confirmada. Se enviará a Ana para generar código del sistema."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirmando operación: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# RUTAS DE CLIENTES
# ============================================

@api_router.get("/clientes", response_model=List[Cliente])
async def obtener_clientes():
    """
    Obtiene todos los clientes.
    """
    clientes = await db.clientes.find({}, {"_id": 0}).to_list(1000)
    
    for cliente in clientes:
        if isinstance(cliente.get('fecha_alta'), str):
            cliente['fecha_alta'] = datetime.fromisoformat(cliente['fecha_alta'])
    
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
        
        # Validar que la operación tenga datos completos
        if not operacion.get("cantidad_ligas") or not operacion.get("nombre_ligas"):
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
        monto_total = sum(c.get("monto", 0) for c in comprobantes_validos)
        
        # Preparar beneficiarios para el layout
        # SUPUESTO: Por ahora generamos una liga por el monto total
        # En una fase posterior, Ana podrá dividir en múltiples beneficiarios
        cantidad_ligas = operacion.get("cantidad_ligas", 1)
        monto_por_liga = monto_total / cantidad_ligas if cantidad_ligas > 0 else monto_total
        
        beneficiarios = []
        for i in range(cantidad_ligas):
            beneficiarios.append({
                "clabe": "646180139409481462",  # CLABE de MBco - debe venir de config
                "titular": operacion.get("nombre_ligas", "TITULAR"),
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
    return verificar_configuracion_gmail()


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

# Montar archivos estáticos para comprobantes
uploads_dir = Path("/app/backend/uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)