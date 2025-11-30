# Flujo Ana → Tesorería - NetCash

## 📋 Resumen

Implementación del flujo completo desde que una solicitud NetCash queda lista hasta que se genera la orden interna para Tesorería.

**Fecha**: Diciembre 2025  
**Tipo**: Feature - Flujo administrativo  

---

## 🎯 Flujo Implementado

```
Cliente confirma operación
         ↓
Estado: "lista_para_mbc"
         ↓
🔔 Notificación a Ana (Telegram)
         ↓
Ana asigna folio MBco
         ↓
Se genera orden interna para Tesorería
         ↓
📧 Correo a Tesorería (layout + comprobantes)
         ↓
🔔 Notificación a Tesorería (Telegram)
         ↓
[Hook para futuro: Tesorería confirma envío de ligas]
```

---

## 🚀 Componentes Implementados

### 1. Configuración de Telegram IDs

**Archivo**: `/app/backend/telegram_config.py`

**Constantes principales:**
```python
TELEGRAM_ID_ANA = 76316336750  # ID de Ana (admin MBco)
TELEGRAM_ID_TESORERIA = 76316336750  # ID de Tesorería
```

**⚠️ IMPORTANTE PARA PRODUCCIÓN:**

Estos IDs están configurados para PRUEBAS. Antes de desplegar a producción:

```python
# Cambiar en /app/backend/telegram_config.py:

# PRODUCCIÓN:
TELEGRAM_ID_ANA = 1720830607  # ID real de Ana
TELEGRAM_ID_TESORERIA = XXXXXXXX  # ID real de grupo/usuario de Tesorería
```

**Manejo de roles por contexto:**

El usuario 76316336750 puede actuar en 2 roles según el CONTEXTO:

1. **Como CLIENTE** (flujo normal):
   - Entra con /start
   - Crea operaciones NetCash
   - Usa menú de cliente

2. **Como ANA** (flujo admin):
   - Recibe notificaciones del sistema
   - Presiona botón [Asignar folio MBco]
   - Asigna folios MBco

El rol se determina por el FLUJO activo, NO por un campo en BD.

---

### 2. Handler de Ana (Admin MBco)

**Archivo**: `/app/backend/telegram_ana_handlers.py`

**Funciones principales:**

#### `notificar_nueva_solicitud_para_mbco(solicitud)`

Se llama automáticamente cuando una solicitud queda en estado `lista_para_mbc`.

**Mensaje enviado a Ana:**
```
🧾 Nueva solicitud NetCash lista para MBco

📋 Folio NetCash: NC-000010
👤 Cliente ID: abc123
🏢 Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV
🆔 IDMEX: 1234567890
💰 Total depósitos: $1,000,000.00
📊 Comisión NetCash (1%): $10,000.00
💸 Monto a enviar (ligas): $990,000.00
🔗 Número de ligas: 5
📅 Fecha creación: 01/12/2025 10:30

Botones:
[📝 Asignar folio MBco]  [🌐 Ver en la web]
```

#### `iniciar_asignacion_folio(update, context)`

Se ejecuta cuando Ana presiona [Asignar folio MBco].

**Flujo:**
1. Verificar que el usuario es Ana
2. Solicitar folio MBco
3. Guardar contexto de la solicitud

**Mensaje:**
```
📝 Asignación de folio MBco

Por favor, escribe el folio de operación MBco para esta solicitud.
Ejemplo: MB-2025-0007

ℹ️ El folio debe ser único y no estar asignado a otra solicitud.
```

#### `recibir_folio_mbco(update, context)`

Se ejecuta cuando Ana envía el texto del folio.

**Validaciones:**
- No vacío
- Longitud mínima 3 caracteres
- Folio no existe en otra solicitud

**Si es válido:**
- Llama a `asignar_folio_mbco_y_generar_orden_interna()`
- Muestra confirmación con detalles

**Si es inválido:**
- Muestra error
- Pide folio de nuevo sin perder contexto

---

### 3. Servicio de Dominio (Orquestación)

**Archivo**: `/app/backend/netcash_service.py`

#### `asignar_folio_mbco_y_generar_orden_interna(solicitud_id, folio_mbco, usuario_asigna)`

**Punto de orquestación central que:**

1. **Asigna folio MBco:**
   ```python
   update_data = {
       "folio_mbco": folio_mbco,
       "estado": "orden_interna_generada",
       "fecha_asignacion_mbco": datetime.now(timezone.utc),
       "usuario_asigna_mbco": usuario_asigna
   }
   ```

2. **Genera orden interna:**
   ```python
   orden_interna = {
       "id": "OI-abc12345",
       "folio_netcash": "NC-000010",
       "folio_mbco": "MB-2025-0007",
       "estado": "pendiente_envio_ligas",
       "beneficiario": "JARDINERIA Y COMERCIO...",
       "num_ligas": 5,
       "monto_total_ligas": 990000.00,
       "monto_por_liga": 198000.00,
       "comprobantes_adjuntos": [...]
   }
   ```
   
   Guardado en colección: `ordenes_internas_tesoreria`

3. **Envía correo a Tesorería** (mock por ahora):
   ```python
   await _enviar_correo_tesoreria(solicitud_id, orden_interna)
   ```

4. **Notifica a Tesorería por Telegram:**
   ```python
   await _notificar_tesoreria_telegram(solicitud_id, orden_interna)
   ```

**Retorno:**
```python
{
    "success": True,
    "solicitud": {...},  # Solicitud actualizada
    "orden_interna": {...}  # Orden generada
}
```

---

### 4. Handler de Tesorería

**Archivo**: `/app/backend/telegram_tesoreria_handlers.py`

#### `notificar_nueva_orden_interna(orden_interna)`

**Mensaje enviado a Tesorería:**
```
📦 Nueva orden interna de Tesorería

🆔 Orden Interna: OI-abc12345
📋 Folio NetCash: NC-000010
🏢 Folio MBco: MB-2025-0007
👤 Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV
🆔 IDMEX: 1234567890

💰 Detalle de pago:
  • Total a enviar: $990,000.00
  • Número de ligas: 5
  • Monto por liga: $198,000.00

📎 Comprobantes adjuntos: 3
📅 Fecha creación: 01/12/2025 10:35

📧 Revisa tu correo para el layout completo y los comprobantes adjuntos.

ℹ️ Una vez que hayas enviado las ligas al proveedor, podrás confirmar el envío aquí.

Botones:
[📋 Ver detalles]
```

#### `ver_detalles_orden(update, context)`

Muestra detalles de la orden (placeholder por ahora).

**Futuro:** Consultar orden de BD y mostrar información completa.

---

## 🔄 Integración en el Bot Principal

**Archivo**: `/app/backend/telegram_bot.py`

**Cambios realizados:**

1. **Importar handlers:**
```python
from telegram_ana_handlers import init_ana_handlers, ANA_ESPERANDO_FOLIO_MBCO
from telegram_tesoreria_handlers import init_tesoreria_handlers

self.ana_handlers = init_ana_handlers(self)
self.tesoreria_handlers = init_tesoreria_handlers(self)
```

2. **Agregar conversation handler para Ana:**
```python
conv_handler_ana = ConversationHandler(
    entry_points=[CallbackQueryHandler(self.ana_handlers.iniciar_asignacion_folio, pattern="^ana_asignar_folio_")],
    states={
        ANA_ESPERANDO_FOLIO_MBCO: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.ana_handlers.recibir_folio_mbco)
        ]
    },
    fallbacks=[CommandHandler("cancelar", self.ana_handlers.cancelar)]
)
```

3. **Agregar handler para botones de Tesorería:**
```python
self.app.add_handler(CallbackQueryHandler(self.tesoreria_handlers.ver_detalles_orden, pattern="^tesor_ver_orden_"))
```

---

## 🗄️ Estructura de Datos

### Solicitud NetCash (actualizada)

**Colección**: `solicitudes_netcash`

**Campos nuevos:**
```python
{
    "folio_mbco": "MB-2025-0007",  # Asignado por Ana
    "fecha_asignacion_mbco": datetime,
    "usuario_asigna_mbco": "ana_telegram",
    "estado": "orden_interna_generada"  # Nuevo estado
}
```

### Orden Interna Tesorería (nueva)

**Colección**: `ordenes_internas_tesoreria`

**Estructura:**
```python
{
    "id": "OI-abc12345",
    "folio_netcash": "NC-000010",
    "folio_mbco": "MB-2025-0007",
    "solicitud_id": "sol_abc123",
    "estado": "pendiente_envio_ligas",  # Estados: pendiente_envio_ligas, ligas_enviadas, completada
    "beneficiario": "JARDINERIA Y COMERCIO THABYETHA SA DE CV",
    "idmex": "1234567890",
    "num_ligas": 5,
    "monto_total_ligas": 990000.00,
    "monto_por_liga": 198000.00,
    "comprobantes_adjuntos": [
        {
            "nombre": "comprobante1.pdf",
            "url": "/path/to/file",
            "monto": 500000.00
        },
        ...
    ],
    "created_at": datetime,
    "created_by": "ana_mbco"
}
```

---

## 🧪 Testing

### Flujo de Prueba (E2E)

**1. Como Cliente (Crear solicitud):**
```
1. Telegram → /start
2. Crear operación NetCash
3. Subir comprobantes válidos
4. Completar datos (beneficiario, IDMEX, ligas)
5. Confirmar operación
→ Estado: "lista_para_mbc"
```

**2. Como Ana (Asignar folio):**
```
6. Ana recibe notificación automática
7. Ana presiona [Asignar folio MBco]
8. Ana escribe: "MB-2025-0007"
→ Estado: "orden_interna_generada"
→ Se crea orden interna
```

**3. Como Tesorería (Recibir orden):**
```
9. Tesorería recibe notificación automática
10. Tesorería presiona [Ver detalles]
11. Tesorería revisa correo con layout
12. [Futuro] Tesorería confirma envío de ligas
```

### Validar Datos en MongoDB

**Verificar solicitud actualizada:**
```javascript
db.solicitudes_netcash.find({
    folio_netcash: "NC-000010"
})

// Debe tener:
// - folio_mbco: "MB-2025-0007"
// - estado: "orden_interna_generada"
// - fecha_asignacion_mbco: fecha actual
```

**Verificar orden interna creada:**
```javascript
db.ordenes_internas_tesoreria.find({
    folio_mbco: "MB-2025-0007"
})

// Debe existir con todos los datos
```

---

## 🔜 Hooks para Siguiente Fase (NO IMPLEMENTADOS)

### 1. Envío de Correo Real

**Hook**: `_enviar_correo_tesoreria()`

**Por implementar:**
- Configurar SMTP (Gmail, SendGrid, etc.)
- Generar layout HTML/PDF
- Adjuntar comprobantes
- Enviar correo

**Placeholder actual:**
```python
logger.info(f"[NetCash] 📧 Correo a Tesorería (MOCK)")
```

### 2. Confirmación de Envío de Ligas

**Handler futuro**: `confirmar_envio_ligas()`

**Flujo futuro:**
1. Tesorería presiona [✅ Confirmar envío ligas]
2. Sistema cambia estado a 'ligas_enviadas'
3. Se notifica al siguiente paso del flujo

**Hook actual:**
```python
# HOOK PARA FUTURO (NO IMPLEMENTAR AÚN)
async def confirmar_envio_ligas(self, update, context):
    pass
```

### 3. Vista de Detalles de Orden

**Handler**: `ver_detalles_orden()`

**Mejora futura:**
- Consultar orden de BD
- Mostrar detalles completos
- Botones de acción

**Implementación actual:**
```python
mensaje = "🔄 Funcionalidad en desarrollo"
```

---

## 📝 Archivos Creados/Modificados

### Archivos Nuevos:

1. **`/app/backend/telegram_config.py`**
   - Configuración de Telegram IDs
   - Funciones de verificación de roles

2. **`/app/backend/telegram_ana_handlers.py`**
   - Handler completo para Ana
   - Conversation handler para asignación de folio

3. **`/app/backend/telegram_tesoreria_handlers.py`**
   - Handler de notificaciones para Tesorería
   - Hooks para confirmación futura

4. **`/app/FLUJO_ANA_TESORERIA.md`**
   - Documentación completa del flujo

### Archivos Modificados:

1. **`/app/backend/netcash_service.py`**
   - `verificar_folio_mbco_existe()`
   - `asignar_folio_mbco_y_generar_orden_interna()`
   - `_generar_orden_interna_tesoreria()`
   - `_enviar_correo_tesoreria()` (mock)
   - `_notificar_tesoreria_telegram()`
   - `_notificar_ana_solicitud_lista()`
   - Modificado `procesar_solicitud_automaticamente()` para notificar a Ana

2. **`/app/backend/telegram_bot.py`**
   - Inicialización de handlers de Ana y Tesorería
   - Conversation handler para Ana
   - Callback handlers para Tesorería

---

## ✅ Resumen de Estados

### Estados de Solicitud:

```
borrador
   ↓
lista_para_mbc  ← Cliente confirma
   ↓
orden_interna_generada  ← Ana asigna folio MBco
   ↓
[futuro: ligas_enviadas]  ← Tesorería confirma
   ↓
[futuro: completada]  ← Proveedor confirma entrega
```

### Estados de Orden Interna:

```
pendiente_envio_ligas  ← Orden creada
   ↓
[futuro: ligas_enviadas]  ← Tesorería confirma
   ↓
[futuro: completada]  ← Todo el flujo terminado
```

---

## 🎯 Criterios de Aceptación

✅ **Completados:**
- [x] Ana recibe notificación cuando solicitud queda lista
- [x] Ana puede asignar folio MBco
- [x] Se valida que folio no esté duplicado
- [x] Se genera orden interna para Tesorería
- [x] Tesorería recibe notificación con detalles
- [x] Layout de correo preparado (mock)
- [x] Datos guardados correctamente en MongoDB
- [x] Hooks preparados para siguiente fase

⏳ **Para Siguiente Fase:**
- [ ] Implementar envío real de correo
- [ ] Confirmación de envío de ligas por Tesorería
- [ ] Vista completa de detalles de orden
- [ ] Integración con proveedor

---

**Status**: ✅ **COMPLETADO**  
**Listo para**: Testing con usuarios reales  
**Próximo paso**: Implementar confirmación de envío de ligas
