from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
from enum import Enum


class EstadoOperacion(str, Enum):
    ESPERANDO_COMPROBANTES = "ESPERANDO_COMPROBANTES"
    VALIDANDO_COMPROBANTES = "VALIDANDO_COMPROBANTES"
    ESPERANDO_DATOS_TITULAR = "ESPERANDO_DATOS_TITULAR"
    ESPERANDO_CONFIRMACION_CLIENTE = "ESPERANDO_CONFIRMACION_CLIENTE"
    ESPERANDO_CODIGO_SISTEMA = "ESPERANDO_CODIGO_SISTEMA"
    PENDIENTE_PAGO_PROVEEDOR = "PENDIENTE_PAGO_PROVEEDOR"
    ESPERANDO_TESORERIA = "ESPERANDO_TESORERIA"
    ESPERANDO_PROVEEDOR = "ESPERANDO_PROVEEDOR"
    LISTO_PARA_ENTREGAR = "LISTO_PARA_ENTREGAR"
    COMPLETADO = "COMPLETADO"
    ALTA_CLIENTE_PENDIENTE = "ALTA_CLIENTE_PENDIENTE"
    CONTROL_DIA_ANTERIOR_PENDIENTE = "CONTROL_DIA_ANTERIOR_PENDIENTE"


class Propietario(str, Enum):
    DANIEL = "D"
    SAMUEL = "S"
    RAMON = "R"
    MBCO = "M"


class ComprobanteDepositoOCR(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    monto: Optional[float] = None
    fecha: Optional[str] = None
    banco_emisor: Optional[str] = None
    cuenta_beneficiaria: Optional[str] = None
    nombre_beneficiario: Optional[str] = None
    referencia: Optional[str] = None
    clave_rastreo: Optional[str] = None  # Identificador único del comprobante
    archivo_original: Optional[str] = None
    es_valido: bool = False
    es_duplicado: bool = False  # Marca si es un comprobante repetido
    mensaje_validacion: Optional[str] = None


class CalculosNetCash(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    monto_depositado_cliente: float
    comision_cliente_porcentaje: float
    capital_netcash: float
    comision_cliente_cobrada: float
    comision_proveedor_porcentaje: float = 0.00375
    comision_proveedor: float
    total_egreso: float


class OperacionNetCash(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    folio_mbco: Optional[str] = None  # Folio legible para el usuario (ej: NC-000123)
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Vínculo con cliente
    id_cliente: Optional[str] = None  # ID del cliente en la colección clientes
    
    # Información del cliente (copiada en el momento de crear la operación)
    cliente_nombre: Optional[str] = None
    cliente_email: Optional[str] = None
    cliente_telefono_completo: Optional[str] = None
    cliente_telegram_id: Optional[str] = None
    
    # Comisión específica de esta operación
    porcentaje_comision_usado: Optional[float] = None  # Copiado del cliente, pero editable para esta operación
    
    # Propietario de la operación
    propietario: Optional[Propietario] = None
    
    # Estado de la operación
    estado: EstadoOperacion = EstadoOperacion.ESPERANDO_COMPROBANTES
    
    # Comprobantes
    comprobantes: List[ComprobanteDepositoOCR] = []
    
    # Datos del titular de las ligas
    titular_nombre_completo: Optional[str] = None
    titular_idmex: Optional[str] = None
    numero_ligas: Optional[int] = None
    
    # Cálculos financieros
    calculos: Optional[CalculosNetCash] = None
    
    # Código del sistema (generado por Ana)
    codigo_operacion_sistema: Optional[str] = None
    
    # Ligas generadas por el proveedor
    ligas: List[str] = []
    
    # Timestamps de seguimiento
    timestamp_confirmacion_cliente: Optional[datetime] = None
    timestamp_codigo_sistema: Optional[datetime] = None
    timestamp_pago_proveedor: Optional[datetime] = None
    timestamp_ligas_recibidas: Optional[datetime] = None
    timestamp_entrega_cliente: Optional[datetime] = None
    
    # Observaciones y notas
    observaciones: List[str] = []


class OperacionNetCashCreate(BaseModel):
    id_cliente: str  # Obligatorio: debe estar vinculado a un cliente
    porcentaje_comision_usado: Optional[float] = None  # Opcional: si no se proporciona, se copia del cliente


class Cliente(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    nombre: str
    email: Optional[str] = None  # Opcional
    pais: str = "MX"  # País por defecto México
    prefijo_telefono: str = "+52"  # Prefijo por defecto México
    telefono: str  # Número sin prefijo
    telefono_completo: Optional[str] = None  # Prefijo + número (auto-generado)
    telegram_id: Optional[str] = None
    porcentaje_comision_cliente: float = 0.65  # Porcentaje (ej: 0.65 = 0.65%)
    canal_preferido: Optional[str] = None  # "Telegram", "WhatsApp", "Correo"
    propietario: Propietario
    rfc: Optional[str] = None  # RFC del cliente
    notas: Optional[str] = None  # Notas sobre el cliente
    estado: str = "activo"  # "pendiente_validacion" o "activo"
    fecha_alta: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    activo: bool = True
    
    def __init__(self, **data):
        super().__init__(**data)
        # Auto-generar telefono_completo
        if not self.telefono_completo and self.telefono:
            self.telefono_completo = f"{self.prefijo_telefono}{self.telefono}"


class ClienteCreate(BaseModel):
    nombre: str
    email: Optional[str] = None  # Opcional
    pais: str = "MX"
    prefijo_telefono: str = "+52"
    telefono: str
    telegram_id: Optional[str] = None
    porcentaje_comision_cliente: float = 0.65
    canal_preferido: Optional[str] = None
    propietario: Propietario
    rfc: Optional[str] = None  # RFC opcional
    notas: Optional[str] = None  # Notas opcionales


class LayoutPagoProveedor(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    bloque_inicio: datetime
    bloque_fin: datetime
    
    operaciones_incluidas: List[str] = []  # IDs de operaciones
    
    # Particiones de capital (BBVA)
    transferencias_capital: List[Dict[str, Any]] = []
    total_capital: float = 0.0
    
    # Particiones de comisión (ASP)
    transferencias_comision: List[Dict[str, Any]] = []
    total_comision: float = 0.0
    
    ejecutado: bool = False
    timestamp_ejecucion: Optional[datetime] = None


class MensajeTelegram(BaseModel):
    telegram_id: str
    mensaje: str
    tipo: str = "text"  # text, document, photo


class CorreoEmail(BaseModel):
    destinatario: str
    asunto: str
    cuerpo: str
    archivos_adjuntos: List[str] = []