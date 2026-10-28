"""Klicktest: Zahlungseingänge (1.8.78, Zahlungsstufe Z1, docs/archiv/zahlungen.md).

    Rechnungsseite     Karte "Zahlungen" (Brutto, offen, Zahlstand), kein "Als bezahlt markieren" mehr; Dialog "Zahlungseingang
                       buchen": Vorschlag zuerst auf den älteren offenen Abschlag desselben Auftrags, Skonto nur, wenn der
                       Betrag passt (1.773,10 = 1.190,00 + 583,10 mit 11,90 Skonto), neuere Rechnung nicht vorgeschlagen;
                       bestätigt -> beide bezahlt; Einbehalt nur von Hand -> "Einbehalt offen", mahnfähig 0; Skonto-Hinweis
                       "außerhalb der Frist"; Überbuchung im Dialog: Warnung, "Buchung bestätigen" gesperrt; weitere
                       Rechnung des Kunden von Hand; Gegenbuchen nur mit Begründung -> Storno wieder möglich
    Kundenakte         Karte "Zahlungen": nicht zugeordneter Rest, Rest zuordnen, Zahlung zurücknehmen mit Begründung
    Finanzen           offener Betrag statt Brutto (seit 1.9.129 Kachel "Unbezahlt"), Filter "Einbehalt offen" (Zeilen der einen
                       Rechnungsliste `#rows tbody tr`), nicht zugeordnete Zahlungen
    API                Rechnung eines fremden Kunden 409; Monteurin 403
    412 px dunkel      Karte "Zahlungen" und Dialog

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_zahlungen.py [--app-port N] [--cdp-port N]
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
    from app.invoices import create_abschlag_pauschal, finalize_and_send_invoice, update_invoice_header, \
        update_invoice_payment_term
    from app.models import AppUser, Customer, Invoice, PaymentTerm, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.payments import Line, book_payment
    from app.project_pipeline_columns import default_pipeline_column_id

    # seit 1.9.111: Geld nur Admin und Büro – Finanzen (app/permissions.py::darf_geld()) -- bis dahin Büro – Auftrag

    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_finanzen", password_hash=k.passwort())
    monteurin = AppUser(username="monteurin", display_name="Mia Monteurin", role="field", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Zahl", last_name="Zahl", street="Dachweg 1", postal_code="52531", city="Uebach",
                     email="zahl@example.com")
    fremd = Customer(name="Fremd GmbH", last_name="Fremd")
    skonto = PaymentTerm(label="14 Tage, 2 % Skonto 10 Tage", days=14, skonto_percent=Decimal("2"), skonto_days=10)
    db.add_all([buero, monteurin, kunde, fremd, skonto]); db.flush()

    def auftrag(nummer, customer=kunde):
        projekt = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=customer.id, status="angebot",
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-{nummer}", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2",
                         unit_price=Decimal("50")))
        db.commit()
        order = create_order_from_quote(db, quote.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
                                        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None,
                                        remarks=None)
        return load_order(db, order.id)

    def pauschal(order, net, *, mit_skonto=False):
        invoice = create_abschlag_pauschal(db, load_order(db, order.id), lump_sum_net=Decimal(net))
        if mit_skonto:
            update_invoice_payment_term(db, invoice, skonto.id)
        update_invoice_header(db, invoice, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 30))
        return finalize_and_send_invoice(db, invoice)

    z1 = auftrag("Z-1")
    aelter = pauschal(z1, "1000")                    # 1.190,00
    gewaehlt = pauschal(z1, "500", mit_skonto=True)  # 595,00, Skonto 11,90 bis heute + 10
    neuer = pauschal(z1, "100")                      # 119,00 -- neuer, nicht vorgeschlagen
    z2 = auftrag("Z-2")
    andere = pauschal(z2, "300")                     # 357,00 -- anderer Auftrag, nur von Hand
    z3 = auftrag("Z-3")
    einbehalt = pauschal(z3, "1000", mit_skonto=True)
    einbehalt.invoice_date = berlin_today() - timedelta(days=20)  # Skontofrist längst vorbei
    einbehalt.due_date = berlin_today() - timedelta(days=6)
    db.commit()
    z4 = auftrag("Z-4")
    storno_fall = pauschal(z4, "200")                # 238,00, davon 200 bezahlt -> Storno gesperrt
    zahlung = book_payment(db, customer_id=kunde.id, received_on=berlin_today() - timedelta(days=2), amount=Decimal("200"),
                           note="Überweisung Z-4", lines=[Line(storno_fall.id, zahlung=Decimal("200"))], user_name="Bea Büro")
    fremd_rechnung = pauschal(auftrag("F-1", fremd), "100")
    return {"kunde": kunde.id, "aelter": aelter.id, "aelter_nr": aelter.invoice_number, "gewaehlt": gewaehlt.id,
            "gewaehlt_nr": gewaehlt.invoice_number, "neuer": neuer.id, "andere": andere.id, "andere_nr": andere.invoice_number,
            "einbehalt": einbehalt.id, "storno_fall": storno_fall.id, "zahlung": zahlung.id,
            "fremd_rechnung": fremd_rechnung.id, "fremd_nr": fremd_rechnung.invoice_number,
            "cookies": {"buero": k.cookies(buero), "monteurin": k.cookies(monteurin)}}


INVOICE_READY = "invoice&&document.getElementById('paymentSummary').innerHTML.length>0"


async def _bild(tab, name, element, dunkel=False):
    await tab.js(f"document.documentElement.setAttribute('data-theme','light');"
                 f"document.getElementById('{element}').scrollIntoView({{block:'center'}})")
    await tab.bild(name)
    if dunkel:
        await tab.js("document.documentElement.setAttribute('data-theme','dark')")
        await tab.bild(name + "_dunkel")
        await tab.js("document.documentElement.setAttribute('data-theme','light')")


async def _dialog(tab):
    await tab.js("openPaymentDialog()")
    return await tab.warten("document.getElementById('paymentDialog').open&&payLines.length>0")


async def _betrag(tab, wert, bedingung):
    await tab.js(f"(()=>{{const a=document.getElementById('pyAmount');a.value='{wert}';a.dispatchEvent(new Event('input'))}})()")
    return await tab.warten(bedingung)


async def _zeilen(tab):
    return await tab.js("payLines.map(l=>[l.invoice_number,l.zahlung,l.skonto,l.einbehalt])")


async def _karte(tab):
    return await tab.js("({badge:document.getElementById('seitenkopfStatus').textContent,offen:document.querySelector('[data-offen]')"
                        "?.textContent||null,einbehalt:document.querySelector('[data-einbehalt]')?.textContent||null,mahnfaehig:"
                        "document.querySelector('[data-mahnfaehig]')?.textContent||null,stand:document.querySelector("
                        "'[data-zahlstand]')?.textContent||null,knopf:!!document.querySelector('#paymentActions button'),"
                        "info:document.getElementById('statusInfo').textContent,status:[...document.querySelectorAll("
                        "'#statusActions button')].map(b=>b.textContent.trim())})")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1280, 1000)
    await tab.anmelden(seed["cookies"]["buero"])

    # --- Rechnungsseite: Karte und Vorschlag ---
    await tab.oeffnen(f"/invoices/{seed['gewaehlt']}", INVOICE_READY)
    karte = await _karte(tab)
    p.pruefe("Karte: offen, Knopf, kein Bezahlt-Knopf",
             [karte["badge"], karte["offen"], karte["knopf"], "Als bezahlt markieren" in karte["status"]],
             ["Offen", "595,00\xa0€", True, False])
    p.pruefe("Dialog geöffnet", await _dialog(tab), True)
    p.pruefe("Vorschlag 595: erst der ältere Abschlag, der neuere nicht",
             await _zeilen(tab), [[seed["aelter_nr"], "595,00", "0,00", "0,00"], [seed["gewaehlt_nr"], "0,00", "0,00", "0,00"]])
    hinweis = await tab.js("document.querySelector('[data-zeile=\"" + str(seed["gewaehlt"]) +
                           "\"] [data-skonto-hinweis]')?.textContent")
    p.pruefe("Skonto-Hinweis in der Frist", [(hinweis or "").startswith("Skonto laut Rechnung 11,90"),
                                            "außerhalb" in (hinweis or "x")], [True, False])
    p.pruefe("Vorschlag 1.773,10: Skonto, weil der Betrag passt",
             await _betrag(tab, "1773,10", "payLines.length===2&&payLines[1].skonto==='11,90'"), True)
    p.pruefe("Zeilen mit Skonto", await _zeilen(tab),
             [[seed["aelter_nr"], "1190,00", "0,00", "0,00"], [seed["gewaehlt_nr"], "583,10", "11,90", "0,00"]])
    p.pruefe("Rest 0", await tab.js("document.querySelector('[data-rest]').textContent"), "0,00\xa0€")
    p.pruefe("neuere Rechnung nur von Hand", await tab.js(
        f"[...document.getElementById('pyAdd').options].some(o=>o.value==='{seed['neuer']}')"), True)
    await _bild(tab, "dialog_vorschlag_skonto", "pyLines", dunkel=True)
    await tab.js("confirmPayment()")
    p.pruefe("gebucht: Dialog zu, bezahlt", await tab.warten(
        "!document.getElementById('paymentDialog').open&&invoice.payment&&invoice.payment.state==='bezahlt'"), True)
    karte = await _karte(tab)
    p.pruefe("Karte nach Buchung", [karte["badge"], karte["offen"], karte["knopf"]], ["Bezahlt", "0,00\xa0€", False])
    aelter = await tab.js(f"fetch('/api/invoices/{seed['aelter']}').then(r=>r.json()).then(d=>d.payment.state)")
    p.pruefe("älterer Abschlag ebenfalls bezahlt", aelter, "bezahlt")
    p.pruefe("Zuordnungen mit Skonto", await tab.js(
        "invoice.payment_allocations.map(a=>a.kind+' '+a.amount)"), ["zahlung 583.10", "skonto 11.90"])
    await _bild(tab, "rechnung_bezahlt", "paymentsCard")

    # --- Einbehalt nur von Hand; Skonto außerhalb der Frist ---
    await tab.oeffnen(f"/invoices/{seed['einbehalt']}", INVOICE_READY)
    p.pruefe("Einbehalt: überfällig", await tab.js("invoice.is_overdue"), True)
    await _dialog(tab)
    p.pruefe("Skonto außerhalb der Frist: Hinweis, kein Skonto", await tab.js(
        "[document.querySelector('[data-skonto-hinweis]').textContent.includes('außerhalb der Frist'),payLines[0].skonto]"),
             [True, "0,00"])
    p.pruefe("Vorschlag 1.130,50", await _betrag(tab, "1130,50", "payLines[0].zahlung==='1130,50'"), True)
    p.pruefe("Einbehalt nie vorgeschlagen", await tab.js("payLines.every(l=>l.einbehalt==='0,00')"), True)
    await tab.js("(()=>{const i=document.querySelector('[data-zeile] input[data-feld=\"einbehalt\"]');i.value='59,50';"
                 "i.dispatchEvent(new Event('input'))})()")
    p.pruefe("Zusammenfassung mit Einbehalt", await tab.js("document.getElementById('pySummary').textContent.includes("
                                                         "'Einbehalt 59,50')"), True)
    await tab.js("confirmPayment()")
    p.pruefe("gebucht: Einbehalt offen", await tab.warten("invoice.payment&&invoice.payment.state==='einbehalt_offen'"), True)
    karte = await _karte(tab)
    p.pruefe("Karte Einbehalt", [karte["badge"], karte["offen"], karte["einbehalt"], karte["mahnfaehig"]],
             ["Einbehalt offen", "59,50\xa0€", "59,50\xa0€", "0,00\xa0€"])
    p.pruefe("nicht mehr überfällig, Hinweis", [await tab.js("invoice.is_overdue"),
                                              karte["info"].startswith("Offen ist nur noch der Einbehalt von 59,50")],
             [False, True])
    await tab.fenster(412, 900, mobil=True)
    await _bild(tab, "einbehalt_412", "paymentsCard", dunkel=True)
    await tab.fenster(1280, 1000)

    # --- Überbuchung im Dialog, weitere Rechnung von Hand ---
    await tab.oeffnen(f"/invoices/{seed['andere']}", INVOICE_READY)
    await _dialog(tab)
    await tab.js("(()=>{const i=document.querySelector('[data-zeile] input[data-feld=\"zahlung\"]');i.value='400';"
                 "i.dispatchEvent(new Event('input'))})()")
    p.pruefe("Überbuchung: Warnung, Bestätigen gesperrt", await tab.js(
        "[!!document.querySelector('[data-warnung]'),document.getElementById('pyConfirm').disabled]"), [True, True])
    await tab.js(f"(()=>{{const s=document.getElementById('pyAdd');s.value='{seed['neuer']}';s.dispatchEvent(new Event('change'))}})()")
    p.pruefe("weitere Rechnung von Hand ergänzt", await tab.js("payLines.map(l=>l.invoice_id)"), [seed["andere"], seed["neuer"]])
    await tab.fenster(412, 900, mobil=True)
    await _bild(tab, "dialog_ueberbuchung_412", "pySummary", dunkel=True)
    await tab.fenster(1280, 1000)
    await tab.js("document.getElementById('paymentDialog').close()")

    # --- Gegenbuchen: nur mit Begründung; danach Storno möglich ---
    await tab.oeffnen(f"/invoices/{seed['storno_fall']}", INVOICE_READY)
    p.pruefe("Storno gesperrt mit Grund", await tab.js(
        "[...document.querySelectorAll('#statusActions button')].some(b=>b.textContent.trim()==='Stornieren')||"
        "document.querySelector('#statusActions [data-sperre]').textContent"),
             "Der Rechnung sind Zahlungen zugeordnet (Zahlung 200,00 €). Erst die Zuordnungen lösen (Gegenbuchung mit "
             "Begründung) -- die Zahlung bleibt dann beim Kunden, nicht zugeordnet.")
    zuordnung = await tab.js("invoice.payment_allocations[0].id")
    await tab.js(f"showReverse({zuordnung});reverseAllocation({zuordnung})")
    p.pruefe("ohne Begründung abgelehnt", await tab.warten(
        "document.getElementById('paymentStatusMsg').textContent==='Bitte eine Begründung angeben.'"), True)
    await tab.js(f"document.getElementById('revReason-{zuordnung}').value='Rechnung wird storniert';reverseAllocation({zuordnung})")
    p.pruefe("gegengebucht", await tab.warten("invoice.payment_allocations[0].reversed"), True)
    p.pruefe("Gegenbuchung sichtbar", await tab.js("document.querySelector('[data-gegenbuchung]').textContent"),
             "Gegengebucht von Bea Büro: Rechnung wird storniert")
    p.pruefe("Stornieren wieder möglich", await tab.js(
        "[...document.querySelectorAll('#statusActions button')].some(b=>b.textContent.trim()==='Stornieren')"), True)
    await _bild(tab, "gegenbuchung", "paymentsCard", dunkel=True)

    # --- Kundenakte: Rest zuordnen, Zahlung zurücknehmen ---
    await tab.oeffnen(f"/customers/{seed['kunde']}#zahlungen", "customerPaymentsData")
    # Seit 1.8.93 (Nacharbeit R4c Punkt 3) zeigt das Kennzeichen das Guthaben des Kunden (Rest und Überzahlung zusammen); bis 1.8.92
    # "Nicht zugeordnet: …" bzw. "Nichts offen zuzuordnen".
    p.pruefe("Kunde: Rest sichtbar (Guthaben des Kunden)", await tab.js("document.getElementById('paymentRestBadge').textContent"),
             "Guthaben des Kunden: 200,00\xa0€")
    z = seed["zahlung"]
    await tab.js(f"(()=>{{const s=document.getElementById('restInvoice-{z}');s.value='{seed['andere']}';"
                 f"s.dispatchEvent(new Event('change'))}})()")
    p.pruefe("Betrag = kleiner von Rest und offen", await tab.js(f"document.getElementById('restAmount-{z}').value"), "200,00")
    await tab.js(f"allocateRest({z})")
    p.pruefe("Rest zugeordnet", await tab.warten(
        "document.getElementById('customerPaymentsStatus').textContent==='Zugeordnet.'"), True)
    p.pruefe("Kunde: nichts mehr offen", await tab.js("document.getElementById('paymentRestBadge').textContent"),
             "Kein Guthaben")
    await _bild(tab, "kunde_zahlungen", "zahlungen", dunkel=True)
    await tab.js(f"showPaymentReverse({z});document.getElementById('payRevReason-{z}').value='nie eingegangen';reversePayment({z})")
    p.pruefe("Zahlung zurückgenommen", await tab.warten(
        "document.getElementById('customerPaymentsStatus').textContent==='Zahlung zurückgenommen.'"), True)
    p.pruefe("zurückgenommen sichtbar", await tab.js(
        f"document.querySelector('[data-zahlung=\"{z}\"]').textContent.includes('zurückgenommen von Bea Büro: nie eingegangen')"),
             True)
    andere = await tab.js(f"fetch('/api/invoices/{seed['andere']}').then(r=>r.json()).then(d=>d.payment.open)")
    p.pruefe("andere Rechnung wieder offen", andere, "357.00")

    # --- Finanzen ---
    await tab.oeffnen("/finanzen", "allInvoices.length>0&&document.getElementById('metrics').innerHTML.length>0")
    erwartet = await tab.js("money(allInvoices.filter(i=>i.payment).reduce((s,i)=>s+Number(i.payment.open),0))")
    p.pruefe("Offener Betrag = Summe offen", await tab.js("document.querySelector('[data-offen-betrag]').textContent"), erwartet)
    p.pruefe("Offener Betrag ist nicht die Brutto-Summe", erwartet != await tab.js(
        "money(allInvoices.filter(i=>i.status==='versendet').reduce((s,i)=>s+Number(i.gross_total),0))"), True)
    await tab.js("setFilter('einbehalt_offen')")
    # seit 1.9.129 ist #rows der Behälter der einen Rechnungsliste (_rechnungsliste.html), die Zeilen stehen in tbody
    p.pruefe("Filter Einbehalt offen", await tab.js("[...document.querySelectorAll('#rows tbody tr')].length"), 1)
    await _bild(tab, "finanzen", "metrics", dunkel=True)

    # --- API: fremde Rechnung; Monteurin ---
    antwort = await tab.js(
        f"fetch('/api/payments',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{customer_id:"
        f"{seed['kunde']},received_on:'2026-10-01',amount:'10',lines:[{{invoice_id:{seed['fremd_rechnung']},zahlung:'10'}}]}})}})"
        ".then(async r=>[r.status,(await r.json()).detail])")
    p.pruefe("API: Rechnung eines fremden Kunden 409", antwort,
             [409, f"Die Rechnung {seed['fremd_nr']} gehört zu einem anderen Kunden als die Zahlung."])
    p.pruefe("JS-Fehler", tab.fehler, [])
    await tab.anmelden(seed["cookies"]["monteurin"])
    status = await tab.js(f"fetch('/api/customers/{seed['kunde']}/payments').then(r=>r.status)")
    p.pruefe("Monteurin: Zahlungen 403", status, 403)
    print(json.dumps({k: v for k, v in seed.items() if k != "cookies"}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
