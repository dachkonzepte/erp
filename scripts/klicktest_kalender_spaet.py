"""Klicktest: Kalender spät abends (1.9.148, Stufe 6, R1, Punkt 6, P6) -- Termin 23:30 im Winter und 22:30 im Sommer in Tag-, Wochen- und Monatsansicht.

Bis 1.9.147 schickte die Seite den Zeitraum als UTC („22:00Z“ für Mitternacht im Sommer); ein Termin ab 22 bzw. 23 Uhr fehlte in der Tagesansicht und am letzten Tag der Woche. Befüllt:
Termine Do 15.01.2026 23:30, So 18.01.2026 23:30 (letzter Tag der Woche), Sa 31.01.2026 23:30 (letzter Tag des Monats), Mi 15.07.2026 22:30, So 19.07.2026 22:30, Fr 31.07.2026 22:30, dazu
je einer um 00:15 am Folgetag, der nicht in den Tag gehört. Geprüft im Browser in Berlin und einmal mit der Zeitzone UTC: Eintrag im Raster jeder Ansicht.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_kalender_spaet.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

UHR_MS = int(datetime(2026, 10, 14, 10, 0, tzinfo=ZoneInfo("Europe/Berlin")).timestamp() * 1000)
TERMINE = [
    ("Winter Donnerstag", (2026, 1, 15, 23, 30)), ("Winter Sonntag", (2026, 1, 18, 23, 30)), ("Winter Monatsende", (2026, 1, 31, 23, 30)),
    ("Sommer Mittwoch", (2026, 7, 15, 22, 30)), ("Sommer Sonntag", (2026, 7, 19, 22, 30)), ("Sommer Monatsende", (2026, 7, 31, 22, 30)),
    ("Winter Folgetag", (2026, 1, 16, 0, 15)), ("Sommer Folgetag", (2026, 7, 16, 0, 15)),
]


def befuellen(db, k):
    from datetime import timedelta

    from app.models import AppUser, CalendarEvent

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    db.add(anna); db.flush()
    for titel, zeit in TERMINE:
        beginn = datetime(*zeit)
        db.add(CalendarEvent(title=titel, start_at=beginn, end_at=beginn + timedelta(minutes=10), owner_user_id=anna.id))
    db.commit()
    return {"anna": k.cookies(anna)}


BODY = "document.getElementById('calendarBody').textContent"
# (Ansicht, Ankerdatum als new Date(...), muss zu sehen sein, darf nicht zu sehen sein)
FAELLE = [
    ("day", "2026,0,15", ["Winter Donnerstag"], ["Winter Folgetag"]),
    ("day", "2026,0,18", ["Winter Sonntag"], []),
    ("week", "2026,0,15", ["Winter Donnerstag", "Winter Sonntag", "Winter Folgetag"], ["Winter Monatsende"]),
    ("month", "2026,0,15", ["Winter Donnerstag", "Winter Sonntag", "Winter Monatsende"], []),
    ("day", "2026,6,15", ["Sommer Mittwoch"], ["Sommer Folgetag"]),
    ("day", "2026,6,19", ["Sommer Sonntag"], []),
    ("week", "2026,6,15", ["Sommer Mittwoch", "Sommer Sonntag", "Sommer Folgetag"], ["Sommer Monatsende"]),
    ("month", "2026,6,15", ["Sommer Mittwoch", "Sommer Sonntag", "Sommer Monatsende"], []),
]


async def _durchlauf(tab, p, zone, bilder=False):
    for ansicht, anker, sichtbar, unsichtbar in FAELLE:
        marke = f"{zone} {ansicht} {anker}"
        await tab.js(f"anchor=new Date({anker});setView('{ansicht}')")
        await tab.warte_auf_ruhe()
        p.pruefe(f"{marke}: zu sehen", await tab.warten(" && ".join(f"{BODY}.includes({titel!r})" for titel in sichtbar)), True)
        text = await tab.js(BODY)
        for titel in unsichtbar:
            p.pruefe(f"{marke}: {titel} nicht", titel in text, False)
        if bilder:
            await tab.bild_ganz(f"kalender_{ansicht}_{anker.replace(',', '_')}")


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")  # Bilder hell
    await tab.browser_uhr_fest(UHR_MS)
    await tab.anmelden(seed["anna"])
    await tab.cmd("Emulation.setTimezoneOverride", timezoneId="Europe/Berlin")
    await tab.oeffnen("/kalender", "typeof events!=='undefined'&&document.getElementById('calendarBody').children.length>0")
    await _durchlauf(tab, p, "Berlin", bilder=True)
    p.pruefe("Berlin: JS-Fehler", tab.fehler, [])

    await tab.cmd("Emulation.setTimezoneOverride", timezoneId="Etc/UTC")
    await tab.oeffnen("/kalender", "typeof events!=='undefined'&&document.getElementById('calendarBody').children.length>0")
    await _durchlauf(tab, p, "UTC")
    p.pruefe("UTC: JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-10-14 10:00"))
