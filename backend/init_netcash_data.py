"""Script para inicializar datos de prueba NetCash V1

Ejecutar: python3 init_netcash_data.py

Crea:
- Cuenta concertadora activa (la del usuario: BANCO PRUEBA CTA)
"""

import asyncio
from config_cuentas_service import config_cuentas_service, TipoCuenta

async def init_data():
    print("=" * 60)
    print("INICIALIZACIÓN DATOS NETCASH V1")
    print("=" * 60)
    
    # Verificar si ya existe cuenta concertadora activa
    cuenta_existente = await config_cuentas_service.obtener_cuenta_activa(TipoCuenta.CONCERTADORA)
    
    if cuenta_existente:
        print(f"\n✅ Ya existe cuenta concertadora activa:")
        print(f"   Banco: {cuenta_existente.get('banco')}")
        print(f"   CLABE: {cuenta_existente.get('clabe')}")
        print(f"   Beneficiario: {cuenta_existente.get('beneficiario')}")
        return
    
    # Crear cuenta concertadora
    print("\n📝 Creando cuenta concertadora activa...")
    
    cuenta = await config_cuentas_service.crear_cuenta(
        tipo=TipoCuenta.CONCERTADORA,
        banco="BANCO PRUEBA CTA",
        clabe="234598762012345687",
        beneficiario="EMPRESA PRUEBA CTA",
        activar_inmediatamente=True,
        notas="Cuenta concertadora principal para depósitos de clientes NetCash"
    )
    
    if cuenta:
        print(f"\n✅ Cuenta concertadora creada:")
        print(f"   ID: {cuenta.get('id')}")
        print(f"   Banco: {cuenta.get('banco')}")
        print(f"   CLABE: {cuenta.get('clabe')}")
        print(f"   Beneficiario: {cuenta.get('beneficiario')}")
        print(f"   Activa: {cuenta.get('activa')}")
    else:
        print("\n❌ Error creando cuenta")
    
    print("\n" + "=" * 60)
    print("INICIALIZACIÓN COMPLETADA")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(init_data())
