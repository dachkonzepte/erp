"""Gemeinsames Werkzeug für die CDP-Klicktests unter scripts/klicktest_*.py (seit 1.8.11).

Ein Klicktest prüft eine Seite so, wie ein Nutzer sie sieht: ein headless Chrome lädt die echte
Seite aus einer laufenden ERP-Instanz, führt ihr JavaScript aus und liest das Ergebnis aus dem
DOM. Gesteuert wird Chrome über das Chrome DevTools Protocol (CDP), ohne Playwright oder npm;
es reichen die Projekt-venv (Paket `websockets` kommt mit uvicorn[standard]) und ein
installiertes Chrome.

AUFRUF (aus dem Projektordner, in der Projekt-venv):

    .venv\\Scripts\\python.exe scripts\\klicktest_<name>.py [Optionen]

    --app-port N        Port der ERP-Instanz (Vorgabe 0 = freien Port wählen)
    --cdp-port N        Port für das DevTools-Protokoll (Vorgabe 0 = freien Port wählen)
    --arbeitsordner P   Ordner für Datenbank, Daten, Chrome-Profil, Logs und Screenshots
                        (Vorgabe: neuer Ordner unter %TEMP%\\erp-klicktest-*). Muss leer sein
                        oder fehlen.
    --chrome P          Pfad zu chrome.exe (Vorgabe: $CHROME, sonst die üblichen
                        Installationsorte von Chrome und Edge)
    --offen-lassen      Instanz und Chrome nach den Prüfungen weiterlaufen lassen (z. B. um im
                        eigenen Browser nachzusehen); die PIDs stehen in <arbeitsordner>\\pids.txt
                        und werden über `taskkill /PID <pid> /T /F` beendet, nicht über den Namen
    --wanduhr HH:MM     Instanz so starten, als wäre es heute HH:MM (Europe/Berlin) -- Gegenprobe für
                        Prüfungen, die von der Tageszeit abhängen. Ein Skript mit fester Uhr
                        (klicktest_main(..., uhr="10:00")) bleibt bei seiner Uhr.
    --zeitlimit SEK     nach SEK Sekunden abbrechen: eigene Prozesse (Befüllen, Instanz, Chrome) über ihre PID
                        beenden, Rückgabecode 3. Ohne Angabe kein Limit -- außer in einer Gegenprobe.

GEGENPROBE (seit 1.8.108): steht der Marker GEGENPROBE irgendwo unter app/ (Regel 24, eine Gegenprobe läuft), bricht
jeder Klicktest nach höchstens 2 min ab (ZEITLIMIT_GEGENPROBE, --zeitlimit kann es nur verkürzen) -- ein ausgehebelter
Schutz lässt eine Seite sonst oft im Kreis laufen oder auf eine Antwort warten, die nie kommt (am 14.10.2026 hing so
eine Gegenprobe über /login?next=…). Rückgabecode 3, die letzte Zeile nennt Grund und Fundstelle des Markers.

GLEICHZEITIG (seit 1.8.108): `scripts/klicktest_alle.py --gleichzeitig 4` lässt mehrere Klicktests zugleich laufen.
Ein Klicktest, dessen Prüfung an einer Zeitspanne hängt (ein Fenster, in dem etwas NICHT geschehen darf, wie
`warten("false", 1.0, melden=False)`; ein Zeitlimit über `window.__dkZeitlimit`; gedrosseltes Netz), setzt auf
Modulebene `ALLEIN = "<Grund>"` -- er läuft dann allein, unter Last würde er schwächer oder rot.
`tests/test_v413_testlauf_parallel.py` verlangt das für jedes solche Skript.

FESTE UHR (seit 1.8.36): `klicktest_main(befuellen, pruefen, uhr="10:00")` lässt die Uhr der Instanz
(app.berlin_time._utc_now, beim Befüllen und im Server) heute ab 10:00 Europe/Berlin laufen, egal
wann der Test startet. Pflicht für jeden Klicktest, der als Monteur /mobil öffnet: ab
MobileSettings.shift_end_time (Vorgabe 19:00) meldet /api/field-view/today ab, eine 403-Prüfung
danach sähe abends 401. Gespeicherte Zeitstempel (datetime.utcnow()) und die Uhr des Browsers
laufen weiter mit der echten Zeit -- seit 1.8.111 lässt sich der Browser mitnehmen: befuellen() gibt
`k.uhr_versatz_ms()` in den Seed, pruefen() ruft vor dem ersten Laden `tab.browser_uhr(versatz)`;
die Uhr des Browsers läuft dann um denselben Versatz weiter (Date und Date.now()).

Rückgabecode: 0 = alle Prüfungen wie erwartet, 1 = mindestens eine Abweichung,
2 = Instanz oder Chrome ließ sich nicht starten, 3 = Zeitlimit (--zeitlimit oder Gegenprobe).

WAS PASSIERT:

1. Der Arbeitsordner bekommt eine Wegwerf-SQLite (`erp.db`), einen eigenen `ERP_DATA_DIR`, einen
   zufälligen `ERP_SECRET_KEY` und die Markierung `.klicktest`. Nie die echte Datenbank
   (Regel 16): Das Befüllen bricht ab, wenn `DATABASE_URL` nicht in einen so markierten Ordner
   zeigt.
2. Das Klicktest-Skript wird in dieser Umgebung noch einmal mit `--nur-befuellen` aufgerufen.
   Das legt über `app.main` alle Tabellen an (`create_all()`, ERP_ENV=development), ruft die
   `befuellen(db, k)`-Funktion des Skripts auf und schreibt deren Ergebnis nach `seed.json`.
3. uvicorn startet auf `--app-port`, Chrome headless mit eigenem `--user-data-dir` im
   Arbeitsordner auf `--cdp-port`.
4. Die `pruefen(tab, seed, p)`-Funktion des Skripts läuft. Screenshots landen unter
   `<arbeitsordner>\\shots`, Server-Logs unter `server.out.log`/`server.err.log`.
5. Chrome und uvicorn werden über ihre eigene PID beendet (Regel 12: nie über den
   Prozessnamen, Tobias arbeitet parallel im eigenen Chrome).

EIN NEUES KLICKTEST-SKRIPT schreibt zwei Funktionen und übergibt sie `klicktest_main()`,
Vorlage: `scripts/klicktest_dashboard_monatswechsel.py` (kurz, festgehaltene Browser-Uhr) oder
`scripts/klicktest_zeitbuchungen_liste.py` (mehrere Seiten und Rollen):

    def befuellen(db, k):                 # läuft in der isolierten Umgebung
        from app.models import ...        # app erst hier importieren
        ...
        return {"cookies": {"buero": k.cookies(user)}, ...}   # landet als seed im Test

    async def pruefen(tab, seed, p):
        await tab.anmelden(seed["cookies"]["buero"])
        await tab.oeffnen("/pfad", "document.querySelector('#fertig')")
        p.pruefe("Bezeichnung", await tab.js("..."), "erwartet")
        p.pruefe("JS-Fehler", tab.fehler, [])

Zwei Fallen aus früheren Runden, hier bereits abgefangen: `Runtime.evaluate` liefert bei einem
JS-Fehler ohne Prüfung von `exceptionDetails` ein leeres Ergebnis statt eines Fehlers
(`Tab.js()` sammelt ihn in `tab.fehler`); und Seiten laden ihre Daten per fetch() nach, erst
eine Bereitschaftsbedingung (`Tab.oeffnen(pfad, bedingung)`) sagt, wann geprüft werden darf.

Eine dritte (seit 1.8.94): nach einer Aktion, die speichert und neu lädt, belegen weder ein Statustext (oft vor dem
Neuladen gesetzt) noch eine feste Pause, dass die Anzeige neu ist. Dafür
`await tab.warte_auf_neu_geladene_liste("…click()", "#liste")` -- wartet, bis keine Anfrage der Seite mehr läuft und die
Liste neu gezeichnet ist; ohne Aktion direkt nach `oeffnen()`, bevor geprüft wird, dass etwas NICHT erscheint.

ANTWORT ZURÜCKHALTEN (seit 1.8.95): `await tab.zurueckhalten(r"/api/task-columns$", "GET")` hält die nächste passende Antwort
zurück (der Server hat sie schon bearbeitet, die Seite bekommt sie erst bei `await tab.freigeben()`), mit `art="anfrage"` geht
die Anfrage erst dann hinaus. `warte_bis_gehalten()`, `gehalten()`, `warte_auf_ruhe()` (Ruhe außer den zurückgehaltenen) --
für Prüfungen, dass eine spät ankommende, ältere Antwort nichts überschreibt (Baustein _speichern.html); Vorlage
`scripts/klicktest_veraltete_antworten.py`.

NETZWERKPROTOKOLL (seit 1.8.97): jeder Tab zeichnet die Network-Ereignisse des Browsers je Anfrage auf (`tab.netz`, Klasse
Netzprotokoll): Adresse, Methode, Art, Start, gesendet (der Browser meldet requestWillBeSentExtraInfo: die Kopfzeilen gehen auf die
Leitung), Antwort-Kopf, fertig oder fehlgeschlagen (errorText). Scheitert etwas -- eine Prüfung (Pruefungen.pruefe), eine Seite wird
nicht bereit (oeffnen), ein Warte-Helfer bricht ab (warte_auf_neu_geladene_liste, warte_bis_gehalten, warte_auf_ruhe,
warte_bis_im_netz_angehalten, warten nach Ablauf der Zeit), der Lauf endet nicht wie erwartet --, druckt das Werkzeug die offenen
Anfragen, je eine Zeile:

        GET /api/customers/3/documents [Fetch]  seit 10:31:02.417 (12,3 s)  gesendet: nein  Antwort-Kopf: nein

dazu die fehlgeschlagenen mit errorText, die beim letzten Wechsel des Dokuments offen gebliebenen und den Anfragenzähler der Seite
(ANFRAGEN_ZAEHLER), wenn er von den offenen Fetch/XHR abweicht. Eine unveränderte Meldung kommt nur einmal. Die Ereignisse kommen
nur an, solange Tab.cmd() liest -- vor dem Drucken liest das Werkzeug deshalb nach (nicht in pruefe(), das synchron ist: dort steht
der Stand des letzten Lesens, meist der Prüfung selbst). Eine gewollte Pause ohne Meldung: `warten("false", 0.8, melden=False)`.
Im Klicktest selbst: `await tab.nachlesen()`, dann `tab.netz.suche(r"/api/auth/logout$", "POST")` -- die Einträge (dict) mit
gesendet()/antwort_kopf(), "fertig", "fehler", "ts_start"/"ts_antwort" (Zeitstempel des Browsers, vergleichbar).

IM NETZ ANHALTEN (seit 1.8.97): `await tab.im_netz_anhalten("*/api/auth/logout")` hält passende Anfragen an, BEVOR sie gesendet
werden (CDP Fetch, Stufe Request) -- der Server hat sie noch nicht, anders als bei zurueckhalten(); das Netzwerkprotokoll zeigt sie
offen, nicht gesendet, "im Netz angehalten". `warte_bis_im_netz_angehalten()`, `im_netz_fortsetzen()`. Vorlage
`scripts/klicktest_anmelden.py`.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = ".klicktest"
GEGENPROBE_MARKER = "GEGENPROBE"  # Regel 24, wie tests/test_v357_gegenprobe_marker.py
ZEITLIMIT_GEGENPROBE = 120  # Sekunden, seit 1.8.108
CODE_ZEITLIMIT = 3
CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Befüllen: läuft im Kindprozess mit der isolierten Umgebung
# ---------------------------------------------------------------------------

class Werkzeug:
    """Wird an befuellen(db, k) übergeben."""

    def __init__(self, db=None):
        self.db = db

    def cookies(self, user) -> dict:
        """Anmelde-Cookie für einen gespeicherten AppUser, ohne Login über die Oberfläche: seit 1.8.98 eine Sitzung auf dem Server
        (app/sitzungen.py), mit bestätigtem zweitem Faktor, damit auch ein Admin ohne zweiten Faktor durchkommt. Jeder Aufruf ist
        eine eigene Sitzung (wie zwei Geräte)."""
        from app import sitzungen
        from app.auth import COOKIE_NAME
        self.db.flush()
        return {COOKIE_NAME: sitzungen.neue_sitzung(self.db, user, zweiter_faktor=True)}

    def passwort(self, text: str = "x-Passwort-123") -> str:
        from app.auth import hash_password
        return hash_password(text)

    def uhr_versatz_ms(self) -> int:
        """Seit 1.8.111: um wie viele Millisekunden die Uhr der Instanz (FESTE UHR) der echten vorausgeht -- für
        Tab.browser_uhr(), damit der Browser dieselbe Zeit sieht. Ohne feste Uhr 0."""
        from app import berlin_time
        return int(round((berlin_time._utc_now().timestamp() - time.time()) * 1000))


def _befuellen_im_kindprozess(befuellen, ziel: Path) -> None:
    url = os.environ.get("DATABASE_URL", "")
    db_file = Path(url.removeprefix("sqlite:///")) if url.startswith("sqlite:///") else None
    if db_file is None or not (db_file.parent / MARKER).exists():
        raise SystemExit(f"Abbruch (Regel 16): DATABASE_URL zeigt nicht in einen Klicktest-Arbeitsordner: {url!r}")
    sys.path.insert(0, str(ROOT))
    _uhr_einsetzen()
    import app.main  # noqa: F401 -- create_all() auf der Wegwerf-Datenbank
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        seed = befuellen(db, Werkzeug(db))
        db.commit()
    finally:
        db.close()
    ziel.write_text(json.dumps(seed, default=str, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------------
# CDP
# ---------------------------------------------------------------------------

# Seit 1.8.94: zählt die Anfragen der Seite (fetch und XMLHttpRequest) für Tab.warte_auf_neu_geladene_liste() -- in jedes neu
# geladene Dokument eingesetzt (_lauf()). ruhigSeit: Zeitpunkt (performance.now()), an dem zuletzt eine Anfrage fertig wurde.
ANFRAGEN_ZAEHLER = """(()=>{if(window.__dkAnfragen)return;
const z=window.__dkAnfragen={gestartet:0,offen:0,ruhigSeit:performance.now()};
const fertig=()=>{z.offen--;z.ruhigSeit=performance.now()};
const f=window.fetch;
window.fetch=function(...a){z.gestartet++;z.offen++;let p;try{p=f.apply(this,a)}catch(e){fertig();throw e}p.then(fertig,fertig);return p};
const s=XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.send=function(...a){z.gestartet++;z.offen++;this.addEventListener('loadend',fertig,{once:true});return s.apply(this,a)};
})()"""


# Seit 1.8.95: hält gezielt eine Antwort (oder eine Anfrage) der Seite zurück -- für Klicktests, die zeigen, dass eine spät
# ankommende, ältere Antwort nichts überschreibt (_speichern.html). In jedes Dokument VOR dem Anfragenzähler eingesetzt (_lauf()),
# damit der Zähler eine zurückgehaltene Antwort als unterwegs zählt. Regel: {muster (RegExp-Quelltext auf die URL), methode,
# anzahl, art}; art "antwort": die Anfrage geht sofort hinaus, der Server bearbeitet sie, die Seite bekommt die Antwort erst bei
# freigeben(); art "anfrage": die Anfrage geht erst bei freigeben() hinaus. gehalten: je Fall {url, methode, art, beantwortet}.
# Seit 1.8.111: versetzte, weiterlaufende Uhr des Browsers (Tab.browser_uhr()) -- new Date() ohne Argument und Date.now() um %d ms.
BROWSER_UHR = """(()=>{if(window.__dkUhrVersatz!==undefined)return;const V=%d;window.__dkUhrVersatz=V;const Echt=Date;
globalThis.Date=class extends Echt{constructor(...a){super(...(a.length?a:[Echt.now()+V]))}static now(){return Echt.now()+V}};})();"""

ANTWORT_RUECKHALT = """(()=>{if(window.__dkRueckhalt)return;
const R=window.__dkRueckhalt={regeln:[],gehalten:[],freigegeben:0};
const f=window.fetch;
window.fetch=function(input,init){
  const url=typeof input==='string'?input:((input&&input.url)||String(input));
  const methode=String((init&&init.method)||(input&&input.method)||'GET').toUpperCase();
  const r=R.regeln.find(x=>x.anzahl>0&&new RegExp(x.muster).test(url)&&(!x.methode||x.methode===methode));
  if(!r)return f.apply(this,arguments);
  r.anzahl--;
  const self=this,args=arguments,fall={url,methode,art:r.art,beantwortet:false};
  return new Promise((ok,fehler)=>{
    if(r.art==='anfrage'){fall.los=()=>{const p=f.apply(self,args);p.then(()=>{fall.beantwortet=true},()=>{fall.beantwortet=true});p.then(ok,fehler)}}
    else{const p=f.apply(self,args);p.then(()=>{fall.beantwortet=true},()=>{fall.beantwortet=true});fall.los=()=>p.then(ok,fehler)}
    R.gehalten.push(fall);
  });
};
R.freigeben=()=>{const fall=R.gehalten.shift();if(!fall)return false;R.freigegeben++;fall.los();return true};
R.stand=()=>R.gehalten.map(x=>({url:x.url,methode:x.methode,art:x.art,beantwortet:x.beantwortet}));
})()"""


def neu_geladen_bedingung(vorher: int | None, mit_liste: bool, ruhe: float) -> str:
    """JS-Bedingung für Tab.warte_auf_neu_geladene_liste() (seit 1.8.94): seit dem Stand vorher (None: ohne Aktion) mindestens
    eine Anfrage gestartet, keine mehr unterwegs, seit ruhe Sekunden keine fertig geworden; mit_liste: keins der vorher
    gemerkten Listenelemente hängt noch im Dokument. tests/test_v397_klicktest_helfer.py führt sie in node aus."""
    teile = ["!!z"]
    if vorher is not None:
        teile.append(f"z.gestartet>{int(vorher)}")
    teile += ["z.offen===0", f"performance.now()-z.ruhigSeit>={int(ruhe * 1000)}"]
    if mit_liste:
        teile.append("(window.__dkAlteListe||[]).every(n=>!n.isConnected)")
    return "(()=>{const z=window.__dkAnfragen;return " + "&&".join(teile) + "})()"


# ---------------------------------------------------------------------------
# Netzwerkprotokoll (seit 1.8.97)
# ---------------------------------------------------------------------------

NETZ_EREIGNISSE = frozenset({
    "Network.requestWillBeSent", "Network.requestWillBeSentExtraInfo", "Network.responseReceived",
    "Network.responseReceivedExtraInfo", "Network.requestServedFromCache", "Network.loadingFinished", "Network.loadingFailed",
    "Fetch.requestPaused", "Page.frameNavigated",
})
NETZ_ZEILEN = 8  # höchstens so viele Anfragen je Abschnitt eines Berichts, der Rest als "… und N weitere"

# Stand des Anfragenzählers der Seite (ANFRAGEN_ZAEHLER) samt zurückgehaltener Antworten (ANTWORT_RUECKHALT), für den Bericht.
SEITE_STAND = ("(()=>{const z=window.__dkAnfragen,R=window.__dkRueckhalt;"
               "return z?{offen:z.offen,gestartet:z.gestartet,gehalten:R?R.gehalten.length:0}:null})()")


def _uhrzeit(wall: float | None) -> str:
    if wall is None:
        return "?"
    return time.strftime("%H:%M:%S", time.localtime(wall)) + f".{int(round((wall % 1) * 1000)) % 1000:03d}"


def _sekunden(wert: float) -> str:
    return f"{max(wert, 0):.1f}".replace(".", ",") + " s"


def _beendet(e: dict) -> bool:
    return e["fertig"] or e["fehler"] is not None


def gesendet(e: dict) -> bool:
    """Ob die Anfrage (in ihrem letzten Schritt, nach einer Weiterleitung der neue) auf die Leitung gegangen ist: der Browser hat
    requestWillBeSentExtraInfo gemeldet oder einen Antwort-Kopf. Aus dem Cache: nein."""
    if e["cache"]:
        return False
    schritte = max(e["schritte"], 1)
    return e["gesendet_n"] >= schritte or e["kopf_n"] >= schritte or e["antwort"]


def antwort_kopf(e: dict) -> bool:
    return e["antwort"] or e["kopf_n"] >= max(e["schritte"], 1)


class Netzprotokoll:
    """Seit 1.8.97: die Network-Ereignisse eines Tabs je Anfrage (requestId). Tab.cmd() reicht jedes Ereignis aus NETZ_EREIGNISSE an
    ereignis() weiter -- ein Ereignis kommt also nur an, solange cmd() liest.

    Gesendet (Festlegung 1.8.97): für die Anfrage kam requestWillBeSentExtraInfo (oder schon ein Antwort-Kopf). Chrome meldet es
    aus dem Netzwerkdienst mit den Kopfzeilen, wie sie auf die Leitung gehen (ohne es zeigen die DevTools "Provisional headers"),
    je Schritt einer Weiterleitung einmal, in beliebiger Reihenfolge zu requestWillBeSent. requestWillBeSent allein heißt nur "die
    Seite will senden": es kommt auch für eine Anfrage, die auf eine freie Verbindung wartet (höchstens sechs je Server), die im
    Netz angehalten ist (Tab.im_netz_anhalten()) oder die der Browser vor dem Senden abbricht. Aus dem Cache bedient: nicht gesendet.

    Wechselt das Hauptdokument (Page.frameNavigated ohne parentId, neuer loaderId), gehören die offenen und fehlgeschlagenen
    Anfragen des alten Dokuments bis zum nächsten Wechsel zu "beim Wechsel offen" bzw. "fehlgeschlagen" -- ein Browser meldet für
    eine Anfrage, die mit ihrem Dokument verschwindet, nicht immer ein Ende. Danach erscheinen sie nicht mehr; verlauf behält alles."""

    def __init__(self, basis: str = ""):
        self.basis = basis.rstrip("/")
        self.verlauf: list[dict] = []           # jede Anfrage, in der Reihenfolge ihres ersten Ereignisses
        self._nach_id: dict[str, dict] = {}
        self._aktuell: dict[str, dict] = {}     # Anfragen des aktuellen Hauptdokuments
        self._alt: list[dict] = []              # beim letzten Wechsel offene oder fehlgeschlagene des alten Dokuments
        self.dokument: str | None = None        # loaderId des Hauptdokuments
        self.wechsel: dict | None = None        # letzter Wechsel: {"url", "zeit"}
        self.angehalten: dict[str, str] = {}    # Fetch-requestId -> requestId der im Netz angehaltenen Anfragen
        self._gemeldet: tuple | None = None

    def _eintrag(self, rid: str, jetzt: float) -> dict:
        e = self._nach_id.get(rid)
        if e is None:
            e = {"id": rid, "url": None, "methode": None, "art": None, "loader": None, "start": None, "ts_start": None,
                 "erstes": jetzt, "schritte": 0, "gesendet_n": 0, "gesendet_um": None, "kopf_n": 0, "antwort": False,
                 "status": None, "ts_antwort": None, "cache": False, "fertig": False, "fehler": None, "abgebrochen": False,
                 "ts_ende": None, "angehalten": False}
            self._nach_id[rid] = e
            self._aktuell[rid] = e
            self.verlauf.append(e)
        return e

    def ereignis(self, methode: str, params: dict, jetzt: float | None = None) -> None:
        jetzt = time.time() if jetzt is None else jetzt
        if methode == "Page.frameNavigated":
            self._dokumentwechsel(params.get("frame") or {}, jetzt)
            return
        if methode == "Fetch.requestPaused":
            rid = params.get("networkId") or params["requestId"]
            e = self._eintrag(rid, jetzt)
            anfrage = params.get("request") or {}
            e["url"] = e["url"] or anfrage.get("url")
            e["methode"] = e["methode"] or anfrage.get("method")
            e["start"] = e["start"] or jetzt
            e["angehalten"] = True
            self.angehalten[params["requestId"]] = rid
            return
        rid = params.get("requestId")
        if rid is None:
            return
        e = self._eintrag(rid, jetzt)
        if methode == "Network.requestWillBeSent":
            anfrage = params.get("request") or {}
            e["schritte"] += 1
            e["url"], e["methode"] = anfrage.get("url"), anfrage.get("method")
            e["art"] = params.get("type") or e["art"]
            e["loader"] = params.get("loaderId") or e["loader"]
            if e["start"] is None or e["ts_start"] is None:
                e["start"] = params.get("wallTime") or e["start"] or jetzt
                e["ts_start"] = params.get("timestamp")
            if self.dokument is not None and e["loader"] == self.dokument and rid not in self._aktuell:
                self._aktuell[rid] = e
        elif methode == "Network.requestWillBeSentExtraInfo":
            e["gesendet_n"] += 1
            e["gesendet_um"] = jetzt
        elif methode == "Network.responseReceivedExtraInfo":
            e["kopf_n"] += 1
            e["status"] = e["status"] or params.get("statusCode")
        elif methode == "Network.responseReceived":
            antwort = params.get("response") or {}
            e["antwort"] = True
            e["status"] = antwort.get("status", e["status"])
            e["ts_antwort"] = params.get("timestamp")
            if antwort.get("fromDiskCache") or antwort.get("fromPrefetchCache") or antwort.get("fromServiceWorker"):
                e["cache"] = True
        elif methode == "Network.requestServedFromCache":
            e["cache"] = True
        elif methode == "Network.loadingFinished":
            e["fertig"], e["ts_ende"] = True, params.get("timestamp")
        elif methode == "Network.loadingFailed":
            e["fehler"] = params.get("errorText") or params.get("blockedReason") or "?"
            e["abgebrochen"] = bool(params.get("canceled"))
            e["ts_ende"] = params.get("timestamp")
        if _beendet(e) and e["angehalten"]:
            self.fortgesetzt(next((f for f, r in self.angehalten.items() if r == rid), None), rid)

    def _dokumentwechsel(self, rahmen: dict, jetzt: float) -> None:
        neu = rahmen.get("loaderId")
        if rahmen.get("parentId") or not neu or neu == self.dokument:
            return
        bleibt, alt = {}, []
        for rid, e in self._aktuell.items():
            if e["loader"] == neu:
                bleibt[rid] = e
            elif e["url"] is not None and (not _beendet(e) or e["fehler"] is not None):
                alt.append(e)
        self.dokument, self._aktuell, self._alt = neu, bleibt, alt
        self.wechsel = {"url": rahmen.get("url"), "zeit": jetzt}

    def fortgesetzt(self, fetch_id: str | None, rid: str | None = None) -> None:
        """Eine im Netz angehaltene Anfrage geht weiter (oder ist beendet)."""
        rid = self.angehalten.pop(fetch_id, None) if fetch_id is not None else rid
        if rid is not None and rid in self._nach_id:
            self._nach_id[rid]["angehalten"] = False

    # -- Abfragen -------------------------------------------------------------

    def suche(self, muster: str, methode: str | None = None, *, ab: int = 0) -> list[dict]:
        """Einträge aus dem Verlauf (ab Index ab, z. B. len(netz.verlauf) vor einer Aktion), deren URL auf den regulären Ausdruck
        muster passt und deren Methode methode ist (None: jede)."""
        return [e for e in self.verlauf[ab:] if e["url"] and re.search(muster, e["url"])
                and (methode is None or e["methode"] == methode.upper())]

    def offen(self) -> list[dict]:
        return [e for e in self._aktuell.values() if e["url"] is not None and not _beendet(e)]

    def beim_wechsel_offen(self) -> list[dict]:
        return [e for e in self._alt if not _beendet(e)]

    def fehlgeschlagen(self) -> list[dict]:
        return [e for e in (*self._aktuell.values(), *self._alt) if e["fehler"] is not None]

    # -- Bericht --------------------------------------------------------------

    def _adresse(self, url: str | None) -> str:
        if not url:
            return "?"
        if self.basis and url.startswith(self.basis + "/"):
            url = url[len(self.basis):]
        return url if len(url) <= 90 else url[:89] + "…"

    def _zeile(self, e: dict, jetzt: float, fehlgeschlagen: bool) -> str:
        was = f"{e['methode'] or '?'} {self._adresse(e['url'])}" + (f" [{e['art']}]" if e["art"] else "")
        if fehlgeschlagen:
            wann = f"{_uhrzeit(e['start'])}  {e['fehler']}" + (" (abgebrochen)" if e["abgebrochen"] else "")
        else:
            wann = f"seit {_uhrzeit(e['start'])} ({_sekunden(jetzt - (e['start'] or jetzt))})"
        zeile = (f"      {was}  {wann}  gesendet: {'ja' if gesendet(e) else ('nein (Cache)' if e['cache'] else 'nein')}"
                 f"  Antwort-Kopf: {'ja' if antwort_kopf(e) else 'nein'}")
        return zeile + ("  im Netz angehalten" if e["angehalten"] else "")

    def _liste(self, eintraege: list[dict], jetzt: float, fehlgeschlagen: bool = False) -> list[str]:
        zeilen = [self._zeile(e, jetzt, fehlgeschlagen) for e in eintraege[:NETZ_ZEILEN]]
        if len(eintraege) > NETZ_ZEILEN:
            zeilen.append(f"      … und {len(eintraege) - NETZ_ZEILEN} weitere")
        return zeilen

    def _seite_weicht_ab(self, seite: dict | None) -> str | None:
        if not seite:
            return None
        im_netz = sum(1 for e in self.offen() if e["art"] in ("Fetch", "XHR"))
        if seite.get("offen") == im_netz:
            return None
        gehalten = seite.get("gehalten") or 0
        return (f"    Seite: Anfragenzähler offen {seite.get('offen')}" + (f", davon zurückgehalten {gehalten}" if gehalten else "")
                + f" -- im Netz offen (Fetch/XHR): {im_netz}")

    def bericht(self, jetzt: float | None = None, seite: dict | None = None) -> list[str]:
        """Zeilen: offene Anfragen des aktuellen Dokuments, die beim letzten Wechsel offen gebliebenen, die fehlgeschlagenen (beider
        Dokumente) mit errorText; dazu der Anfragenzähler der Seite (seite: SEITE_STAND), wenn er abweicht."""
        jetzt = time.time() if jetzt is None else jetzt
        offen, alt, fehl = self.offen(), self.beim_wechsel_offen(), self.fehlgeschlagen()
        zeilen = [f"    Netzwerk: {len(offen)} offen" if offen else "    Netzwerk: keine offenen Anfragen"]
        zeilen += self._liste(offen, jetzt)
        if alt:
            zeilen.append(f"    Netzwerk: beim Wechsel auf {self._adresse((self.wechsel or {}).get('url'))} offen geblieben: {len(alt)}")
            zeilen += self._liste(alt, jetzt)
        if fehl:
            zeilen.append(f"    Netzwerk: fehlgeschlagen: {len(fehl)}")
            zeilen += self._liste(fehl, jetzt, fehlgeschlagen=True)
        abweichung = self._seite_weicht_ab(seite)
        return zeilen + ([abweichung] if abweichung else [])

    def melden(self, jetzt: float | None = None, seite: dict | None = None, *, immer: bool = False) -> list[str]:
        """Wie bericht(); hat sich seit der letzten Meldung nichts geändert (dieselben Anfragen im selben Zustand), nur eine Zeile
        -- ein Klicktest, dessen Seite nicht lädt, scheitert oft an vielen Prüfungen nacheinander."""
        offen, alt, fehl = self.offen(), self.beim_wechsel_offen(), self.fehlgeschlagen()
        schluessel = (tuple((e["id"], gesendet(e), antwort_kopf(e), e["fehler"], e["angehalten"]) for e in (*offen, *alt, *fehl)),
                      self._seite_weicht_ab(seite))
        if not immer and schluessel == self._gemeldet:
            return [f"    Netzwerk: unverändert seit der letzten Meldung ({len(offen)} offen"
                    + (f", {len(alt)} beim Wechsel offen geblieben" if alt else "")
                    + (f", {len(fehl)} fehlgeschlagen" if fehl else "") + ")"]
        self._gemeldet = schluessel
        return self.bericht(jetzt, seite)


class Tab:
    """Eine Browser-Seite. fehler sammelt JS-Ausnahmen und console.error seit dem letzten oeffnen(); netz (seit 1.8.97) zeichnet
    die Netzwerk-Ereignisse auf (Netzprotokoll); downloads (seit 1.8.101) die Downloads, die der Tab beginnt (Page.downloadWillBegin --
    wohin sie gehen, legt ein Klicktest mit Page.setDownloadBehavior fest)."""

    def __init__(self, ws, base_url: str, shots: Path, cdp_port: int | None = None):
        self.ws, self.base, self.shots = ws, base_url, shots
        self.cdp_port = cdp_port  # seit 1.8.103, für zweiter_tab()
        self.n = 0
        self.fehler: list[str] = []
        self.nicht_geladen: list[str] = []
        self.netz = Netzprotokoll(base_url)
        self.downloads: list[dict] = []  # seit 1.8.101: jeder Download, den der Tab beginnt ({"url", "name"})

    async def cmd(self, method: str, **params):
        self.n += 1
        my = self.n
        await self.ws.send(json.dumps({"id": my, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("method") in NETZ_EREIGNISSE:
                self.netz.ereignis(msg["method"], msg.get("params") or {})
            if msg.get("method") == "Runtime.exceptionThrown":
                d = msg["params"]["exceptionDetails"]
                self.fehler.append((d.get("exception", {}).get("description") or d.get("text", "?"))[:300])
            if msg.get("method") == "Runtime.consoleAPICalled" and msg["params"]["type"] == "error":
                self.fehler.append(" ".join(str(a.get("value", a.get("description", ""))) for a in msg["params"]["args"])[:300])
            if msg.get("method") == "Page.downloadWillBegin":
                self.downloads.append({"url": msg["params"].get("url"), "name": msg["params"].get("suggestedFilename")})
            if msg.get("method") == "Page.javascriptDialogOpening":
                await self._dialog(msg.get("params") or {})
            if msg.get("id") == my:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg["result"]

    async def _dialog(self, params: dict) -> None:
        """Seit 1.8.98: ein Dialog des Browsers (vor allem "Seite verlassen?" der Warnung beim Verlassen) hielt jeden weiteren
        CDP-Befehl an -- der Klicktest hing bis zum Zeitlimit von klicktest_alle.py (15 min). Jetzt: melden (die Prüfung zählt als
        nicht wie erwartet, samt Netzprotokoll: welches Speichern noch lief), den Dialog annehmen und weitermachen. alert()/confirm()
        leiten die Klicktests in der Seite um; ein echter Dialog ist deshalb immer ein Befund."""
        art = params.get("type", "?")
        self.nicht_geladen.append(f"Dialog {art} ({(params.get('message') or '')[:60]!r}) auf {params.get('url', '?')}")
        print(f"XX  Dialog des Browsers ({art}) auf {params.get('url', '?')} -- angenommen, der Test läuft weiter", flush=True)
        for zeile in self.netz.melden(immer=True):
            print(zeile, flush=True)
        self.n += 1
        await self.ws.send(json.dumps({"id": self.n, "method": "Page.handleJavaScriptDialog", "params": {"accept": True}}))

    async def js(self, expr: str):
        """Wertet expr in der Seite aus (Promises werden abgewartet). Ein Fehler landet in
        self.fehler und ergibt None -- ohne die Prüfung von exceptionDetails sähe er wie ein
        leeres, aber erfolgreiches Ergebnis aus."""
        res = await self.cmd("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in res:
            d = res["exceptionDetails"]
            self.fehler.append((d.get("exception", {}).get("description") or d.get("text", "?"))[:300])
            return None
        return res["result"].get("value")

    @contextlib.asynccontextmanager
    async def zweiter_tab(self):
        """Seit 1.8.103: ein weiterer Tab desselben Browsers (dieselben Cookies) -- z. B. "in einem neuen Tab anmelden", während die
        Seite dieses Tabs offen bleibt. Wird am Ende geschlossen; Ereignisse dieses Tabs liest erst sein nächster Befehl."""
        import websockets

        anfrage = urllib.request.Request(f"http://127.0.0.1:{self.cdp_port}/json/new?about:blank", method="PUT")
        ziel = json.load(urllib.request.urlopen(anfrage))
        try:
            async with websockets.connect(ziel["webSocketDebuggerUrl"], max_size=64_000_000) as ws:
                tab = Tab(ws, self.base, self.shots, self.cdp_port)
                for domain in ("Page", "Runtime", "Network"):
                    await tab.cmd(f"{domain}.enable")
                await tab.fenster(1400, 1000)
                yield tab
        finally:
            urllib.request.urlopen(f"http://127.0.0.1:{self.cdp_port}/json/close/{ziel['id']}").read()

    async def anmelden(self, cookies: dict) -> None:
        await self.cmd("Network.clearBrowserCookies")
        for name, value in cookies.items():
            await self.cmd("Network.setCookie", name=name, value=value, url=self.base)

    async def browser_uhr(self, versatz_ms: int) -> None:
        """Seit 1.8.111: die Uhr des Browsers um versatz_ms versetzen (sie läuft weiter) -- für jedes danach geladene Dokument. Mit
        Werkzeug.uhr_versatz_ms() aus befuellen() sieht der Browser die Zeit der Instanz (FESTE UHR oben)."""
        await self.cmd("Page.addScriptToEvaluateOnNewDocument", source=BROWSER_UHR % int(versatz_ms))

    async def fenster(self, breite: int, hoehe: int, mobil: bool = False) -> None:
        await self.cmd("Emulation.setDeviceMetricsOverride", width=breite, height=hoehe,
                       deviceScaleFactor=2 if mobil else 1, mobile=mobil)

    async def oeffnen(self, pfad: str, bereit: str, timeout: float = 30) -> bool:
        """Lädt pfad und wartet, bis der JS-Ausdruck bereit wahr ist (Seiten laden ihre Daten per
        fetch() nach). Setzt self.fehler zurück."""
        self.fehler = []
        await self.cmd("Page.navigate", url=self.base + pfad)
        ende = time.monotonic() + timeout
        while time.monotonic() < ende:
            await asyncio.sleep(0.1)
            try:
                if await self.js(f"(()=>{{try{{return !!({bereit})}}catch(e){{return false}}}})()"):
                    await asyncio.sleep(0.3)
                    return True
            except RuntimeError:
                pass  # Navigation noch nicht fertig
        self.nicht_geladen.append(pfad)
        print(f"XX  {pfad}: Seite nicht bereit ({bereit[:80]})")
        await self.netz_melden()
        return False

    async def nachlesen(self) -> dict | None:
        """Seit 1.8.97: holt die inzwischen eingetroffenen Ereignisse ab -- sie kommen nur an, solange cmd() liest -- über einen
        günstigen Befehl nach einer kurzen Pause (Ereignisse aus dem Netzwerkdienst können der Antwort der Seite nachlaufen).
        Rückgabe: Stand des Anfragenzählers der Seite (SEITE_STAND) oder None. Füllt nie self.fehler."""
        await asyncio.sleep(0.2)
        try:
            res = await self.cmd("Runtime.evaluate", expression=SEITE_STAND, returnByValue=True)
        except Exception:  # Seite mitten im Wechsel, Verbindung weg: dann bleibt der Stand des letzten Lesens
            return None
        if "exceptionDetails" in res:
            return None
        return (res.get("result") or {}).get("value")

    async def netz_melden(self, anlass: str | None = None, *, immer: bool = False) -> list[str]:
        """Seit 1.8.97: liest nach und druckt die offenen Anfragen (Netzprotokoll.melden()); anlass als eigene Zeile davor."""
        seite = await self.nachlesen()
        zeilen = ([anlass] if anlass else []) + self.netz.melden(seite=seite, immer=immer)
        print("\n".join(zeilen), flush=True)
        return zeilen

    async def im_netz_anhalten(self, muster: str) -> None:
        """Seit 1.8.97: hält jede Anfrage, deren URL auf das Muster passt (CDP-Muster mit * und ?, z. B. "*/api/auth/logout"), im
        Netz an, bevor sie gesendet wird (Fetch-Domäne, Stufe "Request"), bis im_netz_fortsetzen(). Anders als zurueckhalten()
        (in der Seite, der Server hat die Anfrage schon) hat der Server sie dann noch nicht. Eine angehaltene Anfrage, deren
        Dokument verschwindet, bricht der Browser ab."""
        await self.cmd("Fetch.enable", patterns=[{"urlPattern": muster, "requestStage": "Request"}])

    async def warte_bis_im_netz_angehalten(self, anzahl: int = 1, *, timeout: float = 15) -> bool:
        ende = time.monotonic() + timeout
        while time.monotonic() < ende:
            if len(self.netz.angehalten) >= anzahl:
                return True
            await asyncio.sleep(0.05)
            try:
                await self.cmd("Runtime.evaluate", expression="0")  # liest die Ereignisse ab
            except RuntimeError:
                pass
        self.nicht_geladen.append(f"nicht im Netz angehalten: {anzahl}")
        await self.netz_melden(f"XX  nicht im Netz angehalten ({anzahl})")
        return False

    async def im_netz_fortsetzen(self) -> int:
        """Setzt die im Netz angehaltenen Anfragen fort und hält nichts mehr an; Rückgabe: wie viele weitergingen (eine, die der
        Browser inzwischen abgebrochen hat, nicht)."""
        weiter = 0
        for fetch_id in list(self.netz.angehalten):
            try:
                await self.cmd("Fetch.continueRequest", requestId=fetch_id)
                weiter += 1
            except RuntimeError:
                pass  # schon abgebrochen (Dokument gewechselt)
            self.netz.fortgesetzt(fetch_id)
        await self.cmd("Fetch.disable")
        return weiter

    async def warte_auf_neu_geladene_liste(self, aktion: str | None = None, liste: str | None = None, *, timeout: float = 15,
                                           ruhe: float = 0.3) -> bool:
        """Seit 1.8.94: löst die JS-Aktion aus (z. B. einen Klick) und wartet, bis die Seite danach neu geladen hat -- erst dann
        stimmt, was sie nach einem Speichern oder Buchen per fetch nachlädt und neu zeichnet (Liste, Kennzeichen, Hinweis).
        Ein Statustext ist dafür kein Beleg: viele Seiten setzen ihn vor dem Neuladen ("3 Entwürfe angelegt.", dann
        `await reload()`), und eine sofortige Änderung (Kachel markiert) belegt nur die eine Antwort, nicht eine zweite, die
        noch unterwegs ist.

        Neu geladen heißt: seit der Aktion mindestens eine Anfrage der Seite gestartet (fetch oder XMLHttpRequest, gezählt
        von ANFRAGEN_ZAEHLER), keine mehr unterwegs und `ruhe` Sekunden keine neue -- so liegen auch Ketten wie Speichern ->
        reload() und deren Zeichnen dahinter. Mit `liste` (CSS-Selektor) zusätzlich: keins der Elemente, die vor der Aktion
        darin standen, hängt noch im Dokument (die Liste ist neu gezeichnet). Ohne `aktion` (nach `oeffnen()`): nur warten, bis
        die Seite nichts mehr nachlädt -- vor einer Prüfung, dass etwas NICHT erscheint. Eine Anfrage, die die Seite erst nach
        der Ruhezeit startet (entprellte Eingabe), ist nicht erfasst. Zeitüberschreitung: Meldung und False, der Test zählt
        dann als nicht wie erwartet (nicht_geladen)."""
        vorher = await self.js(
            "(()=>{const z=window.__dkAnfragen;"
            + (f"window.__dkAlteListe=[...document.querySelectorAll({json.dumps(liste)})].flatMap(l=>[...l.children]);"
               if liste else "")
            + "return z?z.gestartet:null})()")
        if vorher is None:
            self.nicht_geladen.append(f"Anfragenzähler fehlt ({liste or aktion or 'Seite'})")
            print("XX  Anfragenzähler fehlt -- Seite nicht über oeffnen() geladen?")
            await self.netz_melden()
            return False
        if aktion is not None:
            await self.js(aktion)
        if await self.warten(neu_geladen_bedingung(vorher if aktion is not None else None, liste is not None, ruhe), timeout,
                             melden=False):
            return True
        stand = await self.js("JSON.stringify(window.__dkAnfragen)")
        self.nicht_geladen.append(f"nicht neu geladen: {liste or aktion or 'Seite'}")
        print(f"XX  nicht neu geladen ({liste or aktion or 'Seite'}), Anfragen {stand}")
        await self.netz_melden()
        return False

    async def zurueckhalten(self, muster: str, methode: str | None = None, *, anzahl: int = 1, art: str = "antwort") -> None:
        """Seit 1.8.95: hält die nächsten `anzahl` Anfragen des geladenen Dokuments zurück, deren URL auf `muster` passt
        (regulärer Ausdruck, z. B. r"/api/task-columns$") und deren Methode `methode` ist (None: jede). art "antwort": die Anfrage
        geht sofort hinaus und der Server bearbeitet sie, die Seite bekommt die Antwort erst bei freigeben() -- eine spät
        ankommende Antwort; art "anfrage": sie geht erst bei freigeben() hinaus (ANTWORT_RUECKHALT)."""
        regel = {"muster": muster, "methode": methode.upper() if methode else None, "anzahl": anzahl, "art": art}
        await self.js(f"window.__dkRueckhalt.regeln.push({json.dumps(regel)})")

    async def gehalten(self) -> list:
        """Die zurückgehaltenen Fälle: [{url, methode, art, beantwortet}] (beantwortet: der Server hat geantwortet)."""
        return await self.js("window.__dkRueckhalt.stand()") or []

    async def warte_bis_gehalten(self, anzahl: int = 1, *, beantwortet: bool = True, timeout: float = 15) -> bool:
        """Wartet, bis `anzahl` Fälle zurückgehalten sind (mit beantwortet: und der Server auf sie geantwortet hat)."""
        teil = "s.slice(0,%d).every(x=>x.beantwortet)" % anzahl if beantwortet else "true"
        if await self.warten(f"(()=>{{const s=window.__dkRueckhalt.stand();return s.length>={anzahl}&&{teil}}})()", timeout,
                             melden=False):
            return True
        self.nicht_geladen.append(f"nicht zurückgehalten: {anzahl} Fall/Fälle")
        print(f"XX  nicht zurückgehalten ({anzahl}), Stand {await self.gehalten()}")
        await self.netz_melden()
        return False

    async def freigeben(self) -> bool:
        """Gibt den ältesten zurückgehaltenen Fall frei (Antwort an die Seite bzw. Anfrage hinaus)."""
        return bool(await self.js("window.__dkRueckhalt.freigeben()"))

    async def warte_auf_ruhe(self, *, ruhe: float = 0.3, timeout: float = 15) -> bool:
        """Wartet, bis außer den zurückgehaltenen Fällen keine Anfrage der Seite mehr unterwegs ist und `ruhe` Sekunden nichts
        fertig wurde (der Anfragenzähler zählt eine zurückgehaltene Antwort als unterwegs)."""
        bedingung = ("(()=>{const z=window.__dkAnfragen,R=window.__dkRueckhalt;return !!z&&z.offen===R.gehalten.length"
                     f"&&performance.now()-z.ruhigSeit>={int(ruhe * 1000)}}})()")
        if await self.warten(bedingung, timeout, melden=False):
            return True
        self.nicht_geladen.append("keine Ruhe außer den zurückgehaltenen")
        print(f"XX  keine Ruhe, Anfragen {await self.js('JSON.stringify(window.__dkAnfragen)')}, gehalten {await self.gehalten()}")
        await self.netz_melden()
        return False

    async def warten(self, bedingung: str, timeout: float = 15, *, melden: bool = True) -> bool:
        """Wartet, bis der JS-Ausdruck wahr ist. Läuft die Zeit ab, druckt es seit 1.8.97 die offenen Anfragen (mit "--", denn ein
        Ablauf ist nicht immer ein Fehler -- meist scheitert danach die Prüfung); melden=False für eine gewollte Pause. Seit 1.8.97
        übersteht es wie oeffnen() eine Navigation (Ausführungskontext gerade weg)."""
        ende = time.monotonic() + timeout
        while time.monotonic() < ende:
            try:
                if await self.js(f"(()=>{{try{{return !!({bedingung})}}catch(e){{return false}}}})()"):
                    return True
            except RuntimeError:
                pass  # Navigation noch nicht fertig
            await asyncio.sleep(0.1)
        if melden:
            await self.netz_melden(f"--  warten: nach {timeout:g} s nicht erfüllt: {bedingung[:80]}")
        return False

    async def bild(self, name: str) -> Path:
        data = (await self.cmd("Page.captureScreenshot", format="png"))["data"]
        ziel = self.shots / f"{name}.png"
        ziel.write_bytes(base64.b64decode(data))
        return ziel


class Pruefungen:
    def __init__(self):
        self.ergebnisse: list[bool] = []
        # Seit 1.8.97: das Netzprotokoll des Tabs (von _lauf() gesetzt) -- eine Abweichung druckt die offenen Anfragen. pruefe() ist
        # synchron und liest nicht nach: es druckt den Stand des letzten Lesens (meist der Prüfung selbst, z. B. await tab.js(…)).
        self.netz: Netzprotokoll | None = None

    def pruefe(self, name: str, ist, soll) -> bool:
        ok = ist == soll
        self.ergebnisse.append(ok)
        print(f"{'OK ' if ok else 'XX '} {name}: {ist!r}" + ("" if ok else f"   (erwartet {soll!r})"))
        if not ok and self.netz is not None:
            print("\n".join(self.netz.melden()), flush=True)
        return ok


# ---------------------------------------------------------------------------
# Prozesse
# ---------------------------------------------------------------------------

def _freier_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _chrome_pfad(angegeben: str | None) -> str:
    for kandidat in (angegeben, os.environ.get("CHROME"), *CHROME_CANDIDATES):
        if kandidat and Path(kandidat).exists():
            return kandidat
    found = shutil.which("chrome") or shutil.which("google-chrome") or shutil.which("msedge")
    if found:
        return found
    raise SystemExit("Kein Chrome gefunden -- Pfad mit --chrome oder $CHROME angeben.")


def _warte_auf(url: str, timeout: float) -> bool:
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except urllib.error.HTTPError:
            return True  # der Server antwortet, der Status ist hier egal
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.3)
    return False


TASKKILL_SEKUNDEN = 30  # seit 1.8.111


def _taskkill(pid: int) -> list[str]:
    return ["taskkill", "/PID", str(pid), "/T", "/F"]


def beenden(pid: int) -> None:
    """Beendet genau diesen Prozess samt eigener Kindprozesse, über die PID (Regel 12).

    Seit 1.8.111 (Vorgabe "Vor dem Abnahmetest" Punkt 7, Nebenbefund 4 aus 1.8.108) mit Zeitlimit: taskkill lief mit
    capture_output ohne Grenze -- in einer Überlast-Probe hing ein Klicktest nach "42 von 42" darin. Jetzt ohne Ausgabe (DEVNULL) und
    nach TASKKILL_SEKUNDEN abgebrochen; dann eine Hinweiszeile mit der PID, der Klicktest endet trotzdem."""
    if os.name == "nt":
        try:
            subprocess.run(_taskkill(pid), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=TASKKILL_SEKUNDEN)
        except subprocess.TimeoutExpired:
            print(f"Hinweis: taskkill für PID {pid} nach {TASKKILL_SEKUNDEN} s abgebrochen -- der Prozess läuft womöglich noch "
                  f"(prüfen über die PID, Regel 12).", flush=True)
    else:
        try:
            os.kill(pid, 15)
        except ProcessLookupError:
            pass


def gegenprobe_im_code(root: Path = ROOT) -> str | None:
    """Erste Fundstelle "<datei>:<zeile>" des Markers GEGENPROBE unter root/app (alle Textdateien, wie test_v357), sonst None."""
    for path in sorted((root / "app").rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if GEGENPROBE_MARKER in text:
            nummer = next(n for n, zeile in enumerate(text.splitlines(), start=1) if GEGENPROBE_MARKER in zeile)
            return f"{path.relative_to(root).as_posix()}:{nummer}"
    return None


class Wachhund:
    """Seit 1.8.108: bricht den Klicktest nach `sekunden` ab -- auch wenn der Lauf in einem CDP-Befehl, im Befüllen oder beim
    Warten auf die Instanz hängt. Beendet die eigenen Kindprozesse (über ihre PID, Regel 12) und den Prozess mit CODE_ZEITLIMIT.
    Ein Thread, kein asyncio: hängt die Ereignisschleife, läuft er trotzdem."""

    def __init__(self, sekunden: float, grund: str):
        self.sekunden, self.grund = sekunden, grund
        self.kinder: list[subprocess.Popen] = []
        self._timer = threading.Timer(sekunden, self._abbrechen)
        self._timer.daemon = True

    def starten(self) -> None:
        self._timer.start()

    def anhalten(self) -> None:
        """Hält ihn an; ist er schon abgelaufen, wartet es auf ihn -- er beendet den Prozess."""
        self._timer.cancel()
        if self._timer.is_alive():
            self._timer.join()

    def _abbrechen(self) -> None:
        print(f"\nABBRUCH: Zeitlimit {int(self.sekunden)} s erreicht ({self.grund}). Eigene Prozesse werden beendet.", flush=True)
        for proc in reversed(self.kinder):
            if proc.poll() is None:
                beenden(proc.pid)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(CODE_ZEITLIMIT)


UHR_ENV = "KLICKTEST_UHR"


def _uhr_marke(uhrzeit: str) -> str:
    """Startpunkt der Uhr für die Kindprozesse: heute (Europe/Berlin) um uhrzeit, in UTC, dazu die
    echte Zeit dieses Augenblicks. Befüllen und Server rechnen von derselben Marke weiter -- die Uhr
    läuft in beiden gleich und springt zwischen ihnen nicht zurück."""
    from datetime import datetime, time as uhr, timezone
    from zoneinfo import ZoneInfo

    berlin = ZoneInfo("Europe/Berlin")
    echt = time.time()
    heute = datetime.fromtimestamp(echt, berlin).date()
    start = datetime.combine(heute, uhr.fromisoformat(uhrzeit), tzinfo=berlin).astimezone(timezone.utc)
    return f"{start.isoformat()}|{echt}"


def _uhr_einsetzen() -> None:
    """Im Kindprozess, vor dem Import von app.main: die eine Uhr der App (app.berlin_time._utc_now)
    auf die Marke aus KLICKTEST_UHR setzen. Ohne die Variable bleibt die echte Uhr."""
    marke = os.environ.get(UHR_ENV)
    if not marke:
        return
    from datetime import datetime, timedelta

    start_text, echt_text = marke.split("|")
    start, echt = datetime.fromisoformat(start_text), float(echt_text)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from app import berlin_time

    berlin_time._utc_now = lambda: start + timedelta(seconds=time.time() - echt)


def _server_mit_uhr(host: str, port: int) -> None:
    """uvicorn im selben Prozess wie die gesetzte Uhr -- `python -m uvicorn` hätte sie nicht."""
    _uhr_einsetzen()
    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port)


def _isolierte_umgebung(ordner: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("ERP_") and k != "DATABASE_URL"}
    env.update({
        "DATABASE_URL": "sqlite:///" + (ordner / "erp.db").as_posix(),
        "ERP_DATA_DIR": str(ordner / "data"),
        "ERP_SECRET_KEY": secrets.token_urlsafe(32),
        "ERP_ENV": "development",
        "PYTHONIOENCODING": "utf-8",
    })
    return env


# ---------------------------------------------------------------------------
# Einstieg
# ---------------------------------------------------------------------------

def klicktest_main(befuellen, pruefen, *, beschreibung: str = "", uhr: str | None = None) -> int:
    """uhr: "HH:MM" -- die Instanz läuft heute ab dieser Uhrzeit (Europe/Berlin), siehe FESTE UHR oben."""
    parser = argparse.ArgumentParser(description=(beschreibung or "").strip().splitlines()[0] if beschreibung else None)
    parser.add_argument("--app-port", type=int, default=0)
    parser.add_argument("--cdp-port", type=int, default=0)
    parser.add_argument("--arbeitsordner", type=Path)
    parser.add_argument("--chrome")
    parser.add_argument("--offen-lassen", action="store_true")
    parser.add_argument("--wanduhr", metavar="HH:MM")
    parser.add_argument("--zeitlimit", type=float, metavar="SEK")
    parser.add_argument("--nur-befuellen", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.nur_befuellen:
        _befuellen_im_kindprozess(befuellen, args.nur_befuellen)
        return 0

    # Seit 1.8.108: Zeitlimit -- in einer Gegenprobe immer höchstens 2 min
    gegenprobe = gegenprobe_im_code()
    grenzen = [(args.zeitlimit, "--zeitlimit")] if args.zeitlimit else []
    if gegenprobe:
        grenzen.append((ZEITLIMIT_GEGENPROBE, f"Gegenprobe läuft, Marker {GEGENPROBE_MARKER} in {gegenprobe}"))
    wachhund = Wachhund(*min(grenzen)) if grenzen else None
    if wachhund:
        print(f"Zeitlimit {int(wachhund.sekunden)} s ({wachhund.grund})", flush=True)
        wachhund.starten()
    try:
        return _ablauf(befuellen, pruefen, args, uhr, wachhund)
    finally:
        if wachhund:  # ist er abgelaufen, endet der Prozess hier mit CODE_ZEITLIMIT -- auch wenn der Ablauf schon zurückkam,
            wachhund.anhalten()  # weil das Beenden seiner Kindprozesse ihn weiterlaufen ließ ("Befüllen fehlgeschlagen.")


def _ablauf(befuellen, pruefen, args, uhr: str | None, wachhund: "Wachhund | None") -> int:
    ordner = (args.arbeitsordner or Path(tempfile.mkdtemp(prefix="erp-klicktest-"))).resolve()
    if ordner.exists() and any(ordner.iterdir()):
        raise SystemExit(f"Arbeitsordner ist nicht leer: {ordner}")
    for sub in ("data", "shots", "chrome-profile"):
        (ordner / sub).mkdir(parents=True, exist_ok=True)
    (ordner / MARKER).write_text("Wegwerf-Instanz eines Klicktests, darf gelöscht werden.\n", encoding="utf-8")
    app_port = args.app_port or _freier_port()
    cdp_port = args.cdp_port or _freier_port()
    env = _isolierte_umgebung(ordner)
    uhrzeit = uhr or args.wanduhr
    if uhrzeit:
        env[UHR_ENV] = _uhr_marke(uhrzeit)
    print(f"Arbeitsordner {ordner}\nERP http://127.0.0.1:{app_port}  CDP {cdp_port}"
          + (f"\nUhr der Instanz: heute ab {uhrzeit} (Europe/Berlin)" if uhrzeit else ""), flush=True)

    skript = Path(sys.argv[0]).resolve()
    seed_datei = ordner / "seed.json"
    befuellen_proc = subprocess.Popen([sys.executable, str(skript), "--nur-befuellen", str(seed_datei)], env=env, cwd=ROOT)
    if wachhund:
        wachhund.kinder.append(befuellen_proc)
    if befuellen_proc.wait() != 0 or not seed_datei.exists():
        print("Befüllen fehlgeschlagen.")
        return 2
    seed = json.loads(seed_datei.read_text(encoding="utf-8"))

    server = chrome = None
    try:
        with open(ordner / "server.out.log", "wb") as out, open(ordner / "server.err.log", "wb") as err:
            befehl = ([sys.executable, str(Path(__file__).resolve()), "--server-mit-uhr", "127.0.0.1", str(app_port)]
                      if uhrzeit else
                      [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(app_port)])
            server = subprocess.Popen(befehl, env=env, cwd=ROOT, stdout=out, stderr=err)
        if wachhund:
            wachhund.kinder.append(server)
        if not _warte_auf(f"http://127.0.0.1:{app_port}/login", 60):
            print(f"ERP-Instanz antwortet nicht, siehe {ordner / 'server.err.log'}")
            return 2
        chrome = subprocess.Popen([_chrome_pfad(args.chrome), "--headless=new", f"--remote-debugging-port={cdp_port}",
                                   f"--user-data-dir={ordner / 'chrome-profile'}", "--no-first-run",
                                   "--no-default-browser-check", "--disable-extensions", "about:blank"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if wachhund:
            wachhund.kinder.append(chrome)
        (ordner / "pids.txt").write_text(f"server={server.pid} chrome={chrome.pid}\n", encoding="utf-8")
        if not _warte_auf(f"http://127.0.0.1:{cdp_port}/json/version", 30):
            print("Chrome antwortet nicht auf dem CDP-Port.")
            return 2
        ok = asyncio.run(_lauf(pruefen, seed, cdp_port, f"http://127.0.0.1:{app_port}", ordner / "shots"))
        return 0 if ok else 1
    finally:
        if wachhund:
            wachhund.anhalten()
        if args.offen_lassen:
            print(f"Läuft weiter: {(ordner / 'pids.txt').read_text(encoding='utf-8').strip()}  "
                  "(beenden mit taskkill /PID <pid> /T /F)")
        else:
            for proc in (chrome, server):
                if proc is not None:
                    beenden(proc.pid)


async def _lauf(pruefen, seed, cdp_port: int, base_url: str, shots: Path) -> bool:
    import websockets

    ziele = json.load(urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/list"))
    seite = next(t for t in ziele if t["type"] == "page")
    p = Pruefungen()
    async with websockets.connect(seite["webSocketDebuggerUrl"], max_size=64_000_000) as ws:
        tab = Tab(ws, base_url, shots, cdp_port)
        p.netz = tab.netz  # seit 1.8.97
        for domain in ("Page", "Runtime", "Network"):
            await tab.cmd(f"{domain}.enable")
        await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=ANTWORT_RUECKHALT)  # seit 1.8.95, vor dem Zähler
        await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=ANFRAGEN_ZAEHLER)  # seit 1.8.94
        await tab.fenster(1400, 1000)
        ok = await _pruefen_und_melden(pruefen, tab, seed, p)
    print(f"{p.ergebnisse.count(True)} von {len(p.ergebnisse)} Prüfungen wie erwartet"
          + ("" if not tab.nicht_geladen else f", nicht geladen: {tab.nicht_geladen}") + f". Screenshots: {shots}")
    return ok


async def _pruefen_und_melden(pruefen, tab: Tab, seed, p: Pruefungen) -> bool:
    """Seit 1.8.97: führt pruefen() aus; endet der Lauf nicht wie erwartet (eine Abweichung, eine Seite nicht geladen oder eine
    Ausnahme), druckt es danach das Netzprotokoll -- auch ohne Änderung seit der letzten Meldung. Eine Ausnahme geht danach weiter."""
    fehler = None
    try:
        await pruefen(tab, seed, p)
    except Exception as exc:
        fehler = exc
    ok = fehler is None and all(p.ergebnisse) and not tab.nicht_geladen
    if not ok:
        try:
            await asyncio.wait_for(tab.netz_melden("--  Netzwerk am Ende des Laufs (nicht wie erwartet):", immer=True), 15)
        except Exception as exc:
            print(f"--  Netzprotokoll am Ende nicht lesbar ({type(exc).__name__})", flush=True)
    if fehler is not None:
        raise fehler
    return ok


if __name__ == "__main__" and len(sys.argv) == 4 and sys.argv[1] == "--server-mit-uhr":
    _server_mit_uhr(sys.argv[2], int(sys.argv[3]))
