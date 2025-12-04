# Guía de Validación Manual P4A

## 🎯 Objetivo
Validar end-to-end el flujo completo de P4A: detección de respuesta de Tesorería, validación de comprobantes y envío automático a DNS.

---

## ✅ Pre-requisitos

### 1. Operación NetCash existente
Necesitas una operación que ya haya pasado por el flujo completo hasta "enviado_a_tesoreria":

```bash
# Verificar operaciones disponibles en MongoDB
mongosh $MONGO_URL --eval "
  use netcash_mbco;
  db.solicitudes_netcash.find(
    {estado: 'enviado_a_tesoreria'},
    {id: 1, folio_mbco: 1, monto_ligas: 1, comision_dns_calculada: 1}
  ).pretty()
"
```

Deberías ver algo como:
```javascript
{
  id: "nc-000123",
  folio_mbco: "23456-209-M-11",
  monto_ligas: 99000.00,
  comision_dns_calculada: 371.25
}
```

### 2. Email original enviado a Tesorería
Esta operación debe haber generado un correo a Tesorería con:
- Layout CSV adjunto
- Comprobantes del cliente adjuntos
- Thread ID guardado en la BD

Verificar:
```bash
mongosh $MONGO_URL --eval "
  use netcash_mbco;
  db.solicitudes_netcash.findOne(
    {id: 'nc-000123'},
    {email_thread_id: 1, correo_tesoreria_enviado: 1}
  )
"
```

Debe mostrar:
```javascript
{
  email_thread_id: "18c3a...",
  correo_tesoreria_enviado: true
}
```

### 3. Variables de entorno configuradas

Verificar archivo `/app/backend/.env`:
```bash
grep -E "NETCASH_DNS_EMAIL|NETCASH_INTERNAL_EMAIL|GMAIL" /app/backend/.env
```

Debe mostrar:
```
NETCASH_DNS_EMAIL=dns@proveedor.com
NETCASH_INTERNAL_EMAIL=netcash@mbco.mx
GMAIL_USER=tu-email@gmail.com
GMAIL_CREDENTIALS_PATH=...
```

### 4. Email monitor activo

Verificar que el scheduler está corriendo:
```bash
sudo supervisorctl status backend
```

El email monitor se ejecuta automáticamente cada N minutos (configurado en `scheduler_email_monitor.py`).

---

## 🧪 Escenario 1: Validación exitosa (Capital + Comisión + Concepto OK)

### Paso 1: Preparar comprobante de pago CORRECTO

Crea un PDF que contenga:
- **Capital**: Exactamente $99,000.00 (mismo que `monto_ligas` en BD)
- **Comisión**: Exactamente $371.25 (mismo que `comision_dns_calculada` en BD)
- **Concepto**: `23456x209xMx11` (folio_mbco con guiones reemplazados por "x")

Ejemplo de contenido del PDF:
```
MBco - Comprobante de Dispersión
================================

Folio: 23456x209xMx11

MOVIMIENTOS:
-----------
1. CAPITAL - AFFORDABLE MEDICAL SERVICES SC
   Concepto: 23456x209xMx11 CAPITAL
   Monto: $99,000.00

2. COMISION DNS - COMERCIALIZADORA UETACOP SA DE CV
   Concepto: 23456x209xMx11 COMISION
   Monto: $371.25

TOTAL: $99,371.25
```

### Paso 2: Responder el correo original

1. Busca en tu bandeja de Gmail el correo que el sistema envió a Tesorería
   - Asunto: `NetCash – Orden de dispersión 23456-209-M-11 – ...`
   
2. **Responder** (no crear correo nuevo, debe ser REPLY en el mismo hilo)

3. En la respuesta:
   - Adjuntar el PDF del comprobante
   - Opcionalmente escribir: "Adjunto comprobante de pago"
   - Enviar desde la cuenta de Tesorería configurada

### Paso 3: Esperar procesamiento automático

El email monitor se ejecuta cada N minutos. Para forzar procesamiento inmediato:

```bash
# Ver logs en tiempo real
tail -f /var/log/supervisor/backend.err.log | grep "\[EmailMonitor\]"
```

O puedes esperar el ciclo automático (máximo N minutos).

### Paso 4: Verificar logs del proceso

Buscar en logs:
```bash
grep "\[EmailMonitor-P4A\]" /var/log/supervisor/backend.err.log | tail -50
grep "\[ComprobantePago-P4A\]" /var/log/supervisor/backend.err.log | tail -30
grep "\[DNSEmail-P4A\]" /var/log/supervisor/backend.err.log | tail -20
```

Deberías ver:
```
[EmailMonitor-P4A] ========== INICIANDO PROCESAMIENTO P4A ==========
[EmailMonitor-P4A] Operación: nc-000123
[EmailMonitor-P4A] Descargando 1 adjunto(s)...
[EmailMonitor-P4A] ✅ Guardado: 23456x209xMx11_pago_proveedor_1.pdf
[EmailMonitor-P4A] ========== INICIANDO VALIDACIONES ==========
[ComprobantePago-P4A] Iniciando validación de comprobante: ...
[ComprobantePago-P4A] Capital en PDF: $99000.00
[ComprobantePago-P4A] Comisión en PDF: $371.25
[ComprobantePago-P4A] ✅ Capital OK (diferencia: $0.00)
[ComprobantePago-P4A] ✅ Comisión OK (diferencia: $0.00)
[ComprobantePago-P4A] ✅ Concepto OK
[ComprobantePago-P4A] 🎉 ✅ Todas las validaciones pasaron
[DNSEmail-P4A] Iniciando envío de correo a DNS
[DNSEmail-P4A] ✅ Correo enviado exitosamente a DNS
[EmailMonitor-P4A] ✅✅ PROCESO COMPLETADO EXITOSAMENTE ✅✅
```

### Paso 5: Verificar archivo guardado

```bash
ls -lh /app/backend/uploads/comprobantes_pago_proveedor/
```

Debe mostrar:
```
23456x209xMx11_pago_proveedor_1.pdf
```

### Paso 6: Verificar MongoDB

```bash
mongosh $MONGO_URL --eval "
  use netcash_mbco;
  db.solicitudes_netcash.findOne(
    {id: 'nc-000123'},
    {
      estado: 1,
      pagado_a_dns: 1,
      pagos_proveedor: 1,
      validacion_pagos_proveedor: 1
    }
  )
"
```

Debe mostrar:
```javascript
{
  estado: "correo_enviado_a_proveedor",
  pagado_a_dns: true,
  pagos_proveedor: {
    fecha_recepcion: "2024-12-02T...",
    correo_tesoreria: "tono@mbco.mx",
    comprobantes: ["23456x209xMx11_pago_proveedor_1.pdf"],
    capital_total_pdf: 99000.00,
    comision_total_pdf: 371.25
  },
  validacion_pagos_proveedor: {
    estado: "validado",
    fecha_validacion: "2024-12-02T...",
    datos_extraidos: { ... }
  }
}
```

### Paso 7: Verificar correo enviado a DNS

Revisar bandeja de entrada de `dns@proveedor.com` (o el email configurado).

Debe haber un correo:
- **De**: Sistema (tu email configurado)
- **Para**: dns@proveedor.com
- **CC**: netcash@mbco.mx
- **Asunto**: `NetCash – Pago a proveedor – nc-000123 / MBco 23456-209-M-11`
- **Cuerpo**: Contiene folio, cliente, IDMEX, montos
- **Adjuntos**: `23456x209xMx11_pago_proveedor_1.pdf`

---

## 🧪 Escenario 2: Error en capital

### Paso 1: Preparar comprobante con CAPITAL INCORRECTO

Modifica el PDF para que el capital sea diferente:
```
1. CAPITAL - AFFORDABLE MEDICAL SERVICES SC
   Concepto: 23456x209xMx11 CAPITAL
   Monto: $98,500.00  ❌ (esperado: $99,000.00)

2. COMISION DNS - COMERCIALIZADORA UETACOP SA DE CV
   Concepto: 23456x209xMx11 COMISION
   Monto: $371.25  ✅
```

### Paso 2: Responder el correo original (igual que antes)

### Paso 3: Verificar logs

Deberías ver:
```
[ComprobantePago-P4A] Capital en PDF: $98500.00
[ComprobantePago-P4A] ❌ Diferencia en capital: esperado $99,000.00, comprobante $98,500.00
[ComprobantePago-P4A] ✅ Comisión OK
[ComprobantePago-P4A] ✅ Concepto OK
[ComprobantePago-P4A] ❌ Validación falló con 1 error(es)
[EmailMonitor-P4A] ❌ Validaciones fallaron
[DNSEmail-P4A] Enviando respuesta de error a Tesorería
[DNSEmail-P4A] ✅ Respuesta de error enviada a Tesorería
```

### Paso 4: Verificar MongoDB

```bash
mongosh $MONGO_URL --eval "
  use netcash_mbco;
  db.solicitudes_netcash.findOne(
    {id: 'nc-000123'},
    {
      estado: 1,
      pagado_a_dns: 1,
      validacion_pagos_proveedor: 1
    }
  )
"
```

Debe mostrar:
```javascript
{
  estado: "enviado_a_tesoreria",  // ⬅️ NO AVANZÓ
  pagado_a_dns: false,  // o no existe
  validacion_pagos_proveedor: {
    estado: "error",
    errores: [
      "Diferencia en capital: esperado $99,000.00, comprobante $98,500.00 (diferencia: $500.00)"
    ],
    fecha_ultima_validacion: "2024-12-02T...",
    capital_total_pdf: 98500.00,
    comision_total_pdf: 371.25
  }
}
```

### Paso 5: Verificar que NO se envió correo a DNS

Revisar bandeja de `dns@proveedor.com` → NO debe haber nuevo correo.

### Paso 6: Verificar respuesta a Tesorería

Revisar la bandeja de Tesorería (la que envió el comprobante).

Debe haber recibido una **respuesta en el mismo hilo** con:
- **Asunto**: `Error en validación de comprobante – nc-000123 / MBco 23456-209-M-11`
- **Cuerpo**: Lista el error detectado:
  ```
  • Diferencia en capital: esperado $99,000.00, comprobante $98,500.00 (diferencia: $500.00)
  ```

---

## 🧪 Escenario 3: Error en comisión

Similar al Escenario 2, pero con comisión incorrecta:
```
1. CAPITAL: $99,000.00  ✅
2. COMISION: $350.00  ❌ (esperado: $371.25)
```

---

## 🧪 Escenario 4: Error en concepto

```
1. CAPITAL: $99,000.00  ✅
2. COMISION: $371.25  ✅
3. Concepto: 23456-209-M-11  ❌ (esperado: 23456x209xMx11)
```

Nota: El concepto debe usar "x" en lugar de guiones.

---

## 🧪 Escenario 5: Error combinado (capital + concepto)

```
1. CAPITAL: $98,500.00  ❌
2. COMISION: $371.25  ✅
3. Concepto: 23456-209-M-11  ❌
```

La respuesta a Tesorería debe listar AMBOS errores.

---

## 🔧 Troubleshooting

### El email monitor no detecta el correo

Verificar:
1. ¿El correo es una respuesta (REPLY) en el mismo hilo?
2. ¿El remitente está en la lista blanca de correos de Tesorería?
3. ¿El asunto contiene el folio MBco?

Ver logs:
```bash
grep "EmailMonitor.*thread" /var/log/supervisor/backend.err.log
```

### Error al parsear PDF

Ver logs:
```bash
grep "ComprobantePago-P4A.*Error" /var/log/supervisor/backend.err.log
```

Posibles causas:
- PDF es imagen escaneada sin OCR
- Formato de layout diferente al esperado

### No se envía correo a DNS

Ver logs:
```bash
grep "DNSEmail-P4A" /var/log/supervisor/backend.err.log
```

Verificar:
- Credenciales de Gmail configuradas
- Variable `NETCASH_DNS_EMAIL` correcta

---

## ✅ Checklist Final

Después de completar los 5 escenarios, verifica:

- [ ] Escenario 1 (OK): Correo a DNS enviado, estado = "correo_enviado_a_proveedor"
- [ ] Escenario 2 (Error capital): Respuesta a Tesorería, NO correo a DNS
- [ ] Escenario 3 (Error comisión): Respuesta a Tesorería, NO correo a DNS
- [ ] Escenario 4 (Error concepto): Respuesta a Tesorería, NO correo a DNS
- [ ] Escenario 5 (Errores múltiples): Respuesta lista ambos errores, NO correo a DNS
- [ ] Comprobantes guardados con nombre `{folio_concepto}_pago_proveedor_{N}.pdf`
- [ ] MongoDB actualizado correctamente en cada caso
- [ ] Logs claros con etiquetas `[EmailMonitor-P4A]`, `[ComprobantePago-P4A]`, `[DNSEmail-P4A]`

---

Una vez completada la validación manual, reportar resultados para proceder con los tests automatizados.
