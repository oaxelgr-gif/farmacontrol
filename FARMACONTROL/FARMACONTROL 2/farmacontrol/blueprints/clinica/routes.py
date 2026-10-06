"""Módulo clínico (solo administrador / médico): expediente, consultas, recetas, estudios y agenda."""
import csv
import io
import json
import os
import uuid
from datetime import date, datetime, timedelta

from flask import (Blueprint, Response, abort, current_app, flash, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ...db import fetch_all
from ...models import ROL_ADMIN
from ...services import clinica as svc
from ...utils.helpers import parse_fecha, to_int

bp = Blueprint("clinica", __name__, url_prefix="/clinica")

EXT_PERMITIDAS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


@bp.before_request
@login_required
def solo_admin():
    if current_user.rol != ROL_ADMIN:
        flash("El módulo clínico es exclusivo del médico/administrador.", "danger")
        return redirect(url_for("dashboard.inicio_farmacia"))
    return None


@bp.context_processor
def catalogos():
    return {
        "SEXOS": svc.SEXOS, "TIPOS_SANGRE": svc.TIPOS_SANGRE, "ESTADOS_CIVILES": svc.ESTADOS_CIVILES,
        "TIPOS_CONSULTA": svc.TIPOS_CONSULTA, "TIPOS_ALERGIA": svc.TIPOS_ALERGIA, "SEVERIDADES": svc.SEVERIDADES,
        "ESTADOS_PADECIMIENTO": svc.ESTADOS_PADECIMIENTO, "TIPOS_ESTUDIO": svc.TIPOS_ESTUDIO,
        "ESTADOS_ESTUDIO": svc.ESTADOS_ESTUDIO, "ESTADOS_CITA": svc.ESTADOS_CITA, "VIAS": svc.VIAS,
        "clasificar_imc": svc.clasificar_imc, "clasificar_ta": svc.clasificar_ta, "edad_de": svc.edad,
        "timedelta": timedelta,
    }


def _json_lista(nombre):
    try:
        datos = json.loads(request.form.get(nombre) or "[]")
        return datos if isinstance(datos, list) else []
    except ValueError:
        return []


def _volver(paciente_id, tab=None):
    return redirect(url_for("clinica.expediente", paciente_id=paciente_id) + (f"#{tab}" if tab else ""))


# ====================================================================== tablero
@bp.route("/")
def tablero():
    return render_template("clinica/tablero.html", t=svc.tablero(), hoy=date.today())


# ====================================================================== pacientes
@bp.route("/pacientes")
def pacientes():
    q = (request.args.get("q") or "").strip()
    padecimiento = (request.args.get("padecimiento") or "").strip()
    sexo = request.args.get("sexo", "")
    orden = request.args.get("orden", "recientes")
    lista = svc.listar_pacientes(q, padecimiento, sexo, orden)
    padecimientos = fetch_all("""SELECT nombre, COUNT(*) AS n FROM paciente_padecimientos WHERE status = 1
                                 GROUP BY nombre ORDER BY n DESC, nombre LIMIT 30""")
    return render_template("clinica/pacientes.html", pacientes=lista, q=q, padecimiento=padecimiento,
                           sexo=sexo, orden=orden, padecimientos=padecimientos)


@bp.route("/pacientes/nuevo", methods=["GET", "POST"])
@bp.route("/pacientes/<int:paciente_id>/editar", methods=["GET", "POST"])
def paciente_form(paciente_id=None):
    paciente = svc.obtener_paciente(paciente_id) if paciente_id else {}
    if request.method == "POST":
        datos, errores = svc.leer_paciente(request.form)
        if not errores:
            nuevo_id = svc.guardar_paciente(datos, current_user.id, paciente_id)
            flash("Paciente actualizado." if paciente_id else "Paciente registrado. Ya puedes iniciar su consulta.", "success")
            if not paciente_id and request.form.get("despues") == "consulta":
                return redirect(url_for("clinica.consulta_nueva", paciente_id=nuevo_id))
            return redirect(url_for("clinica.expediente", paciente_id=nuevo_id))
        for e in errores:
            flash(e, "danger")
        paciente = dict(paciente, **datos)
    return render_template("clinica/paciente_form.html", p=paciente, editando=bool(paciente_id))


@bp.route("/pacientes/<int:paciente_id>")
def expediente(paciente_id):
    try:
        exp = svc.expediente(paciente_id)
    except svc.ClinicaError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("clinica.pacientes"))
    return render_template("clinica/expediente.html", **exp, hoy=date.today())


@bp.route("/pacientes/<int:paciente_id>/imprimir")
def expediente_imprimir(paciente_id):
    try:
        exp = svc.expediente(paciente_id)
    except svc.ClinicaError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("clinica.pacientes"))
    return render_template("clinica/expediente_imprimir.html", exp=exp, p=exp["paciente"],
                           m=svc.perfil_medico(current_user.id, current_user.nombre), ahora=datetime.now())


@bp.route("/pacientes/<int:paciente_id>/eliminar", methods=["POST"])
def paciente_baja(paciente_id):
    svc.baja_paciente(paciente_id)
    flash("Paciente dado de baja. Su historial se conserva en la base de datos.", "success")
    return redirect(url_for("clinica.pacientes"))


@bp.route("/pacientes/<int:paciente_id>/antecedentes", methods=["POST"])
def antecedentes(paciente_id):
    svc.guardar_antecedentes(paciente_id, request.form)
    flash("Antecedentes actualizados.", "success")
    return _volver(paciente_id, "antecedentes")


def _accion(paciente_id, fn, ok, tab):
    try:
        fn()
        flash(ok, "success")
    except svc.ClinicaError as exc:
        flash(str(exc), "danger")
    return _volver(paciente_id, tab)


@bp.route("/pacientes/<int:paciente_id>/alergias", methods=["POST"])
def alergia_nueva(paciente_id):
    return _accion(paciente_id, lambda: svc.agregar_alergia(paciente_id, request.form), "Alergia registrada.", "resumen")


@bp.route("/pacientes/<int:paciente_id>/padecimientos", methods=["POST"])
def padecimiento_nuevo(paciente_id):
    return _accion(paciente_id, lambda: svc.agregar_padecimiento(paciente_id, request.form),
                   "Padecimiento registrado.", "padecimientos")


@bp.route("/pacientes/<int:paciente_id>/padecimientos/<int:item_id>/estado", methods=["POST"])
def padecimiento_estado(paciente_id, item_id):
    return _accion(paciente_id, lambda: svc.actualizar_padecimiento(paciente_id, item_id, request.form.get("estado")),
                   "Estado del padecimiento actualizado.", "padecimientos")


@bp.route("/pacientes/<int:paciente_id>/medicamentos", methods=["POST"])
def medicamento_nuevo(paciente_id):
    return _accion(paciente_id, lambda: svc.agregar_medicamento(paciente_id, request.form),
                   "Medicamento agregado.", "medicamentos")


@bp.route("/pacientes/<int:paciente_id>/medicamentos/<int:item_id>/suspender", methods=["POST"])
def medicamento_suspender(paciente_id, item_id):
    return _accion(paciente_id, lambda: svc.suspender_medicamento(paciente_id, item_id),
                   "Medicamento suspendido.", "medicamentos")


@bp.route("/pacientes/<int:paciente_id>/<tipo>/<int:item_id>/baja", methods=["POST"])
def registro_baja(paciente_id, tipo, item_id):
    tabs = {"alergia": "resumen", "padecimiento": "padecimientos", "medicamento": "medicamentos",
            "estudio": "estudios", "cita": "citas"}
    return _accion(paciente_id, lambda: svc.dar_de_baja(tipo, paciente_id, item_id), "Registro eliminado.",
                   tabs.get(tipo))


@bp.route("/pacientes/<int:paciente_id>/estudios", methods=["POST"])
def estudio_nuevo(paciente_id):
    return _accion(paciente_id, lambda: svc.solicitar_estudio(paciente_id, request.form),
                   "Estudio solicitado.", "estudios")


@bp.route("/pacientes/<int:paciente_id>/citas", methods=["POST"])
def cita_nueva(paciente_id):
    destino = request.form.get("volver")
    try:
        svc.crear_cita(paciente_id, current_user.id, request.form)
        flash("Cita agendada.", "success")
    except svc.ClinicaError as exc:
        flash(str(exc), "danger")
    if destino == "agenda":
        return redirect(url_for("clinica.agenda"))
    return _volver(paciente_id, "citas")


# ====================================================================== consultas
@bp.route("/consultas")
def consultas():
    q = (request.args.get("q") or "").strip()
    desde, hasta = parse_fecha(request.args.get("desde")), parse_fecha(request.args.get("hasta"))
    tipo = request.args.get("tipo", "")
    return render_template("clinica/consultas.html", consultas=svc.listar_consultas(q, desde, hasta, tipo),
                           q=q, desde=desde.isoformat() if desde else "", hasta=hasta.isoformat() if hasta else "",
                           tipo=tipo)


@bp.route("/consultas/nueva", methods=["GET", "POST"])
def consulta_nueva():
    paciente_id = to_int(request.values.get("paciente_id"), 0)
    if request.method == "POST":
        if not paciente_id:
            flash("Selecciona un paciente.", "danger")
        else:
            try:
                consulta_id, receta_id = svc.crear_consulta(
                    paciente_id, current_user.id, request.form, _json_lista("diagnosticos_json"),
                    _json_lista("medicamentos_json"), _json_lista("estudios_json"),
                    request.form.get("indicaciones_receta"))
                flash("Consulta guardada en el expediente." + (" Receta generada." if receta_id else ""), "success")
                session["borrar_borrador"] = f"fc-consulta-{paciente_id}"
                destino = url_for("clinica.consulta_detalle", consulta_id=consulta_id)
                if request.form.get("cobrar") == "1":
                    return redirect(url_for("ventas.punto_venta", consulta=consulta_id))
                if receta_id and request.form.get("imprimir") == "1":
                    destino += f"?imprimir={receta_id}"
                return redirect(destino)
            except svc.ClinicaError as exc:
                flash(str(exc), "danger")
    paciente = exp = None
    if paciente_id:
        try:
            exp = svc.expediente(paciente_id)
            paciente = exp["paciente"]
        except svc.ClinicaError:
            paciente_id = 0
    consultas_catalogo = fetch_all("SELECT id, nombre, precio FROM consultas WHERE status = 1 ORDER BY precio")
    return render_template("clinica/consulta_form.html", paciente=paciente, exp=exp,
                           consultas_catalogo=consultas_catalogo, hoy=date.today())


@bp.route("/consultas/<int:consulta_id>")
def consulta_detalle(consulta_id):
    try:
        c = svc.obtener_consulta(consulta_id)
    except svc.ClinicaError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("clinica.consultas"))
    paciente = svc.obtener_paciente(c["paciente_id"])
    return render_template("clinica/consulta_detalle.html", c=c, paciente=paciente,
                           imprimir=to_int(request.args.get("imprimir"), 0))


@bp.route("/consultas/<int:consulta_id>/nota", methods=["POST"])
def consulta_nota(consulta_id):
    try:
        svc.agregar_nota(consulta_id, current_user.id, request.form.get("nota"))
        flash("Nota de evolución agregada.", "success")
    except svc.ClinicaError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("clinica.consulta_detalle", consulta_id=consulta_id) + "#notas")


# ====================================================================== recetas
@bp.route("/recetas")
def recetas():
    q = (request.args.get("q") or "").strip()
    return render_template("clinica/recetas.html", recetas=svc.listar_recetas(q), q=q)


@bp.route("/recetas/nueva", methods=["GET", "POST"])
def receta_nueva():
    paciente_id = to_int(request.values.get("paciente_id"), 0)
    if request.method == "POST":
        try:
            receta_id = svc.crear_receta(paciente_id, current_user.id, request.form, _json_lista("medicamentos_json"))
            flash("Receta generada.", "success")
            return redirect(url_for("clinica.receta_imprimir", receta_id=receta_id))
        except svc.ClinicaError as exc:
            flash(str(exc), "danger")
    exp = svc.expediente(paciente_id) if paciente_id else None
    return render_template("clinica/receta_form.html", exp=exp, paciente=exp["paciente"] if exp else None)


@bp.route("/recetas/<int:receta_id>/imprimir")
def receta_imprimir(receta_id):
    try:
        r = svc.obtener_receta(receta_id)
    except svc.ClinicaError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("clinica.recetas"))
    return render_template("clinica/receta_imprimir.html", r=r, p=r["paciente"], m=r["medico"], c=r["consulta"],
                           copias=1 if request.args.get("copias") == "1" else 2)


# ====================================================================== estudios
@bp.route("/estudios")
def estudios():
    estado = request.args.get("estado", "pendientes")
    q = (request.args.get("q") or "").strip()
    return render_template("clinica/estudios.html", estudios=svc.listar_estudios(estado, q), estado=estado, q=q)


@bp.route("/estudios/<int:estudio_id>/resultado", methods=["POST"])
def estudio_resultado(estudio_id):
    archivo = request.files.get("archivo")
    ruta = nombre = None
    if archivo and archivo.filename:
        ext = os.path.splitext(archivo.filename)[1].lower()
        if ext not in EXT_PERMITIDAS:
            flash("Formato no permitido. Sube PDF o imagen (PNG, JPG, WEBP).", "danger")
            return redirect(request.referrer or url_for("clinica.estudios"))
        carpeta = os.path.join(current_app.config["UPLOAD_FOLDER"], "estudios")
        os.makedirs(carpeta, exist_ok=True)
        ruta = f"{date.today():%Y%m}_{uuid.uuid4().hex}{ext}"
        archivo.save(os.path.join(carpeta, ruta))
        nombre = secure_filename(archivo.filename) or f"resultado{ext}"
    try:
        paciente_id = svc.registrar_resultado(estudio_id, request.form, ruta, nombre)
        flash("Resultado guardado en el expediente.", "success")
    except svc.ClinicaError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("clinica.estudios"))
    if request.form.get("volver") == "estudios":
        return redirect(url_for("clinica.estudios"))
    return _volver(paciente_id, "estudios")


@bp.route("/estudios/<int:estudio_id>/archivo")
def estudio_archivo(estudio_id):
    e = svc.obtener_estudio(estudio_id)
    if not e or not e["archivo"]:
        abort(404)
    return send_from_directory(os.path.join(current_app.config["UPLOAD_FOLDER"], "estudios"), e["archivo"],
                               download_name=e["archivo_nombre"] or e["archivo"],
                               as_attachment=request.args.get("descargar") == "1")


# ====================================================================== agenda
@bp.route("/agenda")
def agenda():
    desde = parse_fecha(request.args.get("desde")) or date.today()
    dias = to_int(request.args.get("dias"), 7, minimo=1)
    citas = svc.agenda(desde, min(dias, 62))
    por_dia = {}
    for c in citas:
        por_dia.setdefault(c["fecha_hora"].date(), []).append(c)
    return render_template("clinica/agenda.html", por_dia=por_dia, desde=desde, dias=dias,
                           hoy=date.today(), timedelta=timedelta)


@bp.route("/citas/<int:cita_id>/estado", methods=["POST"])
def cita_estado(cita_id):
    try:
        svc.cambiar_estado_cita(cita_id, request.form.get("estado"))
        flash("Cita actualizada.", "success")
    except svc.ClinicaError as exc:
        flash(str(exc), "danger")
    return redirect(request.referrer or url_for("clinica.agenda"))


# ====================================================================== perfil médico
@bp.route("/perfil", methods=["GET", "POST"])
def perfil():
    if request.method == "POST":
        try:
            svc.guardar_perfil(current_user.id, request.form)
            for lado in ("izq", "der"):
                archivo = request.files.get(f"logo_{lado}")
                if archivo and archivo.filename:
                    ext = os.path.splitext(archivo.filename)[1].lower()
                    if ext not in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
                        raise svc.ClinicaError("El logo debe ser imagen PNG, JPG, WEBP o SVG.")
                    carpeta = os.path.join(current_app.config["UPLOAD_FOLDER"], "perfil")
                    os.makedirs(carpeta, exist_ok=True)
                    nombre = f"u{current_user.id}_{lado}_{uuid.uuid4().hex[:8]}{ext}"
                    archivo.save(os.path.join(carpeta, nombre))
                    svc.guardar_logo_perfil(current_user.id, current_user.nombre, lado, nombre)
                elif request.form.get(f"quitar_{lado}"):
                    svc.guardar_logo_perfil(current_user.id, current_user.nombre, lado, None)
            flash("Perfil médico actualizado. Así aparecerá en tus recetas.", "success")
            return redirect(url_for("clinica.perfil"))
        except svc.ClinicaError as exc:
            flash(str(exc), "danger")
    return render_template("clinica/perfil.html", m=svc.perfil_medico(current_user.id, current_user.nombre))


@bp.route("/perfil/logo/<int:usuario_id>/<lado>")
def perfil_logo(usuario_id, lado):
    m = svc.perfil_medico(usuario_id)
    archivo = m.get(f"logo_{lado}") if lado in ("izq", "der") else None
    if not archivo:
        abort(404)
    return send_from_directory(os.path.join(current_app.config["UPLOAD_FOLDER"], "perfil"), archivo, max_age=3600)


# ====================================================================== JSON auxiliares
@bp.route("/api/diagnosticos")
def api_diagnosticos():
    return jsonify(svc.diagnosticos_frecuentes())


@bp.route("/api/pacientes")
def api_pacientes():
    q = (request.args.get("q") or "").strip()
    return jsonify(svc.buscar_pacientes(q) if len(q) >= 2 else [])


@bp.route("/api/medicamentos")
def api_medicamentos():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify([])
    filas = fetch_all("""SELECT id, nombre, stock_actual, antibiotico FROM productos
                         WHERE status = 1 AND nombre LIKE %s ORDER BY nombre LIMIT 12""", (f"%{q}%",))
    return jsonify([{"id": f["id"], "nombre": f["nombre"], "stock": int(f["stock_actual"] or 0),
                     "antibiotico": bool(f["antibiotico"])} for f in filas])


@bp.app_template_filter("dt_local")
def dt_local(valor):
    """datetime -> valor para <input type=datetime-local>."""
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%dT%H:%M")
    return ""


# ====================================================================== reportes
def _rango():
    hoy = date.today()
    desde = parse_fecha(request.args.get("desde")) or hoy.replace(day=1)
    hasta = parse_fecha(request.args.get("hasta")) or hoy
    if desde > hasta:
        desde, hasta = hasta, desde
    return desde, hasta


@bp.route("/reportes")
def reportes():
    desde, hasta = _rango()
    return render_template("clinica/reportes.html", r=svc.reporte(desde, hasta), hoy=date.today())


@bp.route("/reportes/consultas.csv")
def reportes_csv():
    desde, hasta = _rango()
    out = io.StringIO()
    out.write("\ufeff")  # BOM: Excel abre bien los acentos
    w = csv.writer(out)
    for fila in svc.consultas_csv_filas(desde, hasta):
        w.writerow(fila)
    return Response(out.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=consultas_{desde}_{hasta}.csv"})
