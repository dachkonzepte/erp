"""Rechtekonzept "Vier Rollen", Etappe 2 -- die Verengungen (seit 1.4.8, siehe CLAUDE.md
"Rechtekonzept" -> "Vier Rollen"). Betreiberauftrag, wörtlich: Kalkulationsgrundlagen/
Stundenverrechnungssatz-Herleitung/Mitarbeitervergütung auf buero_finanzen verengen (der
Mitarbeiter-BESTAND ohne Vergütung bleibt buero_auftrag), das Zeiterfassungs-Backoffice von
admin-only auf buero_auftrag heben (nachdem geprüft wurde, dass dort keine Vergütung
mitsichtbar wird), und ein abschließender Angriffstest mit je einem Konto pro Rolle:

  - buero_auftrag gegen Kalkulationsgrundlagen, Vergütung -> 403, kein Lohnfeld in irgendeiner
    Antwort
  - buero_auftrag ins Zeiterfassungs-Backoffice -> erlaubt, aber ohne Lohndaten
  - buero_finanzen sieht alles davon -> erlaubt
  - field gegen alles -> wie bisher gesperrt

Null durchgelassen, rekursiver Schlüssel-Scan (Fehlerklasse "purchase_price", siehe CLAUDE.md)
auf jedem Mitarbeiter-Endpunkt -- inklusive der Änderungshistorie, die Vorher-/Nachher-Werte und
angelegt/gelöscht-Schnappschüsse über ALLE Entitäten hinweg zeigt und deshalb ein eigener,
bisher unklassifizierter Fund dieser Etappe war (siehe app/audit.py::WAGE_FIELD_NAMES)."""

import json

import pytest

from app.routers.audit import router as audit_router
from app.routers.employees import router as employees_router
from app.routers.labor_rate import router as labor_rate_router
from app.routers.pages import router as pages_router
from app.routers.settings import router as settings_router
from app.routers.time_backoffice import router as time_backoffice_router

WAGE_KEYS = {"hourly_wage", "monthly_salary", "compensation_type", "effective_hourly_wage", "annual_gross_wage"}
ALL_ROLES = ("field", "buero_auftrag", "buero_finanzen", "admin")


def _recursive_keys(value, keys=None):
    """Sammelt alle Dict-Schlüssel rekursiv -- auch aus als JSON-String codierten Werten
    (z. B. AuditLogOut.details, ein angelegt/gelöscht-Schnappschuss), damit ein versteckt
    verschachteltes Lohnfeld nicht am flachen Vergleich vorbeirutscht."""
    if keys is None:
        keys = set()
    if isinstance(value, dict):
        for k, v in value.items():
            keys.add(k)
            _recursive_keys(v, keys)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _recursive_keys(item, keys)
    elif isinstance(value, str):
        s = value.strip()
        if s[:1] in "{[":
            try:
                parsed = json.loads(s)
            except (TypeError, ValueError):
                return keys
            _recursive_keys(parsed, keys)
    return keys


def _create_wage_employee(db, router_test_client, *, hourly_wage="25.50"):
    """Legt über den echten Router als buero_finanzen (die seit dieser Etappe einzige
    schreibberechtigte Rolle) einen aktiven, gewerblichen Mitarbeiter mit Stundenlohn an --
    Testdatengrundlage für Kalkulationsgrundlagen/Stundenverrechnungssatz UND den
    Angriffstest auf die Vergütung."""
    client = router_test_client(db, employees_router, role="buero_finanzen")
    resp = client.post("/api/employees", json={
        "first_name": "Erika", "last_name": "Musterfrau", "employee_group": "gewerblich",
        "compensation_type": "hourly", "hourly_wage": hourly_wage, "cost_allocation": "labor_rate",
        "weekly_hours": "40.00",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# 1. Kalkulationsgrundlagen (app/routers/settings.py)
# ---------------------------------------------------------------------------

def test_calculation_settings_get_requires_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    for role in ALL_ROLES:
        client = router_test_client(db, settings_router, role=role)
        resp = client.get("/api/calculation-settings")
        expected = 200 if role in ("buero_finanzen", "admin") else 403
        assert resp.status_code == expected, (role, resp.text)
        if expected == 403:
            assert not (_recursive_keys(resp.json()) & WAGE_KEYS), (role, resp.json())


def test_calculation_settings_put_requires_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    payload = {
        "labor_rate": "80.00", "material_markup_pct": "10", "overhead_pct": "5",
        "risk_profit_pct": "5", "use_source_time_as_minutes": True,
    }
    for role in ALL_ROLES:
        client = router_test_client(db, settings_router, role=role)
        resp = client.put("/api/calculation-settings", json=payload)
        expected = 200 if role in ("buero_finanzen", "admin") else 403
        assert resp.status_code == expected, (role, resp.text)


# ---------------------------------------------------------------------------
# 2. Stundenverrechnungssatz-Herleitung (app/routers/labor_rate.py)
# ---------------------------------------------------------------------------

def test_labor_rate_settings_and_calculation_require_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    _create_wage_employee(db, router_test_client)
    for role in ALL_ROLES:
        client = router_test_client(db, labor_rate_router, role=role)
        expected = 200 if role in ("buero_finanzen", "admin") else 403
        r1 = client.get("/api/labor-rate-settings")
        assert r1.status_code == expected, (role, "settings", r1.text)
        r2 = client.get("/api/labor-rate-calculation")
        assert r2.status_code == expected, (role, "calculation", r2.text)
        if expected == 403:
            assert not (_recursive_keys(r1.json()) & WAGE_KEYS)
            assert not (_recursive_keys(r2.json()) & WAGE_KEYS)
        else:
            # calculate_labor_rate() liefert echte Vergütungsaggregate (weighted_mean_wage
            # u. Ä.) -- genau deshalb ist dieser Endpunkt verengt, nicht trotzdem offen.
            assert _recursive_keys(r2.json()) & {"weighted_mean_wage", "annual_gross_wages", "direct_labor_annual_cost"}


def test_labor_rate_settings_put_and_apply_require_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    _create_wage_employee(db, router_test_client)
    payload = {
        "employer_cost_pct": "20", "productive_time_pct": "80", "target_profit_pct": "10",
        "weeks_per_year": "52",
    }
    for role in ALL_ROLES:
        client = router_test_client(db, labor_rate_router, role=role)
        put_resp = client.put("/api/labor-rate-settings", json=payload)
        apply_resp = client.post("/api/labor-rate-calculation/apply")
        if role in ("buero_finanzen", "admin"):
            assert put_resp.status_code == 200, (role, put_resp.text)
            assert apply_resp.status_code != 403, (role, apply_resp.text)
        else:
            assert put_resp.status_code == 403, (role, put_resp.text)
            assert apply_resp.status_code == 403, (role, apply_resp.text)


# ---------------------------------------------------------------------------
# 3. Mitarbeitervergütung -- Lesen (der Bestand bleibt buero_auftrag, die Vergütung nicht)
# ---------------------------------------------------------------------------

def test_employee_list_returns_role_dependent_schema_without_wage_leak(threaded_db_session, router_test_client):
    db = threaded_db_session
    _create_wage_employee(db, router_test_client)
    for role in ALL_ROLES:
        client = router_test_client(db, employees_router, role=role)
        resp = client.get("/api/employees")
        assert resp.status_code == 200, (role, resp.text)  # jede Rolle sieht die Liste
        body = resp.json()
        assert len(body) == 1
        keys_found = _recursive_keys(body)
        if role in ("buero_finanzen", "admin"):
            assert keys_found & WAGE_KEYS, (role, body)
        else:
            assert not (keys_found & WAGE_KEYS), (role, body)
        if role == "field":
            assert set(body[0].keys()) == {"id", "first_name", "last_name", "active"}
        elif role == "buero_auftrag":
            assert "cost_allocation" in body[0]  # Kategorie bleibt sichtbar, kein Betrag
            assert set(body[0].keys()) & WAGE_KEYS == set()


def test_employee_caseworkers_and_detail_require_at_least_buero_auftrag(threaded_db_session, router_test_client):
    db = threaded_db_session
    created = _create_wage_employee(db, router_test_client)
    finanzen = router_test_client(db, employees_router, role="buero_finanzen")
    finanzen.put(f"/api/employees/{created['id']}", json={
        "first_name": "Erika", "last_name": "Musterfrau", "employee_group": "gewerblich",
        "compensation_type": "hourly", "hourly_wage": "25.50", "cost_allocation": "labor_rate",
        "weekly_hours": "40.00", "available_as_caseworker": True,
    })

    for role in ALL_ROLES:
        client = router_test_client(db, employees_router, role=role)
        detail = client.get(f"/api/employees/{created['id']}")
        caseworkers = client.get("/api/employees/caseworkers")
        if role == "field":
            assert detail.status_code == 403, (role, detail.text)
            assert caseworkers.status_code == 403, (role, caseworkers.text)
            continue
        assert detail.status_code == 200, (role, detail.text)
        assert caseworkers.status_code == 200, (role, caseworkers.text)
        detail_keys = _recursive_keys(detail.json())
        caseworker_keys = _recursive_keys(caseworkers.json())
        if role == "buero_auftrag":
            assert not (detail_keys & WAGE_KEYS), (role, detail.json())
            assert not (caseworker_keys & WAGE_KEYS), (role, caseworkers.json())
        else:
            assert detail_keys & WAGE_KEYS, (role, detail.json())
            assert caseworker_keys & WAGE_KEYS, (role, caseworkers.json())


# ---------------------------------------------------------------------------
# 4. Mitarbeitervergütung -- Schreiben (nur buero_finanzen, per Regel-10-Kombiformular)
# ---------------------------------------------------------------------------

def test_employee_create_and_update_require_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    created = _create_wage_employee(db, router_test_client)
    create_payload = {
        "first_name": "Neu", "last_name": "Angestellt", "employee_group": "gewerblich",
        "compensation_type": "hourly", "hourly_wage": "20.00", "cost_allocation": "labor_rate",
    }
    update_payload = {
        "first_name": "Erika", "last_name": "Musterfrau-Geändert", "employee_group": "gewerblich",
        "compensation_type": "hourly", "hourly_wage": "26.00", "cost_allocation": "labor_rate",
    }
    for role in ("field", "buero_auftrag"):
        client = router_test_client(db, employees_router, role=role)
        assert client.post("/api/employees", json=create_payload).status_code == 403, role
        assert client.put(f"/api/employees/{created['id']}", json=update_payload).status_code == 403, role
    for role in ("buero_finanzen", "admin"):
        client = router_test_client(db, employees_router, role=role)
        assert client.put(f"/api/employees/{created['id']}", json=update_payload).status_code == 200, role


# ---------------------------------------------------------------------------
# 5. Zeiterfassungs-Backoffice -- von admin-only auf buero_auftrag angehoben
# ---------------------------------------------------------------------------

def test_time_backoffice_is_open_to_buero_auftrag_but_never_shows_wages(threaded_db_session, router_test_client):
    db = threaded_db_session
    _create_wage_employee(db, router_test_client)
    for role in ALL_ROLES:
        client = router_test_client(db, time_backoffice_router, role=role)
        settings_resp = client.get("/api/time-backoffice/settings")
        payroll_resp = client.get("/api/time-backoffice/payroll-employees")
        summary_resp = client.get("/api/time-backoffice/summary", params={"start_date": "2026-01-01", "end_date": "2026-01-31"})
        if role == "field":
            assert settings_resp.status_code == 403, (role, settings_resp.text)
            assert payroll_resp.status_code == 403, (role, payroll_resp.text)
            assert summary_resp.status_code == 403, (role, summary_resp.text)
            continue
        # buero_auftrag, buero_finanzen, admin: erlaubt (die Anhebung selbst) ...
        assert settings_resp.status_code == 200, (role, settings_resp.text)
        assert payroll_resp.status_code == 200, (role, payroll_resp.text)
        assert summary_resp.status_code == 200, (role, summary_resp.text)
        # ... aber ohne jedes Lohnfeld, für JEDE der drei Rollen gleichermaßen -- das
        # Zeiterfassungs-Backoffice zeigt strukturell keine € (nur DATEV-Buchungscodes/Stunden).
        assert not (_recursive_keys(settings_resp.json()) & WAGE_KEYS), (role, settings_resp.json())
        assert not (_recursive_keys(payroll_resp.json()) & WAGE_KEYS), (role, payroll_resp.json())
        assert not (_recursive_keys(summary_resp.json()) & WAGE_KEYS), (role, summary_resp.json())


# ---------------------------------------------------------------------------
# 6. Änderungshistorie -- eigener Fund dieser Etappe: "jede Auswertung, die Löhne zeigt"
# ---------------------------------------------------------------------------

def test_audit_log_redacts_wage_changes_for_buero_auftrag_but_not_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    created = _create_wage_employee(db, router_test_client)  # "angelegt"-Schnappschuss mit hourly_wage
    finanzen = router_test_client(db, employees_router, role="buero_finanzen")
    finanzen.put(f"/api/employees/{created['id']}", json={
        "first_name": "Erika", "last_name": "Musterfrau", "employee_group": "gewerblich",
        "compensation_type": "hourly", "hourly_wage": "30.00", "cost_allocation": "labor_rate",
        "weekly_hours": "40.00",
    })  # "geändert"-Zeile mit field_name="hourly_wage", old/new_value

    auftrag = router_test_client(db, audit_router, role="buero_auftrag")
    auftrag_resp = auftrag.get("/api/audit-logs")
    assert auftrag_resp.status_code == 200
    auftrag_rows = auftrag_resp.json()
    assert auftrag_rows  # buero_auftrag sieht die Änderungshistorie -- nur nicht die Löhne darin
    for row in auftrag_rows:
        assert row["field_name"] not in WAGE_KEYS, row
        assert not (_recursive_keys(row) & WAGE_KEYS), row

    finanzen_audit = router_test_client(db, audit_router, role="buero_finanzen")
    finanzen_rows = finanzen_audit.get("/api/audit-logs").json()
    assert any(r["field_name"] == "hourly_wage" for r in finanzen_rows), "buero_finanzen muss die Lohnänderung weiterhin sehen"
    assert any(_recursive_keys(r) & WAGE_KEYS for r in finanzen_rows if r["action"] == "angelegt")

    field_resp = router_test_client(db, audit_router, role="field").get("/api/audit-logs")
    assert field_resp.status_code == 403


# ---------------------------------------------------------------------------
# 7. field -- unverändert an jeder Stelle gesperrt (kein Rückschritt durch diese Etappe)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 7b. Seiten-Rendering -- die tatsächlich ausgelieferte HTML-Seite, nicht nur die API.
#     (Fand beim Bauen dieser Etappe einen echten Bug: current_user wurde in settings.html/
#     master_data.html per {% include "_sidebar.html" %} erwartet, aber ein {% set %}
#     innerhalb eines Includes wirkt in Jinja nicht in der einbindenden Vorlage nach --
#     can(current_user, ...) warf dort "current_user is undefined", für JEDE Rolle,
#     behoben durch ein eigenes {% set current_user = request.state.erp_user %} in beiden
#     Dateien. test_v218_template_rendering.py deckt das strukturell (Status 200) ab, hier
#     wird zusätzlich der tatsächliche, rollenabhängige INHALT geprüft.)
# ---------------------------------------------------------------------------

def test_settings_page_hides_calculation_sections_from_buero_auftrag(threaded_db_session, router_test_client):
    # /settings selbst ist -- unverändert seit der Seiten-Klassifizierung (Etappe 1) -- Büro/
    # Admin (require_min_role(ROLE_OFFICE_AUFTRAG)), field kommt dort gar nicht erst hin. Diese
    # Etappe verengt NICHT den Seitenzugriff, sondern nur, was innerhalb der Seite sichtbar ist.
    db = threaded_db_session
    for role, can_see in (("buero_auftrag", False), ("buero_finanzen", True), ("admin", True)):
        client = router_test_client(db, pages_router, role=role)
        resp = client.get("/settings")
        assert resp.status_code == 200, (role, resp.status_code)
        body = resp.text
        expected_flag = "true" if can_see else "false"
        assert f"canSeeCalculationSettings={expected_flag};" in body, (role, body[:200])
        assert (('id="settings-labor-rate"' in body) is can_see), (role, "settings-labor-rate")
        assert (('id="settings-calculation"' in body) is can_see), (role, "settings-calculation")
    client = router_test_client(db, pages_router, role="field")
    assert client.get("/settings").status_code == 403


def test_master_data_page_hides_compensation_from_buero_auftrag(threaded_db_session, router_test_client):
    db = threaded_db_session
    for role, can_manage in (("buero_auftrag", False), ("buero_finanzen", True), ("admin", True)):
        client = router_test_client(db, pages_router, role=role)
        resp = client.get("/master-data")
        assert resp.status_code == 200, (role, resp.status_code)
        expected_flag = "true" if can_manage else "false"
        assert f"canManageEmployees={expected_flag};" in resp.text, (role, resp.text[:200])
    client = router_test_client(db, pages_router, role="field")
    assert client.get("/master-data").status_code == 403


def test_time_backoffice_page_is_reachable_for_buero_auftrag_not_field(threaded_db_session, router_test_client):
    db = threaded_db_session
    for role, expected in (("field", 403), ("buero_auftrag", 200), ("buero_finanzen", 200), ("admin", 200)):
        client = router_test_client(db, pages_router, role=role)
        resp = client.get("/time-backoffice")
        assert resp.status_code == expected, (role, resp.status_code)


def test_master_data_employee_form_pages_stay_buero_finanzen_only(threaded_db_session, router_test_client):
    db = threaded_db_session
    for role, expected in (("field", 403), ("buero_auftrag", 403), ("buero_finanzen", 200), ("admin", 200)):
        client = router_test_client(db, pages_router, role=role)
        assert client.get("/master-data/employees/new").status_code == expected, (role, "new")
        assert client.get("/master-data/employees/1/edit").status_code == expected, (role, "edit")


@pytest.mark.parametrize("router,path,method", [
    (settings_router, "/api/calculation-settings", "get"),
    (labor_rate_router, "/api/labor-rate-settings", "get"),
    (employees_router, "/api/employees/1", "get"),
    (employees_router, "/api/employees/caseworkers", "get"),
    (audit_router, "/api/audit-logs", "get"),
])
def test_field_stays_locked_out_everywhere(threaded_db_session, router_test_client, router, path, method):
    db = threaded_db_session
    client = router_test_client(db, router, role="field")
    resp = getattr(client, method)(path)
    assert resp.status_code == 403, resp.text
