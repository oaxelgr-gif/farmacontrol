"""Reglas de caducidad compartidas por inventario, punto de venta y reportes."""
from flask import current_app

VIGENTE = "VIGENTE"
SIN_FECHA = "Sin fecha"
CADUCADO = "CADUCADO"
PROXIMO = "PRÓXIMO A CADUCAR"

ESTADOS_BLOQUEADOS = (CADUCADO, PROXIMO)


def dias_alerta():
    return int(current_app.config.get("DIAS_ALERTA_CADUCIDAD", 15))


def estado_sql(columna="fecha_caducidad"):
    """Expresión SQL que clasifica la caducidad de un producto."""
    dias = dias_alerta()
    return f"""CASE
            WHEN {columna} IS NULL THEN '{SIN_FECHA}'
            WHEN {columna} < CURDATE() THEN '{CADUCADO}'
            WHEN {columna} <= CURDATE() + INTERVAL {dias} DAY THEN '{PROXIMO}'
            ELSE '{VIGENTE}'
        END"""


def condicion_vendible(columna="fecha_caducidad"):
    """Filtro SQL: excluye productos caducados o por caducar dentro del umbral."""
    dias = dias_alerta()
    return f" AND ({columna} IS NULL OR {columna} > CURDATE() + INTERVAL {dias} DAY) "


def es_vendible(estado):
    return estado not in ESTADOS_BLOQUEADOS
