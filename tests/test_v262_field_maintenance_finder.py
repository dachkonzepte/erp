"""Version 1.3.58 -- Rechtekonzept, Nachtrag: /vor-ort-Vertragsfinder ("Wartungen an meinen
Objekten").

Ein Monteur soll auf /vor-ort einen Vertrag finden, um eine ungeplante Wartung zu starten, ohne
die volle Vertragsliste durchsuchen zu können. Betreibervorgabe (siehe CLAUDE.md):

- Nicht ungefiltert -- ein ±14-Tage-Fenster um eine tatsächliche PlanningSlot-Terminierung der
  Zuordnung (Team- oder Einzelzuweisung an der AV), WorkPreparation.planned_start/planned_end als
  Rückfall, falls keine Terminierung existiert. WorkPreparation.status bewusst NICHT einbezogen --
  siehe app/planning.py::list_field_relevant_property_ids()-Docstring für die Begründung (das
  Feld lässt sich zwar ändern, aber die reale Datenbank enthält dafür nur eine einzige Zeile,
  zu dünn für ein Urteil; "offen ODER Zeitfenster" hätte das Altlasten-Risiko wieder eingeführt).
- Alle Verträge des betroffenen Objekts zeigen, fällige hervorheben.
- Reduziertes Schema: property_name/customer_name nur zur Identifikation, keine Kundennummer,
  keine Adresse über den Ort hinaus.
- Die Karte darf leer bleiben, ohne zu stören (kein 422/500, ein ruhiger Hinweistext).

Testet app/planning.py::list_field_relevant_property_ids(), app/maintenance_contracts.py::
list_relevant_contracts_for_employee() und den Endpunkt GET /api/field-view/maintenance-contracts
direkt über echte Routen (Muster tests/test_v260_role_audit.py::TestObjectFilteringForFieldTeilB)."""

from datetime import date, timedelta
from decimal import Decimal

from app.maintenance_contracts import create_contract, list_relevant_contracts_for_employee, set_contract_archived
from app.planning import list_field_relevant_property_ids


def _employee(db, number, first, last):
    from app.models import Employee
    emp = Employee(employee_number=number, first_name=first, last_name=last,
                   employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    db.add(emp); db.commit()
    return emp


def _order_with_property(db, order_number, project_number, customer=None, property_name="Objekt Nord"):
    """Muster tests/test_v260_role_audit.py::TestObjectFilteringForFieldTeilB._order() --
    ein Auftrag mit eigenem, benanntem Objekt (project.property_id gesetzt)."""
    from app.models import Customer, Order, OrderItem, Project, Property
    if customer is None:
        customer = Customer(name="Testkunde", last_name="Testkunde", city="Teststadt")
        db.add(customer); db.flush()
    prop = Property(customer_id=customer.id, name=property_name, street="Teststr. 1", city="Teststadt")
    db.add(prop); db.flush()
    project = Project(project_number=project_number, name="Testprojekt", customer_id=customer.id, property_id=prop.id)
    db.add(project); db.flush()
    order = Order(order_number=order_number, project_id=project.id,
                  source_quote_id=int(order_number.rsplit("-", 1)[-1]),
                  quote_number_snapshot=f"A-{order_number}", title="Testauftrag", customer_name=customer.name,
                  property_name=property_name)
    db.add(order); db.flush()
    db.add(OrderItem(order_id=order.id, sort_order=10, position_number="1", short_text="Dacheindeckung",
                     quantity=Decimal("10"), unit="m²", unit_price=Decimal("50")))
    db.commit()
    return order, customer, prop


def _order_without_property(db, order_number, project_number, customer):
    """Ein Auftrag OHNE eigenes Objekt (project.property_id bleibt NULL) -- für den
    Hauptadresse-Rückfall-Fall."""
    from app.models import Order, OrderItem, Project
    project = Project(project_number=project_number, name="Testprojekt", customer_id=customer.id)
    db.add(project); db.flush()
    order = Order(order_number=order_number, project_id=project.id,
                  source_quote_id=int(order_number.rsplit("-", 1)[-1]),
                  quote_number_snapshot=f"A-{order_number}", title="Testauftrag", customer_name=customer.name)
    db.add(order); db.flush()
    db.add(OrderItem(order_id=order.id, sort_order=10, position_number="1", short_text="Dacheindeckung",
                     quantity=Decimal("10"), unit="m²", unit_price=Decimal("50")))
    db.commit()
    return order


def _assign_individually(db, order, emp):
    from app.models import WorkPreparationEmployee
    from app.work_preparation import ensure_preparation
    prep = ensure_preparation(db, order.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=emp.id))
    db.commit()
    return prep


def _assign_via_team(db, order, emp):
    from app.models import Team, WorkPreparationTeamAssignment, WorkPreparationTeamEmployee
    from app.work_preparation import ensure_preparation
    prep = ensure_preparation(db, order.id)
    team = Team(name=f"Kolonne {order.order_number}")
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


class TestFieldRelevantPropertyIds:
    """app/planning.py::list_field_relevant_property_ids() -- die eine Definition, welche
    Objekte für die neue Karte relevant sind."""

    def test_individual_assignment_with_planning_slot_inside_window_is_found(self, threaded_db_session):
        db = threaded_db_session
        monteur = _employee(db, "T-262-1", "Ina", "Individuell")
        other = _employee(db, "T-262-2", "Otto", "Anders")
        order, _customer, prop = _order_with_property(db, "AUF-262-0001", "P-262-0001")
        _assign_individually(db, order, monteur)
        # PlanningSlot haengt an einer beliebigen Team-Zuweisung derselben AV (jeder Slot der AV
        # zaehlt fuer die Einzelzuweisung, siehe Docstring) -- Team hier bewusst mit einem
        # ANDEREN Mitarbeiter besetzt.
        prep, assignment = _assign_via_team(db, order, other)
        _slot(db, prep.id, assignment.id, date.today() - timedelta(days=1), date.today() + timedelta(days=1))

        ids = list_field_relevant_property_ids(db, monteur.id)
        assert ids == {prop.id}

    def test_planning_slot_far_outside_window_is_not_found(self, threaded_db_session):
        db = threaded_db_session
        monteur = _employee(db, "T-262-3", "Ina", "Weitweg")
        order, _customer, _prop = _order_with_property(db, "AUF-262-0002", "P-262-0002")
        prep, assignment = _assign_via_team(db, order, monteur)
        _slot(db, prep.id, assignment.id, date.today() + timedelta(days=60), date.today() + timedelta(days=61))

        assert list_field_relevant_property_ids(db, monteur.id) == set()

    def test_no_slot_falls_back_to_work_preparation_planned_dates(self, threaded_db_session):
        db = threaded_db_session
        monteur = _employee(db, "T-262-4", "Paula", "Plan")
        order, _customer, prop = _order_with_property(db, "AUF-262-0003", "P-262-0003")
        prep = _assign_individually(db, order, monteur)
        prep.planned_start = date.today() + timedelta(days=5)
        prep.planned_end = date.today() + timedelta(days=8)
        db.commit()

        assert list_field_relevant_property_ids(db, monteur.id) == {prop.id}

    def test_no_slot_and_no_planned_dates_is_not_found(self, threaded_db_session):
        db = threaded_db_session
        monteur = _employee(db, "T-262-5", "Paula", "Ohne")
        order, _customer, _prop = _order_with_property(db, "AUF-262-0004", "P-262-0004")
        _assign_individually(db, order, monteur)

        assert list_field_relevant_property_ids(db, monteur.id) == set()

    def test_team_assignment_is_found_too(self, threaded_db_session):
        db = threaded_db_session
        monteur = _employee(db, "T-262-6", "Theo", "Team")
        order, _customer, prop = _order_with_property(db, "AUF-262-0005", "P-262-0005")
        prep, assignment = _assign_via_team(db, order, monteur)
        _slot(db, prep.id, assignment.id, date.today(), date.today())

        assert list_field_relevant_property_ids(db, monteur.id) == {prop.id}

    def test_order_without_property_falls_back_to_customer_primary_address(self, threaded_db_session):
        db = threaded_db_session
        from app.models import Customer, Property
        monteur = _employee(db, "T-262-7", "Heidi", "Haupt")
        customer = Customer(name="Hauptadress-Kunde", last_name="Hauptadress-Kunde", city="Kernstadt")
        db.add(customer); db.flush()
        primary = Property(customer_id=customer.id, name="Hauptadresse", city="Kernstadt", is_primary_address=True)
        db.add(primary); db.commit()
        order = _order_without_property(db, "AUF-262-0006", "P-262-0006", customer)
        prep, assignment = _assign_via_team(db, order, monteur)
        _slot(db, prep.id, assignment.id, date.today(), date.today())

        assert list_field_relevant_property_ids(db, monteur.id) == {primary.id}

    def test_unrelated_employee_gets_nothing(self, threaded_db_session):
        db = threaded_db_session
        monteur = _employee(db, "T-262-8", "Niemand", "Zugeordnet")
        order, _customer, prop = _order_with_property(db, "AUF-262-0007", "P-262-0007")
        other = _employee(db, "T-262-9", "Jemand", "Anders")
        prep, assignment = _assign_via_team(db, order, other)
        _slot(db, prep.id, assignment.id, date.today(), date.today())

        assert list_field_relevant_property_ids(db, monteur.id) == set()


class TestRelevantContractsForEmployee:
    """app/maintenance_contracts.py::list_relevant_contracts_for_employee() -- Verträge des
    Objekts, gruppiert, reduziertes Schema."""

    def test_contract_on_the_relevant_property_is_returned_with_due_flag(self, threaded_db_session):
        db = threaded_db_session
        monteur = _employee(db, "T-262-10", "Frida", "Faellig")
        order, customer, prop = _order_with_property(db, "AUF-262-0010", "P-262-0010")
        prep, assignment = _assign_via_team(db, order, monteur)
        _slot(db, prep.id, assignment.id, date.today(), date.today())
        create_contract(db, customer_id=customer.id, property_id=prop.id, title="Jahreswartung",
                        interval_months=12, next_due_date=date.today())  # sofort faellig

        groups = list_relevant_contracts_for_employee(db, monteur.id)
        assert len(groups) == 1
        group = groups[0]
        assert group["property_name"] == "Objekt Nord"
        assert group["city"] == "Teststadt"
        assert group["customer_name"] == customer.name
        assert len(group["contracts"]) == 1
        contract_row = group["contracts"][0]
        assert contract_row["title"] == "Jahreswartung"
        assert contract_row["is_due"] is True
        # reduziertes Schema: keine Kundennummer, keine Strasse/PLZ, keine internen Felder
        assert set(contract_row.keys()) == {"id", "title", "next_due_date", "is_due"}
        assert set(group.keys()) == {"property_name", "city", "customer_name", "contracts"}

    def test_contract_far_in_the_future_is_returned_but_not_marked_due(self, threaded_db_session):
        db = threaded_db_session
        monteur = _employee(db, "T-262-11", "Nora", "Nichtfaellig")
        order, customer, prop = _order_with_property(db, "AUF-262-0011", "P-262-0011")
        prep, assignment = _assign_via_team(db, order, monteur)
        _slot(db, prep.id, assignment.id, date.today(), date.today())
        create_contract(db, customer_id=customer.id, property_id=prop.id, title="Ferne Wartung",
                        interval_months=12, next_due_date=date.today() + timedelta(days=300))

        groups = list_relevant_contracts_for_employee(db, monteur.id)
        assert groups[0]["contracts"][0]["is_due"] is False

    def test_contract_via_primary_address_fallback_is_matched(self, threaded_db_session):
        db = threaded_db_session
        from app.models import Customer, Property
        monteur = _employee(db, "T-262-12", "Hans", "Hauptadresse")
        customer = Customer(name="Nur-Hauptadresse GmbH", last_name="Nur-Hauptadresse GmbH", city="Kernstadt")
        db.add(customer); db.flush()
        primary = Property(customer_id=customer.id, name="Hauptadresse", city="Kernstadt", is_primary_address=True)
        db.add(primary); db.commit()
        order = _order_without_property(db, "AUF-262-0012", "P-262-0012", customer)
        prep, assignment = _assign_via_team(db, order, monteur)
        _slot(db, prep.id, assignment.id, date.today(), date.today())
        # property_id=None -- bedeutet "Hauptadresse", contract_to_dict()-Konvention.
        create_contract(db, customer_id=customer.id, property_id=None, title="Hauptadress-Wartung",
                        interval_months=12, next_due_date=date.today())

        groups = list_relevant_contracts_for_employee(db, monteur.id)
        assert len(groups) == 1
        assert groups[0]["property_name"] == "Hauptadresse"
        assert groups[0]["customer_name"] == customer.name
        assert groups[0]["contracts"][0]["title"] == "Hauptadress-Wartung"

    def test_archived_contract_is_excluded(self, threaded_db_session):
        db = threaded_db_session
        monteur = _employee(db, "T-262-13", "Anna", "Archiv")
        order, customer, prop = _order_with_property(db, "AUF-262-0013", "P-262-0013")
        prep, assignment = _assign_via_team(db, order, monteur)
        _slot(db, prep.id, assignment.id, date.today(), date.today())
        contract = create_contract(db, customer_id=customer.id, property_id=prop.id, title="Archivierte Wartung",
                                   interval_months=12, next_due_date=date.today())
        set_contract_archived(db, contract["id"], True)

        assert list_relevant_contracts_for_employee(db, monteur.id) == []

    def test_contract_with_active_roof_area_items_is_skipped_because_the_button_would_fail(self, threaded_db_session):
        """create_maintenance_visit() lehnt "Wartung durchführen" ab, sobald der Vertrag aktive
        Positionen unter use_roof_area_items hat (siehe dort) -- ein Monteur auf /vor-ort hat
        keinen Weg, statt dessen je Position vorzugehen, also erscheint der Vertrag hier gar
        nicht erst."""
        db = threaded_db_session
        from app.maintenance_contracts import create_contract_item, get_or_create_maintenance_settings
        from app.models import MaintenanceWindow
        from app.roof_areas import create_roof_area
        monteur = _employee(db, "T-262-14", "Rudi", "Roofarea")
        order, customer, prop = _order_with_property(db, "AUF-262-0014", "P-262-0014")
        prep, assignment = _assign_via_team(db, order, monteur)
        _slot(db, prep.id, assignment.id, date.today(), date.today())
        settings = get_or_create_maintenance_settings(db)
        settings.use_roof_area_items = True
        db.commit()
        contract = create_contract(db, customer_id=customer.id, property_id=prop.id, title="Positionsvertrag",
                                   interval_months=12, next_due_date=date.today())
        roof_area = create_roof_area(db, prop.id, name="Nordseite", roof_type="flachdach")
        window = MaintenanceWindow(label="Frühjahr", month_from=3, month_to=5)
        db.add(window); db.commit()
        create_contract_item(db, contract["id"], roof_area_id=roof_area["id"], maintenance_window_id=window.id,
                             description=None, template_project_id=None, inspection_template_id=None,
                             duration_minutes=None)

        assert list_relevant_contracts_for_employee(db, monteur.id) == []

    def test_no_relevant_property_returns_empty_list(self, threaded_db_session):
        db = threaded_db_session
        monteur = _employee(db, "T-262-15", "Niemand", "Objektlos")
        assert list_relevant_contracts_for_employee(db, monteur.id) == []


class TestFieldViewMaintenanceContractsEndpoint:
    """GET /api/field-view/maintenance-contracts -- echte Route (router_test_client), Muster
    tests/test_v260_role_audit.py::TestObjectFilteringForFieldTeilB."""

    def test_field_sees_the_grouped_contracts_of_the_relevant_property(self, router_test_client, threaded_db_session):
        from app.routers.field_view import router as field_view_router
        db = threaded_db_session
        monteur = _employee(db, "T-262-16", "Feld", "Sicht")
        order, customer, prop = _order_with_property(db, "AUF-262-0016", "P-262-0016")
        prep, assignment = _assign_via_team(db, order, monteur)
        _slot(db, prep.id, assignment.id, date.today(), date.today())
        create_contract(db, customer_id=customer.id, property_id=prop.id, title="Sichtbare Wartung",
                        interval_months=12, next_due_date=date.today())

        client = router_test_client(db, field_view_router, role="field", employee_id=monteur.id)
        resp = client.get("/api/field-view/maintenance-contracts")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body) == 1
        assert body[0]["contracts"][0]["title"] == "Sichtbare Wartung"

    def test_field_without_employee_link_gets_a_quiet_empty_list_not_an_error(self, router_test_client, threaded_db_session):
        from app.routers.field_view import router as field_view_router
        db = threaded_db_session
        client = router_test_client(db, field_view_router, role="field")  # kein employee_id
        resp = client.get("/api/field-view/maintenance-contracts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_module_disabled_returns_empty_list(self, router_test_client, threaded_db_session):
        from app.modules import set_module_enabled
        from app.routers.field_view import router as field_view_router
        db = threaded_db_session
        monteur = _employee(db, "T-262-17", "Kein", "Modul")
        order, customer, prop = _order_with_property(db, "AUF-262-0017", "P-262-0017")
        prep, assignment = _assign_via_team(db, order, monteur)
        _slot(db, prep.id, assignment.id, date.today(), date.today())
        create_contract(db, customer_id=customer.id, property_id=prop.id, title="Ausgeblendete Wartung",
                        interval_months=12, next_due_date=date.today())
        set_module_enabled(db, "wartungen", False)

        client = router_test_client(db, field_view_router, role="field", employee_id=monteur.id)
        resp = client.get("/api/field-view/maintenance-contracts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_office_and_admin_can_reach_it_too(self, router_test_client, threaded_db_session):
        from app.routers.field_view import router as field_view_router
        db = threaded_db_session
        for role in ("office", "admin"):
            client = router_test_client(db, field_view_router, role=role)
            resp = client.get("/api/field-view/maintenance-contracts")
            assert resp.status_code == 200, role
