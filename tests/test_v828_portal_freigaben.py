"""Version 1.11.36 (Stufe P2c, Teil 1): Freigaben fürs Kundenportal im ERP -- app/portal_freigaben.py über den Router (router_test_client, SQLite).

    Freigeben     einzeln mit Vorschlag für den Titel (Kategorie und Datum, nie der Dateiname); mehrere auf einmal (Nachtrag 6) -- alles oder nichts,
                  schon freigegebene desselben Kunden zählen als „schon“; fremd wie unbekannt 404 (Regel 25); eine eigene, die heute nicht gilt, 409 mit
                  Grund; nur PDF und Bilder bis 25 MB; im Archiv 409
    Anderswo      steht die Quelle noch bei einem anderen Kunden (dort ruht sie), sagt die Meldung, bei wem -- erst dort zurücknehmen (vorgemerkt 26.11.2026);
                  auch wenn zwei gleichzeitig freigeben
    Zurücknehmen  sofort „zurückgenommen“, die Zeile bleibt; zweimal 409; eine Freigabe eines anderen Kunden 404; auch im Archiv
    Erneut        nur eine gescheiterte Kopie, nicht zurückgenommen
    Stand         wird vorbereitet, sichtbar, gescheitert (Grund in Worten), ruht (Grund)
    Rechte        ab Büro – Auftrag, Monteurin 403, Modul aus 403; Änderungshistorie ohne die Felder der Kopie

Die Kette selbst gegen die Funktion der Datenbank: tests/test_v827_portal_freigaben_kette.py.
"""

from __future__ import annotations

import typing
from datetime import date, datetime

import pytest
from sqlalchemy import select

from app import portal_freigaben as pf
from app.models import (
    AuditLog, Customer, CustomerDocument, CustomerProfile, DocumentCategory, EnabledModule, Order, PortalFreigabe, Project, ProjectDocument, Property,
    ServiceReport, ServiceReportPhoto,
)
from app.portal import werte
from app.project_pipeline_columns import default_pipeline_column_id
from app.routers import portal_freigaben
from app.schemas import FREIGABE_QUELLE
from tests.quellangebot import quell_angebot


class Welt:
    def __init__(self, db, client):
        self.db, self.client = db, client
        self.kategorie = db.scalar(select(DocumentCategory).order_by(DocumentCategory.id).limit(1))
        self.a = self.kunde("Muster", "K-1001")
        self.b = self.kunde("Beispiel", "K-1002")

    def kunde(self, name, nummer):
        k = Customer(name=f"Herr {name}", last_name=name)
        self.db.add(k)
        self.db.flush()
        self.db.add(CustomerProfile(customer_id=k.id, customer_number=nummer))
        self.db.commit()
        return k

    def projekt(self, kunde, *, muster=False):
        o = Property(customer_id=kunde.id, name="Halle", street="Hafenweg 3", postal_code="12345", city="Musterstadt")
        self.db.add(o)
        self.db.flush()
        p = Project(project_number=f"P-{o.id}-{kunde.id}", name="Interner Titel", customer_id=kunde.id, property_id=o.id, status="anfrage",
                    pipeline_column_id=default_pipeline_column_id(self.db), is_template=muster)
        self.db.add(p)
        self.db.commit()
        return p

    def dokument(self, kunde, *, typ="application/pdf", groesse=1000):
        d = CustomerDocument(customer_id=kunde.id, category_id=self.kategorie.id, category=self.kategorie.label, original_filename="geheimer-name.pdf",
                             stored_filename=f"x{datetime.now().timestamp()}-{id(object())}", content_type=typ, file_size=groesse,
                             document_date=date(2026, 11, 20))
        self.db.add(d)
        self.db.commit()
        return d

    def projektdokument(self, p):
        d = ProjectDocument(project_id=p.id, category_id=self.kategorie.id, category=self.kategorie.label, original_filename="plan.pdf",
                            stored_filename=f"p{datetime.now().timestamp()}-{id(object())}", content_type="application/pdf", file_size=10,
                            document_date=date(2026, 11, 21))
        self.db.add(d)
        self.db.commit()
        return d

    def fotos(self, p, anzahl):
        nr = f"A-{p.id}"
        a = Order(order_number=nr, project_id=p.id, source_quote_id=quell_angebot(self.db, p.id, nr), quote_number_snapshot=f"Q-{nr}", title="Dach",
                  customer_name="x", customer_id=p.customer_id)
        self.db.add(a)
        self.db.flush()
        b = ServiceReport(order_id=a.id, report_type="wartung")
        self.db.add(b)
        self.db.flush()
        fotos = [ServiceReportPhoto(service_report_id=b.id, kind="allgemein", file_path=f"f{b.id}-{i}.jpg") for i in range(anzahl)]
        self.db.add_all(fotos)
        self.db.commit()
        return [f.id for f in fotos]

    def url(self, kunde, rest=""):
        return f"/api/customers/{kunde.id}/portal/freigaben{rest}"

    def freigeben(self, kunde, quelle, ids, titel=None):
        return self.client.post(self.url(kunde), json={"quelle": quelle, "quelle_ids": ids, **({"titel": titel} if titel is not None else {})})

    def zeilen(self):
        self.db.expire_all()
        return self.db.scalars(select(PortalFreigabe).order_by(PortalFreigabe.id)).all()


@pytest.fixture
def w(threaded_db_session, router_test_client):
    db = threaded_db_session
    db.add(EnabledModule(module_key="kundenportal", enabled=True))
    db.commit()
    return Welt(db, router_test_client(db, portal_freigaben.router, role="buero_auftrag", user_id=11, display_name="Auri Auftrag"))


def test_schema_kennt_genau_die_quellen():
    assert typing.get_args(FREIGABE_QUELLE) == werte.FREIGABE_QUELLEN


def test_freigeben_einzeln_mit_vorschlag_und_historie(w):
    d = w.dokument(w.a)
    r = w.freigeben(w.a, "customer_documents", [d.id])
    assert r.status_code == 200, r.text
    stand = r.json()
    assert stand["schon"] == 0 and len(stand["neu"]) == 1
    assert stand["portal_aktiv"] is False  # freigeben geht auch, solange das Portal des Kunden aus ist (Bauplan B4.2)
    e = stand["eintraege"][0]
    assert e["titel"] == f"{w.kategorie.label} vom 20.11.2026" and "geheimer-name" not in r.text  # nie der Dateiname
    assert (e["art"], e["zustand"], e["automatisch"], e["freigegeben_von"]) == ("dokument", "wird_vorbereitet", False, "Auri Auftrag")
    f = w.zeilen()[0]
    assert (f.customer_id, f.quelle, f.quelle_id, f.datum, f.regel, f.freigegeben_von_user_id) == (w.a.id, "customer_documents", d.id, date(2026, 11, 20),
                                                                                                    None, 11)
    historie = w.db.scalars(select(AuditLog).where(AuditLog.entity_type == "Freigabe im Kundenportal")).all()
    assert historie and all("kopie" not in (h.field_name or "") for h in historie)


def test_titel_von_hand(w):
    d = w.dokument(w.a)
    assert w.freigeben(w.a, "customer_documents", [d.id], titel="Dachplan Süd").json()["eintraege"][0]["titel"] == "Dachplan Süd"
    for falsch in ("", "   ", "x" * 121):
        assert w.freigeben(w.a, "customer_documents", [w.dokument(w.a).id], titel=falsch).status_code == 422


def test_mehrere_fotos_auf_einmal(w):
    p = w.projekt(w.a)
    fotos = w.fotos(p, 3)
    r = w.freigeben(w.a, "service_report_photos", fotos[:2])
    assert r.status_code == 200 and len(r.json()["neu"]) == 2 and {e["art"] for e in r.json()["eintraege"]} == {"foto"}
    r = w.freigeben(w.a, "service_report_photos", fotos)
    assert r.status_code == 200 and len(r.json()["neu"]) == 1 and r.json()["schon"] == 2
    r = w.freigeben(w.a, "service_report_photos", fotos)
    assert r.status_code == 409 and r.json()["detail"] == pf.MELDUNG_SCHON
    assert len(w.zeilen()) == 3


def test_alles_oder_nichts(w):
    eigene = w.fotos(w.projekt(w.a), 2)
    fremde = w.fotos(w.projekt(w.b), 1)
    r = w.freigeben(w.a, "service_report_photos", eigene + fremde)
    assert r.status_code == 404 and w.zeilen() == []
    r = w.freigeben(w.a, "service_report_photos", eigene + [999_999])
    assert r.status_code == 404 and w.zeilen() == []


def test_fremd_wie_unbekannt(w):
    fremd = w.freigeben(w.a, "customer_documents", [w.dokument(w.b).id])
    unbekannt = w.freigeben(w.a, "customer_documents", [999_999])
    assert fremd.status_code == unbekannt.status_code == 404 and fremd.json() == unbekannt.json() == {"detail": pf.MELDUNG_FREMD}


def test_eigene_die_nicht_gilt_409_mit_grund(w):
    d = w.projektdokument(w.projekt(w.a, muster=True))
    r = w.freigeben(w.a, "project_documents", [d.id])
    assert r.status_code == 409 and r.json()["detail"] == "Lässt sich nicht freigeben: Projekt ist ein Mustervorgang."


def test_nur_pdf_und_bilder_bis_25_mb(w):
    assert w.freigeben(w.a, "customer_documents", [w.dokument(w.a, typ="application/zip").id]).json()["detail"] == pf.MELDUNG_TYP
    assert w.freigeben(w.a, "customer_documents", [w.dokument(w.a, groesse=25 * 2**20 + 1).id]).json()["detail"] == pf.MELDUNG_GROESSE
    for typ in pf.FREIGEBBAR_TYPEN + (None,):  # ohne gespeicherten Typ entscheidet der Postbote am Inhalt
        assert w.freigeben(w.a, "customer_documents", [w.dokument(w.a, typ=typ, groesse=25 * 2**20).id]).status_code == 200, typ


def test_noch_bei_anderem_kunden_klare_meldung(w):
    """Vorgemerkt am 26.11.2026: die Quelle wechselt den Kunden, ihre Freigabe beim bisherigen ruht -- eine neue scheitert sonst am Index „höchstens eine
    je Quelle“. Die Meldung nennt den bisherigen Kunden; nach dem Zurücknehmen dort geht es."""
    p = w.projekt(w.a)
    d = w.projektdokument(p)
    alt = w.freigeben(w.a, "project_documents", [d.id]).json()["neu"][0]
    p.customer_id = w.b.id
    w.db.commit()
    eintrag = w.client.get(w.url(w.a)).json()["eintraege"][0]
    assert (eintrag["zustand"], eintrag["grund"]) == ("ruht", "gehört heute zu einem anderen Kunden")
    r = w.freigeben(w.b, "project_documents", [d.id])
    assert r.status_code == 409 and r.json()["detail"] == ("Diese Unterlage ist noch bei Kunde K-1001 (Herr Muster) freigegeben (dort ruht sie) – erst beim "
                                                           "bisherigen Kunden zurücknehmen.")
    assert w.client.post(w.url(w.a, f"/{alt}/zuruecknehmen"), json={}).status_code == 200
    assert w.freigeben(w.b, "project_documents", [d.id]).status_code == 200


def test_gleichzeitig_freigegeben_ohne_500(w, monkeypatch):
    """Zwei freigeben dieselbe Quelle zugleich: der zweite scheitert am Index, nicht mit 500 -- mit derselben Meldung wie oben."""
    d = w.dokument(w.a)
    w.db.add(PortalFreigabe(customer_id=w.b.id, art="dokument", quelle="customer_documents", quelle_id=d.id, titel="x", datum=date(2026, 11, 20),
                            freigegeben_am=datetime(2026, 11, 20)))
    w.db.commit()
    echt = pf._bestehend
    aufrufe = []

    def erst_nicht_gesehen(db, quelle, qid):
        aufrufe.append(qid)
        return None if len(aufrufe) == 1 else echt(db, quelle, qid)

    monkeypatch.setattr(pf, "_bestehend", erst_nicht_gesehen)
    r = w.freigeben(w.a, "customer_documents", [d.id])
    assert r.status_code == 409 and "erst beim bisherigen Kunden zurücknehmen" in r.json()["detail"] and "K-1002" in r.json()["detail"]


def test_zuruecknehmen(w):
    fid = w.freigeben(w.a, "customer_documents", [w.dokument(w.a).id]).json()["neu"][0]
    r = w.client.post(w.url(w.a, f"/{fid}/zuruecknehmen"), json={"grund": "falsches Dokument"})
    assert r.status_code == 200
    e = r.json()["eintraege"][0]
    assert (e["zustand"], e["grund"], e["zurueckgenommen_von"]) == ("zurueckgenommen", "falsches Dokument", "Auri Auftrag")
    assert w.client.post(w.url(w.a, f"/{fid}/zuruecknehmen"), json={}).json()["detail"] == "Schon zurückgenommen."
    assert len(w.zeilen()) == 1  # die Zeile bleibt


def test_zuruecknehmen_nur_beim_eigenen_kunden(w):
    fid = w.freigeben(w.a, "customer_documents", [w.dokument(w.a).id]).json()["neu"][0]
    r = w.client.post(w.url(w.b, f"/{fid}/zuruecknehmen"), json={})
    assert r.status_code == 404 and w.zeilen()[0].zurueckgenommen_am is None
    assert w.client.post(w.url(w.b, f"/{fid}/erneut")).status_code == 404


def test_im_archiv_zuruecknehmen_ja_freigeben_nein(w):
    fid = w.freigeben(w.a, "customer_documents", [w.dokument(w.a).id]).json()["neu"][0]
    d = w.dokument(w.a)
    w.a.archiviert_am = datetime(2026, 11, 26)
    w.db.commit()
    assert w.freigeben(w.a, "customer_documents", [d.id]).status_code == 409
    r = w.client.post(w.url(w.a, f"/{fid}/zuruecknehmen"), json={})
    assert r.status_code == 200 and r.json()["kunde_archiv"] is True


def test_erneut(w):
    fid = w.freigeben(w.a, "customer_documents", [w.dokument(w.a).id]).json()["neu"][0]
    assert w.client.post(w.url(w.a, f"/{fid}/erneut")).json()["detail"] == "Die Kopie ist nicht gescheitert."
    f = w.zeilen()[0]
    f.kopie_fehler = "nicht_lesbar"
    w.db.commit()
    e = w.client.get(w.url(w.a)).json()["eintraege"][0]
    assert (e["zustand"], e["grund"]) == ("gescheitert", "Datei nicht lesbar")
    r = w.client.post(w.url(w.a, f"/{fid}/erneut"))
    assert r.status_code == 200 and r.json()["eintraege"][0]["zustand"] == "wird_vorbereitet" and w.zeilen()[0].kopie_fehler is None
    w.client.post(w.url(w.a, f"/{fid}/zuruecknehmen"), json={})
    f = w.zeilen()[0]
    f.kopie_fehler = "nicht_lesbar"
    w.db.commit()
    assert w.client.post(w.url(w.a, f"/{fid}/erneut")).json()["detail"] == "Zurückgenommen – erst neu freigeben."


def test_sichtbar_und_ruht(w):
    p = w.projekt(w.a)
    fid = w.freigeben(w.a, "project_documents", [w.projektdokument(p).id]).json()["neu"][0]
    f = w.zeilen()[0]
    f.kopie_name, f.kopie_typ, f.kopie_bereit_am = "a" * 64 + ".pdf", "application/pdf", datetime(2026, 11, 27)
    w.db.commit()
    e = w.client.get(w.url(w.a)).json()["eintraege"][0]
    assert (e["id"], e["zustand"], e["auftrag"], e["objekt"]) == (fid, "sichtbar", None, "Hafenweg 3, 12345 Musterstadt")
    p.archived = True
    w.db.commit()
    e = w.client.get(w.url(w.a)).json()["eintraege"][0]
    assert (e["zustand"], e["grund"]) == ("ruht", "Projekt im Archiv")
    historie = w.db.scalars(select(AuditLog).where(AuditLog.entity_type == "Freigabe im Kundenportal")).all()
    assert all("kopie" not in (h.field_name or "") and "a" * 64 not in (h.new_value or "") for h in historie)


def test_unterlagen_fuer_den_dialog(w):
    p = w.projekt(w.a)
    fotos = w.fotos(p, 2)
    w.freigeben(w.a, "service_report_photos", fotos[:1])
    r = w.client.get("/api/portal-freigaben/unterlagen", params=[("quelle", "service_report_photos")] + [("quelle_ids", i) for i in fotos + [999_999]])
    assert r.status_code == 200, r.text
    eins, zwei, fehlt = r.json()
    assert (eins["customer_id"], eins["freigebbar"], eins["bestehend"]["zustand"], eins["bestehend"]["anderer_kunde"]) == (w.a.id, False,
                                                                                                                          "wird_vorbereitet", False)
    assert (zwei["freigebbar"], zwei["bestehend"], zwei["art"]) == (True, None, "foto") and zwei["titel_vorschlag"].startswith("Foto vom ")
    assert (fehlt["customer_id"], fehlt["freigebbar"], fehlt["grund"]) == (None, False, pf.MELDUNG_FREMD)
    zip_ = w.dokument(w.a, typ="application/zip")
    r = w.client.get("/api/portal-freigaben/unterlagen", params={"quelle": "customer_documents", "quelle_ids": zip_.id}).json()[0]
    assert (r["freigebbar"], r["grund"]) == (False, pf.MELDUNG_TYP)
    assert w.client.get("/api/portal-freigaben/unterlagen", params={"quelle": "lohn", "quelle_ids": 1}).status_code == 422


@pytest.mark.parametrize("rolle, erwartet", [("field", 403), ("buero_auftrag", 200), ("buero_finanzen", 200), ("admin", 200)])
def test_rollen(threaded_db_session, router_test_client, rolle, erwartet):
    db = threaded_db_session
    db.add(EnabledModule(module_key="kundenportal", enabled=True))
    db.commit()
    w = Welt(db, router_test_client(db, portal_freigaben.router, role=rolle, user_id=12, display_name="Konto"))
    d = w.dokument(w.a)
    assert w.client.get(w.url(w.a)).status_code == erwartet
    assert w.freigeben(w.a, "customer_documents", [d.id]).status_code == erwartet
    assert w.client.get("/api/portal-freigaben/unterlagen", params={"quelle": "customer_documents", "quelle_ids": d.id}).status_code == erwartet


def test_modul_aus(threaded_db_session, router_test_client):
    db = threaded_db_session
    w = Welt(db, router_test_client(db, portal_freigaben.router, role="admin", user_id=13, display_name="Admin"))
    d = w.dokument(w.a)
    assert w.client.get(w.url(w.a)).status_code == 403
    assert w.freigeben(w.a, "customer_documents", [d.id]).status_code == 403
    assert w.client.get("/api/portal-freigaben/unterlagen", params={"quelle": "customer_documents", "quelle_ids": d.id}).status_code == 403
    assert w.zeilen() == []
