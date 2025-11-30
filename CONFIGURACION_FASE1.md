# 🚀 Asistente NetCash MBco - Configuración Fase 1

## ✅ Estado Actual

La **Fase 1** del Asistente NetCash MBco ha sido implementada exitosamente con las siguientes funcionalidades:

### Módulos Implementados

1. **✨ Módulo Cliente**
   - Recepción de comprobantes (PDF, imagen, ZIP)
   - OCR con OpenAI GPT-5.1 con visión
   - Validación de cuenta bancaria
   - Captura de datos del titular (nombre completo + IDMEX)
   - Número de ligas

2. **💰 Cálculos Financieros**
   - Capital NetCash (monto de ligas)
   - Comisión cobrada al cliente
   - Comisión pagada al proveedor
   - Total de egreso
   - Particionamiento automático de pagos

3. **📊 Dashboard Web**
   - Visualización de operaciones
   - Creación de nuevas operaciones
   - Vista detallada de cada operación
   - Estadísticas en tiempo real

4. **🤖 Preparación para Bot de Telegram**
   - Código base del bot implementado
   - Sistema de estados de operaciones
   - Mensajes automatizados

---

## 🔧 Configuración Necesaria

Para completar la configuración del sistema, necesitas proporcionar las siguientes credenciales:

### 1. Token del Bot de Telegram

El bot de Telegram está programado pero necesita tu token para funcionar.

**¿Cómo obtener el token?**

1. Abre Telegram y busca a **@BotFather**
2. Envía el comando `/newbot` (o usa un bot que ya hayas creado)
3. Sigue las instrucciones para crear tu bot
4. BotFather te dará un token que se ve así:
   ```
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890
   ```

**¿Dónde pegar el token?**

Abre el archivo `/app/backend/.env` y reemplaza la línea:

```env
TELEGRAM_BOT_TOKEN=
```

Por:

```env
TELEGRAM_BOT_TOKEN=TU_TOKEN_AQUI
```

**Ejemplo:**
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890
```

Después, reinicia el backend:
```bash
sudo supervisorctl restart backend
```

---

### 2. Credenciales de Correo (Gmail SMTP)

Para enviar correos a Ana, Toño, Claudia, etc., el sistema necesita acceso a una cuenta de Gmail.

**Opción Recomendada: App Password de Gmail**

1. Ve a tu cuenta de Google: https://myaccount.google.com/
2. Ve a "Seguridad" → "Verificación en dos pasos" (actívala si no está activa)
3. Ve a "Contraseñas de aplicaciones"
4. Genera una contraseña para "Correo" / "Otro (nombre personalizado)"
5. Copia la contraseña de 16 caracteres

**¿Dónde pegar las credenciales?**

Abre el archivo `/app/backend/.env` y completa:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_email@gmail.com
SMTP_PASSWORD=tu_password_de_app_aqui
```

**Ejemplo:**
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=gestion.netcash@gmail.com
SMTP_PASSWORD=abcd efgh ijkl mnop
```

Después, reinicia el backend:
```bash
sudo supervisorctl restart backend
```

---

## 📋 Verificación de la Configuración

### Verificar que el backend está corriendo:

```bash
tail -f /var/log/supervisor/backend.err.log
```

Deberías ver:
```
INFO:     Application startup complete.
```

### Verificar que el frontend está corriendo:

```bash
tail -f /var/log/supervisor/frontend.err.log
```

### Probar la aplicación web:

Abre tu navegador y ve a:
```
https://payment-validator-10.preview.emergentagent.com
```

---

## 🎯 Funcionalidades Disponibles

### En la Interfaz Web:

1. **Home Page**
   - Información general del sistema
   - Cuenta bancaria autorizada
   - Acceso al Dashboard

2. **Dashboard**
   - Ver todas las operaciones
   - Crear nueva operación
   - Buscar operaciones
   - Estadísticas en tiempo real

3. **Detalle de Operación**
   - Subir comprobantes (se procesan automáticamente con OCR)
   - Agregar datos del titular
   - Calcular montos
   - Confirmar operación
   - Visualizar todos los cálculos

### Bot de Telegram (una vez configurado):

1. Iniciar conversación con `/start`
2. Recibir información de la cuenta de depósito
3. Crear nueva operación
4. Ver mis operaciones
5. Ayuda

---

## 📊 Flujo de Trabajo Fase 1

```
1. Cliente/Operador crea operación
   ↓
2. Sube comprobante(s) de depósito
   ↓
3. Sistema procesa con OCR y valida cuenta
   ↓
4. Agrega datos del titular (nombre + IDMEX + # ligas)
   ↓
5. Sistema calcula:
      • Capital NetCash
      • Comisión cliente
      • Comisión proveedor
      • Total egreso
   ↓
6. Cliente/Operador confirma
   ↓
7. Sistema prepara información para Ana
   (Generación de código del sistema - próxima fase)
```

---

## 🗂️ Estructura de Archivos Importantes

```
/app/
├── backend/
│   ├── .env                    # ⚠️ CONFIGURAR AQUÍ: Tokens y credenciales
│   ├── server.py               # API principal
│   ├── models.py               # Modelos de datos
│   ├── config.py               # Configuración (cuentas bancarias, contactos)
│   ├── ocr_service.py          # Servicio de OCR con GPT-5.1
│   ├── calculos_service.py     # Servicio de cálculos financieros
│   └── telegram_bot.py         # Bot de Telegram
│
└── frontend/
    └── src/
        ├── pages/
        │   ├── Home.jsx
        │   ├── Dashboard.jsx
        │   └── OperacionDetalle.jsx
        └── components/
            └── NuevaOperacionModal.jsx
```

---

## 🔐 Cuentas Bancarias Configuradas

El sistema está pre-configurado con las cuentas reales de producción:

### Cuenta de Depósito (Clientes → MBco)
- **Razón social:** JARDINERIA Y COMERCIO THABYETHA SA DE CV
- **Banco:** STP
- **CLABE:** 646180139409481462

### Cuenta Capital (MBco → Proveedor)
- **Razón social:** AFFORDABLE MEDICAL SERVICES SC
- **Banco:** BBVA
- **CLABE:** 012680001255709482

### Cuenta Comisión Proveedor (MBco → Proveedor)
- **Razón social:** Comercializadora Uetacop SA de CV
- **Banco:** ASP
- **CLABE:** 058680000012912655

---

## 📞 Contactos Pre-configurados

Todos los contactos del sistema están guardados en `/app/backend/config.py`:

- **Ana** (Administradora): gestion.ngdl@gmail.com / +52 33 1218 6685
- **Toño** (Tesorería): Mbcose@gmail.com / +52 33 2536 2673
- **Javier** (Supervisor Tesorería): +52 33 3258 4721
- **Claudia** (Control): comprobanteenlace@gmail.com / +57 301 393 3477
- **Ximena** (Proveedor): dableaff@gmail.com / 4423475954
- Y más...

---

## 🚀 Próximos Pasos (Fase 2)

Una vez que confirmes que la Fase 1 funciona correctamente, podemos implementar:

1. **Integración completa de correos**
   - Envío automático a Ana para código de sistema
   - Layouts para Toño (Tesorería)
   - Instrucciones para proveedor (Ximena)

2. **Sistema de SLA y recordatorios**
   - Alertas si Ana tarda más de 5 minutos
   - Alertas si Toño tarda más de 10 minutos
   - Alertas si proveedor tarda más de 90 minutos

3. **Control con Claudia**
   - Reporte diario de operaciones
   - Validación de ejecución

4. **Reportes a Dirección**
   - Reporte diario a Samuel y Daniel
   - Acumulado mensual
   - Rankings por propietario

5. **Bot de Telegram completo**
   - Procesamiento de archivos directamente
   - Notificaciones en tiempo real
   - Integración con Make/Zapier

---

## ❓ Preguntas Frecuentes

### ¿Cómo pruebo el OCR?

1. Ve al Dashboard
2. Crea una nueva operación
3. Entra al detalle de la operación
4. Sube un comprobante de depósito
5. El sistema lo procesará automáticamente

### ¿Qué tipo de archivos acepta?

- PDFs
- Imágenes: JPG, JPEG, PNG, HEIC
- Archivos ZIP con PDFs o imágenes

### ¿Cómo sé si el comprobante es válido?

El sistema valida automáticamente:
- Que la cuenta beneficiaria coincida con la de MBco
- Que el nombre del beneficiario sea correcto
- Te mostrará un badge verde si es válido

### ¿Puedo cambiar las comisiones?

Sí, las comisiones se configuran por cliente. Por defecto:
- Comisión cliente: 0.65% (configurable por cliente)
- Comisión proveedor: 0.375% (fija)

---

## 📝 Notas Técnicas

### Base de Datos

- **Motor:** MongoDB
- **Base de datos:** netcash_mbco
- **Colecciones:** operaciones, clientes

### API Endpoints

- `GET /api/operaciones` - Listar operaciones
- `POST /api/operaciones` - Crear operación
- `POST /api/operaciones/{id}/comprobante` - Subir comprobante
- `POST /api/operaciones/{id}/titular` - Agregar datos titular
- `POST /api/operaciones/{id}/calcular` - Calcular montos
- `POST /api/operaciones/{id}/confirmar` - Confirmar operación

### Tecnologías Utilizadas

- **Backend:** FastAPI + Python 3.11
- **Frontend:** React 19 + Tailwind CSS + shadcn/ui
- **Base de datos:** MongoDB
- **OCR:** OpenAI GPT-5.1 (con Emergent LLM Key)
- **Bot:** python-telegram-bot

---

## 🆘 Soporte

Si tienes alguna duda o problema, puedes:

1. Revisar los logs del backend: `tail -f /var/log/supervisor/backend.err.log`
2. Revisar los logs del frontend: `tail -f /var/log/supervisor/frontend.err.log`
3. Contactar directamente

---

## ✅ Checklist de Configuración

- [ ] Token de Telegram agregado en `.env`
- [ ] Credenciales de Gmail agregadas en `.env`
- [ ] Backend reiniciado después de cambios
- [ ] Página web carga correctamente
- [ ] Puedo crear una operación nueva
- [ ] Puedo subir un comprobante
- [ ] El OCR procesa el comprobante
- [ ] Los cálculos funcionan correctamente

---

**¡La Fase 1 está completa y lista para usar!** 🎉

Una vez que proporciones el token de Telegram y las credenciales de correo, el sistema estará 100% operativo.
