"""Version 1.3.0 -- Monteursansicht (/mobil, bis 1.3.60 /vor-ort): heutige Einsätze aus der Plantafel (beide
Zuordnungswege), offene Entwurfsberichte, die einheitliche created_by_employee_id-Sperre an
allen vier Einsatzbericht-Endpunkten (ServiceReport/ServiceReportPhoto/ServiceReportMaterial/
Finding), zwei Pflicht-Unterschriften, die Feierabend-Abmeldung und das Web-App-Manifest."""

import asyncio
import io
import json
from datetime import date, datetime, time as dt_time
from decimal import Decimal

from starlette.datastructures import Headers, UploadFile
from starlette.requests import Request

from app.auth import COOKIE_NAME, hash_password
from app.mobile_manifest import build_icon_png, build_manifest
from app.mobile_settings import get_or_create_mobile_settings, is_past_shift_end, update_mobile_settings
from app.models import (
    AppUser, Employee, PlanningSlot, Property, Team, WorkPreparation, WorkPreparationEmployee,
    WorkPreparationTeamAssignment, WorkPreparationTeamEmployee,
)
from app.planning import list_todays_assignments_for_employee
from app.routers.field_view import get_field_view_today, get_manifest, get_mobile_icon
from app.routers.findings import post_finding
from app.routers.service_reports import post_service_report, post_service_report_material, post_service_report_photo
from app.schemas import FindingCreate, ServiceReportCreate, ServiceReportMaterialCreate
from app.service_report_pdf import build_service_report_pdf
from app.service_reports import _load as load_report
from app.service_reports import create_report, list_draft_reports_for_employee
from tests.test_v133_invoices import make_order_with_item
from tests.test_v153_mahnwesen import db_session
from tests.test_v203_service_reports import TINY_PNG, sign_report_for_test
from tests.test_v213_inspection_items import _extract_pdf_text


def request_with_user(user, path="/api/field-view/today"):
    req = Request({"type": "http", "method": "GET", "path": path, "headers": [],
                   "query_string": b"", "server": ("test", 80), "client": ("test", 1234), "scheme": "http"})
    req.state.erp_user = user
    return req


def make_employee(db, number, first, last):
    e = Employee(employee_number=number, first_name=first, last_name=last, employee_group="gewerblich",
                 hourly_wage=Decimal("20"), weekly_hours=Decimal("40"), active=True)
    db.add(e); db.commit()
    return e


def make_non_admin(db, employee_id, username="sb1"):
    user = AppUser(username=username, display_name="Sachbearbeiter", role="user", employee_id=employee_id,
                    active=True, password_hash=hash_password("Passwort123"))
    db.add(user); db.commit()
    return user


def make_admin(db, username="admin1"):
    user = AppUser(username=username, display_name="Admin", role="admin", employee_id=None,
                    active=True, password_hash=hash_password("Passwort123"))
    db.add(user); db.commit()
    return user


def make_team(db, number, name):
    t = Team(team_number=number, name=name)
    db.add(t); db.commit()
    return t


def make_slot_for_team(db, order, team, employee, start_date, end_date):
    prep = WorkPreparation(order_id=order.id, status="offen")
    db.add(prep); db.flush()
    assignment = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
    db.add(assignment); db.flush()
    db.add(WorkPreparationTeamEmployee(assignment_id=assignment.id, employee_id=employee.id,
                                        employee_name_snapshot=f"{employee.first_name} {employee.last_name}"))
    slot = PlanningSlot(preparation_id=prep.id, team_assignment_id=assignment.id, start_date=start_date, end_date=end_date)
    db.add(slot); db.commit()
    return slot, prep


def make_slot_for_individual(db, order, team, employee, start_date, end_date):
    """Individueller Zuordnungsweg (WorkPreparationEmployee an der WorkPreparation selbst, nicht
    am Slot) -- ein PlanningSlot braucht trotzdem eine team_assignment_id (NOT-NULL-Spalte),
    unabhängig davon, über welchen Weg der Mitarbeiter zugeordnet ist."""
    prep = WorkPreparation(order_id=order.id, status="offen")
    db.add(prep); db.flush()
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=employee.id))
    assignment = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
    db.add(assignment); db.flush()
    slot = PlanningSlot(preparation_id=prep.id, team_assignment_id=assignment.id, start_date=start_date, end_date=end_date)
    db.add(slot); db.commit()
    return slot, prep


# --- list_todays_assignments_for_employee(): beide Zuordnungswege -----------------------------

def test_team_path_returns_todays_assignment():
    db = db_session()
    order, _ = make_order_with_item(db)
    emp = make_employee(db, "M-1", "Erika", "Eins")
    team = make_team(db, "K-1", "Kolonne 1")
    make_slot_for_team(db, order, team, emp, date.today(), date.today())
    rows = list_todays_assignments_for_employee(db, emp.id)
    assert len(rows) == 1
    assert rows[0]["order_id"] == order.id


def test_individual_path_returns_todays_assignment():
    db = db_session()
    order, _ = make_order_with_item(db)
    emp = make_employee(db, "M-1", "Erika", "Eins")
    team = make_team(db, "K-1", "Kolonne 1")
    make_slot_for_individual(db, order, team, emp, date.today(), date.today())
    rows = list_todays_assignments_for_employee(db, emp.id)
    assert len(rows) == 1
    assert rows[0]["order_id"] == order.id


def test_employee_on_both_paths_for_same_slot_is_not_duplicated():
    db = db_session()
    order, _ = make_order_with_item(db)
    emp = make_employee(db, "M-1", "Erika", "Eins")
    team = make_team(db, "K-1", "Kolonne 1")
    slot, prep = make_slot_for_team(db, order, team, emp, date.today(), date.today())
    # Derselbe Mitarbeiter zusätzlich über den Einzelweg an derselben AV zugeordnet.
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=emp.id))
    db.commit()
    rows = list_todays_assignments_for_employee(db, emp.id)
    assert len(rows) == 1
    assert rows[0]["slot_id"] == slot.id


def test_day_filter_excludes_slots_outside_the_range():
    db = db_session()
    order, _ = make_order_with_item(db)
    emp = make_employee(db, "M-1", "Erika", "Eins")
    team = make_team(db, "K-1", "Kolonne 1")
    make_slot_for_team(db, order, team, emp, date(2026, 1, 5), date(2026, 1, 7))
    assert list_todays_assignments_for_employee(db, emp.id, day=date(2026, 1, 1)) == []
    rows = list_todays_assignments_for_employee(db, emp.id, day=date(2026, 1, 6))
    assert len(rows) == 1


def test_address_falls_back_to_order_snapshot_without_linked_property():
    db = db_session()
    order, _ = make_order_with_item(db)
    order.property_name = "Baustelle Nord"
    order.property_address = "Feldweg 3\n99999 Nirgendwo"
    db.commit()
    emp = make_employee(db, "M-1", "Erika", "Eins")
    team = make_team(db, "K-1", "Kolonne 1")
    make_slot_for_team(db, order, team, emp, date.today(), date.today())
    rows = list_todays_assignments_for_employee(db, emp.id)
    assert rows[0]["property_name"] == "Baustelle Nord"
    assert rows[0]["property_address"] == "Feldweg 3, 99999 Nirgendwo"


def test_address_uses_linked_property_when_present():
    db = db_session()
    order, _ = make_order_with_item(db)
    prop = Property(customer_id=order.project.customer_id, name="Hauptobjekt",
                     street="Dachweg 1", postal_code="52531", city="Übach-Palenberg")
    db.add(prop); db.flush()
    order.project.property_id = prop.id
    db.commit()
    emp = make_employee(db, "M-1", "Erika", "Eins")
    team = make_team(db, "K-1", "Kolonne 1")
    make_slot_for_team(db, order, team, emp, date.today(), date.today())
    rows = list_todays_assignments_for_employee(db, emp.id)
    assert rows[0]["property_name"] == "Hauptobjekt"
    assert rows[0]["property_address"] == "Dachweg 1, 52531 Übach-Palenberg"


# --- list_draft_reports_for_employee() ---------------------------------------------------------

def test_list_draft_reports_only_shows_own_open_drafts():
    db = db_session()
    order, _ = make_order_with_item(db)
    emp1 = make_employee(db, "M-1", "Erika", "Eins")
    emp2 = make_employee(db, "M-2", "Otto", "Zwei")
    own_draft = create_report(db, order.id, "rapport", created_by_employee_id=emp1.id)
    create_report(db, order.id, "rapport", created_by_employee_id=emp2.id)
    signed = create_report(db, order.id, "rapport", created_by_employee_id=emp1.id)
    sign_report_for_test(db, signed["id"])
    rows = list_draft_reports_for_employee(db, emp1.id)
    assert [r["id"] for r in rows] == [own_draft["id"]]


# --- GET /api/field-view/today --------------------------------------------------------------

def test_field_view_today_returns_assignments_and_drafts_for_linked_employee(monkeypatch):
    # Festes now VOR dem Standard-Feierabend (19 Uhr) -- ohne das wäre dieser Test von der
    # tatsächlichen Wanduhrzeit abhängig und schlüge nach 19 Uhr JEDEN Tag fehl, unabhängig
    # von jeder Codeänderung (siehe CLAUDE.md "Bekannte, bewusst offene Punkte", jetzt behoben).
    # Muster wie test_is_past_shift_end_before_and_after_configured_time() unten, das
    # is_past_shift_end() bereits direkt mit einem festen now aufruft -- get_field_view_today()
    # selbst nimmt bewusst KEINEN now-Parameter über die HTTP-Schnittstelle an (Sicherheitsrisiko,
    # siehe app/routers/field_view.py::_now()), deshalb hier über die private Bruchstelle gesetzt.
    monkeypatch.setattr("app.routers.field_view._now", lambda: datetime(2026, 9, 10, 8, 0))
    db = db_session()
    order, _ = make_order_with_item(db)
    emp = make_employee(db, "M-1", "Erika", "Eins")
    team = make_team(db, "K-1", "Kolonne 1")
    make_slot_for_team(db, order, team, emp, date.today(), date.today())
    report = create_report(db, order.id, "rapport", created_by_employee_id=emp.id)
    user = make_non_admin(db, emp.id, "mont1")
    result = get_field_view_today(request_with_user(user), db=db)
    assert len(result["assignments"]) == 1
    assert result["assignments"][0]["order_id"] == order.id
    assert any(r["id"] == report["id"] for r in result["draft_reports"])


def test_field_view_today_rejects_unlinked_employee(monkeypatch):
    # Dasselbe feste now wie oben -- dieser Test prüft die 422-Ablehnung ohne Mitarbeiterverknüpfung,
    # nicht die Feierabend-Grenze, und darf deshalb ebenso nicht von der Wanduhrzeit abhängen.
    monkeypatch.setattr("app.routers.field_view._now", lambda: datetime(2026, 9, 10, 8, 0))
    db = db_session()
    user = make_non_admin(db, None, "mont2")
    try:
        get_field_view_today(request_with_user(user), db=db)
        assert False, "sollte HTTPException auslösen"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422


def test_field_view_today_logs_out_past_shift_end():
    db = db_session()
    emp = make_employee(db, "M-1", "Erika", "Eins")
    user = make_non_admin(db, emp.id, "mont3")
    update_mobile_settings(db, dt_time(0, 0))  # jede Uhrzeit gilt danach als "Feierabend"
    response = get_field_view_today(request_with_user(user), db=db)
    assert response.status_code == 401
    assert COOKIE_NAME in response.headers.get("set-cookie", "")


# --- MobileSettings / is_past_shift_end() ----------------------------------------------------

def test_is_past_shift_end_before_and_after_configured_time():
    db = db_session()
    settings = get_or_create_mobile_settings(db)
    assert settings.shift_end_time == dt_time(19, 0)
    assert is_past_shift_end(settings, now=datetime(2026, 9, 10, 18, 59)) is False
    assert is_past_shift_end(settings, now=datetime(2026, 9, 10, 19, 0)) is True
    assert is_past_shift_end(settings, now=datetime(2026, 9, 10, 20, 30)) is True


def test_update_mobile_settings_round_trip():
    db = db_session()
    result = update_mobile_settings(db, dt_time(17, 30))
    assert result["shift_end_time"] == "17:30"
    assert get_or_create_mobile_settings(db).shift_end_time == dt_time(17, 30)


# --- Web-App-Manifest / Icons -----------------------------------------------------------------

def test_manifest_json_has_expected_shape():
    db = db_session()
    response = get_manifest(db=db)
    assert response.status_code == 200
    assert response.media_type == "application/manifest+json"
    body = json.loads(response.body)
    assert body["start_url"] == "/mobil"  # seit 1.3.61 (bis 1.3.60 /vor-ort)
    assert body["display"] == "standalone"
    assert len(body["icons"]) == 2


def test_mobile_icon_without_logo_is_plain_placeholder_png():
    db = db_session()
    response = get_mobile_icon(192, db=db)
    assert response.status_code == 200
    assert response.media_type == "image/png"
    assert response.body[:8] == b"\x89PNG\r\n\x1a\n"
    from PIL import Image as PILImage
    img = PILImage.open(io.BytesIO(response.body))
    assert img.size == (192, 192)


def test_mobile_icon_rejects_out_of_range_size():
    db = db_session()
    try:
        get_mobile_icon(4000, db=db)
        assert False, "sollte HTTPException auslösen"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404


def test_build_icon_png_embeds_logo_when_present(tmp_path):
    from app import company_logo
    company_logo.LOGO_ROOT = tmp_path / "logo"
    from PIL import Image as PILImage
    db = db_session()
    from app.settings import get_or_create_general_settings
    general = get_or_create_general_settings(db)
    buf = io.BytesIO()
    PILImage.new("RGB", (40, 40), "red").save(buf, format="PNG")
    stored = company_logo.replace_logo(None, "logo.png", buf.getvalue())
    general.logo_filename = stored
    db.commit()
    data = build_icon_png(db, 192)
    img = PILImage.open(io.BytesIO(data))
    assert img.size == (192, 192)


# --- created_by_employee_id-Sperre an allen vier Endpunkten (seit 1.3.0) ----------------------

def test_non_admin_cannot_set_foreign_employee_id_on_create_report():
    db = db_session()
    order, _ = make_order_with_item(db)
    emp1 = make_employee(db, "M-1", "Erika", "Eins")
    emp2 = make_employee(db, "M-2", "Otto", "Zwei")
    user = make_non_admin(db, emp1.id, "sb1")
    # Direktaufruf ohne FastAPI-DI: seit Rechtekonzept Teil B tragen diese Endpunkte einen
    # _role-Parameter (Depends(require_role(...))), der hier ausdrücklich mitgegeben werden muss.
    try:
        post_service_report(order.id, ServiceReportCreate(report_type="rapport", created_by_employee_id=emp2.id),
                             request_with_user(user), db=db, _role=user)
        assert False, "sollte HTTPException auslösen"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    result = post_service_report(order.id, ServiceReportCreate(report_type="rapport", created_by_employee_id=None),
                                  request_with_user(user), db=db, _role=user)
    assert result["created_by_employee_id"] == emp1.id


def test_admin_can_set_any_employee_id_on_create_report():
    db = db_session()
    order, _ = make_order_with_item(db)
    emp2 = make_employee(db, "M-2", "Otto", "Zwei")
    admin = make_admin(db)
    result = post_service_report(order.id, ServiceReportCreate(report_type="rapport", created_by_employee_id=emp2.id),
                                  request_with_user(admin), db=db, _role=admin)
    assert result["created_by_employee_id"] == emp2.id


def test_non_admin_cannot_set_foreign_employee_id_on_add_photo():
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport")
    emp1 = make_employee(db, "M-1", "Erika", "Eins")
    emp2 = make_employee(db, "M-2", "Otto", "Zwei")
    user = make_non_admin(db, emp1.id, "sb2")
    upload = UploadFile(filename="foto.png", file=io.BytesIO(TINY_PNG), headers=Headers({"content-type": "image/png"}))
    try:
        asyncio.run(post_service_report_photo(
            report["id"], request_with_user(user), file=upload, inspection_item_id=None, finding_id=None,
            kind="allgemein", caption=None, created_by_employee_id=emp2.id, db=db, _role=user,
        ))
        assert False, "sollte HTTPException auslösen"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403


def test_non_admin_cannot_set_foreign_employee_id_on_add_material():
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport")
    emp1 = make_employee(db, "M-1", "Erika", "Eins")
    emp2 = make_employee(db, "M-2", "Otto", "Zwei")
    user = make_non_admin(db, emp1.id, "sb3")
    try:
        post_service_report_material(
            report["id"],
            ServiceReportMaterialCreate(description="Dachziegel", quantity=Decimal("1"), created_by_employee_id=emp2.id),
            request_with_user(user), db=db, _role=user,
        )
        assert False, "sollte HTTPException auslösen"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403


def test_non_admin_cannot_set_foreign_employee_id_on_create_finding():
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport")
    emp1 = make_employee(db, "M-1", "Erika", "Eins")
    emp2 = make_employee(db, "M-2", "Otto", "Zwei")
    user = make_non_admin(db, emp1.id, "sb4")
    try:
        post_finding(
            report["id"],
            FindingCreate(description="Mangel", severity="mittel", action="sofort_behoben", created_by_employee_id=emp2.id),
            request_with_user(user), db=db, _role=user,
        )
        assert False, "sollte HTTPException auslösen"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403


# --- Zwei-Unterschriften-PDF ------------------------------------------------------------------

def test_pdf_shows_two_signatures_when_installer_signature_present(tmp_path):
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport", description="Kontrolliert.")
    sign_report_for_test(db, report["id"], installer_name="Monteur Meier", customer_name="Erika Musterfrau")
    row = load_report(db, report["id"])
    pdf_bytes = build_service_report_pdf(db, row)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Unterschriften" in text
    assert b"Monteur Meier" in text
    assert b"Erika Musterfrau" in text


def test_pdf_regresses_to_single_signature_block_without_installer_signature(tmp_path):
    """Altbestand-Simulation (installer_signature_* bleibt leer, wie bei einem vor 1.3.0
    unterschriebenen Bericht) -- rendert weiterhin den alten Ein-Block-Pfad, unverändert."""
    from app import service_reports as service_reports_module
    service_reports_module.SIGNATURE_ROOT = tmp_path / "sigs"
    db = db_session()
    order, _ = make_order_with_item(db)
    report = create_report(db, order.id, "rapport", description="Kontrolliert.")
    sign_report_for_test(db, report["id"], customer_name="Nur Kunde")
    row = load_report(db, report["id"])
    row.installer_signature_path = None
    row.installer_signature_name = None
    row.installer_signed_at = None
    db.commit()
    row = load_report(db, report["id"])
    pdf_bytes = build_service_report_pdf(db, row)
    text = _extract_pdf_text(pdf_bytes)
    assert b"Unterschriften" not in text
    assert b"Unterschrift" in text
    assert b"Nur Kunde" in text
