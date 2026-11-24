"""gunicorn und uvicorn genau in den Versionen des Servers (seit 1.11.4).

Auf dem Server laufen gunicorn 26.2.0 und uvicorn 0.52.4 (Betreiberangabe 24.11.2026). requirements.txt nennt genau diese Versionen,
und die Suite läuft mit ihnen. Geprüft für den Portal-Dienst, wie die Einheit erp-portal ihn startet (E4):
- gunicorn vertraut X-Forwarded-For ab Werk nur von 127.0.0.1 und ::1 -- weder Einheit noch Umgebung ändern das;
- ab Werk kein Zugriffsprotokoll (weder gunicorn noch uvicorn schreibt eine Zeile je Anfrage);
- der Arbeitsprozess ist der UvicornWorker; er bedient Anfragen und übernimmt die Liste der vertrauten Adressen von gunicorn.

Der echte Weg von gunicorn bis kurz vor dem Hauptprozess läuft in einem eigenen Prozess (`tests/gunicorn_wie_auf_dem_server.py`). Den Hauptprozess
selbst (fork, Signale) gibt es unter Windows nicht -- ihn belegt der ERP-Dienst auf dem Server mit denselben Versionen.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EINHEIT = ROOT / "scripts" / "server" / "erp-portal.service"
UMGEBUNG = ROOT / "scripts" / "server" / "portal.env.beispiel"
SKRIPT = ROOT / "tests" / "gunicorn_wie_auf_dem_server.py"

SERVER = {"gunicorn": "26.2.0", "uvicorn": "0.52.4"}  # Betreiberangabe 24.11.2026
ZEILEN = {"gunicorn": "gunicorn==26.2.0", "uvicorn": "uvicorn[standard]==0.52.4"}
PLATZHALTER_WINDOWS = {"fcntl", "grp", "pwd", "os.geteuid", "os.getegid", "socket.AF_UNIX", "WorkerTmp", "SIGQUIT-Handler"} | {
    f"signal.SIG{n}" for n in "HUP QUIT INT TERM TTIN TTOU USR1 USR2 WINCH CHLD ABRT".split()}


def _anforderungen() -> list[str]:
    return [z.split("#", 1)[0].strip() for z in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()]


def test_versionen_wie_auf_dem_server():
    zeilen = _anforderungen()
    for paket, zeile in ZEILEN.items():
        eigene = [z for z in zeilen if z.split("[")[0].split("=")[0].split(">")[0].split("<")[0].strip() == paket]
        assert eigene == [zeile], f"requirements.txt: {paket} genau in der Version des Servers ({zeile})"
        assert version(paket) == SERVER[paket], f"installiert ist {paket} {version(paket)} -- die Suite läuft mit der Version des Servers"


def _ausfuehren() -> list[str]:
    zeile = next(z for z in EINHEIT.read_text(encoding="utf-8").splitlines() if z.startswith("ExecStart="))
    teile = shlex.split(zeile.removeprefix("ExecStart="))
    assert teile[:3] == ["/srv/erp-code/.venv/bin/python", "-m", "gunicorn"], teile[:3]
    return teile[3:]


def _umgebung_der_einheit() -> dict[str, str]:
    """Was systemd dem Dienst gibt: Environment= und die EnvironmentFile (hier das Muster). Ohne DATABASE_URL -- gunicorn liest sie nicht, und
    an einen Kindprozess geht keine Verbindungszeichenfolge (Regel 27)."""
    umgebung: dict[str, str] = {}
    for z in EINHEIT.read_text(encoding="utf-8").splitlines():
        if z.startswith("Environment="):
            name, wert = z.removeprefix("Environment=").split("=", 1)
            umgebung[name] = wert
        elif z.startswith("EnvironmentFile="):
            assert z == "EnvironmentFile=/etc/dk-portal/portal.env", z
            for m in UMGEBUNG.read_text(encoding="utf-8").splitlines():
                if m and not m.startswith("#"):
                    name, wert = m.split("=", 1)
                    umgebung[name] = wert
    umgebung.pop("DATABASE_URL", None)
    return umgebung


@pytest.fixture(scope="module")
def lauf():
    umgebung = _umgebung_der_einheit()
    if os.name == "nt":
        umgebung["SYSTEMROOT"] = os.environ["SYSTEMROOT"]  # ohne sie keine Sockets unter Windows
    fertig = subprocess.run([sys.executable, "-I", str(SKRIPT), json.dumps(_ausfuehren())], cwd=ROOT, env=umgebung, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=60)
    assert fertig.returncode == 0, fertig.stderr[-3000:]
    return json.loads(fertig.stdout.strip().splitlines()[-1]), fertig.stdout + fertig.stderr


def test_umgebung_der_einheit_setzt_nichts_davon():
    umgebung = _umgebung_der_einheit()
    assert not {"FORWARDED_ALLOW_IPS", "GUNICORN_CMD_ARGS"} & set(umgebung), "die Vorgaben von gunicorn gelten nur ohne diese Variablen"
    verboten = ("--forwarded-allow-ips", "--access-logfile", "--log-syslog", "--log-config", "--log-config-dict", "--log-config-json", "-c", "--config")
    for arg in _ausfuehren():
        assert arg.split("=")[0] not in verboten, arg


def test_vertraut_nur_loopback(lauf):
    """E4: ab Werk nur 127.0.0.1 und ::1 -- gebunden ist der Dienst nur an 127.0.0.1, die Verbindung kommt also nur von nginx."""
    ergebnis, _ = lauf
    assert ergebnis["forwarded_allow_ips"] == ["127.0.0.1", "::1"]
    assert ergebnis["uvicorn_vertraut"] == ["127.0.0.1", "::1"]  # der UvicornWorker reicht die Liste an uvicorn weiter
    assert ergebnis["uvicorn_proxy_headers"] is True
    assert "--bind" in _ausfuehren() and _ausfuehren()[_ausfuehren().index("--bind") + 1] == "127.0.0.1:8010"


def test_kein_zugriffsprotokoll_ab_werk(lauf):
    ergebnis, ausgabe = lauf
    assert ergebnis["accesslog"] is None and ergebnis["syslog"] is False
    assert ergebnis["logconfig"] is None and ergebnis["logconfig_dict"] is False and ergebnis["logconfig_json"] is None
    assert ergebnis["zugriff_handler"] == 0 and ergebnis["zugriff_an"] is False
    assert ergebnis["uvicorn_log_config"] is None  # uvicorn richtet kein eigenes Protokoll ein, es schreibt in das von gunicorn
    assert "/zugriff-pruefpfad" not in ausgabe, "eine Zeile je Anfrage im Protokoll"
    assert "Application startup complete" in ausgabe  # das Fehlerprotokoll (Journal) bekommt den Start -- die Prüfung oben ist nicht still


def test_uvicorn_worker_bedient_anfragen(lauf):
    ergebnis, _ = lauf
    assert ergebnis["klasse"] == "uvicorn.workers.UvicornWorker" and ergebnis["workers"] == 1
    assert ergebnis["v4_ohne"] == "127.0.0.1"
    assert ergebnis["v4_xff"] == "198.51.100.9"
    assert ergebnis["v4_vorangestellt"] == "198.51.100.9"  # die vom Besucher vorangestellte Adresse hilft nicht
    if ergebnis["v6_xff"] is not None:
        assert ergebnis["v6_xff"] == "198.51.100.10"


def test_platzhalter_nur_unter_windows(lauf):
    ergebnis, _ = lauf
    if os.name == "nt":
        assert set(ergebnis["platzhalter"]) <= PLATZHALTER_WINDOWS, ergebnis["platzhalter"]
    else:
        assert ergebnis["platzhalter"] == []
