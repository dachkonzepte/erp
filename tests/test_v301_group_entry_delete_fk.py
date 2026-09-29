"""Version 1.7.11 -- ein per Gruppe gebuchter Eintrag ließ sich unter PostgreSQL nicht löschen:
TimeEntryGroupMember.time_entry_id ist ein Fremdschlüssel ohne Kaskade, delete_entry() entfernte
nur den TimeEntry. SQLite prüft Fremdschlüssel standardmäßig nicht -- deshalb schaltet dieser
Test die Prüfung ausdrücklich ein (PRAGMA foreign_keys=ON), erst NACH dem Aufbau der Testdaten,
weil der wiederverwendete Auftrags-Helfer ein Angebot nur per ID vortäuscht."""

from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Team, TeamEmployee, TimeEntry, TimeEntryGroup, TimeEntryGroupMember
from app.time_tracking import create_group_manual_entry, delete_entry
from tests.test_v264_field_time_tracking import _employee, _order


def _group_with_two_members():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    a, b = _employee(db, "FK-1", "Anna", "A"), _employee(db, "FK-2", "Ben", "B")
    order, _ = _order(db, "AUF-301-0001", "P-301-0001")
    team = Team(name="Kolonne FK"); db.add(team); db.flush()
    db.add_all([TeamEmployee(team_id=team.id, employee_id=a.id), TeamEmployee(team_id=team.id, employee_id=b.id)])
    db.commit()
    group = create_group_manual_entry(db, employee_ids=[a.id, b.id], team_id=team.id, actor_employee_id=a.id,
                                      is_admin=False, order_id=order.id, work_date=date.today(), hours=Decimal("4"))
    db.commit()
    db.execute(text("PRAGMA foreign_keys=ON"))
    assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
    return db, group.id, a.id, b.id


def _entry_of(db, group_id, employee_id):
    return db.scalar(select(TimeEntryGroupMember.time_entry_id).where(
        TimeEntryGroupMember.group_id == group_id, TimeEntryGroupMember.employee_id == employee_id))


def test_member_can_delete_own_group_booked_entry_with_foreign_keys_enforced():
    db, group_id, a_id, b_id = _group_with_two_members()
    delete_entry(db, _entry_of(db, group_id, b_id))
    assert db.get(TimeEntryGroup, group_id) is not None  # Gruppe bleibt, Anna ist noch drin
    assert db.scalars(select(TimeEntryGroupMember.employee_id).where(TimeEntryGroupMember.group_id == group_id)).all() == [a_id]


def test_deleting_the_last_member_entry_removes_the_group_header_too():
    db, group_id, a_id, b_id = _group_with_two_members()
    delete_entry(db, _entry_of(db, group_id, b_id))
    delete_entry(db, _entry_of(db, group_id, a_id))
    assert db.get(TimeEntryGroup, group_id) is None
    assert db.scalar(select(TimeEntry)) is None
