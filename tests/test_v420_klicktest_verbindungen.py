"""Version 1.8.115 -- Klicktest-Werkzeug: Verbindungsprotokoll des Servers und Ausgang hängender Anfragen (Vorgabe vom 16.10.2026,
Punkt 2; scripts/cdp_klicktest.py).

- Jede Klicktest-Instanz startet uvicorn mit --log-level trace und schreibt die Spur (Verbindungen, ASGI-Nachrichten) in
  verbindungen.log ihres Arbeitsordners (log_konfiguration()); das Netzprotokoll gleicht jede gemeldete Anfrage damit ab
  (server_stand(): angekommen, Antwort-Kopf, Körper, abgebrochen, fertig, Verbindung beendet -- oder nicht angekommen).
- Eine einmal als offen gemeldete Anfrage bekommt ihren Ausgang nachgetragen, sobald der Browser ihn meldet (fertig bzw.
  Network.loadingFailed), in der nächsten Meldung und am Ende des Laufs.

Die Spur hier von einem echten uvicorn (Kindprozess, kleine ASGI-App), damit das Format der Spur und das Lesen zusammenpassen."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from tests.test_v400_klicktest_netzwerk import BASIS, T0, W, antwort, eintrag, extra, fehlgeschlagen, fertig, navigiert, protokoll, rwbs

MINI_APP = '''
import asyncio

async def app(scope, receive, send):
    if scope["type"] != "http":
        return
    if scope["path"] == "/langsam":
        await asyncio.sleep(3)
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": b"ok"})
'''


def _freier_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def spur(tmp_path_factory):
    """Ein echter uvicorn mit der Log-Konfiguration des Werkzeugs: /schnell fertig, /langsam vom Client nach 0,5 s verlassen."""
    ordner = tmp_path_factory.mktemp("spur")
    (ordner / "mini_app.py").write_text(MINI_APP, encoding="utf-8")
    datei = ordner / W.VERBINDUNGEN_DATEI
    konfig = ordner / "uvicorn-log.json"
    konfig.write_text(json.dumps(W.log_konfiguration(datei)), encoding="utf-8")
    port = _freier_port()
    with open(ordner / "server.err.log", "wb") as err, open(ordner / "server.out.log", "wb") as out:
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "mini_app:app", "--app-dir", str(ordner), "--host", "127.0.0.1",
                                 "--port", str(port), "--log-config", str(konfig), "--log-level", "trace"],
                                stdout=out, stderr=err, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    try:
        basis = f"http://127.0.0.1:{port}"
        frist = time.time() + 30
        while True:
            try:
                urllib.request.urlopen(basis + "/schnell", timeout=2).read()
                break
            except OSError:
                assert proc.poll() is None and time.time() < frist, (ordner / "server.err.log").read_text(errors="replace")
                time.sleep(0.2)
        start_schnell = time.time()
        assert urllib.request.urlopen(basis + "/schnell", timeout=5).read() == b"ok"
        start_langsam = time.time()
        with pytest.raises(OSError):
            urllib.request.urlopen(basis + "/langsam", timeout=0.5).read()
        time.sleep(3.5)  # die App läuft weiter, bis sie den Abbruch bemerkt bzw. fertig ist
    finally:
        if proc.poll() is None:
            if os.name == "nt":  # nur der eigene Prozess, über seine PID (Regel 12)
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=30)
            else:
                proc.kill()
            proc.wait(timeout=15)
    return {"datei": datei, "basis": basis, "schnell": start_schnell, "langsam": start_langsam, "ordner": ordner}


def test_die_spur_steht_in_der_datei_der_instanz_mit_zeitstempel(spur):
    zeilen = spur["datei"].read_text(encoding="utf-8").splitlines()
    assert any("HTTP connection made" in z for z in zeilen) and any("HTTP connection lost" in z for z in zeilen)
    assert any("ASGI [" in z and "Started scope=" in z for z in zeilen)
    assert all(W._ZEILE.match(z) for z in zeilen), [z for z in zeilen if not W._ZEILE.match(z)][:3]
    # Inhalte nie in der Spur: Körper und Kopfzeilen nur als Platzhalter
    assert "b'ok'" not in "\n".join(zeilen) and "content-type" not in "\n".join(zeilen)
    # Meldungen ab INFO weiter auf stderr, die Spur nicht
    err = (spur["ordner"] / "server.err.log").read_text(encoding="utf-8", errors="replace")
    assert "Uvicorn running" in err and "ASGI [" not in err


def test_das_verbindungsprotokoll_liest_eine_fertige_und_eine_verlassene_anfrage(spur):
    aufgaben, verloren = W.verbindungsprotokoll_lesen(spur["datei"])
    schnell = [a for a in aufgaben if a["pfad"] == "/schnell" and a["start"] >= spur["schnell"] - 0.25][0]
    assert (schnell["methode"], schnell["status"], schnell["ausnahme"]) == ("GET", 200, False)
    assert schnell["start"] <= schnell["kopf"] <= schnell["koerper_fertig"] <= schnell["ende"]
    [langsam] = [a for a in aufgaben if a["pfad"] == "/langsam"]
    assert langsam["start"] >= spur["langsam"] - 0.25
    assert langsam["client"] in verloren and verloren[langsam["client"]] < langsam["start"] + 2


def test_das_netzprotokoll_sagt_wo_eine_anfrage_auf_dem_server_steht(spur):
    n = W.Netzprotokoll(spur["basis"], spur["datei"])
    for rid, pfad, start in (("1", "/schnell", spur["schnell"]), ("2", "/langsam", spur["langsam"]), ("3", "/nie", spur["langsam"])):
        n.ereignis("Network.requestWillBeSent", {"requestId": rid, "loaderId": "L", "request": {"url": spur["basis"] + pfad,
                                                                                               "method": "GET"},
                                                 "type": "Fetch", "wallTime": start, "timestamp": 1.0})
    schnell, langsam, nie = (n.server_stand(eintrag(n, rid)) for rid in "123")
    assert schnell.startswith("Server: [") and "Antwort-Kopf 200 +" in schnell and ", fertig +" in schnell
    assert "angekommen +" in langsam and ("Verbindung beendet +" in langsam or "Browser hat abgebrochen +" in langsam), langsam
    assert nie == "Server: nicht angekommen (keine passende Anfrage im Verbindungsprotokoll)"
    assert W.Netzprotokoll(BASIS).server_stand(eintrag(n, "1")) is None  # ohne Protokoll keine Zeile


def test_ein_bericht_zeigt_den_stand_auf_dem_server_unter_jeder_offenen_anfrage(spur):
    n = W.Netzprotokoll(spur["basis"], spur["datei"])
    n.ereignis("Page.frameNavigated", {"frame": {"id": "F", "loaderId": "L", "url": spur["basis"] + "/"}})
    n.ereignis("Network.requestWillBeSent", {"requestId": "9", "loaderId": "L", "request": {"url": spur["basis"] + "/langsam",
                                                                                           "method": "GET"},
                                             "type": "Fetch", "wallTime": spur["langsam"], "timestamp": 1.0})
    zeilen = n.bericht(jetzt=spur["langsam"] + 2)
    assert zeilen[0] == "    Netzwerk: 1 offen"
    assert zeilen[1].startswith("      GET /langsam [Fetch]  seit ") and zeilen[2].startswith("          Server: [")


# -- Ausgang zuvor offener Anfragen ----------------------------------------------------------------------------------------------

def test_der_ausgang_einer_gemeldeten_anfrage_wird_nachgetragen():
    n = protokoll(navigiert("L1", "/kunden"), rwbs("1", "/api/hängt", "POST", ts=100.0), extra("1"))
    assert n.bericht(jetzt=T0 + 5)[0] == "    Netzwerk: 1 offen"
    assert eintrag(n, "1")["gemeldet_offen"] and n.ausgaenge() == []
    n.ereignis(*fehlgeschlagen("1"))  # loadingFailed bei 101,0
    zeilen = n.bericht(jetzt=T0 + 6)
    assert "    Netzwerk: Ausgang zuvor als offen gemeldeter Anfragen: 1" in zeilen
    assert (f"      POST /api/hängt [Fetch]  seit {W._uhrzeit(T0)}  -> fehlgeschlagen: net::ERR_ABORTED (abgebrochen) nach 1,0 s"
            in zeilen)
    assert not any("Ausgang" in z for z in n.bericht(jetzt=T0 + 7)), "jeder Ausgang nur einmal"


def test_eine_spaet_fertige_anfrage_mit_status_und_dauer():
    n = protokoll(navigiert("L1", "/"), rwbs("1", "/api/langsam", ts=100.0), extra("1"))
    n.bericht(jetzt=T0 + 2)
    n.ereignis(*antwort("1", 200, ts=161.0))
    n.ereignis(*fertig("1", ts=161.2))
    zeilen = n.ausgang_bericht(jetzt=T0 + 70)
    assert zeilen == ["    Netzwerk: Ausgang zuvor als offen gemeldeter Anfragen: 1",
                      f"      GET /api/langsam [Fetch]  seit {W._uhrzeit(T0)}  -> fertig, Status 200 nach 61,2 s"]


def test_eine_nie_gemeldete_anfrage_bekommt_keinen_ausgang():
    n = protokoll(navigiert("L1", "/"), rwbs("1", "/api/x"), extra("1"), fehlgeschlagen("1"))
    assert n.ausgaenge() == [] and n.ausgang_bericht() == []


def test_am_ende_des_laufs_auch_die_noch_offenen():
    n = protokoll(navigiert("L1", "/"), rwbs("1", "/api/a"), rwbs("2", "/api/b"))
    n.bericht(jetzt=T0 + 3)
    n.ereignis(*fertig("1"))
    zeilen = n.ausgang_bericht(jetzt=T0 + 10)
    assert zeilen[0] == "    Netzwerk: Ausgang zuvor als offen gemeldeter Anfragen: 1"
    assert zeilen[2] == "    Netzwerk: zuvor als offen gemeldet, noch ohne Ausgang: 1"
    assert zeilen[3] == f"      GET /api/b [Fetch]  seit {W._uhrzeit(T0)}  -> noch offen nach 10,0 s"


def test_ein_neuer_ausgang_gilt_als_aenderung_der_meldung():
    n = protokoll(navigiert("L1", "/"), rwbs("1", "/api/a"), rwbs("2", "/api/b"))
    n.melden(jetzt=T0 + 2)
    assert n.melden(jetzt=T0 + 3)[0].startswith("    Netzwerk: unverändert")
    n.ereignis(*fertig("1"))
    zeilen = n.melden(jetzt=T0 + 4)
    assert any(z.startswith("    Netzwerk: Ausgang") for z in zeilen)


# -- Start der Instanz --------------------------------------------------------------------------------------------------------

def test_die_instanz_startet_uvicorn_mit_der_spur():
    quelle = (Path(W.__file__)).read_text(encoding="utf-8")
    assert '"--log-config", str(log_config), "--log-level", "trace"' in quelle
    assert 'uvicorn.run("app.main:app", host=host, port=port, log_config=log_config, log_level="trace")' in quelle
    assert 'print(f"Verbindungsprotokoll des Servers (uvicorn trace): {verbindungen}"' in quelle
    k = W.log_konfiguration(Path("x.log"))
    assert k["loggers"]["uvicorn.asgi"]["handlers"] == ["verbindungen"] and k["handlers"]["verbindungen"]["level"] == 5


def test_eine_nie_gesendete_anfrage_nimmt_nicht_die_serverzeile_ihrer_nachfolgerin(tmp_path):
    """Im Klicktest gefunden (klicktest_verbindungsprotokoll.py): die im Netz angehaltene Statusabfrage der Kundenakte bekam die
    Serverzeile der gleichen Abfrage der danach geöffneten Seite. Zugeordnet wird nur bis zum Start der nächsten gleichen Anfrage."""
    spur = tmp_path / "verbindungen.log"
    spur.write_text("\n".join([
        f"{T0 + 1.0:.3f} TRACE uvicorn.asgi 127.0.0.1:5000 - ASGI [7] Started scope={{'type': 'http', 'method': 'GET', 'path': '/api/x'}}",
        f"{T0 + 1.1:.3f} TRACE uvicorn.asgi 127.0.0.1:5000 - ASGI [7] Send {{'type': 'http.response.start', 'status': 200, 'headers': '<...>'}}",
        f"{T0 + 1.1:.3f} TRACE uvicorn.asgi 127.0.0.1:5000 - ASGI [7] Send {{'type': 'http.response.body', 'body': '<2 bytes>'}}",
        f"{T0 + 1.1:.3f} TRACE uvicorn.asgi 127.0.0.1:5000 - ASGI [7] Completed"]) + "\n", encoding="utf-8")
    n = W.Netzprotokoll(BASIS, spur)
    for rid, start in (("alt", T0), ("neu", T0 + 0.9)):
        n.ereignis("Network.requestWillBeSent", {"requestId": rid, "loaderId": "L", "request": {"url": BASIS + "/api/x", "method": "GET"},
                                                 "type": "Fetch", "wallTime": start, "timestamp": 1.0})
    assert n.server_stand(eintrag(n, "alt")) == "Server: nicht angekommen (keine passende Anfrage im Verbindungsprotokoll)"
    assert n.server_stand(eintrag(n, "neu")) == ("Server: [7] angekommen +0,1 s, Antwort-Kopf 200 +0,2 s, Körper gesendet +0,2 s, "
                                                  "fertig +0,2 s")
