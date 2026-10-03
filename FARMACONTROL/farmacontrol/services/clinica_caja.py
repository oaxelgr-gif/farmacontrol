"""
Enlace entre el módulo clínico y la caja.

- Honorarios: una consulta médica con costo > 0 se cobra en el punto de venta como
  línea tipo «honorario» (el precio sale de la consulta, nunca del navegador).
- Recetas: los medicamentos ligados al inventario se cargan al carrito para surtirlos;
  al cobrar, la receta queda marcada como surtida con el folio de la venta.
- El paciente se enlaza (o se crea) como cliente del POS para que la venta quede a su nombre.
"""
import re

from ..db import execute, fetch_all, fetch_one, to_float
from . import caducidad

PREFIJO_FOLIO_RECETA = "R"


class CuentaError(Exception):
    pass


def _nombre(p):
    return " ".join(x for x in (p.get("nombre"), p.get("apellido_paterno"), p.get("apellido_materno")) if x)


def cantidad_sugerida(texto):
    """'2 cajas' → 2 · 'una caja' → 1 · '' → 1 (máximo 99)."""
    m = re.search(r"\d+", texto or "")
    n = int(m.group()) if m else 1
    return max(1, min(n, 99))


def _paciente(paciente_id, cursor=None):
    p = fetch_one("""SELECT id, expediente, nombre, apellido_paterno, apellido_materno, telefono, email,
                            direccion, cliente_id
                     FROM pacientes WHERE id = %s AND status = 1""", (paciente_id,), cursor=cursor)
    if not p:
        raise CuentaError("Paciente no encontrado.")
    return p


def receta_por_folio(folio):
    folio = (folio or "").strip().upper()
    if not folio:
        return None
    if folio.isdigit():
        folio = f"{PREFIJO_FOLIO_RECETA}{int(folio):06d}"
    r = fetch_one("SELECT id FROM recetas WHERE folio = %s AND status = 1", (folio,))
    return r["id"] if r else None


def cuenta(consulta_id=None, receta_id=None):
    """
    Arma la «cuenta» de un paciente para precargar el punto de venta.
    Devuelve los artículos cobrables y los medicamentos que no se pueden surtir.
    """
    consulta = receta = None
    if receta_id:
        receta = fetch_one("""SELECT id, folio, paciente_id, consulta_id, venta_id, surtida_at, fecha
                              FROM recetas WHERE id = %s AND status = 1""", (receta_id,))
        if not receta:
            raise CuentaError("Receta no encontrada.")
        if not consulta_id and receta["consulta_id"]:
            consulta_id = receta["consulta_id"]
    if consulta_id:
        consulta = fetch_one("""SELECT id, folio, paciente_id, costo, venta_id, fecha, motivo
                                FROM consultas_medicas WHERE id = %s AND status = 1""", (consulta_id,))
        if not consulta:
            raise CuentaError("Consulta no encontrada.")
        if not receta:
            receta = fetch_one("""SELECT id, folio, paciente_id, consulta_id, venta_id, surtida_at, fecha
                                  FROM recetas WHERE consulta_id = %s AND status = 1 ORDER BY id LIMIT 1""",
                               (consulta_id,))
    if not consulta and not receta:
        raise CuentaError("Indica una consulta o una receta.")

    paciente = _paciente((consulta or receta)["paciente_id"])
    items, faltantes, avisos = [], [], []

    if consulta:
        costo = to_float(consulta["costo"])
        if consulta["venta_id"]:
            avisos.append(f"La consulta {consulta['folio']} ya fue cobrada.")
        elif costo > 0:
            items.append({"id": consulta["id"], "tipo": "honorario", "nombre": f"Consulta médica {consulta['folio']}",
                          "precio": costo, "cant": 1, "stock": None, "antibiotico": False})
        else:
            avisos.append(f"La consulta {consulta['folio']} no tiene honorarios registrados.")

    if receta:
        if receta["venta_id"]:
            avisos.append(f"La receta {receta['folio']} ya fue surtida.")
        else:
            estado = caducidad.estado_sql("p.fecha_caducidad")
            meds = fetch_all(f"""SELECT rm.medicamento, rm.cantidad, rm.producto_id, p.nombre, p.precio_publico,
                                        p.stock_actual, p.antibiotico, {estado} AS estado_caducidad
                                 FROM receta_medicamentos rm
                                 LEFT JOIN productos p ON p.id = rm.producto_id AND p.status = 1
                                 WHERE rm.receta_id = %s ORDER BY rm.id""", (receta["id"],))
            for m in meds:
                if not m["producto_id"] or m["nombre"] is None:
                    faltantes.append({"medicamento": m["medicamento"], "motivo": "No está ligado al inventario"})
                    continue
                stock = int(m["stock_actual"] or 0)
                if stock <= 0:
                    faltantes.append({"medicamento": m["nombre"], "motivo": "Sin existencia"})
                    continue
                if not caducidad.es_vendible(m["estado_caducidad"]):
                    faltantes.append({"medicamento": m["nombre"], "motivo": f"Lote {m['estado_caducidad'].lower()}"})
                    continue
                pedida = cantidad_sugerida(m["cantidad"])
                if pedida > stock:
                    avisos.append(f"{m['nombre']}: se recetaron {pedida}, solo hay {stock}.")
                items.append({"id": m["producto_id"], "tipo": "producto", "nombre": m["nombre"],
                              "precio": to_float(m["precio_publico"]), "cant": min(pedida, stock), "stock": stock,
                              "antibiotico": bool(m["antibiotico"])})

    alergias = [a["alergeno"] for a in fetch_all(
        "SELECT alergeno FROM paciente_alergias WHERE paciente_id = %s AND status = 1", (paciente["id"],))]
    return {
        "paciente": {"id": paciente["id"], "nombre": _nombre(paciente), "expediente": paciente["expediente"],
                     "cliente_id": paciente["cliente_id"]},
        "consulta": {"id": consulta["id"], "folio": consulta["folio"], "pagada": bool(consulta["venta_id"])} if consulta else None,
        "receta": {"id": receta["id"], "folio": receta["folio"], "surtida": bool(receta["venta_id"])} if receta else None,
        "items": items, "faltantes": faltantes, "avisos": avisos, "alergias": alergias,
    }


# ------------------------------------------------------------- dentro de la venta
def linea_honorario(cur, consulta_id):
    """Línea de venta para los honorarios de una consulta (bloquea la fila)."""
    c = fetch_one("""SELECT id, folio, paciente_id, costo, venta_id FROM consultas_medicas
                     WHERE id = %s AND status = 1 FOR UPDATE""", (consulta_id,), cursor=cur)
    if not c:
        raise CuentaError(f"Consulta ID {consulta_id} no encontrada.")
    if c["venta_id"]:
        raise CuentaError(f"La consulta {c['folio']} ya fue cobrada.")
    precio = to_float(c["costo"])
    if precio <= 0:
        raise CuentaError(f"La consulta {c['folio']} no tiene honorarios.")
    return {"tipo": "honorario", "producto_id": None, "consulta_id": c["id"], "paciente_id": c["paciente_id"],
            "nombre": f"Consulta médica {c['folio']}", "cantidad": 1, "stock": None,
            "precio": precio, "costo": 0.0}


def cliente_para_paciente(cur, paciente_id):
    """Devuelve el cliente del POS ligado al paciente; lo crea si no existe."""
    p = _paciente(paciente_id, cursor=cur)
    if p["cliente_id"] and fetch_one("SELECT id FROM clientes WHERE id = %s AND status = 1",
                                     (p["cliente_id"],), cursor=cur):
        return p["cliente_id"]
    cliente_id = execute("""INSERT INTO clientes (nombre, rfc_nit, direccion, telefono, email, status)
                            VALUES (%s, NULL, %s, %s, %s, 1)""",
                         (_nombre(p)[:100], p["direccion"], p["telefono"], p["email"]), cursor=cur)
    execute("UPDATE pacientes SET cliente_id = %s WHERE id = %s", (cliente_id, paciente_id), cursor=cur)
    return cliente_id


def validar_receta(cur, receta_id):
    r = fetch_one("SELECT id, folio, paciente_id, venta_id FROM recetas WHERE id = %s AND status = 1 FOR UPDATE",
                  (receta_id,), cursor=cur)
    if not r:
        raise CuentaError("Receta no encontrada.")
    if r["venta_id"]:
        raise CuentaError(f"La receta {r['folio']} ya fue surtida.")
    return r


def registrar_cobro(cur, venta_id, lineas, receta_id=None):
    """Marca consultas cobradas y receta surtida con el id de la venta."""
    for ln in lineas:
        if ln["tipo"] == "honorario":
            execute("UPDATE consultas_medicas SET venta_id = %s WHERE id = %s", (venta_id, ln["consulta_id"]), cursor=cur)
    if receta_id:
        execute("UPDATE recetas SET venta_id = %s, surtida_at = NOW() WHERE id = %s", (venta_id, receta_id), cursor=cur)
