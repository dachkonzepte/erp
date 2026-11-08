"""Version 1.9.261 (Stufe 6, R5a, Punkt 2): Konflikte, Kapazität und der Zustand im Dialog je Tag.

    Doppelt     Person und Gerät doppelt nur an gemeinsamen Tagen (bis 1.9.260 bei Personen: die Zeiträume überschneiden sich), jeder Konflikt nennt seine
                Tage („tage“); der Bestand (alle Tage) meldet dasselbe wie bisher, nur mit den Tagen
    Je Tag      abwesend, Freistellung und Antrag offen nur an den Tagen der Person (der Antrag mit dem ersten betroffenen Tag); Feiertag oder betriebsfreier
                Tag nur, wenn an dem Tag jemand steht (Antwort 14)
    Kapazität   je Tag nur, wer an dem Tag am Einsatz steht (Verteilung, Rechnung im Dialog)
    Dialog      „auch bei …“ nur mit den gemeinsamen Tagen; ein Antrag nur, wenn er ihre Tage berührt
"""

from datetime import date, timedelta
from decimal import Decimal

from app.models import EmployeeAbsence, EmployeeAbsenceRequest, PlanningHoliday
from app.planning import _kapazitaet_rechnung, _load_slot, create_slot, einsatz_konflikte, planning_board
from tests.test_v660_besetzung_je_tag import welt  # noqa: F401 -- Fixture

MO = date(2026, 11, 2)
D1 = Decimal("1")


def _tag(n):
    return MO + timedelta(days=n)


def _einsatz(w, auftrag, personen, start=0, ende=2, **mehr):
    """Ohne Kolonne: personen = {Name: Tage oder None}."""
    return create_slot(w["db"], order_id=w[auftrag].id, team_id=None, start_date=_tag(start), end_date=_tag(ende), planned_hours=D1, trotzdem_planen=True,
                       besetzung=[{"employee_id": w[n], "tage": None if t is None else [_tag(x) for x in t]} for n, t in personen.items()], **mehr)


def _konflikte(w, slot):
    k = einsatz_konflikte(w["db"], _load_slot(w["db"], slot.id))
    return k["warnungen"] + k["hinweise"]


def test_person_doppelt_nur_an_gemeinsamen_tagen(welt):
    a = _einsatz(welt, "a", {"tom": [0]})
    b = _einsatz(welt, "b", {"tom": [1]})
    assert [k for k in _konflikte(welt, a) if k["type"] == "employee"] == []
    welt["db"].rollback()
    from app.planning import update_slot
    update_slot(welt["db"], b.id, besetzung=[{"employee_id": welt["tom"], "tage": [_tag(0), _tag(1)]}], trotzdem_planen=True)
    doppelt = [k for k in _konflikte(welt, a) if k["type"] == "employee"]
    assert [(k["employee_id"], k["tage"], k["other_slot_id"]) for k in doppelt] == [(welt["tom"], [_tag(0)], b.id)]


def test_bestand_meldet_dasselbe_mit_den_tagen(welt):
    a = _einsatz(welt, "a", {"tom": None}, 0, 2)
    _einsatz(welt, "b", {"tom": None}, 1, 4)
    [k] = [k for k in _konflikte(welt, a) if k["type"] == "employee"]
    assert k["tage"] == [_tag(1), _tag(2)] and k["stufe"] == "warnung"


def test_geraet_doppelt_nennt_die_tage(welt):
    a = _einsatz(welt, "a", {"tom": None}, geraete=[{"resource_id": welt["kran"], "tage": [_tag(1), _tag(2)]}])
    _einsatz(welt, "b", {"kai": None}, geraete=[{"resource_id": welt["kran"], "tage": [_tag(2)]}])
    [k] = [k for k in _konflikte(welt, a) if k["type"] == "resource"]
    assert (k["resource_id"], k["tage"]) == (welt["kran"], [_tag(2)])


def test_tafel_zaehlt_ein_paar_einmal(welt):
    _einsatz(welt, "a", {"tom": None}, 0, 2)
    _einsatz(welt, "b", {"tom": None}, 0, 2)
    tafel = planning_board(welt["db"], MO, MO + timedelta(days=13))
    assert tafel["zaehler"]["warnungen"] == 1


def test_abwesend_nur_an_ihren_tagen(welt):
    db = welt["db"]
    db.add(EmployeeAbsence(employee_id=welt["tom"], absence_type="Krankheit", absence_category="krankheit", start_date=_tag(1), end_date=_tag(1)))
    db.commit()
    nicht = _einsatz(welt, "a", {"tom": [0, 2]})
    assert [k for k in _konflikte(welt, nicht) if k["type"] == "absence"] == []
    da = _einsatz(welt, "b", {"tom": [1]})
    assert [(k["type"], k["date"]) for k in _konflikte(welt, da) if k["type"] == "absence"] == [("absence", _tag(1))]


def test_antrag_offen_nur_an_ihren_tagen_mit_dem_ersten(welt):
    db = welt["db"]
    db.add(EmployeeAbsenceRequest(employee_id=welt["tom"], absence_type="Urlaub", absence_category="urlaub", start_date=_tag(1), end_date=_tag(4),
                                  status="pending"))
    db.commit()
    nicht = _einsatz(welt, "a", {"tom": [0]})
    assert [k for k in _konflikte(welt, nicht) if k["type"] == "antrag_offen"] == []
    da = _einsatz(welt, "b", {"tom": [0, 2]})
    assert [k["date"] for k in _konflikte(welt, da) if k["type"] == "antrag_offen"] == [_tag(2)]


def test_feiertag_nur_wenn_jemand_steht(welt):
    db = welt["db"]
    db.add(PlanningHoliday(holiday_date=_tag(1), name="Betriebsausflug", active=True))
    db.commit()
    niemand = _einsatz(welt, "a", {"tom": [0, 2]})
    assert [k for k in _konflikte(welt, niemand) if k["type"] == "holiday"] == []
    jemand = _einsatz(welt, "b", {"kai": None})
    assert [k["date"] for k in _konflikte(welt, jemand) if k["type"] == "holiday"] == [_tag(1)]
    geraet = _einsatz(welt, "a", {"mia": [0]}, geraete=[{"resource_id": welt["kran"], "tage": [_tag(1)]}])  # ein Gerät ist auch jemand
    assert [k["date"] for k in _konflikte(welt, geraet) if k["type"] == "holiday"] == [_tag(1)]


def test_kapazitaet_je_tag(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", {"tom": [0], "mia": None})
    tafel = planning_board(db, MO, MO + timedelta(days=13))
    kap = {e["id"]: e for e in tafel["slots"]}[slot.id]
    from app.planning import _slot_distribution, load_planning_settings
    verteilung, _ = _slot_distribution(db, _load_slot(db, slot.id), load_planning_settings(db), set(), {})
    assert [(t, v["capacity"], sorted(v["available_employee_ids"])) for t, v in verteilung.items()] == [
        (_tag(0), Decimal("16.00"), sorted([welt["tom"], welt["mia"]])), (_tag(1), Decimal("8.00"), [welt["mia"]]), (_tag(2), Decimal("8.00"), [welt["mia"]])]
    assert kap["id"] == slot.id


def test_rechnung_im_dialog_je_person(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", {"tom": [0], "mia": None})
    r = _kapazitaet_rechnung(db, _load_slot(db, slot.id))
    assert (r["summe"], r["text"]) == (Decimal("32.00"), "Tom 1 × 8,00 h + Mia 3 × 8,00 h = 32,00 h")
    gleich = _einsatz(welt, "b", {"kai": None, "tom": [1, 2, 0]})  # Normalform: alle Tage
    assert _kapazitaet_rechnung(db, _load_slot(db, gleich.id))["text"] == "2 Personen × 3 Arbeitstage × 8,00 h = 48,00 h"


def test_dialog_auch_bei_nur_mit_den_gemeinsamen_tagen(welt):
    client = welt["client"]
    a = _einsatz(welt, "a", {"tom": [0, 2]})
    _einsatz(welt, "b", {"tom": [1, 2], "mia": [1]}, 0, 2)  # Tom in B Di und Mi, in A Mo und Mi -- gemeinsam nur Mi
    r = client.post(f"/api/planning/slots/{a.id}/pruefen", json={"weitere_personen": [welt["mia"]]})
    assert r.status_code == 200, r.text
    zustand = {p["name"]: (p["zustand"], p["text"]) for p in r.json()["personen"]}
    nr = welt["b"].project.project_number
    assert zustand["Tom Test"] == ("doppelt", f"auch bei {nr} · 04.11.")
    assert zustand["Mia Test"] == ("belegt", f"bei {nr} · 03.11.")  # nicht gewählt: gegen alle Tage des Einsatzes


def test_dialog_abwesend_nur_an_ihren_tagen(welt):
    db, client = welt["db"], welt["client"]
    db.add(EmployeeAbsence(employee_id=welt["tom"], absence_type="Urlaub", absence_category="urlaub", start_date=_tag(2), end_date=_tag(2)))
    db.commit()
    a = _einsatz(welt, "a", {"tom": [0]})
    r = client.post(f"/api/planning/slots/{a.id}/pruefen", json={})
    assert [(p["zustand"], p["text"]) for p in r.json()["personen"]] == [("frei", "frei")]


def test_dialog_antrag_nur_an_ihren_tagen(welt):
    db, client = welt["db"], welt["client"]
    db.add(EmployeeAbsenceRequest(employee_id=welt["tom"], absence_type="Urlaub", absence_category="urlaub", start_date=_tag(2), end_date=_tag(2),
                                  status="pending"))
    db.commit()
    a = _einsatz(welt, "a", {"tom": [0]})
    r = client.post(f"/api/planning/slots/{a.id}/pruefen", json={})
    assert [(p["zustand"], p["text"]) for p in r.json()["personen"]] == [("frei", "frei")]
    r = client.post(f"/api/planning/slots/{a.id}/pruefen", json={"besetzung": [{"employee_id": welt["tom"], "tage": [_tag(0).isoformat(), _tag(2).isoformat()]}]})
    assert [p["zustand"] for p in r.json()["personen"]] == ["antrag"]
