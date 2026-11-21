"""Version 1.10.21 (Antwort F3 vom 21.11.2026; Punkt 7 aus W1c): Rohdaten erledigter Zeilen des Adressimports leeren -- nur Musterdaten.

    erledigt   bestätigt und nicht offen in der Arbeitsliste: Kunde, Lieferant, bereits importiert, ungültig, abgelehnt, Arbeitsliste mit Erledigung
    geleert    Kunden- und Lieferantennummer, Anrede, Titel, Vorname, Name, Straße, Land, PLZ, Ort, Telefon, Fax, Mobil, zwei Mails, Hinweise der Prüfung
    bleibt     Adressnummer, Art, Status, Erledigung (samt Zeitpunkt), Verweise, Lauf, Zeilennummer -- die Wiedererkennung beim nächsten Import bleibt;
               offene Zeilen der Arbeitsliste und eine laufende Vorschau bleiben ganz
    Weg        Vorschau (GET, schreibt nichts) und Bestätigen nur mit ihrer Prüfsumme (sonst 409, nichts geleert); nur Admin; Historie eine Zeile ohne Inhalte
"""

import json
from datetime import datetime

import pytest
from sqlalchemy import select

from app import address_import as A
from app.models import AuditLog, Customer, ImportedAddress, ImportRun, Supplier
from app.routers import address_import as router_modul
from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite

PERSON = {"customer_number_raw": None, "supplier_number_raw": None, "salutation": "Frau", "title": "Dr.", "first_name": "Erika", "last_name": "Musterfrau",
          "street": "Musterweg 1", "country": "Deutschland", "postal_code": "12345", "city": "Musterstadt", "phone": "0000 111", "fax": "0000 112",
          "mobile": "0000 113", "email": "erika@example.invalid", "email_2": "erika2@example.invalid", "validation_notes": "Hinweis zu erika@example.invalid"}


# Festlegung 1.10.21 Nr. 2, ausdrücklich (nicht aus dem Code übernommen): was geleert wird -- und was bleibt
GELEERT = {"customer_number_raw", "supplier_number_raw", "salutation", "title", "first_name", "last_name", "street", "country", "postal_code", "city",
           "phone", "fax", "mobile", "email", "email_2", "validation_notes"}
BLEIBT = {"id", "import_run_id", "row_number", "legacy_address_number", "classification", "status", "resolution", "resolved_at", "created_customer_id",
          "created_supplier_id", "created_property_id", "created_at"}


def test_jede_spalte_eingeordnet():
    assert set(A.ROHDATEN_SPALTEN) == GELEERT
    assert {c.name for c in ImportedAddress.__table__.columns} == GELEERT | BLEIBT  # eine neue Spalte kommt in eine der beiden Mengen


@pytest.fixture
def welt(threaded_db_session):
    db = threaded_db_session
    lauf = ImportRun(source_filename="adressen.csv", status="completed", row_count_total=7)
    db.add(lauf)
    db.flush()
    kunde = Customer(name="Erika Musterfrau", last_name="Musterfrau", first_name="Erika", legacy_address_number="1001", import_run_id=lauf.id)
    lieferant = Supplier(name="Holz Muster GmbH", supplier_number="L-1", legacy_address_number="1002", import_run_id=lauf.id)
    db.add_all([kunde, lieferant])
    db.flush()
    zeilen = {
        "kunde": dict(classification="customer", legacy_address_number="1001", created_customer_id=kunde.id, customer_number_raw="K-1"),
        "lieferant": dict(classification="supplier", legacy_address_number="1002", created_supplier_id=lieferant.id, supplier_number_raw="L-1"),
        "doppelt": dict(classification="duplicate", legacy_address_number="1001"),
        "abgelehnt": dict(classification=A.ABGELEHNT, legacy_address_number="1004"),
        "erledigt": dict(classification="unassigned", legacy_address_number="1005", resolution="discarded", resolved_at=datetime(2026, 10, 1)),
        "offen": dict(classification="unassigned", legacy_address_number="1006"),
    }
    w = {"db": db, "lauf": lauf, "kunde_obj": kunde, "lieferant_obj": lieferant}
    for n, (name, werte) in enumerate(zeilen.items(), 2):
        z = ImportedAddress(import_run_id=lauf.id, row_number=n, status="confirmed", **{**PERSON, **werte})
        db.add(z)
        db.flush()
        w[name] = z.id
    vorschau = ImportedAddress(row_number=2, status="previewing", classification="customer", legacy_address_number="2001", **PERSON)
    db.add(vorschau)
    db.flush()
    w["vorschau"] = vorschau.id
    db.commit()
    return w


def _zeile(db, i):
    db.expire_all()
    return db.get(ImportedAddress, i)


def test_vorschau_zaehlt_und_schreibt_nichts(welt):
    db = welt["db"]
    v = A.rohdaten_vorschau(db)
    assert v["zahl"] == 5 and (v["offen_arbeitsliste"], v["in_vorschau"], v["schon_leer"]) == (1, 1, 0)
    assert [(a["name"], a["zahl"]) for a in v["je_art"]] == [("Kunde", 1), ("Lieferant", 1), ("Arbeitsliste erledigt", 1), ("bereits importiert", 1),
                                                           ("abgelehnt", 1)]
    assert len(v["stand"]) == 16
    assert _zeile(db, welt["kunde"]).first_name == "Erika"


def test_leeren_nur_erledigte_und_nur_die_rohdaten(welt):
    db = welt["db"]
    assert A.rohdaten_leeren(db, A.rohdaten_vorschau(db)["stand"], None) == {"geleert": 5}
    for name in ("kunde", "lieferant", "doppelt", "abgelehnt", "erledigt"):
        z = _zeile(db, welt[name])
        assert all(getattr(z, s) is None for s in GELEERT), name
        assert z.legacy_address_number and z.status == "confirmed" and z.import_run_id == welt["lauf"].id and z.row_number
    k, e = _zeile(db, welt["kunde"]), _zeile(db, welt["erledigt"])
    assert (k.classification, k.created_customer_id) == ("customer", welt["kunde_obj"].id)
    assert _zeile(db, welt["lieferant"]).created_supplier_id == welt["lieferant_obj"].id
    assert (e.resolution, e.resolved_at) == ("discarded", datetime(2026, 10, 1))
    for name in ("offen", "vorschau"):  # unverändert
        z = _zeile(db, welt[name])
        assert all(getattr(z, s) == PERSON[s] for s in GELEERT if s not in ("customer_number_raw", "supplier_number_raw")), name
    v = A.rohdaten_vorschau(db)
    assert (v["zahl"], v["schon_leer"], v["offen_arbeitsliste"]) == (0, 5, 1)
    # der Kunde und der Lieferant selbst bleiben, wie sie sind
    assert db.get(Customer, welt["kunde_obj"].id).first_name == "Erika" and db.get(Supplier, welt["lieferant_obj"].id).name == "Holz Muster GmbH"


def test_wiedererkennung_und_arbeitsliste_bleiben(welt):
    db = welt["db"]
    A.rohdaten_leeren(db, A.rohdaten_vorschau(db)["stand"], None)
    assert A._address_already_imported(db, "1005") and A._address_already_imported(db, "1004")  # nur noch über die Rohzeile bekannt
    offen = A.list_unassigned(db, "musterfrau")
    assert [z["id"] for z in offen] == [welt["offen"]]  # die offene Zeile ist ganz und auffindbar


def test_ein_lauf_laesst_sich_danach_noch_rueckgaengig_machen(welt):
    db = welt["db"]
    db.delete(db.get(ImportedAddress, welt["erledigt"]))  # eine bearbeitete Zeile der Arbeitsliste sperrt das Rückgängigmachen (wie bisher)
    db.commit()
    A.rohdaten_leeren(db, A.rohdaten_vorschau(db)["stand"], None)
    A.revert_import_run(db, welt["lauf"].id)
    db.expire_all()
    assert db.get(ImportRun, welt["lauf"].id).status == "reverted" and db.get(Customer, welt["kunde_obj"].id) is None


def test_pruefsumme_und_nichts_geleert(welt):
    db = welt["db"]
    stand = A.rohdaten_vorschau(db)["stand"]
    z = db.get(ImportedAddress, welt["offen"])
    z.resolution, z.resolved_at = "discarded", datetime(2026, 11, 1)  # inzwischen erledigt: die Liste ist eine andere
    db.commit()
    with pytest.raises(A.RohdatenStandGeaendert):
        A.rohdaten_leeren(db, stand, None)
    db.rollback()
    assert _zeile(db, welt["kunde"]).first_name == "Erika"


def test_historie_ohne_inhalte(welt):
    db = welt["db"]
    vorher = db.scalar(select(AuditLog.id).order_by(AuditLog.id.desc()).limit(1)) or 0
    A.rohdaten_leeren(db, A.rohdaten_vorschau(db)["stand"], None)
    neu = db.scalars(select(AuditLog).where(AuditLog.id > vorher).order_by(AuditLog.id)).all()
    assert [(e.action, e.entity_type, e.old_value, e.new_value) for e in neu] == [
        ("Rohdaten geleert", "Adressimport", "5 erledigte Zeilen mit Rohdaten", "geleert")]
    text = json.dumps([[e.entity_label, e.old_value, e.new_value, e.field_label] for e in neu], ensure_ascii=False)
    for wert in ("Erika", "Musterfrau", "Musterweg", "erika@", "0000 111", "K-1"):
        assert wert not in text


@pytest.mark.parametrize("rolle, status", [("admin", 200), ("buero_finanzen", 403), ("buero_auftrag", 403), ("field", 403)])
def test_nur_admin(welt, router_test_client, rolle, status):
    c = router_test_client(welt["db"], router_modul.router, role=rolle)
    assert c.get("/api/address-import/rohdaten").status_code == status
    r = c.post("/api/address-import/rohdaten/leeren", json={"stand": "0" * 16})
    assert r.status_code == (409 if rolle == "admin" else 403)
    assert _zeile(welt["db"], welt["kunde"]).first_name == "Erika"


def test_ueber_die_schnittstelle(welt, router_test_client):
    c = router_test_client(welt["db"], router_modul.router, role="admin")
    v = c.get("/api/address-import/rohdaten").json()
    assert v["zahl"] == 5
    assert c.post("/api/address-import/rohdaten/leeren", json={"stand": v["stand"]}).json() == {"geleert": 5}
    assert c.get("/api/address-import/rohdaten").json()["zahl"] == 0
    assert c.post("/api/address-import/rohdaten/leeren", json={"stand": " "}).status_code == 422


# --- Seite (node) ---------------------------------------------------------------------------------------------------------------------------------

VORSCHAU = {"zahl": 5, "je_art": [{"art": "customer", "name": "Kunde", "zahl": 3}, {"art": "supplier", "name": "Lieferant", "zahl": 2}],
            "offen_arbeitsliste": 1, "in_vorschau": 0, "schon_leer": 4, "stand": "0123456789abcdef"}


@nur_mit_node
def test_seite_vorschau_und_leeren():
    ablauf = ("rohdaten = " + json.dumps(VORSCHAU) + "; rohdatenZeichnen();"
              "const vorher = [_element('rohdatenText').textContent, _element('rohdatenBleibt').textContent, _element('rohdatenKnopf').hidden];"
              "let frage = ''; confirm = m => { frage = m; return true; };"
              "document.querySelector = () => null;"  # die Attrappe fände sonst ein „abgelehntes Zahlenfeld“ (abschliessen() fragt danach)
              "const _alt = globalThis.fetch; globalThis.fetch = async (u, o = {}) => { const r = await _alt(u, o);"
              " return (o.method || 'GET') === 'POST' ? {...r, json: async () => ({geleert: 5})} : r; };"
              "await rohdatenLeeren(); return [vorher, frage, _element('rohdatenStatus').textContent];")
    lauf = im_browser(seite("address_import.html", "\ninit().catch("), ablauf, {"/api/address-import/rohdaten": {**VORSCHAU, "zahl": 0, "je_art": []}})
    vorher, frage, status = lauf["ergebnis"]
    assert vorher == ["5 erledigte Zeilen tragen noch Rohdaten aus dem Altsystem (Kunde: 3, Lieferant: 2).",
                      "Unverändert bleiben: offen in der Arbeitsliste 1 (bis sie erledigt sind); schon leer: 4.", False]
    assert frage.startswith("Bei 5 erledigten Zeilen Namen, Anschriften") and "nicht rückgängig" in frage
    assert status == "5 Zeilen geleert."
    assert [(a["url"], a["body"]) for a in lauf["aufrufe"] if a["methode"] == "POST"] == [("/api/address-import/rohdaten/leeren", {"stand": "0123456789abcdef"})]


@nur_mit_node
def test_seite_ohne_rohdaten_kein_knopf():
    ablauf = "rohdaten = " + json.dumps({**VORSCHAU, "zahl": 0, "je_art": []}) + "; rohdatenZeichnen(); return [_element('rohdatenText').textContent, _element('rohdatenKnopf').hidden];"
    assert im_browser(seite("address_import.html", "\ninit().catch("), ablauf)["ergebnis"] == ["Keine erledigte Zeile trägt noch Rohdaten aus dem Altsystem.", True]
