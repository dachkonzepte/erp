"""Version 1.8.126 -- Stufe 0d des Redesigns: Bildgrundlage (scripts/bildgrundlage.py).

Das Werkzeug nimmt jede Seite als Bild auf, damit der Umbau auf ein gemeinsames Basis-Layout Seite für Seite verglichen werden kann.
Hier geprüft, ohne Browser:

    Abdeckung       jede Seite aus tests/vorlagen_js.py::seiten() steht in AUFNAHMEN, keine Vorlage dort ist keine Seite
    Adressen        jede Adresse zeichnet für jede ihrer Rollen genau die genannte Vorlage (Sperrseite: 403 für die Monteurin)
    Monteur         jede Seitenroute, die die Monteurin öffnen darf, steht mit Rolle "monteur" in AUFNAHMEN
    Vergleich       gleiche Bilder 0, ein Pixel 1 samt Differenzbild, andere Größe, fehlende und neue Bilder; Rückgabecode
    Zeitstempel     nach dem Befüllen stehen alle auf der Uhr, außer dem Ablauf der Sitzungen
    Uhr             stehende Uhr des Servers ("JJJJ-MM-TT HH:MM") und des Browsers (in node, Regel 36)
    Wachhund        das Zeitlimit je Schritt beginnt mit neu_starten() neu, ohne je_schritt nicht
    Port-Helfer     überspringt belegte (127.0.0.1 und 0.0.0.0) und reservierte Ports; kein Klicktest hat einen eigenen
    Ordner          bildgrundlage/ steht in .gitignore
"""

import errno
import importlib.util
import json
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.database import get_db
from app.routers.pages import router as pages_router
from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _laden(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_test_v431", SCRIPTS / f"{name}.py")
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul  # dataclass liest das Modul aus sys.modules
    spec.loader.exec_module(modul)
    return modul


bg = _laden("bildgrundlage")
kt = sys.modules["cdp_klicktest"]  # bildgrundlage.py importiert es


# ---------------------------------------------------------------------------
# Abdeckung und Adressen
# ---------------------------------------------------------------------------

def test_jede_seite_steht_in_der_liste():
    aufgenommen = {a.vorlage for a in bg.AUFNAHMEN}
    seiten = set(vj.seiten())
    assert sorted(seiten - aufgenommen) == [], "Seiten ohne Bild in scripts/bildgrundlage.py::AUFNAHMEN"
    assert sorted(aufgenommen - seiten) == [], "Vorlagen in AUFNAHMEN, die keine Seite sind"


def test_namen_und_rollen():
    namen = [a.name for a in bg.AUFNAHMEN]
    assert len(namen) == len(set(namen)), "doppelter Name in AUFNAHMEN"
    for a in bg.AUFNAHMEN:
        assert a.rollen and set(a.rollen) <= {bg.BUERO, bg.MONTEUR, bg.ADMIN, bg.ANONYM}, a
        assert "__" not in a.name and a.pfad.startswith("/"), a
    ohne_buero = {a.vorlage for a in bg.AUFNAHMEN if bg.BUERO not in a.rollen}
    assert ohne_buero == {"time_tracking_field.html", "operational_asset_field.html", "login.html", "access_denied.html",
                          "address_import.html"}, "Büro-Rolle überall, wo die Seite eine Büro-Fassung hat und das Büro sie öffnet"


def _pfad(a) -> str:
    """Adresse mit Platzhalter-IDs -- die Seitenrouten zeichnen nur das Gerüst, die Daten lädt die Seite selbst."""
    import re

    return re.sub(r"\{[^}]+\}", "1", a.pfad)


def _anonymer_client(db) -> TestClient:
    app = FastAPI()
    app.include_router(pages_router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


ROLLE_IM_TEST = {bg.BUERO: "buero_finanzen", bg.MONTEUR: "field", bg.ADMIN: "admin"}


def test_jede_adresse_zeichnet_ihre_vorlage(threaded_db_session, router_test_client):
    # bis 1.8.129 legte der Test zuerst ein Konto an (_mit_konto): ohne Konto öffnete /users jeder (Ersteinrichtung)
    clients = {rolle: router_test_client(threaded_db_session, pages_router, role=wert, employee_id=1)
               for rolle, wert in ROLLE_IM_TEST.items()}
    clients[bg.ANONYM] = _anonymer_client(threaded_db_session)
    falsch = []
    for a in bg.AUFNAHMEN:
        for rolle in a.rollen:
            antwort = clients[rolle].get(_pfad(a), follow_redirects=False)
            if a.vorlage == "access_denied.html":
                # Die Sperrseite zeichnet der 403-Handler in app/main.py (in dieser Test-App nicht eingebunden): hier zählt der 403
                ergebnis = antwort.status_code == 403
            else:
                ergebnis = antwort.status_code == 200 and getattr(getattr(antwort, "template", None), "name", None) == a.vorlage
            if not ergebnis:
                falsch.append((a.name, rolle, antwort.status_code, getattr(getattr(antwort, "template", None), "name", None)))
    assert falsch == []


def test_sperrseite_kommt_aus_dem_403_handler():
    text = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert 'name="access_denied.html"' in text and "exc.status_code == 403" in text


def test_monteur_hat_jede_seite_die_er_oeffnen_darf(threaded_db_session, router_test_client):
    client = router_test_client(threaded_db_session, pages_router, role="field", employee_id=1)
    monteur = {a.vorlage for a in bg.AUFNAHMEN if bg.MONTEUR in a.rollen}
    import re

    fehlen = []
    for route in pages_router.routes:
        if "GET" not in getattr(route, "methods", set()) or route.path == "/health":
            continue
        pfad = re.sub(r"\{[^}]+\}", "1", route.path.replace("{data_type}", "properties"))
        antwort = client.get(pfad, follow_redirects=False)
        vorlage = getattr(getattr(antwort, "template", None), "name", None)
        if antwort.status_code == 200 and vorlage and vorlage not in monteur:
            fehlen.append((route.path, vorlage))
    assert fehlen == [], "Seiten, die die Monteurin öffnet, ohne Bild mit Rolle monteur"


# ---------------------------------------------------------------------------
# Vergleich
# ---------------------------------------------------------------------------

def _png(pfad: Path, groesse=(20, 10), farbe=(255, 255, 255, 255), pixel: dict | None = None) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    bild = Image.new("RGBA", groesse, farbe)
    for xy, wert in (pixel or {}).items():
        bild.putpixel(xy, wert)
    bild.save(pfad)


def test_gleiche_bilder_null_pixel(tmp_path, capsys):
    _png(tmp_path / "alt" / "a.png"); _png(tmp_path / "neu" / "a.png")
    assert bg.vergleichen(tmp_path / "alt", tmp_path / "neu", tmp_path / "diff") == 0
    assert not (tmp_path / "diff").exists()
    assert "1 gleich, 0 abweichend" in capsys.readouterr().out


def test_ein_pixel_weicht_ab(tmp_path, capsys):
    _png(tmp_path / "alt" / "a.png"); _png(tmp_path / "alt" / "b.png")
    _png(tmp_path / "neu" / "a.png", pixel={(3, 4): (254, 255, 255, 255)}); _png(tmp_path / "neu" / "b.png")
    assert bg.vergleichen(tmp_path / "alt", tmp_path / "neu", tmp_path / "diff") == 1
    aus = capsys.readouterr().out
    assert "ABWEICHUNG  a.png: 1 Pixel" in aus and "1 gleich, 1 abweichend" in aus
    differenz = Image.open(tmp_path / "diff" / "a.png").convert("RGB")
    assert differenz.getpixel((3, 4)) == (220, 0, 0)
    assert sum(1 for p in differenz.getdata() if p == (220, 0, 0)) == 1
    assert not (tmp_path / "diff" / "b.png").exists()


def test_nur_der_alphakanal_weicht_ab(tmp_path):
    _png(tmp_path / "alt.png"); _png(tmp_path / "neu.png", pixel={(0, 0): (255, 255, 255, 254)})
    assert bg.bilder_vergleichen(tmp_path / "alt.png", tmp_path / "neu.png")[0] == 1


def test_andere_groesse_zaehlt_die_flaeche_ausserhalb(tmp_path):
    _png(tmp_path / "alt.png", groesse=(20, 10)); _png(tmp_path / "neu.png", groesse=(20, 12))
    anzahl, breite, hoehe, _ = bg.bilder_vergleichen(tmp_path / "alt.png", tmp_path / "neu.png")
    assert (anzahl, breite, hoehe) == (40, 20, 12)


def test_fehlende_und_neue_bilder(tmp_path, capsys):
    _png(tmp_path / "alt" / "a.png"); _png(tmp_path / "alt" / "weg.png")
    _png(tmp_path / "neu" / "a.png"); _png(tmp_path / "neu" / "dazu.png")
    assert bg.vergleichen(tmp_path / "alt", tmp_path / "neu", tmp_path / "diff") == 1
    aus = capsys.readouterr().out
    assert "FEHLT       weg.png" in aus and "NEU         dazu.png" in aus


def test_leerer_ordner_ist_keine_gleichheit(tmp_path):
    (tmp_path / "alt").mkdir(); _png(tmp_path / "neu" / "a.png")
    assert bg.vergleichen(tmp_path / "alt", tmp_path / "neu") == 1


def test_vergleichen_ueber_die_kommandozeile(tmp_path, monkeypatch):
    _png(tmp_path / "alt" / "a.png"); _png(tmp_path / "neu" / "a.png", farbe=(0, 0, 0, 255))
    monkeypatch.setattr(sys, "argv", ["bildgrundlage.py", "vergleichen", str(tmp_path / "alt"), str(tmp_path / "neu")])
    assert bg.main() == 1
    assert (tmp_path / "vergleich_alt_neu" / "a.png").exists()


def _chrome(ordner: Path, version: str) -> None:
    (ordner / "bilder.json").write_text(json.dumps({"chrome": version, "bilder": []}), encoding="utf-8")


def test_verschiedene_chrome_versionen_brechen_ab(tmp_path, capsys):
    """Seit 1.8.127: ein anderer Chrome zeichnet anders -- kein Vergleich, Rückgabecode 2, keine Differenzbilder."""
    _png(tmp_path / "alt" / "a.png"); _png(tmp_path / "neu" / "a.png", farbe=(0, 0, 0, 255))
    _chrome(tmp_path / "alt", "Chrome/155.0.8059.40"); _chrome(tmp_path / "neu", "Chrome/156.0.1.2")
    assert bg.vergleichen(tmp_path / "alt", tmp_path / "neu", tmp_path / "diff") == bg.ABBRUCH == 2
    assert "ABBRUCH: verschiedene Chrome-Versionen" in capsys.readouterr().out
    assert not (tmp_path / "diff").exists()


def test_gleiche_chrome_version_vergleicht(tmp_path, capsys):
    _png(tmp_path / "alt" / "a.png"); _png(tmp_path / "neu" / "a.png")
    _chrome(tmp_path / "alt", "Chrome/155.0.8059.40"); _chrome(tmp_path / "neu", "Chrome/155.0.8059.40")
    assert bg.vergleichen(tmp_path / "alt", tmp_path / "neu") == 0
    aus = capsys.readouterr().out
    assert "1 gleich, 0 abweichend" in aus and "Hinweis" not in aus


def test_gleich_benannte_ordner_nehmen_die_oberen_namen(tmp_path):
    _png(tmp_path / "r" / "bilder" / "a.png"); _png(tmp_path / "m" / "bilder" / "a.png", farbe=(0, 0, 0, 255))
    assert bg.vergleichen(tmp_path / "r" / "bilder", tmp_path / "m" / "bilder") == 1
    assert (tmp_path / "m" / "vergleich_r_m" / "a.png").exists()


# ---------------------------------------------------------------------------
# Feste Zeitstempel
# ---------------------------------------------------------------------------

def test_zeitstempel_auf_die_uhr_ausser_dem_sitzungsablauf(db_session):
    from datetime import timedelta

    from app.models import AppUser, CalendarEvent, Customer, UserSession
    from app.sitzungen import neue_sitzung

    nutzer = AppUser(username="z", display_name="Z", role="admin", password_hash="x")
    kunden = [Customer(name=f"K{i}", last_name=f"K{i}") for i in range(3)]
    db_session.add_all([nutzer, *kunden]); db_session.commit()
    beginn = datetime(2026, 10, 14, 14, 0)
    termin = CalendarEvent(title="T", start_at=beginn, end_at=beginn + timedelta(hours=1), owner_user_id=nutzer.id)
    db_session.add(termin)
    neue_sitzung(db_session, nutzer, zweiter_faktor=True)
    db_session.commit()
    ablauf = db_session.query(UserSession).one().expires_at
    uhr = datetime(2026, 10, 14, 8, 0)
    bg._zeitstempel_festsetzen(db_session, uhr)
    db_session.commit(); db_session.expire_all()
    assert [k.created_at for k in kunden] == [uhr] * 3 and nutzer.created_at == uhr
    sitzung = db_session.query(UserSession).one()
    assert sitzung.created_at == uhr and sitzung.expires_at == ablauf
    assert (termin.start_at, termin.end_at, termin.created_at) == (beginn, beginn + timedelta(hours=1), uhr)


# ---------------------------------------------------------------------------
# Stehende Uhr
# ---------------------------------------------------------------------------

def test_stehende_uhr_des_servers(monkeypatch):
    from app import berlin_time

    marke = kt._uhr_marke("2026-10-14 10:00")
    assert marke == "2026-10-14T08:00:00+00:00|fest"
    monkeypatch.setenv(kt.UHR_ENV, marke)
    monkeypatch.setattr(berlin_time, "_utc_now", berlin_time._utc_now)  # nach dem Test wieder die echte Uhr
    kt._uhr_einsetzen()
    erst = berlin_time._utc_now()
    time.sleep(0.05)
    assert berlin_time._utc_now() == erst and erst.isoformat() == "2026-10-14T08:00:00+00:00"
    assert berlin_time.berlin_now().strftime("%Y-%m-%d %H:%M") == "2026-10-14 10:00"


def test_laufende_uhr_bleibt_wie_bisher():
    start, echt = kt._uhr_marke("10:00").split("|")
    assert echt != "fest" and float(echt) > 0 and start.endswith("+00:00")


def test_stehende_uhr_des_browsers():
    zeitpunkt = 1_791_964_800_000
    skript = (kt.BROWSER_UHR_FEST % zeitpunkt).replace("window.", "globalThis.") + "\n" + (kt.BROWSER_UHR_FEST % 5) \
        .replace("window.", "globalThis.") + """
const a = Date.now(); const b = new Date().getTime();
const c = new Date(0).getTime(); const d = new Date(2026, 0, 2).getFullYear();
console.log(JSON.stringify({a, b, c, d, instanz: new Date() instanceof Date}));"""
    ergebnis = node_ausfuehren(skript)
    assert ergebnis == {"a": zeitpunkt, "b": zeitpunkt, "c": 0, "d": 2026, "instanz": True}, "zweites Einsetzen ändert nichts"


# ---------------------------------------------------------------------------
# Wachhund je Schritt
# ---------------------------------------------------------------------------

def test_wachhund_je_schritt_beginnt_neu(monkeypatch):
    abgelaufen = threading.Event()
    monkeypatch.setattr(kt.Wachhund, "_abbrechen", lambda self: abgelaufen.set())
    hund = kt.Wachhund(0.4, "Test", je_schritt=True)
    hund.starten()
    try:
        for _ in range(4):  # 4 x 0,25 s -- länger als das Limit, aber jeder Schritt darunter
            time.sleep(0.25)
            hund.neu_starten()
        assert not abgelaufen.is_set()
        assert abgelaufen.wait(2)
    finally:
        hund.anhalten()


def test_wachhund_ohne_je_schritt_beginnt_nicht_neu(monkeypatch):
    abgelaufen = threading.Event()
    monkeypatch.setattr(kt.Wachhund, "_abbrechen", lambda self: abgelaufen.set())
    hund = kt.Wachhund(0.4, "Test")
    hund.starten()
    try:
        timer = hund._timer
        time.sleep(0.25)
        hund.neu_starten()
        assert hund._timer is timer
        assert abgelaufen.wait(2)
    finally:
        hund.anhalten()


# ---------------------------------------------------------------------------
# Port-Helfer
# ---------------------------------------------------------------------------

def _kandidaten():
    start, ende = kt._kurzlebige_ports()
    return [p for p in range(kt.UNTERSTE_PORTNUMMER, 65536) if not start <= p <= ende]


def _reihenfolge(monkeypatch, *ports):
    kandidaten = _kandidaten()
    indizes = iter([kandidaten.index(p) for p in ports])
    monkeypatch.setattr(kt.secrets, "randbelow", lambda n: next(indizes))


def _zwei_freie_kandidaten() -> list[int]:
    gefunden = []
    for port in _kandidaten()[1000:]:
        if kt._bindbar("127.0.0.1", port) and kt._bindbar("0.0.0.0", port):
            gefunden.append(port)
        if len(gefunden) == 2:
            return gefunden
    pytest.skip("keine zwei freien Ports")


@pytest.mark.parametrize("adresse", ["127.0.0.1", "0.0.0.0"])
def test_port_helfer_ueberspringt_belegte_ports(monkeypatch, adresse):
    belegt, frei = _zwei_freie_kandidaten()
    with socket.socket() as fremd:
        fremd.bind((adresse, belegt))
        fremd.listen()
        _reihenfolge(monkeypatch, belegt, frei)
        assert kt._freier_port() == frei


def test_port_helfer_ueberspringt_reservierte_ports(monkeypatch):
    reserviert, frei = _zwei_freie_kandidaten()
    echt = socket.socket

    class Socket(echt):
        def bind(self, adresse):
            if adresse[1] == reserviert:
                raise OSError(errno.EACCES, "WinError 10013 (nachgestellt)")
            return super().bind(adresse)

    monkeypatch.setattr(kt.socket, "socket", Socket)
    _reihenfolge(monkeypatch, reserviert, frei)
    assert kt._freier_port() == frei


@pytest.mark.skipif(sys.platform != "win32", reason="Portausschlüsse gibt es nur unter Windows")
def test_reservierter_port_ist_nicht_bindbar():
    import re
    import subprocess

    aus = subprocess.run(["netsh", "int", "ipv4", "show", "excludedportrange", "tcp"], capture_output=True, text=True).stdout
    bereiche = [(int(a), int(b)) for a, b in re.findall(r"^\s*(\d+)\s+(\d+)", aus, re.M)]
    if not bereiche:
        pytest.skip("kein Portausschluss auf diesem Rechner")
    assert not kt._bindbar("127.0.0.1", bereiche[0][0])


def test_kein_klicktest_hat_einen_eigenen_port_helfer():
    eigene = [p.name for p in SCRIPTS.glob("*.py") if p.name != "cdp_klicktest.py"
              and ("def _freier_port" in p.read_text(encoding="utf-8") or "bind((\"127.0.0.1\", 0))" in p.read_text(encoding="utf-8"))]
    assert eigene == []


def test_bildgrundlage_steht_in_gitignore():
    zeilen = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "/bildgrundlage/" in zeilen
