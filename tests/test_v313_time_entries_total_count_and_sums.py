"""Version 1.8.9 -- GET /api/time-entries schneidet nicht mehr still ab, Summen kommen aus der Datenbank.

Bis 1.8.8 lieferte GET /api/time-entries höchstens `limit` Buchungen (Vorgabe 500, still gekappt
bei 2000), ohne zu melden, wie viele es insgesamt gibt; Einsatzbericht-Seite und Projektmappe
bildeten ihre Summen in der Oberfläche aus dieser gekürzten Liste, und das Backoffice forderte
3000 an und bekam 2000. Jetzt: Kopfzeile X-Total-Count, GET /api/time-entries/summary (SUM in der
Datenbank, dieselbe Sichtbarkeit wie die Liste), limit über 2000 wird mit 422 abgelehnt.

Ein gemeinsamer Datensatz, jeweils Grenze+1: Auftrag A hat 501 Buchungen (Vorgabe 500), Projekt P
1001 (Projektmappe lädt 1000), insgesamt 2001 (höchstens 2000). Die älteste Buchung (2,5 Std.
Fahrzeit des Monteurs auf Auftrag A) fällt bei jeder dieser Grenzen als erste aus der Liste."""

import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Customer, Employee, Order, Project, TimeEntry
from app.routers.time_tracking import router as time_router
from app.time_tracking import list_entries
from tests.test_v133_invoices import make_order_with_item
from tests.test_v282_role_narrowing_etappe2 import ALL_ROLES, WAGE_KEYS, _recursive_keys

START = date(2026, 1, 1)
OFFICE_ROLES = ("buero_auftrag", "buero_finanzen", "admin")


@pytest.fixture(scope="module")
def data():
    # Einmal je Modul (2001 Buchungen), StaticPool für den TestClient-Threadpool. Kein Test ändert Daten.
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    order_a, _ = make_order_with_item(db)
    order_b = Order(order_number="AUF-TEST-0002", project_id=order_a.project_id, source_quote_id=2,
                    quote_number_snapshot="A-TEST-0002", title="Zweiter Auftrag", customer_name="Test Kunde")
    other_customer = Customer(name="Fremdkunde", last_name="Fremdkunde")
    db.add_all([order_b, other_customer]); db.flush()
    other_project = Project(project_number="P-TEST-0002", name="Fremdes Projekt", customer_id=other_customer.id,
                            pipeline_column_id=order_a.project.pipeline_column_id)
    db.add(other_project); db.flush()
    order_c = Order(order_number="AUF-TEST-0003", project_id=other_project.id, source_quote_id=3,
                    quote_number_snapshot="A-TEST-0003", title="Fremder Auftrag", customer_name="Fremdkunde")
    me = Employee(employee_number="M-1", first_name="Mia", last_name="Monteur", employee_group="gewerblich",
                  hourly_wage="21.50", active=True)
    colleague = Employee(employee_number="K-1", first_name="Karl", last_name="Kollege", employee_group="gewerblich",
                         hourly_wage="23.75", active=True)
    db.add_all([order_c, me, colleague]); db.commit()

    def booking(emp, order, day, hours="1.00", entry_type="site", status="booked"):
        return TimeEntry(employee_id=emp.id, project_id=order.project_id, order_id=order.id,
                         work_date=START + timedelta(days=day), entry_type=entry_type,
                         counts_as_productive=entry_type != "travel", hours=Decimal(hours), status=status)

    db.add(booking(me, order_a, 0, "2.50", "travel"))  # älteste Buchung überhaupt, die einzige des Monteurs
    db.add_all(booking(colleague, order_a, 1 + i // 10) for i in range(499))
    db.add(booking(colleague, order_a, 60, "0", status="running"))
    db.add_all(booking(colleague, order_b, 1 + i // 10) for i in range(500))
    db.add_all(booking(colleague, order_c, 1 + i // 10) for i in range(1000))
    db.commit()
    yield SimpleNamespace(db=db, order_a=order_a.id, order_b=order_b.id, order_c=order_c.id,
                          project_p=order_a.project_id, project_q=other_project.id, me=me.id, colleague=colleague.id)
    db.close()
    engine.dispose()


@pytest.fixture
def client(data, router_test_client):
    return lambda role="buero_auftrag", employee_id=None: router_test_client(data.db, time_router, role=role, employee_id=employee_id)


def _normalized(body):
    return {k: Decimal(str(v)) if k.endswith("_hours") else v for k, v in body.items()}


# ---------------------------------------------------------------------------
# 1. X-Total-Count und die Obergrenze 2000
# ---------------------------------------------------------------------------

def test_list_reports_total_count_beyond_default_limit(data, client):
    resp = client().get(f"/api/time-entries?order_id={data.order_a}")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 500
    assert resp.headers["X-Total-Count"] == "501"
    assert all(r["employee_id"] != data.me for r in resp.json())  # die älteste fehlt in der Liste


def test_limit_2000_reports_2001_and_larger_limits_are_rejected(data, client):
    c = client("admin")
    resp = c.get("/api/time-entries?limit=2000")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 2000
    assert resp.headers["X-Total-Count"] == "2001"
    for bad in (2001, 3000, 0):
        assert c.get(f"/api/time-entries?limit={bad}").status_code == 422, bad


def test_list_entries_rejects_limit_outside_1_to_2000(data):
    assert len(list_entries(data.db, limit=2000)) == 2000
    for bad in (2001, 0):
        with pytest.raises(ValueError):
            list_entries(data.db, limit=bad)


# ---------------------------------------------------------------------------
# 2. Summen per SUM aus der Datenbank (Einsatzbericht-Seite, Projektmappe)
# ---------------------------------------------------------------------------

def test_summary_of_order_sums_all_501_entries(data, client):
    body = client().get(f"/api/time-entries/summary?order_id={data.order_a}").json()
    assert _normalized(body) == {"entry_count": 501, "booked_count": 500, "employee_count": 2, "total_hours": Decimal("501.50"),
                                 "productive_hours": Decimal("499.00"), "travel_hours": Decimal("2.50")}


def test_summary_of_project_sums_all_1001_entries(data, client):
    body = client().get(f"/api/time-entries/summary?project_id={data.project_p}").json()
    assert _normalized(body) == {"entry_count": 1001, "booked_count": 1000, "employee_count": 2, "total_hours": Decimal("1001.50"),
                                 "productive_hours": Decimal("999.00"), "travel_hours": Decimal("2.50")}


# ---------------------------------------------------------------------------
# 3. Summen folgen der Sichtbarkeit der Liste -- Angriffstest Monteur
# ---------------------------------------------------------------------------

OWN = {"entry_count": 1, "booked_count": 1, "employee_count": 1, "total_hours": Decimal("2.50"),
       "productive_hours": Decimal("0"), "travel_hours": Decimal("2.50")}
NOTHING = {"entry_count": 0, "booked_count": 0, "employee_count": 0, "total_hours": Decimal("0"),
           "productive_hours": Decimal("0"), "travel_hours": Decimal("0")}


def test_field_summary_never_includes_colleagues_or_foreign_orders(data, client):
    field = client("field", employee_id=data.me)
    cases = {
        f"order_id={data.order_a}": OWN,                       # gemeinsamer Auftrag: nur eigene
        f"order_id={data.order_c}": NOTHING,                   # fremder Auftrag
        f"project_id={data.project_q}": NOTHING,               # fremdes Projekt
        f"employee_id={data.colleague}": OWN,                  # Kollege: wird auf eigene gesetzt
        f"employee_id={data.colleague}&order_id={data.order_c}": NOTHING,
        f"project_id={data.project_p}": OWN,
        "": OWN,
    }
    for query, expected in cases.items():
        resp = field.get(f"/api/time-entries/summary?{query}")
        assert resp.status_code == 200, (query, resp.text)
        assert _normalized(resp.json()) == expected, query


def test_field_total_count_never_includes_colleagues_or_foreign_orders(data, client):
    field = client("field", employee_id=data.me)
    for query, expected in {f"order_id={data.order_a}": "1", f"order_id={data.order_c}": "0",
                            f"employee_id={data.colleague}": "1", "": "1"}.items():
        resp = field.get(f"/api/time-entries?{query}")
        assert resp.status_code == 200, (query, resp.text)
        assert resp.headers["X-Total-Count"] == expected, query
        assert len(resp.json()) == int(expected) and all(r["employee_id"] == data.me for r in resp.json())


def test_office_sees_colleagues_in_summary(data, client):
    # Gegenstück zum Angriffstest: dieselbe Abfrage zählt für das Büro beide Mitarbeiter.
    for role in OFFICE_ROLES:
        body = client(role).get(f"/api/time-entries/summary?employee_id={data.colleague}&order_id={data.order_c}").json()
        assert body["entry_count"] == 1000 and Decimal(str(body["total_hours"])) == Decimal("1000.00"), role


def test_field_without_employee_link_gets_403_for_summary(data, client):
    resp = client("field", employee_id=None).get("/api/time-entries/summary")
    assert resp.status_code == 403


def test_no_wage_fields_in_summary_or_list_for_any_role(data, client):
    for role in ALL_ROLES:
        c = client(role, employee_id=data.me if role == "field" else None)
        for url in (f"/api/time-entries/summary?order_id={data.order_a}", "/api/time-entries/summary",
                    f"/api/time-entries?order_id={data.order_a}&limit=5"):
            resp = c.get(url)
            assert resp.status_code == 200, (role, url, resp.text)
            keys = _recursive_keys(resp.json())
            assert not keys & WAGE_KEYS, (role, url, keys & WAGE_KEYS)
            assert not [k for k in keys if re.search(r"wage|salary|lohn|gehalt|compensation", k, re.I)], (role, url)


# ---------------------------------------------------------------------------
# 4. Jede Oberfläche mit einer Liste aus GET /api/time-entries zeigt "Liste gekürzt"
# ---------------------------------------------------------------------------

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
LIST_CALL = re.compile(r"/api/time-entries\?")
WRAPPED = re.compile(r"fetchTimeEntries\(\s*[`'\"]\Z")


def _code(path):
    text = path.read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", re.sub(r"\{#.*?#\}", "", text, flags=re.S), flags=re.S)


def test_every_page_listing_time_entries_reads_total_and_shows_truncation_notice():
    pages = {}
    for path in sorted(TEMPLATES.glob("*.html")):
        code = _code(path)
        calls = [m.start() for m in LIST_CALL.finditer(code)]
        if calls and path.name != "_time_entries_list.html":
            pages[path.name] = (code, calls)
    assert {"service_reports.html", "project_folder.html", "time_backoffice.html", "time_tracking.html",
            "time_tracking_field.html", "field_timesheet.html"} <= set(pages)
    for name, (code, calls) in pages.items():
        unwrapped = [code[p - 60:p + 40] for p in calls if not WRAPPED.search(code[max(0, p - 40):p])]
        assert not unwrapped, (name, unwrapped)  # jede Liste über fetchTimeEntries() -> X-Total-Count
        assert '{% include "_time_entries_list.html" %}' in code, name
        assert code.count("timeEntriesTruncatedNotice(") >= len(calls), name


def test_pages_with_sums_take_them_from_summary_endpoint():
    for name in ("service_reports.html", "project_folder.html", "dashboard.html", "order.html"):
        assert "/api/time-entries/summary?" in _code(TEMPLATES / name), name
