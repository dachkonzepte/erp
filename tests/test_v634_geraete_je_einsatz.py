"""Version 1.9.234 (Stufe 6, R3a, Punkt 3): Geräte je Einsatz, für alle Tage oder einzelne Tage.

    Kolonne       schlägt ihre aktiven Geräte vor (alle Tage) -- beim Anlegen und beim Wechsel der Kolonne; ohne Kolonne keine
    gewählt       geraete [{resource_id, tage}] setzt sie genau so; unbekannt, inaktiv, Tag außerhalb, leere Tagesliste 422
    Zeitraum      verschoben (gleiche Dauer): einzelne Tage wandern mit; sonst bleiben nur Tage im neuen Zeitraum, ein Gerät ohne Tag fällt weg
    Leser         Gerät doppelt nur, wenn sich die Tage treffen; Termine im Kalender des Geräts nur an seinen Tagen; Belegung der Tafel; Löschschutz
    Migration     f2c8d4a61e93: die Geräte des Kolonnen-Schnappschusses, alle Tage
"""

import json
import os
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, text

from app.main import create_resource, create_team
from app.models import AuditLog, CalendarEvent, OperationalResource, PlanningSlotResource
from app.planning import GeraeteUngueltig, create_slot, einsatz_konflikte, planning_board, update_slot
from app.routers.planning import router as planning_router
from app.routers.resource_planning import router as resource_router
from app.schemas import OperationalResourceCreate, TeamCreate, TeamEmployeeInput, TeamResourceInput
from tests.test_v090_planning_board import setup_order
from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.test_v633_besetzung_je_einsatz import _person

MONTAG = date(2026, 11, 2)
MIGRATION = "f2c8d4a61e93"
VORHER = "e4b1c9d27a35"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def _geraet(db, nummer, name, aktiv=True):
    r = create_resource(OperationalResourceCreate(resource_number=nummer, resource_type="Maschine", name=name, identifier=nummer), db)
    if not aktiv:
        db.get(OperationalResource, r.id).active = False
        db.commit()
    return r.id


def _geraete(db, slot_id):
    db.expire_all()
    return [(x.resource_id, json.loads(x.tage) if x.tage else None)
            for x in db.scalars(select(PlanningSlotResource).where(PlanningSlotResource.slot_id == slot_id).order_by(PlanningSlotResource.id))]


def _tag(n):
    return (MONTAG + timedelta(days=n)).isoformat()


@pytest.fixture()
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    tom, kai = _person(db, "M-1", "Tom"), _person(db, "M-2", "Kai")
    kran, pritsche, alt = _geraet(db, "K-1", "Kran"), _geraet(db, "F-1", "Pritsche"), _geraet(db, "F-9", "Alt", aktiv=False)
    nord = create_team(TeamCreate(team_number="N", name="Nord", employees=[TeamEmployeeInput(employee_id=tom.id, role="Monteur")],
                                  resources=[TeamResourceInput(resource_id=pritsche, role="Standard"), TeamResourceInput(resource_id=alt, role="Standard")]), db)
    sued = create_team(TeamCreate(team_number="S", name="Süd", employees=[TeamEmployeeInput(employee_id=kai.id, role="Monteur")],
                                  resources=[TeamResourceInput(resource_id=kran, role="bei Bedarf")]), db)
    return {"db": db, "client": router_test_client(db, planning_router, resource_router), "tom": tom, "kai": kai, "kran": kran, "pritsche": pritsche,
            "alt": alt, "nord": nord, "sued": sued, "a": setup_order(db, "1"), "b": setup_order(db, "2")}


def _body(order, team, start=0, tage=3, **mehr):
    return {"order_id": order.id, "team_id": team.id if team is not None else None, "start_date": _tag(start), "end_date": _tag(start + tage - 1),
            "planned_hours": "1", **mehr}


def test_kolonne_schlaegt_ihre_aktiven_geraete_vor(welt):
    r = welt["client"].post("/api/planning/slots", json=_body(welt["a"], welt["nord"]))
    assert r.status_code == 200, r.text
    assert _geraete(welt["db"], r.json()["id"]) == [(welt["pritsche"], None)]  # „Alt“ ist inaktiv
    assert [(g["name"], g["tage"], g["role"]) for g in r.json()["resources"]] == [("Pritsche", None, "Standard")]


def test_ohne_kolonne_keine_geraete_ausser_gewaehlten(welt):
    db = welt["db"]
    ohne = create_slot(db, order_id=welt["a"].id, team_id=None, employee_ids=[welt["tom"].id], start_date=MONTAG, end_date=MONTAG,
                       planned_hours=Decimal("1"))
    assert _geraete(db, ohne.id) == []
    mit = welt["client"].post("/api/planning/slots", json=_body(welt["b"], None, employee_ids=[welt["kai"].id],
                                                                geraete=[{"resource_id": welt["kran"], "tage": [_tag(1)]}]))
    assert mit.status_code == 200 and _geraete(db, mit.json()["id"]) == [(welt["kran"], [_tag(1)])], mit.text


def test_einzelne_tage_und_doppelt_genannt(welt):
    r = welt["client"].post("/api/planning/slots", json=_body(welt["a"], welt["nord"], geraete=[
        {"resource_id": welt["kran"], "tage": [_tag(2), _tag(0), _tag(2)]}, {"resource_id": welt["pritsche"]}, {"resource_id": welt["kran"]}]))
    assert r.status_code == 200, r.text
    assert _geraete(welt["db"], r.json()["id"]) == [(welt["kran"], [_tag(0), _tag(2)]), (welt["pritsche"], None)]


@pytest.mark.parametrize("geraet, text", [
    ({"resource_id": 999999}, "wurde nicht gefunden"), ("alt", "ist nicht aktiv"),
    ("ausserhalb", "liegt außerhalb des Einsatzes"), ("leer", "mindestens einen Tag")])
def test_ungueltige_geraete_422(welt, geraet, text):
    g = geraet if isinstance(geraet, dict) else {"alt": {"resource_id": welt["alt"]}, "ausserhalb": {"resource_id": welt["kran"], "tage": [_tag(5)]},
                                                  "leer": {"resource_id": welt["kran"], "tage": []}}[geraet]
    r = welt["client"].post("/api/planning/slots", json=_body(welt["a"], welt["nord"], geraete=[g]))
    assert r.status_code == 422 and text in r.json()["detail"], r.text


def test_wechsel_der_kolonne_und_ohne_kolonne(welt):
    db, client = welt["db"], welt["client"]
    sid = client.post("/api/planning/slots", json=_body(welt["a"], welt["nord"])).json()["id"]
    assert client.put(f"/api/planning/slots/{sid}", json={"team_id": welt["sued"].id}).status_code == 200
    assert _geraete(db, sid) == [(welt["kran"], None)]
    assert client.put(f"/api/planning/slots/{sid}", json={"team_id": None}).status_code == 200
    assert _geraete(db, sid) == [(welt["kran"], None)]  # ohne Kolonne bleiben die Geräte
    r = client.put(f"/api/planning/slots/{sid}", json={"geraete": [{"resource_id": welt["pritsche"], "tage": [_tag(1)]}]})
    assert r.status_code == 200 and _geraete(db, sid) == [(welt["pritsche"], [_tag(1)])], r.text
    assert client.put(f"/api/planning/slots/{sid}", json={"geraete": None}).status_code == 422


def test_tage_wandern_mit_und_fallen_weg(welt):
    db = welt["db"]
    slot = create_slot(db, order_id=welt["a"].id, team_id=welt["nord"].id, start_date=MONTAG, end_date=MONTAG + timedelta(days=2),
                       planned_hours=Decimal("1"), geraete=[{"resource_id": welt["kran"], "tage": [MONTAG + timedelta(days=2)]},
                                                            {"resource_id": welt["pritsche"], "tage": None}])
    update_slot(db, slot.id, start_date=MONTAG + timedelta(days=7), end_date=MONTAG + timedelta(days=9), trotzdem_planen=True)  # eine Woche später
    assert _geraete(db, slot.id) == [(welt["kran"], [_tag(9)]), (welt["pritsche"], None)]
    update_slot(db, slot.id, end_date=MONTAG + timedelta(days=8), trotzdem_planen=True)  # verkürzt: der 11.11. fällt heraus, der Kran ganz
    assert _geraete(db, slot.id) == [(welt["pritsche"], None)]
    with pytest.raises(GeraeteUngueltig):
        update_slot(db, slot.id, geraete=[{"resource_id": welt["kran"], "tage": [MONTAG]}])


def test_geraet_doppelt_nur_wenn_sich_die_tage_treffen(welt):
    client = welt["client"]
    client.post("/api/planning/slots", json=_body(welt["a"], None, employee_ids=[welt["tom"].id], geraete=[{"resource_id": welt["kran"], "tage": [_tag(0)]}]))
    r = client.post("/api/planning/slots", json=_body(welt["b"], None, employee_ids=[welt["kai"].id], geraete=[{"resource_id": welt["kran"], "tage": [_tag(1)]}]))
    assert r.status_code == 200 and not any(k["type"] == "resource" for k in r.json()["conflicts"]), r.text
    r = client.put(f"/api/planning/slots/{r.json()['id']}", json={"geraete": [{"resource_id": welt["kran"], "tage": [_tag(0), _tag(1)]}]})
    assert r.status_code == 409 and [(k["type"], k["label"]) for k in r.json()["warnungen"]] == [("resource", "Kran")], r.text


def test_termin_im_kalender_des_geraets_nur_an_seinen_tagen(welt):
    db = welt["db"]
    db.add(CalendarEvent(title="Vermietung", start_at=datetime.combine(MONTAG, datetime.min.time()).replace(hour=8),
                         end_at=datetime.combine(MONTAG, datetime.min.time()).replace(hour=12), resource_id=welt["kran"]))
    db.commit()
    an_anderem = create_slot(db, order_id=welt["a"].id, team_id=None, employee_ids=[welt["tom"].id], start_date=MONTAG, end_date=MONTAG + timedelta(days=2),
                             planned_hours=Decimal("1"), geraete=[{"resource_id": welt["kran"], "tage": [MONTAG + timedelta(days=1)]}])
    assert [k for k in einsatz_konflikte(db, an_anderem)["warnungen"] if k["type"] == "resource"] == []
    r = welt["client"].post("/api/planning/slots", json=_body(welt["b"], None, employee_ids=[welt["kai"].id], geraete=[{"resource_id": welt["kran"]}]))
    # alle Tage: der Termin am Montag zählt -- und der erste Einsatz, der den Kran am Dienstag hat
    assert r.status_code == 409 and [k["label"] for k in r.json()["warnungen"]] == ["Kran", "Kran · Termin: Vermietung"], r.text


def test_tafel_belegung_nur_an_den_tagen(welt):
    db = welt["db"]
    create_slot(db, order_id=welt["a"].id, team_id=None, employee_ids=[welt["tom"].id], start_date=MONTAG, end_date=MONTAG + timedelta(days=2),
                planned_hours=Decimal("1"), geraete=[{"resource_id": welt["kran"], "tage": [MONTAG + timedelta(days=1)]}])
    belegung = planning_board(db, MONTAG, MONTAG + timedelta(days=6))["resource_load"][str(welt["kran"])]
    assert [belegung[_tag(i)] for i in range(3)] == [0, 1, 0]


def test_geraet_am_einsatz_wird_nicht_geloescht(welt):
    db = welt["db"]
    create_slot(db, order_id=welt["a"].id, team_id=None, employee_ids=[welt["tom"].id], start_date=MONTAG, end_date=MONTAG,
                planned_hours=Decimal("1"), geraete=[{"resource_id": welt["kran"]}])
    from app.models import TeamResource  # die Kolonne Süd führt den Kran auch -- hier zählt nur der Einsatz
    db.query(TeamResource).filter_by(resource_id=welt["kran"]).delete()
    db.commit()
    r = welt["client"].delete(f"/api/resources/{welt['kran']}")
    assert r.status_code == 200 and r.json() == {"deleted": False, "deactivated": True}, r.text


def test_aenderungsprotokoll_nennt_das_geraet(welt):
    from app.akte_verlauf import ART_JE_TYP
    db = welt["db"]
    slot = create_slot(db, order_id=welt["a"].id, team_id=welt["nord"].id, start_date=MONTAG, end_date=MONTAG, planned_hours=Decimal("1"))
    zeilen = db.execute(select(AuditLog.entity_type, AuditLog.entity_id, AuditLog.entity_label).where(AuditLog.entity_type == "Plantafel-Gerät")).all()
    assert [tuple(z) for z in zeilen] == [("Plantafel-Gerät", str(slot.id), "Pritsche")]
    assert ART_JE_TYP["Plantafel-Gerät"] == "termin"


# --- Migration f2c8d4a61e93 ---------------------------------------------------------------------------------------------------------------

def _probe(url, engine):
    from tests.test_v633_besetzung_je_einsatz import _bestand
    _ok(_alembic(url, "upgrade", VORHER))
    b = _bestand(engine)
    with engine.begin() as c:
        geraete = [c.execute(text("INSERT INTO operational_resources (resource_number, resource_type, name, active, created_at, updated_at) "
                                  "VALUES (:n, 'Maschine', :n, :a, '2026-09-01', '2026-09-01') RETURNING id"), {"n": n, "a": True}).scalar()
                   for n in ("Kran", "Pritsche")]
        zuweisungen = [z for (z,) in c.execute(text("SELECT DISTINCT team_assignment_id FROM planning_slots ORDER BY team_assignment_id"))]
        for gid in geraete:
            c.execute(text("INSERT INTO work_preparation_team_resources (assignment_id, resource_id, resource_name_snapshot, resource_type_snapshot) "
                           "VALUES (:z, :r, 'x', 'Maschine')"), {"z": zuweisungen[0], "r": gid})
    _ok(_alembic(url, "upgrade", MIGRATION))
    s = b["slots"]
    with engine.connect() as c:
        stand = [tuple(z) for z in c.execute(text("SELECT slot_id, resource_id, tage FROM planning_slot_resources ORDER BY id"))]
    assert stand == [(s[0], geraete[0], None), (s[0], geraete[1], None), (s[1], geraete[0], None), (s[1], geraete[1], None)]
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        assert not engine.dialect.has_table(c, "planning_slot_resources")
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'geraete.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_geraete_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
