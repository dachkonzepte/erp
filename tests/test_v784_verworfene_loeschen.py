"""Version 1.10.13 (Stufe W1c, Punkt 4): verworfene Eingänge (Spam, Test, Doppelt) 6 Monate nach Eingang löschen -- nur Musterdaten.

    Fällig     verworfen mit Spam, Test oder Doppelt, 6 Monate nach Eingang (ohne Eingangszeit nach dem Abholen); nie „Sonstiges“ (Archiv), nie
               übernommen, nie mit einem Objektdokument
    Löschen    nur Admin und Büro – Finanzen, einzeln oder gesammelt mit der Prüfsumme der Vorschau; unter den Sperren neu gerechnet, sonst
               übersprungen; Zeilen und Dateien weg, die Historie behält ihre Zeilen und bekommt „gelöscht“ mit Nummer und Grund, ohne Inhalte
    Seite      „Zum Löschen“ mit Knöpfen nur mit Recht; endgültig, über abschliessen() mit Rückfrage
"""

import json

import pytest
from sqlalchemy import select

from app import aufbewahrung as A
from app.audit import record_audit_entry
from app.models import AuditLog, Property, PropertyDocument, WebAnfrage, WebAnfrageDatei
from app.routers import pages as pages_router
from app.webanfragen import ART_HISTORIE, datei_pfad
from tests.test_v334_auswahl_restfaelle import nur_mit_node
from tests.test_v782_archiv import ALT, JUNG, Welt, _c
from tests.test_v783_aufbewahrung_seite import VORSCHAU, _lauf, _seite

BOESE = '<img src=x onerror="alert(1)">'


@pytest.fixture
def welt(threaded_db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("ERP_DATA_DIR", str(tmp_path / "daten"))
    return Welt(threaded_db_session)


def _mit_datei(welt, w, name="anfrage.pdf"):
    d = WebAnfrageDatei(webanfrage_id=w.id, name=name, typ="application/pdf", groesse=4, sha256="0" * 64, gespeichert_als=f"{w.id:032x}.pdf")
    welt.db.add(d)
    welt.db.flush()
    pfad = datei_pfad(d)
    pfad.write_bytes(b"%PDF")
    return pfad


def test_was_zum_loeschen_faellig_ist(welt):
    db = welt.db
    spam, test, doppelt = (welt.eingang(status="verworfen", grund=g) for g in ("spam", "test", "doppelt"))
    jung = welt.eingang(tage=JUNG, status="verworfen", grund="spam")
    sonstiges = welt.eingang(status="verworfen", grund="sonstiges")
    neu = welt.eingang(status="neu")
    ohne_eingang = welt.eingang(status="verworfen", grund="spam", eingang=False)
    mit_dokument = welt.eingang(status="verworfen", grund="spam")
    k = welt.kunde()
    objekt = db.scalar(select(Property).where(Property.customer_id == k.id))
    db.add(PropertyDocument(property_id=objekt.id, category_id=1, original_filename="x.jpg", stored_filename="x.jpg", webanfrage_id=mit_dokument.id))
    db.add(PropertyDocument(property_id=objekt.id, category_id=1, original_filename="y.jpg", stored_filename="y.jpg", webanfrage_id=None))  # NULL zählt nicht
    db.commit()
    ids = [z["id"] for z in A.zum_loeschen(db)]
    assert ids == [spam.id, test.id, doppelt.id, ohne_eingang.id]
    assert jung.id not in ids and sonstiges.id not in ids and neu.id not in ids
    v = A.vorschau(db)
    assert v["zahl_loeschen"] == 4 and len(v["stand_loeschen"]) == 16
    assert [x["grund_text"] for x in v["loeschen"]] == ["Spam", "Test", "Doppelt", "Spam"]


def test_einzeln_samt_dateien_und_historie_ohne_inhalt(welt, router_test_client):
    db = welt.db
    w = welt.eingang(status="verworfen", grund="spam")
    pfad = _mit_datei(welt, w)
    record_audit_entry(db, action="verworfen", entity_type=ART_HISTORIE, entity_id=w.id, entity_label=w.nummer, field_name="status",
                       old_value="neu", new_value="verworfen (spam)")
    db.commit()
    r = _c(db, router_test_client).post(f"/api/aufbewahrung/eingang/{w.id}/loeschen").json()
    assert r == {"geloescht": [{"art": "eingang", "id": w.id, "nummer": w.nummer, "grund": None}], "uebersprungen": []}
    db.expire_all()
    assert db.scalar(select(WebAnfrage.id).where(WebAnfrage.id == w.id)) is None and db.scalar(select(WebAnfrageDatei.id)) is None
    assert not pfad.exists()
    h = db.scalars(select(AuditLog).where(AuditLog.entity_type == ART_HISTORIE, AuditLog.entity_id == str(w.id)).order_by(AuditLog.id)).all()
    assert [(x.action, x.entity_label, x.old_value, x.new_value) for x in h] == [
        ("verworfen", w.nummer, "neu", "verworfen (spam)"), ("gelöscht", w.nummer, "verworfen (Spam)", None)]


def test_nicht_faellig_bleibt(welt, router_test_client):
    db = welt.db
    jung = welt.eingang(tage=JUNG, status="verworfen", grund="spam")
    sonstiges = welt.eingang(status="verworfen", grund="sonstiges")
    db.commit()
    c = _c(db, router_test_client)
    for w in (jung, sonstiges):
        r = c.post(f"/api/aufbewahrung/eingang/{w.id}/loeschen").json()
        assert r["geloescht"] == [] and r["uebersprungen"][0]["grund"] == "nicht (mehr) zum Löschen fällig"
    db.expire_all()
    assert db.get(WebAnfrage, jung.id) is not None and db.get(WebAnfrage, sonstiges.id) is not None


def test_gesammelt_nur_mit_der_pruefsumme(welt, router_test_client):
    db = welt.db
    a, b = welt.eingang(status="verworfen", grund="spam"), welt.eingang(status="verworfen", grund="test")
    db.commit()
    a_id, b_id = a.id, b.id  # nach dem Löschen lädt das Objekt nicht mehr nach
    c = _c(db, router_test_client)
    stand = c.get("/api/aufbewahrung").json()["stand_loeschen"]
    welt.eingang(status="verworfen", grund="doppelt")  # neu dazu nach der Vorschau
    db.commit()
    assert c.post("/api/aufbewahrung/loeschen", json={"stand": stand}).status_code == 409
    db.expire_all()
    assert db.scalar(select(WebAnfrage.id).where(WebAnfrage.id == a_id)) == a_id
    stand = c.get("/api/aufbewahrung").json()["stand_loeschen"]
    r = c.post("/api/aufbewahrung/loeschen", json={"stand": stand}).json()
    assert len(r["geloescht"]) == 3 and c.get("/api/aufbewahrung").json()["zahl_loeschen"] == 0
    assert db.scalar(select(WebAnfrage.id).where(WebAnfrage.id == b_id)) is None


@pytest.mark.parametrize("rolle", ["field", "buero_auftrag"])
def test_nur_admin_und_buero_finanzen(rolle, welt, router_test_client):
    db = welt.db
    w = welt.eingang(status="verworfen", grund="spam")
    db.commit()
    c = _c(db, router_test_client, rolle)
    assert c.post(f"/api/aufbewahrung/eingang/{w.id}/loeschen").status_code == 403
    assert c.post("/api/aufbewahrung/loeschen", json={"stand": "0" * 16}).status_code == 403
    db.expire_all()
    assert db.get(WebAnfrage, w.id) is not None


LOESCHEN = {**VORSCHAU, "zahl_loeschen": 1, "stand_loeschen": "fedcba9876543210",
            "loeschen": [{"art": "eingang", "id": 11, "nummer": "R-20260301-0900-0A1B", "titel": BOESE, "grund": "spam", "grund_text": "Spam",
                          "eingang": "2026-03-01", "faellig_ab": "2026-09-01", "dateien": 2}]}


@nur_mit_node
@pytest.mark.parametrize("rolle, knoepfe", [("buero_finanzen", True), ("buero_auftrag", False)])
def test_seite_zum_loeschen(rolle, knoepfe, threaded_db_session, router_test_client):
    html = _seite(rolle, threaded_db_session, router_test_client).text
    ablauf = f"vorschau = {json.dumps(LOESCHEN)}; standZeichnen(); faelligZeichnen(); return [_element('inhalt').innerHTML, _element('standText').innerHTML];"
    inhalt, stand = _lauf(html, ablauf)["ergebnis"]
    assert "Zum Löschen" in inhalt and "<img" not in inhalt and "&lt;img" in inhalt and "Spam" in inhalt
    assert ('data-klick="loeschen" data-id="11"' in inhalt) == knoepfe and ('id="alleLoeschenKnopf"' in inhalt) == knoepfe
    assert "<b>1</b> zum Löschen" in stand


@nur_mit_node
def test_seite_loescht_mit_rueckfrage_und_pruefsumme(threaded_db_session, router_test_client):
    html = _seite("buero_finanzen", threaded_db_session, router_test_client).text
    ablauf = ("const _alt = globalThis.fetch; globalThis.fetch = async (u, o = {}) => { const r = await _alt(u, o);"
              " return (o.method || 'GET') === 'POST' ? {...r, json: async () => ({geloescht: [{art: 'eingang', id: 11}], uebersprungen: []})} : r; };"
              "let fragen = 0; confirm = () => { fragen++; return true; };"
              "document.querySelector = () => null;"  # die Attrappe fände sonst ein „abgelehntes Zahlenfeld“ (abschliessen() fragt danach)
              f"vorschau = {json.dumps(LOESCHEN)};"
              "await eingangLoeschen(11); const erst = _element('aktionStatus').textContent; await alleLoeschen(); return [fragen, erst, _element('aktionStatus').textContent];")
    lauf = _lauf(html, ablauf, {"/api/aufbewahrung": LOESCHEN})
    posts = [(a["url"], a["body"]) for a in lauf["aufrufe"] if a["methode"] == "POST"]
    assert posts == [("/api/aufbewahrung/eingang/11/loeschen", None), ("/api/aufbewahrung/loeschen", {"stand": "fedcba9876543210"})]
    assert lauf["ergebnis"] == [2, "1 Eingang gelöscht.", "1 Eingang gelöscht."]
