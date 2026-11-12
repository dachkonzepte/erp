"""Version 1.9.324 (Lohn L2c-1, Nachrunde, Punkt A): erzeugte Personalnummern in Tests und Skripten nur aus den erfundenen Kreisen.

    Anlass   1.9.321 (Arbeitskopie, nie auf main): in tests/test_v721 standen zwei echte Personalnummern -- die Reihe 00101, 00102 … aus älteren Tests
             fortgesetzt; tests/test_v708 erzeugte dieselbe Reihe mit f"00{100 + i}". Der Wächter tests/test_v644 sieht nur wörtliche Nummern in Dateien,
             die Git kennt -- eine erzeugte nie.
    Regel    ein f-String, der eine Personalnummer erzeugt (an datev_personnel_number, personalnummer oder pnr, oder an der Stelle der Personalnummer des
             Testhelfers person(w, nummer, vorname, pnr)), beginnt er mit Ziffern, dann mit einem erfundenen Kreis: 0009, 0019 oder 0029 (CLAUDE.md
             „Testen“, seit 1.9.244). Ein f-String ohne Ziffern am Anfang („D-{nr}“) ist keine fünfstellige Nummer und bleibt frei.
    Umfang   jede .py-Datei unter tests/ und scripts/.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KREISE = ("0009", "0019", "0029")
SCHLUESSEL = ("datev_personnel_number", "personalnummer", "pnr")


def erzeugte(text: str) -> list[tuple[int, str, str]]:
    """Je erzeugter Personalnummer (Zeile, Ziffern am Anfang, Ausdruck) -- nur f-Strings mit Ziffern am Anfang."""
    funde = []
    for k in ast.walk(ast.parse(text)):
        if not isinstance(k, ast.Call):
            continue
        werte = [kw.value for kw in k.keywords if kw.arg in SCHLUESSEL]
        if isinstance(k.func, ast.Name) and k.func.id == "person" and len(k.args) >= 4:
            werte.append(k.args[3])
        for v in werte:
            if isinstance(v, ast.JoinedStr) and v.values and isinstance(v.values[0], ast.Constant):
                anfang = re.match(r"\d*", str(v.values[0].value)).group(0)
                if anfang:
                    funde.append((v.lineno, anfang, ast.unparse(v)))
    return funde


def test_erzeugte_personalnummern_nur_aus_erfundenen_kreisen():
    falsch = []
    for p in sorted((ROOT / "tests").glob("*.py")) + sorted((ROOT / "scripts").glob("*.py")):
        try:
            text = p.read_text(encoding="utf-8")
            funde = erzeugte(text)
        except SyntaxError:
            continue
        falsch += [f"{p.relative_to(ROOT).as_posix()}:{zeile} {ausdruck}" for zeile, anfang, ausdruck in funde if not anfang.startswith(KREISE)]
    assert falsch == [], "erzeugte Personalnummern außerhalb der Kreise 0009x, 0019x, 0029x:\n" + "\n".join(falsch)


def test_der_waechter_findet():
    beispiel = '''
person(w, f"M-{i}", f"P{i}", f"00{100 + i}")
person(w, "M-1", "Ada", f"0009{i}")
EmployeePayrollSettings(employee_id=1, datev_personnel_number=f"0{100 + i}")
EmployeePayrollSettings(employee_id=1, datev_personnel_number=f"D-{nr}")
x(pnr=f"0019{i}", personalnummer=f"12{i}")
'''
    assert [(z, a) for z, a, _ in erzeugte(beispiel)] == [(2, "00"), (3, "0009"), (4, "0"), (6, "0019"), (6, "12")]
    assert [a for _, a, _ in erzeugte(beispiel) if not a.startswith(KREISE)] == ["00", "0", "12"]
