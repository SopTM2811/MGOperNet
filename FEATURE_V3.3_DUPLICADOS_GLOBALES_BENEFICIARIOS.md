# Feature V3.3: Duplicados Globales + Beneficiarios Frecuentes (hasta 3)

**Fecha:** 30 de Noviembre, 2025  
**Versión:** V3.3

## 🎯 Objetivos Implementados

### 1. Detección de Duplicados GLOBALES (entre operaciones)
Detectar si un comprobante (mismo hash SHA-256) ya fue usado en otra operación NetCash del **mismo cliente**.

### 2. Beneficiarios Frecuentes: Hasta 3 Sugerencias
Siempre mostrar hasta 3 beneficiarios frecuentes cuando haya historial suficiente (no solo 1).

---

## 🔧 Parte 1: Duplicados Globales

### Problema Anterior
- ✅ Detectaba duplicados dentro de la **misma operación** (V3.2)
- ❌ NO detectaba si el mismo comprobante se usaba en **operaciones diferentes**

### Solución Implementada

**Antes de validar un comprobante, se busca en TODAS las operaciones del cliente:**

```python
# Buscar en otras solicitudes del mismo cliente
otras_solicitudes = await db.solicitudes_netcash.find({
    "cliente_id": cliente_id,
    "id": {"$ne": solicitud_id},  # Excluir operación actual
    "estado": {"$in": ["lista_para_mbc", "en_proceso_mbc", "completada", "borrador"]},
    "comprobantes.archivo_hash": file_hash  # Buscar por hash
}).to_list(10)

if otras_solicitudes:
    # DUPLICADO GLOBAL detectado
    folio_original = otras_solicitudes[0].get("folio_mbco")
    return False, f"duplicado_global:{folio_original}"
```

---

### Flujo de Detección (3 Niveles)

**Nivel 1: Duplicado LOCAL** (misma operación)
- Se compara hash con comprobantes de la operación actual
- Tipo: `"local"`
- Mensaje: "Este archivo parece ser el mismo que otro que ya subiste en esta operación"

**Nivel 2: Duplicado GLOBAL** (entre operaciones del mismo cliente)
- Se busca hash en operaciones anteriores del cliente
- Tipo: `"global"`
- Mensaje: "Este comprobante ya fue utilizado en otra operación NetCash (folio NC-000011)"

**Nivel 3: Único** (no duplicado)
- Se valida normalmente con CLABE/beneficiario
- Se suma al total si es válido

---

### Estructura de Datos

#### Duplicado Global
```json
{
  "archivo_url": "/path/to/file.pdf",
  "nombre_archivo": "comprobante.pdf",
  "archivo_hash": "a63bd20d...",
  "es_valido": false,
  "es_duplicado": true,
  "tipo_duplicado": "global",
  "operacion_original": "NC-000011",
  "id_solicitud_original": "nc-1764489873731",
  "duplicado_de": "comprobante_original.pdf",
  "validacion_detalle": {
    "razon": "Comprobante ya utilizado en operación NC-000011"
  }
}
```

#### Duplicado Local (ya existía en V3.2)
```json
{
  "tipo_duplicado": "local",
  "duplicado_de": "archivo_en_esta_operacion.pdf",
  "validacion_detalle": {
    "razon": "Comprobante duplicado de 'archivo_en_esta_operacion.pdf' en esta operación"
  }
}
```

---

### Mensajes en Telegram

**Duplicado Global:**
```
⚠️ Comprobante ya utilizado anteriormente

Este comprobante ya fue utilizado en otra operación NetCash (folio NC-000011).

No lo vamos a contar de nuevo en el total de depósitos.

Llevamos 2 archivo(s) en total.

¿Quieres subir otro comprobante o continuar?
```

**Duplicado Local:**
```
⚠️ Comprobante duplicado detectado

Este archivo parece ser el mismo que otro que ya subiste en esta operación.
No lo vamos a contar de nuevo en el total de depósitos.

Llevamos 3 archivo(s) en total.

¿Quieres subir otro comprobante o continuar?
```

**Resumen Intermedio (con ambos tipos de duplicados):**
```
📊 Resumen de depósitos detectados:
  • comprobante1.pdf: $2,500.00
  • comprobante2.pdf: $5,000.00

💰 Total de depósitos detectados: $7,500.00

⚠️ Nota: 1 comprobante(s) duplicado(s) en esta operación y 2 ya utilizado(s) en otras operaciones NetCash no se incluyeron en el total.

Continuaremos con el siguiente paso...
```

---

### Testing Completado

**Script:** `/app/test_duplicados_globales.py`

**Escenario:**
1. Cliente crea Operación 1 → Sube comprobante A → Folio NC-000011
2. Cliente crea Operación 2 → Intenta subir el mismo comprobante A

**Resultado:**
```
✅ Duplicado GLOBAL detectado correctamente
   Folio original: NC-000011
✅ Estructura de datos correcta:
   tipo_duplicado: global
   operacion_original: NC-000011
   es_valido: False
```

**Caso Edge:** Comprobante diferente en Operación 2
- ✅ Se agrega y valida normalmente
- ✅ No se marca como duplicado

---

## 🔧 Parte 2: Beneficiarios Frecuentes (hasta 3)

### Problema Anterior
En pruebas recientes, el bot solo mostraba **1 beneficiario frecuente**, aunque el cliente tuviera más en su historial.

### Causa Root
La consulta buscaba solo en solicitudes con estado `lista_para_mbc`, limitando los resultados. Además, el límite de 5 solicitudes históricas podía no ser suficiente para obtener 3 beneficiarios únicos.

### Solución Implementada

**Cambios en la consulta:**

**Antes:**
```python
solicitudes_exitosas = await db.solicitudes_netcash.find({
    "cliente_id": cliente_id,
    "estado": "lista_para_mbc",  # Solo un estado
    ...
}).sort("created_at", -1).limit(5).to_list(5)  # Solo 5 solicitudes
```

**Después:**
```python
estados_validos = ["lista_para_mbc", "en_proceso_mbc", "completada"]

solicitudes_historicas = await db.solicitudes_netcash.find({
    "cliente_id": cliente_id,
    "estado": {"$in": estados_validos},  # Múltiples estados
    ...
}).sort("created_at", -1).limit(20).to_list(20)  # Más solicitudes para garantizar variedad
```

**Deduplicación y ordenamiento:**
```python
# Deduplicar manteniendo orden cronológico
beneficiarios_frecuentes = {}
for sol in solicitudes_historicas:
    benef = sol.get("beneficiario_reportado")
    idmex = sol.get("idmex_reportado")
    key = f"{benef}_{idmex}"
    
    if key not in beneficiarios_frecuentes:
        beneficiarios_frecuentes[key] = {
            "beneficiario": benef,
            "idmex": idmex,
            "created_at": sol.get("created_at")
        }

# Ordenar por fecha más reciente
frecuentes_list = list(beneficiarios_frecuentes.values())
frecuentes_list.sort(key=lambda x: x.get("created_at"), reverse=True)

# Tomar HASTA 3
frecuentes = frecuentes_list[:3]
```

---

### Comportamiento por Casos

| Historial del Cliente | Beneficiarios Mostrados | Comportamiento |
|-----------------------|-------------------------|----------------|
| 0 beneficiarios | 0 | Captura manual directa |
| 1 beneficiario | 1 | Muestra 1 botón |
| 2 beneficiarios | 2 | Muestra 2 botones |
| 3 beneficiarios | 3 | Muestra 3 botones |
| 5+ beneficiarios | 3 | Muestra los 3 más recientes |

---

### Ejemplo en Telegram

**Cliente con 3+ beneficiarios en historial:**
```
👤 Paso 2 de 3: Beneficiario + IDMEX

🔁 Beneficiarios frecuentes:

1. CARLOS MEDINA LÓPEZ – IDMEX: 2345788833
2. JUAN PÉREZ GARCÍA – IDMEX: 9876543210
3. MARÍA GONZÁLEZ TORRES – IDMEX: 1122334455

Puedes elegir uno de la lista o escribir un beneficiario nuevo.

[Botón: CARLOS MEDINA LÓPEZ... (IDMEX 2345788833)]
[Botón: JUAN PÉREZ GARCÍA... (IDMEX 9876543210)]
[Botón: MARÍA GONZÁLEZ TORRES... (IDMEX 1122334455)]
```

---

## 📁 Archivos Modificados

### Backend

**`/app/backend/netcash_service.py`**
- Nueva verificación de duplicados globales en `agregar_comprobante()`
- Búsqueda en otras solicitudes del mismo cliente antes de validar
- Estados válidos expandidos para búsqueda histórica

**`/app/backend/telegram_netcash_handlers.py`**
- Handler actualizado para diferenciar duplicados local vs global
- Mensajes específicos por tipo de duplicado
- Resumen intermedio con conteo separado de ambos tipos
- Consulta de beneficiarios frecuentes mejorada:
  - Estados válidos expandidos
  - Límite aumentado a 20 solicitudes
  - Ordenamiento por fecha más reciente
  - Deduplicación robusta

### Testing

**`/app/test_duplicados_globales.py`** (creado)
- Test end-to-end de duplicados entre operaciones
- Limpieza automática de datos de prueba
- Validación de estructura de datos en BD

### Documentación

**`/app/FEATURE_V3.3_DUPLICADOS_GLOBALES_BENEFICIARIOS.md`** (este archivo)

---

## ✅ Compatibilidad

### Con Versiones Anteriores

- ✅ V3.1 (Validador CLABE/beneficiario) - Sin cambios
- ✅ V3.2 (Duplicados locales) - Mantiene funcionalidad
- ✅ Flujo Telegram → BD → Web - Sin impacto

### Comprobantes Legacy

Comprobantes sin el campo `tipo_duplicado`:
- Se asumen como únicos
- La funcionalidad nueva solo aplica a comprobantes nuevos

---

## 🧪 Testing Ejecutado

### Test 1: Duplicados Globales

**Operación 1:**
- Crear operación
- Subir comprobante A
- Cambiar a estado `lista_para_mbc`
- Generar folio NC-000011

**Operación 2:**
- Crear nueva operación (mismo cliente)
- Intentar subir comprobante A (mismo hash)

**Resultado:**
```
✅ Duplicado GLOBAL detectado
✅ Referencia a folio NC-000011
✅ tipo_duplicado: "global"
✅ NO sumado al total
```

### Test 2: Beneficiarios Frecuentes

**Setup:**
- Cliente con 5 operaciones históricas
- 3 beneficiarios únicos diferentes

**Resultado:**
```
✅ 3 botones mostrados
✅ Beneficiarios ordenados por más reciente
✅ Sin duplicados
```

---

## 📊 Casos de Uso Cubiertos

### Caso A: Usuario intenta reutilizar comprobante
```
Usuario: [En NC-000012] Sube comprobante_marzo.pdf
Bot: ⚠️ Este comprobante ya fue utilizado en NC-000009
```

### Caso B: Usuario sube mismo archivo 2 veces en misma operación
```
Usuario: [En NC-000012] Sube factura.pdf
Usuario: [En NC-000012] Sube factura.pdf de nuevo
Bot: ⚠️ Comprobante duplicado en esta operación
```

### Caso C: Beneficiarios frecuentes
```
Usuario: Nueva operación
Bot: [Muestra 3 beneficiarios más recientes]
Usuario: [Selecciona uno con 1 clic]
```

---

## 🎯 Alcance

### ✅ Incluido en V3.3

**Duplicados:**
- Detección LOCAL (misma operación)
- Detección GLOBAL (entre operaciones del mismo cliente)
- Estados considerados: `lista_para_mbc`, `en_proceso_mbc`, `completada`, `borrador`

**Beneficiarios:**
- Hasta 3 sugerencias
- De operaciones válidas
- Ordenados por más reciente

### ❌ NO Incluido (Futuras Versiones)

**Duplicados:**
- Reutilización controlada (ej: después de 90 días)
- Detección cross-cliente (mismo comprobante, diferentes clientes)
- Índice en BD para búsqueda más rápida

**Beneficiarios:**
- Paginación (más de 3)
- Búsqueda/filtro por nombre
- Estadísticas de frecuencia de uso

---

## 📌 Mejoras Futuras Sugeridas

### 1. Índice en Base de Datos
Optimizar búsqueda de duplicados globales:
```javascript
db.solicitudes_netcash.createIndex({
  "cliente_id": 1,
  "comprobantes.archivo_hash": 1
})
```

### 2. Política de Reutilización Temporal
Permitir reutilizar después de X días:
```python
if dias_desde_uso > 90:
    # Permitir con advertencia
    requiere_confirmacion_manual = True
```

### 3. Caché de Beneficiarios Frecuentes
Evitar consultar BD en cada operación:
```python
# Cachear en Redis con TTL de 1 hora
beneficiarios_cache = redis.get(f"beneficiarios:{cliente_id}")
```

---

## 🎉 Resumen Ejecutivo

**Feature:** Duplicados Globales + Beneficiarios Frecuentes (hasta 3)  
**Versión:** V3.3  
**Estado:** ✅ IMPLEMENTADO Y TESTEADO

### Duplicados Globales
- ✅ Detecta comprobantes ya usados en otras operaciones del cliente
- ✅ Previene fraude/error de reutilización
- ✅ Mensajes claros con referencia al folio original
- ✅ No rompe detección local (V3.2)

### Beneficiarios Frecuentes
- ✅ Siempre muestra hasta 3 (no solo 1)
- ✅ Los más recientes tienen prioridad
- ✅ Mejora UX (menos escritura manual)
- ✅ Consulta optimizada (estados + límite)

**Testing:** 100% pasando
**Compatibilidad:** Total con V3.1 y V3.2
