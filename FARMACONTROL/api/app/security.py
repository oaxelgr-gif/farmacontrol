"""Contraseñas (compatibles con el servicio web) y tokens JWT."""
import hmac
from datetime import datetime, timedelta, timezone

import jwt
from werkzeug.security import check_password_hash, generate_password_hash

from .config import settings

_PREFIJOS = ("pbkdf2:", "scrypt:", "argon2")


def es_hash(valor):
    return bool(valor) and str(valor).startswith(_PREFIJOS)


def verificar_password(guardada, ingresada):
    if not guardada or ingresada is None:
        return False
    if es_hash(guardada):
        try:
            return check_password_hash(guardada, ingresada)
        except ValueError:
            return False
    return hmac.compare_digest(str(guardada), str(ingresada))


def hash_password(password):
    return generate_password_hash(password)


def crear_token(usuario_id, rol):
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario_id),
        "rol": int(rol),
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def leer_token(token):
    """Devuelve el payload o None si el token es inválido/expiró."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def token_interno_valido(token):
    return bool(token) and hmac.compare_digest(str(token), settings.API_INTERNAL_TOKEN)
