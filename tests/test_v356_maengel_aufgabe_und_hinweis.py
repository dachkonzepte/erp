"""Version 1.8.54 -- Stufe 2c-2b, Nacharbeiten Punkt 2 und 3 (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung
1.8.53 und 1.8.54").

- Die Aufgabe folgt dem Status des Mangels: "beseitigt" (Büro oder Monteur) erledigt "Mangel beseitigen" und legt
  "Beseitigung abnehmen lassen" an; zurück auf "offen" erledigt diese und legt wieder "Mangel beseitigen" an (Titel
  "Erneut beseitigen – …"); "Beseitigung abgenommen", "erledigt ohne Beseitigung" und Verwerfen erledigen die aktuelle.
  In derselben Transaktion wie der Eintrag; die neue Aufgabe steht am Eintrag (DefectEvent.task_id). Der Mangel bleibt
  die Wahrheit: eine erledigte Aufgabe ändert an ihm nichts.
- Zur Meldung "beseitigt" ein optionaler kurzer Hinweis des Monteurs (höchstens 500 Zeichen), gespeichert als Text des
  Eintrags (im gebundenen Inhalt), nur fürs Büro sichtbar -- nie in /mobil, nie in Aufgabe oder Antwort der Meldung.

Gegen PostgreSQL (opt-in über ERP_TEST_POSTGRES_URL): Büro setzt "beseitigt", während der Monteur meldet -- eine Meldung,
eine neue Aufgabe."""

import importlib.util
import json
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select

from app import defects as defects_module
from app.database import Base
from app.models import Defect, DefectEvent, EnabledModule, Task, TaskColumn
from tests.test_v349_abnahme_und_gewaehrleistung import _png, _waits_for, ablage, welt  # noqa: F401  (Fixtures)
from tests.test_v351_maengel import _abnahme, _anzahl, _iso, _mangel, _ok, _status, buero  # noqa: F401
from tests.test_v354_maengel_monteur import (  # noqa: F401  (Fixtures)
    HEUTE, _freigegebener_mangel, _liste, _melden, _pg_melden, karl, mia, pg,
)

ROOT = Path(__file__).resolve().parent.parent
HINWEIS = "Rinne neu eingeklebt, Hinweis-7c1e"


def _done_keys(db) -> set[str]:
    return {c.key for c in db.scalars(select(TaskColumn).where(TaskColumn.is_done.is_(True)))}


def _tasks(db) -> list[Task]:
    db.expire_all()
    return db.scalars(select(Task).where(Task.source_module == "maengel").order_by(Task.id)).all()


def _view(buero, welt, defect_id):
    return {x["id"]: x for x in _ok(buero.get(f"/api/orders/{welt['order_id']}/defects"))}[defect_id]


def _strings(value) -> list[str]:
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in [str(k), *_strings(v)]]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return [str(value)]


# ---------------------------------------------------------------------------
# Aufgabe folgt dem Status
# ---------------------------------------------------------------------------

def test_office_remedied_completes_remedy_task_and_creates_acceptance_task(welt, buero):
    db = welt["db"]
    frist = HEUTE + timedelta(days=10)
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"], roof_area_id=welt["areas"]["Nord"], remedy_due_on=_iso(frist),
                    description="Attika undicht"))
    [t1] = _tasks(db)
    _ok(_status(buero, d["id"], status="beseitigt", event_date=_iso(HEUTE)))
    t1_neu, t2 = _tasks(db)
    assert t1_neu.id == t1.id and t1_neu.status in _done_keys(db) and t1_neu.completed_at is not None
    assert t2.title.startswith("Beseitigung abnehmen lassen – Mangel aus Abnahme ") and "Nord" in t2.title
    assert t2.status not in _done_keys(db) and t2.assigned_employee_id is None and t2.min_visible_role == "buero_auftrag"
    assert (t2.source_module, t2.source_url, t2.project_id, t2.due_date) == (
        "maengel", f"/orders/{welt['order_id']}#mangel-{d['id']}", welt["project_id"], None)
    assert "Attika" not in (t2.description or "")  # nur Metadaten
    event = db.scalars(select(DefectEvent).where(DefectEvent.defect_id == d["id"]).order_by(DefectEvent.id.desc())).first()
    assert event.task_id == t2.id
    v = _view(buero, welt, d["id"])
    assert (v["task"]["id"], v["task"]["kind_label"], v["task"]["done"]) == (t2.id, "Beseitigung abnehmen lassen", False)
    assert v["task"]["url"] == f"/tasks?task={t2.id}" and v["task_hint"] is None
    assert v["events"][-1]["task_label"] == "Beseitigung abnehmen lassen" and v["intact"] is True
    # Abnahme der Beseitigung erledigt die neue Aufgabe.
    _ok(_status(buero, d["id"], status="beseitigung_abgenommen", event_date=_iso(HEUTE), reason="vor Ort",
                declared_by="auftraggeber"))
    assert all(t.status in _done_keys(db) for t in _tasks(db)) and len(_tasks(db)) == 2


def test_back_to_open_creates_remedy_task_again(welt, buero):
    db = welt["db"]
    frist = HEUTE + timedelta(days=3)
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"], location="Traufe Ost", remedy_due_on=_iso(frist)))
    _ok(_status(buero, d["id"], status="beseitigt", event_date=_iso(HEUTE)))
    _ok(_status(buero, d["id"], status="offen", reason="Nachbesserung misslungen"))
    t1, t2, t3 = _tasks(db)
    assert t2.status in _done_keys(db) and t3.status not in _done_keys(db)
    assert t3.title.startswith("Erneut beseitigen – Mangel aus Abnahme ") and "Traufe Ost" in t3.title
    assert t3.due_date == frist and "misslungen" not in (t3.description or "")
    v = _view(buero, welt, d["id"])
    assert (v["task"]["id"], v["task"]["kind_label"]) == (t3.id, "Mangel beseitigen")
    # Noch einmal beseitigt und abgenommen: am Ende alle vier erledigt, nie zwei offene gleichzeitig.
    _ok(_status(buero, d["id"], status="beseitigt", event_date=_iso(HEUTE)))
    assert [t.status in _done_keys(db) for t in _tasks(db)] == [True, True, True, False]
    _ok(_status(buero, d["id"], status="beseitigung_abgenommen", event_date=_iso(HEUTE), reason="vor Ort",
                declared_by="auftraggeber"))
    assert [t.status in _done_keys(db) for t in _tasks(db)] == [True, True, True, True]


@pytest.mark.parametrize("abschluss", ["erledigt_ohne", "verworfen"])
def test_finishing_after_back_to_open_completes_the_current_task(welt, buero, abschluss):
    db = welt["db"]
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    _ok(_status(buero, d["id"], status="beseitigt", event_date=_iso(HEUTE)))
    _ok(_status(buero, d["id"], status="offen", reason="misslungen"))
    if abschluss == "erledigt_ohne":
        _ok(_status(buero, d["id"], status="erledigt_ohne", reason="Minderung"))
    else:
        _ok(buero.post(f"/api/defects/{d['id']}/discard", json={"reason": "doppelt"}))
    assert [t.status in _done_keys(db) for t in _tasks(db)] == [True, True, True]


def test_field_report_completes_and_creates_like_the_office(welt, buero, mia):
    db = welt["db"]
    d = _freigegebener_mangel(buero, welt, description="Kehle undicht")
    kennung = str(uuid.uuid4())
    erste = _ok(_melden(mia, d["id"], kennung=kennung))
    t1, t2 = _tasks(db)
    assert t1.status in _done_keys(db) and t2.status not in _done_keys(db)
    assert t2.title.startswith("Beseitigung abnehmen lassen – ")
    assert "in der Monteursansicht von Mia Monteurin" in t2.description and "Kehle" not in t2.description
    assert db.get(DefectEvent, erste["event_id"]).task_id == t2.id
    # Dieselbe Kennung noch einmal: dieselbe Antwort, keine zweite Aufgabe.
    assert _ok(_melden(mia, d["id"], kennung=kennung)) == erste
    assert len(_tasks(db)) == 2


def test_the_defect_stays_the_truth(welt, buero):
    """Die neue Aufgabe von Hand erledigen ändert am Mangel nichts -- die Seite weist darauf hin."""
    db = welt["db"]
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    _ok(_status(buero, d["id"], status="beseitigt", event_date=_iso(HEUTE)))
    t2 = _tasks(db)[-1]
    t2.status = sorted(_done_keys(db))[0]
    db.commit()
    v = _view(buero, welt, d["id"])
    assert v["status"] == "beseitigt" and v["task"]["done"] is True and "maßgeblich ist der Mangel" in v["task_hint"]
    # Zurück auf offen legt trotzdem "Mangel beseitigen" an (die erledigte bleibt erledigt).
    _ok(_status(buero, d["id"], status="offen", reason="misslungen"))
    assert [t.status in _done_keys(db) for t in _tasks(db)] == [True, True, False]


def test_without_task_module_no_new_task(welt, buero):
    db = welt["db"]
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
    db.commit()
    _ok(_status(buero, d["id"], status="beseitigt", event_date=_iso(HEUTE)))
    [t1] = _tasks(db)
    assert t1.status in _done_keys(db)  # die bestehende wird erledigt wie beim Verwerfen
    event = db.scalars(select(DefectEvent).where(DefectEvent.defect_id == d["id"])).all()[-1]
    assert event.task_id is None
    v = _view(buero, welt, d["id"])
    assert v["task"]["id"] == t1.id and v["events"][-1]["task_label"] is None


def test_task_and_event_are_one_transaction(welt, buero, mia, ablage, monkeypatch):
    """Scheitert das Anlegen der neuen Aufgabe, gibt es weder Eintrag noch Aufgabe, und die bisherige bleibt offen --
    beim Büro wie bei der Meldung (deren Fotos sind wieder weg)."""
    db = welt["db"]
    d = _freigegebener_mangel(buero, welt)

    def kaputt(*args, **kwargs):
        raise RuntimeError("Aufgabe nicht angelegt")
    monkeypatch.setattr(defects_module, "_follow_task", kaputt)
    vorher_events, vorher_dateien = _anzahl(db, DefectEvent), sorted(p.name for p in ablage.rglob("*.*"))
    with pytest.raises(RuntimeError):
        defects_module.set_status(db, db.get(Defect, d["id"]), {"status": "beseitigt", "event_date": HEUTE}, [],
                                  user_id=None, user_name="Büro")
    with pytest.raises(RuntimeError):
        defects_module.report_remedied(db, db.get(Defect, d["id"]), event_date=HEUTE, client_uuid=str(uuid.uuid4()),
                                       files=[("foto", "n.png", _png("green"))], note=None, user_id=mia["user_id"],
                                       user_name="Mia Monteurin")
    assert _anzahl(db, DefectEvent) == vorher_events
    assert sorted(p.name for p in ablage.rglob("*.*")) == vorher_dateien
    [t1] = _tasks(db)
    assert t1.status not in _done_keys(db)


# ---------------------------------------------------------------------------
# Hinweis des Monteurs
# ---------------------------------------------------------------------------

def test_field_note_is_stored_sealed_and_shown_to_the_office_only(welt, buero, mia, karl):
    db = welt["db"]
    d = _freigegebener_mangel(buero, welt)
    antwort = _ok(_melden(mia, d["id"], note=f"  {HINWEIS}  "))
    assert HINWEIS not in json.dumps(antwort)
    event = db.get(DefectEvent, antwort["event_id"])
    assert event.reason == HINWEIS
    assert defects_module.event_content(event, db.get(Defect, d["id"]).content_sha256)["reason"] == HINWEIS
    v = _view(buero, welt, d["id"])
    assert v["events"][-1]["reason"] == HINWEIS and v["events"][-1]["via_field_view"] is True and v["intact"] is True
    # Nicht in der Aufgabe.
    assert all(HINWEIS not in (t.title + (t.description or "")) for t in _tasks(db))
    # Wieder offen: der Mangel erscheint in /mobil -- ohne Hinweis, für beide Monteure.
    _ok(_status(buero, d["id"], status="offen", reason="misslungen"))
    for monteur in (mia, karl):
        liste = _liste(monteur)
        assert [x["id"] for x in liste] == [d["id"]]
        assert not any(HINWEIS in s for s in _strings(liste))


def test_field_note_is_optional_short_and_trimmed(welt, buero, mia):
    db = welt["db"]
    leer = _freigegebener_mangel(buero, welt)
    assert db.get(DefectEvent, _ok(_melden(mia, leer["id"], note="   "))["event_id"]).reason is None
    ohne = _freigegebener_mangel(buero, welt)
    assert db.get(DefectEvent, _ok(_melden(mia, ohne["id"]))["event_id"]).reason is None
    lang = _freigegebener_mangel(buero, welt)
    vorher = _anzahl(db, DefectEvent)
    r = _melden(mia, lang["id"], note="x" * 501)
    assert r.status_code in (400, 422), r.text
    assert _anzahl(db, DefectEvent) == vorher
    assert _ok(_melden(mia, lang["id"], note="x" * 500))
    # Ein anderer Text als "note" bleibt verboten (extra="forbid").
    anders = _freigegebener_mangel(buero, welt)
    assert _melden(mia, anders["id"], reason="Begründung").status_code == 422


def test_office_page_labels_the_field_note(welt, router_test_client):
    from app.routers import pages
    html = router_test_client(welt["db"], pages.router).get(f"/orders/{welt['order_id']}").text
    assert "Hinweis aus der Monteursansicht" in html and "task_label" in html


def test_mobil_page_has_the_optional_note(welt, router_test_client, mia):
    from app.routers import pages
    html = router_test_client(welt["db"], pages.router, role="field", employee_id=mia["employee_id"]).get("/mobil").text
    teil = html.split("function renderDefects")[1].split("function loadDefects")[0]
    assert "<textarea" in teil and 'maxlength="500"' in teil and "note:" in teil and "nur fürs Büro" in teil


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def _migration():
    path = next(ROOT.glob("alembic/versions/*_maengel_aufgabe_je_eintrag.py"))
    spec = importlib.util.spec_from_file_location("migration_1854_maengel_aufgabe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_adds_and_removes_the_task_column():
    module = _migration()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    def run(name):
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                getattr(module, name)()

    def spalten():
        return {c["name"] for c in inspect(engine).get_columns("defect_events")}
    run("downgrade")
    assert "task_id" not in spalten() and "client_uuid" in spalten()
    run("upgrade")
    assert "task_id" in spalten()


# ---------------------------------------------------------------------------
# PostgreSQL: gleichzeitig
# ---------------------------------------------------------------------------

def test_postgresql_report_waits_for_office_remedied(pg):
    """Das Büro setzt "beseitigt", während der Monteur meldet: die Meldung wartet auf die Sperre des Mangels und wird
    danach abgelehnt (409) -- ein Eintrag, eine neue Aufgabe."""
    Session, welt = pg
    holder, ready = Session(), threading.Event()

    def hold(release):
        def run():
            defect = holder.get(Defect, welt["defect_id"])
            commit = holder.commit

            def angehalten():
                holder.flush()
                ready.set()
                release.wait(timeout=30)
                commit()
            holder.commit = angehalten
            defects_module.set_status(holder, defect, {"status": "beseitigt", "event_date": HEUTE}, [], user_id=None,
                                      user_name="Büro")
        threading.Thread(target=run).start()
        ready.wait(timeout=10)
    done = _waits_for(hold, lambda: _pg_melden(Session, welt, str(uuid.uuid4())))
    time.sleep(0.3)
    holder.close()
    assert isinstance(done["result"], defects_module.DefectConflict) and done["seconds"] >= 0.9, done
    check = Session()
    try:
        events = check.scalars(select(DefectEvent).where(DefectEvent.defect_id == welt["defect_id"])).all()
        assert [(e.kind, e.value) for e in events] == [("freigabe", "freigegeben"), ("status", "beseitigt")]
        tasks = check.scalars(select(Task).where(Task.source_module == "maengel").order_by(Task.id)).all()
        assert len(tasks) == 2 and events[-1].task_id == tasks[-1].id
    finally:
        check.close()
