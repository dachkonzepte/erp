"""„Heute“ für die Monteurin (seit 1.9.45, Stufe 4, R2): was /mobil oben zeigt -- Arbeitszeit, heutiger Einsatz je Auftrag, Offen, Nächste Tage.

Eine Funktion, heute_fuer(), liefert alles für GET /api/field-view/today (Schlüssel "heute"); die Seite rechnet nichts davon selbst nach
(Regel: keine zweite Rechnung im Browser). Rollenlos wie jede Geschäftslogik: der Router entscheidet, wer es sieht (MOBIL_ROLLEN) und
reicht die Rolle nur als "ist_monteur" für die Sperre "Monat abgeschlossen" herein (dieselbe Regel wie POST …/ende-nachtragen).

    Arbeitszeit  "laeuft": die eigene Zeit von heute (Zeitart, Beginn, Dauer in Minuten bis jetzt, Auftrag · Objekt); in einer laufenden
                 Gruppe stoppt sie der Kolonnenführer, der sie gestartet hat und es noch ist -- er bekommt "gruppe_stoppen", jedes andere
                 Mitglied "stoppt" mit seinem Namen und keinen Knopf.
                 "frueher": die eigene Zeit läuft seit einem früheren Tag (vergessener Feierabend) -- Ende nachtragen nur, wer sie
                 selbst schließen darf (offene_zeit_info()), nicht im abgeschlossenen Monat (Monteurin).
                 "nichts": Auftragsauswahl (list_field_bookable_orders()), vorbelegt bei genau einem Auftrag im heutigen Einsatz, der in
                 dieser Liste steht (seit 1.9.87 zählt ein abgeschlossener oder stornierter Einsatz dabei nicht mit); seit
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
    Nächste Tage Plantafel ab morgen, 14 Tage (bei offener Zeit von früher ab heute, Vorlage „Heute und nächste Tage“); seit 1.9.242 je Einsatz
                 die aufeinander folgenden Arbeitstage in einer Zeile (ohne Wochenende, Feiertag, betriebsfreien Tag und eigene Abwesenheit), dazu
                 jede eigene Abwesenheit und jeder eigene offene Antrag als eigene Zeile; bis 1.9.241 je Auftrag alle Kalendertage.
    Einsatz      seit 1.9.242 (Stufe 6, R3b, Punkt 4, Zeichnung heute-einsatz.html) in der Karte: vorläufig/fest, „Mit dir“ (die Besetzung ohne
                 sie selbst; wer heute abwesend ist, steht nur als „ist nicht da“ dabei, nie mit der Art), die Geräte an ihren Tagen, die Notiz des
                 Einsatzes, die Baustellenhinweise der Arbeitsvorbereitung. Die Karte gibt es nur an einem Arbeitstag und nicht, wenn sie selbst
                 abwesend ist (heute_frei sagt dann, warum; Schlüssel der Karte: angaben).
    Aufträge     seit 1.9.75 (Stufe 4, R4 Nachtrag): die Auftragsliste der Monteurin (list_field_bookable_orders(), dieselbe wie „Zeit
                 nachtragen“) für den Dialog „Für welchen Auftrag?“ -- „Bericht anlegen“ ohne Einsatz und „Bericht für einen anderen
                 Auftrag“ (1.9.74–1.9.78 durfte sie genau dafür anlegen; seit 1.9.79 zu jedem nicht stornierten Auftrag, die übrigen
                 findet die Suche im Dialog).
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
from .models import Checklist, Employee, Order, PlanningSlot, PlanningSlotEmployee, PlanningSlotResource, Project, ServiceReport, WorkPreparation
from .modules import is_module_enabled
from .option_settings import get_option_group
from .planning import list_field_bookable_orders, list_todays_assignments_for_employee
from .service_reports import REPORT_TYPE_LABELS, _report_roof_areas_to_dicts, list_draft_reports_for_employee, noch_offen
from .time_backoffice import load_time_settings, locked_until
from .time_tracking import (
    ZEITART_NAMEN, active_entry, auftrag_geschlossen, crew_leader_team_ids, employee_name, group_for_entry, laeuft_seit_frueher,
    list_crews_for_leader,
)

NAECHSTE_TAGE = 14
WOCHENTAGE = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")


class Tage:
    """Seit 1.9.242: Arbeitstage und die eigenen Abwesenheiten einer Person von von bis bis -- dieselbe Rechnung wie die Plantafel (Arbeitstage der
    Planung, Feiertage und betriebsfreie Tage; genehmigte Abwesenheit und Freistellung des Arbeitszeitkalenders, app/planning.py::_abwesend_map())."""

    def __init__(self, db: Session, employee_id: int, von: date, bis: date):
        from .planning import _absence_rows, _abwesend_map, _combined_holiday_map, _is_workday, _offene_antraege, load_planning_settings
        einstellungen = load_planning_settings(db)
        feiertage = set(_combined_holiday_map(db, von, bis)[0])
        self.arbeitstage = {von + timedelta(days=i) for i in range((bis - von).days + 1)
                            if _is_workday(von + timedelta(days=i), einstellungen, feiertage)}
        self.zeilen = _absence_rows(db, von, bis, {employee_id})
        person = db.get(Employee, employee_id)
        self.abwesend = {tag: a for (eid, tag), a in _abwesend_map(db, self.zeilen, [person], von, bis).items() if eid == employee_id}
        self.antraege = _offene_antraege(db, von, bis, {employee_id}).get(employee_id, [])

    def arbeitet(self, tag: date) -> bool:
        return tag in self.arbeitstage and tag not in self.abwesend


def _tag_kurz(tag: date) -> str:
    return f"{WOCHENTAGE[tag.weekday()]} {tag:%d.%m.}"


def _slots(db: Session, employee_id: int, von: date, bis: date) -> list[PlanningSlot]:
    """Die Einsätze, in deren Besetzung sie steht und die von..bis berühren -- mit Besetzung, Geräten, Arbeitsvorbereitung, Auftrag und Objekt."""
    from .planning import _employee_assignment_slot_condition
    return db.scalars(select(PlanningSlot).options(
        selectinload(PlanningSlot.besetzung).selectinload(PlanningSlotEmployee.employee),
        selectinload(PlanningSlot.geraete).selectinload(PlanningSlotResource.resource),
        selectinload(PlanningSlot.preparation).selectinload(WorkPreparation.order).selectinload(Order.project).selectinload(Project.property),
    ).where(PlanningSlot.start_date <= bis, PlanningSlot.end_date >= von, _employee_assignment_slot_condition(employee_id))
        .order_by(PlanningSlot.start_date, PlanningSlot.id)).all()


def _name(e: Employee | None) -> str:
    return " ".join(x for x in [(e.first_name or "").strip(), (e.last_name or "").strip()] if x) if e is not None else "?"


def einsatz_details(db: Session, employee_id: int, slots: list[PlanningSlot], heute: date) -> dict:
    """Seit 1.9.242: was die Karte des heutigen Einsatzes zu den Einsätzen eines Auftrags zeigt -- Status (vorläufig, wenn einer davon vorläufig ist),
    „Mit dir“, wer nicht da ist (nur der Name), Geräte an ihren Tagen (mit Zusatz bei einzelnen Tagen), Notiz, Baustellenhinweise."""
    from .planning import EINSATZ_STATUS, _abwesend_map, _absence_rows, _tage_der_zeile
    andere = []
    for s in slots:
        for x in s.besetzung:
            if x.employee_id != employee_id and x.employee_id not in [a.id for a in andere]:
                andere.append(x.employee)
    weg = {eid for (eid, _tag) in _abwesend_map(db, _absence_rows(db, heute, heute, {a.id for a in andere}), andere, heute, heute)} if andere else set()
    geraete, gesehen = [], set()
    for s in slots:
        for row in s.geraete:
            tage = sorted(_tage_der_zeile(s, row))
            if heute not in tage or row.resource_id in gesehen:
                continue
            gesehen.add(row.resource_id)
            zusatz = None
            if row.tage:
                spaeter = [t for t in tage if t > heute]
                zusatz = "nur heute" if not spaeter else "auch " + ", ".join(_tag_kurz(t) for t in spaeter[:3]) + (" …" if len(spaeter) > 3 else "")
            geraete.append({"name": row.resource.name if row.resource else f"Gerät #{row.resource_id}", "zusatz": zusatz})
    notizen = [s.notes.strip() for s in slots if (s.notes or "").strip()]
    baustelle = (slots[0].preparation.site_notes or "").strip() or None
    status = "vorlaeufig" if any(s.status == "vorlaeufig" for s in slots) else "fest"
    return {"status": status, "status_label": EINSATZ_STATUS.get(status, status),
            "mit_dir": [_name(a) for a in andere if a.id not in weg], "nicht_da": [_name(a) for a in andere if a.id in weg],
            "geraete": geraete, "notiz": "\n".join(dict.fromkeys(notizen)) or None, "baustelle": baustelle}


def heute_frei(tage: Tage, heute: date) -> str | None:
    """Seit 1.9.242: warum es heute keine Karte gibt -- kein Arbeitstag oder die eigene Abwesenheit (die eigene Art darf sie lesen); sonst None."""
    if heute not in tage.arbeitstage:
        return "Heute ist kein Arbeitstag."
    a = tage.abwesend.get(heute)
    if a is not None:
        return f"Heute bist du nicht eingeplant: {a.absence_type}."
    return None


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
            # seit 1.9.87: abgeschlossen/storniert -- die Seite bietet dann kein „Zeitart wechseln“ an (der Server lehnt es ab, 1.9.81)
            "auftrag_geschlossen": auftrag_geschlossen(row.order.status if row.order else None),
        }
    if auftraege is None:
        auftraege = list_field_bookable_orders(db, employee_id)
    buchbar = {a["id"] for a in auftraege}
    # seit 1.9.87 nur die Einsätze, auf die sie bucht (abgeschlossene und stornierte stehen nicht in der Liste): ein offener neben einem
    # abgeschlossenen ist vorbelegt -- bis 1.9.86 zählte der abgeschlossene mit, dann war keiner vorbelegt
    eindeutig = sorted(set(einsatz_auftraege) & buchbar)
    regeln = load_time_settings(db)
    return {"zustand": "nichts", "auftraege": auftraege,
            "vorbelegt": eindeutig[0] if len(eindeutig) == 1 else None,
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


def einsaetze(db: Session, employee_id: int, *, heute: date, tage: Tage | None = None) -> list[dict]:
    """Heutiger Einsatz je Auftrag (nicht je Plantafel-Abschnitt), in der Reihenfolge des frühesten Abschnitts. Seit 1.9.242 nur an einem Arbeitstag
    und nicht, wenn sie heute abwesend ist; dazu je Karte einsatz_details()."""
    tage = tage or Tage(db, employee_id, heute, heute)
    if not tage.arbeitet(heute):
        return []
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
    # seit 1.9.87: abgeschlossen/storniert je Auftrag -- die Karte zeigt „Auftrag abgeschlossen“ (auf ihn bucht die Monteurin nicht, 1.9.81);
    # seit 1.9.93 (Stufe 4, R5a, Punkt 6) dazu der Titel -- die Karte nennt den Auftrag mit „Nummer · Titel“
    auftraege = {i: (s, t) for i, s, t in db.execute(select(Order.id, Order.status, Order.title).where(Order.id.in_(order_ids))).all()} if order_ids else {}
    status = {i: s for i, (s, _) in auftraege.items()}
    berichte = _berichte(db, employee_id, order_ids, heute) if is_module_enabled(db, "wartungen") else {}
    mit_checklisten = is_module_enabled(db, "checklisten")
    checklisten = _checklisten(db, employee_id, order_ids, heute) if mit_checklisten else {}
    bedenken = open_concerns(db, sorted(order_ids)) if mit_checklisten else {}
    je_auftrag: dict[int, list[PlanningSlot]] = {}
    for s in _slots(db, employee_id, heute, heute):
        je_auftrag.setdefault(s.preparation.order_id, []).append(s)
    return [{**k, "title": auftraege.get(k["order_id"], (None, None))[1], "berichte": berichte.get(k["order_id"], []),
             "checklisten": checklisten.get(k["order_id"], []), "open_concerns": bedenken.get(k["order_id"], []),
             "auftrag_geschlossen": auftrag_geschlossen(status.get(k["order_id"])),
             "angaben": einsatz_details(db, employee_id, je_auftrag.get(k["order_id"], []), heute) if je_auftrag.get(k["order_id"]) else None}
            for k in karten.values()]


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


def naechste_tage(db: Session, employee_id: int, *, heute: date, mit_heute: bool, einsatz_auftraege: set[int], tage: Tage | None = None) -> list[dict]:
    """Seit 1.9.242 (Stufe 6, R3b, Punkt 4): je Einsatz die aufeinander folgenden Arbeitstage ab morgen (mit_heute: ab heute) für 14 Tage -- ohne
    Wochenende, Feiertag, betriebsfreien Tag und Tage eigener Abwesenheit, jede Lücke beginnt eine neue Zeile; mit_heute steht heute als eigene Zeile
    vorn. Zusatz: „weiter“, wenn der Einsatz heute schon läuft; sonst „mit <Vornamen der anderen>“ und „vorläufig“, ohne beides der Titel des
    Auftrags; Tage desselben Auftrags mit demselben Zusatz stehen in einer Zeile (zwei Einsätze nebeneinander). Seit 1.9.243 (Stufe 6, R4, 0a) fehlt
    im „mit …“, wer an dem Tag abwesend ist (genehmigt oder Freistellung, wie „ist nicht da“ auf der Karte; ein offener Antrag nicht) -- der Zusatz
    gilt je Tag, die Zeile teilt sich, wo er sich ändert. Dazu jede eigene genehmigte Abwesenheit („<Art> · genehmigt“) und jeder offene Antrag
    („<Art> · beantragt“) als eigene Zeile, von ihrem ersten bis letzten Arbeitstag im Fenster. Bis 1.9.241: je Auftrag alle Kalendertage in einer
    Zeile, Zusatz „Fortsetzung“ oder der Titel."""
    from .planning import _absence_rows, _abwesend_map
    beginn, ende = (heute if mit_heute else heute + timedelta(days=1)), heute + timedelta(days=NAECHSTE_TAGE)
    tage = tage or Tage(db, employee_id, heute, ende)
    tage_je: dict[tuple, set[date]] = {}  # (Auftrag, Zusatz) -> Tage: zwei Einsätze desselben Auftrags mit demselben Zusatz in einer Zeile
    info = {}
    slots = _slots(db, employee_id, beginn, ende)
    andere_personen = {x.employee_id: x.employee for s in slots for x in s.besetzung if x.employee_id != employee_id}
    weg = set(_abwesend_map(db, _absence_rows(db, beginn, ende, set(andere_personen)), list(andere_personen.values()), beginn, ende)) \
        if andere_personen else set()  # (Person, Tag): abwesend -- seit 1.9.243
    for s in slots:
        order = s.preparation.order
        prop = order.project.property if order.project else None
        info[order.id] = {"order_number": order.order_number, "objekt": (prop.name if prop else order.property_name) or order.customer_name}
        andere = [(x.employee_id, (x.employee.first_name or _name(x.employee)).strip()) for x in s.besetzung if x.employee_id != employee_id]
        tag = max(s.start_date, beginn)
        while tag <= min(s.end_date, ende):
            if tage.arbeitet(tag):
                da = [n for eid, n in andere if (eid, tag) not in weg]
                teile = (["mit " + ", ".join(da)] if da else []) + (["vorläufig"] if s.status == "vorlaeufig" else [])
                sonst = " · ".join(teile) or order.title or order.order_number
                neben = "weiter" if s.start_date <= heute <= s.end_date and tag > heute else sonst  # mit_heute: heute eigene Zeile vorn
                tage_je.setdefault((order.id, neben), set()).add(tag)
            tag += timedelta(days=1)
    zeilen = [{"art": "einsatz", "von": von, "bis": bis, "order_id": oid, "order_number": info[oid]["order_number"], "objekt": info[oid]["objekt"],
               "nebentext": neben}
              for (oid, neben), menge in tage_je.items() for von, bis in _folgen(list(menge))]
    for a, stand in [*((z, "genehmigt") for z in tage.zeilen), *((z, "beantragt") for z in tage.antraege)]:
        arbeit = [t for t in sorted(tage.arbeitstage) if max(a.start_date, beginn) <= t <= min(a.end_date, ende)]
        if arbeit:
            zeilen.append({"art": "abwesenheit", "von": arbeit[0], "bis": arbeit[-1], "order_id": None, "order_number": None,
                           "objekt": a.absence_type or "Abwesenheit", "nebentext": stand})
    return sorted(zeilen, key=lambda z: (z["von"], z["bis"], z["art"], z["order_number"] or ""))


def _folgen(tage_liste: list[date]) -> list[tuple[date, date]]:
    """Aufeinander folgende Kalendertage als (erster, letzter); ein ausgelassener Tag (Wochenende, Feiertag, Abwesenheit) trennt."""
    out: list[tuple[date, date]] = []
    for t in sorted(tage_liste):
        if out and t == out[-1][1] + timedelta(days=1):
            out[-1] = (out[-1][0], t)
        else:
            out.append((t, t))
    return out


def heute_fuer(db: Session, employee_id: int, *, heute: date, jetzt: datetime, ist_monteur: bool) -> dict:
    arten = zeitarten(db)
    tage = Tage(db, employee_id, heute, heute + timedelta(days=NAECHSTE_TAGE))  # seit 1.9.242: Arbeitstage und eigene Abwesenheit
    karten = einsaetze(db, employee_id, heute=heute, tage=tage)
    einsatz_auftraege = {k["order_id"] for k in karten}
    auftraege = list_field_bookable_orders(db, employee_id)
    zeit = arbeitszeit(db, employee_id, heute=heute, jetzt=jetzt, ist_monteur=ist_monteur, arten=arten,
                       einsatz_auftraege=sorted(einsatz_auftraege), auftraege=auftraege)
    return {
        "tag": heute, "mitarbeiter_id": employee_id, "arbeitszeit": zeit, "zeitarten": arten, "einsaetze": karten, "offen": offen(db, employee_id),
        "auftraege": auftraege, "heute_frei": heute_frei(tage, heute),
        "naechste_tage": naechste_tage(db, employee_id, heute=heute, mit_heute=zeit["zustand"] == "frueher",
                                       einsatz_auftraege=einsatz_auftraege, tage=tage),
    }
