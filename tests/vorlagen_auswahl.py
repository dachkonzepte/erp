"""Scanner für den Wächter „Auswahlfeld mit gespeichertem Wert nur über auswahlOptionen()“ (seit 1.9.12, Runde 6 Punkt 1;
tests/test_v447_auswahl_altwerte.py).

Zwei Bauweisen wählen einen gespeicherten Wert außerhalb der Liste nicht vor (die Auswahl steht dann leer oder auf dem ersten Eintrag,
und das nächste Speichern schreibt das):

    P1  Optionen von Hand mit bedingtem selected -- `<option value="${…}" ${x===y?'selected':''}>` oder eine feste Option
        `<option value="a" ${x==='a'?'selected':''}>`; Kennung = der Vergleich ohne Leerzeichen
    P2  ein <select> der Vorlage bekommt seinen Wert per Zuweisung -- `getElementById('id').value = …`, `$('id').value = …`,
        `el('id').value = …` oder über einen Helfer `setv('id', …)` (const setv=(id,x)=>document.getElementById(id).value=…);
        Kennung = die id. Nicht gezählt: ein fester Text als Wert ('normal'), Ja/Nein (`x?'1':'0'`, `x?'true':'false'`)

Was hier nicht erscheint: auswahlOptionen() und auswahlWert() aus _auswahl.html (der richtige Weg) und _auswahl.html selbst. Grenzen: eine
Zuweisung über eine Variable (`const s=…; s.value=…`) oder einen anderen Helfer findet der Scanner nicht."""

import re

from tests import vorlagen_js as vj

P1 = re.compile(r"""<option\s+value=\\?["']?(?:\$\{[^}]*\}|[^"'$\s>]*)\\?["']?\s*\$\{([^}]*?)\?\s*['"`]\s*selected""")
ZUWEISUNG = re.compile(r"""(?:getElementById|\$|el)\(\s*['"]([\w-]+)['"]\s*\)\.value\s*=(?!=)\s*([^;\n]{0,80})""")
HELFER = re.compile(r"""(?:const|let|var)\s+(\w+)\s*=\s*\((\w+)\s*,\s*(\w+)\)\s*=>\s*document\.getElementById\(\2\)\.value\s*=""")
FESTER_TEXT = re.compile(r"""^(['"])[^'"]*\1\s*$""")
JA_NEIN = re.compile(r"""\?\s*'(1|true)'\s*:\s*'(0|false)'\s*\}*\s*$""")


def fundstellen(name: str, text: str | None = None) -> list[tuple[str, str, int]]:
    """(Art, Kennung, Zeile) je Fundstelle in der Vorlage name."""
    if text is None:
        text = (vj.TEMPLATES / name).read_text(encoding="utf-8")
    zeile = lambda pos: text.count("\n", 0, pos) + 1  # noqa: E731
    funde = [("P1", re.sub(r"\s+", "", m.group(1)), zeile(m.start())) for m in P1.finditer(text)]
    selects = set(re.findall(r"""<select[^>]*\bid=\\?["']([\w-]+)""", text))
    zuweisungen = [(m.group(1), m.group(2).strip(), m.start()) for m in ZUWEISUNG.finditer(text)]
    for helfer in {t[0] for t in HELFER.findall(text)}:
        muster = r"\b" + helfer + r"""\(\s*['"]([\w-]+)['"]\s*,\s*([^)\n]{0,80})\)"""
        zuweisungen += [(m.group(1), m.group(2).strip(), m.start()) for m in re.finditer(muster, text)]
    for sid, wert, pos in zuweisungen:
        if sid in selects and not FESTER_TEXT.match(wert) and not JA_NEIN.search(wert):
            funde.append(("P2", sid, zeile(pos)))
    return funde


def alle_fundstellen() -> dict[tuple[str, str, str], list[int]]:
    """{(Vorlage, Art, Kennung): [Zeilen]} über alle Vorlagen außer _auswahl.html."""
    out: dict[tuple[str, str, str], list[int]] = {}
    for name in vj.alle_vorlagen():
        if name == "_auswahl.html":
            continue
        for art, kennung, z in fundstellen(name):
            out.setdefault((name, art, kennung), []).append(z)
    return out
