"""Clientes."""
from typing import List

from fastapi import APIRouter, Depends, status

from ..db import get_db
from ..deps import usuario_actual
from ..schemas import Cliente, ClienteCrear
from ..services import catalogos as svc

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.get("", response_model=List[Cliente], summary="Buscar clientes")
def listar(q: str = "", conn=Depends(get_db), _u=Depends(usuario_actual)):
    return svc.clientes(conn, q.strip())


@router.post("", response_model=Cliente, status_code=status.HTTP_201_CREATED, summary="Registrar cliente")
def crear(datos: ClienteCrear, conn=Depends(get_db), _u=Depends(usuario_actual)):
    return svc.crear_cliente(conn, datos.model_dump())
