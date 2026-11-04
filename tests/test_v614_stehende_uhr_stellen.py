"""Version 1.9.209 (Lohn L1a, Stufe 5, Punkt 2): klicktest_heute mit stehender Uhr in Instanz und Browser -- „Tag zusammen 3:15 h“ auf genau einem
Wert, auch unter Last.

    Werkzeug       scripts/cdp_klicktest.py: Tab.uhr_stellen(ms) stellt die stehende Uhr (klicktest_main(…, uhr="JJJJ-MM-TT HH:MM")) weiter --
                   die Instanz liest den Zeitpunkt bei jedem Blick auf die Uhr aus einer Datei im Arbeitsordner (KLICKTEST_UHR_DATEI), der
                   Browser aus window.__dkUhrFest (das geladene Dokument sofort, neue über ein neues Skript). Eine ganz stehende Uhr reichte nicht:
                   Wechsel und Feierabend fielen in dieselbe Sekunde, der Server lehnt das ab (berlin_now() ist sekundengenau)
    klicktest_heute stehende Uhr Mi 11.11.2026 10:00, Feierabend nach uhr_stellen(+10 s) -- „anwesend 0:00 h · Tag zusammen 3:15 h · … ·
                   gebucht 0,00 h“ genau; kein Warten auf die echte Uhr mehr (bis 1.9.208 performance.now() + 1,1 s, die Uhr lief)
"""

import ast
import asyncio
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from tests.node_lauf import node_ausfuehren

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import cdp_klicktest as kt  # noqa: E402

KLICKTEST = ROOT / "scripts" / "klicktest_heute.py"


# --- Werkzeug ---------------------------------------------------------------------------------------------------------------------------------

def test_stehende_uhr_der_instanz_folgt_der_datei(monkeypatch, tmp_path):
    from app import berlin_time

    datei = tmp_path / "uhr.txt"
    monkeypatch.setenv(kt.UHR_ENV, kt._uhr_marke("2026-11-11 10:00"))
    monkeypatch.setenv(kt.UHR_DATEI_ENV, str(datei))
    monkeypatch.setattr(berlin_time, "_utc_now", berlin_time._utc_now)  # nach dem Test wieder die echte Uhr
    kt._uhr_einsetzen()
    assert berlin_time.berlin_now().strftime("%Y-%m-%d %H:%M:%S") == "2026-11-11 10:00:00"  # ohne Datei: der Startpunkt
    datei.write_text(datetime(2026, 11, 11, 9, 0, 10, tzinfo=timezone.utc).isoformat(), encoding="utf-8")
    assert berlin_time.berlin_now().strftime("%H:%M:%S") == "10:00:10"
    assert berlin_time.berlin_now().strftime("%H:%M:%S") == "10:00:10", "steht weiter"
    datei.write_text("kaputt", encoding="utf-8")
    assert berlin_time.berlin_now().strftime("%H:%M:%S") == "10:00:00", "unlesbar: der Startpunkt"


def test_ohne_datei_wie_bisher(monkeypatch):
    from app import berlin_time

    monkeypatch.delenv(kt.UHR_DATEI_ENV, raising=False)
    monkeypatch.setenv(kt.UHR_ENV, kt._uhr_marke("2026-11-11 10:00"))
    monkeypatch.setattr(berlin_time, "_utc_now", berlin_time._utc_now)
    kt._uhr_einsetzen()
    assert berlin_time._utc_now().isoformat() == "2026-11-11T09:00:00+00:00"


def test_browser_uhr_folgt_dem_wert():
    skript = (kt.BROWSER_UHR_FEST % 1_000).replace("window.", "globalThis.") + """
const a = Date.now(); globalThis.__dkUhrFest = 11_000;
console.log(JSON.stringify({a, b: Date.now(), c: new Date().getTime(), d: new Date(5).getTime()}));"""
    assert node_ausfuehren(skript) == {"a": 1_000, "b": 11_000, "c": 11_000, "d": 5}


class _Tab(kt.Tab):
    def __init__(self):  # ohne Browser: nur die Befehle mitschreiben
        self.befehle, self.ausdruecke, self._uhr_skript = [], [], None

    async def cmd(self, method, **params):
        self.befehle.append((method, params))
        return {"identifier": str(len(self.befehle))}

    async def js(self, expr):
        self.ausdruecke.append(expr)
        return True


def test_uhr_stellen_schreibt_datei_und_browser(monkeypatch, tmp_path):
    monkeypatch.setattr(kt, "_STEHENDE_UHR_DATEI", tmp_path / "uhr.txt")
    tab = _Tab()
    asyncio.run(tab.browser_uhr_fest(1_794_387_600_000))  # Mi 11.11.2026 10:00 in Berlin
    asyncio.run(tab.uhr_stellen(1_794_387_610_000))
    assert (tmp_path / "uhr.txt").read_text(encoding="utf-8") == "2026-11-11T09:00:10+00:00"
    assert [m for m, _ in tab.befehle] == ["Page.addScriptToEvaluateOnNewDocument", "Page.removeScriptToEvaluateOnNewDocument",
                                          "Page.addScriptToEvaluateOnNewDocument"]
    assert tab.befehle[1][1] == {"identifier": "1"} and "1794387610000" in tab.befehle[2][1]["source"]
    assert tab.ausdruecke == ["window.__dkUhrFest=1794387610000;true"]


def test_uhr_stellen_nur_mit_stehender_uhr(monkeypatch):
    monkeypatch.setattr(kt, "_STEHENDE_UHR_DATEI", None)
    with pytest.raises(RuntimeError, match="nur mit stehender Uhr"):
        asyncio.run(_Tab().uhr_stellen(0))


# --- klicktest_heute --------------------------------------------------------------------------------------------------------------------------

def _aufrufe():
    return [n for n in ast.walk(ast.parse(KLICKTEST.read_text(encoding="utf-8"))) if isinstance(n, ast.Call)]


def test_klicktest_heute_steht():
    """Instanz: uhr="JJJJ-MM-TT HH:MM" (ein fester Tag, nicht der Lauftag); Browser: browser_uhr_fest(); weitergestellt nur über uhr_stellen() --
    kein Warten auf die echte Uhr (performance.now())."""
    aufrufe = _aufrufe()
    uhren = [k.value.value for n in aufrufe if isinstance(n.func, ast.Name) and n.func.id == "klicktest_main" for k in n.keywords
             if k.arg == "uhr" and isinstance(k.value, ast.Constant)]
    assert len(uhren) == 1 and re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", uhren[0]), uhren
    date.fromisoformat(uhren[0][:10])
    namen = [n.func.attr for n in aufrufe if isinstance(n.func, ast.Attribute)]
    assert "browser_uhr_fest" in namen and namen.count("uhr_stellen") == 2
    assert "performance.now()" not in KLICKTEST.read_text(encoding="utf-8")


def test_klicktest_heute_tag_zusammen_genau_ein_wert():
    """Die Prüfung „Feierabend: Ergebnis mit Tag zusammen“ vergleicht mit genau einem Text (bis 1.9.208 ein Muster mit „gebucht 0,0\\d h“)."""
    for n in _aufrufe():
        if isinstance(n.func, ast.Attribute) and n.func.attr == "pruefe" and isinstance(n.args[0], ast.Constant) \
                and n.args[0].value == "Feierabend: Ergebnis mit Tag zusammen":
            soll = n.args[2]
            assert isinstance(soll, ast.Constant), ast.unparse(soll)
            assert soll.value == "Feierabend gebucht: anwesend 0:00 h · Tag zusammen 3:15 h · Pause nach Zeitregel − 0:00 h · gebucht 0,00 h"
            return
    pytest.fail("Prüfung nicht gefunden")
