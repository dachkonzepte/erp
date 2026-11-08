"""Version 1.9.267 (Stufe 6, R5b, Punkt 1): Tag setzen -- eine Person, eine Kolonne oder ein Gerät für einen Tag an einen Auftrag.

    dazu        hat der Auftrag an dem Tag einen Einsatz, kommt sie dazu -- an genau diesem Tag; die anderen behalten ihre Tage
    verlängert  schließt der Tag direkt an (kein Arbeitstag dazwischen, Fr -> Mo, Antwort 7), wird der Einsatz verlängert, der vordere zuerst; die Falle:
                wer „alle Tage“ hatte, steht danach an genau den bisherigen Tagen
    neu         sonst ein neuer Einsatz: vorläufig, Stunden = Rest, mit Kolonne nur, wenn eine Kolonne gezogen wurde
    Antwort 6   auf einer Karte: dieser Einsatz; frei: Person/Gerät in den ohne Kolonne, sonst den frühesten; Kolonne in den derselben Kolonne
    Antwort 8   Kolonne auf eine andere Kolonne: ein eigener Einsatz; Kolonne auf eine Kranvermietung: 422; Person allein an einen Tag ohne Einsatz einer
                Kranvermietung: 422
    Fragen      nur bei einer Warnung, die die Aktion neu bringt; eine Rückfrage für die ganze Kolonne; Hinweise (Antrag offen) fragen nicht
    Prüfen      derselbe Weg, nichts bleibt
    API         POST /api/planning/tag-setzen: 200, 409 (Warnung, geschlossen), 404 (Auftrag, fremde Karte), 422
"""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.main import create_team
from app.models import EmployeeAbsence, EmployeeAbsenceRequest, PlanningSlot, PlanningSlotEmployee, PlanningSlotResource, WorkPreparation
from app.planning import PlanungsWarnung, create_slot
from app.schemas import TeamCreate, TeamEmployeeInput
from app.tag_aktionen import KOLONNE_LEER, KRAN_KOLONNE, KRAN_ZUERST, NICHT_AM_TAG, tag_setzen
from tests.test_v090_planning_board import setup_order
from tests.test_v633_besetzung_je_einsatz import _person
from tests.test_v660_besetzung_je_tag import _geraete, _personen, _tag, welt  # noqa: F401 -- welt ist eine Fixture

D1 = Decimal("1")


def _iso(n):
    return _tag(n).isoformat()


def _einsatz(w, auftrag, von, bis, team=None, personen=None, **mehr):
    """Ein Einsatz an Auftrag w[auftrag]: mit Kolonne (team) oder ohne mit den Personen (Name -> None = alle Tage)."""
    besetzung = None if personen is None else [{"employee_id": w[n], "tage": t} for n, t in personen.items()]
    return create_slot(w["db"], order_id=w[auftrag].id, team_id=team, start_date=_tag(von), end_date=_tag(bis), planned_hours=D1, trotzdem_planen=True,
                       besetzung=besetzung, **mehr)


def _zeitraum(db, slot_id):
    db.expire_all()
    s = db.get(PlanningSlot, slot_id)
    return (s.start_date, s.end_date)


def _einsaetze_von(db, order):
    db.expire_all()
    prep = db.scalar(select(WorkPreparation.id).where(WorkPreparation.order_id == order.id))
    return list(db.scalars(select(PlanningSlot).where(PlanningSlot.preparation_id == prep).order_by(PlanningSlot.id))) if prep else []


@pytest.fixture
def mehr(welt):
    db = welt["db"]
    welt["lia"] = _person(db, "M-4", "Lia").id
    welt["sued"] = create_team(TeamCreate(team_number="S", name="Süd", employees=[TeamEmployeeInput(employee_id=welt["lia"], role="Monteur")]), db)
    welt["c"] = setup_order(db, "667c")
    return welt


# --- dazu, verlängert, neu --------------------------------------------------------------------------------------------------------------

def test_dazu_nur_an_diesem_tag(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 2, team=welt["nord"].id)
    e = tag_setzen(db, order_id=welt["a"].id, tag=_tag(1), employee_id=welt["kai"])
    assert (e["aktion"], e["slot_id"], e["tage"], e["bis"]) == ("dazu", slot.id, [_iso(1)], _iso(2))
    assert _personen(db, slot.id) == [(welt["tom"], None), (welt["mia"], None), (welt["kai"], [_iso(1)])]
    assert _zeitraum(db, slot.id) == (_tag(0), _tag(2))
    noch = tag_setzen(db, order_id=welt["a"].id, tag=_tag(2), employee_id=welt["kai"])  # ein zweiter Tag kommt zu ihren Tagen
    assert noch["tage"] == [_iso(1), _iso(2)]
    tag_setzen(db, order_id=welt["a"].id, tag=_tag(1), employee_id=welt["tom"])  # schon da: nichts ändert sich
    assert _personen(db, slot.id) == [(welt["tom"], None), (welt["mia"], None), (welt["kai"], [_iso(1), _iso(2)])]
    tag_setzen(db, order_id=welt["a"].id, tag=_tag(0), employee_id=welt["kai"])  # jetzt an allen Tagen: Normalform „alle Tage“
    assert _personen(db, slot.id) == [(welt["tom"], None), (welt["mia"], None), (welt["kai"], None)]


def test_verlaengert_ueber_das_wochenende_mit_der_falle(welt):
    """Fr -> Mo (Antwort 7). Die Falle: Tom, Mia und die Pritsche standen an allen Tagen -- danach an genau Mo bis Fr, nicht am neuen Montag."""
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, team=welt["nord"].id)
    e = tag_setzen(db, order_id=welt["a"].id, tag=_tag(7), employee_id=welt["kai"])
    assert (e["aktion"], e["slot_id"], e["bis"]) == ("verlaengert", slot.id, _iso(7))
    woche = [_iso(n) for n in range(5)]
    assert _personen(db, slot.id) == [(welt["tom"], woche), (welt["mia"], woche), (welt["kai"], [_iso(7)])]
    assert _geraete(db, slot.id) == [(welt["pritsche"], woche)]
    assert _zeitraum(db, slot.id) == (_tag(0), _tag(7))


def test_verlaengert_nach_vorn_und_der_vordere_zuerst(welt):
    db = welt["db"]
    hinten = _einsatz(welt, "b", 1, 3, personen={"tom": None})
    e = tag_setzen(db, order_id=welt["b"].id, tag=_tag(0), employee_id=welt["kai"])
    assert (e["aktion"], e["slot_id"]) == ("verlaengert", hinten.id)
    assert _zeitraum(db, hinten.id) == (_tag(0), _tag(3))
    assert _personen(db, hinten.id) == [(welt["tom"], [_iso(1), _iso(2), _iso(3)]), (welt["kai"], [_iso(0)])]
    s1 = _einsatz(welt, "a", 7, 8, personen={"tom": None})
    s2 = _einsatz(welt, "a", 10, 11, personen={"mia": None})
    mi = tag_setzen(db, order_id=welt["a"].id, tag=_tag(9), employee_id=welt["kai"])  # schließt an beide an: der vordere wird verlängert
    assert (mi["aktion"], mi["slot_id"]) == ("verlaengert", s1.id)
    assert _zeitraum(db, s2.id) == (_tag(10), _tag(11))


def test_neu_ohne_anschluss(welt):
    db = welt["db"]
    _einsatz(welt, "b", 0, 0, team=welt["nord"].id)
    e = tag_setzen(db, order_id=welt["b"].id, tag=_tag(2), employee_id=welt["kai"])  # Mi: Di liegt dazwischen -- kein Anschluss; ohne Kolonne
    neu = db.get(PlanningSlot, e["slot_id"])
    assert (e["aktion"], neu.status, neu.team_assignment_id, neu.art, _zeitraum(db, neu.id)) == ("neu", "vorlaeufig", None, "baustelle", (_tag(2), _tag(2)))
    assert _personen(db, neu.id) == [(welt["kai"], None)]
    k = tag_setzen(db, order_id=welt["a"].id, tag=_tag(4), team_id=welt["nord"].id, trotzdem_planen=True)  # eine Kolonne: neu mit ihren Mitgliedern
    slot = db.get(PlanningSlot, k["slot_id"])
    assert k["aktion"] == "neu" and slot.team_assignment.team_id == welt["nord"].id
    assert _personen(db, slot.id) == [(welt["tom"], None), (welt["mia"], None)] and _geraete(db, slot.id) == [(welt["pritsche"], None)]
    assert slot.capacity.planned_hours > 0  # Stunden = Rest des Auftrags, wie beim Anlegen


def test_geraet_setzen(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 1, personen={"tom": None})
    e = tag_setzen(db, order_id=welt["a"].id, tag=_tag(1), resource_id=welt["kran"])
    assert (e["aktion"], e["tage"]) == ("dazu", [_iso(1)])
    assert _geraete(db, slot.id) == [(welt["kran"], [_iso(1)])]


# --- Antwort 6 und 8: welcher Einsatz ---------------------------------------------------------------------------------------------------

def test_zwei_einsaetze_am_tag_karte_und_vorschlag(mehr):
    w, db = mehr, mehr["db"]
    nord = _einsatz(w, "a", 0, 4, team=w["nord"].id)
    ohne = _einsatz(w, "a", 2, 2, personen={"kai": None})
    assert tag_setzen(db, order_id=w["a"].id, tag=_tag(2), employee_id=w["lia"], pruefen=True)["slot_id"] == ohne.id  # frei: der ohne Kolonne
    assert tag_setzen(db, order_id=w["a"].id, tag=_tag(2), employee_id=w["lia"], slot_id=nord.id)["slot_id"] == nord.id  # Karte: dieser
    assert tag_setzen(db, order_id=w["a"].id, tag=_tag(2), team_id=w["nord"].id)["slot_id"] == nord.id  # Kolonne: der derselben Kolonne
    sued = tag_setzen(db, order_id=w["a"].id, tag=_tag(2), team_id=w["sued"].id, slot_id=nord.id, trotzdem_planen=True)  # Antwort 8: ein eigener
    assert sued["aktion"] == "neu" and db.get(PlanningSlot, sued["slot_id"]).team_assignment.team_id == w["sued"].id
    beide = _einsatz(w, "b", 0, 0, team=w["nord"].id)
    frueh = _einsatz(w, "b", 0, 0, team=w["sued"].id)
    assert tag_setzen(db, order_id=w["b"].id, tag=_tag(0), resource_id=w["kran"], pruefen=True)["slot_id"] == min(beide.id, frueh.id)  # sonst der früheste


def test_kranvermietung_antwort_8(welt):
    db = welt["db"]
    kran = _einsatz(welt, "a", 2, 2, art="kranvermietung", geraete=[{"resource_id": welt["kran"]}])
    with pytest.raises(ValueError, match=KRAN_KOLONNE):
        tag_setzen(db, order_id=welt["a"].id, tag=_tag(2), team_id=welt["nord"].id, slot_id=kran.id)
    with pytest.raises(ValueError, match=KRAN_KOLONNE):  # frei: die Art des Auftrags ist Kranvermietung
        tag_setzen(db, order_id=welt["a"].id, tag=_tag(4), team_id=welt["nord"].id)
    with pytest.raises(ValueError, match=KRAN_ZUERST):  # Do schließt an -- aber ohne Kran
        tag_setzen(db, order_id=welt["a"].id, tag=_tag(3), employee_id=welt["kai"])
    with pytest.raises(ValueError, match=KRAN_ZUERST):  # Fr: neu
        tag_setzen(db, order_id=welt["a"].id, tag=_tag(4), employee_id=welt["kai"])
    assert tag_setzen(db, order_id=welt["a"].id, tag=_tag(2), employee_id=welt["kai"])["aktion"] == "dazu"  # als Bediener am Krantag
    weiter = tag_setzen(db, order_id=welt["a"].id, tag=_tag(4), resource_id=welt["kran"])  # das Gerät: eine neue Kranvermietung
    assert weiter["aktion"] == "neu" and db.get(PlanningSlot, weiter["slot_id"]).art == "kranvermietung"
    assert [s.id for s in _einsaetze_von(db, welt["a"])] == [kran.id, weiter["slot_id"]]
    gemischt = _einsatz(welt, "b", 0, 0, art="kranvermietung", geraete=[{"resource_id": welt["kran"]}])  # Kran Mo, danach eine Baustelle Di
    _einsatz(welt, "b", 1, 1, personen={"mia": None})
    with pytest.raises(ValueError, match=KRAN_KOLONNE):  # auf der Karte der Kranvermietung -- auch wenn der Auftrag sonst Baustelle ist
        tag_setzen(db, order_id=welt["b"].id, tag=_tag(0), team_id=welt["nord"].id, slot_id=gemischt.id, trotzdem_planen=True)


def test_kolonne_ohne_nicht_zeigen(mehr):
    """Antwort 9: eine gezogene Kolonne bringt ihre Mitglieder ohne „nicht zeigen“."""
    from app.models import EmployeePlanningSettings
    w, db = mehr, mehr["db"]
    vera = _person(db, "M-5", "Vera")
    db.add(EmployeePlanningSettings(employee_id=vera.id, plantafel="nicht_zeigen"))
    db.commit()
    team = create_team(TeamCreate(team_number="V", name="Mit Vera", employees=[TeamEmployeeInput(employee_id=w["lia"], role="Monteur"),
                                                                             TeamEmployeeInput(employee_id=vera.id, role="Monteur")]), db)
    e = tag_setzen(db, order_id=w["c"].id, tag=_tag(0), team_id=team.id)  # neu: der Vorschlag beim Anlegen
    assert _personen(db, e["slot_id"]) == [(w["lia"], None)]
    weiter = tag_setzen(db, order_id=w["c"].id, tag=_tag(1), team_id=team.id)  # verlängert: die Mitglieder, die die Aktion selbst dazu nimmt
    assert weiter["aktion"] == "verlaengert" and _personen(db, e["slot_id"]) == [(w["lia"], None)]


def test_kolonne_ohne_vorschlag(welt):
    db = welt["db"]
    leer = create_team(TeamCreate(team_number="L", name="Leer", employees=[]), db)
    with pytest.raises(ValueError, match=KOLONNE_LEER):
        tag_setzen(db, order_id=welt["a"].id, tag=_tag(0), team_id=leer.id)


# --- Fragen -----------------------------------------------------------------------------------------------------------------------------

def _zahl(db, modell):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(modell))


def test_neue_warnung_fragt_nichts_gespeichert(welt):
    db = welt["db"]
    _einsatz(welt, "a", 2, 2, personen={"tom": None})
    vorher = (_zahl(db, PlanningSlot), _zahl(db, PlanningSlotEmployee), _zahl(db, WorkPreparation))
    with pytest.raises(PlanungsWarnung) as fehler:
        tag_setzen(db, order_id=welt["b"].id, tag=_tag(2), employee_id=welt["tom"])
    assert [(w["type"], w["employee_id"]) for w in fehler.value.warnungen] == [("employee", welt["tom"])]
    del fehler  # gibt den Traceback frei: er hält die verworfenen Objekte fest, SQLAlchemy warnte sonst beim nächsten Flush (nur im Test)
    assert (_zahl(db, PlanningSlot), _zahl(db, PlanningSlotEmployee), _zahl(db, WorkPreparation)) == vorher  # auch keine neue AV
    assert tag_setzen(db, order_id=welt["b"].id, tag=_tag(2), employee_id=welt["tom"], trotzdem_planen=True)["aktion"] == "neu"


def test_was_vorher_schon_da_war_fragt_nicht(welt):
    db = welt["db"]
    _einsatz(welt, "a", 2, 2, personen={"kai": None})
    b = _einsatz(welt, "b", 2, 2, personen={"kai": None})  # Kai doppelt -- schon vorher
    e = tag_setzen(db, order_id=welt["b"].id, tag=_tag(2), employee_id=welt["mia"])
    assert (e["aktion"], e["slot_id"]) == ("dazu", b.id)
    _einsatz(welt, "a", 0, 4, personen={"kai": None, "tom": None})  # Kai Mo–Fr an a -- mit b am Mi doppelt (auch das schon vorher)
    with pytest.raises(PlanungsWarnung) as fehler:  # ein neuer Tag derselben Warnung fragt: Kai am Do an b schließt an und ist doppelt mit demselben Einsatz
        tag_setzen(db, order_id=welt["b"].id, tag=_tag(3), employee_id=welt["kai"])
    assert [(w["type"], w["employee_id"]) for w in fehler.value.warnungen] == [("employee", welt["kai"])]


def test_abwesend_fragt_antrag_nicht(welt):
    db = welt["db"]
    slot = _einsatz(welt, "a", 0, 4, personen={"tom": None})
    db.add(EmployeeAbsence(employee_id=welt["kai"], absence_type="Urlaub", absence_category="urlaub", start_date=_tag(1), end_date=_tag(1)))
    db.add(EmployeeAbsenceRequest(employee_id=welt["mia"], absence_type="Urlaub", absence_category="urlaub", start_date=_tag(2), end_date=_tag(2),
                                  status="pending"))
    db.commit()
    with pytest.raises(PlanungsWarnung) as fehler:
        tag_setzen(db, order_id=welt["a"].id, tag=_tag(1), employee_id=welt["kai"])
    assert [w["type"] for w in fehler.value.warnungen] == ["absence"]
    e = tag_setzen(db, order_id=welt["a"].id, tag=_tag(2), employee_id=welt["mia"])  # Antrag offen: ein Hinweis, keine Rückfrage
    assert e["slot_id"] == slot.id


def test_ganze_kolonne_eine_rueckfrage(welt):
    db = welt["db"]
    _einsatz(welt, "b", 2, 2, personen={"tom": None, "mia": None})
    with pytest.raises(PlanungsWarnung) as fehler:
        tag_setzen(db, order_id=welt["a"].id, tag=_tag(2), team_id=welt["nord"].id)
    assert sorted(w["employee_id"] for w in fehler.value.warnungen if w["type"] == "employee") == sorted([welt["tom"], welt["mia"]])


# --- Prüfen und API ---------------------------------------------------------------------------------------------------------------------

def test_pruefen_schreibt_nichts(welt):
    db = welt["db"]
    _einsatz(welt, "a", 2, 2, personen={"tom": None})
    slot = _einsatz(welt, "b", 0, 1, personen={"mia": None})
    vorher = (_zahl(db, PlanningSlot), _zahl(db, PlanningSlotEmployee), _zahl(db, PlanningSlotResource), _zeitraum(db, slot.id))
    p = tag_setzen(db, order_id=welt["b"].id, tag=_tag(2), employee_id=welt["tom"], pruefen=True)
    assert (p["aktion"], p["slot_id"], p["fragt"], [w["type"] for w in p["warnungen"]]) == ("verlaengert", slot.id, True, ["employee"])
    neu = tag_setzen(db, order_id=welt["a"].id, tag=_tag(9), employee_id=welt["kai"], pruefen=True)  # Mi der Woche danach: kein Anschluss
    assert (neu["aktion"], neu["slot_id"], neu["fragt"]) == ("neu", None, False)
    assert (_zahl(db, PlanningSlot), _zahl(db, PlanningSlotEmployee), _zahl(db, PlanningSlotResource), _zeitraum(db, slot.id)) == vorher


def test_api(welt):
    db, client = welt["db"], welt["client"]
    slot = _einsatz(welt, "a", 0, 1, personen={"tom": None})
    fremd = _einsatz(welt, "b", 0, 1, personen={"mia": None})
    url = "/api/planning/tag-setzen"
    r = client.post(url, json={"order_id": welt["a"].id, "tag": _iso(1), "employee_id": welt["kai"]})
    assert r.status_code == 200, r.text
    assert (r.json()["aktion"], r.json()["einsatz"]["id"], r.json()["tage"]) == ("dazu", slot.id, [_iso(1)])
    assert {e["id"]: e["tage"] for e in r.json()["einsatz"]["employees"]} == {welt["tom"]: None, welt["kai"]: [_iso(1)]}
    p = client.post(url, json={"order_id": welt["b"].id, "tag": _iso(1), "employee_id": welt["tom"], "pruefen": True})
    assert p.status_code == 200 and p.json()["fragt"] and "einsatz" not in p.json()
    assert client.post(url, json={"order_id": welt["b"].id, "tag": _iso(1), "employee_id": welt["tom"]}).status_code == 409
    assert client.post(url, json={"order_id": 999999, "tag": _iso(1), "employee_id": welt["kai"]}).status_code == 404
    assert client.post(url, json={"order_id": welt["a"].id, "tag": _iso(1), "employee_id": welt["kai"], "slot_id": fremd.id}).status_code == 404
    zu_spaet = client.post(url, json={"order_id": welt["a"].id, "tag": _iso(4), "employee_id": welt["kai"], "slot_id": slot.id})
    assert zu_spaet.status_code == 422 and zu_spaet.json()["detail"] == NICHT_AM_TAG
    for koerper in ({"order_id": welt["a"].id, "tag": _iso(1)}, {"order_id": welt["a"].id, "tag": _iso(1), "employee_id": welt["kai"], "team_id": welt["nord"].id}):
        assert client.post(url, json=koerper).status_code == 422
    assert client.post(url, json={"order_id": welt["a"].id, "tag": _iso(1), "employee_id": welt["alt"]}).status_code == 422  # inaktiv


def test_geschlossener_auftrag(welt):
    db = welt["db"]
    _einsatz(welt, "a", 0, 2, personen={"tom": None})  # auch „dazu“ an einen bestehenden Einsatz geht nicht
    welt["a"].status = "abgeschlossen"
    db.commit()
    r = welt["client"].post("/api/planning/tag-setzen", json={"order_id": welt["a"].id, "tag": _iso(1), "employee_id": welt["kai"]})
    assert r.status_code == 409
