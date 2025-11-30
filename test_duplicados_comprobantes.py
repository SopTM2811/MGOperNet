#!/usr/bin/env python3
"""
Test de detección de comprobantes duplicados
"""

import sys
import asyncio
import shutil
sys.path.insert(0, '/app/backend')

from netcash_service import netcash_service
from netcash_models import SolicitudCreate, CanalOrigen

async def test_duplicados():
    print("=" * 80)
    print("TEST: Detección de Comprobantes Duplicados")
    print("=" * 80)
    
    # Paso 1: Crear una solicitud de prueba
    print("\n1️⃣ Creando solicitud de prueba...")
    solicitud_data = SolicitudCreate(
        canal=CanalOrigen.TELEGRAM,
        cliente_id="test-cliente-123",
        cliente_nombre="Cliente de Prueba"
    )
    
    solicitud = await netcash_service.crear_solicitud(solicitud_data)
    solicitud_id = solicitud.get("id")
    print(f"   ✅ Solicitud creada: {solicitud_id}")
    
    # Paso 2: Obtener un archivo de prueba (PDF real)
    archivo_prueba = "/tmp/test_pdfs/THABYETHA_$2,500.00.pdf"
    
    # Verificar que existe
    import os
    if not os.path.exists(archivo_prueba):
        print(f"   ❌ Archivo de prueba no encontrado: {archivo_prueba}")
        return False
    
    print(f"   ✅ Usando archivo de prueba: {archivo_prueba}")
    
    # Paso 3: Agregar el archivo por primera vez
    print("\n2️⃣ Agregando comprobante por primera vez...")
    agregado1, razon1 = await netcash_service.agregar_comprobante(
        solicitud_id,
        archivo_prueba,
        "comprobante1.pdf"
    )
    
    if agregado1:
        print(f"   ✅ Primer comprobante agregado exitosamente")
    else:
        print(f"   ❌ Error agregando primer comprobante: {razon1}")
        return False
    
    # Paso 4: Crear una copia del archivo con otro nombre
    archivo_copia = "/tmp/test_pdfs/copia_comprobante.pdf"
    shutil.copy(archivo_prueba, archivo_copia)
    print(f"   ✅ Copia creada: {archivo_copia}")
    
    # Paso 5: Intentar agregar la copia (mismo contenido, diferente nombre)
    print("\n3️⃣ Intentando agregar el mismo archivo (con diferente nombre)...")
    agregado2, razon2 = await netcash_service.agregar_comprobante(
        solicitud_id,
        archivo_copia,
        "comprobante2_copia.pdf"
    )
    
    if not agregado2 and razon2 == "duplicado":
        print(f"   ✅ Duplicado detectado correctamente")
    else:
        print(f"   ❌ El duplicado NO fue detectado (agregado={agregado2}, razon={razon2})")
        return False
    
    # Paso 6: Agregar un archivo diferente
    archivo_diferente = "/tmp/test_pdfs/THABYETHA_$5,000.00.pdf"
    if os.path.exists(archivo_diferente):
        print("\n4️⃣ Agregando un archivo diferente...")
        agregado3, razon3 = await netcash_service.agregar_comprobante(
            solicitud_id,
            archivo_diferente,
            "comprobante3_diferente.pdf"
        )
        
        if agregado3:
            print(f"   ✅ Archivo diferente agregado exitosamente")
        else:
            print(f"   ⚠️ Archivo diferente no agregado: {razon3}")
    
    # Paso 7: Verificar en BD
    print("\n5️⃣ Verificando datos en BD...")
    solicitud = await netcash_service.obtener_solicitud(solicitud_id)
    comprobantes = solicitud.get("comprobantes", [])
    
    print(f"   Total de comprobantes en BD: {len(comprobantes)}")
    
    duplicados = [c for c in comprobantes if c.get("es_duplicado", False)]
    unicos = [c for c in comprobantes if not c.get("es_duplicado", False)]
    
    print(f"   Comprobantes únicos: {len(unicos)}")
    print(f"   Comprobantes duplicados: {len(duplicados)}")
    
    if len(duplicados) == 1:
        comp_dup = duplicados[0]
        print(f"\n   📋 Detalles del duplicado:")
        print(f"      Nombre: {comp_dup.get('nombre_archivo')}")
        print(f"      Hash: {comp_dup.get('archivo_hash')[:16]}...")
        print(f"      es_duplicado: {comp_dup.get('es_duplicado')}")
        print(f"      Duplicado de: {comp_dup.get('duplicado_de')}")
        print(f"      Razón: {comp_dup.get('validacion_detalle', {}).get('razon')}")
    
    # Paso 8: Verificar que el total solo cuenta los únicos
    print("\n6️⃣ Verificando cálculo de totales...")
    validos = [c for c in comprobantes if c.get("es_valido", False)]
    print(f"   Comprobantes válidos (no duplicados): {len(validos)}")
    
    for comp in validos:
        monto = comp.get("monto_detectado", 0)
        nombre = comp.get("nombre_archivo")
        print(f"      • {nombre}: ${monto:,.2f}")
    
    # Cleanup
    if os.path.exists(archivo_copia):
        os.remove(archivo_copia)
    
    print("\n" + "=" * 80)
    print("RESUMEN DEL TEST:")
    print("=" * 80)
    
    if len(duplicados) == 1 and len(unicos) >= 1:
        print("✅ ¡TEST PASÓ! La detección de duplicados funciona correctamente")
        print(f"✅ {len(unicos)} comprobante(s) único(s) agregado(s)")
        print(f"✅ {len(duplicados)} comprobante(s) duplicado(s) detectado(s)")
        return True
    else:
        print("❌ TEST FALLÓ")
        print(f"   Esperado: 1 duplicado, al menos 1 único")
        print(f"   Obtenido: {len(duplicados)} duplicado(s), {len(unicos)} único(s)")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_duplicados())
    sys.exit(0 if result else 1)
