"""Klicktest: Kleinkram vor dem Abnahmetest (1.8.94) -- "Bezahlt (gesamt)" abzüglich Erstattungen, Zahlbetrag 0 €, "Zahlung
zurücknehmen" nur wenn möglich, enthaltene Rechnungen gruppiert unter ihrer Schlussrechnung.

Ein Kunde mit drei Aufträgen (je 10 m² × 50 € = 595 € brutto, Abschlag nach Leistungsstand über 10 m² = 595 €):

    Auftrag 1   Abschlag 476 € bezahlt (119 € offen), Schlussrechnung 8 m² als Entwurf (−119 €) -- Zahlbetrag 0 €
    Auftrag 2   Abschlag 300 € bezahlt (295 € offen), Schlussrechnung 12 m² festgeschrieben (+119 €) -- der Abschlag ist in ihr
                enthalten
    Auftrag 3   Abschlag voll bezahlt, Schlussrechnung 8 m² (−119 €), davon 100 € erstattet (Zahlungsausgang)
    dazu        eine Zahlung über 50 € ohne Zuordnung, 20 € daraus erstattet (Rest 30 €)

    Finanzen         "Bezahlt (gesamt)" 1.271 € (476 + 300 + 595 − 100), "abzüglich Erstattungen 100,00 €"
    Kundenakte       an der Zahlung mit Erstattung aus dem Rest der Grund statt "Zahlung zurücknehmen", am Zahlungsausgang der Knopf;
                     "Rest zuordnen auf …" mit der Gruppe "Schlussrechnung …" (Schlussrechnung, darunter der Abschlag "enthalten
                     in …"), Abschlag 1 einzeln; 30 € auf den enthaltenen Abschlag zugeordnet
    Rechnungsseite   Schlussrechnung 2: Zahlungsdialog mit der Gruppe, Schlussrechnung zuerst, Abschlag darunter "enthalten in …",
                     Beträge umverteilt und gebucht (landen auf der richtigen Rechnung); "weitere Rechnung" ohne Gruppe
                     Schlussrechnung 1 (Entwurf): Satz "nichts mehr zu zahlen" statt "zahlbar bis", Hinweis am Schlusstext,
                     finalisieren -> Schlusstext leer, PDF aus der Ablage
    412 px dunkel    Kundenakte und Zahlungsdialog
    API              Monteurin 403

Wartet nach jeder Aktion, die neu lädt, über Tab.warte_auf_neu_geladene_liste() (seit 1.8.94).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_zahlungen_kleinkram.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

SATZ = "Mit den geleisteten Zahlungen ist der Zahlbetrag ausgeglichen – es ist nichts mehr zu zahlen."  # app/invoices.py


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.invoices import (
        create_abschlag_leistungsstand, create_schlussrechnung, finalize_and_send_invoice, update_invoice_header,
        update_invoice_item,
    )
    from app.models import AppUser, Customer, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.payments import Line, RefundLine, book_customer_refund, book_payment, book_refund
    from app.project_pipeline_columns import default_pipeline_column_id

    D = Decimal
    heute = berlin_today()
    # seit 1.9.111: Geld nur Admin und Büro – Finanzen (app/permissions.py::darf_geld()) -- bis dahin Büro – Auftrag
    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_finanzen", password_hash=k.passwort())
    monteurin = AppUser(username="monteurin", display_name="Mia Monteurin", role="field", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Klein", last_name="Klein", street="Dachweg 2", postal_code="52531", city="Uebach",
                     email="klein@example.com")
    db.add_all([buero, monteurin, kunde]); db.flush()

    def zeitraum(invoice):
        update_invoice_header(db, invoice, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 30))
        return invoice

    def auftrag(nr: int):
        projekt = Project(project_number=f"P-KT-{nr}", name=f"Dach {nr}", customer_id=kunde.id, status="angebot",
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-KT-{nr}", project_id=projekt.id, title=f"Dachsanierung {nr}", vat_rate=D("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=D("10"), unit="m2",
                         unit_price=D("50")))
        db.commit()
        order = create_order_from_quote(db, quote.id, order_date=date(2026, 9, 1), execution_start=None, execution_end=None,
                                        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None,
                                        remarks=None)
        abschlag = create_abschlag_leistungsstand(db, load_order(db, order.id))
        update_invoice_item(db, abschlag, abschlag.items[0], ist_quantity=D("10"))
        return order, finalize_and_send_invoice(db, zeitraum(abschlag))

    def zahlen(betrag, invoice=None):
        lines = [Line(invoice.id, zahlung=D(betrag))] if invoice is not None else []
        return book_payment(db, customer_id=kunde.id, received_on=heute, amount=D(betrag), note=None, lines=lines,
                            user_name="Bea Büro")

    def schluss(order, ist, fest=True):
        invoice = create_schlussrechnung(db, load_order(db, order.id))
        update_invoice_item(db, invoice, invoice.items[0], ist_quantity=D(ist))
        zeitraum(invoice)
        return finalize_and_send_invoice(db, invoice) if fest else invoice

    o1, a1 = auftrag(1)
    zahlen("476", a1)
    s1 = schluss(o1, "8", fest=False)  # Zahlbetrag 0 €
    o2, a2 = auftrag(2)
    zahlen("300", a2)
    s2 = schluss(o2, "12")  # +119 €, Abschlag 295 € offen und enthalten
    o3, a3 = auftrag(3)
    zahlen("595", a3)
    s3 = schluss(o3, "8")  # −119 €
    book_refund(db, s3, paid_on=heute, amount=D("100"), note="Überweisung")
    rest = zahlen("50")
    aus_rest = book_customer_refund(db, kunde.id, paid_on=heute, note=None, lines=[RefundLine(D("20"), payment_id=rest.id)])
    return {"kunde": kunde.id, "a1": a1.id, "a2": a2.id, "s1": s1.id, "s2": s2.id, "s2_nr": s2.invoice_number,
            "rest": rest.id, "aus_rest": aus_rest.id,
            "cookies": {"buero": k.cookies(buero), "monteurin": k.cookies(monteurin)}}


INVOICE_READY = "invoice&&invoice.id&&document.getElementById('finalBody').innerHTML"
CUSTOMER_READY = "typeof akte!=='undefined'&&!!akte&&!!customerPaymentsData&&!!document.querySelector('#customerPayments tr[data-zahlung]')"


def _passt(p, name, ist, bedingung):
    """Prüfung über eine Bedingung -- bei Abweichung steht der gelesene Wert in der Ausgabe."""
    p.pruefe(name, "passt" if bedingung(ist) else ist, "passt")


def _auswahl(selektor: str) -> str:
    """Optionen einer Auswahl als [Gruppe oder None, Text] (ohne die Leer-Option)."""
    return (f"[...document.querySelectorAll('{selektor} option')].filter(o=>o.value).map(o=>[o.parentElement.tagName==='OPTGROUP'"
            "?o.parentElement.label:null,o.textContent.replace(/\\u00a0/g,' ')])")


async def _offen(tab, invoice_id) -> str:
    return await tab.js(f"fetch('/api/invoices/{invoice_id}').then(r=>r.json()).then(d=>d.payment&&d.payment.open)")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1100)
    s2_nr = seed["s2_nr"]
    gruppe = f"Schlussrechnung {s2_nr}"

    # --- 1. Finanzen ---
    await tab.oeffnen("/finanzen", "document.querySelector('[data-bezahlt]')")
    p.pruefe("Finanzen: Bezahlt (gesamt) abzüglich Erstattungen", await tab.js(
        "[document.querySelector('[data-bezahlt]').textContent,document.querySelector('[data-erstattet]')?.textContent]"
        ".map(t=>t&&t.replace(/\\u00a0/g,' '))"), ["1.271,00 €", "abzüglich Erstattungen 100,00 €"])
    await tab.bild("finanzen_bezahlt")

    # --- 3. und 4. Kundenakte ---
    await tab.oeffnen(f"/customers/{seed['kunde']}#zahlungen", CUSTOMER_READY)
    rest, aus_rest = seed["rest"], seed["aus_rest"]
    # seit 1.9.137 im Dialog „Zurücknehmen“ aus dem „⋮“ (bis 1.9.136 Grund bzw. Knopf an der Karte)
    p.pruefe("Kundenakte: Zahlung mit Erstattung aus dem Rest -- Grund statt Knopf", await tab.js(
        f"(()=>{{zuruecknehmenOeffnen({rest});const e=[document.getElementById('zuruecknehmenGesperrt').textContent,"
        "!document.getElementById('zuruecknehmenKnopf').hidden];document.getElementById('zuruecknehmenDialog').close();return e})()"),
        [f"Aus dem Rest dieser Zahlung ist erstattet (20,00 €, Zahlungsausgang Nr. {aus_rest}) -- erst den Zahlungsausgang "
         "zurücknehmen.", False])
    p.pruefe("Kundenakte: Zahlungsausgang mit Knopf", await tab.js(
        f"(()=>{{zuruecknehmenOeffnen({aus_rest});const e=!document.getElementById('zuruecknehmenKnopf').hidden;"
        "document.getElementById('zuruecknehmenDialog').close();return e})()"), True)
    a1_nr = await tab.js(f"customerOpenInvoices.find(o=>o.invoice_id==={seed['a1']}).invoice_number")
    a2_nr = await tab.js(f"customerOpenInvoices.find(o=>o.invoice_id==={seed['a2']}).invoice_number")
    await tab.js(f"zuordnenOeffnen({rest},null)")  # seit 1.9.137 im Dialog „Rest zuordnen“, „unbezahlt“ statt „offen“
    p.pruefe("Rest zuordnen: Abschlag 1 einzeln, Gruppe der Schlussrechnung mit dem enthaltenen Abschlag", await tab.js(
        _auswahl("#restInvoice")),
        [[None, f"{a1_nr} · unbezahlt 119,00 €"], [gruppe, f"{s2_nr} · unbezahlt 119,00 €"],
         [gruppe, f"{a2_nr} · unbezahlt 295,00 € · enthalten in Schlussrechnung {s2_nr}"]])
    await tab.js(f"(()=>{{const s=document.getElementById('restInvoice');s.value='{seed['a2']}';"
                 "s.dispatchEvent(new Event('change',{bubbles:true}))})()")
    p.pruefe("Rest zuordnen: Betrag = Rest", await tab.js("document.getElementById('restAmount').value"), "30,00")
    await tab.warte_auf_neu_geladene_liste("allocateRest()", "#customerPayments")
    p.pruefe("Rest auf den enthaltenen Abschlag zugeordnet", [
        await tab.js("document.getElementById('customerPaymentsStatus').textContent"), await _offen(tab, seed["a2"])],
        ["Zugeordnet.", "265.00"])
    await tab.js("document.getElementById('reiter-zahlungen').scrollIntoView()")
    await tab.bild("kundenakte_zahlungen")
    p.pruefe("Kundenakte: JS-Fehler", tab.fehler, [])

    # --- 4. Zahlungsdialog an der Schlussrechnung 2 ---
    await tab.oeffnen(f"/invoices/{seed['s2']}", INVOICE_READY)
    await tab.js("openPaymentDialog()")
    await tab.warten("document.getElementById('paymentDialog').open&&payLines.length===2")
    await tab.warte_auf_neu_geladene_liste()
    p.pruefe("Dialog: Gruppe mit Schlussrechnung zuerst, Abschlag darunter", await tab.js(
        f"[...document.querySelectorAll('#pyLines .py-group[data-gruppe=\"{seed['s2']}\"] [data-zeile]')].map(r=>Number(r.dataset.zeile))"),
        [seed["s2"], seed["a2"]])
    p.pruefe("Dialog: Kopf und Hinweis", await tab.js(
        "[document.querySelector('[data-gruppe-kopf]').textContent,"
        f"document.querySelector('[data-zeile=\"{seed['a2']}\"] [data-enthalten]')?.textContent,"
        f"!!document.querySelector('[data-zeile=\"{seed['s2']}\"] [data-enthalten]')]"),
        [f"Schlussrechnung {s2_nr} und die darin enthaltenen Rechnungen", f"enthalten in Schlussrechnung {s2_nr}", False])
    p.pruefe("Dialog: Vorschlag zuerst auf den älteren Abschlag", await tab.js(
        "payLines.map(l=>[l.invoice_id,l.zahlung])"), [[seed["a2"], "119,00"], [seed["s2"], "0,00"]])
    p.pruefe("Dialog: weitere Rechnung ohne Gruppe", await tab.js(_auswahl("#pyAdd")), [[None, f"{a1_nr} · Auftrag "
                                                                                         + await tab.js(f"payOpen.find(o=>o.invoice_id==={seed['a1']}).order_number")
                                                                                         + " · offen 119,00 €"]])
    # Umverteilen in den Feldern der gruppierten Zeilen: alles auf die Schlussrechnung.
    for invoice_id, wert in ((seed["a2"], "0"), (seed["s2"], "119")):
        await tab.js(f"(()=>{{const i=document.querySelector('[data-zeile=\"{invoice_id}\"] input[data-feld=\"zahlung\"]');"
                     f"i.value='{wert}';i.dispatchEvent(new Event('input'))}})()")
    p.pruefe("Dialog: Eingaben landen an der richtigen Zeile", await tab.js("payLines.map(l=>[l.invoice_id,l.zahlung])"),
             [[seed["a2"], "0"], [seed["s2"], "119"]])
    await tab.fenster(412, 900, mobil=True)
    await tab.js("document.documentElement.setAttribute('data-theme','dark')")
    await tab.bild("dialog_gruppe_412_dunkel")
    _passt(p, "Dialog 412 px: ohne waagrechtes Scrollen", await tab.js(
        "document.querySelector('#paymentDialog .dialog').scrollWidth<=document.querySelector('#paymentDialog .dialog').clientWidth+1"),
        lambda v: v is True)
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.fenster(1400, 1100)
    await tab.warte_auf_neu_geladene_liste("document.getElementById('pyConfirm').click()", "#paymentAllocations")
    p.pruefe("Gebucht: Schlussrechnung bezahlt, Abschlag unverändert", [
        await tab.js("document.getElementById('paymentStatusMsg').textContent"), await _offen(tab, seed["s2"]),
        await _offen(tab, seed["a2"])], ["Gebucht.", "0.00", "265.00"])
    p.pruefe("Rechnungsseite 2: JS-Fehler", tab.fehler, [])

    # --- 2. Zahlbetrag 0 €: Schlussrechnung 1 ---
    await tab.oeffnen(f"/invoices/{seed['s1']}", INVOICE_READY)
    p.pruefe("Entwurf: Zahlbetrag 0 €, Satz statt Fälligkeit", await tab.js(
        "[document.querySelector('[data-zahlbetrag]')?.textContent.replace(/\\u00a0/g,' '),"
        "document.getElementById('paymentTermsSentence').textContent]"), ["0,00 €", SATZ])
    _passt(p, "Entwurf: Hinweis am Schlusstext", await tab.js(
        "document.querySelector('[data-nichts-zu-zahlen]')?.textContent||''"),
        lambda v: "Der Zahlbetrag ist 0 €" in v and SATZ in v)
    p.pruefe("Entwurf: kein Hinweis zur Erstattung", await tab.js("!document.querySelector('[data-erstattung-schlusstext]')"), True)
    await tab.js("document.getElementById('refundOutroNote').scrollIntoView({block:'center'})")
    await tab.bild("nichts_zu_zahlen_entwurf")
    await tab.warte_auf_neu_geladene_liste("sendInvoice()")
    p.pruefe("Finalisiert: Schlusstext leer, Satz bleibt, Hinweis weg", await tab.js(
        "[invoice.status,invoice.outro_text,invoice.nothing_due,document.getElementById('paymentTermsSentence').textContent,"
        "!document.querySelector('[data-nichts-zu-zahlen]')]"), ["versendet", None, True, SATZ, True])
    p.pruefe("PDF aus der Ablage", await tab.js(
        f"fetch('/api/invoices/{seed['s1']}/pdf').then(r=>[r.status,!!r.headers.get('X-DK-Ablage')])"), [200, True])
    p.pruefe("Rechnungsseite 1: JS-Fehler", tab.fehler, [])

    # --- Kundenakte 412 px dunkel ---
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/customers/{seed['kunde']}#zahlungen", CUSTOMER_READY)
    await tab.js("document.documentElement.setAttribute('data-theme','dark');document.getElementById('reiter-zahlungen').scrollIntoView()")
    p.pruefe("Kundenakte 412 px: nichts ragt über den Bildschirm", await tab.ueberlauf(), [])
    await tab.bild("kundenakte_412_dunkel")
    await tab.fenster(1400, 1100)

    # --- Monteurin ---
    await tab.anmelden(seed["cookies"]["monteurin"])
    p.pruefe("Monteurin: offene Rechnungen und Zahlungen 403", await tab.js(
        f"Promise.all(['/api/customers/{seed['kunde']}/open-invoices','/api/customers/{seed['kunde']}/payments']"
        ".map(u=>fetch(u).then(r=>r.status)))"), [403, 403])


if __name__ == "__main__":
    raise SystemExit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
