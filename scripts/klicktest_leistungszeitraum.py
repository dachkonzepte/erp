"""Klicktest: Leistungszeitraum an der Rechnung und nächste Nummer in den Einstellungen (1.8.74).

docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.74":

    Rechnungsseite     Schlussrechnung im Entwurf: Felder leer, Vorschlag mit Quelle (erste bis letzte Zeitbuchung), statt
                       "Rechnung finalisieren" der Grund "Leistungszeitraum fehlt"; nichts still eingetragen; "Übernehmen" ->
                       Felder gefüllt und gespeichert, Finalisieren erscheint; Ende vor Beginn -> Fehler, Werte bleiben;
                       Finalisieren -> festgeschrieben mit Zeitraum (hell und dunkel)
    ohne Zeitbuchungen Vorschlag "Geplanter Zeitraum des Auftrags"
    Einstellungen      Nummernkreis Rechnung: nächste Nummer 1 trotz vergebener -> Meldung mit der höchsten, nichts gespeichert

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_leistungszeitraum.py [--app-port N] [--cdp-port N]
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
    from datetime import date
    from decimal import Decimal

    from app.invoices import create_schlussrechnung, finalize_and_send_invoice, update_invoice_header
    from app.models import AppUser, Customer, Employee, Project, Quote, QuoteItem, TimeEntry
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id

    admin = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Klar", last_name="Klar", street="Dachweg 1", postal_code="52531", city="Uebach")
    mona = Employee(first_name="Mona", last_name="Monteurin", active=True)
    db.add_all([admin, kunde, mona]); db.flush()

    def auftrag(nummer, start=None, ende=None):
        projekt = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=kunde.id, status="angebot",
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-{nummer}", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2",
                         unit_price=Decimal("50")))
        db.commit()
        order = create_order_from_quote(db, quote.id, order_date=date(2026, 9, 1), execution_start=start, execution_end=ende,
                                        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None,
                                        remarks=None)
        return load_order(db, order.id)

    # A: Zeitbuchungen 01.09. bis 18.09., Schlussrechnung im Entwurf
    a = auftrag("KT-1")
    for tag in (date(2026, 9, 1), date(2026, 9, 9), date(2026, 9, 18)):
        db.add(TimeEntry(employee_id=mona.id, project_id=a.project_id, order_id=a.id, work_date=tag, entry_type="site",
                         status="booked", hours=Decimal("8")))
    db.commit()
    schluss = create_schlussrechnung(db, a)
    # B: ohne Zeitbuchungen, geplanter Zeitraum am Auftrag
    b = auftrag("KT-2", date(2026, 10, 5), date(2026, 10, 16))
    b_schluss = create_schlussrechnung(db, b)
    # C: eine festgeschriebene Rechnung -- für die Nummernkreis-Sperre
    c = auftrag("KT-3")
    c_rechnung = create_schlussrechnung(db, c)
    update_invoice_header(db, c_rechnung, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 30))
    c_rechnung = finalize_and_send_invoice(db, c_rechnung)
    return {"schluss": schluss.id, "b_schluss": b_schluss.id, "vergeben": c_rechnung.invoice_number,
            "cookies": {"admin": k.cookies(admin)}}


INVOICE_READY = "invoice&&document.getElementById('statusActions').innerHTML.length>0"


async def _stand(tab):
    return await tab.js("(()=>{const box=document.getElementById('periodProposal');return {start:document.getElementById("
                        "'iPeriodStart').value,end:document.getElementById('iPeriodEnd').value,vorschlag:box.textContent,"
                        "uebernehmen:!!box.querySelector('button'),knoepfe:[...document.querySelectorAll('#statusActions button')]"
                        ".map(b=>b.textContent.trim()),sperre:document.querySelector('#statusActions [data-sperre]')?.textContent"
                        "||null}})()")


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
    sid = seed["schluss"]

    # --- Entwurf: Vorschlag, Grund statt Finalisieren, nichts eingetragen ---
    await tab.oeffnen(f"/invoices/{sid}", INVOICE_READY)
    s = await _stand(tab)
    p.pruefe("Entwurf: Felder leer", [s["start"], s["end"]], ["", ""])
    p.pruefe("Entwurf: Vorschlag mit Quelle",
             "Vorschlag: 01.09.2026 bis 18.09.2026" in s["vorschlag"]
             and "Quelle: Erste bis letzte Zeitbuchung des Auftrags (keine Abnahme), 3 Zeitbuchungen." in s["vorschlag"], True)
    p.pruefe("Entwurf: Übernehmen-Knopf", s["uebernehmen"], True)
    p.pruefe("Entwurf: kein Finalisieren, Grund",
             [("Rechnung finalisieren" in s["knoepfe"]), (s["sperre"] or "").startswith("Der Leistungszeitraum fehlt (Beginn und Ende)")],
             [False, True])
    gespeichert = await tab.js(f"fetch('/api/invoices/{sid}').then(r=>r.json()).then(j=>[j.service_period_start,j.service_period_end])")
    p.pruefe("Entwurf: nichts still eingetragen", gespeichert, [None, None])
    await _bild(tab, "rechnung_vorschlag", "periodProposal", dunkel=True)

    # --- Übernehmen per Klick ---
    await tab.js("document.querySelector('#periodProposal button').click()")
    p.pruefe("Übernommen: Felder gefüllt",
             await tab.warten("document.getElementById('iPeriodStart').value==='2026-09-01'"
                              "&&document.getElementById('iPeriodEnd').value==='2026-09-18'"), True)
    s = await _stand(tab)
    p.pruefe("Übernommen: gespeichert und Finalisieren da",
             [await tab.js(f"fetch('/api/invoices/{sid}').then(r=>r.json()).then(j=>[j.service_period_start,j.service_period_end])"),
              "Rechnung finalisieren" in s["knoepfe"], s["uebernehmen"]],
             [["2026-09-01", "2026-09-18"], True, False])

    # --- Ende vor Beginn ---
    await tab.js("const e=document.getElementById('iPeriodEnd');e.value='2026-08-20';e.dispatchEvent(new Event('change'))")
    p.pruefe("Ende vor Beginn: Fehler",
             await tab.warten("document.getElementById('headerStatus').textContent.includes('liegt vor dem Beginn')"), True)
    p.pruefe("Ende vor Beginn: Wert bleibt", await tab.js("document.getElementById('iPeriodEnd').value"), "2026-09-18")
    await _bild(tab, "rechnung_ende_vor_beginn", "headerStatus")

    # --- Finalisieren ---
    await tab.js("sendInvoice()")
    p.pruefe("Finalisiert", await tab.warten("invoice.status==='versendet'"), True)
    s = await _stand(tab)
    p.pruefe("Finalisiert: Felder gesperrt, kein Vorschlag",
             [await tab.js("document.getElementById('iPeriodStart').disabled"), s["vorschlag"]], [True, ""])
    p.pruefe("Finalisiert: Text", await tab.js("invoice.service_period_text"), "Leistungszeitraum: 01.09.2026 bis 18.09.2026")
    hoechste = await tab.js("invoice.invoice_number")  # jetzt die höchste vergebene Rechnungsnummer
    await _bild(tab, "rechnung_finalisiert", "periodProposal")

    # --- ohne Zeitbuchungen: geplanter Zeitraum ---
    await tab.oeffnen(f"/invoices/{seed['b_schluss']}", INVOICE_READY)
    s = await _stand(tab)
    p.pruefe("Ohne Zeitbuchungen: geplanter Zeitraum",
             "Vorschlag: 05.10.2026 bis 16.10.2026" in s["vorschlag"] and "Geplanter Zeitraum des Auftrags." in s["vorschlag"],
             True)

    # --- Einstellungen: nächste Rechnungsnummer 1 ---
    await tab.oeffnen("/settings", "typeof sequences!=='undefined'&&sequences.length>0&&document.querySelector('.sequence')")
    vorher = await tab.js("sequences.find(s=>s.sequence_key==='invoice').next_value")
    await tab.js("(()=>{const r=document.querySelector('.sequence[data-key=\"invoice\"]');r.querySelector('.next').value='1';"
                 "saveSequence('invoice')})()")
    p.pruefe("Nummernkreis: Meldung mit der höchsten vergebenen",
             await tab.warten("document.querySelector('.sequence[data-key=\"invoice\"] .seqStatus').textContent"
                              f".includes('höchste vergebene Nummer in diesem Format ist {hoechste}')"), True)
    nachher = await tab.js("fetch('/api/settings/number-sequences').then(r=>r.json()).then(l=>l.find(s=>s.sequence_key==='invoice')"
                           ".next_value)")
    p.pruefe("Nummernkreis: nichts gespeichert", nachher, vorher)
    await tab.js("showSettingsSection('numbers');document.querySelector('.sequence[data-key=\"invoice\"]')"
                 ".scrollIntoView({block:'center'})")
    await tab.bild("nummernkreis_abgelehnt")
    p.pruefe("JS-Fehler", tab.fehler, [])
    print(json.dumps({k: v for k, v in seed.items() if k != "cookies"}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
