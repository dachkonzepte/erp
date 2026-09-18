"""Router: labor_rate

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 4 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from ..calculation import get_or_create_settings
from ..database import get_db
from ..labor_rate import calculate_labor_rate, get_or_create_labor_rate_settings, get_or_create_overhead_settings, labor_rate_settings_dict
from ..models import AppUser
from ..permissions import ROLE_OFFICE_AUFTRAG, require_min_role
from ..schemas import CalculationSettingsOut, LaborRateCalculationOut, LaborRateSettingsOut, LaborRateSettingsUpdate

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Kalkulationsgrundlage aus den Mitarbeiter-
# Stundenlöhnen -- Büro/Admin, für keinen Monteur relevant.
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG))

@router.get("/api/labor-rate-settings", response_model=LaborRateSettingsOut)
def get_labor_rate_settings(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return LaborRateSettingsOut.model_validate(labor_rate_settings_dict(db))


@router.put("/api/labor-rate-settings", response_model=LaborRateSettingsOut)
def update_labor_rate_settings(payload: LaborRateSettingsUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    settings = get_or_create_labor_rate_settings(db)
    overhead = get_or_create_overhead_settings(db, settings)
    settings.employer_cost_pct = payload.employer_cost_pct
    settings.productive_time_pct = payload.productive_time_pct
    settings.target_profit_pct = payload.target_profit_pct
    settings.weeks_per_year = payload.weeks_per_year

    # Alte Clients können weiterhin annual_overhead senden. Fehlen die neuen Felder,
    # wird der alte Wert als fixe Gemeinkosten in EUR übernommen.
    if payload.fixed_overhead_mode is None and payload.fixed_overhead_value is None and payload.annual_overhead is not None:
        overhead.fixed_overhead_mode = "eur"
        overhead.fixed_overhead_value = payload.annual_overhead
        settings.annual_overhead = payload.annual_overhead
    else:
        if payload.fixed_overhead_mode is not None:
            overhead.fixed_overhead_mode = payload.fixed_overhead_mode
        if payload.fixed_overhead_value is not None:
            overhead.fixed_overhead_value = payload.fixed_overhead_value
        if overhead.fixed_overhead_mode == "eur":
            settings.annual_overhead = overhead.fixed_overhead_value

    if payload.variable_overhead_mode is not None:
        overhead.variable_overhead_mode = payload.variable_overhead_mode
    if payload.variable_overhead_value is not None:
        overhead.variable_overhead_value = payload.variable_overhead_value

    db.commit()
    return LaborRateSettingsOut.model_validate(labor_rate_settings_dict(db))


@router.get("/api/labor-rate-calculation", response_model=LaborRateCalculationOut)
def get_labor_rate_calculation(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    return LaborRateCalculationOut.model_validate(calculate_labor_rate(db, get_or_create_settings(db)))


@router.post("/api/labor-rate-calculation/apply", response_model=CalculationSettingsOut)
def apply_labor_rate_calculation(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    calc_settings = get_or_create_settings(db)
    result = calculate_labor_rate(db, calc_settings)
    if not result["can_calculate"] or result["suggested_labor_rate"] is None:
        raise HTTPException(status_code=422, detail=result.get("note") or "Stundenverrechnungssatz kann nicht berechnet werden.")
    calc_settings.labor_rate = result["suggested_labor_rate"]
    db.commit()
    db.refresh(calc_settings)
    return CalculationSettingsOut.model_validate(calc_settings, from_attributes=True)
