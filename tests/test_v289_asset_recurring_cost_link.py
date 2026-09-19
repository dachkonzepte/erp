"""Nachbesserung "Betriebsmittel-Kosten fest als Kostenposten" (siehe CLAUDE.md
"Betriebsmittelverwaltung" -> gleichnamiger Abschnitt für die volle Herleitung).

Löst die 1.5.0-Doppelzählungs-Sonderbehandlung ab: OperationalAsset.recurring_cost_per_month
entfällt als eigene Spalte -- eine laufende Rate am Betriebsmittel erzeugt/ändert/entfernt
seither einen echten RecurringCost mit is_asset_quick_entry=True
(app/operational_assets.py::sync_asset_recurring_cost()). Deckt ab: die drei Kernregeln
(anlegen bei Betrag > 0, ändern statt duplizieren, entfernen bei 0/None), die vom Betreiber
verlangte Ausnahme (Dokumente/Vertragspartner -> Warnung statt stillem Löschen, force=True
bestätigt), delete_asset()s fest gebundene Kaskade (quick-entry-Posten geht mit, ein
eigenständig verlinkter Posten wird nur entkoppelt) und den abschließend verlangten
Angriffstest: buero_auftrag und field kommen an keinen Teil der Betriebskosten, auch nicht an
den neu verknüpften Posten."""

import json
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import OperationalAsset, RecurringCost
from app.operational_assets import (
    LinkedRecurringCostHasDataError, create_asset, delete_asset, sync_asset_recurring_cost,
)
from app.recurring_costs import create_cost, get_cost
from app.routers.operational_assets import router as assets_router
from app.routers.recurring_costs import router as costs_router

ALL_ROLES = ("field", "buero_auftrag", "buero_finanzen", "admin")


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


def _make_asset(db, **overrides) -> OperationalAsset:
    payload = {"name": "Transporter"}
    payload.update(overrides)
    created = create_asset(db, payload)
    return db.get(OperationalAsset, created["id"])


# --- sync_asset_recurring_cost(): die drei Kernregeln ---

def test_positive_amount_creates_a_quick_entry_cost_with_the_prescribed_defaults():
    db = db_session()
    asset = _make_asset(db)
    sync_asset_recurring_cost(db, asset, Decimal("300.00"))

    rows = db.query(RecurringCost).filter(RecurringCost.asset_id == asset.id).all()
    assert len(rows) == 1
    cost = rows[0]
    assert cost.is_asset_quick_entry is True
    assert cost.net_amount == Decimal("300.00")
    assert cost.tax_rate_pct == Decimal("19.00")
    assert cost.overhead_classification == "keine"
    assert cost.billing_interval == "monatlich"
    assert cost.annual_amount == Decimal("3600.00")
    assert "Transporter" in cost.label


def test_changing_the_amount_updates_the_existing_row_not_a_second_one():
    db = db_session()
    asset = _make_asset(db)
    sync_asset_recurring_cost(db, asset, Decimal("300.00"))
    first_id = db.query(RecurringCost).filter(RecurringCost.asset_id == asset.id).one().id

    sync_asset_recurring_cost(db, asset, Decimal("450.00"))
    rows = db.query(RecurringCost).filter(RecurringCost.asset_id == asset.id).all()
    assert len(rows) == 1
    assert rows[0].id == first_id
    assert rows[0].net_amount == Decimal("450.00")
    assert rows[0].annual_amount == Decimal("5400.00")


@pytest.mark.parametrize("amount", [None, Decimal("0")])
def test_null_or_zero_amount_removes_the_cost_without_extra_data(amount):
    db = db_session()
    asset = _make_asset(db)
    sync_asset_recurring_cost(db, asset, Decimal("300.00"))
    sync_asset_recurring_cost(db, asset, amount)
    assert db.query(RecurringCost).filter(RecurringCost.asset_id == asset.id).count() == 0


def test_removing_and_re_adding_creates_a_brand_new_row():
    """SQLite kann die ROWID einer gelöschten Zeile für die nächste Einfügung wiederverwenden
    (kein AUTOINCREMENT-Keyword) -- ein Vergleich der id allein wäre deshalb kein verlässlicher
    Nachweis. Stattdessen: zwischendurch existiert wirklich keine Zeile, und die neue trägt
    keine Reste der alten (hier: unverändert ohne vendor/notes -- die eigentliche Garantie ist
    Regel 6 fürs Löschen selbst)."""
    db = db_session()
    asset = _make_asset(db)
    sync_asset_recurring_cost(db, asset, Decimal("300.00"))
    assert db.query(RecurringCost).filter(RecurringCost.asset_id == asset.id).count() == 1
    sync_asset_recurring_cost(db, asset, None)
    assert db.query(RecurringCost).filter(RecurringCost.asset_id == asset.id).count() == 0
    sync_asset_recurring_cost(db, asset, Decimal("300.00"))
    recreated = db.query(RecurringCost).filter(RecurringCost.asset_id == asset.id).one()
    assert recreated.vendor is None
    assert recreated.notes is None


# --- Die vom Betreiber verlangte Ausnahme: Dokumente/Vertragspartner ---

@pytest.mark.parametrize("field, value", [
    ("vendor", "Leasing GmbH"),
    ("notes", "Sonderkonditionen ausgehandelt"),
    ("category", "Leasing"),
])
def test_removal_is_blocked_when_the_cost_carries_manually_added_data(field, value):
    db = db_session()
    asset = _make_asset(db)
    sync_asset_recurring_cost(db, asset, Decimal("300.00"))
    cost_id = db.query(RecurringCost).filter(RecurringCost.asset_id == asset.id).one().id
    setattr(db.get(RecurringCost, cost_id), field, value)
    db.commit()

    with pytest.raises(LinkedRecurringCostHasDataError) as exc_info:
        sync_asset_recurring_cost(db, asset, None)
    assert db.query(RecurringCost).filter(RecurringCost.asset_id == asset.id).count() == 1
    if field == "vendor":
        assert exc_info.value.vendor == value


def test_removal_is_blocked_when_the_cost_carries_a_document(tmp_path, monkeypatch):
    from app import recurring_cost_documents as docs_module
    from app.recurring_costs import create_cost_document

    monkeypatch.setattr(docs_module, "DOCUMENT_ROOT", tmp_path)
    db = db_session()
    asset = _make_asset(db)
    sync_asset_recurring_cost(db, asset, Decimal("300.00"))
    cost_id = db.query(RecurringCost).filter(RecurringCost.asset_id == asset.id).one().id
    stored = docs_module.save_document("leasingvertrag.pdf", b"dummy")
    create_cost_document(
        db, cost_id, document_type="Vertrag", notes=None,
        stored_filename=stored, original_filename="leasingvertrag.pdf",
    )

    with pytest.raises(LinkedRecurringCostHasDataError) as exc_info:
        sync_asset_recurring_cost(db, db.get(OperationalAsset, asset.id), None)
    assert exc_info.value.document_count == 1
    assert docs_module.document_path(stored).is_file()


def test_force_true_removes_the_cost_and_its_document_file_despite_the_warning(tmp_path, monkeypatch):
    from app import recurring_cost_documents as docs_module
    from app.recurring_costs import create_cost_document

    monkeypatch.setattr(docs_module, "DOCUMENT_ROOT", tmp_path)
    db = db_session()
    asset = _make_asset(db)
    sync_asset_recurring_cost(db, asset, Decimal("300.00"))
    cost_id = db.query(RecurringCost).filter(RecurringCost.asset_id == asset.id).one().id
    stored = docs_module.save_document("leasingvertrag.pdf", b"dummy")
    create_cost_document(
        db, cost_id, document_type="Vertrag", notes=None,
        stored_filename=stored, original_filename="leasingvertrag.pdf",
    )

    sync_asset_recurring_cost(db, db.get(OperationalAsset, asset.id), None, force=True)
    assert db.query(RecurringCost).filter(RecurringCost.asset_id == asset.id).count() == 0
    assert not docs_module.document_path(stored).is_file()


def test_updating_the_amount_without_removal_never_needs_force_even_with_extra_data():
    """Wird die Rate nur geändert (nicht auf null gesetzt), greift die Ausnahme nicht -- sie
    betrifft ausschließlich das ENTFERNEN, nie das Aktualisieren."""
    db = db_session()
    asset = _make_asset(db)
    sync_asset_recurring_cost(db, asset, Decimal("300.00"))
    cost_id = db.query(RecurringCost).filter(RecurringCost.asset_id == asset.id).one().id
    cost = db.get(RecurringCost, cost_id)
    cost.vendor = "Leasing GmbH"
    db.commit()

    sync_asset_recurring_cost(db, asset, Decimal("500.00"))  # keine Ausnahme
    updated = db.get(RecurringCost, cost_id)
    assert updated.net_amount == Decimal("500.00")
    assert updated.vendor == "Leasing GmbH"  # unberührt


# --- delete_asset(): fest gebunden vs. eigenständig ---

def test_delete_asset_cascades_the_quick_entry_cost_and_its_document(tmp_path, monkeypatch):
    from app import recurring_cost_documents as docs_module
    from app.recurring_costs import create_cost_document

    monkeypatch.setattr(docs_module, "DOCUMENT_ROOT", tmp_path)
    db = db_session()
    asset = _make_asset(db)
    sync_asset_recurring_cost(db, asset, Decimal("300.00"))
    cost_id = db.query(RecurringCost).filter(RecurringCost.asset_id == asset.id).one().id
    stored = docs_module.save_document("leasingvertrag.pdf", b"dummy")
    create_cost_document(
        db, cost_id, document_type="Vertrag", notes=None,
        stored_filename=stored, original_filename="leasingvertrag.pdf",
    )

    assert delete_asset(db, asset.id) is True
    assert db.get(RecurringCost, cost_id) is None
    assert not docs_module.document_path(stored).is_file()


def test_delete_asset_unlinks_but_does_not_delete_an_independently_linked_cost():
    db = db_session()
    asset = _make_asset(db)
    independent = create_cost(db, {
        "label": "Versicherung Transporter", "category": "Versicherung", "net_amount": "80.00",
        "billing_interval": "monatlich", "asset_id": asset.id, "active": True,
    })

    assert delete_asset(db, asset.id) is True
    survivor = get_cost(db, independent["id"])
    assert survivor is not None
    assert survivor["asset_id"] is None
    assert survivor["is_asset_quick_entry"] is False


def test_delete_asset_with_both_a_quick_entry_and_an_independent_cost():
    db = db_session()
    asset = _make_asset(db)
    sync_asset_recurring_cost(db, asset, Decimal("300.00"))
    quick_entry_id = db.query(RecurringCost).filter(
        RecurringCost.asset_id == asset.id, RecurringCost.is_asset_quick_entry == True  # noqa: E712
    ).one().id
    independent = create_cost(db, {
        "label": "Versicherung Transporter", "net_amount": "80.00", "billing_interval": "monatlich",
        "asset_id": asset.id, "active": True,
    })

    assert delete_asset(db, asset.id) is True
    assert db.get(RecurringCost, quick_entry_id) is None
    survivor = get_cost(db, independent["id"])
    assert survivor["asset_id"] is None


# --- Router: eigener, engerer Endpunkt für die laufende Rate ---

def test_recurring_cost_endpoint_requires_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    created = router_test_client(db, assets_router, role="buero_auftrag").post(
        "/api/operational-assets", json={"name": "Kran"}
    ).json()
    for role in ALL_ROLES:
        client = router_test_client(db, assets_router, role=role)
        resp = client.put(f"/api/operational-assets/{created['id']}/recurring-cost", json={"net_amount": "100.00"})
        if role in ("buero_finanzen", "admin"):
            assert resp.status_code == 200, (role, resp.text)
            assert resp.json()["recurring_cost_per_month"] == "100.00"
        else:
            assert resp.status_code == 403, (role, resp.text)
            assert not (_recursive_keys(resp.json()) & {"recurring_cost_per_month", "net_amount"})


def test_general_asset_update_ignores_a_smuggled_recurring_cost_field(threaded_db_session, router_test_client):
    """buero_auftrag darf das Betriebsmittel weiterhin bearbeiten -- aber ein untergeschobenes
    Kosten-Feld im allgemeinen PUT darf nie einen RecurringCost erzeugen: das Schema kennt das
    Feld gar nicht mehr, jeder Effekt ausschließlich über den eigenen, finanzen-gateten
    Endpunkt oben."""
    db = threaded_db_session
    office = router_test_client(db, assets_router, role="buero_auftrag")
    created = office.post("/api/operational-assets", json={"name": "Kran"}).json()
    resp = office.put(f"/api/operational-assets/{created['id']}", json={
        "name": "Kran", "recurring_cost_per_month": "999.00",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["recurring_cost_per_month"] is None
    assert db.query(RecurringCost).filter(RecurringCost.asset_id == created["id"]).count() == 0


def test_409_requires_confirmation_then_force_true_removes_it(threaded_db_session, router_test_client):
    db = threaded_db_session
    assets_client = router_test_client(db, assets_router, role="buero_finanzen")
    created = assets_client.post("/api/operational-assets", json={"name": "Kran"}).json()
    assets_client.put(f"/api/operational-assets/{created['id']}/recurring-cost", json={"net_amount": "100.00"})
    asset_row = db.get(OperationalAsset, created["id"])
    cost_row = db.query(RecurringCost).filter(RecurringCost.asset_id == asset_row.id).one()
    cost_row.vendor = "Leasing GmbH"
    db.commit()

    blocked = assets_client.put(f"/api/operational-assets/{created['id']}/recurring-cost", json={"net_amount": None})
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert detail["vendor"] == "Leasing GmbH"
    assert db.query(RecurringCost).filter(RecurringCost.asset_id == asset_row.id).count() == 1

    forced = assets_client.put(
        f"/api/operational-assets/{created['id']}/recurring-cost",
        json={"net_amount": None, "force_remove": True},
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["recurring_cost_per_month"] is None
    assert db.query(RecurringCost).filter(RecurringCost.asset_id == asset_row.id).count() == 0


# ---------------------------------------------------------------------------
# Angriffstest: buero_auftrag und field kommen an keinen Teil der Betriebskosten, auch nicht
# an den neu verknüpften Posten -- rekursiver Schlüssel-Scan, ein Testkonto pro Rolle.
# ---------------------------------------------------------------------------

def test_neither_buero_auftrag_nor_field_can_reach_the_linked_cost_by_any_path(
    threaded_db_session, router_test_client,
):
    db = threaded_db_session
    finanzen = router_test_client(db, assets_router, role="buero_finanzen")
    created = finanzen.post("/api/operational-assets", json={"name": "Kran"}).json()
    finanzen.put(f"/api/operational-assets/{created['id']}/recurring-cost", json={"net_amount": "100.00"})
    cost_id = db.query(RecurringCost).filter(RecurringCost.asset_id == created["id"]).one().id

    for role in ("buero_auftrag", "field"):
        assets_client = router_test_client(db, assets_router, role=role)
        # (1) Der eigene, engere Endpunkt bleibt für beide Rollen gesperrt.
        r1 = assets_client.put(f"/api/operational-assets/{created['id']}/recurring-cost", json={"net_amount": "1.00"})
        assert r1.status_code == 403, (role, r1.text)

        # (2) Über den allgemeinen Betriebsmittel-Endpunkt lässt sich die Rate weder ändern
        # noch entfernen -- das Feld existiert im Schema nicht mehr, es passiert schlicht nichts.
        if role == "buero_auftrag":
            r2 = assets_client.put(f"/api/operational-assets/{created['id']}", json={
                "name": "Kran", "recurring_cost_per_month": "1.00",
            })
            assert r2.status_code == 200, r2.text
            unchanged = db.get(RecurringCost, cost_id)
            assert unchanged.net_amount == Decimal("100.00")

        # (3) Der komplette Betriebskosten-Router bleibt für beide Rollen gesperrt, auch mit
        # der bekannten cost_id -- kein 404-vs-403-Unterschied, der die Existenz verraten würde.
        costs_client = router_test_client(db, costs_router, role=role)
        assert costs_client.get(f"/api/recurring-costs/{cost_id}").status_code == 403, role
        assert costs_client.get("/api/recurring-costs").status_code == 403, role
        assert costs_client.put(f"/api/recurring-costs/{cost_id}", json={
            "label": "x", "net_amount": "1.00", "billing_interval": "monatlich",
        }).status_code == 403, role
        assert costs_client.delete(f"/api/recurring-costs/{cost_id}").status_code == 403, role

    # Der Posten existiert nach alledem unverändert weiter.
    assert get_cost(db, cost_id)["net_amount"] == Decimal("100.00")
