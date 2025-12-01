"""
Tests para la dispersión de capital en ligas

Verifica que:
1. Cada liga está entre $100,000 y $349,999.99
2. La suma de ligas = capital exacto
3. Los montos son irregulares
4. No hay montos duplicados (o muy pocos)
"""
import sys
import os
sys.path.insert(0, '/app/backend')

from decimal import Decimal
from tesoreria_operacion_service import TesoreriaOperacionService
import random

def test_dispersi on_capital():
    """Test de dispersión de capital en ligas"""
    
    # Fijar seed para tests deterministas
    random.seed(42)
    
    servicio = TesoreriaOperacionService()
    
    print("=" * 80)
    print("TEST: DISPERSIÓN DE CAPITAL EN LIGAS")
    print("=" * 80)
    print()
    
    # Casos de prueba
    casos = [
        Decimal('100000.00'),      # Mínimo
        Decimal('349999.99'),      # Máximo
        Decimal('500000.00'),      # Mediano
        Decimal('1980000.00'),     # Grande (caso real operación 0023)
        Decimal('5000000.00'),     # Muy grande
        Decimal('10000000.00'),    # Extremo
    ]
    
    todos_ok = True
    
    for capital in casos:
        print(f"\n{'='*80}")
        print(f"Probando capital: ${capital:,.2f}")
        print(f"{'='*80}")
        
        ligas = servicio._partir_capital_en_ligas(capital)
        
        print(f"Número de ligas: {len(ligas)}")
        print()
        
        # Verificar cada liga
        min_liga = Decimal('100000.00')
        max_liga = Decimal('349999.99')
        
        errores = []
        
        for i, liga in enumerate(ligas, 1):
            print(f"Liga {i}: ${liga:,.2f}")
            
            # Verificación 1: Rango
            if liga < min_liga:
                errores.append(f"❌ Liga {i} (${liga:,.2f}) es menor que el mínimo (${min_liga:,.2f})")
            elif liga > max_liga:
                errores.append(f"❌ Liga {i} (${liga:,.2f}) es mayor que el máximo (${max_liga:,.2f})")
        
        # Verificación 2: Suma exacta
        suma = sum(ligas)
        diferencia = abs(capital - suma)
        
        print(f"\nSuma de ligas: ${suma:,.2f}")
        print(f"Capital original: ${capital:,.2f}")
        print(f"Diferencia: ${diferencia:.2f}")
        
        if diferencia > Decimal('0.01'):
            errores.append(f"❌ Diferencia entre suma y capital: ${diferencia:.2f} (> $0.01)")
        
        # Verificación 3: Montos irregulares (con centavos)
        montos_con_centavos = [l for l in ligas if (l * Decimal('100')) % Decimal('100') != 0]
        if len(ligas) > 1 and len(montos_con_centavos) == 0:
            print("⚠️  Advertencia: Todos los montos son redondos (sin centavos)")
        else:
            print(f"✅ {len(montos_con_centavos)}/{len(ligas)} montos tienen centavos")
        
        # Verificación 4: No duplicados
        montos_unicos = len(set(ligas))
        if montos_unicos < len(ligas):
            duplicados = len(ligas) - montos_unicos
            print(f"⚠️  Advertencia: Hay {duplicados} monto(s) duplicado(s)")
        else:
            print(f"✅ Todos los montos son únicos")
        
        # Mostrar errores
        if errores:
            print("\n❌ ERRORES ENCONTRADOS:")
            for error in errores:
                print(f"  {error}")
            todos_ok = False
        else:
            print("\n✅ TODAS LAS VERIFICACIONES PASARON")
    
    print()
    print("=" * 80)
    if todos_ok:
        print("✅ TODOS LOS TESTS PASARON")
    else:
        print("❌ ALGUNOS TESTS FALLARON")
    print("=" * 80)
    
    return todos_ok

if __name__ == "__main__":
    resultado = test_dispersi on_capital()
    sys.exit(0 if resultado else 1)
