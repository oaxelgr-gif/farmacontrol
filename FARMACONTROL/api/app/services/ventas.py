"""Registro y consulta de ventas (fuente de verdad del punto de venta)."""
from ..db import execute, fetch_all, fetch_one, num, transaction
from . import NegocioError, antibioticos, clinica_caja, folios
from .caja import corte_abierto
from .productos import es_vendible, estado_sql

TABLAS = {"servicio": "servicios", "consulta": "consultas"}
CLIENTE_GENERAL = 1


def _linea(conn, item):
    tipo, item_id, cant = item["tipo"], int(item["id"]), int(item["cant"])
    if cant <= 0 or item_id <= 0:
        raise NegocioError("Hay un artículo con cantidad o identificador inválido.", 422)
    if tipo == "producto":
        p = fetch_one(conn, f"""SELECT id, nombre, stock_actual, precio_publico, precio_costo, antibiotico,
                                       sustancia_activa, tipo_antibiotico, lote, fecha_caducidad,
                                       {estado_sql()} AS estado_caducidad
                                FROM productos WHERE id = %s AND status = 1 FOR UPDATE""", (item_id,))
        if not p:
            raise NegocioError(f"Producto ID {item_id} no encontrado.", 404)
        if not es_vendible(p["estado_caducidad"]):
            raise NegocioError(f"'{p['nombre']}' está {p['estado_caducidad'].lower()}. No se puede vender.", 409)
        return {"tipo": tipo, "producto_id": p["id"], "nombre": p["nombre"], "cantidad": cant,
                "stock": int(p["stock_actual"] or 0), "precio": num(p["precio_publico"]),
                "costo": num(p["precio_costo"]), "antibiotico": bool(p["antibiotico"]),
                "compuesto": p["sustancia_activa"] or p["nombre"], "tipo_antibiotico": p["tipo_antibiotico"],
                "lote": p["lote"], "fecha_caducidad": p["fecha_caducidad"]}
    if tipo == "honorario":
        return clinica_caja.linea_honorario(conn, item_id)
    tabla = TABLAS.get(tipo)
    if not tabla:
        raise NegocioError(f"Tipo de artículo inválido: {tipo}", 422)
    r = fetch_one(conn, f"SELECT id, nombre, precio FROM {tabla} WHERE id = %s AND status = 1", (item_id,))
    if not r:
        raise NegocioError(f"{tipo.capitalize()} ID {item_id} no encontrado.", 404)
    return {"tipo": tipo, "producto_id": None, "nombre": r["nombre"], "cantidad": cant, "stock": None,
            "precio": num(r["precio"]), "costo": 0.0, "antibiotico": False}


def procesar(conn, carrito, metodo_pago_id, usuario_id, pago=None, cliente_id=None, receta_id=None,
             paciente_id=None, antibiotico=None):
    if not carrito:
        raise NegocioError("El carrito está vacío.", 422)
    metodo = fetch_one(conn, "SELECT id, nombre FROM metodos_pago WHERE id = %s AND status = 1", (metodo_pago_id,))
    if not metodo:
        raise NegocioError("Selecciona un método de pago válido.", 422)
    es_efectivo = "efectivo" in (metodo["nombre"] or "").lower()
    cliente_id = int(cliente_id or 0) or CLIENTE_GENERAL

    with transaction(conn):
        if cliente_id != CLIENTE_GENERAL and not fetch_one(
                conn, "SELECT id FROM clientes WHERE id = %s AND status = 1", (cliente_id,)):
            cliente_id = CLIENTE_GENERAL

        lineas = [_linea(conn, it) for it in carrito]
        registro_ab = antibioticos.limpiar_registro(antibiotico) if any(ln.get("antibiotico") for ln in lineas) else None
        cobradas = [ln["consulta_id"] for ln in lineas if ln["tipo"] == "honorario"]
        if len(cobradas) != len(set(cobradas)):
            raise NegocioError("La misma consulta aparece dos veces en el carrito.", 422)
        if receta_id:
            paciente_id = paciente_id or clinica_caja.validar_receta(conn, receta_id)["paciente_id"]
        paciente_id = paciente_id or next((ln["paciente_id"] for ln in lineas if ln["tipo"] == "honorario"), None)
        if paciente_id and cliente_id == CLIENTE_GENERAL:
            cliente_id = clinica_caja.cliente_para_paciente(conn, paciente_id)
        requeridos = {}
        for ln in lineas:
            if ln["tipo"] == "producto":
                requeridos.setdefault(ln["producto_id"], [ln, 0])[1] += ln["cantidad"]
        for ln, cant in requeridos.values():
            if cant > ln["stock"]:
                raise NegocioError(f"Stock insuficiente para: {ln['nombre']}. Disponible: {ln['stock']}", 409)

        total = round(sum(ln["precio"] * ln["cantidad"] for ln in lineas), 2)
        if es_efectivo:
            recibido = round(num(pago, total), 2)
            if recibido + 0.005 < total:
                raise NegocioError(f"Pago insuficiente. Faltan ${total - recibido:,.2f}", 422)
            cambio = round(recibido - total, 2)
        else:
            recibido, cambio = total, 0.0

        if not corte_abierto(conn, usuario_id):
            execute(conn, """INSERT INTO cortes_caja (usuario_id, fecha_apertura, monto_inicial, cerrado, status)
                             VALUES (%s, NOW(), 0, 0, 1)""", (usuario_id,))

        venta_id = folio = None
        for intento in range(folios.INTENTOS):
            folio = folios.siguiente(lambda sql, prm: fetch_one(conn, sql, prm), usuario_id, intento)
            try:
                venta_id = execute(
                    conn,
                    """INSERT INTO ventas (folio, usuario_id, cliente_id, metodo_pago_id, total, pago_recibido,
                                           cambio_entregado, fecha, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), 1)""",
                    (folio, usuario_id, cliente_id, metodo["id"], total, recibido, cambio),
                )
                break
            except Exception as exc:
                if not folios.es_duplicado(exc):
                    raise
        if venta_id is None:
            raise NegocioError("No se pudo generar el folio de la venta. Intenta de nuevo.", 409)
        for ln in lineas:
            execute(conn, """INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio_unitario,
                                                         precio_costo_momento, subtotal, status)
                             VALUES (%s, %s, %s, %s, %s, %s, 1)""",
                    (venta_id, ln["producto_id"], ln["cantidad"], ln["precio"], ln["costo"],
                     round(ln["precio"] * ln["cantidad"], 2)))
            if ln["tipo"] == "producto":
                execute(conn, "UPDATE productos SET stock_actual = stock_actual - %s WHERE id = %s",
                        (ln["cantidad"], ln["producto_id"]))
        clinica_caja.registrar_cobro(conn, venta_id, lineas, receta_id)
        if registro_ab:
            antibioticos.guardar(conn, venta_id, usuario_id, registro_ab, lineas)

    return {"venta_id": venta_id, "folio": folio, "total": total, "pago": recibido, "cambio": cambio,
            "metodo": metodo["nombre"], "contiene_antibioticos": any(l["antibiotico"] for l in lineas)}


def obtener(conn, venta_id, usuario_id=None):
    """Venta con detalle. Si `usuario_id` se indica, solo devuelve ventas de ese usuario."""
    v = fetch_one(conn, """SELECT v.id, v.folio, v.fecha, v.total, v.pago_recibido, v.cambio_entregado,
                                  v.usuario_id, u.nombre AS vendedor, c.nombre AS cliente,
                                  mp.nombre AS metodo_pago
                           FROM ventas v JOIN usuarios u ON u.id = v.usuario_id
                           LEFT JOIN clientes c ON c.id = v.cliente_id
                           JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
                           WHERE v.id = %s AND v.status = 1""", (venta_id,))
    if not v or (usuario_id is not None and v["usuario_id"] != usuario_id):
        raise NegocioError("Venta no encontrada", 404)
    detalle = fetch_all(conn, """SELECT dv.producto_id, IFNULL(p.nombre, 'Servicio / Consulta') AS nombre,
                                        dv.cantidad, dv.precio_unitario, dv.subtotal,
                                        IFNULL(p.antibiotico, 0) AS antibiotico
                                 FROM detalle_ventas dv LEFT JOIN productos p ON p.id = dv.producto_id
                                 WHERE dv.venta_id = %s ORDER BY dv.id""", (venta_id,))
    return {
        "id": v["id"], "folio": v["folio"], "fecha": v["fecha"].isoformat(sep=" ") if v["fecha"] else None,
        "vendedor": v["vendedor"], "cliente": v["cliente"] or "Público General", "metodo_pago": v["metodo_pago"],
        "total": num(v["total"]), "pago_recibido": num(v["pago_recibido"]),
        "cambio_entregado": num(v["cambio_entregado"]),
        "detalle": [{"producto_id": d["producto_id"], "nombre": d["nombre"], "cantidad": int(d["cantidad"]),
                     "precio_unitario": num(d["precio_unitario"]), "subtotal": num(d["subtotal"]),
                     "antibiotico": bool(d["antibiotico"])} for d in detalle],
    }


def listar(conn, desde=None, hasta=None, usuario_id=None, folio=None, limite=200):
    sql = """SELECT v.id, v.folio, v.fecha, v.total, u.nombre AS vendedor, mp.nombre AS metodo_pago,
                    IFNULL(c.nombre, 'Público General') AS cliente
             FROM ventas v JOIN usuarios u ON u.id = v.usuario_id
             JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
             LEFT JOIN clientes c ON c.id = v.cliente_id
             WHERE v.status = 1"""
    params = []
    if usuario_id:
        sql += " AND v.usuario_id = %s"
        params.append(usuario_id)
    if desde:
        sql += " AND DATE(v.fecha) >= %s"
        params.append(desde)
    if hasta:
        sql += " AND DATE(v.fecha) <= %s"
        params.append(hasta)
    if folio:
        sql += " AND v.folio LIKE %s"
        params.append(f"%{folio}%")
    sql += " ORDER BY v.fecha DESC LIMIT %s"
    params.append(int(limite))
    return [{"id": r["id"], "folio": r["folio"], "fecha": r["fecha"].isoformat(sep=" ") if r["fecha"] else None,
             "vendedor": r["vendedor"], "cliente": r["cliente"], "metodo_pago": r["metodo_pago"],
             "total": num(r["total"])} for r in fetch_all(conn, sql, params)]
