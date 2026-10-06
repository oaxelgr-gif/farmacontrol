"""Catálogos para el punto de venta y combos."""
from typing import List, Union

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import UsuarioActual, usuario_actual
from ..schemas import Catalogo, ItemCatalogo, Producto
from ..services import catalogos as svc
from ..services import productos as svc_productos

router = APIRouter(tags=["Catálogos"])


@router.get("/catalogo/{tipo}", response_model=List[Union[Producto, ItemCatalogo]],
            summary="Artículos vendibles: productos, procedimientos o consultas")
def catalogo(tipo: str, incluir_bloqueados: bool = False, conn=Depends(get_db),
             usuario: UsuarioActual = Depends(usuario_actual)):
    if tipo == "productos":
        return svc_productos.vendibles(conn, incluir_bloqueados and usuario.es_admin)
    return svc.servicios(conn, tipo)


@router.get("/metodos-pago", response_model=List[Catalogo], summary="Métodos de pago activos")
def metodos(conn=Depends(get_db), _u=Depends(usuario_actual)):
    return svc.metodos_pago(conn)


@router.get("/secciones", response_model=List[Catalogo], summary="Secciones / anaqueles")
def secciones(conn=Depends(get_db), _u=Depends(usuario_actual)):
    return svc.secciones(conn)
