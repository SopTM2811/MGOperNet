"""
Servicio de Validación de Confianza OCR

Este servicio determina si los datos extraídos por OCR son confiables
o si se debe activar el modo de captura manual.

Criterios de fallo:
1. Monto detectado = $0.00
2. Sin montos encontrados en el texto
3. Sin CLABE detectada
4. Sin beneficiario detectado
5. Diferencia grande con capital esperado (>10%)
6. PDF marcado como "sin texto legible"
"""

import logging
from typing import Dict, List, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)


class OCRConfidenceValidator:
    """Validador de confianza en datos extraídos por OCR"""
    
    def __init__(self):
        self.umbral_diferencia_porcentual = 0.10  # 10%
        self.monto_minimo_valido = Decimal('1.00')
    
    def validar_confianza_ocr(
        self,
        datos_ocr: Dict,
        capital_esperado: Decimal = None
    ) -> Tuple[bool, str, List[str]]:
        """
        Valida si los datos extraídos por OCR son confiables
        
        Args:
            datos_ocr: Datos extraídos por OCR del comprobante
            capital_esperado: Capital esperado (opcional, para comparación)
        
        Returns:
            Tuple de (es_confiable, motivo_fallo, lista_advertencias)
        """
        logger.info("[OCR-Confidence] Iniciando validación de confianza OCR")
        
        advertencias = []
        es_confiable = True
        motivo_fallo = None
        
        # 1. Verificar que hay texto extraído
        texto_extraido = datos_ocr.get('texto_completo', '')
        if not texto_extraido or len(texto_extraido.strip()) < 50:
            es_confiable = False
            motivo_fallo = "sin_texto_legible"
            logger.error("[OCR-Confidence] ❌ Sin texto legible en el PDF")
            return es_confiable, motivo_fallo, ["PDF sin texto legible o demasiado corto"]
        
        logger.info(f"[OCR-Confidence] Texto extraído: {len(texto_extraido)} caracteres")
        
        # 2. Verificar monto detectado
        monto_detectado = datos_ocr.get('monto_detectado')
        if monto_detectado is None:
            es_confiable = False
            motivo_fallo = "sin_montos_encontrados"
            advertencias.append("No se detectó ningún monto en el comprobante")
            logger.error("[OCR-Confidence] ❌ Sin montos detectados")
        elif Decimal(str(monto_detectado)) < self.monto_minimo_valido:
            es_confiable = False
            motivo_fallo = "monto_cero_o_muy_bajo"
            advertencias.append(f"Monto detectado muy bajo: ${monto_detectado}")
            logger.error(f"[OCR-Confidence] ❌ Monto muy bajo: ${monto_detectado}")
        else:
            logger.info(f"[OCR-Confidence] ✅ Monto detectado: ${monto_detectado}")
        
        # 3. Verificar CLABE
        clabe_detectada = datos_ocr.get('clabe_ordenante') or datos_ocr.get('cuenta_ordenante')
        if not clabe_detectada:
            advertencias.append("No se detectó CLABE ordenante")
            logger.warning("[OCR-Confidence] ⚠️ Sin CLABE detectada")
            # No es fallo crítico, pero suma a la desconfianza
        else:
            logger.info(f"[OCR-Confidence] ✅ CLABE detectada: {clabe_detectada[:4]}...")
        
        # 4. Verificar beneficiario
        beneficiario_detectado = datos_ocr.get('beneficiario_reportado') or datos_ocr.get('nombre_beneficiario')
        if not beneficiario_detectado:
            advertencias.append("No se detectó nombre del beneficiario")
            logger.warning("[OCR-Confidence] ⚠️ Sin beneficiario detectado")
            # No es fallo crítico, pero suma a la desconfianza
        else:
            logger.info(f"[OCR-Confidence] ✅ Beneficiario: {beneficiario_detectado}")
        
        # 5. Comparar con capital esperado (si se proporciona)
        if capital_esperado and monto_detectado and Decimal(str(monto_detectado)) >= self.monto_minimo_valido:
            diferencia_abs = abs(Decimal(str(monto_detectado)) - capital_esperado)
            diferencia_porcentual = diferencia_abs / capital_esperado if capital_esperado > 0 else 1
            
            if diferencia_porcentual > self.umbral_diferencia_porcentual:
                es_confiable = False
                motivo_fallo = "diferencia_grande_con_esperado"
                advertencias.append(
                    f"Diferencia grande: detectado ${monto_detectado:,.2f} "
                    f"vs esperado ${capital_esperado:,.2f} "
                    f"({diferencia_porcentual*100:.1f}%)"
                )
                logger.error(
                    f"[OCR-Confidence] ❌ Diferencia grande: "
                    f"{diferencia_porcentual*100:.1f}% (umbral: {self.umbral_diferencia_porcentual*100}%)"
                )
            else:
                logger.info(f"[OCR-Confidence] ✅ Diferencia aceptable: {diferencia_porcentual*100:.1f}%")
        
        # 6. Verificar banco detectado
        banco_detectado = datos_ocr.get('banco_ordenante', '').upper()
        if banco_detectado:
            logger.info(f"[OCR-Confidence] Banco detectado: {banco_detectado}")
            
            # Bancos conocidos por tener problemas de lectura
            bancos_problematicos = ['ESPIRAL', 'FONDEADORA']
            if any(banco in banco_detectado for banco in bancos_problematicos):
                advertencias.append(f"Banco con historial de problemas de OCR: {banco_detectado}")
                logger.warning(f"[OCR-Confidence] ⚠️ Banco problemático: {banco_detectado}")
        
        # Resultado final
        if es_confiable:
            logger.info("[OCR-Confidence] ✅ OCR confiable - se puede usar automáticamente")
        else:
            logger.error(f"[OCR-Confidence] ❌ OCR NO confiable - motivo: {motivo_fallo}")
            logger.error(f"[OCR-Confidence] Advertencias: {advertencias}")
        
        return es_confiable, motivo_fallo, advertencias
    
    def requiere_captura_manual(self, datos_ocr: Dict) -> bool:
        """
        Determina si se requiere captura manual
        
        Args:
            datos_ocr: Datos extraídos por OCR
        
        Returns:
            True si requiere captura manual
        """
        es_confiable, motivo, _ = self.validar_confianza_ocr(datos_ocr)
        return not es_confiable
    
    def generar_resumen_validacion(
        self,
        es_confiable: bool,
        motivo_fallo: str,
        advertencias: List[str]
    ) -> Dict:
        """
        Genera un resumen estructurado de la validación
        
        Returns:
            Dict con resumen de la validación
        """
        return {
            "ocr_confiable": es_confiable,
            "requiere_captura_manual": not es_confiable,
            "motivo_fallo": motivo_fallo if not es_confiable else None,
            "advertencias": advertencias,
            "nivel_confianza": "alto" if es_confiable and len(advertencias) == 0 else
                              "medio" if es_confiable and len(advertencias) > 0 else
                              "bajo"
        }


# Instancia global
ocr_confidence_validator = OCRConfidenceValidator()
