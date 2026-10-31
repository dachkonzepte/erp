"""Version 1.9.143 (Stufe 6, R1, Punkt 1): Konflikte beim Speichern eines Einsatzes -- warnen, trotzdem planbar (Entscheidung Tobias).

    Warnung      Person, Kolonne, Gerät doppelt, Person abwesend -> 409 mit Liste, nichts gespeichert (auch keine Arbeitsvorbereitung, keine
                 Kolonnen-Zuweisung); mit „trotzdem_planen“ 200 und die Warnungen in der Antwort
    Hinweis      Feiertag, betriebsfreier Tag, Kapazität -> 200 ohne Rückfrage, in der Antwort; seit 1.9.150 meldet ein Wochenende nichts, es ist nur kein Arbeitstag
    Ändern       Kolonne oder Zeitraum geändert -> wie Anlegen; nur Notiz, Status oder Stunden -> keine Rückfrage, Konflikte in der Antwort
    P8           Einsätze stornierter Aufträge zählen nicht, weder als Warnung noch in der Kapazität der Tafel
    Rollen       die Art einer Abwesenheit im 409 nur für Admin und Büro – Finanzen (Krankheitssichtbarkeit)
    Seite        der Dialog zeigt die Liste, „Trotzdem planen“ schickt das Häkchen mit
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.auftragsstatus import status_aendern
from app.main import create_resource, create_team
from app.models import Employee, EmployeeAbsence, PlanningHoliday, PlanningSlot, WorkPreparation, WorkPreparationTeamAssignment
from app.planning import PlanungsWarnung, create_slot, planning_board, update_planning_settings, update_slot
from app.routers.planning import router as planning_router
from app.schemas import OperationalResourceCreate, TeamCreate, TeamEmployeeInput, TeamResourceInput
from tests.test_v090_planning_board import setup_order

MONTAG = date(2026, 11, 2)  # keine Feiertage in dieser Woche


def _person(db, nummer, name):
    emp = Employee(employee_number=nummer, first_name=name, last_name="Test", employee_group="gewerblich", hourly_wage=Decimal("20"),
                   weekly_hours=Decimal("40"), active=True)
    db.add(emp)
    db.commit()
    return emp


def _kolonne(db, nummer, personen=(), geraete=()):
    return create_team(TeamCreate(team_number=nummer, name=f"Kolonne {nummer}", employees=[TeamEmployeeInput(employee_id=p.id, role="Monteur") for p in personen],
                                  resources=[TeamResourceInput(resource_id=g.id, role="Standard") for g in geraete]), db)


def _kran(db):
    return create_resource(OperationalResourceCreate(resource_number="K-1", resource_type="Maschine", name="Kran 30 m", identifier="K1"), db)


def _body(order, team, start=MONTAG, ende=None, **mehr):
    return {"order_id": order.id, "team_id": team.id, "start_date": start.isoformat(), "end_date": (ende or start + timedelta(days=2)).isoformat(),
            "planned_hours": "1", **mehr}


@pytest.fixture()
def tafel(threaded_db_session, router_test_client):
    db = threaded_db_session
    return db, router_test_client(db, planning_router)


def _arten(liste):
    return sorted({k["type"] for k in liste})


def test_person_doppelt_409_mit_liste_und_mit_trotzdem_planen_200(tafel):
    db, client = tafel
    tom = _person(db, "M-1", "Tom")
    a, b = _kolonne(db, "A", [tom]), _kolonne(db, "B", [tom])
    erster, zweiter = setup_order(db, "1"), setup_order(db, "2")
    assert client.post("/api/planning/slots", json=_body(erster, a)).status_code == 200

    antwort = client.post("/api/planning/slots", json=_body(zweiter, b))
    assert antwort.status_code == 409, antwort.text
    daten = antwort.json()
    assert daten["detail"] == "Der Einsatz überschneidet sich – bitte prüfen oder trotzdem planen."
    assert [(k["type"], k["label"], k["other_project"]) for k in daten["warnungen"]] == [("employee", "Tom Test", erster.project.project_number)]
    assert db.scalar(select(func.count()).select_from(PlanningSlot)) == 1

    antwort = client.post("/api/planning/slots", json=_body(zweiter, b, trotzdem_planen=True))
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert _arten(daten["warnungen"]) == ["employee"]
    assert daten["conflicts"] == daten["warnungen"] + daten["hinweise"]
    assert db.scalar(select(func.count()).select_from(PlanningSlot)) == 2


def test_abgelehnter_einsatz_hinterlaesst_nichts(tafel):
    """Bis 1.9.142 legte schon der Versuch die Arbeitsvorbereitung an -- samt Materialbedarf, der den Abgleich mit dem Angebot sperrt."""
    db, client = tafel
    tom = _person(db, "M-1", "Tom")
    a, b = _kolonne(db, "A", [tom]), _kolonne(db, "B", [tom])
    erster, zweiter = setup_order(db, "1"), setup_order(db, "2")
    client.post("/api/planning/slots", json=_body(erster, a))
    assert client.post("/api/planning/slots", json=_body(zweiter, b)).status_code == 409
    assert db.scalar(select(WorkPreparation).where(WorkPreparation.order_id == zweiter.id)) is None
    assert db.scalar(select(func.count()).select_from(WorkPreparationTeamAssignment)) == 1


def test_kolonne_doppelt(tafel):
    db, client = tafel
    a = _kolonne(db, "A", [_person(db, "M-1", "Tom")])
    client.post("/api/planning/slots", json=_body(setup_order(db, "1"), a))
    antwort = client.post("/api/planning/slots", json=_body(setup_order(db, "2"), a))
    assert antwort.status_code == 409
    assert "team" in _arten(antwort.json()["warnungen"])


def test_geraet_doppelt(tafel):
    db, client = tafel
    kran = _kran(db)
    a, b = _kolonne(db, "A", [_person(db, "M-1", "Tom")], [kran]), _kolonne(db, "B", [_person(db, "M-2", "Mia")], [kran])
    client.post("/api/planning/slots", json=_body(setup_order(db, "1"), a))
    antwort = client.post("/api/planning/slots", json=_body(setup_order(db, "2"), b))
    assert antwort.status_code == 409
    assert [(k["type"], k["label"]) for k in antwort.json()["warnungen"]] == [("resource", "Kran 30 m")]


def test_person_abwesend_warnt_und_nennt_die_art_nur_finanzen_und_admin(threaded_db_session, router_test_client):
    db = threaded_db_session
    mia = _person(db, "M-1", "Mia")
    team = _kolonne(db, "A", [mia])
    db.add(EmployeeAbsence(employee_id=mia.id, absence_type="Krankheit", absence_category="krankheit", start_date=MONTAG, end_date=MONTAG))
    db.commit()
    order = setup_order(db, "1")
    for rolle, text in (("buero_auftrag", "Mia Test · abwesend"), ("buero_finanzen", "Mia Test · Krankheit"), ("admin", "Mia Test · Krankheit")):
        antwort = router_test_client(db, planning_router, role=rolle).post("/api/planning/slots", json=_body(order, team))
        assert antwort.status_code == 409, rolle
        warnung = antwort.json()["warnungen"][0]
        assert (warnung["type"], warnung["label"]) == ("absence", text), rolle
        assert "label_redacted" not in warnung
    antwort = router_test_client(db, planning_router, role="buero_auftrag").post("/api/planning/slots", json=_body(order, team, trotzdem_planen=True))
    assert antwort.status_code == 200
    assert "Krankheit" not in antwort.text and "label_redacted" not in antwort.text


def test_feiertag_200_mit_hinweis(tafel):
    db, client = tafel
    team = _kolonne(db, "A", [_person(db, "M-1", "Tom")])
    antwort = client.post("/api/planning/slots", json=_body(setup_order(db, "1"), team, start=date(2026, 12, 24), ende=date(2026, 12, 25)))
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten["warnungen"] == []
    assert [(k["type"], k["label"], k["date"]) for k in daten["hinweise"]] == [("holiday", "1. Weihnachtstag", "2026-12-25")]


def test_betriebsfreier_tag_200_mit_hinweis(tafel):
    db, client = tafel
    db.add(PlanningHoliday(holiday_date=MONTAG, name="Betriebsausflug", active=True))
    db.commit()
    team = _kolonne(db, "A", [_person(db, "M-1", "Tom")])
    antwort = client.post("/api/planning/slots", json=_body(setup_order(db, "1"), team, ende=MONTAG + timedelta(days=1)))
    assert antwort.status_code == 200
    assert [(k["type"], k["label"]) for k in antwort.json()["hinweise"]] == [("holiday", "Betriebsausflug")]


def test_wochenende_meldet_nichts(tafel):
    """Seit 1.9.150 (R1 Nachrunde, Punkt 1): weder beim Speichern noch auf der Tafel -- das Wochenende ist nur kein Arbeitstag."""
    db, client = tafel
    team = _kolonne(db, "A", [_person(db, "M-1", "Tom")])
    freitag = MONTAG + timedelta(days=4)
    antwort = client.post("/api/planning/slots", json=_body(setup_order(db, "1"), team, start=freitag, ende=freitag + timedelta(days=3)))
    assert antwort.status_code == 200
    assert antwort.json()["hinweise"] == [] and antwort.json()["warnungen"] == []
    tafel_daten = planning_board(db, MONTAG, MONTAG + timedelta(days=13))
    assert tafel_daten["slots"][0]["conflicts"] == []
    assert tafel_daten["conflict_count"] == 0


def test_kein_arbeitstag_unter_der_woche_meldet_nichts(tafel):
    """Dieselbe Regel für einen Wochentag, an dem der Betrieb laut Einstellungen nicht arbeitet."""
    db, client = tafel
    update_planning_settings(db, wednesday=False)
    team = _kolonne(db, "A", [_person(db, "M-1", "Tom")])
    antwort = client.post("/api/planning/slots", json=_body(setup_order(db, "1"), team, start=MONTAG, ende=MONTAG + timedelta(days=4)))
    assert antwort.status_code == 200
    assert antwort.json()["hinweise"] == []


def test_feiertag_am_wochenende_meldet_nichts(tafel):
    """Fällt ein Feiertag auf einen Tag, der ohnehin kein Arbeitstag ist, ändert er nichts; ein Feiertag im selben Einsatz unter der Woche meldet sich weiter."""
    db, client = tafel
    samstag, freitag = MONTAG + timedelta(days=5), MONTAG + timedelta(days=4)
    db.add(PlanningHoliday(holiday_date=samstag, name="Am Samstag", active=True))
    db.commit()
    team = _kolonne(db, "A", [_person(db, "M-1", "Tom")])
    antwort = client.post("/api/planning/slots", json=_body(setup_order(db, "1"), team, start=freitag, ende=freitag + timedelta(days=3)))
    assert antwort.json()["hinweise"] == []
    db.add(PlanningHoliday(holiday_date=freitag, name="Am Freitag", active=True))
    db.commit()
    antwort = client.post("/api/planning/slots", json=_body(setup_order(db, "2"), _kolonne(db, "B", [_person(db, "M-2", "Mia")]), start=freitag, ende=freitag + timedelta(days=3)))
    assert [(k["type"], k["label"]) for k in antwort.json()["hinweise"]] == [("holiday", "Am Freitag")]


def test_kapazitaet_200_mit_hinweis(tafel):
    db, client = tafel
    team = _kolonne(db, "A", [_person(db, "M-1", "Tom")])
    antwort = client.post("/api/planning/slots", json=_body(setup_order(db, "1"), team, ende=MONTAG, planned_hours="50"))
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert _arten(daten["hinweise"]) == ["capacity"]
    assert daten["warnungen"] == []


def test_verschieben_auf_eine_belegte_kolonne_fragt_nach_und_laesst_alles_stehen(tafel):
    db, client = tafel
    a, b = _kolonne(db, "A", [_person(db, "M-1", "Tom")]), _kolonne(db, "B", [_person(db, "M-2", "Mia")])
    client.post("/api/planning/slots", json=_body(setup_order(db, "1"), a))
    zweiter = client.post("/api/planning/slots", json=_body(setup_order(db, "2"), b)).json()
    url = f"/api/planning/slots/{zweiter['id']}"

    antwort = client.put(url, json={"team_id": a.id})
    assert antwort.status_code == 409
    assert "team" in _arten(antwort.json()["warnungen"])
    db.expire_all()
    slot = db.get(PlanningSlot, zweiter["id"])
    assert slot.team_assignment.team_id == b.id
    assert db.scalar(select(func.count()).select_from(WorkPreparationTeamAssignment).where(
        WorkPreparationTeamAssignment.preparation_id == slot.preparation_id)) == 1  # keine zweite Zuweisung zurückgeblieben

    antwort = client.put(url, json={"team_id": a.id, "trotzdem_planen": True})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["team_id"] == a.id


def test_nur_notiz_aendern_fragt_nicht_nach_und_nennt_die_konflikte(tafel):
    db, client = tafel
    tom = _person(db, "M-1", "Tom")
    a, b = _kolonne(db, "A", [tom]), _kolonne(db, "B", [tom])
    client.post("/api/planning/slots", json=_body(setup_order(db, "1"), a))
    zweiter = client.post("/api/planning/slots", json=_body(setup_order(db, "2"), b, trotzdem_planen=True)).json()
    url = f"/api/planning/slots/{zweiter['id']}"
    for aenderung in ({"notes": "Kran ab 8 Uhr"}, {"status": "bestaetigt"}, {"planned_hours": "2"},
                      {"team_id": b.id, "start_date": zweiter["start_date"], "end_date": zweiter["end_date"], "notes": "wie der Dialog"}):
        antwort = client.put(url, json=aenderung)
        assert antwort.status_code == 200, (aenderung, antwort.text)
        assert _arten(antwort.json()["warnungen"]) == ["employee"]


def test_null_als_trotzdem_planen_422(tafel):
    db, client = tafel
    team = _kolonne(db, "A", [_person(db, "M-1", "Tom")])
    slot = client.post("/api/planning/slots", json=_body(setup_order(db, "1"), team)).json()
    assert client.put(f"/api/planning/slots/{slot['id']}", json={"trotzdem_planen": None}).status_code == 422


def test_einsatz_eines_stornierten_auftrags_zaehlt_nicht(tafel):
    """P8: bis 1.9.142 färbte er andere Einsätze rot."""
    db, client = tafel
    tom = _person(db, "M-1", "Tom")
    a, b = _kolonne(db, "A", [tom]), _kolonne(db, "B", [tom])
    storno, normal = setup_order(db, "1"), setup_order(db, "2")
    alt = client.post("/api/planning/slots", json=_body(storno, a, planned_hours="16")).json()
    status_aendern(db, storno.id, "storniert", "Kunde abgesprungen")
    db.commit()

    antwort = client.post("/api/planning/slots", json=_body(normal, b))
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["warnungen"] == []

    daten = planning_board(db, MONTAG, MONTAG + timedelta(days=13))
    je_id = {s["id"]: s for s in daten["slots"]}
    assert je_id[alt["id"]]["conflicts"] == []  # bleibt auf der Tafel, mit dem Status des Auftrags
    assert je_id[alt["id"]]["order_status"] == "storniert"
    assert je_id[antwort.json()["id"]]["conflicts"] == []
    assert daten["conflict_count"] == 0
    # die Stunden des stornierten zählen nicht in der Kapazität der Kolonne
    assert daten["team_capacity"][str(a.id)][MONTAG.isoformat()]["planned_hours"] == 0


def test_abgeschlossener_auftrag_zaehlt_weiter(tafel):
    """Nur storniert ist vorgegeben; ein abgeschlossener Auftrag hat tatsächlich gearbeitet."""
    db, client = tafel
    tom = _person(db, "M-1", "Tom")
    a, b = _kolonne(db, "A", [tom]), _kolonne(db, "B", [tom])
    fertig = setup_order(db, "1")
    client.post("/api/planning/slots", json=_body(fertig, a))
    status_aendern(db, fertig.id, "abgeschlossen", "ohne Rechnung")
    db.commit()
    assert client.post("/api/planning/slots", json=_body(setup_order(db, "2"), b)).status_code == 409


def test_geschaeftsfunktion_fragt_ohne_router_genauso(tafel):
    db, _ = tafel
    tom = _person(db, "M-1", "Tom")
    a, b = _kolonne(db, "A", [tom]), _kolonne(db, "B", [tom])
    create_slot(db, order_id=setup_order(db, "1").id, team_id=a.id, start_date=MONTAG, end_date=MONTAG)
    zweiter = setup_order(db, "2")
    with pytest.raises(PlanungsWarnung):
        create_slot(db, order_id=zweiter.id, team_id=b.id, start_date=MONTAG, end_date=MONTAG)
    slot = create_slot(db, order_id=zweiter.id, team_id=b.id, start_date=MONTAG + timedelta(days=1), end_date=MONTAG + timedelta(days=1))
    with pytest.raises(PlanungsWarnung):
        update_slot(db, slot.id, start_date=MONTAG, end_date=MONTAG)
    assert update_slot(db, slot.id, start_date=MONTAG, end_date=MONTAG, trotzdem_planen=True).start_date == MONTAG
