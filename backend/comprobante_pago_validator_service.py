"""
Servicio de Validación de Comprobantes de Pago - P4A

Este servicio valida que los comprobantes de pago enviados por Tesorería
coincidan con los montos y conceptos esperados para una operación NetCash.

Validaciones:
1. Capital total coincide (±$0.01)
2. Comisión DNS coincide (±$0.01)
3. Concepto = folio_mbco con formato "x" (sin guiones)

Si todas las validaciones pasan → aprobado para envío a DNS
Si alguna falla → generar reporte de errores para Tesorería
"""

import os
import re
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import PyPDF2

logger = logging.getLogger(__name__)


class ComprobantePagoValidatorService:
    """Servicio para validar comprobantes de pago de Tesorería"""
    
    def __init__(self):
        self.tolerancia_monto = Decimal('0.01')  # Tolerancia de 1 centavo
    
    def validar_comprobante(
        self, 
        pdf_path: str,
        capital_esperado: Decimal,
        comision_esperada: Decimal,
        folio_concepto: str
    ) -> Tuple[bool, List[str], Dict]:
        """
        Valida un comprobante de pago contra los montos esperados
        
        Args:
            pdf_path: Ruta al PDF del comprobante
            capital_esperado: Monto de capital que se debía pagar
            comision_esperada: Monto de comisión DNS que se debía pagar
            folio_concepto: Folio MBco en formato "x" (ej: 23456x209xMx11)
        
        Returns:
            Tuple de (es_valido, lista_errores, datos_extraidos)
            - es_valido: True si todas las validaciones pasan
            - lista_errores: Lista de mensajes de error (vacía si es_válido=True)
            - datos_extraidos: Dict con capital_pdf, comision_pdf, conceptos_pdf, etc.
        """
        logger.info(f"[ComprobantePago-P4A] Iniciando validación de comprobante: {pdf_path}")
        logger.info(f"[ComprobantePago-P4A] Capital esperado: ${capital_esperado}")
        logger.info(f"[ComprobantePago-P4A] Comisión esperada: ${comision_esperada}")
        logger.info(f"[ComprobantePago-P4A] Concepto esperado: {folio_concepto}")
        
        errores = []
        datos_extraidos = {}
        
        try:
            # 1. Leer y extraer texto del PDF
            texto_completo = self._extraer_texto_pdf(pdf_path)
            
            if not texto_completo:
                error_msg = "No se pudo extraer texto del PDF. El archivo puede estar dañado o ser un escaneo sin OCR."
                logger.error(f"[ComprobantePago-P4A] {error_msg}")
                return False, [error_msg], {}
            
            logger.info(f"[ComprobantePago-P4A] Texto extraído del PDF: {len(texto_completo)} caracteres")
            
            # 2. Parsear el texto para extraer montos y conceptos
            movimientos = self._parsear_movimientos(texto_completo, folio_concepto)
            
            if not movimientos:
                error_msg = f"No se encontraron movimientos relacionados con el folio {folio_concepto} en el comprobante."
                logger.error(f"[ComprobantePago-P4A] {error_msg}")
                return False, [error_msg], {"texto_pdf": texto_completo[:500]}
            
            logger.info(f"[ComprobantePago-P4A] Se encontraron {len(movimientos)} movimiento(s)")
            
            # 3. Clasificar y sumar movimientos
            capital_pdf, comision_pdf, conceptos_encontrados = self._clasificar_y_sumar_movimientos(movimientos)
            
            datos_extraidos = {
                "capital_total_pdf": float(capital_pdf),
                "comision_total_pdf": float(comision_pdf),
                "conceptos_pdf": conceptos_encontrados,
                "num_movimientos": len(movimientos),
                "movimientos_detalle": movimientos
            }
            
            logger.info(f"[ComprobantePago-P4A] Capital en PDF: ${capital_pdf}")
            logger.info(f"[ComprobantePago-P4A] Comisión en PDF: ${comision_pdf}")
            logger.info(f"[ComprobantePago-P4A] Conceptos encontrados: {conceptos_encontrados}")
            
            # 4. Validar capital
            diferencia_capital = abs(capital_pdf - capital_esperado)
            if diferencia_capital > self.tolerancia_monto:
                error_msg = f"Diferencia en capital: esperado ${capital_esperado:,.2f}, comprobante ${capital_pdf:,.2f} (diferencia: ${diferencia_capital:,.2f})"
                errores.append(error_msg)
                logger.error(f"[ComprobantePago-P4A] ❌ {error_msg}")
            else:
                logger.info(f"[ComprobantePago-P4A] ✅ Capital OK (diferencia: ${diferencia_capital:,.2f})")
            
            # 5. Validar comisión
            diferencia_comision = abs(comision_pdf - comision_esperada)
            if diferencia_comision > self.tolerancia_monto:
                error_msg = f"Diferencia en comisión: esperada ${comision_esperada:,.2f}, comprobante ${comision_pdf:,.2f} (diferencia: ${diferencia_comision:,.2f})"
                errores.append(error_msg)
                logger.error(f"[ComprobantePago-P4A] ❌ {error_msg}")
            else:
                logger.info(f"[ComprobantePago-P4A] ✅ Comisión OK (diferencia: ${diferencia_comision:,.2f})")
            
            # 6. Validar concepto
            concepto_correcto = self._validar_concepto(conceptos_encontrados, folio_concepto)
            if not concepto_correcto:
                error_msg = f'Concepto incorrecto: esperado "{folio_concepto}", encontrado {conceptos_encontrados}'
                errores.append(error_msg)
                logger.error(f"[ComprobantePago-P4A] ❌ {error_msg}")
            else:
                logger.info(f"[ComprobantePago-P4A] ✅ Concepto OK")
            
            # 7. Resultado final
            es_valido = len(errores) == 0
            
            if es_valido:
                logger.info(f"[ComprobantePago-P4A] 🎉 ✅ Todas las validaciones pasaron")
            else:
                logger.error(f"[ComprobantePago-P4A] ❌ Validación falló con {len(errores)} error(es)")
            
            return es_valido, errores, datos_extraidos
            
        except Exception as e:
            error_msg = f"Error técnico al validar comprobante: {str(e)}"
            logger.exception(f"[ComprobantePago-P4A] {error_msg}")
            return False, [error_msg], {}
    
    def _extraer_texto_pdf(self, pdf_path: str) -> str:
        """
        Extrae todo el texto de un PDF
        
        Args:
            pdf_path: Ruta al archivo PDF
        
        Returns:
            Texto completo del PDF
        """
        try:
            texto_completo = ""
            
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_paginas = len(pdf_reader.pages)
                
                logger.info(f"[ComprobantePago-P4A] PDF tiene {num_paginas} página(s)")
                
                for i, page in enumerate(pdf_reader.pages):
                    texto_pagina = page.extract_text()
                    if texto_pagina:
                        texto_completo += texto_pagina + "\n"
                        logger.debug(f"[ComprobantePago-P4A] Página {i+1}: {len(texto_pagina)} caracteres")
            
            return texto_completo
            
        except Exception as e:
            logger.exception(f"[ComprobantePago-P4A] Error extrayendo texto del PDF: {str(e)}")
            return ""
    
    def _parsear_movimientos(self, texto: str, folio_concepto: str) -> List[Dict]:
        """
        Parsea el texto del PDF para extraer movimientos relacionados con el folio
        
        Args:
            texto: Texto completo del PDF
            folio_concepto: Folio en formato "x" para buscar (ej: 23456x209xMx11)
        
        Returns:
            Lista de movimientos encontrados
        """
        movimientos = []
        
        # Normalizar texto
        texto = texto.upper()
        folio_concepto_upper = folio_concepto.upper()
        
        # Buscar líneas que contengan el folio_concepto
        lineas = texto.split('\n')
        
        for i, linea in enumerate(lineas):
            if folio_concepto_upper in linea:
                logger.debug(f"[ComprobantePago-P4A] Línea con folio encontrada: {linea[:100]}")
                
                # Intentar extraer monto de esta línea
                # Buscar patrones de montos: $123,456.78 o 123456.78 o 123,456
                patron_monto = r'\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
                montos_encontrados = re.findall(patron_monto, linea)
                
                if montos_encontrados:
                    # Tomar el último monto de la línea (suele ser el importe)
                    monto_str = montos_encontrados[-1].replace(',', '')
                    
                    try:
                        monto = Decimal(monto_str)
                        
                        # Determinar tipo de movimiento (capital o comisión)
                        tipo = self._clasificar_tipo_movimiento(linea)
                        
                        movimiento = {
                            "concepto": folio_concepto,
                            "monto": monto,
                            "tipo": tipo,
                            "linea_original": linea.strip(),
                            "linea_numero": i + 1
                        }
                        
                        movimientos.append(movimiento)
                        logger.info(f"[ComprobantePago-P4A] Movimiento encontrado: {tipo} ${monto} (línea {i+1})")
                        
                    except (ValueError, ArithmeticError) as e:
                        logger.warning(f"[ComprobantePago-P4A] No se pudo convertir monto '{monto_str}': {e}")
        
        # Si no encontramos movimientos con el método exacto, intentar método más flexible
        if not movimientos:
            logger.warning(f"[ComprobantePago-P4A] No se encontraron movimientos con folio exacto. Intentando búsqueda flexible...")
            movimientos = self._parsear_movimientos_flexible(texto, folio_concepto)
        
        return movimientos
    
    def _parsear_movimientos_flexible(self, texto: str, folio_concepto: str) -> List[Dict]:
        """
        Método alternativo de parseo más flexible para diferentes formatos de layout
        
        Args:
            texto: Texto del PDF
            folio_concepto: Folio a buscar
        
        Returns:
            Lista de movimientos
        """
        movimientos = []
        
        # Buscar patrones comunes de layouts bancarios
        # Ejemplo: MBCO 23456x209xMx11 CAPITAL  $99,000.00
        # Ejemplo: MBco 23456x209xMx11 COMISION $371.25
        
        patron_general = r'(?:MBCO|MBco)\s+' + re.escape(folio_concepto.upper()) + r'\s+(\w+).*?\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        
        coincidencias = re.finditer(patron_general, texto, re.IGNORECASE)
        
        for match in coincidencias:
            tipo_str = match.group(1).upper()
            monto_str = match.group(2).replace(',', '')
            
            try:
                monto = Decimal(monto_str)
                tipo = "capital" if "CAPITAL" in tipo_str else "comision" if "COMISION" in tipo_str else "desconocido"
                
                movimiento = {
                    "concepto": folio_concepto,
                    "monto": monto,
                    "tipo": tipo,
                    "linea_original": match.group(0),
                    "metodo": "flexible"
                }
                
                movimientos.append(movimiento)
                logger.info(f"[ComprobantePago-P4A] Movimiento flexible encontrado: {tipo} ${monto}")
                
            except (ValueError, ArithmeticError) as e:
                logger.warning(f"[ComprobantePago-P4A] Error procesando monto flexible: {e}")
        
        return movimientos
    
    def _clasificar_tipo_movimiento(self, linea: str) -> str:
        """
        Clasifica un movimiento como capital o comisión basándose en palabras clave
        
        Args:
            linea: Línea de texto del movimiento
        
        Returns:
            "capital" o "comision"
        """
        linea_upper = linea.upper()
        
        # Palabras clave para capital
        palabras_capital = ["CAPITAL", "AFFORDABLE", "LIGAS", "PROVEEDOR"]
        
        # Palabras clave para comisión
        palabras_comision = ["COMISION", "COMISIÓN", "DNS", "UETACOP", "COMERCIALIZADORA"]
        
        # Contar coincidencias
        score_capital = sum(1 for palabra in palabras_capital if palabra in linea_upper)
        score_comision = sum(1 for palabra in palabras_comision if palabra in linea_upper)
        
        if score_comision > score_capital:
            return "comision"
        elif score_capital > 0:
            return "capital"
        else:
            # Por defecto, asumir capital
            return "capital"
    
    def _clasificar_y_sumar_movimientos(self, movimientos: List[Dict]) -> Tuple[Decimal, Decimal, List[str]]:
        """
        Clasifica movimientos en capital y comisión, y suma los totales
        
        Args:
            movimientos: Lista de movimientos parseados
        
        Returns:
            Tuple de (capital_total, comision_total, conceptos_unicos)
        """
        capital_total = Decimal('0')
        comision_total = Decimal('0')
        conceptos_unicos = set()
        
        for mov in movimientos:
            tipo = mov.get('tipo', 'capital')
            monto = mov.get('monto', Decimal('0'))
            concepto = mov.get('concepto', '')
            
            if tipo == "comision":
                comision_total += monto
            else:
                capital_total += monto
            
            if concepto:
                conceptos_unicos.add(concepto)
        
        return capital_total, comision_total, list(conceptos_unicos)
    
    def _validar_concepto(self, conceptos_encontrados: List[str], folio_concepto_esperado: str) -> bool:
        """
        Valida que al menos uno de los conceptos encontrados coincida con el esperado
        
        Args:
            conceptos_encontrados: Lista de conceptos en el PDF
            folio_concepto_esperado: Concepto esperado
        
        Returns:
            True si hay coincidencia
        """
        if not conceptos_encontrados:
            return False
        
        folio_upper = folio_concepto_esperado.upper()
        
        for concepto in conceptos_encontrados:
            if concepto.upper() == folio_upper:
                return True
        
        return False


# Instancia global del servicio
comprobante_pago_validator = ComprobantePagoValidatorService()
