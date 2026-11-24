"""Version 1.10.23 (Antwort F10 vom 23.11.2026): ein Vorgang im Archiv ist nur lesbar -- der Server lehnt jede Änderung mit 409 ab, einzig „Zurückholen“
bleibt (app/archivschutz.py).

    Teile        jede Tabelle mit einem Fremdschlüssel NOT NULL auf einen Teil ist selbst ein Teil (TEILE) oder steht hier in KEIN_TEIL mit Grund
    vorab        jede schreibende Route, deren Pfad einen Kunden, ein Objekt, eine Dachfläche, ein Projekt, ein Angebot, eine Anfrage oder einen Beteiligten
                 nennt, prüft vor dem Endpunkt (archiv_vorab() am Router) -- oder steht in OHNE_VORAB mit Grund; 409 vor jeder Datei und Mail
    Sitzung      jede neue, geänderte oder gelöschte Zeile eines Teils und jeder neu gesetzte Verweis auf einen Vorgang im Archiv: 409 beim Flush;
                 ein schon gesetzter Verweis bleibt änderbar (Aufgabe, Termin)
    erlaubt      an der Wurzel nur die Spalten des Archivs (Zurückholen, Archivieren und Entarchivieren von Hand)
"""

import io
from datetime import date, datetime

import pytest
from sqlalchemy import func, select

from app.archivschutz import MELDUNGEN, TEILE, ZURUECKHOLEN, ImArchiv, verweise
from app.customer_documents import customer_directory
from app.database import Base
from app.models import (
    CalendarEvent, Contact, Customer, CustomerDocument, CustomerExtraInfo, DocumentCategory, EmailDispatch, Inquiry, Kontaktvermerk, Order, Project,
    ProjectDocument, ProjectParticipant, Property, PropertyDocument, Quote, QuoteItem, QuoteSection, RoofArea, RoofComponent, SentDocument, Task,
)
from app.project_documents import project_directory
from app.routers import aufbewahrung as aufbewahrung_router
from app.routers import customer_documents as kundendokumente_router
from app.routers import customers as kunden_router
from app.routers import email_dispatches as versand_router
from app.routers import inquiries as anfragen_router
from app.routers import project_documents as projektdokumente_router
from app.routers import project_participants as beteiligte_router
from app.routers import projects as projekte_router
from app.routers import properties as objekte_router
from app.routers import property_documents as objektdokumente_router
from app.routers import quotes as angebote_router
from app.routers import roof_areas as flaechen_router
from app.routers import tasks as aufgaben_router
from tests.test_v782_archiv import Welt

IM_ARCHIV = datetime(2026, 11, 20, 23, 30)
KUNDE, PROJEKT, ANFRAGE = MELDUNGEN["kunde"], MELDUNGEN["projekt"], MELDUNGEN["anfrage"]

# Tabellen mit einem Fremdschlüssel NOT NULL auf einen Teil, die selbst kein Teil sind -- je mit Grund. Ein neuer Verweis auf einen Vorgang im Archiv
# lehnt die Sitzung trotzdem ab (Verweis); Teil heißt: auch jede Änderung an einer schon vorhandenen Zeile.
KEIN_TEIL = {
    ("maintenance_contracts", "customer_id"): "Bindung: ein Kunde mit Wartungsvertrag geht nie ins Archiv",
    ("maintenance_contract_items", "roof_area_id"): "Bindung: Wartungsvertrag (siehe oben)",
    ("orders", "customer_id"): "ein Projekt mit Auftrag ist nicht im Archiv, ein Kunde mit Auftrag nie",
    ("orders", "project_id"): "ein Projekt mit Auftrag ist nicht im Archiv",
    ("orders", "source_quote_id"): "ein Projekt mit Auftrag ist nicht im Archiv",
    ("order_customer_changes", "new_customer_id"): "Kundenwechsel am Auftrag (siehe Auftrag)",
    ("order_customer_changes", "old_customer_id"): "Kundenwechsel am Auftrag (siehe Auftrag)",
    ("order_acceptance_roof_areas", "roof_area_id"): "Abnahme hängt am Auftrag",
    ("service_report_roof_areas", "roof_area_id"): "Einsatzbericht hängt am Auftrag",
    ("payments", "customer_id"): "Bindung: ein Kunde mit Zahlung geht nie ins Archiv",
    ("time_entries", "project_id"): "Zeitbuchung hängt am Auftrag",
    ("time_entry_groups", "project_id"): "Zeitbuchung hängt am Auftrag",
    ("work_preparation_delivery_notes", "project_document_id"): "Arbeitsvorbereitung hängt am Auftrag",
    ("portal_zugaenge", "customer_id"): "Zugang zum Kundenportal (seit 1.11.0): Sperren muss auch im Archiv gehen; im Archiv wirkt kein Zugang -- die "
                                        "Funktionen der Datenbank prüfen das Archiv des Kunden selbst; ein neuer Zugang ist ein neuer Verweis (abgelehnt)",
}

# Schreibende Routen, deren Pfad einen Teil nennt, ohne archiv_vorab() -- je mit Grund
OHNE_VORAB = {
    "/api/customers/{customer_id}/kontakte": "eigene Prüfung mit eigener Meldung (app/kontaktvermerke.py, seit 1.10.10), schreibt keine Datei",
    "/api/projects/{project_id}/kontakte": "eigene Prüfung mit eigener Meldung (app/kontaktvermerke.py), schreibt keine Datei",
    "/api/inquiries/{inquiry_id}/kontakte": "eigene Prüfung mit eigener Meldung (app/kontaktvermerke.py), schreibt keine Datei",
    "/api/customers/{customer_id}/refunds": "Erstattung eines Guthabens -- ein Kunde mit Zahlung geht nie ins Archiv; die Sitzung lehnt die Zahlung ab",
    "/api/maintenance-contracts/from-project/{project_id}": "liest das Projekt und legt einen neuen Mustervorgang an; den Vertrag eines Kunden im Archiv lehnt "
                                                           "die Sitzung ab",
    "/api/customers/{customer_id}/portal/sperren": "seit 1.11.13: Sperren des Kundenportals nimmt nur Zugang weg und geht auch im Archiv (Festlegung 1.11.0; "
                                                   "der Zugang ist kein Teil, KEIN_TEIL); schreibt keine Datei und keine Mail",
}
# Pfadparameter, die einen Teil nennen (in jedem Router dieselbe Bedeutung)
NAMEN = {"customer_id", "property_id", "roof_area_id", "project_id", "quote_id", "inquiry_id", "participant_id"}


def _vorab(route):
    for d in route.dependant.dependencies:
        if getattr(d.call, "__name__", "") == "_archiv_vorab":
            return d.call
    return None


# --- Struktur ---------------------------------------------------------------------------------------------------------------------------------------

def test_jede_tabelle_am_vorgang_ist_eingeordnet():
    tabellen = Base.metadata.tables
    assert TEILE <= set(tabellen)
    offen = []
    for name, t in tabellen.items():
        if name in TEILE:
            continue
        for fk in t.foreign_keys:
            if fk.column.table.name in TEILE and not fk.parent.nullable and (name, fk.parent.name) not in KEIN_TEIL:
                offen.append(f"{name}.{fk.parent.name} -> {fk.column.table.name}")
    assert not offen, "Teil (TEILE in app/archivschutz.py) oder KEIN_TEIL mit Grund: " + ", ".join(offen)
    for (name, spalte), grund in KEIN_TEIL.items():
        assert grund and spalte in tabellen[name].c and name not in TEILE
    # jeder Verweis auf einen Teil -- auch die erlaubten -- steht in verweise(): die Sitzung prüft ihn beim Setzen
    assert verweise()["tasks"] == (("project_id", "projects"),)
    assert ("project_id", "projects") in verweise()["calendar_events"]


def test_jede_schreibende_route_mit_vorgang_im_pfad_prueft_vorab():
    from tests.test_v326_monteur_datengrenze import _routers_in_betriebsreihenfolge
    from fastapi.routing import APIRoute
    offen, gesehen, router_mit_vorab = [], set(), {}
    for router in _routers_in_betriebsreihenfolge():
        for route in router.routes:
            if not isinstance(route, APIRoute) or not route.methods & {"POST", "PUT", "PATCH", "DELETE"}:
                continue
            vorab = _vorab(route)
            if vorab is not None:
                router_mit_vorab.setdefault(id(router), (router, vorab))
            namen = {p.name for p in route.dependant.path_params} & NAMEN
            if not namen:
                continue
            gesehen.add(route.path)
            if route.path in OHNE_VORAB:
                assert vorab is None, f"{route.path} steht in OHNE_VORAB, prüft aber vorab"
                continue
            if vorab is None or not namen <= set(vorab.zuordnung):
                offen.append(f"{sorted(route.methods)} {route.path}: {sorted(namen - set(vorab.zuordnung if vorab else {}))}")
    assert not offen, "archiv_vorab() am Router oder OHNE_VORAB mit Grund: " + "; ".join(offen)
    assert set(OHNE_VORAB) <= gesehen, set(OHNE_VORAB) - gesehen
    # keine Zuordnung, die im Router nicht vorkommt; nur die Monteursansicht prüft auch die Monteurin
    for router, vorab in router_mit_vorab.values():
        pfade = {p.name for r in router.routes if isinstance(r, APIRoute) for p in r.dependant.path_params}
        assert set(vorab.zuordnung) <= pfade, set(vorab.zuordnung) - pfade
        assert vorab.monteurin == any(r.path.startswith("/api/field-view/") for r in router.routes if isinstance(r, APIRoute))
    assert ZURUECKHOLEN == {"/api/projects/{project_id}/unarchive"}


def test_im_archiv_ist_409_mit_meldung():
    for art, text in MELDUNGEN.items():
        e = ImArchiv(art)
        assert (e.status_code, e.detail) == (409, text)
        assert text.endswith("ist im Archiv – nur zum Ansehen. Zum Ändern erst zurückholen.")


# --- Abläufe ------------------------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def welt(threaded_db_session):
    """Ein Kunde mit Objekt, Dachfläche, Bauteil, Kundenwissen, Dokumenten, Anfrage und Projekt samt Angebot, Position, Titel, Beteiligtem und Aufgabe --
    alles angelegt, dann ins Archiv (an einem Vorgang im Archiv entsteht nichts mehr). Dazu ein aktiver Kunde mit Projekt."""
    w = Welt(threaded_db_session)
    db = w.db
    w.k = w.kunde(name="Zacharias Archiv")
    w.objekt = db.query(Property).filter(Property.customer_id == w.k.id).one()
    w.flaeche = RoofArea(property_id=w.objekt.id, name="Nordseite")
    db.add(w.flaeche)
    db.flush()
    w.bauteil = RoofComponent(roof_area_id=w.flaeche.id, name="Gully")
    w.info = CustomerExtraInfo(customer_id=w.k.id, info_type="hinweis", value="Hund im Hof")
    w.anf = w.anfrage(w.k)
    w.pj = w.projekt(w.k)
    w.angebot = Quote(project_id=w.pj.id, quote_number="A-0001", title="Dach", status="entwurf")
    db.add_all([w.bauteil, w.info, w.angebot])
    db.flush()
    w.position = QuoteItem(quote_id=w.angebot.id, position_number="1", short_text="Rinne", unit="m")
    w.titel = QuoteSection(quote_id=w.angebot.id, title="Dach")
    w.aufgabe = Task(title="Rückruf", project_id=w.pj.id)
    kategorie = db.scalar(select(DocumentCategory.id).order_by(DocumentCategory.id))
    w.kundendokument = CustomerDocument(customer_id=w.k.id, category_id=kategorie, original_filename="plan.pdf", stored_filename="k-plan.pdf")
    w.projektdokument = ProjectDocument(project_id=w.pj.id, category_id=kategorie, original_filename="plan.pdf", stored_filename="p-plan.pdf")
    w.objektdokument = PropertyDocument(property_id=w.objekt.id, category_id=kategorie, original_filename="plan.pdf", stored_filename="o-plan.pdf")
    w.kontakt = Contact(kind="firma", company_name="Planbüro Muster")
    db.add(w.kontakt)
    db.flush()
    w.beteiligter = ProjectParticipant(project_id=w.pj.id, contact_id=w.kontakt.id, role="architekt_planer")
    w.aktiv = w.kunde(name="Zora Aktiv")
    w.projekt_aktiv = w.projekt(w.aktiv)
    db.add_all([w.position, w.titel, w.aufgabe, w.kundendokument, w.projektdokument, w.objektdokument, w.beteiligter])
    db.flush()
    w.k.archiviert_am = w.anf.archiviert_am = IM_ARCHIV
    w.pj.archived, w.pj.archiviert_am = True, IM_ARCHIV
    db.commit()
    return w


ALLE = (kunden_router, kundendokumente_router, objekte_router, objektdokumente_router, flaechen_router, projekte_router, projektdokumente_router,
        beteiligte_router,
        angebote_router, anfragen_router, aufgaben_router, aufbewahrung_router, versand_router)


def _c(welt, router_test_client, **kw):
    return router_test_client(welt.db, *[m.router for m in ALLE], **kw)


def _stand(db) -> dict:
    """Alle Zeilen aller Teile, dazu die Zahl der Aufgaben, Termine, Aufträge, Versandeinträge und abgelegten Dokumente."""
    db.rollback()  # nach einer Ablehnung im Flush stehen die neuen Objekte noch in der (geteilten) Testsitzung
    db.expire_all()
    stand = {t: sorted((tuple(z) for z in db.execute(select(Base.metadata.tables[t])).all()), key=repr) for t in sorted(TEILE)}
    for modell in (Task, CalendarEvent, Order, EmailDispatch, SentDocument):
        stand[modell.__tablename__] = db.scalar(select(func.count()).select_from(modell))
    return stand


VORAB = [  # (Methode, Pfad, erwartete Meldung) -- der Körper zählt nicht: die Prüfung läuft vor dem Endpunkt
    ("PUT", "/api/customers/{k}", KUNDE),
    ("POST", "/api/customers/{k}/extra-infos", KUNDE),
    ("PUT", "/api/customers/{k}/extra-infos/{info}", KUNDE),
    ("DELETE", "/api/customers/{k}/extra-infos/{info}", KUNDE),
    ("PUT", "/api/properties/{objekt}", KUNDE),
    ("PUT", "/api/roof-areas/{flaeche}", KUNDE),
    ("DELETE", "/api/roof-areas/{flaeche}", KUNDE),
    ("POST", "/api/roof-areas/{flaeche}/archive", KUNDE),
    ("PUT", "/api/roof-components/{bauteil}", KUNDE),
    ("DELETE", "/api/roof-components/{bauteil}", KUNDE),
    ("POST", "/api/properties/{objekt}/roof-areas/bulk", KUNDE),
    ("PUT", "/api/projects/{projekt}", PROJEKT),
    ("DELETE", "/api/projects/{projekt}", PROJEKT),
    ("POST", "/api/projects/{projekt}/duplicate", PROJEKT),
    ("POST", "/api/projects/{projekt}/quotes", PROJEKT),
    ("POST", "/api/projects/{projekt}/archive", PROJEKT),
    ("PUT", "/api/projects/{projekt}/pipeline-column", PROJEKT),
    ("POST", "/api/projects/{projekt}/participants", PROJEKT),
    ("PUT", "/api/quotes/{angebot}", PROJEKT),
    ("PUT", "/api/quotes/{angebot}/items/{position}", PROJEKT),
    ("DELETE", "/api/quotes/{angebot}/items/{position}", PROJEKT),
    ("POST", "/api/quotes/{angebot}/items", PROJEKT),
    ("POST", "/api/quotes/{angebot}/sections", PROJEKT),
    ("DELETE", "/api/quotes/{angebot}/sections/{titel}", PROJEKT),
    ("POST", "/api/quotes/{angebot}/convert-to-order", PROJEKT),
    ("POST", "/api/quotes/{angebot}/send-email", PROJEKT),
    ("PUT", "/api/inquiries/{anfrage}", ANFRAGE),
    ("POST", "/api/inquiries/{anfrage}/convert", ANFRAGE),
    ("PUT", "/api/customer-documents/{kdok}", KUNDE),
    ("DELETE", "/api/customer-documents/{kdok}", KUNDE),
    ("PUT", "/api/project-documents/{pdok}", PROJEKT),
    ("DELETE", "/api/project-documents/{pdok}", PROJEKT),
    ("DELETE", "/api/property-documents/{odok}", KUNDE),
    ("PUT", "/api/project-participants/{beteiligter}", PROJEKT),
    ("DELETE", "/api/project-participants/{beteiligter}", PROJEKT),
]


def _pfad(welt, pfad: str) -> str:
    return pfad.format(k=welt.k.id, info=welt.info.id, objekt=welt.objekt.id, flaeche=welt.flaeche.id, bauteil=welt.bauteil.id, projekt=welt.pj.id,
                       angebot=welt.angebot.id, position=welt.position.id, titel=welt.titel.id, anfrage=welt.anf.id, kdok=welt.kundendokument.id,
                       pdok=welt.projektdokument.id, odok=welt.objektdokument.id, beteiligter=welt.beteiligter.id)


@pytest.mark.parametrize("methode,pfad,meldung", VORAB, ids=[f"{m} {p}" for m, p, _ in VORAB])
def test_vorab_409_und_nichts_geaendert(welt, router_test_client, methode, pfad, meldung):
    c = _c(welt, router_test_client)
    vorher = _stand(welt.db)
    antwort = c.request(methode, _pfad(welt, pfad), json={} if methode != "DELETE" else None)
    assert (antwort.status_code, antwort.json()["detail"]) == (409, meldung)
    assert _stand(welt.db) == vorher


PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f"
       b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


def _dateien(ordner) -> set:
    return {p.name for p in ordner.rglob("*") if p.is_file()} if ordner.exists() else set()


def test_hochladen_409_ohne_datei(welt, router_test_client):
    """Die Router legen eine Datei vor dem Speichern ab -- die Prüfung vorab verhindert, dass sie verwaist liegen bleibt."""
    from app.paths import data_dir
    c = _c(welt, router_test_client)
    vorher = (_dateien(customer_directory(welt.k.id)), _dateien(project_directory(welt.pj.id)), _dateien(data_dir()))
    stand = _stand(welt.db)
    datei = {"file": ("plan.png", io.BytesIO(PNG), "image/png")}
    for pfad, form, meldung in ((f"/api/customers/{welt.k.id}/documents", {"category": "Sonstiges"}, KUNDE),
                                (f"/api/projects/{welt.pj.id}/documents", {"category": "Sonstiges"}, PROJEKT),
                                (f"/api/properties/{welt.objekt.id}/documents", {"category_id": "1"}, KUNDE),
                                (f"/api/roof-areas/{welt.flaeche.id}/sketch", {}, KUNDE)):
        datei["file"][1].seek(0)
        antwort = c.post(pfad, data=form, files=datei)
        assert (antwort.status_code, antwort.json()["detail"]) == (409, meldung), pfad
    assert (_dateien(customer_directory(welt.k.id)), _dateien(project_directory(welt.pj.id)), _dateien(data_dir())) == vorher
    assert _stand(welt.db) == stand


def test_angebot_versenden_ohne_mail(welt, router_test_client, monkeypatch):
    gesendet = []
    monkeypatch.setattr("app.email_sending.send_message", lambda *a, **k: gesendet.append(a))
    c = _c(welt, router_test_client)
    antwort = c.post(f"/api/quotes/{welt.angebot.id}/send-email", json={"recipient": "kunde@example.invalid", "subject": "Angebot", "body": "Text",
                                                                         "dispatch_key": "k1"})
    assert antwort.status_code == 409 and gesendet == []
    assert welt.db.scalar(select(func.count()).select_from(EmailDispatch)) == 0


def test_zustellung_nachtragen_am_angebot_409(welt, router_test_client):
    c = _c(welt, router_test_client)
    stand = _stand(welt.db)
    antwort = c.post("/api/email-dispatches/manual", data={"document_type": "angebot", "document_id": str(welt.angebot.id), "channel": "brief",
                                                           "delivered_on": "2026-11-02", "dispatch_key": "z1"},
                     files={"receipt": ("beleg.png", io.BytesIO(PNG), "image/png")})
    assert (antwort.status_code, antwort.json()["detail"]) == (409, PROJEKT)
    assert _stand(welt.db) == stand


@pytest.mark.parametrize("pfad,koerper,meldung", [
    ("/api/properties", lambda w: {"customer_id": w.k.id, "name": "Neues Objekt"}, KUNDE),
    ("/api/roof-areas", lambda w: {"property_id": w.objekt.id, "name": "Südseite"}, KUNDE),
    ("/api/tasks", lambda w: {"title": "Neue Aufgabe", "project_id": w.pj.id}, PROJEKT),
], ids=["Objekt", "Dachfläche", "Aufgabe"])
def test_anlegen_am_vorgang_im_archiv_409_aus_der_sitzung(welt, router_test_client, pfad, koerper, meldung):
    """Ohne Kennung im Pfad greift die Sitzung: ein neuer Teil bzw. ein neuer Verweis auf einen Vorgang im Archiv -- 409, nichts gespeichert."""
    c = _c(welt, router_test_client)
    stand = _stand(welt.db)
    antwort = c.post(pfad, json=koerper(welt))
    assert (antwort.status_code, antwort.json()["detail"]) == (409, meldung)
    assert _stand(welt.db) == stand


def test_vorhandener_verweis_bleibt_aenderbar(welt, router_test_client):
    """Eine Aufgabe am Projekt im Archiv gehört zum Aufgabenmodul: sie bleibt änderbar; nur ein neuer Verweis auf den Vorgang im Archiv nicht."""
    c = _c(welt, router_test_client)
    assert c.put(f"/api/tasks/{welt.aufgabe.id}", json={"title": "Rückruf erledigen"}).status_code == 200
    assert c.put(f"/api/tasks/{welt.aufgabe.id}", json={"project_id": welt.projekt_aktiv.id}).status_code == 200
    antwort = c.put(f"/api/tasks/{welt.aufgabe.id}", json={"project_id": welt.pj.id})
    assert (antwort.status_code, antwort.json()["detail"]) == (409, PROJEKT)


def test_monteurin_bekommt_403_nicht_409(welt, router_test_client):
    c = _c(welt, router_test_client, role="field")
    assert c.put(f"/api/customers/{welt.k.id}", json={"last_name": "X"}).status_code == 403
    assert c.put(f"/api/projects/{welt.pj.id}", json={}).status_code == 403


def test_zurueckholen_bleibt_danach_wieder_aenderbar(welt, router_test_client):
    c = _c(welt, router_test_client)
    assert c.post(f"/api/aufbewahrung/kunde/{welt.k.id}/zurueckholen").status_code == 200
    assert c.put(f"/api/customers/{welt.k.id}", json={"last_name": "Zacharias Neu"}).status_code == 200
    # das Projekt bleibt im Archiv, bis es selbst zurückkommt -- „Entarchivieren“ im „⋮“ der Akte zählt als Zurückholen
    assert c.put(f"/api/projects/{welt.pj.id}", json={"customer_id": welt.k.id, "name": "Dach neu"}).status_code == 409
    assert c.post(f"/api/projects/{welt.pj.id}/unarchive").status_code == 200
    assert c.put(f"/api/projects/{welt.pj.id}", json={"customer_id": welt.k.id, "name": "Dach neu"}).status_code == 200
    assert c.put(f"/api/quotes/{welt.angebot.id}/items/{welt.position.id}", json={"short_text": "Rinne neu"}).status_code == 200


def test_projekt_von_hand_archivieren_und_entarchivieren(welt, router_test_client):
    c = _c(welt, router_test_client)
    p = welt.projekt_aktiv.id
    assert c.post(f"/api/projects/{p}/archive").status_code == 200
    assert c.put(f"/api/projects/{p}", json={"customer_id": welt.aktiv.id, "name": "Neu"}).status_code == 409
    assert c.post(f"/api/projects/{p}/unarchive").status_code == 200
    assert c.put(f"/api/projects/{p}", json={"customer_id": welt.aktiv.id, "name": "Neu"}).status_code == 200


def test_kontakt_vermerken_behaelt_seine_meldung(welt, router_test_client):
    from app.routers import kontaktvermerke as kontakte_router
    c = router_test_client(welt.db, kontakte_router.router)
    antwort = c.post(f"/api/customers/{welt.k.id}/kontakte", json={"kontakt_am": "2026-11-02", "weg": "telefon"})
    assert antwort.status_code == 409 and "erst zurückholen, dann den Kontakt vermerken" in antwort.json()["detail"]


# --- Sitzung direkt ---------------------------------------------------------------------------------------------------------------------------------

def test_sitzung_lehnt_ab_und_laesst_die_archivspalten(welt):
    db = welt.db
    db.get(Customer, welt.k.id).city = "Andernorts"
    with pytest.raises(ImArchiv):
        db.commit()
    db.rollback()
    for aendern in (lambda: setattr(db.get(QuoteItem, welt.position.id), "short_text", "x"),
                    lambda: db.delete(db.get(QuoteSection, welt.titel.id)),
                    lambda: db.add(Kontaktvermerk(customer_id=welt.k.id, kontakt_am=date(2026, 11, 2), weg="telefon", created_at=IM_ARCHIV)),
                    lambda: db.add(Inquiry(inquiry_number="AN-NEU", customer_id=welt.aktiv.id, project_id=welt.pj.id, title="x"))):
        aendern()
        with pytest.raises(ImArchiv):
            db.flush()
        db.rollback()
    # über die Beziehung gesetzt (der Fremdschlüssel entsteht erst im Flush): eine neue Position am Angebot im Archiv
    db.add(QuoteItem(quote=db.get(Quote, welt.angebot.id), position_number="2", short_text="Kehle", unit="m"))
    with pytest.raises(ImArchiv):
        db.flush()
    db.rollback()
    # die Archivspalten an der Wurzel ändern sich (Zurückholen, Archivieren von Hand)
    k = db.get(Customer, welt.k.id)
    k.archiviert_am, k.zurueckgeholt_am = None, datetime(2026, 11, 23, 9)
    db.commit()
    db.get(Customer, welt.k.id).city = "Andernorts"
    db.commit()


def test_sitzung_auftrag_am_projekt_im_archiv(welt):
    from tests.quellangebot import quell_angebot  # noqa: F401 -- wie Welt.auftrag(), nur ohne Hilfe
    db = welt.db
    db.add(Order(order_number="AUF-X", project_id=welt.pj.id, source_quote_id=welt.angebot.id, quote_number_snapshot="A-0001", title="Dach",
                 customer_name="x", customer_id=welt.aktiv.id))
    with pytest.raises(ImArchiv) as e:
        db.flush()
    assert e.value.detail == PROJEKT
    db.rollback()


def test_projekt_mit_auftrag_ist_nicht_im_archiv(welt):
    """Ein von Hand archiviertes Projekt mit Auftrag ist nicht im Archiv der Aufbewahrung -- es bleibt änderbar (1.10.18-5)."""
    db = welt.db
    p = db.get(Project, welt.projekt_aktiv.id)
    welt.auftrag(p)
    p.archived = True
    db.commit()
    db.get(Project, p.id).name = "Dach mit Auftrag"
    db.commit()
