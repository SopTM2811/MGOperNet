"""
Test para reproducir el bug con comprobante_1045000.pdf
Bug reportado: Al hacer clic en "Continuar" después de subir el PDF, aparece error genérico
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from netcash_service import netcash_service
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s:%(message)s'
)

async def test_bug_continuar_paso1():
    """
    Reproducir el flujo completo de continuar_desde_paso1 con la solicitud problemática
    """
    print("=" * 70)
    print("🧪 TEST: Reproducir bug con comprobante_1045000.pdf")
    print("=" * 70)
    
    solicitud_id = "nc-1764555486884"
    
    try:
        print(f"\n📋 PASO 1: Obtener solicitud {solicitud_id}")
        solicitud = await netcash_service.obtener_solicitud(solicitud_id)
        print(f"✅ Solicitud obtenida")
        print(f"   Cliente: {solicitud.get('cliente_id')}")
        print(f"   Estado: {solicitud.get('estado')}")
        
        comprobantes = solicitud.get("comprobantes", [])
        print(f"   Comprobantes: {len(comprobantes)}")
        
        for idx, comp in enumerate(comprobantes, 1):
            print(f"\n   Comprobante #{idx}:")
            print(f"     Nombre: {comp.get('nombre_archivo')}")
            print(f"     Válido: {comp.get('es_valido')}")
            print(f"     Monto: {comp.get('monto_detectado')} (tipo: {type(comp.get('monto_detectado')).__name__})")
        
        # PASO 2: Validar solicitud completa (línea 503 del handler)
        print(f"\n📋 PASO 2: Validar solicitud completa")
        todas_validas, validaciones = await netcash_service.validar_solicitud_completa(solicitud_id)
        print(f"✅ Validación completada")
        print(f"   Todas válidas: {todas_validas}")
        print(f"   Validaciones:")
        for campo, val in validaciones.items():
            status = "✅" if val.get("valido") else "❌"
            print(f"     {status} {campo}: {val.get('razon')}")
        
        # PASO 3: Contar comprobantes válidos (línea 507)
        print(f"\n📋 PASO 3: Contar comprobantes válidos")
        comprobantes_validos = [c for c in comprobantes if c.get("es_valido", False)]
        comprobantes_duplicados = [c for c in comprobantes if c.get("es_duplicado", False)]
        print(f"✅ Comprobantes válidos: {len(comprobantes_validos)}")
        print(f"   Comprobantes duplicados: {len(comprobantes_duplicados)}")
        
        # PASO 4: Calcular total (líneas 567-578) - PUNTO CRÍTICO
        print(f"\n📋 PASO 4: Calcular total_depositado (PUNTO CRÍTICO)")
        total_depositado = 0.0
        resumen_comprobantes = []
        
        for comp in comprobantes_validos:
            monto = comp.get("monto_detectado")
            nombre = comp.get("nombre_archivo", "Sin nombre")
            print(f"   Procesando: {nombre}")
            print(f"     Monto raw: {monto}")
            print(f"     Monto tipo: {type(monto)}")
            
            if monto and monto > 0:
                print(f"     Monto válido, sumando...")
                try:
                    total_depositado += monto
                    print(f"     Total acumulado: {total_depositado}")
                    resumen_comprobantes.append(f"  • {nombre}: ${monto:,.2f}")
                    print(f"     Línea resumen: {resumen_comprobantes[-1]}")
                except Exception as e:
                    print(f"     ❌ ERROR al sumar o formatear: {e}")
                    raise
            else:
                resumen_comprobantes.append(f"  • {nombre}: (Monto no detectado)")
        
        print(f"\n✅ Total calculado: {total_depositado}")
        print(f"   Tipo: {type(total_depositado)}")
        
        # PASO 5: Construir mensaje de resumen (líneas 579-606) - OTRO PUNTO CRÍTICO
        print(f"\n📋 PASO 5: Construir mensaje de resumen")
        try:
            mensaje_resumen = "✅ **Comprobantes validados correctamente**\n\n"
            mensaje_resumen += f"📊 **Resumen de depósitos detectados:**\n\n"
            
            if len(resumen_comprobantes) > 0:
                mensaje_resumen += "\n".join(resumen_comprobantes)
                mensaje_resumen += f"\n\n💰 **Total de depósitos detectados:** ${total_depositado:,.2f}\n"
                print(f"✅ Mensaje construido correctamente:")
                print(mensaje_resumen)
            else:
                mensaje_resumen += "No se pudo detectar monto en los comprobantes.\n\n"
            
            mensaje_resumen += "\n"
            mensaje_resumen += "Continuaremos con el siguiente paso..."
            
        except Exception as e:
            print(f"❌ ERROR al construir mensaje: {e}")
            import traceback
            print(traceback.format_exc())
            raise
        
        # PASO 6: Mostrar paso 2 beneficiarios (línea 614) - SIGUIENTE PUNTO
        print(f"\n📋 PASO 6: Simular _mostrar_paso2_beneficiarios")
        print(f"   Obteniendo beneficiarios frecuentes...")
        
        cliente_id = solicitud.get("cliente_id")
        mongo_url = os.getenv('MONGO_URL')
        db_name = os.getenv('DB_NAME', 'netcash_mbco')
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        estados_validos = ["lista_para_mbc", "en_proceso_mbc", "completada"]
        
        solicitudes_historicas = await db.solicitudes_netcash.find(
            {
                "cliente_id": cliente_id,
                "estado": {"$in": estados_validos},
                "beneficiario_reportado": {"$exists": True, "$ne": None, "$ne": ""},
                "idmex_reportado": {"$exists": True, "$ne": None, "$ne": ""}
            },
            {"_id": 0, "beneficiario_reportado": 1, "idmex_reportado": 1, "created_at": 1}
        ).sort("created_at", -1).limit(20).to_list(20)
        
        print(f"✅ Beneficiarios históricos encontrados: {len(solicitudes_historicas)}")
        
        # Deduplicar
        beneficiarios_frecuentes = {}
        for sol in solicitudes_historicas:
            benef = sol.get("beneficiario_reportado")
            idmex = sol.get("idmex_reportado")
            
            if not benef or not idmex:
                continue
            
            key = f"{benef}_{idmex}"
            if key not in beneficiarios_frecuentes:
                beneficiarios_frecuentes[key] = {
                    "beneficiario": benef,
                    "idmex": idmex,
                    "created_at": sol.get("created_at")
                }
        
        frecuentes_list = list(beneficiarios_frecuentes.values())
        frecuentes_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        frecuentes = frecuentes_list[:3]
        
        print(f"✅ Beneficiarios únicos frecuentes: {len(frecuentes)}")
        
        # Construir mensaje paso 2
        mensaje_paso2 = "👤 **Paso 2 de 3: Beneficiario + IDMEX**\n\n"
        
        if frecuentes:
            mensaje_paso2 += "🔁 **Beneficiarios frecuentes:**\n\n"
            for idx, freq in enumerate(frecuentes, 1):
                mensaje_paso2 += f"{idx}. {freq['beneficiario']} – IDMEX: {freq['idmex']}\n"
            
            mensaje_paso2 += "\nPuedes elegir uno de la lista o escribir un beneficiario nuevo.\n"
        else:
            mensaje_paso2 += "Por favor envíame el **nombre completo del beneficiario**.\n\n"
        
        print(f"✅ Mensaje paso 2 construido correctamente")
        
        print(f"\n" + "=" * 70)
        print(f"🎉 TEST COMPLETADO SIN ERRORES")
        print(f"=" * 70)
        print(f"\n✅ CONCLUSIÓN: El código funciona correctamente con el monto $1,045,000.00")
        print(f"   No se detectó ningún error en el flujo completo.")
        print(f"   El bug reportado podría ser:")
        print(f"   1. Un problema específico del contexto de Telegram (update/query)")
        print(f"   2. Un problema de concurrencia o timing")
        print(f"   3. Un problema en una versión anterior del código que ya fue corregido")
        print(f"   4. Un problema con el estado de la sesión del usuario en Telegram")
        
    except Exception as e:
        print(f"\n" + "=" * 70)
        print(f"❌ ERROR ENCONTRADO - ESTO ES LO QUE CAUSA EL BUG")
        print(f"=" * 70)
        print(f"Tipo de error: {type(e).__name__}")
        print(f"Mensaje: {str(e)}")
        import traceback
        print(f"\nStack trace completo:")
        print(traceback.format_exc())
        print(f"\n🔍 Este es el error que el usuario ve como mensaje genérico")

if __name__ == "__main__":
    asyncio.run(test_bug_continuar_paso1())
