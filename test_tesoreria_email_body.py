"""
Script para generar y visualizar el contenido del email de Tesorería
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('/app/backend/.env')

# Agregar el path del backend
sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
from tesoreria_service import tesoreria_service

async def test_email_body():
    # Conectar a MongoDB
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]
    
    # Obtener un lote procesado
    lote = await db.lotes_tesoreria.find_one({}, {"_id": 0})
    
    if not lote:
        print("No hay lotes creados")
        return
    
    # Obtener las solicitudes del lote
    solicitud_ids = lote.get('solicitudes_ids', [])
    solicitudes = await db.solicitudes_netcash.find(
        {"id": {"$in": solicitud_ids}},
        {"_id": 0}
    ).to_list(100)
    
    print("=" * 80)
    print(f"GENERANDO EMAIL BODY PARA LOTE: {lote.get('id')}")
    print("=" * 80)
    print()
    
    # Generar el cuerpo del email
    email_body = tesoreria_service._generar_cuerpo_correo(lote, solicitudes)
    
    # Guardar en un archivo HTML para visualizar
    output_file = f"/app/test_email_lote_{lote.get('id')}.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(email_body)
    
    print(f"✅ Email body guardado en: {output_file}")
    print()
    print("=" * 80)
    print("PREVIEW DEL CONTENIDO:")
    print("=" * 80)
    print(email_body[:2000])
    print()
    print("[... contenido truncado ...]")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(test_email_body())
