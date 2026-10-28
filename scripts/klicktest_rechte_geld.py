"""Klicktest: Rechte am Geld (1.9.111, Stufe 5, R1, Punkt 1) -- mit Geld arbeiten nur Admin und Büro – Finanzen.

    Büro – Auftrag   Auftrag: Hinweis statt „Neue Rechnung“, kein „Löschen“ am Entwurf; Rechnung (Entwurf): Hinweis, Felder gesperrt, kein
                     „Kopfdaten speichern“, kein Finalisieren/Löschen; Rechnung (festgeschrieben): kein Versand, kein Storno, kein
                     „Zahlungseingang buchen“, kein Gegenbuchen, keine Mahnung anlegen, Entwurf der Mahnung nur mit PDF, Versandverlauf ohne
                     „Zustellung nachtragen“ und ohne „Empfang bestätigt“; Kundenakte: kein Zuordnen, kein Zurücknehmen, keine Erstattung;
                     Mahnwesen: keine Auswahl, kein „als Entwurf anlegen“, kein Festschreiben; Versandprotokoll: kein „Empfang bestätigt“
                     an der Rechnung; Angriff aus der Seite: Finalisieren 403 -- und überall liest es alles
    Büro – Finanzen  dieselben Seiten mit allen Knöpfen (Gegenprobe), finalisiert den Entwurf
    Bilder           rechnung_buero_auftrag (ganze Seite), rechnung_entwurf_buero_auftrag, auftrag/kundenakte/mahnwesen_buero_auftrag,
                     rechnung_buero_finanzen

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_rechte_geld.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00.
"""

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date, datetime, timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.invoices import create_abschlag_pauschal, finalize_and_send_invoice, update_invoice_header
    from app.models import AppUser, Customer, EmailDispatch, Invoice, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.payments import Line, book_payment
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.reminders import create_reminder

    bea = AppUser(username="bea", display_name="Bea Auftrag", role="buero_auftrag", password_hash=k.passwort())
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Geld", last_name="Geld", street="Dachweg 1", postal_code="52531", city="Uebach",
                     email="geld@example.com")
    db.add_all([bea, fin, kunde]); db.flush()
    projekt = Project(project_number="P-G-1", name="Dach Geld", customer_id=kunde.id, status="angebot",
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    quote = Quote(quote_number="A-G-1", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"))
    db.add(quote); db.flush()
    db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2",
                     unit_price=Decimal("500")))
    db.commit()
    order = create_order_from_quote(db, quote.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
                                    caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)

    def pauschal(net, fest=True):
        invoice = create_abschlag_pauschal(db, load_order(db, order.id), lump_sum_net=Decimal(net))
        update_invoice_header(db, invoice, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 30),
                              intro_text="Einleitung der Rechnung")
        return finalize_and_send_invoice(db, invoice) if fest else invoice

    fest = pauschal("1000")                      # 1.190,00 -- überfällig, teilweise bezahlt, Mahnungsentwurf
    zweite = pauschal("500")                     # 595,00 -- überfällig, zur Mahnung fällig
    for rechnung in (fest, zweite):
        rechnung.invoice_date = berlin_today() - timedelta(days=34)
        rechnung.due_date = berlin_today() - timedelta(days=20)
    db.commit()
    entwurf = pauschal("300", fest=False)        # Entwurf
    book_payment(db, customer_id=kunde.id, received_on=berlin_today() - timedelta(days=2), amount=Decimal("200"), note="Teilzahlung",
                 lines=[Line(fest.id, zahlung=Decimal("200"))], user_name="Fin Finanzen")
    book_payment(db, customer_id=kunde.id, received_on=berlin_today() - timedelta(days=1), amount=Decimal("100"), note="ohne Zweck",
                 lines=[], user_name="Fin Finanzen")  # Rest am Kunden
    mahnung = create_reminder(db, db.get(Invoice, fest.id))
    db.add(EmailDispatch(dispatch_key="geld-rechnung-versand", message_ref="geld-rechnung-versand", status="gesendet", channel="smtp",
                         document_type="rechnung", document_id=fest.id, document_number=fest.invoice_number,
                         to_recipients="geld@example.com", subject="Rechnung", finished_at=datetime.utcnow()))
    db.commit()
    return {"order": order.id, "fest": fest.id, "fest_nr": fest.invoice_number, "zweite": zweite.id, "entwurf": entwurf.id,
            "mahnung": mahnung.id, "kunde": kunde.id,
            "cookies": {"bea": k.cookies(bea), "fin": k.cookies(fin)}}


INVOICE_READY = "invoice&&document.getElementById('statusInfo').textContent.length>0"
KNOEPFE = "[...document.querySelectorAll('{sel} button')].filter(b=>b.offsetParent!==null).map(b=>b.textContent.trim())"


async def _knoepfe(tab, sel):
    return await tab.js(KNOEPFE.replace("{sel}", sel))


async def _ganze_seite(tab, name):
    """Bild der ganzen Seite (wie die Bildgrundlage): die Höhe des Inhalts, Breite des Fensters."""
    await tab.js("document.querySelectorAll('.sticky').forEach(e=>{e.style.position='static';e.style.maxHeight='none';e.style.overflow='visible'})")
    hoehe = await tab.js("Math.ceil(document.documentElement.scrollHeight)")
    daten = (await tab.cmd("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                           clip={"x": 0, "y": 0, "width": 1440, "height": hoehe, "scale": 1}))["data"]
    (tab.shots / f"{name}.png").write_bytes(base64.b64decode(daten))


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1440, 900)

    # ================= Büro – Auftrag: liest alles, kein Knopf =================
    await tab.anmelden(seed["cookies"]["bea"])
    await tab.oeffnen(f"/orders/{seed['order']}", "order&&document.getElementById('invoicesList').innerHTML.length>0")
    p.pruefe("Auftrag: Hinweis statt „Neue Rechnung“", await tab.js(
        "[!!document.querySelector('[data-geld-nur-lesen]'),!!document.getElementById('newInvoiceButton'),"
        "!!document.getElementById('newInvoiceType')]"), [True, False, False])
    p.pruefe("Auftrag: Rechnungen gelistet, kein „Löschen“", await tab.js(
        "[document.querySelectorAll('#invoicesList .revision').length,document.getElementById('invoicesList').textContent.includes('Löschen')]"),
        [3, False])
    await _ganze_seite(tab, "auftrag_buero_auftrag")

    await tab.oeffnen(f"/invoices/{seed['entwurf']}", INVOICE_READY)
    p.pruefe("Entwurf: Hinweis sichtbar", await tab.js("!!document.querySelector('[data-geld-nur-lesen]')"), True)
    p.pruefe("Entwurf: keine Knöpfe im Status", await _knoepfe(tab, "#statusActions"), [])
    p.pruefe("Entwurf: Felder gesperrt, kein Speichern", await tab.js(
        "[document.getElementById('pAmount').disabled,document.getElementById('iIntro').disabled,"
        "document.getElementById('iPeriodStart').disabled,document.querySelector('#pauschalCard button').style.display,"
        "document.querySelector('aside .card button').style.display]"), [True, True, True, "none", "none"])
    p.pruefe("Entwurf: Einleitung gelesen", await tab.js("document.getElementById('iIntro').value"), "Einleitung der Rechnung")
    await _ganze_seite(tab, "rechnung_entwurf_buero_auftrag")
    antwort = await tab.js(f"fetch('/api/invoices/{seed['entwurf']}/send',{{method:'POST'}}).then(async r=>[r.status,(await r.json()).detail])")
    p.pruefe("Angriff aus der Seite: Finalisieren 403", antwort,
             [403, "Rechnungen, Zahlungen und Mahnungen bearbeiten Admin und Büro – Finanzen – du kannst sie lesen."])

    await tab.oeffnen(f"/invoices/{seed['fest']}", INVOICE_READY + "&&document.getElementById('reminderList').innerHTML.length>0"
                      "&&document.querySelector('#invoiceDispatchHistory .dh-row')")
    p.pruefe("Festgeschrieben: kein Versand, kein Storno", [await _knoepfe(tab, "#statusActions"),
                                                           await tab.js("!!document.getElementById('invoiceEmailInput')")], [[], False])
    p.pruefe("Zahlungen gelesen, kein Buchen, kein Gegenbuchen", await tab.js(
        "[document.querySelector('[data-offen]').textContent,!!document.querySelector('#paymentActions button'),"
        "document.querySelectorAll('#paymentAllocations .alloc').length,!!document.querySelector('#paymentAllocations button')]"),
        ["990,00\xa0€", False, 1, False])
    p.pruefe("Mahnung: Entwurf nur mit PDF, keine neue", [await _knoepfe(tab, "#reminderList"), await _knoepfe(tab, "#reminderActions")],
             [["PDF"], []])
    p.pruefe("Versandverlauf ohne Nachtragen und Ergebnis", await tab.js(
        "[document.querySelectorAll('#invoiceDispatchHistory .dh-row').length,!!document.querySelector('#invoiceDispatchHistory [data-klick]')]"),
        [1, False])
    p.pruefe("JS-Fehler (Büro – Auftrag)", tab.fehler, [])
    await _ganze_seite(tab, "rechnung_buero_auftrag")

    await tab.oeffnen(f"/customers/{seed['kunde']}", "customerPaymentsData&&document.getElementById('customerPayments').innerHTML.length>0")
    p.pruefe("Kundenakte: Zahlungen gelesen, kein Knopf", await tab.js(
        "[document.querySelectorAll('[data-zahlung]').length,[...document.querySelectorAll('#zahlungen button')].length,"
        "!!document.querySelector('[data-erstattung]'),!!document.querySelector('#zahlungen [data-geld-nur-lesen]')]"), [2, 0, False, True])
    await _ganze_seite(tab, "kundenakte_buero_auftrag")

    await tab.oeffnen("/mahnwesen", "allReminders.length>0&&attentionRows.length>0")
    p.pruefe("Mahnwesen: gelistet, keine Auswahl, kein Knopf außer PDF/Verlauf", await tab.js(
        "[document.querySelectorAll('#dueRows tr[data-faellig]').length,!!document.getElementById('bulkCreateBtn'),"
        "document.querySelectorAll('.due-select').length,[...document.querySelectorAll('main button')].filter(b=>b.offsetParent!==null).map(b=>b.textContent.trim())"
        ".filter(t=>!['PDF','Verlauf'].includes(t)&&!t.startsWith('⋮')).length]"), [1, False, 0, 0])
    await _ganze_seite(tab, "mahnwesen_buero_auftrag")

    await tab.oeffnen(f"/versandprotokoll?typ=rechnung&id={seed['fest']}", "document.querySelectorAll('[data-dispatch-row],#rows tr').length>0")
    p.pruefe("Versandprotokoll: kein „Empfang bestätigt“ an der Rechnung", await tab.js(
        "!!document.querySelector('[data-klick=\"versandergebnis\"]')"), False)

    # ================= Büro – Finanzen: dieselben Seiten mit Knöpfen =================
    await tab.anmelden(seed["cookies"]["fin"])
    await tab.oeffnen(f"/orders/{seed['order']}", "order&&document.getElementById('invoicesList').innerHTML.length>0")
    p.pruefe("Finanzen: „Neue Rechnung“, „Löschen“ am Entwurf", await tab.js(
        "[!!document.getElementById('newInvoiceButton'),!!document.querySelector('[data-geld-nur-lesen]'),"
        "document.getElementById('invoicesList').textContent.includes('Löschen')]"), [True, False, True])
    await tab.oeffnen(f"/invoices/{seed['fest']}", INVOICE_READY + "&&document.getElementById('reminderList').innerHTML.length>0"
                      "&&document.querySelector('#invoiceDispatchHistory .dh-row')")
    p.pruefe("Finanzen: Versand, Storno, Buchen, Gegenbuchen, Mahnung", await tab.js(
        "[!!document.getElementById('invoiceEmailInput'),[...document.querySelectorAll('#statusActions button')].some(b=>b.textContent==='Stornieren'),"
        "!!document.querySelector('#paymentActions button'),!!document.querySelector('#paymentAllocations button'),"
        "[...document.querySelectorAll('#reminderList button')].map(b=>b.textContent.trim())]"),
        [True, False, True, True, ["Festschreiben", "Bearbeiten", "Löschen", "PDF"]])  # Storno gesperrt: Zahlung zugeordnet
    p.pruefe("Finanzen: Zustellung nachtragen und Empfang bestätigt", await tab.js(
        "[!!document.querySelector('#invoiceDispatchHistory [data-klick=\"zustellung-oeffnen\"]'),"
        "!!document.querySelector('#invoiceDispatchHistory [data-klick=\"versandergebnis\"]')]"), [True, True])
    await _ganze_seite(tab, "rechnung_buero_finanzen")
    await tab.oeffnen(f"/invoices/{seed['entwurf']}", INVOICE_READY)
    p.pruefe("Finanzen: Entwurf bearbeitbar", await tab.js(
        "[document.getElementById('pAmount').disabled,!!document.querySelector('[data-geld-nur-lesen]'),"
        "[...document.querySelectorAll('#statusActions button')].map(b=>b.textContent)]"),
        [False, False, ["Rechnung finalisieren", "Entwurf löschen"]])
    await tab.js("sendInvoice()")
    p.pruefe("Finanzen finalisiert", await tab.warten("invoice.status==='versendet'&&!!invoice.invoice_number"), True)
    await tab.oeffnen(f"/customers/{seed['kunde']}", "customerPaymentsData&&document.getElementById('customerPayments').innerHTML.length>0")
    p.pruefe("Finanzen: Kundenakte mit Zuordnen und Zurücknehmen", await tab.js(
        "[...document.querySelectorAll('#zahlungen button')].map(b=>b.textContent.trim()).filter(t=>['Zuordnen','Zahlung zurücknehmen'].includes(t)).sort()"),
        ["Zahlung zurücknehmen", "Zahlung zurücknehmen", "Zuordnen"])
    await tab.oeffnen("/mahnwesen", "allReminders.length>0&&attentionRows.length>0")
    p.pruefe("Finanzen: Mahnwesen mit Auswahl und Knöpfen", await tab.js(
        "[!!document.getElementById('bulkCreateBtn'),document.querySelectorAll('.due-select').length>0,"
        "[...document.querySelectorAll('main button')].some(b=>b.textContent.trim()==='Festschreiben')]"), [True, True, True])
    p.pruefe("JS-Fehler (Büro – Finanzen)", tab.fehler, [])
    print(json.dumps({k: v for k, v in seed.items() if k != "cookies"}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
