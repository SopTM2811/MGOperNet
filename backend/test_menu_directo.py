"""
Script para probar directamente la lógica del menú de /start
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
import sys
sys.path.insert(0, '/app/backend')

async def test_menu_logica():
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME', 'netcash_mbco')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    telegram_id = "7631636750"
    
    print("=" * 80)
    print("TEST DE LÓGICA DEL MENÚ - Simulación del código real")
    print("=" * 80)
    
    # Obtener usuario (como lo hace el código en start())
    usuario = await db.usuarios_telegram.find_one({"telegram_id": telegram_id}, {"_id": 0})
    
    if not usuario:
        print("\n❌ Usuario no encontrado")
        client.close()
        return
    
    print(f"\n1. Usuario encontrado:")
    print(f"   rol: {usuario.get('rol')}")
    print(f"   id_cliente: {usuario.get('id_cliente')}")
    
    # Simular la lógica de mostrar_menu_principal()
    rol = usuario.get("rol", "desconocido")
    id_cliente = usuario.get("id_cliente")
    
    print(f"\n2. Evaluando condición principal:")
    print(f"   id_cliente: {id_cliente}")
    print(f"   rol: {rol}")
    print(f"   Condición: id_cliente or rol in ['cliente', 'cliente_activo']")
    
    if id_cliente or rol in ["cliente", "cliente_activo"]:
        print(f"   ✓ Condición cumplida - Entrando al bloque de cliente")
        
        # Buscar cliente
        cliente = None
        if id_cliente:
            cliente = await db.clientes.find_one({"id": id_cliente}, {"_id": 0})
            print(f"\n3. Buscando cliente en BD:")
            if cliente:
                print(f"   ✓ Cliente encontrado:")
                print(f"     id: {cliente.get('id')}")
                print(f"     estado: {cliente.get('estado')}")
            else:
                print(f"   ✗ Cliente NO encontrado")
        
        # Evaluar CASO 1
        print(f"\n4. Evaluando CASO 1:")
        print(f"   Condición: cliente and cliente.get('estado') == 'activo'")
        print(f"   cliente: {cliente is not None}")
        if cliente:
            print(f"   cliente['estado']: {cliente.get('estado')}")
        
        if cliente and cliente.get("estado") == "activo":
            print(f"   ✅ CASO 1 CUMPLIDO - DEBERÍA MOSTRAR MENÚ COMPLETO")
            print(f"\n   Mensaje: 'Hola ... Ya estás dado de alta como cliente NetCash'")
            print(f"   Botones:")
            print(f"   - 🧾 Crear nueva operación NetCash")
            print(f"   - 💳 Ver cuenta para depósitos")
            print(f"   - 📂 Ver mis solicitudes")
            print(f"   - ❓ Ayuda")
        # Evaluar CASO 2
        elif rol == "cliente_activo" and not cliente:
            print(f"   ✅ CASO 2 CUMPLIDO - MENÚ COMPLETO (sin cliente en BD)")
            print(f"\n   Mensaje: 'Hola ... Ya estás dado de alta como cliente NetCash'")
            print(f"   Botones: (iguales al CASO 1)")
        # CASO 3
        else:
            print(f"   ❌ CASO 3 - MUESTRA 'REGISTRO EN REVISIÓN'")
            print(f"\n   Mensaje: 'Tu registro está en revisión por Ana'")
            print(f"   Botones:")
            print(f"   - 📊 Ver mis operaciones")
            print(f"   - ❓ Ayuda")
    else:
        print(f"   ✗ Condición NO cumplida - Usuario no es cliente")
    
    print("\n" + "=" * 80)
    client.close()

if __name__ == "__main__":
    asyncio.run(test_menu_logica())
