"""Lógica de negocio de la API (sin dependencias de FastAPI, fácil de probar)."""


class NegocioError(Exception):
    """Error de regla de negocio con el código HTTP sugerido."""

    def __init__(self, mensaje, status=400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status = status
