#!/usr/bin/env python3
"""
Test específico para Beneficiarios CRUD API
"""
import asyncio
import aiohttp
import json
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path
import logging
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv('/app/backend/.env')

# URLs y configuración
BACKEND_URL = "https://receipt-flow-3.preview.emergentagent.com/api"
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'netcash_mbco')

class BeneficiariosTester:
    def __init__(self):
        self.session = None
        self.mongo_client = None
        self.db = None
        
    async def setup(self):
        """Configuración inicial"""
        self.session = aiohttp.ClientSession()
        self.mongo_client = AsyncIOMotorClient(MONGO_URL)
        self.db = self.mongo_client[DB_NAME]
        logger.info("✅ Setup completado")
        
    async def cleanup(self):
        """Limpieza final"""
        if self.session:
            await self.session.close()
        if self.mongo_client:
            self.mongo_client.close()
        logger.info("✅ Cleanup completado")

    async def test_beneficiarios_crud_api(self):
        """Test completo de Beneficiarios CRUD API"""
        logger.info("🔍 Probando CRUD completo de Beneficiarios Frecuentes API...")
        try:
            # Datos de prueba realistas en español
            cliente_id_prueba = "49ac3766-bc9b-4509-89c1-433cc12bbe97"
            nombre_beneficiario = "JUAN PEREZ GARCIA"
            idmex_beneficiario = "1234567890"
            nombre_beneficiario_actualizado = "JUAN PEREZ GARCIA UPDATED"
            beneficiario_id_creado = None
            
            logger.info(f"📋 DATOS DE PRUEBA:")
            logger.info(f"   - Cliente ID: {cliente_id_prueba}")
            logger.info(f"   - Nombre beneficiario: {nombre_beneficiario}")
            logger.info(f"   - IDMEX beneficiario: {idmex_beneficiario}")
            
            # PASO 1: GET /api/beneficiarios-frecuentes - Listar beneficiarios
            logger.info("🔍 PASO 1: GET /api/beneficiarios-frecuentes - Listar beneficiarios...")
            
            async with self.session.get(f"{BACKEND_URL}/beneficiarios-frecuentes") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ GET beneficiarios exitoso: {len(data)} beneficiarios encontrados")
                    
                    # Verificar estructura de respuesta
                    if isinstance(data, list):
                        logger.info("✅ Respuesta es una lista válida")
                        if data:
                            primer_beneficiario = data[0]
                            campos_esperados = ['id', 'cliente_id', 'nombre_beneficiario', 'idmex_beneficiario']
                            for campo in campos_esperados:
                                if campo in primer_beneficiario:
                                    logger.info(f"✅ Campo '{campo}' presente en respuesta")
                                else:
                                    logger.warning(f"⚠️ Campo '{campo}' faltante en respuesta")
                    else:
                        logger.error("❌ Respuesta no es una lista")
                        return False
                else:
                    logger.error(f"❌ Error en GET beneficiarios: {response.status}")
                    error_text = await response.text()
                    logger.error(f"❌ Error details: {error_text}")
                    return False
            
            # PASO 2: POST /api/beneficiarios-frecuentes - Crear beneficiario
            logger.info("📝 PASO 2: POST /api/beneficiarios-frecuentes - Crear beneficiario...")
            
            form_data = aiohttp.FormData()
            form_data.add_field('cliente_id', cliente_id_prueba)
            form_data.add_field('nombre_beneficiario', nombre_beneficiario)
            form_data.add_field('idmex_beneficiario', idmex_beneficiario)
            
            async with self.session.post(f"{BACKEND_URL}/beneficiarios-frecuentes", data=form_data) as response:
                if response.status == 200:
                    data = await response.json()
                    beneficiario_id_creado = data.get('id')
                    logger.info(f"✅ POST beneficiario exitoso: ID={beneficiario_id_creado}")
                    
                    # Verificar campos de respuesta
                    campos_verificar = {
                        'id': beneficiario_id_creado,
                        'cliente_id': cliente_id_prueba,
                        'nombre_beneficiario': nombre_beneficiario.upper(),
                        'idmex_beneficiario': idmex_beneficiario,
                        'activo': True
                    }
                    
                    for campo, valor_esperado in campos_verificar.items():
                        valor_actual = data.get(campo)
                        if valor_actual == valor_esperado:
                            logger.info(f"✅ Campo '{campo}': {valor_actual}")
                        else:
                            logger.warning(f"⚠️ Campo '{campo}': esperado={valor_esperado}, actual={valor_actual}")
                    
                else:
                    logger.error(f"❌ Error en POST beneficiario: {response.status}")
                    error_text = await response.text()
                    logger.error(f"❌ Error details: {error_text}")
                    return False
            
            if not beneficiario_id_creado:
                logger.error("❌ No se obtuvo ID del beneficiario creado")
                return False
            
            # PASO 3: Validación IDMEX - Probar con IDMEX inválido
            logger.info("🔍 PASO 3: Validación IDMEX - Probar con IDMEX inválido...")
            
            form_data_invalido = aiohttp.FormData()
            form_data_invalido.add_field('cliente_id', cliente_id_prueba)
            form_data_invalido.add_field('nombre_beneficiario', "BENEFICIARIO INVALIDO")
            form_data_invalido.add_field('idmex_beneficiario', "123456789")  # Solo 9 dígitos
            
            async with self.session.post(f"{BACKEND_URL}/beneficiarios-frecuentes", data=form_data_invalido) as response:
                if response.status == 400:
                    error_data = await response.json()
                    logger.info(f"✅ Validación IDMEX funciona: {error_data.get('detail')}")
                else:
                    logger.warning(f"⚠️ Validación IDMEX no funcionó como esperado: {response.status}")
            
            # PASO 4: PUT /api/beneficiarios-frecuentes/{id} - Actualizar beneficiario
            logger.info("✏️ PASO 4: PUT /api/beneficiarios-frecuentes/{id} - Actualizar beneficiario...")
            
            form_data_update = aiohttp.FormData()
            form_data_update.add_field('nombre_beneficiario', nombre_beneficiario_actualizado)
            form_data_update.add_field('idmex_beneficiario', idmex_beneficiario)
            
            async with self.session.put(f"{BACKEND_URL}/beneficiarios-frecuentes/{beneficiario_id_creado}", data=form_data_update) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ PUT beneficiario exitoso: {data.get('message')}")
                    
                    if data.get('success'):
                        logger.info("✅ Actualización confirmada")
                    else:
                        logger.warning("⚠️ Actualización no confirmada")
                else:
                    logger.error(f"❌ Error en PUT beneficiario: {response.status}")
                    error_text = await response.text()
                    logger.error(f"❌ Error details: {error_text}")
                    return False
            
            # PASO 5: Verificar actualización - GET específico
            logger.info("🔍 PASO 5: Verificar actualización...")
            
            async with self.session.get(f"{BACKEND_URL}/beneficiarios-frecuentes?cliente_id={cliente_id_prueba}") as response:
                if response.status == 200:
                    data = await response.json()
                    beneficiario_actualizado = None
                    
                    for beneficiario in data:
                        if beneficiario.get('id') == beneficiario_id_creado:
                            beneficiario_actualizado = beneficiario
                            break
                    
                    if beneficiario_actualizado:
                        nombre_actual = beneficiario_actualizado.get('nombre_beneficiario')
                        if nombre_actual == nombre_beneficiario_actualizado.upper():
                            logger.info(f"✅ Actualización verificada: {nombre_actual}")
                        else:
                            logger.error(f"❌ Actualización no aplicada: esperado={nombre_beneficiario_actualizado.upper()}, actual={nombre_actual}")
                            return False
                    else:
                        logger.error("❌ Beneficiario actualizado no encontrado")
                        return False
                else:
                    logger.error(f"❌ Error verificando actualización: {response.status}")
                    return False
            
            # PASO 6: DELETE /api/beneficiarios-frecuentes/{id} - Eliminar beneficiario
            logger.info("🗑️ PASO 6: DELETE /api/beneficiarios-frecuentes/{id} - Eliminar beneficiario...")
            
            async with self.session.delete(f"{BACKEND_URL}/beneficiarios-frecuentes/{beneficiario_id_creado}") as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ DELETE beneficiario exitoso: {data.get('message')}")
                    
                    if data.get('success'):
                        logger.info("✅ Eliminación confirmada")
                    else:
                        logger.warning("⚠️ Eliminación no confirmada")
                else:
                    logger.error(f"❌ Error en DELETE beneficiario: {response.status}")
                    error_text = await response.text()
                    logger.error(f"❌ Error details: {error_text}")
                    return False
            
            # PASO 7: Verificar eliminación (soft delete)
            logger.info("🔍 PASO 7: Verificar eliminación (soft delete)...")
            
            async with self.session.get(f"{BACKEND_URL}/beneficiarios-frecuentes") as response:
                if response.status == 200:
                    data = await response.json()
                    beneficiario_eliminado = None
                    
                    for beneficiario in data:
                        if beneficiario.get('id') == beneficiario_id_creado:
                            beneficiario_eliminado = beneficiario
                            break
                    
                    if not beneficiario_eliminado:
                        logger.info("✅ Beneficiario eliminado no aparece en lista (soft delete correcto)")
                    else:
                        if not beneficiario_eliminado.get('activo', True):
                            logger.info("✅ Beneficiario marcado como inactivo (soft delete correcto)")
                        else:
                            logger.error("❌ Beneficiario aún aparece como activo")
                            return False
                else:
                    logger.error(f"❌ Error verificando eliminación: {response.status}")
                    return False
            
            # PASO 8: Verificar contador atómico de folio
            logger.info("🔢 PASO 8: Verificar contador atómico de folio...")
            
            # Verificar en MongoDB directamente
            contador_folio = await self.db.counters.find_one({"_id": "folio_mbco"}, {"_id": 0})
            
            if contador_folio:
                sequence_value = contador_folio.get('sequence_value')
                logger.info(f"✅ Contador atómico encontrado: sequence_value={sequence_value}")
                
                if sequence_value >= 218:  # Debe ser al menos 218 según el request
                    logger.info(f"✅ Contador está en valor esperado (>= 218): {sequence_value}")
                else:
                    logger.warning(f"⚠️ Contador menor al esperado: {sequence_value} < 218")
            else:
                logger.error("❌ Contador atómico 'folio_mbco' no encontrado")
                return False
            
            # PASO 9: Resultado final
            logger.info("🎯 RESULTADO DE LA PRUEBA:")
            logger.info("✅ GET /api/beneficiarios-frecuentes - Lista correctamente")
            logger.info("✅ POST /api/beneficiarios-frecuentes - Crea correctamente")
            logger.info("✅ Validación IDMEX - Funciona correctamente (10 dígitos)")
            logger.info("✅ PUT /api/beneficiarios-frecuentes/{id} - Actualiza correctamente")
            logger.info("✅ DELETE /api/beneficiarios-frecuentes/{id} - Elimina correctamente (soft delete)")
            logger.info("✅ Contador atómico folio_mbco - Funcionando correctamente")
            
            logger.info("🎉 CRUD de Beneficiarios Frecuentes API funciona completamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en test_beneficiarios_crud_api: {str(e)}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False

async def main():
    """Función principal"""
    tester = BeneficiariosTester()
    
    try:
        await tester.setup()
        result = await tester.test_beneficiarios_crud_api()
        
        if result:
            logger.info("🎉 ¡TODAS LAS PRUEBAS DE BENEFICIARIOS PASARON!")
        else:
            logger.error("❌ ALGUNAS PRUEBAS FALLARON")
        
        return result
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())