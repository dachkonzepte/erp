"""Version 1.9.235 (Stufe 6, R3a, Punkt 4): der Status eines Einsatzes ist vorläufig oder fest.

    Werte      vorlaeufig (Vorgabe beim Anlegen) | fest; jeder andere Wert 422 (bis 1.9.234 freier Text bis 40 Zeichen, Vorgabe „geplant“)
    Anzeige    status_label „vorläufig“/„fest“; der Dialog bietet genau die zwei; im Verlauf „Vorläufig“/„Fest“
    Migration  a7d3e5f9c214: „geplant“ -> vorlaeufig, alles andere -> fest; downgrade vorlaeufig -> geplant, fest -> bestaetigt
"""

import os
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.planning import EINSATZ_STATUS, create_slot, update_slot
from app.routers.planning import router as planning_router
from app.verlauf_namen import _STATUS
from tests.test_v090_planning_board import setup_order
from tests.test_v380_nummern_eindeutig import _alembic, _ok
from tests.test_v633_besetzung_je_einsatz import _kolonne, _person

ROOT = Path(__file__).resolve().parent.parent
MONTAG = date(2026, 11, 2)
MIGRATION = "a7d3e5f9c214"
VORHER = "f2c8d4a61e93"
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.fixture()
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    tom = _person(db, "M-1", "Tom")
    return {"db": db, "client": router_test_client(db, planning_router), "nord": _kolonne(db, "N", [tom]), "a": setup_order(db, "1")}


def _body(w, **mehr):
    return {"order_id": w["a"].id, "team_id": w["nord"].id, "start_date": MONTAG.isoformat(), "end_date": (MONTAG + timedelta(days=1)).isoformat(),
            "planned_hours": "1", **mehr}


def test_vorgabe_vorlaeufig_und_fest(welt):
    client = welt["client"]
    r = client.post("/api/planning/slots", json=_body(welt))
    assert r.status_code == 200 and (r.json()["status"], r.json()["status_label"]) == ("vorlaeufig", "vorläufig"), r.text
    r = client.put(f"/api/planning/slots/{r.json()['id']}", json={"status": "fest"})
    assert r.status_code == 200 and (r.json()["status"], r.json()["status_label"]) == ("fest", "fest"), r.text


@pytest.mark.parametrize("wert", ["geplant", "bestaetigt", "abgeschlossen", "Fest", "", "quatsch"])
def test_andere_werte_422(welt, wert):
    client = welt["client"]
    assert client.post("/api/planning/slots", json=_body(welt, status=wert)).status_code == 422
    sid = client.post("/api/planning/slots", json=_body(welt)).json()["id"]
    assert client.put(f"/api/planning/slots/{sid}", json={"status": wert}).status_code == 422


def test_geschaeftsfunktionen_pruefen_selbst(welt):
    db = welt["db"]
    with pytest.raises(ValueError, match="vorläufig"):
        create_slot(db, order_id=welt["a"].id, team_id=welt["nord"].id, start_date=MONTAG, end_date=MONTAG, status="geplant")
    slot = create_slot(db, order_id=welt["a"].id, team_id=welt["nord"].id, start_date=MONTAG, end_date=MONTAG, planned_hours=Decimal("1"))
    with pytest.raises(ValueError, match="vorläufig"):
        update_slot(db, slot.id, status="bestaetigt")
    assert EINSATZ_STATUS == {"vorlaeufig": "vorläufig", "fest": "fest"}


def test_vorlaeufig_zaehlt_wie_fest(welt):
    """Festlegung 1.9.235 Nr. 3: ein vorläufiger Einsatz zählt bei „Person doppelt“ wie ein fester."""
    client = welt["client"]
    assert client.post("/api/planning/slots", json=_body(welt, status="vorlaeufig")).status_code == 200
    zweiter = setup_order(welt["db"], "2")
    r = client.post("/api/planning/slots", json={**_body(welt, status="fest"), "order_id": zweiter.id})
    assert r.status_code == 409 and "employee" in [k["type"] for k in r.json()["warnungen"]], r.text


def test_dialog_und_verlauf():
    """Seit 1.9.248 ein Umschalter im Einsatz-Dialog (bis 1.9.247 die Auswahl „newStatus“/„editStatus“): genau vorläufig und fest, neu vorläufig."""
    seite = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")
    umschalter = re.search(r'<div[^>]*id="edStatus"[^>]*>(.*?)</div>', seite, re.S).group(1)
    assert re.findall(r'data-status="([^"]*)"', umschalter) == ["vorlaeufig", "fest"]
    assert "status:'vorlaeufig',notes:mehr.notes||''" in seite[seite.index("async function openCreate("):]  # seit 1.9.251 die Notiz aus einem Termin
    assert (_STATUS["vorlaeufig"], _STATUS["fest"]) == ("Vorläufig", "Fest")


# --- Migration a7d3e5f9c214 ---------------------------------------------------------------------------------------------------------------

ALT = ["geplant", "bestaetigt", "in_ausfuehrung", "pausiert", "abgeschlossen", "quatsch", "", "Geplant"]


def _probe(url, engine):
    from tests.test_v633_besetzung_je_einsatz import _bestand
    _ok(_alembic(url, "upgrade", VORHER))
    b = _bestand(engine)
    with engine.begin() as c:
        vorlage = c.execute(text("SELECT preparation_id, team_assignment_id FROM planning_slots WHERE id = :s"), {"s": b["slots"][0]}).one()
        ids = [c.execute(text("INSERT INTO planning_slots (preparation_id, team_assignment_id, start_date, end_date, status, created_at, updated_at) "
                              "VALUES (:p, :t, '2026-12-01', '2026-12-01', :s, '2026-09-01', '2026-09-01') RETURNING id"),
                         {"p": vorlage[0], "t": vorlage[1], "s": s}).scalar() for s in ALT]

    def stand():
        with engine.connect() as c:
            return [c.execute(text("SELECT status FROM planning_slots WHERE id = :i"), {"i": i}).scalar() for i in ids]
    _ok(_alembic(url, "upgrade", MIGRATION))
    assert stand() == ["vorlaeufig", "fest", "fest", "fest", "fest", "fest", "fest", "fest"]
    _ok(_alembic(url, "downgrade", VORHER))
    assert stand() == ["geplant", "bestaetigt", "bestaetigt", "bestaetigt", "bestaetigt", "bestaetigt", "bestaetigt", "bestaetigt"]
    _ok(_alembic(url, "upgrade", "head"))


def test_migration_auf_einem_bestand_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'status.db').as_posix()}"
    engine = create_engine(url)
    try:
        _probe(url, engine)
    finally:
        engine.dispose()


def test_migration_auf_einem_bestand_postgresql():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_status_{uuid.uuid4().hex[:8]}"
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


def test_schema_und_vorgabe_fuer_sich():
    """Seit den Gegenproben 235_1a, 235_1d, 235_1e (grün: die Geschäftsfunktion prüft ebenfalls, die Schnittstelle schickt den Status immer mit) --
    die Schemas lehnen jeden anderen Wert für sich ab, und create_slot() ohne Status legt vorläufig an."""
    from pydantic import ValidationError

    from app.schemas import PlanningSlotCreate, PlanningSlotUpdate
    with pytest.raises(ValidationError):
        PlanningSlotCreate(order_id=1, team_id=1, start_date=MONTAG, end_date=MONTAG, status="geplant")
    with pytest.raises(ValidationError):
        PlanningSlotUpdate(status="bestaetigt")
    assert PlanningSlotCreate(order_id=1, team_id=1, start_date=MONTAG, end_date=MONTAG).status == "vorlaeufig"


def test_create_slot_ohne_status_ist_vorlaeufig(welt):
    slot = create_slot(welt["db"], order_id=welt["a"].id, team_id=welt["nord"].id, start_date=MONTAG, end_date=MONTAG, planned_hours=Decimal("1"))
    assert slot.status == "vorlaeufig"
