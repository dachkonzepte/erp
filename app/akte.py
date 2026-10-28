"""Phase je Auftrag und abgeleiteter Projektstatus (seit 1.9.125, Stufe 5, R2, Punkt 1; Vorlage bildgrundlage/entwurf_stufe5/akte-zuordnung.html).

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
from .rounding import round_half_up, round_hours

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
