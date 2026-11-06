"""Version 1.9.240 (Stufe 6, R3b, Punkt 2): Kranvermietung als Art des Einsatzes.

    Art          baustelle (an einem Auftrag) oder kranvermietung; neu ohne Angabe baustelle; die Art bleibt, wie sie angelegt wurde
    Anlegen      mit Kunde: Projekt und Auftrag „Kranvermietung nach Aufwand“ wie der Schnellauftrag (Position 0,00 €, Auftrag nach Aufwand),
                 in derselben Transaktion -- eine Warnung lässt nichts zurück; oder an einem bestehenden Auftrag
    Regeln       keine Kolonne, mindestens ein Gerät (der Kran), Bediener = Besetzung, auch keine
    Migration    b5f1c7e2a948: jeder bestehende Einsatz ist „baustelle“
"""

import os
import uuid
from datetime import date, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select, text

from app.invoices import effort_only
from app.main import create_customer
from app.models import Order, PlanningSlot, Project, Property, Quote
from app.planning import BesetzungUngueltig, GeraeteUngueltig, create_slot, list_todays_assignments_for_employee, update_slot
from app.routers.planning import router as planning_router
from app.schemas import CustomerCreate, PlanningSlotCreate
from tests.test_v090_planning_board import setup_order
from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.test_v633_besetzung_je_einsatz import _kolonne, _person
from tests.test_v634_geraete_je_einsatz import _geraet, _geraete

MONTAG = date(2026, 11, 2)
MIGRATION = "b5f1c7e2a948"
VORHER = "a7d3e5f9c214"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.fixture()
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    tom = _person(db, "M-1", "Tom")
    kunde = create_customer(CustomerCreate(last_name="Kranmieter"), db)
    return {"db": db, "client": router_test_client(db, planning_router), "tom": tom, "kunde": kunde, "kran": _geraet(db, "K-1", "Kran 30 m"),
            "nord": _kolonne(db, "N", [tom]), "a": setup_order(db, "1")}


def _miete(w, **mehr):
    return {"art": "kranvermietung", "customer_id": w["kunde"].id, "geraete": [{"resource_id": w["kran"]}], "start_date": MONTAG.isoformat(),
            "end_date": (MONTAG + timedelta(days=1)).isoformat(), **mehr}


def _zaehlen(db):
    db.expire_all()
    return tuple(db.scalar(select(func.count()).select_from(m)) for m in (Project, Quote, Order, PlanningSlot))


def test_mit_kunde_entstehen_projekt_und_auftrag_nach_aufwand(welt):
    db, client = welt["db"], welt["client"]
    vorher = _zaehlen(db)
    r = client.post("/api/planning/slots", json=_miete(welt))
    assert r.status_code == 200, r.text
    e = r.json()
    assert (e["art"], e["art_label"], e["team_id"], e["employees"]) == ("kranvermietung", "Kranvermietung", None, [])
    assert [g["id"] for g in e["resources"]] == [welt["kran"]]
    assert _zaehlen(db) == (vorher[0] + 1, vorher[1] + 1, vorher[2] + 1, vorher[3] + 1)
    auftrag = db.get(Order, e["order_id"])
    assert (auftrag.customer_id, auftrag.title, auftrag.project.name) == (welt["kunde"].id, "Kranvermietung", "Kranvermietung")
    assert [(i.short_text, i.unit_price) for i in auftrag.items] == [("Kranvermietung nach Aufwand", 0)]
    assert effort_only(auftrag)  # abgerechnet wie jeder Auftrag nach Aufwand -- die Plantafel schreibt keine Beträge
    assert auftrag.execution_start == MONTAG


def test_mit_titel_und_bediener(welt):
    db, client = welt["db"], welt["client"]
    r = client.post("/api/planning/slots", json=_miete(welt, titel="Kran für Dachdecker Meier", employee_ids=[welt["tom"].id]))
    assert r.status_code == 200, r.text
    assert [p["id"] for p in r.json()["employees"]] == [welt["tom"].id]
    assert db.get(Order, r.json()["order_id"]).project.name == "Kran für Dachdecker Meier"
    assert [a["order_id"] for a in list_todays_assignments_for_employee(db, welt["tom"].id, MONTAG)] == [r.json()["order_id"]]


def test_an_einem_bestehenden_auftrag(welt):
    db, client = welt["db"], welt["client"]
    vorher = _zaehlen(db)
    body = _miete(welt, order_id=welt["a"].id)
    del body["customer_id"]
    r = client.post("/api/planning/slots", json=body)
    assert r.status_code == 200 and r.json()["order_id"] == welt["a"].id and r.json()["art"] == "kranvermietung", r.text
    assert _zaehlen(db) == (vorher[0], vorher[1], vorher[2], vorher[3] + 1)


def test_eine_warnung_laesst_nichts_zurueck(welt):
    """Der Kran ist am Montag schon an einer Baustelle: die Kranvermietung fragt zurück, und es bleibt nichts -- kein Projekt, kein Angebot, kein
    Auftrag, kein Einsatz; mit „trotzdem_planen“ entsteht alles."""
    db, client = welt["db"], welt["client"]
    assert client.post("/api/planning/slots", json={"order_id": welt["a"].id, "team_id": welt["nord"].id, "geraete": [{"resource_id": welt["kran"]}],
                                                    "start_date": MONTAG.isoformat(), "end_date": MONTAG.isoformat()}).status_code == 200
    vorher = _zaehlen(db)
    r = client.post("/api/planning/slots", json=_miete(welt))
    assert r.status_code == 409 and [w["type"] for w in r.json()["warnungen"]] == ["resource"], r.text
    assert _zaehlen(db) == vorher
    r = client.post("/api/planning/slots", json=_miete(welt, trotzdem_planen=True))
    assert r.status_code == 200, r.text
    assert _zaehlen(db) == (vorher[0] + 1, vorher[1] + 1, vorher[2] + 1, vorher[3] + 1)


@pytest.mark.parametrize("aenderung", [
    {"geraete": []}, {"geraete": None}, {"team_id": "nord"}, {"order_id": "a"}, {"customer_id": None},
])
def test_regeln_der_kranvermietung_422(welt, aenderung):
    body = _miete(welt)
    for k, v in aenderung.items():
        body[k] = welt["nord"].id if v == "nord" else welt["a"].id if v == "a" else v
    if body.get("geraete") is None:
        body.pop("geraete")
    r = welt["client"].post("/api/planning/slots", json=body)
    assert r.status_code == 422, (aenderung, r.text)


def test_baustelle_braucht_einen_auftrag(welt):
    client = welt["client"]
    body = {"team_id": welt["nord"].id, "start_date": MONTAG.isoformat(), "end_date": MONTAG.isoformat()}
    assert client.post("/api/planning/slots", json=body).status_code == 422
    assert client.post("/api/planning/slots", json={**body, "customer_id": welt["kunde"].id}).status_code == 422
    r = client.post("/api/planning/slots", json={**body, "order_id": welt["a"].id})
    assert r.status_code == 200 and (r.json()["art"], r.json()["art_label"]) == ("baustelle", "Baustelle"), r.text


def test_schema_fuer_sich():
    """Das Schema lehnt ab, auch wenn die Geschäftsfunktion es ebenfalls täte (Lehre aus 233_5a/235_1a)."""
    tag = MONTAG.isoformat()
    for body in ({"art": "kranvermietung", "customer_id": 1, "start_date": tag, "end_date": tag},
                 {"art": "kranvermietung", "customer_id": 1, "team_id": 1, "geraete": [{"resource_id": 1}], "start_date": tag, "end_date": tag},
                 {"art": "kranvermietung", "customer_id": 1, "order_id": 1, "geraete": [{"resource_id": 1}], "start_date": tag, "end_date": tag},
                 {"art": "baustelle", "customer_id": 1, "order_id": 1, "team_id": 1, "start_date": tag, "end_date": tag},
                 {"art": "flug", "order_id": 1, "team_id": 1, "start_date": tag, "end_date": tag}):
        with pytest.raises(ValidationError):
            PlanningSlotCreate(**body)
    assert PlanningSlotCreate(art="kranvermietung", customer_id=1, geraete=[{"resource_id": 1}], start_date=tag, end_date=tag).employee_ids is None


def test_geschaeftsfunktion_prueft_selbst(welt):
    db = welt["db"]
    with pytest.raises(GeraeteUngueltig):
        create_slot(db, order_id=None, customer_id=welt["kunde"].id, art="kranvermietung", team_id=None, start_date=MONTAG, end_date=MONTAG)
    with pytest.raises(BesetzungUngueltig):
        create_slot(db, order_id=welt["a"].id, art="kranvermietung", team_id=welt["nord"].id, start_date=MONTAG, end_date=MONTAG,
                    geraete=[{"resource_id": welt["kran"]}])
    with pytest.raises(ValueError):
        create_slot(db, order_id=welt["a"].id, customer_id=welt["kunde"].id, art="kranvermietung", team_id=None, start_date=MONTAG, end_date=MONTAG,
                    geraete=[{"resource_id": welt["kran"]}])
    with pytest.raises(ValueError):
        create_slot(db, order_id=None, art="kranvermietung", team_id=None, start_date=MONTAG, end_date=MONTAG, geraete=[{"resource_id": welt["kran"]}])
    with pytest.raises(ValueError):
        create_slot(db, order_id=welt["a"].id, art="flug", team_id=welt["nord"].id, start_date=MONTAG, end_date=MONTAG)
    with pytest.raises(ValueError):  # Baustelle mit Kunde
        create_slot(db, order_id=welt["a"].id, customer_id=welt["kunde"].id, team_id=welt["nord"].id, start_date=MONTAG, end_date=MONTAG)
    slot = create_slot(db, order_id=welt["a"].id, team_id=welt["nord"].id, start_date=MONTAG, end_date=MONTAG)
    assert slot.art == "baustelle"


def test_abgelehnt_bleibt_nichts(welt):
    """Eine Ablehnung nach dem Anlegen von Projekt und Auftrag (Anfahrt nicht unter der täglichen Arbeitszeit): 422, und die Sitzung hält nichts
    davon -- auch nicht, wenn sie danach weiterbenutzt wird (hier teilen sich die Anfragen eine Sitzung)."""
    db, client = welt["db"], welt["client"]
    vorher = _zaehlen(db)
    r = client.post("/api/planning/slots", json=_miete(welt, travel_hours_per_employee_day="23"))
    assert r.status_code == 422, r.text
    assert _zaehlen(db) == vorher


def test_nicht_an_das_modul_wartungen_gebunden(welt):
    from app.models import EnabledModule
    db, client = welt["db"], welt["client"]
    db.add(EnabledModule(module_key="wartungen", enabled=False))
    db.commit()
    assert client.post("/api/planning/slots", json=_miete(welt)).status_code == 200


def test_unbekannter_kunde_und_fremdes_objekt(welt):
    db, client = welt["db"], welt["client"]
    assert client.post("/api/planning/slots", json=_miete(welt, customer_id=99999)).status_code == 404
    anderer = create_customer(CustomerCreate(last_name="Hausverwaltung"), db)
    objekt = Property(customer_id=anderer.id, name="Wohnanlage", street="Ring 1", postal_code="52531", city="Übach")
    db.add(objekt)
    db.commit()
    vorher = _zaehlen(db)
    assert client.post("/api/planning/slots", json=_miete(welt, property_id=objekt.id)).status_code == 409
    assert _zaehlen(db) == vorher
    r = client.post("/api/planning/slots", json=_miete(welt, property_id=objekt.id, confirm_property_customer=True))
    assert r.status_code == 200 and db.get(Order, r.json()["order_id"]).project.property_id == objekt.id, r.text


def test_aendern_einer_kranvermietung(welt):
    db, client = welt["db"], welt["client"]
    e = client.post("/api/planning/slots", json=_miete(welt, employee_ids=[welt["tom"].id])).json()
    url = f"/api/planning/slots/{e['id']}"
    assert client.put(url, json={"team_id": welt["nord"].id}).status_code == 422  # keine Kolonne
    # Gegenprobe 240_5b (erst grün): mit dem Kran in derselben Anfrage fällt kein Gerät weg -- abgelehnt wird allein wegen der Kolonne
    r = client.put(url, json={"team_id": welt["nord"].id, "geraete": [{"resource_id": welt["kran"]}]})
    assert r.status_code == 422 and "keine Kolonne" in r.json()["detail"], r.text
    assert client.put(url, json={"geraete": []}).status_code == 422  # der Kran bleibt
    r = client.put(url, json={"employee_ids": []})  # ohne Bediener geht
    assert r.status_code == 200 and r.json()["employees"] == [], r.text
    r = client.put(url, json={"start_date": (MONTAG + timedelta(days=7)).isoformat(), "end_date": (MONTAG + timedelta(days=8)).isoformat()})
    assert r.status_code == 200 and r.json()["art"] == "kranvermietung", r.text
    assert _geraete(db, e["id"]) == [(welt["kran"], None)]
    # ein Gerät nur an einem Tag, der beim Kürzen wegfällt: ohne Kran 422, nichts geändert
    tag2 = (MONTAG + timedelta(days=8)).isoformat()
    assert client.put(url, json={"geraete": [{"resource_id": welt["kran"], "tage": [tag2]}]}).status_code == 200
    assert client.put(url, json={"end_date": (MONTAG + timedelta(days=7)).isoformat()}).status_code == 422
    db.expire_all()
    assert db.get(PlanningSlot, e["id"]).end_date == MONTAG + timedelta(days=8)


def test_baustelle_ohne_kolonne_braucht_weiter_eine_person(welt):
    client = welt["client"]
    e = client.post("/api/planning/slots", json={"order_id": welt["a"].id, "employee_ids": [welt["tom"].id], "start_date": MONTAG.isoformat(),
                                                 "end_date": MONTAG.isoformat()}).json()
    assert client.put(f"/api/planning/slots/{e['id']}", json={"employee_ids": []}).status_code == 422
    with pytest.raises(BesetzungUngueltig):
        update_slot(welt["db"], e["id"], employee_ids=[])


# --- Migration b5f1c7e2a948 ---------------------------------------------------------------------------------------------------------------

def _probe(url, engine):
    from tests.test_v633_besetzung_je_einsatz import _bestand
    _ok(_alembic(url, "upgrade", VORHER))
    b = _bestand(engine)
    _ok(_alembic(url, "upgrade", MIGRATION))
    with engine.connect() as c:
        assert [c.execute(text("SELECT art FROM planning_slots WHERE id = :i"), {"i": i}).scalar() for i in b["slots"]] == ["baustelle"] * len(b["slots"])
    _ok(_alembic(url, "downgrade", VORHER))
    with engine.connect() as c:
        spalten = [z[1] for z in c.execute(text("PRAGMA table_info(planning_slots)"))] if engine.dialect.name == "sqlite" else [
            z[0] for z in c.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'planning_slots' "
                                         "AND table_schema = current_schema()"))]
    assert "art" not in spalten
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'art.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_art_{uuid.uuid4().hex[:8]}"
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
