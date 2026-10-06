"""
Control de antibióticos en el punto de venta.

Cada venta que incluye antibióticos guarda la receta presentada:
médico (nombre, cédula, domicilio), institución que la expidió, paciente
(interno de la clínica o nombre libre), vale de salida y el detalle de cada
antibiótico dispensado (compuesto, tipo, lote, caducidad y cantidad).
"""
from datetime import date

from ..db import execute, fetch_all, fetch_one
from ..utils.helpers import parse_fecha, to_int

DESTINOS = {"retenida": "Se recoge: SÍ", "sellada": "Se recoge: NO"}


class RegistroError(Exception):
    pass


def _t(valor, largo):
    valor = (str(valor).strip() if valor is not None else "")
    return valor[:largo] if valor else None


def limpiar_registro(datos):
    """Valida y normaliza los datos capturados en el punto de venta."""
    datos = datos or {}
    r = {
        "paciente_id": to_int(datos.get("paciente_id"), 0) or None,
        "paciente_nombre": _t(datos.get("paciente_nombre"), 150),
        "medico_nombre": _t(datos.get("medico_nombre"), 150),
        "medico_cedula": _t(datos.get("medico_cedula"), 30),
        "medico_domicilio": _t(datos.get("medico_domicilio"), 255),
        "institucion": _t(datos.get("institucion"), 150),
        "receta_folio": _t(datos.get("receta_folio"), 40),
        "receta_fecha": parse_fecha(datos.get("receta_fecha")),
        "receta_clinica_id": to_int(datos.get("receta_clinica_id"), 0) or None,
        "vale_salida": "SI" if datos.get("vale_salida") in (True, "SI", "si", "Sí", "SÍ", "1", 1, "on") else _t(datos.get("vale_salida"), 40),
        "destino_receta": datos.get("destino_receta") if datos.get("destino_receta") in DESTINOS else "retenida",
        "observaciones": _t(datos.get("observaciones"), 255),
    }
    faltan = [etq for k, etq in (("paciente_nombre", "nombre del paciente"), ("medico_nombre", "nombre del médico"),
                                 ("medico_cedula", "cédula profesional del médico")) if not r[k]]
    if faltan:
        raise RegistroError("Para vender antibióticos falta: " + ", ".join(faltan) + ".")
    if r["receta_fecha"] and r["receta_fecha"] > date.today():
        raise RegistroError("La fecha de la receta no puede ser futura.")
    return r


def guardar(cur, venta_id, usuario_id, registro, lineas):
    """Inserta el registro y el detalle de antibióticos de la venta (dentro de su transacción)."""
    ab = [ln for ln in lineas if ln.get("antibiotico")]
    if not ab:
        return None
    if registro["paciente_id"] and not fetch_one("SELECT id FROM pacientes WHERE id = %s AND status = 1",
                                                 (registro["paciente_id"],), cursor=cur):
        registro["paciente_id"] = None
    cols = ["venta_id", "usuario_id", "requiere_receta"] + list(registro)
    reg_id = execute(f"INSERT INTO antibioticos_recetas ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                     [venta_id, usuario_id, 1] + list(registro.values()), cursor=cur)
    for ln in ab:
        execute("""INSERT INTO antibioticos_dispensacion (registro_id, venta_id, producto_id, producto_nombre, compuesto,
                                                          tipo_antibiotico, lote, fecha_caducidad, cantidad)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (reg_id, venta_id, ln["producto_id"], ln["nombre"], ln.get("compuesto") or ln["nombre"],
                 ln.get("tipo_antibiotico"), ln.get("lote"), ln.get("fecha_caducidad"), ln["cantidad"]), cursor=cur)
    return reg_id


# ------------------------------------------------------------- autocompletado
def productos_info(ids):
    ids = [i for i in (to_int(x, 0) for x in ids) if i]
    if not ids:
        return []
    filas = fetch_all(f"""SELECT id, nombre, IFNULL(sustancia_activa, nombre) AS compuesto, tipo_antibiotico, lote,
                                 fecha_caducidad
                          FROM productos WHERE id IN ({', '.join(['%s'] * len(ids))}) AND antibiotico = 1""", ids)
    for f in filas:
        f["fecha_caducidad"] = f["fecha_caducidad"].isoformat() if hasattr(f["fecha_caducidad"], "isoformat") else f["fecha_caducidad"]
    return filas


def medicos(q="", limite=10):
    """Médicos usados antes (por cédula) + médicos del consultorio."""
    q = (q or "").strip()
    filtro, prm = "", []
    if q:
        filtro = " AND (medico_nombre LIKE %s OR medico_cedula LIKE %s)"
        prm = [f"%{q}%", f"%{q}%"]
    previos = fetch_all(f"""SELECT medico_cedula AS cedula, MAX(medico_nombre) AS nombre, MAX(medico_domicilio) AS domicilio,
                                   MAX(institucion) AS institucion, COUNT(*) AS veces, MAX(created_at) AS ultimo
                            FROM antibioticos_recetas WHERE 1 = 1 {filtro}
                            GROUP BY medico_cedula ORDER BY veces DESC, ultimo DESC LIMIT %s""", prm + [int(limite)])
    vistos = {m["cedula"] for m in previos}
    filtro2, prm2 = "", []
    if q:
        filtro2 = " AND (nombre_mostrar LIKE %s OR cedula_profesional LIKE %s)"
        prm2 = [f"%{q}%", f"%{q}%"]
    propios = fetch_all(f"""SELECT cedula_profesional AS cedula, nombre_mostrar AS nombre, direccion AS domicilio,
                                   COALESCE(NULLIF(institucion, ''), 'Consultorio') AS institucion
                            FROM perfil_medico WHERE cedula_profesional IS NOT NULL AND cedula_profesional <> '' {filtro2}""",
                        prm2)
    for m in previos:
        m.pop("ultimo", None)
    return previos + [m for m in propios if m["cedula"] not in vistos]


def pacientes(q="", limite=10):
    """Pacientes internos de la clínica + nombres registrados antes en ventas de antibióticos."""
    q = (q or "").strip()
    if len(q) < 2:
        return []
    internos = fetch_all("""SELECT id, expediente, TRIM(CONCAT(nombre, ' ', apellido_paterno, ' ', IFNULL(apellido_materno, ''))) AS nombre
                            FROM pacientes WHERE status = 1
                              AND (CONCAT(nombre, ' ', apellido_paterno, ' ', IFNULL(apellido_materno, '')) LIKE %s OR expediente LIKE %s)
                            ORDER BY apellido_paterno, nombre LIMIT %s""", (f"%{q}%", f"%{q}%", int(limite)))
    for p in internos:
        p["interno"] = True
    externos = fetch_all("""SELECT DISTINCT paciente_nombre AS nombre FROM antibioticos_recetas
                            WHERE paciente_id IS NULL AND paciente_nombre LIKE %s LIMIT %s""", (f"%{q}%", int(limite)))
    nombres = {p["nombre"].upper() for p in internos}
    return internos + [{"id": None, "expediente": None, "nombre": e["nombre"], "interno": False}
                       for e in externos if e["nombre"].upper() not in nombres]


# ------------------------------------------------------------------- reporte
def bitacora(desde, hasta, usuario_id=None, producto_id=None, tipo=None, q=""):
    """Bitácora de dispensación sin importes: incluye ventas antiguas sin registro."""
    sql = """SELECT v.id AS venta_id, v.folio, v.fecha, u.nombre AS gestiono, dv.cantidad,
                    p.id AS producto_id, p.nombre AS producto,
                    COALESCE(ad.compuesto, p.sustancia_activa, p.nombre) AS compuesto,
                    COALESCE(ad.tipo_antibiotico, p.tipo_antibiotico) AS tipo_antibiotico,
                    COALESCE(ad.lote, p.lote) AS lote, COALESCE(ad.fecha_caducidad, p.fecha_caducidad) AS caducidad,
                    ar.id AS registro_id, ar.paciente_id, ar.paciente_nombre, ar.medico_nombre, ar.medico_cedula,
                    ar.medico_domicilio, ar.institucion, ar.receta_folio, ar.receta_fecha, ar.vale_salida,
                    ar.destino_receta, ar.observaciones, pa.expediente
             FROM detalle_ventas dv
             JOIN ventas v ON v.id = dv.venta_id
             JOIN productos p ON p.id = dv.producto_id
             JOIN usuarios u ON u.id = v.usuario_id
             LEFT JOIN antibioticos_recetas ar ON ar.venta_id = v.id
             LEFT JOIN antibioticos_dispensacion ad ON ad.registro_id = ar.id AND ad.producto_id = dv.producto_id
             LEFT JOIN pacientes pa ON pa.id = ar.paciente_id
             WHERE p.antibiotico = 1 AND v.status = 1 AND v.fecha >= %s AND v.fecha < %s"""
    from datetime import datetime, timedelta
    prm = [datetime.combine(desde, datetime.min.time()), datetime.combine(hasta + timedelta(days=1), datetime.min.time())]
    if usuario_id:
        sql += " AND v.usuario_id = %s"
        prm.append(int(usuario_id))
    if producto_id:
        sql += " AND p.id = %s"
        prm.append(int(producto_id))
    if tipo:
        sql += " AND COALESCE(ad.tipo_antibiotico, p.tipo_antibiotico) = %s"
        prm.append(tipo)
    if q:
        sql += """ AND (ar.paciente_nombre LIKE %s OR ar.medico_nombre LIKE %s OR ar.medico_cedula LIKE %s
                        OR p.nombre LIKE %s OR p.sustancia_activa LIKE %s OR v.folio LIKE %s)"""
        prm += [f"%{q}%"] * 6
    sql += " ORDER BY v.fecha DESC, dv.id"
    filas = fetch_all(sql, prm)
    for f in filas:
        f["destino_texto"] = DESTINOS.get(f["destino_receta"] or "", "")
    return filas


def resumen(filas):
    """Tablas del reporte: por compuesto, médico, paciente, usuario y tipo (sin importes)."""
    con_registro = [f for f in filas if f["registro_id"]]
    por_compuesto, por_tipo, por_usuario, por_medico, por_paciente = {}, {}, {}, {}, {}
    for f in filas:
        cant = int(f["cantidad"] or 0)
        c = por_compuesto.setdefault(f["compuesto"], {"compuesto": f["compuesto"], "tipo": f["tipo_antibiotico"],
                                                       "unidades": 0, "ventas": set(), "lotes": set(), "productos": set()})
        c["unidades"] += cant
        c["ventas"].add(f["venta_id"])
        if f["lote"]:
            c["lotes"].add(f["lote"])
        c["productos"].add(f["producto"])
        t = f["tipo_antibiotico"] or "Sin clasificar"
        por_tipo[t] = por_tipo.get(t, 0) + cant
        u = por_usuario.setdefault(f["gestiono"], {"usuario": f["gestiono"], "ventas": set(), "unidades": 0,
                                                    "sin_registro": set(), "ultima": None})
        u["ventas"].add(f["venta_id"])
        u["unidades"] += cant
        u["ultima"] = max(filter(None, [u["ultima"], f["fecha"]]))
        if not f["registro_id"]:
            u["sin_registro"].add(f["venta_id"])
        if not f["registro_id"]:
            continue
        m = por_medico.setdefault(f["medico_cedula"], {"cedula": f["medico_cedula"], "nombre": f["medico_nombre"],
                                                        "domicilio": f["medico_domicilio"], "institucion": f["institucion"],
                                                        "recetas": set(), "unidades": 0, "compuestos": set(),
                                                        "pacientes": set(), "ultima": None})
        m["recetas"].add(f["venta_id"])
        m["unidades"] += cant
        m["compuestos"].add(f["compuesto"].upper())
        m["pacientes"].add((f["paciente_nombre"] or "").upper())
        m["ultima"] = max(filter(None, [m["ultima"], f["fecha"]]))
        clave = f"id{f['paciente_id']}" if f["paciente_id"] else (f["paciente_nombre"] or "").upper()
        p = por_paciente.setdefault(clave, {"nombre": (f["paciente_nombre"] or "").upper(), "paciente_id": f["paciente_id"],
                                            "expediente": f["expediente"], "ventas": set(), "unidades": 0,
                                            "compuestos": set(), "medicos": set(), "ultima": None})
        p["ventas"].add(f["venta_id"])
        p["unidades"] += cant
        p["compuestos"].add(f["compuesto"].upper())
        p["medicos"].add(f"{f['medico_nombre']} ({f['medico_cedula']})")
        p["ultima"] = max(filter(None, [p["ultima"], f["fecha"]]))

    def lista(dic, orden):
        salida = []
        for d in dic.values():
            d = dict(d)
            for k, v in d.items():
                if isinstance(v, set):
                    d[k] = sorted(v) if k in ("compuestos", "medicos", "pacientes", "lotes", "productos") else len(v)
            for k in ("recetas", "ventas", "sin_registro"):
                if isinstance(d.get(k), list):
                    d[k] = len(d[k])
            salida.append(d)
        return sorted(salida, key=orden)

    return {
        "dispensaciones": len({f["venta_id"] for f in filas}),
        "unidades": sum(int(f["cantidad"] or 0) for f in filas),
        "pacientes": len(por_paciente),
        "medicos": len(por_medico),
        "sin_registro": len({f["venta_id"] for f in filas if not f["registro_id"]}),
        "compuestos": lista(por_compuesto, lambda x: -x["unidades"]),
        "por_tipo": sorted(por_tipo.items(), key=lambda x: -x[1]),
        "por_usuario": lista(por_usuario, lambda x: -x["unidades"]),
        "por_medico": lista(por_medico, lambda x: (-x["recetas"], x["nombre"] or "")),
        "por_paciente": lista(por_paciente, lambda x: (-x["ventas"], x["nombre"])),
        "sin_registro_filas": [f for f in filas if not f["registro_id"]],
    }
