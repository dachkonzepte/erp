"""Anmeldeschranke: Identität, Anmeldepflicht, zweiter Faktor und Cache-Verbot für jede Anfrage (seit 1.8.98 aus app/main.py hierher).

app/main.py bindet middleware(SessionLocal) als HTTP-Middleware ein; Tests binden dieselbe Funktion mit ihrer eigenen Sitzungsfabrik
ein, statt sie nachzubauen (bis 1.8.97 hatten vier Testdateien je eine Nachbildung, die vom Original abweichen konnte).

Seit 1.8.98:
- Die Identität kommt aus einer Sitzung auf dem Server (app/sitzungen.py), der zweite Faktor aus derselben Sitzung.
- Jede Antwort an eine angemeldete Sitzung trägt "Cache-Control: no-store", auch PDFs und Dateien (eine eigene Angabe des Endpunkts
  wird ersetzt), ebenso eine Antwort, die eine Sitzung setzt (Anmeldung). Ohne das zeigte "Zurück" nach dem Abmelden die Seite samt
  Daten aus dem Back-Forward- oder dem HTTP-Cache -- auf dem Fahrzeug-Tablet mit mehreren Monteuren.

Seit 1.8.104 (Vorgabe vom 14.10.2026, Punkte 3 und 4):
- Eine schreibende Anfrage (POST, PUT, PATCH, DELETE) geht nur durch, wenn sie von einer Seite des ERP selbst kommt (ursprung_passt()):
  sonst 403, bevor irgendetwas anderes geschieht -- auch von einer Unterdomain derselben Site (dort schickt der Browser das
  SameSite=Lax-Cookie mit), auch beim Anmelden.
- Jede Antwort verbietet das Einrahmen (X-Frame-Options: DENY, Content-Security-Policy frame-ancestors 'none'), auch die Anmeldeseite
  und ausgelieferte Dateien.

Seit 1.8.107 (zweite Vorgabe vom 14.10.2026, Punkt 2): HSTS an jeder Antwort, wo das Cookie Secure ist (Produktion), und die
Schutzkopfzeilen auch an der 500 aus dem Fehler-Handler (serverfehler()); app/main.py und die Tests binden beides über einbinden() ein.

Seit 1.8.114 (Vorgabe vom 16.10.2026, Punkt 1):
- Die Schranke liest nicht mehr auf der Event-Loop (_lesen() im Threadpool). Bis 1.8.113 holte sie ihre Verbindung direkt in der
  async-Middleware: war der Pool leer, wartete die Event-Loop des ganzen Arbeitsprozesses bis zu 30 s darauf -- keine Antwort, kein
  laufender Download, nichts ging weiter.
- Für eine Seitenanfrage lädt sie in derselben Sitzung die Seitendaten mit (app/seitendaten.py): Akzentfarbe, Module, Logo, Konto --
  die Jinja-Globals lesen sie aus request.state. Eine Seite braucht so eine Verbindung statt bis zu 41 (gemessen: 37 je Seite mit
  Seitenleiste).
- Wartet sie länger als das Zeitlimit des Pools (app/database.py) auf eine Verbindung, antwortet sie 503 (ueberlastet()), ebenso jeder
  Endpunkt (Fehler-Handler, einbinden()) -- statt einer 500 ohne Hinweis.

Seit 1.8.127 (Stufe 1 des Redesigns): Design-Dateien unter /static/ gehen ohne Anmeldung und ohne Datenbank durch, wenn
app/design_dateien.py::ist_design_pfad() die Anfrage annimmt (eng gefasst, kein Präfixvergleich); eine Antwort 200 trägt dann
"Cache-Control: public, max-age=31536000, immutable" statt des Cache-Verbots, die Schutzkopfzeilen wie jede Antwort.

Seit 1.8.128 (Runde 1b): die Anmeldepflicht gilt für jede Methode -- bis 1.8.127 nur für GET und POST/PUT/PATCH/DELETE, HEAD, OPTIONS,
TRACE und erfundene Methoden kamen ohne Anmeldung bis zum Routing. Ohne Anmeldung durch gehen nur OEFFENTLICH (Pfad mit Methoden) und
die Design-Dateien (GET, HEAD).

Die Entscheidungsregeln (_request_requires_login(), _page_requires_login(), _blocked_pending_two_factor()) werden von app/main.py weiter
angeboten (ältere Tests importieren sie dort)."""

from __future__ import annotations

import html
import logging
from urllib.parse import quote, urlsplit

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from sqlalchemy.exc import TimeoutError as PoolLeer
from starlette.concurrency import run_in_threadpool

from . import design_dateien, seitendaten, sitzungen
from .audit import reset_audit_context, set_audit_context
from .auth import COOKIE_NAME, NUR_HTTPS, users_exist
from .mobile_manifest import ICON_SIZES
from .version import APP_VERSION

logger = logging.getLogger(__name__)

CACHE_VERBOT = "no-store"


LESEND = frozenset({"GET", "HEAD"})

# Bleiben ohne Anmeldung erreichbar, obwohl sie keine /api/-Endpunkte sind: /login naturgemäß
# (sonst könnte sich niemand anmelden), /health für externe Überwachung (bereits zuvor
# ungated), /manifest.json als reine PWA-Ressource der Monteursansicht (wird ohnehin nur von
# der bereits angemeldeten Seite /mobil aus verlinkt, siehe app/routers/field_view.py).
# Seit 1.8.128 nur mit GET und HEAD.
_PUBLIC_PAGE_PATHS = {"/login", "/health", "/manifest.json"}

# Seit 1.8.128: die öffentlichen Pfade mit ihren Methoden -- ohne Anmeldung geht sonst nichts durch. Die Anmelde-Endpunkte einzeln statt
# "alles unter /api/auth/" (bis 1.8.127, auch jede Methode); Anmelden und Abmelden sind POST (Ursprung geprüft wie jedes Schreiben).
# Die Design-Dateien (GET, HEAD) prüft app/design_dateien.py::ist_design_pfad() vorweg in der Middleware.
OEFFENTLICH: dict[str, frozenset] = {
    **{pfad: LESEND for pfad in _PUBLIC_PAGE_PATHS},
    "/api/auth/status": LESEND,
    "/api/auth/login": frozenset({"POST"}),
    "/api/auth/logout": frozenset({"POST"}),
    # Seit 1.8.130: die PWA-Symbole des Manifests öffentlich wie /manifest.json (nur die Größen, die es gibt)
    **{f"/api/mobile-icon/{groesse}.png": LESEND for groesse in ICON_SIZES},
}


def _oeffentlich(method: str, path: str) -> bool:
    return method in OEFFENTLICH.get(path, ())


def _request_requires_login(has_users: bool, method: str, path: str) -> bool:
    """Ermittelt, ob diese Anfrage ohne angemeldeten ERP-Benutzer mit 401 abgewiesen wird (Seiten mit GET/HEAD leitet
    _page_requires_login() stattdessen auf /login um).

    Greift erst, sobald mindestens ein ERP-Benutzer existiert (der Bootstrap-Fall
    zum Anlegen des allerersten Admin-Kontos bleibt ausgenommen). Schreibende
    Zugriffe waren bereits zuvor geschützt; seit 1.0.6 zusätzlich lesende API-
    Zugriffe (GET /api/...), da darüber z. B. Mitarbeiterlöhne
    (EmployeeOut.effective_hourly_wage / .annual_gross_wage) und
    Kalkulationsgrundlagen ohne Anmeldung auslesbar waren.

    Seit 1.8.128 für jede Methode: bis 1.8.127 kamen HEAD, OPTIONS, TRACE und jede erfundene Methode ohne Anmeldung bis zum Routing --
    die Doku-Routen von FastAPI (/openapi.json, /docs, /redoc, /docs/oauth2-redirect) beantworteten HEAD mit 200 und berechneten dafür
    die ganze Schnittstellenbeschreibung. Jetzt: eine API-Anfrage ist mit jeder Methode 401, eine Seite mit GET/HEAD wird umgeleitet, mit
    jeder anderen Methode 401 (wie POST); ausgenommen nur OEFFENTLICH mit den dort genannten Methoden.

    Seit 1.8.130 ohne Ausnahme für die Ersteinrichtung: ohne Konto antwortet die Middleware vorher selbst (ersteinrichtung_antwort(),
    503); has_users bleibt nur für ältere Aufrufer in der Unterschrift und ändert nichts mehr.
    """
    if _oeffentlich(method, path):
        return False
    if path.startswith("/api/"):
        return True
    return method not in LESEND


def _page_requires_login(has_users: bool, method: str, path: str) -> bool:
    """Seit 1.3.47: ohne Anmeldung führte jede Seite bisher zu einem stillen Rendern des
    Seiten-Gerüsts (kein Redirect, kein Fehler) -- ob überhaupt etwas nutzbar ist, entschied
    rein die clientseitige JS jeder Seite. Diese Funktion entscheidet stattdessen serverseitig,
    ob eine HTML-Seitenanfrage ohne angemeldeten Benutzer auf /login umgeleitet wird.

    Bewusst getrennt von _request_requires_login() oben, nicht darin verschmolzen: eine
    /api/-Anfrage soll bei fehlender Anmeldung weiterhin die dortige 401-JSON-Antwort bekommen,
    nie einen Redirect auf eine HTML-Seite -- ein API-Client würde eine Login-Seite als Antwort
    nicht sinnvoll verarbeiten können. Bewusst nur GET: Seiten kennen ohnehin kein POST/PUT/....
    Seit 1.8.128 GET und HEAD (HEAD kam bis dahin ohne Anmeldung durch); jede andere Methode weist _request_requires_login() mit 401 ab.
    Seit 1.8.130 ohne Ausnahme für die Ersteinrichtung (siehe _request_requires_login()).
    """
    if method not in LESEND or path.startswith("/api/"):
        return False
    return path not in _PUBLIC_PAGE_PATHS


# Seit 1.8.130 (Runde 1d): ohne Konto bleibt die App geschlossen. Bis dahin ließ die Schranke ohne Konto alles durch, und jeder, der den
# Server erreichte, legte über POST /api/users das erste Konto als Admin an. Jetzt entsteht es nur per Befehl auf dem Server
# (scripts/erstes_konto.py, Passwort verdeckt abgefragt); bis dahin gehen nur /health (GET, HEAD) und die Design-Dateien durch, eine
# Seite (GET oder HEAD außerhalb von /api/) zeigt den Hinweis mit dem Befehl, alles andere bekommt 503.
ERSTEINRICHTUNG_BEFEHL = "python scripts/erstes_konto.py <benutzername>"
ERSTEINRICHTUNG_TEXT = ("Ersteinrichtung: es gibt noch kein Benutzerkonto. Das erste Administrator-Konto legt der Betreiber auf dem Server "
                        f"an (im Projektordner, mit geladener .env und der virtuellen Umgebung des ERP): {ERSTEINRICHTUNG_BEFEHL}")


def _ersteinrichtung_seite() -> HTMLResponse:
    seite = f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DACHKONZEPTE ERP – Ersteinrichtung</title>
<script>(function(){{try{{if(window.matchMedia('(prefers-color-scheme: dark)').matches)document.documentElement.setAttribute('data-theme','dark')}}catch(e){{}}}})();</script>
<link rel="stylesheet" href="/static/ds/ds.css?v={APP_VERSION}">
<style>body{{box-sizing:border-box;margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--ds-grund);color:var(--ds-text);font-family:var(--ds-schrift-text);padding:var(--ds-abstand-4)}}
main{{max-width:620px;background:var(--ds-flaeche);border:1px solid var(--ds-linie);border-radius:var(--ds-ecke-karte);padding:var(--ds-abstand-6)}}
h1{{font-family:var(--ds-schrift-titel);font-size:var(--ds-groesse-7);margin:0 0 var(--ds-abstand-3)}}p{{color:var(--ds-text-2);line-height:1.5}}
pre{{font-family:var(--ds-schrift-mono);background:var(--ds-flaeche-2);border:1px solid var(--ds-linie);padding:var(--ds-abstand-3);white-space:pre-wrap}}</style>
</head><body><main><h1>Ersteinrichtung</h1>
<p>Es gibt noch kein Benutzerkonto. Bis zum ersten Administrator-Konto bleibt das ERP geschlossen.</p>
<p>Das erste Konto legt der Betreiber auf dem Server an – im Projektordner, mit geladener <code>.env</code> und der virtuellen Umgebung
des ERP. Das Passwort fragt der Befehl verdeckt ab:</p>
<pre>{html.escape(ERSTEINRICHTUNG_BEFEHL)}</pre>
<p>Danach diese Seite neu laden und anmelden; beim ersten Anmelden richtet das Konto den zweiten Faktor ein.</p></main></body></html>"""
    return HTMLResponse(seite, status_code=503)


def ersteinrichtung_antwort(method: str, path: str):
    """Die Antwort, solange es kein Konto gibt -- None nur für /health mit GET oder HEAD (die Design-Dateien gehen vorher durch)."""
    if path == "/health" and method in LESEND:
        return None
    if method in LESEND and not path.startswith("/api/"):
        antwort = _ersteinrichtung_seite()
    else:
        antwort = JSONResponse(status_code=503, content={"detail": ERSTEINRICHTUNG_TEXT, "ersteinrichtung": True})
    antwort.headers["Cache-Control"] = CACHE_VERBOT
    return antwort


# Diese Endpunkte bleiben für einen Administrator erreichbar, dessen Sitzung das Passwort
# bereits bestätigt hat, aber noch keinen zweiten Faktor -- alles andere unter /api/ ist
# solange blockiert (seit 1.3.34, siehe CLAUDE.md "Zwei-Faktor-Authentifizierung für
# Administratoren"). /api/auth/* ist bereits über _request_requires_login() immer erreichbar,
# taucht hier nicht zusätzlich auf.
_TWO_FACTOR_SETUP_PATHS = {
    "/api/account/2fa/setup/start",
    "/api/account/2fa/setup/confirm",
    "/api/account/2fa/verify",
}


def _blocked_pending_two_factor(path: str) -> bool:
    if not path.startswith("/api/") or path.startswith("/api/auth/"):
        return False
    return path not in _TWO_FACTOR_SETUP_PATHS


def _setzt_sitzung(response) -> bool:
    """Ob die Antwort das Anmelde-Cookie setzt oder löscht (Anmeldung, Abmeldung)."""
    return any(name == b"set-cookie" and value.startswith(COOKIE_NAME.encode() + b"=") for name, value in response.raw_headers)


SCHREIBEND = frozenset({"POST", "PUT", "PATCH", "DELETE"})
FREMDER_URSPRUNG = "Anfrage von einer fremden Seite abgelehnt."


def ursprung_passt(request: Request) -> bool:
    """Seit 1.8.104: ob eine schreibende Anfrage von einer Seite des ERP selbst kommt (lesende immer ja).

    Zuerst Sec-Fetch-Site: der Browser setzt sie selbst, eine Seite kann sie nicht fälschen -- nur "same-origin" gilt ("same-site" ist
    eine Unterdomain derselben Site, "cross-site" eine fremde, "none" eine Eingabe in der Adresszeile). Sie hängt nicht davon ab, welchen
    Host der Reverse-Proxy weitergibt. Ohne sie (ältere Browser): Origin muss http(s) sein und Host samt Port der Kopfzeile Host der
    Anfrage entsprechen. Fehlt beides oder ist Origin "null" (Sandbox, Datei, Umleitung), ist die Anfrage abgelehnt -- ein Programm ohne
    Browser schickt sie mit, wenn es schreiben soll."""
    if request.method.upper() not in SCHREIBEND:
        return True
    site = request.headers.get("sec-fetch-site")
    if site is not None:
        return site.strip().lower() == "same-origin"
    origin = (request.headers.get("origin") or "").strip()
    if not origin or origin.lower() == "null":
        return False
    try:
        teile = urlsplit(origin)
    except ValueError:
        return False
    host = (request.headers.get("host") or "").strip().lower()
    return (teile.scheme in ("http", "https") and bool(teile.netloc) and not teile.path and not teile.query
            and teile.netloc.lower() == host)


# Seit 1.8.107 (Vorgabe Punkt 2): HSTS überall, wo das Cookie Secure ist (app/auth.py::NUR_HTTPS -- Produktion, auch mit fehlender
# ERP_ENV; nicht lokal und nicht in Tests). Ein Jahr, ohne includeSubDomains (andere Dienste unter derselben Domain bleiben, wie sie
# sind) und ohne preload. Ein Browser beachtet die Kopfzeile nur über HTTPS; danach nimmt er für app.dachkonzepte.gmbh nie mehr http.
HSTS = "max-age=31536000" if NUR_HTTPS else None


def _schutzkoepfe(response):
    """Seit 1.8.104: kein Einrahmen -- X-Frame-Options für ältere Browser, frame-ancestors für neuere; eine Content-Security-Policy
    des Endpunkts (Dateien: sandbox) bekommt frame-ancestors angehängt, statt ersetzt zu werden. Seit 1.8.107 dazu HSTS (oben)."""
    response.headers["X-Frame-Options"] = "DENY"
    csp = response.headers.get("content-security-policy")
    if not csp:
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
    elif "frame-ancestors" not in csp:
        response.headers["Content-Security-Policy"] = csp.rstrip("; ") + "; frame-ancestors 'none'"
    if HSTS:
        response.headers["Strict-Transport-Security"] = HSTS
    return response


async def serverfehler(request: Request, exc: Exception):
    """Seit 1.8.107 (Vorgabe Punkt 2): die Antwort auf einen unbehandelten Fehler. Starlette schickt sie aus seinem äußersten Fehler-Handler
    (ServerErrorMiddleware) -- an der Schranke vorbei, bis 1.8.106 deshalb ohne Schutzkopfzeilen und ohne Cache-Verbot (Nebenbefund 1.8.104
    Nr. 2). Inhalt wie bisher nur "Internal Server Error", nichts aus dem Fehler (Regel 18); protokolliert hat ihn die Schranke schon
    (_weiter()), danach gibt Starlette ihn an den Server weiter."""
    antwort = PlainTextResponse("Internal Server Error", status_code=500)
    antwort.headers["Cache-Control"] = CACHE_VERBOT
    return _schutzkoepfe(antwort)


UEBERLASTET = "Der Server ist gerade ausgelastet – bitte in einigen Sekunden noch einmal versuchen."


def _ueberlastet_antwort():
    antwort = JSONResponse(status_code=503, headers={"Retry-After": "5"}, content={"detail": UEBERLASTET})
    antwort.headers["Cache-Control"] = CACHE_VERBOT
    return _schutzkoepfe(antwort)


async def ueberlastet(request: Request, exc: Exception):
    """Seit 1.8.114: ein Endpunkt hat im Zeitlimit des Pools (app/database.py) keine Verbindung bekommen -- 503 mit Retry-After statt
    einer 500. Nur Metadaten im Protokoll (Regel 18)."""
    logger.warning("Keine Datenbankverbindung im Zeitlimit des Pools: %s %s", request.method, request.url.path)
    return _ueberlastet_antwort()


def einbinden(app, session_factory):
    """Seit 1.8.107: Schranke (Middleware) und Fehler-Handler an app -- app/main.py und tests/anmeldung.py binden über diese eine Funktion
    ein. Gibt die Middleware-Funktion zurück. Seit 1.8.114 dazu der Handler für einen leeren Pool (503)."""
    funktion = middleware(session_factory)
    app.middleware("http")(funktion)
    app.add_exception_handler(PoolLeer, ueberlastet)
    app.add_exception_handler(Exception, serverfehler)
    return funktion


ANMELDUNG_ABGELAUFEN = ("Anmeldung abgelaufen – bitte in einem neuen Tab anmelden und danach hier erneut speichern. "
                        "Die Eingaben auf dieser Seite bleiben stehen.")
ABGELAUFEN_KOPF = "X-DK-Anmeldung"


def _seite_erwartet(request: Request, has_users: bool, user) -> bool:
    """Ob die Anfrage eine Seite zeichnet (Vorlage mit Seitenleiste, Kopfzeile oder Akzentfarbe): seit 1.8.120 (Korrektur 114-5) nur eine
    Seitenroute, die für diesen Benutzer nicht umleitet (app/seitendaten.py::wird_gezeichnet()) -- nicht /health, /manifest.json, /docs,
    Dateien, unbekannte Adressen; nicht die Umleitung eines Abgemeldeten auf /login. Bis 1.8.119 jede GET-Anfrage außerhalb von /api/."""
    if user is None and _page_requires_login(has_users, request.method, request.url.path):
        return False
    return seitendaten.wird_gezeichnet(request, user)


def _lesen(session_factory, request: Request) -> dict:
    """Seit 1.8.114 im Threadpool, nie auf der Event-Loop: Benutzer, Sitzung und für eine Seite die Seitendaten -- in einer Sitzung,
    also mit einer Verbindung."""
    stand = {"user": None, "sitzung_id": None, "otp_ok": True, "has_users": False, "seite": None}
    db = session_factory()
    try:
        stand["has_users"] = users_exist(db)
        user, sitzung = sitzungen.anmeldung(db, request)
        if user is not None:
            stand["user"], stand["sitzung_id"] = user, sitzung.id
            if user.role == "admin":
                stand["otp_ok"] = sitzung.second_factor_at is not None
        if _seite_erwartet(request, stand["has_users"], user):
            stand["seite"] = seitendaten.laden(db, user)
    finally:
        db.close()
    return stand


def middleware(session_factory):
    """Die Middleware-Funktion (request, call_next) mit session_factory für die eigene, kurzlebige Datenbanksitzung."""

    async def identitaet_und_audit(request: Request, call_next):
        if design_dateien.ist_design_pfad(request.scope):
            # Seit 1.8.127: Design-Dateien (app/design_dateien.py) ohne Anmeldung und ohne Datenbank -- nur GET/HEAD auf einen eng
            # gefassten Pfad unter /static/. Eine Antwort 200 darf der Browser ein Jahr behalten (die einzige Ausnahme vom
            # Cache-Verbot), jede andere nicht.
            response = await call_next(request)
            response.headers["Cache-Control"] = design_dateien.DAUERHAFT if response.status_code == 200 else CACHE_VERBOT
            return _schutzkoepfe(response)
        if not ursprung_passt(request):
            # Nur Metadaten (Regel 18): Methode, Pfad und die beiden Kopfzeilen, kein Inhalt.
            logger.warning("Schreibende Anfrage von fremdem Ursprung abgelehnt: %s %s (Sec-Fetch-Site=%r, Origin=%r)", request.method,
                           request.url.path, request.headers.get("sec-fetch-site"), request.headers.get("origin"))
            return _schutzkoepfe(JSONResponse(status_code=403, content={"detail": FREMDER_URSPRUNG}))
        try:
            stand = await run_in_threadpool(_lesen, session_factory, request)
        except PoolLeer:
            logger.warning("Anmeldeschranke: keine Datenbankverbindung im Zeitlimit des Pools: %s %s", request.method, request.url.path)
            return _ueberlastet_antwort()
        user, sitzung_id, otp_ok, has_users = stand["user"], stand["sitzung_id"], stand["otp_ok"], stand["has_users"]
        if not has_users:
            # Seit 1.8.130: ohne Konto geschlossen (ersteinrichtung_antwort()) -- nur /health geht weiter
            antwort = ersteinrichtung_antwort(request.method, request.url.path)
            if antwort is not None:
                return _schutzkoepfe(antwort)
        tokens = set_audit_context(user=user, request=request)
        request.state.erp_user = user
        request.state.erp_sitzung_id = sitzung_id
        request.state.otp_ok = otp_ok
        if stand["seite"] is not None:
            setattr(request.state, seitendaten.ZUSTAND, stand["seite"])
        try:
            response = await _weiter(request, call_next, user, has_users, otp_ok)
            if user is not None or _setzt_sitzung(response):
                response.headers["Cache-Control"] = CACHE_VERBOT
            return _schutzkoepfe(response)
        finally:
            reset_audit_context(tokens)

    return identitaet_und_audit


async def _weiter(request: Request, call_next, user, has_users: bool, otp_ok: bool):
    # Sobald ERP-Benutzer eingerichtet sind, sind schreibende Vorgänge und lesende
    # API-Zugriffe nur angemeldet erlaubt (siehe _request_requires_login).
    if user is None and _request_requires_login(has_users, request.method, request.url.path):
        if request.cookies.get(COOKIE_NAME):
            # Seit 1.8.103: ein Anmelde-Cookie ohne gültige Sitzung (abgelaufen, abgemeldet, beendet) -- die Seite sagt das so und
            # lässt die Eingaben stehen (_speichern.html); nach dem Anmelden in einem neuen Tab geht derselbe Klick wieder.
            return JSONResponse(status_code=401, headers={ABGELAUFEN_KOPF: "abgelaufen"},
                                content={"detail": ANMELDUNG_ABGELAUFEN, "anmeldung_abgelaufen": True})
        return JSONResponse(status_code=401, content={"detail": "Bitte zuerst als ERP-Benutzer anmelden."})
    if user is None and _page_requires_login(has_users, request.method, request.url.path):
        # Dieselbe ?next=<Pfad>-Konvention wie bei den bestehenden Abmelden-Links
        # (_sidebar.html/_topbar.html/_mobile_header.html/vor_ort.html: location.href=
        # '/login?next='+encodeURIComponent(location.pathname)) -- login.html liest und
        # honoriert next bereits (siehe dort), nur der Query-String selbst wird bewusst
        # nicht mitgegeben, exakt wie bei jenen Links.
        next_target = quote(request.url.path, safe="")
        return RedirectResponse(url=f"/login?next={next_target}", status_code=302)
    if user is not None and not otp_ok and _blocked_pending_two_factor(request.url.path):
        return JSONResponse(status_code=401, content={"detail": "Zwei-Faktor-Bestätigung ausstehend.", "two_factor_pending": True})
    try:
        return await call_next(request)
    except Exception:
        # Nur protokollieren, nicht abfangen: dieselbe Exception wird
        # unverändert weitergereicht, sodass sich am Antwortverhalten
        # nichts ändert -- neu ist ausschließlich der Log-Eintrag mit
        # vollständigem Traceback (seit 1.0.8 dauerhaft in data/erp.log
        # statt nur in der Konsole).
        logger.exception("Unbehandelter Fehler bei %s %s", request.method, request.url.path)
        raise
