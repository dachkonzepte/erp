"""Testhelfer seit 1.11.47: eine erfundene Webseite in den Unternehmensdaten.

Impressum und Datenschutz sind im Kundenportal Pflicht (Entscheidung des Betriebs 27.11.2026): ohne gültige Webseite gehen Modul einschalten, Portal am
Kunden einschalten und Link senden nicht (409, app/kundenportal.py::pflicht_grund()), und das Portal zeigt statt jeder Seite „Gerade klappt etwas nicht“.
Testdaten, die das Portal einschalten oder einen Link senden, tragen deshalb eine Webseite ein -- erfunden, unter der reservierten Endung .example.
"""

from app.settings import load_general_settings

WEBSEITE = "www.muster-bedachung.example"


def webseite_setzen(db, host: str = WEBSEITE) -> None:
    s = load_general_settings(db)
    s.website = host
    db.commit()
