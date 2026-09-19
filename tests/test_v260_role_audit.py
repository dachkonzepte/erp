"""Version 1.3.51 -- Rechtekonzept, Etappe 1+2 (Fundament + Nachweis am Beispiel dreier Dateien).

Standardverweigerung statt Positivliste (siehe app/permissions.py und CLAUDE.md "Rechtekonzept"
für die volle Begründung): jeder /api/-Endpunkt MUSS eine erkennbare Rollenprüfung tragen
(Depends(require_role(...)) oder das unveränderte Depends(require_admin(...))) -- fehlt sie,
gilt der Endpunkt hier als unklassifiziert und der Test schlägt mit einer namentlichen Liste
fehl. Das IST der Mechanismus, nicht nur sein Test: ein neuer, vergessener Endpunkt fällt beim
nächsten vollständigen Testlauf auf, nicht erst irgendwann durch Zufall.

Diese Version klassifiziert bewusst nur drei Dateien (customers.py/invoices.py/reminders.py,
als Nachweis, dass der Mechanismus trägt) -- der vollständige Durchgang durch die übrigen
Router ist die nächste, separat zu bestätigende Etappe (siehe CLAUDE.md). Der Test unten ist
deshalb ABSICHTLICH so gebaut, dass er die noch unklassifizierten Endpunkte NAMENTLICH auflistet
-- das ist der Vorschlag/die Checkliste für diese nächste Etappe, kein Zufallsfund."""

import importlib
import pkgutil
from decimal import Decimal

import pytest

import app.routers as routers_package
from app.deps import require_admin
from app.models import AppUser
from app.permissions import (
    PAGE_AUDIT_EXEMPT, ROLE_ADMIN, ROLE_AUDIT_EXEMPT, ROLE_FIELD, ROLE_OFFICE_AUFTRAG,
    ROLE_OFFICE_FINANZEN, require_min_role, require_role,
)


def _iter_role_marked_dependants(dependant):
    """Geht dependant.dependencies rekursiv durch (FastAPI verschachtelt Sub-Dependencies) und
    liefert jedes _dk_roles-Attribut, das require_role()/require_admin() markiert haben."""
    for sub in dependant.dependencies:
        call = getattr(sub, "call", None)
        roles = getattr(call, "_dk_roles", None)
        if roles is not None:
            yield roles
        yield from _iter_role_marked_dependants(sub)


def _discover_routes(*, api: bool):
    """Importiert jedes Modul unter app/routers/ selbst (kein app.main -- siehe CLAUDE.md
    "Migrations-Workflow" zum Risiko, app.main in einem Test zu importieren: Base.metadata.
    create_all() liefe sonst gegen die echte, lokale DATABASE_URL) und liefert (method, path,
    route) für jede registrierte /api/-Route (api=True) bzw. jede Seiten-Route (api=False --
    alles andere, u. a. app/routers/pages.py/field_view.py, seit "Rechtekonzept" Seiten-
    Klassifizierung ebenso auditiert wie die API)."""
    found = []
    for module_info in pkgutil.iter_modules(routers_package.__path__, prefix="app.routers."):
        module = importlib.import_module(module_info.name)
        router = getattr(module, "router", None)
        if router is None:
            continue
        for route in router.routes:
            path = getattr(route, "path", "")
            if path.startswith("/api/") != api:
                continue
            for method in (route.methods or set()) - {"HEAD", "OPTIONS"}:
                found.append((method, path, route))
    return found


def _discover_api_routes():
    return _discover_routes(api=True)


def _unclassified(routes, exempt):
    unclassified = []
    for method, path, route in routes:
        if (method, path) in exempt:
            continue
        if any(True for _ in _iter_role_marked_dependants(route.dependant)):
            continue
        unclassified.append(f"{method} {path}")
    unclassified.sort()
    return unclassified


def test_all_api_routes_have_an_explicit_role_check():
    """Seit Teil B (1.3.55) bei null und damit ein HARTER Test (die xfail-Markierung aus 1.3.51
    ist entfernt): ein neuer /api/-Endpunkt ohne Depends(require_role(...))/require_admin(...)
    lässt ab jetzt den vollständigen Testlauf rot werden -- genau die gewollte
    Standardverweigerung (Regel 11 in CLAUDE.md). Wer einen Endpunkt aus strukturellen Gründen
    ohne Rollenprüfung braucht, trägt ihn mit Begründung in ROLE_AUDIT_EXEMPT ein."""
    unclassified = _unclassified(_discover_api_routes(), ROLE_AUDIT_EXEMPT)
    assert not unclassified, (
        f"{len(unclassified)} /api/-Endpunkt(e) ohne erkennbare Rollenprüfung -- Standard ist "
        f"admin-only (siehe app/permissions.py), das ist die Etappe-2/3-Checkliste, keine "
        f"Panik: \n" + "\n".join(unclassified)
    )


def test_all_page_routes_have_an_explicit_role_check():
    """Seit "Rechtekonzept", Seiten-Klassifizierung (siehe CLAUDE.md): dieselbe
    Standardverweigerung wie bei den API-Endpunkten, jetzt auch für Seiten-Routen
    (app/routers/pages.py, app/routers/field_view.py) -- eine Seite, die ein Monteur nicht
    öffnen darf, muss serverseitig sperren (Depends(require_role(...)) -> 403 ->
    access_denied.html über app/main.py's Exception-Handler), nicht nur im Sidebar-Menü
    ausgeblendet sein. Wer eine Seite aus strukturellen Gründen ohne Rollenprüfung braucht,
    trägt sie mit Begründung in PAGE_AUDIT_EXEMPT ein (app/permissions.py)."""
    unclassified = _unclassified(_discover_routes(api=False), PAGE_AUDIT_EXEMPT)
    assert not unclassified, (
        f"{len(unclassified)} Seiten-Route(n) ohne erkennbare Rollenprüfung -- Standard ist "
        f"admin-only (siehe app/permissions.py): \n" + "\n".join(unclassified)
    )


def test_require_admin_and_require_role_both_carry_the_audit_marker():
    """require_admin() (app/deps.py) und require_role() (app/permissions.py) müssen beide die
    _dk_roles-Markierung tragen -- sonst würde der Audit-Test oben jeden der bereits
    bestehenden admin-gateten Endpunkte fälschlich als unklassifiziert melden."""
    admin_dep = require_admin("x")
    assert admin_dep._dk_roles == frozenset({"admin"})
    role_dep = require_role(ROLE_ADMIN, ROLE_OFFICE_FINANZEN)
    assert role_dep._dk_roles == frozenset({"admin", "buero_finanzen"})


def test_require_min_role_carries_the_full_rank_derived_audit_marker():
    """require_min_role() (app/permissions.py, seit der Vier-Rollen-Erweiterung -- CLAUDE.md
    "Rechtekonzept" -> "Vier Rollen" -- die primäre Prüfart für die überwältigende Mehrheit der
    Endpunkte) markiert NICHT nur den übergebenen Mindestrang selbst, sondern die vollständige,
    aus ROLE_RANK abgeleitete Menge aller Rollen AB diesem Rang -- der Audit-Test oben prüft nur
    auf PRÄSENZ irgendeiner _dk_roles-Markierung, das genügt hier bereits, aber die Menge selbst
    muss trotzdem stimmen, sonst würde ein falscher Mindestrang unbemerkt bleiben."""
    auftrag_dep = require_min_role(ROLE_OFFICE_AUFTRAG)
    assert auftrag_dep._dk_roles == frozenset({"buero_auftrag", "buero_finanzen", "admin"})
    finanzen_dep = require_min_role(ROLE_OFFICE_FINANZEN)
    assert finanzen_dep._dk_roles == frozenset({"buero_finanzen", "admin"})
    field_dep = require_min_role(ROLE_FIELD)
    assert field_dep._dk_roles == frozenset({"field", "buero_auftrag", "buero_finanzen", "admin"})
    admin_dep = require_min_role(ROLE_ADMIN)
    assert admin_dep._dk_roles == frozenset({"admin"})


class TestRoleGateOnCustomersInvoicesReminders:
    """Nachweis am Beispiel: beide Bürorollen und admin dürfen weiterhin alles wie bisher (seit
    der Vier-Rollen-Erweiterung -- CLAUDE.md "Rechtekonzept" -> "Vier Rollen" -- über die
    Hierarchie: require_min_role(ROLE_OFFICE_AUFTRAG) lässt buero_finanzen automatisch mit
    durch), field wird an genau diesen drei Dateien abgelehnt (403), ohne dass Objekt-Filterung
    nötig ist -- Kunden/Rechnungen/Mahnungen sind für einen Monteur an keiner Stelle vorgesehen,
    siehe CLAUDE.md."""

    def _client(self, router_test_client, threaded_db_session, role):
        from app.routers.customers import router as customers_router
        from app.routers.invoices import router as invoices_router
        from app.routers.reminders import router as reminders_router
        return router_test_client(
            threaded_db_session, customers_router, invoices_router, reminders_router, role=role,
        )

    @pytest.mark.parametrize("role", ["admin", "buero_finanzen", "buero_auftrag"])
    def test_office_and_admin_still_reach_customers_invoices_reminders(
        self, router_test_client, threaded_db_session, role,
    ):
        client = self._client(router_test_client, threaded_db_session, role)
        assert client.get("/api/customers").status_code == 200
        assert client.get("/api/invoices").status_code == 200
        assert client.get("/api/reminders").status_code == 200

    def test_field_is_rejected_from_customers_invoices_reminders(
        self, router_test_client, threaded_db_session,
    ):
        client = self._client(router_test_client, threaded_db_session, "field")
        for path in ("/api/customers", "/api/invoices", "/api/reminders"):
            response = client.get(path)
            assert response.status_code == 403, path
            assert "detail" in response.json()


class TestRoleGateOnTheHighRiskBatch:
    """Fortsetzung des Nachweises aus 1.3.51 -- diesmal die zweite, nach Risiko geordnete
    Etappe (Finanzen/Rechnungen/Mahnwesen waren schon in 1.3.51 fertig): Kalkulation,
    Mitarbeiter, Einstellungen, Benutzer, Historie. Stichprobenhaft, nicht erschöpfend -- die
    Vollständigkeit über ALLE Endpunkte stellt test_all_api_routes_have_an_explicit_role_check
    oben sicher, hier geht es um den tatsächlichen Ablehnungsnachweis für die sensibelsten
    Fälle je Datei."""

    def test_field_gets_no_wage_data_from_the_employee_list(self, router_test_client, threaded_db_session):
        """Der ursprüngliche Fund der Suche-Bestandsaufnahme: EmployeeOut trägt
        hourly_wage/effective_hourly_wage/annual_gross_wage -- genau das darf ein Monteur nicht
        sehen. GET /api/employees bleibt für `field` seit 1.3.53 aber ERREICHBAR (statt 403) --
        service_reports.html füllt darüber sein Mitarbeiter-Auswahlfeld für die Zeitbuchung,
        siehe CLAUDE.md 'Rechtekonzept' -- liefert dafür nur EmployeeNameOut (id/first_name/
        last_name/active), kein Lohn-/Gehaltsfeld. Die übrige Verwaltung (Einzelabruf/Anlegen/
        Ändern/Sachbearbeiter-Liste) bleibt für field weiterhin gesperrt."""
        from app.employees import ensure_employee_profiles
        from app.models import Employee
        from app.routers.employees import router as employees_router
        emp = Employee(first_name="Erika", last_name="Testfrau", employee_group="angestellt",
                        hourly_wage="45", weekly_hours="40", active=True)
        threaded_db_session.add(emp); threaded_db_session.commit()
        ensure_employee_profiles(threaded_db_session)

        client = router_test_client(threaded_db_session, employees_router, role="field")
        response = client.get("/api/employees")
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 1
        assert set(rows[0].keys()) == {"id", "first_name", "last_name", "active"}

        assert client.get(f"/api/employees/{emp.id}").status_code == 403
        assert client.get("/api/employees/caseworkers").status_code == 403
        assert client.post("/api/employees", json={"first_name": "x", "last_name": "y"}).status_code == 403

    @pytest.mark.parametrize("role", ["buero_finanzen", "buero_auftrag"])
    def test_office_still_reaches_employee_wage_data(self, router_test_client, threaded_db_session, role):
        """Etappe 1 (reine Rollen-Erweiterung, noch keine Verengung -- siehe CLAUDE.md
        "Rechtekonzept" -> "Vier Rollen"): beide Bürorollen sehen hier noch dasselbe. Die
        angekündigte Verengung der Mitarbeitervergütung auf buero_finanzen ist Etappe 2 und
        macht diesen Test dann für buero_auftrag bewusst rot -- das ist der Punkt, nicht ein
        Fehler, siehe dort."""
        from app.routers.employees import router as employees_router
        client = router_test_client(threaded_db_session, employees_router, role=role)
        assert client.get("/api/employees").status_code == 200

    def test_field_is_rejected_from_calculation_settings_and_option_group_list(self, router_test_client, threaded_db_session):
        """Zwei Fälle aus settings.py in einem Test: calculation-settings ist strikt Büro/Admin,
        die LISTE aller Auswahllisten ebenso (anders als eine EINZELNE Auswahlliste nach
        Schlüssel, siehe test_field_still_reaches_a_single_option_group_by_key unten)."""
        from app.routers.settings import router as settings_router
        client = router_test_client(threaded_db_session, settings_router, role="field")
        assert client.get("/api/calculation-settings").status_code == 403
        assert client.get("/api/settings/option-groups").status_code == 403

    def test_field_still_reaches_a_single_option_group_by_key(self, router_test_client, threaded_db_session):
        """service_reports.html/time_tracking.html/roof_area.html lesen genau diesen Endpunkt
        für ganz normale, auch für einen Monteur vorgesehene Formulare (z. B. Zeitarten) --
        siehe Kommentar in app/routers/settings.py. Ein 404 (Gruppe existiert nicht in der
        leeren Testdatenbank) ist hier der Beleg dafür, dass die ROLLE nicht mehr blockiert --
        403 wäre der Regressionsfall."""
        from app.routers.settings import router as settings_router
        client = router_test_client(threaded_db_session, settings_router, role="field")
        response = client.get("/api/settings/option-groups/does-not-exist")
        assert response.status_code == 404

    def test_field_can_still_view_but_not_manage_the_company_logo(self, router_test_client, threaded_db_session):
        from app.routers.settings import router as settings_router
        client = router_test_client(threaded_db_session, settings_router, role="field")
        assert client.get("/api/settings/general/logo").status_code == 404  # kein Logo hinterlegt, aber KEIN 403
        assert client.delete("/api/settings/general/logo").status_code == 403

    def test_field_can_still_search_materials_but_gets_no_purchase_price(self, router_test_client, threaded_db_session):
        """Seit 1.3.53 behoben (vorher bekannter, offener Punkt, siehe CLAUDE.md
        'Rechtekonzept'): GET /api/materials bleibt für Monteure erreichbar (Materialerfassung
        am Einsatzbericht), liefert ihnen aber MaterialSearchOut statt MaterialCatalogOut --
        kein purchase_price/price_basis/catalog_id/source in der Antwort. Verwaltung
        (POST/PUT/move/copy) bleibt für field weiterhin gesperrt."""
        from app.materials import create_manual_material
        from app.routers.materials import router as materials_router
        create_manual_material(threaded_db_session, "Dachziegel rot", "Stk", Decimal("12.50"))

        field_client = router_test_client(threaded_db_session, materials_router, role="field")
        field_response = field_client.get("/api/materials")
        assert field_response.status_code == 200
        field_rows = field_response.json()
        assert len(field_rows) == 1
        assert set(field_rows[0].keys()) == {"id", "article_number", "name", "unit"}
        assert field_client.post("/api/materials", json={"name": "x", "unit": "Stk", "purchase_price": "1"}).status_code == 403

        office_client = router_test_client(threaded_db_session, materials_router, role="buero_auftrag")
        office_rows = office_client.get("/api/materials").json()
        assert Decimal(office_rows[0]["purchase_price"]) == Decimal("12.50")

    def test_field_is_rejected_from_the_user_list_and_audit_log(self, router_test_client, threaded_db_session):
        from app.routers.audit import router as audit_router
        from app.routers.users import router as users_router
        client = router_test_client(threaded_db_session, users_router, audit_router, role="field")
        assert client.get("/api/users").status_code == 403
        assert client.get("/api/audit-logs").status_code == 403

    def test_field_is_rejected_from_tasks_and_task_columns(self, router_test_client, threaded_db_session):
        """Aufgaben bleiben für `field` vollständig gesperrt (siehe CLAUDE.md 'Aufgaben') --
        weder die Aufgabenliste noch die Kanban-Spaltenliste des Boards sind erreichbar."""
        from app.routers.task_columns import router as task_columns_router
        from app.routers.tasks import router as tasks_router
        client = router_test_client(threaded_db_session, tasks_router, task_columns_router, role="field")
        assert client.get("/api/tasks").status_code == 403
        assert client.get("/api/task-columns").status_code == 403
        assert client.get("/api/task-settings").status_code == 403

    def test_office_and_admin_still_reach_tasks_and_task_columns(self, router_test_client, threaded_db_session):
        """GET /api/tasks verlangt für einen Nicht-Admin zusätzlich eine Employee-Verknüpfung
        (bereits bestehende Eigentümer-Filterung, siehe CLAUDE.md 'Aufgaben') -- office bekommt
        deshalb hier eine echte employee_id, damit dieser Test nur die neue Rollenprüfung
        belegt, nicht die davon unabhängige, schon vorher bestehende 403-Bedingung."""
        from app.models import Employee
        from app.routers.task_columns import router as task_columns_router
        from app.routers.tasks import router as tasks_router
        emp = Employee(employee_number="T-260", first_name="Erika", last_name="Testfrau",
                        employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
        threaded_db_session.add(emp); threaded_db_session.commit()
        for role in ("admin", "buero_finanzen", "buero_auftrag"):
            client = router_test_client(threaded_db_session, tasks_router, task_columns_router, role=role, employee_id=emp.id)
            assert client.get("/api/tasks").status_code == 200, role
            assert client.get("/api/task-columns").status_code == 200, role


class TestRoleGateOnTheRemainingBueroOnlyFiles:
    """Nachweis für Teil A der Rest-Etappe (siehe CLAUDE.md 'Rechtekonzept'): reine Büro-/Admin-
    Dateien ohne Monteur-Bezug (geprüft: kein Endpunkt wird von service_reports.html/vor_ort.html/
    _mobile_header.html aufgerufen) -- stichprobenhaft je Datei, nicht erschöpfend, die
    Vollständigkeit sichert weiterhin test_all_api_routes_have_an_explicit_role_check oben."""

    def test_field_is_rejected_from_quotes_planning_and_maintenance_contracts(self, router_test_client, threaded_db_session):
        from app.routers.maintenance_contracts import router as mc_router
        from app.routers.planning import router as planning_router
        from app.routers.quotes import router as quotes_router
        client = router_test_client(threaded_db_session, quotes_router, planning_router, mc_router, role="field")
        assert client.get("/api/quotes").status_code == 403
        assert client.get("/api/planning/holidays").status_code == 403
        assert client.get("/api/maintenance-contracts").status_code == 403

    def test_field_is_rejected_from_projects_resource_planning_and_roof_areas(self, router_test_client, threaded_db_session):
        from app.routers.projects import router as projects_router
        from app.routers.resource_planning import router as rp_router
        from app.routers.roof_areas import router as roof_areas_router
        client = router_test_client(threaded_db_session, projects_router, rp_router, roof_areas_router, role="field")
        assert client.get("/api/projects").status_code == 403
        assert client.get("/api/teams").status_code == 403
        assert client.get("/api/suppliers").status_code == 403
        assert client.get("/api/resources").status_code == 403
        assert client.get("/api/roof-areas?property_id=1").status_code == 403
        assert client.get("/api/roof-component-types").status_code == 403

    def test_field_is_rejected_from_properties_inquiries_and_documents(self, router_test_client, threaded_db_session):
        from app.routers.customer_documents import router as cust_docs_router
        from app.routers.inquiries import router as inquiries_router
        from app.routers.project_documents import router as proj_docs_router
        from app.routers.properties import router as properties_router
        client = router_test_client(
            threaded_db_session, properties_router, inquiries_router, cust_docs_router, proj_docs_router, role="field",
        )
        assert client.get("/api/properties").status_code == 403
        assert client.get("/api/inquiries").status_code == 403
        assert client.get("/api/customer-documents/1/view").status_code == 403
        assert client.get("/api/project-documents/1/view").status_code == 403

    def test_field_is_rejected_from_quick_service_orders(self, router_test_client, threaded_db_session):
        from app.routers.quick_service_orders import router as qso_router
        client = router_test_client(threaded_db_session, qso_router, role="field")
        response = client.post("/api/quick-service-orders", json={
            "customer_id": 1, "order_type": "reparatur", "title": "x",
        })
        assert response.status_code == 403

    def test_office_and_admin_still_reach_the_buero_only_files(self, router_test_client, threaded_db_session):
        from app.routers.quotes import router as quotes_router
        for role in ("admin", "buero_finanzen", "buero_auftrag"):
            client = router_test_client(threaded_db_session, quotes_router, role=role)
            assert client.get("/api/quotes").status_code == 200, role

    def test_absence_requests_stay_open_to_field_as_self_service(self, router_test_client, threaded_db_session):
        """Anders als die übrigen Dateien dieser Etappe: Abwesenheitsanträge stellen/ansehen/
        zurückziehen ist Selbstbedienung für JEDE Rolle (siehe CLAUDE.md 'Rechtekonzept') -- nur
        die Freigabe (review) bleibt admin-only über ihre eigene, unveränderte require_admin()."""
        from app.models import Employee
        from app.routers.absence_requests import router as absence_router
        emp = Employee(employee_number="T-260b", first_name="Otto", last_name="Testmann",
                        employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
        threaded_db_session.add(emp); threaded_db_session.commit()
        client = router_test_client(threaded_db_session, absence_router, role="field", employee_id=emp.id)
        assert client.get("/api/absence-requests").status_code == 200
        created = client.post("/api/absence-requests", json={
            "employee_id": emp.id, "absence_type": "urlaub", "absence_category": "urlaub",
            "start_date": "2026-10-01", "end_date": "2026-10-02",
        })
        assert created.status_code == 200, created.text
        assert client.post(f"/api/absence-requests/{created.json()['id']}/review", json={"decision": "genehmigt"}).status_code == 403

    def test_dashboard_and_modules_stay_open_to_every_role(self, router_test_client, threaded_db_session):
        """Eigenes Dashboard-Layout (rein per user.id isoliert) und der Modul-Ein/Aus-Zustand
        (nicht-sensible Konfiguration, von jeder Seite clientseitig gebraucht) sind für jede
        Rolle lesbar -- siehe CLAUDE.md 'Rechtekonzept'."""
        from app.routers.dashboard import router as dashboard_router
        from app.routers.modules import router as modules_router
        client = router_test_client(threaded_db_session, dashboard_router, modules_router, role="field")
        assert client.get("/api/dashboard/widgets").status_code == 200
        assert client.get("/api/modules").status_code == 200
        assert client.put("/api/modules/wartungen", json={"enabled": True}).status_code == 403

    def test_work_preparation_my_tasks_widget_stays_open_but_editing_does_not(self, router_test_client, threaded_db_session):
        """Dasselbe Selbstbedienungs-Muster wie bei Abwesenheitsanträgen: GET /api/work-
        preparation/tasks ("Meine Aufgaben"-Widget) bleibt für field offen, die eigentliche
        AV-Bearbeitung (hier: eine Mitarbeiterzuordnung anlegen) nicht. Braucht eine echte
        employee_id -- sonst lehnt die Funktion selbst (nicht die Rollenprüfung) mit 403 ab,
        weil ein Nicht-Admin ohne Mitarbeiterverknüpfung keine eigenen Aufgaben haben kann."""
        from app.models import Employee
        from app.routers.work_preparation import router as wp_router
        emp = Employee(employee_number="T-260c", first_name="Klaus", last_name="Testig",
                        employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
        threaded_db_session.add(emp); threaded_db_session.commit()
        client = router_test_client(threaded_db_session, wp_router, role="field", employee_id=emp.id)
        assert client.get("/api/work-preparation/tasks").status_code == 200
        assert client.post("/api/orders/1/work-preparation/employees", json={"employee_id": 1}).status_code == 403


class TestObjectFilteringForFieldTeilB:
    """Nachweis für Teil B (Rechtekonzept, Etappe 3 -- siehe CLAUDE.md): Aufträge, Einsatzberichte,
    Mängel, Zeiterfassung, Prüfvorlagen. Kern ist app/orders.py::field_may_access_order(), die
    EINE Definition, wann ein Monteur einen Auftrag sehen darf -- hier je Weg einzeln belegt und
    über die echten Routen (403 vs. 200) an Auftrag, Bericht, Mangel und Zeitbuchung geprüft."""

    @staticmethod
    def _employee(db, number, first, last):
        from app.models import Employee
        emp = Employee(employee_number=number, first_name=first, last_name=last,
                       employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
        db.add(emp); db.commit()
        return emp

    @staticmethod
    def _order(db, order_number, project_number, property_id=None, customer=None):
        """Muster tests/test_v261_permissions_foundation.py::_make_order_with_property() plus eine
        LV-Position (Muster make_order_with_item() in test_v133_invoices.py) -- die Position
        braucht es, um die preisfreie Antwort für `field` an einer echten Zeile zu belegen."""
        from app.models import Customer, Order, OrderItem, Project, Property
        from app.project_pipeline_columns import default_pipeline_column_id
        if customer is None:
            customer = Customer(name="Testkunde", last_name="Testkunde")
            db.add(customer); db.flush()
        if property_id is None:
            prop = Property(customer_id=customer.id, name="Objekt Nord", street="Teststr. 1", city="Teststadt",
                            notes="Büro-interner Vermerk, nicht für den Monteur")
            db.add(prop); db.flush()
            property_id = prop.id
        project = Project(project_number=project_number, name="Testprojekt", customer_id=customer.id, property_id=property_id, pipeline_column_id=default_pipeline_column_id(db))
        db.add(project); db.flush()
        # source_quote_id ist UNIQUE auf orders -- aus der Nummer abgeleitet, damit mehrere
        # Aufträge je Test nebeneinander existieren können (kein echter Quote-Datensatz nötig,
        # SQLite prüft Fremdschlüssel in dieser Testkonfiguration nicht).
        order = Order(order_number=order_number, project_id=project.id,
                      source_quote_id=int(order_number.rsplit("-", 1)[-1]),
                      quote_number_snapshot=f"A-{order_number}", title="Testauftrag", customer_name=customer.name,
                      customer_number="K-0001", property_name="Objekt Nord")
        db.add(order); db.flush()
        db.add(OrderItem(order_id=order.id, sort_order=10, position_number="1", short_text="Dacheindeckung",
                         quantity=Decimal("100"), unit="m²", unit_price=Decimal("50")))
        db.commit()
        return order, customer, property_id

    @staticmethod
    def _assign_individually(db, order, emp):
        from app.models import WorkPreparationEmployee
        from app.work_preparation import ensure_preparation
        prep = ensure_preparation(db, order.id)
        row = WorkPreparationEmployee(preparation_id=prep.id, employee_id=emp.id)
        db.add(row); db.commit()
        return row

    @staticmethod
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
        return assignment

    def test_field_may_access_order_knows_exactly_three_paths(self, threaded_db_session):
        """Weg 1 Team-Besetzung an der AV, Weg 2 Einzelzuweisung an der AV, Weg 3 eigener Bericht --
        jeweils nur für den betroffenen Auftrag; und die Zeiterfassung (employee_assigned_order_ids)
        liest seit Teil B dieselbe Definition (Weg 1+2), keine zweite."""
        from app.orders import employee_assigned_order_ids, field_may_access_order
        from app.service_reports import create_report
        from app.time_tracking import employee_assigned_order_ids as via_time_tracking
        db = threaded_db_session
        alone = self._employee(db, "T-B1", "Anna", "Allein")
        single = self._employee(db, "T-B2", "Ede", "Einzeln")
        teamed = self._employee(db, "T-B3", "Tom", "Team")
        writer = self._employee(db, "T-B4", "Willi", "Bericht")
        order_a, customer, prop = self._order(db, "AUF-B-0001", "P-B-0001")
        order_b, _, _ = self._order(db, "AUF-B-0002", "P-B-0002", property_id=prop, customer=customer)
        order_c, _, _ = self._order(db, "AUF-B-0003", "P-B-0003", property_id=prop, customer=customer)
        self._assign_individually(db, order_a, single)
        self._assign_via_team(db, order_b, teamed)
        create_report(db, order_c.id, "rapport", created_by_employee_id=writer.id)

        assert field_may_access_order(db, single.id, order_a.id)
        assert field_may_access_order(db, teamed.id, order_b.id)
        assert field_may_access_order(db, writer.id, order_c.id)
        assert not field_may_access_order(db, single.id, order_b.id)
        assert not field_may_access_order(db, teamed.id, order_c.id)
        assert not field_may_access_order(db, writer.id, order_a.id)
        assert not any(field_may_access_order(db, alone.id, o.id) for o in (order_a, order_b, order_c))

        assert employee_assigned_order_ids(db, single.id) == {order_a.id}
        assert employee_assigned_order_ids(db, teamed.id) == {order_b.id}
        assert via_time_tracking(db, teamed.id) == {order_b.id}
        assert via_time_tracking(db, writer.id) == set()  # Weg 3 ist bewusst KEINE Zeiterfassungs-Zuordnung

    def test_field_gets_only_assigned_orders_and_no_prices(self, router_test_client, threaded_db_session):
        from app.routers.orders import router as orders_router
        db = threaded_db_session
        monteur = self._employee(db, "T-B5", "Max", "Monteur")
        mine, customer, prop = self._order(db, "AUF-B-0010", "P-B-0010")
        foreign, _, _ = self._order(db, "AUF-B-0011", "P-B-0011", property_id=prop, customer=customer)
        self._assign_individually(db, mine, monteur)
        field = router_test_client(db, orders_router, role="field", employee_id=monteur.id)

        response = field.get(f"/api/orders/{mine.id}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) == {"id", "order_number", "customer_name", "items"}
        assert set(body["items"][0]) == {"id", "position_number", "gaeb_oz", "short_text", "unit"}

        assert field.get(f"/api/orders/{foreign.id}").status_code == 403
        assert field.get("/api/orders/999999").status_code == 403  # fremd und nicht existent sehen gleich aus
        assert field.get("/api/orders").status_code == 403
        assert field.get(f"/api/orders/{mine.id}/pdf").status_code == 403
        assert field.get(f"/api/orders/{mine.id}/revisions").status_code == 403
        assert field.post(f"/api/orders/{mine.id}/revisions", json={"reason": "x"}).status_code == 403

        office = router_test_client(db, orders_router, role="buero_auftrag")
        full = office.get(f"/api/orders/{foreign.id}").json()
        assert "net_total" in full and "unit_price" in full["items"][0]
        # ein field-Konto ohne Mitarbeiterverknüpfung kann keinem Auftrag zugeordnet sein
        unlinked = router_test_client(db, orders_router, role="field")
        assert unlinked.get(f"/api/orders/{mine.id}").status_code == 403

    def test_report_and_finding_endpoints_follow_the_same_order_access(self, router_test_client, threaded_db_session):
        from app.routers.findings import router as findings_router
        from app.routers.inspection_templates import router as templates_router
        from app.routers.service_reports import router as sr_router
        from app.service_reports import create_report
        db = threaded_db_session
        monteur = self._employee(db, "T-B6", "Kai", "Kolonne")
        mine, customer, prop = self._order(db, "AUF-B-0020", "P-B-0020")
        foreign, _, _ = self._order(db, "AUF-B-0021", "P-B-0021", property_id=prop, customer=customer)
        self._assign_via_team(db, mine, monteur)
        fid = create_report(db, foreign.id, "rapport")["id"]
        field = router_test_client(db, sr_router, findings_router, templates_router, role="field", employee_id=monteur.id)
        update = {"report_type": "rapport", "performed_at": "2026-09-14"}

        assert field.get(f"/api/orders/{mine.id}/service-reports").status_code == 200
        assert field.get(f"/api/orders/{mine.id}/property").status_code == 200
        assert field.get(f"/api/orders/{mine.id}/roof-areas").status_code == 200
        created = field.post(f"/api/orders/{mine.id}/service-reports", json={"report_type": "rapport"})
        assert created.status_code == 200, created.text
        report_id = created.json()["id"]
        for suffix in ("inspection-items", "findings", "materials", "photos"):
            assert field.get(f"/api/service-reports/{report_id}/{suffix}").status_code == 200, suffix
        assert field.put(f"/api/service-reports/{report_id}", json=update).status_code == 200
        assert field.get("/api/inspection-templates").status_code == 200

        assert field.get(f"/api/orders/{foreign.id}/service-reports").status_code == 403
        assert field.get(f"/api/orders/{foreign.id}/property").status_code == 403
        assert field.post(f"/api/orders/{foreign.id}/service-reports", json={"report_type": "rapport"}).status_code == 403
        for suffix in ("inspection-items", "findings", "materials", "photos", "pdf"):
            assert field.get(f"/api/service-reports/{fid}/{suffix}").status_code == 403, suffix
        assert field.put(f"/api/service-reports/{fid}", json=update).status_code == 403
        assert field.delete(f"/api/service-reports/{fid}").status_code == 403
        assert field.post(f"/api/service-reports/{fid}/inspection-items/sync").status_code == 403

        assert field.get(f"/api/orders/{mine.id}/materials").status_code == 403
        assert field.get("/api/findings").status_code == 403
        assert field.get("/api/roof-components/1/findings").status_code == 403
        assert field.post("/api/inspection-templates", json={"label": "x"}).status_code == 403
        assert field.get("/api/roof-type-template-defaults").status_code == 403

        office = router_test_client(db, sr_router, findings_router, role="buero_auftrag")
        assert office.get(f"/api/orders/{foreign.id}/service-reports").status_code == 200
        assert office.get(f"/api/service-reports/{fid}/findings").status_code == 200
        assert office.get(f"/api/orders/{foreign.id}/materials").status_code == 200

    def test_own_draft_report_survives_being_taken_off_the_planning(self, router_test_client, threaded_db_session):
        """Weg 3 über die echte Route: nimmt das Büro den Monteur wieder aus der AV, bleibt sein
        begonnener Bericht erreichbar (sonst zeigte /vor-ort den Entwurf, die Berichtsseite
        aber 403) -- ein nie zugeordneter Kollege bleibt draußen."""
        from app.routers.service_reports import router as sr_router
        db = threaded_db_session
        monteur = self._employee(db, "T-B7", "Rita", "Umgeplant")
        colleague = self._employee(db, "T-B8", "Carl", "Kollege")
        order, _, _ = self._order(db, "AUF-B-0030", "P-B-0030")
        assignment = self._assign_individually(db, order, monteur)
        field = router_test_client(db, sr_router, role="field", employee_id=monteur.id)
        created = field.post(f"/api/orders/{order.id}/service-reports", json={"report_type": "rapport"})
        assert created.status_code == 200, created.text
        assert created.json()["created_by_employee_id"] == monteur.id

        db.delete(assignment); db.commit()
        assert field.get(f"/api/orders/{order.id}/service-reports").status_code == 200
        response = field.put(f"/api/service-reports/{created.json()['id']}",
                             json={"report_type": "rapport", "performed_at": "2026-09-14", "description": "Nachtrag"})
        assert response.status_code == 200, response.text
        other = router_test_client(db, sr_router, role="field", employee_id=colleague.id)
        assert other.get(f"/api/orders/{order.id}/service-reports").status_code == 403

    def test_maintenance_history_carries_no_prices_purchase_values_or_customer_notes(self, router_test_client, threaded_db_session):
        """Die Wartungshistorie zeigt einem Monteur bewusst frühere Berichte ANDERER Aufträge
        desselben Objekts -- dasselbe Muster wie bei purchase_price geprüft: kein Schlüssel der
        Antwort darf Preis/Einkauf/Vergütung/Kundennotiz transportieren, auch nicht verschachtelt."""
        from app.findings import create_finding
        from app.materials import create_manual_material
        from app.models import ServiceReport
        from app.routers.service_reports import router as sr_router
        from app.service_reports import add_inspection_item, add_material, create_report, update_inspection_item
        db = threaded_db_session
        monteur = self._employee(db, "T-B9", "Hans", "Historie")
        earlier, customer, prop = self._order(db, "AUF-B-0040", "P-B-0040")
        current, _, _ = self._order(db, "AUF-B-0041", "P-B-0041", property_id=prop, customer=customer)
        self._assign_individually(db, current, monteur)
        old_id = create_report(db, earlier.id, "wartung", description="Frühjahrswartung -- Beschreibungstext")["id"]
        material = create_manual_material(db, name="Dachziegel", unit="Stk", purchase_price=Decimal("12.50"))
        add_material(db, old_id, material_id=material.id, quantity=Decimal("2"))
        item = add_inspection_item(db, old_id, "Gully Nordost", "ja_nein", group_name="Entwässerung")
        update_inspection_item(db, item["id"], {"result": "nok", "notes": "Laub, gereinigt"})
        create_finding(db, old_id, "Gully verstopft", "mittel", "sofort_behoben", inspection_item_id=item["id"])
        db.get(ServiceReport, old_id).status = "unterschrieben"; db.commit()

        field = router_test_client(db, sr_router, role="field", employee_id=monteur.id)
        response = field.get(f"/api/orders/{current.id}/property-service-reports")
        assert response.status_code == 200, response.text
        history = response.json()
        assert [r["id"] for r in history] == [old_id]
        # Reduziertes Modell (seit 1.3.56): Datum, Berichtstyp, Monteur, Prüfergebnisse, Mängel mit
        # Status -- kein Beschreibungstext, kein Material, keine Unterschrifts-/Vertrags-/Kundenfelder.
        entry = history[0]
        assert set(entry) == {
            "id", "order_number", "order_title", "report_type", "report_type_label", "performed_at",
            "created_by_employee_name", "roof_areas", "inspection_items", "findings",
        }
        assert [(i["text"], i["result"], i["notes"]) for i in entry["inspection_items"]] == [("Gully Nordost", "nok", "Laub, gereinigt")]
        assert [f["description"] for f in entry["findings"]] == ["Gully verstopft"]
        assert set(entry["findings"][0]) == {
            "id", "description", "severity", "severity_label", "action", "action_label",
            "status", "status_label", "roof_component_name", "resubmission_date", "photo_count",
        }
        # Büro bekommt unverändert das volle Modell samt Beschreibungstext, ohne die Inline-Ergebnisse
        office = router_test_client(db, sr_router, role="buero_auftrag")
        full = office.get(f"/api/orders/{current.id}/property-service-reports").json()[0]
        assert full["description"] == "Frühjahrswartung -- Beschreibungstext"
        assert "inspection_items" not in full and "status" in full

        def keys(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    yield key
                    yield from keys(value)
            elif isinstance(obj, list):
                for value in obj:
                    yield from keys(value)
        forbidden = ("price", "preis", "purchase", "einkauf", "wage", "lohn", "gehalt", "cost", "kosten",
                     "customer_note", "property_note")
        offending = sorted({k for k in keys(history) if any(f in k.lower() for f in forbidden)})
        assert offending == [], offending

    def test_field_sees_and_edits_only_own_time_entries_even_filtered_by_order(self, router_test_client, threaded_db_session):
        """Anmerkung 3 der Teil-B-Vorgabe: ?order_id=... liefert einem Monteur NICHT die Buchungen
        der Kollegen -- get_time_entries() setzt employee_id für jeden Nicht-Admin auf die eigene
        Person, list_entries() verknüpft beide Filter mit UND. Fremde Zeilen sind weder änderbar
        noch löschbar, und Buchen unter fremdem Namen wird abgelehnt."""
        from datetime import date
        from app.routers.time_tracking import router as tt_router
        from app.time_tracking import create_manual_entry
        db = threaded_db_session
        me = self._employee(db, "T-B10", "Ich", "Selbst")
        colleague = self._employee(db, "T-B11", "Du", "Kollege")
        order, _, _ = self._order(db, "AUF-B-0050", "P-B-0050")
        mine = create_manual_entry(db, employee_id=me.id, order_id=order.id, work_date=date(2026, 9, 14), hours=Decimal("2"))
        theirs = create_manual_entry(db, employee_id=colleague.id, order_id=order.id, work_date=date(2026, 9, 14), hours=Decimal("3"))
        field = router_test_client(db, tt_router, role="field", employee_id=me.id)

        rows = field.get(f"/api/time-entries?order_id={order.id}").json()
        assert [r["id"] for r in rows] == [mine.id]
        rows = field.get(f"/api/time-entries?order_id={order.id}&employee_id={colleague.id}").json()
        assert [r["id"] for r in rows] == [mine.id]
        assert field.delete(f"/api/time-entries/{theirs.id}").status_code == 403
        assert field.post("/api/time-entries", json={
            "employee_id": colleague.id, "order_id": order.id, "work_date": "2026-09-14", "hours": 1,
        }).status_code == 403
        assert field.get("/api/time-tracking/context").status_code == 200
        assert field.get("/api/time-tracking/settings").status_code == 200

        admin = router_test_client(db, tt_router, role="admin")
        assert {r["id"] for r in admin.get(f"/api/time-entries?order_id={order.id}").json()} == {mine.id, theirs.id}
        # Büro sieht die Buchungen aller (seit 1.3.56, Betreiberentscheidung) -- es rechnet sie ab;
        # auch ein Büro-Konto ohne Mitarbeiterverknüpfung, das vorher 403 bekam.
        office = router_test_client(db, tt_router, role="buero_auftrag")
        assert {r["id"] for r in office.get(f"/api/time-entries?order_id={order.id}").json()} == {mine.id, theirs.id}
        unlinked = router_test_client(db, tt_router, role="field")
        assert unlinked.get("/api/time-entries").status_code == 403

    def test_field_can_start_an_unplanned_maintenance_visit_and_sign_it(
        self, router_test_client, threaded_db_session, tmp_path, monkeypatch,
    ):
        """Betreibervorgabe (1.3.56): ein Monteur muss vor Ort eine ungeplante Wartung starten
        können. Der vorbereitete Bericht trägt ihn als Ersteller -- sein Zugriffsweg auf den neuen
        Auftrag, eine Plantafel-Zuordnung gibt es dafür nicht. Die Vertragsdaten selbst bleiben
        Büro. Und die Unterschrift läuft für ihn bis zum Ende durch: "Rechnung erstellen"-Aufgabe
        und Fortschreibung der Vertragsfälligkeit sind reine In-Process-Aufrufe ohne Rollenprüfung
        (sign_report() -> create_task()/MaintenanceContract, keine Depends(...)-Kette dahinter).

        Seit dem Fund "fremde Wartung per geratener Vertrags-ID" (1.3.59, siehe CLAUDE.md
        "Rechtekonzept" -> "Vertragsfinder auf /vor-ort") setzt "Wartung durchführen" für `field`
        zusätzlich voraus, dass der Monteur dem Objekt des Vertrags tatsächlich zugeordnet ist --
        hier über eine Team-Besetzung an der AV mit einem PlanningSlot im Zeitfenster, dieselbe
        Grenze wie list_field_relevant_property_ids()."""
        import base64
        from datetime import date, timedelta
        from sqlalchemy import select
        from app import service_reports as service_reports_module
        from app.maintenance_contracts import create_contract
        from app.models import MaintenanceContract, PlanningSlot, ServiceReport, Task
        from app.routers.maintenance_contracts import router as mc_router
        from app.routers.service_reports import router as sr_router
        from tests.test_v203_service_reports import TINY_PNG
        monkeypatch.setattr(service_reports_module, "SIGNATURE_ROOT", tmp_path / "sigs")
        db = threaded_db_session
        monteur = self._employee(db, "T-B12", "Uwe", "Ungeplant")
        order, customer, prop = self._order(db, "AUF-B-0060", "P-B-0060")
        contract = create_contract(db, customer_id=customer.id, property_id=prop, title="Jahreswartung",
                                   interval_months=12, next_due_date=date(2026, 10, 1))
        assignment = self._assign_via_team(db, order, monteur)
        db.add(PlanningSlot(preparation_id=assignment.preparation_id, team_assignment_id=assignment.id,
                            start_date=date.today() - timedelta(days=1), end_date=date.today() + timedelta(days=1)))
        db.commit()
        field = router_test_client(db, mc_router, sr_router, role="field", employee_id=monteur.id)
        assert field.get(f"/api/maintenance-contracts/{contract['id']}").status_code == 403

        started = field.post(f"/api/maintenance-contracts/{contract['id']}/perform-maintenance")
        assert started.status_code == 200, started.text
        report_id, order_id = started.json()["report_id"], started.json()["order_id"]
        assert db.get(ServiceReport, report_id).created_by_employee_id == monteur.id
        assert field.get(f"/api/orders/{order_id}/service-reports").status_code == 200  # Weg "eigener Bericht"

        png = base64.b64encode(TINY_PNG).decode()
        signed = field.post(f"/api/service-reports/{report_id}/sign", json={
            "installer_signature_png_base64": png, "installer_signature_name": "Uwe Ungeplant",
            "customer_signature_png_base64": png, "customer_signature_name": "Kunde vor Ort",
        })
        assert signed.status_code == 200, signed.text
        assert signed.json()["status"] == "unterschrieben"
        assert db.get(MaintenanceContract, contract["id"]).next_due_date == date(2027, 10, 1)
        tasks = db.scalars(select(Task).where(Task.source_module == "wartungsbericht")).all()
        assert [t.source_url for t in tasks] == [f"/orders/{order_id}"]

        # ohne Mitarbeiterverknüpfung kein Start -- der Bericht wäre für niemanden erreichbar
        unlinked = router_test_client(db, mc_router, role="field")
        assert unlinked.post(f"/api/maintenance-contracts/{contract['id']}/perform-maintenance").status_code == 403


class TestPageRouteClassification:
    """Seit "Rechtekonzept", Seiten-Klassifizierung (siehe CLAUDE.md): dieselbe Standard-
    verweigerung wie bei der API, jetzt für Seiten-Routen. Vollständigkeit sichert
    test_all_page_routes_have_an_explicit_role_check() oben -- hier stichprobenhaft belegt,
    dass die Rollen dabei auch tatsächlich RICHTIG zugeordnet wurden (ein Endpunkt könnte
    _dk_roles tragen und trotzdem die falsche Rollenmenge haben, das würde der Audit-Test
    allein nicht auffangen)."""

    def test_field_reaches_only_the_seven_pages_it_needs(self, router_test_client, threaded_db_session):
        """Seit 1.3.61: /vor-ort ist zu /mobil geworden (die alte URL entfällt ersatzlos, siehe
        CLAUDE.md "Monteursansicht: Umbenennung zu /mobil"), dazu die fünfte Seite
        /mobil/stundenzettel (Punkt 4 "Stundenzettel"). Seit "Dateiablage je Objekt" eine sechste:
        /mobil/objekt/{property_id}. Seit Betriebsmittelverwaltung Stufe 2 eine siebte:
        /betriebsmittel/{asset_id} -- Ziel des QR-Codes auf dem Etikett, das jeden erreicht, nicht
        nur Büro/Admin (die Seite rendert für `field` aber die reduzierte
        operational_asset_field.html, siehe operational_asset_page()). "/" ist für field seit
        Punkt 2 ("Startseite für Monteure") kein 403 mehr, sondern ein 302 auf /mobil -- die Rolle
        entscheidet das Ziel, nicht ob der Weg gesperrt ist."""
        from app.routers.pages import router as pages_router
        db = threaded_db_session
        field = router_test_client(db, pages_router, role="field")
        for path in ("/account", "/mobil", "/mobil/stundenzettel", "/mobil/objekt/1", "/time-tracking", "/orders/1/service-reports", "/betriebsmittel/1"):
            assert field.get(path, follow_redirects=False).status_code == 200, path
        # /vor-ort entfällt ersatzlos -- keine Route mehr registriert, 404 statt 403/200.
        assert field.get("/vor-ort", follow_redirects=False).status_code == 404
        # "/" leitet auf die eigene Startseite weiter, statt zu sperren.
        root = field.get("/", follow_redirects=False)
        assert root.status_code == 302
        assert root.headers["location"] == "/mobil"
        for path in (
            "/tasks", "/leistungskatalog", "/maintenance-contracts", "/maintenance-contracts/1",
            "/projects", "/planning", "/projects/new", "/projects/1", "/quotes/new", "/services/new",
            "/services/1/edit", "/master-data", "/master-data/teams/new", "/master-data/teams/1/edit",
            "/quotes/1/edit", "/orders/1", "/invoices/1", "/finanzen", "/mahnwesen", "/changelog",
            "/orders/1/work-preparation", "/roof-areas/1", "/properties/1", "/findings",
            "/inspection-templates", "/inspection-templates/1", "/inquiries", "/customers/1", "/settings",
            "/history",
        ):
            assert field.get(path, follow_redirects=False).status_code == 403, path

    def test_office_and_admin_reach_the_buero_pages_field_is_blocked_from(self, router_test_client, threaded_db_session):
        from app.routers.pages import router as pages_router
        db = threaded_db_session
        for role in ("buero_finanzen", "buero_auftrag", "admin"):
            client = router_test_client(db, pages_router, role=role)
            assert client.get("/", follow_redirects=False).status_code == 200, role
            assert client.get("/tasks", follow_redirects=False).status_code == 200, role
            assert client.get("/customers/1", follow_redirects=False).status_code == 200, role
        # admin- statt require_role(...)-gated (unverändert seit vor dem Rechtekonzept) -- Etappe
        # 1 verschiebt time-backoffice/address-import noch nicht, das ist Etappe 2 (siehe CLAUDE.md).
        admin = router_test_client(db, pages_router, role="admin")
        assert admin.get("/address-import", follow_redirects=False).status_code == 200
        office = router_test_client(db, pages_router, role="buero_auftrag")
        assert office.get("/address-import", follow_redirects=False).status_code == 403

    def test_users_page_is_bootstrap_exempt_then_buero_only(self, router_test_client, threaded_db_session):
        """router_test_client() injiziert den angemeldeten Benutzer direkt in request.state,
        ohne eine echte AppUser-Zeile anzulegen -- users_exist(db) bleibt deshalb False, bis wir
        selbst eine anlegen. Das bildet den Bootstrap-Fall exakt nach: kein Benutzer in der
        Datenbank, aber (anders als ein echter Bootstrap-Aufruf) hier zusätzlich ein bereits
        gesetzter role="field"-Kontext -- und selbst DER kommt durch, weil
        _require_users_page_access() den users_exist()-Zweig vor jeder Rollenprüfung auswertet."""
        from app.models import AppUser
        from app.routers.pages import router as pages_router
        db = threaded_db_session
        bootstrap = router_test_client(db, pages_router, role="field")
        assert bootstrap.get("/users", follow_redirects=False).status_code == 200

        db.add(AppUser(username="erste.admina", display_name="Erste Admina", role="admin", active=True,
                       password_hash="x"))
        db.commit()
        field = router_test_client(db, pages_router, role="field")
        assert field.get("/users", follow_redirects=False).status_code == 403
        office = router_test_client(db, pages_router, role="buero_auftrag")
        assert office.get("/users", follow_redirects=False).status_code == 200


def test_403_on_a_page_route_renders_access_denied_html_not_json():
    """Isolierter Test der Exception-Handler-Verdrahtung selbst (app/main.py) -- ohne
    router_test_client(), das keine eigenen Exception-Handler registriert, und ohne die echte
    app.main.app/Middleware anzufassen (deren Middleware liefe gegen die echte DATABASE_URL).
    Ein Mini-FastAPI mit genau einer role-gegateten Seite plus demselben Handler wie main.py."""
    from fastapi import Depends, FastAPI, HTTPException, Request
    from fastapi.testclient import TestClient
    from app.main import _role_check_403_shows_access_denied_page
    from app.models import AppUser
    from app.permissions import ROLE_ADMIN, require_role

    app = FastAPI()
    app.add_exception_handler(HTTPException, _role_check_403_shows_access_denied_page)

    @app.middleware("http")
    async def _fake_identity(request: Request, call_next):
        role = request.headers.get("x-test-role")
        request.state.erp_user = AppUser(username="x", display_name="x", role=role, active=True, password_hash="x") if role else None
        return await call_next(request)

    @app.get("/buero-only")
    def buero_only(request: Request, _role: AppUser = Depends(require_role(ROLE_ADMIN))):
        return {"ok": True}

    @app.get("/api/buero-only")
    def api_buero_only(request: Request, _role: AppUser = Depends(require_role(ROLE_ADMIN))):
        return {"ok": True}

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/buero-only", headers={"x-test-role": "field"})
    assert resp.status_code == 403
    assert "text/html" in resp.headers["content-type"]
    assert "Diese Seite ist für Ihre Rolle nicht verfügbar" in resp.text
    assert 'href="/mobil"' in resp.text  # default_home_page_for_role("field"), seit 1.3.61 (bis 1.3.60 /vor-ort)

    resp_anon = client.get("/buero-only")  # kein x-test-role-Header -> erp_user bleibt None
    assert resp_anon.status_code == 403
    assert 'href="/users"' in resp_anon.text  # Bootstrap-Wegweiser statt des gesperrten Dashboards

    # ein /api/-Pfad bleibt unverändert JSON (kein zweiter Ort mit eigener Fehlerbehandlung)
    resp_api = client.get("/api/buero-only", headers={"x-test-role": "field"})
    assert resp_api.status_code == 403
    assert resp_api.headers["content-type"].startswith("application/json")
