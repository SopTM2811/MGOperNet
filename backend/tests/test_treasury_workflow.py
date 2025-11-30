#!/usr/bin/env python3
"""
Test completo del Treasury Workflow (Proceso de Tesorería) para NetCash

Este test verifica el flujo automatizado que se ejecuta cada 15 minutos:
1. Busca solicitudes con estado 'orden_interna_generada'
2. Las procesa en lotes
3. Genera CSV con layout correcto
4. Cambia estado a 'enviado_a_tesoreria'
5. Crea registro en lotes_tesoreria
"""

import asyncio
import os
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal
import csv
from io import StringIO

# Agregar el directorio backend al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv('/app/backend/.env')

class TreasuryWorkflowTest:
    """Test completo del flujo de Tesorería NetCash"""
    
    def __init__(self):
        self.mongo_client = None
        self.db = None
        self.test_solicitudes_ids = []
        self.test_lote_id = None
        
        # Variables de entorno requeridas
        self.capital_clabe = os.getenv('NETCASH_CAPITAL_CLABE_ORIGEN', '646180000000000000')
        self.comision_clabe = os.getenv('NETCASH_COMISION_CLABE_ORIGEN', '646180000000000001')
        self.tesoreria_email = os.getenv('TESORERIA_TEST_EMAIL', 'dfgalezzo@hotmail.com')
        
        logger.info(f"[Test] Variables de entorno:")
        logger.info(f"[Test] Capital CLABE: {self.capital_clabe}")
        logger.info(f"[Test] Comisión CLABE: {self.comision_clabe}")
        logger.info(f"[Test] Email Tesorería: {self.tesoreria_email}")
    
    async def setup(self):
        """Configuración inicial del test"""
        logger.info("🔧 [Test] Configurando test...")
        
        # Conectar a MongoDB
        mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
        db_name = os.getenv('DB_NAME', 'netcash_mbco')
        
        self.mongo_client = AsyncIOMotorClient(mongo_url)
        self.db = self.mongo_client[db_name]
        
        logger.info("✅ [Test] Setup completado")
    
    async def cleanup(self):
        """Limpieza final del test"""
        logger.info("🧹 [Test] Limpiando datos de prueba...")
        
        try:
            # Eliminar solicitudes de prueba
            if self.test_solicitudes_ids:
                result = await self.db.solicitudes_netcash.delete_many(
                    {"id": {"$in": self.test_solicitudes_ids}}
                )
                logger.info(f"[Test] Eliminadas {result.deleted_count} solicitudes de prueba")
            
            # Eliminar lote de prueba
            if self.test_lote_id:
                result = await self.db.lotes_tesoreria.delete_one({"id": self.test_lote_id})
                logger.info(f"[Test] Eliminado lote de prueba: {self.test_lote_id}")
            
            # Cerrar conexión MongoDB
            if self.mongo_client:
                self.mongo_client.close()
                
            logger.info("✅ [Test] Cleanup completado")
            
        except Exception as e:
            logger.error(f"❌ [Test] Error en cleanup: {str(e)}")
    
    async def crear_solicitudes_prueba(self):
        """
        Crea 2 solicitudes de prueba con estado 'orden_interna_generada'
        
        Solicitud 1: Cliente "TEST CLIENTE A", Beneficiario "JUAN PÉREZ", 1 liga, $5000 total, $50 comisión, $4950 capital
        Solicitud 2: Cliente "TEST CLIENTE B", Beneficiario "MARÍA GARCÍA", 3 ligas, $12000 total, $120 comisión, $11880 capital
        """
        logger.info("📝 [Test] Creando solicitudes de prueba...")
        
        timestamp = int(datetime.now(timezone.utc).timestamp())
        
        # Solicitud 1
        solicitud_1 = {
            "id": f"test-treasury-1-{timestamp}",
            "folio_mbco": f"TEST-001-T-{timestamp % 100}",
            "canal": "telegram",
            "cliente_id": f"test-cliente-a-{timestamp}",
            "cliente_nombre": "TEST CLIENTE A",
            "beneficiario_reportado": "JUAN PÉREZ",
            "idmex_reportado": "PERJ850315HDFRZN01",
            "cantidad_ligas_reportada": 1,
            "total_comprobantes_validos": 5000.00,
            "comision_cliente": 50.00,  # 1% de 5000
            "monto_ligas": 4950.00,     # 5000 - 50
            "estado": "orden_interna_generada",
            "comprobantes": [
                {
                    "monto_detectado": 5000.00,
                    "es_valido": True,
                    "es_duplicado": False,
                    "cuenta_detectada": {
                        "clabe": "646180139409481462",
                        "banco": "STP",
                        "beneficiario": "THABYETHA SA"
                    }
                }
            ],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Solicitud 2
        solicitud_2 = {
            "id": f"test-treasury-2-{timestamp}",
            "folio_mbco": f"TEST-002-T-{timestamp % 100}",
            "canal": "telegram",
            "cliente_id": f"test-cliente-b-{timestamp}",
            "cliente_nombre": "TEST CLIENTE B",
            "beneficiario_reportado": "MARÍA GARCÍA",
            "idmex_reportado": "GARM900215MDFRZR02",
            "cantidad_ligas_reportada": 3,
            "total_comprobantes_validos": 12000.00,
            "comision_cliente": 120.00,  # 1% de 12000
            "monto_ligas": 11880.00,     # 12000 - 120
            "estado": "orden_interna_generada",
            "comprobantes": [
                {
                    "monto_detectado": 6000.00,
                    "es_valido": True,
                    "es_duplicado": False,
                    "cuenta_detectada": {
                        "clabe": "646180139409481462",
                        "banco": "STP",
                        "beneficiario": "THABYETHA SA"
                    }
                },
                {
                    "monto_detectado": 6000.00,
                    "es_valido": True,
                    "es_duplicado": False,
                    "cuenta_detectada": {
                        "clabe": "646180139409481462",
                        "banco": "STP",
                        "beneficiario": "THABYETHA SA"
                    }
                }
            ],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Insertar en BD
        await self.db.solicitudes_netcash.insert_many([solicitud_1, solicitud_2])
        
        self.test_solicitudes_ids = [solicitud_1["id"], solicitud_2["id"]]
        
        logger.info(f"✅ [Test] Solicitudes creadas:")
        logger.info(f"   - Solicitud 1: {solicitud_1['id']} - {solicitud_1['cliente_nombre']} - {solicitud_1['beneficiario_reportado']} - 1 liga - $5,000")
        logger.info(f"   - Solicitud 2: {solicitud_2['id']} - {solicitud_2['cliente_nombre']} - {solicitud_2['beneficiario_reportado']} - 3 ligas - $12,000")
        
        return [solicitud_1, solicitud_2]
    
    async def ejecutar_proceso_tesoreria(self):
        """Ejecuta el proceso de tesorería directamente"""
        logger.info("⚙️ [Test] Ejecutando proceso de tesorería...")
        
        # Importar y ejecutar el servicio
        from tesoreria_service import tesoreria_service
        
        resultado = await tesoreria_service.procesar_lote_tesoreria()
        
        if resultado:
            self.test_lote_id = resultado.get('id')
            logger.info(f"✅ [Test] Proceso ejecutado. Lote creado: {self.test_lote_id}")
        else:
            logger.warning("⚠️ [Test] El proceso no retornó resultado (posiblemente no había solicitudes)")
        
        return resultado
    
    async def verificar_cambio_estados(self):
        """Verifica que las solicitudes cambiaron de estado a 'enviado_a_tesoreria'"""
        logger.info("🔍 [Test] Verificando cambio de estados...")
        
        solicitudes_actualizadas = await self.db.solicitudes_netcash.find(
            {"id": {"$in": self.test_solicitudes_ids}},
            {"_id": 0, "id": 1, "estado": 1, "lote_tesoreria_id": 1}
        ).to_list(10)
        
        estados_correctos = 0
        lotes_asignados = 0
        
        for solicitud in solicitudes_actualizadas:
            estado = solicitud.get("estado")
            lote_id = solicitud.get("lote_tesoreria_id")
            
            logger.info(f"   - Solicitud {solicitud['id']}: Estado = {estado}, Lote = {lote_id}")
            
            if estado == "enviado_a_tesoreria":
                estados_correctos += 1
            
            if lote_id == self.test_lote_id:
                lotes_asignados += 1
        
        if estados_correctos == 2:
            logger.info("✅ [Test] Ambas solicitudes cambiaron a estado 'enviado_a_tesoreria'")
        else:
            logger.error(f"❌ [Test] Solo {estados_correctos}/2 solicitudes cambiaron de estado")
            return False
        
        if lotes_asignados == 2:
            logger.info("✅ [Test] Ambas solicitudes tienen lote_tesoreria_id asignado")
        else:
            logger.error(f"❌ [Test] Solo {lotes_asignados}/2 solicitudes tienen lote asignado")
            return False
        
        return True
    
    async def verificar_lote_creado(self):
        """Verifica que se creó un nuevo lote en la colección lotes_tesoreria"""
        logger.info("🔍 [Test] Verificando lote creado...")
        
        if not self.test_lote_id:
            logger.error("❌ [Test] No hay lote_id para verificar")
            return False
        
        lote = await self.db.lotes_tesoreria.find_one(
            {"id": self.test_lote_id},
            {"_id": 0}
        )
        
        if not lote:
            logger.error(f"❌ [Test] Lote {self.test_lote_id} no encontrado en BD")
            return False
        
        logger.info("✅ [Test] Lote encontrado en BD:")
        logger.info(f"   - ID: {lote.get('id')}")
        logger.info(f"   - Solicitudes: {lote.get('n_solicitudes')}")
        logger.info(f"   - Total depósitos: ${lote.get('total_depositos', 0):,.2f}")
        logger.info(f"   - Total capital: ${lote.get('total_capital', 0):,.2f}")
        logger.info(f"   - Total comisión: ${lote.get('total_comision', 0):,.2f}")
        
        # Verificar datos correctos
        if lote.get('n_solicitudes') != 2:
            logger.error(f"❌ [Test] Número de solicitudes incorrecto: {lote.get('n_solicitudes')} (esperado: 2)")
            return False
        
        if lote.get('total_depositos') != 17000.00:  # 5000 + 12000
            logger.error(f"❌ [Test] Total depósitos incorrecto: ${lote.get('total_depositos')} (esperado: $17,000)")
            return False
        
        if lote.get('total_capital') != 16830.00:  # 4950 + 11880
            logger.error(f"❌ [Test] Total capital incorrecto: ${lote.get('total_capital')} (esperado: $16,830)")
            return False
        
        if lote.get('total_comision') != 170.00:  # 50 + 120
            logger.error(f"❌ [Test] Total comisión incorrecto: ${lote.get('total_comision')} (esperado: $170)")
            return False
        
        logger.info("✅ [Test] Todos los totales del lote son correctos")
        return True
    
    async def verificar_csv_generado(self):
        """Verifica que el CSV se generó con el layout correcto"""
        logger.info("🔍 [Test] Verificando generación de CSV...")
        
        # Generar CSV usando el mismo servicio
        from tesoreria_service import tesoreria_service
        
        # Obtener las solicitudes procesadas
        solicitudes = await self.db.solicitudes_netcash.find(
            {"id": {"$in": self.test_solicitudes_ids}},
            {"_id": 0}
        ).to_list(10)
        
        if len(solicitudes) != 2:
            logger.error(f"❌ [Test] No se encontraron las 2 solicitudes para generar CSV")
            return False
        
        # Generar CSV
        csv_content = await tesoreria_service.generar_layout_fondeadora(solicitudes)
        
        if not csv_content:
            logger.error("❌ [Test] No se generó contenido CSV")
            return False
        
        logger.info("✅ [Test] CSV generado correctamente")
        
        # Analizar contenido CSV
        csv_reader = csv.reader(StringIO(csv_content))
        rows = list(csv_reader)
        
        # Verificar header
        header = rows[0]
        expected_header = [
            'Clabe destinatario',
            'Nombre o razon social destinatario', 
            'Monto',
            'Concepto',
            'Email (opcional)',
            'Tags separados por comas (opcional)',
            'Comentario (opcional)'
        ]
        
        if header != expected_header:
            logger.error(f"❌ [Test] Header CSV incorrecto")
            logger.error(f"   Esperado: {expected_header}")
            logger.error(f"   Obtenido: {header}")
            return False
        
        logger.info("✅ [Test] Header CSV correcto")
        
        # Verificar filas de datos (sin header)
        data_rows = rows[1:]
        
        # Esperamos:
        # - Solicitud 1: 1 fila capital + 1 fila comisión = 2 filas
        # - Solicitud 2: 3 filas capital + 1 fila comisión = 4 filas
        # Total: 6 filas
        
        if len(data_rows) != 6:
            logger.error(f"❌ [Test] Número de filas incorrecto: {len(data_rows)} (esperado: 6)")
            return False
        
        logger.info("✅ [Test] Número de filas CSV correcto (6 filas)")
        
        # Verificar conceptos usan formato correcto (guiones reemplazados por 'x')
        conceptos_encontrados = []
        for row in data_rows:
            concepto = row[3]  # Columna de concepto
            conceptos_encontrados.append(concepto)
        
        logger.info("📋 [Test] Conceptos encontrados en CSV:")
        for concepto in conceptos_encontrados:
            logger.info(f"   - {concepto}")
        
        # Verificar que los conceptos usan 'x' en lugar de '-'
        conceptos_con_guiones = [c for c in conceptos_encontrados if '-' in c]
        if conceptos_con_guiones:
            logger.error(f"❌ [Test] Conceptos con guiones encontrados (deberían usar 'x'): {conceptos_con_guiones}")
            return False
        
        logger.info("✅ [Test] Todos los conceptos usan formato correcto (sin guiones)")
        
        # Verificar CLABEs de origen
        clabes_capital = [row[0] for row in data_rows if 'COMISION' not in row[3]]
        clabes_comision = [row[0] for row in data_rows if 'COMISION' in row[3]]
        
        # Todas las filas de capital deben usar capital_clabe
        if not all(clabe == self.capital_clabe for clabe in clabes_capital):
            logger.error(f"❌ [Test] CLABEs de capital incorrectas")
            logger.error(f"   Esperado: {self.capital_clabe}")
            logger.error(f"   Encontradas: {set(clabes_capital)}")
            return False
        
        # Todas las filas de comisión deben usar comision_clabe
        if not all(clabe == self.comision_clabe for clabe in clabes_comision):
            logger.error(f"❌ [Test] CLABEs de comisión incorrectas")
            logger.error(f"   Esperado: {self.comision_clabe}")
            logger.error(f"   Encontradas: {set(clabes_comision)}")
            return False
        
        logger.info("✅ [Test] CLABEs de origen correctas")
        logger.info(f"   - Capital: {len(clabes_capital)} filas con CLABE {self.capital_clabe}")
        logger.info(f"   - Comisión: {len(clabes_comision)} filas con CLABE {self.comision_clabe}")
        
        return True
    
    async def verificar_layout_csv(self, layout_csv: str):
        """Verifica que el layout CSV tenga el formato correcto y use cuentas de proveedor"""
        logger.info("🔍 [Test] Verificando layout CSV...")
        
        # Parse CSV
        lines = layout_csv.strip().split('\n')
        
        if len(lines) < 2:
            logger.error(f"❌ [Test] Layout CSV tiene solo {len(lines)} líneas")
            return False
        
        # Verificar header
        header = lines[0]
        expected_columns = [
            'Clabe destinatario',
            'Nombre o razon social destinatario',
            'Monto',
            'Concepto'
        ]
        
        for col in expected_columns:
            if col not in header:
                logger.error(f"❌ [Test] Columna faltante en header: {col}")
                return False
        
        # Verificar que hay al menos 6 filas (header + 4 capital + 2 comisión)
        if len(lines) < 7:
            logger.error(f"❌ [Test] Se esperaban al menos 7 líneas, se encontraron {len(lines)}")
            return False
        
        # Verificar que las filas de datos tienen el formato correcto
        import csv
        from io import StringIO
        
        reader = csv.DictReader(StringIO(layout_csv))
        rows = list(reader)
        
        capital_rows = 0
        comision_rows = 0
        
        # CLABEs esperadas del proveedor
        expected_capital_clabe = "012680001255709482"  # AFFORDABLE MEDICAL SERVICES SC
        expected_comision_clabe = "058680000012912655"  # Comercializadora Uetacop SA de CV
        expected_capital_beneficiario = "AFFORDABLE MEDICAL SERVICES SC"
        expected_comision_beneficiario = "COMERCIALIZADORA UETACOP SA DE CV"
        
        for row in rows:
            concepto = row.get('Concepto', '')
            monto = row.get('Monto', '')
            clabe = row.get('Clabe destinatario', '')
            beneficiario = row.get('Nombre o razon social destinatario', '')
            
            # Verificar formato de concepto (MBco XXXxXXXxXxXX)
            if not concepto.startswith('MBco '):
                logger.error(f"❌ [Test] Concepto inválido: {concepto}")
                return False
            
            # Verificar que el folio usa 'x' en lugar de '-'
            if concepto.count('-') > 0:
                logger.error(f"❌ [Test] Concepto usa guiones en lugar de 'x': {concepto}")
                return False
            
            # Verificar que los destinatarios son SIEMPRE del proveedor
            if 'COMISION' in concepto:
                comision_rows += 1
                # Verificar cuenta de comisión DNS
                if clabe != expected_comision_clabe:
                    logger.error(f"❌ [Test] CLABE de comisión incorrecta. Esperada: {expected_comision_clabe}, Encontrada: {clabe}")
                    return False
                if expected_comision_beneficiario not in beneficiario.upper():
                    logger.error(f"❌ [Test] Beneficiario de comisión incorrecto. Esperado: {expected_comision_beneficiario}, Encontrado: {beneficiario}")
                    return False
            else:
                capital_rows += 1
                # Verificar cuenta de capital
                if clabe != expected_capital_clabe:
                    logger.error(f"❌ [Test] CLABE de capital incorrecta. Esperada: {expected_capital_clabe}, Encontrada: {clabe}")
                    return False
                if expected_capital_beneficiario not in beneficiario.upper():
                    logger.error(f"❌ [Test] Beneficiario de capital incorrecto. Esperado: {expected_capital_beneficiario}, Encontrado: {beneficiario}")
                    return False
            
            # Verificar que el monto es numérico
            try:
                float(monto)
            except ValueError:
                logger.error(f"❌ [Test] Monto no numérico: {monto}")
                return False
        
        logger.info(f"   - Filas de capital (ligas): {capital_rows}")
        logger.info(f"   - Filas de comisión: {comision_rows}")
        logger.info(f"   - ✅ Todas las filas usan cuentas del PROVEEDOR (no del cliente)")
        
        # Verificar que hay 4 filas de capital (1 liga + 3 ligas = 4 total)
        # y 2 filas de comisión (1 por solicitud)
        if capital_rows != 4:
            logger.error(f"❌ [Test] Se esperaban 4 filas de capital, se encontraron {capital_rows}")
            return False
        
        if comision_rows != 2:
            logger.error(f"❌ [Test] Se esperaban 2 filas de comisión, se encontraron {comision_rows}")
            return False
        
        logger.info("✅ [Test] Layout CSV válido y usa cuentas de proveedor correctamente")
        return True
    
    async def verificar_no_regresion(self):
        """Verifica que ejecutar el proceso de nuevo NO procese solicitudes ya procesadas"""
        logger.info("🔍 [Test] Verificando que no hay regresión...")
        
        # Ejecutar proceso de nuevo
        from tesoreria_service import tesoreria_service
        resultado = await tesoreria_service.procesar_lote_tesoreria()
        
        if resultado is None:
            logger.info("✅ [Test] El proceso retornó None (no hay solicitudes pendientes)")
            return True
        else:
            logger.error("❌ [Test] El proceso procesó solicitudes que ya estaban procesadas")
            logger.error(f"   Resultado inesperado: {resultado}")
            return False
    
    async def run_test(self):
        """Ejecuta el test completo"""
        logger.info("🚀 [Test] ========== INICIO TEST TREASURY WORKFLOW ==========")
        
        try:
            # Setup
            await self.setup()
            
            # 1. Setup: Crear solicitudes de prueba
            logger.info("\n📝 PASO 1: Creando solicitudes de prueba...")
            await self.crear_solicitudes_prueba()
            
            # 2. Ejecutar el proceso
            logger.info("\n⚙️ PASO 2: Ejecutando proceso de tesorería...")
            resultado = await self.ejecutar_proceso_tesoreria()
            
            if not resultado:
                logger.error("❌ [Test] El proceso no retornó resultado")
                return False
            
            # 3. Verificar resultados
            logger.info("\n🔍 PASO 3: Verificando resultados...")
            
            # 3a. Verificar cambio de estados
            if not await self.verificar_cambio_estados():
                return False
            
            # 3b. Verificar lote creado
            if not await self.verificar_lote_creado():
                return False
            
            # 3c. Verificar CSV generado
            if not await self.verificar_csv_generado():
                return False
            
            # 4. Verificar no regresión
            logger.info("\n🔄 PASO 4: Verificando que no hay regresión...")
            if not await self.verificar_no_regresion():
                return False
            
            logger.info("\n🎉 ========== TEST TREASURY WORKFLOW COMPLETADO EXITOSAMENTE ==========")
            return True
            
        except Exception as e:
            logger.error(f"❌ [Test] Error durante el test: {str(e)}")
            import traceback
            logger.error(f"❌ [Test] Traceback:\n{traceback.format_exc()}")
            return False
        
        finally:
            # 5. Cleanup
            logger.info("\n🧹 PASO 5: Limpieza...")
            await self.cleanup()


async def main():
    """Función principal para ejecutar el test"""
    test = TreasuryWorkflowTest()
    success = await test.run_test()
    
    if success:
        logger.info("✅ TODOS LOS TESTS PASARON")
        return 0
    else:
        logger.error("❌ ALGUNOS TESTS FALLARON")
        return 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)