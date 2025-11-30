"""Servicio para validar comprobantes contra la cuenta activa de NetCash"""

import os
import re
import logging
from typing import Dict, Optional, Tuple
from pathlib import Path

# VERSION DEL VALIDADOR - Para tracking de desincronizaciones
VALIDADOR_THABYETHA_VERSION = "V3.5-fuzzy-beneficiario"

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
        """
        Extrae todas las CLABEs (18 dígitos) encontradas en el texto
        
        Soporta:
        - 18 dígitos juntos: 646180139409481462
        - 18 dígitos separados por espacios o saltos de línea
        """
        clabes_encontradas = []
        
        # Patrón 1: 18 dígitos con límites de palabra en el texto original
        matches1 = re.findall(r'\b(\d{18})\b', texto)
        clabes_encontradas.extend(matches1)
        
        # Patrón 2: 18 dígitos en texto normalizado (sin espacios ni saltos de línea)
        # Esto maneja casos donde la CLABE aparece separada por saltos de línea
        texto_normalizado = re.sub(r'[\s\n\r]+', '', texto)  # Quitar TODOS los espacios en blanco
        matches2 = re.findall(r'(\d{18})', texto_normalizado)
        clabes_encontradas.extend(matches2)
        
        # Patrón 3: 18 dígitos con espacios/saltos cada N caracteres
        # Útil para formatos: "6461 8013 9409 4814 62" o con saltos de línea
        texto_limpio = re.sub(r'[\s\n\r]+', '', texto)
        # Buscar cualquier secuencia de exactamente 18 dígitos consecutivos
        matches3 = re.findall(r'(?<!\d)(\d{18})(?!\d)', texto_limpio)
        clabes_encontradas.extend(matches3)
        
        # Eliminar duplicados manteniendo orden
        clabes_unicas = list(dict.fromkeys(clabes_encontradas))
        
        return clabes_unicas
    
    def buscar_clabe_en_texto(self, texto: str, clabe_objetivo: str) -> Tuple[bool, str]:
        """
        Busca la CLABE/Cuenta objetivo en el texto del comprobante (V3.0 - Multi-layout)
        
        Lógica mejorada:
        a) Primero busca CLABEs completas (18 dígitos) en contexto de destino
        b) Si no hay CLABE completa, busca sufijos enmascarados en múltiples formatos:
           - "CLABE-462", "****2915", "65**0938", etc.
           - En contextos: "Cuenta destino", "Cuenta abono", "Cuenta beneficiaria", "Cuenta destinatario"
        c) Ignora CLABEs de origen, rastreos, y referencias
        
        Returns:
            Tuple (encontrada: bool, metodo: str)
            metodo puede ser: "completa", "sufijo_enmascarado", "no_encontrada"
        """
        if not clabe_objetivo or len(clabe_objetivo) != 18:
            logger.warning(f"[ValidadorComprobantes] CLABE objetivo inválida: {clabe_objetivo}")
            return False, "no_encontrada"
        
        logger.info(f"[ValidadorComprobantes] Buscando CLABE objetivo: {clabe_objetivo}")
        
        # LOG ESPECIAL PARA THABYETHA (debugging)
        es_thabyetha = (clabe_objetivo == "646180139409481462")
        if es_thabyetha:
            logger.info(f"[THABYETHA_DEBUG] ========== INICIO DEBUG THABYETHA ==========")
            logger.info(f"[THABYETHA_DEBUG] Texto normalizado (primeros 600 chars): {texto[:600]}")
        
        # PASO A: Buscar CLABEs completas (18 dígitos) en contexto de DESTINO
        clabes_completas = self.extraer_clabes_del_texto(texto)
        logger.info(f"[ValidadorComprobantes] CLABEs de 18 dígitos encontradas: {clabes_completas}")
        
        if es_thabyetha:
            logger.info(f"[THABYETHA_DEBUG] CLABEs extraídas (18 dígitos): {clabes_completas}")
        
        # Filtrar solo las CLABEs que están en contexto de DESTINO/BENEFICIARIA
        clabes_destino = []
        texto_upper = texto.upper()
        
        for clabe in clabes_completas:
            # ESTRATEGIA MEJORADA: Buscar contexto por líneas, no por caracteres
            # Esto maneja mejor casos donde la CLABE está en una línea separada del keyword
            
            # Dividir texto en líneas
            lineas = texto.split('\n')
            linea_clabe = -1
            
            # Buscar en qué línea está la CLABE
            for i, linea in enumerate(lineas):
                if clabe in linea.replace(' ', '').replace('\r', ''):
                    linea_clabe = i
                    break
            
            if linea_clabe == -1:
                # No se encontró la CLABE
                continue
            
            # Obtener contexto: 5 líneas antes y 3 líneas después
            inicio_contexto = max(0, linea_clabe - 5)
            fin_contexto = min(len(lineas), linea_clabe + 4)
            lineas_contexto = lineas[inicio_contexto:fin_contexto]
            contexto = '\n'.join(lineas_contexto).upper()
            
            # MEJORADO: Detectar si es ORIGEN o DESTINO en layouts tabulares
            # En layouts tipo "ORIGEN | DESTINO", la CLABE puede estar en la columna derecha
            # Necesitamos verificar la posición RELATIVA de la CLABE respecto a las palabras clave
            
            linea_actual = lineas[linea_clabe].upper()
            lineas_antes = lineas[inicio_contexto:linea_clabe]
            texto_antes = '\n'.join(lineas_antes).upper()
            
            # Verificar si este es un layout tabular (tiene "ORIGEN" y "DESTINO" en la misma línea anterior)
            es_layout_tabular = False
            linea_encabezado = None
            for i in range(max(0, linea_clabe - 3), linea_clabe):
                linea = lineas[i].upper()
                if "ORIGEN" in linea and "DESTINO" in linea:
                    es_layout_tabular = True
                    linea_encabezado = linea
                    break
            
            if es_layout_tabular and linea_encabezado:
                # Layout tabular detectado: determinar columna por posición
                # Buscar índice de "ORIGEN" y "DESTINO" en el encabezado
                idx_origen = linea_encabezado.find("ORIGEN")
                idx_destino = linea_encabezado.find("DESTINO")
                
                # Buscar posición de la CLABE en su línea
                idx_clabe = linea_actual.find(clabe)
                
                if idx_clabe != -1:
                    # Si la CLABE está más cerca de DESTINO que de ORIGEN
                    if abs(idx_clabe - idx_destino) < abs(idx_clabe - idx_origen):
                        es_origen = False
                        logger.info(f"[ValidadorComprobantes] CLABE {clabe} en columna DESTINO (layout tabular)")
                    else:
                        es_origen = True
                        logger.info(f"[ValidadorComprobantes] CLABE {clabe} en columna ORIGEN (layout tabular)")
                else:
                    # Fallback: búsqueda tradicional
                    keywords_origen = ["ORIGEN", "ASOCIADA", "ORDENANTE", "CUENTA CARGO"]
                    es_origen = any(kw in texto_antes for kw in keywords_origen)
            else:
                # No es layout tabular, usar lógica tradicional
                keywords_origen = ["ORIGEN", "ASOCIADA", "ORDENANTE", "CUENTA CARGO"]
                es_origen = any(kw in texto_antes for kw in keywords_origen)
            
            # Ignorar si la CLABE MISMA es CLAVE DE RASTREO o REFERENCIA
            # No ignorar si estas palabras aparecen en otras líneas del contexto
            keywords_ignorar = ["RASTREO", "REFERENCIA", "AUTORIZACION", "FOLIO", "NUMERO DE"]
            
            # Buscar solo en la línea de la CLABE y la inmediatamente anterior
            linea_clabe_texto = lineas[linea_clabe] if linea_clabe < len(lineas) else ""
            linea_anterior = lineas[linea_clabe - 1] if linea_clabe > 0 else ""
            contexto_inmediato = (linea_anterior + "\n" + linea_clabe_texto).upper()
            
            es_rastreo = any(kw in contexto_inmediato for kw in keywords_ignorar)
            
            # Debe estar en contexto de DESTINO (buscar en todas las líneas del contexto)
            keywords_destino = [
                "DESTINO", "BENEFICIAR", "ABONO", "RECEPTOR", "DESTINATARIO",
                "CLABE RECEPTOR", "CUENTA RECEPTOR", "CLABE BENEFICIAR"
            ]
            es_destino = any(kw in contexto for kw in keywords_destino)
            
            if not es_origen and not es_rastreo and (es_destino or len(clabes_completas) == 1):
                clabes_destino.append(clabe)
                logger.info(f"[ValidadorComprobantes] ✓ CLABE {clabe} identificada como DESTINO")
            else:
                logger.info(f"[ValidadorComprobantes] ✗ CLABE {clabe} ignorada (origen={es_origen}, rastreo={es_rastreo}, destino={es_destino})")
                if es_thabyetha:
                    logger.info(f"[THABYETHA_DEBUG] Contexto de CLABE {clabe}: {contexto[:200]}")
        
        if es_thabyetha:
            logger.info(f"[THABYETHA_DEBUG] CLABEs válidas después de filtros (destino): {clabes_destino}")
        
        # Verificar si alguna CLABE de destino coincide
        for clabe_encontrada in clabes_destino:
            if clabe_encontrada == clabe_objetivo:
                logger.info(f"[ValidadorComprobantes] ✅✅✅ CLABE COMPLETA ENCONTRADA: {clabe_encontrada}")
                if es_thabyetha:
                    logger.info(f"[THABYETHA_DEBUG] Resultado final: clabe_encontrada=True metodo=completa")
                    logger.info(f"[THABYETHA_DEBUG] ========== FIN DEBUG THABYETHA ==========")
                return True, "completa"
        
        # Si hay CLABEs de destino pero no coinciden, comprobante inválido
        if len(clabes_destino) > 0:
            logger.warning(f"[ValidadorComprobantes] ❌ Hay CLABEs de destino pero NINGUNA coincide con {clabe_objetivo}")
            if es_thabyetha:
                logger.info(f"[THABYETHA_DEBUG] Resultado final: clabe_encontrada=False metodo=no_encontrada (hay CLABEs pero no coinciden)")
                logger.info(f"[THABYETHA_DEBUG] ========== FIN DEBUG THABYETHA ==========")
            return False, "no_encontrada"
        
        # PASO B: Buscar sufijos enmascarados en múltiples formatos
        logger.info(f"[ValidadorComprobantes] No hay CLABE completa de destino. Buscando sufijos enmascarados...")
        
        # Calcular sufijos de diferentes longitudes
        sufijo_4 = clabe_objetivo[-4:]  # Últimos 4 dígitos
        sufijo_3 = clabe_objetivo[-3:]  # Últimos 3 dígitos
        
        # Patrones de sufijo a buscar (en orden de prioridad)
        patrones_sufijo = [
            # Formato: "CLABE-462", "Clabe-2915", etc.
            f"CLABE-{sufijo_3}",
            f"CLABE-{sufijo_4}",
            f"CLABE {sufijo_3}",
            f"CLABE {sufijo_4}",
            # Formato: "****2915", "****462", etc. 
            f"****{sufijo_4}",
            f"****{sufijo_3}",
            # Formato: "65**0938" (dígitos al inicio y al final)
            f"{clabe_objetivo[:2]}**{sufijo_4}",
            f"{clabe_objetivo[:3]}**{sufijo_4}",
            # Formato: "...2915", "...462" (puntos suspensivos)
            f"...{sufijo_4}",
            f"...{sufijo_3}",
        ]
        
        for patron in patrones_sufijo:
            if patron.upper() not in texto_upper:
                continue
            
            logger.info(f"[ValidadorComprobantes] ⚠️ Encontrado patrón enmascarado: '{patron}'")
            
            # Buscar contexto alrededor del patrón
            idx = texto_upper.find(patron.upper())
            contexto_inicio = max(0, idx - 150)
            contexto_fin = min(len(texto), idx + len(patron) + 150)
            contexto = texto[contexto_inicio:contexto_fin].upper()
            
            import unicodedata
            contexto_norm = unicodedata.normalize('NFKD', contexto).encode('ASCII', 'ignore').decode('ASCII')
            
            # Verificar que NO sea línea de origen/ordenante
            lineas = contexto.split('\n')
            linea_patron = None
            for linea in lineas:
                if patron.upper() in linea.upper():
                    linea_patron = linea.upper()
                    break
            
            if linea_patron:
                # Ignorar si la línea contiene palabras de origen
                keywords_origen = ["ORIGEN", "ORDENANTE", "ASOCIADA", "CARGO"]
                if any(kw in linea_patron for kw in keywords_origen):
                    logger.warning(f"[ValidadorComprobantes] ❌ Patrón {patron} está en línea de ORIGEN")
                    continue
            
            # Verificar que esté en contexto de DESTINO
            keywords_destino = [
                "DESTINO", "BENEFICIAR", "ABONO", "RECEPTOR", "DESTINATARIO",
                "CUENTA DESTINO", "CUENTA ABONO", "CUENTA BENEFICIAR",
                "CLABE DESTINO", "PARA", "DEPOSITO"
            ]
            
            es_contexto_destino = any(kw in contexto_norm for kw in keywords_destino)
            
            if not es_contexto_destino:
                logger.warning(f"[ValidadorComprobantes] ❌ Patrón {patron} NO está en contexto de destino")
                continue
            
            logger.info(f"[ValidadorComprobantes] ✅ Patrón {patron} encontrado en contexto de DESTINO")
            logger.info(f"[ValidadorComprobantes] ✅✅✅ SUFIJO ENMASCARADO VÁLIDO encontrado")
            return True, "sufijo_enmascarado"
        
        logger.warning(f"[ValidadorComprobantes] ❌ CLABE objetivo NO encontrada")
        if es_thabyetha:
            logger.info(f"[THABYETHA_DEBUG] Resultado final: clabe_encontrada=False metodo=no_encontrada (no se encontró ni CLABE completa ni sufijo)")
            logger.info(f"[THABYETHA_DEBUG] ========== FIN DEBUG THABYETHA ==========")
        return False, "no_encontrada"
    
    def buscar_beneficiario_en_texto(self, texto: str, beneficiario_objetivo: str, 
                                     clabe_completa_encontrada: bool = False) -> bool:
        """
        Busca el beneficiario objetivo en el texto (V3.5 - Con fuzzy matching)
        
        Tolerante a:
        - Separaciones por líneas/saltos
        - Variaciones de "SA DE CV", "S.A. DE C.V.", etc.
        - Abreviaciones en apps móviles
        - Mayúsculas/minúsculas
        - Acentos
        - **NUEVO V3.5**: Errores pequeños de OCR (solo si CLABE completa de 18 dígitos fue detectada exacta)
        
        Args:
            texto: Texto OCR del comprobante
            beneficiario_objetivo: Nombre del beneficiario esperado
            clabe_completa_encontrada: True si se detectó CLABE de 18 dígitos exacta previamente
        """
        if not beneficiario_objetivo:
            return False
        
        import unicodedata
        
        # Normalizar texto (quitar acentos, mayúsculas, espacios extra)
        def normalizar_avanzado(texto):
            # Quitar acentos
            texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
            # Mayúsculas
            texto = texto.upper()
            # Quitar puntuación
            texto = texto.replace('.', ' ').replace(',', ' ').replace('-', ' ').replace('/', ' ')
            # Normalizar "SA DE CV" y variaciones
            texto = texto.replace('S A DE C V', 'SA DE CV')
            texto = texto.replace('SADE CV', 'SA DE CV')
            texto = texto.replace('SA DECV', 'SA DE CV')
            texto = texto.replace('SADECV', 'SA DE CV')
            texto = texto.replace('S DE RL DE CV', 'SA DE CV')  # Incluir S DE RL
            # Quitar espacios múltiples
            texto = re.sub(r'\s+', ' ', texto)
            return texto.strip()
        
        texto_norm = normalizar_avanzado(texto)
        beneficiario_norm = normalizar_avanzado(beneficiario_objetivo)
        
        logger.info(f"[ValidadorComprobantes] Buscando beneficiario normalizado: {beneficiario_norm}")
        
        # Intento 1: Match completo
        if beneficiario_norm in texto_norm:
            logger.info(f"[ValidadorComprobantes] ✅ Beneficiario completo encontrado (match exacto)")
            return True
        
        # Intento 2: Buscar sin "SA DE CV" al final (muchas veces se omite en apps móviles)
        beneficiario_sin_sadecv = beneficiario_norm.replace('SA DE CV', '').replace('S DE RL', '').strip()
        if len(beneficiario_sin_sadecv) >= 10 and beneficiario_sin_sadecv in texto_norm:
            logger.info(f"[ValidadorComprobantes] ✅ Beneficiario encontrado sin SA DE CV")
            return True
        
        # Intento 3: Extraer palabras clave (≥4 caracteres, no conectores)
        conectores = {'Y', 'DE', 'SA', 'CV', 'LA', 'EL', 'LOS', 'LAS', 'DEL', 'CON', 'POR', 'PARA'}
        
        palabras_benef = [p for p in beneficiario_norm.split() if len(p) >= 4 and p not in conectores]
        
        if len(palabras_benef) == 0:
            # Si no hay palabras clave suficientes, usar todas
            palabras_benef = [p for p in beneficiario_norm.split() if len(p) >= 3]
        
        logger.info(f"[ValidadorComprobantes] Palabras clave a buscar: {palabras_benef}")
        
        palabras_encontradas = [p for p in palabras_benef if p in texto_norm]
        
        if len(palabras_benef) > 0:
            porcentaje = len(palabras_encontradas) / len(palabras_benef)
            
            logger.info(f"[ValidadorComprobantes] Palabras encontradas: {palabras_encontradas} ({int(porcentaje*100)}%)")
            
            # Criterio: al menos 70% de palabras clave encontradas
            if porcentaje >= 0.7:
                logger.info(f"[ValidadorComprobantes] ✅ Beneficiario encontrado (70%+ de palabras clave)")
                return True
        
        # Intento 4: Buscar contexto de beneficiario/destinatario cerca de palabras clave
        # Esto maneja casos donde el beneficiario aparece en una línea tipo:
        # "Beneficiario: JARDINERIA Y COMERCIO..."
        # "Destinatario: UNION AGROINDUSTRIAL..."
        keywords_contexto = ["BENEFICIAR", "DESTINATARIO", "TITULAR", "PARA", "NOMBRE"]
        
        for keyword in keywords_contexto:
            if keyword in texto_norm:
                # Buscar posición del keyword
                idx = texto_norm.find(keyword)
                # Extraer 200 caracteres después del keyword
                fragmento = texto_norm[idx:idx+250]
                
                # Contar cuántas palabras clave del beneficiario aparecen en este fragmento
                palabras_en_fragmento = [p for p in palabras_benef if p in fragmento]
                
                if len(palabras_benef) > 0:
                    porcentaje_frag = len(palabras_en_fragmento) / len(palabras_benef)
                    
                    if porcentaje_frag >= 0.7:
                        logger.info(f"[ValidadorComprobantes] ✅ Beneficiario encontrado cerca de '{keyword}' ({int(porcentaje_frag*100)}%)")
                        return True
        
        # V3.5: FUZZY MATCHING (solo si CLABE completa de 18 dígitos fue encontrada exacta)
        if clabe_completa_encontrada:
            logger.info(f"[VALIDADOR_FUZZY_BENEFICIARIO] CLABE completa detectada. Aplicando fuzzy matching...")
            
            from difflib import SequenceMatcher
            
            # Extraer todas las posibles subcadenas del texto que tengan longitud similar al beneficiario
            # Esto permite encontrar el nombre incluso con errores de OCR
            longitud_benef = len(beneficiario_norm)
            min_len = max(10, int(longitud_benef * 0.7))  # Mínimo 70% de longitud
            max_len = int(longitud_benef * 1.3)  # Máximo 130% de longitud
            
            # Dividir texto en líneas y buscar líneas que puedan contener el beneficiario
            lineas = texto_norm.split('\n')
            mejores_candidatos = []
            
            for linea in lineas:
                linea = linea.strip()
                if len(linea) < min_len or len(linea) > max_len * 2:
                    continue
                
                # Considerar la línea completa y sus subcadenas
                candidatos_linea = [linea]
                
                # También considerar palabras consecutivas dentro de la línea
                palabras = linea.split()
                for i in range(len(palabras)):
                    for j in range(i+1, min(i+10, len(palabras)+1)):
                        subcadena = ' '.join(palabras[i:j])
                        if min_len <= len(subcadena) <= max_len:
                            candidatos_linea.append(subcadena)
                
                mejores_candidatos.extend(candidatos_linea)
            
            # Calcular similitud con cada candidato
            mejor_score = 0.0
            mejor_candidato = None
            
            for candidato in mejores_candidatos:
                # Usar SequenceMatcher para calcular ratio de similitud
                ratio = SequenceMatcher(None, beneficiario_norm, candidato).ratio()
                
                if ratio > mejor_score:
                    mejor_score = ratio
                    mejor_candidato = candidato
            
            # Umbral de similitud: 0.85 (85%)
            UMBRAL_FUZZY = 0.85
            
            logger.info(f"[VALIDADOR_FUZZY_BENEFICIARIO] Mejor candidato: '{mejor_candidato}'")
            logger.info(f"[VALIDADOR_FUZZY_BENEFICIARIO] Score de similitud: {mejor_score:.3f} (umbral: {UMBRAL_FUZZY})")
            logger.info(f"[VALIDADOR_FUZZY_BENEFICIARIO] Beneficiario objetivo: '{beneficiario_norm}'")
            
            if mejor_score >= UMBRAL_FUZZY:
                logger.info(f"[VALIDADOR_FUZZY_BENEFICIARIO] ✅ MATCH FUZZY exitoso! nombre_ocr='{mejor_candidato}' nombre_objetivo='{beneficiario_norm}' score={mejor_score:.3f}")
                return True
            else:
                logger.warning(f"[VALIDADOR_FUZZY_BENEFICIARIO] ❌ Score insuficiente ({mejor_score:.3f} < {UMBRAL_FUZZY})")
        else:
            logger.info(f"[ValidadorComprobantes] No se aplicó fuzzy matching (CLABE completa no encontrada)")
        
        logger.warning(f"[ValidadorComprobantes] ❌ Beneficiario NO encontrado suficientemente en el texto")
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
        # LOG DE VERSION - Para tracking
        import os
        nombre_archivo = os.path.basename(ruta_archivo)
        logger.info(f"[VALIDADOR_NETCASH] Version={VALIDADOR_THABYETHA_VERSION} archivo={nombre_archivo}")
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
        
        # LOGS DETALLADOS SOLO PARA THABYETHA (tracking de bug)
        if beneficiario_activo == "JARDINERIA Y COMERCIO THABYETHA SA DE CV":
            logger.info(f"[VALIDADOR_THABYETHA] ========== CASO ESPECIAL THABYETHA ==========")
            logger.info(f"[VALIDADOR_THABYETHA] Texto OCR (primeros 800 chars): {texto_comprobante[:800]}")
            logger.info(f"[VALIDADOR_THABYETHA] CLABE objetivo: {clabe_activa}")
            logger.info(f"[VALIDADOR_THABYETHA] Sufijo esperado: {clabe_activa[-3:]}")
        
        # Validar CLABE
        clabe_encontrada, metodo_clabe = self.buscar_clabe_en_texto(texto_comprobante, clabe_activa)
        logger.info(f"[ValidadorComprobantes] CLABE activa ({clabe_activa}) encontrada: {clabe_encontrada} (método: {metodo_clabe})")
        
        # Validar beneficiario (con fuzzy matching si CLABE completa fue encontrada)
        clabe_completa_encontrada = (clabe_encontrada and metodo_clabe == "completa")
        beneficiario_encontrado = self.buscar_beneficiario_en_texto(
            texto_comprobante, 
            beneficiario_activo,
            clabe_completa_encontrada=clabe_completa_encontrada
        )
        logger.info(f"[ValidadorComprobantes] Beneficiario activo ({beneficiario_activo}) encontrado: {beneficiario_encontrado}")
        
        # LOGS DETALLADOS SOLO PARA THABYETHA (resultados)
        if beneficiario_activo == "JARDINERIA Y COMERCIO THABYETHA SA DE CV":
            logger.info(f"[VALIDADOR_THABYETHA] Resultado buscar_clabe_en_texto: encontrado={clabe_encontrada} metodo={metodo_clabe}")
            logger.info(f"[VALIDADOR_THABYETHA] Beneficiario_coincide={beneficiario_encontrado}")
            logger.info(f"[VALIDADOR_THABYETHA] ================================================")
        
        # REGLA ESPECIAL: Si se usó sufijo enmascarado, DEBE tener beneficiario
        if metodo_clabe == "sufijo_enmascarado" and not beneficiario_encontrado:
            logger.warning(f"[ValidadorComprobantes] ❌ INVÁLIDO: Sufijo enmascarado encontrado pero beneficiario NO coincide")
            return False, f"El comprobante tiene un sufijo de cuenta que coincide pero el beneficiario no corresponde a {beneficiario_activo}"
        
        # Resultado final
        if clabe_encontrada and beneficiario_encontrado:
            if metodo_clabe == "completa":
                logger.info(f"[ValidadorComprobantes] ✅✅✅ VÁLIDO: CLABE completa de destino y beneficiario coinciden")
                return True, "CLABE completa encontrada y coincide con la cuenta NetCash autorizada"
            elif metodo_clabe == "sufijo_enmascarado":
                logger.info(f"[ValidadorComprobantes] ✅✅✅ VÁLIDO: Sufijo enmascarado y beneficiario coinciden")
                return True, f"Cuenta enmascarada (sufijo {clabe_activa[-4:]}) encontrada en contexto de destino y beneficiario coincide"
            else:
                logger.info(f"[ValidadorComprobantes] ✅ VÁLIDO: CLABE y beneficiario coinciden")
                return True, "Comprobante válido"
        elif clabe_encontrada and not beneficiario_encontrado:
            logger.warning(f"[ValidadorComprobantes] ❌ INVÁLIDO: CLABE correcta pero beneficiario NO coincide")
            return False, f"El comprobante tiene la CLABE/cuenta correcta pero el beneficiario no coincide con {beneficiario_activo}"
        elif not clabe_encontrada and beneficiario_encontrado:
            logger.warning(f"[ValidadorComprobantes] ❌ INVÁLIDO: Beneficiario correcto pero CLABE NO coincide")
            return False, f"El comprobante tiene el beneficiario correcto pero la CLABE/cuenta no coincide con {clabe_activa}"
        else:
            logger.warning(f"[ValidadorComprobantes] ❌ INVÁLIDO: Ni CLABE ni beneficiario coinciden")
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
