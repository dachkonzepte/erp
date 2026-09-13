from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Customer, Project
from app.projects import next_project_number


def test_project_number_sequence():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    customer = Customer(name="Testkunde", last_name="Testkunde")
    db.add(customer)
    db.flush()
    assert next_project_number(db).endswith("0001")
    db.add(Project(project_number=next_project_number(db), customer_id=customer.id, name="Testprojekt"))
    db.commit()
    assert next_project_number(db).endswith("0002")

from app.main import create_customer
from app.schemas import CustomerCreate, CustomerExtraInfoCreate
from app.models import Property, CustomerExtraInfo
from sqlalchemy import select


def test_customer_creates_main_property_and_extra_infos():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    payload = CustomerCreate(
        last_name="Familie Muster",
        street="Musterstraße 12",
        postal_code="52531",
        city="Übach-Palenberg",
        email="haupt@example.de",
        phone="02451 12345",
        extra_infos=[
            CustomerExtraInfoCreate(info_type="phone", label="Mobil", value="0171 1234567"),
            CustomerExtraInfoCreate(info_type="birthday", label="Herr Muster", value="1985-04-16"),
            CustomerExtraInfoCreate(info_type="info", label="Interesse", value="PV bei Dachsanierung ansprechen"),
        ],
    )

    customer = create_customer(payload, db)
    prop = db.scalar(select(Property).where(Property.customer_id == customer.id))
    extras = db.scalars(select(CustomerExtraInfo).where(CustomerExtraInfo.customer_id == customer.id)).all()

    assert prop is not None
    assert prop.name == "Hauptadresse"
    assert prop.street == "Musterstraße 12"
    assert prop.postal_code == "52531"
    assert prop.city == "Übach-Palenberg"
    assert len(extras) == 3
    assert {x.info_type for x in extras} == {"phone", "birthday", "info"}

from app.main import (
    update_customer,
    create_customer_extra_info,
    update_customer_extra_info,
    delete_customer_extra_info,
    create_property,
    update_property,
)
from app.schemas import CustomerUpdate, CustomerExtraInfoUpdate, PropertyCreate, PropertyUpdate


def test_customer_record_updates_main_address_and_crm_data():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    customer = create_customer(CustomerCreate(
        last_name="Kunde Alt",
        street="Altstraße 1",
        postal_code="52000",
        city="Aachen",
        extra_infos=[],
    ), db)

    updated = update_customer(customer.id, CustomerUpdate(
        last_name="Kunde Neu",
        contact_person="Max Mustermann",
        street="Neustraße 7",
        postal_code="52531",
        city="Übach-Palenberg",
        email="kunde@example.de",
        phone="02451 999",
        notes="Bestandskunde",
    ), db)
    main_property = db.scalar(select(Property).where(Property.customer_id == customer.id, Property.name == "Hauptadresse"))
    assert updated.name == "Kunde Neu"
    assert main_property.street == "Neustraße 7"
    assert main_property.postal_code == "52531"
    assert main_property.city == "Übach-Palenberg"

    info = create_customer_extra_info(customer.id, CustomerExtraInfoCreate(
        info_type="phone", label="Mobil", value="0171 111111"
    ), db)
    info = update_customer_extra_info(customer.id, info.id, CustomerExtraInfoUpdate(
        info_type="phone", label="Privat mobil", value="0171 222222"
    ), db)
    assert info.label == "Privat mobil"
    assert info.value == "0171 222222"
    result = delete_customer_extra_info(customer.id, info.id, db)
    assert result["status"] == "deleted"

    second = create_property(PropertyCreate(
        customer_id=customer.id, name="Mietshaus", street="Objektweg 4", postal_code="52062", city="Aachen"
    ), db)
    second = update_property(second.id, PropertyUpdate(
        name="MFH Aachen", street="Objektweg 4", postal_code="52062", city="Aachen", notes="Flachdach"
    ), db)
    assert second.name == "MFH Aachen"
    assert second.notes == "Flachdach"
