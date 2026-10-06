"""Dependencias: conexión y usuario autenticado.

Dos formas de autenticarse:
1. Clientes externos: `Authorization: Bearer <jwt>` (obtenido en /v1/auth/token).
2. Servicio web (Flask): `X-Internal-Token` + `X-User-Id`. El token interno solo
   lo conocen los contenedores (variable API_INTERNAL_TOKEN).
"""
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .db import fetch_one, get_db
from .security import leer_token, token_interno_valido

ROL_ADMIN = 1
ROLES = {1: "Administrador", 2: "Farmacéutico"}

oauth2 = OAuth2PasswordBearer(tokenUrl="/v1/auth/token", auto_error=False)


class UsuarioActual:
    def __init__(self, row):
        self.id = int(row["id"])
        self.nombre = row["nombre"]
        self.username = row.get("username")
        self.rol = int(row["rol"])

    @property
    def es_admin(self):
        return self.rol == ROL_ADMIN

    def dict(self):
        return {"id": self.id, "nombre": self.nombre, "username": self.username,
                "rol": self.rol, "rol_nombre": ROLES.get(self.rol, "Usuario")}


def _cargar(conn, usuario_id):
    row = fetch_one(conn, "SELECT id, nombre, username, rol FROM usuarios WHERE id = %s AND status = 1",
                    (usuario_id,))
    return UsuarioActual(row) if row else None


def usuario_actual(
    conn=Depends(get_db),
    token: Optional[str] = Depends(oauth2),
    x_internal_token: Optional[str] = Header(default=None),
    x_user_id: Optional[int] = Header(default=None),
) -> UsuarioActual:
    no_auth = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada",
                            headers={"WWW-Authenticate": "Bearer"})
    if x_internal_token:
        if not token_interno_valido(x_internal_token) or not x_user_id:
            raise no_auth
        usuario = _cargar(conn, x_user_id)
    elif token:
        payload = leer_token(token)
        if not payload:
            raise no_auth
        usuario = _cargar(conn, int(payload["sub"]))
    else:
        raise no_auth
    if not usuario:
        raise no_auth
    return usuario


def solo_admin(usuario: UsuarioActual = Depends(usuario_actual)) -> UsuarioActual:
    if not usuario.es_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acceso restringido a administradores")
    return usuario
