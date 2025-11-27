# Configuración de Gmail API para NetCash

## 📋 Resumen

Este sistema usa Gmail API para:
- **Enviar correos** a clientes y Ana (notificaciones, confirmaciones)
- **Leer correos entrantes** de clientes (solicitudes NetCash)

## 🔧 Configuración Paso a Paso

### 1. Instalar dependencias de Google

```bash
cd /app/backend
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
pip freeze > requirements.txt
```

### 2. Obtener credenciales OAuth (credentials.json)

#### Opción A: Ya tienes el archivo
1. Coloca `credentials.json` en: `/app/backend/config/gmail_credentials.json`

#### Opción B: Crear nuevo proyecto en Google Cloud
1. Ve a: https://console.cloud.google.com/
2. Crea nuevo proyecto: "NetCash Email"
3. Habilita Gmail API
4. Crea credenciales OAuth 2.0 (tipo: Desktop app)
5. Descarga JSON y renómbralo a `gmail_credentials.json`
6. Coloca en: `/app/backend/config/gmail_credentials.json`

### 3. Scopes configurados

```python
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',      # Enviar correos
    'https://www.googleapis.com/auth/gmail.readonly'   # Leer correos
]
```

### 4. Primera autenticación (generar token.json)

**Ejecutar UNA SOLA VEZ:**

```python
from gmail_service import gmail_service

# Esto abrirá navegador para autorizar
gmail_service.oauth_flow()

# Se genera: /app/backend/config/gmail_token.json
```

**IMPORTANTE:**
- Usa la cuenta de Gmail que quieres para NetCash (ej: mbco.netcash@gmail.com)
- El token.json se refresca automáticamente
- Guarda token.json de forma segura (contiene access token)

## 🧪 Pruebas

### 1. Verificar estado de configuración

```bash
curl http://localhost:8001/api/gmail/status
```

**Respuesta esperada:**
```json
{
  "credentials_existe": true,
  "token_existe": true,
  "servicio_inicializado": true,
  "ruta_credentials": "/app/backend/config/gmail_credentials.json",
  "ruta_token": "/app/backend/config/gmail_token.json"
}
```

### 2. Enviar correo de prueba

```bash
curl -X POST "http://localhost:8001/api/gmail/enviar-prueba" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "destinatario=tu_email@ejemplo.com&asunto=Prueba NetCash&cuerpo=Hola desde NetCash"
```

### 3. Listar correos pendientes

```bash
curl http://localhost:8001/api/gmail/correos-pendientes?etiqueta=NETCASH_INBOX
```

## 📧 Uso en código

### Enviar correo

```python
from gmail_service import gmail_service

exito = gmail_service.enviar_correo(
    destinatario="cliente@ejemplo.com",
    asunto="Tu operación NetCash está lista",
    cuerpo_html="<h1>Hola</h1><p>Tu operación NC-000015...</p>",
    adjuntos=[
        {
            'filename': 'comprobante.pdf',
            'content': archivo_bytes
        }
    ],
    cc=["ana@mbco.com"]
)
```

### Leer correos pendientes

```python
from gmail_service import gmail_service

correos = gmail_service.leer_correos_pendientes(
    etiqueta="NETCASH_INBOX",
    max_resultados=10
)

for correo in correos:
    print(f"De: {correo['remitente']}")
    print(f"Asunto: {correo['asunto']}")
    print(f"ID: {correo['id']}")
    
    # Procesar...
    
    # Marcar como procesado
    gmail_service.marcar_como_procesado(correo['id'])
```

## 🏷️ Etiquetas de Gmail

Crear estas etiquetas en la cuenta de Gmail:

1. **NETCASH_INBOX** - Correos entrantes sin procesar
2. **NETCASH_PROCESADO** - Correos ya procesados
3. **NETCASH_ERROR** - Correos con error de procesamiento

**Configurar filtro automático:**
- Todos los correos a `netcash@mbco.com` → aplicar etiqueta NETCASH_INBOX

## ⚠️ Troubleshooting

### Error: "No se encontró credentials.json"
- Verifica ruta: `/app/backend/config/gmail_credentials.json`
- Asegúrate que el archivo existe

### Error: "Token expirado"
- El sistema auto-refresca el token
- Si falla, elimina token.json y ejecuta oauth_flow() de nuevo

### Error: "Quota exceeded"
- Gmail API tiene límites:
  - 1,000,000,000 quota units/día
  - ~100 correos/segundo
- Para producción, solicita aumento de cuota en Google Cloud

## 📝 Variables de entorno

Agregar en `/app/backend/.env`:

```bash
# Gmail (la cuenta se configura en OAuth, no aquí)
GMAIL_ENABLED=true

# Email de Ana para notificaciones
ANA_EMAIL=gestion.ngdl@gmail.com

# Chat ID de Ana en Telegram
ANA_TELEGRAM_CHAT_ID=1720830607
```

## 🚀 Integración con notificaciones

Una vez configurado Gmail, el sistema automáticamente:
- ✅ Envía correo a Ana cuando operación necesita clave MBControl
- ✅ Responde a clientes cuando falta información
- ✅ Confirma operaciones creadas por correo
- ✅ Lee y procesa solicitudes entrantes

## 📊 Monitoreo

Ver logs de Gmail API:

```bash
tail -f /var/log/supervisor/backend.err.log | grep -i gmail
```

## 🔒 Seguridad

- ✅ OAuth 2.0 (más seguro que contraseña de aplicación)
- ✅ Token cifrado en token.json
- ✅ Scopes mínimos necesarios (readonly + send)
- ❌ NUNCA commitear credentials.json o token.json a Git
- ✅ Agregar a .gitignore: `config/gmail_*.json`
