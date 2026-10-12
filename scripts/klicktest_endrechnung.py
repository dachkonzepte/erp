"""Klicktest: Schlussrechnung als Endrechnung, Abweichung vom Auftrag (1.8.85, R4b Punkte 2, 3 und 5).

docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung R4b":

    Rechnungsseite    Schlussrechnung neben pauschalem Abschlag, Abschlag nach Leistungsstand und Rechnung aus Aufwand: Karte
                      "Endrechnung" mit Gesamtleistung (Positionen und Aufwand), Abzugsblock (drei Rechnungen mit Nummer, netto,
                      USt, brutto), Rechnungsbetrag = oben "Brutto"; Steuerschlüssel gesperrt mit Hinweis; Preis und Einheit der
                      Auftragsposition im Dialog gesperrt; finalisieren, PDF aus der Ablage. Hell, dunkel, 412 px
    Abweichung        Preis am Auftrag nach dem Anlegen des Entwurfs geändert: Grund statt "Finalisieren", Knopf "Aus dem Auftrag
                      aktualisieren", danach Preis übernommen und "Finalisieren" wieder da
    Auftragsseite     nach der Schlussrechnung der Grund für "Rechnung aus Aufwand"

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_endrechnung.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal
    from types import SimpleNamespace

    from app.invoices import (
        add_invoice_item, create_abschlag_leistungsstand, create_abschlag_pauschal, create_invoice_from_time_entries,
        create_schlussrechnung, finalize_and_send_invoice, update_invoice_header, update_invoice_item,
    )
    from app.models import AppUser, Customer, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id

    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Klar", last_name="Klar", street="Dachweg 1", postal_code="52531", city="Uebach")
    db.add_all([buero, kunde]); db.flush()

    def auftrag(nummer):
        projekt = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=kunde.id, status="angebot",
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

    def fest(invoice):
        update_invoice_header(db, invoice, service_period_start=date(2026, 10, 1), service_period_end=date(2026, 10, 5))
        return finalize_and_send_invoice(db, invoice)

    order = auftrag("KT-1")
    fest(create_abschlag_pauschal(db, order, lump_sum_net=Decimal("100")))
    abschlag = create_abschlag_leistungsstand(db, load_order(db, order.id))
    update_invoice_item(db, abschlag, abschlag.items[0], ist_quantity=Decimal("4"))
    fest(abschlag)
    aufwand = create_invoice_from_time_entries(
        db, load_order(db, order.id), [], [SimpleNamespace(material_id=None, description="Kehlblech", unit="Stk.",
                                                           quantity=Decimal("1"))])
    add_invoice_item(db, aufwand, short_text="Reparatur", long_text="", unit="Std.", unit_price=Decimal("50"),
                     ist_quantity=Decimal("1"))
    fest(aufwand)
    schluss = create_schlussrechnung(db, load_order(db, order.id))
    update_invoice_header(db, schluss, service_period_start=date(2026, 10, 1), service_period_end=date(2026, 10, 10))

    abweichend = auftrag("KT-2")
    entwurf = create_schlussrechnung(db, abweichend)
    update_invoice_header(db, entwurf, service_period_start=date(2026, 10, 1), service_period_end=date(2026, 10, 10))
    abweichend.items[0].unit_price = Decimal("60")  # am Auftrag geändert, solange nichts abgerechnet ist (erlaubt)
    db.commit()
    return {"auftrag": order.id, "schluss": schluss.id, "entwurf": entwurf.id, "cookies": {"buero": k.cookies(buero)}}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1280, 1100)
    await tab.anmelden(seed["cookies"]["buero"])
    s = seed["schluss"]

    # --- Endrechnung im Entwurf ---
    await tab.oeffnen(f"/invoices/{s}", "invoice&&invoice.id&&document.getElementById('finalBody').innerHTML")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    p.pruefe("Karte Endrechnung sichtbar", await tab.js("getComputedStyle(document.getElementById('finalCard')).display"),
             "block")
    p.pruefe("Gesamtleistung netto (500 + Aufwand 50)",
             await tab.js("document.querySelector('[data-gesamt-netto]').textContent"), "550,00 €")
    p.pruefe("Abzugsblock: drei Rechnungen", await tab.js("document.querySelectorAll('[data-abzug]').length"), 3)
    p.pruefe("Rechnungsbetrag brutto = oben Brutto",
             await tab.js("[document.querySelector('[data-rechnungsbetrag]').textContent,"
                          "document.getElementById('mGross').textContent]"), ["238,00 €", "238,00 €"])
    p.pruefe("Steuerschlüssel gesperrt, Hinweis",
             await tab.js("[document.getElementById('iTaxKeySelect').disabled,document.getElementById('taxKeyHint').hidden]"),
             [True, False])
    pos = await tab.js("invoice.items[0].id")
    await tab.js(f"openItemDialog({pos})")
    p.pruefe("Dialog: Preis und Einheit aus dem Auftrag gesperrt",
             await tab.js("[document.getElementById('itPrice').disabled,document.getElementById('itUnit').disabled,"
                          "document.getElementById('itIst').disabled]"), [True, True, False])
    await tab.js("document.getElementById('itemDialog').close()")
    await tab.js("document.getElementById('finalCard').scrollIntoView()")
    await tab.bild("endrechnung_entwurf_hell")

    # --- finalisieren, PDF aus der Ablage ---
    await tab.js("sendInvoice()")
    p.pruefe("finalisiert", await tab.warten("invoice.status==='versendet'"), True)
    p.pruefe("Endrechnung danach mit eingefrorenen Abzügen",
             await tab.js("[document.querySelectorAll('[data-abzug]').length,"
                          "document.querySelector('[data-rechnungsbetrag]').textContent]"), [3, "238,00 €"])
    pdf = await tab.js(f"fetch('/api/invoices/{s}/pdf').then(r=>[r.status,r.headers.get('content-type'),"
                       "r.headers.get('X-DK-Ablage')!==null])")
    p.pruefe("PDF aus der Ablage", pdf, [200, "application/pdf", True])
    await tab.js("document.documentElement.setAttribute('data-theme','dark');document.getElementById('finalCard').scrollIntoView()")
    await tab.bild("endrechnung_dunkel")
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/invoices/{s}", "invoice&&invoice.id&&document.getElementById('finalBody').innerHTML")
    await tab.js("document.documentElement.setAttribute('data-theme','dark');document.getElementById('finalCard').scrollIntoView()")
    await tab.bild("endrechnung_412_dunkel")
    await tab.fenster(1280, 1100)

    # --- Auftragsseite: kein Aufwand nach der Schlussrechnung ---
    await tab.oeffnen(f"/orders/{seed['auftrag']}", "order&&order.invoice_create_blocks")
    p.pruefe("Auftrag: Grund für Rechnung aus Aufwand",
             await tab.js("(order.invoice_create_blocks.aufwand||'').includes('keine Rechnung aus Aufwand mehr möglich')"), True)

    # --- Abweichung vom Auftrag ---
    e = seed["entwurf"]
    await tab.oeffnen(f"/invoices/{e}", "invoice&&invoice.id&&document.getElementById('statusActions').innerHTML")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    p.pruefe("Abweichung: Grund statt Finalisieren, Knopf Aktualisieren",
             await tab.js("[(document.querySelector('#statusActions [data-sperre]')?.textContent||'').includes("
                          "'Einheitspreis Pos. 1 (Entwurf 50,00 €, Auftrag 60,00 €)'),"
                          "!!document.querySelector('#statusActions [data-aktualisieren]'),"
                          "[...document.querySelectorAll('#statusActions button')].some(b=>b.textContent==='Rechnung finalisieren')]"),
             [True, True, False])
    await tab.js("document.getElementById('statusActions').scrollIntoView()")
    await tab.bild("abweichung")
    await tab.js("document.querySelector('#statusActions [data-aktualisieren]').click()")
    p.pruefe("Aktualisiert: Preis übernommen, Finalisieren wieder da",
             await tab.warten("invoice.order_deviation===null&&Number(invoice.items[0].unit_price)===60&&"
                              "[...document.querySelectorAll('#statusActions button')].some(b=>b.textContent==='Rechnung finalisieren')"),
             True)
    p.pruefe("Brutto nach dem Aktualisieren", await tab.js("document.getElementById('mGross').textContent"), "714,00 €")
    await tab.js("document.getElementById('statusActions').scrollIntoView()")
    await tab.bild("aktualisiert")
    p.pruefe("JS-Fehler", tab.fehler, [])
    print(json.dumps({"schluss": s, "entwurf": e}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
