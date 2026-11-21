"""Version 1.10.19 (Hinweis des Betriebs vom 21.11.2026): beim Übernehmen stand „Kein bestehender Kunde passt zu den Angaben“, obwohl darunter ein Kunde im
Archiv mit „E-Mail gleich, Name gleich“ passte.

    einer    „Kein aktiver Kunde passt – aber einer im Archiv:“
    mehrere  „Kein aktiver Kunde passt – aber n im Archiv:“
    keiner   wie bisher „Kein bestehender Kunde passt zu den Angaben – unten suchen oder einen neuen anlegen.“
    aktive   passt ein aktiver, steht kein Satz (die Vorschläge)
"""

import json

import pytest

from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite
from tests.test_v447_auswahl_altwerte import WIRKSAM
from tests.test_v779_webanfragen_anderer_kunde import VORSCHLAG

ARCHIV = {"id": 9, "name": "Wilma Archiv", "kundennummer": "K-9", "adresse": None, "gruende": ["E-Mail gleich", "Name gleich"],
          "archiviert_am": "2026-11-20T23:30:00"}
AKTIV = {"id": 4, "name": "Zora Aktiv", "kundennummer": "K-4", "adresse": None, "gruende": ["Name gleich"]}


def _kunden(kunden, archiv):
    ablauf = (f"uebVorschlag={json.dumps({**VORSCHLAG, 'kunden': kunden, 'kunden_archiv': archiv})};uebZeichnen();"
              "return _element('uebKunden').innerHTML;")
    return im_browser(seite("webanfrage.html", "\nlesen('anfrage',") + WIRKSAM, ablauf)["ergebnis"]


@nur_mit_node
@pytest.mark.parametrize("archiv, satz", [
    ([ARCHIV], "Kein aktiver Kunde passt – aber einer im Archiv:"),
    ([ARCHIV, {**ARCHIV, "id": 10}], "Kein aktiver Kunde passt – aber 2 im Archiv:"),
    ([], "Kein bestehender Kunde passt zu den Angaben – unten suchen oder einen neuen anlegen."),
])
def test_satz_ohne_aktiven_kunden(archiv, satz):
    assert _kunden([], archiv) == f'<div class="muted small">{satz}</div>'


@nur_mit_node
def test_mit_aktivem_kunden_kein_satz():
    html = _kunden([AKTIV], [ARCHIV])
    assert "Zora Aktiv" in html and "Kein " not in html
