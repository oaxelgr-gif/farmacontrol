"""Consultas de catálogos reutilizadas por varios módulos."""
from ..db import fetch_all
from ..models import ROL_FARMACEUTICO

# Clasificación de métodos de pago por nombre (robusto aunque cambien los IDs)
SQL_ES_EFECTIVO = "LOWER(mp.nombre) LIKE '%%efectivo%%'"
SQL_ES_TARJETA = "LOWER(mp.nombre) LIKE '%%tarjeta%%'"
SQL_ES_TRANSFER = "LOWER(mp.nombre) LIKE '%%transfer%%'"

SQL_SUMAS_POR_METODO = f"""
    IFNULL(SUM(CASE WHEN {SQL_ES_EFECTIVO} THEN v.total ELSE 0 END), 0) AS efectivo,
    IFNULL(SUM(CASE WHEN {SQL_ES_TARJETA} THEN v.total ELSE 0 END), 0) AS tarjeta,
    IFNULL(SUM(CASE WHEN {SQL_ES_TRANSFER} THEN v.total ELSE 0 END), 0) AS transferencia,
    IFNULL(SUM(CASE WHEN NOT ({SQL_ES_EFECTIVO}) AND NOT ({SQL_ES_TARJETA})
                     AND NOT ({SQL_ES_TRANSFER}) THEN v.total ELSE 0 END), 0) AS otros,
    COUNT(v.id) AS numero_ventas,
    IFNULL(SUM(v.total), 0) AS total_ventas
"""


def farmaceuticos():
    return fetch_all(
        "SELECT id, nombre FROM usuarios WHERE status = 1 AND rol = %s ORDER BY nombre",
        (ROL_FARMACEUTICO,),
    )


def usuarios_activos():
    return fetch_all("SELECT id, nombre FROM usuarios WHERE status = 1 ORDER BY nombre")


def metodos_pago():
    return fetch_all("SELECT id, nombre FROM metodos_pago WHERE status = 1 ORDER BY id")


def secciones():
    return fetch_all("SELECT id, nombre FROM secciones WHERE status = 1 ORDER BY nombre")


def icono_metodo(nombre):
    n = (nombre or "").lower()
    if "efectivo" in n:
        return "fa-money-bill-wave"
    if "tarjeta" in n:
        return "fa-credit-card"
    if "transfer" in n:
        return "fa-building-columns"
    return "fa-wallet"


def clase_metodo(nombre):
    n = (nombre or "").lower()
    if "efectivo" in n:
        return "success"
    if "tarjeta" in n:
        return "info"
    if "transfer" in n:
        return "purple"
    return "neutral"
