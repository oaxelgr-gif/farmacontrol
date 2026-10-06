"""Gestión de usuarios (solo administradores)."""
import pymysql
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ...db import execute, fetch_all, fetch_one, fetch_value
from ...models import ROL_ADMIN, ROL_FARMACEUTICO, ROLES
from ...utils.decorators import admin_required
from ...utils.helpers import to_int
from ...utils.security import hash_password

bp = Blueprint("usuarios", __name__)


@bp.route("/usuarios")
@login_required
@admin_required
def listar_usuarios():
    search_query = (request.args.get("search") or "").strip()
    rol_filter = request.args.get("rol", "")

    sql = "SELECT id, nombre, username AS correo, rol, status FROM usuarios WHERE status = 1"
    params = []
    if search_query:
        sql += " AND (nombre LIKE %s OR username LIKE %s)"
        params += [f"%{search_query}%", f"%{search_query}%"]
    if rol_filter:
        sql += " AND rol = %s"
        params.append(to_int(rol_filter))
    sql += " ORDER BY nombre ASC"

    return render_template(
        "usuarios/lista.html",
        usuarios=fetch_all(sql, params),
        search_query=search_query,
        rol_filter=rol_filter,
        total_usuarios=fetch_value("SELECT COUNT(*) AS n FROM usuarios WHERE status = 1"),
        total_admin=fetch_value("SELECT COUNT(*) AS n FROM usuarios WHERE status = 1 AND rol = %s",
                                (ROL_ADMIN,)),
        total_farmaceuticos=fetch_value(
            "SELECT COUNT(*) AS n FROM usuarios WHERE status = 1 AND rol = %s", (ROL_FARMACEUTICO,)),
    )


@bp.route("/usuario/nuevo", methods=["GET", "POST"])
@bp.route("/usuario/editar/<int:id>", methods=["GET", "POST"])
@login_required
@admin_required
def agregar_editar_usuario(id=None):
    usuario = None
    if id:
        usuario = fetch_one("SELECT id, nombre, username, rol FROM usuarios WHERE id = %s", (id,))
        if not usuario:
            flash("Usuario no encontrado.", "danger")
            return redirect(url_for("usuarios.listar_usuarios"))

    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        username = (request.form.get("correo") or "").strip()
        contrasena = request.form.get("password") or ""
        rol = to_int(request.form.get("rol"), ROL_FARMACEUTICO)

        errores = []
        if not nombre or not username:
            errores.append("Nombre y usuario son obligatorios.")
        if rol not in ROLES:
            errores.append("Rol inválido.")
        if not id and len(contrasena.strip()) < 4:
            errores.append("La contraseña es obligatoria (mínimo 4 caracteres).")
        if id and id == current_user.id and rol != ROL_ADMIN:
            errores.append("No puedes quitarte el rol de administrador a ti mismo.")

        if not errores:
            try:
                if id:
                    if contrasena.strip():
                        execute("UPDATE usuarios SET nombre=%s, username=%s, password=%s, rol=%s WHERE id=%s",
                                (nombre, username, hash_password(contrasena), rol, id))
                    else:
                        execute("UPDATE usuarios SET nombre=%s, username=%s, rol=%s WHERE id=%s",
                                (nombre, username, rol, id))
                else:
                    execute("INSERT INTO usuarios (nombre, username, password, rol, status) "
                            "VALUES (%s, %s, %s, %s, 1)",
                            (nombre, username, hash_password(contrasena), rol))
                flash("Usuario guardado correctamente.", "success")
                return redirect(url_for("usuarios.listar_usuarios"))
            except pymysql.err.IntegrityError:
                errores.append("Ese nombre de usuario ya está en uso.")
            except Exception as exc:
                errores.append(f"Error: {exc}")

        for e in errores:
            flash(e, "danger")
        usuario = {"id": id, "nombre": nombre, "username": username, "rol": rol}

    return render_template("usuarios/form.html", usuario=usuario, editando=bool(id))


@bp.route("/usuario/eliminar/<int:id>", methods=["POST"])
@login_required
@admin_required
def eliminar_usuario(id):
    if id == current_user.id:
        flash("No puedes eliminarte a ti mismo.", "danger")
        return redirect(url_for("usuarios.listar_usuarios"))
    try:
        execute("UPDATE usuarios SET status = 0 WHERE id = %s", (id,))
        flash("Usuario eliminado correctamente.", "success")
    except Exception as exc:
        flash(f"Error al eliminar usuario: {exc}", "danger")
    return redirect(url_for("usuarios.listar_usuarios"))
