# 🛡️ Manejo Robusto de Errores - Botón "Continuar" (P0)

## 📋 Resumen

Este documento explica el sistema de manejo de errores reforzado implementado en el handler `continuar_desde_paso1` del flujo de Telegram NetCash.

**Objetivo:** Blindar el flujo crítico de validación de comprobantes para que:
- Los errores queden trazados con ID único
- Los comprobantes del usuario no se pierdan
- El usuario reciba un mensaje claro y no se quede bloqueado
- Ana pueda rescatar y continuar manualmente las operaciones afectadas

---

## 🔍 ¿Qué se reforzó?

### 1. Try/Catch Global
Todo el handler `continuar_desde_paso1` está envuelto en un `try/except` que captura **cualquier** excepción.

### 2. ID de Error Único
Cada error genera un ID único con el formato:
```
ERR_CONTINUAR_YYYYMMDD_HHMMSS_XXXX
```

Ejemplo: `ERR_CONTINUAR_20251201_143527_8432`

### 3. Logging Detallado
Cuando ocurre un error, se registra:
- ✅ ID de error único
- ✅ Solicitud ID
- ✅ Telegram User ID del cliente
- ✅ Lista de nombres de archivos de comprobantes
- ✅ Total depositado calculado (si llegó a calcular)
- ✅ Tipo de excepción
- ✅ Mensaje de error completo
- ✅ Stack trace completo

**Ubicación de logs:** `/var/log/supervisor/backend.err.log`

**Buscar errores:**
```bash
grep "ERR_CONTINUAR" /var/log/supervisor/backend.err.log
```

### 4. Marcado Automático para Revisión Manual
La solicitud afectada se marca en la BD con:
```json
{
  "requiere_revision_manual": true,
  "error_id": "ERR_CONTINUAR_20251201_143527_8432",
  "error_timestamp": "2025-12-01T14:35:27.123456",
  "error_detalle": {
    "handler": "continuar_desde_paso1",
    "tipo": "ValueError",
    "mensaje": "...",
    "telegram_user_id": 7631636750
  }
}
```

### 5. Mensaje Claro al Usuario
En lugar del mensaje genérico anterior:
```
❌ Error al procesar tu solicitud. Por favor contacta a soporte.
```

El usuario ahora recibe:
```
❌ Tuvimos un problema interno al continuar con tu solicitud.

✅ Tus comprobantes SÍ se guardaron y están a salvo.

👤 Ana o un enlace de nuestro equipo te contactarán pronto para ayudarte a continuar con tu operación.

📋 ID de seguimiento: ERR_CONTINUAR_20251201_143527_8432

Por favor comparte este ID si contactas a soporte.
```

### 6. Log Específico para Montos Grandes
Cuando el total de depósitos es ≥ $1,000,000, se genera un log adicional:
```
[DEBUG_CONTINUAR] ⚠️ Monto alto detectado: $1,045,000.00 en solicitud nc-1764555486884
[DEBUG_CONTINUAR] Comprobantes con montos grandes: ['comprobante_1045000.pdf']
```

---

## 🔧 Cómo Rescatar Solicitudes con Errores

### Opción 1: Consulta MongoDB Directa

```bash
cd /app/backend && python3 -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json

async def buscar_solicitudes_error():
    mongo_url = os.getenv('MONGO_URL')
    db_name = os.getenv('DB_NAME', 'netcash_mbco')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    solicitudes = await db.solicitudes_netcash.find(
        {'requiere_revision_manual': True},
        {'_id': 0, 'id': 1, 'error_id': 1, 'error_timestamp': 1, 
         'cliente_id': 1, 'comprobantes.nombre_archivo': 1,
         'estado': 1, 'error_detalle': 1}
    ).to_list(100)
    
    print(json.dumps(solicitudes, indent=2, default=str))

asyncio.run(buscar_solicitudes_error())
"
```

### Opción 2: Flujo de Ana (Futuro)
Se puede implementar un comando en el bot de Ana tipo:
```
/solicitudes_pendientes
```
Que muestre las solicitudes marcadas con `requiere_revision_manual: true`.

---

## 📊 Estadísticas y Monitoreo

### Ver últimos errores del botón Continuar
```bash
grep "ERR_CONTINUAR" /var/log/supervisor/backend.err.log | tail -20
```

### Ver detalles de un error específico
```bash
grep "ERR_CONTINUAR_20251201_143527_8432" /var/log/supervisor/backend.err.log
```

### Contar solicitudes que requieren revisión manual
```bash
cd /app/backend && python3 -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def contar():
    mongo_url = os.getenv('MONGO_URL')
    db_name = os.getenv('DB_NAME', 'netcash_mbco')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    count = await db.solicitudes_netcash.count_documents({'requiere_revision_manual': True})
    print(f'Solicitudes que requieren revisión manual: {count}')

asyncio.run(contar())
"
```

---

## 🧪 Testing

Se creó un test exhaustivo en:
```
/app/backend/tests/test_bug_comprobante_1045000.py
```

**Ejecutar test:**
```bash
cd /app/backend && python3 tests/test_bug_comprobante_1045000.py
```

Este test simula el flujo completo con un comprobante de $1,045,000 y verifica que:
- ✅ El validador procesa correctamente
- ✅ El total se calcula sin errores
- ✅ El mensaje se formatea correctamente
- ✅ El flujo avanza al paso 2 sin problemas

---

## 📝 Notas Importantes

1. **Los comprobantes NO se pierden:** Cuando ocurre un error, los archivos ya están guardados en `/app/backend/uploads/comprobantes_telegram/` y el registro en la BD existe con toda la información.

2. **El estado NO se corrompe:** La solicitud permanece en estado `borrador` y puede ser continuada manualmente.

3. **Trazabilidad completa:** Cada error tiene un ID único que conecta:
   - Log en archivo
   - Registro en BD
   - Mensaje al usuario

4. **No bloquea al usuario:** El usuario puede intentar de nuevo o esperar contacto del equipo.

---

## 🔄 Flujo de Rescate Manual (Para Ana)

Cuando una solicitud tiene `requiere_revision_manual: true`:

1. **Identificar la solicitud:**
   - ID de solicitud: `nc-XXXXXXXXXXXXX`
   - Error ID: `ERR_CONTINUAR_YYYYMMDD_HHMMSS_XXXX`
   - Telegram User ID del cliente

2. **Verificar comprobantes:**
   - Los archivos están en `/app/backend/uploads/comprobantes_telegram/`
   - El registro `comprobantes` en la BD tiene toda la info de validación

3. **Continuar manualmente:**
   - Opción A: Ana puede crear una nueva solicitud con los datos correctos
   - Opción B: Se puede implementar un comando especial para Ana que permita "retomar" la solicitud desde el paso 2

4. **Limpiar el flag:**
   ```python
   await db.solicitudes_netcash.update_one(
       {"id": "nc-XXXXXXXXXXXXX"},
       {"$unset": {"requiere_revision_manual": "", "error_id": ""}}
   )
   ```

---

## ✅ Resultado

Con esta implementación, el flujo del botón "Continuar" está **blindado** contra errores inesperados:
- ✅ Trazabilidad completa
- ✅ Preservación de datos
- ✅ Mensaje claro al usuario
- ✅ Capacidad de rescate manual
- ✅ Monitoreo específico para montos grandes

El usuario nunca pierde su progreso y el equipo tiene toda la información necesaria para ayudar.
