"""Seit 1.9.279 (Stufe 6, R5c, Punkt 1): die Auftragsliste der Woche für die Ansicht „Aufträge“ der Plantafel.

Zeichnung bildgrundlage/entwurf-stufe6/plantafel-auftraege(-regeln).html, Befund R5 (E, G) und Antwort 10 aus R5a:

    Zeilen     alle offenen Aufträge (läuft, pausiert; nicht abgeschlossen, nicht storniert). Mit Einsatz im Zeitraum oben („eingeplant“), nach ihrem ersten Tag
               im Zeitraum, dann nach Nummer; darunter die übrigen nach Nummer.
    Stunden    wie die Akte (app/akte.py::soll_stunden(), Ist = gebuchte Baustelle & Werkstatt): Kranvermietung „Kran mit Bediener“ bzw. „Kran ohne Bediener“,
               aus einem Wartungsvertrag „Wartungsvertrag“, ohne Soll „nach Aufwand“; sonst „Soll …“, solange nichts gebucht ist, danach „Rest …“ (Soll minus
               gebucht; darüber „… über Soll“).
    Zusatz     eingeplant: „vorläufig“, wenn ein Einsatz im Zeitraum vorläufig ist; sonst der nächste Einsatz nach dem Zeitraum („ab 16.11.“) oder „ohne Termin“;
               „pausiert“ bei einem pausierten Auftrag.
    Abfragen   eine feste Zahl, unabhängig von der Zahl der Aufträge und Einsätze (tests/test_v679_auftragsliste.py) -- rollenlos; die Rolle prüft der Router.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .akte import BAUSTELLE_WERKSTATT, NULL, soll_stunden, stunden_text
from .auftragsstatus import offen_bedingung, wert as status_wert
from .models import Order, OrderItem, PlanningSlot, PlanningSlotEmployee, Project, ProjectProfile, TimeEntry, WorkPreparation
from .rounding import round_hours

MAX_TAGE = 63  # wie die Tafel


def _tag_kurz(d: date) -> str:
    return d.strftime("%d.%m.")


def stunden_zeile(*, soll: Decimal, gebucht: Decimal, kran: bool | None, wartungsvertrag: bool) -> str:
    """Was die Zeile unter dem Namen zu den Stunden sagt (Antwort 10). kran: None = keine Kranvermietung, True/False = mit/ohne Bediener."""
    if kran is not None:
        return "Kran mit Bediener" if kran else "Kran ohne Bediener"
    if wartungsvertrag:
        return "Wartungsvertrag"
    if soll <= 0:
        return "nach Aufwand"
    if gebucht <= 0:
        return f"Soll {stunden_text(soll)}"
    rest = round_hours(soll - gebucht)
    return f"Rest {stunden_text(rest)}" if rest >= 0 else f"{stunden_text(-rest)} über Soll"


def auftragsliste(db: Session, start: date, ende: date) -> list[dict]:
    """Die Zeilen der Ansicht „Aufträge“ für den Zeitraum start–ende (höchstens 63 Tage)."""
    if ende < start:
        raise ValueError("Enddatum darf nicht vor dem Startdatum liegen.")
    if (ende - start).days >= MAX_TAGE:
        raise ValueError(f"Die Plantafel kann maximal {MAX_TAGE} Tage gleichzeitig anzeigen.")
    offen = select(Order.id).where(offen_bedingung()).scalar_subquery()
    orders = db.scalars(select(Order).options(selectinload(Order.project), selectinload(Order.items).selectinload(OrderItem.calculation_snapshot))
                        .where(offen_bedingung())).all()
    gebucht = {oid: Decimal(h or 0) for oid, h in db.execute(
        select(TimeEntry.order_id, func.sum(TimeEntry.hours))
        .where(TimeEntry.order_id.in_(offen), TimeEntry.status == "booked", TimeEntry.entry_type.in_(BAUSTELLE_WERKSTATT))
        .group_by(TimeEntry.order_id))}
    im_zeitraum: dict[int, list[tuple[date, date, str]]] = {}
    for oid, von, bis, status in db.execute(
            select(WorkPreparation.order_id, PlanningSlot.start_date, PlanningSlot.end_date, PlanningSlot.status)
            .join(PlanningSlot, PlanningSlot.preparation_id == WorkPreparation.id)
            .where(WorkPreparation.order_id.in_(offen), PlanningSlot.start_date <= ende, PlanningSlot.end_date >= start)):
        im_zeitraum.setdefault(oid, []).append((von, bis, status))
    naechster = dict(db.execute(
        select(WorkPreparation.order_id, func.min(PlanningSlot.start_date))
        .join(PlanningSlot, PlanningSlot.preparation_id == WorkPreparation.id)
        .where(WorkPreparation.order_id.in_(offen), PlanningSlot.start_date > ende).group_by(WorkPreparation.order_id)).all())
    kran = {oid: bool(n) for oid, n in db.execute(
        select(WorkPreparation.order_id, func.count(PlanningSlotEmployee.id))
        .join(PlanningSlot, PlanningSlot.preparation_id == WorkPreparation.id)
        .outerjoin(PlanningSlotEmployee, PlanningSlotEmployee.slot_id == PlanningSlot.id)
        .where(WorkPreparation.order_id.in_(offen), PlanningSlot.art == "kranvermietung").group_by(WorkPreparation.order_id))}
    wartung = set(db.scalars(select(ProjectProfile.project_id).where(ProjectProfile.source_maintenance_contract_id.is_not(None),
                                                                      ProjectProfile.project_id.in_(select(Order.project_id).where(offen_bedingung())))))
    zeilen = []
    for o in orders:
        einsaetze = im_zeitraum.get(o.id, [])
        soll = soll_stunden(o)
        zusatz = []
        if einsaetze:
            if any(s == "vorlaeufig" for _, _, s in einsaetze):
                zusatz.append("vorläufig")
        else:
            zusatz.append(f"ab {_tag_kurz(naechster[o.id])}" if o.id in naechster else "ohne Termin")
        if status_wert(o.status) == "pausiert":
            zusatz.append("pausiert")
        projekt = o.project
        zeilen.append({
            "order_id": o.id, "order_number": o.order_number, "project_id": o.project_id, "project_number": projekt.project_number if projekt else None,
            "project_name": projekt.name if projekt else None, "customer_name": o.customer_name, "status": status_wert(o.status),
            "eingeplant": bool(einsaetze), "erster_tag": max(min(v for v, _, _ in einsaetze), start).isoformat() if einsaetze else None,
            "naechster_einsatz": naechster[o.id].isoformat() if o.id in naechster else None,
            "soll": soll, "gebucht": round_hours(gebucht.get(o.id, NULL)),
            "stunden": stunden_zeile(soll=soll, gebucht=gebucht.get(o.id, NULL), kran=kran.get(o.id), wartungsvertrag=o.project_id in wartung),
            "zusatz": zusatz,
        })
    zeilen.sort(key=lambda z: (not z["eingeplant"], z["erster_tag"] or "", z["order_number"] or "", z["order_id"]))
    return zeilen
