"""
FarmaControl API (FastAPI)

Servicio REST independiente que concentra la lógica del punto de venta.
- Documentación interactiva: /docs (Swagger) y /redoc
- Lo consume el servicio web (Flask) y cualquier cliente externo con JWT.
"""
import logging

import pymysql
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .routers import auth, caja, catalogo, clientes, clinica, health, productos, reportes, ventas
from .services import NegocioError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("farmacontrol.api")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="API REST de FarmaControl: productos, ventas, caja, clientes, reportes y expediente clínico.",
    docs_url="/docs",
    redoc_url="/redoc",
)

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(NegocioError)
async def error_negocio(_request: Request, exc: NegocioError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.mensaje})


@app.exception_handler(pymysql.err.OperationalError)
async def error_bd(_request: Request, exc: pymysql.err.OperationalError):
    log.error("Base de datos no disponible: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Base de datos no disponible"})


app.include_router(health.router)
for r in (auth.router, productos.router, catalogo.router, clientes.router, ventas.router,
          caja.router, reportes.router, clinica.router):
    app.include_router(r, prefix="/v1")


@app.get("/", include_in_schema=False)
def raiz():
    return {"servicio": settings.APP_NAME, "version": settings.VERSION, "docs": "/docs"}
