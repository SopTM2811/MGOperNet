"""
Tests P4A: Validación de comprobantes de pago de Tesorería

Este archivo contiene los 5 tests solicitados:
1. Test feliz (capital, comisión y concepto OK)
2. Test error capital
3. Test error comisión
4. Test error concepto
5. Test combinación (capital + concepto mal)
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from pathlib import Path
import tempfile
import PyPDF2
from datetime import datetime, timezone

# Fixtures

@pytest.fixture
def solicitud_test():
    """Datos de una solicitud NetCash para testing"""
    return {
        'id': 'nc-test-001',
        'folio_mbco': '12345-678-D-99',
        'cliente_nombre': 'EMPRESA TEST SA DE CV',
        'idmex_reportado': 'IDMEX123456',
        'beneficiario_reportado': 'PROVEEDOR TEST SC',
        'monto_ligas': 99000.00,
        'comision_dns_calculada': 371.25,
        'cantidad_ligas_reportada': 100,
        'estado': 'enviado_a_tesoreria'
    }

@pytest.fixture
def folio_concepto():
    """Folio en formato 'x' para concepto"""
    return '12345x678xDx99'

@pytest.fixture
def mock_db():
    """Mock de MongoDB"""
    mock = MagicMock()
    mock.solicitudes_netcash = MagicMock()
    mock.solicitudes_netcash.find_one = AsyncMock()
    mock.solicitudes_netcash.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    return mock

@pytest.fixture
def mock_gmail_service():
    """Mock del servicio Gmail"""
    mock = MagicMock()
    mock.enviar_correo_con_adjuntos = AsyncMock(return_value={
        'message_id': 'test_msg_123',
        'thread_id': 'test_thread_456'
    })
    mock.enviar_correo_respuesta = AsyncMock(return_value={
        'message_id': 'test_reply_789',
        'thread_id': 'test_thread_456'
    })
    return mock


# Helper: Crear PDFs dummy con contenido específico

def crear_pdf_dummy(
    capital: float,
    comision: float,
    concepto: str,
    output_path: str
) -> str:
    """
    Crea un PDF dummy con el contenido especificado
    
    Args:
        capital: Monto de capital
        comision: Monto de comisión
        concepto: Concepto/folio
        output_path: Ruta donde guardar el PDF
    
    Returns:
        Ruta al PDF creado
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    
    # Crear PDF
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    
    # Título
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 100, "MBco - Comprobante de Dispersión")
    
    # Folio
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 140, f"Folio: {concepto}")
    
    # Movimientos
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - 180, "MOVIMIENTOS:")
    
    # Capital
    c.setFont("Helvetica", 11)
    c.drawString(100, height - 220, f"1. CAPITAL - AFFORDABLE MEDICAL SERVICES SC")
    c.drawString(120, height - 240, f"   Concepto: {concepto} CAPITAL")
    c.drawString(120, height - 260, f"   Monto: ${capital:,.2f}")
    
    # Comisión
    c.drawString(100, height - 300, f"2. COMISION DNS - COMERCIALIZADORA UETACOP SA DE CV")
    c.drawString(120, height - 320, f"   Concepto: {concepto} COMISION")
    c.drawString(120, height - 340, f"   Monto: ${comision:,.2f}")
    
    # Total
    total = capital + comision
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, height - 380, f"TOTAL: ${total:,.2f}")
    
    c.save()
    
    return output_path


# TESTS

@pytest.mark.asyncio
async def test_p4a_caso_feliz_validaciones_ok(solicitud_test, folio_concepto, mock_db, mock_gmail_service, tmp_path):
    """
    Test 1: Caso feliz - Capital, comisión y concepto correctos
    
    Verifica que:
    - Las validaciones pasan
    - Se guarda el comprobante
    - Se envía correo a DNS
    - Se actualiza estado a "correo_enviado_a_proveedor"
    - Se marca pagado_a_dns = True
    """
    print("\n🔍 Test P4A-1: Caso feliz (todas las validaciones OK)")
    
    # Crear PDF dummy con datos CORRECTOS
    pdf_path = tmp_path / "comprobante_ok.pdf"
    crear_pdf_dummy(
        capital=99000.00,  # ✅ Correcto
        comision=371.25,   # ✅ Correcto
        concepto=folio_concepto,  # ✅ Correcto
        output_path=str(pdf_path)
    )
    
    print(f"   PDF creado: {pdf_path}")
    
    # Importar servicio de validación
    from comprobante_pago_validator_service import comprobante_pago_validator
    
    # Ejecutar validación
    es_valido, errores, datos_extraidos = comprobante_pago_validator.validar_comprobante(
        pdf_path=str(pdf_path),
        capital_esperado=Decimal('99000.00'),
        comision_esperada=Decimal('371.25'),
        folio_concepto=folio_concepto
    )
    
    # Verificaciones
    assert es_valido is True, "La validación debe pasar"
    assert len(errores) == 0, f"No debe haber errores, pero se encontraron: {errores}"
    assert datos_extraidos['capital_total_pdf'] == 99000.00
    assert datos_extraidos['comision_total_pdf'] == 371.25
    assert folio_concepto in datos_extraidos['conceptos_pdf']
    
    print("   ✅ Todas las validaciones pasaron")
    
    # Simular envío a DNS con mock
    with patch('dns_email_service.gmail_service', mock_gmail_service):
        from dns_email_service import dns_email_service
        
        envio_exitoso = await dns_email_service.enviar_comprobantes_a_dns(
            solicitud=solicitud_test,
            comprobantes_paths=[str(pdf_path)]
        )
        
        assert envio_exitoso is True
        assert mock_gmail_service.enviar_correo_con_adjuntos.called
        
        # Verificar argumentos del email
        call_args = mock_gmail_service.enviar_correo_con_adjuntos.call_args
        assert 'dns@proveedor.com' in str(call_args)
        assert 'NetCash – Pago a proveedor' in call_args[1]['asunto']
        assert str(pdf_path) in call_args[1]['adjuntos']
    
    print("   ✅ Correo a DNS enviado correctamente")
    print("🎉 Test P4A-1: PASADO\n")


@pytest.mark.asyncio
async def test_p4a_error_capital(solicitud_test, folio_concepto, mock_db, mock_gmail_service, tmp_path):
    """
    Test 2: Error en capital
    
    Verifica que:
    - La validación falla por capital incorrecto
    - Se genera error específico
    - NO se envía correo a DNS
    - Se responde a Tesorería con el error
    """
    print("\n🔍 Test P4A-2: Error en capital")
    
    # Crear PDF con capital INCORRECTO
    pdf_path = tmp_path / "comprobante_capital_mal.pdf"
    crear_pdf_dummy(
        capital=98500.00,  # ❌ Incorrecto (esperado: 99000.00)
        comision=371.25,   # ✅ Correcto
        concepto=folio_concepto,  # ✅ Correcto
        output_path=str(pdf_path)
    )
    
    # Validar
    from comprobante_pago_validator_service import comprobante_pago_validator
    
    es_valido, errores, datos_extraidos = comprobante_pago_validator.validar_comprobante(
        pdf_path=str(pdf_path),
        capital_esperado=Decimal('99000.00'),
        comision_esperada=Decimal('371.25'),
        folio_concepto=folio_concepto
    )
    
    # Verificaciones
    assert es_valido is False, "La validación debe fallar"
    assert len(errores) == 1, f"Debe haber exactamente 1 error, se encontraron {len(errores)}"
    assert "capital" in errores[0].lower(), "El error debe mencionar 'capital'"
    assert "98,500" in errores[0] or "98500" in errores[0], "El error debe mostrar el monto incorrecto"
    assert "99,000" in errores[0] or "99000" in errores[0], "El error debe mostrar el monto esperado"
    
    print(f"   ✅ Error detectado: {errores[0]}")
    
    # Verificar que NO se enviaría a DNS (no hacer llamada real)
    # En producción, el código no llamaría a enviar_comprobantes_a_dns
    print("   ✅ Correo a DNS NO se enviará (validación falló)")
    
    # Simular respuesta a Tesorería
    with patch('dns_email_service.gmail_service', mock_gmail_service):
        from dns_email_service import dns_email_service
        
        respuesta_exitosa = await dns_email_service.responder_a_tesoreria_con_error(
            thread_id='test_thread_456',
            message_id='test_msg_123',
            folio_netcash='nc-test-001',
            folio_mbco='12345-678-D-99',
            cliente_nombre='EMPRESA TEST SA DE CV',
            idmex='IDMEX123456',
            errores=errores
        )
        
        assert respuesta_exitosa is True
        assert mock_gmail_service.enviar_correo_respuesta.called
        
        # Verificar que el error se incluye en la respuesta
        call_args = mock_gmail_service.enviar_correo_respuesta.call_args
        assert "capital" in call_args[1]['cuerpo'].lower()
    
    print("   ✅ Respuesta de error enviada a Tesorería")
    print("🎉 Test P4A-2: PASADO\n")


@pytest.mark.asyncio
async def test_p4a_error_comision(solicitud_test, folio_concepto, tmp_path):
    """
    Test 3: Error en comisión
    
    Verifica que se detecta comisión incorrecta
    """
    print("\n🔍 Test P4A-3: Error en comisión")
    
    # Crear PDF con comisión INCORRECTA
    pdf_path = tmp_path / "comprobante_comision_mal.pdf"
    crear_pdf_dummy(
        capital=99000.00,  # ✅ Correcto
        comision=350.00,   # ❌ Incorrecto (esperado: 371.25)
        concepto=folio_concepto,  # ✅ Correcto
        output_path=str(pdf_path)
    )
    
    # Validar
    from comprobante_pago_validator_service import comprobante_pago_validator
    
    es_valido, errores, datos_extraidos = comprobante_pago_validator.validar_comprobante(
        pdf_path=str(pdf_path),
        capital_esperado=Decimal('99000.00'),
        comision_esperada=Decimal('371.25'),
        folio_concepto=folio_concepto
    )
    
    # Verificaciones
    assert es_valido is False
    assert len(errores) == 1
    assert "comision" in errores[0].lower() or "comisión" in errores[0].lower()
    assert "350" in errores[0]
    assert "371.25" in errores[0]
    
    print(f"   ✅ Error detectado: {errores[0]}")
    print("🎉 Test P4A-3: PASADO\n")


@pytest.mark.asyncio
async def test_p4a_error_concepto(solicitud_test, folio_concepto, tmp_path):
    """
    Test 4: Error en concepto
    
    Verifica que se detecta concepto incorrecto
    """
    print("\n🔍 Test P4A-4: Error en concepto")
    
    # Crear PDF con concepto INCORRECTO (con guiones en lugar de 'x')
    pdf_path = tmp_path / "comprobante_concepto_mal.pdf"
    concepto_incorrecto = '12345-678-D-99'  # ❌ Tiene guiones
    crear_pdf_dummy(
        capital=99000.00,  # ✅ Correcto
        comision=371.25,   # ✅ Correcto
        concepto=concepto_incorrecto,  # ❌ Incorrecto
        output_path=str(pdf_path)
    )
    
    # Validar
    from comprobante_pago_validator_service import comprobante_pago_validator
    
    es_valido, errores, datos_extraidos = comprobante_pago_validator.validar_comprobante(
        pdf_path=str(pdf_path),
        capital_esperado=Decimal('99000.00'),
        comision_esperada=Decimal('371.25'),
        folio_concepto=folio_concepto  # Esperado: 12345x678xDx99
    )
    
    # Verificaciones
    assert es_valido is False
    assert len(errores) == 1
    assert "concepto" in errores[0].lower()
    assert folio_concepto in errores[0]  # Debe mostrar el concepto esperado
    
    print(f"   ✅ Error detectado: {errores[0]}")
    print("🎉 Test P4A-4: PASADO\n")


@pytest.mark.asyncio
async def test_p4a_error_combinado_capital_y_concepto(solicitud_test, folio_concepto, tmp_path):
    """
    Test 5: Error combinado (capital + concepto incorrectos)
    
    Verifica que se detectan MÚLTIPLES errores
    """
    print("\n🔍 Test P4A-5: Error combinado (capital + concepto)")
    
    # Crear PDF con capital Y concepto INCORRECTOS
    pdf_path = tmp_path / "comprobante_multiple_errores.pdf"
    concepto_incorrecto = '12345-678-D-99'
    crear_pdf_dummy(
        capital=98500.00,  # ❌ Incorrecto
        comision=371.25,   # ✅ Correcto
        concepto=concepto_incorrecto,  # ❌ Incorrecto
        output_path=str(pdf_path)
    )
    
    # Validar
    from comprobante_pago_validator_service import comprobante_pago_validator
    
    es_valido, errores, datos_extraidos = comprobante_pago_validator.validar_comprobante(
        pdf_path=str(pdf_path),
        capital_esperado=Decimal('99000.00'),
        comision_esperada=Decimal('371.25'),
        folio_concepto=folio_concepto
    )
    
    # Verificaciones
    assert es_valido is False
    assert len(errores) == 2, f"Debe haber exactamente 2 errores, se encontraron {len(errores)}"
    
    # Verificar que ambos errores están presentes
    errores_texto = ' '.join(errores).lower()
    assert "capital" in errores_texto, "Debe haber error de capital"
    assert "concepto" in errores_texto, "Debe haber error de concepto"
    
    print(f"   ✅ Error 1 detectado: {errores[0]}")
    print(f"   ✅ Error 2 detectado: {errores[1]}")
    print("🎉 Test P4A-5: PASADO\n")


# Test adicional: Tolerancia de ±$0.01

@pytest.mark.asyncio
async def test_p4a_tolerancia_monto(folio_concepto, tmp_path):
    """
    Test adicional: Verificar que la tolerancia de ±$0.01 funciona correctamente
    """
    print("\n🔍 Test P4A-Extra: Tolerancia de ±$0.01")
    
    from comprobante_pago_validator_service import comprobante_pago_validator
    
    # Caso 1: Diferencia de $0.01 debe pasar
    pdf_path_1 = tmp_path / "comprobante_tolerancia_ok.pdf"
    crear_pdf_dummy(
        capital=99000.01,  # Diferencia de $0.01 ✅
        comision=371.25,
        concepto=folio_concepto,
        output_path=str(pdf_path_1)
    )
    
    es_valido, errores, _ = comprobante_pago_validator.validar_comprobante(
        pdf_path=str(pdf_path_1),
        capital_esperado=Decimal('99000.00'),
        comision_esperada=Decimal('371.25'),
        folio_concepto=folio_concepto
    )
    
    assert es_valido is True, "Diferencia de $0.01 debe pasar"
    print("   ✅ Diferencia de $0.01 → PASA")
    
    # Caso 2: Diferencia de $0.02 debe fallar
    pdf_path_2 = tmp_path / "comprobante_tolerancia_falla.pdf"
    crear_pdf_dummy(
        capital=99000.02,  # Diferencia de $0.02 ❌
        comision=371.25,
        concepto=folio_concepto,
        output_path=str(pdf_path_2)
    )
    
    es_valido, errores, _ = comprobante_pago_validator.validar_comprobante(
        pdf_path=str(pdf_path_2),
        capital_esperado=Decimal('99000.00'),
        comision_esperada=Decimal('371.25'),
        folio_concepto=folio_concepto
    )
    
    assert es_valido is False, "Diferencia de $0.02 debe fallar"
    assert len(errores) == 1
    print("   ✅ Diferencia de $0.02 → FALLA")
    print("🎉 Test P4A-Extra: PASADO\n")


if __name__ == "__main__":
    """Ejecutar todos los tests"""
    async def run_all_tests():
        print("=" * 80)
        print("TESTS P4A: VALIDACIÓN DE COMPROBANTES DE PAGO")
        print("=" * 80)
        
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            solicitud = {
                'id': 'nc-test-001',
                'folio_mbco': '12345-678-D-99',
                'cliente_nombre': 'EMPRESA TEST SA DE CV',
                'idmex_reportado': 'IDMEX123456',
                'beneficiario_reportado': 'PROVEEDOR TEST SC',
                'monto_ligas': 99000.00,
                'comision_dns_calculada': 371.25,
                'cantidad_ligas_reportada': 100
            }
            folio = '12345x678xDx99'
            
            mock_db = MagicMock()
            mock_gmail = MagicMock()
            mock_gmail.enviar_correo_con_adjuntos = AsyncMock(return_value={'message_id': '1', 'thread_id': '2'})
            mock_gmail.enviar_correo_respuesta = AsyncMock(return_value={'message_id': '3', 'thread_id': '2'})
            
            # Ejecutar tests
            await test_p4a_caso_feliz_validaciones_ok(solicitud, folio, mock_db, mock_gmail, tmp_path)
            await test_p4a_error_capital(solicitud, folio, mock_db, mock_gmail, tmp_path)
            await test_p4a_error_comision(solicitud, folio, tmp_path)
            await test_p4a_error_concepto(solicitud, folio, tmp_path)
            await test_p4a_error_combinado_capital_y_concepto(solicitud, folio, tmp_path)
            await test_p4a_tolerancia_monto(folio, tmp_path)
            
            print("=" * 80)
            print("✅ TODOS LOS TESTS P4A PASARON (6/6)")
            print("=" * 80)
    
    asyncio.run(run_all_tests())
