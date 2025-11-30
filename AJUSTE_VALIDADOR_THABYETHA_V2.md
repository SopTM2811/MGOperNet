# Ajuste V2: Validador de Comprobantes THABYETHA Banamex

## 📅 Fecha: 30 Nov 2025

## 🎯 Objetivo
Implementar validación correcta de comprobantes de Banamex para THABYETHA que solo contienen sufijo "CLABE-462" en lugar de CLABE completa (18 dígitos), manteniendo validación estricta para otros bancos.

---

## 📋 Especificaciones del Problema

### Cuenta NetCash THABYETHA
- **Banco:** STP
- **CLABE:** 646180139409481462
- **Beneficiario:** JARDINERIA Y COMERCIO THABYETHA SA DE CV
- **Sufijo esperado:** 462 (últimos 3 dígitos)

### Estructura de los Comprobantes Banamex
Los PDFs de Banamex para THABYETHA contienen:

1. **CLABE asociada (origen - IGNORAR):**
   ```
   CLABE asociada: ***************007
   ```
   → Esta es la cuenta de retiro del cliente, NO la cuenta NetCash

2. **Cuenta de depósito (destino - VALIDAR):**
   ```
   Cuenta de depósito:   
   (Dato no verificado por esta institución)
   THABYETHA SA DE CV-
   SIST TRANSF Y PAGOS-
   CLABE-462-JARDINERIA Y 
   COMERCIO THABYETHA SA 
   DE CV
   ```
   → Aquí está el sufijo "CLABE-462" que debemos validar

3. **Clave de rastreo (NO es CLABE):**
   ```
   Clave de rastreo: 085901921704333355
   ```
   → Este número de 18 dígitos NO es una CLABE, es un número de transacción

---

## 🔧 Cambios Implementados

### Archivo Modificado
`/app/backend/validador_comprobantes_service.py`

### Método `buscar_clabe_en_texto()` - Lógica Completa

#### PASO A: Buscar CLABEs Completas (18 dígitos)

```python
# Extraer todas las CLABEs completas (18 dígitos)
clabes_completas = self.extraer_clabes_del_texto(texto)

# Filtrar CLABEs inválidas
clabes_validas = []
for clabe in clabes_completas:
    contexto = texto[idx-50:idx+50].upper()
    
    # Ignorar "CLABE asociada" (cuenta de origen)
    if "CLABE ASOCIADA" in contexto or "ASOCIADA" in contexto:
        continue
    
    # Ignorar CLABEs enmascaradas
    if "*" in contexto:
        continue
    
    # NUEVO: Ignorar "Clave de rastreo"
    if "CLAVE DE RASTREO" in contexto or "RASTREO" in contexto:
        continue
    
    # NUEVO: Ignorar números de referencia/autorización
    if "REFERENCIA" in contexto or "AUTORIZACION" in contexto:
        continue
    
    clabes_validas.append(clabe)
```

**Si hay CLABE completa que coincide:** `return True, "completa"`

**Si hay CLABEs completas pero ninguna coincide:** `return False, "no_encontrada"` (NO aplica sufijo)

#### PASO B: Validación por Sufijo (solo si NO hay CLABEs completas)

```python
# Solo si NO hay CLABEs completas válidas
if len(clabes_validas) == 0:
    sufijo_3 = clabe_objetivo[-3:]  # "462"
    
    patrones = ["CLABE-462", "CLABE 462", "CLABE: 462"]
    
    for patron in patrones:
        if patron in texto.upper():
            # Validación 1: NO en misma LÍNEA que "ASOCIADA" o asteriscos
            lineas = contexto.split('\n')
            linea_con_patron = buscar_linea_con_patron(lineas, patron)
            
            if "ASOCIADA" in linea_con_patron or "*" in linea_con_patron:
                continue  # Rechazar
            
            # Validación 2: Debe estar en contexto de "Cuenta de depósito"
            # (Normalizar para ignorar acentos: "depósito" → "deposito")
            import unicodedata
            contexto_normalizado = normalize(contexto)
            
            if "CUENTA DE DEPOSITO" in contexto_normalizado:
                return True, "sufijo_banamex"
```

### Método `validar_comprobante()` - Mensajes Actualizados

```python
clabe_encontrada, metodo_clabe = self.buscar_clabe_en_texto(...)
beneficiario_encontrado = self.buscar_beneficiario_en_texto(...)

# Regla especial: Si sufijo_banamex, DEBE tener beneficiario
if metodo_clabe == "sufijo_banamex" and not beneficiario_encontrado:
    return False, f"Sufijo CLABE-{sufijo} pero beneficiario NO coincide"

# Resultado final
if clabe_encontrada and beneficiario_encontrado:
    if metodo_clabe == "completa":
        return True, "CLABE encontrada completa y coincide con la cuenta NetCash autorizada"
    elif metodo_clabe == "sufijo_banamex":
        return True, f"CLABE encontrada en formato Banamex (CLABE-{sufijo}) y coincide con la cuenta NetCash autorizada"
```

---

## ✅ Reglas de Validación Finales

### Caso 1: CLABE Completa (Validación Estricta)
- Se encuentra una CLABE de 18 dígitos sin enmascarar
- La CLABE coincide EXACTAMENTE con `646180139409481462`
- El beneficiario coincide
- → **✅ VÁLIDO** (método: "completa")

### Caso 2: Sufijo Banamex (Validación Controlada)
- NO hay CLABEs completas válidas en el comprobante
- Se encuentra el patrón "CLABE-462" en el texto
- El patrón NO está en la misma línea que "ASOCIADA" o asteriscos
- El patrón está en contexto de "Cuenta de depósito"
- El beneficiario completo coincide: `JARDINERIA Y COMERCIO THABYETHA SA DE CV`
- → **✅ VÁLIDO** (método: "sufijo_banamex")

### Se IGNORAN:
- ❌ CLABEs con "CLABE asociada" (cuenta de origen)
- ❌ CLABEs con asteriscos (enmascaradas)
- ❌ "Clave de rastreo" (número de transacción de 18 dígitos)
- ❌ Números de "Referencia" o "Autorización"

---

## 🧪 Pruebas Realizadas

### PDFs de THABYETHA Probados
1. `THABYETHA SA $185,000.00.pdf`
2. `THABYETHA SA $179,800.00.pdf`
3. `THABYETHA SA $135,200.00.pdf`

### Script de Prueba
`/app/test_validador_thabyetha.py`

### Resultado de las Pruebas

```
================================================================================
RESUMEN DE PRUEBAS
================================================================================

📊 Total de comprobantes probados: 3
✅ Válidos: 3
❌ Inválidos: 0

🎉 ¡TODAS LAS PRUEBAS PASARON!
Los comprobantes THABYETHA de Banamex se validan correctamente.
================================================================================
```

**Detalles:**
- ✅ Los 3 PDFs se validan correctamente usando `metodo="sufijo_banamex"`
- ✅ Mensaje de validación: "CLABE encontrada en formato Banamex (CLABE-462) y coincide con la cuenta NetCash autorizada"
- ✅ Se ignoraron correctamente:
  - "CLABE asociada: ***************007"
  - "Clave de rastreo: 085901921704333355"

---

## 🔄 Compatibilidad con Otros Bancos

### Prueba de Regresión

**Escenario:** Comprobante con CLABE completa diferente

Si un comprobante tiene:
- CLABE completa: `012345678901234567` (diferente a THABYETHA)
- Beneficiario: Cualquiera

**Resultado esperado:**
- ❌ **INVÁLIDO**
- Razón: "El comprobante tiene el beneficiario correcto pero la CLABE no coincide con 646180139409481462"
- NO se aplica validación por sufijo

**Comportamiento confirmado:**
- ✅ La validación estricta se mantiene para comprobantes con CLABE completa
- ✅ La validación por sufijo SOLO aplica cuando NO hay CLABEs completas

---

## 📊 Comparación: Antes vs Después

### ANTES (Incorrecto)
```
❌ Se recibieron 3 comprobante(s), pero ninguno coincide con la cuenta NetCash autorizada.

Detalle: Ningún comprobante es válido. 
Razones: El comprobante tiene el beneficiario correcto pero la CLABE no coincide con 646180139409481462
```

### DESPUÉS (Correcto)
```
✅ Comprobantes: 3 archivo(s) (3 válido(s)) ✅

Validación: CLABE encontrada en formato Banamex (CLABE-462) y coincide con la cuenta NetCash autorizada
```

---

## 🔑 Elementos Clave de la Solución

### 1. Filtrado Inteligente de "CLABEs"
- Se ignoran números de 18 dígitos que son "Clave de rastreo", "Referencia", etc.
- Solo se consideran CLABEs reales en contexto bancario

### 2. Validación de Línea Específica
- No basta con que "CLABE asociada" esté en el contexto general
- Se verifica que "CLABE-462" NO esté en la MISMA LÍNEA que "ASOCIADA"
- Esto permite que ambos coexistan en el mismo comprobante

### 3. Normalización de Texto
- Se normaliza el texto para ignorar acentos ("depósito" → "deposito")
- Esto asegura que "Cuenta de depósito" se detecte correctamente

### 4. Validación de Beneficiario Obligatoria
- Cuando se usa sufijo_banamex, el beneficiario DEBE coincidir
- Esto agrega una capa extra de seguridad

---

## 🎯 Casos de Uso Cubiertos

### ✅ Caso A: Comprobante Banamex THABYETHA
- Tiene: "CLABE-462" + beneficiario completo
- NO tiene: CLABE completa de 18 dígitos
- **Resultado:** ✅ VÁLIDO (sufijo_banamex)

### ✅ Caso B: Comprobante con CLABE Completa Correcta
- Tiene: CLABE completa `646180139409481462`
- Tiene: Beneficiario correcto
- **Resultado:** ✅ VÁLIDO (completa)

### ✅ Caso C: Comprobante con CLABE Completa Incorrecta
- Tiene: CLABE completa `012345678901234567` (diferente)
- **Resultado:** ❌ INVÁLIDO (validación estricta)

### ✅ Caso D: Comprobante Mixto (CLABE + sufijo)
- Tiene: CLABE completa diferente + sufijo "462"
- **Resultado:** ❌ INVÁLIDO (prioridad a CLABE completa)

---

## 📝 Logs de Ejemplo

### Comprobante THABYETHA (Válido)
```
[ValidadorComprobantes] CLABEs de 18 dígitos encontradas: ['085901921704333355']
[ValidadorComprobantes] ❌ Ignorando 085901921704333355 (es 'Clave de rastreo' - no es CLABE)
[ValidadorComprobantes] No se encontró ninguna CLABE completa válida (18 dígitos)
[ValidadorComprobantes] No hay CLABEs completas válidas. Activando regla de sufijo Banamex...
[ValidadorComprobantes] Buscando sufijo: 462
[ValidadorComprobantes] ⚠️ Encontrado patrón: 'CLABE-462'
[ValidadorComprobantes] ✅ Patrón CLABE-462 está en contexto de depósito ✅
[ValidadorComprobantes] ✅✅✅ SUFIJO BANAMEX VÁLIDO: CLABE-462 encontrado en contexto de depósito
[ValidadorComprobantes] ✅✅✅ VÁLIDO: CLABE-462 (sufijo Banamex) y beneficiario coinciden
```

---

## ✅ Estado Final

**Archivo modificado:**
- `/app/backend/validador_comprobantes_service.py`
  - Método `buscar_clabe_en_texto()`: Líneas 115-221
  - Método `validar_comprobante()`: Líneas 245-275

**Script de prueba creado:**
- `/app/test_validador_thabyetha.py`

**Servicios:**
- ✅ Backend reiniciado: RUNNING pid 1184
- ✅ Código compilado sin errores
- ✅ 3/3 pruebas con PDFs THABYETHA: PASADAS ✅

**Flujo de Telegram:**
- ✅ NO modificado (solo el validador)
- ✅ UX de multi-comprobantes intacta
- ✅ Orden de pasos intacto

---

## 🎯 Resumen Ejecutivo

### Problema Resuelto
Los comprobantes de Banamex para THABYETHA con sufijo "CLABE-462" ahora se validan correctamente.

### Solución Implementada
1. ✅ Filtrado inteligente de "CLABEs" (ignora clave de rastreo, referencias)
2. ✅ Validación por línea específica (no rechaza si "CLABE asociada" está en otra línea)
3. ✅ Normalización de texto (ignora acentos)
4. ✅ Validación de beneficiario obligatoria para sufijo_banamex
5. ✅ Mantiene validación estricta para CLABEs completas

### Resultado
- **Antes:** 0/3 comprobantes THABYETHA válidos ❌
- **Ahora:** 3/3 comprobantes THABYETHA válidos ✅
- **Compatibilidad:** Validación estricta para otros bancos intacta ✅

---

**Implementado por:** E1 (Emergent Agent)  
**Fecha:** 30 Nov 2025  
**Estado:** ✅ Completado y Probado
