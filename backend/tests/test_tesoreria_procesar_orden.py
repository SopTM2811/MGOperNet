"""
Test para verificar el flujo completo de procesamiento de orden de tesorería
después del fix del error 'await' outside async function.

Este test verifica:
1. Que procesar_operacion_tesoreria funciona sin excepciones
2. Que retorna {"success": True} al completarse
3. Que la función _generar_cuerpo_correo_operacion es async
4. Que el email se envía correctamente (mockeado)
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from decimal import Decimal

# Mocks para evitar dependencias reales
@pytest.fixture
def mock_db():
    """Mock de la base de datos"""
    mock = MagicMock()
    
    # Mock para find_one (obtener solicitud)
    mock.solicitudes_netcash.find_one = AsyncMock(return_value={
        'id': 'test_solicitud_123',
        'folio_mbco': '12345-209-M-11',
        'cliente_nombre': 'JARDINERIA Y COMERCIO THABYETHA SA DE CV',
        'beneficiario_reportado': 'AFFORDABLE MEDICAL SERVICES SC',
        'idmex_reportado': 'TEST123',
        'monto_ligas': 100000.00,
        'total_comprobantes_validos': 101000.00,
        'comprobantes': [
            {
                'es_valido': True,
                'es_duplicado': False,
                'monto_detectado': 101000.00,
                'banco_ordenante': 'BBVA',
                'cuenta_ordenante': '012180015012345678'
            }
        ],
        'correo_tesoreria_enviado': False  # NO ha sido enviado aún
    })
    
    # Mock para update_one (actualizar estado)
    mock.solicitudes_netcash.update_one = AsyncMock(return_value=MagicMock(
        modified_count=1
    ))
    
    return mock


@pytest.fixture
def mock_cuenta_deposito_service():
    """Mock del servicio de cuenta de depósito"""
    mock = MagicMock()
    mock.obtener_cuenta_activa = AsyncMock(return_value={
        'banco': 'STP',
        'clabe': '646180139409481462',
        'beneficiario': 'JARDINERIA Y COMERCIO THABYETHA SA DE CV'
    })
    return mock


@pytest.fixture
def mock_gmail_service():
    """Mock del servicio de Gmail"""
    mock = MagicMock()
    mock.enviar_correo_con_adjuntos = AsyncMock(return_value={
        'thread_id': 'test_thread_123',
        'message_id': 'test_message_456'
    })
    return mock


@pytest.mark.asyncio
async def test_procesar_operacion_tesoreria_success(mock_db, mock_cuenta_deposito_service, mock_gmail_service):
    """
    Test principal: Verificar que el flujo completo funciona sin excepciones
    y retorna success: True
    """
    
    # Patchear las dependencias
    with patch('tesoreria_operacion_service.db', mock_db), \
         patch('tesoreria_operacion_service.cuenta_deposito_service', mock_cuenta_deposito_service), \
         patch('gmail_service.gmail_service', mock_gmail_service):
        
        from tesoreria_operacion_service import tesoreria_operacion_service
        
        # Ejecutar el procesamiento de la operación
        resultado = await tesoreria_operacion_service.procesar_operacion_tesoreria('test_solicitud_123')
        
        # Verificaciones
        assert resultado is not None, "El resultado no debe ser None"
        assert resultado.get('success') is True, "El resultado debe tener success=True"
        assert resultado.get('solicitud_id') == 'test_solicitud_123'
        assert resultado.get('folio_mbco') == '12345-209-M-11'
        assert resultado.get('correo_enviado') is True
        
        # Verificar que se actualizó la base de datos
        assert mock_db.solicitudes_netcash.update_one.called
        update_call = mock_db.solicitudes_netcash.update_one.call_args
        assert update_call[0][0] == {'id': 'test_solicitud_123'}
        assert update_call[0][1]['$set']['estado'] == 'enviado_a_tesoreria'
        assert update_call[0][1]['$set']['correo_tesoreria_enviado'] is True
        
        print("✅ Test P0: procesar_operacion_tesoreria funciona correctamente")
        print(f"✅ Resultado: {resultado}")


@pytest.mark.asyncio
async def test_generar_cuerpo_correo_es_async(mock_cuenta_deposito_service):
    """
    Test específico: Verificar que _generar_cuerpo_correo_operacion es una función async
    """
    import inspect
    from tesoreria_operacion_service import TesoreriaOperacionService
    
    service = TesoreriaOperacionService()
    
    # Verificar que la función es una coroutine (async)
    assert inspect.iscoroutinefunction(service._generar_cuerpo_correo_operacion), \
        "_generar_cuerpo_correo_operacion debe ser una función async"
    
    print("✅ Test P0: _generar_cuerpo_correo_operacion es correctamente async")


@pytest.mark.asyncio
async def test_generar_cuerpo_correo_obtiene_cuenta_activa(mock_cuenta_deposito_service):
    """
    Test: Verificar que _generar_cuerpo_correo_operacion obtiene la cuenta activa
    y la usa en el email (esto también verifica P2)
    """
    with patch('cuenta_deposito_service.cuenta_deposito_service', mock_cuenta_deposito_service):
        from tesoreria_operacion_service import TesoreriaOperacionService
        
        service = TesoreriaOperacionService()
        
        solicitud_test = {
            'id': 'test_123',
            'folio_mbco': '12345-209-M-11',
            'cliente_nombre': 'TEST CLIENTE',
            'beneficiario_reportado': 'TEST BENEFICIARIO',
            'idmex_reportado': 'IDMEX123',
            'total_comprobantes_validos': 101000.00,
            'monto_ligas': 100000.00,
            'comision_dns_calculada': 375.00,
            'comprobantes': [
                {
                    'es_valido': True,
                    'es_duplicado': False,
                    'monto_detectado': 101000.00
                }
            ]
        }
        
        # Generar el cuerpo del correo
        cuerpo = await service._generar_cuerpo_correo_operacion(solicitud_test)
        
        # Verificaciones
        assert cuerpo is not None
        assert isinstance(cuerpo, str)
        assert len(cuerpo) > 0
        
        # Verificar que se llamó a obtener_cuenta_activa
        assert mock_cuenta_deposito_service.obtener_cuenta_activa.called
        
        # Verificar que el CLABE correcto aparece en el cuerpo (P2)
        assert '646180139409481462' in cuerpo, \
            "El CLABE de la cuenta NetCash activa debe aparecer en el correo"
        
        print("✅ Test P0 + P2: El correo incluye el CLABE correcto de la cuenta NetCash activa")
        print(f"✅ Cuerpo generado: {len(cuerpo)} caracteres")


@pytest.mark.asyncio
async def test_operacion_ya_enviada_previamente(mock_db):
    """
    Test: Verificar que si la operación ya fue enviada, retorna success=True
    sin intentar reenviar (protección anti-duplicados)
    """
    # Modificar el mock para simular que ya fue enviado
    mock_db.solicitudes_netcash.find_one = AsyncMock(return_value={
        'id': 'test_solicitud_123',
        'folio_mbco': '12345-209-M-11',
        'correo_tesoreria_enviado': True,  # YA FUE ENVIADO
        'fecha_envio_tesoreria': datetime.now(timezone.utc)
    })
    
    with patch('tesoreria_operacion_service.db', mock_db):
        from tesoreria_operacion_service import tesoreria_operacion_service
        
        resultado = await tesoreria_operacion_service.procesar_operacion_tesoreria('test_solicitud_123')
        
        # Verificaciones
        assert resultado is not None
        assert resultado.get('success') is True
        assert resultado.get('ya_enviado_antes') is True
        
        # Verificar que NO se intentó actualizar la DB (no reenvío)
        assert not mock_db.solicitudes_netcash.update_one.called
        
        print("✅ Test P0: Protección anti-duplicados funciona correctamente")


if __name__ == "__main__":
    # Ejecutar tests
    print("=" * 60)
    print("TEST: Fix P0 - TypeError 'await' outside async function")
    print("=" * 60)
    
    asyncio.run(test_procesar_operacion_tesoreria_success(
        mock_db=pytest.fixture(mock_db)(),
        mock_cuenta_deposito_service=pytest.fixture(mock_cuenta_deposito_service)(),
        mock_gmail_service=pytest.fixture(mock_gmail_service)()
    ))
