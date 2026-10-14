import base64
import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from . import login_security
from .models import AppUser, Employee
from .paths import data_dir

# Seit 1.8.98 trägt dk_erp_auth den Zufallswert einer Sitzung auf dem Server (app/sitzungen.py, app/models.py::UserSession) --
# bis 1.8.97 Benutzer-ID, Ablauf und HMAC (zustandslos: Abmelden beendete nichts auf dem Server). Gültigkeit fest 12 h.
COOKIE_NAME = "dk_erp_auth"
COOKIE_MAX_AGE = 60 * 60 * 12

# Bis 1.8.97 ein zweites Cookie für den bestätigten zweiten Faktor (an den Benutzer gebunden, nicht an die Sitzung -- es ließ sich
# in eine neue Anmeldung mitnehmen). Seit 1.8.98 steht das an der Sitzung (UserSession.second_factor_at); der Name bleibt nur, damit
# Anmelden und Abmelden ein noch vorhandenes altes Cookie löschen.
OTP_COOKIE_NAME = "dk_erp_otp_ok"


def _parse_bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes")


# Seit 1.8.104 (Vorgabe vom 14.10.2026, Punkt 5): in Produktion (ERP_ENV=production) immer Secure -- ohne Schalter, auch mit
# ERP_COOKIE_SECURE=0; der Server läuft nur über HTTPS, ein Aufruf über http (vor der Umleitung) bekommt kein Cookie mehr. Außerhalb
# der Produktion (lokal über reines HTTP, Klicktests) aus, per ERP_COOKIE_SECURE=1 einschaltbar. Gilt für das Anmelde-Cookie und das
# Cookie "vertrautes Gerät".
IS_PRODUCTION = os.getenv("ERP_ENV", "development") == "production"
COOKIE_SECURE = IS_PRODUCTION or _parse_bool_env("ERP_COOKIE_SECURE")

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


def resolve_account_display(db, user: AppUser) -> dict:
    """Liefert vollen Namen und Initialen für den Kontoknopf der Topbar (seit 1.3.45, siehe
    CLAUDE.md "Umgestaltung der Sidebar") -- bevorzugt aus dem über AppUser.employee_id (seit
    1.3.34) verknüpften Employee (first_name/last_name), da AppUser.display_name ein einzelnes
    Freitextfeld ist, das sich nicht zuverlässig in zwei Initialen zerlegen lässt ("Tobias
    Rödchen" -> "TR" braucht die getrennten Namensteile, nicht irgendeinen Anzeigetext). Fehlt
    die Verknüpfung (oder zeigt sie ins Leere, z. B. ein gelöschter Mitarbeiter), fällt es auf
    den Benutzernamen zurück."""
    full_name = None
    if user.employee_id:
        employee = db.get(Employee, user.employee_id)
        if employee is not None:
            full_name = f"{employee.first_name} {employee.last_name}".strip()
    if not full_name:
        full_name = user.username
    parts = full_name.split()
    if len(parts) >= 2:
        initials = (parts[0][0] + parts[-1][0]).upper()
    elif parts and parts[0]:
        initials = parts[0][:2].upper()
    else:
        initials = "?"
    return {"full_name": full_name, "initials": initials}


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
