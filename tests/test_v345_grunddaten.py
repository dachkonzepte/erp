"""Version 1.8.42 -- Grunddaten beim Start statt beim ersten Lesen (app/grunddaten.py).

Bis 1.8.41 legte jede Lesefunktion ihre Einstellung oder ihren Standardsatz beim ersten Zugriff an. Zwei
gleichzeitige erste Zugriffe scheiterten am Primärschlüssel (Einstellungsseite, 1.8.21/1.8.40), Sätze ohne
UNIQUE konnten doppelt entstehen, und das Anlegen committete mitten im Festschreiben des Vertrags.

Geprüft wird hier: anlegen() legt auf einer leeren Datenbank alles an, ein zweiter Lauf schreibt nichts und
lässt Geändertes stehen; Lesefunktionen legen nichts an (GrunddatenFehlen); jede Singleton-Tabelle ist
eingetragen; der Start (import app.main) legt an, auch mit ERP_ENV=production und zwei gleichzeitigen
Prozessen; Rendern beim Festschreiben und Unterschreiben committet nicht. Gegen PostgreSQL (opt-in über
ERP_TEST_POSTGRES_URL, Wegwerf-Schema, Regel 16): gleichzeitige Starts ohne Fehler und ohne Doppel,
gleichzeitige Erstaufrufe ohne Fehler und ohne Schreiben, Rendern unter der gehaltenen Vertragssperre.

Dass kein GET schreibt, prüft der Rundgang in test_v326_monteur_datengrenze.py (test_kein_get_schreibt)."""

import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import close_all_sessions, sessionmaker

from app import grunddaten
from app.database import Base, get_db
from app.document_categories import DEFAULT_CATEGORIES
from app.document_layout import DEFAULT_SHARED_LAYOUT
from app.document_page_margins import PAGE_TYPES
from app.employees import DEFAULT_EMPLOYEE_FUNCTIONS
from app.grunddaten import GrunddatenFehlen
from app.models import (
    AppUser, CalculationSettings, DocumentCategory, DocumentLayoutBlock, DocumentPageMargins, EmployeeFunction,
    GeneralSettings, LaborRateOverheadSettings, LaborRateSettings, NumberSequence, OrderContract, PaymentTerm,
    ProjectPipelineColumn, ReminderLevel, SettingOptionGroup, TaskColumn, TaxKey, WorkTimeModel,
)
from app.option_settings import DEFAULT_OPTION_GROUPS
from app.payment_terms import DEFAULT_TERMS
from app.project_pipeline_columns import DEFAULT_COLUMNS as DEFAULT_PIPELINE_COLUMNS
from app.reminders import DEFAULT_REMINDER_LEVELS
from app.settings import DEFAULT_SEQUENCES
from app.task_columns import DEFAULT_COLUMNS as DEFAULT_TASK_COLUMNS
from app.tax_keys import DEFAULT_TAX_KEYS
from tests.grunddaten_schalter import ohne_grunddaten

ROOT = Path(__file__).resolve().parents[1]
PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")
_SCHREIBEN = re.compile(r'^\s*(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+"?(\w+)', re.I)


def _standardsaetze():
    """(Modell, erwartete Zeilen nach anlegen() auf einer leeren Datenbank) je Standardsatz."""
    return [
        (SettingOptionGroup, len(DEFAULT_OPTION_GROUPS)),
        (DocumentCategory, len(DEFAULT_CATEGORIES)),
        (EmployeeFunction, len(DEFAULT_EMPLOYEE_FUNCTIONS)),
        (PaymentTerm, len(DEFAULT_TERMS)),
        (TaxKey, len(DEFAULT_TAX_KEYS)),
        (ReminderLevel, len(DEFAULT_REMINDER_LEVELS)),
        (ProjectPipelineColumn, len(DEFAULT_PIPELINE_COLUMNS)),
        (TaskColumn, len(DEFAULT_TASK_COLUMNS)),
        (NumberSequence, len(DEFAULT_SEQUENCES)),
        (WorkTimeModel, 2),
        (DocumentLayoutBlock, len(DEFAULT_SHARED_LAYOUT)),
        (DocumentPageMargins, len(PAGE_TYPES)),
        (CalculationSettings, 1),
        (LaborRateOverheadSettings, 1),
        *[(model, 1) for model, _ in grunddaten._einzelzeilen()],
    ]


def _bestand(db) -> dict[str, int]:
    return {model.__tablename__: db.scalar(select(func.count()).select_from(model)) for model, _ in _standardsaetze()}


def _erwartet() -> dict[str, int]:
    return {model.__tablename__: n for model, n in _standardsaetze()}


def _leere_datenbank(url="sqlite:///:memory:", **kwargs):
    engine = create_engine(url, **kwargs)
    with ohne_grunddaten():
        Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


def _schreibzugriffe(engine) -> tuple[list, callable]:
    gefunden = []

    def merken(conn, cursor, statement, params, context, executemany):
        treffer = _SCHREIBEN.match(statement)
        if treffer:
            gefunden.append(treffer.group(1))
    event.listen(engine, "before_cursor_execute", merken)
    return gefunden, lambda: event.remove(engine, "before_cursor_execute", merken)


# --- anlegen() ----------------------------------------------------------------------------------------

def test_anlegen_auf_leerer_datenbank_legt_alles_an():
    engine, Session = _leere_datenbank()
    with Session() as db:
        assert set(_bestand(db).values()) == {0}
        grunddaten.anlegen(db)
    with Session() as db:  # committet, in einer neuen Sitzung sichtbar
        assert _bestand(db) == _erwartet()
        assert db.scalar(select(func.count()).select_from(NumberSequence)) == len(DEFAULT_SEQUENCES)
        assert {s.sequence_key for s in db.scalars(select(NumberSequence))} == set(DEFAULT_SEQUENCES)
        assert db.scalar(select(CalculationSettings).where(CalculationSettings.catalog_id.is_(None))) is not None
        assert {(m.document_type, m.page_type) for m in db.scalars(select(DocumentPageMargins))} == {
            ("default", p) for p in PAGE_TYPES}


def test_anlegen_zum_zweiten_mal_schreibt_nichts():
    engine, Session = _leere_datenbank()
    with Session() as db:
        grunddaten.anlegen(db)
    gefunden, aus = _schreibzugriffe(engine)
    try:
        with Session() as db:
            grunddaten.anlegen(db)
    finally:
        aus()
    assert gefunden == []
    with Session() as db:
        assert _bestand(db) == _erwartet()


def test_anlegen_laesst_geaendertes_stehen():
    engine, Session = _leere_datenbank()
    with Session() as db:
        grunddaten.anlegen(db)
        db.get(GeneralSettings, 1).company_name = "Dach & Co"
        db.get(LaborRateSettings, 1).weeks_per_year = 50
        db.delete(db.scalars(select(PaymentTerm)).first())
        db.commit()
        grunddaten.anlegen(db)
    with Session() as db:
        assert db.get(GeneralSettings, 1).company_name == "Dach & Co"
        assert db.get(LaborRateSettings, 1).weeks_per_year == 50
        assert db.scalar(select(func.count()).select_from(PaymentTerm)) == len(DEFAULT_TERMS) - 1


def test_gemeinkosten_uebernehmen_die_alten_jaehrlichen_gemeinkosten():
    """Wie bis 1.8.41 get_or_create_overhead_settings(): eine Installation aus <=0.6.8 mit "jährlichen
    Gemeinkosten" bekommt sie einmalig als fixe Gemeinkosten in EUR."""
    engine, Session = _leere_datenbank()
    with Session() as db:
        db.add(LaborRateSettings(id=1, annual_overhead=120000))
        db.commit()
        grunddaten.anlegen(db)
        overhead = db.get(LaborRateOverheadSettings, 1)
        assert (overhead.fixed_overhead_mode, overhead.fixed_overhead_value) == ("eur", 120000)


def test_testdatenbanken_bekommen_die_grunddaten_wie_nach_dem_start(db_session):
    assert _bestand(db_session) == _erwartet()


def _inhalt(engine) -> dict:
    """Alle Zeilen aller Tabellen, ohne Zeitstempel-Spalten, sortiert."""
    from sqlalchemy import DateTime
    inhalt = {}
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            spalten = [c for c in table.columns if not isinstance(c.type, DateTime)]
            zeilen = sorted((tuple(map(repr, r)) for r in conn.execute(select(*spalten))), key=str)
            if zeilen:
                inhalt[table.name] = zeilen
    return inhalt


def test_vorlage_im_test_hook_gleicht_einem_echten_anlegen():
    """tests/conftest.py übernimmt unter SQLite die Zeilen einer Vorlage, statt anlegen() je Datenbank laufen
    zu lassen -- der Inhalt muss derselbe sein wie nach anlegen() (ohne Zeitstempel), auch audit_logs."""
    mit_hook = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(mit_hook)
    echt, Session = _leere_datenbank()
    with Session() as db:
        grunddaten.anlegen(db)
    assert _inhalt(mit_hook) == _inhalt(echt)
    assert "audit_logs" in _inhalt(echt)


# --- Lesen legt nichts an -----------------------------------------------------------------------------

def _lesefunktionen():
    from app.ai_settings import load_ai_settings
    from app.calculation import load_calculation_settings
    from app.document_page_margins import get_margins
    from app.email_sending import load_smtp_settings
    from app.incoming_invoices import load_incoming_invoice_settings
    from app.labor_rate import load_labor_rate_settings, load_overhead_settings
    from app.maintenance_contracts import load_maintenance_settings
    from app.mobile_settings import load_mobile_settings
    from app.operational_assets import load_operational_asset_settings
    from app.outlook_calendar_sync import load_outlook_sync_settings
    from app.planning import load_planning_settings, load_region_settings
    from app.productive_hours import load_productive_hours_settings
    from app.recurring_costs import load_recurring_cost_settings
    from app.settings import load_general_settings, load_sequence
    from app.tasks import load_task_settings
    from app.time_backoffice import load_time_settings
    from app.work_time_models import load_advanced_settings
    return [
        load_ai_settings, load_calculation_settings, load_smtp_settings, load_incoming_invoice_settings,
        load_labor_rate_settings, load_overhead_settings, load_maintenance_settings, load_mobile_settings,
        load_operational_asset_settings, load_outlook_sync_settings, load_planning_settings, load_region_settings,
        load_productive_hours_settings, load_recurring_cost_settings, load_general_settings, load_task_settings,
        load_time_settings, load_advanced_settings,
        lambda db: load_sequence(db, "invoice"),
        lambda db: get_margins(db, "invoice", "first"),
    ]


def test_lesefunktionen_legen_nichts_an_und_melden_fehlende_grunddaten():
    engine, Session = _leere_datenbank()
    gefunden, aus = _schreibzugriffe(engine)
    try:
        with Session() as db:
            for lesen in _lesefunktionen():
                with pytest.raises(GrunddatenFehlen):
                    lesen(db)
    finally:
        aus()
    assert gefunden == []


def test_lesefunktionen_lesen_nach_dem_anlegen():
    engine, Session = _leere_datenbank()
    with Session() as db:
        grunddaten.anlegen(db)
    with Session() as db:
        for lesen in _lesefunktionen():
            assert lesen(db) is not None


def test_jede_einzelzeilen_tabelle_ist_in_grunddaten_eingetragen():
    """Eine neue Singleton-Einstellung (id mit Vorgabewert 1) ohne Eintrag in app/grunddaten.py würde nie
    angelegt -- ihre Lesefunktion meldete GrunddatenFehlen."""
    singletons = set()
    for mapper in Base.registry.mappers:
        column = mapper.class_.__table__.columns.get("id")
        if column is not None and column.default is not None and getattr(column.default, "arg", None) == 1:
            singletons.add(mapper.class_)
    eingetragen = {model for model, _ in grunddaten._einzelzeilen()} | {LaborRateOverheadSettings}
    assert singletons == eingetragen


# --- Der Start ----------------------------------------------------------------------------------------

def _start(url: str, data_dir: Path, *, production: bool, go_file: Path | None = None,
           ready_file: Path | None = None) -> subprocess.Popen:
    """import app.main in einem eigenen Prozess -- wie ein gunicorn-Arbeitsprozess. Mit go_file: erst die
    Fachmodule laden, ready_file schreiben, dann warten, bis go_file existiert (zwei Prozesse treffen sich
    beim Anlegen)."""
    env = {**os.environ, "DATABASE_URL": url, "ERP_DATA_DIR": str(data_dir), "ERP_SECRET_KEY": "test-" + "x" * 40}
    env.pop("ERP_ENV", None)
    if production:
        env["ERP_ENV"] = "production"
    code = "import app.main"
    if go_file is not None:
        code = ("import time, pathlib, app.routers.settings, app.routers.labor_rate, app.grunddaten\n"
                f"pathlib.Path({str(ready_file)!r}).write_text('bereit')\n"
                f"go = pathlib.Path({str(go_file)!r})\n"
                "while not go.exists(): time.sleep(0.01)\n"
                "import app.main")
    return subprocess.Popen([sys.executable, "-c", code], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)


def _beide_starten(url: str, tmp_path: Path) -> None:
    go = tmp_path / "los"
    bereit = [tmp_path / f"bereit{i}" for i in range(2)]
    prozesse = [_start(url, tmp_path / f"data{i}", production=True, go_file=go, ready_file=bereit[i])
                for i in range(2)]
    frist = time.monotonic() + 120
    while not all(b.exists() for b in bereit) and time.monotonic() < frist:
        time.sleep(0.05)
    go.write_text("los")
    for p in prozesse:
        _, err = p.communicate(timeout=180)
        assert p.returncode == 0, err[-3000:]


def test_start_legt_die_grunddaten_an(tmp_path):
    url = f"sqlite:///{(tmp_path / 'start.db').as_posix()}"
    p = _start(url, tmp_path / "data", production=False)
    _, err = p.communicate(timeout=180)
    assert p.returncode == 0, err[-3000:]
    with sessionmaker(bind=create_engine(url))() as db:
        assert _bestand(db) == _erwartet()


def test_zwei_gleichzeitige_starts_in_produktion_sqlite(tmp_path):
    """ERP_ENV=production: kein create_all(), das Schema kommt sonst aus alembic -- hier vorher ohne Grunddaten
    angelegt. Beide Prozesse legen gleichzeitig an, keiner scheitert, nichts doppelt."""
    url = f"sqlite:///{(tmp_path / 'prod.db').as_posix()}"
    _leere_datenbank(url)
    _beide_starten(url, tmp_path)
    with sessionmaker(bind=create_engine(url))() as db:
        assert _bestand(db) == _erwartet()


# --- Vertrag: Rendern unter der Sperre committet nicht ------------------------------------------------

def _vertrag_rendern_pruefen(Session, monkeypatch, sperre_gehalten=None):
    """Festschreiben und Unterschreiben eines Vertrags; je Rendern (Vertrag, Unterschriftsblatt) die Zahl der
    Commits währenddessen und, mit sperre_gehalten(order_id), ob die Vertragszeile danach noch gesperrt ist."""
    from app import contract_pdf
    from app.contract_signatures import sign_contract_on_device
    from app.contract_versions import freeze_contract
    from app.orders import load_order
    from tests.test_v325_contract_basis import make_quote
    from tests.test_v335_vertragsvorlagen import beauftragen, save
    from tests.test_v337_vertrag_unterschrift import CHECKBOX, SIGNATURE

    ergebnisse = []

    def beobachten(original):
        def rendern(db, *args, **kwargs):
            commits = []
            zaehlen = lambda session: commits.append(1)  # noqa: E731
            event.listen(db, "after_commit", zaehlen)
            try:
                pdf = original(db, *args, **kwargs)
            finally:
                event.remove(db, "after_commit", zaehlen)
            ergebnisse.append((original.__name__, len(commits),
                               sperre_gehalten(order_id[0]) if sperre_gehalten else None))
            return pdf
        return rendern
    monkeypatch.setattr(contract_pdf, "render_contract_pdf", beobachten(contract_pdf.render_contract_pdf))
    monkeypatch.setattr(contract_pdf, "render_signature_sheet_pdf", beobachten(contract_pdf.render_signature_sheet_pdf))

    order_id = [None]
    with Session() as db:
        save(db, reviewed=True)
        order = beauftragen(db, make_quote(db, number="G1"))
        order_id[0] = order.id
        version = freeze_contract(db, load_order(db, order.id), attachment="aktuell")
        version_id, sha = version.id, version.sent_document.sha256
    with Session() as db:
        sign_contract_on_device(db, load_order(db, order_id[0]), version_id=version_id, pdf_sha256=sha,
                                checkboxes={CHECKBOX: True}, customer_name="Kundin", customer_png=SIGNATURE,
                                company_name="Betrieb", company_png=SIGNATURE)
    with Session() as db:
        assert db.scalar(select(OrderContract.status).where(OrderContract.order_id == order_id[0])) == "unterschrieben"
    return ergebnisse


def test_vertrag_rendern_committet_nicht(threaded_db_session, monkeypatch):
    """1.8.40, Nebenbefund 1: ensure_default_layout() und get_or_create_general_settings() committeten beim
    allerersten Rendern und gaben damit die Sperre aus _locked_contract() frei. Seit 1.8.42 liest das Rendern
    nur -- kein Commit, solange es läuft."""
    Session = sessionmaker(bind=threaded_db_session.get_bind())
    ergebnisse = _vertrag_rendern_pruefen(Session, monkeypatch)
    assert ergebnisse == [("render_contract_pdf", 0, None), ("render_signature_sheet_pdf", 0, None)]


# --- PostgreSQL (opt-in) ------------------------------------------------------------------------------

@pytest.fixture
def pg_leer():
    """Wegwerf-Schema in der PostgreSQL-Testdatenbank, Tabellen ohne Grunddaten (Regel 16)."""
    if not PG_TEST_DATABASE_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_grunddaten_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_TEST_DATABASE_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_TEST_DATABASE_URL}?options=-csearch_path={schema}&application_name={schema}"
    engine, Session = _leere_datenbank(url, pool_size=10)
    try:
        yield {"url": url, "engine": engine, "Session": Session}
    finally:
        close_all_sessions()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"),
                         {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_pg_zwei_gleichzeitige_anlegen_ohne_fehler_und_ohne_doppel(pg_leer):
    """Zwei Sitzungen treffen sich vor anlegen() (Barriere) -- die zweite wartet an der Sperrzeile, bis die
    erste committet hat, und findet dann alles vor. Ohne die Sperre entstünden Zahlungsbedingungen,
    Steuerschlüssel, Mahnstufen und Layout doppelt (kein UNIQUE)."""
    barriere = threading.Barrier(2)
    fehler = []

    def lauf():
        try:
            with pg_leer["Session"]() as db:
                barriere.wait(timeout=20)
                grunddaten.anlegen(db)
        except Exception as e:  # noqa: BLE001 -- jeder Fehler gehört ins Ergebnis
            fehler.append(repr(e))
    threads = [threading.Thread(target=lauf) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert fehler == []
    with pg_leer["Session"]() as db:
        assert _bestand(db) == _erwartet()


def test_pg_zwei_gleichzeitige_starts_in_produktion(pg_leer, tmp_path):
    """Wie gunicorn -w 2 auf dem Server: zwei Prozesse importieren app.main (ERP_ENV=production) und legen
    gleichzeitig an."""
    _beide_starten(pg_leer["url"], tmp_path)
    with pg_leer["Session"]() as db:
        assert _bestand(db) == _erwartet()


# Die GET-Endpunkte, die bis 1.8.41 beim ersten Aufruf Grunddaten anlegten (Rundgang aus test_v326).
ERSTAUFRUFE = [
    "/api/labor-rate-settings", "/api/labor-rate-calculation", "/api/productive-hours-settings",
    "/api/planning/settings", "/api/time-tracking/settings", "/api/time-backoffice/work-time-models",
    "/api/settings/option-groups", "/api/settings/option-groups/time_entry_types", "/api/tax-keys",
    "/api/payment-terms", "/api/reminder-levels", "/api/tasks", "/api/task-settings", "/api/ai-settings",
    "/api/email-settings", "/api/outlook-sync-settings", "/api/operational-assets/due",
    "/api/recurring-cost-overhead-proposal", "/api/incoming-invoices/open-liabilities",
    "/api/document-layout/invoice", "/api/employees", "/api/mobile-settings", "/api/settings/general",
]


def test_pg_gleichzeitige_erstaufrufe_ohne_fehler_und_ohne_schreiben(pg_leer):
    """Frische Datenbank nach dem Start (anlegen() einmal), dann je Endpunkt zwei Erstaufrufe gleichzeitig,
    jede Anfrage mit eigener Verbindung. Bis 1.8.41 scheiterte hier einer am Primärschlüssel
    (labor-rate-settings und labor-rate-calculation, 1.8.21 Nebenbefund 1)."""
    from tests.test_v326_monteur_datengrenze import _routers_in_betriebsreihenfolge
    with pg_leer["Session"]() as db:
        grunddaten.anlegen(db)
    app = FastAPI()
    for router in _routers_in_betriebsreihenfolge():
        app.include_router(router)

    @app.middleware("http")
    async def _admin(request, call_next):
        request.state.erp_user = AppUser(username="admin", display_name="Admin", role="admin", active=True,
                                         password_hash="x")
        return await call_next(request)

    def _session():
        with pg_leer["Session"]() as session:
            yield session
    app.dependency_overrides[get_db] = _session

    gefunden, aus = _schreibzugriffe(pg_leer["engine"])
    ergebnisse = {}
    try:
        barriere = threading.Barrier(2 * len(ERSTAUFRUFE))

        def aufruf(pfad, i):
            with TestClient(app, raise_server_exceptions=False) as client:
                barriere.wait(timeout=60)
                ergebnisse[(pfad, i)] = client.get(pfad).status_code
        threads = [threading.Thread(target=aufruf, args=(pfad, i)) for pfad in ERSTAUFRUFE for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=120)
    finally:
        aus()
    assert {k: v for k, v in ergebnisse.items() if v != 200} == {}
    assert len(ergebnisse) == 2 * len(ERSTAUFRUFE)
    assert gefunden == []


def test_pg_vertrag_rendern_unter_gehaltener_sperre(pg_leer, monkeypatch):
    """Festschreiben und Unterschreiben auf einer frischen Datenbank nach dem Start: das Rendern läuft unter der
    Zeilensperre aus _locked_contract(), committet nicht und hält die Sperre -- eine zweite Verbindung bekommt
    die Vertragszeile mit NOWAIT nicht. Und es blockiert nicht (läuft durch)."""
    with pg_leer["Session"]() as db:
        grunddaten.anlegen(db)

    def sperre_gehalten(order_id):
        with pg_leer["engine"].connect() as conn:
            try:
                conn.execute(text("SELECT id FROM order_contracts WHERE order_id = :o FOR UPDATE NOWAIT"),
                             {"o": order_id})
            except OperationalError as e:
                assert "LockNotAvailable" in type(e.orig).__name__, e
                return True
            finally:
                conn.rollback()
        return False
    ergebnisse = _vertrag_rendern_pruefen(pg_leer["Session"], monkeypatch, sperre_gehalten)
    assert ergebnisse == [("render_contract_pdf", 0, True), ("render_signature_sheet_pdf", 0, True)]
