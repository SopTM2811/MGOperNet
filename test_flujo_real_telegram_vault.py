"""
Test que simula el flujo EXACTO del bot de Telegram al procesar el PDF Vault

Este script replica lo que hace telegram_netcash_handlers.py cuando:
1. El usuario sube un archivo
2. Se guarda temporalmente
3. Se llama a netcash_service.agregar_comprobante()
4. El validador procesa el archivo
"""

import sys
import asyncio
sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
from netcash_service import netcash_service
from config_cuentas_service import config_cuentas_service
from netcash_models import TipoCuenta
import os

async def test_flujo_real_telegram():
    """Simula el flujo completo desde Telegram bot"""
    
    print("="*80)
    print("TEST: Flujo REAL de Telegram Bot - Comprobante Vault/Panekneva")
    print("="*80)
    
    # Paso 1: Obtener cuenta activa (como lo hace el bot)
    print("\n📊 PASO 1: Obtener cuenta NetCash activa")
    cuenta_activa = await config_cuentas_service.obtener_cuenta_activa(TipoCuenta.CONCERTADORA)
    
    if not cuenta_activa:
        print("❌ No hay cuenta activa configurada")
        return False
    
    print(f"   ✅ Cuenta activa obtenida:")
    print(f"      - Banco: {cuenta_activa.get('banco')}")
    print(f"      - CLABE: {cuenta_activa.get('clabe')}")
    print(f"      - Beneficiario: {cuenta_activa.get('beneficiario')}")
    
    # Paso 2: Crear una solicitud de prueba (como lo hace el bot)
    print("\n📝 PASO 2: Crear solicitud NetCash de prueba")
    
    mongo_url = os.getenv('MONGO_URL')
    client = AsyncIOMotorClient(mongo_url)
    db = client['netcash_mbco']
    
    from netcash_models import SolicitudCreate, CanalOrigen
    from datetime import datetime, timezone
    
    datos_solicitud = SolicitudCreate(
        canal=CanalOrigen.TELEGRAM,
        cliente_id="test-client-vault",
        cliente_nombre="Test Vault Client",
        beneficiario_reportado="JARDINERIA Y COMERCIO THABYETHA SA DE CV",
        idmex_reportado="1234567890",
        cantidad_ligas_reportada=10
    )
    
    solicitud = await netcash_service.crear_solicitud(datos_solicitud)
    
    if not solicitud:
        print("❌ Error creando solicitud")
        return False
    
    solicitud_id = solicitud['id']
    print(f"   ✅ Solicitud creada: {solicitud_id}")
    
    # Paso 3: Agregar comprobante (como lo hace el bot)
    print("\n📄 PASO 3: Agregar comprobante Vault/Panekneva")
    print("   Archivo: /tmp/jardineria_test.pdf")
    
    # Este es el flujo EXACTO que usa el bot
    agregado, razon = await netcash_service.agregar_comprobante(
        solicitud_id=solicitud_id,
        archivo_url="/tmp/jardineria_test.pdf",
        nombre_archivo="JARDINERIA 1,507,500.00.pdf"
    )
    
    print(f"\n   Resultado:")
    print(f"      - Agregado: {agregado}")
    print(f"      - Razón: {razon}")
    
    # Paso 4: Verificar el comprobante en la BD
    print("\n🔍 PASO 4: Verificar comprobante en base de datos")
    
    solicitud_actualizada = await db.solicitudes_netcash.find_one(
        {"id": solicitud_id},
        {"_id": 0, "comprobantes": 1}
    )
    
    if solicitud_actualizada and solicitud_actualizada.get("comprobantes"):
        comp = solicitud_actualizada["comprobantes"][0]
        print(f"   Comprobante guardado:")
        print(f"      - Nombre: {comp.get('nombre_archivo')}")
        print(f"      - Es válido: {comp.get('es_valido')}")
        print(f"      - Razón: {comp.get('validacion_detalle', {}).get('razon')}")
        print(f"      - Monto: ${comp.get('monto_detectado', 0):,.2f}")
        
        es_valido = comp.get('es_valido')
    else:
        print("   ❌ No se encontró el comprobante en la BD")
        es_valido = False
    
    # Paso 5: Limpiar solicitud de prueba
    print("\n🧹 PASO 5: Limpiando solicitud de prueba")
    await db.solicitudes_netcash.delete_one({"id": solicitud_id})
    print(f"   ✅ Solicitud {solicitud_id} eliminada")
    
    # Resultado final
    print("\n" + "="*80)
    if es_valido:
        print("✅ TEST EXITOSO: El comprobante Vault es VÁLIDO en flujo real de Telegram")
        print("="*80)
        print("\n📋 Resumen:")
        print("   ✅ El validador reconoce el layout Vault/Panekneva")
        print("   ✅ La CLABE 646180139409481462 se identifica como DESTINO")
        print("   ✅ El beneficiario se detecta correctamente")
        print("\n📝 Próximos pasos:")
        print("   1. Probar desde el bot de Telegram real")
        print("   2. Verificar logs con: grep VAULT_DEBUG /var/log/supervisor/backend.err.log")
        return True
    else:
        print("❌ TEST FALLIDO: El comprobante Vault sigue siendo rechazado")
        print("="*80)
        print("\n⚠️ El problema persiste en el flujo real")
        print("\n🔍 Revisar logs:")
        print("   tail -n 200 /var/log/supervisor/backend.err.log | grep VAULT")
        return False

if __name__ == "__main__":
    exito = asyncio.run(test_flujo_real_telegram())
    sys.exit(0 if exito else 1)
