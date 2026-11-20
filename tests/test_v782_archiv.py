"""Version 1.10.11 (Stufe W1c): Archiv nach dem letzten Kontakt -- nur Musterdaten.

    Rechnung     letzter Kontakt mit Herkunft (Eingang, Anlage, Besichtigung, Vermerk, Angebot nicht Entwurf, Versand, Termin, Zurückholen), fällig ab
                 = + 6 Monate (Monatsende), Sperren (offene Aufgabe, Vorlage eines Wartungsvertrags), Kunde nur ohne Auftrag, ohne Import, ohne
                 Bindung -- NULL in Fremdschlüsseln anderer Zeilen blockiert nichts (kein NOT IN)
    Bestätigen   einzeln (Eingang, Anfrage, Projekt, Kunde mit seinen fälligen Vorgängen), gesammelt nur mit der Prüfsumme der Vorschau; nicht fällig
                 übersprungen mit Grund; Admin und Büro – Finanzen, sonst 403
    Archiv       raus aus Kunden-, Objekt- und Anfragenliste, Büro-Suche (Kunden, Objekte, Anfragen, Projekte ohne Auftrag, Angebote), Suche der
                 Monteurin, Eingang der Webseite (Listen, Zähler, Aktionen 409), Vorschlag und Suche beim Übernehmen, Fotokopien am Objekt; über die
                 Kennung lesbar
    Zurückholen  Büro ab Auftrag; die 6 Monate zählen neu; Anfrage und Projekt holen ihren Kunden mit
    Sperren      kein neuer Vorgang an einem Kunden im Archiv, kein Wechsel dorthin, kein Kontaktvermerk im Archiv
    Von Hand     Archivieren über das „⋮“ der Akte setzt Zeitpunkt, nimmt Anfrage und Eingang mit; Entarchivieren zählt als Zurückholen
    Historie     „archiviert“ / „zurückgeholt“ unter der vorhandenen Art, ohne Inhalte
    Migration    Spalten, downgrade bricht mit Archiv ab -- SQLite und PostgreSQL
"""

import importlib.util
import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, text

from app import aufbewahrung as A
from app.models import (AppUser, AuditLog, CalendarEvent, Contact, Customer, CustomerProfile, EmailDispatch, Inquiry, Invoice, Kontaktvermerk, MaintenanceContract,
                        Order, Project, Property, PropertyDocument, Quote, QuoteDocumentMeta, Task, WebAnfrage)
from app.project_pipeline_columns import default_pipeline_column_id
from app.routers import aufbewahrung as aufbewahrung_router
from app.routers import customers as kunden_router
from app.routers import inquiries as anfragen_router
from app.routers import kontaktvermerke as kontakt_router
from app.routers import projects as projekte_router
from app.routers import properties as objekte_router
from app.search import _search_customers, _search_inquiries, _search_projects, _search_quotes, search_properties_for_field
from tests.quellangebot import quell_angebot

ROOT = Path(__file__).resolve().parent.parent


def vor(tage: int) -> datetime:
    return datetime.utcnow() - timedelta(days=tage)


ALT, JUNG = 250, 100  # Tage: älter bzw. jünger als 6 Monate


class Welt:
    def __init__(self, db):
        self.db, self.n = db, 0

    def kunde(self, name="Erika Muster", tage=ALT, **mehr) -> Customer:
        self.n += 1
        c = Customer(name=name, last_name=name, city="Musterstadt", created_at=vor(tage), **mehr)
        self.db.add(c)
        self.db.flush()
        self.db.add(CustomerProfile(customer_id=c.id, customer_number=f"K-{self.n:04d}"))
        self.db.add(Property(customer_id=c.id, name="Hauptadresse", street="Musterweg 1", postal_code="12345", city="Musterstadt",
                             is_primary_address=True))
        self.db.flush()
        return c

    def anfrage(self, kunde, tage=ALT, **mehr) -> Inquiry:
        self.n += 1
        a = Inquiry(inquiry_number=f"AN-{self.n:04d}", customer_id=kunde.id, title="Dachrinne", created_at=vor(tage), **mehr)
        self.db.add(a)
        self.db.flush()
        return a

    def projekt(self, kunde, tage=ALT, **mehr) -> Project:
        self.n += 1
        p = Project(project_number=f"P-{self.n:04d}", name="Dach", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(self.db),
                    created_at=vor(tage), **mehr)
        self.db.add(p)
        self.db.flush()
        return p

    def auftrag(self, projekt) -> Order:
        self.n += 1
        nummer = f"AUF-{self.n:04d}"
        o = Order(order_number=nummer, project_id=projekt.id, source_quote_id=quell_angebot(self.db, projekt.id, nummer), quote_number_snapshot="Q",
                  title="Dach", customer_name="x", customer_id=projekt.customer_id)
        self.db.add(o)
        self.db.flush()
        return o

    def eingang(self, tage=ALT, status="neu", grund=None, inquiry=None, eingang=True) -> WebAnfrage:
        self.n += 1
        w = WebAnfrage(nummer=f"R-20260101-0900-{self.n:04X}", fassung="dk-anfrage/1", umschlag="{}", umschlag_sha256="0" * 64, status=status,
                       verworfen_grund=grund, eingang_am=vor(tage) if eingang else None, abgeholt_am=vor(tage), inquiry_id=inquiry.id if inquiry else None,
                       betreff="Musterweg 1")
        self.db.add(w)
        self.db.flush()
        return w


@pytest.fixture
def welt(threaded_db_session):
    return Welt(threaded_db_session)


def _c(db, router_test_client, rolle="buero_finanzen"):
    return router_test_client(db, aufbewahrung_router.router, kunden_router.router, anfragen_router.router, projekte_router.router,
                              objekte_router.router, kontakt_router.router, role=rolle, user_id=7, display_name="Fritz Finanzen")


def _vorgaenge(v):
    return {(x["art"], x["id"]): x for g in v["kunden"] for x in g["vorgaenge"]} | {(x["art"], x["id"]): x for x in v["eingaenge"]}


# --- Rechnung -----------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("tag, monate, erwartet", [
    (date(2026, 5, 15), 6, date(2026, 11, 15)), (date(2026, 8, 31), 6, date(2027, 2, 28)), (date(2027, 8, 31), 6, date(2028, 2, 29)),
    (date(2026, 12, 31), 6, date(2027, 6, 30)), (date(2026, 7, 1), 6, date(2027, 1, 1)),
])
def test_monate_spaeter(tag, monate, erwartet):
    assert A.monate_spaeter(tag, monate) == erwartet


def test_anfrage_und_kunde_faellig(welt, threaded_db_session):
    db = welt.db
    k = welt.kunde()
    a = welt.anfrage(k)
    db.commit()
    v = A.vorschau(db)
    g = next(g for g in v["kunden"] if g["id"] == k.id)
    x = _vorgaenge(v)[("anfrage", a.id)]
    assert x["faellig"] and x["letzter_kontakt"]["herkunft"] == f"Anfrage {a.inquiry_number} angelegt"
    assert g["faellig"] and g["gruende"] == []
    assert v["zahl"] == 2


def test_juengerer_kontakt_haelt_den_vorgang(welt):
    db = welt.db
    k = welt.kunde()
    a1, a2, a3 = welt.anfrage(k), welt.anfrage(k), welt.anfrage(k)
    db.add(Kontaktvermerk(inquiry_id=a1.id, kontakt_am=vor(JUNG).date(), weg="telefon"))
    a2.visit_at = datetime.now() - timedelta(days=JUNG)  # vergangene Besichtigung (naive Ortszeit)
    a3.visit_at = datetime.now() + timedelta(days=30)  # künftige: kein Kontakt
    db.commit()
    v = _vorgaenge(A.vorschau(db))
    assert ("anfrage", a1.id) not in v and ("anfrage", a2.id) not in v
    assert v[("anfrage", a3.id)]["faellig"]
    stand = A.berechnen(db)
    assert stand.vorgaenge[("anfrage", a1.id)].kontakt.herkunft == "Kontakt vermerkt (Telefon)"
    assert stand.vorgaenge[("anfrage", a2.id)].kontakt.herkunft == "Besichtigung"
    assert not stand.kunden[k.id].faellig(stand.heute)  # zwei Vorgänge nicht fällig -- der Kunde bleibt


def test_eingang_der_webseite_zaehlt_fuer_die_anfrage(welt):
    db = welt.db
    k = welt.kunde()
    a = welt.anfrage(k, tage=ALT)
    w = welt.eingang(tage=JUNG, status="uebernommen", inquiry=a)
    db.commit()
    stand = A.berechnen(db)
    assert stand.vorgaenge[("anfrage", a.id)].kontakt.herkunft == f"Eingang der Webseite {w.nummer}"
    assert not stand.vorgaenge[("anfrage", a.id)].faellig(stand.heute)


def test_projekt_kontakte_und_sperren(welt):
    db = welt.db
    k = welt.kunde()
    p_angebot, p_entwurf, p_termin, p_aufgabe, p_vorlage, p_versand = (welt.projekt(k) for _ in range(6))
    for p, status in ((p_angebot, "versendet"), (p_entwurf, "entwurf")):
        q = Quote(quote_number=f"A-{p.id}", project_id=p.id, title="Dach", status=status)
        db.add(q)
        db.flush()
        db.add(QuoteDocumentMeta(quote_id=q.id, quote_date=vor(JUNG).date()))
    q = Quote(quote_number=f"A-{p_versand.id}", project_id=p_versand.id, title="Dach", status="versendet")
    db.add(q)
    db.flush()
    db.add(QuoteDocumentMeta(quote_id=q.id, quote_date=vor(ALT).date()))
    db.add(EmailDispatch(dispatch_key="k1", message_ref=str(uuid.uuid4()), status="gesendet", channel="email", document_type="angebot",
                         document_id=q.id, to_recipients="x@example.com", subject="Angebot", created_at=vor(JUNG)))
    konto = AppUser(username="anna", display_name="Anna", password_hash="x", role="admin")
    db.add(konto)
    db.flush()
    db.add(CalendarEvent(title="Aufmaß", start_at=datetime.now() - timedelta(days=JUNG), end_at=datetime.now() - timedelta(days=JUNG),
                         project_id=p_termin.id, owner_user_id=konto.id))
    db.add(Task(title="Rückruf", project_id=p_aufgabe.id, status="offen"))
    db.add(MaintenanceContract(customer_id=welt.kunde(name="Vertragskunde").id, template_project_id=p_vorlage.id, title="Wartung",
                               next_due_date=date(2027, 1, 1)))
    db.commit()
    stand = A.berechnen(db)
    v = {pid: stand.vorgaenge[("projekt", pid)] for pid in (p_angebot.id, p_entwurf.id, p_termin.id, p_aufgabe.id, p_vorlage.id, p_versand.id)}
    assert v[p_angebot.id].kontakt.herkunft.startswith(f"Angebot A-{p_angebot.id} vom") and not v[p_angebot.id].faellig(stand.heute)
    assert v[p_entwurf.id].faellig(stand.heute)  # ein Entwurf ist kein Kontakt
    assert v[p_termin.id].kontakt.herkunft == "Termin" and not v[p_termin.id].faellig(stand.heute)
    assert v[p_versand.id].kontakt.herkunft == f"Angebot A-{p_versand.id} per E-Mail versendet"
    assert v[p_aufgabe.id].sperren == ["offene Aufgabe am Projekt"] and not v[p_aufgabe.id].faellig(stand.heute)
    assert v[p_vorlage.id].sperren == ["Vorlage eines Wartungsvertrags"]


def test_mit_auftrag_kein_vorgang_und_kunde_bleibt(welt):
    db = welt.db
    k, k2 = welt.kunde(), welt.kunde(name="Storniert")
    p, p2 = welt.projekt(k), welt.projekt(k2)
    welt.auftrag(p)
    welt.auftrag(p2).status = "storniert"  # ein stornierter Auftrag war ein Vertrag -- zählt als Auftrag
    db.commit()
    stand = A.berechnen(db)
    assert ("projekt", p.id) not in stand.vorgaenge and k.id not in stand.kunden
    assert ("projekt", p2.id) not in stand.vorgaenge and k2.id not in stand.kunden


def test_kunde_aus_dem_import_und_gebundene_nie(welt):
    db = welt.db
    import_kunde = welt.kunde(name="Altkunde", legacy_address_number="4711")
    adressbuch = welt.kunde(name="Architekt")
    db.add(Contact(last_name="Architekt", customer_id=adressbuch.id))
    muster = welt.kunde(name="Musterkunde")
    welt.projekt(muster, is_template=True)
    db.commit()
    stand = A.berechnen(db)
    assert stand.kunden[import_kunde.id].gruende == ["aus dem Adressimport -- nie automatisch"]
    assert stand.kunden[adressbuch.id].gruende == ["im Adressbuch verknüpft"]
    assert stand.kunden[muster.id].gruende == ["Kunde eines Mustervorgangs"]
    assert not any(stand.kunden[x].faellig(stand.heute) for x in (import_kunde.id, adressbuch.id, muster.id))


def test_leere_fremdschluessel_anderer_zeilen_sperren_nichts(welt):
    """Hinweis des Betriebs: NOT IN über eine Spalte mit NULL liefert still nichts. Hier stehen NULL in invoices.customer_id, contacts.customer_id,
    maintenance_contracts.property_id und webanfragen.inquiry_id -- der Kunde ohne alles ist trotzdem fällig."""
    db = welt.db
    k = welt.kunde()
    anderer = welt.kunde(name="Anderer")
    p = welt.projekt(anderer)
    o = welt.auftrag(p)
    db.add(Invoice(order_id=o.id, invoice_number=None, invoice_type="abschlag_pauschal", customer_name="x", status="entwurf", customer_id=None))
    db.add(Contact(last_name="Lieferant ohne Kunde", customer_id=None))
    db.add(MaintenanceContract(customer_id=anderer.id, property_id=None, title="Wartung", next_due_date=date(2027, 1, 1)))
    welt.eingang(status="neu")
    db.commit()
    stand = A.berechnen(db)
    assert stand.kunden[k.id].faellig(stand.heute) and stand.kunden[k.id].gruende == []


def test_objekt_an_einem_vorgang_eines_anderen_kunden(welt):
    db = welt.db
    k, hv = welt.kunde(), welt.kunde(name="Hausverwaltung")
    objekt = db.scalar(select(Property).where(Property.customer_id == k.id))
    welt.anfrage(hv, tage=JUNG, property_id=objekt.id)
    db.commit()
    stand = A.berechnen(db)
    assert stand.kunden[k.id].gruende == ["Anfrage eines anderen Kunden an einem Objekt"]


def test_eingaenge(welt):
    db = welt.db
    neu, sonstiges, spam, jung, ohne_eingang = (welt.eingang(status="neu"), welt.eingang(status="verworfen", grund="sonstiges"),
                                                welt.eingang(status="verworfen", grund="spam"), welt.eingang(tage=JUNG),
                                                welt.eingang(eingang=False))
    db.commit()
    v = A.vorschau(db)
    ids = {x["id"]: x for x in v["eingaenge"]}
    assert set(ids) == {neu.id, sonstiges.id, ohne_eingang.id}  # Spam löscht 1.10.13, der junge ist nicht fällig
    assert ids[neu.id]["unbearbeitet"] and not ids[sonstiges.id]["unbearbeitet"] and v["unbearbeitet"] == 2
    assert ids[ohne_eingang.id]["letzter_kontakt"]["herkunft"] == "Eingang der Webseite"  # ohne Eingang: abgeholt


# --- Bestätigen ---------------------------------------------------------------------------------------------------------------------------------

def test_rechte(welt, router_test_client):
    db = welt.db
    k = welt.kunde()
    a = welt.anfrage(k)
    db.commit()
    for rolle, lesen, archivieren in (("field", 403, 403), ("buero_auftrag", 200, 403), ("buero_finanzen", 200, 200), ("admin", 200, 200)):
        c = _c(db, router_test_client, rolle)
        assert c.get("/api/aufbewahrung").status_code == lesen
        assert c.get("/api/aufbewahrung/archiv").status_code == lesen
        r = c.post(f"/api/aufbewahrung/kunde/{k.id}/archivieren")
        assert r.status_code == archivieren, (rolle, r.text)
    db.expire_all()
    assert db.get(Inquiry, a.id).archiviert_am is not None  # Büro – Finanzen hat archiviert, der Admin fand nichts mehr
    assert _c(db, router_test_client, "field").post(f"/api/aufbewahrung/anfrage/{a.id}/zurueckholen").status_code == 403
    assert _c(db, router_test_client, "buero_auftrag").post(f"/api/aufbewahrung/anfrage/{a.id}/zurueckholen").status_code == 200
    assert _c(db, router_test_client, "buero_auftrag").post(f"/api/aufbewahrung/anfrage/{a.id}/zurueckholen").status_code == 409  # nicht im Archiv


def test_einzeln_und_nicht_faellig(welt, router_test_client):
    db = welt.db
    k = welt.kunde()
    a, jung = welt.anfrage(k), welt.anfrage(k, tage=JUNG)
    db.commit()
    c = _c(db, router_test_client)
    r = c.post(f"/api/aufbewahrung/anfrage/{jung.id}/archivieren").json()
    assert r["archiviert"] == [] and r["uebersprungen"][0]["grund"].startswith("erst ab ")
    r = c.post(f"/api/aufbewahrung/anfrage/{a.id}/archivieren").json()
    assert [x["id"] for x in r["archiviert"]] == [a.id]
    r = c.post(f"/api/aufbewahrung/kunde/{k.id}/archivieren").json()
    assert r["archiviert"] == [] and r["uebersprungen"][0]["grund"].startswith("erst ab ")  # sein letzter Kontakt ist die junge Anfrage
    assert c.post(f"/api/aufbewahrung/anfrage/{2_147_483_648}/archivieren").status_code == 404
    db.expire_all()
    assert db.get(Inquiry, a.id).archiviert_am is not None and db.get(Inquiry, a.id).archiviert_von_user_id == 7


def test_kunde_nimmt_seine_vorgaenge_mit_und_verschwindet(welt, router_test_client):
    db = welt.db
    k = welt.kunde(name="Zacharias Muster")
    a = welt.anfrage(k)
    p = welt.projekt(k)
    pa = welt.anfrage(k, project_id=p.id)
    w = welt.eingang(status="uebernommen", inquiry=pa)
    objekt = db.scalar(select(Property).where(Property.customer_id == k.id))
    db.add(PropertyDocument(property_id=objekt.id, category_id=1, original_filename=f"{w.nummer}-foto-1.jpg", stored_filename="x.jpg",
                            description=f"Foto der Anfrage der Webseite {w.nummer}", webanfrage_id=w.id))
    db.commit()
    c = _c(db, router_test_client)
    r = c.post(f"/api/aufbewahrung/kunde/{k.id}/archivieren").json()
    assert sorted((x["art"], x["id"]) for x in r["archiviert"]) == sorted([("anfrage", a.id), ("projekt", p.id), ("kunde", k.id)])
    db.expire_all()
    assert db.get(Project, p.id).archived and db.get(Inquiry, pa.id).archiviert_am and db.get(WebAnfrage, w.id).archiviert_am
    assert k.id not in [x["id"] for x in c.get("/api/customers").json()]
    assert k.id in [x["id"] for x in c.get("/api/customers?archivierte=true").json()]
    assert objekt.id not in [x["id"] for x in c.get("/api/properties").json()]
    mit = [x for x in c.get(f"/api/properties?archivierte=true&customer_id={k.id}").json()]
    assert [x["kunde_im_archiv"] for x in mit] == [True]
    assert a.id not in [x["id"] for x in c.get("/api/inquiries").json()]
    assert {x["id"] for x in c.get(f"/api/inquiries?archivierte=true&customer_id={k.id}").json()} == {a.id, pa.id}
    assert c.get(f"/api/customers/{k.id}").status_code == 200  # über die Kennung lesbar
    for suche in (_search_customers, _search_inquiries, _search_projects):
        assert suche(db, "Zacharias", 10)[0] == 0
    assert search_properties_for_field(db, "Zacharias") == []
    from app.property_documents import list_merged_documents_for_property
    assert list_merged_documents_for_property(db, objekt.id) == []


def test_gesammelt_nur_mit_der_pruefsumme(welt, router_test_client):
    db = welt.db
    k = welt.kunde()
    a = welt.anfrage(k)
    w = welt.eingang()
    db.commit()
    c = _c(db, router_test_client)
    v = c.get("/api/aufbewahrung").json()
    welt.anfrage(welt.kunde(name="Neu dazu"))  # fällig geworden nach der Vorschau
    db.commit()
    assert c.post("/api/aufbewahrung/archivieren", json={"stand": v["stand"]}).status_code == 409
    db.expire_all()
    assert db.get(Inquiry, a.id).archiviert_am is None  # nichts archiviert
    v = c.get("/api/aufbewahrung").json()
    assert c.post("/api/aufbewahrung/archivieren", json={"stand": "x" * 16}).status_code == 422
    r = c.post("/api/aufbewahrung/archivieren", json={"stand": v["stand"]}).json()
    assert len(r["archiviert"]) == v["zahl"] == 5 and r["uebersprungen"] == []
    assert c.get("/api/aufbewahrung").json()["zahl"] == 0
    assert {(x["art"], x["id"]) for x in c.get("/api/aufbewahrung/archiv").json()["vorgaenge"]} >= {("anfrage", a.id), ("eingang", w.id)}


def test_zurueckholen_zaehlt_neu_und_holt_den_kunden(welt, router_test_client):
    db = welt.db
    k = welt.kunde()
    a = welt.anfrage(k)
    db.commit()
    c = _c(db, router_test_client, "buero_finanzen")
    c.post(f"/api/aufbewahrung/kunde/{k.id}/archivieren")
    r = _c(db, router_test_client, "buero_auftrag").post(f"/api/aufbewahrung/anfrage/{a.id}/zurueckholen").json()
    assert r == {"art": "anfrage", "id": a.id, "kunde_mit": True}
    db.expire_all()
    assert db.get(Customer, k.id).archiviert_am is None and db.get(Inquiry, a.id).zurueckgeholt_am is not None
    stand = A.berechnen(db)
    assert stand.vorgaenge[("anfrage", a.id)].kontakt.herkunft == "aus dem Archiv zurückgeholt"
    assert not stand.vorgaenge[("anfrage", a.id)].faellig(stand.heute)


def test_im_archiv_nichts_neues(welt, router_test_client):
    db = welt.db
    k, aktiv = welt.kunde(), welt.kunde(name="Aktiv")
    a = welt.anfrage(k)
    p = welt.projekt(aktiv, tage=JUNG)
    db.commit()
    c = _c(db, router_test_client, "admin")
    c.post(f"/api/aufbewahrung/kunde/{k.id}/archivieren")
    assert c.post("/api/inquiries", json={"customer_id": k.id, "title": "Neu"}).status_code == 409
    assert c.post("/api/projects", json={"customer_id": k.id, "name": "Neu"}).status_code == 409
    projekt = c.get(f"/api/projects/{p.id}").json()
    r = c.put(f"/api/projects/{p.id}", json={"customer_id": k.id, "property_id": None, "name": projekt["name"], "description": None})
    assert r.status_code == 409, r.text
    for adresse in (f"/api/inquiries/{a.id}/kontakte", f"/api/customers/{k.id}/kontakte"):
        assert c.post(adresse, json={"kontakt_am": date.today().isoformat(), "weg": "telefon"}).status_code == 409


def test_von_hand_ueber_die_akte(welt, router_test_client):
    db = welt.db
    k = welt.kunde()
    p = welt.projekt(k, tage=JUNG)
    pa = welt.anfrage(k, project_id=p.id)
    db.commit()
    c = _c(db, router_test_client, "buero_auftrag")
    assert c.post(f"/api/projects/{p.id}/archive").status_code == 200
    db.expire_all()
    assert db.get(Project, p.id).archiviert_am is not None and db.get(Inquiry, pa.id).archiviert_am is not None
    db.execute(text("UPDATE customers SET archiviert_am = :t WHERE id = :k"), {"t": datetime.utcnow(), "k": k.id})
    db.commit()
    assert c.post(f"/api/projects/{p.id}/unarchive").status_code == 200
    db.expire_all()
    assert (db.get(Project, p.id).archived, db.get(Project, p.id).archiviert_am, db.get(Inquiry, pa.id).archiviert_am) == (False, None, None)
    assert db.get(Customer, k.id).archiviert_am is None and db.get(Project, p.id).zurueckgeholt_am is not None


def test_historie_ohne_inhalte(welt, router_test_client):
    db = welt.db
    k = welt.kunde()
    p = welt.projekt(k)
    db.commit()
    c = _c(db, router_test_client)
    c.post(f"/api/aufbewahrung/projekt/{p.id}/archivieren")
    c.post(f"/api/aufbewahrung/projekt/{p.id}/zurueckholen")
    zeilen = db.scalars(select(AuditLog).where(AuditLog.field_name == "archiv").order_by(AuditLog.id)).all()
    assert [(z.action, z.entity_type, z.entity_label, z.project_id, z.old_value, z.new_value) for z in zeilen] == [
        ("archiviert", "Projekt", p.project_number, p.id, "aktiv", "im Archiv"), ("zurückgeholt", "Projekt", p.project_number, p.id, "im Archiv", "aktiv")]


def test_eingang_im_archiv_in_keiner_liste_und_ohne_aktion(welt, router_test_client):
    from app import webanfragen as W
    from app.routers import webanfragen as web_router
    db = welt.db
    w = welt.eingang()
    db.commit()
    c = router_test_client(db, aufbewahrung_router.router, web_router.router, role="admin", user_id=7)
    vorher = W.stand(db)["neu"]
    c.post(f"/api/aufbewahrung/eingang/{w.id}/archivieren")
    assert W.stand(db)["neu"] == vorher - 1
    for ansicht in ("eingang", "pruefliste", "erledigt"):
        assert w.id not in [x["id"] for x in c.get(f"/api/webanfragen?ansicht={ansicht}").json()]
    assert c.get(f"/api/webanfragen/{w.id}").status_code == 200  # über die Kennung lesbar
    assert c.post(f"/api/webanfragen/{w.id}/verwerfen", json={"grund": "sonstiges"}).status_code == 409


# --- Migration ----------------------------------------------------------------------------------------------------------------------------------

def _modul():
    pfad = next((ROOT / "alembic" / "versions").glob("*_archiv_aufbewahrung.py"))
    spec = importlib.util.spec_from_file_location("migration_archiv_aufbewahrung", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _bestand_pruefen(conn) -> None:
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext
    conn.execute(text("CREATE TABLE app_users (id INTEGER PRIMARY KEY)"))
    for tabelle in ("webanfragen", "inquiries", "customers", "projects"):
        conn.execute(text(f"CREATE TABLE {tabelle} (id INTEGER PRIMARY KEY, name VARCHAR(20))"))
        conn.execute(text(f"INSERT INTO {tabelle} (id, name) VALUES (1, 'x')"))
    modul = _modul()
    with Operations.context(MigrationContext.configure(conn)):
        modul.upgrade()
    for tabelle in ("webanfragen", "inquiries", "customers", "projects"):
        spalten = {c["name"] for c in inspect(conn).get_columns(tabelle)}
        assert {"archiviert_am", "archiviert_von_user_id", "zurueckgeholt_am"} <= spalten
        assert conn.execute(text(f"SELECT archiviert_am FROM {tabelle}")).scalar() is None
    conn.execute(text("UPDATE customers SET archiviert_am = CURRENT_TIMESTAMP"))
    with Operations.context(MigrationContext.configure(conn)):
        with pytest.raises(RuntimeError, match="customers"):
            modul.downgrade()
    conn.execute(text("UPDATE customers SET archiviert_am = NULL"))
    with Operations.context(MigrationContext.configure(conn)):
        modul.downgrade()
    assert "archiviert_am" not in {c["name"] for c in inspect(conn).get_columns("projects")}
    assert conn.execute(text("SELECT name FROM customers")).scalar() == "x"


def test_migration_sqlite(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'bestand.db').as_posix()}")
    try:
        with engine.begin() as conn:
            _bestand_pruefen(conn)
    finally:
        engine.dispose()


def test_migration_postgresql():
    url = os.getenv("ERP_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_w1c_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        with engine.begin() as conn:
            _bestand_pruefen(conn)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()

# --- Seiten: ein gespeicherter Kunde im Archiv bleibt gewählt, neu angeboten nur aktive -----------------------------------------------------------

from tests.test_v334_auswahl_restfaelle import nur_mit_node  # noqa: E402
from tests.test_v450_auswahl_fremdschluessel import _lauf  # noqa: E402

KUNDEN = [{"id": 1, "customer_number": "K-1", "name": "Aktiv", "archiviert_am": None},
          {"id": 2, "customer_number": "K-2", "name": "Gespeichert", "archiviert_am": "2026-11-01T10:00:00"},
          {"id": 3, "customer_number": "K-3", "name": "Anderer im Archiv", "archiviert_am": "2026-11-01T10:00:00"}]


@nur_mit_node
def test_akte_projekt_bearbeiten_kunde_im_archiv():
    import json
    projekt = {"id": 1, "project_number": "P-1", "name": "Halle", "status": "anfrage", "category": None, "description": "", "customer_id": 2,
               "property_id": None, "property_name": None}
    ablauf = (f"project = {json.dumps(projekt)}; customers = {json.dumps(KUNDEN)}; projectCategories = [];"
              "try { await openProjectEdit(); } catch (e) {} const s = _element('editCustomer');"
              "return [s.value, s.options.map(o => o.text)];")
    wert, texte = _lauf("akte.html", "akteStarten().catch(", ablauf, {"/api/properties?archivierte=true&customer_id=2": []})["ergebnis"]
    assert wert == "2" and texte == ["K-1 · Aktiv", "K-2 · Gespeichert (im Archiv)"]


@nur_mit_node
def test_objektformular_kunde_im_archiv():
    import json
    ablauf = (f"customers = {json.dumps(KUNDEN)}; record = {{customer_id: 2, name: 'Halle'}};  /* editing ist in node schon wahr (record_id wird 1) */ propertyForm();"
              "const f = _element('form').innerHTML; return f.slice(f.indexOf('id=\"customer\"'), f.indexOf('</select>', f.indexOf('id=\"customer\"')));")
    html = _lauf("master_data_form.html", "\ninit()", ablauf)["ergebnis"]
    assert "Gespeichert (im Archiv)" in html and "Anderer im Archiv" not in html and "Aktiv" in html
