"""Cobro de honorarios y surtido de recetas dentro de una venta (espejo de farmacontrol/services/clinica_caja.py)."""
from ..db import execute, fetch_one, num
from . import NegocioError


def _nombre(p):
    return " ".join(x for x in (p.get("nombre"), p.get("apellido_paterno"), p.get("apellido_materno")) if x)


def linea_honorario(conn, consulta_id):
    c = fetch_one(conn, """SELECT id, folio, paciente_id, costo, venta_id FROM consultas_medicas
                           WHERE id = %s AND status = 1 FOR UPDATE""", (consulta_id,))
    if not c:
        raise NegocioError(f"Consulta ID {consulta_id} no encontrada.", 404)
    if c["venta_id"]:
        raise NegocioError(f"La consulta {c['folio']} ya fue cobrada.", 409)
    precio = num(c["costo"])
    if precio <= 0:
        raise NegocioError(f"La consulta {c['folio']} no tiene honorarios.", 422)
    return {"tipo": "honorario", "producto_id": None, "consulta_id": c["id"], "paciente_id": c["paciente_id"],
            "nombre": f"Consulta médica {c['folio']}", "cantidad": 1, "stock": None, "precio": precio,
            "costo": 0.0, "antibiotico": False}


def validar_receta(conn, receta_id):
    r = fetch_one(conn, "SELECT id, folio, paciente_id, venta_id FROM recetas WHERE id = %s AND status = 1 FOR UPDATE",
                  (receta_id,))
    if not r:
        raise NegocioError("Receta no encontrada.", 404)
    if r["venta_id"]:
        raise NegocioError(f"La receta {r['folio']} ya fue surtida.", 409)
    return r


def cliente_para_paciente(conn, paciente_id):
    p = fetch_one(conn, """SELECT id, nombre, apellido_paterno, apellido_materno, telefono, email, direccion, cliente_id
                           FROM pacientes WHERE id = %s AND status = 1""", (paciente_id,))
    if not p:
        raise NegocioError("Paciente no encontrado.", 404)
    if p["cliente_id"] and fetch_one(conn, "SELECT id FROM clientes WHERE id = %s AND status = 1", (p["cliente_id"],)):
        return p["cliente_id"]
    cliente_id = execute(conn, """INSERT INTO clientes (nombre, rfc_nit, direccion, telefono, email, status)
                                  VALUES (%s, NULL, %s, %s, %s, 1)""",
                         (_nombre(p)[:100], p["direccion"], p["telefono"], p["email"]))
    execute(conn, "UPDATE pacientes SET cliente_id = %s WHERE id = %s", (cliente_id, paciente_id))
    return cliente_id


def registrar_cobro(conn, venta_id, lineas, receta_id=None):
    for ln in lineas:
        if ln["tipo"] == "honorario":
            execute(conn, "UPDATE consultas_medicas SET venta_id = %s WHERE id = %s", (venta_id, ln["consulta_id"]))
    if receta_id:
        execute(conn, "UPDATE recetas SET venta_id = %s, surtida_at = NOW() WHERE id = %s", (venta_id, receta_id))
