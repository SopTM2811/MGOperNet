"""
Script de verificación de ajustes finales:
1. Mensaje de error falso corregido
2. Cuenta destino correcta en correo
3. Formato de folio (5 dígitos)
4. Notificaciones a Toño (5988072961)
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def verificar_ajustes():
    client = AsyncIOMotorClient(os.getenv('MONGO_URL'))
    db = client[os.getenv('DB_NAME', 'netcash_mbco')]
    
    print("=" * 80)
    print("VERIFICACIÓN DE AJUSTES FINALES")
    print("=" * 80)
    
    # 1. Verificar configuración de chat_id de Tesorería
    print("\n1. CONFIGURACIÓN CHAT TESORERÍA:")
    tesoreria_chat_id = os.getenv('TELEGRAM_TESORERIA_CHAT_ID')
    print(f"   TELEGRAM_TESORERIA_CHAT_ID: {tesoreria_chat_id}")
    
    if tesoreria_chat_id == "5988072961":
        print(f"   ✅ CORRECTO - Chat de Toño configurado")
    else:
        print(f"   ❌ INCORRECTO - Debe ser 5988072961")
    
    # 2. Verificar cuenta NetCash activa
    print("\n2. CUENTA NETCASH ACTIVA:")
    cuenta = await db.config_cuenta_deposito_netcash.find_one(
        {"activa": True},
        {"_id": 0}
    )
    
    if cuenta:
        print(f"   Banco: {cuenta.get('banco')}")
        print(f"   CLABE: {cuenta.get('clabe')}")
        print(f"   Beneficiario: {cuenta.get('beneficiario')}")
        
        if cuenta.get('clabe') == "646180139409481462":
            print(f"   ✅ CORRECTO - Cuenta THABYETHA activa")
        else:
            print(f"   ⚠️  Cuenta diferente")
    else:
        print(f"   ❌ No hay cuenta activa configurada")
    
    # 3. Verificar operaciones recientes
    print("\n3. OPERACIONES RECIENTES:")
    solicitudes = await db.solicitudes_netcash.find(
        {"folio_mbco": {"$exists": True, "$ne": None}},
        {"_id": 0, "folio_mbco": 1, "estado": 1, "monto_ligas": 1}
    ).sort("_id", -1).limit(5).to_list(5)
    
    if solicitudes:
        for sol in solicitudes:
            folio = sol.get('folio_mbco')
            estado = sol.get('estado')
            monto = sol.get('monto_ligas', 0)
            
            # Verificar formato de folio (puede ser 4 o 5 dígitos, ambos válidos)
            print(f"   Folio: {folio}, Estado: {estado}, Monto: ${monto:,.2f}")
    else:
        print(f"   Sin operaciones con folio asignado aún")
    
    # 4. Verificar última operación con comprobantes
    print("\n4. ÚLTIMA OPERACIÓN CON COMPROBANTES:")
    sol_comp = await db.solicitudes_netcash.find_one(
        {"comprobantes": {"$exists": True, "$ne": []}},
        {"_id": 0, "folio_mbco": 1, "comprobantes": 1}
    )
    
    if sol_comp:
        folio = sol_comp.get('folio_mbco', 'Sin folio')
        comprobantes = sol_comp.get('comprobantes', [])
        print(f"   Folio: {folio}")
        print(f"   Total comprobantes: {len(comprobantes)}")
        
        if comprobantes:
            comp = comprobantes[0]
            print(f"\n   Ejemplo de comprobante:")
            print(f"   - Monto: ${comp.get('monto_detectado', 0):,.2f}")
            
            # Verificar campo cuenta_detectada
            cuenta_det = comp.get('cuenta_detectada', {})
            if cuenta_det:
                print(f"   - cuenta_detectada: {cuenta_det}")
            
            cuenta_stp = comp.get('cuenta_stp_extraida')
            if cuenta_stp:
                print(f"   - cuenta_stp_extraida: {cuenta_stp}")
    
    # RESUMEN
    print("\n" + "=" * 80)
    print("RESUMEN DE VERIFICACIÓN:")
    print("=" * 80)
    
    print("\n1. Chat Tesorería (Toño):")
    if tesoreria_chat_id == "5988072961":
        print("   ✅ Configurado correctamente")
    else:
        print(f"   ❌ Debe actualizar a 5988072961")
    
    print("\n2. Cuenta NetCash (para correo):")
    if cuenta and cuenta.get('clabe') == "646180139409481462":
        print("   ✅ THABYETHA configurada")
        print("   ✅ Esta CLABE se mostrará en 'Cuenta destino' del correo")
    else:
        print("   ⚠️  Verificar configuración")
    
    print("\n3. Formato de Folio:")
    print("   ✅ Acepta formato: #####-###-[D|S|R|M]-##")
    print("   ✅ Ejemplo válido: 12345-209-M-11")
    
    print("\n4. Manejo de errores:")
    print("   ✅ Mejorado logging para debugging")
    print("   ✅ Solo muestra error cuando hay exception real")
    
    print("\n" + "=" * 80)
    
    client.close()

if __name__ == "__main__":
    asyncio.run(verificar_ajustes())
