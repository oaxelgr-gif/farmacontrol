# ---------- Imagen: farmacontrol-web (Flask + Gunicorn) ----------
# Contexto de construcción: raíz del proyecto
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=America/Mexico_City

RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt docker/web/requirements-docker.txt ./
RUN pip install --upgrade pip \
 && pip install -r requirements.txt -r requirements-docker.txt

COPY config.py app.py ./
COPY docker/web/gunicorn.conf.py ./gunicorn.conf.py
COPY farmacontrol ./farmacontrol
COPY templates ./templates
COPY static ./static

RUN useradd --create-home --uid 1000 farma \
 && mkdir -p /srv/instance/uploads \
 && chown -R farma /srv
USER farma

EXPOSE 5010

HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5010/health', timeout=4).status == 200 else 1)"

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
