"""Version 1.8.87 -- "heute" im Browser nur noch in Europe/Berlin (Vorgabe R4c, Vorweg 1).

Bis 1.8.86 bildeten mehrere Vorlagen das heutige Datum über new Date().toISOString().slice(0, 10) -- in UTC: zwischen 0 und
1 Uhr (Winterzeit) bzw. 2 Uhr (Sommerzeit) der Vortag. Anlass: klicktest_teil_updates um Mitternacht ("/time-tracking: Seite
nicht bereit" -- die Büro-Zeiterfassung zeigte die Buchungen des Vortags). Andere Stellen nahmen die Zeitzone des Geräts
(new Date().getDate(), toDateString(), getTimezoneOffset()). Seit 1.8.87 kommt "heute" nur aus app/templates/_berlin_date.html
(berlinToday(), berlinMonth(), berlinMonthRange(), berlinTime(), berlinAddDays(), berlinTodayDate()).

Strukturtest über alle Vorlagen: jedes toISOString(), new Date() und Date.now() ohne Argument steht in ERLAUBT -- mit Grund,
warum dort ein Zeitpunkt gemeint ist und kein Kalendertag; getTimezoneOffset() und toDateString() gibt es nicht. Wer einen
Helfer nutzt, bindet _berlin_date.html ein. Dazu laufen die Helfer in node an den Sekunden vor und nach Mitternacht Berliner
Zeit, mit vier Zeitzonen des Prozesses (wie test_v314; ohne node übersprungen)."""

import json
import re
from pathlib import Path

import pytest

from tests import vorlagen_js
from tests.test_v314_dashboard_month_berlin import NODE, PROCESS_TIMEZONES, _node, _scripts

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
HELPER = "_berlin_date.html"  # eingebunden mit {% include "_berlin_date.html" %}, selbst oder im Basis-Template

JETZT = re.compile(r"\bnew Date\(\s*\)|\bDate\.now\(\s*\)|\.toISOString\(")
VERBOTEN = re.compile(r"getTimezoneOffset|toDateString\(")
HELFER = re.compile(r"\b(berlinToday|berlinTodayDate|berlinMonth|berlinMonthRange|berlinTime|berlinAddDays|berlinDateParts|"
                    r"localDateIso)\(")

# (Vorlage, Ausschnitt der Zeile, Grund) -- ein Zeitpunkt, kein Kalendertag. Darf nur kürzer werden, wenn eine Stelle wegfällt;
# eine neue Stelle braucht einen Grund.
ERLAUBT = [
    ("_email_dispatch.html", "timeZone: 'Europe/Berlin'",
     "berlinTodayIso(): Berliner Tag über Intl mit Europe/Berlin (Vorlage ohne _berlin_date.html)"),
    ("calendar.html", "start:start.toISOString(),end:end.toISOString()",
     "Zeitraum der Kalenderabfrage als Zeitpunkte (Ortsmitternacht des Kalenders), die API rechnet mit Zeitpunkten"),
    ("checklist.html", "client_recorded_at:new Date().toISOString()",
     "Zeitpunkt der Erfassung auf dem Gerät (Offline-Fähigkeit), kein Kalendertag"),
    ("dashboard.html", "new Date(i.follow_up_at)<=new Date()",
     "Wiedervorlage: Zeitpunktvergleich (follow_up_at ist ein Zeitpunkt)"),
    ("inquiries.html", "new Date(i.follow_up_at)<=new Date()",
     "Wiedervorlage: Zeitpunktvergleich (follow_up_at ist ein Zeitpunkt)"),
    ("operational_asset.html", "qr-code.png?v=${Date.now()}", "Cache-Brecher für das Bild"),
    ("roof_area.html", "sketch?t=${Date.now()}", "Cache-Brecher für das Bild"),
]


def _vorlagen() -> list[str]:
    """Jede Vorlage außer dem Helfer -- seit 1.8.124 (Stufe 0b) auch in Unterordnern (tests/vorlagen_js.py::alle_vorlagen())."""
    return [name for name in vorlagen_js.alle_vorlagen(TEMPLATES) if name != HELPER]


def _zeilen(name: str) -> list[str]:
    return (TEMPLATES / name).read_text(encoding="utf-8").splitlines()


def _fundstellen():
    """(Vorlage, Zeilennummer, Zeile) je Vorkommen eines Musters aus JETZT."""
    for name in _vorlagen():
        for nr, line in enumerate(_zeilen(name), start=1):
            for _ in JETZT.finditer(line):
                yield name, nr, line


def _verbotene() -> list[str]:
    return [f"{name}:{nr}" for name in _vorlagen() for nr, line in enumerate(_zeilen(name), start=1) if VERBOTEN.search(line)]


def _helfer_nutzer() -> list[tuple[str, bool]]:
    """(Vorlage, bindet _berlin_date.html ein) je Vorlage, die einen Helfer nutzt -- seit 1.8.124 das Include auch im Basis-Template."""
    return [(name, vorlagen_js.bindet_ein(name, HELPER, TEMPLATES)) for name in _vorlagen()
            if HELFER.search((TEMPLATES / name).read_text(encoding="utf-8"))]


def test_every_now_in_templates_is_an_allowed_instant():
    offen = []
    for name, nr, line in _fundstellen():
        if not any(name == datei and ausschnitt in line for datei, ausschnitt, _ in ERLAUBT):
            treffer = JETZT.search(line)
            start = max(treffer.start() - 60, 0)
            offen.append(f"{name}:{nr}: …{line[start:treffer.end() + 40].strip()}…")
    assert not offen, ("Heute im Browser aus UTC bzw. der Zeitzone des Geräts statt aus _berlin_date.html (berlinToday() u. a.) "
                       "-- oder ein Zeitpunkt ohne Eintrag in ERLAUBT:\n" + "\n".join(offen))


def test_allowed_list_has_no_stale_entries():
    gefunden = {(name, ausschnitt) for name, _, line in _fundstellen()
                for datei, ausschnitt, _ in ERLAUBT if name == datei and ausschnitt in line}
    veraltet = [f"{d}: {a}" for d, a, _ in ERLAUBT if (d, a) not in gefunden]
    assert not veraltet, "Eintrag in ERLAUBT ohne Fundstelle -- bitte streichen:\n" + "\n".join(veraltet)


def test_no_timezone_offset_or_date_string_in_templates():
    treffer = _verbotene()
    assert not treffer, "getTimezoneOffset()/toDateString() ergeben den Tag in der Zeitzone des Geräts: " + ", ".join(treffer)


def test_templates_using_the_helpers_include_them():
    fehlt = [name for name, eingebunden in _helfer_nutzer() if not eingebunden]
    assert not fehlt, "Vorlage nutzt einen Helfer aus _berlin_date.html, ohne ihn einzubinden: " + ", ".join(fehlt)


def test_today_of_the_time_tracking_pages_is_berlin():
    """Der Anlass: die Büro- und die Monteur-Zeiterfassung bilden "heute" für Liste, Summen und Vorgabedatum."""
    # seit 1.9.98 die Seite „Zeiten“ (bis 1.9.97 today() der Zeiterfassung): Vorgabedatum von „Buchung“ und „Kolonne buchen“
    zeiten_buero = (TEMPLATES / "zeiten.html").read_text(encoding="utf-8")
    assert "el('bdDatum').value=aendern?e.work_date:berlinToday();" in zeiten_buero and "el('kdDatum').value=berlinToday();" in zeiten_buero
    # seit 1.9.59 „Meine Zeiten“: das Vorgabedatum von „Zeit nachtragen“ und der Kolonne (bis 1.9.58 today() der Zeiterfassung)
    zeiten = (TEMPLATES / "mobil_zeiten.html").read_text(encoding="utf-8")
    assert "el('zdDatum').value=aendern?z.work_date:berlinToday();" in zeiten
    assert "el('kdDatum').value=aendern?g.work_date:berlinToday();" in zeiten


# ---------------------------------------------------------------------------
# Die Helfer selbst, in node
# ---------------------------------------------------------------------------

# Zeitpunkt in UTC -> (heute, Uhrzeit, Monat) in Europe/Berlin
INSTANTS = {
    "2026-10-12T21:59:59Z": ["2026-10-12", "23:59", "2026-10"],  # Sommerzeit, UTC+2
    "2026-10-12T22:00:00Z": ["2026-10-13", "00:00", "2026-10"],  # 0:00 Uhr in Berlin, in UTC noch der 12.
    "2026-10-12T22:30:00Z": ["2026-10-13", "00:30", "2026-10"],  # der Anlass: Klicktest um halb eins
    "2026-10-31T22:59:59Z": ["2026-10-31", "23:59", "2026-10"],  # seit dem 25.10. Winterzeit, UTC+1
    "2026-10-31T23:00:00Z": ["2026-11-01", "00:00", "2026-11"],
    "2026-12-31T23:30:00Z": ["2027-01-01", "00:30", "2027-01"],  # Silvester: in Berlin schon das neue Jahr
    "2026-03-29T00:59:59Z": ["2026-03-29", "01:59", "2026-03"],  # Umstellung auf Sommerzeit
    "2026-03-29T01:00:00Z": ["2026-03-29", "03:00", "2026-03"],
}
# (Tag, n) -> Tag + n, über Monats-, Jahres- und Schaltjahrgrenzen und die Zeitumstellung
ADD_DAYS = {
    "2026-10-13|-14": "2026-09-29",
    "2026-10-24|1": "2026-10-25",
    "2026-10-25|1": "2026-10-26",
    "2026-12-31|1": "2027-01-01",
    "2028-02-28|1": "2028-02-29",
    "2026-03-28|1": "2026-03-29",
    "2026-10-13|7": "2026-10-20",
}

pytestmark_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert -- die Tests führen JavaScript aus den Vorlagen aus.")


@pytestmark_node
@pytest.mark.parametrize("tz", PROCESS_TIMEZONES)
def test_berlin_today_time_and_month_change_at_berlin_midnight(tz):
    script = _scripts(HELPER) + (
        f"\nconst instants = {json.dumps(list(INSTANTS))};"
        "\nprocess.stdout.write(JSON.stringify(Object.fromEntries(instants.map(s => { const d = new Date(s); "
        "return [s, [berlinToday(d), berlinTime(d), berlinMonth(d)]]; }))));"
    )
    assert _node(script, tz) == INSTANTS


@pytestmark_node
@pytest.mark.parametrize("tz", PROCESS_TIMEZONES)
def test_berlin_add_days_and_local_date(tz):
    script = _scripts(HELPER) + (
        f"\nconst cases = {json.dumps(list(ADD_DAYS))};"
        "\nconst add = Object.fromEntries(cases.map(c => { const [d, n] = c.split('|'); return [c, berlinAddDays(d, Number(n))]; }));"
        # localDateIso() eines aus einem Datum gebauten Date ist wieder dieses Datum -- in jeder Zeitzone.
        "\nconst local = ['2026-10-25', '2026-03-29', '2026-12-31'].map(d => localDateIso(new Date(d + 'T12:00:00')));"
        # berlinTodayDate(): Ortsmitternacht des Berliner Tages -- localDateIso() davon ist der Berliner Tag.
        "\nconst todayDate = localDateIso(berlinTodayDate(new Date('2026-10-12T22:30:00Z')));"
        "\nprocess.stdout.write(JSON.stringify({add, local, todayDate}));"
    )
    assert _node(script, tz) == {"add": ADD_DAYS, "local": ["2026-10-25", "2026-03-29", "2026-12-31"], "todayDate": "2026-10-13"}
