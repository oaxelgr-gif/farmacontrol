"""Historial, auditoría, detalle, impresión y exportación de cortes (administración)."""
import csv
from datetime import datetime
from io import StringIO

from flask import Blueprint, Response, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from ...db import fetch_all, to_float
from ...services import cortes as svc
from ...services.catalogos import farmaceuticos
from ...utils.decorators import admin_required
from ...utils.helpers import parse_fecha, rango_rapido, to_int

bp = Blueprint("cortes", __name__)

SQL_CORTES_CERRADOS = """
    SELECT cc.id AS corte_id, cc.fecha_apertura, cc.fecha_cierre, cc.monto_inicial, cc.monto_final,
           u.id AS usuario_id, u.nombre AS usuario_nombre,
           IFNULL(ac.ventas_efectivo, 0) AS ventas_efectivo,
           IFNULL(ac.ventas_tarjeta, 0) AS ventas_tarjeta,
           IFNULL(ac.ventas_transferencia, 0) AS ventas_transferencia,
           IFNULL(ac.total_ventas, (SELECT IFNULL(SUM(v2.total), 0) FROM ventas v2
                 WHERE v2.usuario_id = u.id AND v2.status = 1
                   AND v2.fecha BETWEEN cc.fecha_apertura AND cc.fecha_cierre)) AS total_ventas,
           (cc.monto_final - cc.monto_inicial) AS diferencia,
           TIMESTAMPDIFF(MINUTE, cc.fecha_apertura, cc.fecha_cierre) AS duracion_minutos,
           (SELECT COUNT(*) FROM ventas v
             WHERE v.usuario_id = u.id AND v.status = 1
               AND v.fecha BETWEEN cc.fecha_apertura AND cc.fecha_cierre) AS total_ventas_corte
    FROM cortes_caja cc
    JOIN usuarios u ON cc.usuario_id = u.id
    LEFT JOIN auditoria_cortes ac ON cc.id = ac.corte_id
    WHERE cc.cerrado = 1 AND cc.status = 1
"""


def _filtrar(sql, fecha_inicio, fecha_fin, usuario_id, campo="cc.fecha_cierre", campo_usuario="cc.usuario_id"):
    params = []
    if fecha_inicio:
        sql += f" AND DATE({campo}) >= %s"
        params.append(fecha_inicio)
    if fecha_fin:
        sql += f" AND DATE({campo}) <= %s"
        params.append(fecha_fin)
    if usuario_id:
        sql += f" AND {campo_usuario} = %s"
        params.append(to_int(usuario_id))
    return sql, params


def _fecha_arg(nombre):
    f = parse_fecha(request.args.get(nombre))
    return f.strftime("%Y-%m-%d") if f else ""


@bp.route("/reportes/reimpresion_cortes")
@login_required
@admin_required
def reimpresion_cortes():
    tipo_filtro = request.args.get("tipo_filtro", "todos")
    fecha_inicio, fecha_fin = _fecha_arg("fecha_inicio"), _fecha_arg("fecha_fin")
    rapido = rango_rapido(tipo_filtro)
    if rapido[0]:
        fecha_inicio, fecha_fin = rapido
    usuario_id = request.args.get("usuario_id", "")

    sql, params = _filtrar(SQL_CORTES_CERRADOS, fecha_inicio, fecha_fin, usuario_id)
    cortes = fetch_all(sql + " ORDER BY cc.fecha_cierre DESC", params)

    por_usuario = {}
    for c in cortes:
        u = por_usuario.setdefault(c["usuario_nombre"], {
            "cortes": 0, "total_ventas": 0, "total_efectivo": 0.0, "total_tarjeta": 0.0,
            "total_transferencia": 0.0, "total_monto": 0.0})
        u["cortes"] += 1
        u["total_ventas"] += c["total_ventas_corte"] or 0
        u["total_efectivo"] += to_float(c["ventas_efectivo"])
        u["total_tarjeta"] += to_float(c["ventas_tarjeta"])
        u["total_transferencia"] += to_float(c["ventas_transferencia"])
        u["total_monto"] += to_float(c["total_ventas"])

    return render_template(
        "cortes/reimpresion.html",
        cortes=cortes,
        usuarios=farmaceuticos(),
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        usuario_id=usuario_id,
        tipo_filtro=tipo_filtro,
        total_cortes=len(cortes),
        total_ventas=sum(c["total_ventas_corte"] or 0 for c in cortes),
        total_efectivo=sum(to_float(c["ventas_efectivo"]) for c in cortes),
        total_tarjeta=sum(to_float(c["ventas_tarjeta"]) for c in cortes),
        total_transferencia=sum(to_float(c["ventas_transferencia"]) for c in cortes),
        total_importe=sum(to_float(c["total_ventas"]) for c in cortes),
        cortes_por_usuario=por_usuario,
    )


@bp.route("/reportes/detalle_corte/<int:corte_id>")
@login_required
@admin_required
def detalle_corte(corte_id):
    datos = svc.datos_ticket(corte_id, con_productos=True)
    if not datos or not datos["cerrado"]:
        flash("Corte no encontrado o aún no está cerrado.", "danger")
        return redirect(url_for("cortes.reimpresion_cortes"))

    corte = svc.obtener_corte(corte_id)
    ventas = svc.ventas_periodo(corte["usuario_id"], corte["fecha_apertura"], corte["fecha_cierre"],
                                con_productos=True)
    por_metodo = {}
    for v in ventas:
        m = por_metodo.setdefault(v["metodo_pago"], {"cantidad": 0, "monto": 0.0})
        m["cantidad"] += 1
        m["monto"] += to_float(v["total"])

    return render_template(
        "cortes/detalle.html",
        corte=corte,
        datos=datos,
        ventas=ventas,
        ventas_por_metodo=por_metodo,
        productos_vendidos=datos["top_productos"],
        total_ventas=len(ventas),
        total_monto_ventas=sum(to_float(v["total"]) for v in ventas),
    )


@bp.route("/reportes/imprimir_corte/<int:corte_id>")
@login_required
@admin_required
def imprimir_corte(corte_id):
    datos = svc.datos_ticket(corte_id, reimpresion=True, con_productos=True)
    if not datos:
        flash("Corte no encontrado.", "danger")
        return redirect(url_for("cortes.reimpresion_cortes"))
    return render_template("tickets/corte.html", datos=datos)


@bp.route("/reimprimir_corte/<int:corte_id>")
@login_required
@admin_required
def reimprimir_corte(corte_id):
    datos = svc.datos_ticket(corte_id, reimpresion=True)
    if not datos:
        flash("Corte no encontrado en auditoría.", "danger")
        return redirect(url_for("cortes.auditoria_cortes"))
    return render_template("tickets/corte.html", datos=datos)


@bp.route("/auditoria_cortes")
@login_required
@admin_required
def auditoria_cortes():
    usuario_id = request.args.get("usuario_id", "")
    fecha_inicio, fecha_fin = _fecha_arg("fecha_inicio"), _fecha_arg("fecha_fin")

    base = """SELECT ac.*, u.nombre AS usuario_nombre, cc.fecha_apertura, cc.fecha_cierre,
                     cc.monto_inicial, cc.monto_final
              FROM auditoria_cortes ac
              JOIN usuarios u ON ac.usuario_id = u.id
              JOIN cortes_caja cc ON ac.corte_id = cc.id
              WHERE 1 = 1"""
    sql, params = _filtrar(base, fecha_inicio, fecha_fin, usuario_id,
                           campo="ac.fecha_cierre", campo_usuario="ac.usuario_id")
    cortes = fetch_all(sql + " ORDER BY ac.fecha_cierre DESC", params)

    return render_template(
        "cortes/auditoria.html",
        cortes=cortes,
        usuarios=farmaceuticos(),
        usuario_id=usuario_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        total_cortes=len(cortes),
        total_ventas=sum(to_float(c["total_ventas"]) for c in cortes),
        total_efectivo=sum(to_float(c["ventas_efectivo"]) for c in cortes),
        total_tarjeta=sum(to_float(c["ventas_tarjeta"]) for c in cortes),
    )


def _cortes_csv(cortes):
    out = StringIO()
    w = csv.writer(out)
    w.writerow(["ID Corte", "Usuario", "Fecha Apertura", "Fecha Cierre", "Fondo Inicial",
                "Ventas Efectivo", "Ventas Tarjeta", "Ventas Transferencia", "Total Ventas",
                "Monto Final", "Diferencia", "Duración (min)"])
    for c in cortes:
        w.writerow([
            c["corte_id"], c["usuario_nombre"],
            c["fecha_apertura"].strftime("%Y-%m-%d %H:%M:%S") if c["fecha_apertura"] else "",
            c["fecha_cierre"].strftime("%Y-%m-%d %H:%M:%S") if c["fecha_cierre"] else "",
            to_float(c["monto_inicial"]), to_float(c["ventas_efectivo"]), to_float(c["ventas_tarjeta"]),
            to_float(c["ventas_transferencia"]), to_float(c["total_ventas"]), to_float(c["monto_final"]),
            to_float(c["diferencia"]), c["duracion_minutos"],
        ])
    return out.getvalue()


@bp.route("/api/cortes/exportar", methods=["POST"])
@login_required
@admin_required
def exportar_cortes():
    """API (JSON) usada por la vista de reimpresión para exportar a CSV."""
    data = request.get_json(silent=True) or {}
    formato = data.get("formato", "csv")
    filtros = data.get("filtros", {}) or {}
    if formato != "csv":
        return jsonify(success=False, message="Formato no soportado (solo CSV).")
    try:
        sql, params = _filtrar(SQL_CORTES_CERRADOS, filtros.get("fecha_inicio"),
                               filtros.get("fecha_fin"), filtros.get("usuario_id"))
        cortes = fetch_all(sql + " ORDER BY cc.fecha_cierre DESC", params)
        return jsonify(success=True, formato="csv", data=_cortes_csv(cortes),
                       filename=f"cortes_{datetime.now():%Y%m%d_%H%M%S}.csv")
    except Exception as exc:
        return jsonify(success=False, message=f"Error al exportar: {exc}")


@bp.route("/reportes/cortes.csv")
@login_required
@admin_required
def descargar_cortes_csv():
    """Descarga directa del CSV con los mismos filtros de la vista."""
    sql, params = _filtrar(SQL_CORTES_CERRADOS, _fecha_arg("fecha_inicio"), _fecha_arg("fecha_fin"),
                           request.args.get("usuario_id"))
    cortes = fetch_all(sql + " ORDER BY cc.fecha_cierre DESC", params)
    nombre = f"cortes_{datetime.now():%Y%m%d_%H%M%S}.csv"
    return Response("﻿" + _cortes_csv(cortes), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={nombre}"})
