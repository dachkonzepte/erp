"""Version 1.4.2 -- Betriebsmittelverwaltung, vier Ergänzungen (siehe CLAUDE.md
"Betriebsmittelverwaltung", Nachtrag zu Stufe 2): automatische Fälligkeitsberechnung der
Prüffristen (Punkt 1), Meldung + Aufgabe vier Wochen vorher (Punkt 2), Betriebsmittel in der
Büro-Suche (Punkt 3), Dokumentenablage am Betriebsmittel (Punkt 4). Alle drei reine
Bürofunktionen -- kein Monteur betroffen, siehe die beiden Angriffstests am Ende dieser Datei.

Deckt ab: die verspätete-Prüfung-verschiebt-den-Rhythmus-mit-Feinheit (Punkt 1, das
entscheidende Belegkriterium der Anfrage), die manuelle Prüffrist ohne Intervall, die
Erinnerungs-Aufgabe samt Idempotenz-Stempel (Punkt 2), die Live-Auflösung eines
ressourcenverknüpften Assets in der Büro-Suche (Punkt 3), die Dokumentenablage-Endpunkte für
Büro/Admin (Punkt 4) UND den abschließend verlangten Angriffstest: ein Monteur kommt über
keinen Weg an eine Betriebsmittel-Rechnung, auch nicht über eine geratene Datei-ID, und die
Büro-Suche liefert einem Monteur kein Betriebsmittel."""

from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import EnabledModule, OperationalAsset, OperationalResource
from app.operational_assets import (
    _compute_next_due_date, check_due_asset_inspections_and_create_reminders, create_asset,
    create_asset_document, create_inspection, update_inspection,
)
from app.search import search_office
from app.tasks import list_tasks


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# --- Punkt 1: automatische Fälligkeitsberechnung ---

def test_first_due_date_is_acquisition_plus_interval_minus_one_day_not_acquisition_itself():
    db = db_session()
    asset = create_asset(db, {"name": "Kran", "acquisition_date": date(2024, 1, 1)})
    inspection = create_inspection(db, asset["id"], {"inspection_type": "TÜV/HU", "interval_months": 12})
    assert inspection["next_due_date"] == date(2024, 12, 31)
    assert inspection["next_due_date"] != date(2024, 1, 1)


def test_late_inspection_advances_next_due_date_from_actual_date_not_cumulatively_from_acquisition():
    """Das entscheidende Belegkriterium der Anfrage: eine verspätet erledigte Prüfung setzt die
    nächste Fälligkeit vom tatsächlichen Erledigungsdatum, NICHT vom ursprünglich geplanten
    Termin -- sonst würde der Rhythmus auseinanderdriften statt sich zu verschieben."""
    db = db_session()
    asset = create_asset(db, {"name": "Kran", "acquisition_date": date(2024, 1, 1)})
    inspection = create_inspection(db, asset["id"], {"inspection_type": "TÜV/HU", "interval_months": 12})
    assert inspection["next_due_date"] == date(2024, 12, 31)  # ursprünglich geplant

    # Die Prüfung findet real deutlich verspätet statt, am 2025-02-15 statt am geplanten 2024-12-31.
    updated = update_inspection(db, inspection["id"], {
        "inspection_type": "TÜV/HU", "interval_months": 12, "last_inspection_date": date(2025, 2, 15),
    })

    # Kumulativ vom Anschaffungsdatum aus wäre die nächste Fälligkeit 2025-12-31 (2024-01-01 + 24mo - 1d)
    # -- das wäre falsch, der Rhythmus muss sich mit der Verspätung mitverschieben.
    cumulative_from_acquisition = date(2025, 12, 31)
    assert updated["next_due_date"] != cumulative_from_acquisition
    # Korrekt: vom tatsächlichen Prüfdatum aus, +12 Monate -1 Tag.
    assert updated["next_due_date"] == date(2026, 2, 14)


def test_one_time_inspection_without_interval_stays_fully_manual():
    """Eine Prüffrist ohne Intervall (einmalige Prüfung) bleibt manuell -- der Server berechnet
    nichts, next_due_date kommt unverändert vom Client."""
    db = db_session()
    asset = create_asset(db, {"name": "Leiter"})
    manual_date = date(2025, 6, 1)
    inspection = create_inspection(db, asset["id"], {
        "inspection_type": "Sonstige Prüfung", "interval_months": None, "next_due_date": manual_date,
    })
    assert inspection["next_due_date"] == manual_date
    assert inspection["interval_months"] is None

    # Bearbeiten mit weiterhin fehlendem Intervall übernimmt weiterhin die manuelle Angabe.
    new_manual_date = date(2025, 9, 1)
    updated = update_inspection(db, inspection["id"], {
        "inspection_type": "Sonstige Prüfung", "interval_months": None, "next_due_date": new_manual_date,
    })
    assert updated["next_due_date"] == new_manual_date


def test_compute_next_due_date_returns_none_without_interval_or_without_any_base_date():
    assert _compute_next_due_date(None, date(2025, 1, 1), date(2024, 1, 1)) is None
    assert _compute_next_due_date(12, None, None) is None


def test_switching_an_inspection_from_manual_to_interval_based_computes_next_due_date():
    """Umgekehrter Fall: eine ursprünglich manuelle Prüffrist bekommt nachträglich ein
    Intervall -- ab dann greift die automatische Berechnung, ausgehend vom zuletzt hinterlegten
    Prüfdatum."""
    db = db_session()
    asset = create_asset(db, {"name": "Kran"})
    inspection = create_inspection(db, asset["id"], {
        "inspection_type": "TÜV/HU", "interval_months": None, "next_due_date": date(2025, 1, 1),
    })
    updated = update_inspection(db, inspection["id"], {
        "inspection_type": "TÜV/HU", "interval_months": 12, "last_inspection_date": date(2025, 3, 10),
    })
    assert updated["next_due_date"] == date(2026, 3, 9)


# --- Punkt 2: Meldung und Aufgabe vier Wochen vorher, On-Demand, idempotent ---

def test_check_due_creates_unassigned_reminder_task_and_is_idempotent():
    db = db_session()
    asset = create_asset(db, {"name": "Kran"})
    inspection = create_inspection(db, asset["id"], {
        "inspection_type": "TÜV/HU", "interval_months": None, "next_due_date": date.today() - timedelta(days=1),
    })

    reminded = check_due_asset_inspections_and_create_reminders(db)
    assert reminded == [inspection["id"]]
    tasks = list_tasks(db)
    assert len(tasks) == 1
    assert tasks[0]["assigned_employee_id"] is None  # "allgemein ans Büro"
    assert tasks[0]["source_module"] == "betriebsmittel"
    assert tasks[0]["source_url"] == f"/betriebsmittel/{asset['id']}"

    # Erneuter Aufruf für denselben Fälligkeitszyklus darf nicht doppelt erinnern -- pro
    # Prüffrist und Fälligkeitstermin genau einmal.
    reminded_again = check_due_asset_inspections_and_create_reminders(db)
    assert reminded_again == []
    assert len(list_tasks(db)) == 1


def test_check_due_reminds_again_after_next_due_date_actually_changes():
    """Der last_reminder_due_date-Stempel blockiert nur denselben Fälligkeitstermin -- ändert
    sich next_due_date (hier: eine neue, spätere Prüfung wird eingetragen und fällt erneut in
    die Vorlaufzeit), erinnert der nächste Aufruf erneut, ohne expliziten Reset."""
    db = db_session()
    asset = create_asset(db, {"name": "Kran"})
    inspection = create_inspection(db, asset["id"], {
        "inspection_type": "TÜV/HU", "interval_months": 1, "last_inspection_date": date.today() - timedelta(days=40),
    })
    assert check_due_asset_inspections_and_create_reminders(db) == [inspection["id"]]
    assert len(list_tasks(db)) == 1

    # Eine neue Prüfung wird eingetragen -- next_due_date verschiebt sich, faellt aber erneut
    # (knapp) in die Vorlaufzeit.
    update_inspection(db, inspection["id"], {
        "inspection_type": "TÜV/HU", "interval_months": 1, "last_inspection_date": date.today() - timedelta(days=1),
    })
    assert check_due_asset_inspections_and_create_reminders(db) == [inspection["id"]]
    assert len(list_tasks(db)) == 2


def test_check_due_skips_reminder_when_aufgabenmanagement_disabled():
    db = db_session()
    asset = create_asset(db, {"name": "Kran"})
    create_inspection(db, asset["id"], {
        "inspection_type": "TÜV/HU", "interval_months": None, "next_due_date": date.today() - timedelta(days=1),
    })
    db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
    db.commit()
    assert check_due_asset_inspections_and_create_reminders(db) == []
    assert list_tasks(db) == []


def test_check_due_ignores_inspections_outside_the_lead_time_window():
    db = db_session()
    asset = create_asset(db, {"name": "Kran"})
    create_inspection(db, asset["id"], {
        "inspection_type": "TÜV/HU", "interval_months": None, "next_due_date": date.today() + timedelta(days=90),
    })
    assert check_due_asset_inspections_and_create_reminders(db) == []
    assert list_tasks(db) == []


# --- Punkt 3: Betriebsmittel in der Büro-Suche -- Live-Auflösung bei Ressourcenbezug ---

def test_resource_linked_asset_is_findable_via_office_search_by_resource_fields():
    """Ein Asset MIT resource_id trägt seine eigenen Identitätsfelder als NULL (Live-Auflösung)
    -- die Büro-Suche muss trotzdem über die Felder der verknüpften Ressource treffen, sonst
    wäre jedes ressourcenverknüpfte Betriebsmittel (Kran, Fahrzeug, Anhänger) unauffindbar."""
    db = db_session()
    resource = OperationalResource(name="Kran Böcker AHK36", resource_type="Kran", manufacturer="Böcker")
    db.add(resource)
    db.commit()
    asset = create_asset(db, {"resource_id": resource.id})

    groups = {g["key"]: g for g in search_office(db, "office", "Böcker")}
    assert "operational_assets" in groups
    hit = groups["operational_assets"]["hits"][0]
    assert hit["id"] == asset["id"]
    assert hit["title"] == "Kran Böcker AHK36"  # der live aufgelöste Ressourcenname
    assert hit["url"] == f"/betriebsmittel/{asset['id']}"


def test_standalone_asset_is_findable_via_office_search_by_own_fields():
    db = db_session()
    create_asset(db, {"name": "Leiter Alu 8m", "manufacturer": "Zarges"})
    groups = {g["key"]: g for g in search_office(db, "office", "Zarges")}
    assert "operational_assets" in groups
    assert groups["operational_assets"]["hits"][0]["title"] == "Leiter Alu 8m"


def test_operational_assets_source_never_appears_for_field_role_in_search_function():
    db = db_session()
    create_asset(db, {"name": "Leiter Alu 8m"})
    groups = {g["key"]: g for g in search_office(db, "field", "Leiter")}
    assert "operational_assets" not in groups


# --- Punkt 4: Dokumentenablage, Büro/Admin ---

def test_office_can_upload_document_router_returns_asset_document(threaded_db_session, router_test_client):
    from app.routers.operational_assets import router as assets_router

    db = threaded_db_session
    office = router_test_client(db, assets_router, role="office")
    asset = office.post("/api/operational-assets", json={"name": "Kran"}).json()

    r = office.post(
        f"/api/operational-assets/{asset['id']}/documents",
        data={"document_type": "Anschaffungsrechnung", "notes": "Rg-Nr. 4711"},
        files={"file": ("rechnung.pdf", b"%PDF-1.4 dummy", "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["document_type"] == "Anschaffungsrechnung"
    assert body["original_filename"] == "rechnung.pdf"
    assert body["notes"] == "Rg-Nr. 4711"

    view = office.get(f"/api/operational-asset-documents/{body['id']}/file")
    assert view.status_code == 200
    assert view.content == b"%PDF-1.4 dummy"

    deleted = office.delete(f"/api/operational-asset-documents/{body['id']}")
    assert deleted.status_code == 200
    assert office.get(f"/api/operational-asset-documents/{body['id']}/file").status_code == 404


def test_deleting_asset_document_removes_file_from_disk(tmp_path, monkeypatch):
    from app import operational_asset_documents as docs_module

    monkeypatch.setattr(docs_module, "DOCUMENT_ROOT", tmp_path)
    db = db_session()
    asset = create_asset(db, {"name": "Kran"})
    stored = docs_module.save_document("leasingvertrag.pdf", b"dummy-inhalt")
    assert docs_module.document_path(stored).is_file()

    document = create_asset_document(
        db, asset["id"], document_type="Leasingvertrag", notes=None,
        stored_filename=stored, original_filename="leasingvertrag.pdf",
    )
    from app.operational_assets import delete_asset_document
    assert delete_asset_document(db, document["id"]) is True
    assert not docs_module.document_path(stored).is_file()


# --- Abschließender Angriffstest, wie ausdrücklich verlangt ---

def test_field_can_never_reach_an_operational_asset_document_via_any_path(threaded_db_session, router_test_client):
    """Ein Monteur kommt über keinen Weg an eine Betriebsmittel-Rechnung -- auch nicht über
    eine geratene Datei-ID. require_role() schließt ROLE_FIELD strukturell aus allen drei
    Dokumentenablage-Endpunkten aus, unabhängig davon, ob asset_id/document_id existieren."""
    from app.routers.operational_assets import router as assets_router

    db = threaded_db_session
    office = router_test_client(db, assets_router, role="office")
    asset = office.post("/api/operational-assets", json={"name": "Kran"}).json()
    uploaded = office.post(
        f"/api/operational-assets/{asset['id']}/documents",
        data={"document_type": "Anschaffungsrechnung"},
        files={"file": ("rechnung.pdf", b"%PDF-1.4 dummy", "application/pdf")},
    ).json()

    field = router_test_client(db, assets_router, role="field")
    # Der reale Weg (echte, bekannte IDs).
    assert field.get(f"/api/operational-asset-documents/{uploaded['id']}/file").status_code == 403
    assert field.delete(f"/api/operational-asset-documents/{uploaded['id']}").status_code == 403
    assert field.post(
        f"/api/operational-assets/{asset['id']}/documents",
        data={"document_type": "Sonstiges"},
        files={"file": ("x.pdf", b"x", "application/pdf")},
    ).status_code == 403
    # Geratene, fortlaufende IDs -- dieselbe Ablehnung, unabhängig davon, ob sie existieren.
    for guessed_id in (1, 2, 9999):
        assert field.get(f"/api/operational-asset-documents/{guessed_id}/file").status_code == 403
        assert field.delete(f"/api/operational-asset-documents/{guessed_id}").status_code == 403


def test_office_search_endpoint_never_returns_an_operational_asset_to_field_role(threaded_db_session, router_test_client):
    """Und die Büro-Suche liefert einem Monteur kein Betriebsmittel -- geprüft über den echten
    Router (require_role lehnt schon vor jedem Dispatcher-Aufruf ab), nicht nur die Kernfunktion."""
    from app.routers.operational_assets import router as assets_router
    from app.routers.search import router as search_router

    db = threaded_db_session
    office = router_test_client(db, assets_router, role="office")
    office.post("/api/operational-assets", json={"name": "Kran Böcker AHK36"})

    field = router_test_client(db, search_router, role="field")
    r = field.get("/api/search", params={"q": "Kran"})
    assert r.status_code == 403
