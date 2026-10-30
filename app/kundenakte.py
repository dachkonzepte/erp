"""Kundenakte (seit 1.9.135, Stufe 5, R3, Punkt 1; Vorlagen bildgrundlage/entwurf_stufe5_kunde/kunde-*.html).

Was die Seite /customers/{id} beim Laden braucht und nicht selbst rechnen soll -- mit den Rechnungen der Akte je Projekt (app/akte.py), damit
dieselbe Zahl in Akte und Kundenakte gleich heißt und gleich lautet:

    projekte()     je Projekt des Kunden (ohne Mustervorgänge) der abgeleitete Status (app/akte.py::projekt_status_alle()), Aufträge, Bauleitung,
                   seit (erster Auftrag) und die Zahlen -- Auftragssumme, abgerechnet, noch nicht abgerechnet (netto, wie akte.leistung()),
                   unbezahlt (brutto, wie akte.zahlung()); für alle Aufträge des Kunden je Art eine Abfrage, kein Nachladen je Auftrag. Ohne
                   Auftrag das jüngste nicht abgelehnte Angebot; je Projekt alle Angebote mit Stand und Summen.
    geld()         über die Rechnungen, die der Kunde beim Festschreiben festhielt (Invoice.customer_id), und seine Zahlungen: unbezahlt (wie
                   Finanzen: nach der gültigen Endrechnung ihr Zahlbetrag), Zahl der unbezahlten Rechnungen und seit 1.9.137 ihre Zeilen
                   (invoice_overview_rows(), älteste Fälligkeit zuerst), überfällig (mahnfähig nach der Fälligkeit) seit der ältesten Fälligkeit, Guthaben (Rest und Überzahlung, app/payments.py::customer_balance()), je Jahr
                   abgerechnet (netto, Rechnungsdatum) und bezahlt (Eingänge minus Ausgänge, Eingangstag; ohne zurückgenommene).
    vorschlaege()  je Rest einer Zahlung „Auf <älteste unbezahlte Rechnung> zuordnen“ (höchstens ihr unbezahlter Betrag), ohne unbezahlte
                   Rechnung „Erstattung buchen“; je Guthaben aus einer Schlussrechnung „Erstattung buchen“ -- nur Vorschläge, gebucht wird über
                   die bestehenden Wege (POST /api/payments/{id}/allocations, POST /api/customers/{id}/refunds).
    zaehler()      die Zahlen an den Reitern.

Rollenlos (Architekturentscheidung „Rollenlose Business-Logik“): was Büro – Auftrag am Geld nicht darf, entscheiden die Seite (Knöpfe) und die
Router der Buchungen (require_geld).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .akte import ANGEBOT_STATUS, PROJEKTSTATUS_NAMEN, projekt_status_alle
from .berlin_time import berlin_today, to_berlin
from .models import (
    Customer, CustomerDocument, CustomerExtraInfo, Inquiry, Invoice, Order, Payment, Project, Property, Quote, QuoteItem, QuoteItemLayout,
)
from .rounding import round_money

NULL = Decimal("0")
GESCHLOSSENE_STATUS = ("abgeschlossen", "storniert")


def _d(x) -> Decimal:
    return Decimal(str(x)) if x is not None else NULL


def angebot_summen(db: Session, quotes: list[Quote]) -> dict[int, tuple[Decimal, Decimal]]:
    """(netto, brutto) je Angebot wie app/projects.py::quote_to_dict() -- Positionen „in Summe“ (Layout), je Position kaufmännisch gerundet --,
    für alle Angebote in zwei Abfragen statt je Angebot."""
    if not quotes:
        return {}
    ids = [q.id for q in quotes]
    items = db.execute(select(QuoteItem.id, QuoteItem.quote_id, QuoteItem.quantity, QuoteItem.unit_price).where(QuoteItem.quote_id.in_(ids))).all()
    ausserhalb = set(db.scalars(select(QuoteItemLayout.quote_item_id).where(
        QuoteItemLayout.quote_item_id.in_([i.id for i in items] or [-1]), QuoteItemLayout.include_in_total.is_(False))))
    netto: dict[int, Decimal] = {i: NULL for i in ids}
    for item_id, quote_id, menge, preis in items:
        if item_id not in ausserhalb:
            netto[quote_id] += round_money(_d(menge) * _d(preis))
    out = {}
    for q in quotes:
        n = round_money(netto[q.id])
        out[q.id] = (n, round_money(n + round_money(n * _d(q.vat_rate) / Decimal("100"))))
    return out


def _zahlen_je_auftrag(db: Session, orders: list[Order]) -> dict[int, dict]:
    """Je Auftrag Auftragssumme, abgerechnet, noch nicht abgerechnet (wie app/akte.py::leistung()) und unbezahlt (wie akte.zahlung()) -- die
    Rechnungen aller Aufträge in einer Abfrage, der Zahlstand über invoice_overview_rows() in einer weiteren."""
    from .invoices import VALID_STATUSES, closing_invoices, invoice_overview_rows, order_sum  # lokal: app/invoices.py hängt an vielen Modulen

    ids = [o.id for o in orders]
    rechnungen = list(db.scalars(select(Invoice).where(Invoice.order_id.in_(ids or [-1])).order_by(Invoice.id)))
    je_auftrag: dict[int, list[Invoice]] = {i: [] for i in ids}
    for inv in rechnungen:
        je_auftrag[inv.order_id].append(inv)
    gezaehlt = [i for i in rechnungen if i.status in VALID_STATUSES and i.invoice_type != "storno"]
    zeilen = {z["id"]: z for z in invoice_overview_rows(db, gezaehlt)}
    out = {}
    for o in orders:
        summe = order_sum(o)
        invs = je_auftrag[o.id]
        eigene = [zeilen[i.id] for i in invs if i.id in zeilen]
        abgerechnet = sum((_d(z["net_total"]) for z in eigene), NULL)
        vollstaendig = bool(closing_invoices([i for i in invs if i.status != "storniert"]))
        out[o.id] = {
            "auftragssumme": summe, "abgerechnet": abgerechnet,
            "noch_nicht_abgerechnet": NULL if vollstaendig else max(summe - abgerechnet, NULL),
            "unbezahlt": sum((max(_d((z["overview"] or {}).get("open")), NULL) for z in eigene), NULL),
        }
    return out


def projekte(db: Session, customer_id: int, heute: date | None = None) -> list[dict]:
    """Die Projekte des Kunden ohne Mustervorgänge: laufende zuerst (nicht abgeschlossen, nicht storniert, nicht archiviert), je Gruppe die
    jüngsten zuerst."""
    from .auftragsstatus import NAMEN as AUFTRAG_NAMEN, wert as auftrag_status

    heute = heute or berlin_today()
    projects = list(db.scalars(select(Project).options(selectinload(Project.property))
                               .where(Project.customer_id == customer_id, Project.is_template.is_(False)).order_by(Project.id.desc())))
    ids = [p.id for p in projects]
    status = projekt_status_alle(db, ids, heute)
    orders = list(db.scalars(select(Order).options(selectinload(Order.items), selectinload(Order.project_manager))
                             .where(Order.project_id.in_(ids or [-1])).order_by(Order.id)))
    zahlen = _zahlen_je_auftrag(db, orders)
    quotes = list(db.scalars(select(Quote).where(Quote.project_id.in_(ids or [-1])).order_by(Quote.id)))
    summen = angebot_summen(db, quotes)
    out = []
    for p in projects:
        eigene = [o for o in orders if o.project_id == p.id]
        angebote = [q for q in quotes if q.project_id == p.id]
        s = status[p.id]
        z = {k: sum((zahlen[o.id][k] for o in eigene), NULL) for k in ("auftragssumme", "abgerechnet", "noch_nicht_abgerechnet", "unbezahlt")}
        leitung = next((o.project_manager for o in eigene if o.project_manager is not None), None)
        angebot = None
        if not eigene and angebote:
            offen = [q for q in angebote if q.status != "abgelehnt"] or angebote
            q = max(offen, key=lambda x: x.id)
            angebot = {"id": q.id, "quote_number": q.quote_number, "status": q.status, "status_label": ANGEBOT_STATUS.get(q.status, q.status),
                       "net_total": summen[q.id][0],
                       "versendet_am": to_berlin(q.email_sent_at).date() if q.email_sent_at else None}
        prop = p.property
        out.append({
            "id": p.id, "project_number": p.project_number, "name": p.name, "archived": bool(p.archived),
            "property_id": p.property_id,  # seit 1.9.137: Objekte der Kundenakte nennen ihre Projekte
            "status": s, "status_label": PROJEKTSTATUS_NAMEN[s],
            "laufend": s not in GESCHLOSSENE_STATUS and not p.archived,
            "objekt": (", ".join(t for t in (prop.street, " ".join(x for x in (prop.postal_code, prop.city) if x)) if t) or prop.name)
                      if prop is not None else None,
            "auftraege": [{"id": o.id, "order_number": o.order_number, "status": auftrag_status(o.status),
                           "status_label": AUFTRAG_NAMEN.get(auftrag_status(o.status), o.status), **zahlen[o.id]} for o in eigene],
            "bauleitung": f"{leitung.first_name} {leitung.last_name}".strip() if leitung is not None else None,
            "seit": min((o.order_date for o in eigene if o.order_date), default=None),
            "zahlen": z, "angebot": angebot,
            "angebote": [{"id": q.id, "quote_number": q.quote_number, "title": q.title, "status": q.status,
                          "status_label": ANGEBOT_STATUS.get(q.status, q.status), "net_total": summen[q.id][0], "gross_total": summen[q.id][1]}
                         for q in angebote],
        })
    out.sort(key=lambda x: not x["laufend"])  # stabil: je Gruppe bleibt „jüngste zuerst“
    return out


def _zahlungen(db: Session, customer_id: int) -> list[Payment]:
    """Zahlungen und Zahlungsausgänge des Kunden ohne zurückgenommene und ohne die Gegenbuchungen selbst."""
    zurueck = select(Payment.reverses_payment_id).where(Payment.reverses_payment_id.is_not(None))
    return list(db.scalars(select(Payment).where(Payment.customer_id == customer_id, Payment.reverses_payment_id.is_(None),
                                                 Payment.id.not_in(zurueck)).order_by(Payment.received_on, Payment.id)))


def guthaben(db: Session, customer_id: int) -> dict:
    """Guthaben des Kunden wie app/payments.py::customer_payments()["balance"] -- ohne die Zeilen jeder Zahlung aufzubauen."""
    from .payments import customer_balance, customer_credits, payment_rest  # lokal: Zirkel-Import über app/invoices.py

    zeilen = [{"id": p.id, "received_on": p.received_on, "rest": payment_rest(db, p)}
              for p in db.scalars(select(Payment).where(Payment.customer_id == customer_id, Payment.reverses_payment_id.is_(None)))]
    return customer_balance(zeilen, customer_credits(db, customer_id))


def geld(db: Session, customer_id: int, heute: date | None = None) -> dict:
    from .invoices import VALID_STATUSES, invoice_overview_rows  # lokal wie oben

    heute = heute or berlin_today()
    rechnungen = list(db.scalars(select(Invoice).where(Invoice.customer_id == customer_id, Invoice.status.in_(VALID_STATUSES),
                                                       Invoice.invoice_type != "storno").order_by(Invoice.id)))
    unbezahlt = ueberfaellig = NULL
    unbezahlte: list[dict] = []
    seit = None
    jahre: dict[int, dict] = {}

    def jahr(j: int) -> dict:
        return jahre.setdefault(j, {"jahr": j, "abgerechnet": NULL, "rechnungen": 0, "bezahlt": NULL, "zahlungen": 0, "erstattet": NULL})

    for z in invoice_overview_rows(db, rechnungen):
        offen = _d((z["overview"] or {}).get("open"))
        if offen > 0:
            unbezahlt += offen
            unbezahlte.append(z)
        if z["is_overdue"]:
            ueberfaellig += _d((z["dunning"] or {}).get("dunnable"))
            seit = z["due_date"] if seit is None or (z["due_date"] and z["due_date"] < seit) else seit
        if z["invoice_date"] is not None:
            w = jahr(z["invoice_date"].year)
            w["abgerechnet"] += _d(z["net_total"])
            w["rechnungen"] += 1
    for p in _zahlungen(db, customer_id):
        w = jahr(p.received_on.year)
        w["bezahlt"] += _d(p.amount)
        if _d(p.amount) > 0:
            w["zahlungen"] += 1
        else:
            w["erstattet"] -= _d(p.amount)
    jahr(heute.year)
    jahr(heute.year - 1)
    return {
        "unbezahlt": unbezahlt, "unbezahlte_rechnungen": len(unbezahlte), "ueberfaellig": ueberfaellig, "ueberfaellig_seit": seit,
        # seit 1.9.137: die Zeilen für „Unbezahlte Rechnungen“ (Reiter Zahlungen), wie die Rechnungsliste der Akte
        "unbezahlte": sorted(unbezahlte, key=lambda z: (z["due_date"] is None, z["due_date"] or heute, z["id"])),
        "guthaben": guthaben(db, customer_id), "jahr": heute.year,
        "je_jahr": sorted(jahre.values(), key=lambda w: -w["jahr"]),
    }


def vorschlaege(db: Session, customer_id: int, balance: dict) -> list[dict]:
    """Was mit dem Guthaben geschehen kann -- je Rest einer Zahlung die älteste unbezahlte Rechnung des Kunden (Rechnungsdatum, dann Nummer
    der Vergabe; höchstens ihr unbezahlter Betrag), ohne unbezahlte Rechnung die Erstattung; je Überzahlung einer Schlussrechnung die Erstattung."""
    from .payments import open_invoices_of_customer  # lokal wie oben

    unbezahlt = [r for r in open_invoices_of_customer(db, customer_id) if _d(r["payment"]["open"]) > 0]
    out = []
    for line in balance["lines"]:
        betrag = _d(line["amount"])
        if line["kind"] == "rest" and unbezahlt:
            r = unbezahlt[0]
            out.append({"art": "zuordnen", "payment_id": line["payment_id"], "eingang": line["date"], "rest": betrag,
                        "invoice_id": r["invoice_id"], "invoice_number": r["invoice_number"],
                        "betrag": min(betrag, _d(r["payment"]["open"]))})
        elif line["kind"] == "rest":
            out.append({"art": "erstatten", "payment_id": line["payment_id"], "eingang": line["date"], "rest": betrag,
                        "invoice_id": None, "invoice_number": None, "betrag": betrag})
        else:
            out.append({"art": "erstatten", "payment_id": None, "eingang": line["date"], "rest": betrag,
                        "invoice_id": line["invoice_id"], "invoice_number": line["invoice_number"], "betrag": betrag})
    return out


def zaehler(db: Session, customer_id: int) -> dict:
    def anzahl(spalte, *bedingungen) -> int:
        return db.scalar(select(func.count(spalte)).where(*bedingungen)) or 0

    return {
        "projekte": anzahl(Project.id, Project.customer_id == customer_id, Project.is_template.is_(False)),
        "objekte": anzahl(Property.id, Property.customer_id == customer_id),
        "anfragen": anzahl(Inquiry.id, Inquiry.customer_id == customer_id),
        "dokumente": anzahl(CustomerDocument.id, CustomerDocument.customer_id == customer_id),
        "kontakte": anzahl(CustomerExtraInfo.id, CustomerExtraInfo.customer_id == customer_id),
    }


def kunde_kontext(db: Session, customer: Customer, heute: date | None = None) -> dict:
    """Was die Kundenakte beim Laden braucht (GET /api/customers/{id}/akte)."""
    heute = heute or berlin_today()
    g = geld(db, customer.id, heute)
    return {
        "customer_id": customer.id,
        "zaehler": zaehler(db, customer.id),
        "projekte": projekte(db, customer.id, heute),
        "geld": g,
        "vorschlaege": vorschlaege(db, customer.id, g["guthaben"]),
    }
