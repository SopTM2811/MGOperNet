# Ejemplos del Parser Mejorado - Email Monitor NetCash

## Reglas de Validación Implementadas

### 1. IDMEX Válido
**Regla**: Exactamente 10 dígitos
**Regex**: `^\[0-9\]{10}$`

✅ Válidos:
- `1234567890`
- `9876543210`

❌ Inválidos:
- `123456789` (solo 9 dígitos)
- `12345678901` (11 dígitos)
- `123-456-7890` (contiene guiones)
- `ABC1234567` (contiene letras)

### 2. Nombre de Beneficiario Válido
**Regla**: Mínimo 3 palabras (nombre + 2 apellidos)
**Validación**: Solo letras, espacios, acentos y ñ

✅ Válidos:
- `Daniel Torres Pérez`
- `María Elena Rodríguez`
- `José Luis García Hernández`

❌ Inválidos:
- `Daniel Torres` (solo 2 palabras)
- `Torres Pérez` (sin nombre claro)
- `Daniel` (solo 1 palabra)
- `Daniel Torres 123` (contiene números)

### 3. Cantidad de Ligas
**Regla**: Número entero >=1 asociado a keywords
**Keywords detectados**:
- `ligas`, `liga`
- `líneas de captura`, `lineas de captura`, `línea`, `linea`
- `lines de captura`, `line`

✅ Formatos válidos:
- `2 ligas`
- `ligas 3`
- `5 líneas de captura`
- `líneas de captura 4`
- `lines de captura 2`
- `3 line`

### 4. Comprobante Adjunto
**Regla**: Al menos 1 adjunto con mime-type válido
**Tipos aceptados**: PDF, JPG, PNG

---

## Ejemplos de Correos Procesados

### Ejemplo 1: Correo COMPLETO (Caso Ideal)

**Email del usuario**:
```
De: cliente@ejemplo.com
Para: bbvanetcashbot@gmail.com
Asunto: NetCash prueba bien
Adjuntos: comprobante.pdf

daniel torres perez
1234567899
lines de captura 2
```

**Procesamiento**:
1. ✅ Cliente identificado
2. ✅ Asunto contiene "NetCash"
3. ✅ Parser detecta:
   - Beneficiario: `daniel torres perez` (3 palabras, sin números)
   - IDMEX: `1234567899` (10 dígitos... ⚠️ ERROR: solo tiene 9)
   
**CORRECCIÓN NECESARIA**: Este correo tiene **9 dígitos**, no 10. El sistema debería detectarlo como **incompleto** y pedir el IDMEX correcto.

**Respuesta esperada**:
```
Asunto: Re: NetCash prueba bien

Hola,

Estamos dando seguimiento a tu correo con asunto: "NetCash prueba bien".

Recibimos tu correo para operar con NetCash, pero todavía nos falta información:

• El IDMEX de 10 dígitos (identificador de la operación que usas con MBco).

[...plantilla...]

Equipo NetCash
```

### Ejemplo 2: Correo COMPLETO (Correcto)

**Email del usuario**:
```
De: cliente@ejemplo.com
Para: bbvanetcashbot@gmail.com
Asunto: NetCash pago urgente
Adjuntos: comprobante.pdf

María Elena Rodríguez
9876543210
3 ligas
```

**Procesamiento**:
1. ✅ Cliente identificado
2. ✅ Asunto contiene "NetCash"
3. ✅ Adjunto: comprobante.pdf
4. ✅ Parser detecta:
   - Beneficiario: `María Elena Rodríguez` (3 palabras ✓)
   - IDMEX: `9876543210` (10 dígitos ✓)
   - Ligas: `3` (keyword "ligas" ✓)
5. ✅ Información COMPLETA

**Respuesta**:
```
Asunto: Re: NetCash pago urgente

Hola,

Estamos dando seguimiento a tu correo con asunto: "NetCash pago urgente".

Recibimos tu correo y tus comprobantes.

Tu operación NetCash ha sido registrada con el código: NC-EMAIL-000001

Esta operación está en proceso de validación interna.

[...cuenta de depósito activa...]

Gracias por usar NetCash.

Equipo NetCash
```

### Ejemplo 3: Correo con Orden Diferente

**Email del usuario**:
```
De: cliente@ejemplo.com
Para: bbvanetcashbot@gmail.com
Asunto: NetCash - Operación nómina
Adjuntos: comprobante1.pdf, comprobante2.jpg

Necesito 5 ligas NetCash
IDMEX: 4567891230
Beneficiario: Juan Carlos Pérez López
```

**Procesamiento**:
1. ✅ Cliente identificado
2. ✅ Asunto contiene "NetCash"
3. ✅ Adjuntos: 2 archivos
4. ✅ Parser detecta (tolerante al orden):
   - Ligas: `5` (detectado primero en el texto)
   - IDMEX: `4567891230` (10 dígitos ✓)
   - Beneficiario: `Juan Carlos Pérez López` (4 palabras ✓)
5. ✅ Información COMPLETA

**Respuesta**: Operación registrada

### Ejemplo 4: Correo Incompleto (Sin IDMEX)

**Email del usuario**:
```
De: cliente@ejemplo.com
Para: bbvanetcashbot@gmail.com
Asunto: NetCash ayuda
Adjuntos: comprobante.pdf

Ana María García Torres
2 líneas de captura
```

**Procesamiento**:
1. ✅ Cliente identificado
2. ✅ Asunto contiene "NetCash"
3. ✅ Adjunto: comprobante.pdf
4. ⚠️ Parser detecta:
   - Beneficiario: `Ana María García Torres` (4 palabras ✓)
   - Ligas: `2` ✓
   - IDMEX: ❌ NO detectado
5. ❌ Información INCOMPLETA (falta IDMEX)

**Respuesta**:
```
Asunto: Re: NetCash ayuda

Hola,

Estamos dando seguimiento a tu correo con asunto: "NetCash ayuda".

Recibimos tu correo para operar con NetCash, pero todavía nos falta información:

• El IDMEX de 10 dígitos (identificador de la operación que usas con MBco).

[...plantilla...]

Para ayudarte mejor, puedes responder usando esta plantilla:

Nombre del beneficiario (nombre y dos apellidos):
IDMEX (10 dígitos):
Cantidad de ligas NetCash:
(Adjunta los comprobantes en PDF, JPG o PNG)
────────────────────────────────

Equipo NetCash
```

### Ejemplo 5: No Cumple Mínimos (Sin Adjunto y Sin Info Completa)

**Email del usuario**:
```
De: cliente@ejemplo.com
Para: bbvanetcashbot@gmail.com
Asunto: NetCash consulta

Hola, necesito información sobre las operaciones.
```

**Procesamiento**:
1. ✅ Cliente identificado
2. ✅ Asunto contiene "NetCash"
3. ❌ NO hay adjuntos
4. ❌ NO se detecta IDMEX ni ligas
5. ❌ NO cumple mínimos para crear operación

**Respuesta**:
```
Asunto: Re: NetCash consulta

Hola,

Estamos dando seguimiento a tu correo con asunto: "NetCash consulta".

Para poder crear una operación NetCash necesitamos al menos:
• Un comprobante de pago adjunto (PDF, JPG o PNG)
O bien:
• IDMEX (10 dígitos) + Cantidad de ligas NetCash

[...cuenta de depósito...]

────────────────────────────────
Puedes responder usando esta plantilla:

Nombre del beneficiario (nombre y dos apellidos):
IDMEX (10 dígitos):
Cantidad de ligas NetCash:
(Adjunta los comprobantes en PDF, JPG o PNG)
────────────────────────────────

Quedamos al pendiente.

Equipo NetCash
```

**Importante**: NO se crea operación en este caso. Etiqueta: `NETCASH/INCOMPLETO_SIN_OPERACION`

### Ejemplo 6: Conversación Guiada (Thread Existente)

**Correo 1** (incompleto):
```
Asunto: NetCash operación
Adjuntos: comprobante.pdf

Pedro Ramírez González
2 ligas
```

**Respuesta 1**: Falta IDMEX (con plantilla)

**Correo 2** (cliente responde en el mismo thread):
```
Re: NetCash operación

IDMEX: 1122334455
```

**Procesamiento Correo 2**:
1. ✅ Detecta thread existente
2. ✅ Busca operación por `gmail_thread_id`
3. ✅ Consolida información:
   - Ya tenía: Adjunto, Beneficiario, Ligas
   - Nuevo: IDMEX `1122334455` (10 dígitos ✓)
4. ✅ Información ahora COMPLETA
5. ✅ Actualiza operación existente

**Respuesta 2**: Operación completada y registrada

---

## Condiciones para Crear Operación

### Condiciones Mínimas
Una operación se crea SOLO si cumple AL MENOS una de estas condiciones:

**Opción A**: 
- ✅ Tiene al menos 1 adjunto válido (PDF/JPG/PNG)

**Opción B**:
- ✅ Tiene IDMEX válido (10 dígitos) **Y**
- ✅ Tiene cantidad de ligas

### Estados de Operación

1. **`en_revision_por_mail`**: Operación completa, lista para revisión interna
   - Todos los campos validados correctamente
   - Adjunto + Beneficiario + IDMEX + Ligas

2. **`FALTA_INFO`** (etiqueta Gmail): Operación creada pero incompleta
   - Cumple mínimos para crear operación
   - Pero falta algún campo (ej: nombre o IDMEX)

3. **`INCOMPLETO_SIN_OPERACION`** (etiqueta Gmail): NO se crea operación
   - No cumple mínimos
   - Solo se envía guía al cliente

---

## Testing del Parser

### Comando de Testing Manual

```bash
# Test del parser con texto de ejemplo
python3 -c "
import sys
sys.path.insert(0, '/app/backend')
from email_monitor import EmailMonitor

monitor = EmailMonitor()

# Texto de prueba
texto = '''
daniel torres perez
1234567890
lines de captura 2
'''

info = monitor._extract_info_from_body_mejorado(texto)

print('Beneficiario:', info.get('beneficiario'))
print('IDMEX:', info.get('idmex'))
print('Ligas:', info.get('cantidad_ligas'))
print('IDMEX válido:', monitor._es_idmex_valido(info.get('idmex')))
print('Nombre válido:', monitor._es_nombre_valido(info.get('beneficiario')))
"
```

### Casos de Test Recomendados

1. **Test IDMEX**:
   - 10 dígitos: ✓
   - 9 dígitos: ✗
   - 11 dígitos: ✗
   - Con guiones: ✗

2. **Test Nombre**:
   - 3 palabras: ✓
   - 2 palabras: ✗
   - Con números: ✗

3. **Test Ligas**:
   - "2 ligas": ✓
   - "ligas 3": ✓
   - "lines de captura 5": ✓
   - Sin keyword: ✗

4. **Test Orden**:
   - Ligas, IDMEX, Nombre: ✓
   - Nombre, Ligas, IDMEX: ✓
   - IDMEX, Nombre, Ligas: ✓

---

## Logs del Parser

El parser genera logs detallados para debugging:

```
[Parser] IDMEX detectado: 1234567890
[Parser] Beneficiario detectado: Daniel Torres Pérez
[Parser] Ligas detectadas: 2
[EmailMonitor] Info completa: True
```

O en caso de campos inválidos:

```
[Parser] IDMEX detectado: 123456789
[EmailMonitor] Info completa: False
[EmailMonitor] Campos faltantes: ['idmex']
```
