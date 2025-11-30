# Instrucciones de Prueba - Treasury Workflow (Tesorería)

## ✅ Ajustes Implementados

### 1. Layout siempre va a PROVEEDOR (no al cliente)
- **Capital/Ligas** → AFFORDABLE MEDICAL SERVICES SC, BBVA, CLABE: 012680001255709482
- **Comisión DNS** → Comercializadora Uetacop SA de CV, ASP, CLABE: 058680000012912655
- Conceptos: `MBco {folio_mbco_con_x}` donde guiones son reemplazados por `x`

### 2. Información de margen removida del correo
- Tesorería solo ve: Cliente, Beneficiario, Total depósitos, Capital a proveedor, Comisión DNS
- NO se muestra: Comisión cliente, utilidad, margen, spread

### 3. Cuentas de proveedor configurables
- Colección: `cuentas_proveedor_netcash`
- Servicio: `cuentas_proveedor_service.py`
- Documentación: `/app/CONFIG_CUENTAS_PROVEEDOR_NETCASH.md`

---

## 🧪 Cómo Probar el Treasury Workflow

### Opción 1: Ejecutar el Test Completo (Recomendado)

```bash
cd /app
python3 backend/tests/test_treasury_workflow.py
```

**Qué hace:**
- Crea 2 solicitudes de prueba en estado `orden_interna_generada`
- Ejecuta el proceso de tesorería
- Verifica que:
  - Estados cambian a `enviado_a_tesoreria` ✅
  - Se crea un lote en BD ✅
  - CSV usa cuentas de PROVEEDOR (no cliente) ✅
  - Conceptos usan formato `MBco XXXxXXXxXxXX` ✅
  - No hay margen/utilidad expuesta ✅
  - Email se envía correctamente ✅
- Limpia los datos de prueba

**Resultado esperado:**
```
✅ TODOS LOS TESTS PASARON
```

### Opción 2: Crear una Solicitud Manual y Esperar el Scheduler

```bash
cd /app
python3 << 'EOF'
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone
from uuid import uuid4

async def crear_solicitud():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['netcash_mbco']
    
    solicitud = {
        "id": f"test-manual-{int(datetime.now(timezone.utc).timestamp())}",
        "folio_mbco": "9876-543-M-21",
        "canal": "telegram",
        "cliente_id": str(uuid4()),
        "cliente_nombre": "CLIENTE MANUAL DE PRUEBA",
        "beneficiario_reportado": "BENEFICIARIO PRUEBA MANUAL",
        "idmex_reportado": "TEST123456789",
        "cantidad_ligas_reportada": 2,
        "total_comprobantes_validos": 10000.00,
        "comision_cliente": 100.00,
        "monto_ligas": 9900.00,
        "estado": "orden_interna_generada",
        "comprobantes": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.solicitudes_netcash.insert_one(solicitud)
    print(f"✅ Solicitud creada: {solicitud['id']}")
    print(f"   Folio: {solicitud['folio_mbco']}")
    print(f"   Estado: {solicitud['estado']}")
    print(f"\n⏱ Espera máximo 15 minutos para que el scheduler procese el lote")
    
    client.close()

asyncio.run(crear_solicitud())
EOF
```

**Luego espera máximo 15 minutos y verifica:**

```bash
# Ver lotes creados
mongo mongodb://localhost:27017/netcash_mbco --eval "db.lotes_tesoreria.find().pretty()"

# Ver estado de la solicitud
mongo mongodb://localhost:27017/netcash_mbco --eval "db.solicitudes_netcash.find({folio_mbco: '9876-543-M-21'}, {estado: 1, lote_tesoreria_id: 1}).pretty()"
```

### Opción 3: Ejecutar el Proceso Manualmente (Sin Esperar)

```bash
cd /app
python3 test_tesoreria_manual.py
```

**Qué hace:**
- Busca solicitudes con estado `orden_interna_generada`
- Ejecuta inmediatamente el proceso de lotes
- Genera CSV y envía correo
- Cambia estados a `enviado_a_tesoreria`

---

## 🔍 Verificar Resultados

### 1. Ver el CSV Generado

```bash
ls -lah /app/backend/uploads/layouts_tesoreria/
cat /app/backend/uploads/layouts_tesoreria/LT-*.csv
```

**Verificar:**
- ✅ Filas de capital tienen CLABE: `012680001255709482` (AFFORDABLE)
- ✅ Filas de capital tienen beneficiario: `AFFORDABLE MEDICAL SERVICES SC`
- ✅ Filas de comisión tienen CLABE: `058680000012912655` (Comercializadora Uetacop)
- ✅ Filas de comisión tienen beneficiario: `COMERCIALIZADORA UETACOP SA DE CV`
- ✅ Conceptos usan `x` en lugar de `-` (ej: `MBco 9876x543xMx21`)
- ❌ NO debe haber nombres de clientes o beneficiarios finales como destinatarios

### 2. Ver Logs del Backend

```bash
tail -f /var/log/supervisor/backend.err.log | grep -E "(Tesorería|CuentasProveedor)"
```

**Buscar:**
```
[Tesorería] Cuenta capital: AFFORDABLE MEDICAL SERVICES SC - 012680001255709482
[Tesorería] Cuenta comisión DNS: COMERCIALIZADORA UETACOP SA DE CV - 058680000012912655
[Tesorería] Destinatarios: Capital=AFFORDABLE MEDICAL SERVICES SC, Comisión=COMERCIALIZADORA UETACOP SA DE CV
```

### 3. Verificar Cuentas de Proveedor en BD

```bash
mongo mongodb://localhost:27017/netcash_mbco << 'EOF'
// Ver cuentas activas
db.cuentas_proveedor_netcash.find({ activo: true }).pretty()

// Debe mostrar 2 cuentas:
// 1. tipo: "capital", clabe: "012680001255709482", beneficiario: "AFFORDABLE MEDICAL SERVICES SC"
// 2. tipo: "comision_dns", clabe: "058680000012912655", beneficiario: "Comercializadora Uetacop SA de CV"
EOF
```

### 4. Verificar Email Enviado

El correo se envía a: `dfgalezzo@hotmail.com` (configurado en `TESORERIA_TEST_EMAIL`)

**Revisar que el correo contiene:**
- ✅ Cliente y Beneficiario como contexto (no como destinatarios)
- ✅ Total depósitos recibidos
- ✅ Monto a enviar en ligas (capital a proveedor)
- ✅ Comisión DNS (a proveedor)
- ✅ Resumen de dispersión al proveedor
- ✅ CSV adjunto
- ❌ NO debe mencionar: "margen", "utilidad MBco", "spread", "comisión cliente"

---

## 🛠️ Cambiar de Proveedor (Ejemplo)

Si en el futuro quieres cambiar a un nuevo proveedor:

```bash
cd /app
python3 << 'EOF'
import asyncio
from cuentas_proveedor_service import cuentas_proveedor_service

async def agregar_nuevo_proveedor():
    # Agregar cuenta de capital del nuevo proveedor
    resultado = await cuentas_proveedor_service.crear_cuenta(
        tipo="capital",
        beneficiario="NUEVO PROVEEDOR MEDICAL SA DE CV",
        banco="SANTANDER",
        clabe="014680001234567890",
        activar_inmediatamente=True,  # Desactiva automáticamente las demás
        notas="Nuevo proveedor a partir del 01-Ene-2026"
    )
    
    if resultado["success"]:
        print("✅ Cuenta de capital creada y activada")
    
    # Agregar cuenta de comisión del nuevo proveedor
    resultado = await cuentas_proveedor_service.crear_cuenta(
        tipo="comision_dns",
        beneficiario="NUEVO PROVEEDOR FACTURACION SA DE CV",
        banco="SANTANDER",
        clabe="014680009876543210",
        activar_inmediatamente=True,
        notas="Nueva cuenta comisión a partir del 01-Ene-2026"
    )
    
    if resultado["success"]:
        print("✅ Cuenta de comisión creada y activada")
    
    print("\n🎉 Nuevo proveedor configurado. Los próximos lotes usarán estas cuentas.")

asyncio.run(agregar_nuevo_proveedor())
EOF
```

---

## 📊 Resumen de Cambios

| Aspecto | Antes | Ahora |
|---------|-------|-------|
| Destinatarios del layout | Cliente/Beneficiario final | Siempre PROVEEDOR |
| Capital CLABE | Hardcode/env var | Desde BD (012680001255709482) |
| Comisión CLABE | Hardcode/env var | Desde BD (058680000012912655) |
| Email muestra margen | ✅ Sí | ❌ No |
| Cambio de proveedor | Requiere código | Solo BD (configurable) |
| Conceptos CSV | MBco 1234-567-M-11 | MBco 1234x567xMx11 |

---

## ✅ Checklist Pre-Producción

Antes de llevar a producción, verificar:

- [ ] Cuentas de proveedor correctas en `cuentas_proveedor_netcash`
- [ ] Email de tesorería configurado en `TESORERIA_TEST_EMAIL`
- [ ] Scheduler corriendo (cada 15 minutos)
- [ ] Tests pasando sin errores
- [ ] Logs del backend sin errores relacionados a Tesorería
- [ ] CSV generado usa solo cuentas de proveedor
- [ ] Email NO expone margen/utilidad
- [ ] Notificaciones Telegram a usuarios con `recibe_alertas_tesoreria=true`

---

## 🆘 Troubleshooting

### Problema: "No hay cuenta activa para tipo 'capital'"

**Solución:**
```bash
cd /app
python3 << 'EOF'
import asyncio
from cuentas_proveedor_service import cuentas_proveedor_service

asyncio.run(cuentas_proveedor_service.sembrar_cuentas_iniciales())
EOF
```

### Problema: El layout usa CLABEs viejas

**Causa:** Las cuentas de proveedor no están activas o no existen.

**Solución:** Verificar cuentas activas:
```bash
mongo mongodb://localhost:27017/netcash_mbco --eval "db.cuentas_proveedor_netcash.find({ activo: true }).pretty()"
```

### Problema: Email no se envía

**Causa:** Gmail service no configurado o credenciales faltantes.

**Solución temporal:** El CSV se guarda localmente en `/app/backend/uploads/layouts_tesoreria/` y se puede enviar manualmente.

---

## 📞 Soporte

Para dudas:
- Configuración de cuentas: Ver `/app/CONFIG_CUENTAS_PROVEEDOR_NETCASH.md`
- Logs del backend: `tail -f /var/log/supervisor/backend.err.log`
- Tests: Ejecutar `python3 backend/tests/test_treasury_workflow.py`
