# Bug Fix V3.5.1: Fuzzy Matching no funcionaba en Telegram (Problema de Proximidad)

## 📋 Resumen

**Versión del Validador**: V3.5.1-fuzzy-beneficiario-proximidad  
**Fecha**: Diciembre 2025  
**Tipo**: Bug Fix Crítico  
**Versión anterior**: V3.5-fuzzy-beneficiario

---

## 🐛 Problema Reportado

El usuario reportó que el fuzzy matching implementado en V3.5 **NO estaba funcionando en el flujo real de Telegram**, aunque los tests unitarios pasaban correctamente.

### Síntoma:

```
❌ Se recibieron 1 comprobante(s), pero ninguno coincide con la cuenta NetCash autorizada.

Detalle: Ningún comprobante es válido. Razones: El comprobante no corresponde a la 
cuenta NetCash activa (Banco: STP, CLABE: 646180139409481462, 
Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV)
```

### Comprobante usado:

- **PDF**: `PAGO - SOLVER - JARDINERIA - EFE NANCY - 4 - 26 NOV 25.pdf`
- **CLABE en OCR**: `646180139409481462` ✅ (exacta, 18 dígitos)
- **Beneficiario en OCR**: `ARDINERIA Y COMERCIO THABYETHA SA DE CV` (falta 'J')
- **Beneficiario esperado**: `JARDINERIA Y COMERCIO THABYETHA SA DE CV`

**Lo esperado**: Con fuzzy matching (score 98.7%), el comprobante debería ser **VÁLIDO**  
**Lo que pasaba**: El comprobante era **RECHAZADO**

---

## 🔍 Root Cause Analysis

### Investigación:

Se agregaron logs detallados en el validador y se ejecutó un test con el PDF real. Los logs mostraron:

```
[ValidadorComprobantes] ✗ CLABE 646180139409481462 ignorada (origen=True, rastreo=False, destino=True)
[THABYETHA_DEBUG] Contexto de CLABE 646180139409481462: 
TIPO DE TRANSFERENCIA MISMO DÍA HÁBIL (SPEI)SOLVER BASKET CO S.A. DE C.V. - *0015 CUENTA ORIGEN
CUENTA DESTINO ARDINERIA Y COMERCIO THABYETHA SA DE CV - 646180139409481462
```

### Causa raíz:

El validador estaba **rechazando la CLABE como de DESTINO** porque detectaba la palabra clave "CUENTA ORIGEN" en el contexto de 5 líneas antes de la CLABE.

**Problema en la lógica V3.5:**

```python
# Lógica anterior (V3.5)
keywords_origen = ["ORIGEN", "ASOCIADA", "ORDENANTE", "CUENTA CARGO"]
es_origen = any(kw in texto_antes for kw in keywords_origen)

# Si es_origen=True, rechazar incluso si es_destino=True también
if not es_origen and not es_rastreo and (es_destino or len(clabes_completas) == 1):
    clabes_destino.append(clabe)
```

En el PDF real de Banregio, el OCR extrae el texto en un formato donde:
- "CUENTA ORIGEN" aparece en líneas anteriores al número de CLABE
- "CUENTA DESTINO" aparece en la **misma línea** que la CLABE

Esto causaba que:
1. `es_origen = True` (porque "ORIGEN" está en las 5 líneas anteriores)
2. `es_destino = True` (porque "DESTINO" está en el contexto)
3. **PERO** la condición `if not es_origen ...` fallaba
4. La CLABE se ignoraba → `clabe_completa_encontrada = False`
5. El fuzzy matching **nunca se aplicaba**

---

## 🔧 Solución Implementada

Se agregó una **lógica de desempate por proximidad** cuando ambos `es_origen` y `es_destino` son True.

### Código nuevo (V3.5.1):

```python
# MEJORA V3.5.1: Cuando AMBOS es_origen y es_destino son True, decidir por PROXIMIDAD
if es_origen and es_destino:
    # Buscar qué keyword está más cerca de la CLABE
    distancia_origen = float('inf')
    distancia_destino = float('inf')
    
    for kw in ["ORIGEN", "ASOCIADA", "ORDENANTE", "CUENTA CARGO"]:
        if kw in contexto:
            idx = contexto.find(kw)
            idx_clabe = contexto.find(clabe)
            if idx != -1 and idx_clabe != -1:
                dist = abs(idx - idx_clabe)
                if dist < distancia_origen:
                    distancia_origen = dist
    
    for kw in keywords_destino:
        if kw in contexto:
            idx = contexto.find(kw)
            idx_clabe = contexto.find(clabe)
            if idx != -1 and idx_clabe != -1:
                dist = abs(idx - idx_clabe)
                if dist < distancia_destino:
                    distancia_destino = dist
    
    # Si DESTINO está más cerca, considerar como destino
    if distancia_destino < distancia_origen:
        es_origen = False
        logger.info(f"Ambigüedad resuelta: DESTINO más cercano (dist={distancia_destino} vs {distancia_origen})")
```

### Lógica de desempate:

1. Cuando ambas keywords (ORIGEN y DESTINO) están presentes
2. Calcular la distancia (en caracteres) de cada keyword a la CLABE
3. Si "DESTINO" está más cerca → marcar como DESTINO
4. Si "ORIGEN" está más cerca → marcar como ORIGEN

---

## ✅ Validación

### Test con PDF real creado:

Se creó `/app/test_fuzzy_real_pdf.py` que descarga y valida el PDF exacto reportado por el usuario.

**Resultado ANTES del fix:**
```
❌ FALLO: El comprobante fue RECHAZADO
CLABE encontrada: False
Fuzzy matching: NO SE APLICÓ
```

**Resultado DESPUÉS del fix:**
```
✅ ÉXITO: El comprobante fue validado correctamente
CLABE encontrada: True (método: completa)
Fuzzy matching: APLICADO (score=0.987)
Ambigüedad resuelta: DESTINO más cercano (dist=50 vs 64)
```

### Tests de regresión:

Todos los tests anteriores de V3.5 siguen pasando:
```bash
$ python test_fuzzy_beneficiary.py
✅ Test 1: SOLVER/JARDINERIA con error OCR: PASS
✅ Test 2: Sin CLABE completa, no fuzzy: PASS
✅ Test 3: Beneficiario muy diferente: PASS

Total: 3/3 tests exitosos
```

---

## 📝 Logs Mejorados

Se agregaron logs adicionales para facilitar debugging:

```python
# Log detallado del flag que controla el fuzzy matching
logger.info(f"[VALIDADOR_NETCASH] clabe_objetivo={clabe_activa} clabe_encontrada={clabe_encontrada} metodo={metodo_clabe} clabe_completa_encontrada={clabe_completa_encontrada}")
logger.info(f"[VALIDADOR_NETCASH] Llamando a buscar_beneficiario_en_texto con clabe_completa_encontrada={clabe_completa_encontrada}")

# Log del fuzzy matching
logger.info(f"[VALIDADOR_FUZZY_BENEFICIARIO] clabe_completa_encontrada={clabe_completa_encontrada}")
logger.info(f"[VALIDADOR_FUZZY_BENEFICIARIO] nombre_objetivo_normalizado={beneficiario_norm}")

# Log de éxito
logger.info(f"[VALIDADOR_FUZZY_BENEFICIARIO] MATCH_FUZZY_OK score={mejor_score:.3f}")
```

### Cómo verificar en producción:

```bash
# Ver logs del backend con filtro de fuzzy
grep -E "VALIDADOR_NETCASH|VALIDADOR_FUZZY_BENEFICIARIO" /var/log/supervisor/backend.err.log | tail -50

# Verificar versión del validador
grep "Version=" /var/log/supervisor/backend.err.log | tail -5
```

Debería verse:
```
[VALIDADOR_NETCASH] Version=V3.5.1-fuzzy-beneficiario-proximidad archivo=...
[VALIDADOR_NETCASH] clabe_completa_encontrada=True
[VALIDADOR_FUZZY_BENEFICIARIO] MATCH_FUZZY_OK score=0.987
```

---

## 🎯 Impacto

### Antes de V3.5.1:
- PDFs de Banregio con formato específico → ❌ RECHAZADOS incorrectamente
- Fuzzy matching implementado pero **no funcionaba** en producción
- Tests unitarios pasaban pero **no replicaban el problema real**

### Después de V3.5.1:
- PDFs de Banregio con ambigüedad ORIGEN/DESTINO → ✅ RESUELTOS por proximidad
- Fuzzy matching **funciona correctamente** en Telegram
- Test creado con PDF real para prevenir regresión

---

## 📚 Archivos Modificados/Creados

### Modificados:
1. **`/app/backend/validador_comprobantes_service.py`**
   - Versión: V3.5.1-fuzzy-beneficiario-proximidad
   - Función `buscar_clabe_en_texto()`: Agregada lógica de desempate por proximidad
   - Función `validar_comprobante()`: Agregados logs detallados

### Creados:
1. **`/app/test_fuzzy_real_pdf.py`**
   - Test con el PDF real reportado por el usuario
   - Descarga el PDF desde la URL y valida con el flujo completo
   - Garantiza que el bug no vuelva a ocurrir

2. **`/app/BUGFIX_V3.5.1_FUZZY_PROXIMIDAD.md`**
   - Documentación completa del bug fix

---

## 🔄 Deployment

### Pasos ejecutados:

```bash
# 1. Reiniciar servicios para aplicar cambios
sudo supervisorctl restart backend telegram_bot

# 2. Verificar que estén corriendo
sudo supervisorctl status backend telegram_bot

# 3. Verificar versión en logs
tail -f /var/log/supervisor/backend.err.log | grep "Version="
```

---

## 🎉 Resultado Final

✅ El comprobante `PAGO - SOLVER - JARDINERIA - EFE NANCY - 4 - 26 NOV 25.pdf` ahora es **aceptado correctamente** en Telegram  
✅ Fuzzy matching funciona en producción como se esperaba  
✅ No hay regresiones en otros casos de prueba  
✅ Logs mejorados facilitan debugging futuro  

---

**Status**: ✅ **RESUELTO Y PROBADO**  
**Implementado por**: E1 Agent  
**Probado por**: Test automatizado + Usuario en Telegram
