import base64
import hashlib
import hmac
import logging
import os
import secrets
import threading
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from .models import AppUser
from .paths import data_dir

COOKIE_NAME = "dk_erp_auth"
COOKIE_MAX_AGE = 60 * 60 * 12


def _parse_bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes")


# Standardmäßig aus, da die App bislang über reines HTTP läuft -- Browser
# senden ein secure-Cookie sonst gar nicht erst mit. Sobald HTTPS eingerichtet
# ist (z. B. hinter einem Reverse-Proxy), per Umgebungsvariable aktivieren:
# ERP_COOKIE_SECURE=1
COOKIE_SECURE = _parse_bool_env("ERP_COOKIE_SECURE")

logger = logging.getLogger(__name__)

# --- Login-Schutz gegen Brute-Force (seit 1.0.8) -----------------------------
# Einfacher In-Memory-Zähler pro Benutzername: nach MAX_LOGIN_ATTEMPTS
# fehlgeschlagenen Versuchen innerhalb von LOGIN_LOCKOUT_SECONDS wird der
# Benutzername vorübergehend gesperrt -- auch bei danach korrektem Passwort.
# Bewusst kein DB-Feld dafür (kein Schema-Update nötig); der Zähler lebt nur
# für die Laufzeit des Prozesses, was für einen einzelnen uvicorn-Worker
# ausreicht. Ein threading.Lock schützt vor Race Conditions bei parallelen
# Anfragen.
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 60

_failed_login_attempts: dict[str, list[float]] = {}
_failed_login_lock = threading.Lock()


def _login_attempt_key(username: str) -> str:
    return username.strip().lower()


def is_login_locked(username: str) -> int | None:
    """None, wenn nicht gesperrt -- sonst verbleibende Sperrsekunden (>= 1)."""
    key = _login_attempt_key(username)
    now = time.time()
    cutoff = now - LOGIN_LOCKOUT_SECONDS
    with _failed_login_lock:
        attempts = [t for t in _failed_login_attempts.get(key, []) if t > cutoff]
        _failed_login_attempts[key] = attempts
        if len(attempts) >= MAX_LOGIN_ATTEMPTS:
            return max(int(attempts[0] + LOGIN_LOCKOUT_SECONDS - now), 1)
    return None


def _register_failed_login(username: str) -> None:
    key = _login_attempt_key(username)
    with _failed_login_lock:
        _failed_login_attempts.setdefault(key, []).append(time.time())


def _clear_failed_logins(username: str) -> None:
    key = _login_attempt_key(username)
    with _failed_login_lock:
        _failed_login_attempts.pop(key, None)


def _secret_path() -> Path:
    return data_dir() / ".erp_secret"


def secret_key() -> bytes:
    env = os.getenv("ERP_SECRET_KEY")
    if env:
        return env.encode("utf-8")
    p = _secret_path()
    if not p.exists():
        p.write_text(secrets.token_hex(32), encoding="utf-8")
    return p.read_text(encoding="utf-8").strip().encode("utf-8")


def warn_if_secret_key_mismatches_file() -> None:
    """Warnt beim Start, wenn ERP_SECRET_KEY gesetzt ist UND bereits eine
    data/.erp_secret-Datei existiert UND beide unterschiedlich sind -- kein
    Abbruch, nur ein Hinweis (siehe CLAUDE.md "Geheimnisse für den
    Serverbetrieb"). Ein abweichender Schlüssel ist z. B. bei einer frischen
    Testinstallation normal; auf einem Server, der eine bestehende Datenbank
    übernommen hat, ist es aber genau der Fall, der bereits verschlüsselte
    SMTP-/Microsoft-365-Zugangsdaten beim nächsten E-Mail-Versand unlesbar
    macht (decrypt_secret() schlägt dann fehl) -- der Hinweis hier kommt
    dafür schon beim Start, nicht erst beim ersten Versandversuch. Gibt den
    Schlüssel selbst nie aus, auch nicht gekürzt."""
    env = os.getenv("ERP_SECRET_KEY")
    if not env:
        return
    path = _secret_path()
    if not path.exists():
        return
    file_value = path.read_text(encoding="utf-8").strip()
    if file_value != env.strip():
        logger.warning(
            "ERP_SECRET_KEY unterscheidet sich vom Inhalt von %s. Falls hier bereits "
            "verschlüsselte SMTP-/Microsoft-365-Zugangsdaten aus einer übernommenen "
            "Datenbank liegen, sind diese mit dem aktuell aktiven Schlüssel (aus der "
            "Umgebungsvariable) nicht mehr lesbar. Bei einer frischen Installation ist "
            "das unbedenklich.",
            path,
        )


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Das Passwort muss mindestens 8 Zeichen lang sein.")
    salt = os.urandom(16)
    iterations = 260_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, it, salt64, digest64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt64)
        expected = base64.b64decode(digest64)
        got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(it))
        return hmac.compare_digest(got, expected)
    except Exception:
        return False


def make_cookie(user_id: int) -> str:
    expiry = int(time.time()) + COOKIE_MAX_AGE
    payload = f"{user_id}:{expiry}"
    sig = hmac.new(secret_key(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()


def parse_cookie(value: str | None) -> int | None:
    if not value:
        return None
    try:
        raw = base64.urlsafe_b64decode(value.encode()).decode()
        user_id_s, expiry_s, sig = raw.split(":", 2)
        payload = f"{user_id_s}:{expiry_s}"
        expected = hmac.new(secret_key(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected) or int(expiry_s) < int(time.time()):
            return None
        return int(user_id_s)
    except Exception:
        return None


def user_from_request(db, request):
    user_id = parse_cookie(request.cookies.get(COOKIE_NAME))
    if not user_id:
        return None
    user = db.get(AppUser, user_id)
    return user if user and user.active else None


def users_exist(db) -> bool:
    return db.scalar(select(AppUser.id).limit(1)) is not None


def authenticate(db, username: str, password: str):
    if is_login_locked(username) is not None:
        logger.warning("Login für '%s' abgelehnt: Benutzername ist derzeit gesperrt.", username.strip())
        return None
    user = db.scalar(select(AppUser).where(AppUser.username == username.strip()))
    if user is None or not user.active or not verify_password(password, user.password_hash):
        _register_failed_login(username)
        logger.warning("Fehlgeschlagener Login-Versuch für Benutzername '%s'.", username.strip())
        return None
    _clear_failed_logins(username)
    user.last_login_at = datetime.utcnow()
    db.commit()
    return user
