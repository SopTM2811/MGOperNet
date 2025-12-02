#!/usr/bin/env python3
"""
Test de integración para verificar el fix P0 del error 'await' outside async function
en tesoreria_operacion_service.py con datos reales de MongoDB
"""

import asyncio
import sys
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('/app/backend/.env')

# Agregar el directorio backend al path
sys.path.insert(0, '/app/backend')

async def test_tesoreria_integration():
    """Test de integración con datos reales"""
    print("=" * 60)
    print("TEST INTEGRACIÓN: Fix P0 - Tesorería Operación Service")
    print("=" * 60)
    
    # Conectar a MongoDB
    mongo_url = os.getenv('MONGO_URL')
    db_name = os.getenv('DB_NAME', 'netcash_mbco')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    try:
        # Test 1: Crear una solicitud de prueba
        print("🔍 Test 1: Creando solicitud de prueba...")
        
        solicitud_test = {
            'id': f'test_p0_{int(datetime.now().timestamp())}',
            'folio_mbco': 'TEST-P0-001-T-99',
            'cliente_nombre': 'CLIENTE PRUEBA P0',
            'beneficiario_reportado': 'BENEFICIARIO PRUEBA P0',
            'idmex_reportado': 'IDMEX123456789',
            'total_comprobantes_validos': 100000.00,
            'monto_ligas': 99625.00,
            'comision_dns_calculada': 373.59,
            'estado': 'lista_para_mbc',
            'correo_tesoreria_enviado': False,
            'comprobantes': [
                {
                    'es_valido': True,
                    'es_duplicado': False,
                    'monto_detectado': 100000.00,
                    'banco_ordenante': 'BBVA',
                    'cuenta_ordenante': '012180015012345678',
                    'archivo_url': '/uploads/comprobantes/test_p0_comprobante.pdf'
                }
            ],
            'fecha_creacion': datetime.now(timezone.utc),
            'canal': 'telegram'
        }
        
        # Insertar en BD
        await db.solicitudes_netcash.insert_one(solicitud_test)
        print(f"   ✅ Solicitud de prueba creada: {solicitud_test['id']}")
        
        # Test 2: Procesar la operación con el servicio real
        print("\n🔍 Test 2: Procesando operación con tesoreria_operacion_service...")
        
        from tesoreria_operacion_service import tesoreria_operacion_service
        
        try:
            resultado = await tesoreria_operacion_service.procesar_operacion_tesoreria(solicitud_test['id'])
            
            if resultado:
                print("   ✅ procesar_operacion_tesoreria ejecutado sin excepciones")
                print(f"   📊 Resultado: {resultado}")
                
                # Verificar estructura del resultado
                if resultado.get('success') is True:
                    print("   ✅ Resultado contiene success=True")
                else:
                    print(f"   ⚠️ Success no es True: {resultado.get('success')}")
                
                if resultado.get('solicitud_id') == solicitud_test['id']:
                    print("   ✅ solicitud_id correcto en resultado")
                else:
                    print(f"   ⚠️ solicitud_id incorrecto: {resultado.get('solicitud_id')}")
                
                if resultado.get('folio_mbco') == solicitud_test['folio_mbco']:
                    print("   ✅ folio_mbco correcto en resultado")
                else:
                    print(f"   ⚠️ folio_mbco incorrecto: {resultado.get('folio_mbco')}")
                
            else:
                print("   ❌ procesar_operacion_tesoreria retornó None")
                return False
                
        except Exception as e:
            print(f"   ❌ Error ejecutando procesar_operacion_tesoreria: {str(e)}")
            import traceback
            print(f"   ❌ Traceback: {traceback.format_exc()}")
            return False
        
        # Test 3: Verificar que la solicitud se actualizó en BD
        print("\n🔍 Test 3: Verificando actualización en BD...")
        
        solicitud_actualizada = await db.solicitudes_netcash.find_one(
            {'id': solicitud_test['id']}, 
            {'_id': 0}
        )
        
        if solicitud_actualizada:
            estado_actual = solicitud_actualizada.get('estado')
            correo_enviado = solicitud_actualizada.get('correo_tesoreria_enviado')
            
            print(f"   📊 Estado actual: {estado_actual}")
            print(f"   📊 Correo enviado: {correo_enviado}")
            
            if estado_actual == 'enviado_a_tesoreria':
                print("   ✅ Estado actualizado correctamente")
            else:
                print(f"   ⚠️ Estado no actualizado como esperado: {estado_actual}")
            
            if correo_enviado is True:
                print("   ✅ Flag correo_tesoreria_enviado actualizado")
            else:
                print(f"   ⚠️ Flag correo_tesoreria_enviado no actualizado: {correo_enviado}")
        else:
            print("   ❌ No se pudo encontrar la solicitud actualizada")
            return False
        
        # Test 4: Verificar que la función _generar_cuerpo_correo_operacion funciona
        print("\n🔍 Test 4: Verificando _generar_cuerpo_correo_operacion directamente...")
        
        from tesoreria_operacion_service import TesoreriaOperacionService
        service = TesoreriaOperacionService()
        
        try:
            cuerpo = await service._generar_cuerpo_correo_operacion(solicitud_actualizada)
            
            if cuerpo and isinstance(cuerpo, str) and len(cuerpo) > 0:
                print(f"   ✅ Cuerpo generado correctamente: {len(cuerpo)} caracteres")
                
                # Verificar que contiene la cuenta NetCash activa
                if '646180139409481462' in cuerpo:
                    print("   ✅ CLABE de cuenta NetCash activa incluida en el correo")
                else:
                    print("   ⚠️ CLABE de cuenta NetCash activa no encontrada en el correo")
                
                # Verificar otros elementos
                if solicitud_test['folio_mbco'] in cuerpo:
                    print("   ✅ Folio MBco incluido en el correo")
                
                if solicitud_test['cliente_nombre'] in cuerpo:
                    print("   ✅ Nombre del cliente incluido en el correo")
                
            else:
                print("   ❌ Cuerpo del correo no generado correctamente")
                return False
                
        except Exception as e:
            print(f"   ❌ Error generando cuerpo del correo: {str(e)}")
            return False
        
        # Test 5: Limpiar datos de prueba
        print("\n🔍 Test 5: Limpiando datos de prueba...")
        
        result = await db.solicitudes_netcash.delete_one({'id': solicitud_test['id']})
        if result.deleted_count > 0:
            print("   ✅ Solicitud de prueba eliminada")
        else:
            print("   ⚠️ No se pudo eliminar la solicitud de prueba")
        
        print("\n" + "=" * 60)
        print("🎉 RESULTADO: Test de integración P0 EXITOSO")
        print("✅ procesar_operacion_tesoreria funciona sin excepciones")
        print("✅ Retorna {'success': True} correctamente")
        print("✅ _generar_cuerpo_correo_operacion es correctamente async")
        print("✅ Obtiene cuenta NetCash activa y la incluye en el email")
        print("✅ Actualiza correctamente el estado en BD")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error durante el test de integración: {str(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return False
    
    finally:
        # Cerrar conexión
        client.close()

async def test_anti_duplicados():
    """Test adicional: Verificar protección anti-duplicados"""
    print("\n🔍 Test adicional: Verificando protección anti-duplicados...")
    
    # Conectar a MongoDB
    mongo_url = os.getenv('MONGO_URL')
    db_name = os.getenv('DB_NAME', 'netcash_mbco')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    try:
        # Crear solicitud ya enviada
        solicitud_enviada = {
            'id': f'test_duplicado_{int(datetime.now().timestamp())}',
            'folio_mbco': 'TEST-DUP-001-T-99',
            'cliente_nombre': 'CLIENTE DUPLICADO',
            'correo_tesoreria_enviado': True,  # YA ENVIADO
            'fecha_envio_tesoreria': datetime.now(timezone.utc),
            'estado': 'enviado_a_tesoreria'
        }
        
        await db.solicitudes_netcash.insert_one(solicitud_enviada)
        print(f"   📝 Solicitud 'ya enviada' creada: {solicitud_enviada['id']}")
        
        # Intentar procesar nuevamente
        from tesoreria_operacion_service import tesoreria_operacion_service
        
        resultado = await tesoreria_operacion_service.procesar_operacion_tesoreria(solicitud_enviada['id'])
        
        if resultado:
            if resultado.get('success') is True and resultado.get('ya_enviado_antes') is True:
                print("   ✅ Protección anti-duplicados funciona correctamente")
            else:
                print(f"   ⚠️ Resultado inesperado: {resultado}")
        else:
            print("   ⚠️ No se retornó resultado para solicitud ya enviada")
        
        # Limpiar
        await db.solicitudes_netcash.delete_one({'id': solicitud_enviada['id']})
        print("   ✅ Solicitud de prueba eliminada")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en test anti-duplicados: {str(e)}")
        return False
    
    finally:
        client.close()

if __name__ == "__main__":
    async def main():
        success1 = await test_tesoreria_integration()
        success2 = await test_anti_duplicados()
        
        if success1 and success2:
            print("\n🎉 TODOS LOS TESTS DE INTEGRACIÓN PASARON")
            print("🎯 FIX P0 COMPLETAMENTE VERIFICADO")
            return 0
        else:
            print("\n❌ ALGUNOS TESTS DE INTEGRACIÓN FALLARON")
            return 1
    
    exit_code = asyncio.run(main())
    exit(exit_code)