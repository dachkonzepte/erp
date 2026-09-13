"""Version 1.3.34 -- Zwei-Faktor-Authentifizierung (TOTP) für Administratoren.

Siehe CLAUDE.md "Zwei-Faktor-Authentifizierung für Administratoren" für den vollständigen
Ablauf inkl. der beiden vorab geklärten Sicherheitsfragen (Notfall-Reset, verpflichtende
Einrichtung ohne Selbstaussperrungsrisiko)."""

import pyotp
import pytest
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import login_security, two_factor
from app.auth import hash_password, otp_ok_for_user, user_from_request
from app.database import Base, get_db
from app.main import _blocked_pending_two_factor
from app.models import AppUser
from app.routers import account as account_router_module
from app.routers import auth as auth_router_module
from app.routers.users import reset_user_two_factor
from tests.test_v153_mahnwesen import db_session


def make_admin(db, username="admin.test", password="RichtigesPasswort123"):
    user = AppUser(username=username, display_name=username, role="admin", active=True,
                    password_hash=hash_password(password))
    db.add(user); db.commit()
    return user


def make_valid_code(secret: str) -> str:
    return pyotp.TOTP(secret).now()


# --- app/two_factor.py, isoliert -------------------------------------------------------------

def test_start_setup_returns_secret_uri_and_qr_code():
    db = db_session()
    admin = make_admin(db)
    result = two_factor.start_setup(db, admin)
    assert result["secret"]
    assert admin.username in result["provisioning_uri"]
    assert result["qr_code_data_uri"].startswith("data:image/png;base64,")
    assert admin.totp_secret_encrypted is not None
    assert admin.totp_confirmed_at is None  # noch nicht bestätigt


def test_confirm_setup_fails_with_wrong_code_and_changes_nothing():
    db = db_session()
    admin = make_admin(db)
    two_factor.start_setup(db, admin)
    assert two_factor.confirm_setup(db, admin, "000000") is None
    assert admin.totp_confirmed_at is None
    assert two_factor.remaining_recovery_codes(db, admin) == 0


def test_confirm_setup_succeeds_and_returns_recovery_codes_once():
    db = db_session()
    admin = make_admin(db)
    setup = two_factor.start_setup(db, admin)
    codes = two_factor.confirm_setup(db, admin, make_valid_code(setup["secret"]))
    assert codes is not None
    assert len(codes) == two_factor.RECOVERY_CODE_COUNT
    assert admin.totp_confirmed_at is not None
    assert two_factor.remaining_recovery_codes(db, admin) == two_factor.RECOVERY_CODE_COUNT


def test_verify_login_code_accepts_current_totp_code():
    db = db_session()
    admin = make_admin(db)
    setup = two_factor.start_setup(db, admin)
    two_factor.confirm_setup(db, admin, make_valid_code(setup["secret"]))
    assert two_factor.verify_login_code(db, admin, make_valid_code(setup["secret"])) is True


def test_recovery_code_works_exactly_once():
    db = db_session()
    admin = make_admin(db)
    setup = two_factor.start_setup(db, admin)
    codes = two_factor.confirm_setup(db, admin, make_valid_code(setup["secret"]))
    one = codes[0]
    assert two_factor.verify_login_code(db, admin, one) is True
    assert two_factor.remaining_recovery_codes(db, admin) == len(codes) - 1
    assert two_factor.verify_login_code(db, admin, one) is False  # ein zweites Mal nicht mehr


def test_reset_clears_secret_and_all_recovery_codes():
    db = db_session()
    admin = make_admin(db)
    setup = two_factor.start_setup(db, admin)
    two_factor.confirm_setup(db, admin, make_valid_code(setup["secret"]))
    two_factor.reset(db, admin)
    assert admin.totp_secret_encrypted is None
    assert admin.totp_confirmed_at is None
    assert two_factor.remaining_recovery_codes(db, admin) == 0


# --- Ergänzung 4: abgebrochene Einrichtung hinterlässt keinen halb aktiven Zustand ------------

def test_abandoned_setup_leaves_no_half_active_state_and_retry_works():
    """Fenster geschlossen, ohne den ersten Code zu bestätigen: nichts wird aktiv, ein neuer
    Einrichtungsversuch überschreibt das alte, nie bestätigte Geheimnis einfach -- ein Code aus
    dem ABGEBROCHENEN ersten Versuch darf danach nicht mehr funktionieren, nur einer aus dem
    zweiten."""
    db = db_session()
    admin = make_admin(db)

    first_attempt = two_factor.start_setup(db, admin)
    # Fenster geschlossen, nie bestätigt -- admin.totp_confirmed_at bleibt None.
    assert admin.totp_confirmed_at is None
    assert two_factor.is_configured(admin) is False

    # Nächster Login: derselbe Ablauf beginnt einfach neu (setup/start erneut aufgerufen).
    second_attempt = two_factor.start_setup(db, admin)
    assert second_attempt["secret"] != first_attempt["secret"]

    # Ein Code aus dem abgebrochenen ersten Versuch funktioniert nicht mehr:
    stale_code = make_valid_code(first_attempt["secret"])
    assert two_factor.confirm_setup(db, admin, stale_code) is None
    assert two_factor.is_configured(admin) is False

    # Ein Code aus dem zweiten, tatsächlich genutzten Versuch funktioniert:
    codes = two_factor.confirm_setup(db, admin, make_valid_code(second_attempt["secret"]))
    assert codes is not None
    assert two_factor.is_configured(admin) is True


# --- Admin setzt ANDEREN Admin zurück, nie den eigenen (routers/users.py) ---------------------

def test_admin_can_reset_another_admins_two_factor():
    db = db_session()
    acting_admin = make_admin(db, "acting.admin")
    other_admin = make_admin(db, "other.admin")
    setup = two_factor.start_setup(db, other_admin)
    two_factor.confirm_setup(db, other_admin, make_valid_code(setup["secret"]))
    assert two_factor.is_configured(other_admin) is True

    reset_user_two_factor(other_admin.id, db, current=acting_admin)

    assert two_factor.is_configured(other_admin) is False


def test_admin_cannot_reset_own_two_factor():
    db = db_session()
    admin = make_admin(db)
    setup = two_factor.start_setup(db, admin)
    two_factor.confirm_setup(db, admin, make_valid_code(setup["secret"]))

    with pytest.raises(HTTPException) as exc:
        reset_user_two_factor(admin.id, db, current=admin)
    assert exc.value.status_code == 409
    assert two_factor.is_configured(admin) is True  # unverändert


# --- Volle Anmeldung inkl. Middleware-Sperre, über echte Cookies (TestClient) -----------------
#
# Absichtlich MEHRERE, unabhängige Session-Objekte auf demselben Engine/derselben Verbindung --
# genau wie in der echten App (app/main.py's Middleware und jedes Depends(get_db) erzeugen je
# eine EIGENE SessionLocal()). Eine einzige, für Middleware UND Endpunkte gemeinsam
# wiederverwendete Session hätte einen echten Bug verdeckt (real aufgetreten, per Smoke-Test
# gegen eine echte Serverinstanz gefunden): app/routers/account.py mutierte ursprünglich direkt
# das über request.state.erp_user hereingereichte Objekt -- geladen von der (zu diesem
# Zeitpunkt bereits wieder geschlossenen) Middleware-Session -- und committete über die eigene,
# ANDERE Depends(get_db)-Session dieses Endpunkts. Die Änderung wurde dadurch nie persistiert,
# ohne dass irgendein Fehler auftrat. Behoben, indem _current_user() (account.py) das Objekt
# über db.get() in der jeweils richtigen Session neu lädt, statt das übergebene Objekt direkt
# zu verwenden. Dieser Testaufbau bildet genau diese Session-Trennung nach, damit ein
# künftiger Rückfall in dasselbe Muster wieder auffällt.

def _make_test_app():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    make_session = sessionmaker(bind=engine)

    app = FastAPI()
    app.include_router(auth_router_module.router)
    app.include_router(account_router_module.router)

    dummy = APIRouter()

    @dummy.get("/api/dummy/business-data")
    def _dummy_business_endpoint():
        return {"ok": True}

    app.include_router(dummy)
    # lambda statt make_session direkt -- FastAPI würde sonst versuchen, die Signatur des
    # sessionmaker-Objekts selbst als Dependency-Parameter zu interpretieren.
    app.dependency_overrides[get_db] = lambda: make_session()

    @app.middleware("http")
    async def _identity_and_two_factor_gate(request: Request, call_next):
        mw_db = make_session()  # ebenfalls eine EIGENE Session, wie in app/main.py
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

    return TestClient(app), make_session


def test_admin_without_two_factor_is_routed_through_mandatory_setup():
    client, make_session = _make_test_app()
    make_admin(make_session(), "frischer.admin")

    login = client.post("/api/auth/login", json={"username": "frischer.admin", "password": "RichtigesPasswort123"})
    assert login.status_code == 200
    assert login.json()["two_factor_required"] is True
    assert login.json()["two_factor_configured"] is False

    # Business-Endpunkt bleibt gesperrt, bis der zweite Faktor eingerichtet ist:
    blocked = client.get("/api/dummy/business-data")
    assert blocked.status_code == 401
    assert blocked.json()["two_factor_pending"] is True

    # Status-Abfrage selbst bleibt erreichbar (Frontend braucht sie, um die Sperre zu erkennen):
    status = client.get("/api/auth/status")
    assert status.status_code == 200
    assert status.json()["otp_ok"] is False

    setup = client.post("/api/account/2fa/setup/start")
    assert setup.status_code == 200
    secret = setup.json()["secret"]

    confirm = client.post("/api/account/2fa/setup/confirm", json={"code": make_valid_code(secret)})
    assert confirm.status_code == 200
    assert len(confirm.json()["recovery_codes"]) == two_factor.RECOVERY_CODE_COUNT

    unlocked = client.get("/api/dummy/business-data")
    assert unlocked.status_code == 200


def test_admin_with_existing_two_factor_must_verify_code_every_login():
    client, make_session = _make_test_app()
    setup_db = make_session()
    admin = make_admin(setup_db, "stammadmin")
    setup = two_factor.start_setup(setup_db, admin)
    two_factor.confirm_setup(setup_db, admin, make_valid_code(setup["secret"]))

    login = client.post("/api/auth/login", json={"username": "stammadmin", "password": "RichtigesPasswort123"})
    assert login.json()["two_factor_configured"] is True

    blocked = client.get("/api/dummy/business-data")
    assert blocked.status_code == 401

    wrong = client.post("/api/account/2fa/verify", json={"code": "000000"})
    assert wrong.status_code == 401

    still_blocked = client.get("/api/dummy/business-data")
    assert still_blocked.status_code == 401

    right = client.post("/api/account/2fa/verify", json={"code": make_valid_code(setup["secret"])})
    assert right.status_code == 200

    unlocked = client.get("/api/dummy/business-data")
    assert unlocked.status_code == 200


def test_non_admin_login_is_never_gated_by_two_factor():
    client, make_session = _make_test_app()
    setup_db = make_session()
    user = AppUser(username="normaler.nutzer", display_name="Normaler Nutzer", role="user", active=True,
                   password_hash=hash_password("RichtigesPasswort123"))
    setup_db.add(user); setup_db.commit()

    login = client.post("/api/auth/login", json={"username": "normaler.nutzer", "password": "RichtigesPasswort123"})
    assert login.json()["two_factor_required"] is False

    unblocked = client.get("/api/dummy/business-data")
    assert unblocked.status_code == 200


def test_two_factor_verify_locks_out_after_repeated_wrong_codes():
    client, make_session = _make_test_app()
    setup_db = make_session()
    admin = make_admin(setup_db, "code.rateversuche")
    setup = two_factor.start_setup(setup_db, admin)
    two_factor.confirm_setup(setup_db, admin, make_valid_code(setup["secret"]))
    client.post("/api/auth/login", json={"username": "code.rateversuche", "password": "RichtigesPasswort123"})

    for _ in range(login_security.MAX_ATTEMPTS_PER_TWO_FACTOR_USER):
        resp = client.post("/api/account/2fa/verify", json={"code": "000000"})
        assert resp.status_code == 401
    locked = client.post("/api/account/2fa/verify", json={"code": make_valid_code(setup["secret"])})
    assert locked.status_code == 429


def test_blocked_pending_two_factor_allowlists_exactly_the_bootstrap_endpoints():
    assert _blocked_pending_two_factor("/api/auth/status") is False
    assert _blocked_pending_two_factor("/api/auth/login") is False
    assert _blocked_pending_two_factor("/api/account/2fa/setup/start") is False
    assert _blocked_pending_two_factor("/api/account/2fa/setup/confirm") is False
    assert _blocked_pending_two_factor("/api/account/2fa/verify") is False
    assert _blocked_pending_two_factor("/api/account/change-password") is True
    assert _blocked_pending_two_factor("/api/employees") is True
    assert _blocked_pending_two_factor("/employees") is False  # Seiten-Gerüst, kein /api/
