"""Sollzeit einer Person an einem Tag -- seit 1.9.167 (Lohn L1a, Punkt 2, Entscheidungen Tobias E3 und E4).

Die eine Rechnung: soll(db, Person, Tag). Daraus nimmt der Export die Stunden von Urlaub, Krankheit und Feiertag (L1b), der Ausfalltag
Schlechtwetter lehnt Tage ohne Soll ab (Punkt 5), der halbe Urlaubstag zählt die halbe Sollzeit (Punkt 6).

    Tarif         Montag bis Freitag die Soll-Arbeitszeit des Arbeitszeitmodells, das an dem Tag für die Person gilt
                  (app/work_time_models.py::employee_model(), ISO-Kalenderwoche: Sommer KW 18–48 8,00 h, Winter KW 49–17 7,50 h,
                  Tarif Dachdecker), Samstag und Sonntag 0.
    eigene Werte  je Person ab einem Tag (EmployeeTargetHours.valid_from) sieben Werte Montag bis Sonntag, z. B. Teilzeit an Di, Mi, Do; es
                  gilt die jüngste Zeile, die am Tag schon begonnen hat. Eine Zeile ohne Werte heißt „ab hier wieder Tarif“.
    Eintritt      vor dem Eintritt und nach dem Austritt (EmployeePayrollSettings.eintritt/austritt) ist die Sollzeit 0.

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
    """Die Sollzeit je Tag von start bis ende in Stunden mit zwei Stellen -- eine Abfrage für Lohnstammdaten und eigene Werte, das Modell je Tag."""
    from datetime import timedelta

    payroll = _payroll(db, employee_id)
    reihe = zeilen(db, employee_id)
    ergebnis: dict[date, Decimal] = {}
    tag = start
    while tag <= ende:
        if not beschaeftigt_am(payroll, tag):
            ergebnis[tag] = round_hours(NULL)
        else:
            eigene = _eigene_zeile(reihe, tag)
            ergebnis[tag] = round_hours(tarif(db, employee_id, tag) if ist_tarif(eigene) else Decimal(str(getattr(eigene, WOCHENTAGE[tag.weekday()]))))
        tag += timedelta(days=1)
    return ergebnis


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
