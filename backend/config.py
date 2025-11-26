import os
from dotenv import load_dotenv

load_dotenv()

# Cuentas bancarias NetCash MBco
CUENTA_DEPOSITO_CLIENTE = {
    "razon_social": "JARDINERIA Y COMERCIO THABYETHA SA DE CV",
    "banco": "STP",
    "clabe": "646180139409481462"
}

CUENTA_CAPITAL_PROVEEDOR = {
    "razon_social": "AFFORDABLE MEDICAL SERVICES SC",
    "banco": "BBVA",
    "clabe": "012680001255709482"
}

CUENTA_COMISION_PROVEEDOR = {
    "razon_social": "Comercializadora Uetacop SA de CV",
    "banco": "ASP",
    "clabe": "058680000012912655"
}

# Contactos
CONTACTOS = {
    "ana": {
        "nombre": "Ana",
        "email": "gestion.ngdl@gmail.com",
        "telegram": "+52 33 1218 6685",
        "rol": "Administradora MBco / Dueña Operación NetCash"
    },
    "tono": {
        "nombre": "Toño",
        "email": "Mbcose@gmail.com",
        "telegram": "+52 33 2536 2673",
        "rol": "Tesorería Operativa"
    },
    "javier": {
        "nombre": "Javier",
        "telegram": "+52 33 3258 4721",
        "rol": "Supervisor de Tesorería"
    },
    "claudia": {
        "nombre": "Claudia",
        "email": "comprobanteenlace@gmail.com",
        "telegram": "+57 301 393 3477",
        "rol": "Control del Día Anterior"
    },
    "ximena": {
        "nombre": "Ximena",
        "email": "dableaff@gmail.com",
        "telegram": "4423475954",
        "rol": "Operadora Proveedor NetCash"
    },
    "alonzo": {
        "nombre": "Alonzo",
        "telegram": "4428163215",
        "rol": "Supervisor Proveedor NetCash"
    },
    "rodrigo": {
        "nombre": "Rodrigo",
        "telegram": "4427068087",
        "rol": "Gerente Proveedor NetCash"
    },
    "nash": {
        "nombre": "Nash",
        "telegram": "4421603030",
        "rol": "Dueño Proveedor NetCash"
    },
    "samuel": {
        "nombre": "Samuel",
        "telegram": "+52 33 1717 3461",
        "rol": "Socio MBco"
    },
    "daniel": {
        "nombre": "Daniel",
        "telegram": "+52 33 11 32 00 98",
        "rol": "Dirección y Dueño del Proyecto"
    }
}

# SLAs (en minutos)
SLA_ANA_CODIGO_SISTEMA = 5
SLA_TONO_EJECUCION_LAYOUT = 10
SLA_PROVEEDOR_LIGAS = 90

# Modo mantenimiento
MODO_MANTENIMIENTO = os.getenv("MODO_MANTENIMIENTO_NETCASH", "OFF")

# Mensajes estándar
MENSAJE_BIENVENIDA_CUENTA = """Para usar NetCash, recuerda que tus transferencias deben ir SIEMPRE a:

• Razón social: JARDINERIA Y COMERCIO THABYETHA SA DE CV
• Banco: STP
• CLABE: 646180139409481462

Cuando tengas tu comprobante de transferencia (PDF, foto o ZIP), mándamelo por aquí y te ayudo a procesar tus ligas NetCash."""

MENSAJE_MANTENIMIENTO = """El asistente NetCash está en mantenimiento temporal. Por favor, comunícate directamente con Ana:

📧 Email: gestion.ngdl@gmail.com
📱 Telegram: +52 33 1218 6685

Disculpa las molestias."""