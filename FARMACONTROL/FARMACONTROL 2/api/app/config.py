"""Configuración de la API (variables de entorno)."""
import os


def _int(nombre, defecto):
    try:
        return int(os.getenv(nombre, defecto))
    except (TypeError, ValueError):
        return defecto


class Settings:
    APP_NAME = "FarmaControl API"
    VERSION = "2.0.0"

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = _int("DB_PORT", 3306)
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "131004131004")
    DB_NAME = os.getenv("DB_NAME", "medicalife")

    # Token compartido con el servicio web (Flask) para llamadas internas
    API_INTERNAL_TOKEN = os.getenv("API_INTERNAL_TOKEN", "cambia-este-token-interno")
    # Firma de los JWT para clientes externos (apps, integraciones)
    JWT_SECRET = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", "cambia-esta-clave-jwt"))
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_MINUTES = _int("JWT_EXPIRE_MINUTES", 720)

    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

    DIAS_ALERTA_CADUCIDAD = _int("DIAS_ALERTA_CADUCIDAD", 15)


settings = Settings()
