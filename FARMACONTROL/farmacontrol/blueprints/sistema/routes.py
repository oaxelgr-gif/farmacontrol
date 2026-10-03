"""Rutas técnicas: diagnóstico de conexión."""
from flask import Blueprint, jsonify
from flask_login import login_required

from ...db import fetch_value
from ...utils.decorators import admin_required

bp = Blueprint("sistema", __name__)


@bp.route("/test_db")
@login_required
@admin_required
def test_db():
    try:
        return jsonify(
            success=True,
            usuarios=fetch_value("SELECT COUNT(*) AS n FROM usuarios WHERE status = 1"),
            productos=fetch_value("SELECT COUNT(*) AS n FROM productos WHERE status = 1"),
            ventas=fetch_value("SELECT COUNT(*) AS n FROM ventas WHERE status = 1"),
        )
    except Exception as exc:
        return jsonify(success=False, error=str(exc)), 500


@bp.route("/health")
def health():
    """Estado del servicio web y la base de datos (sin sesión; usado por Docker)."""
    from flask import current_app

    estado = {"status": "ok", "servicio": "web", "db": "ok",
              "api": current_app.config.get("API_URL") or "local"}
    try:
        fetch_value("SELECT 1 AS ok")
    except Exception as exc:
        estado.update(status="degradado", db=str(exc))
        return jsonify(estado), 503
    return jsonify(estado)
