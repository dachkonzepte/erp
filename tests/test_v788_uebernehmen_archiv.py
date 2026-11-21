"""Version 1.10.17 (Antwort F4 vom 21.11.2026): Übernehmen einer Anfrage der Webseite -- Kunden im Archiv in einer eigenen Gruppe „im Archiv“.

    Vorschlag    dieselben Gründe (E-Mail, Telefon, Name, PLZ) -- die aktiven unter `kunden`, die im Archiv unter `kunden_archiv` (mit archiviert_am)
    Suche        „Anderen bestehenden Kunden wählen“: `kunden`/`anzahl` wie bisher, dazu `archiv`/`archiv_anzahl` (dieselbe Suche, nur das Archiv)
    Seite        im Archiv kein Auswahlknopf, nur „Zurückholen und wählen“: POST …/aufbewahrung/kunde/{id}/zurueckholen, Vorschlag und Suche neu, der
                 Kunde gewählt (seine Objekte geladen)
    Server       das Übernehmen nimmt weiter keinen Kunden im Archiv (404), seine Objekte ebenso nicht
"""

import json
from datetime import datetime

from sqlalchemy import select

from app.crm import kunde_anlegen
from app.models import WebAnfrage
from app.routers import aufbewahrung as aufbewahrung_router
from app.routers import inquiries as inquiries_router
from app.routers import webanfragen as router_modul
from app import webanfragen as W
from scripts.empfangsdienst_attrappe import muster
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.test_v447_auswahl_altwerte import WIRKSAM
from tests.test_v779_webanfragen_anderer_kunde import BOESE, NR, VORSCHLAG, dienst  # noqa: F401 (Fixture)

IM_ARCHIV = datetime(2026, 11, 20, 23, 30)


def _welt(dienst, db, router_test_client, anfrage):
    dienst.dazu(anfrage)
    assert W.abholen(db).neu == 1
    c = router_test_client(db, router_modul.router, inquiries_router.router, aufbewahrung_router.router, role="buero_auftrag", user_id=1)
    return c, db.scalar(select(WebAnfrage.id).where(WebAnfrage.nummer == NR))


def test_vorschlag_mit_gruppe_im_archiv(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    alt = kunde_anlegen(db, {"first_name": "Erika", "last_name": "Muster", "email": "erika@example.invalid"})
    neu = kunde_anlegen(db, {"first_name": "Erika", "last_name": "Muster"})
    alt.archiviert_am = IM_ARCHIV
    db.commit()
    c, i = _welt(dienst, db, router_test_client, muster(NR, name="Erika Muster", email="erika@example.invalid"))
    v = c.get(f"/api/webanfragen/{i}/vorschlag").json()
    assert [k["id"] for k in v["kunden"]] == [neu.id]
    assert [(k["id"], k["gruende"]) for k in v["kunden_archiv"]] == [(alt.id, ["E-Mail gleich", "Name gleich"])]
    assert v["kunden_archiv"][0]["archiviert_am"].startswith("2026-11-20T23:30")
    assert c.get(f"/api/webanfragen/{i}/objekte", params={"kunde_id": alt.id}).status_code == 404  # erst zurückholen
    r = c.post(f"/api/webanfragen/{i}/uebernehmen", json={"kunde_id": alt.id, "objekt": "keins", "titel": "x"})
    assert r.status_code == 404 and db.get(WebAnfrage, i).status == "neu"
    assert c.post(f"/api/aufbewahrung/kunde/{alt.id}/zurueckholen").status_code == 200
    v = c.get(f"/api/webanfragen/{i}/vorschlag").json()
    assert [k["id"] for k in v["kunden"]] == [alt.id, neu.id] and v["kunden_archiv"] == []
    assert c.post(f"/api/webanfragen/{i}/uebernehmen", json={"kunde_id": alt.id, "objekt": "keins", "titel": "x"}).status_code == 200


def test_suche_mit_gruppe_im_archiv(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    aktiv = kunde_anlegen(db, {"last_name": "Gründler Bau"})
    alt = kunde_anlegen(db, {"last_name": "Gründler Hausverwaltung"})
    alt.archiviert_am = IM_ARCHIV
    db.commit()
    c, i = _welt(dienst, db, router_test_client, muster(NR))
    r = c.get(f"/api/webanfragen/{i}/kunden", params={"suche": "grundler"}).json()
    assert ([k["id"] for k in r["kunden"]], r["anzahl"]) == ([aktiv.id], 1)
    assert ([k["id"] for k in r["archiv"]], r["archiv_anzahl"]) == ([alt.id], 1)
    assert r["archiv"][0]["archiviert_am"].startswith("2026-11-20T23:30") and r["kunden"][0]["archiviert_am"] is None
    assert c.get(f"/api/webanfragen/{i}/kunden", params={"suche": "g"}).json() == {"kunden": [], "anzahl": 0, "archiv": [], "archiv_anzahl": 0}


# --- Seite (node) -------------------------------------------------------------------------------------------------------------------------------

ARCHIVIERT = {"id": 9, "name": BOESE, "kundennummer": "K-9", "adresse": "Musterweg 1, 00000 Musterstadt", "gruende": ["E-Mail gleich"],
              "archiviert_am": "2026-11-20T23:30:00"}


def _seite():
    return seite("webanfrage.html", "\nlesen('anfrage',") + WIRKSAM


@nur_mit_node
def test_seite_gruppe_im_archiv_ohne_auswahlknopf():
    v = {**VORSCHLAG, "kunden_archiv": [ARCHIVIERT]}
    r = {"kunden": [], "anzahl": 0, "archiv": [ARCHIVIERT], "archiv_anzahl": 3}
    ablauf = (f"uebVorschlag={json.dumps(v)};uebZeichnen();uebTrefferZeichnen({json.dumps(r)});"
              "return [_element('uebKundenArchiv').innerHTML,_element('uebSucheArchiv').innerHTML,_element('uebSucheHinweis').textContent];")
    vorschlag, suche, hinweis = im_browser(_seite(), ablauf)["ergebnis"]
    for html, quelle in ((vorschlag, "vorschlag"), (suche, "suche")):
        assert html.startswith("<h4>im Archiv</h4>") and "radio" not in html and "<img" not in html and "&lt;img" in html
        assert f'data-klick="uebArchivZurueckholen" data-id="9" data-quelle="{quelle}"' in html and "im Archiv seit 21.11.2026" in html
    assert "E-Mail gleich" in vorschlag and "3 im Archiv, hier die ersten 1." in suche
    assert hinweis == "Kein aktiver Kunde gefunden – siehe „im Archiv“."


@nur_mit_node
def test_seite_ohne_archiv_keine_gruppe():
    ablauf = (f"uebVorschlag={json.dumps({**VORSCHLAG, 'kunden_archiv': []})};uebZeichnen();uebTrefferZeichnen({{kunden:[],anzahl:0}});"
              "return [_element('uebKundenArchiv').innerHTML,_element('uebSucheArchiv').innerHTML];")
    assert im_browser(_seite(), ablauf)["ergebnis"] == ["", ""]


@nur_mit_node
def test_seite_zurueckholen_und_waehlen():
    v = {**VORSCHLAG, "kunden_archiv": [ARCHIVIERT]}
    zurueck = {**VORSCHLAG, "kunden": [{**ARCHIVIERT, "archiviert_am": None}], "kunden_archiv": []}
    ablauf = (f"uebVorschlag={json.dumps(v)};uebZeichnen();"
              "_element('uebSucheText').value='';"
              f"ANTWORTEN['/api/webanfragen/1/vorschlag']={json.dumps(zurueck)};ANTWORTEN['/api/webanfragen/1/objekte?kunde_id=9']=[];"
              "const radio={value:'9',checked:false,dataset:{aenderung:'uebKundeWahl'}};"
              "document.querySelector=(sel)=>sel.includes('#uebKunden ')&&sel.includes('value=\"9\"')?radio:null;"
              "await _dkAktionen.click['uebArchivZurueckholen']({dataset:{id:'9',quelle:'vorschlag'}});"
              "return [radio.checked,uebKunde,_element('uebStatus').textContent,_element('uebKundenArchiv').innerHTML];")
    lauf = im_browser(_seite(), ablauf, {"/api/webanfragen/1/vorschlag": v})
    assert lauf["ergebnis"] == [True, "9", "Kunde zurückgeholt und gewählt – die 6 Monate zählen ab heute neu.", ""]
    aufrufe = [(a["methode"], a["url"]) for a in lauf["aufrufe"]]
    assert aufrufe.index(("POST", "/api/aufbewahrung/kunde/9/zurueckholen")) < aufrufe.index(("GET", "/api/webanfragen/1/vorschlag"))
    assert ("GET", "/api/webanfragen/1/objekte?kunde_id=9") in aufrufe
