"""
Módulo clínico: expediente de pacientes, consultas, recetas, estudios y agenda.

Toda la información queda ligada al paciente (paciente_id) para poder
reconstruir su historial completo. Nada se borra físicamente: se usa
`status = 0` (baja lógica) para conservar la trazabilidad del expediente.
"""
from datetime import date, datetime, timedelta

from ..db import execute, fetch_all, fetch_one, fetch_value, to_float, transaction
from ..utils.helpers import parse_fecha, to_int, to_num

SEXOS = {"F": "Femenino", "M": "Masculino", "O": "Otro"}
TIPOS_SANGRE = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]
ESTADOS_CIVILES = ["Soltero(a)", "Casado(a)", "Unión libre", "Divorciado(a)", "Viudo(a)"]
TIPOS_CONSULTA = {
    "primera_vez": "Primera vez",
    "subsecuente": "Subsecuente",
    "control": "Control",
    "seguimiento": "Seguimiento",
    "urgencia": "Urgencia",
}
TIPOS_ALERGIA = {"medicamento": "Medicamento", "alimento": "Alimento", "ambiental": "Ambiental", "otro": "Otro"}
SEVERIDADES = {"leve": "Leve", "moderada": "Moderada", "grave": "Grave"}
ESTADOS_PADECIMIENTO = {"activo": "Activo", "controlado": "Controlado", "resuelto": "Resuelto"}
TIPOS_ESTUDIO = {"laboratorio": "Laboratorio", "imagen": "Imagen", "gabinete": "Gabinete",
                 "patologia": "Patología", "otro": "Otro"}
ESTADOS_ESTUDIO = {"solicitado": "Solicitado", "en_proceso": "En proceso",
                   "resultado": "Con resultado", "cancelado": "Cancelado"}
ESTADOS_CITA = {"programada": "Programada", "confirmada": "Confirmada", "atendida": "Atendida",
                "cancelada": "Cancelada", "no_asistio": "No asistió"}
VIAS = ["Oral", "Sublingual", "Intramuscular", "Intravenosa", "Subcutánea", "Tópica", "Inhalada",
        "Oftálmica", "Ótica", "Nasal", "Rectal", "Vaginal"]


class ClinicaError(Exception):
    pass


# =================================================================== utilidades
def _txt(valor, largo=None):
    v = (valor or "").strip() if isinstance(valor, str) else valor
    if v in ("", None):
        return None
    return v[:largo] if (largo and isinstance(v, str)) else v


def edad(fecha_nacimiento, referencia=None, completa=False):
    """Edad legible: '57 años', '8 años 7 meses', '5 meses'. Con completa=True: '53 años 5 meses'."""
    if not fecha_nacimiento:
        return None
    ref = referencia or date.today()
    if isinstance(ref, datetime):
        ref = ref.date()
    anios = ref.year - fecha_nacimiento.year - ((ref.month, ref.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    meses = (ref.year - fecha_nacimiento.year) * 12 + ref.month - fecha_nacimiento.month - (ref.day < fecha_nacimiento.day)
    if anios < 1:
        return f"{max(meses, 0)} mes{'es' if meses != 1 else ''}"
    if anios < 12 or completa:
        m = meses - anios * 12
        return f"{anios} año{'s' if anios != 1 else ''}" + (f" {m} mes{'es' if m != 1 else ''}" if m else "")
    return f"{anios} años"


def edad_anios(fecha_nacimiento):
    if not fecha_nacimiento:
        return None
    hoy = date.today()
    return hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))


def calcular_imc(peso_kg, talla_cm):
    peso, talla = to_num(peso_kg, 0), to_num(talla_cm, 0)
    if peso <= 0 or talla <= 0:
        return None
    return round(peso / ((talla / 100) ** 2), 2)


def clasificar_imc(imc):
    if imc is None:
        return None, "neutral"
    imc = to_float(imc)
    if imc < 18.5:
        return "Bajo peso", "warning"
    if imc < 25:
        return "Normal", "success"
    if imc < 30:
        return "Sobrepeso", "warning"
    if imc < 35:
        return "Obesidad grado I", "danger"
    if imc < 40:
        return "Obesidad grado II", "danger"
    return "Obesidad grado III", "danger"


def clasificar_ta(sis, dia):
    if not sis or not dia:
        return None, "neutral"
    if sis >= 180 or dia >= 120:
        return "Crisis hipertensiva", "danger"
    if sis >= 140 or dia >= 90:
        return "Hipertensión", "danger"
    if sis >= 130 or dia >= 80:
        return "Elevada", "warning"
    return "Normal", "success"


def nombre_completo(p):
    return " ".join(x for x in (p.get("nombre"), p.get("apellido_paterno"), p.get("apellido_materno")) if x)


def _folio(prefijo, nuevo_id):
    return f"{prefijo}{nuevo_id:06d}"


# =================================================================== pacientes
SQL_PACIENTE_LISTA = """
    SELECT p.*,
           (SELECT COUNT(*) FROM consultas_medicas c WHERE c.paciente_id = p.id AND c.status = 1) AS visitas,
           (SELECT MAX(c.fecha) FROM consultas_medicas c WHERE c.paciente_id = p.id AND c.status = 1) AS ultima_visita,
           (SELECT GROUP_CONCAT(pp.nombre SEPARATOR '||') FROM paciente_padecimientos pp
             WHERE pp.paciente_id = p.id AND pp.status = 1 AND pp.estado <> 'resuelto') AS padecimientos,
           (SELECT COUNT(*) FROM paciente_alergias a WHERE a.paciente_id = p.id AND a.status = 1) AS alergias,
           (SELECT MIN(ci.fecha_hora) FROM citas ci WHERE ci.paciente_id = p.id AND ci.status = 1
             AND ci.estado IN ('programada', 'confirmada') AND ci.fecha_hora >= %s) AS proxima_cita
    FROM pacientes p
    WHERE p.status = 1
"""


def _decorar(p):
    p["nombre_completo"] = nombre_completo(p)
    p["edad"] = edad(p.get("fecha_nacimiento"))
    p["edad_anios"] = edad_anios(p.get("fecha_nacimiento"))
    p["sexo_texto"] = SEXOS.get(p.get("sexo") or "", "—")
    if "padecimientos" in p:
        p["padecimientos_lista"] = [x for x in (p.get("padecimientos") or "").split("||") if x]
    return p


def listar_pacientes(q="", padecimiento="", sexo="", orden="recientes", limite=500):
    sql = SQL_PACIENTE_LISTA
    params = [datetime.now()]
    if q:
        sql += """ AND (CONCAT(p.nombre, ' ', p.apellido_paterno, ' ', IFNULL(p.apellido_materno, '')) LIKE %s
                   OR p.expediente LIKE %s OR p.curp LIKE %s OR p.telefono LIKE %s)"""
        params += [f"%{q}%"] * 4
    if padecimiento:
        sql += """ AND EXISTS (SELECT 1 FROM paciente_padecimientos pp WHERE pp.paciente_id = p.id
                   AND pp.status = 1 AND (pp.nombre LIKE %s OR pp.cie10 LIKE %s))"""
        params += [f"%{padecimiento}%"] * 2
    if sexo in SEXOS:
        sql += " AND p.sexo = %s"
        params.append(sexo)
    orden_sql = {
        "recientes": "ultima_visita IS NULL, ultima_visita DESC, p.id DESC",
        "nombre": "p.apellido_paterno, p.apellido_materno, p.nombre",
        "visitas": "visitas DESC, p.apellido_paterno",
        "nuevos": "p.id DESC",
    }.get(orden, "p.id DESC")
    sql += f" ORDER BY {orden_sql} LIMIT %s"
    params.append(int(limite))
    return [_decorar(p) for p in fetch_all(sql, params)]


def buscar_pacientes(q, limite=10):
    return [{"id": p["id"], "expediente": p["expediente"], "nombre": p["nombre_completo"],
             "edad": p["edad"], "telefono": p["telefono"], "visitas": p["visitas"]}
            for p in listar_pacientes(q=q, orden="nombre", limite=limite)]


def obtener_paciente(paciente_id):
    p = fetch_one(SQL_PACIENTE_LISTA + " AND p.id = %s", (datetime.now(), paciente_id))
    if not p:
        raise ClinicaError("Paciente no encontrado.")
    return _decorar(p)


CAMPOS_PACIENTE = {
    "nombre": 80, "apellido_paterno": 80, "apellido_materno": 80, "sexo": 1, "curp": 18,
    "tipo_sangre": 5, "estado_civil": 20, "ocupacion": 100, "escolaridad": 60, "telefono": 20,
    "telefono_alt": 20, "email": 120, "direccion": 255, "ciudad": 80, "codigo_postal": 10,
    "contacto_nombre": 120, "contacto_parentesco": 40, "contacto_telefono": 20, "aseguradora": 80,
    "poliza": 40, "notas": None,
}


def leer_paciente(form):
    d = {k: _txt(form.get(k), largo) for k, largo in CAMPOS_PACIENTE.items()}
    d["fecha_nacimiento"] = parse_fecha(form.get("fecha_nacimiento"))
    if d.get("curp"):
        d["curp"] = d["curp"].upper()
    if d.get("sexo") and d["sexo"] not in SEXOS:
        d["sexo"] = None
    errores = []
    if not d["nombre"] or not d["apellido_paterno"]:
        errores.append("Nombre y apellido paterno son obligatorios.")
    if d["fecha_nacimiento"] and d["fecha_nacimiento"] > date.today():
        errores.append("La fecha de nacimiento no puede ser futura.")
    return d, errores


def guardar_paciente(datos, usuario_id, paciente_id=None):
    campos = list(CAMPOS_PACIENTE) + ["fecha_nacimiento"]
    if paciente_id:
        sets = ", ".join(f"{c} = %s" for c in campos)
        execute(f"UPDATE pacientes SET {sets} WHERE id = %s", [datos[c] for c in campos] + [paciente_id])
        return paciente_id
    with transaction() as cur:
        cols = ", ".join(campos + ["created_by", "status"])
        marcas = ", ".join(["%s"] * (len(campos) + 2))
        nuevo = execute(f"INSERT INTO pacientes ({cols}) VALUES ({marcas})",
                        [datos[c] for c in campos] + [usuario_id, 1], cursor=cur)
        execute("UPDATE pacientes SET expediente = %s WHERE id = %s", (_folio("P", nuevo), nuevo), cursor=cur)
        execute("INSERT INTO paciente_antecedentes (paciente_id) VALUES (%s)", (nuevo,), cursor=cur)
    return nuevo


def baja_paciente(paciente_id):
    execute("UPDATE pacientes SET status = 0 WHERE id = %s", (paciente_id,))


# -------------------------------------------------------------- antecedentes
CAMPOS_ANTECEDENTES = ["heredofamiliares", "personales_patologicos", "personales_no_patologicos", "quirurgicos",
                       "traumaticos", "transfusionales", "gineco_obstetricos", "tabaquismo", "alcoholismo",
                       "toxicomanias", "actividad_fisica", "alimentacion", "inmunizaciones"]


def obtener_antecedentes(paciente_id):
    return fetch_one("SELECT * FROM paciente_antecedentes WHERE paciente_id = %s", (paciente_id,)) or {}


def guardar_antecedentes(paciente_id, form):
    valores = [_txt(form.get(c)) for c in CAMPOS_ANTECEDENTES]
    if fetch_one("SELECT paciente_id FROM paciente_antecedentes WHERE paciente_id = %s", (paciente_id,)):
        sets = ", ".join(f"{c} = %s" for c in CAMPOS_ANTECEDENTES)
        execute(f"UPDATE paciente_antecedentes SET {sets} WHERE paciente_id = %s", valores + [paciente_id])
    else:
        cols = ", ".join(["paciente_id"] + CAMPOS_ANTECEDENTES)
        execute(f"INSERT INTO paciente_antecedentes ({cols}) VALUES ({', '.join(['%s'] * (len(valores) + 1))})",
                [paciente_id] + valores)


# ------------------------------------------------- alergias / padecimientos / meds
def agregar_alergia(paciente_id, form):
    alergeno = _txt(form.get("alergeno"), 120)
    if not alergeno:
        raise ClinicaError("Indica el alérgeno.")
    execute("""INSERT INTO paciente_alergias (paciente_id, alergeno, tipo, reaccion, severidad)
               VALUES (%s, %s, %s, %s, %s)""",
            (paciente_id, alergeno, form.get("tipo") if form.get("tipo") in TIPOS_ALERGIA else "otro",
             _txt(form.get("reaccion"), 255),
             form.get("severidad") if form.get("severidad") in SEVERIDADES else "moderada"))


def agregar_padecimiento(paciente_id, form, cursor=None):
    nombre = _txt(form.get("nombre"), 200)
    if not nombre:
        raise ClinicaError("Indica el nombre del padecimiento.")
    return execute("""INSERT INTO paciente_padecimientos (paciente_id, nombre, cie10, tipo, estado, fecha_diagnostico, notas)
                      VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                   (paciente_id, nombre, _txt(form.get("cie10"), 10),
                    form.get("tipo") if form.get("tipo") in ("cronico", "agudo") else "cronico",
                    form.get("estado") if form.get("estado") in ESTADOS_PADECIMIENTO else "activo",
                    parse_fecha(form.get("fecha_diagnostico")) or date.today(), _txt(form.get("notas"))),
                   cursor=cursor)


def padecimiento_desde_diagnostico(cur, paciente_id, descripcion, cie10=None, cronico=False):
    """
    Guarda automáticamente un diagnóstico en la lista de padecimientos del paciente.
    Si ya lo tiene (mismo CIE-10 o mismo nombre) no lo duplica: lo reutiliza y, si
    estaba resuelto, lo vuelve a marcar activo.
    """
    cie10 = _txt(cie10, 10)
    existente = None
    if cie10:
        existente = fetch_one("""SELECT id, estado FROM paciente_padecimientos
                                 WHERE paciente_id = %s AND status = 1 AND cie10 = %s ORDER BY id LIMIT 1""",
                              (paciente_id, cie10), cursor=cur)
    if not existente:
        existente = fetch_one("""SELECT id, estado FROM paciente_padecimientos
                                 WHERE paciente_id = %s AND status = 1 AND LOWER(nombre) = LOWER(%s) ORDER BY id LIMIT 1""",
                              (paciente_id, descripcion), cursor=cur)
    if existente:
        if existente["estado"] == "resuelto":
            execute("UPDATE paciente_padecimientos SET estado = 'activo', fecha_diagnostico = %s WHERE id = %s",
                    (date.today(), existente["id"]), cursor=cur)
        return existente["id"]
    return agregar_padecimiento(paciente_id, {"nombre": descripcion, "cie10": cie10,
                                              "tipo": "cronico" if cronico else "agudo", "estado": "activo"}, cursor=cur)


def aprender_diagnostico(cur, descripcion, cie10=None):
    """Catálogo propio: cada diagnóstico usado queda disponible para autocompletar."""
    descripcion = _txt(descripcion, 200)
    if not descripcion:
        return
    fila = fetch_one("SELECT id FROM diagnosticos_frecuentes WHERE descripcion = %s", (descripcion,), cursor=cur)
    if fila:
        execute("""UPDATE diagnosticos_frecuentes SET usos = usos + 1, ultimo_uso = %s,
                          cie10 = COALESCE(%s, cie10) WHERE id = %s""",
                (datetime.now(), _txt(cie10, 10), fila["id"]), cursor=cur)
    else:
        execute("INSERT INTO diagnosticos_frecuentes (descripcion, cie10, usos, ultimo_uso) VALUES (%s, %s, 1, %s)",
                (descripcion, _txt(cie10, 10), datetime.now()), cursor=cur)


def diagnosticos_frecuentes(limite=300):
    return fetch_all("""SELECT descripcion AS d, cie10 AS c, usos FROM diagnosticos_frecuentes
                        ORDER BY usos DESC, ultimo_uso DESC LIMIT %s""", (int(limite),))


def actualizar_padecimiento(paciente_id, padecimiento_id, estado):
    if estado not in ESTADOS_PADECIMIENTO:
        raise ClinicaError("Estado inválido.")
    execute("UPDATE paciente_padecimientos SET estado = %s WHERE id = %s AND paciente_id = %s",
            (estado, padecimiento_id, paciente_id))


def agregar_medicamento(paciente_id, form):
    med = _txt(form.get("medicamento"), 150)
    if not med:
        raise ClinicaError("Indica el medicamento.")
    execute("""INSERT INTO paciente_medicamentos (paciente_id, medicamento, dosis, frecuencia, via, fecha_inicio, indicado_por)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (paciente_id, med, _txt(form.get("dosis"), 80), _txt(form.get("frecuencia"), 80),
             _txt(form.get("via"), 40), parse_fecha(form.get("fecha_inicio")) or date.today(),
             _txt(form.get("indicado_por"), 120)))


def suspender_medicamento(paciente_id, medicamento_id):
    execute("UPDATE paciente_medicamentos SET activo = 0, fecha_fin = %s WHERE id = %s AND paciente_id = %s",
            (date.today(), medicamento_id, paciente_id))


TABLAS_BAJA = {"alergia": "paciente_alergias", "padecimiento": "paciente_padecimientos",
               "medicamento": "paciente_medicamentos", "estudio": "estudios", "cita": "citas"}


def dar_de_baja(tipo, paciente_id, item_id):
    tabla = TABLAS_BAJA.get(tipo)
    if not tabla:
        raise ClinicaError("Registro inválido.")
    execute(f"UPDATE {tabla} SET status = 0 WHERE id = %s AND paciente_id = %s", (item_id, paciente_id))


# =================================================================== expediente
def expediente(paciente_id):
    p = obtener_paciente(paciente_id)
    consultas = fetch_all(
        """SELECT c.*, u.nombre AS medico FROM consultas_medicas c JOIN usuarios u ON u.id = c.medico_id
           WHERE c.paciente_id = %s AND c.status = 1 ORDER BY c.fecha DESC, c.id DESC""", (paciente_id,))
    diags = fetch_all(
        """SELECT d.* FROM consulta_diagnosticos d JOIN consultas_medicas c ON c.id = d.consulta_id
           WHERE c.paciente_id = %s ORDER BY d.id""", (paciente_id,))
    por_consulta = {}
    for d in diags:
        por_consulta.setdefault(d["consulta_id"], []).append(d)
    for c in consultas:
        c["diagnosticos"] = por_consulta.get(c["id"], [])
        c["tipo_texto"] = TIPOS_CONSULTA.get(c["tipo"], c["tipo"])

    recetas = fetch_all("""SELECT r.*, (SELECT COUNT(*) FROM receta_medicamentos m WHERE m.receta_id = r.id) AS n_meds
                           FROM recetas r WHERE r.paciente_id = %s AND r.status = 1 ORDER BY r.fecha DESC""",
                        (paciente_id,))
    meds_receta = fetch_all("""SELECT m.* FROM receta_medicamentos m JOIN recetas r ON r.id = m.receta_id
                               WHERE r.paciente_id = %s ORDER BY m.id""", (paciente_id,))
    por_receta = {}
    for m in meds_receta:
        por_receta.setdefault(m["receta_id"], []).append(m)
    for r in recetas:
        r["medicamentos"] = por_receta.get(r["id"], [])

    estudios = fetch_all("""SELECT * FROM estudios WHERE paciente_id = %s AND status = 1
                            ORDER BY fecha_solicitud DESC, id DESC""", (paciente_id,))
    citas = fetch_all("""SELECT * FROM citas WHERE paciente_id = %s AND status = 1
                         ORDER BY fecha_hora DESC""", (paciente_id,))
    alergias = fetch_all("SELECT * FROM paciente_alergias WHERE paciente_id = %s AND status = 1 ORDER BY id",
                         (paciente_id,))
    padecimientos = fetch_all("""SELECT * FROM paciente_padecimientos WHERE paciente_id = %s AND status = 1
                                 ORDER BY CASE estado WHEN 'activo' THEN 0 WHEN 'controlado' THEN 1 ELSE 2 END, fecha_diagnostico DESC""",
                              (paciente_id,))
    medicamentos = fetch_all("""SELECT * FROM paciente_medicamentos WHERE paciente_id = %s AND status = 1
                                ORDER BY activo DESC, fecha_inicio DESC""", (paciente_id,))

    ultima = consultas[0] if consultas else None
    vitales = list(reversed([c for c in consultas if c["peso_kg"] or c["ta_sistolica"] or c["glucosa_capilar"]]))

    # Línea de tiempo combinada
    eventos = []
    for c in consultas:
        eventos.append({"fecha": c["fecha"], "tipo": "consulta", "icono": "fa-stethoscope", "color": "accent",
                        "titulo": f"Consulta · {c['tipo_texto']}", "detalle": c["motivo"], "id": c["id"]})
    for r in recetas:
        eventos.append({"fecha": r["fecha"], "tipo": "receta", "icono": "fa-prescription", "color": "purple",
                        "titulo": f"Receta {r['folio']}", "detalle": f"{r['n_meds']} medicamento(s)", "id": r["id"]})
    for e in estudios:
        f = e["fecha_resultado"] if e["estado"] == "resultado" and e["fecha_resultado"] else e["fecha_solicitud"]
        eventos.append({"fecha": datetime.combine(f, datetime.min.time()) if isinstance(f, date) and not isinstance(f, datetime) else f,
                        "tipo": "estudio", "icono": "fa-flask", "color": "info",
                        "titulo": f"Estudio · {ESTADOS_ESTUDIO.get(e['estado'], e['estado'])}",
                        "detalle": e["nombre"], "id": e["id"]})
    eventos = sorted([e for e in eventos if e["fecha"]], key=lambda e: e["fecha"], reverse=True)

    return {
        "paciente": p,
        "antecedentes": obtener_antecedentes(paciente_id),
        "alergias": alergias,
        "padecimientos": padecimientos,
        "medicamentos": medicamentos,
        "consultas": consultas,
        "recetas": recetas,
        "estudios": estudios,
        "citas": citas,
        "ultima": ultima,
        "vitales": vitales,
        "eventos": eventos[:40],
        "stats": {
            "visitas": len(consultas),
            "recetas": len(recetas),
            "estudios": len(estudios),
            "estudios_pendientes": sum(1 for e in estudios if e["estado"] in ("solicitado", "en_proceso")),
            "padecimientos_activos": sum(1 for x in padecimientos if x["estado"] != "resuelto"),
            "primera_visita": consultas[-1]["fecha"] if consultas else None,
            "gasto_consultas": sum(to_float(c["costo"]) for c in consultas),
        },
    }


# =================================================================== consultas
CAMPOS_VITALES = {"peso_kg": float, "talla_cm": float, "temperatura": float, "ta_sistolica": int,
                  "ta_diastolica": int, "frecuencia_cardiaca": int, "frecuencia_respiratoria": int,
                  "saturacion_o2": int, "glucosa_capilar": int, "perimetro_abdominal": float}


def _num_o_none(valor, tipo):
    if valor in (None, ""):
        return None
    try:
        n = float(str(valor).replace(",", "."))
    except ValueError:
        return None
    if n <= 0:
        return None
    return int(round(n)) if tipo is int else round(n, 2)


def crear_consulta(paciente_id, medico_id, form, diagnosticos, medicamentos, estudios_sol, indicaciones_receta=""):
    """
    Registra la consulta completa en una sola transacción:
    consulta + diagnósticos (+ alta en padecimientos) + receta + estudios + próxima cita.
    """
    obtener_paciente(paciente_id)
    motivo = _txt(form.get("motivo"), 255)
    if not motivo:
        raise ClinicaError("El motivo de consulta es obligatorio.")
    vit = {k: _num_o_none(form.get(k), t) for k, t in CAMPOS_VITALES.items()}
    imc = calcular_imc(vit["peso_kg"], vit["talla_cm"])
    proxima = parse_fecha(form.get("proxima_cita"))
    hora_cita = (form.get("proxima_cita_hora") or "09:00").strip()[:5]
    tipo = form.get("tipo") if form.get("tipo") in TIPOS_CONSULTA else "subsecuente"
    diag_texto = "; ".join(d["descripcion"] for d in diagnosticos if d.get("descripcion")) or _txt(form.get("diagnostico"))

    with transaction() as cur:
        consulta_id = execute(
            """INSERT INTO consultas_medicas (paciente_id, medico_id, fecha, tipo, motivo, padecimiento_actual, interrogatorio,
                   peso_kg, talla_cm, imc, temperatura, ta_sistolica, ta_diastolica, frecuencia_cardiaca,
                   frecuencia_respiratoria, saturacion_o2, glucosa_capilar, perimetro_abdominal,
                   exploracion_fisica, resultados_previos, diagnostico, plan_tratamiento, indicaciones, pronostico,
                   proxima_cita, costo, estado, status)
               VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s, %s, %s, %s, 'cerrada', 1)""",
            (paciente_id, medico_id, tipo, motivo, _txt(form.get("padecimiento_actual")), _txt(form.get("interrogatorio")),
             vit["peso_kg"], vit["talla_cm"], imc, vit["temperatura"], vit["ta_sistolica"], vit["ta_diastolica"],
             vit["frecuencia_cardiaca"], vit["frecuencia_respiratoria"], vit["saturacion_o2"], vit["glucosa_capilar"],
             vit["perimetro_abdominal"], _txt(form.get("exploracion_fisica")), _txt(form.get("resultados_previos")),
             diag_texto, _txt(form.get("plan_tratamiento")), _txt(form.get("indicaciones")),
             _txt(form.get("pronostico"), 120), proxima, round(to_num(form.get("costo"), 0), 2)),
            cursor=cur)
        execute("UPDATE consultas_medicas SET folio = %s WHERE id = %s", (_folio("C", consulta_id), consulta_id), cursor=cur)

        for i, d in enumerate(diagnosticos):
            desc = _txt(d.get("descripcion"), 200)
            if not desc:
                continue
            padecimiento_id = None
            # Por defecto el diagnóstico se guarda solo en el expediente (salvo que se desmarque)
            if d.get("agregar", True) not in (False, "false", "0", 0, ""):
                padecimiento_id = padecimiento_desde_diagnostico(cur, paciente_id, desc, d.get("cie10"), d.get("cronico"))
            aprender_diagnostico(cur, desc, d.get("cie10"))
            execute("""INSERT INTO consulta_diagnosticos (consulta_id, descripcion, cie10, tipo, padecimiento_id)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (consulta_id, desc, _txt(d.get("cie10"), 10),
                     d.get("tipo") if d.get("tipo") in ("principal", "secundario", "presuntivo")
                     else ("principal" if i == 0 else "secundario"), padecimiento_id), cursor=cur)

        receta_id = None
        meds = [m for m in medicamentos if _txt(m.get("medicamento"))]
        if meds:
            receta_id = _insertar_receta(cur, paciente_id, medico_id, consulta_id, diag_texto,
                                         indicaciones_receta or _txt(form.get("indicaciones")), proxima, meds)

        for e in estudios_sol:
            if _txt(e.get("nombre")):
                execute("""INSERT INTO estudios (paciente_id, consulta_id, tipo, nombre, fecha_solicitud, estado, status)
                           VALUES (%s, %s, %s, %s, %s, 'solicitado', 1)""",
                        (paciente_id, consulta_id, e.get("tipo") if e.get("tipo") in TIPOS_ESTUDIO else "laboratorio",
                         _txt(e.get("nombre"), 150), date.today()), cursor=cur)

        # Marca como atendida la cita de hoy (si existía) y agenda la próxima
        execute("""UPDATE citas SET estado = 'atendida', consulta_id = %s
                   WHERE paciente_id = %s AND status = 1 AND estado IN ('programada', 'confirmada')
                     AND fecha_hora >= %s AND fecha_hora < %s""",
                (consulta_id, paciente_id, date.today(), date.today() + timedelta(days=1)), cursor=cur)
        if proxima:
            try:
                fh = datetime.strptime(f"{proxima} {hora_cita}", "%Y-%m-%d %H:%M")
            except ValueError:
                fh = datetime.combine(proxima, datetime.min.time()).replace(hour=9)
            execute("""INSERT INTO citas (paciente_id, medico_id, fecha_hora, motivo, estado, status)
                       VALUES (%s, %s, %s, %s, 'programada', 1)""",
                    (paciente_id, medico_id, fh, f"Seguimiento: {motivo}"[:200]), cursor=cur)
    return consulta_id, receta_id


def obtener_consulta(consulta_id):
    c = fetch_one("""SELECT c.*, u.nombre AS medico FROM consultas_medicas c JOIN usuarios u ON u.id = c.medico_id
                     WHERE c.id = %s AND c.status = 1""", (consulta_id,))
    if not c:
        raise ClinicaError("Consulta no encontrada.")
    c["tipo_texto"] = TIPOS_CONSULTA.get(c["tipo"], c["tipo"])
    c["diagnosticos"] = fetch_all("SELECT * FROM consulta_diagnosticos WHERE consulta_id = %s ORDER BY id", (consulta_id,))
    c["notas"] = fetch_all("""SELECT n.*, u.nombre AS autor FROM consulta_notas n JOIN usuarios u ON u.id = n.usuario_id
                              WHERE n.consulta_id = %s ORDER BY n.created_at""", (consulta_id,))
    c["recetas"] = fetch_all("""SELECT r.*, v.folio AS venta_folio FROM recetas r LEFT JOIN ventas v ON v.id = r.venta_id
                                WHERE r.consulta_id = %s AND r.status = 1""", (consulta_id,))
    c["estudios"] = fetch_all("SELECT * FROM estudios WHERE consulta_id = %s AND status = 1", (consulta_id,))
    c["venta"] = fetch_one("SELECT id, folio, fecha, total FROM ventas WHERE id = %s", (c["venta_id"],)) if c.get("venta_id") else None
    c["por_cobrar"] = (to_num(c["costo"], 0) > 0 and not c.get("venta_id")) or any(not r["venta_id"] for r in c["recetas"])
    return c


def agregar_nota(consulta_id, usuario_id, nota):
    nota = _txt(nota)
    if not nota:
        raise ClinicaError("Escribe la nota.")
    obtener_consulta(consulta_id)
    execute("INSERT INTO consulta_notas (consulta_id, usuario_id, nota) VALUES (%s, %s, %s)",
            (consulta_id, usuario_id, nota))


def listar_consultas(q="", desde=None, hasta=None, tipo="", limite=300):
    sql = """SELECT c.id, c.folio, c.fecha, c.tipo, c.motivo, c.diagnostico, c.costo, c.paciente_id,
                    p.expediente, p.nombre, p.apellido_paterno, p.apellido_materno, p.fecha_nacimiento, p.sexo,
                    u.nombre AS medico
             FROM consultas_medicas c
             JOIN pacientes p ON p.id = c.paciente_id
             JOIN usuarios u ON u.id = c.medico_id
             WHERE c.status = 1"""
    params = []
    if q:
        sql += """ AND (CONCAT(p.nombre, ' ', p.apellido_paterno, ' ', IFNULL(p.apellido_materno, '')) LIKE %s
                   OR c.folio LIKE %s OR c.motivo LIKE %s OR c.diagnostico LIKE %s)"""
        params += [f"%{q}%"] * 4
    if desde:
        sql += " AND c.fecha >= %s"
        params.append(desde)
    if hasta:
        sql += " AND c.fecha < %s"
        params.append(hasta + timedelta(days=1))
    if tipo in TIPOS_CONSULTA:
        sql += " AND c.tipo = %s"
        params.append(tipo)
    sql += " ORDER BY c.fecha DESC, c.id DESC LIMIT %s"
    params.append(int(limite))
    filas = fetch_all(sql, params)
    for c in filas:
        c["paciente"] = nombre_completo(c)
        c["edad"] = edad(c["fecha_nacimiento"])
        c["tipo_texto"] = TIPOS_CONSULTA.get(c["tipo"], c["tipo"])
    return filas


# =================================================================== recetas
CAMPOS_MED = {"medicamento": 150, "presentacion": 100, "dosis": 80, "via": 40, "frecuencia": 80,
              "duracion": 60, "cantidad": 40, "indicaciones": 255}


def _insertar_receta(cur, paciente_id, medico_id, consulta_id, diagnostico, indicaciones, proxima, meds):
    receta_id = execute(
        """INSERT INTO recetas (paciente_id, consulta_id, medico_id, fecha, diagnostico, indicaciones_generales,
                                proxima_cita, status)
           VALUES (%s, %s, %s, NOW(), %s, %s, %s, 1)""",
        (paciente_id, consulta_id, medico_id, _txt(diagnostico, 255), _txt(indicaciones), proxima), cursor=cur)
    execute("UPDATE recetas SET folio = %s WHERE id = %s", (_folio("R", receta_id), receta_id), cursor=cur)
    for m in meds:
        valores = [_txt(m.get(k), largo) for k, largo in CAMPOS_MED.items()]
        execute(f"""INSERT INTO receta_medicamentos (receta_id, producto_id, {', '.join(CAMPOS_MED)})
                    VALUES (%s, %s, {', '.join(['%s'] * len(CAMPOS_MED))})""",
                [receta_id, to_int(m.get("producto_id"), 0) or None] + valores, cursor=cur)
    return receta_id


def crear_receta(paciente_id, medico_id, form, medicamentos):
    obtener_paciente(paciente_id)
    meds = [m for m in medicamentos if _txt(m.get("medicamento"))]
    if not meds:
        raise ClinicaError("Agrega al menos un medicamento.")
    with transaction() as cur:
        return _insertar_receta(cur, paciente_id, medico_id, None, form.get("diagnostico"),
                                form.get("indicaciones_generales"), parse_fecha(form.get("proxima_cita")), meds)


def obtener_receta(receta_id):
    r = fetch_one("""SELECT r.*, u.nombre AS medico_usuario FROM recetas r JOIN usuarios u ON u.id = r.medico_id
                     WHERE r.id = %s AND r.status = 1""", (receta_id,))
    if not r:
        raise ClinicaError("Receta no encontrada.")
    r["medicamentos"] = fetch_all("SELECT * FROM receta_medicamentos WHERE receta_id = %s ORDER BY id", (receta_id,))
    r["paciente"] = obtener_paciente(r["paciente_id"])
    r["alergias"] = fetch_all("SELECT alergeno FROM paciente_alergias WHERE paciente_id = %s AND status = 1",
                              (r["paciente_id"],))
    r["consulta"] = fetch_one("SELECT * FROM consultas_medicas WHERE id = %s", (r["consulta_id"],)) if r["consulta_id"] else None
    r["diagnosticos"] = fetch_all("SELECT descripcion, cie10, tipo FROM consulta_diagnosticos WHERE consulta_id = %s ORDER BY id",
                                  (r["consulta_id"],)) if r["consulta_id"] else []
    r["medico"] = perfil_medico(r["medico_id"], r["medico_usuario"])
    return r


def listar_recetas(q="", limite=300):
    sql = """SELECT r.id, r.folio, r.fecha, r.diagnostico, r.paciente_id, r.consulta_id, r.venta_id, r.surtida_at,
                    p.nombre, p.apellido_paterno, p.apellido_materno, p.expediente,
                    (SELECT GROUP_CONCAT(m.medicamento SEPARATOR ', ') FROM receta_medicamentos m WHERE m.receta_id = r.id) AS meds
             FROM recetas r JOIN pacientes p ON p.id = r.paciente_id WHERE r.status = 1"""
    params = []
    if q:
        sql += """ AND (CONCAT(p.nombre, ' ', p.apellido_paterno, ' ', IFNULL(p.apellido_materno, '')) LIKE %s
                   OR r.folio LIKE %s OR r.diagnostico LIKE %s)"""
        params += [f"%{q}%"] * 3
    sql += " ORDER BY r.fecha DESC LIMIT %s"
    params.append(int(limite))
    filas = fetch_all(sql, params)
    for r in filas:
        r["paciente"] = nombre_completo(r)
    return filas


# =================================================================== estudios
def solicitar_estudio(paciente_id, form):
    nombre = _txt(form.get("nombre"), 150)
    if not nombre:
        raise ClinicaError("Indica el nombre del estudio.")
    execute("""INSERT INTO estudios (paciente_id, tipo, nombre, fecha_solicitud, estado, laboratorio, status)
               VALUES (%s, %s, %s, %s, 'solicitado', %s, 1)""",
            (paciente_id, form.get("tipo") if form.get("tipo") in TIPOS_ESTUDIO else "laboratorio", nombre,
             parse_fecha(form.get("fecha_solicitud")) or date.today(), _txt(form.get("laboratorio"), 120)))


def registrar_resultado(estudio_id, form, archivo=None, archivo_nombre=None):
    e = fetch_one("SELECT * FROM estudios WHERE id = %s AND status = 1", (estudio_id,))
    if not e:
        raise ClinicaError("Estudio no encontrado.")
    estado = form.get("estado") if form.get("estado") in ESTADOS_ESTUDIO else "resultado"
    execute("""UPDATE estudios SET estado = %s, fecha_resultado = %s, laboratorio = %s, resultado = %s,
                   interpretacion = %s, archivo = COALESCE(%s, archivo), archivo_nombre = COALESCE(%s, archivo_nombre)
               WHERE id = %s""",
            (estado, parse_fecha(form.get("fecha_resultado")) or (date.today() if estado == "resultado" else None),
             _txt(form.get("laboratorio"), 120) or e["laboratorio"], _txt(form.get("resultado")),
             _txt(form.get("interpretacion")), archivo, archivo_nombre, estudio_id))
    return e["paciente_id"]


def obtener_estudio(estudio_id):
    return fetch_one("SELECT * FROM estudios WHERE id = %s AND status = 1", (estudio_id,))


def listar_estudios(estado="", q="", limite=300):
    sql = """SELECT e.*, p.nombre AS p_nombre, p.apellido_paterno, p.apellido_materno, p.expediente
             FROM estudios e JOIN pacientes p ON p.id = e.paciente_id WHERE e.status = 1"""
    params = []
    if estado == "pendientes":
        sql += " AND e.estado IN ('solicitado', 'en_proceso')"
    elif estado in ESTADOS_ESTUDIO:
        sql += " AND e.estado = %s"
        params.append(estado)
    if q:
        sql += """ AND (CONCAT(p.nombre, ' ', p.apellido_paterno) LIKE %s OR e.nombre LIKE %s)"""
        params += [f"%{q}%"] * 2
    sql += " ORDER BY e.fecha_solicitud DESC, e.id DESC LIMIT %s"
    params.append(int(limite))
    filas = fetch_all(sql, params)
    for e in filas:
        e["paciente"] = " ".join(x for x in (e["p_nombre"], e["apellido_paterno"], e["apellido_materno"]) if x)
    return filas


# =================================================================== citas
def crear_cita(paciente_id, medico_id, form):
    obtener_paciente(paciente_id)
    try:
        fh = datetime.strptime((form.get("fecha_hora") or "").replace("T", " ")[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        raise ClinicaError("Indica fecha y hora válidas.")
    execute("""INSERT INTO citas (paciente_id, medico_id, fecha_hora, duracion_min, motivo, estado, notas, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 1)""",
            (paciente_id, medico_id, fh, to_int(form.get("duracion_min"), 30, minimo=5), _txt(form.get("motivo"), 200),
             form.get("estado") if form.get("estado") in ESTADOS_CITA else "programada", _txt(form.get("notas"), 255)))


def cambiar_estado_cita(cita_id, estado):
    if estado not in ESTADOS_CITA:
        raise ClinicaError("Estado inválido.")
    execute("UPDATE citas SET estado = %s WHERE id = %s", (estado, cita_id))


def agenda(desde, dias=7):
    filas = fetch_all(
        """SELECT ci.*, p.nombre, p.apellido_paterno, p.apellido_materno, p.telefono, p.expediente, p.fecha_nacimiento
           FROM citas ci JOIN pacientes p ON p.id = ci.paciente_id
           WHERE ci.status = 1 AND p.status = 1 AND ci.fecha_hora >= %s AND ci.fecha_hora < %s
           ORDER BY ci.fecha_hora""",
        (desde, desde + timedelta(days=dias)))
    for c in filas:
        c["paciente"] = nombre_completo(c)
        c["edad"] = edad(c["fecha_nacimiento"])
    return filas


# =================================================================== perfil médico
def perfil_medico(usuario_id, nombre_usuario=""):
    p = fetch_one("SELECT * FROM perfil_medico WHERE usuario_id = %s", (usuario_id,))
    return p or {"usuario_id": usuario_id, "nombre_mostrar": nombre_usuario, "especialidad": "Medicina General"}


CAMPOS_PERFIL = {"nombre_mostrar": 150, "especialidad": 120, "cedula_profesional": 30, "cedula_especialidad": 30,
                 "institucion": 150, "telefono": 30, "whatsapp": 30, "email": 120, "direccion": 255, "horario": 150,
                 "leyenda_receta": 255}


def guardar_perfil(usuario_id, form):
    v = {k: _txt(form.get(k), largo) for k, largo in CAMPOS_PERFIL.items()}
    if not v["nombre_mostrar"]:
        raise ClinicaError("El nombre para la receta es obligatorio.")
    if fetch_one("SELECT usuario_id FROM perfil_medico WHERE usuario_id = %s", (usuario_id,)):
        execute(f"UPDATE perfil_medico SET {', '.join(f'{k} = %s' for k in v)} WHERE usuario_id = %s",
                list(v.values()) + [usuario_id])
    else:
        execute(f"INSERT INTO perfil_medico (usuario_id, {', '.join(v)}) VALUES (%s, {', '.join(['%s'] * len(v))})",
                [usuario_id] + list(v.values()))


def guardar_logo_perfil(usuario_id, nombre_usuario, lado, archivo):
    """lado: 'izq' (escudo / institución) o 'der' (emblema). archivo=None lo quita."""
    if lado not in ("izq", "der"):
        raise ClinicaError("Logo inválido.")
    if not fetch_one("SELECT usuario_id FROM perfil_medico WHERE usuario_id = %s", (usuario_id,)):
        execute("INSERT INTO perfil_medico (usuario_id, nombre_mostrar) VALUES (%s, %s)", (usuario_id, nombre_usuario or "Médico"))
    execute(f"UPDATE perfil_medico SET logo_{lado} = %s WHERE usuario_id = %s", (archivo, usuario_id))


# =================================================================== tablero
def tablero():
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)
    manana = hoy + timedelta(days=1)
    return {
        "pacientes": fetch_value("SELECT COUNT(*) AS n FROM pacientes WHERE status = 1"),
        "pacientes_nuevos_mes": fetch_value("SELECT COUNT(*) AS n FROM pacientes WHERE status = 1 AND created_at >= %s",
                                            (inicio_mes,)),
        "consultas_hoy": fetch_value("SELECT COUNT(*) AS n FROM consultas_medicas WHERE status = 1 AND fecha >= %s AND fecha < %s",
                                     (hoy, manana)),
        "consultas_mes": fetch_value("SELECT COUNT(*) AS n FROM consultas_medicas WHERE status = 1 AND fecha >= %s",
                                     (inicio_mes,)),
        "ingresos_mes": fetch_value("SELECT IFNULL(SUM(costo), 0) AS n FROM consultas_medicas WHERE status = 1 AND fecha >= %s",
                                    (inicio_mes,)),
        "cobrado_mes": fetch_value("""SELECT IFNULL(SUM(costo), 0) AS n FROM consultas_medicas
                                      WHERE status = 1 AND fecha >= %s AND venta_id IS NOT NULL""", (inicio_mes,)),
        "por_cobrar": fetch_value("""SELECT COUNT(*) AS n FROM consultas_medicas
                                     WHERE status = 1 AND costo > 0 AND venta_id IS NULL"""),
        "citas_hoy": agenda(hoy, 1),
        "estudios_pendientes": fetch_value(
            "SELECT COUNT(*) AS n FROM estudios WHERE status = 1 AND estado IN ('solicitado', 'en_proceso')"),
        "recetas_mes": fetch_value("SELECT COUNT(*) AS n FROM recetas WHERE status = 1 AND fecha >= %s", (inicio_mes,)),
        "ultimas_consultas": listar_consultas(limite=8),
        "top_padecimientos": fetch_all(
            """SELECT nombre, COUNT(*) AS pacientes FROM paciente_padecimientos
               WHERE status = 1 AND estado <> 'resuelto' GROUP BY nombre ORDER BY pacientes DESC, nombre LIMIT 6"""),
        "consultas_por_mes": fetch_all(
            """SELECT YEAR(fecha) AS anio, MONTH(fecha) AS mes, COUNT(*) AS n FROM consultas_medicas
               WHERE status = 1 AND fecha >= %s GROUP BY YEAR(fecha), MONTH(fecha) ORDER BY anio, mes""",
            ((inicio_mes - timedelta(days=150)).replace(day=1),)),
        "proximas_citas": agenda(manana, 7),
    }


# =================================================================== reportes clínicos
GRUPOS_EDAD = [(0, 11, "0–11"), (12, 17, "12–17"), (18, 29, "18–29"), (30, 44, "30–44"),
               (45, 59, "45–59"), (60, 74, "60–74"), (75, 200, "75+")]


def _grupo_edad(anios):
    if anios is None:
        return "Sin dato"
    for a, b, etiqueta in GRUPOS_EDAD:
        if a <= anios <= b:
            return etiqueta
    return "Sin dato"


def pendientes_cobro(limite=100):
    filas = fetch_all(
        """SELECT c.id, c.folio, c.fecha, c.costo, c.motivo, c.paciente_id, p.nombre, p.apellido_paterno,
                  p.apellido_materno, p.expediente
           FROM consultas_medicas c JOIN pacientes p ON p.id = c.paciente_id
           WHERE c.status = 1 AND c.costo > 0 AND c.venta_id IS NULL
           ORDER BY c.fecha DESC LIMIT %s""", (int(limite),))
    for f in filas:
        f["paciente"] = nombre_completo(f)
    return filas


def reporte(desde, hasta):
    """Indicadores del consultorio entre dos fechas (inclusive)."""
    ini = datetime.combine(desde, datetime.min.time())
    fin = datetime.combine(hasta + timedelta(days=1), datetime.min.time())
    rango = (ini, fin)
    k = fetch_one(
        """SELECT COUNT(*) AS consultas, COUNT(DISTINCT paciente_id) AS pacientes,
                  IFNULL(SUM(CASE WHEN tipo = 'primera_vez' THEN 1 ELSE 0 END), 0) AS primera_vez,
                  IFNULL(SUM(costo), 0) AS honorarios,
                  IFNULL(SUM(CASE WHEN venta_id IS NOT NULL THEN costo ELSE 0 END), 0) AS cobrado,
                  IFNULL(SUM(CASE WHEN venta_id IS NULL THEN costo ELSE 0 END), 0) AS pendiente
           FROM consultas_medicas WHERE status = 1 AND fecha >= %s AND fecha < %s""", rango) or {}
    kpis = {key: (to_float(v) if key in ("honorarios", "cobrado", "pendiente") else int(v or 0)) for key, v in k.items()}
    kpis["ticket_promedio"] = round(kpis["honorarios"] / kpis["consultas"], 2) if kpis.get("consultas") else 0
    kpis["pacientes_nuevos"] = fetch_value("SELECT COUNT(*) AS n FROM pacientes WHERE status = 1 AND created_at >= %s AND created_at < %s", rango)
    r = fetch_one("""SELECT COUNT(*) AS recetas, IFNULL(SUM(CASE WHEN venta_id IS NOT NULL THEN 1 ELSE 0 END), 0) AS surtidas
                     FROM recetas WHERE status = 1 AND fecha >= %s AND fecha < %s""", rango) or {}
    kpis["recetas"], kpis["recetas_surtidas"] = int(r.get("recetas") or 0), int(r.get("surtidas") or 0)
    kpis["surtido_pct"] = round(100 * kpis["recetas_surtidas"] / kpis["recetas"], 1) if kpis["recetas"] else 0
    e = fetch_one("""SELECT COUNT(*) AS estudios, IFNULL(SUM(CASE WHEN estado = 'resultado' THEN 1 ELSE 0 END), 0) AS con_resultado
                     FROM estudios WHERE status = 1 AND fecha_solicitud >= %s AND fecha_solicitud <= %s""", (desde, hasta)) or {}
    kpis["estudios"], kpis["estudios_resultado"] = int(e.get("estudios") or 0), int(e.get("con_resultado") or 0)
    ci = fetch_one("""SELECT COUNT(*) AS citas, IFNULL(SUM(CASE WHEN estado = 'atendida' THEN 1 ELSE 0 END), 0) AS atendidas,
                             IFNULL(SUM(CASE WHEN estado = 'no_asistio' THEN 1 ELSE 0 END), 0) AS no_asistio
                      FROM citas WHERE status = 1 AND fecha_hora >= %s AND fecha_hora < %s""", rango) or {}
    kpis.update({x: int(ci.get(x) or 0) for x in ("citas", "atendidas", "no_asistio")})

    por_tipo = fetch_all("""SELECT tipo, COUNT(*) AS n, IFNULL(SUM(costo), 0) AS monto FROM consultas_medicas
                            WHERE status = 1 AND fecha >= %s AND fecha < %s GROUP BY tipo ORDER BY n DESC""", rango)
    for t in por_tipo:
        t["texto"] = TIPOS_CONSULTA.get(t["tipo"], t["tipo"])
        t["monto"] = to_float(t["monto"])

    inicio_12 = (hasta.replace(day=1) - timedelta(days=335)).replace(day=1)
    por_mes = fetch_all("""SELECT YEAR(fecha) AS anio, MONTH(fecha) AS mes, COUNT(*) AS consultas,
                                  IFNULL(SUM(CASE WHEN venta_id IS NOT NULL THEN costo ELSE 0 END), 0) AS cobrado
                           FROM consultas_medicas WHERE status = 1 AND fecha >= %s AND fecha < %s
                           GROUP BY YEAR(fecha), MONTH(fecha) ORDER BY anio, mes""", (inicio_12, fin))
    for m in por_mes:
        m["cobrado"] = to_float(m["cobrado"])

    top_dx = fetch_all("""SELECT d.descripcion, MAX(d.cie10) AS cie10, COUNT(*) AS n, COUNT(DISTINCT c.paciente_id) AS pacientes
                          FROM consulta_diagnosticos d JOIN consultas_medicas c ON c.id = d.consulta_id
                          WHERE c.status = 1 AND c.fecha >= %s AND c.fecha < %s
                          GROUP BY d.descripcion ORDER BY n DESC, d.descripcion LIMIT 10""", rango)
    top_meds = fetch_all("""SELECT m.medicamento, COUNT(*) AS n,
                                   IFNULL(SUM(CASE WHEN r.venta_id IS NOT NULL THEN 1 ELSE 0 END), 0) AS surtidas,
                                   MAX(CASE WHEN m.producto_id IS NOT NULL THEN 1 ELSE 0 END) AS en_inventario
                            FROM receta_medicamentos m JOIN recetas r ON r.id = m.receta_id
                            WHERE r.status = 1 AND r.fecha >= %s AND r.fecha < %s
                            GROUP BY m.medicamento ORDER BY n DESC, m.medicamento LIMIT 10""", rango)
    frecuentes = fetch_all("""SELECT p.id, p.nombre, p.apellido_paterno, p.apellido_materno, p.expediente,
                                     COUNT(*) AS visitas, MAX(c.fecha) AS ultima, IFNULL(SUM(c.costo), 0) AS monto
                              FROM consultas_medicas c JOIN pacientes p ON p.id = c.paciente_id
                              WHERE c.status = 1 AND c.fecha >= %s AND c.fecha < %s
                              GROUP BY p.id, p.nombre, p.apellido_paterno, p.apellido_materno, p.expediente
                              ORDER BY visitas DESC, ultima DESC LIMIT 10""", rango)
    for f in frecuentes:
        f["paciente"] = nombre_completo(f)
        f["monto"] = to_float(f["monto"])

    atendidos = fetch_all("""SELECT DISTINCT p.id, p.sexo, p.fecha_nacimiento FROM pacientes p
                             JOIN consultas_medicas c ON c.paciente_id = p.id
                             WHERE c.status = 1 AND c.fecha >= %s AND c.fecha < %s""", rango)
    por_sexo, por_edad = {}, {g[2]: 0 for g in GRUPOS_EDAD}
    for a in atendidos:
        s = SEXOS.get(a["sexo"] or "", "Sin dato")
        por_sexo[s] = por_sexo.get(s, 0) + 1
        g = _grupo_edad(edad_anios(a["fecha_nacimiento"]))
        por_edad[g] = por_edad.get(g, 0) + 1

    return {"desde": desde, "hasta": hasta, "kpis": kpis, "por_tipo": por_tipo, "por_mes": por_mes,
            "top_dx": top_dx, "top_meds": top_meds, "frecuentes": frecuentes,
            "por_sexo": por_sexo, "por_edad": {k: v for k, v in por_edad.items() if v or k != "Sin dato"},
            "pendientes": pendientes_cobro(50)}


def consultas_csv_filas(desde, hasta):
    ini = datetime.combine(desde, datetime.min.time())
    fin = datetime.combine(hasta + timedelta(days=1), datetime.min.time())
    filas = fetch_all("""SELECT c.folio, c.fecha, c.tipo, p.expediente, p.nombre, p.apellido_paterno, p.apellido_materno,
                                c.motivo, c.diagnostico, c.costo, c.venta_id, v.folio AS venta_folio, u.nombre AS medico
                         FROM consultas_medicas c JOIN pacientes p ON p.id = c.paciente_id
                         JOIN usuarios u ON u.id = c.medico_id LEFT JOIN ventas v ON v.id = c.venta_id
                         WHERE c.status = 1 AND c.fecha >= %s AND c.fecha < %s ORDER BY c.fecha""", (ini, fin))
    yield ["Folio", "Fecha", "Tipo", "Expediente", "Paciente", "Motivo", "Diagnóstico", "Honorarios",
           "Estado de cobro", "Venta", "Médico"]
    for f in filas:
        yield [f["folio"], f["fecha"].strftime("%Y-%m-%d %H:%M") if hasattr(f["fecha"], "strftime") else f["fecha"],
               TIPOS_CONSULTA.get(f["tipo"], f["tipo"]), f["expediente"], nombre_completo(f), f["motivo"],
               f["diagnostico"] or "", f"{to_float(f['costo']):.2f}",
               "Cobrada" if f["venta_id"] else ("Pendiente" if to_float(f["costo"]) > 0 else "Sin costo"),
               f["venta_folio"] or "", f["medico"]]
