"""Version 1.9.248 (Stufe 6, R4, Punkt 4): der Einsatz-Dialog prüft, bevor gespeichert wird (POST /api/planning/slots/pruefen und …/{id}/pruefen).

    Prüfen       derselbe Weg wie Anlegen bzw. Ändern (dieselben Regeln und Antworten), danach rollback -- nichts bleibt, auch kein Projekt einer
                 Kranvermietung mit Kunde und keine verbrauchte Nummer; beim Ändern alle Warnungen des Einsatzes, auch ohne Änderung
    Kapazität    aus der Sollzeit der Besetzung an den Arbeitstagen minus Anfahrt, mit Rechnung („2 Personen × 3 Arbeitstage × 8,00 h = 48,00 h“, sonst
                 je Person); dazu der Rest laut Kalkulation (Soll minus die anderen Einsätze des Auftrags)
    Personen     je Person der Besetzung, der Kolonne und „+ Person“: frei, „auch bei P-… · 03.–05.11.“ (gewählt: doppelt), „Kranvermietung …“ bzw.
                 „bei P-…“ (nicht gewählt: belegt), abwesend (die Art nur ab Büro – Finanzen), „beantragt …“ (der ganze Antrag, wie die Zeichnung)
    Geräte       je Gerät: „alle Tage“ bzw. „nur 03., 05.11.“, „vermietet …“ (Kranvermietung) bzw. „bei P-…“, Termin im Kalender, abgelaufene Prüfung
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import Customer, EmployeeAbsence, EmployeeAbsenceRequest, PlanningSlot, PlanningSlotEmployee, Project
from app.planning import create_slot, einsatz_pruefen
from app.routers.planning import router as planning_router
from app.settings import preview_number
from tests.test_v090_planning_board import setup_order
from tests.test_v633_besetzung_je_einsatz import _kolonne, _person
from tests.test_v634_geraete_je_einsatz import _geraet

D = Decimal
MO, DI, MI, DO, FR = (date(2026, 11, 2 + i) for i in range(5))


@pytest.fixture()
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    kai, nele, lia = _person(db, "M-1", "Kai"), _person(db, "M-2", "Nele"), _person(db, "M-3", "Lia")
    sued = _kolonne(db, "Süd", [kai, lia, nele])
    kran, pritsche = _geraet(db, "K-1", "Kran"), _geraet(db, "F-1", "Pritsche")
    kunde = Customer(name="Familie Sommer", last_name="Sommer")
    db.add(kunde)
    db.commit()
    return {"db": db, "kai": kai, "nele": nele, "lia": lia, "sued": sued, "kran": kran, "pritsche": pritsche, "kunde": kunde,
            "a": setup_order(db, "1"), "b": setup_order(db, "2"), "client": lambda rolle="admin": router_test_client(db, planning_router, role=rolle)}


def _zaehlen(db):
    return tuple(db.scalar(select(func.count()).select_from(m)) for m in (PlanningSlot, PlanningSlotEmployee, Project))


def _neu(w, **mehr):
    return {"order_id": w["a"].id, "team_id": w["sued"].id, "employee_ids": [w["kai"].id, w["nele"].id], "start_date": DI, "end_date": DO,
            "planned_hours": D("32"), "travel_hours_per_employee_day": D("0"), "geraete": [{"resource_id": w["pritsche"]}], **mehr}


def test_neu_mit_kapazitaet_und_ohne_spuren(welt):
    db = welt["db"]
    vorher = _zaehlen(db)
    e = einsatz_pruefen(db, None, **_neu(welt))
    assert e["kapazitaet"]["text"] == "2 Personen × 3 Arbeitstage × 8,00 h = 48,00 h"  # KW 45: Tarif 8,00 h (KW 18–48)
    assert (e["kapazitaet"]["summe"], e["kapazitaet"]["stunden"]) == (D("48.00"), D("32.00"))
    assert [(p["name"], p["gewaehlt"], p["vorschlag"], p["zustand"]) for p in e["personen"]] == [
        ("Kai Test", True, True, "frei"), ("Nele Test", True, True, "frei"), ("Lia Test", False, True, "frei")]
    assert [(g["name"], g["gewaehlt"], g["tage_text"]) for g in e["geraete"]] == [("Pritsche", True, "alle Tage")]
    assert (e["warnungen"], e["hinweise"]) == ([], [])
    assert _zaehlen(db) == vorher  # nichts bleibt


def test_anfahrt_und_ungleiche_tage_je_person(welt):
    db = welt["db"]
    db.add(EmployeeAbsence(employee_id=welt["nele"].id, absence_type="Urlaub", absence_category="urlaub", start_date=DO, end_date=DO))
    db.commit()
    e = einsatz_pruefen(db, None, **_neu(welt, travel_hours_per_employee_day=D("0.5")))
    assert e["kapazitaet"]["text"] == "Kai 3 × 7,50 h + Nele 2 × 7,50 h = 37,50 h (Sollzeit je Tag − 0,50 h Anfahrt)"


def test_zustand_je_person(welt):
    db = welt["db"]
    create_slot(db, order_id=welt["b"].id, team_id=None, employee_ids=[welt["kai"].id], start_date=MO, end_date=MI, planned_hours=D("1"),
                trotzdem_planen=True)
    create_slot(db, order_id=None, art="kranvermietung", customer_id=welt["kunde"].id, team_id=None, employee_ids=[welt["lia"].id], start_date=MI,
                end_date=DO, geraete=[{"resource_id": welt["kran"]}], planned_hours=D("1"), trotzdem_planen=True)
    db.add(EmployeeAbsenceRequest(employee_id=welt["nele"].id, absence_type="Urlaub", absence_category="urlaub", start_date=DO, end_date=FR,
                                  status="pending"))
    db.commit()
    projekt_b = welt["b"].project.project_number
    e = einsatz_pruefen(db, None, mit_art=True, **_neu(welt))
    zustand = {p["name"]: (p["zustand"], p["text"]) for p in e["personen"]}
    assert zustand == {"Kai Test": ("doppelt", f"auch bei {projekt_b} · 03.–04.11."), "Nele Test": ("antrag", "Urlaub beantragt 05.–06.11."),
                       "Lia Test": ("belegt", "Kranvermietung 04.–05.11.")}
    assert [w["type"] for w in e["warnungen"]] == ["employee"] and [h["type"] for h in e["hinweise"]] == ["antrag_offen"]
    ohne_art = einsatz_pruefen(db, None, mit_art=False, **_neu(welt))
    assert {p["name"]: p["text"] for p in ohne_art["personen"]}["Nele Test"] == "beantragt 05.–06.11."


def test_zustand_je_geraet_und_einzelne_tage(welt):
    db = welt["db"]
    create_slot(db, order_id=None, art="kranvermietung", customer_id=welt["kunde"].id, team_id=None, employee_ids=[welt["lia"].id], start_date=MI,
                end_date=DO, geraete=[{"resource_id": welt["kran"]}], planned_hours=D("1"), trotzdem_planen=True)
    e = einsatz_pruefen(db, None, weitere_geraete=[welt["kran"]], **_neu(welt, geraete=[{"resource_id": welt["pritsche"], "tage": [DI, DO]}]))
    assert [(g["name"], g["gewaehlt"], g["tage_text"], g["zustand"], g["text"]) for g in e["geraete"]] == [
        ("Pritsche", True, "nur 03., 05.11.", "frei", ""), ("Kran", False, "", "belegt", "vermietet 04.–05.11.")]


def test_kranvermietung_mit_kunde_laesst_kein_projekt_und_keine_nummer(welt):
    db = welt["db"]
    vorher, nummer = _zaehlen(db), preview_number(db, "project")
    e = einsatz_pruefen(db, None, art="kranvermietung", order_id=None, customer_id=welt["kunde"].id, team_id=None, employee_ids=[welt["lia"].id],
                        start_date=DI, end_date=MI, geraete=[{"resource_id": welt["kran"]}])
    assert e["kapazitaet"]["rest"] is None  # nach Aufwand: keine Kalkulation
    assert (_zaehlen(db), preview_number(db, "project")) == (vorher, nummer)


def test_aendern_nennt_alle_warnungen_und_laesst_alles(welt):
    db = welt["db"]
    a = create_slot(db, order_id=welt["a"].id, team_id=None, employee_ids=[welt["kai"].id], start_date=DI, end_date=MI, planned_hours=D("4"),
                    trotzdem_planen=True)
    create_slot(db, order_id=welt["b"].id, team_id=None, employee_ids=[welt["kai"].id], start_date=MI, end_date=MI, planned_hours=D("1"),
                trotzdem_planen=True)
    e = einsatz_pruefen(db, a.id)  # ohne Änderung: die Warnung steht trotzdem da
    assert [w["type"] for w in e["warnungen"]] == ["employee"]
    e2 = einsatz_pruefen(db, a.id, end_date=FR, notes="neu")
    assert e2["kapazitaet"]["text"] == "1 Person × 4 Arbeitstage × 8,00 h = 32,00 h"
    db.expire_all()
    slot = db.get(PlanningSlot, a.id)
    assert (slot.end_date, slot.notes) == (MI, None)


def test_rest_laut_kalkulation_ohne_den_eigenen_einsatz(welt):
    db = welt["db"]
    from app.work_preparation import planned_hours
    soll = planned_hours(welt["a"])
    create_slot(db, order_id=welt["a"].id, team_id=welt["sued"].id, start_date=MO, end_date=MO, planned_hours=D("2"), trotzdem_planen=True)
    e = einsatz_pruefen(db, None, **_neu(welt))
    assert e["kapazitaet"]["rest"] == max(D("0"), soll - D("2"))


def test_schnittstelle_mit_rolle_und_fehlern(welt):
    db = welt["db"]
    db.add(EmployeeAbsence(employee_id=welt["nele"].id, absence_type="Krankheit", absence_category="krankheit", start_date=DO, end_date=DO))
    db.commit()
    body = {**_neu(welt), "start_date": DI.isoformat(), "end_date": DO.isoformat(), "planned_hours": "32", "travel_hours_per_employee_day": "0"}
    for rolle, text in (("buero_auftrag", "abwesend 05.11."), ("buero_finanzen", "Krankheit 05.11.")):
        r = welt["client"](rolle).post("/api/planning/slots/pruefen", json=body)
        assert r.status_code == 200, r.text
        assert {p["name"]: p["text"] for p in r.json()["personen"]}["Nele Test"] == text
        assert ("Krankheit" in r.text) is (rolle == "buero_finanzen")
    # seit 1.9.263 (Antwort 4): ohne Kolonne genügt ein Gerät (bis 1.9.262: 422 „mindestens eine Person“, auch mit der Pritsche)
    r = welt["client"]().post("/api/planning/slots/pruefen", json={**body, "team_id": None, "employee_ids": []})
    assert r.status_code == 200, r.text
    r = welt["client"]().post("/api/planning/slots/pruefen", json={**body, "team_id": None, "employee_ids": [], "geraete": []})
    assert (r.status_code, "mindestens eine Person oder ein Gerät" in r.text) == (422, True)
    r = welt["client"]().post("/api/planning/slots/99999/pruefen", json={"notes": "x"})
    assert r.status_code == 404
    assert _zaehlen(db)[0] == 0
