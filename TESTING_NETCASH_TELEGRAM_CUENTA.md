# 🧪 TESTING: CUENTA ACTIVA UNIFICADA EN TELEGRAM

## 📋 Objetivo

Verificar que Telegram **SIEMPRE** muestra la cuenta concertadora activa correcta, la misma que usa el motor NetCash y el endpoint `/api/netcash/cuentas/activa/concertadora`.

---

## ✅ CASO 1: Una Sola Cuenta Activa (THABYETHA)

### **Configuración:**
```javascript
// En MongoDB: config_cuentas_netcash
{
  tipo: "concertadora",
  banco: "STP",
  clabe: "646180115700001462",
  beneficiario: "JARDINERIA Y COMERCIO THABYETHA SA DE CV",
  activa: true
}

{
  tipo: "concertadora",
  banco: "BANCO PRUEBA CTA",
  clabe: "234598762012345687",
  beneficiario: "EMPRESA PRUEBA CTA",
  activa: false  // INACTIVA
}
```

### **Verificación Previa:**
```bash
# Verificar cuenta activa en el endpoint
curl http://localhost:8001/api/netcash/cuentas/activa/concertadora | jq

# Debe retornar:
{
  "success": true,
  "cuenta": {
    "banco": "STP",
    "clabe": "646180115700001462",
    "beneficiario": "JARDINERIA Y COMERCIO THABYETHA SA DE CV",
    "activa": true
  }
}
```

### **Prueba en Telegram:**

#### Paso 1: Ver cuenta
```
Usuario: /start
Bot: [Menú con opciones]

Usuario: Selecciona "💳 Ver cuenta para depósitos"

Bot debe mostrar:
🏦 Cuenta autorizada para tus depósitos NetCash:

Banco: STP
CLABE: 646180115700001462
Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV

💡 Realiza tu depósito a esta cuenta y después envíame los comprobantes.

[⬅️ Volver al menú]
```

#### Paso 2: Crear operación
```
Usuario: Selecciona "🧾 Crear nueva operación NetCash"

Bot debe mostrar:
✅ Iniciemos tu operación NetCash

🏦 Cuenta para tu depósito:
• Banco: STP
• CLABE: 646180115700001462
• Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV

📝 Paso 1 de 4: Nombre del beneficiario

Por favor envíame el nombre completo del beneficiario...
```

### **Logs Esperados:**
```
[NC Telegram] Mostrando cuenta: STP / 646180115700001462
[ConfigCuentas] Cuenta activa concertadora: STP - 646180115700001462
```

### ✅ **Criterio de Aceptación:**
- Telegram muestra EXACTAMENTE los mismos datos que el endpoint `/api/netcash/cuentas/activa/concertadora`
- No hay hardcodes ni referencias a servicios antiguos

---

## ✅ CASO 2: Cambiar Cuenta Activa (BANCO PRUEBA)

### **Configuración:**
```javascript
// Cambiar la cuenta activa en MongoDB
// Desactivar THABYETHA
{
  tipo: "concertadora",
  banco: "STP",
  clabe: "646180115700001462",
  beneficiario: "JARDINERIA Y COMERCIO THABYETHA SA DE CV",
  activa: false  // CAMBIADO A FALSE
}

// Activar BANCO PRUEBA
{
  tipo: "concertadora",
  banco: "BANCO PRUEBA CTA",
  clabe: "234598762012345687",
  beneficiario: "EMPRESA PRUEBA CTA",
  activa: true  // CAMBIADO A TRUE
}
```

### **Script para cambiar cuenta:**
```bash
# Conectar a MongoDB
mongo netcash_mbco

# Desactivar todas las concertadoras
db.config_cuentas_netcash.updateMany(
  {tipo: "concertadora"},
  {$set: {activa: false}}
)

# Activar BANCO PRUEBA
db.config_cuentas_netcash.updateOne(
  {tipo: "concertadora", banco: "BANCO PRUEBA CTA"},
  {$set: {activa: true, fecha_activacion: new Date()}}
)

# Verificar
db.config_cuentas_netcash.find({tipo: "concertadora", activa: true}).pretty()
```

### **Verificación Previa:**
```bash
curl http://localhost:8001/api/netcash/cuentas/activa/concertadora | jq

# Ahora debe retornar:
{
  "success": true,
  "cuenta": {
    "banco": "BANCO PRUEBA CTA",
    "clabe": "234598762012345687",
    "beneficiario": "EMPRESA PRUEBA CTA",
    "activa": true
  }
}
```

### **Prueba en Telegram:**
```
Usuario: /start
Usuario: Selecciona "💳 Ver cuenta para depósitos"

Bot debe mostrar:
🏦 Cuenta autorizada para tus depósitos NetCash:

Banco: BANCO PRUEBA CTA
CLABE: 234598762012345687
Beneficiario: EMPRESA PRUEBA CTA

💡 Realiza tu depósito a esta cuenta...

[⬅️ Volver al menú]
```

### **Logs Esperados:**
```
[NC Telegram] Mostrando cuenta: BANCO PRUEBA CTA / 234598762012345687
[ConfigCuentas] Cuenta activa concertadora: BANCO PRUEBA CTA - 234598762012345687
```

### ✅ **Criterio de Aceptación:**
- Telegram ahora muestra BANCO PRUEBA CTA
- Los datos coinciden EXACTAMENTE con el endpoint
- NO muestra datos de THABYETHA (la cuenta inactiva)

---

## ❌ CASO 3: Dos Cuentas Activas (Escenario de Error)

### **Configuración:**
```javascript
// En MongoDB: Activar AMBAS cuentas (error de configuración)
{
  tipo: "concertadora",
  banco: "STP",
  clabe: "646180115700001462",
  beneficiario: "JARDINERIA Y COMERCIO THABYETHA SA DE CV",
  activa: true  // AMBAS ACTIVAS
}

{
  tipo: "concertadora",
  banco: "BANCO PRUEBA CTA",
  clabe: "234598762012345687",
  beneficiario: "EMPRESA PRUEBA CTA",
  activa: true  // AMBAS ACTIVAS
}
```

### **Script para crear el error:**
```bash
mongo netcash_mbco

# Activar AMBAS
db.config_cuentas_netcash.updateMany(
  {tipo: "concertadora"},
  {$set: {activa: true}}
)

# Verificar (debe mostrar 2)
db.config_cuentas_netcash.count({tipo: "concertadora", activa: true})
```

### **Prueba en Telegram:**
```
Usuario: /start
Usuario: Selecciona "💳 Ver cuenta para depósitos"

Bot debe mostrar:
⚠️ Error de configuración

Por el momento no puedo mostrar la cuenta de depósito NetCash porque hay más de una cuenta activa configurada.

Por favor avísale a Ana para que lo revisen.

[⬅️ Volver al menú]
```

### **Logs Esperados:**
```
[NC Telegram] Error: 2 cuentas concertadora activas (debe haber solo 1)
```

### ✅ **Criterio de Aceptación:**
- Bot NO muestra una cuenta aleatoria
- Muestra mensaje de error claro y amigable
- Logs indican claramente el problema
- Usuario sabe que debe contactar a Ana

---

## 🔍 Verificaciones Técnicas

### **1. Verificar que NO queden referencias antiguas:**
```bash
# Buscar referencias al servicio viejo
grep -r "cuenta_deposito_service" /app/backend/telegram*.py

# Resultado esperado: Sin resultados
```

### **2. Verificar imports correctos:**
```bash
grep -n "from config_cuentas_service" /app/backend/telegram*.py

# Debe aparecer en:
# - telegram_netcash_handlers.py (línea ~12)
# - telegram_bot.py (líneas ~795, 910, 935, 1096)
```

### **3. Verificar que usa TipoCuenta.CONCERTADORA:**
```bash
grep -n "TipoCuenta.CONCERTADORA" /app/backend/telegram*.py

# Debe aparecer en todos los lugares donde se obtiene cuenta
```

---

## 📊 Tabla de Comparación

| Origen | CASO 1 (THABYETHA) | CASO 2 (BANCO PRUEBA) |
|--------|-------------------|----------------------|
| **Endpoint API** | STP / ...1462 | BANCO PRUEBA CTA / ...5687 |
| **Telegram "Ver cuenta"** | ✅ STP / ...1462 | ✅ BANCO PRUEBA CTA / ...5687 |
| **Telegram "Crear operación"** | ✅ STP / ...1462 | ✅ BANCO PRUEBA CTA / ...5687 |
| **Motor NetCash** | ✅ STP / ...1462 | ✅ BANCO PRUEBA CTA / ...5687 |

**✅ Todos deben coincidir**

---

## 🚀 Comandos de Verificación Rápida

```bash
# 1. Ver cuenta activa actual
curl -s http://localhost:8001/api/netcash/cuentas/activa/concertadora | jq '.cuenta | {banco, clabe, beneficiario}'

# 2. Contar cuentas activas
mongo netcash_mbco --eval 'db.config_cuentas_netcash.count({tipo:"concertadora",activa:true})'

# 3. Ver logs de Telegram
tail -f /var/log/telegram_bot.log | grep -E "(NC Telegram|Mostrando cuenta)"

# 4. Listar todas las cuentas
curl -s http://localhost:8001/api/netcash/cuentas | jq '.cuentas[] | select(.tipo=="concertadora") | {banco, activa}'
```

---

## ✅ Checklist Final

- [ ] Telegram usa `config_cuentas_service.obtener_cuenta_activa(TipoCuenta.CONCERTADORA)`
- [ ] NO hay referencias a `cuenta_deposito_service`
- [ ] NO hay hardcodes de banco/CLABE/beneficiario
- [ ] Manejo de error cuando hay más de 1 cuenta activa
- [ ] Logs claros en todas las funciones
- [ ] Datos coinciden con endpoint `/api/netcash/cuentas/activa/concertadora`

---

## 📝 Estado

**LISTO PARA PRUEBAS**

Archivos modificados:
- `/app/backend/telegram_netcash_handlers.py` - Agregado manejo de error
- `/app/backend/telegram_bot.py` - Reemplazadas 4 referencias al servicio antiguo

Bot reiniciado y funcionando: ✅
