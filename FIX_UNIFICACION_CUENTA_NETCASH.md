# 🔧 Fix: Unificación de Cuenta NetCash (Web + Bot de Telegram)

**Fecha:** 2024-12-01  
**Problema:** Desfase entre cuenta NetCash mostrada en web y validada por bot de Telegram  
**Estado:** ✅ **RESUELTO Y VERIFICADO**

---

## 📋 Problema Reportado

### Síntomas:
- **Web mostraba:** JARDINERIA Y COMERCIO THABYETHA SA DE CV (CLABE: 646180139409481462)
- **Bot validaba:** MONTE BANCO SA DE CV (CLABE: 646180174400027290)

### Resultado:
- Cliente subía comprobante con cuenta correcta (la de la web)
- Bot lo rechazaba diciendo "no coincide con cuenta autorizada"
- Mensaje de error mostraba cuenta incorrecta (MONTE BANCO)

---

## 🔍 Causa Raíz Identificada

**Había DOS colecciones diferentes en MongoDB:**

### 1. config_cuentas_netcash (ANTIGUA)
- Usada por: `config_cuentas_service`
- Cuenta: MONTE BANCO SA DE CV - 646180174400027290
- **Problema:** Bot de Telegram usaba esta colección

### 2. config_cuenta_deposito_netcash (NUEVA)
- Usada por: `cuenta_deposito_service`
- Cuenta: JARDINERIA Y COMERCIO THABYETHA SA DE CV - 646180139409481462
- **Correcto:** Web usa esta colección

### Código afectado:
```python
# Bot ANTES (❌ INCORRECTO)
from config_cuentas_service import config_cuentas_service
cuenta = await config_cuentas_service.obtener_cuenta_activa(TipoCuenta.CONCERTADORA)

# Web (✅ CORRECTO desde el inicio)
from cuenta_deposito_service import cuenta_deposito_service
cuenta = await cuenta_deposito_service.obtener_cuenta_activa()
```

---

## ✅ Solución Aplicada

### Unificar a la fuente de verdad correcta

**Cambiar bot para usar `cuenta_deposito_service` (la misma que usa la web)**

### Archivos modificados:

#### 1. `/app/backend/telegram_netcash_handlers.py`
**Cambio:**
```python
# ANTES ❌
from config_cuentas_service import config_cuentas_service, TipoCuenta
cuenta = await config_cuentas_service.obtener_cuenta_activa(TipoCuenta.CONCERTADORA)

# DESPUÉS ✅
from cuenta_deposito_service import cuenta_deposito_service
cuenta = await cuenta_deposito_service.obtener_cuenta_activa()
```

**Líneas cambiadas:**
- Línea 26: Import
- Líneas 110, 214, 688: Llamadas al servicio

#### 2. `/app/backend/netcash_service.py`
**Cambio:**
```python
# ANTES ❌
from config_cuentas_service import config_cuentas_service
from netcash_models import (..., TipoCuenta, ...)
cuenta = await config_cuentas_service.obtener_cuenta_activa(TipoCuenta.CONCERTADORA)

# DESPUÉS ✅
from cuenta_deposito_service import cuenta_deposito_service
from netcash_models import (...)  # Sin TipoCuenta
cuenta = await cuenta_deposito_service.obtener_cuenta_activa()
```

**Líneas cambiadas:**
- Línea 30: Eliminado `TipoCuenta` del import
- Línea 33: Import de `cuenta_deposito_service`
- Líneas 305, 833, 943: Llamadas al servicio

---

## 📊 Verificación

### Estado ANTES del fix:
```
Bot de Telegram:
  Banco: STP
  CLABE: 646180174400027290
  Beneficiario: MONTE BANCO SA DE CV

Web:
  Banco: STP
  CLABE: 646180139409481462
  Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV

❌ DESFASE: Cuentas diferentes
```

### Estado DESPUÉS del fix:
```
Bot de Telegram:
  Banco: STP
  CLABE: 646180139409481462
  Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV

Web:
  Banco: STP
  CLABE: 646180139409481462
  Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV

✅ UNIFICADO: Misma cuenta en bot y web
```

---

## 🧪 Test Creado

**Archivo:** `/app/backend/test_verificacion_cuenta_unificada.py`

### Ejecutar:
```bash
cd /app/backend
python test_verificacion_cuenta_unificada.py
```

### Resultado esperado:
```
🎉 TODO CORRECTO

La cuenta NetCash que verá el bot de Telegram es:
  Banco: STP
  CLABE: 646180139409481462
  Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV

Esta es la MISMA cuenta que muestra la web.
Los comprobantes serán validados contra esta cuenta.
```

---

## 🎯 Comportamiento Esperado Ahora

### En la Web:
1. Admin va a sección de configuración
2. Ve cuenta actual: **JARDINERIA Y COMERCIO THABYETHA SA DE CV**
3. Puede crear nueva cuenta si es necesario

### En Bot de Telegram:
1. Cliente crea operación NetCash
2. Al subir comprobante que no coincide, bot muestra:
   ```
   ❌ Ningún comprobante coincide con la cuenta NetCash autorizada.
   
   La cuenta NetCash autorizada es:
   • Banco: STP
   • CLABE: 646180139409481462
   • Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV
   ```
3. Esta cuenta es **LA MISMA** que muestra la web

### Validación de comprobantes:
- ✅ Si cliente deposita a cuenta **THABYETHA** (646180139409481462) → VÁLIDO
- ❌ Si cliente deposita a cuenta **MONTE BANCO** (646180174400027290) → INVÁLIDO

---

## 🔑 Fuente de Verdad Unificada

### Colección en MongoDB:
```
Nombre: config_cuenta_deposito_netcash
Campo activa: true (solo una cuenta puede estar activa)
```

### Servicio:
```python
from cuenta_deposito_service import cuenta_deposito_service
cuenta = await cuenta_deposito_service.obtener_cuenta_activa()
```

### Usado por:
- ✅ Web (API endpoints en `server.py`)
- ✅ Bot de Telegram (`telegram_netcash_handlers.py`)
- ✅ Servicio de validación (`netcash_service.py`)

### Cambiar cuenta en el futuro:
1. **Ir a la interfaz web** → Configuración de cuenta
2. **Crear nueva cuenta** con datos correctos
3. **Marcar como activa**
4. **NO REQUIERE cambios en código**
5. Bot y web automáticamente usarán la nueva cuenta

---

## 📝 Documentación para Futuro

### ¿Cómo cambiar la cuenta NetCash?

**Desde la interfaz web:**
1. Ir a sección de Configuración
2. Crear nueva cuenta con:
   - Banco
   - CLABE (18 dígitos)
   - Beneficiario
3. Marcar "Activar inmediatamente"
4. Guardar

**El cambio es inmediato:**
- ✅ Bot de Telegram usa nueva cuenta
- ✅ Web muestra nueva cuenta
- ✅ Validaciones usan nueva cuenta
- ✅ NO requiere reiniciar servicios
- ✅ NO requiere cambios en código

### ¿Dónde se almacena?

**MongoDB:**
- Colección: `config_cuenta_deposito_netcash`
- Base de datos: `netcash_mbco`

**Campos importantes:**
```json
{
  "banco": "STP",
  "clabe": "646180139409481462",
  "beneficiario": "JARDINERIA Y COMERCIO THABYETHA SA DE CV",
  "activa": true,
  "created_at": "2024-12-01...",
  "updated_at": "2024-12-01..."
}
```

---

## 🚀 Servicios Reiniciados

```bash
sudo supervisorctl restart backend telegram_bot
```

**Estado:**
- backend: PID 799 ✅
- telegram_bot: PID 803 ✅

---

## ✅ Criterios de Aceptación - Verificados

| Criterio | Estado |
|----------|--------|
| Bot usa misma cuenta que web | ✅ SÍ |
| Comprobante de cuenta web es válido | ✅ SÍ |
| Mensaje de error muestra cuenta correcta | ✅ SÍ |
| Cambio en web afecta inmediatamente al bot | ✅ SÍ |
| NO requiere cambios en código para actualizar cuenta | ✅ SÍ |

---

## 🎉 Conclusión

El desfase entre web y bot ha sido **completamente resuelto**.

**Antes:**
- 2 fuentes de verdad diferentes
- Bot validaba contra cuenta incorrecta
- Cliente confundido con mensajes contradictorios

**Después:**
- 1 fuente de verdad unificada (`config_cuenta_deposito_netcash`)
- Bot y web usan la misma cuenta
- Mensajes consistentes en todos lados
- Fácil de actualizar desde la web (sin código)

**Estado:** ✅ **LISTO PARA PRODUCCIÓN**
