# Feature: Detección de Comprobantes Duplicados

**Fecha:** 30 de Noviembre, 2025  
**Versión:** V3.2

## 🎯 Objetivo

Implementar detección de comprobantes duplicados dentro de la misma operación NetCash usando hash SHA-256 del contenido del archivo.

---

## 📋 Requerimientos Implementados

### Comportamiento Deseado

**Dentro de una misma operación NetCash:**

1. ✅ Cada archivo tiene un hash SHA-256 calculado del contenido binario
2. ✅ Antes de aceptar un comprobante, se compara su hash con los existentes
3. ✅ Si el hash ya existe:
   - No se suma al total de depósitos
   - Se marca como duplicado (`es_duplicado: True`, `es_valido: False`)
   - Se muestra mensaje en Telegram indicando el duplicado
4. ✅ Si el hash no existe:
   - Se procesa normalmente con el validador CLABE/beneficiario
   - Solo si pasa la validación se suma al total

---

## 🔧 Implementación Técnica

### 1. Cálculo de Hash SHA-256

**Archivo:** `/app/backend/netcash_service.py`

**Nueva función:**
```python
def _calcular_hash_archivo(self, archivo_url: str) -> str:
    """
    Calcula hash SHA-256 del contenido de un archivo.
    Lee en chunks de 8192 bytes para manejar archivos grandes.
    """
    import hashlib
    
    with open(archivo_url, 'rb') as f:
        file_hash = hashlib.sha256()
        while chunk := f.read(8192):
            file_hash.update(chunk)
        return file_hash.hexdigest()
```

**Ventajas:**
- ✅ Detecta archivos duplicados independientemente del nombre
- ✅ Eficiente para archivos grandes (lectura en chunks)
- ✅ Hash único por contenido (no por metadatos)

---

### 2. Verificación de Duplicados

**Función modificada:** `agregar_comprobante()`

**Flujo implementado:**

```python
async def agregar_comprobante(solicitud_id, archivo_url, nombre_archivo):
    # 1. Calcular hash del archivo
    file_hash = self._calcular_hash_archivo(archivo_url)
    
    # 2. Obtener comprobantes existentes
    solicitud = await db.find_one({"id": solicitud_id})
    comprobantes_existentes = solicitud.get("comprobantes", [])
    
    # 3. Buscar si el hash ya existe
    for comp in comprobantes_existentes:
        if comp.get("archivo_hash") == file_hash:
            # DUPLICADO DETECTADO
            # Guardar como duplicado sin validar
            comprobante_duplicado = {
                "archivo_url": archivo_url,
                "nombre_archivo": nombre_archivo,
                "archivo_hash": file_hash,
                "es_valido": False,
                "es_duplicado": True,
                "duplicado_de": comp.get("nombre_archivo"),
                "validacion_detalle": {
                    "razon": f"Comprobante duplicado de '{comp.get('nombre_archivo')}'"
                }
            }
            await db.update_one({"id": solicitud_id}, {"$push": {"comprobantes": comprobante_duplicado}})
            return False, "duplicado"
    
    # 4. No es duplicado, validar normalmente
    es_valido, razon = self.validador_comprobantes.validar_comprobante(...)
    
    # 5. Guardar con hash
    comprobante_detalle = {
        "archivo_hash": file_hash,  # Nuevo campo
        "es_duplicado": False,       # Nuevo campo
        "es_valido": es_valido,
        ...
    }
    
    return True, None
```

**Cambios en firma:**
- Antes: `return bool`
- Ahora: `return Tuple[bool, Optional[str]]`
  - `(True, None)`: Agregado exitosamente (único)
  - `(False, "duplicado")`: Duplicado detectado
  - `(False, "error")`: Error al agregar

---

### 3. Mensajes en Telegram

**Archivo:** `/app/backend/telegram_netcash_handlers.py`

**Mensaje para Comprobante Único:**
```
✅ Comprobante recibido.
Llevamos 3 comprobante(s) adjunto(s) a esta operación.

¿Quieres subir otro comprobante o continuar al siguiente paso?
```

**Mensaje para Comprobante Duplicado:**
```
⚠️ Comprobante duplicado detectado

Este archivo parece ser el mismo que otro que ya subiste en esta operación.
No lo vamos a contar de nuevo en el total de depósitos.

Llevamos 4 archivo(s) en total (3 únicos).

¿Quieres subir otro comprobante o continuar?
```

**Resumen Intermedio (con duplicados):**
```
✅ Comprobantes validados correctamente

📊 Resumen de depósitos detectados:
  • comprobante1.pdf: $2,500.00
  • comprobante2.pdf: $5,000.00
  • comprobante3.pdf: $4,695.00

💰 Total de depósitos detectados: $12,195.00

⚠️ Nota: 1 comprobante(s) duplicado(s) no se incluyeron en el total.

Continuaremos con el siguiente paso...
```

---

## 📊 Estructura de Datos en BD

### Comprobante Único (Válido)
```json
{
  "archivo_url": "/path/to/file.pdf",
  "nombre_archivo": "comprobante1.pdf",
  "archivo_hash": "a63bd20d0816fcc0c8c09e37a54ce2c2e01df57eb914788924c33fe70cb97d3a",
  "es_valido": true,
  "es_duplicado": false,
  "validacion_detalle": {
    "razon": "CLABE encontrada completa y coincide con la cuenta NetCash autorizada"
  },
  "monto_detectado": 2500.00
}
```

### Comprobante Duplicado
```json
{
  "archivo_url": "/path/to/file_copy.pdf",
  "nombre_archivo": "comprobante2_copia.pdf",
  "archivo_hash": "a63bd20d0816fcc0c8c09e37a54ce2c2e01df57eb914788924c33fe70cb97d3a",
  "es_valido": false,
  "es_duplicado": true,
  "duplicado_de": "comprobante1.pdf",
  "validacion_detalle": {
    "razon": "Comprobante duplicado de 'comprobante1.pdf'"
  },
  "monto_detectado": null
}
```

**Campos Nuevos:**
- `archivo_hash` (string): Hash SHA-256 del contenido
- `es_duplicado` (boolean): Indica si es duplicado
- `duplicado_de` (string, opcional): Nombre del archivo original

---

## 🧪 Testing Completado

### Script de Test
**Archivo:** `/app/test_duplicados_comprobantes.py`

### Casos Probados

**Caso 1: Agregar archivo único**
- ✅ Se calcula el hash
- ✅ Se valida contra cuenta NetCash
- ✅ Se guarda con `es_duplicado: False`
- ✅ Se suma al total si es válido

**Caso 2: Agregar archivo duplicado (mismo contenido, diferente nombre)**
- ✅ Se calcula el hash
- ✅ Se detecta que el hash ya existe
- ✅ Se guarda con `es_duplicado: True`, `es_valido: False`
- ✅ NO se suma al total
- ✅ Se registra el nombre del archivo original

**Caso 3: Agregar archivo diferente**
- ✅ Se calcula hash único
- ✅ Se valida normalmente
- ✅ Se suma al total si es válido

### Resultado del Test
```
================================================================================
RESUMEN DEL TEST:
================================================================================
✅ ¡TEST PASÓ! La detección de duplicados funciona correctamente
✅ 2 comprobante(s) único(s) agregado(s)
✅ 1 comprobante(s) duplicado(s) detectado(s)
```

---

## 🔐 Alcance de la Detección

### ✅ Incluido en esta Versión

**Duplicados dentro de la MISMA operación:**
- Si subes el mismo archivo 2 veces en la misma solicitud → Se detecta
- Si subes el mismo archivo con diferente nombre → Se detecta
- Si editas ligeramente el archivo (cambio de 1 byte) → Hash diferente, NO se detecta

### ❌ NO Incluido (Futuras Versiones)

**Duplicados entre operaciones diferentes:**
- Si usas el mismo comprobante en NC-000007 y NC-000008 → NO se detecta actualmente
- Requiere búsqueda histórica en toda la BD
- Se puede implementar más adelante con índice en `archivo_hash`

**Validaciones cruzadas:**
- Comprobante usado en diferentes fechas
- Comprobante usado por diferentes clientes
- Límites de reutilización

---

## 📁 Archivos Modificados

**Backend:**
- `/app/backend/netcash_service.py`
  - Nueva función `_calcular_hash_archivo()`
  - Función `agregar_comprobante()` modificada (firma y lógica)
  - Nuevos campos en estructura de comprobantes

- `/app/backend/telegram_netcash_handlers.py`
  - Handler de comprobantes actualizado para manejar duplicados
  - Mensajes diferenciados para únicos vs duplicados
  - Resumen intermedio con información de duplicados

**Testing:**
- `/app/test_duplicados_comprobantes.py` (creado)

**Documentación:**
- `/app/FEATURE_DETECCION_DUPLICADOS.md` (este archivo)

---

## ✅ Compatibilidad

### Código Existente
- ✅ Validador V3.1 (CLABE/beneficiario) NO modificado
- ✅ Flujo Telegram → BD → Web mantiene compatibilidad
- ✅ Comprobantes existentes en BD siguen funcionando

### Comprobantes Legacy
Los comprobantes guardados antes de esta feature NO tienen el campo `archivo_hash`. El código maneja esto:
- Si `archivo_hash` no existe → Se trata como único
- Solo comprobantes nuevos tienen hash para comparación

---

## 🎯 Casos de Uso Cubiertos

### Caso A: Usuario sube el mismo PDF dos veces por error
```
Usuario: [Sube comprobante1.pdf]
Bot: ✅ Comprobante recibido.

Usuario: [Sube comprobante1.pdf de nuevo]
Bot: ⚠️ Comprobante duplicado detectado
     No lo vamos a contar de nuevo en el total.
```

### Caso B: Usuario renombra el archivo y lo sube
```
Usuario: [Sube factura.pdf]
Bot: ✅ Comprobante recibido.

Usuario: [Renombra a factura_copia.pdf y lo sube]
Bot: ⚠️ Comprobante duplicado detectado
     Este archivo parece ser el mismo que 'factura.pdf'
```

### Caso C: Usuario sube 3 archivos únicos
```
Usuario: [Sube archivo1.pdf, archivo2.pdf, archivo3.pdf]
Bot: ✅ Comprobante recibido (3 veces)
     Llevamos 3 comprobante(s) adjunto(s)

Resumen:
  • archivo1.pdf: $2,500.00
  • archivo2.pdf: $5,000.00
  • archivo3.pdf: $4,695.00
  Total: $12,195.00
```

---

## 📌 Próximas Mejoras (Backlog)

### 1. Detección Histórica (Cross-Operation)
Detectar si un comprobante ya fue usado en otra operación:
```python
# Buscar en toda la colección
comprobantes_historicos = await db.solicitudes_netcash.find(
    {"comprobantes.archivo_hash": file_hash},
    {"id": 1, "folio_mbco": 1}
).to_list(10)

if comprobantes_historicos:
    return False, f"Ya usado en operación {folio}"
```

### 2. Índice en Base de Datos
Crear índice para búsquedas rápidas:
```javascript
db.solicitudes_netcash.createIndex({"comprobantes.archivo_hash": 1})
```

### 3. Política de Reutilización
Permitir reutilizar después de X días o con aprobación:
```python
if dias_desde_uso < 30:
    return False, "duplicado_reciente"
elif dias_desde_uso < 90:
    # Permitir con advertencia
    requiere_confirmacion = True
```

---

## 🎉 Resumen Ejecutivo

**Feature:** Detección de Comprobantes Duplicados  
**Alcance:** Dentro de la misma operación  
**Método:** Hash SHA-256 del contenido del archivo  

**Estado:** ✅ IMPLEMENTADO Y TESTEADO

**Resultado:**
- ✅ Previene contar el mismo depósito dos veces
- ✅ Detecta duplicados independientemente del nombre del archivo
- ✅ Mantiene compatibilidad con código existente
- ✅ UX clara en Telegram (mensajes diferenciados)

**Testing:** 100% pasando (archivos únicos, duplicados, diferentes)
