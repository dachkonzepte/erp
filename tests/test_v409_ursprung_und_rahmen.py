"""Version 1.8.104 -- Anfragen fremder Seiten, Einrahmen, Secure (Vorgabe vom 14.10.2026, Punkte 3–5; Befund 1.8.100 Nr. 1–3).

    3  Schreibende Anfragen ohne passenden Ursprung bekommen 403, auch von Unterdomains (app/anmeldeschranke.py::ursprung_passt()):
       Sec-Fetch-Site muss "same-origin" sein; ohne sie muss Origin zu Host passen; fehlt beides, 403.
    4  Kein Einrahmen: jede Antwort trägt X-Frame-Options: DENY und Content-Security-Policy frame-ancestors 'none'.
    5  Secure am Anmelde-Cookie in Produktion ohne Schalter (app/auth.py::COOKIE_SECURE).

Angriffstests mit der echten Anmeldeschranke (tests/anmeldung.py); im Browser: scripts/klicktest_fremde_seite.py."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app import sitzungen
from app.anmeldeschranke import FREMDER_URSPRUNG, ursprung_passt
from app.auth import COOKIE_NAME, hash_password
from app.dateiauslieferung import datei_antwort
from app.models import AppUser, Customer
from app.routers import account as account_router
from app.routers import auth as auth_router
from app.routers import customers as customers_router
from app.routers import pages as pages_router
from tests.anmeldung import EIGENE_SEITE, app_mit_schranke, neue_datenbank
from tests.pg_schutz import pg_url_pruefen
from tests.test_v403_kein_cache import durchlauf  # noqa: F401  (Fixture: Rundgang über alle GET-Routen)

ROOT = Path(__file__).resolve().parent.parent
PASSWORT = "Passwort-123"

_probe = APIRouter()


@_probe.api_route("/api/probe/schreiben", methods=["POST", "PUT", "PATCH", "DELETE"])
def _schreiben():
    return {"ok": True}


@_probe.get("/api/probe/lesen")
def _lesen():
    return {"ok": True}


@_probe.get("/api/probe/datei")
def _datei():
    return datei_antwort(b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "a.svg")


@_probe.get("/api/probe/svg-bild")
def _svg_bild():
    return datei_antwort(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "logo.svg", svg_als_bild=True)


@pytest.fixture
def welt():
    engine, make_session = neue_datenbank()
    with make_session() as db:
        db.add(AppUser(username="bea", display_name="Bea", role="buero_auftrag", active=True, password_hash=hash_password(PASSWORT)))
        db.add(Customer(name="Kunde", last_name="Kunde"))
        db.commit()
    app = app_mit_schranke(make_session, auth_router.router, account_router.router, pages_router.router, customers_router.router,
                           _probe)
    yield app, make_session
    engine.dispose()


def _client(app, make_session=None, *, angemeldet: bool = True) -> TestClient:
    """Ein Gerät OHNE vorgegebene Kopfzeilen (anders als browser_client()) -- jede Anfrage nennt ihren Ursprung selbst."""
    c = TestClient(app, raise_server_exceptions=False)
    if angemeldet:
        with make_session() as db:
            wert = sitzungen.neue_sitzung(db, db.query(AppUser).filter_by(username="bea").one())
            db.commit()
        c.cookies.set(COOKIE_NAME, wert, domain="testserver.local")
    return c


# ---------------------------------------------------------------------------
# Punkt 3: Ursprung schreibender Anfragen
# ---------------------------------------------------------------------------

ANGRIFFE = {
    "Unterdomain (same-site)": {"sec-fetch-site": "same-site", "origin": "https://www.dachkonzepte.gmbh"},
    "Unterdomain, Origin gefälscht passend": {"sec-fetch-site": "same-site", "origin": "http://testserver"},
    "fremde Site": {"sec-fetch-site": "cross-site", "origin": "https://boese.example"},
    "Adresszeile (none)": {"sec-fetch-site": "none"},
    "unbekannter Wert": {"sec-fetch-site": "same-origin, cross-site"},
    "ohne Sec-Fetch-Site: Unterdomain": {"origin": "https://www.dachkonzepte.gmbh"},
    "ohne Sec-Fetch-Site: Host als Präfix": {"origin": "http://testserver.boese.example"},
    "ohne Sec-Fetch-Site: anderer Port": {"origin": "http://testserver:8080"},
    "ohne Sec-Fetch-Site: Benutzerteil": {"origin": "http://boese@testserver"},
    "ohne Sec-Fetch-Site: mit Pfad": {"origin": "http://testserver/x"},
    "ohne Sec-Fetch-Site: anderes Schema": {"origin": "javascript://testserver"},
    "ohne Sec-Fetch-Site: null": {"origin": "null"},
    "ohne Sec-Fetch-Site: leer": {"origin": ""},
    "nur Referer passend": {"referer": "http://testserver/customers/1"},
    "gar nichts": {},
}
ERLAUBT = {
    "eigene Seite": dict(EIGENE_SEITE),
    "same-origin, Origin vom Proxy umgeschrieben": {"sec-fetch-site": "same-origin", "origin": "https://app.dachkonzepte.gmbh"},
    "same-origin in Großbuchstaben": {"sec-fetch-site": "Same-Origin"},
    "ohne Sec-Fetch-Site: Origin passt": {"origin": "http://testserver"},
    "ohne Sec-Fetch-Site: Origin in Großbuchstaben": {"origin": "HTTP://TESTSERVER"},
}


@pytest.mark.parametrize("methode", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("name", list(ANGRIFFE))
def test_schreibende_anfrage_ohne_passenden_ursprung_403(welt, methode, name):
    app, make_session = welt
    antwort = _client(app, make_session).request(methode, "/api/probe/schreiben", headers=ANGRIFFE[name])
    assert (antwort.status_code, antwort.json()) == (403, {"detail": FREMDER_URSPRUNG})
    assert antwort.headers["x-frame-options"] == "DENY"


@pytest.mark.parametrize("methode", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("name", list(ERLAUBT))
def test_schreibende_anfrage_der_eigenen_seite_geht(welt, methode, name):
    app, make_session = welt
    antwort = _client(app, make_session).request(methode, "/api/probe/schreiben", headers=ERLAUBT[name])
    assert antwort.status_code == 200, antwort.text


@pytest.mark.parametrize("name", list(ANGRIFFE))
def test_lesen_bleibt_von_ueberall(welt, name):
    """Lesen ändert nichts -- eine fremde Seite bekommt die Antwort ohnehin nicht zu sehen (keine CORS-Freigabe)."""
    app, make_session = welt
    assert _client(app, make_session).get("/api/probe/lesen", headers=ANGRIFFE[name]).status_code == 200


def test_upload_und_aenderung_von_der_unterdomain_aendern_nichts(welt):
    """Angriffstest wie Befund 1.8.100 Nr. 2: Formular-Upload und eine Anfrage ohne Body (Abmelden) von www.dachkonzepte.gmbh -- 403,
    kein Dokument, die Sitzung lebt."""
    app, make_session = welt
    client = _client(app, make_session)
    fremd = ANGRIFFE["Unterdomain (same-site)"]
    with make_session() as db:
        kid = db.query(Customer).one().id
    antwort = client.post(f"/api/customers/{kid}/documents", headers=fremd, files={"file": ("a.pdf", b"%PDF-1.4 x", "application/pdf")})
    assert antwort.status_code == 403
    assert client.post("/api/auth/logout", headers=fremd).status_code == 403
    assert client.get(f"/api/customers/{kid}/documents").json() == []
    assert client.get("/api/auth/status").json()["authenticated"] is True
    with make_session() as db:
        assert db.query(sitzungen.UserSession).count() == 1


def test_anmelden_von_fremder_seite_wird_abgelehnt(welt):
    """Auch ohne Sitzung: eine fremde Seite kann niemanden in ein Konto ihrer Wahl anmelden (Anmelde-CSRF)."""
    app, _ = welt
    client = _client(app, angemeldet=False)
    antwort = client.post("/api/auth/login", json={"username": "bea", "password": PASSWORT}, headers=ANGRIFFE["Unterdomain (same-site)"])
    assert antwort.status_code == 403
    assert COOKIE_NAME not in antwort.headers.get("set-cookie", "")
    eigen = client.post("/api/auth/login", json={"username": "bea", "password": PASSWORT}, headers=EIGENE_SEITE)
    assert eigen.status_code == 200 and COOKIE_NAME in eigen.headers.get("set-cookie", "")


def test_ursprung_passt_als_funktion():
    from starlette.requests import Request

    def anfrage(methode, **kopf):
        kopf.setdefault("host", "app.dachkonzepte.gmbh")
        return Request({"type": "http", "method": methode, "path": "/", "headers": [(k.encode(), v.encode()) for k, v in kopf.items()]})

    assert ursprung_passt(anfrage("GET", **{"sec-fetch-site": "cross-site"}))
    assert ursprung_passt(anfrage("HEAD"))
    assert ursprung_passt(anfrage("OPTIONS"))
    assert ursprung_passt(anfrage("POST", origin="https://app.dachkonzepte.gmbh"))
    assert not ursprung_passt(anfrage("POST", origin="https://www.dachkonzepte.gmbh"))
    assert not ursprung_passt(anfrage("post", **{"sec-fetch-site": "same-site"}))
    assert not ursprung_passt(anfrage("DELETE"))


def test_die_anwendung_bindet_die_schranke_ein():
    """app/main.py bindet die Anmeldeschranke (mit der Prüfung) als Middleware ein -- sonst schützte sie nur die Tests."""
    from app import main
    namen = [getattr(m.kwargs.get("dispatch"), "__qualname__", "") for m in main.app.user_middleware]
    assert "middleware.<locals>.identitaet_und_audit" in namen


# ---------------------------------------------------------------------------
# Punkt 4: kein Einrahmen
# ---------------------------------------------------------------------------

def _rahmen_verboten(antwort) -> bool:
    csp = antwort.headers.get("content-security-policy", "")
    return antwort.headers.get("x-frame-options") == "DENY" and "frame-ancestors 'none'" in csp


@pytest.mark.parametrize("pfad", ["/login", "/api/auth/status", "/api/probe/lesen", "/customers/1"])
def test_ohne_anmeldung_jede_antwort_ohne_rahmen(welt, pfad):
    app, _ = welt
    antwort = _client(app, angemeldet=False).get(pfad, follow_redirects=False)
    assert _rahmen_verboten(antwort), (antwort.status_code, dict(antwort.headers))


def test_angemeldet_seiten_und_api_ohne_rahmen(welt):
    app, make_session = welt
    client = _client(app, make_session)
    for pfad in ("/account", "/customers/1", "/api/auth/status"):
        antwort = client.get(pfad)
        assert antwort.status_code == 200 and _rahmen_verboten(antwort), pfad
    assert _rahmen_verboten(client.post("/api/probe/schreiben", headers=EIGENE_SEITE))


def test_dateien_behalten_ihre_sandbox_und_bekommen_frame_ancestors(welt):
    app, make_session = welt
    client = _client(app, make_session)
    datei = client.get("/api/probe/datei")
    assert datei.headers["content-security-policy"] == "sandbox; frame-ancestors 'none'"
    assert datei.headers["x-frame-options"] == "DENY"
    svg = client.get("/api/probe/svg-bild")
    assert svg.headers["content-security-policy"].startswith("sandbox; default-src 'none'")
    assert svg.headers["content-security-policy"].endswith("; frame-ancestors 'none'")


def test_jede_antwort_des_rundgangs_ohne_rahmen(durchlauf):  # noqa: F811
    """Alle GET-Routen (Seiten, API, PDFs, Dateien, Logo) als Administratorin und als Monteurin (Rundgang aus test_v403)."""
    for wer, antworten in durchlauf.items():
        ohne = [f"{a['route']} ({a['status']})" for a in antworten
                if a["status"] is not None and not (a["xfo"] == "DENY" and "frame-ancestors 'none'" in (a["csp"] or ""))]
        assert ohne == [], f"{wer}: Antwort ohne Schutz gegen Einrahmen: " + "; ".join(ohne)


# ---------------------------------------------------------------------------
# Punkt 5: Secure in Produktion ohne Schalter
# ---------------------------------------------------------------------------

def _cookie_secure(**env_neu) -> str:
    env = {k: v for k, v in os.environ.items() if k not in ("ERP_COOKIE_SECURE", "ERP_ENV")}
    env.update({"DATABASE_URL": pg_url_pruefen("sqlite://"), "PYTHONIOENCODING": "utf-8", **env_neu})
    r = subprocess.run([sys.executable, "-c", "import app.auth as a; print(a.COOKIE_SECURE)"], cwd=ROOT, env=env, capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.mark.parametrize("env, soll", [
    ({"ERP_ENV": "production"}, "True"),
    ({"ERP_ENV": "production", "ERP_COOKIE_SECURE": "0"}, "True"),  # ohne Schalter: auch ein ausdrückliches 0 ändert nichts
    ({"ERP_ENV": "production", "ERP_COOKIE_SECURE": "1"}, "True"),
    ({}, "True"),  # seit 1.8.107 (Korrektur 104-8): fehlt ERP_ENV, bleibt Secure -- bis 1.8.106 "False"; weitere Fälle in test_v412
    ({"ERP_ENV": "development"}, "False"),
    ({"ERP_COOKIE_SECURE": "1"}, "True"),
])
def test_secure_in_produktion_ohne_schalter(env, soll):
    assert _cookie_secure(**env) == soll


def test_mit_secure_tragen_anmelde_und_geraete_cookie_das_flag(welt, monkeypatch):
    app, _ = welt
    monkeypatch.setattr("app.sitzungen.COOKIE_SECURE", True)
    monkeypatch.setattr("app.routers.account.COOKIE_SECURE", True)
    antwort = _client(app, angemeldet=False).post("/api/auth/login", json={"username": "bea", "password": PASSWORT},
                                                   headers=EIGENE_SEITE)
    zeile = next(z for z in antwort.headers.get_list("set-cookie") if z.startswith(COOKIE_NAME + "="))
    assert "secure" in [t.strip().lower() for t in zeile.split(";")]
