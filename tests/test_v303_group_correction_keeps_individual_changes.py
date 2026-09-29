"""Version 1.7.13 -- eine Gruppenkorrektur (oder -löschung) des Kolonnenführers lässt
Mitgliedsbuchungen unangetastet, die nach der Gruppenbuchung einzeln geändert oder vorzeitig
einzeln gestoppt wurden. Lohnrelevant: vorher stand ein Mitglied, das sich selbst von 7-16 auf
7-14 korrigiert hatte, nach einer späteren Gruppenkorrektur wieder bis 16 Uhr in der Abrechnung.

Merkmal ist ein ausdrücklicher Merker (TimeEntryGroupMember.individually_changed_at), kein
Wertevergleich -- bei Timer-Gruppen haben Mitglieder durch eigene Pausen ohnehin
unterschiedliche Stunden -- und kein updated_at-Vergleich (onupdate-Fallstrick)."""

import importlib.util
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import TimeEntry, TimeEntryGroup, TimeEntryGroupMember
from tests.test_v302_crew_leader import _as, _client, _manual, _user, world  # noqa: F401 -- world ist eine Fixture

TODAY = date.today()


def _at(hour, minute=0):
    return datetime.combine(TODAY, datetime.min.time()).replace(hour=hour, minute=minute).isoformat()


def _run_group_7_to_16(world, members):
    e, crew, order = world["emp"], world["crew"], world["order"]
    lea = _as(world, "lea")
    start = {"employee_ids": [e[m].id for m in members], "team_id": crew.id, "order_id": order.id, "started_at": _at(7)}
    group_id = lea.post("/api/time-entry-groups/start", json=start).json()["id"]
    return lea, group_id


def _entry(world, name):
    return world["db"].query(TimeEntry).filter(TimeEntry.employee_id == world["emp"][name].id).one()


def _correction(world, hours):
    return {"order_id": world["order"].id, "work_date": TODAY.isoformat(), "hours": hours, "break_minutes": 0}


def test_the_reported_example_member_corrected_to_14_stays_after_leader_moves_start_to_730(world):
    """Gruppe 7-16, Max korrigiert sich selbst auf 7-14 (7 h), danach korrigiert Lea die Gruppe
    auf Beginn 7:30 (8,5 h). Max muss bei 7 h bleiben, Lea bekommt 8,5 h, und Lea sieht, bei
    wem die Korrektur nicht gegriffen hat."""
    db, e, order = world["db"], world["emp"], world["order"]
    lea, group_id = _run_group_7_to_16(world, ["lea", "max"])
    assert lea.post(f"/api/time-entry-groups/{group_id}/stop", json={"ended_at": _at(16), "break_minutes": 0}).status_code == 200

    max_entry = _entry(world, "max")
    own = {"employee_id": e["max"].id, "order_id": order.id, "work_date": TODAY.isoformat(), "hours": "7", "break_minutes": 0}
    assert _as(world, "max").put(f"/api/time-entries/{max_entry.id}", json=own).status_code == 200

    resp = lea.put(f"/api/time-entry-groups/{group_id}", json=_correction(world, "8.5"))
    assert resp.status_code == 200
    assert resp.json()["skipped_members"] == ["Max Mitglied"]
    db.expire_all()
    assert _entry(world, "max").hours == Decimal("7")
    assert _entry(world, "lea").hours == Decimal("8.5")

    mine = lea.get("/api/time-entry-groups/mine").json()[0]
    assert {m["name"]: m["individually_changed"] for m in mine["members"]} == {"Lea Leiterin": False, "Max Mitglied": True}


def test_member_who_stopped_early_is_left_alone_by_the_group_correction(world):
    db = world["db"]
    lea, group_id = _run_group_7_to_16(world, ["lea", "max", "vera"])
    max_entry = _entry(world, "max")
    assert _as(world, "max").post(f"/api/time-entries/{max_entry.id}/stop", json={"ended_at": _at(14), "break_minutes": 0}).status_code == 200
    assert db.get(TimeEntryGroup, group_id).status == "running"  # die Gruppe läuft für die anderen weiter
    lea.post(f"/api/time-entry-groups/{group_id}/stop", json={"ended_at": _at(16), "break_minutes": 0})
    max_hours = _entry(world, "max").hours

    resp = lea.put(f"/api/time-entry-groups/{group_id}", json=_correction(world, "8.5"))
    assert resp.json()["skipped_members"] == ["Max Mitglied"]
    db.expire_all()
    assert _entry(world, "max").hours == max_hours
    assert _entry(world, "vera").hours == Decimal("8.5")  # nicht einzeln geändert -> korrigiert


def test_a_group_correction_itself_does_not_mark_anyone(world):
    db = world["db"]
    lea = _as(world, "lea")
    group_id = lea.post("/api/time-entry-groups", json=_manual(world["crew"].id, [world["emp"]["lea"].id, world["emp"]["max"].id], world["order"].id)).json()["id"]
    assert lea.put(f"/api/time-entry-groups/{group_id}", json=_correction(world, "6")).json()["skipped_members"] == []
    assert lea.put(f"/api/time-entry-groups/{group_id}", json=_correction(world, "5")).json()["skipped_members"] == []
    db.expire_all()
    assert {x.hours for x in db.query(TimeEntry).all()} == {Decimal("5")}


def test_an_individual_admin_correction_is_protected_too(world):
    db, e, order = world["db"], world["emp"], world["order"]
    lea = _as(world, "lea")
    group_id = lea.post("/api/time-entry-groups", json=_manual(world["crew"].id, [e["lea"].id, e["max"].id], order.id)).json()["id"]
    admin = _client(db, _user(db, "chef", None, role="admin"))
    body = {"employee_id": e["max"].id, "order_id": order.id, "work_date": TODAY.isoformat(), "hours": "3", "break_minutes": 0}
    assert admin.put(f"/api/time-entries/{_entry(world, 'max').id}", json=body).status_code == 200
    assert lea.put(f"/api/time-entry-groups/{group_id}", json=_correction(world, "6")).json()["skipped_members"] == ["Max Mitglied"]


def test_deleting_the_group_keeps_the_individually_changed_entry_as_a_standalone_booking(world):
    db, e, order = world["db"], world["emp"], world["order"]
    lea = _as(world, "lea")
    group_id = lea.post("/api/time-entry-groups", json=_manual(world["crew"].id, [e["lea"].id, e["max"].id], order.id)).json()["id"]
    max_client = _as(world, "max")
    max_id = _entry(world, "max").id
    body = {"employee_id": e["max"].id, "order_id": order.id, "work_date": TODAY.isoformat(), "hours": "7", "break_minutes": 0}
    max_client.put(f"/api/time-entries/{max_id}", json=body)

    resp = lea.delete(f"/api/time-entry-groups/{group_id}")
    assert resp.json() == {"deleted": True, "kept_members": ["Max Mitglied"]}
    db.expire_all()
    assert db.get(TimeEntryGroup, group_id) is None
    assert db.query(TimeEntry).filter(TimeEntry.employee_id == e["lea"].id).count() == 0
    kept = db.get(TimeEntry, max_id)
    assert kept is not None and kept.hours == Decimal("7")
    assert db.query(TimeEntryGroupMember).count() == 0
    assert max_client.delete(f"/api/time-entries/{max_id}").status_code == 200  # jetzt eine ganz normale eigene Buchung


def _load_migration():
    path = next(Path(__file__).resolve().parent.parent.joinpath("alembic", "versions").glob("*group_member_individually_changed.py"))
    spec = importlib.util.spec_from_file_location("mig_individually_changed", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_backfill_marks_only_recognisably_changed_bestand_members():
    """Nachmarkierung für Bestandsgruppen: Datum/Auftrag/Zeitart weicht ab (immer), Stunden weichen
    ab (nur bei manuellen Gruppen -- bei Timer-Gruppen sind abweichende Stunden durch Pausen normal)."""
    from app.models import Team
    from app.time_tracking import create_group_manual_entry
    from tests.test_v264_field_time_tracking import _employee, _order

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    a, b, c = (_employee(db, f"MB-{i}", n, "X") for i, n in enumerate(("Anna", "Ben", "Cem")))
    order, _ = _order(db, "AUF-303-0001", "P-303-0001")
    team = Team(name="T"); db.add(team); db.commit()
    manual = create_group_manual_entry(db, employee_ids=[a.id, b.id, c.id], team_id=None, actor_employee_id=None, is_admin=True,
                                       order_id=order.id, work_date=TODAY, hours=Decimal("8"))
    timer = create_group_manual_entry(db, employee_ids=[a.id, b.id], team_id=None, actor_employee_id=None, is_admin=True,
                                      order_id=order.id, work_date=TODAY, hours=Decimal("8"))
    db.query(TimeEntryGroup).filter_by(id=timer.id).update({"mode": "timer"}); db.commit()

    def entry(group, emp):
        link = db.query(TimeEntryGroupMember).filter_by(group_id=group.id, employee_id=emp.id).one()
        return db.get(TimeEntry, link.time_entry_id)

    entry(manual, b).hours = Decimal("7")               # manuelle Gruppe, Stunden weichen ab -> markieren
    entry(manual, c).work_date = date(2020, 1, 1)       # Datum weicht ab -> markieren
    entry(timer, a).hours = Decimal("7.25")             # Timer-Gruppe, nur Stunden -> NICHT markieren
    entry(timer, b).entry_type = "travel"               # Timer-Gruppe, Zeitart weicht ab -> markieren
    db.commit()

    db.execute(text(_load_migration().BACKFILL_SQL)); db.commit()
    marked = {(m.group_id, m.employee_id) for m in db.query(TimeEntryGroupMember).all() if m.individually_changed_at is not None}
    assert marked == {(manual.id, b.id), (manual.id, c.id), (timer.id, b.id)}
