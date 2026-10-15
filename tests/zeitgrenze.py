"""Zeitgrenze je Test (seit 1.8.111, Vorgabe "Vor dem Abnahmetest" Punkt 7; docs/archiv/testablauf-und-klicktests.md).

Ein hängender Test hielt bis 1.8.110 den ganzen Lauf an -- im Nachtrag 2 zu 1.8.108 stand ein paralleler Lauf 23 min bei 99 %, bis
er von Hand beendet wurde (Nebenbefund 5). Jetzt läuft je Test eine Uhr in einem eigenen Thread (unabhängig davon, worauf der Test
wartet -- eine Sperre in PostgreSQL, ein Kindprozess, ein Socket). Läuft sie ab, schreibt sie an der Ausgabe-Umleitung von pytest
vorbei "ZEITGRENZE: <Test> …" und den Stapel aller Threads auf die Konsole und beendet den Testprozess mit CODE (os._exit -- ein in
C wartender Thread lässt sich nicht anders unterbrechen):

- im parallelen Lauf (pytest -n …) ist das ein Arbeitsprozess: xdist meldet den Test als Fehler ("worker … crashed while running
  …"), startet einen neuen Arbeitsprozess und der Lauf geht weiter. Mit --dist loadfile gibt xdist dabei die ganze Datei zurück,
  einschließlich des abgestürzten Tests -- er liefe wieder bis zur Grenze, bis xdist keine Arbeitsprozesse mehr ersetzt (gemessen:
  achtmal, der übrige Test der Datei lief nie). Deshalb schreibt die Uhr den Test vor dem Beenden in eine Datei des Laufs
  (Kennung des Laufs aus config.workerinput -- nicht aus der Umgebung: die erbt auch ein pytest, das ein Test als Unterprozess startet),
  und schon_abgelaufen() meldet ihn beim nächsten Versuch sofort als Fehler, ohne ihn auszuführen;
- ohne -n endet der Lauf dort, mit Rückgabecode CODE.

Ein dabei liegen gebliebenes Testschema in PostgreSQL löscht der nächste Lauf beim Start (seit 1.8.108). Die Uhr umfasst Aufbau,
Test und Abbau eines Tests (pytest_runtest_protocol).

Grenze: GRENZE (Vorgabe), für einen einzelnen Test @pytest.mark.zeitgrenze(sekunden), für den ganzen Lauf --zeitgrenze SEK; 0 schaltet
die Uhr ab (zum Untersuchen im Debugger)."""

from __future__ import annotations

import faulthandler
import os
import sys
import tempfile
import threading
from pathlib import Path

GRENZE = 300.0  # Sekunden je Test, Herleitung im Archiv (längster Test im parallelen Lauf rund 60 s)
CODE = 3
MARKER = "zeitgrenze"


def grenze_fuer(item) -> float | None:
    """Sekunden für diesen Test; None = keine Uhr."""
    lauf = item.config.getoption("--zeitgrenze")
    if lauf is not None and lauf <= 0:
        return None
    marke = item.get_closest_marker(MARKER)
    if marke is not None and marke.args:
        return float(marke.args[0])
    return float(lauf) if lauf is not None else GRENZE


def _protokoll(config) -> Path | None:
    """Datei des parallelen Laufs mit den Tests, deren Zeitgrenze schon abgelaufen ist; None außerhalb eines Arbeitsprozesses von
    xdist."""
    lauf = getattr(config, "workerinput", {}).get("testrunuid")
    return Path(tempfile.gettempdir()) / f"erp_pytest_zeitgrenze_{lauf}.txt" if lauf else None


def schon_abgelaufen(item) -> bool:
    datei = _protokoll(item.config)
    try:
        return datei is not None and item.nodeid in datei.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return False


class Uhr:
    def __init__(self, item, sekunden: float):
        self.item, self.sekunden = item, sekunden
        self._timer = threading.Timer(sekunden, self._ablauf)
        self._timer.daemon = True

    def __enter__(self):
        self._timer.start()
        return self

    def __exit__(self, *exc):
        self._timer.cancel()
        return False

    def _ablauf(self) -> None:
        try:
            capman = self.item.config.pluginmanager.getplugin("capturemanager")
            if capman is not None:
                capman.suspend_global_capture(in_=True)
        except Exception:  # noqa: BLE001 -- die Meldung soll trotzdem hinaus
            pass
        try:
            datei = _protokoll(self.item.config)
            if datei is not None:
                with open(datei, "a", encoding="utf-8") as f:
                    f.write(self.item.nodeid + "\n")
                    f.flush()
                    os.fsync(f.fileno())
        except OSError:
            pass
        try:
            sys.stderr.write(f"\n\nZEITGRENZE: {self.item.nodeid} läuft länger als {self.sekunden:.0f} s -- der Testprozess "
                             f"(PID {os.getpid()}) wird beendet. Stapel aller Threads:\n")
            sys.stderr.flush()
            faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
            sys.stderr.flush()
        finally:
            os._exit(CODE)


def option_anmelden(parser) -> None:
    parser.addoption(
        "--zeitgrenze", type=float, metavar="SEK", default=None,
        help=f"Zeitgrenze je Test in Sekunden (Vorgabe {GRENZE:.0f}; 0 = aus). Läuft sie ab, wird der Testprozess mit Stapel aller "
             "Threads beendet -- im parallelen Lauf geht der Lauf ohne diesen Test weiter (seit 1.8.111).",
    )


def marker_anmelden(config) -> None:
    config.addinivalue_line("markers", f"{MARKER}(sekunden): eigene Zeitgrenze für diesen Test (seit 1.8.111, tests/zeitgrenze.py)")
