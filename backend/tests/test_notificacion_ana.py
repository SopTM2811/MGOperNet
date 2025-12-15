#!/usr/bin/env python3
"""
Test específico para el sistema de notificación a Ana
Verifica las correcciones implementadas en _notificar_ana_solicitud_lista
"""
import asyncio
import pytest
import unittest.mock as mock
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
from pathlib import Path
import logging
from datetime import datetime, timezone

# Agregar el directorio backend al path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Importar el servicio a probar
from netcash_service import netcash_service

class TestNotificacionAna:
    """Tests para el sistema de notificación a Ana"""
    
    def setup_method(self):
        """Setup para cada test"""
        self.solicitud_test = {
            "id": "nc-test-123456789",
            "folio_mbco": "NC-000048",
            "cliente_nombre": "JUAN CARLOS PEREZ LOPEZ",
            "beneficiario_reportado": "MARIA ELENA RODRIGUEZ GARCIA",
            "idmex_reportado": "1234567890",
            "cantidad_ligas_reportada": 3,
            "comprobantes": [
                {
                    "monto_detectado": 125000.00,
                    "es_valido": True,
                    "es_duplicado": False,
                    "nombre_archivo": "comprobante_test.pdf"
                }
            ],
            "comision_cliente": 1250.00,
            "modo_captura": "ocr_ok",
            "created_at": datetime.now(timezone.utc)
        }
        
        self.ana_user_mock = {
            "nombre": "Ana Administradora",
            "rol": "admin_netcash",
            "telegram_id": "7631636750"  # Ana's telegram_id from the request
        }
    
    @pytest.mark.asyncio
    async def test_imports_and_compilation(self):
        """Test 1: Verificar que el código compila y no tiene errores de importación"""
        logger.info("🔍 Test 1: Verificando imports y compilación...")
        
        try:
            # Verificar que httpx se puede importar
            import httpx
            logger.info("✅ httpx importado correctamente")
            
            # Verificar que el método existe en netcash_service
            assert hasattr(netcash_service, '_notificar_ana_solicitud_lista')
            logger.info("✅ Método _notificar_ana_solicitud_lista existe")
            
            # Verificar que es callable
            assert callable(getattr(netcash_service, '_notificar_ana_solicitud_lista'))
            logger.info("✅ Método es callable")
            
            logger.info("🎉 Test 1 PASADO: Código compila correctamente")
            
        except ImportError as e:
            logger.error(f"❌ Error de importación: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Error inesperado: {str(e)}")
            raise
    
    @pytest.mark.asyncio
    async def test_notification_logic_with_mocks(self):
        """Test 2: Verificar lógica de notificación con mocks completos"""
        logger.info("🔍 Test 2: Verificando lógica de notificación con mocks...")
        
        # Mock del repositorio de usuarios (importado dentro del método)
        with patch('usuarios_repo.usuarios_repo') as mock_usuarios_repo:
            # Mock del cliente httpx
            with patch('httpx.AsyncClient') as mock_httpx_client:
                # Mock de variables de entorno
                with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'test_token_123'}):
                    
                    # Configurar mock del repositorio
                    mock_usuarios_repo.obtener_usuario_por_rol = AsyncMock(return_value=self.ana_user_mock)
                    
                    # Configurar mock del cliente httpx
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.text = '{"ok": true, "result": {"message_id": 123}}'
                    
                    mock_client_instance = AsyncMock()
                    mock_client_instance.post = AsyncMock(return_value=mock_response)
                    mock_httpx_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                    mock_httpx_client.return_value.__aexit__ = AsyncMock(return_value=None)
                    
                    # Ejecutar el método
                    await netcash_service._notificar_ana_solicitud_lista(self.solicitud_test)
                    
                    # Verificaciones
                    logger.info("📋 Verificando llamadas a mocks...")
                    
                    # 1. Verificar que se consultó el usuario Ana
                    mock_usuarios_repo.obtener_usuario_por_rol.assert_called_once_with("admin_netcash")
                    logger.info("✅ Se consultó usuario con rol 'admin_netcash'")
                    
                    # 2. Verificar que se hizo la llamada HTTP
                    mock_client_instance.post.assert_called_once()
                    call_args = mock_client_instance.post.call_args
                    
                    # Verificar URL
                    expected_url = "https://api.telegram.org/bot{}/sendMessage".format('test_token_123')
                    assert call_args[0][0] == expected_url
                    logger.info("✅ URL de Telegram API correcta")
                    
                    # Verificar payload
                    payload = call_args[1]['json']
                    
                    # 3. Verificar chat_id correcto (Ana's telegram_id)
                    assert payload['chat_id'] == "7631636750"
                    logger.info("✅ chat_id correcto (Ana's telegram_id: 7631636750)")
                    
                    # 4. Verificar que el mensaje contiene campos esperados
                    mensaje = payload['text']
                    assert "NC-000048" in mensaje  # folio_mbco
                    assert "MARIA ELENA RODRIGUEZ GARCIA" in mensaje  # beneficiario
                    assert "125,000.00" in mensaje or "125000.00" in mensaje  # total_depositos
                    logger.info("✅ Mensaje contiene campos esperados (folio_mbco, beneficiario, total_depositos)")
                    
                    # 5. Verificar parse_mode
                    assert payload['parse_mode'] == "Markdown"
                    logger.info("✅ parse_mode configurado como Markdown")
                    
                    # 6. Verificar inline keyboard buttons
                    reply_markup = payload['reply_markup']
                    assert 'inline_keyboard' in reply_markup
                    
                    inline_keyboard = reply_markup['inline_keyboard']
                    assert len(inline_keyboard) == 2  # Dos filas de botones
                    
                    # Verificar botón de validar
                    boton_validar = inline_keyboard[0][0]
                    assert "Validar y asignar folio MBco" in boton_validar['text']
                    assert "ana_asignar_folio_nc-test-123456789" in boton_validar['callback_data']
                    
                    # Verificar botón de rechazar
                    boton_rechazar = inline_keyboard[1][0]
                    assert "Rechazar operación" in boton_rechazar['text']
                    assert "ana_rechazar_nc-test-123456789" in boton_rechazar['callback_data']
                    
                    logger.info("✅ Botones inline correctamente formateados")
                    
                    logger.info("🎉 Test 2 PASADO: Lógica de notificación funciona correctamente")
    
    @pytest.mark.asyncio
    async def test_notification_error_handling(self):
        """Test 3: Verificar manejo de errores"""
        logger.info("🔍 Test 3: Verificando manejo de errores...")
        
        # Test 3a: Usuario Ana no encontrado
        with patch('usuarios_repo.usuarios_repo') as mock_usuarios_repo:
            mock_usuarios_repo.obtener_usuario_por_rol = AsyncMock(return_value=None)
            
            # No debería lanzar excepción, solo loguear error
            try:
                await netcash_service._notificar_ana_solicitud_lista(self.solicitud_test)
                logger.info("✅ Manejo correcto cuando usuario Ana no existe")
            except Exception as e:
                logger.error(f"❌ No debería lanzar excepción: {str(e)}")
                raise
        
        # Test 3b: Usuario Ana sin telegram_id
        ana_sin_telegram = self.ana_user_mock.copy()
        ana_sin_telegram['telegram_id'] = None
        
        with patch('usuarios_repo.usuarios_repo') as mock_usuarios_repo:
            mock_usuarios_repo.obtener_usuario_por_rol = AsyncMock(return_value=ana_sin_telegram)
            
            try:
                await netcash_service._notificar_ana_solicitud_lista(self.solicitud_test)
                logger.info("✅ Manejo correcto cuando Ana no tiene telegram_id")
            except Exception as e:
                logger.error(f"❌ No debería lanzar excepción: {str(e)}")
                raise
        
        # Test 3c: Token de Telegram no configurado
        with patch('usuarios_repo.usuarios_repo') as mock_usuarios_repo:
            with patch.dict(os.environ, {}, clear=True):  # Limpiar variables de entorno
                mock_usuarios_repo.obtener_usuario_por_rol = AsyncMock(return_value=self.ana_user_mock)
                
                try:
                    await netcash_service._notificar_ana_solicitud_lista(self.solicitud_test)
                    logger.info("✅ Manejo correcto cuando TELEGRAM_BOT_TOKEN no está configurado")
                except Exception as e:
                    logger.error(f"❌ No debería lanzar excepción: {str(e)}")
                    raise
        
        # Test 3d: Error en llamada HTTP
        with patch('usuarios_repo.usuarios_repo') as mock_usuarios_repo:
            with patch('httpx.AsyncClient') as mock_httpx_client:
                with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'test_token_123'}):
                    
                    mock_usuarios_repo.obtener_usuario_por_rol = AsyncMock(return_value=self.ana_user_mock)
                    
                    # Simular error HTTP
                    mock_client_instance = AsyncMock()
                    mock_client_instance.post = AsyncMock(side_effect=Exception("Network error"))
                    mock_httpx_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                    mock_httpx_client.return_value.__aexit__ = AsyncMock(return_value=None)
                    
                    try:
                        await netcash_service._notificar_ana_solicitud_lista(self.solicitud_test)
                        logger.info("✅ Manejo correcto de errores HTTP")
                    except Exception as e:
                        logger.error(f"❌ No debería lanzar excepción: {str(e)}")
                        raise
        
        logger.info("🎉 Test 3 PASADO: Manejo de errores funciona correctamente")
    
    @pytest.mark.asyncio
    async def test_message_content_validation(self):
        """Test 4: Validación detallada del contenido del mensaje"""
        logger.info("🔍 Test 4: Validación detallada del contenido del mensaje...")
        
        with patch('usuarios_repo.usuarios_repo') as mock_usuarios_repo:
            with patch('httpx.AsyncClient') as mock_httpx_client:
                with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'test_token_123'}):
                    
                    mock_usuarios_repo.obtener_usuario_por_rol = AsyncMock(return_value=self.ana_user_mock)
                    
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    
                    mock_client_instance = AsyncMock()
                    mock_client_instance.post = AsyncMock(return_value=mock_response)
                    mock_httpx_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                    mock_httpx_client.return_value.__aexit__ = AsyncMock(return_value=None)
                    
                    # Ejecutar
                    await netcash_service._notificar_ana_solicitud_lista(self.solicitud_test)
                    
                    # Obtener el mensaje enviado
                    call_args = mock_client_instance.post.call_args
                    payload = call_args[1]['json']
                    mensaje = payload['text']
                    
                    logger.info("📋 Validando contenido del mensaje...")
                    logger.info(f"Mensaje generado:\n{mensaje}")
                    
                    # Verificaciones específicas del contenido
                    assert "🧾 *Nueva solicitud NetCash lista para MBco*" in mensaje
                    assert f"📋 *Folio NetCash:* {self.solicitud_test['folio_mbco']}" in mensaje
                    assert f"🧑‍💼 *Cliente:* {self.solicitud_test['cliente_nombre']}" in mensaje
                    assert f"👤 *Beneficiario:* {self.solicitud_test['beneficiario_reportado']}" in mensaje
                    assert f"🆔 *IDMEX:* {self.solicitud_test['idmex_reportado']}" in mensaje
                    assert f"🔗 *Número de ligas:* {self.solicitud_test['cantidad_ligas_reportada']}" in mensaje
                    
                    # Verificar cálculos
                    total_depositos = 125000.00
                    comision_netcash = 1250.00
                    monto_ligas = total_depositos - comision_netcash
                    
                    assert f"💰 *Total depósitos:* ${total_depositos:,.2f}" in mensaje
                    assert f"📊 *Comisión NetCash (1%):* ${comision_netcash:,.2f}" in mensaje
                    assert f"💸 *Monto a enviar (ligas):* ${monto_ligas:,.2f}" in mensaje
                    
                    # Verificar origen de datos
                    assert "✅ *Origen datos:* Robot (OCR confiable)" in mensaje
                    
                    logger.info("✅ Contenido del mensaje validado correctamente")
                    logger.info("🎉 Test 4 PASADO: Contenido del mensaje es correcto")
    
    @pytest.mark.asyncio
    async def test_manual_capture_mode_message(self):
        """Test 5: Verificar mensaje cuando es captura manual"""
        logger.info("🔍 Test 5: Verificando mensaje para modo captura manual...")
        
        # Modificar solicitud para modo manual
        solicitud_manual = self.solicitud_test.copy()
        solicitud_manual['modo_captura'] = 'manual_por_fallo_ocr'
        
        with patch('usuarios_repo.usuarios_repo') as mock_usuarios_repo:
            with patch('httpx.AsyncClient') as mock_httpx_client:
                with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'test_token_123'}):
                    
                    mock_usuarios_repo.obtener_usuario_por_rol = AsyncMock(return_value=self.ana_user_mock)
                    
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    
                    mock_client_instance = AsyncMock()
                    mock_client_instance.post = AsyncMock(return_value=mock_response)
                    mock_httpx_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                    mock_httpx_client.return_value.__aexit__ = AsyncMock(return_value=None)
                    
                    # Ejecutar
                    await netcash_service._notificar_ana_solicitud_lista(solicitud_manual)
                    
                    # Verificar mensaje
                    call_args = mock_client_instance.post.call_args
                    payload = call_args[1]['json']
                    mensaje = payload['text']
                    
                    # Verificar indicadores de captura manual
                    assert "⚠️ *CAPTURA MANUAL* - OCR no pudo leer comprobante" in mensaje
                    assert "📊 *Origen datos:* Manual (capturado por cliente)" in mensaje
                    
                    logger.info("✅ Mensaje de captura manual correcto")
                    logger.info("🎉 Test 5 PASADO: Modo captura manual funciona correctamente")

async def run_all_tests():
    """Ejecuta todos los tests"""
    logger.info("🚀 Iniciando tests de notificación a Ana...")
    
    test_instance = TestNotificacionAna()
    
    try:
        # Test 1: Imports y compilación
        test_instance.setup_method()
        await test_instance.test_imports_and_compilation()
        
        # Test 2: Lógica de notificación
        test_instance.setup_method()
        await test_instance.test_notification_logic_with_mocks()
        
        # Test 3: Manejo de errores
        test_instance.setup_method()
        await test_instance.test_notification_error_handling()
        
        # Test 4: Validación de contenido
        test_instance.setup_method()
        await test_instance.test_message_content_validation()
        
        # Test 5: Modo captura manual
        test_instance.setup_method()
        await test_instance.test_manual_capture_mode_message()
        
        logger.info("🎉 TODOS LOS TESTS PASARON EXITOSAMENTE")
        return True
        
    except Exception as e:
        logger.error(f"❌ ERROR EN TESTS: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    # Ejecutar tests
    result = asyncio.run(run_all_tests())
    exit(0 if result else 1)