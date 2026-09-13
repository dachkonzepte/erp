import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import login_security
from app.auth import authenticate, hash_password
from app.database import Base
from app.logging_config import configure_logging
from app.models import AppUser
from app.routers.auth import auth_login
from app.schemas import LoginRequest


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_user(db, username, password="RichtigesPasswort123"):
    user = AppUser(username=username, display_name=username, role="user", active=True,
                    password_hash=hash_password(password))
    db.add(user)
    db.commit()
    login_security.clear_failed_login(db, username)  # unabhängig von evtl. vorheriger Testreihenfolge
    return user


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    """Reicht für auth_login() -- nur .client.host wird gelesen."""
    def __init__(self, host="203.0.113.1"):
        self.client = _FakeClient(host)


def test_login_locks_after_too_many_wrong_passwords():
    db = db_session()
    make_user(db, "lockout.test")
    for _ in range(login_security.MAX_ATTEMPTS_PER_USER):
        assert authenticate(db, "lockout.test", "FalschesPasswort", "203.0.113.1") is None
    # Selbst mit dem richtigen Passwort jetzt gesperrt:
    assert authenticate(db, "lockout.test", "RichtigesPasswort123", "203.0.113.1") is None
    assert login_security.login_lockout_seconds(db, "lockout.test", "203.0.113.1") is not None
    login_security.clear_failed_login(db, "lockout.test")


def test_successful_login_clears_failed_attempts():
    db = db_session()
    make_user(db, "clear.test")
    for _ in range(login_security.MAX_ATTEMPTS_PER_USER - 1):
        assert authenticate(db, "clear.test", "FalschesPasswort", "203.0.113.2") is None
    assert login_security.login_lockout_seconds(db, "clear.test", "203.0.113.2") is None  # ein Versuch unter dem Limit

    assert authenticate(db, "clear.test", "RichtigesPasswort123", "203.0.113.2") is not None
    assert login_security.login_lockout_seconds(db, "clear.test", "203.0.113.2") is None

    # Zähler beginnt nach erfolgreichem Login wieder bei null:
    for _ in range(login_security.MAX_ATTEMPTS_PER_USER - 1):
        assert authenticate(db, "clear.test", "FalschesPasswort", "203.0.113.2") is None
    assert login_security.login_lockout_seconds(db, "clear.test", "203.0.113.2") is None
    login_security.clear_failed_login(db, "clear.test")


def test_lockout_is_per_username_not_global():
    db = db_session()
    make_user(db, "user.a")
    make_user(db, "user.b")
    for i in range(login_security.MAX_ATTEMPTS_PER_USER):
        authenticate(db, "user.a", "falsch", f"198.51.100.{i}")  # jeweils andere IP -- nur die Benutzernamen-Sperre soll greifen
    assert login_security.login_lockout_seconds(db, "user.a", None) is not None
    assert login_security.login_lockout_seconds(db, "user.b", None) is None
    assert authenticate(db, "user.b", "RichtigesPasswort123", "198.51.100.9") is not None
    login_security.clear_failed_login(db, "user.a")


def test_ip_lockout_blocks_rotating_usernames_from_one_address():
    """Der genaue, gemeldete Umgehungsweg: viele VERSCHIEDENE Benutzernamen von derselben
    Adresse durchprobieren -- keiner einzeln oft genug für die Benutzernamen-Sperre, aber in
    Summe genug für die IP-Sperre."""
    db = db_session()
    make_user(db, "echter.nutzer")
    for i in range(login_security.MAX_ATTEMPTS_PER_IP):
        authenticate(db, f"rateversuch{i}", "irgendwas", "192.0.2.50")
    assert login_security.login_lockout_seconds(db, "irgendein.neuer.name", "192.0.2.50") is not None
    # Auch der eigentliche, existierende Benutzer wird von derselben Adresse aus abgelehnt:
    assert authenticate(db, "echter.nutzer", "RichtigesPasswort123", "192.0.2.50") is None
    # Von einer ANDEREN Adresse ist er weiterhin nicht gesperrt:
    assert authenticate(db, "echter.nutzer", "RichtigesPasswort123", "203.0.113.99") is not None


def test_old_failed_attempts_are_cleaned_up_automatically():
    """Kein separater Aufräumjob -- register_failed_attempt() räumt bei jedem neuen
    Fehlversuch alte, für keine Sperre mehr relevante Zeilen mit auf (siehe
    FailedLoginAttempt-Docstring in app/models.py)."""
    from datetime import datetime, timedelta
    from app.models import FailedLoginAttempt

    db = db_session()
    old_bucket = login_security.user_bucket("uralt.test")
    db.add(FailedLoginAttempt(bucket=old_bucket, occurred_at=datetime.utcnow() - timedelta(days=3)))
    db.commit()
    assert db.query(FailedLoginAttempt).filter_by(bucket=old_bucket).count() == 1

    login_security.register_failed_attempt(db, login_security.user_bucket("jemand.anders"))

    assert db.query(FailedLoginAttempt).filter_by(bucket=old_bucket).count() == 0


def test_login_route_returns_429_with_wait_time_when_locked():
    db = db_session()
    make_user(db, "route.test")
    request = _FakeRequest("203.0.113.5")
    for _ in range(login_security.MAX_ATTEMPTS_PER_USER):
        with pytest.raises(HTTPException) as exc:
            auth_login(LoginRequest(username="route.test", password="falsch"), request, db)
        assert exc.value.status_code == 401
    with pytest.raises(HTTPException) as exc:
        auth_login(LoginRequest(username="route.test", password="RichtigesPasswort123"), request, db)
    assert exc.value.status_code == 429
    assert "Sekunden" in exc.value.detail
    login_security.clear_failed_login(db, "route.test")


def test_login_error_message_is_identical_for_unknown_username_and_wrong_password():
    """Darf nicht verraten, ob ein Benutzername überhaupt existiert."""
    db = db_session()
    make_user(db, "bekannt.test")
    request = _FakeRequest("203.0.113.6")
    with pytest.raises(HTTPException) as exc_unknown:
        auth_login(LoginRequest(username="gibt.es.nicht", password="beliebig"), request, db)
    with pytest.raises(HTTPException) as exc_wrong:
        auth_login(LoginRequest(username="bekannt.test", password="FalschesPasswort"), request, db)
    assert exc_unknown.value.status_code == exc_wrong.value.status_code == 401
    assert exc_unknown.value.detail == exc_wrong.value.detail == "Benutzername oder Passwort ist falsch."


def test_configure_logging_writes_file_and_is_idempotent(tmp_path, monkeypatch):
    import logging
    import logging.handlers

    # Isolation: app/main.py ruft configure_logging() bereits beim Import auf, und
    # da alle Tests denselben Prozess/Root-Logger teilen, hat dieser zu diesem
    # Zeitpunkt schon einen RotatingFileHandler auf die echte data/erp.log. Für
    # einen sauberen, von der Testreihenfolge unabhängigen Test daher die
    # bestehenden Handler sichern, zurücksetzen und danach wiederherstellen.
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    root.handlers = []
    try:
        monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path))
        configure_logging()
        configure_logging()  # zweiter Aufruf darf keinen zweiten Datei-Handler anhängen

        file_handlers = [h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(file_handlers) == 1

        logging.getLogger("test_v108").info("Testnachricht für Logging-Check")
        log_file = tmp_path / "erp.log"
        assert log_file.exists()
        assert "Testnachricht für Logging-Check" in log_file.read_text(encoding="utf-8")
    finally:
        root.handlers = saved_handlers
