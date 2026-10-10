"""Klicktest: gesperrte Rechnungsaktionen zeigen den Grund statt des Knopfs (1.8.72).

Befund „Vor dem Echtbetrieb“ Punkt 1 (docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.72"):

    Auftragsseite      "Neue Rechnung": Schlussrechnung neben einem pauschalen Abschlag gesperrt (Grund, kein Knopf, API 409);
                       nach festgeschriebener Schlussrechnung Abschläge und eine zweite Schlussrechnung gesperrt; ein freier
                       Auftrag zeigt den Knopf; Schlussrechnung als Entwurf -> gesperrt, Entwurf in der Liste löschen -> frei
    Rechnungsseite     Abschlagsentwurf von vor der Schlussrechnung: Grund statt "Rechnung finalisieren", "Entwurf löschen"
                       bleibt; verrechneter Abschlag: Grund statt "Stornieren"; Stornorechnung: "lässt sich nicht stornieren"
                       (hell und dunkel)
    Mahnwesen          Mahnungsentwurf zu einer inzwischen bezahlten Rechnung: Grund statt "Versenden", API 409

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_rechnungen_sperren.py [--app-port N] [--cdp-port N]
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
    from app.invoices import (
        create_abschlag_leistungsstand, create_abschlag_pauschal, create_schlussrechnung, create_storno_draft,
        finalize_and_send_invoice, mark_invoice_paid, update_invoice_item,
    )
    from app.models import AppUser, Customer, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.reminders import create_reminder

    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Klar", last_name="Klar", street="Dachweg 1", postal_code="52531", city="Uebach",
                     email="klar@example.com")
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

    def leistungsstand(order, ist):
        invoice = create_abschlag_leistungsstand(db, order)
        update_invoice_item(db, invoice, invoice.items[0], ist_quantity=Decimal(ist))
        return invoice

    # A: pauschaler Abschlag festgeschrieben -> Schlussrechnung gesperrt
    a = auftrag("KT-1")
    pauschal = finalize_and_send_invoice(db, create_abschlag_pauschal(db, a, lump_sum_net=Decimal("200")))
    # B: Abschlag 40 %, Schlussrechnung festgeschrieben, dazwischen ein Abschlagsentwurf
    b = auftrag("KT-2")
    abschlag = finalize_and_send_invoice(db, leistungsstand(b, "4"))
    schluss = create_schlussrechnung(db, load_order(db, b.id))
    spaeter = leistungsstand(load_order(db, b.id), "8")
    schluss = finalize_and_send_invoice(db, schluss)
    # C: Rechnung und ihr Storno
    c = auftrag("KT-3")
    storno = finalize_and_send_invoice(db, create_storno_draft(db, finalize_and_send_invoice(db, leistungsstand(c, "2"))))
    # D: frei; E: Schlussrechnung als Entwurf
    d = auftrag("KT-4")
    e = auftrag("KT-5")
    e_entwurf = create_schlussrechnung(db, e)
    # F: überfällige Rechnung mit Mahnungsentwurf, danach bezahlt
    f = auftrag("KT-6")
    rechnung = finalize_and_send_invoice(db, create_schlussrechnung(db, f, due_date=berlin_today() - timedelta(days=20)))
    mahnung = create_reminder(db, rechnung, 1)
    mark_invoice_paid(db, rechnung, paid_date=berlin_today() - timedelta(days=1))
    return {"a": a.id, "pauschal": pauschal.invoice_number, "b": b.id, "abschlag": abschlag.id, "schluss": schluss.invoice_number,
            "spaeter": spaeter.id, "storno": storno.id, "d": d.id, "e": e.id, "e_entwurf": e_entwurf.id, "mahnung": mahnung.id,
            "rechnung": rechnung.invoice_number, "cookies": {"buero": k.cookies(buero)}}


ORDER_READY = "order&&order.invoice_create_blocks&&document.getElementById('newInvoiceType')"


async def _art(tab, art):
    """Rechnungsart wählen wie im Auswahlfeld; liefert [Hinweis sichtbar, Hinweistext, Knopf sichtbar]."""
    return await tab.js(f"(()=>{{const s=document.getElementById('newInvoiceType');s.value='{art}';"
                        "s.dispatchEvent(new Event('change'));const b=document.getElementById('newInvoiceBlock');"
                        "return [!b.hidden,b.textContent,!document.getElementById('newInvoiceButton').hidden]})()")


async def _aktionen(tab):
    return await tab.js("(()=>{const el=document.getElementById('statusActions');return {knoepfe:[...el.querySelectorAll("
                        "'button')].map(b=>b.textContent.trim()),sperre:el.querySelector('[data-sperre]')?.textContent||null}})()")


async def _bild(tab, name, element, dunkel=False):
    """Bild mit dem Element in der Mitte, hell und auf Wunsch zusätzlich dunkel."""
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
    await tab.anmelden(seed["cookies"]["buero"])

    # --- Auftrag A: Schlussrechnung neben pauschalem Abschlag ---
    await tab.oeffnen(f"/orders/{seed['a']}", ORDER_READY)
    sichtbar, text, knopf = await _art(tab, "schluss")
    p.pruefe("A Schluss: Grund sichtbar, Knopf weg", [sichtbar, knopf], [True, False])
    p.pruefe("A Schluss: Grund nennt den Abschlag",
             text.startswith(f"Die Schlussrechnung ist vorerst gesperrt: am Auftrag besteht ein pauschaler Abschlag "
                             f"({seed['pauschal']})"), True)
    p.pruefe("A Abschlag nach Leistungsstand: frei", await _art(tab, "abschlag_leistungsstand"), [False, "", True])
    api = await tab.js(f"fetch('/api/orders/{seed['a']}/invoices/schlussrechnung',{{method:'POST',headers:{{'Content-Type':"
                       "'application/json'},body:'{}'}).then(async r=>[r.status,(await r.json()).detail.slice(0,42)])")
    p.pruefe("A Schluss: API 409", api, [409, "Die Schlussrechnung ist vorerst gesperrt: "])
    await _art(tab, "schluss")
    await _bild(tab, "auftrag_a_schluss_gesperrt", "newInvoiceBlock")

    # --- Auftrag B: nach der Schlussrechnung ---
    await tab.oeffnen(f"/orders/{seed['b']}", ORDER_READY)
    for art in ("abschlag_pauschal", "abschlag_leistungsstand"):
        sichtbar, text, knopf = await _art(tab, art)
        p.pruefe(f"B {art}: gesperrt", [sichtbar, knopf, text],
                 [True, False, f"Nach der Schlussrechnung {seed['schluss']} sind keine weiteren Abschlagsrechnungen möglich."])
    sichtbar, text, knopf = await _art(tab, "schluss")
    p.pruefe("B zweite Schluss: gesperrt mit Nummer", [sichtbar, knopf, f"({seed['schluss']})" in text], [True, False, True])
    await _bild(tab, "auftrag_b_gesperrt", "newInvoiceBlock", dunkel=True)

    # --- Rechnungsseite: Abschlagsentwurf von vor der Schlussrechnung ---
    await tab.oeffnen(f"/invoices/{seed['spaeter']}", "invoice&&document.getElementById('statusActions').innerHTML.length>0")
    akt = await _aktionen(tab)
    p.pruefe("Entwurf: kein Finalisieren, Löschen bleibt", akt["knoepfe"], ["Entwurf löschen"])
    p.pruefe("Entwurf: Grund", akt["sperre"],
             f"Nach der Schlussrechnung {seed['schluss']} sind keine weiteren Abschlagsrechnungen möglich.")
    await _bild(tab, "rechnung_entwurf_gesperrt", "statusActions")

    # --- Rechnungsseite: verrechneter Abschlag ---
    await tab.oeffnen(f"/invoices/{seed['abschlag']}", "invoice&&document.getElementById('statusActions').innerHTML.length>0")
    akt = await _aktionen(tab)
    p.pruefe("Abschlag: kein Stornieren", "Stornieren" in akt["knoepfe"], False)
    p.pruefe("Abschlag: Bezahlt-Knopf bleibt", "Als bezahlt markieren" in akt["knoepfe"], True)
    p.pruefe("Abschlag: Grund", (akt["sperre"] or "").startswith(f"Der Abschlag ist in der Schlussrechnung {seed['schluss']}"),
             True)
    await _bild(tab, "rechnung_abschlag_storno_gesperrt", "statusActions", dunkel=True)

    # --- Rechnungsseite: Stornorechnung ---
    await tab.oeffnen(f"/invoices/{seed['storno']}", "invoice&&document.getElementById('statusActions').innerHTML.length>0")
    akt = await _aktionen(tab)
    p.pruefe("Storno: kein Stornieren, Grund", ["Stornieren" in akt["knoepfe"], akt["sperre"]],
             [False, "Eine Stornorechnung lässt sich nicht stornieren."])

    # --- Auftrag D: frei ---
    await tab.oeffnen(f"/orders/{seed['d']}", ORDER_READY)
    p.pruefe("D Schluss: frei", await _art(tab, "schluss"), [False, "", True])

    # --- Auftrag E: Schlussrechnung als Entwurf, löschen gibt frei ---
    await tab.oeffnen(f"/orders/{seed['e']}", ORDER_READY)
    sichtbar, text, knopf = await _art(tab, "schluss")
    p.pruefe("E Schluss neben Entwurf: gesperrt", [sichtbar, knopf, "(ein Entwurf)" in text], [True, False, True])
    await tab.js(f"deleteDraftFromList(new Event('click'),{seed['e_entwurf']})")
    p.pruefe("E nach dem Löschen: frei",
             await tab.warten("invoices.length===0&&!document.getElementById('newInvoiceButton').hidden"), True)
    p.pruefe("E nach dem Löschen: Hinweis weg", await tab.js("document.getElementById('newInvoiceBlock').hidden"), True)

    # --- Mahnwesen: Entwurf zu bezahlter Rechnung ---
    await tab.oeffnen("/mahnwesen", "allReminders.length>0&&document.getElementById('allRows').innerHTML.length>0")
    zeile = await tab.js("(()=>{const tr=[...document.querySelectorAll('#allRows tr')].find(t=>t.textContent.includes("
                         f"'{seed['rechnung']}'));return {{versenden:[...tr.querySelectorAll('button')].some(b=>b.textContent"
                         ".trim()==='Versenden'),sperre:tr.querySelector('[data-sperre]')?.textContent||null}})()")
    p.pruefe("Mahnung: kein Versenden", zeile["versenden"], False)
    p.pruefe("Mahnung: Grund", (zeile["sperre"] or "").startswith(f"Die Rechnung {seed['rechnung']} ist bezahlt (am "), True)
    api = await tab.js(f"fetch('/api/reminders/{seed['mahnung']}/send',{{method:'POST'}}).then(r=>r.status)")
    p.pruefe("Mahnung: API 409", api, 409)
    await _bild(tab, "mahnwesen_bezahlt", "allRows", dunkel=True)
    p.pruefe("JS-Fehler", tab.fehler, [])
    print(json.dumps({k: v for k, v in seed.items() if k != "cookies"}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
