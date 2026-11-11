"""Die Tagesbilanz je Person und Tag -- seit 1.9.308 (Lohn L2a, Punkt 1; Befund L2, Abschnitt 8, L2a-1).

Eine Rechnung für alles, was je Person und Tag für den Lohn und die Konten zählt -- unabhängig von Export-Umfang und Zuordnung (die gelten erst in
der Lohndatei, app/lohndatei.py::berechnen(), die seit 1.9.308 darüber rechnet). Je Person und Tag (Tag):

    soll                  die Sollzeit des Tags (app/sollzeit.py; vor dem Eintritt und nach dem Austritt 0)
    beschaeftigt          zwischen Eintritt und Austritt (Lohnstammdaten)
    gebucht               es gibt gebuchte Zeiten an dem Tag (eine laufende zählt nicht)
    arbeit                die Arbeit des Tags im Lohn: alle Zeitarten nach der Pause, auf 0,25 h (app/time_tracking.py::arbeit_des_tags()) -- auch
                          vor dem Eintritt oder nach dem Austritt gebucht (beschaeftigt sagt, ob sie zählt)
    fahrzeit              davon die Fahrzeit (Zeitart „travel“), minutengenau mit zwei Stellen -- getrennt ausgewiesen, solange offen ist, ob sie ins
                          Arbeitszeitkonto zählt (Frage 7 des Befunds L2)
    arbeit_ohne_fahrzeit  die übrigen Zeitarten, ebenso auf 0,25 h
    feiertag              der Name des gesetzlichen Feiertags (Bundesland wie „Zeiten“), sonst None -- auch an einem Tag ohne Sollzeit
    posten                was am Tag außer der Arbeit Stunden trägt (Posten), je mit Quelle:
        feiertag          gesetzlicher Feiertag mit Sollzeit: die Sollzeit (E3)
        kalender          Tag des Arbeitszeitkalenders (Heiligabend, Silvester): die Sollzeit -- nicht an einem Feiertag (der geht vor), nicht wo ein
                          Urlaub ihn als ganzen Urlaubstag nimmt (app/arbeitszeitkalender.py)
        abwesenheit       jede genehmigte Abwesenheit außer Schlechtwetter: Kategorie, Art, Anteil (1 oder 0,5), Stunden = Sollzeit × Anteil -- nur Tage
                          mit Sollzeit, ohne Feiertage und Kalendertage (app/sollzeit.py::abwesenheit_tage())
        schlechtwetter    Ausfalltag: Sollzeit − Arbeit, nie unter 0 (app/schlechtwetter.py::ausfall()), nur beschäftigt; Winter Dezember bis März
    Die Posten eines Tags stehen in dieser Reihenfolge: Feiertag, Kalendertag, dann die Abwesenheiten nach Beginn und Kennung.

Nur genehmigte Abwesenheiten (EmployeeAbsence) zählen, offene Anträge nicht. Für viele Personen in einer festen Zahl Abfragen, unabhängig von der
Zahl der Personen, Tage, Buchungen und Abwesenheiten (das Arbeitszeitmodell je Zuordnung und Kalenderwoche ausgenommen, wie
app/sollzeit.py::soll_fuer_personen()). Rollenlos und nur lesend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import Employee, EmployeeAbsence, EmployeePayrollSettings, TimeEntry
from .rounding import round_hours

NULL = Decimal("0")
QUELLEN = ("feiertag", "kalender", "abwesenheit", "schlechtwetter")
FAHRZEIT = "travel"
WINTER = (12, 1, 2, 3)


@dataclass
class Posten:
    quelle: str  # eins aus QUELLEN
    stunden: Decimal
    bezeichnung: str  # „Feiertag“, „Heiligabend – bezahlte Freistellung“, „Urlaub (Sonderurlaub)“, „Schlechtwetter Winter“
    kategorie: str | None = None  # Abwesenheit: die Kategorie; Kalendertag: sein Schlüssel; Schlechtwetter: „schlechtwetter“
    art: str | None = None  # Abwesenheit: die Art, wie gespeichert
    anteil: Decimal | None = None  # Abwesenheit: 1 oder 0,5


@dataclass
class Tag:
    tag: date
    soll: Decimal
    beschaeftigt: bool
    gebucht: bool = False
    arbeit: Decimal = NULL
    arbeit_ohne_fahrzeit: Decimal = NULL
    fahrzeit: Decimal = NULL
    feiertag: str | None = None
    posten: list[Posten] = field(default_factory=list)


@dataclass
class Bilanz:
    von: date
    bis: date
    personen: list[Employee]
    payrolls: dict[int, EmployeePayrollSettings]
    feiertage: dict[date, str]
    tage: dict[int, dict[date, Tag]]  # je Person jeder Tag von von bis bis


def _tage(von: date, bis: date):
    tag = von
    while tag <= bis:
        yield tag
        tag += timedelta(days=1)


def bilanz(db: Session, von: date, bis: date, employee_ids=None) -> Bilanz:
    """Die Tagesbilanz von von bis bis. employee_ids: genau diese Personen; ohne Angabe jede aktive und jede mit Buchungen oder Abwesenheiten im
    Zeitraum (wie die Lohndatei)."""
    from .absence_requests import ABSENCE_CATEGORY_LABELS
    from .arbeitszeitkalender import abwesenheiten_aus, aktive, ersetzt_aus, kalendertage_aus
    from .planning import automatic_public_holidays
    from .schlechtwetter import SCHLECHTWETTER
    from .sollzeit import abwesenheit_tage, beschaeftigt_am, soll_fuer_personen
    from .time_tracking import arbeit_des_tags
    from .zeiten import feiertage_bundesland

    ids = None if employee_ids is None else list(dict.fromkeys(int(i) for i in employee_ids))
    abfrage = select(TimeEntry).where(TimeEntry.work_date >= von, TimeEntry.work_date <= bis, TimeEntry.status == "booked")
    if ids is not None:
        abfrage = abfrage.where(TimeEntry.employee_id.in_(ids or [0]))
    buchungen: dict[tuple[int, date], list[TimeEntry]] = {}
    for r in db.scalars(abfrage):
        buchungen.setdefault((r.employee_id, r.work_date), []).append(r)
    abfrage = (select(EmployeeAbsence).where(EmployeeAbsence.start_date <= bis, EmployeeAbsence.end_date >= von)
               .order_by(EmployeeAbsence.start_date, EmployeeAbsence.id))
    if ids is not None:
        abfrage = abfrage.where(EmployeeAbsence.employee_id.in_(ids or [0]))
    abwesend: dict[int, list[EmployeeAbsence]] = {}
    for a in db.scalars(abfrage):
        abwesend.setdefault(a.employee_id, []).append(a)
    if ids is None:
        mit_daten = {e for e, _ in buchungen} | set(abwesend)
        personen = list(db.scalars(select(Employee).where(or_(Employee.active == True, Employee.id.in_(mit_daten or {0})))))  # noqa: E712
    else:
        personen = list(db.scalars(select(Employee).where(Employee.id.in_(ids or [0]))))
    payrolls = {p.employee_id: p for p in db.scalars(select(EmployeePayrollSettings).where(
        EmployeePayrollSettings.employee_id.in_([e.id for e in personen] or [0])))}
    feiertage = automatic_public_holidays(feiertage_bundesland(db), range(von.year - 1, bis.year + 2))
    soll = soll_fuer_personen(db, [e.id for e in personen], von, bis)
    kalender_liste = aktive(db)

    ergebnis: dict[int, dict[date, Tag]] = {}
    for emp in personen:
        p, soll_p, eigene = payrolls.get(emp.id), soll.get(emp.id, {}), abwesend.get(emp.id, [])
        tage: dict[date, Tag] = {}
        for t in _tage(von, bis):
            tag = Tag(t, soll_p.get(t, NULL), beschaeftigt_am(p, t), feiertag=feiertage.get(t))
            rows = buchungen.get((emp.id, t))
            if rows:
                tag.gebucht = True
                tag.arbeit = arbeit_des_tags(rows)
                tag.arbeit_ohne_fahrzeit = arbeit_des_tags([r for r in rows if r.entry_type != FAHRZEIT])
                tag.fahrzeit = round_hours(sum((Decimal(str(r.hours or 0)) for r in rows if r.entry_type == FAHRZEIT), NULL))
            if tag.feiertag is not None and tag.soll > 0:
                tag.posten.append(Posten("feiertag", tag.soll, "Feiertag"))
            tage[t] = tag
        kal = kalendertage_aus(kalender_liste, emp.employee_group, soll_p, von, bis)
        for k in abwesenheiten_aus(kal, soll_p, ersetzt_aus(kal, [a for a in eigene if a.absence_category == "urlaub"])):
            if k["tag"] not in feiertage:
                tage[k["tag"]].posten.append(Posten("kalender", k["stunden"], k["abwesenheit"], kategorie=k["schluessel"]))
        for a in eigene:
            a_von, a_bis = max(a.start_date, von), min(a.end_date, bis)
            if a.absence_category == SCHLECHTWETTER:
                for t in _tage(a_von, a_bis):
                    if tage[t].beschaeftigt:
                        tage[t].posten.append(Posten("schlechtwetter", max(NULL, tage[t].soll - tage[t].arbeit),
                                                     "Schlechtwetter " + ("Winter" if t.month in WINTER else "Sommer"), kategorie=SCHLECHTWETTER))
                continue
            stand = abwesenheit_tage(db, emp.id, a_von, a_bis, kategorie=a.absence_category, halber_tag=bool(a.halber_tag), feiertage=feiertage,
                                     kalendertag_urlaub=a.kalendertag_urlaub, soll=soll_p, kalender=dict(kal))
            kategorie = ABSENCE_CATEGORY_LABELS.get(a.absence_category, a.absence_category)
            was = kategorie + (f" ({a.absence_type})" if a.absence_type and a.absence_type.casefold() != kategorie.casefold() else "")
            for x in stand["je_tag"]:
                tage[x["tag"]].posten.append(Posten("abwesenheit", x["stunden"], was, kategorie=a.absence_category, art=a.absence_type,
                                                    anteil=x["anteil"]))
        ergebnis[emp.id] = tage
    return Bilanz(von, bis, personen, payrolls, feiertage, ergebnis)
