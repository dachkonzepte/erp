"""Version 1.9.274 (Nachrunde R5b, Punkt 3; Frage 1 zu 1.9.271): Stammdaten -> Mitarbeiter, Untertitel „N aktiv · M inaktiv“.

    Untertitel   „N aktiv · M inaktiv“ statt „N Mitarbeiterstammsätze“ -- immer beide Zahlen, auch „0 inaktiv“
    gezählt      über alle Mitarbeiter, unabhängig von der Suche und vom Kästchen „Inaktive MA ausblenden“ (wie die Zahl daneben, 1.9.271 Nr. 1)
Der Klicktest scripts/klicktest_stammdaten_inaktive.py prüft den Untertitel im Browser (mit und ohne Haken, in der Suche, Büro – Auftrag).
"""

from tests.test_v399_teil_updates_geld import im_browser, nur_mit_node
from tests.test_v671_inaktive_mitarbeiter_ausblenden import _mitarbeiter_zweig, _text


def _untertitel(liste: list[dict]) -> str:
    import json
    return im_browser("master_data.html", ["mitarbeiterUntertitel"], "var AUFRUFE = AUFRUFE || [];",
                      f"AUFRUFE.push(mitarbeiterUntertitel({json.dumps(liste)}));")[0]


@nur_mit_node
def test_untertitel_aktiv_und_inaktiv():
    assert _untertitel([{"active": True}, {"active": True}, {"active": True}, {"active": False}]) == "3 aktiv · 1 inaktiv"


@nur_mit_node
def test_immer_beide_zahlen():
    assert _untertitel([{"active": True}, {"active": True}]) == "2 aktiv · 0 inaktiv"
    assert _untertitel([{"active": False}]) == "0 aktiv · 1 inaktiv"
    assert _untertitel([]) == "0 aktiv · 0 inaktiv"


def test_gezaehlt_ueber_alle_nicht_nach_suche_oder_kaestchen():
    zweig = _mitarbeiter_zweig()
    assert "sub.textContent=mitarbeiterUntertitel(employees);" in zweig  # alle -- nicht die Liste nach Kästchen und Suche
    assert "${employees.length} Mitarbeiterstammsätze" not in _text()  # der alte Untertitel (der Kommentar nennt ihn)
