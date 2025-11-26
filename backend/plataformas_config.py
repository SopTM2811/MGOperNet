"""Configuración de plataformas y cuentas para layouts"""
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Configuración de plataformas/cuentas disponibles
# SUPUESTO: Esta es una configuración inicial que Ana puede ajustar más tarde
PLATAFORMAS = [
    {
        "id": "netcash_stp",
        "empresa": "MBco",
        "nombre": "NetCash STP",
        "tipo_uso": "operaciones_netcash",  # cobranza, nómina, proveedores, IAS, valores, operaciones_netcash
        "costo_operacion": 8.50,  # Costo aproximado por operación en MXN
        "velocidad_acreditacion": "inmediato",  # inmediato, mismo_dia, siguiente_dia
        "limite_monto": 8000.0,  # Límite por operación
        "ventana_horaria": "24/7",  # Horario de operación
        "prioridad_recomendada": 1,  # 1=más recomendada, 5=menos recomendada
        "notas": "Principal plataforma para operaciones NetCash"
    },
    {
        "id": "bbva_cobranza",
        "empresa": "MBco",
        "nombre": "BBVA Cobranza",
        "tipo_uso": "cobranza",
        "costo_operacion": 5.00,
        "velocidad_acreditacion": "mismo_dia",
        "limite_monto": 50000.0,
        "ventana_horaria": "8:00-18:00",
        "prioridad_recomendada": 3,
        "notas": "Evitar usar para NetCash. Reservada para cobranza empresarial"
    },
    {
        "id": "santander_nomina",
        "empresa": "MBco",
        "nombre": "Santander Nómina",
        "tipo_uso": "nómina",
        "costo_operacion": 0.0,
        "velocidad_acreditacion": "siguiente_dia",
        "limite_monto": 100000.0,
        "ventana_horaria": "8:00-16:00",
        "prioridad_recomendada": 5,
        "notas": "USO EXCLUSIVO para nómina. NO usar para otros fines para evitar empalmes"
    },
    {
        "id": "banorte_proveedores",
        "empresa": "MBco",
        "nombre": "Banorte Proveedores",
        "tipo_uso": "proveedores",
        "costo_operacion": 3.50,
        "velocidad_acreditacion": "mismo_dia",
        "limite_monto": 200000.0,
        "ventana_horaria": "9:00-17:00",
        "prioridad_recomendada": 4,
        "notas": "Para pago a proveedores. Evitar mezclar con otros usos"
    }
]


class ConsejeroPlataformas:
    """Consejero para elegir la mejor plataforma/cuenta para un layout"""
    
    def __init__(self, plataformas: List[Dict[str, Any]] = None):
        self.plataformas = plataformas or PLATAFORMAS
    
    def recomendar_plataforma(
        self,
        tipo_operacion: str = "operaciones_netcash",
        monto_total: float = 0,
        urgencia: str = "normal",  # urgente, normal, puede_esperar
        empresa: str = "MBco"
    ) -> Dict[str, Any]:
        """
        Recomienda la mejor plataforma/cuenta basándose en criterios múltiples.
        
        Args:
            tipo_operacion: Tipo de operación (operaciones_netcash, nómina, proveedores, etc.)
            monto_total: Monto total de la operación
            urgencia: Nivel de urgencia (urgente, normal, puede_esperar)
            empresa: Empresa que realiza la operación
        
        Returns:
            Dict con la plataforma recomendada y la explicación
        """
        try:
            # Filtrar plataformas por empresa
            candidatas = [p for p in self.plataformas if p["empresa"] == empresa]
            
            if not candidatas:
                return {
                    "error": f"No se encontraron plataformas configuradas para {empresa}",
                    "recomendacion": None
                }
            
            # Scoring de plataformas
            scores = []
            
            for plataforma in candidatas:
                score = 0
                razones = []
                advertencias = []
                
                # CRITERIO 1: Coincidencia con tipo de uso (peso: 40 puntos)
                if plataforma["tipo_uso"] == tipo_operacion:
                    score += 40
                    razones.append(f"✅ Diseñada específicamente para {tipo_operacion}")
                else:
                    # Penalización fuerte si se intenta usar cuenta de uso exclusivo para otro fin
                    if plataforma["tipo_uso"] in ["nómina", "cobranza"] and tipo_operacion != plataforma["tipo_uso"]:
                        score -= 50
                        advertencias.append(
                            f"⚠️ ALTO RIESGO: Esta cuenta es de uso exclusivo para {plataforma['tipo_uso']}. "
                            f"Usarla para {tipo_operacion} puede causar empalmes graves en conciliación."
                        )
                    else:
                        score -= 10
                        advertencias.append(f"⚠️ No es el uso principal (diseñada para {plataforma['tipo_uso']})")
                
                # CRITERIO 2: Límite de monto (peso: 20 puntos)
                if monto_total <= plataforma["limite_monto"]:
                    score += 20
                    razones.append(f"✅ Monto dentro del límite (${plataforma['limite_monto']:,.2f})")
                else:
                    score -= 30
                    advertencias.append(
                        f"❌ Monto ${monto_total:,.2f} excede límite de ${plataforma['limite_monto']:,.2f}"
                    )
                
                # CRITERIO 3: Urgencia y velocidad (peso: 20 puntos)
                if urgencia == "urgente" and plataforma["velocidad_acreditacion"] == "inmediato":
                    score += 20
                    razones.append("✅ Acreditación inmediata ideal para operación urgente")
                elif urgencia == "normal" and plataforma["velocidad_acreditacion"] in ["inmediato", "mismo_dia"]:
                    score += 15
                    razones.append(f"✅ Acreditación {plataforma['velocidad_acreditacion']} adecuada")
                elif urgencia == "puede_esperar":
                    score += 10
                    razones.append("✅ Velocidad suficiente para operación no urgente")
                
                # CRITERIO 4: Costo (peso: 10 puntos)
                if plataforma["costo_operacion"] < 5.0:
                    score += 10
                    razones.append(f"✅ Bajo costo (${plataforma['costo_operacion']:.2f} por operación)")
                elif plataforma["costo_operacion"] < 10.0:
                    score += 5
                
                # CRITERIO 5: Prioridad configurada (peso: 10 puntos)
                score += (6 - plataforma["prioridad_recomendada"]) * 2
                
                scores.append({
                    "plataforma": plataforma,
                    "score": score,
                    "razones": razones,
                    "advertencias": advertencias
                })
            
            # Ordenar por score
            scores.sort(key=lambda x: x["score"], reverse=True)
            
            mejor = scores[0]
            
            # Construir explicación
            explicacion = f"**Plataforma recomendada: {mejor['plataforma']['nombre']}**\n\n"
            
            if mejor['razones']:
                explicacion += "**Razones:**\n"
                for razon in mejor['razones']:
                    explicacion += f"• {razon}\n"
            
            if mejor['advertencias']:
                explicacion += "\n**Advertencias:**\n"
                for advertencia in mejor['advertencias']:
                    explicacion += f"• {advertencia}\n"
            
            explicacion += f"\n**Costo estimado:** ${mejor['plataforma']['costo_operacion']:.2f} por operación\n"
            explicacion += f"**Ventana horaria:** {mejor['plataforma']['ventana_horaria']}\n"
            
            # Si hay alternativas viables, mencionarlas
            if len(scores) > 1 and scores[1]['score'] > 0:
                explicacion += f"\n**Alternativa:** {scores[1]['plataforma']['nombre']} (score: {scores[1]['score']})\n"
            
            return {
                "plataforma_id": mejor['plataforma']['id'],
                "plataforma": mejor['plataforma'],
                "score": mejor['score'],
                "explicacion": explicacion,
                "advertencias": mejor['advertencias'],
                "apto": mejor['score'] > 0 and not any("ALTO RIESGO" in adv for adv in mejor['advertencias'])
            }
            
        except Exception as e:
            logger.error(f"Error recomendando plataforma: {str(e)}")
            return {
                "error": str(e),
                "recomendacion": None
            }


# Instancia global
consejero_plataformas = ConsejeroPlataformas()
