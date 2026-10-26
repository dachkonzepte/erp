"""Version 1.8.114 -- Angriffstest unter Last gegen PostgreSQL (Vorgabe vom 16.10.2026, Punkt 1): kleiner Pool, langsame Downloads, viele
gleichzeitige Seiten -- andere Anfragen laufen weiter.

Ein echter uvicorn-Server (Kindprozess) auf einem Wegwerf-Schema der Spielwiese (Regel 27), mit Pool 2, ohne Überlauf, Zeitlimit 3 s
(ERP_DB_POOL_SIZE/ERP_DB_MAX_OVERFLOW/ERP_DB_POOL_TIMEOUT, app/database.py). Die Downloads liest ein eigener Socket langsam (256 KB/s),
der Server muss also über die ganze Prüfzeit weiter senden.

1. Langsame Downloads halten keine Verbindung: vier Downloads zugleich (doppelt so viele wie der Pool), keine Verbindung des Servers
   "idle in transaction" mit einer Transaktion von vor dem Start der Downloads, Abfragen und Seiten daneben mit 200 -- ein gehaltener
   Pool gäbe nach dem Zeitlimit 503 (Punkt 1b).
2. Viele gleichzeitige Seiten (40, darunter /users mit eigener Sitzung) und Abfragen: alle 200 (/users 403 -- seit 1.8.134 nur für
   Administratoren, die Sperrseite wird ebenso gezeichnet), keine 503 (Punkt 1c).
3. Leerer Pool hält nicht den Prozess an: zwei Abfragen warten auf eine gesperrte Tabelle und halten beide Verbindungen; zwei weitere
   Anfragen warten in der Schranke auf den Pool (nach 3 s 503) -- ein laufender Download bekommt dabei weiter Daten: in dieser Zeit
   mindestens eine Sekunde seiner Lesemenge (Punkt 1a). Danach läuft alles wieder.

Seit 1.9.8 ohne Zeitabhängigkeit (Runde 4, Punkt 3): kein Test wartet eine feste Zeit auf einen Zustand -- er wartet, bis der Zustand
eintritt (Sperren in pg_stat_activity, beendete Verbindungen, Antworten), und keine Prüfung misst eine Dauer gegen eine feste Schranke:
bis dahin "unter 2 s", "unter 10 s", "unter 6 s", "Pause unter 1,5 s" -- unter Last brauchte eine Seite 3,5 s und war trotzdem richtig.
Was bleibt, ist das Zeitlimit des Pools im Server (3 s, der Mechanismus unter Test) und Sicherheitsnetze gegen einen hängenden Lauf.
4. Beendete Verbindungen (Neustart von PostgreSQL, pg_terminate_backend): die nächsten Anfragen gelingen (pool_pre_ping, Punkt 1d).

Opt-in wie alle PostgreSQL-Tests (ERP_TEST_POSTGRES_URL), sonst übersprungen."""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from tests.pg_schutz import pg_url_pruefen

ROOT = Path(__file__).resolve().parent.parent
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
pytestmark = [pytest.mark.skipif(not PG_URL, reason="ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in."),
              pytest.mark.zeitgrenze(600)]

DATEI_MB = 24
RATE = 256 * 1024  # Bytes je Sekunde, die ein langsamer Download liest
POOL = {"ERP_DB_POOL_SIZE": "2", "ERP_DB_MAX_OVERFLOW": "0", "ERP_DB_POOL_TIMEOUT": "3"}
SEITEN = ("/", "/projects", "/settings", "/users", "/master-data", "/planning", "/zeiten", "/finanzen", "/kalender",  # seit 1.9.98 „Zeiten“
          "/tasks")
ERWARTET = {"/users": 403}  # seit 1.8.134 nur für Administratoren; das Konto der Tests ist Büro – Finanzen


def _freier_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(url: str, port: int, ordner: Path) -> subprocess.Popen:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ERP_", "DACHKONZEPTE_")) and k != "DATABASE_URL"}
    env.update(POOL, DATABASE_URL=pg_url_pruefen(url), ERP_ENV="test", ERP_DATA_DIR=str(ordner / "data"),
               ERP_SECRET_KEY=secrets.token_urlsafe(32), PYTHONIOENCODING="utf-8")
    log = open(ordner / "server.log", "wb")
    return subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port),
                             "--log-level", "warning"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)


def _beenden(proc: subprocess.Popen) -> None:
    """Nur der eigene Prozess, über seine PID (Regel 12)."""
    if proc.poll() is None:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=30) if os.name == "nt" \
            else proc.kill()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            pass


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    import app.models  # noqa: F401  (registriert die Tabellen an Base.metadata)
    from app import sitzungen
    from app.auth import hash_password
    from app.database import Base
    from app.grunddaten import anlegen
    from app.models import AppUser, Customer

    schema = f"pgtest_last_{uuid.uuid4().hex[:8]}"
    ordner = tmp_path_factory.mktemp("last")
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    db_engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": f"{schema}_test"})
    proc = None
    try:
        Base.metadata.create_all(db_engine)
        with sessionmaker(bind=db_engine)() as db:
            anlegen(db)
            buero = AppUser(username="bea", display_name="Bea", role="buero_finanzen", active=True,
                            password_hash=hash_password("Pw-12345678"))
            kunde = Customer(name="Kundin Last", last_name="Last")
            db.add_all([buero, kunde])
            db.commit()
            wert = sitzungen.neue_sitzung(db, buero)
            db.commit()
            kunde_id = kunde.id
        url = make_url(PG_URL).update_query_dict({"options": f"-csearch_path={schema}", "application_name": schema})
        port = _freier_port()
        proc = _start(url.render_as_string(hide_password=False), port, ordner)
        basis = f"http://127.0.0.1:{port}"
        client = httpx.Client(base_url=basis, cookies={"dk_erp_auth": wert}, timeout=60,
                              headers={"origin": basis, "sec-fetch-site": "same-origin"})
        frist = time.time() + 120
        while True:
            try:
                if client.get("/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            assert proc.poll() is None and time.time() < frist, (ordner / "server.log").read_text(encoding="utf-8", errors="replace")
            time.sleep(0.5)
        inhalt = b"%PDF-1.4\n" + os.urandom(DATEI_MB * 1024 * 1024)
        hoch = client.post(f"/api/customers/{kunde_id}/documents", data={"category": "Sonstiges"},
                           files={"file": ("gross.pdf", inhalt, "application/pdf")})
        assert hoch.status_code == 200, hoch.text
        yield {"client": client, "basis": basis, "port": port, "wert": wert, "kunde": kunde_id, "dokument": hoch.json()["id"],
               "schema": schema, "engine": db_engine, "groesse": len(inhalt), "log": ordner / "server.log"}
        client.close()
    finally:
        if proc is not None:
            _beenden(proc)
        db_engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name LIKE :n"),
                         {"n": f"{schema}%"})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


class LangsamerDownload(threading.Thread):
    """Liest die Antwort mit RATE Bytes je Sekunde über einen Socket mit kleinem Empfangspuffer; empfangen: (Zeit, Bytes) je Lesen."""

    def __init__(self, s: dict):
        super().__init__(daemon=True)
        self.s, self.stop, self.status, self.empfangen, self.fehler = s, threading.Event(), None, [], None
        self.kopf = threading.Event()

    def run(self):
        try:
            with socket.socket() as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)
                sock.connect(("127.0.0.1", self.s["port"]))
                sock.sendall((f"GET /api/customer-documents/{self.s['dokument']}/download HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                              f"Cookie: dk_erp_auth={self.s['wert']}\r\nConnection: close\r\n\r\n").encode())
                puffer = b""
                while b"\r\n\r\n" not in puffer:
                    teil = sock.recv(4096)
                    if not teil:
                        break
                    puffer += teil
                self.status = int(puffer.split(b" ", 2)[1]) if puffer.startswith(b"HTTP/") else -1
                self.kopf.set()
                start = time.monotonic()
                gesamt = 0
                while not self.stop.is_set():
                    teil = sock.recv(4096)
                    if not teil:
                        break
                    gesamt += len(teil)
                    self.empfangen.append((time.monotonic(), len(teil)))
                    warten = start + gesamt / RATE - time.monotonic()
                    if warten > 0:
                        time.sleep(warten)
        except Exception as exc:  # im Test geprüft
            self.fehler = exc
            self.kopf.set()

    def laengste_pause(self, von: float, bis: float) -> float:
        zeiten = [von] + [t for t, _ in self.empfangen if von <= t <= bis] + [bis]
        return max(b - a for a, b in zip(zeiten, zeiten[1:]))

    def bytes_bis(self, bis: float) -> int:
        return sum(n for t, n in self.empfangen if t <= bis)


def _downloads(s, anzahl):
    laeufe = [LangsamerDownload(s) for _ in range(anzahl)]
    for d in laeufe:
        d.start()
    for d in laeufe:
        assert d.kopf.wait(30), "kein Antwortkopf"
    return laeufe


def _stoppen(laeufe):
    for d in laeufe:
        d.stop.set()
    for d in laeufe:
        d.join(10)


def _anfrage(s, pfad):
    t0 = time.monotonic()
    with httpx.Client(base_url=s["basis"], cookies={"dk_erp_auth": s["wert"]}, timeout=30) as c:
        antwort = c.get(pfad, follow_redirects=False)
    return pfad, antwort.status_code, time.monotonic() - t0


def _jetzt_in_der_datenbank(s):
    with s["engine"].connect() as conn:
        return conn.execute(text("SELECT now()")).scalar()


def _haengende_transaktionen(s, vor) -> int:
    """Verbindungen des Servers, die in einer offenen Transaktion ruhen, die vor `vor` (Zeit der Datenbank) begann -- seit 1.9.8 statt
    "seit über 1 s": ein Download, der seine Verbindung hielte, hätte seine Transaktion vor dem Start der Prüfung begonnen; eine Abfrage
    daneben beginnt danach, auch wenn sie unter Last länger ruht."""
    with s["engine"].connect() as conn:
        return conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE application_name = :n AND state = 'idle in transaction' "
                                 "AND xact_start < :vor"), {"n": s["schema"], "vor": vor}).scalar()


def _bis(bedingung, was: str, sicherheitsnetz: float = 120.0):
    """Wartet, bis bedingung() wahr ist (Synchronisation); sicherheitsnetz begrenzt nur einen hängenden Lauf."""
    ende = time.monotonic() + sicherheitsnetz
    while not bedingung():
        assert time.monotonic() < ende, f"{was} -- nach {sicherheitsnetz:.0f} s nicht eingetreten"
        time.sleep(0.05)


def test_langsame_downloads_halten_keine_verbindung(server):
    s = server
    laeufe = _downloads(s, 4)
    try:
        _bis(lambda: all(d.empfangen for d in laeufe), "nicht jeder Download hat Daten bekommen")
        vor = _jetzt_in_der_datenbank(s)
        haengend, ergebnisse = [], []
        for _ in range(15):  # Runden, keine Dauer
            haengend.append(_haengende_transaktionen(s, vor))
            ergebnisse += [_anfrage(s, f"/api/customers/{s['kunde']}"), _anfrage(s, "/projects"), _anfrage(s, "/health")]
        assert max(haengend) == 0, f"Verbindungen 'idle in transaction' seit vor den Prüfrunden: {haengend}"
        assert [d.status for d in laeufe] == [200] * 4, [d.status for d in laeufe]
        assert all(status == 200 for _, status, _ in ergebnisse), [e for e in ergebnisse if e[1] != 200]
        jetzt = time.monotonic()
        assert all(0 < d.bytes_bis(jetzt) < s["groesse"] for d in laeufe), "die Downloads liefen nicht über die ganze Prüfzeit"
        assert all(d.is_alive() and d.fehler is None for d in laeufe), "ein Download endete während der Prüfung"
    finally:
        _stoppen(laeufe)


def _rueckfaelle(s) -> list[str]:
    """Zeilen im Protokoll des Servers, in denen Seitendaten auf ihren Rückfallwert fielen (app/seitendaten.py) -- eine Seite mit 200,
    aber ohne Akzentfarbe, Module oder Logo, weil keine Verbindung zu bekommen war."""
    return [z for z in s["log"].read_text(encoding="utf-8", errors="replace").splitlines() if "Seitendaten:" in z]


def test_viele_gleichzeitige_seiten_und_abfragen(server):
    s = server
    vorher = len(_rueckfaelle(s))
    pfade = [SEITEN[i % len(SEITEN)] for i in range(40)] + [f"/api/customers/{s['kunde']}"] * 20 + ["/api/settings/general"] * 10
    with ThreadPoolExecutor(max_workers=len(pfade)) as pool:
        ergebnisse = list(pool.map(lambda p: _anfrage(s, p), pfade))
    falsch = [e for e in ergebnisse if e[1] != ERWARTET.get(e[0], 200)]
    assert not falsch, f"(Pfad, Status, Dauer): {falsch}"
    assert _rueckfaelle(s)[vorher:] == [], "Seitendaten fielen unter Last auf Rückfallwerte"


def test_ein_leerer_pool_haelt_den_prozess_nicht_an(server):
    s = server
    [download] = _downloads(s, 1)
    sperre = s["engine"].connect()
    blockiert = []
    try:
        assert download.status == 200
        sperre.execute(text("LOCK TABLE customers IN ACCESS EXCLUSIVE MODE"))
        with ThreadPoolExecutor(max_workers=4) as pool:
            gesperrt = [pool.submit(_anfrage, s, f"/api/customers/{s['kunde']}") for _ in range(2)]

            def wartend():
                with s["engine"].connect() as conn:
                    return conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE application_name = :n "
                                             "AND wait_event_type = 'Lock'"), {"n": s["schema"]}).scalar()
            _bis(lambda: wartend() == 2, "nicht zwei Abfragen warten auf die Sperre -- Pool nicht leer")
            von = time.monotonic()
            ohne_pool = [pool.submit(_anfrage, s, "/health"), pool.submit(_anfrage, s, "/projects")]
            blockiert = [f.result(timeout=120) for f in ohne_pool]  # kommen nach dem Zeitlimit des Pools zurück
            bis = min(von + b[2] for b in blockiert)
            gelesen = download.bytes_bis(bis) - download.bytes_bis(von)
            sperre.rollback()
            frei = [f.result(timeout=120) for f in gesperrt]
        # die Downloads lesen RATE Bytes je Sekunde (hinter dem Plan ohne Pause); stünde der Prozess still, kämen nur die Puffer
        assert gelesen >= RATE, f"der Download bekam nur {gelesen} Bytes, während die Schranke auf den Pool wartete"
        assert [b[1] for b in blockiert] == [503, 503], blockiert
        assert [f[1] for f in frei] == [200, 200], frei
        assert _anfrage(s, "/health")[1] == 200 and _anfrage(s, "/projects")[1] == 200
    finally:
        sperre.close()
        _stoppen([download])


def test_beendete_verbindungen_ersetzt_der_pool(server):
    s = server
    assert _anfrage(s, f"/api/customers/{s['kunde']}")[1] == 200
    with s["engine"].begin() as conn:
        beendet = conn.execute(text("SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity WHERE application_name = :n"),
                               {"n": s["schema"]}).scalar()
    assert beendet >= 1

    def verbleibend():
        with s["engine"].connect() as conn:
            return conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE application_name = :n"), {"n": s["schema"]}).scalar()
    _bis(lambda: verbleibend() == 0, "die beendeten Verbindungen sind noch da")  # bis dahin eine feste halbe Sekunde
    ergebnisse = [_anfrage(s, f"/api/customers/{s['kunde']}"), _anfrage(s, "/projects"), _anfrage(s, "/health")]
    assert [e[1] for e in ergebnisse] == [200, 200, 200], ergebnisse
