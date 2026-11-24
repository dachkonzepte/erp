"""Schranke des Portal-Dienstes (seit 1.11.2, Bauplan P1, Abschnitt 3.5) -- eine ASGI-Hülle UM die App, damit jede Antwort sie durchläuft, auch die 500
aus der Fehlerbehandlung von Starlette.

Vor der App:
- Host nur der aus PORTAL_HERKUNFT, sonst 421 (eine Anfrage an den Dienst unter fremdem Namen -- etwa app.dachkonzepte.gmbh -- kommt nicht weiter).
- Methoden nur GET, HEAD und POST, sonst 405 (auch TRACE, OPTIONS, PUT, PATCH, DELETE und erfundene).
- Körper höchstens 16 KB (wie client_max_body_size in nginx), sonst 413 -- gelesen, bevor die App ihn sieht.
- Schreibend (POST) nur von der eigenen Seite: Sec-Fetch-Site same-origin, ohne Sec-Fetch-Site eine Origin gleich PORTAL_HERKUNFT, sonst 403. Eine Seite
  von app.dachkonzepte.gmbh ist same-site, nicht same-origin, und wird abgelehnt (wie Regel 33 im ERP).
Nach der App, an JEDER Antwort: Content-Security-Policy ohne Inline-Skript, Trusted Types, kein Einrahmen, nosniff, keine Referer, getrennte Fenster, keine
Geräte-APIs, Cache-Control no-store (wenn die Antwort keins setzt), HSTS (außer lokal und in Tests).

Antworten der Schranke selbst sind JSON {"fehler": <festes Wort>} -- nie ein Wert aus der Anfrage.

Seit 1.11.14: eine Design-Datei unter /static (app/design_dateien.py::ist_design_pfad(), wie im ERP) bekommt mit 200 „public, max-age=31536000,
immutable“ -- die Seite nennt ds.css mit ?v=<Prüfsumme>, die Schriften ändern sich nur mit neuem Namen; jede andere Antwort dort no-store.
"""

from __future__ import annotations

import json
import logging

from app.design_dateien import DAUERHAFT, ist_design_pfad

logger = logging.getLogger("dk_portal")

ERLAUBTE_METHODEN = frozenset({"GET", "HEAD", "POST"})
SCHREIBEND = frozenset({"POST"})
MAX_KOERPER = 16 * 1024

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; form-action 'self'; "
       "base-uri 'none'; frame-ancestors 'none'; object-src 'none'; require-trusted-types-for 'script'")
PERMISSIONS = ("accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=(), "
               "interest-cohort=()")


def schutz_kopfzeilen(nur_https: bool) -> list[tuple[bytes, bytes]]:
    kopf = [
        (b"content-security-policy", CSP.encode()),
        (b"x-frame-options", b"DENY"),
        (b"x-content-type-options", b"nosniff"),
        (b"referrer-policy", b"no-referrer"),
        (b"cross-origin-opener-policy", b"same-origin"),
        (b"cross-origin-resource-policy", b"same-origin"),
        (b"permissions-policy", PERMISSIONS.encode()),
    ]
    if nur_https:
        kopf.append((b"strict-transport-security", b"max-age=31536000"))
    return kopf


def _kopf(scope, name: bytes) -> str | None:
    for k, v in scope.get("headers") or ():
        if k.lower() == name:
            return v.decode("latin-1")
    return None


class Schranke:
    def __init__(self, app, einstellungen):
        self.app = app
        self.einstellungen = einstellungen
        self._kopf = schutz_kopfzeilen(einstellungen.nur_https)

    async def _antwort(self, send, status: int, fehler: str, extra: list[tuple[bytes, bytes]] = ()):
        koerper = json.dumps({"fehler": fehler}).encode()
        await send({"type": "http.response.start", "status": status, "headers": [
            (b"content-type", b"application/json"), (b"content-length", str(len(koerper)).encode()), (b"cache-control", b"no-store"),
            *extra, *self._kopf]})
        await send({"type": "http.response.body", "body": koerper})

    def _herkunft_passt(self, scope) -> bool:
        seite = _kopf(scope, b"sec-fetch-site")
        if seite is not None:
            return seite == "same-origin"
        return _kopf(scope, b"origin") == self.einstellungen.herkunft

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if (_kopf(scope, b"host") or "").lower() != self.einstellungen.host:
            await self._antwort(send, 421, "host")
            return
        methode = scope["method"]
        if methode not in ERLAUBTE_METHODEN:
            await self._antwort(send, 405, "methode", [(b"allow", b"GET, HEAD, POST")])
            return
        laenge = _kopf(scope, b"content-length")
        if laenge is not None and (not laenge.isdigit() or int(laenge) > MAX_KOERPER):
            await self._antwort(send, 413, "zu_gross")
            return
        if methode in SCHREIBEND and not self._herkunft_passt(scope):
            await self._antwort(send, 403, "herkunft")
            return

        # Körper vorab lesen (höchstens MAX_KOERPER) und der App wieder vorspielen -- auch ohne Content-Length (chunked)
        teile, groesse = [], 0
        while True:
            nachricht = await receive()
            if nachricht["type"] == "http.disconnect":
                return
            teile.append(nachricht.get("body", b""))
            groesse += len(teile[-1])
            if groesse > MAX_KOERPER:
                await self._antwort(send, 413, "zu_gross")
                return
            if not nachricht.get("more_body", False):
                break
        koerper = b"".join(teile)
        gelesen = False

        async def wieder_vorspielen():
            nonlocal gelesen
            if not gelesen:
                gelesen = True
                return {"type": "http.request", "body": koerper, "more_body": False}
            return await receive()

        begonnen = False
        design = ist_design_pfad(scope)

        async def mit_kopfzeilen(nachricht):
            nonlocal begonnen
            if nachricht["type"] == "http.response.start":
                begonnen = True
                kopf = [(k, v) for k, v in nachricht.get("headers", []) if k.lower() not in {name for name, _ in self._kopf}]
                if design:  # seit 1.11.14: Design-Dateien wie im ERP -- 200 ein Jahr, sonst no-store
                    kopf = [(k, v) for k, v in kopf if k.lower() != b"cache-control"]
                    kopf.append((b"cache-control", DAUERHAFT.encode() if nachricht.get("status") == 200 else b"no-store"))
                if not any(k.lower() == b"cache-control" for k, _ in kopf):
                    kopf.append((b"cache-control", b"no-store"))
                nachricht = {**nachricht, "headers": kopf + self._kopf}
            await send(nachricht)

        try:
            await self.app(scope, wieder_vorspielen, mit_kopfzeilen)
        except Exception as exc:  # noqa: BLE001 -- Starlette reicht eine Ausnahme nach ihrer 500 weiter; uvicorn schriebe sonst ihren Text ins Journal
            logger.error("Ausnahme im Portal: %s", type(exc).__name__)
            if not begonnen:
                await self._antwort(send, 500, "technisch")
