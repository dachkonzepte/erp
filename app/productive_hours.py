"""Produktivstunden-Rechner (seit 1.5.1, Verrechnungssatz-Kreislauf Schicht 3, siehe CLAUDE.md
"Betriebskosten-Übersicht").

Leitet LaborRateSettings.productive_time_pct transparent aus einzelnen Annahmen her (Urlaubstage,
Feiertage, durchschnittliche Krankheitstage, Schlechtwetter, unproduktive Zeit), statt den
Prozentsatz zu raten -- calculate_labor_rate() (app/labor_rate.py) bleibt dabei komplett
unangetastet: es liest weiterhin ausschließlich productive_time_pct selbst, das Ergebnis dieses
Rechners wird erst durch einen bewussten "Übernehmen"-Klick
(apply_productive_hours_to_labor_rate(), Muster apply_labor_rate_calculation()) dorthin
geschrieben, kein Automatismus.

weeks_per_year kommt bewusst aus LaborRateSettings, nicht aus einem eigenen Feld hier -- eine
Quelle für dieselbe Zahl (CLAUDE.md-Lehre aus build_customer_and_meta_block()'s drei
divergierenden Kopien).

Ist-Werte als Orientierung (seit der Nachbesserung "Ist-Werte im Produktivstunden-Rechner",
siehe CLAUDE.md): drei der fünf Annahmen bekommen einen aus echten Daten hergeleiteten
Vergleichswert -- KEINER von ihnen wird automatisch übernommen, die Rechnung selbst nutzt
weiterhin ausschließlich die gepflegten Settings-Felder, keine Doppelzählung.
- Feiertage: public_holidays_suggested (errechnet aus PlanningHoliday, siehe
  app/planning.py::count_workday_holidays() -- übersteuerbar, füllt public_holidays nur vor).
- Schlechtwetter/Krankheit: weather_days_actual()/sick_days_actual() -- rollierende 12 Monate,
  Durchschnitt über die Monteure mit effective_cost_allocation()=="labor_rate" (NICHT
  AppUser.role=="field": die meisten Monteure haben gar kein ERP-Login). Reine Orientierung
  neben der Annahme, nie geschrieben.
- Urlaub und unproduktive Zeit bleiben reine Annahmen ohne Ist-Wert-Vergleich (Urlaub ist
  geplant, nicht gemessen; unproduktive Zeit ist keine für sich buchbare Größe)."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .date_utils import add_months
from .employees import effective_cost_allocation
from .labor_rate import active_employees, get_or_create_labor_rate_settings
from .models import Employee, EmployeeAbsence, ProductiveHoursSettings, TimeEntry
from .planning import count_workday_holidays

ZERO = Decimal("0")
HUNDRED = Decimal("100")
_Q2 = Decimal("0.01")

# Fester Code-Wert, bewusst NICHT konfigurierbar (Muster BILLING_INTERVALS/TAX_RATES) --
# eine einstellbare Anonymitäts-Untergrenze könnte ein Betreiber versehentlich oder bewusst
# herabsetzen und damit genau den Schutz aufheben, den sie garantieren soll. 5 folgt derselben
# Größenordnung wie in vielen Datenschutz-Leitfäden übliche Small-Cell-Suppression-Schwellen.
MIN_EMPLOYEES_FOR_SICK_DAYS_AVERAGE = 5

# Muss dieselben Werte sein wie app/time_tracking.py::NON_PRODUCTIVE_ENTRY_TYPES (dort ohne
# "travel", da Fahrzeit hier keine Rolle spielt) -- absichtlich als eigene, kleine Konstante
# statt eines Imports, weil diese Datei nur genau diese zwei Zeitarten braucht, nicht die
# gesamte Produktivitäts-Klassifikation von time_tracking.py.
WEATHER_ENTRY_TYPES = ("weather_winter", "weather_summer")

ROLLING_WINDOW_MONTHS = 12


def _q(value: Decimal) -> Decimal:
    return value.quantize(_Q2, rounding=ROUND_HALF_UP)


def get_or_create_productive_hours_settings(db: Session) -> ProductiveHoursSettings:
    settings = db.get(ProductiveHoursSettings, 1)
    if settings is None:
        settings = ProductiveHoursSettings(id=1)
        db.add(settings)
        db.commit()
    return settings


def calculate_productive_hours(settings: ProductiveHoursSettings, weeks_per_year: Decimal) -> dict:
    """Bruttojahresstunden - Urlaub - Feiertage - Ø Krankheitstage - Schlechtwetter -
    unproduktive Zeit = produktive Jahresstunden, daraus ein Prozentsatz der
    Bruttojahresstunden -- exakt der Wert, den productive_time_pct heute schon trägt."""
    weekly_hours = settings.weekly_hours
    daily_hours = settings.daily_hours
    annual_gross_hours = weekly_hours * weeks_per_year

    vacation_hours = settings.vacation_days * daily_hours
    holiday_hours = settings.public_holidays * daily_hours
    sick_hours = settings.average_sick_days * daily_hours
    weather_hours = settings.weather_loss_days * daily_hours

    hours_after_absences = annual_gross_hours - vacation_hours - holiday_hours - sick_hours - weather_hours
    if hours_after_absences < ZERO:
        hours_after_absences = ZERO

    unproductive_hours = hours_after_absences * settings.unproductive_time_pct / HUNDRED
    productive_hours = hours_after_absences - unproductive_hours

    productive_time_pct_result = (
        (productive_hours / annual_gross_hours * HUNDRED) if annual_gross_hours > ZERO else ZERO
    )

    return {
        "weekly_hours": weekly_hours,
        "daily_hours": daily_hours,
        "vacation_days": settings.vacation_days,
        "public_holidays": settings.public_holidays,
        "average_sick_days": settings.average_sick_days,
        "weather_loss_days": settings.weather_loss_days,
        "unproductive_time_pct": settings.unproductive_time_pct,
        "weeks_per_year": weeks_per_year,
        "annual_gross_hours": _q(annual_gross_hours),
        "vacation_hours": _q(vacation_hours),
        "holiday_hours": _q(holiday_hours),
        "sick_hours": _q(sick_hours),
        "weather_hours": _q(weather_hours),
        "hours_after_absences": _q(hours_after_absences),
        "unproductive_hours": _q(unproductive_hours),
        "productive_hours": _q(productive_hours),
        "productive_time_pct_result": _q(productive_time_pct_result),
    }


def _rolling_window(today: date | None = None) -> tuple[date, date, list[tuple[int, int]]]:
    """Exakt ROLLING_WINDOW_MONTHS (12) volle Kalendermonate bis einschließlich des laufenden,
    noch unvollständigen Monats -- garantiert eine feste Monatsliste der Länge 12, damit "X von
    12 Monaten" nie mit einer je nach Tagesdatum schwankenden Fensterbreite verwechselt wird
    (ein einfaches "heute minus 365 Tage" hätte je nach Monatslängen mal 12, mal 13 Kalendermonate
    berührt)."""
    today = today or date.today()
    current_month_start = date(today.year, today.month, 1)
    start = add_months(current_month_start, -(ROLLING_WINDOW_MONTHS - 1))
    months = []
    cursor = start
    for _ in range(ROLLING_WINDOW_MONTHS):
        months.append((cursor.year, cursor.month))
        cursor = add_months(cursor, 1)
    return start, today, months


def labor_rate_employees(db: Session) -> list[Employee]:
    """Monteure, die in den Verrechnungssatz eingehen -- dieselbe Personenmenge, die
    calculate_labor_rate() (app/labor_rate.py) bereits als direct_employees behandelt
    (effective_cost_allocation()=="labor_rate" UND aktiv). Bewusst NICHT über AppUser.role
    bestimmt: role sitzt auf dem Login-Konto, nicht auf Employee, und die meisten Monteure haben
    gar kein ERP-Login -- ein Filter auf role=="field" hätte hier praktisch immer 0 Personen
    ergeben (real geprüft: 0 AppUser-Konten mit role='field', aber 7 aktive Mitarbeiter mit
    dieser Kosten-Zuordnung)."""
    return [e for e in active_employees(db) if effective_cost_allocation(db, e) == "labor_rate"]


def _touched_months(dates: list[date]) -> set[tuple[int, int]]:
    return {(d.year, d.month) for d in dates}


def _months_between(start: date, end: date) -> set[tuple[int, int]]:
    months = set()
    cursor = date(start.year, start.month, 1)
    end_marker = date(end.year, end.month, 1)
    while cursor <= end_marker:
        months.add((cursor.year, cursor.month))
        cursor = add_months(cursor, 1)
    return months


def weather_days_actual(db: Session, *, today: date | None = None) -> dict:
    """Ist-Wert Schlechtwetter, rollierende 12 Monate -- reine Orientierung, nie geschrieben
    (siehe Moduldocstring). Summiert TimeEntry.hours über beide Schlechtwetter-Zeitarten für die
    Monteure aus labor_rate_employees(), rechnet über ProductiveHoursSettings.daily_hours in
    Tage um -- DENSELBEN Wert, den calculate_productive_hours() bereits für die Umrechnung der
    Annahme (weather_loss_days) in Stunden verwendet, damit Annahme und Ist-Wert direkt
    vergleichbar bleiben (dieselbe Definition von "ein Tag" auf beiden Seiten). Braucht KEINE
    Anonymitäts-Untergrenze wie sick_days_actual() -- Schlechtwetter ist keine Personalinformation.

    Datengrundlage: Monate im Fenster, in denen mindestens eine gebuchte TimeEntry (beliebiger
    Zeitart) für einen der gezählten Monteure existiert -- signalisiert "die Zeiterfassung war in
    diesem Monat aktiv genutzt", damit ein echtes "kein Schlechtwetter" nicht mit "in diesem
    Monat wurde noch gar nichts erfasst" verwechselt wird."""
    start, end, months = _rolling_window(today)
    employees = labor_rate_employees(db)
    employee_ids = [e.id for e in employees]
    daily_hours = get_or_create_productive_hours_settings(db).daily_hours

    if not employee_ids:
        return {
            "employee_count": 0, "window_months": ROLLING_WINDOW_MONTHS, "data_basis_months": 0,
            "total_hours": None, "daily_hours_used": daily_hours, "average_days": None,
        }

    rows = db.scalars(
        select(TimeEntry.hours).where(
            TimeEntry.employee_id.in_(employee_ids), TimeEntry.entry_type.in_(WEATHER_ENTRY_TYPES),
            TimeEntry.status == "booked", TimeEntry.work_date >= start, TimeEntry.work_date <= end,
        )
    ).all()
    total_hours = sum(rows, ZERO)

    activity_dates = db.scalars(
        select(TimeEntry.work_date).where(
            TimeEntry.employee_id.in_(employee_ids), TimeEntry.status == "booked",
            TimeEntry.work_date >= start, TimeEntry.work_date <= end,
        )
    ).all()
    data_basis_months = len(_touched_months(activity_dates) & set(months))

    average_days = (
        (total_hours / daily_hours / Decimal(len(employee_ids))) if daily_hours > ZERO else None
    )
    return {
        "employee_count": len(employee_ids),
        "window_months": ROLLING_WINDOW_MONTHS,
        "data_basis_months": data_basis_months,
        "total_hours": _q(total_hours),
        "daily_hours_used": daily_hours,
        "average_days": _q(average_days) if average_days is not None else None,
    }


def sick_days_actual(db: Session, *, today: date | None = None) -> dict:
    """Ist-Wert Krankheit, rollierende 12 Monate -- reine Orientierung, nie geschrieben (siehe
    Moduldocstring). Zählt Kalendertage (inkl. Wochenende, dieselbe Konvention wie
    average_sick_days selbst -- calculate_productive_hours() unterscheidet bei keiner der vier
    "Tage"-Annahmen nach Wochentag) aus EmployeeAbsence mit absence_category=="krankheit", auf
    das Fenster zugeschnitten, gemittelt über labor_rate_employees().

    ANONYMITÄTS-UNTERGRENZE (Punkt 3 der Anfrage): bei wenigen Monteuren verrät der Durchschnitt
    eine einzelne Krankheit -- drei Monteure, Durchschnitt "8 Tage", zwei gesund, jeder kann auf
    24 Tage für den Dritten rückrechnen. Unter MIN_EMPLOYEES_FOR_SICK_DAYS_AVERAGE (5) liefert
    diese Funktion deshalb WEDER average_days NOCH total_days -- total_days allein würde die
    Durchschnittsbildung (total/count) für jeden trivial nachrechenbar machen, der die (nicht
    geheime) Monteurzahl kennt. employee_count selbst bleibt sichtbar (Organisationsgröße, keine
    Gesundheitsinformation)."""
    start, end, months = _rolling_window(today)
    employees = labor_rate_employees(db)
    employee_ids = [e.id for e in employees]
    suppressed = len(employee_ids) < MIN_EMPLOYEES_FOR_SICK_DAYS_AVERAGE

    if not employee_ids:
        return {
            "employee_count": 0, "window_months": ROLLING_WINDOW_MONTHS, "data_basis_months": 0,
            "total_days": None, "average_days": None, "suppressed": True,
        }

    sick_rows = db.scalars(
        select(EmployeeAbsence).where(
            EmployeeAbsence.employee_id.in_(employee_ids), EmployeeAbsence.absence_category == "krankheit",
            EmployeeAbsence.start_date <= end, EmployeeAbsence.end_date >= start,
        )
    ).all()
    total_days = sum(
        ((min(row.end_date, end) - max(row.start_date, start)).days + 1 for row in sick_rows), 0,
    )

    # Datengrundlage bewusst über JEDE Abwesenheitsart (nicht nur Krankheit) -- ein Monat, in dem
    # z. B. Urlaub erfasst wurde, aber keine Krankheit, signalisiert "Abwesenheitserfassung war
    # aktiv, es gab schlicht keine Krankheit" statt "keine Daten vorhanden". Nur mit dieser
    # weiteren Abfrage lässt sich das von "noch nichts erfasst" unterscheiden.
    any_absence_rows = db.execute(
        select(EmployeeAbsence.start_date, EmployeeAbsence.end_date).where(
            EmployeeAbsence.employee_id.in_(employee_ids),
            EmployeeAbsence.start_date <= end, EmployeeAbsence.end_date >= start,
        )
    ).all()
    data_basis_months: set[tuple[int, int]] = set()
    for row_start, row_end in any_absence_rows:
        data_basis_months |= _months_between(max(row_start, start), min(row_end, end))
    data_basis_months &= set(months)

    if suppressed:
        return {
            "employee_count": len(employee_ids), "window_months": ROLLING_WINDOW_MONTHS,
            "data_basis_months": len(data_basis_months), "total_days": None, "average_days": None,
            "suppressed": True,
        }

    average_days = Decimal(total_days) / Decimal(len(employee_ids))
    return {
        "employee_count": len(employee_ids),
        "window_months": ROLLING_WINDOW_MONTHS,
        "data_basis_months": len(data_basis_months),
        "total_days": total_days,
        "average_days": _q(average_days),
        "suppressed": False,
    }


def public_holidays_suggestion(db: Session, *, today: date | None = None) -> Decimal:
    """Vorschlag für public_holidays -- errechnet, aber übersteuerbar (Punkt 1 der Anfrage): das
    laufende Kalenderjahr, arbeitstägliche Feiertage aus PlanningHoliday (siehe
    app/planning.py::count_workday_holidays()). Füllt public_holidays beim Laden nur vor,
    schreibt es nie selbst -- update_productive_hours_settings() bleibt der einzige Schreibweg."""
    year = (today or date.today()).year
    return Decimal(count_workday_holidays(db, date(year, 1, 1), date(year, 12, 31)))


def productive_hours_settings_dict(db: Session) -> dict:
    settings = get_or_create_productive_hours_settings(db)
    labor_rate_settings = get_or_create_labor_rate_settings(db)
    result = calculate_productive_hours(settings, labor_rate_settings.weeks_per_year)
    result["current_productive_time_pct"] = labor_rate_settings.productive_time_pct
    result["public_holidays_suggested"] = public_holidays_suggestion(db)
    result["weather_days_actual"] = weather_days_actual(db)
    result["sick_days_actual"] = sick_days_actual(db)
    return result


def update_productive_hours_settings(db: Session, payload: dict) -> dict:
    settings = get_or_create_productive_hours_settings(db)
    settings.weekly_hours = payload["weekly_hours"]
    settings.daily_hours = payload["daily_hours"]
    settings.vacation_days = payload["vacation_days"]
    settings.public_holidays = payload["public_holidays"]
    settings.average_sick_days = payload["average_sick_days"]
    settings.weather_loss_days = payload["weather_loss_days"]
    settings.unproductive_time_pct = payload["unproductive_time_pct"]
    db.commit()
    return productive_hours_settings_dict(db)


def apply_productive_hours_to_labor_rate(db: Session) -> dict:
    """Bewusster zweiter Schritt (Muster apply_labor_rate_calculation()) -- schreibt
    AUSSCHLIESSLICH productive_time_pct, calculate_labor_rate() selbst bleibt unangetastet."""
    result = productive_hours_settings_dict(db)
    labor_rate_settings = get_or_create_labor_rate_settings(db)
    labor_rate_settings.productive_time_pct = result["productive_time_pct_result"]
    db.commit()
    return productive_hours_settings_dict(db)
