"""Servicio para la colección de aprendizaje de PDFs NetCash

Este servicio registra casos donde el OCR falló o hubo intervención manual,
creando un dataset de entrenamiento para mejorar los parsers en el futuro.

Colección MongoDB: netcash_pdf_learning
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os
from uuid import uuid4
import hashlib

logger = logging.getLogger(__name__)

# Conexión MongoDB
mongo_url = os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'netcash_mbco')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

COLLECTION_NAME = 'netcash_pdf_learning'


class NetCashPDFLearningService:
    """Servicio para gestionar la colección de aprendizaje de PDFs"""
    
    async def registrar_caso_aprendizaje(
        self,
        solicitud: Dict,
        validado_por_ana: bool = False,
        estado_validacion_ana: str = None
    ) -> Optional[str]:
        """
        Registra un caso de aprendizaje en la colección
        
        Args:
            solicitud: Dict con todos los datos de la solicitud
            validado_por_ana: Si Ana ya validó esta operación
            estado_validacion_ana: "aprobado" o "rechazado"
        
        Returns:
            ID del registro creado o None si no se debe registrar
        """
        try:
            # Solo registrar casos relevantes para aprendizaje
            modo_captura = solicitud.get("modo_captura", "ocr_ok")
            origen_montos = solicitud.get("origen_montos", "robot")
            
            # Decidir si es caso de entrenamiento
            es_caso_entrenamiento = False
            
            if modo_captura == "manual_por_fallo_ocr":
                # Siempre es caso de entrenamiento si hubo fallo OCR
                es_caso_entrenamiento = True
            elif validado_por_ana and origen_montos == "manual_cliente":
                # También si Ana intervino corrigiendo datos manuales
                es_caso_entrenamiento = True
            
            if not es_caso_entrenamiento:
                logger.info(f"[PDF Learning] Solicitud {solicitud.get('id')} no requiere logging (OCR OK)")
                return None
            
            logger.info(f"[PDF Learning] Registrando caso de aprendizaje para solicitud {solicitud.get('id')}")
            
            # Generar ID único
            registro_id = f"learn_{uuid4().hex[:12]}"
            
            # Extraer datos básicos
            solicitud_id = solicitud.get("id")
            
            # Obtener cliente para IDMEX
            cliente_id = solicitud.get("cliente_id")
            cliente = await db.clientes.find_one({"id": cliente_id}, {"_id": 0})
            idmex = cliente.get("idmex") if cliente else None
            
            # Extraer validación OCR
            validacion_ocr = solicitud.get("validacion_ocr", {})
            banco_probable = validacion_ocr.get("banco_detectado", "DESCONOCIDO")
            
            # Extraer metadata de PDFs/comprobantes
            comprobantes = solicitud.get("comprobantes", [])
            metadata_pdfs = []
            
            for comp in comprobantes:
                archivo_url = comp.get("archivo_url")
                archivo_hash = comp.get("archivo_hash")
                
                # Calcular tamaño del archivo
                tamanio_bytes = 0
                tiene_texto = False
                
                if archivo_url and os.path.exists(archivo_url):
                    try:
                        tamanio_bytes = os.path.getsize(archivo_url)
                    except:
                        pass
                
                # Determinar si tiene texto (basado en validación)
                validacion_detalle = comp.get("validacion_detalle", {})
                razon = validacion_detalle.get("razon", "")
                tiene_texto = "pdf_sin_texto_legible" not in razon
                
                metadata_pdfs.append({
                    "nombre_archivo": comp.get("nombre_archivo"),
                    "hash_pdf": archivo_hash,
                    "tamanio_bytes": tamanio_bytes,
                    "tiene_texto": tiene_texto,
                    "es_valido": comp.get("es_valido", False)
                })
            
            # Extraer datos del robot (OCR)
            datos_robot = {}
            ocr_data = comprobantes[0].get("ocr_data", {}) if comprobantes else {}
            
            # Determinar estado de validación del robot
            estado_validacion_robot = "ok"
            if not validacion_ocr.get("es_confiable", True):
                motivo = validacion_ocr.get("motivo_fallo", "")
                if "sin texto legible" in motivo.lower():
                    estado_validacion_robot = "sin_texto_legible"
                elif "monto = 0" in motivo.lower() or "monto detectado = 0" in motivo.lower():
                    estado_validacion_robot = "monto_cero"
                elif "diferencia" in motivo.lower():
                    estado_validacion_robot = "diferencia_grande"
                else:
                    estado_validacion_robot = "otro_fallo"
            
            # Extraer monto y beneficiario detectado por robot
            monto_robot = None
            beneficiario_robot = None
            
            for comp in comprobantes:
                if comp.get("es_valido") and not comp.get("es_duplicado"):
                    monto_robot = comp.get("monto_detectado")
                    cuenta_detectada = comp.get("cuenta_detectada", {})
                    beneficiario_robot = cuenta_detectada.get("beneficiario")
                    break
            
            datos_robot = {
                "monto_detectado": monto_robot,
                "beneficiario_detectado": beneficiario_robot,
                "estado_validacion_robot": estado_validacion_robot,
                "banco_detectado": banco_probable,
                "es_confiable": validacion_ocr.get("es_confiable", True),
                "advertencias": validacion_ocr.get("advertencias", [])
            }
            
            # Extraer datos finales (reales)
            # Si hay captura manual, usar esos datos
            monto_total_real = solicitud.get("monto_total_declarado")
            beneficiario_real = solicitud.get("beneficiario_declarado")
            
            # Si no hay captura manual, usar datos del robot
            if not monto_total_real:
                monto_total_real = solicitud.get("total_comprobantes_validos")
            
            if not beneficiario_real:
                beneficiario_real = solicitud.get("beneficiario_reportado")
            
            datos_finales = {
                "monto_total_real": monto_total_real,
                "beneficiario_real": beneficiario_real,
                "id_beneficiario_frecuente": solicitud.get("id_beneficiario_frecuente"),
                "validado_por_ana": validado_por_ana,
                "estado_validacion_ana": estado_validacion_ana,  # "aprobado" o "rechazado"
                "num_ligas": solicitud.get("ligas_solicitadas") or solicitud.get("cantidad_ligas_reportada")
            }
            
            # Crear registro
            registro = {
                "id": registro_id,
                "id_operacion": solicitud_id,
                "idmex": idmex,
                "banco_probable": banco_probable,
                "fecha": datetime.now(timezone.utc),
                
                "modo_captura": modo_captura,
                "origen_montos": origen_montos,
                
                "metadata_pdf": {
                    "num_comprobantes": len(comprobantes),
                    "comprobantes": metadata_pdfs
                },
                
                "datos_robot": datos_robot,
                "datos_finales": datos_finales,
                
                "es_caso_entrenamiento": es_caso_entrenamiento,
                
                # Metadata adicional
                "cliente_id": cliente_id,
                "cliente_nombre": solicitud.get("cliente_nombre"),
                "folio_mbco": solicitud.get("folio_mbco"),
                "created_at": datetime.now(timezone.utc)
            }
            
            # Insertar en BD
            await db[COLLECTION_NAME].insert_one(registro)
            
            logger.info(f"[PDF Learning] ✅ Caso registrado: {registro_id}")
            logger.info(f"[PDF Learning]    Operación: {solicitud_id}")
            logger.info(f"[PDF Learning]    Modo captura: {modo_captura}")
            logger.info(f"[PDF Learning]    Banco: {banco_probable}")
            logger.info(f"[PDF Learning]    Estado validación robot: {estado_validacion_robot}")
            
            # Retornar sin _id
            if '_id' in registro:
                del registro['_id']
            
            return registro_id
            
        except Exception as e:
            logger.error(f"[PDF Learning] Error registrando caso de aprendizaje: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def obtener_casos_por_banco(
        self,
        banco: str,
        limite: int = 50
    ) -> List[Dict]:
        """
        Obtiene casos de aprendizaje filtrados por banco
        
        Args:
            banco: Nombre del banco (ALBO, ESPIRAL, etc)
            limite: Número máximo de resultados
        
        Returns:
            Lista de casos de aprendizaje
        """
        try:
            casos = await db[COLLECTION_NAME].find(
                {
                    "banco_probable": banco,
                    "es_caso_entrenamiento": True
                },
                {"_id": 0}
            ).sort("fecha", -1).limit(limite).to_list(limite)
            
            logger.info(f"[PDF Learning] Obtenidos {len(casos)} casos para banco {banco}")
            return casos
            
        except Exception as e:
            logger.error(f"[PDF Learning] Error obteniendo casos: {str(e)}")
            return []
    
    async def obtener_casos_sin_validar(self, limite: int = 20) -> List[Dict]:
        """
        Obtiene casos que aún no han sido validados por Ana
        
        Args:
            limite: Número máximo de resultados
        
        Returns:
            Lista de casos sin validar
        """
        try:
            casos = await db[COLLECTION_NAME].find(
                {
                    "datos_finales.validado_por_ana": False,
                    "es_caso_entrenamiento": True
                },
                {"_id": 0}
            ).sort("fecha", -1).limit(limite).to_list(limite)
            
            logger.info(f"[PDF Learning] Obtenidos {len(casos)} casos sin validar")
            return casos
            
        except Exception as e:
            logger.error(f"[PDF Learning] Error obteniendo casos sin validar: {str(e)}")
            return []
    
    async def estadisticas_aprendizaje(self) -> Dict:
        """
        Genera estadísticas de la colección de aprendizaje
        
        Returns:
            Dict con estadísticas
        """
        try:
            # Total de casos
            total_casos = await db[COLLECTION_NAME].count_documents({"es_caso_entrenamiento": True})
            
            # Por banco
            pipeline_banco = [
                {"$match": {"es_caso_entrenamiento": True}},
                {"$group": {
                    "_id": "$banco_probable",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}}
            ]
            por_banco = await db[COLLECTION_NAME].aggregate(pipeline_banco).to_list(None)
            
            # Por estado validación robot
            pipeline_robot = [
                {"$match": {"es_caso_entrenamiento": True}},
                {"$group": {
                    "_id": "$datos_robot.estado_validacion_robot",
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}}
            ]
            por_estado_robot = await db[COLLECTION_NAME].aggregate(pipeline_robot).to_list(None)
            
            # Casos validados vs sin validar
            validados = await db[COLLECTION_NAME].count_documents({
                "es_caso_entrenamiento": True,
                "datos_finales.validado_por_ana": True
            })
            sin_validar = total_casos - validados
            
            stats = {
                "total_casos": total_casos,
                "validados_por_ana": validados,
                "sin_validar": sin_validar,
                "por_banco": {item["_id"]: item["count"] for item in por_banco},
                "por_estado_validacion_robot": {item["_id"]: item["count"] for item in por_estado_robot}
            }
            
            logger.info(f"[PDF Learning] Estadísticas generadas: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"[PDF Learning] Error generando estadísticas: {str(e)}")
            return {}


# Instancia global del servicio
netcash_pdf_learning_service = NetCashPDFLearningService()
