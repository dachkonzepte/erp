"""Version 1.3.12 -- Punkt 2 der Anfrage: Finding.roof_component_name_snapshot/
ServiceReportRoofArea.roof_area_name_snapshot. Ein bereits unterschriebener Einsatzbericht ist
unveränderlich -- eine spätere Umbenennung eines Bauteils oder einer Dachfläche darf ihn nicht
rückwirkend verändern (weder auf dem Bildschirm noch im PDF), obwohl `roof_component_id`/
`roof_area_id` selbst (der reine FK-Bezug) weiterhin eingefroren bleiben."""

import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from tests.test_v133_invoices import make_order_with_item
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v213_inspection_items import TINY_PNG, _extract_pdf_text, _seed_test_template

from app.database import Base
from app.findings import create_finding, finding_to_dict, list_findings_for_report
from app.models import Finding, RoofArea, RoofComponent, ServiceReportRoofArea
from app.roof_areas import create_roof_area, create_roof_component
from app.service_report_pdf import build_service_report_pdf
from app.service_reports import _load as _load_report, create_report, sign_report


def _make_order_for_report(db):
    order, _ = make_order_with_item(db)
    return order


# ---------------------------------------------------------------------------
# create_finding(): Schnappschuss wird beim Anlegen gesetzt
# ---------------------------------------------------------------------------

def test_create_finding_snapshots_component_name():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    component = create_roof_component(db, area["id"], "Gully Nordost", component_type="Gully")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")

    finding = create_finding(db, report["id"], "Riss im Bauteil", "mittel", "sofort_behoben", roof_component_id=component["id"])
    row = db.get(Finding, finding["id"])
    assert row.roof_component_name_snapshot == "Gully Nordost"


def test_finding_name_stays_frozen_after_component_renamed():
    """Kernfall der Anfrage: eine Umbenennung NACH Anlage des Mangels darf weder auf dem
    Bildschirm (finding_to_dict()) noch im PDF etwas ändern."""
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    component = create_roof_component(db, area["id"], "Gully Nordost", component_type="Gully")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    finding = create_finding(db, report["id"], "Riss im Bauteil", "mittel", "sofort_behoben", roof_component_id=component["id"])
    add_finding_photo_and_sign(db, report["id"], finding["id"])

    # Bauteil NACH der Unterschrift umbenennen.
    row = db.get(RoofComponent, component["id"])
    row.name = "Gully Nordost (umbenannt)"
    db.commit()

    updated = finding_to_dict(db.get(Finding, finding["id"]))
    assert updated["roof_component_name"] == "Gully Nordost"

    signed_report = _load_report(db, report["id"])
    pdf_bytes = build_service_report_pdf(db, signed_report)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Gully Nordost" in text
    assert b"umbenannt" not in text


def add_finding_photo_and_sign(db, report_id, finding_id):
    from app.service_reports import add_photo
    add_photo(db, report_id, TINY_PNG, "mangel.png", finding_id=finding_id)
    sign_report(
        db, report_id, installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Test",
        customer_signature_png_bytes=TINY_PNG, customer_signature_name="Max Mustermann",
    )


def test_finding_without_component_has_no_snapshot():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    finding = create_finding(db, report["id"], "Allgemeine Feststellung", "gering", "zurueckgestellt", resubmission_date=__import__("datetime").date.today())
    row = db.get(Finding, finding["id"])
    assert row.roof_component_name_snapshot is None
    assert finding_to_dict(row)["roof_component_name"] is None


def test_finding_to_dict_falls_back_to_live_name_when_snapshot_missing():
    """Bestandszeilen ohne Schnappschuss (vor 1.3.12 angelegt) -- Rückfall auf den aktuellen
    Namen, damit sie nicht plötzlich leer erscheinen."""
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    component = create_roof_component(db, area["id"], "Gully Nordost", component_type="Gully")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    finding = create_finding(db, report["id"], "Riss im Bauteil", "mittel", "sofort_behoben", roof_component_id=component["id"])

    # Schnappschuss simuliert leeren, wie bei einer echten Bestandszeile vor der Migration.
    row = db.get(Finding, finding["id"])
    row.roof_component_name_snapshot = None
    db.commit()

    assert finding_to_dict(db.get(Finding, finding["id"]))["roof_component_name"] == "Gully Nordost"


# ---------------------------------------------------------------------------
# ServiceReportRoofArea.roof_area_name_snapshot
# ---------------------------------------------------------------------------

def test_report_roof_area_name_stays_frozen_after_area_renamed():
    db = db_session()
    _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach Nord", roof_type="Flachdach")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])

    link = db.scalar(select(ServiceReportRoofArea).where(ServiceReportRoofArea.service_report_id == report["id"]))
    assert link.roof_area_name_snapshot == "Hauptdach Nord"

    # Dachfläche umbenennen -- die Anzeige/das PDF müssen weiterhin den alten Namen zeigen.
    area_row = db.get(RoofArea, area["id"])
    area_row.name = "Hauptdach Nord (umbenannt)"
    db.commit()

    from app.service_reports import report_to_dict
    row = _load_report(db, report["id"])
    dict_after_rename = report_to_dict(row)
    assert dict_after_rename["roof_areas"][0]["roof_area_name"] == "Hauptdach Nord"

    # Alle Pflichtpunkte beantworten, damit signiert werden kann.
    from app.service_reports import update_inspection_item, list_inspection_items
    for item in list_inspection_items(db, report["id"]):
        if item["required"]:
            update_inspection_item(db, item["id"], {"result": "ok", "condition_grade": 1})
    sign_report(
        db, report["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Test",
        customer_signature_png_bytes=TINY_PNG, customer_signature_name="Max Mustermann",
    )

    signed_row = _load_report(db, report["id"])
    pdf_bytes = build_service_report_pdf(db, signed_row)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Hauptdach Nord" in text
    assert b"umbenannt" not in text


# ---------------------------------------------------------------------------
# Migration 5149d369dbb6: Bestandszeilen aus dem heutigen Namen befuellen
# ---------------------------------------------------------------------------

def _load_migration():
    path = next(Path(__file__).resolve().parents[1].glob("alembic/versions/*_finding_and_service_report_roof_area_*.py"))
    spec = importlib.util.spec_from_file_location("migration_1312_name_snapshots", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _new_engine_with_schema():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


# Die eigentliche Backfill-LOGIK wird direkt (als eigene, modulweite Funktion, siehe
# Migrationsdatei) gegen eine gebundene Connection getestet, nicht über migration.upgrade()
# selbst -- upgrade()s batch_alter_table()-Aufrufe (autogeneriertes ADD COLUMN, reines
# Alembic-Boilerplate) lassen sich mit dem leichten MigrationContext/Operations-Aufbau dieses
# Testmusters nicht sauber ausführen (SQLite-Batch-Modus braucht eine an echtes target_metadata
# gebundene Umgebung); kein bestehender Migrationstest in diesem Projekt tut das bisher. Das
# Schema selbst kommt hier stattdessen unverändert aus Base.metadata.create_all() (app/models.py
# kennt die neuen Spalten längst) -- getestet wird ausschließlich, ob die Befüll-Funktion
# bestehende Zeilen korrekt aus dem aktuellen Namen nachträgt.

def test_migration_backfills_existing_rows_from_current_names():
    migration = _load_migration()
    engine = _new_engine_with_schema()
    Session = sessionmaker(bind=engine)
    db = Session()

    from app.models import Customer, Order, Project, Property, ServiceReport

    customer = Customer(name="Test Kunde", last_name="Test Kunde")
    db.add(customer)
    db.flush()
    prop = Property(customer_id=customer.id, name="Objekt")
    db.add(prop)
    db.flush()
    area = RoofArea(property_id=prop.id, name="Bestandsflaeche")
    db.add(area)
    db.flush()
    component = RoofComponent(roof_area_id=area.id, name="Bestandsbauteil")
    db.add(component)
    db.flush()
    project = Project(project_number="P-TEST-0099", name="Testprojekt", customer_id=customer.id)
    db.add(project)
    db.flush()
    order = Order(
        order_number="AUF-TEST-0099", project_id=project.id, source_quote_id=99, quote_number_snapshot="A-TEST-0099",
        title="Testauftrag", customer_name="Test Kunde",
    )
    db.add(order)
    db.flush()
    report = ServiceReport(order_id=order.id, report_type="rapport", status="entwurf")
    db.add(report)
    db.flush()
    # Schnappschuss-Spalten existieren bereits (Base.metadata.create_all()), bleiben hier aber
    # bewusst leer -- genau der Zustand einer echten Bestandszeile vor dieser Migration.
    finding = Finding(
        service_report_id=report.id, roof_component_id=component.id,
        description="Bestandsmangel", severity="gering", action="sofort_behoben",
    )
    db.add(finding)
    link = ServiceReportRoofArea(service_report_id=report.id, roof_area_id=area.id)
    db.add(link)
    db.commit()
    finding_id, link_id = finding.id, link.id
    db.close()

    with engine.connect() as conn:
        migration._backfill_finding_roof_component_snapshots(conn)
        migration._backfill_service_report_roof_area_snapshots(conn)
        conn.commit()

    db = Session()
    assert db.get(Finding, finding_id).roof_component_name_snapshot == "Bestandsbauteil"
    assert db.get(ServiceReportRoofArea, link_id).roof_area_name_snapshot == "Bestandsflaeche"
    db.close()


def test_migration_backfill_leaves_findings_without_component_untouched():
    migration = _load_migration()
    engine = _new_engine_with_schema()
    Session = sessionmaker(bind=engine)
    db = Session()

    from app.models import Customer, Order, Project, ServiceReport

    customer = Customer(name="Test Kunde", last_name="Test Kunde")
    db.add(customer)
    db.flush()
    project = Project(project_number="P-TEST-0098", name="Testprojekt", customer_id=customer.id)
    db.add(project)
    db.flush()
    order = Order(
        order_number="AUF-TEST-0098", project_id=project.id, source_quote_id=98, quote_number_snapshot="A-TEST-0098",
        title="Testauftrag", customer_name="Test Kunde",
    )
    db.add(order)
    db.flush()
    report = ServiceReport(order_id=order.id, report_type="rapport", status="entwurf")
    db.add(report)
    db.flush()
    finding = Finding(
        service_report_id=report.id, roof_component_id=None,
        description="Ohne Bauteilbezug", severity="gering", action="sofort_behoben",
    )
    db.add(finding)
    db.commit()
    finding_id = finding.id
    db.close()

    with engine.connect() as conn:
        migration._backfill_finding_roof_component_snapshots(conn)
        conn.commit()

    db = Session()
    assert db.get(Finding, finding_id).roof_component_name_snapshot is None
    db.close()
