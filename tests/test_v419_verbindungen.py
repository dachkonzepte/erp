"""Version 1.8.114 -- Datenbankverbindungen (Vorgabe vom 16.10.2026, Punkt 1), ohne PostgreSQL.

a. Die Anmeldeschranke liest im Threadpool, nie auf der Event-Loop (app/anmeldeschranke.py::_lesen()); kein Endpunkt mit Datenbank ist
   async (16 Uploads waren es bis 1.8.113); ein leerer Pool ergibt 503 statt 500.
b. Jede Route schließt ihre Sitzung vor dem Senden (Depends(get_db, scope="function")); eine Datei geht erst hinaus, wenn ihre Sitzung zu
   ist.
c. Eine Seite braucht eine Verbindung: die Schranke lädt die Seitendaten mit, die Jinja-Globals lesen nichts (app/seitendaten.py).
d. Pool unter PostgreSQL: pool_pre_ping, Größe passend zum Threadpool, Zeitlimit (app/database.py::engine_optionen()).

Der Angriffstest unter Last gegen PostgreSQL steht in tests/test_v419_verbindungen_unter_last.py."""

from __future__ import annotations

import inspect
import re
import threading

import anyio
import pytest
from fastapi import APIRouter, Depends
from fastapi.routing import APIRoute
from sqlalchemy import create_engine, event
from sqlalchemy.exc import TimeoutError as PoolLeer
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as database
from app import sitzungen
from app.auth import COOKIE_NAME, hash_password
from app.database import Base, get_db
from app.models import AppUser, Customer, CustomerDocument
from app.routers import customer_documents as customer_documents_router
from app.routers import customers as customers_router
from app.routers import pages as pages_router
from app.routers import users as users_router
from tests.anmeldung import app_mit_schranke, browser_client

ROOT_PARAM = re.compile(r"\{[^}]+\}")


def _routen_von(eintraege):
    for eintrag in eintraege:
        # FastAPI 0.141 hängt eingebundene Router als _IncludedRouter(original_router=...) an, ältere Fassungen die Routen selbst.
        router = getattr(eintrag, "original_router", None)
        if router is not None:
            yield from _routen_von(router.routes)
        elif isinstance(eintrag, APIRoute):
            yield eintrag


def _app_routen():
    import app.main  # noqa: F401  (conftest: Wegwerf-Datenbank)
    routen = list(_routen_von(app.main.app.routes))
    assert len(routen) > 500, f"nur {len(routen)} Routen in app.main gefunden -- hat sich die Einbindung geändert?"
    return routen


def _abhaengigkeiten(dependant):
    for sub in dependant.dependencies:
        yield sub
        yield from _abhaengigkeiten(sub)


# ---------------------------------------------------------------------------
# b. Sitzung vor dem Senden geschlossen
# ---------------------------------------------------------------------------

def test_jede_route_schliesst_ihre_sitzung_vor_dem_senden():
    """Depends(get_db) ohne scope="function" hielte die Verbindung bis zum letzten Byte der Antwort (FastAPI-Vorgabe "request") -- bei einer
    Datei für die ganze Übertragung, "idle in transaction". Gemischt erzeugte es zudem zwei Sitzungen je Anfrage (der Cache von FastAPI
    unterscheidet nach Scope)."""
    falsch = sorted({f"{sorted(r.methods)[0]} {r.path}" for r in _app_routen()
                     for sub in _abhaengigkeiten(r.dependant) if sub.call is get_db and sub.scope != "function"})
    assert not falsch, f"Depends(get_db) ohne scope=\"function\": {falsch}"


def test_mindestens_die_dateirouten_haben_eine_sitzung():
    """Gegen einen leeren Durchlauf: die Prüfung oben sieht die Sitzungen der Dateirouten wirklich."""
    routen = {r.path: r for r in _app_routen()}
    for pfad in ("/api/customer-documents/{document_id}/download", "/api/settings/general/logo"):
        treffer = [r for p, r in routen.items() if p == pfad]
        assert treffer, pfad
        assert any(sub.call is get_db and sub.scope == "function" for sub in _abhaengigkeiten(treffer[0].dependant)), pfad


# ---------------------------------------------------------------------------
# a. Nichts mit Datenbank auf der Event-Loop
# ---------------------------------------------------------------------------

def test_kein_async_endpunkt_greift_auf_die_datenbank_zu():
    """Ein async-Endpunkt (oder eine async-Abhängigkeit) mit Sitzung führt seine Abfragen auf der Event-Loop aus -- bei leerem Pool wartet
    der ganze Arbeitsprozess. Bis 1.8.113 waren es die 16 Uploads (await file.read(), danach synchron in die Datenbank)."""
    falsch = []
    for r in _app_routen():
        teile = [r.dependant, *_abhaengigkeiten(r.dependant)]
        mit_db = any(sub.call is get_db for sub in teile[1:])
        if mit_db and any(inspect.iscoroutinefunction(t.call) for t in teile if t.call is not None):
            falsch.append(f"{sorted(r.methods)[0]} {r.path}")
    assert not falsch, f"async mit Datenbank: {sorted(falsch)}"


@pytest.fixture
def welt():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    make_session = sessionmaker(bind=engine)
    with make_session() as db:
        admin = AppUser(username="ada", display_name="Ada", role="admin", active=True, password_hash=hash_password("Pw-12345678"))
        db.add(admin)
        db.commit()
        wert = sitzungen.neue_sitzung(db, admin, zweiter_faktor=True)
        db.commit()
    yield engine, make_session, wert
    engine.dispose()


def _client(app, wert):
    client = browser_client(app)
    client.cookies.set(COOKIE_NAME, wert, domain="testserver.local")
    return client


def test_die_schranke_liest_nicht_auf_der_event_loop(welt):
    """Der Thread, in dem die Schranke ihre Sitzung öffnet, ist nicht der Thread der Event-Loop (dort laufen async-Endpunkte)."""
    _, make_session, wert = welt
    threads = []

    def fabrik():
        threads.append(threading.get_ident())
        return make_session()

    probe = APIRouter()
    schleife = []

    @probe.get("/api/probe/schleife")
    async def _schleife():
        schleife.append(threading.get_ident())
        return {"ok": True}

    client = _client(app_mit_schranke(fabrik, probe, pages_router.router), wert)
    assert client.get("/api/probe/schleife").status_code == 200
    assert client.get("/account").status_code == 200
    assert len(threads) == 2 and schleife
    assert schleife[0] not in threads, "die Schranke hat ihre Sitzung auf der Event-Loop geöffnet"


def test_leerer_pool_ergibt_503_in_der_schranke_und_im_endpunkt(welt):
    """Wartet die Schranke oder ein Endpunkt länger als das Zeitlimit des Pools auf eine Verbindung: 503 mit Retry-After und Hinweis, samt
    Schutzkopfzeilen -- statt einer 500."""
    _, make_session, wert = welt

    def leer():
        raise PoolLeer("QueuePool limit reached")

    client = browser_client(app_mit_schranke(leer, pages_router.router), raise_server_exceptions=False)
    antwort = client.get("/login")
    assert antwort.status_code == 503 and antwort.headers["retry-after"] == "5"
    assert "ausgelastet" in antwort.json()["detail"] and antwort.headers["x-frame-options"] == "DENY"

    probe = APIRouter()

    @probe.get("/api/probe/leer")
    def _leer(db: Session = Depends(get_db, scope="function")):
        raise PoolLeer("QueuePool limit reached")

    client = _client(app_mit_schranke(make_session, probe), wert)
    antwort = client.get("/api/probe/leer")
    assert antwort.status_code == 503 and "ausgelastet" in antwort.json()["detail"]
    assert antwort.headers["cache-control"] == "no-store"


# ---------------------------------------------------------------------------
# b. Eine Datei geht erst hinaus, wenn ihre Sitzung geschlossen ist
# ---------------------------------------------------------------------------

class _ZaehlSitzung(Session):
    def close(self):
        self.dk_geschlossen = True
        super().close()


def test_eine_datei_geht_erst_hinaus_wenn_ihre_sitzung_geschlossen_ist(welt):
    """Der Download eines Dokuments der Kundenakte: beim Beginn der Antwort (http.response.start) ist jede Sitzung der Anfrage geschlossen
    -- die Verbindung ist zurück im Pool, keine offene Transaktion während der Übertragung."""
    engine, _, wert = welt
    erzeugt = []
    fabrik_basis = sessionmaker(bind=engine, class_=_ZaehlSitzung)

    def fabrik():
        db = fabrik_basis()
        erzeugt.append(db)
        return db

    with fabrik() as db:
        kunde = Customer(name="Kunde", last_name="Kunde")
        db.add(kunde)
        db.commit()
        kunde_id = kunde.id
    app = app_mit_schranke(fabrik, customers_router.router, customer_documents_router.router)
    client = _client(app, wert)
    hochgeladen = client.post(f"/api/customers/{kunde_id}/documents", data={"category": "Sonstiges"},
                              files={"file": ("plan.pdf", b"%PDF-1.4\n" + b"x" * 200_000, "application/pdf")})
    assert hochgeladen.status_code == 200, hochgeladen.text
    dokument_id = hochgeladen.json()["id"]

    beim_start = []
    vorher = len(erzeugt)
    innen = app

    async def beobachter(scope, receive, send):
        async def senden(nachricht):
            if nachricht["type"] == "http.response.start" and scope.get("path", "").endswith("/download"):
                beim_start.append([getattr(s, "dk_geschlossen", False) for s in erzeugt[vorher:]])
            await send(nachricht)
        await innen(scope, receive, senden)

    client = _client(beobachter, wert)
    antwort = client.get(f"/api/customer-documents/{dokument_id}/download")
    assert antwort.status_code == 200 and antwort.content.startswith(b"%PDF-")
    assert beim_start and len(beim_start[0]) == 2, beim_start  # Schranke und Endpunkt
    assert all(beim_start[0]), f"Sitzung beim Senden noch offen: {beim_start}"


# ---------------------------------------------------------------------------
# c. Eine Seite braucht eine Verbindung
# ---------------------------------------------------------------------------

def _zaehler(engines):
    stand = {"jetzt": 0, "hoechstens": 0, "gesamt": 0}

    def ausgabe(*_):
        stand["jetzt"] += 1
        stand["gesamt"] += 1
        stand["hoechstens"] = max(stand["hoechstens"], stand["jetzt"])

    def rueckgabe(*_):
        stand["jetzt"] -= 1

    for e in engines:
        event.listen(e, "checkout", ausgabe)
        event.listen(e, "checkin", rueckgabe)
    return stand


def _seitenpfad(pfad: str) -> str:
    return {"/master-data/{data_type}/new": "/master-data/customers/new",
            "/master-data/{data_type}/{record_id}/edit": "/master-data/properties/1/edit"}.get(pfad) or ROOT_PARAM.sub("1", pfad)


def test_jede_seite_braucht_eine_verbindung(welt):
    """Jede Seite als Admin: die Schranke holt eine Verbindung (Benutzer, Sitzung, Seitendaten), die Seite selbst keine weitere -- außer
    einer Route mit eigener Sitzung (/users), und auch dann nie zwei zugleich. Bis 1.8.113 öffnete jeder Aufruf eines Jinja-Globals eine
    eigene Sitzung (eine Seite: 37, /tasks 41, /mobil 17; /users hielt dabei schon eine -- zwei zugleich)."""
    engine, make_session, wert = welt
    stand = _zaehler([engine, database.engine])
    client = _client(app_mit_schranke(make_session, pages_router.router), wert)
    mit_eigener_sitzung = {r.path for r in pages_router.router.routes if isinstance(r, APIRoute)
                           and any(sub.call is get_db for sub in _abhaengigkeiten(r.dependant))}
    assert mit_eigener_sitzung == {"/users"}
    gezeigt, falsch = 0, []
    for r in pages_router.router.routes:
        if not isinstance(r, APIRoute) or "GET" not in r.methods or r.path == "/health":
            continue
        stand.update(jetzt=0, hoechstens=0, gesamt=0)
        antwort = client.get(_seitenpfad(r.path), follow_redirects=False)
        erwartet = 2 if r.path in mit_eigener_sitzung else 1
        if antwort.status_code == 200 and "<html" in antwort.text.lower():
            gezeigt += 1
        if (stand["gesamt"], stand["hoechstens"]) != (erwartet, 1):
            falsch.append((r.path, antwort.status_code, stand["gesamt"], stand["hoechstens"]))
    assert not falsch, f"(Seite, Status, Verbindungen gesamt, zugleich): {falsch}"
    assert gezeigt >= 40


def test_die_globals_lesen_die_seitendaten_der_schranke(welt):
    """Akzentfarbe, Modul-Schalter, Logo und Konto kommen auf der Seite an -- aus den Seitendaten der Schranke."""
    from app.models import EnabledModule, GeneralSettings, Employee
    engine, make_session, wert = welt
    with make_session() as db:
        db.get(GeneralSettings, 1).accent_color = "#123456"
        db.add(EnabledModule(module_key="kalender", enabled=False))
        mitarbeiterin = Employee(first_name="Ada", last_name="Lovelace", employee_number="M-1")
        db.add(mitarbeiterin)
        db.flush()
        db.get(AppUser, 1).employee_id = mitarbeiterin.id
        db.commit()
    client = _client(app_mit_schranke(make_session, pages_router.router), wert)
    seite = client.get("/projects").text
    assert "#123456" in seite
    assert 'href="/kalender"' not in seite and 'href="/tasks"' in seite
    assert ">AL<" in seite.replace(" ", "")


# ---------------------------------------------------------------------------
# d. Pool unter PostgreSQL
# ---------------------------------------------------------------------------

PG = "postgresql+psycopg://erp@127.0.0.1:5433/x"


def test_pool_unter_postgresql_passend_zum_threadpool(monkeypatch):
    for name in ("ERP_DB_POOL_SIZE", "ERP_DB_MAX_OVERFLOW", "ERP_DB_POOL_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)
    optionen = database.engine_optionen(PG)
    assert optionen == {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 35, "pool_timeout": 10}

    async def plaetze():
        return anyio.to_thread.current_default_thread_limiter().total_tokens

    assert anyio.run(plaetze) == database.THREADPOOL == optionen["pool_size"] + optionen["max_overflow"]
    arbeitsprozesse, max_connections, superuser = 2, 100, 3
    assert arbeitsprozesse * database.THREADPOOL <= max_connections - superuser - 10  # Rest für Sicherung, update.sh, Cron, psql


def test_pool_werte_aus_der_umgebung(monkeypatch):
    monkeypatch.setenv("ERP_DB_POOL_SIZE", "2")
    monkeypatch.setenv("ERP_DB_MAX_OVERFLOW", "0")
    monkeypatch.setenv("ERP_DB_POOL_TIMEOUT", "3")
    assert database.engine_optionen(PG) == {"pool_pre_ping": True, "pool_size": 2, "max_overflow": 0, "pool_timeout": 3}
    monkeypatch.setenv("ERP_DB_POOL_SIZE", "zwei")
    with pytest.raises(ValueError, match="ERP_DB_POOL_SIZE"):
        database.engine_optionen(PG)
    monkeypatch.setenv("ERP_DB_POOL_SIZE", "0")
    with pytest.raises(ValueError, match="mindestens 1"):
        database.engine_optionen(PG)


def test_sqlite_bleibt_wie_bisher():
    assert database.engine_optionen("sqlite:///./x.db") == {"connect_args": {"check_same_thread": False}}


def test_env_example_nennt_die_pool_variablen():
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / ".env.example").read_text(encoding="utf-8")
    for name in ("ERP_DB_POOL_SIZE", "ERP_DB_MAX_OVERFLOW", "ERP_DB_POOL_TIMEOUT"):
        assert name in text, name
