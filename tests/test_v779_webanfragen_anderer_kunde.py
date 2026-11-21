"""Version 1.10.8 (Nachrunde W1b): „Anderen bestehenden Kunden wählen“ beim Übernehmen einer Anfrage der Webseite -- nur Musterdaten.

    Lücke     fand der Vorschlag den bestehenden Kunden nicht (neue E-Mail, neue Nummer, Name anders geschrieben), blieb nur „Neuer Kunde“ -- eine Dublette
    Suche     GET …/kunden?suche= -- dieselbe Kundensuche wie die Büro-Suche (app/search.py::kunden_suchen(): passt() auf Name und Kundennummer, Reihenfolge
              der Kundenliste), ab zwei Zeichen, höchstens 20 Treffer mit der Zahl aller; schreibt nichts; eine unbekannte Anfrage 404, eine Suche über 100
              Zeichen 422, die Monteurin 403; für jede Rolle der Anfrage, auch beim Mieter
    Danach    seine Objekte wie beim Vorschlag („Adresse gleich“); Übernehmen mit den Prüfungen von 1.10.5 (ein Objekt eines anderen Kunden 422, ein
              unbekannter Kunde 404 -- nichts angelegt)
    Seite     die Suche immer sichtbar, zwischen den Vorschlägen und „Neuer Kunde“; ein Treffer ist eine Wahl wie ein Vorschlag (dieselbe Radiogruppe, danach
              seine Objekte), nichts vorgewählt, jeder Wert über esc(); sucht das Büro weiter und der gewählte Treffer fehlt, ist die Auswahl aufgehoben
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import webanfragen as W
from app.crm import kunde_anlegen
from app.models import AuditLog, Customer, Inquiry, Property, WebAnfrage
from app.routers import inquiries as inquiries_router
from app.routers import webanfragen as router_modul
from app.search import search_office
from scripts.empfangsdienst_attrappe import Attrappe, muster
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.test_v447_auswahl_altwerte import WIRKSAM

ROOT = Path(__file__).resolve().parent.parent
BOESE = '<img src=x onerror="alert(1)">'
NR = "R-20261119-0910-0A1B"


@pytest.fixture
def dienst(monkeypatch, tmp_path):
    monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path / "daten"))
    monkeypatch.setenv("DACHKONZEPTE_PROPERTY_FILE_ROOT", str(tmp_path / "objekte"))
    import app.property_documents as pd
    monkeypatch.setattr(pd, "PROPERTY_ROOT", tmp_path / "objekte")
    with Attrappe() as a:
        monkeypatch.setenv(W.ADRESSE_VARIABLE, a.adresse)
        monkeypatch.setenv(W.SCHLUESSEL_VARIABLE, a.schluessel)
        yield a


def _welt(dienst, db, router_test_client, *anfragen, role="buero_auftrag"):
    for a in anfragen:
        dienst.dazu(a)
    assert W.abholen(db).neu == len(anfragen)
    c = router_test_client(db, router_modul.router, inquiries_router.router, role=role, user_id=1)
    ids = {z.nummer: z.id for z in db.scalars(select(WebAnfrage))}
    return c, ids


def _mieter():
    """Ein Mieter meldet, die Hausverwaltung schreibt er anders als im Kundenstamm -- der Vorschlag findet sie nicht."""
    return muster(NR, rolle="mieter", name="Mia Mieter", hausverwaltung="HV Gruendler", telefon="0000 333", email="mia@example.invalid", fotos=1)


def _anzahlen(db):
    db.expire_all()
    return tuple(db.scalar(select(func.count(m.id))) for m in (Customer, Property, Inquiry, AuditLog))


def test_suche_wie_die_buero_suche(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    hv = kunde_anlegen(db, {"last_name": "Hausverwaltung Gründler GmbH"})
    anna = kunde_anlegen(db, {"first_name": "Anna", "last_name": "Müller"})
    kunde_anlegen(db, {"first_name": "Bernd", "last_name": "Mullbach"})
    db.commit()
    c, ids = _welt(dienst, db, router_test_client, _mieter())
    i = ids[NR]
    assert c.get(f"/api/webanfragen/{i}/vorschlag").json()["kunden"] == []  # die Lücke: der Vorschlag findet die Hausverwaltung nicht
    vorher = _anzahlen(db)
    r = c.get(f"/api/webanfragen/{i}/kunden", params={"suche": "grundler"}).json()  # ü wie u -- wie im Telefonbuch
    assert (r["anzahl"], [k["id"] for k in r["kunden"]]) == (1, [hv.id])
    assert r["kunden"][0] == {"id": hv.id, "name": hv.name, "kundennummer": hv.customer_number, "adresse": None, "gruende": [],
                              "archiviert_am": None}  # archiviert_am seit 1.10.17
    r = c.get(f"/api/webanfragen/{i}/kunden", params={"suche": "MULL"}).json()
    buero = next(g for g in search_office(db, "buero_auftrag", "MULL", types=frozenset({"customers"})) if g["key"] == "customers")
    assert [k["id"] for k in r["kunden"]] == [h["id"] for h in buero["hits"]] and r["anzahl"] == buero["total"] == 2  # dieselbe Suche, dieselbe Reihenfolge
    assert c.get(f"/api/webanfragen/{i}/kunden", params={"suche": anna.customer_number}).json()["kunden"][0]["id"] == anna.id  # Kundennummer
    LEER = {"kunden": [], "anzahl": 0, "archiv": [], "archiv_anzahl": 0}  # archiv, archiv_anzahl seit 1.10.17
    assert c.get(f"/api/webanfragen/{i}/kunden", params={"suche": " m "}).json() == LEER  # ab zwei Zeichen
    assert c.get(f"/api/webanfragen/{i}/kunden", params={"suche": "%%"}).json() == LEER  # „%“ gilt wörtlich
    assert c.get(f"/api/webanfragen/{i}/kunden").json() == LEER
    assert c.get(f"/api/webanfragen/{i}/kunden", params={"suche": "x" * 101}).status_code == 422
    assert c.get("/api/webanfragen/999999/kunden", params={"suche": "mull"}).status_code == 404
    assert _anzahlen(db) == vorher  # schreibt nichts


def test_hoechstens_zwanzig_mit_der_zahl_aller(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    for n in range(23):
        kunde_anlegen(db, {"last_name": f"Musterkunde {n:02d}"})
    db.commit()
    c, ids = _welt(dienst, db, router_test_client, muster(NR))
    r = c.get(f"/api/webanfragen/{ids[NR]}/kunden", params={"suche": "musterkunde"}).json()
    assert (r["anzahl"], len(r["kunden"])) == (23, 20)
    assert [k["name"] for k in r["kunden"]] == [f"Musterkunde {n:02d}" for n in range(20)]


def test_mieter_uebernimmt_den_gefundenen_kunden(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    hv = kunde_anlegen(db, {"last_name": "Hausverwaltung Gründler GmbH"})
    haus = Property(customer_id=hv.id, name="Mietshaus", street="Musterweg 1", postal_code="00000", city="Musterstadt", site_contact_name="Hausmeister")
    db.add(haus)
    db.commit()
    c, ids = _welt(dienst, db, router_test_client, _mieter())
    i = ids[NR]
    gefunden = c.get(f"/api/webanfragen/{i}/kunden", params={"suche": "gründler"}).json()["kunden"]
    assert [k["id"] for k in gefunden] == [hv.id]
    objekte = c.get(f"/api/webanfragen/{i}/objekte", params={"kunde_id": hv.id}).json()
    assert [(o["id"], o["adresse_gleich"]) for o in objekte][0] == (haus.id, True)  # „Adresse gleich“ zuerst (dahinter die Hauptadresse des Kunden)
    kunden_vorher = db.scalar(select(func.count(Customer.id)))
    body = {"kunde_id": hv.id, "objekt": "gewaehlt", "objekt_id": haus.id, "titel": "Rinne", "vor_ort_uebernehmen": True}
    r = c.post(f"/api/webanfragen/{i}/uebernehmen", json=body)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.scalar(select(func.count(Customer.id))) == kunden_vorher  # keine Dublette
    inq = db.scalar(select(Inquiry).where(Inquiry.webseite_nummer == NR))
    assert (inq.customer_id, inq.property_id) == (hv.id, haus.id)
    haus = db.get(Property, haus.id)
    assert (haus.site_contact_name, haus.site_contact_phone) == ("Mia Mieter", "0000 333")
    hv = db.get(Customer, hv.id)
    assert (hv.email, hv.phone) == (None, None)  # Telefon und E-Mail des Mieters nie beim Kunden


def test_pruefungen_wie_beim_vorschlag(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    hv = kunde_anlegen(db, {"last_name": "Hausverwaltung Gründler GmbH"})
    andere = kunde_anlegen(db, {"last_name": "Fremd"})
    fremd = Property(customer_id=andere.id, name="Fremdes Haus")
    db.add(fremd)
    db.commit()
    c, ids = _welt(dienst, db, router_test_client, _mieter())
    i = ids[NR]
    assert [k["id"] for k in c.get(f"/api/webanfragen/{i}/kunden", params={"suche": "grundler"}).json()["kunden"]] == [hv.id]
    vorher = _anzahlen(db)
    r = c.post(f"/api/webanfragen/{i}/uebernehmen", json={"kunde_id": hv.id, "objekt": "gewaehlt", "objekt_id": fremd.id, "titel": "x"})
    assert r.status_code == 422 and r.json()["detail"] == "Das Objekt gehört nicht zum gewählten Kunden."
    assert c.post(f"/api/webanfragen/{i}/uebernehmen", json={"kunde_id": 999999, "objekt": "keins", "titel": "x"}).status_code == 404
    assert c.get(f"/api/webanfragen/{i}/objekte", params={"kunde_id": 999999}).status_code == 404
    assert _anzahlen(db) == vorher and db.get(WebAnfrage, i).status == "neu"


def test_monteurin_nicht(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    c, ids = _welt(dienst, db, router_test_client, muster(NR), role="field")
    assert c.get(f"/api/webanfragen/{ids[NR]}/kunden", params={"suche": "muster"}).status_code == 403


# --- Seite (node) -------------------------------------------------------------------------------------------------------------------------------

VORSCHLAG = {"rolle": "mieter", "auftraggeber": "A", "kunden": [], "kunde_neu": {"last_name": "HV", "is_consumer": None}, "objekt_neu": None,
             "vor_ort": {"name": "Mia", "telefon": None}, "ort_kontakt": None, "anfrage": {"titel": "T", "beschreibung": None, "ansprechpartner": None},
             "uebernehmen_moeglich": True}


def _seite():
    return seite("webanfrage.html", "\nlesen('anfrage',") + WIRKSAM


def test_suche_steht_zwischen_vorschlaegen_und_neuem_kunden():
    text = (ROOT / "app" / "templates" / "webanfrage.html").read_text(encoding="utf-8")
    a, b, c = text.index('id="uebKunden"'), text.index('id="uebSuche"'), text.index('id="uebKundeNeuWahl"')
    assert a < b < c
    kopf = text[b:text.index("</div>", b)]
    assert "hidden" not in kopf  # immer sichtbar


@nur_mit_node
def test_seite_ohne_vorschlag_suche_und_neuer_kunde():
    ablauf = (f"uebVorschlag={json.dumps(VORSCHLAG)};uebZeichnen();"
              "return [_element('uebKunden').innerHTML,_element('uebKundeNeuWahl').innerHTML,_element('uebSucheTreffer').innerHTML];")
    kunden, neu, treffer = im_browser(_seite(), ablauf)["ergebnis"]
    assert "Kein bestehender Kunde passt" in kunden and "radio" not in kunden
    assert 'value="neu"' in neu and "checked" not in neu and treffer == ""


@nur_mit_node
def test_seite_treffer_wie_ein_vorschlag():
    r = {"kunden": [{"id": 5, "name": BOESE, "kundennummer": BOESE, "adresse": BOESE, "gruende": []}], "anzahl": 30}
    ablauf = (f"uebVorschlag={json.dumps(VORSCHLAG)};uebZeichnen();uebTrefferZeichnen({json.dumps(r)});"
              "const erst=[_element('uebSucheTreffer').innerHTML,_element('uebSucheHinweis').textContent];"
              "uebKunde='5';uebKundeAusSuche=true;uebTrefferZeichnen(" + json.dumps(r) + ");const gewaehlt=_element('uebSucheTreffer').innerHTML;"
              "uebTrefferZeichnen({kunden:[],anzahl:0});"
              "return [erst,gewaehlt,uebKunde,uebKundeAusSuche,_element('uebObjekte').innerHTML,_element('uebSucheHinweis').textContent];")
    erst, gewaehlt, kunde, aus_suche, objekte, hinweis = im_browser(_seite(), ablauf)["ergebnis"]
    html, text_ = erst
    assert 'name="uebKunde"' in html and 'value="5"' in html and 'data-quelle="suche"' in html and 'data-aenderung="uebKundeWahl"' in html
    assert "checked" not in html and "<img" not in html and "&lt;img" in html  # nichts vorgewählt, jeder Wert über esc()
    assert text_ == "30 Treffer, hier die ersten 1 – bitte genauer suchen."
    assert "checked" in gewaehlt  # der gewählte Treffer bleibt gewählt, solange er unter den Treffern ist
    assert (kunde, aus_suche, objekte, hinweis) == (None, False, '<div class="muted small">Erst den Auftraggeber wählen.</div>', "Kein Kunde gefunden.")


@nur_mit_node
def test_seite_ohne_suchtext_ohne_anfrage():
    ablauf = ("uebTrefferZeichnen(null);return [_element('uebSucheTreffer').innerHTML,_element('uebSucheHinweis').textContent];")
    assert im_browser(_seite(), ablauf)["ergebnis"] == ["", "Name oder Kundennummer, ab zwei Zeichen – dieselbe Suche wie oben."]
