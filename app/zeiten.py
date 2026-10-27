"""Die Daten der Büroseite „Zeiten“ (seit 1.9.95, Stufe 4, R5b): Prüfen, Buchungen, Monat & Lohn.

Der Server rechnet, die Seite zeigt nur: Summen über tagessumme() (dieselbe Rechnung wie Stundenzettel, Übersicht und DATEV-Export, eine
laufende Zeit zählt nicht mit), ob die Pause eines Tags passt über pausen_vorschau() (über unpassende_pausen(), dieselbe Liste, die den
Abschluss sperrt), was den Abschluss sperrt über abschluss_hindernisse(), was dem DATEV-Export fehlt über datev_fehlt(). Rollenlos wie jede
Geschäftslogik -- was das Konto darf (Knöpfe, „Ende eintragen“), entscheidet der Router (app/routers/zeiten.py)."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import AppUser, AuditLog, Employee, EmployeePayrollSettings, Order, TimeEntry, TimeEntryGroup, TimeEntryGroupMember
from .permissions import MOBIL_ROLLEN
from .rounding import round_hours
from .time_backoffice import (_entry_type_labels, abschluss_hindernisse, datev_fehlt, effective_datev_personnel_number, load_employee_payroll,
                              load_time_settings, unpassende_pausen)
from .time_tracking import auftrag_geschlossen, employee_name, entry_to_dict, laeuft_seit_frueher, list_entries, tagessumme

MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember")

# Die Spalten von „Stunden je Mitarbeiter“ (Monat & Lohn) -- Schlechtwetter Winter und Sommer zusammen, „Sonstige“ (die Zeitart other und
# jede ohne eigene Spalte) nur, wenn es dort Stunden gibt
SPALTEN = (("site", "Baustelle"), ("travel", "Fahrzeit"), ("workshop", "Werkstatt"), ("weather", "Schlechtwetter"))
SPALTE_JE_ZEITART = {"site": "site", "travel": "travel", "workshop": "workshop", "weather_winter": "weather", "weather_summer": "weather"}


def monat_lesen(text: str | None, heute: date) -> date:
    """„JJJJ-MM“ -> der Erste des Monats; leer -> der Monat von heute. Sonst ValueError (der Router antwortet 422)."""
    if not text:
        return heute.replace(day=1)
    try:
        jahr, monat = (int(x) for x in text.split("-"))
        return date(jahr, monat, 1)
    except (ValueError, TypeError):
        raise ValueError("Monat bitte als JJJJ-MM angeben.") from None


def monat_ende(erster: date) -> date:
    return (erster.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def monat_text(erster: date) -> str:
    return f"{erster:%Y-%m}"


def monat_titel(erster: date) -> str:
    return f"{MONATE[erster.month - 1]} {erster.year}"


def _monat_kopf(erster: date) -> dict:
    vorher = (erster - timedelta(days=1)).replace(day=1)
    nachher = monat_ende(erster) + timedelta(days=1)
    return {"monat": monat_text(erster), "titel": monat_titel(erster), "start": erster, "ende": monat_ende(erster),
            "vorher": monat_text(vorher), "nachher": monat_text(nachher)}


def _status(erster: date, abgeschlossen_bis: date | None) -> str:
    """abgeschlossen (bis zum Monatsende), teilweise (der Abschluss liegt im Monat) oder offen."""
    if abgeschlossen_bis is not None and abgeschlossen_bis >= monat_ende(erster):
        return "abgeschlossen"
    if abgeschlossen_bis is not None and abgeschlossen_bis >= erster:
        return "teilweise"
    return "offen"


def pruef_monat(db: Session, heute: date) -> date:
    """Der Monat rechts auf „Prüfen“: der erste noch nicht ganz abgeschlossene -- der Monat nach „Abgeschlossen bis“, höchstens der von
    heute; ohne Abschluss der Monat von heute."""
    lock = load_time_settings(db).locked_until
    if lock is None:
        return heute.replace(day=1)
    return min((lock + timedelta(days=1)).replace(day=1), heute.replace(day=1))


def pruef_beginn(db: Session, heute: date) -> date:
    """Ab wann „Prüfen“ die Pausen der Tage prüft: der Tag nach „Abgeschlossen bis“, ohne Abschluss der Erste des Monats von heute --
    dieselbe Grenze wie abschluss_hindernisse()."""
    lock = load_time_settings(db).locked_until
    return lock + timedelta(days=1) if lock is not None else heute.replace(day=1)


def _auftrag(order: Order | None) -> dict:
    if order is None:
        return {"order_id": None, "order_number": None, "title": None, "auftrag_geschlossen": None}
    return {"order_id": order.id, "order_number": order.order_number, "title": order.title,
            "auftrag_geschlossen": auftrag_geschlossen(order.status)}


def _laufende_gruppen(db: Session, entry_ids: list[int]) -> set[int]:
    """Welche dieser Buchungen gehören zu einer laufenden Gruppe (Kolonne mit Timer)?"""
    if not entry_ids:
        return set()
    abfrage = (select(TimeEntryGroupMember.time_entry_id).join(TimeEntryGroup, TimeEntryGroup.id == TimeEntryGroupMember.group_id)
               .where(TimeEntryGroupMember.time_entry_id.in_(entry_ids), TimeEntryGroup.status == "running"))
    return set(db.scalars(abfrage).all())


def offene_zeiten(db: Session, heute: date) -> list[dict]:
    """Jede Zeit, die seit einem früheren Tag läuft (laeuft_seit_frueher()) -- aller Personen, die älteste zuerst. Je Zeit Person, Beginn,
    Zeitart, Auftrag (Nummer · Titel, Kennzeichen), ob sie zu einer laufenden Gruppe gehört."""
    rows = db.scalars(select(TimeEntry).options(selectinload(TimeEntry.employee), selectinload(TimeEntry.order))
                      .where(TimeEntry.status == "running", TimeEntry.started_at.is_not(None))
                      .order_by(TimeEntry.started_at, TimeEntry.id)).all()
    rows = [r for r in rows if laeuft_seit_frueher(r, heute)]
    namen = _entry_type_labels(db)
    gruppe = _laufende_gruppen(db, [r.id for r in rows])
    return [{"id": r.id, "employee_id": r.employee_id, "name": employee_name(r.employee) or f"#{r.employee_id}", "seit": r.started_at,
             "tag": r.work_date, "entry_type": r.entry_type, "zeitart": namen.get(r.entry_type, r.entry_type), "gruppe": r.id in gruppe,
             **_auftrag(r.order)} for r in rows]


def pausen_tage(db: Session, ab: date, bis: date) -> list[dict]:
    """Die Tage mit unpassender Pause zwischen ab und bis (unpassende_pausen()) -- je Tag Person, abgezogen und nach Zeitregel (Minuten)
    und die Vorschau von „Pausen neu rechnen“ je Buchung, deren Pause sich ändert: Zeitart, Von–Bis, Pause und gebucht alt -> neu. „So
    buchen“ schickt genau diese Vorschau (POST /api/time-entries/pausen-neu-rechnen)."""
    namen = _entry_type_labels(db)
    tage = []
    for employee_id, tag, stand in unpassende_pausen(db, ab, bis):
        zeilen = {r.id: r for r in db.scalars(select(TimeEntry).where(TimeEntry.id.in_([b["id"] for b in stand["buchungen"]]))).all()}
        buchungen = []
        for b in stand["buchungen"]:
            r = zeilen.get(b["id"])
            buchungen.append({**b, "entry_type": r.entry_type if r else None, "zeitart": namen.get(r.entry_type, r.entry_type) if r else None,
                              "von": r.started_at if r else None, "bis": r.ended_at if r else None})
        tage.append({"employee_id": employee_id, "name": employee_name(db.get(Employee, employee_id)) or f"#{employee_id}", "tag": tag,
                     "abgezogen": stand["abgezogen"], "nach_zeitregel": stand["nach_zeitregel"], "buchungen": buchungen})
    return tage


def arbeitstage(start: date, ende: date) -> int:
    """Montag bis Freitag zwischen start und ende ohne die gesetzlichen Feiertage in Nordrhein-Westfalen -- „8 Arbeitstage“ am Antrag. Seit
    1.9.105 (Nachrunde, Punkt 6) über die Feiertagsrechnung der Plantafel (app/planning.py::automatic_public_holidays(), fest „NW“, ohne
    betriebsfreie Tage); bis 1.9.104 Montag bis Freitag ohne Feiertage. Nur Anzeige: die Zahl wird nirgends gespeichert oder verrechnet."""
    from .planning import automatic_public_holidays  # lokal: planning lädt viel, „Zeiten“ braucht es nur hier

    feiertage = automatic_public_holidays("NW", range(start.year, ende.year + 1))
    tage = (start + timedelta(days=i) for i in range((ende - start).days + 1))
    return sum(1 for tag in tage if tag.weekday() < 5 and tag not in feiertage)


def monat_stunden(db: Session, erster: date) -> dict:
    """Stunden je Mitarbeiter im Monat (Tage, Stunden) und die Summen Gebucht und Fahrzeit -- über tagessumme(), eine laufende Zeit zählt
    nicht mit (wie Stundenzettel und DATEV-Export); wer im Monat nur eine laufende Zeit hat, steht nicht in der Liste. Für „Prüfen“ (rechts)."""
    rows = list_entries(db, start_date=erster, end_date=monat_ende(erster), limit=None)
    je = defaultdict(list)
    for r in rows:
        je[r.employee_id].append(r)
    mitarbeiter = []
    for employee_id, eigene in je.items():
        gebucht = [r for r in eigene if r.status == "booked"]
        if not gebucht:
            continue
        mitarbeiter.append({"employee_id": employee_id, "name": employee_name(eigene[0].employee) or f"#{employee_id}",
                            "tage": len({r.work_date for r in gebucht}), "stunden": round_hours(tagessumme(eigene))})
    mitarbeiter.sort(key=lambda x: x["name"].casefold())
    return {"gebucht": round_hours(tagessumme(rows)), "fahrzeit": round_hours(tagessumme([r for r in rows if r.entry_type == "travel"])),
            "mitarbeiter": mitarbeiter, "rows": rows}


def _anzahl(n: int, eins: str, mehr: str) -> str:
    return f"{n} {eins if n == 1 else mehr}"


def luecken_text(luecken: list[dict]) -> str:
    """„2 laufende Zeiten, 1 Pause“ -- die Zeile „Fehlt: …“ unter „Abschließen“ (nur Lücken der Zeiten)."""
    laeuft = sum(1 for x in luecken if x["art"] == "laeuft")
    pause = sum(1 for x in luecken if x["art"] == "pause")
    teile = ([_anzahl(laeuft, "laufende Zeit", "laufende Zeiten")] if laeuft else []) + ([_anzahl(pause, "Pause", "Pausen")] if pause else [])
    return ", ".join(teile)


def datev_text(fehlt: list[dict]) -> str:
    """„1 Personalnummer, 1 Lohnart, DATEV-Nummern“ -- die Zeile „Fehlt: …“ bei „DATEV-Export“."""
    pnr = sum(1 for x in fehlt if x["art"] == "personalnummer")
    lohnart = sum(1 for x in fehlt if x["art"] == "lohnart")
    teile = ([_anzahl(pnr, "Personalnummer", "Personalnummern")] if pnr else []) + \
            ([_anzahl(lohnart, "Lohnart", "Lohnarten")] if lohnart else []) + \
            (["DATEV-Nummern"] if any(x["art"] == "datev_nummern" for x in fehlt) else [])
    return ", ".join(teile)


def vor_dem_abschluss(db: Session, erster: date) -> list[dict]:
    """„Vor dem Abschluss“ auf „Prüfen“: die Lücken der Zeiten als Zahl (wie viele laufen, wie viele Tage passen nicht) und was dem
    DATEV-Export des Monats fehlt, je ein Eintrag mit art und text."""
    luecken = [] if _status(erster, load_time_settings(db).locked_until) == "abgeschlossen" else abschluss_hindernisse(db, monat_ende(erster))
    laeuft = sum(1 for x in luecken if x["art"] == "laeuft")
    pause = sum(1 for x in luecken if x["art"] == "pause")
    liste = ([{"art": "laeuft", "text": _anzahl(laeuft, "Zeit läuft noch", "Zeiten laufen noch")}] if laeuft else []) + \
            ([{"art": "pause", "text": _anzahl(pause, "Tag mit unpassender Pause", "Tage mit unpassender Pause")}] if pause else [])
    return liste + [{"art": x["art"], "text": x["text"]} for x in datev_fehlt(db, erster, monat_ende(erster))]


def pruefen(db: Session, heute: date) -> dict:
    """„Prüfen“: Zeiten von früher, Tage mit unpassender Pause (seit pruef_beginn()), der Monat mit Stunden je Mitarbeiter und „Vor dem
    Abschluss“. Die Anträge gibt der Router dazu (wer sie sieht, hängt am Konto)."""
    erster = pruef_monat(db, heute)
    lock = load_time_settings(db).locked_until
    stunden = monat_stunden(db, erster)
    stunden.pop("rows")
    return {"heute": heute, "offene_zeiten": offene_zeiten(db, heute), "pausen": pausen_tage(db, pruef_beginn(db, heute), heute),
            "monat": {**_monat_kopf(erster), "status": _status(erster, lock), "abgeschlossen_bis": lock, **stunden},
            "vor_dem_abschluss": vor_dem_abschluss(db, erster)}


# Seit 1.9.104 (Nachrunde, Punkte 5 und 6): was die Liste „Buchungen“ aus dem Verlauf (audit_logs) liest -- wer gebucht und wer zuletzt geändert
# hat (Unterzeile des Dialogs) und wer die Zeit zuletzt gesetzt hat (Stunden, Uhrzeiten, Tag, Pause; für „Dauer · vom Büro“). Eine Anfrage: die
# Einträge desselben Pfads mit höchstens 5 Sekunden Abstand (wie scripts/pruefabfrage_kolonne_weit.sql).
ZEIT_FELDER = frozenset({"hours", "started_at", "ended_at", "work_date", "break_minutes"})
GLEICHE_ANFRAGE = timedelta(seconds=5)


def _verlauf_der_buchungen(db: Session, rows: list[TimeEntry]) -> dict[int, dict]:
    """Je Buchung aus dem Verlauf (nur lesen, eine Abfrage je 500 Buchungen):
    - gebucht_von/gebucht_am: wer sie gebucht hat und wann -- bei einer gestoppten Zeit, wer sie beendet hat (Status läuft -> gebucht), sonst wer
      sie angelegt hat; ohne Konto im Verlauf (Testdaten, Skripte) der Anleger der Buchung, ohne ihn kein Name;
    - geaendert_von/geaendert_am: die letzte Änderung danach, ohne die Anfrage, die gebucht hat;
    - vom_buero: ob das Konto, das die Zeit zuletzt gesetzt hat (Stunden, Uhrzeiten, Tag, Pause), außerhalb der Monteursansicht arbeitet --
      ohne solche Änderung (oder ohne Konto im Verlauf) der Anleger. „Dauer · vom Büro“ zeigt die Seite für Buchungen ohne Uhrzeiten danach."""
    eintraege: dict[int, list] = defaultdict(list)
    ids = [str(r.id) for r in rows]
    for i in range(0, len(ids), 500):
        abfrage = (select(AuditLog.entity_id, AuditLog.field_name, AuditLog.old_value, AuditLog.new_value, AuditLog.occurred_at,
                          AuditLog.actor_name, AuditLog.actor_user_id, AuditLog.request_path, AuditLog.request_method)
                   .where(AuditLog.entity_type == "Zeitbuchung", AuditLog.action == "geändert", AuditLog.entity_id.in_(ids[i:i + 500]))
                   .order_by(AuditLog.occurred_at, AuditLog.id))
        for z in db.execute(abfrage):
            if z.entity_id.isdigit():
                eintraege[int(z.entity_id)].append(z)
    konten = {z.actor_user_id for zs in eintraege.values() for z in zs if z.actor_user_id} | {r.created_by_user_id for r in rows if r.created_by_user_id}
    rollen = {u.id: u.role for u in db.scalars(select(AppUser).where(AppUser.id.in_(konten)))} if konten else {}

    def ausserhalb(konto_id) -> bool:
        return konto_id in rollen and rollen[konto_id] not in MOBIL_ROLLEN

    out = {}
    for r in rows:
        zs = eintraege.get(r.id, [])
        anleger = (r.created_by.display_name or r.created_by.username) if r.created_by else None
        gebucht = next((z for z in zs if z.field_name == "status" and z.old_value == "running" and z.new_value == "booked"), None)
        if gebucht is not None:
            von, am = (gebucht.actor_name if gebucht.actor_user_id else anleger), gebucht.occurred_at
        else:
            von, am = anleger, r.created_at

        def zur_buchung(z) -> bool:
            return gebucht is not None and z.request_path == gebucht.request_path and z.request_method == gebucht.request_method \
                and abs(z.occurred_at - gebucht.occurred_at) <= GLEICHE_ANFRAGE

        danach = [z for z in zs if not zur_buchung(z) and (gebucht is None or z.occurred_at > gebucht.occurred_at)]
        geaendert = danach[-1] if danach else None
        gesetzt = [z for z in zs if z.field_name in ZEIT_FELDER and z.actor_user_id]
        out[r.id] = {"gebucht_von": von, "gebucht_am": am,
                     "geaendert_von": geaendert.actor_name if geaendert is not None else None,
                     "geaendert_am": geaendert.occurred_at if geaendert is not None else None,
                     "vom_buero": ausserhalb(gesetzt[-1].actor_user_id if gesetzt else r.created_by_user_id)}
    return out


def reihenfolge(r: TimeEntry) -> tuple:
    """Seit 1.9.103 (Nachrunde, Punkt 2) die Reihenfolge der Liste „Buchungen“ wie die Vorlage: Datum absteigend, im Tag nach Mitarbeiter (Name),
    dann Von aufsteigend, eine Dauer (ohne Von) zuletzt -- bis 1.9.102 die neuesten zuerst (12:00–16:15 vor 07:00–12:00)."""
    return (-r.work_date.toordinal(), (employee_name(r.employee) or "").casefold(), r.employee_id, r.started_at is None,
            r.started_at or datetime.min, r.id)


def buchungen(db: Session, erster: date, *, employee_id: int | None = None, order_id: int | None = None, entry_type: str | None = None) -> dict:
    """„Buchungen“: die Buchungen des Monats nach den Filtern (Mitarbeiter, Auftrag, Zeitart, mit UND verknüpft) in der Reihenfolge der
    Vorlage (reihenfolge()), und die „Summe der Auswahl“ über genau diese Zeilen (tagessumme(): eine laufende Zeit zählt nicht mit). Dazu die
    Auswahl der Filter: jeder aktive Mitarbeiter und jeder, der im Monat gebucht hat; jeder Auftrag des Monats (und der gefilterte); die
    Zeitarten."""
    ende = monat_ende(erster)
    alle = list_entries(db, start_date=erster, end_date=ende, limit=None)
    rows = sorted((r for r in alle if (employee_id is None or r.employee_id == employee_id) and (order_id is None or r.order_id == order_id)
                   and (entry_type is None or r.entry_type == entry_type)), key=reihenfolge)
    namen = _entry_type_labels(db)
    verlauf = _verlauf_der_buchungen(db, rows)
    heute_zeilen = []
    for r in rows:
        d = entry_to_dict(r)
        d["zeitart"] = namen.get(r.entry_type, r.entry_type)
        # seit 1.9.104 aus dem Verlauf: gebucht/geändert von … am … (Unterzeile des Dialogs) und vom_buero -- „Dauer · vom Büro“, wenn ein Konto
        # außerhalb der Monteursansicht die Zeit zuletzt gesetzt hat, auch an einer Buchung der Monteurin (bis 1.9.103 nur, wer sie angelegt hatte)
        d.update(verlauf[r.id])
        heute_zeilen.append(d)
    leute = {e.id: employee_name(e) for e in db.scalars(select(Employee).where(Employee.active == True)).all()}  # noqa: E712
    for r in alle:
        leute.setdefault(r.employee_id, employee_name(r.employee) or f"#{r.employee_id}")
    auftraege = {r.order_id: r.order for r in alle if r.order is not None}
    if order_id is not None and order_id not in auftraege:
        gefiltert = db.get(Order, order_id)
        if gefiltert is not None:
            auftraege[order_id] = gefiltert
    zeitarten = dict(namen)
    for r in alle:
        zeitarten.setdefault(r.entry_type, r.entry_type)
    return {**_monat_kopf(erster), "status": _status(erster, load_time_settings(db).locked_until),
            "eintraege": heute_zeilen, "summe": round_hours(tagessumme(rows)), "laufend": sum(1 for r in rows if r.status == "running"),
            "filter": {
                "mitarbeiter": sorted(({"id": i, "name": n} for i, n in leute.items()), key=lambda x: (x["name"] or "").casefold()),
                "auftraege": [{"id": o.id, **_auftrag(o)} for o in sorted(auftraege.values(), key=lambda o: o.order_number or "", reverse=True)],
                "zeitarten": [{"value": k, "label": v} for k, v in zeitarten.items()],
            }}


def monat(db: Session, erster: date) -> dict:
    """„Monat & Lohn“: Status und Abschluss, die Lücken der Zeiten (abschluss_hindernisse() bis zum Monatsende -- sperren das Abschließen),
    was dem DATEV-Export fehlt (datev_fehlt() -- sperrt den Export, nicht den Abschluss) und die Stunden je Mitarbeiter und Zeitart mit
    Personalnummer (dieselbe Summe wie Stundenzettel und DATEV-Export)."""
    settings = load_time_settings(db)
    lock = settings.locked_until
    ende = monat_ende(erster)
    status = _status(erster, lock)
    luecken = [] if status == "abgeschlossen" else abschluss_hindernisse(db, ende)
    fehlt = datev_fehlt(db, erster, ende)
    rows = [r for r in list_entries(db, start_date=erster, end_date=ende, limit=None)]
    je = defaultdict(list)
    for r in rows:
        je[r.employee_id].append(r)
    payroll = {x.employee_id: x for x in db.scalars(select(EmployeePayrollSettings)).all()}
    zeilen, summe = [], defaultdict(Decimal)
    sonstige = False
    for employee_id, eigene in je.items():
        if not any(r.status == "booked" for r in eigene):
            continue  # nur eine laufende Zeit -- keine Stunden im Monat
        emp = eigene[0].employee
        p = payroll.get(employee_id) or load_employee_payroll(db, employee_id)
        je_spalte = defaultdict(list)
        for r in eigene:
            je_spalte[SPALTE_JE_ZEITART.get(r.entry_type, "other")].append(r)
        stunden = {k: round_hours(tagessumme(v)) for k, v in je_spalte.items()}
        sonstige = sonstige or stunden.get("other", Decimal("0")) != 0
        for k, v in stunden.items():
            summe[k] += v
        zusammen = round_hours(tagessumme(eigene))
        summe["zusammen"] += zusammen
        zeilen.append({"employee_id": employee_id, "name": employee_name(emp) or f"#{employee_id}",
                       "personalnummer": effective_datev_personnel_number(db, emp, p) if emp is not None else None,
                       "lohnexport": bool(p.payroll_export_enabled),
                       "tage": len({r.work_date for r in eigene if r.status == "booked"}),
                       "stunden": {k: stunden.get(k, Decimal("0")) for k, _ in SPALTEN + (("other", ""),)}, "zusammen": zusammen})
    zeilen.sort(key=lambda x: x["name"].casefold())
    spalten = [{"key": k, "label": label} for k, label in SPALTEN] + ([{"key": "other", "label": "Sonstige"}] if sonstige else [])
    from .absence_requests import list_requests
    return {**_monat_kopf(erster), "status": status, "abgeschlossen_bis": lock, "abgeschlossen_am": settings.locked_at,
            "luecken": luecken, "luecken_text": luecken_text(luecken), "datev_fehlt": fehlt, "datev_text": datev_text(fehlt),
            "antraege_offen": len(list_requests(db, status="pending")),
            "spalten": spalten, "zeilen": zeilen,
            "summe": {"stunden": {k: summe.get(k, Decimal("0")) for k, _ in SPALTEN + (("other", ""),)}, "zusammen": summe["zusammen"]}}
