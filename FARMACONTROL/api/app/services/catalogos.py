"""Catálogos auxiliares, clientes y resumen del día."""
from datetime import date

from ..config import settings
from ..db import execute, fetch_all, fetch_one, fetch_value, num
from . import NegocioError
from .caja import SUMAS_POR_METODO

TABLAS_CATALOGO = {"procedimientos": ("servicios", "servicio"), "consultas": ("consultas", "consulta")}


def servicios(conn, tipo):
    if tipo not in TABLAS_CATALOGO:
        raise NegocioError("Catálogo inexistente. Usa: productos, procedimientos o consultas.", 404)
    tabla, tipo_item = TABLAS_CATALOGO[tipo]
    filas = fetch_all(conn, f"SELECT id, nombre, precio FROM {tabla} WHERE status = 1 ORDER BY nombre")
    return [{"id": r["id"], "nombre": r["nombre"], "precio": num(r["precio"]), "tipo": tipo_item} for r in filas]


def metodos_pago(conn):
    return fetch_all(conn, "SELECT id, nombre FROM metodos_pago WHERE status = 1 ORDER BY id")


def secciones(conn):
    return fetch_all(conn, "SELECT id, nombre FROM secciones WHERE status = 1 ORDER BY nombre")


def clientes(conn, q=""):
    sql = "SELECT id, nombre, rfc_nit, telefono, email FROM clientes WHERE status = 1"
    params = []
    if q:
        sql += " AND (nombre LIKE %s OR rfc_nit LIKE %s OR telefono LIKE %s)"
        params += [f"%{q}%"] * 3
    return fetch_all(conn, sql + " ORDER BY nombre LIMIT 25", params)


def crear_cliente(conn, datos):
    nombre = (datos.get("nombre") or "").strip()
    if not nombre:
        raise NegocioError("Nombre requerido", 422)
    limpio = {k: ((datos.get(k) or "").strip() or None) for k in ("rfc_nit", "direccion", "telefono", "email")}
    nuevo = execute(conn, """INSERT INTO clientes (nombre, rfc_nit, direccion, telefono, email, status)
                             VALUES (%s, %s, %s, %s, %s, 1)""",
                    (nombre, limpio["rfc_nit"], limpio["direccion"], limpio["telefono"], limpio["email"]))
    return fetch_one(conn, "SELECT id, nombre, rfc_nit, telefono, email FROM clientes WHERE id = %s", (nuevo,))


def resumen_dia(conn, dia=None):
    dia = dia or date.today()
    d = int(settings.DIAS_ALERTA_CADUCIDAD)
    ventas = fetch_one(conn, f"""SELECT {SUMAS_POR_METODO} FROM ventas v
                                 JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
                                 WHERE DATE(v.fecha) = %s AND v.status = 1""", (dia,)) or {}
    return {
        "fecha": dia.isoformat(),
        "ventas": int(ventas.get("numero_ventas") or 0),
        "ingresos": num(ventas.get("total_ventas")),
        "efectivo": num(ventas.get("efectivo")),
        "tarjeta": num(ventas.get("tarjeta")),
        "transferencia": num(ventas.get("transferencia")),
        "stock_bajo": int(fetch_value(conn, "SELECT COUNT(*) AS n FROM productos WHERE stock_actual <= stock_minimo AND status = 1")),
        "por_caducar": int(fetch_value(conn, f"""SELECT COUNT(*) AS n FROM productos WHERE status = 1 AND stock_actual > 0
                                              AND fecha_caducidad <= CURDATE() + INTERVAL {d} DAY""")),
        "cortes_abiertos": int(fetch_value(conn, "SELECT COUNT(*) AS n FROM cortes_caja WHERE cerrado = 0 AND status = 1")),
        "top_productos": [
            {"nombre": r["nombre"], "cantidad": int(num(r["cantidad"]))}
            for r in fetch_all(conn, """SELECT p.nombre, SUM(dv.cantidad) AS cantidad
                                        FROM detalle_ventas dv JOIN productos p ON p.id = dv.producto_id
                                        JOIN ventas v ON v.id = dv.venta_id
                                        WHERE DATE(v.fecha) = %s AND v.status = 1
                                        GROUP BY p.id, p.nombre ORDER BY cantidad DESC LIMIT 5""", (dia,))
        ],
    }
