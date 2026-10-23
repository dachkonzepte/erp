"""Version 1.8.98 -- Weiterleitungsziele nur lokal (Vorgabe vom 14.10.2026, Punkt 1).

Eine Prüffunktion auf dem Server (app/weiterleitung.py::sicheres_ziel()) und eine im Browser (app/templates/_weiterleitung.html,
sicheresZiel()): nur lokale Pfade, sonst die Startseite. Bis 1.8.97 prüfte nur der Server (_safe_next_target(), ohne Rückstrich, Tab
und kodierte Varianten); im Browser setzte login.html nach der Anmeldung location.href ungeprüft auf next -- /login?next=javascript:…
führte das Skript im ERP aus, next=//fremd leitete auf eine fremde Seite (Nebenbefunde 1 und 2 aus 1.8.97).

- Angriffstabelle: dieselben Werte gegen beide Fassungen (die Browser-Fassung in node), dazu die Weiterleitung des Servers
  (/login?next=…) und die echten Seitenskripte von login.html und account.html in node.
- Strukturtest Server: jede RedirectResponse in app/ nimmt ein festes Ziel oder geht über sicheres_ziel() (AST).
- Strukturtest Browser: jede Navigation einer Vorlage zu einem Wert aus der Adresse geht über sicheresZiel() oder beginnt mit einem
  festen lokalen Pfad (tests/vorlagen_navigation.py).
Der Klicktest scripts/klicktest_anmelden.py prüft dieselben Angriffe im echten Browser (vorher BEFUND-Zeilen)."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from urllib.parse import quote

import pytest

from app.auth import hash_password
from app.models import AppUser
from app.routers import account as account_router
from app.routers import auth as auth_router
from app.routers import pages as pages_router
from app.weiterleitung import ist_lokal, sicheres_ziel
from tests.anmeldung import client_mit_schranke, neue_datenbank
from tests.test_v314_dashboard_month_berlin import NODE, _node
from tests.vorlagen_js import Quelle
from tests.vorlagen_navigation import alle_vorlagen, navigationen, navigationen_der_vorlage

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")

FREMD = "fremd.example"
ANGRIFFE = [
    # Skript statt Pfad
    "javascript:alert(1)", "JaVaScRiPt:alert(1)", " javascript:alert(1)", "java\tscript:alert(1)", "javascript%3Aalert(1)",
    "javascript://%0aalert(1)", "data:text/html,<script>alert(1)</script>", "data:text/html;base64,PHNjcmlwdD4=", "vbscript:msgbox(1)",
    # fremder Server
    f"//{FREMD}", f"///{FREMD}", f"////{FREMD}", f"/\\{FREMD}", f"\\\\{FREMD}", f"\\/{FREMD}", f"/\\/{FREMD}",
    f"http://{FREMD}", f"https://{FREMD}/x", f"https:{FREMD}", f"http:/{FREMD}", f"HTTPS://{FREMD}", f"//{FREMD}@app",
    f"{FREMD}", f"{FREMD}/tasks", "tasks",
    # vom Browser entfernte oder umgedeutete Zeichen
    f"/\t/{FREMD}", f"/\n/{FREMD}", f"/\r/{FREMD}", f"/ /{FREMD}", " /tasks", "/tasks ", "/tasks\n", f"/\x00/{FREMD}",
    f"/。{FREMD}", f"/／{FREMD}", f"/∕{FREMD}",
    # kodierte Varianten
    f"/%2F{FREMD}", f"/%2f%2f{FREMD}", f"%2F%2F{FREMD}", f"/%5C{FREMD}", f"/%5c{FREMD}", f"/%09/{FREMD}", f"/%0a/{FREMD}",
    f"/%0D/{FREMD}", "/%00/x", f"/%252F%252F{FREMD}", f"/%25252F%25252F{FREMD}", f"/%255C{FREMD}", f"/%25%32%46%25%32%46{FREMD}",
    "/%2525252525252F", "/x%", "/x%zz", "/%ff", "/%c3", "/" + "a" * 2001,
    # leer, kein Text
    "", None, 5, ["/tasks"],
]
ERLAUBT = [
    "/", "/tasks", "/customers/12", "/projects?x=1#y", "/login?next=%2Ftasks", "/login?next=%2F%2Ffremd", "/suche?q=M%C3%BCller",
    "/a/b/c", "/%C3%BC", "/mobil", "/orders/3/service-reports?report=7", "/master-data#materials", "/a//b",
]
# Abgelehnt, obwohl ohne Gefahr -- die Regel ist bewusst streng (kein echter Pfad dieser Seiten sieht so aus).
# "/100%25" dekodiert zu "/100%" -- ein "%" ohne Hex-Ziffern, an dem decodeURIComponent im Browser scheitert.
STRENG = ["/Kunde%20A", "/a%5Cb", "/a%09b", "/100%25"]


def _ist_lokal_im_browser(werte: list) -> list:
    skript = re.findall(r"<script>(.*?)</script>", (TEMPLATES / "_weiterleitung.html").read_text(encoding="utf-8"), flags=re.S)[0]
    js = (skript + f"\nconst werte = {json.dumps(werte)};\n"
          "process.stdout.write(JSON.stringify(werte.map(w => [istLokalesZiel(w), sicheresZiel(w, '/start'),"
          " typeof w === 'string' && istLokalesZiel(w) ? new URL(w, 'https://app.example').origin : null])));")
    return _node(js, "Europe/Berlin")


# ---------------------------------------------------------------------------
# Die Prüffunktion
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("wert", ANGRIFFE + STRENG, ids=repr)
def test_server_lehnt_ab(wert):
    assert ist_lokal(wert) is False
    assert sicheres_ziel(wert) == "/"
    assert sicheres_ziel(wert, "/mobil") == "/mobil"


@pytest.mark.parametrize("wert", ERLAUBT)
def test_server_nimmt_lokale_pfade(wert):
    assert ist_lokal(wert) is True
    assert sicheres_ziel(wert, "/start") == wert


@nur_mit_node
def test_browser_entscheidet_wie_der_server():
    werte = ANGRIFFE + STRENG + ERLAUBT
    ergebnis = _ist_lokal_im_browser(werte)
    abweichend = [(w, b[0]) for w, b in zip(werte, ergebnis) if b[0] is not ist_lokal(w)]
    assert abweichend == []
    for w, (lokal, ziel, ursprung) in zip(werte, ergebnis):
        assert ziel == (w if lokal else "/start")
        if lokal:
            assert ursprung == "https://app.example", w  # lokal heißt: derselbe Server


# ---------------------------------------------------------------------------
# Der Server: /login?next=… einer angemeldeten Person
# ---------------------------------------------------------------------------

PASSWORT = "RichtigesPasswort123"


@pytest.fixture
def server():
    engine, make_session = neue_datenbank()
    with make_session() as db:
        for name, rolle in (("bea", "buero_auftrag"), ("mia", "field"), ("anna", "admin")):
            db.add(AppUser(username=name, display_name=name, role=rolle, active=True, password_hash=hash_password(PASSWORT)))
        db.commit()
    yield lambda: client_mit_schranke(make_session, pages_router.router, auth_router.router, account_router.router)
    engine.dispose()


def _angemeldet(neu, name):
    client = neu()
    assert client.post("/api/auth/login", json={"username": name, "password": PASSWORT}).status_code == 200
    return client


def _ziel(client, wert) -> str:
    antwort = client.get("/login", params={"next": wert}, follow_redirects=False)
    assert antwort.status_code == 302
    return antwort.headers["location"]


@pytest.mark.parametrize("wert", [w for w in ANGRIFFE if isinstance(w, str)], ids=repr)
def test_angriff_ueber_next_am_server_landet_auf_der_startseite(server, wert):
    assert _ziel(_angemeldet(server, "bea"), wert) == "/"
    assert _ziel(_angemeldet(server, "mia"), wert) == "/mobil"
    assert _ziel(_angemeldet(server, "anna"), wert) == "/account"  # zweiter Faktor ausstehend, next fällt weg


@pytest.mark.parametrize("wert", ERLAUBT)
def test_lokales_next_am_server_bleibt(server, wert):
    assert _ziel(_angemeldet(server, "bea"), wert) == wert
    assert _ziel(_angemeldet(server, "anna"), wert) == "/account?next=" + quote(wert, safe="")


# ---------------------------------------------------------------------------
# Der Browser: die echten Seitenskripte in node
# ---------------------------------------------------------------------------

_ATTRAPPE = r"""
var AUFRUFE = [], ANTWORT = {};
const _el = {};
var document = {getElementById: id => _el[id] || (_el[id] = {value: '', textContent: '', checked: false, className: '', style: {},
  classList: {add() {}, remove() {}, toggle() {}, contains() { return false; }}, addEventListener() {}}),
  addEventListener() {}, querySelectorAll: () => [], querySelector: () => null};
var window = globalThis;
window.addEventListener = () => {};
var location = {href: '', search: SUCHE, pathname: PFAD, hash: ''};
globalThis.fetch = async (url, opt = {}) => {
  AUFRUFE.push({url, methode: opt.method || 'GET'});
  return {ok: true, status: 200, statusText: 'OK', headers: {get: () => 'application/json'}, json: async () => ANTWORT,
          text: async () => JSON.stringify(ANTWORT), clone() { return this; }};
};
"""


def _seitenskript(vorlage: str) -> str:
    teile = []
    for name in ("_speichern.html", "_weiterleitung.html"):
        teile += re.findall(r"<script>(.*?)</script>", (TEMPLATES / name).read_text(encoding="utf-8"), flags=re.S)
    eigen = re.findall(r"<script>(.*?)</script>", (TEMPLATES / vorlage).read_text(encoding="utf-8"), flags=re.S)[-1]
    return "\n".join(teile) + "\n" + re.sub(r"\{\{.*?\}\}", "1", eigen)


def _browser(vorlage: str, pfad: str, suche: str, antwort: dict, aufruf: str, vorher: str = "") -> str:
    js = (_ATTRAPPE.replace("SUCHE", json.dumps(suche)).replace("PFAD", json.dumps(pfad)) + _seitenskript(vorlage)
          + f"\nANTWORT = {json.dumps(antwort)};\n(async () => {{ {vorher} await {aufruf}; "
          "process.stdout.write(JSON.stringify(location.href)); })().catch(e => { console.error(e && e.stack || e); process.exit(1); });")
    return _node(js, "Europe/Berlin")


def _anmelden_im_browser(wert, antwort) -> str:
    # load() o. ä. gibt es in login.html nicht -- das Skript definiert nur login(); die Felder sind leer.
    return _browser("login.html", "/login", "?next=" + quote(wert, safe=""), antwort, "login()")


@nur_mit_node
@pytest.mark.parametrize("wert", [w for w in ANGRIFFE if isinstance(w, str) and w], ids=repr)
def test_angriff_ueber_next_im_anmeldeformular(wert):
    assert _anmelden_im_browser(wert, {"role": "buero_auftrag"}) == "/projects"
    assert _anmelden_im_browser(wert, {"role": "field"}) == "/mobil"
    assert _anmelden_im_browser(wert, {"role": "admin", "two_factor_required": True, "otp_ok": False}) == "/account"


@nur_mit_node
@pytest.mark.parametrize("wert", ERLAUBT)
def test_lokales_next_im_anmeldeformular(wert):
    assert _anmelden_im_browser(wert, {"role": "buero_auftrag"}) == wert
    assert _anmelden_im_browser(wert, {"role": "admin", "two_factor_required": True, "otp_ok": False}) == \
        "/account?next=" + quote(wert, safe="").replace("~", "%7E")  # encodeURIComponent


@nur_mit_node
@pytest.mark.parametrize("wert,erwartet", [("javascript:alert(1)", "/"), (f"//{FREMD}", "/"), (f"/\\{FREMD}", "/"),
                                           (f"/%2F{FREMD}", "/"), ("/tasks", "/tasks")])
def test_konto_nach_dem_zweiten_faktor(wert, erwartet):
    """account.html::verifyCode() nach der Bestätigung (Zeile 177 setzte next bis 1.8.97 ungeprüft)."""
    ziel = _browser("account.html", "/account", "?next=" + quote(wert, safe=""), {"ok": True}, "verifyCode()",
                    vorher="load = async () => {};")
    assert ziel == erwartet


# ---------------------------------------------------------------------------
# Strukturtest Server: jede Weiterleitung mit festem Ziel oder über sicheres_ziel()
# ---------------------------------------------------------------------------

# Funktionen, deren Ergebnis ein festes Ziel ist (aus einer Tabelle im Code, nie aus der Anfrage).
FESTE_ZIELE = {"default_home_page_for_role": "app/permissions.py: '/mobil' für Monteure, sonst '/'"}


def _fester_lokaler_text(wert: str) -> bool:
    return wert == "/" or (len(wert) >= 2 and wert[0] == "/" and wert[1] not in "/\\")


def _zulaessig(knoten: ast.AST, funktion: ast.AST | None, tiefe: int = 0) -> bool:
    if tiefe > 10:
        return False
    if isinstance(knoten, ast.Constant):
        return isinstance(knoten.value, str) and _fester_lokaler_text(knoten.value)
    if isinstance(knoten, ast.JoinedStr):
        erster = knoten.values[0] if knoten.values else None
        if not isinstance(erster, ast.Constant):
            return False
        return _fester_lokaler_text(erster.value) and (len(erster.value) >= 2 or len(knoten.values) == 1)
    if isinstance(knoten, ast.Call):
        name = getattr(knoten.func, "id", None) or getattr(knoten.func, "attr", None)
        return name == "sicheres_ziel" or name in FESTE_ZIELE
    if isinstance(knoten, ast.IfExp):
        return _zulaessig(knoten.body, funktion, tiefe + 1) and _zulaessig(knoten.orelse, funktion, tiefe + 1)
    if isinstance(knoten, ast.BoolOp):
        return all(_zulaessig(v, funktion, tiefe + 1) for v in knoten.values)
    if isinstance(knoten, ast.Name) and funktion is not None:
        werte = [n.value for n in ast.walk(funktion) if isinstance(n, ast.Assign)
                 and any(isinstance(z, ast.Name) and z.id == knoten.id for z in n.targets)]
        werte += [n.value for n in ast.walk(funktion) if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
                  and n.target.id == knoten.id and n.value is not None]
        return bool(werte) and all(_zulaessig(w, funktion, tiefe + 1) for w in werte)
    return False


def weiterleitungen(quelltext: str, datei: str) -> list[tuple[str, bool]]:
    """(Stelle, zulässig) je RedirectResponse(...) und je Kopfzeile "Location" im Quelltext."""
    baum = ast.parse(quelltext)
    eltern = {}
    for knoten in ast.walk(baum):
        for kind in ast.iter_child_nodes(knoten):
            eltern[kind] = knoten

    def umgebende_funktion(knoten):
        while knoten in eltern:
            knoten = eltern[knoten]
            if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return knoten
        return None

    out = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Call) and (getattr(knoten.func, "id", None) or getattr(knoten.func, "attr", None)) == "RedirectResponse":
            ziel = next((k.value for k in knoten.keywords if k.arg == "url"), knoten.args[0] if knoten.args else None)
            out.append((f"{datei}:{knoten.lineno}", ziel is not None and _zulaessig(ziel, umgebende_funktion(knoten))))
        # Kopfzeile Location von Hand: headers={"Location": …} oder ….headers["Location"] = …
        if isinstance(knoten, ast.keyword) and knoten.arg == "headers" and isinstance(knoten.value, ast.Dict):
            for schluessel in knoten.value.keys:
                if isinstance(schluessel, ast.Constant) and str(schluessel.value).lower() == "location":
                    out.append((f"{datei}:{schluessel.lineno} (Kopfzeile Location)", False))
        if (isinstance(knoten, ast.Subscript) and isinstance(knoten.value, ast.Attribute) and knoten.value.attr == "headers"
                and isinstance(knoten.slice, ast.Constant) and str(knoten.slice.value).lower() == "location"):
            out.append((f"{datei}:{knoten.lineno} (Kopfzeile Location)", False))
    return out


def test_jede_weiterleitung_des_servers_hat_ein_festes_oder_geprueftes_ziel():
    funde, alle = [], []
    for pfad in sorted((ROOT / "app").rglob("*.py")):
        datei = pfad.relative_to(ROOT).as_posix()
        for stelle, ok in weiterleitungen(pfad.read_text(encoding="utf-8"), datei):
            alle.append(stelle)
            if not ok:
                funde.append(stelle)
    assert funde == [], "Weiterleitung ohne festes Ziel und ohne sicheres_ziel() (app/weiterleitung.py): " + ", ".join(funde)
    # Die bekannten Weiterleitungen werden gefunden (sonst prüfte der Test nichts).
    assert {s.split(":")[0] for s in alle} == {"app/anmeldeschranke.py", "app/routers/pages.py"}
    assert len(alle) == 6  # seit 1.9.59 dazu Stundenzettel und /time-tracking der Monteurin (auf „Meine Zeiten“)


@pytest.mark.parametrize("code,erwartet", [
    ('def f(request):\n    return RedirectResponse(url="/tasks")', True),
    ('def f(request):\n    return RedirectResponse(url=f"/login?next={x}")', True),
    ('def f(request):\n    return RedirectResponse(url=sicheres_ziel(request.query_params.get("next")))', True),
    ('def f(request):\n    u = "/a" if x else "/b"\n    return RedirectResponse(url=u)', True),
    ('def f(request):\n    return RedirectResponse(url=default_home_page_for_role(r))', True),
    ('def f(request):\n    return RedirectResponse(url=request.query_params["next"])', False),
    ('def f(request):\n    nxt = request.query_params.get("next")\n    return RedirectResponse(url=nxt or "/")', False),
    ('def f(request):\n    return RedirectResponse(url="/" + x)', False),
    ('def f(request):\n    return RedirectResponse(f"/{x}")', False),
    ('def f(request):\n    return RedirectResponse(url="//fremd")', False),
    ('def f(request):\n    return RedirectResponse(request.headers.get("referer"))', False),
    ('def f(request):\n    return Response(status_code=302, headers={"Location": x})', False),
])
def test_strukturtest_server_erkennt(code, erwartet):
    funde = weiterleitungen(code, "beispiel.py")
    assert funde and all(ok is erwartet for _, ok in funde)


# ---------------------------------------------------------------------------
# Strukturtest Browser: jede Navigation zu einem Wert aus der Adresse ist geprüft
# ---------------------------------------------------------------------------

def test_jede_navigation_zu_einem_wert_aus_der_adresse_ist_geprueft():
    unlesbar, aus_adresse = [], []
    for vorlage in alle_vorlagen():
        aus_adresse += [n for n in navigationen_der_vorlage(vorlage, unlesbar) if n.aus_adresse]
    rot = [f"{n.stelle} {n.ziel[:80]}" for n in aus_adresse if not n.geprueft]
    assert rot == [], "Navigation zu einem Wert aus der Adresse ohne sicheresZiel() (_weiterleitung.html): " + "; ".join(rot)
    # Handler, die der Tokenizer nicht liest, dürfen keine Navigation enthalten.
    assert [(v, c[:80]) for v, c in unlesbar if any(s in c for s in ("location", "href", "open("))] == []
    # Die Anmeldung und "Mein Konto" werden gefunden (sonst prüfte der Test nichts).
    gefunden = {n.stelle.split(":")[0] for n in aus_adresse if "sicheresZiel(" in n.ziel or "istLokalesZiel(" in n.ziel}
    assert {"login.html", "account.html"} <= gefunden


def _seiten_mit_sicheresziel() -> list[tuple[str, bool]]:
    """(Vorlage, bindet _weiterleitung.html ein) je Vorlage ohne "_", die sicheresZiel()/istLokalesZiel() aufruft -- seit 1.8.124
    (Stufe 0b) auch in Unterordnern, das Include auch im Basis-Template (tests/vorlagen_js.py::bindet_ein())."""
    from tests import vorlagen_js

    return [(vorlage, vorlagen_js.bindet_ein(vorlage, "_weiterleitung.html", TEMPLATES)) for vorlage in alle_vorlagen()
            if not Path(vorlage).name.startswith("_")
            and re.search(r"\b(sicheresZiel|istLokalesZiel)\(", (TEMPLATES / vorlage).read_text(encoding="utf-8"))]


def test_seiten_mit_sicheresziel_binden_den_baustein_ein():
    for vorlage, eingebunden in _seiten_mit_sicheresziel():
        assert eingebunden, vorlage


_SKRIPT_MIT_PARAMS = "const params=new URLSearchParams(location.search);function nextZiel(){return params.get('next')}\n"


@pytest.mark.parametrize("code,aus_adresse,geprueft", [
    ("location.href=new URLSearchParams(location.search).get('next');", True, False),
    ("location.href=new URLSearchParams(location.search).get('next')||'/';", True, False),
    ("location.href=sicheresZiel(new URLSearchParams(location.search).get('next'),'/');", True, True),
    (_SKRIPT_MIT_PARAMS + "location.href=params.get('next');", True, False),
    (_SKRIPT_MIT_PARAMS + "location.href=nextZiel();", True, False),
    (_SKRIPT_MIT_PARAMS + "location.href='/'+params.get('x');", True, False),
    (_SKRIPT_MIT_PARAMS + "location.href=`/${params.get('x')}`;", True, False),
    (_SKRIPT_MIT_PARAMS + "location.href='/projects/'+params.get('x');", True, True),
    (_SKRIPT_MIT_PARAMS + "location.href=`/a/${params.get('x')}`;", True, True),
    (_SKRIPT_MIT_PARAMS + "location.href=params.get('x')?`/a/${params.get('x')}`:'/b';", True, True),
    (_SKRIPT_MIT_PARAMS + "location.href=params.get('x')?params.get('x'):'/b';", True, False),
    (_SKRIPT_MIT_PARAMS + "window.open(params.get('x'),'_blank');", True, False),
    (_SKRIPT_MIT_PARAMS + "location.assign(params.get('x'));", True, False),
    (_SKRIPT_MIT_PARAMS + "location.replace(params.get('x'));", True, False),
    (_SKRIPT_MIT_PARAMS + "window.location=params.get('x');", True, False),
    (_SKRIPT_MIT_PARAMS + "document.getElementById('a').href=params.get('x');", True, False),
    ("location.href=document.referrer;", True, False),
    ("const h=location.hash.slice(1);location.href=h;", True, False),
    ("location.href='/orders/'+id;", False, True),
    ("location.href=ziel;", False, False),
])
def test_strukturtest_browser_erkennt(code, aus_adresse, geprueft):
    navs = navigationen(Quelle("beispiel.html", code, []))
    assert navs
    assert (navs[-1].aus_adresse, navs[-1].geprueft) == (aus_adresse, geprueft)


def test_strukturtest_browser_liest_handler_im_html(tmp_path, monkeypatch):
    """Ein Handler im HTML (on…="…") mit einem Wert aus dem Skript der Vorlage zählt mit."""
    import tests.vorlagen_js as vjs
    import tests.vorlagen_navigation as vnav
    (tmp_path / "x.html").write_text(
        "<script>" + _SKRIPT_MIT_PARAMS + "</script><button onclick=\"location.href=params.get('n')\">x</button>"
        "<button onclick=\"location.href=sicheresZiel(params.get('n'))\">y</button>", encoding="utf-8")
    monkeypatch.setattr(vjs, "TEMPLATES", tmp_path)
    monkeypatch.setattr(vnav, "TEMPLATES", tmp_path)
    navs = vnav.navigationen_der_vorlage("x.html")
    assert [(n.aus_adresse, n.geprueft) for n in navs] == [(True, False), (True, True)]
