"""Version 1.9.249 (Stufe 6, R4, Punkt 2): die Tafel bedienen -- Klick öffnet, Ziehen verschiebt (Maus und Finger), Klick in eine freie Zelle plant.

    Ziehen      Pointer Events (Maus und Finger, touch-action none am Balken); in eine Zeile der Kolonnen: die Kolonne und der Zeitraum, in „Ohne Kolonne“:
                keine Kolonne (die Personen bleiben), in der Zeile einer Person oder eines Geräts nur der Zeitraum; eine Kranvermietung bekommt nie eine
                Kolonne; ohne Änderung keine Anfrage; Warnungen fragen zurück (409 -> Rückfrage, „Trotzdem planen“ schickt trotzdem_planen)
    Zelle       Klick in eine freie Zelle: Kolonne -> „Einsatz planen“ mit der Kolonne, „Ohne Kolonne“ -> ohne, Gerät -> mit dem Gerät, Person -> mit ihr; Tag =
                Beginn und Ende
Im Browser mit echten Eingaben: scripts/klicktest_plantafel_bedienen.py.
"""

import json
import re

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node, schreibende
from tests.vorlagen_js import TEMPLATES

SLOTS = [{"id": 1, "team_id": 7, "art": "baustelle", "start_date": "2026-11-03", "end_date": "2026-11-05", "duration_days": 3},
         {"id": 2, "team_id": None, "art": "kranvermietung", "start_date": "2026-11-04", "end_date": "2026-11-05", "duration_days": 2}]
# seit 1.9.282 gehen die Züge über zugSenden() und zeigen danach die Leiste über der Tafel (bandZeigen) -- dafür Kolonnen und esc()
VORBEREITUNG = (f"var board = {{slots: {json.dumps(SLOTS)}, teams: [], employees: [], resources: []}}; var view = 'teams'; async function loadBoard() {{}} "
                "function esc(s){return String(s??'').replace(/[&<>'\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',\"'\":'&#39;','\"':'&quot;'}[c]))} "
                "var geo = {spalten: Array.from({length: 14}, (_, i) => ({d: addDays('2026-11-02', i), x: i * 60, w: 60}))}; const KONFLIKT_ART = {}; "
                "function localDateIso(d) { const p = n => String(n).padStart(2, '0'); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`; } ")
FUNKTIONEN = ["verschieben", "findSlot", "iso", "addDays", "einsatzHinweise", "konfliktZeile", "konfliktFrage", "fmt",
              "fmtSpanne", "zugSenden", "bandZeigen", "leerFrage"]


def _ziel(zeile, ident=""):
    return "{dataset: {zeile: '" + zeile + "', id: '" + str(ident) + "'}}"


@nur_mit_node
def test_ziehen_je_zielzeile():
    ablauf = (f"await verschieben(1, {_ziel('kolonne', 9)}, 2);"      # in die Kolonne 9, ab 04.11.
              f"await verschieben(1, {_ziel('ohne')}, 1);"            # ohne Kolonne, Zeitraum gleich
              f"await verschieben(1, {_ziel('geraet', 3)}, 3);"       # Zeile eines Geräts: nur der Zeitraum
              f"await verschieben(1, {_ziel('person', 5)}, 0);"       # Zeile einer Person (Ansicht Personen): nur der Zeitraum
              f"await verschieben(1, null, 1);"                       # ohne Ziel, nichts geändert -> keine Anfrage
              f"await verschieben(2, {_ziel('kolonne', 9)}, 3);")     # Kranvermietung: nie eine Kolonne
    aufrufe = im_browser("planning.html", FUNKTIONEN, VORBEREITUNG, ablauf)
    # seit 1.9.277 POST …/verschieben mit dem neuen ersten Tag -- das Ende rechnet der Server in Arbeitstagen (bis 1.9.276 PUT mit Beginn und Ende)
    assert [(m, u, b) for m, u, b in schreibende(aufrufe)] == [
        ("POST", "/api/planning/slots/1/verschieben", {"auf": "2026-11-04", "team_id": 9}),
        ("POST", "/api/planning/slots/1/verschieben", {"auf": "2026-11-03", "team_id": None}),
        ("POST", "/api/planning/slots/1/verschieben", {"auf": "2026-11-05"}),
        ("POST", "/api/planning/slots/1/verschieben", {"auf": "2026-11-02"}),
        ("POST", "/api/planning/slots/2/verschieben", {"auf": "2026-11-05"}),
    ]


@nur_mit_node
def test_freie_zelle_plant_fuer_zeile_und_tag():
    vorbereitung = "var geoeffnet = []; function openCreate(...a) { geoeffnet.push(a); } "
    aufrufe = im_browser("planning.html", ["planenAn"], vorbereitung,
                         "planenAn('kolonne','7','2026-11-02');planenAn('ohne','','2026-11-06');planenAn('geraet','3','2026-11-12');"
                         "planenAn('person','5','2026-11-02');AUFRUFE.push({g: geoeffnet});")
    assert aufrufe[-1]["g"] == [[None, "2026-11-02", 7], [None, "2026-11-06", None], [None, "2026-11-12", None, {"geraete": [{"resource_id": 3, "tage": None}]}],
                                [None, "2026-11-02", None, {"employee_ids": [5]}]]


def test_pointer_events_fuer_maus_und_finger():
    text = (TEMPLATES / "planning.html").read_text(encoding="utf-8")
    assert all(f"pl.addEventListener('{e}'" in text for e in ("pointerdown", "pointermove", "pointerup", "pointercancel", "click"))
    assert re.search(r'\.slot\[data-klick="einsatz"\]\{touch-action:none\}', text)
    assert "draggable" not in text and "dragstart" not in text  # kein HTML5-Ziehen mehr (ging nicht mit dem Finger)
    assert "aktion('einsatz',el=>{if(nachZiehen){nachZiehen=false;return}openEdit(Number(el.dataset.id))});" in text  # nach dem Ziehen öffnet kein Klick
    assert "pl.addEventListener('pointerdown',e=>{nachZiehen=false;" in text and "setTimeout(()=>{nachZiehen" not in text  # ohne Timer
