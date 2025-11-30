"""
Repositorio de Usuarios NetCash

Gestiona el catálogo centralizado de usuarios con roles y permisos.
Los usuarios definen quién recibe notificaciones, puede ejecutar acciones, etc.
"""

import logging
from typing import Optional, Dict, List
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from uuid import uuid4
import os

logger = logging.getLogger(__name__)

# Conexión MongoDB
mongo_url = os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'netcash_mbco')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

COLLECTION_NAME = 'usuarios_netcash'


class UsuariosRepository:
    """Repositorio para gestión de usuarios NetCash"""
    
    async def obtener_usuario_por_rol(self, rol_negocio: str) -> Optional[Dict]:
        """
        Obtiene el primer usuario activo con el rol especificado
        
        Args:
            rol_negocio: Rol de negocio (ej: "admin_netcash", "tesoreria")
            
        Returns:
            Dict con datos del usuario o None si no existe
        """
        try:
            usuario = await db[COLLECTION_NAME].find_one(
                {
                    "rol_negocio": rol_negocio,
                    "activo": True
                },
                {"_id": 0}
            )
            
            if usuario:
                logger.info(f"[UsuariosRepo] Usuario encontrado para rol '{rol_negocio}': {usuario.get('nombre')}")
            else:
                logger.warning(f"[UsuariosRepo] No se encontró usuario activo con rol '{rol_negocio}'")
            
            return usuario
            
        except Exception as e:
            logger.error(f"[UsuariosRepo] Error obteniendo usuario por rol: {str(e)}")
            return None
    
    async def obtener_usuarios_por_permiso(self, flag_permiso: str, valor: bool = True) -> List[Dict]:
        """
        Obtiene todos los usuarios activos que tienen un permiso específico
        
        Args:
            flag_permiso: Nombre del permiso (ej: "recibe_alertas_tesoreria")
            valor: Valor esperado del permiso (default: True)
            
        Returns:
            Lista de usuarios con el permiso
        """
        try:
            filtro = {
                "activo": True,
                f"permisos.{flag_permiso}": valor
            }
            
            usuarios = await db[COLLECTION_NAME].find(
                filtro,
                {"_id": 0}
            ).to_list(100)
            
            logger.info(f"[UsuariosRepo] {len(usuarios)} usuario(s) encontrado(s) con permiso '{flag_permiso}={valor}'")
            
            return usuarios
            
        except Exception as e:
            logger.error(f"[UsuariosRepo] Error obteniendo usuarios por permiso: {str(e)}")
            return []
    
    async def listar_todos_usuarios(self) -> List[Dict]:
        """
        Lista todos los usuarios del sistema (activos e inactivos)
        
        Returns:
            Lista de todos los usuarios
        """
        try:
            usuarios = await db[COLLECTION_NAME].find(
                {},
                {"_id": 0}
            ).sort("nombre", 1).to_list(1000)
            
            logger.info(f"[UsuariosRepo] Listando {len(usuarios)} usuario(s) total(es)")
            
            return usuarios
            
        except Exception as e:
            logger.error(f"[UsuariosRepo] Error listando usuarios: {str(e)}")
            return []
    
    async def crear_usuario(self, usuario_data: Dict) -> Dict:
        """
        Crea un nuevo usuario en el catálogo
        
        Args:
            usuario_data: Datos del usuario a crear
            
        Returns:
            Dict con resultado de la operación
        """
        try:
            # Generar ID único
            id_usuario = usuario_data.get("id_usuario", str(uuid4()))
            
            # Estructura completa del usuario
            usuario = {
                "id_usuario": id_usuario,
                "nombre": usuario_data.get("nombre", "Sin nombre"),
                "rol_negocio": usuario_data.get("rol_negocio", "sin_rol"),
                "telegram_id": usuario_data.get("telegram_id"),  # Puede ser None
                "email": usuario_data.get("email"),  # Puede ser None
                "activo": usuario_data.get("activo", True),
                "permisos": usuario_data.get("permisos", {}),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            await db[COLLECTION_NAME].insert_one(usuario)
            
            logger.info(f"[UsuariosRepo] Usuario creado: {usuario['nombre']} ({usuario['rol_negocio']})")
            
            return {"success": True, "usuario": usuario}
            
        except Exception as e:
            logger.error(f"[UsuariosRepo] Error creando usuario: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def sembrar_usuarios_iniciales(self):
        """
        Siembra los usuarios iniciales del sistema si no existen
        """
        try:
            # Verificar si ya existen usuarios
            count = await db[COLLECTION_NAME].count_documents({})
            if count > 0:
                logger.info(f"[UsuariosRepo] Ya existen {count} usuario(s) en el catálogo")
                return
            
            logger.info(f"[UsuariosRepo] Sembrando usuarios iniciales...")
            
            usuarios_iniciales = [
                {
                    "nombre": "Daniel",
                    "rol_negocio": "master",
                    "telegram_id": 76316336750,  # ID de pruebas
                    "email": "daniel@mbco.mx",
                    "activo": True,
                    "permisos": {
                        "puede_asignar_folio_mbco": True,
                        "puede_ver_usuarios": True,
                        "puede_usar_alta_telegram": True,
                        "recibe_alertas_tesoreria": True,
                        "recibe_alertas_proveedor": True,
                        "recibe_reporte_diario": True,
                        "acceso_total": True
                    }
                },
                {
                    "nombre": "Ana",
                    "rol_negocio": "admin_netcash",
                    "telegram_id": 76316336750,  # ID de pruebas (cambiar en producción a 1720830607)
                    "email": "ana@mbco.mx",
                    "activo": True,
                    "permisos": {
                        "puede_asignar_folio_mbco": True,
                        "puede_ver_usuarios": True,
                        "puede_usar_alta_telegram": True,
                        "recibe_alertas_tesoreria": False,
                        "recibe_alertas_proveedor": False,
                        "recibe_reporte_diario": False
                    }
                },
                {
                    "nombre": "Toño",
                    "rol_negocio": "tesoreria",
                    "telegram_id": None,  # TODO: Agregar ID real
                    "email": "tono@mbco.mx",
                    "activo": True,
                    "permisos": {
                        "puede_asignar_folio_mbco": False,
                        "recibe_alertas_tesoreria": True,
                        "recibe_alertas_proveedor": False,
                        "recibe_reporte_diario": False
                    }
                },
                {
                    "nombre": "Javier",
                    "rol_negocio": "sup_tesoreria",
                    "telegram_id": None,  # TODO: Agregar ID real
                    "email": "javier@mbco.mx",
                    "activo": True,
                    "permisos": {
                        "puede_asignar_folio_mbco": False,
                        "recibe_alertas_tesoreria": True,
                        "recibe_alertas_proveedor": False,
                        "recibe_reporte_diario": True
                    }
                },
                {
                    "nombre": "Ximena",
                    "rol_negocio": "operador_proveedor",
                    "telegram_id": None,  # TODO: Agregar ID real
                    "email": "ximena@mbco.mx",
                    "activo": True,
                    "permisos": {
                        "puede_asignar_folio_mbco": False,
                        "recibe_alertas_tesoreria": False,
                        "recibe_alertas_proveedor": True,
                        "recibe_reporte_diario": False
                    }
                },
                {
                    "nombre": "Carlos",
                    "rol_negocio": "sup_proveedor",
                    "telegram_id": None,  # TODO: Agregar ID real
                    "email": "carlos@mbco.mx",
                    "activo": True,
                    "permisos": {
                        "puede_asignar_folio_mbco": False,
                        "recibe_alertas_tesoreria": False,
                        "recibe_alertas_proveedor": True,
                        "recibe_reporte_diario": True
                    }
                },
                {
                    "nombre": "Samuel",
                    "rol_negocio": "socio_mbco",
                    "telegram_id": None,  # TODO: Agregar ID real
                    "email": "samuel@mbco.mx",
                    "activo": True,
                    "permisos": {
                        "puede_asignar_folio_mbco": False,
                        "recibe_alertas_tesoreria": False,
                        "recibe_alertas_proveedor": False,
                        "recibe_reporte_diario": True
                    }
                },
                {
                    "nombre": "Nash",
                    "rol_negocio": "dueno_dns",
                    "telegram_id": None,  # TODO: Agregar ID real
                    "email": "nash@mbco.mx",
                    "activo": True,
                    "permisos": {
                        "puede_asignar_folio_mbco": False,
                        "recibe_alertas_tesoreria": False,
                        "recibe_alertas_proveedor": False,
                        "recibe_reporte_diario": True
                    }
                },
                {
                    "nombre": "AGLAE",
                    "rol_negocio": "apoyo_cliente",
                    "telegram_id": None,  # TODO: Agregar ID real
                    "email": "aglae@mbco.mx",
                    "activo": True,
                    "permisos": {
                        "puede_asignar_folio_mbco": False,
                        "recibe_alertas_tesoreria": False,
                        "recibe_alertas_proveedor": False,
                        "recibe_reporte_diario": False,
                        "puede_crear_operaciones_cliente": True
                    }
                }
            ]
            
            # Insertar cada usuario
            for usuario_data in usuarios_iniciales:
                await self.crear_usuario(usuario_data)
            
            logger.info(f"[UsuariosRepo] ✅ {len(usuarios_iniciales)} usuarios sembrados correctamente")
            
        except Exception as e:
            logger.error(f"[UsuariosRepo] Error sembrando usuarios iniciales: {str(e)}")
            import traceback
            traceback.print_exc()


# Instancia global del repositorio
usuarios_repo = UsuariosRepository()
