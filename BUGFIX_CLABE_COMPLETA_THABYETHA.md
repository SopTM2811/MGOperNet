# Bug Fix: CLABE Completa No Detectada (THABYETHA Montos Pequeños)

**Fecha:** 30 de Noviembre, 2025  
**Versión:** V3.1 (post-bugfix)

## 🐛 Problema Reportado

### Síntoma
Al subir comprobantes de THABYETHA con importes pequeños ($2,500, $4,695, $5,000, $9,400) en Telegram, el bot respondía:

```
❌ Se recibieron 4 comprobante(s), pero ninguno coincide con la cuenta NetCash autorizada.
Detalle: El comprobante tiene el beneficiario correcto pero la CLABE no coincide con 646180139409481462
```

### Evidencia
- `buscar_beneficiario_en_texto()` SÍ encontraba el beneficiario ✅
- `buscar_clabe_en_texto()` NO encontraba la CLABE ❌
- Los PDFs contenían claramente: `Clabe Receptor 646180139409481462`

### Archivos Afectados
- `JARDINERIA_Y_COMERCIO_THABYETHA_$2,500.00.pdf`
- `JARDINERIA_Y_COMERCIO_THABYETHA_$4,695.00.pdf`
- `JARDINERIA_Y_COMERCIO_THABYETHA_$5,000.00.pdf`
- `JARDINERIA_Y_COMERCIO_THABYETHA_$9,400.00.pdf`

---

## 🔍 Diagnóstico - Root Cause Analysis

### Problema 1: Contexto Truncado
**Issue:** El código buscaba el contexto de la CLABE usando posiciones de caracteres (`idx - 100`, `idx + 100`), pero cuando el texto tiene saltos de línea irregulares, el contexto no capturaba correctamente los keywords relevantes.

**Evidencia:**
```
Contexto capturado: "IA Y COMERCIO THABYETHA SA DE CV"
```
Solo capturaba el final del beneficiario, sin incluir "Clabe Receptor".

**Solución:** Cambié la estrategia de búsqueda de contexto a **líneas** en lugar de caracteres, obteniendo 5 líneas antes y 3 líneas después de la CLABE.

---

### Problema 2: Filtro de "RASTREO" Demasiado Agresivo
**Issue:** El código descartaba cualquier CLABE si las palabras "RASTREO" o "REFERENCIA" aparecían **en cualquier parte del contexto** (5 líneas antes y 3 después).

**Evidencia del texto del PDF:**
```
Línea 6: Clave de Rastreo UNALANAPAY0117810163
Línea 7: Beneficiario JARDINERIA Y COMERCIO THABYETHA SA DE CV
Línea 8: Institución Receptora STP
Línea 9: Clabe Receptor 646180139409481462    <-- CLABE objetivo
Línea 10: Email
Línea 11: Referencia 4970049                  <-- Referencia de transacción
```

El filtro detectaba:
- `es_rastreo = True` (porque "RASTREO" está en línea 6 y "REFERENCIA" en línea 11)
- Resultado: La CLABE de línea 9 era **descartada** incorrectamente

**Lógica original (incorrecta):**
```python
keywords_ignorar = ["RASTREO", "REFERENCIA", "AUTORIZACION", "FOLIO", "NUMERO DE"]
es_rastreo = any(kw in contexto for kw in keywords_ignorar)  # Busca en TODO el contexto
```

**Lógica corregida:**
```python
# Buscar SOLO en la línea de la CLABE y la línea inmediatamente anterior
linea_clabe_texto = lineas[linea_clabe]
linea_anterior = lineas[linea_clabe - 1]
contexto_inmediato = (linea_anterior + "\n" + linea_clabe_texto).upper()

es_rastreo = any(kw in contexto_inmediato for kw in keywords_ignorar)
```

**Resultado:** Solo se descarta la CLABE si ella **misma** está etiquetada como "Clave de Rastreo", no si esas palabras aparecen en líneas vecinas.

---

## ✅ Solución Implementada

### Cambio 1: Búsqueda de Contexto por Líneas
**Archivo:** `/app/backend/validador_comprobantes_service.py`  
**Función:** `buscar_clabe_en_texto()`

**Antes (basado en caracteres):**
```python
idx = texto.find(clabe)
contexto_inicio = max(0, idx - 100)
contexto_fin = min(len(texto), idx + len(clabe) + 100)
contexto = texto[contexto_inicio:contexto_fin].upper()
```

**Después (basado en líneas):**
```python
lineas = texto.split('\n')
# Buscar en qué línea está la CLABE
for i, linea in enumerate(lineas):
    if clabe in linea.replace(' ', '').replace('\r', ''):
        linea_clabe = i
        break

# Contexto: 5 líneas antes y 3 líneas después
inicio_contexto = max(0, linea_clabe - 5)
fin_contexto = min(len(lineas), linea_clabe + 4)
lineas_contexto = lineas[inicio_contexto:fin_contexto]
contexto = '\n'.join(lineas_contexto).upper()
```

**Beneficio:** Captura correctamente keywords como "Clabe Receptor" que están en la misma línea o líneas adyacentes.

---

### Cambio 2: Filtro de "Rastreo" Más Específico

**Antes (filtro amplio):**
```python
keywords_ignorar = ["RASTREO", "REFERENCIA", "AUTORIZACION", "FOLIO", "NUMERO DE"]
es_rastreo = any(kw in contexto for kw in keywords_ignorar)  # Busca en 8-9 líneas
```

**Después (filtro específico):**
```python
# Buscar solo en la línea de la CLABE y la inmediatamente anterior
linea_clabe_texto = lineas[linea_clabe]
linea_anterior = lineas[linea_clabe - 1] if linea_clabe > 0 else ""
contexto_inmediato = (linea_anterior + "\n" + linea_clabe_texto).upper()

es_rastreo = any(kw in contexto_inmediato for kw in keywords_ignorar)
```

**Beneficio:** Solo descarta CLABEs que **realmente** son "Clave de Rastreo", no CLABEs válidas que simplemente están cerca de esas palabras.

---

## 🧪 Testing

### Script de Test
Creado: `/app/test_thabyetha_pdfs_reales.py`

**Resultados:**

| PDF | Monto | Estado | Método |
|-----|-------|--------|--------|
| THABYETHA_$2,500.00 | $2,500.00 | ✅ VÁLIDO | completa |
| THABYETHA_$4,695.00 | $4,695.00 | ✅ VÁLIDO | completa |
| THABYETHA_$5,000.00 | $5,000.00 | ✅ VÁLIDO | completa |
| THABYETHA_$9,400.00 | $9,400.00 | ✅ VÁLIDO | completa |

```
🎉 ✅ ¡TODOS LOS COMPROBANTES PASARON LA VALIDACIÓN!
✅ El bug está COMPLETAMENTE RESUELTO
```

---

## 📊 Comparación: Antes vs Después

### Caso de Prueba: THABYETHA_$2,500.00.pdf

**Texto del PDF:**
```
Línea 6: Clave de Rastreo UNALANAPAY0117810163
Línea 7: Beneficiario JARDINERIA Y COMERCIO THABYETHA SA DE CV
Línea 8: Institución Receptora STP
Línea 9: Clabe Receptor 646180139409481462
Línea 10: Email
Línea 11: Referencia 4970049
```

**ANTES (Bug):**
- CLABEs extraídas: `['653180003810172861', '646180139409481462']` ✅
- Contexto capturado: `"IA Y COMERCIO THABYETHA SA DE CV"` ❌ (truncado)
- Keywords detectados: Ninguno ❌
- `es_rastreo`: `True` ❌ (porque "RASTREO" está en línea 6)
- `es_destino`: `False` ❌ (no detecta "RECEPTOR")
- **Resultado:** INVÁLIDO ❌

**DESPUÉS (Fix):**
- CLABEs extraídas: `['653180003810172861', '646180139409481462']` ✅
- Contexto capturado (líneas 4-12): Incluye "CLABE RECEPTOR" ✅
- Keywords detectados: `BENEFICIAR`, `RECEPTOR`, `CLABE RECEPTOR` ✅
- `es_rastreo`: `False` ✅ (solo busca en líneas 8-9, no en línea 6)
- `es_destino`: `True` ✅
- **Resultado:** VÁLIDO ✅ con método `"completa"`

---

## 🎯 Impacto

### Casos Corregidos
✅ Comprobantes de UnalanaPAY con "Clabe Receptor" en la misma línea  
✅ Comprobantes que tienen "Clave de Rastreo" y "Referencia" en líneas separadas  
✅ PDFs con saltos de línea irregulares  
✅ Montos pequeños y grandes de THABYETHA

### Compatibilidad
✅ Los comprobantes que ya funcionaban siguen funcionando  
✅ El caso especial de Banamex (sufijo enmascarado) sigue funcionando  
✅ Los filtros de contexto son más precisos sin ser menos estrictos

---

## 📁 Archivos Modificados

**Backend:**
- `/app/backend/validador_comprobantes_service.py`
  - Función `buscar_clabe_en_texto()` - Búsqueda por líneas y filtro específico de rastreo
  - Logs de debug mejorados para THABYETHA

**Testing:**
- `/app/test_thabyetha_small_amounts.py` - Test con texto de ejemplo
- `/app/test_thabyetha_pdfs_reales.py` - Test con PDFs reales (creado)

---

## 🚀 Despliegue

- ✅ Código corregido
- ✅ Tests pasando (4/4 PDFs válidos)
- ✅ Servicios reiniciados (backend + telegram_bot)
- ✅ Versión actualizada a V3.1

---

## 📝 Lecciones Aprendidas

1. **Búsqueda de contexto:** En PDFs, es más confiable buscar por **líneas** que por **posiciones de caracteres**.

2. **Filtros específicos:** Los filtros deben ser específicos a la entidad que se valida (en este caso, la CLABE), no al contexto general.

3. **Testing con PDFs reales:** Siempre probar con los PDFs reales del usuario, no solo con ejemplos creados manualmente.

4. **Logging detallado:** Los logs de `THABYETHA_DEBUG` fueron cruciales para diagnosticar el problema.

---

## ✅ Verificación en Producción

**Próximos pasos recomendados:**
1. Subir estos 4 comprobantes en Telegram y verificar que pasen el Paso 1
2. Completar una operación end-to-end
3. Monitorear logs para detectar casos edge no cubiertos

**Comando de verificación:**
```bash
cd /app && python3 test_thabyetha_pdfs_reales.py
```

**Resultado esperado:**
```
🎉 ✅ ¡TODOS LOS COMPROBANTES PASARON LA VALIDACIÓN!
```
