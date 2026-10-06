"""Catálogo de servicios médicos (procedimientos) y consultas."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ...db import execute, fetch_all
from ...utils.decorators import admin_required
from ...utils.helpers import to_int, to_num

bp = Blueprint("servicios", __name__)

# Lista blanca: evita inyectar nombres de tabla desde el formulario
TABLAS = {"servicio": "servicios", "consulta": "consultas"}


@bp.route("/gestion_servicios")
@login_required
@admin_required
def gestion_servicios():
    return render_template(
        "servicios/gestion.html",
        servicios=fetch_all("SELECT * FROM servicios WHERE status = 1 ORDER BY nombre ASC"),
        consultas=fetch_all("SELECT * FROM consultas WHERE status = 1 ORDER BY nombre ASC"),
    )


@bp.route("/gestion/guardar", methods=["POST"])
@login_required
@admin_required
def guardar_item():
    tabla = TABLAS.get(request.form.get("tipo"))
    id_item = to_int(request.form.get("id"), 0)
    nombre = (request.form.get("nombre") or "").strip()
    precio = round(to_num(request.form.get("precio"), -1), 2)

    if not tabla:
        flash("Tipo de registro inválido.", "danger")
    elif not nombre or precio < 0:
        flash("Nombre y precio (mayor o igual a 0) son obligatorios.", "danger")
    else:
        try:
            if id_item:
                execute(f"UPDATE {tabla} SET nombre = %s, precio = %s WHERE id = %s",
                        (nombre, precio, id_item))
            else:
                execute(f"INSERT INTO {tabla} (nombre, precio, status) VALUES (%s, %s, 1)",
                        (nombre, precio))
            flash("Registro guardado exitosamente.", "success")
        except Exception as exc:
            flash(f"Error al guardar: {exc}", "danger")
    return redirect(url_for("servicios.gestion_servicios"))


@bp.route("/gestion/eliminar", methods=["POST"])
@login_required
@admin_required
def eliminar_item():
    tabla = TABLAS.get(request.form.get("tipo"))
    id_item = to_int(request.form.get("id"), 0)
    if not tabla or not id_item:
        flash("Registro inválido.", "danger")
    else:
        execute(f"UPDATE {tabla} SET status = 0 WHERE id = %s", (id_item,))
        flash("Registro eliminado.", "success")
    return redirect(url_for("servicios.gestion_servicios"))
