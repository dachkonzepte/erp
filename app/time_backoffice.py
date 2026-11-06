from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO, StringIO
from html import escape
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

from .audit import record_audit_entry
from .grunddaten import einzelzeile
from .models import AppUser, Employee, EmployeePayrollSettings, PersonalnummerVergabe, TimeEntry, TimeTrackingSettings, WorkTimeModel
from .rounding import round_hours
from .time_tracking import employee_name, list_entries, entry_to_dict, pausen_vorschau, tagessumme
from .settings import load_general_settings
from .work_time_models import load_advanced_settings

# Seit 1.9.168 (Lohn L1a, Punkt 3, Entscheidung Tobias E3): was von einer Person in die Lohndatei geht. „alles“ = Arbeit, Abwesenheiten und
# Feiertage; „abwesenheiten“ = nur Urlaub, Krankheit und die übrigen zugeordneten Abwesenheiten (bisher z. B. Azubis in Time 4); „nichts“.
EXPORT_UMFAENGE = {"alles": "alles", "abwesenheiten": "nur Abwesenheiten", "nichts": "nichts"}
# Seit 1.9.212 (L1a Stufe 6, Punkt 1, Antwort des Lohnbüros): eine DATEV-Personalnummer hat genau 5 Ziffern, führende Nullen gehören dazu
# (00001, 00101, 00204) -- „101“ und „00101“ wären sonst zwei Nummern für dieselbe Person. Kein Auffüllen beim Speichern: wer „101“ einträgt,
# bekommt die Meldung (aufgefüllt hat nur die Migration 5d2e8a71c4f3 den Bestand). 1.9.168–1.9.211: 1 bis 5 Ziffern ohne führende Null.
# Ein Semikolon o. Ä. zerstörte die Datei.
PERSONALNUMMER_FORMAT = re.compile(r"^[0-9]{5}$")
PERSONALNUMMER_FALSCH = "Die DATEV-Personalnummer hat genau 5 Ziffern, führende Nullen gehören dazu (z. B. 00101)."
PERSONALNUMMER_VERGEBEN = "Diese DATEV-Personalnummer ist bereits vergeben."
# Seit 1.9.212: die Nummernkreise des Lohnbüros -- nur ein Hinweis beim Speichern, keine Sperre. Der Hinweis nennt nur den Kreis der Nummer und
# prüft nicht gegen ein Merkmal der Person (Minijob gibt es als Merkmal nicht; Azubi seit 1.9.224, EmployeePayrollSettings.azubi, wirkt nur in der
# Lohndatei).
# Seit 1.9.219 (L1a Stufe 7, Punkt 2): die Azubis reichen bis 00299 -- genutzt sind die Kreise je Hundert wie die beiden ersten; darüber sagt der
# Hinweis, dass die Nummer außerhalb der vom Lohnbüro genannten Bereiche liegt (bis 1.9.218 hieß auch 91008 „Kreis Azubis“). Die Grenze steht fest
# hier, nicht aus den vergebenen Nummern abgeleitet: eine aus den Daten abgeleitete Grenze zöge jede Fehleingabe mit (berichtigt 1.9.229 -- die
# bis dahin genannte Begründung „die Sperrliste trägt die Nummern aus Time 4 (91…)“ war nicht belegt, die 91… sind erfundene Musternummern).
NUMMERNKREISE = ((0, 99, "sv-pflichtig Beschäftigte", "00000–00099"), (100, 199, "Minijobber", "00100–00199"), (200, 299, "Azubis", "ab 00200"))
GENUTZT_BIS = NUMMERNKREISE[-1][1]


def personalnummer_gueltig(wert: str | None) -> bool:
    return bool(wert) and PERSONALNUMMER_FORMAT.match(wert) is not None


def nummernkreis(nummer: str | None) -> str | None:
    """Seit 1.9.212: der Hinweis zum Kreis einer gültigen Nummer, z. B. „Die Personalnummer 00150 liegt im Kreis Minijobber (00100–00199).“ --
    seit 1.9.219 über 00299 „… liegt außerhalb der vom Lohnbüro genannten Bereiche …“; None ohne gültige Nummer."""
    if not personalnummer_gueltig(nummer):
        return None
    wert = int(nummer)
    for von, bis, name, bereich in NUMMERNKREISE:
        if von <= wert <= bis:
            return f"Die Personalnummer {nummer} liegt im Kreis {name} ({bereich})."
    return (f"Die Personalnummer {nummer} liegt außerhalb der vom Lohnbüro genannten Bereiche (genutzt: 00000–{GENUTZT_BIS:05d}) – "
            "bitte prüfen.")  # seit 1.9.219


# Seit 1.9.213 (L1a Stufe 6, Punkt 2): so heißt eine gemerkte Nummer ohne Person (scripts/personalnummern_einlesen.py) in der Meldung
EINGELESEN = "eingelesene Liste vergebener Nummern"


# Seit 1.9.177 (L1a-Nachtrag, Punkt 4, Vorgabe Tobias): eine Nummer, die einer Person einmal gehört hat, bleibt dauerhaft gesperrt -- auch nach
# Austritt und nach einem Nummernwechsel (bis 1.9.176 war die alte Nummer nach einem Wechsel frei, Festlegung 1.9.168 Nr. 3). Nur dieselbe Person
# bekommt sie wieder. Gemerkt in PersonalnummerVergabe, nie gelöscht.
def personalnummer_gesperrt(db: Session, nummer: str | None, employee_id: int) -> str | None:
    """Warum die Nummer für diese Person nicht geht -- None: frei oder schon ihre."""
    nummer = (nummer or "").strip()
    if not nummer:
        return None
    row = db.scalar(select(PersonalnummerVergabe).where(PersonalnummerVergabe.nummer == nummer))
    if row is None or row.employee_id == employee_id:
        return None
    if row.employee_id is None:  # seit 1.9.213: eingelesen aus einer Liste vergebener Nummern (scripts/personalnummern_einlesen.py)
        return (f"Die Personalnummer {nummer} ist schon vergeben ({EINGELESEN}) – eine Personalnummer bleibt dauerhaft gesperrt.")
    return (f"Die Personalnummer {nummer} gehörte schon {employee_name(db.get(Employee, row.employee_id)) or 'einer anderen Person'} – eine "
            "Personalnummer bleibt dauerhaft gesperrt, auch nach Austritt und Nummernwechsel.")


def personalnummer_merken(db: Session, nummer: str | None, employee_id: int) -> None:
    """Die Nummer für die Person vormerken (ohne Commit; einmal je Nummer, die Bedingung fängt zwei gleichzeitige ab)."""
    nummer = (nummer or "").strip()
    if nummer and db.scalar(select(PersonalnummerVergabe.id).where(PersonalnummerVergabe.nummer == nummer)) is None:
        db.add(PersonalnummerVergabe(nummer=nummer, employee_id=employee_id))


def fruehere_personalnummern(db: Session) -> dict[int, list[str]]:
    """Je Person die gemerkten Nummern (für die Liste der Lohnstammdaten: „früher …“) -- seit 1.9.213 ohne die eingelesenen ohne Person."""
    je: dict[int, list[str]] = {}
    for nummer, eid in db.execute(select(PersonalnummerVergabe.nummer, PersonalnummerVergabe.employee_id)
                                  .where(PersonalnummerVergabe.employee_id.is_not(None)).order_by(PersonalnummerVergabe.id)):
        je.setdefault(eid, []).append(nummer)
    return je


def eingelesene_personalnummern(db: Session) -> list[dict]:
    """Seit 1.9.218 (L1a Stufe 7, Punkt 1): die gemerkten Nummern ohne Person (eingelesen aus einer Liste vergebener Nummern) für die eigene
    Liste unter „Zeitregeln und DATEV“ -- nur der Admin sieht sie (der Router fragt darf_personalnummer_freigeben()). Je Nummer: der Tag des
    Einlesens in Berlin und wer sie heute trägt (nur an der Sperre vorbei möglich; dann kein „freigeben“, dieselbe Regel wie seit 1.9.191).
    Sortiert nach Nummer."""
    from .berlin_time import to_berlin
    zeilen = db.execute(select(PersonalnummerVergabe.nummer, PersonalnummerVergabe.vergeben_am)
                        .where(PersonalnummerVergabe.employee_id.is_(None)).order_by(PersonalnummerVergabe.nummer)).all()
    traeger = personalnummern_traeger(db, [n for n, _ in zeilen])
    from .lohndatei import personalnummern_der_ablage
    ablage = personalnummern_der_ablage(db)  # seit 1.9.226: steht sie in einer abgelegten Lohndatei, kein „freigeben“
    return [{"nummer": n, "eingelesen_am": to_berlin(am).date() if am else None, "traegt": traeger.get(n), "lohndatei": ablage.get(n)}
            for n, am in zeilen]


class PersonalnummerGehalten(ValueError):
    """Freigeben abgelehnt: eine Person trägt die Nummer heute (409) -- seit 1.9.226 auch: sie steht in einer abgelegten Lohndatei."""


def personalnummer_halter(db: Session, nummer: str) -> Employee | None:
    """Wer die Nummer heute trägt: Lohnstammdaten mit dieser DATEV-Nummer. Seit 1.9.230 nur diese (bis 1.9.229 bei „DATEV-Nr. = ERP-Nr.“ auch
    eine Mitarbeiternummer -- der Schalter ist entfallen)."""
    eid = db.scalar(select(EmployeePayrollSettings.employee_id).where(EmployeePayrollSettings.datev_personnel_number == nummer).limit(1))
    return db.get(Employee, eid) if eid is not None else None


def personalnummern_traeger(db: Session, nummern) -> dict[str, str]:
    """Seit 1.9.191 (L1a Stufe 2, Punkt 6): wer die Nummern heute trägt, {Nummer: Name} -- dieselbe Regel wie personalnummer_halter() (die
    Lohnstammdaten; bis 1.9.229 bei „DATEV-Nr. = ERP-Nr.“ dann die Mitarbeiternummer), für die Liste „früher“ in einem Zug. Eine getragene Nummer
    lässt sich nicht freigeben; die Seite zeigt statt des Knopfs, wer sie trägt."""
    nummern = {n for n in nummern if n}
    if not nummern:
        return {}
    traeger: dict[str, int] = {}
    for nummer, eid in db.execute(select(EmployeePayrollSettings.datev_personnel_number, EmployeePayrollSettings.employee_id)
                                  .where(EmployeePayrollSettings.datev_personnel_number.in_(nummern)).order_by(EmployeePayrollSettings.id)):
        traeger.setdefault(nummer, eid)
    namen = {e.id: employee_name(e) for e in db.scalars(select(Employee).where(Employee.id.in_(set(traeger.values()))))} if traeger else {}
    return {nummer: namen.get(eid) or "eine Person" for nummer, eid in traeger.items()}


def personalnummer_freigeben(db: Session, nummer: str | None) -> None:
    """Seit 1.9.181 (L1a-Korrekturen, Punkt 2, Vorgabe Tobias): eine gemerkte Nummer wieder freigeben (Festlegung 1.9.177 Nr. 3 neu gefasst) --
    der Admin (der Router fragt app/permissions.py::darf_personalnummer_freigeben()), nur solange sie niemand trägt (personalnummer_halter()).
    Danach kann jede Person sie bekommen. Im selben Commit ein Eintrag im Änderungsprotokoll: welche Nummer, wem sie gemerkt war, wer frei gab.
    Seit 1.9.226 (Lohn L1b, Punkt 3, Notiz zu 1.9.181): eine Nummer, die in einer abgelegten Lohndatei steht, bleibt gesperrt (409). Committet."""
    nummer = (nummer or "").strip()
    row = db.scalar(select(PersonalnummerVergabe).where(PersonalnummerVergabe.nummer == nummer).with_for_update())
    if row is None:
        raise LookupError(f"Die Personalnummer {nummer} ist nicht gesperrt.")
    halter = personalnummer_halter(db, nummer)
    if halter is not None:
        raise PersonalnummerGehalten(f"Die Personalnummer {nummer} trägt heute {employee_name(halter) or 'eine Person'} – freigeben geht nur, "
                                     "solange sie niemand trägt.")
    from .lohndatei import personalnummern_der_ablage
    monat = personalnummern_der_ablage(db).get(nummer)
    if monat is not None:
        raise PersonalnummerGehalten(f"Die Personalnummer {nummer} steht in der abgelegten Lohndatei {monat} – sie bleibt gesperrt.")
    if row.employee_id is None:  # seit 1.9.213: eingelesen, ohne Person
        alt = "gesperrt, eingelesen ohne Person"
    else:
        alt = f"gesperrt, gehörte {employee_name(db.get(Employee, row.employee_id)) or 'einer anderen Person'}"
    record_audit_entry(db, action="Personalnummer freigegeben", entity_type="Personalnummer", entity_id=nummer,
                       entity_label=f"Personalnummer {nummer}", field_name="nummer", field_label="Personalnummer",
                       old_value=alt, new_value="frei")
    db.delete(row)
    db.commit()


def export_umfang(p: EmployeePayrollSettings | None) -> str:
    return (p.export_umfang if p is not None and p.export_umfang else "alles")


def exportiert_arbeit(p: EmployeePayrollSettings | None) -> bool:
    """Seit 1.9.168: stehen die gebuchten Stunden der Person in der Lohndatei? Nur beim Umfang „alles“ (bis 1.9.167 payroll_export_enabled)."""
    return export_umfang(p) == "alles"


def load_time_settings(db: Session) -> TimeTrackingSettings:
    """Nur lesen -- die Zeile legt app.grunddaten.anlegen() beim Start an (seit 1.8.42)."""
    return einzelzeile(db, TimeTrackingSettings)


def time_settings_dict(row: TimeTrackingSettings, db: Session | None = None) -> dict:
    advanced = load_advanced_settings(db) if db is not None else None
    return {
        "rounding_minutes": row.rounding_minutes,  # seit 1.9.61 ohne Standardpause
        "allow_manual_entries": row.allow_manual_entries,
        "allow_group_bookings": row.allow_group_bookings,
        "require_order_item": row.require_order_item,
        "require_activity": row.require_activity,
        # seit 1.9.224 ohne Zielsystem und Lohnarten je Zeitart (E8, die Lohndatei nimmt die Zuordnung)
        "datev_beraternummer": row.datev_beraternummer, "datev_mandantennummer": row.datev_mandantennummer,  # seit 1.9.92
        # seit 1.9.230 ohne „DATEV-Nr. = ERP-Nr.“ (Stufe 6, R3a, Punkt 0a: der Schalter ist entfallen)
        "default_work_time_model_id": advanced.default_work_time_model_id if advanced else None,
        "locked_until": row.locked_until,
        "locked_at": row.locked_at,
        "locked_by_name": _locked_by_name(db, row) if db is not None else None,
    }


def _locked_by_name(db: Session, row: TimeTrackingSettings) -> str | None:
    if row.locked_by_user_id is None:
        return None
    user = db.get(AppUser, row.locked_by_user_id)
    return user.display_name if user else None


def locked_until(db: Session) -> date | None:
    return load_time_settings(db).locked_until


def abschluss_hindernisse(db: Session, bis: date) -> list[dict]:
    """Seit 1.9.91 (Stufe 4, R5a, Punkt 4): was den Abschluss bis einschließlich `bis` sperrt -- jede laufende Zeit mit Tag bis dahin (auch
    eine seit früher offene) und jeder Tag mit unpassender Pause (pausen_vorschau(): neu rechnen würde etwas ändern) ab dem Tag nach dem
    bisherigen Abschluss, ohne bisherigen Abschluss im Monat von `bis`. Je Eintrag art ("laeuft" | "pause"), Mitarbeiter, Tag und ein Text.
    Personalnummer, Lohnart und DATEV-Nummern sperren den Abschluss nicht (sie sperren den DATEV-Export)."""
    vorher = load_time_settings(db).locked_until
    ab = vorher + timedelta(days=1) if vorher is not None else bis.replace(day=1)
    liste: list[dict] = []
    laufend = select(TimeEntry).where(TimeEntry.status == "running", TimeEntry.work_date <= bis).order_by(TimeEntry.work_date, TimeEntry.id)
    for row in db.scalars(laufend).all():
        name = employee_name(row.employee) or f"#{row.employee_id}"
        seit = f"{row.started_at:%d.%m.%Y, %H:%M}" if row.started_at else f"{row.work_date:%d.%m.%Y}"
        liste.append({"art": "laeuft", "employee_id": row.employee_id, "name": name, "tag": row.work_date, "entry_id": row.id,
                      "text": f"{name}: Zeit läuft seit {seit}"})
    for employee_id, tag, stand in unpassende_pausen(db, ab, bis):
        name = employee_name(db.get(Employee, employee_id)) or f"#{employee_id}"
        liste.append({"art": "pause", "employee_id": employee_id, "name": name, "tag": tag, "entry_id": None,
                      "text": f"{name}, {tag:%d.%m.%Y}: Pause abgezogen {stand['abgezogen']} min, nach Zeitregel {stand['noetig']} min"})
    return liste


def unpassende_pausen(db: Session, ab: date, bis: date) -> list[tuple[int, date, dict]]:
    """Seit 1.9.95 (Stufe 4, R5b): die Tage mit unpassender Pause zwischen ab und bis -- je (Mitarbeiter, Tag) mit gebuchten Zeiten der
    Stand aus pausen_vorschau(), wenn neu rechnen etwas ändern würde; nach Tag, dann Mitarbeiter. Eine Liste für den Abschluss
    (abschluss_hindernisse()) und „Prüfen“ der Seite „Zeiten“ (app/zeiten.py)."""
    tage = (select(TimeEntry.employee_id, TimeEntry.work_date)
            .where(TimeEntry.status == "booked", TimeEntry.work_date >= ab, TimeEntry.work_date <= bis).distinct())
    ergebnis = []
    for employee_id, tag in sorted(db.execute(tage).all(), key=lambda x: (x[1], x[0])):
        stand = pausen_vorschau(db, employee_id, tag)
        if not stand["passt"]:
            ergebnis.append((employee_id, tag, stand))
    return ergebnis


def abschluss_meldung(liste: list[dict]) -> str:
    """Der Text der Ablehnung (409): wie viele laufen, wie viele Tage passen nicht, danach jeder Eintrag."""
    laeuft = sum(1 for x in liste if x["art"] == "laeuft")
    pause = len(liste) - laeuft
    teile = ([f"{laeuft} {'Zeit läuft' if laeuft == 1 else 'Zeiten laufen'} noch"] if laeuft else []) + \
            ([f"{pause} {'Tag' if pause == 1 else 'Tage'} mit unpassender Pause"] if pause else [])
    return "Abschließen geht noch nicht: " + ", ".join(teile) + " – " + "; ".join(x["text"] for x in liste) + "."


def set_time_lock(db: Session, new_locked_until: date | None, *, user_id: int | None) -> TimeTrackingSettings:
    """Setzt den Abschluss (None = alles offen). Wer zurücknehmen darf, entscheidet der Router --
    diese Funktion kennt keine Rollen."""
    row = load_time_settings(db)
    row.locked_until = new_locked_until
    row.locked_at = datetime.utcnow()
    row.locked_by_user_id = user_id
    db.commit(); db.refresh(row)
    return row


def update_time_settings(db: Session, payload) -> TimeTrackingSettings:
    row = load_time_settings(db)
    for key in (
        "rounding_minutes", "allow_manual_entries",  # seit 1.9.61 ohne Standardpause
        "allow_group_bookings", "require_order_item", "require_activity",  # seit 1.9.224 ohne Zielsystem und Lohnarten (E8)
    ):
        setattr(row, key, getattr(payload, key))
    advanced = load_advanced_settings(db)  # seit 1.9.230 ohne „DATEV-Nr. = ERP-Nr.“ (entfallen; ein mitgeschickter Wert wird nicht übernommen)
    model_id = getattr(payload, "default_work_time_model_id", None)
    # Seit 1.9.14 (Regel 22): "aktiv" nur bei einem neu gewählten Modell prüfen -- ein inzwischen abgeschaltetes Standardmodell bleibt
    # gewählt, sonst ließen sich die Zeitregeln nach dem Abschalten gar nicht mehr speichern.
    if model_id is not None and model_id != advanced.default_work_time_model_id:
        model = db.get(WorkTimeModel, int(model_id))
        if model is None or not model.active:
            raise ValueError("Das gewählte Standard-Arbeitszeitmodell existiert nicht oder ist inaktiv.")
    advanced.default_work_time_model_id = model_id
    db.commit(); db.refresh(row)
    return row


def set_datev_nummern(db: Session, beraternummer: str | None, mandantennummer: str | None) -> TimeTrackingSettings:
    """Seit 1.9.92: Berater- und Mandantennummer (geprüft im Schema DatevNummernUpdate, leer = nicht eingetragen). Wer darf, entscheidet
    der Router (nur Admin)."""
    row = load_time_settings(db)
    row.datev_beraternummer, row.datev_mandantennummer = beraternummer, mandantennummer
    db.commit(); db.refresh(row)
    return row


def get_employee_payroll(db: Session, employee_id: int) -> EmployeePayrollSettings:
    """Lohnstammdaten eines Mitarbeiters, fehlend angelegt -- seit 1.8.84 nur im Schreibweg (set_employee_payroll())."""
    row = db.scalar(select(EmployeePayrollSettings).where(EmployeePayrollSettings.employee_id == employee_id))
    if row is None:
        row = EmployeePayrollSettings(employee_id=employee_id, payroll_export_enabled=True)
        db.add(row); db.commit(); db.refresh(row)
    return row


def load_employee_payroll(db: Session, employee_id: int) -> EmployeePayrollSettings:
    """Lohnstammdaten zum Lesen (seit 1.8.84, Regel 23): die gespeicherten, sonst die Vorgabe (Export an, ohne
    DATEV-Personalnummer), die nicht in die Sitzung geht. Bis 1.8.83 legten Lohnliste, DATEV-Export und Stundenzettel die Zeile
    beim Lesen an und committeten."""
    row = db.scalar(select(EmployeePayrollSettings).where(EmployeePayrollSettings.employee_id == employee_id))
    return row if row is not None else EmployeePayrollSettings(employee_id=employee_id, payroll_export_enabled=True, export_umfang="alles",
                                                                datev_personnel_number=None, azubi=False)


def effective_datev_personnel_number(db: Session, employee: Employee, payroll: EmployeePayrollSettings | None = None) -> str | None:
    """Die DATEV-Personalnummer der Person: die gespeicherte der Lohnstammdaten. Seit 1.9.230 (Stufe 6, R3a, Punkt 0a) nur diese -- bis 1.9.229
    nahm „DATEV-Nr. = ERP-Nr.“ die Mitarbeiternummer, die nie auf 5 Ziffern geprüft war (MA-0042 ging so in die Datei)."""
    payroll = payroll or load_employee_payroll(db, employee.id)
    return (payroll.datev_personnel_number or "").strip() or None


def _sollzeiten_aller(db: Session) -> dict[int, list[dict]]:
    """Seit 1.9.167: die eigenen Sollzeiten aller Personen in einer Abfrage (app/sollzeit.py::zeile_dict())."""
    from .models import EmployeeTargetHours
    from .sollzeit import zeile_dict
    je: dict[int, list[dict]] = {}
    for z in db.scalars(select(EmployeeTargetHours).order_by(EmployeeTargetHours.employee_id, EmployeeTargetHours.valid_from)).all():
        je.setdefault(z.employee_id, []).append(zeile_dict(z))
    return je


def _payroll_dict(db: Session, emp: Employee, p: EmployeePayrollSettings, sollzeiten: list[dict], gemerkt: list[str] | None = None,
                  traeger: dict[str, str] | None = None, ablage: dict[str, str] | None = None) -> dict:
    from .lohndatei import personalnummern_der_ablage
    ablage = personalnummern_der_ablage(db) if ablage is None else ablage
    heute = effective_datev_personnel_number(db, emp, p)
    gemerkt = fruehere_personalnummern(db).get(emp.id, []) if gemerkt is None else gemerkt
    fruehere = [n for n in gemerkt if n != heute]
    traeger = personalnummern_traeger(db, fruehere) if traeger is None else traeger
    return {
        "employee_id": emp.id,
        "employee_name": f"{emp.first_name} {emp.last_name}".strip(),
        "employee_number": emp.employee_number,
        "datev_personnel_number": heute,
        "datev_personnel_number_stored": p.datev_personnel_number,
        "payroll_export_enabled": p.payroll_export_enabled,
        "export_umfang": export_umfang(p),  # seit 1.9.168
        "eintritt": p.eintritt, "austritt": p.austritt,  # seit 1.9.167
        "azubi": bool(p.azubi),  # seit 1.9.224
        "sollzeiten": sollzeiten,
        "fruehere_personalnummern": fruehere,  # seit 1.9.177: gemerkte Nummern außer der heutigen -- dauerhaft gesperrt
        # seit 1.9.191: wer eine frühere Nummer heute trägt (sie lässt sich nicht freigeben) -- {Nummer: Name}, nur getragene
        "fruehere_traeger": {n: traeger[n] for n in fruehere if n in traeger},
        # seit 1.9.226: in welcher abgelegten Lohndatei eine frühere Nummer steht -- {Nummer: „MM/JJJJ“}, dort kein „freigeben“
        "fruehere_in_lohndatei": {n: ablage[n] for n in fruehere if n in ablage},
    }


def payroll_rows(db: Session) -> list[dict]:
    employees = db.scalars(select(Employee).order_by(Employee.active.desc(), Employee.last_name, Employee.first_name)).all()
    sollzeiten, gemerkt = _sollzeiten_aller(db), fruehere_personalnummern(db)
    traeger = personalnummern_traeger(db, [n for liste in gemerkt.values() for n in liste])  # seit 1.9.191, eine Abfrage für alle
    from .lohndatei import personalnummern_der_ablage
    ablage = personalnummern_der_ablage(db)  # seit 1.9.226, einmal für alle
    return [_payroll_dict(db, emp, load_employee_payroll(db, emp.id), sollzeiten.get(emp.id, []), gemerkt.get(emp.id, []), traeger, ablage)
            for emp in employees]


def set_employee_payroll(db: Session, employee_id: int, werte: dict) -> dict:
    """Seit 1.9.167 ein Teil-Update (Regel 22): nur die gesendeten Felder (bis 1.9.166 jedes, ein fehlendes Häkchen hieß „Export an“).
    Seit 1.9.168 erst alles prüfen, dann schreiben -- eine abgelehnte Anfrage lässt in der Sitzung nichts zurück. Seit 1.9.230 ohne
    „DATEV-Nr. = ERP-Nr.“ (bis 1.9.229 galt damit die ERP-Nummer, auch wenn keine Nummer mitkam)."""
    emp=db.get(Employee, employee_id)
    if emp is None: raise ValueError("Mitarbeiter wurde nicht gefunden.")
    row=db.scalar(select(EmployeePayrollSettings).where(EmployeePayrollSettings.employee_id == employee_id))
    # seit 1.9.168 der Export-Umfang; payroll_export_enabled folgt ihm (gelesen wird es nicht mehr) -- ein altes „Export an/aus“ wird „alles“/„nichts“
    umfang=export_umfang(row)
    if "export_umfang" in werte:
        if werte["export_umfang"] not in EXPORT_UMFAENGE:
            raise ValueError("Unbekannter Export-Umfang.")
        umfang=werte["export_umfang"]
    elif "payroll_export_enabled" in werte:
        umfang="alles" if werte["payroll_export_enabled"] else "nichts"
    exportiert=umfang != "nichts"
    neu={feld: werte[feld] for feld in ("eintritt", "austritt") if feld in werte}  # seit 1.9.167, leer = offen
    if "azubi" in werte:  # seit 1.9.224 (Lohn L1b, Punkt 1)
        neu["azubi"]=bool(werte["azubi"])
    if "datev_personnel_number" in werte:
        value=(werte.get("datev_personnel_number") or "").strip() or None
        if value and not personalnummer_gueltig(value):  # seit 1.9.168 nur Ziffern, seit 1.9.212 genau 5
            raise ValueError(PERSONALNUMMER_FALSCH)
        if value:
            duplicate=db.scalar(select(EmployeePayrollSettings).where(
                EmployeePayrollSettings.datev_personnel_number==value,
                EmployeePayrollSettings.employee_id!=employee_id,
            ))
            if duplicate is not None: raise ValueError(PERSONALNUMMER_VERGEBEN)
            gesperrt=personalnummer_gesperrt(db, value, employee_id)  # seit 1.9.177: auch eine frühere Nummer einer anderen Person
            if gesperrt: raise ValueError(gesperrt)
        neu["datev_personnel_number"]=value
    eintritt=neu.get("eintritt", row.eintritt if row is not None else None)
    austritt=neu.get("austritt", row.austritt if row is not None else None)
    if eintritt and austritt and austritt < eintritt:
        raise ValueError("Der Austritt liegt vor dem Eintritt.")
    if row is None:
        row=EmployeePayrollSettings(employee_id=employee_id)
        db.add(row)
    row.export_umfang, row.payroll_export_enabled = umfang, exportiert
    for feld, wert in neu.items():
        setattr(row, feld, wert)
    if neu.get("datev_personnel_number"):
        personalnummer_merken(db, neu["datev_personnel_number"], employee_id)  # seit 1.9.177, im selben Commit
    try:
        db.commit()
    except IntegrityError as exc:  # seit 1.9.168 eindeutig in der Datenbank: zwei gleichzeitige Speichern derselben Nummer
        db.rollback()
        raise ValueError(PERSONALNUMMER_VERGEBEN) from exc
    db.refresh(row)
    antwort = _payroll_dict(db, emp, row, _sollzeiten_aller(db).get(emp.id, []))
    antwort["nummernkreis"] = nummernkreis(antwort["datev_personnel_number"])  # seit 1.9.212: Hinweis beim Speichern, keine Sperre
    return antwort


def rounded_hours(hours: Decimal, rounding_minutes: int) -> Decimal:
    h=Decimal(hours or 0)
    if not rounding_minutes:
        return round_hours(h)
    step=Decimal(rounding_minutes)/Decimal(60)
    if step <= 0: return round_hours(h)
    return round_hours((h/step).quantize(Decimal("1"), rounding=ROUND_HALF_UP)*step)


def backoffice_summary(db: Session, start_date: date, end_date: date, employee_id: int | None = None) -> dict:
    """Kennzahlen und Stunden je Mitarbeiter. Seit 1.9.92 (Stufe 4, R5a, Punkt 5) jede Summe über tagessumme() -- dieselbe wie Stundenzettel
    und DATEV-Export, eine laufende Zeit zählt nicht mit (bis 1.9.91 eigene Summen über alle Zeilen)."""
    rows=list_entries(db, employee_id=employee_id, start_date=start_date, end_date=end_date, limit=None)
    by_employee=defaultdict(list); by_type=defaultdict(list)
    for r in rows:
        by_employee[r.employee_id].append(r); by_type[r.entry_type].append(r)
    employees=[]
    for emp_id,eigene in by_employee.items():
        emp=db.get(Employee,emp_id)
        employees.append({
            "employee_id":emp_id,"employee_name":f"{emp.first_name} {emp.last_name}" if emp else str(emp_id),
            "hours":round_hours(tagessumme(eigene)),"productive_hours":round_hours(tagessumme([r for r in eigene if r.counts_as_productive])),
            "travel_hours":round_hours(tagessumme([r for r in eigene if r.entry_type=="travel"])),"days":len({r.work_date for r in eigene}),
        })
    employees.sort(key=lambda x:x["employee_name"].casefold())
    return {
        "start_date":start_date,"end_date":end_date,"entry_count":len(rows),
        "total_hours":round_hours(tagessumme(rows)),"productive_hours":round_hours(tagessumme([r for r in rows if r.counts_as_productive])),
        "travel_hours":round_hours(tagessumme([r for r in rows if r.entry_type=="travel"])),"employee_count":len(by_employee),
        "by_type":{k:round_hours(tagessumme(v)) for k,v in by_type.items()},"employees":employees,
    }


def _fmt_h(value) -> str:
    return f"{round_hours(value):.2f}".replace(".",",")


def build_timesheet_pdf(db: Session, start_date: date, end_date: date, employee_id: int | None = None) -> bytes:
    type_labels=_entry_type_labels(db)
    rows=list_entries(db, employee_id=employee_id, start_date=start_date, end_date=end_date, limit=None)
    general=load_general_settings(db)
    grouped=defaultdict(list)
    for r in rows: grouped[r.employee_id].append(r)
    if employee_id and employee_id not in grouped:
        emp=db.get(Employee,employee_id)
        if emp: grouped[employee_id]=[]
    buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=landscape(A4),leftMargin=10*mm,rightMargin=10*mm,topMargin=11*mm,bottomMargin=12*mm,title="Stundenzettel")
    styles=getSampleStyleSheet(); body=ParagraphStyle("BodyDE",parent=styles["BodyText"],fontSize=8,leading=10); small=ParagraphStyle("Small",parent=body,fontSize=7,leading=9)
    story=[]
    for idx,(emp_id,entries) in enumerate(sorted(grouped.items(), key=lambda x: ((db.get(Employee,x[0]).last_name if db.get(Employee,x[0]) else ""),x[0]))):
        emp=db.get(Employee,emp_id); name=f"{emp.first_name} {emp.last_name}" if emp else str(emp_id)
        story.append(Paragraph(f"<b>{escape(general.company_name)}</b> – Stundenzettel", styles["Heading2"]))
        story.append(Paragraph(f"Mitarbeiter: <b>{escape(name)}</b> &nbsp;&nbsp; Zeitraum: {start_date.strftime('%d.%m.%Y')}–{end_date.strftime('%d.%m.%Y')}",body)); story.append(Spacer(1,3*mm))
        data=[["Datum","Projekt / Auftrag","LV-Position","Zeitart","Tätigkeit","von","bis","Pause","Stunden"]]
        total=tagessumme(entries)  # seit 1.9.92 dieselbe Summe wie Übersicht und DATEV-Export (eine laufende Zeit zählt nicht mit)
        for r in sorted(entries,key=lambda x:(x.work_date,x.started_at or x.created_at,x.id)):
            d=entry_to_dict(r)
            data.append([r.work_date.strftime("%d.%m.%Y"),Paragraph(escape(f"{d.get('project_number') or ''} / {d.get('order_number') or ''}"),small),Paragraph(escape((d.get('order_item_oz') or '')+' '+(d.get('order_item_text') or '')),small),type_labels.get(r.entry_type,r.entry_type),Paragraph(escape(r.activity or ''),small),r.started_at.strftime("%H:%M") if r.started_at else "",r.ended_at.strftime("%H:%M") if r.ended_at else "",str(r.break_minutes or 0),_fmt_h(r.hours)])
        data.append(["","","","","","","","Summe",_fmt_h(total)])
        t=Table(data,colWidths=[21*mm,42*mm,55*mm,24*mm,42*mm,17*mm,17*mm,17*mm,20*mm],repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e8eee9")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7.5),("GRID",(0,0),(-1,-1),.25,colors.HexColor("#cccccc")),("VALIGN",(0,0),(-1,-1),"TOP"),("ALIGN",(-1,1),(-1,-1),"RIGHT"),("FONTNAME",(-2,-1),(-1,-1),"Helvetica-Bold")]))
        story.append(t); story.append(Spacer(1,6*mm)); story.append(Paragraph("Unterschrift Mitarbeiter: ________________________________     Prüfung Backoffice: ________________________________",body))
        if idx < len(grouped)-1: story.append(PageBreak())
    if not grouped: story.append(Paragraph("Keine Zeitbuchungen im gewählten Zeitraum.",body))
    doc.build(story); return buf.getvalue()


def build_time_csv(db: Session, start_date: date, end_date: date, employee_id: int | None = None) -> bytes:
    type_labels=_entry_type_labels(db)
    out=StringIO(newline=""); w=csv.writer(out,delimiter=";",lineterminator="\r\n")
    w.writerow(["Mitarbeiternummer","Mitarbeiter","Datum","Projekt","Auftrag","LV-OZ","Zeitart","Tätigkeit","von","bis","Pause_Min","Stunden","Notiz"])
    for r in list_entries(db,employee_id=employee_id,start_date=start_date,end_date=end_date,limit=None):
        d=entry_to_dict(r); emp=r.employee
        w.writerow([emp.employee_number or "",d["employee_name"],r.work_date.strftime("%d.%m.%Y"),d.get("project_number") or "",d.get("order_number") or "",d.get("order_item_oz") or "",type_labels.get(r.entry_type,r.entry_type),r.activity or "",r.started_at.strftime("%H:%M") if r.started_at else "",r.ended_at.strftime("%H:%M") if r.ended_at else "",r.break_minutes,_fmt_h(r.hours),r.notes or ""])
    return ("\ufeff"+out.getvalue()).encode("utf-8")


_ENTRY_TYPE_FALLBACK_LABELS = {
    "site": "Baustellenzeit", "travel": "Fahrzeit", "workshop": "Werkstattzeit",
    "other": "Sonstige Arbeitszeit", "weather_winter": "Schlechtwetter Winter",
    "weather_summer": "Schlechtwetter Sommer",
}


def _entry_type_labels(db: Session) -> dict[str, str]:
    """Bezeichnung je Zeitart für den Stundenzettel/CSV-Export -- ohne diese Auflösung stünde
    dort z. B. der rohe interne Wert "weather_winter" statt "Schlechtwetter Winter".

    Seit 1.8.8 einmal je Lauf statt je Zeile (vorher Abfragen je Buchung)."""
    from .option_settings import get_option_group
    group = get_option_group(db, "time_entry_types")
    configured = {}
    for option in (group.options if group else []):
        configured.setdefault(option.value, option.label)  # doppelter Wert: wie bisher gilt die erste Option
    return {**_ENTRY_TYPE_FALLBACK_LABELS, **configured}


class DatevExportGesperrt(ValueError):
    """Seit 1.9.92 (Stufe 4, R5a, Punkt 5): kein Export -- der Text für die Meldung, dazu die Liste dessen, was fehlt (leer: der Zeitraum
    ist nicht abgeschlossen)."""

    def __init__(self, meldung: str, liste: list[dict] | None = None):
        super().__init__(meldung)
        self.liste = liste or []


def datev_fehlt(db: Session, start_date: date, end_date: date, *, personen=None) -> list[dict]:
    """Seit 1.9.92: was dem DATEV-Export für den Monat fehlt -- Personalnummern, Berater- und Mandantennummer. Leer = vollständig. Je Eintrag art
    und ein Text. Seit 1.9.230 auch eine Personalnummer ohne genau 5 Ziffern (art „personalnummer_format“). Seit 1.9.225 (Lohn L1b, Punkt 2) die Personalnummer von jedem, der eine Zeile in der Lohndatei bekäme (app/lohndatei.py::
    berechnen(), auch nur mit Abwesenheiten, Ausfalltagen, Heiligabend oder Silvester; bis 1.9.224 nur von Personen mit Buchungen und Umfang
    „alles“), nach Nachnamen; seit 1.9.224 ohne die Lohnart je Zeitart. personen: das Ergebnis von berechnen(), wenn der Aufrufer es schon hat."""
    from .lohndatei import berechnen

    settings = load_time_settings(db)
    personen = personen if personen is not None else berechnen(db, start_date.replace(day=1))
    liste: list[dict] = []
    for x in sorted(personen, key=lambda x: (x.nachname.casefold(), x.employee_id)):
        if not x.zeilen:
            continue
        if not x.personalnummer:
            liste.append({"art": "personalnummer", "employee_id": x.employee_id, "name": x.name, "text": f"Personalnummer fehlt: {x.name}"})
        elif not personalnummer_gueltig(x.personalnummer):
            # seit 1.9.230 (Stufe 6, R3a, Punkt 0a): eine gespeicherte Nummer ohne genau 5 Ziffern (vor 1.9.212 gespeichert, von der Migration
            # 5d2e8a71c4f3 nicht aufgefüllt) sperrt die Datei wie eine fehlende -- bis 1.9.229 ging sie so hinein
            liste.append({"art": "personalnummer_format", "employee_id": x.employee_id, "name": x.name,
                          "text": f"Personalnummer „{x.personalnummer}“ hat nicht genau 5 Ziffern: {x.name}"})
    fehlen = [n for n, wert in (("Beraternummer", settings.datev_beraternummer), ("Mandantennummer", settings.datev_mandantennummer)) if not wert]
    if fehlen:
        liste.append({"art": "datev_nummern", "text": (" und ".join(fehlen) + (" fehlen" if len(fehlen) > 1 else " fehlt"))})
    return liste


NUR_EIN_MONAT = "Die Lohndatei gibt es nur für einen ganzen Monat (vom Ersten bis zum Letzten)."


def build_datev_export(db: Session, start_date: date, end_date: date) -> tuple[bytes, str]:
    """Die Lohndatei für DATEV Lohn und Gehalt (seit 1.9.224, Lohn L1b, Punkt 1: app/lohndatei.py; bis 1.9.223 Lohn und Gehalt als CSV oder
    LODAS, E8). Ein ganzer Monat (sonst ValueError), nur abgeschlossen (end_date bis zum Abschluss) und vollständig (datev_fehlt() leer) --
    sonst DatevExportGesperrt, keine Datei (seit 1.9.92); seit 1.9.225 verlangt datev_fehlt() die Personalnummer jeder Person mit einer Zeile."""
    from .lohndatei import berechnen, datei, monat_ende

    if start_date.day != 1 or end_date != monat_ende(start_date):
        raise ValueError(NUR_EIN_MONAT)
    settings = load_time_settings(db)
    lock = settings.locked_until
    if lock is None or end_date > lock:
        stand = f"abgeschlossen ist bis {lock:%d.%m.%Y}" if lock is not None else "noch ist nichts abgeschlossen"
        raise DatevExportGesperrt(f"Der DATEV-Export geht nur für abgeschlossene Zeiträume – {stand}.")
    personen = berechnen(db, start_date)
    fehlt = datev_fehlt(db, start_date, end_date, personen=personen)  # seit 1.9.225 jede Person mit einer Zeile (bis 1.9.224 eine zweite Prüfung hier)
    if fehlt:
        raise DatevExportGesperrt("Kein DATEV-Export: " + "; ".join(x["text"] for x in fehlt) + ".", fehlt)
    return datei(settings.datev_beraternummer, settings.datev_mandantennummer, start_date, personen), "txt"


def lohndatei_erzeugen(db: Session, erster: date, *, user_id: int | None, user_name: str | None):
    """Seit 1.9.226 (Lohn L1b, Punkt 3): die Lohndatei des Monats erzeugen (build_datev_export(), dieselben Prüfungen) und ablegen -- jede erzeugte
    Datei bleibt auf dem Server (app/lohndatei.py::ablegen()); bis 1.9.225 ging sie nur an den Browser. Committet."""
    from .lohndatei import ablegen, monat_ende

    erster = erster.replace(day=1)
    inhalt, ext = build_datev_export(db, erster, monat_ende(erster))
    row = ablegen(db, erster, inhalt, f"DATEV_Lohndaten_{erster:%Y-%m}.{ext}", user_id=user_id, user_name=user_name)
    db.commit()
    db.refresh(row)
    return row
