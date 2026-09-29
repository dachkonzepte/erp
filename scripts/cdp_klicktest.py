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

Rückgabecode: 0 = alle Prüfungen wie erwartet, 1 = mindestens eine Abweichung,
2 = Instanz oder Chrome ließ sich nicht starten.

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
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = ".klicktest"
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

    def cookies(self, user) -> dict:
        """Anmelde-Cookies für einen gespeicherten AppUser, ohne Login über die Oberfläche.
        Das 2FA-Cookie ist dabei, damit auch ein Admin ohne zweiten Faktor durchkommt."""
        from app.auth import COOKIE_NAME, OTP_COOKIE_NAME, make_cookie, make_otp_ok_cookie
        return {COOKIE_NAME: make_cookie(user.id), OTP_COOKIE_NAME: make_otp_ok_cookie(user.id)}

    def passwort(self, text: str = "x-Passwort-123") -> str:
        from app.auth import hash_password
        return hash_password(text)


def _befuellen_im_kindprozess(befuellen, ziel: Path) -> None:
    url = os.environ.get("DATABASE_URL", "")
    db_file = Path(url.removeprefix("sqlite:///")) if url.startswith("sqlite:///") else None
    if db_file is None or not (db_file.parent / MARKER).exists():
        raise SystemExit(f"Abbruch (Regel 16): DATABASE_URL zeigt nicht in einen Klicktest-Arbeitsordner: {url!r}")
    sys.path.insert(0, str(ROOT))
    import app.main  # noqa: F401 -- create_all() auf der Wegwerf-Datenbank
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        seed = befuellen(db, Werkzeug())
        db.commit()
    finally:
        db.close()
    ziel.write_text(json.dumps(seed, default=str, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------------
# CDP
# ---------------------------------------------------------------------------

class Tab:
    """Eine Browser-Seite. fehler sammelt JS-Ausnahmen und console.error seit dem letzten oeffnen()."""

    def __init__(self, ws, base_url: str, shots: Path):
        self.ws, self.base, self.shots = ws, base_url, shots
        self.n = 0
        self.fehler: list[str] = []
        self.nicht_geladen: list[str] = []

    async def cmd(self, method: str, **params):
        self.n += 1
        my = self.n
        await self.ws.send(json.dumps({"id": my, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("method") == "Runtime.exceptionThrown":
                d = msg["params"]["exceptionDetails"]
                self.fehler.append((d.get("exception", {}).get("description") or d.get("text", "?"))[:300])
            if msg.get("method") == "Runtime.consoleAPICalled" and msg["params"]["type"] == "error":
                self.fehler.append(" ".join(str(a.get("value", a.get("description", ""))) for a in msg["params"]["args"])[:300])
            if msg.get("id") == my:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg["result"]

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

    async def anmelden(self, cookies: dict) -> None:
        await self.cmd("Network.clearBrowserCookies")
        for name, value in cookies.items():
            await self.cmd("Network.setCookie", name=name, value=value, url=self.base)

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
        return False

    async def warten(self, bedingung: str, timeout: float = 15) -> bool:
        ende = time.monotonic() + timeout
        while time.monotonic() < ende:
            if await self.js(f"(()=>{{try{{return !!({bedingung})}}catch(e){{return false}}}})()"):
                return True
            await asyncio.sleep(0.1)
        return False

    async def bild(self, name: str) -> Path:
        data = (await self.cmd("Page.captureScreenshot", format="png"))["data"]
        ziel = self.shots / f"{name}.png"
        ziel.write_bytes(base64.b64decode(data))
        return ziel


class Pruefungen:
    def __init__(self):
        self.ergebnisse: list[bool] = []

    def pruefe(self, name: str, ist, soll) -> bool:
        ok = ist == soll
        self.ergebnisse.append(ok)
        print(f"{'OK ' if ok else 'XX '} {name}: {ist!r}" + ("" if ok else f"   (erwartet {soll!r})"))
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


def beenden(pid: int) -> None:
    """Beendet genau diesen Prozess samt eigener Kindprozesse, über die PID (Regel 12)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.kill(pid, 15)
        except ProcessLookupError:
            pass


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

def klicktest_main(befuellen, pruefen, *, beschreibung: str = "") -> int:
    parser = argparse.ArgumentParser(description=(beschreibung or "").strip().splitlines()[0] if beschreibung else None)
    parser.add_argument("--app-port", type=int, default=0)
    parser.add_argument("--cdp-port", type=int, default=0)
    parser.add_argument("--arbeitsordner", type=Path)
    parser.add_argument("--chrome")
    parser.add_argument("--offen-lassen", action="store_true")
    parser.add_argument("--nur-befuellen", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.nur_befuellen:
        _befuellen_im_kindprozess(befuellen, args.nur_befuellen)
        return 0

    ordner = (args.arbeitsordner or Path(tempfile.mkdtemp(prefix="erp-klicktest-"))).resolve()
    if ordner.exists() and any(ordner.iterdir()):
        raise SystemExit(f"Arbeitsordner ist nicht leer: {ordner}")
    for sub in ("data", "shots", "chrome-profile"):
        (ordner / sub).mkdir(parents=True, exist_ok=True)
    (ordner / MARKER).write_text("Wegwerf-Instanz eines Klicktests, darf gelöscht werden.\n", encoding="utf-8")
    app_port = args.app_port or _freier_port()
    cdp_port = args.cdp_port or _freier_port()
    env = _isolierte_umgebung(ordner)
    print(f"Arbeitsordner {ordner}\nERP http://127.0.0.1:{app_port}  CDP {cdp_port}", flush=True)

    skript = Path(sys.argv[0]).resolve()
    seed_datei = ordner / "seed.json"
    befuellt = subprocess.run([sys.executable, str(skript), "--nur-befuellen", str(seed_datei)], env=env, cwd=ROOT)
    if befuellt.returncode != 0 or not seed_datei.exists():
        print("Befüllen fehlgeschlagen.")
        return 2
    seed = json.loads(seed_datei.read_text(encoding="utf-8"))

    server = chrome = None
    try:
        with open(ordner / "server.out.log", "wb") as out, open(ordner / "server.err.log", "wb") as err:
            server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                       "--port", str(app_port)], env=env, cwd=ROOT, stdout=out, stderr=err)
        if not _warte_auf(f"http://127.0.0.1:{app_port}/login", 60):
            print(f"ERP-Instanz antwortet nicht, siehe {ordner / 'server.err.log'}")
            return 2
        chrome = subprocess.Popen([_chrome_pfad(args.chrome), "--headless=new", f"--remote-debugging-port={cdp_port}",
                                   f"--user-data-dir={ordner / 'chrome-profile'}", "--no-first-run",
                                   "--no-default-browser-check", "--disable-extensions", "about:blank"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (ordner / "pids.txt").write_text(f"server={server.pid} chrome={chrome.pid}\n", encoding="utf-8")
        if not _warte_auf(f"http://127.0.0.1:{cdp_port}/json/version", 30):
            print("Chrome antwortet nicht auf dem CDP-Port.")
            return 2
        ok = asyncio.run(_lauf(pruefen, seed, cdp_port, f"http://127.0.0.1:{app_port}", ordner / "shots"))
        return 0 if ok else 1
    finally:
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
        tab = Tab(ws, base_url, shots)
        for domain in ("Page", "Runtime", "Network"):
            await tab.cmd(f"{domain}.enable")
        await tab.fenster(1400, 1000)
        await pruefen(tab, seed, p)
    ok = all(p.ergebnisse) and not tab.nicht_geladen
    print(f"{p.ergebnisse.count(True)} von {len(p.ergebnisse)} Prüfungen wie erwartet"
          + ("" if not tab.nicht_geladen else f", nicht geladen: {tab.nicht_geladen}") + f". Screenshots: {shots}")
    return ok
