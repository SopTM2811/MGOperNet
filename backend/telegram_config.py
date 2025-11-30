"""
Configuración de Telegram IDs para el flujo NetCash

IMPORTANTE PARA PRODUCCIÓN:
- Estos IDs están configurados para PRUEBAS
- Antes de desplegar a producción, actualizar con los IDs reales
"""

# ========== IDs DE TELEGRAM ==========

# Ana - Administradora de MBco
# Recibe notificaciones de solicitudes listas para MBco
# Asigna folios MBco a las operaciones
# 
# ⚠️ PRUEBAS: Actualmente usando ID de pruebas (76316336750)
# Este ID también existe como cliente, pero el rol se determina por CONTEXTO:
# - Notificaciones del sistema con botones de admin → modo Ana (admin_mbco)
# - Menú de cliente normal → modo cliente
#
# 🔧 PRODUCCIÓN: Cambiar a ID real de Ana (1720830607)
TELEGRAM_ID_ANA = 76316336750  # TODO: Cambiar a 1720830607 en producción

# Tesorería - Equipo de tesorería MBco
# Recibe notificaciones de órdenes internas pendientes
# Confirma envíos de ligas a proveedores
#
# ⚠️ PRUEBAS: Actualmente usando ID de pruebas (76316336750)
# 🔧 PRODUCCIÓN: Cambiar a ID real del grupo/usuario de Tesorería
TELEGRAM_ID_TESORERIA = 76316336750  # TODO: Cambiar a ID real en producción

# ========== CONFIGURACIÓN DE ROLES ==========

def es_usuario_admin_mbco(telegram_id: int) -> bool:
    """
    Verifica si un usuario tiene rol de administrador MBco (Ana)
    
    Args:
        telegram_id: ID de Telegram del usuario
        
    Returns:
        True si el usuario es admin_mbco, False si no
    """
    return telegram_id == TELEGRAM_ID_ANA


def es_usuario_tesoreria(telegram_id: int) -> bool:
    """
    Verifica si un usuario pertenece al equipo de tesorería
    
    Args:
        telegram_id: ID de Telegram del usuario
        
    Returns:
        True si el usuario es de tesorería, False si no
    """
    return telegram_id == TELEGRAM_ID_TESORERIA


# ========== NOTAS PARA DESARROLLO ==========
"""
CONTEXTO DE CONVERSACIÓN:

Un mismo telegram_id puede tener múltiples roles según el CONTEXTO:

1. Usuario 76316336750 como CLIENTE:
   - Entra al bot con /start
   - Usa el menú de operaciones
   - Crea solicitudes NetCash
   → Se comporta como CLIENTE normal

2. Usuario 76316336750 como ANA (admin_mbco):
   - Recibe notificación del sistema: "🧾 Nueva solicitud NetCash lista para MBco"
   - Presiona botón [Asignar folio MBco]
   - Asigna folios MBco
   → Se comporta como ADMINISTRADOR MBco

El rol NO está hardcodeado en BD, se determina por el FLUJO de conversación activo.

MIGRACIÓN A PRODUCCIÓN:

Archivo a modificar: /app/backend/telegram_config.py

Cambios necesarios:
1. TELEGRAM_ID_ANA = 1720830607  # ID real de Ana
2. TELEGRAM_ID_TESORERIA = XXXXXXXX  # ID real de grupo/usuario de Tesorería

No requiere cambios en:
- Base de datos
- Lógica de negocio
- Handlers de Telegram (usan estas constantes)
"""
