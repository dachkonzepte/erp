"""Schaufenster des Kundenportals (seit 1.11.41, Stufe P2d; Bauplan P2, B3; Entscheidungen P2-7, P2-8; Nachtrag 2 des Betriebs).

Zahlstand und Termine rechnet nur das ERP -- eine zweite Rechnung in plpgsql liefe auseinander. Der Postbote (app/portal_postbote.py) legt das Ergebnis je
Kunde mit Portal ab (portal_rechnungen, portal_termine, portal_schaufenster); die Funktionen der Datenbank lesen nur das (ab 1.11.42):

- Rechnungen: nur, was der Kunde sehen darf (Bauplan P2, B7: Schaufenster-Zeilen nur für sichtbare Rechnungen) -- eine Rechnung mit Freigabe für diesen
  Kunden, nicht zurückgenommen, deren Kette heute gilt (app/portal_freigaben.py::kette(), wie portal_quelle()); ob ihre Kopie bereit ist, prüft die Funktion
  der Datenbank. Zahlstand aus app/invoices.py::invoice_overview_rows() -- derselben Rechnung wie Finanzen, Kundenakte und Rechnungslisten. Zustand nach P2-7: offen | teilweise bezahlt (mit offenem Betrag) | bezahlt | Guthaben | in Schlussrechnung
  enthalten, dazu storniert und Storno (mit der Nummer der stornierten). „Offen“ ist nur, was das ERP mahnen würde (offen minus Einbehalt) -- ein offener
  Einbehalt oder ein genutztes Skonto ist nie offen, nie überfällig. Überfällig nur mit mahnfähigem Betrag nach der Fälligkeit (is_overdue der Rechnungsliste).
  Ob der Kunde eine Rechnung sieht, entscheidet ihre Freigabe (die Funktion der Datenbank prüft sie), nicht diese Tabelle.
- Termine (P2-8): je laufendem oder pausiertem Auftrag des Kunden (Order.customer_id) in einem offenen Projekt (kein Mustervorgang, nicht im Archiv, P2-11)
  die Folgen von Tagen eines festen Einsatzes der Art Baustelle, an denen jemand eingeplant ist (die Tage je Person wie die Plantafel,
  app/planning.py::_tage_der_zeile()) -- ohne Namen, Kolonne, Gerät, Notiz; vorläufige nie; abgeschlossene und stornierte Aufträge nie (wie die Plantafel).
- Wann: auf den Weckruf portal_schaufenster (Auslöser an den Tabellen aus app/portal/weckruf.py::TABELLEN_SCHAUFENSTER) und auf den der Freigaben
  (portal_post: eine Rechnung wird sichtbar oder nicht), beim Start des Postboten und alle 15 Minuten (dann auch „überfällig“ nach Mitternacht). Jeder Lauf rechnet jeden Kunden mit Portal an und nicht im Archiv neu (wenige) und leert das Schaufenster der übrigen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .auftragsstatus import LAEUFT, PAUSIERT
from .berlin_time import utc_jetzt
from .models import (
    Customer, Invoice, Order, PlanningSlot, PortalFreigabe, PortalRechnung, PortalSchaufenster, PortalTermin, Project, WorkPreparation,
)

NULL = Decimal("0.00")
TEXT_ZUSTAND = {
    "offen": "offen", "teilweise_bezahlt": "teilweise bezahlt", "bezahlt": "bezahlt", "guthaben": "Guthaben", "enthalten": "in Schlussrechnung enthalten",
    "storniert": "storniert", "storno": "Storno", "ohne": "ohne Zahlung",
}


def _d(wert) -> Decimal:
    return Decimal(str(wert)) if wert is not None else NULL


def zustand(rechnung: Invoice, zeile: dict, nummern: dict[int, str]) -> tuple[str, Decimal, bool, str | None]:
    """(Zustand, offener Betrag bzw. Guthaben, überfällig, Bezug) aus der Zeile von invoice_overview_rows(). nummern: Rechnungsnummer je ID (für Storno)."""
    if rechnung.status == "storniert":
        return "storniert", NULL, False, None
    if rechnung.invoice_type == "storno":
        return "storno", NULL, False, nummern.get(rechnung.storno_of_invoice_id)
    ov = zeile.get("overview")
    if ov is None:
        return "ohne", NULL, False, None
    if ov["state"] == "enthalten":
        return "enthalten", NULL, False, (ov.get("settled_in") or {}).get("invoice_number")
    if ov["state"] == "guthaben":
        return "guthaben", _d(ov.get("credit")), False, None
    offen = max(_d(ov.get("open")) - _d(ov.get("retained")), NULL)  # nur, was das ERP mahnen würde (P2-7): ohne den offenen Einbehalt
    if offen <= 0:
        return "bezahlt", NULL, False, None
    zahlung = zeile.get("payment") or {}
    teil = _d(zahlung.get("paid")) > 0 or _d(zahlung.get("skonto")) > 0
    return ("teilweise_bezahlt" if teil else "offen"), offen, bool(zeile.get("is_overdue")), None


def sichtbare_rechnungen(db: Session, kunde: Customer) -> list[Invoice]:
    """Festgeschriebene Rechnungen des Kunden mit einer Freigabe für ihn, nicht zurückgenommen, deren Kette heute zu ihm führt."""
    from .portal_freigaben import kette  # lokal: app/portal_freigaben.py zieht viel nach

    ids = select(PortalFreigabe.quelle_id).where(PortalFreigabe.customer_id == kunde.id, PortalFreigabe.quelle == "invoices",
                                                 PortalFreigabe.zurueckgenommen_am.is_(None))
    liste = db.scalars(select(Invoice).where(Invoice.id.in_(ids), Invoice.customer_id == kunde.id, Invoice.status != "entwurf")
                       .order_by(Invoice.invoice_date, Invoice.id)).all()
    aus = []
    for r in liste:
        k = kette(db, "invoices", r.id)
        if k.grund is None and k.kunde == kunde.id:
            aus.append(r)
    return aus


def rechnungen(db: Session, kunde: Customer) -> list[dict]:
    from .invoices import compute_invoice_totals, invoice_overview_rows, rechnungsart_text  # lokal: app/invoices.py hängt an vielen Modulen

    liste = sichtbare_rechnungen(db, kunde)
    nummern = {r.id: r.invoice_number for r in liste}
    fehlend = {r.storno_of_invoice_id for r in liste if r.storno_of_invoice_id and r.storno_of_invoice_id not in nummern}
    if fehlend:
        nummern.update(dict(db.execute(select(Invoice.id, Invoice.invoice_number).where(Invoice.id.in_(fehlend)).order_by(Invoice.id)).all()))
    aus = []
    for r, zeile in zip(liste, invoice_overview_rows(db, liste)):
        z, offen, ueber, bezug = zustand(r, zeile, nummern)
        aus.append({"invoice_id": r.id, "order_id": r.order_id, "nummer": r.invoice_number or "", "art_text": rechnungsart_text(r)[:120], "datum": r.invoice_date,
                    "faellig": r.due_date, "brutto": _d(compute_invoice_totals(r)["gross_total"]), "zustand": z, "offen": offen, "ueberfaellig": ueber,
                    "bezug_nummer": bezug})
    return aus


def termine(db: Session, kunde: Customer) -> list[dict]:
    from .planning import _folgen_der_tage, _tage_der_zeile  # lokal: app/planning.py zieht viel nach

    slots = db.scalars(select(PlanningSlot).join(WorkPreparation, WorkPreparation.id == PlanningSlot.preparation_id)
                       .join(Order, Order.id == WorkPreparation.order_id).join(Project, Project.id == Order.project_id)
                       .where(Order.customer_id == kunde.id, Order.status.in_((LAEUFT, PAUSIERT)), Project.is_template.is_(False),
                              Project.archived.is_(False), Project.archiviert_am.is_(None), PlanningSlot.status == "fest",
                              PlanningSlot.art == "baustelle")
                       .order_by(PlanningSlot.start_date, PlanningSlot.id)).all()
    je_auftrag: dict[int, set[date]] = {}
    for s in slots:
        tage: set[date] = set()
        for zeile in s.besetzung:
            tage |= _tage_der_zeile(s, zeile)
        if tage:
            je_auftrag.setdefault(s.preparation.order_id, set()).update(tage)
    return [{"order_id": order_id, "von": von, "bis": bis} for order_id in sorted(je_auftrag) for von, bis in _folgen_der_tage(je_auftrag[order_id])]


def abgleichen(db: Session, kunde: Customer, jetzt_: datetime | None = None) -> None:
    """Das Schaufenster eines Kunden neu (ein Commit): alte Zeilen weg, neue an, Stand gesetzt."""
    jetzt_ = jetzt_ or utc_jetzt()
    neu_r, neu_t = rechnungen(db, kunde), termine(db, kunde)
    db.execute(delete(PortalRechnung).where(PortalRechnung.customer_id == kunde.id))
    db.execute(delete(PortalTermin).where(PortalTermin.customer_id == kunde.id))
    db.add_all([PortalRechnung(customer_id=kunde.id, stand_am=jetzt_, **r) for r in neu_r])
    db.add_all([PortalTermin(customer_id=kunde.id, stand_am=jetzt_, **t) for t in neu_t])
    stand = db.get(PortalSchaufenster, kunde.id)
    if stand is None:
        db.add(PortalSchaufenster(customer_id=kunde.id, stand_am=jetzt_))
    else:
        stand.stand_am = jetzt_
    db.commit()


@dataclass
class Lauf:
    kunden: int = 0
    geleert: int = 0


def alle(db: Session) -> Lauf:
    """Für den Postboten: jeder Kunde mit Portal an und nicht im Archiv neu, das Schaufenster aller übrigen leer; mit ausgeschaltetem Modul alles leer."""
    from .modules import is_module_enabled

    lauf = Lauf()
    kunden = [] if not is_module_enabled(db, "kundenportal") else db.scalars(
        select(Customer).where(Customer.portal_aktiv.is_(True), Customer.archiviert_am.is_(None)).order_by(Customer.id)).all()
    for kunde in kunden:
        abgleichen(db, kunde)
        lauf.kunden += 1
    ids = [k.id for k in kunden]
    for tabelle in (PortalRechnung, PortalTermin, PortalSchaufenster):
        anweisung = delete(tabelle).where(tabelle.customer_id.not_in(ids)) if ids else delete(tabelle)
        lauf.geleert += db.execute(anweisung).rowcount or 0
    db.commit()
    return lauf
