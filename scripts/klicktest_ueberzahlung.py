"""Klicktest: Überzahlung -- Schlussrechnung unter 0 €, Erstattung als Zahlungsausgang, Guthaben am Kunden (1.8.90, R4c Punkte 6 und 7).

Ein Auftrag (10 m² × 50 € = 595 € brutto) mit einem Abschlag nach Leistungsstand über 10 m² (595 €), voll bezahlt; die Schlussrechnung
mit dem Aufmaß 8 m² lautet über −119 € (Überzahlung). Dazu ein Zahlungsbedingungs-Skonto am Entwurf.

    Rechnungsseite     Entwurf: Rechnungsbetrag −119 €, Zahlungshinweis "Erstattungsbetrag (Überzahlung) 119,00 €", Satz "Den
                       Erstattungsbetrag … überweisen wir Ihnen." statt Fälligkeit und Skonto, Finalisieren möglich; danach Kennzeichen
                       "Guthaben 119,00 €", Karte Zahlungen mit Guthaben und Erstattung buchen (100 €) -> Guthaben 19 €; PDF
    Kundenakte         Guthaben 19 € mit Link, Zahlungsausgang (Erstattung) −100 € ohne "nicht zugeordnet", zurücknehmen -> Guthaben 119 €
    API                zu viel erstattet 409; Monteurin 403
    412 px dunkel      Rechnungsseite

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_ueberzahlung.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from sqlalchemy import update

    from app.berlin_time import berlin_today
    from app.invoices import (
        create_abschlag_leistungsstand, create_schlussrechnung, finalize_and_send_invoice, update_invoice_header,
        update_invoice_item,
    )
    from app.models import AppUser, Customer, Invoice, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.payments import Line, book_payment
    from app.project_pipeline_columns import default_pipeline_column_id

    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    monteurin = AppUser(username="monteurin", display_name="Mia Monteurin", role="field", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Über", last_name="Über", street="Dachweg 1", postal_code="52531", city="Uebach",
                     email="ueber@example.com")
    db.add_all([buero, monteurin, kunde]); db.flush()
    projekt = Project(project_number="P-KT-1", name="Dach", customer_id=kunde.id, status="angebot",
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    quote = Quote(quote_number="A-KT-1", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"))
    db.add(quote); db.flush()
    db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2",
                     unit_price=Decimal("50")))
    db.commit()
    order = create_order_from_quote(db, quote.id, order_date=date(2026, 9, 1), execution_start=None, execution_end=None,
                                    caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None,
                                    remarks=None)
    abschlag = create_abschlag_leistungsstand(db, load_order(db, order.id))
    update_invoice_item(db, abschlag, abschlag.items[0], ist_quantity=Decimal("10"))
    update_invoice_header(db, abschlag, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 30))
    abschlag = finalize_and_send_invoice(db, abschlag)
    book_payment(db, customer_id=kunde.id, received_on=berlin_today(), amount=Decimal("595"), note=None,
                 lines=[Line(abschlag.id, zahlung=Decimal("595"))], user_name="Bea Büro")
    schluss = create_schlussrechnung(db, load_order(db, order.id))
    update_invoice_item(db, schluss, schluss.items[0], ist_quantity=Decimal("8"))  # Aufmaß kleiner als abgeschlagen
    update_invoice_header(db, schluss, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 10, 10))
    db.execute(update(Invoice).where(Invoice.id == schluss.id).values(skonto_percent=Decimal("2"), skonto_days=10))
    db.commit()
    return {"schluss": schluss.id, "kunde": kunde.id, "cookies": {"buero": k.cookies(buero), "monteurin": k.cookies(monteurin)}}


def _passt(p, name, ist, bedingung):
    """Prüfung über eine Bedingung -- bei Abweichung steht der gelesene Wert in der Ausgabe."""
    p.pruefe(name, "passt" if bedingung(ist) else ist, "passt")


READY = "invoice&&invoice.id&&document.getElementById('finalBody').innerHTML"
CUSTOMER_READY = "customerPaymentsData&&document.getElementById('zahlungen').style.display==='block'"


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1100)
    s = seed["schluss"]

    # --- Entwurf ---
    await tab.oeffnen(f"/invoices/{s}", READY)
    p.pruefe("Entwurf: Rechnungsbetrag −119 €", await tab.js("document.querySelector('[data-rechnungsbetrag]').textContent"),
             "-119,00 €")
    p.pruefe("Entwurf: Erstattungsbetrag im Zahlungshinweis", await tab.js(
        "[document.querySelector('[data-erstattungsbetrag]')?.textContent,!!document.querySelector('[data-zahlbetrag]')]"),
        ["119,00 €", False])
    p.pruefe("Entwurf: Satz zur Erstattung statt Fälligkeit und Skonto",
             await tab.js("document.getElementById('paymentTermsSentence').textContent"),
             "Den Erstattungsbetrag von 119,00 € überweisen wir Ihnen.")
    p.pruefe("Entwurf: Finalisieren möglich (kein Grund)", await tab.js(
        "!!document.querySelector('#statusActions button[onclick=\"sendInvoice()\"]')&&!invoice.finalize_block"), True)
    await tab.js("document.getElementById('finalCard').scrollIntoView()")
    await tab.bild("ueberzahlung_entwurf")
    await tab.js("sendInvoice()")
    p.pruefe("finalisiert", await tab.warten("invoice.status==='versendet'"), True)

    # --- Guthaben und Erstattung ---
    p.pruefe("Kennzeichen Guthaben", await tab.js("document.getElementById('statusBadge').textContent.includes('Guthaben 119,00')"),
             True)
    p.pruefe("Karte Zahlungen: Guthaben und Formular", await tab.js(
        "[!!document.querySelector('[data-guthaben]'),document.getElementById('refundAmount')?.value]"), [True, "119,00"])
    await tab.js("document.getElementById('refundAmount').value='100,00';document.getElementById('refundNote').value='Überweisung';"
                 "bookRefund()")
    p.pruefe("Erstattung gebucht, Guthaben 19 €", await tab.warten(
        "Number(invoice.dunning.credit)===19&&document.querySelector('[data-erstattung-zeile]')"), True)
    _passt(p, "Erstattung in den Zuordnungen ohne Gegenbuchen", await tab.js(
        "document.querySelector('[data-erstattung-zeile]').textContent"),
        lambda v: "Erstattung (Zahlungsausgang)" in v and "-100,00" in v and "Kundenakte" in v)
    zuviel = await tab.js(f"fetch('/api/invoices/{s}/refunds',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
                          "body:JSON.stringify({paid_on:berlinToday(),amount:'20.00'})}).then(r=>r.status)")
    p.pruefe("API: zu viel erstattet 409", zuviel, 409)
    pdf = await tab.js(f"fetch('/api/invoices/{s}/pdf').then(r=>[r.status,r.headers.get('content-type')])")
    p.pruefe("PDF aus der Ablage", pdf, [200, "application/pdf"])
    await tab.js("document.getElementById('paymentsCard').scrollIntoView({block:'center'})")
    await tab.bild("ueberzahlung_erstattung")

    # --- Kundenakte ---
    await tab.oeffnen(f"/customers/{seed['kunde']}", CUSTOMER_READY)
    _passt(p, "Kundenakte: Guthaben 19 € mit Link", await tab.js("document.querySelector('#customerCredits [data-guthaben]')?.textContent||''"),
           lambda v: "19,00" in v)
    _passt(p, "Kundenakte: Zahlungsausgang ohne „nicht zugeordnet“", await tab.js(
        "(()=>{const c=[...document.querySelectorAll('[data-zahlung]')].find(x=>x.querySelector('[data-zahlungsausgang]'));"
        "return c?c.textContent:''})()"), lambda v: "-100,00" in v and "nicht zugeordnet" not in v and "Zahlungsausgang Nr." in v)
    pid = await tab.js("customerPaymentsData.payments.find(x=>x.is_refund).id")
    await tab.js(f"showPaymentReverse({pid});document.getElementById('payRevReason-{pid}').value='Überweisung kam zurück';"
                 f"reversePayment({pid})")
    p.pruefe("zurückgenommen: Guthaben wieder 119 €", await tab.warten("Number(customerPaymentsData.credit_total)===119"), True)
    await tab.js("document.getElementById('zahlungen').scrollIntoView()")
    await tab.bild("kundenakte_guthaben")
    p.pruefe("JS-Fehler Büro", tab.fehler, [])

    # --- 412 px dunkel ---
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/invoices/{s}", READY)
    await tab.js("document.documentElement.setAttribute('data-theme','dark');document.getElementById('paymentsCard').scrollIntoView()")
    await tab.bild("ueberzahlung_412_dunkel")
    await tab.fenster(1400, 1100)

    # --- Monteurin ---
    await tab.anmelden(seed["cookies"]["monteurin"])
    status = await tab.js(f"fetch('/api/invoices/{s}/refunds',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
                          "body:JSON.stringify({paid_on:'2026-10-01',amount:'1.00'})}).then(r=>r.status)")
    p.pruefe("Monteurin: 403", status, 403)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
