"""
Menú lateral de la aplicación.

Cada entrada define el endpoint, ícono (Font Awesome), etiqueta, roles que
la ven y los blueprints/endpoints que la marcan como activa.
Modificar el menú = editar esta lista, sin tocar plantillas.
"""
from flask import request, url_for

from .models import ROL_ADMIN, ROL_FARMACEUTICO

AMBOS = (ROL_ADMIN, ROL_FARMACEUTICO)

MENU = [
    {"endpoint": "dashboard.inicio", "icono": "fa-house", "texto": "Inicio",
     "roles": (ROL_ADMIN,), "activo": ("dashboard.inicio",)},
    {"endpoint": "dashboard.inicio_farmacia", "icono": "fa-house", "texto": "Inicio",
     "roles": (ROL_FARMACEUTICO,), "activo": ("dashboard.inicio_farmacia",)},
    {"endpoint": "ventas.punto_venta", "icono": "fa-cash-register", "texto": "Punto de venta",
     "roles": (ROL_ADMIN,), "activo": ("ventas.punto_venta",)},
    {"endpoint": "ventas.punto_farmacia", "icono": "fa-cash-register", "texto": "Ventas",
     "roles": (ROL_FARMACEUTICO,), "activo": ("ventas.punto_farmacia",)},
    {"endpoint": "caja.corte_caja", "icono": "fa-vault", "texto": "Caja",
     "roles": AMBOS, "activo": ("caja",)},
    {"endpoint": "ventas.reimprimir_tickets", "icono": "fa-receipt", "texto": "Tickets",
     "roles": AMBOS, "activo": ("ventas.reimprimir_tickets", "ventas.ver_detalle_venta")},
    {"endpoint": "clinica.tablero", "icono": "fa-user-doctor", "texto": "Clínica",
     "roles": (ROL_ADMIN,), "activo": ("clinica",)},
    {"endpoint": "inventario.listar_productos", "icono": "fa-boxes-stacked", "texto": "Inventario",
     "roles": AMBOS, "activo": ("inventario",)},
    {"endpoint": "servicios.gestion_servicios", "icono": "fa-stethoscope", "texto": "Servicios",
     "roles": (ROL_ADMIN,), "activo": ("servicios",)},
    {"endpoint": "reportes.dashboard", "icono": "fa-chart-pie", "texto": "Reportes",
     "roles": (ROL_ADMIN,), "activo": ("reportes", "cortes")},
    {"endpoint": "reportes.caducidad", "icono": "fa-calendar-xmark", "texto": "Caducidades",
     "roles": (ROL_FARMACEUTICO,), "activo": ("reportes.caducidad",)},
    {"endpoint": "usuarios.listar_usuarios", "icono": "fa-user-shield", "texto": "Usuarios",
     "roles": (ROL_ADMIN,), "activo": ("usuarios",)},
]


def _es_activo(item):
    endpoint = request.endpoint or ""
    blueprint = request.blueprint or ""
    for clave in item["activo"]:
        if clave == endpoint or ("." not in clave and clave == blueprint):
            return True
    return False


def menu_para(usuario):
    if not getattr(usuario, "is_authenticated", False):
        return []
    items = []
    for item in MENU:
        if usuario.rol in item["roles"]:
            items.append({
                "url": url_for(item["endpoint"]),
                "icono": item["icono"],
                "texto": item["texto"],
                "activo": _es_activo(item),
            })
    return items
