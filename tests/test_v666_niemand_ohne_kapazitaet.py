"""1.9.266 (Stufe 6, R5b, Punkt 0b, Frage 2 aus R5a): ein ganz leerer Einsatz („niemand“) meldet keine Kapazität.

Bis 1.9.265 meldete ein behaltener Einsatz ohne Person und Gerät für seine Stunden „Kapazität reicht nicht“ (Festlegung 1.9.263 Nr. 2, zweiter Teil) -- auf der
Tafel, im Knopf „Hinweise“, in der Antwort beim Speichern und in der Prüfung des Dialogs. Ein Einsatz mit jemandem (auch nur einem Gerät) meldet weiter."""

from datetime import date, timedelta
from decimal import Decimal

from app.planning import create_slot, einsatz_pruefen, planning_board, update_slot
from tests.test_v660_besetzung_je_tag import welt  # noqa: F401 -- welt ist eine Fixture

MO = date(2026, 11, 2)
ZEITRAUM = (MO, MO + timedelta(days=13))


def _einsatz(w, **mehr):
    return create_slot(w["db"], order_id=w["b"].id, team_id=None, start_date=MO, end_date=MO, planned_hours=Decimal("40"), trotzdem_planen=True, **mehr)


def _typen(liste):
    return [k["type"] for k in liste]


def test_niemand_auf_der_tafel_und_im_zaehler(welt):
    db = welt["db"]
    slot = _einsatz(welt, employee_ids=[welt["tom"]])
    [s] = planning_board(db, *ZEITRAUM)["slots"]
    assert _typen(s["conflicts"]) == ["capacity"]  # mit Tom: 40 h an einem Tag reichen nicht
    update_slot(db, slot.id, besetzung=[], wenn_leer="behalten")
    tafel = planning_board(db, *ZEITRAUM)
    [s] = tafel["slots"]
    assert s["niemand"] and s["conflicts"] == []
    assert tafel["zaehler"] == {"warnungen": 0, "hinweise": 0}


def test_niemand_beim_speichern_und_in_der_pruefung(welt):
    db = welt["db"]
    slot = _einsatz(welt, employee_ids=[welt["tom"]])
    vorher = einsatz_pruefen(db, slot.id)
    assert _typen(vorher["hinweise"]) == ["capacity"]
    pruefung = einsatz_pruefen(db, slot.id, besetzung=[])
    assert pruefung["leer"] and _typen(pruefung["hinweise"]) == []
    r = welt["client"].put(f"/api/planning/slots/{slot.id}", json={"besetzung": [], "wenn_leer": "behalten"})
    assert r.status_code == 200, r.text
    assert r.json()["niemand"] and r.json()["hinweise"] == [] and r.json()["conflicts"] == []


def test_mit_jemandem_meldet_es_weiter(welt):
    """Nur „niemand“ schweigt: ein Einsatz mit nur einem Gerät (keine Person, also keine Kapazität) meldet weiter, wie bisher."""
    db = welt["db"]
    _einsatz(welt, geraete=[{"resource_id": welt["pritsche"]}])
    [s] = planning_board(db, *ZEITRAUM)["slots"]
    assert not s["niemand"] and _typen(s["conflicts"]) == ["capacity"]
