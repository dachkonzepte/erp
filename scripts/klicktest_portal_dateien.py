"""Klicktest: Dateien im Kundenportal im echten Browser (1.11.34, Stufe P2b; Bauplan P2, B6 „Zu belegen, bevor die Seiten entstehen“).

Wie klicktest_portal_seiten.py: der echte Portal-Dienst in einem eigenen Prozess gegen ein Wegwerf-Schema pgklick_<…> (Testrolle dkportal_test), der
Postbote des ERP in diesem Prozess (Codes an die Attrappe von Microsoft 365, dazu die Kopien -- app/portal_kopien.py), davor die Attrappe von nginx
(scripts/nginx_attrappe.py: X-Accel-Redirect mit den Kopfzeilen des internal-Blocks aus der nginx-Datei). Chrome spricht nur mit der Attrappe.
Die Unterlagen sind erfunden: ein PDF (ReportLab) und ein Foto mit EXIF, beide als Dokument der Kundenakte, je mit Freigabe; eine dritte Freigabe ohne
Anforderung.

    Anmelden     Link -> Code aus der Mail -> „Guten Tag …“ (wie im Portal)
    Kopien       der Postbote legt beide Kopien an (PDF byte-gleich, Foto ohne EXIF)
    PDF          anfordern (fetch auf der Seite des Portals) -> /datei/<n> im selben Tab: Chrome zeigt das PDF (Inhaltstyp application/pdf, Betrachter
                 eingebettet), keine Verletzung der CSP; Bild davon
    Foto         anfordern -> /datei/<n>: Chrome zeigt das Bild (image/jpeg, Breite > 0)
    Herunterladen  /datei/<n>/herunterladen: ein Download mit dem Namen aus dem Titel („Dachplan Süd.pdf“), nie dem ursprünglichen Dateinamen
    Ohne Anforderung  /datei/<dritte>: 404 „nicht_gefunden“; /_portal_dateien/<Name> direkt: 404

AUFRUF (aus dem Projektordner; braucht ERP_TEST_POSTGRES_URL und die Testrolle dkportal_test):

    .venv\\Scripts\\python.exe scripts\\klicktest_portal_dateien.py [--arbeitsordner PFAD] [--chrome PFAD] [--zeitlimit SEK] [--offen-lassen]

Rückgabecode wie scripts/cdp_klicktest.py (0 wie erwartet, 1 Abweichung, 2 nicht gestartet, 3 Zeitlimit).
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import (  # noqa: E402
    GEGENPROBE_MARKER, MARKER, ROOT, ZEITLIMIT_GEGENPROBE, Wachhund, _chrome_pfad, _chrome_port, _freier_port, _lauf, beenden, gegenprobe_im_code,
    klicktest_ordner,
)
import klicktest_portal_seiten as seiten  # noqa: E402
import nginx_attrappe  # noqa: E402

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LINK = secrets.token_urlsafe(32)
GEHEIM = "erfundener-ort-im-foto"


def _pdf() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    aus = io.BytesIO()
    c = canvas.Canvas(aus, pagesize=A4)
    c.setTitle("Dachplan Süd")
    c.drawString(72, 760, "Erfundene Unterlage für den Klicktest – Dachplan Süd")
    c.showPage()
    c.save()
    return aus.getvalue()


def _foto() -> bytes:
    from PIL import Image
    exif = Image.Exif()
    exif[0x010E] = GEHEIM
    aus = io.BytesIO()
    Image.new("RGB", (320, 240), (180, 60, 40)).save(aus, "JPEG", exif=exif.tobytes())
    return aus.getvalue()


def befuellen(erp, daten: Path) -> dict:
    """Schema wie im Klicktest der Seiten (Tabellen, Funktionen, Rechte, Grunddaten, Firmendaten, Modul, Microsoft 365 als Attrappe), ein Kunde mit Zugang,
    zwei Dokumente der Kundenakte mit Datei und je einer Freigabe, ein drittes mit Freigabe (nie angefordert)."""
    from datetime import date, timedelta

    from sqlalchemy import select, text
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401
    from app import grunddaten
    from app.berlin_time import utc_jetzt
    from app.database import Base
    from app.email_sending import load_smtp_settings, update_graph_settings
    from app.models import Customer, CustomerDocument, DocumentCategory, EnabledModule, PortalFreigabe, PortalZugang
    from app.portal import pruefwerte, rechte
    from app.portal.main import kopf_der_migrationen
    from app.settings import load_general_settings

    Base.metadata.create_all(erp)
    with erp.begin() as c:
        aktuell = c.execute(text("SELECT current_schema()")).scalar()
        c.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        c.execute(text("INSERT INTO alembic_version VALUES (:k)"), {"k": kopf_der_migrationen()})
        rechte.setzen(c, rolle=seiten.TESTROLLE, schema=aktuell)
    with Session(erp) as db:
        grunddaten.anlegen(db)
        db.commit()
        s = load_general_settings(db)
        s.company_name, s.street, s.postal_code, s.city = "Muster Bedachung GmbH", "Dachweg 1", "12345", "Musterstadt"
        s.phone, s.email = "0123 456789", "info@example.invalid"
        db.add(EnabledModule(module_key="kundenportal", enabled=True))
        m = load_smtp_settings(db)
        m.send_method = "graph_oauth2"
        update_graph_settings(db, tenant_id="mandant-attrappe", client_id="anwendung-attrappe", sender_mailbox="buero@example.invalid",
                              client_secret="geheim-attrappe")
        jetzt = utc_jetzt()
        k = Customer(portal_aktiv=True, name="Herr Dr. Max Muster", salutation="Herr", title="Dr.", first_name="Max", last_name="Muster",
                     email="max@example.invalid")
        db.add(k)
        db.flush()
        db.add(PortalZugang(customer_id=k.id, email="max@example.invalid", email_anzeige="m***@example.invalid", link_sha256=pruefwerte.link(LINK),
                            link_erzeugt_am=jetzt, gueltig_bis=jetzt + timedelta(days=200), angelegt_am=jetzt, angelegt_von_name="Klicktest"))
        kategorie = db.scalar(select(DocumentCategory.id).order_by(DocumentCategory.id).limit(1))
        ordner = daten / "customer_files" / str(k.id)
        ordner.mkdir(parents=True, exist_ok=True)
        ids, inhalte = {}, {}
        for schluessel, titel, inhalt, original in (("pdf", "Dachplan Süd", _pdf(), "intern-dachplan-v3.pdf"),
                                                    ("foto", "Foto Dachfläche", _foto(), "IMG_0815.jpg"),
                                                    ("ohne", "Ohne Anforderung", _pdf(), "intern-anderes.pdf")):
            gespeichert = uuid.uuid4().hex
            (ordner / gespeichert).write_bytes(inhalt)
            d = CustomerDocument(customer_id=k.id, category_id=kategorie, original_filename=original, stored_filename=gespeichert, file_size=len(inhalt))
            db.add(d)
            db.flush()
            f = PortalFreigabe(customer_id=k.id, art="dokument", quelle="customer_documents", quelle_id=d.id, titel=titel, datum=date(2026, 11, 26),
                               freigegeben_am=jetzt, freigegeben_von_name="Klicktest")
            db.add(f)
            db.flush()
            ids[schluessel], inhalte[schluessel] = f.id, inhalt
        db.commit()
    return {"link": LINK, "ids": ids, "inhalte": inhalte}


class Postbote:
    """Der Postbote in diesem Prozess: alle 0,3 s Codes und Kopien (app/portal_postbote.py::alle(), app/portal_kopien.py::abgleich())."""

    def __init__(self, erp, kopien: Path):
        self.erp, self.kopien, self.halt, self.fehler = erp, kopien, threading.Event(), []
        self.faden = threading.Thread(target=self._laufen, daemon=True)

    def _laufen(self):
        from sqlalchemy.orm import Session

        from app import portal_kopien, portal_postbote
        while not self.halt.wait(0.3):
            try:
                with Session(self.erp) as db:
                    portal_postbote.alle(db)
                    portal_kopien.abgleich(db, self.kopien, voll=True)
            except Exception as exc:  # noqa: BLE001
                self.fehler.append(type(exc).__name__)


def _bereit(port: int, host: str, timeout: float = 60) -> bool:
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        try:
            r = urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"Host": host}), timeout=2)
            if r.status == 200:
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    return False


ANFORDERN = """fetch('/api/datei/anfordern',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({freigabe:%d})})
.then(r=>r.status+' '+r.headers.get('content-type'))"""


async def pruefen(tab, seed, p):
    ids, kopien = seed["ids"], seed["kopien"]
    await tab.cmd("Page.setDownloadBehavior", behavior="allow", downloadPath=str(tab.shots.parent / "downloads"))
    await seiten._vorab(tab, seiten.ERSATZ)
    # Anmelden wie der Kunde
    code = await seiten.bis_c(tab, p, "Anmelden", seed["link"], "m***@example.invalid")
    p.pruefe("Code aus der Mail", bool(code), True)
    await seiten.eintippen(tab, code or "")
    await tab.js("document.getElementById('c-anmelden').click()")
    p.pruefe("D: angemeldet", await tab.warten(seiten.sichtbar("seite-d"), 20), True)
    # Kopien des Postboten
    ende = time.monotonic() + 20
    while time.monotonic() < ende and len([x for x in kopien.iterdir() if x.suffix in (".pdf", ".jpg")]) < 3:
        await asyncio.sleep(0.3)
    namen = sorted(x.name for x in kopien.iterdir() if x.suffix in (".pdf", ".jpg"))
    # seit 1.11.44: zum Foto dazu seine Vorschau (400 px) im selben Ordner
    p.pruefe("Kopien angelegt (2 PDF, 1 Foto mit Vorschau)", sorted(n.rsplit(".", 1)[1] for n in namen), ["jpg", "jpg", "pdf", "pdf"])
    foto = next((kopien / n for n in namen if n.endswith(".jpg")), None)
    p.pruefe("Foto ohne EXIF", foto is not None and GEHEIM.encode() not in foto.read_bytes(), True)
    p.pruefe("D: keine Verletzung der CSP", await tab.js("window.__dkErsatz?window.__dkErsatz.csp:0"), 0)

    # PDF ansehen
    p.pruefe("PDF anfordern", await tab.js(ANFORDERN % ids["pdf"]), "200 application/json")
    await tab.cmd("Page.navigate", url=tab.base + f"/datei/{ids['pdf']}")
    p.pruefe("PDF: Chrome zeigt es (application/pdf)", await tab.warten("document.contentType==='application/pdf'", 20), True)
    # den Betrachter selbst sieht die Seite nicht (Shadow-DOM von Chrome) -- Beleg sind Inhaltstyp, kein Download und das Bild
    await asyncio.sleep(1.5)
    await tab.bild("pdf_ansehen")
    p.pruefe("PDF: kein Download beim Ansehen", [d for d in tab.downloads if f"/datei/{ids['pdf']}" in (d["url"] or "")
                                                 and not d["url"].endswith("/herunterladen")], [])

    # Foto ansehen (die Seite des Portals zuerst wieder -- dort läuft fetch mit der CSP des Portals)
    await seiten.laden(tab, "/", seiten.sichtbar("seite-d"))
    p.pruefe("Foto anfordern", await tab.js(ANFORDERN % ids["foto"]), "200 application/json")
    await tab.cmd("Page.navigate", url=tab.base + f"/datei/{ids['foto']}")
    p.pruefe("Foto: Chrome zeigt es (image/jpeg)", await tab.warten("document.contentType==='image/jpeg'", 20), True)
    p.pruefe("Foto: Bild geladen", await tab.warten("!!document.images[0]&&document.images[0].naturalWidth===320", 10), True)
    await tab.bild("foto_ansehen")

    # Herunterladen: Name aus dem Titel
    await seiten.laden(tab, "/", seiten.sichtbar("seite-d"))
    vorher = len(tab.downloads)
    await tab.cmd("Page.navigate", url=tab.base + f"/datei/{ids['pdf']}/herunterladen")
    ende = time.monotonic() + 15
    while time.monotonic() < ende and len(tab.downloads) == vorher:
        await tab.nachlesen()
    neu = tab.downloads[vorher:]
    p.pruefe("Herunterladen: Name aus dem Titel", [d["name"] for d in neu], ["Dachplan Süd.pdf"])
    datei = tab.shots.parent / "downloads"
    ende = time.monotonic() + 15
    while time.monotonic() < ende and not any(x.suffix == ".pdf" for x in datei.glob("*")):
        await asyncio.sleep(0.2)
    geladen = next((x for x in datei.glob("*.pdf")), None)
    p.pruefe("Herunterladen: Inhalt = Quelle (byte-gleich)", geladen is not None and geladen.read_bytes() == seed["inhalte"]["pdf"], True)

    # ohne Anforderung, interner Weg
    await seiten.laden(tab, "/", seiten.sichtbar("seite-d"))
    await tab.cmd("Page.navigate", url=tab.base + f"/datei/{ids['ohne']}")
    p.pruefe("ohne Anforderung: 404", await tab.warten("document.body&&document.body.innerText.includes('nicht_gefunden')", 10), True)
    await tab.cmd("Page.navigate", url=tab.base + f"/_portal_dateien/{namen[0]}")
    p.pruefe("interner Weg direkt: 404", await tab.warten("document.body&&document.body.innerText.includes('404')", 10), True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Klicktest: Dateien im Kundenportal")
    parser.add_argument("--arbeitsordner", type=Path)
    parser.add_argument("--chrome")
    parser.add_argument("--zeitlimit", type=float)
    parser.add_argument("--offen-lassen", action="store_true")
    args = parser.parse_args()

    pg_url = os.environ.get("ERP_TEST_POSTGRES_URL")
    if not pg_url:
        print("ERP_TEST_POSTGRES_URL fehlt -- das Portal läuft nur gegen PostgreSQL.")
        return 2
    gegenprobe = gegenprobe_im_code()
    grenzen = [(args.zeitlimit, "--zeitlimit")] if args.zeitlimit else []
    if gegenprobe:
        grenzen.append((ZEITLIMIT_GEGENPROBE, f"Gegenprobe läuft, Marker {GEGENPROBE_MARKER} in {gegenprobe}"))
    wachhund = Wachhund(*min(grenzen)) if grenzen else None
    if wachhund:
        wachhund.starten()

    ordner = klicktest_ordner(args.arbeitsordner, "erp-klicktest-")
    if ordner.exists() and any(ordner.iterdir()):
        raise SystemExit(f"Arbeitsordner ist nicht leer: {ordner}")
    for sub in ("data", "shots", "chrome-profile", "kopien", "downloads"):
        (ordner / sub).mkdir(parents=True, exist_ok=True)
    (ordner / MARKER).write_text("Wegwerf-Instanz eines Klicktests, darf gelöscht werden.\n", encoding="utf-8")

    graph_port = seiten._graph_starten()
    os.environ.update({"ERP_ENV": "test", "ERP_DATA_DIR": str(ordner / "data"), "ERP_SECRET_KEY": secrets.token_urlsafe(32),
                       "DATABASE_URL": "sqlite:///" + (ordner / "erp.db").as_posix(),
                       "ERP_TEST_GRAPH": f"http://127.0.0.1:{graph_port}", "PYTHONIOENCODING": "utf-8"})
    from sqlalchemy import create_engine, text

    schema = f"pgklick_{uuid.uuid4().hex[:8]}"
    verwaltung = create_engine(pg_url)
    with verwaltung.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
        c.execute(text(f"COMMENT ON SCHEMA {schema} IS 'Klicktest Dateien im Kundenportal, pid {os.getpid()}'"))
    erp = seiten._engine(pg_url, schema)
    server = chrome = postbote = attrappe = None
    try:
        import app.customer_documents
        assert app.customer_documents.CUSTOMER_ROOT == ordner / "data" / "customer_files"  # ERP_DATA_DIR ist vor dem ersten Import gesetzt
        seed = befuellen(erp, ordner / "data")
        seed["kopien"] = ordner / "kopien"
        postbote = Postbote(erp, ordner / "kopien")
        postbote.faden.start()
        port = _freier_port()
        attrappe = nginx_attrappe.Attrappe(port, ordner / "kopien")
        aussen = attrappe.port
        env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        env.update({"PORTAL_KLICK_SCHEMA": schema, "PORTAL_HERKUNFT": f"http://localhost:{aussen}", "PORTAL_BREMSE_SCHLUESSEL": secrets.token_hex(32),
                    "DATABASE_URL": pg_url})
        with open(ordner / "portal.out.log", "ab") as out:
            server = subprocess.Popen([sys.executable, str(Path(seiten.__file__).resolve()), "--portal-server", str(port)], env=env, cwd=ROOT,
                                      stdout=out, stderr=subprocess.STDOUT)
        if wachhund:
            wachhund.kinder.append(server)
        if not _bereit(port, f"localhost:{aussen}"):
            print(f"Portal-Dienst antwortet nicht, siehe {ordner / 'portal.out.log'}")
            return 2
        attrappe.starten()
        print(f"Arbeitsordner {ordner}\nPortal über nginx (Attrappe) http://localhost:{aussen}  Schema {schema}", flush=True)
        chrome = subprocess.Popen([_chrome_pfad(args.chrome), "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={ordner / 'chrome-profile'}",
                                   "--no-first-run", "--no-default-browser-check", "--disable-extensions", "about:blank"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if wachhund:
            wachhund.kinder.append(chrome)
        cdp_port = _chrome_port(chrome, ordner / "chrome-profile", 30)
        if cdp_port is None:
            print("Chrome antwortet nicht auf dem CDP-Port.")
            return 2
        (ordner / "pids.txt").write_text(f"server={server.pid} chrome={chrome.pid}\n", encoding="utf-8")
        ok = asyncio.run(_lauf(pruefen, seed, cdp_port, f"http://localhost:{aussen}", ordner / "shots", None, wachhund))
        if postbote.fehler:
            print(f"XX  Postbote: {sorted(set(postbote.fehler))}")
            ok = False
        return 0 if ok else 1
    finally:
        if wachhund:
            wachhund.anhalten()
        if postbote is not None:
            postbote.halt.set()
            postbote.faden.join(5)
        if attrappe is not None:
            try:
                attrappe.beenden()
            except Exception:  # noqa: BLE001
                pass
        if not args.offen_lassen:
            for proc in (chrome, server):
                if proc is not None:
                    beenden(proc.pid)
        erp.dispose()
        with verwaltung.begin() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n AND pid <> pg_backend_pid()"), {"n": schema})
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        verwaltung.dispose()


if __name__ == "__main__":
    sys.exit(main())
