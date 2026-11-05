"""Router: time_backoffice

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 15 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.

Rechtekonzept "Vier Rollen" Etappe 2 (seit 1.4.8, siehe CLAUDE.md): von require_admin() auf
require_min_role(ROLE_OFFICE_AUFTRAG) angehoben -- Betreiberbegründung: Zeiten der Kolonnen
korrigieren/Abwesenheiten verwalten gehört zum laufenden, von buero_auftrag geführten Betrieb.
Vor der Anhebung geprüft (wie verlangt), ob dabei Vergütung mitsichtbar wird -- app/time_backoffice.py
gelesen: payroll_rows()/EmployeePayrollSettingsOut tragen nur datev_personnel_number/
payroll_export_enabled (eine Personalnummer-Zuordnung fürs DATEV-Mapping, kein Betrag);
backoffice_summary()/build_timesheet_pdf()/build_time_csv() zeigen ausschließlich Stunden;
build_datev_export()s "Lohnart" ist eine DATEV-Buchungskategorie (Zeitart-zu-Buchungscode-
Zuordnung), kein €-Betrag. Kein einziges €-Vergütungsfeld in dieser Datei -- nichts zu
verengen, die gesamte Datei hebt sich deshalb einheitlich auf buero_auftrag.

Seit 1.9.89 (Stufe 4, R5a, Entscheidung Tobias): die Lohndaten -- Stundenzettel aller, Stundendaten als CSV, DATEV-Export,
Abschließen -- nur für Admin und Büro – Finanzen (require_lohndaten, app/permissions.py); einen Abschluss zurücknehmen oder aufheben
weiter nur der Admin. Die Übersicht (Stunden je Mitarbeiter), Zeitmodelle und Personalnummern bleiben dem Büro.

Seit 1.9.167 (Lohn L1a, Entscheidung Tobias E10): Arbeitszeitmodelle mit Pausenregeln, ihre Zuordnung, Personalnummern, Eintritt, Austritt
und eigene Sollzeiten ändern nur Admin und Büro – Finanzen (require_lohnregeln); Büro – Auftrag liest sie.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..permissions import ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, require_lohndaten, require_lohnregeln, require_min_role, require_personalnummer_freigeben
from ..schemas import ArbeitszeitKalendertagIn, DatevNummernUpdate, LohndateiIn, EmployeePayrollSettingsOut, EmployeePayrollSettingsUpdate, EmployeeTargetHoursCreate, PersonalnummerEingelesenOut, PersonalnummerFreigabeIn, LohnartZuordnungUpdate, EmployeeWorkTimeModelBulkUpdate, EmployeeWorkTimeModelUpdate, TimeTrackingLockUpdate, TimeTrackingSettingsOut, TimeTrackingSettingsUpdate, WorkTimeModelUpsert
from ..dateiauslieferung import datei_antwort
from ..lohndatei import LohndateiVeraendert, abgelegt_dict, abgelegte, lesen as lohndatei_lesen
from ..models import Lohndatei
from ..time_backoffice import DatevExportGesperrt, PersonalnummerGehalten, abschluss_hindernisse, abschluss_meldung, backoffice_summary, lohndatei_erzeugen, set_datev_nummern, build_time_csv, build_timesheet_pdf, eingelesene_personalnummern, load_time_settings, payroll_rows, personalnummer_freigeben, set_employee_payroll, set_time_lock, time_settings_dict, update_time_settings
from ..arbeitszeitkalender import IM_URLAUB, KalendertagUngueltig, aendern as kalendertag_aendern, anlegen as kalendertag_anlegen, eintraege as kalender_eintraege, eintrag_dict as kalendertag_dict
from ..lohnarten import liste as lohnarten_liste, speichern as lohnart_speichern
from ..models import Employee
from ..sollzeit import SollzeitGesperrt, zeile_anlegen as sollzeit_anlegen, zeile_dict, zeile_loeschen as sollzeit_loeschen, zeilen as sollzeit_zeilen
from ..work_time_models import bulk_set_employee_model, delete_model as delete_work_time_model, employee_model_rows, list_models as list_work_time_models, save_model as save_work_time_model, set_employee_model

router = APIRouter()

_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Das Zeiterfassungs-Backoffice ist nur für Büro und Administratoren verfügbar."))
_lohn_dep = Depends(require_lohndaten)  # seit 1.9.89: Admin und Büro – Finanzen
_regeln_dep = Depends(require_lohnregeln)  # seit 1.9.167: Admin und Büro – Finanzen, Büro – Auftrag liest


@router.get("/api/time-backoffice/settings", response_model=TimeTrackingSettingsOut)
def get_time_backoffice_settings(db: Session = Depends(get_db, scope="function"), _role=_role_dep):
    return TimeTrackingSettingsOut.model_validate(time_settings_dict(load_time_settings(db), db))


@router.put("/api/time-backoffice/settings", response_model=TimeTrackingSettingsOut)
def put_time_backoffice_settings(payload: TimeTrackingSettingsUpdate, db: Session = Depends(get_db, scope="function"), _role=_regeln_dep):
    """Rundung, Standardmodell, Lohnarten, „DATEV-Nr. = ERP-Nr.“ -- seit 1.9.167 nur Admin und Büro – Finanzen (E10, bis 1.9.166 jedes Büro)."""
    try:
        row = update_time_settings(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TimeTrackingSettingsOut.model_validate(time_settings_dict(row, db))


@router.put("/api/time-backoffice/datev-nummern", response_model=TimeTrackingSettingsOut)
def put_datev_nummern(payload: DatevNummernUpdate, db: Session = Depends(get_db, scope="function"),
                      _role=Depends(require_min_role(ROLE_ADMIN, message="Berater- und Mandantennummer ändert nur ein Administrator."))):
    """Seit 1.9.92 (Stufe 4, R5a, Punkt 5): Berater- und Mandantennummer für den DATEV-Export -- nur Admin, beide Felder Pflicht (leer =
    nicht eingetragen), Format geprüft (422, schemas.DatevNummernUpdate). Bewusst nicht im allgemeinen Formular der Zeitregeln, das jedes
    Büro speichert."""
    return TimeTrackingSettingsOut.model_validate(time_settings_dict(set_datev_nummern(db, payload.beraternummer, payload.mandantennummer), db))


ABSCHLUSS_NICHT_GANZ = "Ganz aufheben geht nicht – „Abschluss aufheben“ setzt „Abgeschlossen bis“ auf ein früheres Monatsende."
NUR_AUF_MONATSENDE = "Zurückgenommen wird nur auf ein Monatsende."


@router.put("/api/time-backoffice/lock", response_model=TimeTrackingSettingsOut)
def put_time_lock(payload: TimeTrackingLockUpdate, db: Session = Depends(get_db, scope="function"), _role=_lohn_dep):
    """Abschluss der Zeiterfassung (seit 1.7.10). Vorrücken darf seit 1.9.89 Admin und Büro – Finanzen (bis dahin jedes Büro);
    zurücknehmen oder aufheben öffnet bereits abgerechnete Zeiträume wieder und bleibt deshalb dem Admin vorbehalten."""
    current = load_time_settings(db).locked_until
    reopens = current is not None and (payload.locked_until is None or payload.locked_until < current)
    if reopens and _role.role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Einen abgeschlossenen Zeitraum wieder öffnen darf nur ein Administrator.")
    # Seit 1.9.105 (Stufe 4, R5b Nachrunde, Punkt 6): zurückgenommen wird nur auf ein früheres Monatsende, nie ganz (bis 1.9.104 auch auf jeden Tag
    # und ganz) -- auch für den Admin, nach der Rollenprüfung
    if reopens and payload.locked_until is None:
        raise HTTPException(status_code=422, detail=ABSCHLUSS_NICHT_GANZ)
    if reopens and (payload.locked_until + timedelta(days=1)).day != 1:
        raise HTTPException(status_code=422, detail=NUR_AUF_MONATSENDE)
    # Seit 1.9.91 (Stufe 4, R5a, Punkt 4): vorrücken nur ohne laufende Zeiten und ohne Tage mit unpassender Pause bis zum Tag -- sonst 409
    # mit der Liste (auch für den Admin); Personalnummer, Lohnart und DATEV-Nummern sperren nicht
    if payload.locked_until is not None and (current is None or payload.locked_until > current):
        liste = abschluss_hindernisse(db, payload.locked_until)
        if liste:
            return JSONResponse(status_code=409, content={"detail": abschluss_meldung(liste), "liste": jsonable_encoder(liste)})
    row = set_time_lock(db, payload.locked_until, user_id=_role.id)
    return TimeTrackingSettingsOut.model_validate(time_settings_dict(row, db))


@router.get("/api/time-backoffice/work-time-models")
def get_work_time_models(db: Session = Depends(get_db, scope="function"), _role=_role_dep):
    return list_work_time_models(db)


@router.post("/api/time-backoffice/work-time-models")
def create_work_time_model(payload: WorkTimeModelUpsert, db: Session = Depends(get_db, scope="function"), _role=_regeln_dep):
    try:
        row=save_work_time_model(db,model_id=None,name=payload.name,code=payload.code,daily_target_hours=payload.daily_target_hours,valid_from_week=payload.valid_from_week,valid_to_week=payload.valid_to_week,description=payload.description,active=payload.active,sort_order=payload.sort_order,break_rules=[x.model_dump() for x in payload.break_rules])
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return {x["id"]:x for x in list_work_time_models(db)}.get(row.id)


@router.put("/api/time-backoffice/work-time-models/{model_id}")
def put_work_time_model(model_id: int, payload: WorkTimeModelUpsert, db: Session = Depends(get_db, scope="function"), _role=_regeln_dep):
    try:
        row=save_work_time_model(db,model_id=model_id,name=payload.name,code=payload.code,daily_target_hours=payload.daily_target_hours,valid_from_week=payload.valid_from_week,valid_to_week=payload.valid_to_week,description=payload.description,active=payload.active,sort_order=payload.sort_order,break_rules=[x.model_dump() for x in payload.break_rules])
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return {x["id"]:x for x in list_work_time_models(db)}.get(row.id)


@router.delete("/api/time-backoffice/work-time-models/{model_id}")
def remove_work_time_model(model_id: int, db: Session = Depends(get_db, scope="function"), _role=_regeln_dep):
    try: delete_work_time_model(db,model_id)
    except ValueError as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc
    return {"ok":True}


@router.get("/api/time-backoffice/work-time-assignments")
def get_work_time_assignments(db: Session = Depends(get_db, scope="function"), _role=_role_dep):
    return employee_model_rows(db)


@router.put("/api/time-backoffice/work-time-assignments/{employee_id}")
def put_work_time_assignment(employee_id: int, payload: EmployeeWorkTimeModelUpdate, db: Session = Depends(get_db, scope="function"), _role=_regeln_dep):
    try: return set_employee_model(db,employee_id,payload.model_id)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.post("/api/time-backoffice/work-time-assignments/bulk")
def put_work_time_assignments_bulk(payload: EmployeeWorkTimeModelBulkUpdate, db: Session = Depends(get_db, scope="function"), _role=_regeln_dep):
    try: return bulk_set_employee_model(db,payload.employee_ids,payload.model_id)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.get("/api/time-backoffice/payroll-employees", response_model=list[EmployeePayrollSettingsOut])
def get_time_payroll_employees(db: Session = Depends(get_db, scope="function"), _role=_role_dep):
    return [EmployeePayrollSettingsOut.model_validate(x) for x in payroll_rows(db)]


@router.put("/api/time-backoffice/payroll-employees/{employee_id}", response_model=EmployeePayrollSettingsOut)
def put_time_payroll_employee(employee_id: int, payload: EmployeePayrollSettingsUpdate, db: Session = Depends(get_db, scope="function"), _role=_regeln_dep):
    try: row=set_employee_payroll(db,employee_id,payload.model_dump(exclude_unset=True))  # seit 1.9.167 ein Teil-Update (Regel 22)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    return EmployeePayrollSettingsOut.model_validate(row)


@router.get("/api/time-backoffice/personalnummern/eingelesen", response_model=list[PersonalnummerEingelesenOut])
def get_eingelesene_personalnummern(db: Session = Depends(get_db, scope="function"), _role=Depends(require_personalnummer_freigeben)):
    """Seit 1.9.218 (L1a Stufe 7, Punkt 1): die eingelesenen Nummern ohne Person -- nur der Admin (darf_personalnummer_freigeben()), wie das
    Freigeben selbst; Büro – Finanzen 403 und sieht die Liste auf der Seite nicht."""
    return [PersonalnummerEingelesenOut.model_validate(x) for x in eingelesene_personalnummern(db)]


@router.post("/api/time-backoffice/personalnummern/freigeben", response_model=list[EmployeePayrollSettingsOut])
def post_personalnummer_freigeben(payload: PersonalnummerFreigabeIn, db: Session = Depends(get_db, scope="function"),
                                  _role=Depends(require_personalnummer_freigeben)):
    """Seit 1.9.181 (L1a-Korrekturen, Punkt 2): eine gemerkte Personalnummer wieder freigeben -- nur der Admin
    (app/permissions.py::darf_personalnummer_freigeben()), nur solange sie niemand trägt (sonst 409), mit Eintrag im Änderungsprotokoll.
    Antwort: die Lohnstammdaten aller, wie GET /api/time-backoffice/payroll-employees."""
    try:
        personalnummer_freigeben(db, payload.nummer)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PersonalnummerGehalten as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return [EmployeePayrollSettingsOut.model_validate(x) for x in payroll_rows(db)]


@router.get("/api/time-backoffice/lohnarten")
def get_lohnarten(db: Session = Depends(get_db, scope="function"), _role=_role_dep):
    """Seit 1.9.169 (Lohn L1a, Punkt 4): die Zuordnung für den DATEV-Export -- feste Zeilen und je Art, mit dem, was wirkt."""
    return lohnarten_liste(db)


@router.put("/api/time-backoffice/lohnarten")
def put_lohnart(payload: LohnartZuordnungUpdate, db: Session = Depends(get_db, scope="function"), _role=_regeln_dep):
    """Seit 1.9.169: eine Zeile setzen oder leeren (E7, E10: Admin und Büro – Finanzen). Antwort: die ganze Liste."""
    try:
        lohnart_speichern(db, payload.schluessel, payload.kennzeichen, payload.lohnart, payload.monatszeile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return lohnarten_liste(db)


@router.get("/api/time-backoffice/arbeitszeitkalender")
def get_arbeitszeitkalender(db: Session = Depends(get_db, scope="function"), _role=_role_dep):
    """Seit 1.9.175 (L1a-Nachtrag, Punkt 2): die Tage des Arbeitszeitkalenders (Heiligabend …) und die Auswahl „Im Urlaub“."""
    return {"eintraege": [kalendertag_dict(e) for e in kalender_eintraege(db)],
            "im_urlaub": [{"value": k, "label": v} for k, v in IM_URLAUB.items()]}


def _kalender_antwort(db: Session, schreiben) -> dict:
    try:
        schreiben()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KalendertagUngueltig as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return get_arbeitszeitkalender(db)


@router.post("/api/time-backoffice/arbeitszeitkalender")
def post_arbeitszeitkalender(payload: ArbeitszeitKalendertagIn, db: Session = Depends(get_db, scope="function"), _role=_regeln_dep):
    """Seit 1.9.175: einen Tag anlegen -- Admin und Büro – Finanzen (E10, wie die Sollzeit). Antwort: der ganze Kalender."""
    return _kalender_antwort(db, lambda: kalendertag_anlegen(db, payload.model_dump()))


@router.put("/api/time-backoffice/arbeitszeitkalender/{kalendertag_id}")
def put_arbeitszeitkalender(kalendertag_id: int, payload: ArbeitszeitKalendertagIn, db: Session = Depends(get_db, scope="function"), _role=_regeln_dep):
    """Seit 1.9.175: einen Tag ändern (alle Angaben, Pflicht; der Schlüssel bleibt) oder abschalten -- gelöscht wird nicht."""
    return _kalender_antwort(db, lambda: kalendertag_aendern(db, kalendertag_id, payload.model_dump()))


@router.get("/api/time-backoffice/sollzeiten/{employee_id}")
def get_sollzeiten(employee_id: int, db: Session = Depends(get_db, scope="function"), _role=_role_dep):
    """Seit 1.9.167 (Lohn L1a, Punkt 2): die eigenen Sollzeiten einer Person (ab einem Tag, Montag bis Sonntag) -- leer = Tarif."""
    if db.get(Employee, employee_id) is None:
        raise HTTPException(status_code=404, detail="Mitarbeiter wurde nicht gefunden.")
    return [zeile_dict(z) for z in sollzeit_zeilen(db, employee_id)]


@router.post("/api/time-backoffice/sollzeiten/{employee_id}")
def post_sollzeit(employee_id: int, payload: EmployeeTargetHoursCreate, db: Session = Depends(get_db, scope="function"), _role=_regeln_dep):
    """Seit 1.9.167: eigene Sollzeit ab einem Tag (ohne Werte: ab hier wieder Tarif) -- „gültig ab“ nach „Abgeschlossen bis“, sonst 409."""
    try:
        zeile = sollzeit_anlegen(db, employee_id, payload.valid_from, payload.werte)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SollzeitGesperrt as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return zeile_dict(zeile)


@router.delete("/api/time-backoffice/sollzeiten/zeile/{zeile_id}")
def delete_sollzeit(zeile_id: int, db: Session = Depends(get_db, scope="function"), _role=_regeln_dep):
    """Seit 1.9.167: eine eigene Sollzeit löschen -- nur, solange sie keinen abgeschlossenen Zeitraum trifft (sonst 409)."""
    try:
        sollzeit_loeschen(db, zeile_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SollzeitGesperrt as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/api/time-backoffice/summary")
def get_time_backoffice_summary(start_date: date, end_date: date, employee_id: int | None = None, db: Session = Depends(get_db, scope="function"), _role=_role_dep):
    return backoffice_summary(db,start_date,end_date,employee_id)


@router.get("/api/time-backoffice/timesheet.pdf")
def export_time_sheet_pdf(start_date: date, end_date: date, employee_id: int | None = None, db: Session = Depends(get_db, scope="function"), _role=_lohn_dep):
    data=build_timesheet_pdf(db,start_date,end_date,employee_id)
    filename=f"Stundenzettel_{start_date.isoformat()}_{end_date.isoformat()}.pdf"
    return Response(content=data,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="{filename}"'})


@router.get("/api/time-backoffice/timesheet.csv")
def export_time_sheet_csv(start_date: date, end_date: date, employee_id: int | None = None, db: Session = Depends(get_db, scope="function"), _role=_lohn_dep):
    data=build_time_csv(db,start_date,end_date,employee_id)
    filename=f"Stunden_{start_date.isoformat()}_{end_date.isoformat()}.csv"
    return Response(content=data,media_type="text/csv; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="{filename}"'})


# Seit 1.9.226 (Lohn L1b, Punkt 3): jede erzeugte Lohndatei bleibt auf dem Server -- erzeugt wird sie nur noch über POST (kein GET schreibt,
# Regel 23), heruntergeladen aus der Ablage. Bis 1.9.225 GET /api/time-backoffice/datev-export (die Datei ging nur an den Browser). Seit 1.9.92
# nur abgeschlossen und vollständig (409 mit Liste), seit 1.9.224 die Lohndatei für DATEV Lohn und Gehalt, ein ganzer Monat (sonst 422).
@router.post("/api/time-backoffice/lohndateien", status_code=201)
def lohndatei_erzeugen_route(payload: LohndateiIn, db: Session = Depends(get_db, scope="function"), _role=_lohn_dep):
    try:
        row = lohndatei_erzeugen(db, date.fromisoformat(payload.monat + "-01"), user_id=getattr(_role, "id", None),
                                 user_name=getattr(_role, "display_name", None) or getattr(_role, "username", None))
    except DatevExportGesperrt as exc:
        return JSONResponse(status_code=409, content={"detail": str(exc), "liste": jsonable_encoder(exc.liste)})
    return jsonable_encoder(abgelegt_dict(row))


@router.get("/api/time-backoffice/lohndateien")
def lohndateien_liste(monat: str | None = None, db: Session = Depends(get_db, scope="function"), _role=_lohn_dep):
    """Seit 1.9.226: die abgelegten Lohndateien (eines Monats JJJJ-MM), die jüngste zuerst -- ohne die Bytes."""
    erster = None
    if monat is not None:
        try:
            erster = date.fromisoformat(monat + "-01")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Monat im Format JJJJ-MM.") from exc
    return jsonable_encoder([abgelegt_dict(r) for r in abgelegte(db, erster)])


@router.get("/api/time-backoffice/lohndateien/{lohndatei_id}/datei")
def lohndatei_herunterladen(lohndatei_id: int, db: Session = Depends(get_db, scope="function"), _role=_lohn_dep):
    """Seit 1.9.226: genau die abgelegten Bytes, nur mit stimmender Prüfsumme (sonst 409), als Download (Regel 31, datei_antwort())."""
    row = db.get(Lohndatei, lohndatei_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Die Lohndatei wurde nicht gefunden.")
    try:
        inhalt = lohndatei_lesen(row)
    except LohndateiVeraendert as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return datei_antwort(inhalt, row.dateiname, herunterladen=True)
