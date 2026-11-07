"""Version 1.9.254 (Stufe 6, R4b, Punkt 2): ein Termin einer Person in „Personen“ öffnet den Kalender an seinem Tag mit dem Termin.

    Daten        personen_termine nennt „belegt“: ein privater Termin für jemand anderen (Titel „Belegt“)
    Tafel        jeder andere Termin ist ein Knopf (data-klick="personTermin", Kennung e<id> bzw. s<id> für ein Vorkommen einer Serie), title
                 „· im Kalender öffnen“; ein Klick führt nach /kalender?tag=<erster Tag>&termin=<id> bzw. &serie=<id>; „belegt“ bleibt ohne Knopf
    Kalender     ?tag= stellt die Tagesansicht auf den Tag (nur für diesen Aufruf, die gemerkte Ansicht bleibt), ?termin=/serie= öffnet den Termin, sobald
                 die Termine geladen sind; ungültige Werte werden übergangen
Im Browser: scripts/klicktest_plantafel_personen.py (Bea: Termin und Vorkommen einer Serie öffnen den Kalender, „Belegt“ kein Knopf, für Bea selbst schon).
"""

import json
import re
from datetime import date, timedelta
from pathlib import Path

from app.planning import planning_board
from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v650_plantafel_personen import _welt

ROOT = Path(__file__).resolve().parent.parent
MO = date(2026, 11, 2)


def _termine(db, betrachter=None):
    return {t["titel"]: t["belegt"] for t in planning_board(db, MO, MO + timedelta(days=13), betrachter)["personen_termine"]}


def test_belegt_nur_fuer_andere(threaded_db_session):
    db = threaded_db_session
    w = _welt(db)
    assert _termine(db) == {"Aufmaß": False, "Belegt": True, "Messe": False, "Jour fixe": False}
    assert _termine(db, w["konto"].id) == {"Aufmaß": False, "Zahnarzt": False, "Messe": False, "Jour fixe": False}


TAFEL = {"personen_termine": [
    {"id": 7, "employee_id": 1, "titel": "Aufmaß", "von": "2026-11-03", "bis": "2026-11-03", "zeit": "10:00", "serie": False, "belegt": False},
    {"id": 7, "employee_id": 1, "titel": "Jour fixe", "von": "2026-11-04", "bis": "2026-11-04", "zeit": "08:00", "serie": True, "belegt": False},
    {"id": 9, "employee_id": 1, "titel": "Belegt", "von": "2026-11-06", "bis": "2026-11-06", "zeit": "09:00", "serie": False, "belegt": True},
    {"id": 11, "employee_id": 1, "titel": "Messe", "von": "2026-10-30", "bis": "2026-11-03", "zeit": None, "serie": False, "belegt": False}]}


@nur_mit_node
def test_knopf_und_ziel():
    vorbereitung = f"var board = {json.dumps(TAFEL)}; var location = {{href: ''}};"
    ablauf = ("const b = personTermine(1).map(x => [x.b.text + ' ' + x.b.leise, x.b.klick || null, x.b.id || null, x.b.title.endsWith('· im Kalender öffnen')]);"
              "const ziele = ['e7', 's7', 'e9', 'e11', 'x1'].map(k => { location.href = ''; terminImKalender(k); return location.href; });"
              "AUFRUFE.push({b, ziele});")
    [erg] = im_browser("planning.html", ["personTermine", "personTerminKennung", "terminImKalender", "fmtSpanne", "fmt"], vorbereitung, ablauf)
    assert erg["b"] == [["10:00 Aufmaß", "personTermin", "e7", True], ["08:00 Jour fixe", "personTermin", "s7", True],
                        ["09:00 Belegt", None, None, False],               # privat für jemand anderen: kein Knopf
                        ["ganztägig Messe", "personTermin", "e11", True]]
    assert erg["ziele"] == ["/kalender?tag=2026-11-03&termin=7", "/kalender?tag=2026-11-04&serie=7", "",  # gleiche ID, andere Tabelle
                            "/kalender?tag=2026-10-30&termin=11",  # der erste Tag des Termins, auch vor dem Bild
                            ""]


def test_kalender_liest_tag_und_termin():
    html = (ROOT / "app/templates/calendar.html").read_text(encoding="utf-8")
    init = html[html.index("async function init(){"):html.index("init();\n")]
    assert "const tag=params.get('tag'),termin=params.get('termin'),serie=params.get('serie');" in init
    assert re.search(r"if\(tag&&/\^\\d\{4\}-\\d\{2\}-\\d\{2\}\$/\.test\(tag\)\)\{const \[j,m,t\]=tag\.split\('-'\)\.map\(Number\);anchor=new Date\(j,m-1,t\);view='day'\}", init)
    assert "localStorage" not in init  # die gemerkte Ansicht bleibt (setView() würde sie überschreiben)
    assert "geladen.then(()=>openEdit(Number(termin)))" in init and "geladen.then(()=>openSeries(Number(serie)))" in init
    assert "  return loadEvents().then(()=>{" in html  # render() gibt das Laden zurück, erst danach öffnet der Termin
