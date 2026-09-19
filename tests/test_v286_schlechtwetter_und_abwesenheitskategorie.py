"""Schlechtwetter-Zeitarten und Abwesenheitskategorie (nach Befund + Betreiberauftrag, siehe
CLAUDE.md-Segment "Grundlage für die späteren Ist-Werte im Produktivstunden-Rechner").

Vier Betreiberentscheidungen, hier abgesichert:
1. absence_category (urlaub/krankheit/fortbildung/unbezahlt, Rückfallwert "unbekannt" nur für
   Altbestand -- 0 Bestandszeilen real geprüft, siehe Chatverlauf) neben dem unveränderten,
   freien absence_type.
2. Zwei neue Zeitarten weather_winter/weather_summer, counts_as_productive=False für beide,
   geprüft in JEDER bestehenden Auswertung, die produktive Stunden von unproduktiven trennt.
3. Krankheitssichtbarkeit bewusst UNVERÄNDERT gelassen (Betreiberentscheidung nach Rückfrage) --
   kein Test dafür in dieser Datei, da keine Codeänderung.
4. Bedienung: Monteur/Mitarbeiter wählt absence_category beim Stellen des eigenen Antrags selbst.
"""

import importlib.util
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.absence_requests import ABSENCE_CATEGORIES, create_request, review_request
from app.database import Base
from app.invoices import create_invoice_from_time_entries
from app.models import Employee, EmployeeAbsence, InvoiceItem, TimeTrackingSettings
from app.routers.absence_requests import router as absence_requests_router
from app.routers.planning import router as planning_router
from app.time_backoffice import _wage_type, get_or_create_time_settings
from app.time_tracking import NON_PRODUCTIVE_ENTRY_TYPES, create_manual_entry, entry_type_is_productive
from tests.test_v133_invoices import make_order_with_item


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_employee(db, *, number="M-1", active=True):
    emp = Employee(
        employee_number=number, first_name="Max", last_name="Monteur",
        employee_group="gewerblich", hourly_wage=Decimal("20"), weekly_hours=Decimal("40"),
        active=active,
    )
    db.add(emp)
    db.commit()
    return emp


# --- Punkt 2: Schlechtwetter-Zeitarten sind nie produktiv ---

def test_entry_type_is_productive_excludes_travel_and_both_weather_types():
    assert entry_type_is_productive("site") is True
    assert entry_type_is_productive("workshop") is True
    assert entry_type_is_productive("other") is True
    assert entry_type_is_productive("travel") is False
    assert entry_type_is_productive("weather_winter") is False
    assert entry_type_is_productive("weather_summer") is False
    assert NON_PRODUCTIVE_ENTRY_TYPES == {"travel", "weather_winter", "weather_summer"}


def test_manual_weather_booking_is_marked_non_productive():
    db = db_session()
    order, _item = make_order_with_item(db)
    emp = make_employee(db)
    for entry_type in ("weather_winter", "weather_summer"):
        entry = create_manual_entry(
            db, employee_id=emp.id, order_id=order.id, work_date=date(2026, 1, 15),
            hours=Decimal("8"), entry_type=entry_type,
        )
        assert entry.counts_as_productive is False, entry_type


def test_manual_normal_booking_stays_productive():
    db = db_session()
    order, _item = make_order_with_item(db)
    emp = make_employee(db)
    entry = create_manual_entry(
        db, employee_id=emp.id, order_id=order.id, work_date=date(2026, 1, 15),
        hours=Decimal("8"), entry_type="site",
    )
    assert entry.counts_as_productive is True


# --- Abrechnungsschutz: Schlechtwetter darf nie dem Kunden in Rechnung gestellt werden ---

def test_weather_entries_are_excluded_from_invoice_from_time_entries():
    db = db_session()
    order, _item = make_order_with_item(db)
    emp = make_employee(db)
    normal = create_manual_entry(
        db, employee_id=emp.id, order_id=order.id, work_date=date(2026, 1, 10),
        hours=Decimal("4"), entry_type="site", activity="Dachdeckung",
    )
    weather = create_manual_entry(
        db, employee_id=emp.id, order_id=order.id, work_date=date(2026, 1, 15),
        hours=Decimal("6"), entry_type="weather_winter",
    )
    invoice = create_invoice_from_time_entries(db, order, [normal, weather], [])
    items = db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id)).all()
    assert len(items) == 1
    assert items[0].ist_quantity == Decimal("4")


def test_invoice_from_time_entries_rejects_when_only_weather_booked():
    db = db_session()
    order, _item = make_order_with_item(db)
    emp = make_employee(db)
    weather = create_manual_entry(
        db, employee_id=emp.id, order_id=order.id, work_date=date(2026, 1, 15),
        hours=Decimal("6"), entry_type="weather_summer",
    )
    with pytest.raises(ValueError):
        create_invoice_from_time_entries(db, order, [weather], [])


# --- DATEV-Lohnarten: kein stiller Rückfall auf "Sonstige" fuer Schlechtwetter ---

def test_wage_type_has_no_fallback_to_other_for_weather_types():
    db = db_session()
    settings = get_or_create_time_settings(db)
    settings.datev_wage_type_other = "900"
    db.commit()
    assert _wage_type(settings, "weather_winter") is None
    assert _wage_type(settings, "weather_summer") is None
    assert _wage_type(settings, "other") == "900"
    # Ein unkonfigurierter, unbekannter Wert (kein Schlechtwetter) faellt weiterhin auf "other".
    assert _wage_type(settings, "some_future_type") == "900"


def test_wage_type_returns_configured_weather_lohnart():
    db = db_session()
    settings = get_or_create_time_settings(db)
    settings.datev_wage_type_weather_winter = "911"
    settings.datev_wage_type_weather_summer = "912"
    db.commit()
    assert _wage_type(settings, "weather_winter") == "911"
    assert _wage_type(settings, "weather_summer") == "912"


# --- Punkt 1: Abwesenheitskategorie ---

def test_create_request_rejects_unknown_category():
    db = db_session()
    emp = make_employee(db)
    with pytest.raises(ValueError):
        create_request(
            db, employee_id=emp.id, absence_type="Sonstiges", absence_category="ferien",
            start_date=date(2026, 9, 1), end_date=date(2026, 9, 2),
        )


@pytest.mark.parametrize("category", ABSENCE_CATEGORIES)
def test_create_request_accepts_each_real_category(category):
    db = db_session()
    emp = make_employee(db)
    req = create_request(
        db, employee_id=emp.id, absence_type="Sonstiges", absence_category=category,
        start_date=date(2026, 9, 1), end_date=date(2026, 9, 2),
    )
    assert req.absence_category == category


def test_review_request_copies_category_onto_approved_absence():
    db = db_session()
    emp = make_employee(db)
    req = create_request(
        db, employee_id=emp.id, absence_type="Krankheit", absence_category="krankheit",
        start_date=date(2026, 9, 1), end_date=date(2026, 9, 3),
    )
    approved = review_request(db, req.id, decision="approved", reviewed_by_user_id=None)
    absence = db.get(EmployeeAbsence, approved.approved_absence_id)
    assert absence.absence_category == "krankheit"
    assert absence.absence_type == "Krankheit"


def test_unbekannt_is_not_an_accepted_category_at_creation():
    db = db_session()
    emp = make_employee(db)
    with pytest.raises(ValueError):
        create_request(
            db, employee_id=emp.id, absence_type="Sonstiges", absence_category="unbekannt",
            start_date=date(2026, 9, 1), end_date=date(2026, 9, 2),
        )


# --- Router-Ebene: Schema erzwingt eine echte Kategorie ---

def test_absence_request_endpoint_requires_absence_category(threaded_db_session, router_test_client):
    db = threaded_db_session
    emp = make_employee(db)
    client = router_test_client(db, absence_requests_router, role="field", employee_id=emp.id)
    resp = client.post("/api/absence-requests", json={
        "employee_id": emp.id, "absence_type": "Urlaub",
        "start_date": "2026-09-01", "end_date": "2026-09-02",
    })
    assert resp.status_code == 422


def test_absence_request_endpoint_rejects_invalid_category(threaded_db_session, router_test_client):
    db = threaded_db_session
    emp = make_employee(db)
    client = router_test_client(db, absence_requests_router, role="field", employee_id=emp.id)
    resp = client.post("/api/absence-requests", json={
        "employee_id": emp.id, "absence_type": "Urlaub", "absence_category": "ferien",
        "start_date": "2026-09-01", "end_date": "2026-09-02",
    })
    assert resp.status_code == 422


def test_absence_request_endpoint_accepts_valid_category(threaded_db_session, router_test_client):
    db = threaded_db_session
    emp = make_employee(db)
    client = router_test_client(db, absence_requests_router, role="field", employee_id=emp.id)
    resp = client.post("/api/absence-requests", json={
        "employee_id": emp.id, "absence_type": "Krankheit", "absence_category": "krankheit",
        "start_date": "2026-09-01", "end_date": "2026-09-02",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["absence_category"] == "krankheit"


def test_planning_absences_list_returns_category_and_supports_filter(threaded_db_session, router_test_client):
    db = threaded_db_session
    emp = make_employee(db)
    client = router_test_client(db, planning_router, role="buero_auftrag")
    resp = client.post("/api/planning/absences", json={
        "employee_id": emp.id, "absence_type": "Urlaub", "absence_category": "urlaub",
        "start_date": "2026-09-01", "end_date": "2026-09-02",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["absence_category"] == "urlaub"

    resp = client.get("/api/planning/absences", params={"absence_category": "krankheit"})
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.get("/api/planning/absences", params={"absence_category": "urlaub"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["absence_category"] == "urlaub"


# --- Migration: die beiden neuen Zeitarten werden in eine bereits gesäte Gruppe nachgezogen ---

def _load_migration_module():
    path = next(Path("alembic/versions").glob("*_schlechtwetter_zeitarten_und_.py"))
    spec = importlib.util.spec_from_file_location("weather_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_weather_time_entry_types_is_idempotent_and_appends_to_existing_group():
    migration = _load_migration_module()
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE setting_option_groups (id INTEGER PRIMARY KEY, group_key TEXT)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE setting_options (id INTEGER PRIMARY KEY, group_id INTEGER, label TEXT, "
            "value TEXT, sort_order INTEGER, active BOOLEAN, is_default BOOLEAN, "
            "created_at TEXT, updated_at TEXT)"
        )
        conn.exec_driver_sql("INSERT INTO setting_option_groups (id, group_key) VALUES (1, 'time_entry_types')")
        conn.exec_driver_sql(
            "INSERT INTO setting_options (id, group_id, label, value, sort_order, active, is_default) "
            "VALUES (1, 1, 'Baustellenzeit', 'site', 10, 1, 1)"
        )
    with engine.begin() as conn:
        migration.seed_weather_time_entry_types(conn)
    with engine.begin() as conn:
        rows = conn.exec_driver_sql(
            "SELECT label, value FROM setting_options WHERE group_id=1 ORDER BY sort_order"
        ).fetchall()
    assert [tuple(r) for r in rows] == [
        ("Baustellenzeit", "site"),
        ("Schlechtwetter Winter", "weather_winter"),
        ("Schlechtwetter Sommer", "weather_summer"),
    ]
    # Zweiter Lauf legt nichts doppelt an.
    with engine.begin() as conn:
        migration.seed_weather_time_entry_types(conn)
    with engine.begin() as conn:
        count = conn.exec_driver_sql("SELECT COUNT(*) FROM setting_options").scalar()
    assert count == 3


def test_seed_weather_time_entry_types_is_a_noop_without_existing_group():
    migration = _load_migration_module()
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE setting_option_groups (id INTEGER PRIMARY KEY, group_key TEXT)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE setting_options (id INTEGER PRIMARY KEY, group_id INTEGER, label TEXT, "
            "value TEXT, sort_order INTEGER, active BOOLEAN, is_default BOOLEAN, "
            "created_at TEXT, updated_at TEXT)"
        )
    with engine.begin() as conn:
        migration.seed_weather_time_entry_types(conn)  # darf nicht scheitern
        count = conn.exec_driver_sql("SELECT COUNT(*) FROM setting_options").scalar()
    assert count == 0
