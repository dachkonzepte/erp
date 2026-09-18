"""Version 1.3.60 -- Zeiterfassung für Monteure (siehe CLAUDE.md "Zeiterfassung für Monteure").

Reduzierte Zeiterfassung auf /vor-ort statt der vollen, sidebar-getragenen time_tracking.html:
- list_field_bookable_order_ids() (app/planning.py): dasselbe ±14-Tage-Zeitfenster wie der
  1.3.58-Wartungsfinder, auf Aufträge statt Objekte angewendet, PLUS ungefenstert jeder Auftrag,
  zu dem der Monteur bereits selbst einen Bericht angelegt hat (deckt "Wartung durchführen"-
  Aufträge ohne eigene Arbeitsvorbereitung ab -- ein echter, beim Bauen gefundener Fund).
- GET /api/field-view/time-tracking/orders: liefert genau diese Liste, self-scoped.
- app/routers/pages.py::time_tracking_page(): rollenbewusste Vorlagenwahl unter derselben URL
  /time-tracking -- `field` bekommt time_tracking_field.html (keine Gruppenbuchung, keine
  Sidebar), office/admin unverändert time_tracking.html.
"""

from datetime import date, timedelta
from decimal import Decimal

from app.planning import list_field_bookable_order_ids


def _employee(db, number, first, last):
    from app.models import Employee
    emp = Employee(employee_number=number, first_name=first, last_name=last,
                   employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    db.add(emp); db.commit()
    return emp


def _order(db, order_number, project_number, customer=None):
    from app.models import Customer, Order, OrderItem, Project
    from app.project_pipeline_columns import default_pipeline_column_id
    if customer is None:
        customer = Customer(name="Testkunde", last_name="Testkunde", city="Teststadt")
        db.add(customer); db.flush()
    project = Project(project_number=project_number, name="Testprojekt", customer_id=customer.id, pipeline_column_id=default_pipeline_column_id(db))
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


class TestListFieldBookableOrderIds:
    """app/planning.py::list_field_bookable_order_ids() -- dasselbe Fenster wie der
    1.3.58-Wartungsfinder, plus die ungefensterte Ergänzung um selbst angelegte Berichte."""

    def test_order_within_window_via_real_planning_slot_is_included(self, db_session):
        db = db_session
        emp = _employee(db, "T-264-1", "Anna", "Fenster")
        order, _ = _order(db, "AUF-264-0001", "P-264-0001")
        prep, assignment = _assign_via_team(db, order, emp)
        _slot(db, prep.id, assignment.id, date.today(), date.today())
        assert order.id in list_field_bookable_order_ids(db, emp.id)

    def test_order_far_outside_window_is_excluded(self, db_session):
        db = db_session
        emp = _employee(db, "T-264-2", "Bruno", "Weit-Weg")
        order, _ = _order(db, "AUF-264-0002", "P-264-0002")
        prep, assignment = _assign_via_team(db, order, emp)
        far = date.today() - timedelta(days=90)
        _slot(db, prep.id, assignment.id, far, far)
        assert order.id not in list_field_bookable_order_ids(db, emp.id)

    def test_order_assigned_yesterday_worked_today_falls_inside_window(self, db_session):
        """Die konkret geprüfte Betreiberfrage: ein erst gestern angelegter/zugewiesener Auftrag,
        an dem heute gearbeitet wird, muss sicher im Fenster liegen -- die Arbeitsvorbereitung
        selbst trägt hier keinerlei Historie darüber, wann sie angelegt wurde (kein
        created_at-Feld auf WorkPreparation), nur der Plantafel-Slot mit start_date=heute zählt."""
        db = db_session
        emp = _employee(db, "T-264-3", "Carla", "Gestern-Zugewiesen")
        order, _ = _order(db, "AUF-264-0003", "P-264-0003")
        prep, assignment = _assign_via_team(db, order, emp)
        _slot(db, prep.id, assignment.id, date.today(), date.today())
        assert order.id in list_field_bookable_order_ids(db, emp.id, window_days=14)

    def test_no_planning_slot_falls_back_to_planned_start_end(self, db_session):
        db = db_session
        emp = _employee(db, "T-264-4", "Dieter", "Nur-Geplant")
        order, _ = _order(db, "AUF-264-0004", "P-264-0004")
        prep, _ = _assign_via_team(db, order, emp)
        prep.planned_start = date.today(); prep.planned_end = date.today()
        db.commit()
        assert order.id in list_field_bookable_order_ids(db, emp.id)

    def test_adhoc_order_without_any_work_preparation_is_included_via_own_report(self, db_session):
        """Der beim Bauen gefundene, echte Fund: create_quick_service_order() (hinter "Wartung
        durchführen", seit 1.3.56 auch für Monteure) legt bewusst KEINE WorkPreparation an --
        employee_assigned_order_ids() und damit auch das Zeitfenster finden einen solchen Auftrag
        nie, unabhängig von window_days. Der Monteur bleibt trotzdem buchungsfähig, weil er
        selbst Ersteller eines ServiceReport darauf ist -- exakt der zweite Weg von
        field_may_access_order() (app/orders.py)."""
        from app.service_reports import create_report
        db = db_session
        emp = _employee(db, "T-264-5", "Erik", "Ungeplant")
        order, _ = _order(db, "AUF-264-0005", "P-264-0005")
        # bewusst KEINE _assign_via_team()/_slot() -- kein Plantafel-Bezug, wie bei einem
        # per "Wartung durchführen" erzeugten Auftrag
        create_report(db, order.id, "rapport", description="Ungeplante Wartung", created_by_employee_id=emp.id)
        db.commit()
        assert order.id in list_field_bookable_order_ids(db, emp.id)
        # selbst mit einem winzigen Fenster (0 Tage) bleibt der Auftrag sichtbar -- ungefenstert
        assert order.id in list_field_bookable_order_ids(db, emp.id, window_days=0)

    def test_unrelated_order_is_never_included(self, db_session):
        db = db_session
        emp = _employee(db, "T-264-6", "Frida", "Unbeteiligt")
        other_emp = _employee(db, "T-264-7", "Georg", "Anderer")
        order, _ = _order(db, "AUF-264-0006", "P-264-0006")
        prep, assignment = _assign_via_team(db, order, other_emp)
        _slot(db, prep.id, assignment.id, date.today(), date.today())
        assert order.id not in list_field_bookable_order_ids(db, emp.id)


class TestFieldViewTimeTrackingOrdersEndpoint:
    """GET /api/field-view/time-tracking/orders -- self-scoped, keine employee_id im Request."""

    def test_field_sees_own_windowed_and_own_adhoc_orders_not_a_colleagues(self, router_test_client, threaded_db_session):
        from app.service_reports import create_report
        from app.routers.field_view import router as fv_router
        db = threaded_db_session
        me = _employee(db, "T-264-8", "Hanna", "Selbst")
        colleague = _employee(db, "T-264-9", "Ivo", "Kollege")
        windowed_order, _ = _order(db, "AUF-264-0007", "P-264-0007")
        prep, assignment = _assign_via_team(db, windowed_order, me)
        _slot(db, prep.id, assignment.id, date.today(), date.today())
        adhoc_order, _ = _order(db, "AUF-264-0008", "P-264-0008")
        create_report(db, adhoc_order.id, "rapport", description=None, created_by_employee_id=me.id)
        colleague_order, _ = _order(db, "AUF-264-0009", "P-264-0009")
        colleague_prep, colleague_assignment = _assign_via_team(db, colleague_order, colleague)
        _slot(db, colleague_prep.id, colleague_assignment.id, date.today(), date.today())
        db.commit()

        field = router_test_client(db, fv_router, role="field", employee_id=me.id)
        resp = field.get("/api/field-view/time-tracking/orders")
        assert resp.status_code == 200, resp.text
        ids = {row["id"] for row in resp.json()}
        assert ids == {windowed_order.id, adhoc_order.id}

    def test_unlinked_field_account_gets_empty_list_not_403(self, router_test_client, threaded_db_session):
        from app.routers.field_view import router as fv_router
        db = threaded_db_session
        field = router_test_client(db, fv_router, role="field")  # kein employee_id
        resp = field.get("/api/field-view/time-tracking/orders")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_completed_or_cancelled_orders_are_excluded(self, router_test_client, threaded_db_session):
        from app.routers.field_view import router as fv_router
        db = threaded_db_session
        me = _employee(db, "T-264-10", "Jasmin", "Abgeschlossen")
        order, _ = _order(db, "AUF-264-0010", "P-264-0010")
        prep, assignment = _assign_via_team(db, order, me)
        _slot(db, prep.id, assignment.id, date.today(), date.today())
        order.status = "abgeschlossen"
        db.commit()

        field = router_test_client(db, fv_router, role="field", employee_id=me.id)
        resp = field.get("/api/field-view/time-tracking/orders")
        assert resp.json() == []


class TestFieldTimeTrackingPageRouting:
    """app/routers/pages.py::time_tracking_page() -- dieselbe URL /time-tracking rendert seit
    1.3.60 rollenbewusst zwei verschiedene Vorlagen. Die Weiche hängt ausschließlich an der
    Rolle, nicht am aufrufenden Link/Pfad (Betreibervorgabe) -- deshalb hier auch geprüft, dass
    ein mitgegebener ?order_id=-Query-Parameter (wie ihn service_reports.html anhängt) daran
    nichts ändert."""

    def test_field_gets_the_reduced_template_without_sidebar_or_group_booking(self, router_test_client, threaded_db_session):
        from app.routers.pages import router as pages_router
        db = threaded_db_session
        field = router_test_client(db, pages_router, role="field")
        resp = field.get("/time-tracking")
        assert resp.status_code == 200
        body = resp.text
        assert "quickTiles" in body  # eindeutiger Marker aus time_tracking_field.html
        assert "app-sidebar" not in body  # keine volle Sidebar (_sidebar.html)
        assert "groupDialog" not in body  # keine Gruppenbuchung
        assert "time-entry-groups" not in body
        assert "manualEmployeeWrap" not in body  # kein Mitarbeiterfeld

    def test_field_gets_reduced_template_even_with_order_id_query_param(self, router_test_client, threaded_db_session):
        """Der Weg von service_reports.html (#timeLink -> /time-tracking?order_id=...) darf die
        Weiche nicht umgehen -- sie hängt an der Rolle, nicht am Pfad/den Query-Parametern."""
        from app.routers.pages import router as pages_router
        db = threaded_db_session
        field = router_test_client(db, pages_router, role="field")
        resp = field.get("/time-tracking?order_id=1")
        assert resp.status_code == 200
        assert "quickTiles" in resp.text
        assert "app-sidebar" not in resp.text

    def test_office_and_admin_still_get_the_full_sidebar_template_with_group_booking(self, router_test_client, threaded_db_session):
        from app.routers.pages import router as pages_router
        db = threaded_db_session
        for role in ("buero_auftrag", "admin"):
            client = router_test_client(db, pages_router, role=role)
            resp = client.get("/time-tracking")
            assert resp.status_code == 200, role
            assert "groupDialog" in resp.text, role
            assert "app-sidebar" in resp.text, role
