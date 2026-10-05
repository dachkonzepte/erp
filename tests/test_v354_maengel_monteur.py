"""Version 1.8.52 -- Stufe 2c-2b, Punkt 1: Monteur-Sicht auf Mängel in /mobil (docs/archiv/abnahme-und-gewaehrleistung.md,
"Umsetzung 1.8.52").

- Der Monteur sieht nur freigegebene, offene, nicht verworfene Mängel der Aufträge, die er öffnen darf
  (app/orders.py::field_may_access_order()); wird die Freigabe zurückgenommen, verschwindet der Mangel.
- Felder als Positivliste (Beschreibung, Ort, Dachfläche, Frist, Fotos, dazu Auftrag und Objekt) -- keine Haltung, keine
  Abnahmedaten, keine Gewährleistung. Rekursiver Scan aller Schlüssel, Gegenprobe an der Büro-Antwort.
- "Beseitigt" melden mit mindestens einem Foto, idempotent über client_uuid (Stufe 3).
- Fotos nur über den eigenen Monteur-Weg mit derselben Prüfung; Belege und Vollmachten nie.

Angriffe mit Gegenprobe: nicht freigegebener Mangel, Mangel eines fremden Auftrags, Foto eines solchen Mangels, Schlüssel
außerhalb der Positivliste, doppelte Meldung, fremde Kennung. Gegen PostgreSQL (opt-in über ERP_TEST_POSTGRES_URL): zwei
gleichzeitige Meldungen mit derselben Kennung, Meldung gegen gleichzeitiges Zurücknehmen der Freigabe."""

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
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import close_all_sessions, sessionmaker

from app import acceptances as acceptances_module
from app import defects as defects_module
from app.auth import hash_password
from app.berlin_time import berlin_today
from app.database import Base, get_db
from app.models import (
    AppUser, Defect, DefectEvent, DefectFile, Employee, Order, OrderAcceptance, Task, WorkPreparationEmployee,
)
from app.routers import field_defects as field_defects_router
from app.work_preparation import ensure_preparation
from tests.test_v349_abnahme_und_gewaehrleistung import (  # noqa: F401  (Fixtures)
    GUELTIG, PDF, PG_TEST_DATABASE_URL, _erfassen, _png, _waits_for, _welt, ablage, welt,
)
from tests.test_v351_maengel import _abnahme, _anzahl, _iso, _mangel, _ok, _routers, _status, buero  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
HEUTE = berlin_today()

# Die Positivliste je Pfad der Antwort -- jeder andere Schlüssel, auch verschachtelt, ist ein Verstoß.
LISTE_ERLAUBT = {
    "$[]": {"id", "order_id", "order_number", "property_name", "property_address", "description", "location",
            "roof_area_name", "remedy_due_on", "remedy_overdue", "photos"},
    "$[].photos[]": {"id"},
}
MELDUNG_ERLAUBT = {"$": {"defect_id", "event_id", "event_date", "photo_count"}}


def _ausserhalb(value, erlaubt: dict[str, set], path="$") -> list[str]:
    """Jeder Schlüssel einer Antwort, der für seinen Pfad nicht in der Positivliste steht -- rekursiv."""
    funde = []
    if isinstance(value, dict):
        for key, inner in value.items():
            if key not in erlaubt.get(path, set()):
                funde.append(f"{path}.{key}")
            funde += _ausserhalb(inner, erlaubt, f"{path}.{key}")
    elif isinstance(value, list):
        for inner in value:
            funde += _ausserhalb(inner, erlaubt, f"{path}[]")
    return funde


# ---------------------------------------------------------------------------
# Welt: Monteurin Mia und Kollege Karl, beide über die Arbeitsvorbereitung dem Auftrag zugeordnet; der zweite Auftrag
# aus _welt() ist keinem von beiden zugeordnet.
# ---------------------------------------------------------------------------

def _client_als(db, user_id: int) -> TestClient:
    app = FastAPI()
    for router in (*_routers(), field_defects_router.router):
        app.include_router(router)

    @app.middleware("http")
    async def _ich(request, call_next):
        request.state.erp_user = db.get(AppUser, user_id)
        return await call_next(request)

    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _monteur(db, name: str, order_ids: list[int]) -> dict:
    vorname, nachname = name.split()
    emp = Employee(employee_number=f"M-{vorname}", first_name=vorname, last_name=nachname, employee_group="gewerblich",
                   active=True)
    db.add(emp)
    db.flush()
    user = AppUser(username=vorname.lower(), display_name=name, role="field", employee_id=emp.id, active=True,
                   password_hash=hash_password("Passwort123"))
    db.add(user)
    for order_id in order_ids:
        prep = ensure_preparation(db, order_id)
        db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=emp.id))
    db.commit()
    return {"client": _client_als(db, user.id), "user_id": user.id, "employee_id": emp.id}


@pytest.fixture
def mia(welt):
    return _monteur(welt["db"], "Mia Monteurin", [welt["order_id"]])


@pytest.fixture
def karl(welt):
    return _monteur(welt["db"], "Karl Kollege", [welt["order_id"]])


def _freigeben(buero, defect_id, freigegeben=True, reason=None):
    return _ok(buero.post(f"/api/defects/{defect_id}/release",
                          json={"released": freigegeben, "reason": reason or (None if freigegeben else "zurück")}))


def _freigegebener_mangel(buero, welt, **werte):
    a = _abnahme(buero, welt)
    werte = {"photos": [("vorher.png", _png("red"), "image/png")], **werte}
    d = _ok(_mangel(buero, a["id"], **werte))
    _freigeben(buero, d["id"])
    return d


def _liste(monteur):
    r = monteur["client"].get("/api/field-view/defects")
    assert r.status_code == 200, r.text
    return r.json()


def _melden(monteur, defect_id, photos=(("nachher.png", _png("green"), "image/png"),), kennung=None, datum=None,
            **extra):
    data = {"client_uuid": kennung or str(uuid.uuid4()), "event_date": _iso(datum or HEUTE), **extra}
    data = {k: v for k, v in data.items() if v is not ...}
    return monteur["client"].post(f"/api/field-view/defects/{defect_id}/remedied", data={"data": json.dumps(data)},
                                  files=[("photos", p) for p in photos])


def _foto(monteur, defect_id, file_id):
    return monteur["client"].get(f"/api/field-view/defects/{defect_id}/photos/{file_id}")


# ---------------------------------------------------------------------------
# Was der Monteur sieht
# ---------------------------------------------------------------------------

def test_field_worker_sees_only_released_open_defects_of_his_orders(welt, buero, mia):
    sichtbar = _freigegebener_mangel(buero, welt, description="Attika undicht")
    nicht_freigegeben = _ok(_mangel(buero, _abnahme(buero, welt)["id"], description="noch nicht freigegeben"))
    zurueckgenommen = _freigegebener_mangel(buero, welt, description="Freigabe zurückgenommen")
    _freigeben(buero, zurueckgenommen["id"], False)
    beseitigt = _freigegebener_mangel(buero, welt, description="vom Büro als beseitigt gesetzt")
    _ok(_status(buero, beseitigt["id"], status="beseitigt", event_date=_iso(HEUTE)))
    erledigt = _freigegebener_mangel(buero, welt, description="erledigt ohne Beseitigung")
    _ok(_status(buero, erledigt["id"], status="erledigt_ohne", reason="Minderung"))
    verworfen = _freigegebener_mangel(buero, welt, description="verworfen")
    _ok(buero.post(f"/api/defects/{verworfen['id']}/discard", json={"reason": "doppelt"}))
    fremd = _erfassen(buero, welt["other_order_id"], reservation_defects=True)
    fremder = _ok(_mangel(buero, fremd.json()["id"], description="fremder Auftrag"))
    _freigeben(buero, fremder["id"])

    assert [x["description"] for x in _liste(mia)] == ["Attika undicht"]
    # Gegenprobe: freigeben -> erscheint; wieder offen gesetzt -> erscheint wieder.
    _freigeben(buero, nicht_freigegeben["id"])
    _ok(_status(buero, beseitigt["id"], status="offen", reason="Nachbesserung misslungen"))
    assert sorted(x["id"] for x in _liste(mia)) == sorted([sichtbar["id"], nicht_freigegeben["id"], beseitigt["id"]])


def test_withdrawing_the_release_makes_the_defect_disappear(welt, buero, mia):
    d = _freigegebener_mangel(buero, welt)
    foto_id = _liste(mia)[0]["photos"][0]["id"]
    assert _foto(mia, d["id"], foto_id).status_code == 200
    _freigeben(buero, d["id"], False, "Kunde zieht die Rüge zurück")
    assert _liste(mia) == []
    assert _foto(mia, d["id"], foto_id).status_code == 404
    assert _melden(mia, d["id"]).status_code == 404
    assert _anzahl(welt["db"], DefectEvent) == 2  # Freigabe und Zurücknahme, keine Meldung
    # Gegenprobe: erneut freigegeben -> wieder da.
    _freigeben(buero, d["id"], reason="doch beseitigen")
    assert [x["id"] for x in _liste(mia)] == [d["id"]]


def test_positive_list_recursive_scan(welt, buero, mia):
    frist = HEUTE - timedelta(days=1)
    d = _freigegebener_mangel(buero, welt, roof_area_id=welt["areas"]["Nord"], location="Attika West",
                              remedy_due_on=_iso(frist), receipts=[("ruege.pdf", PDF, "application/pdf")])
    _ok(buero.post(f"/api/defects/{d['id']}/stance", json={"stance": "bestritten", "reason": "Abnutzung"}))
    _ok(buero.post(f"/api/defects/{d['id']}/photos", files=[("photos", ("mehr.png", _png("blue"), "image/png"))]))
    _ok(buero.post(f"/api/defects/{d['id']}/receipts", files=[("receipts", ("brief.png", _png("gray"), "image/png"))]))
    liste = _liste(mia)
    assert _ausserhalb(liste, LISTE_ERLAUBT) == []
    eintrag = liste[0]
    order = welt["db"].get(Order, welt["order_id"])
    # Objekt: das der Abnahme (dort ist der Mangel), nicht der Schnappschuss am Auftrag.
    assert order.property_name != "Halle"
    assert eintrag == {
        "id": d["id"], "order_id": order.id, "order_number": order.order_number, "property_name": "Halle",
        "property_address": "Hallenweg 1, 52531 Uebach", "description": "Anschluss an der Attika undicht",
        "location": "Attika West", "roof_area_name": "Nord", "remedy_due_on": _iso(frist), "remedy_overdue": True,
        "photos": eintrag["photos"],
    }
    # Fotos: das beim Erfassen und das ergänzte -- nie Belege (auch nicht der als Bild).
    db = welt["db"]
    fotos = sorted(f.id for f in db.scalars(select(DefectFile).where(DefectFile.defect_id == d["id"],
                                                                       DefectFile.kind == "foto")))
    assert [p["id"] for p in eintrag["photos"]] == fotos and len(fotos) == 2
    # Gegenprobe: derselbe Scan findet in der Büro-Antwort, was der Monteur nicht bekommt.
    buero_funde = _ausserhalb(_ok(buero.get(f"/api/orders/{welt['order_id']}/defects")), LISTE_ERLAUBT)
    for teil in ("$[].stance", "$[].acceptance", "$[].remedy_warranty", "$[].events", "$[].task", "$[].files"):
        assert teil in buero_funde, teil


def test_monteur_route_drops_keys_outside_the_positive_list(welt, buero, mia, monkeypatch):
    """Selbst wenn die Geschäftslogik mehr liefert, kommt beim Monteur nur die Positivliste an (Antwortschema)."""
    _freigegebener_mangel(buero, welt)
    original = defects_module.field_defect_dict

    def mehr(*args, **kwargs):
        return {**original(*args, **kwargs), "stance": "bestritten", "acceptance_id": 1,
                "photos": [{"id": 1, "kind": "beleg", "sha256": "x"}]}
    monkeypatch.setattr(defects_module, "field_defect_dict", mehr)
    assert _ausserhalb(_liste(mia), LISTE_ERLAUBT) == []


# ---------------------------------------------------------------------------
# Fotos nur über den Monteur-Weg
# ---------------------------------------------------------------------------

def test_photos_only_via_the_field_route(welt, buero, mia):
    d = _freigegebener_mangel(buero, welt, receipts=[("brief.png", _png("gray"), "image/png")])
    db = welt["db"]
    foto = db.scalar(select(DefectFile).where(DefectFile.defect_id == d["id"], DefectFile.kind == "foto"))
    beleg = db.scalar(select(DefectFile).where(DefectFile.defect_id == d["id"], DefectFile.kind == "beleg"))
    r = _foto(mia, d["id"], foto.id)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.content == _png("red")
    assert _foto(mia, d["id"], beleg.id).status_code == 404  # ein Beleg ist kein Foto, auch als Bild
    assert mia["client"].get(f"/api/defects/{d['id']}/files/{foto.id}").status_code == 403  # Büro-Weg gesperrt


def test_attack_photo_of_unreleased_or_foreign_defect(welt, buero, mia):
    db = welt["db"]
    offen = _ok(_mangel(buero, _abnahme(buero, welt)["id"], photos=[("a.png", _png("red"), "image/png")]))
    fremd = _erfassen(buero, welt["other_order_id"], reservation_defects=True).json()
    fremder = _ok(_mangel(buero, fremd["id"], photos=[("b.png", _png("blue"), "image/png")]))
    _freigeben(buero, fremder["id"])
    eigener = _freigegebener_mangel(buero, welt)

    def foto_von(defect_id):
        return db.scalar(select(DefectFile.id).where(DefectFile.defect_id == defect_id))
    assert _foto(mia, offen["id"], foto_von(offen["id"])).status_code == 404
    assert _foto(mia, fremder["id"], foto_von(fremder["id"])).status_code == 404
    # Über einen sichtbaren Mangel an das Foto eines anderen: 404.
    assert _foto(mia, eigener["id"], foto_von(offen["id"])).status_code == 404
    assert _foto(mia, eigener["id"], foto_von(fremder["id"])).status_code == 404
    # Gegenprobe: freigegeben bzw. zugeordnet -> 200.
    _freigeben(buero, offen["id"])
    assert _foto(mia, offen["id"], foto_von(offen["id"])).status_code == 200
    prep = ensure_preparation(db, welt["other_order_id"])
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=mia["employee_id"]))
    db.commit()
    assert _foto(mia, fremder["id"], foto_von(fremder["id"])).status_code == 200


# ---------------------------------------------------------------------------
# "Beseitigt" melden
# ---------------------------------------------------------------------------

def test_report_remedied_with_photo(welt, buero, mia, ablage):
    db = welt["db"]
    d = _freigegebener_mangel(buero, welt, remedy_due_on=_iso(HEUTE + timedelta(days=5)))
    kennung = str(uuid.uuid4())
    r = _melden(mia, d["id"], kennung=kennung, datum=HEUTE - timedelta(days=1),
                photos=[("n1.png", _png("green"), "image/png"), ("n2.jpg", _png("yellow"), "image/png")])
    antwort = _ok(r)
    assert _ausserhalb(antwort, MELDUNG_ERLAUBT) == []
    event = db.get(DefectEvent, antwort["event_id"])
    assert antwort == {"defect_id": d["id"], "event_id": event.id, "event_date": _iso(HEUTE - timedelta(days=1)),
                       "photo_count": 2}
    assert (event.kind, event.value, event.previous_value, event.client_uuid) == ("status", "beseitigt", "offen", kennung)
    assert event.created_by_name == "Mia Monteurin" and event.created_by_user_id == mia["user_id"]
    assert [f.kind for f in event.files] == ["foto", "foto"] and event.reason is None and event.declared_by is None
    # Danach nicht mehr in /mobil; das Büro sieht "beseitigt" mit Fotos und "gemeldet in der Monteursansicht".
    assert _liste(mia) == []
    buero_sicht = _ok(buero.get(f"/api/orders/{welt['order_id']}/defects"))[0]
    assert buero_sicht["status"] == "beseitigt" and buero_sicht["intact"] is True
    assert buero_sicht["events"][-1]["via_field_view"] is True and len(buero_sicht["events"][-1]["files"]) == 2
    assert buero_sicht["events"][0]["via_field_view"] is False
    # Die aktuelle Aufgabe ist offen -- seit 1.8.54 "Beseitigung abnehmen lassen" (test_v356); erledigt ist der Mangel
    # erst mit der Abnahme der Beseitigung.
    assert buero_sicht["task"]["done"] is False and buero_sicht["task"]["kind_label"] == "Beseitigung abnehmen lassen"
    # Das Büro kann weiterschreiben.
    _ok(_status(buero, d["id"], status="beseitigung_abgenommen", event_date=_iso(HEUTE), reason="vor Ort abgenommen",
                declared_by="auftraggeber"))


@pytest.mark.parametrize("fall", ["ohne_foto", "pdf_als_foto", "zukunft", "vor_abnahme", "ohne_kennung",
                                  "kennung_zu_lang", "fremdes_feld", "ohne_datum"])
def test_report_needs_photo_date_and_key(welt, buero, mia, ablage, fall):
    d = _freigegebener_mangel(buero, welt)
    vorher = sorted(p.name for p in ablage.rglob("*.*"))
    werte = {
        "ohne_foto": {"photos": ()},
        "pdf_als_foto": {"photos": [("x.pdf", PDF, "application/pdf")]},
        "zukunft": {"datum": HEUTE + timedelta(days=1)},
        "vor_abnahme": {"datum": HEUTE - timedelta(days=60)},
        "ohne_kennung": {"kennung": ""},
        "kennung_zu_lang": {"kennung": "x" * 37},
        "fremdes_feld": {"reason": "Monteur schreibt Begründung"},
        "ohne_datum": {"event_date": ...},
    }[fall]
    if fall == "ohne_kennung":
        r = mia["client"].post(f"/api/field-view/defects/{d['id']}/remedied",
                               data={"data": json.dumps({"client_uuid": "", "event_date": _iso(HEUTE)})},
                               files=[("photos", ("n.png", _png("green"), "image/png"))])
    else:
        r = _melden(mia, d["id"], **werte)
    assert r.status_code in (400, 422), (fall, r.status_code, r.text)
    assert _anzahl(welt["db"], DefectEvent) == 1  # nur die Freigabe
    assert sorted(p.name for p in ablage.rglob("*.*")) == vorher
    assert [x["id"] for x in _liste(mia)] == [d["id"]]


def test_attack_report_on_hidden_defects_is_404_and_stores_nothing(welt, buero, mia, ablage):
    db = welt["db"]
    nicht_freigegeben = _ok(_mangel(buero, _abnahme(buero, welt)["id"]))
    fremd = _erfassen(buero, welt["other_order_id"], reservation_defects=True).json()
    fremder = _ok(_mangel(buero, fremd["id"]))
    _freigeben(buero, fremder["id"])
    verworfen = _freigegebener_mangel(buero, welt)
    _ok(buero.post(f"/api/defects/{verworfen['id']}/discard", json={"reason": "doppelt"}))
    vorher_events = _anzahl(db, DefectEvent)
    vorher_dateien = sorted(p.name for p in ablage.rglob("*.*"))
    for defect_id in (nicht_freigegeben["id"], fremder["id"], verworfen["id"], 999_999):
        r = _melden(mia, defect_id)
        assert r.status_code == 404 and r.json()["detail"] == "Mangel nicht gefunden.", defect_id
    assert _anzahl(db, DefectEvent) == vorher_events and sorted(p.name for p in ablage.rglob("*.*")) == vorher_dateien
    # Gegenprobe: der freigegebene eigene geht.
    _freigeben(buero, nicht_freigegeben["id"])
    assert _melden(mia, nicht_freigegeben["id"]).status_code == 200


def test_double_report_with_the_same_key_is_idempotent(welt, buero, mia, ablage):
    db = welt["db"]
    d = _freigegebener_mangel(buero, welt)
    kennung = str(uuid.uuid4())
    erste = _ok(_melden(mia, d["id"], kennung=kennung))
    dateien = sorted(p.name for p in ablage.rglob("*.*"))
    zweite = _ok(_melden(mia, d["id"], kennung=kennung, photos=[("anders.png", _png("black"), "image/png")]))
    assert zweite == erste and _anzahl(db, DefectEvent) == 2  # Freigabe und genau eine Meldung
    assert sorted(p.name for p in ablage.rglob("*.*")) == dateien  # keine zweite Datei
    # Auch nachdem das Büro weitergeschrieben hat (Mangel für den Monteur unsichtbar): dieselbe Antwort.
    _ok(_status(buero, d["id"], status="beseitigung_abgenommen", event_date=_iso(HEUTE), reason="abgenommen",
                declared_by="auftraggeber"))
    assert _ok(_melden(mia, d["id"], kennung=kennung)) == erste
    # Eine zweite Meldung mit neuer Kennung: der Mangel ist nicht mehr zu beseitigen -> 404, nichts gespeichert.
    assert _melden(mia, d["id"]).status_code == 404
    assert _anzahl(db, DefectEvent) == 3


def test_attack_key_of_another_worker_or_defect_is_rejected(welt, buero, mia, karl):
    db = welt["db"]
    d1 = _freigegebener_mangel(buero, welt)
    d2 = _freigegebener_mangel(buero, welt)
    kennung = str(uuid.uuid4())
    _ok(_melden(mia, d1["id"], kennung=kennung))
    vorher = _anzahl(db, DefectEvent)
    r = _melden(karl, d1["id"], kennung=kennung)  # Karl wiederholt Mias Kennung
    assert r.status_code == 400 and "bereits vergeben" in r.json()["detail"]
    r = _melden(mia, d2["id"], kennung=kennung)  # dieselbe Kennung an einem anderen Mangel
    assert r.status_code == 400 and "bereits vergeben" in r.json()["detail"]
    assert _anzahl(db, DefectEvent) == vorher
    # Gegenprobe: Karl mit eigener Kennung am zweiten Mangel.
    assert _melden(karl, d2["id"]).status_code == 200


def test_unique_key_in_the_database(welt, buero, mia):
    """Zweite Absicherung (gleichzeitige Wiederholung unter SQLite ohne Zeilensperre): UNIQUE auf client_uuid."""
    db = welt["db"]
    d = _freigegebener_mangel(buero, welt)
    kennung = str(uuid.uuid4())
    _ok(_melden(mia, d["id"], kennung=kennung))
    with pytest.raises(IntegrityError):
        db.execute(text("INSERT INTO defect_events (defect_id, kind, client_uuid, content_sha256, checksum_format, "
                        "created_at, created_by_name) VALUES (:d, 'fotos', :k, 'x', 1, '2026-10-05 00:00:00', 'X')"),
                   {"d": d["id"], "k": kennung})
    db.rollback()


def test_concurrent_repeat_falls_back_to_the_stored_report(welt, buero, mia, monkeypatch):
    """Kommt die Wiederholung an der Prüfung vorbei (gleichzeitig, unter SQLite keine Zeilensperre), fängt der
    UNIQUE-Schlüssel sie: Antwort ist die gespeicherte Meldung, kein 500, keine zweite."""
    db = welt["db"]
    d = _freigegebener_mangel(buero, welt)
    kennung = str(uuid.uuid4())
    erste = _ok(_melden(mia, d["id"], kennung=kennung))
    # Das Büro setzt zurück auf offen -- der Mangel ist wieder sichtbar, die Wiederholung käme bis zum Einfügen.
    _ok(_status(buero, d["id"], status="offen", reason="Nachbesserung misslungen"))
    vorher = _anzahl(db, DefectEvent)
    echte, aufrufe = defects_module._event_by_key, []

    def blind(db_, key):  # die drei Nachfragen vor dem Einfügen (Router, vor und unter der Sperre) sehen sie nicht
        aufrufe.append(key)
        return None if len(aufrufe) <= 3 else echte(db_, key)
    monkeypatch.setattr(defects_module, "_event_by_key", blind)
    assert _ok(_melden(mia, d["id"], kennung=kennung)) == erste
    assert len(aufrufe) == 4 and _anzahl(db, DefectEvent) == vorher


def test_office_account_without_employee_gets_422(welt, router_test_client):
    client = router_test_client(welt["db"], field_defects_router.router, role="buero_auftrag")
    assert client.get("/api/field-view/defects").status_code == 422


def test_mobil_page_carries_the_defect_section(welt, router_test_client, mia):
    from app.routers import pages
    html = router_test_client(welt["db"], pages.router, role="field", employee_id=mia["employee_id"]).get("/mobil").text
    assert 'id="defectsList"' in html and "/api/field-view/defects" in html and "/remedied" in html
    teil = html.split('id="defectsList"')[1]
    assert "prompt(" not in teil  # Regel 4
    assert "/api/defects/" not in html  # kein Büro-Weg in der Monteursansicht


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def _migration():
    path = next(ROOT.glob("alembic/versions/*_maengel_meldung_monteur.py"))
    spec = importlib.util.spec_from_file_location("migration_1852_maengel_monteur", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_adds_and_removes_the_key():
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
    assert "client_uuid" not in spalten()
    run("upgrade")
    assert "client_uuid" in spalten()
    assert any(u["column_names"] == ["client_uuid"] for u in inspect(engine).get_unique_constraints("defect_events"))


# ---------------------------------------------------------------------------
# PostgreSQL: gleichzeitig
# ---------------------------------------------------------------------------

@pytest.fixture
def pg(monkeypatch, tmp_path):
    if not PG_TEST_DATABASE_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    monkeypatch.setattr(acceptances_module, "ACCEPTANCE_FILE_ROOT", tmp_path / "abnahmen")
    schema = f"pgtest_mmonteur_{uuid.uuid4().hex[:8]}"
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
            d = defects_module.create_defect(setup, a, {"description": "undicht", "remedy_due_on": None}, [],
                                             user_id=None, user_name="PG")
            defects_module.set_release(setup, d, released=True, reason=None, user_id=None, user_name="PG")
            emp = Employee(employee_number="M-PG", first_name="Mia", last_name="Monteurin", employee_group="gewerblich",
                           active=True)
            setup.add(emp)
            setup.flush()
            user = AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=emp.id,
                           active=True, password_hash="x")
            setup.add(user)
            setup.commit()
            welt.update(defect_id=d.id, user_id=user.id)
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


def _pg_melden(Session, welt, kennung, holder=None):
    db = holder or Session()
    try:
        defect = db.get(Defect, welt["defect_id"])
        return defects_module.report_remedied(
            db, defect, event_date=HEUTE, client_uuid=kennung,
            files=[("foto", "n.png", _png("green"))], user_id=welt["user_id"], user_name="Mia Monteurin").id
    finally:
        if holder is None:
            db.close()


def test_postgresql_two_reports_with_the_same_key_at_once(pg):
    """Zwei gleichzeitige Meldungen mit derselben Kennung (Stufe 3: das Gerät sendet erneut, bevor die erste Antwort
    kam): die zweite wartet auf die Sperre des Mangels und bekommt danach die gespeicherte Meldung -- ein Eintrag."""
    Session, welt = pg
    kennung = str(uuid.uuid4())
    holder, ready, first = Session(), threading.Event(), {}

    def hold(release):
        def run():
            commit = holder.commit

            def angehalten():
                holder.flush()
                ready.set()
                release.wait(timeout=30)
                commit()
            holder.commit = angehalten
            first["id"] = _pg_melden(Session, welt, kennung, holder=holder)
        threading.Thread(target=run).start()
        ready.wait(timeout=10)
    done = _waits_for(hold, lambda: _pg_melden(Session, welt, kennung))
    time.sleep(0.3)
    holder.close()
    assert done["seconds"] >= 0.9 and done["result"] == first["id"], done
    check = Session()
    try:
        events = check.scalars(select(DefectEvent).where(DefectEvent.defect_id == welt["defect_id"])).all()
        assert [e.kind for e in events] == ["freigabe", "status"]
    finally:
        check.close()


def test_postgresql_report_waits_for_withdrawing_the_release(pg):
    """Das Büro nimmt die Freigabe zurück, während der Monteur meldet: die Meldung wartet auf die Sperre des Mangels
    und wird danach abgelehnt (409), statt einen nicht mehr freigegebenen Mangel als beseitigt zu führen."""
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
            defects_module.set_release(holder, defect, released=False, reason="Kunde zieht zurück", user_id=None,
                                       user_name="Büro")
        threading.Thread(target=run).start()
        ready.wait(timeout=10)
    done = _waits_for(hold, lambda: _pg_melden(Session, welt, str(uuid.uuid4())))
    time.sleep(0.3)
    holder.close()
    assert isinstance(done["result"], defects_module.DefectConflict) and done["seconds"] >= 0.9, done
    check = Session()
    try:
        assert [e.kind for e in check.scalars(select(DefectEvent).where(DefectEvent.defect_id == welt["defect_id"]))] \
            == ["freigabe", "freigabe"]
    finally:
        check.close()
