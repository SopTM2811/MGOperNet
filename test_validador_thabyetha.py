#!/usr/bin/env python3
"""Script de prueba para validar comprobantes THABYETHA de Banamex"""

import sys
import os
sys.path.insert(0, '/app/backend')

from validador_comprobantes_service import ValidadorComprobantes

# Configuración de la cuenta NetCash THABYETHA
cuenta_activa = {
    "banco": "STP",
    "clabe": "646180139409481462",
    "beneficiario": "JARDINERIA Y COMERCIO THABYETHA SA DE CV"
}

# PDFs a probar
pdfs_thabyetha = [
    "/app/backend/uploads/comprobantes_telegram/nc-1764478071449_THABYETHA SA $185,000.00.pdf",
    "/app/backend/uploads/comprobantes_telegram/nc-1764478071449_THABYETHA SA $179,800.00.pdf",
    "/app/backend/uploads/comprobantes_telegram/nc-1764478071449_THABYETHA SA $135,200.00.pdf"
]

print("=" * 80)
print("PRUEBA DE VALIDACIÓN: COMPROBANTES THABYETHA DE BANAMEX")
print("=" * 80)
print(f"\n📋 Cuenta NetCash Configurada:")
print(f"   • Banco: {cuenta_activa['banco']}")
print(f"   • CLABE: {cuenta_activa['clabe']}")
print(f"   • Beneficiario: {cuenta_activa['beneficiario']}")
print(f"   • Sufijo esperado: {cuenta_activa['clabe'][-3:]}")
print("\n" + "=" * 80)

validador = ValidadorComprobantes()

resultados = []

for i, pdf_path in enumerate(pdfs_thabyetha, 1):
    print(f"\n📄 PRUEBA {i}/3: {os.path.basename(pdf_path)}")
    print("-" * 80)
    
    if not os.path.exists(pdf_path):
        print(f"❌ Archivo no encontrado: {pdf_path}")
        resultados.append(False)
        continue
    
    try:
        es_valido, razon = validador.validar_comprobante(
            ruta_archivo=pdf_path,
            mime_type="application/pdf",
            cuenta_activa=cuenta_activa
        )
        
        if es_valido:
            print(f"✅ VÁLIDO")
            print(f"   Razón: {razon}")
            resultados.append(True)
        else:
            print(f"❌ INVÁLIDO")
            print(f"   Razón: {razon}")
            resultados.append(False)
    
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        resultados.append(False)

print("\n" + "=" * 80)
print("RESUMEN DE PRUEBAS")
print("=" * 80)

total = len(resultados)
exitosos = sum(resultados)
fallidos = total - exitosos

print(f"\n📊 Total de comprobantes probados: {total}")
print(f"✅ Válidos: {exitosos}")
print(f"❌ Inválidos: {fallidos}")

if exitosos == total:
    print("\n🎉 ¡TODAS LAS PRUEBAS PASARON!")
    print("Los comprobantes THABYETHA de Banamex se validan correctamente.")
else:
    print(f"\n⚠️ FALLÓ {fallidos} prueba(s)")
    print("Revisar los logs de validación arriba.")

print("=" * 80)

# Exit code: 0 si todas las pruebas pasan, 1 si hay fallos
sys.exit(0 if exitosos == total else 1)
