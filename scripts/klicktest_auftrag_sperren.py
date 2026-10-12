"""Klicktest: Sperren am Auftrag und feste Fassung der Rechnung (1.8.82, R4a Punkte 1 und 2).

docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.82":

    Auftrag mit Abschlag   Position 1 abgerechnet (Ist 4): Einheitspreis und Einheit gesperrt mit Hinweis, Menge offen und
                           speicherbar; Position 2 (Ist 0) frei; Dialog zeigt den Grund, Preis/Einheit/"in Summe" gesperrt;
                           Steuerschlüssel gesperrt mit Grund; die API antwortet 409. Hell, dunkel, 412 px
    Auftrag mit Schluss-   Hinweis "Nach der Schlussrechnung …" über dem LV, jede Eingabe gesperrt, kein Bearbeiten-Knopf an
    rechnung               Positionen und Titeln
    Rechnungsseite         das PDF kommt aus der Ablage (Kopfzeile X-DK-Ablage) und trägt den Briefkopf vom Festschreiben, auch
                           nachdem er geändert wurde; ein Entwurf wird neu erzeugt

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_auftrag_sperren.py [--app-port N] [--cdp-port N]
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

    from app.invoices import (
        create_abschlag_leistungsstand, create_schlussrechnung, finalize_and_send_invoice, update_invoice_header,
        update_invoice_item,
    )
    from app.models import AppUser, Customer, OrderSection, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.settings import load_general_settings

    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Klar", last_name="Klar", street="Dachweg 1", postal_code="52531", city="Uebach")
    db.add_all([buero, kunde]); db.flush()
    load_general_settings(db).company_name = "Briefkopf Alt GmbH"
    db.commit()

    def auftrag(nummer):
        projekt = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=kunde.id, status="angebot",
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-{nummer}", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2",
                         unit_price=Decimal("50")))
        db.add(QuoteItem(quote_id=quote.id, position_number="2", short_text="Rinne", quantity=Decimal("5"), unit="m",
                         unit_price=Decimal("20")))
        db.commit()
        order = create_order_from_quote(db, quote.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
                                        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None,
                                        remarks=None)
        db.add(OrderSection(order_id=order.id, title="Dach", sort_order=5))
        db.commit()
        return load_order(db, order.id)

    def festschreiben(invoice):
        update_invoice_header(db, invoice, service_period_start=date(2026, 10, 1), service_period_end=date(2026, 10, 5))
        return finalize_and_send_invoice(db, invoice)

    mit_abschlag = auftrag("KT-1")
    abschlag = create_abschlag_leistungsstand(db, mit_abschlag)
    erste = min(abschlag.items, key=lambda i: (i.sort_order, i.id))
    update_invoice_item(db, abschlag, erste, ist_quantity=Decimal("4"))
    abschlag = festschreiben(abschlag)
    mit_schluss = auftrag("KT-2")
    schluss = festschreiben(create_schlussrechnung(db, mit_schluss))
    entwurf = create_schlussrechnung(db, auftrag("KT-3"))
    load_general_settings(db).company_name = "Briefkopf Neu GmbH"  # nach dem Festschreiben geändert
    db.commit()
    return {"abschlag_auftrag": mit_abschlag.id, "schluss_auftrag": mit_schluss.id, "abschlag": abschlag.id,
            "abschlag_nr": abschlag.invoice_number, "schluss_nr": schluss.invoice_number, "entwurf": entwurf.id,
            "erste": erste.source_order_item_id, "cookies": {"buero": k.cookies(buero)}}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1280, 1000)
    await tab.anmelden(seed["cookies"]["buero"])
    a, s, nr = seed["abschlag_auftrag"], seed["schluss_auftrag"], seed["abschlag_nr"]
    zeile = "document.querySelector('.lv-row[data-item=\"'+ID+'\"]')"

    # --- Auftrag mit festgeschriebenem Abschlag ---
    await tab.oeffnen(f"/orders/{a}", "order&&document.querySelectorAll('.lv-row').length===2")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    ids =await tab.js("order.items.slice().sort((x,y)=>x.sort_order-y.sort_order).map(i=>i.id)")
    erste, zweite = ids
    eins, zwei = zeile.replace("ID", str(erste)), zeile.replace("ID", str(zweite))
    p.pruefe("Abschlag: EP und Einheit der abgerechneten Position gesperrt",
             await tab.js(f"[{eins}.querySelector('.ep input').disabled,{eins}.querySelector('select').disabled]"), [True, True])
    p.pruefe("Abschlag: Grund im Tooltip", nr in (await tab.js(f"{eins}.querySelector('.ep input').title") or ""), True)
    p.pruefe("Abschlag: Hinweis an der Position", await tab.js(f"{eins}.querySelector('.price-lock')?.textContent"),
             "Abgerechnet – Einheitspreis, Einheit und „in Summe“ gesperrt")
    p.pruefe("Abschlag: Menge offen", await tab.js(f"{eins}.querySelector('input.num').disabled"), False)
    p.pruefe("Abschlag: zweite Position (Ist 0) frei",
             await tab.js(f"[{zwei}.querySelector('.ep input').disabled,!!{zwei}.querySelector('.price-lock')]"), [False, False])
    p.pruefe("Abschlag: Steuerschlüssel gesperrt mit Grund",
             await tab.js("[document.getElementById('taxKey').disabled,!document.getElementById('taxLock').hidden,"
                          "document.getElementById('taxLock').textContent.includes('" + nr + "')]"), [True, True, True])
    p.pruefe("Abschlag: kein Hinweis über dem LV", await tab.js("document.getElementById('lvLock').hidden"), True)
    await tab.bild("abschlag_hell")
    await tab.js(f"openItem({erste})")
    p.pruefe("Dialog: Grund und Sperren",
             await tab.js("[document.getElementById('itemLock').hidden,document.getElementById('itemLock').textContent.includes('"
                          + nr + "'),...['iPrice','iUnit','iIncluded','iQty','iShort'].map(x=>document.getElementById(x).disabled)]"),
             [False, True, True, True, True, False, False])
    await tab.bild("abschlag_dialog")
    await tab.js("document.getElementById('itemDialog').close()")
    await tab.js(f"quickItem({erste},'quantity','12')")
    p.pruefe("Abschlag: Menge gespeichert",
             await tab.warten(f"order.items.find(i=>i.id==={erste}).quantity==12"), True)
    api = await tab.js(f"(()=>{{const i=order.items.find(i=>i.id==={erste});return fetch('/api/orders/{a}/items/{erste}',"
                       "{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({quantity:Number(i.quantity),"
                       "unit:i.unit,unit_price:60,short_text:i.short_text,long_text:i.long_text||'',position_type:i.position_type,"
                       "gaeb_oz:i.gaeb_oz||null,include_in_total:i.include_in_total})}).then(async r=>[r.status,"
                       "(await r.json()).detail.includes('" + nr + "')])})()")
    p.pruefe("Abschlag: API 409 für einen anderen Preis", api, [409, True])
    await tab.js("document.documentElement.setAttribute('data-theme','dark')")
    await tab.bild("abschlag_dunkel")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")

    # --- Auftrag mit Schlussrechnung ---
    await tab.oeffnen(f"/orders/{s}", "order&&document.querySelectorAll('.lv-row').length===2")
    p.pruefe("Schluss: Hinweis über dem LV",
             (await tab.js("document.getElementById('lvLock').hidden?'':document.getElementById('lvLock').textContent") or "")
             .startswith(f"Nach der Schlussrechnung {seed['schluss_nr']} ist der Auftrag abgerechnet"), True)
    p.pruefe("Schluss: jede Eingabe der Positionen gesperrt",
             await tab.js("[...document.querySelectorAll('.lv-row input,.lv-row select')].every(e=>e.disabled)"), True)
    p.pruefe("Schluss: keine Bearbeiten-Knöpfe", await tab.js("document.querySelectorAll('#lv .iconbtn').length"), 0)
    p.pruefe("Schluss: Steuerschlüssel gesperrt", await tab.js("document.getElementById('taxKey').disabled"), True)
    await tab.bild("schluss_hell")
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/orders/{s}", "order&&document.querySelectorAll('.lv-row').length===2")
    await tab.js("document.documentElement.setAttribute('data-theme','dark');document.getElementById('lvLock').scrollIntoView();window.scrollBy(0,-140)")
    await tab.bild("schluss_412_dunkel")
    await tab.fenster(1280, 1000)

    # --- Rechnungsseite: feste Fassung ---
    await tab.oeffnen(f"/invoices/{seed['abschlag']}", "typeof invoice!=='undefined'&&invoice&&invoice.id")
    pdf = await tab.js(f"fetch('/api/invoices/{seed['abschlag']}/pdf').then(r=>[r.status,!!r.headers.get('X-DK-Ablage')])")
    p.pruefe("Rechnung: PDF aus der Ablage", pdf, [200, True])
    entwurf = await tab.js(f"fetch('/api/invoices/{seed['entwurf']}/pdf').then(r=>[r.status,r.headers.get('X-DK-Ablage')])")
    p.pruefe("Entwurf: PDF neu erzeugt", entwurf, [200, None])
    p.pruefe("JS-Fehler", tab.fehler, [])
    print(json.dumps({"abschlag_auftrag": a, "schluss_auftrag": s}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
