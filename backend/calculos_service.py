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
        
        FÓRMULAS (alineadas con modelo CalculosNetCash):
        - comision_cliente_cobrada = monto_depositado_cliente * comision_cliente_porcentaje / 100
        - comision_proveedor = monto_depositado_cliente * comision_proveedor_porcentaje / 100
        - capital_netcash = monto_depositado_cliente - comision_cliente_cobrada
        - total_egreso = capital_netcash + comision_proveedor
        
        Args:
            monto_depositado_cliente: Monto total de comprobantes válidos
            comision_cliente_porcentaje: Porcentaje de comisión del cliente (default: 1.0%)
            costo_proveedor_dns_porcentaje: Porcentaje de costo proveedor DNS (default: 0.375%)
            
        Returns:
            Diccionario con campos alineados al modelo CalculosNetCash:
            - monto_depositado_cliente
            - comision_cliente_porcentaje
            - comision_cliente_cobrada
            - comision_proveedor_porcentaje
            - comision_proveedor
            - capital_netcash
            - total_egreso
        """
        try:
            # PASO 1: Calcular comisión cobrada al cliente
            comision_cliente_cobrada = monto_depositado_cliente * comision_cliente_porcentaje / 100
            
            # PASO 2: Calcular comisión del proveedor
            comision_proveedor = monto_depositado_cliente * costo_proveedor_dns_porcentaje / 100
            
            # PASO 3: Calcular capital NetCash (monto - comisión cliente)
            capital_netcash = monto_depositado_cliente - comision_cliente_cobrada
            
            # PASO 4: Calcular total egreso (capital + comisión proveedor)
            total_egreso = capital_netcash + comision_proveedor
            
            # Resultado con nombres alineados al modelo CalculosNetCash de models.py
            resultado = {
                "monto_depositado_cliente": round(monto_depositado_cliente, 2),
                "comision_cliente_porcentaje": comision_cliente_porcentaje,
                "comision_cliente_cobrada": round(comision_cliente_cobrada, 2),
                "comision_proveedor_porcentaje": costo_proveedor_dns_porcentaje,
                "comision_proveedor": round(comision_proveedor, 2),
                "capital_netcash": round(capital_netcash, 2),
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