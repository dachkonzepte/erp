"""Sperren am Auftrag (seit 1.8.82, R4a Punkt 2; Befund R4 Nebenbefund 1, docs/archiv/befund-vor-echtbetrieb.md "Umsetzung 1.8.82").

Der Auftrag ist der Maßstab seiner Rechnungen -- bis 1.8.81 ließen sich Menge, Einheit, Einheitspreis, Texte, "in Summe" und der
Steuersatz jederzeit ändern, auch nach der Schlussrechnung (Befund R4 b: Abschlag zu 50 €, Schlussrechnung danach zu 60 €, "noch
offen" trotz gültiger Schlussrechnung). Seither:

- **Einheitspreis, Einheit und "in Summe" einer Position**: gesperrt, sobald eine gültige Rechnung (festgeschrieben, nicht storniert,
  kein Storno) sie abrechnet -- eine Rechnungsposition mit Verweis auf sie und Ist ≠ 0 (eine Position mit Ist 0 steht auf der
  Rechnung nicht, app/invoices.py::visible_items()). Ist die Rechnung storniert, ist die Position wieder frei.
- **Steuersatz** (Steuerschlüssel) des Auftrags: gesperrt, sobald eine gültige Rechnung besteht, gleich welcher Art.
- **Mengen und Texte**: bis zur Schlussrechnung änderbar.
- **Nach einer gültigen Schlussrechnung**: alles -- Positionen, LV-Titel, Steuersatz. Seit 1.8.86 ebenso nach einer gültigen
  abschließenden Rechnung aus Aufwand (Auftrag nach Aufwand, R4b Punkt 6).

Abgelehnt wird nur eine tatsächliche Änderung (OrderLocked, Router 409 mit dem Grund); ein Speichern mit unveränderten Werten geht
durch. Geprüft unter der Sperre der Auftragszeile (app/invoices.py::lock_order_invoices()) -- dieselbe wie das Festschreiben: eine
Änderung, die auf ein gleichzeitiges Festschreiben wartet, sieht danach die festgeschriebene Rechnung und lehnt ab; ein
Festschreiben, das auf die Änderung wartet, schreibt deren Stand fest. Der Abgleich mit dem Angebot hat eigene Gründe
(app/orders.py::sync_block_reasons(), dort auch Schlussrechnung und Steuersatz).

Rollenlos wie jede Geschäftslogik; die Auftragsseite zeigt die Gründe (order_to_dict(): order_lock, tax_lock, je Position
price_lock) statt der Eingabe."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .invoices import VALID_STATUSES, closing_invoices
from .models import Invoice, InvoiceItem, OrderItem

# Was eine abgerechnete Position nicht mehr ändern darf -- die Menge bleibt bis zur Schlussrechnung offen.
PRICE_FIELDS = ("unit_price", "unit", "include_in_total")


class OrderLocked(ValueError):
    """Eine Änderung am Auftrag ist gesperrt (seit 1.8.82) -- der Router antwortet 409 mit dem Text."""


def _numbers(numbers: list[str]) -> str:
    return numbers[0] if len(numbers) == 1 else ", ".join(numbers[:-1]) + " und " + numbers[-1]


def valid_invoices(invoices: list[Invoice]) -> list[Invoice]:
    """Festgeschrieben, nicht storniert, kein Storno -- dieselbe Menge, die compute_order_billing_progress() zählt."""
    return [i for i in invoices if i.status in VALID_STATUSES and i.invoice_type != "storno"]


def final_lock_reason(invoices: list[Invoice]) -> str | None:
    """Nach einer gültigen Schlussrechnung ist alles gesperrt -- seit 1.8.86 auch nach einer abschließenden Rechnung aus Aufwand."""
    final = [i for i in closing_invoices(invoices) if i.invoice_type == "schluss"]
    if final:
        return (f"Nach der Schlussrechnung {_numbers([i.invoice_number for i in final])} ist der Auftrag abgerechnet: Positionen, "
                "LV-Titel und Steuersatz lassen sich nicht mehr ändern. Ausweg: die Schlussrechnung stornieren.")
    closing = closing_invoices(invoices)
    if not closing:
        return None
    return (f"Nach der abschließenden Rechnung aus Aufwand {_numbers([i.invoice_number for i in closing])} ist der Auftrag "
            "abgerechnet: Positionen, LV-Titel und Steuersatz lassen sich nicht mehr ändern. Ausweg: sie stornieren.")


def tax_lock_reason(invoices: list[Invoice]) -> str | None:
    """Ab der ersten gültigen Rechnung ist der Steuersatz gesperrt."""
    final = final_lock_reason(invoices)
    if final:
        return final
    valid = valid_invoices(invoices)
    if not valid:
        return None
    return (f"Der Steuersatz ist gesperrt: am Auftrag besteht eine festgeschriebene Rechnung "
            f"({_numbers([i.invoice_number for i in valid])}). Ein anderer Steuerschlüssel geht erst, wenn sie storniert ist.")


def billed_items(db: Session, order_id: int) -> dict[int, list[str]]:
    """Auftragsposition -> Nummern der gültigen Rechnungen, die sie abrechnen (Verweis und Ist ≠ 0)."""
    rows = db.execute(
        select(InvoiceItem.source_order_item_id, Invoice.invoice_number)
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .where(Invoice.order_id == order_id, Invoice.status.in_(VALID_STATUSES), Invoice.invoice_type != "storno",
               InvoiceItem.source_order_item_id.is_not(None), InvoiceItem.ist_quantity != 0)
        .distinct().order_by(Invoice.invoice_number)
    ).all()
    result: dict[int, list[str]] = {}
    for item_id, number in rows:
        result.setdefault(item_id, []).append(number)
    return result


def price_lock_reason(numbers: list[str]) -> str:
    return (f"Einheitspreis, Einheit und „in Summe“ sind gesperrt: die Position ist in {_numbers(numbers)} abgerechnet. "
            "Die Menge bleibt bis zur Schlussrechnung änderbar; für einen anderen Preis zuerst die Rechnung stornieren.")


def changed_fields(item, values: dict) -> set[str]:
    return {key for key, value in values.items() if getattr(item, key) != value}


def item_change_reason(db: Session, invoices: list[Invoice], item: OrderItem, values: dict) -> str | None:
    """Warum diese Änderung an der Position gesperrt ist, sonst None (keine Änderung: None)."""
    changed = changed_fields(item, values)
    if not changed:
        return None
    final = final_lock_reason(invoices)
    if final:
        return final
    if changed & set(PRICE_FIELDS):
        numbers = billed_items(db, item.order_id).get(item.id)
        if numbers:
            return price_lock_reason(numbers)
    return None


def lock_info(db: Session, order_id: int, invoices: list[Invoice]) -> dict:
    """Für die Auftragsseite (nur gelesen): order_lock, tax_lock und je Position der Grund der Preissperre."""
    final = final_lock_reason(invoices)
    return {
        "order_lock": final,
        "tax_lock": tax_lock_reason(invoices),
        "item_locks": {} if final else {item_id: price_lock_reason(numbers)
                                         for item_id, numbers in billed_items(db, order_id).items()},
    }
