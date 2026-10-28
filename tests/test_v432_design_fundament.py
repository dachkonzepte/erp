"""Version 1.8.127 -- Stufe 1 des Redesigns: Fundament (app/static/ unter /static/, app/static/ds/ds.css, _ds_kopf.html).

    Auslieferung    /static/ ohne Anmeldung und ohne Datenbank, nur GET und HEAD, kein Listing, keine Symlinks, Typ fest nach Endung,
                    200 mit "Cache-Control: public, max-age=31536000, immutable" (auch angemeldet -- die Ausnahme von Regel 30)
    Angriffe        ohne Anmeldung: .., %2e%2e, %2f, doppelt kodiert, Rückstrich, /staticx, /static ohne Schrägstrich, POST, fehlende
                    Datei -- keiner liefert etwas außer Design-Dateien oder kommt an der Anmeldung vorbei. Direkt über ASGI (path und raw_path
                    wie uvicorn sie bildet; der TestClient normalisiert "/static/../x" vorher und dekodiert %252e doppelt) und gegen einen
                    echten uvicorn (h11 und httptools) mit rohen Anfragezeilen. Gegenprobe: ein reiner Präfixvergleich wird rot.
    Wächter         ds.css nur --ds-* in :root und :root[data-theme="dark"], @font-face und Selektoren mit .ds-; in app/static/ nur .css,
                    .woff2 und Lizenztexte; jede Seite aus seiten() bindet _ds_kopf.html im Kopf vor ihrem eigenen Stilblock ein;
                    StaticFiles nur in app/design_dateien.py; app/main.py bindet /static ein
    Kontrast        die Prüfpaare aus dem Kopfkommentar von ds.css, hell und dunkel (WCAG 2.x)
"""

from __future__ import annotations

import ast
import asyncio
import http.client
import os
import re
import socket
import sys
import threading
import time
from pathlib import Path
from urllib.parse import unquote

import pytest

from app import design_dateien
from app.auth import COOKIE_NAME
from app.design_dateien import DAUERHAFT, STATIC_DIR, TYPEN, ist_design_pfad
from tests import vorlagen_js as vj
from tests.anmeldung import EIGENE_SEITE, app_mit_schranke, neue_datenbank

ROOT = Path(__file__).resolve().parent.parent
DS_CSS = STATIC_DIR / "ds" / "ds.css"
GEHEIM = "GEHEIM-KUNDE-4711"


# ---------------------------------------------------------------------------
# Anfragen wie uvicorn: path dekodiert, raw_path wie gesendet
# ---------------------------------------------------------------------------

def asgi(app, methode: str, roh: bytes, kopf: dict | None = None, body: bytes = b"") -> tuple[int, dict, bytes]:
    """Eine Anfrage direkt an die ASGI-App, mit path und raw_path so, wie uvicorn sie bildet (unquote() des Pfads, raw_path die Bytes
    bis zum Fragezeichen) -- ohne die Normalisierung des TestClient."""
    roh_pfad, _, abfrage = roh.partition(b"?")
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": methode, "scheme": "http",
             "path": unquote(roh_pfad.decode("ascii")), "raw_path": roh_pfad, "query_string": abfrage, "root_path": "",
             "headers": [(b"host", b"testserver")] + [(k.lower().encode(), v.encode()) for k, v in (kopf or {}).items()],
             "server": ("testserver", 80), "client": ("127.0.0.1", 50000)}
    eingang = [{"type": "http.request", "body": body, "more_body": False}]
    antwort = {"status": None, "kopf": {}, "body": b""}

    async def receive():
        return eingang.pop(0) if eingang else {"type": "http.disconnect"}

    async def send(nachricht):
        if nachricht["type"] == "http.response.start":
            antwort["status"] = nachricht["status"]
            antwort["kopf"] = {k.decode().lower(): v.decode() for k, v in nachricht.get("headers", [])}
        elif nachricht["type"] == "http.response.body":
            antwort["body"] += nachricht.get("body", b"")

    asyncio.run(app(scope, receive, send))
    return antwort["status"], antwort["kopf"], antwort["body"]


@pytest.fixture(scope="module")
def welt():
    """Echte Schranke (tests/anmeldung.py) mit Seiten- und Kunden-Router und /static wie app/main.py; ein Konto (die Schranke greift
    erst mit Konten) und ein Kunde mit Erkennungsname. zaehler zählt die Datenbanksitzungen."""
    from app.models import AppUser, Customer
    from app.routers import customers, pages
    from app.sitzungen import neue_sitzung

    engine, make_session = neue_datenbank()
    zaehler = {"n": 0}

    def gezaehlt():
        zaehler["n"] += 1
        return make_session()

    with make_session() as db:
        nutzer = AppUser(username="bea", display_name="Bea", role="buero_finanzen", password_hash="x")
        db.add_all([nutzer, Customer(name=GEHEIM, last_name=GEHEIM)])
        db.commit()
        cookie = neue_sitzung(db, nutzer, zweiter_faktor=True)
        db.commit()
    app = app_mit_schranke(gezaehlt, pages.router, customers.router)
    design_dateien.einbinden(app)
    yield {"app": app, "zaehler": zaehler, "cookie": f"{COOKIE_NAME}={cookie}"}
    engine.dispose()


# ---------------------------------------------------------------------------
# Auslieferung
# ---------------------------------------------------------------------------

def _datei(rel: str) -> bytes:
    return (STATIC_DIR / rel).read_bytes()


@pytest.mark.parametrize("rel", ["ds/ds.css", "ds/schriften/archivo-latin-500-normal.woff2", "ds/schriften/ofl-archivo.txt"])
def test_design_datei_ohne_anmeldung(welt, rel):
    vorher = welt["zaehler"]["n"]
    status, kopf, body = asgi(welt["app"], "GET", f"/static/{rel}".encode())
    assert status == 200 and body == _datei(rel)
    assert kopf["content-type"] == TYPEN[Path(rel).suffix]
    assert kopf["cache-control"] == DAUERHAFT == "public, max-age=31536000, immutable"
    assert kopf["x-content-type-options"] == "nosniff" and kopf["x-frame-options"] == "DENY"
    assert welt["zaehler"]["n"] == vorher, "eine Design-Datei braucht keine Datenbank"


def test_angemeldet_ebenso_dauerhaft_und_ohne_datenbank(welt):
    """Die Ausnahme von Regel 30: auch an eine angemeldete Sitzung geht eine Design-Datei mit langem Cache, nicht mit no-store."""
    vorher = welt["zaehler"]["n"]
    status, kopf, body = asgi(welt["app"], "GET", b"/static/ds/ds.css?v=1.8.127", {"cookie": welt["cookie"]})
    assert status == 200 and kopf["cache-control"] == DAUERHAFT and body == _datei("ds/ds.css")
    assert welt["zaehler"]["n"] == vorher
    # zum Vergleich: dieselbe Sitzung bekommt anderswo das Cache-Verbot
    status, kopf, _ = asgi(welt["app"], "GET", b"/api/customers", {"cookie": welt["cookie"]})
    assert status == 200 and kopf["cache-control"] == "no-store"


def test_head_ohne_inhalt(welt):
    status, kopf, body = asgi(welt["app"], "HEAD", b"/static/ds/ds.css")
    assert status == 200 and body == b"" and kopf["cache-control"] == DAUERHAFT
    assert int(kopf["content-length"]) == len(_datei("ds/ds.css"))


@pytest.mark.parametrize("roh", [b"/static/ds", b"/static/ds/schriften", b"/static/ds/fehlt.css", b"/static/ds/schriften/fehlt.woff2"])
def test_verzeichnis_und_fehlende_datei_404_ohne_listing(welt, roh):
    for kopfzeilen in ({}, {"cookie": welt["cookie"]}):
        status, kopf, body = asgi(welt["app"], "GET", roh, kopfzeilen)
        assert status == 404 and b"woff2" not in body and b"ds.css" not in body, (roh, status, body[:200])
        assert kopf["cache-control"] == "no-store"


def test_angemeldet_post_auf_design_datei_405(welt):
    status, _, body = asgi(welt["app"], "POST", b"/static/ds/ds.css", {"cookie": welt["cookie"], **EIGENE_SEITE})
    assert status == 405 and body != _datei("ds/ds.css")


def _symlink(ziel: Path, link: Path, verzeichnis: bool) -> bool:
    try:
        os.symlink(ziel, link, target_is_directory=verzeichnis)
        return True
    except (OSError, NotImplementedError):
        if verzeichnis and sys.platform == "win32":
            import _winapi
            _winapi.CreateJunction(str(ziel), str(link))  # Verzeichnisverbindung, ohne Sonderrechte
            return True
        return False


def test_keine_symlinks_und_nur_feste_typen(tmp_path):
    """Ein eigener Ordner: echte Datei 200; Symlink auf eine Datei im Ordner, Symlink (unter Windows Verbindung) auf ein Verzeichnis im
    Ordner und Dateien anderer Endung 404."""
    from app.models import AppUser

    wurzel = tmp_path / "static"
    (wurzel / "ds" / "teil").mkdir(parents=True)
    (wurzel / "ds" / "a.css").write_text(".ds-a{color:red}", encoding="utf-8")
    (wurzel / "ds" / "teil" / "b.css").write_text(".ds-b{color:red}", encoding="utf-8")
    (wurzel / "ds" / "x.html").write_text("<script>alert(1)</script>", encoding="utf-8")
    (wurzel / "ds" / "y.svg").write_text("<svg><script>alert(1)</script></svg>", encoding="utf-8")
    datei_link = _symlink(wurzel / "ds" / "a.css", wurzel / "ds" / "link.css", verzeichnis=False)
    assert _symlink(wurzel / "ds" / "teil", wurzel / "ds" / "verweis", verzeichnis=True)
    engine, make_session = neue_datenbank()
    with make_session() as db:
        db.add(AppUser(username="u", display_name="U", role="admin", password_hash="x"))
        db.commit()
    app = app_mit_schranke(make_session)
    design_dateien.einbinden(app, wurzel)
    assert asgi(app, "GET", b"/static/ds/a.css")[0] == 200
    assert asgi(app, "GET", b"/static/ds/teil/b.css")[0] == 200
    assert asgi(app, "GET", b"/static/ds/verweis/b.css")[0] == 404
    assert asgi(app, "GET", b"/static/ds/x.html")[0] == 404
    assert asgi(app, "GET", b"/static/ds/y.svg")[0] == 404
    if datei_link:
        assert asgi(app, "GET", b"/static/ds/link.css")[0] == 404
    engine.dispose()


# ---------------------------------------------------------------------------
# Angriffe ohne Anmeldung
# ---------------------------------------------------------------------------

# (rohe Anfrage, erwartet): "datei" = die Design-Datei selbst, "anmeldung" = die Schranke (302 auf /login bzw. 401), "404" = ein
# Design-Pfad ohne Datei, "abgelehnt" = 403 (fremder Ursprung)
ANGRIFFE = [
    (b"/static/ds/ds.css", "datei"),
    (b"/static/ds/ds.css?v=1.8.127", "datei"),
    (b"/static/ds/schriften/archivo-latin-500-normal.woff2", "datei"),
    (b"/static/ds/schriften/ofl-ibm-plex-sans.txt", "datei"),
    (b"/static/ds/fehlt.css", "404"),
    (b"/static/ds", "404"),
    (b"/static/../api/customers", "anmeldung"),
    (b"/static/ds/../../api/customers", "anmeldung"),
    (b"/static/../projects", "anmeldung"),
    (b"/static/%2e%2e/api/customers", "anmeldung"),
    (b"/static/%2E%2E/%2E%2E/app/main.py", "anmeldung"),
    (b"/static/..%2f..%2fapp%2fmain.py", "anmeldung"),
    (b"/static/ds%2fds.css", "anmeldung"),
    (b"/static%2fds%2fds.css", "anmeldung"),
    (b"/static/%252e%252e/%252e%252e/app/main.py", "anmeldung"),
    (b"/static/%252e%252e%252fapi%252fcustomers", "anmeldung"),
    (b"/static/..\\..\\app\\main.py", "anmeldung"),
    (b"/static\\..\\app\\main.py", "anmeldung"),
    (b"/static/ds\\ds.css", "anmeldung"),
    (b"/staticx/ds/ds.css", "anmeldung"),
    (b"/staticx", "anmeldung"),
    (b"/static", "anmeldung"),
    (b"/static/", "anmeldung"),
    (b"/static//ds/ds.css", "anmeldung"),
    (b"/static/./ds/ds.css", "anmeldung"),
    (b"/static/DS/DS.CSS", "anmeldung"),
    (b"/static/ds/ds.css.", "anmeldung"),
    (b"/static/ds/ds.css::$DATA", "anmeldung"),
    (b"/static/ds/schriften/OFL-Archivo.txt", "anmeldung"),
]
METHODEN = [(m, kopf, erwartet) for m in ("POST", "PUT", "PATCH", "DELETE")
            for kopf, erwartet in (({}, "abgelehnt"), (EIGENE_SEITE, "anmeldung"))]


def kategorie(status: int, kopf: dict, body: bytes, roh: bytes) -> str:
    """Was die Antwort ist -- und für 200 der Nachweis, dass es genau die Design-Datei des Pfads ist."""
    assert GEHEIM.encode() not in body, f"{roh!r}: geschützte Daten in der Antwort"
    if status == 200:
        pfad = unquote(roh.partition(b"?")[0].decode("ascii"))
        rel = pfad.removeprefix("/static/")
        datei = STATIC_DIR / rel
        echt = (pfad.startswith("/static/") and datei.is_file() and body == datei.read_bytes()
                and kopf.get("content-type") == TYPEN.get(datei.suffix) and kopf.get("cache-control") == DAUERHAFT)
        return "datei" if echt else f"200 fremd ({kopf.get('content-type')})"
    if status == 302 and kopf.get("location", "").startswith("/login?next="):
        return "anmeldung"
    if status == 401:
        return "anmeldung"
    if status == 403:
        return "abgelehnt"
    if status == 404:
        return "404"
    return str(status)


def _abweichungen(app, faelle) -> list:
    falsch = []
    for roh, erwartet in faelle:
        ist = kategorie(*asgi(app, "GET", roh), roh)
        if ist != erwartet:
            falsch.append((roh, erwartet, ist))
    return falsch


def test_angriffe_ohne_anmeldung(welt):
    assert _abweichungen(welt["app"], ANGRIFFE) == []


@pytest.mark.parametrize("methode,kopf,erwartet", METHODEN)
def test_schreibende_methoden_ohne_anmeldung(welt, methode, kopf, erwartet):
    status, antwort_kopf, body = asgi(welt["app"], methode, b"/static/ds/ds.css", kopf, body=b"x")
    assert kategorie(status, antwort_kopf, body, b"/static/ds/ds.css") == erwartet, status


def test_gegenprobe_reiner_praefixvergleich_wird_rot(welt, monkeypatch):
    """Mit einer naiven Ausnahme (path.startswith("/static")) kommen Anfragen an der Anmeldung vorbei -- die Tabelle oben wird rot."""
    monkeypatch.setattr(design_dateien, "ist_design_pfad",
                        lambda scope: scope.get("method") in ("GET", "HEAD") and (scope.get("path") or "").startswith("/static"))
    falsch = _abweichungen(welt["app"], ANGRIFFE)
    roh_falsch = {roh for roh, _, _ in falsch}
    assert {b"/staticx/ds/ds.css", b"/static", b"/static/../api/customers"} <= roh_falsch, falsch


@pytest.mark.parametrize("roh,erwartet", [
    (b"/static/ds/ds.css", True), (b"/static/ds/schriften/ibm-plex-mono-latin-ext-500-normal.woff2", True), (b"/static/ds", True),
    (b"/static", False), (b"/static/", False), (b"/staticx/a.css", False), (b"/static/../a.css", False), (b"/static/a..b.css", False),
    (b"/static/%2e%2e/a.css", False), (b"/static/ds%2fds.css", False), (b"/static/a\\b.css", False), (b"/static//a.css", False),
    (b"/static/.a.css", False), (b"/static/a.css.", False), (b"/static/A.css", False), (b"/static/a b.css", False),
])
def test_ist_design_pfad(roh, erwartet):
    scope = {"type": "http", "method": "GET", "path": unquote(roh.decode()), "raw_path": roh}
    assert ist_design_pfad(scope) is erwartet
    assert ist_design_pfad({**scope, "method": "POST"}) is False


# Gegen einen echten uvicorn: rohe Anfragezeilen (http.client normalisiert nichts), h11 und httptools -- 400 heißt, der Server selbst
# hat die Anfrage abgewiesen (auch das liefert nichts)

def _uvicorn(app, http_art: str):
    import uvicorn

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, http=http_art, log_level="warning", lifespan="off"))
    faden = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    faden.start()
    ende = time.monotonic() + 15
    while not server.started:
        assert time.monotonic() < ende, "uvicorn startet nicht"
        time.sleep(0.05)
    return server, faden, sock.getsockname()[1]


def _roh_anfrage(port: int, methode: str, roh: bytes) -> tuple[int, dict, bytes]:
    verbindung = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        verbindung.putrequest(methode, roh.decode("ascii"), skip_host=True, skip_accept_encoding=True)
        verbindung.putheader("Host", "testserver")
        verbindung.endheaders()
        antwort = verbindung.getresponse()
        return antwort.status, {k.lower(): v for k, v in antwort.getheaders()}, antwort.read()
    finally:
        verbindung.close()


@pytest.mark.parametrize("http_art", ["h11", "httptools"])
def test_angriffe_gegen_einen_echten_uvicorn(welt, http_art):
    pytest.importorskip(http_art)
    server, faden, port = _uvicorn(welt["app"], http_art)
    try:
        falsch = []
        for roh, erwartet in ANGRIFFE:
            ist = kategorie(*_roh_anfrage(port, "GET", roh), roh)
            if ist != erwartet and ist != "400":
                falsch.append((roh, erwartet, ist))
        assert falsch == []
    finally:
        server.should_exit = True
        faden.join(15)


# ---------------------------------------------------------------------------
# Wächter
# ---------------------------------------------------------------------------

FONT_FACE_EIGENSCHAFTEN = {"font-family", "font-style", "font-weight", "font-display", "src", "unicode-range"}
TOKEN_BLOECKE = (":root", ':root[data-theme="dark"]')


def css_regeln(text: str) -> tuple[list, str]:
    """[(Kopf, Rumpf)] der obersten Ebene ohne Kommentare, dazu, was übrig bleibt (muss leer sein)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    regeln, pos = [], 0
    kopf_re = re.compile(r"\s*([^{};]+?)\s*\{")
    while (m := kopf_re.match(text, pos)) is not None:
        tiefe, i = 1, m.end()
        while tiefe and i < len(text):
            tiefe += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        regeln.append((m.group(1).strip(), text[m.end():i - 1]))
        pos = i
    return regeln, text[pos:].strip()


def _deklarationen(rumpf: str) -> list[tuple[str, str]]:
    return [(d.split(":", 1)[0].strip(), d.split(":", 1)[1].strip() if ":" in d else "") for d in rumpf.split(";") if d.strip()]


def _oberste_ebene(text: str, trenner) -> list[str]:
    """Teilt text an Zeichen, für die trenner(c) wahr ist -- nur außerhalb von (), [] und Anführungszeichen."""
    teile, aktuell, tiefe, zeichen = [], "", 0, None
    for c in text:
        if zeichen:
            aktuell += c
            zeichen = None if c == zeichen else zeichen
        elif c in "\"'":
            zeichen = c
            aktuell += c
        elif c in "([" or c in ")]":
            tiefe += 1 if c in "([" else -1
            aktuell += c
        elif tiefe == 0 and trenner(c):
            teile.append(aktuell)
            aktuell = ""
        else:
            aktuell += c
    return [t.strip() for t in teile + [aktuell] if t.strip()]


def selektor_ziel(selektor: str) -> str:
    """Das Ziel eines Selektors: sein letzter zusammengesetzter Teil nach den Kombinatoren (Leerraum, >, +, ~)."""
    teile = _oberste_ebene(selektor, lambda c: c.isspace() or c in ">+~")
    return teile[-1] if teile else ""


def traegt_ds_klasse(teil: str) -> bool:
    """Ob ein zusammengesetzter Teil selbst eine Klasse .ds-… trägt -- was in (…) oder […] steht (:not(), :is(), :has(), Attribute),
    zählt nicht: div:not(.ds-x) ist ein div."""
    aussen, tiefe = "", 0
    for c in teil:
        tiefe += 1 if c in "([" else -1 if c in ")]" else 0
        if tiefe == 0 and c not in ")]":
            aussen += c
    return re.search(r"\.ds-[A-Za-z0-9_-]", aussen) is not None


def css_verstoesse(text: str) -> list[str]:
    regeln, rest = css_regeln(text)
    funde = [f"außerhalb einer Regel: {rest[:60]!r}"] if rest else []
    for kopf, rumpf in regeln:
        if kopf.startswith("@") and kopf != "@font-face":
            funde.append(f"At-Regel {kopf}")
        elif "{" in rumpf or "}" in rumpf:
            funde.append(f"{kopf}: verschachtelt")
        elif kopf == "@font-face":
            funde += [f"@font-face: {name}" for name, _ in _deklarationen(rumpf) if name not in FONT_FACE_EIGENSCHAFTEN]
        elif kopf in TOKEN_BLOECKE:
            funde += [f"{kopf}: {name}" for name, wert in _deklarationen(rumpf) if not re.fullmatch(r"--ds-[a-z0-9-]+", name) or not wert]
        else:
            # seit 1.8.129: das Ziel jedes Selektors trägt eine .ds-Klasse (bis dahin genügte .ds- irgendwo im Selektor --
            # ".ds-x div" hätte jedes div in einem .ds-x getroffen)
            for sel in _oberste_ebene(kopf, lambda c: c == ","):
                if ".ds-" not in sel:
                    funde.append(f"Selektor ohne .ds-: {sel}")
                elif not traegt_ds_klasse(selektor_ziel(sel)):
                    funde.append(f"Ziel ohne .ds-Klasse: {sel}")
    return funde


def test_ds_css_nur_tokens_schriften_und_ds_klassen():
    assert css_verstoesse(DS_CSS.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("css,fund", [
    ("body{margin:0}", "Selektor ohne .ds-"),
    (":root{color:red}", ":root: color"),
    (":root{--accent:#000}", ":root: --accent"),
    (":root{color-scheme:dark}", ":root: color-scheme"),
    (':root[data-theme="dark"]{--ds-a:#000;background:#000}', "background"),
    (".knopf{color:red}", "Selektor ohne .ds-"),
    (".ds-a, button{color:red}", "Selektor ohne .ds-"),
    ("@media (prefers-color-scheme: dark){:root{--ds-a:#000}}", "At-Regel"),
    ("@import url(x.css);", "außerhalb einer Regel"),
    ("@font-face{font-family:x;color:red}", "@font-face: color"),
    (":root:not([data-theme]){--ds-a:#000}", "Selektor ohne .ds-"),
])
def test_waechter_findet_fremde_regeln(css, fund):
    assert any(fund in f for f in css_verstoesse(css)), css_verstoesse(css)


def test_waechter_laesst_tokens_schriften_und_ds_klassen_durch():
    css = (':root{--ds-a:#fff}:root[data-theme="dark"]{--ds-a:#000}@font-face{font-family:"X";src:url("schriften/x.woff2")}'
           ".ds-knopf:hover, .ds-karte > .ds-titel{color:var(--ds-a)}")
    assert css_verstoesse(css) == []


# Seit 1.8.129 (Runde 1c, Punkt 4): das Ziel jedes Selektors -- sein letzter Teil -- trägt eine .ds-Klasse
@pytest.mark.parametrize("selektor", [
    ".ds-x div", ".ds-x + p", ".ds-x > span", ".ds-x ~ a", ".ds-x *", ".ds-a .ds-b div", ".ds-x div.andere", "div:not(.ds-x)",
    "div:has(.ds-x)", ":is(.ds-a, .ds-b) p", ".ds-a [class~=ds-b]", ".ds-a>p", ".ds-a+p", ".ds-x\tp", ".ds-ok, .ds-x li",
])
def test_waechter_ziel_ohne_ds_klasse(selektor):
    funde = css_verstoesse(f"{selektor}{{color:red}}")
    assert any(f.startswith("Ziel ohne .ds-Klasse") for f in funde), (selektor, funde)


@pytest.mark.parametrize("selektor", [
    ".ds-x .ds-y", ".ds-x > .ds-y:hover", "a.ds-link", "div.ds-x", ".ds-feld::placeholder", ".ds-a:not(.ds-b)", ".ds-a[data-x='a b']",
    ':is(.ds-a, .ds-b) .ds-c', ".ds-a + .ds-b", ".ds-a ~ .ds-b:focus-visible", '.ds-a[title="x > y"]',
])
def test_waechter_ziel_mit_ds_klasse(selektor):
    assert css_verstoesse(f"{selektor}{{color:red}}") == []


def test_selektor_ziel_und_klammern():
    assert selektor_ziel(".ds-a > .ds-b  span.c:hover") == "span.c:hover"
    assert selektor_ziel('.ds-a[data-x="a b"]') == '.ds-a[data-x="a b"]'
    assert selektor_ziel(":is(.ds-a .ds-b)") == ":is(.ds-a .ds-b)"
    assert traegt_ds_klasse(".ds-a:not(.x)") and not traegt_ds_klasse("div:not(.ds-a)") and not traegt_ds_klasse("[class~=ds-a]")


LIZENZ = re.compile(r"ofl-[a-z0-9-]+\.txt")


def test_in_static_nur_css_woff2_und_lizenztexte():
    """Jede Datei mit erlaubter Endung und einem Namen, den ist_design_pfad() annimmt (sonst wäre sie ohne Anmeldung nicht erreichbar);
    keine Symlinks oder Verbindungen; jede woff2 echt und in ds.css verwendet, jede Familie mit Lizenztext."""
    funde, woff2, lizenzen = [], set(), set()
    for ordner, verzeichnisse, dateien in os.walk(STATIC_DIR):
        for name in verzeichnisse + dateien:
            pfad = Path(ordner) / name
            rel = pfad.relative_to(STATIC_DIR).as_posix()
            if pfad.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(pfad)):
                funde.append(f"{rel}: Symlink")
            if not ist_design_pfad({"type": "http", "method": "GET", "path": f"/static/{rel}", "raw_path": f"/static/{rel}".encode()}):
                funde.append(f"{rel}: Name ohne Anmeldung nicht erreichbar")
        for name in dateien:
            rel = (Path(ordner) / name).relative_to(STATIC_DIR).as_posix()
            if name.endswith(".woff2"):
                woff2.add(rel)
                if (Path(ordner) / name).read_bytes()[:4] != b"wOF2":
                    funde.append(f"{rel}: kein woff2")
            elif LIZENZ.fullmatch(name):
                lizenzen.add(name)
                if "SIL OPEN FONT LICENSE Version 1.1" not in (Path(ordner) / name).read_text(encoding="utf-8"):
                    funde.append(f"{rel}: kein OFL-Text")
            elif not name.endswith(".css"):
                funde.append(f"{rel}: nicht erlaubt")
    css = DS_CSS.read_text(encoding="utf-8")
    verwendet = {f"ds/{u}" for u in re.findall(r'url\("([^"]+)"\)', css)}
    assert funde == [] and woff2 == verwendet, (funde, woff2 ^ verwendet)
    familien = set(re.findall(r'font-family:\s*"([^"]+)"', css))
    assert familien == {"Archivo", "IBM Plex Sans", "IBM Plex Mono"}
    assert lizenzen == {"ofl-archivo.txt", "ofl-ibm-plex-sans.txt", "ofl-ibm-plex-mono.txt"}


def test_schriften_je_schnitt_latin_und_latin_ext():
    css = DS_CSS.read_text(encoding="utf-8")
    flaechen = re.findall(r'font-family:\s*"([^"]+)";\s*font-style:\s*normal;\s*font-weight:\s*(\d+);.*?url\("schriften/[a-z-]+?-'
                          r'(latin|latin-ext)-\d+-normal\.woff2"\)', css, re.S)
    erwartet = {(f, w, t) for f, ws in (("Archivo", "500 600 700"), ("IBM Plex Sans", "400 500 600"), ("IBM Plex Mono", "400 500"))
                for w in ws.split() for t in ("latin", "latin-ext")}
    assert set(flaechen) == erwartet and len(flaechen) == 16


def _ohne_jinja_kommentare(text: str) -> str:
    return re.sub(r"\{#.*?#\}", lambda m: " " * len(m.group(0)), text, flags=re.S)


def test_jede_seite_bindet_den_ds_kopf_vor_ihrem_stil_ein():
    funde = []
    for name in vj.seiten():
        if not vj.bindet_ein(name, "_ds_kopf.html"):
            funde.append(f"{name}: bindet _ds_kopf.html nicht ein")
            continue
        text = _ohne_jinja_kommentare(vj.zusammensetzen(name)[0])
        link = text.find('href="/static/ds/ds.css?v=')
        kopf = text.find("<head")
        kopf_ende = min([i for i in (text.find("</head>"), text.find("<body")) if i >= 0] or [len(text)])
        stil = text.find("<style")
        if text.count('href="/static/ds/ds.css?v=') != 1:
            funde.append(f"{name}: ds.css nicht genau einmal")
        elif not (kopf < link < kopf_ende) or not (stil == -1 or link < stil):
            funde.append(f"{name}: ds.css nicht im Kopf vor dem eigenen Stilblock")
    assert funde == []


def test_ds_kopf_bindet_ds_css_und_ds_basis_mit_pruefsumme_ein():
    """Seit 1.8.161 dazu ds-basis.css (Grundregeln nur unter .ds-seite, tests/test_v441_rahmen_baustein.py) -- nach ds.css. Seit 1.9.2
    mit der Prüfsumme des Inhalts statt der Version (bis dahin ?v={{ app_version }}). Seit 1.9.5 dazu ds-alte-namen.css (die alten
    Farbnamen der Seiten zentral, tests/test_v442_alte_farbnamen.py). Seit 1.9.122 dazu ds-gesperrt.css."""
    text = _ohne_jinja_kommentare((ROOT / "app" / "templates" / "_ds_kopf.html").read_text(encoding="utf-8")).strip()
    assert text.splitlines() == ['<link rel="stylesheet" href="/static/ds/ds.css?v={{ ds_css_pruefsumme }}">',
                                 '<link rel="stylesheet" href="/static/ds/ds-basis.css?v={{ ds_basis_pruefsumme }}">',
                                 '<link rel="stylesheet" href="/static/ds/ds-alte-namen.css?v={{ ds_alte_namen_pruefsumme }}">',
                                 # seit 1.9.122: gesperrte Felder, eine Regel für jede Seite (tests/test_v542_gesperrte_felder.py)
                                 '<link rel="stylesheet" href="/static/ds/ds-gesperrt.css?v={{ ds_gesperrt_pruefsumme }}">']


def test_pruefsumme_folgt_dem_inhalt(tmp_path):
    """Ändert sich der Inhalt, ändert sich die Adresse (seit 1.9.2) -- unabhängig von der Version; derselbe Inhalt, dieselbe Adresse."""
    import hashlib

    import jinja2

    from app.design_dateien import pruefsumme

    datei = tmp_path / "ds.css"
    datei.write_text(":root{--ds-grund:#EEF0F1}", encoding="utf-8")
    vorher = pruefsumme("ds.css", tmp_path)
    assert re.fullmatch(r"[0-9a-f]{10}", vorher) and vorher == hashlib.sha256(datei.read_bytes()).hexdigest()[:10]
    assert pruefsumme("ds.css", tmp_path) == vorher
    datei.write_text(":root{--ds-grund:#EEF0F2}", encoding="utf-8")
    nachher = pruefsumme("ds.css", tmp_path)
    assert nachher != vorher
    kopf = jinja2.Environment(loader=jinja2.FileSystemLoader(str(ROOT / "app" / "templates"))).get_template("_ds_kopf.html")
    adressen = [next(z for z in kopf.render(ds_css_pruefsumme=p, ds_basis_pruefsumme="x").splitlines() if "/ds.css?" in z)
                for p in (vorher, nachher)]
    assert adressen[0] != adressen[1] and f"ds.css?v={nachher}" in adressen[1]


def test_seite_nennt_die_pruefsumme_des_heutigen_inhalts(threaded_db_session, router_test_client):
    import hashlib

    from app.routers.pages import router as pages_router

    html = router_test_client(threaded_db_session, pages_router).get("/inspection-templates").text
    for name in ("ds.css", "ds-basis.css"):
        soll = hashlib.sha256((ROOT / "app" / "static" / "ds" / name).read_bytes()).hexdigest()[:10]
        assert f'href="/static/ds/{name}?v={soll}"' in html, name


def test_waechter_seite_ohne_ds_kopf(tmp_path):
    (tmp_path / "_ds_kopf.html").write_text('<link rel="stylesheet" href="/static/ds/ds.css?v=1">', encoding="utf-8")
    (tmp_path / "gut.html").write_text('<html><head>{% include "_ds_kopf.html" %}<style></style></head><body></body></html>',
                                        encoding="utf-8")
    (tmp_path / "spaet.html").write_text('<html><head><style></style>{% include "_ds_kopf.html" %}</head><body></body></html>',
                                          encoding="utf-8")
    (tmp_path / "ohne.html").write_text("<html><head><style></style></head><body></body></html>", encoding="utf-8")
    assert vj.bindet_ein("gut.html", "_ds_kopf.html", tmp_path) and not vj.bindet_ein("ohne.html", "_ds_kopf.html", tmp_path)
    text = vj.zusammensetzen("spaet.html", wurzel=tmp_path)[0]
    assert text.find("<style") < text.find('href="/static/ds/ds.css')


def test_staticfiles_nur_im_modul_der_design_dateien():
    funde = []
    for pfad in (ROOT / "app").rglob("*.py"):
        if pfad.name == "design_dateien.py" and pfad.parent.name == "app":
            continue
        for knoten in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
            name = (knoten.name if isinstance(knoten, ast.alias) else knoten.id if isinstance(knoten, ast.Name)
                    else knoten.attr if isinstance(knoten, ast.Attribute) else None)
            if name and name.split(".")[-1] == "StaticFiles":
                funde.append(f"{pfad.relative_to(ROOT)}:{getattr(knoten, 'lineno', '?')}")
    assert funde == []


def test_die_anwendung_bindet_static_ein():
    from starlette.routing import Mount

    from app import main
    mounts = [r for r in main.app.routes if isinstance(r, Mount) and r.path == "/static"]
    assert len(mounts) == 1 and isinstance(mounts[0].app, design_dateien.DesignDateien)
    assert Path(mounts[0].app.directory).resolve() == STATIC_DIR


# ---------------------------------------------------------------------------
# Kontrast
# ---------------------------------------------------------------------------

def _tokens(text: str) -> tuple[dict, dict]:
    bloecke = {kopf: dict(_deklarationen(rumpf)) for kopf, rumpf in css_regeln(text)[0] if kopf in TOKEN_BLOECKE}
    hell = {k.removeprefix("--ds-"): v for k, v in bloecke[":root"].items()}
    dunkel = {**hell, **{k.removeprefix("--ds-"): v for k, v in bloecke[':root[data-theme="dark"]'].items()}}
    return hell, dunkel


def pruefpaare(text: str) -> list[tuple[float, str, str]]:
    kopf = text[:text.index("*/")]
    paare = []
    for grenze, block in re.findall(r"mindestens\s+([\d,]+)\s*:\s*1\s*\n(.*?)(?=\n\s*\S[^\n]*mindestens|\Z)", kopf, re.S):
        paare += [(float(grenze.replace(",", ".")), a, b) for a, b in re.findall(r"([a-z0-9-]+)/([a-z0-9-]+)", block)]
    return paare


def _leuchtdichte(farbe: str) -> float:
    h = farbe.strip().lstrip("#")
    assert re.fullmatch(r"[0-9a-fA-F]{6}", h), farbe
    kanaele = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in kanaele]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def kontrast(a: str, b: str) -> float:
    hell, dunkel = sorted((_leuchtdichte(a), _leuchtdichte(b)), reverse=True)
    return (hell + 0.05) / (dunkel + 0.05)


def kontrast_verstoesse(text: str) -> list[str]:
    hell, dunkel = _tokens(text)
    funde = []
    for grenze, a, b in pruefpaare(text):
        for thema, werte in (("hell", hell), ("dunkel", dunkel)):
            if a not in werte or b not in werte:
                funde.append(f"{thema} {a}/{b}: Token fehlt")
            elif (k := kontrast(werte[a], werte[b])) < grenze:
                funde.append(f"{thema} {a}/{b}: {k:.2f} < {grenze}")
    return funde


def test_kontrast_der_pruefpaare_hell_und_dunkel():
    text = DS_CSS.read_text(encoding="utf-8")
    paare = pruefpaare(text)
    # seit 1.8.155 39 statt 34: Firmengrün als Hauptaktion -- Schrift auf dem Knopf und grüne Schrift mindestens 4,5, der Knopf
    # selbst auf Fläche und Grund mindestens 3; seit 1.8.157 40: der Knopf auch auf flaeche-2 (Hover, Infokasten); seit 1.9.1 41:
    # navi-text auf navi-hover (Hover in Leiste und Monteurskopf); seit 1.9.50 43: der Feldrahmen auf der Signalfläche
    # (feld-rand-signal auf signal-hell und flaeche); seit 1.9.96 47: die Farbpunkte der Zeitarten auf der Fläche (Seite „Zeiten“); seit 1.9.110
    # 48: die Schrift eines gesperrten Felds auf seiner Fläche (text-2/feld-gesperrt)
    assert len(paare) == 48 and {g for g, _, _ in paare} == {4.5, 3.0}
    assert (4.5, "text-2", "feld-gesperrt") in paare
    assert (4.5, "navi-text", "navi-hover") in paare
    assert {(4.5, "auf-aktion", "aktion"), (4.5, "aktion-text", "aktion-hell"), (4.5, "aktion-text", "flaeche"),
            (3.0, "aktion", "flaeche"), (3.0, "aktion", "grund"), (3.0, "aktion", "flaeche-2")} <= set(paare)
    assert kontrast_verstoesse(text) == []


def test_kontrast_gegenprobe():
    text = DS_CSS.read_text(encoding="utf-8")
    assert kontrast("#000000", "#FFFFFF") == pytest.approx(21.0)
    zu_hell = text.replace("--ds-text-3: #5A646C;", "--ds-text-3: #9AA3AA;", 1)
    assert any(f.startswith("hell text-3/") for f in kontrast_verstoesse(zu_hell))
    dunkel_zu_dunkel = text.replace("--ds-fehler: #C53A35;", "--ds-fehler: #8F2A27;", 1)
    assert "dunkel fehler/flaeche" in " ".join(kontrast_verstoesse(dunkel_zu_dunkel))
    ohne_token = text.replace("--ds-ok-hell: #EEF5E8;", "", 1)  # bis 1.8.154 #DDF1EE
    assert any("ok-text/ok-hell: Token fehlt" in f for f in kontrast_verstoesse(ohne_token))
    # seit 1.8.155: das dunkle Grün zu dunkel für den Knopf auf der Fläche, Schrift auf dem Knopf zu hell, Token fehlt
    gruen_zu_dunkel = text.replace("--ds-aktion: #3D823E;", "--ds-aktion: #2F5A30;", 1)
    assert "dunkel aktion/flaeche" in " ".join(kontrast_verstoesse(gruen_zu_dunkel))
    schrift_zu_hell = text.replace("--ds-aktion: #367337;", "--ds-aktion: #A7CD5D;", 1)
    assert "hell auf-aktion/aktion" in " ".join(kontrast_verstoesse(schrift_zu_hell))
    ohne_gruen = text.replace("--ds-aktion-text: #2A5C2B;", "", 1)
    assert any("aktion-text/flaeche: Token fehlt" in f for f in kontrast_verstoesse(ohne_gruen))
    # seit 1.8.157: das dunkle Grün von 1.8.155 (#3B7D3C) lag auf flaeche-2 bei 2,91
    gruen_alt = text.replace("--ds-aktion: #3D823E;", "--ds-aktion: #3B7D3C;", 1)
    assert "dunkel aktion/flaeche-2" in " ".join(kontrast_verstoesse(gruen_alt))


def ok_wie_aktion_verstoesse(text: str) -> list[str]:
    hell, dunkel = _tokens(text)
    return [f"{thema} {ok}: {werte.get(ok)} statt {werte.get(aktion)} ({aktion})"
            for thema, werte in (("hell", hell), ("dunkel", dunkel))
            for ok, aktion in (("ok", "aktion"), ("ok-hell", "aktion-hell"), ("ok-text", "aktion-text"))
            if werte.get(ok) is None or werte.get(ok, "").upper() != werte.get(aktion, "").upper()]


def test_ok_traegt_die_werte_von_aktion():
    """Festlegung 1.8.155 Nr. 1 (bestätigt): ok, ok-hell, ok-text tragen dieselben Hex-Werte wie aktion, aktion-hell, aktion-text
    (eigene Werte statt Verweis, damit der Kontrasttest sie liest) -- seit 1.8.157 hält ein Wächter sie gleich."""
    text = DS_CSS.read_text(encoding="utf-8")
    assert ok_wie_aktion_verstoesse(text) == []
    # Gegenprobe: nur aktion geändert, ok nicht nachgezogen
    nur_aktion = text.replace("--ds-aktion: #3D823E;", "--ds-aktion: #3E843F;", 1)
    assert ok_wie_aktion_verstoesse(nur_aktion) == ["dunkel ok: #3D823E statt #3E843F (aktion)"]
