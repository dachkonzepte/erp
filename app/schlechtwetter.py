"""Ausfalltag Schlechtwetter -- seit 1.9.170 (Lohn L1a, Punkt 5, Entscheidung Tobias E5).

Schlechtwetter ist eine Abwesenheit der Kategorie „schlechtwetter“ (EmployeeAbsence, „ein Weg“ über app/absence_requests.py), je Person und
Tag. Die Zuordnung (app/lohnarten.py) unterscheidet Winter (01.12.–31.03., seit 1.9.214 WA / 8195 je Tag; bis 1.9.213 Saison-Kurzarbeitergeld
8110 als Monatszeile) und Sommer. Seit 1.9.216 hat ein Ausfalltag Stunden, abgeleitet: Sollzeit minus gebuchte Arbeit (ausfall()).

    eintragen      Admin, Büro – Finanzen, Kolonnenführer und Vorarbeiter für jeden gewerblichen Mitarbeiter -- gilt sofort (genehmigt);
                   jede andere Person für sich selbst -- ein Antrag, den Kolonnenführer, Vorarbeiter oder Admin bestätigt
    abgelehnt      Samstag, Sonntag, gesetzlicher Feiertag, Tag des Arbeitszeitkalenders (seit 1.9.175, dort gilt dessen Abwesenheit), Tag
                   ohne Sollzeit (app/sollzeit.py), nicht gewerblich, seit 1.9.204 schon abwesend oder ein offener Antrag -- 422 mit Grund
                   je Person
    Warnung        hat die Person an dem Tag schon Zeit gebucht oder laufen, 409 mit der Liste; gespeichert erst mit „trotzdem“ -- seit 1.9.178
                   ebenso an einem von Hand eingetragenen betriebsfreien Tag (bis 1.9.177 ohne Rückfrage angenommen)
    Kolonnenführer TeamEmployee.is_crew_leader in einer aktiven Kolonne (seit 1.7.12); Vorarbeiter EmployeeRoleSettings.vorarbeiter
                   (seit 1.9.170 -- bis dahin war „Vorarbeiter“ nur Text: Funktion „Dachdecker Vorarbeiter“, Rolle in der Kolonne)

Die Rollenentscheidung trifft der Router (app/routers/schlechtwetter.py); hier stehen die Fakten und Regeln.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Employee, EmployeeAbsenceRequest, EmployeeRoleSettings, PlanningHoliday, Team, TeamEmployee, TimeEntry

SCHLECHTWETTER = "schlechtwetter"
WOCHENTAG = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")


class SchlechtwetterWarnung(ValueError):
    """An dem Tag ist schon Zeit gebucht oder (seit 1.9.178) er ist als betriebsfreier Tag eingetragen -- gespeichert erst mit „trotzdem“ (409)."""

    def __init__(self, warnungen: list[dict]):
        self.warnungen = warnungen
        frei = [w["text"] for w in warnungen if w.get("art") == "betriebsfrei"]
        gebucht = [w["text"].rstrip(".") for w in warnungen if w.get("art") != "betriebsfrei"]
        teile = [f"{frei[0]}." if frei else ""]
        if gebucht:
            teile.append(("Außerdem ist schon Zeit gebucht: " if frei else "An diesem Tag ist schon Zeit gebucht: ") + "; ".join(gebucht) + ".")
        super().__init__(" ".join(t for t in teile if t))


class SchlechtwetterAbgelehnt(ValueError):
    """Mindestens eine Person kann an dem Tag keinen Ausfalltag haben (422) -- nichts gespeichert."""

    def __init__(self, liste: list[dict]):
        self.liste = liste
        super().__init__("Nicht eingetragen: " + "; ".join(x["text"].rstrip(".") for x in liste) + ".")  # seit 1.9.171 ein Punkt am Ende, nicht zwei


def _name(emp: Employee | None) -> str:
    return f"{emp.first_name} {emp.last_name}".strip() if emp else ""


def ist_kolonnenfuehrer(db: Session, employee_id: int) -> bool:
    return db.scalar(select(TeamEmployee.id).join(Team, Team.id == TeamEmployee.team_id).where(
        TeamEmployee.employee_id == employee_id, TeamEmployee.is_crew_leader.is_(True), Team.active.is_(True)).limit(1)) is not None


def ist_vorarbeiter(db: Session, employee_id: int) -> bool:
    return bool(db.scalar(select(EmployeeRoleSettings.vorarbeiter).where(EmployeeRoleSettings.employee_id == employee_id)))


def ist_fuehrung(db: Session, employee_id: int | None) -> bool:
    """Kolonnenführer oder Vorarbeiter -- und selbst aktiv."""
    if employee_id is None:
        return False
    emp = db.get(Employee, employee_id)
    return bool(emp is not None and emp.active and (ist_kolonnenfuehrer(db, employee_id) or ist_vorarbeiter(db, employee_id)))


def gewerbliche(db: Session) -> list[Employee]:
    return list(db.scalars(select(Employee).where(Employee.active.is_(True), Employee.employee_group == "gewerblich")
                           .order_by(Employee.last_name, Employee.first_name)).all())


def kolonnen(db: Session) -> list[dict]:
    """Aktive Kolonnen mit ihren gewerblichen Mitgliedern (für „ganze Kolonne“)."""
    zeilen = db.execute(select(Team.id, Team.name, TeamEmployee.employee_id).join(TeamEmployee, TeamEmployee.team_id == Team.id)
                        .join(Employee, Employee.id == TeamEmployee.employee_id)
                        .where(Team.active.is_(True), Employee.active.is_(True), Employee.employee_group == "gewerblich")
                        .order_by(Team.name, Team.id)).all()
    je: dict[int, dict] = {}
    for tid, name, eid in zeilen:
        je.setdefault(tid, {"id": tid, "name": name, "mitglieder": []})["mitglieder"].append(eid)
    return list(je.values())


def gesetzlicher_feiertag(db: Session, tag: date) -> str | None:
    """Der gesetzliche Feiertag des Bundeslands an diesem Tag (unabhängig davon, ob die Plantafel ihn anzeigt) -- von Hand eingetragene
    betriebsfreie Tage zählen nicht."""
    from .planning import automatic_public_holidays, load_region_settings  # lokal: planning importiert viel
    return automatic_public_holidays(load_region_settings(db).federal_state_code, [tag.year]).get(tag)


def grund_gegen(db: Session, employee: Employee | None, tag: date) -> str | None:
    """Warum diese Person an diesem Tag keinen Ausfalltag haben kann -- None: es geht."""
    from .sollzeit import soll  # lokal: sollzeit importiert work_time_models
    if employee is None or not employee.active:
        return "Mitarbeiter nicht gefunden oder inaktiv"
    if employee.employee_group != "gewerblich":
        return f"{_name(employee)}: Schlechtwetter nur für gewerbliche Mitarbeiter"
    if tag.weekday() >= 5:
        return f"{_name(employee)}: {WOCHENTAG[tag.weekday()]} {tag:%d.%m.%Y} ist kein Arbeitstag"
    feiertag = gesetzlicher_feiertag(db, tag)
    if feiertag:
        return f"{_name(employee)}: {tag:%d.%m.%Y} ist ein Feiertag ({feiertag})"
    from .arbeitszeitkalender import kalendertag  # seit 1.9.175: an einem Tag des Arbeitszeitkalenders gilt schon seine Abwesenheit
    eintrag = kalendertag(db, employee.id, tag)
    if eintrag is not None:
        return f"{_name(employee)}: am {tag:%d.%m.%Y} gilt „{eintrag.abwesenheit}“ (Arbeitszeitkalender)"
    if soll(db, employee.id, tag) <= 0:
        return f"{_name(employee)}: am {tag:%d.%m.%Y} keine Sollzeit"
    return None


def betriebsfrei(db: Session, tag: date) -> str | None:
    """Seit 1.9.178: der Name eines von Hand eingetragenen betriebsfreien Tags (PlanningHoliday, aktiv) -- None: keiner."""
    return db.scalar(select(PlanningHoliday.name).where(PlanningHoliday.holiday_date == tag, PlanningHoliday.active.is_(True)).limit(1))


def warnungen(db: Session, employee_ids: list[int], tag: date) -> list[dict]:
    """Personen, die an dem Tag schon Zeit gebucht haben oder deren Zeit läuft -- mit den Stunden; seit 1.9.178 zuerst der Tag selbst, wenn er
    als betriebsfreier Tag eingetragen ist (Vorgabe Tobias: Rückfrage statt stiller Annahme, Festlegung 1.9.170 Nr. 7 neu gefasst)."""
    from .rounding import round_hours
    liste = []
    frei = betriebsfrei(db, tag)
    if frei:
        liste.append({"employee_id": None, "art": "betriebsfrei", "text": f"Der {tag:%d.%m.%Y} ist als betriebsfreier Tag eingetragen ({frei})"})
    for eid in employee_ids:
        rows = db.scalars(select(TimeEntry).where(TimeEntry.employee_id == eid, TimeEntry.work_date == tag,
                                                   TimeEntry.status.in_(("booked", "running")))).all()
        if rows:
            stunden = round_hours(sum((r.hours or 0) for r in rows if r.status == "booked"))
            laeuft = any(r.status == "running" for r in rows)
            text = f"{_name(db.get(Employee, eid))} {str(stunden).replace('.', ',')} h gebucht" + (", eine Zeit läuft" if laeuft else "")
            liste.append({"employee_id": eid, "art": "gebucht", "stunden": stunden, "laeuft": laeuft, "text": text})
    return liste


def eintragen(db: Session, *, employee_ids: list[int], tag: date, notes: str | None, gleich_genehmigt: bool, user_id: int | None,
              trotzdem: bool) -> list[EmployeeAbsenceRequest]:
    """Ein Ausfalltag für jede genannte Person, alles oder nichts in einem Commit. Abgelehnte Tage -> SchlechtwetterAbgelehnt (422),
    gebuchte Zeit ohne „trotzdem“ -> SchlechtwetterWarnung (409). Seit 1.9.204 (L1a Stufe 4, Punkt 3) gehört auch „schon abwesend“ und „offener
    Antrag“ zu den abgelehnten Tagen -- je Person mit Namen in der Liste (bis 1.9.203 erst beim Anlegen, ohne Namen und nur der erste)."""
    from .absence_requests import _antrag_anlegen, _entscheiden, belegt, load_request
    ids = list(dict.fromkeys(int(i) for i in employee_ids))
    gruende = []
    for eid in ids:
        emp = db.get(Employee, eid)
        grund = grund_gegen(db, emp, tag)
        if grund is None:
            frei = belegt(db, eid, tag, tag)
            grund = f"{_name(emp)}: {frei}" if frei else None
        if grund:
            gruende.append({"text": grund})
    if gruende:
        raise SchlechtwetterAbgelehnt(gruende)
    warn = warnungen(db, ids, tag)
    if warn and not trotzdem:
        raise SchlechtwetterWarnung(warn)
    try:
        antraege = []
        for eid in ids:
            row = _antrag_anlegen(db, employee_id=eid, absence_type=None, absence_category=SCHLECHTWETTER, start_date=tag, end_date=tag,
                                  notes=notes, requested_by_user_id=user_id)
            if gleich_genehmigt:
                _entscheiden(db, row, decision="approved", reviewed_by_user_id=user_id)
            antraege.append(row.id)
    except ValueError as exc:
        db.rollback()
        raise SchlechtwetterAbgelehnt([{"text": str(exc)}]) from exc
    db.commit()
    return [load_request(db, i) for i in antraege]


def _stunden_text(wert) -> str:
    return f"{wert:.2f}".replace(".", ",") + " h"


def ausfall(db: Session, paare) -> dict[tuple[int, date], dict]:
    """Seit 1.9.216 (L1a Stufe 6, Punkt 5): die Stunden eines Ausfalltags -- abgeleitet, nie gespeichert (der Eintrag bleibt ein ganzer Tag ohne
    Stundenfeld): Sollzeit des Tags (app/sollzeit.py) minus die gebuchte Arbeitszeit der Person an dem Tag, nie unter 0. Gebucht = alle Zeitarten,
    nur gebuchte (eine laufende Zeit zählt erst gestoppt) -- seit 1.9.223 die Arbeit des Tags im Lohn, auf 0,25 h gerundet
    (app/time_tracking.py::arbeit_des_tags(); bis 1.9.222 minutengenau).
    An einem reinen Ausfalltag die volle Sollzeit; wird danach noch gebucht, stimmt die Zahl beim nächsten Lesen von selbst.
    paare: (Person, Tag). Je Paar soll, gebucht, stunden und text („Ausfall 6,00 h (Sollzeit 8,00 h − gebucht 2,00 h)“) -- eine Abfrage für
    die Sollzeit aller und eine für die Buchungen."""
    from collections import defaultdict
    from decimal import Decimal

    from .rounding import round_hours
    from .sollzeit import soll_fuer_personen
    from .time_tracking import arbeit_des_tags

    paare = set(paare)
    if not paare:
        return {}
    ids, tage = sorted({e for e, _ in paare}), sorted({t for _, t in paare})
    soll = soll_fuer_personen(db, ids, tage[0], tage[-1])
    buchungen = defaultdict(list)
    for r in db.scalars(select(TimeEntry).where(TimeEntry.employee_id.in_(ids), TimeEntry.work_date.in_(tage), TimeEntry.status == "booked")):
        buchungen[(r.employee_id, r.work_date)].append(r)
    aus = {}
    for eid, tag in paare:
        s = round_hours(soll.get(eid, {}).get(tag, Decimal("0")))
        g = arbeit_des_tags(buchungen.get((eid, tag), []))  # seit 1.9.223 die Arbeit des Tags im Lohn, auf 0,25 h (bis 1.9.222 minutengenau)
        h = max(Decimal("0"), s - g)
        text = f"Ausfall {_stunden_text(h)}" + (f" (Sollzeit {_stunden_text(s)} − gebucht {_stunden_text(g)})" if g else "")
        aus[(eid, tag)] = {"soll": s, "gebucht": g, "stunden": h, "text": text}
    return aus


def ausfalltage(db: Session, start: date, ende: date) -> dict[int, dict]:
    """Seit 1.9.216: die genehmigten Ausfalltage im Zeitraum je Person -- Zahl der Tage und Stunden zusammen (ausfall()), für „Monat & Lohn“."""
    from decimal import Decimal

    from .models import EmployeeAbsence
    tage = [(a.employee_id, a.start_date) for a in db.scalars(select(EmployeeAbsence).where(
        EmployeeAbsence.absence_category == SCHLECHTWETTER, EmployeeAbsence.start_date <= ende, EmployeeAbsence.end_date >= start))
        if start <= a.start_date <= ende]
    stunden = ausfall(db, tage)
    je: dict[int, dict] = {}
    for eid, tag in sorted(set(tage)):
        z = je.setdefault(eid, {"tage": 0, "stunden": Decimal("0")})
        z["tage"] += 1
        z["stunden"] += stunden[(eid, tag)]["stunden"]
    return je


def offene_antraege(db: Session) -> list[EmployeeAbsenceRequest]:
    return list(db.scalars(select(EmployeeAbsenceRequest).where(EmployeeAbsenceRequest.absence_category == SCHLECHTWETTER,
                                                                 EmployeeAbsenceRequest.status == "pending")
                           .order_by(EmployeeAbsenceRequest.start_date, EmployeeAbsenceRequest.id)).all())


def entscheiden(db: Session, antrag_id: int, *, decision: str, user_id: int | None, notes: str | None) -> EmployeeAbsenceRequest:
    """Einen offenen Schlechtwetter-Antrag bestätigen oder ablehnen; beim Bestätigen gelten dieselben Regeln wie beim Eintragen -- seit 1.9.202
    prüft sie _entscheiden() für jeden Weg (grund_gegen(), auch beim Genehmigen unter „Zeiten“)."""
    from .absence_requests import _entscheiden, load_request
    row = db.get(EmployeeAbsenceRequest, antrag_id)
    if row is None or row.absence_category != SCHLECHTWETTER:
        raise LookupError("Antrag nicht gefunden.")
    _entscheiden(db, row, decision=decision, reviewed_by_user_id=user_id, review_notes=notes)
    db.commit()
    return load_request(db, row.id)
