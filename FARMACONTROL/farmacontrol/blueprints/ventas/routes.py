"""Punto de venta, historial de tickets, detalle y reimpresión."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ...db import fetch_all, to_float
from ...models import ROL_ADMIN
from ...services import ventas as svc
from ...services.catalogos import metodos_pago, usuarios_activos
from ...services.cortes import corte_abierto
from ...utils.helpers import parse_fecha, to_int

bp = Blueprint("ventas", __name__)


def _render_pos(es_admin):
    clientes = fetch_all("SELECT id, nombre, rfc_nit FROM clientes WHERE status = 1 ORDER BY nombre LIMIT 20")
    return render_template(
        "ventas/pos.html",
        metodos=metodos_pago(),
        clientes=clientes,
        es_admin_pos=es_admin,
        corte=corte_abierto(current_user.id),
        # ?consulta=ID / ?receta=ID / ?folio=R000001 → precarga la cuenta del paciente
        cuenta_inicial={k: request.args.get(k) for k in ("consulta", "receta", "folio") if request.args.get(k)},
    )


@bp.route("/punto_venta")
@login_required
def punto_venta():
    if current_user.rol != ROL_ADMIN:
        return redirect(url_for("ventas.punto_farmacia", **request.args))
    return _render_pos(True)


@bp.route("/punto_farmacia")
@login_required
def punto_farmacia():
    return _render_pos(current_user.rol == ROL_ADMIN)


def _puede_ver(venta_usuario_id):
    return current_user.rol == ROL_ADMIN or venta_usuario_id == current_user.id


@bp.route("/reimprimir_tickets")
@login_required
def reimprimir_tickets():
    es_admin = current_user.rol == ROL_ADMIN
    usuario_id = request.args.get("usuario_id", "") if es_admin else ""
    fi = parse_fecha(request.args.get("fecha_inicio"))
    ff = parse_fecha(request.args.get("fecha_fin"))
    folio = (request.args.get("folio") or "").strip()

    sql = """SELECT v.id, v.folio, v.fecha, v.total, v.pago_recibido, v.cambio_entregado,
                    u.nombre AS vendedor, c.nombre AS cliente, mp.nombre AS metodo_pago
             FROM ventas v
             JOIN usuarios u ON v.usuario_id = u.id
             LEFT JOIN clientes c ON v.cliente_id = c.id
             JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
             WHERE v.status = 1"""
    params = []
    if not es_admin:
        sql += " AND v.usuario_id = %s"
        params.append(current_user.id)
    elif usuario_id:
        sql += " AND v.usuario_id = %s"
        params.append(to_int(usuario_id))
    if fi:
        sql += " AND DATE(v.fecha) >= %s"
        params.append(fi)
    if ff:
        sql += " AND DATE(v.fecha) <= %s"
        params.append(ff)
    if folio:
        sql += " AND v.folio LIKE %s"
        params.append(f"%{folio}%")
    sql += " ORDER BY v.fecha DESC LIMIT 500"
    ventas = fetch_all(sql, params)

    return render_template(
        "ventas/tickets.html",
        ventas=ventas,
        usuarios=usuarios_activos() if es_admin else [],
        usuario_id=usuario_id,
        fecha_inicio=fi.strftime("%Y-%m-%d") if fi else "",
        fecha_fin=ff.strftime("%Y-%m-%d") if ff else "",
        folio=folio,
        total_ventas=len(ventas),
        total_importe=sum(to_float(v["total"]) for v in ventas),
    )


@bp.route("/ver_detalle_venta/<int:venta_id>")
@login_required
def ver_detalle_venta(venta_id):
    venta = svc.obtener_venta(venta_id)
    if not venta:
        flash("Venta no encontrada.", "danger")
        return redirect(url_for("ventas.reimprimir_tickets"))
    if not _puede_ver(venta["usuario_id"]):
        flash("No tienes permiso para ver esta venta.", "danger")
        return redirect(url_for("ventas.reimprimir_tickets"))

    detalles = svc.detalle_venta(venta_id)
    total_productos = sum(int(d["cantidad"] or 0) for d in detalles)
    total_costo = sum((d["cantidad"] or 0) * to_float(d["precio_costo_momento"]) for d in detalles)
    utilidad = to_float(venta["total"]) - total_costo
    return render_template(
        "ventas/detalle.html",
        venta=venta,
        detalles=detalles,
        total_productos=total_productos,
        total_costo=total_costo,
        utilidad=utilidad,
        antibioticos=[d for d in detalles if d["antibiotico"]],
    )


@bp.route("/ticket/reimprimir/<int:venta_id>")
@login_required
def reimprimir_ticket(venta_id):
    venta = svc.obtener_venta(venta_id)
    if not venta or not venta["status"]:
        flash("Venta no encontrada.", "danger")
        return redirect(url_for("ventas.reimprimir_tickets"))
    if not _puede_ver(venta["usuario_id"]):
        flash("No tienes permiso para reimprimir esta venta.", "danger")
        return redirect(url_for("ventas.reimprimir_tickets"))
    return render_template(
        "tickets/venta.html",
        venta=venta,
        detalles=svc.detalle_venta(venta_id),
        pago=venta["pago_recibido"],
        cambio=venta["cambio_entregado"],
        reimpresion=request.args.get("reimpresion") == "1",
    )
