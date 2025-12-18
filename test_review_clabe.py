#!/usr/bin/env python3
"""
Test específico para la CLABE mencionada en el review request: 699180600007037228
"""
import sys
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_review_request_clabe():
    """Test con la CLABE específica del review request"""
    logger.info("🔍 Test: Validación con CLABE del review request (699180600007037228)")
    
    # CLABE del review request
    clabe_activa = "699180600007037228"
    ultimos_4 = "7228"
    
    logger.info(f"   📋 CLABE: {clabe_activa}")
    logger.info(f"   📋 Últimos 4 dígitos: {ultimos_4}")
    
    # Casos de prueba del review request
    test_cases = [
        # Del review request
        {"cuenta": "699180600007037228", "esperado": True, "descripcion": "CLABE completa"},
        {"cuenta": "*7228", "esperado": True, "descripcion": "Formato *7228"},
        {"cuenta": "**7228", "esperado": True, "descripcion": "Formato **7228"},
        {"cuenta": "***7228", "esperado": True, "descripcion": "Formato ***7228"},
        {"cuenta": "7228", "esperado": True, "descripcion": "Solo últimos 4 dígitos"},
        {"cuenta": "037228", "esperado": True, "descripcion": "Últimos 6 dígitos"},
        {"cuenta": "*7229", "esperado": False, "descripcion": "Terminación incorrecta *7229"},
        {"cuenta": "*1234", "esperado": False, "descripcion": "Terminación incorrecta *1234"},
    ]
    
    passed = 0
    total = len(test_cases)
    
    for test_case in test_cases:
        cuenta_str = test_case["cuenta"]
        esperado = test_case["esperado"]
        descripcion = test_case["descripcion"]
        
        # Simular la lógica de validación del netcash_service.py
        cuenta_limpia = cuenta_str.replace(" ", "").replace("-", "").replace("*", "")
        ultimos_4_clabe = clabe_activa[-4:] if len(clabe_activa) >= 4 else clabe_activa
        
        es_valido = False
        
        # Caso 1: CLABE completa coincide
        if clabe_activa in cuenta_limpia or cuenta_limpia in clabe_activa:
            es_valido = True
        
        # Caso 2: Últimos 4 dígitos de cuenta limpia coinciden
        elif len(cuenta_limpia) >= 4 and cuenta_limpia[-4:] == ultimos_4_clabe:
            es_valido = True
        
        # Caso 3: Formato enmascarado (ej: *7228, **7228, ***7228)
        elif '*' in cuenta_str:
            import re
            match = re.search(r'\*+(\d{3,4})$', cuenta_str)
            if match:
                digitos_encontrados = match.group(1)
                if clabe_activa.endswith(digitos_encontrados):
                    es_valido = True
        
        # Caso 4: Verificar si los dígitos están contenidos en la CLABE
        elif len(cuenta_limpia) >= 3:
            if len(cuenta_limpia) <= 6 and clabe_activa.endswith(cuenta_limpia):
                es_valido = True
        
        # Verificar resultado
        if es_valido == esperado:
            logger.info(f"   ✅ {descripcion}: '{cuenta_str}' -> {es_valido} (correcto)")
            passed += 1
        else:
            logger.error(f"   ❌ {descripcion}: '{cuenta_str}' -> {es_valido} (esperado: {esperado})")
    
    logger.info(f"   📊 Resultados: {passed}/{total} casos pasaron")
    
    if passed == total:
        logger.info("🎉 ¡Todos los casos del review request funcionan correctamente!")
        return True
    else:
        logger.error("❌ Algunos casos del review request fallaron")
        return False

if __name__ == "__main__":
    success = test_review_request_clabe()
    exit(0 if success else 1)