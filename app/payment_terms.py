"""Zahlungsbedingungen (seit 1.0.37).

Eigenständige Verwaltung statt Teil der generischen Auswahllisten -- siehe
Begründung am PaymentTerm-Modell in models.py. Wird von Kunden (als
Vorbelegung) und Rechnungen (zur Fälligkeitsberechnung) referenziert.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import PaymentTerm

DEFAULT_TERMS = [
    (10, "Sofort ohne Abzug", 0, False),
    (20, "14 Tage netto", 14, True),
    (30, "30 Tage netto", 30, False),
]


def ensure_default_payment_terms(db: Session) -> None:
    """Legt beim ersten Aufruf (leere Tabelle) die drei Standard-Bedingungen
    an. Rührt bestehende Bedingungen nicht an -- kein Zurücksetzen bei jedem
    Start, nur eine einmalige Grundausstattung."""
    if db.scalar(select(PaymentTerm.id).limit(1)) is not None:
        return
    for sort_order, label, days, is_default in DEFAULT_TERMS:
        db.add(PaymentTerm(label=label, days=days, is_default=is_default, sort_order=sort_order))
    db.commit()


def list_payment_terms(db: Session, *, include_archived: bool = False) -> list[PaymentTerm]:
    stmt = select(PaymentTerm).order_by(PaymentTerm.sort_order, PaymentTerm.id)
    if not include_archived:
        stmt = stmt.where(PaymentTerm.archived == False)  # noqa: E712
    return db.scalars(stmt).all()


def get_default_payment_term(db: Session) -> PaymentTerm | None:
    return db.scalar(select(PaymentTerm).where(PaymentTerm.is_default == True, PaymentTerm.archived == False))  # noqa: E712


def _validate_skonto(days: int, skonto_percent, skonto_days: int | None) -> None:
    has_percent = skonto_percent is not None
    has_days = skonto_days is not None
    if has_percent != has_days:
        raise ValueError("Skonto-Prozentsatz und Skonto-Frist müssen zusammen angegeben werden (oder beide leer bleiben).")
    if has_days and skonto_days > days:
        raise ValueError("Die Skonto-Frist darf nicht länger sein als die reguläre Zahlungsfrist.")
    if has_days and skonto_days < 0:
        raise ValueError("Die Skonto-Frist darf nicht negativ sein.")


def create_payment_term(
    db: Session, label: str, days: int, skonto_percent=None, skonto_days: int | None = None,
    text_template: str | None = None,
) -> PaymentTerm:
    _validate_skonto(days, skonto_percent, skonto_days)
    term = PaymentTerm(
        label=label.strip(), days=days, skonto_percent=skonto_percent, skonto_days=skonto_days,
        text_template=(text_template.strip() if text_template else None), sort_order=(_next_sort_order(db)),
    )
    db.add(term)
    db.commit()
    db.refresh(term)
    return term


def update_payment_term(
    db: Session, term_id: int, label: str, days: int, skonto_percent=None, skonto_days: int | None = None,
    text_template: str | None = None,
) -> PaymentTerm | None:
    term = db.get(PaymentTerm, term_id)
    if term is None:
        return None
    _validate_skonto(days, skonto_percent, skonto_days)
    term.label = label.strip()
    term.days = days
    term.skonto_percent = skonto_percent
    term.skonto_days = skonto_days
    term.text_template = text_template.strip() if text_template else None
    db.commit()
    db.refresh(term)
    return term


def _next_sort_order(db: Session) -> int:
    highest = db.scalar(select(PaymentTerm.sort_order).order_by(PaymentTerm.sort_order.desc()).limit(1))
    return (highest or 0) + 10


def set_default_payment_term(db: Session, term_id: int) -> PaymentTerm | None:
    term = db.get(PaymentTerm, term_id)
    if term is None:
        return None
    for other in db.scalars(select(PaymentTerm).where(PaymentTerm.is_default == True)).all():  # noqa: E712
        other.is_default = False
    term.is_default = True
    db.commit()
    db.refresh(term)
    return term


def set_payment_term_archived(db: Session, term_id: int, archived: bool) -> PaymentTerm | None:
    term = db.get(PaymentTerm, term_id)
    if term is None:
        return None
    if term.is_default and archived:
        raise ValueError("Die Standard-Zahlungsbedingung kann nicht archiviert werden.")
    term.archived = archived
    db.commit()
    db.refresh(term)
    return term
