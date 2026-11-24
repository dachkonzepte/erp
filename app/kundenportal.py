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
"""

from __future__ import annotations

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
    "archiv": "Der Kunde ist im Archiv – sein Zugang wirkt nicht; die Karte ist nur lesbar.",
    "aus": "Das Kundenportal ist für diesen Kunden aus.",
    "ohne_email": "Erst eine E-Mail-Adresse beim Kunden eintragen.",
    "kein_zugang": "Noch kein Zugang.",
    "ohne_link": "Zugang angelegt, noch kein Link versendet.",
    "aktiv": "Link versendet.",
    "laeuft_ab": "Der Link läuft bald ab.",
    "abgelaufen": "Der Link ist abgelaufen.",
    "gesperrt": "Der Zugang ist gesperrt.",
}

# Zugriffsprotokoll des Portals in Worten (app/portal/werte.py::AKTIONEN, ERGEBNISSE)
AKTION_TEXT = {
    "link_geoeffnet": "Link geöffnet", "code_angefordert": "Code angefordert", "code_gesendet": "Code gesendet",
    "code_fehler": "Code nicht gesendet", "code_falsch": "Code falsch eingegeben", "code_abgelaufen": "Code abgelaufen",
    "angemeldet": "Angemeldet", "verlaengert": "Anmeldung verlängert", "abgemeldet": "Abgemeldet",
    "ueberall_abgemeldet": "Auf allen Geräten abgemeldet",
}
ERGEBNIS_TEXT = {
    "ok": "", "unbekannt": "unbekannter Link", "gesperrt": "Zugang gesperrt", "abgelaufen": "Link abgelaufen", "portal_aus": "Portal aus",
    "archiv": "Kunde im Archiv", "modul_aus": "Modul aus", "bremse": "zu viele Versuche", "code_noetig": "neues Gerät, Code nötig",
    "angemeldet": "Gerät schon angemeldet", "ungueltig": "ungültig",
}


class PortalNicht(Exception):
    """Eine Aktion geht im jetzigen Zustand nicht (Router 409) -- der Text sagt, was zu tun ist."""


class ZugangFehlt(Exception):
    """Der Kunde hat keinen Zugang (Router 404)."""


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


def zustand(kunde: Customer, zugang: PortalZugang | None, jetzt_: datetime) -> str:
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
    if zugang.gueltig_bis - jetzt_ <= timedelta(days=HINWEIS_TAGE):
        return "laeuft_ab"
    return "aktiv"


def stand(db: Session, kunde: Customer, jetzt_: datetime) -> dict:
    """Alles, was die Karte zeigt -- liest nur."""

    zugang = zugang_von(db, kunde.id)
    z = zustand(kunde, zugang, jetzt_)
    versand = _letzter_versand(db, zugang.id) if zugang is not None else None
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


# --- Aktionen (jede committet; der Router prüft Modul, Rolle und Archiv vorab) ---------------------------------------------------------------------

def _nicht_im_archiv(kunde: Customer) -> None:
    if kunde.archiviert_am is not None:  # zweite Sicherung -- archiv_vorab() am Router lehnt vorher ab
        raise PortalNicht("Der Kunde ist im Archiv -- erst zurückholen.")


def schalten(db: Session, kunde: Customer, an: bool, jetzt_: datetime) -> None:
    """Portal am Kunden an oder aus. Aus beendet alle Sitzungen des Zugangs (Grund portal_aus)."""
    _nicht_im_archiv(kunde)
    zugang = zugang_von(db, kunde.id, sperren=True)
    kunde.portal_aktiv = an
    if not an and zugang is not None:
        _sitzungen_beenden(db, zugang.id, "portal_aus", jetzt_)
    db.commit()


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
    _nicht_im_archiv(kunde)
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


def verlaengern(db: Session, kunde: Customer, jetzt_: datetime) -> None:
    """Gültig bis = heute + 12 Monate, derselbe Link."""
    _nicht_im_archiv(kunde)
    zugang = zugang_von(db, kunde.id, sperren=True)
    if zugang is None:
        raise ZugangFehlt("Der Kunde hat noch keinen Zugang.")
    if zugang.gesperrt_am is not None:
        raise PortalNicht("Der Zugang ist gesperrt -- erst entsperren.")
    if zugang.link_sha256 is None:
        raise PortalNicht("Es gibt noch keinen Link -- erst einen Link senden.")
    zugang.gueltig_bis = gueltig_bis_ab(jetzt_)
    db.commit()


# --- Protokoll: Portal, Versand und Änderungshistorie zusammen ----------------------------------------------------------------------------------

# Was das Protokoll aus der Änderungshistorie des Zugangs zeigt -- der Rest ist Buchhaltung des Zugangs (Konto-Kennungen, verdeckte Anzeige, angelegt von)
PROTOKOLL_FELDER = ("email", "link_erzeugt_am", "gueltig_bis", "gesperrt_am", "gesperrt_grund")


def _tag(wert: str | None) -> str:
    """Ein Zeitpunkt aus der Historie (naives UTC, isoformat) als Tag in Berlin."""
    from .berlin_time import to_berlin
    try:
        return to_berlin(datetime.fromisoformat(wert)).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return wert or "–"


def _historie_text(a: AuditLog) -> str | None:
    """Ein Eintrag der Änderungshistorie als Satz (seit 1.11.11); None = nicht zeigen."""
    if a.entity_type != ZUGANG_ART:  # der Schalter am Kunden
        return "Kundenportal eingeschaltet" if a.new_value == "Ja" else "Kundenportal ausgeschaltet"
    if a.field_name is None:
        return {"angelegt": "Zugang angelegt", "gelöscht": "Zugang gelöscht"}.get(a.action, a.action)
    if a.field_name == "email":
        return f"E-Mail des Zugangs: {a.old_value or '–'} → {a.new_value or '–'}"
    if a.field_name == "link_erzeugt_am":
        return "Neuer Link erzeugt" if a.new_value else None
    if a.field_name == "gueltig_bis":
        return f"Link gültig bis {_tag(a.new_value)}" if a.new_value else None
    if a.field_name == "gesperrt_am":
        return "Zugang gesperrt" if a.new_value else "Zugang entsperrt"
    if a.field_name == "gesperrt_grund":
        return f"Grund der Sperre: {a.new_value}" if a.new_value else None
    return None


VERSAND_TEXT = {"gesendet": "Link gesendet an {an}", "fehlgeschlagen": "Link nicht gesendet (an {an})", "in_arbeit": "Link wird gesendet an {an}"}


def protokoll(db: Session, kunde: Customer, seite: int = 1) -> dict:
    """Je Seite SEITE Einträge, neueste zuerst: das Zugriffsprotokoll des Zugangs (Aktion und Ergebnis in Worten), die Mails mit dem Link
    (Versandprotokoll) und die Änderungshistorie des Zugangs und des Schalters am Kunden als Sätze (seit 1.11.11; Konto, Zeit). Ohne IP-Adressen -- das
    Zugriffsprotokoll hat keine."""
    zugang = zugang_von(db, kunde.id)
    bis = seite * SEITE + 1
    zeilen = []
    if zugang is not None:
        for z in db.scalars(select(PortalZugriff).where(PortalZugriff.zugang_id == zugang.id)
                            .order_by(PortalZugriff.zeitpunkt.desc(), PortalZugriff.id.desc()).limit(bis)):
            ergebnis = ERGEBNIS_TEXT.get(z.ergebnis, z.ergebnis)
            zeilen.append((z.zeitpunkt, 0, z.id, {"art": "portal", "text": AKTION_TEXT.get(z.aktion, z.aktion) + (f" – {ergebnis}" if ergebnis else ""),
                                                   "von": "Kundenportal"}))
        for d in db.scalars(select(EmailDispatch).where(EmailDispatch.document_type == "portal_link", EmailDispatch.document_id == zugang.id)
                            .order_by(EmailDispatch.created_at.desc(), EmailDispatch.id.desc()).limit(bis)):
            text = VERSAND_TEXT.get(d.status, "Link: {an}").format(an=d.to_recipients)
            zeilen.append((d.created_at, 2, d.id, {"art": "versand", "text": text, "von": d.created_by_name or "System"}))
    bedingung = (AuditLog.entity_type == "Kunde") & (AuditLog.entity_id == str(kunde.id)) & (AuditLog.field_name == "portal_aktiv")
    if zugang is not None:
        bedingung = or_(bedingung, (AuditLog.entity_type == ZUGANG_ART) & (AuditLog.entity_id == str(zugang.id))
                        & (AuditLog.field_name.is_(None) | AuditLog.field_name.in_(PROTOKOLL_FELDER)))
    for a in db.scalars(select(AuditLog).where(bedingung).order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).limit(bis)):
        text = _historie_text(a)
        if text:
            zeilen.append((a.occurred_at, 1, a.id, {"art": "buero", "text": text, "von": a.actor_name or "System"}))
    zeilen.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    teil = zeilen[(seite - 1) * SEITE: seite * SEITE]
    return {"seite": seite, "weiter": len(zeilen) > seite * SEITE,
            "eintraege": [{"zeitpunkt": t, **inhalt} for t, _o, _i, inhalt in teil]}
