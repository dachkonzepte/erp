import base64
import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from . import login_security
from .models import AppUser
from .paths import data_dir

COOKIE_NAME = "dk_erp_auth"
COOKIE_MAX_AGE = 60 * 60 * 12

# Zweites, unabhängiges Cookie: belegt, dass für DIESE Sitzung bereits ein zweiter Faktor
# bestätigt wurde (seit 1.3.34, siehe CLAUDE.md "Zwei-Faktor-Authentifizierung für
# Administratoren"). Bewusst ein eigenes Cookie statt eines zusätzlichen Felds im bestehenden
# dk_erp_auth-Cookie -- ändert an make_cookie()/parse_cookie()/user_from_request() nichts,
# betrifft ausschließlich Administratoren, für die role-abhängig geprüft wird. Trägt ein eigenes
# HMAC-Namespace-Präfix ("otp:"), damit eine signierte otp-Nutzlast nicht als normales
# Anmelde-Cookie durchgehen könnte, obwohl beide denselben secret_key() nutzen.
OTP_COOKIE_NAME = "dk_erp_otp_ok"


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


def make_otp_ok_cookie(user_id: int) -> str:
    expiry = int(time.time()) + COOKIE_MAX_AGE
    payload = f"{user_id}:{expiry}"
    sig = hmac.new(secret_key(), ("otp:" + payload).encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()


def otp_ok_for_user(request, user_id: int) -> bool:
    """Ob FÜR DIESE SITZUNG bereits ein zweiter Faktor bestätigt wurde -- geprüft gegen das
    separate OTP_COOKIE_NAME-Cookie, nicht gegen einen Zustand auf dem Benutzerdatensatz selbst
    (sonst würde eine einzige bestätigte Sitzung alle Geräte/Sitzungen mit freischalten)."""
    value = request.cookies.get(OTP_COOKIE_NAME)
    if not value:
        return False
    try:
        raw = base64.urlsafe_b64decode(value.encode()).decode()
        user_id_s, expiry_s, sig = raw.split(":", 2)
        payload = f"{user_id_s}:{expiry_s}"
        expected = hmac.new(secret_key(), ("otp:" + payload).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected) or int(expiry_s) < int(time.time()):
            return False
        return int(user_id_s) == user_id
    except Exception:
        return False


def users_exist(db) -> bool:
    return db.scalar(select(AppUser.id).limit(1)) is not None


def two_factor_required(user: AppUser) -> bool:
    return user.role == "admin"


def authenticate(db, username: str, password: str, client_ip: str | None = None):
    if login_security.login_lockout_seconds(db, username, client_ip) is not None:
        logger.warning("Login für '%s' abgelehnt: Benutzername oder IP ist derzeit gesperrt.", username.strip())
        return None
    user = db.scalar(select(AppUser).where(AppUser.username == username.strip()))
    if user is None or not user.active or not verify_password(password, user.password_hash):
        login_security.register_failed_login(db, username, client_ip)
        logger.warning("Fehlgeschlagener Login-Versuch für Benutzername '%s'.", username.strip())
        return None
    login_security.clear_failed_login(db, username)
    user.last_login_at = datetime.utcnow()
    db.commit()
    return user
