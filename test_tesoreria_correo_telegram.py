"""
Script para mostrar cómo se ven el correo y mensaje de Telegram de Tesorería
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone

async def mostrar_ejemplo():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['netcash_mbco']
    
    # Buscar un lote de ejemplo
    lote = await db.lotes_tesoreria.find_one({}, {"_id": 0}, sort=[("fecha_corte", -1)])
    
    if not lote:
        print("❌ No hay lotes de tesorería en la BD")
        client.close()
        return
    
    # Obtener solicitudes del lote
    solicitud_ids = lote.get('solicitudes_ids', [])
    solicitudes = await db.solicitudes_netcash.find(
        {"id": {"$in": solicitud_ids}},
        {"_id": 0}
    ).to_list(100)
    
    print("=" * 80)
    print("EJEMPLO DE CORREO A TESORERÍA")
    print("=" * 80)
    print()
    print(f"📧 Destinatario: {os.getenv('TESORERIA_TEST_EMAIL', 'tesoreria@example.com')}")
    print(f"📋 Asunto: NetCash – Lote {lote.get('id_lote_mbco', 'N/A')} – {lote.get('fecha_corte', datetime.now()).strftime('%Y-%m-%d %H:%M')} – {lote.get('n_solicitudes', 0)} solicitudes")
    print()
    print("-" * 80)
    print("CUERPO DEL CORREO (HTML):")
    print("-" * 80)
    print()
    print("═══════════════════════════════════════")
    print("   Lote de Tesorería NetCash")
    print("═══════════════════════════════════════")
    print()
    print(f"ID Lote interno: {lote.get('id', 'N/A')}")
    print(f"ID Lote MBco:    {lote.get('id_lote_mbco', 'N/A')}")
    print(f"Fecha/Hora:      {lote.get('fecha_corte', datetime.now()).strftime('%Y-%m-%d %H:%M UTC')}")
    print()
    print("─────────────────────────────────────────")
    
    # Mostrar 1 solicitud de ejemplo
    if solicitudes:
        sol = solicitudes[0]
        print()
        print(f"▸ Solicitud 1 de {len(solicitudes)}")
        print(f"  Folio MBco: {sol.get('folio_mbco', 'N/A')}")
        print(f"  Cliente: {sol.get('cliente_nombre', 'N/A')}")
        print(f"  Beneficiario: {sol.get('beneficiario_reportado', 'N/A')}")
        print(f"  Total depósitos: ${sol.get('total_comprobantes_validos', 0):,.2f}")
        print(f"  Capital a dispersar: ${sol.get('monto_ligas', 0):,.2f}")
        print(f"  Comisión DNS (0.375%): ${sol.get('comision_dns_calculada', 0):,.2f}")
        print()
        if len(solicitudes) > 1:
            print(f"  ... y {len(solicitudes) - 1} solicitud(es) más")
    
    print()
    print("─────────────────────────────────────────")
    print("   RESUMEN DEL LOTE")
    print("─────────────────────────────────────────")
    print(f"• Solicitudes incluidas: {lote.get('n_solicitudes', 0)}")
    print(f"• Total depósitos: ${lote.get('total_depositos', 0):,.2f}")
    print(f"• Total capital a dispersar: ${lote.get('total_capital', 0):,.2f}")
    print(f"• Total comisión DNS (0.375%): ${lote.get('total_comision_dns', 0):,.2f}")
    print(f"• TOTAL A DISPERSAR AL PROVEEDOR: ${lote.get('total_capital', 0) + lote.get('total_comision_dns', 0):,.2f}")
    print()
    print("Se adjunta layout CSV listo para dispersión.")
    print("También se adjuntan los comprobantes de pago originales del cliente.")
    print()
    print("─────────────────────────────────────────")
    print("   📋 PASOS PARA TESORERÍA")
    print("─────────────────────────────────────────")
    print()
    print("1. Validar ingreso en firme")
    print("   • Entra a tu banca donde se reciben los depósitos NetCash.")
    print("   • Verifica que todos los depósitos estén en firme (no retenidos).")
    print("   • Si algún depósito NO está en firme, NO disperses ese caso.")
    print()
    print("2. Subir el layout a la banca para dispersión")
    print("   • Usa el archivo CSV adjunto (layout Fondeadora).")
    print("   • Verifica que los montos coincidan con el resumen.")
    print()
    print("3. Responder a este correo con los comprobantes de dispersión")
    print("   • Una vez realizadas las transferencias, responde a este correo.")
    print("   • Adjunta los comprobantes de pago (PDF/ZIP).")
    print("   • Confirma si todas las solicitudes quedaron dispersadas.")
    print()
    print("=" * 80)
    print()
    print()
    
    # Mensaje de Telegram
    print("=" * 80)
    print("EJEMPLO DE MENSAJE DE TELEGRAM PARA TOÑO")
    print("=" * 80)
    print()
    print("📬 Lote de Tesorería NetCash listo")
    print()
    print(f"🆔 ID Lote interno: {lote.get('id', 'N/A')}")
    print(f"🏷️ ID Lote MBco: {lote.get('id_lote_mbco', 'N/A')}")
    print()
    print(f"📦 Solicitudes incluidas en este lote: {lote.get('n_solicitudes', 0)}")
    print(f"💰 Total depósitos del lote: ${lote.get('total_depositos', 0):,.2f}")
    print(f"💸 Total capital a dispersar (ligas): ${lote.get('total_capital', 0):,.2f}")
    print(f"🧮 Total comisión DNS (0.375% capital): ${lote.get('total_comision_dns', 0):,.2f}")
    print()
    print("🔎 Revisa tu correo de Tesorería:")
    print("• Ahí encontrarás el detalle folio por folio,")
    print("• El layout CSV listo para dispersión,")
    print("• Y los comprobantes de pago enviados por el cliente.")
    print()
    print("(Todas las transferencias del layout van a cuentas del proveedor.)")
    print()
    print("Solicitudes en este lote:")
    for i, sol in enumerate(solicitudes[:5], 1):
        folio = sol.get('folio_mbco', 'N/A')
        cliente = sol.get('cliente_nombre', 'N/A')[:25]
        depositos = sol.get('total_comprobantes_validos', 0)
        print(f"• {folio} – {cliente} – ${depositos:,.2f}")
    
    if len(solicitudes) > 5:
        print(f"• ... y {len(solicitudes) - 5} solicitud(es) más")
    
    print()
    print("=" * 80)
    
    client.close()

if __name__ == "__main__":
    asyncio.run(mostrar_ejemplo())
