import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import auth as auth_module
from app.auth import authenticate, hash_password, is_login_locked, _clear_failed_logins
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
    _clear_failed_logins(username)  # unabhängig von evtl. vorheriger Testreihenfolge
    return user


def test_login_locks_after_too_many_wrong_passwords():
    db = db_session()
    make_user(db, "lockout.test")
    for _ in range(auth_module.MAX_LOGIN_ATTEMPTS):
        assert authenticate(db, "lockout.test", "FalschesPasswort") is None
    # Selbst mit dem richtigen Passwort jetzt gesperrt:
    assert authenticate(db, "lockout.test", "RichtigesPasswort123") is None
    assert is_login_locked("lockout.test") is not None
    _clear_failed_logins("lockout.test")


def test_successful_login_clears_failed_attempts():
    db = db_session()
    make_user(db, "clear.test")
    for _ in range(auth_module.MAX_LOGIN_ATTEMPTS - 1):
        assert authenticate(db, "clear.test", "FalschesPasswort") is None
    assert is_login_locked("clear.test") is None  # ein Versuch unter dem Limit

    assert authenticate(db, "clear.test", "RichtigesPasswort123") is not None
    assert is_login_locked("clear.test") is None

    # Zähler beginnt nach erfolgreichem Login wieder bei null:
    for _ in range(auth_module.MAX_LOGIN_ATTEMPTS - 1):
        assert authenticate(db, "clear.test", "FalschesPasswort") is None
    assert is_login_locked("clear.test") is None
    _clear_failed_logins("clear.test")


def test_lockout_is_per_username_not_global():
    db = db_session()
    make_user(db, "user.a")
    make_user(db, "user.b")
    for _ in range(auth_module.MAX_LOGIN_ATTEMPTS):
        authenticate(db, "user.a", "falsch")
    assert is_login_locked("user.a") is not None
    assert is_login_locked("user.b") is None
    assert authenticate(db, "user.b", "RichtigesPasswort123") is not None
    _clear_failed_logins("user.a")


def test_login_route_returns_429_with_wait_time_when_locked():
    db = db_session()
    make_user(db, "route.test")
    for _ in range(auth_module.MAX_LOGIN_ATTEMPTS):
        with pytest.raises(HTTPException) as exc:
            auth_login(LoginRequest(username="route.test", password="falsch"), db)
        assert exc.value.status_code == 401
    with pytest.raises(HTTPException) as exc:
        auth_login(LoginRequest(username="route.test", password="RichtigesPasswort123"), db)
    assert exc.value.status_code == 429
    assert "Sekunden" in exc.value.detail
    _clear_failed_logins("route.test")


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
