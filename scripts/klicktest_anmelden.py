"""Klicktest: Anmelden (Formular und Seitenleiste) und Abmelden (beide Kopfzeilen) (1.8.97, Vorgabe Punkt 5).

Seit 1.8.95 laufen Anmelden und Abmelden über den Baustein app/templates/_speichern.html. Geprüft wird im echten Browser, mit Maus
und Tastatur wie ein Nutzer (Input.dispatchMouseEvent/insertText/dispatchKeyEvent), und über das Netzwerkprotokoll des Werkzeugs
(scripts/cdp_klicktest.py, tab.netz):

    Formular        /customers/<id> ohne Anmeldung -> /login?next=…; falsches Passwort: Meldung, kein Cookie, eine Anfrage (401);
                    richtiges: Weiterleitung auf next, Kundenakte geladen, Cookie httpOnly und SameSite=Lax
    Doppelklick     die erste Anmeldung im Netz angehalten: nur eine Anfrage unterwegs; seit 1.8.97 schickt der Baustein die
                    zweite, gleiche Anfrage gar nicht (sie bekommt das Ergebnis der ersten) -- insgesamt eine Anmeldung, und die
                    Weiterleitung steht nicht an der Warnung beim Verlassen
    Zwei Faktoren   Admin mit next=/projects -> /account?next=%2Fprojects "Zweiten Faktor einrichten", API 401
                    two_factor_pending, eine andere Seite schickt zurück nach /account
    Abmelden Büro   Kopfzeile (Kontomenü -> Abmelden) auf der Kundenakte, POST /api/auth/logout im Netz angehalten: die Seite
                    bleibt, keine Navigation; fortgesetzt: /login?next=…, die Abmeldung gesendet und beantwortet (200, nicht
                    abgebrochen), die Navigation erst nach der Antwort, Cookies weg, API 401; ein zweites Mal ohne Anhalten
    Seitenleiste    "Nicht angemeldet" erscheint nur, wenn /api/auth/status beim Laden "nicht angemeldet" meldet, die Seite
                    selbst aber ausgeliefert wurde -- nachgestellt: die Statusabfrage im Netz angehalten, das Cookie gelöscht
                    (Sitzung endet beim Laden), fortgesetzt; falsches Passwort: Meldung; richtiges: neu geladen mit Daten
    Abmelden Mobil  Kopfzeile von /mobil (Monteurin, 412 px) wie im Büro, danach /api/field-view/today 401; Anmelden über
                    das Formular mit next=/mobil
    Angriffe        angemeldet: /login?next=//fremd, /%5C…, /%09/… bleiben im ERP (app/routers/pages.py::_safe_next_target())

Lücken, die die Angriffe zeigen, sind keine Prüfungen, sondern "BEFUND"-Zeilen (gemeldet, nicht gezählt -- Festlegung 1.8.97):
next=fremde Adresse und next=javascript:… über das Formular, der alte Cookie-Wert nach dem Abmelden, "Zurück" nach dem Abmelden
(Back-Forward-Cache und HTTP-Cache). Feste Uhr 10:00 (Monteurin auf /mobil). alert()/confirm() werden mitgeschrieben.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_anmelden.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import asyncio
import json
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import antwort_kopf, gesendet, klicktest_main  # noqa: E402

DIALOGE = ("window.__confirms=[];window.confirm=m=>{window.__confirms.push(String(m));return true};"
           "window.__alerts=[];window.alert=m=>{window.__alerts.push(String(m))};")
PASSWORT = {"bea": "Bea-Passwort-1", "anna": "Anna-Passwort-1", "mia": "Mia-Passwort-1"}
FALSCH = "falsch-falsch-1"
MELDUNG_FALSCH = "Benutzername oder Passwort ist falsch."
COOKIES = ("dk_erp_auth", "dk_erp_otp_ok")
BEFUNDE: list[tuple[str, bool, str]] = []


def befuellen(db, k):
    from decimal import Decimal

    from app.models import AppUser, Customer, Employee

    bea_ma = Employee(employee_number="B-1", first_name="Bea", last_name="Büro", employee_group="angestellt",
                      weekly_hours=Decimal("40"), active=True)
    mia_ma = Employee(employee_number="M-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich",
                      weekly_hours=Decimal("40"), active=True)
    db.add_all([bea_ma, mia_ma]); db.flush()
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", employee_id=bea_ma.id,
                  password_hash=k.passwort(PASSWORT["bea"]))
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort(PASSWORT["anna"]))
    mia = AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia_ma.id,
                  password_hash=k.passwort(PASSWORT["mia"]))
    kunde = Customer(name="Gerda Geheim", last_name="Geheim", city="Geheimstadt")
    db.add_all([bea, anna, mia, kunde]); db.flush()
    return {"kunde": kunde.id, "cookies": {"bea": k.cookies(bea), "mia": k.cookies(mia)}}


# -- Maus und Tastatur ---------------------------------------------------------

async def _klick(tab, selektor: str, anzahl: int = 1) -> None:
    """Mausklick (anzahl 2: Doppelklick) auf die Mitte des Elements. Fehlt es (eine frühere Abweichung), zählt der Lauf als nicht
    wie erwartet, statt mit einer Ausnahme abzubrechen."""
    mitte = await tab.js(f"(()=>{{const e=document.querySelector({json.dumps(selektor)});if(!e)return null;"
                         "e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]})()")
    if not mitte:
        tab.nicht_geladen.append(f"Element fehlt: {selektor}")
        print(f"XX  Element fehlt: {selektor} (auf {await tab.js('location.pathname')})", flush=True)
        return
    x, y = mitte
    for n in range(1, anzahl + 1):
        await tab.cmd("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", buttons=1, clickCount=n)
        await tab.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", buttons=0, clickCount=n)


async def _tippen(tab, selektor: str, text: str) -> None:
    """Ins Feld klicken, vorhandenen Text markieren und den neuen eintippen."""
    await _klick(tab, selektor)
    await tab.js(f"document.querySelector({json.dumps(selektor)})?.select()")
    await tab.cmd("Input.insertText", text=text)


async def _enter(tab) -> None:
    await tab.cmd("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13,
                  nativeVirtualKeyCode=13, text="\r")
    await tab.cmd("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13,
                  nativeVirtualKeyCode=13)


# -- Hilfen ----------------------------------------------------------------------

async def _cookies(tab, details: bool = False) -> list:
    alle = (await tab.cmd("Network.getCookies", urls=[tab.base]))["cookies"]
    return sorted(([c["name"], c["httpOnly"], c.get("sameSite")] if details else c["name"]) for c in alle if c["name"] in COOKIES)


async def _cookie_werte(tab) -> dict:
    return {c["name"]: c["value"] for c in (await tab.cmd("Network.getCookies", urls=[tab.base]))["cookies"] if c["name"] in COOKIES}


def _status_mit_cookie(url: str, cookies: dict) -> int:
    """Eine Anfrage außerhalb des Browsers mit einem gemerkten Cookie-Wert (wie ihn ein Angreifer hätte)."""
    anfrage = urllib.request.Request(url, headers={"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())})
    try:
        with urllib.request.urlopen(anfrage, timeout=10) as antwort:
            return antwort.status
    except urllib.error.HTTPError as fehler:
        return fehler.code


def _freier_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def befund(name: str, luecke: bool, beobachtet: str) -> None:
    """Eine Lücke aus einem Angriff: gemeldet, nicht als Prüfung gezählt (Festlegung 1.8.97)."""
    BEFUNDE.append((name, luecke, beobachtet))
    print(f"BEFUND  {name}: {'ja' if luecke else 'nein'} ({beobachtet})"
          + ("  -- Lücke, gemeldet, keine Prüfung" if luecke else "  -- nicht (mehr) da: als Prüfung aufnehmen"), flush=True)


def _dokumente(tab, marke: int) -> list[dict]:
    return [e for e in tab.netz.verlauf[marke:] if e["art"] == "Document"]


async def _anmelden_formular(tab, benutzer: str, passwort: str, *, per_enter: bool = True) -> None:
    await _tippen(tab, "#u", benutzer)
    await _tippen(tab, "#p", passwort)
    if per_enter:
        await _enter(tab)
    else:
        await _klick(tab, "button")


# -- Anmelden über das Formular --------------------------------------------------

async def _formular(tab, seed, p):
    kid = seed["kunde"]
    next_kunde = f"?next=%2Fcustomers%2F{kid}"
    await tab.anmelden({})
    await tab.oeffnen(f"/customers/{kid}", "document.getElementById('u')")
    p.pruefe("Formular: ohne Anmeldung auf /login mit next", await tab.js("location.pathname+location.search"), "/login" + next_kunde)
    marke = len(tab.netz.verlauf)
    await _anmelden_formular(tab, "bea", FALSCH)
    await tab.warten("document.getElementById('msg').textContent.length>0", 10)
    p.pruefe("Formular: falsches Passwort -> Meldung", await tab.js("document.getElementById('msg').textContent"), MELDUNG_FALSCH)
    p.pruefe("Formular: falsches Passwort -> bleibt auf /login, kein Cookie",
             [await tab.js("location.pathname+location.search"), await _cookies(tab)], ["/login" + next_kunde, []])
    await tab.nachlesen()
    p.pruefe("Formular: falsches Passwort -> eine Anfrage, gesendet, 401",
             [(gesendet(e), e["status"]) for e in tab.netz.suche(r"/api/auth/login$", "POST", ab=marke)], [(True, 401)])

    await _tippen(tab, "#p", PASSWORT["bea"])
    await _klick(tab, "button")
    p.pruefe("Formular: richtiges Passwort -> Weiterleitung auf next, Kundenakte geladen", await tab.warten(
        f"location.pathname==='/customers/{kid}'&&document.getElementById('lastName')?.value==='Geheim'", 15), True)
    p.pruefe("Formular: Anmelde-Cookie httpOnly, SameSite=Lax", await _cookies(tab, details=True), [["dk_erp_auth", True, "Lax"]])
    p.pruefe("Formular: JS-Fehler", tab.fehler, [])
    await tab.bild("formular_angemeldet")


async def _doppelklick(tab, seed, p):
    kid = seed["kunde"]
    await tab.anmelden({})
    await tab.oeffnen(f"/login?next=%2Fcustomers%2F{kid}", "document.getElementById('u')")
    await _tippen(tab, "#u", "bea")
    await _tippen(tab, "#p", PASSWORT["bea"])
    marke = len(tab.netz.verlauf)
    await tab.im_netz_anhalten("*/api/auth/login")
    await _klick(tab, "button", anzahl=2)
    await tab.warte_bis_im_netz_angehalten(1)
    await tab.warten("false", 1.0, melden=False)  # Zeit, in der eine nicht wartende Seite die zweite schon geschickt hätte
    await tab.nachlesen()
    waehrend = tab.netz.suche(r"/api/auth/login$", "POST", ab=marke)
    p.pruefe("Doppelklick: während die erste Anmeldung im Netz hängt, eine Anfrage, nicht gesendet",
             [(gesendet(e), e["angehalten"]) for e in waehrend], [(False, True)])
    p.pruefe("Doppelklick: fortgesetzt", await tab.im_netz_fortsetzen(), 1)
    p.pruefe("Doppelklick: angemeldet auf next", await tab.warten(
        f"location.pathname==='/customers/{kid}'&&document.getElementById('lastName')?.value==='Geheim'", 15), True)
    await tab.nachlesen()
    alle = tab.netz.suche(r"/api/auth/login$", "POST", ab=marke)
    p.pruefe("Doppelklick: insgesamt eine Anmeldung (die zweite, gleiche nicht gesendet)", len(alle), 1)


async def _zwei_faktor(tab, seed, p):
    await tab.anmelden({})
    await tab.oeffnen("/login?next=%2Fprojects", "document.getElementById('u')")
    await _anmelden_formular(tab, "anna", PASSWORT["anna"])
    einrichten = "location.pathname==='/account'&&!document.getElementById('twoFactorSetupCard').classList.contains('hidden')"
    p.pruefe("Zwei Faktoren: Admin landet auf /account?next=%2Fprojects mit 'Zweiten Faktor einrichten'",
             [await tab.warten(einrichten, 15), await tab.js("location.search")], [True, "?next=%2Fprojects"])
    p.pruefe("Zwei Faktoren: angemeldet, zweiter Faktor ausstehend", await tab.js(
        "fetch('/api/auth/status').then(r=>r.json()).then(d=>[d.authenticated,d.two_factor_required,d.otp_ok])"), [True, True, False])
    p.pruefe("Zwei Faktoren: API gesperrt (401 two_factor_pending)", await tab.js(
        "fetch('/api/customers').then(async r=>[r.status,(await r.json()).two_factor_pending])"), [401, True])
    p.pruefe("Zwei Faktoren: eine andere Seite schickt zurück nach /account",
             await tab.oeffnen("/projects", "location.pathname==='/account'"), True)
    p.pruefe("Zwei Faktoren: JS-Fehler", tab.fehler, [])


# -- Abmelden ----------------------------------------------------------------------

async def _abmelden(tab, p, wo: str, *, seite: str, bereit: str, knoepfe: list[str], anhalten: bool, api: str):
    """Abmelden über eine Kopfzeile: auf seite (angemeldet, geladen) die knoepfe klicken. Mit anhalten: POST /api/auth/logout im
    Netz anhalten und prüfen, dass die Seite darauf wartet. Danach /login?next=<seite>, Abmeldung gesendet und beantwortet, die
    Navigation erst nach der Antwort, Cookies weg, api 401. Gibt die Cookie-Werte von vorher zurück."""
    await tab.oeffnen(seite, bereit)
    await tab.warte_auf_neu_geladene_liste()
    vorher = await _cookie_werte(tab)
    await tab.js("window.__vorAbmelden=1")
    marke = len(tab.netz.verlauf)
    if anhalten:
        await tab.im_netz_anhalten("*/api/auth/logout")
    for knopf in knoepfe:
        await _klick(tab, knopf)
    if anhalten:
        await tab.warte_bis_im_netz_angehalten(1)
        await tab.warten("false", 1.0, melden=False)  # Zeit, in der eine nicht wartende Seite schon navigiert hätte
        await tab.nachlesen()
        p.pruefe(f"{wo}: die Seite wartet auf die Abmeldung (dasselbe Dokument, keine Navigation begonnen)",
                 [await tab.js("window.__vorAbmelden===1&&location.pathname"), [e["url"] for e in _dokumente(tab, marke)]],
                 [seite, []])
        p.pruefe(f"{wo}: Abmeldung im Netz angehalten, nicht gesendet",
                 [(gesendet(e), e["angehalten"]) for e in tab.netz.suche(r"/api/auth/logout$", "POST", ab=marke)], [(False, True)])
        p.pruefe(f"{wo}: fortgesetzt", await tab.im_netz_fortsetzen(), 1)
    p.pruefe(f"{wo}: danach /login?next=…", [await tab.warten("location.pathname==='/login'&&document.getElementById('u')", 15),
                                             await tab.js("location.search")], [True, "?next=" + quote(seite, safe="")])
    await tab.nachlesen()
    abmeldungen = tab.netz.suche(r"/api/auth/logout$", "POST", ab=marke)
    e = abmeldungen[-1] if abmeldungen else None
    p.pruefe(f"{wo}: POST /api/auth/logout gesendet und beantwortet (200, nicht abgebrochen)",
             [len(abmeldungen), gesendet(e), antwort_kopf(e), e["status"], e["fehler"]] if e else [0], [1, True, True, 200, None])
    login = [d for d in _dokumente(tab, marke) if "/login?next=" in d["url"]]
    p.pruefe(f"{wo}: Navigation auf /login erst nach der Antwort",
             bool(e and login and e["ts_antwort"] is not None and login[0]["ts_start"] >= e["ts_antwort"]), True)
    p.pruefe(f"{wo}: Cookies gelöscht", await _cookies(tab), [])
    p.pruefe(f"{wo}: API aus der Seite danach 401, Status nicht angemeldet", await tab.js(
        f"Promise.all([fetch({json.dumps(api)}).then(r=>r.status),fetch('/api/auth/status').then(r=>r.json()).then(d=>d.authenticated)])"),
        [401, False])
    p.pruefe(f"{wo}: JS-Fehler", tab.fehler, [])
    return vorher


async def _zurueck(tab, wo: str, daten: str, bereit_seite: str):
    """"Zurück" nach dem Abmelden: zeigt der Browser die Seite mit Daten? Befund, keine Prüfung."""
    marke = len(tab.netz.verlauf)
    await tab.js("history.back()")
    await tab.warten(f"location.pathname!=='/login'&&document.readyState==='complete'&&({bereit_seite})", 10, melden=False)
    await tab.warten("false", 1.0, melden=False)
    await tab.nachlesen()
    sichtbar = bool(await tab.js(f"(()=>{{try{{return !!({daten})}}catch(e){{return false}}}})()"))
    aus_bfcache = await tab.js("window.__vorAbmelden===1")
    aus_cache = [e for e in tab.netz.verlauf[marke:] if e["cache"] and e["url"] and "/api/" in e["url"]]
    herkunft = ("Back-Forward-Cache: dieselbe Seite samt Zustand" if aus_bfcache else
                f"HTTP-Cache: Seite und {len(aus_cache)} API-Antworten aus dem Cache, ohne Anfrage")
    befund(f"{wo}: 'Zurück' nach dem Abmelden zeigt die Daten", sichtbar, herkunft)
    await tab.bild("zurueck_" + "".join(z if z.isascii() and z.isalnum() else "_" for z in wo.lower().replace("ü", "ue")))


async def _abmelden_buero(tab, seed, p):
    kid = seed["kunde"]
    seite = f"/customers/{kid}"
    kunde_da = "document.getElementById('lastName')?.value==='Geheim'"
    daten = "document.body.innerText.includes('Geheimstadt')||document.getElementById('lastName')?.value==='Geheim'"
    knoepfe = ["#appTopbarAccountBtn", "#appTopbarLogout"]
    await tab.anmelden(seed["cookies"]["bea"])
    await tab.fenster(1400, 1000)
    vorher = await _abmelden(tab, p, "Abmelden Büro", seite=seite, bereit=kunde_da, knoepfe=knoepfe, anhalten=True,
                             api=f"/api/customers/{kid}")
    status = await asyncio.to_thread(_status_mit_cookie, tab.base + f"/api/customers/{kid}", vorher)
    befund("Abmelden Büro: der alte Cookie-Wert gilt nach dem Abmelden weiter (Sitzung serverseitig nicht ungültig)",
           status == 200, f"GET /api/customers/{kid} mit dem Cookie von vorher: {status}")
    await _zurueck(tab, "Abmelden Büro", daten, kunde_da)

    # Ein zweites Mal ohne Anhalten (echte Geschwindigkeit), die Seite ohne Back-Forward-Cache (ein unload-Handler schließt ihn
    # aus) -- "Zurück" kommt dann aus dem HTTP-Cache.
    kennung = (await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="addEventListener('unload',()=>{})"))["identifier"]
    await tab.anmelden(seed["cookies"]["bea"])
    await _abmelden(tab, p, "Abmelden Büro (ohne Anhalten)", seite=seite, bereit=kunde_da, knoepfe=knoepfe, anhalten=False,
                    api=f"/api/customers/{kid}")
    await _zurueck(tab, "Abmelden Büro (ohne Back-Forward-Cache)", daten, kunde_da)
    await tab.cmd("Page.removeScriptToEvaluateOnNewDocument", identifier=kennung)


# -- Anmelden über die Seitenleiste ----------------------------------------------

async def _seitenleiste(tab, seed, p):
    kid = seed["kunde"]
    await tab.anmelden(seed["cookies"]["bea"])
    await tab.fenster(1400, 1000)
    await tab.im_netz_anhalten("*/api/auth/status")
    await tab.oeffnen(f"/customers/{kid}", "document.getElementById('appSidebarFoot')")
    await tab.warte_bis_im_netz_angehalten(1)
    for name in COOKIES:  # die Sitzung endet, während die Seite lädt
        await tab.cmd("Network.deleteCookies", name=name, url=tab.base)
    await tab.im_netz_fortsetzen()
    p.pruefe("Seitenleiste: 'Nicht angemeldet' mit Anmeldeformular", [
        await tab.warten("!!document.getElementById('appSidebarLoginForm')", 10),
        await tab.js("document.getElementById('appSidebarFoot').innerText.includes('Nicht angemeldet')")], [True, True])
    await tab.warte_auf_neu_geladene_liste()
    await tab.bild("seitenleiste_nicht_angemeldet")

    marke = len(tab.netz.verlauf)
    await _tippen(tab, "#appSidebarUsername", "bea")
    await _tippen(tab, "#appSidebarPassword", FALSCH)
    await _klick(tab, "#appSidebarLoginForm button")
    await tab.warten("document.getElementById('appSidebarLoginError').textContent.length>0", 10)
    p.pruefe("Seitenleiste: falsches Passwort -> Meldung, kein Cookie",
             [await tab.js("document.getElementById('appSidebarLoginError').textContent"), await _cookies(tab)], [MELDUNG_FALSCH, []])

    await tab.js("window.__vorAnmeldung=1")
    tab.fehler = []  # Fehler der ausgelieferten Seite ohne Sitzung (401 beim Nachladen) zählen hier nicht
    await _tippen(tab, "#appSidebarPassword", PASSWORT["bea"])
    await _enter(tab)  # im Formular: Enter schickt ab
    p.pruefe("Seitenleiste: richtiges Passwort -> Seite neu geladen, Kundenakte mit Daten", await tab.warten(
        f"window.__vorAnmeldung===undefined&&location.pathname==='/customers/{kid}'&&document.getElementById('lastName')?.value==='Geheim'",
        15), True)
    await tab.warte_auf_neu_geladene_liste()
    await tab.nachlesen()
    p.pruefe("Seitenleiste: zwei Anmeldungen gesendet (401, 200), Cookie gesetzt, Formular weg", [
        [(gesendet(e), e["status"]) for e in tab.netz.suche(r"/api/auth/login$", "POST", ab=marke)], await _cookies(tab),
        await tab.js("document.getElementById('appSidebarLoginForm')===null")], [[(True, 401), (True, 200)], ["dk_erp_auth"], True])
    p.pruefe("Seitenleiste: JS-Fehler", tab.fehler, [])


# -- Abmelden auf /mobil -----------------------------------------------------------

async def _abmelden_mobil(tab, seed, p):
    bereit = "document.getElementById('mobileHeaderLogout')&&document.readyState==='complete'"
    daten = "document.querySelector('.mobile-header-user')?.textContent.includes('Mia Monteurin')"
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await _abmelden(tab, p, "Abmelden Mobil", seite="/mobil", bereit=bereit, knoepfe=["#mobileHeaderLogout"], anhalten=True,
                    api="/api/field-view/today")
    await _zurueck(tab, "Abmelden Mobil", daten, bereit)

    await tab.anmelden({})  # unabhängig davon, wie das Abmelden ausging
    await tab.oeffnen("/login?next=%2Fmobil", "document.getElementById('u')")
    await _anmelden_formular(tab, "mia", PASSWORT["mia"], per_enter=False)
    p.pruefe("Mobil: Monteurin meldet sich an -> /mobil", await tab.warten(f"location.pathname==='/mobil'&&{bereit}", 15), True)
    await tab.bild("mobil_angemeldet")
    await tab.fenster(1400, 1000)


# -- Angriffe über next --------------------------------------------------------------

async def _angriffe_next(tab, seed, p):
    port = _freier_port()  # niemand hört dort: eine fremde Adresse, die den Rechner nicht verlässt
    fremd = f"127.0.0.1:{port}/fremd"
    for name, wert in (("absolute Adresse", f"http://{fremd}"), ("protokoll-relativ //", f"//{fremd}"),
                       ("Rückstrich /\\", f"/\\{fremd}")):
        await tab.anmelden({})
        await tab.oeffnen("/login?next=" + quote(wert, safe=""), "document.getElementById('u')")
        marke = len(tab.netz.verlauf)
        await _anmelden_formular(tab, "bea", PASSWORT["bea"])
        await tab.warten(f"location.href.includes({json.dumps(fremd)})||location.protocol==='chrome-error:'", 8, melden=False)
        await tab.nachlesen()
        fremde = [d["url"] for d in _dokumente(tab, marke) if not d["url"].startswith(tab.base + "/")]
        befund(f"Anmelden über das Formular mit next={name}: Weiterleitung auf eine fremde Adresse", bool(fremde),
               f"Dokument-Anfragen: {sorted(set(fremde)) or 'keine fremden'}")

    await tab.anmelden({})
    await tab.oeffnen("/login?next=" + quote("javascript:void(window.__dkXss=document.domain)", safe=""), "document.getElementById('u')")
    await _anmelden_formular(tab, "bea", PASSWORT["bea"])
    await tab.warten("window.__dkXss!==undefined", 5, melden=False)
    xss = await tab.js("window.__dkXss===undefined?null:String(window.__dkXss)")
    befund("Anmelden über das Formular mit next=javascript:…: das Skript läuft im ERP (mit frischer Sitzung)", xss is not None,
           f"window.__dkXss={xss!r}")

    # Angemeldet leitet /login selbst weiter (Server, _safe_next_target()) -- das ist geprüft, also Prüfungen.
    await tab.anmelden(seed["cookies"]["bea"])
    for wert in (f"//{fremd}", f"/%5C{fremd}", f"/%09/{fremd}", f"https:{fremd}"):
        marke = len(tab.netz.verlauf)
        await tab.cmd("Page.navigate", url=f"{tab.base}/login?next={wert}")
        for _ in range(50):  # bis die Navigation (samt Weiterleitungen) zu Ende ist
            await tab.nachlesen()
            if any(d["fertig"] or d["fehler"] for d in _dokumente(tab, marke)):
                break
        dokumente = _dokumente(tab, marke)
        p.pruefe(f"Angriff (angemeldet): /login?next={wert} bleibt im ERP",
                 [bool(dokumente), [d["url"] for d in dokumente if not d["url"].startswith(tab.base + "/")]], [True, []])


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=DIALOGE)
    await _formular(tab, seed, p)
    await _doppelklick(tab, seed, p)
    await _zwei_faktor(tab, seed, p)
    await _abmelden_buero(tab, seed, p)
    await _seitenleiste(tab, seed, p)
    await _abmelden_mobil(tab, seed, p)
    await _angriffe_next(tab, seed, p)
    luecken = [b for b in BEFUNDE if b[1]]
    print(f"BEFUNDE: {len(luecken)} Lücken bei {len(BEFUNDE)} Befund-Angriffen (gemeldet, nicht als Prüfung gezählt)", flush=True)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
