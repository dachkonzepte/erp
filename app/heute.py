"""„Heute“ für die Monteurin (seit 1.9.45, Stufe 4, R2): was /mobil oben zeigt -- Arbeitszeit, heutiger Einsatz je Auftrag, Offen, Nächste Tage.

Eine Funktion, heute_fuer(), liefert alles für GET /api/field-view/today (Schlüssel "heute"); die Seite rechnet nichts davon selbst nach
(Regel: keine zweite Rechnung im Browser). Rollenlos wie jede Geschäftslogik: der Router entscheidet, wer es sieht (MOBIL_ROLLEN) und
reicht die Rolle nur als "ist_monteur" für die Sperre "Monat abgeschlossen" herein (dieselbe Regel wie POST …/ende-nachtragen).

    Arbeitszeit  "laeuft": die eigene Zeit von heute (Zeitart, Beginn, Dauer in Minuten bis jetzt, Auftrag · Objekt); in einer laufenden
                 Gruppe stoppt sie der Kolonnenführer, der sie gestartet hat und es noch ist -- er bekommt "gruppe_stoppen", jedes andere
                 Mitglied "stoppt" mit seinem Namen und keinen Knopf.
                 "frueher": die eigene Zeit läuft seit einem früheren Tag (vergessener Feierabend) -- Ende nachtragen nur, wer sie
                 selbst schließen darf (offene_zeit_info()), nicht im abgeschlossenen Monat (Monteurin).
                 "nichts": Auftragsauswahl (list_field_bookable_orders()), vorbelegt bei genau einem Auftrag im heutigen Einsatz; seit
                 1.9.58 (Stufe 4, R3) dazu die Tätigkeiten (taetigkeiten(), Pflicht nach den Zeitregeln) für „⋮ Mit Tätigkeit starten“
                 und die Kolonnen des Kolonnenführers (list_crews_for_leader(), nur mit Gruppenbuchungen) für „⋮ Für die Kolonne
                 starten“ -- bis dahin auf der Zeiterfassung der Monteurin, die „Meine Zeiten“ ersetzt (Starten nur noch auf „Heute“).
    Einsätze     je Auftrag eine Karte, auch bei mehreren Plantafel-Abschnitten am selben Auftrag; Zeitraum = früheste bis späteste
                 Abschnittsgrenze der heute geltenden Abschnitte. Darin die eigenen Berichte (Entwürfe, dazu heute unterschriebene) mit
                 "noch n offen" aus noch_offen() und die eigenen Checklisten (offen, dazu heute abgeschlossene) mit den fehlenden
                 Pflichtangaben (missing_required_labels()).
    Offen        Zahl der eigenen offenen Berichte, offenen Checklisten (wie GET /api/checklists/mine), Mängel zur Beseitigung
                 (list_field_defects()) und seit 1.9.49 der Wartungsverträge an meinen Objekten (list_relevant_contracts_for_employee())
                 -- dieselben Listen wie auf „Heute / Offen“ (/mobil/offen).
    Nächste Tage Plantafel ab morgen, 14 Tage (bei offener Zeit von früher ab heute, Vorlage „Heute und nächste Tage“); aufeinander
                 folgende Tage desselben Auftrags in einer Zeile.
    Aufträge     seit 1.9.75 (Stufe 4, R4 Nachtrag): die Auftragsliste der Monteurin (list_field_bookable_orders(), dieselbe wie „Zeit
                 nachtragen“) für den Dialog „Für welchen Auftrag?“ -- „Bericht anlegen“ ohne Einsatz und „Bericht für einen anderen
                 Auftrag“; anlegen darf sie genau dafür (app/planning.py::field_order_in_list()).
"""

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .berlin_time import to_berlin
from .checklist_purposes import purpose_office_only
from .checklists import list_checklists, missing_required_labels
from .concern_notices import open_concerns
from .defects import list_field_defects
from .maintenance_contracts import list_relevant_contracts_for_employee
from .meldungen import MONAT_ABGESCHLOSSEN
from .models import Checklist, Employee, Order, ServiceReport
from .modules import is_module_enabled
from .option_settings import get_option_group
from .planning import list_field_bookable_orders, list_todays_assignments_for_employee, list_upcoming_assignments_for_employee
from .service_reports import REPORT_TYPE_LABELS, _report_roof_areas_to_dicts, list_draft_reports_for_employee, noch_offen
from .time_backoffice import load_time_settings, locked_until
from .time_tracking import (
    ZEITART_NAMEN, active_entry, crew_leader_team_ids, employee_name, group_for_entry, laeuft_seit_frueher, list_crews_for_leader,
)

NAECHSTE_TAGE = 14


def zeitarten(db: Session) -> list[dict]:
    """Die aktiven Zeitarten (Optionsgruppe time_entry_types) für die Kacheln -- dieselbe Quelle wie „Schnell starten“."""
    gruppe = get_option_group(db, "time_entry_types")
    optionen = sorted((o for o in (gruppe.options if gruppe is not None else []) if o.active), key=lambda o: (o.sort_order, o.id))
    if not optionen:
        return [{"value": k, "label": v} for k, v in ZEITART_NAMEN.items()]
    return [{"value": o.value, "label": o.label} for o in optionen]


def taetigkeiten(db: Session) -> list[dict]:
    """Die aktiven Tätigkeiten (Optionsgruppe time_entry_activities) für „⋮ Mit Tätigkeit starten“ (seit 1.9.58) -- dieselbe Quelle wie
    das Feld „Tätigkeit“ der Zeiterfassung."""
    gruppe = get_option_group(db, "time_entry_activities")
    optionen = sorted((o for o in (gruppe.options if gruppe is not None else []) if o.active), key=lambda o: (o.sort_order, o.id))
    return [{"value": o.value, "label": o.label} for o in optionen]


def _zeitart_name(arten: list[dict], wert: str) -> str:
    return next((a["label"] for a in arten if a["value"] == wert), None) or ZEITART_NAMEN.get(wert, wert)


def _objekt(order) -> str | None:
    if order is None:
        return None
    prop = order.project.property if order.project is not None else None
    return (prop.name if prop is not None else order.property_name) or order.customer_name


def _gruppe(db: Session, entry_id: int, employee_id: int) -> dict | None:
    gruppe = group_for_entry(db, entry_id)
    if gruppe is None or gruppe.status != "running":
        return None
    fuehrt = gruppe.initiated_by_employee_id == employee_id and gruppe.team_id in crew_leader_team_ids(db, employee_id)
    initiator = db.get(Employee, gruppe.initiated_by_employee_id) if gruppe.initiated_by_employee_id else None
    return {"id": gruppe.id, "kolonnenfuehrer": fuehrt, "stoppt": None if fuehrt else (employee_name(initiator) or "der Kolonnenführer")}


def arbeitszeit(db: Session, employee_id: int, *, heute: date, jetzt: datetime, ist_monteur: bool, arten: list[dict],
                einsatz_auftraege: list[int], auftraege: list[dict] | None = None) -> dict:
    row = active_entry(db, employee_id)
    if row is not None and laeuft_seit_frueher(row, heute):
        gruppe = _gruppe(db, row.id, employee_id)
        lock = locked_until(db) if ist_monteur else None
        return {
            "zustand": "frueher", "id": row.id, "tag": row.started_at.date(), "gestern": row.started_at.date() == heute - timedelta(days=1),
            "beginn": row.started_at.strftime("%H:%M"), "zeitart": row.entry_type, "zeitart_label": _zeitart_name(arten, row.entry_type),
            "order_id": row.order_id, "order_number": row.order.order_number if row.order else None, "objekt": _objekt(row.order),
            "monat_abgeschlossen": bool(lock is not None and row.work_date <= lock), "meldung": MONAT_ABGESCHLOSSEN,
            "gruppe": gruppe is not None, "nachtragen_durch": gruppe["stoppt"] if gruppe and not gruppe["kolonnenfuehrer"] else None,
        }
    if row is not None:
        gruppe = _gruppe(db, row.id, employee_id)
        return {
            "zustand": "laeuft", "id": row.id, "beginn": row.started_at.strftime("%H:%M"),
            "dauer_minuten": max(0, int((jetzt - row.started_at).total_seconds() // 60)),
            "zeitart": row.entry_type, "zeitart_label": _zeitart_name(arten, row.entry_type),
            "order_id": row.order_id, "order_number": row.order.order_number if row.order else None, "objekt": _objekt(row.order),
            "gruppe": gruppe,
        }
    if auftraege is None:
        auftraege = list_field_bookable_orders(db, employee_id)
    buchbar = {a["id"] for a in auftraege}
    eindeutig = sorted(set(einsatz_auftraege))
    regeln = load_time_settings(db)
    return {"zustand": "nichts", "auftraege": auftraege,
            "vorbelegt": eindeutig[0] if len(eindeutig) == 1 and eindeutig[0] in buchbar else None,
            # seit 1.9.58: „⋮ Mit Tätigkeit starten“ (verlangen die Zeitregeln eine Tätigkeit, öffnet auch eine Kachel den Dialog) und
            # „⋮ Für die Kolonne starten“ -- nur mit Gruppenbuchungen (der Server lehnte den Start sonst ab, 403)
            "taetigkeiten": taetigkeiten(db), "taetigkeit_pflicht": bool(regeln.require_activity),
            "kolonnen": list_crews_for_leader(db, employee_id) if regeln.allow_group_bookings else []}


def _berichte(db: Session, employee_id: int, order_ids: list[int], heute: date) -> dict[int, list[dict]]:
    """Die eigenen Berichte je Auftrag: Entwürfe (mit "noch n offen") und heute unterschriebene."""
    if not order_ids:
        return {}
    rows = db.scalars(
        select(ServiceReport)
        .options(selectinload(ServiceReport.inspection_items), selectinload(ServiceReport.findings))
        .where(ServiceReport.order_id.in_(order_ids), ServiceReport.created_by_employee_id == employee_id,
               (ServiceReport.status == "entwurf") | ((ServiceReport.status == "unterschrieben") & (ServiceReport.performed_at == heute)))
        .order_by(ServiceReport.status, ServiceReport.id)
    ).all()
    result: dict[int, list[dict]] = {}
    for r in rows:
        flaechen = ", ".join(a["roof_area_name"] for a in _report_roof_areas_to_dicts(r) if a.get("roof_area_name"))
        result.setdefault(r.order_id, []).append({
            "id": r.id, "titel": REPORT_TYPE_LABELS.get(r.report_type, r.report_type) + (f" · {flaechen}" if flaechen else ""),
            "status": r.status, "noch_offen": len(noch_offen(r)) if r.status == "entwurf" else 0,
        })
    return result


def checklisten_titel(name: str | None) -> str:
    """Seit 1.9.50 (Stufe 4, R2 Nachrunde, Punkt 3): die Zeile einer Checkliste heißt „Checkliste <Name>“ -- beginnt der Name schon
    mit „Checkliste“, bleibt er (kein „Checkliste Checkliste …“)."""
    name = (name or "").strip()
    return name if name.casefold().startswith("checkliste") else f"Checkliste {name}".strip()


def _checklisten(db: Session, employee_id: int, order_ids: list[int], heute: date) -> dict[int, list[dict]]:
    """Die eigenen Checklisten je Auftrag: offene (mit den fehlenden Pflichtangaben) und heute abgeschlossene; nie eine des Büros."""
    if not order_ids:
        return {}
    rows = db.scalars(
        select(Checklist)
        .where(Checklist.order_id.in_(order_ids), Checklist.created_by_employee_id == employee_id,
               Checklist.status.in_(("entwurf", "abgeschlossen")))
        .order_by(Checklist.id)
    ).all()
    result: dict[int, list[dict]] = {}
    for c in rows:
        if purpose_office_only(c.template_version.purpose):
            continue
        if c.status == "abgeschlossen" and (c.completed_at is None or to_berlin(c.completed_at).date() != heute):
            continue
        result.setdefault(c.order_id, []).append({
            "id": c.id, "titel": checklisten_titel(c.template_label_snapshot), "status": c.status,
            "noch_offen": len(missing_required_labels(c)) if c.status == "entwurf" else 0,
        })
    return result


def einsaetze(db: Session, employee_id: int, *, heute: date) -> list[dict]:
    """Heutiger Einsatz je Auftrag (nicht je Plantafel-Abschnitt), in der Reihenfolge des frühesten Abschnitts."""
    karten: dict[int, dict] = {}
    for a in list_todays_assignments_for_employee(db, employee_id, heute):
        karte = karten.get(a["order_id"])
        if karte is None:
            karten[a["order_id"]] = {
                "order_id": a["order_id"], "order_number": a["order_number"], "von": a["start_date"], "bis": a["end_date"],
                "objekt": a["property_name"] or a["customer_name"], "kunde": a["customer_name"], "adresse": a["property_address"] or "",
            }
        else:
            karte["von"], karte["bis"] = min(karte["von"], a["start_date"]), max(karte["bis"], a["end_date"])
    order_ids = list(karten)
    berichte = _berichte(db, employee_id, order_ids, heute) if is_module_enabled(db, "wartungen") else {}
    mit_checklisten = is_module_enabled(db, "checklisten")
    checklisten = _checklisten(db, employee_id, order_ids, heute) if mit_checklisten else {}
    bedenken = open_concerns(db, sorted(order_ids)) if mit_checklisten else {}
    return [{**k, "berichte": berichte.get(k["order_id"], []), "checklisten": checklisten.get(k["order_id"], []),
             "open_concerns": bedenken.get(k["order_id"], [])} for k in karten.values()]


def offen(db: Session, employee_id: int) -> dict:
    """Zahlen für die Karte „Offen“ -- dieselben Listen wie auf „Heute / Offen“ (seit 1.9.49 eine eigene Seite, bis dahin unter „Heute“).
    "wartungen" (seit 1.9.49) zählt die Verträge, nicht die Objekte."""
    mit_wartungen = is_module_enabled(db, "wartungen")
    berichte = len(list_draft_reports_for_employee(db, employee_id)) if mit_wartungen else 0
    wartungen = sum(len(g["contracts"]) for g in list_relevant_contracts_for_employee(db, employee_id)) if mit_wartungen else 0
    checklisten = 0
    if is_module_enabled(db, "checklisten"):
        checklisten = sum(1 for c in list_checklists(db, created_by_employee_id=employee_id, status="entwurf")
                          if c["context_type"] != "betrieb" and not purpose_office_only(c["purpose"]))
    return {"berichte": berichte, "checklisten": checklisten, "maengel": len(list_field_defects(db, employee_id)), "wartungen": wartungen}


def naechste_tage(db: Session, employee_id: int, *, heute: date, mit_heute: bool, einsatz_auftraege: set[int]) -> list[dict]:
    """Plantafel ab morgen für 14 Tage (mit_heute: dazu heute als eigene Zeile); je Auftrag die aufeinander folgenden Tage in einer
    Zeile. Zusatz hinter dem Objekt: „Fortsetzung“, wenn der Auftrag heute schon Einsatz ist, sonst der Titel des Auftrags."""
    morgen, ende = heute + timedelta(days=1), heute + timedelta(days=NAECHSTE_TAGE)
    tage: dict[int, set[date]] = {}
    info: dict[int, dict] = {}
    for a in list_upcoming_assignments_for_employee(db, employee_id, today=heute, days_ahead=NAECHSTE_TAGE):
        tag = max(a["start_date"], morgen)
        while tag <= min(a["end_date"], ende):
            tage.setdefault(a["order_id"], set()).add(tag)
            tag += timedelta(days=1)
        info.setdefault(a["order_id"], a)
    titel = dict(db.execute(select(Order.id, Order.title).where(Order.id.in_(list(info)))).all()) if info else {}
    zeilen = []
    if mit_heute:
        for order_id in sorted(einsatz_auftraege, key=lambda o: info.get(o, {}).get("order_number") or ""):
            if order_id in info:
                zeilen.append(_zeile(info[order_id], heute, heute, titel.get(order_id)))
    for order_id, menge in tage.items():
        folge = sorted(menge)
        von = vorher = folge[0]
        for tag in folge[1:] + [None]:
            if tag is not None and tag == vorher + timedelta(days=1):
                vorher = tag
                continue
            nebentext = "Fortsetzung" if order_id in einsatz_auftraege else titel.get(order_id)
            zeilen.append(_zeile(info[order_id], von, vorher, nebentext))
            if tag is not None:
                von = vorher = tag
    return sorted(zeilen, key=lambda z: (z["von"], z["bis"], z["order_number"] or ""))


def _zeile(a: dict, von: date, bis: date, nebentext: str | None) -> dict:
    return {"von": von, "bis": bis, "order_id": a["order_id"], "order_number": a["order_number"],
            "objekt": a["property_name"] or a["customer_name"], "nebentext": nebentext or a["order_number"]}


def heute_fuer(db: Session, employee_id: int, *, heute: date, jetzt: datetime, ist_monteur: bool) -> dict:
    arten = zeitarten(db)
    karten = einsaetze(db, employee_id, heute=heute)
    einsatz_auftraege = {k["order_id"] for k in karten}
    auftraege = list_field_bookable_orders(db, employee_id)
    zeit = arbeitszeit(db, employee_id, heute=heute, jetzt=jetzt, ist_monteur=ist_monteur, arten=arten,
                       einsatz_auftraege=sorted(einsatz_auftraege), auftraege=auftraege)
    return {
        "tag": heute, "mitarbeiter_id": employee_id, "arbeitszeit": zeit, "zeitarten": arten, "einsaetze": karten, "offen": offen(db, employee_id),
        "auftraege": auftraege,
        "naechste_tage": naechste_tage(db, employee_id, heute=heute, mit_heute=zeit["zustand"] == "frueher",
                                       einsatz_auftraege=einsatz_auftraege),
    }
