"""Version 1.9.279 (Stufe 6, R5c, Punkt 1): Auftragsliste der Woche und Zeitraum „1 Woche“.

    Zeilen     GET /api/planning/auftragsliste?start&end -- alle offenen Aufträge; mit Einsatz im Zeitraum oben nach ihrem ersten Tag im Zeitraum, darunter die
               übrigen nach Nummer; abgeschlossene und stornierte nicht
    Stunden    wie die Akte: „Soll …“, solange nichts gebucht ist, dann „Rest …“ (Soll minus gebuchte Baustelle & Werkstatt, darüber „… über Soll“); ohne Soll
               „nach Aufwand“, aus einem Wartungsvertrag „Wartungsvertrag“, Kranvermietung „Kran mit Bediener“ bzw. „Kran ohne Bediener“ (Antwort 10)
    Zusatz     eingeplant und ein Einsatz im Zeitraum vorläufig: „vorläufig“; sonst „ab <nächster Einsatz>“ oder „ohne Termin“; „pausiert“
    Abfragen   eine feste Zahl, unabhängig von Aufträgen und Einsätzen
    Zeitraum   „1 Woche“ in der Auswahl; jede Ansicht merkt sich ihren Zeitraum im Browser („Aufträge“ Start 1 Woche, sonst 2 Wochen, Antwort 15); die gezeigte
               Woche bleibt beim Wechsel; ändert sich die Zahl der Tage, lädt die Tafel neu
"""

import json
from datetime import timedelta
from decimal import Decimal

import pytest

from app.auftragsliste import auftragsliste, stunden_zeile
from app.models import Employee, ProjectProfile, TimeEntry
from app.planning import create_slot
from app.routers.planning import router as planning_router
from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v564_plantafel_leistung import MONTAG, Zaehler, _auftrag, _kolonne

D = Decimal
SONNTAG = MONTAG + timedelta(days=6)


@pytest.fixture()
def liste(threaded_db_session, router_test_client):
    db = threaded_db_session
    return {"db": db, "client": router_test_client(db, planning_router), "nord": _kolonne(db, "Nord")}


def _einsatz(w, order, von, bis, **mehr):
    return create_slot(w["db"], order_id=order.id, team_id=mehr.pop("team_id", w["nord"].id), start_date=MONTAG + timedelta(days=von),
                       end_date=MONTAG + timedelta(days=bis), planned_hours=D("1"), trotzdem_planen=True, **mehr)


def _zeilen(w):
    w["db"].expire_all()
    return {z["order_id"]: z for z in auftragsliste(w["db"], MONTAG, SONNTAG)}


def test_stunden_zeile():
    assert stunden_zeile(soll=D("8"), gebucht=D("0"), kran=None, wartungsvertrag=False) == "Soll 8,00 h"
    assert stunden_zeile(soll=D("8"), gebucht=D("2.5"), kran=None, wartungsvertrag=False) == "Rest 5,50 h"
    assert stunden_zeile(soll=D("8"), gebucht=D("10"), kran=None, wartungsvertrag=False) == "2,00 h über Soll"
    assert stunden_zeile(soll=D("0"), gebucht=D("3"), kran=None, wartungsvertrag=False) == "nach Aufwand"
    assert stunden_zeile(soll=D("8"), gebucht=D("0"), kran=None, wartungsvertrag=True) == "Wartungsvertrag"
    assert stunden_zeile(soll=D("0"), gebucht=D("0"), kran=True, wartungsvertrag=False) == "Kran mit Bediener"
    assert stunden_zeile(soll=D("0"), gebucht=D("0"), kran=False, wartungsvertrag=True) == "Kran ohne Bediener"


def test_alle_offenen_eingeplante_oben(liste):
    db = liste["db"]
    a, b, c, d = (_auftrag(db) for _ in range(4))
    zu, storno = _auftrag(db, status="abgeschlossen"), _auftrag(db, status="storniert")
    _einsatz(liste, a, 2, 4)  # Mi–Fr
    _einsatz(liste, b, -3, 0)  # Fr der Vorwoche bis Mo: ragt herein, erster Tag im Zeitraum Mo
    _einsatz(liste, c, 9, 10)  # nächste Woche
    zeilen = auftragsliste(db, MONTAG, SONNTAG)
    assert [z["order_id"] for z in zeilen] == [b.id, a.id, c.id, d.id]
    assert zu.id not in [z["order_id"] for z in zeilen] and storno.id not in [z["order_id"] for z in zeilen]
    z = {x["order_id"]: x for x in zeilen}
    assert (z[b.id]["eingeplant"], z[b.id]["erster_tag"]) == (True, MONTAG.isoformat())
    assert (z[c.id]["eingeplant"], z[c.id]["zusatz"], z[c.id]["naechster_einsatz"]) == (False, ["ab 11.11."], (MONTAG + timedelta(days=9)).isoformat())
    assert z[d.id]["zusatz"] == ["ohne Termin"]
    assert (z[a.id]["project_name"], z[a.id]["project_number"], z[a.id]["order_number"]) == (a.project.name, a.project.project_number, a.order_number)


def test_stunden_wie_die_akte(liste):
    db = liste["db"]
    a = _auftrag(db, minuten="60", menge="8")  # Soll 8 h
    ohne = _auftrag(db, minuten="0")
    assert _zeilen(liste)[a.id]["stunden"] == "Soll 8,00 h"
    emp = Employee(first_name="Tom", last_name="Test", employee_group="gewerblich", weekly_hours=D("40"), active=True)
    db.add(emp)
    db.flush()
    for art, h in (("site", "2.5"), ("workshop", "1"), ("travel", "3")):  # Fahrzeit zählt nicht (wie die Akte)
        db.add(TimeEntry(employee_id=emp.id, project_id=a.project_id, order_id=a.id, work_date=MONTAG, entry_type=art, hours=D(h), status="booked"))
    db.add(TimeEntry(employee_id=emp.id, project_id=a.project_id, order_id=a.id, work_date=MONTAG, entry_type="site", hours=D("4"), status="running"))
    db.commit()
    zeilen = _zeilen(liste)
    assert (zeilen[a.id]["stunden"], zeilen[a.id]["soll"], zeilen[a.id]["gebucht"]) == ("Rest 4,50 h", D("8.00"), D("3.50"))
    assert zeilen[ohne.id]["stunden"] == "nach Aufwand"


def test_vorlaeufig_und_pausiert(liste):
    db = liste["db"]
    a, b, c = _auftrag(db), _auftrag(db, status="pausiert"), _auftrag(db)
    _einsatz(liste, a, 1, 2, status="vorlaeufig")
    _einsatz(liste, b, 0, 0, status="fest")
    _einsatz(liste, c, 0, 0, status="fest")
    _einsatz(liste, c, 3, 3, status="vorlaeufig")  # einer von zweien vorläufig genügt
    z = _zeilen(liste)
    assert z[a.id]["zusatz"] == ["vorläufig"] and z[b.id]["zusatz"] == ["pausiert"] and z[c.id]["zusatz"] == ["vorläufig"]


def test_kran_und_wartungsvertrag(liste):
    db = liste["db"]
    from app.models import OperationalResource
    kran = OperationalResource(resource_number="K-1", resource_type="Kran", name="Kran", identifier="K-1", active=True)
    bediener = Employee(first_name="Lia", last_name="Lang", employee_group="gewerblich", weekly_hours=D("40"), active=True)
    db.add_all([kran, bediener])
    db.commit()
    mit, ohne, wartung = _auftrag(db), _auftrag(db), _auftrag(db)
    _einsatz(liste, mit, 4, 4, team_id=None, art="kranvermietung", geraete=[{"resource_id": kran.id}], employee_ids=[bediener.id])
    _einsatz(liste, ohne, 9, 9, team_id=None, art="kranvermietung", geraete=[{"resource_id": kran.id}])
    db.add(ProjectProfile(project_id=wartung.project_id, source_maintenance_contract_id=1))
    db.commit()
    z = _zeilen(liste)
    assert (z[mit.id]["stunden"], z[ohne.id]["stunden"], z[wartung.id]["stunden"]) == ("Kran mit Bediener", "Kran ohne Bediener", "Wartungsvertrag")


def test_feste_zahl_abfragen(liste):
    db, client = liste["db"], liste["client"]

    def abfragen():
        db.expire_all()
        with Zaehler(db) as z:
            r = client.get("/api/planning/auftragsliste", params={"start": MONTAG.isoformat(), "end": SONNTAG.isoformat()})
        assert r.status_code == 200, r.text
        return z.anzahl, len(r.json()["auftraege"])

    for _ in range(2):
        _einsatz(liste, _auftrag(db), 0, 1)
    wenig = abfragen()
    for n in range(8):
        o = _auftrag(db)
        _einsatz(liste, o, n % 5, n % 5)
        _einsatz(liste, o, 8, 9)
    viel = abfragen()
    assert (wenig[1], viel[1]) == (2, 10)
    assert wenig[0] == viel[0], (wenig, viel)


def test_api_und_rolle(liste, router_test_client):
    db, client = liste["db"], liste["client"]
    _auftrag(db)
    r = client.get("/api/planning/auftragsliste", params={"start": MONTAG.isoformat(), "end": SONNTAG.isoformat()})
    assert r.status_code == 200 and len(r.json()["auftraege"]) == 1
    zu_lang = client.get("/api/planning/auftragsliste", params={"start": MONTAG.isoformat(), "end": (MONTAG + timedelta(days=63)).isoformat()})
    assert zu_lang.status_code == 422
    monteurin = router_test_client(db, planning_router, role="field")
    assert monteurin.get("/api/planning/auftragsliste", params={"start": MONTAG.isoformat(), "end": SONNTAG.isoformat()}).status_code == 403


# --- Zeitraum je Ansicht (im Browser) --------------------------------------------------------------------------------------------------------

def _vorgaben() -> str:
    """Die Vorgaben wörtlich aus der Vorlage (const ZEITRAUM_SCHLUESSEL=…;) -- damit der Test den Code der Seite ausführt."""
    import re
    from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT
    treffer = re.search(r"const ZEITRAUM_SCHLUESSEL=[^\n]*?;", (ROOT / "app/templates/planning.html").read_text(encoding="utf-8"))
    assert treffer, "planning.html: const ZEITRAUM_SCHLUESSEL=… nicht gefunden -- Test anpassen"
    return treffer.group(0)


def _seite(speicher: dict | None, ablauf: str, *, wirft: bool = False) -> list:
    vorbereitung = (
        f"var SPEICHER = {json.dumps(speicher or {})}; var WIRFT = {'true' if wirft else 'false'}; var GELADEN = 0, GEZEICHNET = 0;"
        "var localStorage = {getItem(k){ if (WIRFT) throw new Error('kein Speicher'); return k in SPEICHER ? SPEICHER[k] : null; },"
        " setItem(k, v){ if (WIRFT) throw new Error('kein Speicher'); SPEICHER[k] = String(v); }};"
        "function loadBoard(){ GELADEN++; } function renderBoard(){ GEZEICHNET++; } var view = 'teams'; var AUFRUFE = AUFRUFE || [];"
        # seit 1.9.283 öffnet setView() in „Aufträge“ die Liste „Zum Einplanen“ (test_v683) -- hier nur, dass es sie gibt
        "function rueckstandZeigen(){} function rueckstandStartZu(){ return false; }"
        + _vorgaben() + "document.getElementById('rangeDays').value = '14';")
    # seit 1.9.282 schließt setView() die Leiste „Rückgängig“ über der Tafel (bandSchliessen)
    return im_browser("planning.html", ["zeitraumGemerkt", "zeitraumMerken", "setView", "tageAnzahl", "bandSchliessen"], vorbereitung, ablauf)


@nur_mit_node
def test_vorgaben_je_ansicht():
    assert _seite(None, "AUFRUFE.push([zeitraumGemerkt('teams'), zeitraumGemerkt('employees'), zeitraumGemerkt('auftraege')]);") == [[14, 14, 7]]


@nur_mit_node
def test_jede_ansicht_merkt_sich_ihren_zeitraum():
    [a, b] = _seite(None, "zeitraumMerken('teams', 21); AUFRUFE.push([zeitraumGemerkt('teams'), zeitraumGemerkt('auftraege'), SPEICHER.plantafel_zeitraum]);"
                          "zeitraumMerken('auftraege', 14); AUFRUFE.push([zeitraumGemerkt('teams'), zeitraumGemerkt('auftraege')]);")
    assert a == [21, 7, '{"teams":21}'] and b == [21, 14]
    assert _seite({"plantafel_zeitraum": '{"teams": 99}'}, "AUFRUFE.push(zeitraumGemerkt('teams'));") == [14]  # ein unbekannter Wert gilt nicht
    assert _seite(None, "zeitraumMerken('teams', 21); AUFRUFE.push(zeitraumGemerkt('teams'));", wirft=True) == [14]  # ohne Speicher die Vorgabe


@nur_mit_node
def test_wechsel_laedt_nur_bei_anderer_zahl_der_tage():
    [gleich, anders] = _seite({"plantafel_zeitraum": '{"employees": 14, "auftraege": 7}'},
                              "setView('employees'); AUFRUFE.push([GELADEN, GEZEICHNET, tageAnzahl()]);"
                              "setView('auftraege'); AUFRUFE.push([GELADEN, GEZEICHNET, tageAnzahl()]);")
    assert gleich == [0, 1, 14] and anders == [1, 1, 7]


def test_auswahl_mit_einer_woche_und_merken():
    from tests.test_v671_inaktive_mitarbeiter_ausblenden import ROOT
    text = (ROOT / "app/templates/planning.html").read_text(encoding="utf-8")
    assert '<select id="rangeDays" aria-label="Zeitraum"><option value="7">1 Woche</option><option value="14">2 Wochen</option>' in text
    assert "document.getElementById('rangeDays').addEventListener('change',()=>{zeitraumMerken(view,tageAnzahl());loadBoard()});" in text
    assert "document.getElementById('rangeDays').value=String(zeitraumGemerkt(view));" in text  # vor dem ersten Laden
