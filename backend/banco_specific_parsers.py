"""
Parsers Específicos por Banco

Este módulo contiene reglas de parseo específicas para cada banco,
permitiendo extraer correctamente montos, CLABE y beneficiarios
según el formato particular de cada institución.
"""

import re
import logging
from typing import Dict, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class BancoParser:
    """Parser base para comprobantes bancarios"""
    
    def identificar_banco(self, texto: str) -> Optional[str]:
        """
        Identifica el banco basándose en el texto del comprobante
        
        Args:
            texto: Texto extraído del PDF
        
        Returns:
            Nombre del banco o None
        """
        texto_upper = texto.upper()
        
        # Diccionario de patrones por banco
        patrones_banco = {
            'ALBO': ['ALBO', 'ALBO BANK'],
            'ESPIRAL': ['ESPIRAL', 'BANCO ESPIRAL'],
            'FONDEADORA': ['FONDEADORA'],
            'BBVA': ['BBVA', 'BANCOMER'],
            'SANTANDER': ['SANTANDER'],
            'BANAMEX': ['BANAMEX', 'CITIBANAMEX'],
            'BANORTE': ['BANORTE'],
            'STP': ['STP', 'SISTEMA DE TRANSFERENCIAS'],
        }
        
        for banco, palabras_clave in patrones_banco.items():
            if any(palabra in texto_upper for palabra in palabras_clave):
                logger.info(f"[BancoParser] Banco identificado: {banco}")
                return banco
        
        logger.warning("[BancoParser] No se pudo identificar el banco")
        return None
    
    def parsear(self, texto: str) -> Dict:
        """
        Parsea el comprobante genéricamente
        
        Args:
            texto: Texto del comprobante
        
        Returns:
            Dict con datos extraídos
        """
        raise NotImplementedError("Debe implementarse en cada parser específico")


class ALBOParser(BancoParser):
    """
    Parser específico para comprobantes de ALBO
    
    Problema conocido: ALBO tiene una línea "Comisiones $0.00" que se puede
    confundir con el monto total. El monto real está en "Monto total".
    """
    
    def parsear(self, texto: str) -> Dict:
        """
        Parsea comprobante de ALBO
        
        Busca específicamente:
        - "Monto total: $X,XXX.XX" (no "Comisiones")
        - CLABE ordenante
        - Beneficiario
        """
        logger.info("[ALBOParser] Parseando comprobante de ALBO")
        
        resultado = {
            'banco': 'ALBO',
            'monto_detectado': None,
            'clabe_ordenante': None,
            'beneficiario_reportado': None
        }
        
        # 1. Buscar "Monto total" explícitamente (NO comisiones)
        # Patrón: "Monto total" seguido de monto
        patron_monto_total = r'Monto\s+total[:\s]+\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        match_monto = re.search(patron_monto_total, texto, re.IGNORECASE)
        
        if match_monto:
            monto_str = match_monto.group(1).replace(',', '')
            try:
                resultado['monto_detectado'] = float(monto_str)
                logger.info(f"[ALBOParser] ✅ Monto total encontrado: ${resultado['monto_detectado']:,.2f}")
            except ValueError:
                logger.error(f"[ALBOParser] Error convirtiendo monto: {monto_str}")
        
        # Regla de seguridad ALBO: NO usar "Comisiones" como monto
        patron_comisiones = r'Comisiones[:\s]+\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        match_comisiones = re.search(patron_comisiones, texto, re.IGNORECASE)
        if match_comisiones:
            comision_str = match_comisiones.group(1).replace(',', '')
            logger.info(f"[ALBOParser] Comisiones detectadas (IGNORADAS): ${comision_str}")
            # Explícitamente NO usamos esto como monto
        
        # 2. Buscar CLABE
        patron_clabe = r'CLABE[:\s]+(\d{18})'
        match_clabe = re.search(patron_clabe, texto, re.IGNORECASE)
        if match_clabe:
            resultado['clabe_ordenante'] = match_clabe.group(1)
            logger.info(f"[ALBOParser] ✅ CLABE encontrada: {resultado['clabe_ordenante']}")
        
        # 3. Buscar beneficiario
        patron_beneficiario = r'Beneficiario[:\s]+([A-ZÁ-Ú\s]+(?:SA|SC|CV)?)'
        match_beneficiario = re.search(patron_beneficiario, texto, re.IGNORECASE)
        if match_beneficiario:
            resultado['beneficiario_reportado'] = match_beneficiario.group(1).strip()
            logger.info(f"[ALBOParser] ✅ Beneficiario: {resultado['beneficiario_reportado']}")
        
        # Validación final: Si monto = $0.00, marcar como fallo
        if resultado['monto_detectado'] is not None and resultado['monto_detectado'] < 0.01:
            logger.error("[ALBOParser] ❌ Monto es $0.00 - esto NO es válido para ALBO")
            resultado['error'] = "monto_cero_invalido"
            resultado['monto_detectado'] = None
        
        return resultado


class ESPIRALParser(BancoParser):
    """
    Parser específico para comprobantes de ESPIRAL
    
    Problema conocido: A veces se marca como "sin texto legible" pero
    sí tiene texto seleccionable con CLABE y beneficiario.
    """
    
    def parsear(self, texto: str) -> Dict:
        """
        Parsea comprobante de ESPIRAL/Fondeadora
        
        Formatos detectados:
        - "Importe transferido: 190000.00 MXN"
        - "Cuenta de destino: XXXXXXXXXXXXXXXXXX"
        - "Nombre destinatario: NOMBRE"
        """
        logger.info("[ESPIRALParser] Parseando comprobante de ESPIRAL/Fondeadora")
        
        resultado = {
            'banco': 'ESPIRAL',
            'monto_detectado': None,
            'clabe_ordenante': None,
            'beneficiario_reportado': None
        }
        
        # 1. Buscar importe/monto (patrones basados en comprobantes reales)
        patrones_monto = [
            r'Importe\s+transferido[:\s]+(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*MXN',  # Formato real ESPIRAL
            r'Importe[:\s]+\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'Monto\s+total[:\s]+\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'Total[:\s]+\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        ]
        
        for patron in patrones_monto:
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                monto_str = match.group(1).replace(',', '')
                try:
                    resultado['monto_detectado'] = float(monto_str)
                    logger.info(f"[ESPIRALParser] ✅ Monto encontrado: ${resultado['monto_detectado']:,.2f}")
                    break
                except ValueError:
                    continue
        
        # 2. Buscar CLABE (18 dígitos)
        patron_clabe = r'(?:CLABE|Cuenta)[:\s]*(\d{18})'
        match_clabe = re.search(patron_clabe, texto, re.IGNORECASE)
        if match_clabe:
            resultado['clabe_ordenante'] = match_clabe.group(1)
            logger.info(f"[ESPIRALParser] ✅ CLABE encontrada: {resultado['clabe_ordenante']}")
        
        # Si no encontramos CLABE con patrón, buscar cualquier secuencia de 18 dígitos
        if not resultado['clabe_ordenante']:
            match_clabe_generico = re.search(r'\b(\d{18})\b', texto)
            if match_clabe_generico:
                resultado['clabe_ordenante'] = match_clabe_generico.group(1)
                logger.info(f"[ESPIRALParser] ✅ CLABE encontrada (genérico): {resultado['clabe_ordenante']}")
        
        # 3. Buscar beneficiario
        patron_beneficiario = r'Beneficiario[:\s]+([A-ZÁ-Ú\s]+(?:SA|SC|CV)?)'
        match_beneficiario = re.search(patron_beneficiario, texto, re.IGNORECASE)
        if match_beneficiario:
            resultado['beneficiario_reportado'] = match_beneficiario.group(1).strip()
            logger.info(f"[ESPIRALParser] ✅ Beneficiario: {resultado['beneficiario_reportado']}")
        
        return resultado


class BancoParserFactory:
    """Factory para obtener el parser correcto según el banco"""
    
    @staticmethod
    def get_parser(texto: str) -> BancoParser:
        """
        Obtiene el parser específico según el banco detectado
        
        Args:
            texto: Texto del comprobante
        
        Returns:
            Parser específico o genérico
        """
        # Identificar banco
        parser_base = BancoParser()
        banco = parser_base.identificar_banco(texto)
        
        # Retornar parser específico
        if banco == 'ALBO':
            return ALBOParser()
        elif banco in ['ESPIRAL', 'FONDEADORA']:
            return ESPIRALParser()
        else:
            # Parser genérico para otros bancos
            logger.info(f"[ParserFactory] Usando parser genérico para banco: {banco or 'desconocido'}")
            return BancoParser()
    
    @staticmethod
    def parsear_comprobante(texto: str) -> Dict:
        """
        Parsea un comprobante usando el parser adecuado
        
        Args:
            texto: Texto extraído del PDF
        
        Returns:
            Dict con datos parseados
        """
        parser = BancoParserFactory.get_parser(texto)
        
        try:
            return parser.parsear(texto)
        except NotImplementedError:
            # Si es el parser genérico (no implementado), hacer parseo básico
            logger.warning("[ParserFactory] Parser genérico - extracción básica")
            return {
                'banco': 'DESCONOCIDO',
                'monto_detectado': None,
                'clabe_ordenante': None,
                'beneficiario_reportado': None,
                'requiere_parser_especifico': True
            }


# Instancia global
banco_parser_factory = BancoParserFactory()
