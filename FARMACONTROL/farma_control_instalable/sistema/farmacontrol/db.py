"""
Capa de acceso a datos (PyMySQL).

- Una sola conexión por petición, guardada en `flask.g` y cerrada al terminar.
- Helpers `fetch_all`, `fetch_one`, `fetch_value` y `execute` para no repetir
  el patrón try/with/finally en cada ruta.
- `transaction()` para operaciones que deben ser atómicas (ventas, cortes).

Nota sobre parámetros: PyMySQL usa `%s` como marcador. Cuando se pasan
parámetros, un `%` literal en el SQL debe escribirse `%%`.
"""
import time
from contextlib import contextmanager
from decimal import Decimal

import pymysql
from pymysql.cursors import DictCursor
from flask import current_app, g


def _connect(reintentos=2):
    cfg = current_app.config
    for intento in range(reintentos):
        try:
            return _abrir(cfg)
        except pymysql.err.OperationalError:
            if intento == reintentos - 1:
                raise
            time.sleep(0.8)


def _abrir(cfg):
    return pymysql.connect(
        host=cfg["DB_HOST"],
        port=cfg["DB_PORT"],
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
        db=cfg["DB_NAME"],
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
        connect_timeout=5,
    )


def get_db():
    """Devuelve la conexión de la petición actual (la crea si no existe)."""
    if "db" not in g:
        g.db = _connect()
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:  # pragma: no cover - conexión ya cerrada
            pass


def init_app(app):
    app.teardown_appcontext(close_db)


# ---------------------------------------------------------------------------
# Helpers de consulta
# ---------------------------------------------------------------------------
def _params(params):
    # Siempre pasamos una tupla para que el escapado de `%%` sea consistente.
    if params is None:
        return ()
    return tuple(params)


def fetch_all(sql, params=None, cursor=None):
    if cursor is not None:
        cursor.execute(sql, _params(params))
        return cursor.fetchall()
    with get_db().cursor() as cur:
        cur.execute(sql, _params(params))
        return cur.fetchall()


def fetch_one(sql, params=None, cursor=None):
    if cursor is not None:
        cursor.execute(sql, _params(params))
        return cursor.fetchone()
    with get_db().cursor() as cur:
        cur.execute(sql, _params(params))
        return cur.fetchone()


def fetch_value(sql, params=None, default=0, cursor=None):
    """Primer valor de la primera fila (útil para COUNT/SUM)."""
    row = fetch_one(sql, params, cursor=cursor)
    if not row:
        return default
    valor = next(iter(row.values()))
    return default if valor is None else valor


def execute(sql, params=None, cursor=None):
    """Ejecuta INSERT/UPDATE/DELETE y devuelve `lastrowid`."""
    if cursor is not None:
        cursor.execute(sql, _params(params))
        return cursor.lastrowid
    with get_db().cursor() as cur:
        cur.execute(sql, _params(params))
        return cur.lastrowid


@contextmanager
def transaction():
    """
    Bloque transaccional:

        with transaction() as cur:
            cur.execute(...)

    Hace COMMIT al salir sin errores y ROLLBACK si ocurre una excepción.
    """
    conn = get_db()
    conn.begin()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def to_float(valor, defecto=0.0):
    """Convierte Decimal/None/str a float de forma segura."""
    if valor is None or valor == "":
        return defecto
    if isinstance(valor, Decimal):
        return float(valor)
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto
