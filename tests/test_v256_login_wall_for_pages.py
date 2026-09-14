"""Version 1.3.47 -- serverseitige Anmeldeschranke für Seiten, plus /login leitet weiter,
wenn schon jemand angemeldet ist.

Bisher rendierte JEDE Seite (auch /tasks, /settings, /) ihr Gerüst unabhängig vom
Anmeldestatus -- die Autorisierungsprüfung lag ausschließlich beim /api/-Zugriff dahinter
bzw. rein clientseitig in _sidebar.html (das den Anmeldestatus erst NACH dem Rendern per
fetch('/api/auth/status') abfragt). Auf Nutzeranfrage geprüft und zwei echte Lücken
behoben:

1. app/main.py::_page_requires_login() -- neue, bewusst von _request_requires_login()
   getrennte Funktion (siehe deren Docstring für die Begründung), die dieselbe Middleware
   für HTML-Seiten (GET, nicht /api/) auswertet und bei fehlender Anmeldung auf /login
   umleitet, statt die Seite zu rendern. /login, /health, /manifest.json bleiben
   ausgenommen (siehe _PUBLIC_PAGE_PATHS), ebenso die bereits bestehende Bootstrap-Ausnahme
   (kein einziger ERP-Benutzer angelegt).
2. app/routers/pages.py::login_page() -- leitet auf / weiter (bzw. /account bei einem
   Administrator mit noch ausstehendem zweitem Faktor -- sonst wäre dort ohnehin nichts
   nutzbar), wenn schon jemand angemeldet ist, statt die Anmeldemaske erneut zu zeigen.

Bewusst NICHT Teil dieser Version (siehe Bericht an den Nutzer): eine Rückführung nach dem
Anmelden auf die ursprünglich gewünschte Seite (?next=...) -- login.html liest und honoriert
einen solchen Parameter zwar bereits (für die bestehenden Abmelden-Links), aber die neue
Umleitung hier setzt bewusst noch keinen, das war eine separate, abgestimmte Entscheidung.

Isolierter Testaufbau nach dem Muster aus test_v250_two_factor_auth.py::_make_test_app()
(eigene, throwaway In-Memory-SQLite-Engine, eigene, aus den ECHTEN Funktionen
_page_requires_login()/_request_requires_login() nachgebaute Middleware) -- bewusst NICHT
router_test_client() (fest einen bereits angemeldeten Admin-Kontext injiziert, für
"ohne Anmeldung"-Szenarien ungeeignet, siehe dessen eigener Docstring in tests/conftest.py).
pages_router + auth_router_module, damit ein echter TestClient mit echten Cookies den
tatsächlichen Redirect end-to-end durchläuft, nicht nur eine Behauptung über den Code."""

from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password, otp_ok_for_user, user_from_request, users_exist
from app.database import Base, get_db
from app.main import _page_requires_login, _request_requires_login
from app.models import AppUser
from app.routers import auth as auth_router_module
from app.routers import pages as pages_router_module

PASSWORD = "RichtigesPasswort123"


def make_user(db, username="user.test", role="user"):
    user = AppUser(username=username, display_name=username, role=role, active=True,
                    password_hash=hash_password(PASSWORD))
    db.add(user); db.commit()
    return user


def _make_test_app():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    make_session = sessionmaker(bind=engine)

    app = FastAPI()
    app.include_router(pages_router_module.router)
    app.include_router(auth_router_module.router)
    app.dependency_overrides[get_db] = lambda: make_session()

    @app.middleware("http")
    async def _identity_gate(request: Request, call_next):
        mw_db = make_session()
        try:
            has_users = users_exist(mw_db)
            user = user_from_request(mw_db, request)
        finally:
            mw_db.close()
        request.state.erp_user = user
        otp_ok = True
        if user is not None and user.role == "admin":
            otp_ok = otp_ok_for_user(request, user.id)
        request.state.otp_ok = otp_ok
        if user is None and _request_requires_login(has_users, request.method, request.url.path):
            return JSONResponse(status_code=401, content={"detail": "Bitte zuerst als ERP-Benutzer anmelden."})
        if user is None and _page_requires_login(has_users, request.method, request.url.path):
            # Mirror der echten Middleware in app/main.py -- dieselbe ?next=<Pfad>-Konvention.
            next_target = quote(request.url.path, safe="")
            return RedirectResponse(url=f"/login?next={next_target}", status_code=302)
        return await call_next(request)

    return TestClient(app), make_session


# ---------------------------------------------------------------------------
# _page_requires_login() isoliert -- schnelle, direkte Prüfung der Entscheidungsregel
# selbst, analog zu test_v106_access_control.py für _request_requires_login().
# ---------------------------------------------------------------------------

def test_page_requires_login_true_for_a_regular_page():
    assert _page_requires_login(True, "GET", "/tasks") is True
    assert _page_requires_login(True, "GET", "/") is True


def test_page_requires_login_false_for_login_health_and_manifest():
    assert _page_requires_login(True, "GET", "/login") is False
    assert _page_requires_login(True, "GET", "/health") is False
    assert _page_requires_login(True, "GET", "/manifest.json") is False


def test_page_requires_login_false_for_api_paths():
    # /api/... bleibt ausschliesslich Sache von _request_requires_login() (401-JSON) --
    # kein zweiter, hier abweichender Redirect auf eine HTML-Seite fuer einen API-Client.
    assert _page_requires_login(True, "GET", "/api/tasks") is False


def test_page_requires_login_false_during_bootstrap_before_any_user_exists():
    assert _page_requires_login(False, "GET", "/tasks") is False


def test_page_requires_login_false_for_non_get_methods():
    assert _page_requires_login(True, "POST", "/tasks") is False


# ---------------------------------------------------------------------------
# Ende-zu-Ende ueber einen echten TestClient/echte Cookies.
# ---------------------------------------------------------------------------

def test_unauthenticated_get_to_a_protected_page_redirects_to_login_with_next():
    """?next=<Pfad> -- dieselbe Konvention wie die bestehenden Abmelden-Links, damit
    login.html (liest next bereits, siehe dort) nach dem Anmelden zur ursprünglich
    gewünschten Seite zurückführt, nicht immer aufs Dashboard."""
    client, make_session = _make_test_app()
    make_user(make_session())
    resp = client.get("/tasks", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login?next=%2Ftasks"


def test_unauthenticated_get_to_the_root_address_redirects_to_login_with_next():
    client, make_session = _make_test_app()
    make_user(make_session())
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login?next=%2F"


def test_login_page_itself_stays_reachable_and_shows_the_form_when_not_authenticated():
    client, make_session = _make_test_app()
    make_user(make_session())
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "Anmeldung" in resp.text
    assert 'id="u"' in resp.text  # das Benutzername-Feld -- die Maske erscheint wirklich


def test_health_stays_reachable_without_login():
    client, make_session = _make_test_app()
    make_user(make_session())
    resp = client.get("/health")
    assert resp.status_code == 200


def test_protected_page_is_reachable_without_login_before_any_user_exists():
    """Bootstrap-Ausnahme, wie bei _request_requires_login() -- ohne einen einzigen
    ERP-Benutzer muss z. B. /users erreichbar bleiben, um den ersten Administrator
    anzulegen."""
    client, _make_session = _make_test_app()
    resp = client.get("/users", follow_redirects=False)
    assert resp.status_code == 200


def test_authenticated_user_reaches_the_dashboard_directly():
    client, make_session = _make_test_app()
    make_user(make_session())
    login = client.post("/api/auth/login", json={"username": "user.test", "password": PASSWORD})
    assert login.status_code == 200
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 200


def test_authenticated_user_visiting_a_protected_page_gets_it_directly():
    client, make_session = _make_test_app()
    make_user(make_session())
    client.post("/api/auth/login", json={"username": "user.test", "password": PASSWORD})
    resp = client.get("/tasks", follow_redirects=False)
    assert resp.status_code == 200


def test_login_page_redirects_authenticated_non_admin_to_the_dashboard():
    client, make_session = _make_test_app()
    make_user(make_session())
    client.post("/api/auth/login", json={"username": "user.test", "password": PASSWORD})
    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_login_page_redirects_admin_pending_two_factor_to_account_not_dashboard():
    """Wer sich als Administrator gerade erst mit Benutzername/Passwort angemeldet hat,
    aber den zweiten Faktor noch nicht bestaetigt hat, ist im Sinne dieser Anfrage bereits
    "angemeldet" -- geht deshalb nach /account, nicht auf ein Dashboard, auf dem ohnehin
    nichts nutzbar waere (siehe app/main.py::_blocked_pending_two_factor())."""
    client, make_session = _make_test_app()
    make_user(make_session(), username="admin.test", role="admin")
    login = client.post("/api/auth/login", json={"username": "admin.test", "password": PASSWORD})
    assert login.status_code == 200
    assert login.json()["two_factor_required"] is True
    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/account"
