"""Seitenskript aus einer vom Server gezeichneten Seite für node (seit 1.8.145).

`seite()` aus tests/test_v334_auswahl_restfaelle.py liest die Vorlage und setzt jeden Jinja-Ausdruck auf 1 -- eine Seite, deren Skript
an Werten des Servers hängt (Art des Stammdatenbereichs, ID, Ziel nach dem Speichern), läuft so nicht wie im Browser.
`gerenderte_seite()` nimmt die echte Antwort einer Seitenroute: die Attrappe (`FAKE_DOM`), jedes Skript der Seite in ihrer
Reihenfolge (die eingebundenen Bausteine eingeschlossen) und das letzte bis vor den Start-Aufruf. Ausgeführt wird wie bei `seite()`
über `im_browser()` (tests/node_lauf.py, Regel 36).
"""

import re

from tests.test_v334_auswahl_restfaelle import FAKE_DOM


def gerenderte_seite(html: str, start: str) -> str:
    skripte = re.findall(r"<script>(.*?)</script>", html, flags=re.S)
    assert skripte, "keine Skripte in der Seite"
    haupt = skripte[-1]
    assert start in haupt, f"{start!r} nicht im Seitenskript -- Test anpassen"
    return FAKE_DOM + "\n".join(skripte[:-1]) + "\n" + haupt.rsplit(start, 1)[0]
