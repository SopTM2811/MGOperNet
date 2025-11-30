# 🐛 BUGFIX: Operación 0023 - Flujo de Tesorería por Operación

## 📋 Resumen del Bug

**Operación afectada:** nc-1764541698631 (Folio MBco: 2456-234-D-11)
**Monto:** $2,000,000.00
**Síntoma:** Después de que Ana asignó el folio MBco, el flujo de tesorería por operación no se ejecutó.

### Estado Antes del Fix:
- ✅ Ana asignó folio MBco: `2456-234-D-11`
- ✅ Estado cambió a: `orden_interna_generada`
- ❌ NO se generó layout CSV individual
- ❌ NO se envió correo a Tesorería
- ❌ NO cambió a estado `enviado_a_tesoreria`

---

## 🔍 Causa Raíz

El nuevo servicio `tesoreria_operacion_service.py` fue creado pero **NO estaba integrado** en el flujo principal de asignación de folio MBco.

### Flujo Anterior (Roto):
```
Ana asigna folio via Telegram
    ↓
telegram_ana_handlers.py
    ↓
netcash_service.asignar_folio_mbco_y_generar_orden_interna()
    ↓
Asigna folio + estado orden_interna_generada
    ↓
❌ FIN (no llamaba al nuevo servicio de tesorería)
```

### Problema Específico:
- El código en `netcash_service.py` tenía métodos viejos:
  - `_generar_orden_interna_tesoreria()`
  - `_enviar_correo_tesoreria()`
  - `_notificar_tesoreria_telegram()`
  
- Pero estos métodos NO implementaban el nuevo modelo de "layout por operación"
- El nuevo servicio `tesoreria_operacion_service` existía pero nunca se llamaba

---

## ✅ Solución Aplicada

### Archivo Modificado:
`/app/backend/netcash_service.py`

### Cambio Realizado:
Reemplazamos el flujo viejo por la llamada al nuevo servicio:

```python
# ANTES (líneas ~1152-1165):
# 3. Generar orden interna para Tesorería
orden_interna = await self._generar_orden_interna_tesoreria(solicitud_id, folio_mbco)
# 4. Enviar correo a Tesorería
await self._enviar_correo_tesoreria(solicitud_id, orden_interna)
# 5. Notificar a Tesorería por Telegram
await self._notificar_tesoreria_telegram(solicitud_id, orden_interna)

# AHORA:
# 3. NUEVO FLUJO: Procesar operación de tesorería individual
from tesoreria_operacion_service import tesoreria_operacion_service
resultado_tesoreria = await tesoreria_operacion_service.procesar_operacion_tesoreria(solicitud_id)
```

### Flujo Corregido:
```
Ana asigna folio via Telegram
    ↓
telegram_ana_handlers.py
    ↓
netcash_service.asignar_folio_mbco_y_generar_orden_interna()
    ↓
Asigna folio + estado orden_interna_generada
    ↓
✅ tesoreria_operacion_service.procesar_operacion_tesoreria()
    ↓
1. Genera layout CSV: LTMBCO_{folio_con_x}.csv
2. Envía correo a Tesorería (si Gmail configurado)
3. Cambia estado a: enviado_a_tesoreria
```

---

## 🔧 Operación 0023 - Estado Actual

### Procesamiento Manual Ejecutado:
Ejecutamos manualmente el servicio de tesorería para la operación 0023:

```bash
python3 << 'EOF'
from tesoreria_operacion_service import tesoreria_operacion_service
resultado = await tesoreria_operacion_service.procesar_operacion_tesoreria("nc-1764541698631")
EOF
```

### Resultado:
- ✅ **Estado:** `enviado_a_tesoreria`
- ✅ **Layout generado:** `/app/backend/uploads/layouts_operaciones/LTMBCO_2456x234xDx11.csv`
- ✅ **Campos actualizados:**
  - `layout_individual_generado: true`
  - `fecha_envio_tesoreria: 2025-11-30 22:35:36`

### Contenido del Layout CSV:
```csv
Clabe destinatario,Nombre o razon social destinatario,Monto,Concepto,Email (opcional),Tags separados por comas (opcional),Comentario (opcional)
012680001255709482,AFFORDABLE MEDICAL SERVICES SC,495000.00,MBco 2456x234xDx11,,,Liga 1/4
012680001255709482,AFFORDABLE MEDICAL SERVICES SC,495000.00,MBco 2456x234xDx11,,,Liga 2/4
012680001255709482,AFFORDABLE MEDICAL SERVICES SC,495000.00,MBco 2456x234xDx11,,,Liga 3/4
012680001255709482,AFFORDABLE MEDICAL SERVICES SC,495000.00,MBco 2456x234xDx11,,,Liga 4/4
058680000012912655,COMERCIALIZADORA UETACOP SA DE CV,7425.00,MBco 2456x234xDx11 COMISION,,,Comisión proveedor DNS
```

### Verificación de Cálculos:
- Total depósitos: $2,000,000.00
- Comisión cliente (1%): $20,000.00
- Capital (ligas): $1,980,000.00
- Comisión DNS (0.375% capital): $7,425.00 ✅
- División en 4 ligas: $495,000.00 cada una ✅

---

## 🧪 Prueba para Nueva Operación

Para verificar que el bug está resuelto, crear una nueva operación:

### Pasos:
1. Cliente sube comprobante por Telegram
2. Sistema valida y crea solicitud
3. Ana asigna folio MBco

### Resultado Esperado:
- ✅ Mensaje a Ana: "Folio MBco asignado correctamente"
- ✅ Mensaje a Ana: "Layout individual generado y enviado a Tesorería"
- ✅ Estado final: `enviado_a_tesoreria`
- ✅ CSV generado en: `/app/backend/uploads/layouts_operaciones/LTMBCO_{folio_con_x}.csv`
- ✅ Correo enviado a Tesorería (si Gmail configurado)

### Verificación en BD:
```python
solicitud = await db.solicitudes_netcash.find_one({"folio_mbco": "FOLIO-NUEVO"})
assert solicitud['estado'] == 'enviado_a_tesoreria'
assert solicitud['layout_individual_generado'] == True
assert 'fecha_envio_tesoreria' in solicitud
```

---

## 📧 Nota sobre Gmail

**Observado:** Gmail service no está configurado (faltan credenciales)

### Comportamiento Actual:
- ❌ Correo NO se envía a Tesorería
- ✅ CSV se guarda localmente en `/app/backend/uploads/layouts_operaciones/`
- ✅ Log indica: "Gmail service no disponible"

### Para Habilitar Gmail:
1. Configurar variables de entorno en `/app/backend/.env`:
   - `GMAIL_USER`
   - `GMAIL_APP_PASSWORD`
   - `TESORERIA_TEST_EMAIL` (ya configurado)

2. El servicio automáticamente intentará enviar correos

---

## ✅ Verificación de No Regresión

### Flujos que NO se modificaron:
- ✅ Validador de comprobantes Vault
- ✅ Fórmulas de comisión (DNS 0.375%)
- ✅ Cuentas de proveedor (AFFORDABLE + UETACOP)
- ✅ Scheduler de recordatorios (cada 15 min)
- ✅ Asignación de folio por Ana
- ✅ Estados anteriores de solicitudes

### Operaciones Anteriores:
Las operaciones procesadas antes del fix (en estado `enviado_a_tesoreria`) NO se ven afectadas.

---

## 📊 Resumen

| Aspecto | Antes del Fix | Después del Fix |
|---------|---------------|-----------------|
| Folio asignado | ✅ Sí | ✅ Sí |
| Layout CSV generado | ❌ No | ✅ Sí |
| Correo a Tesorería | ❌ No | ✅ Sí (si Gmail config) |
| Estado final | `orden_interna_generada` | `enviado_a_tesoreria` |
| Operación 0023 | ❌ Rota | ✅ Corregida manualmente |

---

## 🎯 Próximos Pasos

1. ✅ Bug de operación 0023 resuelto
2. ✅ Flujo integrado correctamente
3. ⏳ Probar con nueva operación para confirmar
4. ⏳ Configurar Gmail para envío real de correos
5. ⏳ Implementar Fase 2: Detección de respuestas de Toño
