"""
Manejo de contraseñas.

Las contraseñas nuevas se guardan con hash (Werkzeug / scrypt o pbkdf2).
Para no romper las cuentas existentes (guardadas en texto plano en la BD
original), `verificar_password` acepta ambos formatos y `necesita_rehash`
indica cuándo conviene actualizar la contraseña a hash tras un login exitoso.
"""
import hmac

from werkzeug.security import check_password_hash, generate_password_hash

_PREFIJOS_HASH = ("pbkdf2:", "scrypt:", "argon2")


def es_hash(valor):
    return bool(valor) and str(valor).startswith(_PREFIJOS_HASH)


def hash_password(password):
    return generate_password_hash(password)


def verificar_password(guardada, ingresada):
    if not guardada or ingresada is None:
        return False
    if es_hash(guardada):
        try:
            return check_password_hash(guardada, ingresada)
        except ValueError:
            return False
    # Compatibilidad con contraseñas antiguas en texto plano
    return hmac.compare_digest(str(guardada), str(ingresada))


def necesita_rehash(guardada):
    return not es_hash(guardada)
