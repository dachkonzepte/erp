"""Router: settings

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 16 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..calculation import get_or_create_settings
from ..company_logo import MAX_UPLOAD_BYTES as LOGO_MAX_UPLOAD_BYTES, delete_logo, logo_path, replace_logo
from ..database import get_db
from ..employees import ensure_default_employee_functions
from ..models import Employee, EmployeeFunction, EmployeeProfile, SettingOption
from ..option_settings import ensure_default_option_groups, get_option_group, option_group_to_dict
from ..schemas import AppearanceSettingsOut, AppearanceSettingsUpdate, CalculationSettingsOut, CalculationSettingsUpdate, EmployeeFunctionCreate, EmployeeFunctionOut, EmployeeFunctionUpdate, GeneralSettingsOut, GeneralSettingsUpdate, NumberPreviewOut, NumberSequenceOut, NumberSequenceUpdate, SettingOptionCreate, SettingOptionGroupOut, SettingOptionOut, SettingOptionUpdate
from ..settings import ensure_default_sequences, get_accent_color, get_or_create_general_settings, preview_number, set_accent_color, update_sequence

router = APIRouter()

@router.get("/api/calculation-settings", response_model=CalculationSettingsOut)
def get_calculation_settings(db: Session = Depends(get_db)):
    return CalculationSettingsOut.model_validate(get_or_create_settings(db), from_attributes=True)


@router.put("/api/calculation-settings", response_model=CalculationSettingsOut)
def update_calculation_settings(payload: CalculationSettingsUpdate, db: Session = Depends(get_db)):
    settings = get_or_create_settings(db)
    settings.labor_rate = payload.labor_rate
    settings.material_markup_pct = payload.material_markup_pct
    settings.overhead_pct = payload.overhead_pct
    settings.risk_profit_pct = payload.risk_profit_pct
    settings.use_source_time_as_minutes = payload.use_source_time_as_minutes
    db.commit()
    db.refresh(settings)
    return CalculationSettingsOut.model_validate(settings, from_attributes=True)


@router.get("/api/settings/option-groups", response_model=list[SettingOptionGroupOut])
def list_setting_option_groups(db: Session = Depends(get_db)):
    return [option_group_to_dict(g) for g in ensure_default_option_groups(db)]


@router.get("/api/settings/option-groups/{group_key}", response_model=SettingOptionGroupOut)
def get_setting_option_group(group_key: str, db: Session = Depends(get_db)):
    ensure_default_option_groups(db)
    group = get_option_group(db, group_key)
    if group is None:
        raise HTTPException(status_code=404, detail="Auswahlliste nicht gefunden.")
    return option_group_to_dict(group)


@router.post("/api/settings/option-groups/{group_key}/options", response_model=SettingOptionOut)
def create_setting_option(group_key: str, payload: SettingOptionCreate, db: Session = Depends(get_db)):
    ensure_default_option_groups(db)
    group = get_option_group(db, group_key)
    if group is None:
        raise HTTPException(status_code=404, detail="Auswahlliste nicht gefunden.")
    exists = db.scalar(select(SettingOption).where(SettingOption.group_id == group.id, SettingOption.label == payload.label.strip()))
    if exists:
        raise HTTPException(status_code=409, detail="Dieser Eintrag ist bereits vorhanden.")
    row = SettingOption(group_id=group.id, **payload.model_dump())
    row.label = row.label.strip()
    if row.is_default:
        for sibling in group.options:
            sibling.is_default = False
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "group_key": group_key, "label": row.label, "value": row.value, "sort_order": row.sort_order, "active": row.active, "is_default": row.is_default}


@router.put("/api/settings/option-groups/{group_key}/options/{option_id}", response_model=SettingOptionOut)
def update_setting_option(group_key: str, option_id: int, payload: SettingOptionUpdate, db: Session = Depends(get_db)):
    ensure_default_option_groups(db)
    group = get_option_group(db, group_key)
    row = db.get(SettingOption, option_id)
    if group is None or row is None or row.group_id != group.id:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.")
    exists = db.scalar(select(SettingOption).where(SettingOption.group_id == group.id, SettingOption.label == payload.label.strip(), SettingOption.id != option_id))
    if exists:
        raise HTTPException(status_code=409, detail="Dieser Eintrag ist bereits vorhanden.")
    for key, value in payload.model_dump().items(): setattr(row, key, value)
    row.label = row.label.strip()
    if row.is_default:
        for sibling in group.options:
            if sibling.id != row.id: sibling.is_default = False
    db.commit(); db.refresh(row)
    return {"id": row.id, "group_key": group_key, "label": row.label, "value": row.value, "sort_order": row.sort_order, "active": row.active, "is_default": row.is_default}


@router.delete("/api/settings/option-groups/{group_key}/options/{option_id}")
def delete_setting_option(group_key: str, option_id: int, db: Session = Depends(get_db)):
    ensure_default_option_groups(db)
    group = get_option_group(db, group_key); row = db.get(SettingOption, option_id)
    if group is None or row is None or row.group_id != group.id:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.")
    db.delete(row); db.commit(); return {"ok": True}


@router.get("/api/settings/employee-functions", response_model=list[EmployeeFunctionOut])
def list_employee_functions(db: Session = Depends(get_db)):
    return ensure_default_employee_functions(db)


@router.post("/api/settings/employee-functions", response_model=EmployeeFunctionOut)
def create_employee_function(payload: EmployeeFunctionCreate, db: Session = Depends(get_db)):
    exists = db.scalar(select(EmployeeFunction).where(EmployeeFunction.name == payload.name.strip()))
    if exists:
        raise HTTPException(status_code=409, detail="Diese Funktion/Tätigkeit ist bereits vorhanden.")
    function = EmployeeFunction(**payload.model_dump())
    function.name = function.name.strip()
    db.add(function)
    db.commit()
    db.refresh(function)
    return function


@router.put("/api/settings/employee-functions/{function_id}", response_model=EmployeeFunctionOut)
def update_employee_function(function_id: int, payload: EmployeeFunctionUpdate, db: Session = Depends(get_db)):
    function = db.get(EmployeeFunction, function_id)
    if function is None:
        raise HTTPException(status_code=404, detail="Funktion/Tätigkeit nicht gefunden.")
    exists = db.scalar(select(EmployeeFunction).where(EmployeeFunction.name == payload.name.strip(), EmployeeFunction.id != function_id))
    if exists:
        raise HTTPException(status_code=409, detail="Diese Funktion/Tätigkeit ist bereits vorhanden.")
    for key, value in payload.model_dump().items():
        setattr(function, key, value)
    function.name = function.name.strip()
    # Bestehende Mitarbeitergruppe und Legacy-Funktion synchron halten.
    profiles = db.scalars(select(EmployeeProfile).where(EmployeeProfile.function_id == function_id)).all()
    for profile in profiles:
        employee = db.get(Employee, profile.employee_id)
        if employee:
            employee.job_title = function.name
            employee.employee_group = function.employee_group
            if function.employee_group == "gewerblich" and (employee.hourly_wage is None or employee.hourly_wage <= 0):
                function.active = False
                db.rollback()
                raise HTTPException(status_code=422, detail="Funktion kann nicht auf 'gewerblich' geändert werden: Mindestens ein zugeordneter Mitarbeiter hat keinen Stundenlohn.")
    db.commit()
    db.refresh(function)
    return function


@router.delete("/api/settings/employee-functions/{function_id}")
def delete_employee_function(function_id: int, db: Session = Depends(get_db)):
    function = db.get(EmployeeFunction, function_id)
    if function is None:
        raise HTTPException(status_code=404, detail="Funktion/Tätigkeit nicht gefunden.")
    assigned = db.scalar(select(EmployeeProfile.id).where(EmployeeProfile.function_id == function_id).limit(1))
    if assigned is not None:
        raise HTTPException(status_code=409, detail="Funktion ist Mitarbeitern zugeordnet. Bitte stattdessen auf 'inaktiv' setzen.")
    db.delete(function)
    db.commit()
    return {"ok": True}


@router.get("/api/settings/general", response_model=GeneralSettingsOut)
def get_general_settings(db: Session = Depends(get_db)):
    return get_or_create_general_settings(db)


@router.put("/api/settings/general", response_model=GeneralSettingsOut)
def put_general_settings(payload: GeneralSettingsUpdate, db: Session = Depends(get_db)):
    settings = get_or_create_general_settings(db)
    for key, value in payload.model_dump().items():
        setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/api/settings/appearance", response_model=AppearanceSettingsOut)
def get_appearance_settings(db: Session = Depends(get_db)):
    return AppearanceSettingsOut(accent_color=get_accent_color(db))


@router.put("/api/settings/appearance", response_model=AppearanceSettingsOut)
def put_appearance_settings(payload: AppearanceSettingsUpdate, db: Session = Depends(get_db)):
    return AppearanceSettingsOut(accent_color=set_accent_color(db, payload.accent_color))


@router.post("/api/settings/general/logo", response_model=GeneralSettingsOut)
async def upload_company_logo(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswählen.")
    if (file.content_type or "").lower() not in ("image/png", "image/jpeg", "image/svg+xml", "image/webp"):
        raise HTTPException(status_code=422, detail="Bitte PNG, JPEG, WebP oder SVG verwenden.")
    data = await file.read(LOGO_MAX_UPLOAD_BYTES + 1)
    if len(data) > LOGO_MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Logo ist größer als 5 MB.")
    settings = get_or_create_general_settings(db)
    settings.logo_filename = replace_logo(settings.logo_filename, file.filename, data)
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/api/settings/general/logo")
def view_company_logo(db: Session = Depends(get_db)):
    settings = get_or_create_general_settings(db)
    if not settings.logo_filename:
        raise HTTPException(status_code=404, detail="Kein Logo hinterlegt.")
    path = logo_path(settings.logo_filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Logo-Datei nicht gefunden.")
    return FileResponse(path)


@router.delete("/api/settings/general/logo", response_model=GeneralSettingsOut)
def remove_company_logo(db: Session = Depends(get_db)):
    settings = get_or_create_general_settings(db)
    delete_logo(settings.logo_filename)
    settings.logo_filename = None
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/api/settings/number-sequences", response_model=list[NumberSequenceOut])
def list_number_sequences(db: Session = Depends(get_db)):
    sequences = ensure_default_sequences(db)
    result = []
    for sequence in sequences:
        result.append(NumberSequenceOut(
            sequence_key=sequence.sequence_key, label=sequence.label,
            format_pattern=sequence.format_pattern, start_value=sequence.start_value,
            next_value=sequence.next_value, reset_yearly=sequence.reset_yearly,
            preview=preview_number(db, sequence.sequence_key),
        ))
    db.commit()
    return result


@router.put("/api/settings/number-sequences/{sequence_key}", response_model=NumberSequenceOut)
def put_number_sequence(sequence_key: str, payload: NumberSequenceUpdate, db: Session = Depends(get_db)):
    try:
        sequence = update_sequence(
            db, sequence_key, format_pattern=payload.format_pattern,
            start_value=payload.start_value, next_value=payload.next_value,
            reset_yearly=payload.reset_yearly,
        )
        preview = preview_number(db, sequence_key)
        db.commit()
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return NumberSequenceOut(
        sequence_key=sequence.sequence_key, label=sequence.label,
        format_pattern=sequence.format_pattern, start_value=sequence.start_value,
        next_value=sequence.next_value, reset_yearly=sequence.reset_yearly, preview=preview,
    )


@router.get("/api/settings/number-sequences/{sequence_key}/preview", response_model=NumberPreviewOut)
def get_number_preview(sequence_key: str, db: Session = Depends(get_db)):
    try:
        value = preview_number(db, sequence_key)
        db.commit()
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return NumberPreviewOut(sequence_key=sequence_key, preview=value)
