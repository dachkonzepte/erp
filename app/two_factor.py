"""Zwei-Faktor-Authentifizierung für Administratoren (TOTP, seit 1.3.34).

Zeitbasierte Einmalkennwörter (RFC 6238) über eine Authenticator-App -- kein SMS-Versand, keine
E-Mail-Codes, kein externer Dienst nötig. `pyotp` (MIT) erzeugt/prüft die Codes, `qrcode[pil]`
(BSD-3-Clause, zieht `pillow` als Extra -- bereits Pflichtabhängigkeit über ReportLab, kein neues
Gewicht) rendert den QR-Code als PNG. Beide reine Pip-Pakete ohne Systemabhängigkeit, wie bereits
bei pypdfium2 (siehe CLAUDE.md).

Das TOTP-Geheimnis wird wie das SMTP-Passwort verschlüsselt in der Datenbank abgelegt
(app/crypto.py::encrypt_secret()/decrypt_secret()) -- der Klartext muss zur Code-Prüfung
wiederherstellbar sein, anders als ein Benutzerpasswort. Wiederherstellungscodes dagegen werden
wie Benutzerpasswörter nur als Hash gespeichert (app/auth.py::hash_password()/verify_password())
-- sie werden nie zurückgelesen, nur einmal beim Verbrauch verglichen.

Nichts wird als aktiv (`AppUser.totp_confirmed_at`) markiert, bevor nicht ein echter, von der App
gelieferter Code erfolgreich geprüft wurde (siehe confirm_setup()) -- ein abgebrochener
Einrichtungsversuch (Fenster geschlossen, ohne zu bestätigen) hinterlässt dadurch nie einen halb
aktiven Zustand; ein erneuter Einrichtungsversuch überschreibt das vorherige, nie bestätigte
Geheimnis einfach mit einem neuen."""

import base64
import secrets
from datetime import datetime
from io import BytesIO

import pyotp
import qrcode
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import device_trust
from .auth import hash_password, verify_password
from .crypto import decrypt_secret, encrypt_secret
from .models import AppUser, TwoFactorRecoveryCode

ISSUER_NAME = "DACHKONZEPTE ERP"
RECOVERY_CODE_COUNT = 10


def is_required(user: AppUser) -> bool:
    return user.role == "admin"


def is_configured(user: AppUser) -> bool:
    return user.totp_confirmed_at is not None


def start_setup(db: Session, user: AppUser) -> dict:
    """Erzeugt ein neues, noch UNBESTÄTIGTES Geheimnis und überschreibt ein evtl. vorher
    begonnenes, nie bestätigtes -- sicher, da bis zur Bestätigung nichts aktiv ist."""
    secret = pyotp.random_base32()
    user.totp_secret_encrypted = encrypt_secret(secret)
    db.commit()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.username, issuer_name=ISSUER_NAME)
    return {"secret": secret, "provisioning_uri": uri, "qr_code_data_uri": _qr_code_data_uri(uri)}


def _qr_code_data_uri(data: str) -> str:
    img = qrcode.make(data)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def _verify_totp(user: AppUser, code: str) -> bool:
    if not user.totp_secret_encrypted:
        return False
    secret = decrypt_secret(user.totp_secret_encrypted)
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)


def confirm_setup(db: Session, user: AppUser, code: str) -> list[str] | None:
    """Prüft den ersten Code gegen das per start_setup() erzeugte, noch unbestätigte Geheimnis.
    Bei Erfolg: markiert die Einrichtung als aktiv, erzeugt die Wiederherstellungscodes und gibt
    sie EINMALIG im Klartext zurück (danach nie wieder abrufbar). Bei Misserfolg: None, nichts
    ändert sich -- der Aufrufer kann denselben oder einen neu erzeugten Code erneut versuchen."""
    if not _verify_totp(user, code):
        return None
    user.totp_confirmed_at = datetime.utcnow()
    codes = _generate_recovery_codes()
    for plain in codes:
        db.add(TwoFactorRecoveryCode(user_id=user.id, code_hash=hash_password(plain)))
    db.commit()
    return codes


def verify_login_code(db: Session, user: AppUser, code: str) -> bool:
    """Prüft einen Code beim regulären Login (nach bereits abgeschlossener Einrichtung) --
    entweder ein aktueller TOTP-Code oder ein noch nicht verbrauchter Wiederherstellungscode."""
    if _verify_totp(user, code):
        return True
    return _consume_recovery_code(db, user, code)


def _consume_recovery_code(db: Session, user: AppUser, code: str) -> bool:
    candidate = code.strip()
    if not candidate:
        return False
    open_codes = db.scalars(
        select(TwoFactorRecoveryCode).where(
            TwoFactorRecoveryCode.user_id == user.id, TwoFactorRecoveryCode.used_at.is_(None),
        )
    ).all()
    for row in open_codes:
        if verify_password(candidate, row.code_hash):
            row.used_at = datetime.utcnow()
            db.commit()
            return True
    return False


def _generate_recovery_codes(n: int = RECOVERY_CODE_COUNT) -> list[str]:
    return [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(n)]


def remaining_recovery_codes(db: Session, user: AppUser) -> int:
    return db.scalar(
        select(func.count(TwoFactorRecoveryCode.id)).where(
            TwoFactorRecoveryCode.user_id == user.id, TwoFactorRecoveryCode.used_at.is_(None),
        )
    ) or 0


def reset(db: Session, user: AppUser) -> None:
    """Setzt den zweiten Faktor vollständig zurück (Admin-Reset für ein ANDERES Konto, oder das
    Notfall-Kommandozeilenskript scripts/reset_admin_2fa.py) -- der Benutzer muss danach beim
    nächsten Login komplett neu einrichten, wie beim allerersten Mal. Löscht dabei auch ALLE
    vertrauten Geräte dieses Kontos (app/device_trust.py) -- ein zuvor vertrautes Gerät wäre
    sonst weiterhin gültig, obwohl der zweite Faktor, den es ersetzt, gerade entfernt wurde."""
    user.totp_secret_encrypted = None
    user.totp_confirmed_at = None
    for row in db.scalars(select(TwoFactorRecoveryCode).where(TwoFactorRecoveryCode.user_id == user.id)).all():
        db.delete(row)
    db.commit()
    device_trust.revoke_all(db, user)
