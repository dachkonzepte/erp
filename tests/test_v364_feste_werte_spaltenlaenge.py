"""Version 1.8.62 -- jeder feste Wert passt in seine Spalte (docs/archiv/abnahme-und-gewaehrleistung.md, "Umsetzung 1.8.62").

Unter PostgreSQL lehnt eine zu kurze String(n)-Spalte einen längeren Wert ab, SQLite nimmt ihn still an (Anlass 1.8.61: der
zuerst geplante Unterzeichner "auftraggeber_oder_beteiligter" hätte signer_mode String(20) überschritten). Bis 1.8.61 prüfte das
ein Test nur für Unterzeichner, Feldtypen und Systemfeld-Schlüssel; seit 1.8.62 ist es das Muster für jede Textspalte mit festen
Werten:

- FESTE_WERTE: Spalte -> die Konstanten im Code, aus denen ihre Werte kommen (ein neuer Wert in der Konstante wird so
  automatisch mitgeprüft). Eintrag: (Modul, Ausdruck mit "mod") oder eine Funktion.
- FESTE_LITERALE: Spalte -> Werte, die nur als Literal an Schreibstellen stehen (keine Konstante deckt alle ab), mit Fundstelle.
- VORGABEN: Spalten, die Nutzerwerte aufnehmen, deren Vorgaben aber aus dem Code kommen (beim Start angelegt).
- OHNE_FESTE_WERTE: Spalte -> warum sie keine festen Werte trägt (Freitext, MIME-Typ, Optionsgruppe …).

Jede String(n)-Spalte, deren Name nach festen Werten klingt (NAMENSMUSTER), muss eingeordnet sein -- eine neue fällt sonst hier
auf. Dazu sucht test_literale_im_code_passen per AST jedes Literal, das unter app/ in einen Modellkonstruktor, ein
update(Modell).values(...) oder einen Vergleich Modell.spalte == "…" / .in_([...]) geht, und jede String-Vorgabe der Modelle.
Ein neuer fester Wert, eine neue Konstante oder eine neue Spalte kommt in die passende Liste."""

import ast
import importlib
import inspect
import re
import textwrap
from pathlib import Path

from sqlalchemy import String

import app.models  # noqa: F401  (registriert alle Tabellen; lädt nicht app.main)
from app.database import Base

ROOT = Path(__file__).resolve().parent.parent
NAMENSMUSTER = re.compile(r"(^|_)(status|kind|type|mode|source|role|purpose|scope|result|stance|declared_by|key|value|"
                          r"category|state|level|rule|basis|unit|method|channel|action|format|provider|direction|outcome|"
                          r"reason_code|priority|code)$")


def _audit_normalize_literals():
    """Die Typen, die app/audit.py::_normalize() zurückgibt (erstes Element jedes zurückgegebenen Tupels) -- wächst mit."""
    from app import audit

    tree = ast.parse(textwrap.dedent(inspect.getsource(audit._normalize)))
    return [c.value for r in ast.walk(tree) if isinstance(r, ast.Return) and isinstance(r.value, ast.Tuple)
            for c in ast.walk(r.value.elts[0]) if isinstance(c, ast.Constant) and isinstance(c.value, str)]


def _audit_field_names():
    from sqlalchemy import inspect as sa_inspect

    from app import audit
    return [a.key for t in audit.AUDITED_TYPES for a in sa_inspect(t).column_attrs]


_SYSTEMFELDER = ("app.checklist_purposes", "[s.key for p in mod.PURPOSES.values() for s in p.system_fields]")
_BEREITSCHAFT = ("app.checklists", "[mod.READINESS_FIELD_KEY]")
_SYSTEMOPTIONEN = ("app.checklist_purposes", "[k for p in mod.PURPOSES.values() for s in p.system_fields for k, _ in s.options]")
_GRUNDLAGEN = ("app.contract_basis", "mod.CONTRACT_BASES")
_ROLLENTEXTE = ("app.project_participants", "list(mod.ROLES.values())")  # role_label() -> Beschriftung als Schnappschuss
_LAYOUT_TYPEN = ("app.document_layout", "list(mod.DOCUMENT_TYPES) + [mod.SHARED_DOCUMENT_TYPE]")
_ZEITARTEN = ("app.time_tracking", "sorted(mod.ENTRY_TYPES | mod.NON_PRODUCTIVE_ENTRY_TYPES)")
_HERKUNFT = [("app.service", "[mod.SOURCE_TYPE]"),
             ("app.services", "[mod.MANUAL_SOURCE_TYPE, mod.COPIED_SOURCE_TYPE, mod.IMPORTED_SOURCE_TYPE]")]
_MANGELWERTE = ("app.defects", "list(mod.STANCES) + list(mod.STATUSES) + list(mod.RELEASES)")

FESTE_WERTE = {
    "ai_settings.provider": [("app.ai_types", "mod.AI_PROVIDERS")],
    "app_users.role": [("app.permissions", "mod.ROLES")],
    "audit_logs.entity_type": [
        ("app.audit", "list(mod.TYPE_LABELS.values()) + [t.__name__ for t in mod.AUDITED_TYPES] + [mod.TASK_ENTITY_TYPE]"),
        _audit_normalize_literals, ("app.acceptances", "[mod.ENTITY_TYPE]"), ("app.defects", "[mod.ENTITY_TYPE]"),
        ("app.contract_versions", "[mod.CONTRACT_ENTITY_TYPE]"), ("app.email_dispatch", "[mod.DISPATCH_ENTITY_TYPE]"),
    ],
    "audit_logs.field_name": [_audit_field_names],
    "audit_logs.field_label": [("app.audit", "list(mod.FIELD_LABELS.values())")],
    "calendar_events.external_source": [("app.calendar_events", "mod.CALENDAR_EVENT_SOURCES")],
    # Checklisten: Systemfelder der Zwecke -- selbst angelegte Schlüssel begrenzt _FIELD_KEY_PATTERN auf 80
    "checklist_answer_selections.option_key": [_SYSTEMOPTIONEN],
    "checklist_answers.field_key": [_SYSTEMFELDER, _BEREITSCHAFT],
    "checklist_attachments.kind": [("app.checklists", "list(mod.ATTACHMENT_FIELD_TYPES.values())")],
    "checklist_attachments.signer_kind": [("app.checklist_templates", "mod.SIGNER_MODES")],
    "checklist_attachments.signer_role": [_ROLLENTEXTE],
    "checklist_follow_ups.follow_up_key": [("app.checklist_purposes", "[f.key for p in mod.PURPOSES.values() for f in p.follow_ups]")],
    "checklist_follow_ups.status": [("app.checklist_follow_ups", "mod.STATUS_LABELS")],
    "checklist_rule_executions.status": [("app.checklist_rules", "mod.STATUS_LABELS")],
    "checklist_template_field_options.option_key": [_SYSTEMOPTIONEN],
    "checklist_template_field_options.label": [
        ("app.checklist_purposes", "[l for p in mod.PURPOSES.values() for s in p.system_fields for _, l in s.options]")],
    "checklist_template_fields.field_key": [_SYSTEMFELDER, _BEREITSCHAFT],
    "checklist_template_fields.field_type": [("app.checklist_templates", "list(mod.FIELD_TYPES) + list(mod.SYSTEM_ONLY_FIELD_TYPES)")],
    "checklist_template_fields.signer_mode": [("app.checklist_templates", "mod.SIGNER_MODES")],
    "checklist_template_fields.label": [("app.checklist_purposes", "[s.label for p in mod.PURPOSES.values() for s in p.system_fields]")],
    "checklist_template_fields.group_name": [
        ("app.checklist_purposes", "[s.section for p in mod.PURPOSES.values() for s in p.system_fields if s.section]")],
    "checklist_template_fields.signer_label": [
        ("app.checklist_purposes", "[s.signer_label for p in mod.PURPOSES.values() for s in p.system_fields if s.signer_label]")],
    "checklist_template_rules.field_key": [_SYSTEMFELDER, _BEREITSCHAFT],
    "checklist_template_rules.operator": [("app.checklist_templates", "mod.RULE_OPERATORS")],
    "checklist_template_rules.task_priority": [("app.tasks", "mod.PRIORITIES")],
    "checklist_template_rules.assignee_mode": [("app.checklist_templates", "mod.ASSIGNEE_MODES")],
    "checklist_template_rules.min_visible_role": [("app.permissions", "mod.ROLES")],
    "checklist_template_rules.link_purpose": [("app.checklist_purposes", "mod.PURPOSES")],
    "checklist_template_versions.purpose": [("app.checklist_purposes", "mod.PURPOSES")],
    "checklist_templates.purpose": [("app.checklist_purposes", "mod.PURPOSES")],
    "checklists.context_type": [("app.checklist_templates", "mod.CONTEXT_TYPES")],
    "checklists.status": [("app.checklists", "mod.STATUS_LABELS")],
    "contacts.kind": [("app.contacts", "mod.KINDS")],
    "contract_basis_clauses.basis_key": [_GRUNDLAGEN],
    "contract_templates.basis_key": [_GRUNDLAGEN],
    "defect_events.kind": [("app.defects", "mod.EVENT_KINDS")],
    "defect_events.value": [_MANGELWERTE],
    "defect_events.previous_value": [_MANGELWERTE],
    "defect_events.declared_by": [("app.acceptances", "mod.DECLARERS")],
    "defect_events.declared_by_role": [_ROLLENTEXTE],
    "defect_files.kind": [("app.defects", "mod.FILE_KINDS")],
    "defects.source": [("app.defects", "mod.SOURCES")],
    "dispatch_authorizations.role": [("app.project_participants", "mod.ROLES")],
    "dispatch_outcomes.outcome": [("app.email_dispatch", "mod.OUTCOMES")],
    "document_email_templates.document_type": [("app.document_email_templates", "mod.DOCUMENT_TYPES")],
    "document_layout_backgrounds.document_type": [_LAYOUT_TYPEN],
    "document_layout_backgrounds.page_type": [("app.document_page_margins", "mod.PAGE_TYPES")],
    "document_layout_blocks.document_type": [_LAYOUT_TYPEN],
    "document_layout_blocks.block_type": [("app.document_frame", "mod.FRAME_BLOCK_TYPES"),
                                          ("app.document_layout", "[b[0] for b in mod.DEFAULT_SHARED_LAYOUT]")],
    "document_layout_blocks.label": [("app.document_layout", "[b[1] for b in mod.DEFAULT_SHARED_LAYOUT]")],
    "document_page_margins.document_type": [_LAYOUT_TYPEN],
    "document_page_margins.page_type": [("app.document_page_margins", "mod.PAGE_TYPES")],
    "email_dispatches.status": [("app.email_dispatch", "mod.STATUSES")],
    "email_dispatches.channel": [("app.email_dispatch", "mod.CHANNELS")],
    "email_dispatches.document_type": [("app.email_dispatch", "mod.DISPATCH_TYPES")],
    "employee_absence_requests.absence_category": [("app.absence_requests", "mod.ABSENCE_CATEGORY_LABELS")],
    "employee_absences.absence_category": [("app.absence_requests", "mod.ABSENCE_CATEGORY_LABELS")],
    "enabled_modules.module_key": [("app.modules", "mod.OPTIONAL_MODULES")],
    "findings.severity": [("app.findings", "mod.SEVERITIES")],
    "findings.action": [("app.findings", "mod.ACTIONS")],
    "findings.status": [("app.findings", "mod.STATUSES")],
    "import_batches.source_type": _HERKUNFT,
    "incoming_invoices.payment_status": [("app.incoming_invoices", "mod.PAYMENT_STATUSES")],
    "inquiries.status": [("app.routers.inquiries", "mod.INQUIRY_STATUSES")],
    "inquiries.priority": [("app.routers.inquiries", "mod.INQUIRY_PRIORITIES")],
    "inspection_items.item_type": [("app.inspection_templates", "mod.ITEM_TYPES")],
    "inspection_items.result": [("app.service_report_pdf", "mod.RESULT_LABELS")],
    "inspection_template_items.item_type": [("app.inspection_templates", "mod.ITEM_TYPES")],
    "invoices.invoice_type": [("app.invoices", "mod.INVOICE_TYPES")],
    "maintenance_contracts.status": [("app.maintenance_contracts", "mod.STATUSES")],
    "notice_letters.kind": [("app.notice_letters", "mod.LETTER_KINDS")],
    "checklist_versions.kind": [("app.checklist_versions", "mod.VERSION_KINDS")],  # seit 1.8.66
    "notice_reservations.letter_kind": [("app.notice_reservations", "mod.RESERVATION_LETTER_KINDS")],
    "notice_reservations.basis_group": [("app.notice_reservations", "mod.BASIS_GROUPS")],
    "number_sequences.sequence_key": [("app.settings", "mod.DEFAULT_SEQUENCES")],
    "order_acceptance_files.kind": [("app.acceptances", "mod.FILE_KINDS")],
    "order_acceptances.kind": [("app.acceptances", "mod.KINDS")],
    "order_acceptances.scope": [("app.acceptances", "mod.SCOPES")],
    "order_acceptances.result": [("app.acceptances", "mod.RESULTS")],
    "order_acceptances.declared_by": [("app.acceptances", "mod.DECLARERS")],
    "order_acceptances.declared_by_role": [_ROLLENTEXTE],
    "order_contract_basis_changes.old_basis": [_GRUNDLAGEN],
    "order_contract_basis_changes.new_basis": [_GRUNDLAGEN],
    "order_contract_signatures.method": [("app.contract_signatures", "mod.METHODS")],
    "order_contract_versions.basis_key": [_GRUNDLAGEN],
    "order_warranty_changes.work_kind": [("app.warranty", "mod.WORK_KINDS")],
    "order_warranty_changes.contract_basis": [_GRUNDLAGEN],
    "orders.contract_basis": [_GRUNDLAGEN],
    "orders.work_kind": [("app.warranty", "mod.WORK_KINDS")],
    "planning_region_settings.federal_state_code": [("app.planning", "mod.GERMAN_STATES")],
    "planning_school_holiday_sync.state_code": [("app.planning", "mod.GERMAN_STATES")],
    "planning_school_holidays.state_code": [("app.planning", "mod.GERMAN_STATES")],
    "project_participants.role": [("app.project_participants", "mod.ROLES")],
    "quote_document_meta.contract_basis": [_GRUNDLAGEN],
    "recurring_costs.billing_interval": [("app.recurring_costs", "mod.BILLING_INTERVALS")],
    "recurring_costs.overhead_classification": [("app.recurring_costs", "mod.OVERHEAD_CLASSIFICATIONS")],
    "roof_layer_types.option_group": [("app.option_settings", "mod.DEFAULT_OPTION_GROUPS")],
    "sent_documents.document_type": [("app.sent_documents", "mod.DOCUMENT_TYPES")],
    "service_reports.report_type": [("app.service_reports", "mod.REPORT_TYPES")],
    "services.source_type": _HERKUNFT,
    "setting_option_groups.group_key": [("app.option_settings", "mod.DEFAULT_OPTION_GROUPS")],
    "smtp_settings.send_method": [("app.email_sending", "mod.SEND_METHODS")],
    "smtp_settings.encryption": [("app.email_sending", "mod.ENCRYPTION_MODES")],
    "tasks.priority": [("app.tasks", "mod.PRIORITIES")],
    "tasks.min_visible_role": [("app.permissions", "mod.ROLES")],
    "tasks.source_module": [("app.tasks", "mod.TASK_MAIL_KINDS"), ("app.checklist_rules", "[mod.SOURCE_MODULE]"),
                            ("app.defects", "[mod.TASK_SOURCE]")],
    "time_entries.entry_type": [_ZEITARTEN],  # dazu Werte der Optionsgruppe time_entry_types
    "time_entry_groups.entry_type": [_ZEITARTEN],
    "user_dashboard_widgets.widget_key": [("app.dashboard", "[w['widget_key'] for w in mod.DEFAULT_WIDGETS]")],
}

# Werte nur als Literal an Schreibstellen (Fundstelle Stand 1.8.62) -- bei einem neuen Wert hier ergänzen. Die AST-Suche unten
# findet zusätzlich jedes Literal in Konstruktoren, update().values() und Vergleichen; Zuweisungen obj.spalte = "…" nicht.
FESTE_LITERALE = {
    "ai_call_log.caller": ("einstellungen_test",),  # routers/ai_settings.py
    "audit_logs.action": ("angelegt", "geändert", "gelöscht", "verworfen"),  # audit.py, record_audit_entry(action=…)
    # Rückgabe der Folge-Handler (obstruction/concern_notices.py; "abnahme" seit 1.8.63, checklist_purposes.py)
    "checklist_follow_ups.target_type": ("task", "abnahme"),
    "checklist_template_versions.status": ("entwurf", "veroeffentlicht", "abgeloest"),  # checklist_templates.py
    "document_layout_blocks.font_weight": ("normal", "bold"),  # schemas.py (pattern)
    "document_layout_blocks.text_align": ("left", "center", "right"),  # schemas.py (pattern)
    "employee_absence_requests.status": ("pending", "approved", "rejected", "cancelled"),  # absence_requests.py
    "employee_compensation_settings.compensation_type": ("hourly", "fixed_salary"),  # schemas.py, employees.py
    "employee_cost_allocation_settings.allocation_type": ("labor_rate", "variable_overhead", "excluded"),  # employees.py
    "employee_functions.employee_group": ("gewerblich", "kaufmaennisch"),  # schemas.py (Validator)
    "employees.employee_group": ("gewerblich", "kaufmaennisch"),
    "import_runs.status": ("completed", "reverted"),  # address_import.py
    "imported_addresses.status": ("previewing", "confirmed"),
    "imported_addresses.classification": ("customer", "supplier", "unassigned", "duplicate"),
    "imported_addresses.resolution": ("created_as_customer", "assigned_as_property", "discarded"),
    "invoice_items.unit": ("pschl.", "Std."),  # invoices.py; sonst Einheit aus Auftragsposition/Material
    "invoices.status": ("entwurf", "versendet", "bezahlt", "storniert"),  # invoices.py
    "invoices.rounding_rule": ("half_up",),
    "labor_rate_overhead_settings.fixed_overhead_mode": ("eur", "pct"),
    "labor_rate_overhead_settings.variable_overhead_mode": ("eur", "pct"),
    "materials.source": ("imported", "manual"),
    "order_contract_versions.attachment_kind": ("versendet", "aktuell"),
    "order_contracts.status": ("entwurf", "festgeschrieben", "unterschrieben"),
    "order_items.position_type": ("normal",),  # sonst vom Client, Schema max_length=30
    "order_revisions.source": ("manual", "quote", "quote_sync", "migration"),
    "orders.status": ("beauftragt", "storniert", "abgeschlossen"),  # sonst vom Client, Schema max_length=50
    "planning_school_holidays.source": ("ferien-api.de",),
    "planning_slots.status": ("geplant",),  # sonst vom Client, Schema max_length=40
    "projects.status": ("anfrage", "angebot", "beauftragt"),  # sonst vom Client, Schema max_length=50
    "quote_items.position_type": ("normal",),
    "quotes.status": ("entwurf", "beauftragt"),  # sonst vom Client, Schema max_length=50
    "quotes.source_format": ("manual",),
    "reminders.status": ("entwurf", "versendet"),
    "service_report_photos.kind": ("vorher", "nachher", "allgemein"),
    "service_reports.status": ("entwurf", "unterschrieben"),
    "services.time_unit": ("min/unit",),
    "time_entries.source": ("manual", "timer", "group_manual", "group_timer"),
    "time_entries.status": ("booked", "running"),
    "time_entry_groups.mode": ("manual", "timer"),
    "time_entry_groups.status": ("booked", "running"),
    "time_tracking_settings.datev_target": ("lohn_gehalt", "lodas"),
    "work_preparation_materials.status": ("bedarf",),  # sonst vom Client, max_length=40
    "work_preparation_tasks.status": ("offen", "erledigt"),
    "work_preparation_tasks.priority": ("normal",),
    "work_preparations.status": ("offen",),  # sonst vom Client, Schema max_length=50
    "inquiries.source": ("sonstiges",),  # sonst vom Client, Schema max_length=80
}

_OPT = "[o[2] for o in mod.DEFAULT_OPTION_GROUPS[{!r}]['options']]".format
VORGABEN = {  # Nutzerwerte, aber die Vorgaben beim Start kommen aus dem Code
    "document_categories.key": [("app.document_categories", "[c[1] for c in mod.DEFAULT_CATEGORIES]")],
    "customer_documents.category": [("app.document_categories", "[c[1] for c in mod.DEFAULT_CATEGORIES] + [mod.FALLBACK_CATEGORY_KEY]")],
    "project_documents.category": [("app.document_categories", "[c[1] for c in mod.DEFAULT_CATEGORIES] + [mod.FALLBACK_CATEGORY_KEY]")],
    "project_pipeline_columns.key": [("app.project_pipeline_columns", "[c['key'] for c in mod.DEFAULT_COLUMNS]")],
    "task_columns.key": [("app.task_columns", "[c['key'] for c in mod.DEFAULT_COLUMNS]")],
    "tasks.status": [("app.task_columns", "[c['key'] for c in mod.DEFAULT_COLUMNS]")],
    "customer_profiles.category": [("app.option_settings", _OPT("customer_categories"))],
    "project_profiles.category": [("app.option_settings", _OPT("project_categories"))],
    "operational_resources.resource_type": [("app.option_settings", _OPT("resource_types"))],
    "operational_assets.asset_type": [("app.option_settings", _OPT("resource_types"))],
    "work_preparation_team_resources.resource_type_snapshot": [("app.option_settings", _OPT("resource_types"))],
    "operational_asset_inspections.inspection_type": [("app.option_settings", _OPT("operational_asset_inspection_types"))],
    "operational_asset_documents.document_type": [("app.option_settings", _OPT("operational_asset_document_types"))],
    "recurring_costs.category": [("app.option_settings", _OPT("recurring_cost_categories"))],
    "recurring_cost_documents.document_type": [("app.option_settings", _OPT("recurring_cost_document_types"))],
    "services.service_type": [("app.option_settings", _OPT("service_types"))],
    "employee_absences.absence_type": [("app.option_settings", _OPT("absence_types"))],
    "employee_absence_requests.absence_type": [("app.option_settings", _OPT("absence_types"))],
    "time_entries.activity": [("app.option_settings", _OPT("time_entry_activities"))],
    "time_entry_groups.activity": [("app.option_settings", _OPT("time_entry_activities"))],
    "roof_areas.roof_type": [("app.option_settings", _OPT("roof_types"))],
    "roof_layer_types.roof_type": [("app.option_settings", _OPT("roof_types"))],
    "inspection_templates.roof_type": [("app.option_settings", _OPT("roof_types"))],
    "roof_type_inspection_template_defaults.roof_type": [("app.option_settings", _OPT("roof_types"))],
    "quote_items.unit": [("app.option_settings", _OPT("units"))],
    "roof_components.unit": [("app.option_settings", _OPT("units"))],
}

OHNE_FESTE_WERTE = {
    "ai_call_log.error_type": "Klassenname einer Ausnahme",
    "audit_logs.request_method": "HTTP-Methode der Anfrage",
    "checklist_attachments.signer_poa_content_type": "MIME-Typ",
    "checklist_template_fields.unit": "Freitext (Einheit eines Zahlenfelds)",
    "contacts.postal_code": "Postleitzahl",
    "customer_documents.category": "Dokumentkategorie aus den Einstellungen",
    "customer_documents.content_type": "MIME-Typ",
    "customer_extra_infos.info_type": "Freitext (Schema max_length=30)",
    "customer_profiles.category": "Optionsgruppe customer_categories",
    "customers.postal_code": "Postleitzahl",
    "defect_files.content_type": "MIME-Typ",
    "document_categories.key": "Schlüssel aus den Einstellungen",
    "email_dispatches.dispatch_key": "Schlüssel von der Oberfläche (8-80 Zeichen geprüft)",
    "email_dispatches.error_code": "Fehlercode des Mailservers",
    "email_dispatches.lock_key": "zusammengesetzt aus Dokumentart und Kennung",
    "employee_absence_requests.absence_type": "Optionsgruppe absence_types",
    "employee_absences.absence_type": "Optionsgruppe absence_types",
    "employee_profiles.postal_code": "Postleitzahl",
    "general_settings.postal_code": "Postleitzahl",
    "imported_addresses.postal_code": "Postleitzahl",
    "inspection_items.unit": "Freitext-Einheit (aus der Prüfvorlage)",
    "inspection_template_items.component_type": "Bauteilart aus den Einstellungen",
    "inspection_template_items.unit": "Freitext-Einheit",
    "inspection_templates.roof_type": "Optionsgruppe roof_types",
    "material_calculation_overrides.article_number_key": "Artikelnummer",
    "materials.unit": "Einheit (Import, Optionsgruppe units oder Freitext)",
    "operational_asset_documents.document_type": "Optionsgruppe operational_asset_document_types",
    "operational_asset_inspections.inspection_type": "Optionsgruppe operational_asset_inspection_types",
    "operational_assets.asset_type": "Optionsgruppe resource_types",
    "operational_resources.resource_type": "Optionsgruppe resource_types",
    "order_acceptance_files.content_type": "MIME-Typ",
    "order_item_material_snapshots.unit": "Einheit (Kopie aus dem Material)",
    "order_items.unit": "Einheit (Kopie aus der Angebotsposition)",
    "outlook_calendar_sync_state.last_error_type": "Klassenname einer Ausnahme",
    "outlook_series_occurrences.occurrence_type": "Wert aus Microsoft Graph",
    "project_documents.category": "Dokumentkategorie aus den Einstellungen",
    "project_documents.content_type": "MIME-Typ",
    "project_participants.acceptance_poa_content_type": "MIME-Typ",
    "project_participants.poa_content_type": "MIME-Typ",
    "project_pipeline_columns.key": "aus der Beschriftung erzeugt (Einstellungen)",
    "project_profiles.category": "Optionsgruppe project_categories",
    "properties.postal_code": "Postleitzahl",
    "property_documents.content_type": "MIME-Typ",
    "quote_item_material_calculations.unit": "Einheit (Kopie aus dem Material)",
    "quote_items.unit": "Einheit (Optionsgruppe units, Leistung oder Freitext)",
    "recurring_cost_documents.document_type": "Optionsgruppe recurring_cost_document_types",
    "recurring_costs.category": "Optionsgruppe recurring_cost_categories",
    "roof_areas.roof_type": "Optionsgruppe roof_types",
    "roof_component_types.key": "Schlüssel aus den Einstellungen",
    "roof_components.component_type": "Bauteilart aus den Einstellungen",
    "roof_components.unit": "Freitext-Einheit",
    "roof_layer_types.key": "Schlüssel aus den Einstellungen",
    "roof_layer_types.roof_type": "Optionsgruppe roof_types",
    "roof_type_inspection_template_defaults.roof_type": "Optionsgruppe roof_types",
    "sent_documents.content_type": "MIME-Typ",
    "service_materials.unit": "Einheit (Kopie aus dem Material)",
    "service_report_materials.unit": "Freitext-Einheit",
    "services.activity_code": "Wert aus dem Import",
    "services.service_type": "Optionsgruppe service_types",
    "services.unit": "Einheit (Import oder Freitext)",
    "suppliers.postal_code": "Postleitzahl",
    "task_columns.key": "aus der Beschriftung erzeugt (Einstellungen)",
    "tasks.status": "Spaltenschlüssel aus den Einstellungen",
    "team_employees.role": "Freitext (Rolle im Team)",
    "team_resources.role": "Freitext (Rolle im Team)",
    "work_preparation_employees.role": "Freitext",
    "work_preparation_materials.unit": "Einheit (Kopie aus dem Material oder Freitext)",
    "work_time_models.code": "Freitext-Kürzel",
    # außerhalb des Namensmusters, wegen ihrer Vorgaben eingeordnet
    "time_entries.activity": "Optionsgruppe time_entry_activities",
    "time_entry_groups.activity": "Optionsgruppe time_entry_activities",
    "work_preparation_team_resources.resource_type_snapshot": "Kopie aus operational_resources.resource_type",
}


def _columns() -> dict:
    return {f"{t.name}.{c.name}": c for t in Base.metadata.tables.values() for c in t.columns}


def _values(spec) -> list:
    if callable(spec):
        values = spec()
    else:
        module, expression = spec
        values = eval(expression, {"mod": importlib.import_module(module)})  # noqa: S307 -- feste Ausdrücke dieser Datei
    return list(values.keys() if isinstance(values, dict) else values)


def _alle_werte() -> dict[str, list]:
    werte = {}
    for name, specs in [*FESTE_WERTE.items(), *VORGABEN.items()]:
        for spec in specs:
            got = _values(spec)
            assert got, f"{name}: {spec} liefert keine Werte"
            werte.setdefault(name, []).extend(got)
    for name, literale in FESTE_LITERALE.items():
        werte.setdefault(name, []).extend(literale)
    return werte


def test_fixed_values_fit_their_columns():
    columns = _columns()
    zu_lang = []
    for name, values in _alle_werte().items():
        column = columns[name]
        for value in values:
            assert isinstance(value, str), (name, value)
            if len(value) > column.type.length:
                zu_lang.append(f"{name} (String({column.type.length})): {value!r} ({len(value)} Zeichen)")
    assert zu_lang == []


def test_every_candidate_column_is_classified_and_lists_are_consistent():
    columns = _columns()
    eingeordnet = set(FESTE_WERTE) | set(FESTE_LITERALE) | set(OHNE_FESTE_WERTE)
    kandidaten = {name for name, c in columns.items() if isinstance(c.type, String) and c.type.length
                  and NAMENSMUSTER.search(c.name)}
    assert sorted(kandidaten - eingeordnet) == []  # neue Spalte: in FESTE_WERTE, FESTE_LITERALE oder OHNE_FESTE_WERTE
    alle = eingeordnet | set(VORGABEN)
    assert sorted(n for n in alle if n not in columns or not isinstance(columns[n].type, String)
                  or not columns[n].type.length) == []  # nur echte String(n)-Spalten, keine veralteten Einträge
    assert set(FESTE_WERTE) & set(FESTE_LITERALE) == set()
    assert (set(FESTE_WERTE) | set(FESTE_LITERALE)) & set(OHNE_FESTE_WERTE) == set()
    assert set(VORGABEN) <= set(OHNE_FESTE_WERTE)  # Vorgaben: die Spalte nimmt daneben Nutzerwerte auf


def _model_columns() -> dict[str, dict]:
    """Klassenname -> {Attributname: Spalte} aller gemappten Modelle."""
    return {m.class_.__name__: {key: col for key, col in m.columns.items()} for m in Base.registry.mappers}


def _root_model(node) -> str | None:
    """update(Modell).where(...).values(...): den Klassennamen aus update(...) am Anfang der Kette."""
    while isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "update" and node.args \
                and isinstance(node.args[0], ast.Name):
            return node.args[0].id
        node = node.func.value if isinstance(node.func, ast.Attribute) else None
    return None


def _string_constants(node) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def test_literals_in_the_code_fit_their_columns():
    """Jedes Literal, das unter app/ in eine Spalte geht: Modell(spalte="…"), update(Modell).values(spalte="…"),
    Modell.spalte == "…" bzw. != und .in_([...]). Zuweisungen an Objekte (obj.spalte = "…") kennt die Suche nicht -- dafür
    FESTE_LITERALE."""
    models = _model_columns()
    zu_lang, gefunden = [], 0

    def check(model: str, attr: str, values: list[str], where: str):
        nonlocal gefunden
        column = models.get(model, {}).get(attr)
        if column is None or not isinstance(column.type, String) or not column.type.length:
            return
        for value in values:
            gefunden += 1
            if len(value) > column.type.length:
                zu_lang.append(f"{where}: {model}.{attr} (String({column.type.length})) {value!r}")

    for path in sorted((ROOT / "app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                model = node.func.id if isinstance(node.func, ast.Name) and node.func.id in models else None
                if model is None and isinstance(node.func, ast.Attribute) and node.func.attr == "values":
                    model = _root_model(node.func.value)
                for kw in node.keywords if model else ():
                    if kw.arg:
                        check(model, kw.arg, _string_constants(kw.value), f"{rel}:{node.lineno}")
                if isinstance(node.func, ast.Attribute) and node.func.attr == "in_" and node.args \
                        and isinstance(node.func.value, ast.Attribute) and isinstance(node.func.value.value, ast.Name):
                    check(node.func.value.value.id, node.func.value.attr, _string_constants(node.args[0]),
                          f"{rel}:{node.lineno}")
            elif isinstance(node, ast.Compare) and isinstance(node.left, ast.Attribute) \
                    and isinstance(node.left.value, ast.Name):
                for op, right in zip(node.ops, node.comparators):
                    if isinstance(op, (ast.Eq, ast.NotEq)):
                        check(node.left.value.id, node.left.attr, _string_constants(right), f"{rel}:{node.lineno}")
    assert gefunden > 100  # die Suche greift (Stand 1.8.62: 136 Literale)
    assert zu_lang == []


def test_model_string_defaults_fit_their_columns():
    zu_lang = []
    for name, column in _columns().items():
        if not isinstance(column.type, String) or not column.type.length:
            continue
        for default in (column.default, column.server_default):
            value = getattr(default, "arg", None)
            value = getattr(value, "text", value)  # server_default: TextClause
            if isinstance(value, str) and len(value.strip("'")) > column.type.length:
                zu_lang.append(f"{name}: {value!r}")
    assert zu_lang == []
