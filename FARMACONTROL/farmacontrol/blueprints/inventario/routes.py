"""Inventario: listado, alta/edición y baja lógica de productos."""
import pymysql
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ...db import execute, fetch_all, fetch_one, to_float
from ...services import caducidad
from ...services.catalogos import secciones as catalogo_secciones
from ...utils.decorators import admin_required
from ...utils.helpers import hoy, parse_fecha, to_int, to_num

bp = Blueprint("inventario", __name__)


@bp.route("/inventario")
@login_required
def listar_productos():
    search_query = (request.args.get("search") or "").strip()
    alerta_stock = request.args.get("alerta", "")
    seccion_id = request.args.get("seccion_id", "")

    sql = """SELECT p.*, s.nombre AS nombre_seccion
             FROM productos p LEFT JOIN secciones s ON p.seccion_id = s.id
             WHERE p.status = 1"""
    params = []
    if search_query:
        sql += " AND (p.nombre LIKE %s OR p.codigo_barras LIKE %s OR p.lote LIKE %s)"
        term = f"%{search_query}%"
        params += [term, term, term]
    if alerta_stock == "bajo":
        sql += " AND p.stock_actual <= p.stock_minimo"
    elif alerta_stock == "caducidad":
        sql += f" AND p.fecha_caducidad <= CURDATE() + INTERVAL {caducidad.dias_alerta()} DAY"
    elif alerta_stock == "antibiotico":
        sql += " AND p.antibiotico = 1"
    if seccion_id:
        sql += " AND p.seccion_id = %s"
        params.append(to_int(seccion_id))
    sql += " ORDER BY p.nombre ASC"

    productos, secciones = [], []
    try:
        productos = fetch_all(sql, params)
        secciones = catalogo_secciones()
    except Exception as exc:  # pragma: no cover - errores de BD
        flash(f"Error al cargar inventario: {exc}", "danger")

    resumen = {
        "total_productos": len(productos),
        "total_stock": sum(int(p["stock_actual"] or 0) for p in productos),
        "total_valor": sum((p["stock_actual"] or 0) * to_float(p["precio_costo"]) for p in productos),
        "stock_bajo": sum(1 for p in productos if (p["stock_actual"] or 0) <= (p["stock_minimo"] or 0)),
    }
    return render_template(
        "inventario/lista.html",
        productos=productos,
        secciones=secciones,
        search_query=search_query,
        alerta_stock=alerta_stock,
        seccion_id=seccion_id,
        hoy=hoy(),
        dias_alerta=caducidad.dias_alerta(),
        **resumen,
    )


def _leer_formulario():
    f = request.form
    datos = {
        "nombre": (f.get("nombre") or "").strip(),
        "codigo_barras": (f.get("codigo_barras") or "").strip() or None,
        "lote": (f.get("lote") or "").strip(),
        "stock_entrada": to_int(f.get("stock_entrada"), 0, minimo=0),
        "stock_minimo": to_int(f.get("stock_minimo"), 0, minimo=0),
        "precio_costo": round(to_num(f.get("precio_costo")), 2),
        "precio_publico": round(to_num(f.get("precio_publico")), 2),
        "fecha_caducidad": parse_fecha(f.get("fecha_caducidad")),
        "antibiotico": 1 if f.get("antibiotico") else 0,
        "seccion_id": to_int(f.get("seccion_id"), 0) or None,
    }
    errores = []
    if not datos["nombre"]:
        errores.append("El nombre es obligatorio.")
    if datos["precio_costo"] < 0 or datos["precio_publico"] < 0:
        errores.append("Los precios no pueden ser negativos.")
    if datos["precio_publico"] < datos["precio_costo"]:
        flash("Aviso: el precio al público es menor que el costo.", "warning")
    return datos, errores


@bp.route("/producto/gestion", defaults={"id": None}, methods=["GET", "POST"])
@bp.route("/producto/gestion/<int:id>", methods=["GET", "POST"])
@login_required
@admin_required
def agregar_editar_producto(id=None):
    producto = None
    if id:
        producto = fetch_one("SELECT * FROM productos WHERE id = %s", (id,))
        if not producto:
            flash("Producto no encontrado.", "danger")
            return redirect(url_for("inventario.listar_productos"))

    if request.method == "POST":
        d, errores = _leer_formulario()
        if errores:
            for e in errores:
                flash(e, "danger")
        else:
            try:
                if id:
                    execute(
                        """UPDATE productos SET nombre=%s, codigo_barras=%s, lote=%s,
                               stock_actual = stock_actual + %s, stock_minimo=%s, precio_costo=%s,
                               precio_publico=%s, fecha_caducidad=%s, antibiotico=%s, seccion_id=%s
                           WHERE id=%s""",
                        (d["nombre"], d["codigo_barras"], d["lote"], d["stock_entrada"],
                         d["stock_minimo"], d["precio_costo"], d["precio_publico"],
                         d["fecha_caducidad"], d["antibiotico"], d["seccion_id"], id),
                    )
                else:
                    execute(
                        """INSERT INTO productos (nombre, codigo_barras, lote, stock_actual,
                               stock_minimo, precio_costo, precio_publico, fecha_caducidad,
                               antibiotico, seccion_id, status)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)""",
                        (d["nombre"], d["codigo_barras"], d["lote"], d["stock_entrada"],
                         d["stock_minimo"], d["precio_costo"], d["precio_publico"],
                         d["fecha_caducidad"], d["antibiotico"], d["seccion_id"]),
                    )
                flash("¡Producto guardado correctamente!", "success")
                return redirect(url_for("inventario.listar_productos"))
            except pymysql.err.IntegrityError:
                flash("Ya existe un producto con ese código de barras.", "danger")
            except Exception as exc:
                flash(f"Error en la operación: {exc}", "danger")
        # Re-mostrar el formulario con lo capturado
        producto = dict(producto or {}, **{k: v for k, v in d.items() if k != "stock_entrada"})

    return render_template("inventario/form.html", producto=producto,
                           secciones=catalogo_secciones(), editando=bool(id))


@bp.route("/producto/eliminar/<int:id>", methods=["POST"])
@login_required
@admin_required
def eliminar_producto(id):
    try:
        execute("UPDATE productos SET status = 0 WHERE id = %s", (id,))
        flash("Producto removido del inventario.", "success")
    except Exception as exc:
        flash(f"Error al eliminar: {exc}", "danger")
    return redirect(url_for("inventario.listar_productos"))
