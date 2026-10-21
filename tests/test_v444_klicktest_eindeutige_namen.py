"""Seit 1.9.7 (Nachtrag, Runde 4): kein Name auf oberster Ebene eines Klicktest-Skripts wird zweimal vergeben.

Anlass: der Teil "kopfgruppe" von scripts/klicktest_rahmen.py legte eine Konstante KOPF an, die die gleichnamige des Teils "kopfzeile"
überdeckte -- der Teil "kopfzeile" führte danach das falsche Skript aus und brach ab (Endlauf von Runde 4). Geprüft wurde nur mit
--nur kopfgruppe, deshalb fiel es erst im Gesamtlauf auf. Gilt für jedes Skript unter scripts/, das Klicktests oder ihr Werkzeug
enthält (klicktest_*.py, cdp_klicktest.py, bildgrundlage.py)."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKRIPTE = sorted([*(ROOT / "scripts").glob("klicktest_*.py"), ROOT / "scripts" / "cdp_klicktest.py", ROOT / "scripts" / "bildgrundlage.py"])


def doppelte_namen(quelltext: str) -> list[str]:
    """Namen, die auf oberster Ebene mehr als einmal vergeben werden (Zuweisung, def, async def, class)."""
    gesehen, doppelt = set(), []
    for knoten in ast.parse(quelltext).body:
        namen = []
        if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            namen = [knoten.name]
        elif isinstance(knoten, ast.Assign):
            namen = [z.id for ziel in knoten.targets for z in ast.walk(ziel) if isinstance(z, ast.Name)]
        elif isinstance(knoten, ast.AnnAssign) and isinstance(knoten.target, ast.Name):
            namen = [knoten.target.id]
        for name in namen:
            if name in gesehen:
                doppelt.append(f"{name} (Zeile {knoten.lineno})")
            gesehen.add(name)
    return doppelt


@pytest.mark.parametrize("skript", SKRIPTE, ids=lambda p: p.name)
def test_kein_name_zweimal(skript):
    assert doppelte_namen(skript.read_text(encoding="utf-8")) == [], skript.name


def test_waechter_findet_die_ueberdeckte_konstante():
    assert doppelte_namen('KOPF = "a"\ndef f():\n    return KOPF\nKOPF = "b"\n') == ["KOPF (Zeile 4)"]
    assert doppelte_namen("A = 1\nB = 2\ndef f():\n    A = 3\n") == []
