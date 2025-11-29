from typing import Dict
import logging

logger = logging.getLogger(__name__)


class CalculosService:
    """
    Servicio para realizar cálculos financieros de NetCash.
    """
    
    @staticmethod
    def calcular_operacion(
        monto_depositado_cliente: float,
        comision_cliente_porcentaje: float = 1.0,
        costo_proveedor_dns_porcentaje: float = 0.375
    ) -> Dict[str, float]:
        """
        Calcula todos los montos de una operación NetCash.
        
        FÓRMULAS CORRECTAS (según especificación del usuario):
        - importe_comision_cliente = monto_total_comprobantes * porcentaje_comision_cliente / 100
        - importe_costo_proveedor_dns = monto_total_comprobantes * 0.375 / 100
        - utilidad_neta = importe_comision_cliente - importe_costo_proveedor_dns
        
        Args:
            monto_depositado_cliente: Monto total de comprobantes
            comision_cliente_porcentaje: Porcentaje de comisión del cliente (default: 1.0%)
            costo_proveedor_dns_porcentaje: Porcentaje de costo proveedor DNS (default: 0.375%)
            
        Returns:
            Diccionario con todos los cálculos
        """
        try:
            # PASO 1: Calcular importe de comisión al cliente
            # importe_comision_cliente = monto_total_comprobantes * porcentaje_comision_cliente / 100
            importe_comision_cliente = monto_depositado_cliente * comision_cliente_porcentaje / 100
            
            # PASO 2: Calcular importe de costo proveedor DNS
            # importe_costo_proveedor_dns = monto_total_comprobantes * 0.375 / 100
            importe_costo_proveedor_dns = monto_depositado_cliente * costo_proveedor_dns_porcentaje / 100
            
            # PASO 3: Calcular utilidad neta
            # utilidad_neta = importe_comision_cliente - importe_costo_proveedor_dns
            utilidad_neta = importe_comision_cliente - importe_costo_proveedor_dns
            
            resultado = {
                "monto_total_comprobantes": round(monto_depositado_cliente, 2),
                "porcentaje_comision_cliente": comision_cliente_porcentaje,
                "importe_comision_cliente": round(importe_comision_cliente, 2),
                "porcentaje_costo_proveedor_dns": costo_proveedor_dns_porcentaje,
                "importe_costo_proveedor_dns": round(importe_costo_proveedor_dns, 2),
                "utilidad_neta": round(utilidad_neta, 2)
            }
            
            logger.info(f"Cálculo completado: {resultado}")
            return resultado
            
        except Exception as e:
            logger.error(f"Error en cálculo: {str(e)}")
            raise
    
    @staticmethod
    def particionar_monto(monto_total: float, limite_maximo: float = 350000.00) -> list:
        """
        Particiona un monto en transferencias que no excedan el límite.
        Las particiones varían entre 300,000 y 349,999.99 para evitar patrones.
        
        Args:
            monto_total: Monto total a particionar
            limite_maximo: Límite máximo por transferencia
            
        Returns:
            Lista de montos particionados
        """
        if monto_total <= limite_maximo:
            return [round(monto_total, 2)]
        
        particiones = []
        restante = monto_total
        
        import random
        
        while restante > limite_maximo:
            # Generar monto aleatorio entre 300,000 y 349,999
            monto_particion = random.uniform(300000.00, min(349999.99, restante - 1))
            monto_particion = round(monto_particion, 2)
            
            particiones.append(monto_particion)
            restante -= monto_particion
        
        # Agregar el restante
        if restante > 0:
            particiones.append(round(restante, 2))
        
        logger.info(f"Monto {monto_total} particionado en {len(particiones)} transferencias")
        return particiones


# Instancia global del servicio
calculos_service = CalculosService()