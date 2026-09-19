"""Version 1.5.2 -- Verrechnungssatz-Kreislauf Schicht 3, die Einspeisung (siehe CLAUDE.md
"Betriebskosten-Übersicht" -> "Verrechnungssatz-Kreislauf Schicht 3").

Deckt die fünf vom Betreiber vorgegebenen Punkte ab:
(1) recurring_cost_overhead_proposal() zeigt X (auslastungsabhängige Betriebskosten), Y
    (automatisch berechnete Verwaltungslöhne) und X+Y (variable Gemeinkosten) getrennt, für
    "aktuell" UND "Vorschlag" -- die Formel-Konsistenz aus dem Punkt-1-Befund.
(2) Modus-Zwang: apply_recurring_cost_overhead_proposal() erzwingt IMMER Modus "eur" auf beiden
    Feldern, unabhängig vom vorherigen Modus (der Warnhinweis selbst sitzt im Frontend, siehe
    settings.html::applyOverheadProposal()).
(3) Dreistufige Aufschlüsselung: fixed_costs/usage_dependent_costs listen die einzelnen Posten,
    "keine"-klassifizierte und inaktive Posten bleiben draußen.
(4) calculate_labor_rate()s overhead_override rechnet rein in-memory, ohne die persistierten
    Einstellungen anzufassen -- eine Quelle (calculate_labor_rate()), keine zweite Berechnung.
(5) Zweistufigkeit: apply_recurring_cost_overhead_proposal() schreibt AUSSCHLIESSLICH die beiden
    Gemeinkosten-Felder, nie CalculationSettings.labor_rate (das bleibt Schritt 2, unverändert
    apply_labor_rate_calculation()).

Abschließender Angriffstest (Betreibervorgabe): buero_auftrag und field kommen an keinen Teil
des Kreislaufs -- weder an die Einordnung (Betriebskosten-Klassifizierung), noch an die
Vergleichsansicht, noch an den Übernehmen-Knopf, noch an den Produktivstunden-Rechner. Alles
buero_finanzen und admin. Rekursiver Schlüssel-Scan, ein Testkonto pro Rolle."""

import json
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.calculation import get_or_create_settings
from app.database import Base
from app.employees import set_cost_allocation
from app.labor_rate import (
    apply_recurring_cost_overhead_proposal,
    calculate_labor_rate,
    get_or_create_labor_rate_settings,
    get_or_create_overhead_settings,
    recurring_cost_overhead_proposal,
)
from app.models import Employee
from app.recurring_costs import create_cost
from app.routers.labor_rate import router as labor_rate_router
from app.routers.recurring_costs import router as recurring_costs_router

ALL_ROLES = ("field", "buero_auftrag", "buero_finanzen", "admin")


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _cost_payload(**overrides):
    payload = {
        "label": "Kostenposten", "category": None, "net_amount": "100.00",
        "billing_interval": "monatlich", "vendor": None, "contract_end_date": None,
        "notice_period_months": None, "asset_id": None, "active": True, "notes": None,
    }
    payload.update(overrides)
    return payload


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
    elif isinstance(value, str):
        s = value.strip()
        if s[:1] in "{[":
            try:
                parsed = json.loads(s)
            except (TypeError, ValueError):
                return keys
            _recursive_keys(parsed, keys)
    return keys


def _make_direct_employee(db, *, hourly_wage="20", weekly_hours="40"):
    employee = Employee(
        first_name="Direkt", last_name="Dach", employee_group="gewerblich",
        hourly_wage=Decimal(hourly_wage), weekly_hours=Decimal(weekly_hours), active=True,
    )
    db.add(employee)
    db.commit()
    return employee


def _make_variable_overhead_employee(db, *, hourly_wage="10", weekly_hours="40"):
    employee = Employee(
        first_name="Verwaltung", last_name="Büro", employee_group="kaufmaennisch",
        hourly_wage=Decimal(hourly_wage), weekly_hours=Decimal(weekly_hours), active=True,
    )
    db.add(employee)
    db.commit()
    set_cost_allocation(db, employee, "variable_overhead")
    db.commit()
    return employee


# --- (4) calculate_labor_rate() overhead_override: eine Quelle, keine zweite Berechnung, kein DB-Schreiben ---

def test_overhead_override_computes_in_memory_without_touching_persisted_settings():
    db = db_session()
    _make_direct_employee(db)
    calc_settings = get_or_create_settings(db)
    overhead = get_or_create_overhead_settings(db)
    overhead.fixed_overhead_mode = "eur"
    overhead.fixed_overhead_value = Decimal("10000")
    overhead.variable_overhead_mode = "eur"
    overhead.variable_overhead_value = Decimal("5000")
    db.commit()

    result_before = calculate_labor_rate(db, calc_settings)
    assert result_before["fixed_overhead_annual"] == Decimal("10000.00")

    result_override = calculate_labor_rate(
        db, calc_settings,
        overhead_override={
            "fixed_overhead_mode": "eur", "fixed_overhead_value": Decimal("99999"),
            "variable_overhead_mode": "eur", "variable_overhead_value": Decimal("88888"),
        },
    )
    assert result_override["fixed_overhead_annual"] == Decimal("99999.00")
    assert result_override["manual_variable_overhead_annual"] == Decimal("88888.00")
    # annual_productive_hours haengt nicht von den Gemeinkosten ab -- bleibt identisch, exakt
    # dieselbe Formel, kein zweiter Rechenweg fuer denselben Wert.
    assert result_override["annual_productive_hours"] == result_before["annual_productive_hours"]

    # Rein in-memory: die persistierten Einstellungen sind unveraendert.
    db.refresh(overhead)
    assert overhead.fixed_overhead_value == Decimal("10000.00")
    assert overhead.variable_overhead_value == Decimal("5000.00")

    # Ein erneuter Aufruf ohne Override liefert wieder exakt den urspruenglichen Stand.
    result_again = calculate_labor_rate(db, calc_settings)
    assert result_again == result_before


def test_overhead_override_with_percent_mode_uses_direct_labor_cost_as_base():
    db = db_session()
    _make_direct_employee(db, hourly_wage="20", weekly_hours="40")
    calc_settings = get_or_create_settings(db)
    labor_rate_settings = get_or_create_labor_rate_settings(db)
    labor_rate_settings.employer_cost_pct = Decimal("20")
    db.commit()
    # direct_labor_annual_cost = 20*40*52 * 1.20 = 49920.00
    result = calculate_labor_rate(
        db, calc_settings,
        overhead_override={"fixed_overhead_mode": "pct", "fixed_overhead_value": Decimal("10")},
    )
    assert result["direct_labor_annual_cost"] == Decimal("49920.00")
    assert result["fixed_overhead_annual"] == Decimal("4992.00")


# --- (1)+(3) recurring_cost_overhead_proposal(): current/proposed, X+Y=Total, Aufschluesselung ---

def test_proposal_reuses_calculate_labor_rate_for_current_and_proposed():
    """Die Vergleichsansicht baut current/proposed NICHT selbst nach -- beide Zustaende muessen
    sich exakt mit einem direkten calculate_labor_rate()-Aufruf mit denselben Argumenten decken."""
    db = db_session()
    _make_direct_employee(db, hourly_wage="20", weekly_hours="40")
    _make_variable_overhead_employee(db, hourly_wage="10", weekly_hours="40")
    calc_settings = get_or_create_settings(db)
    labor_rate_settings = get_or_create_labor_rate_settings(db)
    labor_rate_settings.employer_cost_pct = Decimal("20")
    labor_rate_settings.productive_time_pct = Decimal("80")
    labor_rate_settings.target_profit_pct = Decimal("10")
    overhead = get_or_create_overhead_settings(db)
    overhead.fixed_overhead_mode = "eur"
    overhead.fixed_overhead_value = Decimal("5000")
    overhead.variable_overhead_mode = "eur"
    overhead.variable_overhead_value = Decimal("3000")
    db.commit()

    create_cost(db, _cost_payload(label="Miete", net_amount="1000.00", overhead_classification="fix"))
    create_cost(db, _cost_payload(label="Diesel", net_amount="200.00", overhead_classification="auslastungsabhaengig"))
    create_cost(db, _cost_payload(label="Unklassifiziert", net_amount="50.00", overhead_classification="keine"))
    create_cost(db, _cost_payload(label="Archivierte Miete", net_amount="9999.00", overhead_classification="fix", active=False))

    proposal = recurring_cost_overhead_proposal(db, calc_settings)

    # annual_fixed_from_costs/annual_usage_dependent_from_costs schliessen "keine" und
    # archivierte Posten aus (overview_summary(), unveraendert).
    assert proposal["annual_fixed_from_costs"] == Decimal("12000.00")
    assert proposal["annual_usage_dependent_from_costs"] == Decimal("2400.00")

    direct_current = calculate_labor_rate(db, calc_settings)
    direct_proposed = calculate_labor_rate(
        db, calc_settings,
        overhead_override={
            "fixed_overhead_mode": "eur", "fixed_overhead_value": Decimal("12000.00"),
            "variable_overhead_mode": "eur", "variable_overhead_value": Decimal("2400.00"),
        },
    )

    assert proposal["current"]["fixed_overhead_annual"] == direct_current["fixed_overhead_annual"]
    assert proposal["current"]["manual_variable_overhead_annual"] == direct_current["manual_variable_overhead_annual"]
    assert proposal["current"]["variable_employee_costs"] == direct_current["variable_employee_costs"]
    assert proposal["current"]["variable_overhead_annual"] == direct_current["variable_overhead_annual"]
    assert proposal["current"]["suggested_labor_rate"] == direct_current["suggested_labor_rate"]

    assert proposal["proposed"]["fixed_overhead_annual"] == direct_proposed["fixed_overhead_annual"]
    assert proposal["proposed"]["manual_variable_overhead_annual"] == direct_proposed["manual_variable_overhead_annual"]
    assert proposal["proposed"]["variable_employee_costs"] == direct_proposed["variable_employee_costs"]
    assert proposal["proposed"]["variable_overhead_annual"] == direct_proposed["variable_overhead_annual"]
    assert proposal["proposed"]["suggested_labor_rate"] == direct_proposed["suggested_labor_rate"]

    # Punkt 1 der Anfrage: X (auslastungsabhaengig) + Y (Verwaltungsloehne) == variable Gemeinkosten.
    x = proposal["proposed"]["manual_variable_overhead_annual"]
    y = proposal["proposed"]["variable_employee_costs"]
    assert x + y == proposal["proposed"]["variable_overhead_annual"]
    assert x == Decimal("2400.00")
    assert y > Decimal("0")

    # variable_employee_costs haengt nur von der Mitarbeiter-Kosten-Zuordnung ab, nicht von den
    # Gemeinkosten-Feldern -- current und proposed muessen deshalb identisch sein.
    assert proposal["current"]["variable_employee_costs"] == proposal["proposed"]["variable_employee_costs"]

    # Modus wird im Vorschlag immer als "eur" ausgewiesen (Modus-Zwang, Punkt 2).
    assert proposal["proposed"]["fixed_mode"] == "eur"
    assert proposal["proposed"]["variable_mode"] == "eur"
    assert proposal["proposed"]["fixed_value"] == Decimal("12000.00")
    assert proposal["proposed"]["variable_value"] == Decimal("2400.00")

    # "current" zeigt unveraendert den tatsaechlich hinterlegten Modus/Wert.
    assert proposal["current"]["fixed_mode"] == "eur"
    assert proposal["current"]["fixed_value"] == Decimal("5000.00")
    assert proposal["current"]["variable_value"] == Decimal("3000.00")


def test_proposal_lists_individual_items_excluding_keine_and_inactive():
    """Dreistufige Aufschluesselung, Punkt 3: fixed_costs/usage_dependent_costs sind die
    einzelnen, aufklappbaren Posten -- "keine"-klassifizierte und inaktive Posten fehlen."""
    db = db_session()
    calc_settings = get_or_create_settings(db)
    miete = create_cost(db, _cost_payload(label="Miete", net_amount="1000.00", overhead_classification="fix"))
    diesel = create_cost(db, _cost_payload(label="Diesel", net_amount="200.00", overhead_classification="auslastungsabhaengig"))
    create_cost(db, _cost_payload(label="Unklassifiziert", net_amount="50.00", overhead_classification="keine"))
    create_cost(db, _cost_payload(label="Archiviert", net_amount="9999.00", overhead_classification="fix", active=False))

    proposal = recurring_cost_overhead_proposal(db, calc_settings)

    assert proposal["fixed_costs"] == [{"id": miete["id"], "label": "Miete", "annual_amount": Decimal("12000.00")}]
    assert proposal["usage_dependent_costs"] == [{"id": diesel["id"], "label": "Diesel", "annual_amount": Decimal("2400.00")}]


def test_proposal_is_read_only_and_never_writes_anything():
    db = db_session()
    calc_settings = get_or_create_settings(db)
    overhead = get_or_create_overhead_settings(db)
    overhead.fixed_overhead_mode = "pct"
    overhead.fixed_overhead_value = Decimal("12")
    db.commit()
    create_cost(db, _cost_payload(label="Miete", net_amount="1000.00", overhead_classification="fix"))

    recurring_cost_overhead_proposal(db, calc_settings)

    db.refresh(overhead)
    assert overhead.fixed_overhead_mode == "pct"
    assert overhead.fixed_overhead_value == Decimal("12.00")


# --- (2)+(5) apply_recurring_cost_overhead_proposal(): Modus-Zwang, schreibt AUSSCHLIESSLICH die zwei Felder ---

def test_apply_forces_eur_mode_on_both_fields_regardless_of_previous_mode():
    db = db_session()
    overhead = get_or_create_overhead_settings(db)
    overhead.fixed_overhead_mode = "pct"
    overhead.fixed_overhead_value = Decimal("15")
    overhead.variable_overhead_mode = "pct"
    overhead.variable_overhead_value = Decimal("8")
    db.commit()
    create_cost(db, _cost_payload(label="Miete", net_amount="1000.00", overhead_classification="fix"))
    create_cost(db, _cost_payload(label="Diesel", net_amount="200.00", overhead_classification="auslastungsabhaengig"))

    apply_recurring_cost_overhead_proposal(db)

    db.refresh(overhead)
    assert overhead.fixed_overhead_mode == "eur"
    assert overhead.fixed_overhead_value == Decimal("12000.00")
    assert overhead.variable_overhead_mode == "eur"
    assert overhead.variable_overhead_value == Decimal("2400.00")


def test_apply_syncs_legacy_annual_overhead_field_but_touches_nothing_else():
    """Schritt 1 schreibt AUSSCHLIESSLICH die beiden Gemeinkosten-Felder (plus das Legacy-Spiegel-
    feld annual_overhead) -- NICHT CalculationSettings.labor_rate (bleibt Schritt 2, getrennt)."""
    db = db_session()
    labor_rate_settings = get_or_create_labor_rate_settings(db)
    labor_rate_settings.employer_cost_pct = Decimal("25.00")
    labor_rate_settings.target_profit_pct = Decimal("12.00")
    labor_rate_settings.annual_overhead = Decimal("1.00")
    calc_settings = get_or_create_settings(db)
    calc_settings.labor_rate = Decimal("77.00")
    db.commit()
    create_cost(db, _cost_payload(label="Miete", net_amount="1000.00", overhead_classification="fix"))

    apply_recurring_cost_overhead_proposal(db)

    db.refresh(labor_rate_settings)
    db.refresh(calc_settings)
    assert labor_rate_settings.annual_overhead == Decimal("12000.00")
    assert labor_rate_settings.employer_cost_pct == Decimal("25.00")
    assert labor_rate_settings.target_profit_pct == Decimal("12.00")
    # Schritt 2 (Verrechnungssatz uebernehmen) ist unangetastet -- apply() der Einspeisung
    # veraendert calc_settings.labor_rate nicht.
    assert calc_settings.labor_rate == Decimal("77.00")


def test_apply_excludes_keine_and_inactive_costs_from_the_written_sums():
    db = db_session()
    create_cost(db, _cost_payload(label="Miete", net_amount="1000.00", overhead_classification="fix"))
    create_cost(db, _cost_payload(label="Unklassifiziert", net_amount="500.00", overhead_classification="keine"))
    create_cost(db, _cost_payload(label="Archiviert", net_amount="9999.00", overhead_classification="fix", active=False))

    apply_recurring_cost_overhead_proposal(db)

    overhead = get_or_create_overhead_settings(db)
    assert overhead.fixed_overhead_value == Decimal("12000.00")


# --- Angriffstest: buero_auftrag/field kommen an keinen Teil des Kreislaufs (Router-Ebene) ---

FORBIDDEN_PROPOSAL_KEYS = {
    "suggested_labor_rate", "fixed_overhead_annual", "variable_overhead_annual",
    "annual_fixed_from_costs", "annual_usage_dependent_from_costs", "manual_variable_overhead_annual",
    "variable_employee_costs", "fixed_costs", "usage_dependent_costs",
}
FORBIDDEN_PRODUCTIVE_HOURS_KEYS = {
    "productive_hours", "productive_time_pct_result", "annual_gross_hours", "weeks_per_year",
}


def test_attack_neither_buero_auftrag_nor_field_reach_any_part_of_the_cycle(threaded_db_session, router_test_client):
    """Vier Teile des Kreislaufs, ein Testkonto je Rolle: die Einordnung (Betriebskosten-
    Klassifizierung), die Vergleichsansicht, der Übernehmen-Knopf, der Produktivstunden-Rechner.
    Rekursiver Schlüssel-Scan gegen Preis-/Kalkulationsfelder, keine davon darf für
    buero_auftrag/field jemals in einer Antwort auftauchen."""
    db = threaded_db_session

    for role in ALL_ROLES:
        expected = 200 if role in ("buero_finanzen", "admin") else 403
        labor_rate_client = router_test_client(db, labor_rate_router, role=role)
        recurring_costs_client = router_test_client(db, recurring_costs_router, role=role)

        # (1) Einordnung -- Betriebskosten anlegen/klassifizieren.
        create_resp = recurring_costs_client.post(
            "/api/recurring-costs",
            json=_cost_payload(label=f"Miete ({role})", overhead_classification="fix"),
        )
        assert create_resp.status_code == expected, (role, "Einordnung", create_resp.text)

        # (2) Vergleichsansicht.
        proposal_resp = labor_rate_client.get("/api/recurring-cost-overhead-proposal")
        assert proposal_resp.status_code == expected, (role, "Vergleichsansicht", proposal_resp.text)

        # (3) Übernehmen-Knopf.
        apply_resp = labor_rate_client.post("/api/recurring-cost-overhead-proposal/apply")
        assert apply_resp.status_code == expected, (role, "Übernehmen", apply_resp.text)

        # (4) Produktivstunden-Rechner.
        ph_get_resp = labor_rate_client.get("/api/productive-hours-settings")
        ph_apply_resp = labor_rate_client.post("/api/productive-hours-settings/apply")
        assert ph_get_resp.status_code == expected, (role, "Produktivstunden GET", ph_get_resp.text)
        assert ph_apply_resp.status_code == expected, (role, "Produktivstunden apply", ph_apply_resp.text)

        if expected == 200:
            # Für die zugelassenen Rollen müssen die eigentlichen Kalkulationsfelder auch
            # tatsächlich vorhanden sein -- sonst würde der Scan unten nichts Sinnvolles prüfen.
            assert _recursive_keys(proposal_resp.json()) & FORBIDDEN_PROPOSAL_KEYS
            assert _recursive_keys(ph_get_resp.json()) & FORBIDDEN_PRODUCTIVE_HOURS_KEYS
        else:
            assert not (_recursive_keys(create_resp.json()) & FORBIDDEN_PROPOSAL_KEYS)
            assert not (_recursive_keys(proposal_resp.json()) & FORBIDDEN_PROPOSAL_KEYS)
            assert not (_recursive_keys(apply_resp.json()) & FORBIDDEN_PROPOSAL_KEYS)
            assert not (_recursive_keys(ph_get_resp.json()) & FORBIDDEN_PRODUCTIVE_HOURS_KEYS)
            assert not (_recursive_keys(ph_apply_resp.json()) & FORBIDDEN_PRODUCTIVE_HOURS_KEYS)
