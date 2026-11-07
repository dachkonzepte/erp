"""Version 1.9.251 (Stufe 6, R4, Punkt 5): ein Termin aus dem Kran-Postfach -- ein Klick zeigt ihn mit „Als Kranvermietung übernehmen …“.

    Server       POST /api/planning/kran-termine/{id}/pruefen: die Vorschau des Dialogs auf demselben Weg wie die Übernahme -- Gerät und Zeitraum vom
                 Termin, der eigene Termin warnt nicht, ein anderer Einsatz am Gerät schon; schreibt nichts (kein Einsatz, kein Projekt, der Termin
                 bleibt frei), dieselben Ablehnungen (404, 409); die Termine am Gerät tragen „privat“
    Seite        der Termin ist ein Knopf; der Dialog zeigt ihn, den Knopf zur Übernahme nur bei einem Einzeltermin; die Übernahme öffnet „Einsatz planen“
                 als Kranvermietung mit dem Termin, dem Gerät, seinen Tagen und dem Titel als Notiz (nicht bei einem privaten); geschickt wird nur, was
                 die Übernahme nimmt
Im Browser: scripts/klicktest_plantafel_kran_termin.py.
"""

import json
from datetime import timedelta

from sqlalchemy import func, select

from app.main import create_customer
from app.models import CalendarEvent, PlanningSlot, Project
from app.planning import geraete_termine
from app.schemas import CustomerCreate
from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v563_konflikte_beim_speichern import MONTAG
from tests.test_v579_geraete_postfach import welt  # noqa: F401  (Fixture)
from tests.test_v641_kran_kalender import _einsatz


def _anlegen(w, titel="Anfrage Müller", von="2026-11-10T08:00:00", bis="2026-11-11T16:00:00", **mehr):
    r = w.client.post("/api/calendar-events", json={"title": titel, "start_at": von, "end_at": bis, "resource_id": w.kran.id, **mehr})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _zaehlen(w):
    w.db.expire_all()
    return [w.db.scalar(select(func.count()).select_from(m)) for m in (PlanningSlot, Project, CalendarEvent)]


def test_pruefen_wie_uebernehmen_ohne_spuren(welt):  # noqa: F811
    kunde = create_customer(CustomerCreate(last_name="Meier"), welt.db)
    termin = _anlegen(welt)
    vorher = _zaehlen(welt)
    r = welt.client.post(f"/api/planning/kran-termine/{termin}/pruefen", json={"customer_id": kunde.id})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["warnungen"] == []  # der eigene Termin warnt nicht gegen sich selbst
    assert [(g["id"], g["gewaehlt"], g["tage_text"]) for g in p["geraete"]] == [(welt.kran.id, True, "alle Tage")]
    assert _zaehlen(welt) == vorher and welt.db.get(CalendarEvent, termin).planning_slot_id is None  # nichts geschrieben
    # danach übernimmt dieselbe Anfrage (die Sperre der Vorschau ist frei)
    r = welt.client.post(f"/api/planning/kran-termine/{termin}/kranvermietung", json={"customer_id": kunde.id, "travel_hours_per_employee_day": "0.5"})
    assert r.status_code == 200 and (r.json()["start_date"], r.json()["end_date"], r.json()["notes"]) == ("2026-11-10", "2026-11-11", "Anfrage Müller"), r.text
    assert str(r.json()["travel_hours_per_employee_day"]) in ("0.5", "0.50")  # seit 1.9.251 nimmt die Übernahme die Anfahrt an


def test_pruefen_warnt_wie_uebernehmen_und_lehnt_ab_wie_uebernehmen(welt):  # noqa: F811
    kunde = create_customer(CustomerCreate(last_name="Meier"), welt.db)
    _einsatz(welt, von=9, bis=9)  # der Kran an einer Baustelle am 11.11.
    termin = _anlegen(welt)
    r = welt.client.post(f"/api/planning/kran-termine/{termin}/pruefen", json={"customer_id": kunde.id})
    assert r.status_code == 200 and [w["type"] for w in r.json()["warnungen"]] == ["resource"], r.text
    assert welt.client.post("/api/planning/kran-termine/99999/pruefen", json={"customer_id": kunde.id}).status_code == 404
    konto = welt.client.post("/api/calendar-events", json={"title": "Besprechung", "start_at": "2026-11-04T09:00:00", "end_at": "2026-11-04T10:00:00",
                                                           "owner_user_id": welt.anna.id}).json()
    assert welt.client.post(f"/api/planning/kran-termine/{konto['id']}/pruefen", json={"customer_id": kunde.id}).status_code == 409
    frei = _anlegen(welt, titel="Anruf", von="2026-11-05T09:00:00", bis="2026-11-05T10:00:00")
    assert welt.client.post(f"/api/planning/kran-termine/{frei}/kranvermietung", json={"customer_id": kunde.id}).status_code == 200
    r = welt.client.post(f"/api/planning/kran-termine/{frei}/pruefen", json={"customer_id": kunde.id})
    assert r.status_code == 409 and "schon zu einem Einsatz" in r.json()["detail"], r.text
    assert welt.client.post(f"/api/planning/kran-termine/{termin}/pruefen", json={}).status_code == 422  # ohne Kunde und Auftrag


def test_termine_am_geraet_tragen_privat(welt):  # noqa: F811
    _anlegen(welt, titel="Geheim", von="2026-11-04T09:00:00", bis="2026-11-04T10:00:00", is_private=True)
    _anlegen(welt, titel="Offen", von="2026-11-05T09:00:00", bis="2026-11-05T10:00:00")
    termine = geraete_termine(welt.db, {welt.kran.id}, MONTAG, MONTAG + timedelta(days=13))
    assert [(t["titel"], t["privat"]) for t in termine] == [("Belegt", True), ("Offen", False)]


@nur_mit_node
def test_dialog_des_termins_und_uebernahme():
    termine = [{"id": 5, "resource_id": 3, "titel": "Anfrage Müller", "von": "2026-11-10", "bis": "2026-11-11", "zeit": "08:00", "uebernehmbar": True, "privat": False},
               {"id": 6, "resource_id": 3, "titel": "Belegt", "von": "2026-11-12", "bis": "2026-11-12", "zeit": None, "uebernehmbar": True, "privat": True},
               {"id": 7, "resource_id": 3, "titel": "Wartung", "von": "2026-11-13", "bis": "2026-11-13", "zeit": "09:00", "uebernehmbar": False, "privat": False}]
    vorbereitung = (f"var board = {{geraete_termine: {json.dumps(termine)}, resources: [{{id: 3, name: 'Kran'}}]}}; var geoeffnet = []; "
                    "var terminDialog = {showModal() { this.offen = true; }, close() { this.offen = false; }}; function openCreate(...a) { geoeffnet.push(a); }")
    ablauf = ("const stand = () => [document.getElementById('tdText').textContent, document.getElementById('tdZeit').textContent, !!document.getElementById('tdUebernehmen').hidden];"
              "terminZeigen(5); const a = stand(); terminUebernehmen(); terminZeigen(6); terminUebernehmen(); terminZeigen(7); const c = stand(); terminUebernehmen();"
              "AUFRUFE.push({a, c, geoeffnet, offen: terminDialog.offen});")
    [erg] = [x for x in im_browser("planning.html", ["terminZeigen", "terminUebernehmen", "fmtSpanne", "fmt"], vorbereitung, ablauf) if "a" in x]
    assert erg["a"] == ["Anfrage Müller", "10.–11.11. · ab 08:00", False]
    assert erg["c"] == ["Wartung", "13.11. · ab 09:00", True]  # Termin einer Serie: kein Knopf
    mehr = lambda tid, titel, bis, notiz: {"art": "kranvermietung", "kran_termin_id": tid, "termin": {"titel": titel},  # noqa: E731
                                           "geraete": [{"resource_id": 3, "tage": None}], "bis": bis, "notes": notiz}
    assert erg["geoeffnet"] == [[None, "2026-11-10", None, mehr(5, "Anfrage Müller", "2026-11-11", "Anfrage Müller")],
                                [None, "2026-11-12", None, mehr(6, "Belegt", "2026-11-12", "")]]  # privat: keine Notiz; der Serientermin öffnet nichts
    assert erg["offen"] is True


@nur_mit_node
def test_aus_dem_termin_nur_was_die_uebernahme_nimmt():
    vorbereitung = "var einsatz = {termin: {titel: 'x'}};"
    ablauf = ("AUFRUFE.push({w: terminWerte({art: 'kranvermietung', customer_id: 4, titel: null, employee_ids: [2], geraete: [{resource_id: 3}], "
              "start_date: '2026-11-10', end_date: '2026-11-11', status: 'vorlaeufig', notes: 'n', planned_hours: null, travel_hours_per_employee_day: 0, kran_termin_id: 5})});"
              "einsatz = {termin: null}; AUFRUFE.push({ohne: terminWerte({art: 'baustelle', start_date: 'x'})});")
    erg = [x for x in im_browser("planning.html", ["terminWerte"], vorbereitung, ablauf) if "w" in x or "ohne" in x]
    assert erg[0]["w"] == {"customer_id": 4, "titel": None, "employee_ids": [2], "status": "vorlaeufig", "notes": "n", "planned_hours": None,
                           "travel_hours_per_employee_day": 0}
    assert erg[1]["ohne"] == {"art": "baustelle", "start_date": "x"}  # ohne Termin unverändert
