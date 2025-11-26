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
        comision_cliente_porcentaje: float,
        comision_proveedor_porcentaje: float = 0.00375
    ) -> Dict[str, float]:
        """
        Calcula todos los montos de una operación NetCash.
        
        Args:
            monto_depositado_cliente: Monto total depositado por el cliente
            comision_cliente_porcentaje: Porcentaje de comisión del cliente (ej: 0.0065 = 0.65%)
            comision_proveedor_porcentaje: Porcentaje de comisión del proveedor (default: 0.00375 = 0.375%)
            
        Returns:
            Diccionario con todos los cálculos
        """
        try:
            # Fórmula principal: capital_netcash = monto_depositado / (1 + comision_cliente_porcentaje)
            capital_netcash = monto_depositado_cliente / (1 + comision_cliente_porcentaje)
            
            # Comisión cobrada al cliente
            comision_cliente_cobrada = monto_depositado_cliente - capital_netcash
            
            # Comisión a pagar al proveedor
            comision_proveedor = capital_netcash * comision_proveedor_porcentaje
            
            # Total de egreso (lo que MBco paga al proveedor)
            total_egreso = capital_netcash + comision_proveedor
            
            resultado = {
                "monto_depositado_cliente": round(monto_depositado_cliente, 2),
                "comision_cliente_porcentaje": comision_cliente_porcentaje,
                "capital_netcash": round(capital_netcash, 2),
                "comision_cliente_cobrada": round(comision_cliente_cobrada, 2),
                "comision_proveedor_porcentaje": comision_proveedor_porcentaje,
                "comision_proveedor": round(comision_proveedor, 2),
                "total_egreso": round(total_egreso, 2)
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