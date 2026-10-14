"""Version 1.8.107 -- Secure als Vorgabe, HSTS, Schutzkopfzeilen auch an der 500 (zweite Vorgabe vom 14.10.2026: Korrektur 104-8 und
Punkt 2).

    104-8  Secure ist die Vorgabe; ohne Secure nur bei ausdrücklich lokalem Betrieb (ERP_ENV=development) oder in Tests
           (ERP_ENV=test). Fehlt ERP_ENV, bleibt Secure (app/auth.py::NUR_HTTPS, COOKIE_SECURE).
    2      HSTS in Produktion, ohne includeSubDomains -- wo das Cookie Secure ist (app/anmeldeschranke.py::HSTS). Die Schutzkopfzeilen
           (X-Frame-Options, frame-ancestors, Cache-Control: no-store, HSTS) tragen alle Antworten, auch die 500 aus dem Fehler-Handler
           (app/anmeldeschranke.py::serverfehler(), eingebunden über einbinden()).

Angriffstests mit der echten Anmeldeschranke (tests/anmeldung.py). Gegenproben: docs/archiv/befund-vor-echtbetrieb.md,
"Umsetzung 1.8.107"."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app import anmeldeschranke, sitzungen
from app.auth import COOKIE_NAME, hash_password
from app.models import AppUser
from app.routers import auth as auth_router
from app.routers import pages as pages_router
from tests.anmeldung import EIGENE_SEITE, app_mit_schranke, client_mit_schranke, neue_datenbank
from tests.pg_schutz import pg_url_pruefen
from tests.test_v326_monteur_datengrenze import _buero_welt, _routers_in_betriebsreihenfolge
from tests.test_v403_kein_cache import _logo, _rundgang
from tests.uhr import uhr_festhalten

ROOT = Path(__file__).resolve().parent.parent
HSTS = "max-age=31536000"
GEHEIM = "Kundin Gerda Geheim, IBAN DE00 1234"

_probe = APIRouter()


@_probe.get("/api/fehler")
def _fehler_api():
    raise RuntimeError(GEHEIM)


@_probe.get("/seite-mit-fehler")
def _fehler_seite():
    raise RuntimeError(GEHEIM)


@_probe.post("/api/fehler")
def _fehler_schreiben():
    raise ValueError(GEHEIM)


@_probe.get("/api/lesen")
def _lesen():
    return {"ok": True}


def _umgebung(code: str, **env_neu) -> str:
    env = {k: v for k, v in os.environ.items() if k not in ("ERP_COOKIE_SECURE", "ERP_ENV")}
    env.update({"DATABASE_URL": pg_url_pruefen("sqlite://"), "PYTHONIOENCODING": "utf-8", **env_neu})
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


# ---------------------------------------------------------------------------
# 104-8: Secure als Vorgabe, HSTS an derselben Stelle
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("env, secure, hsts", [
    ({}, "True", HSTS),                                            # fehlt ERP_ENV, bleibt Secure
    ({"ERP_ENV": ""}, "True", HSTS),                               # leer wie fehlend
    ({"ERP_ENV": "production"}, "True", HSTS),
    ({"ERP_ENV": " Production "}, "True", HSTS),
    ({"ERP_ENV": "production", "ERP_COOKIE_SECURE": "0"}, "True", HSTS),
    ({"ERP_ENV": "staging"}, "True", HSTS),                        # unbekannt = nicht ausdrücklich lokal
    ({"ERP_COOKIE_SECURE": "0"}, "True", HSTS),                    # der Schalter schaltet nur ein, nie aus
    ({"ERP_ENV": "development"}, "False", "None"),                 # ausdrücklich lokal
    ({"ERP_ENV": "test"}, "False", "None"),                        # Tests
    ({"ERP_ENV": "development", "ERP_COOKIE_SECURE": "1"}, "True", "None"),  # lokal hinter HTTPS: Secure, aber kein HSTS
])
def test_secure_ist_die_vorgabe_und_hsts_steht_an_derselben_stelle(env, secure, hsts):
    assert _umgebung("import app.auth as a, app.anmeldeschranke as s; print(a.COOKIE_SECURE); print(s.HSTS)", **env).splitlines() == [
        secure, hsts]


def test_die_tests_laufen_ausdruecklich_als_test():
    """tests/conftest.py setzt ERP_ENV=test -- ohne das wäre das Cookie Secure und der TestClient (http://testserver) schickte es nie
    zurück."""
    from app import auth
    assert os.environ.get("ERP_ENV") == "test" and auth.COOKIE_SECURE is False and anmeldeschranke.HSTS is None


def test_lokaler_start_ist_ausdruecklich_lokal():
    """start_windows.bat startet uvicorn auf 127.0.0.1 über reines HTTP -- ausdrücklich lokal, sonst wäre das Cookie Secure."""
    text = (ROOT / "start_windows.bat").read_text(encoding="utf-8")
    assert "set ERP_ENV=development" in text and text.index("set ERP_ENV=development") < text.index("uvicorn app.main:app")


# ---------------------------------------------------------------------------
# Punkt 2: HSTS an jeder Antwort, Schutzkopfzeilen auch an der 500
# ---------------------------------------------------------------------------

@pytest.fixture
def welt():
    engine, make_session = neue_datenbank()
    with make_session() as db:
        user = AppUser(username="anna", display_name="Anna", role="buero_auftrag", active=True, password_hash=hash_password("Pw-12345678"))
        db.add(user)
        db.commit()
        wert = sitzungen.neue_sitzung(db, user)
        db.commit()
    app = app_mit_schranke(make_session, auth_router.router, pages_router.router, _probe)
    yield app, wert
    engine.dispose()


def _client(app, wert=None) -> TestClient:
    c = TestClient(app, headers=dict(EIGENE_SEITE), raise_server_exceptions=False)
    if wert:
        c.cookies.set(COOKIE_NAME, wert, domain="testserver.local")
    return c


def _geschuetzt(antwort, hsts: str | None) -> list[str]:
    """Was an den Schutzkopfzeilen einer Antwort fehlt (leer = alles da)."""
    fehlt = []
    if antwort.headers.get("x-frame-options") != "DENY":
        fehlt.append("X-Frame-Options")
    if "frame-ancestors 'none'" not in antwort.headers.get("content-security-policy", ""):
        fehlt.append("frame-ancestors")
    if antwort.headers.get("strict-transport-security") != hsts:
        fehlt.append(f"HSTS={antwort.headers.get('strict-transport-security')!r}")
    return fehlt


@pytest.mark.parametrize("hsts", [None, HSTS])
@pytest.mark.parametrize("methode, pfad, angemeldet", [
    ("GET", "/api/fehler", True), ("GET", "/seite-mit-fehler", True), ("POST", "/api/fehler", True), ("GET", "/api/fehler", False),
])
def test_die_500_traegt_die_schutzkopfzeilen_und_keine_daten(welt, monkeypatch, caplog, hsts, methode, pfad, angemeldet):
    """Angriffstest: ein unbehandelter Fehler -- die Antwort kommt aus dem äußersten Fehler-Handler (an der Schranke vorbei), trägt
    trotzdem alle Schutzkopfzeilen und Cache-Control: no-store, und nennt nichts aus dem Fehler. Ohne Anmeldung ist die API 401, nicht
    500 (die Schranke lässt die Anfrage gar nicht durch)."""
    monkeypatch.setattr(anmeldeschranke, "HSTS", hsts)
    app, wert = welt
    with caplog.at_level(logging.ERROR):
        antwort = _client(app, wert if angemeldet else None).request(methode, pfad)
    assert antwort.status_code == (500 if angemeldet else 401)
    assert _geschuetzt(antwort, hsts) == []
    assert GEHEIM not in antwort.text and "Traceback" not in antwort.text
    if angemeldet:
        assert antwort.text == "Internal Server Error" and antwort.headers["content-type"].startswith("text/plain")
        assert antwort.headers.get("cache-control") == "no-store"


def test_ein_fehler_in_der_schranke_selbst_traegt_die_schutzkopfzeilen(monkeypatch):
    """Angriffstest: die Datenbank fällt aus, bevor die Schranke weiß, wer anfragt (users_exist wirft) -- auch diese 500 trägt sie."""
    from fastapi import FastAPI

    monkeypatch.setattr(anmeldeschranke, "HSTS", HSTS)

    def kaputt():
        raise RuntimeError("Datenbank weg: " + GEHEIM)

    app = FastAPI()
    app.include_router(_probe)
    anmeldeschranke.einbinden(app, kaputt)
    antwort = _client(app).get("/api/lesen")
    assert antwort.status_code == 500 and _geschuetzt(antwort, HSTS) == [] and GEHEIM not in antwort.text
    assert antwort.headers.get("cache-control") == "no-store"


@pytest.mark.parametrize("anfrage", [
    ("GET", "/login", {}), ("GET", "/api/lesen", {}), ("GET", "/kunden-gibt-es-nicht", {}), ("GET", "/api/gibt-es-nicht", {}),
    ("POST", "/api/fehler", {"sec-fetch-site": "cross-site"}), ("HEAD", "/login", {}), ("OPTIONS", "/api/lesen", {}),
])
def test_hsts_an_jeder_antwort_ohne_includesubdomains(welt, monkeypatch, anfrage):
    """Mit HSTS (Produktion) trägt jede Antwort der Schranke die Kopfzeile -- auch 401, 403, 404, Weiterleitung -- genau so: ein Jahr,
    ohne includeSubDomains und ohne preload."""
    monkeypatch.setattr(anmeldeschranke, "HSTS", HSTS)
    app, wert = welt
    methode, pfad, kopf = anfrage
    for c in (_client(app), _client(app, wert)):
        antwort = c.request(methode, pfad, headers=kopf, follow_redirects=False)
        assert antwort.headers.get("strict-transport-security") == "max-age=31536000", (methode, pfad, antwort.status_code)
        assert "includesubdomains" not in antwort.headers["strict-transport-security"].lower()
        assert "preload" not in antwort.headers["strict-transport-security"].lower()


def test_die_anwendung_bindet_den_fehler_handler_ein():
    """app/main.py bindet Schranke und Fehler-Handler über dieselbe Funktion ein wie die Tests (app/anmeldeschranke.py::einbinden())."""
    from app import main
    assert main.app.exception_handlers.get(Exception) is anmeldeschranke.serverfehler
    namen = [getattr(m.kwargs.get("dispatch"), "__qualname__", "") for m in main.app.user_middleware]
    assert namen.count("middleware.<locals>.identitaet_und_audit") == 1


@pytest.fixture(scope="module")
def durchlauf_mit_hsts():
    """Der Rundgang aus test_v403 (alle GET-Routen als Administratorin und Monteurin), mit HSTS wie in Produktion."""
    engine, make_session = neue_datenbank()
    try:
        with uhr_festhalten(), pytest.MonkeyPatch.context() as mp:
            mp.setattr(anmeldeschranke, "HSTS", HSTS)
            with make_session() as db:
                welt = _buero_welt(db)
                _logo(db)
                werte = {"admin": sitzungen.neue_sitzung(db, db.get(AppUser, welt["admin_id"]), zweiter_faktor=True),
                         "monteurin": sitzungen.neue_sitzung(db, db.get(AppUser, welt["user_id"]))}
                db.commit()
            routers = _routers_in_betriebsreihenfolge()
            ergebnis = {}
            for name, wert in werte.items():
                client = client_mit_schranke(make_session, *routers, raise_server_exceptions=False)
                client.cookies.set(COOKIE_NAME, wert, domain="testserver.local")
                ergebnis[name] = _rundgang(client, welt, routers)
            yield ergebnis
    finally:
        engine.dispose()


def test_jede_antwort_des_rundgangs_traegt_hsts(durchlauf_mit_hsts):
    for wer, antworten in durchlauf_mit_hsts.items():
        assert len([a for a in antworten if a["status"] == 200]) > (150 if wer == "admin" else 50)
        ohne = [f"{a['route']} ({a['status']})" for a in antworten if a["status"] is not None and a["hsts"] != HSTS]
        assert ohne == [], f"{wer}: Antwort ohne HSTS: " + "; ".join(ohne)
