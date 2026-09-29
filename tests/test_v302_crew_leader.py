"""Version 1.7.12 -- Kolonnenführer: Kennzeichen TeamEmployee.is_crew_leader statt einer fünften
Rolle. Ein Monteur mit Kennzeichen darf für seine Kolonne gruppenbuchen (Start, Stopp,
Nachtrag) und seine eigenen Gruppenbuchungen bis zum Abschluss korrigieren oder löschen.

Enthält den geforderten Angriffstest: ein Monteur OHNE Kennzeichen kann nicht gruppenbuchen,
auch nicht per direktem Aufruf (bis 1.7.12 war das nur in der Oberfläche ausgeblendet); ein
Kolonnenführer bucht nicht für fremde Teams oder Nicht-Mitglieder und ändert keine fremden
Buchungen. Läuft mit ECHTEN, gespeicherten AppUser-Identitäten (nicht der transienten aus
router_test_client), weil die Nachvollziehbarkeit an AppUser.id hängt."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.database import get_db
from app.models import AppUser, Team, TeamEmployee, TimeEntry, TimeEntryGroup
from app.routers.resource_planning import router as teams_router
from app.routers.time_tracking import router as time_router
from app.time_backoffice import set_time_lock
from app.time_tracking import create_manual_entry
from tests.test_v264_field_time_tracking import _assign_via_team, _employee, _order

TODAY = date.today()


def _user(db, username, employee, role="field"):
    u = AppUser(username=username, display_name=username.capitalize(), role=role, active=True,
                employee_id=employee.id if employee else None, password_hash=hash_password("Passwort123"))
    db.add(u); db.commit()
    return u


def _client(db, user, *routers):
    app = FastAPI()
    for r in routers or (time_router,):
        app.include_router(r)
    user_id = user.id

    @app.middleware("http")
    async def _identity(request, call_next):
        request.state.erp_user = db.get(AppUser, user_id)
        return await call_next(request)

    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _team(db, name, members):
    team = Team(name=name); db.add(team); db.flush()
    for emp, leader in members:
        db.add(TeamEmployee(team_id=team.id, employee_id=emp.id, is_crew_leader=leader))
    db.commit()
    return team


@pytest.fixture
def world(threaded_db_session):
    db = threaded_db_session
    lea = _employee(db, "K-1", "Lea", "Leiterin")
    max_ = _employee(db, "K-2", "Max", "Mitglied")
    vera = _employee(db, "K-3", "Vera", "Vertretung")
    otto = _employee(db, "K-4", "Otto", "Aussen")
    pia = _employee(db, "K-5", "Pia", "Fremdleiterin")
    crew = _team(db, "Kolonne Nord", [(lea, True), (max_, False), (vera, True)])
    other = _team(db, "Kolonne Süd", [(pia, True), (otto, False), (lea, False)])
    order, _ = _order(db, "AUF-302-0001", "P-302-0001")
    for emp in (lea, vera, max_, pia):
        _assign_via_team(db, order, emp)
    users = {name: _user(db, name, emp) for name, emp in
             (("lea", lea), ("max", max_), ("vera", vera), ("otto", otto), ("pia", pia))}
    return {"db": db, "emp": {"lea": lea, "max": max_, "vera": vera, "otto": otto, "pia": pia},
            "crew": crew, "other": other, "order": order, "users": users}


def _manual(team_id, employee_ids, order_id, work_date=TODAY, hours="4"):
    return {"employee_ids": employee_ids, "team_id": team_id, "order_id": order_id,
            "work_date": work_date.isoformat(), "hours": hours}


def _as(world, name):
    return _client(world["db"], world["users"][name])


# --- Angriffstest: Monteur ohne Kennzeichen -------------------------------------------------


def test_member_without_flag_cannot_group_book_even_by_direct_call(world):
    e, crew, order = world["emp"], world["crew"], world["order"]
    client = _as(world, "max")
    ids = [e["max"].id, e["lea"].id]
    assert client.post("/api/time-entry-groups", json=_manual(crew.id, ids, order.id)).status_code == 403
    start = {k: v for k, v in _manual(crew.id, ids, order.id).items() if k not in ("work_date", "hours")}
    assert client.post("/api/time-entry-groups/start", json=start).status_code == 403
    assert client.post("/api/time-entry-groups", json=_manual(None, ids, order.id)).status_code == 403
    assert world["db"].query(TimeEntry).count() == 0


def test_flag_in_another_team_does_not_count(world):
    """Lea ist in Kolonne Süd nur Mitglied -- ihr Kennzeichen in Kolonne Nord gilt dort nicht."""
    e, other, order = world["emp"], world["other"], world["order"]
    resp = _as(world, "lea").post("/api/time-entry-groups", json=_manual(other.id, [e["lea"].id, e["otto"].id], order.id))
    assert resp.status_code == 403


# --- Angriffstest: Kolonnenführer -----------------------------------------------------------


def test_leader_cannot_book_for_a_foreign_team_or_non_members(world):
    e, crew, other, order = world["emp"], world["crew"], world["other"], world["order"]
    lea = _as(world, "lea")
    assert lea.post("/api/time-entry-groups", json=_manual(other.id, [e["lea"].id, e["pia"].id], order.id)).status_code == 403
    assert lea.post("/api/time-entry-groups", json=_manual(crew.id, [e["lea"].id, e["otto"].id], order.id)).status_code == 422
    assert world["db"].query(TimeEntry).count() == 0


def test_leader_books_for_the_crew_and_it_is_traceable_who_booked_for_whom(world):
    e, crew, order, db = world["emp"], world["crew"], world["order"], world["db"]
    resp = _as(world, "lea").post("/api/time-entry-groups", json=_manual(crew.id, [e["lea"].id, e["max"].id], order.id))
    assert resp.status_code == 200
    group = db.get(TimeEntryGroup, resp.json()["id"])
    assert group.initiated_by_employee_id == e["lea"].id
    assert group.created_by_user_id == world["users"]["lea"].id

    max_entries = _as(world, "max").get("/api/time-entries").json()
    assert len(max_entries) == 1
    assert max_entries[0]["booked_by_name"] == "Lea"
    assert max_entries[0]["booked_by_employee_id"] == e["lea"].id


def test_leader_sees_no_full_entries_of_colleagues(world):
    e, crew, order = world["emp"], world["crew"], world["order"]
    lea = _as(world, "lea")
    body = _manual(crew.id, [e["lea"].id, e["max"].id], order.id)
    body["notes"] = "Kolonnennotiz"
    data = lea.post("/api/time-entry-groups", json=body).json()
    for member in data["member_entries"]:
        assert set(member) == {"employee_id", "employee_name", "hours", "status"}
    own = lea.get("/api/time-entries").json()
    assert {x["employee_id"] for x in own} == {e["lea"].id}


def test_two_leaders_per_team_both_may_book(world):
    e, crew, order = world["emp"], world["crew"], world["order"]
    resp = _as(world, "vera").post("/api/time-entry-groups", json=_manual(crew.id, [e["vera"].id, e["max"].id], order.id))
    assert resp.status_code == 200


def test_leader_timer_start_and_stop_member_cannot_stop_the_group(world):
    e, crew, order = world["emp"], world["crew"], world["order"]
    lea, max_ = _as(world, "lea"), _as(world, "max")
    start = {"employee_ids": [e["lea"].id, e["max"].id], "team_id": crew.id, "order_id": order.id,
             "started_at": datetime.combine(TODAY, datetime.min.time()).replace(hour=7).isoformat()}
    group_id = lea.post("/api/time-entry-groups/start", json=start).json()["id"]
    end = {"ended_at": datetime.combine(TODAY, datetime.min.time()).replace(hour=11).isoformat()}
    assert max_.post(f"/api/time-entry-groups/{group_id}/stop", json=end).status_code == 403
    assert lea.post(f"/api/time-entry-groups/{group_id}/stop", json=end).status_code == 200


def test_leader_may_correct_and_delete_own_group_others_may_not(world):
    e, crew, order, db = world["emp"], world["crew"], world["order"], world["db"]
    lea = _as(world, "lea")
    group_id = lea.post("/api/time-entry-groups", json=_manual(crew.id, [e["lea"].id, e["max"].id], order.id)).json()["id"]
    change = {k: v for k, v in _manual(crew.id, [], order.id, hours="6").items() if k not in ("employee_ids", "team_id")}

    for intruder in ("max", "vera", "pia"):  # Mitglied, zweite Kolonnenführerin derselben Kolonne, fremde Kolonnenführerin
        client = _as(world, intruder)
        assert client.put(f"/api/time-entry-groups/{group_id}", json=change).status_code == 403, intruder
        assert client.delete(f"/api/time-entry-groups/{group_id}").status_code == 403, intruder

    assert lea.put(f"/api/time-entry-groups/{group_id}", json=change).status_code == 200
    assert {str(x.hours) for x in db.query(TimeEntry).all()} == {"6.0000"}
    assert lea.delete(f"/api/time-entry-groups/{group_id}").status_code == 200
    assert db.query(TimeEntry).count() == 0 and db.get(TimeEntryGroup, group_id) is None


def test_leader_cannot_touch_single_entries_of_colleagues(world):
    e, crew, order, db = world["emp"], world["crew"], world["order"], world["db"]
    _as(world, "lea").post("/api/time-entry-groups", json=_manual(crew.id, [e["lea"].id, e["max"].id], order.id))
    max_entry = db.query(TimeEntry).filter(TimeEntry.employee_id == e["max"].id).one()
    body = {"employee_id": e["max"].id, "order_id": order.id, "work_date": TODAY.isoformat(), "hours": "1"}
    lea = _as(world, "lea")
    assert lea.put(f"/api/time-entries/{max_entry.id}", json=body).status_code == 403
    assert lea.delete(f"/api/time-entries/{max_entry.id}").status_code == 403


def test_correction_is_blocked_after_the_period_is_closed(world):
    e, crew, order, db = world["emp"], world["crew"], world["order"], world["db"]
    lea = _as(world, "lea")
    day = TODAY - timedelta(days=5)
    group_id = lea.post("/api/time-entry-groups", json=_manual(crew.id, [e["lea"].id, e["max"].id], order.id, work_date=day)).json()["id"]
    set_time_lock(db, day, user_id=None)
    change = {k: v for k, v in _manual(crew.id, [], order.id, work_date=TODAY, hours="6").items() if k not in ("employee_ids", "team_id")}
    assert lea.put(f"/api/time-entry-groups/{group_id}", json=change).status_code == 403
    assert lea.delete(f"/api/time-entry-groups/{group_id}").status_code == 403
    assert lea.post("/api/time-entry-groups", json=_manual(crew.id, [e["lea"].id, e["max"].id], order.id, work_date=day)).status_code == 403


def test_removing_the_flag_removes_the_rights(world):
    e, crew, order, db = world["emp"], world["crew"], world["order"], world["db"]
    lea = _as(world, "lea")
    group_id = lea.post("/api/time-entry-groups", json=_manual(crew.id, [e["lea"].id, e["max"].id], order.id)).json()["id"]
    link = db.query(TeamEmployee).filter_by(team_id=crew.id, employee_id=e["lea"].id).one()
    link.is_crew_leader = False; db.commit()
    assert lea.post("/api/time-entry-groups", json=_manual(crew.id, [e["lea"].id, e["max"].id], order.id)).status_code == 403
    assert lea.delete(f"/api/time-entry-groups/{group_id}").status_code == 403
    assert lea.get("/api/time-tracking/crews").json() == []


def test_crews_endpoint_lists_only_own_active_crews(world):
    db, crew = world["db"], world["crew"]
    data = _as(world, "lea").get("/api/time-tracking/crews").json()
    assert [c["name"] for c in data] == ["Kolonne Nord"]
    assert {m["name"] for m in data[0]["members"]} == {"Lea Leiterin", "Max Mitglied", "Vera Vertretung"}
    assert _as(world, "max").get("/api/time-tracking/crews").json() == []
    crew.active = False; db.commit()
    assert _as(world, "lea").get("/api/time-tracking/crews").json() == []


def test_mine_lists_own_group_bookings_with_names_only(world):
    e, crew, order = world["emp"], world["crew"], world["order"]
    lea = _as(world, "lea")
    lea.post("/api/time-entry-groups", json=_manual(crew.id, [e["lea"].id, e["max"].id], order.id))
    mine = lea.get("/api/time-entry-groups/mine").json()
    assert len(mine) == 1 and mine[0]["team_name"] == "Kolonne Nord"
    assert {m["name"] for m in mine[0]["members"]} == {"Lea Leiterin", "Max Mitglied"}
    assert _as(world, "max").get("/api/time-entry-groups/mine").json() == []


def test_team_form_round_trip_keeps_the_flag_and_field_cannot_set_it(world):
    db, crew, e = world["db"], world["crew"], world["emp"]
    office = _client(db, _user(db, "buero", None, role="buero_auftrag"), teams_router)
    payload = {"name": "Kolonne Nord", "active": True, "employees": [
        {"employee_id": e["lea"].id, "role": "Vorarbeiterin", "is_crew_leader": True},
        {"employee_id": e["max"].id, "role": None, "is_crew_leader": False}]}
    assert office.put(f"/api/teams/{crew.id}", json=payload).status_code == 200
    got = {m["employee_id"]: m for m in office.get(f"/api/teams/{crew.id}").json()["employees"]}
    assert got[e["lea"].id]["is_crew_leader"] is True and got[e["max"].id]["is_crew_leader"] is False
    assert _client(db, world["users"]["max"], teams_router).put(f"/api/teams/{crew.id}", json=payload).status_code == 403


# --- /api/time-entries/summary: die Kolonnenführerin summiert nur eigene Buchungen -----------


def _summary(client, query=""):
    resp = client.get(f"/api/time-entries/summary?{query}")
    assert resp.status_code == 200, (query, resp.text)
    return {k: Decimal(str(v)) if k.endswith("_hours") else v for k, v in resp.json().items()}


def test_crew_leader_summary_and_list_contain_only_own_bookings(world):
    """Seit Runde 0e dauerhaft (vorher nur mit der transienten Identität aus router_test_client
    und einem Monteur ohne Kolonne geprüft, tests/test_v313_*): Lea ist echte Kolonnenführerin mit
    gespeichertem AppUser. Sie bucht für sich und Max (je 4 Std.), Vera für sich und Max (je 3),
    Pia in Kolonne Süd für sich und Lea (je 1), Max trägt 2 Std. selbst nach. Summen, Liste und
    Gesamtzahl zeigen Lea nur ihre eigenen zwei Buchungen (5 Std., eine davon von Pia gebucht) --
    mit Max, Vera oder Pia im Filter, mit Auftrag oder Projekt. Gegenstück: das Büro sieht alle."""
    e, crew, other, order, db = world["emp"], world["crew"], world["other"], world["order"], world["db"]
    for booker, team, members, hours in (("lea", crew, ("lea", "max"), "4"), ("vera", crew, ("vera", "max"), "3"),
                                         ("pia", other, ("pia", "lea"), "1")):
        resp = _as(world, booker).post("/api/time-entry-groups", json=_manual(team.id, [e[m].id for m in members], order.id, hours=hours))
        assert resp.status_code == 200, (booker, resp.text)
    create_manual_entry(db, employee_id=e["max"].id, order_id=order.id, work_date=TODAY, hours=Decimal("2"))

    own = {"entry_count": 2, "booked_count": 2, "employee_count": 1, "total_hours": Decimal("5.00"),
           "productive_hours": Decimal("5.00"), "travel_hours": Decimal("0.00")}
    lea = _as(world, "lea")
    for query in ("", f"order_id={order.id}", f"project_id={order.project_id}", f"employee_id={e['max'].id}",
                  f"employee_id={e['vera'].id}&order_id={order.id}", f"employee_id={e['pia'].id}",
                  f"start_date={TODAY.isoformat()}&end_date={TODAY.isoformat()}"):
        assert _summary(lea, query) == own, query
        resp = lea.get(f"/api/time-entries?{query}")
        assert resp.status_code == 200 and resp.headers["X-Total-Count"] == "2", (query, resp.headers.get("X-Total-Count"))
        assert {x["employee_id"] for x in resp.json()} == {e["lea"].id}, query

    office = _client(db, _user(db, "buero", None, role="buero_auftrag"))
    assert _summary(office, f"order_id={order.id}") == {
        "entry_count": 7, "booked_count": 7, "employee_count": 4, "total_hours": Decimal("18.00"),
        "productive_hours": Decimal("18.00"), "travel_hours": Decimal("0.00")}
