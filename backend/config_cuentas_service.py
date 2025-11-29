"""Servicio de configuración de cuentas bancarias NetCash

Maneja la configuración centralizada de las 3 cuentas involucradas:
- Concertadora: donde el cliente deposita
- Capital: para pagar al proveedor de ligas
- Comisión: para comisión MBco

Regla: Solo puede haber UNA cuenta activa por tipo.
"""

import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os

from netcash_models import CuentaBancaria, TipoCuenta

logger = logging.getLogger(__name__)

# Conexión MongoDB
mongo_url = os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'netcash_mbco')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

COLLECTION_NAME = 'config_cuentas_netcash'


class ConfigCuentasService:
    """Servicio para gestionar configuración de cuentas NetCash"""
    
    async def obtener_cuenta_activa(self, tipo: TipoCuenta) -> Optional[Dict]:
        """
        Obtiene la cuenta activa de un tipo específico.
        
        Args:
            tipo: Tipo de cuenta (concertadora, capital, comision)
        
        Returns:
            Dict con datos de la cuenta o None si no hay activa
        """
        try:
            cuenta = await db[COLLECTION_NAME].find_one(
                {"tipo": tipo.value, "activa": True},
                {"_id": 0}
            )
            
            if not cuenta:
                logger.warning(f"[ConfigCuentas] No hay cuenta activa de tipo {tipo.value}")
                return None
            
            logger.info(f"[ConfigCuentas] Cuenta activa {tipo.value}: {cuenta.get('banco')} - {cuenta.get('clabe')}")
            return cuenta
            
        except Exception as e:
            logger.error(f"[ConfigCuentas] Error obteniendo cuenta activa {tipo.value}: {str(e)}")
            return None
    
    async def listar_cuentas(self, tipo: Optional[TipoCuenta] = None, solo_activas: bool = False) -> List[Dict]:
        """
        Lista cuentas según filtros.
        
        Args:
            tipo: Filtrar por tipo de cuenta (opcional)
            solo_activas: Si True, solo muestra activas
        
        Returns:
            Lista de cuentas
        """
        try:
            filtro = {}
            if tipo:
                filtro["tipo"] = tipo.value
            if solo_activas:
                filtro["activa"] = True
            
            cuentas = await db[COLLECTION_NAME].find(
                filtro,
                {"_id": 0}
            ).sort("created_at", -1).to_list(100)
            
            logger.info(f"[ConfigCuentas] {len(cuentas)} cuentas encontradas (tipo={tipo}, activas={solo_activas})")
            return cuentas
            
        except Exception as e:
            logger.error(f"[ConfigCuentas] Error listando cuentas: {str(e)}")
            return []
    
    async def crear_cuenta(self, tipo: TipoCuenta, banco: str, clabe: str, 
                          beneficiario: str, activar_inmediatamente: bool = True,
                          notas: Optional[str] = None) -> Optional[Dict]:
        """
        Crea una nueva cuenta.
        
        Args:
            tipo: Tipo de cuenta
            banco: Nombre del banco
            clabe: CLABE (18 dígitos)
            beneficiario: Nombre del beneficiario
            activar_inmediatamente: Si True, desactiva otras del mismo tipo
            notas: Notas opcionales
        
        Returns:
            Cuenta creada o None si hay error
        """
        try:
            # Validar CLABE
            if not clabe or len(clabe) != 18 or not clabe.isdigit():
                raise ValueError("La CLABE debe tener exactamente 18 dígitos")
            
            # Si se debe activar, desactivar otras del mismo tipo
            if activar_inmediatamente:
                await db[COLLECTION_NAME].update_many(
                    {"tipo": tipo.value, "activa": True},
                    {"$set": {"activa": False, "updated_at": datetime.now(timezone.utc)}}
                )
                logger.info(f"[ConfigCuentas] Cuentas anteriores de tipo {tipo.value} desactivadas")
            
            # Crear nueva cuenta
            cuenta_id = f"cuenta-{tipo.value}-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
            nueva_cuenta = {
                "id": cuenta_id,
                "tipo": tipo.value,
                "banco": banco,
                "clabe": clabe,
                "beneficiario": beneficiario,
                "activa": activar_inmediatamente,
                "fecha_activacion": datetime.now(timezone.utc) if activar_inmediatamente else None,
                "notas": notas,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            await db[COLLECTION_NAME].insert_one(nueva_cuenta)
            logger.info(f"[ConfigCuentas] Cuenta {tipo.value} creada: {banco} - {clabe}")
            
            # Retornar sin _id
            if '_id' in nueva_cuenta:
                del nueva_cuenta['_id']
            return nueva_cuenta
            
        except Exception as e:
            logger.error(f"[ConfigCuentas] Error creando cuenta: {str(e)}")
            raise
    
    async def activar_cuenta(self, cuenta_id: str) -> bool:
        """
        Activa una cuenta específica y desactiva las demás del mismo tipo.
        
        Args:
            cuenta_id: ID de la cuenta a activar
        
        Returns:
            True si se activó correctamente
        """
        try:
            # Buscar la cuenta
            cuenta = await db[COLLECTION_NAME].find_one({"id": cuenta_id})
            if not cuenta:
                logger.error(f"[ConfigCuentas] Cuenta {cuenta_id} no encontrada")
                return False
            
            tipo = cuenta.get("tipo")
            
            # Desactivar todas del mismo tipo
            await db[COLLECTION_NAME].update_many(
                {"tipo": tipo, "activa": True},
                {"$set": {"activa": False, "updated_at": datetime.now(timezone.utc)}}
            )
            
            # Activar la seleccionada
            await db[COLLECTION_NAME].update_one(
                {"id": cuenta_id},
                {"$set": {
                    "activa": True,
                    "fecha_activacion": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            
            logger.info(f"[ConfigCuentas] Cuenta {cuenta_id} ({tipo}) activada")
            return True
            
        except Exception as e:
            logger.error(f"[ConfigCuentas] Error activando cuenta: {str(e)}")
            return False
    
    async def formatear_cuenta_para_mensaje(self, tipo: TipoCuenta) -> str:
        """
        Formatea los datos de una cuenta para mostrar en mensajes al cliente.
        
        Args:
            tipo: Tipo de cuenta
        
        Returns:
            Texto formateado
        """
        cuenta = await self.obtener_cuenta_activa(tipo)
        
        if not cuenta:
            return ("⚠️ No hay cuenta configurada. "
                   "Por favor contacta a tu ejecutivo.")
        
        texto = f"🏦 **Cuenta para tu depósito:**\n\n"
        texto += f"**Banco:** {cuenta.get('banco')}\n"
        texto += f"**CLABE:** {cuenta.get('clabe')}\n"
        texto += f"**Beneficiario:** {cuenta.get('beneficiario')}"
        
        return texto


# Instancia global del servicio
config_cuentas_service = ConfigCuentasService()
