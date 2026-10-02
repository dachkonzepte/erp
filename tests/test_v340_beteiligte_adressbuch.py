"""Version 1.8.37 -- Beteiligte mit Adressbuch (Stufe 2b, Runde 2b-2, siehe
docs/archiv/vertragsgrundlage-und-vertrag.md, "Umsetzung 1.8.37").

1. Adressbuch als Stammdatenbereich (Regel 10): Kontakt als Person oder Firma, Archivieren statt Löschen,
   sobald er in einem Projekt eingetragen ist, in der Büro-Suche.
2. Beteiligte: Projekt--Kontakt--Rolle, Rollen fest im Code, eindeutig je Projekt, Kontakt und Rolle,
   "Kopie bei Anzeigen", "empfangsbevollmächtigt" mit Vollmacht als Beleg; kein Kunde als Beteiligter.
3. Reiter "Beteiligte" in der Projektmappe: erst suchen, dann neu anlegen.
4. Nur Büro, Monteur 403 (auch im Datengrenze-Durchlauf von test_v326).
5. Gegenproben: Kontakt in zwei Projekten, Archivieren statt Löschen, doppelte Zuordnung abgelehnt (auch
   gleichzeitig gegen PostgreSQL, opt-in über ERP_TEST_POSTGRES_URL), Monteur 403.
"""

import os
import re
import threading
import uuid
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from PIL import Image
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app import project_participants as participants_module
from app.contacts import ContactInUseError, create_contact, delete_contact
from app.database import Base
from app.models import AuditLog, Contact, Customer, Project, ProjectParticipant
from app.permissions import ROLE_ADMIN, ROLE_FIELD, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN
from app.project_participants import ROLES, DuplicateParticipantError, add_participant, update_participant
from app.project_pipeline_columns import default_pipeline_column_id
from app.projects import delete_project
from app.routers.contacts import router as contacts_router
from app.routers.project_participants import router as participants_router
from app.search import search_office

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def vollmacht_ordner(tmp_path, monkeypatch):
    monkeypatch.setattr(participants_module, "POWER_OF_ATTORNEY_ROOT", tmp_path / "vollmachten")
    return tmp_path / "vollmachten"


def _projekt(db, nummer: str, kunde: str = "Kunde Klar") -> Project:
    customer = Customer(name=kunde, last_name=kunde)
    db.add(customer); db.flush()
    project = Project(project_number=nummer, customer_id=customer.id, name=f"Dach {nummer}",
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(project); db.commit()
    return project


def _client(router_test_client, db, role="buero_auftrag"):
    return router_test_client(db, contacts_router, participants_router, role=role)


def _kontakt(client, **werte) -> dict:
    body = {"kind": "person", "first_name": "Anna", "last_name": "Architekt", "function": "Planerin",
            "company_name": "Büro Plan", "phone": "0241 1", "mobile": "0170 1", "email": "anna@example.org",
            "street": "Planweg 1", "postal_code": "52062", "city": "Aachen", **werte}
    response = client.post("/api/contacts", json=body)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# 1. Adressbuch
# ---------------------------------------------------------------------------

def test_kontakt_als_person_und_als_firma(router_test_client, threaded_db_session):
    client = _client(router_test_client, threaded_db_session)
    person = _kontakt(client)
    assert person["display_name"] == "Anna Architekt" and person["kind_label"] == "Person"
    assert [person[k] for k in ("function", "phone", "mobile", "email", "street", "postal_code", "city")] == \
        ["Planerin", "0241 1", "0170 1", "anna@example.org", "Planweg 1", "52062", "Aachen"]
    firma = _kontakt(client, kind="firma", company_name="Hausverwaltung Meyer GmbH", first_name=None, last_name=None)
    assert firma["display_name"] == "Hausverwaltung Meyer GmbH" and firma["kind_label"] == "Firma"
    # Pflichtfeld je Art
    assert client.post("/api/contacts", json={"kind": "person", "first_name": "Ohne"}).status_code == 400
    assert client.post("/api/contacts", json={"kind": "firma", "last_name": "Ohne Firma"}).status_code == 400
    assert client.post("/api/contacts", json={"kind": "verein", "last_name": "X"}).status_code == 422


def test_update_uebernimmt_nur_gesendete_felder(router_test_client, threaded_db_session):
    client = _client(router_test_client, threaded_db_session)
    kontakt = _kontakt(client)
    response = client.put(f"/api/contacts/{kontakt['id']}", json={"mobile": "0170 999"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["mobile"] == "0170 999" and data["email"] == "anna@example.org" and data["city"] == "Aachen"
    # Art wechseln ohne Firmenname: abgelehnt, nichts gespeichert
    assert client.put(f"/api/contacts/{kontakt['id']}", json={"kind": "firma", "company_name": None}).status_code == 400
    assert client.get(f"/api/contacts/{kontakt['id']}").json()["kind"] == "person"
    assert client.put(f"/api/contacts/{kontakt['id']}", json={"kind": None}).status_code == 422


def test_kontakt_in_zwei_projekten(router_test_client, threaded_db_session):
    db = threaded_db_session
    client = _client(router_test_client, db)
    eins, zwei = _projekt(db, "P-1"), _projekt(db, "P-2", "Kundin Zwei")
    kontakt = _kontakt(client)
    for projekt, rolle in ((eins, "architekt_planer"), (zwei, "hausverwaltung")):
        response = client.post(f"/api/projects/{projekt.id}/participants", json={"contact_id": kontakt["id"], "role": rolle})
        assert response.status_code == 200, response.text
    detail = client.get(f"/api/contacts/{kontakt['id']}").json()
    assert detail["project_count"] == 2
    assert {(p["project_number"], p["role_label"]) for p in detail["projects"]} == \
        {("P-1", "Architekt/Planer"), ("P-2", "Hausverwaltung")}
    liste = client.get("/api/contacts").json()
    assert [k["project_count"] for k in liste if k["id"] == kontakt["id"]] == [2]
    for projekt, label in ((eins, "Architekt/Planer"), (zwei, "Hausverwaltung")):
        beteiligte = client.get(f"/api/projects/{projekt.id}/participants").json()
        assert [(b["contact"]["display_name"], b["role_label"]) for b in beteiligte] == [("Anna Architekt", label)]
    # Gegenprobe: eine Änderung am Kontakt erscheint in beiden Projekten (ein Datensatz, keine Kopie)
    client.put(f"/api/contacts/{kontakt['id']}", json={"phone": "0241 777"})
    assert {client.get(f"/api/projects/{p.id}/participants").json()[0]["contact"]["phone"] for p in (eins, zwei)} == {"0241 777"}
    # Eindeutig je Projekt, nicht im ganzen Betrieb: dieselbe Rolle im zweiten Projekt ist erlaubt
    gleiche_rolle = client.post(f"/api/projects/{zwei.id}/participants", json={"contact_id": kontakt["id"], "role": "architekt_planer"})
    assert gleiche_rolle.status_code == 200, gleiche_rolle.text
    assert client.get(f"/api/contacts/{kontakt['id']}").json()["project_count"] == 2


def test_archivieren_statt_loeschen(router_test_client, threaded_db_session):
    db = threaded_db_session
    client = _client(router_test_client, db)
    projekt = _projekt(db, "P-1")
    benutzt, frei = _kontakt(client), _kontakt(client, last_name="Frei")
    beteiligt = client.post(f"/api/projects/{projekt.id}/participants",
                            json={"contact_id": benutzt["id"], "role": "sachverstaendiger"}).json()

    abgelehnt = client.delete(f"/api/contacts/{benutzt['id']}")
    assert abgelehnt.status_code == 409 and "archivieren" in abgelehnt.json()["detail"]
    assert db.get(Contact, benutzt["id"]) is not None
    # Gegenprobe: ein Kontakt ohne Projekt lässt sich löschen
    assert client.delete(f"/api/contacts/{frei['id']}").status_code == 200
    db.expire_all()
    assert db.get(Contact, frei["id"]) is None

    archiviert = client.post(f"/api/contacts/{benutzt['id']}/archive").json()
    assert archiviert["archived"] is True and archiviert["archived_at"]
    assert benutzt["id"] not in [k["id"] for k in client.get("/api/contacts").json()]
    assert benutzt["id"] in [k["id"] for k in client.get("/api/contacts?include_archived=true").json()]
    # bleibt im Projekt stehen, gekennzeichnet -- lässt sich aber nicht neu zuordnen
    [eintrag] = client.get(f"/api/projects/{projekt.id}/participants").json()
    assert eintrag["id"] == beteiligt["id"] and eintrag["contact"]["archived"] is True
    neu = client.post(f"/api/projects/{projekt.id}/participants", json={"contact_id": benutzt["id"], "role": "versicherung"})
    assert neu.status_code == 400 and "archiviert" in neu.json()["detail"]
    assert client.post(f"/api/contacts/{benutzt['id']}/unarchive").json()["archived"] is False
    # aus dem Projekt entfernt: jetzt löschbar
    assert client.delete(f"/api/project-participants/{beteiligt['id']}").status_code == 200
    assert client.delete(f"/api/contacts/{benutzt['id']}").status_code == 200


def test_loeschen_prueft_die_verwendung_auch_in_der_geschaeftslogik(db_session):
    projekt = _projekt(db_session, "P-1")
    kontakt = create_contact(db_session, {"kind": "firma", "company_name": "Versicherung AG"})
    add_participant(db_session, projekt, kontakt, role="versicherung")
    with pytest.raises(ContactInUseError):
        delete_contact(db_session, kontakt)


def test_buero_suche_findet_kontakte(router_test_client, threaded_db_session):
    from app.routers.search import router as search_router

    db = threaded_db_session
    client = _client(router_test_client, db)
    kontakt = _kontakt(client, kind="firma", company_name="Gutachterbüro Lot", first_name=None, last_name=None,
                       function="Sachverständiger Dach", city="Düren")
    for begriff in ("Gutachterbüro", "sachverständiger", "Düren"):
        gruppen = {g["key"]: g for g in search_office(db, ROLE_OFFICE_AUFTRAG, begriff)}
        assert [h["id"] for h in gruppen["contacts"]["hits"]] == [kontakt["id"]], begriff
    [treffer] = {g["key"]: g for g in search_office(db, ROLE_OFFICE_AUFTRAG, "Lot")}["contacts"]["hits"]
    assert treffer["url"] == f"/master-data/contacts/{kontakt['id']}/edit"
    assert set(treffer) == {"id", "title", "subtitle", "url"}
    buero = router_test_client(db, search_router, role="buero_auftrag").get("/api/search", params={"q": "Gutachter"})
    assert "contacts" in {g["key"] for g in buero.json()}
    assert router_test_client(db, search_router, role=ROLE_FIELD).get("/api/search", params={"q": "Gutachter"}).status_code == 403


# ---------------------------------------------------------------------------
# 2. Beteiligte
# ---------------------------------------------------------------------------

def test_rollen_fest_im_code(router_test_client, threaded_db_session):
    client = _client(router_test_client, threaded_db_session)
    assert client.get("/api/project-participant-roles").json() == [
        {"key": "architekt_planer", "label": "Architekt/Planer"},
        {"key": "bauleitung_ag", "label": "Bauleitung des Auftraggebers"},
        {"key": "hausverwaltung", "label": "Hausverwaltung"},
        {"key": "eigentuemer", "label": "Eigentümer"},
        {"key": "sachverstaendiger", "label": "Sachverständiger/Gutachter"},
        {"key": "versicherung", "label": "Versicherung"},
        {"key": "anderes_gewerk", "label": "Anderes Gewerk"},
        {"key": "sonstiges", "label": "Sonstiges"},
    ]
    assert "auftraggeber" not in " ".join(ROLES).lower()  # der Kunde ist Auftraggeber, keine Rolle


def test_doppelte_zuordnung_abgelehnt(router_test_client, threaded_db_session):
    db = threaded_db_session
    client = _client(router_test_client, db)
    projekt = _projekt(db, "P-1")
    kontakt = _kontakt(client)
    url = f"/api/projects/{projekt.id}/participants"
    erst = client.post(url, json={"contact_id": kontakt["id"], "role": "eigentuemer", "copy_on_notices": True})
    assert erst.status_code == 200
    doppelt = client.post(url, json={"contact_id": kontakt["id"], "role": "eigentuemer"})
    assert doppelt.status_code == 409 and "bereits als Eigentümer" in doppelt.json()["detail"]
    # Gegenprobe: andere Rolle desselben Kontakts ist erlaubt
    zweite = client.post(url, json={"contact_id": kontakt["id"], "role": "hausverwaltung"})
    assert zweite.status_code == 200
    # Rolle ändern auf eine schon vorhandene: abgelehnt, nichts geändert
    umbenannt = client.put(f"/api/project-participants/{zweite.json()['id']}", json={"role": "eigentuemer"})
    assert umbenannt.status_code == 409
    assert sorted(b["role"] for b in client.get(url).json()) == ["eigentuemer", "hausverwaltung"]
    assert client.post(url, json={"contact_id": kontakt["id"], "role": "bauherr"}).status_code == 400
    assert client.post(url, json={"contact_id": 999, "role": "sonstiges"}).status_code == 404


def test_doppelte_zuordnung_scheitert_auch_ohne_vorpruefung_am_constraint(db_session, monkeypatch):
    """Zwei gleichzeitige Anfragen kommen beide an der Vorprüfung vorbei -- dann hält der UNIQUE-
    Constraint, und der zweite Versuch rollt nur seinen SAVEPOINT zurück (Gegenprobe zur Vorprüfung)."""
    projekt = _projekt(db_session, "P-1")
    kontakt = create_contact(db_session, {"kind": "person", "last_name": "Doppel"})
    add_participant(db_session, projekt, kontakt, role="sonstiges")
    monkeypatch.setattr(participants_module, "_duplicate_exists", lambda *a, **k: False)
    with pytest.raises(DuplicateParticipantError):
        add_participant(db_session, projekt, kontakt, role="sonstiges")
    assert len(db_session.scalars(select(ProjectParticipant)).all()) == 1
    db_session.add(ProjectParticipant(project_id=projekt.id, contact_id=kontakt.id, role="sonstiges"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_haekchen_einzeln_aendern(router_test_client, threaded_db_session):
    db = threaded_db_session
    client = _client(router_test_client, db)
    projekt = _projekt(db, "P-1")
    kontakt = _kontakt(client)
    b = client.post(f"/api/projects/{projekt.id}/participants",
                    json={"contact_id": kontakt["id"], "role": "bauleitung_ag", "copy_on_notices": True}).json()
    assert (b["copy_on_notices"], b["authorized_recipient"]) == (True, False)
    b = client.put(f"/api/project-participants/{b['id']}", json={"authorized_recipient": True}).json()
    assert (b["copy_on_notices"], b["authorized_recipient"], b["role"]) == (True, True, "bauleitung_ag")
    assert client.put(f"/api/project-participants/{b['id']}", json={"copy_on_notices": None}).status_code == 422


def test_vollmacht_als_beleg(router_test_client, threaded_db_session, vollmacht_ordner):
    db = threaded_db_session
    client = _client(router_test_client, db)
    projekt = _projekt(db, "P-1")
    kontakt = _kontakt(client)
    b = client.post(f"/api/projects/{projekt.id}/participants", json={"contact_id": kontakt["id"], "role": "hausverwaltung"}).json()
    url = f"/api/project-participants/{b['id']}/power-of-attorney"
    # ohne Empfangsvollmacht kein Beleg
    ohne = client.post(url, files={"file": ("vollmacht.pdf", PDF, "application/pdf")})
    assert ohne.status_code == 400 and "empfangsbevollmächtigt" in ohne.json()["detail"]
    client.put(f"/api/project-participants/{b['id']}", json={"authorized_recipient": True})
    # am Inhalt erkannt, nicht an Name oder Angabe des Browsers
    assert client.post(url, files={"file": ("vollmacht.pdf", b"<html>kein pdf</html>", "application/pdf")}).status_code == 400
    pdf = client.post(url, files={"file": ("Vollmacht Meyer.pdf", PDF, "image/png")})
    assert pdf.status_code == 200, pdf.text
    vm = pdf.json()["power_of_attorney"]
    assert vm["filename"] == "Vollmacht Meyer.pdf" and vm["content_type"] == "application/pdf" and vm["size_bytes"] == len(PDF)
    assert len(vm["sha256"]) == 64 and vm["uploaded_by_name"]
    abruf = client.get(url)
    assert abruf.status_code == 200 and abruf.content == PDF and abruf.headers["content-type"] == "application/pdf"
    assert len(list(vollmacht_ordner.iterdir())) == 1
    # ersetzen: neue Datei, alte weg
    foto = client.post(url, files={"file": ("foto.png", _png(), "image/png")}).json()["power_of_attorney"]
    assert foto["content_type"] == "image/png" and len(list(vollmacht_ordner.iterdir())) == 1
    # Häkchen entfernen lässt den Beleg stehen
    b = client.put(f"/api/project-participants/{b['id']}", json={"authorized_recipient": False}).json()
    assert b["power_of_attorney"]["sha256"] == foto["sha256"]
    # zu groß
    client.put(f"/api/project-participants/{b['id']}", json={"authorized_recipient": True})
    zu_gross = client.post(url, files={"file": ("gross.pdf", PDF + b"0" * participants_module.MAX_POWER_OF_ATTORNEY_BYTES, "application/pdf")})
    assert zu_gross.status_code == 400
    # entfernen
    assert client.delete(url).json()["power_of_attorney"] is None
    assert list(vollmacht_ordner.iterdir()) == []
    assert client.get(url).status_code == 404


def test_beteiligten_entfernen_und_projekt_loeschen_raeumen_auf(router_test_client, threaded_db_session, vollmacht_ordner):
    db = threaded_db_session
    client = _client(router_test_client, db)
    projekt = _projekt(db, "P-1")
    kontakt = _kontakt(client)
    b = client.post(f"/api/projects/{projekt.id}/participants",
                    json={"contact_id": kontakt["id"], "role": "eigentuemer", "authorized_recipient": True}).json()
    client.post(f"/api/project-participants/{b['id']}/power-of-attorney", files={"file": ("v.pdf", PDF, "application/pdf")})
    assert client.delete(f"/api/project-participants/{b['id']}").status_code == 200
    assert list(vollmacht_ordner.iterdir()) == [] and db.get(Contact, kontakt["id"]) is not None

    b = client.post(f"/api/projects/{projekt.id}/participants",
                    json={"contact_id": kontakt["id"], "role": "eigentuemer", "authorized_recipient": True}).json()
    client.post(f"/api/project-participants/{b['id']}/power-of-attorney", files={"file": ("v.pdf", PDF, "application/pdf")})
    delete_project(db, db.get(Project, projekt.id))
    db.expire_all()
    assert db.scalars(select(ProjectParticipant)).all() == []
    assert list(vollmacht_ordner.iterdir()) == []
    assert db.get(Contact, kontakt["id"]) is not None  # der Kontakt bleibt im Adressbuch


def test_historie_der_projektmappe(router_test_client, threaded_db_session):
    """Beteiligte erscheinen in der Änderungshistorie des Projekts, Kontakte in der allgemeinen."""
    from app.audit import set_audit_context, reset_audit_context

    db = threaded_db_session
    projekt = _projekt(db, "P-1")
    tokens = set_audit_context()
    try:
        kontakt = create_contact(db, {"kind": "firma", "company_name": "Meyer Verwaltung"})
        beteiligt = add_participant(db, projekt, kontakt, role="hausverwaltung", copy_on_notices=True)
        update_participant(db, beteiligt, {"role": "eigentuemer"})
    finally:
        reset_audit_context(tokens)
    zeilen = db.scalars(select(AuditLog).where(AuditLog.project_id == projekt.id,
                                               AuditLog.entity_type == "Projektbeteiligter").order_by(AuditLog.id)).all()
    assert [(z.entity_label, z.action, z.field_label, z.old_value, z.new_value) for z in zeilen] == [
        ("Meyer Verwaltung · Hausverwaltung", "angelegt", None, None, None),
        ("Meyer Verwaltung · Eigentümer", "geändert", "Rolle", "Hausverwaltung", "Eigentümer"),
    ]
    assert db.scalars(select(AuditLog).where(AuditLog.entity_type == "Kontakt (Adressbuch)")).all()


# ---------------------------------------------------------------------------
# 4. Nur Büro
# ---------------------------------------------------------------------------

def _neue_routen():
    for router in (contacts_router, participants_router):
        for route in router.routes:
            if isinstance(route, APIRoute):
                for method in route.methods:
                    yield method, route.path


def test_monteur_bekommt_ueberall_403_buero_darf(router_test_client, threaded_db_session):
    db = threaded_db_session
    projekt = _projekt(db, "P-1")
    kontakt = create_contact(db, {"kind": "person", "last_name": "Geheim", "phone": "0000"})
    beteiligt = add_participant(db, projekt, kontakt, role="sonstiges")
    werte = {"project_id": projekt.id, "contact_id": kontakt.id, "participant_id": beteiligt.id}
    monteur = router_test_client(db, contacts_router, participants_router, role=ROLE_FIELD, employee_id=None)
    gesehen = []
    for method, path in _neue_routen():
        response = monteur.request(method, path.format(**werte), json={})
        gesehen.append(path)
        assert response.status_code == 403, (method, path, response.status_code)
    assert len(gesehen) == 16  # seit 1.8.39 mit der Suche des Dialogs (participant-candidates)
    for rolle in (ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, ROLE_ADMIN):
        buero = router_test_client(db, contacts_router, participants_router, role=rolle)
        assert buero.get(f"/api/projects/{projekt.id}/participants").status_code == 200, rolle
        assert buero.get(f"/api/contacts/{kontakt.id}").status_code == 200, rolle


def test_seiten_nur_fuer_buero(router_test_client, threaded_db_session):
    from app.routers.pages import router as pages_router

    db = threaded_db_session
    for pfad in ("/master-data/contacts/new", "/master-data/contacts/1/edit"):
        assert router_test_client(db, pages_router, role="buero_auftrag").get(pfad).status_code == 200, pfad
        assert router_test_client(db, pages_router, role=ROLE_FIELD).get(pfad).status_code == 403, pfad


# ---------------------------------------------------------------------------
# 1./3. Oberfläche
# ---------------------------------------------------------------------------

def test_adressbuch_folgt_dem_stammdatenmuster():
    """Regel 10: Liste zuerst, Stammdaten-Navigation, Anlegen und Bearbeiten auf eigener Formularseite."""
    liste = (TEMPLATES / "master_data.html").read_text(encoding="utf-8")
    assert "data-view=\"contacts\" onclick=\"showView('contacts')\">Adressbuch</button>" in liste
    assert "'contacts'" in re.search(r"function viewFromHash\(\)\{.*?\}", liste).group(0)
    assert "add.href='/master-data/contacts/new'" in liste
    assert "/master-data/contacts/${x.id}/edit" in liste
    assert "api('/api/contacts?include_archived=true')" in liste
    formular = (TEMPLATES / "master_data_form.html").read_text(encoding="utf-8")
    assert "function contactForm()" in formular and "type==='contacts'" in formular
    for feld in ("kindPerson", "kindFirma", "firstName", "lastName", "companyName", "function", "phone", "mobile",
                 "email", "street", "zip", "city"):
        assert f'id="{feld}"' in formular, feld


def test_reiter_beteiligte_erst_suchen_dann_neu_anlegen():
    mappe = (TEMPLATES / "project_folder.html").read_text(encoding="utf-8")
    assert "data-tab=\"sec-participants\"" in mappe and "'sec-participants'" in mappe
    modal = mappe[mappe.index('id="participantModal"'):]
    assert modal.index('id="pmSearch"') < modal.index('id="pmNewContact"')
    assert "/master-data/contacts/new?projekt=" in mappe
    assert "Auftraggeber" in mappe
    assert '{% include "_fehlertext.html" %}' in mappe
    formular = (TEMPLATES / "master_data_form.html").read_text(encoding="utf-8")
    assert "?kontakt=${saved.id}#sec-participants" in formular


# ---------------------------------------------------------------------------
# 5. Gleichzeitig gegen PostgreSQL
# ---------------------------------------------------------------------------

PG_TEST_DATABASE_URL = os.getenv("ERP_TEST_POSTGRES_URL")


@pytest.mark.skipif(not PG_TEST_DATABASE_URL, reason="ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
def test_postgresql_gleichzeitig_doppelt_und_fremdschluessel():
    schema = f"pgtest_beteiligte_{uuid.uuid4().hex[:8]}"
    admin_engine = create_engine(PG_TEST_DATABASE_URL)
    with admin_engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_TEST_DATABASE_URL, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        setup = Session()
        projekt = _projekt(setup, "P-PG")
        kontakt = create_contact(setup, {"kind": "person", "last_name": "Parallel"})
        projekt_id, kontakt_id = projekt.id, kontakt.id
        setup.close()

        barrier = threading.Barrier(2)
        ergebnisse = {}

        def worker(name):
            session = Session()
            try:
                barrier.wait()
                add_participant(session, session.get(Project, projekt_id), session.get(Contact, kontakt_id), role="sonstiges")
                ergebnisse[name] = "angelegt"
            except DuplicateParticipantError:
                ergebnisse[name] = "abgelehnt"
            finally:
                session.close()

        threads = [threading.Thread(target=worker, args=(name,)) for name in ("A", "B")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert sorted(ergebnisse.values()) == ["abgelehnt", "angelegt"], ergebnisse

        check = Session()
        assert len(check.scalars(select(ProjectParticipant)).all()) == 1
        with pytest.raises(ContactInUseError):
            delete_contact(check, check.get(Contact, kontakt_id))
        # Der Fremdschlüssel hält auch ohne die Prüfung der Geschäftslogik
        with pytest.raises(IntegrityError):
            check.execute(text("DELETE FROM contacts WHERE id = :id"), {"id": kontakt_id})
        check.rollback()
        # Projekt mit Beteiligtem löschen: keine Verletzung des Fremdschlüssels
        delete_project(check, check.get(Project, projekt_id))
        assert check.scalars(select(ProjectParticipant)).all() == []
        check.close()
    finally:
        engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin_engine.dispose()
