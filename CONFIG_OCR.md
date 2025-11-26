# Configuración del Servicio OCR

## API Key Utilizada

El servicio OCR (`/app/backend/ocr_service.py`) utiliza **exclusivamente la Emergent LLM Key** configurada en el entorno de Emergent.

### Variable de Entorno

```
EMERGENT_LLM_KEY
```

Esta clave está pre-configurada en el entorno y NO debe ser modificada manualmente.

## Librería Utilizada

**emergentintegrations** - Librería oficial de Emergent para integración con LLMs.

- Instalación: Ya incluida en el entorno
- Uso: `from emergentintegrations.llm.chat import LlmChat`
- Modelo: `gpt-4o` (con capacidad de visión para imágenes y PDFs)

## Cambios Realizados

- ✅ Eliminada dependencia directa de `openai.AsyncOpenAI`
- ✅ Implementado uso de `emergentintegrations.llm.chat.LlmChat`
- ✅ Soporte para imágenes (JPG, PNG) y PDFs usando `FileContentWithMimeType`
- ✅ API key leída exclusivamente de variable de entorno `EMERGENT_LLM_KEY`

## Campos Extraídos del OCR

- `monto` - Monto numérico del depósito
- `fecha` - Fecha en formato YYYY-MM-DD
- `banco_emisor` - Nombre del banco
- `cuenta_beneficiaria` - CLABE o cuenta (puede estar parcialmente enmascarada)
- `nombre_beneficiario` - Razón social del beneficiario
- `referencia` - Número de referencia
- `clave_rastreo` - Clave de rastreo única (para detección de duplicados)

## Prueba del Servicio

Para verificar que el OCR funciona correctamente:

1. Ir a la interfaz web del Asistente NetCash
2. Crear una nueva operación
3. Subir un comprobante PDF (ejemplo: depósito a THABYETHA)
4. Verificar que se extraen todos los campos correctamente
5. Confirmar que NO aparece error de API key

## Notas

- NO se muestra la clave real por seguridad
- La clave está gestionada por Emergent automáticamente
- NO se requiere configuración manual adicional
