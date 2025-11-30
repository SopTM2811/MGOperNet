"""
Test con el PDF REAL reportado por el usuario que falla en Telegram
PAGO - SOLVER - JARDINERIA - EFE NANCY - 4 - 26 NOV 25.pdf

Este test debe pasar para confirmar que el fuzzy matching funciona
con el PDF exacto que está fallando en producción.
"""

import sys
import os
import logging
sys.path.insert(0, '/app/backend')

# Activar logging detallado
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

from validador_comprobantes_service import ValidadorComprobantes

def test_pdf_real_solver_jardineria():
    """
    Test con el PDF REAL que el usuario reporta como fallando en Telegram
    """
    print("\n" + "="*80)
    print("TEST: PDF REAL - SOLVER/JARDINERIA (4 - 26 NOV 25)")
    print("="*80)
    
    # Descargar el PDF primero
    import requests
    pdf_url = "https://customer-assets.emergentagent.com/job_payslip-verify-1/artifacts/ibq6l1md_PAGO%20-%20SOLVER%20-%20JARDINERIA%20-%20EFE%20NANCY%20-%204%20-%2026%20NOV%2025.pdf"
    
    pdf_path = "/tmp/PAGO_SOLVER_JARDINERIA_4_26NOV25.pdf"
    
    print(f"\n📥 Descargando PDF desde: {pdf_url}")
    response = requests.get(pdf_url)
    
    if response.status_code != 200:
        print(f"❌ ERROR: No se pudo descargar el PDF (status={response.status_code})")
        return False
    
    with open(pdf_path, 'wb') as f:
        f.write(response.content)
    
    print(f"✅ PDF descargado: {pdf_path} ({len(response.content)} bytes)")
    
    # Datos de la cuenta activa (exactamente como los usa Telegram)
    cuenta_activa = {
        'banco': 'STP',
        'clabe': '646180139409481462',
        'beneficiario': 'JARDINERIA Y COMERCIO THABYETHA SA DE CV'
    }
    
    print(f"\n📋 Cuenta NetCash activa:")
    print(f"   Banco: {cuenta_activa['banco']}")
    print(f"   CLABE: {cuenta_activa['clabe']}")
    print(f"   Beneficiario: {cuenta_activa['beneficiario']}")
    
    # Crear validador y validar
    print(f"\n🔍 Validando comprobante...")
    validador = ValidadorComprobantes()
    
    es_valido, razon = validador.validar_comprobante(
        ruta_archivo=pdf_path,
        mime_type='application/pdf',
        cuenta_activa=cuenta_activa
    )
    
    print(f"\n" + "="*80)
    print(f"RESULTADO DE LA VALIDACIÓN")
    print(f"="*80)
    print(f"es_valido: {es_valido}")
    print(f"razon: {razon}")
    print(f"="*80)
    
    if es_valido:
        print(f"\n✅ ÉXITO: El comprobante fue validado correctamente")
        print(f"✅ El fuzzy matching funcionó como se esperaba")
        return True
    else:
        print(f"\n❌ FALLO: El comprobante fue RECHAZADO")
        print(f"❌ Razón: {razon}")
        print(f"\n⚠️ ESTO ES UN BUG: El comprobante debería ser VÁLIDO")
        print(f"   - CLABE: 646180139409481462 (exacta en el PDF)")
        print(f"   - Beneficiario OCR: ARDINERIA Y COMERCIO THABYETHA SA DE CV")
        print(f"   - Beneficiario esperado: JARDINERIA Y COMERCIO THABYETHA SA DE CV")
        print(f"   - Error OCR: Falta la 'J' inicial")
        print(f"   - Fuzzy score esperado: ~0.98 (> 0.85)")
        return False


def main():
    print("\n" + "="*80)
    print("TEST CON PDF REAL REPORTADO POR EL USUARIO")
    print("="*80)
    
    try:
        resultado = test_pdf_real_solver_jardineria()
        
        if resultado:
            print(f"\n🎉 TEST PASÓ: El PDF real es validado correctamente")
            print(f"✅ El fuzzy matching funciona en el flujo integrado")
            return True
        else:
            print(f"\n⚠️ TEST FALLÓ: El PDF real fue rechazado incorrectamente")
            print(f"❌ Revisar logs arriba para identificar el problema")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR EJECUTANDO EL TEST: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
