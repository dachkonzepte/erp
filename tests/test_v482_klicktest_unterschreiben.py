"""Seit 1.9.55 (Stufe 4, R2 Nachrunde 2, Punkt 3): _unterschreiben() in scripts/klicktest_checkliste_unterschrift.py (von acht Klicktests
benutzt) misst die Zeichenfläche erst, wenn kein Speichern der Seite mehr unterwegs ist.

    Befund         Endlauf 1.9.52: klicktest_behinderungsanzeige_versand trug zwei Datumsfelder ein (jedes speichert, die Checkliste
                   zeichnet danach neu) und unterschrieb gleich danach -- das Messen der Zeichenfläche fiel unter Last in das Neuzeichnen,
                   getBoundingClientRect() kam nicht zurück (TypeError im Klicktest)
    jetzt          die erste Anweisung wartet über Tab.warte_auf_ruhe() (Anfragenzähler des Werkzeugs, zurückgehaltene Antworten
                   ausgenommen), bevor gescrollt und gemessen wird -- seit 1.9.64 ist sie Tab.strich(), das dieses Warten selbst
                   mitbringt (über ruhig_im_bild(), geprüft in tests/test_v490_zeichnen_ruhig.py)
"""

import ast
from pathlib import Path

SKRIPT = Path(__file__).resolve().parent.parent / "scripts" / "klicktest_checkliste_unterschrift.py"


def _funktion(name: str) -> ast.AsyncFunctionDef:
    baum = ast.parse(SKRIPT.read_text(encoding="utf-8"))
    return next(k for k in baum.body if isinstance(k, ast.AsyncFunctionDef) and k.name == name)


def _awaits(funktion) -> list[str]:
    """Die erwarteten Aufrufe der Funktion in Reihenfolge, als „tab.methode“."""
    namen = []
    for knoten in ast.walk(funktion):
        if isinstance(knoten, ast.Await) and isinstance(knoten.value, ast.Call) and isinstance(knoten.value.func, ast.Attribute):
            ziel = knoten.value.func
            if isinstance(ziel.value, ast.Name):
                namen.append((knoten.lineno, f"{ziel.value.id}.{ziel.attr}"))
    return [n for _, n in sorted(namen)]


def test_unterschreiben_wartet_erst_auf_ruhe():
    aufrufe = _awaits(_funktion("_unterschreiben"))
    assert aufrufe[0] == "tab.strich", aufrufe  # seit 1.9.64 (bis dahin tab.warte_auf_ruhe); strich() wartet selbst auf Ruhe
    assert aufrufe.index("tab.strich") < aufrufe.index("tab.js")  # vor dem Namen und dem Übernehmen


def test_acht_klicktests_nehmen_diese_funktion():
    """Die Klicktests mit einer Checklisten-Unterschrift importieren genau diese Funktion (keiner baut eine eigene Fassung ohne Warten)."""
    ordner = SKRIPT.parent
    nutzer = sorted(p.name for p in ordner.glob("klicktest_*.py")
                    if "from klicktest_checkliste_unterschrift import CONFIRM, _unterschreiben" in p.read_text(encoding="utf-8"))
    assert len(nutzer) == 7, nutzer  # dazu klicktest_checkliste_unterschrift selbst -- acht
