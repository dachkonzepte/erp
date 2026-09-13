"""Steuerschlüssel (seit 1.0.44).

Steuert sowohl den auf Angebot/Auftrag/Rechnung angezeigten Hinweistext als
auch den tatsächlich verwendeten vat_rate -- siehe ausführliche Begründung
am TaxKey-Modell in models.py. Analog zu payment_terms.py aufgebaut.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import TaxKey

DEFAULT_TAX_KEYS = [
    (10, "Privat", Decimal("19.00"), None, True),
    (20, "Gewerbe", Decimal("19.00"), None, False),
    (
        30, "§13b Bauleistungen (Reverse Charge)", Decimal("0.00"),
        "Steuerschuldnerschaft des Leistungsempfängers gemäß § 13b UStG. "
        "Diese Rechnung enthält keine Umsatzsteuer.",
        False,
    ),
    (
        40, "Solar (Nullsteuersatz)", Decimal("0.00"),
        "Lieferung/Installation unterliegt dem Nullsteuersatz gemäß § 12 Abs. 3 UStG.",
        False,
    ),
]


def ensure_default_tax_keys(db: Session) -> None:
    """Legt beim ersten Aufruf (leere Tabelle) die vier Standard-Schlüssel
    an. Rührt bestehende Schlüssel nicht an -- kein Zurücksetzen bei jedem
    Start, nur eine einmalige Grundausstattung. Die Texte für §13b/Solar
    sind ein Startpunkt, keine Rechtsberatung -- bitte vor Verwendung mit
    einem Steuerberater abgleichen."""
    if db.scalar(select(TaxKey.id).limit(1)) is not None:
        return
    for sort_order, label, vat_rate, notice_text, is_default in DEFAULT_TAX_KEYS:
        db.add(TaxKey(label=label, vat_rate=vat_rate, notice_text=notice_text, is_default=is_default, sort_order=sort_order))
    db.commit()


def list_tax_keys(db: Session, *, include_archived: bool = False) -> list[TaxKey]:
    stmt = select(TaxKey).order_by(TaxKey.sort_order, TaxKey.id)
    if not include_archived:
        stmt = stmt.where(TaxKey.archived == False)  # noqa: E712
    return db.scalars(stmt).all()


def get_default_tax_key(db: Session) -> TaxKey | None:
    return db.scalar(select(TaxKey).where(TaxKey.is_default == True, TaxKey.archived == False))  # noqa: E712


def create_tax_key(db: Session, label: str, vat_rate: Decimal, notice_text: str | None = None) -> TaxKey:
    key = TaxKey(
        label=label.strip(), vat_rate=vat_rate, notice_text=(notice_text.strip() if notice_text else None),
        sort_order=_next_sort_order(db),
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return key


def update_tax_key(db: Session, key_id: int, label: str, vat_rate: Decimal, notice_text: str | None = None) -> TaxKey | None:
    key = db.get(TaxKey, key_id)
    if key is None:
        return None
    key.label = label.strip()
    key.vat_rate = vat_rate
    key.notice_text = notice_text.strip() if notice_text else None
    db.commit()
    db.refresh(key)
    return key


def _next_sort_order(db: Session) -> int:
    highest = db.scalar(select(TaxKey.sort_order).order_by(TaxKey.sort_order.desc()).limit(1))
    return (highest or 0) + 10


def set_default_tax_key(db: Session, key_id: int) -> TaxKey | None:
    key = db.get(TaxKey, key_id)
    if key is None:
        return None
    for other in db.scalars(select(TaxKey).where(TaxKey.is_default == True)).all():  # noqa: E712
        other.is_default = False
    key.is_default = True
    db.commit()
    db.refresh(key)
    return key


def set_tax_key_archived(db: Session, key_id: int, archived: bool) -> TaxKey | None:
    key = db.get(TaxKey, key_id)
    if key is None:
        return None
    if key.is_default and archived:
        raise ValueError("Der Standard-Steuerschlüssel kann nicht archiviert werden.")
    key.archived = archived
    db.commit()
    db.refresh(key)
    return key
