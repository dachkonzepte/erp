"""Version 1.9.268 (Stufe 6, R5b, Punkt 2): Umsetzen, Herausnehmen, Verlängern -- für eine Person oder ein Gerät.

    Umsetzen      aus einer Zelle auf einen anderen Auftrag oder Tag: setzen nach den Regeln von Tag setzen (Antwort 6 mit Karte), dann am alten Platz
                  herausnehmen -- in einer Transaktion; die Tage wandern um gleich viele Kalendertage; im selben Einsatz bleiben die Tage, die sie behält;
                  der alte Platz fragt nicht (Zeichnung: „aus seiner Zelle … ohne Rückfrage“), eine neue Warnung am Ziel schon; wird der Einsatz, aus
                  dem sie kommt, leer: Rückfrage (Antwort 3)
    Herausnehmen  Tage oder alle; am Rand kürzt der Einsatz, in der Mitte bleibt eine Lücke; ganz leer: Rückfrage, wenn_leer; fragt sonst nie
    Verlängern    ab einem ihrer Tage bis zum letzten Tag des Einsatzes; prüft wie Planen
    API           POST /api/planning/slots/{id}/umsetzen | herausnehmen | verlaengern: 200, 409, 404, 422; pruefen schreibt nichts
"""

import pytest
from sqlalchemy import func, select

from app.models import EmployeeAbsence, PlanningSlot, PlanningSlotEmployee
from app.planning import EINSATZ_LEER, EinsatzWirdLeer, PlanungsWarnung, leere_tage
from app.tag_aktionen import NICHTS_ZU_VERLAENGERN, TAGE_ODER_ALLE, herausnehmen, umsetzen, verlaengern
from tests.test_v660_besetzung_je_tag import _geraete, _personen, _tag, welt  # noqa: F401 -- welt ist eine Fixture
from tests.test_v667_tag_setzen import _einsatz, _iso, _zeitraum


def _zahl(db, modell):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(modell))


def _da(db, slot_id):
    db.expire_all()
    return db.get(PlanningSlot, slot_id) is not None


# --- Umsetzen ---------------------------------------------------------------------------------------------------------------------------

def test_umsetzen_auf_einen_anderen_auftrag_fragt_nicht_nach_dem_alten_platz(welt):
    """Zeichnung: Ole ist am Mi beim Sturmschaden -- aus seiner Zelle wird er für den Tag umgesetzt, ohne Rückfrage (aus der Liste fragte „doppelt“)."""
    db = welt["db"]
    quelle = _einsatz(welt, "a", 0, 4, personen={"tom": None, "kai": None})
    with pytest.raises(PlanungsWarnung):  # zum Vergleich: aus der Liste wäre Kai am Mi doppelt
        from app.tag_aktionen import tag_setzen
        tag_setzen(db, order_id=welt["b"].id, tag=_tag(2), employee_id=welt["kai"])
    e = umsetzen(db, slot_id=quelle.id, employee_id=welt["kai"], tage=[_tag(2)], ziel_tag=_tag(2), ziel_order_id=welt["b"].id)
    assert (e["aktion"], e["ziel_aktion"], e["quelle_id"], e["quelle_geloescht"], e["tage"]) == ("umgesetzt", "neu", quelle.id, False, [_iso(2)])
    assert _personen(db, quelle.id) == [(welt["tom"], None), (welt["kai"], [_iso(0), _iso(1), _iso(3), _iso(4)])]
    assert _personen(db, e["slot_id"]) == [(welt["kai"], None)] and _zeitraum(db, e["slot_id"]) == (_tag(2), _tag(2))


def test_umsetzen_auf_einen_anderen_tag_im_selben_einsatz(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, team=welt["nord"].id)
    from app.tag_aktionen import tag_setzen
    tag_setzen(db, order_id=welt["a"].id, tag=_tag(3), employee_id=welt["kai"])
    e = umsetzen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(3)], ziel_tag=_tag(4))
    assert (e["slot_id"], e["quelle_id"], e["tage"]) == (slot.id, slot.id, [_iso(4)])
    assert _personen(db, slot.id)[-1] == (welt["kai"], [_iso(4)]) and _zeitraum(db, slot.id) == (_tag(0), _tag(4))


def test_umsetzen_mehrerer_tage_ueberlappend_mit_der_falle(welt):
    """Do–Fr um einen Tag weiter: Fr–Sa -- der Freitag bleibt (nicht erst gesetzt, dann wieder genommen); Tom und Mia stehen nur bis Fr (die Falle)."""
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, team=welt["nord"].id)
    from app.tag_aktionen import tag_setzen
    tag_setzen(db, order_id=welt["a"].id, tag=_tag(3), employee_id=welt["kai"])
    tag_setzen(db, order_id=welt["a"].id, tag=_tag(4), employee_id=welt["kai"])
    e = umsetzen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(3), _tag(4)], ziel_tag=_tag(4))
    assert e["tage"] == [_iso(4), _iso(5)] and _zeitraum(db, slot.id) == (_tag(0), _tag(5))
    woche = [_iso(n) for n in range(5)]
    assert _personen(db, slot.id) == [(welt["tom"], woche), (welt["mia"], woche), (welt["kai"], [_iso(4), _iso(5)])]


def test_allein_im_einsatz_wandert_der_einsatz(welt):
    """Steht sie allein am Einsatz und geht einen Tag weiter, schließt der Tag an: der Einsatz wird verlängert und kürzt am Rand -- er wandert mit."""
    db = welt["db"]
    slot = _einsatz(welt, "a", 3, 3, personen={"kai": None})
    e = umsetzen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(3)], ziel_tag=_tag(4))
    assert (e["slot_id"], e["quelle_geloescht"]) == (slot.id, False)
    assert _zeitraum(db, slot.id) == (_tag(4), _tag(4)) and _personen(db, slot.id) == [(welt["kai"], None)]


def test_quelle_wird_leer_fragt(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 3, 3, personen={"kai": None})
    vorher = _zahl(db, PlanningSlot)
    with pytest.raises(EinsatzWirdLeer, match=EINSATZ_LEER):
        umsetzen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(3)], ziel_tag=_tag(3), ziel_order_id=welt["b"].id)
    assert _zahl(db, PlanningSlot) == vorher and _personen(db, slot.id) == [(welt["kai"], None)]  # nichts gespeichert
    p = umsetzen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(3)], ziel_tag=_tag(3), ziel_order_id=welt["b"].id, pruefen=True)
    assert p["leer"] and _zahl(db, PlanningSlot) == vorher
    behalten = umsetzen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(3)], ziel_tag=_tag(3), ziel_order_id=welt["b"].id, wenn_leer="behalten")
    assert not behalten["quelle_geloescht"] and _personen(db, slot.id) == []
    zweite = _einsatz(welt, "a", 1, 1, personen={"mia": None})
    weg = umsetzen(db, slot_id=zweite.id, employee_id=welt["mia"], tage=[_tag(1)], ziel_tag=_tag(1), ziel_order_id=welt["b"].id, wenn_leer="loeschen",
                   trotzdem_planen=True)
    assert weg["quelle_geloescht"] and not _da(db, zweite.id)


def test_umsetzen_auf_eine_karte(welt):
    db = welt["db"]
    quelle = _einsatz(welt, "a", 2, 2, personen={"kai": None, "tom": None})
    nord = _einsatz(welt, "b", 0, 4, team=welt["nord"].id)
    ohne = _einsatz(welt, "b", 2, 2, personen={"mia": None})
    frei = umsetzen(db, slot_id=quelle.id, employee_id=welt["kai"], tage=[_tag(2)], ziel_tag=_tag(2), ziel_order_id=welt["b"].id, pruefen=True)
    assert frei["slot_id"] == ohne.id  # frei: der ohne Kolonne (Antwort 6)
    karte = umsetzen(db, slot_id=quelle.id, employee_id=welt["kai"], tage=[_tag(2)], ziel_tag=_tag(2), ziel_order_id=welt["b"].id, ziel_slot_id=nord.id)
    assert karte["slot_id"] == nord.id and (welt["kai"], [_iso(2)]) in _personen(db, nord.id)


def test_neue_warnung_am_ziel_fragt(welt):
    db = welt["db"]
    quelle = _einsatz(welt, "a", 2, 2, personen={"kai": None, "tom": None})
    db.add(EmployeeAbsence(employee_id=welt["kai"], absence_type="Urlaub", absence_category="urlaub", start_date=_tag(3), end_date=_tag(3)))
    db.commit()
    with pytest.raises(PlanungsWarnung) as fehler:
        umsetzen(db, slot_id=quelle.id, employee_id=welt["kai"], tage=[_tag(2)], ziel_tag=_tag(3))
    assert [w["type"] for w in fehler.value.warnungen] == ["absence"]
    del fehler
    assert _personen(db, quelle.id) == [(welt["kai"], None), (welt["tom"], None)] and _zeitraum(db, quelle.id) == (_tag(2), _tag(2))
    umsetzen(db, slot_id=quelle.id, employee_id=welt["kai"], tage=[_tag(2)], ziel_tag=_tag(3), trotzdem_planen=True)
    assert _personen(db, quelle.id)[0] == (welt["kai"], [_iso(3)])


def test_weniger_tage_einer_warnung_sind_nicht_neu(welt):
    """Kai ist Mo–Mi an beiden Aufträgen doppelt. Geht er bei a vom Mo auf den Do, bleibt „doppelt“ nur noch Di–Mi -- weniger Tage, keine neue Warnung,
    keine Rückfrage (bis 1.9.267 waren die Tage Teil des Vergleichs: die kürzere Warnung galt als neu)."""
    db = welt["db"]
    a = _einsatz(welt, "a", 0, 2, personen={"kai": None, "tom": None})
    _einsatz(welt, "b", 0, 2, personen={"kai": None})
    e = umsetzen(db, slot_id=a.id, employee_id=welt["kai"], tage=[_tag(0)], ziel_tag=_tag(3))
    assert e["slot_id"] == a.id and _personen(db, a.id)[0] == (welt["kai"], [_iso(1), _iso(2), _iso(3)])
    p = herausnehmen(db, slot_id=a.id, employee_id=welt["kai"], tage=[_tag(1)], pruefen=True)
    assert not p["fragt"]


def test_geraet_umsetzen(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 2, team=welt["nord"].id)
    e = umsetzen(db, slot_id=slot.id, resource_id=welt["pritsche"], tage=[_tag(2)], ziel_tag=_tag(2), ziel_order_id=welt["b"].id)
    assert _geraete(db, slot.id) == [(welt["pritsche"], [_iso(0), _iso(1)])] and _geraete(db, e["slot_id"]) == [(welt["pritsche"], None)]


# --- Herausnehmen -----------------------------------------------------------------------------------------------------------------------

def test_herausnehmen_in_der_mitte_luecke_am_rand_kuerzen(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, personen={"tom": None})
    herausnehmen(db, slot_id=slot.id, employee_id=welt["tom"], tage=[_tag(2)])
    assert _personen(db, slot.id) == [(welt["tom"], [_iso(0), _iso(1), _iso(3), _iso(4)])] and _zeitraum(db, slot.id) == (_tag(0), _tag(4))
    s = db.get(PlanningSlot, slot.id)
    assert leere_tage(s, lambda t: t.weekday() < 5) == [_tag(2)]
    e = herausnehmen(db, slot_id=slot.id, employee_id=welt["tom"], tage=[_tag(4)])
    assert _zeitraum(db, slot.id) == (_tag(0), _tag(3)) and e["bis"] == _iso(3)


def test_herausnehmen_alle_und_leer(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 2, personen={"tom": None, "mia": None})
    herausnehmen(db, slot_id=slot.id, employee_id=welt["mia"], alle=True)
    assert _personen(db, slot.id) == [(welt["tom"], None)]
    with pytest.raises(EinsatzWirdLeer):
        herausnehmen(db, slot_id=slot.id, employee_id=welt["tom"], alle=True)
    p = herausnehmen(db, slot_id=slot.id, employee_id=welt["tom"], alle=True, pruefen=True)
    assert p["leer"] and _personen(db, slot.id) == [(welt["tom"], None)]
    b = herausnehmen(db, slot_id=slot.id, employee_id=welt["tom"], alle=True, wenn_leer="behalten")
    assert (b["geloescht"], b["slot_id"]) == (False, slot.id) and _personen(db, slot.id) == [] and _zeitraum(db, slot.id) == (_tag(0), _tag(0))
    zweite = _einsatz(welt, "b", 0, 0, personen={"kai": None})
    w = herausnehmen(db, slot_id=zweite.id, employee_id=welt["kai"], tage=[_tag(0)], wenn_leer="loeschen")
    assert (w["geloescht"], w["slot_id"]) == (True, None) and not _da(db, zweite.id)


def test_herausnehmen_fragt_nie(welt):
    """Kai ist Mo–Di abwesend (die Warnung nennt den Mo). Ohne Mo nennt sie den Di -- ein anderer Tag, aber Herausnehmen fragt nie."""
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 2, personen={"kai": None, "tom": None})
    db.add(EmployeeAbsence(employee_id=welt["kai"], absence_type="Urlaub", absence_category="urlaub", start_date=_tag(0), end_date=_tag(1)))
    db.commit()
    e = herausnehmen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(0)])
    assert e["tage"] == [_iso(1), _iso(2)]


def test_herausnehmen_geraet_und_fehler(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 2, team=welt["nord"].id)
    herausnehmen(db, slot_id=slot.id, resource_id=welt["pritsche"], tage=[_tag(0)])
    assert _geraete(db, slot.id) == [(welt["pritsche"], [_iso(1), _iso(2)])] and _zeitraum(db, slot.id) == (_tag(0), _tag(2))  # Tom und Mia stehen am Mo
    for falsch in ({"tage": [_tag(1)], "alle": True}, {}):
        with pytest.raises(ValueError, match=TAGE_ODER_ALLE):
            herausnehmen(db, slot_id=slot.id, employee_id=welt["tom"], **falsch)
    with pytest.raises(ValueError, match="steht an diesen Tagen nicht"):
        herausnehmen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(1)])
    nur_mo = _einsatz(welt, "b", 0, 1, personen={"kai": [_tag(0)], "mia": None})
    with pytest.raises(ValueError, match="steht an diesen Tagen nicht"):  # am Einsatz, aber nicht an diesem Tag
        herausnehmen(db, slot_id=nur_mo.id, employee_id=welt["kai"], tage=[_tag(1)])


# --- Verlängern -------------------------------------------------------------------------------------------------------------------------

def test_verlaengern_bis_zum_letzten_tag(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 2, personen={"tom": None, "kai": [_tag(0)]})
    e = verlaengern(db, slot_id=slot.id, employee_id=welt["kai"], ab_tag=_tag(0))
    assert (e["aktion"], e["tage"], e["bis"]) == ("verlaengert", [_iso(0), _iso(1), _iso(2)], _iso(2))
    assert _personen(db, slot.id) == [(welt["tom"], None), (welt["kai"], None)]  # danach an allen Tagen: Normalform
    with pytest.raises(ValueError, match=NICHTS_ZU_VERLAENGERN):
        verlaengern(db, slot_id=slot.id, employee_id=welt["kai"], ab_tag=_tag(2))


def test_verlaengern_prueft_wie_planen(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 2, personen={"tom": None, "kai": [_tag(0)]})
    _einsatz(welt, "b", 2, 2, personen={"kai": None})
    p = verlaengern(db, slot_id=slot.id, employee_id=welt["kai"], ab_tag=_tag(0), pruefen=True)
    assert p["fragt"] and [w["type"] for w in p["warnungen"]] == ["employee"]
    with pytest.raises(PlanungsWarnung):
        verlaengern(db, slot_id=slot.id, employee_id=welt["kai"], ab_tag=_tag(0))
    assert _personen(db, slot.id)[-1] == (welt["kai"], [_iso(0)])
    verlaengern(db, slot_id=slot.id, employee_id=welt["kai"], ab_tag=_tag(0), trotzdem_planen=True)
    assert _personen(db, slot.id)[-1] == (welt["kai"], None)
    with pytest.raises(ValueError, match="steht an diesen Tagen nicht"):
        verlaengern(db, slot_id=slot.id, employee_id=welt["mia"], ab_tag=_tag(0))


# --- API --------------------------------------------------------------------------------------------------------------------------------

def test_api(welt):
    db, client = welt["db"], welt["client"]
    quelle = _einsatz(welt, "a", 0, 2, personen={"tom": None, "kai": None})
    fremd = _einsatz(welt, "a", 0, 0, personen={"mia": None})
    r = client.post(f"/api/planning/slots/{quelle.id}/umsetzen", json={"employee_id": welt["kai"], "tage": [_iso(2)], "ziel_tag": _iso(2),
                                                                         "ziel_order_id": welt["b"].id})
    assert r.status_code == 200, r.text
    assert r.json()["einsatz"]["employees"][0]["id"] == welt["kai"] and r.json()["quelle"]["id"] == quelle.id
    assert {e["id"]: e["tage"] for e in r.json()["quelle"]["employees"]} == {welt["tom"]: None, welt["kai"]: [_iso(0), _iso(1)]}
    assert client.post("/api/planning/slots/999999/umsetzen", json={"employee_id": welt["kai"], "tage": [_iso(0)], "ziel_tag": _iso(0)}).status_code == 404
    karte_fremd = client.post(f"/api/planning/slots/{quelle.id}/umsetzen", json={"employee_id": welt["kai"], "tage": [_iso(0)], "ziel_tag": _iso(0),
                                                                                  "ziel_order_id": welt["b"].id, "ziel_slot_id": fremd.id})
    assert karte_fremd.status_code == 404
    assert client.post(f"/api/planning/slots/{quelle.id}/umsetzen", json={"employee_id": welt["kai"], "tage": [], "ziel_tag": _iso(0)}).status_code == 422
    assert client.post(f"/api/planning/slots/{quelle.id}/umsetzen", json={"employee_id": welt["mia"], "tage": [_iso(0)], "ziel_tag": _iso(1)}).status_code == 422
    assert client.post(f"/api/planning/slots/{quelle.id}/umsetzen", json={"team_id": welt["nord"].id, "tage": [_iso(0)], "ziel_tag": _iso(1)}).status_code == 422
    leer = client.post(f"/api/planning/slots/{fremd.id}/herausnehmen", json={"employee_id": welt["mia"], "alle": True})
    assert leer.status_code == 409 and leer.json()["rueckfrage"]["art"] == "einsatz_leer"
    raus = client.post(f"/api/planning/slots/{fremd.id}/herausnehmen", json={"employee_id": welt["mia"], "alle": True, "wenn_leer": "loeschen"})
    assert raus.status_code == 200 and raus.json()["geloescht"] and raus.json()["einsatz"] is None
    doppelt = client.post(f"/api/planning/slots/{quelle.id}/verlaengern", json={"employee_id": welt["kai"], "ab_tag": _iso(0)})
    assert doppelt.status_code == 409 and [w["type"] for w in doppelt.json()["warnungen"]] == ["employee"]  # Kai steht am Mi jetzt bei Auftrag b
    lang = client.post(f"/api/planning/slots/{quelle.id}/verlaengern", json={"employee_id": welt["kai"], "ab_tag": _iso(0), "trotzdem_planen": True})
    assert lang.status_code == 200 and lang.json()["tage"] == [_iso(0), _iso(1), _iso(2)]
    welt["b"].status = "abgeschlossen"
    db.commit()
    zu = client.post(f"/api/planning/slots/{quelle.id}/umsetzen", json={"employee_id": welt["tom"], "tage": [_iso(0)], "ziel_tag": _iso(0),
                                                                          "ziel_order_id": welt["b"].id})
    assert zu.status_code == 409


def test_pruefen_schreibt_nichts(welt):
    db = welt["db"]
    quelle = _einsatz(welt, "a", 0, 2, personen={"tom": None, "kai": [_tag(0)]})
    vorher = (_zahl(db, PlanningSlot), _zahl(db, PlanningSlotEmployee), _personen(db, quelle.id), _zeitraum(db, quelle.id))
    umsetzen(db, slot_id=quelle.id, employee_id=welt["kai"], tage=[_tag(0)], ziel_tag=_tag(2), ziel_order_id=welt["b"].id, pruefen=True)
    herausnehmen(db, slot_id=quelle.id, employee_id=welt["tom"], tage=[_tag(0)], pruefen=True)
    verlaengern(db, slot_id=quelle.id, employee_id=welt["kai"], ab_tag=_tag(0), pruefen=True)
    assert (_zahl(db, PlanningSlot), _zahl(db, PlanningSlotEmployee), _personen(db, quelle.id), _zeitraum(db, quelle.id)) == vorher
