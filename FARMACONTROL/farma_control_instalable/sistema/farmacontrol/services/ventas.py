"""
Procesamiento de ventas del punto de venta.

Mejoras respecto a la versión anterior:
- Toda la venta corre en UNA transacción (antes autocommit impedía el rollback).
- Precios y costos se toman de la BD, no del navegador.
- El total y el cambio se recalculan en el servidor.
- Servicios y consultas se guardan con producto_id = NULL (antes se guardaba el
  id del servicio como si fuera un producto, mezclando reportes).
- Bloqueo de filas (FOR UPDATE) para evitar vender stock inexistente.
"""

from ..db import execute, fetch_all, fetch_one, to_float, transaction
from ..utils.helpers import to_int, to_num
from . import antibioticos, caducidad, clinica_caja, folios
from .cortes import corte_abierto

TIPOS_VALIDOS = {"producto", "servicio", "consulta", "honorario"}
TABLA_POR_TIPO = {"servicio": "servicios", "consulta": "consultas"}
CLIENTE_GENERAL_ID = 1


class VentaError(Exception):
    pass


def _tipo_item(item):
    tipo = (item.get("tipo") or "").strip().lower()
    if tipo in TIPOS_VALIDOS:
        return tipo
    # Compatibilidad con el carrito anterior (esProducto true/false)
    return "producto" if item.get("esProducto", True) else "servicio"


def generar_folio(usuario_id):
    """Folio de vista previa (el definitivo se asigna al guardar la venta)."""
    return folios.siguiente(lambda sql, prm: fetch_one(sql, prm), usuario_id)


def _cargar_linea(cur, item):
    tipo = _tipo_item(item)
    cantidad = to_int(item.get("cant") or item.get("cantidad"), 0)
    item_id = to_int(item.get("id"), 0)
    if cantidad <= 0 or item_id <= 0:
        raise VentaError("Hay un artículo con cantidad o identificador inválido.")

    if tipo == "producto":
        prod = fetch_one(
            f"""SELECT id, nombre, stock_actual, precio_publico, precio_costo, antibiotico,
                       sustancia_activa, tipo_antibiotico, lote, fecha_caducidad,
                       {caducidad.estado_sql()} AS estado_caducidad
                FROM productos WHERE id = %s AND status = 1 FOR UPDATE""",
            (item_id,),
            cursor=cur,
        )
        if not prod:
            raise VentaError(f"Producto ID {item_id} no encontrado.")
        if not caducidad.es_vendible(prod["estado_caducidad"]):
            raise VentaError(
                f"'{prod['nombre']}' está {prod['estado_caducidad'].lower()}. No se puede vender.")
        return {
            "tipo": tipo,
            "producto_id": prod["id"],
            "nombre": prod["nombre"],
            "cantidad": cantidad,
            "stock": int(prod["stock_actual"] or 0),
            "precio": to_float(prod["precio_publico"]),
            "costo": to_float(prod["precio_costo"]),
            "antibiotico": bool(prod["antibiotico"]),
            "compuesto": prod["sustancia_activa"] or prod["nombre"],
            "tipo_antibiotico": prod["tipo_antibiotico"],
            "lote": prod["lote"],
            "fecha_caducidad": prod["fecha_caducidad"],
        }

    if tipo == "honorario":  # consulta médica del módulo clínico
        try:
            return clinica_caja.linea_honorario(cur, item_id)
        except clinica_caja.CuentaError as exc:
            raise VentaError(str(exc)) from exc

    tabla = TABLA_POR_TIPO[tipo]
    row = fetch_one(
        f"SELECT id, nombre, precio FROM {tabla} WHERE id = %s AND status = 1",
        (item_id,),
        cursor=cur,
    )
    if not row:
        raise VentaError(f"{tipo.capitalize()} ID {item_id} no encontrado.")
    return {
        "tipo": tipo,
        "producto_id": None,
        "nombre": row["nombre"],
        "cantidad": cantidad,
        "stock": None,
        "precio": to_float(row["precio"]),
        "costo": 0.0,
    }


def procesar_venta(payload, usuario_id):
    carrito = payload.get("carrito") or []
    if not carrito:
        raise VentaError("El carrito está vacío.")

    metodo_id = to_int(payload.get("metodo_pago_id"), 0)
    metodo = fetch_one("SELECT id, nombre FROM metodos_pago WHERE id = %s AND status = 1", (metodo_id,))
    if not metodo:
        raise VentaError("Selecciona un método de pago válido.")
    es_efectivo = "efectivo" in (metodo["nombre"] or "").lower()

    cliente_id = to_int(payload.get("cliente_id"), 0) or CLIENTE_GENERAL_ID
    receta_id = to_int(payload.get("receta_id"), 0) or None
    paciente_id = to_int(payload.get("paciente_id"), 0) or None

    with transaction() as cur:
        if cliente_id != CLIENTE_GENERAL_ID and not fetch_one(
                "SELECT id FROM clientes WHERE id = %s AND status = 1", (cliente_id,), cursor=cur):
            cliente_id = CLIENTE_GENERAL_ID

        lineas = [_cargar_linea(cur, item) for item in carrito]
        registro_ab = None
        if any(ln.get("antibiotico") for ln in lineas):
            try:
                registro_ab = antibioticos.limpiar_registro(payload.get("antibiotico"))
            except antibioticos.RegistroError as exc:
                raise VentaError(str(exc)) from exc
        cobradas = [ln["consulta_id"] for ln in lineas if ln["tipo"] == "honorario"]
        if len(cobradas) != len(set(cobradas)):
            raise VentaError("La misma consulta aparece dos veces en el carrito.")

        # Cuenta de paciente (módulo clínico): receta a surtir y cliente a su nombre
        try:
            if receta_id:
                paciente_id = paciente_id or clinica_caja.validar_receta(cur, receta_id)["paciente_id"]
            paciente_id = paciente_id or next((ln["paciente_id"] for ln in lineas if ln["tipo"] == "honorario"), None)
            if paciente_id and cliente_id == CLIENTE_GENERAL_ID:
                cliente_id = clinica_caja.cliente_para_paciente(cur, paciente_id)
        except clinica_caja.CuentaError as exc:
            raise VentaError(str(exc)) from exc

        # Validar stock agregando cantidades por producto
        requeridos = {}
        for ln in lineas:
            if ln["tipo"] == "producto":
                requeridos.setdefault(ln["producto_id"], [ln, 0])
                requeridos[ln["producto_id"]][1] += ln["cantidad"]
        for ln, cant in requeridos.values():
            if cant > ln["stock"]:
                raise VentaError(
                    f"Stock insuficiente para: {ln['nombre']}. Disponible: {ln['stock']}")

        total = round(sum(ln["precio"] * ln["cantidad"] for ln in lineas), 2)
        if es_efectivo:
            pago = round(to_num(payload.get("pago"), total), 2)
            if pago + 0.005 < total:
                raise VentaError(f"Pago insuficiente. Faltan ${total - pago:,.2f}")
            cambio = round(pago - total, 2)
        else:
            pago, cambio = total, 0.0

        # Abrir corte automáticamente si el usuario no tiene uno
        if not corte_abierto(usuario_id, cursor=cur):
            execute(
                """INSERT INTO cortes_caja (usuario_id, fecha_apertura, monto_inicial, cerrado, status)
                   VALUES (%s, NOW(), 0, 0, 1)""",
                (usuario_id,),
                cursor=cur,
            )

        venta_id = folio = None
        for intento in range(folios.INTENTOS):
            folio = folios.siguiente(lambda sql, prm: fetch_one(sql, prm, cursor=cur), usuario_id, intento)
            try:
                venta_id = execute(
                    """INSERT INTO ventas (folio, usuario_id, cliente_id, metodo_pago_id, total,
                                           pago_recibido, cambio_entregado, fecha, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), 1)""",
                    (folio, usuario_id, cliente_id, metodo["id"], total, pago, cambio),
                    cursor=cur,
                )
                break
            except Exception as exc:
                if not folios.es_duplicado(exc):
                    raise
        if venta_id is None:
            raise VentaError("No se pudo generar el folio de la venta. Intenta de nuevo.")

        for ln in lineas:
            execute(
                """INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio_unitario,
                                               precio_costo_momento, subtotal, status)
                   VALUES (%s, %s, %s, %s, %s, %s, 1)""",
                (venta_id, ln["producto_id"], ln["cantidad"], ln["precio"], ln["costo"],
                 round(ln["precio"] * ln["cantidad"], 2)),
                cursor=cur,
            )
            if ln["tipo"] == "producto":
                execute(
                    "UPDATE productos SET stock_actual = stock_actual - %s WHERE id = %s",
                    (ln["cantidad"], ln["producto_id"]),
                    cursor=cur,
                )
        clinica_caja.registrar_cobro(cur, venta_id, lineas, receta_id)
        if registro_ab:
            antibioticos.guardar(cur, venta_id, usuario_id, registro_ab, lineas)

    return {
        "venta_id": venta_id,
        "folio": folio,
        "total": total,
        "pago": pago,
        "cambio": cambio,
        "metodo": metodo["nombre"],
        "receta_id": receta_id,
        "consultas": [ln["consulta_id"] for ln in lineas if ln["tipo"] == "honorario"],
    }


def obtener_venta(venta_id):
    return fetch_one(
        """SELECT v.*, u.nombre AS vendedor, u.nombre AS farmaceutico,
                  c.nombre AS cliente, c.rfc_nit, c.telefono, c.direccion,
                  mp.nombre AS metodo_pago, mp.nombre AS metodo
           FROM ventas v
           JOIN usuarios u ON v.usuario_id = u.id
           LEFT JOIN clientes c ON v.cliente_id = c.id
           JOIN metodos_pago mp ON v.metodo_pago_id = mp.id
           WHERE v.id = %s""",
        (venta_id,),
    )


def detalle_venta(venta_id):
    return fetch_all(
        """SELECT dv.*, IFNULL(p.nombre, 'Servicio / Consulta') AS producto_nombre,
                  p.codigo_barras, p.lote, IFNULL(p.antibiotico, 0) AS antibiotico
           FROM detalle_ventas dv
           LEFT JOIN productos p ON dv.producto_id = p.id
           WHERE dv.venta_id = %s
           ORDER BY dv.id""",
        (venta_id,),
    )
