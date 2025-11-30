"""
Rutas API para gestión de usuarios NetCash
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict
import logging
from usuarios_repo import usuarios_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/netcash/usuarios", tags=["Usuarios NetCash"])


@router.get("/", response_model=List[Dict])
async def listar_usuarios():
    """
    Lista todos los usuarios del catálogo NetCash
    
    Returns:
        Lista de usuarios con sus datos
    """
    try:
        usuarios = await usuarios_repo.listar_todos_usuarios()
        return usuarios
    except Exception as e:
        logger.error(f"[API Usuarios] Error listando usuarios: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al listar usuarios")


@router.get("/por-rol/{rol_negocio}")
async def obtener_usuario_por_rol(rol_negocio: str):
    """
    Obtiene un usuario específico por su rol de negocio
    
    Args:
        rol_negocio: Rol de negocio (ej: admin_netcash, tesoreria)
        
    Returns:
        Dict con datos del usuario
    """
    try:
        usuario = await usuarios_repo.obtener_usuario_por_rol(rol_negocio)
        
        if not usuario:
            raise HTTPException(status_code=404, detail=f"Usuario con rol '{rol_negocio}' no encontrado")
        
        return usuario
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API Usuarios] Error obteniendo usuario por rol: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al obtener usuario")


@router.post("/sembrar")
async def sembrar_usuarios_iniciales():
    """
    Endpoint para sembrar usuarios iniciales en el catálogo
    
    Útil para inicialización o reset del sistema
    
    Returns:
        Dict con resultado de la operación
    """
    try:
        await usuarios_repo.sembrar_usuarios_iniciales()
        return {"success": True, "message": "Usuarios sembrados correctamente"}
    except Exception as e:
        logger.error(f"[API Usuarios] Error sembrando usuarios: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al sembrar usuarios")
