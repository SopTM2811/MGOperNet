#!/usr/bin/env python3
"""
Script de prueba para validar comprobantes THABYETHA de montos pequeños
Bug reportado: CLABE completa 646180139409481462 no se detecta en PDFs con "Clabe Receptor"
"""

import sys
sys.path.insert(0, '/app/backend')

from validador_comprobantes_service import ValidadorComprobantes

# Cuenta NetCash activa de THABYETHA
CUENTA_ACTIVA = {
    "banco": "STP",
    "clabe": "646180139409481462",
    "beneficiario": "JARDINERIA Y COMERCIO THABYETHA SA DE CV"
}

# Lista de archivos de prueba
TEST_FILES = [
    "/app/backend/uploads/comprobantes/THABYETHA_2500.pdf",
    "/app/backend/uploads/comprobantes/THABYETHA_5000.pdf",
    "/app/backend/uploads/comprobantes/THABYETHA_4695.pdf",
    "/app/backend/uploads/comprobantes/THABYETHA_9400.pdf",
]

def main():
    validador = ValidadorComprobantes()
    
    print("=" * 80)
    print("TEST: Validación de comprobantes THABYETHA (montos pequeños)")
    print("=" * 80)
    print(f"\nCuenta activa:")
    print(f"  Banco: {CUENTA_ACTIVA['banco']}")
    print(f"  CLABE: {CUENTA_ACTIVA['clabe']}")
    print(f"  Beneficiario: {CUENTA_ACTIVA['beneficiario']}")
    print("\n" + "=" * 80)
    
    # Primero probemos con texto de ejemplo directo
    texto_ejemplo = """
    unalanaPAY
    La última generación de Banca Electrónica 24/7
    
    COMERCIALIZADORA INVERMEX SA DE CV
    Institución Ordenante: KUSPIT/UnalanaPAY
    Cuenta: 653180003810172861
    
    Por este conducto le informamos que se ha realizado un pago desde su cuenta hacia 
    JARDINERIA Y COMERCIO THABYETHA SA DE CV de acuerdo a lo siguiente:
    
    Id Transaccion
    0102772781
    
    Clave de Rastreo
    UNALANAPAY0117810163
    
    Beneficiario
    JARDINERIA Y COMERCIO THABYETHA SA DE CV
    
    Institución Receptora
    STP
    
    Clabe Receptor
    646180139409481462
    
    Email
    
    Referencia
    4970049
    
    Concepto
    TERCEROS 4970049
    
    Importe
    2,500.00
    
    Fecha
    2025-11-28 12:11:29
    """
    
    print("\n🧪 PRUEBA 1: Extracción de CLABEs del texto de ejemplo")
    print("-" * 80)
    clabes_extraidas = validador.extraer_clabes_del_texto(texto_ejemplo)
    print(f"CLABEs extraídas: {clabes_extraidas}")
    
    if "646180139409481462" in clabes_extraidas:
        print("✅ CLABE 646180139409481462 detectada correctamente")
    else:
        print("❌ CLABE 646180139409481462 NO detectada")
    
    print("\n🧪 PRUEBA 2: Búsqueda de CLABE en texto")
    print("-" * 80)
    clabe_encontrada, metodo = validador.buscar_clabe_en_texto(
        texto_ejemplo, 
        CUENTA_ACTIVA['clabe']
    )
    print(f"Resultado: encontrada={clabe_encontrada}, metodo={metodo}")
    
    if clabe_encontrada and metodo == "completa":
        print("✅ CLABE encontrada con método 'completa'")
    else:
        print(f"❌ CLABE no encontrada o método incorrecto (metodo={metodo})")
    
    print("\n🧪 PRUEBA 3: Búsqueda de beneficiario")
    print("-" * 80)
    beneficiario_encontrado = validador.buscar_beneficiario_en_texto(
        texto_ejemplo,
        CUENTA_ACTIVA['beneficiario']
    )
    print(f"Beneficiario encontrado: {beneficiario_encontrado}")
    
    if beneficiario_encontrado:
        print("✅ Beneficiario encontrado correctamente")
    else:
        print("❌ Beneficiario NO encontrado")
    
    print("\n" + "=" * 80)
    print("RESUMEN DE PRUEBAS:")
    print("=" * 80)
    
    if "646180139409481462" in clabes_extraidas and clabe_encontrada and beneficiario_encontrado:
        print("✅ ¡TODAS LAS PRUEBAS PASARON!")
        print("✅ El bug está RESUELTO")
        return 0
    else:
        print("❌ ALGUNAS PRUEBAS FALLARON")
        print("❌ El bug AÚN PERSISTE")
        return 1

if __name__ == "__main__":
    sys.exit(main())
