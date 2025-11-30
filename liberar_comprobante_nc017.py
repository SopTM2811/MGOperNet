"""
Script para liberar comprobante JARDINERIA de la operación NC-000017

Problema: NC-000017 fue una prueba fallida que secuestró el hash del comprobante.
Solución: Marcar NC-000017 como "demo" o "cancelada" para que no bloquee duplicados.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone

async def liberar_comprobante():
    """Marca NC-000017 como operación cancelada/demo"""
    
    mongo_url = os.getenv('MONGO_URL')
    client = AsyncIOMotorClient(mongo_url)
    db = client['netcash_mbco']
    
    print('='*80)
    print('LIBERACIÓN DE COMPROBANTE: NC-000017')
    print('='*80)
    
    # 1. Verificar operación
    nc17 = await db.solicitudes_netcash.find_one(
        {'folio_mbco': 'NC-000017'},
        {'_id': 0, 'id': 1, 'folio_mbco': 1, 'estado': 1, 'comprobantes': 1}
    )
    
    if not nc17:
        print('❌ NC-000017 no encontrada')
        return
    
    print(f"\n📋 Operación actual:")
    print(f"   ID: {nc17.get('id')}")
    print(f"   Folio: {nc17.get('folio_mbco')}")
    print(f"   Estado: {nc17.get('estado')}")
    print(f"   Comprobantes: {len(nc17.get('comprobantes', []))}")
    
    # Buscar JARDINERIA
    hash_jardineria = None
    for comp in nc17.get('comprobantes', []):
        if 'JARDINERIA' in comp.get('nombre_archivo', ''):
            hash_jardineria = comp.get('archivo_hash')
            print(f"\n   Comprobante encontrado:")
            print(f"      Nombre: {comp.get('nombre_archivo')}")
            print(f"      Hash: {hash_jardineria[:16]}...")
            print(f"      Válido: {comp.get('es_valido')}")
    
    if not hash_jardineria:
        print('\n❌ Comprobante JARDINERIA no encontrado en NC-000017')
        return
    
    # 2. Marcar como "demo" o "cancelada"
    print(f"\n🔧 Cambios a realizar:")
    print(f"   1. Cambiar estado de 'lista_para_mbc' -> 'demo'")
    print(f"   2. Agregar nota en histórico")
    print(f"   3. El comprobante quedará liberado para uso futuro")
    
    confirmacion = input("\n¿Proceder con la liberación? (sí/no): ")
    
    if confirmacion.lower() not in ['si', 'sí', 's', 'yes', 'y']:
        print('\n❌ Operación cancelada por el usuario')
        return
    
    # Actualizar operación
    result = await db.solicitudes_netcash.update_one(
        {'folio_mbco': 'NC-000017'},
        {
            '$set': {
                'estado': 'demo',
                'updated_at': datetime.now(timezone.utc)
            },
            '$push': {
                'estado_historico': {
                    'estado': 'demo',
                    'en': datetime.now(timezone.utc),
                    'por': 'admin',
                    'notas': 'Operación marcada como demo/prueba. Comprobante liberado para reutilización.'
                }
            }
        }
    )
    
    if result.modified_count > 0:
        print('\n✅ Operación NC-000017 marcada como "demo"')
        print('✅ El comprobante JARDINERIA ahora puede reutilizarse')
        print('\n📝 Verificación:')
        print(f'   Hash liberado: {hash_jardineria}')
        print(f'   Estado nuevo: demo')
        print('\n⚠️ IMPORTANTE:')
        print('   Los estados "demo", "cancelada", "rechazada" NO bloquean duplicados')
        print('   Solo estados válidos ("lista_para_mbc", "en_proceso_mbc", "completada") los bloquean')
    else:
        print('\n❌ No se pudo actualizar la operación')

if __name__ == "__main__":
    asyncio.run(liberar_comprobante())
