from datetime import date, timedelta

from app.findings import create_finding, list_findings_for_component, update_finding_followup
from app.modules import set_module_enabled
from app.models import Finding, Project, ServiceReportPhoto, Task
from app.roof_areas import create_roof_area, create_roof_component, delete_roof_component
from app.service_report_pdf import build_service_report_pdf
from app.service_reports import add_photo, create_report, delete_photo, delete_report, list_inspection_items, list_photos, sign_report, update_inspection_item
from tests.test_v133_invoices import make_order_with_item
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property
from tests.test_v213_inspection_items import TINY_PNG, _extract_pdf_text, _seed_test_template


def _make_order_for_report(db):
    order, _ = make_order_with_item(db)
    return order


def _build_extra_order(db, suffix, source_quote_id):
    """Ein zweiter, unabhängiger Auftrag in derselben Test-DB -- make_order_with_item() nutzt
    feste Literale (order_number/project_number/source_quote_id=1) und kollidiert deshalb bei
    einem zweiten Aufruf im selben Test (UNIQUE-Constraints) bzw. mit einer später über
    create_quick_service_order() real angelegten Quote #1. Gleiches Konstruktionsmuster wie
    make_order_with_item(), nur mit eindeutigen Literalen je Aufruf."""
    from decimal import Decimal
    from app.models import Customer, Order, Project
    customer = Customer(name=f"Test Kunde {suffix}", last_name=f"Test Kunde {suffix}")
    db.add(customer)
    db.flush()
    project = Project(project_number=f"P-TEST-{suffix}", name=f"Testprojekt {suffix}", customer_id=customer.id)
    db.add(project)
    db.flush()
    order = Order(
        order_number=f"AUF-TEST-{suffix}", project_id=project.id, source_quote_id=source_quote_id,
        quote_number_snapshot=f"A-TEST-{suffix}", title="Testauftrag", vat_rate=Decimal("19.00"),
        customer_name=f"Test Kunde {suffix}", customer_number=f"K-{suffix}",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order, customer, project


def _patch_storage_roots(tmp_path):
    """Gemeinsame Vorbereitung für Tests, die tatsächlich Dateien schreiben (Unterschrift
    und/oder Foto) -- gleiches Muster wie test_v213_inspection_items.py."""
    from app import service_report_photos as photos_module
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"
    photos_module.PHOTO_ROOT = tmp_path / "photos"


def _answer_required_items(db, report_id):
    for item in list_inspection_items(db, report_id):
        if item["required"]:
            update_inspection_item(db, item["id"], {"result": "ok", "condition_grade": 1})


def test_sign_report_blocks_on_negative_item_without_finding_then_with_photo_succeeds(tmp_path):
    _patch_storage_roots(tmp_path)
    db = db_session()
    _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    create_roof_component(db, area["id"], "Gully 1", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    _answer_required_items(db, report["id"])

    ablauf_item = next(i for i in list_inspection_items(db, report["id"]) if i["text"] == "Gully 1: Ablauf frei und funktionsfähig")
    update_inspection_item(db, ablauf_item["id"], {"result": "nok"})

    try:
        sign_report(db, report["id"], installer_signature_png_bytes=b"sig", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"sig", customer_signature_name="Max Mustermann")
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "1" in str(exc)

    finding = create_finding(db, report["id"], "Gully verstopft", "mittel", "sofort_behoben", inspection_item_id=ablauf_item["id"])
    assert finding["roof_component_id"] is not None  # aus dem Prüfpunkt übernommen

    try:
        sign_report(db, report["id"], installer_signature_png_bytes=b"sig", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"sig", customer_signature_name="Max Mustermann")
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Foto" in str(exc)

    add_photo(db, report["id"], TINY_PNG, "foto.png", finding_id=finding["id"])
    signed = sign_report(db, report["id"], installer_signature_png_bytes=b"sig", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"sig", customer_signature_name="Max Mustermann")
    assert signed["status"] == "unterschrieben"


def test_resubmission_date_required_for_zurueckgestellt_at_create_and_sign(tmp_path):
    _patch_storage_roots(tmp_path)
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")

    try:
        create_finding(db, report["id"], "Dachluke klemmt", "gering", "zurueckgestellt")
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass

    finding = create_finding(
        db, report["id"], "Dachluke klemmt", "gering", "zurueckgestellt", resubmission_date=date.today() + timedelta(days=30),
    )
    add_photo(db, report["id"], TINY_PNG, "foto.png", finding_id=finding["id"])
    # resubmission_date direkt in der Datenbank entfernen, um sign_report()s eigene,
    # zusätzliche Absicherung unabhängig von create_finding() zu prüfen.
    row = db.get(Finding, finding["id"])
    row.resubmission_date = None
    db.commit()
    try:
        sign_report(db, report["id"], installer_signature_png_bytes=b"sig", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"sig", customer_signature_name="Max Mustermann")
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Wiedervorlage" in str(exc)


def test_signed_report_pdf_regression_without_findings_or_photos(tmp_path):
    _patch_storage_roots(tmp_path)
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport", description="Dach kontrolliert, keine Mängel.")
    sign_report(db, report["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Test", customer_signature_png_bytes=TINY_PNG, customer_signature_name="Max Mustermann")

    from app.service_reports import _load as _load_report
    row = _load_report(db, report["id"])
    pdf_bytes = build_service_report_pdf(db, row)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Dokumentation" not in text
    assert b"Festgestellte" not in text


def test_signed_report_pdf_includes_findings_and_documentation_sections(tmp_path):
    _patch_storage_roots(tmp_path)
    db = db_session()
    _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    create_roof_component(db, area["id"], "Gully Nordost", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    _answer_required_items(db, report["id"])

    ablauf_item = next(i for i in list_inspection_items(db, report["id"]) if i["text"] == "Gully Nordost: Ablauf frei und funktionsfähig")
    add_photo(db, report["id"], TINY_PNG, "doku.png", inspection_item_id=ablauf_item["id"])

    finding = create_finding(db, report["id"], "Moosbewuchs", "gering", "sofort_behoben")
    add_photo(db, report["id"], TINY_PNG, "mangel.png", finding_id=finding["id"])

    signed = sign_report(db, report["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Test", customer_signature_png_bytes=TINY_PNG, customer_signature_name="Max Mustermann")
    assert signed["status"] == "unterschrieben"

    from app.service_reports import _load as _load_report
    row = _load_report(db, report["id"])
    pdf_bytes = build_service_report_pdf(db, row)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Dokumentation" in text
    assert b"Festgestellte" in text
    assert b"Moosbewuchs" in text


def test_buero_pruefen_can_be_retried_after_module_enabled_later():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    set_module_enabled(db, "aufgabenmanagement", False)

    finding = create_finding(db, report["id"], "Riss in der Attika", "mittel", "buero_pruefen")
    assert finding["follow_up_task_id"] is None
    assert finding["status"] == "offen"
    assert db.query(Task).count() == 0

    set_module_enabled(db, "aufgabenmanagement", True)
    updated = update_finding_followup(db, finding["id"], action="buero_pruefen")
    assert updated["follow_up_task_id"] is not None
    assert updated["status"] == "in_bearbeitung"
    assert db.query(Task).count() == 1

    # Ein weiterer Versuch scheitert jetzt, da die Aufgabe bereits existiert.
    try:
        update_finding_followup(db, finding["id"], action="buero_pruefen")
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass
    assert db.query(Task).count() == 1


def test_action_change_away_from_sofort_behoben_resets_closed_at_and_creates_task():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    finding = create_finding(db, report["id"], "Dachpappe lose", "gering", "sofort_behoben")
    assert finding["status"] == "erledigt"
    assert finding["closed_at"] is not None

    updated = update_finding_followup(db, finding["id"], action="buero_pruefen")
    assert updated["closed_at"] is None
    assert updated["closed_by_employee_id"] is None
    assert updated["status"] == "in_bearbeitung"
    assert db.query(Task).count() == 1


def test_buero_pruefen_creates_only_a_task_never_an_order_or_project():
    """Seit 1.2.21 der zentrale Verhaltensunterschied zum früheren "folgeauftrag": das Anlegen
    eines Mangels mit action="buero_pruefen" erzeugt IMMER nur eine Aufgabe, nie einen echten
    Auftrag/Projekt -- der Monteur bleibt im (noch nicht unterschriebenen) Bericht."""
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    finding = create_finding(db, report["id"], "Ziegel gebrochen, Büro soll prüfen", "dringend", "buero_pruefen")
    assert finding["follow_up_task_id"] is not None
    assert finding["follow_up_order_id"] is None
    assert finding["follow_up_project_id"] is None
    assert finding["status"] == "in_bearbeitung"
    assert db.query(Task).count() == 1


def test_finding_photo_must_belong_to_exactly_one_of_item_or_finding():
    db = db_session()
    _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    create_roof_component(db, area["id"], "Gully 1", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    finding = create_finding(db, report["id"], "Test", "gering", "sofort_behoben")
    item = list_inspection_items(db, report["id"])[0]

    try:
        add_photo(db, report["id"], TINY_PNG, "x.png")
        assert False, "sollte ValueError auslösen (keine Zuordnung)"
    except ValueError:
        pass

    try:
        add_photo(db, report["id"], TINY_PNG, "x.png", inspection_item_id=item["id"], finding_id=finding["id"])
        assert False, "sollte ValueError auslösen (beide gesetzt)"
    except ValueError:
        pass


def test_before_after_photo_limit_and_kind_normalization():
    db = db_session()
    from app.inspection_templates import create_template, create_template_item
    template = create_template(db, "Vorher-Nachher-Test")
    create_template_item(db, template["id"], "Vorher/Nachher-Punkt", "ja_nein", photo_before_after=True, sort_order=10)
    create_template_item(db, template["id"], "Normaler Punkt", "ja_nein", photo_before_after=False, sort_order=20)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]], inspection_template_id=template["id"])
    items = list_inspection_items(db, report["id"])
    ba_item = next(i for i in items if i["photo_before_after"])
    normal_item = next(i for i in items if not i["photo_before_after"])

    add_photo(db, report["id"], TINY_PNG, "vorher.png", inspection_item_id=ba_item["id"], kind="vorher")
    try:
        add_photo(db, report["id"], TINY_PNG, "vorher2.png", inspection_item_id=ba_item["id"], kind="vorher")
        assert False, "sollte ValueError auslösen (zweites 'vorher')"
    except ValueError:
        pass
    add_photo(db, report["id"], TINY_PNG, "nachher.png", inspection_item_id=ba_item["id"], kind="nachher")

    photo = add_photo(db, report["id"], TINY_PNG, "egal.png", inspection_item_id=normal_item["id"], kind="vorher")
    assert photo["kind"] == "allgemein"


def test_delete_draft_report_removes_photos_from_disk_and_cleans_up_task(tmp_path):
    _patch_storage_roots(tmp_path)
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    finding = create_finding(db, report["id"], "Kaputt", "mittel", "buero_pruefen")
    assert finding["follow_up_task_id"] is not None
    photo = add_photo(db, report["id"], TINY_PNG, "foto.png", finding_id=finding["id"])

    from app.service_report_photos import photo_path
    stored_path = photo_path(db.get(ServiceReportPhoto, photo["id"]).file_path)
    assert stored_path.is_file()

    assert delete_report(db, report["id"]) is True
    assert not stored_path.is_file()
    assert db.query(ServiceReportPhoto).count() == 0
    assert db.query(Finding).count() == 0
    assert db.query(Task).count() == 0


def test_delete_photo_removes_file_when_report_still_draft(tmp_path):
    _patch_storage_roots(tmp_path)
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    finding = create_finding(db, report["id"], "Kaputt", "gering", "sofort_behoben")
    photo = add_photo(db, report["id"], TINY_PNG, "foto.png", finding_id=finding["id"])

    from app.service_report_photos import photo_path
    stored_path = photo_path(db.get(ServiceReportPhoto, photo["id"]).file_path)
    assert stored_path.is_file()

    assert delete_photo(db, photo["id"]) is True
    assert not stored_path.is_file()
    assert list_photos(db, report["id"]) == []


def test_findings_and_photos_immutable_after_signature(tmp_path):
    _patch_storage_roots(tmp_path)
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    finding = create_finding(db, report["id"], "Kaputt", "gering", "sofort_behoben")
    photo = add_photo(db, report["id"], TINY_PNG, "foto.png", finding_id=finding["id"])
    sign_report(db, report["id"], installer_signature_png_bytes=b"sig", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"sig", customer_signature_name="Max Mustermann")

    try:
        add_photo(db, report["id"], TINY_PNG, "zweites.png", finding_id=finding["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass
    try:
        delete_photo(db, photo["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass
    try:
        create_finding(db, report["id"], "Weiterer Mangel", "gering", "sofort_behoben")
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass

    # update_finding_followup() bleibt die einzige Ausnahme -- auch nach der Unterschrift.
    updated = update_finding_followup(db, finding["id"], status="in_bearbeitung")
    assert updated["status"] == "in_bearbeitung"
    changed_action = update_finding_followup(db, finding["id"], action="buero_pruefen")
    assert changed_action["action"] == "buero_pruefen"


def test_delete_roof_component_blocks_when_finding_references_it_regardless_of_report_status(tmp_path):
    _patch_storage_roots(tmp_path)
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")
    component = create_roof_component(db, area["id"], "Gully 1")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    finding = create_finding(db, report["id"], "Verstopft", "gering", "sofort_behoben", roof_component_id=component["id"])

    try:
        delete_roof_component(db, component["id"])
        assert False, "sollte ValueError auslösen (Entwurf)"
    except ValueError:
        pass

    add_photo(db, report["id"], TINY_PNG, "foto.png", finding_id=finding["id"])
    sign_report(db, report["id"], installer_signature_png_bytes=b"sig", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"sig", customer_signature_name="Max Mustermann")
    try:
        delete_roof_component(db, component["id"])
        assert False, "sollte ValueError auslösen (unterschrieben)"
    except ValueError:
        pass


def test_list_findings_for_component_returns_chronological_history():
    db = db_session()
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach")
    component = create_roof_component(db, area["id"], "Gully 1")
    order1 = _make_order_for_report(db)
    report1 = create_report(db, order1.id, "rapport", performed_at=date(2026, 1, 10))
    finding1 = create_finding(db, report1["id"], "Erste Verstopfung", "gering", "sofort_behoben", roof_component_id=component["id"])

    order2, _customer2, _project2 = _build_extra_order(db, "0002", source_quote_id=2)
    report2 = create_report(db, order2.id, "rapport", performed_at=date(2026, 3, 5))
    finding2 = create_finding(db, report2["id"], "Zweite Verstopfung", "mittel", "sofort_behoben", roof_component_id=component["id"])

    history = list_findings_for_component(db, component["id"])
    assert [h["id"] for h in history] == [finding1["id"], finding2["id"]]


def test_router_endpoints_create_finding_and_reject_sign_without_photo(threaded_db_session, router_test_client):
    from app.routers.findings import router as findings_router
    from app.routers.service_reports import router as service_reports_router

    db = threaded_db_session
    order = _make_order_for_report(db)
    client = router_test_client(db, service_reports_router, findings_router)

    resp = client.post(f"/api/orders/{order.id}/service-reports", json={"report_type": "rapport"})
    assert resp.status_code == 200, resp.text
    report_id = resp.json()["id"]

    finding_resp = client.post(
        f"/api/service-reports/{report_id}/findings",
        json={"description": "Kaputt", "severity": "mittel", "action": "sofort_behoben"},
    )
    assert finding_resp.status_code == 200, finding_resp.text
    finding_id = finding_resp.json()["id"]

    sign_resp = client.post(f"/api/service-reports/{report_id}/sign", json={
        "installer_signature_png_base64": "AAAA", "installer_signature_name": "Monteur Test",
        "customer_signature_png_base64": "AAAA", "customer_signature_name": "Max Mustermann",
    })
    assert sign_resp.status_code == 400
    assert "Foto" in sign_resp.json()["detail"]

    list_resp = client.get("/api/findings")
    assert list_resp.status_code == 200
    assert any(f["id"] == finding_id for f in list_resp.json())
