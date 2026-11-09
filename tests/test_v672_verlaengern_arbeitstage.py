"""Version 1.9.272 (Bestätigung R5b, 1.9.268 Nr. 7 geändert): Verlängern nimmt nur Arbeitstage.

    Verlängern     ab einem ihrer Tage jeder Arbeitstag der Planung bis zum Ende des Einsatzes -- Samstag, Sonntag, gesetzlicher Feiertag und
                   betriebsfreier Tag (Planungsgrundlagen) nicht; bis 1.9.271 jeder Kalendertag
    ausdrücklich   auf einen solchen Tag kommt sie nur, wenn jemand sie ausdrücklich dorthin zieht (Tag setzen, Umsetzen, Tage im Dialog); wo sie schon
                   steht, bleibt sie
    nichts mehr    bleiben bis zum Ende nur Tage ohne Arbeit: 422 mit Meldung (ab dem letzten Tag wie bisher)
    „bis“          der letzte Arbeitstag, der dazukommt (meist das Ende des Einsatzes)
    Arbeitstag     wie „direkt anschließend“ (Antwort 7): die Wochentage der Planungsgrundlagen -- ist dort der Samstag ein Arbeitstag, zählt er
"""

import json

import pytest

from app.models import PlanningHoliday, PlanningRegionSettings, PlanningSettings
from app.tag_aktionen import KEIN_ARBEITSTAG_MEHR, NICHTS_ZU_VERLAENGERN, tag_setzen, verlaengern
from tests.test_v660_besetzung_je_tag import _geraete, _personen, _tag, welt  # noqa: F401 -- welt ist eine Fixture
from tests.test_v667_tag_setzen import _einsatz, _iso, _zeitraum

# MO = Mo 02.11.2026: _tag(3) Do, _tag(4) Fr, _tag(5) Sa, _tag(6) So, _tag(7) Mo, _tag(8) Di


def _kai(db, slot_id, welt):
    return [t for eid, t in _personen(db, slot_id) if eid == welt["kai"]][0]


def test_ueber_das_wochenende_nur_arbeitstage(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 3, 8, personen={"tom": None, "kai": [_tag(3)]})
    e = verlaengern(db, slot_id=slot.id, employee_id=welt["kai"], ab_tag=_tag(3))
    assert (e["aktion"], e["tage"], e["bis"]) == ("verlaengert", [_iso(3), _iso(4), _iso(7), _iso(8)], _iso(8))
    assert _kai(db, slot.id, welt) == [_iso(3), _iso(4), _iso(7), _iso(8)]  # ohne Sa und So
    assert _zeitraum(db, slot.id) == (_tag(3), _tag(8))  # der Einsatz bleibt, wie er ist


def test_feiertag_und_betriebsfreier_tag(welt):
    """Mo 16. bis Fr 20.11.2026 in Sachsen: Mi 18. ist Buß- und Bettag (gesetzlich), Fr 20. betriebsfrei (Planungsgrundlagen) -- beide nicht; „bis“ ist der Do."""
    db = welt["db"]
    region = db.get(PlanningRegionSettings, 1)
    region.federal_state_code, region.auto_public_holidays = "SN", True
    db.add(PlanningHoliday(holiday_date=_tag(18), name="Betriebsausflug", active=True))
    db.commit()
    slot = _einsatz(welt, "a", 14, 18, personen={"tom": None, "kai": [_tag(14)]})
    e = verlaengern(db, slot_id=slot.id, employee_id=welt["kai"], ab_tag=_tag(14))
    assert (e["tage"], e["bis"]) == ([_iso(14), _iso(15), _iso(17)], _iso(17))


def test_ausdruecklich_gezogener_samstag_bleibt(welt):
    """Im Dialog ausdrücklich Mo und Sa: Verlängern füllt Di–Fr auf, der Samstag bleibt -- danach steht sie an allen Tagen des Einsatzes (Normalform)."""
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 5, personen={"tom": None, "kai": [_tag(0), _tag(5)]})
    e = verlaengern(db, slot_id=slot.id, employee_id=welt["kai"], ab_tag=_tag(0))
    assert (e["tage"], e["bis"]) == ([_iso(n) for n in range(6)], _iso(4))
    assert _kai(db, slot.id, welt) is None


def test_tag_setzen_auf_einen_samstag_bleibt_moeglich(welt):
    """„Nur, wenn jemand ausdrücklich auf diesen Tag zieht“: Tag setzen auf den Samstag setzt sie dorthin, wie bisher."""
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, personen={"tom": None})
    e = tag_setzen(db, order_id=welt["a"].id, tag=_tag(5), employee_id=welt["kai"])
    assert (e["slot_id"], e["tage"]) == (slot.id, [_iso(5)])
    assert _kai(db, slot.id, welt) == [_iso(5)]


def test_bis_zum_ende_nur_noch_freie_tage(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 4, 6, personen={"tom": None, "kai": [_tag(4)]})  # Fr–So, Tom ausdrücklich auch am Wochenende
    with pytest.raises(ValueError, match=KEIN_ARBEITSTAG_MEHR):
        verlaengern(db, slot_id=slot.id, employee_id=welt["kai"], ab_tag=_tag(4))
    with pytest.raises(ValueError, match=NICHTS_ZU_VERLAENGERN):
        verlaengern(db, slot_id=slot.id, employee_id=welt["tom"], ab_tag=_tag(6))
    assert _kai(db, slot.id, welt) == [_iso(4)]
    r = welt["client"].post(f"/api/planning/slots/{slot.id}/verlaengern", json={"employee_id": welt["kai"], "ab_tag": _iso(4)})
    assert r.status_code == 422 and "kein Arbeitstag mehr" in r.text


def test_geraet_ebenso(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 3, 8, personen={"tom": None}, geraete=[{"resource_id": welt["pritsche"], "tage": [_tag(3)]}])
    e = verlaengern(db, slot_id=slot.id, resource_id=welt["pritsche"], ab_tag=_tag(3))
    assert e["tage"] == [_iso(3), _iso(4), _iso(7), _iso(8)]
    assert _geraete(db, slot.id) == [(welt["pritsche"], [_iso(3), _iso(4), _iso(7), _iso(8)])]


def test_samstag_als_arbeitstag_der_planung(welt):
    """Arbeitstag = Wochentag der Planungsgrundlagen (wie „direkt anschließend“): ist der Samstag dort ein Arbeitstag, nimmt Verlängern ihn mit."""
    db = welt["db"]
    db.get(PlanningSettings, 1).saturday = True
    db.commit()
    slot = _einsatz(welt, "a", 3, 8, personen={"tom": None, "kai": [_tag(3)]})
    assert verlaengern(db, slot_id=slot.id, employee_id=welt["kai"], ab_tag=_tag(3))["tage"] == [_iso(3), _iso(4), _iso(5), _iso(7), _iso(8)]


def test_pruefen_api_und_rueckgaengig(welt):
    db, client = welt["db"], welt["client"]
    slot = _einsatz(welt, "a", 3, 8, personen={"tom": None, "kai": [_tag(3)]})
    p = client.post(f"/api/planning/slots/{slot.id}/verlaengern", json={"employee_id": welt["kai"], "ab_tag": _iso(3), "pruefen": True})
    assert p.status_code == 200 and p.json()["tage"] == [_iso(3), _iso(4), _iso(7), _iso(8)] and p.json()["bis"] == _iso(8)
    assert _kai(db, slot.id, welt) == [_iso(3)]  # Prüfen schreibt nichts
    r = client.post(f"/api/planning/slots/{slot.id}/verlaengern", json={"employee_id": welt["kai"], "ab_tag": _iso(3)})
    assert r.status_code == 200 and r.json()["tage"] == [_iso(3), _iso(4), _iso(7), _iso(8)]
    u = r.json()["umkehrung"]
    assert client.post(u["pfad"], json=json.loads(json.dumps(u["body"]))).status_code == 200
    assert _kai(db, slot.id, welt) == [_iso(3)]
