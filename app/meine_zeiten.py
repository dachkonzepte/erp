"""„Meine Zeiten“ der Monteurin (seit 1.9.57, Stufe 4, R3): was die Seite /mobil/zeiten zeigt -- Kacheln, Buchungen des Monats je Tag, Monat.

Eine Funktion, meine_zeiten(), liefert alles für GET /api/field-view/meine-zeiten; die Seite rechnet nichts davon nach. Rollenlos wie jede
Geschäftslogik: der Router entscheidet, wessen Zeiten (immer die eigenen) und ob „⋮“ gilt.

    Kacheln      Heute, diese Woche (Montag bis Sonntag) und der angezeigte Monat -- gebuchte Stunden; eine laufende Zeit zählt nicht mit
    Tage         je Tag mit Buchungen eine Kopfzeile mit Summe (tagessumme(), dieselbe Funktion wie der Stundenzettel als PDF) und die
                 Pausenprüfung (pausen_vorschau(): passt die abgezogene Pause noch zur Zeitregel?); die Zeilen in der Reihenfolge des Tags,
                 eine laufende Zeit mit „läuft seit“ ohne Stunden
    Monat        gebuchte Stunden, Tage mit Buchungen, davon Fahrzeit und produktiv (bis 1.9.58 die Kennzahlen „Heute“ der Zeiterfassung)
    Dialoge      seit 1.9.59: Zeitarten, Tätigkeiten, buchbare Aufträge, ob Nachtragen erlaubt ist, die Kolonnen des Kolonnenführers samt
                 seinen Gruppenbuchungen im Monat (zum Ändern und Löschen für die Kolonne), die Arten der Abwesenheit -- dieselben Quellen
                 wie bis dahin die Zeiterfassung der Monteurin

Summen: jede Summe addiert die gespeicherten Stunden (vier Nachkommastellen) und rundet erst das Ergebnis kaufmännisch auf zwei Stellen;
die Zeilen zeigen ihre Stunden gerundet -- die Summe der angezeigten Zeilen kann deshalb um 0,01 von der angezeigten Summe abweichen
(wie im Stundenzettel als PDF).
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .heute import taetigkeiten, zeitarten
from .models import TimeEntryGroup, TimeEntryGroupMember
from .option_settings import get_option_group
from .planning import list_field_bookable_orders
from .rounding import round_hours
from .time_backoffice import load_time_settings, locked_until
from .time_tracking import (
    _reihenfolge_am_tag, auftrag_geschlossen, crew_leader_team_ids, entry_to_dict, list_crews_for_leader, list_entries,
    list_groups_initiated_by, mindestpause_der_buchung, pausen_vorschau, tagessumme,
)

MONATSNAMEN = {
    1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
    7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
}


def abwesenheitsarten(db: Session) -> list[dict]:
    """Die aktiven Arten der Abwesenheit (Optionsgruppe absence_types) für „+ Antrag“ (seit 1.9.59, bis dahin las die Zeiterfassung sie
    selbst)."""
    gruppe = get_option_group(db, "absence_types")
    optionen = sorted((o for o in (gruppe.options if gruppe is not None else []) if o.active), key=lambda o: (o.sort_order, o.id))
    return [{"value": o.value, "label": o.label} for o in optionen]


def monatsgrenzen(monat: date) -> tuple[date, date]:
    erster = monat.replace(day=1)
    return erster, erster.replace(day=calendar.monthrange(erster.year, erster.month)[1])


def _gruppen(db: Session, ids: list[int]) -> dict[int, TimeEntryGroup]:
    """Die Gruppe je Buchung (seit 1.9.59 in einer Abfrage für den ganzen Monat, bis dahin eine je Zeile)."""
    if not ids:
        return {}
    paare = db.execute(select(TimeEntryGroupMember.time_entry_id, TimeEntryGroup)
                       .join(TimeEntryGroup, TimeEntryGroup.id == TimeEntryGroupMember.group_id)
                       .where(TimeEntryGroupMember.time_entry_id.in_(ids))).all()
    return {eintrag: gruppe for eintrag, gruppe in paare}


def _zeile(row, gruppe, arten: list[dict], employee_id: int, kolonnen: set[int], lock: date | None) -> dict:
    d = entry_to_dict(row)
    laeuft = row.status == "running"
    return {
        "id": row.id, "status": row.status, "work_date": row.work_date, "entry_type": row.entry_type,
        "zeitart": next((a["label"] for a in arten if a["value"] == row.entry_type), None) or row.entry_type,
        "order_id": row.order_id, "order_number": d["order_number"], "project_name": d["project_name"],
        "gebucht": None if laeuft else round_hours(row.hours or 0), "anwesend": d["anwesend"], "pause": d["pause"],
        # seit 1.9.62: die eingetragene Mindestpause (eine Buchung von vor 1.9.62: die abgezogene Pause) -- „Ändern“ belegt sie vor
        "mindestpause": None if laeuft else mindestpause_der_buchung(row),
        "von": row.started_at.strftime("%H:%M") if row.started_at else None,
        "bis": row.ended_at.strftime("%H:%M") if row.ended_at else None,
        "laeuft": laeuft, "laeuft_seit_frueher": d["laeuft_seit_frueher"],
        "activity": row.activity, "notes": row.notes,
        # „gebucht von“ nur, wenn ein anderer gebucht hat (der Kolonnenführer)
        "gebucht_von": d["booked_by_name"] if d["booked_by_employee_id"] not in (None, employee_id) else None,
        "abgeschlossen": lock is not None and row.work_date <= lock,
        # seit 1.9.87: der Auftrag ist abgeschlossen/storniert -- kein „⋮“ (Ändern, Löschen lehnt der Server ab, 1.9.81), ein Kennzeichen
        "auftrag_geschlossen": auftrag_geschlossen(row.order.status if row.order else None),
        # die Buchung einer Gruppe, die diese Person angelegt hat und als Kolonnenführer noch ändern darf („⋮ Für die Kolonne …“)
        "gruppe_id": gruppe.id if gruppe is not None else None,
        "kolonne_aendern": bool(gruppe is not None and gruppe.status == "booked" and gruppe.initiated_by_employee_id == employee_id
                                and gruppe.team_id in kolonnen),
    }


def meine_zeiten(db: Session, employee_id: int, *, monat: date, heute: date) -> dict:
    """Alles für „Meine Zeiten“: Kacheln (heute, diese Woche, der angezeigte Monat), die Tage des Monats mit Buchungen (neueste zuerst,
    je Tag Summe und Pausenprüfung, die Zeilen in der Reihenfolge des Tags), der Monat und der Abschluss."""
    erster, letzter = monatsgrenzen(monat)
    woche = heute - timedelta(days=heute.weekday())
    rows = list_entries(db, employee_id=employee_id, start_date=erster, end_date=letzter, limit=None)
    kachel_rows = list_entries(db, employee_id=employee_id, start_date=min(woche, heute), end_date=woche + timedelta(days=6), limit=None)
    arten = zeitarten(db)
    lock = locked_until(db)
    kolonnen = set(crew_leader_team_ids(db, employee_id))
    gruppen_je_buchung = _gruppen(db, [r.id for r in rows])
    tage: dict[date, list] = {}
    for r in rows:
        tage.setdefault(r.work_date, []).append(r)
    tag_liste = []
    for tag in sorted(tage, reverse=True):
        eintraege = tage[tag]
        laufend = [r for r in eintraege if r.status == "running"]
        gebucht = _reihenfolge_am_tag([r for r in eintraege if r.status == "booked"])
        pause = pausen_vorschau(db, employee_id, tag) if gebucht else None
        tag_liste.append({
            "tag": tag, "summe": round_hours(tagessumme(eintraege)), "abgeschlossen": lock is not None and tag <= lock,
            "pause": pause,
            "zeilen": [_zeile(r, gruppen_je_buchung.get(r.id), arten, employee_id, kolonnen, lock) for r in gebucht + laufend],
        })
    booked = [r for r in rows if r.status == "booked"]
    regeln = load_time_settings(db)
    # die eigenen Gruppenbuchungen des Kolonnenführers, an denen eine Zeile des Monats „⋮ Für die Kolonne …“ trägt
    gruppen_ids = {z["gruppe_id"] for t in tag_liste for z in t["zeilen"] if z["kolonne_aendern"]}
    gruppen = [g for g in list_groups_initiated_by(db, employee_id, start_date=erster) if g["id"] in gruppen_ids] if gruppen_ids else []
    return {
        "mitarbeiter_id": employee_id,
        "heute": heute, "monat": erster.strftime("%Y-%m"), "monat_name": f"{MONATSNAMEN[erster.month]} {erster.year}",
        "monat_kurz": MONATSNAMEN[erster.month],
        "kacheln": {"heute": round_hours(tagessumme([r for r in kachel_rows if r.work_date == heute])),
                    "woche": round_hours(tagessumme([r for r in kachel_rows if woche <= r.work_date <= woche + timedelta(days=6)])),
                    "monat": round_hours(tagessumme(rows))},
        "monat_tage": len({r.work_date for r in booked}),
        "monat_fahrzeit": round_hours(tagessumme([r for r in booked if r.entry_type == "travel"])),
        "monat_produktiv": round_hours(tagessumme([r for r in booked if r.counts_as_productive])),
        "abgeschlossen_bis": lock,
        "tage": tag_liste,
        # seit 1.9.59 für die Dialoge der Seite
        "zeitarten": arten, "taetigkeiten": taetigkeiten(db), "auftraege": list_field_bookable_orders(db, employee_id),
        "nachtragen_erlaubt": bool(regeln.allow_manual_entries),  # seit 1.9.61 ohne Standardpause
        "kolonnen": list_crews_for_leader(db, employee_id) if regeln.allow_group_bookings else [],
        "kolonnen_buchungen": gruppen, "abwesenheitsarten": abwesenheitsarten(db),
    }
