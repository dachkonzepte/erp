"""Version 1.4.0 -- Betriebsmittelverwaltung (Modul "betriebsmittel"), Stufe 1.

Deckt ab: das Datenmodell (Asset-Ressourcenbezug, Doppelerfassungs-Schutz), die
Migrations-Backfill-Logik (jede bestehende OperationalResource bekommt ein verknüpftes
Asset), die Fälligkeitslogik (is_inspection_due()/is_inspection_overdue()), die
Business-Logik in app/operational_assets.py (CRUD Assets/Inspektionen, Live-Auflösung
verknüpfter Ressourcen) und die Router-Absicherung (Rollen- UND Modul-Gate)."""

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import EnabledModule, OperationalAsset, OperationalAssetInspection, OperationalResource
from app.operational_assets import (
    create_asset, create_inspection, delete_asset, get_asset, get_or_create_operational_asset_settings,
    is_inspection_due, is_inspection_overdue, list_assets, list_due_assets, update_asset,
    update_operational_asset_settings,
)


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_resource(db, name="Sprinter 1", resource_type="Fahrzeug"):
    r = OperationalResource(name=name, resource_type=resource_type)
    db.add(r)
    db.commit()
    return r


# --- Fälligkeitslogik ---

def test_is_inspection_due_within_lead_days_but_not_before():
    today = date(2026, 1, 1)
    assert is_inspection_due(date(2026, 1, 15), lead_days=30, today=today) is True
    assert is_inspection_due(date(2026, 3, 1), lead_days=30, today=today) is False
    assert is_inspection_due(None, lead_days=30, today=today) is False


def test_is_inspection_overdue_only_when_date_already_passed():
    today = date(2026, 1, 15)
    assert is_inspection_overdue(date(2026, 1, 1), today=today) is True
    assert is_inspection_overdue(date(2026, 1, 15), today=today) is False
    assert is_inspection_overdue(date(2026, 2, 1), today=today) is False
    assert is_inspection_overdue(None, today=today) is False


# --- Doppelerfassungs-Schutz (Punkt 1 der Bau-Entscheidung) ---

def test_resource_can_have_at_most_one_asset():
    db = db_session()
    resource = make_resource(db)
    create_asset(db, {"resource_id": resource.id})
    with pytest.raises(ValueError, match="bereits einem anderen Betriebsmittel zugeordnet"):
        create_asset(db, {"resource_id": resource.id})


def test_updating_asset_to_an_already_taken_resource_is_rejected():
    db = db_session()
    r1 = make_resource(db, "Sprinter 1")
    r2 = make_resource(db, "Sprinter 2")
    create_asset(db, {"resource_id": r1.id})
    standalone = create_asset(db, {"name": "Leiter"})
    with pytest.raises(ValueError, match="bereits einem anderen Betriebsmittel zugeordnet"):
        update_asset(db, standalone["id"], {"resource_id": r1.id})
    # Die eigene, unveränderte Zuordnung darf beim Speichern erneut mitgeschickt werden.
    linked = create_asset(db, {"resource_id": r2.id})
    updated = update_asset(db, linked["id"], {"resource_id": r2.id, "notes": "geprüft"})
    assert updated["resource_id"] == r2.id
    assert updated["notes"] == "geprüft"


def test_linked_asset_resolves_identity_fields_live_from_resource():
    """Kern der Doppelerfassungs-Vermeidung: die Felder werden NIE als eigene Kopie auf dem
    Asset gespeichert, sondern bei jedem Lesezugriff aus der Ressource aufgelöst -- eine
    spätere Umbenennung der Ressource schlägt automatisch durch, ohne das Asset anzufassen."""
    db = db_session()
    resource = make_resource(db, name="Sprinter 1", resource_type="Fahrzeug")
    created = create_asset(db, {"resource_id": resource.id})
    assert created["name"] == "Sprinter 1"
    assert created["asset_type"] == "Fahrzeug"
    row = db.get(OperationalAsset, created["id"])
    assert row.name is None and row.asset_type is None  # nie kopiert

    resource.name = "Sprinter 1 (neu lackiert)"
    db.commit()
    reloaded = get_asset(db, created["id"])
    assert reloaded["name"] == "Sprinter 1 (neu lackiert)"


def test_resource_field_is_ignored_and_own_fields_cleared_when_linking():
    db = db_session()
    resource = make_resource(db)
    standalone = create_asset(db, {"name": "Leiter", "asset_type": "Sonstiges", "manufacturer": "Zarges"})
    linked = update_asset(db, standalone["id"], {"resource_id": resource.id})
    assert linked["manufacturer"] is None
    row = db.get(OperationalAsset, standalone["id"])
    assert row.name is None and row.manufacturer is None


# --- Name-Pflicht bei eigenständigem Betriebsmittel (Pydantic-Validator) ---

def test_schema_requires_name_when_no_resource_linked():
    from pydantic import ValidationError

    from app.schemas import OperationalAssetCreate

    with pytest.raises(ValidationError, match="Bezeichnung ist erforderlich"):
        OperationalAssetCreate(resource_id=None, name=None)
    OperationalAssetCreate(resource_id=None, name="Leiter")  # kein Fehler
    OperationalAssetCreate(resource_id=1, name=None)  # kein Fehler, Ressource liefert den Namen


# --- CRUD + Aggregation über Inspektionen ---

def test_asset_due_and_overdue_aggregate_across_inspections():
    db = db_session()
    asset = create_asset(db, {"name": "Kran"})
    today = date.today()
    create_inspection(db, asset["id"], {"inspection_type": "TÜV", "next_due_date": today + timedelta(days=200)})
    create_inspection(db, asset["id"], {"inspection_type": "UVV-Prüfung", "next_due_date": today - timedelta(days=1)})
    reloaded = get_asset(db, asset["id"])
    assert reloaded["is_overdue"] is True
    assert reloaded["is_due"] is True  # überfällig zählt zugleich als fällig
    assert reloaded["next_due_date"] == today - timedelta(days=1)  # die frühere der beiden Fristen


def test_list_due_assets_only_returns_due_or_overdue_active_assets():
    db = db_session()
    fine = create_asset(db, {"name": "Bohrmaschine"})
    create_inspection(db, fine["id"], {"inspection_type": "Wartung", "next_due_date": date.today() + timedelta(days=365)})
    overdue = create_asset(db, {"name": "Leiter"})
    create_inspection(db, overdue["id"], {"inspection_type": "Leiterprüfung", "next_due_date": date.today() - timedelta(days=5)})
    due_ids = {a["id"] for a in list_due_assets(db)}
    assert overdue["id"] in due_ids
    assert fine["id"] not in due_ids


def test_delete_asset_removes_inspections_but_never_the_linked_resource():
    db = db_session()
    resource = make_resource(db)
    asset = create_asset(db, {"resource_id": resource.id})
    create_inspection(db, asset["id"], {"inspection_type": "TÜV"})
    assert delete_asset(db, asset["id"]) is True
    assert db.get(OperationalAsset, asset["id"]) is None
    assert db.scalar(select(OperationalAssetInspection).where(OperationalAssetInspection.asset_id == asset["id"])) is None
    assert db.get(OperationalResource, resource.id) is not None  # unberührt


def test_settings_singleton_default_lead_days_and_update():
    db = db_session()
    settings = get_or_create_operational_asset_settings(db)
    assert settings.reminder_lead_days == 30
    update_operational_asset_settings(db, 45)
    assert get_or_create_operational_asset_settings(db).reminder_lead_days == 45


# --- Migration: Backfill bestehender Ressourcen als verknüpfte Assets ---

def _migration_module():
    path = next(Path(__file__).resolve().parents[1].glob("alembic/versions/*_operational_assets_betriebsmittel.py"))
    spec = importlib.util.spec_from_file_location("migration_140_operational_assets", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_backfill_creates_one_linked_asset_per_existing_resource():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for name in ("Sprinter 1", "Sprinter 2", "Böcker AHK36"):
            conn.execute(OperationalResource.__table__.insert().values(name=name, resource_type="Fahrzeug", active=True))
        # Bereits ein Asset für einen Teil der Ressourcen -- die Backfill-Funktion selbst wird
        # in dieser Version nur einmal (frisch angelegte Tabelle) aufgerufen; hier wird nur ihre
        # Kernlogik (ein Insert je Ressourcen-ID) isoliert geprüft.
        migration = _migration_module()
        created = migration._backfill_assets_for_existing_resources(conn)
        assert created == 3
        rows = conn.execute(OperationalAsset.__table__.select()).fetchall()
        assert len(rows) == 3
        resource_ids = {r.id for r in conn.execute(OperationalResource.__table__.select()).fetchall()}
        assert {row.resource_id for row in rows} == resource_ids
        assert all(row.name is None for row in rows)
        assert all(row.active for row in rows)


def test_migration_backfill_is_a_noop_without_existing_resources():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        migration = _migration_module()
        assert migration._backfill_assets_for_existing_resources(conn) == 0


# --- Router: Rollen- und Modul-Gate ---

def test_field_role_gets_403_on_every_operational_asset_endpoint(threaded_db_session, router_test_client):
    from app.routers.operational_assets import router as assets_router

    client = router_test_client(threaded_db_session, assets_router, role="field")
    assert client.get("/api/operational-assets").status_code == 403
    assert client.get("/api/operational-assets/due").status_code == 403
    assert client.post("/api/operational-assets", json={"name": "Leiter"}).status_code == 403
    assert client.get("/api/operational-asset-settings").status_code == 403


def test_module_disabled_returns_403_even_for_office_role(threaded_db_session, router_test_client):
    from app.routers.operational_assets import router as assets_router

    threaded_db_session.add(EnabledModule(module_key="betriebsmittel", enabled=False))
    threaded_db_session.commit()
    client = router_test_client(threaded_db_session, assets_router, role="office")
    r = client.get("/api/operational-assets")
    assert r.status_code == 403
    assert "Betriebsmittelverwaltung" in r.json()["detail"]


def test_office_role_full_crud_flow_via_router(threaded_db_session, router_test_client):
    from app.routers.operational_assets import router as assets_router

    client = router_test_client(threaded_db_session, assets_router, role="office")
    created = client.post("/api/operational-assets", json={"name": "Leiter Alu 6m", "asset_type": "Sonstiges"}).json()
    assert created["id"]
    inspection = client.post(
        f"/api/operational-assets/{created['id']}/inspections",
        json={"inspection_type": "Leiterprüfung", "interval_months": 12, "next_due_date": str(date.today() - timedelta(days=1))},
    ).json()
    assert inspection["is_overdue"] is True
    detail = client.get(f"/api/operational-assets/{created['id']}").json()
    assert detail["is_overdue"] is True
    assert len(detail["inspections"]) == 1
    due_list = client.get("/api/operational-assets/due").json()
    assert any(a["id"] == created["id"] for a in due_list)
    assert client.delete(f"/api/operational-asset-inspections/{inspection['id']}").json() == {"deleted": True}
    assert client.delete(f"/api/operational-assets/{created['id']}").json() == {"deleted": True}
    assert client.get(f"/api/operational-assets/{created['id']}").status_code == 404


def test_creating_asset_without_name_or_resource_fails_with_422(threaded_db_session, router_test_client):
    from app.routers.operational_assets import router as assets_router

    client = router_test_client(threaded_db_session, assets_router, role="office")
    r = client.post("/api/operational-assets", json={})
    assert r.status_code == 422
