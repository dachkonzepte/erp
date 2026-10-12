"""Klicktest: Nachtrag am Auftrag, freie Positionen nur aus Aufwand, negativer Abschlag (1.8.83, R4a Punkte 3 und 4).

docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.83":

    Auftragsseite     "+ Nachtrag" öffnet den Dialog "Nachtrag anlegen" (ohne Positionstyp und OZ), gespeichert steht er als N1
                      mit Kennzeichen unter "Nachträge" hinter allen Titeln, die Summe wächst; "Nachtrag entfernen" im Dialog;
                      hängt ein Rechnungsentwurf an ihm, kein Entfernen, der Grund im Dialog. Hell, dunkel, 412 px
    Rechnungsseite    Schlussrechnung: kein "+ Position hinzufügen", stattdessen der Hinweis auf den Nachtrag, der Nachtrag als
                      Position N1; Rechnung aus Aufwand: Knopf da; Abschlag mit negativem Betrag: Grund statt "Finalisieren"

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_nachtrag.py [--app-port N] [--cdp-port N]
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
        create_abschlag_leistungsstand, create_invoice_from_time_entries, finalize_and_send_invoice, update_invoice_header,
        update_invoice_item,
    )
    from app.models import AppUser, Customer, OrderSection, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id

    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Klar", last_name="Klar", street="Dachweg 1", postal_code="52531", city="Uebach")
    db.add_all([buero, kunde]); db.flush()

    def auftrag(nummer, titel=False):
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
        if titel:
            section = OrderSection(order_id=order.id, title="Steildach", sort_order=5)
            db.add(section); db.flush()
            for item in order.items:
                item.section_id = section.id
            db.commit()
        return load_order(db, order.id)

    mit_titel = auftrag("KT-1", titel=True)
    aufwand = create_invoice_from_time_entries(
        db, mit_titel, [], [SimpleNamespace(material_id=None, description="Kehlblech", unit="Stk.", quantity=Decimal("2"))])
    mit_abschlag = auftrag("KT-2")
    erster = create_abschlag_leistungsstand(db, mit_abschlag)
    update_invoice_item(db, erster, erster.items[0], ist_quantity=Decimal("4"))
    update_invoice_header(db, erster, service_period_start=date(2026, 10, 1), service_period_end=date(2026, 10, 5))
    finalize_and_send_invoice(db, erster)
    zurueck = create_abschlag_leistungsstand(db, load_order(db, mit_abschlag.id))
    update_invoice_item(db, zurueck, zurueck.items[0], ist_quantity=Decimal("3"))
    return {"auftrag": mit_titel.id, "aufwand": aufwand.id, "zurueck": zurueck.id, "cookies": {"buero": k.cookies(buero)}}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1280, 1000)
    await tab.anmelden(seed["cookies"]["buero"])
    a = seed["auftrag"]

    # --- Auftragsseite: Nachtrag anlegen ---
    await tab.oeffnen(f"/orders/{a}", "order&&document.querySelectorAll('.lv-row').length===1")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    p.pruefe("Knopf + Nachtrag", await tab.js("document.querySelector('#addendumBar button')?.textContent"), "+ Nachtrag")
    vorher = await tab.js("Number(order.net_total)")
    await tab.js("document.querySelector('#addendumBar button').click()")
    p.pruefe("Dialog: Titel, ohne Typ und OZ",
             await tab.js("[document.getElementById('itemDialogTitle').textContent,document.getElementById('iTypeField').hidden,"
                          "document.getElementById('iOzField').hidden,document.getElementById('iRemove').hidden]"),
             ["Nachtrag anlegen", True, True, True])
    await tab.js("document.getElementById('iShort').value='Kaminverblechung';document.getElementById('iQty').value='10';"
                 "document.getElementById('iPrice').value='100';document.getElementById('iUnit').selectedIndex=1")
    await tab.bild("nachtrag_dialog")
    await tab.js("saveItemDialog()")
    p.pruefe("Nachtrag gespeichert", await tab.warten("order.items.some(i=>i.is_addendum)"), True)
    p.pruefe("Nachtrag: Nummer N1 und Summe",
             await tab.js("[order.items.find(i=>i.is_addendum).position_number,Number(order.net_total)]"), ["N1", vorher + 1000])
    p.pruefe("Nachtrag: Kennzeichen unter „Nachträge“ hinter dem Titel",
             await tab.js("(()=>{const t=[...document.querySelectorAll('#lv .section-head span')].map(s=>s.textContent.trim());"
                          "const z=document.querySelector('#lv .addendum-badge');return [t,!!z,"
                          "z?.closest('.section')?.querySelector('.section-head span').textContent]})()"),
             [["Steildach", "Nachträge"], True, "Nachträge"])
    await tab.bild("nachtrag_hell")
    nid = await tab.js("order.items.find(i=>i.is_addendum).id")
    await tab.js(f"openItem({nid})")
    p.pruefe("Dialog: Nachtrag entfernen sichtbar",
             await tab.js("[document.getElementById('itemDialogTitle').textContent,document.getElementById('iRemove').hidden]"),
             ["Nachtrag N1 bearbeiten", False])
    await tab.js("removeAddendum()")
    p.pruefe("Nachtrag entfernt", await tab.warten("!order.items.some(i=>i.is_addendum)"), True)

    # --- wieder anlegen, Schlussrechnung als Entwurf: kein Entfernen mehr ---
    await tab.js(f"fetch('/api/orders/{a}/items',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
                 "body:JSON.stringify({short_text:'Kaminverblechung',long_text:'',quantity:10,unit:'m',unit_price:100})})")
    schluss = await tab.js(f"fetch('/api/orders/{a}/invoices/schlussrechnung',{{method:'POST',headers:{{'Content-Type':"
                           "'application/json'},body:'{}'}).then(r=>r.json()).then(j=>j.id)")
    await tab.oeffnen(f"/orders/{a}", "order&&order.items.some(i=>i.is_addendum)")
    nid = await tab.js("order.items.find(i=>i.is_addendum).id")
    await tab.js(f"openItem({nid})")
    p.pruefe("Dialog: mit Rechnungsentwurf kein Entfernen, Grund",
             await tab.js("[document.getElementById('iRemove').hidden,document.getElementById('addendumLock').textContent]"),
             [True, "Der Nachtrag N1 lässt sich nicht entfernen: an ihm hängen Rechnungen (1 Entwurf)."])
    await tab.js("document.getElementById('itemDialog').close()")
    await tab.js("document.documentElement.setAttribute('data-theme','dark')")
    await tab.bild("nachtrag_dunkel")
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/orders/{a}", "order&&order.items.some(i=>i.is_addendum)")
    await tab.js("document.documentElement.setAttribute('data-theme','dark');document.getElementById('lv').scrollIntoView();"
                 "window.scrollBy(0,-140)")
    await tab.bild("nachtrag_412_dunkel")
    await tab.fenster(1280, 1000)

    # --- Rechnungsseite ---
    await tab.oeffnen(f"/invoices/{schluss}", "invoice&&invoice.id")
    p.pruefe("Schlussrechnung: kein + Position, Hinweis",
             await tab.js("[document.getElementById('addItemBtn').hidden,document.getElementById('addItemHint').hidden]"),
             [True, False])
    p.pruefe("Schlussrechnung: Nachtrag als Position N1",
             await tab.js("[...document.querySelectorAll('#itemsList .inv-row span:first-child')].map(s=>s.textContent)"),
             ["1", "N1"])
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.bild("schluss_hinweis")
    await tab.oeffnen(f"/invoices/{seed['aufwand']}", "invoice&&invoice.id")
    p.pruefe("Aufwand: + Position da",
             await tab.js("[document.getElementById('addItemBtn').hidden,document.getElementById('addItemHint').hidden]"),
             [False, True])
    await tab.oeffnen(f"/invoices/{seed['zurueck']}", "invoice&&invoice.id&&document.getElementById('statusActions').innerHTML")
    p.pruefe("Negativer Abschlag: Grund statt Finalisieren",
             await tab.js("[(document.querySelector('#statusActions [data-sperre]')?.textContent||'').startsWith("
                          "'Der Abschlag lautet über -59,50 €'),[...document.querySelectorAll('#statusActions button')]"
                          ".some(b=>b.textContent==='Rechnung finalisieren')]"), [True, False])
    await tab.bild("abschlag_negativ")
    p.pruefe("JS-Fehler", tab.fehler, [])
    print(json.dumps({"auftrag": a, "schluss": schluss}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
