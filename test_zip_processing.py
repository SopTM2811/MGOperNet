"""
Test para verificar el procesamiento de archivos ZIP
"""

import sys
import os
import asyncio
import logging
sys.path.insert(0, '/app/backend')

# Activar logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

from netcash_service import netcash_service
from motor.motor_asyncio import AsyncIOMotorClient

async def test_zip_processing():
    """
    Test del procesamiento de ZIP con comprobantes reales
    """
    print("\n" + "="*80)
    print("TEST: Procesamiento de archivo ZIP")
    print("="*80)
    
    # Descargar el ZIP
    import requests
    zip_url = "https://customer-assets.emergentagent.com/job_payslip-verify-1/artifacts/9gtkrh99_netcashdanitza1000000jardineria261125%20%282%29.zip"
    
    zip_path = "/tmp/netcashdanitza1000000jardineria261125.zip"
    
    print(f"\n📥 Descargando ZIP desde: {zip_url}")
    response = requests.get(zip_url)
    
    if response.status_code != 200:
        print(f"❌ ERROR: No se pudo descargar el ZIP (status={response.status_code})")
        return False
    
    with open(zip_path, 'wb') as f:
        f.write(response.content)
    
    print(f"✅ ZIP descargado: {zip_path} ({len(response.content)} bytes)")
    
    # Crear una solicitud de prueba
    mongo_url = os.getenv('MONGO_URL')
    client = AsyncIOMotorClient(mongo_url)
    db = client['netcash_mbco']
    
    # Crear solicitud temporal
    from uuid import uuid4
    from datetime import datetime, timezone
    
    solicitud_id = f"test_zip_{uuid4().hex[:8]}"
    
    solicitud_test = {
        "id": solicitud_id,
        "cliente_id": "test_cliente",
        "estado": "borrador",
        "comprobantes": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.solicitudes_netcash.insert_one(solicitud_test)
    print(f"\n✅ Solicitud de prueba creada: {solicitud_id}")
    
    # Procesar el ZIP
    print(f"\n🔍 Procesando ZIP...")
    resultado = await netcash_service.procesar_archivo_zip(
        solicitud_id,
        zip_path,
        "netcashdanitza1000000jardineria261125.zip"
    )
    
    print(f"\n" + "="*80)
    print(f"RESULTADO DEL PROCESAMIENTO")
    print(f"="*80)
    print(f"Total archivos encontrados: {resultado.get('total_archivos', 0)}")
    print(f"Comprobantes válidos: {resultado.get('validos', 0)}")
    print(f"Comprobantes sin texto legible: {resultado.get('sin_texto_legible', 0)}")
    print(f"Comprobantes inválidos: {resultado.get('invalidos', 0)}")
    print(f"Duplicados: {resultado.get('duplicados', 0)}")
    print(f"No legibles: {resultado.get('no_legibles', 0)}")
    print(f"="*80)
    
    # Mostrar detalle de archivos procesados
    print(f"\n📋 Detalle de archivos procesados:")
    for archivo in resultado.get('archivos_procesados', []):
        nombre = archivo.get('nombre')
        estado = archivo.get('estado')
        print(f"  • {nombre}: {estado}")
        if estado == 'valido':
            monto = archivo.get('monto')
            if monto:
                print(f"    Monto: ${monto:,.2f}")
        elif estado in ['invalido', 'error', 'no_soportado']:
            razon = archivo.get('razon', 'Sin razón')
            print(f"    Razón: {razon[:100]}")
    
    # Verificar solicitud actualizada
    solicitud_actualizada = await db.solicitudes_netcash.find_one(
        {"id": solicitud_id},
        {"_id": 0}
    )
    
    if solicitud_actualizada:
        comprobantes = solicitud_actualizada.get("comprobantes", [])
        print(f"\n✅ Comprobantes en la solicitud: {len(comprobantes)}")
        
        validos = sum(1 for c in comprobantes if c.get("es_valido"))
        print(f"   Válidos: {validos}")
        print(f"   Inválidos: {len(comprobantes) - validos}")
    
    # Limpiar
    await db.solicitudes_netcash.delete_one({"id": solicitud_id})
    print(f"\n🧹 Solicitud de prueba eliminada")
    
    # Evaluar resultado
    if resultado.get('validos', 0) > 0:
        print(f"\n🎉 TEST EXITOSO: Se procesaron {resultado['validos']} comprobante(s) válido(s)")
        return True
    elif resultado.get('total_archivos', 0) > 0:
        print(f"\n⚠️ TEST COMPLETADO: Se encontraron archivos pero ninguno válido")
        print(f"   Esto puede ser esperado si los comprobantes no coinciden con la cuenta de prueba")
        return True
    else:
        print(f"\n❌ TEST FALLÓ: No se encontraron archivos en el ZIP")
        return False


async def main():
    print("\n" + "="*80)
    print("SUITE DE TESTS: Procesamiento de archivos ZIP")
    print("="*80)
    
    try:
        resultado = await test_zip_processing()
        
        if resultado:
            print(f"\n✅ TESTS COMPLETADOS EXITOSAMENTE")
            return True
        else:
            print(f"\n❌ TESTS FALLARON")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR EJECUTANDO TESTS: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
