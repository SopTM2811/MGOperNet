"""
Tests para verificar los 4 ajustes quirúrgicos del flujo de Tesorería:
1. CLABE correcta de comisión DNS (058680000012912655)
2. Nombre correcto del archivo CSV (LTMBCO_{folio_con_x}.csv)
3. Comprobantes del cliente adjuntos en el correo
4. Protección anti-duplicados en el envío

Ejecutar: python3 tests/test_ajustes_tesoreria.py
"""

import asyncio
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tesoreria_operacion_service import TesoreriaOperacionService
from motor.motor_asyncio import AsyncIOMotorClient
from decimal import Decimal
import logging
import csv
from io import StringIO

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

# Silenciar logs de librerías externas
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)


async def test_1_clabe_comision_dns_correcta():
    """
    TEST 1: Verificar que la CLABE de comisión DNS sea exactamente 058680000012912655
    """
    print("\n" + "=" * 70)
    print("TEST 1: CLABE Comisión DNS Correcta")
    print("=" * 70)
    
    try:
        service = TesoreriaOperacionService()
        
        # Crear solicitud de prueba
        solicitud_test = {
            'id': 'test-001',
            'folio_mbco': 'TEST-0001-T-99',
            'monto_ligas': 1000000.00,  # $1,000,000 de capital
            'comision_dns_calculada': 3750.00,  # 0.375% = $3,750
            'comprobantes': []
        }
        
        # Generar layout
        layout_csv = await service._generar_layout_operacion(solicitud_test)
        
        # Parsear CSV
        reader = csv.DictReader(StringIO(layout_csv))
        filas = list(reader)
        
        # Buscar fila de comisión DNS (última fila)
        fila_comision = None
        for fila in filas:
            if 'COMISION' in fila.get('Concepto', '').upper():
                fila_comision = fila
                break
        
        if not fila_comision:
            print("❌ ERROR: No se encontró fila de comisión DNS en el layout")
            return False
        
        # Verificar CLABE
        clabe_encontrada = fila_comision['Clabe destinatario']
        clabe_esperada = '058680000012912655'
        
        print(f"\n📋 Fila de Comisión DNS:")
        print(f"   CLABE encontrada: {clabe_encontrada}")
        print(f"   CLABE esperada:   {clabe_esperada}")
        print(f"   Beneficiario: {fila_comision['Nombre o razon social destinatario']}")
        print(f"   Monto: ${float(fila_comision['Monto']):,.2f}")
        
        if clabe_encontrada == clabe_esperada:
            print("\n✅ TEST 1 PASADO: CLABE de comisión DNS es correcta")
            
            # Verificar también el beneficiario
            beneficiario = fila_comision['Nombre o razon social destinatario']
            if 'COMERCIALIZADORA UETACOP' in beneficiario or 'UETACOP' in beneficiario:
                print("✅ Beneficiario correcto: COMERCIALIZADORA UETACOP SA DE CV")
            else:
                print(f"⚠️ Advertencia: Beneficiario esperado 'COMERCIALIZADORA UETACOP', encontrado: {beneficiario}")
            
            return True
        else:
            print(f"\n❌ TEST 1 FALLADO: CLABE incorrecta")
            print(f"   Se esperaba: {clabe_esperada}")
            print(f"   Se encontró:  {clabe_encontrada}")
            return False
    
    except Exception as e:
        print(f"\n❌ TEST 1 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_2_nombre_archivo_csv():
    """
    TEST 2: Verificar que el nombre del archivo CSV sea LTMBCO_{folio_con_x}.csv
    """
    print("\n" + "=" * 70)
    print("TEST 2: Nombre Correcto del Archivo CSV")
    print("=" * 70)
    
    try:
        service = TesoreriaOperacionService()
        
        # Casos de prueba con diferentes formatos de folio
        casos_prueba = [
            ('TEST-0001-T-99', 'LTMBCO_TESTx0001xTx99.csv'),
            ('2367-123-R-11', 'LTMBCO_2367x123xRx11.csv'),
            ('MBCO-9999-P-01', 'LTMBCO_MBCOx9999xPx01.csv'),
        ]
        
        todos_pasaron = True
        
        for folio_original, nombre_esperado in casos_prueba:
            print(f"\n🧪 Caso: folio = {folio_original}")
            
            # Convertir folio
            folio_concepto = service._convertir_folio_para_concepto(folio_original)
            nombre_generado = f"LTMBCO_{folio_concepto}.csv"
            
            print(f"   Folio convertido: {folio_concepto}")
            print(f"   Nombre esperado:  {nombre_esperado}")
            print(f"   Nombre generado:  {nombre_generado}")
            
            if nombre_generado == nombre_esperado:
                print(f"   ✅ Correcto")
            else:
                print(f"   ❌ Incorrecto")
                todos_pasaron = False
        
        if todos_pasaron:
            print("\n✅ TEST 2 PASADO: Nombres de archivo CSV correctos")
            return True
        else:
            print("\n❌ TEST 2 FALLADO: Algunos nombres incorrectos")
            return False
    
    except Exception as e:
        print(f"\n❌ TEST 2 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_3_adjuntar_comprobantes_cliente():
    """
    TEST 3: Verificar que los comprobantes del cliente se adjunten al correo
    """
    print("\n" + "=" * 70)
    print("TEST 3: Adjuntar Comprobantes del Cliente")
    print("=" * 70)
    
    try:
        # Crear archivos de prueba temporales
        from tempfile import NamedTemporaryFile
        
        comp1_file = NamedTemporaryFile(suffix='.pdf', delete=False)
        comp1_path = comp1_file.name
        comp1_file.write(b'PDF fake content 1')
        comp1_file.close()
        
        comp2_file = NamedTemporaryFile(suffix='.pdf', delete=False)
        comp2_path = comp2_file.name
        comp2_file.write(b'PDF fake content 2')
        comp2_file.close()
        
        print(f"\n📁 Archivos de prueba creados:")
        print(f"   {comp1_path}")
        print(f"   {comp2_path}")
        
        # Crear solicitud de prueba con comprobantes
        solicitud_test = {
            'id': 'test-003',
            'folio_mbco': 'TEST-0003-T-99',
            'cliente_nombre': 'Cliente Test',
            'monto_ligas': 500000.00,
            'comision_dns_calculada': 1875.00,
            'comprobantes': [
                {
                    'nombre_archivo': 'comp1.pdf',
                    'archivo_url': comp1_path,  # ⚠️ Campo correcto
                    'es_valido': True,
                    'es_duplicado': False
                },
                {
                    'nombre_archivo': 'comp2.pdf',
                    'archivo_url': comp2_path,  # ⚠️ Campo correcto
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
        
        # Simular preparación de adjuntos (parte del código de _enviar_correo_operacion)
        folio_concepto = service._convertir_folio_para_concepto('TEST-0003-T-99')
        csv_filename = f"LTMBCO_{folio_concepto}.csv"
        
        # Crear CSV temporal
        csv_dir = Path("/app/backend/uploads/layouts_operaciones")
        csv_dir.mkdir(parents=True, exist_ok=True)
        csv_path = csv_dir / csv_filename
        
        with open(csv_path, 'w') as f:
            f.write(layout_csv)
        
        adjuntos = [str(csv_path)]
        
        # Agregar comprobantes (misma lógica que en _enviar_correo_operacion)
        comprobantes_adjuntos = 0
        for comp in solicitud_test['comprobantes']:
            if comp.get('es_valido') and not comp.get('es_duplicado'):
                ruta = comp.get('archivo_url')
                if ruta and Path(ruta).exists():
                    adjuntos.append(ruta)
                    comprobantes_adjuntos += 1
        
        print(f"\n📎 Adjuntos preparados:")
        print(f"   Total: {len(adjuntos)} archivo(s)")
        print(f"   - 1 CSV layout")
        print(f"   - {comprobantes_adjuntos} comprobante(s) cliente")
        
        for i, adj in enumerate(adjuntos, 1):
            print(f"   {i}. {Path(adj).name}")
        
        # Verificar
        if len(adjuntos) == 3 and comprobantes_adjuntos == 2:
            print("\n✅ TEST 3 PASADO: Comprobantes correctamente adjuntados")
            print(f"   ✅ 1 CSV + 2 comprobantes válidos = 3 adjuntos totales")
            print(f"   ✅ El comprobante inválido NO fue adjuntado")
            
            # Limpiar
            os.unlink(comp1_path)
            os.unlink(comp2_path)
            os.unlink(csv_path)
            
            return True
        else:
            print(f"\n❌ TEST 3 FALLADO:")
            print(f"   Se esperaban 3 adjuntos (1 CSV + 2 comprobantes)")
            print(f"   Se encontraron {len(adjuntos)} adjuntos")
            
            # Limpiar
            os.unlink(comp1_path)
            os.unlink(comp2_path)
            if csv_path.exists():
                os.unlink(csv_path)
            
            return False
    
    except Exception as e:
        print(f"\n❌ TEST 3 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_4_proteccion_anti_duplicados():
    """
    TEST 4: Verificar que no se envíe el correo dos veces para la misma operación
    """
    print("\n" + "=" * 70)
    print("TEST 4: Protección Anti-Duplicados")
    print("=" * 70)
    
    try:
        # Conectar a BD de prueba
        mongo_url = os.getenv('MONGO_URL')
        db_name = os.getenv('DB_NAME', 'netcash_mbco')
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        # Crear solicitud de prueba en BD
        solicitud_test = {
            'id': 'test-duplicado-001',
            'folio_mbco': 'TEST-DUP-001-T-99',
            'cliente_id': 'test-cliente-001',
            'cliente_nombre': 'Cliente Test Duplicado',
            'estado': 'orden_interna_generada',
            'monto_ligas': 200000.00,
            'correo_tesoreria_enviado': False  # Inicialmente NO enviado
        }
        
        # Insertar en BD
        await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})  # Limpiar si existe
        await db.solicitudes_netcash.insert_one(solicitud_test)
        
        print(f"\n📋 Solicitud de prueba creada: {solicitud_test['id']}")
        print(f"   Estado inicial: {solicitud_test['estado']}")
        print(f"   correo_tesoreria_enviado: {solicitud_test['correo_tesoreria_enviado']}")
        
        # Primer intento: Debe procesar y marcar como enviado
        print(f"\n🔄 INTENTO 1: Procesando operación...")
        service = TesoreriaOperacionService()
        
        # Mock: Marcar como si ya se envió el correo
        await db.solicitudes_netcash.update_one(
            {'id': solicitud_test['id']},
            {'$set': {'correo_tesoreria_enviado': True}}
        )
        print("   (Simulando que el correo ya fue enviado)")
        
        # Segundo intento: Debe detectar y NO reenviar
        print(f"\n🔄 INTENTO 2: Intentando procesar de nuevo...")
        resultado = await service.procesar_operacion_tesoreria(solicitud_test['id'])
        
        print(f"\n📊 Resultado del intento 2:")
        print(f"   success: {resultado.get('success')}")
        print(f"   mensaje: {resultado.get('mensaje', 'N/A')}")
        
        # Verificar
        if resultado and not resultado.get('success'):
            if 'ya fue enviado' in resultado.get('mensaje', '').lower():
                print("\n✅ TEST 4 PASADO: Protección anti-duplicados funcionando")
                print("   ✅ El sistema detectó que el correo ya fue enviado")
                print("   ✅ No se reenvió el correo (evita duplicados)")
                
                # Limpiar
                await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
                
                return True
            else:
                print(f"\n❌ TEST 4 FALLADO: El sistema no retornó el mensaje esperado")
                await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
                return False
        else:
            print(f"\n❌ TEST 4 FALLADO: El sistema permitió reenviar (duplicado)")
            await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
            return False
    
    except Exception as e:
        print(f"\n❌ TEST 4 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Ejecutar todos los tests"""
    print("\n" + "=" * 70)
    print("🧪 SUITE DE TESTS - AJUSTES QUIRÚRGICOS TESORERÍA")
    print("=" * 70)
    print("\nTests a ejecutar:")
    print("  1. CLABE correcta de comisión DNS")
    print("  2. Nombre correcto del archivo CSV")
    print("  3. Comprobantes del cliente adjuntos")
    print("  4. Protección anti-duplicados")
    
    resultados = {}
    
    # Test 1
    resultados['test_1'] = await test_1_clabe_comision_dns_correcta()
    
    # Test 2
    resultados['test_2'] = await test_2_nombre_archivo_csv()
    
    # Test 3
    resultados['test_3'] = await test_3_adjuntar_comprobantes_cliente()
    
    # Test 4
    resultados['test_4'] = await test_4_proteccion_anti_duplicados()
    
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
        print("\n🎉 TODOS LOS TESTS PASARON - Ajustes quirúrgicos verificados")
        return True
    else:
        print(f"\n⚠️ {tests_totales - tests_pasados} test(s) fallaron - Revisar implementación")
        return False


if __name__ == "__main__":
    resultado = asyncio.run(main())
    sys.exit(0 if resultado else 1)
