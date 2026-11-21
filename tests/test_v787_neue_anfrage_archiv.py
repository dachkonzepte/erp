"""Version 1.10.16 (Antwort F4 vom 21.11.2026): „Neue Anfrage“ zeigt Kunden im Archiv in einer eigenen Gruppe; gewählt nur über „Zurückholen und wählen“.

    Auswahl      „Neue Anfrage“: die aktiven Kunden, darunter die Gruppe „im Archiv“ mit „(im Archiv seit TT.MM.JJJJ)“; „Bearbeiten“ einer Anfrage ohne Archiv
    Wahl         ein Kunde im Archiv wird nicht gewählt -- die Auswahl springt zurück, darunter „Zurückholen und wählen“ und „Abbrechen“
    Zurückholen  POST /api/aufbewahrung/kunde/{id}/zurueckholen (jedes Büro), Liste neu, der Kunde gewählt; der Server nimmt weiter keine Anfrage an einem
                 Kunden im Archiv (409)
"""

import json

import pytest

from app.routers import aufbewahrung as aufbewahrung_router
from app.routers import inquiries as anfragen_router
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.test_v782_archiv import Welt

AKTIV = {"id": 1, "customer_number": "K-1", "name": "Erika Aktiv", "contact_person": None, "archiviert_am": None}
ARCHIV = {"id": 9, "customer_number": "K-9", "name": '<img src=x onerror="alert(1)">', "contact_person": None, "archiviert_am": "2026-11-20T23:30:00"}
ANTWORTEN = {"/api/customers?archivierte=true": [AKTIV, ARCHIV], "/api/properties": [], "/api/inquiries": []}


def _lauf(ablauf, antworten=None):
    return im_browser(seite("inquiries.html", "\ninit();"), "await loadAll();" + ablauf, antworten or ANTWORTEN)


@nur_mit_node
def test_gruppe_im_archiv_nur_bei_neuer_anfrage():
    neu, bearbeiten = _lauf("return [_element('newCustomer').innerHTML, _element('editCustomer').innerHTML];")["ergebnis"]
    assert neu.index('<option value="1">') < neu.index('<optgroup label="im Archiv">') < neu.index('<option value="9">')
    assert "(im Archiv seit 21.11.2026)" in neu and "<img" not in neu and "&lt;img" in neu
    assert '<option value="9">' not in bearbeiten and "im Archiv" not in bearbeiten


@nur_mit_node
def test_kunde_im_archiv_wird_nicht_gewaehlt():
    ablauf = ("const s = _element('newCustomer'); s.value = '1'; neuerKundeGewaehlt(); s.value = '9'; neuerKundeGewaehlt();"
              "return [s.value, _element('newArchivHinweis').hidden, _element('newArchivText').textContent];")
    wert, verborgen, text = _lauf(ablauf)["ergebnis"]
    assert (wert, verborgen) == ("1", False)
    assert text.startswith("K-9 · ") and "ist im Archiv seit 21.11.2026 – für eine neue Anfrage erst zurückholen." in text


@nur_mit_node
def test_abbrechen():
    ablauf = ("_element('newCustomer').value = '9'; neuerKundeGewaehlt(); _dkAktionen.click['kunde-archiv-abbrechen']();"
              "return [_element('newArchivHinweis').hidden, neuArchivKunde];")
    assert _lauf(ablauf)["ergebnis"] == [True, None]


@nur_mit_node
def test_zurueckholen_und_waehlen():
    zurueck = {**ARCHIV, "archiviert_am": None}
    ablauf = ("_element('newCustomer').value = '9'; neuerKundeGewaehlt();"
              f"ANTWORTEN['/api/customers?archivierte=true'] = {json.dumps([AKTIV, zurueck])};"
              "await _dkAktionen.click['kunde-zurueckholen-waehlen']();"
              "return [_element('newCustomer').value, _element('newArchivHinweis').hidden, _element('createStatus').textContent, kundenArchiv.length];")
    lauf = _lauf(ablauf)
    assert lauf["ergebnis"] == ["9", True, "Kunde zurückgeholt und gewählt – die 6 Monate zählen ab heute neu.", 0]
    posts = [a["url"] for a in lauf["aufrufe"] if a["methode"] == "POST"]
    assert posts == ["/api/aufbewahrung/kunde/9/zurueckholen"]


def test_server_nimmt_keine_anfrage_am_kunden_im_archiv(threaded_db_session, router_test_client):
    w = Welt(threaded_db_session)
    k = w.kunde(name="Zacharias Archiv")
    from datetime import datetime
    k.archiviert_am = datetime(2026, 11, 20, 9, 0)
    threaded_db_session.commit()
    c = router_test_client(threaded_db_session, anfragen_router.router, aufbewahrung_router.router, role="buero_auftrag")
    assert c.post("/api/inquiries", json={"customer_id": k.id, "title": "Neue Anfrage"}).status_code == 409
    assert c.post(f"/api/aufbewahrung/kunde/{k.id}/zurueckholen").status_code == 200
    assert c.post("/api/inquiries", json={"customer_id": k.id, "title": "Neue Anfrage"}).status_code == 200
