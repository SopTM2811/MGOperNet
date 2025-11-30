# Notificación a Ana (Admin NetCash)

## 📋 Resumen

Documentación completa del flujo de notificaciones a Ana cuando una solicitud NetCash queda lista para MBco.

**Usuario**: Ana (admin_netcash)  
**Telegram ID correcto**: `7631636750`  
**Fecha actualización**: Diciembre 2025  

---

## 🎯 ¿Cuándo se dispara la notificación?

**Trigger**: Cuando una solicitud NetCash cambia a estado `lista_para_mbc`

**Flujo:**
```
1. Cliente confirma operación NetCash en Telegram
   ↓
2. Sistema valida comprobantes, CLABE, beneficiario, etc.
   ↓
3. Si todo OK → Estado cambia a "lista_para_mbc"
   ↓
4. Se llama a netcash_service._notificar_ana_solicitud_lista()
   ↓
5. Se consulta catálogo de usuarios (usuarios_netcash)
   ↓
6. Se obtiene usuario con rol "admin_netcash"
   ↓
7. Se envía notificación al telegram_id del usuario
```

---

## 🗄️ Requisitos en Base de Datos

### Colección: `usuarios_netcash`

**Usuario Ana debe tener:**

```javascript
{
  "nombre": "Ana",
  "rol_negocio": "admin_netcash",  // OBLIGATORIO: exactamente este valor
  "telegram_id": 7631636750,        // OBLIGATORIO: exactamente este ID
  "activo": true,                   // OBLIGATORIO: debe ser true
  "email": "ana@mbco.mx",
  "permisos": {
    "puede_asignar_folio_mbco": true,
    "puede_ver_usuarios": true,
    "puede_usar_alta_telegram": true
  }
}
```

**Campos críticos:**
- ✅ `rol_negocio` = `"admin_netcash"` (exacto)
- ✅ `activo` = `true`
- ✅ `telegram_id` = `7631636750` (número, no string)

---

## 📝 Comando de Actualización

### Actualizar telegram_id de Ana

**Comando MongoDB:**
```javascript
use netcash_mbco

db.usuarios_netcash.updateOne(
  { rol_negocio: "admin_netcash" },
  { $set: { telegram_id: 7631636750 } }
)
```

**Comando Python:**
```python
cd /app && python3 << 'EOF'
import asyncio
import os
import sys
sys.path.insert(0, '/app/backend')
from motor.motor_asyncio import AsyncIOMotorClient

async def actualizar_ana():
    mongo_url = os.getenv('MONGO_URL')
    client = AsyncIOMotorClient(mongo_url)
    db = client['netcash_mbco']
    
    result = await db.usuarios_netcash.update_one(
        {'rol_negocio': 'admin_netcash'},
        {'$set': {'telegram_id': 7631636750}}
    )
    
    print(f'✅ Actualización: {result.modified_count} documento(s)')
    
    ana = await db.usuarios_netcash.find_one(
        {'rol_negocio': 'admin_netcash'},
        {'_id': 0, 'nombre': 1, 'telegram_id': 1, 'activo': 1}
    )
    
    print(f'Ana: {ana}')
    client.close()

asyncio.run(actualizar_ana())
EOF
```

**Resultado ejecutado:**
```
✅ Actualización: 1 documento(s) modificado(s)
Usuario Ana actualizado:
  Nombre: Ana
  Rol: admin_netcash
  Telegram ID: 7631636750
  Activo: True
```

---

## 🔍 Código Implementado

### Función de Notificación

**Archivo**: `/app/backend/netcash_service.py`

**Función**: `_notificar_ana_solicitud_lista(solicitud)`

**Flujo detallado:**

```python
async def _notificar_ana_solicitud_lista(self, solicitud: Dict):
    # 1. Obtener usuario Ana desde catálogo
    ana = await usuarios_repo.obtener_usuario_por_rol("admin_netcash")
    
    # 2. Validar que existe
    if not ana:
        logger.error("[NOTIF_ANA] ERROR: No se encontró usuario admin_netcash")
        return
    
    # 3. Validar telegram_id
    if not ana.get("telegram_id"):
        logger.error("[NOTIF_ANA] ERROR: Ana no tiene telegram_id")
        return
    
    # 4. Enviar notificación
    telegram_id = ana.get("telegram_id")
    await telegram_ana_handlers.notificar_nueva_solicitud_para_mbco(solicitud, ana)
    
    logger.info(f"[NOTIF_ANA] ✅ Notificación enviada a chat_id={telegram_id}")
```

**Punto de llamada:**

```python
# En netcash_service.py -> procesar_solicitud_automaticamente()

# Después de cambiar estado a lista_para_mbc:
await self.cambiar_estado(
    solicitud_id,
    EstadoSolicitud.LISTA_PARA_MBC,
    "Todas las validaciones pasaron"
)

# Notificar a Ana
solicitud_actualizada = await db[COLLECTION_NAME].find_one({"id": solicitud_id}, {"_id": 0})
await self._notificar_ana_solicitud_lista(solicitud_actualizada)
```

---

## 📊 Logs de Diagnóstico

### Tags de Log

Todos los logs de notificación a Ana usan el tag: `[NOTIF_ANA]`

### Logs Esperados (Caso Exitoso)

```
[NOTIF_ANA] ========== INICIO NOTIFICACIÓN A ANA ==========
[NOTIF_ANA] Solicitud: NC-000020
[NOTIF_ANA] Consultando usuario con rol 'admin_netcash' en catálogo...
[NOTIF_ANA] Usuario encontrado: Ana
[NOTIF_ANA] Activo: True
[NOTIF_ANA] Telegram ID: 7631636750
[NOTIF_ANA] Intentando notificar a Ana | folio_netcash=NC-000020 | chat_id=7631636750
[Ana Telegram] Preparando notificación para Ana
[Ana Telegram] Folio: NC-000020 | Chat ID: 7631636750
[Ana Telegram] Enviando mensaje a Telegram...
[Ana Telegram] Chat ID: 7631636750
[Ana Telegram] Folio: NC-000020
[Ana Telegram] ✅ Mensaje enviado exitosamente a chat_id=7631636750
[Ana Telegram] Notificación completada para solicitud NC-000020
[NOTIF_ANA] ✅ Notificación enviada exitosamente a Ana (chat_id=7631636750)
[NOTIF_ANA] ========== FIN NOTIFICACIÓN A ANA ==========
```

### Logs de Error (Casos Fallidos)

#### Error 1: Usuario no encontrado
```
[NOTIF_ANA] ERROR: No se encontró usuario con rol 'admin_netcash' en el catálogo
[NOTIF_ANA] Verificar que existe usuario con rol_negocio='admin_netcash' y activo=true
```

**Solución**: Verificar en MongoDB que existe usuario con `rol_negocio: "admin_netcash"` y `activo: true`

#### Error 2: telegram_id no configurado
```
[NOTIF_ANA] ERROR: Usuario Ana (admin_netcash) no tiene telegram_id configurado
[NOTIF_ANA] Actualizar campo telegram_id en la colección usuarios_netcash
```

**Solución**: Ejecutar comando de actualización (ver sección "Comando de Actualización")

#### Error 3: Handlers no inicializados
```
[NOTIF_ANA] ERROR: telegram_ana_handlers no inicializado, notificación no enviada
```

**Solución**: Reiniciar servicio `telegram_bot`:
```bash
sudo supervisorctl restart telegram_bot
```

---

## 🧪 Cómo Probar

### Método 1: Crear operación de prueba

```
1. Ir a Telegram
2. Iniciar operación NetCash con el bot
3. Subir comprobantes válidos
4. Completar datos (beneficiario, IDMEX, ligas)
5. Confirmar operación
6. Verificar que Ana recibe notificación en chat_id 7631636750
```

### Método 2: Verificar logs

```bash
# Ver logs de backend
tail -f /var/log/supervisor/backend.err.log | grep NOTIF_ANA

# Ver logs de telegram_bot
tail -f /var/log/supervisor/telegram_bot.err.log | grep "Ana Telegram"
```

### Método 3: Verificar última operación

```bash
cd /app && python3 << 'EOF'
import asyncio
import os
import sys
sys.path.insert(0, '/app/backend')
from motor.motor_asyncio import AsyncIOMotorClient

async def verificar():
    client = AsyncIOMotorClient(os.getenv('MONGO_URL'))
    db = client['netcash_mbco']
    
    # Última solicitud en estado lista_para_mbc
    sol = await db.solicitudes_netcash.find_one(
        {'estado': 'lista_para_mbc'},
        {'_id': 0, 'folio_netcash': 1, 'estado': 1, 'created_at': 1}
    )
    
    if sol:
        print(f"✅ Última operación lista para MBco:")
        print(f"   Folio: {sol.get('folio_netcash')}")
        print(f"   Estado: {sol.get('estado')}")
    else:
        print("❌ No hay operaciones en estado lista_para_mbc")
    
    client.close()

asyncio.run(verificar())
EOF
```

---

## ⚠️ Problemas Comunes y Soluciones

### 1. Ana no recibe notificación

**Verificaciones:**

1. **Usuario Ana en BD:**
   ```javascript
   db.usuarios_netcash.findOne(
     { rol_negocio: "admin_netcash" },
     { nombre: 1, telegram_id: 1, activo: 1 }
   )
   ```
   
   Debe retornar:
   ```javascript
   {
     "nombre": "Ana",
     "telegram_id": 7631636750,
     "activo": true
   }
   ```

2. **Servicios corriendo:**
   ```bash
   sudo supervisorctl status telegram_bot
   # Debe estar RUNNING
   ```

3. **Logs de error:**
   ```bash
   tail -50 /var/log/supervisor/backend.err.log | grep "NOTIF_ANA.*ERROR"
   ```

### 2. Telegram ID incorrecto

**Error**: Ana recibe notificación en chat equivocado

**Solución**:
```javascript
db.usuarios_netcash.updateOne(
  { rol_negocio: "admin_netcash" },
  { $set: { telegram_id: 7631636750 } }  // ID correcto
)
```

Luego reiniciar backend:
```bash
sudo supervisorctl restart backend telegram_bot
```

### 3. Usuario inactivo

**Error**: Usuario encontrado pero no notifica

**Verificar**:
```javascript
db.usuarios_netcash.findOne(
  { rol_negocio: "admin_netcash" },
  { activo: 1 }
)
```

**Activar**:
```javascript
db.usuarios_netcash.updateOne(
  { rol_negocio: "admin_netcash" },
  { $set: { activo: true } }
)
```

---

## 🔧 Mantenimiento

### Cambiar Telegram ID de Ana (Producción)

Cuando se vaya a producción con el ID real de Ana (1720830607):

```javascript
use netcash_mbco

db.usuarios_netcash.updateOne(
  { rol_negocio: "admin_netcash" },
  { $set: { telegram_id: 1720830607 } }  // ID real de Ana
)
```

### Agregar otro admin_netcash

Si se necesita que más personas reciban notificaciones de admin_netcash:

**Opción 1**: Crear rol específico (recomendado)
```javascript
// Crear usuario con rol específico
db.usuarios_netcash.insertOne({
  "nombre": "María",
  "rol_negocio": "admin_netcash_backup",
  "telegram_id": XXXXXXXXX,
  "activo": true,
  "permisos": {
    "puede_asignar_folio_mbco": true
  }
})
```

**Opción 2**: Modificar código para notificar a múltiples admin_netcash
```python
# En netcash_service.py
usuarios_admin = await usuarios_repo.obtener_usuarios_por_rol("admin_netcash")
for usuario in usuarios_admin:
    if usuario.get("telegram_id"):
        await telegram_ana_handlers.notificar_nueva_solicitud_para_mbco(solicitud, usuario)
```

---

## 📋 Checklist de Verificación

Antes de generar una nueva operación de prueba, verificar:

- [ ] Usuario Ana existe en `usuarios_netcash`
- [ ] `rol_negocio` = `"admin_netcash"`
- [ ] `activo` = `true`
- [ ] `telegram_id` = `7631636750`
- [ ] Servicio `telegram_bot` está RUNNING
- [ ] Servicio `backend` está RUNNING
- [ ] No hay errores en logs recientes

**Comando rápido de verificación:**
```bash
cd /app && python3 << 'EOF'
import asyncio
import os
import sys
sys.path.insert(0, '/app/backend')
from motor.motor_asyncio import AsyncIOMotorClient

async def check():
    client = AsyncIOMotorClient(os.getenv('MONGO_URL'))
    db = client['netcash_mbco']
    
    ana = await db.usuarios_netcash.find_one(
        {'rol_negocio': 'admin_netcash'},
        {'_id': 0, 'nombre': 1, 'telegram_id': 1, 'activo': 1}
    )
    
    print("Verificación de Ana:")
    if ana:
        print(f"  ✅ Usuario encontrado: {ana.get('nombre')}")
        print(f"  {'✅' if ana.get('activo') else '❌'} Activo: {ana.get('activo')}")
        print(f"  {'✅' if ana.get('telegram_id') == 7631636750 else '❌'} Telegram ID: {ana.get('telegram_id')} (esperado: 7631636750)")
    else:
        print("  ❌ Usuario Ana no encontrado")
    
    client.close()

asyncio.run(check())
EOF
```

---

**Status**: ✅ **ACTUALIZADO**  
**Telegram ID correcto**: 7631636750  
**Última actualización**: Diciembre 2025
