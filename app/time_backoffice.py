from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO, StringIO
from html import escape
from sqlalchemy import select
from sqlalchemy.orm import Session

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

from .models import Employee, EmployeePayrollSettings, TimeEntry, TimeTrackingSettings, WorkTimeModel
from .time_tracking import list_entries, entry_to_dict
from .settings import get_or_create_general_settings
from .work_time_models import get_or_create_advanced_settings


def get_or_create_time_settings(db: Session) -> TimeTrackingSettings:
    row = db.get(TimeTrackingSettings, 1)
    if row is None:
        row = TimeTrackingSettings(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def time_settings_dict(row: TimeTrackingSettings, db: Session | None = None) -> dict:
    advanced = get_or_create_advanced_settings(db) if db is not None else None
    return {
        "rounding_minutes": row.rounding_minutes,
        "default_break_minutes": row.default_break_minutes,
        "allow_manual_entries": row.allow_manual_entries,
        "allow_group_bookings": row.allow_group_bookings,
        "require_order_item": row.require_order_item,
        "require_activity": row.require_activity,
        "datev_target": row.datev_target,
        "datev_wage_type_site": row.datev_wage_type_site,
        "datev_wage_type_travel": row.datev_wage_type_travel,
        "datev_wage_type_workshop": row.datev_wage_type_workshop,
        "datev_wage_type_other": row.datev_wage_type_other,
        "datev_personnel_equals_erp_number": bool(advanced.datev_personnel_equals_erp_number) if advanced else False,
        "default_work_time_model_id": advanced.default_work_time_model_id if advanced else None,
    }


def update_time_settings(db: Session, payload) -> TimeTrackingSettings:
    row = get_or_create_time_settings(db)
    for key in (
        "rounding_minutes", "default_break_minutes", "allow_manual_entries",
        "allow_group_bookings", "require_order_item", "require_activity",
        "datev_target", "datev_wage_type_site", "datev_wage_type_travel",
        "datev_wage_type_workshop", "datev_wage_type_other",
    ):
        setattr(row, key, getattr(payload, key))
    advanced = get_or_create_advanced_settings(db)
    advanced.datev_personnel_equals_erp_number = bool(getattr(payload, "datev_personnel_equals_erp_number", False))
    model_id = getattr(payload, "default_work_time_model_id", None)
    if model_id is not None:
        model = db.get(WorkTimeModel, int(model_id))
        if model is None or not model.active:
            raise ValueError("Das gewählte Standard-Arbeitszeitmodell existiert nicht oder ist inaktiv.")
    advanced.default_work_time_model_id = model_id
    db.commit(); db.refresh(row)
    return row


def get_employee_payroll(db: Session, employee_id: int) -> EmployeePayrollSettings:
    row = db.scalar(select(EmployeePayrollSettings).where(EmployeePayrollSettings.employee_id == employee_id))
    if row is None:
        row = EmployeePayrollSettings(employee_id=employee_id, payroll_export_enabled=True)
        db.add(row); db.commit(); db.refresh(row)
    return row


def effective_datev_personnel_number(db: Session, employee: Employee, payroll: EmployeePayrollSettings | None = None) -> str | None:
    advanced = get_or_create_advanced_settings(db)
    if advanced.datev_personnel_equals_erp_number:
        return (employee.employee_number or "").strip() or None
    payroll = payroll or get_employee_payroll(db, employee.id)
    return (payroll.datev_personnel_number or "").strip() or None


def payroll_rows(db: Session) -> list[dict]:
    employees = db.scalars(select(Employee).order_by(Employee.active.desc(), Employee.last_name, Employee.first_name)).all()
    advanced = get_or_create_advanced_settings(db)
    result=[]
    for emp in employees:
        p=get_employee_payroll(db, emp.id)
        result.append({
            "employee_id": emp.id,
            "employee_name": f"{emp.first_name} {emp.last_name}".strip(),
            "employee_number": emp.employee_number,
            "datev_personnel_number": effective_datev_personnel_number(db, emp, p),
            "datev_personnel_number_stored": p.datev_personnel_number,
            "datev_personnel_equals_erp_number": bool(advanced.datev_personnel_equals_erp_number),
            "payroll_export_enabled": p.payroll_export_enabled,
        })
    return result


def set_employee_payroll(db: Session, employee_id: int, payload) -> dict:
    emp=db.get(Employee, employee_id)
    if emp is None: raise ValueError("Mitarbeiter wurde nicht gefunden.")
    advanced=get_or_create_advanced_settings(db)
    value=((emp.employee_number or "").strip() or None) if advanced.datev_personnel_equals_erp_number else ((payload.datev_personnel_number or "").strip() or None)
    if advanced.datev_personnel_equals_erp_number and not value and payload.payroll_export_enabled:
        raise ValueError("ERP-Mitarbeiternummer fehlt. Bei aktivierter Gleichsetzung wird sie als DATEV-Personalnummer benötigt.")
    if value:
        duplicate=db.scalar(select(EmployeePayrollSettings).where(
            EmployeePayrollSettings.datev_personnel_number==value,
            EmployeePayrollSettings.employee_id!=employee_id,
        ))
        if duplicate is not None: raise ValueError("Diese DATEV-Personalnummer ist bereits vergeben.")
    row=get_employee_payroll(db, employee_id)
    row.datev_personnel_number=value
    row.payroll_export_enabled=bool(payload.payroll_export_enabled)
    db.commit(); db.refresh(row)
    return {
        "employee_id": emp.id,
        "employee_name": f"{emp.first_name} {emp.last_name}".strip(),
        "employee_number": emp.employee_number,
        "datev_personnel_number": effective_datev_personnel_number(db, emp, row),
        "payroll_export_enabled": row.payroll_export_enabled,
    }


def rounded_hours(hours: Decimal, rounding_minutes: int) -> Decimal:
    h=Decimal(hours or 0)
    if not rounding_minutes:
        return h.quantize(Decimal("0.01"))
    step=Decimal(rounding_minutes)/Decimal(60)
    if step <= 0: return h.quantize(Decimal("0.01"))
    return ((h/step).quantize(Decimal("1"), rounding=ROUND_HALF_UP)*step).quantize(Decimal("0.01"))


def backoffice_summary(db: Session, start_date: date, end_date: date, employee_id: int | None = None) -> dict:
    rows=list_entries(db, employee_id=employee_id, start_date=start_date, end_date=end_date, limit=2000)
    total=Decimal("0"); productive=Decimal("0"); travel=Decimal("0")
    by_employee=defaultdict(lambda:{"hours":Decimal("0"),"productive":Decimal("0"),"travel":Decimal("0"),"days":set()})
    by_type=defaultdict(Decimal)
    for r in rows:
        h=Decimal(r.hours or 0); total+=h; by_type[r.entry_type]+=h
        if r.counts_as_productive: productive+=h
        if r.entry_type=="travel": travel+=h
        b=by_employee[r.employee_id]; b["hours"]+=h; b["days"].add(r.work_date)
        if r.counts_as_productive: b["productive"]+=h
        if r.entry_type=="travel": b["travel"]+=h
    employees=[]
    for emp_id,vals in by_employee.items():
        emp=db.get(Employee,emp_id)
        employees.append({
            "employee_id":emp_id,"employee_name":f"{emp.first_name} {emp.last_name}" if emp else str(emp_id),
            "hours":vals["hours"].quantize(Decimal("0.01")),"productive_hours":vals["productive"].quantize(Decimal("0.01")),
            "travel_hours":vals["travel"].quantize(Decimal("0.01")),"days":len(vals["days"]),
        })
    employees.sort(key=lambda x:x["employee_name"].casefold())
    return {
        "start_date":start_date,"end_date":end_date,"entry_count":len(rows),
        "total_hours":total.quantize(Decimal("0.01")),"productive_hours":productive.quantize(Decimal("0.01")),
        "travel_hours":travel.quantize(Decimal("0.01")),"employee_count":len(by_employee),
        "by_type":{k:v.quantize(Decimal("0.01")) for k,v in by_type.items()},"employees":employees,
    }


def _fmt_h(value) -> str:
    return f"{Decimal(value or 0):.2f}".replace(".",",")


def build_timesheet_pdf(db: Session, start_date: date, end_date: date, employee_id: int | None = None) -> bytes:
    rows=list_entries(db, employee_id=employee_id, start_date=start_date, end_date=end_date, limit=2000)
    general=get_or_create_general_settings(db)
    grouped=defaultdict(list)
    for r in rows: grouped[r.employee_id].append(r)
    if employee_id and employee_id not in grouped:
        emp=db.get(Employee,employee_id)
        if emp: grouped[employee_id]=[]
    buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=landscape(A4),leftMargin=10*mm,rightMargin=10*mm,topMargin=11*mm,bottomMargin=12*mm,title="Stundenzettel")
    styles=getSampleStyleSheet(); body=ParagraphStyle("BodyDE",parent=styles["BodyText"],fontSize=8,leading=10); small=ParagraphStyle("Small",parent=body,fontSize=7,leading=9)
    story=[]
    for idx,(emp_id,entries) in enumerate(sorted(grouped.items(), key=lambda x: ((db.get(Employee,x[0]).last_name if db.get(Employee,x[0]) else ""),x[0]))):
        emp=db.get(Employee,emp_id); name=f"{emp.first_name} {emp.last_name}" if emp else str(emp_id)
        story.append(Paragraph(f"<b>{escape(general.company_name)}</b> – Stundenzettel", styles["Heading2"]))
        story.append(Paragraph(f"Mitarbeiter: <b>{escape(name)}</b> &nbsp;&nbsp; Zeitraum: {start_date.strftime('%d.%m.%Y')}–{end_date.strftime('%d.%m.%Y')}",body)); story.append(Spacer(1,3*mm))
        data=[["Datum","Projekt / Auftrag","LV-Position","Zeitart","Tätigkeit","von","bis","Pause","Stunden"]]
        total=Decimal("0")
        for r in sorted(entries,key=lambda x:(x.work_date,x.started_at or x.created_at,x.id)):
            d=entry_to_dict(r); total+=Decimal(r.hours or 0)
            data.append([r.work_date.strftime("%d.%m.%Y"),Paragraph(escape(f"{d.get('project_number') or ''} / {d.get('order_number') or ''}"),small),Paragraph(escape((d.get('order_item_oz') or '')+' '+(d.get('order_item_text') or '')),small),r.entry_type,Paragraph(escape(r.activity or ''),small),r.started_at.strftime("%H:%M") if r.started_at else "",r.ended_at.strftime("%H:%M") if r.ended_at else "",str(r.break_minutes or 0),_fmt_h(r.hours)])
        data.append(["","","","","","","","Summe",_fmt_h(total)])
        t=Table(data,colWidths=[21*mm,42*mm,55*mm,24*mm,42*mm,17*mm,17*mm,17*mm,20*mm],repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e8eee9")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7.5),("GRID",(0,0),(-1,-1),.25,colors.HexColor("#cccccc")),("VALIGN",(0,0),(-1,-1),"TOP"),("ALIGN",(-1,1),(-1,-1),"RIGHT"),("FONTNAME",(-2,-1),(-1,-1),"Helvetica-Bold")]))
        story.append(t); story.append(Spacer(1,6*mm)); story.append(Paragraph("Unterschrift Mitarbeiter: ________________________________     Prüfung Backoffice: ________________________________",body))
        if idx < len(grouped)-1: story.append(PageBreak())
    if not grouped: story.append(Paragraph("Keine Zeitbuchungen im gewählten Zeitraum.",body))
    doc.build(story); return buf.getvalue()


def build_time_csv(db: Session, start_date: date, end_date: date, employee_id: int | None = None) -> bytes:
    out=StringIO(newline=""); w=csv.writer(out,delimiter=";",lineterminator="\r\n")
    w.writerow(["Mitarbeiternummer","Mitarbeiter","Datum","Projekt","Auftrag","LV-OZ","Zeitart","Tätigkeit","von","bis","Pause_Min","Stunden","Notiz"])
    for r in list_entries(db,employee_id=employee_id,start_date=start_date,end_date=end_date,limit=2000):
        d=entry_to_dict(r); emp=r.employee
        w.writerow([emp.employee_number or "",d["employee_name"],r.work_date.strftime("%d.%m.%Y"),d.get("project_number") or "",d.get("order_number") or "",d.get("order_item_oz") or "",r.entry_type,r.activity or "",r.started_at.strftime("%H:%M") if r.started_at else "",r.ended_at.strftime("%H:%M") if r.ended_at else "",r.break_minutes,_fmt_h(r.hours),r.notes or ""])
    return ("\ufeff"+out.getvalue()).encode("utf-8")


def _wage_type(settings: TimeTrackingSettings, entry_type: str) -> str | None:
    mapping={"site":settings.datev_wage_type_site,"travel":settings.datev_wage_type_travel,"workshop":settings.datev_wage_type_workshop,"other":settings.datev_wage_type_other}
    return mapping.get(entry_type) or settings.datev_wage_type_other


def build_datev_export(db: Session, start_date: date, end_date: date) -> tuple[bytes,str,list[str]]:
    settings=get_or_create_time_settings(db)
    rows=list_entries(db,start_date=start_date,end_date=end_date,limit=2000)
    aggregated=defaultdict(Decimal); warnings=[]
    payroll={x.employee_id:x for x in db.scalars(select(EmployeePayrollSettings)).all()}
    for r in rows:
        p=payroll.get(r.employee_id) or get_employee_payroll(db,r.employee_id)
        if not p.payroll_export_enabled: continue
        pnr=effective_datev_personnel_number(db, r.employee, p)
        if not pnr:
            name=f"{r.employee.first_name} {r.employee.last_name}"; warnings.append(f"{name}: DATEV-Personalnummer fehlt")
            continue
        wage=_wage_type(settings,r.entry_type)
        if not wage:
            warnings.append(f"Zeitart {r.entry_type}: DATEV-Lohnart fehlt")
            continue
        key=(r.employee_id,pnr,r.work_date,r.entry_type,wage)
        aggregated[key]+=rounded_hours(Decimal(r.hours or 0),settings.rounding_minutes)
    if settings.datev_target=="lodas":
        lines=["[Bewegungsdaten]"]
        for (emp_id,pnr,day,typ,wage),hours in sorted(aggregated.items(),key=lambda x:(x[0][2],x[0][1],x[0][3])):
            # DATEV LODAS Standard-Buchungen: Tabelle 3; Buchungszeitraum; Wert; BS 01 Stunden; Lohnart; Personalnummer.
            lines.append(";".join(["3",day.strftime("01/%m/%Y"),_fmt_h(hours),"01",str(wage),str(pnr)]))
        return ("\r\n".join(lines)+"\r\n").encode("cp1252",errors="replace"),"txt",sorted(set(warnings))
    out=StringIO(newline=""); w=csv.writer(out,delimiter=";",lineterminator="\r\n")
    w.writerow(["Personalnummer","Name","Kalendertag","Stundenanzahl","Lohnart","Zeitart"])
    for (emp_id,pnr,day,typ,wage),hours in sorted(aggregated.items(),key=lambda x:(x[0][2],x[0][1],x[0][3])):
        emp=db.get(Employee,emp_id); name=f"{emp.first_name} {emp.last_name}" if emp else ""
        w.writerow([pnr,name,day.strftime("%d.%m.%Y"),_fmt_h(hours),wage,typ])
    return ("\ufeff"+out.getvalue()).encode("utf-8"),"csv",sorted(set(warnings))
