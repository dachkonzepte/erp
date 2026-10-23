"""Seit 1.9.53 (Stufe 4, R2 Nachrunde 2, Punkt 1; ersetzt Festlegung 1.9.48 Nr. 4): „Tag zusammen“ erklärt die Pause.

    Wert           „Tag zusammen“ = Anwesenheit des Tages samt der neuen Buchung, vor der Pause (app/time_tracking.py::ende_rechnen(),
                   tag_stand()) -- davon hängt die Pause ab; die gebuchten Stunden bleiben dezimal (bis 1.9.52 war „Tag zusammen“ die
                   Summe der gebuchten Stunden)
    Vorschau       „Anwesend 9:00 h · Tag zusammen 9:45 h · Pause nach Zeitregel − 0:45 h“, darunter „Gebucht werden 8,25 h“
    Ergebnis       nach „Feierabend“ (Heute) und nach „Zeit nachtragen“ auf „Meine Zeiten“ (seit 1.9.59, bis dahin die Zeiterfassung der
                   Monteurin) in derselben Reihenfolge: anwesend · Tag zusammen · Pause nach Zeitregel, dann gebucht
    nur mit Tag    „Tag zusammen“ nur, wenn der Tag schon Buchungen hat (tag_buchungen > 1)

Die Zahlen des Servers prüft tests/test_v474_pause_je_tag.py, im Browser scripts/klicktest_heute.py und scripts/klicktest_echter_tag.py.
"""

import json
import re

import pytest

from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren


def _skript(name: str) -> str:
    return vj.eigene_skripte(name).text


def _funktion(text: str, kopf: str) -> str:
    """Eine Funktion samt Rumpf (Klammern gezählt) aus dem Skript einer Vorlage."""
    i = text.index(kopf)
    tiefe, j = 0, text.index("{", i)
    while True:
        tiefe += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
        if tiefe == 0:
            return text[i:j]


def _zahl() -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", (vj.TEMPLATES / "_zahl.html").read_text(encoding="utf-8"), flags=re.S))


MIT_TAG = {"anwesend": "9.0000", "tag_zusammen": "9.7500", "tag_buchungen": 2, "pause": 45, "gebucht": "8.2500"}
OHNE_TAG = {"anwesend": "9.0000", "tag_zusammen": "9.0000", "tag_buchungen": 1, "pause": 30, "gebucht": "8.5000"}
ECHTER_TAG = {"anwesend": "4.2500", "tag_zusammen": "9.2500", "tag_buchungen": 2, "pause": 45, "gebucht": "3.5000"}


def _heute(ablauf: str) -> object:
    text = _skript("mobil.html")
    teile = [_funktion(text, k) for k in ("function pad2(", "function stundenUhr(", "function tagZusammen(", "function ergebnisBuchung(")]
    js = (_zahl() + "\nfunction esc(s){return String(s)}\n" + "\n".join(teile)
          + f"\nconst ergebnis=(()=>{{{ablauf}}})();process.stdout.write(JSON.stringify(ergebnis));")
    return node_ausfuehren(js)  # liefert das ausgegebene JSON schon gelesen


@pytest.mark.parametrize("daten, erwartet", [
    (ECHTER_TAG, "Feierabend gebucht: anwesend 4:15 h · Tag zusammen 9:15 h · Pause nach Zeitregel − 0:45 h · gebucht 3,50 h"),
    (OHNE_TAG, "Feierabend gebucht: anwesend 9:00 h · Pause nach Zeitregel − 0:30 h · gebucht 8,50 h"),
], ids=["echter_tag", "ohne_fruehere_buchung"])
def test_ergebnis_auf_heute(daten, erwartet):
    assert _heute(f"return ergebnisBuchung('Feierabend gebucht')({json.dumps(daten)})") == erwartet


def test_vorschau_auf_heute_tag_zusammen_zwischen_anwesend_und_pause():
    """Die Vorschau setzt „Tag zusammen“ zwischen „Anwesend“ und die Pause -- keine eigene Zeile mehr; die Zeile „Gebucht werden“ bleibt."""
    text = _skript("mobil.html")
    teil = _funktion(text, "function vorschauLaden(")
    assert ("'<span class=\"anwesend\">Anwesend '+esc(stundenUhr(Number(v.anwesend)*60))+esc(tagZusammen(v))\n"
            "        +' · Pause nach Zeitregel − '+esc(stundenUhr(v.pause))+'</span>'") in teil
    assert "'<span class=\"gebucht\">Gebucht werden '+esc(zahlText(v.gebucht,2))+' h</span>'" in teil
    # „Tag zusammen“ kommt nur aus tagZusammen() -- die frühere eigene Zeile (1.9.48–1.9.52) gibt es nicht mehr
    assert teil.count('class="anwesend"') == 1 and "'<span class=\"anwesend\">Tag zusammen '" not in teil
    erste_zeile = _heute(f"const v={json.dumps(MIT_TAG)};return 'Anwesend '+stundenUhr(Number(v.anwesend)*60)+tagZusammen(v)"
                         "+' · Pause nach Zeitregel − '+stundenUhr(v.pause)")
    assert erste_zeile == "Anwesend 9:00 h · Tag zusammen 9:45 h · Pause nach Zeitregel − 0:45 h"


@pytest.mark.parametrize("daten, erwartet", [
    ({**MIT_TAG, "hours": "8.2500"}, "Nachgetragen: anwesend 9:00 h · Tag zusammen 9:45 h · Pause nach Zeitregel − 0:45 h · gebucht 8,25 h"),
    ({**OHNE_TAG, "hours": "8.5000"}, "Nachgetragen: anwesend 9:00 h · Pause nach Zeitregel − 0:30 h · gebucht 8,50 h"),
], ids=["mit_frueherer_buchung", "ohne_fruehere_buchung"])
def test_ergebnis_auf_meine_zeiten(daten, erwartet):
    """Seit 1.9.59 „Meine Zeiten“ statt der Zeiterfassung der Monteurin: dieselbe Zeile wie auf „Heute“ (bis 1.9.58 „Pause 0:45 h“)."""
    text = _skript("mobil_zeiten.html")
    teile = [_funktion(text, k) for k in ("function pad2(", "function stundenUhr(", "function stunden(", "function tagZusammen(",
                                          "function buchungsText(")]
    js = (_zahl() + "\n" + "\n".join(teile) + f"\nconst d={json.dumps(daten)};"
          "process.stdout.write(JSON.stringify('Nachgetragen: '+buchungsText(d)+' · gebucht '+stunden(d.hours)));")
    assert node_ausfuehren(js) == erwartet
    assert "ergebnis((aendern?'Geändert':'Nachgetragen')+': '+buchungsText(d)+' · gebucht '+stunden(d.hours))" in text
