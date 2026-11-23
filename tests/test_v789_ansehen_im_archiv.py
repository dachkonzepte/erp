"""Version 1.10.18 (Antwort F7 vom 21.11.2026): Treffer im Archiv zusätzlich „ansehen“ -- nur lesen, ohne Zurückholen, die 6 Monate laufen nicht neu.

    Suche        je Treffer im Archiv „ansehen“ (Link auf die Seite) und „Zurückholen und öffnen“ (test_v786)
    Seiten       Kundenakte (seit 1.10.12), Akte, Objekt und Angebot sagen „im Archiv“; die Akte holt zurück, Objekt und Angebot verweisen auf Kundenakte
                 bzw. Akte; eine Anfrage im Archiv zeigt /inquiries?inquiry= als Lese-Ansicht mit „Zurückholen“; die Kundenakte verlinkt sie („ansehen“)
    nur lesen    Ansehen schreibt nichts: archiviert_am und zurueckgeholt_am bleiben (kein GET schreibt, Regel 23)
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.models import Customer, Inquiry, Project, Property, Quote
from app.routers import customers as kunden_router
from app.routers import inquiries as anfragen_router
from app.routers import projects as projekte_router
from app.routers import properties as objekte_router
from app.routers import quotes as angebote_router
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.test_v782_archiv import Welt

ROOT = Path(__file__).resolve().parent.parent
IM_ARCHIV = datetime(2026, 11, 20, 23, 30)
BOESE = '<img src=x onerror="alert(1)">'


@pytest.fixture
def welt(threaded_db_session):
    w = Welt(threaded_db_session)
    db = w.db
    w.alt = w.kunde(name="Zacharias Archiv")
    w.anfrage_alt = w.anfrage(w.alt)
    w.projekt_alt = w.projekt(w.alt)
    w.aktiv = w.kunde(name="Zora Aktiv")
    w.projekt_aktiv = w.projekt(w.aktiv)
    w.projekt_mit_auftrag = w.projekt(w.aktiv)
    w.auftrag(w.projekt_mit_auftrag)
    w.projekt_mit_auftrag.archived = True  # von Hand archiviert, mit Auftrag: nicht im Archiv der Aufbewahrung
    for p in (w.projekt_alt, w.projekt_aktiv, w.projekt_mit_auftrag):
        db.add(Quote(project_id=p.id, quote_number=f"A-{p.id}", title="Dach", status="versendet"))
    db.flush()
    # seit 1.10.23 (Archivschutz): erst anlegen, dann ins Archiv -- an einem Vorgang im Archiv entsteht nichts mehr
    w.alt.archiviert_am = w.anfrage_alt.archiviert_am = IM_ARCHIV
    w.projekt_alt.archived, w.projekt_alt.archiviert_am = True, IM_ARCHIV
    db.commit()
    w.angebote = {q.project_id: q.id for q in db.query(Quote).all()}
    w.objekt_alt = db.query(Property).filter(Property.customer_id == w.alt.id).one()
    w.objekt_aktiv = db.query(Property).filter(Property.customer_id == w.aktiv.id).one()
    return w


def _c(welt, router_test_client):
    return router_test_client(welt.db, kunden_router.router, anfragen_router.router, projekte_router.router, objekte_router.router,
                              angebote_router.router, role="buero_auftrag")


def test_seiten_erfahren_das_archiv(welt, router_test_client):
    c = _c(welt, router_test_client)
    assert c.get(f"/api/properties/{welt.objekt_alt.id}").json()["kunde_im_archiv"] is True
    assert c.get(f"/api/properties/{welt.objekt_aktiv.id}").json()["kunde_im_archiv"] is False
    p = c.get(f"/api/projects/{welt.projekt_alt.id}").json()
    assert (p["archived"], p["order_count"], p["archiviert_am"].startswith("2026-11-20T23:30")) == (True, 0, True)
    assert c.get(f"/api/projects/{welt.projekt_aktiv.id}").json()["archiviert_am"] is None
    imarchiv = {pid: c.get(f"/api/quotes/{qid}").json()["projekt_im_archiv"] for pid, qid in welt.angebote.items()}
    assert imarchiv == {welt.projekt_alt.id: True, welt.projekt_aktiv.id: False, welt.projekt_mit_auftrag.id: False}
    a = c.get(f"/api/inquiries/{welt.anfrage_alt.id}").json()
    assert a["archiviert_am"].startswith("2026-11-20T23:30")


def test_ansehen_schreibt_nichts(welt, router_test_client):
    c = _c(welt, router_test_client)
    for url in (f"/api/customers/{welt.alt.id}", f"/api/properties/{welt.objekt_alt.id}", f"/api/projects/{welt.projekt_alt.id}",
                f"/api/quotes/{welt.angebote[welt.projekt_alt.id]}", f"/api/inquiries/{welt.anfrage_alt.id}"):
        assert c.get(url).status_code == 200, url
    db = welt.db
    db.expire_all()
    for zeile in (db.get(Customer, welt.alt.id), db.get(Inquiry, welt.anfrage_alt.id), db.get(Project, welt.projekt_alt.id)):
        assert (zeile.archiviert_am, zeile.zurueckgeholt_am) == (IM_ARCHIV, None)
    assert db.get(Project, welt.projekt_alt.id).archived is True


def test_seiten_haben_den_hinweis():
    akte = (ROOT / "app" / "templates" / "akte.html").read_text(encoding="utf-8")
    assert 'id="archivHinweis"' in akte and "el('archivHinweis').hidden=!(project.archived&&!(project.order_count>0))" in akte
    assert "api(url,{method:'POST'}),{neuLaden:projektLaden}" in akte and "`/api/aufbewahrung/projekt/${Number(projectId)}/zurueckholen`" in akte
    objekt = (ROOT / "app" / "templates" / "property.html").read_text(encoding="utf-8")
    assert "document.getElementById('archivHinweis').hidden=!geladen.kunde_im_archiv" in objekt and "'/customers/'+Number(geladen.customer_id)" in objekt
    angebot = (ROOT / "app" / "templates" / "quote_editor.html").read_text(encoding="utf-8")
    assert "document.getElementById('archivHinweis').hidden=!quote.projekt_im_archiv" in angebot and "if(calendarModuleEnabled)renderCalendarEvents();archivHinweisZeigen()}" in angebot
    kunde = (ROOT / "app" / "templates" / "customer.html").read_text(encoding="utf-8")
    assert 'href="/inquiries?inquiry=${Number(i.id)}">im Archiv – ansehen</a>' in kunde


ARCHIVIERT = {"id": 7, "inquiry_number": "AN-7", "title": BOESE, "customer_id": 3, "customer_name": "Zacharias Archiv", "property_id": None,
              "property_name": "Hauptadresse", "property_address": "Musterweg 1, 12345 Musterstadt", "project_id": None, "project_number": None,
              "description": "Rinne tropft\nseit Montag", "status": "neu", "priority": "normal", "source": "Telefon", "contact_person": None,
              "assigned_to": None, "visit_at": None, "follow_up_at": None, "lost_reason": None, "webseite_nummer": None, "webanfrage_id": None,
              "archiviert_am": "2026-11-20T23:30:00", "created_at": "2026-03-01T09:00:00", "updated_at": "2026-03-01T09:00:00"}
LEER = {"/api/customers?archivierte=true": [], "/api/properties": [], "/api/inquiries": []}


@nur_mit_node
def test_anfrage_im_archiv_als_lese_ansicht():
    ablauf = ("await loadAll(); await archivAnsichtLaden(7);"
              "return [_element('archivAnsicht').hidden,_element('archivTitel').textContent,_element('archivSeitText').textContent,"
              "_element('archivAngaben').kinder.map(k=>k.textContent),_element('editorCard').classList.contains('hidden')];")
    verborgen, titel, seit, angaben, editor_zu = im_browser(seite("inquiries.html", "\ninit();"), ablauf, {**LEER, "/api/inquiries/7": ARCHIVIERT})["ergebnis"]
    assert verborgen is False and titel == f"AN-7 · {BOESE}"  # textContent: kein HTML
    assert seit.startswith("Im Archiv seit 21.11.2026 – nur zum Ansehen, die 6 Monate laufen dabei nicht neu.")
    assert angaben[:4] == ["Kunde", "Zacharias Archiv", "Objekt", "Hauptadresse · Musterweg 1, 12345 Musterstadt"]
    assert "Anfrage / Notizen" in angaben and "Rinne tropft\nseit Montag" in angaben


@nur_mit_node
def test_aktive_anfrage_keine_lese_ansicht():
    ablauf = "await loadAll(); await archivAnsichtLaden(7); return _element('archivAnsicht').hidden===false;"
    assert im_browser(seite("inquiries.html", "\ninit();"), ablauf, {**LEER, "/api/inquiries/7": {**ARCHIVIERT, "archiviert_am": None}})["ergebnis"] is False


@nur_mit_node
def test_lese_ansicht_holt_zurueck():
    ablauf = ("await loadAll(); await archivAnsichtLaden(7);"
              f"ANTWORTEN['/api/inquiries'] = {json.dumps([{**ARCHIVIERT, 'archiviert_am': None}])};"
              "let geoeffnet = null; openInquiry = id => { geoeffnet = id; };"  # der Editor selbst braucht mehr DOM als die Attrappe
              "await _dkAktionen.click['anfrage-zurueckholen']();"
              "return [_element('archivAnsicht').hidden, geoeffnet, _element('editStatusMsg').textContent];")
    lauf = im_browser(seite("inquiries.html", "\ninit();"), ablauf, {**LEER, "/api/inquiries/7": ARCHIVIERT})
    assert lauf["ergebnis"] == [True, 7, "Zurückgeholt – die 6 Monate zählen ab heute neu."]
    assert [a["url"] for a in lauf["aufrufe"] if a["methode"] == "POST"] == ["/api/aufbewahrung/anfrage/7/zurueckholen"]
