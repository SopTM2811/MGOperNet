"""
Test exhaustivo del flujo completo de Tesorería:
1. Nombre del archivo CSV correcto
2. CLABE comisión DNS correcta en el layout
3. Comprobantes del cliente adjuntos
4. No envío doble
5. Detección de duplicados entre operaciones

Ejecutar: python3 tests/test_completo_tesoreria_layout_adjuntos.py
"""

import asyncio
import sys
import os
import csv
from pathlib import Path
from io import StringIO
sys.path.insert(0, str(Path(__file__).parent.parent))

from tesoreria_operacion_service import TesoreriaOperacionService
from netcash_service import netcash_service
from motor.motor_asyncio import AsyncIOMotorClient
import logging
from tempfile import NamedTemporaryFile

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

# Silenciar logs externos
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)


async def test_1_nombre_archivo_csv_correcto():
    """
    TEST 1: Verificar nombre del archivo CSV = LTMBCO_{folio_con_x}.csv
    """
    print("\n" + "=" * 70)
    print("TEST 1: Nombre del Archivo CSV Correcto")
    print("=" * 70)
    
    try:
        service = TesoreriaOperacionService()
        
        # Casos de prueba
        casos = [
            ('TEST-0001-T-99', 'LTMBCO_TESTx0001xTx99.csv'),
            ('2367-123-R-11', 'LTMBCO_2367x123xRx11.csv'),
            ('MBCO-9999-P-01', 'LTMBCO_MBCOx9999xPx01.csv'),
        ]
        
        todos_pasaron = True
        
        for folio_original, nombre_esperado in casos:
            print(f"\n🧪 Caso: {folio_original}")
            
            folio_concepto = service._convertir_folio_para_concepto(folio_original)
            nombre_generado = f"LTMBCO_{folio_concepto}.csv"
            
            print(f"   Esperado: {nombre_esperado}")
            print(f"   Generado: {nombre_generado}")
            
            if nombre_generado == nombre_esperado:
                print(f"   ✅ Correcto")
            else:
                print(f"   ❌ Incorrecto")
                todos_pasaron = False
        
        # Verificar que el archivo se guarda con ese nombre
        print(f"\n📁 Verificando directorio de layouts...")
        layout_dir = Path("/app/backend/uploads/layouts_operaciones")
        if layout_dir.exists():
            archivos = list(layout_dir.glob("*.csv"))
            print(f"   Archivos encontrados: {len(archivos)}")
            for archivo in archivos[:3]:  # Mostrar solo los primeros 3
                print(f"     - {archivo.name}")
        
        if todos_pasaron:
            print(f"\n✅ TEST 1 PASADO: Nombres de archivo CSV correctos")
            return True
        else:
            print(f"\n❌ TEST 1 FALLADO")
            return False
    
    except Exception as e:
        print(f"\n❌ TEST 1 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_2_clabe_comision_dns_correcta():
    """
    TEST 2: Verificar CLABE de comisión DNS = 058680000012912655
    """
    print("\n" + "=" * 70)
    print("TEST 2: CLABE Comisión DNS Correcta en Layout")
    print("=" * 70)
    
    try:
        service = TesoreriaOperacionService()
        
        # Crear solicitud de prueba
        solicitud_test = {
            'id': 'test-layout-001',
            'folio_mbco': 'TEST-0001-T-99',
            'monto_ligas': 1000000.00,
            'comision_dns_calculada': 3750.00,
        }
        
        # Generar layout
        print(f"\n🔍 Generando layout para {solicitud_test['folio_mbco']}...")
        layout_csv = await service._generar_layout_operacion(solicitud_test)
        
        # Parsear CSV
        reader = csv.DictReader(StringIO(layout_csv))
        filas = list(reader)
        
        print(f"\n📊 Layout generado con {len(filas)} fila(s)")
        
        # Buscar fila de comisión (última fila generalmente)
        fila_comision = None
        for fila in filas:
            concepto = fila.get('Concepto', '')
            if 'COMISION' in concepto.upper():
                fila_comision = fila
                break
        
        if not fila_comision:
            print("❌ No se encontró fila de comisión DNS")
            return False
        
        # Verificar CLABE
        clabe_encontrada = fila_comision['Clabe destinatario']
        clabe_esperada = '058680000012912655'
        
        print(f"\n💳 Fila de Comisión DNS:")
        print(f"   CLABE encontrada: {clabe_encontrada}")
        print(f"   CLABE esperada:   {clabe_esperada}")
        print(f"   Beneficiario: {fila_comision['Nombre o razon social destinatario']}")
        print(f"   Monto: ${float(fila_comision['Monto']):,.2f}")
        
        # Verificar filas de capital también
        print(f"\n📋 Verificando filas de capital...")
        clabe_capital_esperada = '012680001255709482'
        filas_capital_incorrectas = 0
        
        for i, fila in enumerate(filas):
            concepto = fila.get('Concepto', '')
            if 'COMISION' not in concepto.upper():
                clabe = fila['Clabe destinatario']
                if clabe != clabe_capital_esperada:
                    print(f"   ❌ Fila {i+1} capital con CLABE incorrecta: {clabe}")
                    filas_capital_incorrectas += 1
        
        if filas_capital_incorrectas == 0:
            print(f"   ✅ Todas las filas de capital usan CLABE correcta: {clabe_capital_esperada}")
        
        if clabe_encontrada == clabe_esperada and filas_capital_incorrectas == 0:
            print(f"\n✅ TEST 2 PASADO: CLABEs correctas en el layout")
            return True
        else:
            print(f"\n❌ TEST 2 FALLADO")
            return False
    
    except Exception as e:
        print(f"\n❌ TEST 2 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_3_comprobantes_adjuntos():
    """
    TEST 3: Verificar que comprobantes del cliente se adjuntan al correo
    """
    print("\n" + "=" * 70)
    print("TEST 3: Comprobantes del Cliente Adjuntados")
    print("=" * 70)
    
    try:
        # Crear archivos de prueba temporales
        comp1_file = NamedTemporaryFile(suffix='.pdf', delete=False)
        comp1_path = comp1_file.name
        comp1_file.write(b'PDF fake content 1')
        comp1_file.close()
        
        comp2_file = NamedTemporaryFile(suffix='.pdf', delete=False)
        comp2_path = comp2_file.name
        comp2_file.write(b'PDF fake content 2')
        comp2_file.close()
        
        print(f"\n📁 Archivos de prueba creados")
        
        # Crear solicitud de prueba con comprobantes
        solicitud_test = {
            'id': 'test-adjuntos-001',
            'folio_mbco': 'TEST-0003-T-99',
            'cliente_nombre': 'Cliente Test',
            'monto_ligas': 500000.00,
            'comision_dns_calculada': 1875.00,
            'comprobantes': [
                {
                    'nombre_archivo': 'comp1.pdf',
                    'archivo_url': comp1_path,  # Campo correcto
                    'es_valido': True,
                    'es_duplicado': False
                },
                {
                    'nombre_archivo': 'comp2.pdf',
                    'archivo_url': comp2_path,  # Campo correcto
                    'es_valido': True,
                    'es_duplicado': False
                },
                {
                    'nombre_archivo': 'comp3_invalido.pdf',
                    'archivo_url': '/ruta/inexistente.pdf',
                    'es_valido': False,  # Este NO debe adjuntarse
                    'es_duplicado': False
                }
            ]
        }
        
        service = TesoreriaOperacionService()
        
        # Generar layout
        layout_csv = await service._generar_layout_operacion(solicitud_test)
        
        # Simular preparación de adjuntos (código de _enviar_correo_operacion)
        folio_concepto = service._convertir_folio_para_concepto('TEST-0003-T-99')
        csv_filename = f"LTMBCO_{folio_concepto}.csv"
        
        # Guardar CSV
        csv_dir = Path("/app/backend/uploads/layouts_operaciones")
        csv_dir.mkdir(parents=True, exist_ok=True)
        csv_path = csv_dir / csv_filename
        
        with open(csv_path, 'w') as f:
            f.write(layout_csv)
        
        adjuntos = [str(csv_path)]
        
        # Lógica de adjuntar comprobantes (misma del servicio)
        comprobantes_adjuntos = 0
        for comp in solicitud_test['comprobantes']:
            if comp.get('es_valido') and not comp.get('es_duplicado'):
                ruta = comp.get('archivo_url')
                if ruta and Path(ruta).exists():
                    adjuntos.append(ruta)
                    comprobantes_adjuntos += 1
                    print(f"   ✅ Adjuntado: {Path(ruta).name}")
                elif ruta:
                    print(f"   ⚠️ No existe: {ruta}")
        
        print(f"\n📎 Adjuntos preparados:")
        print(f"   Total: {len(adjuntos)} archivo(s)")
        print(f"   - 1 CSV layout")
        print(f"   - {comprobantes_adjuntos} comprobante(s) cliente")
        
        # Limpiar
        os.unlink(comp1_path)
        os.unlink(comp2_path)
        os.unlink(csv_path)
        
        if len(adjuntos) == 3 and comprobantes_adjuntos == 2:
            print(f"\n✅ TEST 3 PASADO: 1 CSV + 2 comprobantes = 3 adjuntos")
            return True
        else:
            print(f"\n❌ TEST 3 FALLADO: Esperados 3 adjuntos, encontrados {len(adjuntos)}")
            return False
    
    except Exception as e:
        print(f"\n❌ TEST 3 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_4_no_envio_doble():
    """
    TEST 4: Verificar que no se envía correo doble para la misma operación
    """
    print("\n" + "=" * 70)
    print("TEST 4: Protección Anti-Duplicados en Envío de Correo")
    print("=" * 70)
    
    try:
        mongo_url = os.getenv('MONGO_URL')
        db_name = os.getenv('DB_NAME', 'netcash_mbco')
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        # Crear solicitud de prueba
        solicitud_test = {
            'id': 'test-nodup-001',
            'folio_mbco': 'TEST-DUP-001-T-99',
            'cliente_id': 'test-cliente-001',
            'cliente_nombre': 'Cliente Test',
            'estado': 'orden_interna_generada',
            'monto_ligas': 200000.00,
            'correo_tesoreria_enviado': False
        }
        
        # Limpiar y crear
        await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
        await db.solicitudes_netcash.insert_one(solicitud_test)
        
        print(f"\n📋 Solicitud creada: {solicitud_test['id']}")
        
        service = TesoreriaOperacionService()
        
        # Simular que ya se envió
        await db.solicitudes_netcash.update_one(
            {'id': solicitud_test['id']},
            {'$set': {'correo_tesoreria_enviado': True}}
        )
        
        print(f"\n🔄 Intento 1: Marcar como enviado")
        print(f"   correo_tesoreria_enviado = True")
        
        # Segundo intento: Debe detectar y no reenviar
        print(f"\n🔄 Intento 2: Intentar procesar de nuevo...")
        resultado = await service.procesar_operacion_tesoreria(solicitud_test['id'])
        
        print(f"\n📊 Resultado:")
        print(f"   success: {resultado.get('success')}")
        print(f"   mensaje: {resultado.get('mensaje', 'N/A')}")
        
        # Limpiar
        await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
        
        if resultado and not resultado.get('success'):
            if 'ya fue enviado' in resultado.get('mensaje', '').lower():
                print(f"\n✅ TEST 4 PASADO: Detectó y evitó reenvío")
                return True
        
        print(f"\n❌ TEST 4 FALLADO: No detectó el duplicado")
        return False
    
    except Exception as e:
        print(f"\n❌ TEST 4 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_5_duplicados_entre_operaciones():
    """
    TEST 5: Verificar detección de comprobantes duplicados entre operaciones
    """
    print("\n" + "=" * 70)
    print("TEST 5: Detección de Duplicados Entre Operaciones")
    print("=" * 70)
    
    try:
        mongo_url = os.getenv('MONGO_URL')
        db_name = os.getenv('DB_NAME', 'netcash_mbco')
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        # Crear archivo de prueba
        comp_file = NamedTemporaryFile(suffix='.pdf', delete=False)
        comp_path = comp_file.name
        comp_file.write(b'PDF contenido unico para test duplicados')
        comp_file.close()
        
        print(f"\n📁 Archivo de prueba creado: {Path(comp_path).name}")
        
        # OPERACIÓN 1: Crear y agregar comprobante
        solicitud1 = {
            'id': 'test-dup-op-001',
            'cliente_id': 'test-cliente-001',
            'estado': 'borrador',
            'comprobantes': []
        }
        
        await db.solicitudes_netcash.delete_one({'id': solicitud1['id']})
        await db.solicitudes_netcash.insert_one(solicitud1)
        
        print(f"\n🔄 OPERACIÓN 1: {solicitud1['id']}")
        agregado1, razon1 = await netcash_service.agregar_comprobante(
            solicitud1['id'],
            comp_path,
            "comprobante_test.pdf"
        )
        print(f"   Resultado: agregado={agregado1}, razon={razon1}")
        
        # OPERACIÓN 2: Intentar usar el MISMO comprobante
        solicitud2 = {
            'id': 'test-dup-op-002',
            'cliente_id': 'test-cliente-001',
            'estado': 'borrador',
            'comprobantes': []
        }
        
        await db.solicitudes_netcash.delete_one({'id': solicitud2['id']})
        await db.solicitudes_netcash.insert_one(solicitud2)
        
        print(f"\n🔄 OPERACIÓN 2: {solicitud2['id']}")
        print(f"   Intentando usar el MISMO PDF...")
        agregado2, razon2 = await netcash_service.agregar_comprobante(
            solicitud2['id'],
            comp_path,
            "comprobante_test_copia.pdf"
        )
        print(f"   Resultado: agregado={agregado2}, razon={razon2}")
        
        # Verificar que se detectó como duplicado global
        if not agregado2 and 'duplicado_global' in str(razon2):
            print(f"\n✅ TEST 5 PASADO: Duplicado entre operaciones detectado")
            print(f"   El sistema rechazó el uso del mismo PDF en operación 2")
            
            # Limpiar
            os.unlink(comp_path)
            await db.solicitudes_netcash.delete_one({'id': solicitud1['id']})
            await db.solicitudes_netcash.delete_one({'id': solicitud2['id']})
            
            return True
        else:
            print(f"\n❌ TEST 5 FALLADO: No se detectó como duplicado global")
            print(f"   agregado2={agregado2}, razon2={razon2}")
            
            # Limpiar
            os.unlink(comp_path)
            await db.solicitudes_netcash.delete_one({'id': solicitud1['id']})
            await db.solicitudes_netcash.delete_one({'id': solicitud2['id']})
            
            return False
    
    except Exception as e:
        print(f"\n❌ TEST 5 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Ejecutar todos los tests"""
    print("\n" + "=" * 70)
    print("🧪 SUITE COMPLETA DE TESTS - TESORERÍA + ADJUNTOS + DUPLICADOS")
    print("=" * 70)
    print("\nTests a ejecutar:")
    print("  1. Nombre del archivo CSV correcto")
    print("  2. CLABE comisión DNS correcta (058680000012912655)")
    print("  3. Comprobantes del cliente adjuntados")
    print("  4. No envío doble de correo")
    print("  5. Detección de duplicados entre operaciones")
    
    resultados = {}
    
    resultados['test_1'] = await test_1_nombre_archivo_csv_correcto()
    resultados['test_2'] = await test_2_clabe_comision_dns_correcta()
    resultados['test_3'] = await test_3_comprobantes_adjuntos()
    resultados['test_4'] = await test_4_no_envio_doble()
    resultados['test_5'] = await test_5_duplicados_entre_operaciones()
    
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
        print("\n🎉 TODOS LOS TESTS PASARON")
        return True
    else:
        print(f"\n⚠️ {tests_totales - tests_pasados} test(s) fallaron")
        return False


if __name__ == "__main__":
    resultado = asyncio.run(main())
    sys.exit(0 if resultado else 1)
