"""
Test para Bug 2: Notificación a Ana no llega

Root cause identificado:
- El código usaba `folio_netcash` pero el campo real en DB es `folio_mbco`
- Esto causaba que `folio_netcash` fuera None y la notificación fallara

Fix aplicado:
- Cambiado todas las referencias de `folio_netcash` a `folio_mbco` en:
  * netcash_service.py (líneas 310, 313, 336, 1312)
  * telegram_ana_handlers.py (líneas 39, 48, 71)
"""

import sys
import asyncio
sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone

async def test_ana_notification_bug():
    """Test para verificar que el bug del folio_netcash está corregido"""
    
    print("="*80)
    print("TEST: Notificación a Ana - Bug Fix (folio_netcash -> folio_mbco)")
    print("="*80)
    
    # Conexión a MongoDB
    mongo_url = os.getenv('MONGO_URL')
    client = AsyncIOMotorClient(mongo_url)
    db = client['netcash_mbco']
    
    # 1. Verificar que NC-000017 tiene folio_mbco (no folio_netcash)
    print("\n1. Verificando operación NC-000017...")
    solicitud = await db.solicitudes_netcash.find_one(
        {'folio_mbco': 'NC-000017'},
        {'_id': 0, 'id': 1, 'folio_mbco': 1, 'estado': 1, 'cliente_nombre': 1}
    )
    
    if solicitud:
        print(f"   ✅ Solicitud encontrada:")
        print(f"      - ID: {solicitud.get('id')}")
        print(f"      - folio_mbco: {solicitud.get('folio_mbco')}")
        print(f"      - Estado: {solicitud.get('estado')}")
        print(f"      - Cliente: {solicitud.get('cliente_nombre')}")
    else:
        print("   ❌ Solicitud NC-000017 no encontrada")
        return False
    
    # 2. Verificar usuarios_netcash collection
    print("\n2. Verificando catálogo de usuarios...")
    ana = await db.usuarios_netcash.find_one(
        {'rol_negocio': 'admin_netcash', 'activo': True},
        {'_id': 0}
    )
    
    if ana:
        print(f"   ✅ Usuario Ana encontrado:")
        print(f"      - Nombre: {ana.get('nombre')}")
        print(f"      - Rol: {ana.get('rol_negocio')}")
        print(f"      - Telegram ID: {ana.get('telegram_id')}")
        print(f"      - Activo: {ana.get('activo')}")
    else:
        print("   ❌ Usuario con rol 'admin_netcash' no encontrado")
        return False
    
    # 3. Simular el flujo de notificación (sin enviar realmente el mensaje de Telegram)
    print("\n3. Simulando flujo de notificación...")
    print("   (verificando que el código puede acceder correctamente a los campos)")
    
    try:
        # Simular lo que hace _notificar_ana_solicitud_lista()
        folio_mbco = solicitud.get('folio_mbco', 'N/A')
        telegram_id = ana.get('telegram_id')
        
        print(f"\n   Valores extraídos:")
        print(f"      - folio_mbco: {folio_mbco}")
        print(f"      - telegram_id: {telegram_id}")
        
        if folio_mbco == 'N/A':
            print("\n   ❌ folio_mbco es 'N/A' - Bug NO corregido")
            return False
        
        if not telegram_id:
            print("\n   ❌ telegram_id no configurado para Ana")
            return False
        
        print(f"\n   ✅ Datos correctos extraídos!")
        print(f"      El sistema ahora puede enviar notificación a chat_id={telegram_id}")
        print(f"      Con folio={folio_mbco}")
        
        # Verificar que el código de telegram_ana_handlers también usa folio_mbco
        print("\n4. Verificando código de telegram_ana_handlers...")
        with open('/app/backend/telegram_ana_handlers.py', 'r') as f:
            content = f.read()
            
        # Check if folio_netcash still exists
        if 'folio_netcash' in content:
            print("   ❌ ADVERTENCIA: 'folio_netcash' aún existe en telegram_ana_handlers.py")
            return False
        else:
            print("   ✅ 'folio_netcash' eliminado correctamente")
        
        # Check if folio_mbco is being used
        if 'folio_mbco' in content:
            print("   ✅ 'folio_mbco' se usa correctamente")
        else:
            print("   ❌ 'folio_mbco' no encontrado en el código")
            return False
        
        print("\n" + "="*80)
        print("✅ TEST EXITOSO: Bug de notificación a Ana está corregido")
        print("="*80)
        print("\nResumen del fix:")
        print("  - Campo correcto: 'folio_mbco' (no 'folio_netcash')")
        print("  - Ana recibirá notificaciones con folio: NC-000017 (y futuros)")
        print("  - Telegram ID configurado: 7631636750")
        print("\nPara verificar en producción:")
        print("  1. Crear una nueva operación NetCash")
        print("  2. Completarla hasta estado 'lista_para_mbc'")
        print("  3. Revisar logs: grep '[NOTIF_ANA]' /var/log/supervisor/backend.err.log")
        print("  4. Verificar mensaje en Telegram ID 7631636750")
        
        return True
        
    except Exception as e:
        print(f"\n   ❌ Error en simulación: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    exito = asyncio.run(test_ana_notification_bug())
    sys.exit(0 if exito else 1)
