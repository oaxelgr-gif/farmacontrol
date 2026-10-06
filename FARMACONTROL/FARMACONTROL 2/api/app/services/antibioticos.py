"""Registro de la receta al vender antibióticos (espejo de farmacontrol/services/antibioticos.py)."""
from datetime import date, datetime

from ..db import execute, fetch_one
from . import NegocioError

DESTINOS = ("retenida", "sellada")


def _t(valor, largo):
    valor = (str(valor).strip() if valor is not None else "")
    return valor[:largo] if valor else None


def _fecha(valor):
    if not valor:
        return None
    if isinstance(valor, date):
        return valor
    try:
        return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def limpiar_registro(datos):
    datos = datos or {}
    try:
        paciente_id = int(datos.get("paciente_id") or 0) or None
        receta_clinica_id = int(datos.get("receta_clinica_id") or 0) or None
    except (TypeError, ValueError):
        paciente_id = receta_clinica_id = None
    r = {
        "paciente_id": paciente_id,
        "paciente_nombre": _t(datos.get("paciente_nombre"), 150),
        "medico_nombre": _t(datos.get("medico_nombre"), 150),
        "medico_cedula": _t(datos.get("medico_cedula"), 30),
        "medico_domicilio": _t(datos.get("medico_domicilio"), 255),
        "institucion": _t(datos.get("institucion"), 150),
        "receta_folio": _t(datos.get("receta_folio"), 40),
        "receta_fecha": _fecha(datos.get("receta_fecha")),
        "receta_clinica_id": receta_clinica_id,
        "vale_salida": "SI" if datos.get("vale_salida") in (True, "SI", "si", "Sí", "SÍ", "1", 1, "on") else _t(datos.get("vale_salida"), 40),
        "destino_receta": datos.get("destino_receta") if datos.get("destino_receta") in DESTINOS else "retenida",
        "observaciones": _t(datos.get("observaciones"), 255),
    }
    faltan = [etq for k, etq in (("paciente_nombre", "nombre del paciente"), ("medico_nombre", "nombre del médico"),
                                 ("medico_cedula", "cédula profesional del médico")) if not r[k]]
    if faltan:
        raise NegocioError("Para vender antibióticos falta: " + ", ".join(faltan) + ".", 422)
    if r["receta_fecha"] and r["receta_fecha"] > date.today():
        raise NegocioError("La fecha de la receta no puede ser futura.", 422)
    return r


def guardar(conn, venta_id, usuario_id, registro, lineas):
    ab = [ln for ln in lineas if ln.get("antibiotico")]
    if not ab:
        return None
    if registro["paciente_id"] and not fetch_one(conn, "SELECT id FROM pacientes WHERE id = %s AND status = 1",
                                                 (registro["paciente_id"],)):
        registro["paciente_id"] = None
    cols = ["venta_id", "usuario_id", "requiere_receta"] + list(registro)
    reg_id = execute(conn, f"INSERT INTO antibioticos_recetas ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                     [venta_id, usuario_id, 1] + list(registro.values()))
    for ln in ab:
        execute(conn, """INSERT INTO antibioticos_dispensacion (registro_id, venta_id, producto_id, producto_nombre, compuesto,
                                                                tipo_antibiotico, lote, fecha_caducidad, cantidad)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (reg_id, venta_id, ln["producto_id"], ln["nombre"], ln.get("compuesto") or ln["nombre"],
                 ln.get("tipo_antibiotico"), ln.get("lote"), ln.get("fecha_caducidad"), ln["cantidad"]))
    return reg_id
