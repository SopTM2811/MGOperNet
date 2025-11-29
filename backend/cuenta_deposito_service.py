"""Servicio para gestionar la cuenta de depósito NetCash

Este servicio centraliza el acceso a la configuración de la cuenta
de depósito que usan los clientes para transferencias NetCash.
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os

logger = logging.getLogger(__name__)

# Conexión a MongoDB
mongo_url = os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'netcash_mbco')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

COLLECTION_NAME = 'config_cuenta_deposito_netcash'


class CuentaDepositoService:
    """Servicio para gestionar la cuenta de depósito NetCash"""
    
    async def obtener_cuenta_activa(self) -> Optional[Dict]:
        """
        Obtiene la cuenta de depósito actualmente activa.
        
        Returns:
            Dict con banco, clabe, beneficiario o None si no hay cuenta activa
        """
        try:
            cuenta = await db[COLLECTION_NAME].find_one(
                {"activa": True},
                {"_id": 0}
            )
            
            if not cuenta:
                logger.warning("[CuentaDeposito] No hay cuenta activa configurada")
                return None
            
            logger.info(f"[CuentaDeposito] Cuenta activa: {cuenta.get('banco')} - {cuenta.get('clabe')}")
            return cuenta
            
        except Exception as e:
            logger.error(f"[CuentaDeposito] Error obteniendo cuenta activa: {str(e)}")
            return None
    
    async def listar_todas_cuentas(self, incluir_inactivas: bool = True) -> List[Dict]:
        """
        Lista todas las cuentas de depósito (historial).
        
        Args:
            incluir_inactivas: Si True, incluye cuentas inactivas
        
        Returns:
            Lista de cuentas ordenadas por fecha de creación (más reciente primero)
        """
        try:
            filtro = {} if incluir_inactivas else {"activa": True}
            
            cuentas = await db[COLLECTION_NAME].find(
                filtro,
                {"_id": 0}
            ).sort("created_at", -1).to_list(100)
            
            logger.info(f"[CuentaDeposito] {len(cuentas)} cuentas encontradas")
            return cuentas
            
        except Exception as e:
            logger.error(f"[CuentaDeposito] Error listando cuentas: {str(e)}")
            return []
    
    async def crear_cuenta(self, banco: str, clabe: str, beneficiario: str,
                          activar_inmediatamente: bool = True) -> Dict:
        """
        Crea una nueva cuenta de depósito.
        
        Args:
            banco: Nombre del banco
            clabe: CLABE de 18 dígitos
            beneficiario: Nombre completo del beneficiario
            activar_inmediatamente: Si True, desactiva otras cuentas y activa esta
        
        Returns:
            Cuenta creada
        """
        try:
            # Validar CLABE (18 dígitos)
            if not clabe or len(clabe) != 18 or not clabe.isdigit():
                raise ValueError("La CLABE debe tener exactamente 18 dígitos")
            
            # Si se debe activar inmediatamente, desactivar todas las demás
            if activar_inmediatamente:
                await db[COLLECTION_NAME].update_many(
                    {"activa": True},
                    {"$set": {"activa": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
                logger.info("[CuentaDeposito] Cuentas anteriores desactivadas")
            
            # Crear nueva cuenta
            nueva_cuenta = {
                "id": f"cuenta-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                "banco": banco,
                "clabe": clabe,
                "beneficiario": beneficiario,
                "activa": activar_inmediatamente,
                "fecha_vigencia_desde": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db[COLLECTION_NAME].insert_one(nueva_cuenta)
            
            logger.info(f"[CuentaDeposito] Nueva cuenta creada: {banco} - {clabe}")
            
            # Retornar sin _id
            del nueva_cuenta['_id'] if '_id' in nueva_cuenta else None
            return nueva_cuenta
            
        except Exception as e:
            logger.error(f"[CuentaDeposito] Error creando cuenta: {str(e)}")
            raise
    
    async def activar_cuenta(self, cuenta_id: str) -> bool:
        """
        Activa una cuenta específica y desactiva las demás.
        
        Args:
            cuenta_id: ID de la cuenta a activar
        
        Returns:
            True si se activó correctamente
        """
        try:
            # Verificar que la cuenta existe
            cuenta = await db[COLLECTION_NAME].find_one({"id": cuenta_id})
            
            if not cuenta:
                logger.error(f"[CuentaDeposito] Cuenta {cuenta_id} no encontrada")
                return False
            
            # Desactivar todas las cuentas
            await db[COLLECTION_NAME].update_many(
                {"activa": True},
                {"$set": {"activa": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            
            # Activar la cuenta seleccionada
            await db[COLLECTION_NAME].update_one(
                {"id": cuenta_id},
                {"$set": {"activa": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            
            logger.info(f"[CuentaDeposito] Cuenta {cuenta_id} activada")
            return True
            
        except Exception as e:
            logger.error(f"[CuentaDeposito] Error activando cuenta: {str(e)}")
            return False
    
    async def actualizar_cuenta(self, cuenta_id: str, banco: str = None,
                               clabe: str = None, beneficiario: str = None) -> bool:
        """
        Actualiza los datos de una cuenta existente.
        
        Args:
            cuenta_id: ID de la cuenta a actualizar
            banco: Nuevo nombre del banco (opcional)
            clabe: Nueva CLABE (opcional)
            beneficiario: Nuevo beneficiario (opcional)
        
        Returns:
            True si se actualizó correctamente
        """
        try:
            # Validar CLABE si se proporciona
            if clabe and (len(clabe) != 18 or not clabe.isdigit()):
                raise ValueError("La CLABE debe tener exactamente 18 dígitos")
            
            # Construir update
            update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
            
            if banco:
                update_data["banco"] = banco
            if clabe:
                update_data["clabe"] = clabe
            if beneficiario:
                update_data["beneficiario"] = beneficiario
            
            result = await db[COLLECTION_NAME].update_one(
                {"id": cuenta_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"[CuentaDeposito] Cuenta {cuenta_id} actualizada")
                return True
            else:
                logger.warning(f"[CuentaDeposito] Cuenta {cuenta_id} no encontrada o sin cambios")
                return False
            
        except Exception as e:
            logger.error(f"[CuentaDeposito] Error actualizando cuenta: {str(e)}")
            return False
    
    def formatear_cuenta_para_mensaje(self, cuenta: Optional[Dict]) -> str:
        """
        Formatea la información de la cuenta para mostrar en mensajes.
        
        Args:
            cuenta: Dict con los datos de la cuenta o None
        
        Returns:
            Texto formateado con los datos de la cuenta
        """
        if not cuenta:
            return ("⚠️ No hay cuenta de depósito configurada. "
                   "Por favor contacta a tu ejecutivo para obtener los datos de pago.")
        
        texto = "💳 **Datos para tu depósito NetCash:**\n\n"
        texto += f"🏦 Banco: {cuenta.get('banco', 'N/A')}\n"
        texto += f"🔢 CLABE: {cuenta.get('clabe', 'N/A')}\n"
        texto += f"👤 Beneficiario: {cuenta.get('beneficiario', 'N/A')}"
        
        return texto


# Instancia global del servicio
cuenta_deposito_service = CuentaDepositoService()
