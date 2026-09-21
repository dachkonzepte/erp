"""Version 1.5.12 -- Buchhaltung Stufe 1: Eingangsrechnungen erfassen und ablegen (siehe
CLAUDE.md "Buchhaltung" für die volle Herleitung). Deckt ab: Netto/Steuer/Brutto (Gesamtbetrag
UND je Position), die optionale Positions-Aufschlüsselung mit Summen-Abgleich, die
Exakt-eine-Zuordnung (Projekt/Betriebsmittel/Kostenposten), Skonto-Fälligkeit/Überfälligkeit,
den automatisch berechneten (nie gespeicherten) Überfällig-Status, den vollständigen
CRUD-Zyklus samt Beleg-Ablage, die On-Demand-Skonto-Erinnerung mit
min_visible_role=ROLE_OFFICE_FINANZEN, und den abschließend verlangten Angriffstest:
buero_auftrag und field kommen über KEINEN Weg an die Eingangsrechnungen -- Liste, Einzelabruf,
Beleg (auch über geratene IDs), die Skonto-Aufgaben. Rekursiver Schlüssel-Scan, je ein
Testkonto pro Rolle."""

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.incoming_invoices import (
    MODULE_KEY, check_due_skonto_and_create_reminders, create_invoice, delete_invoice,
    get_invoice, get_or_create_incoming_invoice_settings, gross_amount, invoice_gross_amount,
    is_overdue, is_skonto_due, is_skonto_overdue, list_invoices, open_liabilities_summary,
    remove_invoice_document, set_invoice_document, update_incoming_invoice_settings, update_invoice,
)
from app.models import Customer, EnabledModule, IncomingInvoice, Project, Supplier
from app.operational_assets import create_asset
from app.permissions import ROLE_OFFICE_FINANZEN
from app.project_pipeline_columns import default_pipeline_column_id
from app.recurring_costs import create_cost
from app.routers.incoming_invoices import router as incoming_invoices_router
from app.routers.tasks import router as tasks_router

ALL_ROLES = ("field", "buero_auftrag", "buero_finanzen", "admin")
FORBIDDEN_KEYS = {"supplier_name", "net_amount", "gross_amount", "payment_status", "display_status"}


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _recursive_keys(value, keys=None):
    if keys is None:
        keys = set()
    if isinstance(value, dict):
        for k, v in value.items():
            keys.add(k)
            _recursive_keys(v, keys)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _recursive_keys(item, keys)
    elif isinstance(value, str):
        s = value.strip()
        if s[:1] in "{[":
            try:
                parsed = json.loads(s)
            except (TypeError, ValueError):
                return keys
            _recursive_keys(parsed, keys)
    return keys


def _seed_supplier(db, name="Musterbaustoffe GmbH"):
    supplier = Supplier(name=name)
    db.add(supplier)
    db.commit()
    return supplier.id


def _seed_project(db):
    customer = Customer(name="Testkunde", last_name="Testkunde")
    db.add(customer)
    db.commit()
    project = Project(
        project_number="P-TEST-0001", customer_id=customer.id, name="Testprojekt",
        pipeline_column_id=default_pipeline_column_id(db),
    )
    db.add(project)
    db.commit()
    return project.id


def _seed_asset(db):
    return create_asset(db, {"name": "Bagger 1"})["id"]


def _seed_recurring_cost(db):
    return create_cost(db, {
        "label": "Leasing Bagger 1", "net_amount": "500.00", "billing_interval": "monatlich",
    })["id"]


def _base_payload(supplier_id, **overrides):
    """Für DIREKTE Aufrufe von create_invoice()/update_invoice() -- diese Funktionen laufen
    ohne die Pydantic-Schicht des echten Endpunkts, die sonst ISO-Strings in echte date-Objekte
    parst, deshalb hier bereits echte date-Objekte statt Strings."""
    payload = {
        "supplier_id": supplier_id, "supplier_invoice_number": "RE-2026-001",
        "invoice_date": date(2026, 9, 1), "net_amount": "500.00", "tax_rate_pct": "19.00",
        "due_date": None, "skonto_percent": None, "skonto_deadline": None, "payment_status": "offen",
        "payment_date": None, "project_id": None, "asset_id": None, "recurring_cost_id": None,
        "account_code": None, "notes": None, "items": [],
    }
    payload.update(overrides)
    return payload


def _json_payload(supplier_id, **overrides):
    """Für Router-Aufrufe (client.post(json=...)) -- dieselbe Grundlage wie _base_payload(),
    aber alle date-Felder als ISO-String (JSON kennt keine date-Objekte; die Pydantic-Schicht
    des echten Endpunkts parst sie beim Empfang zurück)."""
    payload = _base_payload(supplier_id, **overrides)
    for field in ("invoice_date", "due_date", "skonto_deadline", "payment_date"):
        if isinstance(payload.get(field), date):
            payload[field] = payload[field].isoformat()
    return payload


# --- Netto/Steuer/Brutto ---

def test_gross_amount_pure_derivation():
    assert gross_amount(Decimal("100"), Decimal("19.00")) == Decimal("119.00")
    assert gross_amount(Decimal("100"), Decimal("0.00")) == Decimal("100.00")


def test_invoice_gross_amount_uses_header_without_items_and_sums_items_with_own_rates():
    db = db_session()
    supplier_id = _seed_supplier(db)
    without_items = create_invoice(db, _base_payload(supplier_id, net_amount="1000.00", tax_rate_pct="19.00"))
    assert without_items["gross_amount"] == Decimal("1190.00")

    with_items = create_invoice(db, _base_payload(
        supplier_id, net_amount="1000.00", tax_rate_pct="19.00",
        items=[
            {"description": "Material", "net_amount": "800.00", "tax_rate_pct": "19.00"},
            {"description": "Steuerfreie Position", "net_amount": "200.00", "tax_rate_pct": "0.00"},
        ],
    ))
    # 800*1.19 + 200*1.00 = 952 + 200 = 1152, NICHT 1000*1.19=1190 -- jede Position mit ihrem
    # eigenen Satz, kein gemeinsamer Header-Satz bei gemischten Positionen.
    assert with_items["gross_amount"] == Decimal("1152.00")


# --- Positionen: optionale Aufschlüsselung, Summen-Abgleich ---

def test_items_are_optional_simple_invoice_stays_a_single_total():
    db = db_session()
    supplier_id = _seed_supplier(db)
    created = create_invoice(db, _base_payload(supplier_id))
    assert created["items"] == []
    assert created["net_amount"] == Decimal("500.00")


def test_matching_item_sum_is_accepted():
    db = db_session()
    supplier_id = _seed_supplier(db)
    created = create_invoice(db, _base_payload(
        supplier_id, net_amount="300.00",
        items=[
            {"description": "A", "net_amount": "200.00", "tax_rate_pct": "19.00"},
            {"description": "B", "net_amount": "100.00", "tax_rate_pct": "0.00"},
        ],
    ))
    assert len(created["items"]) == 2
    assert {i["description"] for i in created["items"]} == {"A", "B"}


def test_mismatched_item_sum_is_rejected_not_silently_allowed():
    db = db_session()
    supplier_id = _seed_supplier(db)
    with pytest.raises(ValueError, match="Summe der Positionen"):
        create_invoice(db, _base_payload(
            supplier_id, net_amount="300.00",
            items=[{"description": "A", "net_amount": "250.00", "tax_rate_pct": "19.00"}],
        ))


def test_update_fully_replaces_items():
    db = db_session()
    supplier_id = _seed_supplier(db)
    created = create_invoice(db, _base_payload(
        supplier_id, net_amount="300.00",
        items=[{"description": "Alt", "net_amount": "300.00", "tax_rate_pct": "19.00"}],
    ))
    updated = update_invoice(db, created["id"], _base_payload(
        supplier_id, net_amount="300.00",
        items=[
            {"description": "Neu 1", "net_amount": "100.00", "tax_rate_pct": "19.00"},
            {"description": "Neu 2", "net_amount": "200.00", "tax_rate_pct": "0.00"},
        ],
    ))
    assert [i["description"] for i in updated["items"]] == ["Neu 1", "Neu 2"]


def test_update_can_remove_all_items_back_to_a_single_total():
    db = db_session()
    supplier_id = _seed_supplier(db)
    created = create_invoice(db, _base_payload(
        supplier_id, net_amount="300.00",
        items=[{"description": "A", "net_amount": "300.00", "tax_rate_pct": "19.00"}],
    ))
    updated = update_invoice(db, created["id"], _base_payload(supplier_id, net_amount="300.00", items=[]))
    assert updated["items"] == []


# --- Zuordnung: höchstens eine von Projekt/Betriebsmittel/Kostenposten ---

def test_single_optional_assignment_project_only():
    db = db_session()
    supplier_id = _seed_supplier(db)
    project_id = _seed_project(db)
    created = create_invoice(db, _base_payload(supplier_id, project_id=project_id))
    assert created["project_id"] == project_id
    assert created["asset_id"] is None
    assert created["recurring_cost_id"] is None


def test_two_assignments_at_once_are_rejected():
    db = db_session()
    supplier_id = _seed_supplier(db)
    project_id = _seed_project(db)
    asset_id = _seed_asset(db)
    with pytest.raises(ValueError, match="nur einem"):
        create_invoice(db, _base_payload(supplier_id, project_id=project_id, asset_id=asset_id))


def test_invoice_can_remain_unassigned():
    db = db_session()
    supplier_id = _seed_supplier(db)
    created = create_invoice(db, _base_payload(supplier_id))
    assert created["project_id"] is None and created["asset_id"] is None and created["recurring_cost_id"] is None


def test_recurring_cost_assignment_never_touches_the_plan():
    """Bestätigte, dauerhafte Grenze (siehe CLAUDE.md "Buchhaltung"): eine Eingangsrechnung
    ändert nie RecurringCost.annual_amount/den Verrechnungssatz."""
    db = db_session()
    supplier_id = _seed_supplier(db)
    cost_id = _seed_recurring_cost(db)
    from app.recurring_costs import get_cost
    before = get_cost(db, cost_id)["annual_amount"]
    create_invoice(db, _base_payload(supplier_id, net_amount="9999.00", recurring_cost_id=cost_id))
    after = get_cost(db, cost_id)["annual_amount"]
    assert before == after == Decimal("6000.00")


# --- Überfällig: nie gespeichert, immer berechnet (konsistent mit Invoice) ---

def test_is_overdue_only_when_open_and_past_due_date():
    today = date(2026, 9, 21)
    assert is_overdue("offen", date(2026, 9, 1), today=today) is True
    assert is_overdue("offen", date(2026, 12, 1), today=today) is False
    assert is_overdue("bezahlt", date(2026, 9, 1), today=today) is False
    assert is_overdue("offen", None, today=today) is False


def test_payment_status_column_never_stores_ueberfaellig():
    db = db_session()
    supplier_id = _seed_supplier(db)
    created = create_invoice(db, _base_payload(supplier_id, due_date=date(2020, 1, 1)))
    row = db.get(IncomingInvoice, created["id"])
    assert row.payment_status == "offen"
    assert created["display_status"] == "ueberfaellig"
    assert created["is_overdue"] is True


def test_paying_an_invoice_clears_stale_overdue_status():
    db = db_session()
    supplier_id = _seed_supplier(db)
    created = create_invoice(db, _base_payload(supplier_id, due_date=date(2020, 1, 1)))
    assert get_invoice(db, created["id"])["display_status"] == "ueberfaellig"
    paid = update_invoice(db, created["id"], _base_payload(
        supplier_id, due_date=date(2020, 1, 1), payment_status="bezahlt", payment_date=date.today(),
    ))
    assert paid["display_status"] == "bezahlt"
    assert paid["is_overdue"] is False


def test_payment_date_is_cleared_when_status_leaves_bezahlt():
    db = db_session()
    supplier_id = _seed_supplier(db)
    created = create_invoice(db, _base_payload(
        supplier_id, payment_status="bezahlt", payment_date=date.today(),
    ))
    assert created["payment_date"] is not None
    reopened = update_invoice(db, created["id"], _base_payload(supplier_id, payment_status="offen"))
    assert reopened["payment_date"] is None


# --- Skonto ---

def test_skonto_due_and_overdue_only_while_open():
    today = date(2026, 9, 21)
    assert is_skonto_due(date(2026, 9, 24), "offen", 5, today=today) is True
    assert is_skonto_due(date(2026, 10, 24), "offen", 5, today=today) is False
    assert is_skonto_due(date(2026, 9, 24), "bezahlt", 5, today=today) is False
    assert is_skonto_overdue(date(2026, 9, 1), "offen", today=today) is True
    assert is_skonto_overdue(date(2026, 9, 1), "bezahlt", today=today) is False


def test_check_due_skonto_creates_finance_task_and_is_idempotent():
    db = db_session()
    supplier_id = _seed_supplier(db)
    created = create_invoice(db, _base_payload(
        supplier_id, skonto_percent="2.00", skonto_deadline=date.today() + timedelta(days=2),
    ))
    reminded_first = check_due_skonto_and_create_reminders(db)
    assert created["id"] in reminded_first
    reminded_second = check_due_skonto_and_create_reminders(db)
    assert created["id"] not in reminded_second  # Idempotenz -- kein zweites Mal


def test_check_due_skonto_reminds_again_after_deadline_actually_changes():
    db = db_session()
    supplier_id = _seed_supplier(db)
    created = create_invoice(db, _base_payload(
        supplier_id, skonto_percent="2.00", skonto_deadline=date.today() + timedelta(days=2),
    ))
    check_due_skonto_and_create_reminders(db)
    update_invoice(db, created["id"], _base_payload(
        supplier_id, skonto_percent="2.00", skonto_deadline=date.today() + timedelta(days=1),
    ))
    reminded_again = check_due_skonto_and_create_reminders(db)
    assert created["id"] in reminded_again


# --- CRUD ---

def test_create_get_update_delete_invoice():
    db = db_session()
    supplier_id = _seed_supplier(db)
    created = create_invoice(db, _base_payload(supplier_id))
    assert created["supplier_name"] == "Musterbaustoffe GmbH"

    fetched = get_invoice(db, created["id"])
    assert fetched["id"] == created["id"]

    updated = update_invoice(db, created["id"], _base_payload(supplier_id, net_amount="600.00"))
    assert updated["net_amount"] == Decimal("600.00")

    assert delete_invoice(db, created["id"]) is True
    assert get_invoice(db, created["id"]) is None
    assert delete_invoice(db, 99999) is False


def test_create_invoice_rejects_unknown_supplier():
    db = db_session()
    with pytest.raises(ValueError):
        create_invoice(db, _base_payload(99999))


def test_create_invoice_rejects_unknown_tax_rate():
    db = db_session()
    supplier_id = _seed_supplier(db)
    with pytest.raises(ValueError):
        create_invoice(db, _base_payload(supplier_id, tax_rate_pct="10.00"))


def test_list_invoices_filters_by_status_supplier_and_date_range():
    db = db_session()
    supplier_a = _seed_supplier(db, "Lieferant A")
    supplier_b = _seed_supplier(db, "Lieferant B")
    create_invoice(db, _base_payload(supplier_a, invoice_date=date(2026, 1, 15)))
    create_invoice(db, _base_payload(supplier_b, invoice_date=date(2026, 6, 15), payment_status="bezahlt"))

    assert len(list_invoices(db)) == 2
    assert len(list_invoices(db, supplier_id=supplier_a)) == 1
    assert len(list_invoices(db, payment_status="bezahlt")) == 1
    assert len(list_invoices(db, date_from=date(2026, 6, 1))) == 1
    assert len(list_invoices(db, date_to=date(2026, 3, 1))) == 1


def test_open_liabilities_summary_sums_only_open_invoices():
    db = db_session()
    supplier_id = _seed_supplier(db)
    create_invoice(db, _base_payload(supplier_id, net_amount="100.00", tax_rate_pct="19.00"))
    create_invoice(db, _base_payload(supplier_id, net_amount="500.00", payment_status="bezahlt"))
    summary = open_liabilities_summary(db)
    assert summary["open_count"] == 1
    assert summary["open_gross_total"] == Decimal("119.00")


def test_document_set_and_remove():
    db = db_session()
    supplier_id = _seed_supplier(db)
    created = create_invoice(db, _base_payload(supplier_id))
    with_doc = set_invoice_document(db, created["id"], stored_filename="abc.pdf", original_filename="Beleg.pdf")
    assert with_doc["has_document"] is True
    assert with_doc["document_original_name"] == "Beleg.pdf"
    without_doc = remove_invoice_document(db, created["id"])
    assert without_doc["has_document"] is False


def test_settings_roundtrip():
    db = db_session()
    default_settings = get_or_create_incoming_invoice_settings(db)
    assert default_settings.skonto_reminder_lead_days == 5
    updated = update_incoming_invoice_settings(db, 10)
    assert updated["skonto_reminder_lead_days"] == 10


# --- Angriffstest: buero_auftrag/field kommen an keinen Teil der Eingangsrechnungen ---

def _seed_invoice_and_finance_task(threaded_db_session, router_test_client):
    db = threaded_db_session
    supplier_id = _seed_supplier(db)
    client = router_test_client(db, incoming_invoices_router, role="buero_finanzen")
    resp = client.post("/api/incoming-invoices", json=_json_payload(
        supplier_id, skonto_percent="2.00", skonto_deadline=str(date.today() + timedelta(days=1)),
    ))
    assert resp.status_code == 200, resp.text
    invoice_id = resp.json()["id"]
    check_due_skonto_and_create_reminders(db)
    return invoice_id


def test_incoming_invoices_list_and_detail_require_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    invoice_id = _seed_invoice_and_finance_task(threaded_db_session, router_test_client)
    for role in ALL_ROLES:
        client = router_test_client(db, incoming_invoices_router, role=role)
        list_resp = client.get("/api/incoming-invoices")
        detail_resp = client.get(f"/api/incoming-invoices/{invoice_id}")
        if role in ("buero_finanzen", "admin"):
            assert list_resp.status_code == 200, (role, list_resp.text)
            assert detail_resp.status_code == 200, (role, detail_resp.text)
            assert _recursive_keys(list_resp.json()) & FORBIDDEN_KEYS
        else:
            assert list_resp.status_code == 403, (role, list_resp.text)
            assert detail_resp.status_code == 403, (role, detail_resp.text)
            assert not (_recursive_keys(list_resp.json()) & FORBIDDEN_KEYS)
            assert not (_recursive_keys(detail_resp.json()) & FORBIDDEN_KEYS)
    # Auch mit einer geratenen, gar nicht existierenden ID -- weiterhin 403 statt 404, bevor
    # irgendeine Geschäftslogik läuft.
    for role in ("buero_auftrag", "field"):
        client = router_test_client(db, incoming_invoices_router, role=role)
        assert client.get("/api/incoming-invoices/99999").status_code == 403, role


def test_incoming_invoices_open_liabilities_requires_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    _seed_invoice_and_finance_task(threaded_db_session, router_test_client)
    for role in ALL_ROLES:
        client = router_test_client(db, incoming_invoices_router, role=role)
        resp = client.get("/api/incoming-invoices/open-liabilities")
        expected = 200 if role in ("buero_finanzen", "admin") else 403
        assert resp.status_code == expected, (role, resp.text)
        if expected == 403:
            assert not (_recursive_keys(resp.json()) & {"open_gross_total", "skonto_due"})


def test_incoming_invoices_write_and_settings_require_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    supplier_id = _seed_supplier(db)
    for role in ALL_ROLES:
        client = router_test_client(db, incoming_invoices_router, role=role)
        expected = 200 if role in ("buero_finanzen", "admin") else 403
        assert client.post("/api/incoming-invoices", json=_json_payload(supplier_id)).status_code == expected, role
        assert client.get("/api/incoming-invoice-settings").status_code == expected, role
        assert client.put("/api/incoming-invoice-settings", json={"skonto_reminder_lead_days": 3}).status_code == expected, role
        assert client.post("/api/incoming-invoices/check-due").status_code == expected, role


def test_incoming_invoice_document_never_reachable_for_buero_auftrag_or_field_even_with_guessed_id(
    threaded_db_session, router_test_client, tmp_path, monkeypatch,
):
    from app import incoming_invoice_documents as docs_module
    monkeypatch.setattr(docs_module, "DOCUMENT_ROOT", tmp_path)

    db = threaded_db_session
    invoice_id = _seed_invoice_and_finance_task(threaded_db_session, router_test_client)
    finanzen_client = router_test_client(db, incoming_invoices_router, role="buero_finanzen")
    upload_resp = finanzen_client.post(
        f"/api/incoming-invoices/{invoice_id}/document",
        files={"file": ("beleg.pdf", b"dummy", "application/pdf")},
    )
    assert upload_resp.status_code == 200, upload_resp.text

    for role in ("buero_auftrag", "field"):
        client = router_test_client(db, incoming_invoices_router, role=role)
        assert client.get(f"/api/incoming-invoices/{invoice_id}/document/file").status_code == 403, role
        assert client.delete(f"/api/incoming-invoices/{invoice_id}/document").status_code == 403, role
        # Auch mit einer geratenen, gar nicht existierenden Rechnungs-ID -- dieselbe 403.
        assert client.get("/api/incoming-invoices/99999/document/file").status_code == 403, role
        assert client.post(
            f"/api/incoming-invoices/{invoice_id}/document",
            files={"file": ("x.pdf", b"x", "application/pdf")},
        ).status_code == 403, role


def test_finance_addressed_skonto_task_never_visible_or_claimable_for_buero_auftrag_or_field(
    threaded_db_session, router_test_client,
):
    db = threaded_db_session
    _seed_invoice_and_finance_task(threaded_db_session, router_test_client)

    finanzen_list = router_test_client(db, tasks_router, role="buero_finanzen").get("/api/tasks?unassigned_only=true")
    assert finanzen_list.status_code == 200
    finance_task_ids = [t["id"] for t in finanzen_list.json() if t.get("min_visible_role") == ROLE_OFFICE_FINANZEN]
    assert finance_task_ids, "Vorbedingung: die Skonto-Erinnerungs-Aufgabe muss existieren"
    task_id = finance_task_ids[0]

    auftrag_client = router_test_client(db, tasks_router, role="buero_auftrag", employee_id=1)
    auftrag_list = auftrag_client.get("/api/tasks?unassigned_only=true")
    assert auftrag_list.status_code == 200
    assert task_id not in [t["id"] for t in auftrag_list.json()]
    assert not any("Skonto" in (t.get("title") or "") for t in auftrag_list.json())
    claim_resp = auftrag_client.post(f"/api/tasks/{task_id}/claim")
    assert claim_resp.status_code == 403, claim_resp.text

    field_client = router_test_client(db, tasks_router, role="field")
    assert field_client.get("/api/tasks?unassigned_only=true").status_code == 403
    assert field_client.post(f"/api/tasks/{task_id}/claim").status_code == 403

    finanzen_claim = router_test_client(db, tasks_router, role="buero_finanzen", employee_id=1).post(
        f"/api/tasks/{task_id}/claim"
    )
    assert finanzen_claim.status_code == 200, finanzen_claim.text


def test_module_disabled_blocks_every_role_including_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    db.add(EnabledModule(module_key=MODULE_KEY, enabled=False))
    db.commit()
    for role in ALL_ROLES:
        client = router_test_client(db, incoming_invoices_router, role=role)
        resp = client.get("/api/incoming-invoices")
        assert resp.status_code == 403, (role, resp.text)
