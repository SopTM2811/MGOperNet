# 🐛 BUG P0 RESUELTO: CUENTA ACTIVA DESINCRONIZADA

## 📋 Problema Reportado

- **Panel NetCash:** Mostraba THABYETHA como cuenta activa
- **Telegram:** Mostraba BANCO PRUEBA como cuenta activa
- **Estado:** ❌ DESINCRONIZADO

---

## 🔍 Diagnóstico

### Causa Raíz

Existían **2 colecciones diferentes** en MongoDB:

1. **`config_cuenta_deposito_netcash`** (ANTIGUA)
   - Usada por el panel web
   - Tenía THABYETHA con `activa: true`

2. **`config_cuentas_netcash`** (NUEVA - NetCash V1)
   - Usada por Telegram y motor NetCash
   - Tenía BANCO PRUEBA con `activa: true`

### Investigación Paso a Paso

**1. Endpoint del backend:**
```bash
curl -s http://localhost:8001/api/netcash/cuentas/activa/concertadora

# ANTES:
{
  "cuenta": {
    "banco": "BANCO PRUEBA CTA",
    "clabe": "234598762012345687",
    "activa": true
  }
}
```

**2. Cuentas en BD:**
```javascript
// Colección NUEVA (config_cuentas_netcash):
{
  banco: "BANCO PRUEBA CTA",
  clabe: "234598762012345687",
  activa: true
}

// Colección ANTIGUA (config_cuenta_deposito_netcash):
{
  banco: "STP",
  clabe: "646180139409481462",
  beneficiario: "JARDINERIA Y COMERCIO THABYETHA SA DE CV",
  activa: true
}
```

**Conclusión:** El panel leía de la colección antigua, Telegram de la nueva.

---

## ✅ Solución Aplicada

### Script de Migración

Se ejecutó un script Python que:

1. **Desactivó** BANCO PRUEBA en `config_cuentas_netcash`
2. **Migró** la cuenta THABYETHA desde la colección antigua a la nueva
3. **Activó** THABYETHA en `config_cuentas_netcash`

```python
# Desactivar todas las concertadoras
await db.config_cuentas_netcash.update_many(
    {"tipo": "concertadora"},
    {"$set": {"activa": False}}
)

# Crear THABYETHA en la colección nueva
nueva_cuenta = {
    "id": "cuenta-concertadora-1764455492797",
    "tipo": "concertadora",
    "banco": "STP",
    "clabe": "646180139409481462",
    "beneficiario": "JARDINERIA Y COMERCIO THABYETHA SA DE CV",
    "activa": True,
    ...
}
await db.config_cuentas_netcash.insert_one(nueva_cuenta)
```

---

## 🧪 Verificación Post-Migración

### 1. Endpoint del backend

```bash
curl -s http://localhost:8001/api/netcash/cuentas/activa/concertadora | jq

# DESPUÉS:
{
  "success": true,
  "cuenta": {
    "banco": "STP",
    "clabe": "646180139409481462",
    "beneficiario": "JARDINERIA Y COMERCIO THABYETHA SA DE CV",
    "activa": true
  }
}
```

✅ **Ahora devuelve THABYETHA**

### 2. Cuentas en BD

```bash
# Verificar colección nueva
mongo netcash_mbco --eval 'db.config_cuentas_netcash.find({tipo:"concertadora", activa:true}).pretty()'

# Resultado:
{
  "banco": "STP",
  "clabe": "646180139409481462",
  "beneficiario": "JARDINERIA Y COMERCIO THABYETHA SA DE CV",
  "activa": true
}
```

✅ **Solo 1 cuenta activa: THABYETHA**

### 3. Telegram

**Comando para probar:**
```
/start → Seleccionar "💳 Ver cuenta para depósitos"
```

**Resultado esperado:**
```
🏦 Cuenta autorizada para tus depósitos NetCash:

Banco: STP
CLABE: 646180139409481462
Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV

💡 Realiza tu depósito a esta cuenta...
```

**Log de Telegram:**
```
[NC Telegram] cuenta_activa usada en ver_cuenta_depositos: 
{
  'banco': 'STP',
  'clabe': '646180139409481462',
  'beneficiario': 'JARDINERIA Y COMERCIO THABYETHA SA DE CV'
}
```

✅ **Telegram ahora muestra THABYETHA**

---

## 📊 Comparación Antes/Después

| Fuente | ANTES | DESPUÉS |
|--------|-------|---------|
| **Panel Web** | THABYETHA | THABYETHA ✅ |
| **Endpoint API** | BANCO PRUEBA ❌ | THABYETHA ✅ |
| **Telegram** | BANCO PRUEBA ❌ | THABYETHA ✅ |
| **Motor NetCash** | BANCO PRUEBA ❌ | THABYETHA ✅ |

**✅ TODOS AHORA MUESTRAN LA MISMA CUENTA**

---

## 🔧 Archivos Modificados

1. **`telegram_netcash_handlers.py`**
   - Agregado log en `ver_cuenta_depositos()` para debugging
   - Línea: `logger.info(f"[NC Telegram] cuenta_activa usada...")`

2. **MongoDB**
   - Colección `config_cuentas_netcash` actualizada
   - Cuenta THABYETHA migrada y activada

3. **NO se modificó:**
   - ❌ netcash_service.py
   - ❌ email_monitor.py
   - ❌ Frontend React
   - ❌ Handler de saludos

---

## ✅ Criterios de Aceptación Cumplidos

- [x] **Criterio 1:** Endpoint `/api/netcash/cuentas/activa/concertadora` devuelve THABYETHA
- [x] **Criterio 2:** Log de `ver_cuenta_depositos()` muestra THABYETHA
- [x] **Criterio 3:** Telegram muestra THABYETHA (banco, CLABE, beneficiario)
- [x] **Criterio 4:** Panel web y Telegram alineados

---

## 🚀 Estado Final

```
✅ BUG RESUELTO
✅ Cuenta activa unificada: THABYETHA
✅ Panel, Telegram, API y Motor sincronizados
✅ Solo 1 cuenta activa en config_cuentas_netcash
```

---

## 📝 Recomendación

**Para evitar este problema en el futuro:**

El panel web debe migrar para leer de `config_cuentas_netcash` (la colección nueva de NetCash V1) en lugar de `config_cuenta_deposito_netcash` (la colección antigua).

Actualmente:
- ✅ Telegram → Lee de config_cuentas_netcash
- ✅ Motor NetCash → Lee de config_cuentas_netcash
- ⚠️ Panel Web → Todavía lee de config_cuenta_deposito_netcash

**Solución temporal aplicada:** Se migró la cuenta THABYETHA a ambas colecciones.

**Solución definitiva (futura):** Migrar el panel web para usar la misma colección que el resto del sistema.
