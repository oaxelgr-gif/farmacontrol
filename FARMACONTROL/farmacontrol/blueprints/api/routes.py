"""API JSON del punto de venta (búsqueda, clientes, catálogos y cobro)."""
from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from ...db import execute, fetch_all, fetch_one, to_float
from ...models import ROL_ADMIN
from ...services import api_client, caducidad
from ...services import ventas as svc_ventas

bp = Blueprint("api", __name__, url_prefix="/api")


def _producto_json(p):
    return {
        "id": p["id"],
        "nombre": p["nombre"],
        "precio": to_float(p["precio_publico"]),
        "stock": int(p["stock_actual"] or 0),
        "stock_actual": int(p["stock_actual"] or 0),
        "antibiotico": bool(p["antibiotico"]),
        "codigo_barras": p.get("codigo_barras"),
        "estado_caducidad": p["estado_caducidad"],
        "tipo": "producto",
    }


@bp.route("/buscar_producto")
@login_required
def buscar_producto():
    query = (request.args.get("query") or "").strip()
    if not query:
        return jsonify(success=False, message="Consulta vacía")

    if api_client.activo():
        try:
            code, cuerpo = api_client.llamar("GET", "/v1/productos/buscar", params={
                "q": query, "incluir_bloqueados": request.args.get("mostrar_caducados", "false")})
            if code == 200:
                data = cuerpo["data"]
                if cuerpo["tipo"] == "exacto":
                    return jsonify(success=True, tipo="exacto", data=data[0])
                return jsonify(success=True, tipo="lista", data=data)
            return jsonify(success=False, message=api_client.mensaje(cuerpo, "No encontrado"))
        except api_client.ApiNoDisponible:
            pass  # respaldo local

    mostrar_todos = request.args.get("mostrar_caducados", "false").lower() == "true" \
        and current_user.rol == ROL_ADMIN
    filtro = "" if mostrar_todos else caducidad.condicion_vendible()
    estado = caducidad.estado_sql()

    # 1. Coincidencia exacta por código de barras (lector)
    exacto = fetch_one(
        f"""SELECT id, nombre, codigo_barras, precio_publico, stock_actual, antibiotico,
                   fecha_caducidad, {estado} AS estado_caducidad
            FROM productos
            WHERE codigo_barras = %s AND status = 1""",
        (query,),
    )
    if exacto:
        if int(exacto["stock_actual"] or 0) <= 0:
            return jsonify(success=False, message=f"«{exacto['nombre']}» no tiene existencias.")
        if not mostrar_todos and not caducidad.es_vendible(exacto["estado_caducidad"]):
            return jsonify(success=False,
                           message=f"Producto {exacto['estado_caducidad'].lower()}. No se puede vender.",
                           estado=exacto["estado_caducidad"])
        return jsonify(success=True, tipo="exacto", data=_producto_json(exacto))

    # 2. Búsqueda por nombre / código parcial
    resultados = fetch_all(
        f"""SELECT id, nombre, codigo_barras, precio_publico, stock_actual, antibiotico,
                   fecha_caducidad, {estado} AS estado_caducidad
            FROM productos
            WHERE (nombre LIKE %s OR codigo_barras LIKE %s)
              AND status = 1 AND stock_actual > 0 {filtro}
            ORDER BY nombre LIMIT 15""",
        (f"%{query}%", f"%{query}%"),
    )
    if resultados:
        return jsonify(success=True, tipo="lista", data=[_producto_json(r) for r in resultados])

    bloqueados = fetch_one(
        "SELECT COUNT(*) AS n FROM productos WHERE nombre LIKE %s AND status = 1 AND stock_actual > 0",
        (f"%{query}%",),
    )
    if bloqueados and bloqueados["n"]:
        return jsonify(success=False,
                       message="Los productos encontrados están caducados o próximos a caducar.",
                       encontrados_caducados=bloqueados["n"])
    return jsonify(success=False, message="No encontrado o sin stock")


@bp.route("/clientes", methods=["GET"])
@login_required
def api_get_clientes():
    q = (request.args.get("q") or "").strip()
    if api_client.activo():
        try:
            code, cuerpo = api_client.llamar("GET", "/v1/clientes", params={"q": q})
            if code == 200:
                return jsonify(cuerpo)
        except api_client.ApiNoDisponible:
            pass
    sql = "SELECT id, nombre, rfc_nit, telefono, email FROM clientes WHERE status = 1"
    params = []
    if q:
        sql += " AND (nombre LIKE %s OR rfc_nit LIKE %s OR telefono LIKE %s)"
        params += [f"%{q}%"] * 3
    sql += " ORDER BY nombre LIMIT 25"
    return jsonify(fetch_all(sql, params))


@bp.route("/clientes/nuevo", methods=["POST"])
@login_required
def api_nuevo_cliente():
    f = request.get_json(silent=True) or request.form
    nombre = (f.get("nombre") or "").strip()
    if not nombre:
        return jsonify(success=False, message="Nombre requerido")
    if api_client.activo():
        try:
            datos = {k: (f.get(k) or None) for k in ("rfc_nit", "telefono", "email", "direccion")}
            code, cuerpo = api_client.llamar("POST", "/v1/clientes", json={"nombre": nombre, **datos})
            if code == 201:
                return jsonify(success=True, id=cuerpo["id"], nombre=cuerpo["nombre"])
            return jsonify(success=False, message=api_client.mensaje(cuerpo))
        except api_client.ApiNoDisponible:
            pass
    try:
        nuevo_id = execute(
            """INSERT INTO clientes (nombre, rfc_nit, direccion, telefono, email, status)
               VALUES (%s, %s, %s, %s, %s, 1)""",
            (nombre, (f.get("rfc_nit") or "").strip() or None, (f.get("direccion") or "").strip() or None,
             (f.get("telefono") or "").strip() or None, (f.get("email") or "").strip() or None),
        )
    except Exception as exc:
        return jsonify(success=False, message=f"No se pudo guardar: {exc}")
    return jsonify(success=True, id=nuevo_id, nombre=nombre)


@bp.route("/items/<tipo>")
@login_required
def api_get_items(tipo):
    if api_client.activo():
        try:
            code, cuerpo = api_client.llamar("GET", f"/v1/catalogo/{tipo}", params={
                "incluir_bloqueados": request.args.get("mostrar_caducados", "false")})
            if code == 200:
                return jsonify(cuerpo)
            if code == 404:
                return jsonify([])
        except api_client.ApiNoDisponible:
            pass
    if tipo == "productos":
        mostrar_todos = request.args.get("mostrar_caducados", "false").lower() == "true" \
            and current_user.rol == ROL_ADMIN
        filtro = "" if mostrar_todos else caducidad.condicion_vendible()
        productos = fetch_all(
            f"""SELECT id, nombre, codigo_barras, precio_publico, stock_actual, antibiotico,
                       fecha_caducidad, {caducidad.estado_sql()} AS estado_caducidad
                FROM productos
                WHERE status = 1 AND stock_actual > 0 {filtro}
                ORDER BY nombre""")
        return jsonify([_producto_json(p) for p in productos])

    tablas = {"procedimientos": ("servicios", "servicio"), "consultas": ("consultas", "consulta")}
    if tipo not in tablas:
        return jsonify([])
    tabla, tipo_item = tablas[tipo]
    filas = fetch_all(f"SELECT id, nombre, precio FROM {tabla} WHERE status = 1 ORDER BY nombre")
    return jsonify([{"id": r["id"], "nombre": r["nombre"], "precio": to_float(r["precio"]),
                     "tipo": tipo_item} for r in filas])


@bp.route("/validar_producto_caducidad/<int:producto_id>")
@login_required
def validar_producto_caducidad(producto_id):
    if api_client.activo():
        try:
            code, cuerpo = api_client.llamar("GET", f"/v1/productos/{producto_id}/caducidad")
            if code == 200:
                return jsonify(success=True, **cuerpo)
            return jsonify(success=False, message=api_client.mensaje(cuerpo))
        except api_client.ApiNoDisponible:
            pass
    p = fetch_one(
        f"""SELECT nombre, fecha_caducidad, {caducidad.estado_sql()} AS estado_caducidad,
                   DATEDIFF(fecha_caducidad, CURDATE()) AS dias_restantes
            FROM productos WHERE id = %s AND status = 1""",
        (producto_id,),
    )
    if not p:
        return jsonify(success=False, message="Producto no encontrado")
    return jsonify(success=True, producto=p["nombre"], estado_caducidad=p["estado_caducidad"],
                   dias_restantes=p["dias_restantes"], es_valido=caducidad.es_vendible(p["estado_caducidad"]))


@bp.route("/procesar_venta", methods=["POST"])
@login_required
def api_procesar_venta():
    data = request.get_json(silent=True) or {}
    if api_client.activo():
        try:
            return _venta_por_api(data)
        except api_client.ApiNoDisponible:
            current_app.logger.warning("Venta procesada localmente: API no disponible")
    try:
        res = svc_ventas.procesar_venta(data, current_user.id)
    except svc_ventas.VentaError as exc:
        return jsonify(success=False, message=str(exc))
    except Exception as exc:
        return jsonify(success=False, message=f"Error en servidor: {exc}"), 500
    return jsonify(success=True, venta_id=res["venta_id"], folio=res["folio"],
                   total_vendido=res["total"], monto_entrega=res["total"],
                   pago=res["pago"], cambio=res["cambio"], metodo=res["metodo"])


def _venta_por_api(data):
    """Normaliza el carrito del POS y lo envía a POST /v1/ventas."""
    carrito = []
    for it in data.get("carrito") or []:
        tipo = (it.get("tipo") or "").lower() or ("producto" if it.get("esProducto", True) else "servicio")
        carrito.append({"id": int(it.get("id") or 0), "tipo": tipo,
                        "cant": int(it.get("cant") or it.get("cantidad") or 0)})
    payload = {"carrito": carrito, "metodo_pago_id": int(data.get("metodo_pago_id") or 0),
               "pago": data.get("pago"), "cliente_id": data.get("cliente_id") or None,
               "receta_id": data.get("receta_id") or None, "paciente_id": data.get("paciente_id") or None}
    code, cuerpo = api_client.llamar("POST", "/v1/ventas", json=payload)
    if code != 201:
        return jsonify(success=False, message=api_client.mensaje(cuerpo, "No se pudo registrar la venta"))
    return jsonify(success=True, venta_id=cuerpo["venta_id"], folio=cuerpo["folio"],
                   total_vendido=cuerpo["total"], monto_entrega=cuerpo["total"],
                   pago=cuerpo["pago"], cambio=cuerpo["cambio"], metodo=cuerpo["metodo"], via="api")


@bp.route("/cuenta_paciente")
@login_required
def cuenta_paciente():
    """Cuenta del consultorio para el POS: honorarios pendientes + medicamentos de la receta."""
    from ...services import clinica_caja
    from ...utils.helpers import to_int

    receta_id = to_int(request.args.get("receta"), 0) or None
    if not receta_id and request.args.get("folio"):
        receta_id = clinica_caja.receta_por_folio(request.args.get("folio"))
        if not receta_id:
            return jsonify(success=False, message="No existe una receta con ese folio.")
    try:
        datos = clinica_caja.cuenta(to_int(request.args.get("consulta"), 0) or None, receta_id)
    except clinica_caja.CuentaError as exc:
        return jsonify(success=False, message=str(exc))
    return jsonify(success=True, data=datos)
