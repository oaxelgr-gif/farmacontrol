"""Corte de caja del usuario autenticado."""
from typing import List

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import UsuarioActual, usuario_actual
from ..schemas import AbrirCaja, CorteCerrado, CorteHistorial, EstadoCaja
from ..services import caja as svc

router = APIRouter(prefix="/caja", tags=["Caja"])


@router.get("", response_model=EstadoCaja, summary="Estado del corte actual")
def estado(conn=Depends(get_db), usuario: UsuarioActual = Depends(usuario_actual)):
    return svc.estado(conn, usuario.id)


@router.post("/abrir", response_model=EstadoCaja, summary="Abrir corte con fondo inicial")
def abrir(datos: AbrirCaja, conn=Depends(get_db), usuario: UsuarioActual = Depends(usuario_actual)):
    return svc.abrir(conn, usuario.id, datos.monto_inicial)


@router.post("/cerrar", response_model=CorteCerrado, summary="Cerrar el corte abierto")
def cerrar(conn=Depends(get_db), usuario: UsuarioActual = Depends(usuario_actual)):
    return svc.cerrar(conn, usuario.id)


@router.get("/historial", response_model=List[CorteHistorial], summary="Mis cortes cerrados")
def historial(conn=Depends(get_db), usuario: UsuarioActual = Depends(usuario_actual)):
    return svc.historial(conn, usuario.id)
