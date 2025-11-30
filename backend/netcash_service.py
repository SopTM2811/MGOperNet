"""Motor Central NetCash - Lógica de Negocio Unificada

Este módulo contiene TODA la lógica de negocio para NetCash V1.
Todos los canales (Telegram, Email, Manual) delegan aquí.

Responsabilidades:
- Crear y actualizar solicitudes NetCash
- Aplicar REGLAS DURAS de validación
- Gestionar transiciones de estado
- Generar resúmenes para clientes
- Generar folios MBco secuenciales

Reglas Duras (Etapa 1):
1. Cliente válido (activo en catálogo)
2. Beneficiario válido (3+ palabras, sin números)
3. IDMEX válido (exactamente 10 dígitos)
4. Ligas válidas (número entero > 0)
5. Comprobante válido (CLABE completa + beneficiario de cuenta concertadora activa)
"""

import logging
import re
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os

from netcash_models import (
    SolicitudNetCash, SolicitudCreate, SolicitudUpdate, ResumenCliente,
    CanalOrigen, EstadoSolicitud, TipoCuenta, ValidacionCampo,
    ComprobanteDetalle, HistoricoEstado, CanalMetadata
)
from config_cuentas_service import config_cuentas_service
from validador_comprobantes_service import ValidadorComprobantes

logger = logging.getLogger(__name__)

# Conexión MongoDB
mongo_url = os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'netcash_mbco')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

COLLECTION_NAME = 'solicitudes_netcash'


class NetCashService:
    """Servicio central para gestión de solicitudes NetCash"""
    
    def __init__(self):
        self.validador_comprobantes = ValidadorComprobantes()
    
    # ==================== CREACIÓN Y ACTUALIZACIÓN ====================
    
    async def crear_solicitud(self, datos: SolicitudCreate) -> Optional[Dict]:
        """
        Crea una nueva solicitud NetCash en estado BORRADOR.
        
        Args:
            datos: Datos básicos de la solicitud
        
        Returns:
            Solicitud creada o None si hay error
        """
        try:
            logger.info(f"[NetCash] ========== CREAR SOLICITUD ==========")
            logger.info(f"[NetCash] Canal: {datos.canal}")
            logger.info(f"[NetCash] Cliente: {datos.cliente_nombre} ({datos.cliente_id})")
            
            # Generar ID interno
            timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
            solicitud_id = f"nc-{timestamp}"
            
            # Crear solicitud base
            solicitud = {
                "id": solicitud_id,
                "folio_mbco": None,  # Se genera al llegar a lista_para_mbc
                "canal": datos.canal.value,
                "cliente_id": datos.cliente_id,
                "cliente_nombre": datos.cliente_nombre,
                "beneficiario_reportado": datos.beneficiario_reportado,
                "idmex_reportado": datos.idmex_reportado,
                "cantidad_ligas_reportada": datos.cantidad_ligas_reportada,
                "comprobantes": [],
                "estado": EstadoSolicitud.BORRADOR.value,
                "validacion": {
                    "cliente": {"valido": False, "razon": "No validado"},
                    "beneficiario": {"valido": False, "razon": "No validado"},
                    "idmex": {"valido": False, "razon": "No validado"},
                    "ligas": {"valido": False, "razon": "No validado"},
                    "comprobante": {"valido": False, "razon": "No validado"}
                },
                "monto_depositado_cliente": None,
                "porcentaje_comision_cliente": None,
                "monto_comision_mbco": None,
                "monto_capital_proveedor": None,
                "canal_metadata": datos.canal_metadata.dict() if datos.canal_metadata else {},
                "legacy": False,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "estado_historico": [
                    {
                        "estado": EstadoSolicitud.BORRADOR.value,
                        "en": datetime.now(timezone.utc),
                        "por": "sistema",
                        "notas": f"Creada desde {datos.canal.value}"
                    }
                ]
            }
            
            await db[COLLECTION_NAME].insert_one(solicitud)
            logger.info(f"[NetCash] ✅ Solicitud creada: {solicitud_id}")
            
            # Retornar sin _id
            if '_id' in solicitud:
                del solicitud['_id']
            
            return solicitud
            
        except Exception as e:
            logger.error(f"[NetCash] ❌ Error creando solicitud: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def actualizar_solicitud(self, solicitud_id: str, datos: SolicitudUpdate) -> bool:
        """
        Actualiza datos de una solicitud existente.
        
        Args:
            solicitud_id: ID de la solicitud
            datos: Datos a actualizar
        
        Returns:
            True si se actualizó correctamente
        """
        try:
            update_data = {}
            if datos.beneficiario_reportado is not None:
                update_data["beneficiario_reportado"] = datos.beneficiario_reportado
            if datos.idmex_reportado is not None:
                update_data["idmex_reportado"] = datos.idmex_reportado
            if datos.cantidad_ligas_reportada is not None:
                update_data["cantidad_ligas_reportada"] = datos.cantidad_ligas_reportada
            if datos.monto_depositado_cliente is not None:
                update_data["monto_depositado_cliente"] = datos.monto_depositado_cliente
            
            if not update_data:
                return True
            
            update_data["updated_at"] = datetime.now(timezone.utc)
            
            result = await db[COLLECTION_NAME].update_one(
                {"id": solicitud_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"[NetCash] Solicitud {solicitud_id} actualizada")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"[NetCash] Error actualizando solicitud: {str(e)}")
            return False
    
    async def agregar_comprobante(self, solicitud_id: str, archivo_url: str, 
                                 nombre_archivo: str) -> bool:
        """
        Agrega un comprobante a una solicitud y lo valida.
        
        Args:
            solicitud_id: ID de la solicitud
            archivo_url: Ruta del archivo
            nombre_archivo: Nombre original del archivo
        
        Returns:
            True si se agregó correctamente
        """
        try:
            logger.info(f"[NetCash] Agregando comprobante a {solicitud_id}")
            
            # Validar comprobante contra cuenta concertadora activa
            cuenta_activa = await config_cuentas_service.obtener_cuenta_activa(TipoCuenta.CONCERTADORA)
            
            if not cuenta_activa:
                logger.error(f"[NetCash] No hay cuenta concertadora activa")
                return False
            
            # Determinar MIME type
            mime_type = "application/pdf" if archivo_url.endswith(".pdf") else "image/jpeg"
            
            # LOG EXPLÍCITO - Para correlacionar con logs del validador
            logger.info(f"[NC TELEGRAM] Llamando a validar_comprobante() para archivo={nombre_archivo}")
            logger.info(f"[NC TELEGRAM] Cuenta activa: banco={cuenta_activa.get('banco')} clabe={cuenta_activa.get('clabe')} beneficiario={cuenta_activa.get('beneficiario')}")
            
            # Validar comprobante
            es_valido, razon = self.validador_comprobantes.validar_comprobante(
                archivo_url, mime_type, cuenta_activa
            )
            
            # Extraer texto para detectar datos
            texto = self.validador_comprobantes.extraer_texto_comprobante(archivo_url, mime_type)
            
            # Intentar extraer CLABE y beneficiario del comprobante
            clabes_detectadas = self._extraer_clabes_del_texto(texto)
            cuenta_detectada = None
            monto_detectado = None
            
            if clabes_detectadas:
                cuenta_detectada = {
                    "clabe": clabes_detectadas[0] if clabes_detectadas else None
                }
            
            # Intentar extraer monto
            monto_detectado = self._extraer_monto_del_texto(texto)
            
            # Crear detalle del comprobante
            comprobante_detalle = {
                "archivo_url": archivo_url,
                "nombre_archivo": nombre_archivo,
                "es_valido": es_valido,
                "validacion_detalle": {
                    "razon": razon,
                    "cuenta_activa_esperada": cuenta_activa,
                    "texto_extraido_chars": len(texto) if texto else 0
                },
                "cuenta_detectada": cuenta_detectada,
                "monto_detectado": monto_detectado
            }
            
            # Agregar a la solicitud
            result = await db[COLLECTION_NAME].update_one(
                {"id": solicitud_id},
                {
                    "$push": {"comprobantes": comprobante_detalle},
                    "$set": {
                        "updated_at": datetime.now(timezone.utc),
                        "monto_depositado_cliente": monto_detectado  # Actualizar monto si se detect\u00f3
                    }
                }
            )
            
            logger.info(f"[NetCash] Comprobante agregado: válido={es_valido}, monto={monto_detectado}")
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"[NetCash] Error agregando comprobante: {str(e)}")
            return False
    
    # ==================== VALIDACIONES (REGLAS DURAS) ====================
    
    async def validar_solicitud_completa(self, solicitud_id: str) -> Tuple[bool, Dict]:
        """
        Aplica TODAS las reglas duras a una solicitud.
        
        Este es el corazón del motor NetCash. Valida:
        1. Cliente activo
        2. Beneficiario (3+ palabras, sin números)
        3. IDMEX (10 dígitos exactos)
        4. Ligas (> 0)
        5. Comprobante (CLABE completa + beneficiario de cuenta activa)
        
        Args:
            solicitud_id: ID de la solicitud
        
        Returns:
            Tupla (todas_validas: bool, validaciones: dict)
        """
        logger.info(f"[NetCash] ========== VALIDAR SOLICITUD COMPLETA ==========")
        logger.info(f"[NetCash] Solicitud: {solicitud_id}")
        
        # Obtener solicitud
        solicitud = await db[COLLECTION_NAME].find_one({"id": solicitud_id}, {"_id": 0})
        if not solicitud:
            logger.error(f"[NetCash] Solicitud {solicitud_id} no encontrada")
            return False, {}
        
        validaciones = {}
        
        # 1. Validar cliente
        validaciones["cliente"] = await self._validar_cliente(
            solicitud.get("cliente_id")
        )
        
        # 2. Validar beneficiario
        validaciones["beneficiario"] = self._validar_beneficiario(
            solicitud.get("beneficiario_reportado")
        )
        
        # 3. Validar IDMEX
        validaciones["idmex"] = self._validar_idmex(
            solicitud.get("idmex_reportado")
        )
        
        # 4. Validar ligas
        validaciones["ligas"] = self._validar_ligas(
            solicitud.get("cantidad_ligas_reportada")
        )
        
        # 5. Validar comprobante
        validaciones["comprobante"] = self._validar_comprobantes_solicitud(
            solicitud.get("comprobantes", [])
        )
        
        # Actualizar validaciones en BD
        await db[COLLECTION_NAME].update_one(
            {"id": solicitud_id},
            {"$set": {
                "validacion": validaciones,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        # Verificar si TODAS son válidas
        todas_validas = all(v.get("valido", False) for v in validaciones.values())
        
        logger.info(f"[NetCash] Resultado validación: {'✅ TODAS VÁLIDAS' if todas_validas else '❌ HAY ERRORES'}")
        for campo, val in validaciones.items():
            status = "✅" if val.get("valido") else "❌"
            logger.info(f"[NetCash]   {status} {campo}: {val.get('razon')}")
        
        return todas_validas, validaciones
    
    async def _validar_cliente(self, cliente_id: str) -> Dict:
        """Valida que el cliente exista y esté activo"""
        try:
            cliente = await db.clientes.find_one({"id": cliente_id}, {"_id": 0})
            
            if not cliente:
                return {"valido": False, "razon": "Cliente no encontrado en catálogo"}
            
            if cliente.get("estado") != "activo":
                return {"valido": False, "razon": f"Cliente no está activo (estado: {cliente.get('estado')})"}
            
            return {"valido": True, "razon": "Cliente activo encontrado"}
            
        except Exception as e:
            logger.error(f"[NetCash] Error validando cliente: {str(e)}")
            return {"valido": False, "razon": f"Error: {str(e)}"}
    
    def _validar_beneficiario(self, beneficiario: Optional[str]) -> Dict:
        """
        Valida beneficiario: mínimo 3 palabras, sin números.
        Ejemplo válido: DANIEL FELIPE GALVEZ MAGALLON
        """
        if not beneficiario or not beneficiario.strip():
            return {"valido": False, "razon": "Beneficiario no proporcionado"}
        
        # Limpiar y contar palabras (solo letras)
        palabras = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]+", beneficiario)
        
        if len(palabras) < 3:
            return {
                "valido": False,
                "razon": f"Beneficiario debe tener mínimo 3 palabras (nombre + 2 apellidos). Detectadas: {len(palabras)}"
            }
        
        # Verificar que no tenga números
        if re.search(r'\d', beneficiario):
            return {"valido": False, "razon": "Beneficiario no debe contener números"}
        
        return {"valido": True, "razon": f"Beneficiario válido ({len(palabras)} palabras)"}
    
    def _validar_idmex(self, idmex: Optional[str]) -> Dict:
        """Valida IDMEX: exactamente 10 dígitos"""
        if not idmex:
            return {"valido": False, "razon": "IDMEX no proporcionado"}
        
        # Limpiar espacios
        idmex_limpio = idmex.strip()
        
        # Verificar que tenga exactamente 10 dígitos
        if not re.match(r'^[0-9]{10}$', idmex_limpio):
            longitud = len(idmex_limpio) if idmex_limpio.isdigit() else "no numérico"
            return {
                "valido": False,
                "razon": f"IDMEX debe tener exactamente 10 dígitos. Recibido: {longitud}"
            }
        
        return {"valido": True, "razon": "IDMEX válido (10 dígitos)"}
    
    def _validar_ligas(self, cantidad: Optional[int]) -> Dict:
        """Valida cantidad de ligas: debe ser entero > 0"""
        if cantidad is None:
            return {"valido": False, "razon": "Cantidad de ligas no proporcionada"}
        
        try:
            cantidad_int = int(cantidad)
            if cantidad_int <= 0:
                return {"valido": False, "razon": f"Cantidad de ligas debe ser mayor a 0. Recibido: {cantidad_int}"}
            
            return {"valido": True, "razon": f"Cantidad válida: {cantidad_int} ligas"}
            
        except (ValueError, TypeError):
            return {"valido": False, "razon": f"Cantidad de ligas debe ser un número entero. Recibido: {cantidad}"}
    
    def _validar_comprobantes_solicitud(self, comprobantes: List[Dict]) -> Dict:
        """Valida que haya al menos un comprobante válido"""
        if not comprobantes or len(comprobantes) == 0:
            return {"valido": False, "razon": "No hay comprobantes adjuntos"}
        
        comprobantes_validos = [c for c in comprobantes if c.get("es_valido", False)]
        
        if len(comprobantes_validos) == 0:
            razones = [c.get("validacion_detalle", {}).get("razon", "Sin razón") 
                      for c in comprobantes]
            return {
                "valido": False,
                "razon": f"Ningún comprobante es válido. Razones: {'; '.join(razones)}"
            }
        
        return {
            "valido": True,
            "razon": f"{len(comprobantes_validos)} comprobante(s) válido(s)"
        }
    
    # ==================== GESTIÓN DE ESTADOS ====================
    
    async def cambiar_estado(self, solicitud_id: str, nuevo_estado: EstadoSolicitud,
                            notas: Optional[str] = None) -> bool:
        """
        Cambia el estado de una solicitud.
        Si el nuevo estado es LISTA_PARA_MBC y no tiene folio, lo genera.
        
        Args:
            solicitud_id: ID de la solicitud
            nuevo_estado: Nuevo estado
            notas: Notas opcionales sobre el cambio
        
        Returns:
            True si se cambió correctamente
        """
        try:
            solicitud = await db[COLLECTION_NAME].find_one({"id": solicitud_id})
            if not solicitud:
                logger.error(f"[NetCash] Solicitud {solicitud_id} no encontrada")
                return False
            
            estado_actual = solicitud.get("estado")
            
            logger.info(f"[NetCash] Cambio de estado: {estado_actual} -> {nuevo_estado.value}")
            
            # Preparar actualización
            update_data = {
                "estado": nuevo_estado.value,
                "updated_at": datetime.now(timezone.utc)
            }
            
            # Si pasa a LISTA_PARA_MBC y no tiene folio, generar
            if nuevo_estado == EstadoSolicitud.LISTA_PARA_MBC and not solicitud.get("folio_mbco"):
                folio = await self._generar_folio_mbco()
                update_data["folio_mbco"] = folio
                logger.info(f"[NetCash] Folio generado: {folio}")
            
            # Agregar al histórico
            historico_entry = {
                "estado": nuevo_estado.value,
                "en": datetime.now(timezone.utc),
                "por": "sistema",
                "notas": notas or f"Cambio automático a {nuevo_estado.value}"
            }
            
            await db[COLLECTION_NAME].update_one(
                {"id": solicitud_id},
                {
                    "$set": update_data,
                    "$push": {"estado_historico": historico_entry}
                }
            )
            
            logger.info(f"[NetCash] ✅ Estado actualizado a {nuevo_estado.value}")
            return True
            
        except Exception as e:
            logger.error(f"[NetCash] Error cambiando estado: {str(e)}")
            return False
    
    async def procesar_solicitud_automaticamente(self, solicitud_id: str) -> Tuple[bool, str]:
        """
        Procesa una solicitud automáticamente:
        1. Valida todos los campos
        2. Si TODO está bien -> Calcula totales y comisiones, guarda en BD, LISTA_PARA_MBC
        3. Si algo falla -> RECHAZADA
        
        Args:
            solicitud_id: ID de la solicitud
        
        Returns:
            Tupla (exitoso, mensaje)
        """
        logger.info(f"[NetCash] Procesando solicitud automáticamente: {solicitud_id}")
        
        # Validar completamente
        todas_validas, validaciones = await self.validar_solicitud_completa(solicitud_id)
        
        if todas_validas:
            # Obtener solicitud para calcular totales
            solicitud = await db[COLLECTION_NAME].find_one({"id": solicitud_id}, {"_id": 0})
            
            # Calcular suma de todos los comprobantes válidos
            comprobantes = solicitud.get("comprobantes", [])
            comprobantes_validos = [c for c in comprobantes if c.get("es_valido", False)]
            comprobantes_invalidos = [c for c in comprobantes if not c.get("es_valido", False)]
            
            total_comprobantes_validos = 0.0
            for comp in comprobantes_validos:
                monto = comp.get("monto_detectado")
                if monto and monto > 0:
                    total_comprobantes_validos += monto
            
            # Calcular comisiones
            porcentaje_comision_cliente = 1.00  # 1.00%
            comision_cliente = total_comprobantes_validos * (porcentaje_comision_cliente / 100)
            monto_ligas = total_comprobantes_validos - comision_cliente
            
            # Obtener cuenta NetCash utilizada
            cuenta_activa = await config_cuentas_service.obtener_cuenta_activa(TipoCuenta.CONCERTADORA)
            cuenta_netcash_info = None
            if cuenta_activa:
                cuenta_netcash_info = {
                    "banco": cuenta_activa.get("banco"),
                    "clabe": cuenta_activa.get("clabe"),
                    "beneficiario": cuenta_activa.get("beneficiario")
                }
            
            # Actualizar solicitud con todos los datos completos
            update_data = {
                "total_comprobantes_validos": total_comprobantes_validos,
                "num_comprobantes_validos": len(comprobantes_validos),
                "num_comprobantes_invalidos": len(comprobantes_invalidos),
                "porcentaje_comision_cliente": porcentaje_comision_cliente,
                "comision_cliente": comision_cliente,
                "monto_ligas": monto_ligas,
                "cuenta_netcash_usada": cuenta_netcash_info,
                "updated_at": datetime.now(timezone.utc)
            }
            
            await db[COLLECTION_NAME].update_one(
                {"id": solicitud_id},
                {"$set": update_data}
            )
            
            logger.info(f"[NetCash] Totales calculados y guardados: total=${total_comprobantes_validos:,.2f}, comisión=${comision_cliente:,.2f}, monto_ligas=${monto_ligas:,.2f}")
            
            # TODO OK -> LISTA_PARA_MBC
            await self.cambiar_estado(
                solicitud_id,
                EstadoSolicitud.LISTA_PARA_MBC,
                "Todas las validaciones pasaron"
            )
            return True, "Solicitud válida y lista para proceso MBco"
        else:
            # Hay errores -> RECHAZADA
            errores = [f"{campo}: {val.get('razon')}" 
                      for campo, val in validaciones.items() 
                      if not val.get("valido")]
            
            await self.cambiar_estado(
                solicitud_id,
                EstadoSolicitud.RECHAZADA,
                f"Validaciones fallidas: {'; '.join(errores)}"
            )
            return False, f"Solicitud rechazada: {'; '.join(errores)}"
    
    # ==================== GENERACIÓN DE RESÚMENES ====================
    
    async def generar_resumen_cliente(self, solicitud_id: str) -> Optional[ResumenCliente]:
        """
        Genera un resumen amigable para mostrar al cliente.
        
        Este es el formato estándar que usan todos los canales.
        
        Returns:
            ResumenCliente con los 3 bloques:
            1. "Esto es lo que entendí"
            2. "Esto falta o está mal"
            3. "Qué sigue"
        """
        try:
            solicitud = await db[COLLECTION_NAME].find_one({"id": solicitud_id}, {"_id": 0})
            if not solicitud:
                return None
            
            validacion = solicitud.get("validacion", {})
            
            # Bloque 1: Campos detectados y cuáles son válidos
            campos_detectados = {
                "beneficiario": solicitud.get("beneficiario_reportado", "No detectado"),
                "idmex": solicitud.get("idmex_reportado", "No detectado"),
                "ligas": solicitud.get("cantidad_ligas_reportada", "No detectado"),
                "comprobantes": len(solicitud.get("comprobantes", []))
            }
            
            campos_validos = [campo for campo, val in validacion.items() 
                            if val.get("valido", False)]
            
            # Bloque 2: Campos faltantes e inválidos
            campos_faltantes = []
            campos_invalidos = []
            
            for campo, val in validacion.items():
                if not val.get("valido", False):
                    razon = val.get("razon", "Sin razón")
                    if "no proporcionado" in razon.lower() or "no detectado" in razon.lower():
                        campos_faltantes.append(campo)
                    else:
                        campos_invalidos.append({"campo": campo, "razon": razon})
            
            # Bloque 3: Mensaje de siguiente paso
            estado = solicitud.get("estado")
            if estado == EstadoSolicitud.LISTA_PARA_MBC.value:
                mensaje_siguiente = f"✅ Tu solicitud está registrada y lista para proceso. Folio: {solicitud.get('folio_mbco')}"
            elif estado == EstadoSolicitud.RECHAZADA.value:
                mensaje_siguiente = "❌ Tu solicitud tiene errores. Por favor corrige lo indicado y vuelve a enviar."
            else:
                mensaje_siguiente = "Estamos procesando tu información. Te avisaremos del resultado."
            
            # Obtener cuenta concertadora
            cuenta = await config_cuentas_service.obtener_cuenta_activa(TipoCuenta.CONCERTADORA)
            cuenta_info = None
            if cuenta:
                cuenta_info = {
                    "banco": cuenta.get("banco"),
                    "clabe": cuenta.get("clabe"),
                    "beneficiario": cuenta.get("beneficiario")
                }
            
            resumen = ResumenCliente(
                solicitud_id=solicitud_id,
                folio_mbco=solicitud.get("folio_mbco"),
                estado=EstadoSolicitud(estado),
                campos_detectados=campos_detectados,
                campos_validos=campos_validos,
                campos_faltantes=campos_faltantes,
                campos_invalidos=campos_invalidos,
                mensaje_siguiente_paso=mensaje_siguiente,
                cuenta_concertadora=cuenta_info
            )
            
            return resumen
            
        except Exception as e:
            logger.error(f"[NetCash] Error generando resumen: {str(e)}")
            return None
    
    # ==================== UTILIDADES ====================
    
    async def _generar_folio_mbco(self) -> str:
        """
        Genera un folio NetCash secuencial (NC-000001, NC-000002, ...)
        
        Returns:
            Folio en formato NC-XXXXXX
        """
        try:
            # Buscar el último folio generado
            ultima_solicitud = await db[COLLECTION_NAME].find_one(
                {"folio_mbco": {"$exists": True, "$ne": None}},
                {"folio_mbco": 1},
                sort=[("folio_mbco", -1)]
            )
            
            if ultima_solicitud and ultima_solicitud.get("folio_mbco"):
                ultimo_folio = ultima_solicitud.get("folio_mbco")
                # Extraer número (NC-000048 -> 48)
                numero = int(ultimo_folio.split("-")[1])
                nuevo_numero = numero + 1
            else:
                # Primera solicitud
                nuevo_numero = 1
            
            folio = f"NC-{nuevo_numero:06d}"
            logger.info(f"[NetCash] Folio generado: {folio}")
            return folio
            
        except Exception as e:
            logger.error(f"[NetCash] Error generando folio: {str(e)}")
            # Fallback: usar timestamp
            timestamp = int(datetime.now(timezone.utc).timestamp())
            return f"NC-{timestamp}"
    
    def _extraer_clabes_del_texto(self, texto: str) -> List[str]:
        """Extrae CLABEs (18 dígitos) del texto"""
        if not texto:
            return []
        clabes = re.findall(r'\b(\d{18})\b', texto)
        return clabes
    
    def _extraer_monto_del_texto(self, texto: str) -> Optional[float]:
        """Intenta extraer un monto del texto del comprobante"""
        if not texto:
            return None
        
        # Buscar patrones como: $10,000.00, $10000, etc.
        patrones = [
            r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'(?:monto|importe|total)[\s:]+\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        ]
        
        for patron in patrones:
            matches = re.findall(patron, texto, re.IGNORECASE)
            if matches:
                try:
                    # Limpiar formato y convertir
                    monto_str = matches[0].replace(',', '')
                    return float(monto_str)
                except:
                    continue
        
        return None
    
    # ==================== CONSULTAS ====================
    
    async def obtener_solicitud(self, solicitud_id: str) -> Optional[Dict]:
        """Obtiene una solicitud por ID"""
        solicitud = await db[COLLECTION_NAME].find_one({"id": solicitud_id}, {"_id": 0})
        return solicitud
    
    async def listar_solicitudes_cliente(self, cliente_id: str, 
                                        solo_validas: bool = False,
                                        limite: int = 20) -> List[Dict]:
        """
        Lista solicitudes de un cliente.
        
        Args:
            cliente_id: ID del cliente
            solo_validas: Si True, solo muestra las que están en lista_para_mbc
            limite: Número máximo de resultados
        
        Returns:
            Lista de solicitudes
        """
        try:
            filtro = {"cliente_id": cliente_id, "legacy": False}
            
            if solo_validas:
                filtro["estado"] = EstadoSolicitud.LISTA_PARA_MBC.value
            
            solicitudes = await db[COLLECTION_NAME].find(
                filtro,
                {"_id": 0}
            ).sort("created_at", -1).limit(limite).to_list(limite)
            
            return solicitudes
            
        except Exception as e:
            logger.error(f"[NetCash] Error listando solicitudes: {str(e)}")
            return []


# Instancia global del servicio
netcash_service = NetCashService()
