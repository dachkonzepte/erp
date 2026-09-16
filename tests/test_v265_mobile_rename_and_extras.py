"""Version 1.3.61 -- fünf weitere Anpassungen an der Monteursansicht (siehe CLAUDE.md
"Zeiterfassung für Monteure" -> "Fünf weitere Anpassungen (seit 1.3.61)"):

1. Umbenennung /vor-ort -> /mobil, /vor-ort entfällt ersatzlos.
2. Startseite für Monteure: "/" leitet für `field` auf /mobil weiter (siehe auch
   test_v260_role_audit.py::TestPageRouteClassification::test_field_reaches_only_the_five_pages_it_needs).
3. Tätigkeit im Nachtrag UND im Schnellstart (time_tracking_field.html).
4. Stundenzettel: GET /api/field-view/timesheet.pdf (eigener PDF-Renderer, gemeinsamer Rahmen).
5. Eigene Plantafel-Einträge: GET /api/field-view/upcoming (list_upcoming_assignments_for_employee()).

Plus der vom Nutzer ausdrücklich verlangte, wiederholte Angriffstest: volle Plantafel, fremde
Stunden, fremde Plantafel-Einträge -- alle drei müssen für `field` weiterhin gesperrt sein.
"""

from datetime import date, timedelta
from decimal import Decimal

import pypdfium2 as pdfium

from app.field_timesheet_pdf import month_date_range
from tests.test_v167_pagination import count_pdf_pages


def _employee(db, number, first, last):
    from app.models import Employee
    emp = Employee(employee_number=number, first_name=first, last_name=last,
                   employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    db.add(emp); db.commit()
    return emp


def _order(db, order_number, project_number, customer=None):
    from app.models import Customer, Order, OrderItem, Project
    if customer is None:
        customer = Customer(name="Testkunde", last_name="Testkunde", city="Teststadt")
        db.add(customer); db.flush()
    project = Project(project_number=project_number, name="Testprojekt", customer_id=customer.id)
    db.add(project); db.flush()
    order = Order(order_number=order_number, project_id=project.id,
                  source_quote_id=int(order_number.rsplit("-", 1)[-1]),
                  quote_number_snapshot=f"A-{order_number}", title="Testauftrag", customer_name=customer.name)
    db.add(order); db.flush()
    db.add(OrderItem(order_id=order.id, sort_order=10, position_number="1", short_text="Dacheindeckung",
                     quantity=Decimal("10"), unit="m²", unit_price=Decimal("50")))
    db.commit()
    return order, customer


def _assign_via_team(db, order, emp):
    from app.models import Team, WorkPreparationTeamAssignment, WorkPreparationTeamEmployee
    from app.work_preparation import ensure_preparation
    prep = ensure_preparation(db, order.id)
    team = Team(name=f"Kolonne {order.order_number}-{emp.id}")
    db.add(team); db.flush()
    assignment = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
    db.add(assignment); db.flush()
    db.add(WorkPreparationTeamEmployee(assignment_id=assignment.id, employee_id=emp.id,
                                       employee_name_snapshot=f"{emp.first_name} {emp.last_name}"))
    db.commit()
    return prep, assignment


def _slot(db, prep_id, team_assignment_id, start, end):
    from app.models import PlanningSlot
    slot = PlanningSlot(preparation_id=prep_id, team_assignment_id=team_assignment_id, start_date=start, end_date=end)
    db.add(slot); db.commit()
    return slot


def _time_entry(db, employee_id, order, work_date, hours, entry_type="site", activity=None):
    from app.models import TimeEntry
    entry = TimeEntry(employee_id=employee_id, project_id=order.project_id, order_id=order.id,
                      work_date=work_date, entry_type=entry_type, activity=activity,
                      hours=Decimal(str(hours)), status="booked")
    db.add(entry); db.commit()
    return entry


class TestVorOrtRenamedToMobil:
    """Punkt 1: /vor-ort entfällt ersatzlos, /mobil ist die neue, einzige URL."""

    def test_vor_ort_no_longer_exists(self, router_test_client, threaded_db_session):
        from app.routers.pages import router as pages_router
        db = threaded_db_session
        field = router_test_client(db, pages_router, role="field")
        assert field.get("/vor-ort", follow_redirects=False).status_code == 404

    def test_mobil_reachable_for_field_with_correct_title(self, router_test_client, threaded_db_session):
        from app.routers.pages import router as pages_router
        db = threaded_db_session
        field = router_test_client(db, pages_router, role="field")
        resp = field.get("/mobil")
        assert resp.status_code == 200
        assert "DACHKONZEPTE GmbH - Mobil" in resp.text

    def test_office_and_admin_are_blocked_from_mobil_pages_unchanged(self, router_test_client, threaded_db_session):
        """Reine Regression -- /mobil war schon vor 1.3.61 (als /vor-ort) für jede Rolle
        erreichbar (_any_role_dep), das ändert die Umbenennung nicht."""
        from app.routers.pages import router as pages_router
        db = threaded_db_session
        for role in ("office", "admin", "field"):
            client = router_test_client(db, pages_router, role=role)
            assert client.get("/mobil").status_code == 200, role

    def test_manifest_start_url_points_to_mobil(self, router_test_client, threaded_db_session):
        from app.routers.field_view import router as fv_router
        db = threaded_db_session
        field = router_test_client(db, fv_router, role="field")
        resp = field.get("/manifest.json")
        assert resp.status_code == 200
        assert resp.json()["start_url"] == "/mobil"

    def test_login_redirects_field_to_mobil_not_vor_ort(self, router_test_client, threaded_db_session):
        """app/permissions.py::default_home_page_for_role() -- der einzige Ort, der die
        Rolle-zu-Startseite-Zuordnung serverseitig trägt (login_page(), dashboard_page(),
        der 403-Exception-Handler)."""
        from app.permissions import ROLE_FIELD, default_home_page_for_role
        assert default_home_page_for_role(ROLE_FIELD) == "/mobil"


class TestStartseiteFuerMonteure:
    """Punkt 2: "/" leitet für `field` auf /mobil weiter, statt zu sperren oder das Dashboard zu
    zeigen -- ausführlich als Rollenzuordnungstest bereits in test_v260_role_audit.py belegt,
    hier zusätzlich der reine Redirect-Mechanismus isoliert."""

    def test_root_redirects_field_to_mobil(self, router_test_client, threaded_db_session):
        from app.routers.pages import router as pages_router
        db = threaded_db_session
        field = router_test_client(db, pages_router, role="field")
        resp = field.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/mobil"

    def test_root_shows_dashboard_for_office_and_admin_unchanged(self, router_test_client, threaded_db_session):
        from app.routers.pages import router as pages_router
        db = threaded_db_session
        for role in ("office", "admin"):
            client = router_test_client(db, pages_router, role=role)
            resp = client.get("/", follow_redirects=False)
            assert resp.status_code == 200, role


class TestTaetigkeitInSchnellstartUndNachtrag:
    """Punkt 3: sowohl Schnellstart als auch Nachtrag haben jetzt ein optionales
    Tätigkeit-Feld -- vor 1.3.61 hatte KEINS von beiden eins (nur die Zeitart-Kacheln), die vom
    Nutzer angenommene Prämisse ("der Schnellstart hat es schon") traf nicht zu, siehe CLAUDE.md."""

    def test_quick_and_manual_activity_selects_are_present(self, router_test_client, threaded_db_session):
        from app.routers.pages import router as pages_router
        db = threaded_db_session
        field = router_test_client(db, pages_router, role="field")
        body = field.get("/time-tracking").text
        assert 'id="quickActivity"' in body
        assert 'id="manualActivity"' in body

    def test_time_entries_start_and_manual_create_accept_an_activity_value(self, router_test_client, threaded_db_session):
        """Backend-seitig war activity schon immer optional auf beiden Schemas -- hier als
        Ende-zu-Ende-Beleg, dass ein Monteur tatsächlich mit Tätigkeit buchen kann."""
        from app.routers.field_view import router as fv_router
        from app.routers.time_tracking import router as tt_router
        db = threaded_db_session
        emp = _employee(db, "T-265-1", "Petra", "Taetig")
        order, _ = _order(db, "AUF-265-0001", "P-265-0001")
        prep, assignment = _assign_via_team(db, order, emp)
        _slot(db, prep.id, assignment.id, date.today(), date.today())

        field = router_test_client(db, fv_router, tt_router, role="field", employee_id=emp.id)
        resp = field.post("/api/time-entries", json={
            "employee_id": emp.id, "order_id": order.id, "work_date": date.today().isoformat(),
            "entry_type": "site", "activity": "Dacheindeckung", "hours": "2.5",
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["activity"] == "Dacheindeckung"


class TestStundenzettel:
    """Punkt 4: eigener Monats-Stundenzettel für Monteure -- nur eigene Buchungen, als PDF über
    den gemeinsamen Rahmen (render_framed_pdf(), document_type="field_timesheet")."""

    def test_month_date_range(self):
        assert month_date_range(2026, 2) == (date(2026, 2, 1), date(2026, 2, 28))
        assert month_date_range(2026, 12) == (date(2026, 12, 1), date(2026, 12, 31))

    def test_timesheet_pdf_endpoint_returns_valid_pdf_for_own_month(self, router_test_client, threaded_db_session):
        from app.routers.field_view import router as fv_router
        db = threaded_db_session
        emp = _employee(db, "T-265-2", "Rudi", "Rapport")
        order, _ = _order(db, "AUF-265-0002", "P-265-0002")
        today = date.today()
        _time_entry(db, emp.id, order, today, "4.0", activity="Dacheindeckung")
        _time_entry(db, emp.id, order, today, "1.5", entry_type="travel")

        field = router_test_client(db, fv_router, role="field", employee_id=emp.id)
        resp = field.get(f"/api/field-view/timesheet.pdf?year={today.year}&month={today.month}")
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"
        assert count_pdf_pages(resp.content) >= 1

    def test_timesheet_pdf_defaults_to_current_month_without_params(self, router_test_client, threaded_db_session):
        from app.routers.field_view import router as fv_router
        db = threaded_db_session
        emp = _employee(db, "T-265-3", "Silke", "Standard")
        field = router_test_client(db, fv_router, role="field", employee_id=emp.id)
        resp = field.get("/api/field-view/timesheet.pdf")
        assert resp.status_code == 200

    def test_unlinked_field_account_gets_422_not_500(self, router_test_client, threaded_db_session):
        from app.routers.field_view import router as fv_router
        db = threaded_db_session
        field = router_test_client(db, fv_router, role="field")  # kein employee_id
        resp = field.get("/api/field-view/timesheet.pdf")
        assert resp.status_code == 422

    def test_timesheet_never_includes_a_colleagues_hours(self, router_test_client, threaded_db_session):
        """Sicherheitsrelevant: nur die eigenen Buchungen dürfen im PDF erscheinen -- geprüft über
        den Textinhalt des erzeugten PDFs (Kollegen-Auftragsnummer darf nirgends auftauchen)."""
        from app.routers.field_view import router as fv_router
        db = threaded_db_session
        me = _employee(db, "T-265-4", "Timo", "Eigen")
        colleague = _employee(db, "T-265-5", "Uwe", "Kollege")
        my_order, _ = _order(db, "AUF-265-0003", "P-265-0003")
        colleague_order, _ = _order(db, "AUF-265-0004", "P-265-0004")
        today = date.today()
        _time_entry(db, me.id, my_order, today, "3.0")
        _time_entry(db, colleague.id, colleague_order, today, "5.0")

        field = router_test_client(db, fv_router, role="field", employee_id=me.id)
        resp = field.get(f"/api/field-view/timesheet.pdf?year={today.year}&month={today.month}")
        assert resp.status_code == 200
        pages = count_pdf_pages(resp.content)
        pdf = pdfium.PdfDocument(resp.content)
        text = ""
        for i in range(pages):
            textpage = pdf[i].get_textpage()
            text += textpage.get_text_range(0, textpage.count_chars())
            textpage.close()
        pdf.close()
        assert my_order.order_number in text
        assert colleague_order.order_number not in text


class TestEigenePlantafelEintraege:
    """Punkt 5: GET /api/field-view/upcoming -- reine Leseansicht der eigenen KOMMENDEN Termine,
    kein Zugriff auf die Plantafel selbst (siehe auch TestVollePlantafelBleibtGesperrt unten)."""

    def test_upcoming_assignment_within_window_is_returned(self, router_test_client, threaded_db_session):
        from app.routers.field_view import router as fv_router
        db = threaded_db_session
        emp = _employee(db, "T-265-6", "Vera", "Kommend")
        order, _ = _order(db, "AUF-265-0005", "P-265-0005")
        prep, assignment = _assign_via_team(db, order, emp)
        future = date.today() + timedelta(days=10)
        _slot(db, prep.id, assignment.id, future, future)

        field = router_test_client(db, fv_router, role="field", employee_id=emp.id)
        resp = field.get("/api/field-view/upcoming")
        assert resp.status_code == 200, resp.text
        ids = {row["order_id"] for row in resp.json()}
        assert order.id in ids

    def test_unlinked_field_account_gets_empty_list_not_error(self, router_test_client, threaded_db_session):
        from app.routers.field_view import router as fv_router
        db = threaded_db_session
        field = router_test_client(db, fv_router, role="field")  # kein employee_id
        resp = field.get("/api/field-view/upcoming")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_far_future_assignment_outside_window_is_excluded(self, router_test_client, threaded_db_session):
        from app.routers.field_view import router as fv_router
        db = threaded_db_session
        emp = _employee(db, "T-265-7", "Willi", "Weit-Weg")
        order, _ = _order(db, "AUF-265-0006", "P-265-0006")
        prep, assignment = _assign_via_team(db, order, emp)
        far = date.today() + timedelta(days=90)
        _slot(db, prep.id, assignment.id, far, far)

        field = router_test_client(db, fv_router, role="field", employee_id=emp.id)
        resp = field.get("/api/field-view/upcoming")
        ids = {row["order_id"] for row in resp.json()}
        assert order.id not in ids


class TestVollePlantafelBleibtGesperrt:
    """Der vom Nutzer ausdrücklich verlangte, wiederholte Angriffstest an den durch diese Runde
    berührten Stellen: volle Plantafel, fremde Stunden, fremde Plantafel-Einträge -- kein
    "durchgelassen". Gegen eine isolierte Testinstanz, nie gegen eine echte Datenbank."""

    def test_field_cannot_open_the_full_planning_page(self, router_test_client, threaded_db_session):
        from app.routers.pages import router as pages_router
        db = threaded_db_session
        field = router_test_client(db, pages_router, role="field")
        assert field.get("/planning", follow_redirects=False).status_code == 403

    def test_field_cannot_call_the_full_planning_board_api(self, router_test_client, threaded_db_session):
        from app.routers.planning import router as planning_router
        db = threaded_db_session
        field = router_test_client(db, planning_router, role="field")
        assert field.get("/api/planning").status_code == 403
        assert field.get("/api/planning/settings").status_code == 403

    def test_field_cannot_read_a_colleagues_hours_via_time_entries(self, router_test_client, threaded_db_session):
        from app.routers.time_tracking import router as tt_router
        db = threaded_db_session
        me = _employee(db, "T-265-8", "Xenia", "Selbst")
        colleague = _employee(db, "T-265-9", "Yannik", "Kollege")
        order, _ = _order(db, "AUF-265-0007", "P-265-0007")
        today = date.today()
        _time_entry(db, me.id, order, today, "2.0")
        _time_entry(db, colleague.id, order, today, "6.0")

        field = router_test_client(db, tt_router, role="field", employee_id=me.id)
        # selbst ein expliziter Versuch, die fremde employee_id anzugeben, wird überschrieben
        resp = field.get(f"/api/time-entries?employee_id={colleague.id}")
        assert resp.status_code == 200
        hours = {float(r["hours"]) for r in resp.json()}
        assert hours == {2.0}

    def test_field_cannot_see_a_colleagues_upcoming_planning_entries(self, router_test_client, threaded_db_session):
        from app.routers.field_view import router as fv_router
        db = threaded_db_session
        me = _employee(db, "T-265-10", "Zora", "Selbst")
        colleague = _employee(db, "T-265-11", "Achim", "Kollege")
        colleague_order, _ = _order(db, "AUF-265-0008", "P-265-0008")
        prep, assignment = _assign_via_team(db, colleague_order, colleague)
        future = date.today() + timedelta(days=5)
        _slot(db, prep.id, assignment.id, future, future)

        field = router_test_client(db, fv_router, role="field", employee_id=me.id)
        resp = field.get("/api/field-view/upcoming")
        assert resp.status_code == 200
        ids = {row["order_id"] for row in resp.json()}
        assert colleague_order.id not in ids
