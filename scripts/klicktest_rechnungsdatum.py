"""Klicktest: Rechnungsdatum = Tag des Finalisierens, Bearbeiten unter der Sperre (1.8.75).

docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.75":

    Entwurf von vor drei Wochen   Rechnungsdaten zeigen "Finalisiert heute: Rechnungsdatum <heute>, fällig <heute + 14>";
                                  Finalisieren -> Rechnungsdatum heute, fällig in 14 Tagen, Skonto bis heute + 7, nicht
                                  überfällig, kein Versandhinweis (hell und dunkel)
    vor zehn Tagen finalisiert    Hinweis über dem E-Mail-Versand: Rechnung vom ..., Skontofrist schon abgelaufen
    veraltete Seite               Entwurf geöffnet, in einer anderen Sitzung finalisiert (API), dann "Kopfdaten speichern" ->
                                  Meldung "Nur Rechnungen im Entwurf ... inzwischen festgeschrieben (R-...)", nichts geändert;
                                  Position ändern über die API -> 409

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_rechnungsdatum.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date, timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.invoices import create_schlussrechnung, finalize_and_send_invoice, update_invoice_header, update_invoice_payment_term
    from app.models import AppUser, Customer, PaymentTerm, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id

    heute = berlin_today()
    admin = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Klar", last_name="Klar", street="Dachweg 1", postal_code="52531", city="Uebach",
                     email="klar@klicktest.example")
    term = PaymentTerm(label="14 Tage, 7 Tage 2 % Skonto", days=14, skonto_percent=Decimal("2"), skonto_days=7)
    db.add_all([admin, kunde, term]); db.flush()

    def entwurf(nummer):
        projekt = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=kunde.id, status="angebot",
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-{nummer}", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2",
                         unit_price=Decimal("50")))
        db.commit()
        order = create_order_from_quote(db, quote.id, order_date=date(2026, 9, 1), execution_start=None, execution_end=None,
                                        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None,
                                        remarks=None)
        invoice = create_schlussrechnung(db, load_order(db, order.id))
        update_invoice_payment_term(db, invoice, term.id)
        update_invoice_header(db, invoice, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 18))
        return invoice

    def zurueck(invoice, tage):
        """Wie ein Entwurf bzw. eine Rechnung von vor `tage` Tagen: Datum und Fälligkeit mit demselben Abstand zurück."""
        invoice.invoice_date -= timedelta(days=tage)
        invoice.due_date -= timedelta(days=tage)
        db.commit()

    alt = entwurf("KT-1")
    zurueck(alt, 21)
    frueher = finalize_and_send_invoice(db, entwurf("KT-2"))
    zurueck(frueher, 10)
    veraltet = entwurf("KT-3")
    return {"alt": alt.id, "frueher": frueher.id, "veraltet": veraltet.id, "heute": heute.strftime("%d.%m.%Y"),
            "heute_iso": heute.isoformat(), "faellig": (heute + timedelta(days=14)).strftime("%d.%m.%Y"),
            "faellig_iso": (heute + timedelta(days=14)).isoformat(),
            "skonto": (heute + timedelta(days=7)).strftime("%d.%m.%Y"),
            "alt_datum": (heute - timedelta(days=21)).isoformat(),
            "frueher_datum": (heute - timedelta(days=10)).strftime("%d.%m.%Y"),
            "cookies": {"admin": k.cookies(admin)}}


INVOICE_READY = "invoice&&document.getElementById('statusActions').innerHTML.length>0"


async def _bild(tab, name, element, dunkel=False):
    await tab.js(f"document.documentElement.setAttribute('data-theme','light');"
                 f"document.getElementById('{element}').scrollIntoView({{block:'center'}})")
    await tab.bild(name)
    if dunkel:
        await tab.js("document.documentElement.setAttribute('data-theme','dark')")
        await tab.bild(name + "_dunkel")
        await tab.js("document.documentElement.setAttribute('data-theme','light')")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1280, 1000)
    await tab.anmelden(seed["cookies"]["admin"])

    # --- Entwurf von vor drei Wochen ---
    await tab.oeffnen(f"/invoices/{seed['alt']}", INVOICE_READY)
    p.pruefe("Entwurf: Rechnungsdatum des Entwurfs im Feld", await tab.js("document.getElementById('iDate').value"),
             seed["alt_datum"])
    notiz = await tab.js("document.querySelector('#dateNote [data-rechnungsdatum]')?.textContent||''")
    p.pruefe("Entwurf: Hinweis mit den Daten von heute",
             f"Finalisiert heute: Rechnungsdatum {seed['heute']}, fällig {seed['faellig']}." in notiz
             and "Zahlungsziel des Entwurfs (14 Tage)" in notiz, True)
    await _bild(tab, "entwurf_rechnungsdatum", "dateNote", dunkel=True)
    await tab.js("sendInvoice()")
    p.pruefe("Finalisiert", await tab.warten("invoice.status==='versendet'"), True)
    p.pruefe("Finalisiert: Rechnungsdatum und Fälligkeit",
             [await tab.js("document.getElementById('iDate').value"), await tab.js("document.getElementById('iDue').value")],
             [seed["heute_iso"], seed["faellig_iso"]])
    satz = await tab.js("document.getElementById('paymentTermsSentence').textContent")
    p.pruefe("Finalisiert: Skonto ab heute", f"Bei Zahlung bis zum {seed['skonto']}" in satz, True)
    p.pruefe("Finalisiert: nicht überfällig, kein Versandhinweis, kein Entwurfshinweis",
             [await tab.js("invoice.is_overdue"), await tab.js("!!document.querySelector('[data-versandhinweis]')"),
              await tab.js("document.getElementById('dateNote').textContent")], [False, False, ""])

    # --- vor zehn Tagen finalisiert: Hinweis beim Versand ---
    await tab.oeffnen(f"/invoices/{seed['frueher']}", INVOICE_READY)
    hinweis = await tab.js("document.querySelector('#statusActions [data-versandhinweis]')?.textContent||''")
    p.pruefe("Später versenden: Hinweis",
             hinweis.startswith(f"Die Rechnung ist vom {seed['frueher_datum']} (Tag des Finalisierens), heute ist der "
                                f"{seed['heute']}.") and hinweis.endswith("Die Skontofrist ist schon abgelaufen."), True)
    p.pruefe("Später versenden: Knopf bleibt", await tab.js("!!document.querySelector('button[onclick^=\"sendInvoiceEmail\"]')"),
             True)
    await _bild(tab, "versandhinweis", "statusActions", dunkel=True)

    # --- veraltete Seite: inzwischen finalisiert ---
    vid = seed["veraltet"]
    await tab.oeffnen(f"/invoices/{vid}", INVOICE_READY)
    nummer = await tab.js(f"fetch('/api/invoices/{vid}/send',{{method:'POST'}}).then(r=>r.json()).then(j=>j.invoice_number)")
    await tab.js("document.getElementById('iIntro').value='Geändert auf veralteter Seite';saveHeader()")
    p.pruefe("Veraltete Seite: Meldung mit Nummer",
             await tab.warten("document.getElementById('headerStatus').textContent.includes('inzwischen festgeschrieben')"),
             True)
    p.pruefe("Veraltete Seite: Text", await tab.js("document.getElementById('headerStatus').textContent"),
             f"Fehler: Nur Rechnungen im Entwurf können bearbeitet werden. Die Rechnung ist inzwischen festgeschrieben ({nummer}).")
    p.pruefe("Veraltete Seite: nichts geändert",
             await tab.js(f"fetch('/api/invoices/{vid}').then(r=>r.json()).then(j=>j.intro_text||'')") != "Geändert auf veralteter Seite",
             True)
    item = await tab.js("invoice.items[0].id")
    status = await tab.js(f"fetch('/api/invoices/{vid}/items/{item}',{{method:'PUT',headers:{{'Content-Type':'application/json'}},"
                          "body:JSON.stringify({ist_quantity:'1'})}).then(r=>r.status)")
    p.pruefe("Veraltete Seite: Position ändern 409", status, 409)
    await _bild(tab, "veraltete_seite", "headerStatus")
    p.pruefe("JS-Fehler", tab.fehler, [])
    print(json.dumps({k: v for k, v in seed.items() if k != "cookies"}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
