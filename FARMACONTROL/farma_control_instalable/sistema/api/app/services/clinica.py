"""Consulta del expediente clínico desde la API (lectura + alta de pacientes y citas)."""
from datetime import date, datetime, timedelta

from ..db import execute, fetch_all, fetch_one, num, transaction
from . import NegocioError

CAMPOS_PACIENTE = ("nombre", "apellido_paterno", "apellido_materno", "fecha_nacimiento", "sexo", "curp",
                   "tipo_sangre", "telefono", "email", "direccion", "ciudad", "codigo_postal",
                   "aseguradora", "poliza", "notas")


def _edad(fn):
    if not fn:
        return None
    hoy = date.today()
    return hoy.year - fn.year - ((hoy.month, hoy.day) < (fn.month, fn.day))


def _nombre(p):
    return " ".join(x for x in (p.get("nombre"), p.get("apellido_paterno"), p.get("apellido_materno")) if x)


def _resumen(p):
    return {"id": p["id"], "expediente": p["expediente"], "nombre": _nombre(p), "sexo": p.get("sexo"),
            "fecha_nacimiento": p.get("fecha_nacimiento"), "edad": _edad(p.get("fecha_nacimiento")),
            "telefono": p.get("telefono"), "visitas": int(p.get("visitas") or 0),
            "ultima_consulta": p.get("ultima_consulta")}


SQL_LISTA = """SELECT p.*, (SELECT COUNT(*) FROM consultas_medicas c WHERE c.paciente_id = p.id AND c.status = 1) AS visitas,
                      (SELECT MAX(c.fecha) FROM consultas_medicas c WHERE c.paciente_id = p.id AND c.status = 1) AS ultima_consulta
               FROM pacientes p WHERE p.status = 1"""


def pacientes(conn, q="", limite=50):
    sql, params = SQL_LISTA, []
    if q:
        sql += """ AND (CONCAT(p.nombre, ' ', p.apellido_paterno, ' ', IFNULL(p.apellido_materno, '')) LIKE %s
                   OR p.expediente LIKE %s OR p.telefono LIKE %s OR p.curp LIKE %s)"""
        params += [f"%{q}%"] * 4
    sql += " ORDER BY p.apellido_paterno, p.nombre LIMIT %s"
    params.append(int(limite))
    return [_resumen(p) for p in fetch_all(conn, sql, params)]


def paciente(conn, paciente_id):
    p = fetch_one(conn, SQL_LISTA + " AND p.id = %s", (paciente_id,))
    if not p:
        raise NegocioError("Paciente no encontrado", 404)
    datos = _resumen(p)
    datos.update({k: p.get(k) for k in CAMPOS_PACIENTE if k not in datos})
    datos["tipo_sangre"] = p.get("tipo_sangre")
    datos["alergias"] = fetch_all(conn, """SELECT alergeno, tipo, reaccion, severidad FROM paciente_alergias
                                           WHERE paciente_id = %s AND status = 1""", (paciente_id,))
    datos["padecimientos"] = fetch_all(conn, """SELECT id, nombre, cie10, tipo, estado, fecha_diagnostico
                                                FROM paciente_padecimientos WHERE paciente_id = %s AND status = 1
                                                ORDER BY estado, nombre""", (paciente_id,))
    datos["medicamentos_actuales"] = fetch_all(conn, """SELECT medicamento, dosis, frecuencia, via FROM paciente_medicamentos
                                                        WHERE paciente_id = %s AND status = 1 AND activo = 1""",
                                               (paciente_id,))
    datos["estudios_pendientes"] = int(fetch_one(conn, """SELECT COUNT(*) AS n FROM estudios WHERE paciente_id = %s
                                                          AND status = 1 AND estado IN ('solicitado', 'en_proceso')""",
                                                 (paciente_id,))["n"])
    return datos


def crear_paciente(conn, datos):
    if not (datos.get("nombre") or "").strip() or not (datos.get("apellido_paterno") or "").strip():
        raise NegocioError("Nombre y apellido paterno son obligatorios.", 422)
    with transaction(conn):
        cols = [c for c in CAMPOS_PACIENTE if datos.get(c) not in (None, "")]
        nuevo = execute(conn, f"INSERT INTO pacientes ({', '.join(cols)}, status) VALUES ({', '.join(['%s'] * len(cols))}, 1)",
                        [datos[c] for c in cols])
        execute(conn, "UPDATE pacientes SET expediente = %s WHERE id = %s", (f"P{nuevo:06d}", nuevo))
    return paciente(conn, nuevo)


def _consulta(c):
    return {"id": c["id"], "folio": c["folio"], "fecha": c["fecha"], "tipo": c["tipo"], "motivo": c["motivo"],
            "diagnostico": c["diagnostico"], "medico": c.get("medico"), "costo": num(c["costo"]),
            "pagada": bool(c.get("venta_id")), "proxima_cita": c.get("proxima_cita"),
            "signos": {k: (num(c[k]) if c.get(k) is not None else None) for k in
                       ("peso_kg", "talla_cm", "imc", "temperatura", "ta_sistolica", "ta_diastolica",
                        "frecuencia_cardiaca", "frecuencia_respiratoria", "saturacion_o2", "glucosa_capilar")}}


def consultas(conn, paciente_id):
    paciente(conn, paciente_id)
    filas = fetch_all(conn, """SELECT c.*, u.nombre AS medico FROM consultas_medicas c JOIN usuarios u ON u.id = c.medico_id
                               WHERE c.paciente_id = %s AND c.status = 1 ORDER BY c.fecha DESC, c.id DESC""",
                      (paciente_id,))
    return [_consulta(c) for c in filas]


def consulta(conn, consulta_id):
    c = fetch_one(conn, """SELECT c.*, u.nombre AS medico FROM consultas_medicas c JOIN usuarios u ON u.id = c.medico_id
                           WHERE c.id = %s AND c.status = 1""", (consulta_id,))
    if not c:
        raise NegocioError("Consulta no encontrada", 404)
    d = _consulta(c)
    d.update({"paciente_id": c["paciente_id"], "padecimiento_actual": c["padecimiento_actual"],
              "exploracion_fisica": c["exploracion_fisica"], "plan_tratamiento": c["plan_tratamiento"],
              "indicaciones": c["indicaciones"], "pronostico": c["pronostico"]})
    d["diagnosticos"] = fetch_all(conn, "SELECT descripcion, cie10, tipo FROM consulta_diagnosticos WHERE consulta_id = %s",
                                  (consulta_id,))
    d["recetas"] = [r["id"] for r in fetch_all(conn, "SELECT id FROM recetas WHERE consulta_id = %s AND status = 1",
                                               (consulta_id,))]
    d["estudios"] = fetch_all(conn, "SELECT id, tipo, nombre, estado FROM estudios WHERE consulta_id = %s AND status = 1",
                              (consulta_id,))
    return d


def _receta(conn, r):
    meds = fetch_all(conn, """SELECT medicamento, presentacion, dosis, via, frecuencia, duracion, cantidad, indicaciones,
                                     producto_id FROM receta_medicamentos WHERE receta_id = %s ORDER BY id""", (r["id"],))
    return {"id": r["id"], "folio": r["folio"], "fecha": r["fecha"], "paciente_id": r["paciente_id"],
            "consulta_id": r["consulta_id"], "diagnostico": r["diagnostico"],
            "indicaciones_generales": r["indicaciones_generales"], "proxima_cita": r["proxima_cita"],
            "surtida": bool(r.get("venta_id")), "surtida_at": r.get("surtida_at"), "medicamentos": meds}


def recetas(conn, paciente_id):
    paciente(conn, paciente_id)
    return [_receta(conn, r) for r in fetch_all(
        conn, "SELECT * FROM recetas WHERE paciente_id = %s AND status = 1 ORDER BY fecha DESC, id DESC", (paciente_id,))]


def receta(conn, receta_id=None, folio=None):
    if folio:
        r = fetch_one(conn, "SELECT * FROM recetas WHERE folio = %s AND status = 1", (folio.strip().upper(),))
    else:
        r = fetch_one(conn, "SELECT * FROM recetas WHERE id = %s AND status = 1", (receta_id,))
    if not r:
        raise NegocioError("Receta no encontrada", 404)
    return _receta(conn, r)


def estudios(conn, paciente_id):
    paciente(conn, paciente_id)
    return fetch_all(conn, """SELECT id, consulta_id, tipo, nombre, estado, fecha_solicitud, fecha_resultado,
                                     laboratorio, resultado, interpretacion
                              FROM estudios WHERE paciente_id = %s AND status = 1
                              ORDER BY fecha_solicitud DESC, id DESC""", (paciente_id,))


def citas(conn, desde=None, dias=7):
    desde = desde or date.today()
    filas = fetch_all(conn, """SELECT ci.id, ci.paciente_id, ci.fecha_hora, ci.motivo, ci.estado,
                                      p.nombre, p.apellido_paterno, p.apellido_materno, p.expediente
                               FROM citas ci JOIN pacientes p ON p.id = ci.paciente_id
                               WHERE ci.status = 1 AND ci.fecha_hora >= %s AND ci.fecha_hora < %s
                               ORDER BY ci.fecha_hora""", (desde, desde + timedelta(days=int(dias))))
    return [{"id": c["id"], "paciente_id": c["paciente_id"], "paciente": _nombre(c), "expediente": c["expediente"],
             "fecha_hora": c["fecha_hora"], "motivo": c["motivo"], "estado": c["estado"]} for c in filas]


def crear_cita(conn, datos, medico_id):
    paciente(conn, datos["paciente_id"])
    fh = datos["fecha_hora"]
    if isinstance(fh, str):
        fh = datetime.fromisoformat(fh)
    with transaction(conn):
        nuevo = execute(conn, """INSERT INTO citas (paciente_id, medico_id, fecha_hora, motivo, estado, status)
                                 VALUES (%s, %s, %s, %s, 'programada', 1)""",
                        (datos["paciente_id"], medico_id, fh, (datos.get("motivo") or "")[:200] or None))
    return {"id": nuevo, "paciente_id": datos["paciente_id"], "fecha_hora": fh, "motivo": datos.get("motivo"),
            "estado": "programada"}
