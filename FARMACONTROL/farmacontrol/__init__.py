"""
FarmaControl — fábrica de la aplicación Flask.

Estructura:
    farmacontrol/
        blueprints/   -> un módulo por apartado (rutas)
        services/     -> lógica de negocio reutilizable (ventas, cortes, caducidad)
        utils/        -> decoradores, seguridad, helpers y filtros
        db.py         -> conexión y helpers de consulta
        models.py     -> Usuario y constantes de roles
        navigation.py -> menú lateral
"""
from datetime import datetime

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user

from config import Config

from . import db
from .extensions import login_manager
from .models import ROL_ADMIN, ROL_FARMACEUTICO, ROLES, Usuario
from .navigation import menu_para
from .services.catalogos import clase_metodo, icono_metodo
from .services.folios import decodificar as decodificar_folio
from .utils.helpers import registrar_filtros

# Endpoints accesibles sin sesión
ENDPOINTS_PUBLICOS = {"auth.login", "static", "sistema.health"}


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(config_class)
    app.json.sort_keys = False

    db.init_app(app)
    login_manager.init_app(app)
    registrar_filtros(app)

    _registrar_blueprints(app)
    _registrar_hooks(app)
    _registrar_contexto(app)
    _registrar_errores(app)
    return app


# ---------------------------------------------------------------------------
def _registrar_blueprints(app):
    from .blueprints.api.routes import bp as api_bp
    from .blueprints.auth.routes import bp as auth_bp
    from .blueprints.caja.routes import bp as caja_bp
    from .blueprints.clinica.routes import bp as clinica_bp
    from .blueprints.cortes.routes import bp as cortes_bp
    from .blueprints.dashboard.routes import bp as dashboard_bp
    from .blueprints.inventario.routes import bp as inventario_bp
    from .blueprints.reportes.routes import bp as reportes_bp
    from .blueprints.servicios.routes import bp as servicios_bp
    from .blueprints.sistema.routes import bp as sistema_bp
    from .blueprints.usuarios.routes import bp as usuarios_bp
    from .blueprints.ventas.routes import bp as ventas_bp

    for bp in (auth_bp, dashboard_bp, inventario_bp, usuarios_bp, caja_bp, cortes_bp,
               ventas_bp, api_bp, reportes_bp, servicios_bp, sistema_bp, clinica_bp):
        app.register_blueprint(bp)


@login_manager.user_loader
def load_user(user_id):
    try:
        data = db.fetch_one(
            "SELECT id, nombre, username, rol FROM usuarios WHERE id = %s AND status = 1",
            (user_id,),
        )
    except Exception:
        return None
    return Usuario(data) if data else None


@login_manager.unauthorized_handler
def _no_autorizado():
    if request.path.startswith("/api/"):
        return jsonify(success=False, message="Sesión expirada"), 401
    return redirect(url_for("auth.login"))


def _registrar_hooks(app):
    @app.before_request
    def proteger_rutas():
        if request.endpoint in ENDPOINTS_PUBLICOS or request.endpoint is None:
            return None
        if not current_user.is_authenticated:
            if request.path.startswith("/api/"):
                return jsonify(success=False, message="Sesión expirada"), 401
            return redirect(url_for("auth.login"))
        session.permanent = False
        return None

    @app.after_request
    def cabeceras_seguridad(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        if current_user.is_authenticated and resp.mimetype == "text/html":
            # Evita que el botón "atrás" muestre páginas tras cerrar sesión
            resp.headers["Cache-Control"] = "no-store"
        return resp


def _registrar_contexto(app):
    @app.context_processor
    def contexto_global():
        return {
            "now": datetime.now,
            "ROL_ADMIN": ROL_ADMIN,
            "ROL_FARMACEUTICO": ROL_FARMACEUTICO,
            "ROLES": ROLES,
            "menu": menu_para(current_user),
            "negocio": {
                "nombre": app.config["NOMBRE_NEGOCIO"],
                "sucursal": app.config["NOMBRE_SUCURSAL"],
                "telefono": app.config["TELEFONO_NEGOCIO"],
                "estacion": app.config["ESTACION_CAJA"],
            },
            "api_docs_url": (app.config.get("API_PUBLIC_URL") or "").rstrip("/") + "/docs"
                            if app.config.get("API_PUBLIC_URL") else "",
            "inicio_url": _inicio_url(),
            "icono_metodo": icono_metodo,
            "clase_metodo": clase_metodo,
            "folio_info": decodificar_folio,
        }


def _inicio_url():
    if not current_user.is_authenticated:
        return url_for("auth.login")
    if current_user.rol == ROL_ADMIN:
        return url_for("dashboard.inicio")
    return url_for("dashboard.inicio_farmacia")


def _registrar_errores(app):
    @app.errorhandler(404)
    def no_encontrado(_e):
        if request.path.startswith("/api/"):
            return jsonify(success=False, message="Recurso no encontrado"), 404
        return render_template("errors/error.html", codigo=404,
                               titulo="Página no encontrada",
                               mensaje="La página que buscas no existe o fue movida."), 404

    import pymysql

    @app.errorhandler(pymysql.err.OperationalError)
    def bd_no_disponible(exc):
        app.logger.error("Base de datos no disponible: %s", exc)
        if request.path.startswith("/api/"):
            return jsonify(success=False, message="Base de datos no disponible"), 503
        return render_template("errors/error.html", codigo=503,
                               titulo="Base de datos no disponible",
                               mensaje="No fue posible conectar con MySQL. Verifica que el servidor "
                                       "esté encendido (o que el contenedor «db» esté en ejecución) "
                                       "e intenta de nuevo."), 503

    @app.errorhandler(500)
    def error_servidor(_e):
        if request.path.startswith("/api/"):
            return jsonify(success=False, message="Error interno del servidor"), 500
        return render_template("errors/error.html", codigo=500,
                               titulo="Algo salió mal",
                               mensaje="Ocurrió un error inesperado. Intenta de nuevo."), 500
