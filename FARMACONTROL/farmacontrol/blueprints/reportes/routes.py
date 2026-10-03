"""Módulo de reportes y analítica."""
from datetime import timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ...db import fetch_all, fetch_one, fetch_value, to_float
from ...services import caducidad
from ...services.catalogos import farmaceuticos, metodos_pago
from ...utils.decorators import admin_required
from ...utils.helpers import hoy, rango_fechas, to_int

bp = Blueprint("reportes", __name__)


# ---------------------------------------------------------------------------
# Panel principal
# ---------------------------------------------------------------------------
@bp.route("/reportes_farmacia_principal")
@login_required
@admin_required
def dashboard():
    dia = hoy()
    return render_template(
        "reportes/index.html",
        ventas_hoy=fetch_one(
            """SELECT COUNT(*) AS ventas_hoy, IFNULL(SUM(total), 0) AS ingresos_hoy
               FROM ventas WHERE DATE(fecha) = %s AND status = 1""", (dia,)) or {},
        stock_bajo=fetch_value(
            "SELECT COUNT(*) AS n FROM productos WHERE stock_actual <= stock_minimo AND status = 1"),
        antibioticos_hoy=fetch_value(
            """SELECT IFNULL(SUM(dv.cantidad), 0) AS n
               FROM detalle_ventas dv
               JOIN productos p ON dv.producto_id = p.id
               JOIN ventas v ON dv.venta_id = v.id
               WHERE p.antibiotico = 1 AND DATE(v.fecha) = %s AND v.status = 1""", (dia,)),
        cortes_abiertos=fetch_value(
            "SELECT COUNT(*) AS n FROM cortes_caja WHERE cerrado = 0 AND status = 1"),
        por_caducar=fetch_value(
            f"""SELECT COUNT(*) AS n FROM productos WHERE status = 1 AND stock_actual > 0
                AND fecha_caducidad <= CURDATE() + INTERVAL {caducidad.dias_alerta()} DAY"""),
    )


# ---------------------------------------------------------------------------
# 1. Financiero
# ---------------------------------------------------------------------------
@bp.route("/reportes/financiero")
@login_required
@admin_required
def financiero():
    f_inicio, f_fin = rango_fechas(request.args, "inicio", "fin")
    try:
        cab = fetch_one(
            """SELECT IFNULL(SUM(total), 0) AS ingresos, COUNT(*) AS total_ventas
               FROM ventas WHERE status = 1 AND DATE(fecha) BETWEEN %s AND %s""",
            (f_inicio, f_fin)) or {}
        costo = fetch_value(
            """SELECT IFNULL(SUM(dv.cantidad * dv.precio_costo_momento), 0) AS costo
               FROM detalle_ventas dv JOIN ventas v ON v.id = dv.venta_id
               WHERE v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s""",
            (f_inicio, f_fin))
        ingresos = to_float(cab.get("ingresos"))
        total_ventas = int(cab.get("total_ventas") or 0)

        v_diaria = fetch_all(
            """SELECT DATE(fecha) AS fecha, SUM(total) AS total_dia, COUNT(*) AS cantidad
               FROM ventas WHERE status = 1 AND DATE(fecha) BETWEEN %s AND %s
               GROUP BY DATE(fecha) ORDER BY DATE(fecha) ASC""", (f_inicio, f_fin))
        metodos = fetch_all(
            """SELECT mp.nombre AS metodo, COUNT(v.id) AS cantidad, SUM(v.total) AS monto
               FROM ventas v JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
               WHERE v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s
               GROUP BY mp.nombre ORDER BY monto DESC""", (f_inicio, f_fin))
        tabla = fetch_all(
            """SELECT v.id, v.fecha, v.folio, u.nombre AS vendedor,
                      IFNULL(c.nombre, 'Público General') AS cliente, mp.nombre AS metodo,
                      v.total, v.pago_recibido, v.cambio_entregado
               FROM ventas v
               LEFT JOIN usuarios u ON v.usuario_id = u.id
               LEFT JOIN clientes c ON v.cliente_id = c.id
               LEFT JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
               WHERE v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s
               ORDER BY v.fecha DESC""", (f_inicio, f_fin))
        por_hora = fetch_all(
            """SELECT HOUR(fecha) AS hora, COUNT(*) AS cantidad, SUM(total) AS monto
               FROM ventas WHERE status = 1 AND DATE(fecha) BETWEEN %s AND %s
               GROUP BY HOUR(fecha) ORDER BY hora ASC""", (f_inicio, f_fin))
    except Exception as exc:
        flash(f"Error: {exc}", "danger")
        return redirect(url_for("reportes.dashboard"))

    ganancias = ingresos - to_float(costo)
    return render_template(
        "reportes/financiero.html",
        ingresos=ingresos,
        ganancias=ganancias,
        margen=(ganancias / ingresos * 100) if ingresos else 0,
        total_ventas=total_ventas,
        ticket_promedio=(ingresos / total_ventas) if total_ventas else 0,
        v_diaria=v_diaria, metodos=metodos, tabla=tabla, por_hora=por_hora,
        f_inicio=f_inicio, f_fin=f_fin,
    )


# ---------------------------------------------------------------------------
# 2. Antibióticos
# ---------------------------------------------------------------------------
@bp.route("/reportes/antibioticos_mejorado")
@login_required
@admin_required
def antibioticos():
    fecha_inicio, fecha_fin = rango_fechas(request.args, "fecha_inicio", "fecha_fin")
    usuario_id = request.args.get("usuario_id", "")
    producto_id = request.args.get("producto_id", "")

    where = " WHERE p.antibiotico = 1 AND v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s"
    params = [fecha_inicio, fecha_fin]
    if usuario_id:
        where += " AND v.usuario_id = %s"
        params.append(to_int(usuario_id))
    if producto_id:
        where += " AND p.id = %s"
        params.append(to_int(producto_id))

    base = """FROM detalle_ventas dv
              JOIN productos p ON dv.producto_id = p.id
              JOIN ventas v ON dv.venta_id = v.id
              JOIN usuarios u ON v.usuario_id = u.id
              LEFT JOIN clientes c ON v.cliente_id = c.id"""

    registros = fetch_all(
        f"""SELECT v.id AS venta_id, v.fecha, v.folio, u.nombre AS vendedor, p.nombre AS producto,
                   p.lote, dv.cantidad, dv.precio_unitario, dv.precio_costo_momento, dv.subtotal,
                   (dv.subtotal - (dv.cantidad * dv.precio_costo_momento)) AS utilidad,
                   c.nombre AS cliente
            {base} {where} ORDER BY v.fecha DESC""", params)
    estadisticas = fetch_one(
        f"""SELECT COUNT(DISTINCT v.id) AS total_ventas, IFNULL(SUM(dv.cantidad), 0) AS total_unidades,
                   IFNULL(SUM(dv.subtotal), 0) AS total_venta,
                   IFNULL(SUM(dv.subtotal - (dv.cantidad * dv.precio_costo_momento)), 0) AS total_utilidad
            {base} {where}""", params) or {}
    top_productos = fetch_all(
        f"""SELECT p.nombre, SUM(dv.cantidad) AS cantidad_vendida, SUM(dv.subtotal) AS total_venta
            {base} {where} GROUP BY p.id, p.nombre ORDER BY cantidad_vendida DESC LIMIT 10""", params)
    por_vendedor = fetch_all(
        f"""SELECT u.nombre AS vendedor, COUNT(DISTINCT v.id) AS ventas_realizadas,
                   SUM(dv.cantidad) AS unidades_vendidas, SUM(dv.subtotal) AS total_venta
            {base} {where} GROUP BY u.id, u.nombre ORDER BY unidades_vendidas DESC""", params)

    return render_template(
        "reportes/antibioticos.html",
        registros=registros,
        usuarios=farmaceuticos(),
        antibioticos=fetch_all(
            "SELECT id, nombre FROM productos WHERE antibiotico = 1 AND status = 1 ORDER BY nombre"),
        fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
        usuario_id=usuario_id, producto_id=producto_id,
        estadisticas=estadisticas, top_productos=top_productos, por_vendedor=por_vendedor,
    )


# ---------------------------------------------------------------------------
# 3. Ventas detalladas
# ---------------------------------------------------------------------------
@bp.route("/reportes/ventas_detalladas")
@login_required
@admin_required
def ventas_detalladas():
    fecha_inicio, fecha_fin = rango_fechas(request.args, "fecha_inicio", "fecha_fin")
    usuario_id = request.args.get("usuario_id", "")
    metodo_pago = request.args.get("metodo_pago", "")
    cliente_id = request.args.get("cliente_id", "")

    sql = """SELECT v.id, v.folio, v.fecha, v.total, v.pago_recibido, v.cambio_entregado,
                    u.nombre AS vendedor, c.nombre AS cliente, mp.nombre AS metodo_pago,
                    (SELECT GROUP_CONCAT(CONCAT(IFNULL(p.nombre, 'Servicio'), ' (', dv2.cantidad, ')') SEPARATOR ', ')
                       FROM detalle_ventas dv2 LEFT JOIN productos p ON dv2.producto_id = p.id
                      WHERE dv2.venta_id = v.id) AS productos_resumen
             FROM ventas v
             JOIN usuarios u ON v.usuario_id = u.id
             LEFT JOIN clientes c ON v.cliente_id = c.id
             JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
             WHERE v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s"""
    params = [fecha_inicio, fecha_fin]
    if usuario_id:
        sql += " AND v.usuario_id = %s"
        params.append(to_int(usuario_id))
    if metodo_pago:
        sql += " AND v.metodo_pago_id = %s"
        params.append(to_int(metodo_pago))
    if cliente_id:
        sql += " AND v.cliente_id = %s"
        params.append(to_int(cliente_id))
    ventas = fetch_all(sql + " ORDER BY v.fecha DESC", params)

    def _es(v, palabra):
        return palabra in (v["metodo_pago"] or "").lower()

    return render_template(
        "reportes/ventas.html",
        ventas=ventas,
        usuarios=farmaceuticos(),
        metodos=metodos_pago(),
        clientes=fetch_all("SELECT id, nombre FROM clientes WHERE status = 1 ORDER BY nombre LIMIT 100"),
        fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
        usuario_id=usuario_id, metodo_pago=metodo_pago, cliente_id=cliente_id,
        total_general=sum(to_float(v["total"]) for v in ventas),
        total_ventas=len(ventas),
        total_efectivo=sum(to_float(v["total"]) for v in ventas if _es(v, "efectivo")),
        total_tarjeta=sum(to_float(v["total"]) for v in ventas if _es(v, "tarjeta")),
        ventas_por_dia=fetch_all(
            """SELECT DATE(fecha) AS fecha, COUNT(*) AS cantidad, SUM(total) AS monto
               FROM ventas WHERE status = 1 AND DATE(fecha) BETWEEN %s AND %s
               GROUP BY DATE(fecha) ORDER BY fecha DESC LIMIT 31""", (fecha_inicio, fecha_fin)),
        ventas_por_vendedor=fetch_all(
            """SELECT u.nombre AS vendedor, COUNT(*) AS ventas, SUM(v.total) AS monto
               FROM ventas v JOIN usuarios u ON v.usuario_id = u.id
               WHERE v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s
               GROUP BY u.id, u.nombre ORDER BY monto DESC""", (fecha_inicio, fecha_fin)),
    )


# ---------------------------------------------------------------------------
# 4. Productos más vendidos
# ---------------------------------------------------------------------------
@bp.route("/reportes/productos")
@login_required
@admin_required
def productos():
    fecha_inicio, fecha_fin = rango_fechas(request.args, "fecha_inicio", "fecha_fin")
    rango = (fecha_inicio, fecha_fin)
    base = """FROM detalle_ventas dv
              JOIN productos p ON dv.producto_id = p.id
              LEFT JOIN secciones s ON p.seccion_id = s.id
              JOIN ventas v ON dv.venta_id = v.id
              WHERE v.status = 1 AND DATE(v.fecha) BETWEEN %s AND %s"""
    try:
        top = fetch_all(
            f"""SELECT p.nombre, p.codigo_barras, s.nombre AS seccion, p.antibiotico,
                       SUM(dv.cantidad) AS cantidad_vendida, SUM(dv.subtotal) AS total_venta,
                       AVG(dv.precio_unitario) AS precio_promedio,
                       COUNT(DISTINCT dv.venta_id) AS veces_vendido
                {base}
                GROUP BY p.id, p.nombre, p.codigo_barras, s.nombre, p.antibiotico
                ORDER BY cantidad_vendida DESC LIMIT 20""", rango)
        comparativa = fetch_all(
            f"""SELECT CASE WHEN p.antibiotico = 1 THEN 'Antibióticos' ELSE 'General' END AS categoria,
                       SUM(dv.cantidad) AS cantidad, SUM(dv.subtotal) AS venta_total,
                       COUNT(DISTINCT dv.venta_id) AS transacciones
                {base} GROUP BY p.antibiotico ORDER BY p.antibiotico DESC""", rango)
        por_seccion = fetch_all(
            f"""SELECT IFNULL(s.nombre, 'Sin sección') AS seccion, SUM(dv.cantidad) AS cantidad,
                       SUM(dv.subtotal) AS venta_total
                {base} GROUP BY s.id, s.nombre ORDER BY venta_total DESC LIMIT 10""", rango)
        estadisticas = fetch_one(
            f"""SELECT COUNT(DISTINCT p.id) AS productos_vendidos,
                       IFNULL(SUM(dv.cantidad), 0) AS unidades_vendidas,
                       IFNULL(SUM(dv.subtotal), 0) AS venta_total,
                       IFNULL(AVG(dv.cantidad), 0) AS promedio_unidades
                {base}""", rango) or {}
    except Exception as exc:
        flash(f"No se pudieron cargar los datos del reporte: {exc}", "danger")
        return redirect(url_for("reportes.dashboard"))

    return render_template("reportes/productos.html", top_productos=top, comparativa=comparativa,
                           por_seccion=por_seccion, estadisticas=estadisticas,
                           fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)


# ---------------------------------------------------------------------------
# 5. Stock bajo
# ---------------------------------------------------------------------------
@bp.route("/reportes/bajo-stock")
@login_required
@admin_required
def stock():
    productos = fetch_all(
        """SELECT p.id, p.codigo_barras, p.nombre, s.nombre AS seccion, p.stock_actual,
                  p.stock_minimo, p.precio_costo, p.precio_publico, p.antibiotico,
                  (p.stock_minimo - p.stock_actual) AS faltante,
                  CASE WHEN p.stock_minimo > 0
                       THEN ROUND((p.stock_actual / p.stock_minimo) * 100, 2) ELSE 0 END AS porcentaje
           FROM productos p LEFT JOIN secciones s ON p.seccion_id = s.id
           WHERE p.status = 1 AND p.stock_actual <= p.stock_minimo
           ORDER BY porcentaje ASC, p.nombre""")
    faltantes = [p for p in productos if (p["faltante"] or 0) > 0]
    return render_template(
        "reportes/stock.html",
        productos=productos,
        total_productos=len(productos),
        total_faltante=sum(int(p["faltante"]) for p in faltantes),
        valor_faltante=sum(int(p["faltante"]) * to_float(p["precio_costo"]) for p in faltantes),
        agotados=sum(1 for p in productos if (p["stock_actual"] or 0) <= 0),
    )


# ---------------------------------------------------------------------------
# 6. Caducidad (disponible para todos los roles)
# ---------------------------------------------------------------------------
@bp.route("/reportes/caducidad", endpoint="caducidad")
@login_required
def caducidad_reporte():
    dias = caducidad.dias_alerta()
    limite = hoy() + timedelta(days=dias)
    productos = []
    try:
        productos = fetch_all(
            """SELECT p.id, p.nombre, p.stock_actual, p.fecha_caducidad, p.lote, p.codigo_barras,
                      s.nombre AS seccion, p.precio_costo, p.precio_publico, p.antibiotico,
                      DATEDIFF(p.fecha_caducidad, CURDATE()) AS dias_restantes,
                      (p.stock_actual * p.precio_costo) AS valor_inventario
               FROM productos p LEFT JOIN secciones s ON p.seccion_id = s.id
               WHERE p.stock_actual > 0 AND p.fecha_caducidad IS NOT NULL
                 AND p.fecha_caducidad <= %s AND p.status = 1
               ORDER BY p.fecha_caducidad ASC""", (limite,))
    except Exception as exc:
        flash(f"Error al cargar el reporte: {exc}", "danger")

    return render_template(
        "reportes/caducidad.html",
        productos=productos,
        hoy=hoy(), limite=limite, dias_alerta=dias,
        total_productos=len(productos),
        total_unidades=sum(int(p["stock_actual"] or 0) for p in productos),
        total_valor=sum(to_float(p["valor_inventario"]) for p in productos),
        ya_vencidos=sum(1 for p in productos if (p["dias_restantes"] or 0) < 0),
        por_vencer=sum(1 for p in productos if (p["dias_restantes"] or 0) >= 0),
    )


# ---------------------------------------------------------------------------
# 7. Personal
# ---------------------------------------------------------------------------
@bp.route("/reportes/personal")
@login_required
@admin_required
def personal():
    f_inicio, f_fin = rango_fechas(request.args, "inicio", "fin")
    tabla = fetch_all(
        """SELECT u.id, u.nombre, u.username AS usuario,
                  COUNT(DISTINCT v.id) AS num_ventas,
                  IFNULL(SUM(v.total), 0) AS total_vendido,
                  IFNULL(AVG(v.total), 0) AS ticket_promedio,
                  (SELECT COUNT(DISTINCT DATE(v2.fecha)) FROM ventas v2
                    WHERE v2.usuario_id = u.id AND v2.status = 1
                      AND DATE(v2.fecha) BETWEEN %s AND %s) AS dias_trabajados,
                  (SELECT p.nombre FROM detalle_ventas dv
                     JOIN productos p ON dv.producto_id = p.id
                     JOIN ventas v2 ON dv.venta_id = v2.id
                    WHERE v2.usuario_id = u.id AND v2.status = 1
                      AND DATE(v2.fecha) BETWEEN %s AND %s
                    GROUP BY p.id, p.nombre ORDER BY SUM(dv.cantidad) DESC LIMIT 1) AS producto_top,
                  (SELECT COUNT(*) FROM cortes_caja cc
                    WHERE cc.usuario_id = u.id AND cc.cerrado = 1
                      AND DATE(cc.fecha_apertura) BETWEEN %s AND %s) AS cortes_realizados
           FROM usuarios u
           LEFT JOIN ventas v ON u.id = v.usuario_id AND v.status = 1
                AND DATE(v.fecha) BETWEEN %s AND %s
           WHERE u.status = 1
           GROUP BY u.id, u.nombre, u.username
           ORDER BY total_vendido DESC""",
        (f_inicio, f_fin) * 4)
    total_vendido = sum(to_float(u["total_vendido"]) for u in tabla)
    activos = [u for u in tabla if u["num_ventas"]]
    return render_template(
        "reportes/personal.html",
        tabla=tabla, f_inicio=f_inicio, f_fin=f_fin,
        total_ventas=sum(int(u["num_ventas"] or 0) for u in tabla),
        total_vendido=total_vendido,
        promedio_general=(total_vendido / len(activos)) if activos else 0,
    )


# ---------------------------------------------------------------------------
# 8. Clientes
# ---------------------------------------------------------------------------
@bp.route("/reportes/clientes")
@login_required
@admin_required
def clientes():
    f_inicio, f_fin = rango_fechas(request.args, "inicio", "fin")
    min_compras = to_int(request.args.get("min_compras"), 1, minimo=0)
    todos = fetch_all(
        """SELECT c.id, c.nombre AS cliente_nombre, c.telefono, c.email, c.rfc_nit,
                  COUNT(v.id) AS total_compras,
                  IFNULL(SUM(v.total), 0) AS total_gastado,
                  IFNULL(AVG(v.total), 0) AS promedio_compra,
                  MIN(v.fecha) AS primera_compra, MAX(v.fecha) AS ultima_compra,
                  CASE WHEN c.id = 1 OR c.nombre LIKE '%%General%%' THEN 1 ELSE 0 END AS es_general,
                  (SELECT p.nombre FROM detalle_ventas dv
                     JOIN productos p ON dv.producto_id = p.id
                     JOIN ventas v2 ON dv.venta_id = v2.id
                    WHERE v2.cliente_id = c.id AND v2.status = 1
                      AND DATE(v2.fecha) BETWEEN %s AND %s
                    GROUP BY p.id, p.nombre ORDER BY SUM(dv.cantidad) DESC LIMIT 1) AS producto_favorito
           FROM clientes c
           LEFT JOIN ventas v ON c.id = v.cliente_id AND v.status = 1
                AND DATE(v.fecha) BETWEEN %s AND %s
           WHERE c.status = 1
           GROUP BY c.id, c.nombre, c.telefono, c.email, c.rfc_nit
           HAVING COUNT(v.id) >= %s
           ORDER BY es_general ASC, total_gastado DESC""",
        (f_inicio, f_fin, f_inicio, f_fin, min_compras))
    reales = [c for c in todos if not c["es_general"]]
    return render_template(
        "reportes/clientes.html",
        tabla=todos, top_reales=reales,
        f_inicio=f_inicio, f_fin=f_fin, min_compras=min_compras,
        total_clientes=len(todos), total_clientes_reales=len(reales),
        total_ventas=sum(int(c["total_compras"] or 0) for c in todos),
        total_gastado=sum(to_float(c["total_gastado"]) for c in todos),
    )
