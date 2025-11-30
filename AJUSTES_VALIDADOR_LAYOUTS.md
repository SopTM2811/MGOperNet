# Ajustes al Validador de Comprobantes NetCash - Soporte Multi-Layout

**Versión:** V3.0-multi-layout  
**Fecha:** 30 de Noviembre, 2025

## 🎯 Objetivo

Mejorar el validador de comprobantes para que soporte **múltiples formatos/layouts de diferentes bancos** de forma genérica, sin necesidad de hardcodear datos específicos por cada banco o tipo de comprobante.

---

## 🔧 Cambios Implementados

### 1. **Búsqueda de CLABE/Cuenta Destino Mejorada**

#### Antes (V2.1):
- Solo buscaba CLABE completa de 18 dígitos
- Caso especial hardcodeado para "CLABE-462" (Banamex THABYETHA)
- No soportaba otros formatos de enmascaramiento

#### Ahora (V3.0):
✅ **Búsqueda en dos fases:**

**Fase 1: CLABE Completa con Contexto**
- Extrae todas las CLABEs de 18 dígitos del texto
- **Filtra por contexto** para identificar cuál es la cuenta DESTINO:
  - ✅ Acepta si está cerca de: "DESTINO", "BENEFICIAR", "ABONO", "RECEPTOR", "DESTINATARIO"
  - ❌ Rechaza si está cerca de: "ORIGEN", "ASOCIADA", "ORDENANTE", "CUENTA CARGO"
  - ❌ Rechaza si está cerca de: "RASTREO", "REFERENCIA", "AUTORIZACION", "FOLIO"

**Fase 2: Sufijos Enmascarados (si no hay CLABE completa)**
- Busca múltiples formatos de enmascaramiento:
  - `CLABE-462` (formato Banamex)
  - `CLABE-2915` (4 dígitos)
  - `****2915` (asteriscos + 4 dígitos)
  - `****462` (asteriscos + 3 dígitos)
  - `65**0938` (inicio visible + asteriscos + final)
  - `...2915` (puntos suspensivos + dígitos)

- **Valida contexto de destino:**
  - Debe estar cerca de keywords: "CUENTA DESTINO", "CUENTA ABONO", "CUENTA BENEFICIAR", etc.
  - NO debe estar en la misma línea que "ORIGEN", "ORDENANTE", "ASOCIADA"

---

### 2. **Búsqueda de Beneficiario Mejorada**

#### Antes (V2.1):
- Búsqueda simple por coincidencia de palabras (70%)
- No manejaba bien variaciones de "SA DE CV"

#### Ahora (V3.0):
✅ **Normalización avanzada:**
- Quita acentos automáticamente
- Normaliza variaciones: "S.A. DE C.V." → "SA DE CV"
- Soporta "S DE RL DE CV" (sociedades de responsabilidad limitada)

✅ **Búsqueda en múltiples intentos:**
1. **Match exacto** del beneficiario completo
2. **Match sin "SA DE CV"** (para apps móviles que abrevian)
3. **Búsqueda por palabras clave** (≥4 caracteres, 70% de coincidencia)
4. **Búsqueda contextual** cerca de keywords como "BENEFICIAR", "DESTINATARIO", "TITULAR"

---

## 📋 Patrones Soportados por Banco/Layout

### Formato 1: Comprobantes con CLABE Completa
**Ejemplo:** Comprobante de dispersión (STP, Fondeadora)

```
BENEFICIARIO: JARDINERIA Y COMERCIO THABYETHA SA DE CV
CUENTA DESTINO: 646180139409481462
```

**Validación:** Match exacto de CLABE completa (18 dígitos) + beneficiario

---

### Formato 2: Comprobantes con Sufijo Tipo Banamex
**Ejemplo:** PDF Banamex con sufijo

```
Cuenta de depósito NetCash
CLABE-462
Beneficiario: JARDINERIA Y COMERCIO...
```

**Validación:** Sufijo de 3-4 dígitos + beneficiario en contexto

---

### Formato 3: Cuentas Enmascaradas con Asteriscos
**Ejemplo:** App móvil BBVA, Santander

```
Destinatario: UNION AGROINDUSTRIAL TERANITE SA DE CV
Cuenta: ****2915
```

**Validación:** Sufijo enmascarado `****2915` + beneficiario

---

### Formato 4: Layouts Tipo Tabla
**Ejemplo:** Reporte ASP/Fondeadora con múltiples operaciones

```
Banco          | Cuenta Destinatario | Destinatario                    | Monto
FONDEADORA     | 699180600007832915  | UNION AGROINDUSTRIAL TERANITE   | $197,450.00
```

**Validación:** CLABE completa en columna "Cuenta Destinatario" + nombre en columna "Destinatario"

---

### Formato 5: Consulta SPEI con Enmascaramiento Parcial
**Ejemplo:** Portal SPEI con visibilidad parcial

```
Cuenta Beneficiaria: 65**0938
Institución receptora: STP
```

**Validación:** Sufijo visible (inicio + final) `65**0938` + contexto de beneficiaria

---

## 🧪 Ejemplos de Validación

### ✅ CASO VÁLIDO 1: CLABE Completa + Beneficiario
**Comprobante:**
```
ORDENANTE: COFFMAN
BENEFICIARIO: JARDINERIA Y COMERCIO THABYETHA SA DE CV
CUENTA DESTINO: 646180139409481462
MONTO: 250000.00
```

**Parámetros de validación:**
- `clabe_objetivo`: `646180139409481462`
- `beneficiario_objetivo`: `JARDINERIA Y COMERCIO THABYETHA SA DE CV`

**Resultado:** ✅ VÁLIDO  
**Razón:** "CLABE completa encontrada y coincide con la cuenta NetCash autorizada"

---

### ✅ CASO VÁLIDO 2: Sufijo Enmascarado + Beneficiario
**Comprobante:**
```
Destinatario: UNION AGROINDUSTRIAL TERANITE SA DE CV
Cuenta abono: ****2915
Banco: FONDEADORA
```

**Parámetros de validación:**
- `clabe_objetivo`: `699180600007832915`
- `beneficiario_objetivo`: `UNION AGROINDUSTRIAL TERANITE SA DE CV`

**Resultado:** ✅ VÁLIDO  
**Razón:** "Cuenta enmascarada (sufijo 2915) encontrada en contexto de destino y beneficiario coincide"

---

### ❌ CASO INVÁLIDO 1: CLABE Correcta pero Beneficiario Diferente
**Comprobante:**
```
BENEFICIARIO: OTRA EMPRESA SA DE CV
CUENTA DESTINO: 646180139409481462
```

**Parámetros de validación:**
- `clabe_objetivo`: `646180139409481462`
- `beneficiario_objetivo`: `JARDINERIA Y COMERCIO THABYETHA SA DE CV`

**Resultado:** ❌ INVÁLIDO  
**Razón:** "El comprobante tiene la CLABE/cuenta correcta pero el beneficiario no coincide con JARDINERIA Y COMERCIO THABYETHA SA DE CV"

---

### ❌ CASO INVÁLIDO 2: CLABE de Origen (no Destino)
**Comprobante:**
```
CUENTA ORIGEN: 646180139409481462
CUENTA DESTINO: 123456789012345678
```

**Parámetros de validación:**
- `clabe_objetivo`: `646180139409481462`

**Resultado:** ❌ INVÁLIDO  
**Razón:** "El comprobante no corresponde a la cuenta NetCash activa"  
**Explicación:** La CLABE objetivo está marcada como "ORIGEN", por lo que se ignora.

---

### ❌ CASO INVÁLIDO 3: Clave de Rastreo (no es CLABE)
**Comprobante:**
```
CLAVE DE RASTREO: 646180139409481462
CUENTA DESTINO: 999999999999999999
```

**Parámetros de validación:**
- `clabe_objetivo`: `646180139409481462`

**Resultado:** ❌ INVÁLIDO  
**Razón:** La CLABE objetivo aparece en el texto pero como "CLAVE DE RASTREO", no como cuenta destino.

---

## 🔑 Keywords Importantes

### Keywords de DESTINO (se aceptan):
- `DESTINO`
- `BENEFICIAR` / `BENEFICIARIO` / `BENEFICIARIA`
- `ABONO`
- `RECEPTOR` / `RECEPTORA`
- `DESTINATARIO` / `DESTINATARIA`
- `PARA`
- `DEPOSITO`

### Keywords de ORIGEN (se rechazan):
- `ORIGEN`
- `ORDENANTE`
- `ASOCIADA`
- `CUENTA CARGO`

### Keywords de Ruido (se ignoran):
- `RASTREO`
- `REFERENCIA`
- `AUTORIZACION`
- `FOLIO`
- `NUMERO DE`

---

## 📊 Reglas de Validación

### Regla Principal:
Un comprobante es **VÁLIDO** si y solo si:
1. **La cuenta/CLABE de DESTINO coincide** con `clabe_objetivo` (completa o por sufijo enmascarado), **Y**
2. **El beneficiario coincide** con `beneficiario_objetivo` (normalizado, 70%+ de palabras clave)

### Regla Especial para Sufijos Enmascarados:
- Si se usa validación por sufijo enmascarado, **SIEMPRE** se requiere que el beneficiario también coincida.
- Esto evita falsos positivos donde el sufijo podría coincidir por azar.

### Orden de Prioridad:
1. Si hay CLABE completa de DESTINO que coincide → **VÁLIDO** (si beneficiario también coincide)
2. Si hay CLABE completa de DESTINO que NO coincide → **INVÁLIDO** (no se intenta validación por sufijo)
3. Si NO hay CLABE completa de destino → Buscar sufijos enmascarados

---

## 🚀 Mejoras Respecto a V2.1

| Aspecto | V2.1 | V3.0 |
|---------|------|------|
| **Formatos soportados** | Solo CLABE completa + caso especial Banamex | CLABE completa + múltiples formatos enmascarados |
| **Identificación de contexto** | Básica (asociada / rastreo) | Avanzada (destino vs origen, múltiples keywords) |
| **Beneficiario** | Match de palabras simple | Normalización avanzada + búsqueda contextual |
| **Hardcodeo** | Caso Banamex específico | Genérico para todos los bancos |
| **Sufijos soportados** | Solo "CLABE-462" | `****2915`, `65**0938`, `...2915`, etc. |
| **Variaciones SA DE CV** | No | Sí (S.A. DE C.V., S DE RL, etc.) |

---

## ⚠️ Notas Importantes

1. **NO se hardcodean datos específicos:**
   - Los PDFs de ejemplo solo sirvieron para identificar PATRONES
   - El validador trabaja SOLO con parámetros dinámicos: `clabe_objetivo`, `beneficiario_objetivo`, `banco_objetivo`

2. **Compatibilidad hacia atrás:**
   - El caso especial de Banamex THABYETHA (`CLABE-462`) sigue funcionando
   - Todos los comprobantes que funcionaban en V2.1 siguen funcionando en V3.0

3. **Diseño genérico:**
   - No se necesita tocar el código para cada nuevo banco
   - Los patrones se basan en conceptos universales: "cuenta destino", "beneficiario", "CLABE"

4. **Extracción de montos:**
   - La lógica de extracción de montos NO fue modificada
   - Se mantiene la funcionalidad existente en `netcash_service.py`

---

## 🧪 Testing Recomendado

Para verificar que el validador funciona correctamente, probar con:

1. **Comprobantes con CLABE completa** (múltiples bancos)
2. **Comprobantes con sufijos enmascarados** (`****`, `...`, inicio+final)
3. **Layouts tipo tabla** (múltiples operaciones en un PDF)
4. **Apps móviles** con abreviaciones
5. **Casos negativos:**
   - CLABE correcta pero beneficiario incorrecto
   - Beneficiario correcto pero CLABE incorrecta
   - CLABE en "clave de rastreo" (debe ser ignorada)
   - CLABE de origen (debe ser ignorada)

---

## 📝 Archivos Modificados

- `/app/backend/validador_comprobantes_service.py`
  - Función `buscar_clabe_en_texto()` - Reescrita completamente
  - Función `buscar_beneficiario_en_texto()` - Mejorada con normalización avanzada
  - Constante `VALIDADOR_THABYETHA_VERSION` - Actualizada a "V3.0-multi-layout"

---

## ✅ Conclusión

El validador V3.0 es **genérico, robusto y escalable**. Soporta múltiples layouts sin necesidad de casos especiales por banco, manteniendo compatibilidad total con el código existente.

Los principios de validación son claros:
- Buscar cuenta/CLABE de **DESTINO** (no origen)
- Validar **contexto** para evitar falsos positivos
- Requerir **beneficiario** siempre que se use validación por sufijo
- **No hardcodear** datos específicos de comprobantes
