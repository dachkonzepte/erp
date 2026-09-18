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
divergierenden Kopien). Der spätere Ist-Wert aus TimeEntry.counts_as_productive ist in
CLAUDE.md als künftiger Punkt vorgemerkt, hier bewusst nicht gebaut."""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from .labor_rate import get_or_create_labor_rate_settings
from .models import ProductiveHoursSettings

ZERO = Decimal("0")
HUNDRED = Decimal("100")
_Q2 = Decimal("0.01")


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


def productive_hours_settings_dict(db: Session) -> dict:
    settings = get_or_create_productive_hours_settings(db)
    labor_rate_settings = get_or_create_labor_rate_settings(db)
    result = calculate_productive_hours(settings, labor_rate_settings.weeks_per_year)
    result["current_productive_time_pct"] = labor_rate_settings.productive_time_pct
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
