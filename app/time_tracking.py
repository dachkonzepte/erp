from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import and_, case, select, func, or_
from sqlalchemy.orm import Session, selectinload

from .berlin_time import berlin_now, berlin_today
from .meldungen import AUFTRAG_ABGESCHLOSSEN_ZEITEN, AUFTRAG_STORNIERT_ZEITEN, KEIN_MITARBEITER
from .option_settings import get_option_group
from .models import (
    Employee, Order, OrderItem, Project, TimeEntry, Team, TeamEmployee,
    TimeEntryGroup, TimeEntryGroupMember,
)

from .rounding import round_half_up, round_hours
from .work_time_models import automatic_break_minutes_for_duration

ENTRY_TYPES = {"site", "workshop", "travel", "other"}
# Zeitarten, die NIE als produktiv gelten -- travel (Fahrzeit) sowie die beiden Schlechtwetter-
# Zeitarten (Winter/Sommer, siehe app/option_settings.py::DEFAULT_OPTION_GROUPS["time_entry_types"]):
# an einem Schlechtwettertag wird nicht gearbeitet, unabhängig davon, ob er einem Kundenauftrag
# zugeordnet werden musste (TimeEntry.order_id ist NOT NULL). Eine spätere, frei gepflegte
# Zeitart (nicht in ENTRY_TYPES) gilt dagegen standardmäßig als produktiv, wie bisher.
NON_PRODUCTIVE_ENTRY_TYPES = {"travel", "weather_winter", "weather_summer"}


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


def gebucht_nach_zeitregel(db: Session, stunden) -> Decimal:
    """Seit 1.9.39 (Stufe 4, R1 Nachrunde, Punkt 2): die gebuchten Stunden nach der Rundung der Zeitregeln (Zeiterfassungs-Backoffice,
    rounding_minutes) -- die eine Stelle für jede neue Buchung: Stopp, Gruppen-Stopp und Stopp im Gruppenfall (je Mitglied), Nachtrag,
    Gruppen-Nachtrag (je Mitglied), Ende nachtragen (einzeln und für die Gruppe). Ohne eingestellte Rundung bleibt der Wert, wie er ist
    (gespeichert mit vier Nachkommastellen). Bis 1.9.38 rundeten nur Einzel-Stopp und Einzel-Nachtrag (im Router), der Stopp im
    Gruppenfall nur die Zeit dessen, der stoppte, Gruppen-Stopp und Gruppen-Nachtrag gar nicht. Ändern mit Dauer rundet nicht (wie
    bisher); Ändern mit Von/Bis (seit 1.9.57) und „Pausen neu rechnen“ runden hier wie ein Nachtrag."""
    from .time_backoffice import load_time_settings, rounded_hours  # lokal: time_backoffice importiert dieses Modul
    schritt = load_time_settings(db).rounding_minutes
    wert = _d(stunden)
    return rounded_hours(wert, schritt) if schritt else wert


def employee_name(emp: Employee | None) -> str | None:
    return f"{emp.first_name} {emp.last_name}".strip() if emp else None


def entry_type_is_productive(entry_type: str) -> bool:
    return entry_type not in NON_PRODUCTIVE_ENTRY_TYPES


def compute_hours(started_at: datetime, ended_at: datetime, break_minutes: int = 0) -> Decimal:
    if ended_at <= started_at:
        raise ValueError("Endzeit muss nach der Startzeit liegen.")
    seconds = Decimal(str((ended_at - started_at).total_seconds()))
    net = seconds / Decimal("3600") - Decimal(max(0, int(break_minutes or 0))) / Decimal("60")
    if net <= 0:
        raise ValueError("Die Netto-Arbeitszeit muss größer als 0 sein.")
    return net.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


class OffeneZeit(ValueError):
    """Seit 1.9.35 (Stufe 4, R1, Punkt 2): eine Zeit läuft seit einem früheren Tag -- erst „Ende nachtragen“, dann neu starten (409)."""


def laeuft_seit_frueher(row: TimeEntry | None, heute: date | None = None) -> bool:
    """Seit 1.9.35: läuft diese Zeit seit einem früheren Tag (Berliner Datum)? Dann stoppt sie kein „Zeit stoppen“ (das buchte sie bis
    jetzt auf den Starttag), nur „Ende nachtragen“ -- nichts schließt sie von selbst, kein Abschluss um Mitternacht, kein Hintergrundjob."""
    return bool(row is not None and row.status == "running" and row.started_at is not None
                and row.started_at.date() < (heute or berlin_today()))


def auftrag_geschlossen(status: str | None) -> str | None:
    """Seit 1.9.86 (Stufe 4, R5): "abgeschlossen" oder "storniert" (Groß- und Kleinschreibung, Leerraum egal), sonst None -- das
    Kennzeichen an Einsatz, Buchung und Vorwahl („Auftrag abgeschlossen“); dieselbe Regel wie auftrag_zeiten_gesperrt()."""
    wert = (status or "").strip().lower()
    return wert if wert in ("abgeschlossen", "storniert") else None


def auftrag_zeiten_gesperrt(order) -> str | None:
    """Seit 1.9.81 (Stufe 4, R4 Nachtrag 3, B): ist der Auftrag abgeschlossen oder storniert, die Meldung dazu, sonst None. Rollenlos --
    gesperrt ist das Buchen dort nur für die Monteurin (app/routers/time_tracking.py::_require_order_open_for_field()), das Büro bucht
    wie bisher; die Seite des Auftrags zeigt der Monteurin statt „Zeit nachtragen“ diese Meldung."""
    zu = auftrag_geschlossen(order.status if order is not None else None)
    return {"abgeschlossen": AUFTRAG_ABGESCHLOSSEN_ZEITEN, "storniert": AUFTRAG_STORNIERT_ZEITEN}.get(zu)


def offene_zeit_von_frueher(db: Session, employee_id: int) -> TimeEntry | None:
    """Seit 1.9.35: die laufende Zeit dieser Person, wenn sie seit einem früheren Tag läuft."""
    row = active_entry(db, employee_id)
    return row if laeuft_seit_frueher(row) else None


ZEITART_NAMEN = {"site": "Baustellenzeit", "travel": "Fahrzeit", "workshop": "Werkstattzeit", "other": "Sonstige"}


def offene_zeit_info(db: Session, employee_id: int) -> dict | None:
    """Seit 1.9.35: für /mobil (GET /api/field-view/today) die Zeit, die seit einem früheren Tag läuft -- Start mit Datum, Zeitart,
    Auftrag; ob sie zu einer laufenden Gruppe gehört und ob die Person sie selbst schließen darf (eine Gruppenzeit nur der Kolonnenführer,
    der sie gestartet hat). Sonst None."""
    row = offene_zeit_von_frueher(db, employee_id)
    if row is None:
        return None
    arten = get_option_group(db, "time_entry_types")
    namen = {o.value: o.label for o in (arten.options if arten is not None else [])}
    gruppe = group_for_entry(db, row.id)
    gruppe_laeuft = gruppe is not None and gruppe.status == "running"
    selbst = (not gruppe_laeuft) or (gruppe.initiated_by_employee_id == employee_id
                                     and gruppe.team_id in crew_leader_team_ids(db, employee_id))
    return {
        "id": row.id, "started_at": row.started_at, "work_date": row.work_date, "entry_type": row.entry_type,
        "entry_type_label": namen.get(row.entry_type) or ZEITART_NAMEN.get(row.entry_type, row.entry_type),
        "order_id": row.order_id, "order_number": row.order.order_number if row.order is not None else None,
        "gruppe": gruppe_laeuft, "selbst_schliessen": selbst,
    }


def anwesend_stunden(beginn: datetime, ende: datetime) -> Decimal:
    """Seit 1.9.34: die Anwesenheit zwischen Beginn und Ende in Stunden (vor Abzug der Pause)."""
    return (Decimal(str((ende - beginn).total_seconds())) / Decimal("3600")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def buchungen_am_tag(db: Session, employee_id: int, tag: date, ohne_id: int | None = None) -> list[TimeEntry]:
    """Seit 1.9.48: die gebuchten Zeiten der Person an diesem Tag (work_date = Starttag), ohne laufende. Seit 1.9.57 ohne_id: der Tag
    ohne die alte Fassung einer Buchung, die gerade geändert wird (Stufe 4, R3)."""
    abfrage = select(TimeEntry).where(TimeEntry.employee_id == employee_id, TimeEntry.work_date == tag, TimeEntry.status == "booked")
    if ohne_id is not None:
        abfrage = abfrage.where(TimeEntry.id != ohne_id)
    return list(db.scalars(abfrage).all())


def _anwesend_der_buchung(row: TimeEntry) -> Decimal:
    """Anwesenheit einer gebuchten Zeit: aus Beginn und Ende, eine reine Dauer als Stunden + Pause (wie entry_to_dict())."""
    if row.started_at and row.ended_at and row.ended_at > row.started_at:
        return anwesend_stunden(row.started_at, row.ended_at)
    return _d(row.hours) + Decimal(int(row.break_minutes or 0)) / Decimal("60")


def _anwesend_summe(rows: list[TimeEntry]) -> Decimal:
    """Seit 1.9.53: die Anwesenheit mehrerer gebuchter Zeiten zusammen -- für die Pause des Tages und für „Tag zusammen“."""
    return sum((_anwesend_der_buchung(r) for r in rows), Decimal("0"))


def mindestpause_der_buchung(row: TimeEntry) -> int:
    """Seit 1.9.62 (Stufe 4, R3 Nachrunde): die eingetragene Mindestpause einer Buchung (TimeEntry.min_break_minutes) -- für
    „Pausen neu rechnen“ (nie darunter), die Vorbelegung von „Ändern“ und ein Ändern ohne neue Angabe. Eine Buchung von vor 1.9.62 hat
    keinen Wert: dort gilt die abgezogene Pause als Mindestpause, neu rechnen kann nur mehr Pause ergeben."""
    return max(0, int(row.min_break_minutes if row.min_break_minutes is not None else (row.break_minutes or 0)))


def pause_nach_zeitregel(db: Session, employee_id: int, anwesend, am: date, mindestpause: int = 0, ohne_id: int | None = None, *,
                         vorher: tuple[Decimal, int] | None = None) -> int:
    """Die EINE Pausenregel (seit 1.9.34) -- für Stopp, Gruppen-Stopp (je Mitglied), Ende nachtragen, den Nachtrag mit Von/Bis,
    Zeitart wechseln und die Vorschau. Seit 1.9.48 (Stufe 4, R2 Nachrunde, Entscheidung Tobias) je Tag: maßgeblich ist die Anwesenheit
    der Person am Tag `am` über alle gebuchten Zeiten samt der neuen (`anwesend`, Stunden); die Pflichtpause des Arbeitszeitmodells
    dafür (über 6 h 30 min, über 9 h 45 min -- „mehr als“ seit 1.9.48) minus die an diesem Tag schon abgezogenen Pausen ist, was dem
    Tag noch fehlt. Die neue Buchung bekommt das, höchstens ihre Anwesenheit, mindestens die eingegebene Pause („Zusätzliche Pause“ bleibt
    Mindestpause, keine Summe). Frühere Buchungen werden nie angefasst. Bis 1.9.46 je Buchung (zwei Buchungen à 5 h ohne Pause).
    Seit 1.9.57 ohne_id: beim Ändern zählt der Tag ohne die alte Fassung dieser Buchung; vorher = (Anwesenheit, abgezogene Pause) der
    früheren Buchungen statt der gespeicherten -- für pausen_vorschau(), die den Tag in seiner Reihenfolge nachrechnet."""
    if vorher is None:
        frueher = buchungen_am_tag(db, employee_id, am, ohne_id)
        anwesend_vorher, abgezogen = _anwesend_summe(frueher), sum(int(r.break_minutes or 0) for r in frueher)
    else:
        anwesend_vorher, abgezogen = vorher
    neu = Decimal(str(anwesend or 0))
    anwesend_tag = anwesend_vorher + neu
    fehlt = max(0, int(automatic_break_minutes_for_duration(db, employee_id, anwesend_tag, am) or 0) - abgezogen)
    # Minuten der neuen Buchung, kaufmännisch gerundet (die Anwesenheit kommt auf vier Stellen gerundet: 20 min = 0,3333 h)
    hoechstens = max(0, int((neu * 60).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    return max(0, int(mindestpause or 0), min(fehlt, hoechstens))


def nachtrag_nach_zeitregel(db: Session, *, employee_id: int, work_date: date, von: time, bis: time, mindestpause: int = 0,
                            ohne_id: int | None = None) -> dict:
    """Seit 1.9.34: ein Nachtrag mit Von/Bis (die Anwesenheit ist bekannt) nach der Pausenregel -- Rückgabe anwesend, pause, netto (vor
    der Rundung), beginn, ende. Eine reine Dauer ist dagegen gebuchte Arbeitszeit (netto) und bleibt, wie sie ist (wie „Stunden (netto)“
    im Büro). Seit 1.9.57 (Stufe 4, R3) auch gebucht (nach der Rundung der Zeitregeln), tag_zusammen und tag_buchungen -- dieselben
    Zahlen für die Vorschau des Dialogs „Zeit nachtragen“ und die Buchung; ohne_id: beim Ändern der Tag ohne die alte Fassung."""
    beginn, ende = datetime.combine(work_date, von), datetime.combine(work_date, bis)
    if ende <= beginn:
        raise ValueError("Bis muss nach Von liegen.")
    anwesend = anwesend_stunden(beginn, ende)
    pause = pause_nach_zeitregel(db, employee_id, anwesend, work_date, mindestpause, ohne_id)
    netto = anwesend - Decimal(pause) / Decimal("60")
    if netto <= 0:  # seit 1.9.48 auch, wenn die fehlende Pause des Tages den Nachtrag ganz aufzehrt
        raise ValueError("Nach Abzug der Pause bleibt keine Arbeitszeit.")
    frueher = buchungen_am_tag(db, employee_id, work_date, ohne_id)
    return {"anwesend": anwesend, "pause": pause, "netto": netto, "beginn": beginn, "ende": ende,
            "gebucht": gebucht_nach_zeitregel(db, netto), "tag_zusammen": _anwesend_summe(frueher) + anwesend,
            "tag_buchungen": len(frueher) + 1}


def kolonne_rechnen(db: Session, mitglieder: list[tuple[int, str, int | None, int]], *, work_date: date, von: time,
                    bis: time) -> dict[int, dict]:
    """Seit 1.9.63 (Stufe 4, R3 Nachrunde, Punkt 1, Entscheidung Tobias): eine Von/Bis-Angabe für die angehakten Mitglieder einer
    Kolonne -- je Mitglied (employee_id, Name, ohne_id: seine Buchung beim Ändern, Mindestpause) dieselbe Rechnung wie sein eigener
    Nachtrag (nachtrag_nach_zeitregel(): Pause aus seinem Tag, Rundung der Zeitregeln). Für Vorschau, Nachtrag und Ändern der Kolonne;
    ein Fehler nennt das Mitglied. Wer anders gearbeitet hat, wird einzeln nachgetragen."""
    if datetime.combine(work_date, bis) <= datetime.combine(work_date, von):
        raise ValueError("Bis muss nach Von liegen.")
    ergebnis: dict[int, dict] = {}
    for employee_id, name, ohne_id, mindestpause in mitglieder:
        try:
            werte = nachtrag_nach_zeitregel(db, employee_id=employee_id, work_date=work_date, von=von, bis=bis,
                                            mindestpause=mindestpause, ohne_id=ohne_id)
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from exc
        if werte["gebucht"] <= 0:
            raise ValueError(f"{name}: Nach der Rundung bleibt keine Arbeitszeit.")
        ergebnis[employee_id] = {**werte, "name": name, "mindestpause": max(0, int(mindestpause or 0))}
    return ergebnis


def ende_rechnen(db: Session, employee_id: int, beginn: datetime, ende: datetime, mindestpause: int = 0) -> dict:
    """Seit 1.9.44 (Stufe 4, R2): anwesend (Stunden), Pause (Minuten) und gebuchte Stunden einer Zeit von beginn bis ende -- die eine
    Rechnung für den Feierabend (Stopp, Gruppen-Stopp je Mitglied, Zeitart wechseln), Ende nachtragen und dessen Vorschau
    (ende_vorschau(), „Gebucht werden …“ auf /mobil). compute_hours() lehnt ein Ende vor dem Beginn ab."""
    anwesend = anwesend_stunden(beginn, ende)
    pause = pause_nach_zeitregel(db, employee_id, anwesend, beginn.date(), mindestpause)
    if ende > beginn and pause > max(0, int(mindestpause or 0)) and pause * 60 >= (ende - beginn).total_seconds():
        netto = Decimal("0")  # seit 1.9.48: die fehlende Pause des Tages zehrt die Zeit ganz auf -- sie wird trotzdem geschlossen
    else:
        netto = compute_hours(beginn, ende, pause)
    gebucht = gebucht_nach_zeitregel(db, netto)
    frueher = buchungen_am_tag(db, employee_id, beginn.date())
    return {"anwesend": anwesend, "pause": pause, "gebucht": gebucht,
            # „Tag zusammen“ seit 1.9.53: die Anwesenheit des Tages samt dieser, vor der Pause -- dieselbe Zahl, nach der die Pause
            # bemessen ist (bis 1.9.52 die gebuchten Stunden des Tages); dazu, wie viele Buchungen der Tag dann hat
            "tag_zusammen": _anwesend_summe(frueher) + anwesend, "tag_buchungen": len(frueher) + 1}


def tag_stand(db: Session, employee_id: int, tag: date) -> dict:
    """Seit 1.9.48 (Stufe 4, R2 Nachrunde): „Tag zusammen“ für die Antwort einer Buchung und die Zahl der Buchungen des Tages (die
    Seite zeigt „Tag zusammen“, wenn es mehr als eine ist). Seit 1.9.53 die Anwesenheit der Person an diesem Tag über alle gebuchten
    Zeiten (vor der Pause, wie die Pausenregel sie zählt) -- bis 1.9.52 die gebuchten Stunden."""
    rows = buchungen_am_tag(db, employee_id, tag)
    return {"tag_zusammen": _anwesend_summe(rows), "tag_buchungen": len(rows)}


class PausenVorschauVeraltet(ValueError):
    """Seit 1.9.57: „Pausen neu rechnen“ bucht nur genau die Vorschau, die die Seite gezeigt hat -- hat sich der Tag inzwischen
    geändert, 409 statt einer anderen Rechnung."""


def _reihenfolge_am_tag(rows: list[TimeEntry]) -> list[TimeEntry]:
    """Die gebuchten Zeiten eines Tags in der Reihenfolge des Tags: mit Beginn nach dem Beginn, reine Dauern danach."""
    return sorted(rows, key=lambda r: (r.started_at is None, r.started_at or datetime.min, r.id))


def pausen_vorschau(db: Session, employee_id: int, tag: date) -> dict:
    """Seit 1.9.57 (Stufe 4, R3, Punkt 5): passt die abgezogene Pause des Tags noch zur Zeitregel? Nach Ändern oder Löschen einer
    Buchung kann sie das nicht mehr -- nichts rechnet sie von selbst neu. „Nach Zeitregel“ ist, was die Regel den Buchungen in der
    Reihenfolge des Tags gäbe (wie pause_nach_zeitregel(): jede bekommt, was dem Tag noch fehlt, höchstens ihre Anwesenheit; seit 1.9.62
    mindestens ihre eingetragene Mindestpause, mindestpause_der_buchung() -- bis 1.9.61 ohne, eine bewusst längere Pause hieß „passt
    nicht“; über pause_nach_zeitregel(vorher=…), die eine Pausenregel). passt = die Summen sind gleich (eine andere Verteilung bei
    gleicher Summe passt). buchungen: je Buchung, deren Pause sich ändern würde, alt -> neu (Pause in Minuten, gebucht nach der Rundung
    der Zeitregeln). Seit 1.9.59: eine reine Dauer (ohne Uhrzeiten) ist gebuchte Arbeitszeit -- ihre Pause bleibt, wie sie ist; sie
    zählt mit Stunden + Pause vor den Buchungen mit Uhrzeiten zur Anwesenheit des Tags (wie beim Buchen). Bis dahin rechnete die Prüfung
    auch sie neu: ein Kolonnen-Nachtrag von 8 h hieß „nach Zeitregel 0:30 h“, „Pausen neu rechnen“ hätte 7,50 h gebucht. Seit 1.9.62
    heißt „passt nicht“ deshalb: neu rechnen würde etwas ändern (jede Buchung behält mindestens, was eingetragen ist)."""
    rows = _reihenfolge_am_tag(buchungen_am_tag(db, employee_id, tag))
    dauern = [r for r in rows if not (r.started_at and r.ended_at and r.ended_at > r.started_at)]
    anwesend_vorher, pause_vorher, plan = _anwesend_summe(dauern), sum(int(r.break_minutes or 0) for r in dauern), []
    for r in (r for r in rows if r not in dauern):
        anwesend = _anwesend_der_buchung(r)
        neu = pause_nach_zeitregel(db, employee_id, anwesend, tag, mindestpause_der_buchung(r), vorher=(anwesend_vorher, pause_vorher))
        alt = int(r.break_minutes or 0)
        if neu != alt:
            plan.append({"id": r.id, "pause_alt": alt, "pause_neu": neu, "gebucht_alt": _d(r.hours),
                         "gebucht_neu": gebucht_nach_zeitregel(db, max(Decimal("0"), anwesend - Decimal(neu) / Decimal("60")))})
        anwesend_vorher += anwesend
        pause_vorher += neu
    abgezogen = sum(int(r.break_minutes or 0) for r in rows)
    passt = abgezogen == pause_vorher
    return {"tag": tag, "abgezogen": abgezogen, "nach_zeitregel": pause_vorher, "passt": passt, "buchungen": [] if passt else plan}


def pausen_neu_rechnen(db: Session, employee_id: int, tag: date, erwartet: dict[int, int]) -> dict:
    """Seit 1.9.57: bucht genau die Vorschau von pausen_vorschau() -- erwartet = {Buchung: neue Pause}, wie die Seite sie gezeigt hat;
    weicht die Rechnung jetzt davon ab (der Tag hat sich geändert) oder passt der Tag schon, PausenVorschauVeraltet (409). Ändert nur
    Pause und gebuchte Stunden der genannten Buchungen (eine Buchung einer Gruppe gilt danach als einzeln geändert), dazu eine Zeile im
    Verlauf. Nie von selbst -- nur auf den Klick „Pausen neu rechnen“."""
    rows = db.scalars(select(TimeEntry).where(TimeEntry.employee_id == employee_id, TimeEntry.work_date == tag,
                                              TimeEntry.status == "booked").with_for_update()).all()
    vorschau = pausen_vorschau(db, employee_id, tag)
    plan = {b["id"]: b for b in vorschau["buchungen"]}
    if vorschau["passt"] or {i: b["pause_neu"] for i, b in plan.items()} != {int(k): int(v) for k, v in erwartet.items()}:
        db.rollback()
        raise PausenVorschauVeraltet("Die Pausen des Tages haben sich inzwischen geändert – bitte die Vorschau neu laden.")
    from .audit import record_audit_entry  # lokal: audit importiert die Modelle, dieses Modul wird früh geladen

    for r in rows:
        b = plan.get(r.id)
        if b is None:
            continue
        if r.min_break_minutes is None:  # seit 1.9.62: eine Buchung von vor 1.9.62 behält ihre bisherige Pause als Mindestpause
            r.min_break_minutes = int(r.break_minutes or 0)
        r.break_minutes, r.hours = b["pause_neu"], b["gebucht_neu"]
        link = _group_link_for_entry(db, r.id)
        if link is not None:
            _mark_individual_change(link)
    record_audit_entry(db, action="Pausen neu gerechnet", entity_type="Zeitbuchung", entity_id=f"{employee_id}/{tag.isoformat()}",
                       entity_label=f"{employee_name(db.get(Employee, employee_id)) or ''} · {tag:%d.%m.%Y}",
                       field_name="break_minutes", field_label="Pause des Tages (Minuten)",
                       old_value=vorschau["abgezogen"], new_value=vorschau["nach_zeitregel"])
    db.commit()
    return pausen_vorschau(db, employee_id, tag)


def load_entry(db: Session, entry_id: int) -> TimeEntry | None:
    return db.scalar(
        select(TimeEntry)
        .options(
            selectinload(TimeEntry.employee), selectinload(TimeEntry.order),
            selectinload(TimeEntry.project), selectinload(TimeEntry.order_item),
            selectinload(TimeEntry.created_by),
        )
        .where(TimeEntry.id == entry_id)
    )


def active_entry(db: Session, employee_id: int) -> TimeEntry | None:
    return db.scalar(
        select(TimeEntry)
        .options(selectinload(TimeEntry.order), selectinload(TimeEntry.project), selectinload(TimeEntry.order_item))
        .where(TimeEntry.employee_id == employee_id, TimeEntry.status == "running")
        .order_by(TimeEntry.started_at.desc())
    )


def validate_order_item(db: Session, order_id: int, order_item_id: int | None) -> OrderItem | None:
    if order_item_id is None:
        return None
    item = db.get(OrderItem, order_item_id)
    if item is None or item.order_id != order_id:
        raise ValueError("Die LV-Position gehört nicht zum ausgewählten Auftrag.")
    return item


def create_manual_entry(
    db: Session, *, employee_id: int, order_id: int, work_date: date,
    hours: Decimal, entry_type: str = "site", order_item_id: int | None = None,
    activity: str | None = None, notes: str | None = None,
    started_at: datetime | None = None, ended_at: datetime | None = None,
    break_minutes: int = 0, created_by_user_id: int | None = None, min_break_minutes: int | None = None,
) -> TimeEntry:
    """Seit 1.9.62: min_break_minutes = die eingetragene Mindestpause (der Nachtrag mit Von/Bis: „Pause mindestens“); ohne Angabe die
    Pause selbst (eine reine Dauer: die eingetragene Pause)."""
    employee = db.get(Employee, employee_id)
    order = db.get(Order, order_id)
    if employee is None or not employee.active:
        raise ValueError("Mitarbeiter wurde nicht gefunden oder ist inaktiv.")
    if order is None:
        raise ValueError("Auftrag wurde nicht gefunden.")
    validate_order_item(db, order_id, order_item_id)
    if entry_type not in ENTRY_TYPES:
        # frei gepflegte Typen bleiben möglich; nur travel ist nicht-produktiv
        entry_type = entry_type.strip() or "other"
    # Seit 1.9.34 sind die Stunden immer die gebuchten (netto): ein Nachtrag mit Von/Bis rechnet sie vorher nach der Pausenregel
    # (nachtrag_nach_zeitregel()) und gibt Beginn und Ende als Nachweis mit -- bis dahin rechnete diese Funktion sie selbst ohne Regel.
    # Seit 1.9.39 rundet sie hier nach den Zeitregeln (gebucht_nach_zeitregel(), bis dahin der Router)
    amount = gebucht_nach_zeitregel(db, hours)
    if amount <= 0:
        raise ValueError("Die Stunden müssen größer als 0 sein.")
    row = TimeEntry(
        employee_id=employee.id, project_id=order.project_id, order_id=order.id,
        order_item_id=order_item_id, work_date=work_date, entry_type=entry_type,
        counts_as_productive=entry_type_is_productive(entry_type), activity=(activity or None),
        started_at=started_at, ended_at=ended_at, break_minutes=max(0, int(break_minutes or 0)),
        min_break_minutes=max(0, int((break_minutes if min_break_minutes is None else min_break_minutes) or 0)),
        hours=amount, notes=(notes or None), source="manual", status="booked",
        created_by_user_id=created_by_user_id,
    )
    db.add(row); db.commit()
    return load_entry(db, row.id)


def start_timer(
    db: Session, *, employee_id: int, order_id: int, entry_type: str = "site",
    order_item_id: int | None = None, activity: str | None = None, notes: str | None = None,
    started_at: datetime | None = None, created_by_user_id: int | None = None,
) -> TimeEntry:
    laufend = active_entry(db, employee_id)
    if laufend is not None:
        if laeuft_seit_frueher(laufend):  # seit 1.9.35: kein neuer Start, solange eine Zeit von früher offen ist
            gruppe = group_for_entry(db, laufend.id)
            if gruppe is not None and gruppe.status == "running" and gruppe.initiated_by_employee_id != employee_id:
                raise OffeneZeit(f"Die Gruppenzeit vom {laufend.started_at:%d.%m.%Y} läuft noch – das Ende trägt der Kolonnenführer nach, "
                                 "dann kannst du neu starten.")
            raise OffeneZeit(f"Die Zeit vom {laufend.started_at:%d.%m.%Y} läuft noch – zuerst das Ende nachtragen, dann neu starten.")
        raise ValueError("Für diesen Mitarbeiter läuft bereits eine Zeiterfassung.")
    employee = db.get(Employee, employee_id); order = db.get(Order, order_id)
    if employee is None or not employee.active:
        raise ValueError("Mitarbeiter wurde nicht gefunden oder ist inaktiv.")
    if order is None:
        raise ValueError("Auftrag wurde nicht gefunden.")
    validate_order_item(db, order_id, order_item_id)
    start = started_at or berlin_now()
    row = TimeEntry(
        employee_id=employee.id, project_id=order.project_id, order_id=order.id,
        order_item_id=order_item_id, work_date=start.date(), entry_type=entry_type,
        counts_as_productive=entry_type_is_productive(entry_type), activity=(activity or None),
        started_at=start, ended_at=None, break_minutes=0, hours=Decimal("0"),
        notes=(notes or None), source="timer", status="running", created_by_user_id=created_by_user_id,
    )
    db.add(row); db.commit()
    return load_entry(db, row.id)


def stop_timer(db: Session, entry_id: int, *, ended_at: datetime | None = None, break_minutes: int = 0) -> TimeEntry:
    row = db.get(TimeEntry, entry_id)
    if row is None:
        raise ValueError("Laufende Zeiterfassung wurde nicht gefunden.")
    if row.status != "running" or row.started_at is None:
        raise ValueError("Diese Zeiterfassung läuft nicht mehr.")
    end = ended_at or berlin_now()
    row.ended_at = end
    if end > row.started_at:  # seit 1.9.44 über ende_rechnen() (dieselbe Rechnung wie die Vorschau)
        werte = ende_rechnen(db, row.employee_id, row.started_at, end, break_minutes)
        row.break_minutes, row.hours = werte["pause"], werte["gebucht"]
    else:
        row.break_minutes = max(0, int(break_minutes or 0))
        row.hours = compute_hours(row.started_at, end, row.break_minutes)  # lehnt das Ende ab
    row.status = "booked"
    row.min_break_minutes = max(0, int(break_minutes or 0))  # seit 1.9.62: die eingegebene Pause, ohne Eingabe 0
    link = _group_link_for_entry(db, row.id)
    if link is not None:
        group = db.get(TimeEntryGroup, link.group_id)
        if group is not None and group.status == "running":
            _mark_individual_change(link)  # vorzeitig einzeln gestoppt, die Gruppe läuft weiter
    db.commit()
    return load_entry(db, row.id)


def ende_nachtragen(db: Session, entry_id: int, *, ende: datetime, mindestpause: int = 0) -> TimeEntry:
    """Seit 1.9.35 (Stufe 4, R1, Punkt 2): das Ende einer Zeit, die seit einem früheren Tag läuft -- am Starttag und nach dem Start, die
    Pause nach derselben Regel wie beim Feierabend (pause_nach_zeitregel() über stop_timer()/stop_group_timer()). Gehört die Zeit zu einer
    laufenden Gruppe, schließt sie die Gruppe wie der Gruppen-Stopp. Nur auf Klick; Rechte, Abschluss und Kolonnenführer prüft der Router."""
    row = db.get(TimeEntry, entry_id)
    _ende_pruefen(row, ende)
    group = group_for_entry(db, entry_id)
    if group is not None and group.status == "running":
        stop_group_timer(db, group.id, ended_at=ende, break_minutes=mindestpause)
        return load_entry(db, entry_id)
    return stop_timer(db, entry_id, ended_at=ende, break_minutes=mindestpause)


def _ende_pruefen(row: TimeEntry | None, ende: datetime) -> None:
    if row is None or row.status != "running" or row.started_at is None:
        raise ValueError("Diese Zeit ist schon geschlossen.")
    if not laeuft_seit_frueher(row):
        raise ValueError("Diese Zeit läuft seit heute – bitte normal stoppen.")
    if ende.date() != row.started_at.date():
        raise ValueError(f"Das Ende muss am Starttag liegen ({row.started_at:%d.%m.%Y}).")
    if ende <= row.started_at:
        raise ValueError(f"Das Ende muss nach dem Start liegen ({row.started_at:%H:%M} Uhr).")


def ende_vorschau(db: Session, entry_id: int, *, ende: datetime, mindestpause: int = 0) -> dict:
    """Seit 1.9.44 (Stufe 4, R2): was ende_nachtragen() mit diesem Ende buchen würde -- anwesend, Pause, gebucht --, ohne zu buchen.
    Dieselbe Prüfung und dieselbe Rechnung (ende_rechnen() mit dem Beginn, den auch der Stopp nimmt: in einer laufenden Gruppe deren
    Beginn), für die Person dieser Zeit."""
    row = db.get(TimeEntry, entry_id)
    _ende_pruefen(row, ende)
    group = group_for_entry(db, entry_id)
    beginn = group.started_at if group is not None and group.status == "running" else row.started_at
    return ende_rechnen(db, row.employee_id, beginn, ende, mindestpause)


class ZeitartInGruppe(ValueError):
    """Seit 1.9.44: eine Gruppenzeit wechselt die Zeitart nicht (409) -- sie stoppt der Kolonnenführer für alle."""


def zeitart_wechseln(db: Session, entry_id: int, entry_type: str, *, jetzt: datetime | None = None,
                     created_by_user_id: int | None = None) -> TimeEntry:
    """Seit 1.9.44 (Stufe 4, R2): „Zeitart wechseln“ auf /mobil -- die laufende Zeit endet jetzt (wie der Feierabend, Pause nach der
    Zeitregel über ende_rechnen()), im selben Augenblick beginnt eine neue mit der neuen Zeitart auf demselben Auftrag (LV-Position und
    Tätigkeit wie bisher): keine Lücke, keine Überschneidung, ein Commit. Nicht für eine Zeit von früher (erst Ende nachtragen) und nicht
    für eine laufende Gruppenzeit."""
    row = db.get(TimeEntry, entry_id)
    if row is None or row.status != "running" or row.started_at is None:
        raise ValueError("Diese Zeiterfassung läuft nicht mehr.")
    if laeuft_seit_frueher(row):
        raise OffeneZeit(f"Die Zeit vom {row.started_at:%d.%m.%Y} läuft noch – zuerst das Ende nachtragen.")
    group = group_for_entry(db, entry_id)
    if group is not None and group.status == "running":
        raise ZeitartInGruppe("Eine Gruppenzeit wechselt die Zeitart nicht – Feierabend für die Gruppe macht der Kolonnenführer.")
    if entry_type == row.entry_type:
        raise ValueError("Diese Zeitart läuft schon.")
    jetzt = jetzt or berlin_now()
    werte = ende_rechnen(db, row.employee_id, row.started_at, jetzt)
    row.ended_at, row.break_minutes, row.hours, row.status = jetzt, werte["pause"], werte["gebucht"], "booked"
    row.min_break_minutes = 0  # seit 1.9.62: beim Wechsel wird keine Pause eingegeben
    neu = TimeEntry(
        employee_id=row.employee_id, project_id=row.project_id, order_id=row.order_id, order_item_id=row.order_item_id,
        work_date=jetzt.date(), entry_type=entry_type, counts_as_productive=entry_type_is_productive(entry_type), activity=row.activity,
        started_at=jetzt, ended_at=None, break_minutes=0, hours=Decimal("0"), notes=None, source="timer", status="running",
        created_by_user_id=created_by_user_id,
    )
    db.add(neu); db.commit()
    return load_entry(db, neu.id)


def _group_link_for_entry(db: Session, entry_id: int) -> TimeEntryGroupMember | None:
    return db.scalar(select(TimeEntryGroupMember).where(TimeEntryGroupMember.time_entry_id == entry_id))


def _mark_individual_change(link: TimeEntryGroupMember) -> None:
    """Seit 1.7.13: Merker "nach der Gruppenbuchung einzeln geändert" -- der erste Zeitpunkt bleibt
    stehen. Rollenlos: gilt für eine Änderung durch das Mitglied selbst wie durch einen Admin."""
    if link.individually_changed_at is None:
        link.individually_changed_at = datetime.utcnow()


def update_entry(
    db: Session, entry_id: int, *, employee_id: int, order_id: int, work_date: date,
    hours: Decimal, entry_type: str, order_item_id: int | None = None,
    activity: str | None = None, notes: str | None = None, break_minutes: int = 0,
    von: time | None = None, bis: time | None = None, mindestpause: int = 0, min_break_minutes: int | None = None,
    als_dauer: bool = False,
) -> TimeEntry:
    """Seit 1.9.57 (Stufe 4, R3) mit von/bis: dieselbe Rechnung wie ein Nachtrag (nachtrag_nach_zeitregel()) -- Pause aus dem Tag ohne
    die alte Fassung dieser Buchung, gebucht nach der Rundung der Zeitregeln, Beginn und Ende neu; hours und break_minutes zählen dann
    nicht. Andere Buchungen werden nie angefasst. Ohne von/bis: die Stunden zählen.
    Seit 1.9.62 die eingetragene Mindestpause: mit von/bis die dieses Ändern (mindestpause), sonst min_break_minutes, wenn angegeben (eine
    Dauer mit neuer Pause, Büro); ohne beides bleibt sie.
    Seit 1.9.90 (Stufe 4, R5a, Punkt 3): als_dauer (die Buchung wird als Dauer gespeichert -- Stunden, Pause oder Tag ohne von/bis) leert
    Beginn und Ende; bis 1.9.89 blieben sie als „Nachweis“ stehen und passten nicht mehr zu Stunden, Pause oder Tag."""
    row = db.get(TimeEntry, entry_id)
    if row is None:
        raise ValueError("Zeitbuchung wurde nicht gefunden.")
    if row.status == "running":
        raise ValueError("Eine laufende Zeiterfassung kann erst nach dem Stoppen bearbeitet werden.")
    employee = db.get(Employee, employee_id); order = db.get(Order, order_id)
    # Seit 1.8.31 muss nur ein neu eingetragener Mitarbeiter aktiv sein: die Buchung einer inzwischen
    # ausgeschiedenen Person ließ sich sonst nicht mehr korrigieren (422), auch ohne Personenwechsel.
    if employee is None or (employee_id != row.employee_id and not employee.active):
        raise ValueError("Mitarbeiter wurde nicht gefunden oder ist inaktiv.")
    if order is None: raise ValueError("Auftrag wurde nicht gefunden.")
    validate_order_item(db, order_id, order_item_id)
    if von is not None:
        werte = nachtrag_nach_zeitregel(db, employee_id=employee_id, work_date=work_date, von=von, bis=bis, mindestpause=mindestpause,
                                        ohne_id=row.id)
        amount, break_minutes = werte["gebucht"], werte["pause"]
        row.started_at, row.ended_at = werte["beginn"], werte["ende"]
    else:
        amount = _d(hours)
    if amount <= 0: raise ValueError("Die Stunden müssen größer als 0 sein.")
    if von is None and als_dauer:
        row.started_at = row.ended_at = None
    row.employee_id=employee_id; row.order_id=order_id; row.project_id=order.project_id
    row.order_item_id=order_item_id; row.work_date=work_date; row.hours=amount
    row.entry_type=entry_type; row.counts_as_productive=entry_type_is_productive(entry_type)
    row.activity=activity or None; row.notes=notes or None; row.break_minutes=max(0,int(break_minutes or 0))
    if von is not None:
        row.min_break_minutes = max(0, int(mindestpause or 0))
    elif min_break_minutes is not None:
        row.min_break_minutes = max(0, int(min_break_minutes))
    link = _group_link_for_entry(db, row.id)
    if link is not None:
        _mark_individual_change(link)
    db.commit()
    return load_entry(db, row.id)


def delete_entry(db: Session, entry_id: int) -> None:
    """Seit 1.7.11: entfernt vorher die Gruppen-Verknüpfung (TimeEntryGroupMember.time_entry_id ist
    ein Fremdschlüssel ohne Kaskade) -- sonst scheitert das Löschen eines per Gruppe gebuchten
    Eintrags unter PostgreSQL mit IntegrityError. Bleibt die Gruppe danach ohne Mitglied, wird auch
    ihr Kopf entfernt."""
    row = db.get(TimeEntry, entry_id)
    if row is None: raise ValueError("Zeitbuchung wurde nicht gefunden.")
    if row.status == "running": raise ValueError("Laufende Zeiterfassung zuerst stoppen.")
    link = db.scalar(select(TimeEntryGroupMember).where(TimeEntryGroupMember.time_entry_id == entry_id))
    if link is not None:
        group_id = link.group_id
        db.delete(link); db.flush()
        if db.scalar(select(TimeEntryGroupMember.id).where(TimeEntryGroupMember.group_id == group_id).limit(1)) is None:
            db.delete(db.get(TimeEntryGroup, group_id)); db.flush()
    db.delete(row); db.commit()


def tagessumme(rows) -> Decimal:
    """Die gebuchten Stunden mehrerer Zeiten -- eine laufende zählt nicht mit. Dieselbe Funktion für Kacheln, Tagessummen, Monat und den
    Stundenzettel als PDF der Monteurin (app/meine_zeiten.py, app/field_timesheet_pdf.py), seit 1.9.92 (Stufe 4, R5a, Punkt 5) auch für die
    Übersicht, den Stundenzettel und den DATEV-Export des Büros (app/time_backoffice.py) -- bis dahin in app/meine_zeiten.py; gerundet wird
    erst das Ergebnis (round_hours()), keine zweite Rundung."""
    return sum((Decimal(str(r.hours or 0)) for r in rows if r.status == "booked"), Decimal("0"))


def entry_to_dict(row: TimeEntry) -> dict:
    item = row.order_item
    return {
        "id": row.id, "employee_id": row.employee_id, "employee_name": employee_name(row.employee),
        "project_id": row.project_id, "project_number": row.project.project_number if row.project else None,
        "project_name": row.project.name if row.project else None,
        "order_id": row.order_id, "order_number": row.order.order_number if row.order else None,
        "order_title": row.order.title if row.order else None,
        "order_item_id": row.order_item_id,
        "order_item_oz": (item.gaeb_oz or item.position_number) if item else None,
        "order_item_text": item.short_text if item else None,
        "work_date": row.work_date, "entry_type": row.entry_type,
        "counts_as_productive": row.counts_as_productive, "activity": row.activity,
        "started_at": row.started_at, "ended_at": row.ended_at, "break_minutes": row.break_minutes,
        "min_break_minutes": row.min_break_minutes,  # seit 1.9.62: die eingetragene Mindestpause (leer: Buchung von vor 1.9.62)
        "hours": row.hours, "notes": row.notes, "source": row.source, "status": row.status,
        # seit 1.9.34 (Stufe 4, R1): anwesend (Stunden vor Abzug der Pause), Pause (Minuten), gebucht (Stunden) -- anwesend aus Beginn und
        # Ende, ohne beide (eine reine Dauer) gebucht + Pause; eine laufende Zeit hat noch keins
        **_anwesend_pause_gebucht(row),
        "laeuft_seit_frueher": laeuft_seit_frueher(row),  # seit 1.9.35: dann „Ende nachtragen“ statt „Zeit stoppen“
        # seit 1.9.90 (Stufe 4, R5a, Punkt 2): das Kennzeichen, wenn der Auftrag abgeschlossen oder storniert ist (das Büro bucht dort)
        "auftrag_geschlossen": auftrag_geschlossen(row.order.status) if row.order else None,
        "created_at": row.created_at,
        "booked_by_name": row.created_by.display_name if row.created_by else None,
        "booked_by_employee_id": row.created_by.employee_id if row.created_by else None,
    }


def _anwesend_pause_gebucht(row: TimeEntry) -> dict:
    if row.status == "running":
        return {"anwesend": None, "pause": None, "gebucht": None}
    if row.started_at and row.ended_at and row.ended_at > row.started_at:
        anwesend = anwesend_stunden(row.started_at, row.ended_at)
    else:
        anwesend = (_d(row.hours) + Decimal(int(row.break_minutes or 0)) / Decimal("60")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return {"anwesend": anwesend, "pause": int(row.break_minutes or 0), "gebucht": row.hours}


# Höchste Zeilenzahl je Abruf von list_entries() mit einer Zahl als limit, damit auch von
# GET /api/time-entries (seit 1.8.9 dort als Obergrenze des Parameters geprüft).
MAX_LIST_LIMIT = 2000


def _entry_filters(*, employee_id: int | None, project_id: int | None, order_id: int | None,
                   start_date: date | None, end_date: date | None) -> list:
    """Die Filter von list_entries(), count_entries() und summarize_entries() an einer Stelle --
    Liste, Gesamtzahl und Summen meinen dadurch immer dieselben Zeilen."""
    conds = []
    if employee_id is not None: conds.append(TimeEntry.employee_id==employee_id)
    if project_id is not None: conds.append(TimeEntry.project_id==project_id)
    if order_id is not None: conds.append(TimeEntry.order_id==order_id)
    if start_date is not None: conds.append(TimeEntry.work_date>=start_date)
    if end_date is not None: conds.append(TimeEntry.work_date<=end_date)
    return conds


def list_entries(
    db: Session, *, employee_id: int | None = None, project_id: int | None = None,
    order_id: int | None = None, start_date: date | None = None, end_date: date | None = None,
    limit: int | None,
) -> list[TimeEntry]:
    # limit ist seit 1.8.7 Pflicht: der frühere Vorgabewert 500 und die Kappung bei 2000 schnitten
    # Rechnung aus Aufwand, Einsatzbericht-PDF und Backoffice still ab. limit=None = ohne
    # Obergrenze, für Aufrufer, die fachlich jede Zeile brauchen. Seit 1.8.9 wird eine Zahl
    # außerhalb von 1..MAX_LIST_LIMIT abgelehnt, statt still auf 2000 gekappt zu werden.
    if limit is not None and not 1 <= limit <= MAX_LIST_LIMIT:
        raise ValueError(f"limit muss zwischen 1 und {MAX_LIST_LIMIT} liegen.")
    stmt = select(TimeEntry).options(
        selectinload(TimeEntry.employee), selectinload(TimeEntry.project),
        selectinload(TimeEntry.order), selectinload(TimeEntry.order_item), selectinload(TimeEntry.created_by),
    ).where(*_entry_filters(employee_id=employee_id, project_id=project_id, order_id=order_id, start_date=start_date, end_date=end_date)
    ).order_by(TimeEntry.work_date.desc(), TimeEntry.started_at.desc(), TimeEntry.id.desc())
    if limit is not None: stmt=stmt.limit(limit)
    return db.scalars(stmt).all()


def count_entries(
    db: Session, *, employee_id: int | None = None, project_id: int | None = None,
    order_id: int | None = None, start_date: date | None = None, end_date: date | None = None,
) -> int:
    """Seit 1.8.9: Gesamtzahl der Treffer von list_entries() mit denselben Filtern, ohne limit --
    GET /api/time-entries meldet sie in der Kopfzeile X-Total-Count."""
    filters = _entry_filters(employee_id=employee_id, project_id=project_id, order_id=order_id, start_date=start_date, end_date=end_date)
    return int(db.scalar(select(func.count(TimeEntry.id)).where(*filters)) or 0)


def summarize_entries(
    db: Session, *, employee_id: int | None = None, project_id: int | None = None,
    order_id: int | None = None, start_date: date | None = None, end_date: date | None = None,
) -> dict:
    """Seit 1.8.9: Summen über ALLE Treffer von list_entries() mit denselben Filtern, per SUM in
    der Datenbank -- vorher bildeten Einsatzbericht-Seite und Projektmappe sie in der Oberfläche
    aus einer auf 500 bzw. 1000 Zeilen gekürzten Liste. Stunden wie order_actual_hours() nur aus
    gebuchten Zeiten (ein laufender Timer trägt 0 Stunden)."""
    filters = _entry_filters(employee_id=employee_id, project_id=project_id, order_id=order_id, start_date=start_date, end_date=end_date)
    booked = TimeEntry.status=="booked"

    def booked_hours(*conds):
        return func.coalesce(func.sum(case((and_(booked, *conds), TimeEntry.hours), else_=0)), 0)

    entry_count, booked_count, total, productive, travel, employees = db.execute(select(
        func.count(TimeEntry.id),
        func.count(case((booked, TimeEntry.id))),
        booked_hours(),
        booked_hours(TimeEntry.counts_as_productive==True),
        booked_hours(TimeEntry.entry_type=="travel"),
        func.count(case((booked, TimeEntry.employee_id)).distinct()),
    ).where(*filters)).one()
    return {
        "entry_count": int(entry_count or 0), "booked_count": int(booked_count or 0),
        "total_hours": round_hours(_d(total)), "productive_hours": round_hours(_d(productive)),
        "travel_hours": round_hours(_d(travel)), "employee_count": int(employees or 0),
    }


def order_actual_hours(db: Session, order_id: int) -> dict:
    rows = db.execute(
        select(TimeEntry.counts_as_productive, TimeEntry.entry_type, func.coalesce(func.sum(TimeEntry.hours), 0))
        .where(TimeEntry.order_id==order_id, TimeEntry.status=="booked")
        .group_by(TimeEntry.counts_as_productive, TimeEntry.entry_type)
    ).all()
    productive=Decimal("0"); travel=Decimal("0"); total=Decimal("0")
    by_type={}
    for productive_flag, entry_type, hours in rows:
        h=_d(hours); total+=h; by_type[entry_type]=round_hours(h)
        if productive_flag: productive+=h
        if entry_type=="travel": travel+=h
    return {"productive_hours":round_hours(productive),"travel_hours":round_hours(travel),"total_hours":round_hours(total),"by_type":by_type}


def order_item_actual_hours(db: Session, order_id: int) -> dict[int, Decimal]:
    rows=db.execute(
        select(TimeEntry.order_item_id, func.coalesce(func.sum(TimeEntry.hours),0))
        .where(TimeEntry.order_id==order_id, TimeEntry.status=="booked", TimeEntry.counts_as_productive==True, TimeEntry.order_item_id.is_not(None))
        .group_by(TimeEntry.order_item_id)
    ).all()
    return {int(item_id):round_hours(_d(hours)) for item_id,hours in rows}


def employee_assigned_order_ids(db: Session, employee_id: int) -> set[int]:
    """Seit Rechtekonzept Teil B nur noch eine Weiterleitung: die Definition "welchen Aufträgen
    ist ein Mitarbeiter zugeordnet" lebt in app/orders.py (_assigned_order_id_queries()), damit
    die Auftragsauswahl der Zeiterfassung und die Objekt-Filterung für `field`
    (field_may_access_order()) nie auseinanderlaufen. Lokaler Import: orders.py erreicht über
    invoices/projects transitiv Module, die dieses Modul importieren (work_preparation.py) --
    dieselbe Zirkel-Vermeidung wie Regel 3 in CLAUDE.md."""
    from .orders import employee_assigned_order_ids as _canonical
    return _canonical(db, employee_id)


def time_tracking_context(db: Session, employee_id: int | None = None, include_all_orders: bool = False,
                          mit_geschlossenen: bool = False) -> dict:
    """Mitarbeiter, Teams und Aufträge für die Zeiterfassung im Büro. Seit 1.9.90 (Stufe 4, R5a, Punkt 2) mit mit_geschlossenen auch die
    abgeschlossenen und stornierten Aufträge -- nach den offenen, gekennzeichnet (geschlossen, status): das Büro mit dem Recht, für andere
    zu buchen, bucht und ändert auch dort (die Monteurin nicht, app/routers/time_tracking.py::_require_order_open_for_field())."""
    emp_stmt=select(Employee).where(Employee.active==True).order_by(Employee.last_name,Employee.first_name)
    employees=db.scalars(emp_stmt).all()
    # Bestandsauftraege aus aelteren Versionen koennen einen leeren/NULL-Status haben.
    # Diese duerfen in der Zeiterfassung nicht versehentlich ausgefiltert werden.
    order_stmt=(
        select(Order)
        .options(selectinload(Order.project), selectinload(Order.items))
        .order_by(Order.order_number.desc())
    )
    if not mit_geschlossenen:
        order_stmt=order_stmt.where(or_(Order.status.is_(None), func.lower(func.coalesce(Order.status, "")).not_in(["abgeschlossen", "storniert"])))
    orders=sorted(db.scalars(order_stmt).unique().all(), key=lambda o: auftrag_geschlossen(o.status) is not None)  # offene zuerst
    assigned_ids=employee_assigned_order_ids(db, employee_id) if employee_id else set()
    if employee_id and assigned_ids and not include_all_orders:
        orders=[o for o in orders if o.id in assigned_ids]
    team_stmt = select(Team).options(selectinload(Team.employees).selectinload(TeamEmployee.employee)).where(Team.active==True).order_by(Team.name)
    teams = db.scalars(team_stmt).unique().all()
    if employee_id and not include_all_orders:
        teams = [t for t in teams if any(m.employee_id == employee_id for m in t.employees)]
    return {
        "employees":[{"id":e.id,"name":employee_name(e),"employee_number":e.employee_number} for e in employees],
        "teams":[{
            "id":t.id,"name":t.name,"team_number":t.team_number,
            "employees":[{"id":m.employee_id,"name":employee_name(m.employee),"role":m.role} for m in t.employees if m.employee and m.employee.active]
        } for t in teams],
        "orders":[{
            "id":o.id,"order_number":o.order_number,"project_id":o.project_id,
            "project_number":o.project.project_number if o.project else None,"project_name":o.project.name if o.project else None,
            "customer_name":o.customer_name,"property_address":o.property_address,"title":o.title,
            "status":o.status,"geschlossen":auftrag_geschlossen(o.status),  # seit 1.9.90
            "items":[{"id":i.id,"oz":i.gaeb_oz or i.position_number,"short_text":i.short_text,"unit":i.unit} for i in o.items],
        } for o in orders],
    }


# --- Version 1.0.2: Gruppenbuchungen ---
def load_group(db: Session, group_id: int) -> TimeEntryGroup | None:
    return db.get(TimeEntryGroup, group_id)


def group_for_entry(db: Session, entry_id: int) -> TimeEntryGroup | None:
    link = db.scalar(select(TimeEntryGroupMember).where(TimeEntryGroupMember.time_entry_id == entry_id))
    return db.get(TimeEntryGroup, link.group_id) if link else None


def group_member_ids(db: Session, group_id: int) -> list[int]:
    return list(db.scalars(select(TimeEntryGroupMember.employee_id).where(TimeEntryGroupMember.group_id == group_id)).all())


def validate_group_members(db: Session, employee_ids: list[int], *, team_id: int | None = None, actor_employee_id: int | None = None, is_admin: bool = False) -> list[Employee]:
    ids = list(dict.fromkeys(int(x) for x in employee_ids if x))
    if not ids:
        raise ValueError("Bitte mindestens einen Mitarbeiter auswählen.")
    employees = list(db.scalars(select(Employee).where(Employee.id.in_(ids), Employee.active==True)).all())
    if len(employees) != len(ids):
        raise ValueError("Mindestens ein ausgewählter Mitarbeiter wurde nicht gefunden oder ist inaktiv.")
    if is_admin:
        if team_id is not None:
            member_ids=set(db.scalars(select(TeamEmployee.employee_id).where(TeamEmployee.team_id==team_id)).all())
            if not set(ids).issubset(member_ids):
                raise ValueError("Mindestens ein Mitarbeiter gehört nicht zum ausgewählten Team.")
        return employees
    if actor_employee_id is None:
        raise ValueError(KEIN_MITARBEITER)
    if actor_employee_id not in ids:
        raise ValueError("Bei einer Gruppenbuchung muss der buchende Mitarbeiter selbst enthalten sein.")
    if team_id is None:
        raise ValueError("Bitte für die Gruppenbuchung ein Team auswählen.")
    actor_in_team = db.scalar(select(TeamEmployee.id).where(TeamEmployee.team_id==team_id, TeamEmployee.employee_id==actor_employee_id).limit(1))
    if actor_in_team is None:
        raise ValueError("Du gehörst nicht zum ausgewählten Team.")
    member_ids=set(db.scalars(select(TeamEmployee.employee_id).where(TeamEmployee.team_id==team_id)).all())
    if not set(ids).issubset(member_ids):
        raise ValueError("Du darfst nur für Kollegen des ausgewählten Teams mitbuchen.")
    return employees


def _create_group_header(db: Session, *, initiated_by_employee_id: int | None, team_id: int | None, order: Order, order_item_id: int | None, mode: str, entry_type: str, activity: str | None, work_date: date, started_at: datetime | None, hours: Decimal, break_minutes: int, notes: str | None, status: str, created_by_user_id: int | None) -> TimeEntryGroup:
    row=TimeEntryGroup(
        initiated_by_employee_id=initiated_by_employee_id, team_id=team_id, order_id=order.id, project_id=order.project_id,
        order_item_id=order_item_id, mode=mode, entry_type=entry_type, activity=activity or None,
        work_date=work_date, started_at=started_at, ended_at=None, break_minutes=max(0,int(break_minutes or 0)),
        hours=_d(hours), notes=notes or None, status=status, created_by_user_id=created_by_user_id,
    )
    db.add(row);db.flush();return row


def create_group_manual_entry(db: Session, *, employee_ids: list[int], team_id: int | None, actor_employee_id: int | None, is_admin: bool, order_id: int, work_date: date, hours: Decimal | None = None, entry_type: str='site', order_item_id: int | None=None, activity: str | None=None, notes: str | None=None, break_minutes: int=0, created_by_user_id: int | None=None, von: time | None = None, bis: time | None = None) -> TimeEntryGroup:
    employees=validate_group_members(db,employee_ids,team_id=team_id,actor_employee_id=actor_employee_id,is_admin=is_admin)
    order=db.get(Order,order_id)
    if order is None: raise ValueError("Auftrag wurde nicht gefunden.")
    validate_order_item(db,order_id,order_item_id)
    if von is not None:
        return _kolonne_von_bis_anlegen(db, employees, team_id=team_id, actor_employee_id=actor_employee_id, order=order, work_date=work_date,
                                       von=von, bis=bis, mindestpause=break_minutes, entry_type=entry_type, order_item_id=order_item_id,
                                       activity=activity, notes=notes, created_by_user_id=created_by_user_id)
    amount=gebucht_nach_zeitregel(db,hours)  # seit 1.9.39 je Mitglied gerundet wie ein Einzel-Nachtrag (alle dieselbe Dauer)
    if amount<=0: raise ValueError("Die Stunden müssen größer als 0 sein.")
    group=_create_group_header(db,initiated_by_employee_id=actor_employee_id,team_id=team_id,order=order,order_item_id=order_item_id,mode='manual',entry_type=entry_type,activity=activity,work_date=work_date,started_at=None,hours=amount,break_minutes=break_minutes,notes=notes,status='booked',created_by_user_id=created_by_user_id)
    for emp in employees:
        entry=TimeEntry(employee_id=emp.id,project_id=order.project_id,order_id=order.id,order_item_id=order_item_id,work_date=work_date,entry_type=entry_type,counts_as_productive=entry_type_is_productive(entry_type),activity=activity or None,started_at=None,ended_at=None,break_minutes=max(0,int(break_minutes or 0)),min_break_minutes=max(0,int(break_minutes or 0)),hours=amount,notes=notes or None,source='group_manual',status='booked',created_by_user_id=created_by_user_id)
        db.add(entry);db.flush();db.add(TimeEntryGroupMember(group_id=group.id,employee_id=emp.id,time_entry_id=entry.id))
    db.commit();return db.get(TimeEntryGroup,group.id)


def _kolonne_kopf(group: TimeEntryGroup, werte: dict[int, dict], work_date: date, von: time, bis: time) -> None:
    """Seit 1.9.63: der Kopf einer Kolonnenbuchung mit Von/Bis -- Beginn und Ende, Stunden im Mittel (wie beim Gruppen-Stopp), die
    größte Pause."""
    group.started_at, group.ended_at = datetime.combine(work_date, von), datetime.combine(work_date, bis)
    if werte:
        group.hours = round_half_up(sum((w["gebucht"] for w in werte.values()), Decimal("0")) / Decimal(len(werte)), Decimal("0.0001"))
        group.break_minutes = max(w["pause"] for w in werte.values())


def _kolonne_von_bis_anlegen(db: Session, employees: list[Employee], *, team_id: int | None, actor_employee_id: int | None, order: Order,
                             work_date: date, von: time, bis: time, mindestpause: int, entry_type: str, order_item_id: int | None,
                             activity: str | None, notes: str | None, created_by_user_id: int | None) -> TimeEntryGroup:
    """Seit 1.9.63: Kolonnen-Nachtrag mit Von/Bis -- je Mitglied Pause und Rundung nach seinem Tag (kolonne_rechnen()), Beginn und
    Ende als Nachweis, die eingetragene Mindestpause gemerkt."""
    werte = kolonne_rechnen(db, [(e.id, employee_name(e) or f"#{e.id}", None, mindestpause) for e in employees],
                            work_date=work_date, von=von, bis=bis)
    group=_create_group_header(db,initiated_by_employee_id=actor_employee_id,team_id=team_id,order=order,order_item_id=order_item_id,mode='manual',entry_type=entry_type,activity=activity,work_date=work_date,started_at=None,hours=Decimal('0'),break_minutes=mindestpause,notes=notes,status='booked',created_by_user_id=created_by_user_id)
    _kolonne_kopf(group, werte, work_date, von, bis)
    for emp in employees:
        w = werte[emp.id]
        entry=TimeEntry(employee_id=emp.id,project_id=order.project_id,order_id=order.id,order_item_id=order_item_id,work_date=work_date,entry_type=entry_type,counts_as_productive=entry_type_is_productive(entry_type),activity=activity or None,started_at=w["beginn"],ended_at=w["ende"],break_minutes=w["pause"],min_break_minutes=w["mindestpause"],hours=w["gebucht"],notes=notes or None,source='group_manual',status='booked',created_by_user_id=created_by_user_id)
        db.add(entry);db.flush();db.add(TimeEntryGroupMember(group_id=group.id,employee_id=emp.id,time_entry_id=entry.id))
    db.commit();return db.get(TimeEntryGroup,group.id)


def start_group_timer(db: Session, *, employee_ids: list[int], team_id: int | None, actor_employee_id: int | None, is_admin: bool, order_id: int, entry_type: str='site', order_item_id: int | None=None, activity: str | None=None, notes: str | None=None, started_at: datetime | None=None, created_by_user_id: int | None=None) -> TimeEntryGroup:
    employees=validate_group_members(db,employee_ids,team_id=team_id,actor_employee_id=actor_employee_id,is_admin=is_admin)
    order=db.get(Order,order_id)
    if order is None: raise ValueError("Auftrag wurde nicht gefunden.")
    validate_order_item(db,order_id,order_item_id)
    laufend={e.id:active_entry(db,e.id) for e in employees}
    # seit 1.9.35 mit dem Tag, an dem eine offene Zeit von früher begann
    busy=[employee_name(e)+(f" (offen seit {laufend[e.id].started_at:%d.%m.})" if laeuft_seit_frueher(laufend[e.id]) else "")
          for e in employees if laufend[e.id] is not None]
    if busy: raise ValueError("Für folgende Mitarbeiter läuft bereits eine Zeiterfassung: "+", ".join(busy))
    start=started_at or berlin_now()
    group=_create_group_header(db,initiated_by_employee_id=actor_employee_id,team_id=team_id,order=order,order_item_id=order_item_id,mode='timer',entry_type=entry_type,activity=activity,work_date=start.date(),started_at=start,hours=Decimal('0'),break_minutes=0,notes=notes,status='running',created_by_user_id=created_by_user_id)
    for emp in employees:
        entry=TimeEntry(employee_id=emp.id,project_id=order.project_id,order_id=order.id,order_item_id=order_item_id,work_date=start.date(),entry_type=entry_type,counts_as_productive=entry_type_is_productive(entry_type),activity=activity or None,started_at=start,ended_at=None,break_minutes=0,hours=Decimal('0'),notes=notes or None,source='group_timer',status='running',created_by_user_id=created_by_user_id)
        db.add(entry);db.flush();db.add(TimeEntryGroupMember(group_id=group.id,employee_id=emp.id,time_entry_id=entry.id))
    db.commit();return db.get(TimeEntryGroup,group.id)


def stop_group_timer(db: Session, group_id: int, *, ended_at: datetime | None=None, break_minutes: int=0) -> TimeEntryGroup:
    group=db.get(TimeEntryGroup,group_id)
    if group is None: raise ValueError("Gruppenbuchung wurde nicht gefunden.")
    if group.status!='running' or group.started_at is None: raise ValueError("Diese Gruppenbuchung läuft nicht mehr.")
    end=ended_at or berlin_now()
    links=db.scalars(select(TimeEntryGroupMember).where(TimeEntryGroupMember.group_id==group.id)).all()
    amounts=[]; applied_breaks=[]
    for link in links:
        entry=db.get(TimeEntry,link.time_entry_id)
        if entry and entry.status=='running':
            # seit 1.9.34 dieselbe Pausenregel wie der Einzel-Stopp, je Mitglied nach seinem Arbeitszeitmodell (pause_nach_zeitregel())
            # seit 1.9.44 über ende_rechnen() -- dieselbe Rechnung wie Einzel-Stopp und Vorschau (seit 1.9.39 je Mitglied gerundet)
            if end>group.started_at:
                werte=ende_rechnen(db,link.employee_id,group.started_at,end,break_minutes);applied,amount=werte["pause"],werte["gebucht"]
            else:
                applied=max(0,int(break_minutes or 0));amount=compute_hours(group.started_at,end,applied)  # lehnt das Ende ab
            entry.ended_at=end;entry.break_minutes=applied;entry.hours=amount;entry.status='booked'
            entry.min_break_minutes=max(0,int(break_minutes or 0))  # seit 1.9.62: die eingegebene Pause, ohne Eingabe 0
            amounts.append(amount);applied_breaks.append(applied)
    group.ended_at=end
    group.break_minutes=max(applied_breaks or [max(0,int(break_minutes or 0))])
    group.hours=round_half_up(sum(amounts,Decimal('0'))/Decimal(len(amounts)),Decimal('0.0001')) if amounts else Decimal('0')
    group.status='booked'
    db.commit();return db.get(TimeEntryGroup,group.id)


def group_to_dict(db: Session, group: TimeEntryGroup) -> dict:
    links=db.scalars(select(TimeEntryGroupMember).where(TimeEntryGroupMember.group_id==group.id).order_by(TimeEntryGroupMember.id)).all()
    member_entries=[]
    for link in links:
        entry=load_entry(db,link.time_entry_id)
        if entry: member_entries.append(entry_to_dict(entry))
    return {"id":group.id,"initiated_by_employee_id":group.initiated_by_employee_id,"team_id":group.team_id,"order_id":group.order_id,"project_id":group.project_id,"order_item_id":group.order_item_id,"mode":group.mode,"entry_type":group.entry_type,"activity":group.activity,"work_date":group.work_date,"started_at":group.started_at,"ended_at":group.ended_at,"break_minutes":group.break_minutes,"hours":group.hours,"notes":group.notes,"status":group.status,"member_entries":member_entries}


# --- Version 1.7.12: Kolonnenführer ---
def crew_leader_team_ids(db: Session, employee_id: int | None) -> set[int]:
    """Aktive Teams, in denen der Mitarbeiter als Kolonnenführer eingetragen ist."""
    if employee_id is None:
        return set()
    return set(db.scalars(
        select(TeamEmployee.team_id).join(Team, Team.id == TeamEmployee.team_id)
        .where(TeamEmployee.employee_id == employee_id, TeamEmployee.is_crew_leader == True, Team.active == True)  # noqa: E712
    ).all())


def list_crews_for_leader(db: Session, employee_id: int | None) -> list[dict]:
    team_ids = crew_leader_team_ids(db, employee_id)
    if not team_ids:
        return []
    teams = db.scalars(
        select(Team).options(selectinload(Team.employees).selectinload(TeamEmployee.employee))
        .where(Team.id.in_(team_ids)).order_by(Team.name)
    ).unique().all()
    return [{
        "team_id": t.id, "name": t.name,
        "members": [{"employee_id": m.employee_id, "name": employee_name(m.employee)}
                    for m in t.employees if m.employee and m.employee.active],
    } for t in teams]


def field_time_tracking_context(db: Session, employee_id: int) -> dict:
    """GET /api/time-tracking/context für Monteure (seit 1.8.24). Vorher bekam der Monteur dasselbe
    wie das Büro: alle aktiven Mitarbeiter mit Personalnummer, alle Teams mit Mitgliedern, Aufträge
    mit Projekt und LV-Positionen -- und ohne einen einzigen geplanten Auftrag sogar alle offenen
    Aufträge des Betriebs (time_tracking_context() filtert nur, wenn es Zuordnungen gibt).

    Die mobile Zeiterfassung ruft diesen Endpunkt nicht auf: Aufträge kommen aus
    GET /api/field-view/time-tracking/orders, Kolonnen aus GET /api/time-tracking/crews. Der Monteur
    bekommt hier deshalb genau diese Daten aus denselben Funktionen, nichts darüber hinaus -- sich
    selbst, als Kolonnenführer zusätzlich seine Kolonne(n), nur Name und ID, keine Personalnummer."""
    from .planning import list_field_bookable_orders  # lokal: planning -> work_preparation -> dieses Modul
    crews = list_crews_for_leader(db, employee_id)
    me = db.get(Employee, employee_id)
    names = {employee_id: employee_name(me)} if me is not None else {}
    for crew in crews:
        for member in crew["members"]:
            names.setdefault(member["employee_id"], member["name"])
    return {
        "employees": [{"id": emp_id, "name": name} for emp_id, name in names.items()],
        "teams": [{"id": c["team_id"], "name": c["name"],
                   "employees": [{"id": m["employee_id"], "name": m["name"]} for m in c["members"]]} for c in crews],
        "orders": list_field_bookable_orders(db, employee_id),
    }


def _group_links(db: Session, group_id: int) -> list[TimeEntryGroupMember]:
    return list(db.scalars(select(TimeEntryGroupMember).where(TimeEntryGroupMember.group_id == group_id).order_by(TimeEntryGroupMember.id)).all())


def update_group(db: Session, group_id: int, *, order_id: int, work_date: date, hours: Decimal, entry_type: str,
                 order_item_id: int | None = None, activity: str | None = None, notes: str | None = None,
                 break_minutes: int = 0, von: time | None = None, bis: time | None = None,
                 mindestpause: int | None = None, als_dauer: bool = False) -> tuple[TimeEntryGroup, list[str]]:
    """Korrigiert eine abgeschlossene Gruppenbuchung und jede Mitgliedsbuchung, die seit der
    Gruppenbuchung NICHT einzeln geändert wurde (seit 1.7.13, lohnrelevant -- vorher überschrieb
    die Gruppenkorrektur auch eine Einzelkorrektur des Mitglieds). Gibt zusätzlich die Namen der
    unangetastet gebliebenen Mitglieder zurück. Seit 1.9.63 mit von/bis: je Mitglied wie ein Nachtrag (kolonne_rechnen(), sein Tag ohne
    die alte Fassung), Mindestpause = mindestpause oder ohne Angabe die gemerkte des Mitglieds; hours und break_minutes zählen dann nicht.
    Seit 1.9.90 (Stufe 4, R5a, Punkt 3): ohne von/bis setzt nur als_dauer (als Dauer gespeichert -- Stunden, Pause oder Tag) Stunden und
    Pause aller Mitglieder und leert Beginn und Ende (auch im Kopf); sonst bleiben Stunden, Pause und Zeiten jedes Mitglieds -- bis 1.9.89
    bekam jedes Mitglied bei jedem Ändern (auch nur der Notiz) die Stunden des Kopfs, nach einem Nachtrag mit Von/Bis deren Mittel."""
    group = db.get(TimeEntryGroup, group_id)
    if group is None: raise ValueError("Gruppenbuchung wurde nicht gefunden.")
    if group.status != "booked": raise ValueError("Eine laufende Gruppenbuchung zuerst stoppen.")
    order = db.get(Order, order_id)
    if order is None: raise ValueError("Auftrag wurde nicht gefunden.")
    validate_order_item(db, order_id, order_item_id)
    amount = _d(hours)
    if von is None and amount <= 0: raise ValueError("Die Stunden müssen größer als 0 sein.")
    skipped: list[str] = []
    # Seit 1.8.99: die Mitgliedsbuchungen gesperrt (aufsteigend), danach ihre Verknüpfungen frisch -- eine gleichzeitige Einzelkorrektur
    # eines Mitglieds (PUT /api/time-entries/{id}, gesperrt) ist so entweder schon gespeichert und wird übersprungen, oder sie wartet.
    links = _group_links(db, group.id)
    db.scalars(select(TimeEntry).where(TimeEntry.id.in_([link.time_entry_id for link in links])).order_by(TimeEntry.id)
               .with_for_update().execution_options(populate_existing=True)).all()
    for link in links:
        db.refresh(link)
    werte: dict[int, dict] = {}
    if von is not None:  # seit 1.9.63: je Mitglied nach seinem Tag, vor jeder Änderung (ein Fehler ändert nichts)
        offen = [(link, db.get(TimeEntry, link.time_entry_id)) for link in links if link.individually_changed_at is None]
        werte = kolonne_rechnen(db, [(e.employee_id, employee_name(db.get(Employee, e.employee_id)) or f"#{e.employee_id}", e.id,
                                      mindestpause if mindestpause is not None else mindestpause_der_buchung(e))
                                     for _, e in offen if e is not None], work_date=work_date, von=von, bis=bis)
    for link in links:
        entry = db.get(TimeEntry, link.time_entry_id)
        if entry is None:
            continue
        if link.individually_changed_at is not None:
            skipped.append(employee_name(db.get(Employee, link.employee_id)) or f"#{link.employee_id}")
            continue
        entry.order_id = order.id; entry.project_id = order.project_id; entry.order_item_id = order_item_id
        entry.work_date = work_date; entry.entry_type = entry_type
        entry.counts_as_productive = entry_type_is_productive(entry_type)
        entry.activity = activity or None; entry.notes = notes or None
        if von is None and als_dauer:  # seit 1.9.90: als Dauer -- Stunden und Pause der Kolonne, ohne Beginn und Ende
            entry.hours = amount; entry.break_minutes = max(0, int(break_minutes or 0))
            entry.min_break_minutes = entry.break_minutes  # seit 1.9.62: die eingetragene Pause der Kolonne
            entry.started_at = entry.ended_at = None
        w = werte.get(entry.employee_id)
        if w is not None:  # seit 1.9.63: Von/Bis
            entry.started_at, entry.ended_at, entry.hours = w["beginn"], w["ende"], w["gebucht"]
            entry.break_minutes, entry.min_break_minutes = w["pause"], w["mindestpause"]
    group.order_id = order.id; group.project_id = order.project_id; group.order_item_id = order_item_id
    group.work_date = work_date; group.hours = amount; group.entry_type = entry_type
    group.activity = activity or None; group.notes = notes or None; group.break_minutes = max(0, int(break_minutes or 0))
    if von is None and als_dauer:
        group.started_at = group.ended_at = None
    if von is not None:  # alle einzeln geändert: der Kopf behält Stunden und Pause
        _kolonne_kopf(group, werte, work_date, von, bis)
    db.commit()
    return db.get(TimeEntryGroup, group.id), skipped


def kolonne_vorschau(db: Session, *, employees: list[Employee] | None = None, group: TimeEntryGroup | None = None, work_date: date,
                    von: time, bis: time, mindestpause: int | None) -> dict:
    """Seit 1.9.63: was der Kolonnen-Nachtrag (employees) bzw. das Ändern einer Kolonnenbuchung (group) mit dieser Von/Bis-Angabe je
    Mitglied buchen würde -- dieselbe Rechnung (kolonne_rechnen()), ohne zu buchen. Beim Ändern ohne die einzeln geänderten Mitglieder
    (uebersprungen), ohne Angabe der Mindestpause mit der gemerkten je Mitglied."""
    mitglieder, uebersprungen = [], []
    if group is not None:
        for link in _group_links(db, group.id):
            name = employee_name(db.get(Employee, link.employee_id)) or f"#{link.employee_id}"
            entry = db.get(TimeEntry, link.time_entry_id)
            if link.individually_changed_at is not None or entry is None:
                uebersprungen.append(name)
                continue
            mitglieder.append((link.employee_id, name, entry.id, mindestpause if mindestpause is not None else mindestpause_der_buchung(entry)))
    else:
        mitglieder = [(e.id, employee_name(e) or f"#{e.id}", None, mindestpause or 0) for e in employees or []]
    werte = kolonne_rechnen(db, mitglieder, work_date=work_date, von=von, bis=bis)
    return {"mitglieder": [{"employee_id": i, "name": w["name"], "anwesend": w["anwesend"], "pause": w["pause"],
                             "gebucht": w["gebucht"], "tag_zusammen": w["tag_zusammen"], "tag_buchungen": w["tag_buchungen"]}
                            for i, w in werte.items()], "uebersprungen": uebersprungen}


def delete_group(db: Session, group_id: int) -> list[str]:
    """Löscht die Gruppenbuchung samt ihrer Mitgliedsbuchungen -- außer denen, die seit der
    Gruppenbuchung einzeln geändert wurden (seit 1.7.13): die bleiben als eigenständige Buchung
    des Mitglieds stehen (nur die Gruppen-Verknüpfung entfällt). Gibt deren Namen zurück."""
    group = db.get(TimeEntryGroup, group_id)
    if group is None: raise ValueError("Gruppenbuchung wurde nicht gefunden.")
    if group.status != "booked": raise ValueError("Eine laufende Gruppenbuchung zuerst stoppen.")
    kept: list[str] = []
    for link in _group_links(db, group.id):
        entry = db.get(TimeEntry, link.time_entry_id)
        changed = link.individually_changed_at is not None
        if changed:
            kept.append(employee_name(db.get(Employee, link.employee_id)) or f"#{link.employee_id}")
        db.delete(link); db.flush()
        if entry is not None and not changed:
            db.delete(entry)
    db.flush()
    db.delete(group); db.commit()
    return kept


def list_groups_initiated_by(db: Session, employee_id: int, *, start_date: date) -> list[dict]:
    groups = db.scalars(
        select(TimeEntryGroup).where(TimeEntryGroup.initiated_by_employee_id == employee_id, TimeEntryGroup.work_date >= start_date)
        .order_by(TimeEntryGroup.work_date.desc(), TimeEntryGroup.id.desc())
    ).all()
    result = []
    for g in groups:
        team = db.get(Team, g.team_id) if g.team_id else None
        order = db.get(Order, g.order_id)
        members, mindestpause = [], None
        for link in _group_links(db, g.id):
            emp = db.get(Employee, link.employee_id)
            members.append({"employee_id": link.employee_id, "name": employee_name(emp) or f"#{link.employee_id}",
                            "individually_changed": link.individually_changed_at is not None})
            entry = db.get(TimeEntry, link.time_entry_id) if link.individually_changed_at is None else None
            if mindestpause is None and entry is not None and entry.status == "booked":
                mindestpause = mindestpause_der_buchung(entry)  # seit 1.9.63: die gemerkte eines nicht einzeln geänderten Mitglieds
        result.append({
            "id": g.id, "team_id": g.team_id, "team_name": team.name if team else None,
            "order_id": g.order_id, "order_number": order.order_number if order else None,
            "order_item_id": g.order_item_id, "mode": g.mode, "entry_type": g.entry_type, "activity": g.activity,
            "work_date": g.work_date, "hours": g.hours, "break_minutes": g.break_minutes, "notes": g.notes,
            "status": g.status, "members": members,
            # seit 1.9.63: Von und Bis (leer bei einer Dauer) und die eingetragene Mindestpause -- „Für die Kolonne ändern“ belegt sie vor
            "von": g.started_at.strftime("%H:%M") if g.started_at else None,
            "bis": g.ended_at.strftime("%H:%M") if g.ended_at else None,
            "mindestpause": mindestpause if mindestpause is not None else int(g.break_minutes or 0),
        })
    return result


def active_group_for_employee(db: Session, employee_id: int, *, initiated_only: bool = False) -> TimeEntryGroup | None:
    stmt=(
        select(TimeEntryGroup)
        .join(TimeEntryGroupMember, TimeEntryGroupMember.group_id==TimeEntryGroup.id)
        .join(TimeEntry, TimeEntry.id==TimeEntryGroupMember.time_entry_id)
        .where(TimeEntryGroupMember.employee_id==employee_id, TimeEntryGroup.status=='running', TimeEntry.status=='running')
        .order_by(TimeEntryGroup.started_at.desc())
    )
    if initiated_only:
        stmt=stmt.where(TimeEntryGroup.initiated_by_employee_id==employee_id)
    return db.scalar(stmt)
