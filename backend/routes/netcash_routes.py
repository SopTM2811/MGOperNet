"""Endpoints API para NetCash V1

Estos endpoints permiten a los canales (Telegram, Email, Panel Ana)
interactuar con el motor central NetCash.

Rutas principales:
- POST /api/netcash/solicitudes - Crear solicitud
- GET /api/netcash/solicitudes/{id} - Consultar solicitud
- PUT /api/netcash/solicitudes/{id} - Actualizar solicitud
- POST /api/netcash/solicitudes/{id}/comprobante - Agregar comprobante
- POST /api/netcash/solicitudes/{id}/validar - Validar y procesar
- GET /api/netcash/solicitudes/cliente/{cliente_id} - Listar por cliente
"""

import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import List, Optional
from pathlib import Path
import uuid

from models.netcash_models import (
    SolicitudCreate, SolicitudUpdate, ResumenCliente,
    EstadoSolicitud, CanalOrigen
)
from netcash_service import netcash_service
from config_cuentas_service import config_cuentas_service, TipoCuenta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/netcash", tags=["NetCash"])


# ==================== SOLICITUDES ====================

@router.post("/solicitudes")
async def crear_solicitud(datos: SolicitudCreate):
    """
    Crea una nueva solicitud NetCash en estado BORRADOR.
    
    Esta es la entrada principal desde cualquier canal.
    """
    try:
        solicitud = await netcash_service.crear_solicitud(datos)
        
        if not solicitud:
            raise HTTPException(status_code=500, detail="Error creando solicitud")
        
        return {
            "success": True,
            "solicitud": solicitud,
            "message": "Solicitud creada en estado borrador"
        }
        
    except Exception as e:
        logger.error(f"[API NetCash] Error en crear_solicitud: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/solicitudes/{solicitud_id}")
async def obtener_solicitud(solicitud_id: str):
    """Obtiene el detalle completo de una solicitud"""
    try:
        solicitud = await netcash_service.obtener_solicitud(solicitud_id)
        
        if not solicitud:
            raise HTTPException(status_code=404, detail="Solicitud no encontrada")
        
        return {"success": True, "solicitud": solicitud}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API NetCash] Error en obtener_solicitud: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/solicitudes/{solicitud_id}")
async def actualizar_solicitud(solicitud_id: str, datos: SolicitudUpdate):
    """Actualiza datos de una solicitud existente"""
    try:
        actualizado = await netcash_service.actualizar_solicitud(solicitud_id, datos)
        
        if not actualizado:
            raise HTTPException(status_code=404, detail="Solicitud no encontrada o no se pudo actualizar")
        
        return {
            "success": True,
            "message": "Solicitud actualizada"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API NetCash] Error en actualizar_solicitud: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/solicitudes/{solicitud_id}/comprobante")
async def agregar_comprobante(
    solicitud_id: str,
    file: UploadFile = File(...)
):
    """
    Agrega un comprobante a una solicitud.
    El comprobante se valida automáticamente contra la cuenta concertadora activa.
    """
    try:
        # Guardar archivo
        upload_dir = Path("/app/backend/uploads/comprobantes")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        file_path = upload_dir / f"{file_id}{file_extension}"
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Agregar a solicitud
        agregado = await netcash_service.agregar_comprobante(
            solicitud_id,
            str(file_path),
            file.filename
        )
        
        if not agregado:
            raise HTTPException(status_code=500, detail="Error agregando comprobante")
        
        # Obtener solicitud actualizada para ver el resultado de validación
        solicitud = await netcash_service.obtener_solicitud(solicitud_id)
        ultimo_comprobante = solicitud.get("comprobantes", [])[-1] if solicitud else None
        
        return {
            "success": True,
            "comprobante": ultimo_comprobante,
            "message": "Comprobante agregado y validado"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API NetCash] Error en agregar_comprobante: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/solicitudes/{solicitud_id}/validar")
async def validar_y_procesar(solicitud_id: str):
    """
    Valida completamente una solicitud y la procesa automáticamente:
    - Si TODO OK -> LISTA_PARA_MBC (genera folio)
    - Si hay errores -> RECHAZADA
    
    Retorna un resumen amigable para el cliente.
    """
    try:
        # Procesar
        exitoso, mensaje = await netcash_service.procesar_solicitud_automaticamente(solicitud_id)
        
        # Generar resumen para cliente
        resumen = await netcash_service.generar_resumen_cliente(solicitud_id)
        
        if not resumen:
            raise HTTPException(status_code=500, detail="Error generando resumen")
        
        return {
            "success": exitoso,
            "resumen": resumen.dict(),
            "message": mensaje
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API NetCash] Error en validar_y_procesar: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/solicitudes/cliente/{cliente_id}")
async def listar_solicitudes_cliente(
    cliente_id: str,
    solo_validas: bool = False,
    limite: int = 20
):
    """
    Lista las solicitudes NetCash de un cliente.
    
    Args:
        cliente_id: ID del cliente
        solo_validas: Si True, solo muestra las que están en lista_para_mbc
        limite: Número máximo de resultados
    """
    try:
        solicitudes = await netcash_service.listar_solicitudes_cliente(
            cliente_id,
            solo_validas,
            limite
        )
        
        return {
            "success": True,
            "solicitudes": solicitudes,
            "total": len(solicitudes)
        }
        
    except Exception as e:
        logger.error(f"[API NetCash] Error en listar_solicitudes_cliente: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CONFIGURACIÓN DE CUENTAS ====================

@router.get("/cuentas/activa/{tipo}")
async def obtener_cuenta_activa(tipo: str):
    """
    Obtiene la cuenta bancaria activa de un tipo específico.
    
    Tipos válidos: concertadora, capital, comision
    """
    try:
        tipo_enum = TipoCuenta(tipo)
        cuenta = await config_cuentas_service.obtener_cuenta_activa(tipo_enum)
        
        if not cuenta:
            raise HTTPException(
                status_code=404,
                detail=f"No hay cuenta activa de tipo {tipo}"
            )
        
        return {"success": True, "cuenta": cuenta}
        
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de cuenta inválido: {tipo}. Válidos: concertadora, capital, comision"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API NetCash] Error en obtener_cuenta_activa: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cuentas")
async def listar_cuentas(tipo: Optional[str] = None, solo_activas: bool = False):
    """Lista todas las cuentas bancarias configuradas"""
    try:
        tipo_enum = TipoCuenta(tipo) if tipo else None
        cuentas = await config_cuentas_service.listar_cuentas(tipo_enum, solo_activas)
        
        return {
            "success": True,
            "cuentas": cuentas,
            "total": len(cuentas)
        }
        
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de cuenta inválido: {tipo}"
        )
    except Exception as e:
        logger.error(f"[API NetCash] Error en listar_cuentas: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== UTILIDADES ====================

@router.get("/resumen/{solicitud_id}")
async def obtener_resumen_cliente(solicitud_id: str):
    """
    Genera un resumen amigable de una solicitud para mostrar al cliente.
    
    Este es el formato estándar usado por todos los canales.
    """
    try:
        resumen = await netcash_service.generar_resumen_cliente(solicitud_id)
        
        if not resumen:
            raise HTTPException(status_code=404, detail="Solicitud no encontrada")
        
        return {"success": True, "resumen": resumen.dict()}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API NetCash] Error en obtener_resumen_cliente: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
