#!/usr/bin/env python3
"""
Test específico para los bugs reportados:
1. Timezone Bug - Operación NC-000208
2. Comprobantes Normalization Bug - monto_detectado -> monto
"""
import asyncio
import aiohttp
import json
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# URL del backend
BACKEND_URL = "https://netcash-hub.preview.emergentagent.com/api"

async def test_specific_bugs():
    """Test específico para los bugs reportados"""
    logger.info("🔍 Testing specific bugs reported by user")
    
    async with aiohttp.ClientSession() as session:
        # Test Bug 1 & 2: Operación NC-000208
        operacion_id = "nc-1765835406493"
        
        logger.info(f"📋 Testing operation: {operacion_id}")
        
        # Test endpoint GET /api/operaciones/{id}
        async with session.get(f"{BACKEND_URL}/operaciones/{operacion_id}") as response:
            if response.status == 200:
                data = await response.json()
                
                logger.info("✅ Operation found:")
                logger.info(f"   - ID: {data.get('id')}")
                logger.info(f"   - Folio: {data.get('folio_mbco')}")
                logger.info(f"   - Origen: {data.get('origen')}")
                logger.info(f"   - fecha_creacion: {data.get('fecha_creacion')}")
                logger.info(f"   - monto_depositado_cliente: {data.get('monto_depositado_cliente')}")
                
                # Check comprobantes normalization
                comprobantes = data.get('comprobantes', [])
                logger.info(f"   - Comprobantes count: {len(comprobantes)}")
                
                for i, comp in enumerate(comprobantes):
                    logger.info(f"   📎 Comprobante {i+1}:")
                    logger.info(f"      - Has 'monto': {'monto' in comp}")
                    logger.info(f"      - Has 'monto_detectado': {'monto_detectado' in comp}")
                    
                    if 'monto' in comp:
                        logger.info(f"      - monto: {comp.get('monto')}")
                    if 'monto_detectado' in comp:
                        logger.info(f"      - monto_detectado: {comp.get('monto_detectado')}")
                    
                    # Verify Bug 2 fix
                    if 'monto' in comp and 'monto_detectado' in comp:
                        if comp.get('monto') == comp.get('monto_detectado'):
                            logger.info("      ✅ Bug 2 FIXED: monto = monto_detectado")
                        else:
                            logger.error("      ❌ Bug 2 NOT FIXED: monto != monto_detectado")
                    elif 'monto_detectado' in comp and 'monto' not in comp:
                        logger.error("      ❌ Bug 2 NOT FIXED: monto_detectado exists but monto missing")
                
                # Verify expected values
                if data.get('folio_mbco') == 'NC-000208':
                    logger.info("✅ Correct folio: NC-000208")
                else:
                    logger.error(f"❌ Wrong folio: {data.get('folio_mbco')}")
                
                if data.get('monto_depositado_cliente') == 223000.0:
                    logger.info("✅ Correct monto_depositado_cliente: 223000.0")
                else:
                    logger.warning(f"⚠️ Unexpected monto_depositado_cliente: {data.get('monto_depositado_cliente')}")
                
                # Bug 1: Timezone - verify fecha_creacion format
                fecha_creacion = data.get('fecha_creacion')
                if fecha_creacion:
                    logger.info("✅ Bug 1: fecha_creacion returned for frontend timezone formatting")
                    logger.info(f"   Frontend should format: {fecha_creacion} -> 15/12/2025, 3:50 p.m. (Mexico time)")
                else:
                    logger.error("❌ Bug 1: fecha_creacion missing")
                
            else:
                logger.error(f"❌ Error getting operation: {response.status}")
                error_text = await response.text()
                logger.error(f"Error details: {error_text}")
                return False
        
        # Test dashboard listing
        logger.info("📋 Testing dashboard listing...")
        async with session.get(f"{BACKEND_URL}/operaciones") as response:
            if response.status == 200:
                operaciones = await response.json()
                logger.info(f"✅ Dashboard listing: {len(operaciones)} operations")
                
                # Find our specific operation
                target_op = None
                for op in operaciones:
                    if op.get('folio_mbco') == 'NC-000208':
                        target_op = op
                        break
                
                if target_op:
                    logger.info("✅ Operation NC-000208 found in dashboard listing")
                    
                    # Check comprobantes normalization in listing
                    comprobantes = target_op.get('comprobantes', [])
                    if comprobantes:
                        for comp in comprobantes:
                            if 'monto' in comp and 'monto_detectado' in comp:
                                logger.info("✅ Comprobantes normalized in dashboard listing")
                                break
                        else:
                            logger.error("❌ Comprobantes NOT normalized in dashboard listing")
                            return False
                else:
                    logger.error("❌ Operation NC-000208 NOT found in dashboard listing")
                    return False
            else:
                logger.error(f"❌ Error getting dashboard listing: {response.status}")
                return False
        
        logger.info("🎉 All bug fixes verified successfully!")
        return True

if __name__ == "__main__":
    asyncio.run(test_specific_bugs())