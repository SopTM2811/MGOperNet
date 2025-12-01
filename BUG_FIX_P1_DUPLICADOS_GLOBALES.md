# 🐛 BUG FIX P1: Detección de Comprobantes Duplicados Globales

**Fecha:** 2024-12-01  
**Agente:** E1 (Fork Agent)  
**Prioridad:** P1 (Funcionalidad crítica - Integridad de datos)

---

## 📋 Resumen Ejecutivo

**BUG:** El sistema permitía usar el mismo comprobante (voucher) en múltiples operaciones diferentes del mismo cliente.

**Ejemplo reportado por usuario:**
- Operación 0022 y Operación 0023 aceptaron el mismo comprobante
- Esto permite "reciclar" comprobantes entre operaciones, comprometiendo la integridad

**CAUSA RAÍZ:** Faltaba el estado `"comprobantes_recibidos"` en la lista de estados que bloquean duplicados.

**SOLUCIÓN:** Añadir `"comprobantes_recibidos"` a la lista de estados que bloquean reutilización de comprobantes.

**ESTADO:** ✅ **CORREGIDO Y VERIFICADO**

---

## 🔍 Análisis del Problema

### ¿Cómo funciona la detección de duplicados?

El sistema usa **hash SHA-256** del contenido del archivo para detectar si el mismo comprobante se ha usado antes:

1. Cuando se sube un comprobante, se calcula su hash SHA-256
2. Se verifica si ese hash ya existe en:
   - **Duplicado LOCAL:** Misma operación (ya subido antes en esta misma solicitud)
   - **Duplicado GLOBAL:** Otras operaciones del mismo cliente

### La lógica de estados

El código busca duplicados solo en operaciones con ciertos estados "activos":

```python
# CÓDIGO ORIGINAL (con bug)
estados_que_bloquean_duplicados = [
    "lista_para_mbc",   # Operación lista para procesar
    "en_proceso_mbc",    # Operación en proceso
    "completada",        # Operación completada
    "borrador"           # Operación en borrador
]
```

**El problema:** Faltaba `"comprobantes_recibidos"`, que es el estado más común cuando los usuarios están subiendo comprobantes activamente.

### Escenario del bug:

1. Usuario crea **Operación A** (estado: `comprobantes_recibidos`)
2. Usuario sube `comprobante_X.pdf` → Se guarda con hash `abc123...`
3. Usuario crea **Operación B** (estado: `comprobantes_recibidos`)
4. Usuario sube el MISMO `comprobante_X.pdf`
5. Sistema busca hash `abc123...` en otras operaciones con estados bloqueantes
6. **Operación A NO está en la lista** (porque está en `comprobantes_recibidos`)
7. Sistema NO detecta el duplicado ❌
8. Comprobante se acepta en Operación B ❌

---

## ✅ La Solución

**Archivo:** `/app/backend/netcash_service.py`  
**Líneas:** 235-244

### Cambio aplicado:

```python
# DESPUÉS ✅ (con fix)
estados_que_bloquean_duplicados = [
    "comprobantes_recibidos",  # ⬅️ AGREGADO (fix principal)
    "lista_para_mbc",
    "en_proceso_mbc",
    "completada",
    "borrador"
]
```

### ¿Por qué este cambio soluciona el problema?

Ahora el sistema busca duplicados en operaciones que están:
- ✅ Recibiendo comprobantes activamente (`comprobantes_recibidos`)
- ✅ Listas para procesar (`lista_para_mbc`)
- ✅ En proceso (`en_proceso_mbc`)
- ✅ Completadas (`completada`)
- ✅ En borrador (`borrador`)

Estados que **NO** bloquean duplicados (permiten reutilizar):
- ✅ `rechazada` - Operación rechazada, se puede intentar de nuevo
- ✅ `cancelada` - Operación cancelada por el usuario
- ✅ `demo` - Operaciones de demostración

---

## 🧪 Verificación del Fix

### Test creado:

**Archivo:** `/app/backend/tests/test_deteccion_duplicados_globales.py`

El test simula exactamente el escenario reportado por el usuario:

1. **Crear Operación 0022** (estado: `comprobantes_recibidos`)
2. **Subir comprobante único** → Calcular hash SHA-256
3. **Guardar** comprobante en Operación 0022
4. **Crear Operación 0023** (estado: `comprobantes_recibidos`)
5. **Intentar subir EL MISMO comprobante**
6. **Verificar** que el sistema lo detecta como duplicado

### Resultados del test:

```
================================================================================
RESULTADOS DEL TEST
================================================================================
✅ CORRECTO: Sistema detectó el duplicado
   Razón: duplicado_global:0022
   Folio original detectado: 0022
   ✅ Folio correcto detectado

   Comprobante en operación 0023:
   - es_duplicado: True
   - tipo_duplicado: global
   - operacion_original: 0022
   ✅ Comprobante correctamente marcado como duplicado global

================================================================================
✅ TEST PASADO: Detección de duplicados funciona correctamente
================================================================================
```

### Prueba adicional - Diferentes estados:

El test también verifica que la detección funciona en todos los estados relevantes:

| Estado Original | Detecta Duplicado | Resultado |
|----------------|-------------------|-----------|
| `comprobantes_recibidos` | ✅ Sí | ✅ CORRECTO |
| `lista_para_mbc` | ✅ Sí | ✅ CORRECTO |
| `en_proceso_mbc` | ✅ Sí | ✅ CORRECTO |
| `completada` | ✅ Sí | ✅ CORRECTO |
| `rechazada` | ❌ No (permite reutilizar) | ✅ CORRECTO |
| `cancelada` | ❌ No (permite reutilizar) | ✅ CORRECTO |

---

## 📊 Impacto del Fix

### Antes del fix:
- ❌ Cliente puede "reciclar" comprobantes entre operaciones activas
- ❌ Compromete la integridad de los datos
- ❌ Puede inflar montos depositados artificialmente
- ❌ Dificulta la auditoría y conciliación

### Después del fix:
- ✅ Sistema detecta y bloquea duplicados entre operaciones activas
- ✅ Comprobante se marca como `duplicado_global`
- ✅ Cliente ve mensaje claro: "Este comprobante ya fue utilizado en operación X"
- ✅ Mantiene integridad de datos y facilita auditoría

---

## 💡 Comportamiento Esperado para el Usuario

### Escenario 1: Comprobante ya usado en operación activa

**Usuario:**
1. Crea Operación A
2. Sube `comprobante_500.pdf`
3. Crea Operación B
4. Intenta subir el mismo `comprobante_500.pdf`

**Sistema responde:**
```
⚠️ Comprobante ya utilizado anteriormente

Este comprobante ya fue utilizado en otra operación NetCash (folio 0022).

No lo vamos a contar de nuevo en el total de depósitos.

Llevamos 1 archivo(s) en total.

¿Quieres subir otro comprobante o continuar?
```

**En la BD:**
- `es_duplicado`: `true`
- `tipo_duplicado`: `"global"`
- `operacion_original`: `"0022"`
- `es_valido`: `false`

### Escenario 2: Comprobante de operación rechazada (PERMITIDO)

**Usuario:**
1. Crea Operación A, sube comprobante
2. Operación A es **rechazada** por alguna razón
3. Crea Operación B
4. Intenta subir el mismo comprobante

**Sistema responde:**
```
✅ Comprobante recibido.
Llevamos 1 comprobante(s) adjunto(s) a esta operación.
```

**Razón:** Las operaciones rechazadas o canceladas permiten reutilizar comprobantes.

---

## 📝 Archivos Modificados

### Código:
- **`/app/backend/netcash_service.py`**
  - Líneas: 235-244
  - Método: `agregar_comprobante()`
  - Cambio: Agregado `"comprobantes_recibidos"` a la lista de estados bloqueantes

### Tests:
- **`/app/backend/tests/test_deteccion_duplicados_globales.py`** (NUEVO)
  - Test completo de detección de duplicados
  - Verifica comportamiento en diferentes estados
  - Simula escenario exacto reportado por usuario

### Documentación:
- **`/app/BUG_FIX_P1_DUPLICADOS_GLOBALES.md`** (ESTE ARCHIVO)

---

## 🔑 Lecciones Aprendidas

1. **Cubrir todos los estados del ciclo de vida:**
   - No solo los estados "finales" (completada, en proceso)
   - También los estados "transicionales" (comprobantes_recibidos)

2. **Tests de integridad de datos son críticos:**
   - No es solo UX, afecta la integridad del sistema
   - Simular escenarios realistas de usuario

3. **Hash SHA-256 es robusto:**
   - Funciona correctamente para detectar archivos idénticos
   - Incluso si cambian el nombre del archivo

---

## ✅ Verificación en Producción

Para verificar que el fix funciona:

1. **Crear dos operaciones diferentes** (A y B)
2. **Subir un comprobante a la Operación A**
3. **Esperar confirmación** de que se recibió
4. **Intentar subir EL MISMO comprobante a la Operación B**
5. **Verificar que el sistema muestra:**
   ```
   ⚠️ Comprobante ya utilizado anteriormente
   Este comprobante ya fue utilizado en otra operación NetCash (folio XXXX).
   ```

---

## 🎉 Conclusión

El bug de duplicados globales ha sido **completamente corregido**. El sistema ahora detecta correctamente cuando el mismo comprobante (basado en hash SHA-256) se intenta usar en múltiples operaciones activas del mismo cliente.

La solución es simple pero efectiva: agregar el estado `"comprobantes_recibidos"` a la lista de estados que bloquean la reutilización de comprobantes. Esto asegura la integridad de los datos y previene el "reciclaje" de comprobantes entre operaciones.

**Estado:** ✅ **LISTO PARA PRODUCCIÓN**
