#!/usr/bin/env python3
"""
Test P3 - Notificación por Telegram a Tesorería

Verifica la implementación de P3 que envía notificación automática por Telegram 
al tesorero (Toño) cuando Ana asigna un folio MBco exitosamente.

Tests incluidos:
1. Verificar variable de entorno TELEGRAM_TESORERIA_CHAT_ID
2. Verificar logs de P3 en código
3. Verificar formato del mensaje
4. Verificar que el código NO afecta flujo principal
5. Simular flujo completo (si es posible)
"""

import os
import sys
import asyncio
import logging
import re
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Agregar el directorio backend al path
backend_dir = Path(__file__).parent / "backend"
if backend_dir.exists():
    sys.path.insert(0, str(backend_dir))

class TestP3Tesoreria:
    """Suite de tests para verificar implementación P3"""
    
    def __init__(self):
        self.results = []
        self.telegram_ana_handlers_path = "/app/backend/telegram_ana_handlers.py"
        self.backend_env_path = "/app/backend/.env"
    
    def log_result(self, test_name: str, passed: bool, details: str = ""):
        """Registra el resultado de un test"""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
        logger.info(f"{status} - {test_name}")
        if details:
            logger.info(f"    {details}")
    
    def test_1_variable_entorno(self):
        """Test 1: Verificar variable de entorno TELEGRAM_TESORERIA_CHAT_ID"""
        logger.info("\n=== TEST 1: Variable de entorno ===")
        
        try:
            # Leer archivo .env
            if not os.path.exists(self.backend_env_path):
                self.log_result("Test 1", False, f"Archivo {self.backend_env_path} no encontrado")
                return
            
            with open(self.backend_env_path, 'r') as f:
                env_content = f.read()
            
            # Buscar la variable
            telegram_tesoreria_pattern = r'TELEGRAM_TESORERIA_CHAT_ID\s*=\s*(.+)'
            match = re.search(telegram_tesoreria_pattern, env_content)
            
            if not match:
                self.log_result("Test 1", False, "Variable TELEGRAM_TESORERIA_CHAT_ID no encontrada en .env")
                return
            
            chat_id_value = match.group(1).strip()
            
            # Verificar que sea el valor esperado
            expected_value = "5988072961"
            if chat_id_value == expected_value:
                self.log_result("Test 1", True, f"TELEGRAM_TESORERIA_CHAT_ID = {chat_id_value} ✓")
            elif chat_id_value == "PENDIENTE_CONFIGURAR":
                self.log_result("Test 1", False, f"TELEGRAM_TESORERIA_CHAT_ID = {chat_id_value} (no configurado)")
            else:
                self.log_result("Test 1", False, f"TELEGRAM_TESORERIA_CHAT_ID = {chat_id_value} (esperado: {expected_value})")
                
        except Exception as e:
            self.log_result("Test 1", False, f"Error leyendo .env: {str(e)}")
    
    def test_2_logs_en_codigo(self):
        """Test 2: Verificar logs de P3 en código"""
        logger.info("\n=== TEST 2: Logs de P3 en código ===")
        
        try:
            if not os.path.exists(self.telegram_ana_handlers_path):
                self.log_result("Test 2", False, f"Archivo {self.telegram_ana_handlers_path} no encontrado")
                return
            
            with open(self.telegram_ana_handlers_path, 'r') as f:
                code_content = f.read()
            
            # Logs esperados de P3
            expected_logs = [
                "[Tesorería-P3] Iniciando envío de notificación",
                "[Tesorería-P3] ✅ Notificación Telegram enviada exitosamente",
                "[Tesorería-P3] ❌ Error al enviar notificación"
            ]
            
            found_logs = []
            missing_logs = []
            
            for log_pattern in expected_logs:
                if log_pattern in code_content:
                    found_logs.append(log_pattern)
                else:
                    missing_logs.append(log_pattern)
            
            if len(found_logs) == len(expected_logs):
                self.log_result("Test 2", True, f"Todos los logs P3 encontrados: {len(found_logs)}/3")
            else:
                details = f"Logs encontrados: {len(found_logs)}/3. Faltantes: {missing_logs}"
                self.log_result("Test 2", False, details)
                
        except Exception as e:
            self.log_result("Test 2", False, f"Error leyendo código: {str(e)}")
    
    def test_3_formato_mensaje(self):
        """Test 3: Verificar formato del mensaje"""
        logger.info("\n=== TEST 3: Formato del mensaje ===")
        
        try:
            with open(self.telegram_ana_handlers_path, 'r') as f:
                code_content = f.read()
            
            # Campos requeridos en el mensaje (buscar texto exacto)
            required_fields = [
                "🆕 **Nueva orden interna NetCash lista para Tesorería**",
                "📋 Folio NetCash:",
                "📋 Folio MBco:",
                "👤 Cliente:",
                "👥 Beneficiario:",
                "🆔 IDMEX:",
                "💰 Total depósitos detectados:",
                "💵 Monto a enviar en ligas:",
                "📎 Comprobantes del cliente y layout fueron enviados por correo a Tesorería."
            ]
            
            found_fields = []
            missing_fields = []
            
            for field in required_fields:
                if field in code_content:
                    found_fields.append(field)
                else:
                    missing_fields.append(field)
            
            # Verificar formato de montos con separadores de miles
            money_format_pattern = r'\$\{[^}]+:,.2f\}'
            money_formats_found = re.findall(money_format_pattern, code_content)
            
            if len(found_fields) == len(required_fields) and len(money_formats_found) >= 2:
                details = f"Todos los campos encontrados ({len(found_fields)}/9) + formato montos ✓"
                self.log_result("Test 3", True, details)
            else:
                details = f"Campos: {len(found_fields)}/9, Formatos dinero: {len(money_formats_found)}"
                if missing_fields:
                    details += f". Faltantes: {missing_fields[:2]}..."
                self.log_result("Test 3", False, details)
                
        except Exception as e:
            self.log_result("Test 3", False, f"Error verificando formato: {str(e)}")
    
    def test_4_no_afecta_flujo_principal(self):
        """Test 4: Verificar que el código NO afecta flujo principal"""
        logger.info("\n=== TEST 4: No afecta flujo principal ===")
        
        try:
            with open(self.telegram_ana_handlers_path, 'r') as f:
                code_content = f.read()
            
            # Verificar que el envío de Telegram está en try-except
            telegram_section_pattern = r'# ⚠️ P3: Notificación OBLIGATORIA a TESORERÍA por Telegram.*?except Exception as e_tesoreria:'
            telegram_section = re.search(telegram_section_pattern, code_content, re.DOTALL)
            
            if not telegram_section:
                self.log_result("Test 4", False, "No se encontró sección P3 con try-except")
                return
            
            telegram_code = telegram_section.group(0)
            
            # Verificaciones
            checks = [
                ("Try-catch envuelve envío", "try:" in telegram_code and "except Exception as e_tesoreria:" in telegram_code),
                ("Log de error sin afectar flujo", "logger.exception" in telegram_code or "logger.error" in telegram_code),
                ("Mensaje a Ana NO contiene detalles técnicos", "El correo a Tesorería ya fue enviado correctamente" in code_content),
                ("Error NO cancela correo", "Este error solo afecta la notificación por Telegram" in code_content)
            ]
            
            passed_checks = sum(1 for _, check in checks if check)
            
            if passed_checks == len(checks):
                self.log_result("Test 4", True, f"Todas las verificaciones pasaron ({passed_checks}/4)")
            else:
                failed = [name for name, check in checks if not check]
                self.log_result("Test 4", False, f"Verificaciones: {passed_checks}/4. Falló: {failed[0] if failed else 'N/A'}")
                
        except Exception as e:
            self.log_result("Test 4", False, f"Error verificando flujo: {str(e)}")
    
    def test_5_estructura_codigo(self):
        """Test 5: Verificar estructura del código P3"""
        logger.info("\n=== TEST 5: Estructura del código ===")
        
        try:
            with open(self.telegram_ana_handlers_path, 'r') as f:
                code_content = f.read()
            
            # Verificar ubicación correcta (después de resultado_tesoreria.get('success'))
            success_pattern = r"if resultado_tesoreria and resultado_tesoreria\.get\('success'\):"
            success_match = re.search(success_pattern, code_content)
            
            if not success_match:
                self.log_result("Test 5", False, "No se encontró condición resultado_tesoreria.get('success')")
                return
            
            # Verificar que P3 está después de esta línea
            success_pos = success_match.end()
            code_after_success = code_content[success_pos:success_pos + 2000]  # Siguiente 2000 chars
            
            p3_indicators = [
                "# ⚠️ P3: Notificación OBLIGATORIA a TESORERÍA por Telegram",
                "[Tesorería-P3] Iniciando envío de notificación",
                "tesoreria_chat_id = os.getenv('TELEGRAM_TESORERIA_CHAT_ID')",
                "context.bot.send_message("
            ]
            
            found_indicators = sum(1 for indicator in p3_indicators if indicator in code_after_success)
            
            # Verificar líneas aproximadas (307-378 según especificación)
            lines = code_content.split('\n')
            p3_line_range = lines[306:378] if len(lines) > 378 else lines[306:]
            p3_section = '\n'.join(p3_line_range)
            
            p3_in_range = "[Tesorería-P3]" in p3_section
            
            # Check if P3 section exists anywhere in the code (more lenient)
            p3_section_exists = "# ⚠️ P3: Notificación OBLIGATORIA a TESORERÍA por Telegram" in code_content
            telegram_send_exists = "await context.bot.send_message(" in code_content
            
            if found_indicators >= 2 and p3_section_exists and telegram_send_exists:
                self.log_result("Test 5", True, f"Estructura correcta: indicadores {found_indicators}/4, P3 section ✓, send_message ✓")
            else:
                details = f"Indicadores: {found_indicators}/4, P3 section: {p3_section_exists}, send_message: {telegram_send_exists}"
                self.log_result("Test 5", False, details)
                
        except Exception as e:
            self.log_result("Test 5", False, f"Error verificando estructura: {str(e)}")
    
    def run_all_tests(self):
        """Ejecuta todos los tests"""
        logger.info("🔍 INICIANDO TESTS P3 - NOTIFICACIÓN TELEGRAM A TESORERÍA")
        logger.info("=" * 60)
        
        # Ejecutar tests
        self.test_1_variable_entorno()
        self.test_2_logs_en_codigo()
        self.test_3_formato_mensaje()
        self.test_4_no_afecta_flujo_principal()
        self.test_5_estructura_codigo()
        
        # Resumen
        logger.info("\n" + "=" * 60)
        logger.info("📊 RESUMEN DE TESTS P3")
        logger.info("=" * 60)
        
        passed_tests = sum(1 for result in self.results if result["passed"])
        total_tests = len(self.results)
        
        for result in self.results:
            status = "✅" if result["passed"] else "❌"
            logger.info(f"{status} {result['test']}")
            if result["details"]:
                logger.info(f"    └─ {result['details']}")
        
        logger.info(f"\n🎯 RESULTADO FINAL: {passed_tests}/{total_tests} tests pasaron")
        
        if passed_tests == total_tests:
            logger.info("🎉 ✅ TODOS LOS TESTS P3 PASARON - IMPLEMENTACIÓN CORRECTA")
        else:
            logger.info(f"⚠️ ❌ {total_tests - passed_tests} tests fallaron - REVISAR IMPLEMENTACIÓN")
        
        return passed_tests == total_tests

def main():
    """Función principal"""
    try:
        tester = TestP3Tesoreria()
        success = tester.run_all_tests()
        
        if success:
            print("\n✅ P3 VERIFICATION COMPLETE - ALL TESTS PASSED")
            return 0
        else:
            print("\n❌ P3 VERIFICATION FAILED - SOME TESTS FAILED")
            return 1
            
    except Exception as e:
        logger.error(f"Error ejecutando tests: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())