"""Version 1.9.277 (Stufe 6, R5c, Punkt 0b; Antwort 4 der Nachrunde R5b): Verschieben zählt Arbeitstage.

    Regel        der erste Tag landet auf dem Zieltag (dort losgelassen -- auch ein freier Tag); jeder weitere Tag behält seinen Abstand in Arbeitstagen
                 (tag_aktionen.verschiebung()): Mo–Fr einen Tag weiter wird Di–Fr und der nächste Mo. Freie Tage nur ausdrücklich -- ein freier Tag, an dem
                 jemand stand, geht im Arbeitstag davor auf. Bis 1.9.276 um gleich viele Kalendertage.
    Umsetzen     eine Person oder ein Gerät (aus einer Zelle, in „Personen“ und „Geräte“) -- in Arbeitstagen
    ganzer       POST /api/planning/slots/{id}/verschieben (Ziehen in „Kolonnen“, bis 1.9.276 PUT mit Beginn und Ende): jede Zeile die Abbilder ihrer Tage, der
    Einsatz      Einsatz endet am Abbild seines letzten Tags; „alle Tage“ nur, wenn sie danach an allen Tagen stehen; eine andere Kolonne bringt ihre Mitglieder
                 an die Abbilder aller Tage; fragt wie bisher bei jeder Warnung des Einsatzes; Rückgängig „zurueck“ (nur unverändert, sonst 409)
    Dialog       Beginn und Ende im Dialog (PUT) bleiben Kalendertage
"""

import inspect
import json
from datetime import date, timedelta

import pytest

from app.planning import PlanungsWarnung, update_slot
from app.routers import planning as planning_router_modul
from app.routers.planning import router as planning_router
from app.tag_aktionen import RUECKGAENGIG_GEAENDERT_VERSCHOBEN, tag_setzen, umsetzen, verschieben, verschiebung
from tests.test_v660_besetzung_je_tag import _geraete, _personen, _tag, welt  # noqa: F401 -- welt ist eine Fixture
from tests.test_v667_tag_setzen import _einsatz, _iso, _zeitraum
from tests.test_v669_sperren_und_rueckgaengig import _bild, _zurueck

# MO = Mo 02.11.2026: _tag(4) Fr, 5 Sa, 6 So, 7 Mo 09.11., 8 Di


def _mo_fr(t: date) -> bool:
    return t.weekday() < 5


def _woche(*n):
    return [_iso(x) for x in n]


# --- die Regel -----------------------------------------------------------------------------------------------------------------------------

def test_verschiebung_in_arbeitstagen():
    weiter = verschiebung(_tag(0), _tag(1), _mo_fr)
    assert [weiter(_tag(n)) for n in range(5)] == [_tag(1), _tag(2), _tag(3), _tag(4), _tag(7)]  # Mo–Fr -> Di–Fr und der nächste Mo
    zurueck = verschiebung(_tag(1), _tag(0), _mo_fr)
    assert [zurueck(_tag(n)) for n in (1, 2, 3, 4, 7)] == [_tag(0), _tag(1), _tag(2), _tag(3), _tag(4)]  # und zurück
    assert verschiebung(_tag(0), _tag(0), _mo_fr)(_tag(5)) == _tag(5)  # nicht verschoben: alles bleibt, auch ein freier Tag


def test_freier_tag_nur_ausdruecklich():
    auf_samstag = verschiebung(_tag(0), _tag(5), _mo_fr)  # der erste Tag ausdrücklich auf Sa
    assert [auf_samstag(_tag(n)) for n in range(3)] == [_tag(5), _tag(7), _tag(8)]  # Sa, dann Mo, Di
    mit_samstag = verschiebung(_tag(3), _tag(4), _mo_fr)  # Do, Fr, Sa (ausdrücklich), Mo einen Tag weiter
    assert sorted({mit_samstag(_tag(n)) for n in (3, 4, 5, 7)}) == [_tag(4), _tag(7), _tag(8)]  # der Sa geht im Mo auf


# --- Umsetzen ------------------------------------------------------------------------------------------------------------------------------

def test_umsetzen_in_arbeitstagen(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, personen={"tom": None, "kai": [_tag(3), _tag(4)]})
    e = umsetzen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(3), _tag(4)], ziel_tag=_tag(4), ziel_slot_id=slot.id, genau=True)
    assert e["tage"] == _woche(4, 7)  # Do, Fr -> Fr und der nächste Mo (bis 1.9.276: Fr, Sa)
    assert _zeitraum(db, slot.id) == (_tag(0), _tag(7))
    assert _personen(db, slot.id) == [(welt["tom"], _woche(0, 1, 2, 3, 4)), (welt["kai"], _woche(4, 7))]  # Tom bleibt Mo–Fr (die Falle)


def test_umsetzen_eines_geraets(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 3, 4, personen={"tom": None}, geraete=[{"resource_id": welt["pritsche"], "tage": None}])
    umsetzen(db, slot_id=slot.id, resource_id=welt["pritsche"], tage=[_tag(3), _tag(4)], ziel_tag=_tag(4), ziel_slot_id=slot.id, genau=True)
    assert _geraete(db, slot.id) == [(welt["pritsche"], _woche(4, 7))]


# --- den ganzen Einsatz verschieben ---------------------------------------------------------------------------------------------------------

def test_ganzer_einsatz_mo_fr_einen_tag_weiter(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, team=welt["nord"].id)
    e = verschieben(db, slot_id=slot.id, auf=_tag(1))
    assert (e["aktion"], e["start_date"], e["end_date"]) == ("verschoben", _iso(1), _iso(7))
    woche = _woche(1, 2, 3, 4, 7)  # Di–Fr und der nächste Mo; das Wochenende bleibt frei („niemand“)
    assert _personen(db, slot.id) == [(welt["tom"], woche), (welt["mia"], woche)]
    assert _geraete(db, slot.id) == [(welt["pritsche"], woche)]


def test_einzelne_tage_wandern_mit(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, personen={"tom": None, "kai": [_tag(0), _tag(4)]})
    verschieben(db, slot_id=slot.id, auf=_tag(1))
    assert _personen(db, slot.id) == [(welt["tom"], _woche(1, 2, 3, 4, 7)), (welt["kai"], _woche(1, 7))]


def test_ein_wochenende_im_einsatz_wird_nicht_mitgezogen(welt):
    """Do–Di an allen Tagen (das Wochenende im Zeitraum) einen Arbeitstag weiter: Fr, Mo, Di, Mi -- niemand landet von selbst auf einem freien Tag."""
    db = welt["db"]
    slot = _einsatz(welt, "a", 3, 8, personen={"tom": None})
    verschieben(db, slot_id=slot.id, auf=_tag(4))
    assert _zeitraum(db, slot.id) == (_tag(4), _tag(9))
    assert _personen(db, slot.id) == [(welt["tom"], _woche(4, 7, 8, 9))]


def test_ausdruecklich_auf_einen_freien_tag(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 2, personen={"tom": None})
    verschieben(db, slot_id=slot.id, auf=_tag(5))
    assert _zeitraum(db, slot.id) == (_tag(5), _tag(8))
    assert _personen(db, slot.id) == [(welt["tom"], _woche(5, 7, 8))]


def test_in_eine_andere_kolonne(welt):
    db = welt["db"]
    from app.main import create_team
    from app.schemas import TeamCreate, TeamEmployeeInput
    sued = create_team(TeamCreate(team_number="S", name="Süd", employees=[TeamEmployeeInput(employee_id=welt["kai"], role="Monteur")], resources=[]), db)
    slot = _einsatz(welt, "a", 0, 4, team=welt["nord"].id)
    verschieben(db, slot_id=slot.id, auf=_tag(1), team_id=sued.id)
    assert _personen(db, slot.id) == [(welt["kai"], _woche(1, 2, 3, 4, 7))]


def test_fragt_bei_jeder_warnung_des_einsatzes(welt):
    """Wie das Ziehen bis 1.9.276: eine schon bestehende Warnung fragt auch (anders als die Tag-Aktionen, 1.9.267 Nr. 10)."""
    db = welt["db"]
    _einsatz(welt, "b", 0, 4, personen={"kai": None})
    slot = _einsatz(welt, "a", 0, 4, personen={"kai": None})  # Kai doppelt -- schon vorher
    vorher = _bild(db, slot.id)
    with pytest.raises(PlanungsWarnung):
        verschieben(db, slot_id=slot.id, auf=_tag(1))
    assert _bild(db, slot.id) == vorher
    p = verschieben(db, slot_id=slot.id, auf=_tag(1), pruefen=True)
    assert p["fragt"] and _bild(db, slot.id) == vorher  # Prüfen schreibt nichts
    assert verschieben(db, slot_id=slot.id, auf=_tag(1), trotzdem_planen=True)["aktion"] == "verschoben"


def test_rueckgaengig_stellt_den_stand_wieder_her(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, team=welt["nord"].id)
    tag_setzen(db, order_id=welt["a"].id, tag=_tag(2), employee_id=welt["kai"])  # Kai nur am Mi
    vorher = _bild(db, slot.id)
    e = verschieben(db, slot_id=slot.id, auf=_tag(3))
    assert _bild(db, slot.id) != vorher
    assert _zurueck(welt, e).status_code == 200 and _bild(db, slot.id) == vorher
    e2 = verschieben(db, slot_id=slot.id, auf=_tag(3))
    update_slot(db, slot.id, notes="danach geändert")
    r = _zurueck(welt, e2)
    assert r.status_code == 409 and RUECKGAENGIG_GEAENDERT_VERSCHOBEN in r.text


def test_dialog_bleibt_in_kalendertagen(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, personen={"tom": None})
    update_slot(db, slot.id, start_date=_tag(1), end_date=_tag(5))
    assert _zeitraum(db, slot.id) == (_tag(1), _tag(5)) and _personen(db, slot.id) == [(welt["tom"], None)]


# --- API -----------------------------------------------------------------------------------------------------------------------------------

def test_api_regeln_und_rolle(welt, router_test_client):
    db, client = welt["db"], welt["client"]
    slot = _einsatz(welt, "a", 0, 4, team=welt["nord"].id)
    p = client.post(f"/api/planning/slots/{slot.id}/verschieben", json={"auf": _iso(1), "pruefen": True})
    assert p.status_code == 200 and p.json()["end_date"] == _iso(7) and _zeitraum(db, slot.id) == (_tag(0), _tag(4))
    r = client.post(f"/api/planning/slots/{slot.id}/verschieben", json={"auf": _iso(1)})
    assert r.status_code == 200, r.text
    assert (r.json()["einsatz"]["start_date"], r.json()["einsatz"]["end_date"]) == (_iso(1), _iso(7))
    assert r.json()["umkehrung"]["body"]["schritte"][0]["art"] == "zurueck"
    assert client.post("/api/planning/slots/999999/verschieben", json={"auf": _iso(1)}).status_code == 404
    kran = _einsatz(welt, "b", 0, 0, art="kranvermietung", geraete=[{"resource_id": welt["kran"]}])
    assert client.post(f"/api/planning/slots/{kran.id}/verschieben", json={"auf": _iso(1), "team_id": welt["nord"].id}).status_code == 422
    monteurin = router_test_client(db, planning_router, role="field")
    assert monteurin.post(f"/api/planning/slots/{slot.id}/verschieben", json={"auf": _iso(2)}).status_code == 403
    funktion = planning_router_modul.post_verschieben
    assert not inspect.iscoroutinefunction(funktion) and 'scope="function"' in inspect.getsource(funktion)
