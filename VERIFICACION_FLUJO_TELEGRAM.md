# Verificación del Flujo NetCash V1 en Telegram

## ✅ Problema Identificado y Resuelto

**Problema:** El bot de Telegram estaba corriendo con un proceso antiguo (PID 42 desde Nov29) que NO se reiniciaba con los cambios de código.

**Causa:** Existe un supervisor separado para el bot de Telegram (`telegram_bot`) que es diferente del supervisor del backend (`backend`).

**Solución:**
```bash
sudo supervisorctl restart telegram_bot
```

---

## 📋 Estado Actual del Sistema

### Servicios Corriendo
- ✅ **Backend:** RUNNING pid 629
- ✅ **Telegram Bot:** RUNNING pid 787 (reiniciado con código nuevo)
- ✅ **Frontend:** RUNNING

### Código Verificado
```python
# Verificación del método iniciar_crear_operacion:
✅ Código correcto: Paso 1 es Comprobantes
Línea 83: mensaje += "🧾 **Paso 1 de 3: Comprobantes de depósito**\n\n"
```

---

## 🧪 Pruebas Manuales a Realizar en Telegram

### **Prueba 1: Verificar Nuevo Orden del Flujo**
**Objetivo:** Confirmar que el flujo comienza con comprobantes.

**Pasos:**
1. Envía `/start` al bot de Telegram
2. Selecciona "🧾 Crear nueva operación NetCash"
3. **VERIFICAR:** El bot debe mostrar:
   ```
   🧾 Paso 1 de 3: Comprobantes de depósito
   
   Envíame uno o varios comprobantes de tus depósitos NetCash.
   Puedes adjuntar:
   • Varios archivos en un solo envío (álbum/selección múltiple)
   • O enviarlos en mensajes separados, uno tras otro
   
   Cuando termines de subir todos tus comprobantes, pulsa "➡️ Continuar".
   ```

**Resultado esperado:**
- ✅ El primer paso es COMPROBANTES, NO beneficiario
- ✅ Dice "Paso 1 de 3" (no "Paso 1 de 4")

---

### **Prueba 2: Fallar Rápido - Comprobante Inválido**
**Objetivo:** Verificar que el sistema no avanza si los comprobantes no son válidos.

**Pasos:**
1. Inicia nueva operación
2. En Paso 1, envía un comprobante que NO sea de la cuenta THABYETHA (cualquier otro PDF/imagen)
3. Presiona "➡️ Continuar"

**Resultado esperado:**
```
❌ Se recibieron 1 comprobante(s), pero ninguno coincide con la cuenta NetCash autorizada.

Detalle: ...

La cuenta NetCash autorizada es:
• Banco: STP
• CLABE: 646180139409481462
• Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV

Por favor envía comprobantes que correspondan a esta cuenta.
```
- ✅ El bot NO avanza al Paso 2
- ✅ Se mantiene en Paso 1 esperando comprobantes válidos

---

### **Prueba 3: Comprobante Válido + Beneficiarios Frecuentes**
**Objetivo:** Verificar el flujo completo con beneficiario frecuente.

**Pasos:**
1. Inicia nueva operación
2. **Paso 1:** Envía comprobante válido THABYETHA (CLABE 646180139409481462)
3. Bot muestra: "✅ Comprobante recibido. Llevamos 1 comprobante(s)..."
4. Presiona "➡️ Continuar"
5. **VERIFICAR Paso 2:** El bot debe mostrar:
   ```
   👤 Paso 2 de 3: Beneficiario + IDMEX
   
   🔁 Beneficiarios frecuentes:
   
   1. [Nombre] – IDMEX: [10 dígitos]
   2. ...
   
   Puedes elegir uno de la lista o escribir un beneficiario nuevo.
   ```
6. Si hay beneficiarios frecuentes, selecciona uno
7. Bot debe mostrar: "✅ Usaremos: [NOMBRE] – IDMEX [XXXXX]"
8. **VERIFICAR Paso 3:** Bot pide ligas directamente (sin pedir IDMEX manual)
9. Envía ligas: `3`
10. **VERIFICAR Paso 4 - Resumen:**
    ```
    📋 Esto es lo que entendí de tu operación NetCash:
    
    • Beneficiario: [NOMBRE] ✅
    • IDMEX: [XXXXX] ✅
    • Ligas NetCash: 3 ✅
    • Comprobantes: 1 archivo(s) (1 válido(s)) ✅
    
    ✅ ¡Todo en orden!
    ```
11. Presiona "✅ Confirmar y enviar a MBco"
12. **VERIFICAR:** Bot muestra folio NC-XXXXX

**Resultado esperado:**
- ✅ Flujo completo: Comprobantes → Beneficiario frecuente → Ligas → Resumen → Folio
- ✅ NO pide IDMEX manual al seleccionar beneficiario frecuente
- ✅ Resumen muestra "1 archivo(s) (1 válido(s)) ✅" sin contradicciones

---

### **Prueba 4: Múltiples Comprobantes**
**Objetivo:** Verificar que el bot maneja correctamente varios comprobantes.

**Pasos:**
1. Inicia nueva operación
2. **Paso 1:** Envía comprobante válido #1 → Bot: "Llevamos 1 comprobante(s)..."
3. Presiona "➕ Agregar otro comprobante"
4. Envía comprobante válido #2 → Bot: "Llevamos 2 comprobante(s)..."
5. Presiona "➕ Agregar otro comprobante"
6. Envía comprobante inválido #3 → Bot: "Llevamos 3 comprobante(s)..."
7. Presiona "➡️ Continuar"
8. Bot debe avanzar al Paso 2 (porque hay al menos 1 válido)
9. Completa flujo con beneficiario nuevo:
   - Nombre: `ANDRÉS MANUEL LÓPEZ OBRADOR`
   - IDMEX: `1234567890`
   - Ligas: `5`
10. **VERIFICAR Resumen:**
    ```
    • Comprobantes: 3 archivo(s) (2 válido(s)) ✅
    ```

**Resultado esperado:**
- ✅ Cada comprobante se cuenta correctamente
- ✅ El resumen muestra total y válidos: "3 archivo(s) (2 válido(s))"
- ✅ El bot avanza si hay >= 1 válido

---

### **Prueba 5: Beneficiario Nuevo (Sin Frecuentes)**
**Objetivo:** Verificar flujo de captura manual de beneficiario + IDMEX.

**Pasos:**
1. Inicia nueva operación
2. **Paso 1:** Envía comprobante válido → "➡️ Continuar"
3. **Paso 2:** Si NO hay frecuentes (o ignora los botones), escribe:
   ```
   ANDRÉS MANUEL LÓPEZ OBRADOR
   ```
4. Bot valida beneficiario
5. **VERIFICAR:** El ejemplo en los mensajes debe decir "ANDRÉS MANUEL LÓPEZ OBRADOR", NO "DANIEL FELIPE GALVEZ MAGALLON"
6. Bot pide IDMEX
7. Envía: `1234567890`
8. Bot valida IDMEX
9. **Paso 3:** Bot pide ligas
10. Envía: `2`
11. Verifica resumen y confirma

**Resultado esperado:**
- ✅ Los ejemplos usan "ANDRÉS MANUEL LÓPEZ OBRADOR"
- ✅ El flujo manual beneficiario → IDMEX funciona correctamente

---

## 🔧 Comandos Útiles para Debugging

### Reiniciar servicios
```bash
# Reiniciar bot de Telegram
sudo supervisorctl restart telegram_bot

# Reiniciar backend
sudo supervisorctl restart backend

# Verificar estado
sudo supervisorctl status
```

### Ver logs
```bash
# Logs del bot de Telegram
tail -f /var/log/telegram_bot.err.log

# Logs del backend
tail -f /var/log/supervisor/backend.err.log
```

### Verificar procesos
```bash
# Ver procesos de Telegram
ps aux | grep telegram

# Ver servicios de supervisor
sudo supervisorctl status
```

---

## 📝 Checklist de Verificación

### Antes de reportar como completado:
- [ ] Ejecuté `/start` → "Crear nueva operación NetCash" → **Primera pantalla muestra Paso 1: Comprobantes**
- [ ] Probé comprobante inválido → Bot **NO avanza** al Paso 2 (fallar rápido funciona)
- [ ] Probé comprobante válido → Bot **SÍ avanza** al Paso 2 (beneficiarios frecuentes)
- [ ] Beneficiarios frecuentes **SÍ aparecen** como botones con nombre + IDMEX
- [ ] Al seleccionar beneficiario frecuente → Bot **NO pide** IDMEX manual
- [ ] Resumen muestra "X archivo(s) (Y válido(s)) ✅" **SIN contradicciones**
- [ ] Múltiples comprobantes se cuentan correctamente
- [ ] Los ejemplos usan "ANDRÉS MANUEL LÓPEZ OBRADOR" (NO "DANIEL FELIPE...")

---

## ✅ Estado Actual

**Fecha:** 30 Nov 2025  
**Hora:** 00:20 UTC

**Servicios:**
- ✅ Backend: RUNNING (código actualizado)
- ✅ Telegram Bot: RUNNING (código actualizado, PID 787)

**Código:**
- ✅ `telegram_netcash_handlers.py`: Refactorizado con nuevo orden
- ✅ `telegram_bot.py`: ConversationHandler actualizado
- ✅ Paso 1: Comprobantes (verificado en código Python)
- ✅ Paso 2: Beneficiarios frecuentes (implementado)
- ✅ Paso 3: Ligas (ajustado)
- ✅ Paso 4: Resumen mejorado (3 casos de comprobantes)

**Pendiente:**
- ⏳ Pruebas manuales en Telegram por el usuario
- ⏳ Verificación de que el flujo real coincide con el código

---

**Nota:** El mismatch reportado por el usuario se debía a que el bot de Telegram NO se había reiniciado. Ahora con `sudo supervisorctl restart telegram_bot`, el código nuevo está activo.
