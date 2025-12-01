# 🧪 Instrucciones de Verificación - Menú Cliente Activo

**Fecha:** 2024-12-01  
**Bug:** Cliente activo ve "registro en revisión" en lugar de menú completo  
**Estado:** ✅ CORREGIDO - Bot reiniciado con código actualizado

---

## 📊 Estado Actual del Usuario DFGV

### En Base de Datos:

```
Usuario Telegram (telegram_id: 7631636750):
  ✅ rol: "cliente_activo"
  ✅ id_cliente: "49ac3766-bc9b-4509-89c1-433cc12bbe97"
  ✅ telefono: configurado

Cliente (id: 49ac3766-bc9b-4509-89c1-433cc12bbe97):
  ✅ estado: "activo"
  ✅ telegram_id: 7631636750
  ✅ nombre: "antonio santana"
```

### Lógica del Código Actualizada:

El archivo `/app/backend/telegram_bot.py` fue modificado en el método `mostrar_menu_principal()` (líneas 430-480) para manejar correctamente estos casos:

**CASO 1:** Cliente existe en BD y está activo ✅
- **Condición:** `if cliente and cliente.get("estado") == "activo"`
- **Resultado:** Menú completo con botón "Crear nueva operación"

**CASO 2:** Rol "cliente_activo" sin cliente en BD ✅
- **Condición:** `elif rol == "cliente_activo" and not cliente`
- **Resultado:** Menú completo (caso borde)

**CASO 3:** Cliente pendiente ⚠️
- **Condición:** `else`
- **Resultado:** Mensaje "Tu registro está en revisión"

---

## 🧪 Pasos de Verificación en Telegram

### Paso 1: Limpiar caché del bot
1. Abrir Telegram
2. Buscar el bot: `@Netcash_bot`
3. Enviar: `/start`

### Paso 2: Verificar el mensaje
**Deberías ver:**
```
Hola DFGV 😊

Ya estás dado de alta como cliente NetCash.

¿Qué necesitas hacer hoy?

[Botones:]
🧾 Crear nueva operación NetCash
💳 Ver cuenta para depósitos
📂 Ver mis solicitudes
❓ Ayuda
```

**NO deberías ver:**
```
❌ "Tu registro está en revisión por Ana"
```

### Paso 3: Probar crear operación
1. Hacer clic en "🧾 Crear nueva operación NetCash"
2. El bot debe iniciar el flujo de creación
3. Debe pedir subir comprobantes

---

## 🔧 Cambios Realizados

### 1. Base de Datos
- ✅ Creado registro de cliente con ID `49ac3766-bc9b-4509-89c1-433cc12bbe97`
- ✅ Estado: `activo`
- ✅ Vinculado con telegram_id: `7631636750`

### 2. Código
**Archivo:** `/app/backend/telegram_bot.py`  
**Método:** `mostrar_menu_principal()`  
**Líneas:** 437-470

**Mejora aplicada:**
- Agregado CASO 2 para manejar rol "cliente_activo" sin cliente en BD
- Agregado logging cuando detecta esta inconsistencia
- Sistema no bloquea al usuario en este caso borde

### 3. Servicios
- ✅ Backend reiniciado (PID 1977)
- ✅ Telegram Bot reiniciado (PID 2368) ⬅️ **CRÍTICO**
- ✅ Código actualizado en ejecución

---

## 🧪 Test Automatizado Creado

**Archivo:** `/app/backend/test_menu_directo.py`

Este script simula exactamente la lógica que el bot ejecuta cuando un usuario hace `/start`.

### Ejecutar el test:
```bash
cd /app/backend
python test_menu_directo.py
```

### Resultado esperado:
```
✅ CASO 1 CUMPLIDO - DEBERÍA MOSTRAR MENÚ COMPLETO

Mensaje: 'Hola ... Ya estás dado de alta como cliente NetCash'
Botones:
- 🧾 Crear nueva operación NetCash
- 💳 Ver cuenta para depósitos
- 📂 Ver mis solicitudes
- ❓ Ayuda
```

---

## ❓ Si el Problema Persiste

### Opción 1: Verificar logs en tiempo real

```bash
# Ver logs del bot de Telegram
tail -f /var/log/telegram_bot.out.log

# En otro terminal, desde Telegram enviar: /start

# Buscar en los logs:
# - "[NetCash][START] Cliente activo -> menú"
# - "[MENU] ..." (warnings si hay casos borde)
```

### Opción 2: Verificar el estado en BD

```bash
cd /app/backend
python3 << 'EOF'
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def verificar():
    client = AsyncIOMotorClient(os.getenv('MONGO_URL'))
    db = client[os.getenv('DB_NAME', 'netcash_mbco')]
    
    usuario = await db.usuarios_telegram.find_one(
        {"telegram_id": "7631636750"},
        {"_id": 0, "rol": 1, "id_cliente": 1}
    )
    
    print(f"rol: {usuario.get('rol')}")
    print(f"id_cliente: {usuario.get('id_cliente')}")
    
    if usuario.get('id_cliente'):
        cliente = await db.clientes.find_one(
            {"id": usuario.get('id_cliente')},
            {"_id": 0, "estado": 1}
        )
        print(f"cliente.estado: {cliente.get('estado') if cliente else 'NO EXISTE'}")
    
    client.close()

asyncio.run(verificar())
EOF
```

### Opción 3: Reiniciar todos los servicios

```bash
sudo supervisorctl restart telegram_bot
sudo supervisorctl restart backend
```

---

## 📋 Checklist de Verificación

- [x] Usuario tiene `rol="cliente_activo"` en BD
- [x] Usuario tiene `id_cliente` asignado
- [x] Cliente existe en colección `clientes` con ese ID
- [x] Cliente tiene `estado="activo"`
- [x] Código actualizado en `telegram_bot.py`
- [x] Bot de Telegram reiniciado (PID 2368)
- [x] Test de lógica pasa correctamente

---

## ✅ Criterios de Aceptación

El bug está **COMPLETAMENTE CORREGIDO** cuando:

1. ✅ Al enviar `/start` en Telegram, aparece:
   - Mensaje: "Hola DFGV 😊 ... Ya estás dado de alta como cliente NetCash"
   - Botón: "🧾 Crear nueva operación NetCash"
   
2. ✅ Al hacer clic en "Crear nueva operación":
   - Inicia el flujo de creación
   - Pide subir comprobantes
   - NO muestra mensaje de "registro en revisión"

3. ✅ Test automatizado `test_menu_directo.py` muestra:
   - "✅ CASO 1 CUMPLIDO - DEBERÍA MOSTRAR MENÚ COMPLETO"

---

## 🔑 Notas Importantes

### Por qué el problema persistía:

1. **Backend vs Bot de Telegram:** Son procesos separados
   - Reiniciar `backend` NO reinicia `telegram_bot`
   - El bot necesita reiniciarse explícitamente

2. **Caché del código:** Python puede cachear módulos
   - Reinicio completo del proceso resuelve el problema

3. **Timing:** El bot tarda ~3-5 segundos en iniciar
   - Esperar a que el status sea "RUNNING"

### Prevención futura:

Cuando modifiques código del bot de Telegram:
```bash
sudo supervisorctl restart telegram_bot
sudo supervisorctl status telegram_bot
# Esperar a que muestre "RUNNING"
```

---

**El bot ahora está ejecutando el código actualizado. Por favor verifica en Telegram enviando `/start`.**
