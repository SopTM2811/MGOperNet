# Feature V3.5: Fuzzy Matching para Nombres de Beneficiarios

## 📋 Resumen

**Versión del Validador**: V3.5-fuzzy-beneficiario  
**Fecha**: Diciembre 2025  
**Tipo**: Feature Enhancement  

Se implementó fuzzy matching para nombres de beneficiarios que tolera errores pequeños de OCR (como letras faltantes o intercambiadas), pero **solo cuando la CLABE de 18 dígitos ha sido detectada de manera exacta**.

---

## 🎯 Objetivo

Resolver el problema donde comprobantes **válidos** eran rechazados debido a errores menores en el reconocimiento OCR del nombre del beneficiario, a pesar de que:
- La CLABE de destino de 18 dígitos es **exactamente correcta**
- El nombre del beneficiario es **casi idéntico** (con errores de OCR menores)

### Ejemplo del problema resuelto:

**Comprobante**: `PAGO - SOLVER - JARDINERIA - EFE NANCY - 2 - 26 NOV 25.pdf`

- **CLABE detectada**: `646180139409481462` ✅ (exacta)
- **Beneficiario esperado**: `JARDINERIA Y COMERCIO THABYETHA SA DE CV`
- **Beneficiario en OCR**: `ARDINERIA Y COMERCIO THABYETHA SA DE CV` ❌ (falta la 'J' inicial)
- **Banco**: STP

**Antes (V3.4)**: Comprobante RECHAZADO (beneficiario no coincide)  
**Ahora (V3.5)**: Comprobante ACEPTADO (fuzzy matching detecta 98.7% de similitud)

---

## 🔒 Criterios de Seguridad (NO SE RELAJA)

### ✅ Fuzzy matching se aplica SOLO cuando:

1. **CLABE completa de 18 dígitos** fue detectada **exactamente** en el texto OCR
2. El beneficiario del OCR tiene una **similitud >= 85%** con el beneficiario esperado
3. No se aplica fuzzy matching en ningún otro caso

### ❌ Fuzzy matching NO se aplica cuando:

- La CLABE solo fue detectada como sufijo enmascarado (ej: `****1462`)
- No se encontró ninguna CLABE de destino
- El beneficiario es completamente diferente (similitud < 85%)

### 🛡️ Garantías de seguridad:

```
SIN CLABE exacta → SIN fuzzy matching → Comprobante RECHAZADO
```

Esto previene que comprobantes de terceros sean aceptados solo porque el nombre es "parecido".

---

## 🧮 Algoritmo de Fuzzy Matching

### 1. Condición de entrada

```python
if clabe_encontrada and metodo_clabe == "completa":
    # Solo aquí se aplica fuzzy matching
    aplicar_fuzzy_matching()
else:
    # Usar solo matching exacto tradicional
    aplicar_matching_tradicional()
```

### 2. Proceso

1. **Dividir el texto OCR en líneas** (preservar estructura)
2. **Normalizar cada línea** individualmente:
   - Mayúsculas
   - Sin acentos
   - Sin puntuación
   - Normalizar variaciones de "SA DE CV"
3. **Filtrar candidatos** por longitud (70%-130% de la longitud del beneficiario esperado)
4. **Extraer subcadenas** de palabras consecutivas dentro de cada línea
5. **Calcular similitud** usando `difflib.SequenceMatcher`
6. **Umbral**: Score >= 0.85 (85%)

### 3. Ejemplo de cálculo

```python
from difflib import SequenceMatcher

beneficiario_esperado = "JARDINERIA Y COMERCIO THABYETHA SA DE CV"
beneficiario_ocr = "ARDINERIA Y COMERCIO THABYETHA SA DE CV"

ratio = SequenceMatcher(None, beneficiario_esperado, beneficiario_ocr).ratio()
# ratio = 0.987 (98.7% de similitud)
# 0.987 >= 0.85 ✅ MATCH FUZZY EXITOSO
```

---

## 📊 Casos de Prueba

### Test 1: Error OCR pequeño (DEBE PASAR) ✅

**Entrada**:
- CLABE: `646180139409481462` (exacta, 18 dígitos)
- Beneficiario esperado: `JARDINERIA Y COMERCIO THABYETHA SA DE CV`
- Beneficiario OCR: `ARDINERIA Y COMERCIO THABYETHA SA DE CV` (falta 'J')

**Resultado**:
- Similitud: 98.7%
- Estado: **VÁLIDO** ✅
- Método: Fuzzy matching

---

### Test 2: Sin CLABE completa (NO DEBE APLICAR FUZZY) ✅

**Entrada**:
- CLABE: `****1462` (enmascarada, NO completa)
- Beneficiario esperado: `JARDINERIA Y COMERCIO THABYETHA SA DE CV`
- Beneficiario OCR: `ARDINERIA Y COMERCIO THABYETHA SA DE CV`

**Resultado**:
- Fuzzy matching: NO SE APLICA (sin CLABE completa)
- Estado: **INVÁLIDO** ❌
- Método: Matching tradicional

---

### Test 3: Beneficiario muy diferente (DEBE RECHAZAR) ✅

**Entrada**:
- CLABE: `646180139409481462` (exacta, 18 dígitos)
- Beneficiario esperado: `JARDINERIA Y COMERCIO THABYETHA SA DE CV`
- Beneficiario OCR: `EMPRESA TOTALMENTE DIFERENTE SA DE CV`

**Resultado**:
- Similitud: 49.3%
- Estado: **INVÁLIDO** ❌ (score < 85%)
- Método: Fuzzy matching rechazó

---

## 📝 Logs de Auditoría

El validador genera logs claros cuando se usa fuzzy matching para facilitar auditorías:

```
[VALIDADOR_FUZZY_BENEFICIARIO] CLABE completa detectada. Aplicando fuzzy matching...
[VALIDADOR_FUZZY_BENEFICIARIO] Mejor candidato: 'ARDINERIA Y COMERCIO THABYETHA SA DE CV'
[VALIDADOR_FUZZY_BENEFICIARIO] Score de similitud: 0.987 (umbral: 0.85)
[VALIDADOR_FUZZY_BENEFICIARIO] Beneficiario objetivo: 'JARDINERIA Y COMERCIO THABYETHA SA DE CV'
[VALIDADOR_FUZZY_BENEFICIARIO] ✅ MATCH FUZZY exitoso! nombre_ocr='ARDINERIA Y COMERCIO THABYETHA SA DE CV' nombre_objetivo='JARDINERIA Y COMERCIO THABYETHA SA DE CV' score=0.987
```

---

## 🔧 Cambios Técnicos

### Archivos modificados:

1. **`/app/backend/validador_comprobantes_service.py`**
   - Versión actualizada: `V3.5-fuzzy-beneficiario`
   - Función modificada: `buscar_beneficiario_en_texto()`
     - Nuevo parámetro: `clabe_completa_encontrada: bool = False`
     - Implementación de fuzzy matching con `difflib.SequenceMatcher`
   - Función modificada: `validar_comprobante()`
     - Ahora pasa información sobre el método de detección de CLABE al validador de beneficiario

### Archivos creados:

1. **`/app/test_fuzzy_beneficiary.py`**
   - Suite de tests automatizados con 3 casos de prueba
   - Incluye el caso obligatorio del comprobante SOLVER/JARDINERIA
   - Tests de regresión para verificar que no se relaja la seguridad

---

## ✅ Verificación

### Tests ejecutados:

```bash
python /app/test_fuzzy_beneficiary.py
```

**Resultado**:
```
✅ Test 1: SOLVER/JARDINERIA con error OCR: PASS
✅ Test 2: Sin CLABE completa, no fuzzy: PASS
✅ Test 3: Beneficiario muy diferente: PASS

Total: 3/3 tests exitosos
🎉 TODOS LOS TESTS PASARON!
```

---

## 📌 Notas Importantes

1. **No se compromete la seguridad**: El fuzzy matching es una capa ADICIONAL de tolerancia, aplicada solo después de verificar la CLABE completa.

2. **Umbral configurable**: El umbral de 0.85 (85%) está definido como constante `UMBRAL_FUZZY` y puede ajustarse según necesidades futuras.

3. **Compatibilidad**: Esta mejora es **completamente retrocompatible** con la versión V3.4. Los comprobantes que antes pasaban siguen pasando.

4. **Performance**: El fuzzy matching se aplica solo cuando es necesario, no afecta el rendimiento en casos donde el match exacto funciona.

---

## 🔄 Historial de Versiones del Validador

- **V3.0**: Multi-layout support (manejo de diferentes formatos de bancos)
- **V3.1**: Bug fix - Detección de CLABEs completas en THABYETHA
- **V3.2**: Detección de duplicados local (mismo operation)
- **V3.3**: Detección de duplicados global (cross-operation)
- **V3.4**: Bug fix - Layout tabular de Inbursa
- **V3.5** 🆕: Fuzzy matching para beneficiarios (con CLABE completa exacta)

---

## 🎯 Impacto

### Antes de V3.5:
- Comprobantes con errores menores de OCR en nombres → ❌ RECHAZADOS
- Usuarios tenían que re-escanear o volver a subir comprobantes válidos
- Frustración en el flujo del usuario

### Después de V3.5:
- Comprobantes con errores menores de OCR en nombres → ✅ ACEPTADOS (si CLABE exacta)
- Mejora significativa en la experiencia del usuario
- Mantiene el mismo nivel de seguridad (CLABE exacta requerida)

---

**Implementado por**: E1 Agent  
**Validado por**: Suite automatizada de tests  
**Status**: ✅ Completado y probado
