"""Manejador de archivos ZIP para comprobantes"""
import zipfile
import logging
from pathlib import Path
from typing import List, Dict, Any
import mimetypes

logger = logging.getLogger(__name__)

FORMATOS_ACEPTADOS = {
    '.pdf': 'application/pdf',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png'
}


class ZipHandler:
    """Maneja extracción y procesamiento de archivos ZIP"""
    
    @staticmethod
    def es_archivo_valido(filename: str) -> bool:
        """Verifica si el archivo tiene un formato aceptado"""
        ext = Path(filename).suffix.lower()
        return ext in FORMATOS_ACEPTADOS
    
    @staticmethod
    def obtener_mime_type(filename: str) -> str:
        """Obtiene el mime type de un archivo por su extensión"""
        ext = Path(filename).suffix.lower()
        return FORMATOS_ACEPTADOS.get(ext, 'application/octet-stream')
    
    @staticmethod
    def extraer_comprobantes_de_zip(zip_path: Path, destino_dir: Path) -> Dict[str, Any]:
        """
        Extrae archivos de un ZIP y los clasifica.
        
        Returns:
            Dict con:
            - archivos_validos: List[Dict] con path y mime_type de cada archivo válido
            - archivos_ignorados: List[str] nombres de archivos ignorados
            - errores: List[str] errores encontrados
        """
        resultado = {
            "archivos_validos": [],
            "archivos_ignorados": [],
            "errores": []
        }
        
        try:
            # Verificar que es un ZIP válido
            if not zipfile.is_zipfile(zip_path):
                resultado["errores"].append("El archivo no es un ZIP válido")
                return resultado
            
            # Crear directorio destino
            destino_dir.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Listar archivos en el ZIP
                archivos_en_zip = zip_ref.namelist()
                logger.info(f"ZIP contiene {len(archivos_en_zip)} archivos")
                
                for archivo_nombre in archivos_en_zip:
                    # Ignorar directorios y archivos ocultos
                    if archivo_nombre.endswith('/') or archivo_nombre.startswith('__MACOSX') or '._' in archivo_nombre:
                        continue
                    
                    # Verificar si es un formato aceptado
                    if ZipHandler.es_archivo_valido(archivo_nombre):
                        try:
                            # Extraer archivo
                            archivo_path = destino_dir / Path(archivo_nombre).name
                            with zip_ref.open(archivo_nombre) as source, open(archivo_path, 'wb') as target:
                                target.write(source.read())
                            
                            # Agregar a lista de válidos
                            resultado["archivos_validos"].append({
                                "path": str(archivo_path),
                                "nombre": Path(archivo_nombre).name,
                                "mime_type": ZipHandler.obtener_mime_type(archivo_nombre)
                            })
                            
                            logger.info(f"Archivo extraído: {Path(archivo_nombre).name}")
                        
                        except Exception as e:
                            logger.error(f"Error extrayendo {archivo_nombre}: {str(e)}")
                            resultado["errores"].append(f"Error procesando {archivo_nombre}")
                    else:
                        # Archivo ignorado (no es PDF/JPG/PNG)
                        resultado["archivos_ignorados"].append(Path(archivo_nombre).name)
                        logger.info(f"Archivo ignorado (formato no soportado): {archivo_nombre}")
        
        except Exception as e:
            logger.error(f"Error procesando ZIP: {str(e)}")
            resultado["errores"].append(f"Error al abrir el ZIP: {str(e)}")
        
        return resultado


# Instancia global
zip_handler = ZipHandler()
