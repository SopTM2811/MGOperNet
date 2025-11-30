"""
Test del validador con los PDFs Vault adjuntos por el usuario
"""
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, '/app/backend')

from validador_comprobantes_service import ValidadorComprobantes
from motor.motor_asyncio import AsyncIOMotorClient

async def test_vault_pdfs():
    # Conectar a MongoDB para obtener cuenta activa
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['netcash_mbco']
    
    # Obtener cuenta activa (Jardinería y Comercio Thabyetha)
    cuenta = await db.config_cuentas_netcash.find_one({"activo": True}, {"_id": 0})
    
    if not cuenta:
        print("❌ No hay cuenta activa configurada")
        return
    
    print("=" * 80)
    print("PRUEBA DE VALIDADOR CON PDFs VAULT")
    print("=" * 80)
    print(f"\n📋 Cuenta activa esperada:")
    print(f"   Banco: {cuenta.get('banco')}")
    print(f"   CLABE: {cuenta.get('clabe')}")
    print(f"   Beneficiario: {cuenta.get('beneficiario')}")
    print()
    
    validador = ValidadorComprobantes()
    
    # PDFs a probar
    pdfs = [
        ("comprobante_30.pdf", "Comprobante 30 (tipo desconocido)"),
        ("jardineria_251128.pdf", "Jardinería - Voucher Vault (esperado: cuenta NO coincide)"),
        ("comprobante_28.pdf", "Comprobante 28 (tipo desconocido)"),
        ("union_agroindustrial.pdf", "Unión Agroindustrial (esperado: beneficiario diferente)")
    ]
    
    for filename, descripcion in pdfs:
        filepath = f"/app/test_vault_pdfs/{filename}"
        
        if not Path(filepath).exists():
            print(f"⚠️  Archivo no encontrado: {filename}")
            continue
        
        print("=" * 80)
        print(f"📄 Probando: {filename}")
        print(f"   Descripción: {descripcion}")
        print("-" * 80)
        
        try:
            es_valido, razon = validador.validar_comprobante(
                ruta_archivo=filepath,
                mime_type='application/pdf',
                cuenta_activa=cuenta
            )
            
            if es_valido:
                print(f"✅ VÁLIDO")
                print(f"   Razón: {razon}")
            else:
                print(f"❌ INVÁLIDO")
                print(f"   Razón: {razon}")
            
        except Exception as e:
            print(f"💥 ERROR GENÉRICO (esto es lo que queremos evitar)")
            print(f"   Tipo: {type(e).__name__}")
            print(f"   Mensaje: {str(e)}")
            
            import traceback
            print(f"\n   Stack trace:")
            traceback.print_exc()
        
        print()
    
    client.close()
    
    print("=" * 80)
    print("FIN DE PRUEBAS")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_vault_pdfs())
