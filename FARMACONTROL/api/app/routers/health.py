"""Estado del servicio (usado por Docker healthcheck)."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..config import settings
from ..db import connect

router = APIRouter(tags=["Sistema"])


@router.get("/health", summary="Estado de la API y de la base de datos")
def health():
    try:
        conn = connect(reintentos=1)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            cur.fetchone()
        conn.close()
        db = "ok"
    except Exception as exc:  # pragma: no cover
        return JSONResponse(status_code=503, content={"status": "degradado", "db": str(exc),
                                                      "version": settings.VERSION})
    return {"status": "ok", "db": db, "version": settings.VERSION}
