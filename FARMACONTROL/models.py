from flask_login import UserMixin

class Usuario(UserMixin):
    def __init__(self, data):
        self.id = data['id']
        self.nombre = data['nombre']
        self.username = data['username']
        self.password = data['password']
        self.rol = data['rol'] # 1: Admin, 0: Farmacéutico
        self.status = data['status']

    def es_admin(self):
        return self.rol == 1

class Producto:
    def __init__(self, data):
        self.id = data['id']
        self.nombre = data['nombre']
        self.codigo_barras = data['codigo_barras']
        self.stock_actual = data['stock_actual']
        self.precio_publico = data['precio_publico']
        self.seccion_id = data['seccion_id']