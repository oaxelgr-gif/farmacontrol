"""Modelos ligeros (no ORM) usados por Flask-Login y las vistas."""
from flask_login import UserMixin

ROL_ADMIN = 1
ROL_FARMACEUTICO = 2

ROLES = {
    ROL_ADMIN: "Administrador",
    ROL_FARMACEUTICO: "Farmacéutico",
}


class Usuario(UserMixin):
    def __init__(self, data):
        self.id = data["id"]
        self.nombre = data["nombre"]
        self.username = data.get("username")
        self.rol = int(data["rol"])

    @property
    def es_admin(self):
        return self.rol == ROL_ADMIN

    @property
    def rol_nombre(self):
        return ROLES.get(self.rol, "Usuario")

    @property
    def iniciales(self):
        partes = [p for p in (self.nombre or "").split() if p]
        if not partes:
            return "U"
        if len(partes) == 1:
            return partes[0][0].upper()
        return (partes[0][0] + partes[1][0]).upper()
