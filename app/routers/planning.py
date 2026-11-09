"""Router: planning

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 16 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from datetime import date
from fastapi import Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..berlin_time import berlin_today
from ..database import get_db
from ..absence_requests import KalendertagFrage, abwesenheit_loeschen, eintragen
from ..meldungen import KEIN_MITARBEITER
from ..auftragsstatus import einsatz_gesperrt
from ..models import AppUser, Employee, EmployeeAbsence, Order, PlanningHoliday
from ..permissions import (ABWESENHEIT_LOESCHEN_NUR_ADMIN, ABWESENHEIT_LOESCHEN_ROLLEN, ROLE_ADMIN, ROLE_OFFICE_AUFTRAG, ROLE_OFFICE_FINANZEN, darf_abwesenheit_loeschen,
                           darf_abwesenheiten_aller, has_min_role, require_min_role, require_planungsgrundlagen, require_role)
from .absence_requests import antrag_fuer, kalendertag_frage_antwort
from ..auftragsstatus import AuftragGeschlossen
from ..planning import GERMAN_STATES, WENN_LEER, BesetzungUngueltig, _load_slot, EinsatzWirdLeer, KranTerminUngueltig, PlanungsWarnung, create_slot, einsatz_pruefen, kran_termin_pruefen, kran_termin_uebernehmen, delete_slot, einsatz_konflikte, load_planning_settings, load_region_settings, offene_auftraege, planning_board, planning_settings_dict, planning_suggestion, slot_to_dict, sync_school_holidays, update_planning_settings, update_slot
from ..zugehoerigkeit import IdNichtGefunden, PropertyCustomerMismatch
from ..schemas import EmployeeAbsenceCreate, EmployeeAbsenceOut, EmployeeAbsencePlanningOut, PlanningHolidayCreate, PlanningHolidayOut, PlanningSettingsOut, PlanningSettingsUpdate, KranTerminPruefung, KranTerminUebernahme, PlanningSlotCreate, PlanningSlotUpdate, PlanningSuggestionRequest, EinsatzPruefungNeu, EinsatzPruefungAenderung, Rueckgaengig, TagHerausnehmen, TagSetzen, TagUmsetzen, TagVerlaengern, EinsatzVerschieben
from ..auftragsliste import auftragsliste
from ..tag_aktionen import RueckgaengigNichtMoeglich, herausnehmen, rueckgaengig, tag_setzen, umsetzen, verlaengern, verschieben

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Plantafel-Verwaltung (Kapazität, Feiertage,
# Abwesenheiten, Slots) ist Büro-/Admin-Bereich -- geprüft, kein Endpunkt dieser Datei wird von
# einer Monteur-Vorlage aufgerufen (die Monteursansicht liest ihre eigenen Einsätze über den
# unabhängigen, bereits ausgenommenen GET /api/field-view/today).
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))
_abwesenheit_loeschen_dep = Depends(require_role(*ABWESENHEIT_LOESCHEN_ROLLEN, message=ABWESENHEIT_LOESCHEN_NUR_ADMIN))
_grundlagen_dep = Depends(require_planungsgrundlagen)  # seit 1.9.147 (P10): Lesen bleibt _role_dep

# Krankheitssichtbarkeit (siehe CLAUDE.md): buero_auftrag sieht bei jeder Abwesenheit --
# egal wer/wann sie angelegt hat, auch die eigene soeben erstellte -- ausschließlich "abwesend"
# mit Zeitraum, nie Art (absence_type/absence_category) oder Grund (notes). buero_finanzen/admin
# sehen unverändert alles. "Einmal eintragen, nie wieder lesen": buero_auftrag darf beim Anlegen
# weiterhin die echte Art eintippen (z. B. nach einem Telefonanruf), das Ergebnis der eigenen
# Anfrage zeigt sie danach aber ebenso wenig wie jede spätere Abfrage.
ABSENCE_FIELD_NAMES = {"absence_type", "absence_category", "notes"}


def _absence_out_for_role(role: AppUser, data: dict):
    if has_min_role(role, ROLE_OFFICE_FINANZEN):
        return EmployeeAbsenceOut.model_validate(data)
    return EmployeeAbsencePlanningOut.model_validate(data)


def _konflikte_fuer_rolle(konflikte: list[dict], role: AppUser) -> list[dict]:
    """Die Art einer Abwesenheit (seit 1.9.152 auch eines offenen Antrags) im Text eines Konflikts nur für buero_finanzen/admin (Krankheitssichtbarkeit); label_redacted verlässt den Server nie."""
    for konflikt in konflikte:
        if "label_redacted" in konflikt and not has_min_role(role, ROLE_OFFICE_FINANZEN):
            konflikt["label"] = konflikt["label_redacted"]
        konflikt.pop("label_redacted", None)
    return konflikte


def _einsatz_antwort(db: Session, slot, role: AppUser) -> dict:
    """Seit 1.9.143: der gespeicherte Einsatz mit seinen Warnungen und Hinweisen (Feiertag, betriebsfreier Tag, Kapazität speichern ohne Rückfrage und stehen hier)."""
    konflikte = einsatz_konflikte(db, slot)
    warnungen, hinweise = _konflikte_fuer_rolle(konflikte["warnungen"], role), _konflikte_fuer_rolle(konflikte["hinweise"], role)
    return {**slot_to_dict(slot, warnungen + hinweise, db=db), "warnungen": warnungen, "hinweise": hinweise}


def _warnung_antwort(fehler: PlanungsWarnung, role: AppUser) -> JSONResponse:
    """409 mit der Liste -- nichts ist gespeichert, „trotzdem_planen“ im selben Aufruf speichert."""
    return JSONResponse(status_code=409, content={"detail": str(fehler), "warnungen": jsonable_encoder(_konflikte_fuer_rolle(fehler.warnungen, role)),
                                                  "hinweise": jsonable_encoder(_konflikte_fuer_rolle(fehler.hinweise, role))})


def _redact_board_absences(board: dict, role: AppUser) -> dict:
    """Entfernt Art/Grund aus JEDER Stelle, an der GET /api/planning Abwesenheiten einbettet --
    Konflikt-Labels je Slot, Team-/Mitarbeiter-Tageskapazität, die Backoffice-Abwesenheitsliste
    selbst (board["absences"], die tatsächliche Datenquelle von planning.html::renderAbsences()).
    Für buero_finanzen/admin unverändert, nur die internen label_redacted-Hilfsfelder werden
    aufgeräumt, damit sie nicht versehentlich in der Antwort auftauchen."""
    for slot in board.get("slots", []):
        _konflikte_fuer_rolle(slot.get("conflicts", []), role)
    if has_min_role(role, ROLE_OFFICE_FINANZEN):
        return board
    for team_rows in board.get("team_capacity", {}).values():
        for day_row in team_rows.values():
            for entry in day_row.get("absences", []):
                entry.pop("type", None)
    for emp_rows in board.get("employee_capacity", {}).values():
        for day_row in emp_rows.values():
            if day_row.get("absence"):
                day_row["absence"] = "abwesend"
    board["absences"] = [
        {"id": a["id"], "employee_id": a["employee_id"], "employee_name": a["employee_name"],
         "start_date": a["start_date"], "end_date": a["end_date"]}
        for a in board.get("absences", [])
    ]
    # seit 1.9.247: die Zeiträume der Tafel ohne Art (genehmigt und Freistellung „abwesend“, ein Antrag nur „beantragt“)
    for a in board.get("abwesenheiten", []):
        a["art"] = None
    return board


def _tafel_rechte(db: Session, role: AppUser) -> dict:
    """Seit 1.9.146: was die Seite im Dialog „Abwesenheiten“ anbietet -- dieselben Regeln wie die Endpunkte, keine eigene Rollenabfrage in der Vorlage."""
    eigener = db.get(Employee, role.employee_id) if role.employee_id else None
    aller = darf_abwesenheiten_aller(role)
    return {"abwesenheit_fuer_andere": aller, "abwesenheit_loeschen": darf_abwesenheit_loeschen(role),
            "eigener_mitarbeiter": {"id": eigener.id, "name": f"{eigener.first_name} {eigener.last_name}".strip()} if eigener else None,
            "hinweis": None if aller or eigener else KEIN_MITARBEITER}


def _redact_suggestion_absences(suggestion: dict, role: AppUser) -> dict:
    if has_min_role(role, ROLE_OFFICE_FINANZEN):
        return suggestion
    for day_row in suggestion.get("days", []):
        for entry in day_row.get("absent_employees", []):
            entry.pop("type", None)
    return suggestion

@router.get("/api/planning/settings", response_model=PlanningSettingsOut)
def get_planning_capacity_settings(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return planning_settings_dict(load_planning_settings(db), db)


@router.put("/api/planning/settings", response_model=PlanningSettingsOut)
def put_planning_capacity_settings(payload: PlanningSettingsUpdate, db: Session = Depends(get_db, scope="function"), _role: AppUser = _grundlagen_dep):
    row = update_planning_settings(db, **payload.model_dump())
    return planning_settings_dict(row, db)


@router.post("/api/planning/school-holidays/sync")
def sync_planning_school_holidays(start_year: int | None = None, years: int = 3, force: bool = False, db: Session = Depends(get_db, scope="function"), _role: AppUser = _grundlagen_dep):
    region = load_region_settings(db)
    start_year = start_year or berlin_today().year
    years = max(1, min(int(years), 6))
    results = [sync_school_holidays(db, region.federal_state_code, year, force=force) for year in range(start_year, start_year + years)]
    return {"state_code": region.federal_state_code, "state_name": GERMAN_STATES.get(region.federal_state_code), "results": results}


@router.get("/api/planning/holidays", response_model=list[PlanningHolidayOut])
def list_planning_holidays(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    return db.scalars(select(PlanningHoliday).order_by(PlanningHoliday.holiday_date)).all()


@router.post("/api/planning/holidays", response_model=PlanningHolidayOut)
def create_planning_holiday(payload: PlanningHolidayCreate, db: Session = Depends(get_db, scope="function"), _role: AppUser = _grundlagen_dep):
    if db.scalar(select(PlanningHoliday).where(PlanningHoliday.holiday_date == payload.holiday_date)):
        raise HTTPException(status_code=409, detail="Für dieses Datum ist bereits ein Feiertag / betriebsfreier Tag hinterlegt.")
    row=PlanningHoliday(**payload.model_dump()); db.add(row); db.commit(); db.refresh(row); return row


@router.put("/api/planning/holidays/{holiday_id}", response_model=PlanningHolidayOut)
def update_planning_holiday(holiday_id:int, payload:PlanningHolidayCreate, db:Session=Depends(get_db, scope="function"),_role:AppUser=_grundlagen_dep):
    row=db.get(PlanningHoliday,holiday_id)
    if row is None: raise HTTPException(status_code=404,detail="Feiertag / betriebsfreier Tag nicht gefunden.")
    duplicate=db.scalar(select(PlanningHoliday).where(PlanningHoliday.holiday_date==payload.holiday_date, PlanningHoliday.id!=holiday_id))
    if duplicate: raise HTTPException(status_code=409,detail="Für dieses Datum ist bereits ein Feiertag / betriebsfreier Tag hinterlegt.")
    for k,v in payload.model_dump().items(): setattr(row,k,v)
    db.commit(); db.refresh(row); return row


@router.delete("/api/planning/holidays/{holiday_id}")
def delete_planning_holiday(holiday_id:int, db:Session=Depends(get_db, scope="function"),_role:AppUser=_grundlagen_dep):
    row=db.get(PlanningHoliday,holiday_id)
    if row is None: raise HTTPException(status_code=404,detail="Feiertag / betriebsfreier Tag nicht gefunden.")
    db.delete(row); db.commit(); return {"deleted":True}


@router.get("/api/planning/absences", response_model=list[EmployeeAbsenceOut] | list[EmployeeAbsencePlanningOut])
def list_employee_absences(start:date|None=None,end:date|None=None,employee_id:int|None=None,absence_category:str|None=None,db:Session=Depends(get_db, scope="function"),_role:AppUser=_role_dep):
    stmt=select(EmployeeAbsence).options(selectinload(EmployeeAbsence.employee)).order_by(EmployeeAbsence.start_date.desc(),EmployeeAbsence.id.desc())
    if start is not None: stmt=stmt.where(EmployeeAbsence.end_date>=start)
    if end is not None: stmt=stmt.where(EmployeeAbsence.start_date<=end)
    if employee_id is not None: stmt=stmt.where(EmployeeAbsence.employee_id==employee_id)
    if absence_category is not None: stmt=stmt.where(EmployeeAbsence.absence_category==absence_category)
    rows=db.scalars(stmt).all()
    return [_absence_out_for_role(_role, {"id":x.id,"employee_id":x.employee_id,"employee_name":f"{x.employee.first_name} {x.employee.last_name}".strip() if x.employee else None,"absence_type":x.absence_type,"absence_category":x.absence_category,"start_date":x.start_date,"end_date":x.end_date,"notes":x.notes}) for x in rows]


@router.post("/api/planning/absences", response_model=EmployeeAbsenceOut | EmployeeAbsencePlanningOut)
def create_employee_absence(payload:EmployeeAbsenceCreate,db:Session=Depends(get_db, scope="function"),_role:AppUser=_role_dep):
    """„Abwesenheit eintragen“ -- seit 1.9.146 (Stufe 6, R1, Punkt 4) ein Antrag wie unter „Zeiten“: Admin gleich genehmigt, Büro – Finanzen auch für andere, Büro – Auftrag nur für
    sich (403). Bis 1.9.145 trug hier jedes Büro für jede Person jede Art ein, ohne Antrag und ohne Entscheidung (P9)."""
    employee_id=antrag_fuer(_role,payload.employee_id)
    try:
        antrag=eintragen(db,gleich_genehmigt=_role.role==ROLE_ADMIN,employee_id=employee_id,absence_type=payload.absence_type,absence_category=payload.absence_category,start_date=payload.start_date,end_date=payload.end_date,notes=payload.notes,requested_by_user_id=_role.id,kalendertag_urlaub=payload.kalendertag_urlaub)
    except KalendertagFrage as exc:  # seit 1.9.176: Silvester im Urlaub -- 409 mit der Rückfrage, wie unter „Zeiten“
        return kalendertag_frage_antwort(exc)
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    # "Einmal eintragen, nie wieder lesen" (siehe CLAUDE.md "Krankheitssichtbarkeit"): buero_auftrag
    # darf Art/Grund hier weiterhin eintippen (payload bleibt ungefiltert), bekommt die soeben
    # selbst angelegte Zeile in der ANTWORT aber bereits redigiert zurück -- keine Ausnahme "aber
    # ich habe es doch gerade selbst getippt".
    emp=antrag.employee
    return _absence_out_for_role(_role, {"id":antrag.approved_absence_id,"antrag_id":antrag.id,"status":antrag.status,"employee_id":antrag.employee_id,"employee_name":f"{emp.first_name} {emp.last_name}".strip(),"absence_type":antrag.absence_type,"absence_category":antrag.absence_category,"start_date":antrag.start_date,"end_date":antrag.end_date,"notes":antrag.notes})


@router.delete("/api/planning/absences/{absence_id}")
def delete_employee_absence(absence_id:int,db:Session=Depends(get_db, scope="function"),_role:AppUser=_abwesenheit_loeschen_dep):
    """Seit 1.9.146 (P1): der Antrag folgt, nie ein 500; nur der Admin (er entscheidet auch die Anträge)."""
    try:
        abwesenheit_loeschen(db,absence_id,geloescht_von_user_id=_role.id)
    except ValueError as exc:
        raise HTTPException(status_code=404,detail=str(exc)) from exc
    return {"deleted":True}


@router.post("/api/planning/suggestion")
def get_planning_suggestion(payload:PlanningSuggestionRequest,db:Session=Depends(get_db, scope="function"),_role:AppUser=_role_dep):
    try: return _redact_suggestion_absences(planning_suggestion(db,**payload.model_dump()), _role)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc


@router.get("/api/planning/auftraege/{order_id}")
def get_planning_order_state(order_id: int, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.9.155 (L6): warum es für einen Auftrag keinen neuen Einsatz gibt -- für ?auftrag=<id> an einem Auftrag, der nicht mehr in der Auswahl steht."""
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Auftrag wurde nicht gefunden.")
    return {"id": order.id, "order_number": order.order_number, "gesperrt": einsatz_gesperrt(order)}


@router.get("/api/planning")
def get_planning_board(start: date, end: date, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    try:
        # seit 1.9.250 mit dem Betrachter: einen privaten Termin sieht nur sein Besitzer mit Titel
        return {**_redact_board_absences(planning_board(db, start, end, getattr(_role, "id", None)), _role), "rechte": _tafel_rechte(db, _role)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/planning/auftragsliste")
def get_auftragsliste(start: date, end: date, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.9.279 (Stufe 6, R5c, Punkt 1): die Auftragsliste der Woche für die Ansicht „Aufträge“ -- alle offenen Aufträge, eingeplante oben, Stunden
    wie die Akte; eine feste Zahl Abfragen (app/auftragsliste.py). Nur diese Ansicht lädt sie."""
    try:
        return {"start": start, "end": end, "auftraege": auftragsliste(db, start, end)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/planning/auftraege")
def get_planning_orders(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.9.144: die Auswahl im Dialog „Einsatz planen“, erst beim Öffnen des Dialogs -- nur offene Aufträge, nur Nummer und Projekt."""
    return offene_auftraege(db)


@router.post("/api/planning/slots")
def create_planning_slot(payload: PlanningSlotCreate, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    try:
        slot = create_slot(db, **payload.model_dump())
    except PlanungsWarnung as exc:  # seit 1.9.143: Warnungen -- nichts gespeichert, bis „trotzdem_planen“ mitkommt
        return _warnung_antwort(exc, _role)
    except AuftragGeschlossen as exc:  # seit 1.9.124: abgeschlossen oder storniert -- kein neuer Einsatz (409)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PropertyCustomerMismatch as exc:  # seit 1.9.240 (Kranvermietung mit Kunde): Objekt eines anderen Kunden ohne Bestätigung
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IdNichtGefunden as exc:  # seit 1.9.240: unbekannter Kunde bzw. unbekanntes Objekt
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:  # seit 1.9.233 auch BesetzungUngueltig (unbekannte oder inaktive Person, ohne Kolonne ohne Personen)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _einsatz_antwort(db, slot, _role)


def _pruefung_antwort(ergebnis: dict, role: AppUser) -> dict:
    """Seit 1.9.248: Warnungen und Hinweise mit der Fassung je Rolle (wie beim Speichern), Kapazität und Zustände."""
    return {**ergebnis, "warnungen": _konflikte_fuer_rolle(ergebnis["warnungen"], role), "hinweise": _konflikte_fuer_rolle(ergebnis["hinweise"], role)}


@router.post("/api/planning/slots/pruefen")
def pruefe_neuen_einsatz(payload: EinsatzPruefungNeu, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.9.248 (Stufe 6, R4, Punkt 4): der Dialog „Einsatz planen“ prüft, bevor gespeichert wird -- Warnungen und Hinweise, Kapazität mit Rechnung,
    Zustand je Person und Gerät. Dieselben Regeln und Antworten wie POST /api/planning/slots (422, 404, 409), schreibt nichts (rollback)."""
    werte = payload.model_dump()
    weitere = {"weitere_personen": werte.pop("weitere_personen"), "weitere_geraete": werte.pop("weitere_geraete")}
    try:
        ergebnis = einsatz_pruefen(db, None, mit_art=has_min_role(_role, ROLE_OFFICE_FINANZEN), **weitere, **werte)
    except (AuftragGeschlossen, PropertyCustomerMismatch) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IdNichtGefunden as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _pruefung_antwort(ergebnis, _role)


@router.post("/api/planning/slots/{slot_id}/pruefen")
def pruefe_einsatz(slot_id: int, payload: EinsatzPruefungAenderung, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.9.248: der Dialog „Einsatz bearbeiten“ prüft mit den geänderten Feldern (Teil-Update wie PUT), schreibt nichts. Alle Warnungen des Einsatzes,
    auch ohne Änderung."""
    werte = payload.model_dump(exclude_unset=True)
    weitere = {"weitere_personen": werte.pop("weitere_personen", []), "weitere_geraete": werte.pop("weitere_geraete", [])}
    try:
        ergebnis = einsatz_pruefen(db, slot_id, mit_art=has_min_role(_role, ROLE_OFFICE_FINANZEN), **weitere, **werte)
    except BesetzungUngueltig as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404 if "nicht gefunden" in str(exc) else 422, detail=str(exc)) from exc
    return _pruefung_antwort(ergebnis, _role)


@router.post("/api/planning/kran-termine/{event_id}/pruefen")
def pruefe_kran_termin(event_id: int, payload: KranTerminPruefung, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.9.251 (Stufe 6, R4, Punkt 5): der Dialog „Als Kranvermietung übernehmen …“ prüft, bevor übernommen wird -- dieselben Regeln und Antworten
    wie POST …/kranvermietung (404, 409, 422), schreibt nichts."""
    werte = payload.model_dump()
    weitere = {"weitere_personen": werte.pop("weitere_personen"), "weitere_geraete": werte.pop("weitere_geraete")}
    try:
        ergebnis = kran_termin_pruefen(db, event_id, mit_art=has_min_role(_role, ROLE_OFFICE_FINANZEN), **weitere, **werte)
    except (AuftragGeschlossen, KranTerminUngueltig, PropertyCustomerMismatch) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IdNichtGefunden as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404 if str(exc) == "Termin nicht gefunden." else 422, detail=str(exc)) from exc
    return _pruefung_antwort(ergebnis, _role)


@router.post("/api/planning/kran-termine/{event_id}/kranvermietung")
def post_kran_termin_uebernehmen(event_id: int, payload: KranTerminUebernahme, db: Session = Depends(get_db, scope="function"),
                                 _role: AppUser = _role_dep):
    """Seit 1.9.241 (Stufe 6, R3b, Punkt 3): ein Termin am Kran wird eine Kranvermietung (der Knopf kommt mit R4). Antworten wie beim Anlegen eines
    Einsatzes; dazu 404 (Termin unbekannt) und 409 (kein Termin an einem Gerät oder schon übernommen)."""
    try:
        slot = kran_termin_uebernehmen(db, event_id, **payload.model_dump())
    except PlanungsWarnung as exc:
        return _warnung_antwort(exc, _role)
    except (AuftragGeschlossen, KranTerminUngueltig, PropertyCustomerMismatch) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IdNichtGefunden as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        code = 404 if str(exc) == "Termin nicht gefunden." else 422
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return _einsatz_antwort(db, slot, _role)


@router.put("/api/planning/slots/{slot_id}")
def put_planning_slot(slot_id: int, payload: PlanningSlotUpdate, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    try:
        slot = update_slot(db, slot_id, **payload.model_dump(exclude_unset=True))  # seit 1.8.96 Teil-Update (Regel 22)
    except PlanungsWarnung as exc:  # seit 1.9.143, wie beim Anlegen
        return _warnung_antwort(exc, _role)
    except EinsatzWirdLeer as exc:  # seit 1.9.263 (Antwort 3): nichts gespeichert -- „Löschen | Behalten“, dann mit wenn_leer noch einmal
        return _leer_antwort(exc)
    except BesetzungUngueltig as exc:  # seit 1.9.233: die Besetzung geht nicht (auch eine unbekannte Person) -- 422, nicht 404 wie ein fehlender Einsatz
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        code = 404 if "nicht gefunden" in str(exc) else 422
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    if slot is None:  # seit 1.9.263: mit wenn_leer="loeschen" gelöscht
        return {"deleted": True, "id": slot_id}
    return _einsatz_antwort(db, slot, _role)


@router.delete("/api/planning/slots/{slot_id}")
def remove_planning_slot(slot_id: int, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    try:
        prep_id = delete_slot(db, slot_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True, "preparation_id": prep_id}


def _leer_antwort(exc: EinsatzWirdLeer) -> JSONResponse:
    """Seit 1.9.263: 409 mit der Rückfrage „Der Einsatz hat dann niemanden mehr.“ Löschen | Behalten -- nichts gespeichert (seit 1.9.268 eine Stelle für
    PUT und die Tag-Aktionen)."""
    return JSONResponse(status_code=409, content={"detail": str(exc), "rueckfrage": {"art": "einsatz_leer", "text": str(exc), "optionen": list(WENN_LEER)}})


def _tag_antwort(db: Session, ergebnis: dict, role: AppUser) -> dict:
    """Seit 1.9.267: das Ergebnis einer Tag-Aktion -- geprüft: Warnungen und Hinweise in der Fassung je Rolle; gespeichert: dazu der Einsatz wie beim
    Speichern (seit 1.9.268 beim Umsetzen auch der, aus dem sie kam, wenn es ihn noch gibt)."""
    if "warnungen" in ergebnis:
        return {**ergebnis, "warnungen": _konflikte_fuer_rolle(ergebnis["warnungen"], role), "hinweise": _konflikte_fuer_rolle(ergebnis["hinweise"], role)}
    slot = _load_slot(db, ergebnis["slot_id"]) if ergebnis.get("slot_id") else None
    antwort = {**ergebnis, "einsatz": _einsatz_antwort(db, slot, role) if slot is not None else None}
    if ergebnis.get("quelle_id") and ergebnis["quelle_id"] != ergebnis.get("slot_id") and not ergebnis.get("quelle_geloescht"):
        antwort["quelle"] = _einsatz_antwort(db, _load_slot(db, ergebnis["quelle_id"]), role)
    return antwort


def _tag_aktion(db: Session, role: AppUser, aufruf) -> dict | JSONResponse:
    """Seit 1.9.268: eine Tag-Aktion mit den Antworten wie beim Anlegen -- 409 mit warnungen/hinweise (nur neue Warnungen fragen), 409 mit der Rückfrage
    „niemand mehr“, 409 geschlossen, 404 (Auftrag, Einsatz oder Karte unbekannt bzw. fremd), 422; sonst das Ergebnis mit dem Einsatz."""
    try:
        ergebnis = aufruf()
    except PlanungsWarnung as exc:
        return _warnung_antwort(exc, role)
    except EinsatzWirdLeer as exc:
        return _leer_antwort(exc)
    except (AuftragGeschlossen, RueckgaengigNichtMoeglich) as exc:  # seit 1.9.269 auch: der eben angelegte Einsatz wurde seitdem geändert
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IdNichtGefunden as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _tag_antwort(db, ergebnis, role)


@router.post("/api/planning/tag-setzen")
def post_tag_setzen(payload: TagSetzen, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.9.267 (Stufe 6, R5b, Punkt 1): eine Person, eine Kolonne oder ein Gerät für einen Tag an einen Auftrag -- dazu, verlängert oder neu
    (app/tag_aktionen.py). pruefen: schreibt nichts."""
    return _tag_aktion(db, _role, lambda: tag_setzen(db, **payload.model_dump()))


@router.post("/api/planning/slots/{slot_id}/umsetzen")
def post_umsetzen(slot_id: int, payload: TagUmsetzen, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.9.268 (Punkt 2): eine Person oder ein Gerät für diese Tage auf einen anderen Auftrag oder Tag -- in einer Transaktion."""
    return _tag_aktion(db, _role, lambda: umsetzen(db, slot_id=slot_id, **payload.model_dump()))


@router.post("/api/planning/slots/{slot_id}/herausnehmen")
def post_herausnehmen(slot_id: int, payload: TagHerausnehmen, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.9.268 (Punkt 2): eine Person oder ein Gerät für diese Tage oder alle aus dem Einsatz -- Kürzen am Rand, Rückfrage „niemand mehr“."""
    return _tag_aktion(db, _role, lambda: herausnehmen(db, slot_id=slot_id, **payload.model_dump()))


@router.post("/api/planning/slots/{slot_id}/verlaengern")
def post_verlaengern(slot_id: int, payload: TagVerlaengern, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.9.268 (Punkt 2): eine Person oder ein Gerät ab einem ihrer Tage bis zum letzten Tag des Einsatzes -- prüft wie Planen."""
    return _tag_aktion(db, _role, lambda: verlaengern(db, slot_id=slot_id, **payload.model_dump()))


@router.post("/api/planning/slots/{slot_id}/verschieben")
def post_verschieben(slot_id: int, payload: EinsatzVerschieben, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.9.277 (Stufe 6, R5c, Punkt 0b): den ganzen Einsatz ziehen (in „Kolonnen“) -- in Arbeitstagen, fragt bei jeder Warnung des Einsatzes,
    mit Rückgängig. team_id nur, wenn gesendet (Regel 22)."""
    return _tag_aktion(db, _role, lambda: verschieben(db, slot_id=slot_id, **payload.model_dump(exclude_unset=True)))


@router.post("/api/planning/rueckgaengig")
def post_rueckgaengig(payload: Rueckgaengig, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.9.269 (Stufe 6, R5b, Punkt 3): „Rückgängig“ nach einer Tag-Aktion -- die Seite schickt die Umkehrung, die die Aktion zurückgab (kein Speicher
    auf dem Server); ein eben angelegter Einsatz wird nur gelöscht, solange er unverändert ist (409 sonst, Antwort 5)."""
    return _tag_aktion(db, _role, lambda: rueckgaengig(db, schritte=[s.model_dump() for s in payload.schritte]))
