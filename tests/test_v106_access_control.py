from app.main import _request_requires_login


def test_login_required_also_before_the_first_account():
    # Bis 1.8.129 blieb vor dem ersten ERP-Benutzer alles erreichbar (dort legte man das erste Konto an). Seit 1.8.130 entsteht es per
    # Befehl auf dem Server (scripts/erstes_konto.py), ohne Konto hält die Schranke die App geschlossen (503) -- has_users öffnet nichts.
    assert _request_requires_login(False, "GET", "/api/employees") is True
    assert _request_requires_login(False, "POST", "/api/projects") is True


def test_login_endpoints_always_reachable():
    assert _request_requires_login(True, "GET", "/api/auth/status") is False
    assert _request_requires_login(True, "POST", "/api/auth/login") is False


def test_write_access_requires_login_as_before():
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert _request_requires_login(True, method, "/api/employees") is True


def test_read_access_to_api_requires_login():
    # Kern des Fixes: GET auf /api/... lieferte u. a. Löhne (EmployeeOut) und
    # Kalkulationsgrundlagen aus und durfte daher nicht länger ohne Login möglich sein.
    assert _request_requires_login(True, "GET", "/api/employees") is True
    assert _request_requires_login(True, "GET", "/api/labor-rate-settings") is True
    assert _request_requires_login(True, "GET", "/api/customers") is True


def test_html_shell_and_health_check_stay_reachable():
    # Die Seiten selbst liefern keine sensiblen Daten (nur das leere Grundgerüst,
    # echte Daten kommen über /api/...), daher hier bewusst nicht gesperrt.
    assert _request_requires_login(True, "GET", "/employees") is False
    assert _request_requires_login(True, "GET", "/") is False
    assert _request_requires_login(True, "GET", "/health") is False
