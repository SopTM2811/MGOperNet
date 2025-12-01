"""
Test para verificar la detección de comprobantes duplicados globales.

Este test verifica que el sistema detecta cuando el mismo comprobante
(basado en hash SHA-256) se intenta usar en múltiples operaciones diferentes.

Bug reportado por usuario: Operaciones 0022 y 0023 aceptaron el mismo comprobante.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone
import hashlib
from pathlib import Path

# Importar servicio
import sys
sys.path.insert(0, '/app/backend')

from netcash_service import netcash_service


async def test_duplicados_globales():
    """
    Test de detección de duplicados globales
    """
    
    mongo_url = os.getenv('MONGO_URL')
    db_name = os.getenv('DB_NAME', 'netcash_mbco')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("\n" + "="*80)
    print("TEST: Detección de Comprobantes Duplicados Globales")
    print("="*80)
    
    # SETUP: Limpiar y crear datos de prueba
    await db.solicitudes_netcash.delete_many({})
    await db.clientes.delete_many({})
    await db.config_cuentas_netcash.delete_many({})
    
    # Cliente de prueba
    await db.clientes.insert_one({
        "id": "cliente_test_duplicados",
        "nombre": "Cliente Test Duplicados",
        "estado": "activo",
        "telegram_id": 999888777
    })
    
    # Cuenta concertadora activa
    await db.config_cuentas_netcash.insert_one({
        "tipo": "concertadora",
        "banco": "STP",
        "clabe": "646180174400027290",
        "beneficiario": "MONTE BANCO SA DE CV",
        "activa": True
    })
    
    # Crear un archivo de prueba único
    upload_dir = Path("/app/backend/uploads/comprobantes_telegram")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    archivo_test = upload_dir / "comprobante_test_duplicados.txt"
    contenido_unico = f"COMPROBANTE DE PRUEBA PARA DETECCIÓN DE DUPLICADOS - {datetime.now().isoformat()}"
    archivo_test.write_text(contenido_unico)
    
    # Calcular hash del archivo
    with open(archivo_test, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    
    print(f"\n1. Archivo de prueba creado: {archivo_test.name}")
    print(f"   Hash SHA-256: {file_hash[:16]}...")
    
    # PASO 1: Crear operación 0022 (primera operación)
    solicitud_0022 = {
        "id": "test_op_0022",
        "solicitud_id": "test_op_0022",
        "folio_mbco": "0022",
        "cliente_id": "cliente_test_duplicados",
        "estado": "comprobantes_recibidos",  # Estado crítico para la detección
        "comprobantes": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    await db.solicitudes_netcash.insert_one(solicitud_0022)
    print(f"\n2. Operación 0022 creada (estado: comprobantes_recibidos)")
    
    # Agregar comprobante a operación 0022
    agregado_1, razon_1 = await netcash_service.agregar_comprobante(
        "test_op_0022",
        str(archivo_test),
        archivo_test.name
    )
    
    if agregado_1:
        print(f"   ✅ Comprobante agregado exitosamente a operación 0022")
    else:
        print(f"   ❌ Error: {razon_1}")
    
    # Verificar que se guardó con el hash correcto
    sol_0022_updated = await db.solicitudes_netcash.find_one(
        {"id": "test_op_0022"},
        {"_id": 0}
    )
    comp_0022 = sol_0022_updated.get("comprobantes", [])[0] if sol_0022_updated.get("comprobantes") else None
    
    if comp_0022:
        hash_guardado_0022 = comp_0022.get("archivo_hash")
        print(f"   Hash guardado en DB: {hash_guardado_0022[:16]}...")
        
        if hash_guardado_0022 == file_hash:
            print(f"   ✅ Hash correcto guardado en operación 0022")
        else:
            print(f"   ❌ ERROR: Hash no coincide!")
            print(f"      Esperado: {file_hash[:16]}...")
            print(f"      Guardado: {hash_guardado_0022[:16]}...")
    
    # PASO 2: Crear operación 0023 (segunda operación)
    solicitud_0023 = {
        "id": "test_op_0023",
        "solicitud_id": "test_op_0023",
        "folio_mbco": "0023",
        "cliente_id": "cliente_test_duplicados",
        "estado": "comprobantes_recibidos",  # Mismo estado
        "comprobantes": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    await db.solicitudes_netcash.insert_one(solicitud_0023)
    print(f"\n3. Operación 0023 creada (estado: comprobantes_recibidos)")
    
    # Intentar agregar EL MISMO comprobante a operación 0023
    print(f"\n4. Intentando agregar el MISMO comprobante a operación 0023...")
    
    agregado_2, razon_2 = await netcash_service.agregar_comprobante(
        "test_op_0023",
        str(archivo_test),
        archivo_test.name
    )
    
    # VERIFICACIÓN: Debe detectar el duplicado
    print("\n" + "="*80)
    print("RESULTADOS DEL TEST")
    print("="*80)
    
    exito = True
    
    if not agregado_2:
        print(f"✅ CORRECTO: Sistema detectó el duplicado")
        print(f"   Razón: {razon_2}")
        
        # Verificar que la razón indica duplicado global
        if razon_2 and razon_2.startswith("duplicado_global:"):
            folio_detectado = razon_2.split(":")[1]
            print(f"   Folio original detectado: {folio_detectado}")
            
            if folio_detectado == "0022":
                print(f"   ✅ Folio correcto detectado")
            else:
                print(f"   ❌ ERROR: Folio incorrecto (esperaba 0022, obtuvo {folio_detectado})")
                exito = False
        else:
            print(f"   ⚠️  WARNING: Razón no indica duplicado_global (razon: {razon_2})")
        
        # Verificar que se marcó como duplicado en la BD
        sol_0023_updated = await db.solicitudes_netcash.find_one(
            {"id": "test_op_0023"},
            {"_id": 0}
        )
        comps_0023 = sol_0023_updated.get("comprobantes", [])
        
        if comps_0023:
            comp_dup = comps_0023[0]
            es_duplicado = comp_dup.get("es_duplicado", False)
            tipo_duplicado = comp_dup.get("tipo_duplicado")
            operacion_original = comp_dup.get("operacion_original")
            
            print(f"\n   Comprobante en operación 0023:")
            print(f"   - es_duplicado: {es_duplicado}")
            print(f"   - tipo_duplicado: {tipo_duplicado}")
            print(f"   - operacion_original: {operacion_original}")
            
            if es_duplicado and tipo_duplicado == "global" and operacion_original == "0022":
                print(f"   ✅ Comprobante correctamente marcado como duplicado global")
            else:
                print(f"   ❌ ERROR: Comprobante no marcado correctamente")
                exito = False
        else:
            print(f"   ⚠️  WARNING: No se encontró comprobante en operación 0023")
    else:
        print(f"❌ ERROR: Sistema NO detectó el duplicado")
        print(f"   El comprobante fue agregado a ambas operaciones (BUG)")
        exito = False
    
    # PRUEBA ADICIONAL: Verificar diferentes estados
    print("\n" + "="*80)
    print("PRUEBA ADICIONAL: Verificar detección en diferentes estados")
    print("="*80)
    
    estados_prueba = [
        ("lista_para_mbc", "debe detectar"),
        ("en_proceso_mbc", "debe detectar"),
        ("completada", "debe detectar"),
        ("rechazada", "NO debe detectar (permite reutilizar)"),
        ("cancelada", "NO debe detectar (permite reutilizar)")
    ]
    
    for idx, (estado, expectativa) in enumerate(estados_prueba, 1):
        # Actualizar estado de operación 0022
        await db.solicitudes_netcash.update_one(
            {"id": "test_op_0022"},
            {"$set": {"estado": estado}}
        )
        
        # Crear nueva operación de prueba
        sol_test = {
            "id": f"test_op_estado_{idx}",
            "solicitud_id": f"test_op_estado_{idx}",
            "folio_mbco": f"test_{idx}",
            "cliente_id": "cliente_test_duplicados",
            "estado": "comprobantes_recibidos",
            "comprobantes": [],
            "created_at": datetime.now(timezone.utc)
        }
        await db.solicitudes_netcash.insert_one(sol_test)
        
        # Intentar agregar el mismo comprobante
        agregado, razon = await netcash_service.agregar_comprobante(
            f"test_op_estado_{idx}",
            str(archivo_test),
            archivo_test.name
        )
        
        debe_detectar = "debe detectar" in expectativa
        
        if debe_detectar:
            if not agregado:
                print(f"   ✅ Estado '{estado}': Duplicado detectado correctamente")
            else:
                print(f"   ❌ Estado '{estado}': ERROR - NO detectó duplicado")
                exito = False
        else:
            if agregado:
                print(f"   ✅ Estado '{estado}': Permitió reutilizar correctamente")
            else:
                print(f"   ⚠️  Estado '{estado}': Detectó duplicado (puede ser correcto)")
    
    print("\n" + "="*80)
    if exito:
        print("✅ TEST PASADO: Detección de duplicados funciona correctamente")
    else:
        print("❌ TEST FALLIDO: Hay problemas con la detección de duplicados")
    print("="*80 + "\n")
    
    # Limpiar archivo de prueba
    if archivo_test.exists():
        archivo_test.unlink()
    
    client.close()
    
    return exito


if __name__ == "__main__":
    resultado = asyncio.run(test_duplicados_globales())
    exit(0 if resultado else 1)
