"""Kontenstamm (Buchhaltung Stufe 2, erster Teil, Modul "buchhaltung") -- Sachkonten nach
SKR 04 für die Vorkontierung von Eingangsrechnungen (siehe app/incoming_invoices.py).

Reine Verwaltungstabelle (Muster app/tax_keys.py) -- Kontonummer + Bezeichnung + optionaler
Standard-Steuersatz, mehr als ein Label, deshalb echte Tabelle statt Optionsgruppe. KEIN
Löschen vorgesehen, nur Archivieren/Aktivieren (Account.active) -- ein bereits in einer
Eingangsrechnung verwendetes Konto darf nie verschwinden.

**Bewusst KEIN Startbestand** -- siehe Account-Klassendocstring (app/models.py) und CLAUDE.md
"Buchhaltung" -> "Kontenstamm" für die volle Begründung. Deshalb auch KEIN ensure_default_*()
wie bei app/tax_keys.py -- die Tabelle bleibt leer, bis der Betreiber selbst Konten anlegt oder
der spätere Datei-Import sie befüllt.

**ANDOCKPUNKT für den Datei-Import (Stufe 2, zweiter Teil, NICHT Teil dieser Version)**: ein
künftiger Import liest die Steuerberater-Kontendatei zeilenweise und ruft für jede Zeile
create_account()/update_account() auf (Upsert nach account_number, der stabile natürliche
Schlüssel) -- beide validieren bereits Eindeutigkeit der Kontonummer und den Steuersatz, keine
Änderung an diesen Funktionen nötig, wenn der Import gebaut wird."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Account

# Fester Code-Wert wie überall im Projekt (RecurringCost.TAX_RATES, IncomingInvoice.TAX_RATES) --
# bewusst eine eigene, lokale Kopie statt eines Imports aus einem Nachbarmodul (Muster: dieselbe
# triviale Drei-Werte-Konstante existiert bereits unabhängig in mehreren Domänen-Modulen dieses
# Projekts, kein gemeinsamer Import zwischen fachlich getrennten Bereichen).
ACCOUNT_TAX_RATES = (Decimal("19.00"), Decimal("7.00"), Decimal("0.00"))


def account_to_dict(account: Account) -> dict:
    return {
        "id": account.id,
        "account_number": account.account_number,
        "label": account.label,
        "default_tax_rate_pct": account.default_tax_rate_pct,
        "active": account.active,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def list_accounts(db: Session, *, include_inactive: bool = True) -> list[dict]:
    stmt = select(Account).order_by(Account.account_number)
    if not include_inactive:
        stmt = stmt.where(Account.active == True)  # noqa: E712
    return [account_to_dict(a) for a in db.scalars(stmt).all()]


def get_account(db: Session, account_id: int) -> dict | None:
    account = db.get(Account, account_id)
    return account_to_dict(account) if account is not None else None


def _validate_tax_rate(default_tax_rate_pct: Decimal | None) -> None:
    if default_tax_rate_pct is not None and default_tax_rate_pct not in ACCOUNT_TAX_RATES:
        raise ValueError(f"Unbekannter Steuersatz: {default_tax_rate_pct}")


def create_account(db: Session, *, account_number: str, label: str,
                    default_tax_rate_pct: Decimal | None = None, active: bool = True) -> dict:
    account_number = account_number.strip()
    if not account_number:
        raise ValueError("Bitte eine Kontonummer angeben.")
    _validate_tax_rate(default_tax_rate_pct)
    if db.scalar(select(Account).where(Account.account_number == account_number)) is not None:
        raise ValueError(f"Kontonummer {account_number} ist bereits vergeben.")
    account = Account(
        account_number=account_number, label=label.strip(),
        default_tax_rate_pct=default_tax_rate_pct, active=active,
    )
    db.add(account)
    db.commit()
    return account_to_dict(account)


def update_account(db: Session, account_id: int, *, account_number: str, label: str,
                    default_tax_rate_pct: Decimal | None = None, active: bool = True) -> dict | None:
    account = db.get(Account, account_id)
    if account is None:
        return None
    account_number = account_number.strip()
    if not account_number:
        raise ValueError("Bitte eine Kontonummer angeben.")
    _validate_tax_rate(default_tax_rate_pct)
    existing = db.scalar(
        select(Account).where(Account.account_number == account_number, Account.id != account_id)
    )
    if existing is not None:
        raise ValueError(f"Kontonummer {account_number} ist bereits vergeben.")
    account.account_number = account_number
    account.label = label.strip()
    account.default_tax_rate_pct = default_tax_rate_pct
    account.active = active
    db.commit()
    return account_to_dict(account)
