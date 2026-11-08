"""Plantafel -> Kran-Kalender (seit 1.9.241, Stufe 6, R3b, Punkt 3).

Ein Einsatz mit einem Gerät, das ein eigenes Outlook-Postfach hat (der Kran, OperationalResource.outlook_mailbox, seit 1.9.161), steht an den Tagen dieses
Geräts im Kalender des Geräts -- Baustelle wie Kranvermietung. Je Gerät und zusammenhängender Folge seiner Tage ein ganztägiger Termin (CalendarEvent mit
resource_id und planning_slot_id), Besitzer das Gerät, Herkunft „erp“. Für diese Termine ist die Plantafel führend:

    Speichern  Anlegen, Ändern, Löschen eines Einsatzes und ein Wechsel des Auftragsstatus gleichen die Termine im selben Commit ab (abgleichen(),
               entfernen()); danach gehen sie wie jeder Termin des ERP sofort hinaus (senden(): push_event_best_effort(), Löschaufträge).
    Outlook    Was jemand in Outlook an einem solchen Termin ändert oder löscht, überschreibt bzw. legt der nächste Abgleich neu an
               (app/outlook_calendar_sync.py, „Plantafel führend“).
    Cron       Vor dem Abgleich eines Geräte-Postfachs zieht nachziehen() die Termine aller laufenden und künftigen Einsätze des Geräts nach (ein Postfach,
               das erst nach der Planung eingetragen wurde).

Was keine Termine bekommt: Einsätze eines abgeschlossenen oder stornierten Auftrags (sie zählen auch sonst nicht), Geräte ohne Postfach oder inaktive.
Termine, die direkt in Outlook entstehen, bleiben Termine am Kran (1.9.161); app/planning.py::kran_termin_uebernehmen() macht einen davon zur
Kranvermietung -- er wird dann der Termin des neuen Einsatzes.

Termininhalt: Titel (Auftrag · Projekt bzw. „Kranvermietung · Kunde“, „vorläufig:“ davor), Ort (Adresse), Text (Herkunft, Besetzung bzw. Bediener,
Notiz). Ins Protokoll geht davon nichts (Regel 18).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auftragsstatus import geschlossen
from .berlin_time import berlin_today
from .models import CalendarEvent, OperationalResource, PlanningSlot, PlanningSlotResource, WorkPreparation

HINWEIS = "Aus der Plantafel – bitte dort ändern; was hier geändert wird, überschreibt der nächste Abgleich."


def _postfach(resource: OperationalResource | None) -> str | None:
    from .outlook_calendar_sync import postfach_normal
    return postfach_normal(resource.outlook_mailbox) if resource is not None and resource.active else None


def _laeufe(tage: list[date]) -> list[tuple[date, date]]:
    """Zusammenhängende Folgen aufeinanderfolgender Kalendertage."""
    out: list[tuple[date, date]] = []
    for tag in sorted(set(tage)):
        if out and tag == out[-1][1] + timedelta(days=1):
            out[-1] = (out[-1][0], tag)
        else:
            out.append((tag, tag))
    return out


def _adresse(order) -> str:
    project = order.project
    prop = project.property if project is not None else None
    if prop is not None:
        return ", ".join(x for x in [prop.street, f"{prop.postal_code or ''} {prop.city or ''}".strip()] if x)
    return (order.property_address or "").replace("\n", ", ")


def _inhalt(slot: PlanningSlot, von: date, bis: date) -> dict:
    """Seit 1.9.262 (Stufe 6, R5a, Punkt 3) je Termin (von..bis, eine Folge von Tagen des Geräts): Besetzung bzw. Bediener nur, wer an einem dieser Tage am
    Einsatz steht -- bis 1.9.261 die ganze Besetzung in jedem Termin."""
    from .planning import EINSATZ_STATUS, _employee_name, _tage_der_zeile
    order = slot.preparation.order
    kran = slot.art == "kranvermietung"
    titel = f"Kranvermietung · {order.customer_name}" if kran else f"{order.order_number} · {order.project.name}"
    if slot.status == "vorlaeufig":
        titel = f"{EINSATZ_STATUS['vorlaeufig']}: {titel}"
    namen = ", ".join(_employee_name(x.employee) for x in slot.besetzung if any(von <= t <= bis for t in _tage_der_zeile(slot, x)))
    zeilen = [f"{HINWEIS} Auftrag {order.order_number}."]
    zeilen.append(("Bediener: " + namen if namen else "Ohne Bediener.") if kran else ("Besetzung: " + namen if namen else "Besetzung: niemand."))
    if slot.notes:
        zeilen.append("Notiz: " + slot.notes)
    return {"title": titel[:255], "location": _adresse(order)[:255] or None, "notes": "\n".join(zeilen), "all_day": True, "is_private": False}


def soll(slot: PlanningSlot) -> dict[tuple[int, date, date], dict]:
    """Je (Gerät, erster Tag, letzter Tag) der Inhalt -- was im Kalender der Geräte stehen soll."""
    from .planning import _tage_der_zeile
    if geschlossen(slot.preparation.order):
        return {}
    out = {}
    for row in slot.geraete:
        if _postfach(row.resource) is None:
            continue
        for von, bis in _laeufe(list(_tage_der_zeile(slot, row))):
            out[(row.resource_id, von, bis)] = _inhalt(slot, von, bis)
    return out


def _weg(db: Session, termin: CalendarEvent) -> None:
    from .outlook_calendar_sync import _loeschauftrag, wo_er_liegt
    if termin.outlook_event_id:
        ort = wo_er_liegt(termin)
        if ort is not None:
            _loeschauftrag(db, ort, termin.outlook_event_id)
    db.delete(termin)


def abgleichen(db: Session, slot: PlanningSlot) -> list[int]:
    """Gleicht die Termine eines Einsatzes ab (ohne Commit): was stimmt, bleibt unberührt; ein Termin desselben Geräts wandert auf eine neue Folge
    von Tagen, statt gelöscht und neu angelegt zu werden; was übrig ist, fällt weg (Löschauftrag, wenn es in Outlook liegt). Gibt die Termine zurück,
    die hinausgehen müssen."""
    vorhanden = list(db.scalars(select(CalendarEvent).where(CalendarEvent.planning_slot_id == slot.id).order_by(CalendarEvent.id)))
    ziel = soll(slot)
    offen = dict(ziel)
    rest = []
    for termin in vorhanden:
        schluessel = (termin.resource_id, termin.start_at.date(), termin.end_at.date())
        if schluessel in offen:
            rest.append((termin, schluessel))
            del offen[schluessel]
        else:
            rest.append((termin, None))
    geaendert = []
    for termin, schluessel in rest:
        if schluessel is None:
            frei = next((k for k in offen if k[0] == termin.resource_id), None)
            if frei is None:
                _weg(db, termin)
                continue
            schluessel = frei
            del offen[frei]
        werte = {**ziel[schluessel], "start_at": datetime.combine(schluessel[1], datetime.min.time()),
                 "end_at": datetime.combine(schluessel[2], datetime.min.time()), "external_source": "erp", "owner_user_id": None}
        if any(getattr(termin, k) != v for k, v in werte.items()):
            for k, v in werte.items():
                setattr(termin, k, v)
            geaendert.append(termin)
    for (rid, von, bis), inhalt in offen.items():
        termin = CalendarEvent(resource_id=rid, planning_slot_id=slot.id, external_source="erp", start_at=datetime.combine(von, datetime.min.time()),
                               end_at=datetime.combine(bis, datetime.min.time()), **inhalt)
        db.add(termin)
        geaendert.append(termin)
    db.flush()
    return [t.id for t in geaendert]


def entfernen(db: Session, slot_id: int) -> None:
    """Vor dem Löschen eines Einsatzes (ohne Commit): seine Termine fallen weg, in Outlook über Löschaufträge."""
    for termin in db.scalars(select(CalendarEvent).where(CalendarEvent.planning_slot_id == slot_id)).all():
        _weg(db, termin)
    db.flush()


def auftrag_abgleichen(db: Session, order_id: int) -> list[int]:
    """Nach einem Wechsel des Auftragsstatus (ohne Commit): abgeschlossen oder storniert -> keine Termine, wieder offen -> wieder da."""
    from .planning import _load_slot
    ids = db.scalars(select(PlanningSlot.id).join(WorkPreparation, PlanningSlot.preparation_id == WorkPreparation.id)
                     .where(WorkPreparation.order_id == order_id)).all()
    return [t for sid in ids for t in abgleichen(db, _load_slot(db, sid))]


def nachziehen(db: Session, geraet: OperationalResource, *, heute: date | None = None) -> list[int]:
    """Vor dem Abgleich des Postfachs eines Geräts (ohne Commit): die Termine jedes Einsatzes mit diesem Gerät, der heute oder später endet."""
    from .planning import _load_slot
    heute = heute or berlin_today()
    ids = db.scalars(select(PlanningSlot.id).join(PlanningSlotResource, PlanningSlotResource.slot_id == PlanningSlot.id)
                     .where(PlanningSlotResource.resource_id == geraet.id, PlanningSlot.end_date >= heute).order_by(PlanningSlot.id)).all()
    return [t for sid in ids for t in abgleichen(db, _load_slot(db, sid))]


def senden(db: Session, termin_ids: list[int]) -> None:
    """Nach dem Commit: die Termine gehen sofort hinaus, Löschaufträge werden abgearbeitet -- best effort wie jeder Termin des ERP; was scheitert,
    holt der nächste Abgleich nach."""
    from .outlook_calendar_sync import loeschauftraege_best_effort, push_event_best_effort
    for termin_id in termin_ids:
        push_event_best_effort(db, termin_id)
    loeschauftraege_best_effort(db)
