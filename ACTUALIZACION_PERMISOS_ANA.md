# Actualización: Permisos de Ana y Botón Usuarios

## 📋 Resumen

Ajustes para refinar el rol de Ana (admin_netcash) y agregar el botón "Usuarios" en la landing de NetCash.

**Fecha**: Diciembre 2025  
**Tipo**: Feature Enhancement  

---

## 🎯 Cambios Implementados

### 1. Nuevos Permisos para Ana y Master

Se agregaron dos nuevos flags de permisos al catálogo de usuarios:

**Nuevos flags:**
- `puede_ver_usuarios` (bool): Permite acceder al catálogo de usuarios
- `puede_usar_alta_telegram` (bool): Permite usar el módulo Alta Telegram

**Usuarios actualizados:**

#### Daniel (master)
```javascript
{
  "nombre": "Daniel",
  "rol_negocio": "master",
  "permisos": {
    "puede_asignar_folio_mbco": true,
    "puede_ver_usuarios": true,         // 🆕
    "puede_usar_alta_telegram": true,   // 🆕
    "recibe_alertas_tesoreria": true,
    "recibe_alertas_proveedor": true,
    "recibe_reporte_diario": true,
    "acceso_total": true
  }
}
```

#### Ana (admin_netcash)
```javascript
{
  "nombre": "Ana",
  "rol_negocio": "admin_netcash",
  "permisos": {
    "puede_asignar_folio_mbco": true,
    "puede_ver_usuarios": true,         // 🆕
    "puede_usar_alta_telegram": true,   // 🆕
    "recibe_alertas_tesoreria": false,
    "recibe_alertas_proveedor": false,
    "recibe_reporte_diario": false
  }
}
```

**Funciones de Ana:**
1. ✅ Asignar folios MBco a operaciones
2. ✅ Usar módulo "Alta Telegram" (dar de alta/vincular clientes)
3. ✅ Ver catálogo de usuarios NetCash

---

### 2. Funciones Helper de Permisos

**Archivo**: `/app/backend/usuarios_repo.py`

Se agregaron dos funciones helper para verificar permisos:

#### `usuario_puede_usar_alta_telegram(usuario)`
Verifica si un usuario tiene permiso para usar Alta Telegram.

```python
from usuarios_repo import usuarios_repo

if await usuarios_repo.usuario_puede_usar_alta_telegram(usuario):
    # Usuario puede ejecutar acciones de Alta Telegram
    pass
```

#### `usuario_puede_ver_usuarios(usuario)`
Verifica si un usuario tiene permiso para ver el catálogo de usuarios.

```python
if await usuarios_repo.usuario_puede_ver_usuarios(usuario):
    # Usuario puede acceder a /usuarios-netcash
    pass
```

**Uso futuro** (cuando haya autenticación completa):
```python
# En endpoint de Alta Telegram
@router.post("/alta-telegram")
async def alta_telegram(usuario_actual: dict):
    if not await usuarios_repo.usuario_puede_usar_alta_telegram(usuario_actual):
        raise HTTPException(status_code=403, detail="No tienes permisos")
    
    # Procesar alta...
```

---

### 3. Botón "Usuarios" en la Landing

**Archivo**: `/app/frontend/src/pages/Home.jsx`

Se agregó un nuevo botón en la pantalla principal de NetCash junto a los botones existentes.

**Botones en la landing:**
```
Operaciones | Clientes | MBControl | Alta Telegram | Mis Solicitudes | Usuarios
```

**Características del botón:**
- **Texto**: "Usuarios"
- **Color**: Gris oscuro (bg-gray-700)
- **Icono**: Users (lucide-react)
- **Acción**: Navega a `/usuarios-netcash`

**Código:**
```jsx
<Button
  data-testid="usuarios-netcash-btn"
  onClick={() => navigate('/usuarios-netcash')}
  size="lg"
  className="bg-gray-700 hover:bg-gray-800 text-white px-10 py-6 text-base rounded-lg shadow-soft hover:shadow-medium transition-all font-medium"
>
  <Users className="mr-2 h-5 w-5" />
  Usuarios
  <ArrowRight className="ml-2 h-5 w-5" />
</Button>
```

**Preparado para control de acceso:**
```jsx
{/* TODO: cuando tengamos usuario logueado, mostrar este botón solo si 
    usuario.permisos.puede_ver_usuarios === true */}
<Button onClick={() => navigate('/usuarios-netcash')}>
  Usuarios
</Button>
```

**Implementación futura** (con autenticación):
```jsx
const { usuario } = useAuth(); // Hook de autenticación

// Renderizar botón solo si tiene permiso
{usuario?.permisos?.puede_ver_usuarios && (
  <Button onClick={() => navigate('/usuarios-netcash')}>
    Usuarios
  </Button>
)}
```

---

## 📁 Archivos Modificados

### Backend:

1. **`/app/backend/usuarios_repo.py`**
   - Permisos de Daniel actualizados
   - Permisos de Ana actualizados
   - Funciones `usuario_puede_usar_alta_telegram()`
   - Funciones `usuario_puede_ver_usuarios()`

### Frontend:

1. **`/app/frontend/src/pages/Home.jsx`**
   - Agregado botón "Usuarios"
   - Comentario TODO para control de acceso futuro

### Scripts:

1. **`/app/actualizar_permisos_usuarios.py`** (nuevo)
   - Script para actualizar permisos de usuarios existentes

---

## ✅ Criterios de Aceptación (Completados)

✅ **1. Catálogo de usuarios actualizado**
- Daniel (master) tiene:
  - `puede_ver_usuarios: true`
  - `puede_usar_alta_telegram: true`
- Ana (admin_netcash) tiene:
  - `puede_ver_usuarios: true`
  - `puede_usar_alta_telegram: true`

✅ **2. Botón "Usuarios" en la landing**
- Visible en la pantalla principal de NetCash
- Ubicado junto a: Operaciones, Clientes, MBControl, Alta Telegram, Mis Solicitudes
- Al hacer clic → navega a `/usuarios-netcash`

✅ **3. Código preparado para control por permisos**
- Frontend: Comentario TODO para mostrar botón solo con permiso
- Backend: Funciones helper listas para usar como gate de seguridad

---

## 🧪 Verificación

### 1. Verificar permisos en MongoDB

```javascript
use netcash_mbco

// Verificar Daniel
db.usuarios_netcash.findOne(
  { rol_negocio: "master" },
  { nombre: 1, permisos: 1 }
)

// Verificar Ana
db.usuarios_netcash.findOne(
  { rol_negocio: "admin_netcash" },
  { nombre: 1, permisos: 1 }
)
```

**Resultado esperado:**
```javascript
// Daniel
{
  "nombre": "Daniel",
  "permisos": {
    "puede_ver_usuarios": true,
    "puede_usar_alta_telegram": true,
    ...
  }
}

// Ana
{
  "nombre": "Ana",
  "permisos": {
    "puede_ver_usuarios": true,
    "puede_usar_alta_telegram": true,
    ...
  }
}
```

### 2. Verificar botón en la landing

```
1. Abrir: http://localhost:3000/
2. Verificar que aparece el botón "Usuarios" (color gris)
3. Hacer clic en "Usuarios"
4. Debe navegar a: http://localhost:3000/usuarios-netcash
5. Debe mostrar el catálogo de usuarios
```

### 3. Verificar funciones helper

```python
# En backend, probar:
python3 -c "
import asyncio
import sys
sys.path.insert(0, '/app/backend')
from usuarios_repo import usuarios_repo

async def test():
    ana = await usuarios_repo.obtener_usuario_por_rol('admin_netcash')
    puede_alta = await usuarios_repo.usuario_puede_usar_alta_telegram(ana)
    puede_ver = await usuarios_repo.usuario_puede_ver_usuarios(ana)
    print(f'Ana - Puede Alta Telegram: {puede_alta}')
    print(f'Ana - Puede Ver Usuarios: {puede_ver}')

asyncio.run(test())
"
```

**Resultado esperado:**
```
Ana - Puede Alta Telegram: True
Ana - Puede Ver Usuarios: True
```

---

## 🔜 Siguiente Paso (Control de Acceso Completo)

### Cuando se implemente autenticación completa:

**Backend:**
1. Crear middleware de autenticación
2. Endpoint `GET /api/auth/me` que retorna usuario actual
3. Decoradores de permisos:
   ```python
   @require_permission("puede_usar_alta_telegram")
   async def alta_telegram(usuario_actual: dict):
       ...
   ```

**Frontend:**
1. Hook `useAuth()` con usuario actual
2. Condicionar visibilidad de botones:
   ```jsx
   {usuario?.permisos?.puede_ver_usuarios && (
     <Button onClick={() => navigate('/usuarios-netcash')}>
       Usuarios
     </Button>
   )}
   ```

3. Proteger rutas:
   ```jsx
   <Route 
     path="/usuarios-netcash" 
     element={
       <ProtectedRoute requiredPermission="puede_ver_usuarios">
         <UsuariosNetCash />
       </ProtectedRoute>
     } 
   />
   ```

---

## 📊 Estado Actual vs Futuro

### Estado Actual ✅
- Permisos definidos en BD
- Funciones helper listas
- Botón visible para todos (preview)
- Comentarios TODO en código

### Estado Futuro 🔜
- Sistema de autenticación completo
- Control de acceso por permisos
- Botones visibles solo con permiso
- Endpoints protegidos

---

## 🎉 Resumen

Ana (admin_netcash) ahora tiene permisos claramente definidos para:
1. Asignar folios MBco
2. Usar Alta Telegram
3. Ver catálogo de usuarios

El botón "Usuarios" está visible en la landing de NetCash y navega correctamente a `/usuarios-netcash`. El código está preparado con TODOs para implementar control de acceso cuando haya autenticación completa.

---

**Status**: ✅ **COMPLETADO**  
**Preparado para**: Control de acceso futuro  
**Vista web**: http://localhost:3000/ → Botón "Usuarios"
