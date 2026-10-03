"""Productos: caducidad, búsqueda, catálogo y administración."""
from ..config import settings
from ..db import execute, fetch_all, fetch_one, num
from . import NegocioError

VIGENTE, SIN_FECHA, CADUCADO, PROXIMO = "VIGENTE", "Sin fecha", "CADUCADO", "PRÓXIMO A CADUCAR"
BLOQUEADOS = (CADUCADO, PROXIMO)


def estado_sql(col="fecha_caducidad"):
    d = int(settings.DIAS_ALERTA_CADUCIDAD)
    return f"""CASE WHEN {col} IS NULL THEN '{SIN_FECHA}'
                    WHEN {col} < CURDATE() THEN '{CADUCADO}'
                    WHEN {col} <= CURDATE() + INTERVAL {d} DAY THEN '{PROXIMO}'
                    ELSE '{VIGENTE}' END"""


def filtro_vendible(col="fecha_caducidad"):
    d = int(settings.DIAS_ALERTA_CADUCIDAD)
    return f" AND ({col} IS NULL OR {col} > CURDATE() + INTERVAL {d} DAY) "


def es_vendible(estado):
    return estado not in BLOQUEADOS


SELECT_PRODUCTO = f"""
    SELECT p.id, p.nombre, p.codigo_barras, p.lote, p.precio_publico, p.precio_costo,
           p.stock_actual, p.stock_minimo, p.antibiotico, p.fecha_caducidad, p.seccion_id,
           s.nombre AS seccion, {estado_sql('p.fecha_caducidad')} AS estado_caducidad
    FROM productos p LEFT JOIN secciones s ON s.id = p.seccion_id
"""


def a_dict(p, con_costo=False):
    d = {
        "id": p["id"],
        "nombre": p["nombre"],
        "codigo_barras": p.get("codigo_barras"),
        "lote": p.get("lote"),
        "precio": num(p["precio_publico"]),
        "stock": int(p["stock_actual"] or 0),
        "stock_minimo": int(p.get("stock_minimo") or 0),
        "antibiotico": bool(p["antibiotico"]),
        "fecha_caducidad": p["fecha_caducidad"].isoformat() if p.get("fecha_caducidad") else None,
        "seccion": p.get("seccion"),
        "estado_caducidad": p["estado_caducidad"],
        "tipo": "producto",
    }
    if con_costo:
        d["precio_costo"] = num(p.get("precio_costo"))
    return d


def listar(conn, search="", alerta="", seccion_id=None, limite=500, con_costo=False):
    sql = SELECT_PRODUCTO + " WHERE p.status = 1"
    params = []
    if search:
        sql += " AND (p.nombre LIKE %s OR p.codigo_barras LIKE %s OR p.lote LIKE %s)"
        params += [f"%{search}%"] * 3
    if alerta == "bajo":
        sql += " AND p.stock_actual <= p.stock_minimo"
    elif alerta == "caducidad":
        sql += f" AND p.fecha_caducidad <= CURDATE() + INTERVAL {int(settings.DIAS_ALERTA_CADUCIDAD)} DAY"
    elif alerta == "antibiotico":
        sql += " AND p.antibiotico = 1"
    if seccion_id:
        sql += " AND p.seccion_id = %s"
        params.append(int(seccion_id))
    sql += " ORDER BY p.nombre LIMIT %s"
    params.append(int(limite))
    return [a_dict(p, con_costo) for p in fetch_all(conn, sql, params)]


def obtener(conn, producto_id, con_costo=False):
    p = fetch_one(conn, SELECT_PRODUCTO + " WHERE p.id = %s AND p.status = 1", (producto_id,))
    if not p:
        raise NegocioError("Producto no encontrado", 404)
    return a_dict(p, con_costo)


def buscar(conn, q, incluir_bloqueados=False):
    """Código exacto (lector) o coincidencias por nombre/código."""
    q = (q or "").strip()
    if not q:
        raise NegocioError("Consulta vacía", 422)

    exacto = fetch_one(conn, SELECT_PRODUCTO + " WHERE p.codigo_barras = %s AND p.status = 1", (q,))
    if exacto:
        if int(exacto["stock_actual"] or 0) <= 0:
            raise NegocioError(f"«{exacto['nombre']}» no tiene existencias.", 409)
        if not incluir_bloqueados and not es_vendible(exacto["estado_caducidad"]):
            raise NegocioError(
                f"Producto {exacto['estado_caducidad'].lower()}. No se puede vender.", 409)
        return {"tipo": "exacto", "data": [a_dict(exacto)]}

    filtro = "" if incluir_bloqueados else filtro_vendible("p.fecha_caducidad")
    filas = fetch_all(
        conn,
        SELECT_PRODUCTO + f""" WHERE (p.nombre LIKE %s OR p.codigo_barras LIKE %s)
             AND p.status = 1 AND p.stock_actual > 0 {filtro}
             ORDER BY p.nombre LIMIT 15""",
        (f"%{q}%", f"%{q}%"),
    )
    if filas:
        return {"tipo": "lista", "data": [a_dict(p) for p in filas]}

    bloqueados = fetch_one(
        conn, "SELECT COUNT(*) AS n FROM productos WHERE nombre LIKE %s AND status = 1 AND stock_actual > 0",
        (f"%{q}%",))
    if bloqueados and bloqueados["n"]:
        raise NegocioError("Los productos encontrados están caducados o próximos a caducar.", 409)
    raise NegocioError("No encontrado o sin stock", 404)


def vendibles(conn, incluir_bloqueados=False):
    filtro = "" if incluir_bloqueados else filtro_vendible("p.fecha_caducidad")
    filas = fetch_all(conn, SELECT_PRODUCTO + f" WHERE p.status = 1 AND p.stock_actual > 0 {filtro} ORDER BY p.nombre")
    return [a_dict(p) for p in filas]


def caducidad(conn, producto_id):
    p = fetch_one(
        conn,
        f"""SELECT nombre, fecha_caducidad, {estado_sql()} AS estado_caducidad,
                   DATEDIFF(fecha_caducidad, CURDATE()) AS dias_restantes
            FROM productos WHERE id = %s AND status = 1""",
        (producto_id,),
    )
    if not p:
        raise NegocioError("Producto no encontrado", 404)
    return {
        "producto": p["nombre"],
        "estado_caducidad": p["estado_caducidad"],
        "dias_restantes": p["dias_restantes"],
        "es_valido": es_vendible(p["estado_caducidad"]),
    }


# ---------------------------------------------------------------- administración
CAMPOS = ("nombre", "codigo_barras", "lote", "stock_minimo", "precio_costo", "precio_publico",
          "fecha_caducidad", "antibiotico", "seccion_id")


def crear(conn, datos):
    try:
        nuevo = execute(
            conn,
            """INSERT INTO productos (nombre, codigo_barras, lote, stock_actual, stock_minimo,
                   precio_costo, precio_publico, fecha_caducidad, antibiotico, seccion_id, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)""",
            (datos["nombre"], datos.get("codigo_barras"), datos.get("lote"), datos.get("stock_inicial", 0),
             datos.get("stock_minimo", 5), datos["precio_costo"], datos["precio_publico"],
             datos.get("fecha_caducidad"), 1 if datos.get("antibiotico") else 0, datos.get("seccion_id")),
        )
    except Exception as exc:
        if "Duplicate" in str(exc) or "UNIQUE" in str(exc):
            raise NegocioError("Ya existe un producto con ese código de barras.", 409)
        raise
    return obtener(conn, nuevo, con_costo=True)


def actualizar(conn, producto_id, cambios):
    obtener(conn, producto_id)
    sets, params = [], []
    for campo in CAMPOS:
        if campo in cambios and cambios[campo] is not None:
            valor = cambios[campo]
            if campo == "antibiotico":
                valor = 1 if valor else 0
            sets.append(f"{campo} = %s")
            params.append(valor)
    if sets:
        try:
            execute(conn, f"UPDATE productos SET {', '.join(sets)} WHERE id = %s", params + [producto_id])
        except Exception as exc:
            if "Duplicate" in str(exc) or "UNIQUE" in str(exc):
                raise NegocioError("Ya existe un producto con ese código de barras.", 409)
            raise
    return obtener(conn, producto_id, con_costo=True)


def sumar_stock(conn, producto_id, cantidad):
    if cantidad <= 0:
        raise NegocioError("La cantidad debe ser mayor a cero.", 422)
    obtener(conn, producto_id)
    execute(conn, "UPDATE productos SET stock_actual = stock_actual + %s WHERE id = %s", (cantidad, producto_id))
    return obtener(conn, producto_id, con_costo=True)


def eliminar(conn, producto_id):
    obtener(conn, producto_id)
    execute(conn, "UPDATE productos SET status = 0 WHERE id = %s", (producto_id,))
