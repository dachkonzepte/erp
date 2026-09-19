"""Netto und Brutto bei den Betriebskosten (Nachbesserung, siehe CLAUDE.md). RecurringCost trägt
seit dieser Version net_amount (die Eingabe) + tax_rate_pct (Feld JE POSTEN, kein globaler Wert)
statt eines einzelnen, semantisch unklaren "amount"-Felds. gross_amount ist eine reine
Anzeige-Ableitung -- entscheidend: annual_amount (und damit overview_summary()/die
Gemeinkosten-Einspeisung aus Schicht 3) rechnet ausnahmslos auf Basis von net_amount, nie brutto."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.recurring_costs import (
    TAX_RATES, create_cost, gross_amount, normalize_to_annual, overview_summary, update_cost,
)
from app.routers.recurring_costs import router as recurring_costs_router


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _payload(**overrides):
    payload = {
        "label": "Kostenposten", "category": None, "net_amount": "100.00",
        "billing_interval": "monatlich", "vendor": None, "contract_end_date": None,
        "notice_period_months": None, "asset_id": None, "active": True, "notes": None,
    }
    payload.update(overrides)
    return payload


def test_gross_amount_pure_function():
    assert gross_amount(Decimal("100.00"), Decimal("19.00")) == Decimal("119.00")
    assert gross_amount(Decimal("100.00"), Decimal("7.00")) == Decimal("107.00")
    assert gross_amount(Decimal("100.00"), Decimal("0.00")) == Decimal("100.00")


def test_create_cost_defaults_to_19_percent_when_omitted():
    db = db_session()
    cost = create_cost(db, _payload(net_amount="200.00"))
    assert cost["tax_rate_pct"] == Decimal("19.00")
    assert cost["gross_amount"] == Decimal("238.00")


@pytest.mark.parametrize("rate", TAX_RATES)
def test_create_cost_accepts_every_real_tax_rate(rate):
    db = db_session()
    cost = create_cost(db, _payload(net_amount="100.00", tax_rate_pct=str(rate)))
    assert cost["tax_rate_pct"] == rate
    assert cost["gross_amount"] == gross_amount(Decimal("100.00"), rate)


def test_create_cost_rejects_an_unsupported_tax_rate():
    db = db_session()
    with pytest.raises(ValueError):
        create_cost(db, _payload(net_amount="100.00", tax_rate_pct="10.00"))


def test_annual_amount_is_computed_from_net_not_gross():
    """Die entscheidende Korrektheitsprüfung: annual_amount (und damit alles, was Schicht 3
    daraus einspeist) darf sich NICHT ändern, wenn nur der Steuersatz variiert -- nur net_amount
    und billing_interval bestimmen ihn."""
    db = db_session()
    low_tax = create_cost(db, _payload(label="Versicherung", net_amount="100.00", tax_rate_pct="0.00", billing_interval="monatlich"))
    high_tax = create_cost(db, _payload(label="Steuerberater", net_amount="100.00", tax_rate_pct="19.00", billing_interval="monatlich"))
    assert low_tax["annual_amount"] == Decimal("1200.00")
    assert high_tax["annual_amount"] == Decimal("1200.00")
    assert low_tax["gross_amount"] == Decimal("100.00")
    assert high_tax["gross_amount"] == Decimal("119.00")
    assert normalize_to_annual(Decimal("100.00"), "monatlich") == Decimal("1200.00")


def test_overview_summary_totals_are_net_based_regardless_of_tax_rate():
    db = db_session()
    create_cost(db, _payload(label="Versicherung", net_amount="100.00", tax_rate_pct="0.00", billing_interval="monatlich", overhead_classification="fix"))
    create_cost(db, _payload(label="Steuerberater", net_amount="100.00", tax_rate_pct="19.00", billing_interval="monatlich", overhead_classification="fix"))
    summary = overview_summary(db)
    # 2 x 100 EUR netto x 12 Monate = 2400 EUR -- waere die Rechnung brutto, kaeme 2628 EUR heraus
    # (100 + 119) x 12).
    assert summary["annual_total"] == Decimal("2400.00")
    assert summary["annual_fixed_from_costs"] == Decimal("2400.00")


def test_update_cost_can_change_tax_rate_without_changing_annual_amount():
    db = db_session()
    cost = create_cost(db, _payload(net_amount="100.00", tax_rate_pct="19.00", billing_interval="monatlich"))
    updated = update_cost(db, cost["id"], _payload(net_amount="100.00", tax_rate_pct="7.00", billing_interval="monatlich"))
    assert updated["tax_rate_pct"] == Decimal("7.00")
    assert updated["annual_amount"] == Decimal("1200.00")
    assert updated["gross_amount"] == Decimal("107.00")


def test_router_rejects_invalid_tax_rate_with_422(threaded_db_session, router_test_client):
    db = threaded_db_session
    client = router_test_client(db, recurring_costs_router, role="buero_finanzen")
    resp = client.post("/api/recurring-costs", json={
        "label": "Test", "net_amount": "100.00", "tax_rate_pct": "10.00", "billing_interval": "monatlich",
    })
    assert resp.status_code == 422


def test_router_response_includes_net_tax_and_gross(threaded_db_session, router_test_client):
    db = threaded_db_session
    client = router_test_client(db, recurring_costs_router, role="buero_finanzen")
    resp = client.post("/api/recurring-costs", json={
        "label": "Steuerberater", "net_amount": "500.00", "tax_rate_pct": "19.00", "billing_interval": "monatlich",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["net_amount"] == "500.00"
    assert body["tax_rate_pct"] == "19.00"
    assert body["gross_amount"] == "595.00"
