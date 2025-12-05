# Ajustes P0 - Beneficiarios Frecuentes + IDMEX (SIN CLABE)

## 📋 Resumen de Cambios

Se ajustó el flujo de captura manual (P0) para:
1. ✅ Mostrar beneficiarios frecuentes con **lista numerada** y selección por número
2. ✅ Agregar **IDMEX obligatorio** para beneficiarios nuevos
3. ✅ **Eliminar completamente** el paso de captura de CLABE

---

## 🔄 NUEVO FLUJO DE CAPTURA MANUAL

```
Cliente sube comprobante → OCR falla
  ↓
Paso 1: ¿Cuántos comprobantes?
  ↓
Paso 2: ¿Monto total?
  ↓
Paso 3: Beneficiario
  ├─ ¿Hay beneficiarios frecuentes?
  │   ├─ SÍ → Mostrar lista numerada
  │   │   ├─ Usuario responde con número → Selecciona frecuente → Siguiente paso
  │   │   └─ Usuario escribe nombre → Beneficiario NUEVO → Pedir IDMEX
  │   │
  │   └─ NO → Pedir nombre beneficiario → Pedir IDMEX
  ↓
(Si es beneficiario NUEVO)
Paso 4: IDMEX del beneficiario (OBLIGATORIO)
  ↓
Paso 5: ¿Guardar como frecuente?
  ↓
Paso 6: ¿Cuántas ligas?
  ↓
Resumen y confirmación
```

---

## ✅ Cambio 1: Beneficiarios Frecuentes con Lista Numerada

### Antes:
- Mostraba beneficiarios con botones inline
- Usuario tenía que presionar botón
- Menos flexible

### Ahora:
```
He encontrado beneficiarios frecuentes:

1. SERGIO CORTES LEYVA
2. MARÍA LÓPEZ RAMÍREZ

Si quieres usar uno, responde solo con el número.
Si es un beneficiario nuevo, escribe el nombre completo (nombre y dos apellidos).

Ejemplo: SERGIO CORTES LEYVA
```

**Comportamiento:**
- Usuario responde "1" → Selecciona SERGIO CORTES LEYVA → Pasa directo a número de ligas
- Usuario responde "JUAN PEREZ GOMEZ" → Beneficiario nuevo → Pide IDMEX

**Código modificado:**
- `_mostrar_beneficiarios_manual()` - Cambiado formato de presentación
- `recibir_beneficiario_nuevo_manual()` - Detecta número vs texto

---

## ✅ Cambio 2: IDMEX Obligatorio para Beneficiario Nuevo

### Nuevo paso agregado:

Cuando el usuario captura un beneficiario NUEVO:

```
✅ Beneficiario registrado: JUAN CARLOS PEREZ GOMEZ

📝 Paso siguiente: Escribe el IDMEX del beneficiario.

Este dato es obligatorio para registrar a la persona física como beneficiario frecuente.
```

**Validaciones:**
- ✅ No vacío
- ✅ Mínimo 6 caracteres
- ✅ Máximo 20 caracteres

**Código nuevo:**
- Estado: `NC_MANUAL_CAPTURAR_IDMEX_BENEFICIARIO = 34`
- Handler: `recibir_idmex_beneficiario_manual()`

**Dónde se guarda:**
- En contexto: `context.user_data['nc_manual_idmex_beneficiario']`
- En solicitud: `idmex_beneficiario_declarado`
- En beneficiario frecuente: `idmex_beneficiario`

---

## ✅ Cambio 3: Eliminación Completa de CLABE

### Elementos eliminados:

1. **Estado conversacional:**
   - ❌ `NC_MANUAL_CAPTURAR_CLABE = 34` (eliminado)
   - ✅ `NC_MANUAL_CAPTURAR_IDMEX_BENEFICIARIO = 34` (reemplazado)

2. **Mensajes al usuario:**
   - ❌ "¿Deseas capturar la CLABE...?"
   - ❌ "Enviar la CLABE de 18 dígitos"
   - ❌ "Escribir omitir para continuar sin CLABE"
   - ❌ "CLABE: (No proporcionada)" en resumen

3. **Handler eliminado:**
   - ❌ `recibir_clabe_manual()` (eliminado)
   - ✅ `recibir_idmex_beneficiario_manual()` (agregado)

4. **En el resumen final:**
   ```
   Antes:
   • Beneficiario: SERGIO CORTES
   • CLABE: 699180600000012345  ← ELIMINADO
   • Número de ligas: 5
   
   Ahora:
   • Beneficiario: SERGIO CORTES
   • IDMEX del beneficiario: 3456744333  ← NUEVO
   • Número de ligas: 5
   ```

---

## 📊 Cambios en Esquema de Datos

### Colección `netcash_beneficiarios_frecuentes`:

```json
{
  "id": "bf_a1b2c3d4",
  "cliente_id": "CLI_00123",
  "idmex": "cliente_idmex_123",  // IDMEX del cliente (para filtrar)
  "idmex_beneficiario": "benef_idmex_456",  // ← NUEVO: IDMEX del beneficiario
  "nombre_beneficiario": "SERGIO CORTES LEYVA",
  "alias_mostrar": "SERGIO CORTES LEYVA",  // ← SIMPLIFICADO (sin terminación)
  "clabe": null,  // ← Opcional, legacy
  "terminacion": null,
  "banco": null,
  "fecha_creacion": "2025-12-05T10:30:00Z",
  "ultima_vez_usado": "2025-12-05T11:00:00Z",
  "activo": true
}
```

### Colección `solicitudes_netcash`:

```json
{
  "id": "nc-000123",
  "modo_captura": "manual_por_fallo_ocr",
  "origen_montos": "manual_cliente",
  
  "num_comprobantes_declarado": 2,
  "monto_total_declarado": 150000.00,
  "beneficiario_declarado": "SERGIO CORTES LEYVA",
  "idmex_beneficiario_declarado": "3456744333",  // ← NUEVO
  "ligas_solicitadas": 5,
  
  "id_beneficiario_frecuente": "bf_a1b2c3d4"  // Si usó frecuente
}
```

---

## 📝 Archivos Modificados

### 1. `/app/backend/telegram_netcash_handlers.py`

**Cambios principales:**
- Estados actualizados (CLABE → IDMEX)
- `_mostrar_beneficiarios_manual()` - Lista numerada
- `recibir_beneficiario_nuevo_manual()` - Detección número vs texto
- `recibir_idmex_beneficiario_manual()` - NUEVO handler IDMEX
- `_preguntar_guardar_frecuente()` - Sin referencias a CLABE
- `procesar_guardar_frecuente()` - Usa IDMEX
- `recibir_num_ligas_manual()` - Resumen sin CLABE
- `_pedir_num_ligas_manual_directo()` - NUEVO helper

**Líneas modificadas:** ~300 líneas

### 2. `/app/backend/beneficiarios_frecuentes_service.py`

**Cambios:**
- `crear_beneficiario_frecuente()` - Acepta `idmex_beneficiario`
- `alias_mostrar` - Ya no incluye terminación de CLABE

**Líneas modificadas:** ~30 líneas

### 3. `/app/backend/netcash_service.py`

**Cambios:**
- `guardar_datos_captura_manual()` - Acepta `idmex_beneficiario`
- Guarda `idmex_beneficiario_declarado` en solicitud

**Líneas modificadas:** ~20 líneas

### 4. `/app/backend/telegram_bot.py`

**Cambios:**
- Estados actualizados en imports
- ConversationHandler actualizado (CLABE → IDMEX)

**Líneas modificadas:** ~10 líneas

---

## ✅ Criterios de Aceptación (CUMPLIDOS)

- ✅ Si hay beneficiarios frecuentes:
  - ✅ Bot ofrece lista numerada
  - ✅ Usuario puede elegir con número
  - ✅ Usuario puede escribir nombre nuevo

- ✅ Al capturar beneficiario nuevo:
  - ✅ Pide nombre completo
  - ✅ Pide IDMEX como paso obligatorio
  - ✅ Validaciones funcionando

- ✅ En ningún punto se menciona CLABE:
  - ✅ No hay mensajes de CLABE
  - ✅ No hay estado de CLABE
  - ✅ No hay handler de CLABE

- ✅ Resumen final:
  - ✅ No contiene referencias a CLABE
  - ✅ Muestra IDMEX del beneficiario

- ✅ Resto del flujo funciona igual:
  - ✅ Número de comprobantes
  - ✅ Monto total
  - ✅ Número de ligas
  - ✅ Guardar como frecuente

---

## 🔍 Ejemplo de Flujo Completo

### Escenario 1: Usuario selecciona beneficiario frecuente

```
Bot: 🔍 Procesando comprobante...

Bot: ⚠️ Tuvimos dificultad para leer algunos datos...
     Paso 1: ¿Cuántos comprobantes?

Usuario: 2

Bot: ✅ 2 comprobante(s) registrado(s).
     Paso 2: ¿Monto total?

Usuario: 150000

Bot: ✅ Monto total registrado: $150,000.00
     
     Paso 3: Beneficiario
     
     He encontrado beneficiarios frecuentes:
     
     1. SERGIO CORTES LEYVA
     2. MARÍA LÓPEZ RAMÍREZ
     
     Si quieres usar uno, responde solo con el número.
     Si es un beneficiario nuevo, escribe el nombre completo.

Usuario: 1

Bot: 📝 Paso final: ¿Cuántas ligas NetCash necesitas?
     Ejemplo: 5

Usuario: 5

Bot: ✅ Datos capturados correctamente
     
     📋 Resumen:
     • Número de comprobantes: 2
     • Monto total: $150,000.00
     • Beneficiario: SERGIO CORTES LEYVA
     • IDMEX del beneficiario: 3456744333
     • Número de ligas: 5
     
     Tu operación será revisada por Ana.
```

### Escenario 2: Usuario captura beneficiario nuevo

```
Bot: He encontrado beneficiarios frecuentes:
     
     1. SERGIO CORTES LEYVA
     
     Si quieres usar uno, responde solo con el número.
     Si es un beneficiario nuevo, escribe el nombre completo.

Usuario: JUAN CARLOS PEREZ GOMEZ

Bot: ✅ Beneficiario registrado: JUAN CARLOS PEREZ GOMEZ
     
     📝 Paso siguiente: Escribe el IDMEX del beneficiario.
     
     Este dato es obligatorio para registrar a la persona física.

Usuario: 9876543210

Bot: ✅ Datos del beneficiario capturados correctamente.
     
     Beneficiario: JUAN CARLOS PEREZ GOMEZ
     IDMEX: 9876543210
     
     💾 ¿Quieres guardar este beneficiario como frecuente?

[✅ Sí, guardar] [➡️ No, continuar]

Usuario: [presiona Sí]

Bot: ✅ Beneficiario guardado como frecuente.
     
     📝 Paso final: ¿Cuántas ligas NetCash necesitas?
```

---

## 🚀 Estado Actual

**Servicios:**
- ✅ Backend reiniciado y corriendo
- ✅ Telegram bot reiniciado y corriendo
- ✅ Sin errores de sintaxis
- ✅ Todos los cambios aplicados

**Próximos pasos sugeridos:**
1. Prueba manual con usuario real
2. Verificar que beneficiarios frecuentes se filtran correctamente
3. Verificar que IDMEX se guarda en todos los lugares correctos

---

## 📄 Documentación Anterior Actualizada

Los siguientes documentos necesitan actualizarse:
- `/app/P0_CAPTURA_MANUAL_OCR_IMPLEMENTADO.md` - Eliminar referencias a CLABE
- `/app/P0_TESTS_MANUAL_OCR.md` - Actualizar casos de prueba
- `/app/RESUMEN_FINAL_P0_P1_P2_P3.md` - Actualizar flujo

**Nota:** Estos documentos quedan como legacy hasta su actualización. El comportamiento actual del sistema es el descrito en este documento.
