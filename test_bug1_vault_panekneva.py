"""
Test para Bug 1: Validador NO reconoce comprobante Vault/Panekneva

Comprobante: JARDINERIA 1,507,500.00.pdf
CLABE destino: 646180139409481462
Beneficiario: JARDINERIA Y COMERCIO THABYETHA SA DE CV
Banco: STP
Layout: Vault/Panekneva con "Cuenta de retiro" (ORIGEN) y "Cuenta de depósito" (DESTINO)
"""

import sys
sys.path.insert(0, '/app/backend')

from validador_comprobantes_service import ValidadorComprobantes

def test_vault_panekneva_layout():
    """Test para validar que el validador reconoce el layout Vault/Panekneva"""
    
    print("="*80)
    print("TEST: Validador con layout Vault/Panekneva (Bug Fix)")
    print("="*80)
    
    # Cuenta activa esperada
    cuenta_activa = {
        "banco": "STP",
        "clabe": "646180139409481462",
        "beneficiario": "JARDINERIA Y COMERCIO THABYETHA SA DE CV"
    }
    
    # Path al PDF descargado
    pdf_path = "/tmp/jardineria_test.pdf"
    mime_type = "application/pdf"
    
    # Crear instancia del validador
    validador = ValidadorComprobantes()
    
    print(f"\nArchivo a validar: {pdf_path}")
    print(f"Cuenta esperada:")
    print(f"  - Banco: {cuenta_activa['banco']}")
    print(f"  - CLABE: {cuenta_activa['clabe']}")
    print(f"  - Beneficiario: {cuenta_activa['beneficiario']}")
    print("\n" + "-"*80)
    
    # Ejecutar validación
    es_valido, razon = validador.validar_comprobante(pdf_path, mime_type, cuenta_activa)
    
    print("\n" + "="*80)
    print("RESULTADO DE LA VALIDACIÓN")
    print("="*80)
    print(f"✅ Es válido: {es_valido}")
    print(f"📄 Razón: {razon}")
    print("="*80)
    
    # Verificar resultado esperado
    if es_valido:
        print("\n🎉 ¡TEST EXITOSO! El validador ahora reconoce el layout Vault/Panekneva")
        return True
    else:
        print("\n❌ TEST FALLIDO: El validador NO reconoció el comprobante")
        print(f"   Razón del rechazo: {razon}")
        return False

if __name__ == "__main__":
    exito = test_vault_panekneva_layout()
    sys.exit(0 if exito else 1)
