"""Die Lohndatei für DATEV Lohn und Gehalt -- seit 1.9.224 (Lohn L1b, Punkt 1; ersetzt die Formate „Lohn und Gehalt“ (CSV) und LODAS, E8).

Format wie die Dateien, die Time 4 an das Lohnbüro gab (Muster in bildgrundlage/lohn, nicht in Git): ASCII, CRLF auch nach der letzten Zeile,
jede Zeile 11 Felder, getrennt durch Semikolon.

    Kopf          Beraternummer;Mandantennummer;MM/JJJJ          (aus den Einstellungen, nur der Admin trägt sie ein)
    Tageszeile    Personalnummer;Tag;Kennzeichen;Lohnart;Stunden;;;;;;   (Tag ohne führende Null, Stunden mit Komma und zwei Stellen;
                                                                          ohne Lohnart bleibt das Feld leer: 00201;31;UU;;7,50;;;;;;)
    Monatszeile   Personalnummer;;;Lohnart;;;Stunden;;;;          (nur eine Zeile der Zuordnung mit „Monatszeile“, heute keine)

Ein Monat. Personen aufsteigend nach Personalnummer, je Person die Tage aufsteigend, im Tag Arbeit, Mehrarbeit, Feiertag, Kalendertag,
Abwesenheit, Schlechtwetter; die Monatszeilen der Person zuletzt. Mehrere Zeilen je Person und Tag sind erlaubt (Steuerbüro, 05.11.2026).
Eine Zeile mit 0,00 Stunden entfällt.

Was je Person und Tag hineinkommt (Kennzeichen und Lohnart aus der Zuordnung, app/lohnarten.py -- ohne Kennzeichen keine Zeile):
    Arbeit         die Arbeit des Tags im Lohn (app/time_tracking.py::arbeit_des_tags(), auf 0,25 h) -- nur beim Umfang „alles“
    Mehrarbeit     nur Azubis (EmployeePayrollSettings.azubi): was die Arbeit über die Sollzeit des Tags bringt, zusammen mit den übrigen Stunden des
                   Tags (Feiertag, Kalendertag, Abwesenheit, Schlechtwetter) -- höchstens die Arbeit; diese Stunden stehen dann unter der
                   Mehrarbeit (AA / 1900), nicht unter der Arbeit. Ohne Kennzeichen der Mehrarbeit bleibt alles unter der Arbeit.
    Feiertag       gesetzlicher Feiertag (Bundesland der Planung) mit Sollzeit, nur beim Umfang „alles“ (E3); geht einem Kalendertag vor
    Kalendertag    die Abwesenheit des Arbeitszeitkalenders (Heiligabend, Silvester), Stunden = Sollzeit des Tags (app/arbeitszeitkalender.py)
    Abwesenheit    jede genehmigte Abwesenheit außer Schlechtwetter, je Tag mit Sollzeit × Anteil (app/sollzeit.py::abwesenheit_tage())
    Schlechtwetter je Ausfalltag Sollzeit minus Arbeit (app/schlechtwetter.py::ausfall()), Winter oder Sommer nach dem Tag
Umfang „nur Abwesenheiten“: Kalendertag, Abwesenheit, Schlechtwetter -- keine Arbeit, keine Mehrarbeit, kein Feiertag. Umfang „nichts“: keine
Zeile. Vor dem Eintritt und nach dem Austritt nichts (die Sollzeit ist dort 0; gebuchte Arbeit dort geht nicht in die Datei).

Rollenlos und nur lesend; wer ausgeben darf und ob der Monat abgeschlossen und vollständig ist, prüfen app/time_backoffice.py und der Router.
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
# Reihenfolge der Zeilen eines Tags
REIHE = ("arbeit", "mehrarbeit", "feiertag", "kalender", "abwesenheit", "schlechtwetter")


@dataclass
class Zeile:
    tag: date | None  # None: Monatszeile
    kennzeichen: str | None
    lohnart: str | None
    stunden: Decimal
    quelle: str  # eins aus REIHE


@dataclass
class Person:
    employee_id: int
    name: str
    personalnummer: str | None
    umfang: str
    azubi: bool
    zeilen: list[Zeile] = field(default_factory=list)


def monat_ende(erster: date) -> date:
    return (erster.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def _stunden_text(wert: Decimal) -> str:
    return f"{round_hours(wert):.2f}".replace(".", ",")


def berechnen(db: Session, erster: date) -> list[Person]:
    """Je Person, die im Monat aktiv ist oder Buchungen bzw. Abwesenheiten hat, ihre Zeilen (sortiert wie in der Datei); Personen mit Umfang
    „nichts“ ohne Zeilen. Reihenfolge der Personen: nach Personalnummer, ohne Nummer nach Namen dahinter."""
    from .arbeitszeitkalender import abwesenheiten as kalender_abwesenheiten
    from .lohnarten import _alle, fest, kalender, zuordnung
    from .planning import automatic_public_holidays, load_region_settings
    from .schlechtwetter import SCHLECHTWETTER, ausfall
    from .sollzeit import abwesenheit_tage, beschaeftigt_am, soll_fuer_personen
    from .time_backoffice import effective_datev_personnel_number, export_umfang, load_employee_payroll
    from .time_tracking import arbeit_des_tags, employee_name

    ende = monat_ende(erster)
    buchungen: dict[tuple[int, date], list[TimeEntry]] = {}
    for r in db.scalars(select(TimeEntry).where(TimeEntry.work_date >= erster, TimeEntry.work_date <= ende, TimeEntry.status == "booked")):
        buchungen.setdefault((r.employee_id, r.work_date), []).append(r)
    abwesend = list(db.scalars(select(EmployeeAbsence).where(EmployeeAbsence.start_date <= ende, EmployeeAbsence.end_date >= erster)
                               .order_by(EmployeeAbsence.start_date, EmployeeAbsence.id)))
    mit_daten = {e for e, _ in buchungen} | {a.employee_id for a in abwesend}
    personen = list(db.scalars(select(Employee).where(or_(Employee.active == True, Employee.id.in_(mit_daten or {0})))))  # noqa: E712
    payrolls = {p.employee_id: p for p in db.scalars(select(EmployeePayrollSettings))}
    feiertage = automatic_public_holidays(load_region_settings(db).federal_state_code, range(erster.year - 1, erster.year + 2))
    soll = soll_fuer_personen(db, [e.id for e in personen], erster, ende)
    alle = _alle(db)
    z_arbeit, z_mehr, z_feiertag = fest(db, "arbeit", alle=alle), fest(db, "mehrarbeit_azubi", alle=alle), fest(db, "feiertag", alle=alle)
    sw_paare = [(a.employee_id, t) for a in abwesend if a.absence_category == SCHLECHTWETTER
                for t in _tage(max(a.start_date, erster), min(a.end_date, ende))]
    sw_stunden = ausfall(db, sw_paare)

    ergebnis: list[Person] = []
    for emp in personen:
        p = payrolls.get(emp.id) or load_employee_payroll(db, emp.id)
        umfang = export_umfang(p)
        person = Person(emp.id, employee_name(emp) or f"#{emp.id}", effective_datev_personnel_number(db, emp, p), umfang, bool(getattr(p, "azubi", False)))
        ergebnis.append(person)
        if umfang == "nichts":
            continue
        alles = umfang == "alles"
        je_tag: dict[date, list[tuple[str, Decimal, dict | None]]] = {}  # Tag -> (Quelle, Stunden, Zuordnung) außer der Arbeit
        soll_p = soll[emp.id]
        if alles:
            for tag, s in soll_p.items():
                if tag in feiertage and s > 0:
                    je_tag.setdefault(tag, []).append(("feiertag", s, z_feiertag))
        for k in kalender_abwesenheiten(db, emp.id, erster, ende):
            if k["tag"] not in feiertage:
                z = kalender(db, k["schluessel"], alle=alle)
                je_tag.setdefault(k["tag"], []).append(("kalender", k["stunden"], z if z and z["exportiert"] else None))
        for a in (a for a in abwesend if a.employee_id == emp.id):
            von, bis = max(a.start_date, erster), min(a.end_date, ende)
            if a.absence_category == SCHLECHTWETTER:
                for tag in _tage(von, bis):
                    if beschaeftigt_am(p, tag):
                        je_tag.setdefault(tag, []).append(("schlechtwetter", sw_stunden[(emp.id, tag)]["stunden"],
                                                           zuordnung(db, SCHLECHTWETTER, None, tag, alle=alle)))
                continue
            stand = abwesenheit_tage(db, emp.id, von, bis, kategorie=a.absence_category, halber_tag=bool(a.halber_tag), feiertage=feiertage,
                                     kalendertag_urlaub=a.kalendertag_urlaub)
            for t in stand["je_tag"]:
                je_tag.setdefault(t["tag"], []).append(("abwesenheit", t["stunden"], zuordnung(db, a.absence_category, a.absence_type, t["tag"],
                                                                                                  alle=alle)))
        tage = sorted(set(je_tag) | ({t for (e, t) in buchungen if e == emp.id and beschaeftigt_am(p, t)} if alles else set()))
        monat: dict[str, Decimal] = {}
        for tag in tage:
            posten = je_tag.get(tag, [])
            if alles and (emp.id, tag) in buchungen:
                arbeit = arbeit_des_tags(buchungen[(emp.id, tag)])
                mehr = NULL
                if person.azubi and z_mehr is not None:
                    mehr = min(arbeit, max(NULL, arbeit + sum((h for _q, h, _z in posten), NULL) - soll_p.get(tag, NULL)))
                if z_arbeit is not None:
                    posten = [("arbeit", arbeit - mehr, z_arbeit), ("mehrarbeit", mehr, z_mehr)] + posten
            for quelle, stunden, z in sorted(posten, key=lambda x: REIHE.index(x[0])):
                if z is None or stunden <= 0:
                    continue
                if z.get("monatszeile"):
                    monat[z["lohnart"]] = monat.get(z["lohnart"], NULL) + stunden
                    continue
                person.zeilen.append(Zeile(tag, z["kennzeichen"], z["lohnart"], round_hours(stunden), quelle))
        for lohnart in sorted(monat):
            person.zeilen.append(Zeile(None, None, lohnart, round_hours(monat[lohnart]), "schlechtwetter"))
    ergebnis.sort(key=lambda x: (x.personalnummer is None, x.personalnummer or "", x.name.casefold()))
    return ergebnis


def _tage(von: date, bis: date):
    tag = von
    while tag <= bis:
        yield tag
        tag += timedelta(days=1)


def zeile_text(pnr: str, z: Zeile) -> str:
    if z.tag is None:
        return f"{pnr};;;{z.lohnart};;;{_stunden_text(z.stunden)};;;;"
    return f"{pnr};{z.tag.day};{z.kennzeichen};{z.lohnart or ''};{_stunden_text(z.stunden)};;;;;;"


def datei(beraternummer: str, mandantennummer: str, erster: date, personen: list[Person]) -> bytes:
    """Die Datei: Kopf, dann je Person mit Zeilen ihre Zeilen. Jede Person mit Zeilen braucht eine Personalnummer (prüft der Aufrufer)."""
    zeilen = [f"{beraternummer};{mandantennummer};{erster:%m/%Y}"]
    for p in personen:
        zeilen += [zeile_text(p.personalnummer, z) for z in p.zeilen]
    return ("\r\n".join(zeilen) + "\r\n").encode("ascii")
