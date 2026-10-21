"""Seit 1.9.19 (Runde 7, Punkt 6): scripts/klicktest_alle.py wiederholt einen Klicktest genau einmal, wenn seine einzige Abweichung eine
Anfrage ist, die nie beim Server ankam (Befund Runde 6, Punkt 2: Testaufbau, nicht das Programm), und weist das immer aus.

    Erkennen     nur_nicht_angekommen(): jede Zeile „XX“ trägt unmittelbar ein Netzwerkprotokoll, dessen offene Anfragen alle „Server:
                 nicht angekommen“ heißen (oder „unverändert seit der letzten Meldung“ danach) -- die zwei echten Fälle aus Runde 5 ja;
                 eine Abweichung ohne Netzwerkprotokoll, eine angekommene, fehlgeschlagene oder beim Seitenwechsel offen gebliebene
                 Anfrage, „keine offenen Anfragen“ oder ein Protokoll ohne Abweichung nein
    Ablauf       ausfuehren() mit Schein-Klicktests: wiederholt nur bei Rückgabecode 1 (bzw. eigenem Zeitlimit von klicktest_alle), nur
                 einmal, zweites Protokoll <name>.wiederholt.log, erstes bleibt; gezählt der zweite Lauf, mit Hinweis zum ersten
    Ausweisen    zusammenfassung(): „davon N wiederholt“ und je Wiederholung eine Zeile -- auch wenn der zweite Lauf wie erwartet war
"""

import importlib.util
import os
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location("klicktest_alle", SCRIPTS / "klicktest_alle.py")
ALLE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ALLE)

# Ausschnitte aus den zwei echten Fällen (Gesamtlauf kt_r5_440828e, Runde 5)
RAHMEN = """OK  Leiste buero dunkel 1440×900: keine JS-Fehler: []
XX  /: Seite nicht bereit (document.readyState==='complete'&&document.fonts.status==='loaded'&&!!window.__d)
    Netzwerk: 1 offen
      GET /api/payments/customer-balances [Fetch]  seit 12:56:03.283 (45,3 s)  gesendet: ja  Antwort-Kopf: nein
          Server: nicht angekommen (keine passende Anfrage im Verbindungsprotokoll)
XX  Leiste buero hell 1280×800: geladen: False   (erwartet True)
    Netzwerk: unverändert seit der letzten Meldung (1 offen)
OK  Leiste buero hell 1280×800: ohne Bildlauf, Version im Fenster: [False, True, True]
--  Netzwerk am Ende des Laufs (nicht wie erwartet):
    Netzwerk: 5 offen
810 von 811 Prüfungen wie erwartet, nicht geladen: ['/']. Screenshots: C:\\x\\shots
"""
OBJEKT = """Uhr der Instanz: heute ab 10:00 (Europe/Berlin)
XX  /maintenance-contracts: Seite nicht bereit (customers.length>0&&document.getElementById('qsoCustomer').options.length>1)
    Netzwerk: 1 offen
      GET /static/ds/ds-alte-namen.css?v=09c7f24ae2 [Stylesheet]  seit 13:00:43.587 (30,3 s)  gesendet: ja  Antwort-Kopf: nein
          Server: nicht angekommen (keine passende Anfrage im Verbindungsprotokoll)
XX  Schnellauftrag: nur Objekte des Kunden: None   (erwartet ['— Hauptadresse verwenden —', 'Halle Süd'])
    Netzwerk: unverändert seit der letzten Meldung (1 offen)
XX  Schnellauftrag: mit anderen Kunden: False   (erwartet True)
    Netzwerk: unverändert seit der letzten Meldung (1 offen)
"""


def test_die_zwei_echten_faelle_werden_erkannt():
    assert ALLE.nur_nicht_angekommen(RAHMEN) == ["GET /api/payments/customer-balances [Fetch]"]
    assert ALLE.nur_nicht_angekommen(OBJEKT) == ["GET /static/ds/ds-alte-namen.css?v=09c7f24ae2 [Stylesheet]"]


@pytest.mark.parametrize("protokoll", [
    "XX  Kopf: falsch   (erwartet richtig)\nOK  weiter\n",                                     # Abweichung ohne Netzwerkprotokoll
    RAHMEN + "XX  Leiste: Gruppen: []   (erwartet ['x'])\nOK  y\n",                            # dazu eine echte Abweichung
    "XX  a: b\n    Netzwerk: keine offenen Anfragen\n",                                        # nichts offen
    "XX  a: b\n    Netzwerk: 1 offen\n      GET /api/x [Fetch]  seit 1 (2 s)  gesendet: ja  Antwort-Kopf: nein\n"
    "          Server: [41] angekommen 12:00:00.100, keine Antwort\n",                          # angekommen, die App hängt
    "XX  a: b\n    Netzwerk: 1 offen\n      GET /api/x [Fetch]  seit 1 (2 s)  gesendet: ja  Antwort-Kopf: nein\n"
    "          Server: nicht angekommen (keine passende Anfrage im Verbindungsprotokoll)\n"
    "    Netzwerk: fehlgeschlagen: 1\n      POST /api/y [Fetch]  net::ERR_FAILED\n",           # dazu ein Fehlschlag
    "XX  a: b\n    Netzwerk: unverändert seit der letzten Meldung (1 offen)\n",                # unverändert ohne Bericht davor
    "OK  a\nBefüllen fehlgeschlagen.\n",                                                       # keine Abweichung
    "",
])
def test_andere_abweichungen_nicht(protokoll):
    assert ALLE.nur_nicht_angekommen(protokoll) is None


SCHEIN = """import pathlib, sys
zaehler = pathlib.Path({ordner!r}) / (pathlib.Path(__file__).stem + ".laeufe")
n = int(zaehler.read_text()) + 1 if zaehler.exists() else 1
zaehler.write_text(str(n))
art = {arten!r}[min(n, len({arten!r})) - 1]
if art == "ok":
    print("3 von 3 Prüfungen wie erwartet"); sys.exit(0)
if art == "nicht_angekommen":
    print({rahmen!r}); sys.exit(1)
if art == "nicht_angekommen_code2":
    print({rahmen!r}); sys.exit(2)
print("XX  Kopf: falsch   (erwartet richtig)\\n2 von 3 Prüfungen wie erwartet"); sys.exit(1)
"""


def _schein(ordner: Path, name: str, *arten: str) -> Path:
    datei = ordner / f"{name}.py"
    datei.write_text(SCHEIN.format(ordner=str(ordner), arten=list(arten), rahmen=RAHMEN), encoding="utf-8")
    return datei


def _laeufe(ordner: Path, name: str) -> int:
    return int((ordner / f"{name}.laeufe").read_text())


def test_ablauf_wiederholt_nur_den_einen_fall_genau_einmal(tmp_path):
    ausgabe = tmp_path / "aus"
    ausgabe.mkdir()
    skripte = [_schein(tmp_path, "klicktest_a", "nicht_angekommen", "ok"),       # wiederholt, dann wie erwartet
               _schein(tmp_path, "klicktest_b", "rot", "ok"),                    # echte Abweichung: nicht wiederholt
               _schein(tmp_path, "klicktest_c", "nicht_angekommen_code2", "ok"),  # Rückgabecode 2: nicht wiederholt
               _schein(tmp_path, "klicktest_d", "nicht_angekommen", "nicht_angekommen", "ok")]  # nur einmal wiederholt
    umgebung = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    zeilen = {z[0]: z for z in ALLE.ausfuehren([(skripte, 2)], ausgabe, umgebung, 120, 4)}
    assert sorted(zeilen) == ["klicktest_a", "klicktest_b", "klicktest_c", "klicktest_d"]
    hinweis = "1. Lauf ROT (1) 810/811, Anfrage nicht angekommen: GET /api/payments/customer-balances [Fetch]"
    assert zeilen["klicktest_a"][1:3] == ("OK", "3/3") and zeilen["klicktest_a"][4] == hinweis
    assert zeilen["klicktest_b"][1:3] == ("ROT (1)", "2/3") and zeilen["klicktest_b"][4] is None
    assert zeilen["klicktest_c"][1] == "ROT (2)" and zeilen["klicktest_c"][4] is None
    assert zeilen["klicktest_d"][1:3] == ("ROT (1)", "810/811") and zeilen["klicktest_d"][4] == hinweis
    assert [_laeufe(tmp_path, n) for n in ("klicktest_a", "klicktest_b", "klicktest_c", "klicktest_d")] == [2, 1, 1, 2]
    assert (ausgabe / "klicktest_a.log").exists() and (ausgabe / "klicktest_a.wiederholt.log").exists()
    assert "nicht angekommen" in (ausgabe / "klicktest_a.log").read_text(encoding="utf-8")
    assert not (ausgabe / "klicktest_b.wiederholt.log").exists()


def test_zusammenfassung_weist_jede_wiederholung_aus(tmp_path):
    zeilen = [("klicktest_a", "OK", "3/3", 12.0, "1. Lauf ROT (1) 810/811, Anfrage nicht angekommen: GET /api/x [Fetch]"),
              ("klicktest_b", "OK", "5/5", 3.0, None)]
    text = ALLE.zusammenfassung(zeilen, "zu 4 zugleich", 75.0, tmp_path)
    assert text[0] == "2 von 2 Klicktests wie erwartet (zu 4 zugleich), davon 1 wiederholt (nur Anfrage nicht angekommen), Laufzeit gesamt 1:15"
    assert text[1:] == ["  wiederholt: klicktest_a -- 1. Lauf ROT (1) 810/811, Anfrage nicht angekommen: GET /api/x [Fetch]; 2. Lauf OK 3/3 "
                        "(Protokolle: klicktest_a.log, klicktest_a.wiederholt.log)"]
    assert ALLE.zusammenfassung([zeilen[1]], "nacheinander", 3.0, tmp_path) == [
        "1 von 1 Klicktests wie erwartet (nacheinander), Laufzeit gesamt 0:03"]
