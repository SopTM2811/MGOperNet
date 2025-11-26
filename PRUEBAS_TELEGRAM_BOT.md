# Pruebas del Bot de Telegram - NetCash MBco

## Información del Bot
- **Nombre:** @Netcash_bot
- **Token configurado:** ✅ 8205886520:AAHuXw_66oeUQCL5Gzcfwy3WzzhHmBMXhE4

## Estado del Bot
- **Servicio:** `telegram_bot` (gestionado por supervisor)
- **Estado:** RUNNING
- **Logs:** `/var/log/telegram_bot.err.log` y `/var/log/telegram_bot.out.log`

---

## Prueba 1: Usuario nuevo (no registrado)

### Acción:
Usuario nuevo envía `/start` por primera vez

### Resultado Esperado:
1. Bot pide compartir teléfono con botón
2. Usuario comparte teléfono
3. Bot muestra menú con opciones:
   - 1️⃣ Registrarme como cliente NetCash
   - 2️⃣ Crear nueva operación NetCash
   - 3️⃣ Ver mis operaciones
   - ❓ Ayuda

### Flujo de Registro:
1. Usuario elige "1️⃣ Registrarme como cliente NetCash"
2. Bot toma nombre del perfil de Telegram
3. Bot pide teléfono (si no lo tiene) con formato: +52 33 xxxx xxxx
4. Bot pide email (opcional): "Escribe 'no' para saltar"
5. Bot crea cliente en la base de datos
6. Bot notifica a Ana (si ANA_TELEGRAM_CHAT_ID está configurado)
7. Bot confirma: "✅ ¡Listo! Ya te di de alta como cliente NetCash MBco..."

### Verificación en Dashboard:
- Cliente aparece en `/clientes`
- Badge "✈️ Telegram conectado" visible
- Estadística "Con Telegram" incrementada

---

## Prueba 2: Usuario nuevo intenta crear operación sin registro

### Acción:
Usuario NO registrado elige "2️⃣ Crear nueva operación NetCash"

### Resultado Esperado:
Bot responde:
```
⚠️ **Para crear una operación primero necesito darte de alta como cliente.**

Elige la opción **1️⃣ Registrarme como cliente NetCash**.

Usa /start para ver el menú.
```

### Verificación:
- ❌ NO se crea operación en la base de datos
- ✅ Usuario recibe mensaje de error claro

---

## Prueba 3: Usuario registrado crea operación

### Acción:
Usuario YA registrado envía `/start` y elige "Crear nueva operación NetCash"

### Resultado Esperado:
1. Bot NO vuelve a pedir datos de registro
2. Bot crea operación ligada al `cliente_id` correcto
3. Bot responde:
```
✅ **Creé tu operación NetCash**

**ID:** `[ID de operación]`

Ahora mándame el comprobante del depósito (PDF o imagen) para procesarlo.

**Recuerda:** El depósito debe ser a la cuenta:
JARDINERIA Y COMERCIO THABYETHA SA DE CV
CLABE: 646180139409481462
```

### Flujo de Comprobante:
1. Usuario envía archivo PDF o imagen
2. Bot responde: "🔍 Procesando comprobante..."
3. (Actualmente) Bot indica que use la web para subir comprobantes

### Verificación en Dashboard:
- Cliente correcto visible en `/clientes`
- Operación aparece en `/dashboard` ligada al cliente correcto
- Al subir comprobante vía web:
  - Comprobante ligado a la operación
  - OCR procesa y extrae monto, referencia, clave de rastreo
  - Datos visibles en detalle de operación

---

## Logs de Prueba Reales

### Log de inicio del bot:
```
2025-11-26 17:27:32,658 - Bot inicializado. Ana chat ID: None
2025-11-26 17:27:32,698 - Bot iniciado correctamente. Esperando mensajes...
2025-11-26 17:27:33,199 - Application started
2025-11-26 17:27:33,561 - /start recibido de DFGV (chat_id: 1570668456)
```

### Log de callback (usuario eligiendo opción):
```
2025-11-26 17:27:49,998 - answerCallbackQuery "HTTP/1.1 200 OK"
2025-11-26 17:27:50,254 - editMessageText "HTTP/1.1 200 OK"
```

---

## Configuración de Notificaciones a Ana

### Método: Telegram
Para habilitar notificaciones a Ana cuando se crea un cliente desde Telegram:

1. **Variable de entorno requerida:**
   ```bash
   ANA_TELEGRAM_CHAT_ID=<chat_id de Ana>
   ```

2. **Cómo obtener el chat_id de Ana:**
   - Ana debe enviar `/start` al bot
   - El bot registrará su `chat_id` en los logs
   - Copiar ese ID y agregarlo a `/app/backend/.env`

3. **Ubicación del archivo:**
   `/app/backend/.env`

4. **Reiniciar el bot después de configurar:**
   ```bash
   sudo supervisorctl restart telegram_bot
   ```

### Contenido de la notificación:
```
🆕 **Nuevo cliente creado desde Telegram**

**Nombre:** [Nombre del cliente]
**Teléfono:** [Teléfono completo]
**Email:** [Email o "No proporcionado"]
**Cliente ID:** `[UUID del cliente]`
**Fecha:** [YYYY-MM-DD HH:MM:SS] UTC
```

---

## Estado de Implementación

✅ **Completado:**
- Bot corriendo de forma estable con supervisor
- Alta de cliente con flujo conversacional (nombre, teléfono, email opcional)
- Validación: solo clientes registrados pueden crear operaciones
- Creación de operación ligada a cliente_id
- Notificación a Ana (funcional si ANA_TELEGRAM_CHAT_ID está configurado)
- Indicador de Telegram en dashboard de clientes

⚠️ **Pendiente (fase futura):**
- Procesamiento de comprobantes directamente desde Telegram
- Descarga y envío de archivo a la API de OCR

---

## Comandos Útiles

### Ver estado del bot:
```bash
sudo supervisorctl status telegram_bot
```

### Ver logs en tiempo real:
```bash
tail -f /var/log/telegram_bot.err.log
```

### Reiniciar el bot:
```bash
sudo supervisorctl restart telegram_bot
```

### Detener el bot:
```bash
sudo supervisorctl stop telegram_bot
```

### Iniciar el bot manualmente (para debugging):
```bash
cd /app/backend
/root/.venv/bin/python telegram_bot.py
```
