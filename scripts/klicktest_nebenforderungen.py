"""Klicktest: Zahlungsstufe Z2b (1.8.80, docs/archiv/zahlungen.md): Vertragspartner am Auftrag, Mahnung ersetzen, Mahngebühren und
Pauschale (zuschaltbar), Verzugsbeginn.

    Einstellungen      Büro: Schalter "Mahngebühren und Verzugszinsen" aus, nur lesen, keine Gebührenfelder, Einschalten per API
                       403; Admin schaltet ein -> Gebühr je Stufe als "Vorschlag" (Stufe 1: 0 €)
    Rechnungsseite     Karte "Nebenforderungen und Verzug": Vorschlag "Verzug ab" mit Quelle (Zugang der 1. Mahnung), bestätigen;
                       2. Mahnung anlegen, im Editor Vorschlag Gebühr 10 € und Pauschale, beides übernehmen -> Aufstellung mit
                       "(neu)", Gesamtbetrag; Festschreiben -> zwei Nebenforderungen, offen 50 €; Gebühr gegenbuchen mit Begründung
                       -> offen 40 €, die Mahnung geht nicht mehr hinaus ("nennt Nebenforderungen")
    Mahnwesen          nie hinausgegangene, überholte 1. Mahnung: Zeile "zur Mahnung fällig" mit "(ersetzt …)"; Status
                       "Hinausgegangen" bzw. "Festgeschrieben, noch nicht hinaus"; Ersatz anlegen und festschreiben -> "Ersetzt"
    Projektmappe       Kundenwechsel mit Auftrag: Begründungsfeld erscheint, ohne Begründung abgelehnt, mit Begründung gespeichert ->
                       Auftrag mit neuem Kunden (Name im Schnappschuss)
    Monteurin          Nebenforderungen und Schalter 403
    412 px dunkel      Rechnungsseite (Karte), Mahnwesen

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_nebenforderungen.py [--app-port N] [--cdp-port N]
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
    from app.invoices import create_abschlag_pauschal, finalize_and_send_invoice, update_invoice_header
    from app.models import AppUser, Customer, EmailDispatch, Employee, Project, Quote, QuoteItem, Reminder
    from app.orders import create_order_from_quote, load_order
    from app.payments import Line, book_payment
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.reminders import create_reminder, finalize_and_send_reminder

    heute = berlin_today()
    bea = Employee(employee_number="E-1", first_name="Bea", last_name="Büro", employee_group="angestellt", active=True,
                   hourly_wage=Decimal("22.00"))
    db.add(bea); db.flush()
    admin = AppUser(username="admin", display_name="Ada Admin", role="admin", password_hash=k.passwort())
    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_auftrag", employee_id=bea.id,
                    password_hash=k.passwort())
    monteurin = AppUser(username="monteurin", display_name="Mia Monteurin", role="field", password_hash=k.passwort())
    kunde = Customer(name="Gewerbe Dach GmbH", last_name="Gewerbe", is_consumer=False, street="Dachweg 1",
                     postal_code="52531", city="Uebach", email="gewerbe@example.com")
    weg = Customer(name="WEG Musterstraße 5", last_name="WEG", is_consumer=False, street="Musterstraße 5",
                   postal_code="52511", city="Geilenkirchen")
    db.add_all([admin, buero, monteurin, kunde, weg]); db.flush()

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

    # X: 1. Mahnung festgeschrieben und per Einschreiben zugestellt, Frist abgelaufen -> 2. Mahnung möglich, Verzug ab Zustellung
    x = rechnung("N-1", "1000", 20)  # 1.190,00
    m1 = finalize_and_send_reminder(db, create_reminder(db, x))
    db.execute(update(Reminder).where(Reminder.id == m1.id).values(reminder_date=heute - timedelta(days=10),
                                                                  new_due_date=heute - timedelta(days=3)))
    zugestellt = heute - timedelta(days=9)
    db.add(EmailDispatch(dispatch_key=f"klick-{uuid.uuid4()}", message_ref=str(uuid.uuid4()), status="gesendet",
                         channel="einschreiben", document_type="mahnung", document_id=m1.id, document_number=m1.reminder_number,
                         to_recipients="Gewerbe Dach GmbH", subject="Mahnung", finished_at=datetime(2026, 10, 3, 8, 0),
                         delivered_on=zugestellt, delivered_to_client=True, delivery_note="Einschreiben RR 1 DE"))
    db.commit()
    # Y: 1. Mahnung festgeschrieben, nie hinausgegangen, danach Teilzahlung -> geht so nicht mehr hinaus, wird ersetzt
    y = rechnung("N-2", "500", 20)  # 595,00
    m_y = finalize_and_send_reminder(db, create_reminder(db, y))
    book_payment(db, customer_id=kunde.id, received_on=heute, amount=Decimal("95"), note="Teilzahlung",
                 lines=[Line(y.id, zahlung=Decimal("95"))], user_name="Bea Büro")
    # P: Auftrag ohne festgeschriebene Rechnung -- Kundenwechsel nur mit Begründung
    p = auftrag("N-3")
    return {"x": x.id, "x_nr": x.invoice_number, "m1": m1.id, "m1_nr": m1.reminder_number, "y": y.id,
            "m_y": m_y.id, "m_y_nr": m_y.reminder_number, "projekt_p": p.project_id, "auftrag_p": p.id, "weg": weg.id,
            "verzug": zugestellt.strftime("%d.%m.%Y"),
            "cookies": {"admin": k.cookies(admin), "buero": k.cookies(buero), "monteurin": k.cookies(monteurin)}}


INVOICE_READY = "invoice&&document.getElementById('reminderStatusInfo').textContent.length>0&&chargesView!==null"
MAHNWESEN_READY = "document.getElementById('metrics').innerHTML.length>0&&document.getElementById('allRows').innerHTML.length>0"
SETTINGS_READY = "reminderLevels.length>0&&dunningSettings!==null&&document.querySelector('[data-schalter-zustand]')"


async def _bild(tab, name, element, dunkel=False):
    await tab.js(f"document.documentElement.setAttribute('data-theme','light');"
                 f"document.getElementById('{element}').scrollIntoView({{block:'center'}})")
    await tab.bild(name)
    if dunkel:
        await tab.js("document.documentElement.setAttribute('data-theme','dark')")
        await tab.bild(name + "_dunkel")
        await tab.js("document.documentElement.setAttribute('data-theme','light')")


def _knopf(text):
    return f"[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==={json.dumps(text)})"


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1280, 1000)

    # --- Einstellungen: Büro liest nur, Admin schaltet ein ---
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.oeffnen("/settings#reminder-levels", SETTINGS_READY)
    p.pruefe("Büro: ausgeschaltet, nur lesen", await tab.js(
        "[document.querySelector('[data-schalter-zustand]').textContent.startsWith('Ausgeschaltet'),"
        "!document.getElementById('dunningChargesEnabled'),document.getElementById('dunningSwitch').textContent"
        ".includes('Nur Administratoren')]"), [True, True, True])
    p.pruefe("Büro: keine Gebührenfelder", await tab.js("document.querySelectorAll('[id^=rl][id$=Fee]').length"), 0)
    p.pruefe("Büro: Einschalten per API 403", await tab.js(
        "fetch('/api/dunning-settings',{method:'PUT',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({charges_enabled:true})}).then(r=>r.status)"), 403)
    await _bild(tab, "einstellungen_aus", "settings-reminder-levels")
    await tab.anmelden(seed["cookies"]["admin"])
    await tab.oeffnen("/settings?als=admin#reminder-levels", SETTINGS_READY)  # neue Adresse: sonst bliebe die Seite des Büros
    await tab.js("(()=>{const c=document.getElementById('dunningChargesEnabled');c.checked=true;"
                 "c.dispatchEvent(new Event('change'))})()")
    p.pruefe("Admin: eingeschaltet, Gebühr je Stufe als Vorschlag", await tab.warten(
        "dunningSettings.charges_enabled&&document.querySelectorAll('[id^=rl][id$=Fee]').length===3"), True)
    p.pruefe("Vorschläge 0 / 10 / 15 €", await tab.js(
        "[1,2,3].map(l=>Number(document.querySelector(`[data-mahnstufe=\"${l}\"] input[id$=Fee]`).value))"), [0, 10, 15])
    p.pruefe("Feld heißt Vorschlag", await tab.js(
        "document.getElementById('reminderLevelRows').textContent.includes('Mahngebühr € (Vorschlag)')"), True)
    await _bild(tab, "einstellungen_ein", "settings-reminder-levels", dunkel=True)

    # --- Rechnungsseite X: Verzugsbeginn bestätigen, 2. Mahnung mit Gebühr und Pauschale ---
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.oeffnen(f"/invoices/{seed['x']}", INVOICE_READY)
    vorschlag = await tab.js("document.querySelector('[data-verzug-vorschlag]')?.textContent||''")
    p.pruefe("Vorschlag Verzug ab Zustellung der 1. Mahnung",
             [f"Vorschlag: Verzug ab {seed['verzug']}" in vorschlag, f"Zugang der 1. Mahnung {seed['m1_nr']}" in vorschlag],
             [True, True])
    await tab.js(_knopf("Verzugsbeginn bestätigen") + ".click()")
    p.pruefe("Verzugsbeginn bestätigt", await tab.warten(
        f"(document.querySelector('[data-verzug]')?.textContent||'').includes('Verzug ab {seed['verzug']}')"), True)
    p.pruefe("Mahnkarte: Stufe 1 erreicht", await tab.js(
        "document.getElementById('reminderStatusInfo').textContent.startsWith('Erreicht: Stufe 1')"), True)
    await tab.js(_knopf("2. Mahnung als Entwurf anlegen") + ".click()")
    p.pruefe("Entwurf der 2. Mahnung", await tab.warten("currentReminders.some(r=>r.status==='entwurf'&&r.level===2)"), True)
    entwurf = await tab.js("currentReminders.find(r=>r.status==='entwurf').id")
    await tab.js(f"editReminderNow({entwurf})")
    p.pruefe("Editor: Vorschlag Gebühr 10 €, nichts übernommen, Pauschale möglich", await tab.js(
        "[document.querySelector('[data-gebuehr-vorschlag]').textContent.includes('Mahngebühr 10,00'),"
        "document.getElementById('reminderEditorFeeAccepted').checked,document.getElementById('reminderEditorFlatAccepted')"
        ".disabled,!!document.querySelector('[data-pauschale-grund]')]"), [True, False, False, False])
    await tab.js("document.getElementById('reminderEditorFeeAccepted').checked=true;"
                 "document.getElementById('reminderEditorFlatAccepted').checked=true;saveReminderEditNow()")
    p.pruefe("übernommen: Aufstellung mit (neu), Gesamtbetrag 1.240 €", await tab.warten(
        f"currentReminders.some(r=>r.id==={entwurf}&&r.fee_accepted&&r.flat_fee_accepted&&r.total_amount==='1240.00')"), True)
    p.pruefe("Aufstellung in der Liste", await tab.js(
        "[...document.querySelectorAll('[data-aufstellung]')].some(e=>e.textContent.includes('Pauschale nach § 288 Abs. 5 BGB (neu)'))"),
        True)
    await _bild(tab, "entwurf_mit_nebenforderungen", "remindersCard")
    await tab.js(f"sendReminderNow({entwurf})")
    p.pruefe("festgeschrieben: zwei Nebenforderungen, offen 50 €", await tab.warten(
        "chargesView&&chargesView.charges.length===2&&chargesView.open_total==='50.00'"), True)
    gebuehr = await tab.js("chargesView.charges.find(c=>c.kind==='gebuehr').id")
    await tab.js(f"document.querySelector('[data-nebenforderung=\"{gebuehr}\"] button').click();"
                 f"document.getElementById('crevReason-{gebuehr}').value='Kulanz, Stammkunde';reverseCharge({gebuehr})")
    p.pruefe("Gebühr gegengebucht: offen 40 €", await tab.warten(
        "chargesView.open_total==='40.00'&&!!document.querySelector('[data-gegenbuchung]')"), True)
    p.pruefe("Mahnung mit geänderten Nebenforderungen geht nicht hinaus", await tab.warten(
        f"currentReminders.some(r=>r.id==={entwurf}&&(r.send_block||'').includes('nennt Nebenforderungen von 50,00'))"), True)
    p.pruefe("PDF der Mahnung", await tab.js(
        f"fetch('/api/reminders/{entwurf}/pdf').then(r=>[r.status,r.headers.get('content-type')])"), [200, "application/pdf"])
    await _bild(tab, "rechnung_nebenforderungen", "chargesCard", dunkel=True)
    await tab.fenster(412, 900, mobil=True)
    await tab.js("document.documentElement.setAttribute('data-theme','dark')")
    await tab.js("document.getElementById('chargesCard').scrollIntoView({block:'start'})")
    await tab.bild("rechnung_nebenforderungen_412_dunkel")
    p.pruefe("412 px: kein waagerechtes Scrollen", await tab.js(
        "document.documentElement.scrollWidth<=window.innerWidth+1"), True)
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.fenster(1280, 1000)

    # --- Mahnwesen: nie hinausgegangene Mahnung ersetzen ---
    await tab.oeffnen("/mahnwesen", MAHNWESEN_READY)
    zeile = await tab.js(f"(document.querySelector('#dueRows tr[data-faellig=\"{seed['y']}\"]')?.textContent||'')")
    p.pruefe("Y zur Mahnung fällig, ersetzt die alte", [f"(ersetzt {seed['m_y_nr']})" in zeile,
                                                     f"{seed['m_y_nr']} ging nie hinaus" in zeile], [True, True])
    p.pruefe("Status: hinausgegangen / noch nicht hinaus", await tab.js(
        f"[...document.querySelectorAll('#allRows tr')].filter(r=>r.textContent.includes('{seed['m1_nr']}')||"
        f"r.textContent.includes('{seed['m_y_nr']}')).map(r=>r.querySelector('[data-status]')?.dataset.status)"),
        ["festgeschrieben", "hinaus"])  # neueste zuerst: Y von heute, X vor zehn Tagen
    await tab.js(f"document.querySelector('#dueRows tr[data-faellig=\"{seed['y']}\"] button').click()")
    p.pruefe("Ersatz angelegt", await tab.warten(
        f"allReminders.some(r=>r.invoice_id==={seed['y']}&&r.status==='entwurf'&&r.level===1)"), True)
    ersatz = await tab.js(f"allReminders.find(r=>r.invoice_id==={seed['y']}&&r.status==='entwurf').id")
    await tab.js(f"sendReminder({ersatz})")
    p.pruefe("alte Mahnung ersetzt", await tab.warten(
        f"allReminders.some(r=>r.id==={seed['m_y']}&&r.replaced_by_id==={ersatz})"), True)
    p.pruefe("Status 'Ersetzt' und Grund statt E-Mail", await tab.js(
        f"(()=>{{const r=[...document.querySelectorAll('#allRows tr')].find(t=>t.textContent.includes('{seed['m_y_nr']}'));"
        "return [r.querySelector('[data-status]').dataset.status,(r.querySelector('[data-sperre]')?.textContent||'')"
        ".includes('ersetzt')]})()"), ["ersetzt", True])
    await _bild(tab, "mahnwesen_ersetzt", "allRows")
    await tab.fenster(412, 900, mobil=True)
    await _bild(tab, "mahnwesen_412", "dueCard", dunkel=True)
    await tab.fenster(1280, 1000)

    # --- Projektmappe: Kundenwechsel mit Auftrag nur mit Begründung ---
    await tab.oeffnen(f"/projects/{seed['projekt_p']}", "typeof project!=='undefined'&&project&&customers.length>0")
    await tab.js("openProjectEdit()")
    await tab.warten("document.getElementById('projectModal').classList.contains('open')||"
                     "getComputedStyle(document.getElementById('projectModal')).display!=='none'")
    p.pruefe("Begründungsfeld erst nach Kundenwahl", await tab.js(
        "document.getElementById('customerChangeReasonField').style.display"), "none")
    await tab.js(f"(()=>{{const s=document.getElementById('editCustomer');s.value='{seed['weg']}';"
                 "s.dispatchEvent(new Event('change'))})()")
    p.pruefe("Begründungsfeld erscheint", await tab.warten(
        "document.getElementById('customerChangeReasonField').style.display==='block'"), True)
    await tab.warten("document.getElementById('editProperty').options.length>0")
    await _bild(tab, "projekt_kundenwechsel", "projectModal")
    await tab.js("saveProject()")
    p.pruefe("ohne Begründung abgelehnt", await tab.warten(
        "document.getElementById('projectEditStatus').textContent.includes('bitte eine Begründung angeben')"), True)
    await tab.js("document.getElementById('editCustomerChangeReason').value='Auftraggeber ist die WEG';saveProject()")
    p.pruefe("mit Begründung gespeichert", await tab.warten(f"project.customer_id==={seed['weg']}"), True)
    auftrag = await tab.js(f"fetch('/api/orders/{seed['auftrag_p']}').then(r=>r.json()).then(o=>[o.customer_id,o.customer_name])")
    p.pruefe("Auftrag mit neuem Kunden", auftrag, [seed["weg"], "WEG Musterstraße 5"])
    p.pruefe("JS-Fehler", tab.fehler, [])

    # --- Monteurin ---
    await tab.anmelden(seed["cookies"]["monteurin"])
    status = await tab.js(f"Promise.all([fetch('/api/invoices/{seed['x']}/charges').then(r=>r.status),"
                          "fetch('/api/dunning-settings').then(r=>r.status)])")
    p.pruefe("Monteurin: 403", status, [403, 403])
    print(json.dumps({k: v for k, v in seed.items() if k != "cookies"}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
