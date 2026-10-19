"""Version 1.8.129 -- Runde 1c (Härtung vor Stufe 2): Schnittstellen-Doku nur lokal auf Wunsch, /health auch mit HEAD.

    Doku        /docs, /redoc, /docs/oauth2-redirect, /openapi.json gibt es nur mit ERP_API_DOKU=1 und ERP_ENV=development oder test
                (app/main.py::api_doku_aktiv()). Im Betriebsmodus -- ERP_ENV=production, auch mit ERP_API_DOKU=1 -- sind die Routen nicht
                angelegt: 404, auch mit Anmeldung (geprüft in einem Kindprozess, der app.main mit diesen Umgebungsvariablen und einer
                eigenen Wegwerf-Datenbank startet).
    /health     beantwortet GET und HEAD, ohne Anmeldung -- gegen einen echten uvicorn (HEAD ohne Inhalt).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.anmeldung import app_mit_schranke, neue_datenbank

ROOT = Path(__file__).resolve().parent.parent
DOKU = ["/docs", "/redoc", "/docs/oauth2-redirect", "/openapi.json"]


@pytest.mark.parametrize("umgebung,erwartet", [
    ({"ERP_API_DOKU": "1", "ERP_ENV": "development"}, True),
    ({"ERP_API_DOKU": "1", "ERP_ENV": "test"}, True),
    ({"ERP_API_DOKU": " 1 ", "ERP_ENV": "Development"}, True),
    ({"ERP_API_DOKU": "1", "ERP_ENV": "production"}, False),
    ({"ERP_API_DOKU": "1"}, False),
    ({"ERP_API_DOKU": "1", "ERP_ENV": "staging"}, False),
    ({"ERP_ENV": "development"}, False),
    ({"ERP_API_DOKU": "0", "ERP_ENV": "development"}, False),
    ({"ERP_API_DOKU": "ja", "ERP_ENV": "development"}, False),
    ({}, False),
])
def test_schalter(umgebung, erwartet):
    from app.main import api_doku_aktiv

    assert api_doku_aktiv(umgebung) is erwartet


def test_die_anwendung_legt_die_doku_nur_mit_schalter_an():
    from app import main

    pfade = {getattr(r, "path", None) for r in main.app.routes}
    assert main.API_DOKU == main.api_doku_aktiv()
    assert (set(DOKU) <= pfade) is main.API_DOKU and (set(DOKU) & pfade == set()) is (not main.API_DOKU)


# Kindprozess: app.main mit den Umgebungsvariablen des Betriebs (bzw. lokal), eigene Wegwerf-Datenbank (Regel 16), angemeldet über eine
# Sitzung als Cookie-Kopfzeile (im Betrieb ist das Cookie Secure, der TestClient spricht http)
KIND = r"""
import json, sys
from app.database import Base, SessionLocal, engine
import app.models  # noqa: F401
Base.metadata.create_all(engine)  # im Betrieb legt app.main keine Tabellen an
from app import grunddaten
from app.models import AppUser
from app.sitzungen import neue_sitzung
with SessionLocal() as db:
    grunddaten.anlegen(db)
    db.commit()
    nutzer = AppUser(username="ada", display_name="Ada", role="admin", password_hash="x")
    db.add(nutzer)
    db.commit()
    wert = neue_sitzung(db, nutzer, zweiter_faktor=True)
    db.commit()
from fastapi.testclient import TestClient
from app.auth import COOKIE_NAME
from app.main import app
client = TestClient(app)
angemeldet = {"cookie": f"{COOKIE_NAME}={wert}"}
ergebnis = {}
for pfad in json.loads(sys.argv[1]):
    ergebnis[pfad] = {
        "GET angemeldet": client.get(pfad, headers=angemeldet, follow_redirects=False).status_code,
        "HEAD angemeldet": client.head(pfad, headers=angemeldet, follow_redirects=False).status_code,
        "GET ohne": client.get(pfad, follow_redirects=False).status_code,
    }
ergebnis["/api/auth/status"] = {"GET angemeldet": client.get("/api/auth/status", headers=angemeldet).json().get("authenticated")}
print("ERGEBNIS " + json.dumps(ergebnis))
"""


def _kind(tmp_path: Path, **umgebung) -> dict:
    from tests.pg_schutz import pg_url_pruefen

    env = {k: v for k, v in os.environ.items() if not k.startswith("ERP_") and k != "DATABASE_URL"}
    env.update({"DATABASE_URL": pg_url_pruefen("sqlite:///" + (tmp_path / "erp.db").as_posix()), "ERP_DATA_DIR": str(tmp_path / "data"),
                "ERP_SECRET_KEY": "x" * 40, "PYTHONIOENCODING": "utf-8", **umgebung})
    lauf = subprocess.run([sys.executable, "-c", KIND, json.dumps(DOKU)], cwd=ROOT, env=env, capture_output=True, text=True,
                          encoding="utf-8", timeout=180)
    zeile = next((z for z in lauf.stdout.splitlines() if z.startswith("ERGEBNIS ")), None)
    assert zeile, lauf.stdout[-2000:] + lauf.stderr[-3000:]
    return json.loads(zeile.removeprefix("ERGEBNIS "))


def test_im_betriebsmodus_404_auch_mit_anmeldung_und_schalter(tmp_path):
    ergebnis = _kind(tmp_path, ERP_ENV="production", ERP_API_DOKU="1")
    assert ergebnis.pop("/api/auth/status") == {"GET angemeldet": True}, "die Anmeldung gilt"
    assert {pfad: (w["GET angemeldet"], w["HEAD angemeldet"]) for pfad, w in ergebnis.items()} == {pfad: (404, 404) for pfad in DOKU}
    assert {w["GET ohne"] for w in ergebnis.values()} == {302}, "ohne Anmeldung leitet die Schranke vorher um"


def test_lokal_ohne_schalter_404(tmp_path):
    ergebnis = _kind(tmp_path, ERP_ENV="development")
    ergebnis.pop("/api/auth/status")
    assert {w["GET angemeldet"] for w in ergebnis.values()} == {404}


def test_lokal_mit_schalter_verfuegbar(tmp_path):
    """Gegenstück: der Kindprozess misst wirklich die Doku -- lokal mit ERP_API_DOKU=1 ist sie angemeldet da (GET und HEAD 200, die
    OAuth-Umleitungsseite inbegriffen); ohne Anmeldung leitet die Schranke um."""
    ergebnis = _kind(tmp_path, ERP_ENV="development", ERP_API_DOKU="1")
    ergebnis.pop("/api/auth/status")
    assert {pfad: (w["GET angemeldet"], w["HEAD angemeldet"], w["GET ohne"]) for pfad, w in ergebnis.items()} == \
        {pfad: (200, 200, 302) for pfad in DOKU}


# ---------------------------------------------------------------------------
# /health mit HEAD
# ---------------------------------------------------------------------------

def test_health_get_und_head_ohne_anmeldung_gegen_echten_uvicorn():
    from app.models import AppUser
    from app.routers import pages
    from tests.test_v433_schranke_alle_methoden import _anfrage, _uvicorn

    engine, make_session = neue_datenbank()
    with make_session() as db:
        db.add(AppUser(username="u", display_name="U", role="admin", password_hash="x"))  # die Schranke greift erst mit Konten
        db.commit()
    app = app_mit_schranke(make_session, pages.router)
    server, faden, port = _uvicorn(app, "h11")
    try:
        status, kopf, body = _anfrage(port, "HEAD", "/health")
        assert status == 200 and body == b"" and kopf["content-type"].startswith("application/json"), (status, kopf)
        status, _, body = _anfrage(port, "GET", "/health")
        assert status == 200 and json.loads(body)["status"] == "ok"
        assert _anfrage(port, "OPTIONS", "/health")[0] == 401, "andere Methoden bleiben abgewiesen"
        assert _anfrage(port, "HEAD", "/login")[0] == 405, "die übrigen öffentlichen GET-Routen bleiben ohne HEAD"
    finally:
        server.should_exit = True
        faden.join(15)
        engine.dispose()
