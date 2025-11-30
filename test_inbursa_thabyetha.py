#!/usr/bin/env python3
"""
Test específico para comprobante Inbursa THABYETHA
Bug: Beneficiario detectado OK, CLABE marcada como no coincidente
"""

import sys
import logging
sys.path.insert(0, '/app/backend')

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

from validador_comprobantes_service import ValidadorComprobantes

# Cuenta NetCash autorizada
CUENTA_ACTIVA = {
    "banco": "STP",
    "clabe": "646180139409481462",
    "beneficiario": "JARDINERIA Y COMERCIO THABYETHA SA DE CV"
}

def main():
    print("=" * 80)
    print("TEST: Comprobante Inbursa THABYETHA")
    print("=" * 80)
    
    archivo_pdf = "/app/uploads/inbursa_test/16413089245271125.pdf"
    
    print(f"\n📄 Archivo: {archivo_pdf}")
    print(f"🏦 Cuenta activa:")
    print(f"   Banco: {CUENTA_ACTIVA['banco']}")
    print(f"   CLABE: {CUENTA_ACTIVA['clabe']}")
    print(f"   Beneficiario: {CUENTA_ACTIVA['beneficiario']}")
    
    validador = ValidadorComprobantes()
    
    # PASO 1: Extraer texto
    print(f"\n📝 PASO 1: Extrayendo texto del PDF...")
    texto = validador.extraer_texto_pdf(archivo_pdf)
    print(f"   Texto extraído: {len(texto)} caracteres")
    print(f"\n   Primeros 500 caracteres:")
    print(f"   {texto[:500]}")
    
    # PASO 2: Extraer CLABEs
    print(f"\n🔍 PASO 2: Extrayendo CLABEs de 18 dígitos...")
    clabes = validador.extraer_clabes_del_texto(texto)
    print(f"   CLABEs encontradas: {clabes}")
    
    for clabe in clabes:
        if clabe == CUENTA_ACTIVA['clabe']:
            print(f"   ✅ CLABE objetivo {clabe} SÍ está en el texto")
        else:
            print(f"   ⚠️ CLABE {clabe} encontrada pero NO es la objetivo")
    
    # PASO 3: Buscar CLABE con contexto
    print(f"\n🎯 PASO 3: Buscando CLABE objetivo con contexto...")
    clabe_encontrada, metodo = validador.buscar_clabe_en_texto(
        texto,
        CUENTA_ACTIVA['clabe']
    )
    print(f"   Resultado: encontrada={clabe_encontrada}, metodo={metodo}")
    
    # PASO 4: Buscar beneficiario
    print(f"\n👤 PASO 4: Buscando beneficiario...")
    beneficiario_encontrado = validador.buscar_beneficiario_en_texto(
        texto,
        CUENTA_ACTIVA['beneficiario']
    )
    print(f"   Resultado: encontrado={beneficiario_encontrado}")
    
    # PASO 5: Validación completa
    print(f"\n✅ PASO 5: Validación completa del comprobante...")
    es_valido, razon = validador.validar_comprobante(
        ruta_archivo=archivo_pdf,
        mime_type="application/pdf",
        cuenta_activa=CUENTA_ACTIVA
    )
    
    print(f"\n{'='*80}")
    print(f"RESULTADO FINAL:")
    print(f"{'='*80}")
    print(f"   es_valido: {es_valido}")
    print(f"   razon: {razon}")
    
    if es_valido:
        print(f"\n✅ ¡COMPROBANTE VÁLIDO!")
        return 0
    else:
        print(f"\n❌ COMPROBANTE INVÁLIDO")
        print(f"\n🐛 BUG DETECTADO:")
        print(f"   - Beneficiario encontrado: {beneficiario_encontrado}")
        print(f"   - CLABE encontrada: {clabe_encontrada}")
        print(f"   - Método CLABE: {metodo}")
        print(f"   - Razón de rechazo: {razon}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
