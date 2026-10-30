"""Version 1.9.145 (Stufe 6, R1, Punkt 3, F12): hat die Arbeitsvorbereitung Einsätze, ist ihr geplanter Zeitraum der der Einsätze -- lesend, mit Hinweis.

    Handeingabe  ohne Einsatz von Hand; kein Speichern eines Einsatzes überschreibt sie (Anlegen, Verschieben, Notiz, Löschen); der letzte gelöschte Einsatz leert sie nicht
    Lesen        mit Einsätzen liefern Arbeitsvorbereitung und Akte deren Zeitraum und „zeitraum_aus_einsaetzen“
    Schreiben    mit Einsätzen ein anderer Zeitraum von Hand -> 409, nichts geändert; derselbe Zeitraum und alles andere gehen
    Teil-Update  PUT nur mit einem Feld lässt die übrigen stehen (bis 1.9.144: Status „offen“, Ende und Hinweise leer)
    Seite        Felder gesperrt, Hinweis sichtbar, Zeitraum geht nicht mit
"""

from datetime import date
from pathlib import Path

import pytest

from app.akte import ausfuehrung
from app.models import WorkPreparation
from app.orders import load_order
from app.planning import create_slot
from app.routers.planning import router as planning_router
from app.routers.work_preparation import router as av_router
from tests.test_v090_planning_board import setup_order, setup_shared_teams

ROOT = Path(__file__).resolve().parent.parent
VON, BIS = "2026-12-02", "2026-12-03"


@pytest.fixture()
def welt(threaded_db_session, router_test_client):
    db = threaded_db_session
    order = setup_order(db)
    _, _, team1, team2 = setup_shared_teams(db)
    client = router_test_client(db, planning_router, av_router)
    return {"db": db, "client": client, "order": order, "team": team1, "team2": team2, "url": f"/api/orders/{order.id}/work-preparation"}


def _einsatz(welt, von="2026-11-12", bis="2026-11-13", **mehr):
    antwort = welt["client"].post("/api/planning/slots", json={"order_id": welt["order"].id, "team_id": welt["team"].id, "start_date": von, "end_date": bis, "planned_hours": "1", **mehr})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _gespeichert(welt):
    welt["db"].expire_all()
    prep = welt["db"].query(WorkPreparation).filter_by(order_id=welt["order"].id).one()
    return prep.planned_start, prep.planned_end


def test_ohne_einsatz_von_hand(welt):
    antwort = welt["client"].put(welt["url"], json={"planned_start": VON, "planned_end": BIS})
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert (daten["planned_start"], daten["planned_end"], daten["zeitraum_aus_einsaetzen"]) == (VON, BIS, False)


def test_notiz_am_einsatz_aendern_ueberschreibt_den_zeitraum_der_av_nicht(welt):
    """Der Beleg aus dem Befund (V5): die geänderte Notiz schrieb den Zeitraum des Einsatzes in die Arbeitsvorbereitung."""
    welt["client"].put(welt["url"], json={"planned_start": VON, "planned_end": BIS})
    einsatz = _einsatz(welt)
    hand = (date(2026, 12, 2), date(2026, 12, 3))
    assert _gespeichert(welt) == hand  # Anlegen schreibt nicht
    assert welt["client"].put(f"/api/planning/slots/{einsatz['id']}", json={"notes": "Kran ab 8 Uhr"}).status_code == 200
    assert _gespeichert(welt) == hand
    assert welt["client"].put(f"/api/planning/slots/{einsatz['id']}", json={"start_date": "2026-11-16", "end_date": "2026-11-17"}).status_code == 200
    assert _gespeichert(welt) == hand  # Verschieben auch nicht


def test_mit_einsaetzen_liest_die_av_deren_zeitraum_und_die_akte_auch(welt):
    welt["client"].put(welt["url"], json={"planned_start": VON, "planned_end": BIS})
    _einsatz(welt, "2026-11-12", "2026-11-13")
    _einsatz(welt, "2026-11-20", "2026-11-24", team_id=welt["team2"].id, trotzdem_planen=True)
    daten = welt["client"].get(welt["url"]).json()
    assert (daten["planned_start"], daten["planned_end"], daten["zeitraum_aus_einsaetzen"]) == ("2026-11-12", "2026-11-24", True)
    akte = ausfuehrung(welt["db"], load_order(welt["db"], welt["order"].id))["arbeitsvorbereitung"]
    assert (akte["planned_start"], akte["planned_end"]) == (date(2026, 11, 12), date(2026, 11, 24))


def test_mit_einsatz_von_hand_409_und_nichts_geaendert(welt):
    welt["client"].put(welt["url"], json={"planned_start": VON, "planned_end": BIS, "site_notes": "Zufahrt Tor 2"})
    _einsatz(welt)
    for body in ({"planned_start": "2026-11-01"}, {"planned_end": "2026-12-24"}, {"planned_start": None, "planned_end": None},
                 {"planned_start": "2026-11-01", "site_notes": "anders"}):
        antwort = welt["client"].put(welt["url"], json=body)
        assert antwort.status_code == 409, body
        assert antwort.json()["detail"] == "Der geplante Zeitraum ergibt sich aus den Einsätzen der Plantafel – ändern lässt er sich dort."
    assert _gespeichert(welt) == (date(2026, 12, 2), date(2026, 12, 3))
    assert welt["client"].get(welt["url"]).json()["site_notes"] == "Zufahrt Tor 2"


def test_mit_einsatz_derselbe_zeitraum_und_alles_andere_gehen(welt):
    _einsatz(welt, "2026-11-12", "2026-11-13")
    antwort = welt["client"].put(welt["url"], json={"planned_start": "2026-11-12", "planned_end": "2026-11-13", "status": "bereit"})
    assert antwort.status_code == 200, antwort.text
    antwort = welt["client"].put(welt["url"], json={"site_notes": "Zufahrt Tor 2", "material_notes": "Kran bestellt"})
    assert antwort.status_code == 200
    daten = antwort.json()
    assert (daten["status"], daten["site_notes"], daten["material_notes"]) == ("bereit", "Zufahrt Tor 2", "Kran bestellt")


def test_letzter_einsatz_geloescht_handeingabe_wieder_da(welt):
    """Bis 1.9.144 stand die Arbeitsvorbereitung danach leer da (V6)."""
    welt["client"].put(welt["url"], json={"planned_start": VON, "planned_end": BIS})
    einsatz = _einsatz(welt)
    assert welt["client"].delete(f"/api/planning/slots/{einsatz['id']}").status_code == 200
    daten = welt["client"].get(welt["url"]).json()
    assert (daten["planned_start"], daten["planned_end"], daten["zeitraum_aus_einsaetzen"]) == (VON, BIS, False)
    assert welt["client"].put(welt["url"], json={"planned_start": "2026-12-07", "planned_end": None}).status_code == 200


def test_teil_update_laesst_die_uebrigen_felder_stehen(welt):
    """V7: PUT nur mit Beginn setzte den Status auf „offen“ und leerte Ende und Hinweise."""
    welt["client"].put(welt["url"], json={"status": "bereit", "planned_start": VON, "planned_end": BIS, "site_notes": "Tor 2", "material_notes": "Kran"})
    daten = welt["client"].put(welt["url"], json={"planned_start": "2026-12-01"}).json()
    assert (daten["status"], daten["planned_start"], daten["planned_end"], daten["site_notes"], daten["material_notes"]) == ("bereit", "2026-12-01", BIS, "Tor 2", "Kran")
    assert welt["client"].put(welt["url"], json={"status": None}).status_code == 422


def test_seite_sperrt_die_felder_und_schickt_den_zeitraum_nicht():
    html = (ROOT / "app/templates/work_preparation.html").read_text(encoding="utf-8")
    assert "document.getElementById('start').disabled=document.getElementById('end').disabled=!!prep.zeitraum_aus_einsaetzen" in html
    assert "document.getElementById('zeitraumHinweis').hidden=!prep.zeitraum_aus_einsaetzen" in html
    assert "...(prep.zeitraum_aus_einsaetzen?{}:{planned_start:" in html


def test_kein_einsatz_schreibt_mehr_in_die_arbeitsvorbereitung():
    """Die eine Stelle, die das tat, gibt es nicht mehr."""
    quelltext = (ROOT / "app/planning.py").read_text(encoding="utf-8")
    assert "sync_preparation_dates" not in quelltext
    assert "prep.planned_start =" not in quelltext and "prep.planned_end =" not in quelltext


def test_create_slot_ohne_router_schreibt_auch_nicht(welt):
    welt["client"].put(welt["url"], json={"planned_start": VON, "planned_end": BIS})
    create_slot(welt["db"], order_id=welt["order"].id, team_id=welt["team"].id, start_date=date(2026, 11, 12), end_date=date(2026, 11, 12))
    assert _gespeichert(welt) == (date(2026, 12, 2), date(2026, 12, 3))
