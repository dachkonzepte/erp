"""Schnellauftrag für Reparatur/Wartung (seit 1.2.12, Modul "wartungen").

Ein einzelner Reparatur- oder Wartungsauftrag soll sich in einem Schritt anlegen lassen,
ohne dass der Nutzer Projekt, Angebot und Beauftragung einzeln durchlaufen muss. Technisch
entsteht dabei trotzdem die normale Kette Project -> Quote -> Order (create_order_from_quote()
in app/orders.py verlangt zwingend mindestens eine QuoteItem-Position) -- dafür funktionieren
Rechnung, Zeiterfassung und Einsatzbericht anschließend ohne jeden Sonderfall weiter.

Die Platzhalter-Position ("Reparatur/Wartung nach Aufwand", 0,00 EUR) trägt bewusst keinen
Preis: abgerechnet wird später über "Rechnung aus Zeitbuchungen" (invoice_type="aufwand",
seit 1.2.2) auf Basis der tatsächlich gebuchten Stunden, nicht über diese LV-Position."""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from .berlin_time import berlin_today
from .models import Project, Quote
from .orders import create_order_from_quote
from .project_pipeline_columns import default_pipeline_column_id
from .projects import create_free_quote_item, next_project_number, next_quote_number
from .zugehoerigkeit import require_confirmed_property

ORDER_TYPES = ("reparatur", "wartung")
ORDER_TYPE_LABELS = {"reparatur": "Reparatur", "wartung": "Wartung"}


def auftrag_nach_aufwand(
    db: Session, *, customer_id: int, property_id: int | None, title: str, position: str, description: str | None = None,
    caseworker_employee_id: int | None = None, execution_start: date | None = None, confirm_property_customer: bool = False,
    commit: bool = True,
):
    """Projekt -> Angebot mit einer Position „<position>“ (1 pauschal, 0,00 €) -> Auftrag, ohne Vertragsentwurf: der Weg des Schnellauftrags, seit
    1.9.240 (Stufe 6, R3b, Punkt 2) auch für die Kranvermietung der Plantafel. commit=False: nichts wird festgeschrieben, der Aufrufer committet alles
    zusammen (die Kranvermietung: mit dem Einsatz -- eine Warnung lässt nichts zurück). Gibt (Projekt, Auftrag) zurück."""
    title = title.strip()
    if not title:
        raise ValueError("Bitte eine Bezeichnung angeben.")
    require_confirmed_property(db, customer_id, property_id, confirm_property_customer)

    project = Project(
        project_number=next_project_number(db), customer_id=customer_id, property_id=property_id,
        name=title, description=(description or None),
        pipeline_column_id=default_pipeline_column_id(db),
    )
    db.add(project)
    db.flush()

    quote = Quote(quote_number=next_quote_number(db), project_id=project.id, title=title)
    db.add(quote)
    db.flush()

    create_free_quote_item(
        db, quote, short_text=position, long_text=position,
        quantity=Decimal("1"), unit="pauschal", unit_price=Decimal("0"), position_type="normal",
        section_id=None, commit=commit,
    )
    if not commit:
        db.expire(quote)  # ohne Commit kennt quote.items die neue Position sonst nicht (create_order_from_quote() lädt das Angebot)

    # Seit 1.8.33 ohne automatischen Vertragsentwurf (nach Aufwand); von Hand bleibt er auf der Auftragsseite möglich.
    order = create_order_from_quote(
        db, quote.id, order_date=berlin_today(), execution_start=execution_start, execution_end=None,
        caseworker_employee_id=caseworker_employee_id, project_manager_employee_id=None,
        payment_terms=None, remarks=None, contract_draft=False, commit=commit,
    )
    return project, order


def create_quick_service_order(
    db: Session, *, customer_id: int, property_id: int | None, order_type: str, title: str,
    description: str | None = None, caseworker_employee_id: int | None = None,
    execution_start: date | None = None, confirm_property_customer: bool = False, commit: bool = True,
) -> dict:
    """confirm_property_customer (seit 1.8.70, Befund 2f): ein Objekt eines anderen Kunden (Generalunternehmer,
    Hausverwaltung) nur mit Bestätigung -- sonst PropertyCustomerMismatch (Router 409). Vorher verband der Schnellauftrag
    jeden Kunden mit jedem Objekt; Auftrag und Rechnung tragen das Objekt als Schnappschuss. Aufrufe im Prozess, die Kunde
    und Objekt aus einem bestehenden Datensatz übernehmen (Vertrag, Mangel), bestätigen selbst.

    Seit 1.9.245 (Stufe 6, R4, Punkt 0c, Befund R3b 5b) eine Transaktion wie die Kranvermietung: Projekt, Angebot, Position und Auftrag mit einem
    Commit am Ende (bis 1.9.244 dreimal unterwegs -- scheiterte ein späterer Schritt, blieben Projekt und Angebot ohne Auftrag stehen). Scheitert
    ein Schritt, nimmt die Sitzung alles zurück. commit=False: der Aufrufer committet den Schnellauftrag mit seiner eigenen Änderung zusammen
    (Folgeauftrag aus einem Befund, Wartung durchführen) und nimmt bei einem Fehler selbst zurück."""
    if order_type not in ORDER_TYPES:
        raise ValueError(f"Unbekannte Auftragsart: {order_type}")
    try:
        project, order = auftrag_nach_aufwand(
            db, customer_id=customer_id, property_id=property_id, title=title, position=f"{ORDER_TYPE_LABELS[order_type]} nach Aufwand",
            description=description, caseworker_employee_id=caseworker_employee_id, execution_start=execution_start,
            confirm_property_customer=confirm_property_customer, commit=False,
        )
        ergebnis = {"project_id": project.id, "order_id": order.id, "order_number": order.order_number}
        if commit:
            db.commit()
    except Exception:
        if commit:
            db.rollback()
        raise
    return ergebnis
