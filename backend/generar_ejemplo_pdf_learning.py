"""
Script para generar un documento de ejemplo en netcash_pdf_learning

Este script simula el flujo completo:
1. Cliente sube comprobante con OCR fallido
2. Cliente captura datos manualmente
3. Sistema registra en colección de aprendizaje
"""

import asyncio
import os
import json
from datetime import datetime, timezone
from netcash_pdf_learning_service import netcash_pdf_learning_service
from motor.motor_asyncio import AsyncIOMotorClient

async def generar_ejemplo():
    """Genera un documento de ejemplo completo"""
    
    print("📝 Generando documento de ejemplo en netcash_pdf_learning...\n")
    
    # Simular una solicitud completa con captura manual
    solicitud_ejemplo = {
        "id": "nc-ejemplo-001",
        "cliente_id": "CLI_00123",
        "cliente_nombre": "JUAN PEREZ GOMEZ",
        "folio_mbco": "23456-209-M-11",
        "estado": "esperando_validacion_ana",
        
        # Modo de captura (P0)
        "modo_captura": "manual_por_fallo_ocr",
        "origen_montos": "manual_cliente",
        
        # Validación OCR (backend)
        "validacion_ocr": {
            "es_confiable": False,
            "motivo_fallo": "Monto detectado = 0 o inconsistencia",
            "advertencias": ["Banco: ALBO - Monto = $0.00"],
            "banco_detectado": "ALBO"
        },
        
        # Comprobantes subidos
        "comprobantes": [
            {
                "nombre_archivo": "comprobante_albo_001.pdf",
                "archivo_url": "/uploads/comprobantes/nc-ejemplo-001/comprobante_albo_001.pdf",
                "archivo_hash": "sha256:abc123def456789...",
                "es_valido": False,
                "es_duplicado": False,
                "monto_detectado": 0.00,  # OCR falló
                "cuenta_detectada": {},
                "validacion_detalle": {
                    "es_valido": False,
                    "razon": "pdf_sin_texto_legible o monto_cero"
                },
                "ocr_data": {
                    "texto_crudo": "ALBO\nPago\n$0.00\nComisión\n$0.00",
                    "banco": "ALBO"
                }
            },
            {
                "nombre_archivo": "comprobante_albo_002.pdf",
                "archivo_url": "/uploads/comprobantes/nc-ejemplo-001/comprobante_albo_002.pdf",
                "archivo_hash": "sha256:xyz789uvw456123...",
                "es_valido": False,
                "monto_detectado": 0.00,
                "validacion_detalle": {
                    "es_valido": False,
                    "razon": "monto_cero"
                }
            }
        ],
        
        # Datos capturados manualmente (P0)
        "num_comprobantes_declarado": 2,
        "monto_total_declarado": 150000.00,
        "beneficiario_declarado": "SERGIO CORTES LEYVA",
        "clabe_declarada": "699180600000012345",
        "id_beneficiario_frecuente": "bf_a1b2c3d4",
        "ligas_solicitadas": 5,
        
        # Validación pendiente
        "validado_por_ana": False,
        
        # Metadata
        "idmex_reportado": "3456744333",
        "beneficiario_reportado": "SERGIO CORTES LEYVA",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    print("📋 Solicitud simulada:")
    print(f"   ID: {solicitud_ejemplo['id']}")
    print(f"   Cliente: {solicitud_ejemplo['cliente_nombre']}")
    print(f"   Modo captura: {solicitud_ejemplo['modo_captura']}")
    print(f"   Monto declarado: ${solicitud_ejemplo['monto_total_declarado']:,.2f}")
    print(f"   Beneficiario: {solicitud_ejemplo['beneficiario_declarado']}")
    print(f"   Beneficiario frecuente: {solicitud_ejemplo['id_beneficiario_frecuente']}")
    print()
    
    # Registrar en la colección de aprendizaje
    print("💾 Registrando en colección de aprendizaje...")
    registro_id = await netcash_pdf_learning_service.registrar_caso_aprendizaje(
        solicitud=solicitud_ejemplo,
        validado_por_ana=False
    )
    
    if registro_id:
        print(f"✅ Registro creado: {registro_id}\n")
        
        # Obtener el documento completo de MongoDB
        mongo_url = os.getenv('MONGO_URL')
        db_name = os.getenv('DB_NAME', 'netcash_mbco')
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        documento = await db.netcash_pdf_learning.find_one(
            {"id": registro_id},
            {"_id": 0}
        )
        
        if documento:
            print("📄 Documento guardado en MongoDB:\n")
            print("=" * 80)
            # Convertir datetime a string para JSON
            def datetime_to_str(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return obj
            
            # Serializar con indentación
            documento_str = json.dumps(documento, indent=2, default=datetime_to_str, ensure_ascii=False)
            print(documento_str)
            print("=" * 80)
            print()
            
            # Guardar en archivo para referencia
            with open('/app/ejemplo_documento_pdf_learning.json', 'w', encoding='utf-8') as f:
                f.write(documento_str)
            print("📁 Documento guardado en: /app/ejemplo_documento_pdf_learning.json")
            
            # Mostrar estadísticas
            print("\n📊 Generando estadísticas de la colección...")
            stats = await netcash_pdf_learning_service.estadisticas_aprendizaje()
            print(f"\n📈 Estadísticas:")
            print(f"   Total casos: {stats.get('total_casos', 0)}")
            print(f"   Validados por Ana: {stats.get('validados_por_ana', 0)}")
            print(f"   Sin validar: {stats.get('sin_validar', 0)}")
            print(f"   Por banco: {stats.get('por_banco', {})}")
            print(f"   Por estado validación robot: {stats.get('por_estado_validacion_robot', {})}")
    else:
        print("❌ No se pudo crear el registro")

if __name__ == "__main__":
    asyncio.run(generar_ejemplo())
