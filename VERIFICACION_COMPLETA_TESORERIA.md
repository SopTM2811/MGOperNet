# ✅ Verificación Completa - Flujo de Tesorería

## 📋 Resumen Ejecutivo

**Estado:** ✅ TODOS LOS TESTS PASADOS (5/5)

Después de las correcciones implementadas, el sistema funciona correctamente:
1. ✅ Nombre archivo CSV correcto: `LTMBCO_{folio_con_x}.csv`
2. ✅ CLABE comisión DNS correcta: `058680000012912655`
3. ✅ Comprobantes del cliente adjuntados (1 CSV + N PDFs)
4. ✅ Protección anti-duplicados en envío de correo
5. ✅ Detección de duplicados entre operaciones

---

## 🧪 Suite de Tests Ejecutada

**Archivo:** `/app/backend/tests/test_completo_tesoreria_layout_adjuntos.py`

### Test 1: Nombre del Archivo CSV ✅
```
Casos verificados:
  TEST-0001-T-99 → LTMBCO_TESTx0001xTx99.csv ✅
  2367-123-R-11 → LTMBCO_2367x123xRx11.csv ✅
  MBCO-9999-P-01 → LTMBCO_MBCOx9999xPx01.csv ✅
```

### Test 2: CLABE Comisión DNS ✅
```
Layout generado con 6 filas:
  - 5 filas de capital → CLABE: 012680001255709482 (AFFORDABLE) ✅
  - 1 fila comisión DNS → CLABE: 058680000012912655 (UETACOP) ✅

Beneficiario comisión: COMERCIALIZADORA UETACOP SA DE CV ✅
Monto comisión: $3,750.00 (0.375% de $1,000,000) ✅
```

### Test 3: Comprobantes Adjuntados ✅
```
Operación con 3 comprobantes en BD:
  - comp1.pdf (válido) → Adjuntado ✅
  - comp2.pdf (válido) → Adjuntado ✅
  - comp3_invalido.pdf (inválido) → NO adjuntado ✅

Resultado: 3 adjuntos totales (1 CSV + 2 comprobantes) ✅
```

### Test 4: No Envío Doble ✅
```
Intento 1: Marcar operación como enviada (correo_tesoreria_enviado = True)
Intento 2: Intentar procesar de nuevo
  ⚠️ CORREO YA ENVIADO para operación TEST-DUP-001-T-99
  Saltando reenvío para evitar duplicado ✅

Resultado: success=False, mensaje="Correo ya fue enviado previamente" ✅
```

### Test 5: Duplicados Entre Operaciones ✅
```
Operación 1: Agregar comprobante_test.pdf
  Hash: 557d16c17bea4b8114e9c984d2df9ffa350846ec371adfef5ce17c060f749b4c
  Resultado: agregado=True ✅

Operación 2: Intentar usar el MISMO PDF
  Hash: 557d16c17bea4b8114e9c984d2df9ffa350846ec371adfef5ce17c060f749b4c
  ⚠️ COMPROBANTE DUPLICADO GLOBAL detectado
  Ya usado en operación: test-dup-op-001
  Resultado: agregado=False, razon=duplicado_global ✅
```

---

## 📁 Verificación de Archivos Generados

### Layout CSV Ejemplo

**Archivo:** `/app/backend/uploads/layouts_operaciones/LTMBCO_2456x234xDx11.csv`

```csv
Clabe destinatario,Nombre o razon social destinatario,Monto,Concepto,Email (opcional),Tags separados por comas (opcional),Comentario (opcional)
012680001255709482,AFFORDABLE MEDICAL SERVICES SC,495000.00,MBco 2456x234xDx11,,,Liga 1/4
012680001255709482,AFFORDABLE MEDICAL SERVICES SC,495000.00,MBco 2456x234xDx11,,,Liga 2/4
012680001255709482,AFFORDABLE MEDICAL SERVICES SC,495000.00,MBco 2456x234xDx11,,,Liga 3/4
012680001255709482,AFFORDABLE MEDICAL SERVICES SC,495000.00,MBco 2456x234xDx11,,,Liga 4/4
058680000012912655,COMERCIALIZADORA UETACOP SA DE CV,7425.00,MBco 2456x234xDx11 COMISION,,,Comisión proveedor DNS
```

**Verificación:**
- ✅ Nombre archivo: `LTMBCO_2456x234xDx11.csv` (formato correcto)
- ✅ Filas 1-4: CLABE capital = `012680001255709482`
- ✅ Fila 5: CLABE comisión DNS = `058680000012912655`

---

## 🔧 Troubleshooting - Si el Usuario No Ve los Cambios

### 1. Verificar que el Backend Está Actualizado

```bash
# Verificar última actualización
sudo supervisorctl status backend

# Revisar logs recientes
tail -50 /var/log/supervisor/backend.err.log

# Confirmar que los schedulers están corriendo
grep "Scheduler" /var/log/supervisor/backend.err.log | tail -5
```

**Output esperado:**
```
INFO:scheduler_tesoreria:[Scheduler Tesorería] Iniciado
INFO:scheduler_email_monitor:[EmailMonitorScheduler] ✅ Iniciado
```

### 2. Verificar Cuentas en Base de Datos

```bash
cd /app/backend && python3 << 'EOF'
import asyncio
from cuentas_proveedor_service import cuentas_proveedor_service

async def check():
    capital = await cuentas_proveedor_service.obtener_cuenta_activa("capital")
    comision = await cuentas_proveedor_service.obtener_cuenta_activa("comision_dns")
    
    print("Capital CLABE:", capital.get('clabe'))
    print("Comisión DNS CLABE:", comision.get('clabe'))
    
    assert capital.get('clabe') == '012680001255709482', "CLABE capital incorrecta"
    assert comision.get('clabe') == '058680000012912655', "CLABE comisión incorrecta"
    print("✅ CLABEs correctas")

asyncio.run(check())
EOF
```

### 3. Generar un Layout Nuevo y Verificar

```bash
# Ejecutar tests completos
cd /app/backend && python3 tests/test_completo_tesoreria_layout_adjuntos.py

# Ver último layout generado
ls -lht /app/backend/uploads/layouts_operaciones/ | head -3

# Ver contenido del último layout
ULTIMO=$(ls -t /app/backend/uploads/layouts_operaciones/*.csv | head -1)
echo "Verificando: $ULTIMO"
cat "$ULTIMO"

# Verificar CLABE comisión DNS en la última fila
tail -1 "$ULTIMO" | grep "058680000012912655"
```

### 4. Limpiar Operaciones Antiguas (Si Es Necesario)

Si el usuario está viendo operaciones antiguas generadas antes de los fixes:

```bash
cd /app/backend && python3 << 'EOF'
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def limpiar_flags():
    client = AsyncIOMotorClient(os.getenv('MONGO_URL'))
    db = client[os.getenv('DB_NAME', 'netcash_mbco')]
    
    # Resetear flags de envío de correo para permitir regenerar
    # SOLO SI ES NECESARIO PARA TESTING
    result = await db.solicitudes_netcash.update_many(
        {'correo_tesoreria_enviado': True},
        {'$set': {'correo_tesoreria_enviado': False}}
    )
    
    print(f"Flags reseteados: {result.modified_count} operación(es)")

# DESCOMENTAR SOLO SI ES NECESARIO
# asyncio.run(limpiar_flags())
print("Para resetear flags, descomentar la última línea")
EOF
```

---

## 📧 Estructura del Correo a Tesorería

### Ejemplo de Correo Correcto:

```
De: bbvanetcashbot@gmail.com
Para: dfgalezzo@hotmail.com (o email configurado)
Asunto: NetCash – Orden de dispersión MBCO-0023-T-12 – Juan Pérez

📎 Adjuntos:
  1. LTMBCO_MBCOx0023xTx12.csv        ← Layout con formato correcto
  2. comprobante_250000.pdf            ← Comprobante original del cliente
  3. comprobante_adicional.pdf         ← Otro comprobante si hay más

Cuerpo del email:
  Operación NetCash: MBCO-0023-T-12
  Cliente: Juan Pérez
  Total de depósitos: $250,000.00
  
  Se adjunta:
  - Layout CSV para dispersión
  - Comprobantes de pago del cliente
  
  Por favor procesar según layout.
```

---

## 🔍 Cómo Probar End-to-End Desde el Usuario

### Paso 1: Crear una Nueva Operación

1. Cliente sube comprobante válido al bot
2. Ana asigna folio_mbco
3. Sistema genera layout y envía correo

### Paso 2: Verificar el Email

**Revisar:**
- ✅ Asunto contiene folio correcto
- ✅ Adjunto CSV con nombre `LTMBCO_{folio_con_x}.csv`
- ✅ Adjuntos de comprobantes del cliente (todos los válidos)
- ✅ Solo UN correo por operación

### Paso 3: Verificar el Layout CSV

**Abrir el CSV y verificar:**
- ✅ Filas de capital tienen CLABE: `012680001255709482`
- ✅ Beneficiario capital: `AFFORDABLE MEDICAL SERVICES SC`
- ✅ Última fila (comisión) tiene CLABE: `058680000012912655`
- ✅ Beneficiario comisión: `COMERCIALIZADORA UETACOP SA DE CV`
- ✅ Monto comisión = 0.375% del capital

### Paso 4: Probar Duplicados

**Test de duplicado entre operaciones:**
1. Crear operación A con comprobante X
2. Intentar crear operación B con el MISMO comprobante X
3. Resultado esperado:
   ```
   ⚠️ Este comprobante ya fue utilizado en otra operación NetCash.
   Por favor envía un comprobante diferente para continuar.
   ```

---

## 🐛 Errores Comunes y Soluciones

### Problema 1: "Layout tiene CLABE incorrecta"

**Diagnóstico:**
```bash
# Verificar cuentas en BD
cd /app/backend && python3 -c "
import asyncio
from cuentas_proveedor_service import cuentas_proveedor_service

async def check():
    comision = await cuentas_proveedor_service.obtener_cuenta_activa('comision_dns')
    print('CLABE comisión DNS:', comision.get('clabe'))

asyncio.run(check())
"
```

**Solución:**
Si la CLABE es incorrecta, actualizar en BD:
```bash
# Conectar a MongoDB y actualizar
mongosh netcash_mbco

db.cuentas_proveedor_netcash.updateOne(
  {tipo: "comision_dns"},
  {$set: {clabe: "058680000012912655"}}
)
```

### Problema 2: "Comprobantes no se adjuntan"

**Diagnóstico:**
```bash
# Ver logs del envío de correo
grep "Adjuntando comprobante" /var/log/supervisor/backend.err.log | tail -10
grep "Adjuntos totales" /var/log/supervisor/backend.err.log | tail -10
```

**Causas posibles:**
- Comprobantes marcados como `es_valido: False`
- Campo `archivo_url` vacío o ruta no existe
- Comprobantes duplicados (no se adjuntan)

**Solución:**
Verificar comprobantes en BD:
```javascript
db.solicitudes_netcash.findOne(
  {id: "nc-XXXX"},
  {comprobantes: 1}
)

// Verificar que tengan:
// - es_valido: true
// - es_duplicado: false
// - archivo_url: "/app/backend/uploads/comprobantes_telegram/..."
```

### Problema 3: "Recibo 2 correos"

**Diagnóstico:**
```bash
# Buscar en logs
grep "CORREO YA ENVIADO" /var/log/supervisor/backend.err.log
grep "Correo enviado a" /var/log/supervisor/backend.err.log | tail -20
```

**Verificar flag en BD:**
```javascript
db.solicitudes_netcash.find(
  {folio_mbco: "MBCO-0023-T-12"},
  {correo_tesoreria_enviado: 1, fecha_envio_tesoreria: 1}
)
```

**Solución:**
Si el flag no se está guardando, revisar que el servicio esté actualizado.

### Problema 4: "Duplicado no se detecta"

**Diagnóstico:**
```bash
# Ver logs de detección
grep "DUPLICADO GLOBAL detectado" /var/log/supervisor/backend.err.log
grep "Hash del archivo" /var/log/supervisor/backend.err.log | tail -10
```

**Verificar que el hash se calcula:**
```bash
# Simular cálculo de hash
cd /app/backend && python3 << 'EOF'
import hashlib

def calcular_hash(ruta):
    with open(ruta, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

# Usar ruta real de comprobante
hash1 = calcular_hash("/app/backend/uploads/test_250k.pdf")
print(f"Hash: {hash1}")
EOF
```

---

## ✅ Checklist Final de Verificación

Antes de reportar un problema, verificar:

- [ ] Backend reiniciado después de cambios
- [ ] Schedulers corriendo (Tesorería + Email Monitor)
- [ ] Cuentas proveedor correctas en BD
- [ ] Layout generado tiene formato correcto
- [ ] Tests automatizados pasando (5/5)
- [ ] Logs sin errores relevantes
- [ ] Operación nueva (no antigua pre-fix)

---

## 📞 Información de Soporte

**Si persisten problemas después de verificar:**

1. Ejecutar tests automatizados:
   ```bash
   cd /app/backend && python3 tests/test_completo_tesoreria_layout_adjuntos.py
   ```

2. Capturar logs relevantes:
   ```bash
   grep -A 20 "ERROR" /var/log/supervisor/backend.err.log | tail -50
   ```

3. Compartir:
   - Output de tests
   - Logs de error
   - Folio de operación problemática
   - Screenshots del layout CSV

---

## 🎯 Estado Actual Confirmado

**Sistema funcionando correctamente:**
- ✅ 5/5 tests pasados
- ✅ Layout con CLABEs correctas
- ✅ Comprobantes adjuntados
- ✅ Anti-duplicados funcionando
- ✅ Detección duplicados entre operaciones

**Próximos pasos recomendados:**
1. Usuario ejecuta prueba end-to-end con operación nueva
2. Verifica correo recibido en Tesorería
3. Revisa layout CSV adjunto
4. Confirma que comprobantes del cliente están adjuntos
5. Prueba duplicados entre operaciones
