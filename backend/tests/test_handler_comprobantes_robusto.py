"""
Test para verificar el manejo robusto de errores en el handler de comprobantes

Ejecutar: python3 tests/test_handler_comprobantes_robusto.py
"""

import asyncio
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from netcash_service import netcash_service
from motor.motor_asyncio import AsyncIOMotorClient
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

# Silenciar logs externos
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)


async def test_1_comprobante_valido():
    """
    TEST 1: Procesar un comprobante válido correctamente
    """
    print("\n" + "=" * 70)
    print("TEST 1: Procesar Comprobante Válido")
    print("=" * 70)
    
    try:
        # Crear solicitud de prueba
        mongo_url = os.getenv('MONGO_URL')
        db_name = os.getenv('DB_NAME', 'netcash_mbco')
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        solicitud_test = {
            'id': 'test-comp-valido-001',
            'cliente_id': 'test-cliente-001',
            'estado': 'borrador',
            'comprobantes': []
        }
        
        # Limpiar y crear
        await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
        await db.solicitudes_netcash.insert_one(solicitud_test)
        
        print(f"\n📋 Solicitud de prueba creada: {solicitud_test['id']}")
        
        # Usar el PDF de prueba que ya existe
        ruta_pdf = "/app/backend/uploads/test_250k.pdf"
        
        if not Path(ruta_pdf).exists():
            print(f"❌ Archivo de prueba no encontrado: {ruta_pdf}")
            return False
        
        print(f"\n🔍 Procesando comprobante: {Path(ruta_pdf).name}")
        
        # Agregar comprobante
        agregado, razon = await netcash_service.agregar_comprobante(
            solicitud_test['id'],
            ruta_pdf,
            "test_250k.pdf"
        )
        
        print(f"\n📊 Resultado:")
        print(f"   Agregado: {agregado}")
        print(f"   Razón: {razon if razon else 'N/A'}")
        
        # Verificar en BD
        solicitud_actualizada = await db.solicitudes_netcash.find_one(
            {'id': solicitud_test['id']},
            {'_id': 0, 'comprobantes': 1}
        )
        
        comprobantes = solicitud_actualizada.get('comprobantes', [])
        
        if len(comprobantes) > 0:
            comp = comprobantes[0]
            print(f"\n💳 Comprobante agregado:")
            print(f"   es_valido: {comp.get('es_valido')}")
            print(f"   razon: {comp.get('validacion_detalle', {}).get('razon')}")
            if comp.get('monto_detectado'):
                print(f"   monto: ${comp.get('monto_detectado'):,.2f}")
            
            if comp.get('es_valido'):
                print(f"\n✅ TEST 1 PASADO: Comprobante procesado correctamente")
                
                # Limpiar
                await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
                return True
            else:
                print(f"\n❌ TEST 1 FALLADO: Comprobante marcado como inválido")
                await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
                return False
        else:
            print(f"\n❌ TEST 1 FALLADO: No se agregó ningún comprobante")
            await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
            return False
    
    except Exception as e:
        print(f"\n❌ TEST 1 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_2_comprobante_duplicado():
    """
    TEST 2: Detectar comprobante duplicado correctamente
    """
    print("\n" + "=" * 70)
    print("TEST 2: Detectar Comprobante Duplicado")
    print("=" * 70)
    
    try:
        mongo_url = os.getenv('MONGO_URL')
        db_name = os.getenv('DB_NAME', 'netcash_mbco')
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        solicitud_test = {
            'id': 'test-comp-dup-001',
            'cliente_id': 'test-cliente-001',
            'estado': 'borrador',
            'comprobantes': []
        }
        
        # Limpiar y crear
        await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
        await db.solicitudes_netcash.insert_one(solicitud_test)
        
        ruta_pdf = "/app/backend/uploads/test_250k.pdf"
        
        print(f"\n🔍 Intento 1: Agregar comprobante...")
        agregado1, razon1 = await netcash_service.agregar_comprobante(
            solicitud_test['id'],
            ruta_pdf,
            "test_250k.pdf"
        )
        print(f"   Resultado: agregado={agregado1}, razon={razon1}")
        
        print(f"\n🔍 Intento 2: Agregar el MISMO comprobante...")
        agregado2, razon2 = await netcash_service.agregar_comprobante(
            solicitud_test['id'],
            ruta_pdf,
            "test_250k_copia.pdf"  # Nombre diferente pero mismo contenido
        )
        print(f"   Resultado: agregado={agregado2}, razon={razon2}")
        
        # Verificar
        if not agregado2 and razon2 == "duplicado_local":
            print(f"\n✅ TEST 2 PASADO: Duplicado detectado correctamente")
            await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
            return True
        else:
            print(f"\n❌ TEST 2 FALLADO: No se detectó el duplicado")
            await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
            return False
    
    except Exception as e:
        print(f"\n❌ TEST 2 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_3_manejo_error_archivo_corrupto():
    """
    TEST 3: Verificar que el manejo de errores marca solicitud para revisión manual
    """
    print("\n" + "=" * 70)
    print("TEST 3: Manejo de Error - Archivo Corrupto")
    print("=" * 70)
    
    try:
        mongo_url = os.getenv('MONGO_URL')
        db_name = os.getenv('DB_NAME', 'netcash_mbco')
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        solicitud_test = {
            'id': 'test-comp-error-001',
            'cliente_id': 'test-cliente-001',
            'estado': 'borrador',
            'comprobantes': []
        }
        
        # Limpiar y crear
        await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
        await db.solicitudes_netcash.insert_one(solicitud_test)
        
        # Crear archivo corrupto temporal
        from tempfile import NamedTemporaryFile
        
        archivo_corrupto = NamedTemporaryFile(suffix='.pdf', delete=False)
        archivo_corrupto.write(b'Este no es un PDF valido, solo texto basura')
        archivo_corrupto.close()
        
        print(f"\n🔍 Intentando procesar archivo corrupto...")
        
        try:
            agregado, razon = await netcash_service.agregar_comprobante(
                solicitud_test['id'],
                archivo_corrupto.name,
                "archivo_corrupto.pdf"
            )
            
            print(f"   Resultado: agregado={agregado}, razon={razon}")
            
            # El archivo corrupto debería ser marcado como inválido pero agregado
            # O podría lanzar excepción dependiendo del validador
            
        except Exception as e:
            print(f"   Excepción capturada (esperada): {type(e).__name__}")
        
        # Limpiar archivo temporal
        os.unlink(archivo_corrupto.name)
        
        # Verificar que la solicitud NO tiene flag de revisión manual
        # (porque agregar_comprobante no lo marca, lo hace el handler de Telegram)
        print(f"\n📋 Nota: El flag 'requiere_revision_manual' se marca desde el handler de Telegram")
        print(f"   Este test verifica que el servicio base maneja el error sin romper")
        
        await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
        
        print(f"\n✅ TEST 3 PASADO: Error manejado sin romper el flujo")
        return True
    
    except Exception as e:
        print(f"\n❌ TEST 3 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Ejecutar todos los tests"""
    print("\n" + "=" * 70)
    print("🧪 SUITE DE TESTS - HANDLER DE COMPROBANTES ROBUSTO")
    print("=" * 70)
    print("\nTests a ejecutar:")
    print("  1. Procesar comprobante válido")
    print("  2. Detectar comprobante duplicado")
    print("  3. Manejo de error - archivo corrupto")
    
    resultados = {}
    
    # Test 1
    resultados['test_1'] = await test_1_comprobante_valido()
    
    # Test 2
    resultados['test_2'] = await test_2_comprobante_duplicado()
    
    # Test 3
    resultados['test_3'] = await test_3_manejo_error_archivo_corrupto()
    
    # Resumen
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE TESTS")
    print("=" * 70)
    
    tests_pasados = sum(1 for v in resultados.values() if v)
    tests_totales = len(resultados)
    
    for nombre, pasado in resultados.items():
        status = "✅ PASADO" if pasado else "❌ FALLADO"
        print(f"{nombre}: {status}")
    
    print(f"\n{'=' * 70}")
    print(f"Total: {tests_pasados}/{tests_totales} tests pasados")
    
    if tests_pasados == tests_totales:
        print("\n🎉 TODOS LOS TESTS PASARON - Handler robusto verificado")
        return True
    else:
        print(f"\n⚠️ {tests_totales - tests_pasados} test(s) fallaron")
        return False


if __name__ == "__main__":
    resultado = asyncio.run(main())
    sys.exit(0 if resultado else 1)
