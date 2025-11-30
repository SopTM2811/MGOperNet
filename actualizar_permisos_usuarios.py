"""
Script para actualizar permisos de usuarios existentes

Actualiza los permisos de Daniel (master) y Ana (admin_netcash)
para incluir puede_ver_usuarios y puede_usar_alta_telegram
"""

import asyncio
import sys
import os
sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient

async def actualizar_permisos():
    """Actualiza permisos de usuarios master y admin_netcash"""
    
    # Conectar a MongoDB
    mongo_url = os.getenv('MONGO_URL')
    db_name = 'netcash_mbco'
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("Actualizando permisos de usuarios...\n")
    
    # Actualizar Daniel (master)
    result_daniel = await db.usuarios_netcash.update_one(
        {"rol_negocio": "master"},
        {"$set": {
            "permisos.puede_ver_usuarios": True,
            "permisos.puede_usar_alta_telegram": True
        }}
    )
    
    if result_daniel.modified_count > 0:
        print("✅ Permisos de Daniel (master) actualizados:")
        print("   - puede_ver_usuarios: True")
        print("   - puede_usar_alta_telegram: True\n")
    else:
        print("⚠️ Daniel (master) no encontrado o ya tenía estos permisos\n")
    
    # Actualizar Ana (admin_netcash)
    result_ana = await db.usuarios_netcash.update_one(
        {"rol_negocio": "admin_netcash"},
        {"$set": {
            "permisos.puede_ver_usuarios": True,
            "permisos.puede_usar_alta_telegram": True
        }}
    )
    
    if result_ana.modified_count > 0:
        print("✅ Permisos de Ana (admin_netcash) actualizados:")
        print("   - puede_ver_usuarios: True")
        print("   - puede_usar_alta_telegram: True\n")
    else:
        print("⚠️ Ana (admin_netcash) no encontrada o ya tenía estos permisos\n")
    
    # Verificar cambios
    print("Verificando usuarios actualizados:\n")
    
    daniel = await db.usuarios_netcash.find_one({"rol_negocio": "master"}, {"_id": 0})
    if daniel:
        print("👤 Daniel (master):")
        print(f"   Permisos: {daniel.get('permisos', {})}\n")
    
    ana = await db.usuarios_netcash.find_one({"rol_negocio": "admin_netcash"}, {"_id": 0})
    if ana:
        print("👤 Ana (admin_netcash):")
        print(f"   Permisos: {ana.get('permisos', {})}\n")
    
    client.close()
    print("✅ Actualización completada")


if __name__ == "__main__":
    asyncio.run(actualizar_permisos())
