# Análisis: OCR Falla en Telegram pero Funciona en Web

## 🐛 PROBLEMA REPORTADO

Usuario reporta que:
- ✅ En la **web**: Los archivos se leen sin problema
- ❌ En **Telegram**: Los mismos archivos causan "dificultad para leer" → captura manual

## 🔍 CAUSA RAÍZ IDENTIFICADA

### Flujo WEB (server.py - líneas 94-128)

```python
# 1. Lee OCR del comprobante
datos_ocr = await ocr_service.leer_comprobante(archivo, mime_type)

# 2. Validación SIMPLE y PERMISIVA
cuenta_valida = validar_cuenta_beneficiaria(datos_ocr["cuenta"], CUENTA_ESPERADA)
nombre_valido = validar_nombre_beneficiario(datos_ocr["nombre"], NOMBRE_ESPERADO)

if cuenta_valida and nombre_valido:
    es_valido = True  # ✅ Comprobante válido
else:
    es_valido = False  # ⚠️ No válido, pero NO activa captura manual
    mensaje = "La cuenta o el beneficiario no coinciden"

# 3. Agrega comprobante y continúa flujo normalmente
```

**Características:**
- ✅ NO usa `ocr_confidence_validator`
- ✅ Solo valida cuenta y beneficiario
- ✅ Si falla, marca como "no válido" pero permite continuar
- ✅ NO activa modo captura manual
- ✅ Usuario puede corregir o agregar más comprobantes

---

### Flujo TELEGRAM (netcash_service.py - líneas 330-413)

```python
# 1. Lee OCR del comprobante
texto = await ocr_service.extraer_texto_pdf(archivo)
datos_parseados = banco_parser.parsear(texto)

# 2. Validación ESTRICTA con ocr_confidence_validator
es_confiable, motivo_fallo, advertencias = ocr_confidence_validator.validar_confianza_ocr(
    datos_ocr={
        'texto_completo': texto,
        'monto_detectado': datos_parseados.get('monto_detectado'),
        'clabe_ordenante': datos_parseados.get('clabe_ordenante'),
        'beneficiario': datos_parseados.get('beneficiario_reportado')
    },
    capital_esperado=capital
)

# 3. Si NO es confiable y es el primer comprobante → ACTIVA CAPTURA MANUAL
if not es_confiable and len(comprobantes_existentes) == 0:
    logger.warning("⚠️ Activando modo captura manual")
    update_fields["modo_captura"] = "manual_por_fallo_ocr"
    return True, "requiere_captura_manual"  # ❌ Activa captura manual inmediatamente
```

**Características:**
- ❌ SÍ usa `ocr_confidence_validator` (muy estricto)
- ❌ Múltiples puntos de fallo (ver abajo)
- ❌ Si falla, activa INMEDIATAMENTE captura manual
- ❌ Usuario no puede continuar con flujo normal

---

## 📋 CRITERIOS ESTRICTOS DEL ocr_confidence_validator

El validador en `ocr_confidence_validator.py` falla si:

### 1. Texto muy corto (< 50 caracteres)
```python
if not texto_extraido or len(texto_extraido.strip()) < 50:
    es_confiable = False
    motivo_fallo = "sin_texto_legible"
```
**Problema:** PDFs con poco texto pero válidos son rechazados

### 2. Monto no detectado o = 0
```python
if monto_detectado is None:
    es_confiable = False
    motivo_fallo = "sin_montos_encontrados"
elif Decimal(str(monto_detectado)) < Decimal('1.00'):
    es_confiable = False
    motivo_fallo = "monto_cero_o_muy_bajo"
```
**Problema:** Si el parser no encuentra el monto (formato diferente), falla

### 3. Sin CLABE detectada
```python
if not clabe_detectada:
    advertencias.append("No se detectó CLABE ordenante")
    # No falla por esto, solo advertencia
```
**Problema:** Advertencia que puede confundir

### 4. Sin beneficiario detectado
```python
if not beneficiario_detectado:
    advertencias.append("No se detectó beneficiario")
```
**Problema:** Advertencia que puede confundir

### 5. Diferencia con capital esperado (> 10%)
```python
if capital_esperado:
    diferencia_porcentual = abs(monto - capital_esperado) / capital_esperado
    if diferencia_porcentual > 0.10:  # 10%
        es_confiable = False
        motivo_fallo = "diferencia_grande_con_capital_esperado"
```
**Problema:** Falsos positivos si capital esperado no está bien configurado

---

## 🎯 SOLUCIONES PROPUESTAS

### Opción 1: Relajar Validaciones del ocr_confidence_validator (RECOMENDADO) ✨

**Ajustes sugeridos:**

```python
# 1. Reducir umbral de texto mínimo
if len(texto_extraido.strip()) < 20:  # Antes: 50
    es_confiable = False

# 2. Permitir monto = 0 (será revisado por humano después)
# Comentar esta validación o hacer que solo genere advertencia

# 3. CLABE y beneficiario → Solo advertencias, NO fallo
# Ya está así, mantener

# 4. Aumentar umbral de diferencia
self.umbral_diferencia_porcentual = 0.25  # 25% en vez de 10%

# 5. NO activar captura manual si solo hay advertencias (no errores críticos)
```

**Ventajas:**
- ✅ Reduce falsos positivos
- ✅ Mantiene validación OCR
- ✅ Solo activa captura manual en casos realmente problemáticos

---

### Opción 2: Usar Misma Lógica que la Web (RÁPIDO) ⚡

Cambiar `netcash_service.agregar_comprobante()` para que:
- NO use `ocr_confidence_validator`
- Use solo validación simple como en web
- Marque comprobantes como válidos/inválidos
- NO active captura manual automáticamente

**Ventajas:**
- ✅ Consistencia entre web y Telegram
- ✅ Menos restricciones
- ✅ Usuario puede continuar flujo

**Desventajas:**
- ⚠️ Pierde la funcionalidad de captura manual inteligente
- ⚠️ Puede permitir comprobantes inválidos

---

### Opción 3: Híbrida (BALANCEADA) ⚖️

Mantener validador pero:
1. Solo activar captura manual en casos CRÍTICOS:
   - PDF completamente sin texto (< 20 chars)
   - Error al leer archivo
2. Para otros casos:
   - Marcar como "requiere revisión"
   - Permitir continuar flujo
   - Ana valida después

**Ventajas:**
- ✅ Balance entre automatización y flexibilidad
- ✅ Mantiene captura manual para casos extremos
- ✅ No bloquea usuario innecesariamente

---

## 📊 COMPARACIÓN DE SOLUCIONES

| Aspecto | Opción 1: Relajar Validador | Opción 2: Como Web | Opción 3: Híbrida |
|---------|---------------------------|-------------------|------------------|
| Complejidad | Media | Baja | Media-Alta |
| Consistencia web/Telegram | Media | Alta | Media |
| Falsos positivos | Reducidos | Muy Reducidos | Mínimos |
| Mantiene captura manual | ✅ Sí | ❌ No | ✅ Sí (críticos) |
| Requiere cambios | Moderados | Mínimos | Moderados |
| Recomendado para | Mejorar actual | Solución rápida | Solución robusta |

---

## 🎬 RECOMENDACIÓN FINAL

**Opción 1: Relajar Validaciones** es la mejor opción porque:

1. ✅ **Mantiene la funcionalidad de captura manual** para casos realmente problemáticos
2. ✅ **Reduce falsos positivos** ajustando umbrales realistas
3. ✅ **No requiere reescribir lógica** completa
4. ✅ **Mejora UX** sin comprometer seguridad

**Cambios específicos a aplicar:**

```python
# En ocr_confidence_validator.py

# 1. Texto mínimo: 50 → 20 caracteres
if len(texto_extraido.strip()) < 20:  # Más permisivo

# 2. Monto mínimo: $1.00 → $0.01 (permite montos muy pequeños)
self.monto_minimo_valido = Decimal('0.01')

# 3. Umbral diferencia: 10% → 25%
self.umbral_diferencia_porcentual = 0.25

# 4. NO fallar por monto = 0 si hay texto legible
# Generar solo advertencia, no error crítico
```

**Resultado esperado:**
- ✅ Telegram procesará más comprobantes exitosamente
- ✅ Solo activará captura manual en casos realmente críticos:
  - PDFs escaneados sin texto
  - Archivos corruptos
  - Errores de lectura graves
- ✅ Consistencia mejorada con web
- ✅ Mejor experiencia de usuario

---

## 📝 PRÓXIMOS PASOS

1. Aplicar ajustes recomendados en `ocr_confidence_validator.py`
2. Probar con comprobantes reales del usuario
3. Monitorear logs para verificar reducción de falsos positivos
4. Ajustar umbrales si es necesario según resultados

¿Proceder con Opción 1?
