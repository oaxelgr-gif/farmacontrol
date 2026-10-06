"""Productos: búsqueda para el punto de venta y administración de inventario."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response, status

from ..db import get_db
from ..deps import UsuarioActual, solo_admin, usuario_actual
from ..schemas import (BusquedaProductos, EntradaStock, EstadoCaducidad, Producto, ProductoActualizar,
                       ProductoCrear)
from ..services import productos as svc

router = APIRouter(prefix="/productos", tags=["Productos"])


@router.get("", response_model=List[Producto], summary="Listar inventario")
def listar(search: str = "", alerta: str = Query("", pattern="^(|bajo|caducidad|antibiotico)$"),
           seccion_id: Optional[int] = None, limite: int = Query(500, ge=1, le=2000),
           conn=Depends(get_db), usuario: UsuarioActual = Depends(usuario_actual)):
    return svc.listar(conn, search.strip(), alerta, seccion_id, limite, con_costo=usuario.es_admin)


@router.get("/buscar", response_model=BusquedaProductos, summary="Buscar por código de barras o nombre",
            responses={404: {"description": "No encontrado"}, 409: {"description": "Sin stock o caducado"}})
def buscar(q: str = Query(..., min_length=1), incluir_bloqueados: bool = False,
           conn=Depends(get_db), usuario: UsuarioActual = Depends(usuario_actual)):
    return svc.buscar(conn, q, incluir_bloqueados and usuario.es_admin)


@router.get("/{producto_id}", response_model=Producto, summary="Detalle de un producto")
def obtener(producto_id: int, conn=Depends(get_db), usuario: UsuarioActual = Depends(usuario_actual)):
    return svc.obtener(conn, producto_id, con_costo=usuario.es_admin)


@router.get("/{producto_id}/caducidad", response_model=EstadoCaducidad, summary="Validar caducidad")
def caducidad(producto_id: int, conn=Depends(get_db), _u=Depends(usuario_actual)):
    return svc.caducidad(conn, producto_id)


@router.post("", response_model=Producto, status_code=status.HTTP_201_CREATED, summary="Crear producto (admin)")
def crear(datos: ProductoCrear, conn=Depends(get_db), _a=Depends(solo_admin)):
    return svc.crear(conn, datos.model_dump())


@router.patch("/{producto_id}", response_model=Producto, summary="Actualizar producto (admin)")
def actualizar(producto_id: int, cambios: ProductoActualizar, conn=Depends(get_db), _a=Depends(solo_admin)):
    return svc.actualizar(conn, producto_id, cambios.model_dump(exclude_unset=True))


@router.post("/{producto_id}/stock", response_model=Producto, summary="Registrar entrada de mercancía (admin)")
def entrada(producto_id: int, datos: EntradaStock, conn=Depends(get_db), _a=Depends(solo_admin)):
    return svc.sumar_stock(conn, producto_id, datos.cantidad)


@router.delete("/{producto_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Dar de baja (admin)")
def eliminar(producto_id: int, conn=Depends(get_db), _a=Depends(solo_admin)):
    svc.eliminar(conn, producto_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
