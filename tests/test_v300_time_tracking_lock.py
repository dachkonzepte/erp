"""Version 1.7.10 -- Abschluss der Zeiterfassung (Sperrdatum). Buchungen mit work_date <=
locked_until legt/ändert/stoppt/löscht nur noch ein Admin -- auch die eigenen eines Monteurs.
Vorrücken darf das Backoffice (buero_auftrag+), zurücknehmen/aufheben nur der Admin. Das
allgemeine Einstellungsformular (voller PUT) darf den Abschluss nie überschreiben."""

from datetime import date, datetime, timedelta
from decimal import Decimal

from app.routers.time_backoffice import router as backoffice_router
from app.routers.time_tracking import router as time_router
from app.time_backoffice import set_time_lock
from app.time_tracking import create_manual_entry, start_timer
from tests.test_v264_field_time_tracking import _assign_via_team, _employee, _order

TODAY = date.today()
LOCK = TODAY - timedelta(days=10)
LOCKED_DAY = LOCK - timedelta(days=2)
OPEN_DAY = TODAY - timedelta(days=1)


def _setup(db):
    me = _employee(db, "T-300-1", "Lea", "Lock")
    order, _ = _order(db, "AUF-300-0001", "P-300-0001")
    _assign_via_team(db, order, me)
    locked_entry = create_manual_entry(db, employee_id=me.id, order_id=order.id, work_date=LOCKED_DAY, hours=Decimal("3"))
    open_entry = create_manual_entry(db, employee_id=me.id, order_id=order.id, work_date=OPEN_DAY, hours=Decimal("3"))
    return me, order, locked_entry, open_entry


def _entry(employee_id, order_id, work_date):
    return {"employee_id": employee_id, "order_id": order_id, "work_date": work_date.isoformat(), "hours": "2"}


def test_backoffice_may_advance_but_only_admin_may_reopen_or_clear(threaded_db_session, router_test_client):
    db = threaded_db_session
    office = router_test_client(db, backoffice_router, role="buero_auftrag")
    admin = router_test_client(db, backoffice_router, role="admin")

    assert office.put("/api/time-backoffice/lock", json={"locked_until": LOCK.isoformat()}).status_code == 200
    later = (LOCK + timedelta(days=3)).isoformat()
    assert office.put("/api/time-backoffice/lock", json={"locked_until": later}).status_code == 200
    assert office.put("/api/time-backoffice/lock", json={"locked_until": LOCK.isoformat()}).status_code == 403
    assert office.put("/api/time-backoffice/lock", json={"locked_until": None}).status_code == 403
    assert admin.put("/api/time-backoffice/lock", json={"locked_until": LOCK.isoformat()}).status_code == 200
    assert admin.get("/api/time-backoffice/settings").json()["locked_until"] == LOCK.isoformat()
    assert admin.put("/api/time-backoffice/lock", json={"locked_until": None}).json()["locked_until"] is None
    assert router_test_client(db, backoffice_router, role="field").put("/api/time-backoffice/lock", json={"locked_until": LOCK.isoformat()}).status_code == 403


def test_saving_the_general_settings_form_never_touches_the_lock(threaded_db_session, router_test_client):
    db = threaded_db_session
    admin = router_test_client(db, backoffice_router, role="admin")
    admin.put("/api/time-backoffice/lock", json={"locked_until": LOCK.isoformat()})
    form = admin.get("/api/time-backoffice/settings").json()
    form.update({"locked_until": None, "rounding_minutes": 15})
    assert admin.put("/api/time-backoffice/settings", json=form).status_code == 200
    after = admin.get("/api/time-backoffice/settings").json()
    assert after["locked_until"] == LOCK.isoformat()
    assert after["rounding_minutes"] == 15


def test_field_cannot_create_change_or_delete_in_the_locked_period(threaded_db_session, router_test_client):
    db = threaded_db_session
    me, order, locked_entry, open_entry = _setup(db)
    set_time_lock(db, LOCK, user_id=None)
    field = router_test_client(db, time_router, role="field", employee_id=me.id)

    assert field.post("/api/time-entries", json=_entry(me.id, order.id, LOCKED_DAY)).status_code == 403
    assert field.post("/api/time-entries", json=_entry(me.id, order.id, LOCK)).status_code == 403  # einschließlich
    assert field.post("/api/time-entries", json=_entry(me.id, order.id, OPEN_DAY)).status_code == 200
    assert field.put(f"/api/time-entries/{locked_entry.id}", json=_entry(me.id, order.id, OPEN_DAY)).status_code == 403
    assert field.put(f"/api/time-entries/{open_entry.id}", json=_entry(me.id, order.id, LOCKED_DAY)).status_code == 403
    assert field.put(f"/api/time-entries/{open_entry.id}", json=_entry(me.id, order.id, OPEN_DAY)).status_code == 200
    assert field.delete(f"/api/time-entries/{locked_entry.id}").status_code == 403
    assert field.delete(f"/api/time-entries/{open_entry.id}").status_code == 200


def test_field_cannot_stop_a_timer_that_runs_in_the_locked_period(threaded_db_session, router_test_client):
    db = threaded_db_session
    me, order, _, _ = _setup(db)
    running = start_timer(db, employee_id=me.id, order_id=order.id, started_at=datetime.combine(LOCKED_DAY, datetime.min.time()).replace(hour=7))
    set_time_lock(db, LOCK, user_id=None)
    field = router_test_client(db, time_router, role="field", employee_id=me.id)
    assert field.post(f"/api/time-entries/{running.id}/stop", json={}).status_code == 403
    admin = router_test_client(db, time_router, role="admin")
    assert admin.post(f"/api/time-entries/{running.id}/stop", json={"ended_at": datetime.combine(LOCKED_DAY, datetime.min.time()).replace(hour=15).isoformat()}).status_code == 200


def test_timer_start_is_blocked_when_today_is_already_locked(threaded_db_session, router_test_client):
    db = threaded_db_session
    me, order, _, _ = _setup(db)
    set_time_lock(db, TODAY, user_id=None)
    field = router_test_client(db, time_router, role="field", employee_id=me.id)
    assert field.post("/api/time-entries/start", json={"employee_id": me.id, "order_id": order.id}).status_code == 403


def test_admin_may_still_change_the_locked_period(threaded_db_session, router_test_client):
    db = threaded_db_session
    me, order, locked_entry, _ = _setup(db)
    set_time_lock(db, LOCK, user_id=None)
    admin = router_test_client(db, time_router, role="admin")
    assert admin.post("/api/time-entries", json=_entry(me.id, order.id, LOCKED_DAY)).status_code == 200
    assert admin.put(f"/api/time-entries/{locked_entry.id}", json=_entry(me.id, order.id, LOCKED_DAY)).status_code == 200
    assert admin.delete(f"/api/time-entries/{locked_entry.id}").status_code == 200


def test_field_settings_expose_the_lock_for_the_mobile_view(threaded_db_session, router_test_client):
    db = threaded_db_session
    me, _, _, _ = _setup(db)
    set_time_lock(db, LOCK, user_id=None)
    field = router_test_client(db, time_router, role="field", employee_id=me.id)
    assert field.get("/api/time-tracking/settings").json()["locked_until"] == LOCK.isoformat()
