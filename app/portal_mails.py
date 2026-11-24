"""Mails des Kundenportals (seit 1.11.5, Stufe P1c; Bauplan P1, Abschnitt 4) -- der Link zum Portal und der Anmeldecode.

- Feste Texte im Code (P1-7), gesiezt (Kundentexte, tests/test_v440_runde_du.py) -- mit einer Vorlage in den Einstellungen ließe sich der
  Sicherheitshinweis entfernen oder der Link in den Betreff setzen; Änderungen deshalb nur über eine Version.
- Der Betreff ist fest und enthält weder Link noch Code: das Versandprotokoll speichert Empfänger und Betreff, nie den Text (Regel 18).
- Gesendet wird nur über Microsoft 365 und ohne Kopie in „Gesendete Elemente“ (P1-3) -- Link und Code lägen sonst im Postfach des Betriebs.
  dispatch_email(gesendete_elemente=False) lehnt den Versand über SMTP ab, bevor etwas geschrieben wird.
- senden() ist der einzige Weg für Mails des Portals: tests/test_v804_portal_mails.py prüft per AST, dass keine andere Stelle eine Versandart des Portals
  oder den Schalter gesendete_elemente nimmt.

Link (ab P1d) und Code (Postbote, ab 1.11.6) stehen nur im Text der Mail und kurz im Speicher -- nie in einer Tabelle, einem Protokoll, einer Antwort oder
einer Ausnahme.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from .berlin_time import to_berlin
from .email_dispatch import PORTAL_TYPES, DispatchResult, dispatch_email
from .models import Customer
from .portal.begruessung import begruessung
from .settings import load_general_settings

# Versandart -> Betreff (fest, ohne Link und Code)
BETREFF = {"portal_link": "Ihr Zugang zum Kundenportal", "portal_code": "Ihr Anmeldecode für das Kundenportal"}
assert set(BETREFF) == set(PORTAL_TYPES), "jede Versandart des Portals braucht ihren festen Betreff"
CODE_MINUTEN = 10  # wie portal_code_pruefen() und der Postbote (gültig bis)


def anrede(kunde: Customer) -> str:
    """Erste Zeile der Mail, wie die Begrüßung im Portal (app/portal/begruessung.py)."""
    return begruessung(kunde.salutation, kunde.title, kunde.first_name, kunde.last_name, kunde.name) + ","


def schluss(db: Session) -> str:
    """Gruß und Absender aus den Firmendaten der Einstellungen (P1-14) -- dieselben Angaben, die das Portal als Kontakt zeigt."""
    s = load_general_settings(db)
    zeilen = [s.company_name, s.street, " ".join(t for t in (s.postal_code, s.city) if t)]
    zeilen.append(" · ".join(t for t in (f"Telefon {s.phone}" if s.phone else None, s.email, s.website) if t))
    return "Mit freundlichen Grüßen\n\n" + "\n".join(z.strip() for z in zeilen if z and z.strip())


def link_text(db: Session, kunde: Customer, adresse: str, gueltig_bis: datetime) -> str:
    """Text der Mail mit dem Link (Versandart portal_link, ab P1d). adresse = https://kunde…/#z=<Wert>; gueltig_bis in naivem UTC."""
    bis = to_berlin(gueltig_bis).strftime("%d.%m.%Y")
    return (
        f"{anrede(kunde)}\n\n"
        "über unser Kundenportal erreichen Sie Ihre Unterlagen bei uns. Ihr persönlicher Zugang:\n\n"
        f"{adresse}\n\n"
        f"Der Link gilt bis {bis}. Beim ersten Öffnen auf einem Gerät schicken wir Ihnen einen Anmeldecode an diese E-Mail-Adresse.\n\n"
        "Bitte geben Sie den Link nicht weiter – er öffnet Ihr Kundenportal. Wir fragen Sie nie nach einem Passwort. Haben Sie diese E-Mail nicht "
        "erwartet, rufen Sie uns bitte an.\n\n"
        f"{schluss(db)}\n"
    )


def code_text(db: Session, kunde: Customer, code: str) -> str:
    """Text der Mail mit dem Anmeldecode (Versandart portal_code, Postbote)."""
    return (
        f"{anrede(kunde)}\n\n"
        "Ihr Anmeldecode für das Kundenportal:\n\n"
        f"{code}\n\n"
        f"Der Code gilt {CODE_MINUTEN} Minuten und nur in dem Browser, in dem Sie ihn angefordert haben.\n\n"
        "Haben Sie keinen Code angefordert? Dann hat jemand Ihren Link zum Kundenportal geöffnet. Bitte rufen Sie uns an – wir sperren den Link und "
        "schicken Ihnen einen neuen. Wir fragen Sie nie nach diesem Code oder einem Passwort.\n\n"
        f"{schluss(db)}\n"
    )


def senden(db: Session, *, art: str, dokument_id: int, an: str, text: str, dispatch_key: str,
           user_id: int | None = None, user_name: str | None = None) -> DispatchResult:
    """Die eine Stelle, an der eine Mail des Portals hinausgeht: dispatch_email() mit dem festen Betreff der Art und ohne „Gesendete Elemente“.
    dokument_id: der Zugang (portal_link) bzw. der Auftrag an den Postboten (portal_code). Wirft wie dispatch_email() ValueError und DispatchConflict --
    deren Text nennt nie den Text der Mail."""
    # je Art ein Aufruf mit fester Versandart (die Wächter test_v355 und test_v371 verlangen eine Konstante)
    if art == "portal_link":
        return dispatch_email(
            db, dispatch_key=dispatch_key, document_type="portal_link", document_id=dokument_id, document_number=None, to=an, cc=None,
            subject=BETREFF["portal_link"], body_text=text, user_id=user_id, user_name=user_name, gesendete_elemente=False,
        )
    if art == "portal_code":
        return dispatch_email(
            db, dispatch_key=dispatch_key, document_type="portal_code", document_id=dokument_id, document_number=None, to=an, cc=None,
            subject=BETREFF["portal_code"], body_text=text, user_id=user_id, user_name=user_name, gesendete_elemente=False,
        )
    raise ValueError(f"Unbekannte Versandart des Portals: {art}")
