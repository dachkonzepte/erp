"""Version 1.8.130 -- Runde 1d: ohne Konto geschlossen, Akzentfarbe nur für Administratoren, PWA-Symbole öffentlich.

Bis 1.8.129 ließ die Anmeldeschranke ohne Konto jede Anfrage durch (Befund Ersteinrichtung, 1.8.129): wer den Server erreichte, legte über
POST /api/users das erste Konto an, immer als Admin, und sah jede Seite und jede API ohne Rollenprüfung. Seit 1.8.130 hält die Schranke
die App bis zum ersten Konto geschlossen: durch gehen nur /health (GET, HEAD) und die Design-Dateien, eine Seite zeigt den Hinweis mit dem
Befehl (scripts/erstes_konto.py), alles andere bekommt 503 -- eine schreibende Anfrage von fremder Seite wie immer vorher 403.

    Entscheidung    ersteinrichtung_antwort(): /health frei, Seiten 503 mit dem Befehl, sonst 503 als JSON; has_users öffnet nichts mehr
    Angriffe        ohne Konto gegen einen echten uvicorn (h11 und httptools): jede Methode auf Seiten, API, Anmeldung, Benutzer anlegen,
                    Manifest, PWA-Symbol, Doku, Zähl-Routen und fehlende Pfade -- nur /health und die Design-Datei antworten von
                    dahinter, kein Endpunkt erreicht, kein Konto entsteht
    Endpunkte       POST /api/users nur Admin, /users ab Büro -- auch ohne Schranke ohne Ausnahme für die Ersteinrichtung
    Gegenprobe      mit der Schranke von 1.8.129 erreichen die Angriffe Endpunkte und Seiten
    PWA-Symbole     /api/mobile-icon/<192|512>.png ohne Anmeldung mit GET und HEAD (wie /manifest.json), jede andere Methode und
                    jede andere Größe 401; jedes Symbol des Manifests ist öffentlich
    Akzentfarbe     PUT /api/settings/appearance nur Admin (Büro 403), die Felder der Einstellungsseite nur für Admin
    Skript          scripts/erstes_konto.py: legt das erste Konto als Admin an, Passwort verdeckt (nie als Argument), nichts neben einem
                    vorhandenen Konto, ohne DATABASE_URL oder Terminal Abbruch
"""

from __future__ import annotations

import ast
import html
import http.client
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import anmeldeschranke, design_dateien
from app.anmeldeschranke import (ERSTEINRICHTUNG_BEFEHL, LESEND, OEFFENTLICH, _page_requires_login, _request_requires_login,
                                 ersteinrichtung_antwort)
from app.auth import COOKIE_NAME, verify_password
from app.database import get_db
from app.design_dateien import STATIC_DIR
from app.mobile_manifest import ICON_SIZES
from tests.anmeldung import EIGENE_SEITE, app_mit_schranke, browser_client, neue_datenbank
from tests.test_v433_schranke_alle_methoden import _uvicorn

ROOT = Path(__file__).resolve().parent.parent
SKRIPT = ROOT / "scripts" / "erstes_konto.py"
ALLE = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "FOO"]
SCHREIBEND = {"POST", "PUT", "PATCH", "DELETE"}


# ---------------------------------------------------------------------------
# Entscheidung
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("methode", ["GET", "HEAD"])
def test_health_bleibt_frei(methode):
    assert ersteinrichtung_antwort(methode, "/health") is None


@pytest.mark.parametrize("methode", ALLE)
@pytest.mark.parametrize("pfad", ["/", "/login", "/users", "/projects", "/manifest.json", "/gibt-es-nicht", "/health"])
def test_seiten_zeigen_den_befehl_sonst_503(methode, pfad):
    antwort = ersteinrichtung_antwort(methode, pfad)
    if pfad == "/health" and methode in LESEND:
        assert antwort is None
        return
    assert antwort.status_code == 503 and antwort.headers["cache-control"] == "no-store"
    if methode in LESEND:
        # der Befehl als Text: <benutzername> roh im HTML wäre ein unbekanntes Element, unsichtbar
        assert antwort.media_type == "text/html" and html.escape(ERSTEINRICHTUNG_BEFEHL) in antwort.body.decode()
        assert ERSTEINRICHTUNG_BEFEHL not in antwort.body.decode()
    else:
        assert json.loads(antwort.body)["ersteinrichtung"] is True


@pytest.mark.parametrize("methode", ALLE)
@pytest.mark.parametrize("pfad", ["/api/users", "/api/auth/status", "/api/auth/login", "/api/customers", "/api/mobile-icon/192.png",
                                  "/api/gibt-es-nicht"])
def test_api_ohne_konto_503_als_json(methode, pfad):
    antwort = ersteinrichtung_antwort(methode, pfad)
    assert antwort.status_code == 503 and json.loads(antwort.body)["ersteinrichtung"] is True


@pytest.mark.parametrize("methode", ALLE)
@pytest.mark.parametrize("pfad", ["/api/users", "/users", "/projects", "/api/customers", "/login", "/api/auth/login", "/gibt-es-nicht"])
def test_has_users_oeffnet_nichts_mehr(methode, pfad):
    """Bis 1.8.129 gab has_users=False jede Anfrage frei; jetzt entscheiden beide Funktionen ohne Konto wie mit."""
    assert _request_requires_login(False, methode, pfad) is _request_requires_login(True, methode, pfad)
    assert _page_requires_login(False, methode, pfad) is _page_requires_login(True, methode, pfad)


def test_die_seite_traegt_das_design_system_und_keinen_inhalt_aus_der_anfrage():
    text = ersteinrichtung_antwort("GET", "/<script>alert(1)</script>").body.decode()
    assert '<link rel="stylesheet" href="/static/ds/ds.css?v=' in text and "<script>alert" not in text and 'lang="de"' in text


# ---------------------------------------------------------------------------
# Angriffe ohne Konto gegen einen echten uvicorn
# ---------------------------------------------------------------------------

ERREICHT: list[str] = []
zaehl_router = APIRouter()


@zaehl_router.api_route("/zaehl/seite", methods=ALLE, include_in_schema=False)
@zaehl_router.api_route("/api/zaehl", methods=ALLE, include_in_schema=False)
def zaehl_endpunkt(request: Request):
    """Nimmt jede Methode an -- erreicht eine Anfrage ohne Konto diesen Endpunkt, steht sie in ERREICHT."""
    ERREICHT.append(f"{request.method} {request.url.path}")
    return JSONResponse({"erreicht": True})


@pytest.fixture(scope="module")
def leer():
    """Echte Schranke ohne ein einziges Konto, mit den Routern der Ersteinrichtung (Benutzer, Anmeldung, Seiten, Manifest/Symbole), den
    Kunden, den Zähl-Routen und den Design-Dateien."""
    from app.routers import auth, customers, field_view, pages, users

    engine, make_session = neue_datenbank()
    app = app_mit_schranke(make_session, pages.router, users.router, auth.router, field_view.router, customers.router, zaehl_router)
    design_dateien.einbinden(app, STATIC_DIR)
    yield {"app": app, "make_session": make_session}
    engine.dispose()


PFADE = {"health": "/health", "design": "/static/ds/ds.css", "Anmeldeseite": "/login", "Benutzerseite": "/users",
         "Seite": "/projects", "Start": "/", "Manifest": "/manifest.json", "Symbol": "/api/mobile-icon/192.png",
         "Status": "/api/auth/status", "Anmelden": "/api/auth/login", "Abmelden": "/api/auth/logout", "Konto anlegen": "/api/users",
         "API": "/api/customers", "Zähl-Seite": "/zaehl/seite", "Zähl-API": "/api/zaehl", "Doku": "/openapi.json",
         "fehlt": "/gibt-es-nicht", "API fehlt": "/api/gibt-es-nicht"}
DURCH = {("GET", "health"), ("HEAD", "health"), ("GET", "design"), ("HEAD", "design")}
KONTO = json.dumps({"username": "mallory", "password": "geheim-genug", "display_name": "Mallory", "role": "admin"}).encode()


def _anfrage(port: int, methode: str, pfad: str, kopf: dict, koerper: bytes = b"") -> tuple[int, dict, bytes]:
    verbindung = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        verbindung.putrequest(methode, pfad, skip_host=True, skip_accept_encoding=True)
        verbindung.putheader("Host", "testserver")
        for k, v in kopf.items():
            verbindung.putheader(k, v)
        if koerper:
            verbindung.putheader("Content-Type", "application/json")
        verbindung.putheader("Content-Length", str(len(koerper)))
        verbindung.endheaders(koerper or None)
        antwort = verbindung.getresponse()
        return antwort.status, {k.lower(): v for k, v in antwort.getheaders()}, antwort.read()
    finally:
        verbindung.close()


def _wer(status: int, kopf: dict, koerper: bytes, methode: str) -> str | None:
    """"ersteinrichtung" (503 der Schranke: Seite mit dem Befehl bzw. JSON mit ersteinrichtung=true; bei HEAD ohne Körper am Typ
    erkannt), "ursprung" (403), "server" (400 vom HTTP-Parser); None: die Antwort kam von dahinter."""
    if status == 503 and kopf.get("cache-control") == "no-store":
        typ = kopf.get("content-type", "")
        if methode == "HEAD":
            return "ersteinrichtung" if typ.startswith(("text/html", "application/json")) else None
        if typ.startswith("text/html") and html.escape(ERSTEINRICHTUNG_BEFEHL).encode() in koerper:
            return "ersteinrichtung"
        if typ.startswith("application/json") and json.loads(koerper).get("ersteinrichtung") is True:
            return "ersteinrichtung"
        return None
    if status == 403:
        return "ursprung"
    if status == 400:
        return "server"
    return None


def angriffe(port: int) -> list[tuple[str, str, dict, int, dict, str | None]]:
    """[(Methode, Art, Kopf, Status, Antwortkopf, wer)] für jede Methode und jeden Pfad, je ohne und mit Kopfzeilen der eigenen Seite;
    POST auf /api/users mit einem vollständigen Konto."""
    ergebnisse = []
    for methode in ALLE:
        for art, pfad in PFADE.items():
            for kopf in ({}, EIGENE_SEITE):
                koerper = KONTO if (methode, art) == ("POST", "Konto anlegen") else b""
                status, antwort_kopf, inhalt = _anfrage(port, methode, pfad, kopf, koerper)
                ergebnisse.append((methode, art, kopf, status, antwort_kopf, _wer(status, antwort_kopf, inhalt, methode)))
    return ergebnisse


def _angriffe_mit_server(app, http_art):
    server, faden, port = _uvicorn(app, http_art)
    try:
        ERREICHT.clear()
        return angriffe(port), list(ERREICHT)
    finally:
        server.should_exit = True
        faden.join(15)


def _konten(make_session) -> int:
    from app.models import AppUser

    with make_session() as db:
        return db.scalar(select(func.count(AppUser.id)))


@pytest.mark.parametrize("http_art", ["h11", "httptools"])
def test_ohne_konto_kommt_nur_health_und_design_durch(leer, http_art):
    pytest.importorskip(http_art)
    ergebnisse, erreicht = _angriffe_mit_server(leer["app"], http_art)
    assert erreicht == [], "Endpunkt ohne Konto erreicht"
    assert _konten(leer["make_session"]) == 0, "Konto ohne Befehl angelegt"
    for methode, art, kopf, status, antwort_kopf, wer in ergebnisse:
        if (methode, art) in DURCH:
            assert status == 200 and wer is None, (methode, art, status)
        elif wer == "server":
            assert http_art == "httptools" and methode == "FOO", (methode, art, status)
        elif methode in SCHREIBEND and not kopf:
            assert wer == "ursprung", (methode, art, status)  # von fremder Seite wie immer 403, vor allem anderen
        else:
            assert wer == "ersteinrichtung", (methode, art, kopf, status)
            erwartet = "text/html" if methode in LESEND and not PFADE[art].startswith("/api/") else "application/json"
            assert antwort_kopf["content-type"].startswith(erwartet), (methode, art, antwort_kopf["content-type"])


def test_die_design_datei_ist_wirklich_die_datei(leer):
    """Gegenstück zu DURCH: die Design-Datei kommt aus app/static/ (nicht nur irgendein 200)."""
    server, faden, port = _uvicorn(leer["app"], "h11")
    try:
        status, kopf, inhalt = _anfrage(port, "GET", "/static/ds/ds.css", {})
        assert status == 200 and kopf["content-type"].startswith("text/css") and inhalt == (STATIC_DIR / "ds" / "ds.css").read_bytes()
        status, kopf, inhalt = _anfrage(port, "GET", "/health", {})
        assert status == 200 and json.loads(inhalt)
    finally:
        server.should_exit = True
        faden.join(15)


# Gegenprobe: die Regeln von 1.8.129 (wörtlich), eingesetzt in die echte Schranke, ohne die Antwort der Ersteinrichtung

def _alt_request_requires_login(has_users, method, path):
    if not has_users or anmeldeschranke._oeffentlich(method, path):
        return False
    if path.startswith("/api/"):
        return True
    return method not in LESEND


def _alt_page_requires_login(has_users, method, path):
    if not has_users or method not in LESEND or path.startswith("/api/"):
        return False
    return path not in anmeldeschranke._PUBLIC_PAGE_PATHS


def test_gegenprobe_mit_der_schranke_von_1_8_129(leer, monkeypatch):
    monkeypatch.setattr(anmeldeschranke, "ersteinrichtung_antwort", lambda method, path: None)
    monkeypatch.setattr(anmeldeschranke, "_request_requires_login", _alt_request_requires_login)
    monkeypatch.setattr(anmeldeschranke, "_page_requires_login", _alt_page_requires_login)
    ergebnisse, erreicht = _angriffe_mit_server(leer["app"], "h11")
    vorbei = {(m, art) for m, art, kopf, status, _, wer in ergebnisse if wer is None and kopf}
    assert {"GET /zaehl/seite", "HEAD /api/zaehl", "OPTIONS /api/zaehl", "POST /api/zaehl"} <= set(erreicht), erreicht
    # ohne Konto kam bis 1.8.129 alles bis zum Endpunkt; Seiten und API mit Rollenprüfung antworteten dort 403 (kein erp_user), die
    # übrigen von dahinter
    assert {("GET", "Status"), ("GET", "Doku"), ("GET", "Manifest"), ("GET", "Zähl-Seite"), ("GET", "fehlt"), ("HEAD", "API fehlt")} <= vorbei
    # das Konto anlegen gelingt auch mit der alten Schranke nicht mehr: der Endpunkt verlangt seit 1.8.130 selbst einen Admin
    assert any(m == "POST" and art == "Konto anlegen" and status == 403 for m, art, kopf, status, _, _ in ergebnisse if kopf)
    assert _konten(leer["make_session"]) == 0


# ---------------------------------------------------------------------------
# Endpunkte ohne Ausnahme für die Ersteinrichtung (auch ohne Schranke)
# ---------------------------------------------------------------------------

@pytest.fixture()
def ohne_schranke():
    """Benutzer- und Seiten-Router ohne Schranke und ohne Konto: kein erp_user -- so wie die Endpunkte bis 1.8.129 die offene
    Ersteinrichtung sahen."""
    from app.routers import pages, users

    engine, make_session = neue_datenbank()
    app = FastAPI()
    app.include_router(users.router)
    app.include_router(pages.router)

    def _db():
        db = make_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    yield TestClient(app), make_session
    engine.dispose()


def test_konto_anlegen_nur_als_admin_auch_ohne_konto(ohne_schranke):
    client, make_session = ohne_schranke
    antwort = client.post("/api/users", content=KONTO, headers={"Content-Type": "application/json"})
    assert antwort.status_code == 403 and _konten(make_session) == 0


def test_benutzerseite_ohne_ausnahme(ohne_schranke):
    client, _ = ohne_schranke
    assert client.get("/users").status_code == 403


def test_benutzerseite_und_konto_anlegen_mit_rollen():
    """Mit Schranke: /users ab Büro – Auftrag, POST /api/users nur Admin (Büro – Finanzen 403), Admin legt mit der gewählten Rolle an."""
    from app.models import AppUser
    from app.routers import pages, users
    from app.sitzungen import neue_sitzung

    engine, make_session = neue_datenbank()
    cookies = {}
    with make_session() as db:
        for name, rolle in (("ada", "admin"), ("bernd", "buero_finanzen"), ("berta", "buero_auftrag"), ("mia", "field")):
            nutzer = AppUser(username=name, display_name=name.title(), role=rolle, password_hash="x")
            db.add(nutzer)
            db.flush()
            cookies[name] = neue_sitzung(db, nutzer, zweiter_faktor=True)
        db.commit()
    client = browser_client(app_mit_schranke(make_session, pages.router, users.router), follow_redirects=False)
    try:
        # seit 1.8.134 /users nur für Administratoren (bis dahin ab Büro – Auftrag)
        for name, erwartet in (("ada", 200), ("bernd", 403), ("berta", 403), ("mia", 403)):
            client.cookies.set(COOKIE_NAME, cookies[name], domain="testserver.local")
            assert client.get("/users").status_code == erwartet, name
        for name in ("bernd", "berta", "mia"):
            client.cookies.set(COOKIE_NAME, cookies[name], domain="testserver.local")
            assert client.post("/api/users", json={"username": f"neu-{name}", "password": "geheim-genug", "display_name": "Neu",
                                                   "role": "admin"}).status_code == 403, name
        client.cookies.set(COOKIE_NAME, cookies["ada"], domain="testserver.local")
        antwort = client.post("/api/users", json={"username": "neu", "password": "geheim-genug", "display_name": "Neu", "role": "field"})
        assert antwort.status_code == 200 and antwort.json()["role"] == "field"
        assert _konten(make_session) == 5
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# PWA-Symbole öffentlich wie /manifest.json
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mit_konto():
    from app.models import AppUser
    from app.routers import field_view, settings
    from app.sitzungen import neue_sitzung

    engine, make_session = neue_datenbank()
    cookies = {}
    with make_session() as db:
        for name, rolle in (("ada", "admin"), ("bernd", "buero_finanzen"), ("berta", "buero_auftrag"), ("mia", "field")):
            nutzer = AppUser(username=name, display_name=name.title(), role=rolle, password_hash="x")
            db.add(nutzer)
            db.flush()
            cookies[name] = neue_sitzung(db, nutzer, zweiter_faktor=True)
        db.commit()
    from app.routers import pages
    app = app_mit_schranke(make_session, field_view.router, settings.router, pages.router)
    yield {"app": app, "cookies": cookies, "make_session": make_session}
    engine.dispose()


def _client(welt, name: str | None = None) -> TestClient:
    client = browser_client(welt["app"], follow_redirects=False)
    if name:
        client.cookies.set(COOKIE_NAME, welt["cookies"][name], domain="testserver.local")
    return client


@pytest.mark.parametrize("groesse", ICON_SIZES)
def test_symbol_ohne_anmeldung_mit_get_und_head(mit_konto, groesse):
    client = _client(mit_konto)
    antwort = client.get(f"/api/mobile-icon/{groesse}.png")
    assert antwort.status_code == 200 and antwort.headers["content-type"] == "image/png" and antwort.content.startswith(b"\x89PNG")
    kopf = client.head(f"/api/mobile-icon/{groesse}.png")
    assert kopf.status_code == 200 and kopf.headers["content-type"] == "image/png" and kopf.content == b""


@pytest.mark.parametrize("methode", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"])
def test_symbol_andere_methoden_brauchen_die_anmeldung(mit_konto, methode):
    assert _client(mit_konto).request(methode, "/api/mobile-icon/192.png").status_code == 401


@pytest.mark.parametrize("pfad", ["/api/mobile-icon/64.png", "/api/mobile-icon/0192.png", "/api/mobile-icon/192.PNG",
                                  "/api/mobile-icon/192.png/x", "/api/mobile-icon/512.gif"])
def test_andere_groessen_brauchen_die_anmeldung(mit_konto, pfad):
    assert _client(mit_konto).get(pfad).status_code == 401


def test_jedes_symbol_des_manifests_ist_oeffentlich(mit_konto):
    manifest = _client(mit_konto).get("/manifest.json").json()
    quellen = [symbol["src"] for symbol in manifest["icons"]]
    assert len(quellen) == len(ICON_SIZES)
    for quelle in quellen:
        assert anmeldeschranke._oeffentlich("GET", quelle) and anmeldeschranke._oeffentlich("HEAD", quelle), quelle


def test_symbol_gegenprobe_ohne_eintrag(mit_konto, monkeypatch):
    monkeypatch.setattr(anmeldeschranke, "OEFFENTLICH", {k: v for k, v in OEFFENTLICH.items() if "mobile-icon" not in k})
    assert _client(mit_konto).get("/api/mobile-icon/192.png").status_code == 401


# ---------------------------------------------------------------------------
# Akzentfarbe nur für Administratoren
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["bernd", "berta", "mia"])
def test_akzentfarbe_aendert_nur_ein_admin(mit_konto, name):
    antwort = _client(mit_konto, name).put("/api/settings/appearance", json={"accent_color": "#123456"})
    assert antwort.status_code == 403 and "Administrator" in antwort.json()["detail"]


def test_admin_aendert_die_akzentfarbe_und_buero_liest_sie(mit_konto):
    admin = _client(mit_konto, "ada")
    vorher = admin.get("/api/settings/appearance").json()["accent_color"]
    try:
        assert admin.put("/api/settings/appearance", json={"accent_color": "#123456"}).status_code == 200
        assert _client(mit_konto, "berta").get("/api/settings/appearance").json() == {"accent_color": "#123456"}
    finally:
        admin.put("/api/settings/appearance", json={"accent_color": vorher})


@pytest.mark.parametrize("name,sichtbar", [("ada", True), ("bernd", False), ("berta", False)])
def test_einstellungsseite_zeigt_die_akzentfarbe_nur_dem_admin(mit_konto, name, sichtbar):
    text = _client(mit_konto, name).get("/settings").text
    assert ('id="accentColorPicker"' in text) is sichtbar and ('onclick="saveAccentColor()"' in text) is sichtbar
    for stelle in (">Akzentfarbe</h3>", ", Akzentfarbe</span>", "Logos und Akzentfarbe stehen", "Logo der Seitenleiste und Akzentfarbe"):
        assert (stelle in text) is sichtbar, stelle
    # die Listener der Felder und das Laden hängen am Admin -- sonst bräche das Seitenskript ohne die Felder ab
    assert "if(istAdmin){  // seit 1.8.130" in text and "if(istAdmin)loadAppearance();" in text


# ---------------------------------------------------------------------------
# scripts/erstes_konto.py
# ---------------------------------------------------------------------------

def _skript():
    spec = importlib.util.spec_from_file_location("erstes_konto_test", SKRIPT)
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


class Eingaben:
    def __init__(self, *werte):
        self.werte, self.fragen = list(werte), []

    def __call__(self, frage):
        self.fragen.append(frage)
        return self.werte.pop(0)


@pytest.fixture()
def skript_db():
    engine, make_session = neue_datenbank()
    db = make_session()
    yield db
    db.close()
    engine.dispose()


def _lauf(db, argv, *eingaben):
    zeilen, eingabe = [], Eingaben(*eingaben)
    rc = _skript().main(argv, eingabe=eingabe, sitzung=db, ausgabe=zeilen.append)
    return rc, "\n".join(zeilen), eingabe


def test_skript_legt_das_erste_konto_als_admin_an(skript_db):
    from app.models import AppUser

    rc, text, eingabe = _lauf(skript_db, ["ada", "--anzeigename", "Ada Admin"], "geheim-genug", "geheim-genug")
    assert rc == 0 and "angelegt" in text and "geheim-genug" not in text
    assert len(eingabe.fragen) == 2
    nutzer = skript_db.scalars(select(AppUser)).all()
    assert [(n.username, n.display_name, n.role, n.active) for n in nutzer] == [("ada", "Ada Admin", "admin", True)]
    assert verify_password("geheim-genug", nutzer[0].password_hash)


def test_skript_legt_nichts_neben_einem_konto_an(skript_db):
    _lauf(skript_db, ["ada"], "geheim-genug", "geheim-genug")
    rc, text, eingabe = _lauf(skript_db, ["bea"], "noch-geheimer", "noch-geheimer")
    assert rc == 1 and "schon ein ERP-Konto" in text and eingabe.fragen == []  # nicht einmal nach dem Passwort gefragt
    assert _anzahl(skript_db) == 1


def _anzahl(db) -> int:
    from app.models import AppUser

    return db.scalar(select(func.count(AppUser.id)))


@pytest.mark.parametrize("argv,eingaben,meldung", [
    (["ada"], ("geheim-genug", "geheim-genuG"), "stimmen nicht überein"),
    (["ada"], ("kurz123", "kurz123"), "Passwort: mindestens 8 Zeichen"),
    (["ab"], ("geheim-genug", "geheim-genug"), "Benutzername: mindestens 3 Zeichen"),
    (["ada", "--anzeigename", "  "], ("geheim-genug", "geheim-genug"), "Anzeigename: mindestens 1 Zeichen"),
])
def test_skript_ungueltige_eingaben_legen_nichts_an(skript_db, argv, eingaben, meldung):
    rc, text, _ = _lauf(skript_db, argv, *eingaben)
    assert rc == 1 and meldung in text and "nichts angelegt" in text
    assert all(wert not in text for wert in eingaben)
    assert _anzahl(skript_db) == 0


def test_skript_ohne_database_url_bricht_ab():
    zeilen, eingabe = [], Eingaben()
    rc = _skript().main(["ada"], eingabe=eingabe, umgebung={}, ausgabe=zeilen.append)
    assert rc == 2 and "DATABASE_URL ist nicht gesetzt" in zeilen[0] and eingabe.fragen == []


def test_skript_ohne_terminal_bricht_ab(monkeypatch):
    class KeinTerminal:
        def isatty(self):
            return False

    from tests.pg_schutz import pg_url_pruefen

    monkeypatch.setattr(sys, "stdin", KeinTerminal())
    zeilen = []
    rc = _skript().main(["ada"], umgebung={"DATABASE_URL": pg_url_pruefen("sqlite://")}, ausgabe=zeilen.append)
    assert rc == 2 and "Kein Terminal" in zeilen[0]


@pytest.mark.parametrize("argv", [["ada", "geheim-genug"], ["ada", "--passwort", "geheim-genug"], ["ada", "--password=geheim-genug"],
                                  ["ada", "-p", "geheim-genug"]])
def test_skript_nimmt_kein_passwort_als_argument(argv):
    with pytest.raises(SystemExit) as fehler:
        _skript().main(argv, eingabe=Eingaben(), umgebung={})
    assert fehler.value.code == 2


def test_skript_fragt_verdeckt_und_kennt_kein_passwort_argument():
    baum = ast.parse(SKRIPT.read_text(encoding="utf-8"))
    argumente = [ast.literal_eval(a) for knoten in ast.walk(baum) if isinstance(knoten, ast.Call)
                 and getattr(knoten.func, "attr", None) == "add_argument" for a in knoten.args]
    assert argumente == ["benutzername", "--anzeigename"]
    assert any(isinstance(k, ast.Attribute) and k.attr == "getpass" and getattr(k.value, "id", None) == "getpass" for k in ast.walk(baum))
    assert "input(" not in SKRIPT.read_text(encoding="utf-8")


def test_skript_als_prozess_ohne_terminal(tmp_path):
    """Als echter Prozess, die Eingabe aus einer Pipe: kein Terminal -- Abbruch, bevor gefragt oder die Datenbank geöffnet wird."""
    from tests.pg_schutz import pg_url_pruefen

    env = {k: v for k, v in os.environ.items() if not k.startswith("ERP_") and k != "DATABASE_URL"}
    env.update({"DATABASE_URL": pg_url_pruefen("sqlite:///" + (tmp_path / "erp.db").as_posix()), "ERP_DATA_DIR": str(tmp_path / "data"),
                "PYTHONIOENCODING": "utf-8"})
    lauf = subprocess.run([sys.executable, str(SKRIPT), "ada"], input="geheim-genug\ngeheim-genug\n", capture_output=True, text=True,
                          encoding="utf-8", env=env, cwd=tmp_path, timeout=60)
    assert lauf.returncode == 2 and "Kein Terminal" in lauf.stdout, (lauf.stdout, lauf.stderr)
    assert not (tmp_path / "erp.db").exists()
    del env["DATABASE_URL"]
    lauf = subprocess.run([sys.executable, str(SKRIPT), "ada"], capture_output=True, text=True, encoding="utf-8", env=env, cwd=tmp_path,
                          timeout=60, stdin=subprocess.DEVNULL)
    assert lauf.returncode == 2 and "DATABASE_URL ist nicht gesetzt" in lauf.stdout, (lauf.stdout, lauf.stderr)
