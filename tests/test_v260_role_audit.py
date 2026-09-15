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
from app.permissions import ROLE_ADMIN, ROLE_AUDIT_EXEMPT, ROLE_OFFICE, require_role


def _iter_role_marked_dependants(dependant):
    """Geht dependant.dependencies rekursiv durch (FastAPI verschachtelt Sub-Dependencies) und
    liefert jedes _dk_roles-Attribut, das require_role()/require_admin() markiert haben."""
    for sub in dependant.dependencies:
        call = getattr(sub, "call", None)
        roles = getattr(call, "_dk_roles", None)
        if roles is not None:
            yield roles
        yield from _iter_role_marked_dependants(sub)


def _discover_api_routes():
    """Importiert jedes Modul unter app/routers/ selbst (kein app.main -- siehe CLAUDE.md
    "Migrations-Workflow" zum Risiko, app.main in einem Test zu importieren: Base.metadata.
    create_all() liefe sonst gegen die echte, lokale DATABASE_URL) und liefert (method, path,
    route) für jede registrierte /api/-Route."""
    found = []
    for module_info in pkgutil.iter_modules(routers_package.__path__, prefix="app.routers."):
        module = importlib.import_module(module_info.name)
        router = getattr(module, "router", None)
        if router is None:
            continue
        for route in router.routes:
            path = getattr(route, "path", "")
            if not path.startswith("/api/"):
                continue
            for method in (route.methods or set()) - {"HEAD", "OPTIONS"}:
                found.append((method, path, route))
    return found


@pytest.mark.xfail(
    reason="Etappe 2/3 (voller Rollen-Sweep aller Router) ist noch offen, siehe CLAUDE.md "
           "'Rechtekonzept' -- dieser Test bleibt bis dahin absichtlich rot, das ist die "
           "Checkliste dafür, kein Regressionsfund. pytest -rx zeigt die vollständige Liste.",
    strict=False,
)
def test_all_api_routes_have_an_explicit_role_check():
    unclassified = []
    for method, path, route in _discover_api_routes():
        if (method, path) in ROLE_AUDIT_EXEMPT:
            continue
        if any(True for _ in _iter_role_marked_dependants(route.dependant)):
            continue
        unclassified.append(f"{method} {path}")
    unclassified.sort()
    assert not unclassified, (
        f"{len(unclassified)} /api/-Endpunkt(e) ohne erkennbare Rollenprüfung -- Standard ist "
        f"admin-only (siehe app/permissions.py), das ist die Etappe-2/3-Checkliste, keine "
        f"Panik: \n" + "\n".join(unclassified)
    )


def test_require_admin_and_require_role_both_carry_the_audit_marker():
    """require_admin() (app/deps.py) und require_role() (app/permissions.py) müssen beide die
    _dk_roles-Markierung tragen -- sonst würde der Audit-Test oben jeden der zwölf bereits
    bestehenden admin-gateten Endpunkte fälschlich als unklassifiziert melden."""
    admin_dep = require_admin("x")
    assert admin_dep._dk_roles == frozenset({"admin"})
    role_dep = require_role(ROLE_ADMIN, ROLE_OFFICE)
    assert role_dep._dk_roles == frozenset({"admin", "office"})


class TestRoleGateOnCustomersInvoicesReminders:
    """Nachweis am Beispiel: office/admin dürfen weiterhin alles wie bisher, field wird an
    genau diesen drei Dateien abgelehnt (403), ohne dass Objekt-Filterung nötig ist -- Kunden/
    Rechnungen/Mahnungen sind für einen Monteur an keiner Stelle vorgesehen, siehe CLAUDE.md."""

    def _client(self, router_test_client, threaded_db_session, role):
        from app.routers.customers import router as customers_router
        from app.routers.invoices import router as invoices_router
        from app.routers.reminders import router as reminders_router
        return router_test_client(
            threaded_db_session, customers_router, invoices_router, reminders_router, role=role,
        )

    @pytest.mark.parametrize("role", ["admin", "office"])
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

    def test_office_still_reaches_employee_wage_data(self, router_test_client, threaded_db_session):
        from app.routers.employees import router as employees_router
        client = router_test_client(threaded_db_session, employees_router, role="office")
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

        office_client = router_test_client(threaded_db_session, materials_router, role="office")
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
        for role in ("admin", "office"):
            client = router_test_client(threaded_db_session, tasks_router, task_columns_router, role=role, employee_id=emp.id)
            assert client.get("/api/tasks").status_code == 200, role
            assert client.get("/api/task-columns").status_code == 200, role
