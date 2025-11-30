# Catálogo de Usuarios NetCash

## 📋 Resumen

Implementación del catálogo centralizado de usuarios con roles y permisos para el sistema NetCash. Reemplaza constantes hardcodeadas por una gestión dinámica desde base de datos.

**Fecha**: Diciembre 2025  
**Tipo**: Feature - Gestión de Usuarios  

---

## 🎯 Objetivo

**Antes:**
- IDs de Telegram hardcodeados en `telegram_config.py`
- Difícil agregar/modificar usuarios
- No hay visibilidad de quién tiene qué permisos

**Ahora:**
- Catálogo centralizado en MongoDB
- Gestión dinámica de usuarios y permisos
- Vista web para consultar usuarios
- Fácil agregar nuevos roles

---

## 👥 Usuarios Iniciales

### 1. Daniel (Master)
- **Rol**: `master`
- **Telegram ID**: 76316336750 (pruebas)
- **Email**: daniel@mbco.mx
- **Permisos**:
  - `puede_asignar_folio_mbco`: ✅
  - `recibe_alertas_tesoreria`: ✅
  - `recibe_alertas_proveedor`: ✅
  - `recibe_reporte_diario`: ✅
  - `acceso_total`: ✅

### 2. Ana (Admin NetCash)
- **Rol**: `admin_netcash`
- **Telegram ID**: 76316336750 (pruebas) → **1720830607 en producción**
- **Email**: ana@mbco.mx
- **Permisos**:
  - `puede_asignar_folio_mbco`: ✅
- **Función**: Asigna folios MBco a operaciones

### 3. Toño (Tesorería)
- **Rol**: `tesoreria`
- **Telegram ID**: Pendiente
- **Email**: tono@mbco.mx
- **Permisos**:
  - `recibe_alertas_tesoreria`: ✅
- **Función**: Concilia y realiza pagos

### 4. Javier (Supervisor Tesorería)
- **Rol**: `sup_tesoreria`
- **Telegram ID**: Pendiente
- **Email**: javier@mbco.mx
- **Permisos**:
  - `recibe_alertas_tesoreria`: ✅
  - `recibe_reporte_diario`: ✅
- **Función**: Supervisa a Toño

### 5. Ximena (Operador Proveedor)
- **Rol**: `operador_proveedor`
- **Telegram ID**: Pendiente
- **Email**: ximena@mbco.mx
- **Permisos**:
  - `recibe_alertas_proveedor`: ✅
- **Función**: Concilia con proveedor, genera líneas NetCash

### 6. Carlos (Supervisor Proveedor)
- **Rol**: `sup_proveedor`
- **Telegram ID**: Pendiente
- **Email**: carlos@mbco.mx
- **Permisos**:
  - `recibe_alertas_proveedor`: ✅
  - `recibe_reporte_diario`: ✅
- **Función**: Supervisa a Ximena

### 7. Samuel (Socio MBco)
- **Rol**: `socio_mbco`
- **Telegram ID**: Pendiente
- **Email**: samuel@mbco.mx
- **Permisos**:
  - `recibe_reporte_diario`: ✅
- **Función**: Recibe reportes diarios

### 8. Nash (Dueño DNS)
- **Rol**: `dueno_dns`
- **Telegram ID**: Pendiente
- **Email**: nash@mbco.mx
- **Permisos**:
  - `recibe_reporte_diario`: ✅
- **Función**: Recibe reportes diarios

### 9. AGLAE (Apoyo Cliente)
- **Rol**: `apoyo_cliente`
- **Telegram ID**: Pendiente
- **Email**: aglae@mbco.mx
- **Permisos**:
  - `puede_crear_operaciones_cliente`: ✅
- **Función**: Crea operaciones a nombre de clientes

---

## 🗄️ Estructura de Datos

### Colección: `usuarios_netcash`

```javascript
{
  "_id": ObjectId("..."),
  "id_usuario": "uuid",  // ID único del usuario
  "nombre": "Ana",
  "rol_negocio": "admin_netcash",
  "telegram_id": 1720830607,  // Puede ser null
  "email": "ana@mbco.mx",  // Puede ser null
  "activo": true,
  
  "permisos": {
    "puede_asignar_folio_mbco": true,
    "recibe_alertas_tesoreria": false,
    "recibe_alertas_proveedor": false,
    "recibe_reporte_diario": false,
    // Fácil agregar nuevos permisos aquí
  },
  
  "created_at": ISODate("2025-12-01T10:00:00Z"),
  "updated_at": ISODate("2025-12-01T10:00:00Z")
}
```

---

## 🔧 Componentes Implementados

### 1. Repositorio de Usuarios

**Archivo**: `/app/backend/usuarios_repo.py`

**Clase**: `UsuariosRepository`

**Funciones principales:**

#### `obtener_usuario_por_rol(rol_negocio)`
Obtiene el primer usuario activo con un rol específico.

```python
ana = await usuarios_repo.obtener_usuario_por_rol("admin_netcash")
# Retorna: {"nombre": "Ana", "telegram_id": 76316336750, ...}
```

#### `obtener_usuarios_por_permiso(flag_permiso, valor=True)`
Obtiene todos los usuarios activos con un permiso específico.

```python
usuarios_tesoreria = await usuarios_repo.obtener_usuarios_por_permiso("recibe_alertas_tesoreria")
# Retorna: [{"nombre": "Toño", ...}, {"nombre": "Javier", ...}]
```

#### `listar_todos_usuarios()`
Lista todos los usuarios del sistema.

```python
usuarios = await usuarios_repo.listar_todos_usuarios()
# Retorna: Lista completa ordenada por nombre
```

#### `sembrar_usuarios_iniciales()`
Siembra los 9 usuarios iniciales si la colección está vacía.

Se ejecuta automáticamente al iniciar el backend.

---

### 2. Integración con Notificaciones

**Antes (hardcoded):**
```python
from telegram_config import TELEGRAM_ID_ANA

# Enviar notificación
await bot.send_message(chat_id=TELEGRAM_ID_ANA, text=mensaje)
```

**Ahora (dinámico):**
```python
from usuarios_repo import usuarios_repo

# Obtener usuario desde catálogo
ana = await usuarios_repo.obtener_usuario_por_rol("admin_netcash")

if not ana or not ana.get("telegram_id"):
    logger.warning("[NetCash] Ana no tiene telegram_id configurado")
    return

# Enviar notificación
await bot.send_message(chat_id=ana["telegram_id"], text=mensaje)
```

**Modificaciones realizadas:**

1. **`netcash_service.py`**:
   - `_notificar_ana_solicitud_lista()`: Usa catálogo en lugar de constante
   - `_notificar_tesoreria_telegram()`: Notifica a TODOS los usuarios con permiso `recibe_alertas_tesoreria`

2. **`telegram_ana_handlers.py`**:
   - `notificar_nueva_solicitud_para_mbco()`: Recibe objeto `usuario` como parámetro

3. **`telegram_tesoreria_handlers.py`**:
   - `notificar_nueva_orden_interna()`: Recibe objeto `usuario` como parámetro

---

### 3. Endpoints API

**Archivo**: `/app/backend/routes/usuarios_routes.py`

#### `GET /api/netcash/usuarios/`
Lista todos los usuarios del catálogo.

**Respuesta:**
```json
[
  {
    "id_usuario": "abc-123",
    "nombre": "Ana",
    "rol_negocio": "admin_netcash",
    "telegram_id": 76316336750,
    "email": "ana@mbco.mx",
    "activo": true,
    "permisos": {
      "puede_asignar_folio_mbco": true
    },
    "created_at": "2025-12-01T10:00:00Z"
  },
  ...
]
```

#### `GET /api/netcash/usuarios/por-rol/{rol_negocio}`
Obtiene un usuario específico por su rol.

**Ejemplo:**
```bash
GET /api/netcash/usuarios/por-rol/admin_netcash
```

#### `POST /api/netcash/usuarios/sembrar`
Siembra usuarios iniciales (útil para reset o inicialización).

---

### 4. Vista Frontend

**Archivo**: `/app/frontend/src/pages/UsuariosNetCash.jsx`

**Ruta**: `/usuarios-netcash`

**Características:**
- ✅ Lista todos los usuarios del catálogo
- ✅ Muestra rol con badge de color
- ✅ Indica si usuario está activo/inactivo
- ✅ Muestra Telegram ID y email
- ✅ Lista permisos activos
- ✅ Diseño responsive con Tailwind CSS

**Vista incluye:**
- Nombre del usuario
- Rol de negocio (con badge de color)
- Estado (activo/inactivo)
- Telegram ID
- Email
- Permisos activos

**Colores por rol:**
- `master`: Púrpura
- `admin_netcash`: Azul
- `tesoreria`: Verde
- `sup_tesoreria`: Verde oscuro
- `operador_proveedor`: Naranja
- `sup_proveedor`: Naranja oscuro
- `socio_mbco`: Índigo
- `dueno_dns`: Rosa
- `apoyo_cliente`: Cyan

---

## 🔄 Flujo de Notificaciones (Actualizado)

### Notificación a Ana (Admin NetCash)

```
1. Solicitud → estado "lista_para_mbc"
   ↓
2. netcash_service._notificar_ana_solicitud_lista()
   ↓
3. usuarios_repo.obtener_usuario_por_rol("admin_netcash")
   ↓
4. Verificar telegram_id
   ↓
5. Enviar notificación al telegram_id del catálogo
```

### Notificación a Tesorería

```
1. Ana asigna folio MBco
   ↓
2. Se genera orden interna
   ↓
3. netcash_service._notificar_tesoreria_telegram()
   ↓
4. usuarios_repo.obtener_usuarios_por_permiso("recibe_alertas_tesoreria")
   ↓
5. Para cada usuario con el permiso:
   - Verificar telegram_id
   - Enviar notificación
```

**Ventaja**: Si agregamos más supervisores de tesorería, automáticamente reciben notificaciones.

---

## 📝 Archivos Creados/Modificados

### Archivos Nuevos:

1. **`/app/backend/usuarios_repo.py`**
   - Repositorio completo de usuarios
   - Siembra de usuarios iniciales
   - Consultas por rol y permiso

2. **`/app/backend/routes/usuarios_routes.py`**
   - Endpoints API para gestión de usuarios

3. **`/app/frontend/src/pages/UsuariosNetCash.jsx`**
   - Vista web de usuarios

4. **`/app/CATALOGO_USUARIOS_NETCASH.md`**
   - Documentación completa

### Archivos Modificados:

1. **`/app/backend/server.py`**
   - Agregado router de usuarios
   - Evento `startup` para sembrar usuarios

2. **`/app/backend/netcash_service.py`**
   - `_notificar_ana_solicitud_lista()`: Usa catálogo
   - `_notificar_tesoreria_telegram()`: Usa catálogo y notifica a múltiples usuarios

3. **`/app/backend/telegram_ana_handlers.py`**
   - `notificar_nueva_solicitud_para_mbco()`: Recibe objeto usuario

4. **`/app/backend/telegram_tesoreria_handlers.py`**
   - `notificar_nueva_orden_interna()`: Recibe objeto usuario

5. **`/app/frontend/src/App.js`**
   - Agregada ruta `/usuarios-netcash`

---

## 🧪 Testing

### 1. Verificar Siembra de Usuarios

**Consultar MongoDB:**
```javascript
use netcash_mbco
db.usuarios_netcash.find().pretty()

// Debe haber 9 usuarios
```

### 2. Probar Endpoint de Usuarios

```bash
curl http://localhost:8001/api/netcash/usuarios/
```

**Resultado esperado**: Lista JSON con 9 usuarios

### 3. Probar Notificación a Ana

```
1. Crear operación NetCash completa
2. Confirmar → Estado "lista_para_mbc"
3. Verificar en logs:
   "[UsuariosRepo] Usuario encontrado para rol 'admin_netcash': Ana"
   "[NetCash] Notificación enviada a Ana (admin_netcash)"
4. Ana (ID 76316336750) debe recibir notificación en Telegram
```

### 4. Verificar Vista Web

```
1. Abrir: http://localhost:3000/usuarios-netcash
2. Verificar que se muestran 9 usuarios
3. Verificar badges de colores por rol
4. Verificar que se muestran permisos activos
```

---

## ⚙️ Configuración para Producción

### IDs de Telegram a Actualizar

**En MongoDB** (actualizar directamente):

```javascript
// Ana (Admin NetCash)
db.usuarios_netcash.updateOne(
  { rol_negocio: "admin_netcash" },
  { $set: { telegram_id: 1720830607 } }
)

// Toño (Tesorería)
db.usuarios_netcash.updateOne(
  { rol_negocio: "tesoreria" },
  { $set: { telegram_id: XXXXXXXX } }  // ID real de Toño
)

// ... repetir para cada usuario
```

**Método alternativo** (futuro):
- Crear endpoint `PATCH /api/netcash/usuarios/{id_usuario}` para editar usuarios
- Crear formulario en frontend para actualizar datos

---

## 🔜 Próximas Mejoras (Futuras)

1. **Edición de usuarios desde web**
   - Botón "Editar" en cada usuario
   - Formulario para cambiar telegram_id, email, permisos

2. **Crear nuevo usuario**
   - Formulario web para agregar usuarios
   - Validación de datos

3. **Desactivar/activar usuarios**
   - Toggle en la vista web
   - Endpoint PATCH

4. **Historial de cambios**
   - Registrar quién modificó qué y cuándo

5. **Roles y permisos más granulares**
   - Permisos a nivel de operación
   - Permisos de visualización vs edición

6. **Múltiples telegram_ids por usuario**
   - Lista de IDs en lugar de uno solo
   - Útil si un usuario tiene varios dispositivos

---

## ✅ Criterios de Aceptación (Completados)

✅ **1. Notificación a Ana usa catálogo**
- Función `_notificar_ana_solicitud_lista()` consulta `usuarios_repo`
- Se envía al `telegram_id` del usuario `admin_netcash`

✅ **2. Notificación a Tesorería usa catálogo**
- Función `_notificar_tesoreria_telegram()` consulta `usuarios_repo`
- Se envía a TODOS los usuarios con permiso `recibe_alertas_tesoreria`

✅ **3. Colección usuarios_netcash existe**
- 9 usuarios sembrados automáticamente al iniciar backend
- Todos con roles y permisos correctos

✅ **4. Endpoint y vista web funcionando**
- Endpoint `GET /api/netcash/usuarios/` operativo
- Vista `/usuarios-netcash` muestra tabla de usuarios

✅ **5. Sin regresiones**
- Todo el flujo NetCash sigue funcionando igual
- Validaciones, duplicados, ZIP, fuzzy matching sin cambios

---

## 🎉 Resumen Ejecutivo

El catálogo de usuarios NetCash está **COMPLETADO y FUNCIONANDO**. Se reemplazaron constantes hardcodeadas por gestión dinámica desde MongoDB. Los 9 usuarios iniciales están sembrados con roles y permisos correctos. Las notificaciones de Ana y Tesorería ahora consultan el catálogo automáticamente. Vista web disponible para consultar usuarios. Sistema preparado para futura gestión completa de usuarios y permisos.

---

**Status**: ✅ **COMPLETADO**  
**Listo para**: Producción (actualizar IDs de Telegram reales)  
**Vista web**: http://localhost:3000/usuarios-netcash
