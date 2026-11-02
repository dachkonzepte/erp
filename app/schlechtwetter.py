"""Ausfalltag Schlechtwetter -- seit 1.9.170 (Lohn L1a, Punkt 5, Entscheidung Tobias E5).

Schlechtwetter ist eine Abwesenheit der Kategorie „schlechtwetter“ (EmployeeAbsence, „ein Weg“ über app/absence_requests.py), je Person und
Tag. Die Zuordnung (app/lohnarten.py) unterscheidet Winter (01.12.–31.03., Saison-Kurzarbeitergeld 8110 als Monatszeile) und Sommer.

    eintragen      Admin, Büro – Finanzen, Kolonnenführer und Vorarbeiter für jeden gewerblichen Mitarbeiter -- gilt sofort (genehmigt);
                   jede andere Person für sich selbst -- ein Antrag, den Kolonnenführer, Vorarbeiter oder Admin bestätigt
    abgelehnt      Samstag, Sonntag, gesetzlicher Feiertag, Tag ohne Sollzeit (app/sollzeit.py), nicht gewerblich -- 422 mit Grund
    Warnung        hat die Person an dem Tag schon Zeit gebucht oder laufen, 409 mit der Liste; gespeichert erst mit „trotzdem“
    Kolonnenführer TeamEmployee.is_crew_leader in einer aktiven Kolonne (seit 1.7.12); Vorarbeiter EmployeeRoleSettings.vorarbeiter
                   (seit 1.9.170 -- bis dahin war „Vorarbeiter“ nur Text: Funktion „Dachdecker Vorarbeiter“, Rolle in der Kolonne)

Die Rollenentscheidung trifft der Router (app/routers/schlechtwetter.py); hier stehen die Fakten und Regeln.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Employee, EmployeeAbsenceRequest, EmployeeRoleSettings, Team, TeamEmployee, TimeEntry

SCHLECHTWETTER = "schlechtwetter"
WOCHENTAG = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")


class SchlechtwetterWarnung(ValueError):
    """An dem Tag ist schon Zeit gebucht -- gespeichert erst mit „trotzdem“ (409)."""

    def __init__(self, warnungen: list[dict]):
        self.warnungen = warnungen
        super().__init__("An diesem Tag ist schon Zeit gebucht: " + "; ".join(w["text"] for w in warnungen) + ".")


class SchlechtwetterAbgelehnt(ValueError):
    """Mindestens eine Person kann an dem Tag keinen Ausfalltag haben (422) -- nichts gespeichert."""

    def __init__(self, liste: list[dict]):
        self.liste = liste
        super().__init__("Nicht eingetragen: " + "; ".join(x["text"] for x in liste) + ".")


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
    if soll(db, employee.id, tag) <= 0:
        return f"{_name(employee)}: am {tag:%d.%m.%Y} keine Sollzeit"
    return None


def warnungen(db: Session, employee_ids: list[int], tag: date) -> list[dict]:
    """Personen, die an dem Tag schon Zeit gebucht haben oder deren Zeit läuft -- mit den Stunden."""
    from .rounding import round_hours
    liste = []
    for eid in employee_ids:
        rows = db.scalars(select(TimeEntry).where(TimeEntry.employee_id == eid, TimeEntry.work_date == tag,
                                                   TimeEntry.status.in_(("booked", "running")))).all()
        if rows:
            stunden = round_hours(sum((r.hours or 0) for r in rows if r.status == "booked"))
            laeuft = any(r.status == "running" for r in rows)
            text = f"{_name(db.get(Employee, eid))} {str(stunden).replace('.', ',')} h gebucht" + (", eine Zeit läuft" if laeuft else "")
            liste.append({"employee_id": eid, "stunden": stunden, "laeuft": laeuft, "text": text})
    return liste


def eintragen(db: Session, *, employee_ids: list[int], tag: date, notes: str | None, gleich_genehmigt: bool, user_id: int | None,
              trotzdem: bool) -> list[EmployeeAbsenceRequest]:
    """Ein Ausfalltag für jede genannte Person, alles oder nichts in einem Commit. Abgelehnte Tage -> SchlechtwetterAbgelehnt (422),
    gebuchte Zeit ohne „trotzdem“ -> SchlechtwetterWarnung (409)."""
    from .absence_requests import _antrag_anlegen, _entscheiden, load_request
    ids = list(dict.fromkeys(int(i) for i in employee_ids))
    gruende = [g for g in (grund_gegen(db, db.get(Employee, eid), tag) for eid in ids) if g]
    if gruende:
        raise SchlechtwetterAbgelehnt([{"text": g} for g in gruende])
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


def offene_antraege(db: Session) -> list[EmployeeAbsenceRequest]:
    return list(db.scalars(select(EmployeeAbsenceRequest).where(EmployeeAbsenceRequest.absence_category == SCHLECHTWETTER,
                                                                 EmployeeAbsenceRequest.status == "pending")
                           .order_by(EmployeeAbsenceRequest.start_date, EmployeeAbsenceRequest.id)).all())


def entscheiden(db: Session, antrag_id: int, *, decision: str, user_id: int | None, notes: str | None) -> EmployeeAbsenceRequest:
    """Einen offenen Schlechtwetter-Antrag bestätigen oder ablehnen; beim Bestätigen gelten dieselben Regeln wie beim Eintragen."""
    from .absence_requests import _entscheiden, load_request
    row = db.get(EmployeeAbsenceRequest, antrag_id)
    if row is None or row.absence_category != SCHLECHTWETTER:
        raise LookupError("Antrag nicht gefunden.")
    if decision == "approved":
        grund = grund_gegen(db, db.get(Employee, row.employee_id), row.start_date)
        if grund:
            raise ValueError(grund)
    _entscheiden(db, row, decision=decision, reviewed_by_user_id=user_id, review_notes=notes)
    db.commit()
    return load_request(db, row.id)
