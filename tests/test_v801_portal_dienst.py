"""Version 1.11.2 (Stufe P1b): der Portal-Dienst ohne Oberfläche -- App, Schranke, Startprüfung, öffentliche Wege, Server-Dateien.

    Wege          nur die des Portals; jeder genau in OEFFENTLICH, VORSTUFE oder SITZUNG; jeder Pfad des ERP 404; keine Schnittstellen-Doku
    Schranke      Host nur der eigene (421), Methoden nur GET/HEAD/POST (405 mit Allow), Körper höchstens 16 KB (413, auch ohne Content-Length),
                  schreibend nur same-origin bzw. passende Origin (403) -- auch gegen einen echten uvicorn (h11, httptools) mit rohen Anfragen
    Kopfzeilen    an jeder Antwort (200, 404, 405, 421, 403, 413, 422, 500, 503): CSP ohne Inline-Skript mit Trusted Types, kein Einrahmen, nosniff,
                  no-referrer, COOP/CORP, Permissions-Policy, no-store; HSTS außer lokal und in Tests
    Fehler        500 ohne jedes Detail, im Protokoll nur die Klasse; 503 bei leerem Pool
    Einstellungen aus der Umgebung streng geprüft, keine Meldung nennt einen Wert; Startprüfung: PostgreSQL, Revision = Kopf (sonst kein Start)
    Tabellen      die Core-Tabellen des Portals = rechte.LESEN, Typen wie im Modell
    Server        erp-portal.service, nginx-kunde.conf, portal.env.beispiel wie im Bauplan; gunicorn in requirements.txt
"""

import http.client
import logging
import os
import socket
import threading
import time
import uuid
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, text
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.portal import rechte, routen, tabellen
from app.portal.einstellungen import Einstellungen, EinstellungFalsch, aus_umgebung
from app.portal.main import erzeugen, kopf_der_migrationen, startpruefung
from app.portal.datenbank import Datenbank

ROOT = Path(__file__).resolve().parent.parent
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
HERKUNFT = "https://kunde.test"
EIGEN = {"Sec-Fetch-Site": "same-origin"}
SCHUTZ = ("content-security-policy", "x-frame-options", "x-content-type-options", "referrer-policy", "cross-origin-opener-policy",
          "cross-origin-resource-policy", "permissions-policy")


def _einstellungen(**anders) -> Einstellungen:
    return Einstellungen(**{"datenbank_url": "postgresql+psycopg://unbenutzt", "herkunft": HERKUNFT, "bremse_schluessel": b"k" * 32,
                            "umgebung": "test", **anders})


@pytest.fixture
def dienst():
    """Der Dienst über einer SQLite-Datenbank mit den Firmendaten (für Schranke und öffentliche Wege braucht es keine Funktionen)."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    tabellen.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(insert(tabellen.general_settings).values(id=1, company_name="Muster Bedachung GmbH", street="Dachweg 1", postal_code="12345",
                                                           city="Musterstadt", phone="01234 5678", email="info@example.invalid",
                                                           website="https://example.invalid"))
    app = erzeugen(_einstellungen(), engine=engine, pruefen=False)
    with TestClient(app, base_url=HERKUNFT) as client:
        yield client, app
    engine.dispose()


def _fastapi(app):
    return app.app  # die Schranke hält die FastAPI-App


def _portal_pfade() -> set[str]:
    """Die Wege aus routen.router -- in app.routes stehen eingebundene Router als _IncludedRouter, eine flache Suche fände keine Route."""
    return {r.path for r in routen.router.routes if isinstance(r, APIRoute)}


# --- Wege ----------------------------------------------------------------------------------------------------------------------------------------

def test_jeder_weg_in_genau_einer_liste(dienst):
    _client, _app = dienst
    pfade = _portal_pfade()
    listen = [routen.OEFFENTLICH, routen.VORSTUFE, routen.SITZUNG]
    assert pfade == set().union(*listen)
    assert sum(len(x) for x in listen) == len(pfade)  # keine doppelt


def test_kein_weg_des_erp_und_keine_doku(dienst):
    client, app = dienst
    from tests.test_v326_monteur_datengrenze import _routers_in_betriebsreihenfolge
    pfade = sorted({r.path for router in _routers_in_betriebsreihenfolge() for r in router.routes if isinstance(r, APIRoute)})
    assert len(pfade) > 400
    portal = routen.OEFFENTLICH | routen.VORSTUFE | routen.SITZUNG  # die erklärten Wege -- ein Weg nur im Router wird geprüft wie jeder andere
    erreicht = []
    for pfad in pfade:
        if pfad in portal:
            continue
        konkret = pfad.replace("{", "").replace("}", "").replace("_id", "").replace(":path", "")
        for methode in ("GET", "POST"):
            r = client.request(methode, konkret, headers=EIGEN)
            if r.status_code != 404:
                erreicht.append(f"{methode} {pfad}: {r.status_code}")
    assert erreicht == []
    for pfad in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
        assert client.get(pfad).status_code == 404


# --- Schranke ------------------------------------------------------------------------------------------------------------------------------------

def _schutz(r, hsts=False):
    fehlt = [k for k in SCHUTZ if k not in r.headers]
    assert fehlt == [], fehlt
    assert "script-src 'self'" in r.headers["content-security-policy"] and "'unsafe-inline'" not in r.headers["content-security-policy"]
    assert "require-trusted-types-for 'script'" in r.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"
    assert ("strict-transport-security" in r.headers) is hsts


@pytest.mark.parametrize("host", ["app.dachkonzepte.gmbh", "kunde.test.evil", "KUNDE.TEST.", "127.0.0.1", ""])
def test_fremder_host_421(dienst, host):
    client, _ = dienst
    r = client.get("/health", headers={"Host": host})
    assert (r.status_code, r.json()) == (421, {"fehler": "host"})
    _schutz(r)


@pytest.mark.parametrize("methode", ["PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "PROPFIND", "ERFUNDEN"])
@pytest.mark.parametrize("pfad", ["/health", "/api/kontakt", "/gibt-es-nicht"])
def test_methoden_ausser_get_head_post_405(dienst, methode, pfad):
    client, _ = dienst
    r = client.request(methode, pfad, headers=EIGEN)
    assert (r.status_code, r.headers.get("allow")) == (405, "GET, HEAD, POST")
    _schutz(r)


@pytest.mark.parametrize("kopf, erlaubt", [
    ({"Sec-Fetch-Site": "same-origin"}, True), ({"Sec-Fetch-Site": "same-site"}, False), ({"Sec-Fetch-Site": "cross-site"}, False),
    ({"Sec-Fetch-Site": "none"}, False), ({"Origin": HERKUNFT}, True), ({"Origin": "https://app.dachkonzepte.gmbh"}, False),
    ({"Origin": "null"}, False), ({"Origin": "https://kunde.test.evil"}, False), ({}, False),
    ({"Sec-Fetch-Site": "cross-site", "Origin": HERKUNFT}, False),
])
def test_schreibend_nur_von_der_eigenen_seite(dienst, kopf, erlaubt):
    client, _ = dienst
    r = client.post("/gibt-es-nicht", headers=kopf)
    assert r.status_code == (404 if erlaubt else 403)
    if not erlaubt:
        assert r.json() == {"fehler": "herkunft"}
    _schutz(r)


def test_koerper_hoechstens_16_kb(dienst):
    client, _ = dienst
    assert client.post("/gibt-es-nicht", headers=EIGEN, content=b"x" * 16384).status_code == 404
    r = client.post("/gibt-es-nicht", headers=EIGEN, content=b"x" * 16385)
    assert (r.status_code, r.json()) == (413, {"fehler": "zu_gross"})
    _schutz(r)

    def stueckweise():
        for _ in range(17):
            yield b"x" * 1024
    r = client.post("/gibt-es-nicht", headers=EIGEN, content=stueckweise())  # ohne Content-Length
    assert r.status_code == 413
    assert client.post("/gibt-es-nicht", headers={**EIGEN, "Content-Length": "abc"}, content=b"").status_code in (400, 413)


def test_kopfzeilen_an_jeder_antwort(dienst, monkeypatch):
    client, app = dienst
    for r in (client.get("/health"), client.get("/api/kontakt"), client.head("/health"), client.get("/gibt-es-nicht"),
              client.post("/health", headers=EIGEN), client.get("/api/kontakt?x=" + "y" * 10)):
        _schutz(r)
    db = _fastapi(app).state.db
    monkeypatch.setattr(db, "kontakt", lambda: (_ for _ in ()).throw(PoolTimeout("leer")))
    r = client.get("/api/kontakt")
    assert (r.status_code, r.json()) == (503, {"fehler": "ausgelastet"})
    _schutz(r)


def test_500_ohne_details_und_protokoll_nur_die_klasse(dienst, monkeypatch, caplog):
    client, app = dienst
    db = _fastapi(app).state.db
    monkeypatch.setattr(db, "kontakt", lambda: (_ for _ in ()).throw(RuntimeError("geheim-4711")))
    with caplog.at_level(logging.ERROR, logger="dk_portal"):
        r = client.get("/api/kontakt")
    assert (r.status_code, r.json()) == (500, {"fehler": "technisch"})
    assert "geheim" not in r.text
    _schutz(r)
    assert "RuntimeError" in caplog.text and "geheim" not in caplog.text


def test_hsts_nur_ausserhalb_von_test_und_entwicklung():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    tabellen.metadata.create_all(engine)
    for umgebung, hsts in (("production", True), ("development", False), ("test", False)):
        app = erzeugen(_einstellungen(umgebung=umgebung), engine=engine, pruefen=False)
        with TestClient(app, base_url=HERKUNFT) as client:
            _schutz(client.get("/health"), hsts=hsts)
            _schutz(client.get("/gibt-es-nicht", headers={"Host": "fremd"}), hsts=hsts)
    engine.dispose()


def test_pool_passt_zum_einen_arbeitsprozess():
    """3 + 3 Verbindungen, 10 Sekunden warten (dann 503), Vorprüfung jeder Verbindung -- die Rolle erlaubt höchstens 10 (Bauplan P1, 1.4)."""
    from app.portal.datenbank import engine_erzeugen
    engine = engine_erzeugen("postgresql+psycopg://dkportal@127.0.0.1:5432/dachkonzepte")  # verbindet noch nicht
    try:
        assert (engine.pool.size(), engine.pool._max_overflow, engine.pool._timeout, engine.pool._pre_ping) == (3, 3, 10, True)
    finally:
        engine.dispose()


def test_lebensdauer_zehn_faeden(dienst):
    import anyio.to_thread
    client, _ = dienst
    assert client.portal.call(lambda: anyio.to_thread.current_default_thread_limiter().total_tokens) == 10


# --- öffentliche Wege -------------------------------------------------------------------------------------------------------------------------------

def test_health(dienst, monkeypatch):
    client, app = dienst
    assert (client.get("/health").status_code, client.get("/health").json()) == (200, {"ok": True})
    assert client.head("/health").status_code == 200
    monkeypatch.setattr(_fastapi(app).state.db, "erreichbar", lambda: (_ for _ in ()).throw(RuntimeError("weg")))
    assert (client.get("/health").status_code, client.get("/health").json()) == (503, {"ok": False})


def test_kontakt_genau_die_firmendaten(dienst):
    client, _ = dienst
    r = client.get("/api/kontakt")
    assert r.status_code == 200
    assert r.json() == {"firma": "Muster Bedachung GmbH", "strasse": "Dachweg 1", "plz": "12345", "ort": "Musterstadt", "telefon": "01234 5678",
                        "email": "info@example.invalid", "webseite": "https://example.invalid"}


# --- Einstellungen und Startprüfung -------------------------------------------------------------------------------------------------------------------

GUT = {"DATABASE_URL": "postgresql+psycopg://dkportal:pw-geheim@127.0.0.1:5432/dachkonzepte", "PORTAL_HERKUNFT": "https://kunde.dachkonzepte.gmbh",
       "PORTAL_BREMSE_SCHLUESSEL": "ab" * 32, "ERP_ENV": "production"}


def test_einstellungen_aus_der_umgebung():
    e = aus_umgebung(dict(GUT))
    assert (e.host, e.nur_https, e.bremse_schluessel) == ("kunde.dachkonzepte.gmbh", True, bytes.fromhex("ab" * 32))
    assert aus_umgebung({k: v for k, v in GUT.items() if k != "ERP_ENV"}).umgebung == "production"  # fehlt ERP_ENV: streng
    lokal = aus_umgebung({**GUT, "PORTAL_HERKUNFT": "http://localhost:8010", "ERP_ENV": "development"})
    assert (lokal.host, lokal.nur_https) == ("localhost:8010", False)


# als Paare (Name, Inhalt): ein Wörterbuch mit dem Schlüssel DATABASE_URL in der Funktion hielte test_v384 für die Übergabe an einen Kindprozess
@pytest.mark.parametrize("name, inhalt", [
    ("DATABASE_URL", ""), ("DATABASE_URL", "sqlite:///erp.db"), ("PORTAL_HERKUNFT", ""), ("PORTAL_HERKUNFT", "http://kunde.dachkonzepte.gmbh"),
    ("PORTAL_HERKUNFT", "https://kunde.dachkonzepte.gmbh/pfad"), ("PORTAL_HERKUNFT", "https://nutzer:pw-geheim@kunde.dachkonzepte.gmbh"),
    ("PORTAL_HERKUNFT", "https://kunde.dachkonzepte.gmbh?x=1"), ("PORTAL_HERKUNFT", "http://localhost:8010"),
    ("PORTAL_BREMSE_SCHLUESSEL", ""), ("PORTAL_BREMSE_SCHLUESSEL", "ab" * 31), ("PORTAL_BREMSE_SCHLUESSEL", "zz" * 32),
    ("PORTAL_BREMSE_SCHLUESSEL", "abc"), ("ERP_ENV", "prod"),
])
def test_einstellung_falsch_kein_start_und_kein_wert_in_der_meldung(name, inhalt):
    umgebung = dict(GUT)
    umgebung[name] = inhalt
    with pytest.raises(EinstellungFalsch) as fehler:
        aus_umgebung(umgebung)
    for wert in ("pw-geheim", "ab" * 31, "zz" * 32):
        assert wert not in str(fehler.value)


def test_startpruefung_nur_postgresql():
    engine = create_engine("sqlite://")
    with pytest.raises(EinstellungFalsch, match="nur gegen PostgreSQL"):
        startpruefung(Datenbank(engine))
    engine.dispose()


@pytest.fixture
def pg_schema():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_pd_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
    erp = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        with erp.connect() as c:
            if c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = 'dkportal_test'")).first() is None:
                pytest.skip("Testrolle dkportal_test fehlt (siehe tests/test_v799_portal_rechte.py)")
        Base.metadata.create_all(erp)
        with erp.begin() as c:
            c.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
            c.execute(text("INSERT INTO alembic_version VALUES (:k)"), {"k": kopf_der_migrationen()})
            rechte.setzen(c, rolle="dkportal_test", schema=schema)
        portal = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema} -crole=dkportal_test", "application_name": schema})
        yield erp, portal, schema
        portal.dispose()
    finally:
        erp.dispose()
        with admin.begin() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_startpruefung_als_rolle_des_portals(pg_schema, caplog):
    erp, portal, _schema = pg_schema
    zeile = startpruefung(Datenbank(portal))
    assert zeile == f"Portal verbunden als dkportal_test, Revision {kopf_der_migrationen()}"
    with caplog.at_level(logging.WARNING, logger="dk_portal"):
        erzeugen(_einstellungen(), engine=portal)
    assert "Portal verbunden als dkportal_test" in caplog.text
    with erp.begin() as c:
        c.execute(text("UPDATE alembic_version SET version_num = 'alt123'"))
    with pytest.raises(EinstellungFalsch, match=f"Datenbank auf Revision alt123, der Code erwartet {kopf_der_migrationen()}"):
        erzeugen(_einstellungen(), engine=portal)


def test_kontakt_als_rolle_des_portals(pg_schema):
    _erp, portal, _schema = pg_schema
    app = erzeugen(_einstellungen(), engine=portal, pruefen=False)
    with TestClient(app, base_url=HERKUNFT) as client:
        r = client.get("/api/kontakt")
        assert r.status_code == 200 and set(r.json()) == {"firma", "strasse", "plz", "ort", "telefon", "email", "webseite"}
        assert client.get("/health").json() == {"ok": True}


def test_core_tabellen_genau_lesen():
    assert set(tabellen.metadata.tables) == set(rechte.LESEN)
    for name, tabelle in tabellen.metadata.tables.items():
        assert tuple(tabelle.columns.keys()) == rechte.LESEN[name], name
        if name in Base.metadata.tables:
            modell = Base.metadata.tables[name]
            for spalte in tabelle.columns:
                assert type(spalte.type) is type(modell.c[spalte.name].type), (name, spalte.name)
                assert getattr(spalte.type, "length", None) == getattr(modell.c[spalte.name].type, "length", None), (name, spalte.name)


# --- Server-Dateien und Abhängigkeiten ---------------------------------------------------------------------------------------------------------------

def test_einheit_des_dienstes():
    einheit = (ROOT / "scripts" / "server" / "erp-portal.service").read_text(encoding="utf-8")
    for zeile in ("User=dkportal", "Group=dkportal", "EnvironmentFile=/etc/dk-portal/portal.env", "ProtectHome=tmpfs", "ProtectSystem=strict",
                  "TemporaryFileSystem=/srv/erp-code", "BindReadOnlyPaths=/home/tobias/erp/app:/srv/erp-code/app",
                  "BindReadOnlyPaths=/home/tobias/erp/alembic:/srv/erp-code/alembic", "BindReadOnlyPaths=/home/tobias/erp/alembic.ini:/srv/erp-code/alembic.ini",
                  "BindReadOnlyPaths=/home/tobias/erp/.venv:/srv/erp-code/.venv", "MemoryHigh=200M", "MemoryMax=256M", "NoNewPrivileges=true",
                  "CapabilityBoundingSet=", "UMask=0077"):
        assert zeile + "\n" in einheit, zeile
    start = next(z for z in einheit.splitlines() if z.startswith("ExecStart="))
    assert start.startswith("ExecStart=/srv/erp-code/.venv/bin/python -m gunicorn 'app.portal.main:erzeugen()'")
    assert "--workers 1 " in start and "--bind 127.0.0.1:8010 " in start and "uvicorn.workers.UvicornWorker" in start
    assert "forwarded-allow-ips" not in einheit.replace("Kein --forwarded-allow-ips", "")  # E4: gunicorn vertraut nur 127.0.0.1
    assert "access-logfile" not in einheit  # kein Zugriffsprotokoll des Dienstes (keine Adressen im Journal)
    assert "--no-control-socket" in start.split()  # seit 1.11.22 kein Steuer-Socket (test_v803 prüft den Weg des Hauptprozesses)
    eingebunden = [z.split("=", 1)[1].split(":")[0] for z in einheit.splitlines() if z.startswith("BindReadOnlyPaths=")]
    assert sorted(eingebunden) == sorted(f"/home/tobias/erp/{x}" for x in ("app", "alembic", "alembic.ini", ".venv"))


def test_nginx_block():
    conf = (ROOT / "scripts" / "server" / "nginx-kunde.conf").read_text(encoding="utf-8")
    zeilen = [z.split("#")[0].strip() for z in conf.splitlines() if z.split("#")[0].strip()]
    log = next(z for z in zeilen if z.startswith("log_format"))
    assert "$remote_addr" not in log and "$http_x_forwarded_for" not in log and "$request " not in log and "$request_uri" not in log and "$uri" in log
    for z in ("server_tokens off;", "client_max_body_size 16k;", "proxy_set_header X-Real-IP $remote_addr;",
              "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;", "proxy_set_header X-Forwarded-Proto $scheme;",
              "proxy_set_header Host $host;", "proxy_pass http://127.0.0.1:8010;", "limit_conn dkportal_anschluss 20;", "limit_req_status 429;",
              "limit_req_log_level notice;", "limit_conn_log_level notice;", "error_log /var/log/nginx/kunde.error.log error;"):
        assert z in zeilen, z
    assert all(z.endswith("dkportal;") for z in zeilen if z.startswith("access_log"))


def test_muster_der_umgebung_ohne_werte():
    muster = (ROOT / "scripts" / "server" / "portal.env.beispiel").read_text(encoding="utf-8")
    werte = dict(z.split("=", 1) for z in muster.splitlines() if z and not z.startswith("#"))
    assert set(werte) == {"DATABASE_URL", "PORTAL_HERKUNFT", "PORTAL_BREMSE_SCHLUESSEL", "ERP_ENV"}
    assert "<PASSWORT>" in werte["DATABASE_URL"] and werte["PORTAL_BREMSE_SCHLUESSEL"].startswith("<")
    with pytest.raises(EinstellungFalsch):
        aus_umgebung(werte)  # das Muster selbst startet nichts


def test_gunicorn_in_den_abhaengigkeiten():
    zeilen = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert any(z.startswith("gunicorn==") for z in zeilen)  # seit 1.11.4 genau die Version des Servers (test_v803)


# --- Angriffe gegen einen echten uvicorn ---------------------------------------------------------------------------------------------------------

def _uvicorn(app, http_art: str):
    import uvicorn
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, http=http_art, log_level="warning", lifespan="on"))
    faden = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    faden.start()
    ende = time.monotonic() + 15
    while not server.started:
        assert time.monotonic() < ende, "uvicorn startet nicht"
        time.sleep(0.05)
    return server, faden, sock.getsockname()[1]


def _roh(port: int, methode: str, pfad: str, kopf: dict) -> int:
    verbindung = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        verbindung.putrequest(methode, pfad, skip_host=True, skip_accept_encoding=True)
        for k, v in kopf.items():
            verbindung.putheader(k, v)
        verbindung.putheader("Content-Length", "0")
        verbindung.endheaders()
        antwort = verbindung.getresponse()
        antwort.read()
        return antwort.status
    finally:
        verbindung.close()


@pytest.mark.parametrize("http_art", ["h11", "httptools"])
def test_angriffe_gegen_einen_echten_uvicorn(dienst, http_art):
    pytest.importorskip(http_art)
    _client, app = dienst
    server, faden, port = _uvicorn(app, http_art)
    try:
        erreicht = []
        for methode in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "ERFUNDEN"):
            for pfad in ("/health", "/api/kontakt", "/api/customers", "/login", "/static/ds/ds.css", "/gibt-es-nicht"):
                for kopf in ({"Host": "kunde.test"}, {"Host": "kunde.test", **EIGEN}, {"Host": "app.dachkonzepte.gmbh", **EIGEN}, {}):
                    status = _roh(port, methode, pfad, kopf)
                    if status < 400:
                        erreicht.append((methode, pfad, kopf.get("Host"), status))
        # erreicht wird nur, was offen gedacht ist: GET/HEAD auf /health, /api/kontakt und seit 1.11.14 die Design-Datei (die Seite braucht ds.css)
        # mit dem eigenen Host
        assert sorted(erreicht) == sorted((m, p, "kunde.test", 200) for m in ("GET", "HEAD") for p in ("/health", "/api/kontakt", "/static/ds/ds.css")
                                          for _ in range(2))
    finally:
        server.should_exit = True
        faden.join(15)
