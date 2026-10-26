"""Seit 1.9.85 (Stufe 4, R5, Teil 1 Punkt 4; Befund vom 24.10.2026): der Port-Wettlauf zweier gleichzeitig startender Klicktests.

    Befund     zwischen _freier_port() und dem Start der Instanz nahm ein anderer Prozess den Port; _warte_auf() nahm jede HTTP-Antwort als
               „bereit“ -- der Klicktest lief gegen einen fremden Server und brach ab (klicktest_heute, 1.9.73)
    jetzt      ERP-Instanz: Kennung in der Umgebung (ERP_INSTANZ), /health nennt sie (nur mit ERP_ENV=development/test); bereit erst mit
               der eigenen Kennung und solange der eigene Prozess läuft (_eigene_instanz_bereit()), sonst beendet und auf einem neuen Port
               neu gestartet (_mit_eigenem_port(), höchstens START_VERSUCHE, mit --app-port keiner)
               Chrome: wählt den Port selbst (--remote-debugging-port=0) und nennt ihn in DevToolsActivePort seines Profils (_chrome_port())
"""

import ast
import http.server
import importlib.util
import json
import threading
from contextlib import contextmanager
from pathlib import Path

from app.routers import pages

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _werkzeug():
    spec = importlib.util.spec_from_file_location("cdp_klicktest_v506", SCRIPTS / "cdp_klicktest.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


W = _werkzeug()


class _Proc:
    """Attrappe eines Kindprozesses: läuft, bis beendet gesetzt ist."""
    def __init__(self, pid=4711, beendet=False):
        self.pid, self.beendet = pid, beendet

    def poll(self):
        return 1 if self.beendet else None


@contextmanager
def _server(antwort: dict | list, pfad: str):
    """Ein HTTP-Server auf einem freien Port, der unter pfad mit antwort (JSON) antwortet, sonst 404."""
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path != pfad:
                self.send_error(404)
                return
            daten = json.dumps(antwort).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(daten)))
            self.end_headers()
            self.wfile.write(daten)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    faden = threading.Thread(target=server.serve_forever, daemon=True)
    faden.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


# --- /health -------------------------------------------------------------------------------------------------------------------------

def test_health_nennt_die_kennung_nur_in_entwicklung_und_test(monkeypatch):
    monkeypatch.setenv("ERP_INSTANZ", "abc123")
    for umgebung, soll in (("development", "abc123"), ("test", "abc123"), ("production", None), ("", None)):
        monkeypatch.setenv("ERP_ENV", umgebung)
        assert pages.health().get("instanz") == soll, umgebung
    monkeypatch.delenv("ERP_INSTANZ")
    monkeypatch.setenv("ERP_ENV", "test")
    assert "instanz" not in pages.health()
    assert pages.health()["status"] == "ok"


# --- ERP-Instanz ---------------------------------------------------------------------------------------------------------------------

def test_fremder_server_unter_dem_port_ist_nicht_bereit():
    """Angriff (Befund): unter dem Port antwortet ein fremder Server (andere Kennung, oder /health gar nicht) -- nie „bereit“; solange
    der eigene Prozess läuft, bis zum Zeitlimit, endet er (Port war belegt), sofort „beendet“."""
    with _server({"status": "ok", "instanz": "fremd"}, "/health") as port:
        url = f"http://127.0.0.1:{port}/health"
        assert W._eigene_instanz_bereit(_Proc(), url, "meins", 1.0) == "zeitlimit"
        assert W._eigene_instanz_bereit(_Proc(beendet=True), url, "meins", 5.0) == "beendet"
    with _server({"ok": True}, "/anderes") as port:  # 404 unter /health
        assert W._eigene_instanz_bereit(_Proc(), f"http://127.0.0.1:{port}/health", "meins", 1.0) == "zeitlimit"


def test_eigene_kennung_ist_bereit():
    with _server({"status": "ok", "instanz": "meins"}, "/health") as port:
        assert W._eigene_instanz_bereit(_Proc(), f"http://127.0.0.1:{port}/health", "meins", 5.0) == "bereit"


def test_neuer_versuch_auf_neuem_port(monkeypatch):
    """Der erste Port gebunden von einem anderen (eigener Prozess beendet) -> beendet über seine PID, zweiter Versuch auf neuem Port."""
    beendet, versuche = [], []
    monkeypatch.setattr(W, "beenden", lambda pid: beendet.append(pid))
    monkeypatch.setattr(W, "_freier_port", lambda: 5002)

    def starten(port, kennung):
        versuche.append((port, kennung))
        return _Proc(pid=100 + len(versuche))

    ergebnis = W._mit_eigenem_port(starten, lambda proc, port, kennung: "beendet" if port == 5001 else "bereit",
                                   erster_port=5001, fest=False, name="ERP-Instanz")
    assert ergebnis is not None and ergebnis[1] == 5002 and ergebnis[0].pid == 102
    assert [p for p, _ in versuche] == [5001, 5002] and beendet == [101]
    assert versuche[0][1] != versuche[1][1]  # je Versuch eine neue Kennung


def test_fester_port_ohne_neuen_versuch_und_hoechstens_drei(monkeypatch):
    beendet, versuche = [], []
    monkeypatch.setattr(W, "beenden", lambda pid: beendet.append(pid))
    monkeypatch.setattr(W, "_freier_port", lambda: 6000 + len(versuche))

    def starten(port, kennung):
        versuche.append(port)
        return _Proc(pid=200 + len(versuche))

    assert W._mit_eigenem_port(starten, lambda *a: "zeitlimit", erster_port=5001, fest=True, name="ERP-Instanz") is None
    assert versuche == [5001] and beendet == [201]
    versuche.clear(); beendet.clear()
    assert W._mit_eigenem_port(starten, lambda *a: "beendet", erster_port=5001, fest=False, name="ERP-Instanz") is None
    assert len(versuche) == W.START_VERSUCHE == 3 and len(beendet) == 3


# --- Chrome --------------------------------------------------------------------------------------------------------------------------

def test_chrome_port_aus_dem_eigenen_profil(tmp_path):
    """Chrome wählt den Port (0) und nennt ihn mit dem Pfad des Browsers in DevToolsActivePort; /json/version bestätigt den Pfad."""
    pfad = "/devtools/browser/eigen-123"
    with _server({"webSocketDebuggerUrl": "ws://127.0.0.1:1" + pfad}, "/json/version") as port:
        (tmp_path / "DevToolsActivePort").write_text(f"{port}\n{pfad}", encoding="utf-8")
        assert W._chrome_port(_Proc(), tmp_path, 5.0) == port


def test_chrome_fremder_browser_oder_beendet_ist_nicht_bereit(tmp_path):
    """Angriff: die Datei nennt einen Port, unter dem ein anderer Browser antwortet (anderer Pfad) -- nicht bereit; ohne Datei ebenso;
    der eigene Prozess beendet -> sofort None."""
    with _server({"webSocketDebuggerUrl": "ws://127.0.0.1:1/devtools/browser/fremd"}, "/json/version") as port:
        (tmp_path / "DevToolsActivePort").write_text(f"{port}\n/devtools/browser/eigen-123", encoding="utf-8")
        assert W._chrome_port(_Proc(), tmp_path, 1.0) is None
        assert W._chrome_port(_Proc(beendet=True), tmp_path, 5.0) is None
    assert W._chrome_port(_Proc(), tmp_path / "leer", 1.0) is None


def test_der_ablauf_nimmt_die_pruefungen():
    """Struktur: _ablauf() startet die ERP-Instanz über _mit_eigenem_port() mit _eigene_instanz_bereit() an /health und Chrome mit
    --remote-debugging-port=0 über _chrome_port(); _warte_auf() nur noch für einen fest vorgegebenen CDP-Port."""
    quelle = (SCRIPTS / "cdp_klicktest.py").read_text(encoding="utf-8")
    ablauf = next(n for n in ast.walk(ast.parse(quelle)) if isinstance(n, ast.FunctionDef) and n.name == "_ablauf")
    text = ast.get_source_segment(quelle, ablauf)
    assert "_mit_eigenem_port(server_starten," in text
    assert '_eigene_instanz_bereit(proc, f"http://127.0.0.1:{port}/health", kennung, 60)' in text
    assert "env[INSTANZ_ENV] = kennung" in text
    assert 'f"--remote-debugging-port={args.cdp_port or 0}"' in text
    assert '_chrome_port(chrome, ordner / "chrome-profile", 30)' in text
    assert text.count("_warte_auf(") == 1 and 'if args.cdp_port:' in text
