"""
Configuración central de FarmaControl.

Todos los valores se pueden sobrescribir con variables de entorno o con un
archivo `.env` en la raíz del proyecto (ver `.env.example`).
Los valores por defecto replican la configuración original para que el
sistema siga funcionando sin cambios en la máquina de desarrollo.
"""
import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

try:  # python-dotenv es opcional
    from dotenv import load_dotenv

    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:  # pragma: no cover
    pass


def _bool(valor, defecto=False):
    if valor is None:
        return defecto
    return str(valor).strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


class Config:
    # --- Flask ---
    SECRET_KEY = os.getenv("SECRET_KEY", "131004131004")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    JSON_SORT_KEYS = False

    # --- Base de datos MySQL ---
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "131004131004")
    DB_NAME = os.getenv("DB_NAME", "medicalife")

    # --- Microservicio FastAPI (opcional) ---
    # Vacío = el punto de venta usa la lógica local. En Docker: http://api:8000
    API_URL = os.getenv("API_URL", "")
    API_INTERNAL_TOKEN = os.getenv("API_INTERNAL_TOKEN", "cambia-este-token-interno")
    API_TIMEOUT = float(os.getenv("API_TIMEOUT", "8"))
    API_PUBLIC_URL = os.getenv("API_PUBLIC_URL", "")  # enlace a /docs mostrado en la interfaz

    # --- Reglas de negocio ---
    DIAS_ALERTA_CADUCIDAD = int(os.getenv("DIAS_ALERTA_CADUCIDAD", "15"))
    FONDO_SUGERIDO = float(os.getenv("FONDO_SUGERIDO", "500"))
    NOMBRE_NEGOCIO = os.getenv("NOMBRE_NEGOCIO", "MEDICALIFE")
    NOMBRE_SUCURSAL = os.getenv("NOMBRE_SUCURSAL", "Consultorio y Farmacia")
    TELEFONO_NEGOCIO = os.getenv("TELEFONO_NEGOCIO", "(55) 1234-5678")
    ESTACION_CAJA = os.getenv("ESTACION_CAJA", "ESTACION01")

    # --- Archivos (resultados de estudios) ---
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(BASE_DIR, "instance", "uploads"))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB por archivo

    # --- Servidor ---
    HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT = int(os.getenv("FLASK_PORT", "5010"))
    DEBUG = _bool(os.getenv("FLASK_DEBUG"), True)
