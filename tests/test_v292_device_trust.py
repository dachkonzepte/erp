"""Version 1.5.11 -- "Diesem Gerät für 30 Tage vertrauen" (Geräte-Vertrauen für die
Zwei-Faktor-Authentifizierung, app/device_trust.py). Siehe CLAUDE.md
"Zwei-Faktor-Authentifizierung für Administratoren" -> "Diesem Gerät vertrauen".

Server-seitig verwaltet (app/models.py::TrustedDevice) -- ein separates, signiertes Cookie
(dk_erp_trust) trägt nur Zeilen-ID + rohes Geheimnis, der Server vergleicht gegen den
gespeicherten Hash. Checkbox erscheint AUSSCHLIESSLICH bei der Routine-Bestätigung
(POST /api/account/2fa/verify), NIE bei der Ersteinrichtung. ALLE Geräte eines Kontos werden bei
fünf Stellen widerrufen: (1) admin-reset-two-factor-Endpunkt, (2) das Notfallskript
reset_admin_2fa.py -- beide über die gemeinsame app/two_factor.py::reset() --, (3) die eigene
Passwortänderung, (4) ein von einem Administrator für ein ANDERES Konto gesetztes Passwort, (5)
der ausdrückliche Widerruf ("Alle vertrauten Geräte abmelden"). Jede der fünf Stellen wird hier
einzeln geprüft: ein zuvor vertrautes Gerät muss danach wertlos sein, der Code wird wieder
fällig."""

import base64
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import device_trust, two_factor
from app.auth import otp_ok_for_user, user_from_request
from app.database import Base, get_db
from app.main import _blocked_pending_two_factor
from app.models import AppUser, TrustedDevice
from app.routers import account as account_router_module
from app.routers import auth as auth_router_module
from app.routers import users as users_router_module
from app.routers.users import reset_user_two_factor, update_app_user
from app.schemas import AppUserUpdate
from tests.test_v153_mahnwesen import db_session
from tests.test_v250_two_factor_auth import make_admin, make_valid_code

PASSWORD = "RichtigesPasswort123"


# --- app/device_trust.py, isoliert -----------------------------------------------------------

def test_create_trust_and_check_trust_round_trip():
    db = db_session()
    admin = make_admin(db)
    cookie = device_trust.create_trust(db, admin)
    assert device_trust.check_trust(db, admin, cookie) is True


def test_check_trust_rejects_missing_or_garbage_cookie():
    db = db_session()
    admin = make_admin(db)
    assert device_trust.check_trust(db, admin, None) is False
    assert device_trust.check_trust(db, admin, "") is False
    assert device_trust.check_trust(db, admin, "!!!nicht-base64-kauderwelsch!!!") is False
    assert device_trust.check_trust(db, admin, base64.urlsafe_b64encode(b"kein-doppelpunkt").decode()) is False


def test_check_trust_rejects_expired_device():
    db = db_session()
    admin = make_admin(db)
    cookie = device_trust.create_trust(db, admin)
    row = db.scalar(select(TrustedDevice).where(TrustedDevice.user_id == admin.id))
    row.expires_at = datetime.utcnow() - timedelta(days=1)
    db.commit()
    assert device_trust.check_trust(db, admin, cookie) is False


def test_check_trust_rejects_a_cookie_belonging_to_a_different_account():
    db = db_session()
    admin_a = make_admin(db, "isoliert.a")
    admin_b = make_admin(db, "isoliert.b")
    cookie_a = device_trust.create_trust(db, admin_a)
    assert device_trust.check_trust(db, admin_b, cookie_a) is False
    assert device_trust.check_trust(db, admin_a, cookie_a) is True  # unverändert für das echte Konto


def test_check_trust_rejects_forged_secret_for_a_real_device_id():
    """Ein manipuliertes Cookie mit einer echten Zeilen-ID, aber falschem Geheimnis -- der
    Hash-Vergleich (nicht nur die ID) entscheidet."""
    db = db_session()
    admin = make_admin(db)
    cookie = device_trust.create_trust(db, admin)
    device_id = base64.urlsafe_b64decode(cookie.encode()).decode().split(":", 1)[0]
    forged = base64.urlsafe_b64encode(f"{device_id}:falsches-geheimnis-erraten".encode()).decode()
    assert device_trust.check_trust(db, admin, forged) is False


def test_revoke_all_only_deletes_the_given_users_devices():
    db = db_session()
    admin_a = make_admin(db, "widerruf.a")
    admin_b = make_admin(db, "widerruf.b")
    cookie_a = device_trust.create_trust(db, admin_a)
    cookie_b = device_trust.create_trust(db, admin_b)
    device_trust.revoke_all(db, admin_a)
    assert device_trust.check_trust(db, admin_a, cookie_a) is False
    assert device_trust.check_trust(db, admin_b, cookie_b) is True  # anderes Konto unangetastet


def test_revoke_all_removes_multiple_devices_of_the_same_account():
    db = db_session()
    admin = make_admin(db)
    cookie_1 = device_trust.create_trust(db, admin)
    cookie_2 = device_trust.create_trust(db, admin)
    device_trust.revoke_all(db, admin)
    assert device_trust.check_trust(db, admin, cookie_1) is False
    assert device_trust.check_trust(db, admin, cookie_2) is False


# --- Ende-zu-Ende über echte Cookies (TestClient), Muster test_v250_two_factor_auth ------------

def _make_test_app():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    make_session = sessionmaker(bind=engine)

    app = FastAPI()
    app.include_router(auth_router_module.router)
    app.include_router(account_router_module.router)
    app.include_router(users_router_module.router)
    app.dependency_overrides[get_db] = lambda: make_session()

    @app.middleware("http")
    async def _identity_and_two_factor_gate(request: Request, call_next):
        mw_db = make_session()
        try:
            user = user_from_request(mw_db, request)
        finally:
            mw_db.close()
        request.state.erp_user = user
        otp_ok = True
        if user is not None and user.role == "admin":
            otp_ok = otp_ok_for_user(request, user.id)
        request.state.otp_ok = otp_ok
        if user is not None and not otp_ok and _blocked_pending_two_factor(request.url.path):
            return JSONResponse(status_code=401, content={"detail": "Zwei-Faktor-Bestätigung ausstehend.", "two_factor_pending": True})
        return await call_next(request)

    return app, make_session


def _configured_admin(db, username):
    admin = make_admin(db, username)
    setup = two_factor.start_setup(db, admin)
    two_factor.confirm_setup(db, admin, make_valid_code(setup["secret"]))
    return admin, setup["secret"]


def _login_and_trust(app, username, password, secret):
    """Loggt ein, bestätigt den Code mit gesetztem "Diesem Gerät vertrauen"-Häkchen -- liefert
    (client, trust_cookie_wert)."""
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200
    verify = client.post("/api/account/2fa/verify", json={"code": make_valid_code(secret), "trust_device": True})
    assert verify.status_code == 200
    trust_value = client.cookies.get(device_trust.TRUST_COOKIE_NAME)
    assert trust_value
    return client, trust_value


def _login_with_trust_cookie(app, username, password, trust_value):
    """Simuliert eine neue Browsersitzung auf demselben Gerät -- neuer Client (leerer
    Cookie-Speicher), aber mit dem zuvor gesetzten dk_erp_trust-Cookie."""
    client = TestClient(app)
    client.cookies.set(device_trust.TRUST_COOKIE_NAME, trust_value)
    login = client.post("/api/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200
    return client, login


def _assert_trust_now_invalid(app, username, trust_value, password=PASSWORD):
    client, login = _login_with_trust_cookie(app, username, password, trust_value)
    assert login.json()["otp_ok"] is False
    status = client.get("/api/auth/status")
    assert status.json()["otp_ok"] is False


def test_trusted_device_skips_code_on_next_login():
    app, make_session = _make_test_app()
    db = make_session()
    admin, secret = _configured_admin(db, "vertrauen.test")
    _, trust_value = _login_and_trust(app, "vertrauen.test", PASSWORD, secret)

    client, login = _login_with_trust_cookie(app, "vertrauen.test", PASSWORD, trust_value)
    assert login.json()["otp_ok"] is True
    status = client.get("/api/auth/status")
    assert status.json()["otp_ok"] is True


def test_unchecked_checkbox_creates_no_trust():
    app, make_session = _make_test_app()
    db = make_session()
    admin, secret = _configured_admin(db, "ohne.haekchen")
    client = TestClient(app)
    client.post("/api/auth/login", json={"username": "ohne.haekchen", "password": PASSWORD})
    verify = client.post("/api/account/2fa/verify", json={"code": make_valid_code(secret)})  # trust_device Standard False
    assert verify.status_code == 200
    assert device_trust.TRUST_COOKIE_NAME not in client.cookies
    assert db.scalar(select(TrustedDevice).where(TrustedDevice.user_id == admin.id)) is None


def test_setup_confirm_never_creates_trust_even_if_the_field_is_smuggled_in():
    """Die Ersteinrichtung nutzt TwoFactorCodeRequest, das gar kein trust_device-Feld kennt --
    ein untergeschobenes Feld im JSON-Body wird von Pydantic stillschweigend ignoriert, in
    KEINEM Fall entsteht dabei ein vertrautes Gerät."""
    app, make_session = _make_test_app()
    db = make_session()
    admin = make_admin(db, "erst.einrichtung")
    client = TestClient(app)
    client.post("/api/auth/login", json={"username": "erst.einrichtung", "password": PASSWORD})
    setup = client.post("/api/account/2fa/setup/start")
    secret = setup.json()["secret"]
    confirm = client.post("/api/account/2fa/setup/confirm", json={"code": make_valid_code(secret), "trust_device": True})
    assert confirm.status_code == 200
    assert device_trust.TRUST_COOKIE_NAME not in client.cookies
    assert db.scalar(select(TrustedDevice).where(TrustedDevice.user_id == admin.id)) is None


# --- Angriffstest: gefälschtes/manipuliertes Cookie, kontenübergreifend -----------------------

def test_forged_trust_cookie_is_rejected_on_login():
    app, make_session = _make_test_app()
    db = make_session()
    admin, secret = _configured_admin(db, "faelschung.test")
    _, trust_value = _login_and_trust(app, "faelschung.test", PASSWORD, secret)

    device_id = base64.urlsafe_b64decode(trust_value.encode()).decode().split(":", 1)[0]
    forged = base64.urlsafe_b64encode(f"{device_id}:falsches-geheimnis-1234567890".encode()).decode()

    client, login = _login_with_trust_cookie(app, "faelschung.test", PASSWORD, forged)
    assert login.json()["otp_ok"] is False
    assert client.get("/api/auth/status").json()["otp_ok"] is False


def test_garbage_trust_cookie_is_rejected_on_login():
    app, make_session = _make_test_app()
    db = make_session()
    _configured_admin(db, "kauderwelsch.test")
    client, login = _login_with_trust_cookie(app, "kauderwelsch.test", PASSWORD, "!!!kein-gueltiges-cookie!!!")
    assert login.json()["otp_ok"] is False


def test_trust_cookie_never_grants_access_to_a_different_account():
    app, make_session = _make_test_app()
    db = make_session()
    admin_a, secret_a = _configured_admin(db, "konto.a")
    _configured_admin(db, "konto.b")
    _, trust_a = _login_and_trust(app, "konto.a", PASSWORD, secret_a)

    # Konto B versucht sich mit dem Trust-Cookie von Konto A anzumelden:
    client, login = _login_with_trust_cookie(app, "konto.b", PASSWORD, trust_a)
    assert login.json()["otp_ok"] is False
    assert client.get("/api/auth/status").json()["otp_ok"] is False

    # Konto A selbst funktioniert mit demselben Cookie weiterhin:
    client_a, login_a = _login_with_trust_cookie(app, "konto.a", PASSWORD, trust_a)
    assert login_a.json()["otp_ok"] is True


# --- Die fünf Widerrufsstellen, jede einzeln --------------------------------------------------

def _load_reset_script_module():
    script_path = Path(__file__).parents[1] / "scripts" / "reset_admin_2fa.py"
    spec = importlib.util.spec_from_file_location("reset_admin_2fa_under_test_device_trust", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_site_1_admin_reset_two_factor_endpoint_invalidates_trust():
    app, make_session = _make_test_app()
    db = make_session()
    target, secret = _configured_admin(db, "site1.ziel")
    acting_admin = make_admin(db, "site1.handelnd")
    _, trust_value = _login_and_trust(app, "site1.ziel", PASSWORD, secret)

    reset_user_two_factor(target.id, db, current=acting_admin)

    assert device_trust.check_trust(db, target, trust_value) is False
    assert db.scalars(select(TrustedDevice).where(TrustedDevice.user_id == target.id)).all() == []
    _assert_trust_now_invalid(app, "site1.ziel", trust_value)


def test_site_2_cli_emergency_script_invalidates_trust(monkeypatch):
    app, make_session = _make_test_app()
    db = make_session()
    target, secret = _configured_admin(db, "site2.ziel")
    _, trust_value = _login_and_trust(app, "site2.ziel", PASSWORD, secret)

    module = _load_reset_script_module()
    module.SessionLocal = lambda: db
    monkeypatch.setattr("sys.argv", ["reset_admin_2fa.py", "site2.ziel", "--yes"])
    exit_code = module.main()
    assert exit_code == 0

    assert device_trust.check_trust(db, target, trust_value) is False
    assert db.scalars(select(TrustedDevice).where(TrustedDevice.user_id == target.id)).all() == []
    _assert_trust_now_invalid(app, "site2.ziel", trust_value)


def test_site_3_self_service_password_change_invalidates_trust():
    app, make_session = _make_test_app()
    db = make_session()
    admin, secret = _configured_admin(db, "site3.selbst")
    client, trust_value = _login_and_trust(app, "site3.selbst", PASSWORD, secret)

    changed = client.post("/api/account/change-password", json={"current_password": PASSWORD, "new_password": "NeuesPasswort456"})
    assert changed.status_code == 200

    assert device_trust.check_trust(db, admin, trust_value) is False
    assert db.scalars(select(TrustedDevice).where(TrustedDevice.user_id == admin.id)).all() == []
    _assert_trust_now_invalid(app, "site3.selbst", trust_value, password="NeuesPasswort456")


def test_site_4_admin_sets_password_for_another_user_invalidates_trust():
    app, make_session = _make_test_app()
    db = make_session()
    target, secret = _configured_admin(db, "site4.ziel")
    acting_admin = make_admin(db, "site4.handelnd")
    _, trust_value = _login_and_trust(app, "site4.ziel", PASSWORD, secret)

    payload = AppUserUpdate(
        username="site4.ziel", display_name=target.display_name, employee_id=None,
        role="admin", active=True, new_password="AdminGesetztesPW1",
    )
    update_app_user(target.id, payload, db, current=acting_admin)

    assert device_trust.check_trust(db, target, trust_value) is False
    assert db.scalars(select(TrustedDevice).where(TrustedDevice.user_id == target.id)).all() == []
    _assert_trust_now_invalid(app, "site4.ziel", trust_value, password="AdminGesetztesPW1")


def test_site_4_updating_unrelated_fields_without_a_new_password_leaves_trust_intact():
    """Gegenprobe zu Standort 4: ändert ein Admin NUR den Anzeigenamen (kein new_password), darf
    das vertraute Gerät nicht angetastet werden -- die Revokation hängt am Passwort, nicht an
    jeder Änderung des Datensatzes."""
    app, make_session = _make_test_app()
    db = make_session()
    target, secret = _configured_admin(db, "site4.unveraendert")
    acting_admin = make_admin(db, "site4.unveraendert.handelnd")
    _, trust_value = _login_and_trust(app, "site4.unveraendert", PASSWORD, secret)

    payload = AppUserUpdate(
        username="site4.unveraendert", display_name="Neuer Anzeigename", employee_id=None,
        role="admin", active=True, new_password=None,
    )
    update_app_user(target.id, payload, db, current=acting_admin)

    assert device_trust.check_trust(db, target, trust_value) is True
    client, login = _login_with_trust_cookie(app, "site4.unveraendert", PASSWORD, trust_value)
    assert login.json()["otp_ok"] is True


def test_site_5_explicit_revoke_button_invalidates_trust():
    app, make_session = _make_test_app()
    db = make_session()
    admin, secret = _configured_admin(db, "site5.widerruf")
    client, trust_value = _login_and_trust(app, "site5.widerruf", PASSWORD, secret)

    revoke = client.post("/api/account/trusted-devices/revoke-all")
    assert revoke.status_code == 200

    assert device_trust.check_trust(db, admin, trust_value) is False
    assert db.scalars(select(TrustedDevice).where(TrustedDevice.user_id == admin.id)).all() == []
    _assert_trust_now_invalid(app, "site5.widerruf", trust_value)


def test_revoke_all_button_only_affects_the_own_account_not_others():
    app, make_session = _make_test_app()
    db = make_session()
    admin_a, secret_a = _configured_admin(db, "widerruf.eigenes")
    admin_b, secret_b = _configured_admin(db, "widerruf.fremdes")
    client_a, trust_a = _login_and_trust(app, "widerruf.eigenes", PASSWORD, secret_a)
    _, trust_b = _login_and_trust(app, "widerruf.fremdes", PASSWORD, secret_b)

    client_a.post("/api/account/trusted-devices/revoke-all")

    assert device_trust.check_trust(db, admin_a, trust_a) is False
    assert device_trust.check_trust(db, admin_b, trust_b) is True
