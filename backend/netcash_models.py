"""Modelos de datos para NetCash V1

Estos modelos definen la estructura unificada para solicitudes NetCash,
independientemente del canal de entrada (Telegram, Email, Manual).
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class CanalOrigen(str, Enum):
    """Canales de entrada para solicitudes NetCash"""
    TELEGRAM = "telegram"
    EMAIL = "email"
    MANUAL = "manual"


class EstadoSolicitud(str, Enum):
    """Estados del ciclo de vida de una solicitud NetCash"""
    BORRADOR = "borrador"  # Info recibida pero incompleta
    PENDIENTE_VALIDACION = "pendiente_validacion"  # Listo para validar
    RECHAZADA = "rechazada"  # No pasó alguna regla dura
    DEMO = "demo"  # Operación de prueba/demo (permite reutilizar comprobantes)
    CANCELADA = "cancelada"  # Operación cancelada (permite reutilizar comprobantes)
    LISTA_PARA_MBC = "lista_para_mbc"  # Válida y lista para proceso
    ORDEN_INTERNA_GENERADA = "orden_interna_generada"  # Ana asignó folio, orden creada
    ENVIADO_A_TESORERIA = "enviado_a_tesoreria"  # Incluido en lote enviado a Tesorería
    EN_PROCESO_MBC = "en_proceso_mbc"  # MBco procesando la operación
    # Futuros estados (Etapa 2+)
    LAYOUT_GENERADO = "layout_generado"
    LIGAS_SOLICITADAS = "ligas_solicitadas"
    LIGAS_ENVIADAS = "ligas_enviadas"


class TipoCuenta(str, Enum):
    """Tipos de cuentas bancarias en el flujo NetCash"""
    CONCERTADORA = "concertadora"  # Donde el cliente deposita
    CAPITAL = "capital"  # Para pagar al proveedor de ligas
    COMISION = "comision"  # Para comisión MBco


class ValidacionCampo(BaseModel):
    """Resultado de validación de un campo individual"""
    valido: bool
    razon: str = ""
    detalles: Optional[Dict[str, Any]] = None


class ComprobanteDetalle(BaseModel):
    """Detalle de un comprobante procesado"""
    archivo_url: str
    nombre_archivo: str
    es_valido: bool = False
    validacion_detalle: Optional[Dict[str, Any]] = None
    cuenta_detectada: Optional[Dict[str, str]] = None  # banco, clabe, beneficiario
    monto_detectado: Optional[float] = None


class CanalMetadata(BaseModel):
    """Metadata específica del canal de origen"""
    telegram_chat_id: Optional[str] = None
    telegram_message_id: Optional[str] = None
    email_message_id: Optional[str] = None
    email_thread_id: Optional[str] = None
    usuario_captura: Optional[str] = None  # Para canal manual


class HistoricoEstado(BaseModel):
    """Registro de cambio de estado"""
    estado: EstadoSolicitud
    en: datetime
    por: str = "sistema"  # sistema, usuario, etc.
    notas: Optional[str] = None


class SolicitudNetCash(BaseModel):
    """Modelo principal de una solicitud NetCash
    
    Este modelo unifica todas las solicitudes NetCash independientemente
    del canal de entrada. Todas las validaciones y el flujo de estados
    se aplican de manera consistente.
    """
    
    # Identificadores
    id: str = Field(..., description="ID interno (ej: nc-2025-000001)")
    folio_mbco: Optional[str] = Field(None, description="Folio NetCash (ej: NC-000048), se genera al llegar a lista_para_mbc")
    
    # Origen
    canal: CanalOrigen
    cliente_id: str
    cliente_nombre: str
    
    # Datos de la solicitud (reportados por el cliente)
    beneficiario_reportado: Optional[str] = None
    idmex_reportado: Optional[str] = None
    cantidad_ligas_reportada: Optional[int] = None
    
    # Comprobantes
    comprobantes: List[ComprobanteDetalle] = []
    
    # Estado y validación
    estado: EstadoSolicitud = EstadoSolicitud.BORRADOR
    validacion: Dict[str, ValidacionCampo] = {
        "cliente": ValidacionCampo(valido=False, razon="No validado"),
        "beneficiario": ValidacionCampo(valido=False, razon="No validado"),
        "idmex": ValidacionCampo(valido=False, razon="No validado"),
        "ligas": ValidacionCampo(valido=False, razon="No validado"),
        "comprobante": ValidacionCampo(valido=False, razon="No validado")
    }
    
    # Montos (Etapa 1: solo guardar, no calcular automáticamente)
    monto_depositado_cliente: Optional[float] = None
    porcentaje_comision_cliente: Optional[float] = None
    monto_comision_mbco: Optional[float] = None
    monto_capital_proveedor: Optional[float] = None
    
    # Metadata del canal
    canal_metadata: CanalMetadata = CanalMetadata()
    
    # Control
    legacy: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    estado_historico: List[HistoricoEstado] = []
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CuentaBancaria(BaseModel):
    """Modelo de una cuenta bancaria en config_cuentas_netcash"""
    id: str
    tipo: TipoCuenta
    banco: str
    clabe: str = Field(..., min_length=18, max_length=18)
    beneficiario: str
    activa: bool = False
    fecha_activacion: Optional[datetime] = None
    notas: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class SolicitudCreate(BaseModel):
    """DTO para crear una nueva solicitud NetCash"""
    canal: CanalOrigen
    cliente_id: str
    cliente_nombre: str
    beneficiario_reportado: Optional[str] = None
    idmex_reportado: Optional[str] = None
    cantidad_ligas_reportada: Optional[int] = None
    canal_metadata: Optional[CanalMetadata] = None


class SolicitudUpdate(BaseModel):
    """DTO para actualizar una solicitud existente"""
    beneficiario_reportado: Optional[str] = None
    idmex_reportado: Optional[str] = None
    cantidad_ligas_reportada: Optional[int] = None
    monto_depositado_cliente: Optional[float] = None


class ResumenCliente(BaseModel):
    """Resumen de validación para mostrar al cliente
    
    Este es el formato estándar para comunicar al cliente
    el estado de su solicitud, usado por todos los canales.
    """
    solicitud_id: str
    folio_mbco: Optional[str] = None
    estado: EstadoSolicitud
    
    # Bloque 1: "Esto es lo que entendí"
    campos_detectados: Dict[str, Any]  # {campo: valor}
    campos_validos: List[str]  # ["beneficiario", "idmex", ...]
    
    # Bloque 2: "Esto falta o está mal"
    campos_faltantes: List[str]
    campos_invalidos: List[Dict[str, str]]  # [{campo, razon}, ...]
    
    # Bloque 3: "Qué sigue"
    mensaje_siguiente_paso: str
    cuenta_concertadora: Optional[Dict[str, str]] = None  # banco, clabe, beneficiario
