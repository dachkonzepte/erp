"""gunicorn so, wie die Einheit erp-portal ihn startet -- ohne den Hauptprozess (seit 1.11.4).

Läuft nur als eigener Prozess (`tests/test_v803_gunicorn_server.py`), nie im Testprozess selbst: unter Windows fehlen gunicorn
fcntl, grp, pwd, einige Signale und AF_UNIX -- dafür setzt dieses Skript leere Platzhalter ein, und nur hier. Unter Linux setzt es
keinen ein.

Ablauf wie `python -m gunicorn <Argumente aus ExecStart>` bis kurz vor dem Hauptprozess: die Argumente gehen durch den echten
Parser von gunicorn (`WSGIApplication`, auch Umgebung und eine gunicorn.conf.py im Arbeitsordner), der Logger ist der von
gunicorn, und der Arbeitsprozess ist die Klasse, die gunicorn daraus lädt (UvicornWorker) -- gebaut mit denselben Argumenten wie
im Hauptprozess (`Arbiter.spawn_worker`). Nicht dabei: fork, Signale, die Datei für den Herzschlag (unter Windows nicht
löschbar, solange sie offen ist) und das Laden der App -- statt des Portals bedient der Arbeitsprozess eine kleine App, die die
Adresse der Verbindung zurückgibt (das Portal selbst hinter echtem uvicorn: `tests/test_v802_portal_sitzung.py`).

Eingabe: die Argumente nach `-m gunicorn` als JSON in argv[1]; die Umgebung der Einheit kommt vom Aufrufer. Ausgabe: eine Zeile
JSON auf stdout. Das Protokoll von gunicorn geht nach stderr -- der Aufrufer prüft dort, dass keine Anfrage darin steht.
"""

from __future__ import annotations

import http.client
import json
import os
import signal
import socket
import sys
import threading
import time
import types
import warnings

PFAD = "/zugriff-pruefpfad"  # steht er im Protokoll, schrieb jemand ein Zugriffsprotokoll

platzhalter = []
for _name in ("fcntl", "grp", "pwd"):
    try:
        __import__(_name)
    except ImportError:
        sys.modules[_name] = types.ModuleType(_name)
        platzhalter.append(_name)
for _name in ("geteuid", "getegid"):
    if not hasattr(os, _name):
        setattr(os, _name, lambda: 0)
        platzhalter.append("os." + _name)
for _i, _name in enumerate("HUP QUIT INT TERM TTIN TTOU USR1 USR2 WINCH CHLD ABRT".split()):
    if not hasattr(signal, "SIG" + _name):
        setattr(signal, "SIG" + _name, 200 + _i)
        platzhalter.append("signal.SIG" + _name)
if not hasattr(socket, "AF_UNIX"):
    socket.AF_UNIX = 1
    platzhalter.append("socket.AF_UNIX")

from gunicorn.app.wsgiapp import WSGIApplication  # noqa: E402

sys.argv = ["gunicorn", *json.loads(sys.argv[1])]
anwendung = WSGIApplication("%(prog)s [OPTIONS] [APP_MODULE]", prog="gunicorn")
cfg = anwendung.cfg
log = cfg.logger_class(cfg)

if os.name == "nt":  # die Datei für den Herzschlag löscht gunicorn, solange sie offen ist -- unter Windows nicht möglich
    import gunicorn.workers.base as _basis

    class _Herzschlag:
        def __init__(self, cfg):
            pass

        def notify(self):
            pass

    _basis.WorkerTmp = _Herzschlag
    platzhalter.append("WorkerTmp")

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)  # uvicorn.workers ist in uvicorn 0.52 als veraltet markiert
    klasse = cfg.worker_class

ergebnis = {
    "platzhalter": platzhalter,
    "klasse": f"{klasse.__module__}.{klasse.__name__}",
    "workers": cfg.workers,
    "forwarded_allow_ips": list(cfg.forwarded_allow_ips),
    "accesslog": cfg.accesslog,
    "syslog": cfg.syslog,
    "logconfig": cfg.logconfig,
    "logconfig_dict": bool(cfg.logconfig_dict),
    "logconfig_json": cfg.logconfig_json,
    "zugriff_handler": len(log.access_log.handlers),
    "zugriff_an": bool(log.access_log_enabled),
}


def ausgeben():
    time.sleep(0.3)  # ein Zugriffsprotokoll schriebe nach der Antwort -- Zeit dafür lassen
    print(json.dumps(ergebnis))
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if ergebnis["klasse"] != "uvicorn.workers.UvicornWorker":  # anderer Arbeitsprozess: nur die Konfiguration melden, der Test sagt den Rest
    ausgeben()


async def echo(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            nachricht = await receive()
            if nachricht["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            else:
                await send({"type": "lifespan.shutdown.complete"})
                return
    inhalt = (scope["client"][0] if scope.get("client") else "").encode()
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-length", str(len(inhalt)).encode())]})
    await send({"type": "http.response.body", "body": inhalt})


v4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
v4.bind(("127.0.0.1", 0))
v4.listen()
steckdosen = [v4]
try:
    v6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    v6.bind(("::1", 0))
    v6.listen()
    steckdosen.append(v6)
except OSError:
    v6 = None

arbeiter = klasse(1, os.getpid(), steckdosen, anwendung, cfg.timeout / 2.0, cfg, log)  # wie Arbiter.spawn_worker
arbeiter.wsgi = echo
if os.name == "nt":  # loop.add_signal_handler gibt es unter Windows nicht
    arbeiter._install_sigquit_handler = lambda: None
    platzhalter.append("SIGQUIT-Handler")
threading.Thread(target=arbeiter.run, daemon=True).start()


def frage(host, port, xff):
    for _ in range(100):
        try:
            verbindung = http.client.HTTPConnection(host, port, timeout=5)
            verbindung.request("GET", PFAD, headers={"X-Forwarded-For": xff} if xff else {})
            antwort = verbindung.getresponse()
            return antwort.read().decode()
        except ConnectionRefusedError:
            time.sleep(0.05)
    raise RuntimeError("Arbeitsprozess antwortet nicht")


p4 = v4.getsockname()[1]
vertraut = arbeiter.config.forwarded_allow_ips
ergebnis.update({
    "uvicorn_vertraut": [vertraut] if isinstance(vertraut, str) else list(vertraut),
    "uvicorn_proxy_headers": arbeiter.config.proxy_headers,
    "uvicorn_log_config": arbeiter.config.log_config,
    "v4_ohne": frage("127.0.0.1", p4, None),
    "v4_xff": frage("127.0.0.1", p4, "198.51.100.9"),
    "v4_vorangestellt": frage("127.0.0.1", p4, "203.0.113.5, 198.51.100.9"),
    "v6_xff": frage("::1", v6.getsockname()[1], "198.51.100.10") if v6 else None,
})
ausgeben()
