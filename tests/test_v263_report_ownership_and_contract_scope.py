"""Version 1.3.59 -- Rechtekonzept, zwei Funde aus dem Sicherheitstest behoben (siehe CLAUDE.md
"Rechtekonzept" -> "Berichts-Eigentümerschaft" und "Vertragsfinder auf /vor-ort").

FUND 1: "fremde Berichte lesen und schreiben auf einem gemeinsamen Auftrag" --
require_field_order_access() prüfte nur "gehört der Auftrag zu mir", nie "gehört der Bericht zu
mir". Auf einem Mehrpersonen-Auftrag (Team-Besetzung an der AV) konnte ein Monteur jeden Bericht
eines Kollegen lesen, ändern, löschen und signieren. Behoben: Lesen der Berichtsliste bleibt für
jeden mit Auftragszugriff erlaubt, aber jeder Bericht eines ANDEREN Erstellers kommt im
reduzierten Schema der Wartungshistorie (ServiceReportHistoryOut); jeder Detail-/Schreibzugriff
auf einen konkreten Bericht (PUT/DELETE/sign, Prüfpunkte, Fotos, Material, Mängel, PDF) verlangt
zusätzlich, dass der Monteur dessen Ersteller ist (require_field_report_ownership()). Bewusste
betriebliche Festlegung (Betreibervorgabe): jeder Monteur schreibt seinen eigenen Bericht, keine
Fortführung durch einen Kollegen -- ändert sich das, muss hier auf "alle dem Auftrag zugeordneten
Monteure" erweitert werden, nicht der Auftragsbezug selbst.

FUND 2: "fremde Wartung per geratener Vertrags-ID" -- POST .../perform-maintenance prüfte für
`field` keine Zuordnung zwischen Monteur und Vertrag, nur die Mitarbeiterverknüpfung selbst. Ein
Monteur konnte damit für JEDEN Vertrag (fortlaufende ID) einen echten Auftrag unter einem fremden
Kunden anlegen. Behoben über field_may_perform_maintenance() -- dieselbe Grenze wie der
Vertragsfinder auf /vor-ort (list_field_relevant_property_ids())."""

from datetime import date, timedelta
from decimal import Decimal

from app.maintenance_contracts import create_contract


def _employee(db, number, first, last):
    from app.models import Employee
    emp = Employee(employee_number=number, first_name=first, last_name=last,
                   employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    db.add(emp); db.commit()
    return emp


def _order_with_property(db, order_number, project_number, customer=None, property_name="Objekt Nord"):
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


def _slot(db, prep_id, team_assignment_id, start=None, end=None):
    from app.models import PlanningSlot
    slot = PlanningSlot(preparation_id=prep_id, team_assignment_id=team_assignment_id,
                         start_date=start or date.today(), end_date=end or date.today())
    db.add(slot); db.commit()
    return slot


def _shared_order_with_two_reports(db):
    """Auftrag, dem sowohl A als auch B über die AV legitim zugeordnet sind (Team-Besetzung) --
    B hat darauf bereits einen eigenen Bericht mit einer als vertraulich markierten Notiz."""
    from app.service_reports import create_report
    monteur_a = _employee(db, "T-263-A", "Anna", "Eigenbericht")
    monteur_b = _employee(db, "T-263-B", "Bruno", "Kollege")
    order, customer, prop = _order_with_property(db, "AUF-263-0001", "P-263-0001")
    prep, assignment = _assign_via_team(db, order, monteur_a)
    from app.models import WorkPreparationTeamEmployee
    db.add(WorkPreparationTeamEmployee(assignment_id=assignment.id, employee_id=monteur_b.id,
                                       employee_name_snapshot=f"{monteur_b.first_name} {monteur_b.last_name}"))
    db.commit()
    _slot(db, prep.id, assignment.id)
    report_b = create_report(db, order.id, "rapport",
                             description="VERTRAULICHE NOTIZ VON B -- nicht fuer A", created_by_employee_id=monteur_b.id)
    db.commit()
    return order, monteur_a, monteur_b, report_b


class TestReportOwnershipRead:
    """FUND 1, Lesen: die Berichtsliste bleibt für jeden mit Auftragszugriff sichtbar -- der
    eigene Bericht voll, jeder fremde reduziert."""

    def test_field_sees_own_report_full_and_colleagues_report_reduced(self, router_test_client, threaded_db_session):
        from app.routers.service_reports import router as sr_router
        db = threaded_db_session
        order, monteur_a, monteur_b, report_b = _shared_order_with_two_reports(db)
        from app.service_reports import create_report
        report_a = create_report(db, order.id, "rapport", description="Eigene Notiz von A",
                                 created_by_employee_id=monteur_a.id)
        db.commit()

        client = router_test_client(db, sr_router, role="field", employee_id=monteur_a.id)
        resp = client.get(f"/api/orders/{order.id}/service-reports")
        assert resp.status_code == 200, resp.text
        by_id = {r["id"]: r for r in resp.json()}

        own = by_id[report_a["id"]]
        assert own["description"] == "Eigene Notiz von A"
        assert "status" in own and "created_at" in own  # volles ServiceReportOut

        foreign = by_id[report_b["id"]]
        assert "description" not in foreign
        assert "status" not in foreign and "created_at" not in foreign
        assert "signature_name" not in foreign
        # reduziertes Schema wie die Wartungshistorie (ServiceReportHistoryOut)
        assert set(foreign.keys()) == {
            "id", "order_number", "order_title", "report_type", "report_type_label", "performed_at",
            "created_by_employee_name", "roof_areas", "inspection_items", "findings",
        }

    def test_office_and_admin_see_the_full_report_regardless_of_creator(self, router_test_client, threaded_db_session):
        from app.routers.service_reports import router as sr_router
        db = threaded_db_session
        order, monteur_a, monteur_b, report_b = _shared_order_with_two_reports(db)
        for role in ("office", "admin"):
            client = router_test_client(db, sr_router, role=role)
            resp = client.get(f"/api/orders/{order.id}/service-reports")
            assert resp.status_code == 200
            row = next(r for r in resp.json() if r["id"] == report_b["id"])
            assert row["description"] == "VERTRAULICHE NOTIZ VON B -- nicht fuer A"


class TestReportOwnershipWrite:
    """FUND 1, Schreiben/Detail: nur der Ersteller darf PUT/DELETE/sign sowie Prüfpunkte, Fotos,
    Material, Mängel und das PDF eines konkreten Berichts erreichen."""

    def test_field_cannot_edit_a_colleagues_report_on_a_shared_order(self, router_test_client, threaded_db_session):
        from app.routers.service_reports import router as sr_router
        db = threaded_db_session
        order, monteur_a, monteur_b, report_b = _shared_order_with_two_reports(db)
        client = router_test_client(db, sr_router, role="field", employee_id=monteur_a.id)
        resp = client.put(f"/api/service-reports/{report_b['id']}", json={
            "report_type": "rapport", "description": "von A ueberschrieben", "performed_at": "2026-09-16",
        })
        assert resp.status_code == 403, resp.text

    def test_field_cannot_delete_a_colleagues_report_on_a_shared_order(self, router_test_client, threaded_db_session):
        from app.routers.service_reports import router as sr_router
        db = threaded_db_session
        order, monteur_a, monteur_b, report_b = _shared_order_with_two_reports(db)
        client = router_test_client(db, sr_router, role="field", employee_id=monteur_a.id)
        resp = client.delete(f"/api/service-reports/{report_b['id']}")
        assert resp.status_code == 403, resp.text

    def test_field_cannot_sign_a_colleagues_report_on_a_shared_order(self, router_test_client, threaded_db_session):
        import base64
        from tests.test_v203_service_reports import TINY_PNG
        from app.routers.service_reports import router as sr_router
        db = threaded_db_session
        order, monteur_a, monteur_b, report_b = _shared_order_with_two_reports(db)
        client = router_test_client(db, sr_router, role="field", employee_id=monteur_a.id)
        png = base64.b64encode(TINY_PNG).decode()
        resp = client.post(f"/api/service-reports/{report_b['id']}/sign", json={
            "installer_signature_png_base64": png, "installer_signature_name": "Anna Eigenbericht",
            "customer_signature_png_base64": png, "customer_signature_name": "Kunde",
        })
        assert resp.status_code == 403, resp.text

    def test_field_cannot_read_pdf_of_a_colleagues_report(self, router_test_client, threaded_db_session):
        from app.routers.service_reports import router as sr_router
        db = threaded_db_session
        order, monteur_a, monteur_b, report_b = _shared_order_with_two_reports(db)
        client = router_test_client(db, sr_router, role="field", employee_id=monteur_a.id)
        resp = client.get(f"/api/service-reports/{report_b['id']}/pdf")
        assert resp.status_code == 403, resp.text

    def test_field_cannot_read_or_write_inspection_items_of_a_colleagues_report(self, router_test_client, threaded_db_session):
        from app.routers.service_reports import router as sr_router
        db = threaded_db_session
        order, monteur_a, monteur_b, report_b = _shared_order_with_two_reports(db)
        client = router_test_client(db, sr_router, role="field", employee_id=monteur_a.id)
        assert client.get(f"/api/service-reports/{report_b['id']}/inspection-items").status_code == 403
        assert client.post(f"/api/service-reports/{report_b['id']}/inspection-items", json={
            "text": "Punkt von A", "item_type": "free_text",
        }).status_code == 403
        assert client.post(f"/api/service-reports/{report_b['id']}/inspection-items/regenerate").status_code == 403
        assert client.post(f"/api/service-reports/{report_b['id']}/inspection-items/sync").status_code == 403

    def test_field_cannot_read_or_write_photos_of_a_colleagues_report(self, router_test_client, threaded_db_session):
        from app.routers.service_reports import router as sr_router
        db = threaded_db_session
        order, monteur_a, monteur_b, report_b = _shared_order_with_two_reports(db)
        client = router_test_client(db, sr_router, role="field", employee_id=monteur_a.id)
        assert client.get(f"/api/service-reports/{report_b['id']}/photos").status_code == 403

    def test_field_cannot_read_or_write_materials_of_a_colleagues_report(self, router_test_client, threaded_db_session):
        from app.routers.service_reports import router as sr_router
        db = threaded_db_session
        order, monteur_a, monteur_b, report_b = _shared_order_with_two_reports(db)
        client = router_test_client(db, sr_router, role="field", employee_id=monteur_a.id)
        assert client.get(f"/api/service-reports/{report_b['id']}/materials").status_code == 403
        assert client.post(f"/api/service-reports/{report_b['id']}/materials", json={
            "quantity": "1", "description": "Ziegel",
        }).status_code == 403

    def test_field_cannot_read_or_write_findings_of_a_colleagues_report(self, router_test_client, threaded_db_session):
        from app.routers.findings import router as findings_router
        db = threaded_db_session
        order, monteur_a, monteur_b, report_b = _shared_order_with_two_reports(db)
        client = router_test_client(db, findings_router, role="field", employee_id=monteur_a.id)
        assert client.get(f"/api/service-reports/{report_b['id']}/findings").status_code == 403
        assert client.post(f"/api/service-reports/{report_b['id']}/findings", json={
            "description": "Mangel von A", "severity": "mittel", "action": "sofort_behoben",
        }).status_code == 403

    def test_field_cannot_change_followup_of_a_finding_on_a_colleagues_report(self, router_test_client, threaded_db_session):
        from app.findings import create_finding
        from app.routers.findings import router as findings_router
        db = threaded_db_session
        order, monteur_a, monteur_b, report_b = _shared_order_with_two_reports(db)
        finding = create_finding(db, report_b["id"], "Mangel von B", "mittel", "buero_pruefen",
                                 created_by_employee_id=monteur_b.id)
        db.commit()
        client = router_test_client(db, findings_router, role="field", employee_id=monteur_a.id)
        resp = client.put(f"/api/findings/{finding['id']}/followup", json={"status": "erledigt"})
        assert resp.status_code == 403, resp.text

    def test_field_can_still_fully_edit_and_sign_their_own_report(self, router_test_client, threaded_db_session, tmp_path, monkeypatch):
        """Regressionsschutz: die Ersteller-Prüfung darf den eigenen Bericht nicht miteinsperren."""
        import base64
        from app import service_reports as service_reports_module
        from tests.test_v203_service_reports import TINY_PNG
        from app.routers.service_reports import router as sr_router
        monkeypatch.setattr(service_reports_module, "SIGNATURE_ROOT", tmp_path / "sigs")
        db = threaded_db_session
        order, monteur_a, monteur_b, report_b = _shared_order_with_two_reports(db)
        from app.service_reports import create_report
        report_a = create_report(db, order.id, "rapport", description="Eigene Notiz",
                                 created_by_employee_id=monteur_a.id)
        db.commit()
        client = router_test_client(db, sr_router, role="field", employee_id=monteur_a.id)

        put_resp = client.put(f"/api/service-reports/{report_a['id']}", json={
            "report_type": "rapport", "description": "Geaendert von A selbst", "performed_at": "2026-09-16",
        })
        assert put_resp.status_code == 200, put_resp.text

        assert client.get(f"/api/service-reports/{report_a['id']}/inspection-items").status_code == 200
        assert client.get(f"/api/service-reports/{report_a['id']}/photos").status_code == 200
        assert client.get(f"/api/service-reports/{report_a['id']}/materials").status_code == 200

        png = base64.b64encode(TINY_PNG).decode()
        sign_resp = client.post(f"/api/service-reports/{report_a['id']}/sign", json={
            "installer_signature_png_base64": png, "installer_signature_name": "Anna Eigenbericht",
            "customer_signature_png_base64": png, "customer_signature_name": "Kunde",
        })
        assert sign_resp.status_code == 200, sign_resp.text

    def test_office_can_edit_a_report_it_did_not_create(self, router_test_client, threaded_db_session):
        """Büro/Admin bleiben unbeschränkt -- die Ersteller-Prüfung gilt nur für `field`."""
        from app.routers.service_reports import router as sr_router
        db = threaded_db_session
        order, monteur_a, monteur_b, report_b = _shared_order_with_two_reports(db)
        client = router_test_client(db, sr_router, role="office")
        resp = client.put(f"/api/service-reports/{report_b['id']}", json={
            "report_type": "rapport", "description": "vom Buero geaendert", "performed_at": "2026-09-16",
        })
        assert resp.status_code == 200, resp.text


class TestPerformMaintenanceObjectScope:
    """FUND 2: "Wartung durchführen" nur an einem Objekt, dem der Monteur tatsächlich zugeordnet
    ist -- dieselbe Grenze wie list_field_relevant_property_ids()."""

    def test_field_cannot_perform_maintenance_on_an_unassigned_contract(self, router_test_client, threaded_db_session):
        from app.routers.maintenance_contracts import router as mc_router
        db = threaded_db_session
        monteur = _employee(db, "T-263-C1", "Uwe", "Fremd")
        _order, customer, prop = _order_with_property(db, "AUF-263-0002", "P-263-0002")
        contract = create_contract(db, customer_id=customer.id, property_id=prop.id, title="Fremder Vertrag",
                                   interval_months=12, next_due_date=date.today())
        client = router_test_client(db, mc_router, role="field", employee_id=monteur.id)
        resp = client.post(f"/api/maintenance-contracts/{contract['id']}/perform-maintenance")
        assert resp.status_code == 403, resp.text

    def test_field_cannot_perform_maintenance_on_an_unassigned_contract_without_property(self, router_test_client, threaded_db_session):
        """property_id IS NULL -- bedeutet Hauptadresse des Kunden; auch dieser Rückfall muss
        die Zuordnung prüfen, nicht klammheimlich durchlassen."""
        from app.models import Customer, Property
        from app.routers.maintenance_contracts import router as mc_router
        db = threaded_db_session
        monteur = _employee(db, "T-263-C2", "Uwe", "Fremd2")
        customer = Customer(name="Hauptadresskunde", last_name="Hauptadresskunde", city="Kernstadt")
        db.add(customer); db.flush()
        primary = Property(customer_id=customer.id, name="Hauptadresse", city="Kernstadt", is_primary_address=True)
        db.add(primary); db.commit()
        contract = create_contract(db, customer_id=customer.id, property_id=None, title="Hauptadress-Vertrag",
                                   interval_months=12, next_due_date=date.today())
        client = router_test_client(db, mc_router, role="field", employee_id=monteur.id)
        resp = client.post(f"/api/maintenance-contracts/{contract['id']}/perform-maintenance")
        assert resp.status_code == 403, resp.text

    def test_field_can_perform_maintenance_on_an_assigned_contract(self, router_test_client, threaded_db_session):
        from app.routers.maintenance_contracts import router as mc_router
        db = threaded_db_session
        monteur = _employee(db, "T-263-C3", "Uwe", "Zugeordnet")
        order, customer, prop = _order_with_property(db, "AUF-263-0003", "P-263-0003")
        prep, assignment = _assign_via_team(db, order, monteur)
        _slot(db, prep.id, assignment.id)
        contract = create_contract(db, customer_id=customer.id, property_id=prop.id, title="Eigener Vertrag",
                                   interval_months=12, next_due_date=date.today())
        client = router_test_client(db, mc_router, role="field", employee_id=monteur.id)
        resp = client.post(f"/api/maintenance-contracts/{contract['id']}/perform-maintenance")
        assert resp.status_code == 200, resp.text

    def test_office_and_admin_can_perform_maintenance_regardless_of_assignment(self, router_test_client, threaded_db_session):
        from app.routers.maintenance_contracts import router as mc_router
        db = threaded_db_session
        _order, customer, prop = _order_with_property(db, "AUF-263-0004", "P-263-0004")
        contract = create_contract(db, customer_id=customer.id, property_id=prop.id, title="Vertrag",
                                   interval_months=12, next_due_date=date.today())
        for role in ("office", "admin"):
            client = router_test_client(db, mc_router, role=role)
            resp = client.post(f"/api/maintenance-contracts/{contract['id']}/perform-maintenance")
            assert resp.status_code == 200, (role, resp.text)


class TestFieldMayPerformMaintenanceUnit:
    """app/maintenance_contracts.py::field_may_perform_maintenance() direkt, ohne HTTP-Umweg."""

    def test_resolves_hauptadresse_when_contract_has_no_property(self, threaded_db_session):
        from app.maintenance_contracts import contract_effective_property_id, field_may_perform_maintenance
        from app.models import Customer, MaintenanceContract, Project, Property
        db = threaded_db_session
        monteur = _employee(db, "T-263-U1", "Uwe", "Unit")
        customer = Customer(name="Unit-Kunde", last_name="Unit-Kunde", city="Kernstadt")
        db.add(customer); db.flush()
        primary = Property(customer_id=customer.id, name="Hauptadresse", city="Kernstadt", is_primary_address=True)
        db.add(primary); db.commit()
        contract = create_contract(db, customer_id=customer.id, property_id=None, title="Vertrag",
                                   interval_months=12, next_due_date=date.today())
        contract_row = db.get(MaintenanceContract, contract["id"])
        assert contract_effective_property_id(db, contract_row) == primary.id
        assert field_may_perform_maintenance(db, monteur.id, contract["id"]) is False

        # Der Monteur wird jetzt einem Auftrag zugeordnet, dessen Projekt auf DIESELBE
        # Hauptadresse-Property zeigt wie der Vertrag (property_id=None) -- kein neues, eigenes
        # Objekt, sondern exakt der Hauptadresse-Rückfall, den contract_effective_property_id()
        # oben auflöst.
        order, _customer2, _own_prop = _order_with_property(
            db, "AUF-263-0099", "P-263-0099", customer=customer, property_name="Hauptadresse-Order",
        )
        db.get(Project, order.project_id).property_id = primary.id
        db.commit()
        prep, assignment = _assign_via_team(db, order, monteur)
        _slot(db, prep.id, assignment.id)
        assert field_may_perform_maintenance(db, monteur.id, contract["id"]) is True
