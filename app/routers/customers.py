"""Router: customers

Automatisch aus app/main.py in Version 1.0.7 extrahiert (main.py-Aufteilung,
siehe README). Enthaelt 7 Endpunkt(e), unveraendert
uebernommen -- reine Verschiebung, keine Verhaltensaenderung.

list_customer_documents/upload_customer_document (seit 1.0.54) neu ergänzt,
nach exakt demselben Muster wie list_project_documents/upload_project_document
in projects.py -- siehe dort für die Begründung der einzelnen Schritte.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi import Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..crm import compose_customer_name, ensure_customer_profile, ensure_customer_profiles
from ..customer_documents import MAX_UPLOAD_BYTES, customer_directory, make_stored_filename
from ..database import get_db
from ..document_categories import resolve_category_id
from ..models import AppUser, Customer, CustomerDocument, CustomerExtraInfo, Property
from ..permissions import ROLE_ADMIN, ROLE_OFFICE, require_role
from .customer_documents import _customer_document_out
from ..schemas import (
    CustomerCreate, CustomerDocumentOut, CustomerExtraInfoCreate, CustomerExtraInfoOut,
    CustomerExtraInfoUpdate, CustomerOut, CustomerUpdate,
)

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Kundendaten sind Büro-/Admin-Bereich, ein Monteur
# erreicht das, was er über einen Einsatz braucht, ausschließlich über
# GET /api/orders/{id}/property (app/routers/service_reports.py) -- nie über diese Datei.
_role_dep = Depends(require_role(ROLE_ADMIN, ROLE_OFFICE, message="Kundendaten sind nur für Büro und Administratoren verfügbar."))


@router.get("/api/customers", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db), _role: AppUser = _role_dep):
    customers = db.scalars(
        select(Customer)
        .options(selectinload(Customer.extra_infos), selectinload(Customer.profile))
        .order_by(Customer.name)
    ).all()
    ensure_customer_profiles(db, customers)
    return customers


@router.get("/api/customers/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    customer = db.scalar(
        select(Customer)
        .options(selectinload(Customer.extra_infos), selectinload(Customer.profile))
        .where(Customer.id == customer_id)
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    ensure_customer_profile(db, customer)
    db.commit()
    return customer


@router.put("/api/customers/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, payload: CustomerUpdate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    customer = db.scalar(
        select(Customer)
        .options(selectinload(Customer.extra_infos), selectinload(Customer.properties), selectinload(Customer.profile))
        .where(Customer.id == customer_id)
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")

    for key, value in payload.model_dump(exclude={"category", "customer_number", "default_payment_term_id"}).items():
        setattr(customer, key, value)
    customer.name = compose_customer_name(customer.salutation, customer.title, customer.first_name, customer.last_name)
    try:
        ensure_customer_profile(
            db, customer, payload.category, payload.customer_number,
            default_payment_term_id=payload.default_payment_term_id, set_payment_term=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    # Die Hauptadresse bleibt synchron mit den Kundenstammdaten. Andere Objekte
    # sind eigenständige Baustellen-/Objektadressen und werden nicht verändert.
    main_property = next((p for p in customer.properties if p.is_primary_address), None)
    if main_property is None:
        # Fallback über den Namen für eine Zeile, die (noch) nicht geflaggt ist -- verhindert
        # eine doppelte "Hauptadresse"-Zeile, falls is_primary_address aus irgendeinem Grund
        # nicht gesetzt wurde (siehe CLAUDE.md "Objekte: Hauptadressen kennzeichnen und
        # ausblenden"); heilt eine solche Zeile beim nächsten Speichern gleich mit aus.
        main_property = next((p for p in customer.properties if p.name == "Hauptadresse"), None)
    if main_property is None:
        main_property = Property(customer_id=customer.id, name="Hauptadresse", is_primary_address=True)
        db.add(main_property)
    main_property.is_primary_address = True
    main_property.street = customer.street
    main_property.postal_code = customer.postal_code
    main_property.city = customer.city
    if not main_property.notes:
        main_property.notes = "Automatisch aus der Kunden-Hauptadresse angelegt."

    db.commit()
    return db.scalar(
        select(Customer)
        .options(selectinload(Customer.extra_infos), selectinload(Customer.profile))
        .where(Customer.id == customer_id)
    )


@router.post("/api/customers/{customer_id}/extra-infos", response_model=CustomerExtraInfoOut)
def create_customer_extra_info(
    customer_id: int, payload: CustomerExtraInfoCreate, db: Session = Depends(get_db),
    _role: AppUser = _role_dep,
):
    if db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    info = CustomerExtraInfo(customer_id=customer_id, **payload.model_dump())
    db.add(info)
    db.commit()
    db.refresh(info)
    return info


@router.put("/api/customers/{customer_id}/extra-infos/{info_id}", response_model=CustomerExtraInfoOut)
def update_customer_extra_info(
    customer_id: int, info_id: int, payload: CustomerExtraInfoUpdate, db: Session = Depends(get_db),
    _role: AppUser = _role_dep,
):
    info = db.get(CustomerExtraInfo, info_id)
    if info is None or info.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Kundeninformation nicht gefunden.")
    for key, value in payload.model_dump().items():
        setattr(info, key, value)
    db.commit()
    db.refresh(info)
    return info


@router.delete("/api/customers/{customer_id}/extra-infos/{info_id}")
def delete_customer_extra_info(customer_id: int, info_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    info = db.get(CustomerExtraInfo, info_id)
    if info is None or info.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Kundeninformation nicht gefunden.")
    db.delete(info)
    db.commit()
    return {"status": "deleted", "id": info_id}


@router.post("/api/customers", response_model=CustomerOut)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    data = payload.model_dump(exclude={"extra_infos", "category", "customer_number", "default_payment_term_id"})
    data["name"] = compose_customer_name(data.get("salutation"), data.get("title"), data.get("first_name"), data["last_name"])
    customer = Customer(**data)
    for info in payload.extra_infos:
        customer.extra_infos.append(CustomerExtraInfo(**info.model_dump()))
    db.add(customer)
    db.flush()
    try:
        ensure_customer_profile(
            db, customer, payload.category, payload.customer_number,
            default_payment_term_id=payload.default_payment_term_id, set_payment_term=True,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    # Die Kunden-Hauptadresse ist automatisch das erste Objekt. Dadurch kann ein
    # neues Projekt sofort auf die Hauptadresse gebucht werden, ohne dass sie
    # noch einmal manuell als Objekt erfasst werden muss.
    main_property = Property(
        customer_id=customer.id,
        name="Hauptadresse",
        street=customer.street,
        postal_code=customer.postal_code,
        city=customer.city,
        notes="Automatisch aus der Kunden-Hauptadresse angelegt.",
        is_primary_address=True,
    )
    db.add(main_property)
    db.commit()
    customer = db.scalar(
        select(Customer)
        .options(selectinload(Customer.extra_infos), selectinload(Customer.profile))
        .where(Customer.id == customer.id)
    )
    return customer


@router.get("/api/customers/{customer_id}/documents", response_model=list[CustomerDocumentOut])
def list_customer_documents(customer_id: int, db: Session = Depends(get_db), _role: AppUser = _role_dep):
    if db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    docs = db.scalars(select(CustomerDocument).where(CustomerDocument.customer_id == customer_id).order_by(CustomerDocument.uploaded_at.desc())).all()
    return [_customer_document_out(d) for d in docs]


@router.post("/api/customers/{customer_id}/documents", response_model=CustomerDocumentOut)
async def upload_customer_document(
    customer_id: int, file: UploadFile = File(...), category: str = Form("Sonstiges"), subfolder: str | None = Form(None),
    description: str | None = Form(None), document_date: str | None = Form(None), db: Session = Depends(get_db),
    _role: AppUser = _role_dep,
):
    if db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswählen.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei ist größer als 50 MB.")
    stored = make_stored_filename(file.filename)
    target = customer_directory(customer_id) / stored
    target.write_bytes(data)
    from datetime import date as _date
    parsed_date = None
    if document_date:
        try:
            parsed_date = _date.fromisoformat(document_date)
        except ValueError:
            target.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="Ungültiges Dokumentdatum.")
    category_value = (category or "Sonstiges").strip()
    doc = CustomerDocument(
        customer_id=customer_id, category=category_value, category_id=resolve_category_id(db, category_value),
        subfolder=(subfolder.strip() or None) if isinstance(subfolder, str) else None,
        original_filename=Path(file.filename).name,
        stored_filename=stored, content_type=file.content_type, file_size=len(data), description=(description or None), document_date=parsed_date,
    )
    db.add(doc); db.commit(); db.refresh(doc)
    return _customer_document_out(doc)
