"""Rechnungswesen (seit 1.0.33).

Ein Auftrag kann mehrere Rechnungen haben: Abschlagsrechnungen (pauschal oder
nach Leistungsstand), eine Schlussrechnung, und Stornorechnungen zu bereits
versendeten Rechnungen. Siehe Invoice/InvoiceItem in models.py für die
Feldbeschreibungen und die Begründung der Soll/Ist-Mechanik.

Kernprinzip Soll/Ist: ist_quantity auf einer Rechnungsposition ist immer der
KUMULIERTE Stand zum Zeitpunkt dieser Rechnung (z.B. "80 von 100 m² insgesamt
fertig"), nicht der Anteil dieser einen Rechnung. Was auf einer konkreten
Rechnung abgerechnet wird (billed_quantity/billed_total), ist die Differenz
zum kumulierten Stand der letzten vorherigen, bereits versendeten Rechnung für
dieselbe Auftragsposition -- siehe compute_billed_quantity_and_total().

Nummernvergabe: eine Rechnung bekommt ihre invoice_number erst beim Versenden
(entwurf -> versendet), nicht beim Anlegen -- verworfene Entwürfe hinterlassen
so keine Lücken in der Nummernfolge (GoBD). Ab 'versendet' ist eine Rechnung
unveränderlich; Korrekturen laufen ausschließlich über eine Stornorechnung.

Sperren (seit 1.8.72, Befund 1c-1h, docs/archiv/befund-vor-echtbetrieb.md): je Auftrag höchstens eine nicht
stornierte Schlussrechnung (auch als Entwurf), nach der festgeschriebenen keine Abschläge mehr und kein Storno eines
Abschlags; je Rechnung höchstens ein Storno, keins eines Stornos; bis zur Umstellung der Schlussrechnung (R4) keine
Schlussrechnung neben einem nicht stornierten pauschalen Abschlag. Geprüft beim Anlegen und noch einmal beim
Festschreiben, unter der Sperre der Auftragszeile (lock_order_invoices()) -- die Gründe kommen aus
create_block_reason()/finalize_block_reason()/storno_block_reason(), dieselben Texte zeigen Auftrags- und Rechnungsseite.
Seit 1.8.75 läuft jeder schreibende Weg an einer Rechnung unter dieser Sperre, auch "Rechnung aus Aufwand" anlegen und
Positionen, Kopf, Zahlungsbedingung und Steuerschlüssel eines Entwurfs bearbeiten (_lock_draft(): geändert wird nur, was nach
der Sperre noch Entwurf ist, sonst InvoiceBlocked = 409) -- tests/test_v378_rechnung_sperre_und_datum.py prüft das.

Rechnungsdatum (seit 1.8.75, Befund 4a-4c): der Tag des Festschreibens in Berliner Zeit (Tag der Ausgabe), nicht der Tag des
Entwurfs. Beim Festschreiben rücken Rechnungsdatum und Fälligkeit auf diesen Tag (finalize_dates(): das Zahlungsziel des
Entwurfs bleibt); das Skontodatum rechnet ohnehin ab dem Rechnungsdatum. Bis dahin trägt der Entwurf das Datum seines Anlegens.

Zahlungen (seit 1.8.78, Zahlungsstufe Z1, app/payments.py): "bezahlt" ist kein Status mehr -- der Status kennt nur Entwurf,
festgeschrieben ("versendet") und storniert; offen, teilweise bezahlt, Einbehalt offen und bezahlt leiten sich aus den
gebuchten Zahlungen ab. Eine Rechnung mit zugeordneten Zahlungen lässt sich erst stornieren, wenn die Zuordnungen gelöst sind
(storno_block_reason()); eine Stornorechnung ist nie offen.

Kunde der Rechnung (seit 1.8.79, Vorgabe Z2a "Vorweg"): beim Festschreiben hält die Rechnung ihren Kunden fest
(Invoice.customer_id: der Kunde des Projekts, beim Storno der der stornierten Rechnung) -- danach gehört sie zu ihm, auch für
Zahlungen und den Versand an seine Adresse (invoice_customer()). Den Kunden eines Projekts mit festgeschriebener Rechnung kann
niemand mehr wechseln (app/project_participants.py::check_client_change(), dieselbe Sperre der Auftragszeilen).

Feste Fassung (seit 1.8.82, R4a Punkt 1, docs/archiv/befund-vor-echtbetrieb.md "Umsetzung 1.8.82"): das PDF jeder Rechnung (jede
Art, auch Storno) entsteht beim Festschreiben im selben Commit und liegt ab dann mit SHA-256 in der Ablage (_store_fixed_pdf(),
Invoice.pdf_document_id) -- Download, Versand und nachgetragene Zustellung nehmen nur diese Bytes, nie ein neu erzeugtes PDF.

Schlussrechnung als Endrechnung (seit 1.8.85, R4b Punkte 2, 3 und 5, docs/archiv/befund-vor-echtbetrieb.md "Umsetzung R4b"): alle
Auftragspositionen samt Nachträgen mit ihrer Ist-Menge (Vorschlag: die Menge des Auftrags) -- die Gesamtleistung --, darunter der Abzug jeder
festgeschriebenen, nicht stornierten Abschlagsrechnung und Rechnung aus Aufwand mit Netto, USt und Brutto (Rechnungen aus Aufwand
zählen zugleich zur Gesamtleistung). Rechnungsbetrag = Gesamtleistung − Abzüge (final_breakdown()); er ist der Betrag der Rechnung
für Zahlungen, offene Posten und "abgerechnet" (compute_invoice_totals()). Im Entwurf zieht sie die gerade gültigen Rechnungen ab,
beim Festschreiben unter der Sperre frieren die Abzüge ein (InvoiceDeduction). Beim Festschreiben jeder Art wird unter der Sperre
neu gerechnet (_recompute_draft(), Befund 1b), ein Entwurf, dessen Preise, Einheiten, Positionen oder Steuerschlüssel vom Auftrag
abweichen, nicht festgeschrieben (order_deviation_reason(), 409, Ausweg refresh_draft_from_order()). Ein Abschlag muss über 0 €
liegen, eine Schlussrechnung darf bis R4c nicht unter 0 € lauten (amount_block_reason()).

Zahlungshinweis und abschließende Rechnung aus Aufwand (seit 1.8.86, R4b Punkte 4 und 6): die Endrechnung nennt "Stand <Tag des
Festschreibens>" je abgezogener Rechnung, was dort noch offen ist (einschließlich Einbehalt), und den Zahlbetrag (payment_note(),
beim Festschreiben an den Abzügen eingefroren). Seit 1.8.90 (R4c Punkte 6 und 7): eine Schlussrechnung darf unter 0 € lauten
(Überzahlung); ist der Zahlbetrag negativ, nennen PDF, Rechnungsseite und E-Mail einen Erstattungsbetrag, ohne Skonto und ohne
"zahlbar" (format_payment_terms_sentence()); Skonto gibt es nur bei positivem Rechnungsbetrag (skonto_offer()). Die Erstattung
bucht app/payments.py::book_refund() als Zahlungsausgang, das Guthaben steht am Kunden. Ein Auftrag nach Aufwand (Auftragssumme 0 €, z. B. Schnellauftrag) schließt mit
einer als abschließend gekennzeichneten Rechnung aus Aufwand ab (Invoice.closes_order) -- statt einer Schlussrechnung über 0 €, die
es dort nicht gibt. Danach gilt er als vollständig abgerechnet wie nach einer Schlussrechnung (closing_invoices()).
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session

from .acceptances import lock_order
from .berlin_time import berlin_today
from .calculation import effective_material_sale_price, load_calculation_settings
from .models import (
    Customer, Invoice, InvoiceDeduction, InvoiceItem, Material, Order, OrderItem, PaymentTerm, Project, ServiceReportMaterial,
    TaxKey, TimeEntry,
)
from .option_settings import default_option_value
from .payment_terms import get_default_payment_term
from .placeholders import apply_placeholders
from .rounding import CENT, INVOICE_ROUNDING_HALF_UP, round_money
from .service_period import check_order, missing_reason, period_text, proposal as service_period_proposal
from .settings import issue_number

logger = logging.getLogger(__name__)

INVOICE_TYPES ={"abschlag_pauschal", "abschlag_leistungsstand", "schluss", "aufwand", "storno"}
EDITABLE_STATUS = "entwurf"
PROGRESS_INVOICE_TYPES = ("abschlag_pauschal", "abschlag_leistungsstand")
# Seit 1.8.85 (R4b): was die Schlussrechnung abzieht -- Abschläge und Rechnungen aus Aufwand ("Entscheidungen Rechnungen" 12.10.).
DEDUCTED_INVOICE_TYPES = (*PROGRESS_INVOICE_TYPES, "aufwand")
# Festgeschrieben und nicht storniert -- "gültig". Bis 1.8.77 auch "bezahlt"; seit 1.8.78 ist der Zahlstand abgeleitet
# (app/payments.py), die Migration c7d41e9a2b63 setzte bezahlte Rechnungen auf "versendet".
VALID_STATUSES = ("versendet",)


class InvoiceBlocked(ValueError):
    """Eine Aktion ist am Stand des Auftrags gesperrt (seit 1.8.72, siehe Moduldocstring "Sperren"; auch die Mahnung zu
    einer stornierten oder bezahlten Rechnung, app/reminders.py, und seit 1.8.78 das Storno einer Rechnung mit zugeordneten
    Zahlungen). Die Router antworten 409 mit dem Text."""


def is_invoice_editable(invoice: Invoice) -> bool:
    return invoice.status == EDITABLE_STATUS


def lock_order_invoices(db: Session, order_id: int) -> list[Invoice]:
    """Sperrt die Zeile des Auftrags bis zum Commit und liefert seine Rechnungen frisch aus der Datenbank (seit 1.8.72).
    Dieselbe Sperre wie Abnahme und Abgleich mit dem Angebot (app/acceptances.py::lock_order()): Anlegen, Festschreiben,
    Storno und "bezahlt" der Rechnungen eines Auftrags und Anlegen und Versenden ihrer Mahnungen laufen so nacheinander,
    jede Prüfung sieht den Stand, den die vorige hinterlassen hat. populate_existing: der Router hat Auftrag und Rechnung
    vorher ungesperrt geladen -- ohne das blieben deren Werte von vor dem Warten stehen. Wirkt unter PostgreSQL; SQLite
    (nur Entwicklung) ignoriert FOR UPDATE. Seit 1.8.78 buchen auch Zahlungen und ihre Gegenbuchungen unter dieser Sperre
    (app/payments.py::lock_for_booking(), mehrere Aufträge aufsteigend nach ID)."""
    lock_order(db, order_id)
    db.scalar(select(Order).where(Order.id == order_id).execution_options(populate_existing=True))
    return list(db.scalars(
        select(Invoice).where(Invoice.order_id == order_id).order_by(Invoice.id).execution_options(populate_existing=True)
    ))


def _still_there(invoices: list[Invoice], invoice: Invoice) -> bool:
    """Gibt es die Rechnung nach der Sperre noch? (Ein gleichzeitig gelöschter Entwurf fehlt in der frisch geladenen Liste,
    sein Objekt trüge sonst weiter den alten Stand.)"""
    return any(i.id == invoice.id for i in invoices)


def _labels(invoices: list[Invoice]) -> str:
    """"R-2026-0003, R-2026-0005 und ein Entwurf" -- Nummern, Entwürfe als Anzahl."""
    parts = [i.invoice_number for i in invoices if i.invoice_number]
    drafts = sum(1 for i in invoices if not i.invoice_number)
    if drafts:
        parts.append("ein Entwurf" if drafts == 1 else f"{drafts} Entwürfe")
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " und " + parts[-1]


def _final_invoices(invoices: list[Invoice], *, with_drafts: bool, exclude_id: int | None = None) -> list[Invoice]:
    statuses = (EDITABLE_STATUS, *VALID_STATUSES) if with_drafts else VALID_STATUSES
    return [i for i in invoices if i.invoice_type == "schluss" and i.status in statuses and i.id != exclude_id]


def _closing_effort(invoices: list[Invoice], *, exclude_id: int | None = None) -> list[Invoice]:
    """Gültige, als abschließend gekennzeichnete Rechnungen aus Aufwand (seit 1.8.86, R4b Punkt 6)."""
    return [i for i in invoices if i.invoice_type == "aufwand" and i.closes_order and i.status in VALID_STATUSES
            and i.id != exclude_id]


def closing_invoices(invoices: list[Invoice]) -> list[Invoice]:
    """Was einen Auftrag abschließt -- danach gilt er als vollständig abgerechnet: die gültige Schlussrechnung und seit 1.8.86
    eine gültige abschließende Rechnung aus Aufwand (R4b Punkt 6)."""
    return _final_invoices(invoices, with_drafts=False) + _closing_effort(invoices)


def order_sum(order: Order) -> Decimal:
    """Auftragssumme netto (Positionen in der Summe, kaufmännisch je Position gerundet)."""
    return sum((round_money(item.quantity * item.unit_price) for item in order.items if item.include_in_total), Decimal("0"))


def effort_only(order: Order) -> bool:
    """Auftrag nach Aufwand (seit 1.8.86): Auftragssumme 0 € -- Schnellauftrag, Wartung aus dem Vertrag, Auftrag aus einem Befund
    ("… nach Aufwand", 1 × 0 €). Abgerechnet wird er über Rechnungen aus Aufwand, abgeschlossen mit einer abschließenden."""
    return order_sum(order) == 0


ZERO_FINAL_TEXT = ("Ein Auftrag nach Aufwand (Auftragssumme 0 €) wird nicht mit einer Schlussrechnung über 0 € abgeschlossen – die "
                   "Rechnung aus Aufwand als „abschließend“ kennzeichnen.")


def _closing_effort_reason(invoices: list[Invoice], *, exclude_id: int | None = None) -> str | None:
    closing = _closing_effort(invoices, exclude_id=exclude_id)
    if not closing:
        return None
    return (f"Der Auftrag ist mit der abschließenden Rechnung aus Aufwand {_labels(closing)} vollständig abgerechnet – keine "
            "weitere Rechnung. Ausweg: sie stornieren.")


def _progress_after_final_reason(invoices: list[Invoice], invoice_type: str = "abschlag_leistungsstand") -> str | None:
    """Nach einer gültigen Schlussrechnung keine Abschläge mehr (seit 1.8.72) und seit 1.8.85 (R4b Punkt 5) keine Rechnung aus
    Aufwand -- die Schlussrechnung hätte sie weder in der Gesamtleistung noch abgezogen. Seit 1.8.86 ebenso nach einer
    abschließenden Rechnung aus Aufwand."""
    final = _final_invoices(invoices, with_drafts=False)
    if not final:
        return _closing_effort_reason(invoices)
    if invoice_type == "aufwand":
        return (f"Nach der Schlussrechnung {_labels(final)} ist keine Rechnung aus Aufwand mehr möglich -- die Schlussrechnung "
                "hat sie weder in der Gesamtleistung noch abgezogen. Ausweg: die Schlussrechnung stornieren.")
    return f"Nach der Schlussrechnung {_labels(final)} sind keine weiteren Abschlagsrechnungen möglich."


def create_block_reason(invoices: list[Invoice], invoice_type: str, order: Order | None = None) -> str | None:
    """Warum eine neue Rechnung dieser Art am Auftrag gesperrt ist (invoices = alle Rechnungen des Auftrags), sonst None.
    Bis 1.8.84 sperrte zusätzlich ein pauschaler Abschlag die Schlussrechnung (sie zog ihn nicht ab, Befund 1a) -- seit 1.8.85
    zieht die Endrechnung jeden Abschlag ab (R4b Punkt 5). Seit 1.8.86 (Punkt 6) keine Schlussrechnung an einem Auftrag nach
    Aufwand (sie lautete über 0 €) und keine Rechnung nach einer abschließenden Rechnung aus Aufwand."""
    if invoice_type == "schluss":
        existing = _final_invoices(invoices, with_drafts=True)
        if existing:
            return (f"Am Auftrag besteht schon eine Schlussrechnung ({_labels(existing)}). Eine weitere ist erst möglich, "
                    "wenn sie storniert bzw. der Entwurf gelöscht ist.")
        if order is not None and effort_only(order):
            return ZERO_FINAL_TEXT
        return _closing_effort_reason(invoices)
    if invoice_type in DEDUCTED_INVOICE_TYPES:
        return _progress_after_final_reason(invoices, invoice_type)
    return None


def storno_block_reason(invoices: list[Invoice], original: Invoice, *, storno_draft_id: int | None = None) -> str | None:
    """Warum diese Rechnung nicht (mehr) storniert werden kann, sonst None. storno_draft_id: beim Festschreiben dieser
    Storno-Entwurf selbst -- dort zählt nur ein schon festgeschriebenes Storno (Altbestand: zwei Entwürfe nebeneinander);
    beim Anlegen zählt auch ein Entwurf."""
    if original.invoice_type == "storno":
        return "Eine Stornorechnung lässt sich nicht stornieren."
    others = [i for i in invoices if i.invoice_type == "storno" and i.storno_of_invoice_id == original.id
              and i.id != storno_draft_id and (storno_draft_id is None or i.status != EDITABLE_STATUS)]
    if others:
        return f"Zu dieser Rechnung besteht schon eine Stornorechnung ({_labels(others)})."
    if original.status == "storniert":
        return "Diese Rechnung ist schon storniert."
    if original.invoice_type in DEDUCTED_INVOICE_TYPES:
        final = _final_invoices(invoices, with_drafts=False)
        if final:
            what = "Die Rechnung aus Aufwand" if original.invoice_type == "aufwand" else "Der Abschlag"
            return (f"{what} ist in der Schlussrechnung {_labels(final)} verrechnet und lässt sich nicht stornieren, "
                    "solange sie gilt -- zuerst die Schlussrechnung stornieren.")
        # Seit 1.8.86: neben einer abschließenden Rechnung aus Aufwand gilt der Auftrag als vollständig abgerechnet.
        closing = _closing_effort(invoices, exclude_id=original.id)
        if closing:
            return (f"Der Auftrag ist mit der abschließenden Rechnung aus Aufwand {_labels(closing)} vollständig abgerechnet -- "
                    "zuerst sie stornieren.")
    # Seit 1.8.78 (Vorgabe Z1 Nr. 5): erst die Zuordnungen lösen, dann stornieren -- die Zahlung bleibt nicht zugeordnet am
    # Kunden. Beim Anlegen und beim Festschreiben des Stornos unter der Sperre geprüft (Zuordnungen buchen unter derselben).
    # Seit 1.8.81 (Z2b "Vorweg" 2): ebenso erst ohne offene Nebenforderungen (gegenbuchen mit Begründung) -- Nebenforderungen
    # entstehen und werden gegengebucht unter derselben Sperre.
    db = object_session(original)
    if db is not None and original.status in VALID_STATUSES:
        from .dunning_charges import charges_storno_block_reason  # lokal: app/dunning_charges.py importiert dieses Modul
        from .payments import allocation_block_reason  # lokal: app/payments.py importiert dieses Modul
        return allocation_block_reason(db, original) or charges_storno_block_reason(db, original)
    return None


def finalize_block_reason(invoices: list[Invoice], invoice: Invoice) -> str | None:
    """Warum dieser Entwurf nicht festgeschrieben werden kann -- dieselben Regeln wie beim Anlegen, für Entwürfe, die vor
    einer anderen Festschreibung entstanden sind (oder als Altbestand vor 1.8.72). Seit 1.8.74 der Leistungszeitraum (Pflicht,
    app/service_period.py::missing_reason()), zuletzt. Seit 1.8.85 (R4b Punkt 3) davor die Abweichung vom Auftrag (Preise,
    Einheiten, Positionen, Steuerschlüssel) und der Betrag (amount_block_reason(), wie bis 1.8.84 der negative Abschlag vor dem
    Zeitraum) -- beim Festschreiben nach der Neuberechnung unter der Sperre (_recompute_draft())."""
    return (_finalize_rule_reason(invoices, invoice) or order_deviation_reason(invoice) or amount_block_reason(invoice)
            or missing_reason(invoice))


def _finalize_rule_reason(invoices: list[Invoice], invoice: Invoice) -> str | None:
    if invoice.invoice_type == "schluss":
        other = _final_invoices(invoices, with_drafts=False, exclude_id=invoice.id)
        if other:
            return f"Am Auftrag besteht schon eine festgeschriebene Schlussrechnung ({_labels(other)})."
        if invoice.order is not None and effort_only(invoice.order):  # seit 1.8.86 (R4b Punkt 6)
            return ZERO_FINAL_TEXT
        return _closing_effort_reason(invoices) or free_items_reason(invoice)  # freie Positionen seit 1.8.83
    if invoice.invoice_type in DEDUCTED_INVOICE_TYPES:
        # Seit 1.8.83 (R4a Punkt 3): keine freie Position; seit 1.8.85 kein Aufwand nach der Schlussrechnung (R4b Punkt 5); seit
        # 1.8.86 die Regeln einer abschließenden Rechnung aus Aufwand (Punkt 6).
        return (_progress_after_final_reason(invoices, invoice.invoice_type) or free_items_reason(invoice)
                or (closing_block_reason(invoices, invoice) if invoice.closes_order else None))
    if invoice.invoice_type == "storno" and invoice.storno_of_invoice_id is not None:
        original = next((i for i in invoices if i.id == invoice.storno_of_invoice_id), None)
        if original is not None:
            return storno_block_reason(invoices, original, storno_draft_id=invoice.id)
    return None


def _eur(amount: Decimal) -> str:
    return f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def amount_block_reason(invoice: Invoice) -> str | None:
    """Der Betrag, mit dem ein Entwurf nicht festgeschrieben wird.

    - Abschlag (pauschal und nach Leistungsstand): nur über 0 €. Seit 1.8.83 (R4a Punkt 4) kein negativer Abschlag nach
      Leistungsstand -- ein Ist unter dem zuletzt abgerechneten Stand; zu viel Abgerechnetes korrigieren Storno oder
      Schlussrechnung. Seit 1.8.85 (Festlegung 1.8.83 Nr. 6 geändert, Vorgabe R4b) auch 0 € nicht -- vorher ging ein Abschlag
      über 0,00 € mit Nummer durch.
    - Schlussrechnung (seit 1.8.85, R4b): bis 1.8.89 nicht unter 0 €; seit 1.8.90 (R4c Punkt 6) darf sie unter 0 € lauten -- die
      Abschläge übersteigen die Gesamtleistung (Überzahlung), der Kunde bekommt den Erstattungsbetrag."""
    gross = compute_invoice_totals(invoice)["gross_total"]
    if invoice.invoice_type == "abschlag_leistungsstand" and gross < 0:
        return (f"Der Abschlag lautet über {_eur(gross)}: das Ist liegt unter dem zuletzt abgerechneten Stand. Ein Abschlag nach "
                "Leistungsstand nimmt nichts zurück – zu viel Abgerechnetes korrigiert das Storno des Abschlags, der zu viel "
                "abgerechnet hat, oder die Schlussrechnung.")
    if invoice.invoice_type == "abschlag_leistungsstand" and gross == 0:
        return ("Der Abschlag lautet über 0,00 €: seit dem zuletzt abgerechneten Stand ist nichts dazugekommen. Ein Abschlag muss "
                "über 0 € liegen – das Ist der Positionen eintragen oder den Entwurf löschen.")
    if invoice.invoice_type == "abschlag_pauschal" and gross <= 0:
        return f"Der Abschlag lautet über {_eur(gross)}. Ein Abschlag muss über 0 € liegen – den Betrag eintragen."
    return None


def closing_block_reason(invoices: list[Invoice], invoice: Invoice) -> str | None:
    """Warum diese Rechnung nicht als abschließend gekennzeichnet bzw. als abschließende festgeschrieben werden kann (seit 1.8.86,
    R4b Punkt 6): nur eine Rechnung aus Aufwand an einem Auftrag nach Aufwand (Auftragssumme 0 €), nicht neben einer gültigen
    Schlussrechnung oder einer anderen abschließenden Rechnung."""
    if invoice.invoice_type != "aufwand":
        return "Als abschließend kennzeichnen lässt sich nur eine Rechnung aus Aufwand."
    order = invoice.order
    if order is not None and not effort_only(order):
        return (f"„Abschließend“ gibt es nur bei einem Auftrag nach Aufwand (Auftragssumme 0 €) – dieser Auftrag hat Positionen mit "
                f"Preis ({_eur(order_sum(order))} netto); ihn schließt die Schlussrechnung ab.")
    final = _final_invoices(invoices, with_drafts=False)
    if final:
        return f"Am Auftrag besteht schon eine Schlussrechnung ({_labels(final)})."
    other = _closing_effort(invoices, exclude_id=invoice.id)
    if other:
        return f"Am Auftrag besteht schon eine abschließende Rechnung aus Aufwand ({_labels(other)})."
    return None


def _rate_text(rate) -> str:
    return f"{Decimal(rate or 0).normalize():f}".replace(".", ",") + " %"


def order_deviations(db: Session, invoice: Invoice) -> list[str]:
    """Wo ein Entwurf vom Auftrag abweicht (seit 1.8.85, R4b Punkt 3, Befund R4 Nebenbefunde 1 und 2 aus 1.8.82): Steuerschlüssel
    bzw. Steuersatz (jede Art außer Storno), Einheitspreis und Einheit einer Position mit Auftragsbezug, eine Position, die nicht
    mehr in der Summe des Auftrags steht, und bei der Schlussrechnung fehlende Positionen des Auftrags. Leer: keine Abweichung.
    Ein Storno spiegelt seine Rechnung und weicht nie ab."""
    if invoice.invoice_type == "storno" or invoice.status != EDITABLE_STATUS:
        return []
    order = db.get(Order, invoice.order_id)
    if order is None:
        return []
    parts = []
    if invoice.tax_key_id != order.tax_key_id or Decimal(invoice.vat_rate or 0) != Decimal(order.vat_rate or 0):
        parts.append(f"Steuerschlüssel (Entwurf {_rate_text(invoice.vat_rate)}, Auftrag {_rate_text(order.vat_rate)})")
    order_items = {item.id: item for item in order.items}
    present = set()
    for item in sorted(invoice.items, key=lambda x: (x.sort_order, x.id)):
        if item.source_order_item_id is None:
            continue
        present.add(item.source_order_item_id)
        label = item.gaeb_oz or item.position_number or item.short_text
        source = order_items.get(item.source_order_item_id)
        if source is None or not source.include_in_total:
            parts.append(f"Pos. {label} steht nicht mehr in der Summe des Auftrags")
            continue
        if Decimal(item.unit_price or 0) != Decimal(source.unit_price or 0):
            parts.append(f"Einheitspreis Pos. {label} (Entwurf {_eur(Decimal(item.unit_price))}, "
                         f"Auftrag {_eur(Decimal(source.unit_price))})")
        if (item.unit or "") != (source.unit or ""):
            parts.append(f"Einheit Pos. {label} (Entwurf {item.unit or '–'}, Auftrag {source.unit or '–'})")
    if invoice.invoice_type == "schluss":
        missing = [item.gaeb_oz or item.position_number or item.short_text
                   for item in sorted(order.items, key=lambda x: (x.sort_order, x.id))
                   if item.include_in_total and item.id not in present]
        if missing:
            parts.append(f"es fehlen Positionen des Auftrags ({', '.join(missing)})")
    return parts


def order_deviation_reason(invoice: Invoice) -> str | None:
    """Der Grund für die Rechnungsseite und das Festschreiben (409) -- None: der Entwurf passt zum Auftrag."""
    db = object_session(invoice)
    parts = order_deviations(db, invoice) if db is not None else []
    if not parts:
        return None
    return ("Der Entwurf weicht vom Auftrag ab: " + "; ".join(parts) + ". „Aus dem Auftrag aktualisieren“ übernimmt Preise, "
            "Einheiten, Positionen und Steuerschlüssel des Auftrags.")


def free_items_reason(invoice: Invoice) -> str | None:
    """Seit 1.8.83 (R4a Punkt 3): freie Positionen ohne Auftragsbezug gibt es nur in Rechnungen aus Aufwand -- ein Nachtrag
    kommt als gekennzeichnete Position an den Auftrag (app/orders.py::add_order_addendum()) und steht so in jeder folgenden
    Rechnung und in der Schlussrechnung. Beim Festschreiben eines Abschlags nach Leistungsstand oder einer Schlussrechnung
    geprüft, die vor 1.8.83 eine freie Position bekam (Anlegen lehnt add_invoice_item() seither ab). Die Projektionsposition
    des pauschalen Abschlags hat bewusst keinen Bezug (_sync_lump_sum_pauschal_item())."""
    if invoice.invoice_type not in ("abschlag_leistungsstand", "schluss"):
        return None
    free = [i.short_text for i in sorted(invoice.items, key=lambda x: (x.sort_order, x.id)) if i.source_order_item_id is None]
    if not free:
        return None
    return (f"Die Rechnung enthält {'eine freie Position' if len(free) == 1 else f'{len(free)} freie Positionen'} ohne "
            f"Auftragsbezug („{'“, „'.join(free)}“). Freie Positionen gibt es nur in Rechnungen aus Aufwand; einen Nachtrag am "
            "Auftrag anlegen („+ Nachtrag“), dann die Position hier entfernen bzw. die Rechnung neu anlegen.")


def _check_create(db: Session, order: Order, invoice_type: str) -> None:
    invoices = lock_order_invoices(db, order.id)
    db.expire(order, ["items"])  # seit 1.8.86: Auftrag nach Aufwand? -- Positionen nach der Sperre
    reason = create_block_reason(invoices, invoice_type, order)
    if reason:
        db.rollback()  # gibt die Sperre frei
        raise InvoiceBlocked(reason)


def _lock_draft(db: Session, invoice: Invoice) -> None:
    """Dieselbe Sperre wie beim Festschreiben (seit 1.8.75), vor jeder Änderung an einem Entwurf: danach ist die Rechnung
    samt Positionen frisch geladen, geändert wird nur, was noch Entwurf ist -- sonst InvoiceBlocked (409, vorher 400 ohne
    Nummer). Ohne die Sperre wartete eine Änderung auf ein gleichzeitiges Festschreiben und schrieb danach in die
    festgeschriebene Rechnung (Positionen, Betrag, Zeitraum). Wer nach der Sperre ablehnt, rollt zurück (gibt sie frei)."""
    invoices = lock_order_invoices(db, invoice.order_id)
    if not _still_there(invoices, invoice):
        db.rollback()
        raise InvoiceBlocked("Der Entwurf wurde inzwischen gelöscht.")
    if invoice.status != EDITABLE_STATUS:
        number = f" Die Rechnung ist inzwischen festgeschrieben ({invoice.invoice_number})." if invoice.invoice_number else ""
        db.rollback()
        raise InvoiceBlocked(f"Nur Rechnungen im Entwurf können bearbeitet werden.{number}")
    # Positionen frisch: populate_existing oben lädt nur die Rechnungen, nicht ihre Positionen.
    db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id).execution_options(populate_existing=True)).all()
    db.expire(invoice, ["items"])


def _reject(db: Session, error: Exception) -> Exception:
    """Ablehnen nach der Sperre: zurückrollen (gibt sie frei), dann den Fehler werfen -- raise _reject(db, ValueError(...))."""
    db.rollback()
    return error


def _snapshot_order_fields(db: Session, order: Order) -> dict:
    tax_notice_text = None
    if order.tax_key_id is not None:
        key = db.get(TaxKey, order.tax_key_id)
        tax_notice_text = key.notice_text if key else None
    return {
        "customer_name": order.customer_name,
        "customer_number": order.customer_number,
        "customer_address": order.customer_address,
        "property_name": order.property_name,
        "property_address": order.property_address,
        "vat_rate": order.vat_rate,
        "tax_key_id": order.tax_key_id,
        "tax_notice_text": tax_notice_text,
    }


def _count_progress_invoices(db: Session, order_id: int) -> int:
    """Anzahl bereits vorhandener Abschlagsrechnungen (pauschal + nach
    Leistungsstand, nicht storniert) für diesen Auftrag -- Grundlage für die
    automatische Durchnummerierung ('1. Abschlagsrechnung', '2. ...').
    Entwürfe zählen bewusst mit: die Nummerierung ist rein beschreibend
    (progress_description), nicht die rechtlich bedeutsame invoice_number,
    daher darf sie auch verworfene Entwürfe grob mitzählen -- die Bezeichnung
    bleibt ohnehin frei änderbar."""
    return db.scalar(
        select(func.count()).select_from(Invoice).where(
            Invoice.order_id == order_id,
            Invoice.invoice_type.in_(PROGRESS_INVOICE_TYPES),
            Invoice.status != "storniert",
        )
    ) or 0


def _find_matching_payment_term(db: Session, label: str) -> PaymentTerm | None:
    """Robusterer Abgleich als eine reine Gleichheitsprüfung -- Leerzeichen
    am Rand und Groß-/Kleinschreibung werden ignoriert, damit z.B. ein Auftrag
    mit '14 Tage Netto ' (Leerzeichen/Großschreibung) trotzdem die passende
    Zahlungsbedingung '14 Tage netto' findet."""
    normalized = label.strip().lower()
    for term in db.scalars(select(PaymentTerm)).all():
        if term.label.strip().lower() == normalized:
            return term
    return None


def _default_payment_terms_for_order(db: Session, order: Order) -> tuple[str | None, int, object, int | None, str | None]:
    """(Bezeichnung, Tage, Skonto-Prozent, Skonto-Tage, Text-Vorlage) für
    eine neue Rechnung. Die im Auftrag hinterlegte Zahlungsbedingung hat
    Vorrang -- sie wird unverändert als Bezeichnung übernommen; Tage/Skonto/
    Textvorlage werden über eine gleichnamige PaymentTerm ermittelt, falls
    vorhanden (Neuanlagen ab 1.0.39 verwenden dieselben kurzen Bezeichnungen
    wie hier, ältere Aufträge mit dem früheren langen Fließtext-Wert finden
    ggf. keine exakte Übereinstimmung -- dann werden Tage/Skonto/Textvorlage
    über den Kunden-/Systemstandard geschätzt, die Bezeichnung des Auftrags
    bleibt trotzdem erhalten). Nur wenn der Auftrag gar keine Zahlungsbedingung
    trägt, wird komplett auf Kunden-/Systemstandard zurückgefallen."""
    _, fallback_days, fallback_skonto_pct, fallback_skonto_days, fallback_template = _fallback_payment_terms(db, order)
    if order.payment_terms:
        matching = _find_matching_payment_term(db, order.payment_terms)
        if matching:
            return order.payment_terms, matching.days, matching.skonto_percent, matching.skonto_days, matching.text_template
        return order.payment_terms, fallback_days, fallback_skonto_pct, fallback_skonto_days, fallback_template
    return _fallback_payment_terms(db, order)


def _fallback_payment_terms(db: Session, order: Order) -> tuple[str | None, int, object, int | None, str | None]:
    """Kunden-Standard, sonst Systemstandard, sonst 14 Tage ohne Bezeichnung/Skonto/Textvorlage."""
    customer = order.project.customer if order.project else None
    term = None
    if customer is not None and customer.profile and customer.profile.default_payment_term_id:
        term = db.get(PaymentTerm, customer.profile.default_payment_term_id)
    if term is None:
        term = get_default_payment_term(db)
    if term is None:
        return None, 14, None, None, None
    return term.label, term.days, term.skonto_percent, term.skonto_days, term.text_template


def _default_invoice_header_fields(db: Session, order: Order, *, due_date: date | None) -> dict:
    label, days, skonto_percent, skonto_days, text_template = _default_payment_terms_for_order(db, order)
    today = berlin_today()  # Datum des Entwurfs; das Festschreiben setzt das Rechnungsdatum neu (finalize_dates())
    return {
        **_snapshot_order_fields(db, order),
        "invoice_date": today,
        "payment_terms": label,
        "due_date": due_date or (today + timedelta(days=days)),
        "skonto_percent": skonto_percent,
        "skonto_days": skonto_days,
        "payment_terms_text_template": text_template,
        "intro_text": default_option_value(db, "invoice_intro_texts"),
        "outro_text": default_option_value(db, "invoice_outro_texts"),
    }


def get_previous_cumulative_ist(
    db: Session, order_id: int, source_order_item_id: int, *, exclude_invoice_id: int | None = None,
) -> Decimal:
    """Kumulierter Ist-Stand der zuletzt festgeschriebenen
    (NICHT: Entwurf, NICHT: stornierte) Rechnung für dieselbe
    Auftragsposition. Entwürfe zählen bewusst nicht mit, da sie noch nicht
    endgültig sind -- eine stornierte Rechnung zählt bewusst nicht mit, da ihr
    Stand damit rückgängig gemacht wurde.

    invoice_type wird zusätzlich auf abschlag_leistungsstand/schluss begrenzt:
    eine Storno-Rechnung übernimmt ist_quantity unverändert von der Rechnung,
    die sie storniert (nur billed_quantity/-total werden negiert, siehe
    create_storno_draft) -- sie selbst würde sonst fälschlich als neuer,
    aktueller Stand erkannt, obwohl sie das genaue Gegenteil bedeutet.

    "Zuletzt" seit 1.8.83 (R4a Punkt 5): nach dem Zeitpunkt des Festschreibens (Invoice.finalized_at) -- vorher nach
    Rechnungsdatum und ID, am selben Tag also die zuletzt ANGELEGTE (zwei Entwürfe nebeneinander, der ältere zuletzt
    festgeschrieben: es galt der Stand des jüngeren, Befund R4 b). Rechnungen von vor 1.8.83 (ohne Zeitpunkt) wie bisher, hinter
    jeder späteren."""
    stmt = (
        select(InvoiceItem.ist_quantity)
        .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
        .where(
            Invoice.order_id == order_id,
            Invoice.status.in_(VALID_STATUSES),
            Invoice.invoice_type.in_(["abschlag_leistungsstand", "schluss"]),
            InvoiceItem.source_order_item_id == source_order_item_id,
        )
        .order_by(Invoice.finalized_at.is_(None), Invoice.finalized_at.desc(), Invoice.invoice_date.desc(), Invoice.id.desc())
    )
    if exclude_invoice_id is not None:
        stmt = stmt.where(Invoice.id != exclude_invoice_id)
    result = db.scalar(stmt)
    return result if result is not None else Decimal("0")


def compute_billed_quantity_and_total(
    db: Session, order_id: int, invoice_id: int | None, source_order_item_id: int | None,
    ist_quantity: Decimal, unit_price: Decimal, *, invoice_type: str | None = None,
) -> tuple[Decimal, Decimal]:
    """Berechnet, was auf EINER Rechnung für eine Position tatsächlich
    abgerechnet wird. Ohne Bezug zu einer Auftragsposition (neue Position/
    Nachtrag) wird die komplette ist_quantity abgerechnet, da es keinen
    vorherigen Stand gibt. Seit 1.8.85 (R4b) rechnet die Schlussrechnung als Endrechnung
    ebenso die volle Ist-Menge -- die Abschläge zieht sie als Beträge ab (final_breakdown()),
    nicht mehr über die Menge."""
    if source_order_item_id is None or invoice_type == "schluss":
        billed_quantity = ist_quantity
    else:
        previous = get_previous_cumulative_ist(
            db, order_id, source_order_item_id, exclude_invoice_id=invoice_id,
        )
        billed_quantity = ist_quantity - previous
    return billed_quantity, billed_quantity * unit_price


def invoice_rounding(invoice: Invoice) -> str:
    """Rundungsart dieser Rechnung (seit 1.8.11, Invoice.rounding_rule): ROUND_HALF_UP
    (kaufmännisch) für jede Rechnung ab 1.8.11, ROUND_HALF_EVEN für eine vorher versendete -- so
    hat deren PDF die Beträge beim Formatieren gerundet (f"{x:.2f}" rundet halb-gerade)."""
    return ROUND_HALF_UP if invoice.rounding_rule == INVOICE_ROUNDING_HALF_UP else ROUND_HALF_EVEN


def _billed(invoice: Invoice, item: InvoiceItem) -> tuple[Decimal, Decimal]:
    """(abgerechnete Menge, Betrag) einer Position. Ein Entwurf der Schlussrechnung rechnet seit 1.8.85 die volle Ist-Menge
    (Endrechnung) -- unabhängig davon, was ein Entwurf von vor 1.8.85 als Rest gespeichert hat; das Festschreiben speichert
    die volle Menge (_recompute_draft())."""
    if invoice.invoice_type == "schluss" and invoice.status == EDITABLE_STATUS:
        return item.ist_quantity, item.ist_quantity * item.unit_price
    return item.billed_quantity, item.billed_total


def invoice_line_total(invoice: Invoice, item: InvoiceItem) -> Decimal:
    """Positionsbetrag, wie er auf der Rechnung steht. billed_total ist mit sechs
    Nachkommastellen gespeichert (Menge x Preis) und bleibt so; ab 1.8.11 zählt der
    kaufmännisch auf den Cent gerundete Betrag, vorher der ungerundete."""
    total = _billed(invoice, item)[1]
    if invoice.rounding_rule == INVOICE_ROUNDING_HALF_UP:
        return round_money(total)
    return total


def compute_invoice_totals(invoice: Invoice) -> dict:
    """net/vat/gross wie bei Order nicht gespeichert, sondern immer frisch
    berechnet -- für abschlag_pauschal aus lump_sum_net, sonst aus der Summe
    der Positionsbeträge (unabhängig von der Ist=0-Anzeigeregel, die nur die
    Darstellung betrifft, nicht die Summe).

    Seit 1.8.11 (rounding_rule "half_up") wie bei Angebot und Auftrag kaufmännisch:
    Positionsbeträge und Pauschalbetrag auf den Cent, Netto als deren Summe, USt auf den Cent,
    Brutto = Netto + USt. Eine vorher versendete Rechnung (rounding_rule leer) rechnet
    unverändert ungerundet, gerundet wird dort erst beim Formatieren -- sonst ergäbe ihr
    Nachdruck bei einem halben Cent einen anderen Betrag als das versendete Dokument."""
    if invoice.rounding_rule != INVOICE_ROUNDING_HALF_UP:
        if invoice.invoice_type == "abschlag_pauschal":
            net = invoice.lump_sum_net or Decimal("0")
        else:
            net = sum((_billed(invoice, item)[1] for item in invoice.items), Decimal("0"))
        vat = net * invoice.vat_rate / Decimal("100")
        return {"net_total": net, "vat_total": vat, "gross_total": net + vat}
    # Seit 1.8.85 (R4b): die Schlussrechnung als Endrechnung (und ihr Storno) -- Rechnungsbetrag = Gesamtleistung − Abzüge.
    breakdown = final_breakdown(invoice)
    if breakdown is not None:
        return {"net_total": breakdown.amount_net, "vat_total": breakdown.amount_vat, "gross_total": breakdown.amount_gross}
    if invoice.invoice_type == "abschlag_pauschal":
        net = round_money(invoice.lump_sum_net)
    else:
        net = sum((invoice_line_total(invoice, item) for item in invoice.items), Decimal("0"))
    vat = round_money(net * invoice.vat_rate / Decimal("100"))
    return {"net_total": net, "vat_total": vat, "gross_total": net + vat}


@dataclass(frozen=True)
class DeductionLine:
    """Eine abgezogene Rechnung in der Endrechnung (seit 1.8.85) -- Beträge aus der Rechnung selbst, beim Storno mit umgekehrtem
    Vorzeichen."""
    invoice: Invoice
    net: Decimal
    vat: Decimal
    gross: Decimal

    def as_dict(self) -> dict:
        inv = self.invoice
        return {"invoice_id": inv.id, "invoice_number": inv.invoice_number, "invoice_date": inv.invoice_date,
                "invoice_type": inv.invoice_type, "description": inv.progress_description, "vat_rate": inv.vat_rate,
                "net": self.net, "vat": self.vat, "gross": self.gross}


@dataclass(frozen=True)
class FinalBreakdown:
    """Aufstellung der Endrechnung (seit 1.8.85, R4b Punkt 2): Positionen (volle Ist-Menge) und Rechnungen aus Aufwand ergeben die
    Gesamtleistung (netto, USt auf den Cent, brutto); davon gehen die Abzüge ab (je Netto, USt, Brutto der abgezogenen Rechnung);
    Rechnungsbetrag = Gesamtleistung − Abzüge, netto, USt und brutto je für sich -- so geht die Summe auf den Cent auf."""
    positions_net: Decimal
    effort: list[DeductionLine]
    total_net: Decimal
    total_vat: Decimal
    total_gross: Decimal
    deductions: list[DeductionLine]
    deducted_net: Decimal
    deducted_vat: Decimal
    deducted_gross: Decimal
    amount_net: Decimal
    amount_vat: Decimal
    amount_gross: Decimal
    tax_notes: list[str]

    def as_dict(self) -> dict:
        return {"positions_net": self.positions_net, "effort": [line.as_dict() for line in self.effort],
                "total_net": self.total_net, "total_vat": self.total_vat, "total_gross": self.total_gross,
                "deductions": [line.as_dict() for line in self.deductions], "deducted_net": self.deducted_net,
                "deducted_vat": self.deducted_vat, "deducted_gross": self.deducted_gross, "amount_net": self.amount_net,
                "amount_vat": self.amount_vat, "amount_gross": self.amount_gross, "tax_notes": self.tax_notes}


def _deduction_order(invoice: Invoice):
    """Älteste zuerst: nach dem Zeitpunkt des Festschreibens; Rechnungen von vor 1.8.83 (ohne) davor, nach Datum und ID."""
    return (invoice.finalized_at is not None, invoice.finalized_at or datetime.min, invoice.invoice_date or date.min, invoice.id)


def deductible_invoices(invoices: list[Invoice], final: Invoice) -> list[Invoice]:
    """Was die Schlussrechnung gerade abzöge (seit 1.8.85): jede festgeschriebene, nicht stornierte Abschlagsrechnung und Rechnung
    aus Aufwand desselben Auftrags, älteste zuerst."""
    return sorted((i for i in invoices if i.order_id == final.order_id and i.id != final.id
                   and i.invoice_type in DEDUCTED_INVOICE_TYPES and i.status in VALID_STATUSES), key=_deduction_order)


def _deducted(invoice: Invoice) -> tuple[list[Invoice], int] | None:
    """(abgezogene Rechnungen, Vorzeichen) einer Endrechnung, None für jede andere Rechnung: der Entwurf der Schlussrechnung zieht
    die gerade gültigen ab, die festgeschriebene ihre eingefrorenen (InvoiceDeduction), ihr Storno die des Originals mit
    umgekehrtem Vorzeichen. Eine festgeschriebene Schlussrechnung ohne Abzüge (auch jede von vor 1.8.85, deren Positionen den Rest
    über die Menge tragen) rechnet wie jede Rechnung aus ihren Positionen."""
    if invoice.invoice_type == "schluss":
        if invoice.status == EDITABLE_STATUS:
            db = object_session(invoice)
            if db is None or invoice.order_id is None:
                return None
            others = list(db.scalars(select(Invoice).where(Invoice.order_id == invoice.order_id)))
            found = deductible_invoices(others, invoice)
        else:
            found = [row.deducted_invoice for row in invoice.deductions]
        return (found, 1) if found else None
    if invoice.invoice_type == "storno" and invoice.storno_of_invoice_id is not None:
        db = object_session(invoice)
        original = db.get(Invoice, invoice.storno_of_invoice_id) if db is not None else None
        if original is None or original.invoice_type != "schluss" or not original.deductions:
            return None
        return [row.deducted_invoice for row in original.deductions], -1
    return None


def final_breakdown(invoice: Invoice) -> FinalBreakdown | None:
    """Die Aufstellung der Endrechnung (siehe FinalBreakdown), None für jede Rechnung ohne Abzüge."""
    found = _deducted(invoice)
    if found is None:
        return None
    deducted, sign = found
    positions_net = sum((invoice_line_total(invoice, item) for item in invoice.items), Decimal("0"))
    lines = []
    for other in deducted:
        totals = compute_invoice_totals(other)
        lines.append(DeductionLine(other, sign * totals["net_total"], sign * totals["vat_total"], sign * totals["gross_total"]))
    effort = [line for line in lines if line.invoice.invoice_type == "aufwand"]
    total_net = positions_net + sum((line.net for line in effort), Decimal("0"))
    total_vat = round_money(total_net * invoice.vat_rate / Decimal("100"))
    deducted_net = sum((line.net for line in lines), Decimal("0"))
    deducted_vat = sum((line.vat for line in lines), Decimal("0"))
    amount_net, amount_vat = total_net - deducted_net, total_vat - deducted_vat
    tax_notes = [f"{line.invoice.invoice_number or 'Entwurf'} ist mit {_rate_text(line.invoice.vat_rate)} USt abgerechnet, die "
                 f"Schlussrechnung mit {_rate_text(invoice.vat_rate)} – abgezogen wird die USt, die dort steht."
                 for line in lines if Decimal(line.invoice.vat_rate or 0) != Decimal(invoice.vat_rate or 0)]
    return FinalBreakdown(
        positions_net=positions_net, effort=effort, total_net=total_net, total_vat=total_vat, total_gross=total_net + total_vat,
        deductions=lines, deducted_net=deducted_net, deducted_vat=deducted_vat, deducted_gross=deducted_net + deducted_vat,
        amount_net=amount_net, amount_vat=amount_vat, amount_gross=amount_net + amount_vat, tax_notes=tax_notes,
    )


def payment_note(invoice: Invoice) -> dict | None:
    """Zahlungshinweis der Endrechnung (seit 1.8.86, R4b Punkt 4): "Stand <Tag>" -- je abgezogener Rechnung mit offenem Betrag
    (einschließlich Einbehalt) "zzgl. noch offen aus …", darunter der Zahlbetrag = Rechnungsbetrag + noch Offenes. Im Entwurf der
    Stand von heute (live), festgeschrieben der vom Tag des Festschreibens (an den Abzügen eingefroren, Rechnungsdatum). Der
    Rechnungsbetrag bleibt der Betrag der Rechnung (Zahlungen, Mahnung); die Mahnfähigkeit danach regelt R4c. None für jede
    andere Rechnung, ein Storno und Abzüge von 1.8.85 ohne eingefrorenen Stand."""
    if invoice.invoice_type != "schluss":
        return None
    breakdown = final_breakdown(invoice)
    if breakdown is None:
        return None
    if invoice.status == EDITABLE_STATUS:
        from .payments import payment_states  # lokal: app/payments.py importiert dieses Modul
        db = object_session(invoice)
        states = payment_states(db, [line.invoice for line in breakdown.deductions])  # Altbestand über 0 € oder weniger: None
        rows = [(line.invoice, states[line.invoice.id].open if states.get(line.invoice.id) else Decimal("0.00"),
                 states[line.invoice.id].retained_open if states.get(line.invoice.id) else Decimal("0.00"))
                for line in breakdown.deductions]
        as_of = berlin_today()
    else:
        if any(row.open_amount is None for row in invoice.deductions):
            return None
        rows = [(row.deducted_invoice, row.open_amount, row.retained_open or Decimal("0.00")) for row in invoice.deductions]
        as_of = invoice.invoice_date
    lines = [{"invoice_id": other.id, "invoice_number": other.invoice_number, "invoice_type": other.invoice_type,
              "open": open_, "retained": retained} for other, open_, retained in rows if open_ > 0]
    pay_amount = breakdown.amount_gross + sum((line["open"] for line in lines), Decimal("0"))
    # Seit 1.8.90 (R4c Punkt 6): ein negativer Zahlbetrag ist ein Erstattungsbetrag (Überzahlung).
    return {"as_of": as_of, "invoice_amount": breakdown.amount_gross, "lines": lines, "pay_amount": pay_amount,
            "refund_amount": -pay_amount if pay_amount < 0 else None}


def refund_due(invoice: Invoice) -> Decimal | None:
    """Der Erstattungsbetrag laut Zahlungshinweis (seit 1.8.90), None ohne Überzahlung."""
    note = payment_note(invoice)
    return note["refund_amount"] if note is not None else None


def refund_sentence(amount: Decimal) -> str:
    """Satz statt der Zahlungsbedingungen bei einem Erstattungsbetrag (seit 1.8.90): ohne Skonto und ohne "zahlbar"."""
    return f"Den Erstattungsbetrag von {_eur(amount)} überweisen wir Ihnen."


def _copy_order_items_with_default_ist(db: Session, invoice: Invoice, order: Order) -> None:
    """Kopiert alle Auftragspositionen (in der Summe, samt Nachträgen) als Rechnungspositionen -- Ist vom Nutzer danach
    anpassbar (_proposed_ist())."""
    for order_item in order.items:
        if not order_item.include_in_total:
            continue
        _add_order_item(db, invoice, order, order_item)


def _proposed_ist(db: Session, invoice: Invoice, order: Order, order_item: OrderItem) -> Decimal:
    """Vorgeschlagenes Ist einer Position: beim Abschlag nach Leistungsstand der zuletzt abgerechnete Stand (0, falls noch nie
    abgerechnet), bei der Schlussrechnung die Menge des Auftrags -- der letzte Stand des Auftrags, dessen Mengen bis zur
    Schlussrechnung änderbar bleiben (R4a). Seit 1.8.85 rechnet die Schlussrechnung diese Ist-Mengen voll ab (Endrechnung,
    Festlegung 1.8.85 Nr. 1)."""
    if invoice.invoice_type == "schluss":
        return order_item.quantity
    return get_previous_cumulative_ist(db, order.id, order_item.id, exclude_invoice_id=invoice.id)


def final_quantity_checks(invoice: Invoice) -> dict[int, dict]:
    """Mengenvergleich im Entwurf der Schlussrechnung (seit 1.8.88, Ergänzung zu Festlegung 1.8.85 Nr. 1): je Position mit
    Auftragsbezug die Menge des Auftrags (heute), die zuletzt abgerechnete Menge (Ist der zuletzt festgeschriebenen Rechnung dieser
    Position, get_previous_cumulative_ist(); 0, wenn noch nie abgerechnet) und die Abweichungen des Ist: "auftrag" (Ist ≠ Menge des
    Auftrags) und "abgerechnet" (Ist unter der zuletzt abgerechneten Menge). Leer für jede andere Rechnung und nach dem Festschreiben."""
    if invoice.invoice_type != "schluss" or invoice.status != EDITABLE_STATUS:
        return {}
    db = object_session(invoice)
    if db is None:
        return {}
    order_items = {item.id: item for item in db.scalars(select(OrderItem).where(OrderItem.order_id == invoice.order_id))}
    checks = {}
    for item in invoice.items:
        if item.source_order_item_id is None:
            continue
        source = order_items.get(item.source_order_item_id)
        order_quantity = source.quantity if source is not None else None
        last = get_previous_cumulative_ist(db, invoice.order_id, item.source_order_item_id, exclude_invoice_id=invoice.id)
        ist = Decimal(item.ist_quantity or 0)
        deviations = []
        if order_quantity is not None and ist != Decimal(order_quantity):
            deviations.append("auftrag")
        if ist < Decimal(last):
            deviations.append("abgerechnet")
        checks[item.id] = {"order_quantity": order_quantity, "last_billed_quantity": last, "deviations": deviations}
    return checks


def _add_order_item(db: Session, invoice: Invoice, order: Order, order_item: OrderItem) -> None:
    ist_quantity = _proposed_ist(db, invoice, order, order_item)
    billed_quantity, billed_total = compute_billed_quantity_and_total(
        db, order.id, invoice.id, order_item.id, ist_quantity, order_item.unit_price, invoice_type=invoice.invoice_type,
    )
    db.add(InvoiceItem(
        invoice_id=invoice.id, source_order_item_id=order_item.id,
        sort_order=order_item.sort_order, position_number=order_item.position_number,
        gaeb_oz=order_item.gaeb_oz, short_text=order_item.short_text, long_text=order_item.long_text,
        unit=order_item.unit, unit_price=order_item.unit_price,
        soll_quantity=order_item.quantity, ist_quantity=ist_quantity,
        billed_quantity=billed_quantity, billed_total=billed_total,
    ))


LUMP_SUM_ITEM_UNIT = "pschl."


def _sync_lump_sum_pauschal_item(db: Session, invoice: Invoice) -> None:
    """Haelt die EINZIGE InvoiceItem-Zeile einer abschlag_pauschal-Rechnung synchron zu
    lump_sum_net/progress_description (seit 1.3.24, CLAUDE.md "Pauschale Abschlagsrechnung ohne
    Positionstabelle") -- vorher hatte dieser Rechnungstyp ueberhaupt keine Position, PDF und
    Bildschirm zeigten nur einen Betrag ohne jede Beschreibung dessen, was pauschal abgerechnet
    wird.

    WICHTIG, REINE PROJEKTION: diese Zeile ist niemals unabhaengig editierbar. lump_sum_net
    bleibt die alleinige Quelle der Wahrheit fuer den Rechnungsbetrag (compute_invoice_totals()
    liest bei diesem Typ weiterhin ausschliesslich lump_sum_net, nie eine Positionssumme) --
    add_invoice_item()/update_invoice_item()/remove_invoice_item() lehnen jede Änderung an dieser
    Zeile über den allgemeinen Positionsweg deshalb explizit ab (ValueError). Eine künftige
    Positionsbearbeitung speziell für abschlag_pauschal darf NICHT gebaut werden, ohne dieses
    Prinzip zu überdenken -- zwei unabhängig editierbare Zahlen für denselben Betrag wären genau
    der Fehler, der beim Mahntext (CLAUDE.md "Mahnwesen: Löschen/Versenden/Bearbeiten") bewusst
    vermieden wurde. Menge/Einheit sind fest (1 / "pschl.") und tragen keine eigene Bedeutung --
    einzig Bezeichnung und Betrag stammen aus den beiden editierbaren Feldern des Pauschalbetrag-
    Kärtchens."""
    existing = next(iter(invoice.items), None)
    text = invoice.progress_description or "Abschlagszahlung gemäß Auftrag"
    amount = invoice.lump_sum_net if invoice.lump_sum_net is not None else Decimal("0")
    if existing is None:
        db.add(InvoiceItem(
            invoice_id=invoice.id, sort_order=10, position_number="1",
            short_text=text, long_text=None, unit=LUMP_SUM_ITEM_UNIT, unit_price=amount,
            soll_quantity=Decimal("1"), ist_quantity=Decimal("1"),
            billed_quantity=Decimal("1"), billed_total=amount,
        ))
    else:
        existing.short_text = text
        existing.unit_price = amount
        existing.billed_total = amount


def create_abschlag_pauschal(
    db: Session, order: Order, *, lump_sum_net: Decimal, progress_description: str | None = None,
    due_date: date | None = None,
) -> Invoice:
    _check_create(db, order, "abschlag_pauschal")
    if not progress_description:
        progress_description = f"{_count_progress_invoices(db, order.id) + 1}. Abschlagsrechnung"
    invoice = Invoice(
        order_id=order.id, invoice_type="abschlag_pauschal", status="entwurf",
        lump_sum_net=lump_sum_net, progress_description=progress_description,
        **_default_invoice_header_fields(db, order, due_date=due_date),
    )
    db.add(invoice)
    db.flush()  # invoice.id fuer die Projektions-Position
    _sync_lump_sum_pauschal_item(db, invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def create_abschlag_leistungsstand(db: Session, order: Order, *, due_date: date | None = None) -> Invoice:
    _check_create(db, order, "abschlag_leistungsstand")
    progress_description = f"{_count_progress_invoices(db, order.id) + 1}. Abschlagsrechnung (nach Leistungsstand)"
    invoice = Invoice(
        order_id=order.id, invoice_type="abschlag_leistungsstand", status="entwurf",
        progress_description=progress_description,
        **_default_invoice_header_fields(db, order, due_date=due_date),
    )
    db.add(invoice)
    db.flush()
    _copy_order_items_with_default_ist(db, invoice, order)
    db.commit()
    db.refresh(invoice)
    return invoice


def create_schlussrechnung(db: Session, order: Order, *, due_date: date | None = None) -> Invoice:
    _check_create(db, order, "schluss")
    invoice = Invoice(
        order_id=order.id, invoice_type="schluss", status="entwurf",
        **_default_invoice_header_fields(db, order, due_date=due_date),
    )
    db.add(invoice)
    db.flush()
    _copy_order_items_with_default_ist(db, invoice, order)
    db.commit()
    db.refresh(invoice)
    return invoice


def _time_entry_employee_name(employee) -> str:
    return f"{employee.first_name} {employee.last_name}".strip() if employee else ""


def create_invoice_from_time_entries(
    db: Session, order: Order, time_entries: list[TimeEntry], materials: list[ServiceReportMaterial],
    *, due_date: date | None = None,
) -> Invoice:
    """Erzeugt eine Rechnung aus Ist-Zeitbuchungen UND verbrauchtem Material statt aus
    Auftragspositionen (seit 1.2.2, Material seit 1.2.23) -- Grundlage für zeitbasiert
    abgerechnete Reparaturen/kleine Einsätze (siehe app/service_reports.py, dessen Unterschrift
    die zugehörige "Rechnung erstellen"-Aufgabe für den Sachbearbeiter auslöst). Nur bereits
    gebuchte, nicht mehr laufende Zeiten (status="booked") werden berücksichtigt, gruppiert nach
    Mitarbeiter + Tätigkeit. Ein einheitlicher Stundenpreis für alle Zeitpositionen aus dem
    globalen Stundenverrechnungssatz (CalculationSettings.labor_rate, id ohne Katalogbezug).

    Material (seit 1.2.23, siehe list_materials_for_invoicing() in app/service_reports.py --
    nur unterschriebene Berichte liefern Zeilen): Zeitpositionen zuerst, danach Material.
    Katalogmaterial (material_id gesetzt) wird nach (material_id, unit) gruppiert und mit dem
    AKTUELLEN Katalogpreis MIT dem globalen Materialaufschlag bepreist
    (effective_material_sale_price(), CalculationSettings.material_markup_pct -- derselbe
    Mechanismus, der auch im Leistungskatalog aus Einkaufs- den Verkaufspreis macht, siehe
    app/calculation.py::build_calculation()). Frei eingetipptes Material (material_id leer) wird
    NIE zusammengefasst, auch nicht bei identischem Text, und bekommt unit_price=0 -- das Büro
    trägt den Preis im Rechnungsentwurf nach, die Position soll dabei sichtbar bleiben, nicht
    fehlen.

    Ergebnis ist wie jede andere Rechnung nur ein Entwurf, die Positionen bleiben vor dem
    Versenden vollständig prüf-/änderbar."""
    # Schlechtwetter-Zeitarten (weather_winter/weather_summer, siehe app/time_tracking.py::
    # NON_PRODUCTIVE_ENTRY_TYPES) sind witterungsbedingter Ausfall, nie ausgeführte Leistung --
    # TimeEntry.order_id ist NOT NULL, ein Monteur muss sie also zwangsläufig einem Auftrag
    # zuordnen, obwohl sie fachlich nichts mit dessen Leistungserbringung zu tun haben. Ohne
    # diesen Ausschluss würde "Rechnung aus Zeitbuchungen" sie dem Kunden in Rechnung stellen.
    booked = [
        e for e in time_entries
        if e.status == "booked" and e.hours and e.entry_type not in ("weather_winter", "weather_summer")
    ]
    if not booked and not materials:
        raise ValueError("Weder abrechenbare Zeitbuchungen noch Material für diesen Auftrag vorhanden.")

    # Stundenpreis/Materialaufschlag VOR dem Anlegen der Rechnung abfragen: load_calculation_settings()
    # führt eine eigene Schema-Introspektion (sa_inspect) aus. Käme das NACH einem bereits geflushten,
    # aber noch nicht committeten Invoice, kann das je nach Verbindungs-/Pooling-Verhalten die noch
    # ungesicherte Zeile verwerfen -- also lieber vorher abfragen, wenn die Session noch keinen eigenen
    # ungesicherten Stand trägt. (Bis 1.8.41 kam beim ersten Aufruf noch ein eigener Commit dazu.)
    settings = load_calculation_settings(db)
    hourly_rate = settings.labor_rate
    # Seit 1.8.75 unter derselben Sperre wie das Festschreiben (nach den Einstellungen, siehe oben); seit 1.8.85 (R4b Punkt 5)
    # nach einer gültigen Schlussrechnung gesperrt (bis 1.8.84 möglich, Festlegung 1.8.72 Nr. 3).
    _check_create(db, order, "aufwand")

    # Seit 1.8.74: erster und letzter Arbeitstag der übernommenen Buchungen -- Quelle des Vorschlags für den
    # Leistungszeitraum (app/service_period.py); welche Buchungen abgerechnet wurden, steht sonst nirgends.
    work_dates = [e.work_date for e in booked]
    invoice = Invoice(
        order_id=order.id, invoice_type="aufwand", status="entwurf",
        billed_work_from=min(work_dates, default=None), billed_work_to=max(work_dates, default=None),
        **_default_invoice_header_fields(db, order, due_date=due_date),
    )
    db.add(invoice)
    db.flush()

    grouped: dict[tuple[int, str], dict] = {}
    for entry in booked:
        key = (entry.employee_id, entry.activity or "")
        bucket = grouped.setdefault(key, {"employee": entry.employee, "activity": entry.activity, "hours": Decimal("0")})
        bucket["hours"] += Decimal(entry.hours)

    ordered_buckets = sorted(
        grouped.values(), key=lambda b: (_time_entry_employee_name(b["employee"]), b["activity"] or ""),
    )
    for index, bucket in enumerate(ordered_buckets, start=1):
        employee_name = _time_entry_employee_name(bucket["employee"])
        db.add(InvoiceItem(
            invoice_id=invoice.id, source_order_item_id=None, sort_order=index * 10,
            position_number="", short_text=bucket["activity"] or "Ausgeführte Arbeiten",
            long_text=(f"Ausgeführt von {employee_name}" if employee_name else ""),
            unit="Std.", unit_price=hourly_rate, soll_quantity=None,
            ist_quantity=bucket["hours"], billed_quantity=bucket["hours"], billed_total=bucket["hours"] * hourly_rate,
        ))

    # Materialpositionen -- Katalogzeilen nach (material_id, unit) gruppiert und summiert, freie
    # Zeilen nie zusammengefasst (siehe Docstring).
    catalog_groups: dict[tuple[int, str], Decimal] = {}
    free_rows: list[ServiceReportMaterial] = []
    for m in materials:
        if m.material_id is not None:
            key = (m.material_id, m.unit or "")
            catalog_groups[key] = catalog_groups.get(key, Decimal("0")) + Decimal(m.quantity)
        else:
            free_rows.append(m)

    material_lines: list[tuple[str, str, Decimal, Decimal]] = []  # (short_text, unit, quantity, unit_price)
    materials_by_id = {
        material.id: material
        for material in (db.get(Material, mid) for mid, _unit in catalog_groups) if material is not None
    }
    for (material_id, unit), qty in sorted(
        catalog_groups.items(), key=lambda kv: materials_by_id[kv[0][0]].name if kv[0][0] in materials_by_id else "",
    ):
        material = materials_by_id.get(material_id)
        if material is None:
            continue  # Katalogeintrag inzwischen entfernt -- kann heute über die App nicht passieren, defensiv
        unit_price = effective_material_sale_price(material.purchase_price, material.price_basis, settings.material_markup_pct)
        material_lines.append((material.name, unit or material.unit, qty, unit_price))
    for m in sorted(free_rows, key=lambda r: r.description):
        material_lines.append((m.description, m.unit or "", Decimal(m.quantity), Decimal("0")))

    for offset, (short_text, unit, qty, unit_price) in enumerate(material_lines, start=1):
        index = len(ordered_buckets) + offset
        db.add(InvoiceItem(
            invoice_id=invoice.id, source_order_item_id=None, sort_order=index * 10,
            position_number="", short_text=short_text, long_text="", unit=unit, unit_price=unit_price,
            soll_quantity=None, ist_quantity=qty, billed_quantity=qty, billed_total=qty * unit_price,
        ))

    db.commit()
    db.refresh(invoice)
    return invoice


FREE_ITEM_TEXT = ("Freie Positionen ohne Auftragsbezug gibt es nur in Rechnungen aus Aufwand. Ein Nachtrag kommt als Position an "
                  "den Auftrag („+ Nachtrag“ auf der Auftragsseite) und steht dann in jeder folgenden Rechnung.")
# Seit 1.8.85 (R4b Punkt 3): Einheitspreis und Einheit einer Position mit Auftragsbezug kommen aus dem Auftrag.
PRICE_FROM_ORDER_TEXT = ("Einheitspreis und Einheit einer Position mit Auftragsbezug kommen aus dem Auftrag – dort ändern (solange "
                         "sie nicht abgerechnet ist), dann „Aus dem Auftrag aktualisieren“.")
TAX_FROM_ORDER_TEXT = ("Der Steuerschlüssel einer Rechnung kommt aus dem Auftrag – dort ändern (bis zur ersten festgeschriebenen "
                       "Rechnung), dann „Aus dem Auftrag aktualisieren“.")


def add_invoice_item(
    db: Session, invoice: Invoice, *, short_text: str, long_text: str, unit: str,
    unit_price: Decimal, ist_quantity: Decimal, source_order_item_id: int | None = None,
    soll_quantity: Decimal | None = None, position_number: str | None = None,
    sort_order: int | None = None,
) -> InvoiceItem:
    """Für freie Positionen (source_order_item_id=None) sowie um
    ausdrücklich eine bestehende Auftragsposition erneut hinzuzufügen, falls
    sie zuvor entfernt wurde. Seit 1.8.70 (Befund 2i) nur eine Position des
    Auftrags dieser Rechnung -- vorher auch die eines fremden Auftrags (volle
    Menge berechnet, nach dem Festschreiben unveränderlich). Seit 1.8.75 unter
    der Sperre (_lock_draft()). Seit 1.8.83 (R4a Punkt 3) freie Positionen nur
    in Rechnungen aus Aufwand (sonst InvoiceBlocked, 409) -- ein Nachtrag kommt
    als gekennzeichnete Position an den Auftrag (app/orders.py::add_order_addendum());
    vorher stand er nur in der einen Rechnung, keine spätere übernahm oder zog ihn ab."""
    _lock_draft(db, invoice)
    if source_order_item_id is not None:
        source = db.get(OrderItem, source_order_item_id)
        if source is None or source.order_id != invoice.order_id:
            raise _reject(db, ValueError("Die Auftragsposition gehört nicht zum Auftrag dieser Rechnung."))
    if invoice.invoice_type == "abschlag_pauschal":
        raise _reject(db, ValueError(
            "Pauschale Abschlagsrechnungen haben nur die eine, automatisch erzeugte Position -- "
            "Bezeichnung und Betrag über das Pauschalbetrag-Feld ändern."
        ))
    if source_order_item_id is None and invoice.invoice_type != "aufwand":
        raise _reject(db, InvoiceBlocked(FREE_ITEM_TEXT))
    if source_order_item_id is not None and (Decimal(unit_price) != Decimal(source.unit_price or 0)
                                             or (unit or "") != (source.unit or "")):
        raise _reject(db, InvoiceBlocked(PRICE_FROM_ORDER_TEXT))
    billed_quantity, billed_total = compute_billed_quantity_and_total(
        db, invoice.order_id, invoice.id, source_order_item_id, ist_quantity, unit_price, invoice_type=invoice.invoice_type,
    )
    item = InvoiceItem(
        invoice_id=invoice.id, source_order_item_id=source_order_item_id,
        sort_order=sort_order if sort_order is not None else (len(invoice.items) + 1) * 10,
        position_number=position_number or "",
        short_text=short_text, long_text=long_text, unit=unit, unit_price=unit_price,
        soll_quantity=soll_quantity, ist_quantity=ist_quantity,
        billed_quantity=billed_quantity, billed_total=billed_total,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_invoice_item(
    db: Session, invoice: Invoice, item: InvoiceItem, *, short_text: str | None = None,
    long_text: str | None = None, unit: str | None = None, unit_price: Decimal | None = None,
    ist_quantity: Decimal | None = None,
) -> InvoiceItem:
    """Seit 1.8.75 unter der Sperre (_lock_draft()); die Position wird danach frisch geladen -- gerechnet wird mit dem Stand
    nach einer gleichzeitigen Änderung, nicht mit dem vorher geladenen."""
    _lock_draft(db, invoice)
    if invoice.invoice_type == "abschlag_pauschal":
        raise _reject(db, ValueError(
            "Die Position einer pauschalen Abschlagsrechnung ist eine reine Projektion von "
            "Bezeichnung/Betrag -- bitte dort ändern, siehe _sync_lump_sum_pauschal_item()."
        ))
    item = next((i for i in invoice.items if i.id == item.id), None)
    if item is None:
        raise _reject(db, InvoiceBlocked("Die Position wurde inzwischen entfernt."))
    # Seit 1.8.85 (R4b Punkt 3): Preis und Einheit einer Position mit Auftragsbezug nur aus dem Auftrag -- abgelehnt wird nur eine
    # tatsächliche Änderung (die Oberfläche schickt beim Speichern alle Felder).
    if item.source_order_item_id is not None and (
            (unit_price is not None and Decimal(unit_price) != Decimal(item.unit_price or 0))
            or (unit is not None and unit != item.unit)):
        raise _reject(db, InvoiceBlocked(PRICE_FROM_ORDER_TEXT))
    if short_text is not None:
        item.short_text = short_text
    if long_text is not None:
        item.long_text = long_text
    if unit is not None:
        item.unit = unit
    if unit_price is not None:
        item.unit_price = unit_price
    if ist_quantity is not None:
        item.ist_quantity = ist_quantity
    # Neuberechnung immer, auch wenn nur unit_price sich geändert hat.
    item.billed_quantity, item.billed_total = compute_billed_quantity_and_total(
        db, invoice.order_id, invoice.id, item.source_order_item_id, item.ist_quantity, item.unit_price,
        invoice_type=invoice.invoice_type,
    )
    db.commit()
    db.refresh(item)
    return item


def remove_invoice_item(db: Session, invoice: Invoice, item_id: int) -> bool:
    """Seit 1.8.75 unter der Sperre (_lock_draft())."""
    _lock_draft(db, invoice)
    if invoice.invoice_type == "abschlag_pauschal":
        raise _reject(db, ValueError("Die Position einer pauschalen Abschlagsrechnung kann nicht einzeln entfernt werden."))
    item = next((i for i in invoice.items if i.id == item_id), None)
    if item is None:
        db.rollback()  # gibt die Sperre frei
        return False
    # Aus der Collection entfernen, nicht db.delete(item) direkt -- siehe
    # ausführlicher Kommentar bei remove_material_from_service in services.py,
    # derselbe delete-orphan-Cascade-Konflikt gilt hier für Invoice.items.
    invoice.items.remove(item)
    db.commit()
    return True


def finalize_dates(invoice: Invoice, today: date) -> tuple[date, date | None]:
    """(Rechnungsdatum, Fälligkeit) beim Festschreiben an diesem Tag (seit 1.8.75, Befund 4a-4c): das Rechnungsdatum ist der
    Tag des Festschreibens, die Fälligkeit behält das Zahlungsziel des Entwurfs -- die Tage zwischen seinem Datum und seiner
    Fälligkeit (Zahlungsbedingung, sonst wie angegeben) -- und rückt mit. Vorher blieben beide auf dem Tag des Entwurfs: ein
    drei Wochen später versendeter Entwurf mit 14 Tagen Ziel war schon bei Versand überfällig. Ohne Fälligkeit (Storno)
    bleibt sie leer."""
    if invoice.due_date is None or invoice.invoice_date is None:
        return today, invoice.due_date
    return today, today + (invoice.due_date - invoice.invoice_date)


def finalize_and_send_invoice(db: Session, invoice: Invoice) -> Invoice:
    """entwurf -> versendet: vergibt die Rechnungsnummer aus dem Nummernkreis
    und sperrt die Rechnung endgültig für Bearbeitung. Bei einer Storno-
    Rechnung wird im selben Schritt die referenzierte Original-Rechnung auf
    'storniert' gesetzt -- so entsteht nie ein Zwischenzustand mit einem noch
    verwerfbaren Storno-Entwurf, aber einer bereits als storniert markierten
    Original-Rechnung.

    Seit 1.8.72 unter der Sperre der Auftragszeile und mit den Regeln aus finalize_block_reason() (InvoiceBlocked): ein
    Entwurf, der vor einer anderen Festschreibung oder einem Storno desselben Auftrags entstand, wird hier noch einmal
    geprüft. Ein zweites, gleichzeitiges Festschreiben desselben Entwurfs findet ihn danach schon festgeschrieben.

    Seit 1.8.85 (R4b Punkt 3, Befund 1b): vor der Prüfung wird der Entwurf unter der Sperre neu gerechnet (_recompute_draft():
    der Abschlag gegen den letzten Stand von jetzt, die Schlussrechnung mit der vollen Ist-Menge); die Schlussrechnung friert
    ihre Abzüge ein (InvoiceDeduction), danach ziehen die übrigen Entwürfe des Auftrags nach (_refresh_other_drafts())."""
    invoices = lock_order_invoices(db, invoice.order_id)
    if not _still_there(invoices, invoice):
        db.rollback()
        raise InvoiceBlocked("Der Entwurf wurde inzwischen gelöscht.")
    if invoice.status != "entwurf":
        db.rollback()
        raise ValueError("Nur Rechnungen im Entwurf können versendet werden.")
    db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id).execution_options(populate_existing=True)).all()
    db.expire(invoice, ["items"])
    if invoice.order is not None:
        db.expire(invoice.order, ["items"])  # seit 1.8.86: Auftrag nach Aufwand? -- Positionen nach der Sperre
    _recompute_draft(db, invoice)
    reason = finalize_block_reason(invoices, invoice)
    if reason:
        db.rollback()
        raise InvoiceBlocked(reason)
    # Seit 1.8.75: Rechnungsdatum = Tag des Festschreibens (Berlin), die Fälligkeit rückt mit (finalize_dates()).
    invoice.invoice_date, invoice.due_date = finalize_dates(invoice, berlin_today())
    # Seit 1.8.79: ab hier hält die Rechnung ihren Kunden fest (_customer_at_finalize()). Seit 1.8.80 (Vorgabe Z2b "Vorweg" 1)
    # Kunde, Name und Anschrift vom Auftrag -- frisch nach der Sperre, unter der auch ein Kundenwechsel am Auftrag läuft.
    invoice.customer_id = _customer_at_finalize(db, invoice)
    if invoice.invoice_type != "storno":
        order = db.get(Order, invoice.order_id)
        invoice.customer_name = order.customer_name
        invoice.customer_number = order.customer_number
        invoice.customer_address = order.customer_address
    # Seit 1.8.85 (R4b Punkt 2): die Abzüge der Endrechnung, wie sie unter der Sperre gelten -- vor dem Statuswechsel, danach
    # rechnet die Schlussrechnung mit ihnen statt mit den gerade gültigen.
    if invoice.invoice_type == "schluss":
        # Seit 1.8.86 (R4b Punkt 4): mit dem, was an jeder abgezogenen Rechnung jetzt noch offen ist (Zahlungshinweis) -- Zahlungen
        # buchen unter derselben Sperre (app/payments.py::lock_for_booking()).
        from .payments import payment_states  # lokal: app/payments.py importiert dieses Modul
        deducted = deductible_invoices(invoices, invoice)
        states = payment_states(db, deducted)
        for index, other in enumerate(deducted, start=1):
            state = states.get(other.id)
            invoice.deductions.append(InvoiceDeduction(
                deducted_invoice_id=other.id, sort_order=index * 10,
                open_amount=state.open if state is not None else Decimal("0.00"),
                retained_open=state.retained_open if state is not None else Decimal("0.00")))
    invoice.invoice_number = issue_number(db, "invoice")
    invoice.status = "versendet"
    invoice.finalized_at = _finalized_at(invoices)  # seit 1.8.83 (R4a Punkt 5)
    if invoice.invoice_type == "storno" and invoice.storno_of_invoice_id is not None:
        original = db.get(Invoice, invoice.storno_of_invoice_id)
        if original is not None:
            original.status = "storniert"
    _refresh_other_drafts(db, invoices, invoice)
    # Seit 1.8.82 (R4a Punkt 1): die feste Fassung im selben Commit -- keine festgeschriebene Rechnung ohne PDF in der Ablage.
    _store_fixed_pdf(db, invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def _recompute_draft(db: Session, invoice: Invoice) -> None:
    """Rechnet die abgerechneten Mengen eines Entwurfs neu, mit dem Stand unter der Sperre (seit 1.8.85, R4b Punkt 3, Befund 1b):
    beim Abschlag nach Leistungsstand Ist − letzter Stand von jetzt (vorher galt der Stand beim Anlegen bzw. letzten Bearbeiten
    -- zwei Entwürfe nebeneinander rechneten beide gegen denselben), bei der Schlussrechnung die volle Ist-Menge. Ändert nur
    billed_*, nie Ist, Preis oder Text. Ohne Commit: der Aufrufer schreibt fest oder rollt zurück."""
    if invoice.invoice_type not in ("abschlag_leistungsstand", "schluss"):
        return
    for item in invoice.items:
        if item.source_order_item_id is None:
            continue
        billed = compute_billed_quantity_and_total(db, invoice.order_id, invoice.id, item.source_order_item_id,
                                                   item.ist_quantity, item.unit_price, invoice_type=invoice.invoice_type)
        if (item.billed_quantity, item.billed_total) != billed:
            item.billed_quantity, item.billed_total = billed


def _refresh_other_drafts(db: Session, invoices: list[Invoice], finalized: Invoice) -> None:
    """Nach einem Festschreiben (auch eines Stornos) zieht jeder andere Entwurf eines Abschlags nach Leistungsstand desselben
    Auftrags seine abgerechneten Mengen nach (seit 1.8.85) -- im selben Commit, unter derselben Sperre. So zeigt die
    Rechnungsseite eines Entwurfs, was das Festschreiben ergäbe."""
    db.flush()
    for other in invoices:
        if other.id != finalized.id and other.status == EDITABLE_STATUS and other.invoice_type == "abschlag_leistungsstand":
            _recompute_draft(db, other)


def refresh_draft_from_order(db: Session, invoice: Invoice) -> Invoice:
    """„Aus dem Auftrag aktualisieren“ (seit 1.8.85, R4b Punkt 3): der Entwurf übernimmt Steuerschlüssel, Einheitspreise und
    Einheiten des Auftrags; Positionen, die nicht mehr in der Summe des Auftrags stehen, gehen heraus; beim Abschlag nach
    Leistungsstand und der Schlussrechnung kommen fehlende Positionen des Auftrags (auch spätere Nachträge) mit Ist = letzter
    Stand dazu. Ist-Mengen und Texte bleiben. Unter der Sperre (_lock_draft()); ein Storno spiegelt seine Rechnung und wird nicht
    aktualisiert."""
    _lock_draft(db, invoice)
    if invoice.invoice_type == "storno":
        raise _reject(db, InvoiceBlocked("Ein Storno spiegelt die stornierte Rechnung und wird nicht aus dem Auftrag aktualisiert."))
    order = db.scalar(select(Order).where(Order.id == invoice.order_id).execution_options(populate_existing=True))
    snapshot = _snapshot_order_fields(db, order)
    invoice.tax_key_id, invoice.vat_rate = snapshot["tax_key_id"], snapshot["vat_rate"]
    invoice.tax_notice_text = snapshot["tax_notice_text"]
    order_items = {item.id: item for item in db.scalars(
        select(OrderItem).where(OrderItem.order_id == order.id).execution_options(populate_existing=True))}
    present = set()
    for item in list(invoice.items):
        if item.source_order_item_id is None:
            continue
        source = order_items.get(item.source_order_item_id)
        if source is None or not source.include_in_total:
            invoice.items.remove(item)
            continue
        present.add(source.id)
        item.unit_price, item.unit = source.unit_price, source.unit
        item.billed_quantity, item.billed_total = compute_billed_quantity_and_total(
            db, invoice.order_id, invoice.id, item.source_order_item_id, item.ist_quantity, item.unit_price,
            invoice_type=invoice.invoice_type)
    if invoice.invoice_type in ("abschlag_leistungsstand", "schluss"):
        for source in sorted(order_items.values(), key=lambda x: (x.sort_order, x.id)):
            if source.include_in_total and source.id not in present:
                _add_order_item(db, invoice, order, source)
    db.commit()
    db.refresh(invoice)
    return invoice


def _finalized_at(invoices: list[Invoice]) -> datetime:
    """Zeitpunkt des Festschreibens (seit 1.8.83, R4a Punkt 5): jetzt (naive UTC), mindestens eine Mikrosekunde nach dem
    jüngsten des Auftrags -- unter der Sperre der Auftragszeile sind die Zeitpunkte je Auftrag so streng steigend, auch wenn die
    Uhr des Servers einmal zurückgestellt wird. Grundlage von "letzter Stand" (get_previous_cumulative_ist())."""
    now = datetime.utcnow()
    latest = max((i.finalized_at for i in invoices if i.finalized_at is not None), default=None)
    return now if latest is None or now > latest else latest + timedelta(microseconds=1)


def _store_fixed_pdf(db: Session, invoice: Invoice) -> None:
    """Die feste Fassung (seit 1.8.82, R4a Punkt 1): das PDF im Stand des Festschreibens -- Nummer, Datum, Kunde und Anschrift
    schon gesetzt --, abgelegt mit SHA-256 (app/sent_documents.py, Art "rechnung", Dokument-ID = Rechnung) und an der Rechnung
    vermerkt (Invoice.pdf_document_id). Danach entsteht es nie neu: Download, Versand und nachgetragene Zustellung nehmen die
    abgelegten Bytes, nur mit stimmender Prüfsumme (frozen_version()). Vorher (bis 1.8.81) entstand das PDF bis zum ersten Versand
    bei jedem Abruf neu -- mit dem Briefkopf und den Einstellungen von heute. Scheitert das PDF oder die Ablage, rollt das
    Festschreiben zurück (keine Nummer, kein Status) -- ValueError, Router 400. Aufruf unter der Sperre der Auftragszeile."""
    from .audit import current_actor
    from .invoice_pdf import build_invoice_pdf  # lokal: app/invoice_pdf.py importiert dieses Modul (Regel 3)
    from .sent_documents import store_sent_document

    db.flush()
    try:
        content = build_invoice_pdf(db, invoice)
        user_id, user_name = current_actor()
        document = store_sent_document(
            db, document_type="rechnung", document_id=invoice.id, document_number=invoice.invoice_number,
            filename=f"{invoice.invoice_number}.pdf", content=content, user_id=user_id, user_name=user_name,
        )
    except Exception as exc:  # noqa: BLE001 -- ohne feste Fassung kein Festschreiben
        logger.error("Rechnung %s: feste Fassung nicht erstellt (%s)", invoice.id, type(exc).__name__)
        raise _reject(db, ValueError(
            "Das PDF der Rechnung ließ sich nicht erstellen bzw. ablegen – die Rechnung ist nicht festgeschrieben, keine Nummer "
            "vergeben. Bitte erneut versuchen; bleibt es dabei, die Einstellungen (Briefkopf, Ränder) prüfen.")) from exc
    invoice.pdf_document_id = document.id


def _customer_at_finalize(db: Session, invoice: Invoice) -> int | None:
    """Der Kunde, den die Rechnung beim Festschreiben festhält (seit 1.8.79): beim Storno der Kunde der stornierten Rechnung,
    sonst seit 1.8.80 der des Auftrags (Order.customer_id, Vorgabe Z2b "Vorweg" 1; bis 1.8.79 der des Projekts) -- frisch gelesen
    nach der Sperre der Auftragszeile. Ein Kundenwechsel am Projekt nimmt dieselbe Sperre
    (app/project_participants.py::check_client_change()) und wechselt den Kunden des Auftrags mit: wartet das Festschreiben auf
    ihn, liest es danach den neuen Kunden; wartet er auf das Festschreiben, findet er die festgeschriebene Rechnung und lehnt ab."""
    if invoice.invoice_type == "storno" and invoice.storno_of_invoice_id is not None:
        original = db.get(Invoice, invoice.storno_of_invoice_id)
        if original is not None and original.customer_id is not None:
            return original.customer_id
    return db.scalar(select(Order.customer_id).where(Order.id == invoice.order_id))


def invoice_customer(invoice: Invoice) -> Customer | None:
    """Kunde der Rechnung (seit 1.8.79): festgeschrieben der festgehaltene, im Entwurf seit 1.8.80 der Kunde des Auftrags."""
    if invoice.customer_id is not None:
        return invoice.customer
    order = invoice.order
    return order.customer if order is not None else None


def invoice_customer_id(invoice: Invoice) -> int | None:
    """ID des Kunden der Rechnung (siehe invoice_customer()), ohne den Kunden zu laden."""
    if invoice.customer_id is not None:
        return invoice.customer_id
    order = invoice.order
    return order.customer_id if order is not None else None


def delete_invoice_draft(db: Session, invoice: Invoice) -> None:
    """Löscht eine Rechnung unwiderruflich -- nur im Entwurf möglich. Bewusst
    keine Nummernkreis-Rücknahme nötig: ein Entwurf hat noch keine
    Rechnungsnummer erhalten (die wird erst in finalize_and_send_invoice()
    vergeben), Löschen kann also keine Lücke in der Rechnungsnummernfolge
    reißen -- GoBD-technisch unproblematisch. Eine Stornorechnung im Entwurf
    darf ebenfalls gelöscht werden: das Original wird erst beim tatsächlichen
    Versand des Storno auf 'storniert' gesetzt (siehe finalize_and_send_invoice),
    ist also zu diesem Zeitpunkt noch unberührt und bleibt es auch.

    Seit 1.8.73 (Nebenbefund 2 aus 1.8.72) unter derselben Sperre wie das Festschreiben: gelöscht wird nur, was danach
    noch Entwurf ist, sonst InvoiceBlocked (409). Vorher prüfte das Löschen ohne Sperre -- unter PostgreSQL wartete das
    DELETE auf ein gleichzeitiges Festschreiben und löschte danach die festgeschriebene Rechnung (Nummer vergeben,
    Rechnung weg)."""
    invoices = lock_order_invoices(db, invoice.order_id)
    if not _still_there(invoices, invoice):
        db.rollback()
        raise InvoiceBlocked("Der Entwurf wurde inzwischen gelöscht.")
    if invoice.status != EDITABLE_STATUS:
        number = f" Die Rechnung ist inzwischen festgeschrieben ({invoice.invoice_number})." if invoice.invoice_number else ""
        db.rollback()
        raise InvoiceBlocked(f"Nur Rechnungen im Entwurf können gelöscht werden.{number}")
    db.delete(invoice)
    db.commit()


def create_storno_draft(db: Session, original: Invoice) -> Invoice:
    """Erzeugt den Entwurf einer Stornorechnung zu einer bereits festgeschriebenen
    Rechnung -- kehrt Betrag und alle Positionen um (negatives
    Vorzeichen). Die Original-Rechnung wird NICHT sofort auf 'storniert'
    gesetzt, sondern erst, wenn dieser Entwurf tatsächlich versendet wird
    (siehe finalize_and_send_invoice) -- ein verworfener Storno-Entwurf lässt
    die Original-Rechnung also unangetastet.

    Seit 1.8.72 (Befund 1e-1g) unter der Sperre der Auftragszeile: höchstens ein Storno je Rechnung (auch ein Entwurf
    zählt), keins eines Stornos, keins eines Abschlags hinter einer gültigen Schlussrechnung -- storno_block_reason(); seit
    1.8.78 keins, solange der Rechnung Zahlungen zugeordnet sind."""
    invoices = lock_order_invoices(db, original.order_id)
    if original.status == EDITABLE_STATUS:
        db.rollback()
        raise ValueError("Nur festgeschriebene Rechnungen können storniert werden.")
    reason = storno_block_reason(invoices, original)  # auch "schon storniert" (409 statt bis 1.8.71 400)
    if reason:
        db.rollback()
        raise InvoiceBlocked(reason)
    storno = Invoice(
        order_id=original.order_id, invoice_type="storno", status="entwurf",
        storno_of_invoice_id=original.id, invoice_date=berlin_today(),
        customer_name=original.customer_name, customer_number=original.customer_number,
        customer_address=original.customer_address, property_name=original.property_name,
        property_address=original.property_address, vat_rate=original.vat_rate,
        tax_key_id=original.tax_key_id, tax_notice_text=original.tax_notice_text,
        progress_description=f"Stornierung zu Rechnung {original.invoice_number or '(Entwurf)'}",
        lump_sum_net=(-original.lump_sum_net if original.lump_sum_net is not None else None),
        # Seit 1.8.74: der Leistungszeitraum der stornierten Rechnung (vor 1.8.74 festgeschrieben: leer, dann von Hand).
        service_period_start=original.service_period_start, service_period_end=original.service_period_end,
    )
    db.add(storno)
    db.flush()
    # Seit 1.8.11: dieselbe Rundungsregel wie das Original, damit sich beide auf den Cent aufheben.
    # Erst nach dem flush: ein None im Konstruktor ersetzt SQLAlchemy durch den Vorgabewert "half_up".
    storno.rounding_rule = original.rounding_rule
    if original.invoice_type == "abschlag_pauschal" and not original.items:
        # Seit 1.8.83 (R4a Punkt 6, Befund 1d): ein pauschaler Abschlag von vor 1.3.24 hat keine Position, sein Betrag steht nur
        # in lump_sum_net -- das Storno (Art "storno", gerechnet aus den Positionen) lautete deshalb über 0 €. Es bekommt die
        # Projektionsposition, die das Original heute hätte, mit umgekehrtem Vorzeichen: Gegenbetrag des Originals.
        amount = original.lump_sum_net if original.lump_sum_net is not None else Decimal("0")
        db.add(InvoiceItem(
            invoice_id=storno.id, sort_order=10, position_number="1",
            short_text=original.progress_description or "Abschlagszahlung gemäß Auftrag", long_text="", unit=LUMP_SUM_ITEM_UNIT,
            unit_price=amount, soll_quantity=Decimal("1"), ist_quantity=Decimal("1"),
            billed_quantity=Decimal("-1"), billed_total=-amount,
        ))
    for item in original.items:
        db.add(InvoiceItem(
            invoice_id=storno.id, source_order_item_id=item.source_order_item_id,
            sort_order=item.sort_order, position_number=item.position_number, gaeb_oz=item.gaeb_oz,
            short_text=item.short_text, long_text=item.long_text, unit=item.unit, unit_price=item.unit_price,
            soll_quantity=item.soll_quantity, ist_quantity=item.ist_quantity,
            billed_quantity=-item.billed_quantity, billed_total=-item.billed_total,
        ))
    db.commit()
    db.refresh(storno)
    return storno


def visible_items(invoice: Invoice) -> list[InvoiceItem]:
    """Positionen mit ist_quantity=0 werden auf der Rechnung selbst nicht
    angezeigt (bleiben aber in der Datenbank für die Soll/Ist-Historie
    bestehen) -- von der PDF-/Anzeigelogik zu verwenden, nicht list(invoice.items)."""
    return [item for item in invoice.items if item.ist_quantity != 0]


INVOICE_HEADER_FIELDS = ("due_date", "progress_description", "lump_sum_net", "intro_text", "outro_text",
                         "outro_text_2", "payment_terms", "service_period_start", "service_period_end",
                         "closes_order")  # closes_order seit 1.8.86


def update_invoice_header(db: Session, invoice: Invoice, **changes) -> Invoice:
    """Teil-Update (seit 1.8.25): nur die übergebenen Felder ändern sich -- "Pauschale speichern"
    leerte vorher den Schlusstext 2, den es nicht mitschickte. Seit 1.8.75 unter der Sperre (_lock_draft())."""
    unknown = set(changes) - set(INVOICE_HEADER_FIELDS)
    if unknown:
        raise TypeError(f"Unbekannte Felder: {sorted(unknown)}")
    _lock_draft(db, invoice)
    if invoice.invoice_type != "abschlag_pauschal":
        changes.pop("lump_sum_net", None)
    # Seit 1.8.74: Leistungszeitraum -- Ende >= Beginn, auch wenn nur eine Seite gesendet wird (gegen den gespeicherten Wert,
    # seit 1.8.75 den nach der Sperre).
    try:
        check_order(changes.get("service_period_start", invoice.service_period_start),
                    changes.get("service_period_end", invoice.service_period_end))
    except ValueError as e:
        raise _reject(db, e) from None
    # Seit 1.8.86 (R4b Punkt 6): "abschließend" nur an einer Rechnung aus Aufwand eines Auftrags nach Aufwand.
    if changes.get("closes_order"):
        if invoice.order is not None:
            db.expire(invoice.order, ["items"])
        reason = closing_block_reason(list(db.scalars(select(Invoice).where(Invoice.order_id == invoice.order_id))), invoice)
        if reason:
            raise _reject(db, InvoiceBlocked(reason))
    elif "closes_order" in changes:
        changes["closes_order"] = False
    for key, value in changes.items():
        setattr(invoice, key, value)
    if invoice.invoice_type == "abschlag_pauschal":
        _sync_lump_sum_pauschal_item(db, invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def update_invoice_payment_term(db: Session, invoice: Invoice, payment_term_id: int) -> Invoice:
    """Setzt Bezeichnung, Fälligkeitsdatum UND Skonto aus einer gewählten
    Zahlungsbedingung neu (invoice_date + Tage) -- die Dropdown-Auswahl aus
    der Erfassungsoberfläche, getrennt von update_invoice_header, da dort
    due_date auch weiterhin direkt (unabhängig von einer Zahlungsbedingung)
    gesetzt werden kann. Seit 1.8.75 unter der Sperre (_lock_draft()); das
    Festschreiben rückt die Fälligkeit danach mit dem Rechnungsdatum auf den
    Tag des Festschreibens (finalize_dates())."""
    _lock_draft(db, invoice)
    term = db.get(PaymentTerm, payment_term_id)
    if term is None:
        raise _reject(db, ValueError("Zahlungsbedingung nicht gefunden."))
    invoice.payment_terms = term.label
    invoice.due_date = invoice.invoice_date + timedelta(days=term.days)
    invoice.skonto_percent = term.skonto_percent
    invoice.skonto_days = term.skonto_days
    invoice.payment_terms_text_template = term.text_template
    db.commit()
    db.refresh(invoice)
    return invoice


def update_invoice_tax_key(db: Session, invoice: Invoice, tax_key_id: int) -> Invoice:
    """Setzt tax_key_id, vat_rate UND den eingefrorenen Hinweistext neu --
    wie bei Skonto/Zahlungsbedingung eingefroren, nicht live nachgeladen (der
    Grund steht ausführlich am Invoice.tax_notice_text-Feld in models.py).
    Seit 1.8.75 unter der Sperre (_lock_draft())."""
    _lock_draft(db, invoice)
    key = db.get(TaxKey, tax_key_id)
    if key is None:
        raise _reject(db, ValueError("Steuerschlüssel nicht gefunden."))
    # Seit 1.8.85 (R4b Punkt 3, Befund R4 Nebenbefund 2 aus 1.8.82): nur der Schlüssel des Auftrags -- beim Storno der der
    # stornierten Rechnung. Vorher wählte jede Rechnung einen beliebigen (Abschlag 0 %, Schlussrechnung 19 %).
    if invoice.invoice_type == "storno":
        original = db.get(Invoice, invoice.storno_of_invoice_id) if invoice.storno_of_invoice_id else None
        expected = original.tax_key_id if original is not None else invoice.tax_key_id
        if tax_key_id != expected:
            raise _reject(db, InvoiceBlocked("Ein Storno hat den Steuerschlüssel der stornierten Rechnung."))
    elif tax_key_id != db.scalar(select(Order.tax_key_id).where(Order.id == invoice.order_id)):
        raise _reject(db, InvoiceBlocked(TAX_FROM_ORDER_TEXT))
    invoice.tax_key_id = tax_key_id
    invoice.vat_rate = key.vat_rate
    invoice.tax_notice_text = key.notice_text
    db.commit()
    db.refresh(invoice)
    return invoice


def skonto_offer(invoice: Invoice) -> tuple[date, Decimal] | None:
    """(Skontodatum, Skontobetrag) laut Rechnung, None ohne Skonto -- derselbe Betrag wie im Zahlungssatz ({skontobetrag}:
    der Abzug, nicht der Zahlbetrag); seit 1.8.78 auch Grundlage des Skonto-Vorschlags beim Zahlungseingang
    (app/payments.py::proposal())."""
    if not (invoice.skonto_percent and invoice.skonto_days is not None):
        return None
    gross = compute_invoice_totals(invoice)["gross_total"]
    if gross <= 0:  # seit 1.8.90 (R4c Punkt 6): Skonto nur bei positivem Rechnungsbetrag
        return None
    until = invoice.invoice_date + timedelta(days=invoice.skonto_days)
    return until, (gross * invoice.skonto_percent / Decimal("100")).quantize(CENT, rounding=invoice_rounding(invoice))


def format_payment_terms_sentence(invoice: Invoice) -> str:
    """Automatisch aus Fälligkeitsdatum und Skonto erzeugter Satz mit echten
    Daten (nicht nur der abstrakten Bezeichnung wie '14 Tage netto') --
    zusammen mit dem Schlusstext auf Rechnung/PDF angezeigt. Absichtlich hier
    und nicht in invoice_pdf.py erzeugt, damit Oberfläche und PDF exakt
    denselben Text zeigen, nicht zwei unabhängig gepflegte Formulierungen.

    Ist auf der Zahlungsbedingung eine eigene Textvorlage hinterlegt (seit
    1.0.42, invoice.payment_terms_text_template), wird die stattdessen
    verwendet -- mit denselben, per .replace() ersetzten Platzhaltern wie
    unten. Ein unbekannter/falsch geschriebener Platzhalter bleibt einfach
    als Text stehen (kein Fehler), damit ein Tippfehler in der Vorlage nicht
    die ganze Rechnung blockiert.

    Seit 1.8.90 (R4c Punkt 6): weist der Zahlungshinweis einer Endrechnung einen Erstattungsbetrag aus, steht statt der
    Zahlungsbedingungen (auch statt einer Textvorlage) der Satz zur Erstattung -- ohne Skonto und ohne "zahlbar"."""
    refund = refund_due(invoice) if invoice.invoice_type == "schluss" else None
    if refund is not None:
        return refund_sentence(refund)
    if invoice.due_date is None:
        return ""
    due_str = invoice.due_date.strftime("%d.%m.%Y")
    offer = skonto_offer(invoice)
    has_skonto = offer is not None
    skonto_date_str = percent_text = amount_text = ""
    if has_skonto:
        skonto_date, skonto_amount = offer
        skonto_date_str = skonto_date.strftime("%d.%m.%Y")
        percent_text = f"{invoice.skonto_percent:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        amount_text = f"{skonto_amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    if invoice.payment_terms_text_template:
        return (
            invoice.payment_terms_text_template
            .replace("{faelligkeitsdatum}", due_str)
            .replace("{skontodatum}", skonto_date_str)
            .replace("{skontoprozent}", percent_text)
            .replace("{skontobetrag}", amount_text)
        )

    sentence = f"Zahlbar rein netto bis zum {due_str}."
    if has_skonto:
        sentence += (
            f" Bei Zahlung bis zum {skonto_date_str} gewähren wir "
            f"{percent_text} % Skonto, das entspricht {amount_text} €."
        )
    return sentence


def _service_period_info(invoice: Invoice) -> dict:
    start, end = invoice.service_period_start, invoice.service_period_end
    db = object_session(invoice)
    return {
        "service_period_start": start,
        "service_period_end": end,
        "service_period_text": period_text(start, end) if start is not None and end is not None and end >= start else None,
        "service_period_proposal": (service_period_proposal(db, invoice).as_dict()
                                    if invoice.status == EDITABLE_STATUS and db is not None and invoice.order is not None
                                    else None),
    }


def _de(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def send_hint(invoice: Invoice, today: date) -> str | None:
    """Hinweis beim Versand an einem späteren Tag als dem Rechnungsdatum (seit 1.8.75): Fälligkeit und Skontofrist rechnen ab
    dem Rechnungsdatum (Tag des Festschreibens), nicht ab dem Versand. Nur für eine festgeschriebene, nicht bezahlte (seit
    1.8.78 aus den gebuchten Zahlungen, app/payments.py)."""
    if invoice.status != "versendet" or invoice.invoice_date is None or invoice.invoice_date >= today:
        return None
    db = object_session(invoice)
    if db is not None:
        from .payments import payment_state  # lokal: Zirkel-Import
        state = payment_state(db, invoice)
        if state is not None and state.state == "bezahlt":
            return None
    text = f"Die Rechnung ist vom {_de(invoice.invoice_date)} (Tag des Finalisierens), heute ist der {_de(today)}."
    if invoice.due_date is None:
        return text
    skonto_until = (invoice.invoice_date + timedelta(days=invoice.skonto_days)
                    if invoice.skonto_percent and invoice.skonto_days is not None else None)
    deadlines = f"Fälligkeit ({_de(invoice.due_date)})" + (f" und Skontofrist (bis {_de(skonto_until)})" if skonto_until else "")
    text += f" {deadlines} rechnen ab dem Rechnungsdatum, nicht ab dem Versand."
    if invoice.due_date < today:
        text += " Die Fälligkeit ist schon überschritten."
    elif skonto_until is not None and skonto_until < today:
        text += " Die Skontofrist ist schon abgelaufen."
    return text


def _date_info(invoice: Invoice) -> dict:
    """Seit 1.8.75: im Entwurf, was das Festschreiben heute als Rechnungsdatum und Fälligkeit setzen würde (nur Anzeige);
    danach der Hinweis für einen späteren Versand."""
    today = berlin_today()
    if invoice.status == EDITABLE_STATUS:
        invoice_date, due_date = finalize_dates(invoice, today)
        days = (invoice.due_date - invoice.invoice_date).days if invoice.due_date and invoice.invoice_date else None
        return {"finalize_dates": {"invoice_date": invoice_date, "due_date": due_date, "payment_days": days},
                "send_hint": None}
    return {"finalize_dates": None, "send_hint": send_hint(invoice, today)}


def _action_blocks(invoice: Invoice) -> dict:
    invoices = list(invoice.order.invoices) if invoice.order is not None else [invoice]
    return {
        "finalize_block": finalize_block_reason(invoices, invoice) if invoice.status == EDITABLE_STATUS else None,
        "storno_block": storno_block_reason(invoices, invoice) if invoice.status in VALID_STATUSES else None,
        # Seit 1.8.85 (R4b Punkt 3): weicht der Entwurf vom Auftrag ab, zeigt die Rechnungsseite „Aus dem Auftrag aktualisieren“.
        "order_deviation": order_deviation_reason(invoice) if invoice.status == EDITABLE_STATUS else None,
        # Seit 1.8.86 (R4b Punkt 6): warum sich eine Rechnung aus Aufwand nicht als abschließend kennzeichnen lässt (None: sie kann).
        "closing_block": (closing_block_reason(invoices, invoice)
                          if invoice.invoice_type == "aufwand" and invoice.status == EDITABLE_STATUS else None),
    }


def _payment_info(invoice: Invoice, state=None, *, with_allocations: bool, dunning=None) -> dict:
    """Seit 1.8.78: Zahlstand (offen, mahnfähig, Zustand) statt Status "bezahlt"; überfällig nur mit mahnfähigem Betrag (ein
    offener Einbehalt wird nicht gemahnt, eine Stornorechnung ist nie offen). Seit 1.8.89 (R4c, app/final_dunning.py) überfällig
    nach dem angemahnten Betrag: eine in einer gültigen Endrechnung abgezogene Rechnung nie (gemahnt wird über die Endrechnung), die
    Endrechnung auch, wenn nur noch ein abgezogener Abschlag offen ist; dazu "dunning" und der Hinweis an der abgezogenen. Seit 1.8.91
    "overview": wie die Rechnung in Finanzen, Dashboard und den Rechnungslisten zählt (app/final_dunning.py::overview())."""
    from .final_dunning import deducted_hint, dunning_state, overview  # lokal: app/final_dunning.py importiert dieses Modul
    from .payments import invoice_allocations, not_payable_reason, payment_state  # lokal: Zirkel-Import
    db = object_session(invoice)
    if state is None and db is not None:
        state = payment_state(db, invoice)
    if dunning is None and db is not None and invoice.status in VALID_STATUSES:
        dunning = dunning_state(db, invoice)
    info = {
        "payment": state.as_dict() if state is not None else None,
        "not_payable_reason": not_payable_reason(invoice) if invoice.status != EDITABLE_STATUS else None,
        "is_overdue": (dunning is not None and dunning.dunnable > 0 and invoice.due_date is not None
                       and invoice.due_date < berlin_today()),
        "dunning": dunning.as_dict() if dunning is not None else None,
        "dunning_hint": deducted_hint(dunning) if dunning is not None else None,
        "overview": overview(state, dunning),
    }
    if with_allocations:
        info["payment_allocations"] = invoice_allocations(db, invoice) if db is not None else []
    return info


def invoice_to_dict(invoice: Invoice) -> dict:
    """Rechnung inkl. Positionen und berechneter Summen für API-Antworten und
    PDF-Erzeugung. visible_items() (Ist=0 ausgeblendet) wird bewusst NICHT
    hier angewendet -- die Erfassungsoberfläche muss auch Positionen mit
    Ist=0 sehen und bearbeiten können, nur die PDF-Ausgabe blendet sie aus."""
    totals = compute_invoice_totals(invoice)
    items = sorted(invoice.items, key=lambda x: (x.sort_order, x.id))
    quantity_checks = final_quantity_checks(invoice)  # seit 1.8.88: Entwurf der Schlussrechnung
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "order_id": invoice.order_id,
        # Für die Breadcrumb (seit 1.3.23, Muster property.html/roof_area.html) -- invoice_to_dict()
        # kannte bisher nur order_id, nicht den Weg zurück zu Auftrag/Projekt/Kunde.
        "order_number": invoice.order.order_number,
        "project_id": invoice.order.project_id,
        "project_number": invoice.order.project.project_number,
        "customer_id": invoice_customer_id(invoice),  # seit 1.8.79 der festgehaltene Kunde
        "invoice_type": invoice.invoice_type,
        "status": invoice.status,
        "invoice_date": invoice.invoice_date,
        "due_date": invoice.due_date,
        "storno_of_invoice_id": invoice.storno_of_invoice_id,
        "customer_name": invoice.customer_name,
        "customer_number": invoice.customer_number,
        "customer_address": invoice.customer_address,
        "property_name": invoice.property_name,
        "property_address": invoice.property_address,
        "vat_rate": invoice.vat_rate,
        "lump_sum_net": invoice.lump_sum_net,
        "progress_description": invoice.progress_description,
        "intro_text": invoice.intro_text,
        "outro_text": invoice.outro_text,
        "outro_text_2": invoice.outro_text_2,
        "payment_terms": invoice.payment_terms,
        "tax_key_id": invoice.tax_key_id,
        "tax_notice_text": invoice.tax_notice_text,
        "skonto_percent": invoice.skonto_percent,
        "skonto_days": invoice.skonto_days,
        "payment_terms_sentence": format_payment_terms_sentence(invoice),
        "is_editable": is_invoice_editable(invoice),
        # Seit 1.8.78: Zahlstand und Zuordnungen, überfällig nur mit mahnfähigem Betrag (app/payments.py).
        **_payment_info(invoice, with_allocations=True),
        # Seit 1.8.72: warum "Finalisieren" bzw. "Stornieren" gesperrt ist -- die Rechnungsseite zeigt den Grund statt des Knopfs.
        **_action_blocks(invoice),
        # Seit 1.8.74: Leistungszeitraum, im Entwurf mit Vorschlag samt Quelle (übernommen nur per Klick).
        **_service_period_info(invoice),
        # Seit 1.8.75: Rechnungsdatum = Tag des Festschreibens -- Vorschau im Entwurf, Hinweis beim späteren Versand.
        **_date_info(invoice),
        "items": [
            {
                "id": i.id, "source_order_item_id": i.source_order_item_id, "sort_order": i.sort_order,
                "position_number": i.position_number, "gaeb_oz": i.gaeb_oz, "short_text": i.short_text,
                "long_text": i.long_text, "unit": i.unit, "unit_price": i.unit_price,
                "soll_quantity": i.soll_quantity, "ist_quantity": i.ist_quantity,
                "billed_quantity": _billed(invoice, i)[0], "billed_total": invoice_line_total(invoice, i),
                # Seit 1.8.88: im Entwurf der Schlussrechnung Menge des Auftrags, zuletzt abgerechnet, Abweichungen des Ist.
                "quantity_check": quantity_checks.get(i.id),
            }
            for i in items
        ],
        # Seit 1.8.85 (R4b Punkt 2): Aufstellung der Endrechnung (Gesamtleistung, Abzüge, Rechnungsbetrag), sonst leer.
        "final_breakdown": breakdown.as_dict() if (breakdown := final_breakdown(invoice)) is not None else None,
        # Seit 1.8.86 (R4b Punkte 4 und 6): Zahlungshinweis der Endrechnung; abschließende Rechnung aus Aufwand.
        "payment_note": payment_note(invoice),
        "closes_order": bool(invoice.closes_order),
        "email_sent_at": invoice.email_sent_at,
        "email_sent_to": invoice.email_sent_to,
        "recipient_email": get_invoice_recipient_email(invoice),
        **totals,
    }


def list_invoices_for_order(db: Session, order_id: int) -> list[Invoice]:
    return db.scalars(
        select(Invoice).where(Invoice.order_id == order_id).order_by(Invoice.created_at)
    ).all()


def get_invoice(db: Session, invoice_id: int) -> Invoice | None:
    return db.get(Invoice, invoice_id)


def invoice_summary_for_order(db: Session, order_id: int) -> tuple[int, bool]:
    """(Anzahl nicht stornierter Rechnungen, vollständig abgerechnet) -- für
    die Anzeige in Projektmappe/Auftragsliste, ohne dort die komplette
    Rechnungsliste laden zu müssen. 'Vollständig abgerechnet' heißt: eine
    finalisierte (nicht mehr im Entwurf, nicht stornierte) Schlussrechnung
    existiert."""
    invoices = list_invoices_for_order(db, order_id)
    active = [i for i in invoices if i.status != "storniert"]
    fully_invoiced = bool(closing_invoices(active))  # seit 1.8.86 auch eine abschließende Rechnung aus Aufwand
    return len(active), fully_invoiced


def compute_order_billing_progress(db: Session, order_id: int) -> dict:
    """Wie viel von einem Auftrag bereits (verbindlich) abgerechnet wurde,
    Netto und Brutto -- für die Anzeige im Auftrag selbst. Zählt nur
    festgeschriebene Rechnungen; Entwürfe zählen bewusst
    nicht mit, da sie noch nicht endgültig sind. Stornierte Rechnungen UND
    die zugehörigen Storno-Rechnungen selbst zählen bewusst BEIDE nicht mit
    (nicht: eine zählt positiv, die andere negativ) -- sonst würde eine
    stornierte Position fälschlich einen negativen Betrag beitragen, statt
    schlicht wieder auf 'nicht abgerechnet' zurückzufallen."""
    invoices = list_invoices_for_order(db, order_id)
    counted = [i for i in invoices if i.status in VALID_STATUSES and i.invoice_type != "storno"]
    invoiced_net = Decimal("0")
    invoiced_gross = Decimal("0")
    for inv in counted:
        totals = compute_invoice_totals(inv)
        invoiced_net += totals["net_total"]
        invoiced_gross += totals["gross_total"]
    return {"invoiced_net": invoiced_net, "invoiced_gross": invoiced_gross}


def list_all_invoices(db: Session, *, status: str | None = None) -> list[Invoice]:
    """Systemweite Rechnungsliste für die Finanzen-Übersicht -- unabhängig
    vom jeweiligen Auftrag/Projekt, mit optionalem Status-Filter."""
    stmt = select(Invoice).order_by(Invoice.created_at.desc())
    if status:
        stmt = stmt.where(Invoice.status == status)
    return db.scalars(stmt).all()


def list_invoices_for_project(db: Session, project_id: int) -> list[Invoice]:
    """Alle Rechnungen über alle Aufträge eines Projekts hinweg gebündelt --
    für den eigenen Rechnungen-Reiter in der Projektmappe."""
    return db.scalars(
        select(Invoice)
        .join(Order, Invoice.order_id == Order.id)
        .where(Order.project_id == project_id)
        .order_by(Invoice.created_at.desc())
    ).all()


def invoice_overview_rows(db: Session, invoices: list[Invoice]) -> list[dict]:
    """Zeilen für Finanzen und Projektmappe, der Zahlstand aller Rechnungen in einer Abfrage (seit 1.8.78); seit 1.8.89 auch, was zu
    jeder gemahnt werden kann (app/final_dunning.py, für "überfällig")."""
    from .final_dunning import dunning_states  # lokal: app/final_dunning.py importiert dieses Modul
    from .payments import payment_states  # lokal: Zirkel-Import
    states = payment_states(db, invoices)
    dunning = dunning_states(db, [inv for inv in invoices if inv.status in VALID_STATUSES])
    return [invoice_overview_row(inv, states.get(inv.id), dunning.get(inv.id)) for inv in invoices]


def invoice_overview_row(invoice: Invoice, state=None, dunning=None) -> dict:
    """Leichtgewichtige Zeile für die Finanzen-Übersicht (ohne Positionen,
    dafür mit Auftrags-/Projektbezug) -- bewusst getrennt von
    invoice_to_dict(), das für Detailansicht/PDF die volle Positionsliste
    mitliefert, die hier für eine Liste vieler Rechnungen unnötig wäre.
    Seit 1.8.78 mit Zahlstand (state aus invoice_overview_rows(), sonst einzeln geladen)."""
    totals = compute_invoice_totals(invoice)
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "invoice_type": invoice.invoice_type,
        "status": invoice.status,
        "invoice_date": invoice.invoice_date,
        "due_date": invoice.due_date,
        **_payment_info(invoice, state, with_allocations=False, dunning=dunning),
        "customer_name": invoice.customer_name,
        "order_id": invoice.order_id,
        "order_number": invoice.order.order_number if invoice.order else None,
        "project_number": invoice.order.project.project_number if invoice.order and invoice.order.project else None,
        "gross_total": totals["gross_total"],
    }


DEFAULT_INVOICE_EMAIL_SUBJECT = "Rechnung {rechnungsnummer}"
DEFAULT_INVOICE_EMAIL_BODY = (
    "Sehr geehrte Damen und Herren,\n\n"
    "anbei erhalten Sie unsere Rechnung {rechnungsnummer} vom {rechnungsdatum} "
    "über {gesamtbetrag}. Alle Einzelheiten entnehmen Sie bitte dem beigefügten PDF.\n\n"
    "Mit freundlichen Grüßen"
)
# Seit 1.8.90 (R4c Punkt 7): Platzhalter des Zahlungshinweises einer Endrechnung.
PAYMENT_NOTE_PLACEHOLDERS = ("{zahlbetrag}", "{erstattungsbetrag}", "{zahlungshinweis}")


def payment_note_sentence(invoice: Invoice) -> str:
    """Der Satz der E-Mail zum Zahlungshinweis einer Endrechnung (seit 1.8.90, R4c Punkt 7): der Zahlbetrag bzw. der
    Erstattungsbetrag laut Zahlungshinweis (Stand des PDFs) -- leer für jede andere Rechnung."""
    note = payment_note(invoice)
    if note is None:
        return ""
    as_of = note["as_of"].strftime("%d.%m.%Y")
    if note["refund_amount"] is not None:
        return (f"Laut Zahlungshinweis (Stand {as_of}) ergibt sich ein Erstattungsbetrag von {_eur(note['refund_amount'])} – "
                "den überweisen wir Ihnen.")
    return f"Laut Zahlungshinweis (Stand {as_of}) beträgt der Zahlbetrag {_eur(note['pay_amount'])}."


def _with_payment_note(body: str, template: str, sentence: str) -> str:
    """Seit 1.8.90: nennt die Vorlage keinen Platzhalter des Zahlungshinweises, steht sein Satz als eigener Absatz vor dem letzten
    (dem Gruß) -- so nennt jede E-Mail zur Endrechnung den Zahl- bzw. Erstattungsbetrag, auch mit einer eigenen Vorlage."""
    if not sentence or any(p in template for p in PAYMENT_NOTE_PLACEHOLDERS):
        return body
    parts = body.rstrip().split("\n\n")
    if len(parts) < 2:
        return body.rstrip() + "\n\n" + sentence
    return "\n\n".join(parts[:-1] + [sentence, parts[-1]])


def get_invoice_recipient_email(invoice: Invoice) -> str | None:
    """Aktuelle, live nachgeschlagene Kunden-E-Mail -- analog zu
    get_reminder_recipient_email() in app/reminders.py. Bewusst defensiv
    gegen fehlende Zwischenglieder (order/project/customer). Seit 1.8.79 die des Kunden der Rechnung (invoice_customer())."""
    customer = invoice_customer(invoice)
    return (customer.email or None) if customer else None


def send_invoice_email(
    db: Session, invoice: Invoice, *, to_email: str | None = None, cc_email: str | None = None,
    dispatch_key: str | None = None, user=None,
) -> Invoice:
    """Versendet eine bereits finalisierte Rechnung tatsächlich per E-Mail
    (seit 1.0.82) -- analog zu send_reminder_email() in app/reminders.py.
    Kann auch mehrfach aufgerufen werden (z.B. erneuter Versand), aktualisiert
    email_sent_at/email_sent_to bei jedem Aufruf neu.

    to_email überschreibt die automatisch ermittelte Kunden-E-Mail nur für
    DIESEN Versand, ändert aber nie die Kundenstammdaten selbst.

    PDF-Erzeugung und E-Mail-Versand erfolgen hier lokal importiert (nicht
    am Modulanfang), um Zirkel-Importe zu vermeiden -- analog zur
    Begründung bei send_reminder_email().

    Seit 1.8.17 über app/email_dispatch.py: Versandprotokoll, Ablage des PDFs, Sperre gegen
    Doppelversand (dispatch_key; ohne Schlüssel wird einer erzeugt -- die API verlangt ihn),
    mehrere Empfänger und CC. Ein schon gesendeter Schlüssel ändert nichts mehr.

    Seit 1.8.19 geht ab dem ersten Versand die abgelegte Fassung hinaus, nicht ein neu erzeugtes
    PDF (app/sent_documents.py::frozen_or_fresh_pdf()) -- auch bei einer Stornorechnung. Seit 1.8.82 schon
    beim ersten Versand: die feste Fassung vom Festschreiben (_store_fixed_pdf())."""
    from .document_email_templates import get_email_template
    from .email_dispatch import actor_of, dispatch_email, mark_document_sent, new_dispatch_key
    from .invoice_pdf import build_invoice_pdf
    from .sent_documents import ArchiveFileError, frozen_or_fresh_pdf

    if invoice.status == "entwurf":
        raise ValueError("Nur bereits versendete Rechnungen können per E-Mail versendet werden.")

    recipient = (to_email or "").strip() or get_invoice_recipient_email(invoice)
    if not recipient:
        raise ValueError("Keine E-Mail-Adresse hinterlegt und keine wurde manuell angegeben.")

    totals = compute_invoice_totals(invoice)
    money = lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"  # noqa: E731
    # Seit 1.8.90 (R4c Punkt 7): an der Endrechnung der Zahl- bzw. Erstattungsbetrag laut Zahlungshinweis, sonst der Rechnungsbetrag.
    note = payment_note(invoice) if invoice.invoice_type == "schluss" else None
    sentence = payment_note_sentence(invoice) if note is not None else ""
    placeholders = {
        "{rechnungsnummer}": invoice.invoice_number or "",
        "{rechnungsdatum}": invoice.invoice_date.strftime("%d.%m.%Y"),
        "{faelligkeitsdatum}": invoice.due_date.strftime("%d.%m.%Y") if invoice.due_date else "",
        "{gesamtbetrag}": money(totals["gross_total"]),
        "{kundenname}": invoice.customer_name,
        "{zahlbetrag}": (money(totals["gross_total"]) if note is None
                         else money(note["pay_amount"]) if note["refund_amount"] is None else ""),
        "{erstattungsbetrag}": money(note["refund_amount"]) if note is not None and note["refund_amount"] is not None else "",
        "{zahlungshinweis}": sentence,
    }

    template = get_email_template(db, "invoice")
    subject_template = (template.subject_template if template else None) or DEFAULT_INVOICE_EMAIL_SUBJECT
    body_template = (template.body_template if template else None) or DEFAULT_INVOICE_EMAIL_BODY
    subject = apply_placeholders(subject_template, placeholders)
    body = _with_payment_note(apply_placeholders(body_template, placeholders), body_template, sentence)

    try:
        pdf = frozen_or_fresh_pdf(db, "rechnung", invoice.id, build=lambda: build_invoice_pdf(db, invoice),
                                  filename=f"{invoice.invoice_number}.pdf")
    except ArchiveFileError as e:
        raise ValueError(f"Die versendete Fassung dieser Rechnung in der Ablage ist nicht mehr unversehrt: {e} "
                         "Es wurde nichts versendet -- bitte im Versandprotokoll prüfen.") from e
    user_id, user_name = actor_of(user)
    result = dispatch_email(
        db, dispatch_key=dispatch_key or new_dispatch_key("rechnung"), document_type="rechnung",
        document_id=invoice.id, document_number=invoice.invoice_number, to=recipient, cc=cc_email,
        subject=subject, body_text=body, attachment_bytes=pdf.content, attachment_filename=pdf.filename,
        archived_document=pdf.archived, user_id=user_id, user_name=user_name,
    )
    # Seit 1.8.75 schreibt auch der Versandnachweis an der Rechnung (email_sent_at/_to) unter der Sperre -- erst nach dem
    # Senden genommen, damit sie nicht über die Verbindung zum Mailserver gehalten wird (Festlegung 1.8.72 Nr. 6).
    if result.newly_sent:  # sonst schreibt mark_document_sent() nichts
        lock_order_invoices(db, invoice.order_id)
    mark_document_sent(db, invoice, result)
    return invoice
