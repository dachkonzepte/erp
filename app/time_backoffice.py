from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime, timedelta
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

from .grunddaten import einzelzeile
from .models import AppUser, Employee, EmployeePayrollSettings, TimeEntry, TimeTrackingSettings, WorkTimeModel
from .rounding import round_hours
from .time_tracking import employee_name, list_entries, entry_to_dict, pausen_vorschau, tagessumme
from .settings import load_general_settings
from .work_time_models import load_advanced_settings


def load_time_settings(db: Session) -> TimeTrackingSettings:
    """Nur lesen -- die Zeile legt app.grunddaten.anlegen() beim Start an (seit 1.8.42)."""
    return einzelzeile(db, TimeTrackingSettings)


def time_settings_dict(row: TimeTrackingSettings, db: Session | None = None) -> dict:
    advanced = load_advanced_settings(db) if db is not None else None
    return {
        "rounding_minutes": row.rounding_minutes,  # seit 1.9.61 ohne Standardpause
        "allow_manual_entries": row.allow_manual_entries,
        "allow_group_bookings": row.allow_group_bookings,
        "require_order_item": row.require_order_item,
        "require_activity": row.require_activity,
        "datev_target": row.datev_target,
        "datev_wage_type_site": row.datev_wage_type_site,
        "datev_wage_type_travel": row.datev_wage_type_travel,
        "datev_wage_type_workshop": row.datev_wage_type_workshop,
        "datev_wage_type_other": row.datev_wage_type_other,
        "datev_wage_type_weather_winter": row.datev_wage_type_weather_winter,
        "datev_wage_type_weather_summer": row.datev_wage_type_weather_summer,
        "datev_beraternummer": row.datev_beraternummer, "datev_mandantennummer": row.datev_mandantennummer,  # seit 1.9.92
        "datev_personnel_equals_erp_number": bool(advanced.datev_personnel_equals_erp_number) if advanced else False,
        "default_work_time_model_id": advanced.default_work_time_model_id if advanced else None,
        "locked_until": row.locked_until,
        "locked_at": row.locked_at,
        "locked_by_name": _locked_by_name(db, row) if db is not None else None,
    }


def _locked_by_name(db: Session, row: TimeTrackingSettings) -> str | None:
    if row.locked_by_user_id is None:
        return None
    user = db.get(AppUser, row.locked_by_user_id)
    return user.display_name if user else None


def locked_until(db: Session) -> date | None:
    return load_time_settings(db).locked_until


def abschluss_hindernisse(db: Session, bis: date) -> list[dict]:
    """Seit 1.9.91 (Stufe 4, R5a, Punkt 4): was den Abschluss bis einschließlich `bis` sperrt -- jede laufende Zeit mit Tag bis dahin (auch
    eine seit früher offene) und jeder Tag mit unpassender Pause (pausen_vorschau(): neu rechnen würde etwas ändern) ab dem Tag nach dem
    bisherigen Abschluss, ohne bisherigen Abschluss im Monat von `bis`. Je Eintrag art ("laeuft" | "pause"), Mitarbeiter, Tag und ein Text.
    Personalnummer, Lohnart und DATEV-Nummern sperren den Abschluss nicht (sie sperren den DATEV-Export)."""
    vorher = load_time_settings(db).locked_until
    ab = vorher + timedelta(days=1) if vorher is not None else bis.replace(day=1)
    liste: list[dict] = []
    laufend = select(TimeEntry).where(TimeEntry.status == "running", TimeEntry.work_date <= bis).order_by(TimeEntry.work_date, TimeEntry.id)
    for row in db.scalars(laufend).all():
        name = employee_name(row.employee) or f"#{row.employee_id}"
        seit = f"{row.started_at:%d.%m.%Y, %H:%M}" if row.started_at else f"{row.work_date:%d.%m.%Y}"
        liste.append({"art": "laeuft", "employee_id": row.employee_id, "name": name, "tag": row.work_date, "entry_id": row.id,
                      "text": f"{name}: Zeit läuft seit {seit}"})
    for employee_id, tag, stand in unpassende_pausen(db, ab, bis):
        name = employee_name(db.get(Employee, employee_id)) or f"#{employee_id}"
        liste.append({"art": "pause", "employee_id": employee_id, "name": name, "tag": tag, "entry_id": None,
                      "text": f"{name}, {tag:%d.%m.%Y}: Pause abgezogen {stand['abgezogen']} min, nach Zeitregel {stand['noetig']} min"})
    return liste


def unpassende_pausen(db: Session, ab: date, bis: date) -> list[tuple[int, date, dict]]:
    """Seit 1.9.95 (Stufe 4, R5b): die Tage mit unpassender Pause zwischen ab und bis -- je (Mitarbeiter, Tag) mit gebuchten Zeiten der
    Stand aus pausen_vorschau(), wenn neu rechnen etwas ändern würde; nach Tag, dann Mitarbeiter. Eine Liste für den Abschluss
    (abschluss_hindernisse()) und „Prüfen“ der Seite „Zeiten“ (app/zeiten.py)."""
    tage = (select(TimeEntry.employee_id, TimeEntry.work_date)
            .where(TimeEntry.status == "booked", TimeEntry.work_date >= ab, TimeEntry.work_date <= bis).distinct())
    ergebnis = []
    for employee_id, tag in sorted(db.execute(tage).all(), key=lambda x: (x[1], x[0])):
        stand = pausen_vorschau(db, employee_id, tag)
        if not stand["passt"]:
            ergebnis.append((employee_id, tag, stand))
    return ergebnis


def abschluss_meldung(liste: list[dict]) -> str:
    """Der Text der Ablehnung (409): wie viele laufen, wie viele Tage passen nicht, danach jeder Eintrag."""
    laeuft = sum(1 for x in liste if x["art"] == "laeuft")
    pause = len(liste) - laeuft
    teile = ([f"{laeuft} {'Zeit läuft' if laeuft == 1 else 'Zeiten laufen'} noch"] if laeuft else []) + \
            ([f"{pause} {'Tag' if pause == 1 else 'Tage'} mit unpassender Pause"] if pause else [])
    return "Abschließen geht noch nicht: " + ", ".join(teile) + " – " + "; ".join(x["text"] for x in liste) + "."


def set_time_lock(db: Session, new_locked_until: date | None, *, user_id: int | None) -> TimeTrackingSettings:
    """Setzt den Abschluss (None = alles offen). Wer zurücknehmen darf, entscheidet der Router --
    diese Funktion kennt keine Rollen."""
    row = load_time_settings(db)
    row.locked_until = new_locked_until
    row.locked_at = datetime.utcnow()
    row.locked_by_user_id = user_id
    db.commit(); db.refresh(row)
    return row


def update_time_settings(db: Session, payload) -> TimeTrackingSettings:
    row = load_time_settings(db)
    for key in (
        "rounding_minutes", "allow_manual_entries",  # seit 1.9.61 ohne Standardpause
        "allow_group_bookings", "require_order_item", "require_activity",
        "datev_target", "datev_wage_type_site", "datev_wage_type_travel",
        "datev_wage_type_workshop", "datev_wage_type_other",
        "datev_wage_type_weather_winter", "datev_wage_type_weather_summer",
    ):
        setattr(row, key, getattr(payload, key))
    advanced = load_advanced_settings(db)
    advanced.datev_personnel_equals_erp_number = bool(getattr(payload, "datev_personnel_equals_erp_number", False))
    model_id = getattr(payload, "default_work_time_model_id", None)
    # Seit 1.9.14 (Regel 22): "aktiv" nur bei einem neu gewählten Modell prüfen -- ein inzwischen abgeschaltetes Standardmodell bleibt
    # gewählt, sonst ließen sich die Zeitregeln nach dem Abschalten gar nicht mehr speichern.
    if model_id is not None and model_id != advanced.default_work_time_model_id:
        model = db.get(WorkTimeModel, int(model_id))
        if model is None or not model.active:
            raise ValueError("Das gewählte Standard-Arbeitszeitmodell existiert nicht oder ist inaktiv.")
    advanced.default_work_time_model_id = model_id
    db.commit(); db.refresh(row)
    return row


def set_datev_nummern(db: Session, beraternummer: str | None, mandantennummer: str | None) -> TimeTrackingSettings:
    """Seit 1.9.92: Berater- und Mandantennummer (geprüft im Schema DatevNummernUpdate, leer = nicht eingetragen). Wer darf, entscheidet
    der Router (nur Admin)."""
    row = load_time_settings(db)
    row.datev_beraternummer, row.datev_mandantennummer = beraternummer, mandantennummer
    db.commit(); db.refresh(row)
    return row


def get_employee_payroll(db: Session, employee_id: int) -> EmployeePayrollSettings:
    """Lohnstammdaten eines Mitarbeiters, fehlend angelegt -- seit 1.8.84 nur im Schreibweg (set_employee_payroll())."""
    row = db.scalar(select(EmployeePayrollSettings).where(EmployeePayrollSettings.employee_id == employee_id))
    if row is None:
        row = EmployeePayrollSettings(employee_id=employee_id, payroll_export_enabled=True)
        db.add(row); db.commit(); db.refresh(row)
    return row


def load_employee_payroll(db: Session, employee_id: int) -> EmployeePayrollSettings:
    """Lohnstammdaten zum Lesen (seit 1.8.84, Regel 23): die gespeicherten, sonst die Vorgabe (Export an, ohne
    DATEV-Personalnummer), die nicht in die Sitzung geht. Bis 1.8.83 legten Lohnliste, DATEV-Export und Stundenzettel die Zeile
    beim Lesen an und committeten."""
    row = db.scalar(select(EmployeePayrollSettings).where(EmployeePayrollSettings.employee_id == employee_id))
    return row if row is not None else EmployeePayrollSettings(employee_id=employee_id, payroll_export_enabled=True,
                                                                datev_personnel_number=None)


def effective_datev_personnel_number(db: Session, employee: Employee, payroll: EmployeePayrollSettings | None = None) -> str | None:
    advanced = load_advanced_settings(db)
    if advanced.datev_personnel_equals_erp_number:
        return (employee.employee_number or "").strip() or None
    payroll = payroll or load_employee_payroll(db, employee.id)
    return (payroll.datev_personnel_number or "").strip() or None


def payroll_rows(db: Session) -> list[dict]:
    employees = db.scalars(select(Employee).order_by(Employee.active.desc(), Employee.last_name, Employee.first_name)).all()
    advanced = load_advanced_settings(db)
    result=[]
    for emp in employees:
        p=load_employee_payroll(db, emp.id)
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
    advanced=load_advanced_settings(db)
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
        return round_hours(h)
    step=Decimal(rounding_minutes)/Decimal(60)
    if step <= 0: return round_hours(h)
    return round_hours((h/step).quantize(Decimal("1"), rounding=ROUND_HALF_UP)*step)


def backoffice_summary(db: Session, start_date: date, end_date: date, employee_id: int | None = None) -> dict:
    """Kennzahlen und Stunden je Mitarbeiter. Seit 1.9.92 (Stufe 4, R5a, Punkt 5) jede Summe über tagessumme() -- dieselbe wie Stundenzettel
    und DATEV-Export, eine laufende Zeit zählt nicht mit (bis 1.9.91 eigene Summen über alle Zeilen)."""
    rows=list_entries(db, employee_id=employee_id, start_date=start_date, end_date=end_date, limit=None)
    by_employee=defaultdict(list); by_type=defaultdict(list)
    for r in rows:
        by_employee[r.employee_id].append(r); by_type[r.entry_type].append(r)
    employees=[]
    for emp_id,eigene in by_employee.items():
        emp=db.get(Employee,emp_id)
        employees.append({
            "employee_id":emp_id,"employee_name":f"{emp.first_name} {emp.last_name}" if emp else str(emp_id),
            "hours":round_hours(tagessumme(eigene)),"productive_hours":round_hours(tagessumme([r for r in eigene if r.counts_as_productive])),
            "travel_hours":round_hours(tagessumme([r for r in eigene if r.entry_type=="travel"])),"days":len({r.work_date for r in eigene}),
        })
    employees.sort(key=lambda x:x["employee_name"].casefold())
    return {
        "start_date":start_date,"end_date":end_date,"entry_count":len(rows),
        "total_hours":round_hours(tagessumme(rows)),"productive_hours":round_hours(tagessumme([r for r in rows if r.counts_as_productive])),
        "travel_hours":round_hours(tagessumme([r for r in rows if r.entry_type=="travel"])),"employee_count":len(by_employee),
        "by_type":{k:round_hours(tagessumme(v)) for k,v in by_type.items()},"employees":employees,
    }


def _fmt_h(value) -> str:
    return f"{round_hours(value):.2f}".replace(".",",")


def build_timesheet_pdf(db: Session, start_date: date, end_date: date, employee_id: int | None = None) -> bytes:
    type_labels=_entry_type_labels(db)
    rows=list_entries(db, employee_id=employee_id, start_date=start_date, end_date=end_date, limit=None)
    general=load_general_settings(db)
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
        total=tagessumme(entries)  # seit 1.9.92 dieselbe Summe wie Übersicht und DATEV-Export (eine laufende Zeit zählt nicht mit)
        for r in sorted(entries,key=lambda x:(x.work_date,x.started_at or x.created_at,x.id)):
            d=entry_to_dict(r)
            data.append([r.work_date.strftime("%d.%m.%Y"),Paragraph(escape(f"{d.get('project_number') or ''} / {d.get('order_number') or ''}"),small),Paragraph(escape((d.get('order_item_oz') or '')+' '+(d.get('order_item_text') or '')),small),type_labels.get(r.entry_type,r.entry_type),Paragraph(escape(r.activity or ''),small),r.started_at.strftime("%H:%M") if r.started_at else "",r.ended_at.strftime("%H:%M") if r.ended_at else "",str(r.break_minutes or 0),_fmt_h(r.hours)])
        data.append(["","","","","","","","Summe",_fmt_h(total)])
        t=Table(data,colWidths=[21*mm,42*mm,55*mm,24*mm,42*mm,17*mm,17*mm,17*mm,20*mm],repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e8eee9")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7.5),("GRID",(0,0),(-1,-1),.25,colors.HexColor("#cccccc")),("VALIGN",(0,0),(-1,-1),"TOP"),("ALIGN",(-1,1),(-1,-1),"RIGHT"),("FONTNAME",(-2,-1),(-1,-1),"Helvetica-Bold")]))
        story.append(t); story.append(Spacer(1,6*mm)); story.append(Paragraph("Unterschrift Mitarbeiter: ________________________________     Prüfung Backoffice: ________________________________",body))
        if idx < len(grouped)-1: story.append(PageBreak())
    if not grouped: story.append(Paragraph("Keine Zeitbuchungen im gewählten Zeitraum.",body))
    doc.build(story); return buf.getvalue()


def build_time_csv(db: Session, start_date: date, end_date: date, employee_id: int | None = None) -> bytes:
    type_labels=_entry_type_labels(db)
    out=StringIO(newline=""); w=csv.writer(out,delimiter=";",lineterminator="\r\n")
    w.writerow(["Mitarbeiternummer","Mitarbeiter","Datum","Projekt","Auftrag","LV-OZ","Zeitart","Tätigkeit","von","bis","Pause_Min","Stunden","Notiz"])
    for r in list_entries(db,employee_id=employee_id,start_date=start_date,end_date=end_date,limit=None):
        d=entry_to_dict(r); emp=r.employee
        w.writerow([emp.employee_number or "",d["employee_name"],r.work_date.strftime("%d.%m.%Y"),d.get("project_number") or "",d.get("order_number") or "",d.get("order_item_oz") or "",type_labels.get(r.entry_type,r.entry_type),r.activity or "",r.started_at.strftime("%H:%M") if r.started_at else "",r.ended_at.strftime("%H:%M") if r.ended_at else "",r.break_minutes,_fmt_h(r.hours),r.notes or ""])
    return ("\ufeff"+out.getvalue()).encode("utf-8")


def _wage_type(settings: TimeTrackingSettings, entry_type: str) -> str | None:
    mapping={"site":settings.datev_wage_type_site,"travel":settings.datev_wage_type_travel,"workshop":settings.datev_wage_type_workshop,"other":settings.datev_wage_type_other,"weather_winter":settings.datev_wage_type_weather_winter,"weather_summer":settings.datev_wage_type_weather_summer}
    # Bewusst KEIN Rueckfall auf "other" fuer die beiden Schlechtwetter-Zeitarten: Saison-
    # Kurzarbeitergeld (Winter) und tarifliches Ausfallgeld (Sommer) sind eigene Lohnarten,
    # eine stillschweigende Buchung unter "Sonstige Arbeitszeit" waere tariflich falsch.
    # Seit 1.9.92 (Stufe 4, R5a, Punkt 5) ebenso fuer Baustelle, Fahrzeit und Werkstatt: jede Zeitart mit eigener Einstellung braucht ihre
    # Lohnart, sonst lehnt build_datev_export() mit der Liste ab (bis 1.9.91 still unter "Sonstige"). Nur eine Zeitart ohne eigene
    # Einstellung (aus der Liste der Zeitarten) nimmt weiter die Lohnart "Sonstige".
    if entry_type in mapping:
        return mapping[entry_type] or None
    return settings.datev_wage_type_other or None


_ENTRY_TYPE_FALLBACK_LABELS = {
    "site": "Baustellenzeit", "travel": "Fahrzeit", "workshop": "Werkstattzeit",
    "other": "Sonstige Arbeitszeit", "weather_winter": "Schlechtwetter Winter",
    "weather_summer": "Schlechtwetter Sommer",
}


def _entry_type_labels(db: Session) -> dict[str, str]:
    """Bezeichnung je Zeitart für den Stundenzettel/CSV-Export -- ohne diese Auflösung stünde
    dort z. B. der rohe interne Wert "weather_winter" statt "Schlechtwetter Winter".

    Seit 1.8.8 einmal je Lauf statt je Zeile (vorher Abfragen je Buchung)."""
    from .option_settings import get_option_group
    group = get_option_group(db, "time_entry_types")
    configured = {}
    for option in (group.options if group else []):
        configured.setdefault(option.value, option.label)  # doppelter Wert: wie bisher gilt die erste Option
    return {**_ENTRY_TYPE_FALLBACK_LABELS, **configured}


class DatevExportGesperrt(ValueError):
    """Seit 1.9.92 (Stufe 4, R5a, Punkt 5): kein Export -- der Text für die Meldung, dazu die Liste dessen, was fehlt (leer: der Zeitraum
    ist nicht abgeschlossen)."""

    def __init__(self, meldung: str, liste: list[dict] | None = None):
        super().__init__(meldung)
        self.liste = liste or []


def datev_fehlt(db: Session, start_date: date, end_date: date) -> list[dict]:
    """Seit 1.9.92: was dem DATEV-Export für den Zeitraum fehlt -- je Mitarbeiter mit Lohnexport und Buchungen die Personalnummer, je
    gebuchter Zeitart die Lohnart (_wage_type()), Berater- und Mandantennummer. Leer = vollständig. Je Eintrag art und ein Text."""
    settings = load_time_settings(db)
    rows = [r for r in list_entries(db, start_date=start_date, end_date=end_date, limit=None) if r.status == "booked"]
    labels = _entry_type_labels(db)
    payroll = {x.employee_id: x for x in db.scalars(select(EmployeePayrollSettings)).all()}
    liste: list[dict] = []
    gesehen: set = set()
    for r in sorted(rows, key=lambda x: ((x.employee.last_name or "") if x.employee else "", x.employee_id)):
        if r.employee_id in gesehen:
            continue
        gesehen.add(r.employee_id)
        p = payroll.get(r.employee_id) or load_employee_payroll(db, r.employee_id)
        if p.payroll_export_enabled and not effective_datev_personnel_number(db, r.employee, p):
            name = employee_name(r.employee) or f"#{r.employee_id}"
            liste.append({"art": "personalnummer", "employee_id": r.employee_id, "name": name, "text": f"Personalnummer fehlt: {name}"})
    for typ in sorted({r.entry_type for r in rows if (payroll.get(r.employee_id) or load_employee_payroll(db, r.employee_id)).payroll_export_enabled}):
        if not _wage_type(settings, typ):
            liste.append({"art": "lohnart", "zeitart": typ, "text": f"Lohnart fehlt: {labels.get(typ, typ)}"})
    fehlen = [n for n, wert in (("Beraternummer", settings.datev_beraternummer), ("Mandantennummer", settings.datev_mandantennummer)) if not wert]
    if fehlen:
        liste.append({"art": "datev_nummern", "text": (" und ".join(fehlen) + (" fehlen" if len(fehlen) > 1 else " fehlt"))})
    return liste


def _lodas_kopf(settings: TimeTrackingSettings) -> list[str]:
    """Seit 1.9.92: der Kopf einer LODAS-Importdatei -- [Allgemein] mit Berater- und Mandantennummer, [Satzbeschreibung] der Buchungen."""
    return ["[Allgemein]", "Ziel=LODAS", "Version_SST=1.0", f"BeraterNr={settings.datev_beraternummer}",
            f"MandantenNr={settings.datev_mandantennummer}", "Datumsformat=TT/MM/JJJJ", "Feldtrennzeichen=;", "Zahlenkomma=,", "",
            "[Satzbeschreibung]",
            "3;u_lod_bwd_buchung_standard;abrechnung_zeitraum#bwd;bs_wert_butab#bwd;bs_nr#bwd;la_eigene#bwd;pnr#bwd;", ""]


def build_datev_export(db: Session, start_date: date, end_date: date) -> tuple[bytes, str]:
    """Die Lohndaten für DATEV. Seit 1.9.92 (Stufe 4, R5a, Punkt 5, Entscheidung Tobias): nur für einen abgeschlossenen Zeitraum (end_date
    bis zum Abschluss), nur vollständig (datev_fehlt() leer) -- sonst DatevExportGesperrt, keine Datei; bis 1.9.91 fehlten Stunden ohne
    Personalnummer oder Lohnart still (nur als Zahl in einer Kopfzeile). Stunden = die gespeicherten, summiert über tagessumme() wie
    Stundenzettel und Übersicht -- keine zweite Rundung (bis 1.9.91 wurde jede Buchung nach den Zeitregeln erneut gerundet). LODAS: Kopf mit
    Berater- und Mandantennummer, je Personalnummer, Monat und Lohnart eine Zeile (der Satz trägt nur den Monat); Lohn und Gehalt: je
    Personalnummer, Tag, Zeitart und Lohnart."""
    settings = load_time_settings(db)
    lock = settings.locked_until
    if lock is None or end_date > lock:
        stand = f"abgeschlossen ist bis {lock:%d.%m.%Y}" if lock is not None else "noch ist nichts abgeschlossen"
        raise DatevExportGesperrt(f"Der DATEV-Export geht nur für abgeschlossene Zeiträume – {stand}.")
    fehlt = datev_fehlt(db, start_date, end_date)
    if fehlt:
        raise DatevExportGesperrt("Kein DATEV-Export: " + "; ".join(x["text"] for x in fehlt) + ".", fehlt)
    rows = [r for r in list_entries(db, start_date=start_date, end_date=end_date, limit=None) if r.status == "booked"]
    payroll = {x.employee_id: x for x in db.scalars(select(EmployeePayrollSettings)).all()}
    gruppen: dict[tuple, list] = defaultdict(list)
    lodas = settings.datev_target == "lodas"
    for r in rows:
        p = payroll.get(r.employee_id) or load_employee_payroll(db, r.employee_id)
        if not p.payroll_export_enabled:
            continue
        pnr = effective_datev_personnel_number(db, r.employee, p)
        tag = r.work_date.replace(day=1) if lodas else r.work_date
        gruppen[(r.employee_id, pnr, tag, "" if lodas else r.entry_type, _wage_type(settings, r.entry_type))].append(r)
    reihe = sorted(gruppen.items(), key=lambda x: (x[0][2], x[0][1], x[0][4], x[0][3]))
    if lodas:
        lines = _lodas_kopf(settings) + ["[Bewegungsdaten]"]
        for (emp_id, pnr, monat, _, wage), eintraege in reihe:
            # DATEV LODAS Standard-Buchungen: Tabelle 3; Abrechnungszeitraum; Wert; BS 01 Stunden; Lohnart; Personalnummer.
            lines.append(";".join(["3", monat.strftime("01/%m/%Y"), _fmt_h(tagessumme(eintraege)), "01", str(wage), str(pnr)]))
        return ("\r\n".join(lines) + "\r\n").encode("cp1252", errors="replace"), "txt"
    out = StringIO(newline=""); w = csv.writer(out, delimiter=";", lineterminator="\r\n")
    w.writerow(["Personalnummer", "Name", "Kalendertag", "Stundenanzahl", "Lohnart", "Zeitart"])
    for (emp_id, pnr, day, typ, wage), eintraege in reihe:
        emp = db.get(Employee, emp_id); name = f"{emp.first_name} {emp.last_name}" if emp else ""
        w.writerow([pnr, name, day.strftime("%d.%m.%Y"), _fmt_h(tagessumme(eintraege)), wage, typ])
    return ("\ufeff" + out.getvalue()).encode("utf-8"), "csv"
