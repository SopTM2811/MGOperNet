# Ejemplos de Correos Automáticos - Sistema NetCash

## Escenario 1: Cliente NO Identificado

**Situación**: El remitente no está registrado como cliente activo en el sistema.

**Email que recibiría el usuario**:

```
De: bbvanetcashbot@gmail.com
Para: [correo del remitente]
Asunto: NetCash – Registro necesario para usar este canal

Hola,

Recibimos tu correo, pero para poder operar con NetCash es necesario que primero estés dado de alta como cliente.

Por favor contacta a Ana para realizar tu registro:
• Correo: gestion.ngdl@gmail.com
• WhatsApp: +52 33 1218 6685

Una vez que Ana te confirme tu alta, podrás usar este correo y el asistente NetCash sin problema.

Equipo NetCash
```

**Acciones del sistema**:
- NO crea operación
- NO valida campos
- Etiqueta: `NETCASH/CLIENTE_NO_IDENTIFICADO`
- Marca correo como leído

---

## Escenario 2: Cliente Identificado - Correo Incompleto CON Adjunto

**Situación**: Cliente registrado envía correo con adjunto pero falta información (beneficiario, IDMEX, cantidad de ligas).

**Email original del cliente**:
```
De: cliente@ejemplo.com
Para: bbvanetcashbot@gmail.com
Asunto: NetCash - Operación urgente
Adjuntos: comprobante.pdf

Hola, te mando el comprobante de pago.
```

**Email de respuesta automática**:

```
De: bbvanetcashbot@gmail.com
Para: cliente@ejemplo.com
Asunto: NetCash – Hace falta información para tu operación

Hola,

Recibimos tu correo para operar con NetCash, pero todavía nos falta información para poder registrar correctamente la operación.

En tu próximo correo por favor incluye lo siguiente que nos falta:
• El nombre completo del beneficiario al que se aplicará el pago.
• El IDMEX o identificador de la operación que usas con MBco.
• La cantidad de ligas NetCash que necesitas para esta operación.

Si necesitas apoyo para completar la información, simplemente responde a este mismo correo escribiendo la palabra "AYUDA" y nuestro equipo se pondrá en contacto contigo.

Recuerda realizar tu depósito a la cuenta autorizada:
Banco: STP
CLABE: 646180139409481462
Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV

En cuanto tengamos la información completa, registramos la operación y te confirmamos por este mismo medio.

Quedamos al pendiente.

Equipo NetCash
```

**Acciones del sistema**:
- Descarga y guarda el adjunto en `/app/backend/uploads/email_attachments/`
- Crea operación parcial con estado `en_revision_por_mail`
- Registra: `gmail_thread_id`, `email_cliente`, adjuntos
- Etiqueta: `NETCASH/FALTA_INFO`
- Espera respuesta del cliente en el mismo thread

---

## Escenario 3: Cliente Responde en el Mismo Thread (Conversación Guiada)

**Situación**: Cliente responde al correo anterior proporcionando parte de la información faltante.

**Respuesta del cliente en el mismo thread**:
```
De: cliente@ejemplo.com
Para: bbvanetcashbot@gmail.com
Asunto: Re: NetCash – Hace falta información para tu operación

Beneficiario: JUAN PEREZ GARCIA
IDMEX: MX-2025-001
```

**Email de respuesta automática** (NOTA: Solo pide lo que AÚN falta):

```
De: bbvanetcashbot@gmail.com
Para: cliente@ejemplo.com
Asunto: NetCash – Hace falta información para tu operación

Hola,

Recibimos tu correo para operar con NetCash, pero todavía nos falta información para poder registrar correctamente la operación.

En tu próximo correo por favor incluye lo siguiente que nos falta:
• La cantidad de ligas NetCash que necesitas para esta operación.

Si necesitas apoyo para completar la información, simplemente responde a este mismo correo escribiendo la palabra "AYUDA" y nuestro equipo se pondrá en contacto contigo.

Recuerda realizar tu depósito a la cuenta autorizada:
Banco: STP
CLABE: 646180139409481462
Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV

En cuanto tengamos la información completa, registramos la operación y te confirmamos por este mismo medio.

Quedamos al pendiente.

Equipo NetCash
```

**Acciones del sistema**:
- Detecta que es el mismo thread
- Busca operación existente por `gmail_thread_id`
- Consolida información anterior + nueva
- Re-evalúa campos faltantes
- Actualiza operación en BD
- Solo pide lo que AÚN falta (en este caso: cantidad de ligas)

---

## Escenario 4: Cliente Completa la Información

**Situación**: Cliente envía la última información faltante.

**Respuesta final del cliente**:
```
De: cliente@ejemplo.com
Para: bbvanetcashbot@gmail.com
Asunto: Re: NetCash – Hace falta información para tu operación

Cantidad de ligas: 5
```

**Email de confirmación automática**:

```
De: bbvanetcashbot@gmail.com
Para: cliente@ejemplo.com
Asunto: NetCash – Operación registrada

Hola,

Recibimos tu correo y tus comprobantes.

Tu operación NetCash ha sido registrada con el código: NC-EMAIL-000001

Esta operación está en proceso de validación interna.
En caso de requerir información adicional, nos pondremos en contacto contigo.

Recuerda realizar tu depósito a la cuenta autorizada:
Banco: STP
CLABE: 646180139409481462
Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV

Gracias por usar NetCash.

Equipo NetCash
```

**Acciones del sistema**:
- Actualiza operación con la información completa
- Cambia estado a `en_revision_por_mail`
- Etiqueta: `NETCASH/PROCESADO`
- La operación queda lista para ser revisada por el equipo interno

---

## Escenario 5: Cliente Identificado - Correo Completo desde el Inicio

**Situación**: Cliente registrado envía toda la información necesaria en el primer correo.

**Email del cliente**:
```
De: cliente@ejemplo.com
Para: bbvanetcashbot@gmail.com
Asunto: NetCash - Pago urgente a proveedor
Adjuntos: comprobante_bancario.pdf, comprobante_2.jpg

Hola,

Les envío comprobantes para nueva operación NetCash.

Beneficiario: MARIA LOPEZ HERNANDEZ
IDMEX: MX-2025-002
Cantidad de ligas: 3
Monto: $50,000.00

Saludos
```

**Email de confirmación automática**:

```
De: bbvanetcashbot@gmail.com
Para: cliente@ejemplo.com
Asunto: NetCash – Operación registrada

Hola,

Recibimos tu correo y tus comprobantes.

Tu operación NetCash ha sido registrada con el código: NC-EMAIL-000002

Esta operación está en proceso de validación interna.
En caso de requerir información adicional, nos pondremos en contacto contigo.

Recuerda realizar tu depósito a la cuenta autorizada:
Banco: STP
CLABE: 646180139409481462
Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV

Gracias por usar NetCash.

Equipo NetCash
```

**Acciones del sistema**:
- Descarga ambos adjuntos
- Extrae toda la información del cuerpo
- Crea operación completa con estado `en_revision_por_mail`
- Etiqueta: `NETCASH/PROCESADO`
- Envía confirmación inmediata (en menos de 20 segundos)

---

## Escenario 6: Correo sin "NetCash" en el Asunto

**Situación**: Alguien envía un correo sin incluir "NetCash" en el asunto.

**Email del usuario**:
```
De: alguien@ejemplo.com
Para: bbvanetcashbot@gmail.com
Asunto: Necesito ayuda con un pago
Adjuntos: documento.pdf

Hola, necesito procesar un pago urgente...
```

**Email de respuesta automática**:

```
De: bbvanetcashbot@gmail.com
Para: alguien@ejemplo.com
Asunto: NetCash – Ajuste en el asunto de tu correo

Hola,

Recibimos tu correo, pero para poder procesar correctamente tu solicitud en NetCash es necesario que el asunto incluya la palabra "NetCash".

Por favor vuelve a enviar tu correo a esta misma dirección, asegurándote de que el asunto contenga "NetCash" (puede ir acompañado de la referencia que tú quieras).

Ejemplos:
• NetCash – Pago proveedor
• NetCash – Nómina semana 15

Una vez que recibamos tu correo con el asunto correcto, podremos continuar con el proceso.

Equipo NetCash
```

**Acciones del sistema**:
- NO crea operación
- NO valida campos
- Etiqueta: `NETCASH/ASUNTO_INCORRECTO`
- Marca correo como leído
- NO procesa adjuntos

---

## Notas Técnicas

### Validación de Cliente
**Colección**: `clientes`
**Campo de búsqueda**: `email`
**Condición**: `estado: "activo"`

Si no existe o el estado no es "activo" → Escenario 1 (Cliente no identificado)

### Registro de Adjuntos en BD
Los adjuntos se guardan en el campo `archivos_adjuntos` de la operación:
```json
{
  "archivos_adjuntos": [
    {
      "nombre_original": "comprobante.pdf",
      "nombre_guardado": "uuid_comprobante.pdf",
      "ruta": "/app/backend/uploads/email_attachments/uuid_comprobante.pdf",
      "mime_type": "application/pdf",
      "tamaño": 125643
    }
  ]
}
```

### Trazabilidad en Logs
Cada procesamiento genera logs detallados:
```
[EmailMonitor] 📧 Email de: cliente@ejemplo.com
[EmailMonitor] 📝 Asunto: NetCash - Operación urgente
[EmailMonitor] 📎 Adjuntos: 1
[EmailMonitor] ✅ Cliente identificado: Juan Perez (estado: activo)
[EmailMonitor] 📎 Procesando 1 adjuntos para mensaje 19abc123...
[EmailMonitor] ✅ Adjunto descargado: uuid_comprobante.pdf (125643 bytes) de cliente@ejemplo.com
[EmailMonitor] 📦 Total adjuntos guardados: 1 de 1 detectados
```

### Intervalo del Monitor
- **Configurado**: 20 segundos (`await asyncio.sleep(20)`)
- **Ubicación**: `/app/backend/email_monitor.py` línea 587
- **Sensación de inmediatez**: Usuario envía correo → máximo 20 segundos → recibe respuesta

### Cuenta de Depósito
La cuenta se obtiene SIEMPRE de:
- **Servicio**: `cuenta_deposito_service.obtener_cuenta_activa()`
- **Colección**: `config_cuenta_deposito_netcash`
- **Condición**: `activa: true`
- **NO hay fallback hardcoded**: Si no hay cuenta activa, muestra mensaje genérico

