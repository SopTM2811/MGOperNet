# Refactorización Completa: Flujo NetCash V1 en Telegram

## 📅 Fecha: Noviembre 2025

## 🎯 Objetivo Principal
Reordenar el flujo de creación de operaciones NetCash en Telegram para **fallar rápido** si los comprobantes no son válidos, evitando que el cliente pierda tiempo capturando datos innecesarios.

---

## 🔄 Cambio de Diseño: Nuevo Orden del Flujo

### ❌ Orden ANTERIOR (V1 original)
1. Beneficiario
2. IDMEX
3. Ligas
4. Comprobantes ← **Validación al final**

### ✅ Orden NUEVO (V1 refactorizado)
1. **Comprobantes** ← **Validación primero (Fallar rápido)**
2. Beneficiario + IDMEX (con sugerencias frecuentes)
3. Ligas NetCash
4. Resumen y Confirmación

**Filosofía:** Si los comprobantes no sirven, el usuario lo sabe **inmediatamente** sin haber perdido tiempo en capturar beneficiario, IDMEX y ligas.

---

## 🐛 Bug P0 Corregido

### Problema
En el resumen final, el bot mostraba:
```
• Comprobante: 1 archivo(s) ✅
```
Pero en "Problemas detectados":
```
• Comprobante: No hay comprobantes adjuntos ❌
```

**Causa raíz:** El resumen mostraba el **número** de archivos recibidos (línea 578 del código anterior), pero la validación del motor consideraba si los comprobantes eran **válidos** (matching con la cuenta NetCash autorizada).

### Solución Implementada
Se refactorizó el método `_mostrar_resumen_y_confirmar()` para **diferenciar 3 casos**:

#### **Caso A: Sin archivos**
```
• Comprobantes: 0 archivo(s) ❌
Problema: No se recibió ningún comprobante.
```

#### **Caso B: Archivos recibidos pero ninguno válido**
```
• Comprobantes: 2 archivo(s) ❌
Problema: Se recibieron comprobantes, pero ninguno coincide con la cuenta NetCash autorizada.
```

#### **Caso C: Al menos un comprobante válido**
```
• Comprobantes: 2 archivo(s) (1 válido(s)) ✅
```

**Código actualizado (líneas 1104-1130 en `telegram_netcash_handlers.py`):**
```python
# Comprobante - MEJORADO para diferenciar casos
num_comprobantes = campos.get("comprobantes", 0)
comprobante_valido = "comprobante" in campos_validos

# Obtener solicitud para analizar comprobantes
solicitud = await netcash_service.obtener_solicitud(solicitud_id)
comprobantes = solicitud.get("comprobantes", [])
comprobantes_validos_list = [c for c in comprobantes if c.get("es_valido", False)]

if num_comprobantes == 0:
    # Caso A: Sin archivos
    icono_comp = "❌"
    mensaje += f"• Comprobantes: 0 archivo(s) {icono_comp}\n"
elif len(comprobantes_validos_list) == 0:
    # Caso B: Archivos recibidos pero ninguno válido
    icono_comp = "❌"
    mensaje += f"• Comprobantes: {num_comprobantes} archivo(s) {icono_comp}\n"
else:
    # Caso C: Al menos uno válido
    icono_comp = "✅"
    mensaje += f"• Comprobantes: {num_comprobantes} archivo(s) ({len(comprobantes_validos_list)} válido(s)) {icono_comp}\n"

# Mejorar mensajes de error
if campo == "comprobante":
    if num_comprobantes == 0:
        razon = "No se recibió ningún comprobante."
    elif len(comprobantes_validos_list) == 0:
        razon = "Se recibieron comprobantes, pero ninguno coincide con la cuenta NetCash autorizada."
```

---

## 🧾 Paso 1: Comprobantes (Multi-archivo + Disparo Múltiple)

### Mensaje de Entrada
```
✅ Iniciemos tu operación NetCash

🏦 Cuenta para tu depósito:
• Banco: STP
• CLABE: 646180139409481462
• Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV

🧾 Paso 1 de 3: Comprobantes de depósito

Envíame uno o varios comprobantes de tus depósitos NetCash.
Puedes adjuntar:
• Varios archivos en un solo envío (álbum/selección múltiple)
• O enviarlos en mensajes separados, uno tras otro

Formatos aceptados:
• Archivo PDF
• Imagen (JPG, PNG)

⚠️ Importante: Los comprobantes deben corresponder a la cuenta NetCash autorizada mostrada arriba.

Cuando termines de subir todos tus comprobantes, pulsa "➡️ Continuar".
```

### Flujo de Recepción
1. Usuario envía 1 o más comprobantes (PDF/imagen)
2. Bot procesa cada archivo con `netcash_service.agregar_comprobante()`
3. Bot muestra:
   ```
   ✅ Comprobante recibido.
   Llevamos 1 comprobante(s) adjunto(s) a esta operación.
   
   ¿Quieres subir otro comprobante o continuar al siguiente paso?
   
   [➕ Agregar otro comprobante] [➡️ Continuar]
   ```

### Validación al Presionar "Continuar"
Cuando el usuario presiona "➡️ Continuar":
1. **Si no hay comprobantes (num_comprobantes == 0):**
   ```
   ⚠️ Para continuar, debes adjuntar por lo menos un comprobante de depósito.
   Por favor sube al menos uno.
   ```
   → Mantiene en `NC_ESPERANDO_COMPROBANTE`

2. **Si hay comprobantes pero ninguno válido:**
   ```
   ❌ Se recibieron 2 comprobante(s), pero ninguno coincide con la cuenta NetCash autorizada.
   
   Detalle: Ningún comprobante es válido. Razones: ...
   
   La cuenta NetCash autorizada es:
   • Banco: STP
   • CLABE: 646180139409481462
   • Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV
   
   Por favor envía comprobantes que correspondan a esta cuenta.
   ```
   → Mantiene en `NC_ESPERANDO_COMPROBANTE` (FALLAR RÁPIDO)

3. **Si hay al menos 1 comprobante válido:**
   ```
   ✅ Comprobantes validados. Pasando al siguiente paso...
   ```
   → Avanza al Paso 2 (`NC_ESPERANDO_BENEFICIARIO`)

**Código clave (método `continuar_desde_paso1`):**
```python
# Validar comprobantes antes de avanzar
todas_validas, validaciones = await netcash_service.validar_solicitud_completa(solicitud_id)
validacion_comprobante = validaciones.get("comprobante", {})

# Contar comprobantes válidos
comprobantes_validos = [c for c in comprobantes if c.get("es_valido", False)]

if len(comprobantes_validos) == 0:
    # NO hay comprobantes válidos - FALLAR RÁPIDO
    mensaje = f"❌ Se recibieron {num_comprobantes} comprobante(s), pero ninguno coincide..."
    return NC_ESPERANDO_COMPROBANTE

# Hay al menos 1 válido - continuar al Paso 2
await self._mostrar_paso2_beneficiarios(query, context, solicitud_id)
return NC_ESPERANDO_BENEFICIARIO
```

---

## 👤 Paso 2: Beneficiario + IDMEX (Con Frecuentes)

### Lógica de Beneficiarios Frecuentes

**Consulta a la BD:**
```python
# Consultar últimas 5 solicitudes exitosas del cliente
solicitudes_exitosas = await db.solicitudes_netcash.find(
    {
        "cliente_id": cliente_id,
        "estado": "lista_para_mbc",
        "beneficiario_reportado": {"$exists": True, "$ne": None},
        "idmex_reportado": {"$exists": True, "$ne": None}
    },
    {"_id": 0, "beneficiario_reportado": 1, "idmex_reportado": 1}
).sort("created_at", -1).limit(5).to_list(5)

# Deduplicar (mismo beneficiario + idmex)
beneficiarios_frecuentes = {}
for sol in solicitudes_exitosas:
    benef = sol.get("beneficiario_reportado")
    idmex = sol.get("idmex_reportado")
    key = f"{benef}_{idmex}"
    if key not in beneficiarios_frecuentes:
        beneficiarios_frecuentes[key] = {"beneficiario": benef, "idmex": idmex}

# Tomar los 3 más frecuentes
frecuentes = list(beneficiarios_frecuentes.values())[:3]
```

### Caso A: Hay Beneficiarios Frecuentes
```
👤 Paso 2 de 3: Beneficiario + IDMEX

🔁 Beneficiarios frecuentes:

1. ANDRÉS MANUEL LÓPEZ OBRADOR – IDMEX: 1234567890
2. CLAUDIA SHEINBAUM PARDO – IDMEX: 0987654321
3. MARÍA ELENA ÁLVAREZ BRITO – IDMEX: 5555555555

Puedes elegir uno de la lista o escribir un beneficiario nuevo.
Si prefieres escribir uno nuevo, simplemente envía el nombre completo del beneficiario.

[ANDRÉS MANUEL LÓPEZ OBRADOR (IDMEX 1234567890)]
[CLAUDIA SHEINBAUM PARDO (IDMEX 0987654321)]
[MARÍA ELENA ÁLVAREZ BRITO (IDMEX 5555555555)]
```

**Si el usuario selecciona un frecuente:**
- Auto-rellena `beneficiario_reportado` y `idmex_reportado`
- Muestra confirmación:
  ```
  ✅ Usaremos:
  
  • Beneficiario: ANDRÉS MANUEL LÓPEZ OBRADOR
  • IDMEX: 1234567890
  
  Pasando al siguiente paso...
  ```
- **Avanza directamente al Paso 3 (Ligas)** sin pedir IDMEX manualmente

**Si el usuario escribe un nombre nuevo:**
- Flujo clásico:
  1. Valida beneficiario (min 3 palabras, sin números)
  2. Si válido, pide IDMEX (10 dígitos)

### Caso B: NO Hay Beneficiarios Frecuentes
```
👤 Paso 2 de 3: Beneficiario + IDMEX

Por favor envíame el nombre completo del beneficiario.

El nombre debe tener:
• Mínimo 3 palabras (nombre + dos apellidos)
• Sin números

Ejemplo: ANDRÉS MANUEL LÓPEZ OBRADOR
```

**Código clave (método `seleccionar_beneficiario_frecuente`):**
```python
async def seleccionar_beneficiario_frecuente(self, update, context):
    # Extraer IDMEX del callback_data
    idmex = query.data.replace("nc_benef_freq_", "")
    
    # Recuperar datos del contexto
    benef_data = context.user_data.get(f"benef_freq_{idmex}")
    
    # Actualizar solicitud con beneficiario + IDMEX
    await netcash_service.actualizar_solicitud(
        solicitud_id,
        SolicitudUpdate(
            beneficiario_reportado=benef_data['beneficiario'],
            idmex_reportado=benef_data['idmex']
        )
    )
    
    # Pasar directamente al Paso 3 (Ligas)
    await self._mostrar_paso3_ligas(query, context, solicitud_id)
    return NC_ESPERANDO_LIGAS
```

---

## 🎫 Paso 3: Ligas NetCash

Muy similar al flujo anterior, pero ahora es el **Paso 3** en lugar del paso 2.

```
🎫 Paso 3 de 3: Cantidad de ligas NetCash

¿Cuántas ligas NetCash necesitas?

Envíame solo el número (debe ser mayor a 0).

Ejemplo: 3
```

Validación:
- Debe ser entero > 0
- Si válido, pasa automáticamente al Paso 4 (Resumen)

---

## 📋 Paso 4: Resumen y Confirmación

El resumen ahora muestra información más clara sobre los comprobantes:

```
📋 Esto es lo que entendí de tu operación NetCash:

• Beneficiario: ANDRÉS MANUEL LÓPEZ OBRADOR ✅
• IDMEX: 1234567890 ✅
• Ligas NetCash: 3 ✅
• Comprobantes: 2 archivo(s) (2 válido(s)) ✅

✅ ¡Todo en orden!

Si los datos son correctos, confirma para enviar a proceso MBco.

[✅ Confirmar y enviar a MBco]
[✏️ Corregir datos]
[❌ Cancelar]
```

O si hay problemas:

```
📋 Esto es lo que entendí de tu operación NetCash:

• Beneficiario: ANDRÉS MANUEL LÓPEZ OBRADOR ✅
• IDMEX: 1234567890 ✅
• Ligas NetCash: 3 ✅
• Comprobantes: 2 archivo(s) ❌

⚠️ Problemas detectados:
• Comprobante: Se recibieron comprobantes, pero ninguno coincide con la cuenta NetCash autorizada.

❌ Hay errores que debes corregir.

Por favor corrige los datos marcados con ❌ y vuelve a intentar.

[✏️ Corregir datos]
[❌ Cancelar]
```

---

## 📁 Archivos Modificados

### 1. `/app/backend/telegram_netcash_handlers.py` (COMPLETAMENTE REFACTORIZADO)
**Cambios principales:**
- **Reordenado todo el flujo:** Comprobantes → Beneficiario+IDMEX → Ligas → Confirmación
- **Paso 1:** Implementado soporte de múltiples comprobantes con validación temprana
- **Paso 2:** Implementado beneficiarios frecuentes con botones inline
- **Resumen:** Mejorado para diferenciar los 3 casos de comprobantes
- **Estados actualizados:** Los números de estados siguen igual pero se usan en distinto orden

**Métodos nuevos:**
- `continuar_desde_paso1()`: Valida comprobantes antes de avanzar al Paso 2
- `_mostrar_paso2_beneficiarios()`: Muestra beneficiarios frecuentes o captura manual
- `seleccionar_beneficiario_frecuente()`: Auto-rellena beneficiario + IDMEX
- `_mostrar_paso3_ligas()`: Helper para mostrar el Paso 3

**Métodos refactorizados:**
- `iniciar_crear_operacion()`: Ahora comienza con Paso 1 (Comprobantes)
- `recibir_comprobante()`: Mantiene lógica de múltiples archivos
- `recibir_beneficiario()`: Ahora es Paso 2a
- `recibir_idmex()`: Ahora es Paso 2b
- `recibir_ligas()`: Ahora es Paso 3
- `_mostrar_resumen_y_confirmar()`: Mejorado para diferenciar casos de comprobantes

### 2. `/app/backend/telegram_bot.py`
**Cambios:**
- **Línea 32-33:** Actualización de orden de constantes de estados
- **Líneas 1186-1208:** ConversationHandler completamente actualizado con nuevo orden

**Actualización del ConversationHandler:**
```python
conv_handler_netcash = ConversationHandler(
    entry_points=[CallbackQueryHandler(self.nc_handlers.iniciar_crear_operacion, pattern="^nc_crear_operacion$")],
    states={
        NC_ESPERANDO_COMPROBANTE: [
            MessageHandler(filters.Document.ALL, self.nc_handlers.recibir_comprobante),
            MessageHandler(filters.PHOTO, self.nc_handlers.recibir_comprobante),
            CallbackQueryHandler(self.nc_handlers.agregar_otro_comprobante, pattern="^nc_mas_comprobantes_"),
            CallbackQueryHandler(self.nc_handlers.continuar_desde_paso1, pattern="^nc_continuar_paso1_")
        ],
        NC_ESPERANDO_BENEFICIARIO: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.nc_handlers.recibir_beneficiario),
            CallbackQueryHandler(self.nc_handlers.seleccionar_beneficiario_frecuente, pattern="^nc_benef_freq_")
        ],
        NC_ESPERANDO_IDMEX: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.nc_handlers.recibir_idmex)],
        NC_ESPERANDO_LIGAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.nc_handlers.recibir_ligas)],
        NC_ESPERANDO_CONFIRMACION: [
            CallbackQueryHandler(self.nc_handlers.confirmar_operacion, pattern="^nc_confirmar_"),
            CallbackQueryHandler(self.nc_handlers.corregir_datos, pattern="^nc_corregir_")
        ]
    },
    fallbacks=[...]
)
```

---

## 🔐 Archivos NO Modificados

✅ **Respetando el alcance:**
- ✅ `netcash_service.py` - NO modificado (solo se usa)
- ✅ `email_monitor.py` - NO modificado
- ✅ Frontend React - NO modificado
- ✅ Otros flujos de Telegram - NO modificados

---

## 🧪 Casos de Prueba Propuestos

### **Caso 1: Flujo Completo con 1 Comprobante Válido + Beneficiario Frecuente**
**Objetivo:** Probar el camino feliz con beneficiario frecuente.

**Pasos:**
1. Inicia con `/start` → "🧾 Crear nueva operación NetCash"
2. **Paso 1:** Envía 1 comprobante PDF válido (THABYETHA STP, CLABE 646180139409481462)
3. Presiona "➡️ Continuar"
4. **Paso 2:** Selecciona un beneficiario frecuente de la lista (si tienes)
5. **Paso 3:** Envía cantidad de ligas (ej. `3`)
6. **Paso 4:** Verifica el resumen:
   - Comprobantes: 1 archivo(s) (1 válido(s)) ✅
   - Beneficiario ✅
   - IDMEX ✅
   - Ligas ✅
7. Presiona "✅ Confirmar y enviar a MBco"
8. Verifica folio generado NC-XXXXX

**Resultado esperado:** Operación creada exitosamente en estado `lista_para_mbc`.

---

### **Caso 2: Fallar Rápido - Comprobante Inválido**
**Objetivo:** Verificar que el sistema falla rápido si el comprobante no coincide con la cuenta autorizada.

**Pasos:**
1. Inicia con `/start` → "🧾 Crear nueva operación NetCash"
2. **Paso 1:** Envía 1 comprobante que NO sea de la cuenta THABYETHA (ej. comprobante de otra cuenta)
3. Presiona "➡️ Continuar"
4. **Resultado:** El bot debe mostrar:
   ```
   ❌ Se recibieron 1 comprobante(s), pero ninguno coincide con la cuenta NetCash autorizada.
   
   Detalle: ...
   
   La cuenta NetCash autorizada es:
   • Banco: STP
   • CLABE: 646180139409481462
   • Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV
   
   Por favor envía comprobantes que correspondan a esta cuenta.
   ```
5. El bot debe **mantenerse en el Paso 1** sin avanzar

**Resultado esperado:** El usuario NO pierde tiempo capturando beneficiario/IDMEX/ligas si el comprobante no sirve.

---

### **Caso 3: Múltiples Comprobantes (2 válidos, 1 inválido)**
**Objetivo:** Verificar que el sistema maneja correctamente múltiples comprobantes, aceptando la operación si al menos 1 es válido.

**Pasos:**
1. Inicia con `/start` → "🧾 Crear nueva operación NetCash"
2. **Paso 1:** Envía 3 comprobantes:
   - 1º: Comprobante válido THABYETHA
   - 2º: Comprobante inválido (otra cuenta)
   - 3º: Comprobante válido THABYETHA
3. Cada vez que envías uno, el bot muestra: "✅ Comprobante recibido. Llevamos X comprobante(s)..."
4. Presiona "➡️ Continuar" después del 3º comprobante
5. **Resultado:** El bot debe avanzar al Paso 2 porque hay al menos 1 válido
6. Completa el flujo (beneficiario nuevo: "ANDRÉS MANUEL LÓPEZ OBRADOR", IDMEX: `1234567890`, ligas: `5`)
7. **Paso 4:** Verifica el resumen:
   ```
   • Comprobantes: 3 archivo(s) (2 válido(s)) ✅
   ```

**Resultado esperado:** Operación creada exitosamente con 3 comprobantes totales, 2 válidos.

---

### **Caso 4: Beneficiario Nuevo (Sin Frecuentes)**
**Objetivo:** Verificar el flujo de captura manual de beneficiario + IDMEX.

**Pasos:**
1. Inicia con `/start` → "🧾 Crear nueva operación NetCash"
2. **Paso 1:** Envía 1 comprobante válido → "➡️ Continuar"
3. **Paso 2:** Si NO tienes beneficiarios frecuentes, escribe un nombre nuevo: `ANDRÉS MANUEL LÓPEZ OBRADOR`
4. Bot valida y pide IDMEX
5. **Paso 2b:** Envía IDMEX: `1234567890`
6. **Paso 3:** Envía ligas: `2`
7. **Paso 4:** Verifica resumen y confirma

**Resultado esperado:** Operación creada con beneficiario y IDMEX capturados manualmente.

---

## ✅ Estado Final del Sistema

- ✅ Backend compilado sin errores
- ✅ Backend corriendo: `RUNNING pid 479`
- ✅ Logs limpios, sin errores de sintaxis o importación
- ✅ Flujo completo refactorizado y reordenado
- ✅ Bug P0 de comprobantes corregido
- ✅ Beneficiarios frecuentes implementados
- ✅ Validación temprana de comprobantes (fallar rápido) implementada
- ⏳ Pendiente: Pruebas manuales del usuario

---

## 🎯 Resumen de Mejoras

### 1. **Fallar Rápido (Comprobantes Primero)**
- El usuario ya no pierde tiempo capturando datos si sus comprobantes no sirven
- La validación de comprobantes ocurre **antes** de pedir beneficiario/IDMEX/ligas

### 2. **Beneficiarios Frecuentes**
- Ahorra tiempo al usuario mostrando sus 3 beneficiarios más usados
- Auto-rellena beneficiario + IDMEX con 1 clic
- Si no hay frecuentes, flujo manual funciona igual

### 3. **Mensajes Claros sobre Comprobantes**
- Diferencia 3 casos: sin archivos, archivos inválidos, archivos válidos
- Muestra en el resumen cuántos comprobantes son válidos vs totales

### 4. **UX Mejorada**
- Mensajes más claros en cada paso
- Uso de ejemplos reales (ANDRÉS MANUEL LÓPEZ OBRADOR como ejemplo)
- Botones inline para acciones frecuentes

---

**Implementado por:** E1 (Emergent Agent)  
**Fecha:** Noviembre 2025  
**Estado:** ✅ Completado - Listo para pruebas manuales
