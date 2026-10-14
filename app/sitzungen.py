"""Anmeldesitzungen auf dem Server (seit 1.8.98, app/models.py::UserSession).

Das Cookie dk_erp_auth trägt einen Zufallswert; gespeichert ist nur sein SHA-256. Eine Sitzung gilt, solange ihre Zeile besteht, sie
nicht abgelaufen ist (fest 12 h ab der Anmeldung) und der Benutzer aktiv ist. Beendet wird sie
- beim Abmelden (beenden(), nur diese),
- bei einer Passwortänderung (eigene und durch einen Administrator), einer Änderung am zweiten Faktor (Ersteinrichtung, Zurücksetzen
  durch einen Administrator oder das Notfallskript) und beim Deaktivieren eines Benutzers (alle_beenden(), alle seine),
- seit 1.8.103 (Korrekturen 98-11/98-12): "Alle vertrauten Geräte abmelden" beendet alle anderen Sitzungen des Kontos
  (andere_beenden()), ein Administrator beendet alle Sitzungen eines Benutzers (alle_beenden()), und der Feierabend in /mobil beendet
  die Sitzung wie das Abmelden (beenden()).
Wer selbst ändert (eigenes Passwort, Ersteinrichtung des zweiten Faktors), bleibt auf diesem Gerät angemeldet -- mit einer neuen
Sitzung, die alte endet wie alle anderen.

Der zweite Faktor gilt je Sitzung (second_factor_at); bestätigt ihn eine Sitzung, bekommt sie einen neuen Wert (erneuern()), damit ein
vorher bekannter Wert nach der Bestätigung nichts mehr nützt.

Ein Lesepfad schreibt nie (Regel 23): Ablauf ohne gleitende Verlängerung, Aufräumen abgelaufener Zeilen nur bei der Anmeldung."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .auth import COOKIE_MAX_AGE, COOKIE_NAME, COOKIE_SECURE
from .models import AppUser, UserSession

DAUER = timedelta(seconds=COOKIE_MAX_AGE)
# Ein echter Wert ist 43 Zeichen lang (token_urlsafe(32)); alles deutlich Längere wird gar nicht erst gehasht.
_MAX_COOKIE_LAENGE = 200


def _hash(wert: str) -> str:
    return hashlib.sha256(wert.encode("utf-8")).hexdigest()


def _jetzt() -> datetime:
    return datetime.utcnow()


def neue_sitzung(db: Session, user: AppUser, *, zweiter_faktor: bool = False) -> str:
    """Legt eine Sitzung für user an (flush, kein Commit) und gibt den Cookie-Wert zurück -- er steht nur hier, gespeichert ist der
    Hash."""
    wert = secrets.token_urlsafe(32)
    jetzt = _jetzt()
    db.add(UserSession(user_id=user.id, token_hash=_hash(wert), created_at=jetzt, expires_at=jetzt + DAUER,
                       second_factor_at=jetzt if zweiter_faktor else None))
    db.flush()
    return wert


def sitzung_zum_wert(db: Session, wert: str | None) -> UserSession | None:
    """Die gültige (nicht abgelaufene) Sitzung zu einem Cookie-Wert, sonst None."""
    if not wert or len(wert) > _MAX_COOKIE_LAENGE:
        return None
    sitzung = db.scalar(select(UserSession).where(UserSession.token_hash == _hash(wert)))
    if sitzung is None or sitzung.expires_at <= _jetzt():
        return None
    return sitzung


def anmeldung(db: Session, request) -> tuple[AppUser | None, UserSession | None]:
    """Benutzer und Sitzung der Anfrage (Cookie dk_erp_auth) -- (None, None) ohne gültige Sitzung oder bei inaktivem Benutzer."""
    sitzung = sitzung_zum_wert(db, request.cookies.get(COOKIE_NAME))
    if sitzung is None:
        return None, None
    user = db.get(AppUser, sitzung.user_id)
    if user is None or not user.active:
        return None, None
    return user, sitzung


def benutzer_aus_anfrage(db: Session, request) -> AppUser | None:
    return anmeldung(db, request)[0]


def beenden(db: Session, wert: str | None) -> None:
    """Beendet die Sitzung zu diesem Cookie-Wert (kein Commit). Unbekannt oder abgelaufen: nichts zu tun."""
    if wert and len(wert) <= _MAX_COOKIE_LAENGE:
        db.execute(delete(UserSession).where(UserSession.token_hash == _hash(wert)))


def alle_beenden(db: Session, user: AppUser, *, request=None, response=None, zweiter_faktor: bool | None = None) -> None:
    """Beendet alle Sitzungen von user (kein Commit). Gehört die Sitzung der Anfrage (request) zu user, bekommt dieses Gerät eine neue
    -- Cookie in response, zweiter Faktor wie bisher oder wie zweiter_faktor angibt. Ohne request (Notfallskript, ein anderes Konto)
    endet jede Sitzung."""
    # Ohne response (Notfallskript, Direktaufruf) gibt es kein neues Cookie -- dann endet auch die Sitzung der Anfrage.
    aktuelle = sitzung_zum_wert(db, request.cookies.get(COOKIE_NAME)) if request is not None and response is not None else None
    weiter = aktuelle is not None and aktuelle.user_id == user.id
    mit_faktor = (aktuelle.second_factor_at is not None if zweiter_faktor is None else zweiter_faktor) if weiter else False
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    if weiter:
        cookie_setzen(response, neue_sitzung(db, user, zweiter_faktor=mit_faktor))


def andere_beenden(db: Session, user: AppUser, request) -> int:
    """Beendet alle Sitzungen von user außer der der Anfrage (kein Commit) -- "Alle vertrauten Geräte abmelden" (seit 1.8.103). Gibt
    zurück, wie viele endeten."""
    aktuelle = sitzung_zum_wert(db, request.cookies.get(COOKIE_NAME)) if request is not None else None
    bedingung = UserSession.user_id == user.id
    if aktuelle is not None and aktuelle.user_id == user.id:
        bedingung = bedingung & (UserSession.id != aktuelle.id)
    return db.execute(delete(UserSession).where(bedingung)).rowcount or 0


def anzahl(db: Session, user: AppUser) -> int:
    """Wie viele Sitzungen von user gelten (nicht abgelaufen) -- nur lesen."""
    from sqlalchemy import func
    return db.scalar(select(func.count(UserSession.id)).where(UserSession.user_id == user.id,
                                                              UserSession.expires_at > _jetzt())) or 0


def erneuern(db: Session, request, response, user: AppUser, *, zweiter_faktor: bool) -> None:
    """Ersetzt die Sitzung der Anfrage durch eine neue (neuer Wert, Cookie in response), z. B. nach der Bestätigung des zweiten
    Faktors. Die übrigen Sitzungen von user bleiben."""
    beenden(db, request.cookies.get(COOKIE_NAME))
    cookie_setzen(response, neue_sitzung(db, user, zweiter_faktor=zweiter_faktor))


def abgelaufene_entfernen(db: Session) -> None:
    """Löscht abgelaufene Sitzungen aller Benutzer (kein Commit) -- nur aus einem Schreibweg (Anmeldung), nie beim Lesen."""
    db.execute(delete(UserSession).where(UserSession.expires_at <= _jetzt()))


def cookie_setzen(response, wert: str) -> None:
    response.set_cookie(COOKIE_NAME, wert, max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax", secure=COOKIE_SECURE)
