#!/usr/bin/env python3
"""
Test de detección de comprobantes duplicados GLOBALES (entre operaciones)
"""

import sys
import asyncio
import shutil
sys.path.insert(0, '/app/backend')

from netcash_service import netcash_service
from netcash_models import SolicitudCreate, CanalOrigen

async def test_duplicados_globales():
    print("=" * 80)
    print("TEST: Detección de Comprobantes Duplicados GLOBALES")
    print("=" * 80)
    
    cliente_id = "test-cliente-global-dup-123"
    
    # Limpiar operaciones anteriores de este cliente de prueba
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    mongo_url = os.getenv('MONGO_URL')
    db_name = os.getenv('DB_NAME', 'netcash_mbco')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    result = await db.solicitudes_netcash.delete_many({"cliente_id": cliente_id})
    if result.deleted_count > 0:
        print(f"🧹 Limpieza: {result.deleted_count} operación(es) anterior(es) eliminada(s)\n")
    
    # ====================
    # OPERACIÓN 1
    # ====================
    print("\n📋 OPERACIÓN 1: Crear primera operación y agregar comprobante único")
    print("-" * 80)
    
    solicitud1_data = SolicitudCreate(
        canal=CanalOrigen.TELEGRAM,
        cliente_id=cliente_id,
        cliente_nombre="Cliente Prueba Global"
    )
    
    solicitud1 = await netcash_service.crear_solicitud(solicitud1_data)
    solicitud1_id = solicitud1.get("id")
    print(f"✅ Operación 1 creada: {solicitud1_id}")
    
    # Agregar comprobante a la primera operación
    archivo_prueba = "/tmp/test_pdfs/THABYETHA_$2,500.00.pdf"
    
    import os
    if not os.path.exists(archivo_prueba):
        print(f"❌ Archivo de prueba no encontrado: {archivo_prueba}")
        return False
    
    agregado1, razon1 = await netcash_service.agregar_comprobante(
        solicitud1_id,
        archivo_prueba,
        "comprobante_operacion1.pdf"
    )
    
    if agregado1:
        print(f"✅ Comprobante agregado a Operación 1")
    else:
        print(f"❌ Error: {razon1}")
        return False
    
    # Cambiar estado para simular que es una operación válida
    from netcash_models import EstadoSolicitud
    await netcash_service.cambiar_estado(
        solicitud1_id,
        EstadoSolicitud.LISTA_PARA_MBC,
        "Operación 1 procesada"
    )
    
    sol1 = await netcash_service.obtener_solicitud(solicitud1_id)
    folio1 = sol1.get("folio_mbco")
    print(f"✅ Operación 1 procesada con folio: {folio1}")
    
    # ====================
    # OPERACIÓN 2
    # ====================
    print("\n📋 OPERACIÓN 2: Crear segunda operación e intentar usar el mismo comprobante")
    print("-" * 80)
    
    solicitud2_data = SolicitudCreate(
        canal=CanalOrigen.TELEGRAM,
        cliente_id=cliente_id,  # Mismo cliente
        cliente_nombre="Cliente Prueba Global"
    )
    
    solicitud2 = await netcash_service.crear_solicitud(solicitud2_data)
    solicitud2_id = solicitud2.get("id")
    print(f"✅ Operación 2 creada: {solicitud2_id}")
    
    # Intentar agregar el MISMO archivo (duplicado global)
    print("\n🔍 Intentando agregar el mismo archivo en Operación 2...")
    agregado2, razon2 = await netcash_service.agregar_comprobante(
        solicitud2_id,
        archivo_prueba,
        "comprobante_operacion2.pdf"  # Diferente nombre, mismo contenido
    )
    
    print(f"   Resultado: agregado={agregado2}, razon={razon2}")
    
    if not agregado2 and razon2.startswith("duplicado_global:"):
        folio_detectado = razon2.split(":")[1]
        print(f"✅ Duplicado GLOBAL detectado correctamente")
        print(f"   Folio original: {folio_detectado}")
        
        if folio_detectado == folio1:
            print(f"✅ Folio coincide con Operación 1")
        else:
            print(f"❌ Folio NO coincide (esperado: {folio1}, obtenido: {folio_detectado})")
            return False
    else:
        print(f"❌ El duplicado GLOBAL NO fue detectado")
        return False
    
    # ====================
    # VERIFICAR EN BD
    # ====================
    print("\n📊 Verificando datos en BD...")
    print("-" * 80)
    
    sol2 = await netcash_service.obtener_solicitud(solicitud2_id)
    comprobantes2 = sol2.get("comprobantes", [])
    
    if len(comprobantes2) == 1:
        comp = comprobantes2[0]
        print(f"✅ Comprobante guardado en Operación 2:")
        print(f"   es_duplicado: {comp.get('es_duplicado')}")
        print(f"   tipo_duplicado: {comp.get('tipo_duplicado')}")
        print(f"   operacion_original: {comp.get('operacion_original')}")
        print(f"   es_valido: {comp.get('es_valido')}")
        
        if comp.get("tipo_duplicado") == "global" and comp.get("operacion_original") == folio1:
            print(f"✅ Estructura de datos correcta")
        else:
            print(f"❌ Estructura de datos incorrecta")
            return False
    else:
        print(f"❌ Número incorrecto de comprobantes en Operación 2: {len(comprobantes2)}")
        return False
    
    # ====================
    # AGREGAR COMPROBANTE ÚNICO
    # ====================
    print("\n📋 Agregando un comprobante DIFERENTE a Operación 2...")
    print("-" * 80)
    
    archivo_diferente = "/tmp/test_pdfs/THABYETHA_$5,000.00.pdf"
    if os.path.exists(archivo_diferente):
        agregado3, razon3 = await netcash_service.agregar_comprobante(
            solicitud2_id,
            archivo_diferente,
            "comprobante_diferente.pdf"
        )
        
        if agregado3:
            print(f"✅ Comprobante diferente agregado correctamente")
        else:
            print(f"⚠️ Comprobante diferente no agregado: {razon3}")
    
    # ====================
    # RESUMEN
    # ====================
    print("\n" + "=" * 80)
    print("RESUMEN DEL TEST:")
    print("=" * 80)
    
    print(f"\n✅ Operación 1 ({folio1}):")
    print(f"   - 1 comprobante único agregado")
    print(f"   - Estado: lista_para_mbc")
    
    sol2_final = await netcash_service.obtener_solicitud(solicitud2_id)
    comps2_final = sol2_final.get("comprobantes", [])
    dup_global = [c for c in comps2_final if c.get("tipo_duplicado") == "global"]
    unicos2 = [c for c in comps2_final if not c.get("es_duplicado", False)]
    
    print(f"\n✅ Operación 2:")
    print(f"   - {len(comps2_final)} comprobante(s) total")
    print(f"   - {len(dup_global)} duplicado(s) GLOBAL(es)")
    print(f"   - {len(unicos2)} único(s)")
    
    if len(dup_global) == 1 and dup_global[0].get("operacion_original") == folio1:
        print(f"\n✅ ¡TEST PASÓ! La detección de duplicados GLOBALES funciona correctamente")
        return True
    else:
        print(f"\n❌ TEST FALLÓ")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_duplicados_globales())
    sys.exit(0 if result else 1)
