"""Version 1.8.70 -- Strukturtest: jede ID aus der Anfrage läuft über eine Zugehörigkeitsprüfung.

Fehlerklasse (Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ Punkt 2, docs/archiv/befund-vor-echtbetrieb.md): der Server
speicherte IDs aus der Anfrage, ohne zu prüfen, dass sie zum selben Objekt, Auftrag oder Kunden gehören -- die Dachfläche eines
fremden Objekts im Einsatzbericht, die Position eines fremden Auftrags in der Rechnung, das Objekt eines anderen Kunden am
Schnellauftrag. Jede Stelle einzeln war unauffällig; erst die Suche über den ganzen Code fand neun.

Der Test geht jede Route aus app.main durch (keine Liste im Test) und findet
  - jede ID-Eingabe einer schreibenden Route (POST/PUT/PATCH/DELETE): Feld *_id/*_ids im Body (auch verschachtelt, z. B.
    items.section_id), als Formularfeld oder Query-Parameter;
  - jedes Paar von IDs im Pfad (jede Methode): die zweite muss zur ersten gehören (/quotes/{quote_id}/items/{item_id}).
Jede gefundene Eingabe ist eingeordnet:
  STAMMDATEN  nach Feldname: das Ziel gehört keinem Objekt, Auftrag oder Kunden (Mitarbeiter, Steuerschlüssel, Katalog …);
  GEPRUEFT    je Route und Feld: die Funktion, in der die Prüfung steht, und der Vergleich selbst. Der Test verlangt, dass die
              Funktion vom Endpunkt aus aufgerufen wird (Aufrufgraph über app/, per AST) und den Vergleich wörtlich enthält
              (Leerzeichen egal) -- fällt der Vergleich weg oder wird die Funktion nicht mehr erreicht, ist der Test rot;
  FREI        je Route und Feld, mit Grund: die ID legt den Besitzer oder Kontext des Datensatzes erst fest (Kunde eines neuen
              Objekts, Projekt einer Eingangsrechnung) -- jede VORHANDENE ist richtig. Seit 1.8.71 dazu wie bei GEPRUEFT die
              Funktion und der Vergleich, mit dem die Existenz geprüft wird (unbekannte ID 404/422 statt Fremdschlüssel: unter
              PostgreSQL 500, unter SQLite still gespeichert). Bis 1.8.70 trug FREI nur den Grund -- so blieben Aufgabe
              (project_id) sowie Schnellauftrag und Wartungsvertrag ohne Objekt (customer_id) ohne Prüfung unbemerkt;
  AUSNAHMEN   je Route und Feld, mit Grund: gehört geprüft, ist es nicht. Die Liste darf nur kürzer werden: ein Eintrag, der
              nicht mehr gefunden wird, ist rot (dann streichen); ein neuer Eintrag braucht eine Begründung im Archiv.
Eine neue ID-Eingabe, die nirgends eingeordnet ist, ist rot -- Prüfung bauen (app/zugehoerigkeit.py oder eine eigene) und in
GEPRUEFT eintragen, oder als FREI begründen.

Was der Test nicht sieht: ob die Prüfung genau DIESES Feld vergleicht (er sieht Funktion und Vergleich, nicht den Datenfluss) --
dafür die Angriffstests (tests/test_v373_zugehoerigkeit.py, tests/test_v372_befund_fremdes_objekt.py). Und IDs im Pfad allein:
die Route prüft ihren Datensatz selbst (Rollen, require_field_report_ownership())."""

import ast
import inspect
import re
import typing
from pathlib import Path

from fastapi.routing import APIRoute
from pydantic import BaseModel

from tests.test_v326_monteur_datengrenze import _routers_in_betriebsreihenfolge

APP = Path(__file__).resolve().parent.parent / "app"
SCHREIBEND = {"POST", "PUT", "PATCH", "DELETE"}
MAX_TIEFE = 6


# ---------------------------------------------------------------------------
# Einordnung
# ---------------------------------------------------------------------------

_PERSON = ("Mitarbeiter bzw. Konto des Betriebs -- gehört keinem Objekt, Auftrag oder Kunden; wer sich selbst eintragen darf, "
           "regelt die Rolle (_employee_for_request(), _time_entry_employee_for_request())")
_STAMM = "Stammsatz des Betriebs (Katalog, Einstellung, Betriebsmittel) -- gehört keinem Objekt, Auftrag oder Kunden"
_KEINE_ID = "kein Datensatz: Text (USt-IdNr., Microsoft-365-Mandant/-Anwendung)"

STAMMDATEN = {
    "employee_id": _PERSON, "employee_ids": _PERSON, "created_by_employee_id": _PERSON, "assigned_employee_id": _PERSON,
    "responsible_employee_id": _PERSON, "caseworker_employee_id": _PERSON, "project_manager_employee_id": _PERSON,
    "contact_person_employee_id": _PERSON, "default_responsible_employee_id": _PERSON, "owner_user_id": _PERSON,
    "team_id": "Kolonne -- Stammsatz der Personalplanung",
    "supplier_id": _STAMM, "catalog_id": _STAMM, "material_id": _STAMM, "service_id": _STAMM, "tax_key_id": _STAMM,
    "account_id": _STAMM, "inspection_template_id": _STAMM, "maintenance_window_id": _STAMM, "payment_term_id": _STAMM,
    "default_payment_term_id": _STAMM, "category_id": _STAMM, "pipeline_column_id": _STAMM, "function_id": _STAMM,
    "model_id": _STAMM, "default_work_time_model_id": _STAMM, "resource_id": _STAMM, "asset_id": _STAMM,
    "operational_asset_id": _STAMM, "recurring_cost_id": _STAMM, "template_id": "Checklisten-Vorlage -- " + _STAMM,
    "layer_type_id": "Schichttyp -- " + _STAMM,
    "vat_id": _KEINE_ID, "tenant_id": _KEINE_ID, "client_id": _KEINE_ID,
}

# "Erfasst von" / "geschlossen von" setzt seit 1.8.70 der Server aus der Anmeldung -- kein Schema darf sie annehmen.
VOM_SERVER = {"recorded_by_employee_id", "closed_by_employee_id"}

_MENGE = "set(ordered_ids)!=set("  # Reihenfolge: genau die vorhandenen Einträge

GEPRUEFT = {
    # --- Einsatzbericht (Befund 2a–2e, app/zugehoerigkeit.py) ---
    "POST /api/orders/{order_id}/service-reports roof_area_ids":
        ("zugehoerigkeit.require_in_order_property", "area is None or area.property_id != property_id"),
    "POST /api/service-reports/{report_id}/inspection-items roof_area_id":
        ("zugehoerigkeit.require_in_order_property", "area is None or area.property_id != property_id"),
    "POST /api/service-reports/{report_id}/inspection-items roof_component_id":
        ("zugehoerigkeit.require_in_order_property", "component.roof_area_id != roof_area_id"),
    "POST /api/service-reports/{report_id}/findings roof_component_id":
        ("zugehoerigkeit.require_in_order_property", "component.roof_area_id != roof_area_id"),
    "POST /api/service-reports/{report_id}/findings inspection_item_id":
        ("findings.create_finding", "item is None or item.service_report_id != service_report_id"),
    "POST /api/service-reports/{report_id}/materials roof_area_id":
        ("zugehoerigkeit.require_in_order_property", "area is None or area.property_id != property_id"),
    "POST /api/service-reports/{report_id}/materials inspection_item_id":
        ("service_reports.add_material", "item is None or item.service_report_id != service_report_id"),
    "POST /api/service-reports/{report_id}/materials finding_id":
        ("service_reports.add_material", "finding is None or finding.service_report_id != service_report_id"),
    "PUT /api/service-report-materials/{material_id} roof_area_id":
        ("zugehoerigkeit.require_in_order_property", "area is None or area.property_id != property_id"),
    "PUT /api/service-report-materials/{material_id} inspection_item_id":
        ("service_reports.update_material", "item is None or item.service_report_id != row.service_report_id"),
    "PUT /api/service-report-materials/{material_id} finding_id":
        ("service_reports.update_material", "finding is None or finding.service_report_id != row.service_report_id"),
    "POST /api/service-reports/{report_id}/photos inspection_item_id":
        ("service_reports.add_photo", "item is None or item.service_report_id != service_report_id"),
    "POST /api/service-reports/{report_id}/photos finding_id":
        ("service_reports.add_photo", "finding is None or finding.service_report_id != service_report_id"),
    # --- Objekt gehört zum Kunden (Befund 2f/2g: mit Bestätigung) ---
    "POST /api/quick-service-orders property_id":
        ("zugehoerigkeit.property_customer_mismatch", "prop.customer_id == customer_id"),
    "POST /api/maintenance-contracts property_id":
        ("zugehoerigkeit.property_customer_mismatch", "prop.customer_id == customer_id"),
    "PUT /api/maintenance-contracts/{contract_id} property_id":
        ("zugehoerigkeit.property_customer_mismatch", "prop.customer_id == customer_id"),
    "POST /api/projects property_id":
        ("routers.projects.create_project", "property_obj is None or property_obj.customer_id != payload.customer_id"),
    "PUT /api/projects/{project_id} property_id":
        ("routers.projects.update_project", "prop is None or prop.customer_id != payload.customer_id"),
    "POST /api/inquiries property_id":
        ("routers.inquiries._validate_inquiry_customer_property", "property_obj.customer_id != customer_id"),
    "PUT /api/inquiries/{inquiry_id} property_id":
        ("routers.inquiries._validate_inquiry_customer_property", "property_obj.customer_id != customer_id"),
    # --- Wartungsvertrag (Befund 2h: Mustervorgang) ---
    "POST /api/maintenance-contracts template_project_id":
        ("maintenance_contracts.require_template_project", "template is None or not template.is_template"),
    "PUT /api/maintenance-contracts/{contract_id} template_project_id":
        ("maintenance_contracts.require_template_project", "template is None or not template.is_template"),
    "POST /api/maintenance-contracts/{contract_id}/items template_project_id":
        ("maintenance_contracts.require_template_project", "template is None or not template.is_template"),
    "PUT /api/maintenance-contract-items/{item_id} template_project_id":
        ("maintenance_contracts.require_template_project", "template is None or not template.is_template"),
    "POST /api/maintenance-contracts/{contract_id}/items roof_area_id":
        ("maintenance_contracts.create_contract_item", "roof_area.property_id != contract.property_id"),
    "PUT /api/maintenance-contract-items/{item_id} roof_area_id":
        ("maintenance_contracts.update_contract_item", "roof_area.property_id != contract.property_id"),
    "POST /api/maintenance-contracts/{contract_id}/create-project item_id":
        ("maintenance_contracts.create_project_from_contract", "item is None or item.contract_id != contract_id"),
    # --- Rechnung (Befund 2i) und Zeitbuchung ---
    "POST /api/invoices/{invoice_id}/items source_order_item_id":
        ("invoices.add_invoice_item", "source is None or source.order_id != invoice.order_id"),
    **{f"{route} order_item_id": ("time_tracking.validate_order_item", "item is None or item.order_id != order_id") for route in (
        "POST /api/time-entries", "POST /api/time-entries/start", "PUT /api/time-entries/{entry_id}",
        "POST /api/time-entry-groups", "POST /api/time-entry-groups/start", "PUT /api/time-entry-groups/{group_id}")},
    # --- Angebot ---
    **{f"{route} section_id": ("projects._validate_section", "section is None or section.quote_id != quote_id") for route in (
        "POST /api/quotes/{quote_id}/free-items", "POST /api/quotes/{quote_id}/items",
        "PUT /api/quotes/{quote_id}/items/{item_id}/layout")},
    "POST /api/quotes/{quote_id}/sections parent_id":
        ("projects._validate_section", "section is None or section.quote_id != quote_id"),
    "PUT /api/quotes/{quote_id}/sections/{section_id} parent_id":
        ("projects._validate_section", "section is None or section.quote_id != quote_id"),
    "POST /api/quotes/{quote_id}/reorder items.section_id":
        ("projects.reorder_quote", "section_id is not None and section_id not in valid_sections"),
    "POST /api/quotes/{quote_id}/reorder sections.parent_id":
        ("projects.reorder_quote", "parent_id is not None and parent_id not in valid_sections"),
    # --- Vertrag am Auftrag ---
    "POST /api/orders/{order_id}/contract/freeze attachment_document_id":
        ("contract_versions._choose_attachment", "attachment_document_id != last.id"),
    "POST /api/orders/{order_id}/contract/sign version_id": ("contract_signatures._signable", "version.id != version_id"),
    "POST /api/orders/{order_id}/contract/sign-paper version_id": ("contract_signatures._signable", "version.id != version_id"),
    # --- Checklisten, Versand ---
    "POST /api/checklists/{checklist_id}/attachments field_id":
        ("checklists._field_of", "checklist.template_version.fields if f.id == field_id"),
    "POST /api/checklists/{checklist_id}/attachments participant_id":
        ("checklists._signer", "participant is None or participant.project_id != order.project_id"),
    "POST /api/checklists/{checklist_id}/discard-signatures signature_id":
        ("checklists.discard_signatures", "checklist.attachments if a.id == signature_id"),
    "POST /api/checklist-template-versions/{version_id}/fields/reorder field_ids":
        ("checklist_templates.reorder_fields", "set(field_ids) != set(by_id)"),
    "POST /api/email-dispatches/manual participant_ids":
        ("email_dispatch.record_manual_delivery", "any(pid not in by_id for pid in participant_ids)"),
    # --- Arbeitsvorbereitung ---
    "POST /api/work-preparation/materials/bulk-assign material_ids":
        ("routers.work_preparation.bulk_assign_work_preparation_materials", "len(prep_ids)!=1"),
    "POST /api/work-preparation/materials/bulk-assign delivery_note_id":
        ("routers.work_preparation.bulk_assign_work_preparation_materials",
         "delivery_note is None or delivery_note.preparation_id!=prep_id"),
    # --- Reihenfolgen: genau die vorhandenen Einträge ---
    "PUT /api/maintenance-windows/reorder ordered_ids": ("maintenance_contracts.reorder_windows", _MENGE + "windows_by_id.keys())"),
    "PUT /api/project-pipeline-columns/reorder ordered_ids":
        ("project_pipeline_columns.reorder_columns", _MENGE + "columns_by_id.keys())"),
    "PUT /api/task-columns/reorder ordered_ids": ("task_columns.reorder_columns", _MENGE + "columns_by_id.keys())"),
    "PUT /api/roof-component-types/reorder ordered_ids": ("roof_areas.reorder_component_types", _MENGE + "all_types.keys())"),
    "PUT /api/roof-layer-types/reorder ordered_ids": ("roof_areas.reorder_layer_types", _MENGE + "group.keys())"),
    # --- Paare im Pfad: die zweite ID gehört zur ersten ---
    "GET /api/order-acceptances/{acceptance_id}/files/{file_id} file_id":
        ("routers.acceptances.get_order_acceptance_file", "row is None or row.acceptance_id != acceptance_id"),
    "PUT /api/checklists/{checklist_id}/answers/{field_id} field_id":
        ("checklists._field_of", "checklist.template_version.fields if f.id == field_id"),
    "PUT /api/customers/{customer_id}/extra-infos/{info_id} info_id":
        ("routers.customers.update_customer_extra_info", "info is None or info.customer_id != customer_id"),
    "DELETE /api/customers/{customer_id}/extra-infos/{info_id} info_id":
        ("routers.customers.delete_customer_extra_info", "info is None or info.customer_id != customer_id"),
    "GET /api/defects/{defect_id}/files/{file_id} file_id":
        ("routers.defects.get_defect_file", "row is None or row.defect_id != defect_id"),
    "GET /api/field-view/defects/{defect_id}/photos/{file_id} file_id":
        ("defects.field_photo", "d.files if f.id == file_id"),
    "GET /api/field-view/properties/{property_id}/documents/{source}/{document_id}/view document_id":
        ("property_documents.resolve_property_document_for_field", "PropertyDocument.property_id == property_id"),
    "GET /api/field-view/properties/{property_id}/documents/{source}/{document_id}/download document_id":
        ("property_documents.resolve_property_document_for_field", "PropertyDocument.property_id == property_id"),
    "GET /api/field-view/properties/{property_id}/maintenance-history/{report_id}/pdf report_id":
        ("service_reports.resolve_property_history_report_for_field", "order.project.property_id != property_id"),
    "PUT /api/invoices/{invoice_id}/items/{item_id} item_id":
        ("routers.invoices.put_invoice_item", "invoice.items if i.id == item_id"),
    "DELETE /api/invoices/{invoice_id}/items/{item_id} item_id":
        ("invoices.remove_invoice_item", "invoice.items if i.id == item_id"),
    "PUT /api/orders/{order_id}/items/{item_id} item_id":
        ("orders.update_order_item", "item is None or item.order_id != order_id"),
    "PUT /api/orders/{order_id}/sections/{section_id} section_id":
        ("orders.update_order_section", "section is None or section.order_id != order_id"),
    "PUT /api/quotes/{quote_id}/sections/{section_id} section_id":
        ("projects._validate_section", "section is None or section.quote_id != quote_id"),
    "DELETE /api/quotes/{quote_id}/sections/{section_id} section_id":
        ("projects._validate_section", "section is None or section.quote_id != quote_id"),
    "PUT /api/quotes/{quote_id}/items/{item_id}/layout item_id":
        ("projects.set_item_layout", "item is None or item.quote_id != quote_id"),
    "POST /api/quotes/{quote_id}/items/{item_id}/duplicate item_id":
        ("routers.quotes.duplicate_item_api", "QuoteItem.quote_id == quote_id"),
    "PUT /api/quotes/{quote_id}/items/{item_id} item_id":
        ("routers.quotes.update_quote_item", "item is None or item.quote_id != quote_id"),
    "GET /api/quotes/{quote_id}/items/{item_id}/calculation item_id":
        ("routers.quotes.get_quote_item_calculation", "QuoteItem.id == item_id, QuoteItem.quote_id == quote_id"),
    "PUT /api/quotes/{quote_id}/items/{item_id}/calculation item_id":
        ("routers.quotes.update_quote_item_calculation", "QuoteItem.id == item_id, QuoteItem.quote_id == quote_id"),
    "DELETE /api/quotes/{quote_id}/items/{item_id} item_id":
        ("routers.quotes.delete_quote_item", "quote.items if x.id == item_id"),
    "DELETE /api/services/{service_id}/materials/{service_material_id} service_material_id":
        ("services.remove_material_from_service", "service.materials if m.id == service_material_id"),
    "PUT /api/tasks/{task_id}/checklist-items/{item_id} item_id":
        ("tasks.update_checklist_item", "TaskChecklistItem.task_id == task_id"),
    "DELETE /api/tasks/{task_id}/checklist-items/{item_id} item_id":
        ("tasks.delete_checklist_item", "TaskChecklistItem.task_id == task_id"),
    "DELETE /api/work-preparation/materials/{material_id}/delivery-notes/{delivery_note_id} delivery_note_id":
        ("routers.work_preparation.unlink_material_delivery_note",
         "WorkPreparationMaterialDeliveryNote.material_id==material_id"),
}

_BESITZER = "legt den Besitzer des neuen bzw. geänderten Datensatzes fest -- jeder vorhandene ist richtig"
_KONTEXT = "wählt den Auftrag als Kontext; der Monteur nur einen zugeordneten (require_field_order_access() bzw. _require_bookable_order())"
_AUFTRAG_FEHLT = 'if order is None: raise ValueError("Auftrag wurde nicht gefunden.")'

# {"METHODE /pfad feld": (Grund, Funktion mit der Existenzprüfung, Vergleich)} -- geprüft wie GEPRUEFT.
FREI = {
    "POST /api/projects customer_id": (_BESITZER, "routers.projects.create_project",
                                       "customer = db.get(Customer, payload.customer_id) if customer is None"),
    "PUT /api/projects/{project_id} customer_id": (
        _BESITZER + "; Kundenwechsel gesperrt bei festem Vertrag oder Beteiligtem (check_client_change())",
        "routers.projects.update_project", "customer = db.get(Customer, payload.customer_id) if customer is None"),
    "POST /api/properties customer_id": (_BESITZER, "routers.properties.create_property",
                                         "customer = db.get(Customer, payload.customer_id) if customer is None"),
    "POST /api/inquiries customer_id": (_BESITZER, "routers.inquiries._validate_inquiry_customer_property",
                                        "customer = db.get(Customer, customer_id) if customer is None"),
    "PUT /api/inquiries/{inquiry_id} customer_id": (
        _BESITZER + "; nach Projektanlage gegen den Kunden des Projekts gesperrt",
        "routers.inquiries._validate_inquiry_customer_property", "customer = db.get(Customer, customer_id) if customer is None"),
    "POST /api/quick-service-orders customer_id": (
        _BESITZER + " (Objekt dazu: property_id, mit Bestätigung)",
        "zugehoerigkeit.require_customer", "customer = db.get(Customer, customer_id) if customer is None"),
    "POST /api/maintenance-contracts customer_id": (
        _BESITZER + " (Objekt dazu: property_id, mit Bestätigung)",
        "zugehoerigkeit.require_customer", "customer = db.get(Customer, customer_id) if customer is None"),
    "POST /api/roof-areas property_id": (_BESITZER, "roof_areas.create_roof_area", "if db.get(Property, property_id) is None"),
    "POST /api/address-import/unassigned/{entry_id}/assign-property customer_id": (
        "legt den Kunden des neuen Objekts aus einer Importzeile ohne Kunden fest (Admin)",
        "address_import.resolve_as_property", "customer = db.get(Customer, customer_id) if customer is None"),
    "POST /api/checklists property_id": (
        "Checkliste im Kontext Objekt: jedes Objekt (Betreiberentscheidung A, app/routers/checklists.py Moduldocstring)",
        "checklists._context_snapshot", "prop = db.get(Property, property_id) if property_id else None if prop is None"),
    "POST /api/checklists order_id": (_KONTEXT, "checklists._context_snapshot",
                                      "order = db.get(Order, order_id) if order_id else None if order is None"),
    "POST /api/planning/slots order_id": ("verplant genau diesen Auftrag (Büro)", "planning.create_slot",
                                          "order = db.get(Order, order_id) if order is None"),
    "POST /api/planning/suggestion order_id": ("rechnet nur, speichert nichts", "planning.planning_suggestion",
                                               "order = load_order(db, order_id) if order is None"),
    "POST /api/time-entries order_id": (_KONTEXT, "time_tracking.create_manual_entry", _AUFTRAG_FEHLT),
    "POST /api/time-entries/start order_id": (_KONTEXT, "time_tracking.start_timer", _AUFTRAG_FEHLT),
    "PUT /api/time-entries/{entry_id} order_id": (_KONTEXT, "time_tracking.update_entry", _AUFTRAG_FEHLT),
    "POST /api/time-entry-groups order_id": (_KONTEXT, "time_tracking.create_group_manual_entry", _AUFTRAG_FEHLT),
    "POST /api/time-entry-groups/start order_id": (_KONTEXT, "time_tracking.start_group_timer", _AUFTRAG_FEHLT),
    "PUT /api/time-entry-groups/{group_id} order_id": (_KONTEXT, "time_tracking.update_group", _AUFTRAG_FEHLT),
    "POST /api/calendar-events project_id": (
        "Termin frei an jedes Projekt (Büro), nur entweder Projekt oder Angebot",
        "calendar_events._validate_referenced_entities", "project_id is not None and db.get(Project, project_id) is None"),
    "POST /api/calendar-events quote_id": (
        "Termin frei an jedes Angebot (Büro), nur entweder Projekt oder Angebot",
        "calendar_events._validate_referenced_entities", "quote_id is not None and db.get(Quote, quote_id) is None"),
    "PUT /api/calendar-events/{event_id} project_id": (
        "wie beim Anlegen", "calendar_events._validate_referenced_entities",
        "project_id is not None and db.get(Project, project_id) is None"),
    "PUT /api/calendar-events/{event_id} quote_id": (
        "wie beim Anlegen", "calendar_events._validate_referenced_entities",
        "quote_id is not None and db.get(Quote, quote_id) is None"),
    "POST /api/incoming-invoices project_id": (
        "Kosten einer Eingangsrechnung frei an jedes Projekt (Buchhaltung)", "incoming_invoices._validate_referenced_entities",
        'fields["project_id"] is not None and db.get(Project, fields["project_id"]) is None'),
    "PUT /api/incoming-invoices/{invoice_id} project_id": (
        "wie beim Anlegen", "incoming_invoices._validate_referenced_entities",
        'fields["project_id"] is not None and db.get(Project, fields["project_id"]) is None'),
    "POST /api/tasks project_id": ("Aufgabe frei an jedes Projekt (Büro); seit 1.8.71 unbekannt 404 statt Fremdschlüssel",
                                   "zugehoerigkeit.require_project", "project = db.get(Project, project_id) if project is None"),
    "PUT /api/tasks/{task_id} project_id": ("wie beim Anlegen", "zugehoerigkeit.require_project",
                                            "project = db.get(Project, project_id) if project is None"),
    "POST /api/projects/{project_id}/participants contact_id": (
        "Adressbuch des Betriebs; nicht der Auftraggeber (check_not_client())",
        "routers.project_participants.post_project_participant", "contact = db.get(Contact, payload.contact_id) if contact is None"),
    "POST /api/projects/{project_id}/participants customer_id": (
        "jeder Kunde kann Beteiligter sein, nur nicht der Auftraggeber (check_not_client())",
        "routers.project_participants.post_project_participant",
        "customer = db.get(Customer, payload.customer_id) if customer is None"),
    "POST /api/email-dispatches/manual document_id": (
        "das Dokument ist selbst Gegenstand des Eintrags", "dispatch_documents.dispatch_document",
        "row = document_row(db, document_type, document_id) if row is None"),
}

AUSNAHMEN = {
    "PUT /api/properties/{property_id} customer_id":
        "Eigentümerwechsel prüft nur die Existenz des Kunden -- Projekte, Anfragen, Verträge am Objekt zeigen danach auf ein "
        "Objekt eines anderen Kunden (Befund Nebenbefund 3; ein Wechsel kann gewollt sein, nicht entschieden)",
}
HOECHSTENS_AUSNAHMEN = 1  # darf nur kleiner werden


# ---------------------------------------------------------------------------
# Suche: ID-Eingaben der Routen
# ---------------------------------------------------------------------------

def _id_name(name: str) -> bool:
    return name.endswith("_id") or name.endswith("_ids")


def _modelle(annotation):
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
    for arg in typing.get_args(annotation):
        yield from _modelle(arg)


def _id_felder(model, prefix="", gesehen=frozenset()):
    if model in gesehen:
        return
    for name, info in model.model_fields.items():
        if _id_name(name):
            yield prefix + name
        for sub in _modelle(info.annotation):
            yield from _id_felder(sub, f"{prefix}{name}.", gesehen | {model})


def _routen():
    for router in _routers_in_betriebsreihenfolge():
        for route in router.routes:
            if isinstance(route, APIRoute):
                yield route


def id_eingaben() -> dict[str, APIRoute]:
    """{"METHODE /pfad feld": route} für jede ID-Eingabe (siehe Moduldocstring)."""
    gefunden = {}
    for route in _routen():
        felder = []
        if route.methods & SCHREIBEND:
            for param in route.dependant.body_params:
                modelle = list(_modelle(param.field_info.annotation))
                if modelle:
                    for model in modelle:
                        felder += list(_id_felder(model))
                elif _id_name(param.name):
                    felder.append(param.name)
            felder += [p.name for p in route.dependant.query_params if _id_name(p.name)]
        pfad_ids = [p.name for p in route.dependant.path_params if _id_name(p.name)]
        if len(pfad_ids) >= 2:
            felder += pfad_ids[1:]
        for methode in sorted(route.methods):
            for feld in felder:
                gefunden[f"{methode} {route.path} {feld}"] = route
    return gefunden


def _feldname(schluessel: str) -> str:
    return schluessel.rsplit(" ", 1)[1].rsplit(".", 1)[-1]


# ---------------------------------------------------------------------------
# Suche: Aufrufgraph über app/
# ---------------------------------------------------------------------------

def _funktionen() -> dict[str, ast.AST]:
    """{"modul.funktion": FunctionDef} für jede Funktion unter app/ (Modul relativ zu app/, z. B. routers.projects)."""
    index = {}
    for datei in APP.rglob("*.py"):
        modul = ".".join(datei.relative_to(APP).with_suffix("").parts)
        for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
                index.setdefault(f"{modul}.{knoten.name}", knoten)
    return index


def _aufgerufene_namen(knoten: ast.AST) -> set[str]:
    """Aufgerufene Namen -- auch eine Funktion, die als Argument weitergereicht wird (_call(reorder_fields, db, …))."""
    namen = set()
    for k in ast.walk(knoten):
        if isinstance(k, ast.Call):
            if isinstance(k.func, ast.Name):
                namen.add(k.func.id)
            elif isinstance(k.func, ast.Attribute):
                namen.add(k.func.attr)
            namen.update(a.id for a in k.args if isinstance(a, ast.Name))
    return namen


def _import_aliase() -> dict[str, set[str]]:
    """{alias: {Originalname}} aus jedem "from … import name as alias" unter app/ (update_entry as update_time_entry_row)."""
    aliase: dict[str, set[str]] = {}
    for datei in APP.rglob("*.py"):
        for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            if isinstance(knoten, ast.ImportFrom):
                for name in knoten.names:
                    if name.asname:
                        aliase.setdefault(name.asname, set()).add(name.name)
    return aliase


def erreichbar(index: dict[str, ast.AST], start: str, ziel: str, aliase: dict[str, set[str]] | None = None) -> bool:
    """Wird `ziel` von `start` aus aufgerufen (höchstens MAX_TIEFE Ebenen)? Aufrufe werden über den Funktionsnamen
    aufgelöst (auch über Import-Aliase) -- großzügig (gleichnamige Funktionen zählen alle), der Vergleich in der
    Zielfunktion ist der eigentliche Beleg."""
    aliase = aliase or {}
    nach_name: dict[str, list[str]] = {}
    for schluessel in index:
        nach_name.setdefault(schluessel.rsplit(".", 1)[1], []).append(schluessel)
    gesehen, ebene = {start}, [start]
    for _ in range(MAX_TIEFE + 1):
        if ziel in ebene:
            return True
        naechste = []
        for schluessel in ebene:
            namen = _aufgerufene_namen(index[schluessel])
            for name in namen | {o for n in namen for o in aliase.get(n, ())}:
                for kandidat in nach_name.get(name, []):
                    if kandidat not in gesehen:
                        gesehen.add(kandidat)
                        naechste.append(kandidat)
        ebene = naechste
    return False


def _ohne_leerzeichen(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _endpunkt(route: APIRoute) -> str:
    return f"{route.endpoint.__module__.removeprefix('app.')}.{route.endpoint.__name__}"


# ---------------------------------------------------------------------------
# Selbsttest der Suche
# ---------------------------------------------------------------------------

def test_selbsttest_aufrufgraph():
    quelle = '''
def endpunkt(db, payload):
    return _call(mittel_alias, db, payload.x)

def mittel(db, x):
    obj.pruefe(db, x)

def pruefe(db, x):
    if a.b != x:
        raise ValueError

def fern(db):
    pass
'''
    index = {f"m.{k.name}": k for k in ast.walk(ast.parse(quelle)) if isinstance(k, ast.FunctionDef)}
    assert erreichbar(index, "m.endpunkt", "m.pruefe", {"mittel_alias": {"mittel"}})
    assert not erreichbar(index, "m.endpunkt", "m.pruefe")  # ohne den Alias kein Weg
    assert not erreichbar(index, "m.endpunkt", "m.fern", {"mittel_alias": {"mittel"}})
    assert _ohne_leerzeichen("a.b  !=\n x") in _ohne_leerzeichen(ast.unparse(index["m.pruefe"]))


def test_selbsttest_findet_verschachtelte_und_pfad_ids():
    eingaben = id_eingaben()
    assert "POST /api/quotes/{quote_id}/reorder items.section_id" in eingaben
    assert "POST /api/service-reports/{report_id}/photos finding_id" in eingaben          # Formularfeld
    assert "POST /api/address-import/unassigned/{entry_id}/assign-property customer_id" in eingaben  # Query
    assert "PUT /api/orders/{order_id}/items/{item_id} item_id" in eingaben              # Paar im Pfad
    assert "GET /api/orders/{order_id} order_id" not in eingaben                          # eine ID im Pfad: kein Paar


# ---------------------------------------------------------------------------
# Durchlauf
# ---------------------------------------------------------------------------

def test_jede_id_eingabe_ist_eingeordnet():
    offen = sorted(k for k in id_eingaben()
                   if _feldname(k) not in STAMMDATEN and k not in GEPRUEFT and k not in FREI and k not in AUSNAHMEN)
    assert offen == [], ("ID aus der Anfrage ohne Einordnung -- Zugehörigkeitsprüfung bauen und in GEPRUEFT eintragen oder als "
                         "FREI begründen:\n" + "\n".join(offen))


def test_geprueft_wird_vom_endpunkt_erreicht_und_enthaelt_den_vergleich():
    """GEPRUEFT (Zugehörigkeit) und seit 1.8.71 FREI (Existenz): Funktion vom Endpunkt aus erreicht, Vergleich darin."""
    eingaben, index, aliase = id_eingaben(), _funktionen(), _import_aliase()
    funde = []
    pruefstellen = {**GEPRUEFT, **{k: (funktion, vergleich) for k, (_, funktion, vergleich) in FREI.items()}}
    for schluessel, (funktion, vergleich) in sorted(pruefstellen.items()):
        route = eingaben.get(schluessel)
        if route is None:
            continue  # veraltet -- test_keine_veralteten_eintraege
        if funktion not in index:
            funde.append(f"{schluessel}: Funktion {funktion} gibt es nicht")
            continue
        if _ohne_leerzeichen(vergleich) not in _ohne_leerzeichen(ast.get_source_segment(
                (APP / (funktion.rsplit(".", 1)[0].replace(".", "/") + ".py")).read_text(encoding="utf-8"), index[funktion]) or ""):
            funde.append(f"{schluessel}: in {funktion} steht der Vergleich nicht mehr: {vergleich}")
        if not erreichbar(index, _endpunkt(route), funktion, aliase):
            funde.append(f"{schluessel}: {_endpunkt(route)} ruft {funktion} nicht (mehr) auf")
    assert funde == [], "\n".join(funde)


def test_keine_veralteten_eintraege():
    eingaben = id_eingaben()
    veraltet = sorted(k for k in [*GEPRUEFT, *FREI, *AUSNAHMEN] if k not in eingaben)
    assert veraltet == [], "Eintrag ohne passende Route/Eingabe -- streichen:\n" + "\n".join(veraltet)
    doppelt = sorted(set(GEPRUEFT) & set(FREI) | set(GEPRUEFT) & set(AUSNAHMEN) | set(FREI) & set(AUSNAHMEN))
    assert doppelt == []
    assert sorted(k for k in [*GEPRUEFT, *FREI, *AUSNAHMEN] if _feldname(k) in STAMMDATEN) == []


def test_ausnahmen_werden_nur_weniger():
    assert len(AUSNAHMEN) <= HOECHSTENS_AUSNAHMEN, "Die Ausnahmeliste darf nur kürzer werden."
    assert all(grund.strip() for grund in [*(g for g, _, _ in FREI.values()), *AUSNAHMEN.values(), *STAMMDATEN.values()])


def test_erfasst_und_geschlossen_von_nimmt_kein_schema_an():
    """Seit 1.8.70 setzt der Server "erfasst von" und "geschlossen von" aus der Anmeldung -- keine Route nimmt sie an."""
    funde = sorted(k for k in id_eingaben() if _feldname(k) in VOM_SERVER)
    assert funde == [], "\n".join(funde)
    # und die Schemas lehnen den Schlüssel ausdrücklich ab (sonst ignorierte Pydantic ihn still)
    from app.schemas import FindingFollowupUpdate, InspectionItemResultUpdate

    for schema, feld in ((InspectionItemResultUpdate, "recorded_by_employee_id"), (FindingFollowupUpdate, "closed_by_employee_id")):
        try:
            schema.model_validate({feld: None})
        except ValueError:
            continue
        raise AssertionError(f"{schema.__name__} nimmt {feld} still an")


def test_stammdaten_sind_wirklich_keine_eigenen_datensaetze():
    """Gegenprobe der Einordnung nach Feldnamen: ein Feld *_id, dessen Ziel einem Objekt, Auftrag oder Kunden gehört, darf
    nicht unter STAMMDATEN stehen. Diese Ziele erkennt der Test am Fremdschlüssel der Zieltabelle auf properties, orders,
    customers, projects oder quotes."""
    from app.database import Base
    import app.models  # noqa: F401

    besitzer = {"properties", "orders", "customers", "projects", "quotes", "service_reports", "roof_areas"}
    eigene = {t.name for t in Base.metadata.sorted_tables
              if any(fk.column.table.name in besitzer for fk in t.foreign_keys) or t.name in besitzer}
    funde = []
    for t in Base.metadata.sorted_tables:
        for spalte in t.columns:
            if spalte.name in STAMMDATEN:
                for fk in spalte.foreign_keys:
                    if fk.column.table.name in eigene:
                        funde.append(f"{t.name}.{spalte.name} -> {fk.column.table.name}")
    assert funde == [], "unter STAMMDATEN, zeigt aber auf einen Datensatz mit Besitzer:\n" + "\n".join(funde)
