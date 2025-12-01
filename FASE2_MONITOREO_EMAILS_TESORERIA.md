# 📧 Fase 2: Monitoreo de Emails de Tesorería - Documentación Completa

## 📋 Resumen

Este documento explica la implementación de la **Fase 2** del flujo de Tesorería: el sistema automatizado de monitoreo de respuestas de emails que detecta cuando Tesorería (Toño) responde con comprobantes de dispersión, actualiza el estado de la operación y notifica a Ana y al cliente.

---

## 🎯 Objetivo

**Cerrar el ciclo completo del flujo de Tesorería:**

1. ✅ Ana asigna folio → Se genera layout y se envía email a Tesorería (**Ya implementado - Fase 1**)
2. ✅ **Tesorería responde con comprobantes → Sistema detecta, guarda adjuntos y notifica (NUEVO - Fase 2)**

---

## 🔧 Componentes Implementados

### 1. **Servicio de Monitoreo de Emails**
**Archivo:** `/app/backend/tesoreria_email_monitor_service.py`

Este servicio:
- Se conecta a Gmail API para leer emails no leídos
- Identifica cuáles son respuestas de operaciones NetCash
- Descarga comprobantes adjuntos (PDFs)
- Actualiza estado de la operación a `dispersada_proveedor`
- Notifica a Ana y al cliente vía Telegram

**Clase principal:** `TesoreriaEmailMonitorService`

**Métodos clave:**
- `procesar_respuestas_pendientes()`: Procesa todos los emails no leídos
- `_identificar_operacion()`: Asocia un email con una operación usando Thread-ID o folio_mbco
- `_procesar_respuesta_operacion()`: Descarga adjuntos, actualiza BD y notifica
- `_notificar_dispersion()`: Envía notificaciones Telegram a Ana y cliente

### 2. **Scheduler Automático**
**Archivo:** `/app/backend/scheduler_email_monitor.py`

Ejecuta el monitoreo de emails cada **15 minutos** automáticamente.

**Clase principal:** `EmailMonitorScheduler`

**Frecuencia:** 15 minutos (configurable en `self.intervalo_minutos`)

### 3. **Actualización de Gmail Service**
**Archivo:** `/app/backend/gmail_service.py`

Se modificó el método `enviar_correo_con_adjuntos()` para que devuelva:
```python
{
    'message_id': 'ABC123...',
    'thread_id': 'XYZ789...'
}
```

Esto permite guardar el `thread_id` en la BD para asociar respuestas futuras.

### 4. **Actualización de Tesorería Operación Service**
**Archivo:** `/app/backend/tesoreria_operacion_service.py`

Se modificó `_enviar_correo_operacion()` para:
- Capturar el `thread_id` del email enviado
- Guardarlo en la solicitud en BD (`email_thread_id` y `email_message_id`)

### 5. **Integración en Server**
**Archivo:** `/app/backend/server.py`

El scheduler se inicia automáticamente al arrancar el backend:
```python
@app.on_event("startup")
async def startup_event():
    # ... otros inicios ...
    
    from scheduler_email_monitor import email_monitor_scheduler
    email_monitor_scheduler.start()
```

---

## 🔑 Variables de Entorno Requeridas

### Gmail API (para monitoreo de emails)
```bash
GMAIL_USER=bbvanetcashbot@gmail.com
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
GMAIL_REFRESH_TOKEN=...
```

### Email de Tesorería (opcional, para validación)
```bash
TESORERIA_GMAIL_USER=tono@example.com
```

**⚠️ Importante:**
- Si las credenciales de Gmail **NO** están configuradas, el sistema:
  - ✅ Continúa funcionando normalmente
  - ✅ Genera layouts y guarda adjuntos localmente
  - ⚠️ NO podrá enviar emails ni monitorear respuestas
  - 📝 Registra en logs: `"Gmail no configurado – correo no enviado, layout guardado localmente"`

---

## 🔄 Flujo Completo de la Fase 2

### 1. Envío de Operación a Tesorería (Ya existente - Fase 1)

```
Ana asigna folio_mbco
    ↓
tesoreria_operacion_service.procesar_operacion_tesoreria()
    ↓
Se genera CSV layout
    ↓
Se envía email a Tesorería con adjuntos
    ↓
Se guarda thread_id en BD (NUEVO):
    email_thread_id: "abc123..."
    email_message_id: "xyz789..."
    ↓
Estado: enviado_a_tesoreria
```

### 2. Monitoreo de Respuestas (NUEVO - Fase 2)

```
Scheduler ejecuta cada 15 minutos
    ↓
tesoreria_email_monitor.procesar_respuestas_pendientes()
    ↓
Lee emails no leídos del inbox
    ↓
Para cada email:
    ├─ Identifica operación asociada:
    │   ├─ Por thread_id (más confiable)
    │   ├─ Por folio_mbco en asunto/cuerpo
    │   └─ Si no identifica → Ignorar
    │
    ├─ Descarga adjuntos PDF
    │   └─ Guarda en /app/backend/uploads/comprobantes_dispersion/
    │
    ├─ Actualiza BD:
    │   ├─ estado: "dispersada_proveedor"
    │   ├─ comprobantes_dispersion: [...]
    │   ├─ fecha_dispersion_proveedor: timestamp
    │   └─ email_respuesta_tesoreria: {...}
    │
    ├─ Notifica vía Telegram:
    │   ├─ A Ana: "✅ Operación [folio] dispersada"
    │   └─ Al Cliente: "✅ Tus ligas están en proceso"
    │
    └─ Marca email como leído
        └─ Agrega etiqueta "NETCASH/PROCESADO"
```

---

## 🗄️ Estructura de Datos en MongoDB

### Campos agregados a `solicitudes_netcash`:

```javascript
{
  // Campos existentes...
  "estado": "dispersada_proveedor",  // Nuevo estado
  
  // NUEVOS - Fase 1 (envío)
  "email_thread_id": "1234567890abcdef",  // Thread de Gmail
  "email_message_id": "abc123xyz789",      // ID del mensaje enviado
  
  // NUEVOS - Fase 2 (respuesta)
  "comprobantes_dispersion": [
    {
      "nombre_archivo": "comprobante_dispersion_proveedor.pdf",
      "ruta": "/app/backend/uploads/comprobantes_dispersion/nc-123_comprobante.pdf",
      "tamano_bytes": 45678,
      "fecha_descarga": "2025-12-01T15:30:00Z"
    }
  ],
  "fecha_dispersion_proveedor": "2025-12-01T15:30:00Z",
  "email_respuesta_tesoreria": {
    "message_id": "resp_xyz789",
    "thread_id": "1234567890abcdef",
    "from": "tono@example.com",
    "subject": "Re: NetCash – Orden de dispersión MBCO-0001-T-12",
    "fecha_recibido": "2025-12-01T15:30:00Z"
  }
}
```

### Estados del Flujo Completo:

```
borrador
    ↓
lista_para_mbc
    ↓
orden_interna_generada
    ↓
enviado_a_tesoreria  ← Fase 1
    ↓
dispersada_proveedor ← Fase 2 (NUEVO)
    ↓
en_proceso_mbc
    ↓
completada
```

---

## 📧 Estrategias de Identificación de Operaciones

El sistema usa **3 estrategias** para asociar un email con una operación:

### Estrategia 1: Thread-ID (Más confiable) ⭐
```python
# Busca operaciones con el thread_id del email
solicitud = await db.solicitudes_netcash.find_one({
    "email_thread_id": thread_id,
    "estado": "enviado_a_tesoreria"
})
```

### Estrategia 2: folio_mbco en asunto o cuerpo
```python
# Busca patrones como: MBCO-0001-T-12, TEST-001-T-43
patron_folio = r'[A-Z]{4}-\d{4}-[A-Z]-\d{2}'
folios = re.findall(patron_folio, subject + body)
```

### Estrategia 3: Fallback (requiere revisión manual)
```python
# Si el remitente es de Tesorería y tiene PDFs adjuntos
# pero no se puede identificar el folio/thread
# → Log de advertencia para revisión manual
```

---

## 📝 Notificaciones Telegram

### A Ana (admin):
```
✅ Operación dispersada al proveedor

📋 Folio: MBCO-0023-T-12
👤 Cliente: Juan Pérez
💰 Total: $150,000.00
📎 Comprobantes recibidos: 2

Los comprobantes de dispersión se recibieron de Tesorería 
y la operación está lista para continuar.
```

### Al Cliente:
```
✅ ¡Tu operación NetCash está en proceso!

📋 Folio: MBCO-0023-T-12
💰 Total: $150,000.00

Tus depósitos ya fueron enviados a NetCash para la 
generación de ligas.

Te notificaremos cuando tus ligas estén listas.
```

---

## 🧪 Testing Manual

### 1. Verificar que el scheduler esté corriendo:
```bash
tail -f /var/log/supervisor/backend.err.log | grep EmailMonitor
```

Deberías ver cada 15 minutos:
```
[EmailMonitorScheduler] Ejecutando job de monitoreo de emails...
[EmailMonitor] ========== INICIANDO PROCESAMIENTO DE RESPUESTAS ==========
[EmailMonitor] No hay mensajes no leídos para procesar
```

### 2. Simular una respuesta de Tesorería:

**Paso 1:** Obtener una operación en estado `enviado_a_tesoreria`:
```bash
cd /app/backend && python3 -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def buscar():
    client = AsyncIOMotorClient(os.getenv('MONGO_URL'))
    db = client[os.getenv('DB_NAME', 'netcash_mbco')]
    
    ops = await db.solicitudes_netcash.find(
        {'estado': 'enviado_a_tesoreria'},
        {'_id': 0, 'id': 1, 'folio_mbco': 1, 'email_thread_id': 1}
    ).to_list(5)
    
    for op in ops:
        print(f\"ID: {op['id']}, Folio: {op.get('folio_mbco')}, Thread: {op.get('email_thread_id')}\")

asyncio.run(buscar())
"
```

**Paso 2:** Enviar un email de prueba respondiendo al thread con un PDF adjunto

**Paso 3:** Esperar a que el scheduler procese (máx 15 mins) o ejecutar manualmente:
```bash
cd /app/backend && python3 -c "
import asyncio
from tesoreria_email_monitor_service import tesoreria_email_monitor

asyncio.run(tesoreria_email_monitor.procesar_respuestas_pendientes())
"
```

### 3. Verificar que se actualizó el estado:
```bash
cd /app/backend && python3 -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json

async def verificar():
    client = AsyncIOMotorClient(os.getenv('MONGO_URL'))
    db = client[os.getenv('DB_NAME', 'netcash_mbco')]
    
    ops = await db.solicitudes_netcash.find(
        {'estado': 'dispersada_proveedor'},
        {'_id': 0}
    ).to_list(5)
    
    print(json.dumps(ops, indent=2, default=str))

asyncio.run(verificar())
"
```

---

## 🐛 Troubleshooting

### Problema: "Gmail no configurado"
**Causa:** Faltan variables de entorno para Gmail API

**Solución:**
1. Configurar las variables:
   ```bash
   GMAIL_USER=...
   GMAIL_CLIENT_ID=...
   GMAIL_CLIENT_SECRET=...
   GMAIL_REFRESH_TOKEN=...
   ```
2. Reiniciar backend:
   ```bash
   sudo supervisorctl restart backend
   ```

### Problema: No se detectan respuestas de Tesorería
**Causas posibles:**
1. El thread_id no coincide (Gmail creó un thread nuevo)
2. El folio no está en el asunto del email de respuesta
3. El remitente no es el esperado

**Debugging:**
```bash
# Ver logs del monitor
grep "EmailMonitor" /var/log/supervisor/backend.err.log | tail -50

# Ver operaciones pendientes
cd /app/backend && python3 -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def check():
    client = AsyncIOMotorClient(os.getenv('MONGO_URL'))
    db = client[os.getenv('DB_NAME', 'netcash_mbco')]
    
    count = await db.solicitudes_netcash.count_documents({'estado': 'enviado_a_tesoreria'})
    print(f'Operaciones pendientes de dispersión: {count}')

asyncio.run(check())
"
```

### Problema: Los adjuntos no se descargan
**Causa:** Error de permisos o ruta inexistente

**Solución:**
```bash
# Crear directorio si no existe
mkdir -p /app/backend/uploads/comprobantes_dispersion
chmod 755 /app/backend/uploads/comprobantes_dispersion

# Verificar archivos descargados
ls -lh /app/backend/uploads/comprobantes_dispersion/
```

---

## 📊 Monitoreo y Estadísticas

### Ver operaciones dispersadas hoy:
```bash
cd /app/backend && python3 -c "
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
import os

async def stats():
    client = AsyncIOMotorClient(os.getenv('MONGO_URL'))
    db = client[os.getenv('DB_NAME', 'netcash_mbco')]
    
    hoy = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    count = await db.solicitudes_netcash.count_documents({
        'estado': 'dispersada_proveedor',
        'fecha_dispersion_proveedor': {'\$gte': hoy}
    })
    
    print(f'Operaciones dispersadas hoy: {count}')

asyncio.run(stats())
"
```

### Ver última ejecución del scheduler:
```bash
tail -20 /var/log/supervisor/backend.err.log | grep "EmailMonitorScheduler"
```

---

## ✅ Checklist de Validación

Para verificar que la Fase 2 está funcionando correctamente:

- [ ] Scheduler de emails está corriendo (ver logs cada 15 mins)
- [ ] Variables de entorno de Gmail configuradas
- [ ] Al enviar una operación a Tesorería, se guarda `email_thread_id`
- [ ] Al responder con PDF adjunto, el sistema:
  - [ ] Detecta el email
  - [ ] Asocia con la operación correcta
  - [ ] Descarga el PDF a `/app/backend/uploads/comprobantes_dispersion/`
  - [ ] Actualiza el estado a `dispersada_proveedor`
  - [ ] Notifica a Ana por Telegram
  - [ ] Notifica al cliente por Telegram
  - [ ] Marca el email como leído
  - [ ] Agrega etiqueta "NETCASH/PROCESADO"

---

## 🔜 Próximos Pasos (Futuro)

1. **Dashboard de monitoreo:** Panel para ver operaciones por estado en tiempo real
2. **Alertas por timeout:** Si una operación lleva >48h en `enviado_a_tesoreria`, alertar a Ana
3. **Reenvío automático:** Botón para reenviar el email de operación si Tesorería no responde
4. **Historial de emails:** Ver todos los emails relacionados a una operación

---

## 📚 Archivos Relacionados

| Archivo | Descripción |
|---------|-------------|
| `/app/backend/tesoreria_email_monitor_service.py` | Servicio principal de monitoreo |
| `/app/backend/scheduler_email_monitor.py` | Scheduler para ejecución periódica |
| `/app/backend/gmail_service.py` | Servicio de Gmail API (actualizado) |
| `/app/backend/tesoreria_operacion_service.py` | Envío de operaciones (actualizado) |
| `/app/backend/server.py` | Integración de schedulers (actualizado) |
| `/app/FASE2_MONITOREO_EMAILS_TESORERIA.md` | Este documento |

---

## 🎉 Resumen

La Fase 2 completa el ciclo automatizado de Tesorería:
- ✅ Detecta automáticamente respuestas de Tesorería
- ✅ Descarga y guarda comprobantes de dispersión
- ✅ Actualiza estados sin intervención manual
- ✅ Notifica a todos los involucrados
- ✅ Funciona sin Gmail (modo degradado con logs)

**El flujo completo ahora es 100% automatizado de principio a fin.**
