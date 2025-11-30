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
    
    def extraer_clabes_del_texto(self, texto: str) -> list:
        """Extrae todas las CLABEs (18 dígitos) encontradas en el texto"""
        # Buscar secuencias de exactamente 18 dígitos
        clabes_encontradas = []
        
        # Patrón 1: 18 dígitos juntos
        matches = re.findall(r'\b(\d{18})\b', texto)
        clabes_encontradas.extend(matches)
        
        # Patrón 2: 18 dígitos con espacios cada 4 (ej: 1234 5678 9012 3456 78)
        texto_sin_espacios = texto.replace(' ', '').replace('\n', '')
        matches2 = re.findall(r'\b(\d{18})\b', texto_sin_espacios)
        clabes_encontradas.extend(matches2)
        
        return list(set(clabes_encontradas))  # Eliminar duplicados
    
    def buscar_clabe_en_texto(self, texto: str, clabe_objetivo: str) -> Tuple[bool, str]:
        """
        Busca la CLABE objetivo en el texto del comprobante
        
        Returns:
            Tuple (encontrada: bool, metodo: str)
            metodo puede ser: "completa", "sufijo_3", "no_encontrada"
        """
        if not clabe_objetivo or len(clabe_objetivo) != 18:
            logger.warning(f"[ValidadorComprobantes] CLABE objetivo inválida: {clabe_objetivo}")
            return False, "no_encontrada"
        
        logger.info(f"[ValidadorComprobantes] Buscando CLABE objetivo: {clabe_objetivo}")
        
        # Extraer todas las CLABEs completas (18 dígitos) del texto
        clabes_en_texto = self.extraer_clabes_del_texto(texto)
        
        # PASO 1: Filtrar CLABEs enmascaradas (con asteriscos) y CLABEs asociadas (origen)
        clabes_validas = []
        for clabe in clabes_en_texto:
            # Buscar contexto alrededor de esta CLABE en el texto original
            contexto_inicio = max(0, texto.find(clabe) - 50)
            contexto_fin = min(len(texto), texto.find(clabe) + 50)
            contexto = texto[contexto_inicio:contexto_fin].upper()
            
            # Ignorar si tiene "CLABE ASOCIADA" cerca (es cuenta de origen, no destino)
            if "CLABE ASOCIADA" in contexto or "ASOCIADA" in contexto:
                logger.info(f"[ValidadorComprobantes] Ignorando CLABE {clabe} (es CLABE asociada - cuenta de origen)")
                continue
            
            # Ignorar si tiene asteriscos cerca (CLABE enmascarada)
            if "*" in contexto:
                logger.info(f"[ValidadorComprobantes] Ignorando CLABE {clabe} (tiene asteriscos - enmascarada)")
                continue
            
            clabes_validas.append(clabe)
        
        if clabes_validas:
            logger.info(f"[ValidadorComprobantes] CLABEs válidas encontradas (sin enmascarar ni asociadas): {clabes_validas}")
        else:
            logger.warning(f"[ValidadorComprobantes] No se encontró ninguna CLABE completa válida (18 dígitos) en el comprobante")
        
        # PASO 2: Verificar si alguna CLABE válida coincide EXACTAMENTE con la objetivo
        for clabe_encontrada in clabes_validas:
            if clabe_encontrada == clabe_objetivo:
                logger.info(f"[ValidadorComprobantes] ✅ CLABE objetivo ENCONTRADA (completa): {clabe_encontrada}")
                return True, "completa"
            else:
                logger.info(f"[ValidadorComprobantes] CLABE válida {clabe_encontrada} NO coincide con objetivo {clabe_objetivo}")
        
        # PASO 3: NUEVO - Validación por sufijo para formatos Banamex
        # Si NO se encontró CLABE completa, buscar patrón "CLABE-XXX" o "CLABE XXX"
        # donde XXX son los últimos 3 dígitos de la CLABE objetivo
        ultimos_3_objetivo = clabe_objetivo[-3:]
        
        # Patrones que indican cuenta de depósito con sufijo
        patrones_deposito = [
            f"CLABE-{ultimos_3_objetivo}",
            f"CLABE {ultimos_3_objetivo}",
            f"CLABE: {ultimos_3_objetivo}",
        ]
        
        texto_upper = texto.upper()
        for patron in patrones_deposito:
            if patron in texto_upper:
                logger.info(f"[ValidadorComprobantes] ⚠️ Encontrado patrón '{patron}' (sufijo de CLABE objetivo)")
                
                # VALIDACIÓN EXTRA: Verificar que NO haya otra CLABE válida que contradiga
                # (si hay CLABEs completas válidas y ninguna coincide, el sufijo no cuenta)
                if len(clabes_validas) > 0:
                    # Hay CLABEs completas pero ninguna coincidió
                    logger.warning(f"[ValidadorComprobantes] Se encontró sufijo {ultimos_3_objetivo}, pero hay CLABEs completas que NO coinciden: {clabes_validas}")
                    return False, "no_encontrada"
                
                # Buscar contexto para confirmar que es cuenta de DEPÓSITO (destino)
                idx = texto_upper.find(patron)
                contexto_inicio = max(0, idx - 100)
                contexto_fin = min(len(texto), idx + 200)
                contexto_deposito = texto[contexto_inicio:contexto_fin].upper()
                
                # Confirmar que está relacionado con "CUENTA DE DEPÓSITO" o "DESTINO"
                if "CUENTA DE DEPOSITO" in contexto_deposito or "DEPOSITO" in contexto_deposito or "DESTINO" in contexto_deposito:
                    logger.info(f"[ValidadorComprobantes] ✅ Validación por SUFIJO exitosa: sufijo {ultimos_3_objetivo} encontrado en contexto de cuenta de depósito")
                    return True, "sufijo_3"
                else:
                    logger.warning(f"[ValidadorComprobantes] Patrón {patron} encontrado pero NO en contexto de cuenta de depósito")
        
        logger.warning(f"[ValidadorComprobantes] ❌ CLABE objetivo {clabe_objetivo} NO encontrada (ni completa ni por sufijo)")
        return False, "no_encontrada"
    
    def buscar_beneficiario_en_texto(self, texto: str, beneficiario_objetivo: str) -> bool:
        """Busca el beneficiario objetivo en el texto (tolerante a separaciones)"""
        if not beneficiario_objetivo:
            return False
        
        # Normalizar
        texto_normalizado = self.normalizar_texto(texto)
        beneficiario_normalizado = self.normalizar_texto(beneficiario_objetivo)
        
        # Buscar beneficiario completo
        if beneficiario_normalizado in texto_normalizado:
            logger.info(f"[ValidadorComprobantes] ✅ Beneficiario completo encontrado")
            return True
        
        # Para "JARDINERIA Y COMERCIO THABYETHA SA DE CV"
        # Buscar partes clave que suelen aparecer separadas
        partes_clave = []
        
        # Extraer palabras significativas (ignorar conectores)
        palabras = beneficiario_normalizado.split()
        for palabra in palabras:
            if palabra not in ['Y', 'DE', 'SA', 'CV', 'LA', 'EL', 'LOS', 'LAS']:
                if len(palabra) >= 4:  # Solo palabras significativas
                    partes_clave.append(palabra)
        
        # Contar cuántas partes clave aparecen
        encontradas = sum(1 for parte in partes_clave if parte in texto_normalizado)
        
        if len(partes_clave) > 0:
            porcentaje = encontradas / len(partes_clave)
            
            if porcentaje >= 0.7:
                logger.info(f"[ValidadorComprobantes] ✅ {int(porcentaje*100)}% de partes clave encontradas: {encontradas}/{len(partes_clave)}")
                return True
        
        # Fallback: buscar al menos 70% de TODAS las palabras
        todas_palabras = beneficiario_normalizado.split()
        if len(todas_palabras) >= 2:
            palabras_encontradas = sum(1 for palabra in todas_palabras if palabra in texto_normalizado)
            porcentaje_total = palabras_encontradas / len(todas_palabras)
            
            if porcentaje_total >= 0.7:
                logger.info(f"[ValidadorComprobantes] ✅ {int(porcentaje_total*100)}% del beneficiario encontrado")
                return True
        
        logger.warning(f"[ValidadorComprobantes] ❌ Beneficiario NO encontrado suficientemente")
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
        logger.info(f"[ValidadorComprobantes] ========== INICIO VALIDACIÓN ==========")
        logger.info(f"[ValidadorComprobantes] Archivo: {ruta_archivo}")
        
        if not cuenta_activa:
            logger.error(f"[ValidadorComprobantes] ❌ No hay cuenta activa configurada")
            return False, "No hay cuenta activa configurada"
        
        clabe_activa = cuenta_activa.get('clabe')
        beneficiario_activo = cuenta_activa.get('beneficiario')
        banco_activo = cuenta_activa.get('banco')
        
        logger.info(f"[ValidadorComprobantes] Cuenta ACTIVA esperada:")
        logger.info(f"[ValidadorComprobantes]   - Banco: {banco_activo}")
        logger.info(f"[ValidadorComprobantes]   - CLABE: {clabe_activa}")
        logger.info(f"[ValidadorComprobantes]   - Beneficiario: {beneficiario_activo}")
        
        if not clabe_activa or not beneficiario_activo:
            logger.error(f"[ValidadorComprobantes] ❌ Cuenta activa incompleta")
            return False, "Cuenta activa incompleta"
        
        # Extraer texto del comprobante
        texto_comprobante = self.extraer_texto_comprobante(ruta_archivo, mime_type)
        
        if not texto_comprobante or len(texto_comprobante) < 20:
            logger.warning(f"[ValidadorComprobantes] ❌ No se pudo extraer texto suficiente del comprobante (len={len(texto_comprobante) if texto_comprobante else 0})")
            return False, "No se pudo leer el comprobante o está vacío"
        
        logger.info(f"[ValidadorComprobantes] Texto extraído del comprobante ({len(texto_comprobante)} caracteres)")
        logger.info(f"[ValidadorComprobantes] Primeros 500 caracteres: {texto_comprobante[:500]}")
        
        # Validar CLABE
        clabe_encontrada, metodo_clabe = self.buscar_clabe_en_texto(texto_comprobante, clabe_activa)
        logger.info(f"[ValidadorComprobantes] CLABE activa ({clabe_activa}) encontrada en comprobante: {clabe_encontrada} (método: {metodo_clabe})")
        
        # Validar beneficiario
        beneficiario_encontrado = self.buscar_beneficiario_en_texto(texto_comprobante, beneficiario_activo)
        logger.info(f"[ValidadorComprobantes] Beneficiario activo ({beneficiario_activo}) encontrado en comprobante: {beneficiario_encontrado}")
        
        # Resultado
        if clabe_encontrada and beneficiario_encontrado:
            if metodo_clabe == "completa":
                logger.info(f"[ValidadorComprobantes] ✅ VÁLIDO: CLABE completa y beneficiario coinciden con cuenta activa")
                return True, "Comprobante válido: CLABE y beneficiario coinciden"
            elif metodo_clabe == "sufijo_3":
                logger.info(f"[ValidadorComprobantes] ✅ VÁLIDO: Beneficiario coincide y CLABE termina en {clabe_activa[-3:]} (formato Banamex sin CLABE completa)")
                return True, f"Comprobante válido: beneficiario coincide y la CLABE termina en {clabe_activa[-3:]} (formato Banamex)"
            else:
                logger.info(f"[ValidadorComprobantes] ✅ VÁLIDO: CLABE y beneficiario coinciden")
                return True, "Comprobante válido"
        elif clabe_encontrada and not beneficiario_encontrado:
            logger.warning(f"[ValidadorComprobantes] ❌ INVÁLIDO: CLABE correcta pero beneficiario NO coincide")
            return False, f"El comprobante tiene la CLABE correcta pero el beneficiario no coincide con {beneficiario_activo}"
        elif not clabe_encontrada and beneficiario_encontrado:
            logger.warning(f"[ValidadorComprobantes] ❌ INVÁLIDO: Beneficiario correcto pero CLABE NO coincide")
            return False, f"El comprobante tiene el beneficiario correcto pero la CLABE no coincide con {clabe_activa}"
        else:
            logger.warning(f"[ValidadorComprobantes] ❌ INVÁLIDO: Ni CLABE ni beneficiario coinciden con cuenta activa")
            return False, f"El comprobante no corresponde a la cuenta NetCash activa (Banco: {banco_activo}, CLABE: {clabe_activa}, Beneficiario: {beneficiario_activo})"
    
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
