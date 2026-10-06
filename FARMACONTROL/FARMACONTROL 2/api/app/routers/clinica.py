"""Expediente clínico (solo administrador / médico)."""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from ..db import get_db
from ..deps import UsuarioActual, solo_admin
from ..services import clinica as svc

router = APIRouter(prefix="/clinica", tags=["Clínica"])


class PacienteCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    apellido_paterno: str = Field(min_length=1, max_length=80)
    apellido_materno: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    sexo: Optional[str] = Field(default=None, pattern="^[FMO]$")
    curp: Optional[str] = Field(default=None, max_length=18)
    tipo_sangre: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    direccion: Optional[str] = None
    ciudad: Optional[str] = None
    codigo_postal: Optional[str] = None
    aseguradora: Optional[str] = None
    poliza: Optional[str] = None
    notas: Optional[str] = None


class CitaCrear(BaseModel):
    paciente_id: int
    fecha_hora: datetime
    motivo: Optional[str] = Field(default=None, max_length=200)


@router.get("/pacientes", summary="Buscar pacientes (nombre, expediente, teléfono o CURP)")
def pacientes(q: str = "", limite: int = Query(50, ge=1, le=500), conn=Depends(get_db), _u=Depends(solo_admin)):
    return svc.pacientes(conn, q.strip(), limite)


@router.post("/pacientes", status_code=status.HTTP_201_CREATED, summary="Registrar paciente")
def crear_paciente(datos: PacienteCrear, conn=Depends(get_db), _u=Depends(solo_admin)):
    return svc.crear_paciente(conn, datos.model_dump())


@router.get("/pacientes/{paciente_id}", summary="Ficha del paciente: alergias, padecimientos, tratamiento y visitas")
def paciente(paciente_id: int, conn=Depends(get_db), _u=Depends(solo_admin)):
    return svc.paciente(conn, paciente_id)


@router.get("/pacientes/{paciente_id}/consultas", summary="Historial de consultas del paciente")
def consultas_paciente(paciente_id: int, conn=Depends(get_db), _u=Depends(solo_admin)):
    return svc.consultas(conn, paciente_id)


@router.get("/pacientes/{paciente_id}/recetas", summary="Recetas del paciente")
def recetas_paciente(paciente_id: int, conn=Depends(get_db), _u=Depends(solo_admin)):
    return svc.recetas(conn, paciente_id)


@router.get("/pacientes/{paciente_id}/estudios", summary="Estudios del paciente")
def estudios_paciente(paciente_id: int, conn=Depends(get_db), _u=Depends(solo_admin)):
    return svc.estudios(conn, paciente_id)


@router.get("/consultas/{consulta_id}", summary="Nota médica completa")
def consulta(consulta_id: int, conn=Depends(get_db), _u=Depends(solo_admin)):
    return svc.consulta(conn, consulta_id)


@router.get("/recetas/{receta_id}", summary="Receta por id")
def receta(receta_id: int, conn=Depends(get_db), _u=Depends(solo_admin)):
    return svc.receta(conn, receta_id)


@router.get("/recetas/folio/{folio}", summary="Receta por folio (p. ej. R000001)")
def receta_folio(folio: str, conn=Depends(get_db), _u=Depends(solo_admin)):
    return svc.receta(conn, folio=folio)


@router.get("/citas", summary="Agenda de citas")
def citas(desde: Optional[date] = None, dias: int = Query(7, ge=1, le=90), conn=Depends(get_db),
          _u=Depends(solo_admin)):
    return svc.citas(conn, desde, dias)


@router.post("/citas", status_code=status.HTTP_201_CREATED, summary="Agendar cita")
def crear_cita(datos: CitaCrear, conn=Depends(get_db), usuario: UsuarioActual = Depends(solo_admin)):
    return svc.crear_cita(conn, datos.model_dump(), usuario.id)
