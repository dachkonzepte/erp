"""Phase je Auftrag und abgeleiteter Projektstatus (seit 1.9.125, Stufe 5, R2, Punkt 1; Vorlage bildgrundlage/entwurf_stufe5/akte-zuordnung.html),
seit 1.9.126 die Zahlen der Akte je Auftrag (Leistung, Zahlung, Stunden, je Position; unten bei zahlen()), seit 1.9.128 Kopf und Übersicht der
Akte (akte_kontext(): Auftragswahl, Phasen, was ansteht, Termine, Ausführung, Befunde, Zähler; hauptaktion() je Phase und Rolle).

Die Phase steht in keinem Feld -- sie ergibt sich aus den Daten, eine Funktion für Akte, Listen und Dashboard. Sie zeigt, wo der Auftrag steht, und
sperrt nichts (gesperrt wird über den Status, app/auftragsstatus.py).

    Angebot          ein Angebot des Auftrags ist angelegt; „angenommen“ mit dem Tag der Beauftragung
    Auftrag          der Auftrag ist angelegt (Datum, Vertragsgrundlage, Vertrag)
    Ausführung       erste Zeitbuchung, erster Einsatz (begonnen, nicht nur geplant) oder erster Bericht
    Abnahme          eine gültige Abnahme (nicht verworfen, abgenommen)
    Schlussrechnung  gültige Schlussrechnung oder abschließende Rechnung aus Aufwand

Die Phase eines Auftrags ist die letzte erreichte. Vor dem ersten Auftrag zeigt der Kopf die Phase des Angebots.

Projektstatus (kein Feld mehr von Hand, Project.status wird seit 1.9.125 nicht mehr gelesen): ohne Angebot „Anfrage“, mit Angebot und ohne Auftrag
„Angebot“, sonst die früheste Phase der Aufträge, die laufen oder pausiert sind; sind alle Aufträge abgeschlossen oder storniert, „Abgeschlossen“
(mindestens einer abgeschlossen) bzw. „Storniert“. Archivieren bleibt davon unberührt.

Für Listen gesammelt (projekt_status_alle(), signale()): je Art eine Abfrage für alle Aufträge, kein Nachladen je Projekt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .auftragsstatus import ABGESCHLOSSEN, GESCHLOSSEN, wert as status_wert
from .berlin_time import berlin_today
from .contract_basis import contract_basis_label
from .models import (
    Checklist, Invoice, Order, OrderAcceptance, OrderContract, PlanningSlot, Project, Quote, ServiceReport, TimeEntry, WorkPreparation,
)
from .rounding import round_half_up, round_hours, round_money

PHASEN = ("angebot", "auftrag", "ausfuehrung", "abnahme", "schlussrechnung")
PHASE_NAMEN = {"angebot": "Angebot", "auftrag": "Auftrag", "ausfuehrung": "Ausführung", "abnahme": "Abnahme",
               "schlussrechnung": "Schlussrechnung"}
PROJEKTSTATUS = ("anfrage", "angebot", "auftrag", "ausfuehrung", "abnahme", "schlussrechnung", "abgeschlossen", "storniert")
PROJEKTSTATUS_NAMEN = {"anfrage": "Anfrage", **PHASE_NAMEN, "abgeschlossen": "Abgeschlossen", "storniert": "Storniert"}
ANGEBOT_STATUS = {"entwurf": "Entwurf", "versendet": "versendet", "in_pruefung": "in Prüfung", "beauftragt": "angenommen",
                  "abgelehnt": "abgelehnt"}


def tag(d: date | None, heute: date | None = None) -> str:
    """„12.08.“ im laufenden Jahr, sonst „12.08.2025“."""
    if d is None:
        return ""
    return d.strftime("%d.%m.") if d.year == (heute or berlin_today()).year else d.strftime("%d.%m.%Y")


def stunden_text(h: Decimal | None) -> str:
    """„10,75 h“ -- seit 1.9.132 (R2 Nachrunde, Punkt 3) mit zwei Stellen wie „Zeiten“ (bis 1.9.131 eine, „10,8 h“, wie die Vorlage)."""
    wert = round_hours(Decimal(h or 0))
    return f"{wert:.2f}".replace(".", ",") + " h"


@dataclass
class Signale:
    """Was zu einem Auftrag in den Daten liegt -- gesammelt für viele Aufträge (signale())."""
    erste_buchung: date | None = None
    stunden: Decimal = Decimal("0")
    erster_einsatz: date | None = None  # begonnen (Beginn bis heute)
    naechster_einsatz: date | None = None  # geplant (Beginn nach heute)
    erster_bericht: date | None = None
    abgenommen: date | None = None  # früheste gültige, abgenommene Abnahme
    verweigert: date | None = None  # jüngste gültige verweigerte, solange keine abgenommen ist
    schluss: tuple[str | None, date | None] | None = None  # (Nummer, Datum) der abschließenden Rechnung
    vertrag: str | None = None  # Status des Vertrags
    rechnungen: list = field(default_factory=list)


def signale(db: Session, order_ids, heute: date | None = None) -> dict[int, Signale]:
    """Je Auftrag die Signale der Phasen -- je Art eine Abfrage über alle order_ids."""
    from .invoices import closing_invoices  # lokal: app/invoices.py hängt an vielen Modulen

    ids = sorted(set(order_ids))
    heute = heute or berlin_today()
    out = {i: Signale() for i in ids}
    if not ids:
        return out
    for oid, erste, summe in db.execute(
            select(TimeEntry.order_id, func.min(TimeEntry.work_date),
                   func.coalesce(func.sum(case((TimeEntry.status == "booked", TimeEntry.hours), else_=0)), 0))
            .where(TimeEntry.order_id.in_(ids)).group_by(TimeEntry.order_id)):
        out[oid].erste_buchung, out[oid].stunden = erste, round_hours(Decimal(summe or 0))
    for oid, beginn in db.execute(
            select(WorkPreparation.order_id, PlanningSlot.start_date).join(PlanningSlot, PlanningSlot.preparation_id == WorkPreparation.id)
            .where(WorkPreparation.order_id.in_(ids))):
        s = out[oid]
        if beginn <= heute:
            s.erster_einsatz = min(filter(None, (s.erster_einsatz, beginn)))
        else:
            s.naechster_einsatz = min(filter(None, (s.naechster_einsatz, beginn)))
    for oid, erster in db.execute(select(ServiceReport.order_id, func.min(ServiceReport.performed_at))
                                  .where(ServiceReport.order_id.in_(ids)).group_by(ServiceReport.order_id)):
        out[oid].erster_bericht = erster
    for oid, am, ergebnis in db.execute(select(OrderAcceptance.order_id, OrderAcceptance.accepted_on, OrderAcceptance.result)
                                        .where(OrderAcceptance.order_id.in_(ids), OrderAcceptance.discarded_at.is_(None))):
        s = out[oid]
        if ergebnis == "abgenommen":
            s.abgenommen = min(filter(None, (s.abgenommen, am)))
        else:
            s.verweigert = max(filter(None, (s.verweigert, am)))
    for oid, vstatus in db.execute(select(OrderContract.order_id, OrderContract.status).where(OrderContract.order_id.in_(ids))):
        out[oid].vertrag = vstatus
    rechnungen: dict[int, list[Invoice]] = {}
    for inv in db.scalars(select(Invoice).where(Invoice.order_id.in_(ids), Invoice.invoice_type.in_(("schluss", "aufwand")))):
        rechnungen.setdefault(inv.order_id, []).append(inv)
    for oid, invs in rechnungen.items():
        fertig = closing_invoices(invs)
        if fertig:
            erste = min(fertig, key=lambda i: (i.invoice_date or date.max, i.id))
            out[oid].schluss = (erste.invoice_number, erste.invoice_date)
    for s in out.values():
        if s.abgenommen is not None:
            s.verweigert = None
    return out


def _ausfuehrung_seit(s: Signale) -> date | None:
    kandidaten = [d for d in (s.erste_buchung, s.erster_einsatz, s.erster_bericht) if d is not None]
    return min(kandidaten) if kandidaten else None


def phasen(order: Order, s: Signale, heute: date | None = None) -> dict:
    """Die fünf Schritte eines Auftrags mit „erreicht“, „jetzt“ (die letzte erreichte Phase) und einem kurzen Text wie in der Vorlage."""
    heute = heute or berlin_today()
    seit = _ausfuehrung_seit(s)
    vertrag = {"festgeschrieben": "Vertrag festgeschrieben", "unterschrieben": "Vertrag unterschrieben"}.get(s.vertrag)
    auftrag_text = " · ".join(t for t in (tag(order.order_date, heute), contract_basis_label(order.contract_basis), vertrag) if t)
    if seit is not None:
        ausfuehrung = f"seit {tag(seit, heute)} · {stunden_text(s.stunden)} gebucht"
    elif s.naechster_einsatz is not None:
        ausfuehrung = f"geplant ab {tag(s.naechster_einsatz, heute)}"
    else:
        ausfuehrung = "noch nicht begonnen"
    if s.abgenommen is not None:
        abnahme = f"abgenommen {tag(s.abgenommen, heute)}"
    elif s.verweigert is not None:
        abnahme = f"verweigert {tag(s.verweigert, heute)}"
    else:
        abnahme = "noch nicht erfasst"
    if s.schluss is not None:
        schluss = " · ".join(t for t in (s.schluss[0], tag(s.schluss[1], heute)) if t)
    else:
        schluss = "nach der Abnahme"
    schritte = [
        {"key": "angebot", "erreicht": True, "text": f"{order.quote_number_snapshot} · angenommen {tag(order.order_date, heute)}"},
        {"key": "auftrag", "erreicht": True, "text": auftrag_text},
        {"key": "ausfuehrung", "erreicht": seit is not None, "text": ausfuehrung},
        {"key": "abnahme", "erreicht": s.abgenommen is not None, "text": abnahme},
        {"key": "schlussrechnung", "erreicht": s.schluss is not None, "text": schluss},
    ]
    aktuell = max(i for i, x in enumerate(schritte) if x["erreicht"])
    for i, x in enumerate(schritte):
        x["name"] = PHASE_NAMEN[x["key"]]
        x["jetzt"] = i == aktuell
    return {"phase": schritte[aktuell]["key"], "phase_label": schritte[aktuell]["name"], "schritte": schritte}


def phasen_ohne_auftrag(quotes: list[Quote]) -> dict:
    """Vor dem ersten Auftrag: die Phase des Angebots (das jüngste nicht abgelehnte, sonst das jüngste); ohne Angebot ist nichts erreicht."""
    angebot = None
    if quotes:
        offen = [q for q in quotes if q.status != "abgelehnt"] or list(quotes)
        angebot = max(offen, key=lambda q: q.id)
    text = f"{angebot.quote_number} · {ANGEBOT_STATUS.get(angebot.status, angebot.status)}" if angebot else "noch kein Angebot"
    schritte = [{"key": "angebot", "erreicht": angebot is not None, "text": text}]
    schritte += [{"key": k, "erreicht": False, "text": ""} for k in PHASEN[1:]]
    for x in schritte:
        x["name"] = PHASE_NAMEN[x["key"]]
        x["jetzt"] = x["key"] == "angebot" and angebot is not None
    return {"phase": "angebot" if angebot else None, "phase_label": "Angebot" if angebot else None, "schritte": schritte}


def projekt_status_aus(orders: list[Order], phasen_je_auftrag: dict[int, str], hat_angebot: bool) -> str:
    """Der abgeleitete Projektstatus aus den Aufträgen (mit Phase) und ob es ein Angebot gibt."""
    if not orders:
        return "angebot" if hat_angebot else "anfrage"
    aktive = [o for o in orders if status_wert(o.status) not in GESCHLOSSEN]
    if not aktive:
        return "abgeschlossen" if any(status_wert(o.status) == ABGESCHLOSSEN for o in orders) else "storniert"
    return min((phasen_je_auftrag[o.id] for o in aktive), key=PHASEN.index)


def projekt_status_alle(db: Session, project_ids, heute: date | None = None) -> dict[int, str]:
    """Der abgeleitete Status je Projekt -- für Listen: Aufträge, Angebote und Signale je eine Abfrage."""
    ids = sorted(set(project_ids))
    if not ids:
        return {}
    auftraege: dict[int, list[Order]] = {}
    for o in db.scalars(select(Order).where(Order.project_id.in_(ids))):
        auftraege.setdefault(o.project_id, []).append(o)
    mit_angebot = set(db.scalars(select(Quote.project_id).where(Quote.project_id.in_(ids)).distinct()))
    alle = [o for liste in auftraege.values() for o in liste]
    sig = signale(db, [o.id for o in alle], heute)
    je_auftrag = {o.id: phasen(o, sig[o.id], heute)["phase"] for o in alle}
    return {pid: projekt_status_aus(auftraege.get(pid, []), je_auftrag, pid in mit_angebot) for pid in ids}


def projekt_status(db: Session, project: Project) -> str:
    return projekt_status_alle(db, [project.id])[project.id]


# --- Zahlen der Akte (seit 1.9.126, Stufe 5, R2, Punkt 1; Befund F18, F19, F21) -------------------------------------------------------------
# Je Zahl eine Rechnung, die Akte, Arbeitsvorbereitung, Plantafel und die Auftragslisten gemeinsam benutzen (Vorlage akte-uebersicht.html,
# akte-leistungen.html):
#   Leistung netto   Auftragssumme (Positionen „in Summe“, Nachträge eingeschlossen, app/invoices.py::order_sum()), abgerechnet (festgeschriebene
#                    Rechnungen ohne Stornos und stornierte, app/invoices.py::compute_order_billing_progress()), noch nicht abgerechnet; nach der
#                    abschließenden Rechnung ist nichts mehr „noch nicht abgerechnet“ -- weniger bzw. mehr als die Auftragssumme steht daneben
#   Zahlung brutto   in Rechnung gestellt (Brutto derselben Rechnungen), bezahlt (abzüglich Erstattungen, wie „Bezahlt (gesamt)“ in Finanzen),
#                    Skonto, unbezahlt (wie Finanzen und Dashboard: nach der gültigen Endrechnung ihr Zahlbetrag, app/final_dunning.py::overview()),
#                    davon Einbehalt, Guthaben, überfällig (der mahnfähige Betrag nach der Fälligkeit) mit dem Tag der ältesten Fälligkeit
#   Stunden          Soll aus der Kalkulation der Positionen „in Summe“ (Nachträge ohne Kalkulation tragen nichts), gebucht (alle Zeitarten, nur
#                    gebuchte -- ein laufender Timer trägt nichts), Fahrzeit, Baustelle & Werkstatt (die Zeitarten der Kalkulation) gegen das Soll
#   je Position      abgerechnet (kumulierte Ist-Menge der zuletzt festgeschriebenen Abschlagsrechnung nach Leistungsstand bzw. Schlussrechnung,
#                    wie app/invoices.py::get_previous_cumulative_ist(), Prozent der Menge) und Std. Ist/Soll (Baustelle & Werkstatt mit Bezug auf
#                    die Position gegen Kalkulation × Menge)

BAUSTELLE_WERKSTATT = ("site", "workshop")
FAHRZEIT = "travel"
NULL = Decimal("0")


def _d(x) -> Decimal:
    return Decimal(str(x)) if x is not None else NULL


def _prozent(teil: Decimal, ganz: Decimal) -> int | None:
    """Ganze Prozent, kaufmännisch gerundet; ohne Bezugsgröße keine Angabe."""
    return int(round_half_up(_d(teil) / _d(ganz) * 100, Decimal("1"))) if ganz else None


def soll_je_position(item) -> Decimal:
    """Planstunden einer Position: (Baustelle + Werkstatt) Minuten der Kalkulation / 60 × Menge; ohne Kalkulation 0 (ungerundet)."""
    calc = item.calculation_snapshot
    if calc is None:
        return NULL
    return (_d(calc.site_time_minutes) + _d(calc.workshop_time_minutes)) / Decimal("60") * _d(item.quantity)


def soll_stunden(order: Order) -> Decimal:
    """Soll aus der Kalkulation, nur Positionen „in Summe“ -- die eine Rechnung für Akte, Arbeitsvorbereitung und Plantafel
    (app/work_preparation.py::planned_hours()). Bis 1.9.125 zählte planned_hours() auch Positionen außerhalb der Summe (Befund F18)."""
    return round_hours(sum((soll_je_position(i) for i in order.items if i.include_in_total), NULL))


def leistung(db: Session, order: Order) -> dict:
    from .invoices import compute_order_billing_progress, invoice_summary_for_order, order_sum  # lokal wie in signale()

    summe = order_sum(order)
    nachtraege = order_sum_nachtraege(order)
    abgerechnet = compute_order_billing_progress(db, order.id)["invoiced_net"]
    vollstaendig = invoice_summary_for_order(db, order.id)[1]
    return {
        "auftragssumme": summe, "nachtraege": nachtraege, "abgerechnet": abgerechnet, "abgerechnet_prozent": _prozent(abgerechnet, summe),
        "vollstaendig": vollstaendig,
        "noch_nicht_abgerechnet": NULL if vollstaendig else max(summe - abgerechnet, NULL),
        "unter_auftragssumme": max(summe - abgerechnet, NULL) if vollstaendig else NULL,
        "ueber_auftragssumme": max(abgerechnet - summe, NULL),
    }


def order_sum_nachtraege(order: Order) -> Decimal:
    """Der Anteil der Nachträge an der Auftragssumme (seit 1.8.83 Auftragspositionen mit is_addendum)."""
    return sum((round_money(_d(i.quantity) * _d(i.unit_price)) for i in order.items if i.include_in_total and i.is_addendum), NULL)


def zahlung(db: Session, order: Order) -> dict:
    """Brutto über die festgeschriebenen Rechnungen des Auftrags (ohne Stornos und stornierte) -- je Rechnung dieselbe Zeile wie in Finanzen
    und den Rechnungslisten (app/invoices.py::invoice_overview_rows())."""
    from .invoices import VALID_STATUSES, invoice_overview_rows, list_invoices_for_order  # lokal wie in signale()

    gezaehlt = [i for i in list_invoices_for_order(db, order.id) if i.status in VALID_STATUSES and i.invoice_type != "storno"]
    w = {"rechnungen": len(gezaehlt), "in_rechnung": NULL, "bezahlt": NULL, "erstattet": NULL, "skonto": NULL, "unbezahlt": NULL,
         "einbehalt": NULL, "guthaben": NULL, "ueberfaellig": NULL, "ueberfaellig_seit": None}
    for zeile in invoice_overview_rows(db, gezaehlt):
        w["in_rechnung"] += _d(zeile["gross_total"])
        stand = zeile["payment"] or {}
        w["bezahlt"] += _d(stand.get("paid"))
        w["skonto"] += _d(stand.get("skonto"))
        ueber = zeile["overview"] or {}
        w["erstattet"] += _d(ueber.get("refunded"))
        w["unbezahlt"] += max(_d(ueber.get("open")), NULL)
        w["einbehalt"] += _d(ueber.get("retained"))
        w["guthaben"] += _d(ueber.get("credit"))
        if zeile["is_overdue"]:
            w["ueberfaellig"] += _d((zeile["dunning"] or {}).get("dunnable"))
            if w["ueberfaellig_seit"] is None or zeile["due_date"] < w["ueberfaellig_seit"]:
                w["ueberfaellig_seit"] = zeile["due_date"]
    w["bezahlt"] -= w["erstattet"]
    w["bezahlt_prozent"] = _prozent(w["bezahlt"], w["in_rechnung"]) if w["in_rechnung"] > 0 else None
    return w


def stunden(db: Session, order: Order) -> dict:
    """Gebuchte Stunden je Zeitart und je Mitarbeiter, dazu das Soll; ohne_position = Baustelle & Werkstatt ohne Bezug auf eine Position."""
    from .models import Employee

    gebucht = fahrzeit = bw = ohne_position = NULL
    je: dict[int, dict] = {}
    je_zeitart: dict[str, Decimal] = {}
    for emp_id, art, tag_, position, h in db.execute(
            select(TimeEntry.employee_id, TimeEntry.entry_type, TimeEntry.work_date, TimeEntry.order_item_id, TimeEntry.hours)
            .where(TimeEntry.order_id == order.id, TimeEntry.status == "booked")):
        h = _d(h)
        gebucht += h
        je_zeitart[art] = je_zeitart.get(art, NULL) + h
        zeile = je.setdefault(emp_id, {"tage": set(), "fahrzeit": NULL, "stunden": NULL})
        zeile["tage"].add(tag_)
        zeile["stunden"] += h
        if art == FAHRZEIT:
            fahrzeit += h
            zeile["fahrzeit"] += h
        if art in BAUSTELLE_WERKSTATT:
            bw += h
            if position is None:
                ohne_position += h
    namen = ({e.id: f"{e.first_name} {e.last_name}".strip() for e in db.scalars(select(Employee).where(Employee.id.in_(list(je))))}
             if je else {})
    soll = soll_stunden(order)
    mitarbeiter = [{"employee_id": k, "name": namen.get(k, f"Nr. {k}"), "tage": len(v["tage"]), "fahrzeit": round_hours(v["fahrzeit"]),
                    "stunden": round_hours(v["stunden"])} for k, v in je.items()]
    mitarbeiter.sort(key=lambda x: (-x["stunden"], x["name"]))
    return {"soll": soll, "gebucht": round_hours(gebucht), "fahrzeit": round_hours(fahrzeit), "baustelle_werkstatt": round_hours(bw),
            "ohne_position": round_hours(ohne_position), "abweichung": round_hours(bw - soll), "prozent_vom_soll": _prozent(bw, soll),
            "je_zeitart": {k: round_hours(v) for k, v in je_zeitart.items()}, "mitarbeiter": mitarbeiter}


def ist_je_position(db: Session, order_id: int) -> dict[int, Decimal]:
    """Std. Ist je Position: gebuchte Baustelle & Werkstatt mit Bezug auf die Position (Akte und Arbeitsvorbereitung)."""
    return {int(k): round_hours(_d(v)) for k, v in db.execute(
        select(TimeEntry.order_item_id, func.coalesce(func.sum(TimeEntry.hours), 0))
        .where(TimeEntry.order_id == order_id, TimeEntry.status == "booked", TimeEntry.order_item_id.is_not(None),
               TimeEntry.entry_type.in_(BAUSTELLE_WERKSTATT))
        .group_by(TimeEntry.order_item_id))}


def positionen(db: Session, order: Order) -> dict:
    """Stand je Position: abgerechnete Menge (letzter festgeschriebener Stand) mit Prozent, Std. Ist/Soll; dazu die Rechnung des Stands."""
    from .invoices import VALID_STATUSES  # lokal wie in signale()
    from .models import InvoiceItem

    stand: dict[int, Decimal] = {}
    quelle = None
    for item_id, ist, inv_id, nummer, am, art, bezeichnung in db.execute(
            select(InvoiceItem.source_order_item_id, InvoiceItem.ist_quantity, Invoice.id, Invoice.invoice_number, Invoice.invoice_date,
                   Invoice.invoice_type, Invoice.progress_description)
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .where(Invoice.order_id == order.id, Invoice.status.in_(VALID_STATUSES),
                   Invoice.invoice_type.in_(("abschlag_leistungsstand", "schluss")), InvoiceItem.source_order_item_id.is_not(None))
            .order_by(Invoice.finalized_at.is_(None), Invoice.finalized_at.desc(), Invoice.invoice_date.desc(), Invoice.id.desc())):
        if quelle is None:
            quelle = {"invoice_id": inv_id, "invoice_number": nummer, "invoice_date": am, "invoice_type": art, "bezeichnung": bezeichnung}
        stand.setdefault(item_id, _d(ist))
    ist_h = ist_je_position(db, order.id)
    zeilen = []
    for item in sorted(order.items, key=lambda x: (x.sort_order, x.id)):
        menge = stand.get(item.id, NULL)
        zeilen.append({"item_id": item.id, "abgerechnet_menge": menge, "abgerechnet_prozent": _prozent(menge, _d(item.quantity)),
                       "stunden_ist": ist_h.get(item.id, round_hours(NULL)),
                       "stunden_soll": round_hours(soll_je_position(item)) if item.calculation_snapshot is not None else None})
    return {"zeilen": zeilen, "quelle": quelle}


def zahlen(db: Session, order: Order) -> dict:
    """Alle Zahlen der Akte zu einem Auftrag (GET /api/orders/{id}/zahlen)."""
    return {"order_id": order.id, "leistung": leistung(db, order), "zahlung": zahlung(db, order), "stunden": stunden(db, order),
            "positionen": positionen(db, order)}


# --- Kopf und Übersicht der Akte (seit 1.9.128, Stufe 5, R2, Punkt 2; Vorlage akte-uebersicht.html) --------------------------------------
# Was die Seite /projects/{id} beim Laden braucht und nicht selbst rechnen soll: die Aufträge zur Auswahl, der gewählte, seine Phasen, was
# ansteht, Termine, der Stand der Ausführung und die Zahlen an den Reitern. Die Hauptaktion je Phase und Rolle entscheidet der Router (geld).

def auftrag_waehlen(orders: list[Order], gewuenscht: int | None) -> Order | None:
    """Der gewählte Auftrag: der gewünschte, sonst der älteste laufende oder pausierte, sonst der jüngste."""
    if gewuenscht is not None:
        return next((o for o in orders if o.id == gewuenscht), None)
    offen = [o for o in orders if status_wert(o.status) not in GESCHLOSSEN]
    if offen:
        return min(offen, key=lambda o: o.id)
    return max(orders, key=lambda o: o.id) if orders else None


def _rechnungsname(inv: Invoice) -> str:
    from .invoices import rechnungsart_text  # lokal wie in signale()
    return rechnungsart_text(inv)


def ansteht(db: Session, order: Order, heute: date | None = None) -> list[dict]:
    """Was zu diesem Auftrag wartet: überfällige Rechnungen, Befunde zur Prüfung, Checklisten im Entwurf. Je Eintrag Text, Ziel und ob der
    Knopf zum Geld gehört (die Seite zeigt ihn nur nach darf_geld())."""
    from .invoices import VALID_STATUSES, _eur, invoice_overview_rows, list_invoices_for_order
    from .models import Finding
    from .modules import is_module_enabled

    heute = heute or berlin_today()
    out = []
    rechnungen = [i for i in list_invoices_for_order(db, order.id) if i.status in VALID_STATUSES and i.invoice_type != "storno"]
    je_id = {i.id: i for i in rechnungen}
    for z in invoice_overview_rows(db, rechnungen):
        if z["is_overdue"]:
            inv = je_id[z["id"]]
            offen = (z["dunning"] or {}).get("dunnable")
            out.append({"art": "ueberfaellig", "titel": f"{_rechnungsname(inv)} überfällig",
                        "unter": " · ".join(t for t in (inv.invoice_number, _eur(offen) if offen is not None else None,
                                                        f"fällig war {tag(inv.due_date, heute)}" if inv.due_date else None) if t),
                        "href": "/mahnwesen", "knopf": "Mahnen", "geld": True})
    for befund, bericht in db.execute(select(Finding, ServiceReport).join(ServiceReport, Finding.service_report_id == ServiceReport.id)
                                      .where(ServiceReport.order_id == order.id, Finding.status == "offen")
                                      .order_by(ServiceReport.performed_at, Finding.id)):
        text = (befund.description or "").strip().splitlines()[0][:80] if (befund.description or "").strip() else "ohne Beschreibung"
        out.append({"art": "befund", "titel": f"Befund prüfen: {text}",
                    "unter": " · ".join(t for t in (f"Einsatzbericht {tag(bericht.performed_at, heute)}", befund.created_by_name) if t),
                    "href": f"/service-reports/{bericht.id}", "knopf": "Ansehen", "geld": False})
    if is_module_enabled(db, "checklisten"):
        from .berlin_time import to_berlin
        for c in db.scalars(select(Checklist).where(Checklist.order_id == order.id, Checklist.status == "entwurf").order_by(Checklist.id)):
            seit = to_berlin(c.created_at).date() if c.created_at else None
            out.append({"art": "checkliste", "titel": f"Checkliste „{c.template_label_snapshot}“",
                        "unter": f"im Entwurf seit {tag(seit, heute)}" if seit else "im Entwurf", "href": f"/checklisten/{c.id}",
                        "knopf": "Öffnen", "geld": False})
    return out


def einsaetze(db: Session, order_id: int) -> list[dict]:
    """Die Einsätze der Plantafel zu einem Auftrag, nach Beginn."""
    from .models import WorkPreparationTeamAssignment

    rows = db.execute(select(PlanningSlot, WorkPreparationTeamAssignment).join(WorkPreparation, PlanningSlot.preparation_id == WorkPreparation.id)
                      .join(WorkPreparationTeamAssignment, PlanningSlot.team_assignment_id == WorkPreparationTeamAssignment.id)
                      .where(WorkPreparation.order_id == order_id).order_by(PlanningSlot.start_date, PlanningSlot.id)).all()
    return [{"id": s.id, "start_date": s.start_date, "end_date": s.end_date, "status": s.status, "team": a.team_name_snapshot,
             "personen": len(a.employees)} for s, a in rows]


def ausfuehrung(db: Session, order: Order) -> dict:
    """Stand der Ausführung: Arbeitsvorbereitung, Einsätze, Berichte, Checklisten, Stunden -- die Seiten dafür bleiben, die Akte führt hin."""
    from .models import Employee
    from .modules import is_module_enabled
    from .service_reports import REPORT_TYPE_LABELS

    av = db.scalar(select(WorkPreparation).where(WorkPreparation.order_id == order.id))
    berichte = db.scalars(select(ServiceReport).where(ServiceReport.order_id == order.id)
                          .order_by(ServiceReport.performed_at.desc(), ServiceReport.id.desc())).all()
    namen = {e.id: f"{e.first_name} {e.last_name}".strip() for e in db.scalars(select(Employee).where(
        Employee.id.in_([b.created_by_employee_id for b in berichte if b.created_by_employee_id] or [-1])))}
    checklisten = None
    if is_module_enabled(db, "checklisten"):
        checklisten = {s: n for s, n in db.execute(select(Checklist.status, func.count(Checklist.id)).where(Checklist.order_id == order.id)
                                                    .group_by(Checklist.status))}
    einsatz_zeilen = einsaetze(db, order.id)
    return {
        # seit 1.9.145 (F12): mit Einsätzen ist ihr Zeitraum der geplante -- wie app/work_preparation.py::einsatz_zeitraum()
        "arbeitsvorbereitung": ({"id": av.id, "status": av.status,
                                 "planned_start": min(e["start_date"] for e in einsatz_zeilen) if einsatz_zeilen else av.planned_start,
                                 "planned_end": max(e["end_date"] for e in einsatz_zeilen) if einsatz_zeilen else av.planned_end}
                                if av else None),
        "einsaetze": einsatz_zeilen,
        "berichte": [{"id": b.id, "performed_at": b.performed_at, "art": REPORT_TYPE_LABELS.get(b.report_type, b.report_type),
                      "status": b.status, "von": namen.get(b.created_by_employee_id)} for b in berichte],
        "checklisten": checklisten,
        "stunden": stunden(db, order),
    }


def hauptaktion(phase: str | None, *, hat_angebot: bool, verweigert: bool, geschlossen: bool, geld: bool, muster: bool = False) -> dict | None:
    """Der eine Knopf im Kopf je Phase und Rolle (geld = darf_geld(), entscheidet der Router):
       ohne Auftrag      ohne Angebot „+ Angebot“, sonst „Beauftragen“ (im Angebot)
       Auftrag           „Einsatz planen“
       Ausführung        mit Geld „Rechnung erstellen“, sonst „Einsatz planen“; nach einer verweigerten Abnahme „Abnahme erfassen“
       Abnahme           mit Geld „Schlussrechnung erstellen“, sonst „Abnahme & Mängel“
       Schlussrechnung   „Auftrag abschließen“, solange er nicht geschlossen ist
    Ein Mustervorgang hat keine (er wird nicht beauftragt, seit 1.9.117; „Kopieren“ steht im Menü).
    """
    if muster:
        return None
    if phase in (None, "angebot"):
        return {"art": "beauftragen", "text": "Beauftragen"} if hat_angebot else {"art": "angebot", "text": "Angebot"}
    if geschlossen:
        return None
    if phase == "auftrag":
        return {"art": "einsatz", "text": "Einsatz planen"}
    if phase == "ausfuehrung":
        if verweigert:
            return {"art": "abnahme", "text": "Abnahme erfassen"}
        return {"art": "rechnung", "text": "Rechnung erstellen"} if geld else {"art": "einsatz", "text": "Einsatz planen"}
    if phase == "abnahme":
        return {"art": "schlussrechnung", "text": "Schlussrechnung erstellen"} if geld else {"art": "maengel", "text": "Abnahme & Mängel"}
    return {"art": "abschliessen", "text": "Auftrag abschließen"}


def befunde(db: Session, order: Order) -> list[dict]:
    """Die Befunde aus den Einsatzberichten des Auftrags (Reiter „Abnahme & Mängel“), neueste zuerst."""
    from .findings import ACTION_LABELS, SEVERITY_LABELS, STATUS_LABELS
    from .models import Finding

    out = []
    for f, b in db.execute(select(Finding, ServiceReport).join(ServiceReport, Finding.service_report_id == ServiceReport.id)
                           .where(ServiceReport.order_id == order.id).order_by(ServiceReport.performed_at.desc(), Finding.id.desc())):
        text = (f.description or "").strip().splitlines()[0][:120] if (f.description or "").strip() else "ohne Beschreibung"
        out.append({"id": f.id, "service_report_id": b.id, "titel": text,
                    "unter": " · ".join(t for t in (SEVERITY_LABELS.get(f.severity, f.severity), "Maßnahme: " + ACTION_LABELS.get(f.action, f.action),
                                                    STATUS_LABELS.get(f.status, f.status), f"Einsatzbericht {tag(b.performed_at)}") if t)})
    return out


def termine(db: Session, project: Project, order: Order | None, viewer_user_id: int | None, heute: date | None = None) -> list[dict]:
    """Was ab heute ansteht: Termine des Projekts (Kalender, privat fremder als „Belegt“) und Einsätze des gewählten Auftrags, nach Tag."""
    from .calendar_events import event_to_dict, is_redacted_for_viewer, redact_for_busy
    from .models import CalendarEvent
    from .modules import is_module_enabled

    heute = heute or berlin_today()
    out = []
    if is_module_enabled(db, "kalender"):
        for ev in db.scalars(select(CalendarEvent).where(CalendarEvent.project_id == project.id, CalendarEvent.end_at >= datetime.combine(heute, time.min))
                             .order_by(CalendarEvent.start_at).limit(8)):
            d = event_to_dict(db, ev)
            if is_redacted_for_viewer(d, viewer_user_id):
                d = redact_for_busy(d)
            zeit = "ganztägig" if d["all_day"] else d["start_at"].strftime("%H:%M")
            out.append({"tag": d["start_at"].date(), "titel": d["title"], "unter": " · ".join(t for t in (zeit, d.get("location"), "Termin") if t),
                        "quelle": "termin"})
    if order is not None:
        for s in einsaetze(db, order.id):
            if s["end_date"] >= heute:
                out.append({"tag": s["start_date"], "titel": f"Einsatz {s['team']} · {s['personen']} {'Person' if s['personen'] == 1 else 'Personen'}",
                            "unter": f"{tag(s['start_date'], heute)}–{tag(s['end_date'], heute)} · Plantafel", "quelle": "einsatz"})
    out.sort(key=lambda t: t["tag"])
    return out[:8]


def akte_kontext(db: Session, project: Project, gewuenscht: int | None, viewer_user_id: int | None) -> dict:
    """Was die Akte beim Laden braucht (GET /api/projects/{id}/akte). LookupError: der gewünschte Auftrag gehört nicht zum Projekt."""
    from .invoices import list_invoices_for_order, order_sum
    from .models import ProjectDocument
    from .service_reports import bericht_zum_auftrag_moeglich

    orders = sorted(db.scalars(select(Order).where(Order.project_id == project.id)), key=lambda o: o.id)
    gewaehlt = auftrag_waehlen(orders, gewuenscht)
    if gewuenscht is not None and gewaehlt is None:
        raise LookupError("Auftrag nicht gefunden.")
    sig = signale(db, [o.id for o in orders])
    je = {o.id: phasen(o, sig[o.id]) for o in orders}
    quotes = list(db.scalars(select(Quote).where(Quote.project_id == project.id).order_by(Quote.id)))
    offen = [q for q in quotes if q.status != "abgelehnt"] or quotes
    from .auftragsstatus import NAMEN
    return {
        "auftraege": [{"id": o.id, "order_number": o.order_number, "title": o.title, "net_total": order_sum(o), "status": status_wert(o.status),
                       "status_label": NAMEN.get(status_wert(o.status), o.status), "phase": je[o.id]["phase"], "phase_label": je[o.id]["phase_label"]}
                      for o in orders],
        "summe_auftraege": sum((order_sum(o) for o in orders), NULL),
        "auftrag_id": gewaehlt.id if gewaehlt else None,
        "phasen": je[gewaehlt.id] if gewaehlt else phasen_ohne_auftrag(quotes),
        "angebot_id": max(offen, key=lambda q: q.id).id if offen else None,
        "ansteht": ansteht(db, gewaehlt) if gewaehlt else [],
        "termine": termine(db, project, gewaehlt, viewer_user_id),
        "ausfuehrung": ausfuehrung(db, gewaehlt) if gewaehlt else None,
        "befunde": befunde(db, gewaehlt) if gewaehlt else [],
        "bericht_anlegen": bericht_zum_auftrag_moeglich(gewaehlt) if gewaehlt else False,
        "zaehler": {"angebote": len(quotes), "leistungen": len(gewaehlt.items) if gewaehlt else 0,
                    "rechnungen": len(list_invoices_for_order(db, gewaehlt.id)) if gewaehlt else 0,
                    "dateien": db.scalar(select(func.count(ProjectDocument.id)).where(ProjectDocument.project_id == project.id)) or 0},
        "_haupt": {"phase": je[gewaehlt.id]["phase"] if gewaehlt else None, "hat_angebot": bool(quotes),
                   "verweigert": bool(gewaehlt and sig[gewaehlt.id].verweigert is not None),
                   "geschlossen": bool(gewaehlt and status_wert(gewaehlt.status) in GESCHLOSSEN), "muster": bool(project.is_template)},
    }
