"""Version 1.7.9 -- ein Monteur bucht nur noch auf Aufträge, die field_may_access_order() ihm
zuordnet (Planungsbezug oder eigener Bericht, ohne Zeitfenster). Vorher nahm der Server für
`field` jede existierende Auftrags-ID an -- die Oberfläche bot zwar nur die eigenen Aufträge an,
ein direkter Aufruf aber nicht, und die Antwort lieferte Auftragsnummer/Projektname zurück.
Gilt für Einzelbuchung, Timer-Start, Änderung und Gruppenbuchung; Büro/Admin unverändert."""

from datetime import date

from app.routers.time_tracking import router as time_router
from tests.test_v264_field_time_tracking import _assign_via_team, _employee, _order


def _setup(db):
    me = _employee(db, "T-299-1", "Mia", "Monteur")
    mine, _ = _order(db, "AUF-299-0001", "P-299-0001")
    foreign, _ = _order(db, "AUF-299-0002", "P-299-0002")
    _assign_via_team(db, mine, me)
    return me, mine, foreign


def _manual(employee_id, order_id):
    return {"employee_id": employee_id, "order_id": order_id, "work_date": date.today().isoformat(), "hours": "2"}


def test_field_can_book_own_order_but_not_a_foreign_or_unknown_one(threaded_db_session, router_test_client):
    db = threaded_db_session
    me, mine, foreign = _setup(db)
    client = router_test_client(db, time_router, role="field", employee_id=me.id)

    assert client.post("/api/time-entries", json=_manual(me.id, mine.id)).status_code == 200
    denied = client.post("/api/time-entries", json=_manual(me.id, foreign.id))
    assert denied.status_code == 403
    assert "AUF-299-0002" not in denied.text and "P-299-0002" not in denied.text
    assert client.post("/api/time-entries", json=_manual(me.id, 999_999)).status_code == 403  # nicht 404: keine Auftragsnummern erraten


def test_field_cannot_start_a_timer_on_a_foreign_order(threaded_db_session, router_test_client):
    db = threaded_db_session
    me, mine, foreign = _setup(db)
    client = router_test_client(db, time_router, role="field", employee_id=me.id)
    assert client.post("/api/time-entries/start", json={"employee_id": me.id, "order_id": foreign.id}).status_code == 403
    assert client.post("/api/time-entries/start", json={"employee_id": me.id, "order_id": mine.id}).status_code == 200


def test_field_cannot_move_an_own_entry_onto_a_foreign_order(threaded_db_session, router_test_client):
    db = threaded_db_session
    me, mine, foreign = _setup(db)
    client = router_test_client(db, time_router, role="field", employee_id=me.id)
    entry_id = client.post("/api/time-entries", json=_manual(me.id, mine.id)).json()["id"]
    assert client.put(f"/api/time-entries/{entry_id}", json=_manual(me.id, foreign.id)).status_code == 403
    assert client.put(f"/api/time-entries/{entry_id}", json=_manual(me.id, mine.id)).status_code == 200


def test_field_group_booking_on_a_foreign_order_is_rejected(threaded_db_session, router_test_client):
    db = threaded_db_session
    me, mine, foreign = _setup(db)
    client = router_test_client(db, time_router, role="field", employee_id=me.id)
    payload = {"employee_ids": [me.id], "team_id": None, "order_id": foreign.id,
               "work_date": date.today().isoformat(), "hours": "2"}
    assert client.post("/api/time-entry-groups", json=payload).status_code == 403
    assert client.post("/api/time-entry-groups/start", json={k: v for k, v in payload.items() if k not in ("work_date", "hours")}).status_code == 403


def test_admin_still_books_on_any_order(threaded_db_session, router_test_client):
    db = threaded_db_session
    me, _, foreign = _setup(db)
    client = router_test_client(db, time_router, role="admin")
    assert client.post("/api/time-entries", json=_manual(me.id, foreign.id)).status_code == 200
