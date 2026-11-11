"""Urlaubsanspruch je Person und Jahr, Startwerte der Konten und ihre Vorgaben -- seit 1.9.310 (Lohn L2a, Punkt 3; Antworten 11 und 12 des Befunds L2).

Nur die Daten und ihre Pflege; gerechnet wird mit ihnen erst im Urlaubskonto (L2b) und im Arbeitszeitkonto (L2c).

    Vorgaben    in den Zeitregeln (TimeTrackingSettings): Urlaubsanspruch je Jahr in Tagen (halbe erlaubt) -- gilt für jede Person ohne eigenen Wert im
                Jahr; Übertrag ins Folgejahr („von_hand“ | „automatisch“) und sein Verfall („TT.MM.“ im Folgejahr, leer = kein Verfall). Übertrag und Verfall
                wirken erst mit dem Urlaubskonto; bis Frage 2 des Befunds beantwortet ist, sind sie nur vorgemerkt.
    Anspruch    je Person und Jahr (Urlaubsanspruch): Urlaubstage (leer = die Vorgabe), Übertrag aus dem Vorjahr (leer = nicht von Hand), Verfallsdatum des
                Übertrags (leer = die Vorgabe), Notiz. So passen die offenen Antworten zu Frage 1 (Anspruch, Teilzeit, anteilig im Eintrittsjahr) und
                Frage 2 (Übertrag, Verfall) ohne neue Migration: ein Wert je Person und Jahr von Hand, eine allgemeine Regel später im Code.
    Startwert   je Person einer (LohnStartwert): Stichtag (31.12.2026, Stand nach dem Tag), Resturlaub in Tagen (halbe erlaubt, auch negativ), Saldo des
                Arbeitszeitkontos in Stunden (zwei Stellen, auch negativ), Herkunft (Steuerbüro, Time 4, Sonstiges) mit Bemerkung, geprüft am / durch.
                Ändert sich ein Wert ohne neue Prüfung, fällt die Prüfung weg (wie beim Basiszinssatz). Von Hand im Formular, kein Einleseskript.
    Rechte      lesen: Admin und Büro – Finanzen alle, alle anderen nur die eigenen (app/permissions.py::darf_konten_aller()); ändern:
                darf_lohnregeln() (Admin, Büro – Finanzen); den Startwert nach dem Abschluss des Monats nach dem Stichtag (Januar 2027) nur der Admin
                (startwert_gesperrt()). Der Router prüft die Rollen; hier sagt der Aufrufer nur, ob er Admin ist.
Ein Lesepfad legt nichts an (Regel 23): ohne Zeile gilt die Vorgabe; eine Zeile entsteht erst beim Speichern.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from .berlin_time import berlin_today
from .models import Employee, LohnStartwert, TimeTrackingSettings, Urlaubsanspruch
from .rounding import round_half_up

STICHTAG = date(2026, 12, 31)  # Antwort 12: Stand nach dem Tag, die Konten beginnen am 01.01.2027
UEBERTRAG = ("von_hand", "automatisch")
HERKUNFT = ("steuerbuero", "time4", "sonstiges")
HERKUNFT_TEXT = {"steuerbuero": "Steuerbüro", "time4": "Time 4", "sonstiges": "Sonstiges"}
ZEHNTEL, HUNDERTSTEL = Decimal("0.1"), Decimal("0.01")
TAGE_MAX, STUNDEN_MAX = Decimal("99.5"), Decimal("9999.99")


class StartwertGesperrt(ValueError):
    """Der Startwert ist nach dem Abschluss des Monats nach dem Stichtag nur für den Admin änderbar (403)."""


def _einstellungen(db: Session) -> TimeTrackingSettings:
    row = db.get(TimeTrackingSettings, 1)
    if row is None:
        from .grunddaten import GrunddatenFehlen
        raise GrunddatenFehlen("Die Einstellungen der Zeiterfassung fehlen.")
    return row


def _zahl(wert) -> Decimal:
    try:
        return Decimal(str(wert))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Bitte eine Zahl angeben.") from exc


def _tage_text(wert: Decimal) -> str:
    return f"{wert:.1f}".replace(".", ",").replace(",0", "")


def halbe_tage(wert, name: str, unten: Decimal, oben: Decimal = TAGE_MAX) -> Decimal | None:
    """Tage in halben Schritten zwischen unten und oben, sonst ValueError mit dem Namen des Felds; leer bleibt leer."""
    if wert is None or wert == "":
        return None
    d = _zahl(wert)
    if d < unten or d > oben or d * 2 != (d * 2).to_integral_value():
        raise ValueError(f"{name}: in halben Tagen zwischen {_tage_text(unten)} und {_tage_text(oben)}.")
    return round_half_up(d, ZEHNTEL)


def stunden(wert, name: str) -> Decimal | None:
    if wert is None or wert == "":
        return None
    d = _zahl(wert)
    if abs(d) > STUNDEN_MAX or d != round_half_up(d, HUNDERTSTEL):
        raise ValueError(f"{name}: höchstens zwei Nachkommastellen, zwischen -9.999,99 und 9.999,99.")
    return round_half_up(d, HUNDERTSTEL)


def verfall_text(wert: str | None) -> str | None:
    """„TT.MM.“ eines Tags im Jahr (der 29.02. nicht -- er fehlt in drei von vier Jahren); leer = kein Verfall."""
    wert = (wert or "").strip()
    if not wert:
        return None
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.?", wert)
    try:
        if m is None:
            raise ValueError
        tag = date(2027, int(m.group(2)), int(m.group(1)))  # 2027 ist kein Schaltjahr: so ist auch der 29.02. ungültig
    except ValueError as exc:
        raise ValueError("Verfall des Übertrags: ein Tag im Jahr als „TT.MM.“, z. B. 31.03. (nicht der 29.02.).") from exc
    return f"{tag:%d.%m.}"


# --- Vorgaben -------------------------------------------------------------------------------------------------------------------------------

def vorgaben(db: Session) -> dict:
    row = _einstellungen(db)
    return {"urlaub_vorgabe_tage": row.urlaub_vorgabe_tage, "urlaub_uebertrag": row.urlaub_uebertrag, "urlaub_verfall": row.urlaub_verfall}


def vorgaben_setzen(db: Session, werte: dict) -> dict:
    """Teil-Update (Regel 22): erst alles prüfen, dann schreiben; committet."""
    neu = {}
    if "urlaub_vorgabe_tage" in werte:
        neu["urlaub_vorgabe_tage"] = halbe_tage(werte["urlaub_vorgabe_tage"], "Urlaubsanspruch je Jahr", Decimal("0"))
        if neu["urlaub_vorgabe_tage"] is None:
            raise ValueError("Urlaubsanspruch je Jahr: bitte eine Zahl angeben.")
    if "urlaub_uebertrag" in werte:
        if werte["urlaub_uebertrag"] not in UEBERTRAG:
            raise ValueError("Übertrag ins Folgejahr: „von Hand“ oder „automatisch“.")
        neu["urlaub_uebertrag"] = werte["urlaub_uebertrag"]
    if "urlaub_verfall" in werte:
        neu["urlaub_verfall"] = verfall_text(werte["urlaub_verfall"])
    row = _einstellungen(db)
    for feld, wert in neu.items():
        setattr(row, feld, wert)
    db.commit()
    return vorgaben(db)


# --- lesen ----------------------------------------------------------------------------------------------------------------------------------

def standardjahr() -> int:
    """Das Jahr, dessen Anspruch die Seite zuerst zeigt: das laufende, frühestens das erste Jahr der Konten (2027)."""
    return max(berlin_today().year, STICHTAG.year + 1)


def startwert_gesperrt(db: Session) -> bool:
    """Seit dem Abschluss des Monats nach dem Stichtag (Januar 2027) ändert den Startwert nur der Admin (Antwort 12)."""
    bis = _einstellungen(db).locked_until
    grenze = (STICHTAG + timedelta(days=1) + timedelta(days=31)).replace(day=1) - timedelta(days=1)  # Ende des Monats nach dem Stichtag
    return bis is not None and bis >= grenze


def _anspruch_dict(row: Urlaubsanspruch, vorgabe: Decimal) -> dict:
    return {"jahr": row.jahr, "urlaubstage": row.urlaubstage, "urlaubstage_wirksam": row.urlaubstage if row.urlaubstage is not None else vorgabe,
            "vorgabe": row.urlaubstage is None,
            "uebertrag": row.uebertrag, "verfall_am": row.verfall_am, "notiz": row.notiz}


def _startwert_dict(row: LohnStartwert | None) -> dict | None:
    if row is None:
        return None
    return {"stichtag": row.stichtag, "resturlaub_tage": row.resturlaub_tage, "saldo_stunden": row.saldo_stunden, "herkunft": row.herkunft,
            "herkunft_text": HERKUNFT_TEXT.get(row.herkunft, row.herkunft), "herkunft_notiz": row.herkunft_notiz, "geprueft_am": row.geprueft_am,
            "geprueft_von": row.geprueft_von}


def konten(db: Session, employee_ids=None) -> list[dict]:
    """Je Person (employee_ids: nur diese; sonst alle, aktive zuerst) ihre Ansprüche aller Jahre und ihr Startwert -- drei Abfragen."""
    vorgabe = _einstellungen(db).urlaub_vorgabe_tage
    abfrage = select(Employee).order_by(Employee.active.desc(), Employee.last_name, Employee.first_name)
    if employee_ids is not None:
        abfrage = abfrage.where(Employee.id.in_(list(employee_ids) or [0]))
    personen = list(db.scalars(abfrage))
    ids = [e.id for e in personen] or [0]
    ansprueche: dict[int, list] = {}
    for a in db.scalars(select(Urlaubsanspruch).where(Urlaubsanspruch.employee_id.in_(ids)).order_by(Urlaubsanspruch.jahr)):
        ansprueche.setdefault(a.employee_id, []).append(_anspruch_dict(a, vorgabe))
    startwerte = {s.employee_id: s for s in db.scalars(select(LohnStartwert).where(LohnStartwert.employee_id.in_(ids)))}
    return [{"employee_id": e.id, "employee_name": f"{e.first_name} {e.last_name}".strip(), "active": bool(e.active),
             "ansprueche": ansprueche.get(e.id, []), "startwert": _startwert_dict(startwerte.get(e.id))} for e in personen]


# --- schreiben ------------------------------------------------------------------------------------------------------------------------------

def _person(db: Session, employee_id: int) -> Employee:
    emp = db.get(Employee, employee_id)
    if emp is None:
        raise LookupError("Mitarbeiter wurde nicht gefunden.")
    return emp


def anspruch_setzen(db: Session, employee_id: int, jahr: int, werte: dict) -> dict:
    """Teil-Update des Anspruchs einer Person in einem Jahr (Regel 22); legt die Zeile beim ersten Speichern an. Erst prüfen, dann schreiben;
    committet. Antwort: der Eintrag der Person wie in konten()."""
    _person(db, employee_id)
    if not 2026 <= jahr <= 2100:
        raise ValueError("Jahr: zwischen 2026 und 2100.")
    neu = {}
    if "urlaubstage" in werte:
        neu["urlaubstage"] = halbe_tage(werte["urlaubstage"], "Urlaubstage", Decimal("0"))
    if "uebertrag" in werte:
        neu["uebertrag"] = halbe_tage(werte["uebertrag"], "Übertrag", -TAGE_MAX)
    if "verfall_am" in werte:
        neu["verfall_am"] = werte["verfall_am"]
        if neu["verfall_am"] is not None and neu["verfall_am"].year != jahr:
            raise ValueError(f"Der Übertrag verfällt im Jahr des Anspruchs ({jahr}).")
    if "notiz" in werte:
        neu["notiz"] = (werte["notiz"] or "").strip() or None
    row = db.scalar(select(Urlaubsanspruch).where(Urlaubsanspruch.employee_id == employee_id, Urlaubsanspruch.jahr == jahr))
    if row is None:
        row = Urlaubsanspruch(employee_id=employee_id, jahr=jahr)
        db.add(row)
    for feld, wert in neu.items():
        setattr(row, feld, wert)
    db.commit()
    return konten(db, [employee_id])[0]


WERTE_DES_STARTWERTS = ("stichtag", "resturlaub_tage", "saldo_stunden", "herkunft", "herkunft_notiz")


def startwert_setzen(db: Session, employee_id: int, werte: dict, *, admin: bool, geprueft_von: str | None) -> dict:
    """Teil-Update des Startwerts einer Person (Regel 22); legt die Zeile beim ersten Speichern an (Stichtag 31.12.2026, Herkunft Steuerbüro).
    geprueft (bool, im Wert): True = geprüft heute durch geprueft_von, False = Prüfung weg. Ändert sich ein Wert ohne geprueft=True, fällt die
    Prüfung weg. Nach dem Abschluss des Monats nach dem Stichtag nur mit admin (StartwertGesperrt). Committet."""
    _person(db, employee_id)
    if not admin and startwert_gesperrt(db):
        bis = _einstellungen(db).locked_until
        raise StartwertGesperrt(f"Die Zeiterfassung ist bis {bis:%d.%m.%Y} abgeschlossen. Den Startwert ändert jetzt nur ein Administrator.")
    neu = {}
    if "stichtag" in werte:
        if werte["stichtag"] is None:
            raise ValueError("Stichtag: bitte ein Datum angeben.")
        neu["stichtag"] = werte["stichtag"]
    if "resturlaub_tage" in werte:
        neu["resturlaub_tage"] = halbe_tage(werte["resturlaub_tage"], "Resturlaub", -TAGE_MAX)
    if "saldo_stunden" in werte:
        neu["saldo_stunden"] = stunden(werte["saldo_stunden"], "Saldo Arbeitszeitkonto")
    if "herkunft" in werte:
        if werte["herkunft"] not in HERKUNFT:
            raise ValueError("Herkunft: Steuerbüro, Time 4 oder Sonstiges.")
        neu["herkunft"] = werte["herkunft"]
    if "herkunft_notiz" in werte:
        neu["herkunft_notiz"] = (werte["herkunft_notiz"] or "").strip() or None
    row = db.scalar(select(LohnStartwert).where(LohnStartwert.employee_id == employee_id))
    if row is None:
        row = LohnStartwert(employee_id=employee_id, stichtag=STICHTAG, herkunft="steuerbuero")
        db.add(row)
    geaendert = any(getattr(row, f) != w for f, w in neu.items())
    for feld, wert in neu.items():
        setattr(row, feld, wert)
    if werte.get("geprueft") is True:
        row.geprueft_am, row.geprueft_von = berlin_today(), geprueft_von
    elif werte.get("geprueft") is False or geaendert:
        row.geprueft_am, row.geprueft_von = None, None
    db.commit()
    return konten(db, [employee_id])[0]
