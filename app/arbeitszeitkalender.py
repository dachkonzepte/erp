"""Arbeitszeitkalender -- seit 1.9.175 (L1a-Nachtrag, Punkt 2, Vorgabe Tobias 03.11.2026).

Tage, die jedes Jahr am selben Datum anders laufen als der Tarif (ArbeitszeitKalendertag), gepflegt unter Einstellungen → „Zeitregeln und
DATEV“, nicht im Code. Vorbelegt beim Start (app.grunddaten.anlegen()):

    Heiligabend  24.12.  Sollzeit 7,00 h statt Modellwert, für alle gleich (auch Azubis und Teilzeit mit eigener Sollzeit); von selbst die
                         Abwesenheit „Heiligabend – bezahlte Freistellung“ mit 7,00 h; kein Urlaubstag -- ein Urlaub über den Tag zählt ihn mit
                         0 Arbeitstagen; gebuchte Arbeit kommt dazu und mindert die 7,00 h nicht; Zuordnung BF, Lohnart offen (Lohnbüro)

Ein Kalendertag gilt für eine Person an einem Tag (gilt()), wenn er aktiv ist, Monat und Tag passen, der Tag ein Montag bis Freitag ist
(nur_mo_fr) und die Person gewerblich ist (nur_gewerblich); vor dem Eintritt und nach dem Austritt ist die Sollzeit 0, dann gibt es auch keine
Abwesenheit. Die Abwesenheit wird nicht gespeichert, abwesenheiten() leitet sie je Tag ab: ändert sich der Kalender, die Funktion oder der
Eintritt, stimmt sie sofort, und es gibt nichts nachzutragen oder zu löschen. Rechnet nur hier und in app/sollzeit.py (Sollzeit des Tags,
Tage einer Abwesenheit); rollenlos, die Rechte prüft der Router.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import ArbeitszeitKalendertag, Employee
from .rounding import round_hours

# Was ein Urlaub über den Kalendertag zählt
IM_URLAUB = {
    "kein_urlaubstag": "kein Urlaubstag – ein Urlaub über den Tag zählt ihn mit 0",
}
MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember")
# Vorbelegung (Vorgabe Tobias, L1a-Nachtrag); ein Eintrag fehlt nur, wenn sein Schlüssel fehlt -- ein geänderter oder abgeschalteter bleibt
VORGABEN = [
    {"schluessel": "heiligabend", "name": "Heiligabend", "monat": 12, "tag": 24, "sollzeit": Decimal("7.00"),
     "abwesenheit": "Heiligabend – bezahlte Freistellung", "bezahlt": True, "im_urlaub": "kein_urlaubstag"},
]


class KalendertagUngueltig(ValueError):
    """Eingabe abgelehnt (422)."""


def ensure_default_kalendertage(db: Session) -> None:
    """Anlegeschritt von app.grunddaten.anlegen(): legt die Vorgaben an, deren Schlüssel fehlt -- rührt vorhandene nie an. flush, kein commit;
    je Eintrag ein SAVEPOINT (UNIQUE auf Schlüssel und Datum: gibt es den Tag schon unter anderem Namen, bleibt es bei dem)."""
    vorhanden = set(db.scalars(select(ArbeitszeitKalendertag.schluessel)).all())
    for v in VORGABEN:
        if v["schluessel"] in vorhanden:
            continue
        try:
            with db.begin_nested():
                db.add(ArbeitszeitKalendertag(**v, nur_gewerblich=True, nur_mo_fr=True, aktiv=True))
                db.flush()
        except IntegrityError:
            continue


def eintraege(db: Session) -> list[ArbeitszeitKalendertag]:
    return list(db.scalars(select(ArbeitszeitKalendertag).order_by(ArbeitszeitKalendertag.monat, ArbeitszeitKalendertag.tag)).all())


def aktive(db: Session) -> list[ArbeitszeitKalendertag]:
    return [e for e in eintraege(db) if e.aktiv]


def gilt(eintrag: ArbeitszeitKalendertag, tag: date, gruppe: str | None) -> bool:
    """Gilt der Kalendertag für eine Person dieser Gruppe an diesem Tag? (Eintritt und Austritt prüft die Sollzeit.)"""
    return (bool(eintrag.aktiv) and (eintrag.monat, eintrag.tag) == (tag.month, tag.day)
            and (not eintrag.nur_mo_fr or tag.weekday() < 5) and (not eintrag.nur_gewerblich or gruppe == "gewerblich"))


def fuer_tag(liste: list[ArbeitszeitKalendertag], tag: date, gruppe: str | None) -> ArbeitszeitKalendertag | None:
    for e in liste:
        if gilt(e, tag, gruppe):
            return e
    return None


def gruppe_von(db: Session, employee_id: int) -> str | None:
    emp = db.get(Employee, employee_id)
    return emp.employee_group if emp is not None else None


def kalendertag(db: Session, employee_id: int, tag: date) -> ArbeitszeitKalendertag | None:
    """Der Kalendertag, der für die Person an diesem Tag gilt -- None: keiner."""
    return fuer_tag(aktive(db), tag, gruppe_von(db, employee_id))


def kalendertage_im_zeitraum(db: Session, employee_id: int, start: date, ende: date) -> list[tuple[date, ArbeitszeitKalendertag]]:
    liste, gruppe = aktive(db), gruppe_von(db, employee_id)
    ergebnis, tag = [], start
    while tag <= ende:
        e = fuer_tag(liste, tag, gruppe)
        if e is not None:
            ergebnis.append((tag, e))
        tag += timedelta(days=1)
    return ergebnis


def abwesenheiten(db: Session, employee_id: int, start: date, ende: date) -> list[dict]:
    """Die Abwesenheiten des Kalenders für eine Person von start bis ende, je Tag: Name, Abwesenheit, Stunden = Sollzeit des Tags (Heiligabend
    7,00 h), bezahlt. Nur an Tagen mit Sollzeit (beschäftigt). Gebuchte Arbeit an dem Tag ändert nichts daran -- sie kommt dazu."""
    from .sollzeit import soll_zeitraum  # lokal: sollzeit fragt den Kalender nach der Sollzeit
    tage = kalendertage_im_zeitraum(db, employee_id, start, ende)
    if not tage:
        return []
    soll = soll_zeitraum(db, employee_id, start, ende)
    return [{"tag": t, "schluessel": e.schluessel, "name": e.name, "abwesenheit": e.abwesenheit, "stunden": soll[t], "bezahlt": bool(e.bezahlt)}
            for t, e in tage if soll[t] > 0]


def datum_text(e: ArbeitszeitKalendertag) -> str:
    return f"{e.tag:02d}.{e.monat:02d}."


def eintrag_dict(e: ArbeitszeitKalendertag) -> dict:
    return {"id": e.id, "schluessel": e.schluessel, "name": e.name, "monat": e.monat, "tag": e.tag, "datum": datum_text(e),
            "sollzeit": e.sollzeit, "abwesenheit": e.abwesenheit, "bezahlt": bool(e.bezahlt), "im_urlaub": e.im_urlaub,
            "im_urlaub_text": IM_URLAUB.get(e.im_urlaub, e.im_urlaub), "nur_gewerblich": bool(e.nur_gewerblich), "nur_mo_fr": bool(e.nur_mo_fr),
            "aktiv": bool(e.aktiv)}


def naechste(db: Session, heute: date, jahre: int = 2) -> list[dict]:
    """Die aktiven Kalendertage dieses und der folgenden Jahre ab heute, mit Datum und Wochentag (für „Zeiten → Abwesenheiten“) -- ob sie für
    eine Person gelten, hängt an Gruppe und Wochentag (Text „für …“)."""
    zeilen = []
    for e in aktive(db):
        for jahr in range(heute.year, heute.year + jahre):
            try:
                t = date(jahr, e.monat, e.tag)
            except ValueError:  # 29.02. in einem Jahr ohne Schalttag
                continue
            if t < heute or (e.nur_mo_fr and t.weekday() >= 5):
                continue
            zeilen.append({"tag": t, "name": e.name, "abwesenheit": e.abwesenheit, "sollzeit": e.sollzeit,
                           "fuer": "gewerbliche Mitarbeiter" if e.nur_gewerblich else "alle Mitarbeiter"})
    return sorted(zeilen, key=lambda z: z["tag"])


def _schluessel_aus(name: str, vorhanden: set[str]) -> str:
    basis = re.sub(r"[^a-z0-9]+", "_", name.casefold().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")).strip("_")[:32]
    basis = basis or "tag"
    schluessel, n = basis, 2
    while schluessel in vorhanden:
        schluessel, n = f"{basis}_{n}", n + 1
    return schluessel


def _pruefen(db: Session, werte: dict, eigene_id: int | None) -> dict:
    name = (werte.get("name") or "").strip()
    abwesenheit = (werte.get("abwesenheit") or "").strip()
    if not name:
        raise KalendertagUngueltig("Bitte einen Namen angeben, z. B. Heiligabend.")
    if not abwesenheit:
        raise KalendertagUngueltig("Bitte die Abwesenheit angeben, z. B. „Heiligabend – bezahlte Freistellung“.")
    monat, tag = int(werte["monat"]), int(werte["tag"])
    try:
        date(2000, monat, tag)  # ein Schaltjahr: der 29.02. ist ein Tag
    except ValueError as exc:
        raise KalendertagUngueltig("Diesen Tag gibt es nicht.") from exc
    if werte.get("im_urlaub") not in IM_URLAUB:
        raise KalendertagUngueltig("Unbekannte Angabe „Im Urlaub“.")
    sollzeit = werte.get("sollzeit")
    if sollzeit is not None and not (Decimal("0") <= Decimal(str(sollzeit)) <= Decimal("24")):
        raise KalendertagUngueltig("Die Sollzeit liegt zwischen 0 und 24 Stunden.")
    gleich = db.scalar(select(ArbeitszeitKalendertag).where(ArbeitszeitKalendertag.monat == monat, ArbeitszeitKalendertag.tag == tag))
    if gleich is not None and gleich.id != eigene_id:
        raise KalendertagUngueltig(f"Für den {tag:02d}.{monat:02d}. steht schon „{gleich.name}“ im Kalender.")
    return {"name": name, "monat": monat, "tag": tag, "sollzeit": None if sollzeit is None else round_hours(Decimal(str(sollzeit))), "abwesenheit": abwesenheit,
            "bezahlt": bool(werte["bezahlt"]), "im_urlaub": werte["im_urlaub"], "nur_gewerblich": bool(werte["nur_gewerblich"]),
            "nur_mo_fr": bool(werte["nur_mo_fr"]), "aktiv": bool(werte["aktiv"])}


def anlegen(db: Session, werte: dict) -> ArbeitszeitKalendertag:
    """Ein neuer Kalendertag; der Schlüssel (für die Zuordnung) kommt aus dem Namen und bleibt. Committet."""
    neu = _pruefen(db, werte, None)
    e = ArbeitszeitKalendertag(schluessel=_schluessel_aus(neu["name"], set(db.scalars(select(ArbeitszeitKalendertag.schluessel)).all())), **neu)
    db.add(e)
    _commit(db)
    db.refresh(e)
    return e


def aendern(db: Session, eintrag_id: int, werte: dict) -> ArbeitszeitKalendertag:
    """Alle Angaben außer dem Schlüssel. Wie eine Änderung am Arbeitszeitmodell gilt sie auch für zurückliegende Jahre. Committet."""
    e = db.get(ArbeitszeitKalendertag, eintrag_id)
    if e is None:
        raise LookupError("Der Kalendertag wurde nicht gefunden.")
    for feld, wert in _pruefen(db, werte, e.id).items():
        setattr(e, feld, wert)
    _commit(db)
    db.refresh(e)
    return e


def _commit(db: Session) -> None:
    """Zwei gleichzeitige Einträge für denselben Tag enden an der Bedingung mit einer Meldung (422), nicht mit 500."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise KalendertagUngueltig("Für diesen Tag steht schon ein Eintrag im Kalender.") from exc
