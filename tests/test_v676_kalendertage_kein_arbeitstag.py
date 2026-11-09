"""Version 1.9.276 (Stufe 6, R5c, Punkt 0a; Antwort 1 der Nachrunde R5b): Heiligabend und Silvester sind auf der Plantafel keine Arbeitstage.

    Kalendertag    ein aktiver Tag des Arbeitszeitkalenders (Vorgabe: Heiligabend 24.12., Silvester 31.12.) zählt wie ein betriebsfreier Tag nicht als
                   Arbeitstag der Planung -- für alle Personen und Geräte, Gruppe und Sollzeit spielen dafür keine Rolle (bis 1.9.275 ein Arbeitstag)
    überall        wo die Planung Arbeitstage zählt (_arbeitstag()): Verlängern, „direkt anschließend“ bei Tag setzen, ab 1.9.277 Verschieben
    abgeschaltet   ein inaktiver Kalendertag ist wieder ein Arbeitstag
"""

import pytest

from app.models import ArbeitszeitKalendertag, PlanningRegionSettings
from app.tag_aktionen import tag_setzen, verlaengern
from tests.test_v660_besetzung_je_tag import _geraete, _personen, _tag, welt  # noqa: F401 -- welt ist eine Fixture
from tests.test_v667_tag_setzen import _einsatz, _iso, _zeitraum

# MO = Mo 02.11.2026: _tag(49) Mo 21.12., 52 Do 24.12. (Heiligabend), 53 Fr 25.12., 54 Sa, 55 So, 56 Mo 28.12., 59 Do 31.12. (Silvester)
MO21, HA, MO28, SILV = 49, 52, 56, 59


@pytest.fixture()
def nrw(welt):
    region = welt["db"].get(PlanningRegionSettings, 1)
    region.federal_state_code, region.auto_public_holidays = "NW", True
    welt["db"].commit()
    return welt


def _kai(db, slot_id, welt):
    return [t for eid, t in _personen(db, slot_id) if eid == welt["kai"]][0]


def test_verlaengern_laesst_heiligabend_und_silvester_aus(nrw):
    db = nrw["db"]
    slot = _einsatz(nrw, "a", MO21, SILV, personen={"tom": None, "kai": [_tag(MO21)]})
    e = verlaengern(db, slot_id=slot.id, employee_id=nrw["kai"], ab_tag=_tag(MO21))
    assert (e["tage"], e["bis"]) == ([_iso(n) for n in (49, 50, 51, 56, 57, 58)], _iso(58))


def test_geraet_ebenso(nrw):
    """Für alle -- auch ein Gerät, das keine Gruppe und keine Sollzeit hat."""
    db = nrw["db"]
    slot = _einsatz(nrw, "a", MO21, MO28, personen={"tom": None}, geraete=[{"resource_id": nrw["pritsche"], "tage": [_tag(MO21)]}])
    verlaengern(db, slot_id=slot.id, resource_id=nrw["pritsche"], ab_tag=_tag(MO21))
    assert _geraete(db, slot.id) == [(nrw["pritsche"], [_iso(n) for n in (49, 50, 51, 56)])]


def test_direkt_anschliessend_ueber_die_feiertage(nrw):
    """Einsatz bis Mi 23.12., Tag setzen auf Mo 28.12.: dazwischen nur Heiligabend, Feiertage und Wochenende -- der Einsatz wird verlängert, kein neuer."""
    db = nrw["db"]
    slot = _einsatz(nrw, "a", MO21, MO21 + 2, personen={"tom": None})
    e = tag_setzen(db, order_id=nrw["a"].id, tag=_tag(MO28), employee_id=nrw["kai"])
    assert (e["aktion"], e["slot_id"]) == ("verlaengert", slot.id)
    assert _zeitraum(db, slot.id) == (_tag(MO21), _tag(MO28))


def test_abgeschalteter_kalendertag_ist_wieder_arbeitstag(nrw):
    db = nrw["db"]
    for e in db.query(ArbeitszeitKalendertag).all():
        e.aktiv = False
    db.commit()
    slot = _einsatz(nrw, "a", MO21, SILV, personen={"tom": None, "kai": [_tag(MO21)]})
    e = verlaengern(db, slot_id=slot.id, employee_id=nrw["kai"], ab_tag=_tag(MO21))
    assert e["tage"] == [_iso(n) for n in (49, 50, 51, 52, 56, 57, 58, 59)]
