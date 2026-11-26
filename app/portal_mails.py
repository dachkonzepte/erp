"""Mails des Kundenportals (seit 1.11.5, Stufe P1c; Bauplan P1, Abschnitt 4) -- der Link zum Portal und der Anmeldecode.

- Feste Texte im Code (P1-7), gesiezt (Kundentexte, tests/test_v440_runde_du.py) -- mit einer Vorlage in den Einstellungen ließe sich der
  Sicherheitshinweis entfernen oder der Link in den Betreff setzen; Änderungen deshalb nur über eine Version.
- Der Betreff ist fest und enthält weder Link noch Code: das Versandprotokoll speichert Empfänger und Betreff, nie den Text (Regel 18).
- Gesendet wird nur über Microsoft 365 und ohne Kopie in „Gesendete Elemente“ (P1-3) -- Link und Code lägen sonst im Postfach des Betriebs.
  dispatch_email(gesendete_elemente=False) lehnt den Versand über SMTP ab, bevor etwas geschrieben wird.
- senden() ist der einzige Weg für Mails des Portals: tests/test_v804_portal_mails.py prüft per AST, dass keine andere Stelle eine Versandart des Portals
  oder den Schalter gesendete_elemente nimmt.

Seit 1.11.8 als HTML nach dem freigegebenen Entwurf (bildgrundlage/entwurf-p1/Portal-Mails.dc.html; Wortlaut verbindlich): Name des Betriebs als Text,
grüne Linie, Knopf „Kundenportal öffnen“ (seit 1.11.24 Polster und Hintergrund an der Tabellenzelle), Code in Gruppen („481 207“). Nur Tabellen und Stile in den Tags, höchstens 600 px breit, keine Bilder, keine
Schriften, kein <style>, nichts von außen -- geprüft in tests/test_v807_portal_mails_html.py. Ein Textteil daneben ginge über Graph nur mit eigenem
MIME-Bau (sendMail nimmt genau einen Körper, Text oder HTML) -- deshalb nur HTML.

- Jeder eingesetzte Wert geht durch html.escape() (_e). Der Link kommt nur nach link_pruefen() in den Knopf: genau PORTAL_ADRESSE + „/#z=“ + ein Wert in
  der Form von app/portal/pruefwerte.py::neuer_wert() (43 Zeichen URL-sicher).
- Telefon, Fußzeile, Impressum und Datenschutz aus den Firmendaten der Einstellungen (P1-14, firma()). Impressum und Datenschutz sind die Seiten der
  Webseite (Bauplan P1, Abschnitt 5: „Links auf die Webseite“), so wie die Webseite selbst sie verlinkt: https://<Webseite>/impressum und /datenschutz.
  Ohne gültige Webseite fehlen beide Links und die Webseite in der Fußzeile; ohne Telefon fällt nur die Nummer weg, der Satz „rufen Sie uns … an“ bleibt.
- Seit 1.11.12 (§ 35a GmbHG) darunter eine kleine Zeile „Sitz <Ort> · <Registergericht> <Registernummer> · Geschäftsführer: <Name(n)>“ aus den
  Firmendaten (Sitz = Ort der Anschrift; ein eigenes Feld dafür gibt es nicht); fehlt ein Feld, fällt nur dieses weg, fehlen alle, fehlt die Zeile. Seit
  1.11.17 kommen Anschrift und Pflichtangaben aus app/firmenangaben.py -- derselben Quelle wie die Zeilen unter jeder anderen Mail an Kunden.

Link (ab P1d) und Code (Postbote, ab 1.11.6) stehen nur im Text der Mail und kurz im Speicher -- nie in einer Tabelle, einem Protokoll, einer Antwort oder
einer Ausnahme.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from .berlin_time import to_berlin
from .email_dispatch import PORTAL_TYPES, DispatchResult, dispatch_email
from .firmenangaben import anschrift as firmen_anschrift
from .firmenangaben import pflichtangaben  # noqa: F401 -- seit 1.11.17 dort (eine Quelle für Portal und ERP)
from .models import Customer
from .portal.begruessung import begruessung
from .settings import load_general_settings

# Versandart -> Betreff (fest, ohne Link und Code)
BETREFF = {"portal_link": "Ihr Zugang zum Kundenportal", "portal_code": "Ihr Anmeldecode für das Kundenportal"}
assert set(BETREFF) == set(PORTAL_TYPES), "jede Versandart des Portals braucht ihren festen Betreff"
CODE_MINUTEN = 10  # wie portal_code_pruefen() und der Postbote (gültig bis)
SITZUNG_TAGE = 30  # wie die Sitzung des Portals (F2)

# Die Adresse des Portals (F1) -- fest im Code, nie aus der Umgebung: der Satz „finden Sie immer unter …“ und der Link können so nicht auseinanderlaufen.
# Die Einheit des Portals bekommt denselben Wert als PORTAL_HERKUNFT (scripts/server/portal.env.beispiel, geprüft in test_v807).
PORTAL_ADRESSE = "https://kunde.dachkonzepte.gmbh"
PORTAL_HOST = PORTAL_ADRESSE.removeprefix("https://")
LINK_MUSTER = re.compile(re.escape(PORTAL_ADRESSE) + r"/#z=[A-Za-z0-9_-]{43}")
LINK_FALSCH = "Der Link zum Kundenportal hat nicht die erwartete Form -- es wurde nichts versendet."
_HOST = re.compile(r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}")

# Farben und Maße des Entwurfs
_GRUEN, _TEXT, _TITEL, _LEISE, _MARKE, _MARKE_2 = "#367337", "#2B3238", "#171C1F", "#4B555D", "#1F2529", "#5A646C"
_FLAECHE, _GRAU, _RAND, _LINK = "#EEF0F1", "#F3F5F6", "#DADEE1", "#1D5FA8"
_SCHRIFT = "Arial, Helvetica, sans-serif"  # Systemschrift -- keine Schrift von außen
_MONO = "Consolas, 'Courier New', monospace"


def _e(wert: object) -> str:
    return html.escape(str(wert), quote=True)


def link_pruefen(adresse: str) -> str:
    """Nur ein Link genau in der Form PORTAL_ADRESSE/#z=<Wert> kommt in den Knopf; sonst ValueError ohne den Wert (Regel 18)."""
    if not isinstance(adresse, str) or not LINK_MUSTER.fullmatch(adresse):
        raise ValueError(LINK_FALSCH)
    return adresse


def link_adresse(wert: str) -> str:
    """Die Adresse eines Links aus seinem Wert (app/portal/pruefwerte.py::neuer_wert()), geprüft."""
    return link_pruefen(f"{PORTAL_ADRESSE}/#z={wert}")


def code_gruppen(code: str) -> str:
    """Der Code in zwei Gruppen zu drei Ziffern („481 207“) -- das Portal nimmt ihn mit und ohne Leerzeichen."""
    if not re.fullmatch(r"[0-9]{6}", code or ""):
        raise ValueError("Der Anmeldecode hat nicht die erwartete Form -- es wurde nichts versendet.")
    return f"{code[:3]} {code[3:]}"


def anrede(kunde: Customer) -> str:
    """Erste Zeile der Mail, wie die Begrüßung im Portal (app/portal/begruessung.py), mit Komma am Ende: „Guten Tag Herr Dr. Muster,“ (seit 1.11.23
    ohne Komma nach „Guten Tag“), ohne Namen „Guten Tag,“."""
    return begruessung(kunde.salutation, kunde.title, kunde.first_name, kunde.last_name, kunde.name) + ","


def webseite_host(webseite: str | None) -> str | None:
    """Der Host der Webseite aus den Firmendaten („www.beispiel.de“, auch mit https:// oder / am Ende eingetragen); nichts Gültiges -> None."""
    text = (webseite or "").strip()
    for vorne in ("https://", "http://"):
        if text.lower().startswith(vorne):
            text = text[len(vorne):]
    text = text.rstrip("/")
    return text if _HOST.fullmatch(text) else None


@dataclass(frozen=True)
class Firma:
    name: str
    marke: str            # erste Zeile der Wortmarke (erstes Wort des Namens)
    marke_rest: str       # zweite Zeile (der Rest), leer bei einem Wort
    anschrift: str        # „Name · Straße · PLZ Ort“ ohne leere Teile
    telefon: str | None
    webseite: str | None  # Host, nur wenn gültig
    impressum: str | None
    datenschutz: str | None
    pflichtangaben: str | None = None  # seit 1.11.12: „Sitz … · Registergericht Nummer · Geschäftsführer: …“ (§ 35a GmbHG), leer ohne jedes Feld


def firma(db: Session) -> Firma:
    """Die Angaben des Betriebs aus den Firmendaten der Einstellungen (P1-14) -- dieselben, die das Portal als Kontakt zeigt."""
    s = load_general_settings(db)
    name = (s.company_name or "").strip()
    marke, _, rest = name.partition(" ")
    anschrift = firmen_anschrift(s.company_name, s.street, s.postal_code, s.city)  # seit 1.11.17 aus app/firmenangaben.py
    host = webseite_host(s.website)
    return Firma(
        name=name, marke=marke, marke_rest=rest.strip(), anschrift=anschrift, telefon=(s.phone or "").strip() or None, webseite=host,
        impressum=f"https://{host}/impressum" if host else None, datenschutz=f"https://{host}/datenschutz" if host else None,
        pflichtangaben=pflichtangaben(s.city, s.register_court, s.register_number, s.managing_director),
    )



# --- Bausteine (Tabellen und Stile in den Tags) -----------------------------------------------------------------------------------------------

def _p(inhalt: str, stil: str = "") -> str:
    return f'<p style="margin:0 0 16px 0;{stil}">{inhalt}</p>'


_KNOPF_POLSTER = "14px 24px"


def _knopf(adresse: str, text: str) -> str:
    """Das übliche Muster (seit 1.11.28): Hintergrund und Ecken an der Zelle, das Polster am Link als inline-block -- in Browsern und Apps ist so die
    ganze Fläche klickbar, auf dem Handy vor allem. Outlook am Rechner (Word) kennt an einem Link weder padding noch inline-block (1.11.24); dort polstert
    `mso-padding-alt` die Zelle, das liest nur Outlook. Die Zelle selbst hat kein padding, sonst läge es in Browsern doppelt."""
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 16px 0;border-collapse:separate;"><tr>'
        f'<td align="center" style="background-color:{_GRUEN};border-radius:10px;mso-padding-alt:{_KNOPF_POLSTER};">'
        f'<a href="{_e(link_pruefen(adresse))}" style="display:inline-block;padding:{_KNOPF_POLSTER};font-family:{_SCHRIFT};font-size:15px;'
        f'font-weight:bold;line-height:20px;color:#FFFFFF;text-decoration:none;">{_e(text)}</a></td></tr></table>'
    )


def _kasten(inhalt: str) -> str:
    return (f'<div style="margin:0 0 16px 0;padding:12px 16px;border-radius:10px;background-color:{_GRAU};font-size:14px;line-height:1.5;">'
            f'{inhalt}</div>')


def _sicherheit(inhalt: str) -> str:
    return (f'<p style="margin:0 0 16px 0;padding:0 0 0 12px;border-left:3px solid {_GRUEN};font-size:13px;line-height:1.5;color:{_LEISE};">'
            f'{inhalt}</p>')


def _code_kasten(code: str) -> str:
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 16px 0;border-collapse:separate;"><tr>'
        f'<td style="padding:14px 22px;border-radius:12px;background-color:{_GRAU};border:1px solid {_RAND};font-family:{_MONO};font-size:34px;'
        f'line-height:40px;letter-spacing:6px;color:{_TITEL};">{_e(code_gruppen(code))}</td></tr></table>'
    )


def _anrufen(f: Firma) -> str:
    """„… rufen Sie uns bitte an: <Telefon>.“ -- ohne Telefon nur „… an.“ (der Satz bleibt)."""
    return f"Dann rufen Sie uns bitte an: {_e(f.telefon)}." if f.telefon else "Dann rufen Sie uns bitte an."


def _fusszeile(f: Firma) -> str:
    zeilen = [_e(f.anschrift)] if f.anschrift else []
    kontakt = " · ".join(t for t in (f"Telefon {_e(f.telefon)}" if f.telefon else "", _e(f.webseite) if f.webseite else "") if t)
    if kontakt:
        zeilen.append(kontakt)
    if f.impressum and f.datenschutz:
        stil = f"color:{_LINK};text-decoration:underline;"
        zeilen.append(f'<a href="{_e(f.impressum)}" style="{stil}">Impressum</a> · <a href="{_e(f.datenschutz)}" style="{stil}">Datenschutz</a>')
    fuss = "<br>".join(zeilen)
    if f.pflichtangaben:  # seit 1.11.12: die kleine Zeile nach § 35a GmbHG, zuletzt
        abstand = "margin:8px 0 0 0;" if fuss else "margin:0;"
        fuss += f'<div style="{abstand}font-size:11px;line-height:1.5;">{_e(f.pflichtangaben)}</div>'
    return fuss


def _rahmen(f: Firma, betreff: str, inhalt: str) -> str:
    marke = (f'<div style="font-family:{_SCHRIFT};font-weight:bold;font-size:15px;line-height:18px;letter-spacing:1px;color:{_MARKE};">'
             f'{_e(f.marke)}</div>')
    if f.marke_rest:
        marke += f'<div style="font-family:{_SCHRIFT};font-size:12px;line-height:16px;color:{_MARKE_2};">{_e(f.marke_rest)}</div>'
    fuss = _fusszeile(f)
    fuss_zeile = (f'<tr><td style="padding:16px 28px;background-color:{_GRAU};border-radius:0 0 12px 12px;font-family:{_SCHRIFT};font-size:12px;'
                  f'line-height:1.6;color:{_LEISE};">{fuss}</td></tr>') if fuss else ""
    return (
        '<!DOCTYPE html>\n<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{_e(betreff)}</title></head>'
        f'<body style="margin:0;padding:0;background-color:{_FLAECHE};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:{_FLAECHE};"><tr>'
        '<td align="center" style="padding:24px 12px;">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%;max-width:600px;background-color:#FFFFFF;border-radius:12px;border-collapse:separate;">'
        f'<tr><td style="padding:18px 28px;border-bottom:3px solid {_GRUEN};">{marke}</td></tr>'
        f'<tr><td style="padding:28px 28px 12px 28px;font-family:{_SCHRIFT};font-size:15px;line-height:1.6;color:{_TEXT};">{inhalt}'
        f'{_p("Mit freundlichen Grüßen<br>Ihr Team der " + _e(f.name))}</td></tr>'
        f'{fuss_zeile}'
        '</table></td></tr></table></body></html>'
    )


def _titel(text: str) -> str:
    return (f'<h1 style="margin:0 0 16px 0;font-family:{_SCHRIFT};font-size:24px;line-height:1.25;font-weight:bold;color:{_TITEL};">'
            f'{_e(text)}</h1>')


def link_html(db: Session, kunde: Customer, adresse: str, gueltig_bis: datetime) -> str:
    """Die Mail mit dem Link (Versandart portal_link, ab P1d). adresse = PORTAL_ADRESSE/#z=<Wert> (link_pruefen()); gueltig_bis in naivem UTC."""
    link_pruefen(adresse)
    f = firma(db)
    bis = to_berlin(gueltig_bis).strftime("%d.%m.%Y")
    inhalt = (
        _titel("Ihr persönlicher Zugang zum Kundenportal")
        + _p(_e(anrede(kunde)))
        + _p("wie besprochen haben wir für Sie einen Zugang zu unserem Kundenportal eingerichtet. Dort finden Sie künftig Ihre Unterlagen zu "
             "Anfragen und Aufträgen an einem Ort.")
        + _knopf(adresse, "Kundenportal öffnen")
        + _p("Beim ersten Öffnen auf einem Gerät senden wir Ihnen zur Sicherheit einen Code an diese E-Mail-Adresse. Danach bleiben Sie dort "
             f"{SITZUNG_TAGE} Tage angemeldet.")
        + _kasten(f"Der Link ist persönlich und gilt bis {_e(bis)}. Bitte leiten Sie diese E-Mail nicht weiter.")
        + _sicherheit("Wir fragen Sie nie nach einem Passwort oder nach Bankdaten. Unser Kundenportal finden Sie immer unter "
                      f"{_e(PORTAL_HOST)}. Haben Sie diese E-Mail nicht erwartet? {_anrufen(f)}")
    )
    return _rahmen(f, BETREFF["portal_link"], inhalt)


def code_html(db: Session, kunde: Customer, code: str) -> str:
    """Die Mail mit dem Anmeldecode (Versandart portal_code, Postbote)."""
    f = firma(db)
    nummer = f" {_e(f.telefon)}" if f.telefon else ""
    inhalt = (
        _titel("Ihr Anmeldecode")
        + _p(_e(anrede(kunde)))
        + _p("Ihr Code für das Kundenportal lautet:")
        + _code_kasten(code)
        + _p(f"Er gilt {CODE_MINUTEN} Minuten und nur in dem Browser, in dem Sie ihn angefordert haben.")
        + _p("Sie haben keinen Code angefordert? Dann hat wohl jemand anderes Ihren Link zum Kundenportal geöffnet. Ohne diesen Code kommt er nicht "
             f"hinein. Rufen Sie uns bitte trotzdem an{':' + nummer if nummer else ''} – wir sperren den Link und schicken Ihnen einen neuen.")
        + _sicherheit("Wir fragen Sie nie nach diesem Code, einem Passwort oder Bankdaten. Geben Sie den Code nur im Kundenportal ein, nie am Telefon.")
    )
    return _rahmen(f, BETREFF["portal_code"], inhalt)


def senden(db: Session, *, art: str, dokument_id: int, an: str, html_: str, dispatch_key: str,
           user_id: int | None = None, user_name: str | None = None) -> DispatchResult:
    """Die eine Stelle, an der eine Mail des Portals hinausgeht: dispatch_email() mit dem festen Betreff der Art, als HTML und ohne „Gesendete
    Elemente“. dokument_id: der Zugang (portal_link) bzw. der Auftrag an den Postboten (portal_code). Wirft wie dispatch_email() ValueError und
    DispatchConflict -- deren Text nennt nie den Text der Mail."""
    # je Art ein Aufruf mit fester Versandart (die Wächter test_v355 und test_v371 verlangen eine Konstante)
    if art == "portal_link":
        return dispatch_email(
            db, dispatch_key=dispatch_key, document_type="portal_link", document_id=dokument_id, document_number=None, to=an, cc=None,
            subject=BETREFF["portal_link"], body_text="", body_html=html_, user_id=user_id, user_name=user_name, gesendete_elemente=False,
        )
    if art == "portal_code":
        return dispatch_email(
            db, dispatch_key=dispatch_key, document_type="portal_code", document_id=dokument_id, document_number=None, to=an, cc=None,
            subject=BETREFF["portal_code"], body_text="", body_html=html_, user_id=user_id, user_name=user_name, gesendete_elemente=False,
        )
    raise ValueError(f"Unbekannte Versandart des Portals: {art}")
