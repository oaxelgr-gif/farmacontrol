"""Utilidades generales: fechas, números y filtros de Jinja."""
from datetime import date, datetime, timedelta
from decimal import Decimal

FORMATO_FECHA = "%Y-%m-%d"


def hoy():
    return datetime.now().date()


def inicio_de_mes():
    return hoy().replace(day=1)


def parse_fecha(valor, defecto=None):
    """Convierte 'YYYY-MM-DD' en date. Devuelve `defecto` si no es válida."""
    if isinstance(valor, date):
        return valor
    try:
        return datetime.strptime(str(valor).strip(), FORMATO_FECHA).date()
    except (TypeError, ValueError):
        return defecto


def rango_fechas(args, clave_inicio="inicio", clave_fin="fin", por_defecto="mes"):
    """
    Lee un rango de fechas de `request.args` validando el formato.
    Devuelve (inicio_str, fin_str) en formato YYYY-MM-DD.
    Si inicio > fin se intercambian.
    """
    fin_def = hoy()
    inicio_def = inicio_de_mes() if por_defecto == "mes" else None
    inicio = parse_fecha(args.get(clave_inicio), inicio_def)
    fin = parse_fecha(args.get(clave_fin), fin_def)
    if inicio and fin and inicio > fin:
        inicio, fin = fin, inicio
    return (
        inicio.strftime(FORMATO_FECHA) if inicio else "",
        fin.strftime(FORMATO_FECHA) if fin else "",
    )


def rango_rapido(tipo):
    """Rangos predefinidos: hoy, semana, mes. Devuelve (inicio, fin) o (None, None)."""
    h = hoy()
    if tipo == "hoy":
        return h.strftime(FORMATO_FECHA), h.strftime(FORMATO_FECHA)
    if tipo == "semana":
        return (h - timedelta(days=7)).strftime(FORMATO_FECHA), h.strftime(FORMATO_FECHA)
    if tipo == "mes":
        return (h - timedelta(days=30)).strftime(FORMATO_FECHA), h.strftime(FORMATO_FECHA)
    return None, None


def to_int(valor, defecto=0, minimo=None):
    try:
        n = int(float(valor))
    except (TypeError, ValueError):
        n = defecto
    if minimo is not None and n < minimo:
        n = minimo
    return n


def to_num(valor, defecto=0.0):
    if valor is None or valor == "":
        return defecto
    if isinstance(valor, Decimal):
        return float(valor)
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


# ---------------------------------------------------------------------------
# Filtros de plantilla
# ---------------------------------------------------------------------------
def filtro_money(valor, simbolo=True):
    n = to_num(valor)
    texto = f"{n:,.2f}"
    return f"${texto}" if simbolo else texto


def filtro_numero(valor, decimales=0):
    n = to_num(valor)
    return f"{n:,.{decimales}f}"


def filtro_fecha(valor, formato="%d/%m/%Y"):
    if not valor:
        return "—"
    if isinstance(valor, (datetime, date)):
        return valor.strftime(formato)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", FORMATO_FECHA):
        try:
            return datetime.strptime(str(valor), fmt).strftime(formato)
        except ValueError:
            continue
    return str(valor)


def filtro_fecha_hora(valor):
    return filtro_fecha(valor, "%d/%m/%Y %H:%M")


def filtro_hora(valor):
    return filtro_fecha(valor, "%H:%M")


def filtro_porcentaje(valor, decimales=1):
    return f"{to_num(valor):.{decimales}f}%"


def filtro_iniciales(nombre):
    partes = [p for p in str(nombre or "").split() if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][0].upper()
    return (partes[0][0] + partes[1][0]).upper()


def registrar_filtros(app):
    app.jinja_env.filters["money"] = filtro_money
    app.jinja_env.filters["numero"] = filtro_numero
    app.jinja_env.filters["fecha"] = filtro_fecha
    app.jinja_env.filters["fecha_hora"] = filtro_fecha_hora
    app.jinja_env.filters["hora"] = filtro_hora
    app.jinja_env.filters["pct"] = filtro_porcentaje
    app.jinja_env.filters["iniciales"] = filtro_iniciales
    app.jinja_env.filters["num"] = to_num
