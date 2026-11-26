"""Attrappe von nginx für Tests und Klicktests des Kundenportals (seit 1.11.34, Stufe P2b; Bauplan P2, B2.1) -- nur lokal, nur 127.0.0.1.

Lokal (Windows) gibt es kein nginx. Diese Attrappe steht vor dem Portal-Dienst und macht genau das, was der Block für kunde.dachkonzepte.gmbh mit den Dateien
macht (scripts/server/nginx-kunde.conf):
- jede Anfrage geht unverändert an den Dienst (Host und Kopfzeilen wie vom Browser);
- antwortet der Dienst mit X-Accel-Redirect auf /_portal_dateien/<Name>, liefert sie die Datei aus dem Ordner der Kopien -- mit den Kopfzeilen, die nginx
  dabei aus der Antwort des Dienstes übernimmt (UEBERNOMMEN: wie die Tabelle der Kopfzeilen von nginx, Feld „redirect“), und mit genau den add_header des
  internal-Blocks, gelesen aus der nginx-Datei selbst (so laufen Attrappe und Datei nicht auseinander); den Typ nimmt sie wie nginx aus der Antwort des
  Dienstes, sonst aus „types“ nach der Endung, sonst default_type;
- /_portal_dateien/ direkt ist 404 (internal), ebenso ein Name, der nicht wie eine Kopie aussieht, oder eine fehlende Datei;
- Range und HEAD wie nginx für eine statische Datei (eine Spanne „bytes=a-b“; sonst die ganze Datei).

Startet nur mit ERP_ENV development oder test und bindet nur an 127.0.0.1. Gebraucht von tests/test_v825_portal_dateien.py und
scripts/klicktest_portal_dateien.py.
"""

from __future__ import annotations

import http.client
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NGINX = ROOT / "scripts" / "server" / "nginx-kunde.conf"
INTERN = "/_portal_dateien/"
NAME = re.compile(r"^[0-9a-f]{64}\.(pdf|jpg)$")
# Was nginx bei X-Accel-Redirect aus der Antwort des Upstreams übernimmt (ngx_http_upstream.c, ngx_http_upstream_headers_in[], Feld redirect = 1)
UEBERNOMMEN = ("content-type", "content-disposition", "cache-control", "expires", "accept-ranges", "set-cookie")
HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "proxy-authenticate", "proxy-authorization"}


def internal_block(conf: Path = NGINX) -> dict:
    """add_header, types und default_type des Blocks location /_portal_dateien/ aus der nginx-Datei."""
    text = conf.read_text(encoding="utf-8")
    start = text.index("location /_portal_dateien/ {")
    tiefe, i = 0, start
    while True:
        if text[i] == "{":
            tiefe += 1
        elif text[i] == "}":
            tiefe -= 1
            if tiefe == 0:
                break
        i += 1
    block = "\n".join(z.split("#")[0] for z in text[start:i + 1].splitlines())
    kopf = [(m.group(1), m.group(2) if m.group(2) is not None else m.group(3))
            for m in re.finditer(r'add_header\s+(\S+)\s+(?:"([^"]*)"|(\S+))\s+always\s*;', block)]
    typen = re.search(r"types\s*\{([^}]*)\}", block)
    endungen = {}
    for eintrag in (typen.group(1).split(";") if typen else []):
        teile = eintrag.split()
        for endung in teile[1:]:
            endungen[endung] = teile[0]
    vorgabe = re.search(r"default_type\s+(\S+)\s*;", block)
    return {"kopf": kopf, "typen": endungen, "vorgabe": vorgabe.group(1) if vorgabe else "text/plain", "internal": re.search(r"\binternal\s*;", block) is not None}


class Attrappe:
    def __init__(self, oben_port: int, ordner: Path, conf: Path = NGINX):
        if os.environ.get("ERP_ENV") not in ("development", "test"):
            raise RuntimeError("Die Attrappe von nginx läuft nur mit ERP_ENV development oder test.")
        self.oben_port, self.ordner, self.block = oben_port, Path(ordner), internal_block(conf)
        attrappe = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _weiter(self):
                attrappe.bearbeiten(self)

            do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_TRACE = _weiter

        class Server(ThreadingHTTPServer):
            daemon_threads = True

            def handle_error(self, request, client_address):  # ein Browser, der eine ruhende Verbindung schließt, ist kein Fehler
                if isinstance(sys.exc_info()[1], ConnectionError):
                    return
                super().handle_error(request, client_address)

        self.server = Server(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.faden = threading.Thread(target=self.server.serve_forever, daemon=True)

    def starten(self) -> int:
        self.faden.start()
        return self.port

    def beenden(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    # --- eine Anfrage ----------------------------------------------------------------------------------------------------------------------------

    def _senden(self, h, status: int, kopf: list[tuple[str, str]], koerper: bytes) -> None:
        h.send_response_only(status)
        for k, v in kopf:
            h.send_header(k, v)
        h.send_header("Content-Length", str(len(koerper)))
        h.end_headers()
        if h.command != "HEAD":
            h.wfile.write(koerper)

    def bearbeiten(self, h) -> None:
        if h.path.split("?", 1)[0].startswith(INTERN):
            self._senden(h, 404, [("Content-Type", "text/html")], b"<html><body>404 Not Found</body></html>")
            return
        laenge = int(h.headers.get("Content-Length") or 0)
        koerper = h.rfile.read(laenge) if laenge else b""
        oben = http.client.HTTPConnection("127.0.0.1", self.oben_port, timeout=30)
        try:
            oben.putrequest(h.command, h.path, skip_host=True, skip_accept_encoding=True)
            for k, v in h.headers.items():
                if k.lower() not in HOP and k.lower() != "content-length":
                    oben.putheader(k, v)
            oben.putheader("X-Forwarded-For", h.client_address[0])
            oben.putheader("Content-Length", str(len(koerper)))
            oben.endheaders(koerper)
            antwort = oben.getresponse()
            inhalt = antwort.read()
            kopf = [(k, v) for k, v in antwort.getheaders() if k.lower() not in HOP and k.lower() != "content-length"]
        finally:
            oben.close()
        ziel = next((v for k, v in kopf if k.lower() == "x-accel-redirect"), None)
        if ziel is None:
            self._senden(h, antwort.status, kopf, inhalt)
            return
        self._datei(h, ziel, kopf)

    def _datei(self, h, ziel: str, kopf_oben: list[tuple[str, str]]) -> None:
        name = ziel[len(INTERN):] if ziel.startswith(INTERN) else ""
        pfad = self.ordner / name
        if not NAME.match(name) or not pfad.is_file():
            self._senden(h, 404, [("Content-Type", "text/html")], b"<html><body>404 Not Found</body></html>")
            return
        daten = pfad.read_bytes()
        kopf = [(k, v) for k, v in kopf_oben if k.lower() in UEBERNOMMEN]
        if not any(k.lower() == "content-type" for k, _ in kopf):
            kopf.append(("Content-Type", self.block["typen"].get(name.rsplit(".", 1)[1], self.block["vorgabe"])))
        kopf += self.block["kopf"]
        kopf.append(("Accept-Ranges", "bytes"))
        spanne = re.fullmatch(r"bytes=(\d*)-(\d*)", h.headers.get("Range") or "")
        if spanne and (spanne.group(1) or spanne.group(2)):
            a = int(spanne.group(1)) if spanne.group(1) else max(0, len(daten) - int(spanne.group(2)))
            b = int(spanne.group(2)) if spanne.group(1) and spanne.group(2) else len(daten) - 1
            b = min(b, len(daten) - 1)
            if a > b:
                self._senden(h, 416, [("Content-Range", f"bytes */{len(daten)}")] + self.block["kopf"], b"")
                return
            self._senden(h, 206, kopf + [("Content-Range", f"bytes {a}-{b}/{len(daten)}")], daten[a:b + 1])
            return
        self._senden(h, 200, kopf, daten)
