"""Version 1.3.22 -- letzter loser Faden aus 1.3.12 (CLAUDE.md "Bekannte, bewusst offene Punkte"):
ServiceReportRoofArea.inspection_template_label_snapshot. Ein bereits unterschriebener
Einsatzbericht ist unveränderlich -- eine spätere Umbenennung der Prüfvorlage (update_template())
darf ihn nicht rückwirkend verändern, obwohl inspection_template_id selbst (der reine FK-Bezug)
weiterhin eingefroren bleibt. Gleiches Muster wie test_v234_finding_roof_area_name_snapshots.py."""

import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from tests.test_v133_invoices import make_order_with_item
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v213_inspection_items import _seed_test_template

from app.database import Base
from app.inspection_templates import update_template
from app.models import InspectionTemplate, RoofArea, ServiceReportRoofArea
from app.roof_areas import create_roof_area
from app.service_reports import _load as _load_report, create_report, report_to_dict


def _make_order_for_report(db):
    order, _ = make_order_with_item(db)
    return order


# ---------------------------------------------------------------------------
# create_report(): Schnappschuss wird beim Anlegen gesetzt
# ---------------------------------------------------------------------------

def test_create_report_snapshots_template_label():
    db = db_session()
    _seed_test_template(db, roof_type="Flachdach", label="Testvorlage")
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])

    link = db.scalar(select(ServiceReportRoofArea).where(ServiceReportRoofArea.service_report_id == report["id"]))
    assert link.inspection_template_label_snapshot == "Testvorlage"


def test_report_roof_area_without_resolvable_template_has_no_label_snapshot():
    """Eine Fläche ohne auflösbare Vorlage bekommt trotzdem ihre Zeile (siehe
    _generate_inspection_items_for_areas()), aber keinen Label-Schnappschuss -- nichts zum
    Einfrieren vorhanden."""
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Steildach")  # keine Vorlage dafür
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])

    link = db.scalar(select(ServiceReportRoofArea).where(ServiceReportRoofArea.service_report_id == report["id"]))
    assert link.inspection_template_id is None
    assert link.inspection_template_label_snapshot is None


# ---------------------------------------------------------------------------
# Kernfall: Umbenennung NACH Anlage darf die Anzeige nicht rückwirkend ändern
# ---------------------------------------------------------------------------

def test_report_roof_area_template_label_stays_frozen_after_template_renamed():
    db = db_session()
    template = _seed_test_template(db, roof_type="Flachdach", label="Testvorlage")
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])

    # Vorlage NACH der Berichtsanlage umbenennen.
    update_template(db, template["id"], "Testvorlage (umbenannt)", "Flachdach", None)

    row = _load_report(db, report["id"])
    updated = report_to_dict(row)
    assert updated["roof_areas"][0]["inspection_template_label"] == "Testvorlage"


def test_report_to_dict_falls_back_to_live_label_when_snapshot_missing():
    """Bestandszeilen ohne Schnappschuss (vor 1.3.22 angelegt) -- Rückfall auf den aktuellen
    Namen, damit sie nicht plötzlich leer erscheinen."""
    db = db_session()
    _seed_test_template(db, roof_type="Flachdach", label="Testvorlage")
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])

    link = db.scalar(select(ServiceReportRoofArea).where(ServiceReportRoofArea.service_report_id == report["id"]))
    link.inspection_template_label_snapshot = None
    db.commit()

    row = _load_report(db, report["id"])
    assert report_to_dict(row)["roof_areas"][0]["inspection_template_label"] == "Testvorlage"


# ---------------------------------------------------------------------------
# Migration 14b130f9c315: Bestandszeilen aus dem heutigen Namen befuellen
# ---------------------------------------------------------------------------

def _load_migration():
    path = next(Path(__file__).resolve().parents[1].glob("alembic/versions/*_inspection_template_label_snapshot.py"))
    spec = importlib.util.spec_from_file_location("migration_1322_template_label_snapshot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _new_engine_with_schema():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_migration_backfills_existing_rows_from_current_template_label():
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
    template = InspectionTemplate(label="Bestandsvorlage", sort_order=10)
    db.add(template)
    db.flush()
    project = Project(project_number="P-TEST-0097", name="Testprojekt", customer_id=customer.id)
    db.add(project)
    db.flush()
    order = Order(
        order_number="AUF-TEST-0097", project_id=project.id, source_quote_id=97, quote_number_snapshot="A-TEST-0097",
        title="Testauftrag", customer_name="Test Kunde",
    )
    db.add(order)
    db.flush()
    report = ServiceReport(order_id=order.id, report_type="wartung", status="entwurf")
    db.add(report)
    db.flush()
    # Schnappschuss-Spalte existiert bereits (Base.metadata.create_all()), bleibt hier aber bewusst
    # leer -- genau der Zustand einer echten Bestandszeile vor dieser Migration.
    link = ServiceReportRoofArea(
        service_report_id=report.id, roof_area_id=area.id, inspection_template_id=template.id,
    )
    db.add(link)
    db.commit()
    link_id = link.id
    db.close()

    with engine.connect() as conn:
        migration._backfill_service_report_roof_area_template_label_snapshots(conn)
        conn.commit()

    db = Session()
    assert db.get(ServiceReportRoofArea, link_id).inspection_template_label_snapshot == "Bestandsvorlage"
    db.close()


def test_migration_backfill_leaves_rows_without_template_untouched():
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
    project = Project(project_number="P-TEST-0096", name="Testprojekt", customer_id=customer.id)
    db.add(project)
    db.flush()
    order = Order(
        order_number="AUF-TEST-0096", project_id=project.id, source_quote_id=96, quote_number_snapshot="A-TEST-0096",
        title="Testauftrag", customer_name="Test Kunde",
    )
    db.add(order)
    db.flush()
    report = ServiceReport(order_id=order.id, report_type="rapport", status="entwurf")
    db.add(report)
    db.flush()
    link = ServiceReportRoofArea(service_report_id=report.id, roof_area_id=area.id, inspection_template_id=None)
    db.add(link)
    db.commit()
    link_id = link.id
    db.close()

    with engine.connect() as conn:
        migration._backfill_service_report_roof_area_template_label_snapshots(conn)
        conn.commit()

    db = Session()
    assert db.get(ServiceReportRoofArea, link_id).inspection_template_label_snapshot is None
    db.close()
