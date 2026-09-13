"""Router: properties

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 4 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.
"""

from fastapi import APIRouter
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Customer, Property
from ..schemas import PropertyCreate, PropertyOut, PropertyUpdate

router = APIRouter()

@router.get("/api/properties", response_model=list[PropertyOut])
def list_properties(customer_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(Property).order_by(Property.name)
    if customer_id is not None:
        stmt = stmt.where(Property.customer_id == customer_id)
    return db.scalars(stmt).all()


@router.get("/api/properties/{property_id}", response_model=PropertyOut)
def get_property(property_id: int, db: Session = Depends(get_db)):
    property_obj = db.get(Property, property_id)
    if property_obj is None:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden.")
    return property_obj


@router.put("/api/properties/{property_id}", response_model=PropertyOut)
def update_property(property_id: int, payload: PropertyUpdate, db: Session = Depends(get_db)):
    property_obj = db.get(Property, property_id)
    if property_obj is None:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden.")
    values = payload.model_dump()
    customer_id = values.pop("customer_id", None)
    if customer_id is not None:
        if db.get(Customer, customer_id) is None:
            raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
        property_obj.customer_id = customer_id
    for key, value in values.items():
        setattr(property_obj, key, value)
    db.commit()
    db.refresh(property_obj)
    return property_obj


@router.post("/api/properties", response_model=PropertyOut)
def create_property(payload: PropertyCreate, db: Session = Depends(get_db)):
    customer = db.get(Customer, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    property_obj = Property(**payload.model_dump())
    db.add(property_obj)
    db.commit()
    db.refresh(property_obj)
    return property_obj
