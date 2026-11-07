"""Version 1.9.253 (Stufe 6, R4b, Punkt 1): das Kennzeichen „Plantafel“ am Mitarbeiter -- einplanbar | Bauleitung | nicht zeigen.

    Feld        employee_planning_settings.plantafel ersetzt das Häkchen show_on_planning_board; Schema: Literal, None = unverändert, beim Anlegen
                „einplanbar“; ohne Zeile die Vorgabe aus Gruppe und Funktion (kaufmännisch, Lager, Büro, Verwaltung: nicht zeigen)
    Plantafel   „nicht zeigen“: weder in den Personen der Tafel (also weder „Personen“ noch „+ Person“) noch in der Kapazität; Bauleitung und einplanbar
                schickt der Server mit dem Kennzeichen
    Personen    „Bauleitung · Termine aus dem Kalender“ = Kennzeichen Bauleitung (auch in einer Kolonne); einplanbar ohne Kolonne -> „Ohne Kolonne“,
                mit oder ohne Konto (1.9.250–1.9.252 entschied das Konto)
    Migration   e3b7c51a9d26: Häkchen gesetzt -> einplanbar, nicht gesetzt -> nicht_zeigen, Mitarbeiter ohne Zeile bleiben ohne; downgrade zurück
Im Browser: scripts/klicktest_plantafel_personen.py (Bea mit Kennzeichen Bauleitung, Paul mit Konto ohne Kolonne, Vera „nicht zeigen“).
"""

import json
import os
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.employees import PLANTAFEL, effective_plantafel
from app.models import AppUser, Employee, EmployeePlanningSettings
from app.planning import planning_board, planning_visible_employee_ids
from app.routers.employees import router as employees_router
from app.routers.planning import router as planning_router
from app.verlauf_namen import wert_lesbar
from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v633_besetzung_je_einsatz import _kolonne, _person

ROOT = Path(__file__).resolve().parent.parent
MO = date(2026, 11, 2)
MIGRATION = "e3b7c51a9d26"
VORHER = "c9d2e6a3f417"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


def _kennzeichen(db, emp, wert):
    db.add(EmployeePlanningSettings(employee_id=emp.id, plantafel=wert))
    db.commit()


@pytest.fixture()
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    tom, bea, vera, paul = (_person(db, "M-1", "Tom"), _person(db, "M-2", "Bea"), _person(db, "M-3", "Vera"), _person(db, "M-4", "Paul"))
    _kennzeichen(db, bea, "bauleitung")
    _kennzeichen(db, vera, "nicht_zeigen")
    db.add(AppUser(username="paul", display_name="Paul", role="field", employee_id=paul.id, password_hash="x", active=True))
    db.commit()
    nord = _kolonne(db, "N", [tom, bea, vera])
    return {"db": db, "client": router_test_client(db, employees_router, planning_router), "tom": tom, "bea": bea, "vera": vera, "paul": paul, "nord": nord}


def _ohne_ausgabefelder(d):
    return {k: v for k, v in d.items() if k not in ("id", "function_name", "effective_hourly_wage", "annual_gross_wage")}


# --- Feld und Schnittstelle ------------------------------------------------------------------------------------------------------------------

def test_drei_werte():
    assert PLANTAFEL == {"einplanbar": "einplanbar", "bauleitung": "Bauleitung", "nicht_zeigen": "nicht zeigen"}
    assert wert_lesbar("plantafel", "bauleitung") == "Bauleitung" and wert_lesbar("plantafel", "nicht_zeigen") == "Nicht zeigen"


def test_anlegen_ohne_angabe_ist_einplanbar_aendern_ohne_angabe_unveraendert(welt):
    c = welt["client"]
    vorlage = _ohne_ausgabefelder(c.get(f"/api/employees/{welt['tom'].id}").json())
    assert vorlage.pop("plantafel") == "einplanbar"
    neu = c.post("/api/employees", json={**vorlage, "employee_number": "M-9", "first_name": "Lea"})
    assert neu.status_code == 200, neu.text
    assert neu.json()["plantafel"] == "einplanbar"
    zeile = welt["db"].query(EmployeePlanningSettings).filter_by(employee_id=neu.json()["id"]).one()
    assert zeile.plantafel == "einplanbar"  # angelegt mit dem Mitarbeiter, nicht erst beim Lesen
    bea = _ohne_ausgabefelder(c.get(f"/api/employees/{welt['bea'].id}").json())
    assert bea["plantafel"] == "bauleitung"
    del bea["plantafel"]
    r = c.put(f"/api/employees/{welt['bea'].id}", json={**bea, "city": "Uebach"})  # ohne Kennzeichen: bleibt Bauleitung (Regel 22)
    assert r.status_code == 200 and r.json()["plantafel"] == "bauleitung"
    r = c.put(f"/api/employees/{welt['bea'].id}", json={**bea, "plantafel": "nicht_zeigen"})
    assert r.status_code == 200 and r.json()["plantafel"] == "nicht_zeigen"
    assert c.put(f"/api/employees/{welt['bea'].id}", json={**bea, "plantafel": "konto"}).status_code == 422
    assert c.put(f"/api/employees/{welt['bea'].id}", json={**bea, "show_on_planning_board": True}).json()["plantafel"] == "nicht_zeigen"


def test_ohne_zeile_die_vorgabe_aus_gruppe_und_funktion(threaded_db_session):
    db = threaded_db_session
    buero = Employee(employee_number="B-1", first_name="Ina", last_name="Office", employee_group="kaufmaennisch", job_title="Büro", active=True)
    lager = Employee(employee_number="L-1", first_name="Lars", last_name="Lager", employee_group="gewerblich", job_title="Lagerist", active=True)
    dach = _person(db, "D-1", "Max")
    db.add_all([buero, lager]); db.commit()
    assert [effective_plantafel(db, e) for e in (buero, lager, dach)] == ["nicht_zeigen", "nicht_zeigen", "einplanbar"]
    assert planning_visible_employee_ids(db) == {dach.id}


# --- Plantafel ------------------------------------------------------------------------------------------------------------------------------

def test_tafel_schickt_das_kennzeichen_und_laesst_nicht_zeigen_weg(welt):
    tafel = welt["client"].get("/api/planning", params={"start": MO.isoformat(), "end": (MO + timedelta(days=13)).isoformat()}).json()
    assert {e["name"]: e["plantafel"] for e in tafel["employees"]} == {"Tom Test": "einplanbar", "Bea Test": "bauleitung", "Paul Test": "einplanbar"}
    assert "konto" not in tafel["employees"][0]
    # die Kolonne nennt nur, wer in der Plantafel steht (wie bisher ohne Häkchen)
    assert [e["name"] for t in tafel["teams"] for e in t["employees"]] == ["Tom Test", "Bea Test"]


def test_nicht_zeigen_auch_nicht_im_einsatz_dialog(welt):
    """„+ Person“ bietet board.employees an; die Prüfung des Dialogs zeigt eine Person „nicht zeigen“ nur, wenn sie schon gewählt ist (wie bisher ohne
    Häkchen -- auch, wenn ihre Kolonne sie vorschlägt: die Besetzung bleibt, wie sie ist)."""
    from tests.test_v090_planning_board import setup_order
    auftrag = setup_order(welt["db"], "653")
    body = {"order_id": auftrag.id, "team_id": None, "employee_ids": [welt["tom"].id], "start_date": "2026-11-03", "end_date": "2026-11-04",
            "status": "vorlaeufig", "planned_hours": "8", "weitere_personen": [welt["vera"].id, welt["paul"].id, welt["bea"].id]}
    r = welt["client"].post("/api/planning/slots/pruefen", json=body)
    assert r.status_code == 200, r.text
    assert [p["name"] for p in r.json()["personen"]] == ["Tom Test", "Paul Test", "Bea Test"]  # Vera fehlt, Bauleitung bleibt einplanbar
    r = welt["client"].post("/api/planning/slots/pruefen", json={**body, "team_id": welt["nord"].id, "employee_ids": None, "weitere_personen": []})
    assert [p["name"] for p in r.json()["personen"]] == ["Tom Test", "Bea Test", "Vera Test"]  # die Kolonne schlägt sie vor (wie bisher)


def _gruppen(tafel):
    vorbereitung = f"var board = {json.dumps(tafel)};"
    [erg] = im_browser("planning.html", ["personenGruppen"], vorbereitung,
                       "AUFRUFE.push(personenGruppen().map(g => [g.titel, g.team, g.personen.map(p => p.name)]));")
    return erg


@nur_mit_node
def test_personen_nach_dem_kennzeichen():
    tafel = {"teams": [{"id": 1, "name": "Kolonne Nord", "employees": [{"id": 10, "name": "Tom", "kf": True}, {"id": 31, "name": "Bea", "kf": False}]}],
             "employees": [{"id": 10, "name": "Tom", "plantafel": "einplanbar"}, {"id": 31, "name": "Bea", "plantafel": "bauleitung"},
                           {"id": 40, "name": "Paul", "plantafel": "einplanbar"}, {"id": 41, "name": "Uwe", "plantafel": "einplanbar"},
                           {"id": 42, "name": "Ben", "plantafel": "bauleitung"}]}
    assert _gruppen(tafel) == [["Kolonne Nord", 1, ["Tom"]],                                  # Bea steht in Nord, ist aber Bauleitung
                               ["Ohne Kolonne", None, ["Paul", "Uwe"]],                       # einplanbar ohne Kolonne -- ob mit Konto, zählt nicht
                               ["Bauleitung · Termine aus dem Kalender", None, ["Bea", "Ben"]]]


@nur_mit_node
def test_ohne_bauleitung_kein_abschnitt():
    tafel = {"teams": [], "employees": [{"id": 40, "name": "Paul", "plantafel": "einplanbar"}]}
    assert _gruppen(tafel) == [["Ohne Kolonne", None, ["Paul"]]]


def test_tafel_rechnet_wie_bisher_mit_planning_board(welt):
    tafel = planning_board(welt["db"], MO, MO + timedelta(days=13))
    assert {e["id"] for e in tafel["employees"]} == {welt["tom"].id, welt["bea"].id, welt["paul"].id}
    assert set(tafel["employee_capacity"]) == {str(welt["tom"].id), str(welt["bea"].id), str(welt["paul"].id)}  # Vera ohne Kapazität


# --- Formular und Liste -------------------------------------------------------------------------------------------------------------------

def test_formular_und_liste():
    form = (ROOT / "app/templates/master_data_form.html").read_text(encoding="utf-8")
    assert ('<select id="plantafel"><option value="einplanbar">einplanbar</option><option value="bauleitung">Bauleitung</option>'
            '<option value="nicht_zeigen">nicht zeigen</option></select>') in form
    assert "el('plantafel').value=record.plantafel||'einplanbar'" in form and "plantafel:v('plantafel')||'einplanbar'" in form
    assert "showOnPlanningBoard" not in form
    liste = (ROOT / "app/templates/master_data.html").read_text(encoding="utf-8")
    assert "x.plantafel==='bauleitung'?'<span class=\"pill\">Bauleitung</span>'" in liste


# --- Migration e3b7c51a9d26 -------------------------------------------------------------------------------------------------------------------

def _probe(url, engine):
    _ok(_alembic(url, "upgrade", VORHER))
    with engine.begin() as c:
        ids = [c.execute(text("INSERT INTO employees (employee_number, first_name, last_name, employee_group, weekly_hours, active, created_at, updated_at) "
                              "VALUES (:n, :n, 'Test', 'gewerblich', 40, :a, '2026-09-01', '2026-09-01') RETURNING id"), {"n": n, "a": True}).scalar()
               for n in ("Tom", "Vera", "Ohne")]
        for i, sichtbar in zip(ids[:2], (True, False)):
            c.execute(text("INSERT INTO employee_planning_settings (employee_id, show_on_planning_board, updated_at) VALUES (:e, :s, '2026-09-01')"),
                      {"e": i, "s": sichtbar})

    def stand(spalte):
        with engine.connect() as c:
            return [c.execute(text(f"SELECT {spalte} FROM employee_planning_settings WHERE employee_id = :e"), {"e": i}).scalar() for i in ids]
    _ok(_alembic(url, "upgrade", MIGRATION))
    assert stand("plantafel") == ["einplanbar", "nicht_zeigen", None]  # ohne Zeile bleibt ohne Zeile
    with engine.begin() as c:
        c.execute(text("UPDATE employee_planning_settings SET plantafel = 'bauleitung' WHERE employee_id = :e"), {"e": ids[0]})
        neu = c.execute(text("INSERT INTO employee_planning_settings (employee_id, updated_at) VALUES (:e, '2026-09-01') RETURNING plantafel"),
                        {"e": ids[2]}).scalar()
    assert neu == "einplanbar"  # Vorgabe der Spalte
    _ok(_alembic(url, "downgrade", VORHER))
    assert [bool(x) for x in stand("show_on_planning_board")] == [True, False, True]  # Bauleitung stand in der Plantafel
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'plantafel.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_plantafel_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        _probe(url, engine)
        with engine.connect() as c:  # Index wie im Modell, die alte Spalte samt Index weg
            indizes = {r[0] for r in c.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname = :s AND tablename = 'employee_planning_settings'"),
                                               {"s": schema})}
        assert "ix_employee_planning_settings_plantafel" in indizes and "ix_employee_planning_settings_show_on_planning_board" not in indizes
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
