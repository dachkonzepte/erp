"""Version 1.10.5 (Stufe W1b): eine Anfrage der Webseite als Anfrage übernehmen -- nur Musterdaten, gegen die Attrappe des Empfangsdienstes.

    Vorschlag   nur aus den strukturierten Angaben: Eigentümer = Melder (Verbraucher), Hausverwaltung = Firma (kein Verbraucher, Melder als Ansprechpartner),
                Mieter = Hausverwaltung aus dem Pflichtfeld (Verbraucher offen; Telefon und E-Mail des Mieters nie beim Kunden), Mieter als Ansprechpartner
                vor Ort; Kantservice, Dach, PV = Kontakt (PV: privat/gewerbe). Bestehende Kunden mit Gründen (E-Mail, Telefon, Name; PLZ nur zusätzlich),
                je Kunde seine Objekte mit „Adresse gleich“. Nie aus Betreff oder Nachricht; schreibt nichts.
    Übernehmen  eine Transaktion: neuer oder gewählter Kunde (mit Profil und Hauptadresse), neues, gewähltes (nur des Kunden), Haupt- oder kein Objekt,
                Anfrage mit Quelle „Website“ und Nummer der Webseite, Fotos ans Objekt, Status übernommen, Meldung mit der Anfragenummer (F2), Historie
                ohne Inhalte; zweimal oder aus der Prüfliste 409; fremdes Objekt 422, unbekannter Kunde 404 -- dann bleibt nichts angelegt, auch keine Datei
    Anfrage     trägt Nummer der Webseite und Weg zum Eingang (PDF und Fotos)
"""

import importlib.util
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, inspect, select, text

from app import webanfragen as W
from app.crm import kunde_anlegen
from app.models import AuditLog, Customer, Inquiry, Property, PropertyDocument, WebAnfrage
from app.property_documents import document_path
from app.routers import inquiries as inquiries_router
from app.routers import webanfragen as router_modul
from scripts.empfangsdienst_attrappe import Attrappe, muster
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.test_v447_auswahl_altwerte import WIRKSAM

ROOT = Path(__file__).resolve().parent.parent
BOESE = '<img src=x onerror="alert(1)">'


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


def _welt(dienst, db, router_test_client, *anfragen):
    for a in anfragen:
        dienst.dazu(a)
    assert W.abholen(db).neu == len(anfragen)
    c = router_test_client(db, router_modul.router, inquiries_router.router, role="buero_auftrag", user_id=1)
    ids = {z.nummer: z.id for z in db.scalars(select(WebAnfrage))}
    return c, ids


def _neu(vorschlag: dict, **mehr) -> dict:
    k = dict(vorschlag["kunde_neu"])
    if k.get("is_consumer") is None:
        k["is_consumer"] = False
    return {"kunde_neu": k, "objekt": "neu", "objekt_neu": vorschlag["objekt_neu"], "titel": vorschlag["anfrage"]["titel"],
            "beschreibung": vorschlag["anfrage"]["beschreibung"], "ansprechpartner": vorschlag["anfrage"]["ansprechpartner"], **mehr}


# --- Vorschlag ---------------------------------------------------------------------------------------------------------------------------------

def test_vorschlag_je_rolle(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    e = muster("R-20261119-0910-0A1B", rolle="eigentuemer", name="Max Muster", vor_ort={"name": "Erika Muster", "telefon": "0000 111"}, fotos=1)
    v_ = muster("R-20261119-0911-0A1B", rolle="verwaltung", name="Vera Verwalter", firma="Muster Verwaltung GmbH")
    m = muster("R-20261119-0912-0A1B", rolle="mieter", name="Mia Mieter", hausverwaltung="HV Musterhaus", telefon="0000 222222", email="mieter@example.invalid")
    c, ids = _welt(dienst, db, router_test_client, e, v_, m)
    ve = c.get(f"/api/webanfragen/{ids['R-20261119-0910-0A1B']}/vorschlag").json()
    assert (ve["rolle"], ve["kunde_neu"]["first_name"], ve["kunde_neu"]["last_name"], ve["kunde_neu"]["is_consumer"]) == ("eigentuemer", "Max", "Muster", True)
    assert (ve["kunde_neu"]["street"], ve["kunde_neu"]["postal_code"], ve["kunde_neu"]["city"]) == ("Musterweg 1", "00000", "Musterstadt")
    assert ve["objekt_neu"] == {"name": "Musterweg 1", "street": "Musterweg 1", "postal_code": "00000", "city": "Musterstadt",
                                "site_contact_name": "Erika Muster", "site_contact_phone": "0000 111"}
    assert ve["anfrage"]["titel"] == "Musterweg 1 – Dachrinne / Fallrohr" and ve["anfrage"]["beschreibung"].startswith("Anfrage der Webseite R-20261119-0910-0A1B")
    assert ve["uebernehmen_moeglich"] is True
    vv = c.get(f"/api/webanfragen/{ids['R-20261119-0911-0A1B']}/vorschlag").json()
    assert (vv["kunde_neu"]["last_name"], vv["kunde_neu"]["contact_person"], vv["kunde_neu"]["is_consumer"], vv["anfrage"]["ansprechpartner"]) == (
        "Muster Verwaltung GmbH", "Vera Verwalter", False, "Vera Verwalter")
    assert vv["kunde_neu"]["street"] is None  # die Anschrift der Verwaltung kennt das Formular nicht
    vm = c.get(f"/api/webanfragen/{ids['R-20261119-0912-0A1B']}/vorschlag").json()
    assert (vm["kunde_neu"]["last_name"], vm["kunde_neu"]["is_consumer"], vm["kunde_neu"]["email"], vm["kunde_neu"]["phone"]) == ("HV Musterhaus", None, None, None)
    assert vm["vor_ort"] == {"name": "Mia Mieter", "telefon": "0000 222222"} and vm["objekt_neu"]["site_contact_name"] == "Mia Mieter"


def test_vorschlag_kantservice_dach_pv(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    c, ids = _welt(dienst, db, router_test_client, muster("K-20261119-0910-0A1B", "kantservice"), muster("D-20261119-0911-0A1B", "dach"),
                   muster("P-20261119-0912-0A1B", "pv"))
    vk = c.get(f"/api/webanfragen/{ids['K-20261119-0910-0A1B']}/vorschlag").json()
    assert (vk["rolle"], vk["objekt_neu"], vk["ort_kontakt"], vk["kunde_neu"]["street"], vk["kunde_neu"]["is_consumer"]) == ("kontakt", None, "00000 Musterstadt", None, None)
    vd = c.get(f"/api/webanfragen/{ids['D-20261119-0911-0A1B']}/vorschlag").json()
    assert (vd["kunde_neu"]["street"], vd["kunde_neu"]["is_consumer"], vd["objekt_neu"]["street"]) == ("Musterweg 1", True, "Musterweg 1")
    vp = c.get(f"/api/webanfragen/{ids['P-20261119-0912-0A1B']}/vorschlag").json()
    assert vp["kunde_neu"]["is_consumer"] is True  # PV: „privat“


def test_vorschlag_nie_aus_betreff_oder_nachricht(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    a = muster("D-20261119-0910-0A1B", "dach", adresse=False, name="Max Muster")
    a["umschlag"]["betreff"] = "Fremdweg 9 – Herr Falsch"
    a["umschlag"]["text"] = "Anschrift des Hauses: Fremdweg 9, 99999 Falschstadt"
    c, ids = _welt(dienst, db, router_test_client, a)
    v = c.get(f"/api/webanfragen/{ids['D-20261119-0910-0A1B']}/vorschlag").json()
    assert v["objekt_neu"] is None and v["kunde_neu"]["street"] is None and v["kunde_neu"]["last_name"] == "Muster"
    assert "Fremdweg" not in json.dumps(v["kunde_neu"])


def test_bestehende_kunden_mit_gruenden(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    a = kunde_anlegen(db, {"first_name": "Max", "last_name": "Muster", "email": "MUSTER@example.invalid", "postal_code": "00000"})
    b = kunde_anlegen(db, {"last_name": "Anderer", "phone": "0000/000-000"})
    hv = kunde_anlegen(db, {"last_name": "HV Musterhaus GmbH", "email": "mieter@example.invalid"})
    kunde_anlegen(db, {"last_name": "Fremd"})
    db.commit()
    c, ids = _welt(dienst, db, router_test_client, muster("R-20261119-0910-0A1B"),
                   muster("R-20261119-0911-0A1B", rolle="mieter", name="Mia Mieter", hausverwaltung="HV Musterhaus", email="mieter@example.invalid"))
    k = {x["id"]: x["gruende"] for x in c.get(f"/api/webanfragen/{ids['R-20261119-0910-0A1B']}/vorschlag").json()["kunden"]}
    assert k[a.id] == ["E-Mail gleich", "Name gleich", "PLZ gleich"] and k[b.id] == ["Telefon gleich"] and hv.id not in k
    km = {x["id"]: x["gruende"] for x in c.get(f"/api/webanfragen/{ids['R-20261119-0911-0A1B']}/vorschlag").json()["kunden"]}
    assert km == {hv.id: ["Name ähnlich"]}  # beim Mieter nur der Name der Hausverwaltung -- nicht seine E-Mail


def test_objekte_mit_adresse_gleich(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    k = kunde_anlegen(db, {"last_name": "Muster", "street": "Anderer Weg 2", "postal_code": "00000", "city": "Musterstadt"})
    db.add(Property(customer_id=k.id, name="Haus", street="Musterweg  1", postal_code="00000", city="Musterstadt"))
    db.commit()
    c, ids = _welt(dienst, db, router_test_client, muster("R-20261119-0910-0A1B"))
    liste = c.get(f"/api/webanfragen/{ids['R-20261119-0910-0A1B']}/objekte?kunde_id={k.id}").json()
    assert [(o["name"], o["adresse_gleich"]) for o in liste] == [("Haus", True), ("Hauptadresse", False)]
    assert c.get(f"/api/webanfragen/{ids['R-20261119-0910-0A1B']}/objekte?kunde_id=999999").status_code == 404


# --- Übernehmen --------------------------------------------------------------------------------------------------------------------------------

def test_uebernehmen_neu_mit_fotos_und_meldung(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    nr = "R-20261119-0910-0A1B"
    c, ids = _welt(dienst, db, router_test_client, muster(nr, fotos=2, vor_ort={"name": "Erika Muster", "telefon": "0000 111"}))
    kunden_vorher = db.scalar(select(func.count(Customer.id)))
    v = c.get(f"/api/webanfragen/{ids[nr]}/vorschlag").json()
    r = c.post(f"/api/webanfragen/{ids[nr]}/uebernehmen", json=_neu(v))
    assert r.status_code == 200, r.text
    erg = r.json()
    db.expire_all()
    inq = db.get(Inquiry, erg["inquiry_id"])
    assert (inq.webseite_nummer, inq.source, inq.status, inq.title) == (nr, "Website", "neu", "Musterweg 1 – Dachrinne / Fallrohr")
    kunde = db.get(Customer, inq.customer_id)
    assert (kunde.first_name, kunde.last_name, kunde.is_consumer, kunde.customer_number is not None) == ("Max", "Muster", True, True)
    assert db.scalar(select(func.count(Customer.id))) == kunden_vorher + 1 and any(p.is_primary_address for p in kunde.properties)
    objekt = db.get(Property, inq.property_id)
    assert (objekt.street, objekt.site_contact_name, objekt.customer_id) == ("Musterweg 1", "Erika Muster", kunde.id)
    fotos = db.scalars(select(PropertyDocument).where(PropertyDocument.property_id == objekt.id)).all()
    assert len(fotos) == 2 and all(document_path(f).is_file() and f.document_category.key == "Bilder / Fotos" for f in fotos)
    z = db.get(WebAnfrage, ids[nr])
    assert (z.status, z.inquiry_id, z.melden_soll, z.gemeldet_als, z.erledigt_von_user_id) == ("uebernommen", inq.id, inq.inquiry_number, inq.inquiry_number, 1)
    assert dienst.uebernommen[nr] == inq.inquiry_number and erg["anfrage"]["anfrage_nummer"] == inq.inquiry_number
    h = db.scalars(select(AuditLog).where(AuditLog.entity_type == W.ART_HISTORIE, AuditLog.action == "übernommen")).all()
    assert [(x.entity_label, x.new_value) for x in h] == [(nr, f"uebernommen ({inq.inquiry_number})")]
    assert c.post(f"/api/webanfragen/{ids[nr]}/uebernehmen", json=_neu(v)).status_code == 409  # nie zweimal
    a = c.get(f"/api/inquiries/{inq.id}").json()
    assert (a["webseite_nummer"], a["webanfrage_id"]) == (nr, ids[nr])


def test_uebernehmen_bestehender_kunde_und_objekt(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    k = kunde_anlegen(db, {"last_name": "HV Musterhaus"})
    haus = Property(customer_id=k.id, name="Haus", street="Musterweg 1", postal_code="00000", city="Musterstadt", site_contact_name="Hausmeister")
    db.add(haus)
    db.commit()
    nr = "R-20261119-0910-0A1B"
    c, ids = _welt(dienst, db, router_test_client, muster(nr, rolle="mieter", name="Mia Mieter", hausverwaltung="HV Musterhaus", fotos=1))
    kunden_vorher = db.scalar(select(func.count(Customer.id)))
    body = {"kunde_id": k.id, "objekt": "gewaehlt", "objekt_id": haus.id, "titel": "Rinne", "vor_ort_uebernehmen": False}
    assert c.post(f"/api/webanfragen/{ids[nr]}/uebernehmen", json=body).status_code == 200
    db.expire_all()
    assert db.scalar(select(func.count(Customer.id))) == kunden_vorher
    haus = db.get(Property, haus.id)
    assert haus.site_contact_name == "Hausmeister"  # ohne Haken bleibt der Ansprechpartner vor Ort
    inq = db.scalar(select(Inquiry).where(Inquiry.webseite_nummer == nr))
    assert (inq.customer_id, inq.property_id) == (k.id, haus.id)


def test_vor_ort_nur_mit_haken(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    k = kunde_anlegen(db, {"last_name": "HV Musterhaus"})
    haus = Property(customer_id=k.id, name="Haus", street="Musterweg 1")
    db.add(haus)
    db.commit()
    nr = "R-20261119-0910-0A1B"
    c, ids = _welt(dienst, db, router_test_client, muster(nr, rolle="mieter", name="Mia Mieter", hausverwaltung="HV Musterhaus", telefon="0000 333"))
    body = {"kunde_id": k.id, "objekt": "gewaehlt", "objekt_id": haus.id, "titel": "Rinne", "vor_ort_uebernehmen": True}
    assert c.post(f"/api/webanfragen/{ids[nr]}/uebernehmen", json=body).status_code == 200
    db.expire_all()
    haus = db.get(Property, haus.id)
    assert (haus.site_contact_name, haus.site_contact_phone) == ("Mia Mieter", "0000 333")


def test_fremdes_objekt_und_unbekannter_kunde_legen_nichts_an(dienst, threaded_db_session, router_test_client, tmp_path):
    db = threaded_db_session
    a = kunde_anlegen(db, {"last_name": "Muster"})
    b = kunde_anlegen(db, {"last_name": "Fremd"})
    fremd = Property(customer_id=b.id, name="Fremdes Haus")
    db.add(fremd)
    db.commit()
    nr = "R-20261119-0910-0A1B"
    c, ids = _welt(dienst, db, router_test_client, muster(nr, fotos=1))
    vorher = (db.scalar(select(func.count(Customer.id))), db.scalar(select(func.count(Property.id))), db.scalar(select(func.count(Inquiry.id))))
    r = c.post(f"/api/webanfragen/{ids[nr]}/uebernehmen", json={"kunde_id": a.id, "objekt": "gewaehlt", "objekt_id": fremd.id, "titel": "x"})
    assert r.status_code == 422 and r.json()["detail"] == "Das Objekt gehört nicht zum gewählten Kunden."
    v = c.get(f"/api/webanfragen/{ids[nr]}/vorschlag").json()
    r = c.post(f"/api/webanfragen/{ids[nr]}/uebernehmen", json=_neu(v, objekt="gewaehlt", objekt_id=999999))  # neuer Kunde, unbekanntes Objekt
    assert r.status_code == 404
    assert c.post(f"/api/webanfragen/{ids[nr]}/uebernehmen", json={"kunde_id": 999999, "objekt": "keins", "titel": "x"}).status_code == 404
    db.expire_all()
    nachher = (db.scalar(select(func.count(Customer.id))), db.scalar(select(func.count(Property.id))), db.scalar(select(func.count(Inquiry.id))))
    assert nachher == vorher and db.get(WebAnfrage, ids[nr]).status == "neu"
    assert not (tmp_path / "objekte").exists() or not any((tmp_path / "objekte").rglob("*.jpg"))  # keine Datei liegen geblieben


def test_scheitert_eine_datei_bleibt_nichts(dienst, threaded_db_session, router_test_client, tmp_path):
    db = threaded_db_session
    nr = "R-20261119-0910-0A1B"
    c, ids = _welt(dienst, db, router_test_client, muster(nr, fotos=2))
    zeile = db.get(WebAnfrage, ids[nr])
    W.datei_pfad(zeile.dateien[2]).unlink()  # das zweite Foto fehlt in der Ablage: das erste ist schon kopiert, dann scheitert es
    vorher = db.scalar(select(func.count(Customer.id)))
    v = c.get(f"/api/webanfragen/{ids[nr]}/vorschlag").json()
    with pytest.raises(FileNotFoundError):
        c.post(f"/api/webanfragen/{ids[nr]}/uebernehmen", json=_neu(v))
    db.expire_all()
    assert db.scalar(select(func.count(Customer.id))) == vorher and db.get(WebAnfrage, ids[nr]).status == "neu"
    assert not any((tmp_path / "objekte").rglob("*.jpg")) if (tmp_path / "objekte").exists() else True


def test_nicht_aus_der_pruefliste_und_hauptadresse_nur_neu(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    k = kunde_anlegen(db, {"last_name": "Muster"})
    db.commit()
    c, ids = _welt(dienst, db, router_test_client, muster("R-20261119-0910-0A1B", spam=True), muster("R-20261119-0911-0A1B"))
    assert c.post(f"/api/webanfragen/{ids['R-20261119-0910-0A1B']}/uebernehmen", json={"kunde_id": k.id, "objekt": "keins", "titel": "x"}).status_code == 409
    assert c.get(f"/api/webanfragen/{ids['R-20261119-0910-0A1B']}/vorschlag").json()["uebernehmen_moeglich"] is False
    r = c.post(f"/api/webanfragen/{ids['R-20261119-0911-0A1B']}/uebernehmen", json={"kunde_id": k.id, "objekt": "hauptadresse", "titel": "x"})
    assert r.status_code == 422
    r = c.post(f"/api/webanfragen/{ids['R-20261119-0911-0A1B']}/uebernehmen", json={"objekt": "keins", "titel": "x"})
    assert r.status_code == 422  # kein Auftraggeber gewählt
    v = c.get(f"/api/webanfragen/{ids['R-20261119-0911-0A1B']}/vorschlag").json()
    kn = dict(v["kunde_neu"])
    kn.pop("is_consumer")
    assert c.post(f"/api/webanfragen/{ids['R-20261119-0911-0A1B']}/uebernehmen",
                  json={"kunde_neu": kn, "objekt": "keins", "titel": "x"}).status_code == 422  # Verbraucher ja/nein ohne Vorgabe


def test_monteurin_nirgends(dienst, threaded_db_session, router_test_client):
    db = threaded_db_session
    _, ids = _welt(dienst, db, router_test_client, muster("R-20261119-0910-0A1B"))
    c = router_test_client(db, router_modul.router, role="field")
    i = ids["R-20261119-0910-0A1B"]
    assert c.get(f"/api/webanfragen/{i}/vorschlag").status_code == 403
    assert c.get(f"/api/webanfragen/{i}/objekte?kunde_id=1").status_code == 403
    assert c.post(f"/api/webanfragen/{i}/uebernehmen", json={"objekt": "keins", "titel": "x"}).status_code == 403


# --- Seiten (node) ----------------------------------------------------------------------------------------------------------------------------

VORSCHLAG = {"rolle": "mieter", "auftraggeber": BOESE, "kunden": [{"id": 4, "name": BOESE, "kundennummer": "K-1", "adresse": None, "gruende": [BOESE]}],
             "kunde_neu": {"first_name": None, "last_name": BOESE, "contact_person": None, "email": None, "phone": None, "street": None, "postal_code": None,
                           "city": None, "is_consumer": None},
             "objekt_neu": {"name": "Musterweg 1", "street": "Musterweg 1", "postal_code": "00000", "city": "Musterstadt", "site_contact_name": "Mia",
                            "site_contact_phone": None},
             "vor_ort": {"name": "Mia", "telefon": None}, "ort_kontakt": None, "anfrage": {"titel": "T", "beschreibung": "B", "ansprechpartner": None},
             "uebernehmen_moeglich": True}


@nur_mit_node
def test_seite_nichts_vorgewaehlt_und_ueber_esc():
    ablauf = (f"uebVorschlag={json.dumps(VORSCHLAG)};uebZeichnen();"
              "return [_element('uebKunden').innerHTML + _element('uebKundeNeuWahl').innerHTML, _element('uebAuftraggeberText').textContent,"
              " _element('uebTitel').value];")  # seit 1.10.8 steht „Neuer Kunde“ in uebKundeNeuWahl, nach der Suche
    kunden, text_, titel = im_browser(seite("webanfrage.html", "\nlesen('anfrage',") + WIRKSAM, ablauf)["ergebnis"]
    assert "checked" not in kunden and "<img" not in kunden and "&lt;img" in kunden and 'value="4"' in kunden and 'value="neu"' in kunden
    assert text_ == BOESE and titel == "T"


@nur_mit_node
def test_inquiries_zeigt_nummer_der_webseite():
    ablauf = ("currentInquiry={inquiry_number:'ANF-1',title:'T',customer_name:'K',created_at:'2026-11-19T08:00:00',customer_id:1,status:'neu',priority:'normal',"
              f"source:'Website',webanfrage_id:7,webseite_nummer:{json.dumps(BOESE)}}};webanfrageHinweis(currentInquiry);"
              "return _element('webanfrageHinweis').innerHTML;")
    html = im_browser(seite("inquiries.html", "\ninit();"), ablauf)["ergebnis"]
    assert 'href="/anfragen/webseite/7"' in html and "&lt;img" in html and "<img" not in html


# --- Migration ---------------------------------------------------------------------------------------------------------------------------------

def _modul(teil: str):
    pfad = next((ROOT / "alembic" / "versions").glob(f"*_{teil}.py"))
    spec = importlib.util.spec_from_file_location(f"migration_{teil}", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_migration_bestand_postgresql():
    url = os.getenv("ERP_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext
    schema = f"pgtest_w1b_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE app_users (id INTEGER PRIMARY KEY)"))
            conn.execute(text("CREATE TABLE inquiries (id INTEGER PRIMARY KEY, inquiry_number VARCHAR(50))"))
            conn.execute(text("INSERT INTO inquiries (id, inquiry_number) VALUES (1, 'ANF-2026-0001')"))
            with Operations.context(MigrationContext.configure(conn)):
                for teil in ("webanfragen_eingang", "webanfragen_objekt_adresse", "webanfragen_pruefliste_verwerfen", "webanfragen_uebernehmen"):
                    _modul(teil).upgrade()
            conn.execute(text("INSERT INTO webanfragen (id, nummer, fassung, umschlag, umschlag_sha256, status, abgeholt_am, spamverdacht, inquiry_id) "
                              "VALUES (1, 'R-20261119-0910-0A1B', 'dk-anfrage/1', '{}', :s, 'uebernommen', :t, false, 1)"),
                         {"s": "0" * 64, "t": datetime(2026, 11, 19)})
            conn.execute(text("UPDATE inquiries SET webseite_nummer = 'R-20261119-0910-0A1B' WHERE id = 1"))
            with Operations.context(MigrationContext.configure(conn)):
                with pytest.raises(RuntimeError, match="übernommen"):
                    _modul("webanfragen_uebernehmen").downgrade()
        with engine.begin() as conn:
            conn.execute(text("UPDATE webanfragen SET status = 'neu', inquiry_id = NULL"))
            with Operations.context(MigrationContext.configure(conn)):
                _modul("webanfragen_uebernehmen").downgrade()
            assert "webseite_nummer" not in {c["name"] for c in inspect(conn).get_columns("inquiries")}
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


@nur_mit_node
def test_erledigt_nennt_die_anfragenummer():
    zeile = {"id": 3, "nummer": "R-20261119-0910-0A1B", "art": "reparatur", "art_name": "Reparatur-Anfrage", "fassung": "dk-anfrage/1",
             "eingang_am": "2026-11-19T08:10:27", "betreff": None, "kontakt_name": None, "spamverdacht": False, "pruefen_grund": None, "status": "uebernommen",
             "abgeholt_am": "2026-11-19T08:11:00", "gemeldet_am": None, "dateien": 0, "zustand": "uebernommen", "meldung_offen": False,
             "anfrage_nummer": BOESE, "inquiry_id": 9}
    ablauf = f"ansicht='erledigt'; liste = [{json.dumps(zeile)}]; listeZeichnen(); return _element('listeRahmen').innerHTML;"
    tabelle = im_browser(seite("webanfragen.html", "\nladen().catch(") + WIRKSAM, ablauf)["ergebnis"]
    assert "übernommen: &lt;img" in tabelle and "<img" not in tabelle
