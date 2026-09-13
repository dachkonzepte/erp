"""Persistente Anmeldesperre gegen Brute-Force (seit 1.3.34, ersetzt den früheren
In-Memory-Zähler in app/auth.py).

Zwei unabhängige Sperren gemeinsam, nicht nur eine:
- Je BENUTZERNAME (verhindert, gegen ein bekanntes Konto viele Passwörter durchzuprobieren).
- Je IP-ADRESSE (verhindert, viele verschiedene -- auch erratene -- Benutzernamen von einer
  Adresse durchzuprobieren; eine reine Benutzernamen-Sperre ließe sich sonst durch rotierende
  Benutzernamen umgehen).

Ist EINE der beiden Sperren aktiv, wird die Anmeldung abgelehnt. Die IP-Sperre hat eine höhere
Schwelle als die Benutzernamen-Sperre, damit ein Büro mit mehreren Mitarbeitern hinter derselben
Adresse sich nicht bereits durch normale Tippfehler gegenseitig aussperrt.

Bewusst NICHT in dieser Version: Auswertung von X-Forwarded-For hinter einem Reverse-Proxy --
`request.client.host` ist der unmittelbare TCP-Peer. Läuft der Server später hinter einem
Reverse-Proxy, sehen alle Anfragen dieselbe (Proxy-)Adresse, die IP-Sperre würde dann faktisch
alle Nutzer gemeinsam treffen. Das ist ein bekannter, bewusst offener Punkt für den Moment, in
dem ein Reverse-Proxy tatsächlich eingerichtet wird (siehe CLAUDE.md)."""

from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import FailedLoginAttempt

MAX_ATTEMPTS_PER_USER = 5
LOCKOUT_SECONDS_PER_USER = 15 * 60

MAX_ATTEMPTS_PER_IP = 20
LOCKOUT_SECONDS_PER_IP = 15 * 60

MAX_ATTEMPTS_PER_TWO_FACTOR_USER = 5
LOCKOUT_SECONDS_PER_TWO_FACTOR_USER = 15 * 60

# Für die automatische Aufräumung: keine Zeile ist über das größte hier verwendete Zeitfenster
# hinaus für irgendeine Sperre noch relevant.
_RETENTION_SECONDS = max(
    LOCKOUT_SECONDS_PER_USER, LOCKOUT_SECONDS_PER_IP, LOCKOUT_SECONDS_PER_TWO_FACTOR_USER,
)


def _normalize(value: str) -> str:
    return value.strip().lower()


def user_bucket(username: str) -> str:
    return f"login_user:{_normalize(username)}"


def ip_bucket(client_ip: str) -> str:
    return f"login_ip:{_normalize(client_ip)}"


def two_factor_user_bucket(username: str) -> str:
    return f"twofa_user:{_normalize(username)}"


def register_failed_attempt(db: Session, bucket: str) -> None:
    """Trägt einen Fehlversuch ein und räumt bei dieser Gelegenheit gleich alte, für keine
    Sperre mehr relevante Zeilen auf -- kein separater Aufräumjob nötig (siehe
    FailedLoginAttempt-Docstring in app/models.py)."""
    db.add(FailedLoginAttempt(bucket=bucket))
    cutoff = datetime.utcnow() - timedelta(seconds=_RETENTION_SECONDS)
    db.execute(delete(FailedLoginAttempt).where(FailedLoginAttempt.occurred_at < cutoff))
    db.commit()


def clear_failed_attempts(db: Session, bucket: str) -> None:
    db.execute(delete(FailedLoginAttempt).where(FailedLoginAttempt.bucket == bucket))
    db.commit()


def seconds_until_unlocked(db: Session, bucket: str, max_attempts: int, window_seconds: int) -> int | None:
    """None, wenn nicht gesperrt -- sonst verbleibende Sperrsekunden (>= 1). Gleitendes
    Zeitfenster wie zuvor beim In-Memory-Zähler: erst wenn der ÄLTESTE Versuch innerhalb des
    Fensters aus dem Fenster herausfällt, sinkt die Zählung wieder unter die Schwelle."""
    cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
    count = db.scalar(
        select(func.count(FailedLoginAttempt.id)).where(
            FailedLoginAttempt.bucket == bucket, FailedLoginAttempt.occurred_at > cutoff,
        )
    )
    if count is None or count < max_attempts:
        return None
    oldest = db.scalar(
        select(func.min(FailedLoginAttempt.occurred_at)).where(
            FailedLoginAttempt.bucket == bucket, FailedLoginAttempt.occurred_at > cutoff,
        )
    )
    remaining = (oldest + timedelta(seconds=window_seconds) - datetime.utcnow()).total_seconds()
    return max(int(remaining), 1)


def login_lockout_seconds(db: Session, username: str, client_ip: str | None) -> int | None:
    """Prüft BEIDE Sperren (Benutzername und, falls bekannt, IP) und liefert die größere
    verbleibende Sperrzeit, falls eine der beiden aktiv ist."""
    remaining = seconds_until_unlocked(db, user_bucket(username), MAX_ATTEMPTS_PER_USER, LOCKOUT_SECONDS_PER_USER)
    if client_ip:
        ip_remaining = seconds_until_unlocked(db, ip_bucket(client_ip), MAX_ATTEMPTS_PER_IP, LOCKOUT_SECONDS_PER_IP)
        if ip_remaining is not None and (remaining is None or ip_remaining > remaining):
            remaining = ip_remaining
    return remaining


def register_failed_login(db: Session, username: str, client_ip: str | None) -> None:
    register_failed_attempt(db, user_bucket(username))
    if client_ip:
        register_failed_attempt(db, ip_bucket(client_ip))


def clear_failed_login(db: Session, username: str) -> None:
    """Nur die Benutzernamen-Sperre wird bei Erfolg zurückgesetzt -- bewusst NICHT die
    IP-Sperre: gelingt zufällig EIN Login von einer Adresse, mit der zuvor viele andere
    Benutzernamen durchprobiert wurden, soll das die IP-Sperre nicht aufheben."""
    clear_failed_attempts(db, user_bucket(username))


def two_factor_lockout_seconds(db: Session, username: str) -> int | None:
    return seconds_until_unlocked(
        db, two_factor_user_bucket(username), MAX_ATTEMPTS_PER_TWO_FACTOR_USER, LOCKOUT_SECONDS_PER_TWO_FACTOR_USER,
    )


def register_failed_two_factor_attempt(db: Session, username: str) -> None:
    register_failed_attempt(db, two_factor_user_bucket(username))


def clear_failed_two_factor_attempts(db: Session, username: str) -> None:
    clear_failed_attempts(db, two_factor_user_bucket(username))
