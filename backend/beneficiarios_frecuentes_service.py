"""Servicio para gestionar beneficiarios frecuentes de NetCash

Este servicio maneja el CRUD de beneficiarios frecuentes para clientes NetCash.
Los beneficiarios frecuentes permiten al usuario seleccionar rápidamente datos
guardados de beneficiarios utilizados previamente.

Colección MongoDB: netcash_beneficiarios_frecuentes
"""

import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os
from uuid import uuid4

logger = logging.getLogger(__name__)

# Conexión MongoDB
mongo_url = os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'netcash_mbco')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

COLLECTION_NAME = 'netcash_beneficiarios_frecuentes'


class BeneficiariosFrecuentesService:
    """Servicio para gestionar beneficiarios frecuentes"""
    
    async def obtener_beneficiarios_frecuentes(
        self, 
        idmex: str, 
        limite: int = 3
    ) -> List[Dict]:
        """
        Obtiene los beneficiarios frecuentes de un cliente por IDMEX
        
        Args:
            idmex: IDMEX del cliente
            limite: Número máximo de beneficiarios a retornar (default: 3)
        
        Returns:
            Lista de beneficiarios frecuentes ordenados por uso reciente
        """
        try:
            logger.info(f"[BenefFrec] Buscando beneficiarios frecuentes para IDMEX: {idmex}")
            
            beneficiarios = await db[COLLECTION_NAME].find(
                {
                    "idmex": idmex,
                    "activo": True
                },
                {"_id": 0}
            ).sort("ultima_vez_usado", -1).limit(limite).to_list(limite)
            
            logger.info(f"[BenefFrec] Encontrados {len(beneficiarios)} beneficiarios frecuentes")
            return beneficiarios
            
        except Exception as e:
            logger.error(f"[BenefFrec] Error obteniendo beneficiarios frecuentes: {str(e)}")
            return []
    
    async def crear_beneficiario_frecuente(
        self,
        idmex: str,
        cliente_id: str,
        nombre_beneficiario: str,
        idmex_beneficiario: Optional[str] = None,
        clabe: Optional[str] = None,
        banco: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Crea un nuevo beneficiario frecuente
        
        Args:
            idmex: IDMEX del cliente (para asociar al cliente)
            cliente_id: ID interno del cliente
            nombre_beneficiario: Nombre completo del beneficiario
            idmex_beneficiario: IDMEX del beneficiario (persona física)
            clabe: CLABE del beneficiario (opcional, legacy)
            banco: Nombre del banco (opcional)
        
        Returns:
            Beneficiario creado o None si hay error
        """
        try:
            # Verificar si ya existe este beneficiario
            existing = await db[COLLECTION_NAME].find_one(
                {
                    "idmex": idmex,
                    "nombre_beneficiario": nombre_beneficiario.upper(),
                    "activo": True
                },
                {"_id": 0}
            )
            
            if existing:
                logger.info(f"[BenefFrec] Beneficiario ya existe: {nombre_beneficiario}")
                # Actualizar última vez usado
                await self.actualizar_ultima_vez_usado(existing['id'])
                return existing
            
            # Generar ID único
            beneficiario_id = f"bf_{uuid4().hex[:8]}"
            
            # Calcular terminación de CLABE si existe
            terminacion = clabe[-4:] if clabe and len(clabe) >= 4 else None
            
            # Crear alias para mostrar (solo nombre, sin CLABE)
            alias_mostrar = f"{nombre_beneficiario}"
            
            beneficiario = {
                "id": beneficiario_id,
                "cliente_id": cliente_id,
                "idmex": idmex,  # IDMEX del cliente
                "idmex_beneficiario": idmex_beneficiario,  # IDMEX del beneficiario
                "nombre_beneficiario": nombre_beneficiario.upper(),
                "alias_mostrar": alias_mostrar,
                "clabe": clabe,
                "terminacion": terminacion,
                "banco": banco,
                "fecha_creacion": datetime.now(timezone.utc),
                "ultima_vez_usado": datetime.now(timezone.utc),
                "activo": True
            }
            
            await db[COLLECTION_NAME].insert_one(beneficiario)
            logger.info(f"[BenefFrec] ✅ Beneficiario frecuente creado: {beneficiario_id}")
            
            # Retornar sin _id
            if '_id' in beneficiario:
                del beneficiario['_id']
            
            return beneficiario
            
        except Exception as e:
            logger.error(f"[BenefFrec] Error creando beneficiario frecuente: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def actualizar_ultima_vez_usado(self, beneficiario_id: str) -> bool:
        """
        Actualiza la fecha de última vez usado de un beneficiario
        
        Args:
            beneficiario_id: ID del beneficiario
        
        Returns:
            True si se actualizó correctamente
        """
        try:
            result = await db[COLLECTION_NAME].update_one(
                {"id": beneficiario_id},
                {"$set": {"ultima_vez_usado": datetime.now(timezone.utc)}}
            )
            
            if result.modified_count > 0:
                logger.info(f"[BenefFrec] Actualizada última vez usado para: {beneficiario_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"[BenefFrec] Error actualizando última vez usado: {str(e)}")
            return False
    
    async def desactivar_beneficiario(self, beneficiario_id: str) -> bool:
        """
        Desactiva un beneficiario frecuente (no lo elimina físicamente)
        
        Args:
            beneficiario_id: ID del beneficiario
        
        Returns:
            True si se desactivó correctamente
        """
        try:
            result = await db[COLLECTION_NAME].update_one(
                {"id": beneficiario_id},
                {"$set": {"activo": False}}
            )
            
            if result.modified_count > 0:
                logger.info(f"[BenefFrec] Beneficiario desactivado: {beneficiario_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"[BenefFrec] Error desactivando beneficiario: {str(e)}")
            return False


# Instancia global del servicio
beneficiarios_frecuentes_service = BeneficiariosFrecuentesService()
