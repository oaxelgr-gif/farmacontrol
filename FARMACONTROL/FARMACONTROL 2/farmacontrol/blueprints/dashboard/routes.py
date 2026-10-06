"""Paneles de inicio para administrador y farmacéutico."""
from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from ...db import fetch_all, fetch_one, fetch_value, to_float
from ...models import ROL_ADMIN
from ...services import caducidad
from ...services.catalogos import SQL_SUMAS_POR_METODO
from ...services.cortes import corte_abierto, totales_periodo
from ...utils.decorators import admin_required
from ...utils.helpers import hoy

bp = Blueprint("dashboard", __name__)


@bp.route("/inicio")
@login_required
@admin_required
def inicio():
    dia = hoy()
    estadisticas = fetch_one(
        f"""SELECT {SQL_SUMAS_POR_METODO}
            FROM ventas v JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
            WHERE DATE(v.fecha) = %s AND v.status = 1""",
        (dia,),
    )
    dias = caducidad.dias_alerta()
    stock_bajo = fetch_value(
        "SELECT COUNT(*) AS n FROM productos WHERE stock_actual <= stock_minimo AND status = 1")
    proximos_caducar = fetch_value(
        f"""SELECT COUNT(*) AS n FROM productos
            WHERE fecha_caducidad <= CURDATE() + INTERVAL {dias} DAY
              AND fecha_caducidad >= CURDATE() AND status = 1""")
    antibioticos_bajo = fetch_value(
        """SELECT COUNT(*) AS n FROM productos
           WHERE antibiotico = 1 AND stock_actual <= stock_minimo AND status = 1""")
    cortes_abiertos = fetch_value(
        "SELECT COUNT(*) AS n FROM cortes_caja WHERE cerrado = 0 AND status = 1")
    ventas_recientes = fetch_all(
        """SELECT v.id, v.folio, v.fecha, u.nombre AS vendedor, v.total, mp.nombre AS metodo
           FROM ventas v
           JOIN usuarios u ON v.usuario_id = u.id
           JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
           WHERE DATE(v.fecha) = %s AND v.status = 1
           ORDER BY v.fecha DESC LIMIT 8""",
        (dia,),
    )
    top_productos = fetch_all(
        """SELECT p.nombre, SUM(dv.cantidad) AS cantidad_vendida
           FROM detalle_ventas dv
           JOIN productos p ON dv.producto_id = p.id
           JOIN ventas v ON dv.venta_id = v.id
           WHERE DATE(v.fecha) = %s AND v.status = 1
           GROUP BY p.id, p.nombre
           ORDER BY cantidad_vendida DESC LIMIT 5""",
        (dia,),
    )
    semana = fetch_all(
        """SELECT DATE(fecha) AS dia, IFNULL(SUM(total), 0) AS total
           FROM ventas
           WHERE status = 1 AND DATE(fecha) >= CURDATE() - INTERVAL 6 DAY
           GROUP BY DATE(fecha) ORDER BY dia""")

    return render_template(
        "dashboard/admin.html",
        estadisticas=estadisticas or {},
        stock_bajo=stock_bajo,
        proximos_caducar=proximos_caducar,
        antibioticos_bajo=antibioticos_bajo,
        ventas_recientes=ventas_recientes,
        top_productos=top_productos,
        cortes_abiertos=cortes_abiertos,
        semana=[{"dia": str(r["dia"])[:10], "total": to_float(r["total"])} for r in semana],
    )


@bp.route("/inicio_farmacia")
@login_required
def inicio_farmacia():
    if current_user.rol == ROL_ADMIN:
        return redirect(url_for("dashboard.inicio"))

    dia = hoy()
    estadisticas = fetch_one(
        f"""SELECT {SQL_SUMAS_POR_METODO}
            FROM ventas v JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
            WHERE DATE(v.fecha) = %s AND v.usuario_id = %s AND v.status = 1""",
        (dia, current_user.id),
    )
    corte = corte_abierto(current_user.id)
    totales_corte = totales_periodo(current_user.id, corte["fecha_apertura"]) if corte else None
    mis_ventas = fetch_all(
        """SELECT v.id, v.folio, v.fecha, v.total, mp.nombre AS metodo
           FROM ventas v JOIN metodos_pago mp ON mp.id = v.metodo_pago_id
           WHERE DATE(v.fecha) = %s AND v.usuario_id = %s AND v.status = 1
           ORDER BY v.fecha DESC LIMIT 6""",
        (dia, current_user.id),
    )
    return render_template(
        "dashboard/farmaceutico.html",
        estadisticas=estadisticas or {},
        corte=corte,
        corte_abierto=bool(corte),
        totales_corte=totales_corte,
        mis_ventas=mis_ventas,
    )
