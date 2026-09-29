"""Geschäftsdatum und Uhrzeit in Europe/Berlin: die eine Stelle für "jetzt" und "heute" (seit 1.8.12).

Der Server läuft in UTC (timedatectl: Etc/UTC), der Entwicklungsrechner in deutscher Zeit.
date.today() und datetime.now() liefern die Zeit des Rechners: auf dem Server bis 1 Uhr (Winter)
bzw. 2 Uhr (Sommer) noch den Vortag, in der Silvesternacht das alte Jahr. Lokal fällt das nicht
auf. Deshalb fragt app/ "heute" und "jetzt" ausschließlich hier ab; tests/test_v316_berlin_time.py
sucht app/ nach date.today() und datetime.now() ohne Zeitzone ab.

Zwei Arten gespeicherter Zeit, nicht verwechseln:
- Zeitstempel (created_at, signed_at, completed_at, ... aus datetime.utcnow()) sind naive UTC und
  bleiben es. Für die Anzeige rechnet to_berlin() sie um.
- Geschäftszeiten, die ein Mensch als Ortszeit meint (Beginn/Ende einer Zeitbuchung, Termine,
  Datumsfelder), sind naive Ortszeit. berlin_now() liefert genau so einen Wert.

Die Kalender-Synchronisation (app/outlook_calendar_sync.py) hat ihre eigene, gleichwertige
Umrechnung und bleibt bewusst unangetastet.
"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")


def _utc_now() -> datetime:
    """Die einzige Uhr. Tests setzen hier eine feste Zeit ein."""
    return datetime.now(timezone.utc)


def berlin_now() -> datetime:
    """Jetzt als naive Ortszeit Europe/Berlin, sekundengenau."""
    return _utc_now().astimezone(BERLIN).replace(tzinfo=None, microsecond=0)


def berlin_today() -> date:
    """Heute in Europe/Berlin -- das Geschäftsdatum."""
    return berlin_now().date()


def to_berlin(value: datetime | None) -> datetime | None:
    """Gespeicherten Zeitstempel für die Anzeige in naive Ortszeit umrechnen. Naive Werte gelten
    als UTC (so schreibt sie datetime.utcnow()), zeitzonenbewusste werden umgerechnet."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BERLIN).replace(tzinfo=None)
