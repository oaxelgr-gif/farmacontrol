"""Anaqueles (ubicaciones) del inventario: el usuario los crea, renombra y elimina.

Se guardan en la tabla `secciones` (la que ya usaban los productos), así que los
productos existentes conservan su ubicación.
"""
from ..db import execute, fetch_all, fetch_one, transaction


class AnaquelError(Exception):
    pass


def _limpiar(texto, largo):
    texto = (texto or "").strip()
    return texto[:largo] if texto else None


def listar():
    return fetch_all(
        """SELECT s.id, s.nombre, s.descripcion,
                  (SELECT COUNT(*) FROM productos p WHERE p.seccion_id = s.id AND p.status = 1) AS productos,
                  (SELECT IFNULL(SUM(p.stock_actual), 0) FROM productos p WHERE p.seccion_id = s.id AND p.status = 1) AS piezas
           FROM secciones s WHERE s.status = 1 ORDER BY s.nombre""")


def sin_anaquel():
    return fetch_one("SELECT COUNT(*) AS n FROM productos WHERE status = 1 AND seccion_id IS NULL")["n"]


def _nombre_libre(nombre, excluir_id=None):
    sql, prm = "SELECT id FROM secciones WHERE status = 1 AND LOWER(nombre) = LOWER(%s)", [nombre]
    if excluir_id:
        sql += " AND id <> %s"
        prm.append(excluir_id)
    if fetch_one(sql, prm):
        raise AnaquelError(f"Ya existe un anaquel llamado «{nombre}».")


def crear(nombre, descripcion=None):
    nombre = _limpiar(nombre, 100)
    if not nombre:
        raise AnaquelError("Escribe el nombre del anaquel.")
    _nombre_libre(nombre)
    nuevo = execute("INSERT INTO secciones (nombre, descripcion, status) VALUES (%s, %s, 1)",
                    (nombre, _limpiar(descripcion, 255)))
    return {"id": nuevo, "nombre": nombre}


def editar(anaquel_id, nombre, descripcion=None):
    nombre = _limpiar(nombre, 100)
    if not nombre:
        raise AnaquelError("El nombre no puede quedar vacío.")
    if not fetch_one("SELECT id FROM secciones WHERE id = %s AND status = 1", (anaquel_id,)):
        raise AnaquelError("Anaquel no encontrado.")
    _nombre_libre(nombre, anaquel_id)
    execute("UPDATE secciones SET nombre = %s, descripcion = %s WHERE id = %s",
            (nombre, _limpiar(descripcion, 255), anaquel_id))


def eliminar(anaquel_id, mover_a=None):
    """Baja lógica. Los productos pasan al anaquel `mover_a` o quedan «Sin anaquel»."""
    a = fetch_one("SELECT id, nombre FROM secciones WHERE id = %s AND status = 1", (anaquel_id,))
    if not a:
        raise AnaquelError("Anaquel no encontrado.")
    if mover_a:
        if int(mover_a) == int(anaquel_id) or not fetch_one(
                "SELECT id FROM secciones WHERE id = %s AND status = 1", (mover_a,)):
            raise AnaquelError("Elige otro anaquel destino válido.")
    movidos = fetch_one("SELECT COUNT(*) AS n FROM productos WHERE seccion_id = %s AND status = 1", (anaquel_id,))["n"]
    with transaction() as cur:
        execute("UPDATE productos SET seccion_id = %s WHERE seccion_id = %s", (mover_a or None, anaquel_id), cursor=cur)
        execute("UPDATE secciones SET status = 0 WHERE id = %s", (anaquel_id,), cursor=cur)
    return a["nombre"], movidos
