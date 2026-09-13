from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.importers.leistungen_dach import parse_leistungen_dach_xml
from app.main import (
    add_quote_item,
    create_customer,
    create_project,
    create_quote,
    get_quote_item_calculation,
    list_customers,
    update_quote_item_calculation,
)
from app.models import Customer, CustomerProfile, QuoteItem, Service
from app.schemas import (
    CustomerCreate,
    ProjectCreate,
    QuoteCreate,
    QuoteItemCalculationUpdate,
    QuoteItemCreate,
    QuoteItemMaterialCalculationUpdate,
)
from app.service import persist_project


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_customer_number_category_and_legacy_backfill():
    db = make_db()
    c1 = create_customer(CustomerCreate(last_name="Hausverwaltung Test", category="Hausverwaltung"), db)
    c2 = create_customer(CustomerCreate(last_name="Privat Test"), db)

    assert c1.customer_number.startswith("K-")
    assert c2.customer_number.startswith("K-")
    assert c1.customer_number != c2.customer_number
    assert c1.category == "Hausverwaltung"
    assert c2.category == "Privatkunde"

    legacy = Customer(name="Altkunde ohne Profil", last_name="Altkunde ohne Profil")
    db.add(legacy)
    db.commit()
    customers = list_customers(db)
    legacy = next(c for c in customers if c.name == "Altkunde ohne Profil")
    assert legacy.customer_number.startswith("K-")
    assert legacy.category == "Privatkunde"
    assert db.scalar(select(CustomerProfile).where(CustomerProfile.customer_id == legacy.id)) is not None


def test_project_specific_quote_calculation_updates_ep_without_catalog_change():
    db = make_db()
    sample = Path(__file__).parents[1] / "sample_data" / "Thiefes.xml"
    parsed = parse_leistungen_dach_xml(sample.read_bytes())
    persist_project(db, parsed, "Thiefes.xml")
    service = db.scalar(select(Service).where(Service.external_id == "L600109101011"))
    catalog_sale_price = Decimal(service.sale_price)

    customer = create_customer(CustomerCreate(last_name="Kalkulationskunde"), db)
    project = create_project(ProjectCreate(customer_id=customer.id, name="Testprojekt"), db)
    quote = create_quote(project.id, QuoteCreate(title="Testangebot"), db)
    quote = add_quote_item(quote.id, QuoteItemCreate(service_id=service.id, quantity=Decimal("10")), db)
    item = quote.items[0]

    calc = get_quote_item_calculation(quote.id, item.id, db)
    old_ep = Decimal(calc.effective_sale_price)
    assert calc.materials

    materials = [
        QuoteItemMaterialCalculationUpdate(
            id=m.id,
            quantity=Decimal(m.quantity),
            waste_pct=Decimal(m.waste_pct),
            purchase_price=Decimal(m.purchase_price) + Decimal("1.00") if m.id == calc.materials[0].id else Decimal(m.purchase_price),
            price_basis=Decimal(m.price_basis),
        )
        for m in calc.materials
    ]
    updated = update_quote_item_calculation(
        quote.id,
        item.id,
        QuoteItemCalculationUpdate(
            site_time_minutes=Decimal(calc.site_time_minutes) + Decimal("5"),
            workshop_time_minutes=Decimal(calc.workshop_time_minutes),
            labor_rate=Decimal(calc.labor_rate),
            material_markup_pct=Decimal(calc.material_markup_pct),
            equipment_cost=Decimal(calc.equipment_cost),
            subcontractor_cost=Decimal(calc.subcontractor_cost),
            other_cost=Decimal(calc.other_cost),
            overhead_pct=Decimal(calc.overhead_pct),
            risk_profit_pct=Decimal(calc.risk_profit_pct),
            manual_sale_price=None,
            notes="Projektbezogene Erschwernis",
            materials=materials,
        ),
        db,
    )

    assert Decimal(updated.effective_sale_price) != old_ep
    db.refresh(service)
    assert Decimal(service.sale_price) == catalog_sale_price
    stored_item = db.get(QuoteItem, item.id)
    assert Decimal(stored_item.unit_price) == Decimal(updated.effective_sale_price)
