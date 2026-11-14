"""Gemeinsame pytest-Fixtures (seit 1.0.11).

Viele bestehende Testdateien definieren ihre eigene db_session()- oder
new_db()-Hilfsfunktion für eine frische In-Memory-SQLite-Datenbank -- das
funktioniert und wurde hier bewusst nicht angefasst (Risiko für etwas, das
längst läuft, unnötig). Für NEUE Tests steht ab jetzt dieselbe Datenbank
als reguläre pytest-Fixture zur Verfügung, um die Dopplung nicht weiter
wachsen zu lassen:

    def test_etwas(db_session):
        kunde = Customer(name="Test", last_name="Test")
        db_session.add(kunde); db_session.commit()
        ...

Bestehende Testdateien mit eigener lokaler db_session()-Funktion sind davon
nicht betroffen: ein Name, der in einer Testdatei selbst definiert wird,
hat dort Vorrang vor dieser Fixture.
"""

import os
import tempfile
from datetime import date
from pathlib import Path

# Regel 16 (CLAUDE.md): kein Testlauf berührt die echte Datenbank oder den echten Datenordner.
# Ohne diese Zeilen fiele app.database beim Import still auf ./dachkonzepte_erp.db zurück --
# jeder Test, der app.main importiert (create_all()) oder eine Seite rendert (Jinja-Globals mit
# eigener SessionLocal()), schriebe dann in die lokale Arbeitsdatenbank. Gesetzt VOR dem ersten
# Import aus app.*, bewusst unbedingt: auch ein in der Shell gesetztes DATABASE_URL (z. B. die
# lokale Postgres-Instanz) wird für den Testlauf ersetzt. Die Wegwerf-Dateien liegen im
# Temp-Verzeichnis und werden nie wiederverwendet.
_TEST_SCRATCH = Path(tempfile.mkdtemp(prefix="erp_pytest_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEST_SCRATCH / 'wegwerf.db').as_posix()}"
os.environ["ERP_DATA_DIR"] = str(_TEST_SCRATCH / "data")
# Seit 1.8.107 ausdrücklich "test" (Korrektur 104-8): ohne ERP_ENV wäre das Anmelde-Cookie Secure, und der TestClient (http://testserver)
# schickte es nie zurück. create_all() beim Import von app.main läuft wie bisher (nur production schaltet es ab).
os.environ["ERP_ENV"] = "test"
os.environ.pop("ERP_COOKIE_SECURE", None)

import pytest  # noqa: E402 -- erst nach dem Umlenken der Datenbank
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
from app.models import AppUser
from tests.aufraeumen import wegwerf_engine
from tests.grunddaten_schalter import grunddaten_aus, ohne_grunddaten
from tests import aufraeumen, reihenfolge
from tests.pg_schutz import liegen_gebliebene_schemas_loeschen, schema_waechter_einrichten
from tests.uhr import uhr_festhalten
from tests.zeitgrenze import Uhr, grenze_fuer, marker_anmelden, option_anmelden, schon_abgelaufen

@event.listens_for(Engine, "connect")
def _fremdschluessel_pruefen(dbapi_connection, connection_record):
    """Seit 1.9.339 (Runde V1, Punkt 2): jede SQLite-Verbindung dieses Testprozesses prüft Fremdschlüssel (PRAGMA foreign_keys=ON) -- wie
    PostgreSQL live. Bis dahin prüfte die Suite keinen: SQLite tut es nur mit dem PRAGMA, und app/database.py setzt es bewusst nicht (für eine
    lokale Datenbank mit Altbestand). So blieben fünf Fehler unsichtbar, die live mit 500 abgingen (Befund SQLite/PostgreSQL, E1–E5,
    docs/archiv/sqlite-und-postgresql.md). Das Ereignis „connect“ an der Klasse Engine gilt für jede Engine, auch eine, die vor diesem Modul
    entstand (app.database); Kindprozesse (alembic, uvicorn) haben es nicht. Wächter: tests/test_v739_fremdschluessel_sqlite.py."""
    if type(dbapi_connection).__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Seit 1.8.81 (Regel 27): kein Test gegen PostgreSQL im Schema public der Spielwiese -- für jede Engine dieses Testprozesses.
# Seit 1.8.108 trägt dabei jedes angelegte Schema pgtest_* die Kennung dieses Prozesses (tests/pg_schutz.py).
schema_waechter_einrichten()


def pytest_sessionstart(session):
    """Seit 1.8.108: zu Beginn eines Testlaufs liegen gebliebene Schemas pgtest_* in der Spielwiese löschen -- nur solche, deren
    Testprozess nicht mehr läuft (tests/pg_schutz.py::liegen_gebliebene_schemas_loeschen). Nur im Hauptprozess, nicht in den
    Arbeitsprozessen eines parallelen Laufs (pytest-xdist); ohne ERP_TEST_POSTGRES_URL nichts."""
    url = os.getenv("ERP_TEST_POSTGRES_URL")
    if not url or hasattr(session.config, "workerinput"):
        return
    melden = session.config.pluginmanager.get_plugin("terminalreporter")
    try:
        ergebnis = liegen_gebliebene_schemas_loeschen(url)
    except Exception as exc:  # Instanz nicht erreichbar: die Tests gegen PostgreSQL melden es selbst
        zeilen = [f"PostgreSQL-Testschemas nicht aufgeräumt: {type(exc).__name__}"]
    else:
        zeilen = [f"PostgreSQL-Testschemas: {text} {len(namen)} ({', '.join(namen[:5])}{' …' if len(namen) > 5 else ''})"
                  for text, namen in (
            ("liegen geblieben, gelöscht:", ergebnis["geloescht"]),
            ("nicht gelöscht, Löschen gescheitert:", ergebnis["fehler"]),
            ("nicht gelöscht, ohne Kennung (Stand vor 1.8.108?):", ergebnis["ohne_kennung"]),
            ("nicht gelöscht, Kennung eines anderen Rechners:", ergebnis["fremder_rechner"]),
            ("eines laufenden Testprozesses, stehen gelassen:", ergebnis["laufend"])) if namen]
    for zeile in zeilen:
        if melden is not None:
            melden.write_line(zeile)


@event.listens_for(Base.metadata, "after_create")
def _grunddaten_wie_nach_dem_start(target, connection, **kw):
    """Seit 1.8.42 legt app/main.py die Grunddaten (Einstellungen, Standardsätze) beim Start an, kein
    Lesepfad mehr beim ersten Zugriff (app/grunddaten.py). Jede Testdatenbank aus create_all() bekommt
    sie hier genauso -- sie sieht damit aus wie eine Installation nach dem Start. Läuft in der
    Transaktion von create_all(); eine Datenbank OHNE Grunddaten: tests/grunddaten_schalter.py.

    Unter SQLite übernimmt der Hook die Zeilen einer Vorlage, die anlegen() einmal je Jahr erzeugt hat
    (anlegen() je Datenbank kostete rund 70 ms, bei über 2500 Tests zwei Minuten). Das Jahr zählt, weil
    die Nummernkreise es speichern (test_v316 stellt die Uhr auf andere Jahre). Hat die Datenbank schon
    Grunddaten oder ist es PostgreSQL (Sequenzen), läuft anlegen() selbst."""
    if grunddaten_aus():
        return
    from app.berlin_time import berlin_now
    from app.grunddaten import anlegen
    from app.models import GeneralSettings
    leer = connection.execute(select(GeneralSettings.id).limit(1)).first() is None
    if connection.dialect.name == "sqlite" and leer:
        for table, rows in _grunddaten_vorlage(berlin_now().year):
            connection.execute(table.insert(), rows)
        return
    with Session(bind=connection) as session:
        anlegen(session)


_VORLAGEN: dict[int, list] = {}


def _grunddaten_vorlage(jahr: int) -> list:
    """(Tabelle, Zeilen) aller Tabellen, in die anlegen() auf einer leeren SQLite-Datenbank schreibt."""
    if jahr not in _VORLAGEN:
        from app.grunddaten import anlegen
        engine = create_engine("sqlite:///:memory:")
        with ohne_grunddaten():
            Base.metadata.create_all(engine)
        with Session(engine) as session:
            anlegen(session)
        with engine.connect() as conn:
            _VORLAGEN[jahr] = [(table, rows) for table in Base.metadata.sorted_tables
                               if (rows := [dict(r._mapping) for r in conn.execute(table.select())])]
        engine.dispose()
    return _VORLAGEN[jahr]


def pytest_addoption(parser):
    parser.addoption(
        "--wanduhr", metavar="HH:MM", default=None,
        help="Suite so laufen lassen, als wäre es heute HH:MM (Europe/Berlin) -- Gegenprobe für Tests, "
             "die von der Tageszeit abhängen (seit 1.8.36, z. B. --wanduhr 19:30 nach der Feierabend-Grenze). Seit 1.9.242 auch "
             "\"JJJJ-MM-TT HH:MM\": als wäre es an diesem Tag (z. B. ein Samstag, Gegenprobe für den Tag ohne Arbeit).",
    )
    option_anmelden(parser)  # --zeitgrenze, seit 1.8.111


def pytest_configure(config):
    marker_anmelden(config)
    reihenfolge.einrichten(config)  # seit 1.9.183


def pytest_runtest_logstart(nodeid, location):
    """Seit 1.9.183: Reihenfolge der Tests je Testprozess mitschreiben (tests/reihenfolge.py) -- ein Wackler lässt sich so nachstellen."""
    reihenfolge.gestartet(nodeid)


def pytest_runtest_logreport(report):
    reihenfolge.bericht(report)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """Seit 1.8.111: Zeitgrenze je Test (tests/zeitgrenze.py) -- ein hängender Test beendet seinen Testprozess mit Stapel, statt
    den ganzen Lauf anzuhalten."""
    sekunden = grenze_fuer(item)
    if sekunden is None:
        yield
        return
    with Uhr(item, sekunden):
        yield


# Seit 1.9.339: E1–E5 aus dem Befund SQLite/PostgreSQL scheitern mit PRAGMA foreign_keys=ON wie live unter PostgreSQL. Bis zu ihrer Behebung
# (Runde V1, Punkt 3) erwartet rot, nur mit IntegrityError und streng -- wird einer grün, scheitert der Lauf. Die Liste darf nur kürzer werden.
FREMDSCHLUESSEL_BEKANNT = {
    **{f"tests/test_v194_project_archive_delete.py::{t}": "E1 Projekt löschen mit LV-Titel (app/projects.py::delete_project())" for t in (
        "test_delete_project_without_orders_succeeds", "test_delete_template_always_works_since_templates_never_have_orders",
        "test_delete_project_cascades_to_quote_structure", "test_delete_project_removes_physical_document_folder",
        "test_delete_project_does_not_touch_other_projects_folder")},
    **{f"tests/test_v247_address_import.py::{t}": "E2 Adressimport rückgängig (app/address_import.py::revert_import_run())" for t in (
        "test_revert_deletes_untouched_customers_and_suppliers", "test_reverted_run_frees_the_legacy_address_number_for_a_future_import",
        "test_upload_preview_confirm_and_revert_over_real_routes")},
    "tests/test_v214_findings_and_photos.py::test_delete_draft_report_removes_photos_from_disk_and_cleans_up_task":
        "E3 Berichtsentwurf mit Folgeaufgabe löschen (app/service_reports.py::delete_report())",
    "tests/test_v105_booking_reassign_week_validity.py::test_backoffice_booking_can_be_reassigned_to_another_project_order":
        "E4 Leistungskatalog erneut importieren (app/service.py::persist_project())",
    "tests/test_v083_material_bulk_assignment.py::test_material_delivery_note_links_survive_order_material_refresh":
        "E5 Materialbedarf der AV neu aufbauen (app/work_preparation.py::refresh_preparation_materials())",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        grund = FREMDSCHLUESSEL_BEKANNT.get(item.nodeid)
        if grund:
            item.add_marker(pytest.mark.xfail(strict=True, raises=IntegrityError, reason=f"{grund} -- Fremdschlüssel, behoben mit Punkt 3"))


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Seit 1.8.111: ein Test, dessen Zeitgrenze in diesem parallelen Lauf schon einmal abgelaufen ist, läuft nicht noch einmal
    (xdist gibt nach dem Absturz die ganze Datei zurück, tests/zeitgrenze.py)."""
    if schon_abgelaufen(item):
        pytest.fail(f"ZEITGRENZE: {item.nodeid} hat seine Zeitgrenze in diesem Lauf schon überschritten (Arbeitsprozess beendet) -- "
                    "nicht noch einmal ausgeführt.", pytrace=False)


@pytest.fixture(scope="session", autouse=True)
def _wanduhr(request):
    """Ohne --wanduhr nichts. Mit: die Uhr der App läuft ab HH:MM heute. Sitzungsweit, damit sie auch
    unter Modul-Fixtures liegt; feste_uhr/uhr_festhalten() setzen sich darüber."""
    wert = request.config.getoption("--wanduhr")
    if not wert:
        yield
        return
    from datetime import date, time
    tag, _, uhrzeit = wert.strip().rpartition(" ")
    with uhr_festhalten(time.fromisoformat(uhrzeit), tag=date.fromisoformat(tag) if tag else None):
        yield


@pytest.fixture
def feste_uhr():
    """Uhr der App (app.berlin_time) läuft ab heute 10:00 Europe/Berlin -- für Tests, die sonst von
    der Tageszeit abhingen (Feierabend-Grenze an /api/field-view/today). Siehe tests/uhr.py."""
    with uhr_festhalten() as start:
        yield start


# Seit 1.9.166 (Lohn L1a, Entscheidung Tobias E2): Tests der Zeitregeln mit festen Tagen statt relativ zu heute. Dienstag, KW 46 -- weder
# Monatserster noch Feiertag, ein Tag nach einem Arbeitstag.
FESTER_TAG = date(2026, 11, 10)


@pytest.fixture
def fester_tag():
    """Wie feste_uhr, aber an FESTER_TAG statt heute: berlin_today() ist dann 10.11.2026, 10:00 Uhr Europe/Berlin."""
    with uhr_festhalten(tag=FESTER_TAG) as start:
        yield start


# Seit 1.9.195 (L1a Stufe 3, Punkt 4): jede über tests/aufraeumen.py::wegwerf_engine() angelegte Engine schließt das Ende ihres Aufbaus mit
# dispose() -- des Tests, des Moduls oder des Laufs, je nachdem, wo sie entstand (autouse-Fixtures eines Umfangs laufen vor dessen übrigen
# Fixtures an und als letzte ab). Bis dahin räumte die Speicherbereinigung sie ab, oft in einem fremden Thread (Fehler im Protokoll).
@pytest.fixture(scope="session", autouse=True)
def _engines_des_laufs():
    marke = aufraeumen.marke()
    yield
    aufraeumen.schliessen(marke)


@pytest.fixture(scope="module", autouse=True)
def _engines_des_moduls():
    marke = aufraeumen.marke()
    yield
    aufraeumen.schliessen(marke)


@pytest.fixture(autouse=True)
def _engines_des_tests():
    marke = aufraeumen.marke()
    yield
    aufraeumen.schliessen(marke)


@pytest.fixture
def db_session():
    engine = wegwerf_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def threaded_db_session():
    """Wie db_session(), aber mit check_same_thread=False + StaticPool (seit 1.2.15) -- der
    FastAPI-TestClient führt Endpunkte über einen Threadpool aus. Ohne StaticPool würde
    SQLAlchemys SingletonThreadPool dem neuen Thread eine ZWEITE, leere :memory:-Verbindung
    zuteilen ("no such table"); StaticPool erzwingt exakt dieselbe Connection über alle Threads.
    Für echte HTTP-Routen-Tests über router_test_client() -- reine In-Process-Tests bleiben bei
    der einfachen db_session-Fixture bzw. der gleichnamigen lokalen Funktion."""
    engine = wegwerf_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def router_test_client():
    """Baut aus ECHTEN Router-Instanzen (nicht kopiert) eine schlanke Test-App -- prüft die
    tatsächliche FastAPI/Starlette-Routenauflösung (z. B. dass "/reorder" nicht von "/{id}"
    verschluckt wird), ohne die produktive identity_and_audit_middleware (echte Datei-DB,
    echter Login) mitzuschleppen. Ersetzt sie durch einen einfachen, fest angemeldeten
    Admin-Kontext -- reine Test-Infrastruktur, betrifft nicht die Auth-Prüfung selbst.

    Verwendung: client = router_test_client(db, some_router, other_router); db muss mit der
    threaded_db_session-Fixture erzeugt worden sein.

    Seit "Rechtekonzept" (siehe CLAUDE.md): optionale Parameter role/employee_id, um dieselbe
    Test-App auch als Büro-/Monteur-Konto statt fest als Administrator zu durchlaufen (z. B. um
    require_role(...)-Ablehnungen zu belegen) -- Vorgabewerte bleiben "admin"/None, kein
    bestehender Aufruf muss sich ändern. Seit 1.8.57 optional user_id/display_name -- ein Konto mit ID (z. B. für
    Unterschriften "angemeldetes Konto"); ohne bleibt das Konto ohne ID wie bisher.
    Seit 1.9.338 gibt es ein Konto mit ID auch in der Datenbank: fehlt dort ein AppUser mit dieser ID, legt _make ihn an
    (Benutzername "test-konto-<id>", Rolle und Mitarbeiter wie angemeldet). Bis dahin zeigte jede gespeicherte Konto-ID
    (requested_by_user_id, owner_user_id …) ins Leere -- unter PostgreSQL und mit PRAGMA foreign_keys=ON ein Fehler."""
    def _make(db, *routers, role="admin", employee_id=None, user_id=None, display_name=None):
        if user_id is not None and db.get(AppUser, user_id) is None:
            db.add(AppUser(id=user_id, username=f"test-konto-{user_id}", display_name=display_name or role.capitalize(), role=role,
                           active=True, employee_id=employee_id, password_hash=hash_password("Passwort123")))
            db.commit()
        app = FastAPI()
        for router in routers:
            app.include_router(router)

        @app.middleware("http")
        async def _fake_identity(request, call_next):
            request.state.erp_user = AppUser(
                id=user_id, username=f"{role}-test", display_name=display_name or role.capitalize(), role=role, active=True,
                employee_id=employee_id, password_hash=hash_password("Passwort123"),
            )
            return await call_next(request)

        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app)
    return _make
