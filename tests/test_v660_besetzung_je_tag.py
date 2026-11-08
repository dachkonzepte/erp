"""Version 1.9.260 (Stufe 6, R5a, Punkt 1): die Besetzung je Tag -- Spalte, Schreibweg, Normalform, Mitnehmen, die Falle.

    Spalte      planning_slot_employees.tage wie planning_slot_resources.tage: JSON-Liste einzelner Tage im Einsatz, leer (NULL) = alle Tage; der Bestand
                bleibt leer (alle Tage)
    Schreibweg  besetzung [{employee_id, tage}] beim Anlegen, Ändern und Prüfen; employee_ids und der Vorschlag der Kolonne heißen alle Tage; beides zugleich
                422; Tage nur im Einsatz, keine leere Liste (422); doppelt genannt zählt die erste
    Normalform  auf dem Server, für Personen und Geräte: alle Tage des Einsatzes einzeln genannt heißt NULL
    Mitnehmen   ein neuer Zeitraum nimmt die einzelnen Tage der Personen mit wie die der Geräte (gleiche Dauer verschoben, sonst nur die Tage im neuen
                Zeitraum; ohne verbleibenden Tag fällt die Person weg); wer an allen Tagen steht, steht danach an allen Tagen des neuen Zeitraums
    Die Falle   update_slot(alle_tage_mitnehmen=False) -- wer in der Änderung nicht gesetzt wird und an allen Tagen stand, steht danach an genau den bisherigen
                Tagen (sonst stünde bei einer Verlängerung die ganze Kolonne auch am neuen Tag)
    Dialog      die Seite hält die Besetzung mit den Tagen und schickt besetzung statt employee_ids (eine Änderung an den Personen verliert keine Tage)
    Migration   b6e4d2a9c731: Spalte dazu, nichts geschrieben; downgrade bricht ab, solange jemand an einzelnen Tagen steht
"""

import json
import os
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, text

from app.main import create_team
from app.models import AuditLog, PlanningSlotEmployee, PlanningSlotResource
from app.planning import BesetzungUngueltig, GeraeteUngueltig, PlanungsWarnung, _tage_der_zeile, create_slot, slot_to_dict, update_slot
from app.routers.planning import router as planning_router
from app.routers.resource_planning import router as resource_router
from app.schemas import TeamCreate, TeamEmployeeInput, TeamResourceInput
from tests.test_v090_planning_board import setup_order
from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v633_besetzung_je_einsatz import _person
from tests.test_v634_geraete_je_einsatz import _geraet

MO = date(2026, 11, 2)  # KW 45, Montag
MIGRATION = "b6e4d2a9c731"
VORHER = "e3b7c51a9d26"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
D1 = Decimal("1")


def _tag(n):
    return MO + timedelta(days=n)


def _iso(n):
    return _tag(n).isoformat()


def _personen(db, slot_id):
    db.expire_all()
    return [(x.employee_id, json.loads(x.tage) if x.tage else None)
            for x in db.scalars(select(PlanningSlotEmployee).where(PlanningSlotEmployee.slot_id == slot_id).order_by(PlanningSlotEmployee.id))]


def _geraete(db, slot_id):
    db.expire_all()
    return [(x.resource_id, json.loads(x.tage) if x.tage else None)
            for x in db.scalars(select(PlanningSlotResource).where(PlanningSlotResource.slot_id == slot_id).order_by(PlanningSlotResource.id))]


@pytest.fixture()
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    tom, mia, kai = _person(db, "M-1", "Tom"), _person(db, "M-2", "Mia"), _person(db, "M-3", "Kai")
    alt = _person(db, "M-9", "Alt", aktiv=False)
    pritsche, kran = _geraet(db, "F-1", "Pritsche"), _geraet(db, "K-1", "Kran")
    nord = create_team(TeamCreate(team_number="N", name="Nord", employees=[TeamEmployeeInput(employee_id=tom.id, role="Monteur"),
                                                                           TeamEmployeeInput(employee_id=mia.id, role="Monteur")],
                                  resources=[TeamResourceInput(resource_id=pritsche, role="Standard")]), db)
    return {"db": db, "client": router_test_client(db, planning_router, resource_router), "tom": tom.id, "mia": mia.id, "kai": kai.id, "alt": alt.id,
            "pritsche": pritsche, "kran": kran, "nord": nord, "a": setup_order(db, "660a"), "b": setup_order(db, "660b")}


def _nord(w, start=0, ende=2, **mehr):
    """Kolonne Nord (Tom, Mia, Pritsche -- alle an allen Tagen) von Mo + start bis Mo + ende."""
    return create_slot(w["db"], order_id=w["a"].id, team_id=w["nord"].id, start_date=_tag(start), end_date=_tag(ende), planned_hours=D1, **mehr)


# --- Bestand und Schreibweg ---------------------------------------------------------------------------------------------------------------

def test_employee_ids_und_kolonne_heissen_alle_tage(welt):
    db = welt["db"]
    slot = _nord(welt)
    assert _personen(db, slot.id) == [(welt["tom"], None), (welt["mia"], None)]
    einzeln = create_slot(db, order_id=welt["b"].id, team_id=None, employee_ids=[welt["kai"]], start_date=_tag(0), end_date=_tag(2), planned_hours=D1)
    assert _personen(db, einzeln.id) == [(welt["kai"], None)]
    assert [e["tage"] for e in slot_to_dict(slot, db=db)["employees"]] == [None, None]


def test_besetzung_mit_tagen_anlegen(welt):
    db = welt["db"]
    r = welt["client"].post("/api/planning/slots", json={"order_id": welt["b"].id, "team_id": None, "start_date": _iso(0), "end_date": _iso(2),
                                                        "planned_hours": "1", "besetzung": [{"employee_id": welt["kai"], "tage": [_iso(2), _iso(1)]},
                                                                                            {"employee_id": welt["tom"]}]})
    assert r.status_code == 200, r.text
    assert _personen(db, r.json()["id"]) == [(welt["kai"], [_iso(1), _iso(2)]), (welt["tom"], None)]
    assert {e["id"]: e["tage"] for e in r.json()["employees"]} == {welt["kai"]: [_iso(1), _iso(2)], welt["tom"]: None}
    zeile = db.scalar(select(PlanningSlotEmployee).where(PlanningSlotEmployee.employee_id == welt["kai"]))
    assert _tage_der_zeile(_slot(db, r.json()["id"]), zeile) == {_tag(1), _tag(2)}


def _slot(db, slot_id):
    from app.models import PlanningSlot
    return db.get(PlanningSlot, slot_id)


@pytest.mark.parametrize("person, grund", [
    ({"tage": [_iso(5)]}, "liegt außerhalb des Einsatzes"),
    ({"tage": []}, "mindestens einen Tag"),
])
def test_tage_einer_person_nur_im_einsatz(welt, person, grund):
    r = welt["client"].post("/api/planning/slots", json={"order_id": welt["b"].id, "team_id": None, "start_date": _iso(0), "end_date": _iso(2),
                                                        "planned_hours": "1", "besetzung": [{"employee_id": welt["kai"], **person}]})
    assert r.status_code == 422 and grund in r.text, r.text


def test_unbekannt_inaktiv_und_beides_zugleich(welt):
    client = welt["client"]
    body = {"order_id": welt["b"].id, "team_id": None, "start_date": _iso(0), "end_date": _iso(2), "planned_hours": "1"}
    assert client.post("/api/planning/slots", json={**body, "besetzung": [{"employee_id": 99999}]}).status_code == 422
    assert client.post("/api/planning/slots", json={**body, "besetzung": [{"employee_id": welt["alt"]}]}).status_code == 422
    r = client.post("/api/planning/slots", json={**body, "employee_ids": [welt["kai"]], "besetzung": [{"employee_id": welt["kai"]}]})
    assert r.status_code == 422 and "nicht beides" in r.text
    slot = _nord(welt)
    r = client.put(f"/api/planning/slots/{slot.id}", json={"employee_ids": [welt["kai"]], "besetzung": [{"employee_id": welt["kai"]}]})
    assert r.status_code == 422 and "nicht beides" in r.text
    with pytest.raises(BesetzungUngueltig, match="nicht beides"):
        update_slot(welt["db"], slot.id, employee_ids=[welt["kai"]], besetzung=[{"employee_id": welt["kai"], "tage": None}])
    assert client.put(f"/api/planning/slots/{slot.id}", json={"besetzung": None}).status_code == 422  # null heißt nicht „unverändert“


def test_doppelt_genannt_zaehlt_die_erste(welt):
    db = welt["db"]
    slot = create_slot(db, order_id=welt["b"].id, team_id=None, start_date=_tag(0), end_date=_tag(2), planned_hours=D1,
                       besetzung=[{"employee_id": welt["kai"], "tage": [_tag(0)]}, {"employee_id": welt["kai"], "tage": None}])
    assert _personen(db, slot.id) == [(welt["kai"], [_iso(0)])]


def test_normalform_alle_tage_heisst_null_auch_bei_geraeten(welt):
    db = welt["db"]
    slot = create_slot(db, order_id=welt["b"].id, team_id=None, start_date=_tag(0), end_date=_tag(2), planned_hours=D1,
                       besetzung=[{"employee_id": welt["kai"], "tage": [_tag(2), _tag(0), _tag(1)]}],
                       geraete=[{"resource_id": welt["kran"], "tage": [_tag(0), _tag(1), _tag(2)]}])
    assert _personen(db, slot.id) == [(welt["kai"], None)]
    assert _geraete(db, slot.id) == [(welt["kran"], None)]


def test_aendern_setzt_genau_und_ein_teil_update_laesst_die_tage(welt):
    db, client = welt["db"], welt["client"]
    slot = _nord(welt)
    r = client.put(f"/api/planning/slots/{slot.id}", json={"besetzung": [{"employee_id": welt["tom"], "tage": [_iso(0)]}, {"employee_id": welt["mia"]}],
                                                          "trotzdem_planen": True})
    assert r.status_code == 200, r.text
    assert _personen(db, slot.id) == [(welt["tom"], [_iso(0)]), (welt["mia"], None)]
    assert client.put(f"/api/planning/slots/{slot.id}", json={"notes": "Notiz"}).status_code == 200
    assert _personen(db, slot.id) == [(welt["tom"], [_iso(0)]), (welt["mia"], None)]


def test_geaenderte_tage_fragen_zurueck_wie_die_besetzung(welt):
    db = welt["db"]
    slot = _nord(welt)
    create_slot(db, order_id=welt["b"].id, team_id=None, employee_ids=[welt["tom"]], start_date=_tag(0), end_date=_tag(0), planned_hours=D1,
                trotzdem_planen=True)
    with pytest.raises(PlanungsWarnung):  # nur die Tage von Tom ändern sich -- auch das fragt zurück
        update_slot(db, slot.id, besetzung=[{"employee_id": welt["tom"], "tage": [_tag(0), _tag(1)]}, {"employee_id": welt["mia"], "tage": None}])
    assert _personen(db, slot.id) == [(welt["tom"], None), (welt["mia"], None)]
    update_slot(db, slot.id, notes="nur die Notiz")  # fragt nicht
    assert _personen(db, slot.id) == [(welt["tom"], None), (welt["mia"], None)]


def test_pruefung_nennt_die_tage_je_person(welt):
    slot = _nord(welt, besetzung=[{"employee_id": welt["tom"], "tage": [_tag(0), _tag(2)]}, {"employee_id": welt["mia"], "tage": None}])
    r = welt["client"].post(f"/api/planning/slots/{slot.id}/pruefen", json={})
    assert r.status_code == 200, r.text
    assert [(p["name"], p["tage"], p["tage_text"]) for p in r.json()["personen"]] == [
        ("Tom Test", [_iso(0), _iso(2)], "nur 02., 04.11."), ("Mia Test", None, "alle Tage")]


# --- Mitnehmen ----------------------------------------------------------------------------------------------------------------------------

def test_verschieben_nimmt_die_tage_mit(welt):
    db = welt["db"]
    slot = _nord(welt, besetzung=[{"employee_id": welt["tom"], "tage": [_tag(1)]}, {"employee_id": welt["mia"], "tage": None}])
    update_slot(db, slot.id, start_date=_tag(7), end_date=_tag(9), trotzdem_planen=True)
    assert _personen(db, slot.id) == [(welt["tom"], [_iso(8)]), (welt["mia"], None)]


def test_anderer_zeitraum_laesst_die_tage_darin_und_wer_keinen_hat_faellt_weg(welt):
    db = welt["db"]
    slot = _nord(welt, besetzung=[{"employee_id": welt["tom"], "tage": [_tag(2)]}, {"employee_id": welt["mia"], "tage": [_tag(0), _tag(1)]}])
    update_slot(db, slot.id, end_date=_tag(1), trotzdem_planen=True)
    assert _personen(db, slot.id) == [(welt["mia"], None)]  # Tom hatte nur Mi; Mia steht an allen Tagen Mo–Di -> Normalform


# --- Die Falle ----------------------------------------------------------------------------------------------------------------------------

def test_falle_ende_aendern_nimmt_alle_tage_mit(welt):
    """Der Dialog (und Ziehen des ganzen Einsatzes): wer an allen Tagen steht, steht danach an allen Tagen des neuen Zeitraums -- wie bei den Geräten."""
    db = welt["db"]
    slot = _nord(welt)
    update_slot(db, slot.id, end_date=_tag(3), trotzdem_planen=True)
    s = _slot(db, slot.id)
    assert all(_tage_der_zeile(s, x) == {_tag(n) for n in range(4)} for x in s.besetzung)
    assert _geraete(db, slot.id) == [(welt["pritsche"], None)]


def test_falle_tag_aktion_schreibt_die_anderen_fest(welt):
    """Die Tag-Aktion (ab R5b): nur das Gesetzte steht am neuen Tag -- Tom, Mia und die Pritsche behalten genau ihre Tage Mo–Mi."""
    db = welt["db"]
    slot = _nord(welt)
    update_slot(db, slot.id, end_date=_tag(3), alle_tage_mitnehmen=False, trotzdem_planen=True,
                geraete=[{"resource_id": welt["pritsche"], "tage": [_tag(0), _tag(1), _tag(2)]}, {"resource_id": welt["kran"], "tage": [_tag(3)]}])
    bisher = [_iso(0), _iso(1), _iso(2)]
    assert _personen(db, slot.id) == [(welt["tom"], bisher), (welt["mia"], bisher)]
    assert _geraete(db, slot.id) == [(welt["pritsche"], bisher), (welt["kran"], [_iso(3)])]
    s = _slot(db, slot.id)
    assert (s.start_date, s.end_date) == (_tag(0), _tag(3))


def test_falle_tag_aktion_schreibt_auch_ungenannte_geraete_fest(welt):
    db = welt["db"]
    slot = _nord(welt)
    update_slot(db, slot.id, end_date=_tag(3), alle_tage_mitnehmen=False, trotzdem_planen=True,
                besetzung=[{"employee_id": welt["tom"], "tage": [_tag(0), _tag(1), _tag(2)]}, {"employee_id": welt["kai"], "tage": [_tag(3)]}])
    assert _geraete(db, slot.id) == [(welt["pritsche"], [_iso(0), _iso(1), _iso(2)])]
    assert _personen(db, slot.id) == [(welt["tom"], [_iso(0), _iso(1), _iso(2)]), (welt["kai"], [_iso(3)])]


def test_falle_gesetzt_heisst_wie_gesetzt(welt):
    """Was die Änderung selbst setzt, gilt so -- auch „alle Tage“ (dann eben die des neuen Zeitraums)."""
    db = welt["db"]
    slot = _nord(welt)
    update_slot(db, slot.id, end_date=_tag(3), alle_tage_mitnehmen=False, trotzdem_planen=True,
                besetzung=[{"employee_id": welt["tom"], "tage": None}])
    assert _personen(db, slot.id) == [(welt["tom"], None)]


# --- Verlauf ------------------------------------------------------------------------------------------------------------------------------

def test_aenderungsprotokoll_nennt_die_tage(welt):
    db = welt["db"]
    slot = _nord(welt)
    update_slot(db, slot.id, besetzung=[{"employee_id": welt["tom"], "tage": [_tag(1)]}, {"employee_id": welt["mia"], "tage": None}], trotzdem_planen=True)
    zeilen = db.scalars(select(AuditLog).where(AuditLog.entity_type == "Plantafel-Besetzung", AuditLog.entity_id == str(slot.id),
                                               AuditLog.field_name == "tage")).all()
    assert [(z.entity_label, z.field_label, z.old_value, z.new_value) for z in zeilen] == [("Tom Test", "Tage", None, json.dumps([_iso(1)]))]


# --- Dialog -------------------------------------------------------------------------------------------------------------------------------

@nur_mit_node
def test_dialog_schickt_die_besetzung_mit_den_tagen():
    felder = ("['edKolonne','1'],['edVon','2026-11-02'],['edBis','2026-11-04'],['edNotiz',''],['edStunden',''],['edAnfahrt','0'],['edAuftrag','5'],"
              "['edBezug','kunde'],['edKunde',''],['edTitel2','']")
    vorbereitung = (f"for (const [i, v] of [{felder}]) document.getElementById(i).value = v; var geaendert = new Set(); "
                    "var einsatz = {id: 3, art: 'baustelle', order_id: 5, team_id: 1, besetzung: [{employee_id: 7, tage: ['2026-11-03']}, "
                    "{employee_id: 8, tage: null}], geraete: null, start_date: '2026-11-02', end_date: '2026-11-04', status: 'vorlaeufig', notes: '', "
                    "planned_hours: null, travel: 0, bezug: 'kunde'};")
    ablauf = ("felderLesen(); AUFRUFE.push({ohne: einsatzWerte()});"
              "einsatz.besetzung = einsatz.besetzung.concat([{employee_id: 9, tage: null}]); geaendert.add('besetzung');"
              "AUFRUFE.push({mit: einsatzWerte(), fragt: einsatzFragt()});")
    aufrufe = im_browser("planning.html", ["felderLesen", "einsatzWerte", "einsatzFragt"], vorbereitung, ablauf)
    ohne, mit = aufrufe[-2]["ohne"], aufrufe[-1]
    assert ohne == {}  # unverändert: nichts
    assert mit["mit"]["besetzung"] == [{"employee_id": 7, "tage": ["2026-11-03"]}, {"employee_id": 8, "tage": None}, {"employee_id": 9, "tage": None}]
    assert "employee_ids" not in mit["mit"] and mit["fragt"] is True


def test_dialog_haelt_die_tage_aus_der_pruefung():
    from pathlib import Path
    seite = (Path(__file__).resolve().parent.parent / "app/templates/planning.html").read_text(encoding="utf-8")
    assert "einsatz.besetzung=p.personen.filter(x=>x.gewaehlt).map(x=>({employee_id:x.id,tage:x.tage??null}))" in seite
    assert "employee_ids:s.employees" not in seite and "neu('employee_ids'" not in seite


# --- Migration b6e4d2a9c731 ---------------------------------------------------------------------------------------------------------------

def _probe(url, engine):
    from tests.test_v633_besetzung_je_einsatz import _bestand
    _ok(_alembic(url, "upgrade", VORHER))
    b = _bestand(engine)
    s = b["slots"]
    with engine.begin() as c:
        for slot_id, person in ((s[0], "Tom"), (s[0], "Mia"), (s[2], "Kai")):
            c.execute(text("INSERT INTO planning_slot_employees (slot_id, employee_id, created_at) VALUES (:s, :e, '2026-09-01')"),
                      {"s": slot_id, "e": b["ids"][person]})
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.connect() as c:
        stand = [tuple(z) for z in c.execute(text("SELECT slot_id, employee_id, tage FROM planning_slot_employees ORDER BY id"))]
    assert stand == [(s[0], b["ids"]["Tom"], None), (s[0], b["ids"]["Mia"], None), (s[2], b["ids"]["Kai"], None)]  # alle Tage
    with engine.begin() as c:
        c.execute(text("UPDATE planning_slot_employees SET tage = '[\"2026-11-03\"]' WHERE employee_id = :e"), {"e": b["ids"]["Mia"]})
    nein = _alembic(url, "downgrade", VORHER)
    assert nein.returncode != 0 and "Downgrade abgebrochen" in (nein.stdout + nein.stderr), nein.stdout + nein.stderr
    with engine.connect() as c:
        assert c.execute(text("SELECT tage FROM planning_slot_employees WHERE employee_id = :e"), {"e": b["ids"]["Mia"]}).scalar() == '["2026-11-03"]'
    with engine.begin() as c:
        c.execute(text("UPDATE planning_slot_employees SET tage = NULL"))
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        spalten = [z[1] if engine.dialect.name == "sqlite" else z[0] for z in (
            c.execute(text("PRAGMA table_info(planning_slot_employees)")) if engine.dialect.name == "sqlite" else
            c.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'planning_slot_employees' "
                           "AND table_schema = current_schema()")))]
        assert "tage" not in spalten and c.execute(text("SELECT count(*) FROM planning_slot_employees")).scalar() == 3
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'tage.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_tage_{uuid.uuid4().hex[:8]}"
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
