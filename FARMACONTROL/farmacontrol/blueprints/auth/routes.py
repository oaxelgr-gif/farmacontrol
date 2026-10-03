"""Acceso: login, logout y redirección inicial según rol."""
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ...db import execute, fetch_one
from ...models import ROL_ADMIN, Usuario
from ...services.cortes import corte_abierto
from ...utils.security import hash_password, necesita_rehash, verificar_password

bp = Blueprint("auth", __name__)


def _destino(rol):
    return url_for("dashboard.inicio") if rol == ROL_ADMIN else url_for("dashboard.inicio_farmacia")


@bp.route("/")
def index():
    if not current_user.is_authenticated:
        session.clear()
        return redirect(url_for("auth.login"))

    activo = fetch_one("SELECT id FROM usuarios WHERE id = %s AND status = 1", (current_user.id,))
    if not activo:
        logout_user()
        session.clear()
        flash("Tu cuenta ha sido desactivada.", "danger")
        return redirect(url_for("auth.login"))
    return redirect(_destino(current_user.rol))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.index"))

    username = ""
    if request.method == "POST":
        username = (request.form.get("correo") or request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            flash("Escribe tu usuario y contraseña.", "warning")
        else:
            try:
                data = fetch_one(
                    """SELECT id, nombre, username, password, rol
                       FROM usuarios WHERE username = %s AND status = 1""",
                    (username,),
                )
            except Exception as exc:
                data = None
                current_app.logger.exception("Error de conexión a MySQL")
                flash(f"No se pudo conectar con la base de datos: {exc}", "danger")
            else:
                if data and verificar_password(data["password"], password):
                    # Migración transparente de contraseñas en texto plano a hash
                    if necesita_rehash(data["password"]):
                        try:
                            execute("UPDATE usuarios SET password = %s WHERE id = %s",
                                    (hash_password(password), data["id"]))
                        except Exception:
                            pass
                    login_user(Usuario(data), remember=False)
                    return redirect(_destino(int(data["rol"])))
                flash("Credenciales incorrectas o cuenta inactiva.", "danger")

    return render_template("auth/login.html", username=username)


@bp.route("/logout")
@login_required
def logout():
    if corte_abierto(current_user.id):
        flash("Tienes un corte de caja abierto. Debes cerrarlo antes de salir.", "warning")
        return redirect(url_for("caja.corte_caja"))
    logout_user()
    session.clear()
    flash("Sesión cerrada correctamente.", "success")
    return redirect(url_for("auth.login"))
