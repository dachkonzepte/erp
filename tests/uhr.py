"""Feste Uhr für Tests, deren Ergebnis sonst von der Tageszeit abhinge (seit 1.8.36).

Ab MobileSettings.shift_end_time (Vorgabe 19:00) meldet GET /api/field-view/today den Monteur ab
(401 "Feierabend"). Tests, die diesen Endpunkt als Monteur aufrufen, waren deshalb abends rot --
eine volle Suite nach 19 Uhr nie ganz grün (1.8.35, Nebenbefund 3).

uhr_festhalten() setzt die eine Uhr der App (app.berlin_time._utc_now, siehe dort) auf eine
laufende Uhr, die heute um `uhrzeit` (Europe/Berlin) beginnt. "Heute" kommt von der Uhr, die
vorher galt -- der echten oder der mit --wanduhr vorgetäuschten (tests/conftest.py). Die Uhr läuft
weiter, damit Dauer und Reihenfolge innerhalb eines Tests stimmen.

Verwendung: die Fixture `feste_uhr` (tests/conftest.py) in einem Test, oder
`with uhr_festhalten():` in einer Fixture mit größerem Geltungsbereich (Modul-Fixtures können
keine Funktions-Fixture nutzen, siehe tests/test_v326_monteur_datengrenze.py).

Nicht betroffen: gespeicherte Zeitstempel aus datetime.utcnow() (created_at u. a.) -- sie laufen
weiter mit der echten Zeit, wie im Betrieb neben einer Ortszeit, die nur über berlin_time kommt.
"""

import time as _time
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone

from app import berlin_time

STANDARD_UHRZEIT = time(10, 0)


def arbeitstag_ab(tag: date) -> date:
    """Seit 1.9.242 (Stufe 6, R3b, Punkt 4): der Tag selbst, wenn an ihm gearbeitet wird -- Montag bis Freitag, kein gesetzlicher Feiertag in NRW
    (die Vorgabe der Planung, app/planning.py::automatic_public_holidays()) --, sonst der nächste solche Tag. „Heute“ zeigt den Einsatz nur an einem
    Arbeitstag; ein Test mit laufender Uhr ab heute wäre sonst am Wochenende und an einem Feiertag rot."""
    from app.planning import automatic_public_holidays
    while tag.weekday() >= 5 or tag in automatic_public_holidays("NW", [tag.year]):
        tag += timedelta(days=1)
    return tag


@contextmanager
def uhr_festhalten(uhrzeit: time = STANDARD_UHRZEIT, tag: date | None = None):
    """tag (seit 1.9.166, Lohn L1a): die Uhr beginnt an diesem Tag statt heute -- für Tests mit festen Tagen, deren Ergebnis nicht am Lauftag
    hängen soll (Fixture `fester_tag`). Ohne tag seit 1.9.242 heute, an einem Tag ohne Arbeit der nächste Arbeitstag (arbeitstag_ab())."""
    heute = tag or arbeitstag_ab(berlin_time.berlin_today())
    start = datetime.combine(heute, uhrzeit, tzinfo=berlin_time.BERLIN).astimezone(timezone.utc)
    beginn = _time.monotonic()
    vorher = berlin_time._utc_now
    berlin_time._utc_now = lambda: start + timedelta(seconds=_time.monotonic() - beginn)
    try:
        yield start
    finally:
        berlin_time._utc_now = vorher
