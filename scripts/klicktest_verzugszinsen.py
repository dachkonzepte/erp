"""Klicktest: Zahlungsstufe Z2b Punkte 7-9 (1.8.81, docs/archiv/zahlungen.md "Umsetzung 1.8.81"): Basiszinssatz, Verzugszinsen,
Zahlungen auf Nebenforderungen nach § 367 BGB, Rechtstexte, keine Gebühr neben der Pauschale, Storno nur ohne offene
Nebenforderungen, Rückfrage vor dem Ersetzen.

    Einstellungen      Büro: Basiszinssatz und Rechtstexte nur lesen, Anlegen per API 403; Admin legt das laufende Halbjahr an
                       (geprüft) und einen geprüften Rechtstext "Verzugszinsen"
    Rechnungsseite X   2. Mahnung: vorher "kein Basiszinssatz für das Halbjahr …", danach Zinsvorschlag mit Abschnitt (10,27 %,
                       9 Tage); Pauschale übernehmen sperrt die Gebühr ("abgegolten"); Zinsen übernehmen; Warnungen für die
                       ungeprüften Rechtstexte "Verzug" und "Pauschale", "Wird gedruckt" für "Verzugszinsen"; Festschreiben ->
                       Pauschale und Zinsen mit Abschnitt in der Karte, Aufstellung Format 3 mit dem Rechtstext
                       Zahlungsdialog: Betrag samt Nebenforderungen vorbelegt; 50 € -> erst Pauschale, dann Zinsen, dann die Rechnung;
                       gebucht -> Nebenforderungen offen 0, Storno gesperrt (Zuordnungen)
    Rechnungsseite W   offene Mahngebühr -> statt "Stornieren" der Grund "offene Nebenforderungen"
    Mahnwesen          Ersatz der nie hinausgegangenen 2. Mahnung von Y: "Beim Festschreiben ersetzt … gegengebucht werden:
                       Mahngebühr …" in der Zeile und in der Rückfrage; danach ersetzt und die Gebühr gegengebucht
    Monteurin          Basiszinssatz und Rechtstexte 403
    412 px dunkel      Rechnungsseite (Nebenforderungen, Zahlungsdialog), Einstellungen

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_verzugszinsen.py [--app-port N] [--cdp-port N]
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
    import uuid
    from datetime import date, datetime, timedelta
    from decimal import Decimal

    from sqlalchemy import update

    from app.berlin_time import berlin_today
    from app.default_interest import half_year_of, next_half_year
    from app.dunning_charges import confirm_default_start
    from app.invoices import create_abschlag_pauschal, finalize_and_send_invoice, update_invoice_header
    from app.models import (
        AppUser, BaseInterestRate, Customer, EmailDispatch, GeneralSettings, InvoiceCharge, Project, Quote, QuoteItem, Reminder,
    )
    from app.orders import create_order_from_quote, load_order
    from app.payments import Line, book_payment
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.reminders import create_reminder, finalize_and_send_reminder, set_reminder_charges

    heute = berlin_today()
    admin = AppUser(username="admin", display_name="Ada Admin", role="admin", password_hash=k.passwort())
    # seit 1.9.111: Geld nur Admin und Büro – Finanzen (app/permissions.py::darf_geld()) -- bis dahin Büro – Auftrag
    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_finanzen", password_hash=k.passwort())
    monteurin = AppUser(username="monteurin", display_name="Mia Monteurin", role="field", password_hash=k.passwort())
    kunde = Customer(name="Gewerbe Dach GmbH", last_name="Gewerbe", is_consumer=False, street="Dachweg 1",
                     postal_code="52531", city="Uebach", email="gewerbe@example.com")
    db.add_all([admin, buero, monteurin, kunde]); db.flush()
    db.get(GeneralSettings, 1).dunning_charges_enabled = True
    # Basiszinssätze der vergangenen Halbjahre (Testwerte), das laufende fehlt -- das legt der Admin in der Oberfläche an.
    hy = half_year_of(heute - timedelta(days=400))
    while hy < half_year_of(heute):
        db.add(BaseInterestRate(half_year_start=hy, rate_percent=Decimal("1.27"), reviewed_on=heute, reviewed_by="Test"))
        hy = next_half_year(hy)
    db.commit()

    def auftrag(nummer):
        projekt = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=kunde.id, status="angebot",
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-{nummer}", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2",
                         unit_price=Decimal("50")))
        db.commit()
        order = create_order_from_quote(db, quote.id, order_date=date(2026, 9, 1), execution_start=None, execution_end=None,
                                        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None,
                                        remarks=None)
        return load_order(db, order.id)

    def rechnung(nummer, net, faellig_vor_tagen):
        invoice = create_abschlag_pauschal(db, auftrag(nummer), lump_sum_net=Decimal(net))
        update_invoice_header(db, invoice, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 30))
        invoice = finalize_and_send_invoice(db, invoice)
        invoice.due_date = heute - timedelta(days=faellig_vor_tagen)
        db.commit()
        return invoice

    def erste_zugestellt(invoice):
        m1 = finalize_and_send_reminder(db, create_reminder(db, invoice))
        db.execute(update(Reminder).where(Reminder.id == m1.id).values(reminder_date=heute - timedelta(days=10),
                                                                      new_due_date=heute - timedelta(days=3)))
        db.add(EmailDispatch(dispatch_key=f"klick-{uuid.uuid4()}", message_ref=str(uuid.uuid4()), status="gesendet",
                             channel="einschreiben", document_type="mahnung", document_id=m1.id,
                             document_number=m1.reminder_number, to_recipients="Gewerbe Dach GmbH", subject="Mahnung",
                             finished_at=datetime(2026, 10, 3, 8, 0), delivered_on=heute - timedelta(days=9),
                             delivered_to_client=True, delivery_note="Einschreiben RR 1 DE"))
        db.commit()
        return m1

    # X: 1. Mahnung vor neun Tagen zugestellt, Verzug ab dann bestätigt, 2. Mahnung als Entwurf
    x = rechnung("Z-1", "1000", 20)  # 1.190,00
    erste_zugestellt(x)
    confirm_default_start(db, x, starts_on=heute - timedelta(days=9), reason=None)
    m2 = create_reminder(db, x)
    # Y: 2. Mahnung mit Gebühr festgeschrieben, nie hinausgegangen, danach Teilzahlung -> Ersatz als Entwurf
    y = rechnung("Z-2", "500", 20)  # 595,00
    erste_zugestellt(y)
    m_y = create_reminder(db, y)
    set_reminder_charges(db, m_y, fee_amount=Decimal("10.00"), fee_accepted=True, flat_fee_accepted=False)
    finalize_and_send_reminder(db, m_y)
    book_payment(db, customer_id=kunde.id, received_on=heute, amount=Decimal("95"), note="Teilzahlung",
                 lines=[Line(y.id, zahlung=Decimal("95"))], user_name="Bea Büro")
    ersatz = create_reminder(db, y)
    # W: offene Mahngebühr (Bestand) -> Storno gesperrt
    w = rechnung("Z-3", "200", 20)
    db.add(InvoiceCharge(invoice_id=w.id, kind="gebuehr", amount=Decimal("10.00"), created_by_name="Test"))
    db.commit()
    halbjahr = half_year_of(heute)
    return {"x": x.id, "m2": m2.id, "y": y.id, "m_y": m_y.id, "m_y_nr": m_y.reminder_number, "ersatz": ersatz.id, "w": w.id,
            "halbjahr_monat": "07-01" if halbjahr.month == 7 else "01-01", "halbjahr_jahr": halbjahr.year,
            "halbjahr_text": f"{halbjahr.strftime('%d.%m.%Y')}",
            "zinsen": str((Decimal("1190.00") * Decimal("10.27") * 9 / Decimal(36500)).quantize(Decimal("0.01"))),
            "cookies": {"admin": k.cookies(admin), "buero": k.cookies(buero), "monteurin": k.cookies(monteurin)}}


INVOICE_READY = "invoice&&document.getElementById('reminderStatusInfo').textContent.length>0&&chargesView!==null"
MAHNWESEN_READY = "document.getElementById('metrics').innerHTML.length>0&&document.getElementById('allRows').innerHTML.length>0"
SETTINGS_READY = "reminderLevels.length>0&&baseRates!==null&&legalTexts!==null&&document.querySelector('[data-rechtstext]')"


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
                  source="window.alert=m=>console.error('alert(): '+m);"
                         "window.confirm=m=>{window.__rueckfragen=(window.__rueckfragen||[]).concat([m]);return true}")
    await tab.fenster(1280, 1000)

    # --- Einstellungen: Büro liest nur ---
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.oeffnen("/settings#reminder-levels", SETTINGS_READY)
    p.pruefe("Büro: Basiszinssatz und Rechtstexte nur lesen", await tab.js(
        "[document.getElementById('baseRatesBox').textContent.includes('Nur Administratoren pflegen'),"
        "!document.querySelector('[data-basiszins-neu]'),[...document.querySelectorAll('.ltBody')].every(t=>t.disabled),"
        "document.getElementById('legalTextsBox').textContent.includes('Nur Administratoren')]"), [True, True, True, True])
    p.pruefe("Büro: Anlegen per API 403", await tab.js(
        "fetch('/api/base-interest-rates',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify("
        "{half_year_start:'2026-07-01',rate_percent:'1.27',reviewed_on:null,reviewed_by:null})}).then(r=>r.status)"), 403)

    # --- Rechnungsseite X vorher: kein Basiszinssatz für das laufende Halbjahr ---
    await tab.oeffnen(f"/invoices/{seed['x']}", INVOICE_READY)
    await tab.js(f"editReminderNow({seed['m2']})")
    p.pruefe("Zinsen: Halbjahr fehlt", await tab.js(
        "(document.querySelector('[data-zinsen-grund]')?.textContent||'')"
        f".includes('kein Basiszinssatz für das Halbjahr {seed['halbjahr_text']}')"), True)

    # --- Admin: laufendes Halbjahr und Rechtstext anlegen ---
    await tab.anmelden(seed["cookies"]["admin"])
    await tab.oeffnen("/settings?als=admin#reminder-levels", SETTINGS_READY)
    await tab.js(f"document.getElementById('brNewHalf').value='{seed['halbjahr_monat']}';"
                 f"document.getElementById('brNewYear').value='{seed['halbjahr_jahr']}';"
                 "document.getElementById('brNewRate').value='1,27';"
                 "document.getElementById('brNewOn').value=new Date(Date.now()-86400000).toISOString().slice(0,10);"
                 "document.getElementById('brNewBy').value='Kanzlei Test';createBaseRate()")
    p.pruefe("Admin: Halbjahr angelegt und geprüft", await tab.warten(
        "baseRates.length>=1&&baseRates[0].reviewed&&document.querySelector('[data-basiszins-stand]').textContent==='geprüft'"),
        True)
    await tab.js("(()=>{const r=document.querySelector('[data-rechtstext=\"zinsen\"]');"
                 "r.querySelector('.ltBody').value='Verzugszinsen: {prozentpunkte} Prozentpunkte ueber dem Basiszinssatz "
                 "vom {zinsen_von} bis {zinsen_bis} (Testtext).';"
                 "r.querySelector('.ltOn').value=new Date(Date.now()-86400000).toISOString().slice(0,10);"
                 "r.querySelector('.ltBy').value='Kanzlei Test';saveLegalText('zinsen')})()")
    p.pruefe("Admin: Rechtstext Zinsen geprüft", await tab.warten(
        "legalTexts.find(t=>t.text_key==='zinsen').reviewed"), True)
    await tab.js("(()=>{const r=document.querySelector('[data-rechtstext=\"verzug\"]');"
                 "r.querySelector('.ltBody').value='Text mit {tippfehler}';saveLegalText('verzug')})()")
    p.pruefe("unbekannter Platzhalter gewarnt", await tab.warten(
        "(document.querySelector('[data-rechtstext=\"verzug\"] [data-unbekannt]')?.textContent||'').includes('{tippfehler}')"),
        True)
    await _bild(tab, "einstellungen_basiszins", "dunningLegal", dunkel=True)

    # --- Rechnungsseite X: Zinsvorschlag, Pauschale sperrt die Gebühr, Warnungen, Festschreiben ---
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.oeffnen(f"/invoices/{seed['x']}?als=buero", INVOICE_READY)
    await tab.js(f"editReminderNow({seed['m2']})")
    zinsen = await tab.js("[document.querySelector('label:has(#reminderEditorInterestAccepted)')?.textContent||'',"
                          "document.querySelector('[data-zinsen-abschnitte]')?.textContent||'']")
    betrag = seed["zinsen"].replace(".", ",")
    p.pruefe("Zinsvorschlag mit Abschnitt", [f"Verzugszinsen {betrag}" in zinsen[0], "9 Prozentpunkte" in zinsen[0],
                                            "10,27 %" in zinsen[1], "9 Tage" in zinsen[1], "durch 365" in zinsen[1]],
             [True, True, True, True, True])
    await tab.js("(()=>{const f=document.getElementById('reminderEditorFlatAccepted');f.checked=true;"
                 "f.dispatchEvent(new Event('change'));document.getElementById('reminderEditorInterestAccepted').checked=true})()")
    p.pruefe("Pauschale sperrt die Gebühr", await tab.js(
        "[document.getElementById('reminderEditorFeeAccepted').disabled,"
        "getComputedStyle(document.querySelector('[data-gebuehr-abgegolten]')).display!=='none']"), [True, True])
    await tab.js("saveReminderEditNow()")
    p.pruefe("übernommen: Pauschale und Zinsen", await tab.warten(
        f"currentReminders.some(r=>r.id==={seed['m2']}&&r.flat_fee_accepted&&r.interest_accepted&&!r.fee_accepted)"), True)
    await tab.warten(f"currentReminders.some(r=>r.id==={seed['m2']}&&r.interest_accepted)")
    p.pruefe("Rechtstexte: Warnungen und gedruckt", await tab.js(
        f"(()=>{{const r=currentReminders.find(r=>r.id==={seed['m2']});return [r.legal_text_warnings.map(w=>w.split('„')[1]"
        ".split('“')[0]),r.legal_texts.map(t=>t.key)]})()"), [["Verzug", "Pauschale nach § 288 Abs. 5 BGB"], ["zinsen"]])
    p.pruefe("Warnung in der Liste", await tab.js(
        "[...document.querySelectorAll('[data-rechtstext-warnung]')].map(e=>e.textContent).join('|').includes('„Pauschale nach')"),
        True)
    await _bild(tab, "entwurf_mit_zinsen", "remindersCard")
    await tab.js(f"sendReminderNow({seed['m2']})")
    p.pruefe("festgeschrieben: Pauschale und Zinsen", await tab.warten(
        "chargesView&&chargesView.charges.length===2&&chargesView.charges.some(c=>c.kind==='zinsen'&&c.sections.length===1)"),
        True)
    p.pruefe("Karte zeigt den Zinsabschnitt", await tab.js(
        "(document.querySelector('[data-zinsabschnitte]')?.textContent||'').includes('10,27 %')"), True)
    aufstellung = await tab.js(f"fetch('/api/invoices/{seed['x']}/reminders').then(r=>r.json()).then(l=>l.find(r=>r.id==="
                               f"{seed['m2']})).then(r=>[r.amounts.format,r.amounts.legal_texts.length,"
                               "r.amounts.legal_texts[0].text.includes('Testtext')])")
    # Seit 1.8.89 Format 4 (R4c: abgezogene Rechnungen der Endrechnung und angemahnter Betrag) -- bis 1.8.88 Format 3.
    p.pruefe("Aufstellung Format 4 mit Rechtstext", aufstellung, [4, 1, True])
    p.pruefe("PDF der Mahnung", await tab.js(
        f"fetch('/api/reminders/{seed['m2']}/pdf').then(r=>[r.status,r.headers.get('content-type')])"), [200, "application/pdf"])

    # --- Zahlungsdialog: § 367 BGB ---
    await tab.js("openPaymentDialog()")
    await tab.warten("payLines.length>0")
    owed = await tab.js("document.getElementById('pyAmount').value")
    p.pruefe("Betrag samt Nebenforderungen vorbelegt", owed, f"{1190 + 40 + float(seed['zinsen']):.2f}".replace(".", ","))
    await tab.js("document.getElementById('pyAmount').value='50,00';payProposal()")
    p.pruefe("Vorschlag: erst Pauschale, dann Zinsen, dann die Rechnung", await tab.warten(
        f"payLines.length===1&&payLines[0].charges.map(c=>c.kind+':'+c.amount).join(',')==='pauschale:40,00,zinsen:{betrag}'"
        f"&&payLines[0].zahlung==='{50 - 40 - float(seed['zinsen']):.2f}'.replace('.',',')"), True)
    p.pruefe("Zeilen der Nebenforderungen vor der Rechnung", await tab.js(
        "[...document.querySelectorAll('#pyLines .py-row')].map(r=>r.dataset.nebenforderungZeile?'NF':'R').join('')"), "NFNFR")
    await tab.fenster(412, 900, mobil=True)
    await tab.js("document.documentElement.setAttribute('data-theme','dark')")
    await tab.bild("zahlungsdialog_412_dunkel")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.fenster(1280, 1000)
    await tab.js("confirmPayment()")
    p.pruefe("gebucht: Nebenforderungen bezahlt, Rechnung offen", await tab.warten(
        f"chargesView.open_total==='0.00'&&invoice.payment.open==='{1190 - (50 - 40 - float(seed['zinsen'])):.2f}'"), True)
    p.pruefe("Storno gesperrt (Zuordnungen)", await tab.js(
        "(document.querySelector('#statusActions [data-sperre]')?.textContent||'').includes('Zahlung auf Nebenforderung')"), True)
    await _bild(tab, "rechnung_nebenforderungen_bezahlt", "chargesCard", dunkel=True)

    # --- Rechnungsseite W: offene Nebenforderung sperrt das Storno ---
    await tab.oeffnen(f"/invoices/{seed['w']}", INVOICE_READY)
    p.pruefe("W: Grund statt Stornieren", await tab.js(
        "[(document.querySelector('#statusActions [data-sperre]')?.textContent||'').includes('offene Nebenforderungen'),"
        "![...document.querySelectorAll('#statusActions button')].some(b=>b.textContent.trim()==='Stornieren')]"), [True, True])

    # --- Mahnwesen: Ersatz nennt die gegengebuchte Gebühr ---
    await tab.oeffnen("/mahnwesen", MAHNWESEN_READY)
    zeile = await tab.js("[...document.querySelectorAll('[data-ersatz-hinweis]')].map(e=>e.textContent).join('|')")
    p.pruefe("Ersatz: gegengebuchte Gebühr genannt", [f"ersetzt: {seed['m_y_nr']}" in zeile, "Mahngebühr (2. Mahnung" in zeile,
                                                    "10,00" in zeile], [True, True, True])
    await tab.js(f"sendReminder({seed['ersatz']})")
    p.pruefe("Rückfrage nennt die Gegenbuchung", await tab.warten(
        f"(window.__rueckfragen||[]).some(m=>m.includes('{seed['m_y_nr']}')&&m.includes('gegengebucht werden: Mahngebühr'))"),
        True)
    p.pruefe("ersetzt", await tab.warten(f"allReminders.some(r=>r.id==={seed['m_y']}&&r.replaced_by_id==={seed['ersatz']})"),
             True)
    gegen = await tab.js(f"fetch('/api/invoices/{seed['y']}/charges').then(r=>r.json()).then(v=>[v.open_total,"
                         "v.charges[0].reversed])")
    p.pruefe("Gebühr der ersetzten Mahnung gegengebucht", gegen, ["0.00", True])
    p.pruefe("JS-Fehler", tab.fehler, [])

    # --- Monteurin ---
    await tab.anmelden(seed["cookies"]["monteurin"])
    status = await tab.js("Promise.all([fetch('/api/base-interest-rates').then(r=>r.status),"
                          "fetch('/api/dunning-legal-texts').then(r=>r.status)])")
    p.pruefe("Monteurin: 403", status, [403, 403])
    print(json.dumps({k: v for k, v in seed.items() if k != "cookies"}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
