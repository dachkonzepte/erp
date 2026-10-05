"""Version 1.8.55 -- Stufe 2c-2c, Punkt 0 (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.55").

"Zurück auf offen" trägt optional eine neue Beseitigungsfrist (DefectEvent.due_on, nicht vor heute). Die aktuelle Frist ist
die des letzten Eintrags mit einer, sonst die beim Erfassen (current_due()) -- die Aufgabe "Erneut beseitigen", die
Büro-Seite (Überschreitung) und /mobil nutzen sie. Die Frist steht im gebundenen Inhalt des Eintrags, nur wenn gesetzt:
frühere Einträge behalten ihre Prüfsumme, ein am ORM vorbei gesetztes oder entferntes Datum fällt auf."""

import importlib.util
from datetime import timedelta
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select, text, update

from app.database import Base
from app.defects import content_sha256, event_content
from app.models import DefectEvent, Task
from tests.test_v349_abnahme_und_gewaehrleistung import _png, ablage, welt  # noqa: F401  (Fixtures)
from tests.test_v351_maengel import _abnahme, _iso, _mangel, _ok, _status, buero  # noqa: F401
from tests.test_v354_maengel_monteur import HEUTE, _freigegebener_mangel, _liste, mia  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent


def _view(buero, welt, defect_id):
    return {x["id"]: x for x in _ok(buero.get(f"/api/orders/{welt['order_id']}/defects"))}[defect_id]


def _tasks(db) -> list[Task]:
    db.expire_all()
    return db.scalars(select(Task).where(Task.source_module == "maengel").order_by(Task.id)).all()


def _last_event(db, defect_id) -> DefectEvent:
    db.expire_all()
    return db.scalars(select(DefectEvent).where(DefectEvent.defect_id == defect_id).order_by(DefectEvent.id.desc())).first()


def _zurueck(buero, defect_id, **extra):
    _ok(_status(buero, defect_id, status="beseitigt", event_date=_iso(HEUTE)))
    return _status(buero, defect_id, status="offen", reason="Nachbesserung misslungen", **extra)


def test_back_to_open_with_new_deadline(welt, buero):
    db = welt["db"]
    alt, neu = HEUTE + timedelta(days=2), HEUTE + timedelta(days=21)
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"], remedy_due_on=_iso(alt)))
    _ok(_zurueck(buero, d["id"], due_on=_iso(neu)))
    event = _last_event(db, d["id"])
    assert (event.value, event.due_on) == ("offen", neu)
    erneut = _tasks(db)[-1]
    assert erneut.title.startswith("Erneut beseitigen – ") and erneut.due_date == neu
    assert neu.strftime("%d.%m.%Y") in erneut.description
    v = _view(buero, welt, d["id"])
    assert (v["remedy_due_on"], v["remedy_due_on_original"], v["remedy_due_changed"]) == (_iso(neu), _iso(alt), True)
    assert v["events"][-1]["due_on"] == _iso(neu) and v["intact"] is True
    # Die Frist steht im gebundenen Inhalt des Eintrags.
    assert event_content(event, event.defect.content_sha256)["due_on"] == _iso(neu)


def test_without_new_deadline_the_current_one_stays(welt, buero):
    """Ohne neue Frist gilt die zuletzt gesetzte weiter -- nicht die beim Erfassen."""
    db = welt["db"]
    alt, neu = HEUTE + timedelta(days=2), HEUTE + timedelta(days=30)
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"], remedy_due_on=_iso(alt)))
    _ok(_zurueck(buero, d["id"]))
    assert _tasks(db)[-1].due_date == alt and _last_event(db, d["id"]).due_on is None
    _ok(_zurueck(buero, d["id"], due_on=_iso(neu)))
    _ok(_zurueck(buero, d["id"]))
    assert _tasks(db)[-1].due_date == neu
    v = _view(buero, welt, d["id"])
    assert v["remedy_due_on"] == _iso(neu) and v["remedy_due_changed"] is True and v["intact"] is True
    assert [e["due_on"] for e in v["events"]] == [None, None, None, _iso(neu), None, None]


def test_new_deadline_without_original_one(welt, buero):
    db = welt["db"]
    neu = HEUTE + timedelta(days=7)
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    _ok(_zurueck(buero, d["id"], due_on=_iso(neu)))
    assert _tasks(db)[-1].due_date == neu
    v = _view(buero, welt, d["id"])
    assert (v["remedy_due_on"], v["remedy_due_on_original"], v["remedy_due_changed"]) == (_iso(neu), None, True)


def test_overdue_follows_the_current_deadline(welt, buero, mia):
    """Büro und /mobil: überschritten nach der aktuellen Frist -- eine neue Frist hebt die Überschreitung auf."""
    gestern = HEUTE - timedelta(days=1)
    d = _freigegebener_mangel(buero, welt, remedy_due_on=_iso(gestern))
    [m] = _liste(mia)
    assert (m["remedy_due_on"], m["remedy_overdue"]) == (_iso(gestern), True)
    assert _view(buero, welt, d["id"])["remedy_overdue"] is True
    neu = HEUTE + timedelta(days=14)
    _ok(_zurueck(buero, d["id"], due_on=_iso(neu)))
    [m] = _liste(mia)
    assert (m["id"], m["remedy_due_on"], m["remedy_overdue"]) == (d["id"], _iso(neu), False)
    assert _view(buero, welt, d["id"])["remedy_overdue"] is False


@pytest.mark.parametrize("fall", ["anderer_status", "vergangenheit", "beseitigt_mit_frist"])
def test_invalid_new_deadline_is_rejected_and_nothing_stored(welt, buero, fall):
    db = welt["db"]
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    if fall == "beseitigt_mit_frist":
        r = _status(buero, d["id"], status="beseitigt", event_date=_iso(HEUTE), due_on=_iso(HEUTE + timedelta(days=3)))
        erwartet = "nur zu „zurück auf offen“"
    else:
        _ok(_status(buero, d["id"], status="beseitigt", event_date=_iso(HEUTE)))
        if fall == "anderer_status":
            r = _status(buero, d["id"], status="erledigt_ohne", reason="Minderung", due_on=_iso(HEUTE))
            erwartet = "nur zu „zurück auf offen“"
        else:
            r = _status(buero, d["id"], status="offen", reason="misslungen", due_on=_iso(HEUTE - timedelta(days=1)))
            erwartet = "in der Vergangenheit"
    assert r.status_code == 400 and erwartet in r.json()["detail"]
    db.expire_all()
    assert all(e.due_on is None for e in db.scalars(select(DefectEvent)))
    # Heute ist erlaubt.
    if fall == "vergangenheit":
        _ok(_status(buero, d["id"], status="offen", reason="misslungen", due_on=_iso(HEUTE)))


def test_attack_deadline_changed_at_the_orm_is_detected(welt, buero):
    """Am ORM vorbei: eine neue Frist an einem Eintrag ohne eine, eine geänderte und eine entfernte -- jedes Mal weicht
    der Verlauf von seiner Prüfsumme ab."""
    db = welt["db"]
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    _ok(_zurueck(buero, d["id"], due_on=_iso(HEUTE + timedelta(days=5))))
    events = db.scalars(select(DefectEvent).where(DefectEvent.defect_id == d["id"]).order_by(DefectEvent.id)).all()
    beseitigt, offen = events[0].id, events[1].id
    for event_id, wert in ((beseitigt, HEUTE + timedelta(days=9)), (offen, HEUTE + timedelta(days=60)), (offen, None)):
        original = db.get(DefectEvent, event_id).due_on
        db.execute(update(DefectEvent).where(DefectEvent.id == event_id).values(due_on=wert))
        db.commit()
        v = _view(buero, welt, d["id"])
        assert v["intact"] is False and "Verlauf weicht von seiner Prüfsumme ab" in v["check"]["text"], (event_id, wert)
        db.execute(update(DefectEvent).where(DefectEvent.id == event_id).values(due_on=original))
        db.commit()
        assert _view(buero, welt, d["id"])["intact"] is True


def test_events_without_deadline_keep_their_old_checksum(welt, buero):
    """Ohne neue Frist ist der gebundene Inhalt genau der von 1.8.54 -- vorhandene Prüfsummen bleiben gültig."""
    db = welt["db"]
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    _ok(_zurueck(buero, d["id"]))
    for event in db.scalars(select(DefectEvent).where(DefectEvent.defect_id == d["id"])):
        content = event_content(event, event.defect.content_sha256)
        assert "due_on" not in content and content_sha256(content) == event.content_sha256


def test_office_page_shows_the_new_deadline_field():
    page = (ROOT / "app/templates/_maengel.html").read_text(encoding="utf-8")
    assert 'id="defDueBox${id}"' in page and "Neue Beseitigungsfrist (optional" in page
    assert "document.getElementById('defDueBox'+id).hidden=next!=='offen'" in page
    assert "data.due_on=due" in page and "data-neue-frist" in page and "beim Erfassen:" in page


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def _migration():
    path = next(ROOT.glob("alembic/versions/*_maengel_neue_frist.py"))
    spec = importlib.util.spec_from_file_location("migration_1855_maengel_neue_frist", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_adds_column_and_refuses_downgrade_with_deadlines():
    module = _migration()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    def run(name):
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                getattr(module, name)()

    def spalten():
        return {c["name"] for c in inspect(engine).get_columns("defect_events")}

    with engine.begin() as conn:  # Bestand: ein Eintrag mit neuer Frist (Mangel und Kette braucht die Prüfung nicht)
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("INSERT INTO defect_events (defect_id, kind, value, content_sha256, checksum_format, "
                          "created_by_name, created_at, due_on) VALUES (1, 'status', 'offen', 'x', 1, 'Büro', "
                          "'2026-10-05 10:00:00', '2026-11-30')"))
    with pytest.raises(RuntimeError, match="Downgrade verweigert: 1 Einträge"):
        run("downgrade")
    assert "due_on" in spalten()
    with engine.begin() as conn:
        conn.execute(text("UPDATE defect_events SET due_on = NULL"))
    run("downgrade")
    assert "due_on" not in spalten() and "task_id" in spalten()
    run("upgrade")
    assert "due_on" in spalten()
