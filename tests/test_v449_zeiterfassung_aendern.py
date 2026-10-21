"""Seit 1.9.15 (Runde 7, Punkt 3): „Ändern“ in der Büro-Zeiterfassung tut nie still nichts (Nebenbefund 1.9.12).

Der Knopf steht in der Liste „Heutige Buchungen“; die Karte „Auswertung“ kann einen anderen Tag zeigen. Bis 1.9.14 suchte editEntry() die
Buchung nur in der Liste der Auswertung -- stand dort ein anderes Datum, öffnete „Ändern“ bei einer Buchung von heute nichts. Seither:

    ändern        die Buchung wird in beiden geladenen Listen gesucht und im Dialog geöffnet, egal welches Datum die Auswertung zeigt
    klar sagen    steht sie in keiner (inzwischen gelöscht oder verschoben), sagt die Seite das unter „Heutige Buchungen“
"""

import json

from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite

HEUTE = {"id": 5, "employee_id": 1, "work_date": "2026-10-21", "entry_type": "site", "status": "booked", "hours": "2.00",
         "order_id": 3, "order_number": "AUF-1", "project_name": "P", "order_item_id": None, "activity": "", "notes": "",
         "counts_as_productive": True}
GESTERN = dict(HEUTE, id=4, work_date="2026-10-20")


def _lauf(heute: list, auswertung: list, klick: int):
    ablauf = (f"todayEntries = {json.dumps(heute)}; entries = {json.dumps(auswertung)};"
              "let geoeffnet = null; openManual = r => { geoeffnet = r; };"
              f"editEntry({klick}); return {{geoeffnet: geoeffnet && geoeffnet.id, meldung: _element('todayMsg').textContent}};")
    return im_browser(seite("time_tracking.html", "init().catch("), ablauf)["ergebnis"]


@nur_mit_node
def test_aendern_bei_anderem_auswertungsdatum():
    """Auswertung zeigt gestern, „Ändern“ an der Buchung von heute öffnet sie (bis 1.9.14: nichts)."""
    assert _lauf([HEUTE], [GESTERN], 5) == {"geoeffnet": 5, "meldung": ""}


@nur_mit_node
def test_aendern_bei_gleichem_datum_wie_bisher():
    """Vergleichsfall, auch bis 1.9.14 grün."""
    assert _lauf([HEUTE], [HEUTE], 5)["geoeffnet"] == 5


@nur_mit_node
def test_aendern_ohne_buchung_sagt_warum():
    lauf = _lauf([], [GESTERN], 5)
    assert lauf["geoeffnet"] is None
    assert lauf["meldung"] == "Diese Buchung steht nicht mehr in der Liste (gelöscht oder verschoben) – bitte die Seite neu laden."


def test_meldungsfeld_unter_heutigen_buchungen():
    from tests import vorlagen_js as vj
    text = (vj.TEMPLATES / "time_tracking.html").read_text(encoding="utf-8")
    assert '<div id="todayEntries" class="entries"></div><div id="todayMsg" class="small" role="status"></div>' in text
