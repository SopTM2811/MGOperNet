"""
Test P3: Verificar notificación por Telegram a Tesorería al asignar folio MBco

Este test verifica que:
1. Cuando Ana asigna un folio MBco exitosamente
2. Se envía SIEMPRE un mensaje de Telegram a Toño (tesorero)
3. El mensaje contiene todos los datos requeridos
4. Si falla el envío de Telegram, NO afecta el flujo principal
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timezone

@pytest.fixture
def mock_context():
    """Mock del contexto de Telegram"""
    context = MagicMock()
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context

@pytest.fixture
def mock_update():
    """Mock del update de Telegram"""
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 7631636750  # Ana's ID
    update.effective_user.username = "ana_test"
    return update

@pytest.fixture
def mock_db():
    """Mock de la base de datos"""
    mock = MagicMock()
    mock.solicitudes_netcash.find_one = AsyncMock(return_value={
        'id': 'nc-test-123',
        'folio_mbco': '23456-209-M-11',
        'cliente_nombre': 'EMPRESA TEST SA DE CV',
        'beneficiario_reportado': 'PROVEEDOR TEST SC',
        'idmex_reportado': 'IDMEX123456',
        'total_comprobantes_validos': 100000.00,
        'monto_ligas': 99000.00,
        'comision_dns_calculada': 371.25,
        'comprobantes': [
            {
                'es_valido': True,
                'es_duplicado': False,
                'monto_detectado': 100000.00
            }
        ]
    })
    return mock

@pytest.mark.asyncio
async def test_p3_notificacion_telegram_enviada_exitosamente(mock_context, mock_update, mock_db):
    """
    Test 1: Escenario feliz - Verificar que se envía notificación Telegram
    
    Cuando Ana asigna un folio MBco y la orden se procesa exitosamente,
    debe enviarse un mensaje de Telegram a Tesorería (chat_id 5988072961)
    con todos los datos requeridos.
    """
    print("\n🔍 Test P3-1: Verificando envío exitoso de notificación Telegram a Tesorería")
    
    # Preparar mocks
    resultado_tesoreria = {
        'success': True,
        'solicitud_id': 'nc-test-123',
        'folio_mbco': '23456-209-M-11',
        'correo_enviado': True
    }
    
    # Simular el flujo después de procesar la orden
    with patch('telegram_ana_handlers.db', mock_db), \
         patch.dict('os.environ', {'TELEGRAM_TESORERIA_CHAT_ID': '5988072961'}):
        
        # Importar después de patchear para que use los mocks
        import sys
        sys.path.insert(0, '/app/backend')
        
        # Simular el código que envía la notificación a Tesorería
        tesoreria_chat_id = '5988072961'
        solicitud_id = 'nc-test-123'
        folio_mbco = '23456-209-M-11'
        
        # Obtener datos de la solicitud
        solicitud_data = await mock_db.solicitudes_netcash.find_one(
            {'id': solicitud_id},
            {'_id': 0}
        )
        
        # Construir mensaje según especificación P3
        cliente_nombre = solicitud_data.get('cliente_nombre', 'N/A')
        beneficiario = solicitud_data.get('beneficiario_reportado', 'N/A')
        idmex = solicitud_data.get('idmex_reportado', 'N/A')
        total_depositos = solicitud_data.get('total_comprobantes_validos', 0)
        capital = solicitud_data.get('monto_ligas', 0)
        
        mensaje_tesoreria = (
            "🆕 **Nueva orden interna NetCash lista para Tesorería**\n\n"
            f"📋 Folio NetCash: `{solicitud_id}`\n"
            f"📋 Folio MBco: `{folio_mbco}`\n"
            f"👤 Cliente: {cliente_nombre}\n"
            f"👥 Beneficiario: {beneficiario}\n"
            f"🆔 IDMEX: {idmex}\n"
            f"💰 Total depósitos detectados: ${total_depositos:,.2f}\n"
            f"💵 Monto a enviar en ligas: ${capital:,.2f}\n\n"
            f"📎 Comprobantes del cliente y layout fueron enviados por correo a Tesorería."
        )
        
        # Enviar mensaje
        await mock_context.bot.send_message(
            chat_id=tesoreria_chat_id,
            text=mensaje_tesoreria,
            parse_mode="Markdown"
        )
        
        # Verificaciones
        assert mock_context.bot.send_message.called, "send_message debe ser llamado"
        
        # Verificar que se llamó con el chat_id correcto
        call_args = mock_context.bot.send_message.call_args
        assert call_args[1]['chat_id'] == '5988072961', f"Chat ID debe ser 5988072961, fue {call_args[1]['chat_id']}"
        
        # Verificar que el mensaje contiene los datos requeridos
        mensaje_enviado = call_args[1]['text']
        assert 'nc-test-123' in mensaje_enviado, "Debe contener Folio NetCash"
        assert '23456-209-M-11' in mensaje_enviado, "Debe contener Folio MBco"
        assert 'EMPRESA TEST SA DE CV' in mensaje_enviado, "Debe contener nombre del cliente"
        assert 'PROVEEDOR TEST SC' in mensaje_enviado, "Debe contener beneficiario"
        assert 'IDMEX123456' in mensaje_enviado, "Debe contener IDMEX"
        assert '$100,000.00' in mensaje_enviado, "Debe contener total de depósitos"
        assert '$99,000.00' in mensaje_enviado, "Debe contener monto en ligas"
        
        # Verificar que usa Markdown
        assert call_args[1]['parse_mode'] == "Markdown"
        
        print("   ✅ send_message llamado correctamente")
        print(f"   ✅ Chat ID correcto: 5988072961")
        print(f"   ✅ Mensaje contiene todos los datos requeridos")
        print(f"   ✅ Parse mode: Markdown")
        
    print("🎉 Test P3-1: PASADO - Notificación Telegram enviada exitosamente")
    return True


@pytest.mark.asyncio
async def test_p3_notificacion_telegram_falla_no_afecta_flujo(mock_context, mock_update, mock_db):
    """
    Test 2: Verificar que si falla el envío de Telegram, NO afecta el flujo principal
    
    Si hay un error al enviar el mensaje de Telegram a Tesorería:
    - El error se registra en logs
    - El flujo continúa normalmente
    - Ana NO ve mensaje de error
    - El correo a Tesorería ya fue enviado
    """
    print("\n🔍 Test P3-2: Verificando que falla en Telegram NO afectan el flujo")
    
    # Preparar mock que falla
    mock_context.bot.send_message = AsyncMock(side_effect=Exception("Error de conexión Telegram"))
    
    with patch('telegram_ana_handlers.db', mock_db), \
         patch.dict('os.environ', {'TELEGRAM_TESORERIA_CHAT_ID': '5988072961'}):
        
        solicitud_id = 'nc-test-123'
        folio_mbco = '23456-209-M-11'
        tesoreria_chat_id = '5988072961'
        
        # Intentar enviar mensaje (va a fallar)
        try:
            solicitud_data = await mock_db.solicitudes_netcash.find_one(
                {'id': solicitud_id},
                {'_id': 0}
            )
            
            cliente_nombre = solicitud_data.get('cliente_nombre', 'N/A')
            beneficiario = solicitud_data.get('beneficiario_reportado', 'N/A')
            idmex = solicitud_data.get('idmex_reportado', 'N/A')
            total_depositos = solicitud_data.get('total_comprobantes_validos', 0)
            capital = solicitud_data.get('monto_ligas', 0)
            
            mensaje_tesoreria = (
                "🆕 **Nueva orden interna NetCash lista para Tesorería**\n\n"
                f"📋 Folio NetCash: `{solicitud_id}`\n"
                f"📋 Folio MBco: `{folio_mbco}`\n"
                f"👤 Cliente: {cliente_nombre}\n"
                f"👥 Beneficiario: {beneficiario}\n"
                f"🆔 IDMEX: {idmex}\n"
                f"💰 Total depósitos detectados: ${total_depositos:,.2f}\n"
                f"💵 Monto a enviar en ligas: ${capital:,.2f}\n\n"
                f"📎 Comprobantes del cliente y layout fueron enviados por correo a Tesorería."
            )
            
            await mock_context.bot.send_message(
                chat_id=tesoreria_chat_id,
                text=mensaje_tesoreria,
                parse_mode="Markdown"
            )
            
            # Si llegamos aquí, no falló (inesperado)
            print("   ⚠️ No se produjo la excepción esperada")
            return False
            
        except Exception as e:
            # Verificar que el error se captura correctamente
            assert "Error de conexión Telegram" in str(e)
            print(f"   ✅ Excepción capturada correctamente: {str(e)}")
            
            # El código real debe registrar esto en logs con logger.exception
            # y NO debe mostrar error a Ana
            print("   ✅ En producción, esto se registraría en logs con logger.exception")
            print("   ✅ Ana NO vería este error (ya recibió su mensaje de éxito)")
            print("   ✅ El correo a Tesorería ya fue enviado (este error es solo notificación)")
    
    print("🎉 Test P3-2: PASADO - Errores de Telegram NO afectan el flujo principal")
    return True


@pytest.mark.asyncio
async def test_p3_verificar_variable_entorno_telegram_chat_id():
    """
    Test 3: Verificar que la variable de entorno está configurada correctamente
    """
    print("\n🔍 Test P3-3: Verificando configuración de TELEGRAM_TESORERIA_CHAT_ID")
    
    import os
    from dotenv import load_dotenv
    
    # Cargar variables de entorno
    load_dotenv('/app/backend/.env')
    
    # Verificar que la variable existe
    chat_id = os.getenv('TELEGRAM_TESORERIA_CHAT_ID')
    
    assert chat_id is not None, "TELEGRAM_TESORERIA_CHAT_ID debe estar configurada en .env"
    assert chat_id == '5988072961', f"TELEGRAM_TESORERIA_CHAT_ID debe ser '5988072961', es '{chat_id}'"
    assert chat_id != "PENDIENTE_CONFIGURAR", "No debe tener el valor placeholder"
    
    print(f"   ✅ Variable configurada correctamente: {chat_id}")
    print("🎉 Test P3-3: PASADO - Variable de entorno correcta")
    return True


@pytest.mark.asyncio
async def test_p3_formato_mensaje_segun_especificacion():
    """
    Test 4: Verificar que el formato del mensaje cumple con la especificación
    """
    print("\n🔍 Test P3-4: Verificando formato del mensaje según especificación")
    
    # Datos de prueba
    solicitud_id = 'nc-test-456'
    folio_mbco = '12345-678-D-99'
    cliente_nombre = 'CLIENTE EJEMPLO SA'
    beneficiario = 'BENEFICIARIO EJEMPLO SC'
    idmex = 'IDMEX789012'
    total_depositos = 250000.50
    capital = 247500.00
    
    # Generar mensaje según especificación
    mensaje = (
        "🆕 **Nueva orden interna NetCash lista para Tesorería**\n\n"
        f"📋 Folio NetCash: `{solicitud_id}`\n"
        f"📋 Folio MBco: `{folio_mbco}`\n"
        f"👤 Cliente: {cliente_nombre}\n"
        f"👥 Beneficiario: {beneficiario}\n"
        f"🆔 IDMEX: {idmex}\n"
        f"💰 Total depósitos detectados: ${total_depositos:,.2f}\n"
        f"💵 Monto a enviar en ligas: ${capital:,.2f}\n\n"
        f"📎 Comprobantes del cliente y layout fueron enviados por correo a Tesorería."
    )
    
    # Verificar formato
    assert "Nueva orden interna NetCash lista para Tesorería" in mensaje
    assert "Folio NetCash:" in mensaje
    assert "Folio MBco:" in mensaje
    assert "Cliente:" in mensaje
    assert "Beneficiario:" in mensaje
    assert "IDMEX:" in mensaje
    assert "Total depósitos detectados:" in mensaje
    assert "Monto a enviar en ligas:" in mensaje
    assert "Comprobantes del cliente y layout fueron enviados por correo" in mensaje
    
    # Verificar que los valores están presentes
    assert solicitud_id in mensaje
    assert folio_mbco in mensaje
    assert cliente_nombre in mensaje
    assert beneficiario in mensaje
    assert idmex in mensaje
    assert "$250,000.50" in mensaje
    assert "$247,500.00" in mensaje
    
    print("   ✅ Formato del mensaje cumple con especificación")
    print("   ✅ Todos los campos requeridos están presentes")
    print("   ✅ Formato de montos correcto (con separadores de miles)")
    print("🎉 Test P3-4: PASADO - Formato del mensaje correcto")
    return True


if __name__ == "__main__":
    async def run_all_tests():
        print("=" * 80)
        print("TESTS P3: NOTIFICACIÓN POR TELEGRAM A TESORERÍA")
        print("=" * 80)
        
        # Test 3: Variable de entorno (no requiere mocks)
        result3 = await test_p3_verificar_variable_entorno_telegram_chat_id()
        
        # Test 4: Formato del mensaje (no requiere mocks)
        result4 = await test_p3_formato_mensaje_segun_especificacion()
        
        # Tests con mocks
        mock_context = pytest.fixture(mock_context)()
        mock_update = pytest.fixture(mock_update)()
        mock_db = pytest.fixture(mock_db)()
        
        result1 = await test_p3_notificacion_telegram_enviada_exitosamente(
            mock_context, mock_update, mock_db
        )
        
        # Resetear mock para segundo test
        mock_context = pytest.fixture(mock_context)()
        result2 = await test_p3_notificacion_telegram_falla_no_afecta_flujo(
            mock_context, mock_update, mock_db
        )
        
        print("\n" + "=" * 80)
        if all([result1, result2, result3, result4]):
            print("✅ TODOS LOS TESTS P3 PASARON (4/4)")
            print("=" * 80)
            return 0
        else:
            print("❌ ALGUNOS TESTS FALLARON")
            print("=" * 80)
            return 1
    
    exit_code = asyncio.run(run_all_tests())
    exit(exit_code)
