"""Version 1.9.233 (Stufe 6, R3a, Punkt 2): Besetzung je Einsatz.

    Kolonne       schlägt beim Anlegen und beim Wechsel ihre heutigen aktiven Mitglieder vor (Stammdaten, nicht der Schnappschuss an der AV); eine spätere
                  Änderung der Kolonne ändert keinen bestehenden Einsatz
    gewählt       employee_ids setzt die Besetzung genau so (auch Personen anderer Kolonnen); unbekannt oder inaktiv 422
    ohne Kolonne  team_id null mit mindestens einer Person; beim Ändern bleiben die Personen; ohne Person 422; keine Kolonnen-Zuweisung an der AV
    Leser         Tafel, Kapazität, Konflikte, „Heute“/„Nächste Tage“, Zugriff der Monteurin, Akte -- alle aus der Besetzung
    Migration     e4b1c9d27a35: Schnappschuss der Kolonne, dann Einzelzuweisungen der AV; downgrade bricht ab, solange ein Einsatz ohne Kolonne besteht
"""

import os
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text

from app.akte import einsaetze
from app.main import create_team
from app.models import Employee, PlanningSlot, PlanningSlotEmployee, TeamEmployee, WorkPreparationEmployee, WorkPreparationTeamAssignment
from app.orders import employee_assigned_order_ids, field_may_access_order
from app.planning import BesetzungUngueltig, create_slot, einsatz_konflikte, list_todays_assignments_for_employee, list_upcoming_assignments_for_employee, \
    planning_board, update_slot
from app.routers.planning import router as planning_router
from app.schemas import TeamCreate, TeamEmployeeInput
from tests.test_v090_planning_board import setup_order
from tests.test_v380_nummern_eindeutig import _alembic, _ok

ROOT = Path(__file__).resolve().parent.parent
MONTAG = date(2026, 11, 2)  # KW 45: Sollzeit 8,00 h (Tarif KW 18–48)
MIGRATION = "e4b1c9d27a35"
VORHER = "b6d14e8a2f73"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def _person(db, nummer, name, aktiv=True):
    emp = Employee(employee_number=nummer, first_name=name, last_name="Test", employee_group="gewerblich", hourly_wage=Decimal("20"),
                   weekly_hours=Decimal("40"), active=aktiv)
    db.add(emp)
    db.commit()
    return emp


def _kolonne(db, nummer, personen=()):
    return create_team(TeamCreate(team_number=nummer, name=f"Kolonne {nummer}",
                                  employees=[TeamEmployeeInput(employee_id=p.id, role="Monteur") for p in personen]), db)


def _besetzung(db, slot_id):
    db.expire_all()
    return [x.employee_id for x in db.scalars(select(PlanningSlotEmployee).where(PlanningSlotEmployee.slot_id == slot_id).order_by(PlanningSlotEmployee.id))]


def _body(order, team, start=MONTAG, tage=3, **mehr):
    return {"order_id": order.id, "team_id": team.id if team is not None else None, "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=tage - 1)).isoformat(), "planned_hours": "1", **mehr}


@pytest.fixture()
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    tom, mia, ole, kai = (_person(db, f"M-{i}", n) for i, n in enumerate(("Tom", "Mia", "Ole", "Kai"), 1))
    alt = _person(db, "M-9", "Alt", aktiv=False)
    nord = _kolonne(db, "N", [tom, mia, alt])
    sued = _kolonne(db, "S", [kai])
    return {"db": db, "client": router_test_client(db, planning_router), "tom": tom, "mia": mia, "ole": ole, "kai": kai, "alt": alt, "nord": nord,
            "sued": sued, "a": setup_order(db, "1"), "b": setup_order(db, "2")}


# --- Anlegen ------------------------------------------------------------------------------------------------------------------------------

def test_kolonne_schlaegt_ihre_aktiven_mitglieder_vor(welt):
    db = welt["db"]
    r = welt["client"].post("/api/planning/slots", json=_body(welt["a"], welt["nord"]))
    assert r.status_code == 200, r.text
    assert _besetzung(db, r.json()["id"]) == [welt["tom"].id, welt["mia"].id]  # Alt ist inaktiv
    assert [e["name"] for e in r.json()["employees"]] == ["Tom Test", "Mia Test"]


def test_spaetere_aenderung_der_kolonne_aendert_keinen_einsatz(welt):
    """B1 (Befund Stufe 6): Ole kommt nach dem ersten Einsatz in die Kolonne -- der erste bleibt, ein neuer Einsatz derselben Kolonne am selben Auftrag
    schlägt Ole mit vor (bis 1.9.232 galt für ihn der alte Schnappschuss an der AV)."""
    db = welt["db"]
    erster = create_slot(db, order_id=welt["a"].id, team_id=welt["nord"].id, start_date=MONTAG, end_date=MONTAG, planned_hours=Decimal("1"))
    db.add(TeamEmployee(team_id=welt["nord"].id, employee_id=welt["ole"].id))
    db.commit()
    zweiter = create_slot(db, order_id=welt["a"].id, team_id=welt["nord"].id, start_date=MONTAG + timedelta(days=7), end_date=MONTAG + timedelta(days=7),
                          planned_hours=Decimal("1"))
    assert _besetzung(db, erster.id) == [welt["tom"].id, welt["mia"].id]
    assert _besetzung(db, zweiter.id) == [welt["tom"].id, welt["mia"].id, welt["ole"].id]


def test_gewaehlte_personen_auch_aus_anderer_kolonne(welt):
    db = welt["db"]
    r = welt["client"].post("/api/planning/slots", json=_body(welt["a"], welt["nord"], employee_ids=[welt["mia"].id, welt["kai"].id, welt["mia"].id]))
    assert r.status_code == 200, r.text
    assert _besetzung(db, r.json()["id"]) == [welt["mia"].id, welt["kai"].id]
    assert r.json()["team_id"] == welt["nord"].id


@pytest.mark.parametrize("wer, text", [("unbekannt", "wurde nicht gefunden"), ("alt", "ist nicht aktiv")])
def test_unbekannt_oder_inaktiv_422(welt, wer, text):
    eid = 999999 if wer == "unbekannt" else welt["alt"].id
    r = welt["client"].post("/api/planning/slots", json=_body(welt["a"], welt["nord"], employee_ids=[eid]))
    assert r.status_code == 422 and text in r.json()["detail"], r.text
    assert welt["db"].scalar(select(func.count()).select_from(PlanningSlot)) == 0


def test_ohne_kolonne(welt):
    db = welt["db"]
    r = welt["client"].post("/api/planning/slots", json=_body(welt["a"], None, employee_ids=[welt["ole"].id]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["team_id"], d["team_name"], d["team_assignment_id"]) == (None, None, None)
    assert _besetzung(db, d["id"]) == [welt["ole"].id]
    assert db.scalar(select(func.count()).select_from(WorkPreparationTeamAssignment)) == 0  # keine Kolonnen-Zuweisung an der AV
    for koerper in (_body(welt["a"], None), _body(welt["a"], None, employee_ids=[])):
        r = welt["client"].post("/api/planning/slots", json=koerper)
        assert r.status_code == 422 and "mindestens eine Person" in r.text, r.text
    with pytest.raises(BesetzungUngueltig):
        create_slot(db, order_id=welt["a"].id, team_id=None, start_date=MONTAG, end_date=MONTAG)


# --- Ändern -------------------------------------------------------------------------------------------------------------------------------

def test_andere_kolonne_setzt_ihre_mitglieder(welt):
    db, client = welt["db"], welt["client"]
    sid = client.post("/api/planning/slots", json=_body(welt["a"], welt["nord"])).json()["id"]
    r = client.put(f"/api/planning/slots/{sid}", json={"team_id": welt["sued"].id})
    assert r.status_code == 200, r.text
    assert _besetzung(db, sid) == [welt["kai"].id]
    r = client.put(f"/api/planning/slots/{sid}", json={"team_id": welt["nord"].id, "employee_ids": [welt["ole"].id]})
    assert r.status_code == 200 and _besetzung(db, sid) == [welt["ole"].id], r.text


def test_ohne_kolonne_behaelt_die_personen(welt):
    db, client = welt["db"], welt["client"]
    sid = client.post("/api/planning/slots", json=_body(welt["a"], welt["nord"])).json()["id"]
    r = client.put(f"/api/planning/slots/{sid}", json={"team_id": None})
    assert r.status_code == 200 and r.json()["team_id"] is None, r.text
    assert _besetzung(db, sid) == [welt["tom"].id, welt["mia"].id]
    r = client.put(f"/api/planning/slots/{sid}", json={"employee_ids": []})
    assert r.status_code == 422 and "mindestens eine Person" in r.json()["detail"], r.text
    assert _besetzung(db, sid) == [welt["tom"].id, welt["mia"].id]
    assert client.put(f"/api/planning/slots/{sid}", json={"employee_ids": None}).status_code == 422  # null heißt nicht „unverändert“


def test_nur_die_personen_setzen_und_unveraendert(welt):
    db, client = welt["db"], welt["client"]
    sid = client.post("/api/planning/slots", json=_body(welt["a"], welt["nord"])).json()["id"]
    assert client.put(f"/api/planning/slots/{sid}", json={"employee_ids": [welt["kai"].id, welt["tom"].id]}).status_code == 200
    assert _besetzung(db, sid) == [welt["tom"].id, welt["kai"].id]  # wer bleibt, behält seinen Platz; neue kommen dahinter
    assert client.put(f"/api/planning/slots/{sid}", json={"notes": "Schlüssel bei Sommer"}).status_code == 200
    assert _besetzung(db, sid) == [welt["tom"].id, welt["kai"].id]
    assert client.put(f"/api/planning/slots/{sid}", json={"employee_ids": [999999]}).status_code == 422


def test_geaenderte_besetzung_fragt_zurueck(welt):
    """Kai steht schon im Einsatz von Auftrag 1 -- ihn in den Einsatz von Auftrag 2 nehmen fragt (409), mit „trotzdem“ gespeichert."""
    client = welt["client"]
    client.post("/api/planning/slots", json=_body(welt["a"], welt["sued"]))
    sid = client.post("/api/planning/slots", json=_body(welt["b"], welt["nord"])).json()["id"]
    r = client.put(f"/api/planning/slots/{sid}", json={"employee_ids": [welt["tom"].id, welt["kai"].id]})
    assert r.status_code == 409 and [(k["type"], k["label"]) for k in r.json()["warnungen"]] == [("employee", "Kai Test")], r.text
    assert _besetzung(welt["db"], sid) == [welt["tom"].id, welt["mia"].id]
    r = client.put(f"/api/planning/slots/{sid}", json={"employee_ids": [welt["tom"].id, welt["kai"].id], "trotzdem_planen": True})
    assert r.status_code == 200 and _besetzung(welt["db"], sid) == [welt["tom"].id, welt["kai"].id], r.text


# --- Leser --------------------------------------------------------------------------------------------------------------------------------

def test_person_doppelt_auch_ohne_kolonne(welt):
    """B6 auf dem neuen Modell: Ole einzeln an zwei Aufträgen am selben Tag -- Warnung."""
    db = welt["db"]
    create_slot(db, order_id=welt["a"].id, team_id=None, employee_ids=[welt["ole"].id], start_date=MONTAG, end_date=MONTAG, planned_hours=Decimal("1"))
    r = welt["client"].post("/api/planning/slots", json=_body(welt["b"], None, employee_ids=[welt["ole"].id], tage=1))
    assert r.status_code == 409 and [(k["type"], k["label"]) for k in r.json()["warnungen"]] == [("employee", "Ole Test")], r.text


def test_kapazitaet_aus_der_besetzung(welt):
    """Zwei Personen × 3 Arbeitstage × 8,00 h (KW 45, Tarif KW 18–48) = 48,00 h; mit 50 h fehlen 2,00 h."""
    db = welt["db"]
    slot = create_slot(db, order_id=welt["a"].id, team_id=welt["sued"].id, employee_ids=[welt["kai"].id, welt["ole"].id], start_date=MONTAG,
                       end_date=MONTAG + timedelta(days=2), planned_hours=Decimal("50"), travel_hours_per_employee_day=Decimal("0"),
                       trotzdem_planen=True)
    hinweise = einsatz_konflikte(db, slot)["hinweise"]
    assert [(k["type"], k["shortfall_hours"]) for k in hinweise] == [("capacity", Decimal("2.00"))]


def test_tafel_zeigt_besetzung_und_ohne_kolonne(welt):
    db = welt["db"]
    mit = create_slot(db, order_id=welt["a"].id, team_id=welt["nord"].id, employee_ids=[welt["kai"].id], start_date=MONTAG, end_date=MONTAG,
                      planned_hours=Decimal("1"))
    ohne = create_slot(db, order_id=welt["b"].id, team_id=None, employee_ids=[welt["ole"].id], start_date=MONTAG, end_date=MONTAG,
                       planned_hours=Decimal("1"))
    tafel = planning_board(db, MONTAG, MONTAG + timedelta(days=6))
    slots = {s["id"]: s for s in tafel["slots"]}
    assert [e["id"] for e in slots[mit.id]["employees"]] == [welt["kai"].id]
    assert (slots[ohne.id]["team_id"], [e["id"] for e in slots[ohne.id]["employees"]]) == (None, [welt["ole"].id])
    seite = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")
    assert "label:'Ohne Kolonne',sub:'Personen einzeln gewählt'" in seite
    assert "teamOptions(s.team_id,{leer:'ohne Kolonne – die Personen bleiben'})" in seite
    assert "team_id:document.getElementById('editTeam').value===''?null:" in seite


def test_heute_naechste_tage_und_zugriff_aus_der_besetzung(welt):
    db = welt["db"]
    tag = date(2026, 11, 3)
    slot = create_slot(db, order_id=welt["a"].id, team_id=welt["nord"].id, employee_ids=[welt["tom"].id, welt["kai"].id], start_date=tag, end_date=tag,
                       planned_hours=Decimal("1"))
    assert [a["slot_id"] for a in list_todays_assignments_for_employee(db, welt["kai"].id, tag)] == [slot.id]
    assert list_todays_assignments_for_employee(db, welt["mia"].id, tag) == []  # in der Kolonne, aber nicht im Einsatz
    assert [a["slot_id"] for a in list_upcoming_assignments_for_employee(db, welt["kai"].id, today=tag)] == [slot.id]
    assert field_may_access_order(db, welt["kai"].id, welt["a"].id) and welt["a"].id in employee_assigned_order_ids(db, welt["kai"].id)
    assert not field_may_access_order(db, welt["ole"].id, welt["a"].id)
    # eine Einzelzuweisung an der AV nach 1.9.233 ist eine Zuweisung ohne Datum: Zugriff, aber kein Einsatz auf „Heute“
    db.add(WorkPreparationEmployee(preparation_id=slot.preparation_id, employee_id=welt["ole"].id))
    db.commit()
    assert field_may_access_order(db, welt["ole"].id, welt["a"].id)
    assert list_todays_assignments_for_employee(db, welt["ole"].id, tag) == []


def test_akte_nennt_kolonne_und_personen(welt):
    db = welt["db"]
    create_slot(db, order_id=welt["a"].id, team_id=welt["nord"].id, start_date=MONTAG, end_date=MONTAG, planned_hours=Decimal("1"))
    create_slot(db, order_id=welt["a"].id, team_id=None, employee_ids=[welt["ole"].id], start_date=MONTAG + timedelta(days=7),
                end_date=MONTAG + timedelta(days=7), planned_hours=Decimal("1"))
    assert [(e["team"], e["personen"]) for e in einsaetze(db, welt["a"].id)] == [("Kolonne N", 2), ("Ohne Kolonne", 1)]


def test_update_slot_direkt_ohne_kolonne_ohne_personen(welt):
    db = welt["db"]
    slot = create_slot(db, order_id=welt["a"].id, team_id=welt["nord"].id, start_date=MONTAG, end_date=MONTAG, planned_hours=Decimal("1"))
    with pytest.raises(BesetzungUngueltig):
        update_slot(db, slot.id, team_id=None, employee_ids=[])


# --- Migration e4b1c9d27a35 ---------------------------------------------------------------------------------------------------------------

def _bestand(engine) -> dict:
    """Zwei Einsätze an einer AV mit Kolonne (Tom, Mia im Schnappschuss) und zwei Einzelzuweisungen (Ole, Tom); ein Einsatz einer zweiten AV
    nur mit Kolonne (Kai). Stand VORHER (Core-Insert, Aufträge über tests/bestand_alt.py)."""
    from sqlalchemy.orm import Session
    from tests.bestand_alt import auftrag as alt_auftrag
    with Session(engine) as s:
        auftraege = [alt_auftrag(s, number=f"633-{nr}").id for nr in range(2)]
    with engine.begin() as c:
        def neu(sql, **w):
            return c.execute(text(sql + " RETURNING id"), w).scalar()
        ids = {n: neu("INSERT INTO employees (employee_number, first_name, last_name, employee_group, weekly_hours, active, created_at, updated_at) "
                      "VALUES (:n, :n, 'Test', 'gewerblich', 40, :a, '2026-09-01', '2026-09-01')", n=n, a=True) for n in ("Tom", "Mia", "Ole", "Kai")}
        team = neu("INSERT INTO teams (team_number, name, active, created_at, updated_at) VALUES ('N', 'Nord', :a, '2026-09-01', '2026-09-01')", a=True)
        slots = []
        for nr, (kolonne, einzeln) in enumerate(((["Tom", "Mia"], ["Ole", "Tom"]), (["Kai"], []))):
            auftrag = auftraege[nr]
            av = neu("INSERT INTO work_preparations (order_id, status, created_at, updated_at) VALUES (:o, 'offen', '2026-09-01', '2026-09-01')", o=auftrag)
            zuweisung = neu("INSERT INTO work_preparation_team_assignments (preparation_id, team_id, team_name_snapshot, created_at) "
                            "VALUES (:av, :t, 'Nord', '2026-09-01')", av=av, t=team)
            for n in kolonne:
                c.execute(text("INSERT INTO work_preparation_team_employees (assignment_id, employee_id, employee_name_snapshot) VALUES (:z, :e, :n)"),
                          {"z": zuweisung, "e": ids[n], "n": n})
            for n in einzeln:
                c.execute(text("INSERT INTO work_preparation_employees (preparation_id, employee_id) VALUES (:av, :e)"), {"av": av, "e": ids[n]})
            for tag in (("2026-11-02", "2026-11-04"), ("2026-11-09", "2026-11-10"))[: 2 if nr == 0 else 1]:
                slots.append(neu("INSERT INTO planning_slots (preparation_id, team_assignment_id, start_date, end_date, status, created_at, updated_at) "
                                 "VALUES (:av, :z, :s, :e, 'geplant', '2026-09-01', '2026-09-01')", av=av, z=zuweisung, s=tag[0], e=tag[1]))
    return {"ids": ids, "slots": slots}


def _stand(engine):
    with engine.connect() as c:
        return [tuple(z) for z in c.execute(text("SELECT slot_id, employee_id FROM planning_slot_employees ORDER BY id"))]


def _probe(url, engine):
    _ok(_alembic(url, "upgrade", VORHER))
    b = _bestand(engine)
    _ok(_alembic(url, "upgrade", MIGRATION))
    i, s = b["ids"], b["slots"]
    assert _stand(engine) == [(s[0], i["Tom"]), (s[0], i["Mia"]), (s[0], i["Ole"]), (s[1], i["Tom"]), (s[1], i["Mia"]), (s[1], i["Ole"]),
                              (s[2], i["Kai"])]
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        assert not engine.dialect.has_table(c, "planning_slot_employees")
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.begin() as c:  # ein Einsatz ohne Kolonne -- downgrade bricht ab, nichts geändert
        c.execute(text("UPDATE planning_slots SET team_assignment_id = NULL WHERE id = :s"), {"s": s[2]})
    vorher = _stand(engine)
    r = _alembic(url, "downgrade", VORHER)
    assert r.returncode != 0 and "ohne Kolonne" in r.stdout + r.stderr
    assert _stand(engine) == vorher
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'besetzung.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_besetzung_{uuid.uuid4().hex[:8]}"
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


def test_aenderungsprotokoll_nennt_besetzung_und_ohne_kolonne(welt):
    """Seit 1.9.233 steht jede Person der Besetzung im Änderungsprotokoll (Typ „Plantafel-Besetzung“, Kennung = Einsatz, damit der Verlauf der Akte
    sie dem Auftrag zuordnet); ein Einsatz ohne Kolonne heißt dort „Ohne Kolonne · …“."""
    from app.akte_verlauf import ART_JE_TYP
    from app.models import AuditLog
    assert ART_JE_TYP["Plantafel-Besetzung"] == "termin"
    db = welt["db"]
    slot = create_slot(db, order_id=welt["a"].id, team_id=None, employee_ids=[welt["ole"].id], start_date=MONTAG, end_date=MONTAG,
                       planned_hours=Decimal("1"))
    zeilen = db.execute(select(AuditLog.entity_type, AuditLog.entity_id, AuditLog.entity_label)
                        .where(AuditLog.entity_type.in_(["Plantafel-Einsatz", "Plantafel-Besetzung"]))).all()
    assert ("Plantafel-Besetzung", str(slot.id), "Ole Test") in [tuple(z) for z in zeilen]
    assert any(t == "Plantafel-Einsatz" and (label or "").startswith("Ohne Kolonne") for t, _i, label in zeilen)


def test_schema_ohne_kolonne_ohne_person():
    """Seit der Gegenprobe 233_5a (sie blieb grün: die Geschäftsfunktion lehnt ebenfalls ab): das Schema allein lehnt „ohne Kolonne ohne Person“ ab."""
    from pydantic import ValidationError

    from app.schemas import PlanningSlotCreate
    for personen in (None, []):
        with pytest.raises(ValidationError, match="mindestens eine Person"):
            PlanningSlotCreate(order_id=1, team_id=None, employee_ids=personen, start_date=MONTAG, end_date=MONTAG)
    assert PlanningSlotCreate(order_id=1, team_id=None, employee_ids=[1], start_date=MONTAG, end_date=MONTAG).employee_ids == [1]
