"""Das Kundenportal am Kunden (seit 1.11.10, Stufe P1d; Bauplan P1, Abschnitt 4; docs/archiv/webseite-und-kundenportal.md) -- Schalter, Zugang, Link
senden, sperren, entsperren, verlängern, Protokoll. Die Karte „Kundenportal“ der Kundenakte liest und schreibt nur hierüber (app/routers/kundenportal.py).

- Ein Zugang je Kunde (F10, bis P5) mit eigener E-Mail, vorbelegt mit der des Kunden (F4, P1-15). Ohne E-Mail am Kunden kein Zugang.
- „Link senden“ erzeugt den Link: der Wert existiert nur in dieser Anfrage (in der Mail), gespeichert wird nur sein Prüfwert; gültig 12 Monate (F3).
  Ein zweites „Link senden“ ist „neu erzeugen“: der alte gilt nicht mehr, alle Geräte sind abgemeldet (P1-5). Eine geänderte E-Mail wirkt erst mit diesem
  neuen Link (P1-15) -- geändert wird sie nur beim Senden.
- Sperren (mit Grund) beendet alle Sitzungen; Portal aus beendet sie ebenso. Die Funktionen der Datenbank prüfen beides ohnehin bei jeder Anfrage
  (portal_zugang_grund()) -- das Beenden hält fest, warum eine Sitzung endete, und lässt sie nach einem Entsperren nicht wieder aufleben.
- Jede Änderung steht in der Änderungshistorie (PortalZugang in app/audit.py::AUDITED_TYPES, ohne den Prüfwert des Links); das Protokoll der Karte zeigt
  sie zusammen mit dem Zugriffsprotokoll des Portals (portal_zugriffe), ohne Adressen (es gibt keine).

Sperren in fester Reihenfolge wie der Postbote: Zeile des Zugangs, dann seine Sitzungen.

Seit 1.11.13 (Antworten des Betriebs zu 1.11.10/1.11.11): „Versand gescheitert“ ist ein eigener Zustand (der letzte Link ging nicht hinaus); Verlängern nur,
solange der Link gilt (aktiv, läuft bald ab) -- ein abgelaufener lebt nicht wieder auf; Sperren geht auch im Archiv (Festlegung 1.11.0: es nimmt nur Zugang
weg); das Protokoll zeigt eine Zeile je Aktion statt je Feld.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from . import portal_mails
from .date_utils import add_months
from .email_dispatch import DispatchResult, parse_recipients
from .models import AuditLog, Customer, EmailDispatch, PortalSitzung, PortalZugang, PortalZugriff
from .portal import pruefwerte

GUELTIG_MONATE = 12          # F3
HINWEIS_TAGE = 30            # „läuft in 30 Tagen ab“
SEITE = 50                   # Einträge des Protokolls je Seite
ZUGANG_ART = "Zugang zum Kundenportal"  # Art in der Änderungshistorie (app/audit.py)

ZUSTAENDE = {
    "archiv": "Der Kunde ist im Archiv – sein Zugang wirkt nicht.",  # seit 1.11.13 ohne „nur lesbar“: Sperren geht auch hier
    "aus": "Das Kundenportal ist für diesen Kunden aus.",
    "ohne_email": "Erst eine E-Mail-Adresse beim Kunden eintragen.",
    "kein_zugang": "Noch kein Zugang.",
    "ohne_link": "Zugang angelegt, noch kein Link versendet.",
    "aktiv": "Link versendet.",
    "laeuft_ab": "Der Link läuft bald ab.",
    "abgelaufen": "Der Link ist abgelaufen.",
    "gescheitert": "Der Link ging nicht hinaus.",  # seit 1.11.13 ein eigener Zustand
    "gesperrt": "Der Zugang ist gesperrt.",
}
LINK_GILT = ("aktiv", "laeuft_ab")  # seit 1.11.13: nur dann gibt es „Verlängern“

# Zugriffsprotokoll des Portals in Worten (app/portal/werte.py::AKTIONEN, ERGEBNISSE)
AKTION_TEXT = {
    "link_geoeffnet": "Link geöffnet", "code_angefordert": "Code angefordert", "code_gesendet": "Code gesendet",
    "code_fehler": "Code nicht gesendet", "code_falsch": "Code falsch eingegeben", "code_abgelaufen": "Code abgelaufen",
    "angemeldet": "Angemeldet", "verlaengert": "Anmeldung verlängert", "abgemeldet": "Abgemeldet",
    "ueberall_abgemeldet": "Auf allen Geräten abgemeldet",
    "unterlagen": "Unterlagen geöffnet", "datei_angefordert": "Unterlage angefordert",  # seit 1.11.31 (P2a)
    "rechnungen": "Rechnungen geöffnet", "termine": "Termine geöffnet", "uebersicht": "Übersicht geöffnet",  # seit 1.11.42 (P2d)
}
ERGEBNIS_TEXT = {
    "ok": "", "unbekannt": "unbekannter Link", "gesperrt": "Zugang gesperrt", "abgelaufen": "Link abgelaufen", "portal_aus": "Portal aus",
    "archiv": "Kunde im Archiv", "modul_aus": "Modul aus", "bremse": "zu viele Versuche", "code_noetig": "neues Gerät, Code nötig",
    "angemeldet": "Gerät schon angemeldet", "ungueltig": "ungültig",
}
# Seit 1.11.31 (P2a): ein Ergebnis, das je Aktion etwas anderes heißt -- „unbekannt“ bei einer Unterlage ist kein unbekannter Link
ERGEBNIS_JE_AKTION = {("datei_angefordert", "unbekannt"): "nicht verfügbar"}


class PortalNicht(Exception):
    """Eine Aktion geht im jetzigen Zustand nicht (Router 409) -- der Text sagt, was zu tun ist."""


class ZugangFehlt(Exception):
    """Der Kunde hat keinen Zugang (Router 404)."""


# Seit 1.11.47 (Entscheidung des Betriebs 27.11.2026): Impressum und Datenschutz sind im Portal Pflicht. Beide verlinkt das Portal als
# https://<Webseite>/impressum bzw. /datenschutz aus den Unternehmensdaten (wie die Mails, app/portal_mails.py::firma()); ohne gültige Webseite gehen
# Modul einschalten, Portal am Kunden einschalten und Link senden nicht (409 mit diesem Grund), „Start“ zeigt den Hinweis (PFLICHT_HINWEIS), und das Portal
# selbst zeigt statt jeder Seite „Gerade klappt etwas nicht“ (app/portal/seiten.py::Seiten.pflicht_da()).
PFLICHT_FEHLT = ("Im Kundenportal fehlen sonst Impressum und Datenschutz: in den Unternehmensdaten steht keine gültige Webseite -- bitte zuerst unter "
                 "Einstellungen → Unternehmensdaten die Webseite eintragen.")
PFLICHT_HINWEIS = ("Im Kundenportal fehlen Impressum und Datenschutz: in den Unternehmensdaten steht keine gültige Webseite. Bis dahin zeigt das Portal "
                   "statt seiner Seiten „Gerade klappt etwas nicht“, und es geht kein Link hinaus.")


def pflicht_grund(db: Session) -> str | None:
    """Seit 1.11.47: None, wenn Impressum und Datenschutz verlinkt werden können; sonst der Grund (PFLICHT_FEHLT)."""
    f = portal_mails.firma(db)
    return None if f.impressum and f.datenschutz else PFLICHT_FEHLT


def email_anzeige(email: str) -> str:
    """Die verdeckte Anzeige für das Portal: erstes Zeichen, „***“, die Domain („m***@beispiel.de“). Die Adresse selbst sieht das Portal nie."""
    lokal, _, domain = email.rpartition("@")
    return f"{lokal[:1]}***@{domain}"


def _email(text: str | None) -> str:
    """Genau eine gültige Adresse (wie der Versand sie prüft)."""
    adressen = parse_recipients(text, label="E-Mail-Adresse")
    if len(adressen) != 1:
        raise ValueError("Bitte genau eine E-Mail-Adresse angeben.")
    if len(adressen[0]) > 255:
        raise ValueError("Die E-Mail-Adresse ist zu lang (höchstens 255 Zeichen).")
    return adressen[0]


def gueltig_bis_ab(jetzt_: datetime) -> datetime:
    """12 Monate ab jetzt (Kalendermonate; am 29.02. der 28.02.), naives UTC."""
    return datetime.combine(add_months(jetzt_.date(), GUELTIG_MONATE), jetzt_.time())


def zugang_von(db: Session, kunde_id: int, *, sperren: bool = False) -> PortalZugang | None:
    abfrage = select(PortalZugang).where(PortalZugang.customer_id == kunde_id)
    if sperren:
        abfrage = abfrage.with_for_update()
    return db.scalar(abfrage)


def _sitzungen_beenden(db: Session, zugang_id: int, grund: str, jetzt_: datetime) -> int:
    return db.execute(update(PortalSitzung).where(PortalSitzung.zugang_id == zugang_id, PortalSitzung.beendet_am.is_(None))
                      .values(beendet_am=jetzt_, beendet_grund=grund).execution_options(synchronize_session=False)).rowcount


def _letzter_versand(db: Session, zugang_id: int) -> EmailDispatch | None:
    return db.scalar(select(EmailDispatch).where(EmailDispatch.document_type == "portal_link", EmailDispatch.document_id == zugang_id)
                     .order_by(EmailDispatch.created_at.desc(), EmailDispatch.id.desc()).limit(1))


def zustand(kunde: Customer, zugang: PortalZugang | None, jetzt_: datetime, versand: EmailDispatch | None = None) -> str:
    """versand: der letzte Versand des Links (seit 1.11.13: ist er gescheitert, heißt der Zustand „gescheitert“ -- der Link ging nie hinaus)."""
    if kunde.archiviert_am is not None:  # im Archiv wirkt kein Zugang (portal_zugang_grund() -> „archiv“), gleich was sonst gilt
        return "archiv"
    if not kunde.portal_aktiv:
        return "aus"
    if zugang is None:
        return "kein_zugang" if (kunde.email or "").strip() else "ohne_email"
    if zugang.gesperrt_am is not None:
        return "gesperrt"
    if zugang.link_sha256 is None or zugang.gueltig_bis is None:
        return "ohne_link"
    if zugang.gueltig_bis <= jetzt_:
        return "abgelaufen"
    if versand is not None and versand.status == "fehlgeschlagen":
        return "gescheitert"
    if zugang.gueltig_bis - jetzt_ <= timedelta(days=HINWEIS_TAGE):
        return "laeuft_ab"
    return "aktiv"


def stand(db: Session, kunde: Customer, jetzt_: datetime) -> dict:
    """Alles, was die Karte zeigt -- liest nur."""

    zugang = zugang_von(db, kunde.id)
    versand = _letzter_versand(db, zugang.id) if zugang is not None else None
    z = zustand(kunde, zugang, jetzt_, versand)
    return {
        "aktiv": bool(kunde.portal_aktiv), "zustand": z, "zustand_text": ZUSTAENDE[z], "kunde_email": (kunde.email or "").strip() or None,
        "nur_lesen": kunde.archiviert_am is not None,
        "zugang": None if zugang is None else {
            "email": zugang.email, "link_erzeugt_am": zugang.link_erzeugt_am, "gueltig_bis": zugang.gueltig_bis,
            "zuletzt_genutzt_am": zugang.zuletzt_genutzt_am, "angelegt_am": zugang.angelegt_am,
            "angelegt_von": zugang.angelegt_von_name, "gesperrt_am": zugang.gesperrt_am, "gesperrt_grund": zugang.gesperrt_grund,
            "gesperrt_von": zugang.gesperrt_von_name, "hat_link": zugang.link_sha256 is not None,
        },
        "versand": None if versand is None else {
            "status": versand.status, "am": versand.finished_at or versand.created_at, "von": versand.created_by_name,
            "an": versand.to_recipients,
        },
    }


# --- Aktionen (jede committet; der Router prüft Modul, Rolle und Archiv vorab -- Sperren geht seit 1.11.13 auch im Archiv) ---------------------------

def _nicht_im_archiv(kunde: Customer) -> None:
    if kunde.archiviert_am is not None:  # zweite Sicherung -- archiv_vorab() an der Route lehnt vorher ab
        raise PortalNicht("Der Kunde ist im Archiv -- erst zurückholen.")


def schalten(db: Session, kunde: Customer, an: bool, jetzt_: datetime) -> None:
    """Portal am Kunden an oder aus. Aus beendet alle Sitzungen des Zugangs (Grund portal_aus). Seit 1.11.37 (Stufe P2c): An wendet gleich die
    automatischen Regeln an (app/portal_freigaben.py::regeln_anwenden(), auch für alles, was vor der Einladung entstand) -- so zeigt die Karte vor dem
    Einladen, was der Kunde dann sieht; danach hält der Postbote sie aktuell."""
    from . import portal_freigaben

    _nicht_im_archiv(kunde)
    if an and (grund := pflicht_grund(db)):  # seit 1.11.47: ausschalten geht immer
        raise PortalNicht(grund)
    zugang = zugang_von(db, kunde.id, sperren=True)
    war_an = bool(kunde.portal_aktiv)
    kunde.portal_aktiv = an
    if an:  # seit 1.11.51 (W1c Stufe 2, S2-0 c): „Portal aus seit“ nur beim Wechsel von an auf aus, leer, sobald es wieder an ist
        kunde.portal_aus_seit = None
    elif war_an:
        kunde.portal_aus_seit = jetzt_
    if not an and zugang is not None:
        _sitzungen_beenden(db, zugang.id, "portal_aus", jetzt_)
    db.commit()
    if an:
        portal_freigaben.regeln_anwenden(db, kunde)


def zugang_anlegen(db: Session, kunde: Customer, email: str, jetzt_: datetime, *, user_id: int | None, user_name: str | None) -> PortalZugang:
    _nicht_im_archiv(kunde)
    if not kunde.portal_aktiv:
        raise PortalNicht("Erst das Kundenportal für diesen Kunden einschalten.")
    if not (kunde.email or "").strip():
        raise PortalNicht(ZUSTAENDE["ohne_email"])
    if zugang_von(db, kunde.id) is not None:
        raise PortalNicht("Der Kunde hat schon einen Zugang.")
    adresse = _email(email)
    zugang = PortalZugang(customer_id=kunde.id, email=adresse, email_anzeige=email_anzeige(adresse), angelegt_am=jetzt_, angelegt_von_user_id=user_id,
                          angelegt_von_name=user_name or "System")
    db.add(zugang)
    db.commit()
    return zugang


@dataclass(frozen=True)
class Gesendet:
    ergebnis: DispatchResult
    neu: bool  # ein früherer Link galt nicht mehr


def link_senden(db: Session, kunde: Customer, email: str, dispatch_key: str, jetzt_: datetime, *, user_id: int | None,
                user_name: str | None) -> Gesendet:
    """Neuer Link für den Zugang, gesendet an die (geänderte) Adresse. Der Wert steht nur in der Mail; gespeichert wird sein Prüfwert -- zusammen mit dem
    Eintrag „in Arbeit“ im Versandprotokoll, bevor gesendet wird (dispatch_email() committet ihn). Scheitert der Versand danach, gilt der neue Link trotzdem
    (die Karte zeigt „Versand gescheitert“; ein neuer Klick erzeugt wieder einen). Eine Wiederholung desselben Klicks (dispatch_key) erzeugt nichts."""
    _nicht_im_archiv(kunde)
    vorher = db.scalar(select(EmailDispatch).where(EmailDispatch.dispatch_key == (dispatch_key or "").strip()))
    if vorher is not None:  # derselbe Klick noch einmal: nichts erzeugen, dieselbe Antwort
        if vorher.document_type != "portal_link" or vorher.document_id != getattr(zugang_von(db, kunde.id), "id", None):
            raise PortalNicht("Dieser Versand gehört zu einem anderen Vorgang -- bitte die Seite neu laden.")
        if vorher.status != "gesendet":  # wie dispatch_email(): ein laufender oder gescheiterter Versand wird nicht wiederholt
            raise PortalNicht("Dieser Versand läuft noch oder ist gescheitert -- für einen neuen Versuch bitte noch einmal „Link senden“.")
        return Gesendet(ergebnis=DispatchResult(dispatch=vorher, newly_sent=False), neu=False)
    if not kunde.portal_aktiv:
        raise PortalNicht("Erst das Kundenportal für diesen Kunden einschalten.")
    if grund := pflicht_grund(db):  # seit 1.11.47: kein Link in ein Portal ohne Impressum und Datenschutz
        raise PortalNicht(grund)
    zugang = zugang_von(db, kunde.id, sperren=True)
    if zugang is None:
        raise ZugangFehlt("Der Kunde hat noch keinen Zugang.")
    if zugang.gesperrt_am is not None:
        raise PortalNicht("Der Zugang ist gesperrt -- erst entsperren.")
    adresse = _email(email)
    neu = zugang.link_sha256 is not None
    if adresse != zugang.email:
        zugang.email, zugang.email_anzeige = adresse, email_anzeige(adresse)
    wert = pruefwerte.neuer_wert()
    zugang.link_sha256, zugang.link_erzeugt_am, zugang.gueltig_bis = pruefwerte.link(wert), jetzt_, gueltig_bis_ab(jetzt_)
    if neu:
        _sitzungen_beenden(db, zugang.id, "neu_erzeugt", jetzt_)
    html_ = portal_mails.link_html(db, kunde, portal_mails.link_adresse(wert), zugang.gueltig_bis)
    del wert
    try:
        ergebnis = portal_mails.senden(db, art="portal_link", dokument_id=zugang.id, an=adresse, html_=html_, dispatch_key=dispatch_key,
                                       user_id=user_id, user_name=user_name)
    except Exception:
        # Lehnt dispatch_email() vor dem Eintrag „in Arbeit“ ab (SMTP, Adresse, laufender Versand), ist nichts committet -- der neue Link, die E-Mail
        # und das Abmelden fallen weg (die Abfragen davor hatten sie schon geflusht). Scheiterte erst der Versand, ist alles schon committet: der neue Link
        # gilt, die Karte zeigt „Versand gescheitert“.
        db.rollback()
        raise
    finally:
        del html_
    return Gesendet(ergebnis=ergebnis, neu=neu)


def sperren(db: Session, kunde: Customer, grund: str, jetzt_: datetime, *, user_id: int | None, user_name: str | None) -> None:
    """Seit 1.11.13 auch im Archiv (Festlegung 1.11.0, Antwort des Betriebs 24.11.2026): Sperren nimmt nur Zugang weg -- sonst wäre der Zugang nach dem
    Zurückholen offen, bis jemand sperrt. Der Zugang zählt nicht zum Vorgang des Archivs (app/archivschutz.py, KEIN_TEIL)."""
    zugang = zugang_von(db, kunde.id, sperren=True)
    if zugang is None:
        raise ZugangFehlt("Der Kunde hat noch keinen Zugang.")
    if zugang.gesperrt_am is not None:
        raise PortalNicht("Der Zugang ist schon gesperrt.")
    zugang.gesperrt_am, zugang.gesperrt_grund, zugang.gesperrt_von_user_id, zugang.gesperrt_von_name = jetzt_, grund, user_id, user_name or "System"
    _sitzungen_beenden(db, zugang.id, "gesperrt", jetzt_)
    db.commit()


def entsperren(db: Session, kunde: Customer) -> None:
    _nicht_im_archiv(kunde)
    zugang = zugang_von(db, kunde.id, sperren=True)
    if zugang is None:
        raise ZugangFehlt("Der Kunde hat noch keinen Zugang.")
    if zugang.gesperrt_am is None:
        raise PortalNicht("Der Zugang ist nicht gesperrt.")
    zugang.gesperrt_am = zugang.gesperrt_grund = zugang.gesperrt_von_user_id = zugang.gesperrt_von_name = None
    db.commit()


VERLAENGERN_NICHT = {  # seit 1.11.13: Verlängern nur, solange der Link gilt (LINK_GILT)
    "aus": "Erst das Kundenportal für diesen Kunden einschalten.",
    "ohne_link": "Es gibt noch keinen Link -- erst einen Link senden.",
    "gesperrt": "Der Zugang ist gesperrt -- erst entsperren.",
    "abgelaufen": "Der Link ist abgelaufen und lebt nicht wieder auf -- bitte einen neuen Link senden.",
    "gescheitert": "Der Link ging nicht hinaus -- bitte den Link erneut senden.",
}


def verlaengern(db: Session, kunde: Customer, jetzt_: datetime) -> None:
    """Gültig bis = heute + 12 Monate, derselbe Link -- seit 1.11.13 nur, solange er gilt (aktiv, läuft bald ab)."""
    _nicht_im_archiv(kunde)
    zugang = zugang_von(db, kunde.id, sperren=True)
    if zugang is None:
        raise ZugangFehlt("Der Kunde hat noch keinen Zugang.")
    z = zustand(kunde, zugang, jetzt_, _letzter_versand(db, zugang.id))
    if z not in LINK_GILT:
        raise PortalNicht(VERLAENGERN_NICHT.get(z, ZUSTAENDE.get(z, z)))
    zugang.gueltig_bis = gueltig_bis_ab(jetzt_)
    db.commit()


# --- Protokoll: Portal, Versand und Änderungshistorie zusammen -- seit 1.11.13 eine Zeile je Aktion --------------------------------------------------

# Was das Protokoll aus der Änderungshistorie des Zugangs liest -- der Rest ist Buchhaltung des Zugangs (Konto-Kennungen, verdeckte Anzeige, angelegt von)
PROTOKOLL_FELDER = ("email", "link_erzeugt_am", "gueltig_bis", "gesperrt_am", "gesperrt_grund")
# Welche Aktion ein Feld ändert: E-Mail und „Link erzeugt“ nur Link senden, „gültig bis“ Link senden oder Verlängern, die Sperre Sperren und Entsperren.
FELD_ART = {"email": "link", "link_erzeugt_am": "link", "gueltig_bis": "frist", "gesperrt_am": "sperre", "gesperrt_grund": "sperre"}
_SPALTEN = [c.key for c in PortalZugang.__table__.columns]  # in dieser Reihenfolge schreibt die Historie die Felder eines Flushs
GRUPPE_SEKUNDEN = 5  # wie der Verlauf der Akte (app/akte_verlauf.py)
ZEILEN_JE_AKTION = 8  # höchstens so viele Zeilen der Historie hat eine Aktion am Zugang (Link senden: 3)


def _tag(wert: str | None) -> str:
    """Ein Zeitpunkt aus der Historie (naives UTC, isoformat) als Tag in Berlin."""
    from .berlin_time import to_berlin
    try:
        return to_berlin(datetime.fromisoformat(wert)).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return wert or "–"


@dataclass
class _Aktion:
    """Die Zeilen der Historie, die eine Aktion am Zugang schrieb (ein Flush): dasselbe Konto, höchstens GRUPPE_SEKUNDEN auseinander, die Felder in der
    Reihenfolge der Spalten, jedes höchstens einmal, nur verträgliche Arten (Link mit Frist; Sperre allein)."""
    zeilen: dict
    erste: AuditLog
    letzte: AuditLog
    versand: EmailDispatch | None = None

    @property
    def art(self) -> str:
        if self.erste.field_name is None:
            return "angelegt" if self.erste.action == "angelegt" else self.erste.action
        if "link_erzeugt_am" in self.zeilen or "email" in self.zeilen:
            return "link"
        if "gesperrt_am" in self.zeilen:
            return "gesperrt" if self.zeilen["gesperrt_am"].new_value else "entsperrt"
        if "gueltig_bis" in self.zeilen:
            return "verlaengert"
        return "sperre"


def _passt(g: _Aktion, a: AuditLog) -> bool:
    if g.erste.field_name is None or a.field_name is None:  # Anlegen ist immer eine Aktion für sich
        return False
    if (a.actor_user_id, a.actor_name) != (g.letzte.actor_user_id, g.letzte.actor_name):
        return False
    if abs((a.occurred_at - g.letzte.occurred_at).total_seconds()) > GRUPPE_SEKUNDEN:
        return False
    if a.field_name in g.zeilen or _SPALTEN.index(a.field_name) < _SPALTEN.index(g.letzte.field_name):  # ein Flush schreibt jedes Feld einmal, der Reihe nach
        return False
    arten = {FELD_ART[f] for f in g.zeilen} | {FELD_ART[a.field_name]}
    return arten <= {"link", "frist"} or arten == {"sperre"}


def _aktionen(zeilen: list[AuditLog]) -> list[_Aktion]:
    """zeilen: die Historie des Zugangs, älteste zuerst."""
    gruppen: list[_Aktion] = []
    for a in zeilen:
        if gruppen and _passt(gruppen[-1], a):
            gruppen[-1].zeilen[a.field_name] = a
            gruppen[-1].letzte = a
        else:
            gruppen.append(_Aktion(zeilen={a.field_name: a} if a.field_name else {}, erste=a, letzte=a))
    return gruppen


def _versand_zuordnen(gruppen: list[_Aktion], versand: list[EmailDispatch]) -> list[EmailDispatch]:
    """Jeder Link der Historie bekommt den Versand, den dieselbe Anfrage anlegte (der nächste in der Zeit, höchstens GRUPPE_SEKUNDEN entfernt); was übrig
    bleibt, steht für sich (Rand einer Seite)."""
    offen = [g for g in gruppen if g.art == "link"]
    uebrig = []
    for d in sorted(versand, key=lambda x: (x.created_at, x.id)):
        nah = [g for g in offen if abs((d.created_at - g.letzte.occurred_at).total_seconds()) <= GRUPPE_SEKUNDEN]
        vorher = [g for g in nah if g.letzte.occurred_at <= d.created_at]  # die Historie schreibt der Link vor dem Versand (link_html() flusht)
        if nah:
            g = (max(vorher, key=lambda x: (x.letzte.occurred_at, x.erste.id)) if vorher
                 else min(nah, key=lambda x: (abs((d.created_at - x.letzte.occurred_at).total_seconds()), x.erste.id)))
            g.versand = d
            offen.remove(g)
        else:
            uebrig.append(d)
    return uebrig


def _link_text(neu: bool, versand: EmailDispatch | None, gueltig: str | None, vorher: str | None) -> str:
    wort = "Neuer Link" if neu else "Link"
    an = versand.to_recipients if versand is not None else None
    if versand is None:
        text = f"{wort} erzeugt" + (f" – gültig bis {gueltig}" if gueltig else "")
    elif versand.status == "gesendet":
        text = f"{wort} gesendet an {an}" + (f" – gültig bis {gueltig}" if gueltig else "")
    elif versand.status == "fehlgeschlagen":
        text = f"{wort} nicht gesendet – Versand an {an} gescheitert"
    else:
        text = f"{wort} wird gesendet an {an}"
    return text + (f" (E-Mail vorher {vorher})" if vorher else "")


def _aktion_text(g: _Aktion, erster_versand: int | None) -> str | None:
    """Eine Aktion als Satz (seit 1.11.13) -- None = nicht zeigen. erster_versand: der erste Versand eines Links an diesen Zugang -- jeder spätere ist ein
    neuer Link (jeder Link geht genau einmal hinaus; lehnt der Versand vorher ab, gibt es keinen Link)."""
    art = g.art
    if art == "angelegt":
        try:
            email = json.loads(g.erste.details or "{}").get("email")
        except ValueError:
            email = None
        return f"Zugang angelegt für {email}" if email else "Zugang angelegt"
    if art == "link":
        erzeugt, email, frist = g.zeilen.get("link_erzeugt_am"), g.zeilen.get("email"), g.zeilen.get("gueltig_bis")
        neu = g.versand.id != erster_versand if g.versand is not None else bool(erzeugt is not None and erzeugt.old_value)
        vorher = email.old_value if email is not None and email.old_value and email.old_value != email.new_value else None
        return _link_text(neu, g.versand, _tag(frist.new_value) if frist is not None and frist.new_value else None, vorher)
    if art == "verlaengert":
        return f"Link verlängert – gültig bis {_tag(g.zeilen['gueltig_bis'].new_value)}"
    if art == "gesperrt":
        grund = g.zeilen.get("gesperrt_grund")
        return f"Zugang gesperrt – Grund: {grund.new_value}" if grund is not None and grund.new_value else "Zugang gesperrt"
    if art == "entsperrt":
        return "Zugang entsperrt"
    if art == "gelöscht":
        return "Zugang gelöscht"
    return None


def protokoll(db: Session, kunde: Customer, seite: int = 1) -> dict:
    """Je Seite SEITE Einträge, neueste zuerst: das Zugriffsprotokoll des Zugangs (Aktion und Ergebnis in Worten), jede Aktion des Büros am Zugang als eine
    Zeile (seit 1.11.13: die Felder der Änderungshistorie einer Aktion zusammen, der Link mit seinem Versand -- „Neuer Link gesendet an … – gültig bis …
    (E-Mail vorher …)“) und der Schalter am Kunden; Konto, Zeit. Ohne IP-Adressen -- das Zugriffsprotokoll hat keine."""
    zugang = zugang_von(db, kunde.id)
    bis = seite * SEITE + 1
    zeilen = []
    if zugang is not None:
        for z in db.scalars(select(PortalZugriff).where(PortalZugriff.zugang_id == zugang.id)
                            .order_by(PortalZugriff.zeitpunkt.desc(), PortalZugriff.id.desc()).limit(bis)):
            ergebnis = ERGEBNIS_JE_AKTION.get((z.aktion, z.ergebnis), ERGEBNIS_TEXT.get(z.ergebnis, z.ergebnis))
            zeilen.append((z.zeitpunkt, 0, z.id, {"art": "portal", "text": AKTION_TEXT.get(z.aktion, z.aktion) + (f" – {ergebnis}" if ergebnis else ""),
                                                   "von": "Kundenportal"}))
        grenze = bis * ZEILEN_JE_AKTION
        historie = list(db.scalars(select(AuditLog).where(AuditLog.entity_type == ZUGANG_ART, AuditLog.entity_id == str(zugang.id),
                                                          AuditLog.field_name.is_(None) | AuditLog.field_name.in_(PROTOKOLL_FELDER))
                                   .order_by(AuditLog.id.desc()).limit(grenze)))
        abgeschnitten = len(historie) == grenze
        gruppen = _aktionen(list(reversed(historie)))
        if abgeschnitten and gruppen:  # die älteste Aktion kann unvollständig sein -- sie steht auf einer späteren Seite
            gruppen = gruppen[1:]
        versand = list(db.scalars(select(EmailDispatch).where(EmailDispatch.document_type == "portal_link", EmailDispatch.document_id == zugang.id)
                                  .order_by(EmailDispatch.created_at.desc(), EmailDispatch.id.desc()).limit(bis)))
        if abgeschnitten and gruppen:
            versand = [d for d in versand if (d.created_at - gruppen[0].erste.occurred_at).total_seconds() >= -GRUPPE_SEKUNDEN]
        erster = db.scalar(select(EmailDispatch.id).where(EmailDispatch.document_type == "portal_link", EmailDispatch.document_id == zugang.id)
                           .order_by(EmailDispatch.created_at, EmailDispatch.id).limit(1))
        for d in _versand_zuordnen(gruppen, versand):
            zeilen.append((d.created_at, 2, d.id, {"art": "versand", "text": _link_text(d.id != erster, d, None, None), "von": d.created_by_name or "System"}))
        for g in gruppen:
            text = _aktion_text(g, erster)
            if text:
                von = g.versand.created_by_name if g.versand is not None and g.versand.created_by_name else (g.erste.actor_name or "System")
                zeilen.append((g.erste.occurred_at, 1, g.erste.id, {"art": "buero", "text": text, "von": von}))
    for a in db.scalars(select(AuditLog).where(AuditLog.entity_type == "Kunde", AuditLog.entity_id == str(kunde.id), AuditLog.field_name == "portal_aktiv")
                        .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).limit(bis)):
        zeilen.append((a.occurred_at, 1, a.id, {"art": "buero", "text": "Kundenportal eingeschaltet" if a.new_value == "Ja" else "Kundenportal ausgeschaltet",
                                                 "von": a.actor_name or "System"}))
    zeilen.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    teil = zeilen[(seite - 1) * SEITE: seite * SEITE]
    return {"seite": seite, "weiter": len(zeilen) > seite * SEITE,
            "eintraege": [{"zeitpunkt": t, **inhalt} for t, _o, _i, inhalt in teil]}
