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
)

_actor_id = contextvars.ContextVar("audit_actor_id", default=None)
_actor_name = contextvars.ContextVar("audit_actor_name", default="System")
_request_path = contextvars.ContextVar("audit_request_path", default=None)
_request_method = contextvars.ContextVar("audit_request_method", default=None)

EXCLUDED_FIELDS = {"created_at", "updated_at", "last_login_at", "password_hash"}
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
}

EXTENSION_TYPES = (CustomerProfile, ProjectProfile, EmployeeProfile, EmployeeRoleSettings, EmployeeCompensationSettings, EmployeeCostAllocationSettings, QuoteDocumentMeta, QuoteItemLayout, QuoteEmployeeAssignment)

AUDITED_TYPES = (
    Customer, CustomerProfile, CustomerExtraInfo, Property, Inquiry, Project, ProjectProfile, ProjectDocument, Supplier, OperationalResource, Team, TeamEmployee, TeamResource,
    Quote, QuoteItem, QuoteItemCalculation, QuoteItemMaterialCalculation, QuoteDocumentMeta, QuoteSection,
    QuoteItemLayout, QuoteEmployeeAssignment, Order, OrderRevision, WorkPreparation, WorkPreparationEmployee, WorkPreparationTask, WorkPreparationMaterial, WorkPreparationTeamAssignment, WorkPreparationTeamEmployee, WorkPreparationTeamResource, WorkPreparationMaterialSupplier, WorkPreparationDeliveryNote, WorkPreparationMaterialDeliveryNote, PlanningSlot, PlanningSettings, PlanningRegionSettings, PlanningHoliday, EmployeeAbsence, EmployeeAbsenceRequest, PlanningSlotCapacity, TimeEntry, TimeEntryGroup, TimeEntryGroupMember, TimeTrackingSettings, EmployeePayrollSettings, TimeBackofficeAdvancedSettings, WorkTimeModel, WorkTimeBreakRule, EmployeeWorkTimeModel, Employee, EmployeeCompensationSettings, EmployeeCostAllocationSettings, EmployeeProfile, EmployeeRoleSettings, EmployeePlanningSettings, EmployeeFunction,
    GeneralSettings, CalculationSettings, LaborRateSettings, LaborRateOverheadSettings, NumberSequence, SettingOptionGroup, SettingOption,
    AppUser, ServiceCalculation, MaterialCalculationOverride,
)

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
    "planned_start":"Geplanter Baustart","planned_end":"Geplante Fertigstellung","site_notes":"Baustellenhinweise","material_notes":"Materialhinweise","planned_hours":"Geplante Stunden","role":"Rolle","priority":"Priorität","due_date":"Fälligkeit","assigned_employee_id":"Zuständig","planned_quantity":"Planmenge","supplier":"Lieferant","supplier_id":"Lieferant","resource_type":"Ressourcentyp","identifier":"Kennzeichen / Seriennummer","team_number":"Teamnummer","resource_number":"Ressourcennummer","supplier_number":"Lieferantennummer","delivery_note_number":"Lieferscheinnummer","start_date":"Planungsbeginn","end_date":"Planungsende","team_assignment_id":"Kolonne / Team","daily_work_hours":"Tägliche Arbeitszeit","default_travel_hours_per_employee_day":"Standard-Anfahrtszeit","federal_state_code":"Bundesland","auto_public_holidays":"Feiertage automatisch","show_school_holidays":"Schulferien anzeigen","holiday_date":"Feiertag / betriebsfreier Tag","absence_type":"Abwesenheitsart","decision":"Entscheidung","review_notes":"Freigabe-Notiz","reviewed_by_user_id":"Geprüft von","approved_absence_id":"Genehmigte Abwesenheit","team_id":"Team","travel_hours_per_employee_day":"Anfahrtszeit pro MA/Tag","work_date":"Arbeitstag","entry_type":"Zeitart","hours":"Ist-Stunden","break_minutes":"Pause (Min.)","activity":"Tätigkeit","order_item_id":"LV-Position","counts_as_productive":"Produktive Zeit","datev_personnel_number":"DATEV-Personalnummer","payroll_export_enabled":"DATEV-Lohnexport aktiv","datev_personnel_equals_erp_number":"DATEV-Nr. entspricht ERP-Nr.","default_work_time_model_id":"Standard-Arbeitszeitmodell","daily_target_hours":"Soll-Arbeitszeit pro Tag","threshold_hours":"Pausenschwelle","model_id":"Arbeitszeitmodell",
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
    return {k: _text(getattr(obj, k, None)) for k in _columns(obj) if getattr(obj, k, None) not in (None, "")}


def _normalize(session, obj):
    """Gibt (entity_type, entity_id, label, project_id) zurück und fasst Erweiterungstabellen fachlich zusammen."""
    if isinstance(obj, CustomerProfile):
        c = session.get(Customer, obj.customer_id); return "Kunde", str(obj.customer_id), _entity_label(c), None
    if isinstance(obj, ProjectProfile):
        p = session.get(Project, obj.project_id); return "Projekt", str(obj.project_id), _entity_label(p), obj.project_id
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
        emp = session.get(Employee, obj.employee_id)
        return "Mitarbeiter-Abwesenheit", str(obj.id), f"{_entity_label(emp) or 'Mitarbeiter'} · {obj.absence_type}", None
    if isinstance(obj, EmployeeAbsenceRequest):
        emp = session.get(Employee, obj.employee_id)
        return "Abwesenheitsantrag", str(obj.id), f"{_entity_label(emp) or 'Mitarbeiter'} · {obj.absence_type} · {obj.start_date}–{obj.end_date}", None
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
    if isinstance(obj, Order): return "Auftrag", str(obj.id), _entity_label(obj), obj.project_id
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
    if isinstance(obj, OperationalResource): return f"{obj.resource_number or ''} {obj.name}".strip()
    if isinstance(obj, Team): return f"{obj.team_number or ''} {obj.name}".strip()
    if isinstance(obj, QuoteItem): return f"{obj.gaeb_oz or obj.position_number or ''} {obj.short_text}".strip()[:255]
    if isinstance(obj, Employee): return f"{obj.employee_number or ''} {obj.first_name} {obj.last_name}".strip()
    if isinstance(obj, TimeEntry): return f"{obj.work_date} · {obj.entry_type} · {obj.hours} h"
    if isinstance(obj, EmployeeFunction): return obj.name
    if isinstance(obj, NumberSequence): return obj.label
    if isinstance(obj, SettingOption): return obj.label
    if isinstance(obj, AppUser): return obj.display_name
    return getattr(obj, "name", None) or getattr(obj, "title", None) or type(obj).__name__


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
            if key in EXCLUDED_FIELDS or key == "id": continue
            hist = state.attrs[key].history
            if not hist.has_changes(): continue
            old = hist.deleted[0] if hist.deleted else None
            new = hist.added[0] if hist.added else getattr(obj, key, None)
            if _text(old) == _text(new): continue
            pending.append(_record("geändert", obj, key, old, new))
    for obj in list(session.deleted):
        if isinstance(obj, AuditLog) or not isinstance(obj, AUDITED_TYPES): continue
        pending.append(_record("gelöscht", obj, details=json.dumps(_snapshot(obj), ensure_ascii=False)))


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


def audit_rows(db, project_id=None, entity_type=None, entity_id=None, actor=None, limit=250):
    stmt = select(AuditLog).order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).limit(min(max(limit,1),1000))
    if project_id is not None: stmt = stmt.where(AuditLog.project_id == project_id)
    if entity_type: stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id: stmt = stmt.where(AuditLog.entity_id == str(entity_id))
    if actor: stmt = stmt.where(AuditLog.actor_name.contains(actor))
    return db.scalars(stmt).all()
