"""
Servicio de Tesorería para manejo de operaciones individuales
(Layout por operación en lugar de lotes agrupados)

Este servicio complementa al tesoreria_service.py existente para
el nuevo modelo de trabajo: una operación = un layout = un correo
"""

import logging
import os
import csv
from datetime import datetime, timezone
from typing import Dict, Optional, List
from io import StringIO
from motor.motor_asyncio import AsyncIOMotorClient
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import aiohttp

logger = logging.getLogger(__name__)

# Conexión MongoDB
mongo_url = os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'netcash_mbco')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

COLLECTION_NAME = 'solicitudes_netcash'

# Configuración de tasas de comisión (igual que en tesoreria_service)
NETCASH_COMISION_CLIENTE_PCT = Decimal('0.01')  # 1%
NETCASH_COMISION_DNS_PCT = Decimal('0.00375')    # 0.375%


class TesoreriaOperacionService:
    """Servicio para gestión de operaciones individuales de Tesorería"""
    
    def __init__(self):
        self.tesoreria_email = os.getenv('TESORERIA_TEST_EMAIL', 'dfgalezzo@hotmail.com')
        logger.info(f"[TesoreriaOp] Servicio inicializado")
        logger.info(f"[TesoreriaOp] Email Tesorería: {self.tesoreria_email}")
    
    def _partir_capital_en_ligas(self, capital: Decimal) -> List[Decimal]:
        """
        Divide el capital en múltiples filas cumpliendo reglas estrictas:
        
        1. Cada fila debe estar entre $100,000 y $349,999.99
        2. Montos irregulares con centavos (no montos "bonitos")
        3. No repetir exactamente el mismo monto
        4. La suma debe ser exactamente igual al capital
        
        Args:
            capital: Monto total a dividir
            
        Returns:
            Lista de montos (Decimal) que suman exactamente el capital
        """
        import random
        
        MIN_LIGA = Decimal('100000.00')
        MAX_LIGA = Decimal('349999.99')
        
        if capital <= MIN_LIGA:
            # Si el capital es menor o igual al mínimo, retornar una sola liga
            return [capital]
        
        ligas = []
        restante = capital
        
        # Calcular cuántas ligas necesitamos (aproximado)
        # Para evitar que la última sea muy pequeña, usamos un promedio
        promedio_por_liga = (MIN_LIGA + MAX_LIGA) / Decimal('2')
        num_ligas_aprox = int(capital / promedio_por_liga)
        
        if num_ligas_aprox < 1:
            num_ligas_aprox = 1
        
        # Generar ligas con montos irregulares
        for i in range(num_ligas_aprox):
            if restante <= MIN_LIGA:
                # Si queda poco, agregar como última liga
                if restante > Decimal('0'):
                    ligas.append(restante)
                break
            
            # Calcular monto máximo para esta liga
            # Asegurarnos de que quede suficiente para las ligas restantes
            ligas_restantes = num_ligas_aprox - i
            max_para_esta_liga = min(MAX_LIGA, restante - (MIN_LIGA * Decimal(str(ligas_restantes - 1))))
            
            if max_para_esta_liga < MIN_LIGA:
                max_para_esta_liga = MIN_LIGA
            
            if max_para_esta_liga > restante:
                max_para_esta_liga = restante
            
            # Generar monto irregular entre MIN y max_para_esta_liga
            # Usar random para generar centavos "feos"
            rango_entero = int((max_para_esta_liga - MIN_LIGA) * Decimal('100'))  # En centavos
            
            if rango_entero > 0:
                centavos_aleatorios = random.randint(0, rango_entero)
                monto_liga = MIN_LIGA + (Decimal(str(centavos_aleatorios)) / Decimal('100'))
            else:
                monto_liga = MIN_LIGA
            
            # Redondear a 2 decimales
            monto_liga = monto_liga.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Verificar que no sea igual a las anteriores (si es posible)
            intentos = 0
            while monto_liga in ligas and intentos < 10:
                centavos_aleatorios = random.randint(0, rango_entero)
                monto_liga = MIN_LIGA + (Decimal(str(centavos_aleatorios)) / Decimal('100'))
                monto_liga = monto_liga.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                intentos += 1
            
            ligas.append(monto_liga)
            restante -= monto_liga
        
        # Ajuste final: si quedó un restante, manejarlo adecuadamente
        if restante > Decimal('0.01'):
            # Si el restante es significativo
            if restante >= MIN_LIGA and restante <= MAX_LIGA:
                # Si está en rango, agregarlo como nueva liga
                ligas.append(restante)
            elif restante > MAX_LIGA:
                # Si es muy grande, dividirlo recursivamente
                ligas_restante = self._partir_capital_en_ligas(restante)
                ligas.extend(ligas_restante)
            else:
                # Si es muy pequeño, agregarlo a la última liga
                if ligas:
                    ultima_liga = ligas[-1]
                    if ultima_liga + restante <= MAX_LIGA:
                        ligas[-1] += restante
                    else:
                        # La última liga se pasaría, crear nueva
                        ligas.append(restante)
                else:
                    ligas.append(restante)
        elif restante < Decimal('-0.01'):
            # Si nos pasamos (por redondeos), ajustar la última liga
            if ligas:
                ligas[-1] += restante  # restante será negativo, así que resta
        
        # Verificación final
        suma = sum(ligas)
        diferencia = capital - suma
        
        if abs(diferencia) > Decimal('0.01'):
            # Ajuste de precisión en la última liga
            if ligas:
                ligas[-1] += diferencia
        
        logger.info(f"[TesoreriaOp] Capital ${capital:,.2f} dividido en {len(ligas)} liga(s)")
        for i, liga in enumerate(ligas, 1):
            logger.info(f"[TesoreriaOp]   Liga {i}: ${liga:,.2f}")
        
        return ligas
    
    def _convertir_folio_para_concepto(self, folio_mbco: str) -> str:
        """
        Convierte folio MBco para usar en concepto (reemplaza guiones por 'x')
        
        Ejemplos:
        - 1234-209-M-11 → 1234x209xMx11
        - 3452-232-D-11 → 3452x232xDx11
        """
        return folio_mbco.replace('-', 'x')
    
    async def procesar_operacion_tesoreria(self, solicitud_id: str) -> Optional[Dict]:
        """
        Procesa una operación individual de tesorería:
        1. Genera layout CSV individual
        2. Envía correo a Tesorería con layout y comprobantes
        3. Actualiza estado de la solicitud a 'enviado_a_tesoreria'
        
        Args:
            solicitud_id: ID de la solicitud a procesar
            
        Returns:
            Dict con resultado del procesamiento o None si hubo error
        """
        logger.info(f"[TesoreriaOp] ========== INICIO PROCESO OPERACIÓN INDIVIDUAL ==========")
        logger.info(f"[TesoreriaOp] Solicitud ID: {solicitud_id}")
        
        try:
            # 1. Obtener solicitud
            solicitud = await db[COLLECTION_NAME].find_one(
                {'id': solicitud_id},
                {'_id': 0}
            )
            
            if not solicitud:
                logger.error(f"[TesoreriaOp] Solicitud no encontrada: {solicitud_id}")
                return None
            
            folio_mbco = solicitud.get('folio_mbco', 'SIN-FOLIO')
            cliente = solicitud.get('cliente_nombre', 'N/A')
            
            logger.info(f"[TesoreriaOp] Procesando operación:")
            logger.info(f"[TesoreriaOp]   Folio MBco: {folio_mbco}")
            logger.info(f"[TesoreriaOp]   Cliente: {cliente}")
            
            # 2. Calcular comisión DNS
            capital = Decimal(str(solicitud.get('monto_ligas', 0)))
            comision_dns = (capital * NETCASH_COMISION_DNS_PCT).quantize(
                Decimal('0.01'), 
                rounding=ROUND_HALF_UP
            )
            
            solicitud['comision_dns_calculada'] = float(comision_dns)
            
            logger.info(f"[TesoreriaOp]   Capital: ${capital:,.2f}")
            logger.info(f"[TesoreriaOp]   Comisión DNS: ${comision_dns:,.2f}")
            
            # 3. Generar layout CSV individual
            layout_csv = await self._generar_layout_operacion(solicitud)
            
            # 4. Enviar correo a Tesorería
            await self._enviar_correo_operacion(solicitud, layout_csv)
            
            # 5. Actualizar estado de la solicitud
            fecha_envio = datetime.now(timezone.utc)
            
            await db[COLLECTION_NAME].update_one(
                {'id': solicitud_id},
                {
                    '$set': {
                        'estado': 'enviado_a_tesoreria',
                        'fecha_envio_tesoreria': fecha_envio,
                        'layout_individual_generado': True,
                        'updated_at': fecha_envio
                    },
                    '$push': {
                        'estado_historico': {
                            'estado': 'enviado_a_tesoreria',
                            'en': fecha_envio,
                            'por': 'tesoreria_operacion_service',
                            'notas': f'Layout individual generado y enviado para {folio_mbco}'
                        }
                    }
                }
            )
            
            logger.info(f"[TesoreriaOp] ✅ Operación procesada exitosamente")
            logger.info(f"[TesoreriaOp] ========== FIN PROCESO OPERACIÓN ==========")
            
            return {
                'success': True,
                'solicitud_id': solicitud_id,
                'folio_mbco': folio_mbco,
                'fecha_envio': fecha_envio
            }
            
        except Exception as e:
            logger.error(f"[TesoreriaOp] ❌ Error procesando operación {solicitud_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _generar_layout_operacion(self, solicitud: Dict) -> str:
        """
        Genera layout CSV Fondeadora para una operación individual
        
        Returns:
            String con contenido CSV
        """
        folio_mbco = solicitud.get('folio_mbco', 'SIN-FOLIO')
        folio_concepto = self._convertir_folio_para_concepto(folio_mbco)
        
        logger.info(f"[TesoreriaOp] Generando layout individual para {folio_mbco}")
        
        # Obtener cuentas activas del proveedor
        from cuentas_proveedor_service import cuentas_proveedor_service
        
        cuenta_capital = await cuentas_proveedor_service.obtener_cuenta_activa("capital")
        cuenta_comision = await cuentas_proveedor_service.obtener_cuenta_activa("comision_dns")
        
        if not cuenta_capital or not cuenta_comision:
            raise ValueError("No hay cuentas de proveedor activas configuradas")
        
        clabe_capital = cuenta_capital.get('clabe')
        beneficiario_capital = cuenta_capital.get('beneficiario')
        clabe_comision = cuenta_comision.get('clabe')
        beneficiario_comision = cuenta_comision.get('beneficiario')
        
        # Generar CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Clabe destinatario',
            'Nombre o razon social destinatario',
            'Monto',
            'Concepto',
            'Email (opcional)',
            'Tags separados por comas (opcional)',
            'Comentario (opcional)'
        ])
        
        # Datos de la operación
        monto_ligas = Decimal(str(solicitud.get('monto_ligas', 0)))
        comision_dns = Decimal(str(solicitud.get('comision_dns_calculada', 0)))
        
        # FILAS DE CAPITAL (LIGAS)
        # Usar la función que divide el capital en montos irregulares
        # entre $100,000 y $349,999.99
        if monto_ligas > 0:
            ligas = self._partir_capital_en_ligas(monto_ligas)
            
            for i, monto_liga in enumerate(ligas, 1):
                writer.writerow([
                    clabe_capital,
                    beneficiario_capital,
                    f"{monto_liga:.2f}",
                    f"MBco {folio_concepto}",
                    '',
                    '',
                    f"Liga {i}/{len(ligas)}"
                ])
        
        # FILA DE COMISIÓN DNS
        if comision_dns > 0:
            writer.writerow([
                clabe_comision,
                beneficiario_comision,
                f"{comision_dns:.2f}",
                f"MBco {folio_concepto} COMISION",
                '',
                '',
                "Comisión proveedor DNS"
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        logger.info(f"[TesoreriaOp] Layout generado: {len(csv_content)} caracteres")
        
        return csv_content
    
    async def _enviar_correo_operacion(self, solicitud: Dict, layout_csv: str):
        """
        Envía correo a Tesorería con layout y comprobantes de la operación
        """
        folio_mbco = solicitud.get('folio_mbco', 'SIN-FOLIO')
        folio_concepto = self._convertir_folio_para_concepto(folio_mbco)
        cliente = solicitud.get('cliente_nombre', 'N/A')
        
        logger.info(f"[TesoreriaOp] Enviando correo para operación {folio_mbco}")
        
        # Asunto
        asunto = f"NetCash – Orden de dispersión {folio_mbco} – {cliente}"
        
        # Cuerpo
        cuerpo = self._generar_cuerpo_correo_operacion(solicitud)
        
        # Preparar adjuntos
        # 1. Guardar CSV temporal
        import tempfile
        csv_filename = f"LTMBCO_{folio_concepto}.csv"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(layout_csv)
            csv_path = f.name
        
        adjuntos = [csv_path]
        
        # 2. Agregar comprobantes del cliente
        comprobantes = solicitud.get('comprobantes', [])
        for comp in comprobantes:
            if comp.get('es_valido') and not comp.get('es_duplicado'):
                ruta = comp.get('ruta_archivo')
                if ruta and Path(ruta).exists():
                    adjuntos.append(ruta)
        
        logger.info(f"[TesoreriaOp] Adjuntos: 1 CSV + {len(adjuntos)-1} comprobantes")
        
        # Enviar correo
        from gmail_service import gmail_service
        
        if not gmail_service:
            logger.warning(f"[TesoreriaOp] Gmail service no disponible")
            
            # Guardar CSV localmente
            csv_dir = Path("/app/backend/uploads/layouts_operaciones")
            csv_dir.mkdir(parents=True, exist_ok=True)
            csv_path_saved = csv_dir / csv_filename
            
            with open(csv_path_saved, 'w', encoding='utf-8') as f:
                f.write(layout_csv)
            
            logger.info(f"[TesoreriaOp] CSV guardado en: {csv_path_saved}")
            return
        
        try:
            email_info = await gmail_service.enviar_correo_con_adjuntos(
                destinatario=self.tesoreria_email,
                asunto=asunto,
                cuerpo=cuerpo,
                adjuntos=adjuntos
            )
            
            if email_info:
                logger.info(f"[TesoreriaOp] ✅ Correo enviado a {self.tesoreria_email}")
                
                # Guardar thread_id en la solicitud para poder asociar respuestas
                solicitud_id = solicitud.get('id')
                await db.solicitudes_netcash.update_one(
                    {"id": solicitud_id},
                    {
                        "$set": {
                            "email_thread_id": email_info['thread_id'],
                            "email_message_id": email_info['message_id']
                        }
                    }
                )
                logger.info(f"[TesoreriaOp] Thread ID guardado: {email_info['thread_id']}")
            else:
                raise Exception("No se obtuvo información del email enviado")
            
        except Exception as e:
            logger.error(f"[TesoreriaOp] ❌ Error enviando correo: {str(e)}")
            
            # Guardar CSV localmente como respaldo
            csv_dir = Path("/app/backend/uploads/layouts_operaciones")
            csv_dir.mkdir(parents=True, exist_ok=True)
            csv_path_saved = csv_dir / csv_filename
            
            with open(csv_path_saved, 'w', encoding='utf-8') as f:
                f.write(layout_csv)
            
            logger.info(f"[TesoreriaOp] CSV guardado localmente en: {csv_path_saved}")
        
        finally:
            # Limpiar CSV temporal
            try:
                os.unlink(csv_path)
            except:
                pass
    
    def _generar_cuerpo_correo_operacion(self, solicitud: Dict) -> str:
        """Genera cuerpo HTML del correo por operación"""
        
        folio_mbco = solicitud.get('folio_mbco', 'N/A')
        folio_netcash = solicitud.get('id', 'N/A')
        cliente = solicitud.get('cliente_nombre', 'N/A')
        beneficiario = solicitud.get('beneficiario_reportado', 'N/A')
        idmex = solicitud.get('idmex_reportado', 'N/A')
        
        total_depositos = solicitud.get('total_comprobantes_validos', 0)
        capital = solicitud.get('monto_ligas', 0)
        comision_dns = solicitud.get('comision_dns_calculada', 0)
        total_proveedor = capital + comision_dns
        
        cuerpo = "<html><body>"
        cuerpo += "<h2>Orden de Tesorería NetCash – POR OPERACIÓN</h2>"
        cuerpo += f"<p><strong>Folio NetCash:</strong> {folio_netcash}</p>"
        cuerpo += f"<p><strong>Folio MBco:</strong> {folio_mbco}</p>"
        cuerpo += f"<p><strong>Cliente:</strong> {cliente}</p>"
        cuerpo += f"<p><strong>Beneficiario:</strong> {beneficiario}</p>"
        cuerpo += f"<p><strong>IDMEX:</strong> {idmex}</p>"
        cuerpo += "<hr>"
        
        # Comprobantes
        comprobantes = solicitud.get('comprobantes', [])
        comprobantes_validos = [c for c in comprobantes if c.get('es_valido') and not c.get('es_duplicado')]
        
        cuerpo += "<h3>Resumen de comprobantes:</h3>"
        cuerpo += "<ul>"
        cuerpo += f"<li><strong>Total comprobantes:</strong> {len(comprobantes_validos)}</li>"
        
        for i, comp in enumerate(comprobantes_validos, 1):
            monto = comp.get('monto_detectado', 0)
            cuenta = comp.get('cuenta_detectada', {})
            clabe = cuenta.get('clabe', 'N/A') if cuenta else 'N/A'
            cuerpo += f"<li>Comprobante {i}: ${monto:,.2f} – Cuenta destino: {clabe}</li>"
        
        cuerpo += f"<li><strong>→ Total depósitos detectados: ${total_depositos:,.2f}</strong></li>"
        cuerpo += "</ul>"
        
        # Resumen financiero
        cuerpo += "<h3>Resumen financiero:</h3>"
        cuerpo += "<ul>"
        cuerpo += f"<li>Total depósitos recibidos: ${total_depositos:,.2f}</li>"
        cuerpo += f"<li>Capital a proveedor (ligas): ${capital:,.2f}</li>"
        cuerpo += f"<li>Comisión DNS (0.375% capital): ${comision_dns:,.2f}</li>"
        cuerpo += f"<li><strong>Total a dispersar al proveedor: ${total_proveedor:,.2f}</strong></li>"
        cuerpo += "</ul>"
        
        # Pasos para Tesorería
        cuerpo += "<hr>"
        cuerpo += "<div style='margin: 20px 0; padding: 15px; background: #fff3cd; border: 2px solid #ffc107;'>"
        cuerpo += "<h3>📋 Pasos para Tesorería (POR OPERACIÓN)</h3>"
        cuerpo += "<ol>"
        cuerpo += "<li><strong>Validar ingreso en firme</strong><ul>"
        cuerpo += "<li>Verifica en tu banca que los depósitos relacionados con esta operación ya están en firme (no retenidos).</li>"
        cuerpo += "</ul></li>"
        cuerpo += "<li><strong>Subir el layout a la banca del proveedor</strong><ul>"
        cuerpo += "<li>Usa el archivo CSV adjunto para dispersar:</li>"
        cuerpo += "<li>• Capital (AFFORDABLE MEDICAL SERVICES SC)</li>"
        cuerpo += "<li>• Comisión DNS (COMERCIALIZADORA UETACOP SA DE CV)</li>"
        cuerpo += "</ul></li>"
        cuerpo += "<li><strong>Responder este correo con comprobantes</strong><ul>"
        cuerpo += "<li>Una vez hechas las transferencias al proveedor, responde a este mismo correo adjuntando los comprobantes de dispersión (PDFs / imágenes de las transferencias).</li>"
        cuerpo += "</ul></li>"
        cuerpo += "</ol>"
        cuerpo += "</div>"
        
        cuerpo += "</body></html>"
        
        return cuerpo


# Instancia global del servicio
tesoreria_operacion_service = TesoreriaOperacionService()
