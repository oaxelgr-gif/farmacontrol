"""Cortes de caja: estado, apertura y cierre."""
from datetime import datetime

from ..db import execute, fetch_all, fetch_one, num, transaction
from . import NegocioError

_EF = "LOWER(mp.nombre) LIKE '%%efectivo%%'"
_TJ = "LOWER(mp.nombre) LIKE '%%tarjeta%%'"
_TR = "LOWER(mp.nombre) LIKE '%%transfer%%'"

SUMAS_POR_METODO = f"""
    IFNULL(SUM(CASE WHEN {_EF} THEN v.total ELSE 0 END), 0) AS efectivo,
    IFNULL(SUM(CASE WHEN {_TJ} THEN v.total ELSE 0 END), 0) AS tarjeta,
    IFNULL(SUM(CASE WHEN {_TR} THEN v.total ELSE 0 END), 0) AS transferencia,
    IFNULL(SUM(CASE WHEN NOT ({_EF}) AND NOT ({_TJ}) AND NOT ({_TR}) THEN v.total ELSE 0 END), 0) AS otros,
    COUNT(v.id) AS numero_ventas,
    IFNULL(SUM(v.total), 0) AS total_ventas
"""


def corte_abierto(conn, usuario_id):
    return fetch_one(
        conn,
        """SELECT id, monto_inicial, fecha_apertura FROM cortes_caja
           WHERE usuario_id = %s AND cerrado = 0 AND status = 1 ORDER BY id DESC LIMIT 1""",
        (usuario_id,),
    )


def totales(conn, usuario_id, desde, hasta=None):
    sql = f"""SELECT {SUMAS_POR_METODO} FROM ventas v JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
              WHERE v.usuario_id = %s AND v.status = 1 AND v.fecha >= %s"""
    params = [usuario_id, desde]
    if hasta is not None:
        sql += " AND v.fecha <= %s"
        params.append(hasta)
    r = fetch_one(conn, sql, params) or {}
    return {
        "efectivo": num(r.get("efectivo")),
        "tarjeta": num(r.get("tarjeta")),
        "transferencia": num(r.get("transferencia")),
        "otros": num(r.get("otros")),
        "numero_ventas": int(r.get("numero_ventas") or 0),
        "total_ventas": num(r.get("total_ventas")),
    }


def estado(conn, usuario_id):
    c = corte_abierto(conn, usuario_id)
    if not c:
        return {"abierto": False, "corte_id": None}
    t = totales(conn, usuario_id, c["fecha_apertura"])
    fondo = num(c["monto_inicial"])
    return {
        "abierto": True,
        "corte_id": c["id"],
        "fecha_apertura": c["fecha_apertura"].isoformat(sep=" ") if c["fecha_apertura"] else None,
        "fondo_inicial": fondo,
        **t,
        "efectivo_en_caja": round(fondo + t["efectivo"], 2),
    }


def abrir(conn, usuario_id, monto_inicial):
    if monto_inicial < 0:
        raise NegocioError("El monto inicial no puede ser negativo.", 422)
    with transaction(conn):
        if corte_abierto(conn, usuario_id):
            raise NegocioError("Ya tienes un corte de caja abierto.", 409)
        execute(conn, """INSERT INTO cortes_caja (usuario_id, fecha_apertura, monto_inicial, cerrado, status)
                         VALUES (%s, NOW(), %s, 0, 1)""", (usuario_id, round(monto_inicial, 2)))
    return estado(conn, usuario_id)


def cerrar(conn, usuario_id):
    with transaction(conn):
        c = corte_abierto(conn, usuario_id)
        if not c:
            raise NegocioError("No hay un corte de caja abierto.", 409)
        cierre = datetime.now().replace(microsecond=0)
        t = totales(conn, usuario_id, c["fecha_apertura"], cierre)
        fondo = num(c["monto_inicial"])
        final = round(fondo + t["total_ventas"], 2)
        execute(conn, "UPDATE cortes_caja SET cerrado = 1, fecha_cierre = %s, monto_final = %s WHERE id = %s",
                (cierre, final, c["id"]))
        execute(conn, """INSERT INTO auditoria_cortes (corte_id, usuario_id, fecha_apertura, fecha_cierre,
                             monto_inicial, monto_final, ventas_efectivo, ventas_tarjeta,
                             ventas_transferencia, total_ventas)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (c["id"], usuario_id, c["fecha_apertura"], cierre, fondo, final,
                 t["efectivo"], t["tarjeta"], t["transferencia"], t["total_ventas"]))
    return {"corte_id": c["id"], "fecha_cierre": cierre.isoformat(sep=" "), "fondo_inicial": fondo,
            "monto_final": final, "efectivo_en_caja": round(fondo + t["efectivo"], 2), **t}


def historial(conn, usuario_id, limite=10):
    filas = fetch_all(conn, """SELECT id, fecha_apertura, fecha_cierre, monto_inicial, monto_final
                               FROM cortes_caja WHERE usuario_id = %s AND cerrado = 1 AND status = 1
                               ORDER BY fecha_cierre DESC LIMIT %s""", (usuario_id, limite))
    return [{"corte_id": f["id"],
             "fecha_apertura": f["fecha_apertura"].isoformat(sep=" ") if f["fecha_apertura"] else None,
             "fecha_cierre": f["fecha_cierre"].isoformat(sep=" ") if f["fecha_cierre"] else None,
             "monto_inicial": num(f["monto_inicial"]), "monto_final": num(f["monto_final"])} for f in filas]
