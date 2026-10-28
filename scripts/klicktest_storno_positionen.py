"""Klicktest: Positionen im Storno-Entwurf und in der Schlussrechnung (1.9.114, Stufe 5, R1, Punkt 4, Befund F8/F9).

    Storno-Entwurf      kein Ist-Feld, kein „✎“, kein „✕“; Finalisieren und „Entwurf löschen“ bleiben; der Angriff aus der Seite (PUT Ist)
                        bekommt 409 mit dem Grund, die Summe bleibt der Gegenbetrag (Bild)
    Schlussrechnung     Ist-Feld und „✎“ je Position, kein „✕“ (Mengenvergleich); DELETE aus der Seite 409
    Abschlag            Ist-Feld, „✎“ und „✕“ wie bisher

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_storno_positionen.py [--app-port N] [--cdp-port N]
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

    from app.invoices import (create_abschlag_leistungsstand, create_schlussrechnung, create_storno_draft, finalize_and_send_invoice,
                              update_invoice_header, update_invoice_item)
    from app.models import AppUser, Customer, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id

    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Storno", last_name="Storno", city="Uebach")
    db.add_all([fin, kunde]); db.flush()

    def auftrag(nummer):
        projekt = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=kunde.id, status="angebot",
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-{nummer}", project_id=projekt.id, title="Sanierung", vat_rate=Decimal("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("100"), unit="m2",
                         unit_price=Decimal("50")))
        db.commit()
        return create_order_from_quote(db, quote.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
                                       caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)

    a = auftrag("S-1")
    abschlag = create_abschlag_leistungsstand(db, load_order(db, a.id))
    update_invoice_item(db, abschlag, abschlag.items[0], ist_quantity=Decimal("40"))
    update_invoice_header(db, abschlag, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 30))
    abschlag = finalize_and_send_invoice(db, abschlag)
    storno = create_storno_draft(db, abschlag)
    b = auftrag("S-2")
    schluss = create_schlussrechnung(db, load_order(db, b.id))
    c = auftrag("S-3")
    offen = create_abschlag_leistungsstand(db, load_order(db, c.id))
    return {"storno": storno.id, "storno_pos": storno.items[0].id, "schluss": schluss.id, "schluss_pos": schluss.items[0].id,
            "abschlag": offen.id, "cookies": {"fin": k.cookies(fin)}}


BEREIT = "invoice&&document.getElementById('statusInfo').textContent.length>0&&document.getElementById('itemsList').innerHTML.length>0"
ZEILE = ("(()=>{const z=document.querySelector('#itemsList .inv-row');return {ist:!!z.querySelector('input[data-zahl]'),"
         "bearbeiten:[...z.querySelectorAll('button')].some(b=>b.textContent==='✎'),entfernen:[...z.querySelectorAll('button')].some(b=>b.textContent==='✕')}})()")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1440, 900)
    await tab.anmelden(seed["cookies"]["fin"])
    await tab.oeffnen(f"/invoices/{seed['storno']}", BEREIT)
    p.pruefe("Storno-Entwurf: kein Ist-Feld, kein ✎, kein ✕", await tab.js(ZEILE), {"ist": False, "bearbeiten": False, "entfernen": False})
    p.pruefe("Storno-Entwurf: Finalisieren und Entwurf löschen bleiben", await tab.js(
        "[...document.querySelectorAll('#statusActions button')].map(b=>b.textContent).filter(t=>['Rechnung finalisieren','Entwurf löschen'].includes(t))"),
        ["Rechnung finalisieren", "Entwurf löschen"])
    antwort = await tab.js(f"fetch('/api/invoices/{seed['storno']}/items/{seed['storno_pos']}',{{method:'PUT',headers:{{'Content-Type':"
                           "'application/json'},body:JSON.stringify({ist_quantity:'7'})}).then(async r=>[r.status,(await r.json()).detail.slice(0,40)])")
    p.pruefe("Angriff aus der Seite: Ist am Storno 409", antwort, [409, "Ein Storno spiegelt die stornierte Rechn"])
    p.pruefe("Storno bleibt der Gegenbetrag", await tab.js(f"fetch('/api/invoices/{seed['storno']}').then(r=>r.json()).then(d=>d.net_total)"),
             "-2000.00")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.bild("storno_entwurf_ohne_positionsknoepfe")

    await tab.oeffnen(f"/invoices/{seed['schluss']}", BEREIT)
    p.pruefe("Schlussrechnung: Ist-Feld und ✎, kein ✕", await tab.js(ZEILE), {"ist": True, "bearbeiten": True, "entfernen": False})
    antwort = await tab.js(f"fetch('/api/invoices/{seed['schluss']}/items/{seed['schluss_pos']}',{{method:'DELETE'}})"
                           ".then(async r=>[r.status,(await r.json()).detail.slice(0,38)])")
    p.pruefe("Angriff aus der Seite: Position der Schlussrechnung entfernen 409", antwort, [409, "In der Schlussrechnung stehen alle Pos"])

    await tab.oeffnen(f"/invoices/{seed['abschlag']}", BEREIT)
    p.pruefe("Abschlag: Ist-Feld, ✎ und ✕ wie bisher", await tab.js(ZEILE), {"ist": True, "bearbeiten": True, "entfernen": True})
    p.pruefe("JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
