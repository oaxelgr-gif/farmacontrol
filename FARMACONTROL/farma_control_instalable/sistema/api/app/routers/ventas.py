"""Ventas del punto de venta."""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status

from ..db import get_db
from ..deps import UsuarioActual, usuario_actual
from ..schemas import VentaCrear, VentaDetalle, VentaRegistrada, VentaResumen
from ..services import ventas as svc

router = APIRouter(prefix="/ventas", tags=["Ventas"])


@router.post("", response_model=VentaRegistrada, status_code=status.HTTP_201_CREATED,
             summary="Cobrar una venta",
             description="Precios, total y cambio se calculan en el servidor. Valida stock y caducidad "
                         "y registra todo en una sola transacción.")
def crear(venta: VentaCrear, conn=Depends(get_db), usuario: UsuarioActual = Depends(usuario_actual)):
    return svc.procesar(conn, [i.model_dump() for i in venta.carrito], venta.metodo_pago_id,
                        usuario.id, venta.pago, venta.cliente_id, venta.receta_id, venta.paciente_id,
                        venta.antibiotico)


@router.get("", response_model=List[VentaResumen], summary="Historial de ventas")
def listar(desde: Optional[date] = None, hasta: Optional[date] = None, usuario_id: Optional[int] = None,
           folio: Optional[str] = None, limite: int = Query(200, ge=1, le=1000),
           conn=Depends(get_db), usuario: UsuarioActual = Depends(usuario_actual)):
    # Un farmacéutico solo ve sus propias ventas
    filtro_usuario = usuario_id if usuario.es_admin else usuario.id
    return svc.listar(conn, desde, hasta, filtro_usuario, folio, limite)


@router.get("/{venta_id}", response_model=VentaDetalle, summary="Detalle de una venta")
def obtener(venta_id: int, conn=Depends(get_db), usuario: UsuarioActual = Depends(usuario_actual)):
    return svc.obtener(conn, venta_id, None if usuario.es_admin else usuario.id)
