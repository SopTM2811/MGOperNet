from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from typing import List, Optional
import shutil
from datetime import datetime, timezone

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
    """
    try:
        # Verificar que la operación exista
        operacion = await db.operaciones.find_one({"id": operacion_id}, {"_id": 0})
        if not operacion:
            raise HTTPException(status_code=404, detail="Operación no encontrada")
        
        # Guardar archivo temporalmente
        upload_dir = Path("/tmp/netcash_uploads")
        upload_dir.mkdir(exist_ok=True)
        
        file_path = upload_dir / f"{operacion_id}_{file.filename}"
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Determinar tipo MIME
        mime_type = file.content_type or "application/octet-stream"
        
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
        
        # Crear comprobante
        comprobante = ComprobanteDepositoOCR(
            **datos_ocr,
            archivo_original=file.filename,
            es_valido=es_valido,
            es_duplicado=es_duplicado,
            mensaje_validacion=mensaje_validacion
        )
        
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