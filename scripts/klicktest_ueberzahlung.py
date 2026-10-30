"""Klicktest: Überzahlung -- Schlussrechnung unter 0 €, Erstattung als Zahlungsausgang, Guthaben am Kunden (1.8.90, R4c Punkte 6 und 7;
seit 1.8.92 Schlusstext bei Erstattung, Nacharbeit R4c Punkt 2; seit 1.8.93 Guthaben des Kunden aus Rest und Überzahlung, Punkt 3).

Ein Auftrag (10 m² × 50 € = 595 € brutto) mit einem Abschlag nach Leistungsstand über 10 m² (595 €), voll bezahlt; die Schlussrechnung
mit dem Aufmaß 8 m² lautet über −119 € (Überzahlung). Dazu ein Zahlungsbedingungs-Skonto am Entwurf und (seit 1.8.93) eine Zahlung
über 50 € ohne Zuordnung.

    Rechnungsseite     Entwurf: Rechnungsbetrag −119 €, Zahlungshinweis "Erstattungsbetrag (Überzahlung) 119,00 €", Satz "Den
                       Erstattungsbetrag … überweisen wir Ihnen." statt Fälligkeit und Skonto, Finalisieren möglich; danach Kennzeichen
                       "Guthaben 119,00 €", Karte Zahlungen mit Guthaben und Erstattung buchen (100 €) -> Guthaben 19 €; PDF;
                       seit 1.8.92 im Entwurf der Hinweis "Text für die Erstattung" am Schlusstext, nach dem Finalisieren ist er
                       der Schlusstext
    Einstellungen      Auswahlliste "Rechnungs-Schlusstexte bei Erstattung" (seit 1.8.92)
    Kundenakte         Guthaben des Kunden 69 € (Rest 50 € + 19 €) aufgeschlüsselt, Zahlungsausgang (Erstattung) −100 € ohne "nicht
                       zugeordnet", zurücknehmen -> 169 €; seit 1.8.93 eine Erstattung für Rest und Überzahlung zusammen -> kein
                       Guthaben, Quelle an Zahlungsausgang und Zahlung; an der Zahlung mit erstattetem Rest seit 1.8.94 der Grund
                       statt "Zahlung zurücknehmen" (API 409)
    Finanzen           seit 1.8.93 "Guthaben der Kunden" 169 € davon nicht zugeordnet 50 €, Zeile des Kunden
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

    # seit 1.9.111: Geld nur Admin und Büro – Finanzen (app/permissions.py::darf_geld()) -- bis dahin Büro – Auftrag

    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_finanzen", password_hash=k.passwort())
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
    rest = book_payment(db, customer_id=kunde.id, received_on=berlin_today(), amount=Decimal("50"), note="doppelt überwiesen",
                        lines=[], user_name="Bea Büro")  # seit 1.8.93: nicht zugeordneter Rest
    schluss = create_schlussrechnung(db, load_order(db, order.id))
    update_invoice_item(db, schluss, schluss.items[0], ist_quantity=Decimal("8"))  # Aufmaß kleiner als abgeschlagen
    update_invoice_header(db, schluss, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 10, 10))
    db.execute(update(Invoice).where(Invoice.id == schluss.id).values(skonto_percent=Decimal("2"), skonto_days=10))
    db.commit()
    return {"schluss": schluss.id, "kunde": kunde.id, "rest": rest.id,
            "cookies": {"buero": k.cookies(buero), "monteurin": k.cookies(monteurin)}}


def _passt(p, name, ist, bedingung):
    """Prüfung über eine Bedingung -- bei Abweichung steht der gelesene Wert in der Ausgabe."""
    p.pruefe(name, "passt" if bedingung(ist) else ist, "passt")


READY = "invoice&&invoice.id&&document.getElementById('finalBody').innerHTML"
ERSTATTUNG_TEXT = ("Vielen Dank für Ihren Auftrag. Sollte sich Ihre Bankverbindung geändert haben, teilen Sie uns diese bitte für die "
                   "Erstattung mit.")  # Vorgabe der Auswahlliste (app/option_settings.py, seit 1.8.92)
CUSTOMER_READY = "typeof akte!=='undefined'&&!!akte&&!!customerPaymentsData&&!!document.querySelector('#customerPayments tr[data-zahlung]')"


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
    _passt(p, "Entwurf: Hinweis „Text für die Erstattung“ am Schlusstext (seit 1.8.92)", await tab.js(
        "document.querySelector('[data-erstattung-schlusstext]')?.textContent||''"),
        lambda v: "Rechnungs-Schlusstexte bei Erstattung" in v and ERSTATTUNG_TEXT in v)
    await tab.js("document.getElementById('refundOutroNote').scrollIntoView({block:'center'})")
    await tab.bild("ueberzahlung_schlusstext")
    await tab.js("document.getElementById('finalCard').scrollIntoView()")
    await tab.bild("ueberzahlung_entwurf")
    await tab.js("sendInvoice()")
    p.pruefe("finalisiert", await tab.warten("invoice.status==='versendet'"), True)
    p.pruefe("finalisiert: Schlusstext = Text für die Erstattung, Hinweis weg", await tab.js(
        "[invoice.outro_text,!!document.querySelector('[data-erstattung-schlusstext]')]"), [ERSTATTUNG_TEXT, False])

    # --- Guthaben und Erstattung ---
    p.pruefe("Kennzeichen Guthaben", await tab.js("document.getElementById('seitenkopfStatus').textContent.includes('Guthaben 119,00')"),
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
    await tab.oeffnen(f"/customers/{seed['kunde']}#zahlungen", CUSTOMER_READY)
    # Seit 1.8.93: Rest und Überzahlung zusammen als "Guthaben des Kunden" (Erwartung geändert, bis 1.8.92 nur "19,00").
    # seit 1.9.137: Kennzahl „Guthaben“, je Posten ein Vorschlag; die Zeilen stehen im Dialog „Erstattung buchen“ (bis 1.9.136 Karte mit Zeilen)
    p.pruefe("Kundenakte: Guthaben des Kunden 69 € aus Rest und Überzahlung", await tab.js(
        "[document.querySelectorAll('#zKacheln .gross')[1].textContent.replace(/\\u00a0/g,' '),"
        "customerPaymentsData.balance.lines.map(l=>l.kind),document.querySelectorAll('#zVorschlaege [data-vorschlag]').length]"),
        ["69,00 €", ["rest", "guthaben"], 2])
    _passt(p, "Kundenakte: Zahlungsausgang ohne „nicht zugeordnet“", await tab.js(
        "(()=>{const c=document.querySelector('tr[data-zahlungsausgang]');return c?c.textContent:''})()"),
        lambda v: "-100,00" in v and "Rest " not in v and "Erstattung (Zahlungsausgang)" in v)
    pid = await tab.js("customerPaymentsData.payments.find(x=>x.is_refund).id")
    await tab.js(f"zuruecknehmenOeffnen({pid});document.getElementById('payRevReason').value='Überweisung kam zurück';reversePayment()")
    p.pruefe("zurückgenommen: Guthaben wieder 119 €, des Kunden 169 €", await tab.warten(
        "Number(customerPaymentsData.credit_total)===119&&Number(customerPaymentsData.balance.total)===169"), True)
    await tab.js("document.getElementById('reiter-zahlungen').scrollIntoView()")
    await tab.bild("kundenakte_guthaben")

    # --- Finanzen: Guthaben der Kunden (seit 1.8.93) ---
    await tab.oeffnen("/finanzen", "allInvoices.length>0&&document.getElementById('metrics').innerHTML")
    p.pruefe("Finanzen: Guthaben der Kunden 169 €, davon nicht zugeordnet 50 €", await tab.js(
        "[document.querySelector('#metrics [data-guthaben]')?.textContent.replace(/\\u00a0/g,' '),"
        "document.querySelector('#metrics [data-nicht-zugeordnet]')?.textContent.replace(/\\u00a0/g,' ')]"),
        ["169,00 €", "davon nicht zugeordnet 50,00 €"])
    _passt(p, "Finanzen: Zeile des Kunden mit Rest und Überzahlung", await tab.js(
        f"document.querySelector('[data-kunde-guthaben=\"{seed['kunde']}\"]')?.textContent.replace(/\\u00a0/g,' ')||''"),
        lambda v: "169,00 €" in v and "nicht zugeordnet 50,00 €" in v and "Überzahlung 119,00 €" in v)

    # --- Kundenakte: eine Erstattung für Rest und Überzahlung (seit 1.8.93) ---
    await tab.oeffnen(f"/customers/{seed['kunde']}#zahlungen", CUSTOMER_READY)
    await tab.js("erstattenOeffnen();document.getElementById('custRefundNote').value='Überweisung an den Kunden';bookCustomerRefund()")
    p.pruefe("Erstattung gebucht: kein Guthaben mehr", await tab.warten(
        "Number(customerPaymentsData.balance.total)===0&&document.getElementById('zKacheln').textContent.includes('kein Guthaben')"),
        True)
    _passt(p, "Zahlungsausgang −169 € mit Quelle, Zahlung mit „aus dem Rest erstattet“", await tab.js(
        f"(()=>{{const a=customerPaymentsData.payments.find(x=>x.is_refund&&!x.reversed);"
        f"const q=document.querySelector('tr[data-zahlung=\"'+a.id+'\"] [data-erstattet-aus=\"{seed['rest']}\"]');"
        f"const z=document.querySelector('tr[data-zahlung=\"{seed['rest']}\"] [data-erstattet-mit]');"
        "return [a.amount,q?q.textContent:'',z?z.textContent:'']})()"),
        lambda v: v[0] == "-169.00" and "aus dem Rest des Eingangs" in v[1] and "erstattet am" in v[2])
    rest = seed["rest"]
    # Seit 1.8.94: statt des Knopfs steht an der Zahlung der Grund (bis 1.8.93 kam die Ablehnung erst nach "Zurücknahme
    # bestätigen" -- Erwartung geändert seit 1.8.94); die API lehnt weiter ab.
    # seit 1.9.137 im Dialog „Zurücknehmen“: der Grund statt Feld und Knopf
    p.pruefe("Zahlung mit erstattetem Rest: Grund statt „Zurücknahme bestätigen“", await tab.js(
        f"(async()=>{{zuruecknehmenOeffnen({rest});const e=[document.getElementById('zuruecknehmenGesperrt').textContent.includes('erst den Zahlungsausgang "
        f"zurücknehmen'),!document.getElementById('zuruecknehmenKnopf').hidden,"
        f"await fetch('/api/payments/{rest}/reverse',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        "body:JSON.stringify({reason:'falsch erfasst'})}).then(r=>r.status)];document.getElementById('zuruecknehmenDialog').close();return e})()"), [True, False, 409])
    zuviel = await tab.js(f"fetch('/api/customers/{seed['kunde']}/refunds',{{method:'POST',headers:{{'Content-Type':"
                          f"'application/json'}},body:JSON.stringify({{paid_on:berlinToday(),lines:[{{payment_id:{rest},"
                          "amount:'1.00'}]})}).then(r=>r.status)")
    p.pruefe("API: Rest schon erstattet 409", zuviel, 409)
    await tab.js("document.getElementById('reiter-zahlungen').scrollIntoView()")
    await tab.bild("kundenakte_erstattung_rest")
    # --- Einstellungen (seit 1.8.92) ---
    await tab.oeffnen("/settings", "optionGroups.length>0")
    p.pruefe("Einstellungen: Auswahlliste „Rechnungs-Schlusstexte bei Erstattung“", await tab.js(
        "(()=>{const g=optionGroups.find(x=>x.group_key==='invoice_refund_texts');return g?[g.label,g.options[0].value]:null})()"),
        ["Rechnungs-Schlusstexte bei Erstattung", ERSTATTUNG_TEXT])
    p.pruefe("JS-Fehler Büro", tab.fehler, [])

    # --- 412 px dunkel ---
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/invoices/{s}", READY)
    await tab.js("document.documentElement.setAttribute('data-theme','dark');document.getElementById('paymentsCard').scrollIntoView()")
    await tab.bild("ueberzahlung_412_dunkel")
    await tab.oeffnen(f"/customers/{seed['kunde']}#zahlungen", CUSTOMER_READY)  # seit 1.8.93: Kundenakte mit Zahlungsausgang
    await tab.js("document.documentElement.setAttribute('data-theme','dark');document.getElementById('reiter-zahlungen').scrollIntoView()")
    await tab.bild("kundenakte_412_dunkel")
    await tab.fenster(1400, 1100)

    # --- Monteurin ---
    await tab.anmelden(seed["cookies"]["monteurin"])
    status = await tab.js(f"fetch('/api/invoices/{s}/refunds',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
                          "body:JSON.stringify({paid_on:'2026-10-01',amount:'1.00'})}).then(r=>r.status)")
    p.pruefe("Monteurin: 403", status, 403)
    status = await tab.js(f"fetch('/api/customers/{seed['kunde']}/refunds',{{method:'POST',headers:{{'Content-Type':"
                          f"'application/json'}},body:JSON.stringify({{paid_on:'2026-10-01',lines:[{{payment_id:{seed['rest']},"
                          "amount:'1.00'}]})}).then(r=>r.status)")
    p.pruefe("Monteurin: Erstattung in der Kundenakte 403 (seit 1.8.93)", status, 403)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
