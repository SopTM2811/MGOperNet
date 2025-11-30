# Configuración de Cuentas de Proveedor NetCash

## 📋 Descripción General

El sistema NetCash gestiona las cuentas bancarias del **proveedor** (DNS) de manera configurable en base de datos. Esto permite cambiar de proveedor sin modificar código, solo actualizando la configuración.

### Tipos de Cuentas

Existen dos tipos de cuentas de proveedor:

1. **`capital`**: Cuenta para pagar al proveedor el capital de las ligas
   - El proveedor genera las ligas de pago
   - Esta cuenta recibe el monto que se va a dispersar en ligas

2. **`comision_dns`**: Cuenta para pagar la comisión al proveedor
   - Esta es la comisión que se cobra al proveedor por su servicio
   - Es independiente del capital

---

## 🗄️ Estructura de la Colección MongoDB

**Colección:** `cuentas_proveedor_netcash`

### Estructura del Documento

```json
{
  "id": "uuid-generado",
  "tipo": "capital | comision_dns",
  "beneficiario": "NOMBRE DEL BENEFICIARIO",
  "banco": "NOMBRE DEL BANCO",
  "clabe": "18-digitos-clabe",
  "activo": true | false,
  "fecha_alta": ISODate("2025-11-30T..."),
  "fecha_baja": ISODate("2025-12-15T...") | null,
  "notas": "Descripción o notas adicionales",
  "created_at": ISODate("2025-11-30T..."),
  "updated_at": ISODate("2025-11-30T...")
}
```

### Campos

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | String (UUID) | Identificador único de la cuenta |
| `tipo` | String | `"capital"` o `"comision_dns"` |
| `beneficiario` | String | Nombre completo del beneficiario (se guarda en mayúsculas) |
| `banco` | String | Nombre del banco (se guarda en mayúsculas) |
| `clabe` | String | CLABE de 18 dígitos |
| `activo` | Boolean | `true` si es la cuenta activa para su tipo |
| `fecha_alta` | DateTime | Fecha en que se dio de alta la cuenta |
| `fecha_baja` | DateTime/null | Fecha en que se desactivó (null si está activa) |
| `notas` | String | Notas o comentarios sobre la cuenta |
| `created_at` | DateTime | Timestamp de creación del registro |
| `updated_at` | DateTime | Timestamp de última actualización |

---

## ⚙️ Regla de Negocio Importante

**Solo puede haber UNA cuenta activa por tipo a la vez.**

- Si activas una cuenta de tipo `capital`, todas las demás cuentas `capital` se desactivan automáticamente
- Lo mismo aplica para `comision_dns`
- Esto asegura que el sistema siempre use las cuentas correctas en cada momento

---

## 🛠️ Cómo Usar el Sistema

### 1. Consultar Cuentas Activas

```python
from cuentas_proveedor_service import cuentas_proveedor_service

# Obtener cuenta de capital activa
cuenta_capital = await cuentas_proveedor_service.obtener_cuenta_activa("capital")
print(cuenta_capital)  # Retorna dict con datos de la cuenta o None

# Obtener cuenta de comisión DNS activa
cuenta_comision = await cuentas_proveedor_service.obtener_cuenta_activa("comision_dns")
```

### 2. Listar Todas las Cuentas

```python
# Listar todas las cuentas (activas e inactivas)
todas = await cuentas_proveedor_service.listar_todas_cuentas(incluir_inactivas=True)

# Listar solo activas
activas = await cuentas_proveedor_service.listar_todas_cuentas(incluir_inactivas=False)
```

### 3. Agregar una Nueva Cuenta de Proveedor

```python
resultado = await cuentas_proveedor_service.crear_cuenta(
    tipo="capital",
    beneficiario="NUEVO PROVEEDOR SA DE CV",
    banco="BANORTE",
    clabe="072680001234567890",
    activar_inmediatamente=True,  # Desactiva automáticamente las demás de este tipo
    notas="Cuenta nueva del proveedor efectiva desde 2025-12-01"
)

if resultado["success"]:
    print("✅ Cuenta creada:", resultado["cuenta"])
else:
    print("❌ Error:", resultado["error"])
```

### 4. Activar una Cuenta Existente

Si tienes varias cuentas configuradas y quieres activar una específica:

```python
# Activar cuenta por ID
exito = await cuentas_proveedor_service.activar_cuenta("uuid-de-la-cuenta")

if exito:
    print("✅ Cuenta activada. Las demás del mismo tipo se desactivaron.")
else:
    print("❌ No se pudo activar la cuenta.")
```

### 5. Desactivar una Cuenta

```python
exito = await cuentas_proveedor_service.desactivar_cuenta("uuid-de-la-cuenta")
```

---

## 📝 Ejemplo: Cambiar de Proveedor

### Escenario

Actualmente trabajamos con el **Proveedor A** pero queremos cambiar al **Proveedor B** a partir del 1 de diciembre.

### Pasos

1. **Agregar las cuentas del nuevo proveedor** (sin activarlas aún):

```python
# Cuenta de capital del Proveedor B
await cuentas_proveedor_service.crear_cuenta(
    tipo="capital",
    beneficiario="PROVEEDOR B SERVICIOS MEDICOS SA",
    banco="HSBC",
    clabe="021680009876543210",
    activar_inmediatamente=False,  # No activar todavía
    notas="Proveedor B - Vigente a partir del 01-Dic-2025"
)

# Cuenta de comisión del Proveedor B
await cuentas_proveedor_service.crear_cuenta(
    tipo="comision_dns",
    beneficiario="PROVEEDOR B FACTURACION SA",
    banco="HSBC",
    clabe="021680005555555555",
    activar_inmediatamente=False,
    notas="Proveedor B comisión - Vigente a partir del 01-Dic-2025"
)
```

2. **El 1 de diciembre, activar las cuentas nuevas**:

```python
# Activar cuenta de capital del Proveedor B
await cuentas_proveedor_service.activar_cuenta("uuid-cuenta-capital-proveedor-b")

# Activar cuenta de comisión del Proveedor B
await cuentas_proveedor_service.activar_cuenta("uuid-cuenta-comision-proveedor-b")
```

3. **Automáticamente**:
   - Las cuentas viejas del Proveedor A quedan inactivas
   - Los próximos lotes de Tesorería usarán las cuentas del Proveedor B
   - El layout CSV tendrá los nuevos beneficiarios y CLABEs

---

## 🔍 Verificación

### Desde MongoDB

```javascript
// Ver cuentas activas
db.cuentas_proveedor_netcash.find({ activo: true })

// Ver todas las cuentas de capital
db.cuentas_proveedor_netcash.find({ tipo: "capital" }).sort({ fecha_alta: -1 })

// Ver historial de una cuenta específica
db.cuentas_proveedor_netcash.find({ id: "uuid-de-cuenta" })
```

### Desde Logs del Backend

Al iniciar el servidor, verás:
```
[CuentasProveedor] Ya existen 2 cuenta(s) configurada(s)
```

Al generar un lote de Tesorería, verás:
```
[Tesorería] Cuenta capital: AFFORDABLE MEDICAL SERVICES SC - 012680001255709482
[Tesorería] Cuenta comisión DNS: Comercializadora Uetacop SA de CV - 058680000012912655
```

---

## 🎯 Cuentas Iniciales (Sembradas Automáticamente)

Al iniciar el sistema por primera vez, se crean estas cuentas:

### Cuenta de Capital (tipo: `capital`)
- **Beneficiario:** AFFORDABLE MEDICAL SERVICES SC
- **Banco:** BBVA
- **CLABE:** 012680001255709482
- **Estado:** Activa

### Cuenta de Comisión DNS (tipo: `comision_dns`)
- **Beneficiario:** Comercializadora Uetacop SA de CV
- **Banco:** ASP
- **CLABE:** 058680000012912655
- **Estado:** Activa

---

## 🚨 Importante

- **NO modificar directamente en MongoDB** sin usar el servicio `cuentas_proveedor_service`
- **NO eliminar cuentas**, solo desactivarlas (para mantener historial)
- **Verificar CLABEs** antes de activar (debe ser 18 dígitos válidos)
- **Probar en ambiente de prueba** antes de cambiar en producción

---

## 📞 Soporte

Para dudas sobre configuración de cuentas de proveedor, contactar a:
- Desarrollo: revisar logs en `/var/log/supervisor/backend.*.log`
- Negocio: confirmar datos de nuevas cuentas de proveedor antes de configurar
