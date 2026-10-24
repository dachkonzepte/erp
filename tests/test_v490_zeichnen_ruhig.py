"""Seit 1.9.64 (Stufe 4, R4 Punkt 7): ein Klicktest zeichnet nur über Tab.strich() (scripts/cdp_klicktest.py).

    Anlass       Endlauf der R3-Nachrunde: klicktest_unterzeichner maß die Zeichenfläche nach einer festen Pause von 0,2 s -- unter Last
                 (vier Klicktests zugleich) ging Petras Strich verloren, die Seite sendete nichts (16 von 19, einzeln dreimal 19 von 19).
    Helfer       strich() wartet über ruhig_im_bild(), bis kein Speichern mehr unterwegs ist (die Checkliste zeichnet danach neu) und die
                 Fläche zweimal hintereinander dieselbe Lage hat, zeichnet dann und prüft danach, dass Tinte auf der Fläche ist -- sonst
                 ist der Lauf nicht wie erwartet (nicht_geladen) statt still eine leere Unterschrift zu senden.
    Wächter      kein Klicktest schickt selbst eine Mausbewegung mit gedrückter Taste (Zeichnen an strich() vorbei).
"""

import ast
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _zeichnet_selbst(pfad: Path) -> list[int]:
    """Zeilen mit tab.cmd("Input.dispatchMouseEvent", type="mouseMoved", …, buttons=1) -- eine Bewegung mit gedrückter Taste."""
    zeilen = []
    for knoten in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
        if not (isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Attribute) and knoten.func.attr == "cmd"):
            continue
        if not (knoten.args and isinstance(knoten.args[0], ast.Constant) and knoten.args[0].value == "Input.dispatchMouseEvent"):
            continue
        werte = {k.arg: k.value for k in knoten.keywords}
        art, taste = werte.get("type"), werte.get("buttons")
        if (isinstance(art, ast.Constant) and art.value == "mouseMoved" and isinstance(taste, ast.Constant) and taste.value == 1):
            zeilen.append(knoten.lineno)
    return zeilen


def test_kein_klicktest_zeichnet_an_strich_vorbei():
    funde = {p.name: z for p in sorted(SCRIPTS.glob("klicktest_*.py")) if (z := _zeichnet_selbst(p))}
    assert funde == {}, "Zeichnen nur über tab.strich() (Ruhe, ruhige Lage, Prüfung auf Tinte)"


def test_die_vier_zeichnenden_klicktests_nehmen_den_helfer():
    for name in ("klicktest_unterzeichner.py", "klicktest_checkliste_unterschrift.py", "klicktest_abschliessen.py",
                 "klicktest_vertrag_unterschrift.py"):
        assert "await tab.strich(" in (SCRIPTS / name).read_text(encoding="utf-8"), name


def test_der_helfer_wartet_auf_ruhe_und_lage_und_prueft_die_tinte():
    text = (SCRIPTS / "cdp_klicktest.py").read_text(encoding="utf-8")
    lage = text[text.index("    async def ruhig_im_bild("):text.index("    async def strich(")]
    strich = text[text.index("    async def strich("):text.index("    async def warten(")]
    assert "await self.warte_auf_ruhe()" in lage and "scrollIntoView" in lage
    assert "jetzt == vorher" in lage and "self.nicht_geladen.append(" in lage
    assert "await self.ruhig_im_bild(flaeche)" in strich
    assert "getImageData" in strich and "if not tinte:" in strich and "self.nicht_geladen.append(" in strich
    assert "asyncio.sleep(0.2)" not in lage + strich


def test_der_waechter_findet_einen_selbst_gezeichneten_strich(tmp_path):
    """Gegenprobe des Wächters: ein Klicktest wie bis 1.9.63 (Bewegung mit gedrückter Taste) wird gefunden."""
    alt = tmp_path / "klicktest_alt.py"
    alt.write_text('async def f(tab, x0, y0):\n'
                   '    await tab.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=x0 + 15, y=y0 + (12 if True else -12),\n'
                   '                  button="left", buttons=1)\n', encoding="utf-8")
    assert _zeichnet_selbst(alt) == [2]
