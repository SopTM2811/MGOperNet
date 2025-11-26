# 🤖 Guía: Configurar el Bot de Telegram - Asistente NetCash MBco

## 📌 Información Importante

El bot de Telegram ya está **completamente programado** en el backend. Solo necesita el token para empezar a funcionar.

---

## ✅ Paso 1: Obtener el Token del Bot de Telegram

1. **Abre Telegram** en tu teléfono o computadora

2. **Busca a @BotFather** (es el bot oficial de Telegram para crear bots)

3. **Envía el comando:** `/newbot`
   - O si ya tienes un bot creado, usa: `/mybots` y selecciona tu bot

4. **Sigue las instrucciones:**
   - Te pedirá un **nombre** para tu bot (ejemplo: "Asistente NetCash MBco")
   - Te pedirá un **username** único que termine en "bot" (ejemplo: "netcash_mbco_bot")

5. **Copia el token** que te da BotFather
   - Se ve así: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890`
   - ⚠️ **IMPORTANTE:** Guarda este token en un lugar seguro. No lo compartas públicamente.

---

## ✅ Paso 2: Configurar el Token en el Entorno

**EN ESTE ENTORNO DE EMERGENT, NO HAY UNA INTERFAZ VISUAL DE "SETTINGS" PARA VARIABLES DE ENTORNO.**

La forma de configurar el token es editando directamente el archivo de configuración:

### Opción A: Usando el Editor Web de Emergent

1. En la interfaz de Emergent, busca el **explorador de archivos** del proyecto
2. Navega a: `/app/backend/.env`
3. Haz clic para editar el archivo
4. Busca la línea que dice:
   ```
   TELEGRAM_BOT_TOKEN=
   ```
5. Pega tu token después del `=`:
   ```
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890
   ```
6. **Guarda el archivo** (botón Save o Ctrl+S)

### Opción B: Si prefieres usar comandos (para usuarios avanzados)

Si tienes acceso a una terminal o consola en Emergent:

```bash
# Editar el archivo .env
nano /app/backend/.env

# O usar echo para agregar directamente:
echo "TELEGRAM_BOT_TOKEN=TU_TOKEN_AQUI" >> /app/backend/.env
```

---

## ✅ Paso 3: Reiniciar el Backend

**Después de agregar el token, DEBES reiniciar el backend para que cargue la nueva configuración.**

### Opción A: Usando la Interfaz de Emergent

1. Busca el botón **"Restart Services"** o similar en la interfaz
2. Selecciona **"Backend"** o **"All Services"**
3. Haz clic en **Restart**

### Opción B: Usando el terminal (si está disponible)

```bash
sudo supervisorctl restart backend
```

---

## ✅ Paso 4: Verificar que el Backend Reinició Correctamente

Para asegurarte de que no hay errores:

```bash
tail -n 30 /var/log/supervisor/backend.err.log
```

Deberías ver algo como:
```
INFO:     Application startup complete.
```

Si ves errores relacionados con el token, verifica que lo copiaste correctamente.

---

## ✅ Paso 5: Probar el Bot

1. **Abre Telegram**
2. **Busca tu bot** por el username que le diste (ejemplo: @netcash_mbco_bot)
3. **Haz clic en "Start"** o envía el comando: `/start`

### Respuesta Esperada:

El bot debería responder con un mensaje de bienvenida similar a:

```
Hola 😊

Para usar NetCash, recuerda que tus transferencias deben ir SIEMPRE a:

• Razón social: JARDINERIA Y COMERCIO THABYETHA SA DE CV
• Banco: STP
• CLABE: 646180139409481462

Cuando tengas tu comprobante de transferencia (PDF, foto o ZIP), mándamelo por aquí
y te ayudo a procesar tus ligas NetCash.
```

También verás botones interactivos:
- 📎 Nueva operación NetCash
- 📊 Ver mis operaciones
- ❓ Ayuda

---

## ✅ Paso 6: Iniciar el Bot de Telegram (Si No Inicia Automáticamente)

El bot está configurado para iniciarse automáticamente con el backend. Pero si por alguna razón no está corriendo, puedes iniciarlo manualmente:

### Verificar si el bot está corriendo:

```bash
ps aux | grep telegram_bot
```

### Iniciar el bot manualmente (en segundo plano):

```bash
cd /app/backend
nohup python telegram_bot.py > /var/log/telegram_bot.log 2>&1 &
```

### Ver logs del bot:

```bash
tail -f /var/log/telegram_bot.log
```

---

## 🔧 Comandos Disponibles en el Bot

Una vez que el bot esté funcionando, los usuarios pueden usar:

- `/start` - Iniciar conversación y ver opciones
- `/ayuda` - Obtener ayuda sobre cómo usar el bot

---

## 🚨 Solución de Problemas

### Problema: El bot no responde

**Posibles causas:**
1. El token no está configurado correctamente
2. El backend no se reinició después de agregar el token
3. El bot no se está ejecutando

**Soluciones:**
1. Verifica el archivo `.env`: `cat /app/backend/.env | grep TELEGRAM_BOT_TOKEN`
2. Reinicia el backend: `sudo supervisorctl restart backend`
3. Verifica los logs: `tail -n 50 /var/log/supervisor/backend.err.log`

### Problema: Error "Invalid token"

**Causa:** El token está mal copiado o es inválido

**Solución:**
1. Vuelve a @BotFather en Telegram
2. Usa `/mybots` → selecciona tu bot → "API Token"
3. Copia el token nuevamente (asegúrate de copiar TODO)
4. Reemplázalo en `/app/backend/.env`
5. Reinicia el backend

### Problema: El bot responde pero con errores

**Causa:** Puede haber problemas con la conexión a MongoDB o falta de permisos

**Solución:**
1. Verifica los logs: `tail -f /var/log/supervisor/backend.err.log`
2. Asegúrate de que MongoDB está corriendo: `sudo supervisorctl status`
3. Verifica que el archivo `.env` tenga todas las variables necesarias

---

## 📋 Checklist Final

- [ ] Token de Telegram obtenido de @BotFather
- [ ] Token agregado en `/app/backend/.env`
- [ ] Backend reiniciado
- [ ] Sin errores en los logs del backend
- [ ] Bot responde al comando `/start` en Telegram
- [ ] Botones interactivos funcionan

---

## 📞 Resumen de Configuración

**Archivo a editar:**
```
/app/backend/.env
```

**Línea a modificar:**
```env
TELEGRAM_BOT_TOKEN=TU_TOKEN_AQUI
```

**Comando para reiniciar:**
```bash
sudo supervisorctl restart backend
```

**Comando para probar:**
Enviar `/start` a tu bot en Telegram

---

## 🎯 Siguiente Paso

Una vez que el bot esté funcionando, los clientes podrán:
1. Iniciar una operación NetCash desde Telegram
2. Enviar comprobantes directamente al bot
3. Recibir actualizaciones del estado de sus operaciones
4. Consultar sus operaciones anteriores

**¡El bot está listo para usarse!** 🚀
