"""Indicadores para tableros y apps."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import solo_admin
from ..schemas import ResumenDia
from ..services import catalogos as svc

router = APIRouter(prefix="/reportes", tags=["Reportes"])


@router.get("/resumen-dia", response_model=ResumenDia, summary="KPIs del día (admin)")
def resumen(fecha: Optional[date] = None, conn=Depends(get_db), _a=Depends(solo_admin)):
    return svc.resumen_dia(conn, fecha)
