"""Version 1.8.116 -- eine JS-Ausnahme in einem node-Test lässt den Test scheitern (Vorgabe vom 16.10.2026, Punkt 5; tests/node_lauf.py).

- Ein Programmfehler (TypeError, ReferenceError, SyntaxError, RangeError, URIError, EvalError) im Seitenskript lässt den Lauf scheitern --
  auch wenn die Seite ihn fängt (fast jede Seite fängt und zeigt den Fehler an), auch in einem async-Ablauf.
- Eine gewollte Ausnahme der Seite (Error) bleibt erlaubt, ebenso der Netzfehler "Failed to fetch" und die Fälle in ERLAUBT; ein Test kann
  für eine Attrappe, die absichtlich wirft, weitere erlauben.
- Jeder node-Lauf eines Tests geht über tests/node_lauf.py (AST), außer der reinen Syntaxprüfung in test_v398."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.node_lauf import NODE, ERLAUBT, ERLAUBT_TEXT, JsAusnahme, node_ausfuehren, node_lauf

pytestmark = pytest.mark.skipif(NODE is None, reason="node nicht installiert")
TESTS = Path(__file__).resolve().parent


def _ausgabe(js: str) -> str:
    return js + "\nprocess.stdout.write(JSON.stringify('fertig'));"


def test_ein_gefangener_typeerror_laesst_den_test_scheitern():
    js = _ausgabe("function zeichnen(){ try { const el = {}; el.remove(); } catch (e) { return 'Fehler: ' + e.message; } }\nzeichnen();")
    with pytest.raises(JsAusnahme, match=r"TypeError in zeichnen \(Zeile \d+\): el.remove is not a function"):
        node_ausfuehren(js)


def test_ein_referenceerror_im_async_ablauf_auch_gefangen():
    js = """(async () => { try { await (async () => { fehlerText(1); })(); } catch (e) {}
      process.stdout.write(JSON.stringify('fertig')); })();"""
    with pytest.raises(JsAusnahme, match=r"ReferenceError .*fehlerText is not defined"):
        node_ausfuehren(js)


def test_ein_ungefangener_fehler_ebenso():
    with pytest.raises(JsAusnahme, match=r"TypeError in \(oben\).*Cannot read properties of undefined"):
        node_lauf("const x = undefined; x.y;")


def test_eine_gewollte_ausnahme_der_seite_bleibt_erlaubt():
    js = _ausgabe("async function api(){ throw new Error('Kunde nicht gefunden.'); }\n"
                  "(async()=>{ try { await api(); } catch(e) {} })();\n"
                  "try { decodeURIComponent('%'); } catch (e) {}")
    with pytest.raises(JsAusnahme, match="URIError in \\(oben\\)"):
        node_ausfuehren(js)  # nur der URIError außerhalb von istLokalesZiel zählt
    assert node_ausfuehren(_ausgabe("try { throw new Error('gewollt'); } catch (e) {}")) == "fertig"


def test_die_erlaubten_faelle_mit_grund():
    assert node_ausfuehren(_ausgabe("function istLokalesZiel(w){ try { decodeURIComponent(w); } catch (e) { return false; } }\n"
                                    "istLokalesZiel('/%ff');")) == "fertig"
    assert node_ausfuehren(_ausgabe("try { throw new TypeError('Failed to fetch'); } catch (e) {}")) == "fertig"
    assert all(len(grund) > 30 for grund in (*ERLAUBT.values(), *ERLAUBT_TEXT.values()))
    js = _ausgabe("const attrappe = {json: () => { throw new SyntaxError('kein JSON'); }};\ntry { attrappe.json(); } catch (e) {}")
    with pytest.raises(JsAusnahme):
        node_ausfuehren(js)
    assert node_ausfuehren(js, erlaubt={("json", "SyntaxError"): "Attrappe: Antwort ohne JSON"}) == "fertig"


def test_ausnahmen_in_node_selbst_zaehlen_nicht():
    assert node_ausfuehren(_ausgabe("try { require('gibt-es-nicht'); } catch (e) {}")) == "fertig"


def test_die_ausgabe_des_skripts_bleibt_unveraendert():
    assert node_ausfuehren("process.stdout.write(JSON.stringify({a: [1, 'ü']}));", "Europe/Berlin") == {"a": [1, "ü"]}


# ---------------------------------------------------------------------------
# Jeder node-Lauf eines Tests über tests/node_lauf.py
# ---------------------------------------------------------------------------

# Datei: Grund -- dort startet ein Test node ohne Seitenskript.
AUSNAHMEN = {
    "test_v398_speichern_baustein.py": "prüft nur die Syntax jedes Seitenskripts mit einem Parser (node -e), führt es nicht aus",
}


def _startet_node(knoten: ast.AST) -> bool:
    """subprocess.run/Popen/check_output mit einer Liste, deren erstes Element NODE oder "node" ist."""
    if not (isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Attribute)
            and knoten.func.attr in ("run", "Popen", "check_output", "call") and knoten.args):
        return False
    liste = knoten.args[0]
    if not isinstance(liste, ast.List) or not liste.elts:
        return False
    erstes = liste.elts[0]
    return (isinstance(erstes, ast.Name) and erstes.id in ("NODE", "node")) or \
        (isinstance(erstes, ast.Constant) and erstes.value == "node")


def test_jeder_node_lauf_geht_ueber_node_lauf():
    funde, gesehen = [], 0
    for pfad in sorted(TESTS.glob("*.py")):
        if pfad.name == "node_lauf.py":
            continue
        for knoten in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
            if _startet_node(knoten):
                gesehen += 1
                if pfad.name not in AUSNAHMEN:
                    funde.append(f"{pfad.name}:{knoten.lineno}")
    assert gesehen >= 1  # die Ausnahme selbst -- der Scanner sieht etwas
    assert funde == [], "node ohne tests/node_lauf.py (eine JS-Ausnahme bliebe ungesehen): " + ", ".join(funde)


def test_der_scanner_findet_einen_direkten_lauf():
    quelle = "import subprocess\nsubprocess.run([NODE], input='x')\nsubprocess.run(['node', '-e', 'x'])\nsubprocess.run(['python'])\n"
    assert [k.lineno for k in ast.walk(ast.parse(quelle)) if _startet_node(k)] == [2, 3]
