"""Version 1.8.49 -- Stufe 2c-2a, Punkt 1: Mängel aus der Abnahme (docs/archiv/abnahme-und-gewaehrleistung.md,
"Umsetzung 1.8.49").

- Mangel (Defect) nur an einer nicht verworfenen Abnahme mit "Vorbehalt Mängel: ja" oder "verweigert"; Warnung an
  solchen Abnahmen ohne Mangel.
- Beschreibung Pflicht; Dachfläche nur aus dem Objekt der Abnahme; Ortsangabe, Beseitigungsfrist, Fotos und Belege.
  Unveränderlich, Fotos nur ergänzen, Korrektur durch Verwerfen mit Begründung.
- Haltung (offen/anerkannt/bestritten mit Begründung), Status (offen/beseitigt/Beseitigung abgenommen/erledigt ohne
  Beseitigung), Freigabe zur Beseitigung -- je mit Verlauf.
- Nur bei vob_b: "Nachbesserung regulär bis" = das spätere von Regelende und Abnahme der Beseitigung + 24 Monate.
- Aufgabe beim Erfassen (ohne Zuständigkeit, fällig zur Frist), Verweis in beide Richtungen; die Erledigung des
  Mangels erledigt die Aufgabe, umgekehrt nicht.

Angriffe mit Gegenprobe: Dachfläche eines fremden Objekts, Mangel an einer Abnahme ohne Vorbehalt, Monteur liest
Mängel, Ändern nach dem Speichern (ORM und am ORM vorbei). Gegen PostgreSQL (opt-in über ERP_TEST_POSTGRES_URL):
Erfassen wartet auf das Verwerfen der Abnahme, zwei Statuswechsel gleichzeitig."""

import importlib.util
import json
import logging
import os
import stat
import threading
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, delete, inspect, select, text, update
from sqlalchemy.orm import close_all_sessions, sessionmaker

from app import acceptances as acceptances_module
from app import defects as defects_module
from app.berlin_time import berlin_today
from app.contract_basis import change_order_contract_basis
from app.database import Base
from app.models import (
    ArchiveImmutableError, AuditLog, Defect, DefectEvent, EnabledModule, Order, OrderAcceptance, Project,
    Task, TaskColumn,
)
from app.routers import defects as defects_router
from app.routers import tasks as tasks_router
from tests.test_v349_abnahme_und_gewaehrleistung import (  # noqa: F401  (Fixtures)
    GUELTIG, PDF, PG_TEST_DATABASE_URL, SVG, _dauer, _erfassen, _png, _waits_for, _welt, ablage, welt,
)

ROOT = Path(__file__).resolve().parent.parent
HEUTE = berlin_today()


def _iso(d: date) -> str:
    return d.isoformat()


@pytest.fixture
def buero(welt, router_test_client):
    return router_test_client(welt["db"], *_routers(), role="buero_auftrag")


def _routers():
    from app.routers import acceptances, orders, project_participants, roof_areas
    return (acceptances.router, orders.router, roof_areas.router, project_participants.router, defects_router.router,
            tasks_router.router)


def _abnahme(buero, welt, art="vorbehalt", tag=None):
    """"vorbehalt": abgenommen mit Vorbehalt Mängel; "ohne": ohne Vorbehalt; "verweigert"."""
    werte = {"vorbehalt": {"reservation_defects": True},
             "ohne": {},
             "verweigert": {"result": "verweigert", "reservation_defects": ..., "reservation_penalty": ...}}[art]
    tag = tag or HEUTE - timedelta(days=20)
    r = _erfassen(buero, welt["order_id"], accepted_on=_iso(tag), **werte)
    assert r.status_code == 200, r.text
    return r.json()


def _mangel(buero, acceptance_id, photos=(), receipts=(), **werte):
    data = {"description": "Anschluss an der Attika undicht", **werte}
    data = {k: v for k, v in data.items() if v is not ...}
    files = [("photos", p) for p in photos] + [("receipts", r) for r in receipts]
    return buero.post(f"/api/order-acceptances/{acceptance_id}/defects", data={"data": json.dumps(data)}, files=files)


def _ok(r):
    assert r.status_code == 200, r.text
    return r.json()


def _status(buero, defect_id, receipts=(), **data):
    return buero.post(f"/api/defects/{defect_id}/status", data={"data": json.dumps(data)},
                      files=[("receipts", r) for r in receipts])


def _anzahl(db, model=Defect):
    db.expire_all()
    return len(db.scalars(select(model)).all())


# ---------------------------------------------------------------------------
# Nur an Abnahmen mit Vorbehalt Mängel oder verweigert
# ---------------------------------------------------------------------------

def test_attack_defect_at_acceptance_without_reservation_is_rejected(welt, buero, ablage):
    ohne = _abnahme(buero, welt, "ohne")
    r = _mangel(buero, ohne["id"], photos=[("foto.png", _png(), "image/png")])
    assert r.status_code == 400 and "Vorbehalt Mängel" in r.json()["detail"]
    assert _anzahl(welt["db"]) == 0 and _anzahl(welt["db"], Task) == 0
    assert not list((ablage / "maengel").rglob("*.*")) if (ablage / "maengel").exists() else True
    assert buero.get(f"/api/order-acceptances/{ohne['id']}/defect-options").json()["allowed"] is False
    # Gegenprobe: mit Vorbehalt und bei Verweigerung geht es.
    for art in ("vorbehalt", "verweigert"):
        a = _abnahme(buero, welt, art)
        assert buero.get(f"/api/order-acceptances/{a['id']}/defect-options").json()["allowed"] is True
        assert _mangel(buero, a["id"]).status_code == 200, art
    assert _anzahl(welt["db"]) == 2


def test_discarded_acceptance_takes_no_new_defect(welt, buero):
    a = _abnahme(buero, welt)
    d = _ok(_mangel(buero, a["id"]))
    buero.post(f"/api/order-acceptances/{a['id']}/discard", json={"reason": "falsch erfasst"})
    r = _mangel(buero, a["id"])
    assert r.status_code == 409 and "verworfen" in r.json()["detail"]
    # Der schon erfasste Mangel bleibt, gekennzeichnet.
    liste = _ok(buero.get(f"/api/orders/{welt['order_id']}/defects"))
    assert [x["id"] for x in liste] == [d["id"]] and liste[0]["acceptance"]["discarded"] is True


def test_acceptance_list_warns_without_defect(welt, buero):
    vorbehalt = _abnahme(buero, welt)
    ohne = _abnahme(buero, welt, "ohne")
    verweigert = _abnahme(buero, welt, "verweigert")

    def stand():
        return {x["id"]: x["defects"] for x in buero.get(f"/api/orders/{welt['order_id']}/acceptances").json()}
    s = stand()
    assert s[vorbehalt["id"]]["missing"] is True and s[verweigert["id"]]["missing"] is True
    assert s[ohne["id"]] == {"expected": False, "active": 0, "total": 0, "missing": False, "text": None}
    assert "ohne erfassten Mangel" in s[vorbehalt["id"]]["text"]
    d = _ok(_mangel(buero, vorbehalt["id"]))
    assert stand()[vorbehalt["id"]]["missing"] is False and stand()[vorbehalt["id"]]["active"] == 1
    buero.post(f"/api/defects/{d['id']}/discard", json={"reason": "doppelt"})
    s = stand()[vorbehalt["id"]]
    assert s["missing"] is True and s["total"] == 1 and s["active"] == 0


# ---------------------------------------------------------------------------
# Erfassen: Pflichtfelder, Dachfläche, Dateien
# ---------------------------------------------------------------------------

def test_defect_with_roof_area_photos_and_receipt(welt, buero, ablage):
    a = _abnahme(buero, welt)
    frist = HEUTE + timedelta(days=14)
    d = _ok(_mangel(buero, a["id"], roof_area_id=welt["areas"]["Nord"], location="Attika Westseite",
                    remedy_due_on=_iso(frist), photos=[("a.png", _png(), "image/png"), ("b.png", _png("red"), "image/png")],
                    receipts=[("ruege.pdf", PDF, "application/pdf")]))
    assert d["roof_area_name"] == "Nord" and d["location"] == "Attika Westseite" and d["remedy_due_on"] == _iso(frist)
    assert sorted(f["kind"] for f in d["files"]) == ["beleg", "foto", "foto"]
    assert d["stance"] == "offen" and d["status"] == "offen" and d["released"] is False and d["intact"] is True
    assert d["checksum_format"] == 1 and d["created_by_name"] == "Buero_auftrag"
    assert all(f["status"] == "unveraendert" for f in d["files"])
    for f in d["files"]:
        r = buero.get(f"/api/defects/{d['id']}/files/{f['id']}")
        assert r.status_code == 200 and r.headers["x-content-type-options"] == "nosniff"
    stored = list((ablage / "maengel").rglob("*.*"))
    assert len(stored) == 3 and all(not os.access(p, os.W_OK) for p in stored)


@pytest.mark.parametrize("werte,dateien,teil", [
    ({"description": "  "}, {}, "beschreiben"),
    ({"remedy_due_on": "2020-01-01"}, {}, "vor dem Datum der Abnahme"),
    ({}, {"photos": [("x.pdf", PDF, "application/pdf")]}, "Foto muss JPEG"),
    ({}, {"photos": [("x.svg", SVG, "image/svg+xml")]}, "Foto (JPEG, PNG, WebP) oder ein PDF"),
    ({}, {"receipts": [("x.pdf", PDF, "application/pdf"), ("y.pdf", PDF, "application/pdf")]}, "mehrfach"),
    ({"location": "x" * 501}, {}, "Ortsangabe"),
])
def test_invalid_input_is_rejected_and_nothing_stored(welt, buero, ablage, werte, dateien, teil):
    a = _abnahme(buero, welt)
    r = _mangel(buero, a["id"], **werte, **dateien)
    assert r.status_code == 400 and teil in r.json()["detail"], r.text
    assert _anzahl(welt["db"]) == 0 and _anzahl(welt["db"], Task) == 0
    assert not (ablage / "maengel").exists() or not list((ablage / "maengel").rglob("*.*"))


def test_attack_roof_area_of_a_foreign_property_is_rejected(welt, buero):
    a = _abnahme(buero, welt)
    r = _mangel(buero, a["id"], roof_area_id=welt["fremd_area"])
    assert r.status_code == 400 and "Objekt der Abnahme" in r.json()["detail"] and _anzahl(welt["db"]) == 0
    r = _mangel(buero, a["id"], roof_area_id=welt["areas"]["Anbau (alt)"])
    assert r.status_code == 400 and "archiviert" in r.json()["detail"]
    assert _mangel(buero, a["id"], roof_area_id=welt["areas"]["Süd"]).status_code == 200  # Gegenprobe
    # Zieht das Projekt um, bleibt das Objekt DER ABNAHME maßgeblich -- nicht das heutige des Projekts.
    db = welt["db"]
    db.get(Project, welt["project_id"]).property_id = welt["fremd_property_id"]
    db.commit()
    assert _mangel(buero, a["id"], roof_area_id=welt["fremd_area"]).status_code == 400
    assert _mangel(buero, a["id"], roof_area_id=welt["areas"]["Nord"]).status_code == 200
    optionen = buero.get(f"/api/order-acceptances/{a['id']}/defect-options").json()
    assert {x["name"] for x in optionen["roof_areas"]} == {"Nord", "Süd"} and optionen["property"]["name"] == "Halle"


# ---------------------------------------------------------------------------
# Unveränderlich
# ---------------------------------------------------------------------------

def test_attack_no_route_changes_or_deletes_a_defect(welt, buero):
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"], photos=[("a.png", _png(), "image/png")]))
    for method in ("put", "patch", "delete"):
        assert getattr(buero, method)(f"/api/defects/{d['id']}").status_code in (404, 405)
        assert buero.request(method.upper(), f"/api/defects/{d['id']}/files/{d['files'][0]['id']}").status_code == 405


def test_attack_orm_changes_and_deletes_are_refused(welt, buero):
    db = welt["db"]
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"], photos=[("a.png", _png(), "image/png")]))
    _ok(buero.post(f"/api/defects/{d['id']}/stance", json={"stance": "anerkannt", "reason": None}))
    for change in (
        lambda x: setattr(x, "description", "harmlos"),
        lambda x: setattr(x, "remedy_due_on", date(2030, 1, 1)),
        lambda x: setattr(x, "discard_reason", "über das ORM"),
        lambda x: setattr(x, "task_id", None),
        lambda x: setattr(x.files[0], "sha256", "0" * 64),
        lambda x: setattr(x.events[0], "value", "bestritten"),
    ):
        change(db.get(Defect, d["id"]))
        with pytest.raises(ArchiveImmutableError):
            db.commit()
        db.rollback()
    for target in (lambda x: x, lambda x: x.files[0], lambda x: x.events[0]):
        db.delete(target(db.get(Defect, d["id"])))
        with pytest.raises(ArchiveImmutableError):
            db.commit()
        db.rollback()
    assert _ok(buero.get(f"/api/orders/{welt['order_id']}/defects"))[0]["intact"] is True


def test_attack_change_past_the_orm_is_detected(welt, buero, ablage, caplog):
    db = welt["db"]
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"], photos=[("a.png", _png(), "image/png")]))
    for stance, grund in (("anerkannt", None), ("bestritten", "kein Mangel, sondern Abnutzung"), ("anerkannt", "Gutachten")):
        _ok(buero.post(f"/api/defects/{d['id']}/stance", json={"stance": stance, "reason": grund}))
    stand = lambda: _ok(buero.get(f"/api/orders/{welt['order_id']}/defects"))[0]  # noqa: E731
    assert stand()["intact"] is True

    db.execute(update(Defect).where(Defect.id == d["id"]).values(description="harmlos")
               .execution_options(synchronize_session=False))
    db.commit()
    with caplog.at_level(logging.ERROR, logger="app.defects"):
        s = stand()
    assert s["intact"] is False and s["check"]["text"].startswith("Inhalt weicht")
    meldung = " ".join(r.getMessage() for r in caplog.records if r.name == "app.defects")
    assert f"Mangel {d['id']}" in meldung and "harmlos" not in meldung and "Attika" not in meldung  # Regel 18
    db.execute(update(Defect).where(Defect.id == d["id"]).values(description="Anschluss an der Attika undicht")
               .execution_options(synchronize_session=False))
    db.commit()
    assert stand()["intact"] is True  # Gegenprobe: zurückgesetzt stimmt es wieder

    # Ein Eintrag im Verlauf geändert bzw. mittendrin entfernt: die Kette fällt auf.
    ids = [e["id"] for e in stand()["events"]]
    db.execute(update(DefectEvent).where(DefectEvent.id == ids[1]).values(reason="anders")
               .execution_options(synchronize_session=False))
    db.commit()
    assert stand()["check"]["text"] == "Verlauf weicht von seiner Prüfsumme ab"
    db.execute(delete(DefectEvent).where(DefectEvent.id == ids[1]).execution_options(synchronize_session=False))
    db.commit()
    s = stand()
    assert s["intact"] is False and [e["intact"] for e in s["events"]] == [True, False]

    pfad = next((ablage / "maengel").rglob("*.png"))
    os.chmod(pfad, stat.S_IWRITE | stat.S_IREAD)
    pfad.unlink()
    assert buero.get(f"/api/defects/{d['id']}/files/{d['files'][0]['id']}").status_code == 410


def test_file_of_another_defect_is_not_delivered(welt, buero):
    a = _abnahme(buero, welt)
    d1 = _ok(_mangel(buero, a["id"], photos=[("a.png", _png(), "image/png")]))
    d2 = _ok(_mangel(buero, a["id"], photos=[("b.png", _png("red"), "image/png")]))
    assert buero.get(f"/api/defects/{d1['id']}/files/{d2['files'][0]['id']}").status_code == 404


def test_photos_can_only_be_added(welt, buero):
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"], photos=[("a.png", _png(), "image/png")]))
    assert buero.post(f"/api/defects/{d['id']}/photos", files=[]).status_code == 400
    r = buero.post(f"/api/defects/{d['id']}/photos", files=[("photos", ("x.pdf", PDF, "application/pdf"))])
    assert r.status_code == 400
    v = _ok(buero.post(f"/api/defects/{d['id']}/photos", files=[("photos", ("b.png", _png("blue"), "image/png"))]))
    assert len(v["files"]) == 1  # die beim Erfassen bleiben, wie sie waren
    assert v["events"][-1]["kind"] == "fotos" and len(v["events"][-1]["files"]) == 1 and v["intact"] is True


# ---------------------------------------------------------------------------
# Haltung, Status, Freigabe
# ---------------------------------------------------------------------------

def test_stance_with_history(welt, buero):
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    url = f"/api/defects/{d['id']}/stance"
    r = buero.post(url, json={"stance": "bestritten", "reason": " "})
    assert r.status_code == 400 and "begründen" in r.json()["detail"]
    _ok(buero.post(url, json={"stance": "bestritten", "reason": "Abnutzung durch den Nutzer"}))
    assert buero.post(url, json={"stance": "bestritten", "reason": "noch einmal"}).status_code == 409
    assert buero.post(url, json={"stance": "offen", "reason": None}).status_code == 422
    v = _ok(buero.post(url, json={"stance": "anerkannt", "reason": None}))
    assert v["stance"] == "anerkannt"
    assert [(e["value"], e["previous_value"]) for e in v["events"]] == [("bestritten", "offen"), ("anerkannt", "bestritten")]
    assert v["events"][0]["reason"] == "Abnutzung durch den Nutzer"


def test_status_flow_and_rules(welt, buero):
    a = _abnahme(buero, welt, tag=HEUTE - timedelta(days=20))
    d = _ok(_mangel(buero, a["id"]))
    url_tag = lambda n: _iso(HEUTE - timedelta(days=n))  # noqa: E731
    r = _status(buero, d["id"], status="beseitigung_abgenommen", event_date=url_tag(1), reason="x",
                declared_by="auftraggeber")
    assert r.status_code == 409 and "offen" in r.json()["detail"]
    assert _status(buero, d["id"], status="beseitigt").status_code == 400                         # Datum fehlt
    assert _status(buero, d["id"], status="beseitigt", event_date=_iso(HEUTE + timedelta(days=1))).status_code == 400
    r = _status(buero, d["id"], status="beseitigt", event_date=url_tag(30))
    assert r.status_code == 400 and "vor der Abnahme" in r.json()["detail"]
    _ok(_status(buero, d["id"], status="beseitigt", event_date=url_tag(10)))
    r = _status(buero, d["id"], status="offen")
    assert r.status_code == 400 and "begründen" in r.json()["detail"]
    _ok(_status(buero, d["id"], status="offen", reason="Nachbesserung nicht gelungen, weiter feucht"))
    _ok(_status(buero, d["id"], status="beseitigt", event_date=url_tag(5)))
    r = _status(buero, d["id"], status="beseitigung_abgenommen", event_date=url_tag(3), declared_by="auftraggeber")
    assert r.status_code == 400 and "Nachweis" in r.json()["detail"]
    r = _status(buero, d["id"], status="beseitigung_abgenommen", event_date=url_tag(6), declared_by="auftraggeber",
                reason="per E-Mail")
    assert r.status_code == 400 and "vor dem Datum der Beseitigung" in r.json()["detail"]
    assert _status(buero, d["id"], status="beseitigung_abgenommen", event_date=url_tag(3),
                   reason="per E-Mail").status_code == 400                                          # wer?
    v = _ok(_status(buero, d["id"], receipts=[("abnahme.pdf", PDF, "application/pdf")],
                    status="beseitigung_abgenommen", event_date=url_tag(3), declared_by="auftraggeber"))
    assert v["status"] == "beseitigung_abgenommen" and v["done"] is True and v["next_statuses"] == []
    letzter = v["events"][-1]
    assert letzter["declared_by_name"] == welt["db"].get(Order, welt["order_id"]).customer_name
    assert [f["kind"] for f in letzter["files"]] == ["beleg"]
    assert [e["value"] for e in v["events"]] == ["beseitigt", "offen", "beseitigt", "beseitigung_abgenommen"]
    # Endgültig: kein weiterer Status, keine Freigabe mehr.
    assert _status(buero, d["id"], status="offen", reason="doch nicht").status_code == 409
    assert buero.post(f"/api/defects/{d['id']}/release", json={"released": True, "reason": None}).status_code == 409


def test_done_without_remedy_needs_a_reason(welt, buero):
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    assert _status(buero, d["id"], status="erledigt_ohne").status_code == 400
    assert _status(buero, d["id"], status="erledigt_ohne", event_date=_iso(HEUTE), reason="x").status_code == 400
    v = _ok(_status(buero, d["id"], status="erledigt_ohne", reason="Minderung vereinbart"))
    assert v["status_label"] == "erledigt ohne Beseitigung" and v["done"] is True


def test_remedy_declared_by_participant_freezes_the_acceptance_power_of_attorney(welt, buero):
    a = _abnahme(buero, welt)
    for teilnehmer, mit_vollmacht in ((welt["bauleitung"], True), (welt["architektin"], False)):
        d = _ok(_mangel(buero, a["id"]))
        _ok(_status(buero, d["id"], status="beseitigt", event_date=_iso(HEUTE - timedelta(days=2))))
        v = _ok(_status(buero, d["id"], status="beseitigung_abgenommen", event_date=_iso(HEUTE), reason="vor Ort",
                        declared_by="beteiligter", participant_id=teilnehmer))
        e = v["events"][-1]
        assert e["without_power_of_attorney"] is (not mit_vollmacht)
        assert [f["kind"] for f in e["files"]] == (["abnahmevollmacht"] if mit_vollmacht else [])
    d = _ok(_mangel(buero, a["id"]))
    _ok(_status(buero, d["id"], status="beseitigt", event_date=_iso(HEUTE)))
    r = _status(buero, d["id"], status="beseitigung_abgenommen", event_date=_iso(HEUTE), reason="x",
                declared_by="beteiligter", participant_id=welt["fremd_beteiligt"])
    assert r.status_code == 400 and "dieses Projekts" in r.json()["detail"]


def test_release_is_independent_of_the_stance(welt, buero):
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    url = f"/api/defects/{d['id']}/release"
    v = _ok(buero.post(url, json={"released": True, "reason": None}))  # Haltung noch offen: Freigabe geht
    assert v["released"] is True
    assert buero.post(url, json={"released": True, "reason": None}).status_code == 409
    assert buero.post(url, json={"released": False, "reason": None}).status_code == 400  # Zurücknehmen: Begründung
    _ok(buero.post(url, json={"released": False, "reason": "erst Gutachten abwarten"}))
    _ok(buero.post(f"/api/defects/{d['id']}/stance", json={"stance": "bestritten", "reason": "Abnutzung"}))
    r = buero.post(url, json={"released": True, "reason": None})
    assert r.status_code == 400 and "Kulanz" in r.json()["detail"]
    v = _ok(buero.post(url, json={"released": True, "reason": "Kulanz, Stammkunde"}))
    assert v["released"] is True and v["stance"] == "bestritten"
    assert [(e["kind"], e["value"]) for e in v["events"]] == [
        ("freigabe", "freigegeben"), ("freigabe", "zurueckgenommen"), ("haltung", "bestritten"), ("freigabe", "freigegeben")]
    assert buero.post(url, json={"released": "true", "reason": "x"}).status_code == 422  # keine stille Umdeutung


def test_discard_with_reason_once(welt, buero):
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    url = f"/api/defects/{d['id']}/discard"
    assert buero.post(url, json={"reason": ""}).status_code == 422
    v = _ok(buero.post(url, json={"reason": "doppelt erfasst"}))
    assert v["discarded"] is True and v["discard_check"] == "unveraendert" and v["intact"] is True
    assert buero.post(url, json={"reason": "noch einmal"}).status_code == 409
    for r in (buero.post(f"/api/defects/{d['id']}/stance", json={"stance": "anerkannt", "reason": None}),
              _status(buero, d["id"], status="erledigt_ohne", reason="x"),
              buero.post(f"/api/defects/{d['id']}/photos", files=[("photos", ("b.png", _png(), "image/png"))])):
        assert r.status_code == 409 and "verworfen" in r.json()["detail"]
    welt["db"].execute(update(Defect).where(Defect.id == d["id"]).values(discard_reason="anders")
                       .execution_options(synchronize_session=False))
    welt["db"].commit()
    s = _ok(buero.get(f"/api/orders/{welt['order_id']}/defects"))[0]
    assert s["discard_check"] == "abweichend" and s["intact"] is False


def test_named_roof_area_and_declaring_participant_cannot_be_removed(welt, buero):
    a = _abnahme(buero, welt)
    _ok(_mangel(buero, a["id"], roof_area_id=welt["areas"]["Süd"]))
    d = _ok(_mangel(buero, a["id"]))
    _ok(_status(buero, d["id"], status="beseitigt", event_date=_iso(HEUTE)))
    _ok(_status(buero, d["id"], status="beseitigung_abgenommen", event_date=_iso(HEUTE), reason="vor Ort",
                declared_by="beteiligter", participant_id=welt["architektin"]))
    r = buero.delete(f"/api/roof-areas/{welt['areas']['Süd']}")
    assert r.status_code == 400 and "Mangel" in r.json()["detail"]
    r = buero.delete(f"/api/project-participants/{welt['architektin']}")
    assert r.status_code == 409 and "Mangels" in r.json()["detail"]
    assert buero.delete(f"/api/roof-areas/{welt['areas']['Nord']}").status_code == 200  # Gegenprobe


def test_history_in_the_audit_log(welt, buero):
    db = welt["db"]
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    _ok(buero.post(f"/api/defects/{d['id']}/stance", json={"stance": "anerkannt", "reason": None}))
    _ok(buero.post(f"/api/defects/{d['id']}/discard", json={"reason": "doppelt"}))
    eintraege = db.scalars(select(AuditLog).where(AuditLog.entity_type == "Mangel").order_by(AuditLog.id)).all()
    assert [e.action for e in eintraege] == ["angelegt", "angelegt", "verworfen"]
    assert all(e.entity_id == str(d["id"]) and e.project_id == welt["project_id"] for e in eintraege)
    assert json.loads(eintraege[0].details)["description"] == "Anschluss an der Attika undicht"


# ---------------------------------------------------------------------------
# Aufgabe: Verweis in beide Richtungen, der Mangel ist die Wahrheit
# ---------------------------------------------------------------------------

def test_task_without_assignee_due_at_the_deadline_linked_both_ways(welt, buero):
    db = welt["db"]
    frist = HEUTE + timedelta(days=10)
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"], roof_area_id=welt["areas"]["Nord"], remedy_due_on=_iso(frist)))
    task = db.get(Task, d["task"]["id"])
    assert task.assigned_employee_id is None and task.due_date == frist and task.min_visible_role == "buero_auftrag"
    assert task.source_module == "maengel" and task.source_url == f"/orders/{welt['order_id']}#mangel-{d['id']}"
    assert "Nord" in task.title and "Attika" not in (task.description or "")  # nur Metadaten
    assert task.project_id == welt["project_id"] and d["task"]["done"] is False
    # Die Aufgabe erledigen ändert am Mangel nichts -- die Seite sagt es.
    done = db.scalars(select(TaskColumn).where(TaskColumn.is_done.is_(True))).first()
    task.status = done.key
    db.commit()
    v = _ok(buero.get(f"/api/orders/{welt['order_id']}/defects"))[0]
    assert v["status"] == "offen" and v["task"]["done"] is True and "maßgeblich ist der Mangel" in v["task_hint"]


@pytest.mark.parametrize("abschluss", ["erledigt_ohne", "beseitigung_abgenommen", "verworfen"])
def test_finishing_the_defect_completes_the_task(welt, buero, abschluss):
    db = welt["db"]
    d = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    if abschluss == "erledigt_ohne":
        _ok(_status(buero, d["id"], status="erledigt_ohne", reason="Minderung"))
    elif abschluss == "beseitigung_abgenommen":
        _ok(_status(buero, d["id"], status="beseitigt", event_date=_iso(HEUTE)))
        db.expire_all()
        # Seit 1.8.54: "beseitigt" erledigt "Mangel beseitigen" und legt "Beseitigung abnehmen lassen" an
        # (tests/test_v356_maengel_aufgabe_und_hinweis.py); erst die Abnahme der Beseitigung erledigt diese.
        assert db.get(Task, d["task"]["id"]).completed_at is not None
        assert db.scalars(select(Task).where(Task.id != d["task"]["id"])).one().completed_at is None
        _ok(_status(buero, d["id"], status="beseitigung_abgenommen", event_date=_iso(HEUTE), reason="vor Ort",
                    declared_by="auftraggeber"))
    else:
        _ok(buero.post(f"/api/defects/{d['id']}/discard", json={"reason": "doppelt"}))
    db.expire_all()
    task = db.get(Task, d["task"]["id"])
    assert task.completed_at is not None and db.get(TaskColumn, 1) is not None
    done_keys = {c.key for c in db.scalars(select(TaskColumn).where(TaskColumn.is_done.is_(True)))}
    assert all(t.status in done_keys and t.completed_at is not None for t in db.scalars(select(Task)))


def test_without_task_module_no_task_and_deleted_task_is_shown(welt, buero):
    db = welt["db"]
    db.add(EnabledModule(module_key="aufgabenmanagement", enabled=False))
    db.commit()
    a = _abnahme(buero, welt)
    d = _ok(_mangel(buero, a["id"]))
    assert d["task"]["exists"] is False and "Aufgabenmodul" in d["task"]["text"] and _anzahl(db, Task) == 0
    db.get(EnabledModule, db.scalars(select(EnabledModule.id)).first()).enabled = True
    db.commit()
    d2 = _ok(_mangel(buero, a["id"]))
    db.delete(db.get(Task, d2["task"]["id"]))
    db.commit()
    v = {x["id"]: x for x in _ok(buero.get(f"/api/orders/{welt['order_id']}/defects"))}[d2["id"]]
    assert v["task"]["exists"] is False and "gelöscht" in v["task"]["text"] and v["intact"] is True
    _ok(_status(buero, d2["id"], status="erledigt_ohne", reason="Minderung"))  # ohne Aufgabe kein Fehler


# ---------------------------------------------------------------------------
# Nachbesserung regulär bis (nur VOB/B)
# ---------------------------------------------------------------------------

def _beseitigt_und_abgenommen(buero, defect_id, beseitigt: date, abgenommen: date):
    _ok(_status(buero, defect_id, status="beseitigt", event_date=_iso(beseitigt)))
    return _ok(_status(buero, defect_id, status="beseitigung_abgenommen", event_date=_iso(abgenommen),
                       reason="vor Ort", declared_by="auftraggeber"))


def test_remedy_end_is_the_later_of_regular_end_and_remedy_plus_24_months(welt, buero):
    abnahme_tag, abgenommen = date(2026, 8, 31), date(2026, 9, 30)
    a = _abnahme(buero, welt, tag=abnahme_tag)
    d = _ok(_mangel(buero, a["id"]))
    v = _beseitigt_und_abgenommen(buero, d["id"], date(2026, 9, 29), abgenommen)
    w = v["remedy_warranty"]
    assert w["end"] is None and "nicht festgelegt" in w["text"]  # ohne Dauer nicht berechenbar
    _dauer(buero, welt, 48, grund=None)  # Regelende 31.08.2030 > 30.09.2028
    w = _ok(buero.get(f"/api/orders/{welt['order_id']}/defects"))[0]["remedy_warranty"]
    assert (w["end"], w["regular_end"], w["remedy_end"]) == ("2030-08-31", "2030-08-31", "2028-09-30")
    assert w["check"] == {"ok": True, "text": "Prüfsumme stimmt"} and "§ 13 Abs. 5 Nr. 1 Satz 3 VOB/B" in w["rule"]
    r = buero.put(f"/api/orders/{welt['order_id']}/warranty",
                  json={"work_kind": "sonstige", "warranty_months": 12, "warranty_days": 0, "reason": "nur Reparatur"})
    assert r.status_code == 200, r.text  # Regelende 31.08.2027 < 30.09.2028
    w = _ok(buero.get(f"/api/orders/{welt['order_id']}/defects"))[0]["remedy_warranty"]
    assert (w["end"], w["regular_end"]) == ("2028-09-30", "2027-08-31")
    assert w["text"].startswith("Nachbesserung regulär bis 30.09.2028")
    # Prüfstatus: die Abnahme weicht ab -> auch das Ende der Nachbesserung ist nicht verlässlich.
    welt["db"].execute(update(OrderAcceptance).where(OrderAcceptance.id == a["id"]).values(kind="schluessig")
                       .execution_options(synchronize_session=False))
    welt["db"].commit()
    w = _ok(buero.get(f"/api/orders/{welt['order_id']}/defects"))[0]["remedy_warranty"]
    assert w["check"]["ok"] is False


def test_remedy_end_only_for_vob_b(welt, buero):
    a = _abnahme(buero, welt, tag=date(2026, 8, 31))
    _dauer(buero, welt, 48)
    d = _ok(_mangel(buero, a["id"]))
    assert _beseitigt_und_abgenommen(buero, d["id"], date(2026, 9, 29), date(2026, 9, 30))["remedy_warranty"]["end"]
    db = welt["db"]
    change_order_contract_basis(db, db.get(Order, welt["order_id"]), contract_basis="bgb", reason="BGB-Vertrag")
    assert _ok(buero.get(f"/api/orders/{welt['order_id']}/defects"))[0]["remedy_warranty"] is None


def test_remedy_at_a_refused_acceptance_has_no_regular_end(welt, buero):
    a = _abnahme(buero, welt, "verweigert", tag=date(2026, 8, 31))
    _dauer(buero, welt, 48)
    d = _ok(_mangel(buero, a["id"]))
    w = _beseitigt_und_abgenommen(buero, d["id"], date(2026, 9, 29), date(2026, 9, 30))["remedy_warranty"]
    assert w["end"] is None and "verweigert" in w["text"]


# ---------------------------------------------------------------------------
# Angriff: Monteur liest Mängel
# ---------------------------------------------------------------------------

def test_attack_field_worker_reads_no_defects(welt, buero, router_test_client):
    a = _abnahme(buero, welt)
    d = _ok(_mangel(buero, a["id"], photos=[("a.png", _png(), "image/png")]))
    monteur = router_test_client(welt["db"], *_routers(), role="field")
    for url in (f"/api/orders/{welt['order_id']}/defects", f"/api/order-acceptances/{a['id']}/defect-options",
                f"/api/defects/{d['id']}/files/{d['files'][0]['id']}"):
        assert monteur.get(url).status_code == 403, url
    assert _mangel(monteur, a["id"]).status_code == 403
    for pfad, body in (("stance", {"stance": "anerkannt", "reason": None}), ("release", {"released": True, "reason": "x"}),
                       ("discard", {"reason": "x"})):
        assert monteur.post(f"/api/defects/{d['id']}/{pfad}", json=body).status_code == 403
    assert _status(monteur, d["id"], status="erledigt_ohne", reason="x").status_code == 403
    assert monteur.post(f"/api/defects/{d['id']}/photos", files=[("photos", ("b.png", _png(), "image/png"))]).status_code == 403
    assert _anzahl(welt["db"]) == 1 and _anzahl(welt["db"], DefectEvent) == 0
    # Die Aufgabe ist Büro (ohne Zuständigkeit, Sichtbarkeitsgrenze buero_auftrag) -- der Monteur sieht sie nicht.
    assert all(t["id"] != d["task"]["id"] for t in monteur.get("/api/tasks").json()) \
        if monteur.get("/api/tasks").status_code == 200 else True


# ---------------------------------------------------------------------------
# Oberfläche
# ---------------------------------------------------------------------------

def test_order_page_carries_the_defect_card(welt, router_test_client):
    from app.routers import pages
    html = router_test_client(welt["db"], pages.router, role="buero_auftrag").get(f"/orders/{welt['order_id']}").text
    assert 'id="defectCard"' in html and 'id="defectDialog"' in html and "function loadDefects(" in html
    teil = html.split('id="defectCard"')[1]
    assert "prompt(" not in teil  # Regel 4


def test_defect_dialog_has_no_preselection():
    source = (ROOT / "app" / "templates" / "_maengel.html").read_text(encoding="utf-8")
    dialog = source.split('id="defectDialog"')[1].split("</dialog>")[0]
    assert " checked" not in dialog and " selected" not in dialog and "value=\"20" not in dialog


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def _migration():
    path = next(ROOT.glob("alembic/versions/*_maengel_aus_der_abnahme.py"))
    spec = importlib.util.spec_from_file_location("migration_1849_maengel", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_down_refuses_while_defects_exist():
    module = _migration()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    def run(name):
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                getattr(module, name)()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO defects (order_id, source, acceptance_id, description, content_sha256, "
                          "checksum_format, created_at, created_by_name) VALUES (1, 'abnahme', 1, 'x', 'y', 1, "
                          "'2026-10-05 00:00:00', 'X')"))
    with pytest.raises(RuntimeError, match="1 Mängel"):
        run("downgrade")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM defects"))
    run("downgrade")
    assert not {"defects", "defect_events", "defect_files"} & set(inspect(engine).get_table_names())
    run("upgrade")
    assert {"defects", "defect_events", "defect_files"} <= set(inspect(engine).get_table_names())


# ---------------------------------------------------------------------------
# PostgreSQL: Sperren
# ---------------------------------------------------------------------------

@pytest.fixture
def pg(monkeypatch, tmp_path):
    if not PG_TEST_DATABASE_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    monkeypatch.setattr(acceptances_module, "ACCEPTANCE_FILE_ROOT", tmp_path / "abnahmen")
    schema = f"pgtest_maengel_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_TEST_DATABASE_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, pool_size=5,
                           connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        from app.grunddaten import anlegen
        Session = sessionmaker(bind=engine)
        setup = Session()
        try:
            anlegen(setup)
            setup.commit()
            welt = _welt(setup)
            order = setup.get(Order, welt["order_id"])
            a = acceptances_module.create_acceptance(
                setup, order, {**GUELTIG, "accepted_on": HEUTE - timedelta(days=5), "reservation_defects": True,
                               "roof_area_ids": []}, [("beleg.pdf", PDF)], user_id=None, user_name="PG")
            welt["acceptance_id"] = a.id
        finally:
            setup.close()
        yield Session, welt
    finally:
        close_all_sessions()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"),
                         {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def _pg_create(Session, welt):
    db = Session()
    try:
        return defects_module.create_defect(db, db.get(OrderAcceptance, welt["acceptance_id"]),
                                            {"description": "undicht", "remedy_due_on": None}, [],
                                            user_id=None, user_name="PG").id
    finally:
        db.close()


def test_postgresql_defect_waits_for_discarding_the_acceptance(pg):
    """Das Verwerfen der Abnahme hält die Sperre der Auftragszeile -- ein gleichzeitiges Erfassen wartet und sieht
    danach die verworfene Abnahme (409). Ohne die Sperre beim Erfassen liefe es durch."""
    Session, welt = pg
    holder, ready = Session(), threading.Event()

    def hold(release):
        def run():
            acceptance = holder.get(OrderAcceptance, welt["acceptance_id"])
            commit = holder.commit

            def angehalten():
                holder.flush()
                ready.set()
                release.wait(timeout=30)
                commit()
            holder.commit = angehalten
            acceptances_module.discard_acceptance(holder, acceptance, reason="falsch", user_id=None, user_name="PG")
        threading.Thread(target=run).start()
        ready.wait(timeout=10)
    done = _waits_for(hold, lambda: _pg_create(Session, welt))
    time.sleep(0.2)
    holder.close()
    assert isinstance(done["result"], defects_module.DefectConflict) and done["seconds"] >= 0.9


def test_postgresql_two_status_changes_at_once(pg):
    """Zwei Bearbeiter setzen gleichzeitig "erledigt ohne Beseitigung" -- der zweite wartet auf die Sperre des
    Mangels und bekommt dann 409 statt eines zweiten Eintrags."""
    Session, welt = pg
    defect_id = _pg_create(Session, welt)
    holder, ready = Session(), threading.Event()

    def hold(release):
        def run():
            defect = holder.get(Defect, defect_id)
            commit = holder.commit

            def angehalten():
                holder.flush()
                ready.set()
                release.wait(timeout=30)
                commit()
            holder.commit = angehalten
            defects_module.set_status(holder, defect, {"status": "erledigt_ohne", "reason": "Minderung"}, [],
                                      user_id=None, user_name="A")
        threading.Thread(target=run).start()
        ready.wait(timeout=10)

    def second():
        db = Session()
        try:
            return defects_module.set_status(db, db.get(Defect, defect_id),
                                             {"status": "erledigt_ohne", "reason": "auch"}, [], user_id=None,
                                             user_name="B")
        finally:
            db.close()
    done = _waits_for(hold, second)
    time.sleep(0.2)
    holder.close()
    assert isinstance(done["result"], defects_module.DefectConflict) and done["seconds"] >= 0.9
    check = Session()
    try:
        assert len(check.scalars(select(DefectEvent).where(DefectEvent.defect_id == defect_id)).all()) == 1
    finally:
        check.close()
