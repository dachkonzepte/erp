"""Version 1.11.47 -- Impressum und Datenschutz als Pflicht, die Orte von nginx, „Allgemeine Fotos“, Messung des Kinds (Kleinigkeiten nach P2e).

    Pflicht       Entscheidung des Betriebs 27.11.2026: Impressum und Datenschutz sind im Portal Pflicht. Beide bildet das Portal aus der Webseite der
                  Unternehmensdaten (https://<Webseite>/impressum bzw. /datenschutz). Ohne gültige Webseite: jede Seite des Portals „Gerade klappt etwas
                  nicht“ (500) statt einer Seite ohne die Links; im ERP Modul einschalten, Portal am Kunden einschalten und Link senden 409 mit Grund,
                  ausschalten geht immer; „Start“ zeigt den Hinweis (tests/test_v806_portal_stau.py, Klicktest klicktest_portal_stau.py). Dass beide
                  Links auf jeder Seite stehen, belegen klicktest_portal_seiten.py (A bis E) und klicktest_portal_bereiche.py (jeder Bereich).
    Orte          scripts/server/nginx-kunde.conf: der Block der Dateien mit ^~ -- kein Regex-Ort nimmt ihm eine Adresse; die Attrappe wählt den Ort jeder
                  Adresse wie nginx (exakt, längster Präfix, ^~, Regex) und verlangt, dass ein X-Accel-Redirect im Block der Dateien landet.
    Fotos         die Gruppe ohne Auftrag und Objekt heißt unter „Fotos“ „Allgemeine Fotos“ (unter „Unterlagen“ weiter „Allgemeine Unterlagen“).
    Messung       scripts/pruefe_portal_foto.py startet das Kind aus einem kleinen Messprozess, der kein Bild hält -- unter Linux übernähme das Kind
                  sonst beim Start den Höchststand des startenden Prozesses in seine Spitze (bis 1.11.46 gemessen: rund 320 MB, die des Skripts).
"""

import http.client
import importlib.util
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from sqlalchemy import select

from app import kundenportal as kp
from app.models import Customer, EmailDispatch, EnabledModule, PortalZugang
from app.portal import bereiche
from app.routers import kundenportal, modules
from tests.portal_webseite import webseite_setzen
from tests.test_v811_portal_seiten import _client

ROOT = Path(__file__).resolve().parent.parent
NGINX = ROOT / "scripts" / "server" / "nginx-kunde.conf"
sys.path.insert(0, str(ROOT / "scripts"))
import nginx_attrappe  # noqa: E402


# --- Pflicht im Dienst des Portals ------------------------------------------------------------------------------------------------------------

def _fall(html_: str) -> str:
    return re.search(r'<body data-fall="([^"]*)"', html_).group(1)


@pytest.mark.parametrize("webseite", [None, "", "javascript:alert(1)", "localhost"])
def test_ohne_gueltige_webseite_jede_seite_technisch(webseite):
    client, _app, _engine = _client(website=webseite)
    with client:
        for pfad in ("/", "/gibt-es-nicht"):
            r = client.get(pfad)
            assert (r.status_code, _fall(r.text)) == (500, "technisch"), pfad
            assert "/impressum" not in r.text and "Seite gibt es nicht" not in r.text


def test_mit_webseite_beide_links_im_fuss():
    client, _app, _engine = _client()
    with client:
        for pfad, status, fall in (("/", 200, ""), ("/gibt-es-nicht", 404, "nicht_gefunden")):
            r = client.get(pfad)
            assert (r.status_code, _fall(r.text)) == (status, fall)
            fuss = r.text[r.text.index('<footer class="fuss">'):r.text.index("</footer>")]
            assert re.findall(r'<a href="([^"]*)">([^<]*)</a>', fuss) == [("https://www.example.invalid/impressum", "Impressum"),
                                                                       ("https://www.example.invalid/datenschutz", "Datenschutz")]


def test_pflicht_da_wie_firma():
    from app.portal.seiten import Seiten
    assert Seiten.pflicht_da({"website": "www.example.invalid"}) and not Seiten.pflicht_da({"website": None}) and not Seiten.pflicht_da(None)


# --- Pflicht im ERP --------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def erp(threaded_db_session, router_test_client):
    db = threaded_db_session
    kunde = Customer(name="Herr Max Muster", salutation="Herr", first_name="Max", last_name="Muster", email="max@example.invalid")
    db.add(kunde)
    db.commit()
    admin = router_test_client(db, modules.router, role="admin")
    buero = router_test_client(db, kundenportal.router, role="buero_auftrag", user_id=11, display_name="Auri Auftrag")
    return db, kunde, admin, buero


def test_modul_einschalten_nur_mit_webseite(erp):
    db, _kunde, admin, _buero = erp
    r = admin.put("/api/modules/kundenportal", json={"enabled": True})
    assert (r.status_code, r.json()["detail"]) == (409, kp.PFLICHT_FEHLT)
    assert db.scalar(select(EnabledModule).where(EnabledModule.module_key == "kundenportal")) is None  # nichts gespeichert
    assert admin.put("/api/modules/kundenportal", json={"enabled": False}).status_code == 200  # ausschalten geht immer
    webseite_setzen(db)
    assert admin.put("/api/modules/kundenportal", json={"enabled": True}).json()["enabled"] is True


def test_portal_am_kunden_nur_mit_webseite(erp):
    db, kunde, _admin, buero = erp
    db.add(EnabledModule(module_key="kundenportal", enabled=True))
    db.commit()
    r = buero.post(f"/api/customers/{kunde.id}/portal/schalter", json={"an": True})
    assert (r.status_code, r.json()["detail"]) == (409, kp.PFLICHT_FEHLT)
    db.refresh(kunde)
    assert kunde.portal_aktiv is False
    assert buero.post(f"/api/customers/{kunde.id}/portal/schalter", json={"an": False}).status_code == 200
    webseite_setzen(db)
    assert buero.post(f"/api/customers/{kunde.id}/portal/schalter", json={"an": True}).status_code == 200


def test_link_senden_nur_mit_webseite(erp):
    """Webseite nach dem Einschalten entfernt: kein neuer Link, keine Mail, nichts gespeichert."""
    db, kunde, _admin, buero = erp
    db.add(EnabledModule(module_key="kundenportal", enabled=True))
    kunde.portal_aktiv = True
    db.add(PortalZugang(customer_id=kunde.id, email="max@example.invalid", email_anzeige="m***@example.invalid"))
    db.commit()
    r = buero.post(f"/api/customers/{kunde.id}/portal/link", json={"email": "max@example.invalid", "dispatch_key": "portal-link-v837-0001"})
    assert (r.status_code, r.json()["detail"]) == (409, kp.PFLICHT_FEHLT)
    assert db.scalar(select(EmailDispatch)) is None
    assert db.scalar(select(PortalZugang)).link_sha256 is None


# --- Orte von nginx -------------------------------------------------------------------------------------------------------------------------

def test_block_der_dateien_mit_praefix_vorrang():
    orte = nginx_attrappe.orte(NGINX)
    datei = [o for o in orte if o.muster == "/_portal_dateien/"]
    assert datei == [nginx_attrappe.Ort("^~", "/_portal_dateien/", True)]
    assert not [o for o in orte if o.art in ("~", "~*")], "ein Regex-Ort im Block des Portals -- nimmt er Adressen unter /_portal_dateien/?"
    waehlen = lambda p: nginx_attrappe.ort_waehlen(p, orte)  # noqa: E731
    assert waehlen("/_portal_dateien/.datenbank") == datei[0] and waehlen("/_portal_dateien/" + "a" * 64 + ".pdf") == datei[0]
    assert waehlen("/_portal_dateien").muster == "/" and waehlen("/api/code").art == "=" and waehlen("/api/code/x").muster == "/"
    assert waehlen("/_wartung.html").internal and not waehlen("/datei/1").internal


def _mit_regex(tmp_path: Path, mit_praefix: bool) -> Path:
    """Die nginx-Datei mit einem Regex-Ort für PDF und JPEG vor /api/code -- mit oder ohne ^~ am Block der Dateien."""
    text = NGINX.read_text(encoding="utf-8").replace("    location = /api/code {", "    location ~* \\.(pdf|jpg)$ {\n        proxy_pass http://127.0.0.1:8010;\n    }\n\n    location = /api/code {")
    if not mit_praefix:
        text = text.replace("location ^~ /_portal_dateien/ {", "location /_portal_dateien/ {")
    ziel = tmp_path / ("mit.conf" if mit_praefix else "ohne.conf")
    ziel.write_text(text, encoding="utf-8")
    return ziel


def test_mit_praefix_vorrang_gewinnt_der_block_gegen_einen_regex(tmp_path):
    name = "/_portal_dateien/" + "b" * 64 + ".pdf"
    mit = nginx_attrappe.orte(_mit_regex(tmp_path, True))
    ohne = nginx_attrappe.orte(_mit_regex(tmp_path, False))
    assert nginx_attrappe.ort_waehlen(name, mit).muster == "/_portal_dateien/"
    assert nginx_attrappe.ort_waehlen(name, ohne).art == "~*"  # so wie nginx: ein Präfix ohne ^~ verliert gegen den Regex


class _Dienst(BaseHTTPRequestHandler):
    """Attrappe des Portal-Dienstes: antwortet auf /gut mit einem X-Accel-Redirect in den Block der Dateien, auf /falsch daneben."""
    NAME = "c" * 64 + ".pdf"

    def log_message(self, *args):
        pass

    def do_GET(self):
        ziel = {"/gut": "/_portal_dateien/" + self.NAME, "/falsch": "/_anderswo/" + self.NAME}.get(self.path)
        self.send_response(200 if ziel else 404)
        if ziel:
            self.send_header("X-Accel-Redirect", ziel)
            self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.mark.parametrize("conf, pfad, status", [
    ("echt", "/gut", 200), ("echt", "/falsch", 500), ("echt", "/_portal_dateien/" + _Dienst.NAME, 404),
    ("ohne", "/gut", 500),  # ohne ^~ nähme der Regex-Ort den internen Weg -- die Attrappe macht es sichtbar
])
def test_attrappe_waehlt_den_ort_wie_nginx(tmp_path, conf, pfad, status):
    (tmp_path / _Dienst.NAME).write_bytes(b"%PDF-1.4 erfunden")
    dienst = ThreadingHTTPServer(("127.0.0.1", 0), _Dienst)
    Thread(target=dienst.serve_forever, daemon=True).start()
    datei = NGINX if conf == "echt" else _mit_regex(tmp_path, False)
    attrappe = nginx_attrappe.Attrappe(dienst.server_address[1], tmp_path, datei)
    port = attrappe.starten()
    try:
        verbindung = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        verbindung.request("GET", pfad)
        antwort = verbindung.getresponse()
        inhalt = antwort.read()
        verbindung.close()
        assert antwort.status == status, inhalt[:200]
        if status == 200:
            assert inhalt == b"%PDF-1.4 erfunden"
    finally:
        attrappe.beenden()
        dienst.shutdown()
        dienst.server_close()


# --- Fotos ohne Auftrag ---------------------------------------------------------------------------------------------------------------------

def test_fotos_ohne_auftrag_heissen_allgemeine_fotos():
    from datetime import date

    zeilen = [{"freigabe": 1, "art": "foto", "titel": "Foto", "datum": date(2026, 11, 20), "auftrag": None, "betreff": None, "objekt": None},
              {"freigabe": 2, "art": "foto", "titel": "Foto", "datum": date(2026, 11, 19), "auftrag": "A-1", "betreff": "Dach", "objekt": "Musterweg 12"},
              {"freigabe": 3, "art": "dokument", "titel": "Plan", "datum": date(2026, 11, 18), "auftrag": None, "betreff": None, "objekt": None}]
    d = bereiche.unterlagen(zeilen)
    assert [(g["titel"], g["unter"]) for g in d["fotos"]] == [("Auftrag A-1 · Dach", "Musterweg 12"), ("Allgemeine Fotos", "ohne bestimmten Auftrag")]
    assert [(g["titel"], g["unter"]) for g in d["unterlagen"]] == [("Allgemeine Unterlagen", "ohne bestimmten Auftrag")]


# --- Messung: das Kind startet ein Prozess ohne Bild -----------------------------------------------------------------------------------------

# Attrappe des Kinds (nur Windows): misst den Höchststand des Prozesses, der es gestartet hat, und endet mit 0, wenn er klein ist (unter 100 MB)
KIND = r"""
import ctypes, ctypes.wintypes as wt, os, sys
sys.stdin.buffer.read()
class PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("a", ctypes.c_size_t), ("b", ctypes.c_size_t), ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("e", ctypes.c_size_t), ("f", ctypes.c_size_t)]
k = ctypes.windll.kernel32
k.OpenProcess.restype = wt.HANDLE
ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD]
h = k.OpenProcess(0x1000 | 0x0010, False, os.getppid())
pmc = PMC(); pmc.cb = ctypes.sizeof(PMC)
if not h or not ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb) or pmc.PeakWorkingSetSize == 0:
    sys.exit(8)  # nicht gemessen -- nie als „klein“ werten
sys.exit(0 if pmc.PeakWorkingSetSize < 100 * 2**20 else 9)
"""


@pytest.mark.skipif(sys.platform != "win32", reason="misst den startenden Prozess über die Speicherangaben von Windows")
def test_messung_startet_das_kind_aus_einem_kleinen_prozess(tmp_path, monkeypatch):
    """Dieser Testprozess hält 300 MB; das Kind (Attrappe) sieht trotzdem einen kleinen Starter -- es wird nicht von hier gestartet."""
    spec = importlib.util.spec_from_file_location("pruefe_portal_foto_v837", ROOT / "scripts" / "pruefe_portal_foto.py")
    skript = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(skript)
    ballast = b"\x01" * (300 * 2**20)  # noqa: F841 -- belegt
    # der echte Interpreter, nicht .venv\Scripts\python.exe: der startet unter Windows den Interpreter als eigenes Kind -- die Attrappe sähe sonst
    # immer diesen kleinen Starter als Elternprozess (die erste Fassung dieses Tests blieb deshalb in der Gegenprobe grün)
    monkeypatch.setattr("app.portal_kopien.kind_befehl", lambda *a, **k: [sys._base_executable, "-I", "-c", KIND])
    (tmp_path / "eingabe.bin").write_bytes(b"x" * 1024)
    ergebnis, _dauer, _spitze = skript._messen(tmp_path / "eingabe.bin")
    assert ergebnis == "JPEG 0 KB", ergebnis  # Rückgabe 0: der Starter war klein
    assert json.loads(json.dumps({"ballast": len(ballast)}))["ballast"] == 300 * 2**20
