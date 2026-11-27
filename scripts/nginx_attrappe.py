"""Attrappe von nginx für Tests und Klicktests des Kundenportals (seit 1.11.34, Stufe P2b; Bauplan P2, B2.1) -- nur lokal, nur 127.0.0.1.

Lokal (Windows) gibt es kein nginx. Diese Attrappe steht vor dem Portal-Dienst und macht genau das, was der Block für kunde.dachkonzepte.gmbh mit den Dateien
macht (scripts/server/nginx-kunde.conf):
- jede Anfrage geht unverändert an den Dienst (Host und Kopfzeilen wie vom Browser);
- antwortet der Dienst mit X-Accel-Redirect auf /_portal_dateien/<Name>, liefert sie die Datei aus dem Ordner der Kopien -- mit den Kopfzeilen, die nginx
  dabei aus der Antwort des Dienstes übernimmt (UEBERNOMMEN: wie die Tabelle der Kopfzeilen von nginx, Feld „redirect“), und mit genau den add_header des
  internal-Blocks, gelesen aus der nginx-Datei selbst (so laufen Attrappe und Datei nicht auseinander); den Typ nimmt sie wie nginx aus der Antwort des
  Dienstes, sonst aus „types“ nach der Endung, sonst default_type;
- /_portal_dateien/ direkt ist 404 (internal), ebenso ein Name, der nicht wie eine Kopie aussieht, oder eine fehlende Datei; seit 1.11.47 wählt sie den Ort
  jeder Adresse wie nginx (ort_waehlen(): exakt, längster Präfix, ^~, Regex) -- von außen und für das Ziel eines X-Accel-Redirect;
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
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NGINX = ROOT / "scripts" / "server" / "nginx-kunde.conf"
INTERN = "/_portal_dateien/"
NAME = re.compile(r"^[0-9a-f]{64}\.(pdf|jpg)$")
# Was nginx bei X-Accel-Redirect aus der Antwort des Upstreams übernimmt (ngx_http_upstream.c, ngx_http_upstream_headers_in[], Feld redirect = 1)
UEBERNOMMEN = ("content-type", "content-disposition", "cache-control", "expires", "accept-ranges", "set-cookie")
HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "proxy-authenticate", "proxy-authorization"}


ORT = re.compile(r"\blocation\s+(?:(=|\^~|~\*|~)\s+)?(\S+)\s*\{")


def _ohne_kommentare(conf: Path) -> str:
    return "\n".join(z.split("#")[0] for z in conf.read_text(encoding="utf-8").splitlines())


def _ende(text: str, auf: int) -> int:
    """Index der schließenden Klammer zum „{“ an der Stelle auf (Blöcke dürfen verschachtelt sein, etwa types { … })."""
    tiefe = 0
    for i in range(auf, len(text)):
        if text[i] == "{":
            tiefe += 1
        elif text[i] == "}":
            tiefe -= 1
            if tiefe == 0:
                return i
    raise ValueError("Block ohne Ende")


@dataclass(frozen=True)
class Ort:
    art: str        # "=", "^~", "~", "~*" oder "" (Präfix ohne Zeichen)
    muster: str
    internal: bool


def orte(conf: Path = NGINX) -> list[Ort]:
    """Seit 1.11.47: die Orte (location) des Servers für Port 443 in der Reihenfolge der Datei, je mit internal."""
    text = _ohne_kommentare(conf)
    anfang = text.rfind("server {", 0, text.index("listen 443"))
    server = text[anfang:_ende(text, text.index("{", anfang)) + 1]
    gefunden = []
    for m in ORT.finditer(server):
        inhalt = server[m.end():_ende(server, m.end() - 1)]
        gefunden.append(Ort(m.group(1) or "", m.group(2), re.search(r"\binternal\s*;", inhalt) is not None))
    return gefunden


def ort_waehlen(pfad: str, orte_: list[Ort]) -> Ort | None:
    """Seit 1.11.47: welcher Ort eine Adresse nimmt -- in der Reihenfolge von nginx (ngx_http_core_find_location): ein exakter Ort (=) gewinnt sofort;
    sonst der längste passende Präfix-Ort; trägt er ^~, endet die Suche dort; sonst der erste passende Regex-Ort (~, ~* ohne Groß und klein) in der
    Reihenfolge der Datei; ohne ihn der längste Präfix-Ort. So nimmt die Attrappe von außen und beim X-Accel-Redirect denselben Ort wie nginx."""
    for o in orte_:
        if o.art == "=" and pfad == o.muster:
            return o
    praefix = max((o for o in orte_ if o.art in ("", "^~") and pfad.startswith(o.muster)), key=lambda o: len(o.muster), default=None)
    if praefix is not None and praefix.art == "^~":
        return praefix
    for o in orte_:
        if o.art in ("~", "~*") and re.search(o.muster, pfad, re.IGNORECASE if o.art == "~*" else 0):
            return o
    return praefix


def internal_block(conf: Path = NGINX) -> dict:
    """add_header, types und default_type des Blocks location ^~ /_portal_dateien/ aus der nginx-Datei (bis 1.11.46 ohne ^~)."""
    text = conf.read_text(encoding="utf-8")
    start = re.search(r"\blocation\s+(?:\^~\s+)?/_portal_dateien/\s*\{", text).start()
    i = _ende(text, text.index("{", start))
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
        self.oben_port, self.ordner, self.block, self.orte = oben_port, Path(ordner), internal_block(conf), orte(conf)
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
        ort = ort_waehlen(h.path.split("?", 1)[0], self.orte)  # seit 1.11.47 wie nginx; bis dahin nur „beginnt mit /_portal_dateien/“
        if ort is None or ort.internal:
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
        ort = ort_waehlen(ziel.split("?", 1)[0], self.orte)
        if ort is None or ort.muster != INTERN or not ort.internal:  # seit 1.11.47: der interne Weg muss im Block der Dateien landen, sonst ein Fehler
            self._senden(h, 500, [("Content-Type", "text/plain")], f"X-Accel-Redirect landet nicht im Block der Dateien: {ort}".encode())
            return
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
