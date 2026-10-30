"""Version 1.9.140 (Stufe 5, R4, Punkt 3) -- Kundendokumente im Änderungsprotokoll und im Verlauf des Kunden.

Hochladen, Angaben ändern und Löschen über die echten Endpunkte (POST /api/customers/{id}/documents, PUT und DELETE /api/customer-documents/{id}):
je eine Zeile im Verlauf des Kunden -- auch nach dem Löschen, nichts bei einem anderen Kunden, und der Name der Ablagedatei steht nicht in der Zeile."""

import pytest
from sqlalchemy import select

from app import customer_documents
from app.audit import STILL_JE_ART, TYPE_LABELS
from app.grunddaten import anlegen
from app.models import AuditLog, CustomerDocument, ProjectDocument
from app.routers import customer_documents as dokumente_router
from app.routers import customers as customers_router
from tests.test_v381_zahlungen import _kunde
from tests.test_v547_akte_verlauf import _Anfrage

PDF = b"%PDF-1.4\n%test\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture
def welt(threaded_db_session, router_test_client, tmp_path, monkeypatch):
    monkeypatch.setattr(customer_documents, "CUSTOMER_ROOT", tmp_path / "customer_files")
    db = threaded_db_session
    anlegen(db)
    kessler, lorenz = _kunde(db, "Kessler"), _kunde(db, "Lorenz")
    db.commit()
    client = router_test_client(db, customers_router.router, dokumente_router.router)
    return {"db": db, "kessler": kessler, "lorenz": lorenz, "client": client}


def _hochladen(w, kunde, name="vertrag.pdf", **felder):
    with _Anfrage(7, "Olga Office", "POST", f"/api/customers/{kunde.id}/documents"):
        a = w["client"].post(f"/api/customers/{kunde.id}/documents", files={"file": (name, PDF, "application/pdf")}, data={"category": "Sonstiges", **felder})
    assert a.status_code == 200, a.text
    return a.json()


def _loeschen(w, doc_id):
    with _Anfrage(7, "Olga Office", "DELETE", f"/api/customer-documents/{doc_id}"):
        a = w["client"].delete(f"/api/customer-documents/{doc_id}")
    assert a.status_code == 200, a.text


def _strom(w, kunde, **abfrage):
    a = w["client"].get(f"/api/customers/{kunde.id}/verlauf", params=abfrage)
    assert a.status_code == 200, a.text
    return a.json()["eintraege"]


def _dokument_zeilen(strom):
    return [e for e in strom if e["einzelheiten"] and e["einzelheiten"][0]["entity_type"] == "Kundendokument"]


def test_art_steht_im_protokoll():
    assert TYPE_LABELS[CustomerDocument] == "Kundendokument"
    assert "category_id" in STILL_JE_ART[CustomerDocument] and "category_id" in STILL_JE_ART[ProjectDocument]


def test_hochladen_und_loeschen_sind_zwei_zeilen(welt):
    doc = _hochladen(welt, welt["kessler"])
    _loeschen(welt, doc["id"])
    zeilen = _dokument_zeilen(_strom(welt, welt["kessler"]))
    assert [e["titel"] for e in zeilen] == ["Kundendokument vertrag.pdf gelöscht", "Kundendokument vertrag.pdf angelegt"]
    assert {e["art"] for e in zeilen} == {"aenderung"} and {e["konto"] for e in zeilen} == {"Olga Office"}
    # beide im Protokoll selbst, unter der Kennung des Dokuments
    db = welt["db"]
    aktionen = list(db.scalars(select(AuditLog.action).where(AuditLog.entity_type == "Kundendokument", AuditLog.entity_id == str(doc["id"])).order_by(AuditLog.id)))
    assert aktionen == ["angelegt", "gelöscht"]


def test_geloeschtes_dokument_bleibt_im_verlauf(welt):
    doc = _hochladen(welt, welt["kessler"], name="alt.pdf")
    _loeschen(welt, doc["id"])
    assert welt["db"].get(CustomerDocument, doc["id"]) is None
    assert any("alt.pdf" in e["titel"] for e in _strom(welt, welt["kessler"]))


def test_angaben_aendern_ist_eine_zeile(welt):
    doc = _hochladen(welt, welt["kessler"])
    with _Anfrage(7, "Olga Office", "PUT", f"/api/customer-documents/{doc['id']}"):
        a = welt["client"].put(f"/api/customer-documents/{doc['id']}", json={"category": "Sonstiges", "subfolder": "Verträge", "description": "Rahmenvertrag", "document_date": "2026-10-01"})
    assert a.status_code == 200, a.text
    zeile = _dokument_zeilen(_strom(welt, welt["kessler"]))[0]
    felder = {z["field_name"] for z in zeile["einzelheiten"]}
    assert felder == {"subfolder", "description", "document_date"}
    assert "vertrag.pdf" in zeile["titel"]
    beschreibung = next(z for z in zeile["einzelheiten"] if z["field_name"] == "description")
    assert (beschreibung["field_label"], beschreibung["old_value"], beschreibung["new_value"]) == ("Beschreibung", None, "Rahmenvertrag")


def test_nichts_beim_anderen_kunden(welt):
    doc = _hochladen(welt, welt["lorenz"], name="fremd.pdf")
    assert not _dokument_zeilen(_strom(welt, welt["kessler"]))
    assert [e["titel"] for e in _dokument_zeilen(_strom(welt, welt["lorenz"]))] == ["Kundendokument fremd.pdf angelegt"]
    _loeschen(welt, doc["id"])
    assert not _dokument_zeilen(_strom(welt, welt["kessler"]))  # auch der Schnappschuss des Löschens gehört Lorenz


def test_filter_aenderung_zeigt_dokumente_zahlung_nicht(welt):
    _hochladen(welt, welt["kessler"])
    assert _dokument_zeilen(_strom(welt, welt["kessler"], art="aenderung"))
    assert not _dokument_zeilen(_strom(welt, welt["kessler"], art="zahlung"))


def test_ablagename_steht_nicht_in_der_zeile(welt):
    doc = _hochladen(welt, welt["kessler"])
    gespeichert = welt["db"].get(CustomerDocument, doc["id"]).stored_filename
    e = _dokument_zeilen(_strom(welt, welt["kessler"]))[0]
    assert gespeichert not in e["titel"] and gespeichert not in (e["unterzeile"] or "")


def test_kategorie_aendern_steht_einmal_und_lesbar(welt):
    """Name und Kennung der Kategorie ändern sich zusammen -- bis 1.9.139 zwei gleiche Zeilen „Kategorie“ (auch an der Projektdatei)."""
    doc = _hochladen(welt, welt["kessler"])
    with _Anfrage(7, "Olga Office", "PUT", f"/api/customer-documents/{doc['id']}"):
        a = welt["client"].put(f"/api/customer-documents/{doc['id']}", json={"category": "Rechnungen / Belege", "subfolder": None, "description": None, "document_date": None})
    assert a.status_code == 200, a.text
    gespeichert = welt["db"].get(CustomerDocument, doc["id"])
    welt["db"].refresh(gespeichert)
    assert gespeichert.category == "Rechnungen / Belege"  # die Kennung läuft mit, sonst prüfte der Rest nichts
    zeile = _dokument_zeilen(_strom(welt, welt["kessler"]))[0]
    assert [(z["field_name"], z["old_value"], z["new_value"]) for z in zeile["einzelheiten"]] == [("category", "Sonstiges", "Rechnungen / Belege")]
    assert (zeile["titel"], zeile["unterzeile"]) == ("Kundendokument vertrag.pdf: Kategorie Sonstiges → Rechnungen / Belege", "")
