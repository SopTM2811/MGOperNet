"""Servicio para validar comprobantes contra la cuenta activa de NetCash"""

import os
import re
import logging
from typing import Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Intentar importar librerías de OCR/extracción
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    logger.warning("[ValidadorComprobantes] PyPDF2 no disponible")

try:
    from PIL import Image
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    logger.warning("[ValidadorComprobantes] pytesseract no disponible")


class ValidadorComprobantes:
    """Valida comprobantes de pago contra la cuenta activa"""
    
    def __init__(self):
        pass
    
    def extraer_texto_pdf(self, ruta_archivo: str) -> str:
        """Extrae texto de un archivo PDF"""
        if not PYPDF2_AVAILABLE:
            logger.warning("[ValidadorComprobantes] PyPDF2 no disponible, no se puede extraer texto de PDF")
            return ""
        
        try:
            texto = ""
            with open(ruta_archivo, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    texto += page.extract_text() + "\n"
            
            logger.info(f"[ValidadorComprobantes] Texto extraído de PDF: {len(texto)} caracteres")
            return texto
        except Exception as e:
            logger.error(f"[ValidadorComprobantes] Error extrayendo texto de PDF: {str(e)}")
            return ""
    
    def extraer_texto_imagen(self, ruta_archivo: str) -> str:
        """Extrae texto de una imagen usando OCR"""
        if not PYTESSERACT_AVAILABLE:
            logger.warning("[ValidadorComprobantes] pytesseract no disponible, no se puede hacer OCR")
            return ""
        
        try:
            image = Image.open(ruta_archivo)
            texto = pytesseract.image_to_string(image, lang='spa')
            
            logger.info(f"[ValidadorComprobantes] Texto extraído de imagen: {len(texto)} caracteres")
            return texto
        except Exception as e:
            logger.error(f"[ValidadorComprobantes] Error haciendo OCR: {str(e)}")
            return ""
    
    def extraer_texto_comprobante(self, ruta_archivo: str, mime_type: str) -> str:
        """Extrae texto del comprobante según su tipo"""
        ruta_archivo = str(ruta_archivo)
        
        if not os.path.exists(ruta_archivo):
            logger.error(f"[ValidadorComprobantes] Archivo no existe: {ruta_archivo}")
            return ""
        
        # PDF
        if mime_type == 'application/pdf' or ruta_archivo.lower().endswith('.pdf'):
            return self.extraer_texto_pdf(ruta_archivo)
        
        # Imágenes
        if mime_type in ['image/jpeg', 'image/jpg', 'image/png'] or \
           ruta_archivo.lower().endswith(('.jpg', '.jpeg', '.png')):
            return self.extraer_texto_imagen(ruta_archivo)
        
        logger.warning(f"[ValidadorComprobantes] Tipo de archivo no soportado: {mime_type}")
        return ""
    
    def normalizar_texto(self, texto: str) -> str:
        """Normaliza texto para comparación (quita espacios extra, convierte a mayúsculas)"""
        # Convertir a mayúsculas
        texto = texto.upper()
        # Quitar múltiples espacios
        texto = re.sub(r'\s+', ' ', texto)
        # Quitar puntuación extra
        texto = texto.replace('.', '').replace(',', '').replace('-', '').replace('/', '')
        return texto.strip()
    
    def buscar_clabe_en_texto(self, texto: str, clabe_objetivo: str) -> bool:
        """Busca la CLABE objetivo en el texto del comprobante"""
        if not clabe_objetivo or len(clabe_objetivo) != 18:
            return False
        
        # Normalizar
        texto_normalizado = self.normalizar_texto(texto)
        clabe_normalizado = self.normalizar_texto(clabe_objetivo)
        
        # Buscar CLABE completa
        if clabe_normalizado in texto_normalizado:
            logger.info(f"[ValidadorComprobantes] ✅ CLABE {clabe_objetivo} encontrada en comprobante")
            return True
        
        # Buscar CLABE con espacios entre bloques (ej: 6461 8013 9409 4814 62)
        clabe_con_espacios = ' '.join([clabe_objetivo[i:i+4] for i in range(0, len(clabe_objetivo), 4)])
        if clabe_con_espacios in texto:
            logger.info(f"[ValidadorComprobantes] ✅ CLABE {clabe_objetivo} encontrada (con espacios)")
            return True
        
        # Buscar por partes (al menos los últimos 10 dígitos)
        ultimos_digitos = clabe_objetivo[-10:]
        if ultimos_digitos in texto_normalizado:
            logger.info(f"[ValidadorComprobantes] ✅ Últimos 10 dígitos de CLABE encontrados")
            return True
        
        logger.warning(f"[ValidadorComprobantes] ❌ CLABE {clabe_objetivo} NO encontrada en comprobante")
        return False
    
    def buscar_beneficiario_en_texto(self, texto: str, beneficiario_objetivo: str) -> bool:
        """Busca el beneficiario objetivo en el texto del comprobante"""
        if not beneficiario_objetivo:
            return False
        
        # Normalizar
        texto_normalizado = self.normalizar_texto(texto)
        beneficiario_normalizado = self.normalizar_texto(beneficiario_objetivo)
        
        # Buscar beneficiario completo
        if beneficiario_normalizado in texto_normalizado:
            logger.info(f"[ValidadorComprobantes] ✅ Beneficiario '{beneficiario_objetivo}' encontrado")
            return True
        
        # Buscar por palabras clave del beneficiario (al menos 70% de las palabras)
        palabras_beneficiario = beneficiario_normalizado.split()
        if len(palabras_beneficiario) < 2:
            return False
        
        palabras_encontradas = sum(1 for palabra in palabras_beneficiario if palabra in texto_normalizado)
        porcentaje = palabras_encontradas / len(palabras_beneficiario)
        
        if porcentaje >= 0.7:
            logger.info(f"[ValidadorComprobantes] ✅ {int(porcentaje*100)}% del beneficiario encontrado")
            return True
        
        logger.warning(f"[ValidadorComprobantes] ❌ Beneficiario '{beneficiario_objetivo}' NO encontrado")
        return False
    
    def validar_comprobante(self, 
                           ruta_archivo: str, 
                           mime_type: str,
                           cuenta_activa: Dict) -> Tuple[bool, str]:
        """
        Valida un comprobante contra la cuenta activa
        
        Args:
            ruta_archivo: Ruta al archivo del comprobante
            mime_type: Tipo MIME del archivo
            cuenta_activa: Dict con banco, clabe, beneficiario
        
        Returns:
            Tuple (es_valido: bool, razon: str)
        """
        if not cuenta_activa:
            return False, "No hay cuenta activa configurada"
        
        clabe_activa = cuenta_activa.get('clabe')
        beneficiario_activo = cuenta_activa.get('beneficiario')
        
        if not clabe_activa or not beneficiario_activo:
            return False, "Cuenta activa incompleta"
        
        # Extraer texto del comprobante
        texto_comprobante = self.extraer_texto_comprobante(ruta_archivo, mime_type)
        
        if not texto_comprobante or len(texto_comprobante) < 20:
            logger.warning(f"[ValidadorComprobantes] No se pudo extraer texto suficiente del comprobante")
            # Si no se puede extraer texto, lo consideramos inválido por precaución
            return False, "No se pudo leer el comprobante o está vacío"
        
        # Validar CLABE
        clabe_encontrada = self.buscar_clabe_en_texto(texto_comprobante, clabe_activa)
        
        # Validar beneficiario
        beneficiario_encontrado = self.buscar_beneficiario_en_texto(texto_comprobante, beneficiario_activo)
        
        # Resultado
        if clabe_encontrada and beneficiario_encontrado:
            return True, "Comprobante válido: CLABE y beneficiario coinciden"
        elif clabe_encontrada and not beneficiario_encontrado:
            return False, f"El comprobante tiene la CLABE correcta pero el beneficiario no coincide con {beneficiario_activo}"
        elif not clabe_encontrada and beneficiario_encontrado:
            return False, f"El comprobante tiene el beneficiario correcto pero la CLABE no coincide con {clabe_activa}"
        else:
            return False, f"El comprobante no corresponde a la cuenta NetCash activa (Banco: {cuenta_activa.get('banco')}, CLABE: {clabe_activa}, Beneficiario: {beneficiario_activo})"
    
    def validar_todos_comprobantes(self, 
                                   archivos_adjuntos: list,
                                   cuenta_activa: Dict) -> Tuple[bool, list]:
        """
        Valida todos los comprobantes adjuntos
        
        Args:
            archivos_adjuntos: Lista de dicts con ruta, mime_type
            cuenta_activa: Dict con datos de la cuenta activa
        
        Returns:
            Tuple (todos_validos: bool, lista_validaciones: list)
        """
        if not archivos_adjuntos or len(archivos_adjuntos) == 0:
            return False, ["No hay comprobantes adjuntos"]
        
        validaciones = []
        al_menos_uno_valido = False
        
        for idx, archivo in enumerate(archivos_adjuntos):
            ruta = archivo.get('ruta')
            mime_type = archivo.get('mime_type')
            nombre = archivo.get('nombre_original', 'comprobante')
            
            es_valido, razon = self.validar_comprobante(ruta, mime_type, cuenta_activa)
            
            validaciones.append({
                'nombre': nombre,
                'valido': es_valido,
                'razon': razon
            })
            
            if es_valido:
                al_menos_uno_valido = True
        
        return al_menos_uno_valido, validaciones


# Instancia global
validador_comprobantes = ValidadorComprobantes()
