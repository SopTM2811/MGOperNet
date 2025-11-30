"""
Servicio de gestión de cuentas de proveedor NetCash

Este servicio gestiona las cuentas bancarias del proveedor (DNS) usadas para:
- Capital / Ligas: Pagos al proveedor que genera las ligas
- Comisión DNS: Comisión al proveedor por el servicio

La configuración se almacena en BD para facilitar cambios de proveedor sin tocar código.
"""

import logging
import os
from typing import Optional, Dict, List
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)

# Conexión MongoDB
mongo_url = os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'netcash_mbco')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

COLLECTION_NAME = 'cuentas_proveedor_netcash'


class CuentasProveedorService:
    """Servicio para gestión de cuentas bancarias del proveedor NetCash"""
    
    async def obtener_cuenta_activa(self, tipo: str) -> Optional[Dict]:
        """
        Obtiene la cuenta activa de un tipo específico
        
        Args:
            tipo: "capital" o "comision_dns"
            
        Returns:
            Dict con datos de la cuenta o None si no existe
        """
        try:
            cuenta = await db[COLLECTION_NAME].find_one(
                {
                    "tipo": tipo,
                    "activo": True
                },
                {"_id": 0}
            )
            
            if cuenta:
                logger.info(f"[CuentasProveedor] Cuenta activa '{tipo}': {cuenta.get('beneficiario')} - {cuenta.get('clabe')}")
            else:
                logger.warning(f"[CuentasProveedor] No hay cuenta activa para tipo '{tipo}'")
            
            return cuenta
            
        except Exception as e:
            logger.error(f"[CuentasProveedor] Error obteniendo cuenta activa: {str(e)}")
            return None
    
    async def listar_todas_cuentas(self, incluir_inactivas: bool = True) -> List[Dict]:
        """
        Lista todas las cuentas de proveedor
        
        Args:
            incluir_inactivas: Si True, incluye cuentas inactivas
            
        Returns:
            Lista de cuentas
        """
        try:
            filtro = {} if incluir_inactivas else {"activo": True}
            
            cuentas = await db[COLLECTION_NAME].find(
                filtro,
                {"_id": 0}
            ).sort([("tipo", 1), ("fecha_alta", -1)]).to_list(100)
            
            logger.info(f"[CuentasProveedor] Listando {len(cuentas)} cuenta(s)")
            
            return cuentas
            
        except Exception as e:
            logger.error(f"[CuentasProveedor] Error listando cuentas: {str(e)}")
            return []
    
    async def crear_cuenta(
        self,
        tipo: str,
        beneficiario: str,
        banco: str,
        clabe: str,
        activar_inmediatamente: bool = True,
        notas: str = None
    ) -> Dict:
        """
        Crea una nueva cuenta de proveedor
        
        Args:
            tipo: "capital" o "comision_dns"
            beneficiario: Nombre del beneficiario
            banco: Nombre del banco
            clabe: CLABE de 18 dígitos
            activar_inmediatamente: Si True, desactiva otras cuentas del mismo tipo
            notas: Notas adicionales
            
        Returns:
            Dict con resultado de la operación
        """
        try:
            # Validar tipo
            if tipo not in ["capital", "comision_dns"]:
                raise ValueError(f"Tipo inválido: {tipo}. Debe ser 'capital' o 'comision_dns'")
            
            # Validar CLABE
            if len(clabe) != 18 or not clabe.isdigit():
                raise ValueError(f"CLABE inválida: debe tener 18 dígitos")
            
            # Si se va a activar, desactivar otras cuentas del mismo tipo
            if activar_inmediatamente:
                await self._desactivar_cuentas_tipo(tipo)
            
            # Crear nueva cuenta
            cuenta_id = str(uuid4())
            cuenta = {
                "id": cuenta_id,
                "tipo": tipo,
                "beneficiario": beneficiario.upper(),
                "banco": banco.upper(),
                "clabe": clabe,
                "activo": activar_inmediatamente,
                "fecha_alta": datetime.now(timezone.utc),
                "fecha_baja": None,
                "notas": notas or "",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            await db[COLLECTION_NAME].insert_one(cuenta)
            
            logger.info(f"[CuentasProveedor] Cuenta creada: {tipo} - {beneficiario} - {clabe}")
            
            return {"success": True, "cuenta": cuenta}
            
        except ValueError as e:
            logger.error(f"[CuentasProveedor] Error de validación: {str(e)}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"[CuentasProveedor] Error creando cuenta: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def activar_cuenta(self, cuenta_id: str) -> bool:
        """
        Activa una cuenta y desactiva las demás del mismo tipo
        
        Args:
            cuenta_id: ID de la cuenta a activar
            
        Returns:
            True si se activó correctamente
        """
        try:
            # Buscar la cuenta
            cuenta = await db[COLLECTION_NAME].find_one(
                {"id": cuenta_id},
                {"_id": 0}
            )
            
            if not cuenta:
                logger.warning(f"[CuentasProveedor] Cuenta no encontrada: {cuenta_id}")
                return False
            
            tipo = cuenta.get("tipo")
            
            # Desactivar otras cuentas del mismo tipo
            await self._desactivar_cuentas_tipo(tipo)
            
            # Activar esta cuenta
            await db[COLLECTION_NAME].update_one(
                {"id": cuenta_id},
                {
                    "$set": {
                        "activo": True,
                        "fecha_baja": None,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            logger.info(f"[CuentasProveedor] Cuenta activada: {cuenta_id} ({tipo})")
            return True
            
        except Exception as e:
            logger.error(f"[CuentasProveedor] Error activando cuenta: {str(e)}")
            return False
    
    async def desactivar_cuenta(self, cuenta_id: str) -> bool:
        """
        Desactiva una cuenta
        
        Args:
            cuenta_id: ID de la cuenta a desactivar
            
        Returns:
            True si se desactivó correctamente
        """
        try:
            result = await db[COLLECTION_NAME].update_one(
                {"id": cuenta_id},
                {
                    "$set": {
                        "activo": False,
                        "fecha_baja": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"[CuentasProveedor] Cuenta desactivada: {cuenta_id}")
                return True
            else:
                logger.warning(f"[CuentasProveedor] No se desactivó la cuenta: {cuenta_id}")
                return False
            
        except Exception as e:
            logger.error(f"[CuentasProveedor] Error desactivando cuenta: {str(e)}")
            return False
    
    async def _desactivar_cuentas_tipo(self, tipo: str):
        """Desactiva todas las cuentas activas de un tipo"""
        try:
            result = await db[COLLECTION_NAME].update_many(
                {
                    "tipo": tipo,
                    "activo": True
                },
                {
                    "$set": {
                        "activo": False,
                        "fecha_baja": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"[CuentasProveedor] Desactivadas {result.modified_count} cuenta(s) tipo '{tipo}'")
            
        except Exception as e:
            logger.error(f"[CuentasProveedor] Error desactivando cuentas tipo '{tipo}': {str(e)}")
    
    async def sembrar_cuentas_iniciales(self):
        """Siembra las cuentas iniciales del proveedor si no existen"""
        try:
            # Verificar si ya existen cuentas
            count = await db[COLLECTION_NAME].count_documents({})
            if count > 0:
                logger.info(f"[CuentasProveedor] Ya existen {count} cuenta(s) configurada(s)")
                return
            
            logger.info(f"[CuentasProveedor] Sembrando cuentas iniciales del proveedor...")
            
            cuentas_iniciales = [
                {
                    "tipo": "capital",
                    "beneficiario": "AFFORDABLE MEDICAL SERVICES SC",
                    "banco": "BBVA",
                    "clabe": "012680001255709482",
                    "notas": "Cuenta para pagos de capital (ligas) al proveedor"
                },
                {
                    "tipo": "comision_dns",
                    "beneficiario": "Comercializadora Uetacop SA de CV",
                    "banco": "ASP",
                    "clabe": "058680000012912655",
                    "notas": "Cuenta para comisión DNS al proveedor"
                }
            ]
            
            for cuenta_data in cuentas_iniciales:
                result = await self.crear_cuenta(
                    tipo=cuenta_data["tipo"],
                    beneficiario=cuenta_data["beneficiario"],
                    banco=cuenta_data["banco"],
                    clabe=cuenta_data["clabe"],
                    activar_inmediatamente=True,
                    notas=cuenta_data["notas"]
                )
                
                if result["success"]:
                    logger.info(f"[CuentasProveedor] ✅ Cuenta sembrada: {cuenta_data['tipo']} - {cuenta_data['beneficiario']}")
                else:
                    logger.error(f"[CuentasProveedor] ❌ Error sembrando cuenta: {result.get('error')}")
            
            logger.info(f"[CuentasProveedor] ✅ Cuentas iniciales sembradas correctamente")
            
        except Exception as e:
            logger.error(f"[CuentasProveedor] Error sembrando cuentas iniciales: {str(e)}")
            import traceback
            traceback.print_exc()


# Instancia global del servicio
cuentas_proveedor_service = CuentasProveedorService()
