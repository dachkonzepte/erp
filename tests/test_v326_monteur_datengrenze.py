"""Version 1.8.22 -- Datengrenze für Monteure, dauerhaft geprüft (siehe docs/archiv/rechtekonzept.md,
Abschnitt "Datengrenze für Monteure: ein Durchlauf über alle GET-Endpunkte").

Anlass: GET /api/orders/{order_id}/roof-areas lieferte dem Monteur die volle Dachfläche
(customer_id, notes, contractor, warranty_until). Der Rollen-Audit-Test (test_v260_role_audit.py)
sieht nur, OB ein Endpunkt eine Rolle prüft -- nicht, WAS er der erlaubten Rolle zurückgibt.

Dieser Test ruft deshalb jeden GET-Endpunkt unter /api/ mit Testdaten als Monteur auf und prüft
jede JSON-Antwort mit Status 200 rekursiv auf verbotene Schlüssel. Die Routen kommen aus app.main
(dieselbe Reihenfolge wie im Betrieb), nicht aus einer Liste in dieser Datei: ein neuer Endpunkt
läuft automatisch mit. Damit er dabei nicht still durchrutscht:
- ein Pfadparameter oder Pflicht-Query-Parameter ohne Testwert färbt den Test rot;
- ein für Monteure freigegebener Endpunkt muss 200 liefern (Ausnahmen einzeln begründet in
  OHNE_200), sonst bliebe seine Antwort ungeprüft; jeder andere muss 403 liefern;
- eine Liste, die beim Monteur leer ankommt, prüft nichts -- auch das ist nur mit Begründung
  erlaubt (LEER_ERLAUBT);
- die Gegenprobe hängt eine Route mit dem alten Dachflächen-Schema in denselben Durchlauf und
  verlangt, dass er sie findet.

Verboten ist ein Schlüssel nach seinem Namen (VERBOTENE_WOERTER/VERBOTENE_WORTTEILE), egal ob der
Wert gefüllt ist -- ein Schema, das das Feld trägt, liefert es spätestens beim nächsten Datensatz.
Wo ein solcher Name beim Monteur richtig ist (die Bemerkung am Prüfpunkt, die Notiz an der eigenen
Zeitbuchung), steht er mit Begründung in ERLAUBT_JE_ROUTE; ein Eintrag dort, der nicht mehr
vorkommt, färbt den Test ebenfalls rot."""

import importlib
import re
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.berlin_time import berlin_today
from app.database import Base, get_db
from app.models import (
    AppUser, Customer, CustomerProfile, Employee, EmployeePayrollSettings, EmployeeProfile, Material, OperationalAsset, Order, OrderItem, PlanningSlot,
    Project, Property, RoofArea, RoofComponent, ServiceReport, Team, TeamEmployee, WorkPreparationTask,
    WorkPreparationTeamAssignment, WorkPreparationTeamEmployee,
)
from app.permissions import ROLE_FIELD, ROLE_OFFICE_AUFTRAG, require_min_role
from app.project_pipeline_columns import default_pipeline_column_id
from app.schemas import EmployeeRosterOut, RoofAreaOut
from tests.test_v260_role_audit import _iter_role_marked_dependants
from tests.uhr import uhr_festhalten

# ---------------------------------------------------------------------------
# Was ein Monteur nie sehen darf: Preise, Kosten, Löhne, Sätze, interne Notizen,
# Kundenkontakt, Gewährleistung, Personaldaten (seit 1.8.24).
# ---------------------------------------------------------------------------

# Ganze Wortteile eines Schlüssels (an "_" getrennt): "notes" trifft "notes" und "review_notes",
# nicht "denotes"; "rate" trifft "vat_rate", nicht "generated".
VERBOTENE_WOERTER = {
    "note", "notes", "remark", "remarks", "comment", "comments",          # interne Notizen
    "rate", "rates",                                                     # Sätze
    "net", "gross", "amount", "fee", "fees", "vat", "margin", "markup", "discount",  # Preise
    "contact", "fax",                                                    # Kundenkontakt
    "iban", "bic",                                                       # Bankverbindung
    "sv", "svnr", "ssn", "idnr",                                         # Sozialversicherungs-, Steuer-ID
}
# Teilzeichenfolgen, auch mitten im Schlüssel (deutsche Zusammensetzungen, "purchase_price").
VERBOTENE_WORTTEILE = (
    "price", "preis", "purchase", "einkauf", "betrag", "subtotal", "line_total", "skonto", "rabatt",
    "cost", "kosten",
    "wage", "lohn", "salary", "gehalt", "compensation", "verguetung", "payroll",
    "satz",
    "intern", "notiz", "vermerk", "bemerkung",
    "email", "phone", "mobile", "telefon",
    "warranty", "gewaehrleistung", "contractor",
    # Personaldaten (seit 1.8.24): Personalnummer (auch die DATEV-Personalnummer), Geburtsdatum,
    # Bankverbindung, Steuer- und Sozialversicherungsdaten. Die Privatadresse trägt keinen eigenen
    # Namen (street/city wie am Objekt) -- siehe _privatadresse().
    "employee_number", "personnel", "personal", "staff_number",
    "birth", "geburt",
    "bank", "account_holder", "kontoinhaber", "sepa",
    "tax", "steuer", "social_security", "sozialvers", "insurance", "versicherung", "krankenkasse",
    "pension", "religion", "konfession", "church", "kirche",
    # "Wichtige Infos" am Mitarbeiter (EmployeeProfile.important_info, seit 1.8.27): Freitext, im
    # Formular für Gesundheitliches gedacht (Allergien, Einschränkungen) -- nie an den Monteur.
    "important", "wichtig",
)
# Überall richtig: Objektzugang und Ansprechpartner vor Ort (PropertyAccessOut, seit 1.3.53 eigens
# für den Einsatz gebaut) und der Kundenname (OrderFieldAccessOut, Objektsuche seit 1.3.65).
UEBERALL_ERLAUBT = {"access_notes", "site_contact_name", "site_contact_phone", "customer_name"}

# (Route, Pfad.Schlüssel; * steht für beliebige Zeichen) -> warum der Monteur das sehen soll.
_PRUEFPUNKT_BEMERKUNG = ("Bemerkung am Prüfpunkt: Teil des Prüfergebnisses, steht auf dem Kunden-PDF "
                         "(rechtekonzept.md, Wartungshistorie 1.3.56)")
_BEDIENHINWEIS = ("Bedienungshinweis zum Gerät, eigens für den Monteur getrennt von notes "
                  "(OperationalAssetFieldOut, modul-betriebsmittel-und-betriebskosten.md, Stufe 2)")
ERLAUBT_JE_ROUTE = {
    ("/api/service-reports/{report_id}/inspection-items", "$[].notes"): _PRUEFPUNKT_BEMERKUNG,
    ("/api/field-view/properties/{property_id}/maintenance-history", "$[].inspection_items[].notes"): _PRUEFPUNKT_BEMERKUNG,
    ("/api/orders/{order_id}/property-service-reports", "$[].inspection_items[].notes"): _PRUEFPUNKT_BEMERKUNG,
    ("/api/service-reports/{report_id}/materials", "$[].notes"): "Bemerkung des Monteurs zum Material im eigenen Bericht",
    ("/api/service-reports/{report_id}/assets", "$[].notes"): "Bemerkung des Monteurs zum Geräteeinsatz im eigenen Bericht",
    ("/api/time-entries", "$[].notes"): "eigene Zeitbuchung (self-scoped seit 1.3.56), die Notiz schreibt er selbst",
    ("/api/time-entries/active", "$.notes"): "eigene laufende Zeitbuchung",
    ("/api/time-entry-groups/active", "$.notes"): "Notiz der Kolonnenbuchung, in der er selbst mitgebucht ist (1.7.12)",
    ("/api/time-entry-groups/mine", "$[].notes"): "Notiz der Kolonnenbuchung, in der er selbst mitgebucht ist (1.7.12)",
    ("/api/absence-requests", "$[].notes"): "eigener Abwesenheitsantrag, die Notiz schreibt er selbst",
    ("/api/absence-requests", "$[].review_notes"): "Antwort des Büros auf seinen eigenen Antrag",
    ("/api/time-tracking/settings", "$.datev_wage_type_*"): ("DATEV-Lohnart: Buchungsschlüssel, kein Betrag "
                                                             "(rechtekonzept.md, Vier Rollen, Etappe 2 Punkt 4)"),
    ("/api/time-tracking/settings", "$.datev_personnel_equals_erp_number"): ("Schalter des Backoffice (DATEV- gleich "
                                                                             "ERP-Personalnummer), ein Wahrheitswert, "
                                                                             "keine Nummer"),
    ("/api/checklists/asset-readiness/{asset_id}", "$.release_note"): ("Reparaturvermerk zur Einsatzbereitschaft "
                                                                       "des Geräts (modul-checklisten.md, 1.8.2)"),
    ("/api/operational-assets/{asset_id}", "$.usage_notes"): _BEDIENHINWEIS,
    ("/api/operational-assets/selectable-for-report", "$[].usage_notes"): _BEDIENHINWEIS,
}

# Für Monteure freigegeben, aber ohne 200 im Durchlauf -- jeweils mit Grund.
OHNE_200 = {
    "/api/settings/general/logo": "Bilddatei statt JSON; ohne hochgeladenes Logo 404",
    "/api/settings/general/sidebar-logo": "Bilddatei statt JSON; ohne hochgeladenes Logo 404",
}
# Für Monteure freigegeben, Antwort im Durchlauf leer -- jeweils mit Grund.
LEER_ERLAUBT: dict[str, str] = {}


def _verboten(key: str) -> bool:
    k = key.lower()
    if k in UEBERALL_ERLAUBT:
        return False
    if k.startswith("customer_"):
        return True  # Kundennummer, -adresse, -ID: alles am Kunden außer dem Namen
    if set(re.split(r"[^a-z0-9]+", k)) & VERBOTENE_WOERTER:
        return True
    return any(teil in k for teil in VERBOTENE_WORTTEILE)


# Privatadresse (seit 1.8.24): Adressfelder heißen am Mitarbeiter wie am Objekt (EmployeeProfile:
# street/postal_code/city/country). Am Objekt braucht der Monteur sie, an einer Person nie --
# verboten deshalb jedes Adressfeld unter einem Personen-Knoten (Pfad) oder einer Personen-Route.
ADRESS_WOERTER = {"street", "strasse", "postal", "zip", "plz", "city", "ort", "country", "land",
                  "address", "adresse", "wohnort", "house", "hausnummer"}
PERSONEN_WORTTEILE = ("employee", "member", "mitarbeiter", "kollege", "colleague", "user", "person",
                      "crew", "leader", "staff")


def _privatadresse(route: str, path: str, key: str) -> bool:
    if not set(re.split(r"[^a-z0-9]+", key.lower())) & ADRESS_WOERTER:
        return False
    return any(teil in f"{route} {path}".lower() for teil in PERSONEN_WORTTEILE)


def _passt(full: str, muster: str) -> bool:
    """Wie fnmatch, aber nur mit * -- fnmatch läse das [] der Listenpfade als Zeichenklasse."""
    return re.fullmatch(".*".join(map(re.escape, muster.split("*"))), full) is not None


def _schluessel(value, path="$"):
    """(Pfad, Schlüssel) für jeden Schlüssel einer JSON-Antwort, Listenindizes als []."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield path, key
            yield from _schluessel(child, f"{path}.{key}")
    elif isinstance(value, list):
        for child in value:
            yield from _schluessel(child, f"{path}[]")


def _verstoesse(antworten: list[dict]) -> tuple[list[str], set]:
    """Verbotene Schlüssel je Route, dazu die Ausnahmen, die tatsächlich gegriffen haben."""
    gefunden, genutzt = set(), set()
    for antwort in antworten:
        if antwort["body"] is None:
            continue
        for path, key in _schluessel(antwort["body"]):
            if not (_verboten(key) or _privatadresse(antwort["route"], path, key)):
                continue
            full = f"{path}.{key}"
            erlaubt = [e for e in ERLAUBT_JE_ROUTE if e[0] == antwort["route"] and _passt(full, e[1])]
            if erlaubt:
                genutzt.update(erlaubt)
            else:
                gefunden.add(f"{antwort['route']}  {full}")
    return sorted(gefunden), genutzt


# ---------------------------------------------------------------------------
# Testdaten: ein Monteur mit Einsatz, Berichten, Zeiten, Checkliste, Dokument -- und
# überall Werte, die er nicht sehen darf.
# ---------------------------------------------------------------------------

def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (40, 20), (10, 120, 90)).save(buf, format="PNG")
    return buf.getvalue()


def _auftrag(db: Session, nummer: int, customer: Customer, prop: Property) -> Order:
    project = Project(project_number=f"P-2026-{nummer:04d}", name="Sanierung Halle Süd", customer_id=customer.id,
                      property_id=prop.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.flush()
    order = Order(order_number=f"AU-2026-{nummer:04d}", project_id=project.id, source_quote_id=nummer,
                  quote_number_snapshot=f"A-2026-{nummer:04d}", title="Dachsanierung", customer_name=customer.name,
                  customer_number="K-4711", customer_address="Privatweg 9\n11111 Kundenstadt",
                  property_name=prop.name, property_address="Werkstr. 5\n22222 Objektstadt",
                  payment_terms="14 Tage netto", remarks="Interne Auftragsbemerkung")
    db.add(order)
    db.flush()
    db.add(OrderItem(order_id=order.id, sort_order=10, position_number="1", short_text="Abdichtung",
                     quantity=Decimal("850"), unit="m²", unit_price=Decimal("48.90")))
    db.commit()
    return order


def _monteur_welt(db: Session) -> dict:
    from app.absence_requests import create_request
    from app.checklist_templates import add_field, create_template, publish_draft
    from app.checklists import add_attachment, complete_checklist, create_checklist, save_answer
    from app.document_categories import ensure_default_categories, resolve_category_id
    from app.findings import create_finding
    from app.inspection_templates import create_template as create_inspection_template
    from app.inspection_templates import create_template_item
    from app.maintenance_contracts import create_contract
    from app.property_documents import create_property_document
    from app.service_reports import (
        add_asset_usage, add_inspection_item, add_material, add_photo, create_report, update_inspection_item,
    )
    from app.time_tracking import create_manual_entry, start_group_timer
    from app.work_preparation import ensure_preparation

    today = berlin_today()
    monteur = Employee(employee_number="M-1", first_name="Max", last_name="Monteur", job_title="Dachdecker",
                       employee_group="angestellt", hourly_wage=Decimal("31.50"), weekly_hours=Decimal("40"), active=True)
    kollege = Employee(employee_number="M-2", first_name="Karl", last_name="Kollege", job_title="Geselle",
                       employee_group="angestellt", hourly_wage=Decimal("29.00"), weekly_hours=Decimal("40"), active=True)
    db.add_all([monteur, kollege])
    db.flush()
    for nr, emp in enumerate((monteur, kollege), start=1):
        db.add(EmployeeProfile(employee_id=emp.id, street=f"Wohnweg {nr}", postal_code="33333", city="Wohnort",
                               phone="0555 1", mobile="0171 2", email=f"privat{nr}@example.org",
                               birthday=date(1990, 1, nr), important_info="Allergie gegen Bitumen"))
        db.add(EmployeePayrollSettings(employee_id=emp.id, datev_personnel_number=f"D-{nr}"))
    user = AppUser(username="max", password_hash=hash_password("Passwort123"), display_name="Max Monteur",
                   employee_id=monteur.id, role=ROLE_FIELD, active=True)
    db.add(user)

    customer = Customer(name="Kundin Klar", last_name="Klar", email="kundin@example.org", phone="0123 456",
                        mobile="0170 111", contact_person="Frau Klar", street="Privatweg 9", postal_code="11111",
                        city="Kundenstadt", notes="Zahlt langsam")
    db.add(customer)
    db.flush()
    db.add(CustomerProfile(customer_id=customer.id, customer_number="K-4711"))
    prop = Property(customer_id=customer.id, name="Halle Süd", street="Werkstr. 5", postal_code="22222",
                    city="Objektstadt", notes="Büro-intern: Streit mit der Hausverwaltung",
                    access_notes="Schlüssel beim Pförtner", site_contact_name="Herr Vorort", site_contact_phone="0999 1")
    db.add(prop)
    db.flush()
    roof = RoofArea(property_id=prop.id, name="Hauptdach", roof_type="flachdach", covering="Bitumen",
                    pitch_degrees=Decimal("3"), area_sqm=Decimal("850"), contractor="Fremdfirma GmbH",
                    warranty_until=date(2031, 5, 1), last_renovation=date(2016, 5, 1),
                    notes="Gewährleistungsstreit mit der Fremdfirma")
    db.add(roof)
    db.flush()
    db.add(RoofComponent(roof_area_id=roof.id, name="Gully Nordost", notes="Bauteil-Notiz"))
    material = Material(name="Bitumenbahn", unit="m²", purchase_price=Decimal("12.34"), price_basis=Decimal("1"),
                        source="manual")
    asset = OperationalAsset(name="Hubsteiger", asset_type="Maschine", asset_number="BM-7",
                             acquisition_cost=Decimal("45000"), cost_notes="Leasing bis 2028",
                             notes="Büro-Notiz zum Gerät", active=True, selectable_in_reports=True)
    db.add_all([material, asset])
    db.commit()
    order = _auftrag(db, 901, customer, prop)
    frueherer_auftrag = _auftrag(db, 902, customer, prop)

    inspection_template = create_inspection_template(db, "Flachdach-Wartung", roof_type="flachdach")
    create_template_item(db, inspection_template["id"], "Abdichtung Sichtprüfung", "ja_nein")

    # Einsatz: Kolonne (Monteur ist Kolonnenführer) an der AV, Termin heute.
    prep = ensure_preparation(db, order.id)
    prep.site_notes = "Baustellenhinweis"
    team = Team(name="Kolonne Süd", active=True)
    db.add(team)
    db.flush()
    db.add_all([TeamEmployee(team_id=team.id, employee_id=monteur.id, is_crew_leader=True),
                TeamEmployee(team_id=team.id, employee_id=kollege.id)])
    assignment = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
    db.add(assignment)
    db.flush()
    for emp in (monteur, kollege):
        db.add(WorkPreparationTeamEmployee(assignment_id=assignment.id, employee_id=emp.id,
                                           employee_name_snapshot=f"{emp.first_name} {emp.last_name}"))
    db.add(PlanningSlot(preparation_id=prep.id, team_assignment_id=assignment.id, start_date=today,
                        end_date=today + timedelta(days=1), notes="Slot-Notiz der Planung"))
    db.add(WorkPreparationTask(preparation_id=prep.id, title="Gerüst prüfen", status="offen",
                               assigned_employee_id=monteur.id, notes="Aufgabennotiz"))
    db.commit()

    # Eigener, unterschriebener Bericht mit allem, was ein Bericht tragen kann; ein eigener Entwurf;
    # ein Entwurf des Kollegen auf demselben Auftrag; ein unterschriebener Bericht des Kollegen auf
    # einem früheren Auftrag desselben Objekts (Wartungshistorie).
    report_id = create_report(db, order.id, "wartung", description="Eigener Bericht",
                              created_by_employee_id=monteur.id, roof_area_ids=[roof.id])["id"]
    inspection = add_inspection_item(db, report_id, "Gully Nordost", "ja_nein", group_name="Entwässerung",
                                     roof_area_id=roof.id)
    update_inspection_item(db, inspection["id"], {"result": "nok", "notes": "Laub entfernt"})
    create_finding(db, report_id, "Gully verstopft", "mittel", "sofort_behoben",
                   inspection_item_id=inspection["id"], created_by_employee_id=monteur.id)
    photo = add_photo(db, report_id, _png(), "foto.png", inspection_item_id=inspection["id"],
                      created_by_employee_id=monteur.id)
    add_material(db, report_id, material_id=material.id, quantity=Decimal("2"), notes="Rest im Fahrzeug",
                 created_by_employee_id=monteur.id)
    add_asset_usage(db, report_id, asset_id=asset.id, notes="2 Stunden", created_by_employee_id=monteur.id)
    db.get(ServiceReport, report_id).status = "unterschrieben"
    db.commit()
    create_report(db, order.id, "rapport", description="Eigener Entwurf", created_by_employee_id=monteur.id)
    create_report(db, order.id, "rapport", description="Bericht des Kollegen", created_by_employee_id=kollege.id)
    frueher_id = create_report(db, frueherer_auftrag.id, "wartung", description="Wartung im Vorjahr",
                               created_by_employee_id=kollege.id, roof_area_ids=[roof.id])["id"]
    frueher_item = add_inspection_item(db, frueher_id, "Attika", "ja_nein", roof_area_id=roof.id)
    update_inspection_item(db, frueher_item["id"], {"result": "ok", "notes": "ohne Befund"})
    create_finding(db, frueher_id, "Riss in der Attika", "gering", "sofort_behoben", created_by_employee_id=kollege.id)
    db.get(ServiceReport, frueher_id).status = "unterschrieben"
    db.commit()

    create_manual_entry(db, employee_id=monteur.id, order_id=order.id, work_date=today, hours=Decimal("4"),
                        notes="Eigene Notiz", created_by_user_id=user.id)
    create_manual_entry(db, employee_id=kollege.id, order_id=order.id, work_date=today, hours=Decimal("3"),
                        notes="Notiz des Kollegen")
    start_group_timer(db, employee_ids=[monteur.id, kollege.id], team_id=team.id, actor_employee_id=monteur.id,
                      is_admin=False, order_id=order.id, notes="Kolonne läuft", created_by_user_id=user.id)
    create_request(db, employee_id=monteur.id, absence_type="Urlaub", absence_category="urlaub",
                   start_date=today + timedelta(days=30), end_date=today + timedelta(days=31), notes="Familienfeier")
    create_contract(db, customer.id, prop.id, "Wartung Halle Süd", 12, next_due_date=today,
                    notes="Vertragsnotiz fürs Büro")

    ensure_default_categories(db)
    document = create_property_document(
        db, prop.id, category_id=resolve_category_id(db, "Pläne"), file_data=b"%PDF-1.4\n%%EOF\n",
        original_filename="dachplan.pdf", content_type="application/pdf", description="Dachplan",
        uploaded_by_employee_id=monteur.id,
    )

    template = create_template(db, label="Sicherheitscheck", contexts=["auftrag", "objekt", "betriebsmittel"],
                               field_readable=True)
    version_id = template["draft_version_id"]
    add_field(db, version_id, {"field_type": "text", "label": "Bemerkung", "field_key": "bem"})
    add_field(db, version_id, {"field_type": "foto", "label": "Fotos", "field_key": "fotos"})
    publish_draft(db, template["id"])
    checklist = create_checklist(db, template_id=template["id"], context_type="auftrag", order_id=order.id,
                                 created_by_employee_id=monteur.id, created_by_user_id=user.id)
    field_ids = {f["field_key"]: f["id"] for f in checklist["fields"]}
    save_answer(db, checklist["id"], field_ids["bem"], "alles sicher", recorded_by_employee_id=monteur.id)
    add_attachment(db, checklist["id"], field_ids["fotos"], _png(), created_by_employee_id=monteur.id)
    checklist = complete_checklist(db, checklist["id"], completed_by_employee_id=monteur.id)
    offen = create_checklist(db, template_id=template["id"], context_type="objekt", property_id=prop.id,
                             created_by_employee_id=monteur.id, created_by_user_id=user.id)
    save_answer(db, offen["id"], field_ids["bem"], "Zugang frei", recorded_by_employee_id=monteur.id)

    return {
        "user_id": user.id, "employee_id": monteur.id, "order_id": order.id, "report_id": report_id,
        "property_id": prop.id, "roof_area_id": roof.id, "asset_id": asset.id, "photo_id": photo["id"],
        "document_id": document.id, "checklist_id": checklist["id"],
        "attachment_id": checklist["attachments"][0]["id"], "customer_id": customer.id,
        "project_id": order.project_id, "material_id": material.id, "item_id": inspection["id"],
        "team_id": team.id, "kollege_id": kollege.id,
    }


# ---------------------------------------------------------------------------
# Der Durchlauf
# ---------------------------------------------------------------------------

# Pfadparameter, die nicht direkt aus den Testdaten kommen. Für Endpunkte, die der Monteur nicht
# erreicht, genügt irgendein Wert: dort entscheidet die Rollenprüfung vor jedem Datenbankzugriff.
PFAD_WERTE = {
    "source": "property", "group_key": "time_entry_types", "size": "192",
    "document_type": "invoice", "page_type": "orders", "sequence_key": "invoice",
    "quote_id": 1, "inquiry_id": 1, "supplier_id": 1, "resource_id": 1, "service_id": 1, "invoice_id": 1,
    "reminder_id": 1, "contract_id": 1, "inspection_id": 1, "cost_id": 1, "account_id": 1, "event_id": 1,
    "template_id": 1, "component_id": 1, "task_id": 1, "version_id": 1, "sent_document_id": 1,
}
# Query-Parameter: Pflichtparameter nach Namen, dazu je Route, was die Monteursicht erst füllt.
# "@name" steht für den Wert aus den Testdaten.
QUERY_WERTE = {"start": "2026-01-01", "end": "2026-12-31", "start_date": "2026-01-01", "end_date": "2026-12-31",
               "property_id": "@property_id", "context": "auftrag"}
QUERY_JE_ROUTE = {
    "/api/field-view/properties/search": {"q": "Halle"},
    "/api/checklists": {"order_id": "@order_id"},
}


def _routers_in_betriebsreihenfolge() -> list:
    """Die Router in der Reihenfolge, in der app/main.py sie einbindet -- davon hängt ab, welche
    Route eine URL zuerst fängt."""
    from app import main
    routers = []
    for entry in main.app.routes:
        # FastAPI 0.141 hängt eingebundene Router als _IncludedRouter(original_router=...) an,
        # ältere Fassungen kopieren die einzelnen Routen.
        router = getattr(entry, "original_router", None)
        if router is None:
            module = getattr(getattr(entry, "endpoint", None), "__module__", "")
            router = importlib.import_module(module).router if module.startswith("app.routers.") else None
        if router is not None and router not in routers:
            routers.append(router)
    assert len(routers) > 50, "Router aus app.main nicht gefunden -- hat sich die Einbindung geändert?"
    return routers


def _monteur_client(db: Session, routers, user_id: int) -> TestClient:
    """Wie router_test_client(), aber mit dem gespeicherten Monteur-Konto statt einer transienten
    Identität -- einige Endpunkte filtern nach der Benutzer-ID (created_by_user_id)."""
    app = FastAPI()
    for router in routers:
        app.include_router(router)
    user = db.get(AppUser, user_id)

    @app.middleware("http")
    async def _monteur(request, call_next):
        request.state.erp_user = user
        return await call_next(request)

    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def _fuer_monteure_offen(route: APIRoute) -> bool:
    markers = list(_iter_role_marked_dependants(route.dependant))
    return not markers or all(ROLE_FIELD in roles for roles in markers)


def _wert(welt: dict, value):
    return welt[value[1:]] if isinstance(value, str) and value.startswith("@") else value


def _durchlauf(db: Session, welt: dict, routers) -> dict:
    client = _monteur_client(db, routers, welt["user_id"])
    ohne_wert, antworten = [], []
    for router in routers:
        for route in router.routes:
            if not isinstance(route, APIRoute) or not route.path.startswith("/api/") or "GET" not in route.methods:
                continue
            werte = {}
            for param in route.dependant.path_params:
                wert = welt.get(param.name, PFAD_WERTE.get(param.name))
                if wert is None:
                    ohne_wert.append(f"{route.path}: Pfadparameter {param.name}")
                werte[param.name] = wert
            query = {k: _wert(welt, v) for k, v in QUERY_JE_ROUTE.get(route.path, {}).items()}
            for param in route.dependant.query_params:
                if param.field_info.is_required() and param.name not in query:
                    if param.name not in QUERY_WERTE:
                        ohne_wert.append(f"{route.path}: Query-Parameter {param.name}")
                        continue
                    query[param.name] = _wert(welt, QUERY_WERTE[param.name])
            if any(v is None for v in werte.values()):
                continue
            response = client.get(route.path.format(**werte), params=query)
            is_json = response.headers.get("content-type", "").startswith("application/json")
            body = response.json() if response.status_code == 200 and is_json else None
            antworten.append({"route": route.path, "status": response.status_code, "json": is_json,
                              "monteur": _fuer_monteure_offen(route), "body": body})
    return {"ohne_wert": ohne_wert, "antworten": antworten}


@pytest.fixture(scope="module")
def durchlauf():
    """Einmal Testdaten anlegen und einmal durchlaufen -- alle Prüfungen unten lesen dasselbe
    Ergebnis. Eigene Datenbank wie threaded_db_session (die ist je Test, das hier je Modul).

    Feste Uhr (seit 1.8.36, tests/uhr.py): /api/field-view/today meldet den Monteur ab 19 Uhr ab
    (401 "Feierabend") -- ohne sie war der Durchlauf abends rot."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        with uhr_festhalten():
            welt = _monteur_welt(db)
            yield {"db": db, "welt": welt, **_durchlauf(db, welt, _routers_in_betriebsreihenfolge())}
    finally:
        db.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# Die Prüfungen
# ---------------------------------------------------------------------------

def test_jeder_get_endpunkt_bekommt_testwerte(durchlauf):
    """Ein neuer Endpunkt mit einem Parameter, den dieser Test nicht kennt, fällt hier auf statt
    still übersprungen zu werden -- Wert in PFAD_WERTE/QUERY_WERTE ergänzen."""
    assert durchlauf["ohne_wert"] == []
    assert len(durchlauf["antworten"]) > 200


def test_monteur_endpunkte_liefern_200_und_alle_anderen_403(durchlauf):
    antworten = durchlauf["antworten"]
    monteur_routen = {a["route"] for a in antworten if a["monteur"]}
    assert set(OHNE_200) <= monteur_routen, "OHNE_200 nennt eine Route, die es nicht (mehr) gibt"
    ohne_200 = [f"{a['status']} {a['route']}" for a in antworten
                if a["monteur"] and a["status"] != 200 and a["route"] not in OHNE_200]
    assert ohne_200 == [], "Für Monteure freigegeben, Antwort ungeprüft -- Testdaten ergänzen oder begründen"
    nicht_gesperrt = [f"{a['status']} {a['route']}" for a in antworten if not a["monteur"] and a["status"] != 403]
    assert nicht_gesperrt == []
    assert len(monteur_routen) >= 50


def test_monteur_antworten_sind_nicht_leer(durchlauf):
    """Eine leere Liste oder null prüft keinen einzigen Schlüssel -- jede JSON-Antwort an den
    Monteur soll Inhalt haben, sonst Testdaten ergänzen (oder in LEER_ERLAUBT begründen)."""
    leer = sorted(a["route"] for a in durchlauf["antworten"]
                  if a["monteur"] and a["status"] == 200 and a["json"] and a["body"] in ([], {}, None)
                  and a["route"] not in LEER_ERLAUBT)
    assert leer == []
    assert set(LEER_ERLAUBT) <= {a["route"] for a in durchlauf["antworten"] if a["monteur"]}


def test_keine_verbotenen_schluessel_in_monteur_antworten(durchlauf):
    gefunden, genutzt = _verstoesse(durchlauf["antworten"])
    assert gefunden == [], "\n".join(["Verbotene Schlüssel in Monteur-Antworten:", *gefunden])
    assert set(ERLAUBT_JE_ROUTE) - genutzt == set(), "Ausnahme greift nicht mehr -- aus ERLAUBT_JE_ROUTE streichen"


def test_vertragsrouten_im_durchlauf_fuer_monteure_gesperrt(durchlauf):
    """Seit 1.8.32: Vertrag am Auftrag und Vertragsvorlagen sind kaufmännisch -- der Durchlauf ruft
    jede GET-Route davon auf, und jede antwortet dem Monteur mit 403. Seit 1.8.33 auch die Auswahl der
    Anlage beim Festschreiben."""
    vertrag = {a["route"]: a["status"] for a in durchlauf["antworten"]
               if "/contract" in a["route"] and "contract-bases" not in a["route"]
               and "contract-basis" not in a["route"]}
    assert vertrag == {
        "/api/settings/contract-templates": 403,
        "/api/orders/{order_id}/contract": 403,
        "/api/orders/{order_id}/contract/pdf": 403,
        "/api/orders/{order_id}/contract/attachment-options": 403,
    }


def test_dachflaechen_monteur_reduziert_buero_voll(durchlauf, router_test_client):
    """Punkt 1 dieser Runde: der Monteur bekommt nur, was die Berichtsseite braucht, plus die
    technischen Angaben zur Fläche; das Büro unverändert alles."""
    from app.routers.service_reports import router as service_reports_router
    db, welt = durchlauf["db"], durchlauf["welt"]
    url = f"/api/orders/{welt['order_id']}/roof-areas"
    monteur = next(a for a in durchlauf["antworten"] if a["route"] == "/api/orders/{order_id}/roof-areas")
    assert [set(row) for row in monteur["body"]] == [
        {"id", "name", "roof_type", "covering", "pitch_degrees", "area_sqm"},
    ]
    assert monteur["body"][0]["name"] == "Hauptdach"
    office = router_test_client(db, service_reports_router, role=ROLE_OFFICE_AUFTRAG).get(url)
    assert office.status_code == 200
    assert office.json()[0]["warranty_until"] == "2031-05-01"
    assert office.json()[0]["contractor"] == "Fremdfirma GmbH"
    assert office.json()[0]["customer_id"] == welt["customer_id"]


def test_gegenprobe_altes_dachflaechen_schema_faellt_auf(threaded_db_session):
    """Dieselbe Route mit dem alten Schema, als neuer Endpunkt in denselben Durchlauf gehängt:
    er muss sie finden, ohne dass dieser Test sie irgendwo einzeln nennt."""
    from app.routers.orders import require_field_order_access
    from app.service_reports import list_roof_areas_for_order
    db = threaded_db_session
    welt = _monteur_welt(db)
    altes_schema = APIRouter()

    @altes_schema.get("/api/orders/{order_id}/roof-areas-alt", response_model=list[RoofAreaOut])
    def _alt(order_id: int, db: Session = Depends(get_db), _role: AppUser = Depends(require_min_role(ROLE_FIELD))):
        require_field_order_access(db, _role, order_id)
        return list_roof_areas_for_order(db, order_id)

    ergebnis = _durchlauf(db, welt, [*_routers_in_betriebsreihenfolge(), altes_schema])
    gefunden, _ = _verstoesse(ergebnis["antworten"])
    alt = {eintrag.split("  ")[1] for eintrag in gefunden if eintrag.startswith("/api/orders/{order_id}/roof-areas-alt")}
    assert {"$[].customer_id", "$[].notes", "$[].contractor", "$[].warranty_until"} <= alt
    assert all(eintrag.startswith("/api/orders/{order_id}/roof-areas-alt") for eintrag in gefunden)


def test_zeiterfassungs_kontext_monteur_nur_eigenes_buero_unveraendert(durchlauf, router_test_client):
    """1.8.24, Punkt 1: GET /api/time-tracking/context gibt dem Monteur nur sich selbst, als
    Kolonnenführer seine Kolonne, und seine buchbaren Aufträge -- dieselben wie die Auftragsauswahl
    der mobilen Zeiterfassung, die /context selbst nicht aufruft. Keine Personalnummer. Das Büro
    bekommt unverändert, was time_tracking_context() liefert."""
    from app.routers.time_tracking import router as time_tracking_router
    from app.time_tracking import time_tracking_context
    db, welt = durchlauf["db"], durchlauf["welt"]
    antworten = {a["route"]: a["body"] for a in durchlauf["antworten"]}
    max_, karl = welt["employee_id"], welt["kollege_id"]

    # Max ist Kolonnenführer der Kolonne Süd (mit Karl).
    ctx = antworten["/api/time-tracking/context"]
    assert set(ctx) == {"employees", "teams", "orders", "current_employee_id", "is_admin"}
    assert sorted(ctx["employees"], key=lambda e: e["id"]) == [{"id": max_, "name": "Max Monteur"},
                                                             {"id": karl, "name": "Karl Kollege"}]
    assert [(t["id"], t["name"], set(t)) for t in ctx["teams"]] == [(welt["team_id"], "Kolonne Süd", {"id", "name", "employees"})]
    assert sorted(m["id"] for m in ctx["teams"][0]["employees"]) == sorted([max_, karl])
    assert ctx["orders"] == antworten["/api/field-view/time-tracking/orders"]
    assert {o["order_number"] for o in ctx["orders"]} == {"AU-2026-0901"}
    assert (ctx["current_employee_id"], ctx["is_admin"]) == (max_, False)

    # Karl ist in derselben Kolonne, aber nicht Kolonnenführer: nur er selbst, keine Teams.
    karl_ctx = router_test_client(db, time_tracking_router, role=ROLE_FIELD, employee_id=karl).get("/api/time-tracking/context").json()
    assert karl_ctx["employees"] == [{"id": karl, "name": "Karl Kollege"}]
    assert karl_ctx["teams"] == []
    assert {o["order_number"] for o in karl_ctx["orders"]} == {"AU-2026-0901", "AU-2026-0902"}

    # Ohne jeden Einsatz: vorher alle offenen Aufträge des Betriebs (time_tracking_context() filtert
    # nur, wenn es Zuordnungen gibt), jetzt keine.
    neu = Employee(employee_number="M-3", first_name="Nina", last_name="Neu", employee_group="gewerblich", active=True)
    db.add(neu)
    db.commit()
    assert len(time_tracking_context(db, employee_id=neu.id)["orders"]) == 2
    neu_ctx = router_test_client(db, time_tracking_router, role=ROLE_FIELD, employee_id=neu.id).get("/api/time-tracking/context").json()
    assert (neu_ctx["employees"], neu_ctx["teams"], neu_ctx["orders"]) == ([{"id": neu.id, "name": "Nina Neu"}], [], [])

    # Büro unverändert, mit Personalnummer und LV-Positionen.
    office = router_test_client(db, time_tracking_router, role=ROLE_OFFICE_AUFTRAG, employee_id=karl).get("/api/time-tracking/context").json()
    assert office == {**time_tracking_context(db, employee_id=karl), "current_employee_id": karl, "is_admin": False}
    assert {"M-1", "M-2", "M-3"} <= {e["employee_number"] for e in office["employees"]}
    assert all("items" in o for o in office["orders"])


def test_gegenprobe_alter_kontext_und_mitarbeiterbestand_fallen_auf(threaded_db_session):
    """1.8.24, Punkt 2: der alte Zeiterfassungs-Kontext (Büro-Fassung, wie bis 1.8.23 an den Monteur)
    und der Mitarbeiterbestand im Büro-Schema, als neue Endpunkte in denselben Durchlauf gehängt.
    Er muss Personalnummer, Geburtsdatum und Privatadresse finden, ohne die Routen zu kennen."""
    from app.employees import employee_to_dict, ensure_employee_profiles
    from app.time_tracking import time_tracking_context
    db = threaded_db_session
    welt = _monteur_welt(db)
    alt = APIRouter()

    @alt.get("/api/time-tracking/context-alt")
    def _kontext_alt(db: Session = Depends(get_db), _role: AppUser = Depends(require_min_role(ROLE_FIELD))):
        return time_tracking_context(db, employee_id=_role.employee_id)

    @alt.get("/api/employees-alt", response_model=list[EmployeeRosterOut])
    def _bestand_alt(db: Session = Depends(get_db), _role: AppUser = Depends(require_min_role(ROLE_FIELD))):
        return [EmployeeRosterOut.model_validate(employee_to_dict(e, db)) for e in ensure_employee_profiles(db)]

    ergebnis = _durchlauf(db, welt, [*_routers_in_betriebsreihenfolge(), alt])
    gefunden, _ = _verstoesse(ergebnis["antworten"])
    je_route: dict[str, set] = {}
    for eintrag in gefunden:
        route, pfad = eintrag.split("  ")
        je_route.setdefault(route, set()).add(pfad)
    assert set(je_route) == {"/api/time-tracking/context-alt", "/api/employees-alt"}
    assert je_route["/api/time-tracking/context-alt"] == {"$.employees[].employee_number"}
    assert {"$[].employee_number", "$[].birthday", "$[].street", "$[].postal_code", "$[].city",
            "$[].country", "$[].important_info"} <= je_route["/api/employees-alt"]


@pytest.mark.parametrize("key", [
    "employee_number", "datev_personnel_number", "personalnummer", "birthday", "date_of_birth", "geburtsdatum",
    "iban", "bic", "bank_name", "account_holder", "tax_id", "tax_class", "steuerklasse", "steuer_id",
    "social_security_number", "sozialversicherungsnummer", "sv_nummer", "health_insurance", "krankenkasse",
    "church_tax", "konfession", "important_info", "wichtige_infos",
])
def test_personaldaten_schluessel_sind_verboten(key):
    assert _verboten(key)


@pytest.mark.parametrize("route,path,key,erwartet", [
    ("/api/employees-alt", "$[]", "street", True),
    ("/api/time-tracking/context", "$.employees[]", "city", True),
    ("/api/time-tracking/crews", "$[].members[]", "postal_code", True),
    ("/api/field-view/properties/{property_id}", "$", "street", False),
    ("/api/time-tracking/context", "$.orders[]", "property_address", False),
    ("/api/employees", "$[]", "first_name", False),
])
def test_privatadresse_nur_an_personen(route, path, key, erwartet):
    assert _privatadresse(route, path, key) is erwartet
