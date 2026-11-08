"""Version 1.9.237 (Stufe 6, R3a, Punkt 6): die heutige Oberfläche der Plantafel bleibt auf dem neuen Modell bedienbar.

    Kolonne wählen   setzt ihre Mitglieder und Geräte (Server, tests/test_v633, tests/test_v634); „Einsatz bearbeiten“ nennt Besetzung und Geräte
    ohne Kolonne     Option im Dialog, schickt team_id null; Zeile „Ohne Kolonne“ auf der Tafel
    Status           vorläufig | fest (tests/test_v635)
    Klicktest        scripts/klicktest_plantafel_besetzung.py (Neu, Dialog, Süd mit Prüffrist, ohne Kolonne, Ziehen, Status)
"""

import re
from pathlib import Path

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node

ROOT = Path(__file__).resolve().parent.parent
HINTEN = "Eine andere Kolonne setzt ihre Mitglieder und Geräte."


@nur_mit_node
def test_dialog_nennt_besetzung_und_geraete():
    aufrufe = im_browser("planning.html", ["besetzungText", "fmt"], "",
                         "AUFRUFE.push({t: besetzungText({employees:[{name:'Tom Test'},{name:'Mia Test'}],"
                         "resources:[{name:'Pritsche',tage:null},{name:'Kran',tage:['2026-10-21','2026-10-22']}]})});"
                         "AUFRUFE.push({t: besetzungText({employees:[],resources:[]})});")
    assert [a["t"] for a in aufrufe] == [f"Besetzung: Tom Test, Mia Test · Geräte: Pritsche, Kran (21.10., 22.10.). {HINTEN}",
                                         f"Besetzung: niemand. {HINTEN}"]


def test_dialog_fuellt_die_zeile_beim_oeffnen():
    seite = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")
    # seit 1.9.248 (Einsatz-Dialog, Punkt 4): Besetzung und Geräte als Liste mit Zustand je Person (vom Server) -- die Zeile füllt das Öffnen;
    # seit 1.9.260 die Besetzung mit den Tagen je Person (bis 1.9.259 employee_ids:s.employees.map(e=>e.id))
    oeffnen = re.search(r"function openEdit\(id\)\{.*?\n", seite).group(0)
    assert ("besetzung:s.employees.map(e=>({employee_id:e.id,tage:e.tage??null})),geraete:s.resources.map(r=>({resource_id:r.id,tage:r.tage}))" in oeffnen
            and "dialogFuellen()" in oeffnen)
    assert "document.getElementById('edPersonen').innerHTML=personen.map(personZeile)" in seite


def test_klicktest_deckt_die_ablaeufe():
    klicktest = (ROOT / "scripts/klicktest_plantafel_besetzung.py").read_text(encoding="utf-8")
    for pruefung in ("Neu: Besetzung und Geräte der Kolonne", "Mitarbeiter: bei Tom und Mia, nicht bei Kai", "Fahrzeuge: bei der Pritsche",
                     "Dialog: Besetzung und Geräte", "Süd: Prüffrist abgelaufen", "ohne Kolonne: Zeile mit dem Balken",
                     "Ziehen nach Nord: Tom, Mia und die Pritsche", "Status fest gespeichert", "keine JS-Fehler"):
        assert f'"{pruefung}' in klicktest, pruefung


def test_ohne_kolonne_fragt_wie_jeder_wechsel(threaded_db_session, router_test_client):
    """Festlegung 1.9.237 Nr. 2: der Wechsel auf „ohne Kolonne“ fragt bei Warnungen zurück (hier die abgelaufene Prüffrist des Krans)."""
    from datetime import date, timedelta
    from app.models import OperationalAsset, OperationalAssetInspection
    from app.routers.planning import router as planning_router
    from tests.test_v090_planning_board import setup_order
    from tests.test_v633_besetzung_je_einsatz import _kolonne, _person
    from tests.test_v634_geraete_je_einsatz import _geraet
    db = threaded_db_session
    montag = date(2026, 11, 2)
    tom = _person(db, "M-1", "Tom")
    kran = _geraet(db, "K-1", "Kran")
    asset = OperationalAsset(resource_id=kran)
    db.add(asset); db.flush()
    db.add(OperationalAssetInspection(asset_id=asset.id, inspection_type="UVV", next_due_date=montag))
    db.commit()
    client = router_test_client(db, planning_router)
    body = {"order_id": setup_order(db, "1").id, "team_id": _kolonne(db, "N", [tom]).id, "geraete": [{"resource_id": kran}],
            "start_date": montag.isoformat(), "end_date": (montag + timedelta(days=2)).isoformat(), "planned_hours": "1", "trotzdem_planen": True}
    sid = client.post("/api/planning/slots", json=body).json()["id"]
    r = client.put(f"/api/planning/slots/{sid}", json={"team_id": None})
    assert r.status_code == 409 and [k["type"] for k in r.json()["warnungen"]] == ["pruefung"], r.text
    assert client.put(f"/api/planning/slots/{sid}", json={"team_id": None, "trotzdem_planen": True}).status_code == 200
