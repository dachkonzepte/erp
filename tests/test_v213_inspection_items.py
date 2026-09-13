import base64
import re
import zlib
from decimal import Decimal

from app.inspection_templates import create_template, create_template_item, get_template, update_template_item
from app.models import InspectionItem
from app.roof_areas import (
    create_roof_area, create_roof_component, delete_roof_component, set_roof_component_archived,
)
from app.routers.inspection_templates import router as inspection_templates_router
from app.routers.service_reports import router as service_reports_router
from app.service_report_pdf import _format_inspection_result, build_service_report_pdf
from app.service_reports import (
    add_inspection_item, create_report, delete_inspection_item, list_inspection_items,
    regenerate_inspection_items, sign_report, sync_inspection_items, update_inspection_item,
)
from tests.test_v133_invoices import make_order_with_item
from tests.test_v153_mahnwesen import db_session
from tests.test_v202_maintenance_contracts import make_customer_and_property


def _make_tiny_png() -> bytes:
    """Ein echtes, von PIL erzeugtes PNG statt handgeschriebener Bytes -- build_service_report_pdf()
    baut die Unterschrift über ein platypus.Image-Flowable ein, das PIL zum Dekodieren braucht
    (Muster wie test_v203_service_reports.py)."""
    from io import BytesIO
    from PIL import Image as PILImage
    buf = BytesIO()
    PILImage.new("RGB", (4, 4), "white").save(buf, format="PNG")
    return buf.getvalue()


TINY_PNG = _make_tiny_png()


def _extract_pdf_text(pdf_bytes: bytes) -> bytes:
    """Dekodiert alle Content-Streams selbst (kein pypdf/pdfminer -- gleiches Prinzip wie
    test_v167_pagination.py, das aus demselben Grund bewusst nur unkomprimierte Objektangaben
    prüft) und gibt die verkatteten Rohbytes zurück. reportlab kodiert Streams standardmäßig als
    ASCII85Decode + FlateDecode-Filterkette (kein reines FlateDecode) -- empirisch geprüft,
    nicht aus der reportlab-Doku übernommen. Reicht, um reine ASCII-Substrings im sichtbaren
    Text zu finden (Helvetica/WinAnsi kodiert ASCII 1:1)."""
    chunks = []
    for match in re.finditer(rb">>\s*stream\s*(.*?)\s*endstream", pdf_bytes, re.DOTALL):
        data = match.group(1)
        if data.endswith(b"~>"):
            data = data[:-2]
        try:
            chunks.append(zlib.decompress(base64.a85decode(data, adobe=False)))
        except Exception:
            continue
    return b"".join(chunks)


def _seed_test_template(db, roof_type="Flachdach", label="Testvorlage"):
    """Baut eine Vorlage mit denselben, für die Tests relevanten Punkten wie die echte
    Migrations-Seed-Vorlage "Flachdach Standard" -- eine frische :memory:-Testdatenbank
    (Base.metadata.create_all()) enthält die Migrations-Seed-Daten NICHT, nur echte
    Alembic-Läufe gegen die Datei-Datenbank tun das (gleiches Prinzip wie
    test_v212_maintenance_windows.py, das seine MaintenanceWindow-Zeilen ebenfalls selbst per
    create_window() anlegt statt sich auf die Migrations-Seeds zu verlassen)."""
    template = create_template(db, label, roof_type=roof_type)
    tid = template["id"]
    create_template_item(db, tid, "Zugang und Absturzsicherung geprüft", "ja_nein", group_name="Allgemein", required=True, sort_order=10)
    create_template_item(db, tid, "Gesamtzustand Dachfläche", "condition_grade", group_name="Allgemein", required=True, sort_order=20)
    create_template_item(db, tid, "Ablauf frei und funktionsfähig", "ja_nein", group_name="Entwässerung", component_type="Gully", required=True, sort_order=30)
    create_template_item(db, tid, "Laubfang vorhanden und intakt", "ja_nein", group_name="Entwässerung", component_type="Gully", sort_order=40)
    create_template_item(db, tid, "frei und funktionsfähig", "ja_nein", group_name="Entwässerung", component_type="Notüberlauf", required=True, sort_order=50)
    create_template_item(db, tid, "Abdichtung auf Blasen, Risse, Falten", "condition_grade", group_name="Fläche", required=True, sort_order=80)
    create_template_item(db, tid, "Verglasung und Dichtung", "condition_grade", group_name="Aufbauten", component_type="Lichtkuppel", sort_order=120)
    create_template_item(db, tid, "Dichtheitsprüfung", "leak_test", group_name="Abschluss", sort_order=150)
    create_template_item(db, tid, "Bemerkungen", "free_text", group_name="Abschluss", sort_order=160)
    return get_template(db, tid)


def _make_order_for_report(db):
    """Ein Auftrag ohne Gebäude-/Dachflächenbezug (make_order_with_item() legt ein eigenes,
    property-loses Projekt an) -- roof_area_id wird in den Tests bewusst explizit übergeben,
    die Order->Project->Property-Auflösung wird hier nicht gebraucht."""
    order, _ = make_order_with_item(db)
    return order


def test_generation_creates_expected_item_count_with_component_names_and_order():
    db = db_session()
    template = _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    for i in range(7):
        create_roof_component(db, area["id"], f"Gully {i + 1}", component_type="Gully", sort_order=(i + 1) * 10)
    for i in range(2):
        create_roof_component(db, area["id"], f"Notüberlauf {i + 1}", component_type="Notüberlauf", sort_order=(i + 1) * 10)
    for i in range(3):
        create_roof_component(db, area["id"], f"Lichtkuppel {i + 1}", component_type="Lichtkuppel", sort_order=(i + 1) * 10)

    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    assert report["roof_areas"][0]["inspection_template_id"] == template["id"]

    items = list_inspection_items(db, report["id"])
    # 5 Nicht-Bauteil-Punkte (Allgemein x2, Abdichtung, Dichtheitsprüfung, Bemerkungen)
    # + 7 Gully x 2 Vorlagenpunkte + 2 Notüberlauf x 1 + 3 Lichtkuppel x 1
    assert len(items) == 5 + 7 * 2 + 2 * 1 + 3 * 1

    gully_items = [i for i in items if i["text"].startswith("Gully 1:")]
    assert len(gully_items) == 2  # "Ablauf frei..." und "Laubfang..."
    assert any(i["text"] == "Gully 1: Ablauf frei und funktionsfähig" for i in items)

    # Reihenfolge: Bauteile innerhalb eines Vorlagenpunkts folgen RoofComponent.sort_order.
    ablauf_items = sorted(
        (i for i in items if i["text"].startswith("Gully") and "Ablauf frei" in i["text"]),
        key=lambda i: i["sort_order"],
    )
    assert [i["text"] for i in ablauf_items] == [f"Gully {n}: Ablauf frei und funktionsfähig" for n in range(1, 8)]


def test_report_without_resolvable_roof_area_behaves_like_before():
    """Regression: kein Gebäude/keine Dachfläche -- Bericht verhält sich exakt wie vor 1.2.16."""
    db = db_session()
    _seed_test_template(db)
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung")
    assert report["roof_area_id"] is None
    assert report["inspection_template_id"] is None
    assert list_inspection_items(db, report["id"]) == []

    signed = sign_report(db, report["id"], installer_signature_png_bytes=b"fake-signature-bytes", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"fake-signature-bytes", customer_signature_name="Max Mustermann")
    assert signed["status"] == "unterschrieben"


def test_rapport_without_explicit_template_gets_no_items():
    db = db_session()
    _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport", roof_area_ids=[area["id"]])
    assert report["inspection_template_id"] is None
    assert list_inspection_items(db, report["id"]) == []


def test_rapport_with_explicit_template_gets_items():
    db = db_session()
    template = _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport", roof_area_ids=[area["id"]], inspection_template_id=template["id"])
    assert report["roof_areas"][0]["inspection_template_id"] == template["id"]
    assert len(list_inspection_items(db, report["id"])) > 0


def test_sign_report_blocks_on_open_required_items_and_names_count_then_succeeds():
    db = db_session()
    _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    create_roof_component(db, area["id"], "Gully 1", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])

    items = list_inspection_items(db, report["id"])
    required_items = [i for i in items if i["required"]]
    assert len(required_items) == 4  # Zugang, Gesamtzustand, Abdichtung (alle ohne Bauteil) + Gully "Ablauf frei"

    try:
        sign_report(db, report["id"], installer_signature_png_bytes=b"sig", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"sig", customer_signature_name="Max Mustermann")
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "4" in str(exc)

    for item in required_items[:-1]:
        update_inspection_item(db, item["id"], {"result": "ok", "condition_grade": 1})

    try:
        sign_report(db, report["id"], installer_signature_png_bytes=b"sig", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"sig", customer_signature_name="Max Mustermann")
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "1" in str(exc)

    last = required_items[-1]
    update_inspection_item(db, last["id"], {"result": "ok", "condition_grade": 1})
    signed = sign_report(db, report["id"], installer_signature_png_bytes=b"sig", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"sig", customer_signature_name="Max Mustermann")
    assert signed["status"] == "unterschrieben"


def test_changes_to_inspection_items_blocked_after_signature():
    db = db_session()
    _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    for item in list_inspection_items(db, report["id"]):
        if item["required"]:
            update_inspection_item(db, item["id"], {"result": "ok", "condition_grade": 1})
    sign_report(db, report["id"], installer_signature_png_bytes=b"sig", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"sig", customer_signature_name="Max Mustermann")

    some_item = list_inspection_items(db, report["id"])[0]
    for fn, args in [
        (update_inspection_item, (db, some_item["id"], {})),
        (add_inspection_item, (db, report["id"], "Zusatzpunkt", "free_text")),
        (delete_inspection_item, (db, some_item["id"])),
        (regenerate_inspection_items, (db, report["id"])),
    ]:
        try:
            fn(*args)
            assert False, f"{fn.__name__} sollte ValueError auslösen"
        except ValueError:
            pass


def test_template_change_does_not_affect_existing_report():
    db = db_session()
    template = _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    original_texts = {i["id"]: i["text"] for i in list_inspection_items(db, report["id"])}

    version_before = template["version"]
    first_item = template["items"][0]
    update_template_item(
        db, first_item["id"], "Geänderter Text", first_item["item_type"], first_item["group_name"],
        first_item["component_type"], first_item["required"], first_item["target_min"], first_item["target_max"],
        first_item["unit"], first_item["photo_required"], first_item["photo_before_after"], first_item["sort_order"],
    )
    updated_template = get_template(db, template["id"])
    assert updated_template["version"] == version_before + 1

    current_texts = {i["id"]: i["text"] for i in list_inspection_items(db, report["id"])}
    assert current_texts == original_texts


def test_sync_inspection_items_is_purely_additive():
    db = db_session()
    _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    create_roof_component(db, area["id"], "Gully 1", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])

    ablauf_item = next(i for i in list_inspection_items(db, report["id"]) if i["text"] == "Gully 1: Ablauf frei und funktionsfähig")
    update_inspection_item(db, ablauf_item["id"], {"result": "ok"})

    result_no_change = sync_inspection_items(db, report["id"])
    assert result_no_change["added"] == 0

    new_component = create_roof_component(db, area["id"], "Gully 2", component_type="Gully", sort_order=20)
    result_added = sync_inspection_items(db, report["id"])
    assert result_added["added"] == 2  # Gully hat zwei Vorlagenpunkte ("Ablauf frei" + "Laubfang")

    unchanged = next(i for i in result_added["items"] if i["id"] == ablauf_item["id"])
    assert unchanged["result"] == "ok"  # Sync rührt bereits erfasste Ergebnisse nicht an

    new_item = next(i for i in result_added["items"] if i["text"] == "Gully 2: Ablauf frei und funktionsfähig")
    update_inspection_item(db, new_item["id"], {"result": "nok"})

    delete_roof_component(db, new_component["id"])  # Entwurf, kein signierter Bezug -> erlaubt
    result_after_delete = sync_inspection_items(db, report["id"])
    assert result_after_delete["added"] == 0
    still_present = next(i for i in result_after_delete["items"] if i["id"] == new_item["id"])
    assert still_present["result"] == "nok"  # Punkt zu entferntem Bauteil bleibt unverändert stehen


def test_sort_order_band_holds_with_large_component_sort_order():
    db = db_session()
    _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    create_roof_component(db, area["id"], "Gully hoch sortiert", component_type="Gully", sort_order=5000)
    create_roof_component(db, area["id"], "Notüberlauf 1", component_type="Notüberlauf", sort_order=10)
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])

    items = list_inspection_items(db, report["id"])
    gully_sort_orders = [i["sort_order"] for i in items if i["text"].startswith("Gully hoch sortiert")]
    notueberlauf_sort_orders = [i["sort_order"] for i in items if i["text"].startswith("Notüberlauf 1")]
    # Gully (Vorlagenpunkt sort_order 30/40) muss trotz component sort_order=5000 weiterhin vor
    # Notüberlauf (Vorlagenpunkt sort_order 50) sortieren.
    assert max(gully_sort_orders) < min(notueberlauf_sort_orders)


def test_delete_roof_component_blocks_when_signed_report_references_it_then_succeeds(tmp_path):
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"
    db = db_session()
    _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    component = create_roof_component(db, area["id"], "Gully 1", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    for item in list_inspection_items(db, report["id"]):
        if item["required"]:
            update_inspection_item(db, item["id"], {"result": "ok", "condition_grade": 1})
    sign_report(db, report["id"], installer_signature_png_bytes=b"sig", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"sig", customer_signature_name="Max Mustermann")

    try:
        delete_roof_component(db, component["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass

    # Ein unterschriebener Bericht kann über die App selbst nicht mehr gelöscht werden
    # (GoBD-Unveränderlichkeit) -- die Zeile hier direkt zu entfernen simuliert für den Test
    # ausschließlich "es existiert kein signierter Bezug mehr", kein Produktivpfad.
    from app.service_reports import _load as _load_report
    report_row = _load_report(db, report["id"])
    db.delete(report_row)
    db.commit()
    assert delete_roof_component(db, component["id"]) is True


def test_component_archived_after_signature_report_remains_fully_readable(tmp_path):
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"
    db = db_session()
    _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    component = create_roof_component(db, area["id"], "Gully 1", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    for item in list_inspection_items(db, report["id"]):
        if item["required"]:
            update_inspection_item(db, item["id"], {"result": "ok", "condition_grade": 1})
    sign_report(db, report["id"], installer_signature_png_bytes=b"sig", installer_signature_name="Monteur Test", customer_signature_png_bytes=b"sig", customer_signature_name="Max Mustermann")

    set_roof_component_archived(db, component["id"], True)

    items_after = list_inspection_items(db, report["id"])
    assert any(i["text"] == "Gully 1: Ablauf frei und funktionsfähig" and i["result"] == "ok" for i in items_after)


def test_client_uuid_unique_constraint_allows_multiple_nulls_but_not_duplicate_value():
    db = db_session()
    _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    items = list_inspection_items(db, report["id"])
    assert len(items) >= 2

    update_inspection_item(db, items[0]["id"], {"result": "ok"})
    update_inspection_item(db, items[1]["id"], {"result": "ok"})  # zwei client_uuid=None -- erlaubt

    update_inspection_item(db, items[0]["id"], {"result": "ok", "client_uuid": "11111111-1111-1111-1111-111111111111"})
    try:
        update_inspection_item(db, items[1]["id"], {"result": "ok", "client_uuid": "11111111-1111-1111-1111-111111111111"})
        assert False, "sollte IntegrityError auslösen"
    except Exception as exc:
        assert "UNIQUE" in str(exc) or "unique" in str(exc).lower()


def test_format_inspection_result_covers_all_item_types():
    unanswered = InspectionItem(item_type="ja_nein", result=None)
    assert _format_inspection_result(unanswered) == ("nicht geprüft", False)

    ok = InspectionItem(item_type="ja_nein", result="ok")
    assert _format_inspection_result(ok) == ("OK", False)

    leak = InspectionItem(item_type="leak_test", result="nok", duration_minutes=15)
    text, out_of_range = _format_inspection_result(leak)
    assert "Nicht OK" in text and "15" in text and out_of_range is False

    grade = InspectionItem(item_type="condition_grade", condition_grade=4)
    assert _format_inspection_result(grade) == ("Sanierung erforderlich", False)

    in_range = InspectionItem(item_type="measurement", measured_value=Decimal("7"), target_min=Decimal("5"),
                               target_max=Decimal("10"), unit="mm")
    _, out_of_range = _format_inspection_result(in_range)
    assert out_of_range is False

    out_of_range_item = InspectionItem(item_type="measurement", measured_value=Decimal("12"), target_min=Decimal("5"),
                                        target_max=Decimal("10"), unit="mm")
    _, out_of_range = _format_inspection_result(out_of_range_item)
    assert out_of_range is True

    qty = InspectionItem(item_type="quantity", quantity=Decimal("3"), unit="Stück")
    assert _format_inspection_result(qty) == ("3 Stück", False)

    free_text_answered = InspectionItem(item_type="free_text", notes="Alles in Ordnung")
    assert _format_inspection_result(free_text_answered) == ("erfasst", False)

    free_text_unanswered = InspectionItem(item_type="free_text", notes=None)
    assert _format_inspection_result(free_text_unanswered) == ("nicht geprüft", False)

    photo = InspectionItem(item_type="photo")
    assert _format_inspection_result(photo) == ("Fotoerfassung folgt", False)


def test_signed_report_pdf_includes_inspection_results(tmp_path):
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"
    db = db_session()
    _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    create_roof_component(db, area["id"], "Gully Nordost", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "wartung", roof_area_ids=[area["id"]])
    for item in list_inspection_items(db, report["id"]):
        if item["required"]:
            update_inspection_item(db, item["id"], {"result": "ok", "condition_grade": 1})
    sign_report(db, report["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Test", customer_signature_png_bytes=TINY_PNG, customer_signature_name="Max Mustermann")

    from app.service_reports import _load as _load_report
    row = _load_report(db, report["id"])
    pdf_bytes = build_service_report_pdf(db, row)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Gully Nordost" in text
    assert b"OK" in text


def test_signed_report_pdf_without_inspection_items_is_unchanged(tmp_path):
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport", description="Dach kontrolliert, keine Mängel.")
    sign_report(db, report["id"], installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Test", customer_signature_png_bytes=TINY_PNG, customer_signature_name="Max Mustermann")

    from app.service_reports import _load as _load_report
    row = _load_report(db, report["id"])
    pdf_bytes = build_service_report_pdf(db, row)
    # Kein Unterschied zum Verhalten vor 1.2.16: ohne Prüfpunkte wird die entsprechende
    # story-Sektion gar nicht erst gebaut (if inspection_items: siehe service_report_pdf.py),
    # ein einfaches "baut erfolgreich" reicht als Regressionsbeleg (Muster wie die bestehende
    # test_signed_report_pdf_can_be_built in test_v203_service_reports.py).
    assert pdf_bytes[:4] == b"%PDF"


def test_router_endpoints_generate_items_and_reject_open_required_via_http(threaded_db_session, router_test_client):
    db = threaded_db_session
    _seed_test_template(db)
    customer, prop = make_customer_and_property(db)
    area = create_roof_area(db, prop.id, "Hauptdach", roof_type="Flachdach")
    create_roof_component(db, area["id"], "Gully 1", component_type="Gully", sort_order=10)
    order = _make_order_for_report(db)

    client = router_test_client(db, service_reports_router, inspection_templates_router)
    resp = client.post(f"/api/orders/{order.id}/service-reports", json={"report_type": "wartung", "roof_area_ids": [area["id"]]})
    assert resp.status_code == 200, resp.text
    report_id = resp.json()["id"]
    items_resp = client.get(f"/api/service-reports/{report_id}/inspection-items")
    assert items_resp.status_code == 200
    assert len(items_resp.json()) > 0

    sign_resp = client.post(f"/api/service-reports/{report_id}/sign", json={
        "installer_signature_png_base64": "AAAA", "installer_signature_name": "Monteur Test",
        "customer_signature_png_base64": "AAAA", "customer_signature_name": "Max Mustermann",
    })
    assert sign_resp.status_code == 400
    assert re.search(r"\d+ Pflichtpunkt", sign_resp.json()["detail"])
