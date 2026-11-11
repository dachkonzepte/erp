"""Sollzeit einer Person an einem Tag -- seit 1.9.167 (Lohn L1a, Punkt 2, Entscheidungen Tobias E3 und E4).

Die eine Rechnung: soll(db, Person, Tag). Daraus nimmt der Export die Stunden von Urlaub, Krankheit und Feiertag (L1b), der Ausfalltag
Schlechtwetter lehnt Tage ohne Soll ab (Punkt 5), der halbe Urlaubstag zählt die halbe Sollzeit (Punkt 6).

    Tarif         Montag bis Freitag die Soll-Arbeitszeit des Arbeitszeitmodells, das an dem Tag für die Person gilt
                  (app/work_time_models.py::employee_model(), ISO-Kalenderwoche: Sommer KW 18–48 8,00 h, Winter KW 49–17 7,50 h,
                  Tarif Dachdecker), Samstag und Sonntag 0.
    eigene Werte  je Person ab einem Tag (EmployeeTargetHours.valid_from) sieben Werte Montag bis Sonntag, z. B. Teilzeit an Di, Mi, Do; es
                  gilt die jüngste Zeile, die am Tag schon begonnen hat. Eine Zeile ohne Werte heißt „ab hier wieder Tarif“.
    Eintritt      vor dem Eintritt und nach dem Austritt (EmployeePayrollSettings.eintritt/austritt) ist die Sollzeit 0.
    Kalender      seit 1.9.175 geht ein Tag des Arbeitszeitkalenders mit eigener Sollzeit Tarif und eigenen Werten vor (Heiligabend 7,00 h für
                  gewerbliche Mitarbeiter, app/arbeitszeitkalender.py) -- seit 1.9.180 nur, wo Tarif bzw. eigene Werte an dem Tag Sollzeit
                  ergäben; dann voll, nicht anteilig.

Ein Feiertag ändert die Sollzeit nicht -- die Zeile F trägt die Sollzeit des Wochentags (E3). Wer eine Zeile anlegt oder löscht, ändert nie
einen abgeschlossenen Zeitraum: „gültig ab“ liegt nach „Abgeschlossen bis“ (sonst 409).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Employee, EmployeePayrollSettings, EmployeeTargetHours, TimeTrackingSettings
from .rounding import round_hours
from .work_time_models import employee_model

WOCHENTAGE = ("montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag")
WOCHENTAG_KURZ = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
NULL = Decimal("0")


class SollzeitGesperrt(ValueError):
    """Die Zeile träfe einen abgeschlossenen Zeitraum (409)."""


def _payroll(db: Session, employee_id: int) -> EmployeePayrollSettings | None:
    return db.scalar(select(EmployeePayrollSettings).where(EmployeePayrollSettings.employee_id == employee_id))


def beschaeftigt_am(payroll: EmployeePayrollSettings | None, tag: date) -> bool:
    """Zwischen Eintritt und Austritt (beide Tage eingeschlossen); fehlt ein Datum, gilt es als offen."""
    if payroll is None:
        return True
    return (payroll.eintritt is None or tag >= payroll.eintritt) and (payroll.austritt is None or tag <= payroll.austritt)


def zeilen(db: Session, employee_id: int) -> list[EmployeeTargetHours]:
    return list(db.scalars(select(EmployeeTargetHours).where(EmployeeTargetHours.employee_id == employee_id)
                           .order_by(EmployeeTargetHours.valid_from)).all())


def _eigene_zeile(reihe: list[EmployeeTargetHours], tag: date) -> EmployeeTargetHours | None:
    gilt = None
    for z in reihe:
        if z.valid_from <= tag:
            gilt = z
    return gilt


def ist_tarif(zeile: EmployeeTargetHours | None) -> bool:
    return zeile is None or all(getattr(zeile, w) is None for w in WOCHENTAGE)


def tarif(db: Session, employee_id: int, tag: date) -> Decimal:
    """Montag bis Freitag die Soll-Arbeitszeit des Modells, das an dem Tag gilt; Samstag und Sonntag 0."""
    if tag.weekday() >= 5:
        return NULL
    modell = employee_model(db, employee_id, tag)
    return Decimal(str(modell.daily_target_hours)) if modell is not None and modell.daily_target_hours is not None else NULL


def soll(db: Session, employee_id: int, tag: date) -> Decimal:
    """Die Sollzeit der Person an diesem Tag in Stunden."""
    return soll_zeitraum(db, employee_id, tag, tag)[tag]


def soll_zeitraum(db: Session, employee_id: int, start: date, ende: date) -> dict[date, Decimal]:
    """Die Sollzeit je Tag von start bis ende in Stunden mit zwei Stellen -- eine Abfrage für Lohnstammdaten und eigene Werte, das Modell je
    Kalenderwoche (es hängt nur an der Woche; seit 1.9.171 zwischengespeichert, bis 1.9.170 je Tag nachgeschlagen). Seit 1.9.211 über
    soll_fuer_personen() -- eine Rechnung für eine wie für viele Personen."""
    return soll_fuer_personen(db, [employee_id], start, ende)[employee_id]


def soll_fuer_personen(db: Session, employee_ids, start: date, ende: date) -> dict[int, dict[date, Decimal]]:
    """Seit 1.9.211 (L1a Stufe 5, Punkt 4: die Plantafel rechnet mit der Sollzeit): die Sollzeit vieler Personen je Tag von start bis ende --
    dieselbe Rechnung wie bisher soll_zeitraum() je Person, mit je einer Abfrage für Lohnstammdaten, eigene Werte, Gruppen und Zuordnung der
    Modelle für alle; das Modell je Zuordnung und Kalenderwoche einmal (app/work_time_models.py::modell_fuer_zuordnung())."""
    from datetime import timedelta

    from .arbeitszeitkalender import aktive, fuer_tag
    from .work_time_models import modell_fuer_zuordnung, zuordnungen

    ids = list(dict.fromkeys(int(i) for i in employee_ids))
    if not ids:
        return {}
    payrolls = {p.employee_id: p for p in db.scalars(select(EmployeePayrollSettings).where(EmployeePayrollSettings.employee_id.in_(ids)))}
    reihen: dict[int, list[EmployeeTargetHours]] = {i: [] for i in ids}
    for z in db.scalars(select(EmployeeTargetHours).where(EmployeeTargetHours.employee_id.in_(ids)).order_by(EmployeeTargetHours.valid_from)):
        reihen[z.employee_id].append(z)
    gruppen = dict(db.execute(select(Employee.id, Employee.employee_group).where(Employee.id.in_(ids))).all())
    modelle = zuordnungen(db, ids)
    # seit 1.9.175 (L1a-Nachtrag, Punkt 2): ein Tag des Arbeitszeitkalenders mit eigener Sollzeit (Heiligabend 7,00 h) geht Tarif und eigenen
    # Werten vor; seit 1.9.180 (L1a-Korrekturen, Punkt 1) nur, wo die Person an dem Tag ohne ihn Sollzeit hätte -- dann voll, nicht anteilig
    # (Teilzeit am Donnerstag mit 3,00 h: 7,00 h; ohne Sollzeit am Wochentag: 0, keine Freistellung)
    kalender = [e for e in aktive(db) if e.sollzeit is not None]
    je_woche: dict[tuple[int | None, int, int], Decimal] = {}
    ergebnis: dict[int, dict[date, Decimal]] = {}
    for eid in ids:
        payroll, reihe, gruppe, zuordnung = payrolls.get(eid), reihen[eid], gruppen.get(eid), modelle[eid]
        tage: dict[date, Decimal] = {}
        tag = start
        while tag <= ende:
            if not beschaeftigt_am(payroll, tag):
                tage[tag] = round_hours(NULL)
            else:
                eigene = _eigene_zeile(reihe, tag)
                if not ist_tarif(eigene):
                    wert = Decimal(str(getattr(eigene, WOCHENTAGE[tag.weekday()])))
                elif tag.weekday() >= 5:
                    wert = NULL
                else:
                    schluessel = (zuordnung, *tag.isocalendar()[:2])
                    if schluessel not in je_woche:
                        modell = modell_fuer_zuordnung(db, zuordnung, tag)
                        je_woche[schluessel] = (Decimal(str(modell.daily_target_hours))
                                                if modell is not None and modell.daily_target_hours is not None else NULL)
                    wert = je_woche[schluessel]
                kalendertag = fuer_tag(kalender, tag, gruppe) if kalender and wert > 0 else None
                if kalendertag is not None:
                    wert = Decimal(str(kalendertag.sollzeit))
                tage[tag] = round_hours(wert)
            tag += timedelta(days=1)
        ergebnis[eid] = tage
    return ergebnis


def soll_an_tagen(db: Session, employee_id: int, tage: list[date]) -> dict[date, Decimal]:
    """Seit 1.9.188: die Sollzeit an einzelnen Tagen -- je Gruppe naher Tage (höchstens 14 Tage vom ersten) ein soll_zeitraum(), nicht über
    alle Tage dazwischen (die Plantafel fragt Heiligabend und Silvester über bis zu zwei Jahre)."""
    from datetime import timedelta

    ergebnis: dict[date, Decimal] = {}
    reihe = sorted(set(tage))
    i = 0
    while i < len(reihe):
        j = i
        while j + 1 < len(reihe) and reihe[j + 1] - reihe[i] <= timedelta(days=14):
            j += 1
        werte = soll_zeitraum(db, employee_id, reihe[i], reihe[j])
        ergebnis.update({t: werte[t] for t in reihe[i:j + 1]})
        i = j + 1
    return ergebnis


HALB = Decimal("0.5")


def anteil(halber_tag: bool = False) -> Decimal:
    """Welcher Teil des Tags eine Abwesenheit ist: ein halber Urlaubstag 0,5, sonst 1. Seit 1.9.174 (L1a-Nachtrag, Punkt 1) ohne die
    Halbierung von Urlaub am 24.12. und 31.12. (1.9.171–1.9.173 je 0,5, Festlegung 1.9.171 Nr. 2 zurückgezogen)."""
    return HALB if halber_tag else Decimal("1")


def abwesenheit_tage(db: Session, employee_id: int, start: date, ende: date, *, kategorie: str | None, halber_tag: bool = False,
                     feiertage: dict | None = None, kalendertag_urlaub: bool | None = None, soll: dict[date, Decimal] | None = None,
                     kalender: dict | None = None) -> dict:
    """Seit 1.9.171 (Lohn L1a, Punkt 6): wie viele Tage und Stunden eine Abwesenheit zählt -- nur Tage mit Sollzeit, ohne gesetzliche
    Feiertage (dort gilt der Feiertag), je Tag mit ihrem Anteil (anteil(): ein halber Urlaubstag 0,5). Stunden = Sollzeit × Anteil.
    feiertage: {Tag: Name} des Bundeslands, sonst hier gelesen. Für die Anzeige („2,5 Arbeitstage“), das Urlaubskonto (L2) und den Export
    (L1b). kalendertag_urlaub: seit 1.9.176 die Antwort auf die Rückfrage an einem Kalendertag mit Rückfrage (Silvester) -- im Urlaub zählt er
    als ganzer Tag, außer bei False (frei); leer gilt wie der Vorschlag. soll und kalender: seit 1.9.308 (Lohn L2a, Punkt 1) die Sollzeit je Tag
    und die Kalendertage der Person ({Tag: Eintrag}, app/arbeitszeitkalender.py::kalendertage_aus()), wenn der Aufrufer sie schon hat -- dann ohne
    Abfrage (app/tagesbilanz.py); beide dürfen über den Zeitraum hinausreichen."""
    from .arbeitszeitkalender import als_urlaubstag, kalendertage_im_zeitraum

    if feiertage is None:
        from .planning import automatic_public_holidays, load_region_settings  # lokal: planning importiert viel
        feiertage = automatic_public_holidays(load_region_settings(db).federal_state_code, range(start.year, ende.year + 1))
    # seit 1.9.175 (L1a-Nachtrag, Punkt 2): an einem Tag des Arbeitszeitkalenders gilt seine Abwesenheit (Heiligabend: bezahlte Freistellung) --
    # eine andere Abwesenheit über den Tag zählt ihn nicht, ein Urlaub dort ist kein Urlaubstag; seit 1.9.176 außer an einem Tag mit Rückfrage
    # (Silvester), den der Urlaub als ganzen Urlaubstag nimmt
    if soll is None:
        soll = soll_zeitraum(db, employee_id, start, ende)
    else:
        soll = {t: s for t, s in soll.items() if start <= t <= ende}
    if kalender is None:
        kalender = {t: e for t, e in kalendertage_im_zeitraum(db, employee_id, start, ende, soll=soll)}
    tage, stunden, je_tag = Decimal("0"), Decimal("0"), []
    for tag, soll_tag in soll.items():
        if soll_tag <= 0 or tag in feiertage:
            continue
        if tag in kalender and not (kategorie == "urlaub" and kalender[tag].im_urlaub == "fragen" and als_urlaubstag(kalendertag_urlaub)):
            continue
        a = anteil(halber_tag)
        tage += a
        stunden += round_hours(soll_tag * a)
        je_tag.append({"tag": tag, "anteil": a, "stunden": round_hours(soll_tag * a)})
    return {"tage": tage, "stunden": round_hours(stunden), "je_tag": je_tag}


def zeile_dict(z: EmployeeTargetHours) -> dict:
    werte = None if ist_tarif(z) else {w: getattr(z, w) for w in WOCHENTAGE}
    return {"id": z.id, "employee_id": z.employee_id, "valid_from": z.valid_from, "tarif": werte is None, "werte": werte,
            "text": text(z)}


def text(z: EmployeeTargetHours | None) -> str:
    """„Tarif“ oder „Di–Do 3,00 h“ bzw. „Mo 8,00 · Di 8,00 … h“ -- kurz für die Liste."""
    if ist_tarif(z):
        return "Tarif"
    werte = [Decimal(str(getattr(z, w))) for w in WOCHENTAGE]
    teile = [f"{WOCHENTAG_KURZ[i]} {str(round_hours(werte[i])).replace('.', ',')}" for i in range(7) if werte[i] > 0]
    return " · ".join(teile) + " h" if teile else "keine Sollzeit"


def _abgeschlossen_bis(db: Session) -> date | None:
    row = db.get(TimeTrackingSettings, 1)
    return row.locked_until if row is not None else None


def zeile_anlegen(db: Session, employee_id: int, valid_from: date, werte: dict[str, Decimal] | None) -> EmployeeTargetHours:
    """Eigene Werte ab valid_from (werte = None: ab hier wieder Tarif). Nur nach „Abgeschlossen bis“; je Person und Tag eine Zeile (eine
    vorhandene für denselben Tag wird ersetzt). Committet."""
    if db.get(Employee, employee_id) is None:
        raise LookupError("Mitarbeiter wurde nicht gefunden.")
    bis = _abgeschlossen_bis(db)
    if bis is not None and valid_from <= bis:
        raise SollzeitGesperrt(f"„Gültig ab“ muss nach dem Abschluss liegen (abgeschlossen bis {bis:%d.%m.%Y}) – ein abgeschlossener Zeitraum "
                               "bleibt, wie er abgerechnet ist.")
    if werte is not None:
        for w in WOCHENTAGE:
            wert = Decimal(str(werte.get(w) if werte.get(w) is not None else 0))
            if wert < 0 or wert > 24:
                raise ValueError("Die Sollzeit eines Tags liegt zwischen 0 und 24 Stunden.")
    zeile = db.scalar(select(EmployeeTargetHours).where(EmployeeTargetHours.employee_id == employee_id,
                                                        EmployeeTargetHours.valid_from == valid_from))
    if zeile is None:
        zeile = EmployeeTargetHours(employee_id=employee_id, valid_from=valid_from)
        db.add(zeile)
    for w in WOCHENTAGE:
        setattr(zeile, w, None if werte is None else Decimal(str(werte.get(w) if werte.get(w) is not None else 0)))
    db.commit()
    db.refresh(zeile)
    return zeile


def zeile_loeschen(db: Session, zeile_id: int) -> None:
    zeile = db.get(EmployeeTargetHours, zeile_id)
    if zeile is None:
        raise LookupError("Die Sollzeit wurde nicht gefunden.")
    bis = _abgeschlossen_bis(db)
    if bis is not None and zeile.valid_from <= bis:
        raise SollzeitGesperrt(f"Diese Sollzeit gilt schon in einem abgeschlossenen Zeitraum (abgeschlossen bis {bis:%d.%m.%Y}) – sie bleibt. Ab "
                               "einem späteren Tag lässt sich eine neue eintragen.")
    db.delete(zeile)
    db.commit()
