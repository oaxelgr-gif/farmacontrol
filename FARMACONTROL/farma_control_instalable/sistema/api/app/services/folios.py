"""
Folios seriados de venta.

Formato:  AMMUUUNNNNZ  (11 dígitos, sin guiones)
          │ │ │  │   └─ último dígito del año      (2026 → 6)
          │ │ │  └───── operación del usuario en el mes (0001, 0002…)
          │ │ └──────── id del usuario (3 dígitos)
          │ └────────── mes (01–12)
          └──────────── penúltimo dígito del año  (2026 → 2)

Ejemplos (octubre 2026):
    usuario 2, 1ª venta del mes  →  21000200016
    usuario 2, 2ª venta del mes  →  21000200026
    usuario 3, 1ª venta del mes  →  21000300016
    enero 2027, usuario 2, 1ª    →  20100200017

El consecutivo se reinicia cada mes por usuario (así el folio nunca se repite).
Este archivo es idéntico en farmacontrol/services/ y api/app/services/.
"""
from datetime import date, datetime

INTENTOS = 5


def codificar(fecha, usuario_id, operacion):
    anio = f"{fecha.year:04d}"
    return f"{anio[2]}{fecha.month:02d}{int(usuario_id):03d}{int(operacion):04d}{anio[3]}"


def decodificar(folio):
    """Devuelve {'anio', 'mes', 'usuario_id', 'operacion'} o None si no tiene este formato."""
    d = str(folio or "")
    if len(d) < 11 or not d.isdigit():
        return None
    dec, mes, usuario, op, uni = d[0], d[1:3], d[3:6], d[6:-1], d[-1]
    if not 1 <= int(mes) <= 12:
        return None
    return {"anio": 2000 + int(dec + uni), "mes": int(mes), "usuario_id": int(usuario), "operacion": int(op)}


def _rango_mes(fecha):
    inicio = date(fecha.year, fecha.month, 1)
    fin = date(fecha.year + (fecha.month == 12), fecha.month % 12 + 1, 1)
    return inicio, fin


def siguiente(consultar, usuario_id, intento=0, fecha=None):
    """
    Siguiente folio del usuario en el mes actual.
    `consultar(sql, params)` devuelve una fila (dict); se ejecuta dentro de la
    transacción de la venta. `intento` suma 1 por cada choque al insertar.
    """
    fecha = fecha or datetime.now()
    inicio, fin = _rango_mes(fecha)
    fila = consultar(
        """SELECT COUNT(*) AS n FROM ventas
           WHERE usuario_id = %s AND fecha >= %s AND fecha < %s FOR UPDATE""",
        (usuario_id, inicio, fin),
    )
    hechas = int((fila or {}).get("n") or 0)
    return codificar(fecha, usuario_id, hechas + 1 + intento)


def es_duplicado(exc):
    texto = str(exc)
    return "Duplicate" in texto or "UNIQUE" in texto or "1062" in texto
