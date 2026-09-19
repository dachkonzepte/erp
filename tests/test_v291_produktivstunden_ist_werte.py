"""Ist-Werte im Produktivstunden-Rechner (Nachbesserung, siehe CLAUDE.md
"Produktivstunden-Rechner"/app/productive_hours.py-Moduldocstring) -- als Orientierung neben
den gepflegten Annahmen, nichts wird automatisch übernommen.

Deckt die vier Punkte der Anfrage ab:
(1) Feiertage: count_workday_holidays() (app/planning.py) -- nur Feiertage auf einem laut
    PlanningSettings konfigurierten Arbeitstag, übersteuerbarer Vorschlag (public_holidays_
    suggested), schreibt public_holidays nie selbst.
(2) Schlechtwetter/Krankheit als Ist-Wert, rollierende 12 Monate, Durchschnitt über
    labor_rate_employees() (effective_cost_allocation()=="labor_rate", NICHT AppUser.role) --
    Schlechtwetter über ProductiveHoursSettings.daily_hours in Tage umgerechnet (derselbe Wert,
    der auch die Annahme in Stunden umrechnet), Krankheit als reine Kalendertage.
(3) Anonymitäts-Untergrenze: sick_days_actual() liefert unter MIN_EMPLOYEES_FOR_SICK_DAYS_AVERAGE
    (5) weder average_days noch total_days -- rekursiver Schlüssel-Scan auf dem Endpunkt.
(4) Datengrundlage-Anzeige (data_basis_months von window_months) ist Pflicht und ehrlich, auch
    wenn sie "0 von 12" zeigt."""

from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.employees import set_cost_allocation
from app.models import Employee, EmployeeAbsence, PlanningHoliday
from app.planning import count_workday_holidays, get_or_create_planning_settings
from app.productive_hours import (
    MIN_EMPLOYEES_FOR_SICK_DAYS_AVERAGE,
    get_or_create_productive_hours_settings,
    labor_rate_employees,
    productive_hours_settings_dict,
    public_holidays_suggestion,
    sick_days_actual,
    weather_days_actual,
)
from app.routers.labor_rate import router as labor_rate_router
from app.time_tracking import create_manual_entry
from tests.test_v133_invoices import make_order_with_item

ALL_ROLES = ("field", "buero_auftrag", "buero_finanzen", "admin")
TODAY = date(2026, 9, 19)


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _recursive_keys(value, keys=None):
    if keys is None:
        keys = set()
    if isinstance(value, dict):
        for k, v in value.items():
            keys.add(k)
            _recursive_keys(v, keys)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _recursive_keys(item, keys)
    return keys


def _make_employee(db, *, number, gewerblich=True, active=True):
    emp = Employee(
        employee_number=number, first_name="Max", last_name=f"Monteur{number}",
        employee_group="gewerblich" if gewerblich else "kaufmaennisch",
        hourly_wage=Decimal("20"), weekly_hours=Decimal("40"), active=active,
    )
    db.add(emp)
    db.commit()
    return emp


def _make_absence(db, employee_id, *, category, start, end, absence_type="Urlaub"):
    row = EmployeeAbsence(
        employee_id=employee_id, absence_type=absence_type, absence_category=category,
        start_date=start, end_date=end,
    )
    db.add(row)
    db.commit()
    return row


# --- Punkt 1: Feiertage aus der Plantafel ---

def test_count_workday_holidays_excludes_weekend_and_inactive():
    db = db_session()
    db.add_all([
        PlanningHoliday(holiday_date=date(2026, 1, 1), name="Neujahr (Do)"),  # Donnerstag -> zaehlt
        PlanningHoliday(holiday_date=date(2026, 5, 1), name="Tag der Arbeit (Fr)"),  # Freitag -> zaehlt
        PlanningHoliday(holiday_date=date(2026, 12, 25), name="1. Weihnachtstag (Fr)"),  # zaehlt
        PlanningHoliday(holiday_date=date(2026, 12, 26), name="2. Weihnachtstag (Sa)"),  # Samstag -> NICHT
        PlanningHoliday(holiday_date=date(2026, 6, 4), name="Fronleichnam NRW (Do)", active=False),  # inaktiv
    ])
    db.commit()
    assert count_workday_holidays(db, date(2026, 1, 1), date(2026, 12, 31)) == 3


def test_count_workday_holidays_respects_configured_working_weekdays():
    """Nutzt dieselbe Arbeitstage-Definition wie die Plantafel (PlanningSettings), nicht
    hartcodiertes Mo-Fr -- ein Betrieb mit Samstagsarbeit zaehlt einen Samstagsfeiertag mit."""
    db = db_session()
    settings = get_or_create_planning_settings(db)
    settings.saturday = True
    db.commit()
    db.add(PlanningHoliday(holiday_date=date(2026, 12, 26), name="2. Weihnachtstag (Sa)"))
    db.commit()
    assert count_workday_holidays(db, date(2026, 12, 1), date(2026, 12, 31)) == 1


def test_count_workday_holidays_respects_date_range_boundaries():
    db = db_session()
    db.add(PlanningHoliday(holiday_date=date(2027, 1, 1), name="Neujahr naechstes Jahr"))
    db.commit()
    assert count_workday_holidays(db, date(2026, 1, 1), date(2026, 12, 31)) == 0
    assert count_workday_holidays(db, date(2027, 1, 1), date(2027, 12, 31)) == 1


def test_public_holidays_suggestion_uses_current_calendar_year():
    db = db_session()
    db.add_all([
        PlanningHoliday(holiday_date=date(2026, 1, 1), name="Neujahr (Do)"),
        PlanningHoliday(holiday_date=date(2025, 12, 25), name="Weihnachten letztes Jahr (Do)"),
    ])
    db.commit()
    assert public_holidays_suggestion(db, today=date(2026, 6, 1)) == Decimal("1")


def test_public_holidays_suggestion_is_zero_without_any_configured_holidays():
    """Reale Datenlage heute: 0 PlanningHoliday-Zeilen -- der Vorschlag muss das ehrlich zeigen,
    nicht auf einen erfundenen Standardwert zurueckfallen."""
    db = db_session()
    assert public_holidays_suggestion(db, today=TODAY) == Decimal("0")


# --- labor_rate_employees(): NICHT ueber AppUser.role, sondern effective_cost_allocation() ---

def test_labor_rate_employees_uses_cost_allocation_not_app_user_role():
    db = db_session()
    gewerblich = _make_employee(db, number="M-1", gewerblich=True)
    kaufmaennisch = _make_employee(db, number="M-2", gewerblich=False)
    excluded_explicitly = _make_employee(db, number="M-3", gewerblich=True)
    set_cost_allocation(db, excluded_explicitly, "variable_overhead")
    db.commit()
    inactive = _make_employee(db, number="M-4", gewerblich=True, active=False)

    result_ids = {e.id for e in labor_rate_employees(db)}
    assert result_ids == {gewerblich.id}
    assert kaufmaennisch.id not in result_ids
    assert excluded_explicitly.id not in result_ids
    assert inactive.id not in result_ids


# --- Punkt 2/4: Schlechtwetter-Ist-Wert -- Umrechnung ueber ProductiveHoursSettings.daily_hours ---

def test_weather_days_actual_converts_hours_via_the_existing_daily_hours_setting():
    db = db_session()
    settings = get_or_create_productive_hours_settings(db)
    settings.daily_hours = Decimal("8.00")
    db.commit()
    emp1 = _make_employee(db, number="M-1")
    emp2 = _make_employee(db, number="M-2")
    order, _item = make_order_with_item(db)
    # 40h Schlechtwetter fuer emp1, verteilt auf beide Zeitarten, innerhalb der letzten 12 Monate.
    create_manual_entry(db, employee_id=emp1.id, order_id=order.id, work_date=date(2026, 1, 15),
                         hours=Decimal("24"), entry_type="weather_winter")
    create_manual_entry(db, employee_id=emp1.id, order_id=order.id, work_date=date(2026, 6, 10),
                         hours=Decimal("16"), entry_type="weather_summer")
    # 0h fuer emp2 -- zaehlt trotzdem im Nenner mit (Durchschnitt ueber ALLE labor_rate-Monteure).
    result = weather_days_actual(db, today=TODAY)
    assert result["employee_count"] == 2
    assert result["total_hours"] == Decimal("40.00")
    assert result["daily_hours_used"] == Decimal("8.00")
    # 40h / 8h je Tag / 2 Monteure = 2,5 Tage im Durchschnitt.
    assert result["average_days"] == Decimal("2.50")


def test_weather_days_actual_excludes_entries_outside_the_rolling_window():
    db = db_session()
    emp = _make_employee(db, number="M-1")
    order, _item = make_order_with_item(db)
    create_manual_entry(db, employee_id=emp.id, order_id=order.id, work_date=date(2024, 1, 15),
                         hours=Decimal("40"), entry_type="weather_winter")
    result = weather_days_actual(db, today=TODAY)
    assert result["total_hours"] == Decimal("0.00")
    assert result["average_days"] == Decimal("0.00")


def test_weather_days_actual_excludes_non_booked_entries():
    db = db_session()
    from app.models import TimeEntry

    emp = _make_employee(db, number="M-1")
    order, _item = make_order_with_item(db)
    running = TimeEntry(
        employee_id=emp.id, project_id=order.project_id, order_id=order.id,
        work_date=date(2026, 1, 15), entry_type="weather_winter", hours=Decimal("40"),
        status="running",
    )
    db.add(running)
    db.commit()
    result = weather_days_actual(db, today=TODAY)
    assert result["total_hours"] == Decimal("0.00")


def test_weather_days_actual_with_no_labor_rate_employees():
    db = db_session()
    result = weather_days_actual(db, today=TODAY)
    assert result["employee_count"] == 0
    assert result["average_days"] is None


# --- Punkt 3: Anonymitaets-Untergrenze bei Krankheit ---

def test_sick_days_actual_is_suppressed_below_five_employees():
    """Drei Monteure, einer 24 Tage krank -- Durchschnitt "8 Tage" waere fuer Kollegen
    rueckrechenbar. Weder average_days NOCH total_days duerfen dann geliefert werden."""
    db = db_session()
    employees = [_make_employee(db, number=f"M-{i}") for i in range(1, 4)]
    _make_absence(db, employees[0].id, category="krankheit",
                   start=date(2026, 3, 1), end=date(2026, 3, 24))
    result = sick_days_actual(db, today=TODAY)
    assert result["employee_count"] == 3
    assert result["suppressed"] is True
    assert result["average_days"] is None
    assert result["total_days"] is None


def test_sick_days_actual_is_visible_at_five_employees():
    db = db_session()
    employees = [_make_employee(db, number=f"M-{i}") for i in range(1, 6)]
    _make_absence(db, employees[0].id, category="krankheit",
                   start=date(2026, 3, 1), end=date(2026, 3, 10))  # 10 Tage
    result = sick_days_actual(db, today=TODAY)
    assert len(employees) == MIN_EMPLOYEES_FOR_SICK_DAYS_AVERAGE
    assert result["suppressed"] is False
    assert result["total_days"] == 10
    assert result["average_days"] == Decimal("2.00")  # 10 Tage / 5 Monteure


def test_sick_days_actual_only_counts_krankheit_not_urlaub_or_unbekannt():
    db = db_session()
    employees = [_make_employee(db, number=f"M-{i}") for i in range(1, 6)]
    _make_absence(db, employees[0].id, category="urlaub",
                   start=date(2026, 3, 1), end=date(2026, 3, 10))
    _make_absence(db, employees[1].id, category="unbekannt",
                   start=date(2026, 3, 1), end=date(2026, 3, 5))
    result = sick_days_actual(db, today=TODAY)
    assert result["total_days"] == 0
    assert result["average_days"] == Decimal("0.00")


def test_sick_days_actual_clips_absence_to_the_rolling_window():
    """Eine Abwesenheit, die vor dem Fenster beginnt und hineinreicht, wird auf das Fenster
    zugeschnitten, nicht komplett gezaehlt."""
    db = db_session()
    employees = [_make_employee(db, number=f"M-{i}") for i in range(1, 6)]
    window_start = date(2025, 10, 1)  # siehe _rolling_window(): 12 Monate bis TODAY (2026-09-19)
    _make_absence(db, employees[0].id, category="krankheit",
                  start=date(2025, 9, 20), end=date(2025, 10, 5))  # 5 Tage liegen im Fenster
    result = sick_days_actual(db, today=TODAY)
    assert result["total_days"] == 5


def test_sick_days_actual_data_basis_counts_any_absence_activity_not_only_sick_ones():
    """Ein Monat mit Urlaub, aber ohne Krankheit, ist trotzdem eine echte Datengrundlage -- kein
    Hinweis auf fehlende Erfassung."""
    db = db_session()
    employees = [_make_employee(db, number=f"M-{i}") for i in range(1, 6)]
    _make_absence(db, employees[0].id, category="urlaub",
                   start=date(2026, 4, 1), end=date(2026, 4, 5))
    result = sick_days_actual(db, today=TODAY)
    assert result["data_basis_months"] == 1
    assert result["window_months"] == 12


def test_sick_days_actual_zero_employees_is_suppressed_too():
    db = db_session()
    result = sick_days_actual(db, today=TODAY)
    assert result["employee_count"] == 0
    assert result["suppressed"] is True
    assert result["average_days"] is None
    assert result["total_days"] is None


# --- Punkt 4: Datengrundlage-Anzeige ist ehrlich, auch bei (fast) keinen Daten ---

def test_data_basis_is_honestly_zero_without_any_real_data():
    """Die reale, heutige Datenlage (0 Zeitbuchungen, 0 Abwesenheiten) -- die Anzeige darf das
    nicht schoenreden."""
    db = db_session()
    employees = [_make_employee(db, number=f"M-{i}") for i in range(1, 6)]
    weather = weather_days_actual(db, today=TODAY)
    sick = sick_days_actual(db, today=TODAY)
    assert weather["data_basis_months"] == 0
    assert weather["window_months"] == 12
    assert sick["data_basis_months"] == 0
    assert sick["window_months"] == 12


# --- Router: alles buero_finanzen/admin, Krankheit nie personenbezogen ---

def test_endpoint_returns_new_fields_and_recursive_scan_finds_no_personal_data(
    threaded_db_session, router_test_client,
):
    db = threaded_db_session
    employees = [_make_employee(db, number=f"M-{i}") for i in range(1, 4)]  # < 5 -> suppressed
    _make_absence(db, employees[0].id, category="krankheit",
                  start=date(2026, 3, 1), end=date(2026, 3, 24))
    order, _item = make_order_with_item(db)
    create_manual_entry(db, employee_id=employees[1].id, order_id=order.id,
                         work_date=date(2026, 1, 15), hours=Decimal("8"), entry_type="weather_winter")

    for role in ALL_ROLES:
        client = router_test_client(db, labor_rate_router, role=role)
        resp = client.get("/api/productive-hours-settings")
        if role in ("buero_finanzen", "admin"):
            assert resp.status_code == 200, (role, resp.text)
            body = resp.json()
            assert "public_holidays_suggested" in body
            assert "weather_days_actual" in body
            assert "sick_days_actual" in body
            assert body["sick_days_actual"]["suppressed"] is True
            assert body["sick_days_actual"]["average_days"] is None
            assert body["sick_days_actual"]["total_days"] is None
            # Rekursiver Schlüssel-Scan: keine personenbezogenen Bezeichner in der Antwort.
            forbidden = {"employee_id", "employee_name", "first_name", "last_name", "employee"}
            assert not (_recursive_keys(body) & forbidden), _recursive_keys(body)
        else:
            assert resp.status_code == 403, (role, resp.text)


def test_endpoint_sick_value_becomes_visible_once_five_employees_exist(
    threaded_db_session, router_test_client,
):
    db = threaded_db_session
    employees = [_make_employee(db, number=f"M-{i}") for i in range(1, 6)]
    _make_absence(db, employees[0].id, category="krankheit",
                  start=date(2026, 3, 1), end=date(2026, 3, 10))
    client = router_test_client(db, labor_rate_router, role="buero_finanzen")
    resp = client.get("/api/productive-hours-settings")
    assert resp.status_code == 200, resp.text
    body = resp.json()["sick_days_actual"]
    assert body["suppressed"] is False
    assert body["total_days"] == 10
    assert body["average_days"] == "2.00"
