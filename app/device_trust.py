"""Geräte-Vertrauen für die Zwei-Faktor-Authentifizierung ("Diesem Gerät für 30 Tage
vertrauen", seit 1.5.11, siehe CLAUDE.md "Zwei-Faktor-Authentifizierung").

Server-seitig verwaltet -- ein Cookie allein würde keinen Widerruf erlauben. Pro vertrautem Gerät
eine Zeile (app/models.py::TrustedDevice) mit einer Ablaufzeit; das zugehörige, signierte Cookie
(dk_erp_trust, eigenständig neben dk_erp_auth/dk_erp_otp_ok) trägt nur die Zeilen-ID plus ein
rohes, hochentropisches Geheimnis -- der Server vergleicht dieses Geheimnis gegen den in der
Zeile gespeicherten Hash (hash_password()/verify_password(), dieselbe Technik wie bei
Wiederherstellungscodes). Eine zusätzliche HMAC-Signatur des Cookies (wie bei dk_erp_auth/
dk_erp_otp_ok) ist hier nicht nötig: ein 256-Bit-Zufallsgeheimnis lässt sich nicht erraten, und
jede Manipulation des Cookies (fremde ID, falsches Geheimnis) scheitert bereits am
Hash-Vergleich bzw. am user_id-Abgleich in check_trust() -- das ist die eigentliche
Absicherung, keine zusätzliche Signatur nötig.

Die Gültigkeit ist FEST (30 Tage ab dem Setzen des Häkchens), keine gleitende Verlängerung bei
jeder erneuten Anmeldung -- einfacher und vorhersehbarer als ein sich selbst erneuerndes
Vertrauen."""

import base64
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import hash_password, verify_password
from .models import AppUser, TrustedDevice

TRUST_COOKIE_NAME = "dk_erp_trust"
TRUST_DAYS = 30
TRUST_MAX_AGE = 60 * 60 * 24 * TRUST_DAYS


def create_trust(db: Session, user: AppUser) -> str:
    """Legt ein neues vertrautes Gerät für user an und liefert den fertigen Cookie-Wert (Zeilen-ID
    + rohes Geheimnis, base64url-kodiert) -- das Geheimnis selbst wird NIE gespeichert, nur sein
    Hash."""
    raw_secret = secrets.token_urlsafe(32)
    row = TrustedDevice(
        user_id=user.id,
        token_hash=hash_password(raw_secret),
        expires_at=datetime.utcnow() + timedelta(days=TRUST_DAYS),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    payload = f"{row.id}:{raw_secret}"
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _parse_cookie(value: str) -> tuple[int, str] | None:
    try:
        raw = base64.urlsafe_b64decode(value.encode()).decode()
        id_s, raw_secret = raw.split(":", 1)
        return int(id_s), raw_secret
    except Exception:
        return None


def check_trust(db: Session, user: AppUser, cookie_value: str | None) -> bool:
    """Prüft, ob cookie_value ein gültiges, nicht abgelaufenes vertrautes Gerät GENAU für user
    belegt -- der user_id-Abgleich ist die Absicherung gegen ein Cookie, das (echt oder
    manipuliert) auf ein fremdes Konto zeigt: es reicht nicht, dass die Zeile existiert und ihr
    Geheimnis passt, sie muss zusätzlich exakt diesem Benutzer gehören."""
    if not cookie_value:
        return False
    parsed = _parse_cookie(cookie_value)
    if parsed is None:
        return False
    device_id, raw_secret = parsed
    row = db.get(TrustedDevice, device_id)
    if row is None or row.user_id != user.id:
        return False
    if row.expires_at < datetime.utcnow():
        return False
    return verify_password(raw_secret, row.token_hash)


def revoke_all(db: Session, user: AppUser) -> None:
    """Löscht ALLE vertrauten Geräte von user -- aufgerufen bei jeder Änderung, die ein zuvor
    vertrautes Gerät entwerten muss (2FA-Reset, Passwortänderung, expliziter Widerruf), siehe
    CLAUDE.md und den Klassendocstring von TrustedDevice."""
    for row in db.scalars(select(TrustedDevice).where(TrustedDevice.user_id == user.id)).all():
        db.delete(row)
    db.commit()
