"""Version 1.3.34 -- Selbstbedienungsseite "Mein Konto" (app/routers/account.py,
app/templates/account.html). Vorher konnte niemand das eigene Passwort selbst ändern -- nur ein
Administrator konnte das Passwort eines ANDEREN Kontos setzen (routers/users.py). Siehe
CLAUDE.md "Zwei-Faktor-Authentifizierung für Administratoren"."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import two_factor
from app.auth import hash_password, verify_password
from app.models import AppUser
from app.routers.account import change_password
from app.schemas import ChangePasswordRequest
from tests.test_v153_mahnwesen import db_session


def make_user(db, username="selbst.test", password="AltesPasswort123", role="user"):
    user = AppUser(username=username, display_name=username, role=role, active=True,
                    password_hash=hash_password(password))
    db.add(user); db.commit()
    return user


def _request_for(user):
    return SimpleNamespace(state=SimpleNamespace(erp_user=user))


def test_change_password_requires_correct_current_password():
    db = db_session()
    user = make_user(db)
    with pytest.raises(HTTPException) as exc:
        change_password(ChangePasswordRequest(current_password="Falsch123", new_password="NeuesPasswort123"), _request_for(user), db)
    assert exc.value.status_code == 401
    assert verify_password("AltesPasswort123", user.password_hash)  # unverändert


def test_change_password_succeeds_and_new_password_works():
    db = db_session()
    user = make_user(db)
    change_password(ChangePasswordRequest(current_password="AltesPasswort123", new_password="NeuesPasswort123"), _request_for(user), db)
    assert verify_password("NeuesPasswort123", user.password_hash)
    assert not verify_password("AltesPasswort123", user.password_hash)


def test_change_password_works_for_non_admin_users_too():
    """Der eigentliche Kern der Anfrage: bisher konnte NIEMAND sein eigenes Passwort ändern --
    nicht nur Administratoren profitieren von der neuen Selbstbedienung."""
    db = db_session()
    user = make_user(db, role="user")
    change_password(ChangePasswordRequest(current_password="AltesPasswort123", new_password="AndereNeueOne1"), _request_for(user), db)
    assert verify_password("AndereNeueOne1", user.password_hash)


def test_change_password_requires_login():
    db = db_session()
    with pytest.raises(HTTPException) as exc:
        change_password(ChangePasswordRequest(current_password="x", new_password="beliebig123"), _request_for(None), db)
    assert exc.value.status_code == 401


# --- Seite selbst: Struktur/Verdrahtung geprüft, Muster wie test_v163_sidebar_login_status ----

def test_account_page_references_all_required_endpoints():
    html = (Path(__file__).parents[1] / "app" / "templates" / "account.html").read_text(encoding="utf-8")
    for endpoint in ("/api/auth/status", "/api/account/change-password", "/api/account/2fa/setup/start",
                     "/api/account/2fa/setup/confirm", "/api/account/2fa/verify"):
        assert endpoint in html


def test_account_page_shows_recovery_codes_only_once_with_print_option():
    html = (Path(__file__).parents[1] / "app" / "templates" / "account.html").read_text(encoding="utf-8")
    assert "recovery_codes" in html
    assert "window.print()" in html


def test_sidebar_links_to_account_page():
    html = (Path(__file__).parents[1] / "app" / "templates" / "_sidebar.html").read_text(encoding="utf-8")
    assert 'href="/account"' in html


def test_sidebar_redirects_to_account_when_two_factor_pending():
    html = (Path(__file__).parents[1] / "app" / "templates" / "_sidebar.html").read_text(encoding="utf-8")
    assert "two_factor_required" in html
    assert "otp_ok" in html


def test_users_page_has_sole_admin_warning_and_reset_button():
    html = (Path(__file__).parents[1] / "app" / "templates" / "users.html").read_text(encoding="utf-8")
    assert "soleAdminWarning" in html
    assert "reset-two-factor" in html


# --- scripts/reset_admin_2fa.py -------------------------------------------------------------
# main() wird direkt aufgerufen, NIE über "python scripts/reset_admin_2fa.py" als Subprozess --
# das Skript-Modul wird geladen und seine SessionLocal danach durch eine isolierte
# Test-Datenbank ersetzt, damit garantiert nie die echte, konfigurierte DATABASE_URL berührt
# wird (Muster wie bei den Migrations-Testdateien, siehe CLAUDE.md "Testen").

def _load_script_module():
    import importlib.util
    script_path = Path(__file__).parents[1] / "scripts" / "reset_admin_2fa.py"
    spec = importlib.util.spec_from_file_location("reset_admin_2fa_under_test", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_configured_admin(db, username):
    import pyotp
    from app import two_factor as two_factor_module
    admin = AppUser(username=username, display_name=username, role="admin", active=True,
                    password_hash=hash_password("RichtigesPasswort123"))
    db.add(admin); db.commit()
    setup = two_factor_module.start_setup(db, admin)
    two_factor_module.confirm_setup(db, admin, pyotp.TOTP(setup["secret"]).now())
    return admin


def test_reset_admin_2fa_script_with_yes_flag_resets_without_prompting(monkeypatch):
    db = db_session()
    admin = _make_configured_admin(db, "skript.mit.yes")
    module = _load_script_module()
    module.SessionLocal = lambda: db
    monkeypatch.setattr("sys.argv", ["reset_admin_2fa.py", "skript.mit.yes", "--yes"])

    exit_code = module.main()

    assert exit_code == 0
    assert two_factor.is_configured(admin) is False


def test_reset_admin_2fa_script_aborts_on_wrong_confirmation(monkeypatch):
    db = db_session()
    admin = _make_configured_admin(db, "skript.falsche.bestaetigung")
    module = _load_script_module()
    module.SessionLocal = lambda: db
    monkeypatch.setattr("sys.argv", ["reset_admin_2fa.py", "skript.falsche.bestaetigung"])
    monkeypatch.setattr("builtins.input", lambda prompt="": "falscher-name")

    exit_code = module.main()

    assert exit_code == 1
    assert two_factor.is_configured(admin) is True  # unverändert -- nichts wurde zurückgesetzt


def test_reset_admin_2fa_script_proceeds_on_correct_confirmation(monkeypatch):
    db = db_session()
    admin = _make_configured_admin(db, "skript.korrekte.bestaetigung")
    module = _load_script_module()
    module.SessionLocal = lambda: db
    monkeypatch.setattr("sys.argv", ["reset_admin_2fa.py", "skript.korrekte.bestaetigung"])
    monkeypatch.setattr("builtins.input", lambda prompt="": "skript.korrekte.bestaetigung")

    exit_code = module.main()

    assert exit_code == 0
    assert two_factor.is_configured(admin) is False


def test_reset_admin_2fa_script_reports_unknown_username(monkeypatch):
    db = db_session()
    module = _load_script_module()
    module.SessionLocal = lambda: db
    monkeypatch.setattr("sys.argv", ["reset_admin_2fa.py", "gibt.es.nicht", "--yes"])

    exit_code = module.main()

    assert exit_code == 1
