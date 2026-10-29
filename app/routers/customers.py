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
from datetime import datetime

from fastapi import Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..crm import compose_customer_name, ensure_customer_profile
from ..customer_documents import MAX_UPLOAD_BYTES, customer_directory, make_stored_filename
from ..dateiauslieferung import gespeicherter_typ
from ..database import get_db
from .. import akte_verlauf, kunde_verlauf
from ..kundenakte import kunde_kontext
from ..document_categories import resolve_category_id
from ..models import AppUser, Customer, CustomerDocument, CustomerExtraInfo, Property
from ..permissions import GELD_DOKUMENTE, ROLE_OFFICE_AUFTRAG, darf_geld, require_min_role
from .customer_documents import _customer_document_out
from ..schemas import (
    CustomerCreate, CustomerDocumentOut, CustomerExtraInfoCreate, CustomerExtraInfoOut,
    CustomerExtraInfoUpdate, CustomerOut, CustomerUpdate,
)

router = APIRouter()

# Seit "Rechtekonzept" (siehe CLAUDE.md): Kundendaten sind Büro-/Admin-Bereich, ein Monteur
# erreicht das, was er über einen Einsatz braucht, ausschließlich über
# GET /api/orders/{id}/property (app/routers/service_reports.py) -- nie über diese Datei.
_role_dep = Depends(require_min_role(ROLE_OFFICE_AUFTRAG, message="Kundendaten sind nur für Büro und Administratoren verfügbar."))


@router.get("/api/customers", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    customers = db.scalars(
        select(Customer)
        .options(selectinload(Customer.extra_infos), selectinload(Customer.profile))
        .order_by(Customer.name)
    ).all()
    # Seit 1.8.76 legt das Lesen kein fehlendes Profil mehr an (vorher samt Kundennummer aus dem Nummernkreis -- eine Anzeige
    # verbrauchte eine Nummer, Regel 23). Jeder Anlegeweg legt das Profil an; ein Altkunde ohne Profil zeigt keine Nummer, bis
    # er gespeichert wird.
    return customers


@router.get("/api/customers/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    customer = db.scalar(
        select(Customer)
        .options(selectinload(Customer.extra_infos), selectinload(Customer.profile))
        .where(Customer.id == customer_id)
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    return customer  # seit 1.8.76 ohne Anlegen eines fehlenden Profils, siehe list_customers()


@router.get("/api/customers/{customer_id}/akte")
def get_customer_akte(customer_id: int, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.9.135 (Stufe 5, R3, Punkt 1): was die Kundenakte /customers/{id} beim Laden braucht -- Zähler der Reiter, je Projekt Status und
    Zahlen, Geld (unbezahlt, überfällig, Guthaben, je Jahr abgerechnet und bezahlt) und die Vorschläge für das Guthaben
    (app/kundenakte.py::kunde_kontext()). Büro – Auftrag liest alles, gebucht wird über die Wege mit require_geld."""
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    return kunde_kontext(db, customer)


@router.get("/api/customers/{customer_id}/verlauf")
def get_customer_verlauf(customer_id: int, art: list[str] = Query(default=[]), vor: datetime | None = None,
                         db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    """Seit 1.9.136 (Stufe 5, R3, Punkt 1): der Verlauf der Kundenakte -- Änderungen am Kunden, Kundenwissen, Objekten (samt Dachflächen),
    Anfragen, seine Zahlungen und der Versand seiner Dokumente, eine Zeile je Aktion (app/kunde_verlauf.py), Filter nach Art, Seiten über `vor`.
    Geschwärzt wie /api/audit-logs; „Zustellung nachtragen“ an Rechnung und Mahnung nach darf_geld() (wie der Verlauf der Akte)."""
    from ..email_dispatch import list_dispatches
    from ..models import AuditLog
    from .audit import sichtbar

    if db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    unbekannt = [a for a in art if a not in kunde_verlauf.ARTEN]
    if unbekannt:
        raise HTTPException(status_code=422, detail=f"Unbekannte Art: {', '.join(unbekannt)}.")
    stmt = select(AuditLog).where(kunde_verlauf.zeilen_bedingung(db, customer_id))
    if vor is not None:
        stmt = stmt.where(AuditLog.occurred_at < vor)
    zeilen, weitere = akte_verlauf.zeilen_seite(db, stmt.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()))
    versand = list_dispatches(db, customer_id=customer_id, limit=1000)["items"]
    versand = [e for e in versand if (vor is None or e["created_at"] < vor) and (not weitere or e["created_at"] >= zeilen[-1].occurred_at)]
    for e in versand:  # wie GET /api/email-dispatches (seit 1.9.111): Rechnung und Mahnung nur nach darf_geld()
        geld = e["document_type"] not in GELD_DOKUMENTE or darf_geld(_role)
        e["can_record_outcome"] = e["can_record_outcome"] and geld
        e["zustellung_nachtragen"] = geld and e["document_id"] is not None
    return kunde_verlauf.strom(sichtbar(db, zeilen, _role), versand, arten=set(art) or None, weitere=weitere)


@router.put("/api/customers/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, payload: CustomerUpdate, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    customer = db.scalar(
        select(Customer)
        .options(selectinload(Customer.extra_infos), selectinload(Customer.properties), selectinload(Customer.profile))
        .where(Customer.id == customer_id)
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")

    # Seit 1.9.136 (Stufe 5, R3, Punkt 1) ein Teil-Update (Regel 22): nur gesendete Felder -- die Kundenakte schickt aus dem Dialog
    # „Stammdaten bearbeiten“ nur, was geändert ist; bis 1.9.135 übernahm der Handler jedes Feld (Vorgabe „Privatkunde“, „Deutschland“).
    werte = payload.model_dump(exclude_unset=True)
    for key, value in werte.items():
        if key not in ("category", "customer_number", "default_payment_term_id"):
            setattr(customer, key, value)
    customer.name = compose_customer_name(customer.salutation, customer.title, customer.first_name, customer.last_name)
    try:
        ensure_customer_profile(
            db, customer, werte.get("category"), werte.get("customer_number"),
            default_payment_term_id=werte.get("default_payment_term_id"), set_payment_term="default_payment_term_id" in werte,
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
    customer_id: int, payload: CustomerExtraInfoCreate, db: Session = Depends(get_db, scope="function"),
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
    customer_id: int, info_id: int, payload: CustomerExtraInfoUpdate, db: Session = Depends(get_db, scope="function"),
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
def delete_customer_extra_info(customer_id: int, info_id: int, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    info = db.get(CustomerExtraInfo, info_id)
    if info is None or info.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Kundeninformation nicht gefunden.")
    db.delete(info)
    db.commit()
    return {"status": "deleted", "id": info_id}


@router.post("/api/customers", response_model=CustomerOut)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
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
def list_customer_documents(customer_id: int, db: Session = Depends(get_db, scope="function"), _role: AppUser = _role_dep):
    if db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    docs = db.scalars(select(CustomerDocument).where(CustomerDocument.customer_id == customer_id).order_by(CustomerDocument.uploaded_at.desc())).all()
    return [_customer_document_out(d) for d in docs]


@router.post("/api/customers/{customer_id}/documents", response_model=CustomerDocumentOut)
# Seit 1.8.114 def statt async def: im Threadpool, die Datenbank nie auf der Event-Loop (Punkt 1a, tests/test_v419_verbindungen.py).
def upload_customer_document(
    customer_id: int, file: UploadFile = File(...), category: str = Form("Sonstiges"), subfolder: str | None = Form(None),
    description: str | None = Form(None), document_date: str | None = Form(None), db: Session = Depends(get_db, scope="function"),
    _role: AppUser = _role_dep,
):
    if db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden.")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Bitte eine Datei auswählen.")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
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
        stored_filename=stored, content_type=gespeicherter_typ(data), file_size=len(data), description=(description or None), document_date=parsed_date,
    )
    db.add(doc); db.commit(); db.refresh(doc)
    return _customer_document_out(doc)
