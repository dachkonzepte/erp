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

Was nicht in die Datei geht (seit 1.9.225, Lohn L1b, Punkt 2), je Person mit Grund (Person.nicht, „Monat & Lohn“ über dem Knopf): Arbeit, Mehrarbeit
und Feiertage beim Umfang „nur Abwesenheiten“; gebuchte Arbeit und eingetragene Abwesenheiten beim Umfang „nichts“ (Feiertage und Kalendertage einer
Person ohne Export nennt die Liste nicht); jede Zeile ohne Kennzeichen in der Zuordnung; Arbeit vor dem Eintritt oder nach dem Austritt. Je Art und
Grund die Zahl der Tage und die Stunden. Zeilen mit 0,00 Stunden fehlen nicht -- es gibt nichts.

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
UMFANG_NICHTS = "Export-Umfang „nichts“"
UMFANG_ABWESENHEITEN = "Export-Umfang „nur Abwesenheiten“"
OHNE_KENNZEICHEN = "ohne Kennzeichen in der Zuordnung"
AUSSERHALB = "vor dem Eintritt oder nach dem Austritt"


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
    nachname: str = ""
    zeilen: list[Zeile] = field(default_factory=list)
    # seit 1.9.225: was nicht in die Datei geht -- je (Art, Grund) {"was", "grund", "tage", "stunden"}
    nicht: list[dict] = field(default_factory=list)

    def nicht_merken(self, was: str, grund: str, tag: date, stunden: Decimal) -> None:
        for n in self.nicht:
            if (n["was"], n["grund"]) == (was, grund):
                n["tage"].add(tag)
                n["stunden"] += stunden
                return
        self.nicht.append({"was": was, "grund": grund, "tage": {tag}, "stunden": stunden})

    def nicht_texte(self) -> list[str]:
        """„Arbeit: 2 Tage, 15,50 h – Export-Umfang „nur Abwesenheiten““ je Art und Grund."""
        return [f"{n['was']}: {len(n['tage'])} {'Tag' if len(n['tage']) == 1 else 'Tage'}, {_stunden_text(n['stunden'])} h – {n['grund']}"
                for n in self.nicht]


def monat_ende(erster: date) -> date:
    return (erster.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def _stunden_text(wert: Decimal) -> str:
    return f"{round_hours(wert):.2f}".replace(".", ",")


def berechnen(db: Session, erster: date) -> list[Person]:
    """Je Person, die im Monat aktiv ist oder Buchungen bzw. Abwesenheiten hat, ihre Zeilen (sortiert wie in der Datei); Personen mit Umfang
    „nichts“ ohne Zeilen. Reihenfolge der Personen: nach Personalnummer, ohne Nummer nach Namen dahinter."""
    from .absence_requests import ABSENCE_CATEGORY_LABELS
    from .arbeitszeitkalender import abwesenheiten as kalender_abwesenheiten
    from .lohnarten import _alle, fest, kalender, zuordnung
    from .planning import automatic_public_holidays
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
    # seit 1.9.225 das Bundesland wie „Zeiten“ (ohne Einstellung Nordrhein-Westfalen; bis dahin load_region_settings(), das ohne Zeile wirft)
    from .zeiten import feiertage_bundesland
    feiertage = automatic_public_holidays(feiertage_bundesland(db), range(erster.year - 1, erster.year + 2))
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
        person = Person(emp.id, employee_name(emp) or f"#{emp.id}", effective_datev_personnel_number(db, emp, p), umfang, bool(getattr(p, "azubi", False)),
                        emp.last_name or "")
        ergebnis.append(person)
        alles, nichts = umfang == "alles", umfang == "nichts"
        # Tag -> (Quelle, Stunden, Zuordnung, Bezeichnung) außer der Arbeit; Feiertag und Kalendertag nur für eine Person mit Export (seit 1.9.225 der
        # Feiertag auch bei „nur Abwesenheiten“ -- er steht dann unter „Nicht in der Datei“)
        je_tag: dict[date, list[tuple[str, Decimal, dict | None, str]]] = {}
        soll_p = soll[emp.id]
        if not nichts:
            for tag, s in soll_p.items():
                if tag in feiertage and s > 0:
                    je_tag.setdefault(tag, []).append(("feiertag", s, z_feiertag, "Feiertag"))
            for k in kalender_abwesenheiten(db, emp.id, erster, ende):
                if k["tag"] not in feiertage:
                    z = kalender(db, k["schluessel"], alle=alle)
                    je_tag.setdefault(k["tag"], []).append(("kalender", k["stunden"], z if z and z["exportiert"] else None, k["abwesenheit"]))
        for a in (a for a in abwesend if a.employee_id == emp.id):
            von, bis = max(a.start_date, erster), min(a.end_date, ende)
            if a.absence_category == SCHLECHTWETTER:
                for tag in _tage(von, bis):
                    if beschaeftigt_am(p, tag):
                        je_tag.setdefault(tag, []).append(("schlechtwetter", sw_stunden[(emp.id, tag)]["stunden"],
                                                           zuordnung(db, SCHLECHTWETTER, None, tag, alle=alle),
                                                           "Schlechtwetter " + ("Winter" if tag.month in (12, 1, 2, 3) else "Sommer")))
                continue
            stand = abwesenheit_tage(db, emp.id, von, bis, kategorie=a.absence_category, halber_tag=bool(a.halber_tag), feiertage=feiertage,
                                     kalendertag_urlaub=a.kalendertag_urlaub)
            kategorie = ABSENCE_CATEGORY_LABELS.get(a.absence_category, a.absence_category)
            was = kategorie + (f" ({a.absence_type})" if a.absence_type and a.absence_type.casefold() != kategorie.casefold() else "")
            for t in stand["je_tag"]:
                je_tag.setdefault(t["tag"], []).append(("abwesenheit", t["stunden"], zuordnung(db, a.absence_category, a.absence_type, t["tag"],
                                                                                                  alle=alle), was))
        gebucht = {t for (e, t) in buchungen if e == emp.id}
        monat: dict[str, Decimal] = {}
        for tag in sorted(set(je_tag) | gebucht):
            posten = je_tag.get(tag, [])
            if tag in gebucht:
                arbeit = arbeit_des_tags(buchungen[(emp.id, tag)])
                if not beschaeftigt_am(p, tag):
                    if arbeit > 0:
                        person.nicht_merken("Arbeit", AUSSERHALB, tag, arbeit)
                elif not alles:
                    posten = [("arbeit", arbeit, z_arbeit, "Arbeit")] + posten
                else:
                    mehr = NULL
                    if person.azubi and z_mehr is not None:
                        mehr = min(arbeit, max(NULL, arbeit + sum((h for _q, h, _z, _w in posten), NULL) - soll_p.get(tag, NULL)))
                    posten = [("arbeit", arbeit - mehr, z_arbeit, "Arbeit"), ("mehrarbeit", mehr, z_mehr, "Mehrarbeit")] + posten
            for quelle, stunden, z, was in sorted(posten, key=lambda x: REIHE.index(x[0])):
                if stunden <= 0:
                    continue
                grund = (UMFANG_NICHTS if nichts else UMFANG_ABWESENHEITEN if not alles and quelle in ("arbeit", "mehrarbeit", "feiertag")
                         else OHNE_KENNZEICHEN if z is None else None)
                if grund:
                    person.nicht_merken(was, grund, tag, stunden)
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
