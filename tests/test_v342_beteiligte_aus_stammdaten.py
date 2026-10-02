"""Version 1.8.39 -- Beteiligte aus den Stammdaten (siehe docs/archiv/vertragsgrundlage-und-vertrag.md,
"Umsetzung 1.8.39").

1. Der Dialog "Beteiligten hinzufügen" durchsucht Adressbuch, Kunden und Lieferanten, nach Herkunft gruppiert,
   nur was die Rolle in der Büro-Suche sieht. Mitarbeiter nicht.
2. Ein gewählter Kunde oder Lieferant wird zum Adressbuch-Eintrag mit Verweis, höchstens einer je Stammsatz,
   wiederverwendet; Name, E-Mail, Telefon und Adresse immer aktuell aus dem Stammsatz, ohne Kopie, im
   Adressbuch nicht änderbar ("aus Kundenstamm"/"aus Lieferantenstamm"); ein inaktiver Lieferant gekennzeichnet.
3. Der Kunde des Projekts kann nicht Beteiligter werden.
4. Gegenproben: Kunde in zwei Projekten -> ein Eintrag (auch gleichzeitig gegen PostgreSQL, opt-in über
   ERP_TEST_POSTGRES_URL), geänderte E-Mail im Kunden erscheint beim Beteiligten, Auftraggeber abgelehnt,
   Rollenprüfung der Suche, Monteur 403.
"""

import dataclasses
import os
import threading
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app import search as search_module
from app.address_import import _run_is_untouched
from app.audit import reset_audit_context, set_audit_context
from app.contacts import linked_contact
from app.database import Base
from app.models import AuditLog, Contact, Customer, Employee, ImportRun, Project, Supplier
from app.permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE_AUFTRAG
from app.project_participants import add_participant
from app.project_pipeline_columns import default_pipeline_column_id
from app.routers.contacts import router as contacts_router
from app.routers.project_participants import router as participants_router
from app.routers.resource_planning import router as resource_router
from app.search import search_office

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"


def _kunde(db, last_name="Hausverwaltung Hof GmbH", **werte) -> Customer:
    from app.crm import compose_customer_name

    kunde = Customer(last_name=last_name, **werte)
    kunde.name = compose_customer_name(kunde.salutation, kunde.title, kunde.first_name, last_name)
    db.add(kunde); db.commit()
    return kunde


def _lieferant(db, name="Gerüstbau Stark", **werte) -> Supplier:
    lieferant = Supplier(name=name, **werte)
    db.add(lieferant); db.commit()
    return lieferant


def _projekt(db, nummer: str, kunde: Customer | None = None) -> Project:
    kunde = kunde or _kunde(db, f"Auftraggeber {nummer}")
    projekt = Project(project_number=nummer, customer_id=kunde.id, name=f"Dach {nummer}",
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.commit()
    return projekt


def _client(router_test_client, db, role=ROLE_OFFICE_AUFTRAG):
    return router_test_client(db, contacts_router, participants_router, resource_router, role=role)


def _hinzufuegen(client, projekt, **herkunft):
    return client.post(f"/api/projects/{projekt.id}/participants", json={"role": "hausverwaltung", **herkunft})


def _kandidaten(client, projekt, q=""):
    response = client.get(f"/api/projects/{projekt.id}/participant-candidates", params={"q": q})
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# 2. Ein Eintrag je Stammsatz, Werte live
# ---------------------------------------------------------------------------

def test_kunde_in_zwei_projekten_ein_eintrag(router_test_client, threaded_db_session):
    db = threaded_db_session
    client = _client(router_test_client, db)
    kunde = _kunde(db, phone="0241 77", email="info@hof.example", street="Hofweg 1", postal_code="52062", city="Aachen")
    eins, zwei = _projekt(db, "P-1"), _projekt(db, "P-2")
    erste = _hinzufuegen(client, eins, customer_id=kunde.id)
    zweite = client.post(f"/api/projects/{zwei.id}/participants", json={"customer_id": kunde.id, "role": "eigentuemer"})
    assert erste.status_code == 200 and zweite.status_code == 200, (erste.text, zweite.text)
    assert erste.json()["contact_id"] == zweite.json()["contact_id"]
    assert db.scalar(select(func.count()).select_from(Contact).where(Contact.customer_id == kunde.id)) == 1
    eintrag = erste.json()["contact"]
    assert (eintrag["source"], eintrag["source_label"], eintrag["source_id"], eintrag["source_url"]) == \
        ("customer", "aus Kundenstamm", kunde.id, f"/customers/{kunde.id}")
    assert client.get(f"/api/contacts/{eintrag['id']}").json()["project_count"] == 2
    # Dieselbe Rolle im selben Projekt noch einmal: abgelehnt, und weiterhin ein Eintrag
    assert _hinzufuegen(client, eins, customer_id=kunde.id).status_code == 409
    assert db.scalar(select(func.count()).select_from(Contact).where(Contact.customer_id == kunde.id)) == 1
    # Im Adressbuch steht er einmal; im Dialog unter "Kunden" mit dem vorhandenen Eintrag
    liste = [c for c in client.get("/api/contacts").json() if c["source_id"] == kunde.id]
    assert len(liste) == 1
    gruppen = {g["key"]: g for g in _kandidaten(client, eins, "Hof")["groups"]}
    assert [h["contact_id"] for h in gruppen["customers"]["hits"]] == [eintrag["id"]]
    assert "contacts" not in gruppen or eintrag["id"] not in [h["contact_id"] for h in gruppen["contacts"]["hits"]]

    # Lieferant ebenso
    lieferant = _lieferant(db)
    a = _hinzufuegen(client, eins, supplier_id=lieferant.id).json()
    b = client.post(f"/api/projects/{zwei.id}/participants", json={"supplier_id": lieferant.id, "role": "anderes_gewerk"}).json()
    assert a["contact_id"] == b["contact_id"] and a["contact"]["source_label"] == "aus Lieferantenstamm"
    assert db.scalar(select(func.count()).select_from(Contact).where(Contact.supplier_id == lieferant.id)) == 1


def test_genau_eine_herkunft(router_test_client, threaded_db_session):
    db = threaded_db_session
    client = _client(router_test_client, db)
    projekt, kunde, lieferant = _projekt(db, "P-1"), _kunde(db), _lieferant(db)
    assert _hinzufuegen(client, projekt).status_code == 422
    assert _hinzufuegen(client, projekt, customer_id=kunde.id, supplier_id=lieferant.id).status_code == 422
    assert _hinzufuegen(client, projekt, customer_id=999_999).status_code == 404
    assert _hinzufuegen(client, projekt, supplier_id=999_999).status_code == 404


def test_geaenderte_daten_im_stammsatz_erscheinen_beim_beteiligten(router_test_client, threaded_db_session):
    db = threaded_db_session
    client = _client(router_test_client, db)
    kunde = _kunde(db, "Hof", salutation="Herr", first_name="Hans", email="alt@hof.example", phone="0241 1",
                   mobile="0170 1", street="Altweg 1", postal_code="52062", city="Aachen")
    projekt = _projekt(db, "P-1")
    beteiligt = _hinzufuegen(client, projekt, customer_id=kunde.id).json()
    assert (beteiligt["contact"]["display_name"], beteiligt["contact"]["kind"], beteiligt["contact"]["email"]) == \
        ("Herr Hans Hof", "person", "alt@hof.example")

    kunde.email, kunde.phone, kunde.street, kunde.city = "neu@hof.example", "0241 2", "Neuweg 9", "Düren"
    db.commit()
    [aktuell] = client.get(f"/api/projects/{projekt.id}/participants").json()
    assert [aktuell["contact"][k] for k in ("email", "phone", "mobile", "street", "city")] == \
        ["neu@hof.example", "0241 2", "0170 1", "Neuweg 9", "Düren"]
    assert client.get(f"/api/contacts/{aktuell['contact_id']}").json()["email"] == "neu@hof.example"
    # Keine Kopie: die eigenen Spalten des Eintrags bleiben leer
    eintrag = db.get(Contact, aktuell["contact_id"])
    db.refresh(eintrag)
    assert [getattr(eintrag, k) for k in ("company_name", "first_name", "last_name", "phone", "mobile", "email",
                                          "street", "postal_code", "city")] == [None] * 9

    # Firmenkunde: Firma; Lieferant: Firma ohne Mobil, inaktiv gekennzeichnet
    firma = _kunde(db, "Verwaltung Eck GmbH")
    lieferant = _lieferant(db, phone="0221 5", email="info@stark.example", city="Köln")
    f = _hinzufuegen(client, projekt, customer_id=firma.id).json()["contact"]
    assert (f["kind"], f["company_name"], f["display_name"]) == ("firma", "Verwaltung Eck GmbH", "Verwaltung Eck GmbH")
    l = _hinzufuegen(client, projekt, supplier_id=lieferant.id).json()["contact"]
    assert (l["kind"], l["phone"], l["source_archived"]) == ("firma", "0221 5", False)
    lieferant.active, lieferant.phone = False, "0221 6"
    db.commit()
    l = next(p["contact"] for p in client.get(f"/api/projects/{projekt.id}/participants").json()
             if p["contact"]["source"] == "supplier")
    assert (l["phone"], l["source_archived"]) == ("0221 6", True)


def test_eintrag_mit_verweis_im_adressbuch_nicht_aenderbar(router_test_client, threaded_db_session):
    db = threaded_db_session
    client = _client(router_test_client, db)
    kunde, projekt = _kunde(db, email="info@hof.example"), _projekt(db, "P-1")
    kontakt_id = _hinzufuegen(client, projekt, customer_id=kunde.id).json()["contact_id"]
    for feld, wert in (("email", "x@y.example"), ("last_name", "Anders"), ("city", "Bonn"), ("kind", "person")):
        response = client.put(f"/api/contacts/{kontakt_id}", json={feld: wert})
        assert response.status_code == 400, feld
        assert "Kundenstamm" in response.json()["detail"]
    response = client.put(f"/api/contacts/{kontakt_id}", json={"function": "Objektbetreuung"})
    assert response.status_code == 200, response.text
    assert (response.json()["function"], response.json()["email"]) == ("Objektbetreuung", "info@hof.example")
    assert db.get(Contact, kontakt_id).email is None
    # Archivieren geht wie bei jedem Eintrag; Löschen nur ohne Projekt
    assert client.post(f"/api/contacts/{kontakt_id}/archive").status_code == 200
    assert client.delete(f"/api/contacts/{kontakt_id}").status_code == 409


# ---------------------------------------------------------------------------
# 3. Auftraggeber
# ---------------------------------------------------------------------------

def test_auftraggeber_kunde_abgelehnt(router_test_client, threaded_db_session):
    db = threaded_db_session
    client = _client(router_test_client, db)
    auftraggeber = _kunde(db, "Bauherr Berg")
    eigenes, fremdes = _projekt(db, "P-1", auftraggeber), _projekt(db, "P-2")
    response = _hinzufuegen(client, eigenes, customer_id=auftraggeber.id)
    assert response.status_code == 400 and "Auftraggeber" in response.json()["detail"]
    assert db.scalar(select(func.count()).select_from(Contact)) == 0  # kein Eintrag angelegt
    # In einem fremden Projekt darf er Beteiligter sein -- sein Eintrag aber nie im eigenen
    kontakt_id = _hinzufuegen(client, fremdes, customer_id=auftraggeber.id).json()["contact_id"]
    assert _hinzufuegen(client, eigenes, contact_id=kontakt_id).status_code == 400
    with pytest.raises(ValueError, match="Auftraggeber"):
        add_participant(db, eigenes, db.get(Contact, kontakt_id), role="sonstiges")
    # Im Dialog gekennzeichnet und nicht wählbar -- im fremden Projekt wählbar
    [treffer] = {g["key"]: g for g in _kandidaten(client, eigenes, "Berg")["groups"]}["customers"]["hits"]
    assert treffer["blocked"] == "Auftraggeber dieses Projekts"
    [treffer] = {g["key"]: g for g in _kandidaten(client, fremdes, "Berg")["groups"]}["customers"]["hits"]
    assert treffer["blocked"] is None


# ---------------------------------------------------------------------------
# 1. Der Dialog
# ---------------------------------------------------------------------------

def test_dialog_gruppiert_nach_herkunft_ohne_mitarbeiter(router_test_client, threaded_db_session):
    db = threaded_db_session
    client = _client(router_test_client, db)
    projekt = _projekt(db, "P-1")
    client.post("/api/contacts", json={"kind": "firma", "company_name": "Müller Planung"})
    _kunde(db, "Müller Bau")
    _lieferant(db, "Müller Dach", active=False)
    db.add(Employee(first_name="Max", last_name="Müller")); db.commit()

    antwort = _kandidaten(client, projekt, "Müller")
    assert [s["key"] for s in antwort["sources"]] == ["contacts", "customers", "suppliers"]
    gruppen = {g["key"]: g for g in antwort["groups"]}
    assert [(k, g["label"]) for k, g in gruppen.items()] == \
        [("contacts", "Adressbuch"), ("customers", "Kunden"), ("suppliers", "Lieferanten")]
    assert [h["title"] for h in gruppen["contacts"]["hits"]] == ["Müller Planung"]
    assert [h["title"] for h in gruppen["customers"]["hits"]] == ["Müller Bau"]
    [lieferant] = gruppen["suppliers"]["hits"]
    assert (lieferant["title"], lieferant["source_archived"], lieferant["blocked"]) == ("Müller Dach", True, None)
    assert all("Max" not in h["title"] for g in antwort["groups"] for h in g["hits"])
    # Ohne bzw. mit einem Zeichen: nur das Adressbuch (wie bisher), Kunden und Lieferanten ab zwei Zeichen
    for q in ("", "M"):
        assert [g["key"] for g in _kandidaten(client, projekt, q)["groups"]] == ["contacts"], q
    # Ein im Adressbuch archivierter Eintrag eines Kunden: im Dialog nicht wählbar
    kunde = db.scalar(select(Customer).where(Customer.last_name == "Müller Bau"))
    kontakt = linked_contact(db, customer=kunde); db.commit()
    client.post(f"/api/contacts/{kontakt.id}/archive")
    [treffer] = {g["key"]: g for g in _kandidaten(client, projekt, "Müller Bau")["groups"]}["customers"]["hits"]
    assert treffer["contact_archived"] and "archiviert" in treffer["blocked"]
    assert _hinzufuegen(client, projekt, customer_id=kunde.id).status_code == 400


def _nur_admin_sieht_lieferanten(monkeypatch):
    quellen = tuple(dataclasses.replace(s, allowed_roles=frozenset({ROLE_ADMIN})) if s.key == "suppliers" else s
                    for s in search_module.OFFICE_SEARCH_SOURCES)
    monkeypatch.setattr(search_module, "OFFICE_SEARCH_SOURCES", quellen)


def test_rollenpruefung_wie_in_der_buero_suche(router_test_client, threaded_db_session, monkeypatch):
    db = threaded_db_session
    projekt, lieferant = _projekt(db, "P-1"), _lieferant(db, "Dachhandel Nord")
    buero, admin = _client(router_test_client, db), _client(router_test_client, db, ROLE_ADMIN)
    # Heute sehen alle Bürorollen Lieferanten -- Dialog und Büro-Suche gleich
    assert "suppliers" in {g["key"] for g in _kandidaten(buero, projekt, "Dachhandel")["groups"]}
    assert "suppliers" in {g["key"] for g in search_office(db, ROLE_OFFICE_AUFTRAG, "Dachhandel")}
    kontakt_id = _hinzufuegen(admin, projekt, supplier_id=lieferant.id).json()["contact_id"]

    _nur_admin_sieht_lieferanten(monkeypatch)
    assert "suppliers" not in {g["key"] for g in search_office(db, ROLE_OFFICE_AUFTRAG, "Dachhandel")}
    antwort = _kandidaten(buero, projekt, "Dachhandel")
    assert "suppliers" not in [s["key"] for s in antwort["sources"]]
    assert "suppliers" not in {g["key"] for g in antwort["groups"]}
    # Auch über die API nicht wählbar -- weder als Lieferant noch über seinen Adressbuch-Eintrag
    zweites = _projekt(db, "P-2")
    assert _hinzufuegen(buero, zweites, supplier_id=lieferant.id).status_code == 403
    assert _hinzufuegen(buero, zweites, contact_id=kontakt_id).status_code == 403
    assert "suppliers" in {g["key"] for g in _kandidaten(admin, projekt, "Dachhandel")["groups"]}
    assert _hinzufuegen(admin, zweites, supplier_id=lieferant.id).status_code == 200


def test_monteur_403(router_test_client, threaded_db_session):
    db = threaded_db_session
    projekt, kunde = _projekt(db, "P-1"), _kunde(db)
    monteur = _client(router_test_client, db, ROLE_FIELD)
    assert monteur.get(f"/api/projects/{projekt.id}/participant-candidates", params={"q": "Hof"}).status_code == 403
    assert _hinzufuegen(monteur, projekt, customer_id=kunde.id).status_code == 403
    assert db.scalar(select(func.count()).select_from(Contact)) == 0


# ---------------------------------------------------------------------------
# Suche, Historie, Verwendung
# ---------------------------------------------------------------------------

def test_suche_und_historie_mit_den_werten_des_stammsatzes(router_test_client, threaded_db_session):
    db = threaded_db_session
    client = _client(router_test_client, db)
    kunde, projekt = _kunde(db, "Zentralverwaltung Ost", email="post@zvo.example", city="Eschweiler"), _projekt(db, "P-1")
    tokens = set_audit_context()
    try:
        kontakt_id = _hinzufuegen(client, projekt, customer_id=kunde.id).json()["contact_id"]
    finally:
        reset_audit_context(tokens)
    for begriff in ("zvo.example", "Eschweiler", "Zentralverwaltung"):
        assert [c["id"] for c in client.get("/api/contacts", params={"search": begriff}).json()] == [kontakt_id], begriff
    [treffer] = {g["key"]: g for g in search_office(db, ROLE_OFFICE_AUFTRAG, "Zentralverwaltung")}["contacts"]["hits"]
    assert treffer["title"] == "Zentralverwaltung Ost" and "aus Kundenstamm" in treffer["subtitle"]
    labels = db.scalars(select(AuditLog.entity_label).where(AuditLog.entity_type == "Projektbeteiligter")).all()
    assert labels == ["Zentralverwaltung Ost · Hausverwaltung"]


def test_verweis_zaehlt_als_verwendung_des_stammsatzes(router_test_client, threaded_db_session):
    """Lieferant löschen deaktiviert ihn, solange ein Adressbuch-Eintrag auf ihn zeigt; ein Importlauf mit einem
    so verwendeten Kunden ist nicht mehr rückgängig zu machen (unter PostgreSQL hielte sonst der Fremdschlüssel)."""
    db = threaded_db_session
    client = _client(router_test_client, db)
    projekt, lieferant, frei = _projekt(db, "P-1"), _lieferant(db), _lieferant(db, "Ohne Verweis")
    _hinzufuegen(client, projekt, supplier_id=lieferant.id)
    assert client.delete(f"/api/suppliers/{lieferant.id}").json() == {"deleted": False, "deactivated": True}
    assert db.get(Supplier, lieferant.id) is not None
    assert client.delete(f"/api/suppliers/{frei.id}").json() == {"deleted": True}

    lauf = ImportRun(source_filename="adressen.csv")
    db.add(lauf); db.commit()
    kunde = _kunde(db, "Importiert", import_run_id=lauf.id)
    assert _run_is_untouched(db, lauf)
    linked_contact(db, customer=kunde); db.commit()
    assert not _run_is_untouched(db, lauf)


# ---------------------------------------------------------------------------
# Oberfläche
# ---------------------------------------------------------------------------

def test_oberflaeche_dialog_adressbuch_und_formular():
    mappe = (TEMPLATES / "project_folder.html").read_text(encoding="utf-8")
    assert "/participant-candidates" in mappe and "pm-group" in mappe
    assert "customer_id:pmChoice.customer_id" in mappe and "supplier_id:pmChoice.supplier_id" in mappe
    assert "c.source_label" in mappe and "Lieferant inaktiv" in mappe
    liste = (TEMPLATES / "master_data.html").read_text(encoding="utf-8")
    assert "x.source_label" in liste
    formular = (TEMPLATES / "master_data_form.html").read_text(encoding="utf-8")
    assert "record?.source" in formular and "readOnly=true" in formular
    assert "body={function:n(v('function'))}" in formular


# ---------------------------------------------------------------------------
# Gleichzeitig gegen PostgreSQL
# ---------------------------------------------------------------------------

PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.mark.skipif(not PG_TEST_DATABASE_URL, reason="ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
def test_postgresql_gleichzeitig_ein_eintrag_je_kunde():
    """Zwei gleichzeitige erste Wahlen desselben Kunden: beide lesen "kein Eintrag", eine legt an, die andere
    scheitert am UNIQUE-Constraint und nimmt den Eintrag der ersten."""
    schema = f"pgtest_stammdaten_{uuid.uuid4().hex[:8]}"
    admin_engine = create_engine(PG_TEST_DATABASE_URL)
    with admin_engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        setup = Session()
        kunde_id = _kunde(setup, "Parallel GmbH").id
        setup.close()

        barrier = threading.Barrier(2)
        ergebnisse = {}

        def worker(name):
            session = Session()
            original = session.scalar
            aufrufe = []

            def lesen_dann_warten(*args, **kwargs):
                result = original(*args, **kwargs)
                aufrufe.append(1)
                if len(aufrufe) == 1:
                    barrier.wait(timeout=10)  # beide haben gelesen, bevor eine anlegt
                return result

            session.scalar = lesen_dann_warten
            try:
                kontakt = linked_contact(session, customer=session.get(Customer, kunde_id))
                session.commit()
                ergebnisse[name] = kontakt.id
            finally:
                session.close()

        threads = [threading.Thread(target=worker, args=(name,)) for name in ("A", "B")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert len(ergebnisse) == 2 and ergebnisse["A"] == ergebnisse["B"], ergebnisse
        check = Session()
        assert check.scalar(select(func.count()).select_from(Contact)) == 1
        check.close()
    finally:
        engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin_engine.dispose()
