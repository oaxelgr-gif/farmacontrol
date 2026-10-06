"""Modelos de entrada/salida (validación automática y documentación Swagger)."""
from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Mensaje(BaseModel):
    detail: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class Usuario(BaseModel):
    id: int
    nombre: str
    username: Optional[str] = None
    rol: int
    rol_nombre: str


class Producto(BaseModel):
    id: int
    nombre: str
    codigo_barras: Optional[str] = None
    lote: Optional[str] = None
    precio: float
    precio_costo: Optional[float] = None
    stock: int
    stock_minimo: int = 0
    antibiotico: bool
    fecha_caducidad: Optional[str] = None
    seccion: Optional[str] = None
    estado_caducidad: str
    tipo: str = "producto"


class BusquedaProductos(BaseModel):
    tipo: Literal["exacto", "lista"]
    data: List[Producto]


class EstadoCaducidad(BaseModel):
    producto: str
    estado_caducidad: str
    dias_restantes: Optional[int] = None
    es_valido: bool


class ProductoCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    codigo_barras: Optional[str] = Field(default=None, max_length=50)
    lote: Optional[str] = Field(default=None, max_length=50)
    stock_inicial: int = Field(default=0, ge=0)
    stock_minimo: int = Field(default=5, ge=0)
    precio_costo: float = Field(ge=0)
    precio_publico: float = Field(ge=0)
    fecha_caducidad: Optional[date] = None
    antibiotico: bool = False
    seccion_id: Optional[int] = None


class ProductoActualizar(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=200)
    codigo_barras: Optional[str] = Field(default=None, max_length=50)
    lote: Optional[str] = Field(default=None, max_length=50)
    stock_minimo: Optional[int] = Field(default=None, ge=0)
    precio_costo: Optional[float] = Field(default=None, ge=0)
    precio_publico: Optional[float] = Field(default=None, ge=0)
    fecha_caducidad: Optional[date] = None
    antibiotico: Optional[bool] = None
    seccion_id: Optional[int] = None


class EntradaStock(BaseModel):
    cantidad: int = Field(gt=0)


class ItemCatalogo(BaseModel):
    id: int
    nombre: str
    precio: float
    tipo: str


class Catalogo(BaseModel):
    id: int
    nombre: str


class ClienteCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    rfc_nit: Optional[str] = Field(default=None, max_length=20)
    telefono: Optional[str] = Field(default=None, max_length=15)
    email: Optional[str] = Field(default=None, max_length=100)
    direccion: Optional[str] = None


class Cliente(BaseModel):
    id: int
    nombre: str
    rfc_nit: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None


class ItemVenta(BaseModel):
    id: int = Field(gt=0)
    tipo: Literal["producto", "servicio", "consulta", "honorario"] = "producto"
    cant: int = Field(gt=0, le=10000)


class VentaCrear(BaseModel):
    carrito: List[ItemVenta] = Field(min_length=1)
    metodo_pago_id: int
    pago: Optional[float] = Field(default=None, ge=0, description="Efectivo recibido (solo pagos en efectivo)")
    cliente_id: Optional[int] = None
    receta_id: Optional[int] = Field(default=None, description="Receta que se surte con esta venta")
    paciente_id: Optional[int] = Field(default=None, description="Paciente: la venta queda a su nombre")
    antibiotico: Optional[dict] = Field(default=None, description=(
        "Obligatorio si el carrito tiene antibióticos: paciente_nombre, paciente_id, medico_nombre, medico_cedula, "
        "medico_domicilio, institucion, receta_folio, receta_fecha, vale_salida, destino_receta (retenida/sellada)"))


class VentaRegistrada(BaseModel):
    venta_id: int
    folio: str
    total: float
    pago: float
    cambio: float
    metodo: str
    contiene_antibioticos: bool


class LineaVenta(BaseModel):
    producto_id: Optional[int] = None
    nombre: str
    cantidad: int
    precio_unitario: float
    subtotal: float
    antibiotico: bool


class VentaDetalle(BaseModel):
    id: int
    folio: str
    fecha: Optional[str] = None
    vendedor: str
    cliente: str
    metodo_pago: str
    total: float
    pago_recibido: float
    cambio_entregado: float
    detalle: List[LineaVenta]


class VentaResumen(BaseModel):
    id: int
    folio: str
    fecha: Optional[str] = None
    vendedor: str
    cliente: str
    metodo_pago: str
    total: float


class AbrirCaja(BaseModel):
    monto_inicial: float = Field(ge=0)


class EstadoCaja(BaseModel):
    abierto: bool
    corte_id: Optional[int] = None
    fecha_apertura: Optional[str] = None
    fondo_inicial: Optional[float] = None
    efectivo: Optional[float] = None
    tarjeta: Optional[float] = None
    transferencia: Optional[float] = None
    otros: Optional[float] = None
    numero_ventas: Optional[int] = None
    total_ventas: Optional[float] = None
    efectivo_en_caja: Optional[float] = None


class CorteCerrado(BaseModel):
    corte_id: int
    fecha_cierre: str
    fondo_inicial: float
    monto_final: float
    efectivo_en_caja: float
    efectivo: float
    tarjeta: float
    transferencia: float
    otros: float
    numero_ventas: int
    total_ventas: float


class CorteHistorial(BaseModel):
    corte_id: int
    fecha_apertura: Optional[str] = None
    fecha_cierre: Optional[str] = None
    monto_inicial: float
    monto_final: float


class TopProducto(BaseModel):
    nombre: str
    cantidad: int


class ResumenDia(BaseModel):
    fecha: str
    ventas: int
    ingresos: float
    efectivo: float
    tarjeta: float
    transferencia: float
    stock_bajo: int
    por_caducar: int
    cortes_abiertos: int
    top_productos: List[TopProducto]
