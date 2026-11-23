"""Prüfwerte des Kundenportals (seit 1.11.1, Nachtrag N1 zum Bauplan P1).

Link, Cookie und Code verlassen Python nie als Klartext in Richtung Datenbank: dorthin gehen nur diese Prüfwerte (SHA-256 mit Zweck, 64 Zeichen
hexadezimal). So steht keiner der Werte in einer Tabelle, in einem Parameter im Log von PostgreSQL oder in einer Antwort. Der Prüfwert des Codes hängt an
der Sitzung, die ihn anforderte: derselbe Code passt zu keiner anderen Sitzung. Der Anschluss (IP-Adresse) geht nur als HMAC mit einem Schlüssel des
Portals in die Bremsen (F14) -- ohne den Schlüssel lässt sich die Adresse nicht zurückrechnen, auch nicht durch Probieren aller Adressen.

Benutzt vom Dienst des Portals (ab P1b), vom ERP (Link erzeugen, ab P1d) und vom Postboten (Code anlegen, ab P1c).
"""

import hashlib
import hmac
import secrets

from .werte import ZWECK_CODE, ZWECK_LINK, ZWECK_SITZUNG

ZWECK_ANSCHLUSS = "dk-portal-anschluss:"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def neuer_wert() -> str:
    """Ein neuer Wert für Link oder Cookie: 32 Byte Zufall, URL-sicher (43 Zeichen)."""
    return secrets.token_urlsafe(32)


def neuer_code() -> str:
    """Ein neuer Anmeldecode: 6 Ziffern, gleich verteilt."""
    return f"{secrets.randbelow(1_000_000):06d}"


def link(wert: str) -> str:
    """Prüfwert des Links (portal_zugaenge.link_sha256)."""
    return _sha256(ZWECK_LINK + wert)


def sitzung(wert: str) -> str:
    """Prüfwert des Cookies (portal_sitzungen.wert_sha256)."""
    return _sha256(ZWECK_SITZUNG + wert)


def code(sitzung_pruefwert: str, code_: str) -> str:
    """Prüfwert des Codes für genau diese (unbestätigte) Sitzung (portal_codes.pruefwert)."""
    return _sha256(ZWECK_CODE + sitzung_pruefwert + ":" + code_)


def anschluss(adresse: str, schluessel: bytes) -> str:
    """Prüfwert des Anschlusses für die Bremsen: HMAC-SHA-256 mit dem Schlüssel des Portals (PORTAL_BREMSE_SCHLUESSEL)."""
    if len(schluessel) < 32:
        raise ValueError("Der Schlüssel der Bremsen ist zu kurz (mindestens 32 Byte).")
    return hmac.new(schluessel, (ZWECK_ANSCHLUSS + adresse).encode("utf-8"), hashlib.sha256).hexdigest()
