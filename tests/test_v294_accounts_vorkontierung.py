"""Version 1.6.1 -- Buchhaltung Stufe 2, erster Teil: Kontenstamm mit manueller Pflege und
Vorkontierung der Eingangsrechnungen (siehe CLAUDE.md "Buchhaltung" -> "Kontenstamm" für die
volle Herleitung). Deckt ab: den Kontenstamm selbst (Account -- Kontonummer/Bezeichnung/
optionaler Standard-Steuersatz, Eindeutigkeit, aktiv/archiviert, KEIN Startbestand, KEIN
Löschen), die Umstellung von IncomingInvoice(Item).account_code (Freitext) auf account_id (FK)
inkl. Validierung, is_invoice_accounted() (Header ODER je Position, je nachdem ob Positionen
existieren), dass der Standard-Steuersatz eines Kontos NIE serverseitig auf die Rechnung/
Position übertragen wird (reiner Client-Vorschlag), und den abschließend verlangten
Angriffstest: buero_auftrag/field kommen an keinen Teil des Kontenstamms."""

import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts import (
    ACCOUNT_TAX_RATES, account_to_dict, create_account, get_account, list_accounts, update_account,
)
from app.database import Base
from app.incoming_invoices import create_invoice, get_invoice, is_invoice_accounted, update_invoice
from app.models import Account, EnabledModule, Supplier
from app.routers.accounts import router as accounts_router
from app.routers.incoming_invoices import router as incoming_invoices_router

ALL_ROLES = ("field", "buero_auftrag", "buero_finanzen", "admin")
FORBIDDEN_KEYS = {"account_number", "label", "default_tax_rate_pct"}


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


def _seed_supplier(db):
    supplier = Supplier(name="Musterbaustoffe GmbH")
    db.add(supplier)
    db.commit()
    return supplier.id


def _invoice_payload(supplier_id, **overrides):
    payload = {
        "supplier_id": supplier_id, "supplier_invoice_number": "RE-2026-001",
        "invoice_date": date(2026, 9, 1), "net_amount": "500.00", "tax_rate_pct": "19.00",
        "due_date": None, "skonto_percent": None, "skonto_deadline": None, "payment_status": "offen",
        "payment_date": None, "project_id": None, "asset_id": None, "recurring_cost_id": None,
        "account_id": None, "notes": None, "items": [],
    }
    payload.update(overrides)
    return payload


# --- Kontenstamm ---

def test_no_default_accounts_exist_on_a_fresh_database():
    """Bewusst KEIN Startbestand -- siehe CLAUDE.md "Buchhaltung" -> "Kontenstamm"."""
    db = db_session()
    assert list_accounts(db) == []


def test_create_get_update_account():
    db = db_session()
    created = create_account(db, account_number="4200", label="Wareneinkauf", default_tax_rate_pct=Decimal("19.00"))
    assert created["account_number"] == "4200"
    assert created["active"] is True

    fetched = get_account(db, created["id"])
    assert fetched["label"] == "Wareneinkauf"

    updated = update_account(
        db, created["id"], account_number="4200", label="Wareneinkauf (Material)",
        default_tax_rate_pct=Decimal("0.00"), active=False,
    )
    assert updated["label"] == "Wareneinkauf (Material)"
    assert updated["default_tax_rate_pct"] == Decimal("0.00")
    assert updated["active"] is False


def test_account_number_must_be_unique():
    db = db_session()
    create_account(db, account_number="4200", label="Wareneinkauf")
    with pytest.raises(ValueError, match="bereits vergeben"):
        create_account(db, account_number="4200", label="Zweites Konto")


def test_account_number_uniqueness_excludes_self_on_update():
    db = db_session()
    a = create_account(db, account_number="4200", label="Wareneinkauf")
    updated = update_account(db, a["id"], account_number="4200", label="Wareneinkauf (umbenannt)")
    assert updated["label"] == "Wareneinkauf (umbenannt)"


def test_create_account_rejects_unknown_tax_rate():
    db = db_session()
    with pytest.raises(ValueError, match="Steuersatz"):
        create_account(db, account_number="4200", label="X", default_tax_rate_pct=Decimal("10.00"))


def test_default_tax_rate_pct_is_optional():
    db = db_session()
    created = create_account(db, account_number="6400", label="Versicherungen")
    assert created["default_tax_rate_pct"] is None


def test_account_tax_rates_match_the_rest_of_the_project():
    assert ACCOUNT_TAX_RATES == (Decimal("19.00"), Decimal("7.00"), Decimal("0.00"))


def test_no_delete_function_exists_only_archive_via_active_flag():
    """Betreibervorgabe: nie löschen, nur archivieren/aktivieren."""
    import app.accounts as accounts_module
    assert not hasattr(accounts_module, "delete_account")


def test_list_accounts_include_inactive_toggle():
    db = db_session()
    create_account(db, account_number="4200", label="Aktiv")
    create_account(db, account_number="6400", label="Archiviert", active=False)
    assert len(list_accounts(db, include_inactive=True)) == 2
    active_only = list_accounts(db, include_inactive=False)
    assert len(active_only) == 1
    assert active_only[0]["account_number"] == "4200"


# --- Vorkontierung ---

def test_invoice_can_be_created_and_updated_without_any_account():
    db = db_session()
    supplier_id = _seed_supplier(db)
    created = create_invoice(db, _invoice_payload(supplier_id))
    assert created["account_id"] is None
    assert created["is_accounted"] is False


def test_header_account_makes_a_simple_invoice_accounted():
    db = db_session()
    supplier_id = _seed_supplier(db)
    account = create_account(db, account_number="4200", label="Wareneinkauf")
    created = create_invoice(db, _invoice_payload(supplier_id, account_id=account["id"]))
    assert created["is_accounted"] is True
    assert created["account_number"] == "4200"
    assert created["account_label"] == "Wareneinkauf"


def test_with_items_every_item_must_carry_an_account_to_count_as_accounted():
    db = db_session()
    supplier_id = _seed_supplier(db)
    account = create_account(db, account_number="4200", label="Wareneinkauf")
    partially = create_invoice(db, _invoice_payload(
        supplier_id, net_amount="300.00",
        items=[
            {"description": "A", "net_amount": "200.00", "tax_rate_pct": "19.00", "account_id": account["id"]},
            {"description": "B", "net_amount": "100.00", "tax_rate_pct": "0.00", "account_id": None},
        ],
    ))
    assert partially["is_accounted"] is False

    fully = update_invoice(db, partially["id"], _invoice_payload(
        supplier_id, net_amount="300.00",
        items=[
            {"description": "A", "net_amount": "200.00", "tax_rate_pct": "19.00", "account_id": account["id"]},
            {"description": "B", "net_amount": "100.00", "tax_rate_pct": "0.00", "account_id": account["id"]},
        ],
    ))
    assert fully["is_accounted"] is True
    assert all(i["account_number"] == "4200" for i in fully["items"])


def test_header_account_is_irrelevant_once_items_exist():
    """is_invoice_accounted() prüft bei vorhandenen Positionen ausschließlich diese -- ein
    (ggf. veraltetes) Header-Konto macht eine aufgeschlüsselte Rechnung nicht "kontiert"."""
    db = db_session()
    supplier_id = _seed_supplier(db)
    account = create_account(db, account_number="4200", label="Wareneinkauf")
    created = create_invoice(db, _invoice_payload(
        supplier_id, account_id=account["id"], net_amount="300.00",
        items=[{"description": "A", "net_amount": "300.00", "tax_rate_pct": "19.00", "account_id": None}],
    ))
    assert is_invoice_accounted.__doc__ is not None  # Dokumentation vorhanden
    assert created["is_accounted"] is False


def test_create_invoice_rejects_unknown_header_account():
    db = db_session()
    supplier_id = _seed_supplier(db)
    with pytest.raises(ValueError, match="Konto"):
        create_invoice(db, _invoice_payload(supplier_id, account_id=99999))


def test_create_invoice_rejects_unknown_item_account():
    db = db_session()
    supplier_id = _seed_supplier(db)
    with pytest.raises(ValueError, match="Konto"):
        create_invoice(db, _invoice_payload(
            supplier_id, net_amount="300.00",
            items=[{"description": "A", "net_amount": "300.00", "tax_rate_pct": "19.00", "account_id": 99999}],
        ))


def test_account_default_tax_rate_is_never_applied_server_side():
    """Betreibervorgabe: "der hinterlegte Standard-Steuersatz ... wird beim Wählen
    vorgeschlagen, aber ist übersteuerbar -- die Rechnung entscheidet, nicht das Konto." Nur
    ein Client-Vorschlag (siehe incoming_invoices.html::applyAccountDefaultTaxRate()) -- die
    Business-Logik übernimmt den Kontosatz nie automatisch."""
    db = db_session()
    supplier_id = _seed_supplier(db)
    account = create_account(db, account_number="6400", label="Versicherungen", default_tax_rate_pct=Decimal("0.00"))
    created = create_invoice(db, _invoice_payload(supplier_id, account_id=account["id"], tax_rate_pct="19.00"))
    assert created["tax_rate_pct"] == Decimal("19.00")


def test_archived_account_stays_valid_on_an_already_accounted_invoice():
    """Ein bereits verwendetes Konto darf archiviert werden, ohne die bestehende Zuordnung zu
    zerstören -- archivieren blendet es nur aus künftigen Auswahllisten aus."""
    db = db_session()
    supplier_id = _seed_supplier(db)
    account = create_account(db, account_number="4200", label="Wareneinkauf")
    created = create_invoice(db, _invoice_payload(supplier_id, account_id=account["id"]))
    update_account(db, account["id"], account_number="4200", label="Wareneinkauf", active=False)
    fetched = get_invoice(db, created["id"])
    assert fetched["account_id"] == account["id"]
    assert fetched["is_accounted"] is True


# --- Angriffstest: buero_auftrag/field kommen an keinen Teil des Kontenstamms ---

def test_accounts_endpoints_require_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    for role in ALL_ROLES:
        client = router_test_client(db, accounts_router, role=role)
        expected = 200 if role in ("buero_finanzen", "admin") else 403
        list_resp = client.get("/api/accounts")
        assert list_resp.status_code == expected, (role, list_resp.text)
        create_resp = client.post("/api/accounts", json={"account_number": f"42{role[:2]}", "label": "Test", "active": True})
        assert create_resp.status_code == expected, (role, create_resp.text)
        if expected == 403:
            assert not (_recursive_keys(list_resp.json()) & FORBIDDEN_KEYS)
            assert not (_recursive_keys(create_resp.json()) & FORBIDDEN_KEYS)


def test_accounts_detail_and_update_require_buero_finanzen_even_with_guessed_id(threaded_db_session, router_test_client):
    db = threaded_db_session
    finanzen_client = router_test_client(db, accounts_router, role="buero_finanzen")
    created = finanzen_client.post("/api/accounts", json={"account_number": "4200", "label": "Wareneinkauf", "active": True})
    assert created.status_code == 200, created.text
    account_id = created.json()["id"]

    for role in ("buero_auftrag", "field"):
        client = router_test_client(db, accounts_router, role=role)
        assert client.get(f"/api/accounts/{account_id}").status_code == 403, role
        assert client.put(f"/api/accounts/{account_id}", json={"account_number": "4200", "label": "x", "active": True}).status_code == 403, role
        # Auch mit einer geratenen, gar nicht existierenden ID -- dieselbe 403.
        assert client.get("/api/accounts/99999").status_code == 403, role


def test_incoming_invoice_with_account_still_hides_account_fields_from_buero_auftrag_and_field(
    threaded_db_session, router_test_client,
):
    db = threaded_db_session
    finanzen_client = router_test_client(db, accounts_router, role="buero_finanzen")
    account_resp = finanzen_client.post("/api/accounts", json={"account_number": "4200", "label": "Wareneinkauf", "active": True})
    account_id = account_resp.json()["id"]

    supplier_id = _seed_supplier(db)
    invoices_client = router_test_client(db, incoming_invoices_router, role="buero_finanzen")
    payload = _invoice_payload(supplier_id, account_id=account_id)
    payload["invoice_date"] = payload["invoice_date"].isoformat()
    created = invoices_client.post("/api/incoming-invoices", json=payload)
    assert created.status_code == 200, created.text
    invoice_id = created.json()["id"]

    for role in ("buero_auftrag", "field"):
        client = router_test_client(db, incoming_invoices_router, role=role)
        detail_resp = client.get(f"/api/incoming-invoices/{invoice_id}")
        assert detail_resp.status_code == 403, role
        assert not (_recursive_keys(detail_resp.json()) & FORBIDDEN_KEYS)


def test_module_disabled_blocks_accounts_for_every_role_including_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    db.add(EnabledModule(module_key="buchhaltung", enabled=False))
    db.commit()
    for role in ALL_ROLES:
        client = router_test_client(db, accounts_router, role=role)
        assert client.get("/api/accounts").status_code == 403, role
