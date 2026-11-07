"""Version 1.9.155 (Stufe 6, R1 Nachrunde, Punkt 6, Befund L6): kein „Einsatz planen“, das ins Leere führt.

    Akte       am abgeschlossenen oder stornierten Auftrag kein Link und keine Hauptaktion, stattdessen der Grund; am laufenden und pausierten bleiben sie
    Adresse    /planning?auftrag=<geschlossen>: kein Dialog, der Grund vom Server; unbekannt: Meldung; offen: der Dialog
    Speichern  ohne gewählten Auftrag: Meldung statt „Auftrag wurde nicht gefunden.“ ; am geschlossenen Auftrag weiter 409 mit dem Grund
"""

import json
import re

import pytest

from app.akte import ausfuehrung, hauptaktion
from app.auftragsstatus import EINSATZ_GESPERRT, einsatz_gesperrt, status_aendern
from app.main import create_team
from app.orders import load_order
from app.routers.planning import router as planning_router
from app.schemas import TeamCreate
from tests.node_lauf import node_lauf
from tests.test_v090_planning_board import setup_order
from tests.vorlagen_js import TEMPLATES

AUSLOESER = {"storniert": "Kunde abgesprungen", "abgeschlossen": "ohne Rechnung", "pausiert": "Gerüst fehlt"}


def _geschlossen(db, status):
    order = setup_order(db, status)
    status_aendern(db, order.id, status, AUSLOESER[status])
    db.commit()
    return load_order(db, order.id)


@pytest.mark.parametrize("status", ["abgeschlossen", "storniert"])
def test_akte_nennt_den_grund(threaded_db_session, status):
    db = threaded_db_session
    daten = ausfuehrung(db, _geschlossen(db, status))
    assert daten["einsatz_gesperrt"] == EINSATZ_GESPERRT[status]


def test_akte_laufend_und_pausiert_ohne_sperre(threaded_db_session):
    db = threaded_db_session
    assert ausfuehrung(db, setup_order(db, "laeuft"))["einsatz_gesperrt"] is None
    assert ausfuehrung(db, _geschlossen(db, "pausiert"))["einsatz_gesperrt"] is None


@pytest.mark.parametrize("phase", ["auftrag", "ausfuehrung"])
def test_hauptaktion_am_geschlossenen_auftrag_nicht(phase):
    """Die Hauptaktion nannte es schon vorher nicht -- dass das so bleibt."""
    assert hauptaktion(phase, hat_angebot=True, verweigert=False, geschlossen=True, geld=False) is None
    assert hauptaktion(phase, hat_angebot=True, verweigert=False, geschlossen=False, geld=False)["text"] == "Einsatz planen"


@pytest.mark.parametrize("status", ["abgeschlossen", "storniert"])
def test_grund_vom_server_und_gleiche_meldung_wie_beim_speichern(threaded_db_session, router_test_client, status):
    db = threaded_db_session
    order = _geschlossen(db, status)
    client = router_test_client(db, planning_router, role="buero_auftrag")
    antwort = client.get(f"/api/planning/auftraege/{order.id}")
    assert antwort.status_code == 200
    assert antwort.json() == {"id": order.id, "order_number": order.order_number, "gesperrt": EINSATZ_GESPERRT[status]}

    team = create_team(TeamCreate(team_number="A", name="Kolonne A", employees=[], resources=[]), db)
    speichern = client.post("/api/planning/slots", json={"order_id": order.id, "team_id": team.id, "start_date": "2026-11-02", "end_date": "2026-11-02"})
    assert speichern.status_code == 409 and speichern.json()["detail"] == EINSATZ_GESPERRT[status]


def test_offener_auftrag_ohne_grund_und_unbekannter_404(threaded_db_session, router_test_client):
    db = threaded_db_session
    client = router_test_client(db, planning_router)
    assert client.get(f"/api/planning/auftraege/{setup_order(db, '1').id}").json()["gesperrt"] is None
    antwort = client.get("/api/planning/auftraege/999999")
    assert antwort.status_code == 404 and antwort.json()["detail"] == "Auftrag wurde nicht gefunden."


def test_monteurin_403(threaded_db_session, router_test_client):
    db = threaded_db_session
    assert router_test_client(db, planning_router, role="field").get(f"/api/planning/auftraege/{setup_order(db, '1').id}").status_code == 403


def test_einsatz_gesperrt_laufend_none():
    class Auftrag:
        status = "laeuft"
    assert einsatz_gesperrt(Auftrag()) is None


def test_akte_versteckt_den_link_nach_dem_server():
    text = (TEMPLATES / "akte.html").read_text(encoding="utf-8")
    assert "el('einsatzLink').hidden=!!a.einsatz_gesperrt" in text
    assert 'id="einsatzGesperrt" hidden' in text


def _plantafel(ausdruck, orders="[]", antworten="{}"):
    """openCreate(), fehltBezug() und einsatzSpeichern() in node, die übrige Seite als Attrappe -- seit 1.9.248 der Einsatz-Dialog (bis 1.9.247
    createDialog und saveNew())."""
    from tests.test_v399_teil_updates_geld import js_funktion
    teile = [js_funktion("planning.html", name) for name in ("einsatzGesperrt", "openCreate", "fehltBezug", "einsatzSpeichern")]
    return node_lauf("""
const felder={};
const document={getElementById:i=>felder[i]||(felder[i]={value:'',innerHTML:'',textContent:''})};
let geoeffnet=false;const einsatzDialog={showModal(){geoeffnet=true},close(){}};
const esc=s=>String(s);const board={settings:{},teams:[]};const periodStart='2026-11-02';const iso=x=>x;const addDays=x=>x;
const selectedBacklog=()=>null;const dialogFuellen=()=>{};const kundenLaden=async()=>{};const pruefenJetzt=()=>{};const felderLesen=()=>true;
let einsatz=null,geaendert=null,weiterePersonen=[],weitereGeraete=[],pruefung=null,pruefungFuer=null,pruefenZeit=null;
let orders=[];const ANTWORTEN=""" + antworten + """;const GESENDET=[];
const api=async (u,o)=>{if(o&&o.method)GESENDET.push(u);if(u==='/api/planning/auftraege')return """ + orders + """;if(ANTWORTEN[u])return ANTWORTEN[u];throw new Error('Auftrag wurde nicht gefunden.')};
const lesen=async (b,f,a)=>a(await f());const speichern=async (b,f)=>f();
""" + "\n".join(teile) + """
(async()=>{console.log(JSON.stringify(await (""" + ausdruck + """)()))})();
""").stdout.strip()


def test_geschlossener_auftrag_oeffnet_keinen_dialog_und_nennt_den_grund():
    aus = json.loads(_plantafel(
        "async()=>{await openCreate(7);return [geoeffnet,document.getElementById('einsatzHinweis').innerHTML]}",
        antworten=json.dumps({"/api/planning/auftraege/7": {"id": 7, "order_number": "AU-7", "gesperrt": EINSATZ_GESPERRT["abgeschlossen"]}})))
    assert aus[0] is False
    assert "Kein neuer Einsatz für AU-7" in aus[1] and EINSATZ_GESPERRT["abgeschlossen"] in aus[1]


def test_unbekannter_auftrag_meldet_sich():
    aus = json.loads(_plantafel("async()=>{await openCreate(8);return [geoeffnet,document.getElementById('einsatzHinweis').innerHTML]}"))
    assert aus[0] is False and "Auftrag wurde nicht gefunden." in aus[1]


def test_offener_auftrag_oeffnet_den_dialog():
    aus = json.loads(_plantafel("async()=>{await openCreate(9);return geoeffnet}", orders='[{"id":9,"order_number":"AU-9"}]'))
    assert aus is True


@pytest.mark.parametrize("orders, leeren, text", [("[]", False, "Es gibt keinen offenen Auftrag."), ('[{"id":9}]', True, "Bitte einen Auftrag wählen.")])
def test_speichern_ohne_auftrag_meldet_sich_vor_dem_senden(orders, leeren, text):
    """Seit 1.9.248 im Einsatz-Dialog: „+ Einsatz“ wählt den ersten offenen Auftrag vor; ohne Auftrag meldet sich das Speichern, ohne zu senden."""
    aus = json.loads(_plantafel("async()=>{await openCreate();" + ("einsatz.order_id=null;" if leeren else "")
                                + "await einsatzSpeichern();return [GESENDET,document.getElementById('edMeldung').textContent]}", orders=orders))
    assert aus == [[], text]


def test_pruefen_ohne_auftrag_meldet_sich_vor_der_anfrage():
    """Seit 1.9.248 prüft der Dialog bei jeder Änderung auf dem Server -- ohne Auftrag (bzw. bei einer Kranvermietung ohne Kunde) erst gar nicht:
    keine Anfrage, die Meldung, die alte Prüfung verworfen."""
    from tests.test_v399_teil_updates_geld import js_funktion
    teile = [js_funktion("planning.html", name) for name in ("fehltBezug", "pruefenJetzt")]
    aus = node_lauf("""
const felder={};const document={getElementById:i=>felder[i]||(felder[i]={value:'',innerHTML:'',textContent:''})};
const felderLesen=()=>true;const einsatzKopf=()=>{};const zustandZeichnen=()=>{};const einsatzWerte=()=>({});const GESENDET=[];
const api=async (u,o)=>{GESENDET.push(u);return {}};const speichern=async (b,f)=>f();
let pruefung={alt:true},pruefungFuer='alt',weiterePersonen=[],weitereGeraete=[],orders=[];let einsatz={id:null,art:'baustelle',order_id:null};
""" + "\n".join(teile) + """
(async()=>{await pruefenJetzt();const ohneAuftrag=[GESENDET.length,document.getElementById('edMeldung').textContent,pruefung,pruefungFuer];
einsatz={id:null,art:'kranvermietung',bezug:'kunde',customer_id:null};await pruefenJetzt();
console.log(JSON.stringify([ohneAuftrag,[GESENDET.length,document.getElementById('edMeldung').textContent]]))})();
""").stdout.strip()
    assert json.loads(aus) == [[0, "Es gibt keinen offenen Auftrag.", None, None], [0, "Bitte einen Kunden wählen."]]
