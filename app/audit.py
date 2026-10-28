import contextvars
import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from .models import (
    AuditLog, Customer, CustomerProfile, CustomerExtraInfo, Property, Inquiry,
    Project, ProjectProfile, ProjectDocument, Supplier, OperationalResource, Team, TeamEmployee, TeamResource, Quote, QuoteItem, QuoteItemCalculation,
    QuoteItemMaterialCalculation, QuoteDocumentMeta, QuoteSection, QuoteItemLayout,
    QuoteEmployeeAssignment, Order, OrderRevision, OrderSection, OrderItem, WorkPreparation, WorkPreparationEmployee, WorkPreparationTask, WorkPreparationMaterial, WorkPreparationTeamAssignment, WorkPreparationTeamEmployee, WorkPreparationTeamResource, WorkPreparationMaterialSupplier, WorkPreparationDeliveryNote, WorkPreparationMaterialDeliveryNote, PlanningSlot, PlanningSettings, PlanningRegionSettings, PlanningHoliday, EmployeeAbsence, EmployeeAbsenceRequest, PlanningSlotCapacity, TimeEntry, TimeEntryGroup, TimeEntryGroupMember, TimeTrackingSettings, EmployeePayrollSettings, TimeBackofficeAdvancedSettings, WorkTimeModel, WorkTimeBreakRule, EmployeeWorkTimeModel, Employee, EmployeeCompensationSettings, EmployeeCostAllocationSettings, EmployeeProfile, EmployeeRoleSettings, EmployeePlanningSettings,
    EmployeeFunction, GeneralSettings, CalculationSettings, LaborRateSettings, LaborRateOverheadSettings,
    NumberSequence, SettingOptionGroup, SettingOption, AppUser, ServiceCalculation, MaterialCalculationOverride,
    Checklist, ChecklistAttachment, ChecklistAssetRelease, OperationalAsset, Contact, ProjectParticipant,
    OrderAcceptance, Defect, DefectEvent, Invoice, Payment, PaymentAllocation,
    InvoiceCharge, InvoiceDefaultStart, OrderCustomerChange, BaseInterestRate, DunningLegalText,
    OrderStatusChange, InvoiceItem, Reminder, ServiceReport, MaintenanceContract, RoofArea, CalendarEvent,
)

_actor_id = contextvars.ContextVar("audit_actor_id", default=None)
_actor_name = contextvars.ContextVar("audit_actor_name", default="System")
_request_path = contextvars.ContextVar("audit_request_path", default=None)
_request_method = contextvars.ContextVar("audit_request_method", default=None)

# sealed_content (Checklisten-Unterschrift seit 1.8.14, Checklisten-Abschluss seit 1.8.15): die
# versiegelte Kopie steht an der Unterschrift bzw. Checkliste selbst; die Historie trägt ihre
# Prüfsumme (content_sha256), nicht noch eine Kopie.
EXCLUDED_FIELDS = {"created_at", "updated_at", "last_login_at", "password_hash", "sealed_content"}
TYPE_LABELS = {
    Customer: "Kunde", Property: "Objekt", Project: "Projekt", ProjectDocument: "Projektdatei",
    Quote: "Angebot", QuoteItem: "Angebotsposition", QuoteItemCalculation: "Positionskalkulation",
    QuoteItemMaterialCalculation: "Materialkalkulation", QuoteDocumentMeta: "Angebotskopf",
    QuoteSection: "LV-Titel", Order: "Auftrag", OrderRevision: "Auftragsrevision", OrderSection: "Auftrags-LV-Titel", OrderItem: "Auftragsposition", WorkPreparation: "Arbeitsvorbereitung", WorkPreparationEmployee: "AV-Mitarbeiter", WorkPreparationTask: "AV-Aufgabe", WorkPreparationMaterial: "AV-Material", WorkPreparationTeamAssignment:"AV-Team", WorkPreparationDeliveryNote:"AV-Lieferschein", WorkPreparationMaterialDeliveryNote:"Material-Lieferschein-Zuordnung", PlanningSlot:"Plantafel-Einsatz", PlanningSettings:"Plantafel-Einstellung", PlanningRegionSettings:"Plantafel-Region", PlanningHoliday:"Feiertag / betriebsfreier Tag", EmployeeAbsence:"Mitarbeiter-Abwesenheit", EmployeeAbsenceRequest:"Abwesenheitsantrag", PlanningSlotCapacity:"Plantafel-Kapazität", TimeEntry:"Zeitbuchung", TimeEntryGroup:"Gruppen-Zeitbuchung", TimeEntryGroupMember:"Gruppenbuchungs-Mitglied", TimeTrackingSettings:"Zeiterfassungs-Einstellung", EmployeePayrollSettings:"DATEV-Mitarbeitereinstellung", TimeBackofficeAdvancedSettings:"Zeiterfassungs-Backoffice-Einstellung", WorkTimeModel:"Arbeitszeitmodell", WorkTimeBreakRule:"Arbeitszeitmodell-Pausenregel", EmployeeWorkTimeModel:"Mitarbeiter-Arbeitszeitmodell", Supplier:"Lieferant", OperationalResource:"Ressource", Team:"Kolonne / Team", Employee: "Mitarbeiter", EmployeeFunction: "Mitarbeiterfunktion",
    GeneralSettings: "Unternehmenseinstellung", CalculationSettings: "Kalkulationsgrundlage",
    LaborRateSettings: "Verrechnungssatz-Grundlage", LaborRateOverheadSettings: "Gemeinkosten-Grundlage",
    EmployeeCostAllocationSettings: "Mitarbeiter-Kostenzuordnung", NumberSequence: "Nummernkreis",
    SettingOption: "Auswahllistenwert", AppUser: "ERP-Benutzer", Inquiry: "Anfrage",
    ServiceCalculation: "Katalogleistung-Kalkulation", MaterialCalculationOverride: "Katalog-Materialkalkulation",
    Checklist: "Checkliste", ChecklistAssetRelease: "Gerät als repariert markiert",
    Contact: "Kontakt (Adressbuch)", ProjectParticipant: "Projektbeteiligter",
    OrderAcceptance: "Abnahme", Defect: "Mangel", DefectEvent: "Mangel",
    Payment: "Zahlungseingang", PaymentAllocation: "Zahlungseingang",
    InvoiceCharge: "Nebenforderung", InvoiceDefaultStart: "Verzugsbeginn", OrderCustomerChange: "Auftrag",
    BaseInterestRate: "Basiszinssatz", DunningLegalText: "Rechtstext Mahnwesen",
    # seit 1.8.138 jede protokollierte Art (bis dahin stand für diese 16 der Klassenname in der Historie); die Erweiterungs-
    # tabellen fasst _normalize() ohnehin unter ihrem Hauptdatensatz zusammen
    CustomerProfile: "Kunde", CustomerExtraInfo: "Kundenwissen", ProjectProfile: "Projekt", TeamEmployee: "Teammitglied",
    TeamResource: "Team-Ressource", QuoteItemLayout: "Angebotsposition", QuoteEmployeeAssignment: "Angebot – Mitarbeiter",
    WorkPreparationTeamEmployee: "AV-Teammitglied", WorkPreparationTeamResource: "AV-Team-Ressource",
    WorkPreparationMaterialSupplier: "AV-Materiallieferant", EmployeeCompensationSettings: "Mitarbeiter",
    EmployeeProfile: "Mitarbeiter", EmployeeRoleSettings: "Mitarbeiter", EmployeePlanningSettings: "Mitarbeiter",
    SettingOptionGroup: "Auswahlliste", ChecklistAttachment: "Checklisten-Unterschrift",
    # seit 1.9.115 (Stufe 5, R1, Punkt 5)
    Invoice: "Rechnung", InvoiceItem: "Rechnungsposition", Reminder: "Mahnung", ServiceReport: "Einsatzbericht",
    MaintenanceContract: "Wartungsvertrag", RoofArea: "Dachfläche", CalendarEvent: "Termin",
    OrderStatusChange: "Auftragsstatus",  # seit 1.9.124
}

EXTENSION_TYPES = (CustomerProfile, ProjectProfile, EmployeeProfile, EmployeeRoleSettings, EmployeeCompensationSettings, EmployeeCostAllocationSettings, QuoteDocumentMeta, QuoteItemLayout, QuoteEmployeeAssignment)

AUDITED_TYPES = (
    Customer, CustomerProfile, CustomerExtraInfo, Property, Inquiry, Project, ProjectProfile, ProjectDocument, Supplier, OperationalResource, Team, TeamEmployee, TeamResource,
    Quote, QuoteItem, QuoteItemCalculation, QuoteItemMaterialCalculation, QuoteDocumentMeta, QuoteSection,
    QuoteItemLayout, QuoteEmployeeAssignment, Order, OrderRevision, WorkPreparation, WorkPreparationEmployee, WorkPreparationTask, WorkPreparationMaterial, WorkPreparationTeamAssignment, WorkPreparationTeamEmployee, WorkPreparationTeamResource, WorkPreparationMaterialSupplier, WorkPreparationDeliveryNote, WorkPreparationMaterialDeliveryNote, PlanningSlot, PlanningSettings, PlanningRegionSettings, PlanningHoliday, EmployeeAbsence, EmployeeAbsenceRequest, PlanningSlotCapacity, TimeEntry, TimeEntryGroup, TimeEntryGroupMember, TimeTrackingSettings, EmployeePayrollSettings, TimeBackofficeAdvancedSettings, WorkTimeModel, WorkTimeBreakRule, EmployeeWorkTimeModel, Employee, EmployeeCompensationSettings, EmployeeCostAllocationSettings, EmployeeProfile, EmployeeRoleSettings, EmployeePlanningSettings, EmployeeFunction,
    GeneralSettings, CalculationSettings, LaborRateSettings, LaborRateOverheadSettings, NumberSequence, SettingOptionGroup, SettingOption,
    AppUser, ServiceCalculation, MaterialCalculationOverride,
    # Checklisten (seit 1.8.13): Anlegen, Abschließen, Löschen eines Entwurfs; jedes Foto und jede
    # Unterschrift samt Verwerfen; "als repariert markieren". Antworten bewusst NICHT -- sie
    # speichern beim Tippen (eine Zeile je 700-ms-Pause), verbindlich wird der Inhalt erst mit der
    # Unterschrift, und die bindet ihn per Prüfsumme.
    Checklist, ChecklistAttachment, ChecklistAssetRelease,
    # Adressbuch und Beteiligte am Projekt (seit 1.8.37); Beteiligte erscheinen in der Historie der Projektmappe.
    Contact, ProjectParticipant,
    # Abnahme (seit 1.8.46): das Anlegen mit dem ganzen Inhalt; das Verwerfen läuft als bedingtes UPDATE an der
    # ORM-Sperre vorbei und schreibt seine Zeile selbst (app/acceptances.py::discard_acceptance()).
    OrderAcceptance,
    # Mangel (seit 1.8.49): Anlegen mit dem ganzen Inhalt und jeder Eintrag im Verlauf (Haltung, Status, Freigabe,
    # Fotos) unter der Kennung des Mangels; das Verwerfen schreibt seine Zeile selbst (app/defects.py::discard_defect()).
    Defect, DefectEvent,
    # Zahlungseingang (seit 1.8.78): jede Zahlung, Zuordnung, jeder Abzug und jede Gegenbuchung unter der Kennung der Zahlung;
    # Zuordnungen erscheinen auch in der Historie der Projektmappe. Geändert oder gelöscht wird nichts (ORM-Sperre).
    Payment, PaymentAllocation,
    # Seit 1.8.80 (Zahlungsstufe Z2b): Nebenforderungen und ihre Gegenbuchung, Verzugsbeginn (bestätigt, verworfen), Kundenwechsel
    # am Auftrag mit Begründung (unter der Kennung des Auftrags). Geändert oder gelöscht wird nichts (ORM-Sperre).
    InvoiceCharge, InvoiceDefaultStart, OrderCustomerChange,
    # Seit 1.8.81 (Z2b Punkte 7 und 9): Basiszinssatz je Halbjahr und Rechtstexte -- jede Änderung samt Prüfangabe.
    BaseInterestRate, DunningLegalText,
    # Seit 1.9.115 (Stufe 5, R1, Punkt 5, Befund F13): Auftragspositionen und LV-Titel des Auftrags, Rechnungen mit Positionen und Statuswechseln,
    # Mahnungen, Einsatzberichte, Wartungsverträge, Dachflächen, Termine -- bis 1.9.114 gar nicht, obwohl die Karte „Auftragsstände“ es sagte.
    # Ausgenommen (STILL_JE_ART): reine Buchhaltung des Kalender-Abgleichs, die Eingefrorenen Aufstellungen (Mahnung, Zeiten des Berichts) und die
    # Beschreibung eines Berichts im Entwurf (speichert beim Tippen wie die Antworten einer Checkliste; mit der Unterschrift steht sie fest).
    OrderItem, OrderSection, Invoice, InvoiceItem, Reminder, ServiceReport, MaintenanceContract, RoofArea, CalendarEvent,
    # Seit 1.9.124 (Stufe 5, R2, Punkt 1): jeder Statuswechsel am Auftrag mit Begründung (unveränderlich, ORM-Sperre); daneben die Zeile
    # „Auftrag · Status“ alt -> neu aus derselben Anfrage.
    OrderStatusChange,
)

# Seit 1.9.115: Felder, die je Art nicht als Änderung protokolliert werden (der Schnappschuss beim Anlegen enthält sie).
STILL_JE_ART = {
    CalendarEvent: {"outlook_synced_at", "outlook_etag", "outlook_event_id"},  # Abgleich mit Outlook (eigene Diagnose, Regel 18)
    MaintenanceContract: {"last_reminder_due_date"},  # Stempel gegen doppeltes Erinnern
    Reminder: {"amounts_json"},  # eingefrorene Aufstellung, steht an der Mahnung
    ServiceReport: {"time_rows_json"},  # eingefrorene Zeiten, stehen am Bericht
}
# Seit 1.9.115: Inhalte eines privaten Termins nie in der Historie (sie liest jedes Büro) -- nur, dass sich etwas geändert hat.
PRIVATE_TERMINFELDER = {"title", "location", "notes"}
PRIVAT = "(privat)"


def _still(obj, key, state=None) -> bool:
    if key in STILL_JE_ART.get(type(obj), ()):
        return True
    if isinstance(obj, ServiceReport) and key == "description":
        alt = state.attrs["status"].history.deleted if state is not None else ()
        return obj.status == "entwurf" and (not alt or alt[0] == "entwurf")
    return False


def _privat(obj) -> bool:
    return isinstance(obj, CalendarEvent) and bool(obj.is_private)

FIELD_LABELS = {
    "name":"Bezeichnung / Name","status":"Status","description":"Beschreibung","category":"Kategorie",
    "customer_id":"Kunde","property_id":"Objekt","project_number":"Projektnummer","title":"Titel",
    "original_filename":"Dateiname","document_date":"Dokumentdatum","quote_number":"Angebotsnummer","order_number":"Auftragsnummer","order_date":"Auftragsdatum","execution_start":"Ausführungsbeginn","execution_end":"Geplantes Ende","project_manager_employee_id":"Projektleiter / Vorarbeiter",
    "short_text":"Kurztext","long_text":"Langtext","quantity":"Menge","unit":"Mengeneinheit",
    "unit_price":"Einheitspreis","position_type":"Positionstyp","gaeb_oz":"OZ","intro_text":"Vortext",
    "outro_text":"Schlusstext","vat_rate":"MwSt.","payment_terms":"Zahlungsbedingungen",
    "execution_period":"Ausführungszeitraum","internal_note":"Interne Notiz","contact_person":"Ansprechpartner",
    "hourly_wage":"Kalkulatorischer Stundenlohn","weekly_hours":"Wochenstunden","compensation_type":"Vergütungsart","monthly_salary":"Monatsfestgehalt","cost_allocation":"Kosten-Zuordnung","allocation_type":"Kosten-Zuordnung","active":"Aktiv","available_as_caseworker":"Sachbearbeiter verfügbar","show_on_planning_board":"In Plantafel anzeigen",
    "street":"Straße","postal_code":"PLZ","city":"Ort","email":"E-Mail","phone":"Telefon","mobile":"Mobil",
    "birthday":"Geburtstag","important_info":"Wichtige Informationen","customer_number":"Kundennummer",
    "format_pattern":"Nummernformat","start_value":"Startnummer","next_value":"Nächste Nummer",
    "labor_rate":"Stundenkostenverrechnungssatz","fixed_overhead_mode":"Fixe GK Eingabeart","fixed_overhead_value":"Fixe Gemeinkosten","variable_overhead_mode":"Variable GK Eingabeart","variable_overhead_value":"Variable Gemeinkosten","material_markup_pct":"Materialaufschlag",
    "overhead_pct":"Gemeinkosten","risk_profit_pct":"Wagnis & Gewinn",
    "site_time_minutes":"Baustellenzeit","workshop_time_minutes":"Werkstattzeit","purchase_price":"Einkaufspreis",
    "waste_pct":"Verschnitt","sort_order":"Sortierung","include_in_total":"In Summe berücksichtigen",
    "label":"Bezeichnung","value":"Wert","is_default":"Standardwert","employee_group":"Mitarbeitergruppe",
    "function_id":"Funktion / Tätigkeit","caseworker_employee_id":"Sachbearbeiter",
    "planned_start":"Geplanter Baustart","planned_end":"Geplante Fertigstellung","site_notes":"Baustellenhinweise","material_notes":"Materialhinweise","planned_hours":"Geplante Stunden","role":"Rolle","priority":"Priorität","due_date":"Fälligkeit","assigned_employee_id":"Zuständig","planned_quantity":"Planmenge","supplier":"Lieferant","supplier_id":"Lieferant","resource_type":"Ressourcentyp","identifier":"Kennzeichen / Seriennummer","team_number":"Teamnummer","resource_number":"Ressourcennummer","supplier_number":"Lieferantennummer","delivery_note_number":"Lieferscheinnummer","start_date":"Planungsbeginn","end_date":"Planungsende","team_assignment_id":"Kolonne / Team","daily_work_hours":"Tägliche Arbeitszeit","default_travel_hours_per_employee_day":"Standard-Anfahrtszeit","federal_state_code":"Bundesland","auto_public_holidays":"Feiertage automatisch","show_school_holidays":"Schulferien anzeigen","holiday_date":"Feiertag / betriebsfreier Tag","absence_type":"Abwesenheitsart","decision":"Entscheidung","review_notes":"Freigabe-Notiz","reviewed_by_user_id":"Geprüft von","approved_absence_id":"Genehmigte Abwesenheit","team_id":"Team","travel_hours_per_employee_day":"Anfahrtszeit pro MA/Tag","work_date":"Arbeitstag","entry_type":"Zeitart","hours":"Ist-Stunden","break_minutes":"Pause (Min.)","min_break_minutes":"Pause mindestens (Min.)","activity":"Tätigkeit","order_item_id":"LV-Position","counts_as_productive":"Produktive Zeit","datev_personnel_number":"DATEV-Personalnummer","payroll_export_enabled":"DATEV-Lohnexport aktiv","datev_personnel_equals_erp_number":"DATEV-Nr. entspricht ERP-Nr.","default_work_time_model_id":"Standard-Arbeitszeitmodell","daily_target_hours":"Soll-Arbeitszeit pro Tag","threshold_hours":"Pausenschwelle","model_id":"Arbeitszeitmodell",
    "completed_at":"Abgeschlossen am","completed_by_employee_id":"Abgeschlossen von (Mitarbeiter)","signer_name":"Unterschrieben von","signer_kind":"Unterzeichner (Art)","signer_user_id":"Unterzeichner (Konto)","signer_participant_id":"Unterzeichner (Beteiligter)","signer_role":"Rolle des Unterzeichners","signer_poa_sha256":"Vollmacht (SHA-256)","signer_poa_content_type":"Vollmacht (Typ)","signer_poa_stored_filename":"Vollmacht (Datei)","seal_format":"Siegelformat","signer_person":"Unterschrieben von (Person)","signer_function":"Funktion der unterschreibenden Person","content_sha256":"Prüfsumme (SHA-256)","discarded_at":"Verworfen am","discarded_by_user_id":"Verworfen von (Konto)","discarded_by_name":"Verworfen von","discard_reason":"Begründung (Verwerfen)",
    "kind":"Art","company_name":"Firma","first_name":"Vorname","last_name":"Nachname","function":"Funktion","archived":"Archiviert","archived_at":"Archiviert am","contact_id":"Kontakt","copy_on_notices":"Kopie bei Anzeigen","authorized_recipient":"Empfangsbevollmächtigt für den Auftraggeber","poa_original_filename":"Vollmacht (Datei)","poa_sha256":"Vollmacht (Prüfsumme SHA-256)","poa_content_type":"Vollmacht (Dateiart)","poa_size_bytes":"Vollmacht (Größe)","poa_uploaded_at":"Vollmacht hochgeladen am","poa_uploaded_by_name":"Vollmacht hochgeladen von","poa_stored_filename":"Vollmacht (Ablagename)",
    # seit 1.8.47: Vollmacht zur Abnahme am Beteiligten
    "acceptance_authorized":"Vollmacht zur Abnahme","acceptance_poa_original_filename":"Vollmacht zur Abnahme (Datei)","acceptance_poa_sha256":"Vollmacht zur Abnahme (Prüfsumme SHA-256)","acceptance_poa_content_type":"Vollmacht zur Abnahme (Dateiart)","acceptance_poa_size_bytes":"Vollmacht zur Abnahme (Größe)","acceptance_poa_uploaded_at":"Vollmacht zur Abnahme hochgeladen am","acceptance_poa_uploaded_by_name":"Vollmacht zur Abnahme hochgeladen von","acceptance_poa_stored_filename":"Vollmacht zur Abnahme (Ablagename)",
    # seit 1.8.41: Checkliste als gegenstandslos abgeschlossen
    "void_reason":"Begründung (gegenstandslos)","voided_at":"Gegenstandslos am","voided_by_name":"Gegenstandslos durch","voided_by_user_id":"Gegenstandslos durch (Konto)",
    # seit 1.8.46: Leistungsart und Gewährleistungsdauer am Auftrag, Abnahme
    "work_kind":"Leistungsart","warranty_months":"Gewährleistung (Monate)","warranty_days":"Gewährleistung (Tage)",
    "accepted_on":"Abnahmedatum","scope":"Umfang","scope_description":"Umfang (Beschreibung)","result":"Ergebnis",
    "reservation_defects":"Vorbehalt Mängel","reservation_penalty":"Vorbehalt Vertragsstrafe",
    "contractor_objections":"Einwendungen des Auftragnehmers","declared_by":"Erklärt durch","participant_id":"Beteiligter",
    "declared_by_name":"Erklärt durch (Name)","declared_by_role":"Erklärt durch (Rolle)","poa_on_record":"Vollmacht hinterlegt",
    "conduct_reason":"Begründung (schlüssige Abnahme)","created_by_name":"Erfasst von","created_by_user_id":"Erfasst von (Konto)",
    # seit 1.8.48/1.8.49: Prüfsummenformat, Siegel des Verwerfens; Mangel und sein Verlauf
    "checksum_format":"Prüfsummenformat","discard_sha256":"Siegel des Verwerfens (SHA-256)",
    "source":"Quelle","acceptance_id":"Abnahme","roof_area_id":"Dachfläche","roof_area_name":"Dachfläche (Name)",
    "location":"Ortsangabe","remedy_due_on":"Beseitigungsfrist","task_id":"Aufgabe","defect_id":"Mangel",
    "previous_value":"Stand davor","event_date":"Datum","reason":"Begründung",
    "previous_event_sha256":"Prüfsumme des vorigen Eintrags",
    # seit 1.8.80: Nebenforderung, Verzugsbeginn, Kundenwechsel am Auftrag
    "amount":"Betrag","reminder_id":"Mahnung","reverses_charge_id":"Gegenbuchung zu","starts_on":"Verzug ab","basis":"Grundlage",
    "source_text":"Vorschlag (Quelle)","proposal_on":"Vorschlag","old_customer_id":"Kunde bisher","new_customer_id":"Kunde neu",
    "old_customer_name":"Kunde bisher (Name)","new_customer_name":"Kunde neu (Name)","changed_by_name":"Geändert von",
    "changed_by_user_id":"Geändert von (Konto)","dunning_charges_enabled":"Mahngebühren und Verzugszinsen",
    # seit 1.9.124: Statuswechsel am Auftrag
    "old_status":"Status bisher","new_status":"Status neu","without_invoice":"Ohne Rechnung abgeschlossen",
    # seit 1.8.81: Basiszinssatz, Rechtstexte, Verzugszinsen, Zahlung auf Nebenforderung
    "half_year_start":"Halbjahr ab","rate_percent":"Basiszinssatz (%)","reviewed_on":"Geprüft am","reviewed_by":"Geprüft durch",
    "text_key":"Rechtstext","body":"Text","period_start":"Zinsen ab","period_end":"Zinsen bis",
    "calculation_json":"Zinsberechnung","charge_id":"Nebenforderung","interest_accepted":"Verzugszinsen übernommen",
    # seit 1.8.138 jedes protokollierte Feld (bis dahin stand für 199 der Spaltenname in der Historie)
    "absence_category": "Abwesenheitskategorie",
    "accent_color": "Akzentfarbe",
    "access_notes": "Zugangshinweise",
    "allow_group_bookings": "Gruppenbuchungen erlauben",
    "allow_manual_entries": "Manuelle Buchungen erlauben",
    "annual_overhead": "Jährliche Gemeinkosten",
    "article_number": "Artikelnummer",
    "article_number_key": "Artikelnummer (Schlüssel)",
    "assigned_to": "Zugewiesen an",
    "assignment_id": "Team-Zuweisung",
    "bic": "BIC",
    "calculated_quantity": "Berechnete Menge",
    "calculation_id": "Kalkulation",
    "catalog_id": "Katalog",
    "category_id": "Kategorie",
    "changed_at": "Geändert am",
    "checklist_attachment_id": "Checklisten-Unterschrift",
    "checklist_id": "Checkliste",
    "client_uuid": "Gerätekennung",
    "code": "Kürzel",
    "content_type": "Dateiart",
    "context_detail_snapshot": "Bezug (Details)",
    "context_label_snapshot": "Bezug",
    "context_type": "Bezugsart",
    "contract_basis": "Vertragsgrundlage",
    "contract_basis_manual": "Vertragsgrundlage von Hand",
    "country": "Land",
    "created_by_employee_id": "Angelegt von (Mitarbeiter)",
    "customer_address": "Kundenanschrift",
    "customer_name": "Kundenname",
    "customer_number_at_supplier": "Kundennummer beim Lieferanten",
    "datev_beraternummer": "DATEV-Beraternummer",  # seit 1.9.92
    "datev_mandantennummer": "DATEV-Mandantennummer",  # seit 1.9.92
    "datev_target": "DATEV-Ziel",
    "datev_wage_type_other": "DATEV-Lohnart Sonstige",
    "datev_wage_type_site": "DATEV-Lohnart Baustelle",
    "datev_wage_type_travel": "DATEV-Lohnart Fahrzeit",
    "datev_wage_type_weather_summer": "DATEV-Lohnart Schlechtwetter Sommer",
    "datev_wage_type_weather_winter": "DATEV-Lohnart Schlechtwetter Winter",
    "datev_wage_type_workshop": "DATEV-Lohnart Werkstatt",
    "declared_by_function": "Erklärt durch (Funktion)",
    "declared_by_person": "Erklärt durch (Person)",
    "default_break_minutes": "Standardpause (Min.)",
    "default_payment_term_id": "Standard-Zahlungsbedingung",
    "default_quote_intro": "Standard-Vortext Angebot",
    "default_quote_outro": "Standard-Schlusstext Angebot",
    "default_vat_rate": "Standard-MwSt.",
    "delivery_note_id": "Lieferschein",
    "display_name": "Anzeigename",
    "due_on": "Fällig am",
    "email_2": "E-Mail 2",
    "email_sent_at": "E-Mail versendet am",
    "email_sent_to": "E-Mail versendet an",
    "employee_id": "Mitarbeiter",
    "employee_name_snapshot": "Mitarbeiter (Name)",
    "employee_number": "Personalnummer",
    "employer_cost_pct": "Arbeitgeberanteil (%)",
    "ended_at": "Ende",
    "equipment_cost": "Gerätekosten",
    "fax": "Fax",
    "file_size": "Dateigröße",
    "follow_up_at": "Wiedervorlage",
    "friday": "Freitag",
    "gaeb_exchange_phase": "GAEB-Austauschphase",
    "group_id": "Gruppe",
    "group_key": "Auswahlliste",
    "iban": "IBAN",
    "import_run_id": "Importlauf",
    "individually_changed_at": "Einzeln geändert am",
    "info_type": "Art der Information",
    "initiated_by_employee_id": "Ausgelöst von (Mitarbeiter)",
    "inquiry_number": "Anfragenummer",
    "invoice_id": "Rechnung",
    "is_consumer": "Verbraucher",
    "is_crew_leader": "Kolonnenführer",
    "is_primary_address": "Hauptadresse",
    "is_template": "Mustervorgang",
    "job_title": "Berufsbezeichnung",
    "labor_rate_override": "Verrechnungssatz (abweichend)",
    "last_year": "Letztes Jahr",
    "legacy_address_number": "Adressnummer im Altsystem",
    "locked_at": "Gesperrt am",
    "locked_by_user_id": "Gesperrt von (Konto)",
    "locked_until": "Gesperrt bis",
    "logo_filename": "Firmenlogo",
    "lost_reason": "Verlustgrund",
    "managing_director": "Geschäftsführer / Inhaber",
    "manual_sale_price": "Verkaufspreis von Hand",
    "manufacturer": "Hersteller",
    "material_id": "Material",
    "material_markup_pct_override": "Materialaufschlag (abweichend)",
    "material_name_key": "Materialname (Schlüssel)",
    "mode": "Modus",
    "model": "Modell",
    "monday": "Montag",
    "note": "Notiz",
    "notes": "Notizen",
    "operational_asset_id": "Betriebsmittel",
    "order_id": "Auftrag",
    "origin": "Herkunft",
    "other_cost": "Sonstige Kosten",
    "outlook_mailbox": "Outlook-Postfach",
    "outro_text_2": "Schlusstext 2",
    "overhead_pct_override": "Gemeinkosten (abweichend)",
    "parent_id": "Übergeordneter Eintrag",
    "payment_id": "Zahlung",
    "pipeline_column_id": "Pipeline-Spalte",
    "position_number": "Positionsnummer",
    "preparation_id": "Arbeitsvorbereitung",
    "price_basis": "Preisbasis",
    "price_basis_override": "Preisbasis (abweichend)",
    "productive_time_pct": "Produktivzeit (%)",
    "project_document_id": "Projektdatei",
    "project_id": "Projekt",
    "property_address": "Objektanschrift",
    "property_name": "Objekt (Name)",
    "protocol_pdf_sha256": "Protokoll-PDF (Prüfsumme)",
    "protocol_seal_sha256": "Protokoll-Siegel (Prüfsumme)",
    "protocol_version_id": "Protokollfassung",
    "public_base_url": "Öffentliche Adresse",
    "purchase_price_override": "Einkaufspreis (abweichend)",
    "quantity_override": "Menge (abweichend)",
    "quote_date": "Angebotsdatum",
    "quote_id": "Angebot",
    "quote_item_id": "Angebotsposition",
    "quote_number_snapshot": "Angebotsnummer (Stand)",
    "received_on": "Eingegangen am",
    "register_court": "Registergericht",
    "register_number": "Registernummer",
    "released_at": "Freigegeben am",
    "released_by_employee_id": "Freigegeben von (Mitarbeiter)",
    "released_by_name": "Freigegeben von",
    "released_by_user_id": "Freigegeben von (Konto)",
    "remarks": "Bemerkungen",
    "reminders_auto_create_drafts": "Mahnentwürfe automatisch anlegen",
    "requested_by_user_id": "Beantragt von (Konto)",
    "require_activity": "Tätigkeit Pflicht",
    "require_order_item": "LV-Position Pflicht",
    "reset_yearly": "Jährlich zurücksetzen",
    "resource_id": "Ressource",
    "resource_name_snapshot": "Ressource (Name)",
    "resource_type_snapshot": "Ressourcentyp (Stand)",
    "reverses_allocation_id": "Gegenbuchung zu (Zuordnung)",
    "reverses_payment_id": "Gegenbuchung zu (Zahlung)",
    "reviewed_at": "Geprüft am",
    "revision_number": "Revisionsnummer",
    "risk_profit_pct_override": "Wagnis & Gewinn (abweichend)",
    "role_snapshot": "Rolle (Stand)",
    "rounding_minutes": "Rundung (Min.)",
    "salutation": "Anrede",
    "saturday": "Samstag",
    "section_id": "LV-Titel",
    "section_number": "Titelnummer",
    "sequence_key": "Nummernkreis",
    "service_id": "Leistung",
    "sidebar_logo_filename": "Logo der Leiste",
    "sidebar_logo_height_px": "Logohöhe in der Leiste (px)",
    "site_contact_name": "Ansprechpartner vor Ort",
    "site_contact_phone": "Telefon vor Ort",
    "slot_id": "Plantafel-Einsatz",
    "snapshot_json": "Stand (Daten)",
    "source_external_id": "Externe Kennung (Quelle)",
    "source_format": "Quellformat",
    "source_maintenance_contract_id": "Aus Wartungsvertrag",
    "source_maintenance_contract_item_id": "Aus Wartungsvertrag (Dachfläche)",
    "source_material_id": "Quellmaterial",
    "source_material_snapshot_id": "Quellmaterial (Stand)",
    "source_order_item_id": "Quellposition (Auftrag)",
    "source_purchase_price": "Einkaufspreis (Quelle)",
    "source_quantity": "Menge (Quelle)",
    "source_quote_id": "Quellangebot",
    "source_service_id": "Quellleistung",
    "source_unit_price": "Einheitspreis (Quelle)",
    "started_at": "Beginn",
    "stored_filename": "Ablagename",
    "subcontractor_cost": "Fremdleistung",
    "subfolder": "Unterordner",
    "sunday": "Sonntag",
    "target_profit_pct": "Zielgewinn (%)",
    "tax_key_id": "Steuerschlüssel",
    "tax_number": "Steuernummer",
    "team_name_snapshot": "Team (Name)",
    "template_field_id": "Vorlagenfeld",
    "template_id": "Vorlage",
    "template_label_snapshot": "Vorlage (Name)",
    "template_version_id": "Vorlagenfassung",
    "thursday": "Donnerstag",
    "time_entry_id": "Zeitbuchung",
    "totp_confirmed_at": "Zweiter Faktor bestätigt am",
    "totp_secret_encrypted": "Zweiter Faktor (verschlüsselt)",
    "tuesday": "Dienstag",
    "updated_by_name": "Geändert von",
    "uploaded_at": "Hochgeladen am",
    "use_source_time_as_minutes": "Quellzeit als Minuten",
    "username": "Benutzername",
    "valid_until": "Gültig bis",
    "vat_id": "USt-IdNr.",
    "visit_at": "Termin vor Ort",
    "website": "Website",
    "wednesday": "Mittwoch",
    "weeks_per_year": "Wochen pro Jahr",
    # seit 1.9.115: Auftragspositionen, Rechnungen, Mahnungen, Einsatzberichte, Wartungsverträge, Dachflächen, Termine
    "source_quote_item_id": "Angebotsposition (Herkunft)", "is_addendum": "Nachtrag", "source_quote_section_id": "Angebots-LV-Titel (Herkunft)",
    "invoice_number": "Rechnungsnummer", "invoice_type": "Rechnungsart", "invoice_date": "Rechnungsdatum", "paid_date": "Bezahlt am (bis 1.8.77)",
    "service_period_start": "Leistungszeitraum Beginn", "service_period_end": "Leistungszeitraum Ende",
    "billed_work_from": "Abgerechnete Arbeit ab", "billed_work_to": "Abgerechnete Arbeit bis", "storno_of_invoice_id": "Storno zu Rechnung",
    "tax_notice_text": "Steuerhinweis", "lump_sum_net": "Pauschalbetrag netto", "progress_description": "Bezeichnung des Abschlags",
    "rounding_rule": "Rundungsregel", "skonto_percent": "Skonto (%)", "skonto_days": "Skontotage",
    "payment_terms_text_template": "Text der Zahlungsbedingung", "pdf_document_id": "Feste Fassung (PDF)", "finalized_at": "Festgeschrieben am",
    "closes_order": "Abschließende Rechnung",
    "soll_quantity": "Soll-Menge", "ist_quantity": "Ist-Menge (gesamt)", "billed_quantity": "Abgerechnete Menge", "billed_total": "Betrag",
    "reminder_number": "Mahnungsnummer", "level": "Mahnstufe", "reminder_date": "Mahndatum", "new_due_date": "Neue Frist",
    "outstanding_amount": "Angemahnter Betrag", "fee_amount": "Mahngebühr", "text": "Text", "amounts_json": "Aufstellung",
    "replaced_by_id": "Ersetzt durch Mahnung", "replaced_at": "Ersetzt am", "fee_accepted": "Mahngebühr übernommen",
    "flat_fee_accepted": "Pauschale übernommen",
    "report_type": "Berichtstyp", "performed_at": "Datum des Einsatzes", "signature_path": "Unterschrift Kunde (Datei)",
    "signature_name": "Unterschrieben von (Kunde)", "signed_at": "Unterschrieben am", "installer_signature_path": "Unterschrift Monteur (Datei)",
    "installer_signature_name": "Unterschrieben von (Monteur)", "installer_signed_at": "Monteur unterschrieben am",
    "maintenance_contract_id": "Wartungsvertrag", "maintenance_contract_item_id": "Leistung des Wartungsvertrags",
    "inspection_template_id": "Prüfvorlage", "inspection_template_version": "Fassung der Prüfvorlage",
    "advance_due_date_on_sign": "Nächste Fälligkeit mit der Unterschrift", "time_rows_json": "Zeiten des Berichts",
    "interval_months": "Intervall (Monate)", "next_due_date": "Nächste Fälligkeit", "last_reminder_due_date": "Zuletzt erinnert für",
    "template_project_id": "Vorlage-Projekt", "responsible_employee_id": "Zuständig",
    "roof_type": "Dachtyp", "covering": "Eindeckung", "pitch_degrees": "Dachneigung (°)", "area_sqm": "Fläche (m²)", "build_up": "Aufbau",
    "insulation": "Dämmung", "last_renovation": "Letzte Sanierung", "contractor": "Ausführende Firma",
    "third_party_guarantee_until": "Garantie Dritter bis", "sketch_path": "Skizze (Datei)",
    "start_at": "Beginn", "end_at": "Ende", "all_day": "Ganztägig", "owner_user_id": "Besitzer (Konto)", "is_private": "Privat",
    "outlook_event_id": "Outlook-Termin", "external_source": "Herkunft", "outlook_synced_at": "Mit Outlook abgeglichen am",
    "outlook_etag": "Outlook-Stand",
}


def set_audit_context(user=None, request=None):
    return (
        _actor_id.set(getattr(user, "id", None)),
        _actor_name.set(getattr(user, "display_name", None) or getattr(user, "username", None) or "System"),
        _request_path.set(str(request.url.path) if request else None),
        _request_method.set(request.method if request else None),
    )


def reset_audit_context(tokens):
    _actor_id.reset(tokens[0]); _actor_name.reset(tokens[1]); _request_path.reset(tokens[2]); _request_method.reset(tokens[3])


def current_actor() -> tuple[int | None, str]:
    """(Benutzer-ID, Anzeigename) der laufenden Anfrage, außerhalb einer Anfrage (None, "System").
    Für Protokolle, die den Auslöser nicht als Argument bekommen (seit 1.8.17: Versandprotokoll
    einer Aufgaben-Mail)."""
    return _actor_id.get(), _actor_name.get()


TASK_ENTITY_TYPE = "Aufgabe"


def record_audit_entry(session, *, action, entity_type, entity_id, entity_label, project_id=None,
                       field_name=None, field_label=None, old_value=None, new_value=None,
                       actor_user_id=None, actor_name=None):
    """Historienzeile für eine Änderung, die an before_flush vorbeiläuft (seit 1.8.18: bedingtes
    UPDATE beim Übernehmen einer Aufgabe, app/tasks.py::claim_task()). Committet nicht -- die
    Zeile gehört in dieselbe Transaktion wie die Änderung selbst. Auslöser aus den Argumenten,
    sonst aus dem Anfragekontext."""
    session.add(AuditLog(
        actor_user_id=actor_user_id if actor_user_id is not None else _actor_id.get(),
        actor_name=actor_name or _actor_name.get(), action=action, entity_type=entity_type,
        entity_id=str(entity_id), entity_label=(entity_label or "")[:255] or None, project_id=project_id,
        field_name=field_name, field_label=field_label or FIELD_LABELS.get(field_name, field_name),
        old_value=_text(old_value), new_value=_text(new_value), request_method=_request_method.get(),
        request_path=_request_path.get(),
    ))


def _text(value):
    if value is None: return None
    if isinstance(value, (datetime, date)): return value.isoformat()
    if isinstance(value, Decimal): return format(value, "f")
    if isinstance(value, bool): return "Ja" if value else "Nein"
    if isinstance(value, (dict, list, tuple)): return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _columns(obj):
    state = inspect(obj)
    return [a.key for a in state.mapper.column_attrs if a.key not in EXCLUDED_FIELDS and a.key != "id"]


def _snapshot(obj):
    werte = {k: _text(getattr(obj, k, None)) for k in _columns(obj) if getattr(obj, k, None) not in (None, "")}
    if _privat(obj):  # seit 1.9.115: Inhalt eines privaten Termins nie im Schnappschuss
        werte = {k: (PRIVAT if k in PRIVATE_TERMINFELDER else v) for k, v in werte.items()}
    return werte


def _normalize(session, obj):
    """Gibt (entity_type, entity_id, label, project_id) zurück und fasst Erweiterungstabellen fachlich zusammen."""
    if isinstance(obj, CustomerProfile):
        c = session.get(Customer, obj.customer_id); return "Kunde", str(obj.customer_id), _entity_label(c), None
    if isinstance(obj, ProjectProfile):
        p = session.get(Project, obj.project_id); return "Projekt", str(obj.project_id), _entity_label(p), obj.project_id
    if isinstance(obj, ProjectParticipant):
        # Über session.get, nicht obj.contact -- bei "gelöscht" ist die Zeile schon aus der Sitzung.
        from .contacts import contact_display_name
        from .project_participants import role_label
        c = session.get(Contact, obj.contact_id)
        name = contact_display_name(c) if c else f"Kontakt #{obj.contact_id}"
        return "Projektbeteiligter", str(obj.id), f"{name} · {role_label(obj.role)}"[:255], obj.project_id
    if isinstance(obj, (EmployeeProfile, EmployeeRoleSettings, EmployeeCompensationSettings, EmployeeCostAllocationSettings, EmployeePlanningSettings)):
        e = session.get(Employee, obj.employee_id); return "Mitarbeiter", str(obj.employee_id), _entity_label(e), None
    if isinstance(obj, QuoteDocumentMeta) or isinstance(obj, QuoteSection) or isinstance(obj, QuoteEmployeeAssignment):
        q = session.get(Quote, obj.quote_id); return TYPE_LABELS.get(type(obj), "Angebot"), str(obj.quote_id), _entity_label(q), q.project_id if q else None
    if isinstance(obj, QuoteItemLayout):
        qi = session.get(QuoteItem, obj.quote_item_id); return "Angebotsposition", str(obj.quote_item_id), _entity_label(qi), _project_for_quote_item(session, qi)
    if isinstance(obj, QuoteItemCalculation):
        qi = session.get(QuoteItem, obj.quote_item_id); return "Positionskalkulation", str(obj.quote_item_id), _entity_label(qi), _project_for_quote_item(session, qi)
    if isinstance(obj, QuoteItemMaterialCalculation):
        calc = session.get(QuoteItemCalculation, obj.calculation_id); qi = session.get(QuoteItem, calc.quote_item_id) if calc else None
        return "Materialkalkulation", str(qi.id) if qi else None, obj.name, _project_for_quote_item(session, qi)
    if isinstance(obj, WorkPreparation):
        o = session.get(Order, obj.order_id); return "Arbeitsvorbereitung", str(obj.id), _entity_label(o), o.project_id if o else None
    if isinstance(obj, PlanningSlot):
        prep = session.get(WorkPreparation, obj.preparation_id)
        order = session.get(Order, prep.order_id) if prep else None
        assignment = session.get(WorkPreparationTeamAssignment, obj.team_assignment_id)
        label = f"{assignment.team_name_snapshot if assignment else 'Team'} · {_entity_label(order) or ''}".strip(" ·")
        return "Plantafel-Einsatz", str(obj.id), label[:255], order.project_id if order else None
    if isinstance(obj, PlanningSlotCapacity):
        slot = session.get(PlanningSlot, obj.slot_id)
        prep = session.get(WorkPreparation, slot.preparation_id) if slot else None
        order = session.get(Order, prep.order_id) if prep else None
        return "Plantafel-Kapazität", str(obj.slot_id), _entity_label(slot), order.project_id if order else None
    if isinstance(obj, EmployeeAbsence):
        # Kein absence_type im Label (siehe CLAUDE.md "Krankheitssichtbarkeit") -- die Art landet
        # ausschließlich im details-Schnappschuss, wo sie für buero_auftrag gezielt redigierbar
        # ist (redact_absence_snapshot() unten). Der Zeitraum bleibt im Label, Daten sind nicht
        # die sensible Information.
        emp = session.get(Employee, obj.employee_id)
        return "Mitarbeiter-Abwesenheit", str(obj.id), f"{_entity_label(emp) or 'Mitarbeiter'} · {obj.start_date}–{obj.end_date}", None
    if isinstance(obj, EmployeeAbsenceRequest):
        emp = session.get(Employee, obj.employee_id)
        return "Abwesenheitsantrag", str(obj.id), f"{_entity_label(emp) or 'Mitarbeiter'} · {obj.start_date}–{obj.end_date}", None
    if isinstance(obj, TimeEntryGroup):
        order = session.get(Order, obj.order_id)
        return "Gruppen-Zeitbuchung", str(obj.id), f"{_entity_label(order) or 'Auftrag'} · {obj.work_date} · {obj.entry_type}", order.project_id if order else obj.project_id
    if isinstance(obj, TimeEntryGroupMember):
        group = session.get(TimeEntryGroup, obj.group_id)
        order = session.get(Order, group.order_id) if group else None
        emp = session.get(Employee, obj.employee_id)
        return "Gruppenbuchungs-Mitglied", str(obj.id), f"{_entity_label(emp) or 'Mitarbeiter'} · Gruppe #{obj.group_id}", order.project_id if order else None
    if isinstance(obj, TimeEntry):
        emp = session.get(Employee, obj.employee_id)
        order = session.get(Order, obj.order_id)
        label = f"{_entity_label(emp) or 'Mitarbeiter'} · {obj.work_date} · {obj.entry_type} · {obj.hours} h"
        return "Zeitbuchung", str(obj.id), label[:255], order.project_id if order else obj.project_id
    if isinstance(obj, WorkPreparationMaterialDeliveryNote):
        material=session.get(WorkPreparationMaterial,obj.material_id)
        prep=session.get(WorkPreparation,material.preparation_id) if material else None
        order=session.get(Order,prep.order_id) if prep else None
        note=session.get(WorkPreparationDeliveryNote,obj.delivery_note_id)
        label=f"{material.name if material else 'Material'} ↔ {note.delivery_note_number or ('Lieferschein #'+str(note.id)) if note else 'Lieferschein'}"
        return "Material-Lieferschein-Zuordnung", str(obj.id), label[:255], order.project_id if order else None
    if isinstance(obj, (WorkPreparationEmployee, WorkPreparationTask, WorkPreparationMaterial, WorkPreparationTeamAssignment, WorkPreparationDeliveryNote)):
        prep = session.get(WorkPreparation, obj.preparation_id); o = session.get(Order, prep.order_id) if prep else None
        return TYPE_LABELS.get(type(obj), type(obj).__name__), str(obj.id), _entity_label(obj), o.project_id if o else None
    if isinstance(obj, Checklist):
        return "Checkliste", str(obj.id), _checklist_label(obj, obj.id), _checklist_project_id(session, obj)
    if isinstance(obj, ChecklistAttachment):
        # entity_id ist die Checkliste (Muster QuoteSection → Angebot); Unterschrift und Foto getrennt
        # benannt, damit "Unterschreiben"/"Verwerfen" in der Historie als solches lesbar ist.
        checklist = session.get(Checklist, obj.checklist_id)
        signature = obj.kind == "unterschrift"
        label = f"{_checklist_label(checklist, obj.checklist_id)} · {obj.signer_name if signature else 'Foto'}"
        return ("Checklisten-Unterschrift" if signature else "Checklisten-Foto"), str(obj.checklist_id), label[:255], \
            _checklist_project_id(session, checklist)
    if isinstance(obj, ChecklistAssetRelease):
        from .operational_assets import resolve_asset_identity  # lokal: nur hier gebraucht
        asset = session.get(OperationalAsset, obj.operational_asset_id)
        name = resolve_asset_identity(asset)[0] if asset else None
        number = f" ({asset.asset_number})" if asset and asset.asset_number else ""
        label = f"{name or 'Betriebsmittel'}{number} · Meldung aus Checkliste Nr. {obj.checklist_id}"
        return "Gerät als repariert markiert", str(obj.checklist_id), label[:255], None
    if isinstance(obj, Order): return "Auftrag", str(obj.id), _entity_label(obj), obj.project_id
    if isinstance(obj, OrderAcceptance):
        from .acceptances import ENTITY_TYPE, _label
        o = session.get(Order, obj.order_id)
        return ENTITY_TYPE, str(obj.id), _label(obj, o), o.project_id if o else None
    if isinstance(obj, (Defect, DefectEvent)):
        # Seit 1.8.49: ein Eintrag im Verlauf steht unter der Kennung seines Mangels (Muster Checklisten-Unterschrift).
        from .defects import ENTITY_TYPE, EVENT_KINDS, defect_label
        defect = obj if isinstance(obj, Defect) else session.get(Defect, obj.defect_id)
        o = session.get(Order, defect.order_id) if defect else None
        label = defect_label(defect, o) if defect else f"Mangel Nr. {obj.defect_id}"
        if isinstance(obj, DefectEvent):
            label = f"{label} · {EVENT_KINDS.get(obj.kind, obj.kind)}"[:255]
        return ENTITY_TYPE, str(defect.id if defect else obj.defect_id), label, o.project_id if o else None
    if isinstance(obj, (Payment, PaymentAllocation)):
        from .payments import KIND_LABELS, money  # lokal: nur hier gebraucht
        # Die Gegenbuchung einer Zahlung steht unter der Kennung der Zahlung, die sie zurücknimmt.
        if isinstance(obj, Payment):
            payment = session.get(Payment, obj.reverses_payment_id) if obj.reverses_payment_id is not None else obj
        else:
            payment = session.get(Payment, obj.payment_id)
        customer = session.get(Customer, payment.customer_id) if payment else None
        label = (f"Zahlung {money(abs(payment.amount))} vom {payment.received_on.strftime('%d.%m.%Y')}"
                 f"{' · ' + customer.name if customer else ''}") if payment else f"Zahlung Nr. {obj.payment_id}"
        if isinstance(obj, Payment) and obj.reverses_payment_id is not None:
            label = f"{label} · zurückgenommen"
        project_id = None
        if isinstance(obj, PaymentAllocation):
            invoice = session.get(Invoice, obj.invoice_id)
            order = session.get(Order, invoice.order_id) if invoice else None
            project_id = order.project_id if order else None
            what = "Gegenbuchung " if obj.reverses_allocation_id is not None else ""
            label = (f"{label} · {what}{KIND_LABELS.get(obj.kind, obj.kind)} {money(abs(obj.amount))} an "
                     f"{invoice.invoice_number if invoice else 'Rechnung'}")
        return "Zahlungseingang", str(payment.id if payment else obj.payment_id), label[:255], project_id
    if isinstance(obj, (InvoiceCharge, InvoiceDefaultStart)):
        from .dunning_charges import KIND_LABELS, money  # lokal: nur hier gebraucht
        invoice = session.get(Invoice, obj.invoice_id)
        order = session.get(Order, invoice.order_id) if invoice else None
        number = invoice.invoice_number if invoice else f"Rechnung {obj.invoice_id}"
        if isinstance(obj, InvoiceCharge):
            what = "Gegenbuchung " if obj.reverses_charge_id is not None else ""
            label = f"{what}{KIND_LABELS.get(obj.kind, obj.kind)} {money(abs(obj.amount))} · {number}"
            return "Nebenforderung", str(obj.reverses_charge_id or obj.id), label[:255], order.project_id if order else None
        label = f"Verzug ab {obj.starts_on.strftime('%d.%m.%Y')} · {number}"
        return "Verzugsbeginn", str(obj.id), label[:255], order.project_id if order else None
    if isinstance(obj, BaseInterestRate):
        from .default_interest import half_year_label  # lokal: nur hier gebraucht
        return "Basiszinssatz", str(obj.id), f"Basiszinssatz {half_year_label(obj.half_year_start)}"[:255], None
    if isinstance(obj, DunningLegalText):
        from .dunning_texts import LEGAL_TEXT_LABELS  # lokal: nur hier gebraucht
        return "Rechtstext Mahnwesen", obj.text_key, f"Rechtstext {LEGAL_TEXT_LABELS.get(obj.text_key, obj.text_key)}"[:255], None
    if isinstance(obj, OrderStatusChange):
        from .auftragsstatus import name as status_name  # lokal: nur hier gebraucht
        o = session.get(Order, obj.order_id)
        label = f"{o.order_number if o else 'Auftrag'} · {status_name(obj.old_status)} → {status_name(obj.new_status)}"
        return "Auftragsstatus", str(obj.id), label[:255], o.project_id if o else None
    if isinstance(obj, OrderCustomerChange):
        o = session.get(Order, obj.order_id)
        label = f"Kundenwechsel {obj.old_customer_name} → {obj.new_customer_name} · {_entity_label(o) or ''}".strip(" ·")
        return "Auftrag", str(obj.order_id), label[:255], o.project_id if o else None
    if isinstance(obj, Invoice):
        o = session.get(Order, obj.order_id)
        return "Rechnung", str(obj.id), _invoice_label(obj), o.project_id if o else None
    if isinstance(obj, InvoiceItem):
        inv = session.get(Invoice, obj.invoice_id); o = session.get(Order, inv.order_id) if inv else None
        position = f"{obj.gaeb_oz or obj.position_number or ''} {obj.short_text or ''}".strip()
        return "Rechnungsposition", str(obj.id), f"{_invoice_label(inv) if inv else 'Rechnung'} · {position}"[:255], o.project_id if o else None
    if isinstance(obj, Reminder):
        inv = session.get(Invoice, obj.invoice_id); o = session.get(Order, inv.order_id) if inv else None
        label = f"{obj.reminder_number or 'Entwurf'} · {obj.level}. Mahnung zu {inv.invoice_number if inv and inv.invoice_number else 'Rechnung'}"
        return "Mahnung", str(obj.id), label[:255], o.project_id if o else None
    if isinstance(obj, ServiceReport):
        o = session.get(Order, obj.order_id)
        from .service_reports import REPORT_TYPE_LABELS  # lokal: nur hier gebraucht
        art = REPORT_TYPE_LABELS.get(obj.report_type, "Einsatzbericht")
        tag = obj.performed_at.strftime("%d.%m.%Y") if obj.performed_at else ""
        return "Einsatzbericht", str(obj.id), f"{art} vom {tag} · {o.order_number if o else ''}".strip(" ·")[:255], o.project_id if o else None
    if isinstance(obj, MaintenanceContract):
        c = session.get(Customer, obj.customer_id)
        return "Wartungsvertrag", str(obj.id), f"{obj.title}{' · ' + c.name if c else ''}"[:255], None
    if isinstance(obj, RoofArea):
        p = session.get(Property, obj.property_id)
        return "Dachfläche", str(obj.id), f"{obj.name}{' · ' + p.name if p else ''}"[:255], None
    if isinstance(obj, CalendarEvent):
        tag = obj.start_at.strftime("%d.%m.%Y") if obj.start_at else ""
        titel = "Privater Termin" if _privat(obj) else (obj.title or "Termin")
        return "Termin", str(obj.id), f"{titel} · {tag}".strip(" ·")[:255], obj.project_id
    if isinstance(obj, OrderRevision):
        o = session.get(Order, obj.order_id); return "Auftragsrevision", str(obj.id), f"Revision {obj.revision_number} · {_entity_label(o) or ''}".strip(), o.project_id if o else None
    if isinstance(obj, OrderSection):
        o = session.get(Order, obj.order_id); return "Auftrags-LV-Titel", str(obj.id), obj.title, o.project_id if o else None
    if isinstance(obj, OrderItem):
        o = session.get(Order, obj.order_id); return "Auftragsposition", str(obj.id), _entity_label(obj), o.project_id if o else None
    et = TYPE_LABELS.get(type(obj), type(obj).__name__)
    eid = str(getattr(obj, "id", "")) or None
    pid = None
    if isinstance(obj, Project): pid = obj.id
    elif isinstance(obj, Inquiry): pid = obj.project_id
    elif isinstance(obj, ProjectDocument): pid = obj.project_id
    elif isinstance(obj, Quote): pid = obj.project_id
    elif isinstance(obj, QuoteItem): pid = _project_for_quote_item(session, obj)
    return et, eid, _entity_label(obj), pid


# Rechnungsart in der Historie (Bezeichnung der Rechnung, Wert von invoice_type -- app/verlauf_namen.py)
RECHNUNGSARTEN = {"abschlag_pauschal": "Abschlag (Pauschal)", "abschlag_leistungsstand": "Abschlag (Leistungsstand)",
                   "schluss": "Schlussrechnung", "aufwand": "Rechnung aus Aufwand", "storno": "Stornorechnung"}


def _invoice_label(invoice) -> str:
    """Seit 1.9.115: „R-2026-0001 · Schlussrechnung“, im Entwurf „Entwurf · Schlussrechnung“."""
    return f"{invoice.invoice_number or 'Entwurf'} · {RECHNUNGSARTEN.get(invoice.invoice_type, invoice.invoice_type)}"


def _checklist_label(checklist, checklist_id):
    if checklist is None:  # z. B. Anhang eines gerade gelöschten Entwurfs
        return f"Checkliste Nr. {checklist_id}"
    context = f" · {checklist.context_label_snapshot}" if checklist.context_label_snapshot else ""
    return f"Nr. {checklist.id} {checklist.template_label_snapshot}{context}"[:255]


def _checklist_project_id(session, checklist):
    """Checklisten am Auftrag erscheinen auch in der Historie der Projektmappe."""
    if checklist is None or not checklist.order_id:
        return None
    order = session.get(Order, checklist.order_id)
    return order.project_id if order else None


def _project_for_quote_item(session, qi):
    if not qi: return None
    q = session.get(Quote, qi.quote_id)
    return q.project_id if q else None


def _entity_label(obj):
    if obj is None: return None
    if isinstance(obj, Customer): return f"{obj.customer_number or ''} {obj.name}".strip()
    if isinstance(obj, Property): return obj.name
    if isinstance(obj, Project): return f"{obj.project_number} · {obj.name}"
    if isinstance(obj, ProjectDocument): return obj.original_filename
    if isinstance(obj, Quote): return f"{obj.quote_number} · {obj.title}"
    if isinstance(obj, Order): return f"{obj.order_number} · {obj.title}"
    if isinstance(obj, OrderItem): return f"{obj.gaeb_oz or obj.position_number or ''} {obj.short_text}".strip()[:255]
    if isinstance(obj, WorkPreparationTask): return obj.title
    if isinstance(obj, WorkPreparationMaterial): return obj.name[:255]
    if isinstance(obj, WorkPreparationEmployee): return f"Mitarbeiter #{obj.employee_id}"
    if isinstance(obj, WorkPreparationTeamAssignment): return obj.team_name_snapshot
    if isinstance(obj, WorkPreparationDeliveryNote): return obj.delivery_note_number or f"Lieferschein #{obj.id}"
    if isinstance(obj, PlanningSlot): return f"Planeinsatz {obj.start_date}–{obj.end_date}"
    if isinstance(obj, Supplier): return f"{obj.supplier_number or ''} {obj.name}".strip()
    if isinstance(obj, Contact):
        from .contacts import contact_display_name
        return contact_display_name(obj) or f"Kontakt #{obj.id}"
    if isinstance(obj, OperationalResource): return f"{obj.resource_number or ''} {obj.name}".strip()
    if isinstance(obj, Team): return f"{obj.team_number or ''} {obj.name}".strip()
    if isinstance(obj, QuoteItem): return f"{obj.gaeb_oz or obj.position_number or ''} {obj.short_text}".strip()[:255]
    if isinstance(obj, Employee): return f"{obj.employee_number or ''} {obj.first_name} {obj.last_name}".strip()
    if isinstance(obj, TimeEntry): return f"{obj.work_date} · {obj.entry_type} · {obj.hours} h"
    if isinstance(obj, EmployeeFunction): return obj.name
    if isinstance(obj, NumberSequence): return obj.label
    if isinstance(obj, SettingOption): return obj.label
    if isinstance(obj, AppUser): return obj.display_name
    return getattr(obj, "name", None) or getattr(obj, "title", None) or TYPE_LABELS.get(type(obj), type(obj).__name__)  # seit 1.8.138 lesbar


def _record(action, obj, field_name=None, old=None, new=None, details=None):
    return {"action":action,"obj":obj,"field_name":field_name,"old":_text(old),"new":_text(new),"details":details}


@event.listens_for(Session, "before_flush")
def collect_audit(session, flush_context, instances):
    if session.info.get("audit_disabled") or _request_method.get() == "GET": return
    pending = session.info.setdefault("_audit_pending", [])
    for obj in list(session.new):
        if isinstance(obj, AuditLog) or not isinstance(obj, AUDITED_TYPES) or isinstance(obj, EXTENSION_TYPES): continue
        pending.append(_record("angelegt", obj, details=json.dumps(_snapshot(obj), ensure_ascii=False)))
    for obj in list(session.dirty):
        if isinstance(obj, AuditLog) or not isinstance(obj, AUDITED_TYPES) or not session.is_modified(obj, include_collections=False): continue
        state = inspect(obj)
        for attr in state.mapper.column_attrs:
            key = attr.key
            if key in EXCLUDED_FIELDS or key == "id" or _still(obj, key, state): continue
            hist = state.attrs[key].history
            if not hist.has_changes(): continue
            old = hist.deleted[0] if hist.deleted else None
            new = hist.added[0] if hist.added else getattr(obj, key, None)
            if _text(old) == _text(new): continue
            if key in PRIVATE_TERMINFELDER and (_privat(obj) or (isinstance(obj, CalendarEvent) and state.attrs["is_private"].history.deleted
                                                                  and state.attrs["is_private"].history.deleted[0])):
                old, new = PRIVAT, PRIVAT  # seit 1.9.115: privater Termin -- nur, dass sich der Inhalt änderte
            if isinstance(obj, ProjectParticipant) and key == "role":
                # Rolle als Beschriftung ("Hausverwaltung → Eigentümer"), nicht als Schlüssel (seit 1.8.37)
                from .project_participants import role_label
                old, new = role_label(old), role_label(new)
            pending.append(_record("geändert", obj, key, old, new))
    for obj in list(session.deleted):
        if isinstance(obj, AuditLog) or not isinstance(obj, AUDITED_TYPES): continue
        pending.append(_record("gelöscht", obj, details=json.dumps(_snapshot(obj), ensure_ascii=False)))


@event.listens_for(Session, "after_soft_rollback")
def drop_pending_audit(session, previous_transaction):
    """Vorgemerkte Einträge eines gescheiterten Flushs verwerfen (seit 1.8.13). before_flush merkt
    vor, erst after_flush_postexec schreibt -- scheitert der Flush dazwischen (typisch: Einfügen im
    SAVEPOINT kollidiert mit einem Unique-Constraint, Muster "Self-Seeding"/client_uuid), blieb die
    Vormerkung liegen und landete beim nächsten erfolgreichen Flush als Geisterzeile ("Nr. None …
    angelegt") in der Historie. Jeder Rollback -- auch der interne des gescheiterten Flushs und der
    eines SAVEPOINTs -- räumt deshalb auf; nach einem erfolgreichen Flush ist die Liste ohnehin leer."""
    session.info.pop("_audit_pending", None)


@event.listens_for(Session, "after_flush_postexec")
def write_audit(session, flush_context):
    pending = session.info.pop("_audit_pending", [])
    if not pending: return
    session.info["audit_disabled"] = True
    try:
        for p in pending:
            obj = p["obj"]
            et, eid, label, project_id = _normalize(session, obj)
            session.add(AuditLog(
                actor_user_id=_actor_id.get(), actor_name=_actor_name.get(), action=p["action"],
                entity_type=et, entity_id=eid, entity_label=label, project_id=project_id,
                field_name=p["field_name"], field_label=FIELD_LABELS.get(p["field_name"], p["field_name"]),
                old_value=p["old"], new_value=p["new"], request_method=_request_method.get(),
                request_path=_request_path.get(), details=p["details"],
            ))
    finally:
        session.info["audit_disabled"] = False


WAGE_FIELD_NAMES = {"hourly_wage", "monthly_salary", "compensation_type"}


def redact_wage_snapshot(details_json):
    """Entfernt Vergütungsfelder aus einem angelegt/gelöscht-Schnappschuss (JSON-String) --
    Rechtekonzept "Vier Rollen" Etappe 2 (seit 1.4.8, siehe CLAUDE.md): buero_auftrag nutzt
    denselben /api/audit-logs-Endpunkt wie buero_finanzen, darf aber keine Vergütung sehen.
    Rückgabe unverändert, falls details leer/kein JSON-Objekt ist oder keine der drei Wage-
    Spalten enthält (kein unnötiges Neu-Serialisieren)."""
    if not details_json:
        return details_json
    try:
        data = json.loads(details_json)
    except (TypeError, ValueError):
        return details_json
    if not isinstance(data, dict):
        return details_json
    redacted = {k: v for k, v in data.items() if k not in WAGE_FIELD_NAMES}
    if len(redacted) == len(data):
        return details_json
    return json.dumps(redacted, ensure_ascii=False)


# Krankheitssichtbarkeit (siehe CLAUDE.md): buero_auftrag sieht bei einer Abwesenheit nur, DASS
# jemand abwesend war, nicht die Art (absence_type/absence_category) oder den Freitext-Grund
# (notes). "notes" ist bewusst NUR für diese beiden Entitätstypen redigiert -- bei jeder anderen
# Entität (Wartungsvertrag, Projekt, ...) bleibt eine Notiz für buero_auftrag sichtbar, das Feld
# ist dort nicht sensibel; ein Blanket-Filter über ABSENCE_FIELD_NAMES hinweg wäre deshalb falsch.
ABSENCE_ENTITY_TYPES = {"Mitarbeiter-Abwesenheit", "Abwesenheitsantrag"}
ABSENCE_FIELD_NAMES = {"absence_type", "absence_category", "notes"}


def redact_absence_snapshot(entity_type, details_json):
    """Entfernt Art/Kategorie/Notiz aus einem angelegt/gelöscht-Schnappschuss einer Abwesenheit --
    Gegenstück zu redact_wage_snapshot(), aber entitätstyp-gebunden statt global, siehe oben."""
    if entity_type not in ABSENCE_ENTITY_TYPES or not details_json:
        return details_json
    try:
        data = json.loads(details_json)
    except (TypeError, ValueError):
        return details_json
    if not isinstance(data, dict):
        return details_json
    redacted = {k: v for k, v in data.items() if k not in ABSENCE_FIELD_NAMES}
    if len(redacted) == len(data):
        return details_json
    return json.dumps(redacted, ensure_ascii=False)


def audit_rows(db, project_id=None, entity_type=None, entity_id=None, actor=None, limit=250, offset=0):
    """Neueste zuerst; seit 1.8.138 mit Versatz (offset) zum Blättern."""
    stmt = select(AuditLog).order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).limit(min(max(limit,1),1001)).offset(max(offset,0))
    if project_id is not None: stmt = stmt.where(AuditLog.project_id == project_id)
    if entity_type: stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id: stmt = stmt.where(AuditLog.entity_id == str(entity_id))
    if actor: stmt = stmt.where(AuditLog.actor_name.ilike(f"%{actor}%"))  # .contains() waere unter PostgreSQL groß-/kleinschreibungsempfindlich (LIKE statt SQLite-typischem case-insensitivem Verhalten), .ilike() bleibt bei beiden Dialekten gleich
    return db.scalars(stmt).all()
