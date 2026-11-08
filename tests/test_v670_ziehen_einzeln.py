"""Version 1.9.270 (Stufe 6, R5b, Punkt 4, Antwort 12): in „Personen“ und „Geräte“ verschiebt Ziehen nur diese Person bzw. dieses Gerät.

    eigene Zeile   ihre Tage dieses Balkens um gleich viele Tage, im selben Einsatz (umsetzen mit genau: der Einsatz wird verlängert, die anderen bleiben an
                   ihren Tagen -- die Falle; am Rand gekürzt); steht sie allein, wandert der Einsatz mit (gleiche ID, Notiz, Status, Stunden)
    andere Zeile   eine andere Person bzw. ein anderes Gerät übernimmt die Tage (auf_employee_id / auf_resource_id; dieselbe Art, sonst 422)
    Rückfrage      bei einer neuen Warnung (409, „Trotzdem planen“); „niemand mehr“ wie bisher
    Kolonnen       weiter der ganze Einsatz (verschieben(), auch in ihren Gerätezeilen) -- test_v649 unverändert
    Seite          Balken mit ihrem Stück (data-von, data-bis), pointerup: umsetzenZiehen() in „Personen“ und „Geräte“
Im Browser mit echten Eingaben: scripts/klicktest_plantafel_ziehen.py.
"""

import json
import re

import pytest

from app.planning import PlanungsWarnung, leere_tage
from app.models import PlanningSlot
from app.tag_aktionen import tag_setzen, umsetzen
from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node, schreibende
from tests.test_v660_besetzung_je_tag import _geraete, _personen, _tag, welt  # noqa: F401 -- welt ist eine Fixture
from tests.test_v667_tag_setzen import _einsatz, _iso, _zeitraum, mehr  # noqa: F401 -- mehr ist eine Fixture
from tests.vorlagen_js import TEMPLATES


def test_eigene_zeile_nur_diese_person(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, team=welt["nord"].id)
    for n in (3, 4):
        tag_setzen(db, order_id=welt["a"].id, tag=_tag(n), employee_id=welt["kai"])
    e = umsetzen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(3), _tag(4)], ziel_tag=_tag(10), ziel_slot_id=slot.id, genau=True)
    assert (e["slot_id"], e["ziel_aktion"], e["tage"]) == (slot.id, "verlaengert", [_iso(10), _iso(11)])
    woche = [_iso(n) for n in range(5)]
    assert _personen(db, slot.id) == [(welt["tom"], woche), (welt["mia"], woche), (welt["kai"], [_iso(10), _iso(11)])]
    assert _zeitraum(db, slot.id) == (_tag(0), _tag(11))
    assert leere_tage(db.get(PlanningSlot, slot.id), lambda t: t.weekday() < 5) == [_tag(7), _tag(8), _tag(9)]  # die Lücke Mo–Mi


def test_allein_wandert_der_einsatz(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 3, 3, personen={"kai": None}, notes="Gerüst steht", status="fest")
    e = umsetzen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(3)], ziel_tag=_tag(9), ziel_slot_id=slot.id, genau=True)
    s = db.get(PlanningSlot, slot.id)
    assert (e["slot_id"], _zeitraum(db, slot.id), s.notes, s.status, _personen(db, slot.id)) == (slot.id, (_tag(9), _tag(9)), "Gerüst steht", "fest",
                                                                                                  [(welt["kai"], None)])


def test_andere_zeile_uebernimmt_die_tage(mehr):
    w, db = mehr, mehr["db"]
    slot = _einsatz(w, "a", 0, 4, team=w["nord"].id)
    for n in (3, 4):
        tag_setzen(db, order_id=w["a"].id, tag=_tag(n), employee_id=w["kai"])
    tag_setzen(db, order_id=w["a"].id, tag=_tag(4), employee_id=w["lia"])  # Lia schon am Fr: zusammen
    e = umsetzen(db, slot_id=slot.id, employee_id=w["kai"], tage=[_tag(3), _tag(4)], ziel_tag=_tag(3), ziel_slot_id=slot.id, genau=True,
                 auf_employee_id=w["lia"])
    assert e["tage"] == [_iso(3), _iso(4)]
    assert _personen(db, slot.id) == [(w["tom"], None), (w["mia"], None), (w["lia"], [_iso(3), _iso(4)])]  # Kai ist weg
    versetzt = umsetzen(db, slot_id=slot.id, employee_id=w["lia"], tage=[_tag(3), _tag(4)], ziel_tag=_tag(1), ziel_slot_id=slot.id, genau=True,
                        auf_employee_id=w["kai"])  # schräg: andere Zeile und andere Tage
    assert versetzt["tage"] == [_iso(1), _iso(2)] and _personen(db, slot.id)[-1] == (w["kai"], [_iso(1), _iso(2)])


def test_geraet_auf_geraet(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, team=welt["nord"].id)
    umsetzen(db, slot_id=slot.id, resource_id=welt["pritsche"], tage=[_tag(3), _tag(4)], ziel_tag=_tag(3), ziel_slot_id=slot.id, genau=True,
             auf_resource_id=welt["kran"])
    assert _geraete(db, slot.id) == [(welt["pritsche"], [_iso(0), _iso(1), _iso(2)]), (welt["kran"], [_iso(3), _iso(4)])]
    umsetzen(db, slot_id=slot.id, resource_id=welt["kran"], tage=[_tag(3), _tag(4)], ziel_tag=_tag(4), ziel_slot_id=slot.id, genau=True)  # eigene Zeile
    assert _geraete(db, slot.id)[-1] == (welt["kran"], [_iso(4), _iso(5)]) and _zeitraum(db, slot.id) == (_tag(0), _tag(5))


def test_regeln(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 2, personen={"tom": None})
    with pytest.raises(ValueError, match="nur auf eine Person"):
        umsetzen(db, slot_id=slot.id, employee_id=welt["tom"], tage=[_tag(0)], ziel_tag=_tag(0), ziel_slot_id=slot.id, genau=True,
                 auf_resource_id=welt["kran"])
    with pytest.raises(ValueError, match="braucht den Einsatz"):
        umsetzen(db, slot_id=slot.id, employee_id=welt["tom"], tage=[_tag(0)], ziel_tag=_tag(1), genau=True)


def test_rueckfrage_bei_warnung_und_rueckgaengig(welt):
    db, client = welt["db"], welt["client"]
    slot = _einsatz(welt, "a", 0, 2, personen={"tom": None, "kai": None})
    _einsatz(welt, "b", 1, 1, personen={"mia": None})  # Mia am Di bei b
    vorher = (_personen(db, slot.id), _zeitraum(db, slot.id))
    with pytest.raises(PlanungsWarnung) as fehler:
        umsetzen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(1)], ziel_tag=_tag(1), ziel_slot_id=slot.id, genau=True, auf_employee_id=welt["mia"])
    assert [(w["type"], w["employee_id"]) for w in fehler.value.warnungen] == [("employee", welt["mia"])]
    del fehler
    assert (_personen(db, slot.id), _zeitraum(db, slot.id)) == vorher
    e = umsetzen(db, slot_id=slot.id, employee_id=welt["kai"], tage=[_tag(1)], ziel_tag=_tag(1), ziel_slot_id=slot.id, genau=True, auf_employee_id=welt["mia"],
                 trotzdem_planen=True)
    assert client.post(e["umkehrung"]["pfad"], json=json.loads(json.dumps(e["umkehrung"]["body"]))).status_code == 200
    assert (_personen(db, slot.id), _zeitraum(db, slot.id)) == vorher


def test_api(welt):
    slot = _einsatz(welt, "a", 0, 2, personen={"tom": None})
    r = welt["client"].post(f"/api/planning/slots/{slot.id}/umsetzen", json={"employee_id": welt["tom"], "tage": [_iso(0)], "ziel_tag": _iso(0),
                                                                              "ziel_slot_id": slot.id, "genau": True, "auf_employee_id": welt["kai"]})
    assert r.status_code == 200, r.text
    assert {e["id"]: e["tage"] for e in r.json()["einsatz"]["employees"]} == {welt["tom"]: [_iso(1), _iso(2)], welt["kai"]: [_iso(0)]}


# --- Seite -------------------------------------------------------------------------------------------------------------------------------

SLOTS = [{"id": 1, "team_id": 7, "art": "baustelle", "start_date": "2026-11-02", "end_date": "2026-11-06", "duration_days": 5,
          "employees": [{"id": 5, "tage": ["2026-11-05", "2026-11-06"]}, {"id": 6, "tage": None}], "resources": [{"id": 3, "tage": None}]}]
VORBEREITUNG = (f"var board = {{slots: {json.dumps(SLOTS)}}}; var view = 'employees'; async function loadBoard() {{}} "
                "var geo = {spalten: Array.from({length: 14}, (_, i) => ({d: addDays('2026-11-02', i), x: i * 60, w: 60}))}; const KONFLIKT_ART = {}; "
                "function localDateIso(d) { const p = n => String(n).padStart(2, '0'); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`; } ")
FUNKTIONEN = ["umsetzenZiehen", "nurDieseZeile", "findSlot", "iso", "addDays", "einsatzTage", "personTageIn", "geraetTageIn", "einsatzHinweise", "konfliktZeile",
              "konfliktFrage", "leerFrage", "fmt"]


def _zug(zeile, wer, von, bis):
    return "{id: 1, zeile: '" + zeile + "', wer: " + str(wer) + ", von: '" + von + "', bis: '" + bis + "'}"


def _ziel(zeile, ident):
    return "{dataset: {zeile: '" + zeile + "', id: '" + str(ident) + "'}}"


@nur_mit_node
def test_seite_schickt_umsetzen():
    ablauf = (f"await umsetzenZiehen({_zug('person', 5, '2026-11-05', '2026-11-06')}, {_ziel('person', 5)}, 4);"   # eigene Zeile, einen Tag weiter
              f"await umsetzenZiehen({_zug('person', 5, '2026-11-05', '2026-11-06')}, {_ziel('person', 6)}, 3);"   # andere Zeile, gleiche Tage
              f"await umsetzenZiehen({_zug('person', 5, '2026-11-05', '2026-11-06')}, {_ziel('person', 5)}, 3);"   # nichts geändert: keine Anfrage
              f"await umsetzenZiehen({_zug('person', 5, '2026-11-05', '2026-11-06')}, {_ziel('geraet', 3)}, 3);"   # andere Art: keine Anfrage
              f"await umsetzenZiehen({_zug('person', 6, '2026-11-02', '2026-11-03')}, {_ziel('person', 6)}, 2);"   # alle Tage: das Stück Mo–Di
              f"await umsetzenZiehen({_zug('geraet', 3, '2026-11-02', '2026-11-06')}, {_ziel('geraet', 4)}, 0);")  # Gerät auf Gerät
    aufrufe = im_browser("planning.html", FUNKTIONEN, VORBEREITUNG, ablauf)
    basis = {"ziel_slot_id": 1, "genau": True}
    assert [(u, b) for _m, u, b in schreibende(aufrufe)] == [
        ("/api/planning/slots/1/umsetzen", {"employee_id": 5, "tage": ["2026-11-05", "2026-11-06"], "ziel_tag": "2026-11-06", **basis}),
        ("/api/planning/slots/1/umsetzen", {"employee_id": 5, "tage": ["2026-11-05", "2026-11-06"], "ziel_tag": "2026-11-05", **basis, "auf_employee_id": 6}),
        ("/api/planning/slots/1/umsetzen", {"employee_id": 6, "tage": ["2026-11-02", "2026-11-03"], "ziel_tag": "2026-11-04", **basis}),
        ("/api/planning/slots/1/umsetzen", {"resource_id": 3, "tage": ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"],
                                            "ziel_tag": "2026-11-02", **basis, "auf_resource_id": 4}),
    ]


@nur_mit_node
def test_welche_ansicht_zieht_einzeln():
    ablauf = ("var r = []; for (const [v, z] of [['employees', 'person'], ['resources', 'geraet'], ['teams', 'geraet'], ['teams', 'kolonne'], "
              "['employees', 'kolonne']]) { view = v; r.push(nurDieseZeile({dataset: {zeile: z}})); } AUFRUFE.push({r});")
    assert im_browser("planning.html", ["nurDieseZeile"], "var view = 'teams'; ", ablauf)[-1]["r"] == [True, True, False, False, False]


def test_balken_traegt_sein_stueck_und_pointerup_waehlt():
    text = (TEMPLATES / "planning.html").read_text(encoding="utf-8")
    assert 'data-von="${esc(b.von)}" data-bis="${esc(b.bis)}"' in text
    assert re.search(r"von:stueck\?stueck\[0\]:s\.start_date,bis:stueck\?stueck\[1\]:s\.end_date", text)
    assert "if(war.einzeln)umsetzenZiehen(war,z,tag-war.versatz);else verschieben(war.id,z,tag-war.versatz)" in text
