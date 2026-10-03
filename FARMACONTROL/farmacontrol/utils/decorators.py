"""Decoradores de autorización."""
from functools import wraps

from flask import flash, jsonify, redirect, request, url_for
from flask_login import current_user

from ..models import ROL_ADMIN


def _es_peticion_api():
    return request.path.startswith("/api/") or request.is_json


def admin_required(f):
    """Permite el acceso solo a administradores (rol 1)."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != ROL_ADMIN:
            if _es_peticion_api():
                return jsonify(success=False, message="Acceso restringido a administradores"), 403
            flash("Acceso restringido: solo para administradores.", "danger")
            return redirect(url_for("dashboard.inicio_farmacia"))
        return f(*args, **kwargs)

    return wrapper


# Alias para mantener el nombre usado en la versión anterior.
admin_only = admin_required
