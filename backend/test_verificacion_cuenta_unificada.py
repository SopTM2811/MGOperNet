"""
Script de verificación: Unificación de cuenta NetCash
Verifica que bot y web usen la misma fuente de verdad
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
import sys
sys.path.insert(0, '/app/backend')

from cuenta_deposito_service import cuenta_deposito_service
from netcash_service import netcash_service

async def verificar_unificacion():
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME', 'netcash_mbco')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("=" * 80)
    print("VERIFICACIÓN: Unificación de Cuenta NetCash (Web + Bot)")
    print("=" * 80)
    
    # 1. Cuenta en colección WEB
    print("\n1. CUENTA CONFIGURADA EN WEB (config_cuenta_deposito_netcash):\n")
    cuenta_web = await db.config_cuenta_deposito_netcash.find_one(
        {"activa": True},
        {"_id": 0}
    )
    
    if cuenta_web:
        print(f"   ✓ Cuenta activa encontrada:")
        print(f"     Banco: {cuenta_web.get('banco')}")
        print(f"     CLABE: {cuenta_web.get('clabe')}")
        print(f"     Beneficiario: {cuenta_web.get('beneficiario')}")
    else:
        print(f"   ✗ No hay cuenta activa")
    
    # 2. Cuenta que obtiene cuenta_deposito_service
    print("\n2. CUENTA QUE OBTIENE cuenta_deposito_service:\n")
    cuenta_servicio = await cuenta_deposito_service.obtener_cuenta_activa()
    
    if cuenta_servicio:
        print(f"   ✓ Cuenta obtenida:")
        print(f"     Banco: {cuenta_servicio.get('banco')}")
        print(f"     CLABE: {cuenta_servicio.get('clabe')}")
        print(f"     Beneficiario: {cuenta_servicio.get('beneficiario')}")
    else:
        print(f"   ✗ Servicio no devolvió cuenta")
    
    # 3. Cuenta en colección ANTIGUA (debe ser ignorada ahora)
    print("\n3. CUENTA EN COLECCIÓN ANTIGUA (config_cuentas_netcash - IGNORADA):\n")
    cuenta_antigua = await db.config_cuentas_netcash.find_one(
        {"tipo": "concertadora", "activa": True},
        {"_id": 0}
    )
    
    if cuenta_antigua:
        print(f"   ⚠️  Cuenta antigua (ya NO se usa):")
        print(f"     Banco: {cuenta_antigua.get('banco')}")
        print(f"     CLABE: {cuenta_antigua.get('clabe')}")
        print(f"     Beneficiario: {cuenta_antigua.get('beneficiario')}")
    else:
        print(f"   (vacía)")
    
    # VERIFICACIÓN
    print("\n" + "=" * 80)
    print("VERIFICACIÓN:")
    print("=" * 80)
    
    todo_correcto = True
    
    if not cuenta_web:
        print(f"\n   ❌ No hay cuenta configurada en la web")
        print(f"      Solución: Usar interfaz web para configurar cuenta")
        todo_correcto = False
    
    if not cuenta_servicio:
        print(f"\n   ❌ cuenta_deposito_service no devuelve cuenta")
        todo_correcto = False
    
    if cuenta_web and cuenta_servicio:
        if cuenta_web.get('clabe') == cuenta_servicio.get('clabe'):
            print(f"\n   ✅ Servicio devuelve la misma cuenta que la web")
        else:
            print(f"\n   ❌ DESFASE: Servicio devuelve cuenta diferente")
            todo_correcto = False
    
    # Comparar con antigua
    if cuenta_antigua and cuenta_servicio:
        if cuenta_antigua.get('clabe') == cuenta_servicio.get('clabe'):
            print(f"   ⚠️  Servicio aún usa colección antigua")
            todo_correcto = False
        else:
            print(f"   ✅ Servicio usa colección NUEVA (correcta)")
    
    # RESUMEN FINAL
    print("\n" + "=" * 80)
    print("RESUMEN FINAL:")
    print("=" * 80)
    
    if todo_correcto and cuenta_web and cuenta_servicio:
        print(f"\n   🎉 TODO CORRECTO")
        print(f"\n   La cuenta NetCash que verá el bot de Telegram es:")
        print(f"     Banco: {cuenta_servicio.get('banco')}")
        print(f"     CLABE: {cuenta_servicio.get('clabe')}")
        print(f"     Beneficiario: {cuenta_servicio.get('beneficiario')}")
        print(f"\n   Esta es la MISMA cuenta que muestra la web.")
        print(f"   Los comprobantes serán validados contra esta cuenta.")
    else:
        print(f"\n   ⚠️  HAY PROBLEMAS - Ver detalles arriba")
    
    print("\n" + "=" * 80)
    
    client.close()
    
    return todo_correcto

if __name__ == "__main__":
    resultado = asyncio.run(verificar_unificacion())
    exit(0 if resultado else 1)
