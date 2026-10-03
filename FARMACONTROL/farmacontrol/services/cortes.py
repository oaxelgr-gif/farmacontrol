"""Lógica de cortes de caja: apertura, totales, cierre y datos para tickets."""
from datetime import datetime

from ..db import execute, fetch_all, fetch_one, to_float, transaction
from .catalogos import SQL_SUMAS_POR_METODO


class CorteError(Exception):
    pass


def corte_abierto(usuario_id, cursor=None):
    return fetch_one(
        """SELECT id, monto_inicial, fecha_apertura
           FROM cortes_caja
           WHERE usuario_id = %s AND cerrado = 0 AND status = 1
           ORDER BY id DESC LIMIT 1""",
        (usuario_id,),
        cursor=cursor,
    )


def totales_periodo(usuario_id, desde, hasta=None, cursor=None):
    """Suma de ventas del usuario entre `desde` y `hasta` agrupadas por método."""
    sql = f"""SELECT {SQL_SUMAS_POR_METODO}
              FROM ventas v
              JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
              WHERE v.usuario_id = %s AND v.status = 1 AND v.fecha >= %s"""
    params = [usuario_id, desde]
    if hasta is not None:
        sql += " AND v.fecha <= %s"
        params.append(hasta)
    row = fetch_one(sql, params, cursor=cursor) or {}
    return {
        "efectivo": to_float(row.get("efectivo")),
        "tarjeta": to_float(row.get("tarjeta")),
        "transferencia": to_float(row.get("transferencia")),
        "otros": to_float(row.get("otros")),
        "numero_ventas": int(row.get("numero_ventas") or 0),
        "total_ventas": to_float(row.get("total_ventas")),
    }


def ventas_periodo(usuario_id, desde, hasta=None, con_productos=False):
    resumen = ""
    if con_productos:
        resumen = """,
            (SELECT GROUP_CONCAT(CONCAT(dv.cantidad, 'x ', IFNULL(p.nombre, 'Servicio')) SEPARATOR ', ')
             FROM detalle_ventas dv LEFT JOIN productos p ON dv.producto_id = p.id
             WHERE dv.venta_id = v.id) AS productos_resumen"""
    sql = f"""SELECT v.id, v.folio, v.fecha, v.total, v.pago_recibido, v.cambio_entregado,
                     mp.nombre AS metodo_pago, c.nombre AS cliente {resumen}
              FROM ventas v
              JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
              LEFT JOIN clientes c ON v.cliente_id = c.id
              WHERE v.usuario_id = %s AND v.status = 1 AND v.fecha >= %s"""
    params = [usuario_id, desde]
    if hasta is not None:
        sql += " AND v.fecha <= %s"
        params.append(hasta)
    sql += " ORDER BY v.fecha DESC"
    return fetch_all(sql, params)


def abrir_corte(usuario_id, monto_inicial):
    if monto_inicial < 0:
        raise CorteError("El monto inicial no puede ser negativo.")
    with transaction() as cur:
        if corte_abierto(usuario_id, cursor=cur):
            raise CorteError("Ya tienes un corte de caja abierto.")
        return execute(
            """INSERT INTO cortes_caja (usuario_id, fecha_apertura, monto_inicial, cerrado, status)
               VALUES (%s, NOW(), %s, 0, 1)""",
            (usuario_id, monto_inicial),
            cursor=cur,
        )


def cerrar_corte(usuario_id):
    """Cierra el corte abierto del usuario, registra auditoría y devuelve el id."""
    with transaction() as cur:
        corte = corte_abierto(usuario_id, cursor=cur)
        if not corte:
            raise CorteError("No hay un corte de caja abierto.")
        cierre = datetime.now().replace(microsecond=0)
        t = totales_periodo(usuario_id, corte["fecha_apertura"], cierre, cursor=cur)
        monto_inicial = to_float(corte["monto_inicial"])
        monto_final = round(monto_inicial + t["total_ventas"], 2)

        execute(
            """UPDATE cortes_caja SET cerrado = 1, fecha_cierre = %s, monto_final = %s
               WHERE id = %s""",
            (cierre, monto_final, corte["id"]),
            cursor=cur,
        )
        execute(
            """INSERT INTO auditoria_cortes
               (corte_id, usuario_id, fecha_apertura, fecha_cierre, monto_inicial, monto_final,
                ventas_efectivo, ventas_tarjeta, ventas_transferencia, total_ventas)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (corte["id"], usuario_id, corte["fecha_apertura"], cierre, monto_inicial, monto_final,
             t["efectivo"], t["tarjeta"], t["transferencia"], t["total_ventas"]),
            cursor=cur,
        )
        return corte["id"]


def obtener_corte(corte_id, solo_cerrado=True):
    sql = """SELECT cc.*, u.nombre AS usuario_nombre,
                    ac.ventas_efectivo AS aud_efectivo, ac.ventas_tarjeta AS aud_tarjeta,
                    ac.ventas_transferencia AS aud_transferencia, ac.total_ventas AS aud_total
             FROM cortes_caja cc
             JOIN usuarios u ON cc.usuario_id = u.id
             LEFT JOIN auditoria_cortes ac ON ac.corte_id = cc.id
             WHERE cc.id = %s"""
    if solo_cerrado:
        sql += " AND cc.cerrado = 1"
    return fetch_one(sql + " LIMIT 1", (corte_id,))


def top_productos_periodo(usuario_id, desde, hasta, limite=10):
    return fetch_all(
        """SELECT IFNULL(p.nombre, 'Servicio / Consulta') AS nombre, p.codigo_barras,
                  IFNULL(p.antibiotico, 0) AS antibiotico,
                  SUM(dv.cantidad) AS cantidad_vendida,
                  SUM(dv.subtotal) AS total_venta,
                  COUNT(DISTINCT dv.venta_id) AS veces_vendido
           FROM detalle_ventas dv
           JOIN ventas v ON dv.venta_id = v.id
           LEFT JOIN productos p ON dv.producto_id = p.id
           WHERE v.usuario_id = %s AND v.status = 1 AND v.fecha BETWEEN %s AND %s
           GROUP BY p.id, p.nombre, p.codigo_barras, p.antibiotico
           ORDER BY cantidad_vendida DESC
           LIMIT %s""",
        (usuario_id, desde, hasta, limite),
    )


def datos_ticket(corte_id, reimpresion=False, con_productos=False):
    """
    Estructura normalizada para los tickets de corte (cierre y reimpresión).
    Devuelve None si el corte no existe.
    """
    corte = obtener_corte(corte_id, solo_cerrado=False)
    if not corte:
        return None

    cerrado = bool(corte["cerrado"]) and corte["fecha_cierre"] is not None
    hasta = corte["fecha_cierre"] if cerrado else datetime.now()
    t = totales_periodo(corte["usuario_id"], corte["fecha_apertura"], hasta)

    # Si existe snapshot de auditoría y no hay ventas ligadas, se respeta el snapshot
    if t["numero_ventas"] == 0 and corte.get("aud_total"):
        t.update(
            efectivo=to_float(corte["aud_efectivo"]),
            tarjeta=to_float(corte["aud_tarjeta"]),
            transferencia=to_float(corte["aud_transferencia"]),
            total_ventas=to_float(corte["aud_total"]),
        )

    fondo = to_float(corte["monto_inicial"])
    monto_final = to_float(corte["monto_final"]) if cerrado else round(fondo + t["total_ventas"], 2)
    fmt = "%d/%m/%Y %H:%M"
    duracion = ""
    if corte["fecha_apertura"]:
        delta = hasta - corte["fecha_apertura"]
        horas, resto = divmod(int(delta.total_seconds()), 3600)
        duracion = f"{horas} h {resto // 60:02d} min"

    datos = {
        "corte_id": corte["id"],
        "usuario": corte["usuario_nombre"],
        "usuario_id": corte["usuario_id"],
        "cerrado": cerrado,
        "fecha_apertura": corte["fecha_apertura"].strftime(fmt) if corte["fecha_apertura"] else "",
        "fecha_cierre": corte["fecha_cierre"].strftime(fmt) if cerrado else "EN CURSO",
        "duracion": duracion,
        "fondo_inicial": fondo,
        "ventas_efectivo": t["efectivo"],
        "ventas_tarjeta": t["tarjeta"],
        "ventas_transferencia": t["transferencia"],
        "ventas_otros": t["otros"],
        "total_ventas": t["total_ventas"],
        "numero_ventas": t["numero_ventas"],
        "monto_final": monto_final,
        "efectivo_en_caja": round(fondo + t["efectivo"], 2),
        "ventas": ventas_periodo(corte["usuario_id"], corte["fecha_apertura"], hasta),
        "es_reimpresion": reimpresion,
        "top_productos": [],
    }
    if con_productos:
        datos["top_productos"] = top_productos_periodo(
            corte["usuario_id"], corte["fecha_apertura"], hasta)
    return datos
