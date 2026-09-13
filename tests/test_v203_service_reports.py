from pathlib import Path

from starlette.requests import Request

from app import service_reports
from app.models import AppUser, Employee, ServiceReport
from app.modules import set_module_enabled
from app.service_reports import create_report, delete_report, list_reports, sign_report, update_report
from app.tasks import list_tasks
from tests.test_v133_invoices import make_order_with_item
from tests.test_v153_mahnwesen import db_session


def request_with_user(user):
    req = Request({"type": "http", "method": "GET", "path": "/api/orders/1/service-reports", "headers": [],
                   "query_string": b"", "server": ("test", 80), "client": ("test", 1234), "scheme": "http"})
    req.state.erp_user = user
    return req


def _admin_user():
    return AppUser(id=1, username="admin-test", display_name="Admin", role="admin", active=True, password_hash="x")


def sign_report_for_test(db, report_id, installer_name="Monteur Test", customer_name="Max Mustermann",
                          installer_bytes=None, customer_bytes=None):
    """Testhelfer (seit 1.3.0): sign_report() verlangt jetzt beide Unterschriften in einem
    Aufruf -- die meisten bestehenden Tests wollen nur "diesen Bericht fertig unterschreiben",
    nicht die Zwei-Unterschriften-Mechanik selbst prüfen (das tut
    test_sign_report_writes_signature_file_and_freezes_status gezielt)."""
    installer_bytes = installer_bytes if installer_bytes is not None else TINY_PNG
    customer_bytes = customer_bytes if customer_bytes is not None else TINY_PNG
    return sign_report(
        db, report_id, installer_signature_png_bytes=installer_bytes, installer_signature_name=installer_name,
        customer_signature_png_bytes=customer_bytes, customer_signature_name=customer_name,
    )


def _make_tiny_png() -> bytes:
    """Ein echtes, von PIL erzeugtes PNG statt handgeschriebener Bytes -- build_service_report_pdf()
    baut die Unterschrift über ein platypus.Image-Flowable ein, das PIL zum Dekodieren braucht."""
    from io import BytesIO
    from PIL import Image as PILImage
    buf = BytesIO()
    PILImage.new("RGB", (4, 4), "white").save(buf, format="PNG")
    return buf.getvalue()


TINY_PNG = _make_tiny_png()


def test_create_report_rejects_unknown_type():
    db = db_session()
    order, _ = make_order_with_item(db)
    try:
        create_report(db, order.id, "unbekannt")
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_create_report_requires_existing_order():
    db = db_session()
    try:
        create_report(db, 999999, "rapport")
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_update_and_delete_work_only_while_draft(tmp_path):
    service_reports.SIGNATURE_ROOT = tmp_path / "sigs"
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport", description="Erstfassung")
    updated = update_report(db, report["id"], report_type="wartung", description="Geändert", performed_at=report["performed_at"])
    assert updated["report_type"] == "wartung"

    sign_report_for_test(db, report["id"])
    try:
        update_report(db, report["id"], report_type="rapport", description="x", performed_at=report["performed_at"])
        assert False, "sollte ValueError auslösen (unveränderlich nach Unterschrift)"
    except ValueError:
        pass
    try:
        delete_report(db, report["id"])
        assert False, "sollte ValueError auslösen (unveränderlich nach Unterschrift)"
    except ValueError:
        pass


def test_sign_report_writes_signature_file_and_freezes_status(tmp_path):
    service_reports.SIGNATURE_ROOT = tmp_path / "sigs"
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "wartung")

    installer_png = TINY_PNG
    signed = sign_report_for_test(db, report["id"], installer_name="Monteur Meier", customer_name="Erika Musterfrau",
                                   installer_bytes=installer_png)
    assert signed["status"] == "unterschrieben"
    assert signed["signature_name"] == "Erika Musterfrau"
    assert signed["signed_at"] is not None
    assert signed["installer_signature_name"] == "Monteur Meier"
    assert signed["installer_signed_at"] is not None

    row = db.get(ServiceReport, report["id"])
    stored = service_reports.signature_path(row.signature_path)
    assert stored.exists()
    assert stored.read_bytes() == TINY_PNG
    installer_stored = service_reports.signature_path(row.installer_signature_path)
    assert installer_stored.exists()
    assert installer_stored.read_bytes() == installer_png


def test_sign_report_rejects_already_signed():
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport")
    sign_report_for_test(db, report["id"])
    try:
        sign_report_for_test(db, report["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_sign_report_rejects_empty_signature_name():
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport")
    try:
        sign_report_for_test(db, report["id"], installer_name="   ", customer_name="   ")
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_sign_report_rejects_empty_installer_name_even_with_valid_customer_name():
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport")
    try:
        sign_report_for_test(db, report["id"], installer_name="   ", customer_name="Max Mustermann")
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_sign_report_rejects_empty_customer_name_even_with_valid_installer_name():
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport")
    try:
        sign_report_for_test(db, report["id"], installer_name="Monteur Test", customer_name="   ")
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_sign_report_creates_invoice_task_for_caseworker():
    db = db_session()
    order, _ = make_order_with_item(db)
    caseworker = Employee(first_name="Sina", last_name="Sachbearbeiterin", employee_group="angestellt", active=True)
    db.add(caseworker); db.commit()
    order.caseworker_employee_id = caseworker.id
    db.commit()

    report = create_report(db, order.id, "rapport")
    sign_report_for_test(db, report["id"])

    tasks = list_tasks(db, employee_id=caseworker.id)
    assert len(tasks) == 1
    assert tasks[0]["source_module"] == "wartungsbericht"
    assert tasks[0]["source_url"] == f"/orders/{order.id}"
    assert "Rechnung erstellen" in tasks[0]["title"]


def test_sign_report_skips_task_when_aufgabenmanagement_disabled():
    db = db_session()
    order, _ = make_order_with_item(db)
    set_module_enabled(db, "aufgabenmanagement", False)
    report = create_report(db, order.id, "rapport")
    sign_report_for_test(db, report["id"])
    assert list_tasks(db) == []


def test_list_reports_filters_by_order_and_orders_newest_first():
    db = db_session()
    order, _ = make_order_with_item(db)
    r1 = create_report(db, order.id, "rapport", description="Erster")
    r2 = create_report(db, order.id, "wartung", description="Zweiter")
    rows = list_reports(db, order.id)
    assert [r["id"] for r in rows] == [r2["id"], r1["id"]]


def test_service_reports_endpoints_return_403_when_module_disabled():
    from app.routers.service_reports import get_service_reports, post_service_report
    from app.schemas import ServiceReportCreate

    db = db_session()
    order, _ = make_order_with_item(db)
    set_module_enabled(db, "wartungen", False)

    def expect_403(fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
            assert False, "sollte HTTPException auslösen"
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 403

    expect_403(get_service_reports, order.id, db=db)
    expect_403(post_service_report, order.id, ServiceReportCreate(report_type="rapport"), request_with_user(_admin_user()), db=db)


def test_pdf_endpoint_rejects_unsigned_report():
    from app.service_report_pdf import build_service_report_pdf

    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport")
    row = db.get(ServiceReport, report["id"])
    try:
        build_service_report_pdf(db, row)
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_signed_report_pdf_can_be_built(tmp_path):
    service_reports.SIGNATURE_ROOT = tmp_path / "sigs"
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "wartung", description="Dach kontrolliert, keine Mängel.")
    sign_report_for_test(db, report["id"])
    row = db.get(ServiceReport, report["id"])

    from app.service_report_pdf import build_service_report_pdf
    pdf_bytes = build_service_report_pdf(db, row)
    assert pdf_bytes[:4] == b"%PDF"


def test_ui_wires_service_reports_page_and_time_tracking_link():
    root = Path(__file__).parents[1]
    pages_src = (root / "app/routers/pages.py").read_text(encoding="utf-8")
    assert '"/orders/{order_id}/service-reports"' in pages_src
    assert (root / "app/templates/service_reports.html").exists()
    time_tracking_html = (root / "app/templates/time_tracking.html").read_text(encoding="utf-8")
    assert "service-reports" in time_tracking_html
