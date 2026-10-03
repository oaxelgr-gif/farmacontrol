"""Acceso a MySQL para la API (una conexión por petición)."""
import time
from contextlib import contextmanager
from decimal import Decimal

import pymysql
from pymysql.cursors import DictCursor

from .config import settings


def connect(reintentos=3, espera=1.0):
    """Abre una conexión; reintenta brevemente si MySQL aún está arrancando."""
    ultimo = None
    for intento in range(reintentos):
        try:
            return pymysql.connect(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                db=settings.DB_NAME,
                charset="utf8mb4",
                cursorclass=DictCursor,
                autocommit=True,
                connect_timeout=5,
            )
        except pymysql.err.OperationalError as exc:
            ultimo = exc
            if intento < reintentos - 1:
                time.sleep(espera)
    raise ultimo


def get_db():
    """Dependencia de FastAPI: entrega la conexión y la cierra al terminar."""
    conn = connect()
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _p(params):
    return () if params is None else tuple(params)


def fetch_all(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, _p(params))
        return cur.fetchall()


def fetch_one(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, _p(params))
        return cur.fetchone()


def fetch_value(conn, sql, params=None, default=0):
    row = fetch_one(conn, sql, params)
    if not row:
        return default
    v = next(iter(row.values()))
    return default if v is None else v


def execute(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, _p(params))
        return cur.lastrowid


@contextmanager
def transaction(conn):
    conn.begin()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def num(v, d=0.0):
    if v is None or v == "":
        return d
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return d
