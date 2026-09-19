"""Krankheitssichtbarkeit: buero_auftrag sieht bei jeder Abwesenheit -- egal wer/wann sie
angelegt wurde, auch die eigene soeben erstellte -- ausschließlich "abwesend" mit Zeitraum, nie
Art (absence_type/absence_category) oder Grund (notes). buero_finanzen/admin sehen alles
unverändert. Ein Monteur (field) bleibt von jedem dieser Endpunkte vollständig ausgesperrt
(unverändert seit "Rechtekonzept").

"Einmal eintragen, nie wieder lesen" (Betreiberentscheidung): buero_auftrag darf beim Anlegen
weiterhin die echte Art eintippen, das Ergebnis der eigenen Anfrage zeigt sie danach aber
ebenso wenig wie jede spätere Abfrage.

Angriffstest: rekursiver Schlüssel-Scan (Fehlerklasse purchase_price) über jeden Endpunkt, der
Abwesenheiten liefert -- GET/POST/PUT /api/planning/absences, GET /api/planning (Board),
POST /api/planning/suggestion, GET /api/audit-logs."""

import json

import pytest

from app.models import Employee, OrderItemCalculationSnapshot, Team, TeamEmployee
from app.routers.audit import router as audit_router
from app.routers.planning import router as planning_router
from tests.test_v133_invoices import make_order_with_item

ALL_ROLES = ("field", "buero_auftrag", "buero_finanzen", "admin")
SENSITIVE_KEYS = {"absence_type", "absence_category", "notes"}


def _recursive_keys(value, keys=None):
    if keys is None:
        keys = set()
    if isinstance(value, dict):
        for k, v in value.items():
            keys.add(k)
            _recursive_keys(v, keys)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _recursive_keys(item, keys)
    elif isinstance(value, str):
        s = value.strip()
        if s[:1] in "{[":
            try:
                parsed = json.loads(s)
            except (TypeError, ValueError):
                return keys
            _recursive_keys(parsed, keys)
    return keys


def make_employee(db, *, number="M-1"):
    emp = Employee(
        employee_number=number, first_name="Erika", last_name="Krank",
        employee_group="gewerblich", hourly_wage="20", weekly_hours="40", active=True,
    )
    db.add(emp)
    db.commit()
    return emp


def make_team_with_employee(db, emp, *, second_employee=False):
    team = Team(team_number="K-1", name="Kolonne 1", active=True)
    db.add(team)
    db.flush()
    db.add(TeamEmployee(team_id=team.id, employee_id=emp.id, role="Geselle"))
    if second_employee:
        colleague = make_employee(db, number="M-2")
        db.add(TeamEmployee(team_id=team.id, employee_id=colleague.id, role="Geselle"))
    db.commit()
    return team


# --- CRUD: buero_auftrag anlegen/lesen, "einmal eintragen, nie wieder lesen" ---

def test_buero_auftrag_create_response_hides_category_type_and_notes(threaded_db_session, router_test_client):
    db = threaded_db_session
    emp = make_employee(db)
    client = router_test_client(db, planning_router, role="buero_auftrag")
    resp = client.post("/api/planning/absences", json={
        "employee_id": emp.id, "absence_type": "Krankheit", "absence_category": "krankheit",
        "start_date": "2026-09-01", "end_date": "2026-09-03", "notes": "Grippe",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert not (_recursive_keys(body) & SENSITIVE_KEYS), body
    assert body["employee_id"] == emp.id
    assert body["start_date"] == "2026-09-01" and body["end_date"] == "2026-09-03"


def test_buero_finanzen_create_response_shows_everything(threaded_db_session, router_test_client):
    db = threaded_db_session
    emp = make_employee(db)
    client = router_test_client(db, planning_router, role="buero_finanzen")
    resp = client.post("/api/planning/absences", json={
        "employee_id": emp.id, "absence_type": "Krankheit", "absence_category": "krankheit",
        "start_date": "2026-09-01", "end_date": "2026-09-03", "notes": "Grippe",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["absence_category"] == "krankheit"
    assert body["absence_type"] == "Krankheit"
    assert body["notes"] == "Grippe"


def test_buero_auftrag_list_hides_a_colleague_entry_created_by_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    emp = make_employee(db)
    finanzen_client = router_test_client(db, planning_router, role="buero_finanzen")
    created = finanzen_client.post("/api/planning/absences", json={
        "employee_id": emp.id, "absence_type": "Krankheit", "absence_category": "krankheit",
        "start_date": "2026-09-01", "end_date": "2026-09-03", "notes": "Grippe",
    }).json()

    auftrag_client = router_test_client(db, planning_router, role="buero_auftrag")
    resp = auftrag_client.get("/api/planning/absences")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert not (_recursive_keys(rows) & SENSITIVE_KEYS), rows
    assert rows[0]["id"] == created["id"]
    assert rows[0]["employee_name"]

    finanzen_resp = finanzen_client.get("/api/planning/absences")
    finanzen_rows = finanzen_resp.json()
    assert finanzen_rows[0]["absence_category"] == "krankheit"


# --- PUT: exclude_unset schuetzt vor Blanket-Overwrite ---

def test_partial_update_by_buero_auftrag_leaves_category_and_notes_untouched(threaded_db_session, router_test_client):
    db = threaded_db_session
    emp = make_employee(db)
    finanzen_client = router_test_client(db, planning_router, role="buero_finanzen")
    created = finanzen_client.post("/api/planning/absences", json={
        "employee_id": emp.id, "absence_type": "Krankheit", "absence_category": "krankheit",
        "start_date": "2026-09-01", "end_date": "2026-09-03", "notes": "Grippe",
    }).json()

    # buero_auftrag verschiebt nur das Enddatum -- sendet weder absence_category, absence_type
    # noch notes mit (das Formular zeigt sie ihm nicht an).
    auftrag_client = router_test_client(db, planning_router, role="buero_auftrag")
    resp = auftrag_client.put(f"/api/planning/absences/{created['id']}", json={"end_date": "2026-09-05"})
    assert resp.status_code == 200, resp.text
    assert not (_recursive_keys(resp.json()) & SENSITIVE_KEYS)

    finanzen_check = finanzen_client.get("/api/planning/absences").json()[0]
    assert finanzen_check["end_date"] == "2026-09-05"
    assert finanzen_check["absence_category"] == "krankheit"
    assert finanzen_check["absence_type"] == "Krankheit"
    assert finanzen_check["notes"] == "Grippe"


def test_partial_update_rejects_end_before_start_against_stored_value(threaded_db_session, router_test_client):
    db = threaded_db_session
    emp = make_employee(db)
    client = router_test_client(db, planning_router, role="buero_finanzen")
    created = client.post("/api/planning/absences", json={
        "employee_id": emp.id, "absence_type": "Urlaub", "absence_category": "urlaub",
        "start_date": "2026-09-10", "end_date": "2026-09-12",
    }).json()
    # Nur start_date wird gesendet, aber auf einen Wert NACH dem (unveraendert bleibenden)
    # end_date verschoben -- muss gegen den TATSAECHLICH gespeicherten end_date geprueft werden,
    # nicht nur gegen die im Request enthaltenen Felder.
    resp = client.put(f"/api/planning/absences/{created['id']}", json={"start_date": "2026-09-15"})
    assert resp.status_code == 422


def test_field_role_cannot_reach_any_absence_endpoint(threaded_db_session, router_test_client):
    db = threaded_db_session
    emp = make_employee(db)
    client = router_test_client(db, planning_router, role="field", employee_id=emp.id)
    assert client.get("/api/planning/absences").status_code == 403
    assert client.post("/api/planning/absences", json={
        "employee_id": emp.id, "absence_category": "urlaub",
        "start_date": "2026-09-01", "end_date": "2026-09-02",
    }).status_code == 403
    assert client.get("/api/planning", params={"start": "2026-09-01", "end": "2026-09-14"}).status_code == 403


# --- Plantafel-Board: Konflikte, Tageskapazitaet, Backoffice-Liste ---

@pytest.mark.parametrize("role,expects_type", [("buero_auftrag", False), ("buero_finanzen", True), ("admin", True)])
def test_board_absences_and_capacity_redacted_only_for_buero_auftrag(threaded_db_session, router_test_client, role, expects_type):
    db = threaded_db_session
    emp = make_employee(db)
    make_team_with_employee(db, emp)
    finanzen_client = router_test_client(db, planning_router, role="buero_finanzen")
    finanzen_client.post("/api/planning/absences", json={
        "employee_id": emp.id, "absence_type": "Krankheit", "absence_category": "krankheit",
        "start_date": "2026-09-07", "end_date": "2026-09-09", "notes": "Grippe",
    })

    client = router_test_client(db, planning_router, role=role)
    resp = client.get("/api/planning", params={"start": "2026-09-07", "end": "2026-09-09"})
    assert resp.status_code == 200, resp.text
    board = resp.json()

    keys_present = _recursive_keys(board) & SENSITIVE_KEYS
    if expects_type:
        assert keys_present == SENSITIVE_KEYS or "absence_type" in keys_present
    else:
        assert not keys_present, keys_present

    # Team-Tageskapazitaet: "type" verschwindet, "employee_capacity" zeigt hoechstens "abwesend".
    day = "2026-09-07"
    team_rows = list(board["team_capacity"].values())[0]
    absences_that_day = team_rows[day]["absences"]
    assert len(absences_that_day) == 1
    if expects_type:
        assert absences_that_day[0]["type"] == "Krankheit"
    else:
        assert "type" not in absences_that_day[0]

    emp_rows = board["employee_capacity"][str(emp.id)]
    if expects_type:
        assert emp_rows[day]["absence"] == "Krankheit"
    else:
        assert emp_rows[day]["absence"] == "abwesend"


def test_field_gets_403_on_planning_board_not_a_reduced_view(threaded_db_session, router_test_client):
    db = threaded_db_session
    client = router_test_client(db, planning_router, role="field")
    resp = client.get("/api/planning", params={"start": "2026-09-01", "end": "2026-09-07"})
    assert resp.status_code == 403


# --- Planungsvorschlag ---

def test_planning_suggestion_hides_absence_type_for_buero_auftrag(threaded_db_session, router_test_client):
    db = threaded_db_session
    emp = make_employee(db)
    team = make_team_with_employee(db, emp, second_employee=True)
    order, item = make_order_with_item(db)
    db.add(OrderItemCalculationSnapshot(order_item_id=item.id, site_time_minutes="720", workshop_time_minutes="0"))
    db.commit()

    finanzen_client = router_test_client(db, planning_router, role="buero_finanzen")
    finanzen_client.post("/api/planning/absences", json={
        "employee_id": emp.id, "absence_type": "Krankheit", "absence_category": "krankheit",
        "start_date": "2026-09-07", "end_date": "2026-09-07",
    })

    payload = {"order_id": order.id, "team_id": team.id, "start_date": "2026-09-07"}
    auftrag_resp = router_test_client(db, planning_router, role="buero_auftrag").post("/api/planning/suggestion", json=payload)
    assert auftrag_resp.status_code == 200, auftrag_resp.text
    assert not (_recursive_keys(auftrag_resp.json()) & SENSITIVE_KEYS)

    finanzen_resp = finanzen_client.post("/api/planning/suggestion", json=payload)
    finanzen_body = finanzen_resp.json()
    day_with_absence = next((d for d in finanzen_body["days"] if d.get("absent_employees")), None)
    assert day_with_absence is not None
    assert day_with_absence["absent_employees"][0]["type"] == "Krankheit"


# --- Aenderungshistorie ---

def test_audit_log_label_never_contains_absence_type_for_anyone(threaded_db_session, router_test_client):
    db = threaded_db_session
    emp = make_employee(db)
    router_test_client(db, planning_router, role="buero_finanzen").post("/api/planning/absences", json={
        "employee_id": emp.id, "absence_type": "Krankheit", "absence_category": "krankheit",
        "start_date": "2026-09-01", "end_date": "2026-09-02",
    })
    resp = router_test_client(db, audit_router, role="buero_finanzen").get(
        "/api/audit-logs", params={"entity_type": "Mitarbeiter-Abwesenheit"}
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert rows
    assert "Krankheit" not in rows[0]["entity_label"]


def test_audit_log_details_snapshot_redacted_for_buero_auftrag_not_for_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    emp = make_employee(db)
    router_test_client(db, planning_router, role="buero_finanzen").post("/api/planning/absences", json={
        "employee_id": emp.id, "absence_type": "Krankheit", "absence_category": "krankheit",
        "start_date": "2026-09-01", "end_date": "2026-09-02", "notes": "Grippe",
    })

    auftrag_resp = router_test_client(db, audit_router, role="buero_auftrag").get(
        "/api/audit-logs", params={"entity_type": "Mitarbeiter-Abwesenheit"}
    )
    auftrag_rows = auftrag_resp.json()
    assert auftrag_rows
    assert not (_recursive_keys(auftrag_rows) & SENSITIVE_KEYS), auftrag_rows

    finanzen_rows = router_test_client(db, audit_router, role="buero_finanzen").get(
        "/api/audit-logs", params={"entity_type": "Mitarbeiter-Abwesenheit"}
    ).json()
    assert _recursive_keys(finanzen_rows) & SENSITIVE_KEYS


def test_field_cannot_reach_audit_logs_at_all(threaded_db_session, router_test_client):
    db = threaded_db_session
    resp = router_test_client(db, audit_router, role="field").get("/api/audit-logs")
    assert resp.status_code == 403


# --- Gesamt-Angriffstest ueber alle Rollen ---

@pytest.mark.parametrize("role", ALL_ROLES)
def test_absence_endpoints_never_leak_sensitive_keys_to_field_or_auftrag(threaded_db_session, router_test_client, role):
    db = threaded_db_session
    emp = make_employee(db)
    make_team_with_employee(db, emp)
    router_test_client(db, planning_router, role="admin").post("/api/planning/absences", json={
        "employee_id": emp.id, "absence_type": "Krankheit", "absence_category": "krankheit",
        "start_date": "2026-09-07", "end_date": "2026-09-09", "notes": "Grippe",
    })
    client = router_test_client(db, planning_router, role=role, employee_id=emp.id if role == "field" else None)

    list_resp = client.get("/api/planning/absences")
    board_resp = client.get("/api/planning", params={"start": "2026-09-01", "end": "2026-09-14"})

    if role == "field":
        assert list_resp.status_code == 403
        assert board_resp.status_code == 403
        return

    assert list_resp.status_code == 200
    assert board_resp.status_code == 200
    should_be_hidden = role == "buero_auftrag"
    for resp in (list_resp, board_resp):
        found = _recursive_keys(resp.json()) & SENSITIVE_KEYS
        if should_be_hidden:
            assert not found, (role, found)
        else:
            assert found, (role, "expected to see absence detail but found none")
