"""Was jede Seite für Akzentfarbe, Seitenleiste und Kopfzeile aus der Datenbank braucht (seit 1.8.114, Vorgabe vom 16.10.2026, Punkt 1c).

Bis 1.8.113 öffnete jeder der fünf datenbankgestützten Jinja-Globals (get_theme, is_module_enabled, sidebar_logo_url,
sidebar_logo_height_px, account_display -- app/routers/pages.py) bei jedem Aufruf eine eigene Sitzung: eine Seite mit Seitenleiste und
Kopfzeile holte so 37 Verbindungen nacheinander aus dem Pool (/tasks 41, /mobil 17; gemessen mit tests/test_v419_verbindungen.py), und
eine Seitenroute mit eigener Sitzung (/users) hielt dabei schon eine -- bei leerem Pool wartete sie auf sich selbst.

Jetzt lädt die Anmeldeschranke diese Daten für eine Seitenanfrage in ihrer einen Sitzung mit (laden(), app/anmeldeschranke.py) und legt
sie an request.state ab; die Globals lesen nur noch dort (fuer_anfrage()). Ohne Schranke (Tests mit router_test_client) lädt der erste
Global einer Anfrage einmal mit eigener Sitzung und legt das Ergebnis ebenso ab -- auch dann eine Verbindung je Seite.

Jeder Teil fällt bei einem Fehler einzeln auf seinen Rückfallwert zurück (Vorfall 2, CLAUDE.md "Produktivbetrieb"): eine Seite -- auch
die Anmeldeseite -- darf nie an einem Datenbankzustand scheitern. Nach einem Fehler setzt rollback() die Sitzung zurück, sonst lehnte
PostgreSQL jede weitere Abfrage derselben Transaktion ab."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .auth import resolve_account_display
from .company_logo import DEFAULT_SIDEBAR_LOGO_HEIGHT_PX, sidebar_logo_filename, sidebar_logo_height_px
from .database import SessionLocal
from .modules import module_enabled_in, stored_module_states
from .settings import get_accent_color

logger = logging.getLogger(__name__)

STANDARD_AKZENT = "#0d9488"
ZUSTAND = "dk_seitendaten"  # Name an request.state

# Beide Logos liegen in getrennten Ordnern hinter getrennten Endpunkten (seit 1.3.43, app/company_logo.py::sidebar_logo_filename()).
LOGO_ENDPUNKTE = {
    "sidebar": "/api/settings/general/sidebar-logo",
    "company": "/api/settings/general/logo",
}


@dataclass(frozen=True)
class Seitendaten:
    akzentfarbe: str = STANDARD_AKZENT
    module: dict[str, bool] = field(default_factory=dict)  # gespeicherte Zustände; ein fehlender Schlüssel gilt als aktiv
    logo_url: str | None = None
    logo_hoehe: int = DEFAULT_SIDEBAR_LOGO_HEIGHT_PX
    konto: dict | None = None  # Name und Initialen für den Kontoknopf
    konto_von: int | None = None  # ID des Benutzers, für den konto gilt

    def modul_aktiv(self, module_key: str) -> bool:
        return module_enabled_in(self.module, module_key)


def konto_rueckfall(user) -> dict:
    """Name und Initialen ohne Datenbank: der Benutzername."""
    if user is None:
        return {"full_name": "", "initials": ""}
    username = getattr(user, "username", "") or ""
    return {"full_name": username, "initials": (username[:2].upper() if username else "?")}


def _logo_url(db) -> str | None:
    """Die URL des Logos der Leiste oder None (dann der Schriftzug). ?v=<gespeicherter Name> bricht den Bild-Cache des Browsers auf,
    sobald ein Logo ersetzt wird -- jeder Upload bekommt einen neuen, zufälligen Namen."""
    ref = sidebar_logo_filename(db)
    if ref is None:
        return None
    return f"{LOGO_ENDPUNKTE[ref.source]}?v={ref.stored_filename}"


def _teil(db, name: str, lesen, rueckfall):
    try:
        return lesen()
    except Exception:
        logger.exception("Seitendaten: %s nicht lesbar, Rückfallwert", name)
        try:
            db.rollback()
        except Exception:
            logger.exception("Seitendaten: Zurücksetzen der Sitzung gescheitert")
        return rueckfall


def laden(db, user) -> Seitendaten:
    """Alle Teile in der Sitzung db; user: der angemeldete Benutzer oder None."""
    return Seitendaten(
        akzentfarbe=_teil(db, "Akzentfarbe", lambda: get_accent_color(db), STANDARD_AKZENT),
        module=_teil(db, "Module", lambda: stored_module_states(db), {}),
        logo_url=_teil(db, "Logo der Leiste", lambda: _logo_url(db), None),
        logo_hoehe=_teil(db, "Höhe des Logos", lambda: sidebar_logo_height_px(db), DEFAULT_SIDEBAR_LOGO_HEIGHT_PX),
        konto=None if user is None else _teil(db, "Konto", lambda: resolve_account_display(db, user), konto_rueckfall(user)),
        konto_von=getattr(user, "id", None),
    )


def laden_mit_eigener_sitzung(user) -> Seitendaten:
    """laden() mit einer eigenen, kurzen Sitzung (eine Verbindung) -- für eine Anfrage ohne Daten der Schranke."""
    try:
        with SessionLocal() as db:
            return laden(db, user)
    except Exception:
        logger.exception("Seitendaten: keine Sitzung, alle Rückfallwerte")
        return Seitendaten(konto=None if user is None else konto_rueckfall(user), konto_von=getattr(user, "id", None))


def fuer_anfrage(request) -> Seitendaten:
    """Die Seitendaten der Anfrage: von der Schranke geladen, sonst einmal je Anfrage nachgeladen (request None: jedes Mal)."""
    state = getattr(request, "state", None)
    daten = getattr(state, ZUSTAND, None) if state is not None else None
    if daten is None:
        daten = laden_mit_eigener_sitzung(getattr(state, "erp_user", None) if state is not None else None)
        if state is not None:
            setattr(state, ZUSTAND, daten)
    return daten
