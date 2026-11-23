"""Einstellungen des Portal-Dienstes (seit 1.11.2, Stufe P1b) -- nur aus der Umgebung, streng geprüft, ohne stillen Rückfall (Vorfall 1).

Auf dem Server aus /etc/dk-portal/portal.env (640 root:dkportal; Muster ohne Werte: scripts/server/portal.env.beispiel):

    DATABASE_URL              Pflicht, PostgreSQL mit der Rolle des Portals (postgresql+psycopg://dkportal:…@127.0.0.1:5432/dachkonzepte)
    PORTAL_HERKUNFT           Pflicht, z. B. https://kunde.dachkonzepte.gmbh -- daraus der einzige erlaubte Host und die Herkunft schreibender Anfragen
    PORTAL_BREMSE_SCHLUESSEL  Pflicht, mindestens 32 Byte als Hexadezimalzahl (openssl rand -hex 32) -- nur für den Prüfwert des Anschlusses (F14)
    ERP_ENV                   production (Vorgabe, auch wenn sie fehlt), development oder test -- nur development/test erlauben http://localhost

Ein Wert, der nicht passt, bricht den Start ab (EinstellungFalsch) -- mit einem Satz, der nie einen Wert nennt.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

LOKAL = ("localhost", "127.0.0.1")
_HEX = re.compile(r"^[0-9a-fA-F]+$")


class EinstellungFalsch(Exception):
    """Eine Einstellung fehlt oder passt nicht -- der Dienst startet nicht."""


@dataclass(frozen=True)
class Einstellungen:
    datenbank_url: str
    herkunft: str
    bremse_schluessel: bytes
    umgebung: str = "production"

    @property
    def host(self) -> str:
        """Der einzige erlaubte Host (mit Port, wenn die Herkunft einen nennt)."""
        return urlsplit(self.herkunft).netloc.lower()

    @property
    def nur_https(self) -> bool:
        """HSTS und HTTPS-Pflicht -- außer lokal (development) und in Tests."""
        return self.umgebung not in ("development", "test")


def pruefen(e: Einstellungen) -> Einstellungen:
    """Prüft eine Einstellung wie aus der Umgebung; gibt sie unverändert zurück oder wirft EinstellungFalsch."""
    if e.umgebung not in ("production", "development", "test"):
        raise EinstellungFalsch("ERP_ENV ist weder production noch development noch test.")
    if not e.datenbank_url.startswith("postgresql"):
        raise EinstellungFalsch("DATABASE_URL fehlt oder ist nicht PostgreSQL -- das Portal läuft nur gegen PostgreSQL.")
    teile = urlsplit(e.herkunft)
    if teile.username or teile.password or teile.path not in ("", "/") or teile.query or teile.fragment or not teile.hostname:
        raise EinstellungFalsch("PORTAL_HERKUNFT ist keine reine Herkunft (Schema und Host, ohne Pfad).")
    if teile.scheme != "https" and not (teile.scheme == "http" and teile.hostname in LOKAL and not e.nur_https):
        raise EinstellungFalsch("PORTAL_HERKUNFT muss mit https:// beginnen (http nur lokal mit ERP_ENV development oder test).")
    if len(e.bremse_schluessel) < 32:
        raise EinstellungFalsch("PORTAL_BREMSE_SCHLUESSEL fehlt oder ist kürzer als 32 Byte (64 Hexadezimalzeichen).")
    return e


def aus_umgebung(umgebung: dict | None = None) -> Einstellungen:
    env = os.environ if umgebung is None else umgebung
    schluessel = (env.get("PORTAL_BREMSE_SCHLUESSEL") or "").strip()
    if not _HEX.match(schluessel) or len(schluessel) % 2:
        raise EinstellungFalsch("PORTAL_BREMSE_SCHLUESSEL fehlt oder ist keine Hexadezimalzahl (openssl rand -hex 32).")
    return pruefen(Einstellungen(
        datenbank_url=(env.get("DATABASE_URL") or "").strip(),
        herkunft=(env.get("PORTAL_HERKUNFT") or "").strip().rstrip("/"),
        bremse_schluessel=bytes.fromhex(schluessel),
        umgebung=(env.get("ERP_ENV") or "production").strip(),
    ))
