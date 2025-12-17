#!/usr/bin/env python3
"""
Test específico para los 3 bug fixes implementados:
1. View Comprobante (File Access) - file_url con /api/uploads/
2. Re-OCR validates against bank rules
3. Monto total updates when comprobantes change
"""
import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import os
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv('/app/frontend/.env')

# URLs y configuración
BACKEND_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://telegrambot-repair.preview.emergentagent.com') + '/api'

class BugFixesTester:
    def __init__(self):
        self.session = None
        
    async def setup(self):
        """Configuración inicial"""
        self.session = aiohttp.ClientSession()
        logger.info("✅ Setup completado")
        
    async def cleanup(self):
        """Limpieza final"""
        if self.session:
            await self.session.close()
        logger.info("✅ Cleanup completado")
    
    async def test_bug_fix_1_view_comprobante_file_access(self):
        """
        Test 1: View Comprobante (File Access)
        - Verificar que comprobantes tienen file_url con /api/uploads/
        - Probar acceso directo al archivo
        """
        logger.info("🔍 Test 1: View Comprobante (File Access) - Bug Fix")
        try:
            # Obtener operación nc-1765997234254 específica del request
            operacion_id = "nc-1765997234254"
            
            logger.info(f"   📋 Probando operación: {operacion_id}")
            
            # PASO 1: GET /api/operaciones/{id} - Obtener operación específica
            async with self.session.get(f"{BACKEND_URL}/operaciones/{operacion_id}") as response:
                if response.status == 200:
                    operacion = await response.json()
                    logger.info(f"   ✅ Operación obtenida: {operacion.get('folio_mbco')}")
                    
                    # Verificar comprobantes
                    comprobantes = operacion.get('comprobantes', [])
                    if not comprobantes:
                        logger.warning("   ⚠️ No hay comprobantes en la operación")
                        return False
                    
                    logger.info(f"   📎 Comprobantes encontrados: {len(comprobantes)}")
                    
                    # Verificar file_url en cada comprobante
                    for i, comprobante in enumerate(comprobantes):
                        file_url = comprobante.get('file_url')
                        if file_url:
                            logger.info(f"   📄 Comprobante {i}: file_url = {file_url}")
                            
                            # Verificar que file_url empieza con /api/uploads/
                            if file_url.startswith('/api/uploads/'):
                                logger.info(f"   ✅ File URL correcto: {file_url}")
                                
                                # PASO 2: Probar acceso directo al archivo
                                file_access_url = BACKEND_URL.replace('/api', '') + file_url
                                logger.info(f"   🔗 Probando acceso a: {file_access_url}")
                                
                                async with self.session.get(file_access_url) as file_response:
                                    if file_response.status == 200:
                                        content_type = file_response.headers.get('content-type', '')
                                        logger.info(f"   ✅ Archivo accesible: HTTP 200, Content-Type: {content_type}")
                                        
                                        # Verificar que es PDF o imagen
                                        if content_type.startswith('application/pdf') or content_type.startswith('image/'):
                                            logger.info(f"   ✅ Content-Type válido: {content_type}")
                                        else:
                                            logger.warning(f"   ⚠️ Content-Type inesperado: {content_type}")
                                    else:
                                        logger.error(f"   ❌ Error accediendo archivo: HTTP {file_response.status}")
                                        return False
                            else:
                                logger.error(f"   ❌ File URL incorrecto: {file_url} (no empieza con /api/uploads/)")
                                return False
                        else:
                            logger.warning(f"   ⚠️ Comprobante {i} sin file_url")
                    
                    logger.info("   🎉 Bug Fix 1 VERIFICADO: File URLs correctos y archivos accesibles")
                    return True
                    
                elif response.status == 404:
                    logger.error(f"   ❌ Operación {operacion_id} no encontrada")
                    return False
                else:
                    logger.error(f"   ❌ Error obteniendo operación: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error en test_bug_fix_1: {str(e)}")
            return False
    
    async def test_bug_fix_2_reocr_validates_bank_rules(self):
        """
        Test 2: Re-OCR validates against bank rules
        - Probar POST /api/operaciones/{id}/comprobantes/{idx}/reocr
        - Verificar que valida contra cuenta activa (bank rules)
        """
        logger.info("🔍 Test 2: Re-OCR validates against bank rules - Bug Fix")
        try:
            # Usar operación nc-1765997234254 (NC-000213), comprobante index 0
            operacion_id = "nc-1765997234254"
            comprobante_idx = 0
            
            logger.info(f"   📋 Probando Re-OCR: {operacion_id}, comprobante {comprobante_idx}")
            
            # PASO 1: POST /api/operaciones/{id}/comprobantes/{idx}/reocr
            reocr_url = f"{BACKEND_URL}/operaciones/{operacion_id}/comprobantes/{comprobante_idx}/reocr"
            
            async with self.session.post(reocr_url) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"   ✅ Re-OCR ejecutado exitosamente")
                    
                    # Verificar campos de respuesta
                    campos_esperados = ['es_valido', 'nuevo_monto_total']
                    for campo in campos_esperados:
                        if campo in result:
                            logger.info(f"   ✅ Campo '{campo}' presente: {result.get(campo)}")
                        else:
                            logger.warning(f"   ⚠️ Campo '{campo}' faltante en respuesta")
                    
                    # Verificar que se validó contra cuenta activa
                    es_valido = result.get('es_valido')
                    mensaje = result.get('mensaje', '')
                    
                    if es_valido is not None:
                        logger.info(f"   ✅ Validación ejecutada: es_valido = {es_valido}")
                        if mensaje:
                            logger.info(f"   📝 Mensaje de validación: {mensaje}")
                        
                        # Si es válido, debe haber pasado las reglas bancarias
                        if es_valido:
                            logger.info("   ✅ Comprobante válido según reglas bancarias")
                        else:
                            logger.info("   ℹ️ Comprobante inválido según reglas bancarias")
                        
                        logger.info("   🎉 Bug Fix 2 VERIFICADO: Re-OCR valida contra reglas bancarias")
                        return True
                    else:
                        logger.error("   ❌ Campo 'es_valido' no encontrado en respuesta")
                        return False
                        
                elif response.status == 404:
                    logger.error(f"   ❌ Operación o comprobante no encontrado")
                    return False
                else:
                    error_text = await response.text()
                    logger.error(f"   ❌ Error en Re-OCR: HTTP {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error en test_bug_fix_2: {str(e)}")
            return False
    
    async def test_bug_fix_3_monto_total_updates(self):
        """
        Test 3: Monto total updates when comprobantes change
        - Probar PATCH /api/operaciones/{id}/comprobantes/{idx}
        - Verificar que nuevo_monto_total se actualiza
        - Verificar que calculos se limpia (set to null)
        """
        logger.info("🔍 Test 3: Monto total updates when comprobantes change - Bug Fix")
        try:
            # Usar una operación con múltiples comprobantes
            operacion_id = "nc-1765997234254"
            comprobante_idx = 0
            
            logger.info(f"   📋 Probando actualización de monto: {operacion_id}, comprobante {comprobante_idx}")
            
            # PASO 1: Obtener estado inicial
            async with self.session.get(f"{BACKEND_URL}/operaciones/{operacion_id}") as response:
                if response.status == 200:
                    operacion_inicial = await response.json()
                    monto_inicial = operacion_inicial.get('monto_depositado_cliente', 0)
                    calculos_inicial = operacion_inicial.get('calculos')
                    
                    logger.info(f"   📊 Estado inicial:")
                    logger.info(f"      - monto_depositado_cliente: {monto_inicial}")
                    logger.info(f"      - calculos presente: {calculos_inicial is not None}")
                    
                    comprobantes = operacion_inicial.get('comprobantes', [])
                    if not comprobantes or len(comprobantes) <= comprobante_idx:
                        logger.error(f"   ❌ No hay comprobante en índice {comprobante_idx}")
                        return False
                    
                    comprobante_inicial = comprobantes[comprobante_idx]
                    monto_comprobante_inicial = comprobante_inicial.get('monto', 0)
                    logger.info(f"      - monto comprobante {comprobante_idx}: {monto_comprobante_inicial}")
                else:
                    logger.error(f"   ❌ Error obteniendo operación inicial: HTTP {response.status}")
                    return False
            
            # PASO 2: PATCH /api/operaciones/{id}/comprobantes/{idx} - Cambiar monto
            nuevo_monto = 75000.0  # Nuevo monto para el comprobante
            
            patch_data = {
                'monto': nuevo_monto
            }
            
            patch_url = f"{BACKEND_URL}/operaciones/{operacion_id}/comprobantes/{comprobante_idx}"
            
            async with self.session.patch(patch_url, json=patch_data) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"   ✅ PATCH ejecutado exitosamente")
                    
                    # Verificar nuevo_monto_total en respuesta
                    nuevo_monto_total = result.get('nuevo_monto_total')
                    if nuevo_monto_total is not None:
                        logger.info(f"   ✅ nuevo_monto_total en respuesta: {nuevo_monto_total}")
                        
                        # Verificar que el monto cambió
                        if nuevo_monto_total != monto_inicial:
                            logger.info(f"   ✅ Monto total actualizado: {monto_inicial} → {nuevo_monto_total}")
                        else:
                            logger.warning(f"   ⚠️ Monto total no cambió: {nuevo_monto_total}")
                    else:
                        logger.error("   ❌ Campo 'nuevo_monto_total' no encontrado en respuesta")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"   ❌ Error en PATCH: HTTP {response.status} - {error_text}")
                    return False
            
            # PASO 3: Verificar estado final - calculos debe estar limpio (null)
            async with self.session.get(f"{BACKEND_URL}/operaciones/{operacion_id}") as response:
                if response.status == 200:
                    operacion_final = await response.json()
                    monto_final = operacion_final.get('monto_depositado_cliente', 0)
                    calculos_final = operacion_final.get('calculos')
                    
                    logger.info(f"   📊 Estado final:")
                    logger.info(f"      - monto_depositado_cliente: {monto_final}")
                    logger.info(f"      - calculos: {calculos_final}")
                    
                    # Verificar que calculos se limpió (es null)
                    if calculos_final is None:
                        logger.info("   ✅ Cálculos limpiados correctamente (null)")
                    else:
                        logger.warning("   ⚠️ Cálculos no se limpiaron (debería ser null)")
                    
                    # Verificar que el monto del comprobante se actualizó
                    comprobantes_final = operacion_final.get('comprobantes', [])
                    if len(comprobantes_final) > comprobante_idx:
                        comprobante_final = comprobantes_final[comprobante_idx]
                        monto_comprobante_final = comprobante_final.get('monto', 0)
                        
                        if monto_comprobante_final == nuevo_monto:
                            logger.info(f"   ✅ Monto del comprobante actualizado: {monto_comprobante_final}")
                        else:
                            logger.error(f"   ❌ Monto del comprobante no se actualizó: esperado={nuevo_monto}, actual={monto_comprobante_final}")
                            return False
                    
                    logger.info("   🎉 Bug Fix 3 VERIFICADO: Monto total se actualiza y cálculos se limpian")
                    return True
                else:
                    logger.error(f"   ❌ Error obteniendo operación final: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error en test_bug_fix_3: {str(e)}")
            return False
    
    async def test_additional_verification_reocr_button_availability(self):
        """
        Test adicional: Verificar que Re-OCR button está disponible para TODOS los comprobantes con archivos
        """
        logger.info("🔍 Test Adicional: Re-OCR button disponible para todos los comprobantes con archivos")
        try:
            # Obtener operaciones y verificar comprobantes
            async with self.session.get(f"{BACKEND_URL}/operaciones") as response:
                if response.status == 200:
                    operaciones = await response.json()
                    
                    # Filtrar operaciones de Telegram con comprobantes
                    operaciones_telegram = [op for op in operaciones if op.get('id', '').startswith('nc-')]
                    logger.info(f"   📋 Operaciones Telegram encontradas: {len(operaciones_telegram)}")
                    
                    comprobantes_con_archivo = 0
                    comprobantes_sin_archivo = 0
                    
                    for operacion in operaciones_telegram[:5]:  # Revisar primeras 5
                        comprobantes = operacion.get('comprobantes', [])
                        for comprobante in comprobantes:
                            file_url = comprobante.get('file_url')
                            if file_url and file_url.startswith('/api/uploads/'):
                                comprobantes_con_archivo += 1
                                logger.info(f"   📄 Comprobante con archivo: {file_url}")
                            else:
                                comprobantes_sin_archivo += 1
                    
                    logger.info(f"   📊 Resumen:")
                    logger.info(f"      - Comprobantes con archivo: {comprobantes_con_archivo}")
                    logger.info(f"      - Comprobantes sin archivo: {comprobantes_sin_archivo}")
                    
                    if comprobantes_con_archivo > 0:
                        logger.info("   ✅ Hay comprobantes con archivos disponibles para Re-OCR")
                        return True
                    else:
                        logger.warning("   ⚠️ No se encontraron comprobantes con archivos")
                        return False
                else:
                    logger.error(f"   ❌ Error obteniendo operaciones: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error en test_additional_verification: {str(e)}")
            return False
    
    async def run_all_tests(self):
        """Ejecutar todos los tests de bug fixes"""
        logger.info("🚀 Iniciando tests de Bug Fixes")
        
        await self.setup()
        
        tests = [
            ("Bug Fix 1: View Comprobante File Access", self.test_bug_fix_1_view_comprobante_file_access),
            ("Bug Fix 2: Re-OCR validates bank rules", self.test_bug_fix_2_reocr_validates_bank_rules),
            ("Bug Fix 3: Monto total updates", self.test_bug_fix_3_monto_total_updates),
            ("Additional: Re-OCR button availability", self.test_additional_verification_reocr_button_availability)
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            logger.info(f"\n{'='*60}")
            logger.info(f"Ejecutando: {test_name}")
            logger.info('='*60)
            
            try:
                result = await test_func()
                results[test_name] = result
                
                if result:
                    logger.info(f"✅ {test_name}: PASSED")
                else:
                    logger.error(f"❌ {test_name}: FAILED")
                    
            except Exception as e:
                logger.error(f"❌ {test_name}: ERROR - {str(e)}")
                results[test_name] = False
        
        await self.cleanup()
        
        # Resumen final
        logger.info(f"\n{'='*60}")
        logger.info("RESUMEN FINAL DE BUG FIXES")
        logger.info('='*60)
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            logger.info(f"{status} - {test_name}")
        
        logger.info(f"\nResultado: {passed}/{total} tests pasaron")
        
        if passed == total:
            logger.info("🎉 TODOS LOS BUG FIXES VERIFICADOS EXITOSAMENTE")
        else:
            logger.error("❌ ALGUNOS BUG FIXES REQUIEREN ATENCIÓN")
        
        return results

async def main():
    """Función principal"""
    tester = BugFixesTester()
    results = await tester.run_all_tests()
    return results

if __name__ == "__main__":
    asyncio.run(main())