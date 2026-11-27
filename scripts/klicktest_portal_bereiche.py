"""Klicktest: die Bereiche des Kundenportals im echten Browser (1.11.46, Stufe P2e; Entwürfe bildgrundlage/Entwürfe/P2/, Seiten 1–5).

Wie klicktest_portal_dateien.py: der echte Portal-Dienst in einem eigenen Prozess gegen ein Wegwerf-Schema pgklick_<…> (Testrolle dkportal_test), davor
die Attrappe von nginx, der Postbote des ERP in diesem Prozess (Codes, Kopien mit Vorschau, Schaufenster). Alle Daten erfunden: Herr Dr. Muster mit einem
Auftrag „Steildachsanierung mit Aufsparrendämmung“ (A-2026-0118, Musterweg 12), drei festgeschriebenen Rechnungen (eine teilweise bezahlt, eine bezahlt,
eine offen), festen Baustellentagen ab heute und vergangenen, einem PDF der Kundenakte und zwei Fotos -- je mit Freigabe.

    Übersicht    Gruß, vier Kacheln mit den Zahlen vom Server, Stand „heute, …“; eine Kachel führt in ihren Bereich
    Rechnungen   Gruppe „Auftrag A-2026-0118 · Steildachsanierung mit Aufsparrendämmung“, darunter die Adresse; Kennzeichen je Rechnung; offen insgesamt
    Termine      kommende Tage mit „heute“, vergangene darunter; Hinweis zu Regen und Sturm
    Unterlagen   „Allgemeine Unterlagen“; „Ansehen“ öffnet das PDF im selben Tab, „Zurück“ führt in den Bereich zurück; zurückgenommen: „Nicht mehr verfügbar.“
    Fotos        Vorschauen laden (400 px), ein Foto groß (800 px), weiter und zurück
    Bilder       jeder Bereich in 1280 px hell und dunkel und 390 px hell; 390 px ohne Überlauf, unten die Leiste der Bereiche; keine Verletzung der CSP

AUFRUF (aus dem Projektordner; braucht ERP_TEST_POSTGRES_URL und die Testrolle dkportal_test):

    .venv\\Scripts\\python.exe scripts\\klicktest_portal_bereiche.py [--arbeitsordner PFAD] [--chrome PFAD] [--zeitlimit SEK] [--offen-lassen]

Rückgabecode wie scripts/cdp_klicktest.py (0 wie erwartet, 1 Abweichung, 2 nicht gestartet, 3 Zeitlimit).
"""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import secrets
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import (  # noqa: E402
    GEGENPROBE_MARKER, MARKER, ROOT, ZEITLIMIT_GEGENPROBE, Wachhund, _chrome_pfad, _chrome_port, _freier_port, _lauf, beenden, gegenprobe_im_code,
    klicktest_ordner,
)
import klicktest_portal_dateien as dateien  # noqa: E402
import klicktest_portal_seiten as seiten  # noqa: E402
import nginx_attrappe  # noqa: E402

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LINK = secrets.token_urlsafe(32)
BETREFF = "Steildachsanierung mit Aufsparrendämmung"


def _foto(breite=800, hoehe=600, farbe=(120, 90, 60)) -> bytes:
    from PIL import Image
    aus = io.BytesIO()
    Image.new("RGB", (breite, hoehe), farbe).save(aus, "JPEG", quality=90)
    return aus.getvalue()


def befuellen(erp, daten: Path) -> dict:
    from datetime import date, timedelta
    from decimal import Decimal

    from sqlalchemy import select, text
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401
    from app import grunddaten
    from app.berlin_time import berlin_today, utc_jetzt
    from app.database import Base
    from app.email_sending import load_smtp_settings, update_graph_settings
    from app.invoices import create_abschlag_pauschal, finalize_and_send_invoice, update_invoice_header
    from app.models import (Customer, CustomerDocument, DocumentCategory, Employee, EnabledModule, Order, OrderItem, PlanningSlot, PlanningSlotEmployee,
                            PortalFreigabe, PortalZugang, Project, Property, WorkPreparation)
    from app.payments import Line, book_payment
    from app.portal import pruefwerte, rechte
    from app.portal.main import kopf_der_migrationen
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.settings import load_general_settings
    from tests.quellangebot import quell_angebot

    Base.metadata.create_all(erp)
    with erp.begin() as c:
        aktuell = c.execute(text("SELECT current_schema()")).scalar()
        c.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        c.execute(text("INSERT INTO alembic_version VALUES (:k)"), {"k": kopf_der_migrationen()})
        rechte.setzen(c, rolle=seiten.TESTROLLE, schema=aktuell)
    heute = berlin_today()
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
        o = Property(customer_id=k.id, name="Wohnhaus", street="Musterweg 12", postal_code="52531", city="Übach-Palenberg")
        db.add(o)
        db.flush()
        p = Project(project_number="P-2026-0118", name="Interner Projekttitel", customer_id=k.id, property_id=o.id,
                    pipeline_column_id=default_pipeline_column_id(db))
        db.add(p)
        db.flush()
        auftrag = Order(order_number="A-2026-0118", project_id=p.id, source_quote_id=quell_angebot(db, p.id, "A-2026-0118"),
                        quote_number_snapshot="ANG-2026-0118", title=BETREFF,
                        vat_rate=Decimal("19.00"), customer_name=k.name, customer_id=k.id)
        db.add(auftrag)
        db.flush()
        db.add(OrderItem(order_id=auftrag.id, sort_order=10, position_number="1", short_text="Dacheindeckung", quantity=Decimal("100"), unit="m²",
                         unit_price=Decimal("50")))
        db.commit()
        rechnungen = []
        for netto, faellig in (("2000", heute + timedelta(days=7)), ("1000", heute + timedelta(days=7)), ("500", heute - timedelta(days=3))):
            r = create_abschlag_pauschal(db, db.get(Order, auftrag.id), lump_sum_net=Decimal(netto), due_date=faellig)
            update_invoice_header(db, r, service_period_start=heute - timedelta(days=30), service_period_end=heute - timedelta(days=1))
            rechnungen.append(finalize_and_send_invoice(db, r))
        teil, bezahlt, offen = rechnungen
        for r, betrag in ((teil, "1000"), (bezahlt, "1190")):
            book_payment(db, customer_id=k.id, received_on=heute, amount=Decimal(betrag), note=None, lines=[Line(r.id, zahlung=Decimal(betrag))],
                         user_name="Klicktest")
        av = WorkPreparation(order_id=auftrag.id)
        db.add(av)
        db.flush()
        mensch = Employee(first_name="Erfunden", last_name="Monteur")
        db.add(mensch)
        db.flush()
        for von, bis in ((heute, heute + timedelta(days=2)), (heute - timedelta(days=21), heute - timedelta(days=17))):
            slot = PlanningSlot(preparation_id=av.id, start_date=von, end_date=bis, status="fest", art="baustelle")
            db.add(slot)
            db.flush()
            db.add(PlanningSlotEmployee(slot_id=slot.id, employee_id=mensch.id))
        kategorie = db.scalar(select(DocumentCategory.id).order_by(DocumentCategory.id).limit(1))
        ordner = daten / "customer_files" / str(k.id)
        ordner.mkdir(parents=True, exist_ok=True)
        ids = {}
        for schluessel, titel, inhalt, art in (("pdf", "Förderunterlagen", dateien._pdf(), "dokument"), ("foto1", "Foto Dach Süd", _foto(), "foto"),
                                               ("foto2", "Foto Dach Nord", _foto(farbe=(60, 90, 120)), "foto")):
            gespeichert = uuid.uuid4().hex
            (ordner / gespeichert).write_bytes(inhalt)
            d = CustomerDocument(customer_id=k.id, category_id=kategorie, original_filename="intern.bin", stored_filename=gespeichert, file_size=len(inhalt))
            db.add(d)
            db.flush()
            f = PortalFreigabe(customer_id=k.id, art=art, quelle="customer_documents", quelle_id=d.id, titel=titel, datum=date(2026, 11, 20),
                               freigegeben_am=jetzt, freigegeben_von_name="Klicktest")
            db.add(f)
            db.flush()
            ids[schluessel] = f.id
        for r in rechnungen:
            f = PortalFreigabe(customer_id=k.id, art="rechnung", quelle="invoices", quelle_id=r.id, titel=f"Abschlagsrechnung {r.invoice_number}",
                               datum=r.invoice_date, freigegeben_am=jetzt, freigegeben_von_name="Klicktest")
            db.add(f)
            db.flush()
            ids[f"r{r.id}"] = f.id
        db.commit()
        nummern = [r.invoice_number for r in rechnungen]
    return {"link": LINK, "ids": ids, "nummern": nummern, "heute": heute}


class Postbote(dateien.Postbote):
    """Wie im Klicktest der Dateien, dazu das Schaufenster (app/portal_schaufenster.py)."""

    def _laufen(self):
        from sqlalchemy.orm import Session

        from app import portal_kopien, portal_postbote, portal_schaufenster
        while not self.halt.wait(0.3):
            try:
                with Session(self.erp) as db:
                    portal_postbote.alle(db)
                    portal_kopien.abgleich(db, self.kopien, voll=True)
                    portal_schaufenster.alle(db)
            except Exception as exc:  # noqa: BLE001
                self.fehler.append(type(exc).__name__)


def _t(kennung: str) -> str:
    return f"(document.getElementById('{kennung}')||{{}}).textContent||''"


GRUPPEN = "[...document.querySelectorAll('#{liste} .gruppe-kopf')].map(g=>[...g.querySelectorAll('h2,.gruppe-titel p')].map(x=>x.textContent))"


async def reiter(tab, name: str, bereit: str) -> bool:
    await tab.js(f"document.querySelector('.reiter [data-bereich=\"{name}\"]').click()")
    return await tab.warten(bereit, 20)


async def alle_bilder(tab, p, name: str) -> None:
    for breite, hoehe, mobil, thema in ((1280, 900, False, "hell"), (1280, 900, False, "dunkel"), (390, 844, True, "hell")):
        await seiten.ansicht(tab, breite, hoehe, mobil, {"hell": "light", "dunkel": "dark"}[thema])
        p.pruefe(f"{name}: {breite} px {thema}", await tab.js("document.documentElement.getAttribute('data-theme')"), {"hell": "light", "dunkel": "dark"}[thema])
        await asyncio.sleep(0.3)
        await tab.bild(f"{name}_{breite}_{thema}")
        if mobil:
            p.pruefe(f"{name}: 390 px ohne Überlauf", await tab.ueberlauf(), [])
            p.pruefe(f"{name}: unten die Leiste der Bereiche", await tab.js(
                "(()=>{const r=document.querySelector('.reiter').getBoundingClientRect();return Math.round(r.bottom)===window.innerHeight})()"), True)
    await seiten.ansicht(tab, 1280, 900, False, "light")


async def pruefen(tab, seed, p):
    ids, nr = seed["ids"], seed["nummern"]
    await seiten._vorab(tab, seiten.ERSATZ)
    code = await seiten.bis_c(tab, p, "Anmelden", seed["link"], "m***@example.invalid")
    p.pruefe("Code aus der Mail", bool(code), True)
    await seiten.eintippen(tab, code or "")
    await tab.js("document.getElementById('c-anmelden').click()")
    p.pruefe("angemeldet: Übersicht", await tab.warten(seiten.sichtbar("bereich-uebersicht"), 20), True)
    # der Postbote: Kopien (1 PDF, 2 Fotos mit Vorschau, 3 Rechnungen) und Schaufenster -- dann neu laden
    ende = time.monotonic() + 40
    while time.monotonic() < ende and len([x for x in seed["kopien"].iterdir() if x.suffix in (".pdf", ".jpg")]) < 8:
        await asyncio.sleep(0.3)
    await asyncio.sleep(1.0)
    p.pruefe("Übersicht nach dem Neuladen", await seiten.laden(tab, "/", "document.getElementById('k-unterlagen-wert').textContent!==''"), True)

    # Übersicht
    p.pruefe("Übersicht: Gruß", await tab.js(_t("d-gruss")), "Guten Tag Herr Dr. Muster")
    p.pruefe("Übersicht: Rechnungen", [await tab.js(_t(k)) for k in ("k-rechnungen-zahl", "k-rechnungen-wert", "k-rechnungen-satz")],
             ["2 offen", "1.975,00 € offen", f"Abschlagsrechnung {nr[2]}, fällig seit {(seed['heute'] - __import__('datetime').timedelta(days=3)).strftime('%d.%m.%Y')}"])
    p.pruefe("Übersicht: Unterlagen und Fotos", [await tab.js(_t(k)) for k in ("k-unterlagen-wert", "k-fotos-wert")], ["1 Unterlage", "2 Fotos"])
    p.pruefe("Übersicht: nächster Einsatz mit Betreff", (await tab.js(_t("k-einsatz-satz"))), f"{BETREFF} · Musterweg 12, 52531 Übach-Palenberg")
    p.pruefe("Übersicht: Stand heute", (await tab.js(_t("d-stand"))).startswith("Stand: heute, "), True)
    await alle_bilder(tab, p, "uebersicht")

    # Rechnungen (über die Kachel)
    await tab.js("document.querySelector('.kachel-karte[data-bereich=\"rechnungen\"]').click()")
    p.pruefe("Rechnungen: geladen", await tab.warten("document.querySelectorAll('#r-liste .zeile').length===3", 20), True)
    p.pruefe("Rechnungen: Adresse ?bereich=rechnungen", await tab.js("location.search"), "?bereich=rechnungen")
    p.pruefe("Rechnungen: Gruppe mit Betreff und Adresse", await tab.js(GRUPPEN.format(liste="r-liste")),
             [[f"Auftrag A-2026-0118 · {BETREFF}", "Musterweg 12, 52531 Übach-Palenberg"]])
    p.pruefe("Rechnungen: nie der Projekttitel", "Interner Projekttitel" in await tab.js("document.body.textContent"), False)
    p.pruefe("Rechnungen: Kennzeichen", await tab.js("[...document.querySelectorAll('#r-liste .zeile')].map(z=>[z.querySelector('.mono').textContent.split(' · ')[0],"
                                                     "(z.querySelector('.chip')||{}).textContent,[...z.querySelectorAll('.zustand-hinweis')].map(h=>h.textContent)])"),
             [[nr[2], "offen", [f"fällig seit {(seed['heute'] - __import__('datetime').timedelta(days=3)).strftime('%d.%m.%Y')}"]],
              [nr[1], "bezahlt", []],
              [nr[0], "teilweise bezahlt", ["noch offen 1.380,00 €", f"fällig am {(seed['heute'] + __import__('datetime').timedelta(days=7)).strftime('%d.%m.%Y')}"]]])
    p.pruefe("Rechnungen: offen insgesamt", [await tab.js(_t("r-offen-titel")), await tab.js(_t("r-offen"))], ["Offen insgesamt", "1.975,00 €"])
    await alle_bilder(tab, p, "rechnungen")

    # Termine
    p.pruefe("Termine: geladen", await reiter(tab, "termine", "document.querySelectorAll('#t-liste .termin').length===2"), True)
    p.pruefe("Termine: heute gekennzeichnet, vergangen darunter", await tab.js(
        "[...document.querySelectorAll('#t-liste .termin')].map(t=>[t.classList.contains('heute'),t.closest('.gruppe').classList.contains('vergangen')])"),
        [[True, False], [False, True]])
    p.pruefe("Termine: Dauer", await tab.js("[...document.querySelectorAll('#t-liste .termin .leise')].map(x=>x.textContent)"), ["3 Tage", "5 Tage"])
    await alle_bilder(tab, p, "termine")

    # Unterlagen: Ansehen im selben Tab, Zurück
    p.pruefe("Unterlagen: geladen", await reiter(tab, "unterlagen", "document.querySelectorAll('#u-liste .zeile').length===1"), True)
    p.pruefe("Unterlagen: Allgemeine Unterlagen", await tab.js(GRUPPEN.format(liste="u-liste")), [["Allgemeine Unterlagen", "ohne bestimmten Auftrag"]])
    await alle_bilder(tab, p, "unterlagen")
    await tab.js("document.querySelector('#u-liste .ansehen').click()")
    p.pruefe("Unterlagen: Ansehen öffnet das PDF im selben Tab", await tab.warten("document.contentType==='application/pdf'", 20), True)
    await tab.cmd("Runtime.evaluate", expression="history.back()")
    p.pruefe("Unterlagen: Zurück führt in den Bereich", await tab.warten(
        "location.search==='?bereich=unterlagen'&&!!document.getElementById('bereich-unterlagen')&&!document.getElementById('bereich-unterlagen').hidden"
        "&&document.querySelectorAll('#u-liste .zeile').length===1", 20), True)
    with seiten._engine(os.environ["ERP_TEST_POSTGRES_URL"], seed["schema"]).begin() as c:
        from sqlalchemy import text
        c.execute(text("UPDATE portal_freigaben SET zurueckgenommen_am = now(), zurueckgenommen_von_name = 'Klicktest' WHERE id = :i"), {"i": ids["pdf"]})
    await tab.js("document.querySelector('#u-liste .ansehen').click()")
    p.pruefe("Unterlagen: zurückgenommen -> nicht mehr verfügbar", await tab.warten(
        "(document.querySelector('#bereich-unterlagen .bereich-hinweis')||{}).textContent?.startsWith('Nicht mehr verfügbar. Diese Unterlage ist nicht mehr verfügbar.')", 20), True)
    p.pruefe("Unterlagen: Telefon im Hinweis", "0123 456789" in await tab.js("(document.querySelector('#bereich-unterlagen .bereich-hinweis')||{}).textContent||''"), True)

    # Fotos: Vorschau 400 px, groß 800 px, weiter
    p.pruefe("Fotos: geladen", await reiter(tab, "fotos", "document.querySelectorAll('#f-liste .foto').length===2"), True)
    p.pruefe("Fotos: Vorschauen geladen (400 px)", await tab.warten(
        "[...document.querySelectorAll('#f-liste .foto img')].every(i=>i.complete&&i.naturalWidth===400)", 20), True)
    await alle_bilder(tab, p, "fotos")
    await tab.js("document.querySelector('#f-liste .foto').click()")
    p.pruefe("Fotos: groß (800 px)", await tab.warten("document.getElementById('foto-gross').open&&document.getElementById('foto-gross-bild').naturalWidth===800", 20), True)
    p.pruefe("Fotos: Titel „Foto 1 von 2“", await tab.js(_t("foto-gross-titel")), "Foto 1 von 2")
    await tab.bild("foto_gross_1280")
    await tab.js("document.getElementById('foto-gross-vor').click()")
    p.pruefe("Fotos: weiter", await tab.warten("document.getElementById('foto-gross-titel').textContent==='Foto 2 von 2'"
                                               "&&document.getElementById('foto-gross-bild').naturalWidth===800", 20), True)
    await tab.js("document.getElementById('foto-gross-zu').click()")
    p.pruefe("Fotos: zu", await tab.js("document.getElementById('foto-gross').open"), False)
    p.pruefe("keine Verletzung der CSP", await tab.js("window.__dkErsatz?window.__dkErsatz.csp:0"), 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Klicktest: Bereiche des Kundenportals")
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
        c.execute(text(f"COMMENT ON SCHEMA {schema} IS 'Klicktest Bereiche des Kundenportals, pid {os.getpid()}'"))
    erp = seiten._engine(pg_url, schema)
    server = chrome = postbote = attrappe = None
    try:
        seed = befuellen(erp, ordner / "data")
        seed["kopien"], seed["schema"] = ordner / "kopien", schema
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
        if not dateien._bereit(port, f"localhost:{aussen}"):
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
