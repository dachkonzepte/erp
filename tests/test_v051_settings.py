from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crm import ensure_customer_profile
from app.database import Base
from app.models import Customer, CustomerProfile
from app.settings import (
    format_sequence_number,
    get_or_create_general_settings,
    preview_number,
    update_sequence,
)


def new_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_number_format_and_start_value():
    db = new_db()
    sequence = update_sequence(
        db,
        "customer",
        format_pattern="KD-{YY}-{NNNNNN}",
        start_value=500,
        next_value=500,
        reset_yearly=False,
    )
    assert sequence.next_value == 500
    assert preview_number(db, "customer") == f"KD-{str(datetime.now().year)[-2:]}-000500"
    assert format_sequence_number("ALT-{NNN}", 7) == "ALT-007"


def test_manual_customer_number_does_not_consume_normal_sequence():
    db = new_db()
    update_sequence(
        db,
        "customer",
        format_pattern="K-{YYYY}-{NNNN}",
        start_value=1000,
        next_value=1000,
        reset_yearly=True,
    )
    legacy = Customer(name="Bestandskunde", last_name="Bestandskunde")
    db.add(legacy)
    db.flush()
    ensure_customer_profile(db, legacy, "Privatkunde", "4711")
    db.commit()
    assert legacy.customer_number == "4711"
    assert preview_number(db, "customer").endswith("1000")

    fresh = Customer(name="Neukunde", last_name="Neukunde")
    db.add(fresh)
    db.flush()
    ensure_customer_profile(db, fresh, "Privatkunde")
    db.commit()
    assert fresh.customer_number.endswith("1000")
    assert preview_number(db, "customer").endswith("1001")


def test_duplicate_customer_number_is_rejected():
    db = new_db()
    a = Customer(name="A", last_name="A")
    b = Customer(name="B", last_name="B")
    db.add_all([a, b])
    db.flush()
    ensure_customer_profile(db, a, customer_number="ALT-100")
    db.commit()
    with pytest.raises(ValueError):
        ensure_customer_profile(db, b, customer_number="ALT-100")


def test_company_settings_are_available():
    db = new_db()
    settings = get_or_create_general_settings(db)
    assert settings.company_name == "DACHKONZEPTE Rödchen GmbH"
    assert float(settings.default_vat_rate) == 19.0
