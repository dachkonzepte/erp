"""Betriebsmittelverwaltung, Stufe 3 (seit 1.4.5) -- eingesetzte Betriebsmittel im
Einsatzbericht dokumentieren, siehe CLAUDE.md "Betriebsmittelverwaltung" -> Stufe 3.

Reine Dokumentation: kein Preis, keine Menge, keine Betriebsstunden. ServiceReportAsset trägt
asset_id (Pflicht, Verweis für eine spätere Kostenauswertung) UND asset_name_snapshot
(physisch eingefroren bei der Erfassung, dasselbe Muster wie die Bauteil-/Dachflächennamen seit
1.3.12) -- ein unterschriebener Bericht zeigt immer, was damals eingesetzt wurde, unabhängig
von einer späteren Umbenennung/Löschung des Betriebsmittels.

Deckt ab:
1. Namens-Snapshot bei der Erfassung, bleibt bei Umbenennung/Live-Auflösung unverändert.
2. Freigabe-Flag (selectable_in_reports, Standard AUS) -- gilt für JEDEN Aufrufer gleich, auch
   Büro/Admin, keine Rollenausnahme.
3. delete_asset() blockiert, solange ein Bericht (Entwurf ODER unterschrieben) referenziert --
   archivieren (active=False) bleibt frei.
4. Einfrieren nach der Unterschrift wie Material/Fotos/Prüfpunkte.
5. Kundenbericht: schlichte, komma-getrennte Namensliste, KeepTogether, nur wenn erfasst, ohne
   interne Notizen -- erscheint auch im reduzierten Feld-PDF (keine Personendaten betroffen).
6. Der verlangte Angriffstest: die Auswahlliste liefert kein Kosten-/Fristen-/Artikelnummernfeld
   (rekursiver Schlüssel-Scan), und ein Monteur kann über eine geratene asset_id kein nicht
   freigegebenes Betriebsmittel in den Bericht zwingen."""

from app.operational_assets import create_asset, delete_asset, list_selectable_assets, update_asset
from app.service_report_pdf import build_service_report_pdf, build_service_report_pdf_for_field
from app.service_reports import (
    _load as _load_report,
    add_asset_usage,
    delete_asset_usage,
    list_assets_for_report,
    sign_report,
    update_asset_usage,
)
from app.service_reports import create_report
from tests.test_v153_mahnwesen import db_session
from tests.test_v213_inspection_items import TINY_PNG, _extract_pdf_text, _make_order_for_report


def _sign(db, report_id, **overrides):
    payload = dict(
        installer_signature_png_bytes=TINY_PNG, installer_signature_name="Monteur Test",
        customer_signature_png_bytes=TINY_PNG, customer_signature_name="Max Mustermann",
    )
    payload.update(overrides)
    return sign_report(db, report_id, **payload)


def _make_selectable_asset(db, name="Kran"):
    return create_asset(db, {"name": name, "selectable_in_reports": True})


# --- Namens-Snapshot ---

def test_add_asset_usage_freezes_name_snapshot_at_creation():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = _make_selectable_asset(db, name="Kran 40t")

    row = add_asset_usage(db, report["id"], asset_id=asset["id"])
    assert row["asset_name_snapshot"] == "Kran 40t"
    assert row["asset_id"] == asset["id"]
    assert row["notes"] is None


def test_name_snapshot_survives_a_later_rename_of_the_asset():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = _make_selectable_asset(db, name="Kran 40t")
    row = add_asset_usage(db, report["id"], asset_id=asset["id"])

    update_asset(db, asset["id"], {"name": "Kran 40t (umbenannt)", "selectable_in_reports": True})

    reloaded = list_assets_for_report(db, report["id"])[0]
    assert reloaded["asset_name_snapshot"] == "Kran 40t"  # unverändert, nicht der neue Name


def test_name_snapshot_survives_deletion_of_the_referenced_asset_via_archiving():
    """delete_asset() (echtes Löschen) blockiert bei Verweis -- der Weg, ein referenziertes
    Betriebsmittel trotzdem "loszuwerden", ist Archivieren (active=False), was den Namen NICHT
    anfasst. Belegt gleichzeitig, dass der Snapshot auch danach unverändert lesbar bleibt."""
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = _make_selectable_asset(db, name="Kran 40t")
    add_asset_usage(db, report["id"], asset_id=asset["id"])

    update_asset(db, asset["id"], {"name": "Kran 40t", "selectable_in_reports": True, "active": False})
    reloaded = list_assets_for_report(db, report["id"])[0]
    assert reloaded["asset_name_snapshot"] == "Kran 40t"


# --- Freigabe-Flag ---

def test_add_asset_usage_rejects_a_non_selectable_asset():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = create_asset(db, {"name": "Akkuschrauber"})  # selectable_in_reports Standard False

    try:
        add_asset_usage(db, report["id"], asset_id=asset["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "auswählbar" in str(exc)


def test_selectable_in_reports_defaults_to_false_and_gate_applies_to_every_caller_not_just_field():
    """Keine Rollenausnahme -- Büro/Admin unterliegen derselben Regel wie ein Monteur, siehe
    add_asset_usage()-Docstring."""
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = create_asset(db, {"name": "Akkuschrauber"})
    assert asset["selectable_in_reports"] is False
    try:
        add_asset_usage(db, report["id"], asset_id=asset["id"], created_by_employee_id=None)
        assert False, "sollte ValueError auslösen, unabhängig vom Aufrufer"
    except ValueError:
        pass


def test_add_asset_usage_rejects_unknown_asset_id():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    try:
        add_asset_usage(db, report["id"], asset_id=999999)
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "nicht gefunden" in str(exc)


# --- list_selectable_assets() ---

def test_list_selectable_assets_filters_to_selectable_and_active_only():
    db = db_session()
    selectable_active = _make_selectable_asset(db, name="Kran")
    create_asset(db, {"name": "Trennschleifer"})  # nicht freigegeben
    selectable_inactive = create_asset(db, {"name": "Alter Kran", "selectable_in_reports": True, "active": False})

    rows = list_selectable_assets(db)
    ids = {r["id"] for r in rows}
    assert ids == {selectable_active["id"]}
    assert selectable_inactive["id"] not in ids


def test_list_selectable_assets_uses_live_resolved_name_for_resource_linked_assets_and_sorts_by_it():
    from app.models import OperationalResource

    db = db_session()
    resource = OperationalResource(name="Anhänger XL", resource_type="Anhänger")
    db.add(resource)
    db.commit()
    linked = create_asset(db, {"resource_id": resource.id, "selectable_in_reports": True})
    _make_selectable_asset(db, name="Bagger")

    rows = list_selectable_assets(db)
    names = [r["name"] for r in rows]
    assert names == sorted(names, key=str.lower)
    linked_row = next(r for r in rows if r["id"] == linked["id"])
    assert linked_row["name"] == "Anhänger XL"  # live aufgelöst, nicht NULL


def test_list_selectable_assets_response_never_carries_a_locked_field():
    """Der verlangte rekursive Schlüssel-Scan -- dieselbe Fehlerklasse wie an anderer Stelle im
    Projekt (purchase_price/cost_notes/acquisition_cost/article_number/next_due_date)."""
    db = db_session()
    asset = create_asset(db, {
        "name": "Kran", "selectable_in_reports": True, "article_number": "ART-1",
        "product_url": "https://example.com/kran", "acquisition_cost": "50000.00",
        "recurring_cost_per_month": "120.00", "cost_notes": "geleast",
    })
    rows = list_selectable_assets(db)
    row = next(r for r in rows if r["id"] == asset["id"])
    assert set(row.keys()) == {"id", "name", "asset_type", "manufacturer", "model", "usage_notes"}


# --- delete_asset(): Blockade bei Verweis ---

def test_delete_asset_is_blocked_while_referenced_by_a_draft_report():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = _make_selectable_asset(db, name="Kran")
    add_asset_usage(db, report["id"], asset_id=asset["id"])

    try:
        delete_asset(db, asset["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError as exc:
        assert "Einsatzbericht" in str(exc)


def test_delete_asset_is_blocked_while_referenced_by_a_signed_report():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = _make_selectable_asset(db, name="Kran")
    add_asset_usage(db, report["id"], asset_id=asset["id"])
    _sign(db, report["id"])

    try:
        delete_asset(db, asset["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_delete_asset_works_when_unreferenced():
    db = db_session()
    asset = _make_selectable_asset(db, name="Kran")
    assert delete_asset(db, asset["id"]) is True


def test_archiving_a_referenced_asset_remains_possible():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = _make_selectable_asset(db, name="Kran")
    add_asset_usage(db, report["id"], asset_id=asset["id"])

    updated = update_asset(db, asset["id"], {"name": "Kran", "selectable_in_reports": True, "active": False})
    assert updated["active"] is False


# --- Einfrieren nach Unterschrift ---

def test_add_asset_usage_rejects_when_report_already_signed():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = _make_selectable_asset(db, name="Kran")
    _sign(db, report["id"])

    try:
        add_asset_usage(db, report["id"], asset_id=asset["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_update_and_delete_asset_usage_rejected_after_signing():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = _make_selectable_asset(db, name="Kran")
    row = add_asset_usage(db, report["id"], asset_id=asset["id"])
    _sign(db, report["id"])

    try:
        update_asset_usage(db, row["id"], {"notes": "neu"})
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass
    try:
        delete_asset_usage(db, row["id"])
        assert False, "sollte ValueError auslösen"
    except ValueError:
        pass


def test_update_asset_usage_changes_only_notes():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = _make_selectable_asset(db, name="Kran")
    row = add_asset_usage(db, report["id"], asset_id=asset["id"])

    updated = update_asset_usage(db, row["id"], {"notes": "mit Fahrer"})
    assert updated["notes"] == "mit Fahrer"
    assert updated["asset_name_snapshot"] == "Kran"


def test_delete_asset_usage_removes_the_row():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = _make_selectable_asset(db, name="Kran")
    row = add_asset_usage(db, report["id"], asset_id=asset["id"])

    assert delete_asset_usage(db, row["id"]) is True
    assert list_assets_for_report(db, report["id"]) == []


# --- PDF ---

def test_pdf_omits_assets_section_when_none_recorded():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport", description="Ohne Betriebsmittel")
    _sign(db, report["id"])

    row = _load_report(db, report["id"])
    text = _extract_pdf_text(build_service_report_pdf(db, row))
    assert b"Eingesetzte Betriebsmittel" not in text


def test_pdf_shows_frozen_asset_names_as_a_comma_separated_list_without_notes():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    kran = _make_selectable_asset(db, name="Kran")
    hubsteiger = _make_selectable_asset(db, name="Hubsteiger")
    add_asset_usage(db, report["id"], asset_id=kran["id"], notes="interne Notiz DARF NICHT im PDF stehen")
    add_asset_usage(db, report["id"], asset_id=hubsteiger["id"])
    _sign(db, report["id"])

    row = _load_report(db, report["id"])
    text = _extract_pdf_text(build_service_report_pdf(db, row))
    assert b"Eingesetzte Betriebsmittel" in text
    assert b"Kran" in text
    assert b"Hubsteiger" in text
    assert b"interne Notiz" not in text
    assert b"DARF NICHT" not in text


def test_pdf_asset_name_stays_frozen_even_if_asset_renamed_after_signing():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = _make_selectable_asset(db, name="Kran Original")
    add_asset_usage(db, report["id"], asset_id=asset["id"])
    _sign(db, report["id"])

    update_asset(db, asset["id"], {"name": "Kran Umbenannt", "selectable_in_reports": True})

    row = _load_report(db, report["id"])
    text = _extract_pdf_text(build_service_report_pdf(db, row))
    assert b"Kran Original" in text
    assert b"Umbenannt" not in text


def test_field_pdf_also_includes_the_assets_section_no_personal_data_concern():
    db = db_session()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = _make_selectable_asset(db, name="Kran")
    add_asset_usage(db, report["id"], asset_id=asset["id"])
    _sign(db, report["id"])

    row = _load_report(db, report["id"])
    text = _extract_pdf_text(build_service_report_pdf_for_field(db, row))
    assert b"Eingesetzte Betriebsmittel" in text
    assert b"Kran" in text


# --- Router ---

def test_router_endpoints_for_service_report_assets(threaded_db_session, router_test_client):
    from app.routers.service_reports import router as service_reports_router

    db = threaded_db_session
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = _make_selectable_asset(db, name="Kran")
    client = router_test_client(db, service_reports_router)

    post_resp = client.post(f"/api/service-reports/{report['id']}/assets", json={"asset_id": asset["id"], "notes": "mit Fahrer"})
    assert post_resp.status_code == 200, post_resp.text
    row_id = post_resp.json()["id"]
    assert post_resp.json()["asset_name_snapshot"] == "Kran"

    get_resp = client.get(f"/api/service-reports/{report['id']}/assets")
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 1

    put_resp = client.put(f"/api/service-report-assets/{row_id}", json={"notes": "ohne Fahrer"})
    assert put_resp.status_code == 200
    assert put_resp.json()["notes"] == "ohne Fahrer"

    delete_resp = client.delete(f"/api/service-report-assets/{row_id}")
    assert delete_resp.status_code == 200
    assert client.get(f"/api/service-reports/{report['id']}/assets").json() == []


def test_selectable_for_report_endpoint_recursive_key_scan_for_every_role(threaded_db_session, router_test_client):
    """Angriffstest, Router-Ebene: die Auswahlliste liefert für JEDE Rolle -- auch Büro/Admin --
    ausschließlich die fünf feldsicheren Felder, nie Kosten/Fristen/Artikelnummer."""
    from app.routers.operational_assets import router as operational_assets_router

    db = threaded_db_session
    _make_selectable_asset(db, name="Kran")
    create_asset(db, {"name": "Trennschleifer"})  # nicht freigegeben -- darf nie auftauchen

    for role, employee_id in (("field", None), ("office", None), ("admin", None)):
        client = router_test_client(db, operational_assets_router, role=role, employee_id=employee_id)
        resp = client.get("/api/operational-assets/selectable-for-report")
        assert resp.status_code == 200, (role, resp.text)
        body = resp.json()
        assert len(body) == 1  # nur das freigegebene
        for row in body:
            assert set(row.keys()) == {"id", "name", "asset_type", "manufacturer", "model", "usage_notes"}, (role, row)


def test_field_cannot_force_a_non_selectable_asset_into_a_report_via_a_guessed_asset_id(router_test_client, threaded_db_session):
    """Der zweite verlangte Angriffstest: eine Aufgabe-fremde/nicht freigegebene asset_id über
    den POST-Endpunkt liefert 400, egal ob die ID existiert oder geraten/erfunden ist -- die
    Aufgabe wird in keinem Fall dem Bericht hinzugefügt."""
    from app.routers.service_reports import router as service_reports_router
    from app.models import Employee

    db = threaded_db_session
    employee = Employee(first_name="Monteur", last_name="Eins")
    db.add(employee); db.commit()
    order = _make_order_for_report(db)
    # created_by_employee_id gesetzt, damit field_may_access_order() über den "eigener Bericht"-Weg
    # greift (siehe app/orders.py) -- der Test soll die asset-spezifische Ablehnung (400) prüfen,
    # nicht eine vorgelagerte Auftrags-/Berichts-Zugriffsablehnung (403), die bereits an anderer
    # Stelle (test_v260_role_audit.py, "Berichts-Eigentümerschaft") belegt ist.
    report = create_report(db, order.id, "rapport", created_by_employee_id=employee.id)
    not_selectable = create_asset(db, {"name": "Trennschleifer"})

    client = router_test_client(db, service_reports_router, role="field", employee_id=employee.id)
    resp = client.post(f"/api/service-reports/{report['id']}/assets", json={"asset_id": not_selectable["id"]})
    assert resp.status_code == 400, resp.text
    assert list_assets_for_report(db, report["id"]) == []

    resp_guessed = client.post(f"/api/service-reports/{report['id']}/assets", json={"asset_id": 999999})
    assert resp_guessed.status_code == 400, resp_guessed.text
    assert list_assets_for_report(db, report["id"]) == []


def test_field_cannot_add_an_asset_to_a_colleagues_report(router_test_client, threaded_db_session):
    from app.routers.service_reports import router as service_reports_router
    from app.models import Employee

    db = threaded_db_session
    owner = Employee(first_name="Erika", last_name="Eins")
    other = Employee(first_name="Otto", last_name="Zwei")
    db.add_all([owner, other]); db.commit()
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport", created_by_employee_id=owner.id)
    asset = _make_selectable_asset(db, name="Kran")

    client = router_test_client(db, service_reports_router, role="field", employee_id=other.id)
    resp = client.post(f"/api/service-reports/{report['id']}/assets", json={"asset_id": asset["id"]})
    assert resp.status_code == 403, resp.text
    assert list_assets_for_report(db, report["id"]) == []


def test_betriebsmittel_module_disabled_blocks_asset_endpoints_even_with_wartungen_enabled(router_test_client, threaded_db_session):
    from app.routers.service_reports import router as service_reports_router
    from app.models import EnabledModule

    db = threaded_db_session
    order = _make_order_for_report(db)
    report = create_report(db, order.id, "rapport")
    asset = _make_selectable_asset(db, name="Kran")
    db.add(EnabledModule(module_key="betriebsmittel", enabled=False))
    db.commit()

    client = router_test_client(db, service_reports_router)
    resp = client.post(f"/api/service-reports/{report['id']}/assets", json={"asset_id": asset["id"]})
    assert resp.status_code == 403, resp.text
