"""Version 1.5.1 -- Verrechnungssatz-Kreislauf Schicht 3, die beiden buildbaren, vom
Begriffskonflikt unabhängigen Teile (siehe CLAUDE.md "Betriebskosten-Übersicht"):

(1) Produktivstunden-Rechner (app/productive_hours.py) -- leitet LaborRateSettings.
    productive_time_pct nachvollziehbar aus einzelnen Annahmen ab, schreibt erst nach einem
    bewussten "Übernehmen"-Aufruf, calculate_labor_rate() bleibt unangetastet. weeks_per_year
    kommt aus LaborRateSettings, nicht aus einem eigenen Feld -- eine Quelle für dieselbe Zahl.

(2) overview_summary()-Erweiterung um RecurringCost.overhead_classification (fix/
    auslastungsabhaengig/keine, vorläufige Bezeichnung, siehe Punkt-1-Bericht) -- drei getrennte
    Summen zusätzlich zum unveränderten annual_total.

Die eigentliche "Einspeisung" (Schreiben in LaborRateOverheadSettings, Modus-Zwang, Vergleichs-
ansicht) ist NICHT Teil dieser Version -- wartet auf die Bestätigung des Punkt-1-Vorschlags."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.labor_rate import get_or_create_labor_rate_settings
from app.productive_hours import (
    apply_productive_hours_to_labor_rate,
    calculate_productive_hours,
    get_or_create_productive_hours_settings,
    productive_hours_settings_dict,
    update_productive_hours_settings,
)
from app.recurring_costs import OVERHEAD_CLASSIFICATIONS, create_cost, overview_summary, update_cost
from app.routers.labor_rate import router as labor_rate_router
from app.routers.recurring_costs import router as recurring_costs_router

ALL_ROLES = ("field", "buero_auftrag", "buero_finanzen", "admin")


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _base_payload(**overrides):
    payload = {
        "label": "Kostenposten", "category": None, "amount": "100.00",
        "billing_interval": "monatlich", "vendor": None, "contract_end_date": None,
        "notice_period_months": None, "asset_id": None, "active": True, "notes": None,
    }
    payload.update(overrides)
    return payload


# --- calculate_productive_hours() ---

def test_calculate_productive_hours_with_round_numbers():
    """Runde Zahlen ohne Krankheit/Feiertage/Schlechtwetter/unproduktive Zeit -- von Hand
    nachrechenbar: 40h * 50 Wochen = 2000 Bruttostunden, 25 Urlaubstage * 8h = 200h Urlaub,
    1800h verbleiben, alle davon produktiv -> 90 %."""
    settings = get_or_create_productive_hours_settings(db_session())
    settings.weekly_hours = Decimal("40")
    settings.daily_hours = Decimal("8")
    settings.vacation_days = Decimal("25")
    settings.public_holidays = Decimal("0")
    settings.average_sick_days = Decimal("0")
    settings.weather_loss_days = Decimal("0")
    settings.unproductive_time_pct = Decimal("0")

    result = calculate_productive_hours(settings, Decimal("50"))

    assert result["annual_gross_hours"] == Decimal("2000.00")
    assert result["vacation_hours"] == Decimal("200.00")
    assert result["hours_after_absences"] == Decimal("1800.00")
    assert result["unproductive_hours"] == Decimal("0.00")
    assert result["productive_hours"] == Decimal("1800.00")
    assert result["productive_time_pct_result"] == Decimal("90.00")


def test_calculate_productive_hours_with_every_deduction_active():
    """Alle fünf Abzüge gleichzeitig aktiv (Modell-Standardwerte, 52 Wochen/Jahr) --
    2080 Bruttostunden - 440h Abwesenheiten = 1640h, davon 15 % unproduktiv (246h) ->
    1394 produktive Stunden, 67,02 % der Bruttostunden."""
    db = db_session()
    settings = get_or_create_productive_hours_settings(db)
    result = calculate_productive_hours(settings, Decimal("52"))

    assert result["annual_gross_hours"] == Decimal("2080.00")
    assert result["vacation_hours"] == Decimal("240.00")
    assert result["holiday_hours"] == Decimal("80.00")
    assert result["sick_hours"] == Decimal("80.00")
    assert result["weather_hours"] == Decimal("40.00")
    assert result["hours_after_absences"] == Decimal("1640.00")
    assert result["unproductive_hours"] == Decimal("246.00")
    assert result["productive_hours"] == Decimal("1394.00")
    assert result["productive_time_pct_result"] == Decimal("67.02")


def test_calculate_productive_hours_floors_at_zero_when_absences_exceed_gross_hours():
    """Absurd hohe Abwesenheiten (Testgrenzfall) dürfen nicht zu negativen Stunden führen."""
    settings = get_or_create_productive_hours_settings(db_session())
    settings.weekly_hours = Decimal("40")
    settings.daily_hours = Decimal("8")
    settings.vacation_days = Decimal("300")
    settings.public_holidays = Decimal("0")
    settings.average_sick_days = Decimal("0")
    settings.weather_loss_days = Decimal("0")
    settings.unproductive_time_pct = Decimal("0")

    result = calculate_productive_hours(settings, Decimal("52"))

    assert result["hours_after_absences"] == Decimal("0.00")
    assert result["productive_hours"] == Decimal("0.00")
    assert result["productive_time_pct_result"] == Decimal("0")


# --- weeks_per_year kommt aus LaborRateSettings, keine eigene Quelle ---

def test_weeks_per_year_is_read_from_labor_rate_settings_not_a_second_field():
    db = db_session()
    labor_rate_settings = get_or_create_labor_rate_settings(db)
    labor_rate_settings.weeks_per_year = Decimal("48.00")
    db.commit()

    result = productive_hours_settings_dict(db)

    assert result["weeks_per_year"] == Decimal("48.00")
    # Mit weniger Wochen/Jahr sinken die Bruttojahresstunden gegenüber dem 52-Wochen-Fall.
    assert result["annual_gross_hours"] < Decimal("2080.00")


# --- update_productive_hours_settings() ---

def test_update_productive_hours_settings_persists_and_recalculates():
    """weeks_per_year bleibt beim Standardwert 52 -- siehe
    test_productive_hours_router_apply_updates_labor_rate_settings_field für die Herleitung
    von 90,38 %."""
    db = db_session()
    result = update_productive_hours_settings(db, {
        "weekly_hours": Decimal("40"), "daily_hours": Decimal("8"), "vacation_days": Decimal("25"),
        "public_holidays": Decimal("0"), "average_sick_days": Decimal("0"),
        "weather_loss_days": Decimal("0"), "unproductive_time_pct": Decimal("0"),
    })
    assert result["vacation_days"] == Decimal("25")
    assert result["productive_time_pct_result"] == Decimal("90.38")

    # Persistiert -- ein zweiter Lesezugriff liefert denselben, gespeicherten Stand.
    reloaded = productive_hours_settings_dict(db)
    assert reloaded["vacation_days"] == Decimal("25")


# --- apply_productive_hours_to_labor_rate(): schreibt AUSSCHLIESSLICH productive_time_pct ---

def test_apply_writes_only_productive_time_pct_leaves_everything_else_untouched():
    db = db_session()
    labor_rate_settings = get_or_create_labor_rate_settings(db)
    labor_rate_settings.employer_cost_pct = Decimal("30.00")
    labor_rate_settings.target_profit_pct = Decimal("12.00")
    labor_rate_settings.weeks_per_year = Decimal("52.00")
    labor_rate_settings.productive_time_pct = Decimal("70.00")
    db.commit()

    update_productive_hours_settings(db, {
        "weekly_hours": Decimal("40"), "daily_hours": Decimal("8"), "vacation_days": Decimal("25"),
        "public_holidays": Decimal("0"), "average_sick_days": Decimal("0"),
        "weather_loss_days": Decimal("0"), "unproductive_time_pct": Decimal("0"),
    })

    result = apply_productive_hours_to_labor_rate(db)
    assert result["current_productive_time_pct"] == Decimal("90.38")

    db.refresh(labor_rate_settings)
    assert labor_rate_settings.productive_time_pct == Decimal("90.38")
    # Alles andere unveraendert -- kein Nebeneffekt auf die uebrigen Kalkulationsgrundlagen.
    assert labor_rate_settings.employer_cost_pct == Decimal("30.00")
    assert labor_rate_settings.target_profit_pct == Decimal("12.00")
    assert labor_rate_settings.weeks_per_year == Decimal("52.00")


def test_apply_is_a_conscious_second_step_not_triggered_by_saving_settings_alone():
    """Speichern allein (ohne apply()) darf productive_time_pct NICHT veraendern -- Muster
    apply_labor_rate_calculation(): kein Automatismus."""
    db = db_session()
    labor_rate_settings = get_or_create_labor_rate_settings(db)
    labor_rate_settings.productive_time_pct = Decimal("70.00")
    db.commit()

    update_productive_hours_settings(db, {
        "weekly_hours": Decimal("40"), "daily_hours": Decimal("8"), "vacation_days": Decimal("25"),
        "public_holidays": Decimal("0"), "average_sick_days": Decimal("0"),
        "weather_loss_days": Decimal("0"), "unproductive_time_pct": Decimal("0"),
    })

    db.refresh(labor_rate_settings)
    assert labor_rate_settings.productive_time_pct == Decimal("70.00")


# --- Router: Produktivstunden-Rechner ist buero_finanzen/admin-only (Muster Stundensatz-Rechner) ---

def test_productive_hours_router_requires_buero_finanzen(threaded_db_session, router_test_client):
    db = threaded_db_session
    for role in ALL_ROLES:
        client = router_test_client(db, labor_rate_router, role=role)
        get_resp = client.get("/api/productive-hours-settings")
        if role in ("buero_finanzen", "admin"):
            assert get_resp.status_code == 200, (role, get_resp.text)
        else:
            assert get_resp.status_code == 403, (role, get_resp.text)

    put_payload = {
        "weekly_hours": 40, "daily_hours": 8, "vacation_days": 25, "public_holidays": 0,
        "average_sick_days": 0, "weather_loss_days": 0, "unproductive_time_pct": 0,
    }
    for role in ALL_ROLES:
        client = router_test_client(db, labor_rate_router, role=role)
        put_resp = client.put("/api/productive-hours-settings", json=put_payload)
        apply_resp = client.post("/api/productive-hours-settings/apply")
        if role in ("buero_finanzen", "admin"):
            assert put_resp.status_code == 200, (role, put_resp.text)
            assert apply_resp.status_code == 200, (role, apply_resp.text)
        else:
            assert put_resp.status_code == 403, (role, put_resp.text)
            assert apply_resp.status_code == 403, (role, apply_resp.text)


def test_productive_hours_router_apply_updates_labor_rate_settings_field(threaded_db_session, router_test_client):
    """weeks_per_year bleibt beim Standardwert 52 (aus labor-rate-settings, nicht ueberschrieben)
    -- 40h*52 Wochen=2080h Brutto, 25 Urlaubstage*8h=200h, 1880h verbleiben, alle produktiv:
    1880/2080*100 = 90,3846...%, ROUND_HALF_UP auf 90,38%."""
    db = threaded_db_session
    client = router_test_client(db, labor_rate_router, role="buero_finanzen")
    client.put("/api/productive-hours-settings", json={
        "weekly_hours": 40, "daily_hours": 8, "vacation_days": 25, "public_holidays": 0,
        "average_sick_days": 0, "weather_loss_days": 0, "unproductive_time_pct": 0,
    })
    apply_resp = client.post("/api/productive-hours-settings/apply")
    assert apply_resp.status_code == 200, apply_resp.text

    settings_resp = client.get("/api/labor-rate-settings")
    assert settings_resp.status_code == 200
    assert Decimal(str(settings_resp.json()["productive_time_pct"])) == Decimal("90.38")


# --- RecurringCost.overhead_classification ---

def test_overhead_classification_defaults_to_keine_and_is_validated():
    db = db_session()
    cost = create_cost(db, _base_payload(label="Ohne Angabe"))
    assert cost["overhead_classification"] == "keine"

    for value in OVERHEAD_CLASSIFICATIONS:
        c = create_cost(db, _base_payload(label=f"Klassifiziert als {value}", overhead_classification=value))
        assert c["overhead_classification"] == value

    with pytest.raises(ValueError):
        create_cost(db, _base_payload(label="Ungueltig", overhead_classification="variabel"))


def test_overhead_classification_can_be_changed_via_update_cost():
    db = db_session()
    cost = create_cost(db, _base_payload(label="Leasingrate", overhead_classification="fix"))
    updated = update_cost(db, cost["id"], _base_payload(label="Leasingrate", overhead_classification="auslastungsabhaengig"))
    assert updated["overhead_classification"] == "auslastungsabhaengig"


# --- overview_summary(): drei getrennte Summen, annual_total bleibt unveraendert ---

def test_overview_summary_splits_annual_sums_by_classification_but_keeps_total_unchanged():
    db = db_session()
    create_cost(db, _base_payload(label="Miete", amount="1000.00", billing_interval="monatlich", overhead_classification="fix"))
    create_cost(db, _base_payload(label="Diesel", amount="50.00", billing_interval="monatlich", overhead_classification="auslastungsabhaengig"))
    create_cost(db, _base_payload(label="Unklassifiziert", amount="20.00", billing_interval="monatlich", overhead_classification="keine"))

    summary = overview_summary(db)

    assert summary["annual_fixed_from_costs"] == Decimal("12000.00")
    assert summary["annual_usage_dependent_from_costs"] == Decimal("600.00")
    assert summary["annual_none_from_costs"] == Decimal("240.00")
    # Summe der drei Gruppen == annual_total (annual_total bleibt die unveraenderte Gesamtsumme).
    assert summary["annual_fixed_from_costs"] + summary["annual_usage_dependent_from_costs"] + summary["annual_none_from_costs"] == summary["annual_total"]
    assert summary["annual_total"] == Decimal("12840.00")


def test_overview_summary_excludes_inactive_costs_from_all_three_groups():
    db = db_session()
    create_cost(db, _base_payload(label="Aktiv fix", amount="100.00", overhead_classification="fix", active=True))
    create_cost(db, _base_payload(label="Inaktiv fix", amount="999.00", overhead_classification="fix", active=False))

    summary = overview_summary(db)

    assert summary["annual_fixed_from_costs"] == Decimal("1200.00")


# --- Router: overview liefert die drei neuen Felder nur fuer buero_finanzen/admin ---

def test_overview_router_returns_the_three_classification_sums(threaded_db_session, router_test_client):
    db = threaded_db_session
    client = router_test_client(db, recurring_costs_router, role="buero_finanzen")
    client.post("/api/recurring-costs", json=_base_payload(label="Miete", overhead_classification="fix"))
    resp = client.get("/api/recurring-costs/overview")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "annual_fixed_from_costs" in body
    assert "annual_usage_dependent_from_costs" in body
    assert "annual_none_from_costs" in body


def test_overview_router_invalid_classification_rejected_with_422(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, recurring_costs_router, role="buero_finanzen")
    resp = client.post("/api/recurring-costs", json=_base_payload(label="Ungueltig", overhead_classification="variabel"))
    assert resp.status_code == 422, resp.text
