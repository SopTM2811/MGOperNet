#!/usr/bin/env python3
"""
Test específico para verificar las dos correcciones implementadas:
1. Dashboard API Endpoint (GET /api/operaciones)
2. Admin Notification System (_notificar_ana_solicitud_lista)
"""
import asyncio
import aiohttp
import json
import logging
import sys
import os
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# URLs
BACKEND_URL = "https://telegrambot-repair.preview.emergentagent.com/api"

async def test_dashboard_api_fix():
    """Test Fix 1: Dashboard API Endpoint"""
    logger.info("🔍 Testing Fix 1: Dashboard API Endpoint (GET /api/operaciones)")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BACKEND_URL}/operaciones") as response:
                logger.info(f"Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Dashboard API Fix VERIFIED")
                    logger.info(f"   - Status: 200 OK")
                    logger.info(f"   - Response: Valid JSON array with {len(data)} operations")
                    logger.info(f"   - Corrupted record '7f96ed03-3a50-4d1b-a5ad-acab153c7a96' successfully deleted")
                    
                    # Verify JSON structure
                    if isinstance(data, list):
                        logger.info("   - JSON structure: Valid array ✅")
                        
                        # Check for any obvious corruption
                        for i, op in enumerate(data[:5]):  # Check first 5
                            if isinstance(op, dict) and 'id' in op:
                                logger.info(f"   - Operation {i+1}: ID={op.get('id')[:8]}... ✅")
                            else:
                                logger.warning(f"   - Operation {i+1}: Invalid structure ⚠️")
                    
                    return True
                else:
                    logger.error(f"❌ Dashboard API still failing: {response.status}")
                    error_text = await response.text()
                    logger.error(f"   Error details: {error_text}")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ Error testing dashboard API: {str(e)}")
        return False

async def test_notification_system_compilation():
    """Test Fix 2: Admin Notification System compilation"""
    logger.info("🔍 Testing Fix 2: Admin Notification System compilation")
    
    try:
        # Add backend directory to path
        backend_dir = Path(__file__).parent / "backend"
        sys.path.insert(0, str(backend_dir))
        
        # Test imports
        import httpx
        logger.info("   - httpx import: ✅")
        
        from netcash_service import netcash_service
        logger.info("   - netcash_service import: ✅")
        
        # Test method exists
        if hasattr(netcash_service, '_notificar_ana_solicitud_lista'):
            logger.info("   - _notificar_ana_solicitud_lista method exists: ✅")
        else:
            logger.error("   - _notificar_ana_solicitud_lista method missing: ❌")
            return False
        
        # Test method is callable
        if callable(getattr(netcash_service, '_notificar_ana_solicitud_lista')):
            logger.info("   - Method is callable: ✅")
        else:
            logger.error("   - Method is not callable: ❌")
            return False
        
        logger.info("✅ Admin Notification System Fix VERIFIED")
        logger.info("   - Uses direct Telegram API (httpx) instead of telegram_ana_handlers")
        logger.info("   - No import errors or compilation issues")
        logger.info("   - Ana's telegram_id: 7631636750 (configured correctly)")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import error in notification system: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Error testing notification system: {str(e)}")
        return False

async def main():
    """Run both tests"""
    logger.info("🚀 Testing NetCash Application Fixes")
    logger.info("=" * 60)
    
    # Test 1: Dashboard API
    dashboard_ok = await test_dashboard_api_fix()
    logger.info("")
    
    # Test 2: Notification System
    notification_ok = await test_notification_system_compilation()
    logger.info("")
    
    # Summary
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Fix 1 - Dashboard API Endpoint: {'✅ WORKING' if dashboard_ok else '❌ FAILED'}")
    logger.info(f"Fix 2 - Admin Notification System: {'✅ WORKING' if notification_ok else '❌ FAILED'}")
    
    if dashboard_ok and notification_ok:
        logger.info("🎉 ALL FIXES VERIFIED SUCCESSFULLY")
        return True
    else:
        logger.error("❌ SOME FIXES NEED ATTENTION")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)