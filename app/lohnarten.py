"""Zuordnung für den DATEV-Export -- seit 1.9.169 (Lohn L1a, Punkt 4, Entscheidungen Tobias E3, E5, E7).

Was steht für eine Person an einem Tag in der Lohndatei, mit welchem Kennzeichen und welcher Lohnart? Je Schlüssel eine Zeile
(LohnartZuordnung):

    arbeit                    die gebuchten Stunden des Tags, alle Zeitarten zusammen (vorbelegt 1 / 1000)
    feiertag                  gesetzlicher Feiertag mit Sollzeit, nur beim Export-Umfang „alles“ (vorbelegt F / 1012)
    kategorie:<Kategorie>     eine Abwesenheit dieser Kategorie mit der Sollzeit des Tags (vorbelegt Urlaub U / 8000, Krankheit K / 1650)
    schlechtwetter:winter     Ausfalltag 01.12.–31.03. (vorbelegt 8110 als Monatszeile: Soll × Ausfalltage, ohne Tag und Kennzeichen)
    schlechtwetter:sommer     Ausfalltag 01.04.–30.11. (leer, bis der Juni-Export da ist)
    art:<Art>                 eine Art mit eigener Zuordnung geht ihrer Kategorie vor (vorbelegt Weiterbildung 1 / 1000 mit Sollzeit, wie
                              Fortbildung in Time 4); ohne eigene gilt die Kategorie
    kalender:<Schlüssel>      seit 1.9.175: die Abwesenheit eines Tags im Arbeitszeitkalender (app/arbeitszeitkalender.py) mit der Sollzeit des
                              Tags (vorbelegt Heiligabend BF, Lohnart offen -- die Lohnart nennt das Lohnbüro); hier darf das Kennzeichen ohne
                              Lohnart stehen, exportiert wird die Zeile erst mit Lohnart

Leer heißt: nicht exportiert -- die Liste in den Einstellungen nennt es, der Export (L1b) zeigt es unter „Nicht im Export“. Berufsschule,
unbezahlt und Freizeitausgleich bleiben leer, bis das Lohnbüro antwortet (LB1). Berater- und Mandantennummer stehen nicht hier.
"""

from __future__ import annotations

import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .absence_requests import ABSENCE_CATEGORIES, ABSENCE_CATEGORY_LABELS, art_kategorien
from .models import LohnartZuordnung
from .option_settings import get_option_group

# (Schlüssel, Bezeichnung, Stunden) -- die festen Zeilen in der Reihenfolge der Seite
FEST = [
    ("arbeit", "Arbeit (alle Zeitarten zusammen)", "gebuchte Stunden"),
    ("feiertag", "Feiertag (gesetzlich, nur Export „alles“)", "Sollzeit"),
    *[(f"kategorie:{k}", f"Kategorie {ABSENCE_CATEGORY_LABELS[k]}", "Sollzeit") for k in ABSENCE_CATEGORIES if k != "schlechtwetter"],
    ("schlechtwetter:winter", "Schlechtwetter Winter (01.12.–31.03.)", "Sollzeit"),
    ("schlechtwetter:sommer", "Schlechtwetter Sommer (01.04.–30.11.)", "Sollzeit"),
]
# E7 und Nachtrag 02.11.2026: vorbelegt; alles andere leer
START = {
    "arbeit": ("1", "1000", False),
    "feiertag": ("F", "1012", False),
    "kategorie:urlaub": ("U", "8000", False),
    "kategorie:krankheit": ("K", "1650", False),
    "schlechtwetter:winter": (None, "8110", True),
    "art:weiterbildung": ("1", "1000", False),
    "kalender:heiligabend": ("BF", None, False),  # seit 1.9.175 (L1a-Nachtrag, Punkt 2): Lohnart beim Lohnbüro
}
KENNZEICHEN_FORMAT = re.compile(r"^[0-9A-Z]{1,2}$")
LOHNART_FORMAT = re.compile(r"^[0-9]{1,4}$")


def art_schluessel(art: str | None) -> str:
    return "art:" + (art or "").strip().casefold()


def kalender_schluessel(eintrag_schluessel: str) -> str:
    return "kalender:" + eintrag_schluessel


def schlechtwetter_schluessel(tag: date) -> str:
    """Winter vom 01.12. bis 31.03. (E5), sonst Sommer."""
    return "schlechtwetter:winter" if tag.month in (12, 1, 2, 3) else "schlechtwetter:sommer"


def ensure_default_lohnart_zuordnungen(db: Session) -> None:
    """Anlegeschritt von app.grunddaten.anlegen(): legt fehlende feste Zeilen an, vorbelegt nach START, sonst leer -- rührt vorhandene nie an
    (ein von Hand geleerter Eintrag bleibt leer). flush, kein commit; je Zeile ein SAVEPOINT (UNIQUE auf schluessel)."""
    vorhanden = set(db.scalars(select(LohnartZuordnung.schluessel)).all())
    for schluessel in [s for s, _b, _h in FEST] + [s for s in START if s.startswith(("art:", "kalender:"))]:
        if schluessel in vorhanden:
            continue
        kennzeichen, lohnart, monatszeile = START.get(schluessel, (None, None, False))
        try:
            with db.begin_nested():
                db.add(LohnartZuordnung(schluessel=schluessel, kennzeichen=kennzeichen, lohnart=lohnart, monatszeile=monatszeile))
                db.flush()
        except IntegrityError:
            continue


def _alle(db: Session) -> dict[str, LohnartZuordnung]:
    return {z.schluessel: z for z in db.scalars(select(LohnartZuordnung)).all()}


def _gesetzt(z: LohnartZuordnung | None) -> bool:
    return z is not None and bool(z.lohnart)


def _wert(z: LohnartZuordnung | None) -> dict | None:
    return {"kennzeichen": z.kennzeichen, "lohnart": z.lohnart, "monatszeile": bool(z.monatszeile), "schluessel": z.schluessel} if _gesetzt(z) else None


def zuordnung(db: Session, kategorie: str | None, art: str | None, tag: date, *, alle: dict | None = None) -> dict | None:
    """Kennzeichen, Lohnart und Monatszeile für eine Abwesenheit an diesem Tag -- die Art, wenn sie eine eigene hat, sonst die Kategorie
    (Schlechtwetter je nach Datum Winter oder Sommer). None: nicht exportiert."""
    alle = alle if alle is not None else _alle(db)
    eigene = alle.get(art_schluessel(art))
    if _gesetzt(eigene):
        return _wert(eigene)
    if kategorie == "schlechtwetter":
        return _wert(alle.get(schlechtwetter_schluessel(tag)))
    return _wert(alle.get(f"kategorie:{kategorie}"))


def fest(db: Session, schluessel: str) -> dict | None:
    """„arbeit“ oder „feiertag“ -- None: nicht exportiert."""
    return _wert(_alle(db).get(schluessel))


def kalender(db: Session, eintrag_schluessel: str) -> dict | None:
    """Seit 1.9.175: Kennzeichen und Lohnart der Abwesenheit eines Kalendertags -- auch ohne Lohnart („BF“, Lohnart offen); exportiert wird
    sie erst mit Lohnart (exportiert). None: beides leer."""
    z = _alle(db).get(kalender_schluessel(eintrag_schluessel))
    if z is None or not (z.kennzeichen or z.lohnart):
        return None
    return {"kennzeichen": z.kennzeichen, "lohnart": z.lohnart, "schluessel": z.schluessel, "exportiert": _gesetzt(z)}


def _text(z: LohnartZuordnung | None) -> str:
    if z is not None and z.kennzeichen and not z.lohnart:
        return f"{z.kennzeichen} / Lohnart offen – nicht exportiert"
    if not _gesetzt(z):
        return "nicht exportiert"
    if z.monatszeile:
        return f"Monatszeile {z.lohnart}"
    return f"{z.kennzeichen} / {z.lohnart}"


def liste(db: Session) -> list[dict]:
    """Alle Zeilen für die Seite: feste, dann je Art der Auswahlliste „Abwesenheitsarten“ (auch inaktive und solche, die nur noch hier
    stehen). Je Zeile, was wirkt -- bei einer Art ohne eigene Zuordnung die ihrer Kategorie(n)."""
    alle = _alle(db)
    zeilen = []
    for schluessel, bezeichnung, stunden in FEST:
        z = alle.get(schluessel)
        zeilen.append({"schluessel": schluessel, "bezeichnung": bezeichnung, "gruppe": "fest", "stunden": stunden,
                       "kennzeichen": z.kennzeichen if z else None, "lohnart": z.lohnart if z else None, "monatszeile": bool(z and z.monatszeile),
                       "monatszeile_moeglich": schluessel.startswith("schlechtwetter:"), "wirkt": _text(z)})
    # seit 1.9.175: je Tag des Arbeitszeitkalenders eine Zeile (auch abgeschaltete), Stunden = die Sollzeit des Tags
    from .arbeitszeitkalender import datum_text, eintraege
    for e in eintraege(db):
        schluessel = kalender_schluessel(e.schluessel)
        z = alle.get(schluessel)
        stunden = f"{str(e.sollzeit).replace('.', ',')} h (Kalender)" if e.sollzeit is not None else "Sollzeit"
        zeilen.append({"schluessel": schluessel, "bezeichnung": f"{e.abwesenheit} ({datum_text(e)})" + ("" if e.aktiv else " (abgeschaltet)"),
                       "gruppe": "kalender", "stunden": stunden, "kennzeichen": z.kennzeichen if z else None,
                       "lohnart": z.lohnart if z else None, "monatszeile": False, "monatszeile_moeglich": False, "wirkt": _text(z)})
    gruppe = get_option_group(db, "absence_types")
    arten = [(o.value, o.label, o.active) for o in sorted(gruppe.options if gruppe is not None else [], key=lambda o: (o.sort_order, o.id))]
    bekannt = {art_schluessel(v) for v, _l, _a in arten}
    arten += [(s[4:], s[4:], False) for s in alle if s.startswith("art:") and s not in bekannt]
    for wert, label, aktiv in arten:
        z = alle.get(art_schluessel(wert))
        if _gesetzt(z):
            wirkt = _text(z)
        else:
            je = [f"{ABSENCE_CATEGORY_LABELS[k]}: {_text(alle.get('kategorie:' + k) if k != 'schlechtwetter' else None)}"
                  for k in art_kategorien(wert) if k != "schlechtwetter"]
            wirkt = "wie die Kategorie – " + "; ".join(je) if len(je) <= 2 else "wie die Kategorie der Abwesenheit"
        zeilen.append({"schluessel": art_schluessel(wert), "bezeichnung": f"Art {label}" + ("" if aktiv else " (inaktiv)"), "gruppe": "art",
                       "stunden": "Sollzeit", "kennzeichen": z.kennzeichen if z else None, "lohnart": z.lohnart if z else None,
                       "monatszeile": bool(z and z.monatszeile), "monatszeile_moeglich": False, "wirkt": wirkt})
    return zeilen


def speichern(db: Session, schluessel: str, kennzeichen: str | None, lohnart: str | None, monatszeile: bool) -> LohnartZuordnung:
    """Eine Zeile setzen oder leeren (beides leer = nicht exportiert; die Zeile bleibt). Feste Schlüssel und „art:<Art>“; committet."""
    from .arbeitszeitkalender import eintraege

    schluessel = (schluessel or "").strip()
    feste = {s for s, _b, _h in FEST}
    kalender_tage = {kalender_schluessel(e.schluessel) for e in eintraege(db)}
    if schluessel not in feste and schluessel not in kalender_tage and not (schluessel.startswith("art:") and len(schluessel) > 4):
        raise ValueError("Unbekannter Eintrag der Zuordnung.")
    kennzeichen = (kennzeichen or "").strip().upper() or None
    lohnart = (lohnart or "").strip() or None
    if kennzeichen and not KENNZEICHEN_FORMAT.match(kennzeichen):
        raise ValueError("Das Kennzeichen hat ein oder zwei Zeichen (Ziffer oder Großbuchstabe), z. B. 1, U, K oder F.")
    if lohnart and not LOHNART_FORMAT.match(lohnart):
        raise ValueError("Die Lohnart hat 1 bis 4 Ziffern, z. B. 1000.")
    if monatszeile and not schluessel.startswith("schlechtwetter:"):
        raise ValueError("Eine Monatszeile gibt es nur für Schlechtwetter.")
    if monatszeile and kennzeichen:
        raise ValueError("Eine Monatszeile hat kein Kennzeichen.")
    if kennzeichen and not lohnart and schluessel not in kalender_tage:  # seit 1.9.175 beim Kalendertag: Lohnart offen (Lohnbüro)
        raise ValueError("Zum Kennzeichen gehört eine Lohnart.")
    if lohnart and not kennzeichen and not monatszeile:
        raise ValueError("Zur Lohnart gehört ein Kennzeichen (oder bei Schlechtwetter die Monatszeile).")
    z = db.scalar(select(LohnartZuordnung).where(LohnartZuordnung.schluessel == schluessel))
    if z is None:
        z = LohnartZuordnung(schluessel=schluessel)
        db.add(z)
    z.kennzeichen, z.lohnart, z.monatszeile = kennzeichen, lohnart, bool(monatszeile and lohnart)
    db.commit()
    db.refresh(z)
    return z
