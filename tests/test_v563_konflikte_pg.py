"""Version 1.9.143 (Stufe 6, R1, Punkt 1), Nachtrag 1.9.147: Konflikte beim Speichern unter PostgreSQL (Regel 27: Wegwerf-Schema). SQLite kennt weder die Zeilensperre noch die Fremdschlüsselprüfung:

    Anlegen      Kolonne doppelt -> 409, nichts zurückgeblieben (Einsatz, Kolonnen-Zuweisung, neue Arbeitsvorbereitung); mit „trotzdem_planen“ 200
    Ändern       Verschieben auf eine belegte Kolonne -> 409, die Sperre der Arbeitsvorbereitung ist danach frei, ein weiteres Ändern geht
    Tafel        GET /api/planning und die Auswahl im Dialog laufen auf PostgreSQL (nur offene, Rückstand)
"""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import get_db
from app.models import AppUser, PlanningSlot, Team, WorkPreparation, WorkPreparationTeamAssignment
from app.routers.planning import router as planning_router
from tests.test_v375_rechnungen_sperren import _vorbereiten, pg  # noqa: F401  (pg ist eine Fixture)

VON, BIS = "2026-11-02", "2026-11-04"


def _client(Session):
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(planning_router)

    @app.middleware("http")
    async def _identitaet(request, call_next):
        request.state.erp_user = AppUser(username="anna", display_name="Anna", role="admin", active=True, password_hash="x")
        return await call_next(request)

    def _db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    return TestClient(app)


def _kolonnen(Session):
    def anlegen(s):
        a, b = Team(name="Kolonne A", active=True), Team(name="Kolonne B", active=True)
        s.add_all([a, b])
        s.commit()
        return a.id, b.id
    return _vorbereiten(Session, anlegen)


def _zaehlen(Session, modell):
    return _vorbereiten(Session, lambda s: s.scalar(select(func.count()).select_from(modell)))


def _body(order_id, team, **mehr):
    return {"order_id": order_id, "team_id": team, "start_date": VON, "end_date": BIS, "planned_hours": "1", **mehr}


def test_pg_warnung_laesst_nichts_zurueck_und_trotzdem_planen_speichert(pg):  # noqa: F811
    Session, order_id = pg
    a, b = _kolonnen(Session)
    client = _client(Session)
    assert client.post("/api/planning/slots", json=_body(order_id, a)).status_code == 200
    antwort = client.post("/api/planning/slots", json=_body(order_id, a))
    assert antwort.status_code == 409, antwort.text
    assert [k["type"] for k in antwort.json()["warnungen"]] == ["team"]
    assert (_zaehlen(Session, PlanningSlot), _zaehlen(Session, WorkPreparationTeamAssignment), _zaehlen(Session, WorkPreparation)) == (1, 1, 1)
    antwort = client.post("/api/planning/slots", json=_body(order_id, a, trotzdem_planen=True))
    assert antwort.status_code == 200, antwort.text
    assert _zaehlen(Session, PlanningSlot) == 2


def test_pg_verschieben_mit_warnung_gibt_die_sperre_frei(pg):  # noqa: F811
    Session, order_id = pg
    a, b = _kolonnen(Session)
    client = _client(Session)
    client.post("/api/planning/slots", json=_body(order_id, a))
    zweiter = client.post("/api/planning/slots", json=_body(order_id, b, start_date="2026-11-16", end_date="2026-11-17")).json()
    url = f"/api/planning/slots/{zweiter['id']}"
    antwort = client.put(url, json={"team_id": a, "start_date": VON, "end_date": BIS})
    assert antwort.status_code == 409, antwort.text
    stand = _vorbereiten(Session, lambda s: (lambda x: (x.team_assignment.team_id, x.start_date))(s.get(PlanningSlot, zweiter["id"])))
    assert stand == (b, date(2026, 11, 16))
    assert _zaehlen(Session, WorkPreparationTeamAssignment) == 2  # keine dritte zurückgeblieben
    antwort = client.put(url, json={"notes": "geht weiter"})  # hinge an der Sperre, bliebe sie stehen
    assert antwort.status_code == 200, antwort.text
    assert client.put(url, json={"team_id": a, "start_date": VON, "end_date": BIS, "trotzdem_planen": True}).status_code == 200


def test_pg_tafel_und_auswahl(pg):  # noqa: F811
    Session, order_id = pg
    a, _ = _kolonnen(Session)
    client = _client(Session)
    params = {"start": "2026-11-02", "end": "2026-11-15"}
    daten = client.get("/api/planning", params=params).json()
    assert [z["order_id"] for z in daten["backlog"]] == [order_id]
    assert [x["id"] for x in client.get("/api/planning/auftraege").json()] == [order_id]
    client.post("/api/planning/slots", json=_body(order_id, a, planned_hours="50"))
    daten = client.get("/api/planning", params=params).json()
    assert daten["backlog"] == []
    assert [s["order_id"] for s in daten["slots"]] == [order_id]
    assert Decimal(str(daten["slots"][0]["planned_hours"])) == Decimal("50")
    assert daten["conflict_count"] == 1  # Kapazität
