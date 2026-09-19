from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import (
    CalculationSettings, Employee, EmployeeCompensationSettings,
    LaborRateOverheadSettings, LaborRateSettings,
)
from .employees import annual_gross_wage, effective_cost_allocation
from .recurring_costs import list_costs, overview_summary

ZERO = Decimal("0")
HUNDRED = Decimal("100")
CENT = Decimal("0.01")


def q(value: Decimal | int | float | str) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def get_or_create_labor_rate_settings(db: Session) -> LaborRateSettings:
    settings = db.get(LaborRateSettings, 1)
    if settings is None:
        settings = LaborRateSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def get_or_create_overhead_settings(db: Session, base: LaborRateSettings | None = None) -> LaborRateOverheadSettings:
    row = db.get(LaborRateOverheadSettings, 1)
    if row is None:
        base = base or get_or_create_labor_rate_settings(db)
        # Bestehende "jährliche Gemeinkosten" aus <=0.6.8 werden einmalig als fixe GK in EUR übernommen.
        row = LaborRateOverheadSettings(
            id=1,
            fixed_overhead_mode="eur",
            fixed_overhead_value=Decimal(base.annual_overhead or ZERO),
            variable_overhead_mode="eur",
            variable_overhead_value=ZERO,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def labor_rate_settings_dict(db: Session) -> dict:
    base = get_or_create_labor_rate_settings(db)
    overhead = get_or_create_overhead_settings(db, base)
    return {
        "employer_cost_pct": base.employer_cost_pct,
        "productive_time_pct": base.productive_time_pct,
        "annual_overhead": base.annual_overhead,  # Legacy/API-Kompatibilität
        "fixed_overhead_mode": overhead.fixed_overhead_mode,
        "fixed_overhead_value": overhead.fixed_overhead_value,
        "variable_overhead_mode": overhead.variable_overhead_mode,
        "variable_overhead_value": overhead.variable_overhead_value,
        "target_profit_pct": base.target_profit_pct,
        "weeks_per_year": base.weeks_per_year,
    }


def active_employees(db: Session) -> list[Employee]:
    return db.scalars(
        select(Employee)
        .options(selectinload(Employee.compensation))
        .where(Employee.active.is_(True))
        .order_by(Employee.last_name, Employee.first_name)
    ).all()


def _annual_employee_cost(employee: Employee, weeks_per_year: Decimal, employer_cost_pct: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    gross = Decimal(annual_gross_wage(employee, weeks_per_year) or ZERO)
    employer = gross * employer_cost_pct / HUNDRED
    return gross, employer, gross + employer


def _overhead_amount(mode: str, value: Decimal, direct_labor_annual_cost: Decimal) -> Decimal:
    if mode == "pct":
        return direct_labor_annual_cost * value / HUNDRED
    return value


def calculate_labor_rate(
    db: Session, calc_settings: CalculationSettings, *, overhead_override: dict | None = None,
) -> dict:
    params = get_or_create_labor_rate_settings(db)
    overhead_settings = get_or_create_overhead_settings(db, params)
    weeks = Decimal(params.weeks_per_year or Decimal("52"))
    employer_pct = Decimal(params.employer_cost_pct or ZERO)

    direct_employees: list[Employee] = []
    variable_employees: list[Employee] = []
    for employee in active_employees(db):
        allocation = effective_cost_allocation(db, employee)
        if allocation == "labor_rate":
            direct_employees.append(employee)
        elif allocation == "variable_overhead":
            variable_employees.append(employee)

    paid_hours = ZERO
    gross_wages = ZERO
    for employee in direct_employees:
        annual_hours = Decimal(employee.weekly_hours or ZERO) * weeks
        paid_hours += annual_hours
        gross_wages += Decimal(annual_gross_wage(employee, weeks) or ZERO)

    variable_gross = ZERO
    variable_employer_costs = ZERO
    for employee in variable_employees:
        gross, employer, _ = _annual_employee_cost(employee, weeks, employer_pct)
        variable_gross += gross
        variable_employer_costs += employer
    variable_employee_costs = variable_gross + variable_employer_costs

    current = Decimal(calc_settings.labor_rate or ZERO)
    direct_count = len(direct_employees)
    variable_count = len(variable_employees)

    base_empty = {
        "commercial_employee_count": direct_count,  # Legacy-Bezeichnung
        "direct_employee_count": direct_count,
        "variable_overhead_employee_count": variable_count,
        "weighted_mean_wage": None,
        "annual_paid_hours": q(paid_hours),
        "annual_productive_hours": ZERO,
        "annual_gross_wages": q(gross_wages),
        "annual_employer_costs": ZERO,
        "direct_labor_annual_cost": ZERO,
        "variable_employee_gross_wages": q(variable_gross),
        "variable_employee_employer_costs": q(variable_employer_costs),
        "variable_employee_costs": q(variable_employee_costs),
        "labor_cost_per_productive_hour": None,
        "fixed_overhead_annual": ZERO,
        "fixed_overhead_per_productive_hour": None,
        "manual_variable_overhead_annual": ZERO,
        "variable_overhead_annual": q(variable_employee_costs),
        "variable_overhead_per_productive_hour": None,
        "total_overhead_annual": q(variable_employee_costs),
        "overhead_per_productive_hour": None,
        "self_cost_per_hour": None,
        "target_profit_per_hour": None,
        "suggested_labor_rate": None,
        "current_labor_rate": q(current),
        "difference_to_current": None,
        "can_calculate": False,
    }

    if not direct_employees or paid_hours <= ZERO or gross_wages <= ZERO:
        return {
            **base_empty,
            "note": "Noch keine aktiven gewerblichen Mitarbeiter bzw. sonstigen Mitarbeiter der Kosten-Zuordnung ‚Stundenkostenverrechnungssatz‘ mit gültiger Vergütung und Wochenstunden hinterlegt.",
        }

    mean_wage = gross_wages / paid_hours
    productive_hours = paid_hours * Decimal(params.productive_time_pct or ZERO) / HUNDRED
    employer_costs = gross_wages * employer_pct / HUNDRED
    direct_labor_annual_cost = gross_wages + employer_costs

    if productive_hours <= ZERO:
        return {
            **base_empty,
            "weighted_mean_wage": q(mean_wage),
            "annual_employer_costs": q(employer_costs),
            "direct_labor_annual_cost": q(direct_labor_annual_cost),
            "note": "Die produktive Zeit muss größer als 0 % sein.",
        }

    # overhead_override (Schicht 3, Einspeisung seit 1.5.2) laesst eine Vorschau MIT den
    # Betriebskosten-Vorschlagswerten rechnen, OHNE die persistierten Einstellungen anzufassen --
    # rein in-memory, keine DB-Schreibung. Damit kommt annual_productive_hours (und jede andere
    # Groesse dieser Funktion) fuer "aktuell" und "Vorschlag" aus GENAU DERSELBEN Formel, keine
    # zweite Berechnung an anderer Stelle (siehe recurring_cost_overhead_proposal() unten).
    if overhead_override is not None:
        fixed_mode = overhead_override.get("fixed_overhead_mode", overhead_settings.fixed_overhead_mode)
        fixed_value = Decimal(overhead_override.get("fixed_overhead_value", overhead_settings.fixed_overhead_value) or ZERO)
        variable_mode = overhead_override.get("variable_overhead_mode", overhead_settings.variable_overhead_mode)
        variable_value = Decimal(overhead_override.get("variable_overhead_value", overhead_settings.variable_overhead_value) or ZERO)
    else:
        fixed_mode = overhead_settings.fixed_overhead_mode
        fixed_value = Decimal(overhead_settings.fixed_overhead_value or ZERO)
        variable_mode = overhead_settings.variable_overhead_mode
        variable_value = Decimal(overhead_settings.variable_overhead_value or ZERO)
    fixed_overhead = _overhead_amount(fixed_mode, fixed_value, direct_labor_annual_cost)
    manual_variable_overhead = _overhead_amount(variable_mode, variable_value, direct_labor_annual_cost)
    variable_overhead = manual_variable_overhead + variable_employee_costs
    total_overhead = fixed_overhead + variable_overhead

    labor_cost = direct_labor_annual_cost / productive_hours
    fixed_per_hour = fixed_overhead / productive_hours
    variable_per_hour = variable_overhead / productive_hours
    overhead_per_hour = total_overhead / productive_hours
    self_cost = labor_cost + overhead_per_hour
    profit_per_hour = self_cost * Decimal(params.target_profit_pct or ZERO) / HUNDRED
    suggested = self_cost + profit_per_hour

    return {
        "commercial_employee_count": direct_count,
        "direct_employee_count": direct_count,
        "variable_overhead_employee_count": variable_count,
        "weighted_mean_wage": q(mean_wage),
        "annual_paid_hours": q(paid_hours),
        "annual_productive_hours": q(productive_hours),
        "annual_gross_wages": q(gross_wages),
        "annual_employer_costs": q(employer_costs),
        "direct_labor_annual_cost": q(direct_labor_annual_cost),
        "variable_employee_gross_wages": q(variable_gross),
        "variable_employee_employer_costs": q(variable_employer_costs),
        "variable_employee_costs": q(variable_employee_costs),
        "labor_cost_per_productive_hour": q(labor_cost),
        "fixed_overhead_annual": q(fixed_overhead),
        "fixed_overhead_per_productive_hour": q(fixed_per_hour),
        "manual_variable_overhead_annual": q(manual_variable_overhead),
        "variable_overhead_annual": q(variable_overhead),
        "variable_overhead_per_productive_hour": q(variable_per_hour),
        "total_overhead_annual": q(total_overhead),
        "overhead_per_productive_hour": q(overhead_per_hour),
        "self_cost_per_hour": q(self_cost),
        "target_profit_per_hour": q(profit_per_hour),
        "suggested_labor_rate": q(suggested),
        "current_labor_rate": q(current),
        "difference_to_current": q(suggested - current),
        "can_calculate": True,
        "note": None,
    }


def _overhead_proposal_state(fixed_mode: str, fixed_value: Decimal, variable_mode: str, variable_value: Decimal, result: dict) -> dict:
    """Ein Zustand (aktuell ODER Vorschlag) der Vergleichsansicht -- fixed_overhead_annual/
    manual_variable_overhead_annual/variable_employee_costs/variable_overhead_annual/
    suggested_labor_rate kommen ALLE aus dem calculate_labor_rate()-Ergebnis (result), nie neu
    berechnet. fixed_mode/fixed_value/variable_mode/variable_value sind die rohen, gepflegten
    bzw. vorgeschlagenen Werte (fuer die Anzeige "aktuell: 12 % vom Lohnkostenanteil")."""
    return {
        "fixed_mode": fixed_mode,
        "fixed_value": q(fixed_value),
        "fixed_overhead_annual": result["fixed_overhead_annual"],
        "variable_mode": variable_mode,
        "variable_value": q(variable_value),
        "manual_variable_overhead_annual": result["manual_variable_overhead_annual"],
        "variable_employee_costs": result["variable_employee_costs"],
        "variable_overhead_annual": result["variable_overhead_annual"],
        "suggested_labor_rate": result["suggested_labor_rate"],
        "can_calculate": result["can_calculate"],
    }


def recurring_cost_overhead_proposal(db: Session, calc_settings: CalculationSettings) -> dict:
    """Vergleichsansicht für die Einspeisung des Betriebskosten-Vorschlags in die beiden
    Gemeinkosten-Felder (Fortsetzung von Schicht 3, seit 1.5.2, siehe CLAUDE.md
    "Betriebskosten-Übersicht"). Reine Vorschau, schreibt nichts.

    Ruft calculate_labor_rate() ZWEIMAL auf -- unveraendert ("current") und mit den
    Betriebskosten-Vorschlagswerten temporaer als overhead_override eingesetzt ("proposed") --
    damit annual_productive_hours und die Verrechnungssatz-Formel selbst aus EINER Quelle
    kommen, keine zweite, hier nachgebaute Berechnung (Befund zu Punkt 1). Da
    variable_employee_costs unabhaengig von den Gemeinkosten-Feldern ist (nur von den
    Mitarbeitern mit Kosten-Zuordnung "Variable Gemeinkosten" abhaengt), ist dieser Wert in
    current UND proposed automatisch identisch, ohne dass das hier gesondert sichergestellt
    werden muesste."""
    summary = overview_summary(db)
    overhead = get_or_create_overhead_settings(db)
    proposed_fixed_value = Decimal(summary["annual_fixed_from_costs"])
    proposed_variable_value = Decimal(summary["annual_usage_dependent_from_costs"])

    current_result = calculate_labor_rate(db, calc_settings)
    proposed_result = calculate_labor_rate(
        db, calc_settings,
        overhead_override={
            "fixed_overhead_mode": "eur", "fixed_overhead_value": proposed_fixed_value,
            "variable_overhead_mode": "eur", "variable_overhead_value": proposed_variable_value,
        },
    )

    costs = list_costs(db, include_inactive=False)
    fixed_costs = [
        {"id": c["id"], "label": c["label"], "annual_amount": c["annual_amount"]}
        for c in costs if c["overhead_classification"] == "fix"
    ]
    usage_dependent_costs = [
        {"id": c["id"], "label": c["label"], "annual_amount": c["annual_amount"]}
        for c in costs if c["overhead_classification"] == "auslastungsabhaengig"
    ]

    return {
        "current": _overhead_proposal_state(
            overhead.fixed_overhead_mode, Decimal(overhead.fixed_overhead_value or ZERO),
            overhead.variable_overhead_mode, Decimal(overhead.variable_overhead_value or ZERO),
            current_result,
        ),
        "proposed": _overhead_proposal_state("eur", proposed_fixed_value, "eur", proposed_variable_value, proposed_result),
        "annual_fixed_from_costs": proposed_fixed_value,
        "annual_usage_dependent_from_costs": proposed_variable_value,
        "fixed_costs": fixed_costs,
        "usage_dependent_costs": usage_dependent_costs,
    }


def apply_recurring_cost_overhead_proposal(db: Session) -> None:
    """Schritt 1 der Einspeisung (Muster apply_labor_rate_calculation() als bewusst getrennter
    Schritt 2, unveraendert) -- schreibt AUSSCHLIESSLICH die beiden Gemeinkosten-Felder.
    Erzwingt dabei IMMER Modus "eur" auf beiden (Nutzervorgabe: keine stille Semantikaenderung --
    die Warnung dafuer sitzt im Frontend, vor diesem Aufruf, nicht hier)."""
    summary = overview_summary(db)
    overhead = get_or_create_overhead_settings(db)
    params = get_or_create_labor_rate_settings(db)
    overhead.fixed_overhead_mode = "eur"
    overhead.fixed_overhead_value = Decimal(summary["annual_fixed_from_costs"])
    overhead.variable_overhead_mode = "eur"
    overhead.variable_overhead_value = Decimal(summary["annual_usage_dependent_from_costs"])
    # Legacy-Feld bleibt im Modus "eur" im Gleichschritt mit fixed_overhead_value -- dasselbe
    # Muster wie beim bestehenden PUT /api/labor-rate-settings (app/routers/labor_rate.py).
    params.annual_overhead = overhead.fixed_overhead_value
    db.commit()
