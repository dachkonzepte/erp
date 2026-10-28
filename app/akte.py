"""Phase je Auftrag und abgeleiteter Projektstatus (seit 1.9.125, Stufe 5, R2, Punkt 1; Vorlage bildgrundlage/entwurf_stufe5/akte-zuordnung.html),
seit 1.9.126 die Zahlen der Akte je Auftrag (Leistung, Zahlung, Stunden, je Position; unten bei zahlen()).

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
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .auftragsstatus import ABGESCHLOSSEN, GESCHLOSSEN, wert as status_wert
from .berlin_time import berlin_today
from .contract_basis import contract_basis_label
from .models import (
    Invoice, Order, OrderAcceptance, OrderContract, PlanningSlot, Project, Quote, ServiceReport, TimeEntry, WorkPreparation,
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
    wert = round_half_up(Decimal(h or 0), Decimal("0.1"))
    return f"{wert:.1f}".replace(".", ",") + " h"


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
