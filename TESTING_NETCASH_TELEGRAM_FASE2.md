# 🧪 TESTING NETCASH V1 - FASE 2: INTEGRACIÓN TELEGRAM

## 📋 Casos de Prueba Mínimos

### ✅ **CASO 1: Flujo Completo Válido**

**Objetivo:** Verificar que una solicitud NetCash con todos los datos correctos se procesa exitosamente.

**Prerrequisitos:**
- Usuario registrado como cliente activo en la BD
- Cuenta concertadora activa configurada (BANCO PRUEBA CTA / 234598762012345687)
- Comprobante de depósito a esa cuenta disponible

**Pasos:**
1. Enviar "Hola" al bot
2. **Verificar:** Bot responde con menú que incluye:
   - 🧾 Crear nueva operación NetCash
   - 💳 Ver cuenta para depósitos
   - 📂 Ver mis solicitudes

3. Seleccionar "🧾 Crear nueva operación NetCash"
4. **Verificar:** Bot muestra:
   - Cuenta concertadora (Banco, CLABE, Beneficiario)
   - Pide: "Paso 1 de 4: Nombre del beneficiario"

5. Enviar: `DANIEL FELIPE GALVEZ MAGALLON`
6. **Verificar:** Bot responde:
   - ✅ Beneficiario registrado
   - Pide: "Paso 2 de 4: IDMEX"

7. Enviar: `1234567890`
8. **Verificar:** Bot responde:
   - ✅ IDMEX registrado
   - Pide: "Paso 3 de 4: Cantidad de ligas"

9. Enviar: `3`
10. **Verificar:** Bot responde:
    - ✅ Cantidad de ligas: 3
    - Pide: "Paso 4 de 4: Comprobante de depósito"

11. Enviar comprobante PDF/imagen de BANCO PRUEBA CTA
12. **Verificar:** Bot responde con resumen:
    ```
    📋 Esto es lo que entendí de tu operación NetCash:
    • Beneficiario: DANIEL FELIPE GALVEZ MAGALLON ✅
    • IDMEX: 1234567890 ✅
    • Ligas NetCash: 3 ✅
    • Comprobante: 1 archivo(s) ✅
    
    ✅ ¡Todo en orden!
    
    [✅ Confirmar y enviar a MBco]
    [✏️ Corregir datos]
    ```

13. Presionar "✅ Confirmar y enviar a MBco"
14. **Verificar:** Bot responde:
    ```
    🎉 ¡Tu operación NetCash fue registrada correctamente!
    
    📋 Folio: NC-000001
    👤 Beneficiario: DANIEL FELIPE GALVEZ MAGALLON
    🆔 IDMEX: 1234567890
    🎫 Ligas NetCash: 3
    💵 Monto detectado: $10,000.00
    
    ✅ Estado: Lista para proceso interno MBco
    
    Te avisaremos cuando tus ligas NetCash estén listas. 🚀
    ```

**Verificación en BD:**
```bash
# Conectar a MongoDB y verificar
use netcash_mbco
db.solicitudes_netcash.find({folio_mbco: "NC-000001"}).pretty()

# Debe mostrar:
# - estado: "lista_para_mbc"
# - folio_mbco: "NC-000001"
# - validacion: todos los campos con valido: true
```

---

### ❌ **CASO 2: IDMEX Inválido (8 dígitos)**

**Objetivo:** Verificar que el motor rechaza IDMEX con longitud incorrecta.

**Pasos:**
1. Iniciar flujo como en CASO 1
2. En paso de IDMEX, enviar: `12345678` (solo 8 dígitos)
3. **Verificar:** Bot responde:
   ```
   ❌ IDMEX debe tener exactamente 10 dígitos. Recibido: 8
   
   Por favor envíame el IDMEX correcto (10 dígitos).
   
   Ejemplo: 1234567890
   ```
4. El bot **NO avanza** al siguiente paso
5. Enviar IDMEX correcto: `1234567890`
6. **Verificar:** Bot acepta y continúa al paso de ligas

**Logs esperados:**
```
[NetCash] Validación IDMEX: ❌ INVÁLIDO (longitud: 8, esperado: 10)
[NC Telegram] IDMEX rechazado, pidiendo de nuevo
```

---

### ❌ **CASO 3: Comprobante de Cuenta Incorrecta**

**Objetivo:** Verificar que el validador rechaza comprobantes de cuentas no autorizadas.

**Prerrequisitos:**
- Cuenta activa: BANCO PRUEBA CTA / 234598762012345687
- Comprobante de cuenta diferente (ej: THABYETHA STP / ...1462)

**Pasos:**
1. Iniciar flujo y completar pasos 1-3 correctamente
2. En paso de comprobante, enviar PDF/imagen de cuenta THABYETHA
3. **Verificar:** Bot muestra resumen con:
   ```
   📋 Esto es lo que entendí de tu operación NetCash:
   • Beneficiario: DANIEL FELIPE GALVEZ MAGALLON ✅
   • IDMEX: 1234567890 ✅
   • Ligas NetCash: 3 ✅
   • Comprobante: 1 archivo(s) ❌
   
   ⚠️ Problemas detectados:
   • comprobante: El comprobante no corresponde a la cuenta NetCash activa
   
   ❌ Hay errores que debes corregir.
   
   [✏️ Corregir datos]
   [❌ Cancelar]
   ```

4. **NO debe aparecer** el botón "✅ Confirmar y enviar a MBco"
5. Presionar "✏️ Corregir datos"
6. **Verificar:** Solicitud queda en estado "borrador" o "rechazada"

**Logs esperados:**
```
[ValidadorComprobantes] Cuenta ACTIVA esperada:
  - Banco: BANCO PRUEBA CTA
  - CLABE: 234598762012345687
[ValidadorComprobantes] CLABEs encontradas: ['646180115700001462']
[ValidadorComprobantes] ❌ INVÁLIDO: CLABE no coincide
[NC Telegram] Comprobante rechazado, mostrando en resumen
```

---

### ❌ **CASO 4: Nombre con 2 Palabras (Inválido)**

**Objetivo:** Verificar que el motor rechaza nombres sin apellido materno.

**Pasos:**
1. Iniciar flujo
2. En paso de beneficiario, enviar: `DANIEL GALVEZ` (solo 2 palabras)
3. **Verificar:** Bot responde:
   ```
   ❌ Beneficiario debe tener mínimo 3 palabras (nombre + 2 apellidos). Detectadas: 2
   
   Por favor envíame el nombre correcto.
   Recuerda: mínimo 3 palabras (nombre + dos apellidos), sin números.
   
   Ejemplo: DANIEL FELIPE GALVEZ MAGALLON
   ```
4. El bot **NO avanza** al paso de IDMEX
5. Enviar nombre correcto: `DANIEL FELIPE GALVEZ MAGALLON`
6. **Verificar:** Bot acepta y continúa

**Logs esperados:**
```
[NetCash] Validación beneficiario: ❌ INVÁLIDO (2 palabras, mínimo 3)
[NC Telegram] Beneficiario rechazado, pidiendo de nuevo
```

---

## 🔍 Verificación de Integración Motor-Bot

### **Puntos de Integración a Verificar:**

1. **Creación de solicitud:**
   ```python
   solicitud_data = SolicitudCreate(
       canal=CanalOrigen.TELEGRAM,
       cliente_id=cliente.get("id"),
       ...
   )
   solicitud = await netcash_service.crear_solicitud(solicitud_data)
   ```
   ✅ Verificar que se crea en estado "borrador"

2. **Actualización de campos:**
   ```python
   await netcash_service.actualizar_solicitud(
       solicitud_id,
       SolicitudUpdate(beneficiario_reportado=beneficiario)
   )
   ```
   ✅ Verificar que actualiza en BD

3. **Validación por campo:**
   ```python
   todas_validas, validaciones = await netcash_service.validar_solicitud_completa(solicitud_id)
   validacion_beneficiario = validaciones.get("beneficiario", {})
   ```
   ✅ Bot usa el resultado del motor, NO valida por su cuenta

4. **Agregación de comprobante:**
   ```python
   await netcash_service.agregar_comprobante(
       solicitud_id,
       str(file_path),
       nombre_archivo
   )
   ```
   ✅ Motor llama a validador_comprobantes_service

5. **Generación de resumen:**
   ```python
   resumen = await netcash_service.generar_resumen_cliente(solicitud_id)
   ```
   ✅ Bot muestra el resumen tal cual viene del motor

6. **Procesamiento final:**
   ```python
   exitoso, mensaje = await netcash_service.procesar_solicitud_automaticamente(solicitud_id)
   ```
   ✅ Motor decide si pasa a "lista_para_mbc" y genera folio

---

## 📊 Checklist de Integración

- [ ] Bot NO valida reglas de negocio (las delega al motor)
- [ ] Bot NO calcula nada (solo muestra lo que el motor devuelve)
- [ ] Bot NO genera folios (el motor los genera)
- [ ] Bot NO decide estados (el motor los cambia)
- [ ] Cuenta concertadora SIEMPRE se obtiene de `config_cuentas_service`
- [ ] Mensajes de error vienen del motor (`validaciones.get("campo").razon`)
- [ ] Resumen "Esto es lo que entendí" viene del motor (`generar_resumen_cliente`)

---

## 🚀 Comandos de Verificación Rápida

```bash
# Ver última solicitud creada
mongo netcash_mbco --eval 'db.solicitudes_netcash.find().sort({created_at:-1}).limit(1).pretty()'

# Ver cuenta concertadora activa
curl http://localhost:8001/api/netcash/cuentas/activa/concertadora | jq

# Ver logs del bot
tail -f /var/log/telegram_bot.log | grep -E "(NetCash|NC Telegram)"

# Ver logs del motor
tail -f /var/log/supervisor/backend.*.log | grep NetCash
```

---

## ✅ Criterios de Aceptación FASE 2

Para considerar la Fase 2 completada:

1. ✅ Flujo completo válido genera folio NC-XXXXXX
2. ✅ IDMEX inválido NO permite avanzar
3. ✅ Comprobante de cuenta incorrecta se rechaza con mensaje claro
4. ✅ Nombre con 2 palabras NO permite avanzar
5. ✅ Bot delega TODA lógica al motor (sin duplicación)
6. ✅ Mensajes amigables y consistentes
7. ✅ Cuenta concertadora NUNCA hardcodeada

**Estado:** ✅ LISTO PARA PRUEBAS
