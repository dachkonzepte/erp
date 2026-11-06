"""Version 1.9.236 (Stufe 6, R3a, Punkt 5): Konflikte auf dem neuen Modell (Besetzung und Geräte je Einsatz).

    Warnung   Person doppelt (auch einzeln Zugeordnete, B5/B6) · Person abwesend (genehmigt) · Gerät doppelt (auch Termine im Kalender des Geräts) ·
              Gerät mit abgelaufener Prüffrist (neu)
    Hinweis   Antrag offen · Feiertag oder betriebsfreier Tag · Kapazität (Sollzeit der Besetzung an den Arbeitstagen minus Anfahrt)
    entfällt  Kolonne doppelt -- es zählen die Personen
"""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.models import EnabledModule, OperationalAsset, OperationalAssetInspection, PlanningSlot, WorkPreparation, WorkPreparationEmployee, \
    WorkPreparationTeamAssignment
from app.planning import HINWEIS_ARTEN, WARNUNG_ARTEN, create_slot, einsatz_konflikte, planning_board
from app.routers.planning import router as planning_router
from tests.besetzung import wie_migration
from tests.test_v090_planning_board import setup_order
from tests.test_v633_besetzung_je_einsatz import _kolonne, _person
from tests.test_v634_geraete_je_einsatz import _geraet

ROOT = Path(__file__).resolve().parent.parent
MONTAG = date(2026, 11, 2)


@pytest.fixture()
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    tom, kai = _person(db, "M-1", "Tom"), _person(db, "M-2", "Kai")
    kran = _geraet(db, "K-1", "Kran")
    asset = OperationalAsset(resource_id=kran)
    db.add(asset)
    db.flush()
    db.add(OperationalAssetInspection(asset_id=asset.id, inspection_type="UVV", next_due_date=MONTAG + timedelta(days=1)))
    db.commit()
    return {"db": db, "client": router_test_client(db, planning_router), "tom": tom, "kai": kai, "kran": kran, "nord": _kolonne(db, "N", [tom]),
            "a": setup_order(db, "1"), "b": setup_order(db, "2")}


def _body(w, order, tage=(0, 2), **mehr):
    return {"order_id": order.id, "team_id": None, "employee_ids": [w["kai"].id], "start_date": (MONTAG + timedelta(days=tage[0])).isoformat(),
            "end_date": (MONTAG + timedelta(days=tage[1])).isoformat(), "planned_hours": "1", **mehr}


def test_arten():
    assert WARNUNG_ARTEN == {"employee", "resource", "absence", "pruefung"}
    assert HINWEIS_ARTEN == {"holiday", "capacity", "antrag_offen", "kalendertag"}
    seite = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")
    assert "pruefung:'Prüffrist abgelaufen: '" in seite and "team:'Kolonne doppelt: '" not in seite


def test_pruefung_abgelaufen_ist_eine_warnung(welt):
    """UVV fällig am Di 03.11. -- ein Einsatz Mo–Fr mit dem Kran: eine Warnung mit dem ersten Tag danach (Mi 04.11.); trotzdem planbar."""
    client = welt["client"]
    body = _body(welt, welt["a"], tage=(0, 4), geraete=[{"resource_id": welt["kran"]}])
    r = client.post("/api/planning/slots", json=body)
    assert r.status_code == 409, r.text
    assert [(k["type"], k["label"], k["date"]) for k in r.json()["warnungen"]] == [("pruefung", "Kran · UVV fällig am 03.11.2026", "2026-11-04")]
    r = client.post("/api/planning/slots", json={**body, "trotzdem_planen": True})
    assert r.status_code == 200 and [k["type"] for k in r.json()["conflicts"]] == ["pruefung"], r.text
    tafel = planning_board(welt["db"], MONTAG, MONTAG + timedelta(days=6))
    assert [k["type"] for k in tafel["slots"][0]["conflicts"]] == ["pruefung"] and tafel["conflict_count"] == 1


def test_pruefung_nur_an_den_tagen_des_geraets(welt):
    """Der Kran nur am Mo und Di -- die Prüffrist läuft erst danach ab: keine Warnung; ebenso ein Einsatz, der vor der Fälligkeit endet."""
    client = welt["client"]
    r = client.post("/api/planning/slots", json=_body(welt, welt["a"], geraete=[{"resource_id": welt["kran"], "tage": [MONTAG.isoformat(),
                                                                                                                    (MONTAG + timedelta(days=1)).isoformat()]}]))
    assert r.status_code == 200 and r.json()["conflicts"] == [], r.text
    r = client.post("/api/planning/slots", json=_body(welt, welt["b"], tage=(0, 1), employee_ids=[welt["tom"].id], geraete=[{"resource_id": welt["kran"]}]))
    assert r.status_code == 409 and [k["type"] for k in r.json()["warnungen"]] == ["resource"], r.text  # nur der Kran doppelt am Mo/Di


def test_pruefung_zaehlt_nur_mit_betriebsmittelverwaltung(welt):
    db = welt["db"]
    db.add(EnabledModule(module_key="betriebsmittel", enabled=False))
    db.commit()
    slot = create_slot(db, order_id=welt["a"].id, team_id=None, employee_ids=[welt["kai"].id], start_date=MONTAG, end_date=MONTAG + timedelta(days=2),
                       planned_hours=Decimal("1"), geraete=[{"resource_id": welt["kran"]}])
    assert einsatz_konflikte(db, slot)["warnungen"] == []


def test_ohne_faelligkeit_keine_warnung(welt):
    db = welt["db"]
    for p in db.query(OperationalAssetInspection).all():
        p.next_due_date = None
    db.commit()
    slot = create_slot(db, order_id=welt["a"].id, team_id=None, employee_ids=[welt["kai"].id], start_date=MONTAG, end_date=MONTAG + timedelta(days=2),
                       planned_hours=Decimal("1"), geraete=[{"resource_id": welt["kran"]}])
    assert einsatz_konflikte(db, slot)["warnungen"] == []


def test_einzelzuweisung_aus_dem_bestand_zaehlt_als_person_doppelt(welt):
    """B5/B6: Kai einzeln an der AV von Auftrag 1 (Bestand vor 1.9.233, die Migration übernimmt ihn in die Besetzung) -- sein Einsatz an Auftrag 2
    am selben Tag meldet „Person doppelt“."""
    db = welt["db"]
    alt = create_slot(db, order_id=welt["a"].id, team_id=welt["nord"].id, start_date=MONTAG, end_date=MONTAG, planned_hours=Decimal("1"))
    db.add(WorkPreparationEmployee(preparation_id=alt.preparation_id, employee_id=welt["kai"].id))
    db.query(type(alt.besetzung[0])).filter_by(slot_id=alt.id).delete()
    db.commit()
    wie_migration(db, db.get(PlanningSlot, alt.id))
    db.commit()
    r = welt["client"].post("/api/planning/slots", json=_body(welt, welt["b"], tage=(0, 0)))
    assert r.status_code == 409 and [(k["type"], k["label"]) for k in r.json()["warnungen"]] == [("employee", "Kai Test")], r.text


def test_kapazitaet_sollzeit_der_besetzung_minus_anfahrt(welt):
    """Kai allein, Mo–Mi (KW 45: 8,00 h), Anfahrt 1,00 h: 3 × 7,00 h = 21,00 h; mit 25 h fehlen 4,00 h (Hinweis, keine Rückfrage)."""
    r = welt["client"].post("/api/planning/slots", json=_body(welt, welt["a"], planned_hours="25", travel_hours_per_employee_day="1"))
    assert r.status_code == 200, r.text
    assert [(k["type"], Decimal(str(k["shortfall_hours"]))) for k in r.json()["hinweise"]] == [("capacity", Decimal("4.00"))]


def test_zwei_einsaetze_derselben_kolonne_ohne_gemeinsame_person(welt):
    db = welt["db"]
    create_slot(db, order_id=welt["a"].id, team_id=welt["nord"].id, start_date=MONTAG, end_date=MONTAG, planned_hours=Decimal("1"))
    zweiter = create_slot(db, order_id=welt["b"].id, team_id=welt["nord"].id, employee_ids=[welt["kai"].id], start_date=MONTAG, end_date=MONTAG,
                          planned_hours=Decimal("1"))
    assert einsatz_konflikte(db, zweiter) == {"warnungen": [], "hinweise": []}
    assert db.query(WorkPreparationTeamAssignment).count() == 2 and db.query(WorkPreparation).count() == 2
