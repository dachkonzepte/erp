"""Version 1.8.128 -- Runde 1b: die Anmeldeschranke gilt für jede Methode (Nebenbefund 1.8.127 Nr. 1).

Bis 1.8.127 verlangte app/anmeldeschranke.py die Anmeldung nur für GET (Seite: Umleitung, API: 401) und für POST/PUT/PATCH/DELETE (401);
HEAD, OPTIONS, TRACE und jede andere Methode kamen ohne Anmeldung bis zum Routing -- dort beantworteten die Doku-Routen von FastAPI
(/openapi.json, /docs, /docs/oauth2-redirect, /redoc: Starlette-Route mit GET und HEAD) ein HEAD mit 200, alles andere 405 oder 404.
Seit 1.8.128: ohne gültige Sitzung wird jede Methode abgewiesen wie ein GET bzw. POST auf diesem Pfad -- Seite (GET, HEAD): Umleitung auf
/login, sonst 401 --, ausgenommen nur die öffentlichen Pfade mit ihren Methoden (OEFFENTLICH in der Schranke) und die Design-Dateien
(GET, HEAD).

    Entscheidung    die Regeln je Methode und Pfad, auch für die öffentlichen Pfade
    Angriffe        ohne Anmeldung gegen einen echten uvicorn (h11 und httptools): HEAD, OPTIONS, PUT, PATCH, DELETE, TRACE und eine
                    erfundene Methode, je auf eine Seite, eine API-Route und einen nicht vorhandenen Pfad -- jede Antwort kommt von der
                    Schranke (302 auf /login, 401, bei schreibender Methode ohne eigene Seite 403) oder vom Server selbst (400), keine
                    erreicht einen Endpunkt (Zähler an Routen, die jede Methode annehmen, auch HEAD)
    Gegenprobe      mit den Regeln von 1.8.127 werden die Angriffstests rot, und die HEAD-Route war ohne Anmeldung erreichbar
    Wächter         jeder Name in app/static/ passt zum Muster der Design-Ausnahme
"""

from __future__ import annotations

import http.client
import os
import socket
import threading
import time
from pathlib import Path

import pytest
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import anmeldeschranke
from app.anmeldeschranke import _page_requires_login, _request_requires_login
from app.auth import COOKIE_NAME
from app.design_dateien import STATIC_DIR, ist_design_pfad
from tests.anmeldung import EIGENE_SEITE, app_mit_schranke, neue_datenbank

ROOT = Path(__file__).resolve().parent.parent
ALLE = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "FOO"]
ANGRIFFS_METHODEN = ["HEAD", "OPTIONS", "PUT", "PATCH", "DELETE", "TRACE", "FOO"]


# ---------------------------------------------------------------------------
# Entscheidung
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("methode", ALLE)
@pytest.mark.parametrize("pfad", ["/projects", "/customers/1", "/gibt-es-nicht", "/"])
def test_seite_ohne_anmeldung_jede_methode_abgewiesen(methode, pfad):
    """GET und HEAD auf eine Seite: Umleitung auf /login; jede andere Methode: 401 (wie POST)."""
    umleitung, verweigert = _page_requires_login(True, methode, pfad), _request_requires_login(True, methode, pfad)
    assert (umleitung, verweigert) == ((True, False) if methode in ("GET", "HEAD") else (False, True))


@pytest.mark.parametrize("methode", ALLE)
@pytest.mark.parametrize("pfad", ["/api/customers", "/api/gibt-es-nicht", "/api/auth/gibt-es-nicht"])
def test_api_ohne_anmeldung_jede_methode_401(methode, pfad):
    assert _request_requires_login(True, methode, pfad) is True and _page_requires_login(True, methode, pfad) is False


@pytest.mark.parametrize("pfad,erlaubt", [
    ("/login", {"GET", "HEAD"}), ("/health", {"GET", "HEAD"}), ("/manifest.json", {"GET", "HEAD"}),
    ("/api/auth/status", {"GET", "HEAD"}), ("/api/auth/login", {"POST"}), ("/api/auth/logout", {"POST"}),
])
def test_oeffentliche_pfade_nur_mit_ihren_methoden(pfad, erlaubt):
    for methode in ALLE:
        abgewiesen = _request_requires_login(True, methode, pfad) or _page_requires_login(True, methode, pfad)
        assert abgewiesen is (methode not in erlaubt), (pfad, methode)


def test_ohne_konten_dieselbe_entscheidung():
    """Bis 1.8.129 blieb ohne Konto alles offen (1.8.128 Nr. 4); seit 1.8.130 öffnet has_users nichts mehr -- ohne Konto antwortet die
    Schranke vorher selbst (tests/test_v435_ersteinrichtung_geschlossen.py)."""
    for methode in ALLE:
        assert _request_requires_login(False, methode, "/api/users") is _request_requires_login(True, methode, "/api/users")
        assert _page_requires_login(False, methode, "/users") is _page_requires_login(True, methode, "/users")


# ---------------------------------------------------------------------------
# Angriffe gegen einen echten uvicorn
# ---------------------------------------------------------------------------

ERREICHT: list[str] = []
zaehl_router = APIRouter()


@zaehl_router.api_route("/zaehl/seite", methods=ALLE, include_in_schema=False)
@zaehl_router.api_route("/api/zaehl", methods=ALLE, include_in_schema=False)
def zaehl_endpunkt(request: Request):
    """Nimmt jede Methode an, auch HEAD -- erreicht eine Anfrage ohne Anmeldung diesen Endpunkt, steht sie in ERREICHT."""
    ERREICHT.append(f"{request.method} {request.url.path}")
    return JSONResponse({"erreicht": True})


@pytest.fixture(scope="module")
def welt():
    """Echte Schranke mit Seiten-, Kunden- und Zähl-Router; ein Konto, damit die Schranke greift."""
    from app.models import AppUser
    from app.routers import customers, pages
    from app.sitzungen import neue_sitzung

    engine, make_session = neue_datenbank()
    with make_session() as db:
        nutzer = AppUser(username="bea", display_name="Bea", role="buero_finanzen", password_hash="x")
        db.add(nutzer)
        db.commit()
        cookie = neue_sitzung(db, nutzer, zweiter_faktor=True)
        db.commit()
    app = app_mit_schranke(make_session, pages.router, customers.router, zaehl_router)
    yield {"app": app, "cookie": f"{COOKIE_NAME}={cookie}"}
    engine.dispose()


def _uvicorn(app, http_art: str):
    import uvicorn

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, http=http_art, log_level="warning", lifespan="off"))
    faden = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    faden.start()
    ende = time.monotonic() + 15
    while not server.started:
        assert time.monotonic() < ende, "uvicorn startet nicht"
        time.sleep(0.05)
    return server, faden, sock.getsockname()[1]


def _anfrage(port: int, methode: str, pfad: str, kopf: dict | None = None) -> tuple[int, dict, bytes]:
    verbindung = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        verbindung.putrequest(methode, pfad, skip_host=True, skip_accept_encoding=True)
        verbindung.putheader("Host", "testserver")
        for k, v in (kopf or {}).items():
            verbindung.putheader(k, v)
        verbindung.putheader("Content-Length", "0")
        verbindung.endheaders()
        antwort = verbindung.getresponse()
        return antwort.status, {k.lower(): v for k, v in antwort.getheaders()}, antwort.read()
    finally:
        verbindung.close()


# "Doku": die Starlette-Route von FastAPI für /openapi.json beantwortet HEAD selbst (wie /docs, /redoc, /docs/oauth2-redirect) -- bis
# 1.8.127 ohne Anmeldung 200, samt Berechnung der ganzen Schnittstellenbeschreibung
PFADE = {"Seite": "/zaehl/seite", "Seite (Router)": "/projects", "API": "/api/zaehl", "API (Router)": "/api/customers",
         "Doku": "/openapi.json", "fehlt": "/gibt-es-nicht", "API fehlt": "/api/gibt-es-nicht"}


def _von_der_schranke(status: int, kopf: dict, methode: str) -> str | None:
    """Wer geantwortet hat: "anmeldung" (302 auf /login bzw. 401), "ursprung" (403), "server" (400 -- der HTTP-Parser hat die Anfrage
    abgewiesen); None heißt: die Antwort kam von dahinter (Routing oder Endpunkt)."""
    if status == 302 and kopf.get("location", "").startswith("/login?next="):
        return "anmeldung"
    if status == 401:
        return "anmeldung"
    if status == 403:
        return "ursprung"
    if status == 400:
        return "server"
    return None


def angriffe(port: int) -> list[tuple[str, str, str, int, str | None]]:
    """[(Methode, Art, Pfad, Status, wer)] für jede Angriffsmethode, je ohne und mit Kopfzeilen der eigenen Seite."""
    ergebnisse = []
    for methode in ANGRIFFS_METHODEN:
        for art, pfad in PFADE.items():
            for kopf in ({}, EIGENE_SEITE):
                status, antwort_kopf, _ = _anfrage(port, methode, pfad, kopf)
                ergebnisse.append((methode, art, pfad, status, _von_der_schranke(status, antwort_kopf, methode)))
    return ergebnisse


def _angriffe_mit_server(app, http_art):
    server, faden, port = _uvicorn(app, http_art)
    try:
        ERREICHT.clear()
        return angriffe(port), list(ERREICHT)
    finally:
        server.should_exit = True
        faden.join(15)


@pytest.mark.parametrize("http_art", ["h11", "httptools"])
def test_angriffe_ohne_anmeldung_erreichen_keinen_endpunkt(welt, http_art):
    pytest.importorskip(http_art)
    ergebnisse, erreicht = _angriffe_mit_server(welt["app"], http_art)
    assert erreicht == [], "Endpunkt ohne Anmeldung erreicht"
    vorbei = [(m, art, status) for m, art, _, status, wer in ergebnisse if wer is None]
    assert vorbei == [], "Antwort von hinter der Schranke"
    # die erwartete Antwort je Methode: Seite mit HEAD -> Umleitung, sonst 401; schreibend ohne eigene Seite 403
    for methode, art, pfad, status, wer in ergebnisse:
        if wer == "server":
            assert http_art == "httptools" and methode == "FOO", (methode, art, status)


def test_angemeldet_erreichen_dieselben_methoden_den_endpunkt(welt):
    """Gegenstück: mit Sitzung geht jede Methode durch die Schranke (der Zähler zählt) -- die Tests oben prüfen also wirklich die
    Schranke, nicht eine Route, die es nicht gibt."""
    server, faden, port = _uvicorn(welt["app"], "h11")
    try:
        ERREICHT.clear()
        for methode in ANGRIFFS_METHODEN:
            status, _, _ = _anfrage(port, methode, "/api/zaehl", {"Cookie": welt["cookie"], **EIGENE_SEITE})
            assert status == 200, (methode, status)
        assert sorted(ERREICHT) == sorted(f"{m} /api/zaehl" for m in ANGRIFFS_METHODEN)
    finally:
        server.should_exit = True
        faden.join(15)


# Gegenprobe: die Regeln von 1.8.127 (wörtlich), eingesetzt in die echte Schranke

def _alt_request_requires_login(has_users, method, path):
    if not has_users or path.startswith("/api/auth/"):
        return False
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        return True
    return method == "GET" and path.startswith("/api/")


def _alt_page_requires_login(has_users, method, path):
    if not has_users or method != "GET" or path.startswith("/api/"):
        return False
    return path not in {"/login", "/health", "/manifest.json"}


def test_gegenprobe_mit_der_alten_schranke(welt, monkeypatch):
    monkeypatch.setattr(anmeldeschranke, "_request_requires_login", _alt_request_requires_login)
    monkeypatch.setattr(anmeldeschranke, "_page_requires_login", _alt_page_requires_login)
    ergebnisse, erreicht = _angriffe_mit_server(welt["app"], "h11")
    vorbei = {(m, art) for m, art, _, _, wer in ergebnisse if wer is None}
    assert "HEAD /zaehl/seite" in erreicht and "HEAD /api/zaehl" in erreicht, erreicht
    assert {("OPTIONS", "API (Router)"), ("TRACE", "Seite (Router)"), ("FOO", "fehlt"), ("HEAD", "API fehlt"), ("HEAD", "Doku")} <= vorbei
    assert any(m == "HEAD" and art == "Doku" and status == 200 for m, art, _, status, _ in ergebnisse)


# ---------------------------------------------------------------------------
# Wächter: Namen in app/static/
# ---------------------------------------------------------------------------

def namen_ausserhalb_der_ausnahme(wurzel: Path) -> list[str]:
    """Jeder Ordner- und Dateiname unter wurzel, dessen Pfad /static/<rel> die Design-Ausnahme nicht annimmt -- eine solche Datei wäre
    ohne Anmeldung nicht erreichbar (Seiten bänden sie ein, der Browser bekäme die Anmeldung)."""
    funde = []
    for ordner, verzeichnisse, dateien in os.walk(wurzel):
        for name in verzeichnisse + dateien:
            rel = (Path(ordner) / name).relative_to(wurzel).as_posix()
            pfad = f"/static/{rel}"
            if not ist_design_pfad({"type": "http", "method": "GET", "path": pfad, "raw_path": pfad.encode("utf-8")}):
                funde.append(rel)
    return sorted(funde)


def test_jeder_name_in_static_passt_zum_muster_der_ausnahme():
    assert namen_ausserhalb_der_ausnahme(STATIC_DIR) == []


def test_waechter_namen_gegenprobe(tmp_path):
    for rel in ("ds/gut.css", "ds/OFL-Archivo.txt", "ds/Grosse.css", "ds/mit leer.css", "ds/.versteckt.css", "ds/punkt.css.",
                "ds/umläut.css", "Ordner/x.css"):
        ziel = tmp_path / rel
        ziel.parent.mkdir(parents=True, exist_ok=True)
        try:
            ziel.write_text("x", encoding="utf-8")
        except OSError:  # Windows nimmt keinen Namen mit Punkt am Ende -- dann prüft der Fall nichts
            continue
    funde = namen_ausserhalb_der_ausnahme(tmp_path)
    assert "ds/gut.css" not in funde and "ds" not in funde
    assert {"ds/OFL-Archivo.txt", "ds/Grosse.css", "ds/mit leer.css", "ds/.versteckt.css", "ds/umläut.css", "Ordner"} <= set(funde)
