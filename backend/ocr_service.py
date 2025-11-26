import os
import base64
from typing import Dict, Any, Optional, List
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
import asyncio
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)


class OCRService:
    def __init__(self):
        self.api_key = os.getenv("EMERGENT_LLM_KEY")
        if not self.api_key:
            logger.warning("EMERGENT_LLM_KEY no está configurada")
    
    async def leer_comprobante(self, archivo_path: str, mime_type: str) -> Dict[str, Any]:
        """
        Lee un comprobante de depósito usando OCR con OpenAI GPT-5.1 visión.
        
        Args:
            archivo_path: Ruta al archivo del comprobante
            mime_type: Tipo MIME del archivo
            
        Returns:
            Diccionario con los datos extraídos del comprobante
        """
        try:
            # Crear sesión de chat con GPT-5.1
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"ocr_{archivo_path.split('/')[-1]}",
                system_message="Eres un asistente experto en leer y extraer información de comprobantes bancarios en español."
            ).with_model("openai", "gpt-5.1")
            
            # Preparar el mensaje con el archivo
            prompt = """Analiza este comprobante de depósito bancario y extrae la siguiente información en formato JSON:

{
  "monto": [monto numérico del depósito, ejemplo: 2000000.00],
  "fecha": [fecha del depósito en formato YYYY-MM-DD],
  "banco_emisor": [nombre del banco que emite el comprobante],
  "cuenta_beneficiaria": [CLABE o número de cuenta del beneficiario, puede estar parcialmente enmascarada con asteriscos],
  "nombre_beneficiario": [nombre completo o razón social del beneficiario],
  "referencia": [número de referencia o folio del depósito],
  "clave_rastreo": [clave de rastreo única de la transacción bancaria]
}

Responde ÚNICAMENTE con el JSON, sin explicaciones adicionales. Si algún campo no está visible, usa null.

IMPORTANTE: La clave_rastreo y referencia son fundamentales para identificar únicamente cada transacción."""
            
            # Para OpenAI, usamos directamente el archivo
            # Nota: OpenAI no usa FileContentWithMimeType, sino que procesa directamente
            # Vamos a leer el archivo y enviarlo como base64 si es imagen, o como texto si es PDF
            
            if mime_type.startswith("image/"):
                # Para imágenes, leemos y enviamos como base64
                with open(archivo_path, "rb") as f:
                    contenido = base64.b64encode(f.read()).decode('utf-8')
                
                # Crear mensaje con imagen
                user_message = UserMessage(
                    text=prompt
                )
                # Nota: Con OpenAI necesitamos usar un formato específico para imágenes
                # Por ahora usaremos el texto y confiaremos en que la librería maneja el archivo
                
            elif mime_type == "application/pdf":
                # Para PDFs, OpenAI puede procesarlos directamente
                user_message = UserMessage(
                    text=prompt
                )
            
            else:
                logger.warning(f"Tipo MIME no soportado: {mime_type}")
                return {
                    "error": f"Tipo de archivo no soportado: {mime_type}"
                }
            
            # Por limitaciones de la librería con OpenAI, vamos a hacer una implementación directa
            # usando la API de OpenAI para visión
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.api_key)
            
            # Leer archivo como base64
            with open(archivo_path, "rb") as f:
                if mime_type.startswith("image/"):
                    file_data = base64.b64encode(f.read()).decode('utf-8')
                    
                    response = await client.chat.completions.create(
                        model="gpt-4o",  # Usando gpt-4o que tiene visión
                        messages=[
                            {
                                "role": "system",
                                "content": "Eres un asistente experto en leer y extraer información de comprobantes bancarios en español."
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{mime_type};base64,{file_data}"
                                        }
                                    }
                                ]
                            }
                        ],
                        max_tokens=1000
                    )
                    
                    respuesta_texto = response.choices[0].message.content
                    
                elif mime_type == "application/pdf":
                    # Para PDFs, usar directamente el modelo de visión con el PDF
                    # OpenAI puede procesar PDFs directamente como imágenes
                    with open(archivo_path, "rb") as f:
                        file_data = base64.b64encode(f.read()).decode('utf-8')
                    
                    # Procesar PDF como imagen base64
                    response = await client.chat.completions.create(
                        model="gpt-4o",  # gpt-4o soporta documentos
                        messages=[
                            {
                                "role": "system",
                                "content": "Eres un asistente experto en leer y extraer información de comprobantes bancarios en español."
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:application/pdf;base64,{file_data}"
                                        }
                                    }
                                ]
                            }
                        ],
                        max_tokens=1000
                    )
                    
                    respuesta_texto = response.choices[0].message.content
            
            # Parsear respuesta JSON
            import json
            
            # Limpiar respuesta si tiene markdown
            if "```json" in respuesta_texto:
                respuesta_texto = respuesta_texto.split("```json")[1].split("```")[0]
            elif "```" in respuesta_texto:
                respuesta_texto = respuesta_texto.split("```")[1].split("```")[0]
            
            datos = json.loads(respuesta_texto.strip())
            
            logger.info(f"OCR completado exitosamente para {archivo_path}")
            return datos
            
        except Exception as e:
            logger.error(f"Error en OCR: {str(e)}")
            return {
                "error": f"Error al procesar comprobante: {str(e)}"
            }
    
    def validar_cuenta_beneficiaria(self, cuenta_leida: str, cuenta_esperada: str) -> bool:
        """
        Valida que la cuenta beneficiaria coincida, considerando enmascaramiento.
        """
        if not cuenta_leida or not cuenta_esperada:
            return False
        
        # Limpiar espacios y caracteres especiales
        cuenta_leida = cuenta_leida.replace(" ", "").replace("-", "")
        cuenta_esperada = cuenta_esperada.replace(" ", "").replace("-", "")
        
        # Si la cuenta leída tiene asteriscos, validar solo los dígitos visibles
        if "*" in cuenta_leida:
            # Extraer los últimos 4 dígitos si están disponibles
            digitos_visibles = "".join([c for c in cuenta_leida if c.isdigit()])
            if len(digitos_visibles) >= 4:
                return cuenta_esperada.endswith(digitos_visibles[-4:])
            return False
        
        # Comparación directa
        return cuenta_leida == cuenta_esperada
    
    def validar_nombre_beneficiario(self, nombre_leido: str, nombre_esperado: str) -> bool:
        """
        Valida que el nombre del beneficiario coincida (flexibilidad en mayúsculas/minúsculas).
        """
        if not nombre_leido or not nombre_esperado:
            return False
        
        # Normalizar y comparar
        nombre_leido = nombre_leido.upper().strip()
        nombre_esperado = nombre_esperado.upper().strip()
        
        # Verificar si al menos una parte significativa coincide
        palabras_esperadas = nombre_esperado.split()
        palabras_leidas = nombre_leido.split()
        
        coincidencias = sum(1 for p in palabras_esperadas if p in palabras_leidas)
        
        # Al menos 50% de las palabras deben coincidir
        return coincidencias >= len(palabras_esperadas) * 0.5


# Instancia global del servicio
ocr_service = OCRService()