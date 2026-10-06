"""Autenticación con JWT para clientes externos."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ..config import settings
from ..db import execute, fetch_one, get_db
from ..deps import UsuarioActual, usuario_actual
from ..schemas import Token, Usuario
from ..security import crear_token, es_hash, hash_password, verificar_password

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/token", response_model=Token, summary="Iniciar sesión (usuario y contraseña)")
def login(form: OAuth2PasswordRequestForm = Depends(), conn=Depends(get_db)):
    row = fetch_one(conn, "SELECT id, password, rol FROM usuarios WHERE username = %s AND status = 1",
                    (form.username.strip(),))
    if not row or not verificar_password(row["password"], form.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales incorrectas o cuenta inactiva")
    if not es_hash(row["password"]):  # migra contraseñas antiguas en texto plano
        execute(conn, "UPDATE usuarios SET password = %s WHERE id = %s", (hash_password(form.password), row["id"]))
    return Token(access_token=crear_token(row["id"], row["rol"]),
                 expires_in_minutes=settings.JWT_EXPIRE_MINUTES)


@router.get("/me", response_model=Usuario, summary="Usuario autenticado")
def me(usuario: UsuarioActual = Depends(usuario_actual)):
    return usuario.dict()
