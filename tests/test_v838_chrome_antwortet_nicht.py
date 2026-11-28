"""Version 1.11.48 -- eine Grenze für jeden Befehl an Chrome im Klicktest-Werkzeug (Vorgabe des Betriebs vom 28.11.2026).

Im Endlauf auf dc8dfadb (27.11.2026) hing klicktest_kontakt_vermerken 15 Minuten bis zum Zeitlimit von klicktest_alle.py: der Server hatte jede Anfrage
beantwortet, Chrome antwortete auf einen Befehl des Werkzeugs nicht mehr, und Tab.cmd() wartete ohne Grenze auf die Antwort.

    Grenze        Tab.cmd() wartet höchstens CMD_SEKUNDEN (60) auf die Antwort, danach ChromeAntwortetNicht
    ab Senden     Ereignisse zwischendurch (Netzwerk, Konsole) verlängern die Grenze nicht
    Meldung       „XX  Chrome antwortet nicht: <Befehl> ohne Antwort nach 60 s (Ausdruck: …), Seite …“, darunter das Netzprotokoll
    danach        jeder weitere Befehl des Tabs endet sofort mit derselben Meldung -- nichts geht mehr hinaus
    durch warten  keine Unterklasse von RuntimeError: warten() und oeffnen() fangen RuntimeError (Navigation) und warteten sonst weiter
    Antwort       eine Antwort innerhalb der Grenze kommt wie bisher an, auch nach Ereignissen
    Wiederholung  klicktest_alle.py wiederholt einen Lauf mit „Chrome antwortet nicht“ nie, auch wenn darunter nur nicht angekommene Anfragen stehen
Das Ende eines Klicktests damit (klicktest_main(): eine Zeile statt eines Tracebacks, Rückgabecode 1) ist mit echtem Chrome von Hand geprüft (Archiv
„Testablauf“, 1.11.48) -- ein Klicktest mit Chrome im Testlauf wäre zu schwer für eine Zeile Ausgabe.
"""

import asyncio
import importlib.util
import json
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _laden(name: str, datei: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / datei)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


CDP = _laden("cdp_klicktest_v838", "cdp_klicktest.py")
ALLE = _laden("klicktest_alle_v838", "klicktest_alle.py")


class Chrome:
    """Attrappe der Verbindung: nimmt jeden Befehl an; antwortet nie -- oder nach `antwort_nach` Sekunden auf den zuletzt gesendeten; liefert alle
    `takt` Sekunden ein Ereignis der Konsole (wie Chrome, das weiter Ereignisse schickt, aber auf den Befehl nicht antwortet)."""

    def __init__(self, *, takt: float | None = None, antwort_nach: float | None = None):
        self.gesendet: list[dict] = []
        self.takt, self.antwort_nach = takt, antwort_nach
        self._seit = time.monotonic()

    async def send(self, text: str) -> None:
        self.gesendet.append(json.loads(text))
        self._seit = time.monotonic()

    async def recv(self) -> str:
        while True:
            if self.antwort_nach is not None and time.monotonic() - self._seit >= self.antwort_nach:
                self.antwort_nach = None
                return json.dumps({"id": self.gesendet[-1]["id"], "result": {"ok": True}})
            if self.takt is not None:
                await asyncio.sleep(self.takt)
                return json.dumps({"method": "Runtime.consoleAPICalled", "params": {"type": "log", "args": [{"value": "x"}]}})
            await asyncio.sleep(0.01)


def _tab(chrome: Chrome, tmp_path: Path):
    return CDP.Tab(chrome, "http://127.0.0.1:1", tmp_path / "shots")


def _lauf(coro, grenze: float = 5):
    """Führt coro aus; endet sie nicht in `grenze` Sekunden, ist das ein Fehler des Tests (die Gegenprobe ohne Grenze hinge sonst ewig)."""
    async def mit_grenze():
        return await asyncio.wait_for(coro, grenze)
    start = time.monotonic()
    try:
        return asyncio.run(mit_grenze()), None, time.monotonic() - start
    except Exception as exc:  # noqa: BLE001 -- die Tests prüfen die Art
        return None, exc, time.monotonic() - start


@pytest.fixture
def kurz(monkeypatch):
    monkeypatch.setattr(CDP, "CMD_SEKUNDEN", 0.3)


def test_vorgabe_sechzig_sekunden():
    assert CDP.CMD_SEKUNDEN == 60
    assert not issubclass(CDP.ChromeAntwortetNicht, RuntimeError)


def test_grenze_mit_meldung(kurz, tmp_path, capsys):
    chrome = Chrome()
    tab = _tab(chrome, tmp_path)
    tab.seite = "/customers/7"
    _, fehler, dauer = _lauf(tab.cmd("Runtime.evaluate", expression="new Promise(()=>{})\n  .then(x=>x)", returnByValue=True, awaitPromise=True))
    assert isinstance(fehler, CDP.ChromeAntwortetNicht), repr(fehler)
    assert 0.25 <= dauer < 3, dauer
    soll = ("Chrome antwortet nicht: Runtime.evaluate ohne Antwort nach 0.3 s (Ausdruck: new Promise(()=>{}) .then(x=>x)), Seite /customers/7 -- "
            "der Klicktest endet hier")
    assert str(fehler) == soll and tab.stumm == soll and soll in tab.nicht_geladen
    zeilen = capsys.readouterr().out.splitlines()
    assert zeilen[0] == f"XX  {soll}" and zeilen[0].startswith(f"XX  {CDP.CHROME_STUMM}")
    assert zeilen[1].startswith("    Netzwerk:"), zeilen  # das Netzprotokoll darunter


def test_ereignisse_verlaengern_die_grenze_nicht(kurz, tmp_path):
    chrome = Chrome(takt=0.05)
    _, fehler, dauer = _lauf(_tab(chrome, tmp_path).cmd("Page.navigate", url="http://127.0.0.1:1/"))
    assert isinstance(fehler, CDP.ChromeAntwortetNicht), repr(fehler)
    assert dauer < 3, dauer
    assert "Page.navigate ohne Antwort" in str(fehler) and "Ausdruck" not in str(fehler) and "Seite -" in str(fehler)


def test_danach_geht_nichts_mehr_hinaus(kurz, tmp_path):
    chrome = Chrome()
    tab = _tab(chrome, tmp_path)
    _, erster, _ = _lauf(tab.cmd("Runtime.evaluate", expression="1"))
    _, zweiter, dauer = _lauf(tab.cmd("Runtime.evaluate", expression="2"))
    assert isinstance(zweiter, CDP.ChromeAntwortetNicht) and str(zweiter) == str(erster)
    assert dauer < 0.2 and len(chrome.gesendet) == 1


@pytest.mark.parametrize("aufruf", ["warten", "oeffnen"])
def test_geht_durch_warten_und_oeffnen(kurz, tmp_path, aufruf):
    tab = _tab(Chrome(), tmp_path)
    coro = tab.warten("true", 10) if aufruf == "warten" else tab.oeffnen("/kunden", "true", 10)
    _, fehler, dauer = _lauf(coro)
    assert isinstance(fehler, CDP.ChromeAntwortetNicht), repr(fehler)
    assert dauer < 3, dauer
    if aufruf == "oeffnen":
        assert "Page.navigate ohne Antwort" in str(fehler) and "Seite /kunden" in str(fehler)


def test_antwort_innerhalb_der_grenze(monkeypatch, tmp_path):
    monkeypatch.setattr(CDP, "CMD_SEKUNDEN", 2)
    tab = _tab(Chrome(takt=0.02, antwort_nach=0.2), tmp_path)
    ergebnis, fehler, _ = _lauf(tab.cmd("Runtime.evaluate", expression="1"))
    assert fehler is None and ergebnis == {"ok": True} and tab.stumm is None


NICHT_ANGEKOMMEN = ("    Netzwerk: 1 offen\n      GET /api/x [Fetch]  seit 12:00:00.000 (61,0 s)  gesendet: ja  Antwort-Kopf: nein\n"
                    "          Server: nicht angekommen (keine passende Anfrage im Verbindungsprotokoll)\n")


def test_keine_wiederholung():
    # Derselbe Block nach einer anderen Abweichung würde wiederholt -- nach „Chrome antwortet nicht“ nie.
    assert ALLE.nur_nicht_angekommen("XX  /kunden: Seite nicht bereit (true)\n" + NICHT_ANGEKOMMEN) == ["GET /api/x [Fetch]"]
    stumm = (f"XX  {CDP.CHROME_STUMM}: Runtime.evaluate ohne Antwort nach 60 s (Ausdruck: 1), Seite /kunden -- der Klicktest endet hier\n"
             + NICHT_ANGEKOMMEN)
    assert ALLE.nur_nicht_angekommen(stumm) is None
    assert ALLE.nur_nicht_angekommen("XX  /kunden: Seite nicht bereit (true)\n" + NICHT_ANGEKOMMEN + stumm) is None
    assert ALLE.CHROME_STUMM == CDP.CHROME_STUMM
