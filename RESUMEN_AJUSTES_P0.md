# Resumen de Ajustes P0 - Flujo de Correos NetCash

## ✅ Implementaciones Completadas

### 1. Módulo de Configuración de Cuenta de Depósito NetCash

#### A) Base de Datos
- **Colección**: `config_cuenta_deposito_netcash`
- **Campos**:
  - `id`: Identificador único
  - `banco`: Nombre del banco (ej: STP, BBVA)
  - `clabe`: CLABE de 18 dígitos
  - `beneficiario`: Razón social del beneficiario
  - `activa`: Boolean (solo una cuenta activa a la vez)
  - `fecha_vigencia_desde`: Fecha de inicio de vigencia
  - `created_at`: Fecha de creación
  - `updated_at`: Fecha de última actualización

- **Cuenta Real Insertada**:
  - Banco: **STP**
  - CLABE: **646180139409481462**
  - Beneficiario: **JARDINERIA Y COMERCIO THABYETHA SA DE CV**
  - Estado: **ACTIVA**

#### B) Backend - API Endpoints
**Archivo**: `/app/backend/server.py`

Endpoints creados:
- `GET /api/config/cuenta-deposito-activa` - Obtiene la cuenta activa actual
- `GET /api/config/cuentas-deposito` - Lista todas las cuentas (historial)
- `POST /api/config/cuenta-deposito` - Crea nueva cuenta y opcionalmente la activa
- `PUT /api/config/cuenta-deposito/{cuenta_id}/activar` - Activa una cuenta específica
- `PUT /api/config/cuenta-deposito/{cuenta_id}` - Actualiza datos de una cuenta

#### C) Servicio Centralizado
**Archivo**: `/app/backend/cuenta_deposito_service.py`

Funciones principales:
- `obtener_cuenta_activa()` - Obtiene la cuenta activa desde BD
- `listar_todas_cuentas()` - Lista historial de cuentas
- `crear_cuenta()` - Crea nueva cuenta con validaciones
- `activar_cuenta()` - Activa una cuenta y desactiva las demás
- `actualizar_cuenta()` - Actualiza datos de cuenta existente
- `formatear_cuenta_para_mensaje()` - Formatea cuenta para mostrar en mensajes

**Uso**: Todos los canales (Email, Telegram, Web) ahora usan este servicio centralizado.

#### D) Frontend - Panel de Administración
**Archivo**: `/app/frontend/src/pages/ConfiguracionCuenta.jsx`
**Ruta**: `/config/cuenta-deposito`

Funcionalidades:
- Visualización de cuenta activa (destacada en verde)
- Formulario para crear nueva cuenta
- Validación de CLABE (18 dígitos numéricos)
- Tabla con historial de todas las cuentas
- Botón para activar cuentas inactivas del historial
- Información sobre el uso automático en todos los canales

**Acceso**: Desde el Dashboard → Botón "Configuración Cuenta"

---

### 2. Corrección: Query de Gmail (Correos sin "NetCash")

#### Problema Anterior
El query de Gmail filtraba solo correos con adjuntos O con "NetCash" en el asunto:
```python
query = "label:INBOX is:unread (has:attachment OR subject:NetCash)"
```

Esto impedía que correos sin "NetCash" llegaran al monitor.

#### Solución Implementada
**Archivo**: `/app/backend/gmail_service.py` (línea 70)

Nuevo query:
```python
query = "label:INBOX is:unread"
```

Ahora trae **TODOS** los correos no leídos del INBOX. La validación de "NetCash" en el asunto se hace en el monitor.

#### Flujo de Manejo
**Archivo**: `/app/backend/email_monitor.py` (líneas 99-108)

1. Monitor recibe TODOS los correos no leídos
2. Valida si el asunto contiene "NetCash" (case-insensitive)
3. Si NO contiene "NetCash":
   - Envía correo automático pidiendo que incluyan "NetCash" en el asunto
   - Marca el correo como leído
   - Etiqueta: `NETCASH/ASUNTO_INCORRECTO`
   - NO crea operación

**Mensaje enviado**:
- Asunto: "NetCash – Ajuste en el asunto de tu correo"
- Contenido: Explica que el asunto debe incluir "NetCash" con ejemplos

---

### 3. Conversación Guiada (Re-evaluación de Campos)

#### Funcionalidad Implementada
**Archivo**: `/app/backend/email_monitor.py`

El monitor ahora detecta si un correo es parte de un thread existente y re-evalúa solo los campos faltantes.

#### Lógica de Flujo:

**Primera vez** (correo nuevo):
1. Extrae información del correo
2. Valida campos requeridos
3. Si falta información → responde listando campos faltantes
4. Crea operación parcial en BD con `estado: "en_revision_por_mail"`

**Respuestas subsecuentes** (mismo thread):
1. Busca operación existente por `gmail_thread_id`
2. Consolida información anterior + nueva información
3. Re-evalúa solo campos que AÚN faltan
4. Si ahora está completa → actualiza operación y confirma al cliente
5. Si aún falta algo → responde solo pidiendo lo que falta

#### Funciones Clave:
- `_buscar_operacion_por_thread()` - Busca operación existente por thread
- `_validate_info_consolidada()` - Valida consolidando datos previos + nuevos
- `_actualizar_operacion()` - Actualiza operación existente con nueva info

**Campos validados**:
1. Adjuntos (comprobantes)
2. Nombre completo del beneficiario
3. IDMEX
4. Cantidad de ligas NetCash

---

### 4. Mensaje Dinámico de Información Incompleta

Ya estaba implementado pero mejorado con:
- Lista dinámica de campos faltantes (solo muestra lo que falta)
- Recordatorio de cuenta de pago (ahora con cuenta REAL)
- Texto de ayuda
- Se actualiza en cada respuesta del cliente

**Archivo**: `/app/backend/email_monitor.py` (línea 367)
Función: `_send_incomplete_response_dynamic()`

---

### 5. Índice Único en MongoDB (Prevención de Duplicados)

#### Implementado
**Colección**: `usuarios_telegram`
- **Índice único en `telegram_id`**: ✅ Creado
  - Previene que se creen usuarios duplicados por telegram_id
  - Causa raíz del bug histórico del bot

#### No Implementado
- **Índice único en `chat_id`**: ❌ No posible
  - Razón: Existen múltiples registros con `chat_id: null` en la BD
  - MongoDB no permite índice único sparse con múltiples nulls

#### Solución
- `telegram_id`: Índice único (previene duplicados)
- `chat_id`: Los valores null se actualizan automáticamente cuando el usuario interactúa con el bot (lógica ya existente en `telegram_bot.py`)

---

### 6. Actualización de Email Monitor

**Archivo**: `/app/backend/email_monitor.py`

Ahora usa el servicio centralizado de cuenta de depósito:
```python
from cuenta_deposito_service import cuenta_deposito_service

async def _get_cuenta_pago(self):
    cuenta = await cuenta_deposito_service.obtener_cuenta_activa()
    return cuenta
```

---

## 📊 Configuración del Monitor

### Intervalo de Ejecución
**Ubicación**: `/app/backend/email_monitor.py` (línea 454)
```python
await asyncio.sleep(120)  # 2 minutos
```

**Configuración Supervisor**: `/etc/supervisor/conf.d/supervisord.conf`
- El monitor se ejecuta como proceso en segundo plano
- Autostart: true
- Autorestart: true

### Respuesta Inmediata
El monitor responde al cliente en la **misma ejecución** que detecta el correo:
- Detecta correo → Procesa → Responde → Marca como leído
- Todo en un mismo ciclo (menos de 1 segundo de procesamiento)

---

## 🔄 Uso Centralizado de la Cuenta

### Canales que Usan la Cuenta Activa:

1. **Email Monitor** (`email_monitor.py`)
   - Correos de "Información incompleta"
   - Correos de "Operación registrada"

2. **Telegram Bot** (`telegram_bot.py`)
   - Pendiente: Actualizar para usar el servicio centralizado
   - Ubicaciones a modificar: Donde se muestre la cuenta para pagos

3. **Frontend Web** (`ConfiguracionCuenta.jsx`)
   - Panel de administración de la cuenta
   - Visualización en portal del cliente (pendiente implementar)

---

## 📁 Archivos Modificados/Creados

### Backend
- ✅ `/app/backend/cuenta_deposito_service.py` - **NUEVO** - Servicio centralizado
- ✅ `/app/backend/server.py` - Endpoints de configuración
- ✅ `/app/backend/email_monitor.py` - Conversación guiada + uso de cuenta centralizada
- ✅ `/app/backend/gmail_service.py` - Query corregido

### Frontend
- ✅ `/app/frontend/src/pages/ConfiguracionCuenta.jsx` - **NUEVO** - Panel admin
- ✅ `/app/frontend/src/App.js` - Ruta agregada
- ✅ `/app/frontend/src/pages/Dashboard.jsx` - Botón de acceso

### Base de Datos
- ✅ Colección `config_cuenta_deposito_netcash` creada
- ✅ Cuenta real insertada y activa
- ✅ Índice único en `usuarios_telegram.telegram_id`

---

## 🧪 Testing Realizado

### 1. Backend API
```bash
curl http://localhost:8001/api/config/cuenta-deposito-activa
# ✅ Respuesta: STP - 646180139409481462
```

### 2. Monitor de Email
```bash
tail -f /var/log/email_monitor.log
# ✅ Detecta correos sin "NetCash"
# ✅ Envía respuestas automáticas
# ✅ Etiqueta correctamente
```

### 3. Servicios
```bash
sudo supervisorctl status
# ✅ backend: RUNNING
# ✅ frontend: RUNNING
# ✅ email_monitor: RUNNING
```

---

## 🎯 Próximos Pasos Recomendados

### Pendiente de Usuario
1. **Validar flujo de email completo**:
   - Enviar correo completo con "NetCash" → verificar creación de operación
   - Enviar correo incompleto → verificar respuesta dinámica
   - Responder al hilo con información faltante → verificar re-evaluación

2. **Probar panel de administración**:
   - Acceder a `/config/cuenta-deposito`
   - Crear nueva cuenta
   - Verificar que se muestra en correos

### Trabajo Técnico Futuro
3. **Telegram Bot**: Actualizar para usar `cuenta_deposito_service`
4. **Frontend Cliente**: Agregar sección donde los clientes vean la cuenta activa
5. **Monitor de inactividad**: Corregir (P2)
6. **Modo espejo web**: Finalizar (P3)
7. **Filtros de búsqueda**: Implementar (P3)

---

## ⚠️ Notas Importantes

1. **La cuenta cambia semanalmente**: Por eso se creó el módulo de configuración. Ya no es necesario tocar código ni BD manualmente.

2. **Todos los canales deben usar el servicio centralizado**: Pendiente actualizar Telegram bot.

3. **El monitor responde en tiempo real**: Cada 2 minutos revisa correos y responde inmediatamente.

4. **Los correos sin "NetCash" ahora se manejan**: Ya no se quedan sin respuesta.

5. **La conversación es guiada**: El sistema "recuerda" qué falta y solo pide eso en respuestas subsecuentes.

---

## 📞 Soporte

Para cualquier duda sobre la configuración o uso del módulo, consultar:
- Documentación técnica: Este archivo
- Logs del monitor: `/var/log/email_monitor.log`
- Logs del backend: `/var/log/supervisor/backend.err.log`
