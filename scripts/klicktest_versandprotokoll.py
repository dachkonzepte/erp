"""Klicktest: Versand mit Protokoll und Ablage (1.8.17, Stufe 2, Runde 2a-3a).

Sendet über die echten Seiten Rechnung, Auftrag, Angebot und Mahnung per E-Mail -- mit mehreren
Empfängern und CC -- an einen kleinen SMTP-Empfänger, der in diesem Skript läuft (Port im Seed,
nichts verlässt den Rechner). Prüft dann:

- Rechnung: An vorbelegt, CC-Feld, Doppelklick sendet genau eine Mail (Knopf gesperrt, Schlüssel
  je Klick), Umschlag An + CC, Kopfzeile X-DK-Versand-ID; ein abgelehnter Empfänger zeigt den
  Fehler auf der Seite und sendet nichts.
- Auftrag, Angebot, Mahnung: je ein Versand über die Seite.
- /versandprotokoll: sechs Einträge (vier gesendet, einer fehlgeschlagen mit Fehlerklasse, ein
  vorab angelegter hängender), Hinweis auf den hängenden, "Prüfen" der Ablage, PDF-Abruf,
  Filter auf ein Dokument, hell und dunkel, 412 px ohne seitliches Scrollen.
- Monteur: Seite und API gesperrt.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_versandprotokoll.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import email
import socket
import socketserver
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

POSTFACH: list[dict] = []


def befuellen(db, k):
    from datetime import date, datetime, timedelta
    from decimal import Decimal

    from app.email_sending import update_smtp_settings
    from app.invoices import create_schlussrechnung, finalize_and_send_invoice
    from app.models import AppUser, Customer, EmailDispatch, Order, OrderItem, Project, Quote, QuoteItem
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.reminders import compute_reminder_status, create_reminder, ensure_default_reminder_levels, finalize_and_send_reminder

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        smtp_port = s.getsockname()[1]
    update_smtp_settings(db, host="127.0.0.1", port=smtp_port, username="buero", encryption="none",
                         sender_email="buero@klicktest.example", sender_name="Klicktest GmbH", password="pw")

    kunde = Customer(name="Klicktest Kunde", last_name="Klicktest Kunde", email="kunde@klicktest.example")
    db.add(kunde); db.flush()
    projekt = Project(project_number="P-KT-1", name="Versand", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(quote_number="A-KT-1", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19.00"), status="versendet")
    db.add(angebot); db.flush()
    db.add(QuoteItem(quote_id=angebot.id, sort_order=10, position_number="1", short_text="Dacheindeckung",
                     quantity=Decimal("10"), unit="m²", unit_price=Decimal("50")))
    auftrag = Order(order_number="AUF-KT-1", project_id=projekt.id, source_quote_id=angebot.id, quote_number_snapshot="A-KT-1",
                    title="Dachsanierung", vat_rate=Decimal("19.00"), customer_name="Klicktest Kunde", customer_number="K-KT-1")
    db.add(auftrag); db.flush()
    db.add(OrderItem(order_id=auftrag.id, sort_order=10, position_number="1", short_text="Dacheindeckung",
                     quantity=Decimal("10"), unit="m²", unit_price=Decimal("50")))
    db.commit()
    rechnung = finalize_and_send_invoice(db, create_schlussrechnung(db, auftrag, due_date=date.today() - timedelta(days=20)))
    ensure_default_reminder_levels(db)
    mahnung = finalize_and_send_reminder(db, create_reminder(db, rechnung, compute_reminder_status(db, rechnung)["next_level"]))

    buero = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    monteur = AppUser(username="max", display_name="Max Monteur", role="field", password_hash=k.passwort())
    db.add_all([buero, monteur]); db.flush()
    db.add(EmailDispatch(
        dispatch_key="angebot-haengt-00000001", message_ref="00000000-0000-0000-0000-00000000beef", status="in_arbeit",
        channel="smtp", document_type="angebot", document_id=angebot.id, document_number="A-KT-1",
        to_recipients="kunde@klicktest.example", subject="Angebot A-KT-1 (hängt)",
        created_at=datetime.utcnow() - timedelta(minutes=30), created_by_name="Bea Büro",
    ))
    db.commit()
    return {"smtp_port": smtp_port, "rechnung": rechnung.id, "auftrag": auftrag.id, "angebot": angebot.id, "mahnung": mahnung.id,
            "cookies": {"buero": k.cookies(buero), "monteur": k.cookies(monteur)}}


class _SMTPHandler(socketserver.StreamRequestHandler):
    """Gerade genug SMTP für smtplib: EHLO mit AUTH PLAIN, abgelehnt@ bekommt 550."""

    def handle(self):
        def w(text):
            self.wfile.write((text + "\r\n").encode())
        w("220 klicktest ESMTP")
        rcpts = []
        while True:
            line = self.rfile.readline()
            if not line:
                return
            cmd = line.decode("utf-8", "replace").strip()
            up = cmd.upper()
            if up.startswith("EHLO"):
                w("250-klicktest"); w("250 AUTH PLAIN")
            elif up.startswith("AUTH"):
                w("235 2.7.0 ok")
            elif up.startswith("MAIL FROM"):
                rcpts = []; w("250 ok")
            elif up.startswith("RCPT TO"):
                addr = cmd.split(":", 1)[1].strip().strip("<>")
                if addr.startswith("abgelehnt@"):
                    w("550 5.1.1 unbekannt")
                else:
                    rcpts.append(addr); w("250 ok")
            elif up == "DATA":
                w("354 weiter")
                data = []
                while True:
                    part = self.rfile.readline()
                    if not part or part in (b".\r\n", b".\n"):
                        break
                    data.append(part)
                POSTFACH.append({"rcpts": rcpts, "message": email.message_from_bytes(b"".join(data))})
                w("250 ok")
            elif up == "QUIT":
                w("221 tschuess"); return
            else:
                w("250 ok")


def _smtp_starten(port):
    server = socketserver.ThreadingTCPServer(("127.0.0.1", port), _SMTPHandler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


FERTIG = "!!document.querySelector('#rows tr td') && !document.querySelector('#rows td.empty')"


async def pruefen(tab, seed, p):
    server = _smtp_starten(seed["smtp_port"])
    try:
        await _pruefen(tab, seed, p)
    finally:
        server.shutdown()


async def _pruefen(tab, seed, p):
    await tab.anmelden(seed["cookies"]["buero"])

    # --- Rechnung: vorbelegt, CC, Doppelklick = eine Mail
    await tab.oeffnen(f"/invoices/{seed['rechnung']}", "document.getElementById('invoiceCcInput')")
    p.pruefe("Rechnung: An vorbelegt", await tab.js("document.getElementById('invoiceEmailInput').value"), "kunde@klicktest.example")
    p.pruefe("Rechnung: Feldtyp", await tab.js("[document.getElementById('invoiceEmailInput').type, document.getElementById('invoiceEmailInput').multiple]"), ["email", True])
    await tab.js("document.getElementById('invoiceEmailInput').value='kunde@klicktest.example, zweite@klicktest.example';"
                 "document.getElementById('invoiceCcInput').value='chef@klicktest.example';"
                 "const b=document.querySelector('button[onclick^=\"sendInvoiceEmail\"]'); b.click(); b.click(); true")
    await tab.warten("document.getElementById('statusActionMsg').textContent.includes('versendet')")
    p.pruefe("Rechnung: Statuszeile", await tab.js("document.getElementById('statusActionMsg').textContent"), "Per E-Mail versendet.")
    p.pruefe("Rechnung: Doppelklick sendet genau eine Mail", len(POSTFACH), 1)
    p.pruefe("Rechnung: Umschlag An + CC", POSTFACH[0]["rcpts"] if POSTFACH else None,
             ["kunde@klicktest.example", "zweite@klicktest.example", "chef@klicktest.example"])
    p.pruefe("Rechnung: Kopfzeile Cc", POSTFACH[0]["message"]["Cc"] if POSTFACH else None, "chef@klicktest.example")
    kennung = POSTFACH[0]["message"]["X-DK-Versand-ID"] if POSTFACH else None
    p.pruefe("Rechnung: X-DK-Versand-ID vorhanden", bool(kennung and len(kennung) == 36), True)
    p.pruefe("Rechnung: JS-Fehler", tab.fehler, [])

    # --- abgelehnter Empfänger: Fehler sichtbar, nichts gesendet
    await tab.js("document.getElementById('invoiceEmailInput').value='abgelehnt@klicktest.example';"
                 "document.querySelector('button[onclick^=\"sendInvoiceEmail\"]').click(); true")
    await tab.warten("document.getElementById('statusActionMsg').textContent.startsWith('Fehler')")
    fehler = await tab.js("document.getElementById('statusActionMsg').textContent")
    p.pruefe("Rechnung abgelehnt: Fehler auf der Seite", (fehler or "").startswith("Fehler: E-Mail-Versand fehlgeschlagen"), True)
    p.pruefe("Rechnung abgelehnt: keine weitere Mail", len(POSTFACH), 1)
    await tab.bild("rechnung_versand")

    # --- Auftrag, Angebot, Mahnung
    await tab.oeffnen(f"/orders/{seed['auftrag']}", "document.getElementById('orderEmailSection').style.display==='block'")
    await tab.js("document.getElementById('orderCcInput').value='chef@klicktest.example';"
                 "document.querySelector('button[onclick^=\"sendOrderEmail\"]').click(); true")
    await tab.warten("document.getElementById('orderEmailStatus').textContent==='Versendet.'")
    p.pruefe("Auftrag: versendet", await tab.js("document.getElementById('orderEmailStatus').textContent"), "Versendet.")
    p.pruefe("Auftrag: Link ins Protokoll", await tab.js("document.getElementById('orderDispatchLink').getAttribute('href')"),
             f"/versandprotokoll?typ=auftrag&id={seed['auftrag']}")
    p.pruefe("Auftrag: JS-Fehler", tab.fehler, [])

    await tab.oeffnen(f"/quotes/{seed['angebot']}/edit", "document.getElementById('quoteEmailSection')?.style.display==='block'")
    await tab.js("document.querySelector('button[onclick^=\"sendQuoteEmail\"]').click(); true")
    await tab.warten("document.getElementById('quoteEmailStatus').textContent==='Versendet.'")
    p.pruefe("Angebot: versendet", await tab.js("document.getElementById('quoteEmailStatus').textContent"), "Versendet.")
    p.pruefe("Angebot: JS-Fehler", tab.fehler, [])

    await tab.oeffnen("/mahnwesen", f"document.getElementById('reminderCcInput{seed['mahnung']}')")
    await tab.js(f"document.getElementById('reminderCcInput{seed['mahnung']}').value='chef@klicktest.example';"
                 f"document.querySelector('button[onclick^=\"sendReminderEmail({seed['mahnung']},\"]').click(); true")
    await tab.warten("document.getElementById('allRows').textContent.includes('versendet ')")
    p.pruefe("Mahnung: versendet", "an kunde@klicktest.example" in (await tab.js("document.getElementById('allRows').textContent") or ""), True)
    p.pruefe("Mahnung: JS-Fehler", tab.fehler, [])
    p.pruefe("Mails insgesamt", len(POSTFACH), 4)

    # --- Versandprotokoll
    await tab.oeffnen("/versandprotokoll", FERTIG)
    await tab.js("localStorage.setItem('erp_theme','light'); true")
    await tab.oeffnen("/versandprotokoll", FERTIG)
    p.pruefe("Protokoll: sechs Einträge", await tab.js("document.querySelectorAll('#rows tr').length"), 6)
    pillen = await tab.js("[...document.querySelectorAll('#rows .pill')].map(e=>e.textContent)")
    p.pruefe("Protokoll: Status", sorted(pillen or []), ["Fehlgeschlagen", "Gesendet", "Gesendet", "Gesendet", "Gesendet", "Hängt"])
    p.pruefe("Protokoll: Fehlerklasse sichtbar", "SMTPRecipientsRefused" in (await tab.js("document.getElementById('rows').textContent") or ""), True)
    p.pruefe("Protokoll: Hinweis auf hängenden Versand", await tab.js(
        "getComputedStyle(document.getElementById('stuckCard')).display!=='none' && document.getElementById('stuckCard').textContent.includes('Ein Versand hängt')"), True)
    p.pruefe("Protokoll: Kennung der Rechnungs-Mail in der Liste", (kennung or "-") in (await tab.js("document.getElementById('rows').textContent") or ""), True)
    await tab.js("document.querySelector('#rows button[onclick^=\"checkArchive\"]').click(); true")
    await tab.warten("[...document.querySelectorAll('#rows .check-ok,#rows .check-bad')].length>0")
    p.pruefe("Protokoll: Ablage geprüft", await tab.js("document.querySelector('#rows .check-ok')?.textContent"), "Datei unverändert (Prüfsumme stimmt).")
    pdf = await tab.js("(async()=>{const id=document.querySelector('#rows button[onclick^=\"checkArchive\"]').getAttribute('onclick').match(/\\d+/)[0];"
                       "const r=await fetch('/api/sent-documents/'+id+'/file');const b=new Uint8Array(await r.arrayBuffer());"
                       "return [r.status,r.headers.get('content-type'),String.fromCharCode(...b.slice(0,4))]})()")
    p.pruefe("Protokoll: PDF aus der Ablage", pdf, [200, "application/pdf", "%PDF"])
    p.pruefe("Protokoll: Hintergrund hell", await tab.js("getComputedStyle(document.body).backgroundColor"), "rgb(244, 246, 245)")
    p.pruefe("Protokoll: JS-Fehler", tab.fehler, [])
    await tab.bild("protokoll_hell")

    await tab.js("localStorage.setItem('erp_theme','dark'); true")
    await tab.oeffnen("/versandprotokoll", FERTIG)
    p.pruefe("Protokoll: Hintergrund dunkel", await tab.js("getComputedStyle(document.body).backgroundColor"), "rgb(18, 24, 22)")
    p.pruefe("Protokoll dunkel: Warnkarte nicht weiß", await tab.js("getComputedStyle(document.getElementById('stuckCard')).backgroundColor"), "rgb(58, 47, 20)")
    await tab.bild("protokoll_dunkel")
    await tab.js("localStorage.setItem('erp_theme','light'); true")

    await tab.oeffnen(f"/versandprotokoll?typ=rechnung&id={seed['rechnung']}", FERTIG)
    p.pruefe("Filter auf eine Rechnung: zwei Einträge", await tab.js("document.querySelectorAll('#rows tr').length"), 2)

    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen("/versandprotokoll", FERTIG)
    p.pruefe("412 px: kein seitliches Scrollen der Seite", await tab.js("document.documentElement.scrollWidth<=window.innerWidth"), True)
    await tab.bild("protokoll_412")
    await tab.fenster(1280, 900)

    # --- Monteur
    await tab.anmelden(seed["cookies"]["monteur"])
    await tab.oeffnen("/versandprotokoll", "document.readyState==='complete'")
    p.pruefe("Monteur: Seite gesperrt", await tab.js("document.title"), "DACHKONZEPTE ERP – Kein Zugriff")
    p.pruefe("Monteur: API gesperrt", await tab.js("Promise.all(['/api/email-dispatches','/api/sent-documents/1/file'].map(u=>fetch(u).then(r=>r.status)))"), [403, 403])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
