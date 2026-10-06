"""Configuración de Gunicorn para el servicio web (Flask)."""
import os

bind = "0.0.0.0:5010"
workers = int(os.getenv("WEB_WORKERS", "3"))
threads = int(os.getenv("WEB_THREADS", "2"))
timeout = 60
graceful_timeout = 20
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("WEB_LOG_LEVEL", "info")
forwarded_allow_ips = "*"
