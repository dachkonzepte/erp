"""Zuordnung für den DATEV-Export -- seit 1.9.169 (Lohn L1a, Punkt 4, Entscheidungen Tobias E3, E5, E7).

Was steht für eine Person an einem Tag in der Lohndatei, mit welchem Kennzeichen und welcher Lohnart? Je Schlüssel eine Zeile
(LohnartZuordnung):

    arbeit                    die gebuchten Stunden des Tags, alle Zeitarten zusammen (vorbelegt 1 / 1000)
    mehrarbeit_azubi          seit 1.9.224: nur Azubis, der Teil der Arbeit über der Sollzeit des Tags (vorbelegt AA / 1900, Antwort des
                              Lohnbüros; leer: alles bleibt unter „arbeit“) -- app/lohndatei.py
    feiertag                  gesetzlicher Feiertag mit Sollzeit, nur beim Export-Umfang „alles“ (vorbelegt F / 1012)
    kategorie:<Kategorie>     eine Abwesenheit dieser Kategorie mit der Sollzeit des Tags (vorbelegt Urlaub U / 8000, Krankheit K / 1650)
    schlechtwetter:winter     Ausfalltag 01.12.–31.03. (vorbelegt seit 1.9.214 WA / 8195 je Tag, Antwort des Lohnbüros; 1.9.169–1.9.213 8110
                              als Monatszeile: Soll × Ausfalltage, ohne Tag und Kennzeichen)
    schlechtwetter:sommer     Ausfalltag 01.04.–30.11. (leer -- seit 1.9.214 auch nach der Antwort des Lohnbüros)
    art:<Art>                 eine Art mit eigener Zuordnung geht ihrer Kategorie vor (vorbelegt Weiterbildung 1 / 1000 mit Sollzeit, wie
                              Fortbildung in Time 4; seit 1.9.214 Berufsschule FE ohne Lohnart); ohne eigene gilt die Kategorie -- seit 1.9.203 nie bei Schlechtwetter: dort gewinnt immer
                              die Jahreszeit (Festlegung 1.9.169 Nr. 3); eine Zeile für eine Art, die nur zu Schlechtwetter passt („art:schlechtwetter“),
                              lehnt speichern() ab, eine schon gespeicherte wird übergangen (scripts/pruefe_zeitregeln.py nennt sie)
    kalender:<Schlüssel>      seit 1.9.175: die Abwesenheit eines Tags im Arbeitszeitkalender (app/arbeitszeitkalender.py) mit der Sollzeit des
                              Tags (vorbelegt seit 1.9.214 Heiligabend FR / 1080 und Silvester UU ohne Lohnart, Antwort des Lohnbüros;
                              1.9.175–1.9.213 BF bzw. AF, Lohnart offen)

Seit 1.9.215 (L1a Stufe 6, Punkt 4) gilt für jede Zeile (wirkt() sagt, welcher Fall):
    Kennzeichen leer                     nicht exportiert -- die Liste in den Einstellungen nennt es, der Export (L1b) zeigt es unter
                                         „Nicht im Export“
    Kennzeichen gesetzt, Lohnart leer    exportiert, die Stunden ohne Lohnart (UU, FE)
    beides gesetzt                       exportiert mit Lohnart
Dazu bis L1b die Monatszeile (nur Schlechtwetter, Lohnart ohne Kennzeichen; keine Zeile nutzt sie seit 1.9.214). Bis 1.9.214 galt: zum
Kennzeichen gehört eine Lohnart, ohne Lohnart nicht exportiert (nur beim Kalendertag durfte das Kennzeichen allein stehen). Unbezahlt und
Freizeitausgleich bleiben leer (LB1). Seit 1.9.313 die Kategorie Sonderurlaub, leer bis das Steuerbüro die Lohnart nennt. Seit 1.9.317 sperren Tage
einer Kategorie ohne Kennzeichen (außer Unbezahlt und Freizeitausgleich) die Lohndatei (app/lohndatei.py::ohne_zuordnung(), über datev_fehlt()) -- in
der Auslieferung sind das Sonderurlaub und Fortbildung (deren Arten Weiterbildung und Berufsschule haben eine eigene). Berater- und Mandantennummer
stehen nicht hier.
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
    # seit 1.9.224 (Lohn L1b, Punkt 1): nur Azubis -- der Teil der Arbeit über der Sollzeit des Tags (app/lohndatei.py)
    ("mehrarbeit_azubi", "Mehrarbeit Azubis (Arbeit über der Sollzeit)", "Arbeit über der Sollzeit"),
    ("feiertag", "Feiertag (gesetzlich, nur Export „alles“)", "Sollzeit"),
    *[(f"kategorie:{k}", f"Kategorie {ABSENCE_CATEGORY_LABELS[k]}", "Sollzeit") for k in ABSENCE_CATEGORIES if k != "schlechtwetter"],
    # seit 1.9.216 (Nachtrag): die Stunden eines Ausfalltags sind Sollzeit minus gebuchte Arbeit (app/schlechtwetter.py::ausfall())
    ("schlechtwetter:winter", "Schlechtwetter Winter (01.12.–31.03.)", "Sollzeit − gebuchte Arbeit"),
    ("schlechtwetter:sommer", "Schlechtwetter Sommer (01.04.–30.11.)", "Sollzeit − gebuchte Arbeit"),
]
# E7 und Nachtrag 02.11.2026: vorbelegt; alles andere leer. Seit 1.9.214 (L1a Stufe 6, Punkt 3) mit den Werten des Lohnbüros -- eine bestehende
# Installation stellt die Migration a3f61c8d2b95 um, nur wo noch der bisherige Vorgabewert steht.
START = {
    "arbeit": ("1", "1000", False),
    "mehrarbeit_azubi": ("AA", "1900", False),  # seit 1.9.224, Antwort des Lohnbüros (Notiz 1.9.214)
    "feiertag": ("F", "1012", False),
    "kategorie:urlaub": ("U", "8000", False),
    "kategorie:krankheit": ("K", "1650", False),
    "schlechtwetter:winter": ("WA", "8195", False),  # seit 1.9.214 je Tag (1.9.169–1.9.213: 8110 als Monatszeile)
    "art:weiterbildung": ("1", "1000", False),
    "art:berufsschule": ("FE", None, False),  # seit 1.9.214: ohne Lohnart
    "kalender:heiligabend": ("FR", "1080", False),  # seit 1.9.214 (1.9.175–1.9.213: BF, Lohnart offen)
    "kalender:silvester": ("UU", None, False),  # seit 1.9.214 ohne Lohnart (1.9.176–1.9.213: AF, Lohnart offen)
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


NUR_JAHRESZEIT = ("Für Schlechtwetter gilt immer die Jahreszeit (Zeilen „Schlechtwetter Winter“ und „Schlechtwetter Sommer“) – "
                  "eine eigene Zuordnung je Art gibt es dort nicht.")


def nur_jahreszeit(schluessel: str | None) -> bool:
    """Seit 1.9.203 (L1a Stufe 4, Punkt 2): eine Zeile „art:<Art>“ für eine Art, die nur zur Kategorie Schlechtwetter passt -- sie kann nie
    wirken (dort gewinnt die Jahreszeit), speichern() lehnt einen Wert ab, zuordnung() übergeht sie."""
    return bool(schluessel) and schluessel.startswith("art:") and art_kategorien(schluessel[4:]) == ("schlechtwetter",)


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
    """Wird die Zeile exportiert? Seit 1.9.215: sobald ein Kennzeichen steht, mit oder ohne Lohnart -- dazu die Monatszeile mit Lohnart (bis
    L1b, Befund 1.9.217). Bis 1.9.214: nur mit Lohnart."""
    return z is not None and (bool(z.kennzeichen) or (bool(z.monatszeile) and bool(z.lohnart)))


def _wert(z: LohnartZuordnung | None) -> dict | None:
    if not _gesetzt(z):
        return None
    return {"kennzeichen": z.kennzeichen, "lohnart": z.lohnart, "monatszeile": bool(z.monatszeile), "schluessel": z.schluessel}


def zuordnung(db: Session, kategorie: str | None, art: str | None, tag: date, *, alle: dict | None = None) -> dict | None:
    """Kennzeichen, Lohnart und Monatszeile für eine Abwesenheit an diesem Tag -- die Art, wenn sie eine eigene hat (seit 1.9.215: ein
    Kennzeichen, bis 1.9.214 eine Lohnart), sonst die Kategorie; die Lohnart kann leer sein (exportiert ohne Lohnart);
    Schlechtwetter seit 1.9.203 immer nach der Jahreszeit (Winter oder Sommer), ohne Blick auf die Art. None: nicht exportiert."""
    alle = alle if alle is not None else _alle(db)
    if kategorie == "schlechtwetter":
        return _wert(alle.get(schlechtwetter_schluessel(tag)))
    eigene = alle.get(art_schluessel(art))
    if _gesetzt(eigene) and not nur_jahreszeit(eigene.schluessel):  # seit 1.9.203: „art:schlechtwetter“ wirkt nie, auch nicht im Altbestand
        return _wert(eigene)
    return _wert(alle.get(f"kategorie:{kategorie}"))


def fest(db: Session, schluessel: str, *, alle: dict | None = None) -> dict | None:
    """„arbeit“, „mehrarbeit_azubi“ (seit 1.9.224) oder „feiertag“ -- None: nicht exportiert."""
    return _wert((alle if alle is not None else _alle(db)).get(schluessel))


def kalender(db: Session, eintrag_schluessel: str, *, alle: dict | None = None) -> dict | None:
    """Seit 1.9.175: Kennzeichen und Lohnart der Abwesenheit eines Kalendertags -- exportiert seit 1.9.215 mit Kennzeichen, auch ohne Lohnart
    (bis 1.9.214 erst mit Lohnart). None: beides leer."""
    z = (alle if alle is not None else _alle(db)).get(kalender_schluessel(eintrag_schluessel))
    if z is None or not (z.kennzeichen or z.lohnart):
        return None
    return {"kennzeichen": z.kennzeichen, "lohnart": z.lohnart, "schluessel": z.schluessel, "exportiert": _gesetzt(z)}


def kurz(z: LohnartZuordnung | None) -> str:
    """Der gespeicherte Wert in Kurzform: „FR / 1080“, „UU“, „Monatszeile 8110“, „leer“."""
    if z is not None and z.monatszeile and z.lohnart:
        return f"Monatszeile {z.lohnart}"
    if z is None or not (z.kennzeichen or z.lohnart):
        return "leer"
    return " / ".join(w for w in (z.kennzeichen, z.lohnart) if w)


def wirkt(z: LohnartZuordnung | None) -> str:
    """Seit 1.9.215 (L1a Stufe 6, Punkt 4): welcher Fall für die Zeile gilt -- „nicht exportiert“ (ohne Kennzeichen), „UU – exportiert, Stunden
    ohne Lohnart“, „FR / 1080 – exportiert mit Lohnart“; dazu bis L1b die Monatszeile. Bis 1.9.214 „FR / 1080“, „BF / Lohnart offen – nicht
    exportiert“, „nicht exportiert“, „Monatszeile 8110“."""
    if not _gesetzt(z):
        return "nicht exportiert"
    if z.monatszeile:
        return f"Monatszeile {z.lohnart} – exportiert als eine Zeile je Monat"
    if not z.lohnart:
        return f"{z.kennzeichen} – exportiert, Stunden ohne Lohnart"
    return f"{z.kennzeichen} / {z.lohnart} – exportiert mit Lohnart"


def liste(db: Session) -> list[dict]:
    """Alle Zeilen für die Seite: feste, dann je Art der Auswahlliste „Abwesenheitsarten“ (auch inaktive und solche, die nur noch hier
    stehen). Je Zeile, was wirkt -- bei einer Art ohne eigene Zuordnung die ihrer Kategorie(n)."""
    alle = _alle(db)
    zeilen = []
    for schluessel, bezeichnung, stunden in FEST:
        z = alle.get(schluessel)
        zeilen.append({"schluessel": schluessel, "bezeichnung": bezeichnung, "gruppe": "fest", "stunden": stunden,
                       "kennzeichen": z.kennzeichen if z else None, "lohnart": z.lohnart if z else None, "monatszeile": bool(z and z.monatszeile),
                       "monatszeile_moeglich": schluessel.startswith("schlechtwetter:"), "wirkt": wirkt(z)})
    # seit 1.9.175: je Tag des Arbeitszeitkalenders eine Zeile (auch abgeschaltete), Stunden = die Sollzeit des Tags
    from .arbeitszeitkalender import datum_text, eintraege
    for e in eintraege(db):
        schluessel = kalender_schluessel(e.schluessel)
        z = alle.get(schluessel)
        stunden = f"{str(e.sollzeit).replace('.', ',')} h (Kalender)" if e.sollzeit is not None else "Sollzeit"
        zeilen.append({"schluessel": schluessel, "bezeichnung": f"{e.abwesenheit} ({datum_text(e)})" + ("" if e.aktiv else " (abgeschaltet)"),
                       "gruppe": "kalender", "stunden": stunden, "kennzeichen": z.kennzeichen if z else None,
                       "lohnart": z.lohnart if z else None, "monatszeile": False, "monatszeile_moeglich": False, "wirkt": wirkt(z)})
    gruppe = get_option_group(db, "absence_types")
    arten = [(o.value, o.label, o.active) for o in sorted(gruppe.options if gruppe is not None else [], key=lambda o: (o.sort_order, o.id))]
    bekannt = {art_schluessel(v) for v, _l, _a in arten}
    arten += [(s[4:], s[4:], False) for s in alle if s.startswith("art:") and s not in bekannt]
    for wert, label, aktiv in arten:
        z = alle.get(art_schluessel(wert))
        if nur_jahreszeit(art_schluessel(wert)):  # seit 1.9.203: hier wirkt nie die Art (bis dahin „wie die Kategorie – “ ohne Kategorie)
            text = "nach der Jahreszeit (Schlechtwetter Winter bzw. Sommer)"
            if z is not None and (z.kennzeichen or z.lohnart):
                text = f"gespeichert {kurz(z)} – wird übergangen, es gilt die Jahreszeit (Schlechtwetter Winter bzw. Sommer)"
        elif _gesetzt(z):
            text = wirkt(z)
        else:
            je = [f"{ABSENCE_CATEGORY_LABELS[k]}: {wirkt(alle.get('kategorie:' + k) if k != 'schlechtwetter' else None)}"
                  for k in art_kategorien(wert) if k != "schlechtwetter"]
            text = "wie die Kategorie – " + "; ".join(je) if len(je) <= 2 else "wie die Kategorie der Abwesenheit"
        zeilen.append({"schluessel": art_schluessel(wert), "bezeichnung": f"Art {label}" + ("" if aktiv else " (inaktiv)"), "gruppe": "art",
                       "stunden": "Sollzeit", "kennzeichen": z.kennzeichen if z else None, "lohnart": z.lohnart if z else None,
                       "monatszeile": bool(z and z.monatszeile), "monatszeile_moeglich": False, "wirkt": text})
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
    if nur_jahreszeit(schluessel) and (kennzeichen or lohnart or monatszeile):  # seit 1.9.203; leeren geht (dann kein Befund mehr)
        raise ValueError(NUR_JAHRESZEIT)
    if kennzeichen and not KENNZEICHEN_FORMAT.match(kennzeichen):
        raise ValueError("Das Kennzeichen hat ein oder zwei Zeichen (Ziffer oder Großbuchstabe), z. B. 1, U, K oder F.")
    if lohnart and not LOHNART_FORMAT.match(lohnart):
        raise ValueError("Die Lohnart hat 1 bis 4 Ziffern, z. B. 1000.")
    if monatszeile and not schluessel.startswith("schlechtwetter:"):
        raise ValueError("Eine Monatszeile gibt es nur für Schlechtwetter.")
    if monatszeile and kennzeichen:
        raise ValueError("Eine Monatszeile hat kein Kennzeichen.")
    # seit 1.9.215 (L1a Stufe 6, Punkt 4): ein Kennzeichen ohne Lohnart geht überall (exportiert ohne Lohnart) -- bis 1.9.214 nur am Kalendertag,
    # sonst „Zum Kennzeichen gehört eine Lohnart.“
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
