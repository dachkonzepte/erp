"""Version 1.3.?? -- Wartungsbericht-Detailansicht für Monteure, ausschließlich über das Objekt
(siehe CLAUDE.md "Dateiablage je Objekt" -> "Wartungsbericht-Detailansicht"). Anlass: ein Monteur
führt dieselbe Wartung erneut durch und will nachvollziehen, was beim letzten Einsatz gemacht
wurde -- auch von einem inzwischen ausgeschiedenen Kollegen.

Vier Punkte, jeder einzeln geprüft:
1. Kein "internal_note" oder sinnverwandtes Feld im reduzierten Schema (ServiceReportHistoryOut)
   -- rekursiver Schlüssel-Scan, KEIN FUND (das Feld existiert an keiner Stelle im Modell/Schema,
   siehe test_no_internal_or_price_like_field_anywhere_in_the_reduced_history_schema unten;
   nichts wurde deshalb aus dem Schema entfernt -- der bereits bestehende Exact-Key-Set-Test in
   tests/test_v260_role_audit.py bestätigt das unverändert mit).
2. Das PDF ohne fremde Zeitbuchungen entsteht über build_service_report_pdf() mit
   include_time_entries=False (build_service_report_pdf_for_field(), siehe
   app/service_report_pdf.py) -- derselbe Renderer, nur ein Schalter. Kein Preis wird dabei
   entfernt, da ServiceReportMaterial/TimeEntry ohnehin nirgends eine Preisspalte tragen.
3. Zugang nur über das Objekt -- eine geratene report_id ohne Objektweg oder ein Bericht, der zu
   einem ANDEREN Objekt gehört, wird abgewiesen (404, ununterscheidbar von "existiert nicht").
4. Nur Lesen -- kein PUT/DELETE/sign über diesen Weg; die bestehenden Berichts-Endpunkte bleiben
   unverändert über require_field_report_ownership() gesperrt, unberührt von dieser Änderung."""

from datetime import date
from decimal import Decimal

from app.models import Customer, Employee, Order, OrderItem, Project, Property
from tests.test_v213_inspection_items import _extract_pdf_text


def _employee(db, number, first, last, active=True):
    emp = Employee(employee_number=number, first_name=first, last_name=last,
                    employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=active)
    db.add(emp); db.commit()
    return emp


def _order(db, order_number, project_number, property_id=None, customer=None):
    """Muster tests/test_v260_role_audit.py::TestObjectFilteringForFieldTeilB._order()."""
    if customer is None:
        customer = Customer(name="Testkunde", last_name="Testkunde")
        db.add(customer); db.flush()
    if property_id is None:
        prop = Property(customer_id=customer.id, name="Objekt Nord", street="Teststr. 1", city="Teststadt")
        db.add(prop); db.flush()
        property_id = prop.id
    project = Project(project_number=project_number, name="Testprojekt", customer_id=customer.id, property_id=property_id)
    db.add(project); db.flush()
    order = Order(order_number=order_number, project_id=project.id,
                  source_quote_id=int(order_number.rsplit("-", 1)[-1]),
                  quote_number_snapshot=f"A-{order_number}", title="Testauftrag", customer_name=customer.name,
                  customer_number="K-0001", property_name="Objekt Nord")
    db.add(order); db.flush()
    db.add(OrderItem(order_id=order.id, sort_order=10, position_number="1", short_text="Dacheindeckung",
                      quantity=Decimal("100"), unit="m²", unit_price=Decimal("50")))
    db.commit()
    return order, customer, property_id


def _signed_report_with_finding_and_foreign_time(db, order, creator):
    """Bericht mit Prüfpunkt, Mangel, Beschreibung UND einer Zeitbuchung eines ANDEREN Kollegen
    (nicht des Erstellers) -- genug unterscheidbaren Inhalt, um im PDF-Text zu belegen, was
    mit/ohne include_time_entries erscheint bzw. verschwindet. Der Ersteller selbst bleibt als
    "Monteur"-Meta-Feld in BEIDEN Varianten sichtbar (Punkt 2 der Anfrage erlaubt "damaliger
    Monteur" ausdrücklich) -- nur der ZWEITE, fremde Zeitbucher darf in der Field-Variante nicht
    auftauchen, deshalb ein eigener, dritter Name. creator muss beim Aufruf noch aktiv sein
    (create_manual_entry() lehnt inaktive Mitarbeiter ab) -- "inzwischen ausgeschieden" heißt:
    aktiv zum Zeitpunkt der Arbeit, seither deaktiviert; diese Funktion deaktiviert ihn deshalb
    erst NACH der Erstellung."""
    from app.findings import create_finding
    from app.models import ServiceReport
    from app.service_reports import add_inspection_item, create_report, update_inspection_item
    from app.time_tracking import create_manual_entry
    report_id = create_report(
        db, order.id, "wartung", description="Frühjahrswartung -- Beschreibungstext",
        created_by_employee_id=creator.id,
    )["id"]
    item = add_inspection_item(db, report_id, "Gully Nordost", "ja_nein", group_name="Entwässerung")
    update_inspection_item(db, item["id"], {"result": "nok", "notes": "Laub, gereinigt"})
    create_finding(db, report_id, "Gully verstopft", "mittel", "sofort_behoben", inspection_item_id=item["id"])
    time_booker = _employee(db, f"T-Z{order.id}", "Klaus", "Kollegenzeit")
    create_manual_entry(db, employee_id=time_booker.id, order_id=order.id, work_date=date(2025, 5, 3), hours=Decimal("3"))
    db.get(ServiceReport, report_id).status = "unterschrieben"
    creator.active = False
    db.commit()
    return report_id


# ---------------------------------------------------------------------------
# Punkt 1: kein "internal_note" o. ä. im reduzierten Schema -- kein Fund
# ---------------------------------------------------------------------------

def test_no_internal_or_price_like_field_anywhere_in_the_reduced_history_schema(router_test_client, threaded_db_session):
    """Rekursiver Schlüssel-Scan wie bei test_maintenance_history_carries_no_prices_purchase_
    values_or_customer_notes (tests/test_v260_role_audit.py), hier zusätzlich um "internal"/
    "office_note"/"vermerk"/"betrag"/"summe" erweitert. Ergebnis: KEIN FUND -- ServiceReport,
    Finding und InspectionItem tragen an keiner Stelle ein Feld mit diesem Namen (geprüft direkt
    an app/models.py). Der Test dokumentiert die Abwesenheit als Regression, nicht eine Behebung."""
    from app.routers.field_view import router as field_view_router
    db = threaded_db_session
    creator = _employee(db, "T-C1", "Fritz", "Ausgeschieden")
    order, _, property_id = _order(db, "AUF-C-0001", "P-C-0001")
    _signed_report_with_finding_and_foreign_time(db, order, creator)

    field = router_test_client(db, field_view_router, role="field", employee_id=creator.id)
    response = field.get(f"/api/field-view/properties/{property_id}/maintenance-history")
    assert response.status_code == 200, response.text
    history = response.json()
    assert len(history) == 1

    def keys(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                yield key
                yield from keys(value)
        elif isinstance(obj, list):
            for value in obj:
                yield from keys(value)

    forbidden = (
        "price", "preis", "purchase", "einkauf", "wage", "lohn", "gehalt", "cost", "kosten",
        "customer_note", "property_note", "internal", "office_note", "vermerk", "betrag", "summe",
    )
    offending = sorted({k for k in keys(history) if any(f in k.lower() for f in forbidden)})
    assert offending == [], offending
    # Exakte Feldmenge -- dieselbe wie in test_v260_role_audit.py, hier erneut belegt: nichts
    # Neues ist hinzugekommen, nichts Vorhandenes musste entfernt werden.
    assert set(history[0]) == {
        "id", "order_number", "order_title", "report_type", "report_type_label", "performed_at",
        "created_by_employee_name", "roof_areas", "inspection_items", "findings",
    }


# ---------------------------------------------------------------------------
# Punkt 2: das PDF ohne fremde Zeitbuchungen -- Schalter statt eigenem Renderer
# ---------------------------------------------------------------------------

def test_field_pdf_omits_only_the_time_entries_section(threaded_db_session):
    """Vergleich der beiden Renderer-Aufrufe an DEMSELBEN Bericht: das Kundendokument
    (build_service_report_pdf(), include_time_entries=True, Standard) zeigt "Erfasste Zeiten"
    samt dem Namen des Zeitbuchers -- die Monteursvariante (build_service_report_pdf_for_field())
    zeigt beides NICHT, aber Beschreibung/Prüfpunkt/Mangel bleiben in beiden identisch."""
    from app.service_report_pdf import build_service_report_pdf, build_service_report_pdf_for_field
    from app.service_reports import get_report_row
    db = threaded_db_session
    creator = _employee(db, "T-C2", "Fritz", "Ausgeschieden")
    order, _, _ = _order(db, "AUF-C-0002", "P-C-0002")
    report_id = _signed_report_with_finding_and_foreign_time(db, order, creator)
    report = get_report_row(db, report_id)

    full_text = _extract_pdf_text(build_service_report_pdf(db, report))
    field_text = _extract_pdf_text(build_service_report_pdf_for_field(db, report))

    assert b"Erfasste Zeiten" in full_text
    assert b"Kollegenzeit" in full_text
    assert b"Erfasste Zeiten" not in field_text
    assert b"Kollegenzeit" not in field_text

    # Der Ersteller ("damaliger Monteur") bleibt in BEIDEN Varianten sichtbar -- Punkt 2 erlaubt
    # dieses Feld ausdrücklich, nur die Zeitbuchung eines ANDEREN Kollegen muss verschwinden.
    for shared in (b"Wartungsbericht", b"Gully Nordost", b"Gully verstopft", b"AUF-C-0002", b"Ausgeschieden"):
        assert shared in full_text, shared
        assert shared in field_text, shared


def test_field_pdf_never_calls_list_entries_and_carries_no_price_key(threaded_db_session, monkeypatch):
    """Strukturelle statt nur inhaltliche Garantie: list_entries() wird bei
    include_time_entries=False gar nicht erst aufgerufen (nicht nur die Tabelle ausgeblendet) --
    ein Patch, der bei jedem Aufruf eine Ausnahme wirft, darf für die Field-Variante nicht
    ausgelöst werden. Zusätzlich ein rekursiver Schlüssel-Scan über report_to_dict() (die
    Datengrundlage, die build_service_report_pdf() tatsächlich in die Story einspeist) --
    dieselbe Fehlerklasse wie purchase_price, kein Fund."""
    import app.service_report_pdf as service_report_pdf_module
    from app.service_report_pdf import build_service_report_pdf_for_field
    from app.service_reports import get_report_row, report_to_dict
    db = threaded_db_session
    creator = _employee(db, "T-C3", "Fritz", "Ausgeschieden")
    order, _, _ = _order(db, "AUF-C-0003", "P-C-0003")
    report_id = _signed_report_with_finding_and_foreign_time(db, order, creator)
    report = get_report_row(db, report_id)

    def _boom(*args, **kwargs):
        raise AssertionError("list_entries() darf für die Field-PDF-Variante nicht aufgerufen werden.")
    monkeypatch.setattr(service_report_pdf_module, "list_entries", _boom)
    build_service_report_pdf_for_field(db, report)  # wirft nicht -> list_entries() wurde nie erreicht

    def keys(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                yield key
                yield from keys(value)
        elif isinstance(obj, list):
            for value in obj:
                yield from keys(value)

    forbidden = ("price", "preis", "purchase", "einkauf", "wage", "lohn", "gehalt", "cost", "kosten")
    offending = sorted({k for k in keys(report_to_dict(report)) if any(f in k.lower() for f in forbidden)})
    assert offending == [], offending


# ---------------------------------------------------------------------------
# Punkt 3: Zugang nur über das Objekt
# ---------------------------------------------------------------------------

def test_correct_object_and_report_returns_the_pdf(router_test_client, threaded_db_session):
    from app.routers.field_view import router as field_view_router
    db = threaded_db_session
    creator = _employee(db, "T-C4", "Fritz", "Ausgeschieden")
    viewer = _employee(db, "T-C5", "Uwe", "Aktuell")
    order, _, property_id = _order(db, "AUF-C-0004", "P-C-0004")
    report_id = _signed_report_with_finding_and_foreign_time(db, order, creator)

    field = router_test_client(db, field_view_router, role="field", employee_id=viewer.id)
    response = field.get(f"/api/field-view/properties/{property_id}/maintenance-history/{report_id}/pdf")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    text = _extract_pdf_text(response.content)
    assert b"Gully Nordost" in text
    assert b"Erfasste Zeiten" not in text


def test_guessed_report_id_without_a_real_object_route_is_rejected(router_test_client, threaded_db_session):
    """Es gibt keine Route, die eine bloße report_id ohne property_id annimmt (für `field` auf
    diesem Weg) -- eine nicht existierende report_id unter einem echten Objekt liefert 404, exakt
    wie ein tatsächlich nicht existierender Bericht."""
    from app.routers.field_view import router as field_view_router
    db = threaded_db_session
    viewer = _employee(db, "T-C6", "Uwe", "Aktuell")
    _, _, property_id = _order(db, "AUF-C-0005", "P-C-0005")

    field = router_test_client(db, field_view_router, role="field", employee_id=viewer.id)
    response = field.get(f"/api/field-view/properties/{property_id}/maintenance-history/999999/pdf")
    assert response.status_code == 404, response.text


def test_report_belonging_to_a_different_property_is_rejected(router_test_client, threaded_db_session):
    """Der zweite, eigenständige Angriffsfall: eine tatsächlich existierende report_id, aber über
    das ID des FALSCHEN Objekts angefragt -- resolve_property_history_report_for_field() prüft
    die Objekt-Zugehörigkeit erneut am Abrufzeitpunkt, nicht nur bei der Auflistung. Derselbe
    Bericht bleibt über sein EIGENES Objekt weiterhin erreichbar (Positivkontrolle)."""
    from app.routers.field_view import router as field_view_router
    db = threaded_db_session
    creator = _employee(db, "T-C7", "Fritz", "Ausgeschieden")
    viewer = _employee(db, "T-C8", "Uwe", "Aktuell")
    order_a, _, property_a = _order(db, "AUF-C-0006", "P-C-0006")
    _, _, property_b = _order(db, "AUF-C-0007", "P-C-0007")  # fremdes, unabhängiges zweites Objekt
    report_id = _signed_report_with_finding_and_foreign_time(db, order_a, creator)

    field = router_test_client(db, field_view_router, role="field", employee_id=viewer.id)
    wrong = field.get(f"/api/field-view/properties/{property_b}/maintenance-history/{report_id}/pdf")
    assert wrong.status_code == 404, wrong.text
    correct = field.get(f"/api/field-view/properties/{property_a}/maintenance-history/{report_id}/pdf")
    assert correct.status_code == 200, correct.text


def test_draft_report_is_not_reachable_this_way(router_test_client, threaded_db_session):
    """Nur bereits unterschriebene Berichte gehören zur Historie -- ein Entwurf (z. B. noch in
    Arbeit auf einem anderen Auftrag) bleibt über diesen Weg unerreichbar, dieselbe Grenze wie
    list_maintenance_history_for_property_field()."""
    from app.routers.field_view import router as field_view_router
    from app.service_reports import create_report
    db = threaded_db_session
    creator = _employee(db, "T-C9", "Fritz", "Ausgeschieden")
    viewer = _employee(db, "T-C10", "Uwe", "Aktuell")
    order, _, property_id = _order(db, "AUF-C-0008", "P-C-0008")
    report_id = create_report(db, order.id, "wartung", created_by_employee_id=creator.id)["id"]

    field = router_test_client(db, field_view_router, role="field", employee_id=viewer.id)
    response = field.get(f"/api/field-view/properties/{property_id}/maintenance-history/{report_id}/pdf")
    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# Punkt 4: nur Lesen -- kein PUT/DELETE/sign über diesen Weg
# ---------------------------------------------------------------------------

def test_the_new_route_accepts_only_get(router_test_client, threaded_db_session):
    from app.routers.field_view import router as field_view_router
    db = threaded_db_session
    creator = _employee(db, "T-C11", "Fritz", "Ausgeschieden")
    order, _, property_id = _order(db, "AUF-C-0009", "P-C-0009")
    report_id = _signed_report_with_finding_and_foreign_time(db, order, creator)

    field = router_test_client(db, field_view_router, role="field", employee_id=creator.id)
    url = f"/api/field-view/properties/{property_id}/maintenance-history/{report_id}/pdf"
    assert field.put(url, json={}).status_code == 405
    assert field.delete(url).status_code == 405
    assert field.post(url, json={}).status_code == 405


def test_existing_write_endpoints_remain_ownership_gated_unaffected_by_the_new_read_path(
    router_test_client, threaded_db_session,
):
    """Die eigentliche Bestätigung von Punkt 4: der neue, objektbezogene Lesezugang ändert nichts
    an require_field_report_ownership() -- ein Monteur, der über das Objekt lesen darf, bekommt
    über die klassischen Berichts-Endpunkte weiterhin ein 403 für PUT/DELETE/sign, wenn er nicht
    der Ersteller ist."""
    from app.routers.field_view import router as field_view_router
    from app.routers.service_reports import router as sr_router
    db = threaded_db_session
    creator = _employee(db, "T-C12", "Fritz", "Ausgeschieden")
    viewer = _employee(db, "T-C13", "Uwe", "Aktuell")
    order, _, property_id = _order(db, "AUF-C-0010", "P-C-0010")
    report_id = _signed_report_with_finding_and_foreign_time(db, order, creator)

    field = router_test_client(db, field_view_router, sr_router, role="field", employee_id=viewer.id)
    # Lesen über das Objekt: erlaubt.
    assert field.get(f"/api/field-view/properties/{property_id}/maintenance-history/{report_id}/pdf").status_code == 200
    # Schreiben über den klassischen Weg: weiterhin gesperrt, unverändert.
    update = {"report_type": "wartung", "performed_at": "2025-05-03", "description": "Manipuliert"}
    assert field.put(f"/api/service-reports/{report_id}", json=update).status_code == 403
    assert field.delete(f"/api/service-reports/{report_id}").status_code == 403
    assert field.post(f"/api/service-reports/{report_id}/sign", json={
        "installer_signature_png_base64": "eA==", "installer_signature_name": "x",
        "customer_signature_png_base64": "eA==", "customer_signature_name": "x",
    }).status_code == 403
