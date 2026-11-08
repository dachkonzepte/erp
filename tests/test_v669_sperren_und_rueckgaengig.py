"""Version 1.9.269 (Stufe 6, R5b, Punkt 3): Sperren, Zugehörigkeit, Rolle, Teil-Update, Event-Loop -- und Rückgängig.

    Rückgängig  jede Tag-Aktion gibt ihre Umkehrung zurück (POST /api/planning/rueckgaengig mit Schritten -- kein Speicher auf dem Server); die Seite schickt
                sie, der Stand davor ist wieder da. Ein eben angelegter Einsatz wird gelöscht, nur solange er unverändert ist (Antwort 5, sonst 409). Hat die
                Aktion einen Einsatz gelöscht (Löschen in der Rückfrage), gibt es kein Rückgängig.
    Sperren     jede Tag-Aktion sperrt die Arbeitsvorbereitungen, die sie berührt, in aufsteigender Reihenfolge -- zwei gleichzeitige Umsetzen über Kreuz
                warten aufeinander statt sich zu blockieren (PostgreSQL)
    Rolle       ab Büro – Auftrag wie die Tafel; die Monteurin 403
    Teil-Update eine Tag-Aktion ändert nur die Zeilen der Genannten -- Zeitraum nur, wo sie ihn braucht, Notiz, Status, Stunden, Kolonne und jede andere Zeile
                bleiben; PUT kennt dazu/weg nicht
    Event-Loop  jeder Endpunkt def, Sitzung vor dem Senden zu (Regel 35)
"""

import inspect
import json
import threading
import time
from datetime import date

import pytest
from sqlalchemy import event, select

from app.models import PlanningSlot, PlanningSlotCapacity
from app.routers import planning as planning_router_modul
from app.routers.planning import router as planning_router
from app.tag_aktionen import RUECKGAENGIG_GEAENDERT, herausnehmen, tag_setzen, umsetzen, verlaengern
from tests.test_v660_besetzung_je_tag import _geraete, _personen, _tag, welt  # noqa: F401 -- welt ist eine Fixture
from tests.test_v667_tag_setzen import _einsatz, _iso
from tests.test_v375_rechnungen_sperren import pg  # noqa: F401 -- pg ist eine Fixture (Wegwerf-Schema)

ENDPUNKTE = ["post_tag_setzen", "post_umsetzen", "post_herausnehmen", "post_verlaengern", "post_rueckgaengig"]


def _bild(db, *slot_ids):
    """Was an den Einsätzen steht: Zeitraum, Personen und Geräte mit Tagen, Notiz, Status, Stunden -- None, wenn es den Einsatz nicht gibt."""
    db.expire_all()
    out = {}
    for sid in slot_ids:
        s = db.get(PlanningSlot, sid)
        if s is None:
            out[sid] = None
            continue
        kap = db.scalar(select(PlanningSlotCapacity).where(PlanningSlotCapacity.slot_id == sid))
        out[sid] = (s.start_date, s.end_date, s.status, s.notes, s.team_assignment_id, _personen(db, sid), _geraete(db, sid),
                    kap.planned_hours if kap else None)
    return out


def _zurueck(welt, ergebnis):
    u = ergebnis["umkehrung"]
    assert u["pfad"] == "/api/planning/rueckgaengig"
    return welt["client"].post(u["pfad"], json=json.loads(json.dumps(u["body"])))


# --- Rückgängig -------------------------------------------------------------------------------------------------------------------------

def test_rueckgaengig_dazu_und_verlaengert(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, team=welt["nord"].id)
    vorher = _bild(db, slot.id)
    dazu = tag_setzen(db, order_id=welt["a"].id, tag=_tag(2), employee_id=welt["kai"])
    assert _zurueck(welt, dazu).status_code == 200 and _bild(db, slot.id) == vorher
    lang = tag_setzen(db, order_id=welt["a"].id, tag=_tag(7), employee_id=welt["kai"])  # Fr -> Mo: die Falle schreibt Tom, Mia, Pritsche fest
    assert lang["aktion"] == "verlaengert" and _bild(db, slot.id) != vorher
    assert _zurueck(welt, lang).status_code == 200 and _bild(db, slot.id) == vorher  # wieder Mo–Fr, alle wieder „alle Tage“
    kolonne = tag_setzen(db, order_id=welt["a"].id, tag=_tag(7), team_id=welt["nord"].id)
    assert len(kolonne["umkehrung"]["body"]["schritte"]) == 3  # Tom, Mia, Pritsche
    assert _zurueck(welt, kolonne).status_code == 200 and _bild(db, slot.id) == vorher
    nichts = tag_setzen(db, order_id=welt["a"].id, tag=_tag(2), employee_id=welt["tom"])  # schon da: nichts geändert, nichts rückgängig zu machen
    assert nichts["umkehrung"] is None


def test_rueckgaengig_neu_nur_unveraendert(welt):
    """Antwort 5: ein eben angelegter Einsatz wird gelöscht, solange er unverändert ist."""
    db = welt["db"]
    neu = tag_setzen(db, order_id=welt["b"].id, tag=_tag(2), employee_id=welt["kai"])
    assert neu["aktion"] == "neu" and neu["umkehrung"]["body"]["schritte"][0]["art"] == "loeschen"
    assert _zurueck(welt, neu).status_code == 200 and _bild(db, neu["slot_id"]) == {neu["slot_id"]: None}
    zweiter = tag_setzen(db, order_id=welt["b"].id, tag=_tag(2), employee_id=welt["kai"])
    assert welt["client"].put(f"/api/planning/slots/{zweiter['slot_id']}", json={"notes": "Gerüst"}).status_code == 200
    r = _zurueck(welt, zweiter)
    assert r.status_code == 409 and r.json()["detail"] == RUECKGAENGIG_GEAENDERT
    assert _bild(db, zweiter["slot_id"])[zweiter["slot_id"]] is not None  # nichts geändert


def test_rueckgaengig_umsetzen(welt):
    db = welt["db"]
    quelle = _einsatz(welt, "a", 0, 4, personen={"tom": None, "kai": None})
    ziel = _einsatz(welt, "b", 0, 4, personen={"mia": None})
    vorher = _bild(db, quelle.id, ziel.id)
    in_ziel = umsetzen(db, slot_id=quelle.id, employee_id=welt["kai"], tage=[_tag(2)], ziel_tag=_tag(2), ziel_order_id=welt["b"].id)
    assert in_ziel["slot_id"] == ziel.id
    assert _zurueck(welt, in_ziel).status_code == 200 and _bild(db, quelle.id, ziel.id) == vorher
    weiter = umsetzen(db, slot_id=quelle.id, employee_id=welt["kai"], tage=[_tag(3), _tag(4)], ziel_tag=_tag(4))  # im selben Einsatz, überlappend
    assert _zurueck(welt, weiter).status_code == 200 and _bild(db, quelle.id, ziel.id) == vorher
    neu = umsetzen(db, slot_id=quelle.id, employee_id=welt["kai"], tage=[_tag(1)], ziel_tag=_tag(9), ziel_order_id=welt["b"].id)
    assert neu["ziel_aktion"] == "neu"
    assert _zurueck(welt, neu).status_code == 200 and _bild(db, quelle.id, ziel.id) == vorher and _bild(db, neu["slot_id"]) == {neu["slot_id"]: None}


def test_rueckgaengig_herausnehmen_und_verlaengern(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, personen={"tom": None, "mia": [_tag(0), _tag(1)]})
    vorher = _bild(db, slot.id)
    for tage in ([_tag(2)], [_tag(4)], [_tag(0), _tag(4)]):  # Mitte (Lücke), Rand (gekürzt), beides
        e = herausnehmen(db, slot_id=slot.id, employee_id=welt["tom"], tage=tage)
        assert _zurueck(welt, e).status_code == 200 and _bild(db, slot.id) == vorher, tage
    lang = verlaengern(db, slot_id=slot.id, employee_id=welt["mia"], ab_tag=_tag(1))
    assert _zurueck(welt, lang).status_code == 200 and _bild(db, slot.id) == vorher
    leer = _einsatz(welt, "b", 1, 2, personen={"kai": None})
    leer_vorher = _bild(db, leer.id)
    behalten = herausnehmen(db, slot_id=leer.id, employee_id=welt["kai"], alle=True, wenn_leer="behalten")  # danach „niemand“
    assert _zurueck(welt, behalten).status_code == 200 and _bild(db, leer.id) == leer_vorher
    weg = herausnehmen(db, slot_id=leer.id, employee_id=welt["kai"], alle=True, wenn_leer="loeschen")
    assert weg["umkehrung"] is None  # der Einsatz ist gelöscht: kein Rückgängig


def test_rueckgaengig_nach_umsetzen_mit_geloeschter_quelle(welt):
    db = welt["db"]
    allein = _einsatz(welt, "a", 2, 2, personen={"kai": None})
    _einsatz(welt, "b", 2, 2, personen={"mia": None})  # das Ziel gibt es schon: Kai kommt dazu
    e = umsetzen(db, slot_id=allein.id, employee_id=welt["kai"], tage=[_tag(2)], ziel_tag=_tag(2), ziel_order_id=welt["b"].id, wenn_leer="loeschen")
    assert e["quelle_geloescht"] and e["umkehrung"] is None


def test_rueckgaengig_in_einer_transaktion_und_fragt_nie(welt):
    db, client = welt["db"], welt["client"]
    slot = _einsatz(welt, "a", 0, 2, personen={"tom": None, "kai": None})
    _einsatz(welt, "b", 0, 2, personen={"kai": None})  # Kai Mo–Mi doppelt -- schon vorher
    vorher = _bild(db, slot.id)
    halb = client.post("/api/planning/rueckgaengig", json={"schritte": [{"art": "weg", "slot_id": slot.id, "employee_id": welt["tom"], "tage": [_iso(0)]},
                                                                        {"art": "weg", "slot_id": slot.id, "employee_id": welt["mia"], "tage": [_iso(0)]}]})
    assert halb.status_code == 422 and _bild(db, slot.id) == vorher  # der zweite Schritt geht nicht: auch der erste bleibt nicht
    e = herausnehmen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(0)])
    assert _zurueck(welt, e).status_code == 200 and _bild(db, slot.id) == vorher  # stellt „doppelt Mo“ wieder her, ohne zu fragen


def test_rueckgaengig_schritte_pruefen(welt):
    client = welt["client"]
    slot = _einsatz(welt, "a", 0, 1, personen={"tom": None})
    for body, code in ((
        {"schritte": []}, 422), ({"schritte": [{"art": "weg", "slot_id": 999999, "employee_id": welt["tom"], "tage": [_iso(0)]}]}, 404),
            ({"schritte": [{"art": "weg", "slot_id": slot.id, "tage": [_iso(0)]}]}, 422),
            ({"schritte": [{"art": "kaputt", "slot_id": slot.id}]}, 422), ({"schritte": [{"art": "weg", "slot_id": slot.id, "employee_id": welt["kai"],
                                                                                     "tage": [_iso(0)]}]}, 422)):
        assert client.post("/api/planning/rueckgaengig", json=body).status_code == code, body


# --- Rolle, Event-Loop, Teil-Update -----------------------------------------------------------------------------------------------------

def test_rolle_ab_buero_auftrag(welt, router_test_client):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 1, personen={"tom": None})
    aufrufe = [("/api/planning/tag-setzen", {"order_id": welt["a"].id, "tag": _iso(1), "employee_id": welt["kai"], "pruefen": True}),
               (f"/api/planning/slots/{slot.id}/umsetzen", {"employee_id": welt["tom"], "tage": [_iso(0)], "ziel_tag": _iso(1), "pruefen": True}),
               (f"/api/planning/slots/{slot.id}/herausnehmen", {"employee_id": welt["tom"], "tage": [_iso(0)], "pruefen": True}),
               (f"/api/planning/slots/{slot.id}/verlaengern", {"employee_id": welt["tom"], "ab_tag": _iso(0), "pruefen": True}),
               ("/api/planning/rueckgaengig", {"schritte": [{"art": "weg", "slot_id": slot.id, "employee_id": welt["kai"], "tage": [_iso(0)]}]})]
    monteurin = router_test_client(db, planning_router, role="field")
    buero = router_test_client(db, planning_router, role="buero_auftrag")
    for url, body in aufrufe:
        assert monteurin.post(url, json=body).status_code == 403, url
        assert buero.post(url, json=body).status_code != 403, url


def test_endpunkte_ohne_event_loop():
    """Regel 35: kein Endpunkt einer Tag-Aktion ist async, jeder bindet die Sitzung mit scope="function" ein (der Wächter test_v419 prüft alle Routen;
    hier namentlich die neuen)."""
    for name in ENDPUNKTE:
        fn = getattr(planning_router_modul, name)
        assert not inspect.iscoroutinefunction(fn), name
        db = inspect.signature(fn).parameters["db"].default
        assert getattr(db, "scope", None) == "function", name


def test_teil_update_nur_die_genannten(welt):
    db, client = welt["db"], welt["client"]
    slot = _einsatz(welt, "a", 0, 4, team=welt["nord"].id, notes="Gerüst steht", status="fest")
    vorher = _bild(db, slot.id)[slot.id]
    tag_setzen(db, order_id=welt["a"].id, tag=_tag(2), employee_id=welt["kai"])
    herausnehmen(db, slot_id=slot.id, resource_id=welt["pritsche"], tage=[_tag(3)])
    danach = _bild(db, slot.id)[slot.id]
    assert danach[:5] == vorher[:5] and danach[7] == vorher[7]  # Zeitraum, Status, Notiz, Kolonne, Stunden
    assert danach[5] == [(welt["tom"], None), (welt["mia"], None), (welt["kai"], [_iso(2)])]
    assert danach[6] == [(welt["pritsche"], [_iso(0), _iso(1), _iso(2), _iso(4)])]
    r = client.put(f"/api/planning/slots/{slot.id}", json={"dazu": [{"employee_id": welt["alt"], "tage": [_iso(0)]}],
                                                           "weg": [{"employee_id": welt["tom"], "tage": None}]})
    assert r.status_code == 200 and _bild(db, slot.id)[slot.id] == danach  # PUT kennt dazu/weg nicht


# --- Sperren ----------------------------------------------------------------------------------------------------------------------------

def test_sperren_aufsteigend(welt):
    """Umsetzen von einem Auftrag mit der jüngeren Arbeitsvorbereitung auf einen mit der älteren: gesperrt wird zuerst die ältere (kleinere ID)."""
    db = welt["db"]
    alt = _einsatz(welt, "b", 0, 0, personen={"mia": None})  # AV von b zuerst angelegt: kleinere ID
    jung = _einsatz(welt, "a", 0, 0, personen={"kai": None, "tom": None})
    av = {o: db.scalar(select(PlanningSlot.preparation_id).where(PlanningSlot.id == s.id)) for o, s in (("b", alt), ("a", jung))}
    assert av["b"] < av["a"]
    gesperrt = []

    @event.listens_for(db.get_bind(), "before_cursor_execute")
    def _mitschreiben(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT work_preparations.id") and "work_preparations.id = " in statement:
            gesperrt.append(parameters[0] if isinstance(parameters, (list, tuple)) else next(iter(parameters.values())))
    try:
        umsetzen(db, slot_id=jung.id, employee_id=welt["kai"], tage=[_tag(0)], ziel_tag=_tag(0), ziel_order_id=welt["b"].id, trotzdem_planen=True)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", _mitschreiben)
    assert gesperrt[:2] == [av["b"], av["a"]]


@pytest.fixture
def pg_zwei(pg):
    """Zwei Aufträge mit je einem Einsatz auf PostgreSQL (Wegwerf-Schema, Regel 27): Tom am Einsatz von Auftrag 1, Kai an dem von Auftrag 2."""
    from app.models import Employee
    from app.planning import create_slot
    from tests.test_v325_contract_basis import beauftragen, make_quote
    from tests.test_v375_rechnungen_sperren import _vorbereiten
    Session, order1 = pg

    def aufbauen(s):
        from decimal import Decimal
        order2 = beauftragen(s, make_quote(s, is_consumer=False, number="0002")).id
        tom = Employee(first_name="Tom", last_name="Test", employee_group="gewerblich", hourly_wage=Decimal("20"), weekly_hours=Decimal("40"))
        kai = Employee(first_name="Kai", last_name="Test", employee_group="gewerblich", hourly_wage=Decimal("20"), weekly_hours=Decimal("40"))
        s.add_all([tom, kai])
        s.commit()
        tag = date(2026, 11, 4)
        a = create_slot(s, order_id=order1, team_id=None, start_date=tag, end_date=tag, besetzung=[{"employee_id": tom.id, "tage": None}],
                        planned_hours=Decimal("1"), trotzdem_planen=True)
        b = create_slot(s, order_id=order2, team_id=None, start_date=tag, end_date=tag, besetzung=[{"employee_id": kai.id, "tage": None}],
                        planned_hours=Decimal("1"), trotzdem_planen=True)
        return {"order1": order1, "order2": order2, "tom": tom.id, "kai": kai.id, "a": a.id, "b": b.id, "tag": tag}
    return Session, _vorbereiten(Session, aufbauen)


def test_postgresql_umsetzen_ueber_kreuz_ohne_deadlock(pg_zwei):
    """Tom von Auftrag 1 nach 2, gleichzeitig Kai von 2 nach 1. Die erste Aktion hält nach ihrer ersten Sperre an, die zweite startet; danach länger als
    deadlock_timeout (1 s) warten. In fester Reihenfolge wartet die zweite schon auf die erste Sperre -- beide gelingen nacheinander. In der Reihenfolge
    der Anfrage (Quelle zuerst) hielte jede eine und wartete auf die andere: PostgreSQL bräche eine mit einem Deadlock ab."""
    Session, w = pg_zwei
    halt, weiter = threading.Event(), threading.Event()
    zaehler = {"erste": 0}

    def _lauschen(conn, cursor, statement, parameters, context, executemany):
        if threading.current_thread().name == "erste" and "FROM work_preparations" in statement and "FOR UPDATE" in statement:
            zaehler["erste"] += 1
            if zaehler["erste"] == 1:
                halt.set()
                weiter.wait(timeout=30)
    engine = Session.kw["bind"]
    event.listen(engine, "after_cursor_execute", _lauschen)
    ergebnis = {}

    def laufen(name, aktion):
        s = Session()
        try:
            ergebnis[name] = aktion(s)
        except Exception as exc:  # noqa: BLE001
            ergebnis[name] = exc
        finally:
            s.close()
    erste = threading.Thread(name="erste", target=laufen, args=("erste", lambda s: umsetzen(
        s, slot_id=w["a"], employee_id=w["tom"], tage=[w["tag"]], ziel_tag=w["tag"], ziel_order_id=w["order2"], trotzdem_planen=True, wenn_leer="behalten")))
    zweite = threading.Thread(name="zweite", target=laufen, args=("zweite", lambda s: umsetzen(
        s, slot_id=w["b"], employee_id=w["kai"], tage=[w["tag"]], ziel_tag=w["tag"], ziel_order_id=w["order1"], trotzdem_planen=True, wenn_leer="behalten")))
    try:
        erste.start()
        assert halt.wait(timeout=10)
        zweite.start()
        time.sleep(1.5)
        weiter.set()
        erste.join(timeout=30)
        zweite.join(timeout=30)
    finally:
        weiter.set()
        event.remove(engine, "after_cursor_execute", _lauschen)
    assert not isinstance(ergebnis.get("erste"), Exception) and not isinstance(ergebnis.get("zweite"), Exception), ergebnis
    assert ergebnis["erste"]["aktion"] == ergebnis["zweite"]["aktion"] == "umgesetzt"
