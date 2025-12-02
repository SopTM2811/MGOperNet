# Fix P1 - Flujo claro para asignar folio MBco

## 🟡 Problema Identificado

**Síntomas**:
1. Ana puede tener varias solicitudes pendientes al mismo tiempo
2. Cuando elige "Asignar folio MBco", solo ve un campo para teclear
3. No queda claro a qué solicitud se le asigna el folio
4. El formato correcto ahora es 5 dígitos iniciales, pero había folios históricos de 4 dígitos

## ✅ Solución Implementada

### 1. Confirmación antes de pedir el folio (líneas 159-200)

**Mejora**: Antes de pedir el folio, mostrar claramente a qué solicitud se le va a asignar.

**ANTES**:
```python
mensaje = "📝 **Asignación de folio MBco**\n\n"
mensaje += "Por favor, escribe el folio de operación MBco...\n"
mensaje += "**Formato:** 4 dígitos – 3 dígitos – 1 letra (D, S, R o M) – 2 dígitos\n"
```

**DESPUÉS**:
```python
# Obtener datos de la solicitud para mostrar confirmación
solicitud = await db.solicitudes_netcash.find_one({'id': solicitud_id}, {'_id': 0})

mensaje = "📝 **Asignación de folio MBco**\n\n"
mensaje += "🎯 **Vas a asignar folio a esta solicitud:**\n\n"
mensaje += f"📋 Folio NetCash: `{folio_nc}`\n"
mensaje += f"👤 Cliente: {cliente}\n"
mensaje += f"👥 Beneficiario: {beneficiario}\n"
mensaje += f"💰 Total depósitos: ${total_depositos:,.2f}\n\n"
mensaje += "───────────────────────\n\n"
mensaje += "📝 **Escribe el folio MBco:**\n\n"
mensaje += "**Formato:** #####-###-[D|S|R|M]-##\n"
mensaje += "**Ejemplo:** `23456-209-M-11`\n\n"
```

**Beneficio**: Ana ve claramente:
- A qué solicitud específica va el folio
- Folio NetCash
- Cliente y beneficiario
- Monto total

### 2. Validación de formato flexible (líneas 211-226)

**Mejora**: Aceptar tanto formato nuevo (5 dígitos) como histórico (4 dígitos).

**ANTES**:
```python
patron_folio = r'^\d{4}-\d{3}-[DSRM]-\d{2}$'  # Solo 4 dígitos

if not re.match(patron_folio, folio_mbco):
    # Rechaza folios de 5 dígitos
```

**DESPUÉS**:
```python
# Formato nuevo: 5 dígitos iniciales
patron_folio_nuevo = r'^\d{5}-\d{3}-[DSRM]-\d{2}$'
# Formato viejo: 4 dígitos iniciales (compatibilidad)
patron_folio_viejo = r'^\d{4}-\d{3}-[DSRM]-\d{2}$'

if not (re.match(patron_folio_nuevo, folio_mbco) or re.match(patron_folio_viejo, folio_mbco)):
    # Rechazar si no cumple ninguno de los dos formatos
```

**Formatos válidos**:
- ✅ `23456-209-M-11` (nuevo: 5 dígitos)
- ✅ `1234-209-M-11` (viejo: 4 dígitos - para históricos)
- ❌ `123-209-M-11` (solo 3 dígitos)
- ❌ `23456-20-M-11` (segunda parte incorrecta)

**Letras válidas**: D, S, R, M

### 3. Mensaje de éxito claro (línea 315)

**Ya implementado en P0**: El mensaje muestra claramente el folio asignado:

```python
await update.message.reply_text(
    "✅ **Orden procesada correctamente.**\n\n"
    f"Folio MBco: **{folio_mbco}**\n\n"
    "El layout fue generado y enviado a Tesorería."
)
```

## 📊 Flujo Completo Mejorado

### ANTES:
```
1. Ana recibe notificación con botón "Asignar folio"
2. Presiona botón
3. Ve: "Escribe el folio..." (sin contexto claro)
4. Escribe folio
5. Se asigna (no queda claro a qué solicitud)
```

### DESPUÉS:
```
1. Ana recibe notificación con botón "Asignar folio"
2. Presiona botón
3. Ve confirmación:
   🎯 Vas a asignar folio a esta solicitud:
   📋 Folio NetCash: nc-abc-123
   👤 Cliente: EMPRESA XYZ
   👥 Beneficiario: PROVEEDOR ABC
   💰 Total: $100,000.00
   
   📝 Escribe el folio MBco:
   Formato: #####-###-[D|S|R|M]-##
   
4. Escribe folio (ej: 23456-209-M-11)
5. Validación de formato (5 dígitos preferido, 4 dígitos aceptado)
6. Validación de unicidad
7. ✅ Orden procesada correctamente.
   Folio MBco: 23456-209-M-11
   El layout fue generado y enviado a Tesorería.
```

## 🧪 Validación

**Casos de prueba**:
1. ✅ Folio con 5 dígitos iniciales: `23456-209-M-11`
2. ✅ Folio con 4 dígitos iniciales: `1234-209-M-11`
3. ❌ Folio con formato incorrecto: `123-20-M-1`
4. ❌ Folio duplicado
5. ✅ Confirmación clara de qué solicitud se está procesando

## 📝 Archivos Modificados

**Archivo**: `/app/backend/telegram_ana_handlers.py`

**Cambios**:
- **Líneas 159-200**: Agregar confirmación mostrando detalles de la solicitud antes de pedir folio
- **Líneas 211-226**: Actualizar validación de formato para aceptar 4 o 5 dígitos iniciales
- **Línea 162, 220-221**: Actualizar mensajes de ayuda con formato nuevo (#####-###-[D|S|R|M]-##)

## ✅ Criterios de Aceptación P1

- [x] Ana ve claramente a qué solicitud asigna el folio (Folio NetCash, cliente, beneficiario, monto)
- [x] Formato de validación acepta 5 dígitos iniciales (nuevo)
- [x] Formato de validación acepta 4 dígitos iniciales (histórico/compatible)
- [x] Mensaje de ayuda muestra formato correcto con ejemplo
- [x] Mensaje de éxito muestra folio asignado claramente
- [x] No se rompen operaciones históricas con folios de 4 dígitos

## 📋 Formato Completo del Folio

**Estructura**: `#####-###-L-##`

**Partes**:
1. **5 dígitos** (iniciales): `23456`
2. **Guión**: `-`
3. **3 dígitos**: `209`
4. **Guión**: `-`
5. **1 letra** (D, S, R o M): `M`
6. **Guión**: `-`
7. **2 dígitos** (finales): `11`

**Ejemplo completo**: `23456-209-M-11`

**Compatibilidad histórica**: También acepta `1234-209-M-11` (4 dígitos iniciales)

---

**Fecha del fix**: 2024-12-02
**Status**: ✅ COMPLETADO Y LISTO PARA PRUEBAS
