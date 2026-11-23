"""Der Portal-Dienst (seit 1.11.2, Stufe P1b; Bauplan P1, Abschnitt 1.1) -- eine eigene ASGI-App, in der nur die Wege des Portals angelegt sind.

Gestartet auf dem Server als systemd-Dienst erp-portal unter dem Systembenutzer dkportal (scripts/server/erp-portal.service):

    .venv/bin/python -m gunicorn 'app.portal.main:erzeugen()' -w 1 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8010 …

erzeugen() liest die Einstellungen aus der Umgebung (einstellungen.py), prüft beim Start die Datenbank (PostgreSQL, Revision gleich dem Kopf der Migrationen
-- sonst startet der Dienst nicht, statt halb zu laufen; Vorfall 1) und gibt die App in der Schranke zurück (schranke.py). Kein Router des ERP, keine
Schnittstellen-Doku, kein create_all(), keine Grunddaten. Jeder Endpunkt ist ein gewöhnliches def (Threadpool, 10 Fäden; nie die Datenbank auf der
Event-Loop, wie Regel 35 im ERP).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import TimeoutError as PoolTimeout
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import routen
from .datenbank import Datenbank, engine_erzeugen
from .einstellungen import Einstellungen, EinstellungFalsch, aus_umgebung
from .schranke import Schranke

logger = logging.getLogger("dk_portal")
ROOT = Path(__file__).resolve().parents[2]
FAEDEN = 10
FEHLER_JE_STATUS = {400: "anfrage", 401: "sitzung", 404: "nicht_gefunden", 405: "methode", 413: "zu_gross", 422: "eingabe", 429: "bremse"}


def kopf_der_migrationen() -> str:
    """Der Kopf der Migrationskette aus alembic/ (der Dienst sieht den Ordner nur lesend)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    konfiguration = Config(str(ROOT / "alembic.ini"))
    konfiguration.set_main_option("script_location", str(ROOT / "alembic"))
    return ScriptDirectory.from_config(konfiguration).get_current_head()


def startpruefung(db: Datenbank) -> str:
    """Vor dem ersten Dienst: PostgreSQL erreichbar, Revision = Kopf. Gibt die Zeile fürs Journal zurück (ohne Geheimnisse)."""
    if db.engine.dialect.name != "postgresql":
        raise EinstellungFalsch("Das Portal läuft nur gegen PostgreSQL.")
    revision, kopf = db.revision(), kopf_der_migrationen()
    if revision != kopf:
        raise EinstellungFalsch(f"Datenbank auf Revision {revision}, der Code erwartet {kopf} -- erst update.sh (Migration), dann den Dienst starten.")
    return f"Portal verbunden als {db.benutzer()}, Revision {revision}"


def _fehler(status: int, fehler: str, kopf: dict | None = None) -> JSONResponse:
    return JSONResponse({"fehler": fehler}, status_code=status, headers=kopf)


def erzeugen(einstellungen: Einstellungen | None = None, *, engine=None, pruefen: bool = True):
    einstellungen = einstellungen or aus_umgebung()
    db = Datenbank(engine if engine is not None else engine_erzeugen(einstellungen.datenbank_url))
    if pruefen:
        logger.warning(startpruefung(db))  # warning: steht im Journal auch ohne eigene Log-Einstellung

    @asynccontextmanager
    async def lebensdauer(_app):
        import anyio.to_thread
        anyio.to_thread.current_default_thread_limiter().total_tokens = FAEDEN
        yield

    api = FastAPI(title="Kundenportal", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lebensdauer)
    api.state.db = db
    api.state.einstellungen = einstellungen
    api.include_router(routen.router)

    @api.exception_handler(StarletteHTTPException)
    async def _http(_request: Request, exc: StarletteHTTPException):
        return _fehler(exc.status_code, FEHLER_JE_STATUS.get(exc.status_code, "anfrage"), getattr(exc, "headers", None))

    @api.exception_handler(RequestValidationError)
    async def _eingabe(_request: Request, _exc: RequestValidationError):
        return _fehler(422, "eingabe")

    @api.exception_handler(PoolTimeout)
    async def _ausgelastet(_request: Request, _exc: PoolTimeout):
        return _fehler(503, "ausgelastet")

    @api.exception_handler(Exception)
    async def _technisch(_request: Request, exc: Exception):
        logger.error("Fehler im Portal: %s", type(exc).__name__)  # nur die Klasse, nie der Text (er kann Werte enthalten)
        return _fehler(500, "technisch")

    return Schranke(api, einstellungen)
