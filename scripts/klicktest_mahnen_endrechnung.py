"""Klicktest: Mahnen nach der Endrechnung (1.8.89, R4c Punkte 3-5, docs/archiv/befund-vor-echtbetrieb.md "Umsetzung R4c").

Ein Auftrag (10 m² × 50 € = 595 € brutto) mit einem pauschalen Abschlag (119 €, nicht bezahlt) und einem Abschlag nach
Leistungsstand (4 m², 238 €: 100 € gezahlt, 38 € Einbehalt -- offen 138 €, davon Einbehalt 38 €); zum pauschalen Abschlag ein
Mahnungsentwurf. Danach die Schlussrechnung (Endrechnung, Rechnungsbetrag 238 €), festgeschrieben und überfällig.

    Mahnwesen          die beiden Abschläge nicht mehr in "zur Mahnung fällig"; die Schlussrechnung mit 495 € (238 + 119 + 138)
                       und "Zahlbetrag samt …"; der Entwurf zum Abschlag in "Alle Mahnungen" mit "überholt" statt "Versenden"
    Abschlag           Hinweis "abgezogen" samt fälligem Einbehalt, nicht überfällig, Grund statt "anlegen"
    Schlussrechnung    "Gemahnt wird der Zahlbetrag …", 1. Mahnung anlegen -> Aufstellung mit "zzgl. noch offen aus Abschlag
                       Nr. …" je Rechnung und "angemahnt 495,00 €"; festschreiben, PDF; Abschlag zum Einbehalt bezahlt -> der
                       Entwurf bzw. die Mahnung nennt den neuen Betrag
    API                Mahnung zum Abschlag 409; Monteurin 403
    412 px dunkel      Mahnwesen, Rechnungsseite

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_mahnen_endrechnung.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date, timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.invoices import (
        create_abschlag_leistungsstand, create_abschlag_pauschal, create_schlussrechnung, finalize_and_send_invoice,
        update_invoice_header, update_invoice_item,
    )
    from app.models import AppUser, Customer, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.payments import Line, book_payment
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.reminders import create_reminder

    heute = berlin_today()
    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    monteurin = AppUser(username="monteurin", display_name="Mia Monteurin", role="field", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Ende", last_name="Ende", street="Dachweg 1", postal_code="52531", city="Uebach",
                     email="ende@example.com", is_consumer=False)
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

    def fest(invoice, faellig_vor_tagen):
        update_invoice_header(db, invoice, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 30))
        invoice = finalize_and_send_invoice(db, invoice)
        invoice.due_date = heute - timedelta(days=faellig_vor_tagen)
        db.commit()
        return invoice

    pauschal = fest(create_abschlag_pauschal(db, load_order(db, order.id), lump_sum_net=Decimal("100")), 30)
    abschlag = create_abschlag_leistungsstand(db, load_order(db, order.id))
    update_invoice_item(db, abschlag, abschlag.items[0], ist_quantity=Decimal("4"))
    abschlag = fest(abschlag, 20)
    book_payment(db, customer_id=kunde.id, received_on=heute, amount=Decimal("100"), note=None,
                 lines=[Line(abschlag.id, zahlung=Decimal("100"), einbehalt=Decimal("38"))], user_name="Bea Büro")
    entwurf = create_reminder(db, pauschal)  # Entwurf zum pauschalen Abschlag -- nach der Schlussrechnung überholt
    schluss = fest(create_schlussrechnung(db, load_order(db, order.id)), 10)
    return {"pauschal": pauschal.id, "pauschal_nr": pauschal.invoice_number, "abschlag": abschlag.id,
            "abschlag_nr": abschlag.invoice_number, "schluss": schluss.id, "schluss_nr": schluss.invoice_number,
            "entwurf": entwurf.id, "kunde": kunde.id,
            "cookies": {"buero": k.cookies(buero), "monteurin": k.cookies(monteurin)}}


def _passt(p, name, ist, bedingung):
    """Prüfung über eine Bedingung -- bei Abweichung steht der gelesene Wert in der Ausgabe."""
    p.pruefe(name, "passt" if bedingung(ist) else ist, "passt")


MAHNWESEN_READY = "document.getElementById('metrics').innerHTML.length>0&&document.getElementById('allRows').innerHTML.length>0"
INVOICE_READY = "invoice&&document.getElementById('reminderStatusInfo').textContent.length>0"


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)

    # --- Mahnwesen ---
    await tab.oeffnen("/mahnwesen", MAHNWESEN_READY)
    p.pruefe("Abschläge nicht mehr zur Mahnung fällig oder überfällig", await tab.js(
        f"attentionRows.filter(r=>[{seed['pauschal']},{seed['abschlag']}].includes(r.invoice_id)).length"), 0)
    p.pruefe("Schlussrechnung zur Mahnung fällig über den Zahlbetrag", await tab.js(
        f"(()=>{{const r=attentionRows.find(r=>r.invoice_id==={seed['schluss']});return r?[r.due_for_reminder,Number(r.outstanding_amount)]:null}})()"),
        [True, 495])
    p.pruefe("Zeile nennt „Zahlbetrag samt …“", await tab.js(
        f"document.querySelector('tr[data-faellig=\"{seed['schluss']}\"] [data-zahlbetrag-mit]')?.textContent"),
        f"Zahlbetrag samt {seed['pauschal_nr']}, {seed['abschlag_nr']}")
    _passt(p, "Entwurf zum Abschlag: überholt statt Versenden", await tab.js(
        f"(()=>{{const r=allReminders.find(r=>r.id==={seed['entwurf']});return r?r.send_block:null}})()||''"),
        lambda v: v.startswith("Der Entwurf (1. Mahnung) ist überholt: ") and seed["schluss_nr"] in v)
    await tab.js("document.getElementById('dueCard').scrollIntoView({block:'center'})")
    await tab.bild("mahnwesen_hell")

    # --- Abschlag: Hinweis, nicht überfällig, Grund statt anlegen ---
    await tab.oeffnen(f"/invoices/{seed['abschlag']}", INVOICE_READY)
    _passt(p, "Abschlag: Hinweis abgezogen, Einbehalt fällig", await tab.js(
        "document.querySelector('[data-abgezogen]')?.textContent||''"),
        lambda v: v.startswith(f"In der Schlussrechnung {seed['schluss_nr']} vom ") and "Der Einbehalt (38,00 €) ist mit der Schlussrechnung fällig." in v)
    # Seit 1.8.91 (Nacharbeit R4c Punkt 1) heißt das Kennzeichen "Enthalten in Schlussrechnung …" statt "… · in … abgezogen".
    p.pruefe("Abschlag: nicht überfällig, Kennzeichen „Enthalten in Schlussrechnung …“", await tab.js(
        "[invoice.is_overdue,document.getElementById('seitenkopfStatus').textContent]"),
        [False, f"Enthalten in Schlussrechnung {seed['schluss_nr']}"])
    _passt(p, "Abschlag: Grund statt „Mahnung anlegen“", await tab.js(
        "document.querySelector('#reminderActions [data-grund]')?.textContent||''"),
        lambda v: "abgezogen" in v and "gemahnt wird nur noch die Schlussrechnung" in v)
    await tab.js("document.getElementById('paymentsCard').scrollIntoView({block:'center'})")
    await tab.bild("abschlag_abgezogen")

    # --- Schlussrechnung: Mahnung über den Zahlbetrag ---
    await tab.oeffnen(f"/invoices/{seed['schluss']}", INVOICE_READY)
    _passt(p, "Schlussrechnung: „Gemahnt wird der Zahlbetrag …“", await tab.js(
        "document.getElementById('reminderStatusInfo').textContent"),
        lambda v: v.startswith("Gemahnt wird der Zahlbetrag 495,00 €") and seed["pauschal_nr"] in v and seed["abschlag_nr"] in v)
    p.pruefe("Schlussrechnung: überfällig, Zahlbetrag offen", await tab.js(
        "[invoice.is_overdue,document.getElementById('seitenkopfStatus').textContent.includes('Zahlbetrag offen 495,00')]"), [True, True])
    await tab.js("document.querySelector('#reminderActions button').click()")
    p.pruefe("Entwurf angelegt", await tab.warten("currentReminders.length===1"), True)
    _passt(p, "Aufstellung je Rechnung mit Nummer", await tab.js(
        "document.querySelector('#reminderList [data-aufstellung]')?.textContent||''"),
        lambda v: (f"zzgl. noch offen aus Abschlag Nr. {seed['pauschal_nr']} 119,00" in v
                   and f"zzgl. noch offen aus Abschlag Nr. {seed['abschlag_nr']} 138,00" in v and "davon Einbehalt 38,00" in v
                   and v.endswith("angemahnt 495,00 €")))
    rid = await tab.js("currentReminders[0].id")
    await tab.js(f"sendReminderNow({rid})")
    p.pruefe("festgeschrieben", await tab.warten("currentReminders[0]&&currentReminders[0].status==='versendet'"), True)
    pdf = await tab.js(f"fetch('/api/reminders/{rid}/pdf').then(r=>[r.status,r.headers.get('content-type')])")
    p.pruefe("PDF der Mahnung", pdf, [200, "application/pdf"])
    await tab.js("document.getElementById('remindersCard').scrollIntoView({block:'center'})")
    await tab.bild("schlussrechnung_mahnung_hell")
    # Zahlung auf den pauschalen Abschlag: die festgeschriebene Mahnung stimmt nicht mehr.
    status = await tab.js(
        "fetch('/api/payments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({customer_id:"
        f"{seed['kunde']},received_on:berlinToday(),amount:'119.00',note:null,lines:[{{invoice_id:{seed['pauschal']},"
        "zahlung:'119.00',skonto:'0.00',einbehalt:'0.00',charges:[]}]})}).then(r=>r.status)")
    p.pruefe("Zahlung auf den Abschlag gebucht", status, 200)
    await tab.oeffnen(f"/invoices/{seed['schluss']}", INVOICE_READY + "&&currentReminders.length===1")
    _passt(p, "Mahnung nennt den neuen Zahlbetrag", await tab.js("currentReminders[0].send_block||''"),
             lambda v: "mahnfähig sind inzwischen 376,00" in v)

    # --- API ---
    api = await tab.js(f"fetch('/api/invoices/{seed['abschlag']}/reminders',{{method:'POST',headers:{{'Content-Type':"
                       "'application/json'},body:'{}'}).then(async r=>[r.status,(await r.json()).detail])")
    p.pruefe("API: Mahnung zum Abschlag 409", [api[0], "abgezogen" in (api[1] or "")], [409, True])
    p.pruefe("JS-Fehler Büro", tab.fehler, [])

    # --- 412 px dunkel ---
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen("/mahnwesen", MAHNWESEN_READY)
    await tab.js("document.documentElement.setAttribute('data-theme','dark');document.getElementById('dueCard').scrollIntoView()")
    await tab.bild("mahnwesen_412_dunkel")
    await tab.oeffnen(f"/invoices/{seed['abschlag']}", INVOICE_READY)
    await tab.js("document.documentElement.setAttribute('data-theme','dark');document.getElementById('paymentsCard').scrollIntoView()")
    await tab.bild("abschlag_412_dunkel")
    await tab.fenster(1400, 1000)

    # --- Monteurin ---
    await tab.anmelden(seed["cookies"]["monteurin"])
    p.pruefe("Monteurin: 403", await tab.js(f"fetch('/api/invoices/{seed['schluss']}/reminder-status').then(r=>r.status)"), 403)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
