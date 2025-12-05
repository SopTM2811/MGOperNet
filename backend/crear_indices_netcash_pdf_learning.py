"""
Script para crear índices en la colección netcash_pdf_learning

Índices sugeridos:
- id_operacion (unique)
- idmex
- banco_probable
- es_caso_entrenamiento
- fecha
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

async def crear_indices():
    """Crea los índices necesarios en la colección netcash_pdf_learning"""
    
    # Conexión MongoDB
    mongo_url = os.getenv('MONGO_URL')
    db_name = os.getenv('DB_NAME', 'netcash_mbco')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    collection = db.netcash_pdf_learning
    
    print("📊 Creando índices en netcash_pdf_learning...")
    
    # 1. Índice único en id_operacion
    await collection.create_index("id_operacion", unique=True)
    print("✅ Índice único creado: id_operacion")
    
    # 2. Índice en idmex
    await collection.create_index("idmex")
    print("✅ Índice creado: idmex")
    
    # 3. Índice en banco_probable
    await collection.create_index("banco_probable")
    print("✅ Índice creado: banco_probable")
    
    # 4. Índice en es_caso_entrenamiento
    await collection.create_index("es_caso_entrenamiento")
    print("✅ Índice creado: es_caso_entrenamiento")
    
    # 5. Índice en fecha (descendente para queries recientes)
    await collection.create_index("fecha", direction=-1)
    print("✅ Índice creado: fecha (descendente)")
    
    # 6. Índice compuesto para queries comunes
    await collection.create_index([
        ("es_caso_entrenamiento", 1),
        ("banco_probable", 1),
        ("fecha", -1)
    ])
    print("✅ Índice compuesto creado: es_caso_entrenamiento + banco_probable + fecha")
    
    # 7. Índice compuesto para casos sin validar
    await collection.create_index([
        ("datos_finales.validado_por_ana", 1),
        ("fecha", -1)
    ])
    print("✅ Índice compuesto creado: validado_por_ana + fecha")
    
    # Listar todos los índices
    print("\n📋 Índices actuales en la colección:")
    indices = await collection.index_information()
    for nombre, info in indices.items():
        print(f"   - {nombre}: {info.get('key')}")
    
    print("\n✅ Índices creados correctamente")

if __name__ == "__main__":
    asyncio.run(crear_indices())
