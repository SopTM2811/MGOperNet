"""
Script de verificación completa para usuario telegram_id: 1570668456
Valida que el comportamiento sea consistente y siempre muestre menú de cliente activo
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
import sys
sys.path.insert(0, '/app/backend')

from telegram_bot import TelegramBotNetCash

async def test_verificacion_completa():
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME', 'netcash_mbco')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    telegram_id = "1570668456"
    
    print("=" * 80)
    print(f"VERIFICACIÓN COMPLETA - Usuario telegram_id: {telegram_id}")
    print("=" * 80)
    
    # 1. Estado en BD
    print("\n1. ESTADO EN BASE DE DATOS\n")
    
    usuario = await db.usuarios_telegram.find_one(
        {"telegram_id": telegram_id},
        {"_id": 0}
    )
    
    if usuario:
        print(f"   ✓ Usuario encontrado:")
        print(f"     nombre: {usuario.get('nombre')}")
        print(f"     rol: {usuario.get('rol')}")
        print(f"     id_cliente: {usuario.get('id_cliente')}")
        
        id_cliente = usuario.get('id_cliente')
        if id_cliente:
            cliente = await db.clientes.find_one(
                {"id": id_cliente},
                {"_id": 0}
            )
            
            if cliente:
                print(f"\n   ✓ Cliente encontrado:")
                print(f"     id: {cliente.get('id')}")
                print(f"     nombre: {cliente.get('nombre')}")
                print(f"     estado: {cliente.get('estado')}")
            else:
                print(f"\n   ✗ Cliente NO encontrado (id: {id_cliente})")
    else:
        print(f"   ✗ Usuario NO encontrado")
    
    # 2. Test de función es_cliente_activo
    print("\n" + "=" * 80)
    print("2. TEST DE FUNCIÓN es_cliente_activo()")
    print("=" * 80)
    
    bot = TelegramBotNetCash()
    es_activo, usuario_ret, cliente_ret = await bot.es_cliente_activo(telegram_id)
    
    print(f"\n   Resultado: es_activo = {es_activo}")
    if usuario_ret:
        print(f"   Usuario retornado: {usuario_ret.get('nombre')}, rol={usuario_ret.get('rol')}")
    if cliente_ret:
        print(f"   Cliente retornado: {cliente_ret.get('nombre')}, estado={cliente_ret.get('estado')}")
    
    # 3. Simular lógica de mostrar_menu_principal
    print("\n" + "=" * 80)
    print("3. SIMULACIÓN DE LÓGICA DEL MENÚ /start")
    print("=" * 80)
    
    if usuario:
        rol = usuario.get("rol", "desconocido")
        id_cliente = usuario.get("id_cliente")
        
        print(f"\n   Evaluando condiciones:")
        print(f"     rol: {rol}")
        print(f"     id_cliente: {id_cliente}")
        
        if id_cliente or rol in ["cliente", "cliente_activo"]:
            print(f"\n   ✓ Entra al bloque de cliente")
            
            cliente = None
            if id_cliente:
                cliente = await db.clientes.find_one({"id": id_cliente}, {"_id": 0})
            
            # CASO 1
            if cliente and cliente.get("estado") == "activo":
                print(f"\n   ✅ CASO 1: Cliente existe y está activo")
                print(f"      RESULTADO: Menú completo con 'Crear nueva operación'")
            # CASO 2
            elif rol == "cliente_activo" and not cliente:
                print(f"\n   ✅ CASO 2: Rol activo sin cliente en BD")
                print(f"      RESULTADO: Menú completo (caso borde manejado)")
            # CASO 3
            else:
                print(f"\n   ❌ CASO 3: Usuario pendiente")
                print(f"      RESULTADO: Mensaje 'Tu registro está en revisión'")
        else:
            print(f"\n   ✗ NO entra al bloque de cliente")
    
    # 4. Test de crear operación
    print("\n" + "=" * 80)
    print("4. TEST DE CREAR OPERACIÓN (función es_cliente_activo)")
    print("=" * 80)
    
    if es_activo:
        print(f"\n   ✅ Usuario PUEDE crear operaciones")
        print(f"      Flujo: Hacer clic en 'Crear nueva operación' → Solicita comprobantes")
    else:
        print(f"\n   ❌ Usuario NO PUEDE crear operaciones")
        print(f"      Mensaje mostrado: 'Para crear una operación NetCash primero necesitas estar dado de alta'")
    
    # Resumen final
    print("\n" + "=" * 80)
    print("RESUMEN FINAL")
    print("=" * 80)
    
    todo_correcto = True
    
    if not usuario or usuario.get('rol') != 'cliente_activo':
        print(f"\n   ❌ Usuario no tiene rol cliente_activo")
        todo_correcto = False
    else:
        print(f"\n   ✅ Usuario tiene rol cliente_activo")
    
    if not es_activo:
        print(f"   ❌ Función es_cliente_activo() retorna False")
        todo_correcto = False
    else:
        print(f"   ✅ Función es_cliente_activo() retorna True")
    
    if todo_correcto:
        print(f"\n   🎉 TODO CORRECTO")
        print(f"\n   El usuario debería ver SIEMPRE:")
        print(f"   - Menú completo con 'Crear nueva operación NetCash'")
        print(f"   - Poder crear operaciones sin mensaje de 'contacta a Ana'")
    else:
        print(f"\n   ⚠️  HAY PROBLEMAS QUE CORREGIR")
    
    print("\n" + "=" * 80)
    
    client.close()
    
    return todo_correcto

if __name__ == "__main__":
    resultado = asyncio.run(test_verificacion_completa())
    exit(0 if resultado else 1)
