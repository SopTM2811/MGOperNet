#!/usr/bin/env python3
"""
Test con los PDFs reales de THABYETHA de montos pequeños
"""

import sys
import logging
import os
import urllib.request
import tempfile

sys.path.insert(0, '/app/backend')

logging.basicConfig(
    level=logging.WARNING,  # Solo mostrar warnings y errores
    format='%(message)s'
)

from validador_comprobantes_service import ValidadorComprobantes

CUENTA_ACTIVA = {
    "banco": "STP",
    "clabe": "646180139409481462",
    "beneficiario": "JARDINERIA Y COMERCIO THABYETHA SA DE CV"
}

# URLs de los PDFs
TEST_PDFS = [
    {
        "url": "https://customer-assets.emergentagent.com/job_telegram-web-sync-2/artifacts/l4dxssxk_JARDINERIA_Y_COMERCIO_THABYETHA_%242%2C500.00.pdf",
        "nombre": "THABYETHA_$2,500.00",
        "monto_esperado": 2500.00
    },
    {
        "url": "https://customer-assets.emergentagent.com/job_telegram-web-sync-2/artifacts/5n4wuxt1_JARDINERIA_Y_COMERCIO_THABYETHA_%244%2C695.00.pdf",
        "nombre": "THABYETHA_$4,695.00",
        "monto_esperado": 4695.00
    },
    {
        "url": "https://customer-assets.emergentagent.com/job_telegram-web-sync-2/artifacts/6jpqxezd_JARDINERIA_Y_COMERCIO_THABYETHA_%245%2C000.00.pdf",
        "nombre": "THABYETHA_$5,000.00",
        "monto_esperado": 5000.00
    },
    {
        "url": "https://customer-assets.emergentagent.com/job_telegram-web-sync-2/artifacts/w0xikuyp_JARDINERIA_Y_COMERCIO_THABYETHA_%249%2C400.00.pdf",
        "nombre": "THABYETHA_$9,400.00",
        "monto_esperado": 9400.00
    }
]

def descargar_pdf(url: str, nombre: str) -> str:
    """Descarga un PDF desde URL y lo guarda temporalmente"""
    tmp_dir = "/tmp/test_pdfs"
    os.makedirs(tmp_dir, exist_ok=True)
    
    filepath = os.path.join(tmp_dir, f"{nombre}.pdf")
    
    # Descargar
    with urllib.request.urlopen(url) as response:
        pdf_data = response.read()
    
    # Guardar
    with open(filepath, 'wb') as f:
        f.write(pdf_data)
    
    return filepath

def main():
    validador = ValidadorComprobantes()
    
    print("=" * 80)
    print("TEST: Validación de PDFs Reales THABYETHA (montos pequeños)")
    print("=" * 80)
    print(f"\nCuenta NetCash activa:")
    print(f"  Banco: {CUENTA_ACTIVA['banco']}")
    print(f"  CLABE: {CUENTA_ACTIVA['clabe']}")
    print(f"  Beneficiario: {CUENTA_ACTIVA['beneficiario']}")
    print("\n" + "=" * 80)
    
    resultados = []
    
    for pdf_info in TEST_PDFS:
        print(f"\n📄 Procesando: {pdf_info['nombre']}")
        print("-" * 80)
        
        try:
            # Descargar PDF
            print(f"   Descargando PDF...")
            pdf_path = descargar_pdf(pdf_info['url'], pdf_info['nombre'])
            print(f"   ✓ PDF descargado: {pdf_path}")
            
            # Extraer texto del PDF
            print(f"   Extrayendo texto...")
            texto = validador.extraer_texto_pdf(pdf_path)
            
            if not texto or len(texto) < 50:
                print(f"   ❌ ERROR: No se pudo extraer texto del PDF")
                resultados.append(False)
                continue
            
            print(f"   ✓ Texto extraído ({len(texto)} caracteres)")
            
            # Validar comprobante usando el método completo
            print(f"   Validando CLABE y beneficiario...")
            es_valido, razon = validador.validar_comprobante(
                ruta_archivo=pdf_path,
                mime_type="application/pdf",
                cuenta_activa=CUENTA_ACTIVA
            )
            
            if es_valido:
                print(f"   ✅ VÁLIDO: {razon}")
                resultados.append(True)
            else:
                print(f"   ❌ INVÁLIDO: {razon}")
                resultados.append(False)
                
        except Exception as e:
            print(f"   ❌ ERROR: {str(e)}")
            resultados.append(False)
    
    # Resumen
    print("\n" + "=" * 80)
    print("RESUMEN DE VALIDACIÓN:")
    print("=" * 80)
    
    total = len(resultados)
    validos = sum(resultados)
    
    print(f"\nTotal de PDFs probados: {total}")
    print(f"PDFs válidos: {validos}")
    print(f"PDFs inválidos: {total - validos}")
    
    if validos == total:
        print("\n🎉 ✅ ¡TODOS LOS COMPROBANTES PASARON LA VALIDACIÓN!")
        print("✅ El bug está COMPLETAMENTE RESUELTO")
        return 0
    else:
        print(f"\n⚠️ ❌ SOLO {validos}/{total} COMPROBANTES PASARON")
        print("❌ El bug AÚN PERSISTE en algunos casos")
        return 1

if __name__ == "__main__":
    sys.exit(main())
