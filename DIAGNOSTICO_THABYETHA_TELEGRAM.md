# Diagnóstico: Desincronización THABYETHA entre Script y Telegram

## 📅 Fecha: 30 Nov 2025 - 11:45 PM

---

## ✅ Cambios Implementados

### 1. Versión del Validador
**Archivo:** `/app/backend/validador_comprobantes_service.py`

```python
# Línea 10
VALIDADOR_THABYETHA_VERSION = "V2.1-sufijo-banamex"
```

### 2. Logs Agregados

#### En `validar_comprobante()` - Línea 349
```python
logger.info(f"[VALIDADOR_NETCASH] Version={VALIDADOR_THABYETHA_VERSION} archivo={nombre_archivo}")
```

#### En `validar_comprobante()` - Logs específicos THABYETHA (líneas 370-381)
```python
if beneficiario_activo == "JARDINERIA Y COMERCIO THABYETHA SA DE CV":
    logger.info(f"[VALIDADOR_THABYETHA] ========== CASO ESPECIAL THABYETHA ==========")
    logger.info(f"[VALIDADOR_THABYETHA] Texto OCR (primeros 800 chars): {texto_comprobante[:800]}")
    logger.info(f"[VALIDADOR_THABYETHA] CLABE objetivo: {clabe_activa}")
    logger.info(f"[VALIDADOR_THABYETHA] Sufijo esperado: {clabe_activa[-3:]}")
    # ... más logs después de validación
    logger.info(f"[VALIDADOR_THABYETHA] Resultado buscar_clabe_en_texto: encontrado={clabe_encontrada} metodo={metodo_clabe}")
    logger.info(f"[VALIDADOR_THABYETHA] Beneficiario_coincide={beneficiario_encontrado}")
```

#### En `buscar_clabe_en_texto()` - Logs detallados (líneas 135-148)
```python
if clabe_objetivo == "646180139409481462":
    logger.info(f"[VALIDADOR_THABYETHA] CLABEs extraídas del PDF: {clabes_completas}")
    logger.info(f"[VALIDADOR_THABYETHA] CLABEs ignoradas (rastreo/asociada/etc): {ignoradas_rastreo}")
    logger.info(f"[VALIDADOR_THABYETHA] CLABEs válidas para comparar: {clabes_validas}")
    logger.info(f"[VALIDADOR_THABYETHA] USANDO METODO: {metodo}")
```

#### En `netcash_service.py` - agregar_comprobante() (líneas 196-197)
```python
logger.info(f"[NC TELEGRAM] Llamando a validar_comprobante() para archivo={nombre_archivo}")
logger.info(f"[NC TELEGRAM] Cuenta activa: banco={cuenta_activa.get('banco')} clabe={cuenta_activa.get('clabe')} beneficiario={cuenta_activa.get('beneficiario')}")
```

---

## ✅ Verificaciones Realizadas

### 1. Solo hay UNA copia del validador
```bash
$ find /app -name "validador_comprobantes_service.py" -type f
/app/backend/validador_comprobantes_service.py
```

### 2. La versión se define correctamente
```bash
$ grep -n "VALIDADOR_THABYETHA_VERSION" /app -r
/app/backend/validador_comprobantes_service.py:10:VALIDADOR_THABYETHA_VERSION = "V2.1-sufijo-banamex"
/app/backend/validador_comprobantes_service.py:349:        logger.info(f"[VALIDADOR_NETCASH] Version={VALIDADOR_THABYETHA_VERSION} archivo={nombre_archivo}")
```

### 3. Servicios reiniciados
```bash
$ sudo supervisorctl restart backend telegram_bot
backend: stopped
telegram_bot: stopped
backend: started
telegram_bot: started

$ sudo supervisorctl status
backend                          RUNNING   pid 1550
telegram_bot                     RUNNING   pid 1554
```

---

## 🧪 Prueba Directa (Python) - ✅ FUNCIONA

### Comando Ejecutado
```python
from validador_comprobantes_service import ValidadorComprobantes

cuenta_activa = {
    "banco": "STP",
    "clabe": "646180139409481462",
    "beneficiario": "JARDINERIA Y COMERCIO THABYETHA SA DE CV"
}

validador = ValidadorComprobantes()
es_valido, razon = validador.validar_comprobante(
    ruta_archivo="/app/backend/uploads/.../THABYETHA SA $185,000.00.pdf",
    mime_type="application/pdf",
    cuenta_activa=cuenta_activa
)
```

### Logs Generados
```
[VALIDADOR_NETCASH] Version=V2.1-sufijo-banamex archivo=nc-1764478071449_THABYETHA SA $185,000.00.pdf
[VALIDADOR_THABYETHA] ========== CASO ESPECIAL THABYETHA ==========
[VALIDADOR_THABYETHA] Texto OCR (primeros 800 chars): Pago interbancario...
[VALIDADOR_THABYETHA] CLABE objetivo: 646180139409481462
[VALIDADOR_THABYETHA] Sufijo esperado: 462
[VALIDADOR_THABYETHA] CLABEs extraídas del PDF: ['085901921704333355']
[VALIDADOR_THABYETHA] CLABEs ignoradas (rastreo/asociada/etc): ['085901921704333355']
[VALIDADOR_THABYETHA] CLABEs válidas para comparar: []
[VALIDADOR_THABYETHA] USANDO METODO: sufijo_banamex
[VALIDADOR_THABYETHA] Resultado buscar_clabe_en_texto: encontrado=True metodo=sufijo_banamex
[VALIDADOR_THABYETHA] Beneficiario_coincide=True
```

### Resultado
```
✅ Válido: True
✅ Razón: CLABE encontrada en formato Banamex (CLABE-462) y coincide con la cuenta NetCash autorizada
```

---

## 🔍 Próximo Paso: Prueba desde Telegram

### Instrucciones para el Usuario

1. **Envía un comprobante THABYETHA desde Telegram:**
   - Inicia operación NetCash: `/start` → "Crear nueva operación"
   - Paso 1: Sube UNO de los PDFs THABYETHA (ej: $185,000.00)
   - Presiona "➡️ Continuar"

2. **Revisa los logs del backend:**
   ```bash
   tail -n 200 /var/log/supervisor/backend.err.log | grep -E "VALIDADOR_NETCASH|VALIDADOR_THABYETHA|NC TELEGRAM"
   ```

3. **Busca estas líneas clave:**

   #### A. Confirmación de versión:
   ```
   [VALIDADOR_NETCASH] Version=V2.1-sufijo-banamex archivo=...
   ```
   → Si NO aparece, el backend NO está usando el código actualizado

   #### B. Logs de THABYETHA:
   ```
   [VALIDADOR_THABYETHA] ========== CASO ESPECIAL THABYETHA ==========
   [VALIDADOR_THABYETHA] Texto OCR (primeros 800 chars): ...
   [VALIDADOR_THABYETHA] CLABEs extraídas del PDF: [...]
   [VALIDADOR_THABYETHA] CLABEs válidas para comparar: []
   [VALIDADOR_THABYETHA] USANDO METODO: sufijo_banamex
   ```

   #### C. Resultado final:
   ```
   [VALIDADOR_THABYETHA] Resultado buscar_clabe_en_texto: encontrado=True metodo=sufijo_banamex
   [VALIDADOR_THABYETHA] Beneficiario_coincide=True
   ```

4. **Comparte estos logs conmigo.**

---

## 🎯 Escenarios Posibles

### Escenario A: Los logs NO aparecen
**Significado:** El backend de Telegram NO está usando el validador actualizado.

**Posibles causas:**
1. El proceso `telegram_bot` está importando una versión cacheada
2. Hay un problema con el import de módulos
3. El supervisor no reinició correctamente

**Solución:**
```bash
# Limpiar cache de Python
find /app/backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find /app/backend -name "*.pyc" -delete 2>/dev/null

# Reiniciar con kill forzoso
sudo supervisorctl stop backend telegram_bot
sleep 3
sudo supervisorctl start backend telegram_bot
```

### Escenario B: Los logs aparecen pero dice "no_encontrada"
**Significado:** El validador se está ejecutando pero la lógica de sufijo NO se activa.

**Posibles causas:**
1. El texto OCR extraído es diferente al del script
2. Hay un problema con la normalización de texto
3. El contexto no contiene "Cuenta de depósito"

**Solución:** Necesitaré ver el log completo del texto OCR para diagnóstico.

### Escenario C: Los logs aparecen y dice "sufijo_banamex" pero luego falla
**Significado:** La CLABE se encuentra pero el beneficiario NO coincide.

**Posibles causas:**
1. El método `buscar_beneficiario_en_texto()` está fallando
2. El beneficiario tiene formato diferente (espacios, mayúsculas, etc.)

**Solución:** Revisar logs de beneficiario.

---

## 📋 Checklist de Diagnóstico

### Antes de probar en Telegram:
- [x] Versión agregada al validador
- [x] Logs detallados implementados
- [x] Verificado que solo hay 1 copia del validador
- [x] Servicios reiniciados
- [x] Prueba directa Python: ✅ FUNCIONA

### Después de probar en Telegram (pendiente):
- [ ] Log de versión aparece en backend
- [ ] Logs de THABYETHA aparecen
- [ ] Método usado es "sufijo_banamex"
- [ ] Beneficiario coincide
- [ ] Resultado es VÁLIDO

---

## 🔧 Comandos Útiles para Debugging

### Ver logs del backend en tiempo real:
```bash
tail -f /var/log/supervisor/backend.err.log
```

### Filtrar solo logs relevantes de THABYETHA:
```bash
tail -n 500 /var/log/supervisor/backend.err.log | grep -E "VALIDADOR|NC TELEGRAM"
```

### Ver procesos de Python corriendo:
```bash
ps aux | grep python
```

### Verificar que no hay cache de Python:
```bash
find /app/backend -name "*.pyc" | wc -l
# Debe ser 0 después de limpiar cache
```

---

## 📊 Comparación: Script vs Telegram

### Script de Prueba (/app/test_validador_thabyetha.py)
- ✅ Importa directamente `ValidadorComprobantes`
- ✅ Llama a `validar_comprobante()` con parámetros explícitos
- ✅ Resultado: **3/3 válidos**

### Flujo de Telegram
- ❓ `telegram_netcash_handlers.py` → `netcash_service.agregar_comprobante()`
- ❓ `netcash_service.py` → `validador_comprobantes.validar_comprobante()`
- ❌ Resultado reportado: **0/3 válidos**

**Hipótesis:** Hay una diferencia en cómo se están pasando los parámetros o en el texto OCR extraído entre el script y Telegram.

---

## 🎯 Próxima Acción Requerida

**POR FAVOR, ejecuta una operación NetCash desde Telegram con un PDF THABYETHA y comparte los logs filtrados:**

```bash
tail -n 300 /var/log/supervisor/backend.err.log | grep -E "VALIDADOR_NETCASH|VALIDADOR_THABYETHA|NC TELEGRAM"
```

Con estos logs podré identificar EXACTAMENTE dónde está el gap entre el script (que funciona) y Telegram (que falla).

---

**Estado Actual:**
- ✅ Código modificado con logs detallados
- ✅ Servicios reiniciados
- ✅ Prueba directa: FUNCIONA
- ⏳ Pendiente: Prueba desde Telegram + logs

**Implementado por:** E1 (Emergent Agent)  
**Fecha:** 30 Nov 2025  
**Estado:** ⏳ Esperando prueba desde Telegram
