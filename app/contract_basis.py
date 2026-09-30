"""Vertragsgrundlage an Angebot und Auftrag (seit 1.8.21, Stufe 2b, Runde 2b-1a).

Drei feste Schlüssel -- nie umbenennen, sie stehen in quote_document_meta.contract_basis,
orders.contract_basis und contract_basis_clauses.basis_key:

- ``vob_b``: VOB/B (Vorgabe für Kunden, die keine Verbraucher sind)
- ``bgb_vob_c_4_5``: BGB-Bauvertrag mit VOB/C Abschnitt 4 und 5 (Vorgabe für Verbraucher)
- ``bgb``: BGB ohne VOB (alle Angebote und Aufträge von vor 1.8.21)

Der Klauseltext je Grundlage wird in den Einstellungen gepflegt und nur gedruckt, wenn er rechtlich
geprüft ist (Datum und Name gesetzt). Ohne geprüfte Klausel zeigt der Editor eine Warnung, das PDF
enthält dann nichts dazu. Rollenlos wie jede Geschäftslogik; wer ändern darf, entscheidet der Router.
"""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .berlin_time import berlin_today
from .models import ContractBasisClause, Customer, Order, OrderContractBasisChange

CONTRACT_BASES: dict[str, str] = {
    "vob_b": "VOB/B",
    "bgb_vob_c_4_5": "BGB mit VOB/C Abschnitt 4 und 5",
    "bgb": "BGB (ohne VOB)",
}
LEGACY_CONTRACT_BASIS = "bgb"
CONSUMER_DEFAULT_BASIS = "bgb_vob_c_4_5"
BUSINESS_DEFAULT_BASIS = "vob_b"

MAX_REASON_LENGTH = 2000


def contract_basis_label(key: str | None) -> str | None:
    if key is None:
        return None
    return CONTRACT_BASES.get(key, key)


def validate_contract_basis(key: str | None) -> str:
    value = (key or "").strip()
    if value not in CONTRACT_BASES:
        raise ValueError(f"Unbekannte Vertragsgrundlage: {key!r}.")
    return value


def default_contract_basis_for_customer(customer: Customer | None) -> str:
    """Vorgabe für ein NEUES Angebot: Verbraucher -> BGB mit VOB/C 4 und 5, sonst VOB/B. Ohne
    Kunden (sollte nicht vorkommen) die Verbraucher-Vorgabe, wie das Feld selbst."""
    if customer is None or customer.is_consumer is None or customer.is_consumer:
        return CONSUMER_DEFAULT_BASIS
    return BUSINESS_DEFAULT_BASIS


def _clause_row(db: Session, key: str) -> ContractBasisClause | None:
    return db.scalar(select(ContractBasisClause).where(ContractBasisClause.basis_key == key))


def clause_is_reviewed(row: ContractBasisClause | None) -> bool:
    return bool(
        row is not None and (row.clause_text or "").strip()
        and row.reviewed_on is not None and (row.reviewed_by or "").strip()
    )


def printable_clause_text(db: Session, key: str | None) -> str | None:
    """Der Klauseltext für das PDF -- nur, wenn rechtlich geprüft, sonst None (nichts drucken)."""
    if not key:
        return None
    row = _clause_row(db, key)
    return row.clause_text.strip() if clause_is_reviewed(row) else None


def clause_to_dict(key: str, row: ContractBasisClause | None) -> dict:
    return {
        "basis_key": key,
        "label": CONTRACT_BASES[key],
        "clause_text": row.clause_text if row else None,
        "reviewed_on": row.reviewed_on if row else None,
        "reviewed_by": row.reviewed_by if row else None,
        "reviewed": clause_is_reviewed(row),
        "updated_at": row.updated_at if row else None,
        "updated_by_name": row.updated_by_name if row else None,
    }


def list_clauses(db: Session) -> list[dict]:
    rows = {r.basis_key: r for r in db.scalars(select(ContractBasisClause)).all()}
    return [clause_to_dict(key, rows.get(key)) for key in CONTRACT_BASES]


def contract_basis_options(db: Session) -> list[dict]:
    """Auswahl für Angebots-Editor und Auftragsseite, mit dem Prüfstand je Klausel."""
    rows = {r.basis_key: r for r in db.scalars(select(ContractBasisClause)).all()}
    return [
        {"key": key, "label": label, "clause_reviewed": clause_is_reviewed(rows.get(key))}
        for key, label in CONTRACT_BASES.items()
    ]


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def update_clause(
    db: Session, key: str, *, clause_text: str | None, reviewed_on: date | None,
    reviewed_by: str | None, actor_name: str = "System",
) -> tuple[dict, bool]:
    """Speichert Klauseltext und Prüfangaben. Rückgabe: (Klausel, review_reset).

    Regeln: "geprüft am" und "durch" nur zusammen; "geprüft am" nicht in der Zukunft; ohne Text keine
    Prüfangabe. Ändert sich der Text und kommen dieselben Prüfangaben wie bisher mit (die Prüfung
    galt dem alten Text), fallen sie weg -- review_reset=True, die Oberfläche sagt es dazu."""
    key = validate_contract_basis(key)
    text = _clean(clause_text)
    by = _clean(reviewed_by)
    if (reviewed_on is None) != (by is None):
        raise ValueError("„Rechtlich geprüft am“ und „durch“ bitte gemeinsam angeben oder beide leer lassen.")
    if reviewed_on is not None and reviewed_on > berlin_today():
        raise ValueError("„Rechtlich geprüft am“ darf nicht in der Zukunft liegen.")
    if text is None and reviewed_on is not None:
        raise ValueError("Ohne Klauseltext gibt es nichts, das geprüft sein könnte.")

    row = _clause_row(db, key)
    if row is None:
        row = ContractBasisClause(basis_key=key)
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
        except IntegrityError:
            # Gleichzeitig zum ersten Mal gespeichert -- die andere Zeile übernehmen (CLAUDE.md,
            # "Self-Seeding gegen gleichzeitigen ersten Zugriff absichern").
            row = _clause_row(db, key)

    review_reset = False
    text_changed = (row.clause_text or None) != text
    if text_changed and reviewed_on is not None and reviewed_on == row.reviewed_on and by == row.reviewed_by:
        reviewed_on, by = None, None
        review_reset = True
    row.clause_text = text
    row.reviewed_on = reviewed_on
    row.reviewed_by = by
    row.updated_by_name = actor_name or "System"
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return clause_to_dict(key, row), review_reset


def change_order_contract_basis(
    db: Session, order: Order, *, contract_basis: str, reason: str, actor_name: str = "System",
) -> OrderContractBasisChange:
    """Ändert die Vertragsgrundlage am Auftrag -- nur mit Begründung, mit Historie. Danach gilt sie
    als am Auftrag festgelegt: der Abgleich mit dem Angebot überschreibt sie nicht mehr."""
    new_basis = validate_contract_basis(contract_basis)
    text = (reason or "").strip()
    if not text:
        raise ValueError("Bitte eine Begründung für die Änderung angeben.")
    if len(text) > MAX_REASON_LENGTH:
        raise ValueError(f"Die Begründung darf höchstens {MAX_REASON_LENGTH} Zeichen lang sein.")
    if new_basis == order.contract_basis:
        raise ValueError("Der Auftrag hat bereits diese Vertragsgrundlage.")
    change = OrderContractBasisChange(
        order_id=order.id, old_basis=order.contract_basis, new_basis=new_basis,
        reason=text, changed_by_name=actor_name or "System",
    )
    db.add(change)
    order.contract_basis = new_basis
    order.contract_basis_manual = True
    db.commit()
    db.refresh(change)
    return change


def contract_basis_change_to_dict(change: OrderContractBasisChange) -> dict:
    return {
        "id": change.id,
        "order_id": change.order_id,
        "old_basis": change.old_basis,
        "old_label": contract_basis_label(change.old_basis),
        "new_basis": change.new_basis,
        "new_label": contract_basis_label(change.new_basis),
        "reason": change.reason,
        "changed_by_name": change.changed_by_name,
        "changed_at": change.changed_at,
    }


def list_order_contract_basis_changes(db: Session, order_id: int) -> list[dict]:
    rows = db.scalars(
        select(OrderContractBasisChange)
        .where(OrderContractBasisChange.order_id == order_id)
        .order_by(OrderContractBasisChange.id.desc())
    ).all()
    return [contract_basis_change_to_dict(r) for r in rows]
