# Flujos de Operación y Mapeo de Estados

## 📱 FLUJO TELEGRAM (Bot NetCash)

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUJO TELEGRAM                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1️⃣ INICIO                                                       │
│     └── Usuario inicia /netcash                                  │
│     └── Estado: "borrador"                                       │
│                                                                  │
│  2️⃣ PASO 1: COMPROBANTES (NC_ESPERANDO_COMPROBANTE = 20)        │
│     └── Usuario sube comprobante(s) PDF/imagen                   │
│     └── OCR procesa y valida                                     │
│     └── Botones: [➕ Agregar otro] [✅ Continuar]                │
│     └── Estado: "borrador" → "pendiente_comprobantes"            │
│                                                                  │
│  3️⃣ PASO 2a: BENEFICIARIO (NC_ESPERANDO_BENEFICIARIO = 21)      │
│     └── Usuario ingresa nombre del beneficiario                  │
│     └── O selecciona de beneficiarios frecuentes                 │
│     └── Estado: sin cambio                                       │
│                                                                  │
│  4️⃣ PASO 2b: IDMEX (NC_ESPERANDO_IDMEX = 22)                    │
│     └── Usuario ingresa IDMEX (10 dígitos)                       │
│     └── Estado: sin cambio                                       │
│                                                                  │
│  5️⃣ PASO 3: LIGAS (NC_ESPERANDO_LIGAS = 23)                     │
│     └── Usuario indica cantidad de ligas                         │
│     └── Sistema calcula comisiones                               │
│     └── Estado: "lista_para_confirmacion"                        │
│                                                                  │
│  6️⃣ PASO 4: CONFIRMACIÓN (NC_ESPERANDO_CONFIRMACION = 24)       │
│     └── Usuario revisa resumen y confirma                        │
│     └── Botones: [✅ Confirmar] [❌ Cancelar]                    │
│     └── Estado: "lista_para_mbc"                                 │
│                                                                  │
│  7️⃣ FIN: OPERACIÓN REGISTRADA                                   │
│     └── Sistema genera folio (ej: NC-000305)                     │
│     └── Operación aparece en Dashboard Web                       │
│     └── Estado final Telegram: "lista_para_mbc"                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🖥️ FLUJO WEB (Dashboard)

```
┌─────────────────────────────────────────────────────────────────┐
│                      FLUJO WEB                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1️⃣ CREAR OPERACIÓN                                              │
│     └── Nueva operación desde Dashboard                          │
│     └── Estado: ESPERANDO_COMPROBANTES                           │
│                                                                  │
│  2️⃣ SUBIR COMPROBANTES                                           │
│     └── Subir archivos ZIP o individuales                        │
│     └── OCR procesa automáticamente                              │
│     └── Validación contra cuenta activa                          │
│     └── Estado: ESPERANDO_DATOS_TITULAR (si válidos)             │
│               ESPERANDO_COMPROBANTES (si inválidos)              │
│                                                                  │
│  3️⃣ DATOS DEL TITULAR                                            │
│     └── Ingresar nombre completo (mín 3 palabras)                │
│     └── Ingresar IDMEX                                           │
│     └── Ingresar cantidad de ligas                               │
│     └── Estado: ESPERANDO_CONFIRMACION_CLIENTE                   │
│                                                                  │
│  4️⃣ CÁLCULOS                                                     │
│     └── Sistema muestra cálculos financieros                     │
│     └── Comisión, monto depositado, monto ligas                  │
│     └── Botón: [Confirmar Operación]                             │
│     └── Estado: DATOS_COMPLETOS                                  │
│                                                                  │
│  5️⃣ PENDIENTES MBCONTROL                                         │
│     └── Ana asigna clave MBControl (folio)                       │
│     └── Estado: ESPERANDO_CODIGO_SISTEMA → CON_CLAVE_MBCO        │
│                                                                  │
│  6️⃣ ENVÍO LAYOUT                                                 │
│     └── Sistema genera layout                                    │
│     └── Envía email a Tesorería                                  │
│     └── Estado: PENDIENTE_ENVIO_LAYOUT → LAYOUT_ENVIADO          │
│                                                                  │
│  7️⃣ TESORERÍA                                                    │
│     └── Espera respuesta de Tesorería                            │
│     └── Estado: ESPERANDO_TESORERIA                              │
│                                                                  │
│  8️⃣ COMPLETADO                                                   │
│     └── Operación finalizada                                     │
│     └── Estado: COMPLETADO                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 MAPEO DE ESTADOS (Telegram → Web)

| Estado Telegram              | Estado Web (EstadoOperacion)        | Descripción                              |
|------------------------------|-------------------------------------|------------------------------------------|
| `borrador`                   | ESPERANDO_COMPROBANTES              | Operación iniciada                       |
| `pendiente_comprobantes`     | ESPERANDO_COMPROBANTES              | Esperando más comprobantes               |
| `pendiente_datos`            | ESPERANDO_DATOS_TITULAR             | Esperando datos del beneficiario         |
| `pendiente_confirmacion`     | ESPERANDO_CONFIRMACION_CLIENTE      | Esperando confirmación del cliente       |
| `lista_para_confirmacion`    | ESPERANDO_CONFIRMACION_CLIENTE      | Listo para que cliente confirme          |
| `LISTA_PARA_CONFIRMACION`    | ESPERANDO_CONFIRMACION_CLIENTE      | (variante mayúsculas)                    |
| `lista_para_mbc`             | DATOS_COMPLETOS                     | ✅ Confirmado, listo para MBControl      |
| `LISTA_PARA_MBC`             | DATOS_COMPLETOS                     | (variante mayúsculas)                    |
| `ESPERANDO_VALIDACION_ANA`   | VALIDANDO_COMPROBANTES              | Ana revisando comprobantes               |
| `lista_para_mbco`            | ESPERANDO_CODIGO_SISTEMA            | Esperando clave MBControl                |
| `orden_interna_generada`     | ESPERANDO_CODIGO_SISTEMA            | Orden interna creada                     |
| `ORDEN_INTERNA_GENERADA`     | ESPERANDO_CODIGO_SISTEMA            | (variante mayúsculas)                    |
| `enviada_tesoreria`          | ESPERANDO_TESORERIA                 | Enviado a tesorería                      |
| `enviado_a_tesoreria`        | ESPERANDO_TESORERIA                 | (variante)                               |
| `ENVIADO_A_TESORERIA`        | ESPERANDO_TESORERIA                 | (variante mayúsculas)                    |
| `dispersada_proveedor`       | COMPLETADO                          | Proveedor dispersó fondos                |
| `DISPERSADA_PROVEEDOR`       | COMPLETADO                          | (variante mayúsculas)                    |
| `completada`                 | COMPLETADO                          | Operación finalizada                     |

---

## 📊 ESTADOS WEB (EstadoOperacion Enum)

```python
class EstadoOperacion(str, Enum):
    # Fase de captura
    EN_CAPTURA = "EN_CAPTURA"
    ESPERANDO_COMPROBANTES = "ESPERANDO_COMPROBANTES"
    COMPROBANTES_CERRADOS = "COMPROBANTES_CERRADOS"
    VALIDANDO_COMPROBANTES = "VALIDANDO_COMPROBANTES"
    
    # Fase de datos cliente
    ESPERANDO_DATOS_TITULAR = "ESPERANDO_DATOS_TITULAR"
    ESPERANDO_CONFIRMACION_CLIENTE = "ESPERANDO_CONFIRMACION_CLIENTE"
    DATOS_COMPLETOS = "DATOS_COMPLETOS"
    
    # Fase MBControl
    CON_CLAVE_MBCO = "CON_CLAVE_MBCO"
    ESPERANDO_CODIGO_SISTEMA = "ESPERANDO_CODIGO_SISTEMA"
    
    # Fase Layout/Tesorería
    PENDIENTE_ENVIO_LAYOUT = "PENDIENTE_ENVIO_LAYOUT"
    LAYOUT_ENVIADO = "LAYOUT_ENVIADO"
    ESPERANDO_TESORERIA = "ESPERANDO_TESORERIA"
    
    # Fase Proveedor
    PENDIENTE_PAGO_PROVEEDOR = "PENDIENTE_PAGO_PROVEEDOR"
    ESPERANDO_PROVEEDOR = "ESPERANDO_PROVEEDOR"
    LISTO_PARA_ENTREGAR = "LISTO_PARA_ENTREGAR"
    
    # Finalización
    COMPLETADO = "COMPLETADO"
    CANCELADA_POR_INACTIVIDAD = "CANCELADA_POR_INACTIVIDAD"
    
    # Estados especiales
    ALTA_CLIENTE_PENDIENTE = "ALTA_CLIENTE_PENDIENTE"
    CONTROL_DIA_ANTERIOR_PENDIENTE = "CONTROL_DIA_ANTERIOR_PENDIENTE"
```

---

## 🗄️ COLECCIONES EN MONGODB

| Colección                | Origen      | Descripción                           |
|--------------------------|-------------|---------------------------------------|
| `operaciones`            | WEB         | Operaciones creadas desde Dashboard   |
| `solicitudes_netcash`    | TELEGRAM    | Operaciones creadas desde Bot         |

**Nota importante:** Varios endpoints del backend buscan en AMBAS colecciones para soportar operaciones de cualquier origen:
- `/api/operaciones` (GET) - Lista todas
- `/api/operaciones/{id}` (GET) - Detalle
- `/api/operaciones/{id}/confirmar` (POST) - Confirmar
- `/api/operaciones/{id}/titular` (POST) - Guardar titular

---

## 🔀 FLUJO VISUAL SIMPLIFICADO

```
TELEGRAM                              WEB
────────                              ───
   │                                   │
   ▼                                   ▼
[Comprobantes] ──────────────────► [Comprobantes]
   │                                   │
   ▼                                   ▼
[Beneficiario + IDMEX] ──────────► [Datos Titular]
   │                                   │
   ▼                                   ▼
[Ligas] ─────────────────────────► [Cálculos]
   │                                   │
   ▼                                   ▼
[Confirmar] ─────────────────────► [Confirmar]
   │                                   │
   ▼                                   ▼
[lista_para_mbc] ═══════════════► [DATOS_COMPLETOS]
                                       │
                                       ▼
                              [Pendientes MBControl]
                                       │
                                       ▼
                              [Ana asigna folio]
                                       │
                                       ▼
                              [Layout a Tesorería]
                                       │
                                       ▼
                              [COMPLETADO]
```
