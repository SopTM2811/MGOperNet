"""
Script de prueba para ejecutar manualmente el proceso de Tesorería
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv('/app/backend/.env')

# Agregar el path del backend
sys.path.insert(0, '/app/backend')

from tesoreria_service import tesoreria_service

async def test_tesoreria():
    print("=" * 60)
    print("PRUEBA MANUAL DEL PROCESO DE TESORERÍA")
    print("=" * 60)
    print()
    
    try:
        print("📋 Ejecutando proceso de lotes de Tesorería...")
        print()
        
        resultado = await tesoreria_service.procesar_lote_tesoreria()
        
        if resultado:
            print()
            print("=" * 60)
            print("✅ LOTE PROCESADO EXITOSAMENTE")
            print("=" * 60)
            print(f"ID Lote: {resultado['id']}")
            print(f"Solicitudes: {resultado['n_solicitudes']}")
            print(f"Total depósitos: ${resultado['total_depositos']:,.2f}")
            print(f"Total capital: ${resultado['total_capital']:,.2f}")
            print(f"Total comisión: ${resultado['total_comision']:,.2f}")
            print()
        else:
            print()
            print("=" * 60)
            print("ℹ️ NO HAY SOLICITUDES PENDIENTES")
            print("=" * 60)
            print()
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ ERROR EN EL PROCESO")
        print("=" * 60)
        print(f"Error: {str(e)}")
        import traceback
        print()
        print("Traceback completo:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_tesoreria())
