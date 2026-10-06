"""Corte de caja del usuario en turno: abrir, consultar y cerrar."""
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user

from ...db import fetch_all
from ...services import cortes as svc
from ...utils.helpers import to_num

bp = Blueprint("caja", __name__)


@bp.route("/corte_caja")
@login_required
def corte_caja():
    corte = svc.corte_abierto(current_user.id)
    if not corte:
        historial = fetch_all(
            """SELECT id, fecha_apertura, fecha_cierre, monto_inicial, monto_final
               FROM cortes_caja
               WHERE usuario_id = %s AND cerrado = 1 AND status = 1
               ORDER BY fecha_cierre DESC LIMIT 10""",
            (current_user.id,),
        )
        return render_template("caja/corte.html", datos=None, corte_abierto=False,
                               historial=historial,
                               fondo_sugerido=current_app.config["FONDO_SUGERIDO"])

    t = svc.totales_periodo(current_user.id, corte["fecha_apertura"])
    fondo = float(corte["monto_inicial"] or 0)
    datos = {
        "corte_id": corte["id"],
        "vendedor": current_user.nombre,
        "fecha_apertura": corte["fecha_apertura"].strftime("%d/%m/%Y %H:%M"),
        "fondo_inicial": fondo,
        "ventas_efectivo": t["efectivo"],
        "ventas_tarjeta": t["tarjeta"],
        "ventas_transferencia": t["transferencia"],
        "ventas_otros": t["otros"],
        "total_ventas": t["numero_ventas"],
        "importe_ventas": t["total_ventas"],
        "efectivo_en_caja": fondo + t["efectivo"],
        "monto_final_estimado": fondo + t["total_ventas"],
    }
    return render_template(
        "caja/corte.html",
        datos=datos,
        corte_abierto=True,
        detalle_ventas=svc.ventas_periodo(current_user.id, corte["fecha_apertura"]),
    )


@bp.route("/abrir_caja", methods=["POST"])
@login_required
def abrir_caja():
    try:
        svc.abrir_corte(current_user.id, round(to_num(request.form.get("monto_inicial")), 2))
        flash("Corte de caja abierto correctamente. ¡Buen turno!", "success")
    except svc.CorteError as exc:
        flash(str(exc), "warning")
    except Exception as exc:
        flash(f"Error al abrir caja: {exc}", "danger")
    return redirect(url_for("caja.corte_caja"))


@bp.route("/cerrar_caja", methods=["POST"])
@login_required
def cerrar_caja():
    try:
        corte_id = svc.cerrar_corte(current_user.id)
    except svc.CorteError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("caja.corte_caja"))
    except Exception as exc:
        flash(f"Error al cerrar caja: {exc}", "danger")
        return redirect(url_for("caja.corte_caja"))

    datos = svc.datos_ticket(corte_id, con_productos=True)
    # Al cerrar caja se cierra la sesión automáticamente (comportamiento original)
    logout_user()
    session.clear()
    return render_template("tickets/corte.html", datos=datos, cierre_turno=True)
