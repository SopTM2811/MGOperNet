"""
Test para enviar notificación directa a Ana
Este script prueba que el sistema puede enviar mensajes a Ana correctamente
"""

import sys
import asyncio
sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
import os

async def test_notificacion_ana():
    """Prueba enviar notificación a Ana usando el handler real"""
    
    print("="*80)
    print("TEST: Notificación Directa a Ana")
    print("="*80)
    
    mongo_url = os.getenv('MONGO_URL')
    client = AsyncIOMotorClient(mongo_url)
    db = client['netcash_mbco']
    
    # 1. Verificar usuario Ana
    print("\n1️⃣ Verificando usuario Ana en catálogo...")
    ana = await db.usuarios_netcash.find_one(
        {'rol_negocio': 'admin_netcash'},
        {'_id': 0}
    )
    
    if not ana:
        print("❌ Usuario Ana NO encontrado")
        return False
    
    print(f"✅ Usuario Ana encontrado:")
    print(f"   Nombre: {ana.get('nombre')}")
    print(f"   Telegram ID: {ana.get('telegram_id')}")
    print(f"   Activo: {ana.get('activo')}")
    
    # 2. Obtener solicitud NC-000019 para usar de ejemplo
    print("\n2️⃣ Obteniendo solicitud NC-000019...")
    solicitud = await db.solicitudes_netcash.find_one(
        {'folio_mbco': 'NC-000019'},
        {'_id': 0}
    )
    
    if not solicitud:
        print("❌ NC-000019 no encontrada")
        return False
    
    print(f"✅ Solicitud encontrada:")
    print(f"   Folio: {solicitud.get('folio_mbco')}")
    print(f"   Estado: {solicitud.get('estado')}")
    
    # 3. Llamar directamente al handler
    print("\n3️⃣ Llamando a notificación de Ana...")
    
    from netcash_service import netcash_service
    
    try:
        await netcash_service._notificar_ana_solicitud_lista(solicitud)
        print("✅ Notificación enviada (revisar logs y Telegram de Ana)")
        
    except Exception as e:
        print(f"❌ Error al enviar notificación: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # 4. Verificar logs
    print("\n4️⃣ Verificando logs...")
    print("   Revisar: tail -n 50 /var/log/telegram_bot.log | grep 'Ana Telegram'")
    
    print("\n" + "="*80)
    print("📋 RESUMEN")
    print("="*80)
    print("\n✅ Notificación enviada al handler")
    print("\n📝 Próximos pasos:")
    print("   1. Revisar Telegram de Ana (ID: 7631636750)")
    print("   2. Verificar logs: tail -n 50 /var/log/telegram_bot.log")
    print("   3. Si el mensaje llegó, el bug está RESUELTO ✅")
    print("   4. Si NO llegó, revisar permisos del bot en Telegram")
    
    return True

if __name__ == "__main__":
    exito = asyncio.run(test_notificacion_ana())
    sys.exit(0 if exito else 1)
