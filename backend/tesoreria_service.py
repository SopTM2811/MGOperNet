"""
Servicio de Tesorería para NetCash

Responsabilidades:
- Generar lotes cada 15 minutos
- Crear layouts CSV formato Fondeadora
- Enviar correos a Tesorería
- Notificar por Telegram
"""

import logging
import os
import csv
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
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

# Configuración de tasas de comisión
# IMPORTANTE: Estas son las fórmulas correctas del negocio
# - Cliente paga: 1% del total de depósitos
# - Proveedor DNS recibe: 0.375% del capital
# - Margen MBco: diferencia entre ambas (NO se incluye en layout ni correo a Tesorería)
NETCASH_COMISION_CLIENTE_PCT = Decimal('0.01')  # 1%
NETCASH_COMISION_DNS_PCT = Decimal('0.00375')    # 0.375%

# Configuración
COLLECTION_NAME = 'solicitudes_netcash'
LOTES_COLLECTION = 'lotes_tesoreria'

class TesoreriaService:
    """Servicio para gestión de lotes y dispersiones de Tesorería"""
    
    def __init__(self):
        self.tesoreria_email = os.getenv('TESORERIA_TEST_EMAIL', 'dfgalezzo@hotmail.com')
        
        # Las cuentas de proveedor se obtienen dinámicamente de la BD
        # en lugar de env vars para facilitar cambios de proveedor
        
        logger.info(f"[Tesorería] Servicio inicializado")
        logger.info(f"[Tesorería] Email: {self.tesoreria_email}")
        logger.info(f"[Tesorería] Cuentas de proveedor se cargan dinámicamente de BD")
    
    def convertir_folio_mbco_para_concepto(self, folio_mbco: str) -> str:
        """
        Convierte folio MBco de formato 1234-209-M-11 a 1234x209xMx11
        
        Args:
            folio_mbco: Folio en formato original (ej: "3452-232-D-11")
            
        Returns:
            Folio con guiones reemplazados por 'x' (ej: "3452x232xDx11")
        """
        return folio_mbco.replace('-', 'x')
    
    async def generar_layout_fondeadora(self, solicitudes: List[Dict]) -> str:
        """
        Genera layout CSV formato Fondeadora para un lote de solicitudes
        
        IMPORTANTE: El layout SIEMPRE va dirigido al PROVEEDOR (quien genera las ligas),
        NO al cliente final ni al beneficiario final.
        
        Layout Fondeadora:
        Clabe destinatario, Nombre o razon social destinatario, Monto, Concepto, Email (opcional), Tags (opcional), Comentario (opcional)
        
        Args:
            solicitudes: Lista de solicitudes a incluir en el layout
            
        Returns:
            String con contenido CSV
        """
        logger.info(f"[Tesorería] Generando layout Fondeadora para {len(solicitudes)} solicitudes")
        
        # Obtener cuentas activas del proveedor desde BD
        from cuentas_proveedor_service import cuentas_proveedor_service
        
        cuenta_capital = await cuentas_proveedor_service.obtener_cuenta_activa("capital")
        cuenta_comision = await cuentas_proveedor_service.obtener_cuenta_activa("comision_dns")
        
        if not cuenta_capital:
            raise ValueError("No hay cuenta de capital activa configurada para el proveedor")
        if not cuenta_comision:
            raise ValueError("No hay cuenta de comisión DNS activa configurada para el proveedor")
        
        # Extraer datos de las cuentas
        clabe_capital = cuenta_capital.get('clabe')
        beneficiario_capital = cuenta_capital.get('beneficiario')
        
        clabe_comision = cuenta_comision.get('clabe')
        beneficiario_comision = cuenta_comision.get('beneficiario')
        
        logger.info(f"[Tesorería] Cuenta capital: {beneficiario_capital} - {clabe_capital}")
        logger.info(f"[Tesorería] Cuenta comisión DNS: {beneficiario_comision} - {clabe_comision}")
        
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
        
        for solicitud in solicitudes:
            folio_mbco = solicitud.get('folio_mbco', 'SIN-FOLIO')
            folio_concepto = self.convertir_folio_mbco_para_concepto(folio_mbco)
            n_ligas = solicitud.get('cantidad_ligas_reportada', 1)
            monto_ligas = Decimal(str(solicitud.get('monto_ligas', 0)))
            
            # IMPORTANTE: Usar la comisión DNS calculada (0.375% del capital)
            # NO usar comision_cliente (que es 1% del total)
            comision_dns = Decimal(str(solicitud.get('comision_dns_calculada', 0)))
            
            # Datos para contexto interno (NO van como destinatario en el layout)
            cliente = solicitud.get('cliente_nombre', 'N/A')
            beneficiario_final = solicitud.get('beneficiario_reportado', 'N/A')
            
            # FILAS DE CAPITAL (LIGAS) - Destinatario: PROVEEDOR
            # El proveedor es quien genera las ligas, por eso se le paga el capital
            if n_ligas > 0 and monto_ligas > 0:
                monto_por_liga = (monto_ligas / Decimal(str(n_ligas))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                
                # Generar n-1 filas con monto_por_liga
                for i in range(n_ligas - 1):
                    writer.writerow([
                        clabe_capital,                    # CLABE del proveedor
                        beneficiario_capital,             # Nombre del proveedor
                        f"{monto_por_liga:.2f}",
                        f"MBco {folio_concepto}",        # Concepto con folio transformado
                        '',  # Email
                        '',  # Tags
                        f"Liga {i+1}/{n_ligas}"          # Comentario interno
                    ])
                
                # Última fila ajustada para que sume exacto
                monto_ultima_liga = monto_ligas - (monto_por_liga * Decimal(str(n_ligas - 1)))
                writer.writerow([
                    clabe_capital,
                    beneficiario_capital,
                    f"{monto_ultima_liga:.2f}",
                    f"MBco {folio_concepto}",
                    '',
                    '',
                    f"Liga {n_ligas}/{n_ligas}"
                ])
            
            # FILA DE COMISIÓN DNS - Destinatario: PROVEEDOR (cuenta de comisión)
            # Esta es la comisión que se le paga al proveedor por el servicio
            if comision_dns > 0:
                writer.writerow([
                    clabe_comision,                      # CLABE de comisión del proveedor
                    beneficiario_comision,               # Nombre del proveedor (cuenta comisión)
                    f"{comision_dns:.2f}",
                    f"MBco {folio_concepto} COMISION",   # Concepto con COMISION
                    '',
                    '',
                    f"Comisión proveedor"                # Comentario
                ])
        
        csv_content = output.getvalue()
        output.close()
        
        logger.info(f"[Tesorería] Layout CSV generado: {len(csv_content)} caracteres")
        logger.info(f"[Tesorería] Destinatarios: Capital={beneficiario_capital}, Comisión={beneficiario_comision}")
        return csv_content
    
    async def procesar_lote_tesoreria(self) -> Optional[Dict]:
        """
        Proceso principal que se ejecuta cada 15 minutos
        
        1. Busca solicitudes con estado orden_interna_generada
        2. Agrupa en lote
        3. Genera layout CSV
        4. Envía correo a Tesorería
        5. Notifica por Telegram
        6. Cambia estado a enviado_a_tesoreria
        
        Returns:
            Dict con información del lote procesado o None si no hay solicitudes
        """
        logger.info(f"[Tesorería] ========== INICIO PROCESO LOTE TESORERÍA ==========")
        
        # 1. Buscar solicitudes pendientes
        solicitudes = await db[COLLECTION_NAME].find(
            {'estado': 'orden_interna_generada'},
            {'_id': 0}
        ).to_list(1000)
        
        if not solicitudes:
            logger.info(f"[Tesorería] No hay solicitudes pendientes. Saltando ciclo.")
            return None
        
        logger.info(f"[Tesorería] Encontradas {len(solicitudes)} solicitudes pendientes")
        
        # 2. Crear lote
        lote_id = f"LT-{int(datetime.now(timezone.utc).timestamp())}"
        fecha_corte = datetime.now(timezone.utc)
        
        # Calcular totales
        # IMPORTANTE: Usar las fórmulas correctas del negocio
        total_depositos = Decimal('0')
        total_capital = Decimal('0')
        total_comision_dns = Decimal('0')  # Lo que realmente se paga al proveedor
        total_comision_cliente = Decimal('0')  # Lo que se cobra al cliente (NO va al layout)
        
        for sol in solicitudes:
            depositos = Decimal(str(sol.get('total_comprobantes_validos', 0)))
            capital = Decimal(str(sol.get('monto_ligas', 0)))
            comision_cliente = Decimal(str(sol.get('comision_cliente', 0)))
            
            # Comisión DNS = 0.375% del capital (lo que se paga al proveedor)
            comision_dns = (capital * NETCASH_COMISION_DNS_PCT).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Agregar a la solicitud para usarlo después
            sol['comision_dns_calculada'] = float(comision_dns)
            
            total_depositos += depositos
            total_capital += capital
            total_comision_dns += comision_dns
            total_comision_cliente += comision_cliente
        
        # Margen MBco = comision_cliente - comision_dns
        # Este margen NO se incluye en el layout ni en el correo de Tesorería
        margen_mbco = total_comision_cliente - total_comision_dns
        
        lote_info = {
            'id': lote_id,
            'fecha_corte': fecha_corte,
            'n_solicitudes': len(solicitudes),
            'total_depositos': float(total_depositos),
            'total_capital': float(total_capital),
            'total_comision_dns': float(total_comision_dns),  # Lo que realmente va al proveedor
            'total_comision_cliente': float(total_comision_cliente),  # Solo para tracking interno
            'margen_mbco': float(margen_mbco),  # Solo para tracking interno, NO va a tesorería
            'solicitudes_ids': [s.get('id') for s in solicitudes],
            'estado': 'enviado'
        }
        
        logger.info(f"[Tesorería] Lote creado: {lote_id}")
        logger.info(f"[Tesorería] Solicitudes: {len(solicitudes)}")
        logger.info(f"[Tesorería] Total depósitos: ${total_depositos:,.2f}")
        logger.info(f"[Tesorería] Total capital (a proveedor): ${total_capital:,.2f}")
        logger.info(f"[Tesorería] Total comisión DNS (0.375% capital, a proveedor): ${total_comision_dns:,.2f}")
        logger.info(f"[Tesorería] [INTERNO] Comisión cliente (1%): ${total_comision_cliente:,.2f}")
        logger.info(f"[Tesorería] [INTERNO] Margen MBco: ${margen_mbco:,.2f}")
        
        # 3. Generar layout CSV
        layout_csv = await self.generar_layout_fondeadora(solicitudes)
        
        # 4. Enviar correo a Tesorería
        await self._enviar_correo_tesoreria(lote_info, solicitudes, layout_csv)
        
        # 5. Notificar por Telegram
        await self._notificar_telegram_tesoreria(lote_info, solicitudes)
        
        # 6. Actualizar estado de solicitudes
        for solicitud in solicitudes:
            await db[COLLECTION_NAME].update_one(
                {'id': solicitud.get('id')},
                {
                    '$set': {
                        'estado': 'enviado_a_tesoreria',
                        'lote_tesoreria_id': lote_id,
                        'fecha_envio_tesoreria': fecha_corte,
                        'enviado_por_scheduler': True,
                        'updated_at': datetime.now(timezone.utc)
                    },
                    '$push': {
                        'estado_historico': {
                            'estado': 'enviado_a_tesoreria',
                            'en': fecha_corte,
                            'por': 'scheduler_tesoreria',
                            'notas': f'Incluido en lote {lote_id}'
                        }
                    }
                }
            )
        
        # Guardar lote en BD
        await db[LOTES_COLLECTION].insert_one(lote_info)
        
        logger.info(f"[Tesorería] Lote {lote_id} procesado exitosamente")
        logger.info(f"[Tesorería] ========== FIN PROCESO LOTE TESORERÍA ==========")
        
        return lote_info
    
    async def _enviar_correo_tesoreria(self, lote_info: Dict, solicitudes: List[Dict], layout_csv: str):
        """Envía correo a Tesorería con detalle y layout adjunto"""
        logger.info(f"[Tesorería] Preparando correo para {self.tesoreria_email}")
        
        # Construir asunto
        fecha_str = lote_info['fecha_corte'].strftime('%Y-%m-%d %H:%M')
        asunto = f"NetCash – Lote Tesorería – {fecha_str} – {lote_info['n_solicitudes']} solicitudes"
        
        # Construir cuerpo
        cuerpo = self._generar_cuerpo_correo(lote_info, solicitudes)
        
        # Enviar correo con adjunto
        from gmail_service import gmail_service
        
        # Verificar si gmail_service está disponible
        if not gmail_service:
            logger.warning(f"[Tesorería] Gmail service no disponible. No se puede enviar correo.")
            logger.warning(f"[Tesorería] El layout CSV se guardará localmente.")
            
            # Guardar CSV en disco para referencia
            import tempfile
            csv_dir = Path("/app/backend/uploads/layouts_tesoreria")
            csv_dir.mkdir(parents=True, exist_ok=True)
            
            lote_id = lote_info['id']
            csv_filename = f"{lote_id}_layout.csv"
            csv_path = csv_dir / csv_filename
            
            with open(csv_path, 'w', encoding='utf-8') as f:
                f.write(layout_csv)
            
            logger.info(f"[Tesorería] Layout guardado en: {csv_path}")
            logger.info(f"[Tesorería] ⚠️ IMPORTANTE: Enviar manualmente el layout a {self.tesoreria_email}")
            return
        
        # Guardar CSV temporalmente
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(layout_csv)
            csv_path = f.name
        
        try:
            await gmail_service.enviar_correo_con_adjuntos(
                destinatario=self.tesoreria_email,
                asunto=asunto,
                cuerpo=cuerpo,
                adjuntos=[csv_path]
            )
            logger.info(f"[Tesorería] ✅ Correo enviado exitosamente a {self.tesoreria_email}")
        except Exception as e:
            logger.error(f"[Tesorería] ❌ Error enviando correo: {str(e)}")
            logger.warning(f"[Tesorería] El proceso continuará, pero el correo no se envió")
            
            # Guardar CSV en disco para referencia
            csv_dir = Path("/app/backend/uploads/layouts_tesoreria")
            csv_dir.mkdir(parents=True, exist_ok=True)
            
            lote_id = lote_info['id']
            csv_filename = f"{lote_id}_layout.csv"
            csv_path_saved = csv_dir / csv_filename
            
            with open(csv_path_saved, 'w', encoding='utf-8') as f:
                f.write(layout_csv)
            
            logger.info(f"[Tesorería] Layout guardado localmente en: {csv_path_saved}")
            logger.info(f"[Tesorería] ⚠️ IMPORTANTE: Enviar manualmente el layout a {self.tesoreria_email}")
        finally:
            # Limpiar archivo temporal
            import os as os_module
            try:
                os_module.unlink(csv_path)
            except:
                pass
    
    def _generar_cuerpo_correo(self, lote_info: Dict, solicitudes: List[Dict]) -> str:
        """Genera el cuerpo HTML del correo de Tesorería"""
        
        cuerpo = "<html><body>"
        cuerpo += "<h2>Lote de Tesorería NetCash</h2>"
        cuerpo += f"<p><strong>ID Lote:</strong> {lote_info['id']}</p>"
        cuerpo += f"<p><strong>Fecha/Hora:</strong> {lote_info['fecha_corte'].strftime('%Y-%m-%d %H:%M UTC')}</p>"
        cuerpo += "<hr>"
        
        # Detalle por solicitud
        for i, solicitud in enumerate(solicitudes, 1):
            cuerpo += "<div style='margin: 20px 0; padding: 15px; border: 1px solid #ddd; background: #f9f9f9;'>"
            cuerpo += f"<h3>Solicitud {i} de {len(solicitudes)}</h3>"
            
            folio_mbco = solicitud.get('folio_mbco', 'N/A')
            cliente = solicitud.get('cliente_nombre', 'N/A')
            beneficiario = solicitud.get('beneficiario_reportado', 'N/A')
            idmex = solicitud.get('idmex_reportado', 'N/A')
            estado = solicitud.get('estado', 'N/A')
            
            cuerpo += f"<p><strong>Folio MBco:</strong> {folio_mbco}</p>"
            cuerpo += f"<p><strong>Cliente:</strong> {cliente}</p>"
            cuerpo += f"<p><strong>Beneficiario:</strong> {beneficiario}</p>"
            cuerpo += f"<p><strong>IDMEX:</strong> {idmex}</p>"
            cuerpo += f"<p><strong>Estado actual:</strong> {estado}</p>"
            
            # Comprobantes
            comprobantes = solicitud.get('comprobantes', [])
            comprobantes_validos = [c for c in comprobantes if c.get('es_valido') and not c.get('es_duplicado')]
            
            cuerpo += "<p><strong>Resumen de comprobantes:</strong></p>"
            cuerpo += "<ul>"
            cuerpo += f"<li>Total comprobantes: {len(comprobantes_validos)}</li>"
            
            for j, comp in enumerate(comprobantes_validos, 1):
                monto = comp.get('monto_detectado', 0)
                cuenta = comp.get('cuenta_detectada', {})
                clabe = cuenta.get('clabe', 'N/A') if cuenta else 'N/A'
                cuerpo += f"<li>Comprobante {j}: ${monto:,.2f} – Cuenta destino: STP {clabe}</li>"
            
            total_comp = sum(c.get('monto_detectado', 0) for c in comprobantes_validos)
            cuerpo += f"<li><strong>→ Total depósitos detectados: ${total_comp:,.2f}</strong></li>"
            cuerpo += "</ul>"
            
            # Resumen financiero (solo lo que Tesorería necesita)
            # NO se debe mostrar el margen/utilidad MBco
            total_dep = solicitud.get('total_comprobantes_validos', 0)
            comision_dns = solicitud.get('comision_cliente', 0)  # Es comisión DNS (al proveedor), no al cliente
            monto_ligas = solicitud.get('monto_ligas', 0)
            n_ligas = solicitud.get('cantidad_ligas_reportada', 0)
            
            cuerpo += "<p><strong>Resumen financiero para Tesorería:</strong></p>"
            cuerpo += "<ul>"
            cuerpo += f"<li>Total depósitos recibidos: ${total_dep:,.2f}</li>"
            cuerpo += f"<li>Monto a enviar en ligas (capital a proveedor): ${monto_ligas:,.2f}</li>"
            cuerpo += f"<li>Comisión DNS (a proveedor): ${comision_dns:,.2f}</li>"
            cuerpo += "</ul>"
            
            # Resumen layout - SOLO información de proveedor
            cuerpo += "<p><strong>Resumen de dispersión al proveedor:</strong></p>"
            cuerpo += "<ul>"
            cuerpo += f"<li>Transferencias de capital (ligas): {n_ligas}</li>"
            cuerpo += f"<li>Monto total capital: ${monto_ligas:,.2f}</li>"
            cuerpo += f"<li>Transferencias de comisión DNS: 1</li>"
            cuerpo += f"<li>Monto comisión DNS: ${comision_dns:,.2f}</li>"
            cuerpo += f"<li><strong>Total a dispersar al proveedor: ${monto_ligas + comision_dns:,.2f}</strong></li>"
            cuerpo += "</ul>"
            cuerpo += "<p><em>Nota: Los destinatarios de todas las transferencias son cuentas del proveedor (ver CSV adjunto).</em></p>"
            
            cuerpo += "</div>"
        
        # Resumen global
        cuerpo += "<hr>"
        cuerpo += "<div style='margin: 20px 0; padding: 15px; background: #e7f3ff; border: 2px solid #2196F3;'>"
        cuerpo += "<h3>Resumen del lote:</h3>"
        cuerpo += "<ul>"
        cuerpo += f"<li><strong>Solicitudes incluidas:</strong> {lote_info['n_solicitudes']}</li>"
        cuerpo += f"<li><strong>Total depósitos del lote:</strong> ${lote_info['total_depositos']:,.2f}</li>"
        cuerpo += f"<li><strong>Total capital a dispersar:</strong> ${lote_info['total_capital']:,.2f}</li>"
        cuerpo += f"<li><strong>Total comisión:</strong> ${lote_info['total_comision']:,.2f}</li>"
        cuerpo += "</ul>"
        cuerpo += "<p><em>Se adjunta layout CSV listo para dispersión.</em></p>"
        cuerpo += "</div>"
        
        cuerpo += "</body></html>"
        
        return cuerpo
    
    async def _notificar_telegram_tesoreria(self, lote_info: Dict, solicitudes: List[Dict]):
        """Notifica a Tesorería por Telegram"""
        logger.info(f"[Tesorería] Notificando por Telegram a usuarios con recibe_alertas_tesoreria")
        
        # Obtener usuarios de Tesorería
        from usuarios_repo import usuarios_repo
        usuarios = await usuarios_repo.obtener_usuarios_por_permiso('recibe_alertas_tesoreria', True)
        
        if not usuarios:
            logger.warning(f"[Tesorería] No hay usuarios con permiso recibe_alertas_tesoreria")
            return
        
        # Construir mensaje
        fecha_str = lote_info['fecha_corte'].strftime('%Y-%m-%d %H:%M UTC')
        
        mensaje = "🧾 **Nuevo lote NetCash para Tesorería**\n\n"
        mensaje += f"⏱ **Corte:** {fecha_str}\n"
        mensaje += f"📦 **Solicitudes incluidas:** {lote_info['n_solicitudes']}\n"
        mensaje += f"💰 **Total depósitos:** ${lote_info['total_depositos']:,.2f}\n"
        mensaje += f"💸 **Total capital a dispersar:** ${lote_info['total_capital']:,.2f}\n"
        mensaje += f"🧮 **Total comisión:** ${lote_info['total_comision']:,.2f}\n\n"
        mensaje += "**Detalle:**\n"
        
        for solicitud in solicitudes[:10]:  # Mostrar máximo 10 en Telegram
            folio_mbco = solicitud.get('folio_mbco', 'N/A')
            cliente = solicitud.get('cliente_nombre', 'N/A')
            beneficiario = solicitud.get('beneficiario_reportado', 'N/A')
            total_dep = solicitud.get('total_comprobantes_validos', 0)
            
            # Truncar nombres si son muy largos
            cliente_short = cliente[:20] + "..." if len(cliente) > 20 else cliente
            beneficiario_short = beneficiario[:20] + "..." if len(beneficiario) > 20 else beneficiario
            
            mensaje += f"• MBco: {folio_mbco}\n"
            mensaje += f"  Cliente: {cliente_short}\n"
            mensaje += f"  Beneficiario: {beneficiario_short}\n"
            mensaje += f"  Depósitos: ${total_dep:,.2f}\n\n"
        
        if len(solicitudes) > 10:
            mensaje += f"... y {len(solicitudes) - 10} operación(es) más\n\n"
        
        mensaje += f"✅ Se envió correo a Tesorería con layout CSV adjunto.\n"
        mensaje += f"📧 Revisa tu correo para el archivo de dispersión completo."
        
        # Enviar a cada usuario
        errores_envio = 0
        enviados_exitosos = 0
        
        for usuario in usuarios:
            telegram_id = usuario.get('telegram_id')
            nombre_usuario = usuario.get('nombre', 'Usuario sin nombre')
            
            if not telegram_id:
                logger.warning(f"[Tesorería] Usuario {nombre_usuario} no tiene telegram_id configurado")
                continue
            
            try:
                # Importar el bot de proceso de servidor
                # NOTA: El bot corre en telegram_bot.py como proceso separado
                # Para enviar desde aquí, necesitamos acceder al bot vía HTTP API
                import aiohttp
                
                bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
                if not bot_token:
                    logger.error("[Tesorería] TELEGRAM_BOT_TOKEN no configurado")
                    errores_envio += 1
                    continue
                
                # Enviar mensaje directamente vía Telegram Bot API
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    'chat_id': telegram_id,
                    'text': mensaje,
                    'parse_mode': 'Markdown'
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as response:
                        if response.status == 200:
                            logger.info(f"[Tesorería] ✅ Notificación enviada a {nombre_usuario} (telegram_id: {telegram_id})")
                            enviados_exitosos += 1
                        else:
                            error_text = await response.text()
                            logger.error(f"[Tesorería] ❌ Error enviando a {nombre_usuario}: {response.status} - {error_text}")
                            errores_envio += 1
                
            except Exception as e:
                logger.error(f"[Tesorería] Error notificando a {nombre_usuario}: {str(e)}")
                errores_envio += 1
        
        logger.info(f"[Tesorería] Notificaciones completadas: {enviados_exitosos} exitosos, {errores_envio} errores")


# Instancia global
tesoreria_service = TesoreriaService()
