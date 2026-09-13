"""Version 1.2.23 -- Materialerfassung am Einsatzbericht, Rechnung aus Aufwand um Material
erweitert."""

from decimal import Decimal

from app.calculation import effective_material_sale_price, get_or_create_settings
from app.invoices import create_invoice_from_time_entries
from app.materials import create_manual_material
from app.models import Material
from app.roof_areas import create_roof_area
from app.service_report_pdf import build_service_report_pdf
from app.service_reports import (
    _load as _load_report,
    add_material,
    create_report,
    delete_material,
    list_materials_for_invoicing,
    list_materials_for_report,
    sign_report,
    update_material,
)
from tests.test_v133_invoices import make_order_with_item
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v213_inspection_items import TINY_PNG, _extract_pdf_text, _make_order_for_report, _seed_test_template
from tests.test_v214_findings_and_photos import _build_extra_order


def _make_material(db, name="Bitumenbahn", unit="m2", purchase_price="12.50", price_basis="1"):
    return create_manual_material(db, name, unit, Decimal(purchase_price), price_basis=Decimal(price_basis))


# --- Anlegen/Bearbeiten/Löschen ---

def test_add_material_from_catalog_copies_description_and_unit_as_snapshot():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    material = _make_material(db, name="Bitumenbahn G200", unit="m2")

    row = add_material(db, report["id"], material_id=material.id, quantity=Decimal("5"))
    assert row["description"] == "Bitumenbahn G200"
    assert row["unit"] == "m2"
    assert row["material_id"] == material.id
    assert "price" not in row and "purchase_price" not in row  # keine Preisdaten im Ergebnis


def test_add_material_free_text_creates_no_catalog_entry():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    before = db.query(Material).count()

    row = add_material(db, report["id"], description="3 Dachziegel vom Lager", quantity=Decimal("3"), unit="Stk")
    assert row["material_id"] is None
    assert row["description"] == "3 Dachziegel vom Lager"
    assert db.query(Material).count() == before  # kein neuer Katalogeintrag


def test_add_material_free_text_requires_description():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    try:
        add_material(db, report["id"], description="   ", quantity=Decimal("1"))
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Bezeichnung" in str(exc)


def test_add_material_rejects_non_positive_quantity():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    try:
        add_material(db, report["id"], description="Test", quantity=Decimal("0"))
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Menge" in str(exc)


def test_add_material_rejects_roof_area_not_covered_by_report():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    other_customer, other_prop = make_customer_and_property(db)
    foreign_area = create_roof_area(db, other_prop.id, "Fremde Fläche")
    order = _make_order_for_report(db)
    area = create_roof_area(db, prop.id, "Eigene Fläche")
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    try:
        add_material(db, report["id"], description="Test", quantity=Decimal("1"), roof_area_id=foreign_area["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Dachfläche" in str(exc)


def test_add_material_rejects_inspection_item_and_finding_from_other_report():
    db = db_session()
    order1 = _make_order_for_report(db)
    order2, _customer2, _project2 = _build_extra_order(db, "9223", source_quote_id=9223)
    template = _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Fläche", roof_type="Flachdach")
    report1 = create_report(db, order1.id, "wartung", roof_area_ids=[area["id"]])
    report2 = create_report(db, order2.id, "rapport")
    foreign_item = _load_report(db, report1["id"]).inspection_items[0]

    try:
        add_material(db, report2["id"], description="Test", quantity=Decimal("1"), inspection_item_id=foreign_item.id)
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Prüfpunkt" in str(exc)

    from app.findings import create_finding
    finding = create_finding(db, report1["id"], "Mangel", "gering", "sofort_behoben")
    try:
        add_material(db, report2["id"], description="Test", quantity=Decimal("1"), finding_id=finding["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Mangel" in str(exc)


def test_update_material_exclude_unset_and_material_id_switch_recopies_snapshot():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    material_a = _make_material(db, name="Material A", unit="Stk")
    material_b = _make_material(db, name="Material B", unit="kg")
    row = add_material(db, report["id"], material_id=material_a.id, quantity=Decimal("2"), notes="Ursprüngliche Notiz")

    updated = update_material(db, row["id"], {"quantity": Decimal("4")})
    assert updated["quantity"] == Decimal("4")
    assert updated["notes"] == "Ursprüngliche Notiz"  # nicht mitgeschickt -> unverändert
    assert updated["description"] == "Material A"  # ebenfalls unverändert

    switched = update_material(db, row["id"], {"material_id": material_b.id})
    assert switched["description"] == "Material B"
    assert switched["unit"] == "kg"


def test_delete_material():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    row = add_material(db, report["id"], description="Test", quantity=Decimal("1"))
    assert delete_material(db, row["id"]) is True
    assert list_materials_for_report(db, report["id"]) == []
    assert delete_material(db, row["id"]) is False


def test_material_blocked_after_signature():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    row = add_material(db, report["id"], description="Test", quantity=Decimal("1"))
    sign_report(db, report["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Max Mustermann")

    try:
        add_material(db, report["id"], description="Neu", quantity=Decimal("1"))
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass
    try:
        update_material(db, row["id"], {"quantity": Decimal("5")})
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass
    try:
        delete_material(db, row["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_sign_report_without_any_material_is_unaffected():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    signed = sign_report(db, report["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Max Mustermann")
    assert signed["status"] == "unterschrieben"


def test_client_uuid_unique_constraint_allows_multiple_nulls_but_not_duplicate_value():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    add_material(db, report["id"], description="A", quantity=Decimal("1"))
    add_material(db, report["id"], description="B", quantity=Decimal("1"))  # zwei client_uuid=None -- erlaubt

    add_material(db, report["id"], description="C", quantity=Decimal("1"), client_uuid="11111111-1111-1111-1111-111111111111")
    try:
        add_material(db, report["id"], description="D", quantity=Decimal("1"), client_uuid="11111111-1111-1111-1111-111111111111")
        assert False, "sollte IntegrityError auslösen"
    except Exception as exc:
        db.rollback()
        assert "UNIQUE" in str(exc) or "unique" in str(exc).lower()


# --- PDF ---

def test_pdf_material_section_only_appears_when_materials_exist(tmp_path):
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport", description="Ohne Material")
    sign_report(db, report["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Test", customer_signature_png_bytes=TINY_PNG, customer_signature_name="Max Mustermann")

    row = _load_report(db, report["id"])
    pdf_bytes = build_service_report_pdf(db, row)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Verbrauchtes Material" not in text  # Regressionsbeleg: identisch zu 1.2.22


def test_pdf_material_section_groups_by_area_and_shows_no_prices(tmp_path):
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area_a = create_roof_area(db, prop.id, "Flaeche Nord")
    area_b = create_roof_area(db, prop.id, "Flaeche Sued")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area_a["id"], area_b["id"]])
    add_material(db, report["id"], description="Bitumenbahn", quantity=Decimal("12.5"), unit="m2", roof_area_id=area_a["id"])
    add_material(db, report["id"], description="Dachlatte", quantity=Decimal("3"), unit="Stk", roof_area_id=area_b["id"])
    sign_report(db, report["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Test", customer_signature_png_bytes=TINY_PNG, customer_signature_name="Max Mustermann")

    row = _load_report(db, report["id"])
    pdf_bytes = build_service_report_pdf(db, row)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Verbrauchtes Material" in text
    assert b"Flaeche Nord" in text and b"Flaeche Sued" in text
    assert b"Bitumenbahn" in text and b"Dachlatte" in text
    assert b"12,50" in text
    assert b"12.50" not in text  # kein Katalogpreis, keine Punkt-Dezimalschreibweise als Preis


# --- Rechnung aus Aufwand ---

def test_effective_material_sale_price_with_and_without_markup():
    assert effective_material_sale_price(Decimal("10"), Decimal("1"), Decimal("0")) == Decimal("10")
    assert effective_material_sale_price(Decimal("10"), Decimal("1"), Decimal("20")) == Decimal("12")
    assert effective_material_sale_price(Decimal("100"), Decimal("100"), Decimal("0")) == Decimal("1")
    assert effective_material_sale_price(Decimal("10"), Decimal("0"), Decimal("0")) == Decimal("10")  # price_basis==0-Schutz


def test_invoice_from_effort_prices_catalog_material_with_configured_markup():
    db = db_session()
    settings = get_or_create_settings(db)
    settings.material_markup_pct = Decimal("20")
    db.commit()

    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport")
    material = _make_material(db, name="Bitumenbahn", unit="m2", purchase_price="10.00")
    add_material(db, report["id"], material_id=material.id, quantity=Decimal("5"))
    sign_report(db, report["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Max Mustermann")

    materials = list_materials_for_invoicing(db, order.id)
    invoice = create_invoice_from_time_entries(db, order, [], materials)
    material_item = next(i for i in invoice.items if i.short_text == "Bitumenbahn")
    assert material_item.unit_price == Decimal("12.00")  # 10 * 1.2
    assert material_item.ist_quantity == Decimal("5")
    assert material_item.billed_total == Decimal("60.00")


def test_invoice_from_effort_uses_bare_purchase_price_when_markup_is_zero_default():
    """Hält ausdrücklich fest (nicht verhindert): material_markup_pct==0 (Standardwert jeder
    Installation, die ihn nie konfiguriert hat) führt zum nackten Einkaufspreis in der
    Rechnung -- genau der Zustand, den der sichtbare Hinweis im Router abfangen soll."""
    db = db_session()
    settings = get_or_create_settings(db)
    assert settings.material_markup_pct == Decimal("0")  # Standardwert, nicht extra gesetzt

    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport")
    material = _make_material(db, name="Bitumenbahn", unit="m2", purchase_price="10.00")
    add_material(db, report["id"], material_id=material.id, quantity=Decimal("5"))
    sign_report(db, report["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Max Mustermann")

    materials = list_materials_for_invoicing(db, order.id)
    invoice = create_invoice_from_time_entries(db, order, [], materials)
    material_item = next(i for i in invoice.items if i.short_text == "Bitumenbahn")
    assert material_item.unit_price == Decimal("10.00")  # bestätigt, nicht verhindert


def test_invoice_from_effort_free_material_has_zero_price_and_is_never_merged():
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport")
    add_material(db, report["id"], description="Dachziegel Rest", quantity=Decimal("2"), unit="Stk")
    add_material(db, report["id"], description="Dachziegel Rest", quantity=Decimal("3"), unit="Stk")
    sign_report(db, report["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Max Mustermann")

    materials = list_materials_for_invoicing(db, order.id)
    invoice = create_invoice_from_time_entries(db, order, [], materials)
    free_items = [i for i in invoice.items if i.short_text == "Dachziegel Rest"]
    assert len(free_items) == 2  # NIE zusammengefasst, auch bei identischem Text nicht
    assert all(i.unit_price == Decimal("0") for i in free_items)


def test_invoice_from_effort_merges_same_catalog_material_across_two_signed_reports():
    db = db_session()
    order, _ = make_order_with_item(db)
    material = _make_material(db, name="Bitumenbahn", unit="m2", purchase_price="10.00")

    report1 = create_report(db, order.id, "rapport")
    add_material(db, report1["id"], material_id=material.id, quantity=Decimal("5"))
    sign_report(db, report1["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Max Mustermann")

    report2 = create_report(db, order.id, "rapport")
    add_material(db, report2["id"], material_id=material.id, quantity=Decimal("3"))
    sign_report(db, report2["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Erika Musterfrau")

    materials = list_materials_for_invoicing(db, order.id)
    assert len(materials) == 2
    invoice = create_invoice_from_time_entries(db, order, [], materials)
    catalog_items = [i for i in invoice.items if i.short_text == "Bitumenbahn"]
    assert len(catalog_items) == 1
    assert catalog_items[0].ist_quantity == Decimal("8")


def test_invoice_from_effort_ignores_draft_report_material():
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport")  # bleibt Entwurf, nie unterschrieben
    add_material(db, report["id"], description="Nicht abrechenbar", quantity=Decimal("1"))
    materials = list_materials_for_invoicing(db, order.id)
    assert materials == []


def test_invoice_from_effort_regression_without_any_material_matches_pre_1_2_23_behavior():
    """Expliziter Regressionstest: ein Auftrag ohne jedes Material erzeugt dieselbe Rechnung wie
    vor dieser Version (test_v204: gruppiert nach Mitarbeiter+Tätigkeit, Stundenpreis, keine
    zusätzlichen Positionen)."""
    from app.models import Employee, TimeEntry
    from datetime import date as _date

    db = db_session()
    order, _ = make_order_with_item(db)
    emp = Employee(employee_number="T-1", first_name="Max", last_name="Muster",
                    employee_group="gewerblich", hourly_wage="25", active=True)
    db.add(emp); db.commit()
    entry = TimeEntry(employee=emp, project_id=order.project_id, order_id=order.id, work_date=_date.today(),
                       activity="Reparatur", hours=Decimal("2.0"), status="booked")
    db.add(entry); db.commit()

    invoice = create_invoice_from_time_entries(db, order, [entry], [])
    assert len(invoice.items) == 1
    assert invoice.items[0].short_text == "Reparatur"
    assert invoice.items[0].ist_quantity == Decimal("2.0")


def test_router_endpoint_sets_material_markup_hint_only_when_relevant(threaded_db_session, router_test_client):
    from app.routers.invoices import router as invoices_router
    from app.schemas import InvoiceCreateFromOrder

    db = threaded_db_session
    order, _ = make_order_with_item(db)
    material = _make_material(db, name="Bitumenbahn", unit="m2", purchase_price="10.00")
    report = create_report(db, order.id, "rapport")
    add_material(db, report["id"], material_id=material.id, quantity=Decimal("1"))
    sign_report(db, report["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Max Mustermann")

    client = router_test_client(db, invoices_router)
    resp = client.post(f"/api/orders/{order.id}/invoices/aus-zeitbuchungen", json={"due_date": None})
    assert resp.status_code == 200, resp.text
    assert resp.json()["material_markup_hint"] is not None


def test_router_endpoint_material_markup_hint_absent_with_configured_markup(threaded_db_session, router_test_client):
    from app.routers.invoices import router as invoices_router
    from app.calculation import get_or_create_settings as _settings

    db = threaded_db_session
    settings = _settings(db)
    settings.material_markup_pct = Decimal("15")
    db.commit()
    order, _ = make_order_with_item(db)
    material = _make_material(db, name="Bitumenbahn", unit="m2", purchase_price="10.00")
    report = create_report(db, order.id, "rapport")
    add_material(db, report["id"], material_id=material.id, quantity=Decimal("1"))
    sign_report(db, report["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Max Mustermann")

    client = router_test_client(db, invoices_router)
    resp = client.post(f"/api/orders/{order.id}/invoices/aus-zeitbuchungen", json={"due_date": None})
    assert resp.status_code == 200, resp.text
    assert resp.json().get("material_markup_hint") is None


def test_router_endpoint_material_markup_hint_absent_for_free_material_only(threaded_db_session, router_test_client):
    from app.routers.invoices import router as invoices_router

    db = threaded_db_session
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport")
    add_material(db, report["id"], description="Freies Material", quantity=Decimal("1"))
    sign_report(db, report["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Max Mustermann")

    client = router_test_client(db, invoices_router)
    resp = client.post(f"/api/orders/{order.id}/invoices/aus-zeitbuchungen", json={"due_date": None})
    assert resp.status_code == 200, resp.text
    assert resp.json().get("material_markup_hint") is None


# --- Router: neue Material-Endpunkte ---

def test_router_endpoints_for_service_report_materials(threaded_db_session, router_test_client):
    from app.routers.service_reports import router as service_reports_router

    db = threaded_db_session
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    client = router_test_client(db, service_reports_router)

    post_resp = client.post(
        f"/api/service-reports/{report['id']}/materials",
        json={"description": "Testmaterial", "quantity": "2.5", "unit": "Stk"},
    )
    assert post_resp.status_code == 200, post_resp.text
    material_id = post_resp.json()["id"]

    get_resp = client.get(f"/api/service-reports/{report['id']}/materials")
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 1

    put_resp = client.put(f"/api/service-report-materials/{material_id}", json={"quantity": "4"})
    assert put_resp.status_code == 200
    assert Decimal(put_resp.json()["quantity"]) == Decimal("4")

    delete_resp = client.delete(f"/api/service-report-materials/{material_id}")
    assert delete_resp.status_code == 200
    assert client.get(f"/api/service-reports/{report['id']}/materials").json() == []
