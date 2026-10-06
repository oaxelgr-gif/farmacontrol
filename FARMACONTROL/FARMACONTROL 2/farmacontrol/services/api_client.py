"""
Cliente del microservicio FastAPI.

Cuando `API_URL` está configurada (en Docker: http://api:8000), el punto de venta
delega búsquedas, catálogos, clientes y cobros a la API. Si la API no responde,
el servicio web usa su lógica local como respaldo para no detener la venta.
"""
from flask import current_app
from flask_login import current_user


class ApiNoDisponible(Exception):
    pass


def activo():
    return bool(current_app.config.get("API_URL"))


def llamar(metodo, ruta, params=None, json=None):
    """Devuelve (status_code, cuerpo_json). Lanza ApiNoDisponible ante fallas de red/5xx."""
    import requests  # import diferido: solo se necesita si la API está activa

    cfg = current_app.config
    headers = {"X-Internal-Token": cfg["API_INTERNAL_TOKEN"], "Accept": "application/json"}
    if current_user.is_authenticated:
        headers["X-User-Id"] = str(current_user.id)
    try:
        resp = requests.request(metodo, cfg["API_URL"].rstrip("/") + ruta, params=params, json=json,
                                headers=headers, timeout=cfg.get("API_TIMEOUT", 8))
    except requests.RequestException as exc:
        current_app.logger.warning("API no disponible (%s %s): %s", metodo, ruta, exc)
        raise ApiNoDisponible(str(exc)) from exc
    if resp.status_code >= 500 or resp.status_code == 401:
        current_app.logger.warning("API respondió %s en %s %s", resp.status_code, metodo, ruta)
        raise ApiNoDisponible(f"HTTP {resp.status_code}")
    try:
        cuerpo = resp.json()
    except ValueError:
        cuerpo = {}
    return resp.status_code, cuerpo


def mensaje(cuerpo, defecto="Error en la solicitud"):
    detalle = cuerpo.get("detail") if isinstance(cuerpo, dict) else None
    if isinstance(detalle, list) and detalle:  # errores de validación de FastAPI
        return "; ".join(str(d.get("msg", d)) for d in detalle)
    return detalle or defecto
