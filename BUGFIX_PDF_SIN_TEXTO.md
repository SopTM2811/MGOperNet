# Bug Fix: Detección de PDFs Sin Texto Legible (Imágenes Escaneadas)

## 📋 Resumen

**Fecha**: Diciembre 2025  
**Tipo**: Bug Fix + UX Improvement  
**Prioridad**: P0  

Se implementó detección específica para PDFs e imágenes sin texto legible (escaneados, capturas de pantalla) para mostrar mensajes claros al usuario, diferenciándolos de comprobantes que no coinciden con la cuenta NetCash.

---

## 🐛 Problema Reportado

### Síntoma:

Usuario sube un ZIP con 9 comprobantes que visualmente son correctos:
- Archivo ejemplo: `26112025 $250,000.00 MXN TRANSFERENCIA JARDINERIA THABYETHA - EFECT PROV EXT (APOYO HMO) LTZ 1.pdf`
- Cuenta esperada:
  - Banco: STP
  - CLABE: 646180139409481462
  - Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV

**Sistema rechazaba con mensaje confuso:**
```
❌ Se recibieron 9 comprobante(s), pero ninguno coincide con la cuenta NetCash autorizada.

Detalle: Ningún comprobante es válido. Razones: No se pudo leer el comprobante o está vacío
```

### Causa raíz:

Los PDFs son **imágenes escaneadas** sin texto embebido. Cuando el validador intenta extraer texto con PyPDF2, obtiene string vacío o casi vacío (< 20 caracteres).

**El problema NO es que los comprobantes sean inválidos**, sino que **no tienen texto seleccionable**.

El mensaje "no coincide con la cuenta NetCash activa" es **incorrecto y confuso** porque da a entender que:
- La CLABE no coincide
- El beneficiario no coincide

Cuando en realidad el problema es: **"No pudimos leer texto del PDF"**.

---

## 🔧 Solución Implementada

### 1. Detección Específica en el Validador

**Archivo**: `/app/backend/validador_comprobantes_service.py`

**Antes (confuso):**
```python
if not texto_comprobante or len(texto_comprobante) < 20:
    return False, "No se pudo leer el comprobante o está vacío"
```

**Ahora (específico):**
```python
# DETECCIÓN ESPECÍFICA: PDF sin texto legible (imagen escaneada)
if not texto_comprobante or len(texto_comprobante.strip()) < 20:
    logger.warning(f"[ValidadorComprobantes] ❌ PDF sin texto legible (len={len(texto_comprobante) if texto_comprobante else 0})")
    logger.warning(f"[ValidadorComprobantes] Posible causa: Imagen escaneada o captura de pantalla sin texto seleccionable")
    
    # Razón específica para distinguir de otros errores
    return False, "pdf_sin_texto_legible"
```

**Cambios clave:**
- Nueva razón específica: `"pdf_sin_texto_legible"`
- Log claro indicando el problema
- Umbral: < 20 caracteres (sensato para detectar PDFs sin contenido real)

---

### 2. Mensajes Específicos en Telegram

#### Para Comprobante Individual:

**Archivo**: `/app/backend/telegram_netcash_handlers.py`

Cuando el usuario intenta continuar sin comprobantes válidos, el sistema ahora distingue entre:

**ANTES (confuso):**
```
❌ Se recibieron 9 comprobante(s), pero ninguno coincide con la cuenta NetCash autorizada.
```

**AHORA (claro):**
```
❌ Se recibieron 9 comprobante(s), pero ninguno es válido.

Detalle:
• 9 comprobante(s) sin texto legible (imagen escaneada o captura)

⚠️ Los comprobantes deben ser documentos originales donde se pueda seleccionar el texto 
(beneficiario y CLABE). Las capturas de pantalla o PDFs escaneados sin texto no son válidos.

La cuenta NetCash autorizada es:
• Banco: STP
• CLABE: 646180139409481462
• Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV
```

#### Para Archivo ZIP:

**ANTES (confuso):**
```
⚠️ No se encontraron comprobantes válidos dentro del archivo ZIP.

• 9 archivo(s) encontrado(s) dentro
• 9 comprobante(s) no coinciden con la cuenta NetCash activa
```

**AHORA (claro):**
```
⚠️ No se encontraron comprobantes válidos dentro del archivo ZIP.

• 9 archivo(s) encontrado(s) dentro
• 9 comprobante(s) sin texto legible (imagen escaneada) ⚠️

⚠️ Nota importante: Los comprobantes deben ser documentos originales donde se pueda 
seleccionar el texto. Las capturas de pantalla o PDFs escaneados sin texto no son válidos.

Asegúrate de que el ZIP contenga PDFs o imágenes de comprobantes para la cuenta NetCash autorizada.
```

---

### 3. Estadísticas Detalladas en ZIP

Se agregó un nuevo contador en `procesar_archivo_zip()`:

**Antes:**
```python
resultado = {
    "total_archivos": 0,
    "validos": 0,
    "invalidos": 0,
    "duplicados": 0,
    "no_legibles": 0,
    "archivos_procesados": []
}
```

**Ahora:**
```python
resultado = {
    "total_archivos": 0,
    "validos": 0,
    "invalidos": 0,
    "sin_texto_legible": 0,  # 🆕 PDFs/imágenes sin texto extraíble
    "duplicados": 0,
    "no_legibles": 0,
    "archivos_procesados": []
}
```

**Clasificación inteligente:**
```python
if razon_invalido == "pdf_sin_texto_legible":
    resultado["sin_texto_legible"] += 1
    resultado["archivos_procesados"].append({
        "nombre": nombre_interno,
        "estado": "sin_texto_legible",
        "razon": "PDF/imagen sin texto seleccionable"
    })
else:
    resultado["invalidos"] += 1
    # ... otros errores
```

---

## 🧪 Testing

### Test Automatizado Actualizado

**Archivo**: `/app/test_zip_processing.py`

**Resultado del test con ZIP real del usuario:**

```
================================================================================
RESULTADO DEL PROCESAMIENTO
================================================================================
Total archivos encontrados: 9
Comprobantes válidos: 0
Comprobantes sin texto legible: 9  ✅ (detectados correctamente)
Comprobantes inválidos: 0
Duplicados: 0
No legibles: 0
================================================================================

📋 Detalle de archivos procesados:
  • 26112025 $250,000.00 MXN TRANSFERENCIA JARDINERIA THABYETHA - EFECT PROV EXT (APOYO HMO)  LTZ 1.pdf: sin_texto_legible
  • 26112025 $250,000.00 MXN TRANSFERENCIA JARDINERIA THABYETHA - EFECT PROV EXT (APOYO HMO)  LTZ 2.pdf: sin_texto_legible
  • 26112025 $250,000.00 MXN TRANSFERENCIA JARDINERIA THABYETHA - EFECT PROV EXT (APOYO HMO)  LTZ 3.pdf: sin_texto_legible
  • 26112025 $250,000.00 MXN TRANSFERENCIA JARDINERIA THABYETHA - EFECT PROV EXT (APOYO HMO)  LTZ 4.pdf: sin_texto_legible
  • 26112025 $3,250.00 MXN PAGO COMISION .65% JARINERIA THABYETHA (EFECTIVO PROV EXT) APOYO HMO.pdf: sin_texto_legible
  • 26112025 $3,250.00 MXN PAGO COMISION .65% JARINERIA THABYETHA (EFECTIVO PROV EXT) APOYO HMO 2.pdf: sin_texto_legible
  • INE-GERARDO HERNANDEZ MORENO (1).pdf: sin_texto_legible
  • Imagen de WhatsApp 2025-11-25 a las 16.54.09_018f4baa.jpg: sin_texto_legible
  • Imagen de WhatsApp 2025-11-25 a las 16.54.09_fad8b881.jpg: sin_texto_legible

✅ Comprobantes en la solicitud: 9
   Válidos: 0
   Inválidos: 9 (todos marcados con razón "pdf_sin_texto_legible")
```

**Verificación:**
✅ Los 9 archivos fueron correctamente clasificados como "sin_texto_legible"  
✅ NO se clasificaron como "no coinciden con cuenta NetCash"  
✅ El mensaje sería claro para el usuario  

---

## 📊 Casos de Uso

### Caso 1: ZIP con solo PDFs sin texto ✅

**Entrada:**
- 9 PDFs escaneados sin texto seleccionable

**Salida:**
```
⚠️ No se encontraron comprobantes válidos dentro del archivo ZIP.

• 9 archivo(s) encontrado(s) dentro
• 9 comprobante(s) sin texto legible (imagen escaneada) ⚠️

⚠️ Nota importante: Los comprobantes deben ser documentos originales...
```

---

### Caso 2: ZIP mixto (con texto + sin texto) ✅

**Entrada:**
- 3 PDFs con texto seleccionable válidos
- 5 PDFs escaneados sin texto
- 1 PDF inválido (CLABE no coincide)

**Salida:**
```
✅ Se procesó tu archivo ZIP.

• 9 archivo(s) encontrado(s) dentro
• 3 comprobante(s) válido(s) ✅
• 5 comprobante(s) sin texto legible (no se incluyeron) ⚠️
• 1 comprobante(s) inválido(s) (no se incluyeron)

💰 Total de depósitos detectados hasta ahora: $XXX,XXX.XX
```

---

### Caso 3: Comprobante individual sin texto ✅

**Entrada:**
- 1 PDF escaneado sin texto

**Cuando el usuario intenta continuar:**
```
❌ Se recibieron 1 comprobante(s), pero ninguno es válido.

Detalle:
• 1 comprobante(s) sin texto legible (imagen escaneada o captura)

⚠️ Los comprobantes deben ser documentos originales donde se pueda seleccionar el texto...
```

---

## 🔄 Compatibilidad

### Lo que NO cambió:

✅ **Validación de comprobantes con texto** - Funciona igual  
✅ **Validador V3.5.1** - Sin cambios  
✅ **Detección de duplicados** - Sin cambios  
✅ **Fuzzy matching de beneficiarios** - Sin cambios  
✅ **CLABE estricta** - Sin cambios  
✅ **Reglas de negocio** - Sin cambios  

### Lo que se agregó:

🆕 **Detección específica de PDFs sin texto**  
🆕 **Razón "pdf_sin_texto_legible"**  
🆕 **Mensajes claros para usuario**  
🆠**Contador separado en ZIPs**  
🆕 **Logs específicos para debugging**  

---

## 📝 Archivos Modificados

### 1. `/app/backend/validador_comprobantes_service.py`

**Cambios:**
- Detección de texto < 20 caracteres
- Nueva razón: `"pdf_sin_texto_legible"`
- Logs específicos

**Líneas modificadas:** ~5 líneas

---

### 2. `/app/backend/netcash_service.py`

**Cambios:**
- Agregado contador `"sin_texto_legible"` en `procesar_archivo_zip()`
- Clasificación inteligente de comprobantes inválidos
- Distinción entre "sin texto" vs "no coincide"

**Líneas modificadas:** ~20 líneas

---

### 3. `/app/backend/telegram_netcash_handlers.py`

**Cambios:**
- Análisis de razones de invalidez para mensajes claros
- Mensajes específicos para PDFs sin texto
- Contador de "sin_texto_legible" en ZIPs
- Nota educativa para el usuario

**Líneas modificadas:** ~40 líneas

---

### 4. `/app/test_zip_processing.py`

**Cambios:**
- Agregado output de "sin_texto_legible" en resultados

**Líneas modificadas:** ~2 líneas

---

## 🚀 Deployment

```bash
# Servicios reiniciados
sudo supervisorctl restart backend telegram_bot

# Status
backend: RUNNING
telegram_bot: RUNNING
```

---

## 📋 Verificación por Usuario - PENDIENTE

**Pasos para probar en Telegram:**

1. **Subir el ZIP que reportaste:**
   - Archivo: `netcashdanitza1000000jardineria261125 (2).zip`
   - **Esperado**: Mensaje claro indicando "9 comprobante(s) sin texto legible (imagen escaneada)"

2. **Verificar mensaje educativo:**
   - Debe decir claramente: "Los comprobantes deben ser documentos originales donde se pueda seleccionar el texto"
   - **NO** debe decir: "no coinciden con la cuenta NetCash activa"

3. **Probar comprobante individual sin texto:**
   - Subir 1 PDF escaneado
   - Intentar continuar
   - **Esperado**: Mensaje específico sobre texto legible

4. **Verificar que comprobantes CON texto siguen funcionando:**
   - Subir un PDF con texto seleccionable válido
   - **Esperado**: Debe ser aceptado normalmente

---

## 🎯 Impacto

**ANTES:**
- PDF sin texto → ❌ "No coincide con cuenta NetCash" (confuso)
- Usuario no entiende qué está mal
- Piensa que sus comprobantes son incorrectos

**AHORA:**
- PDF sin texto → ⚠️ "Sin texto legible (imagen escaneada)" (claro)
- Usuario entiende el problema: necesita documento original
- Mensaje educativo sobre qué es un documento válido

---

## 🔜 Próximos Pasos (Fuera de Alcance P0)

**No implementado en este fix (futuro):**
- ❌ OCR con Tesseract para procesar imágenes escaneadas
- ❌ Aceptación automática de PDFs escaneados
- ❌ Conversión de imágenes a texto

**Razón:** El usuario solicitó explícitamente:
> "NO quiero que estos comprobantes se acepten automáticamente (ahora mismo no hay OCR).  
> SOLO quiero que el sistema sea honesto con la causa."

---

## ✅ Resumen

Este fix **NO relaja las reglas de validación**. Solo hace el sistema más **honesto y claro** sobre por qué rechaza un comprobante.

**Reglas mantenidas:**
- ✅ CLABE de 18 dígitos estricta
- ✅ Fuzzy matching solo con CLABE exacta
- ✅ Detección de duplicados
- ✅ Todas las reglas de negocio

**Mejora UX:**
- ✅ Mensajes específicos por tipo de error
- ✅ Usuario entiende qué hacer
- ✅ Sistema más transparente

---

**Status**: ✅ **COMPLETADO Y PROBADO**  
**Implementado por**: E1 Agent  
**Probado**: Test automatizado con ZIP real del usuario  
**Listo para**: Verificación del usuario en Telegram
