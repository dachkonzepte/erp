"""Klicktest: Mahnwesen Z2a (1.8.79, Zahlungsstufe Z2a, docs/archiv/zahlungen.md).

    Mahnwesen          Öffnen legt nichts an; "Zur Mahnung fällig" mit den zwei überfälligen Rechnungen (seit 1.8.80 dazu der
                       Ersatz einer nie versendeten Mahnung), die übrigen mit Grund
                       ("erst ab dem …"); beide auswählen -> "Entwürfe für Auswahl anlegen (2)" -> zwei Entwürfe; Bearbeiten:
                       Zahlungsfrist in Tagen (10), Hinweis "Mahndatum ist der Tag des Festschreibens"; Versenden -> Mahndatum
                       heute, Frist heute + 10; Mahnung nach einer Teilzahlung: Grund statt E-Mail ("neue Mahnung")
    Rechnungsseite     Grund statt "anlegen" (nächste Stufe erst nach der Frist, nicht fällige Rechnung), Aufstellung der Mahnung
    Einstellungen      Mahnstufen ohne Schalter "automatisch anlegen", Zahl heißt "Zahlungsfrist (Tage ab Mahndatum)"
    Dashboard          Zeilen "Mahnung" mit gewähltem Mitarbeiter (Sachbearbeiter des Auftrags leer)
    API                E-Mail und Zustellung der überholten Mahnung 409; Kundenwechsel am Projekt mit festgeschriebener Rechnung
                       409; Monteurin 403
    412 px dunkel      Mahnwesen

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_mahnwesen.py [--app-port N] [--cdp-port N]
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
    from app.invoices import create_abschlag_pauschal, finalize_and_send_invoice, update_invoice_header
    from app.models import AppUser, Customer, EmailDispatch, Employee, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.payments import Line, book_payment
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.reminders import create_reminder, finalize_and_send_reminder

    heute = berlin_today()
    bea = Employee(employee_number="E-1", first_name="Bea", last_name="Büro", employee_group="angestellt", active=True,
                   hourly_wage=Decimal("22.00"))
    db.add(bea); db.flush()
    # seit 1.9.111: Geld nur Admin und Büro – Finanzen (app/permissions.py::darf_geld()) -- bis dahin Büro – Auftrag
    buero = AppUser(username="buero", display_name="Bea Büro", role="buero_finanzen", employee_id=bea.id,
                    password_hash=k.passwort())
    monteurin = AppUser(username="monteurin", display_name="Mia Monteurin", role="field", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Mahn", last_name="Mahn", street="Dachweg 1", postal_code="52531", city="Uebach",
                     email="mahn@example.com")
    anderer = Customer(name="Andere GmbH", last_name="Andere")
    db.add_all([buero, monteurin, kunde, anderer]); db.flush()

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

    a = rechnung("M-1", "1000", 10)          # 1.190,00, zur Mahnung fällig
    b = rechnung("M-2", "500", 5)            # 595,00, zur Mahnung fällig
    nicht_faellig = rechnung("M-3", "200", -7)   # erst in einer Woche fällig
    in_frist = rechnung("M-4", "300", 20)    # 1. Mahnung festgeschrieben und zugestellt, Frist läuft
    m4 = finalize_and_send_reminder(db, create_reminder(db, in_frist))
    # Seit 1.8.80 ist eine Stufe erst mit Versand oder Zustellung erreicht -- die 1. Mahnung ging per Einschreiben hinaus.
    db.add(EmailDispatch(dispatch_key="klick-m4-zustellung", message_ref="klick-m4-zustellung", status="gesendet",
                         channel="einschreiben", document_type="mahnung", document_id=m4.id, document_number=m4.reminder_number,
                         to_recipients="Bauherr Mahn", subject="Mahnung", delivered_on=heute, delivered_to_client=True))
    db.commit()
    ueberholt = rechnung("M-5", "400", 20)   # 476,00, festgeschrieben, danach Teilzahlung 100
    m5 = finalize_and_send_reminder(db, create_reminder(db, ueberholt))
    book_payment(db, customer_id=kunde.id, received_on=heute, amount=Decimal("100"), note="Teilzahlung",
                 lines=[Line(ueberholt.id, zahlung=Decimal("100"))], user_name="Bea Büro")
    return {"a": a.id, "a_nr": a.invoice_number, "b": b.id, "b_nr": b.invoice_number, "nicht_faellig": nicht_faellig.id,
            "in_frist": in_frist.id, "in_frist_nr": in_frist.invoice_number, "m4": m4.id, "m4_nr": m4.reminder_number,
            "m4_frist": m4.new_due_date.strftime("%d.%m.%Y"), "ueberholt": ueberholt.id, "m5": m5.id,
            "m5_nr": m5.reminder_number, "projekt_a": load_order(db, a.order_id).project_id, "anderer": anderer.id,
            "heute": heute.strftime("%d.%m.%Y"), "frist10": (heute + timedelta(days=10)).strftime("%d.%m.%Y"),
            "frist10_iso": (heute + timedelta(days=10)).isoformat(), "heute_iso": heute.isoformat(),
            "nicht_faellig_am": (heute + timedelta(days=7)).strftime("%d.%m.%Y"),
            "cookies": {"buero": k.cookies(buero), "monteurin": k.cookies(monteurin)}}


MAHNWESEN_READY = "document.getElementById('metrics').innerHTML.length>0&&document.getElementById('allRows').innerHTML.length>0"
INVOICE_READY = "invoice&&document.getElementById('reminderStatusInfo').textContent.length>0"


async def _bild(tab, name, element, dunkel=False):
    await tab.js(f"document.documentElement.setAttribute('data-theme','light');"
                 f"document.getElementById('{element}').scrollIntoView({{block:'center'}})")
    await tab.bild(name)
    if dunkel:
        await tab.js("document.documentElement.setAttribute('data-theme','dark')")
        await tab.bild(name + "_dunkel")
        await tab.js("document.documentElement.setAttribute('data-theme','light')")


async def _anzahl_mahnungen(tab):
    return await tab.js("fetch('/api/reminders').then(r=>r.json()).then(d=>d.length)")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1280, 1000)
    await tab.anmelden(seed["cookies"]["buero"])

    # --- Mahnwesen: Öffnen legt nichts an, Liste "zur Mahnung fällig" ---
    await tab.oeffnen("/settings", "true")
    vorher = await _anzahl_mahnungen(tab)
    await tab.oeffnen("/mahnwesen", MAHNWESEN_READY)
    p.pruefe("Öffnen legt keine Entwürfe an", [vorher, await _anzahl_mahnungen(tab)], [2, 2])
    # Seit 1.8.80 ("Vorweg" 2) auch M-5: ihre 1. Mahnung ging nie hinaus und geht nach der Teilzahlung so nicht mehr hinaus --
    # eine neue derselben Stufe ersetzt sie.
    p.pruefe("zur Mahnung fällig: die zwei überfälligen und der Ersatz", await tab.js(
        "[...document.querySelectorAll('#dueRows tr[data-faellig]')].map(r=>Number(r.dataset.faellig)).sort((x,y)=>x-y)"),
             sorted([seed["a"], seed["b"], seed["ueberholt"]]))
    p.pruefe("Ersatz mit Hinweis", await tab.js(
        f"(document.querySelector('#dueRows tr[data-faellig=\"{seed['ueberholt']}\"]')?.textContent||'')"
        f".includes('(ersetzt {seed['m5_nr']})')"), True)
    p.pruefe("Kennzahl", await tab.js("document.querySelector('[data-kennzahl-faellig]').textContent"), "3")
    gruende = await tab.js("[...document.querySelectorAll('#attentionRows [data-grund]')].map(e=>e.textContent)")
    p.pruefe("in der Frist: Grund statt Knopf", any(
        g.startswith(f"Die 2. Mahnung ist erst ab dem") and seed["m4_nr"] in g and seed["m4_frist"] in g for g in gruende), True)
    p.pruefe("nicht fällige Rechnung nicht überfällig", await tab.js(
        f"attentionRows.some(r=>r.invoice_id==={seed['nicht_faellig']})"), False)
    p.pruefe("Auswahl: Knopf gesperrt ohne Auswahl", await tab.js("document.getElementById('bulkCreateBtn').disabled"), True)
    await tab.js("(()=>{const c=document.getElementById('dueSelectAll');c.checked=true;c.dispatchEvent(new Event('change'))})()")
    p.pruefe("Auswahl: Knopf mit Anzahl", await tab.js("document.getElementById('bulkCreateBtn').textContent"),
             "Entwürfe für Auswahl anlegen (3)")
    await _bild(tab, "zur_mahnung_faellig", "dueCard", dunkel=True)
    # Seit 1.8.87: der Text steht vor dem Neuladen der Liste (createSelectedReminders(): erst Text, dann reload()) -- erst auf
    # die neu geladene Liste warten, dann lesen (bis 1.8.86 las der Klicktest sofort und sah je nach Tempo noch die alte); seit
    # 1.8.94 über den gemeinsamen Helfer.
    await tab.warte_auf_neu_geladene_liste("document.getElementById('bulkCreateBtn').click()", "#dueRows")
    p.pruefe("drei Entwürfe angelegt", await tab.js("document.getElementById('bulkStatus').textContent"), "3 Entwürfe angelegt.")
    p.pruefe("Liste danach leer, Entwürfe in 'Weitere'", await tab.js(
        "[document.querySelectorAll('#dueRows tr[data-faellig]').length,"
        "document.querySelectorAll('#attentionRows .pill.entwurf').length]"), [0, 3])
    p.pruefe("API: jetzt fünf Mahnungen", await _anzahl_mahnungen(tab), 5)

    # --- Bearbeiten: Zahlungsfrist in Tagen; Versenden: Mahndatum heute, Frist ab dann ---
    entwurf = await tab.js(f"allReminders.find(r=>r.invoice_id==={seed['a']}&&r.status==='entwurf').id")
    await tab.js(f"editReminder({entwurf})")
    p.pruefe("Editor: Frist 7 Tage, Hinweis", await tab.js(
        "[document.getElementById('editorPaymentDays').value,document.getElementById('editorDatesHint').textContent"
        ".startsWith('Mahndatum ist der Tag des Festschreibens')]"), ["7", True])
    await tab.js("document.getElementById('editorPaymentDays').value='10';saveReminderEdit()")
    p.pruefe("gespeichert: 10 Tage", await tab.warten(
        f"allReminders.some(r=>r.id==={entwurf}&&r.payment_days===10&&r.effective_new_due_date==='{seed['frist10_iso']}')"), True)
    await _bild(tab, "entwurf_bearbeitet", "allRows")
    await tab.js(f"sendReminder({entwurf})")
    p.pruefe("festgeschrieben: heute, Frist heute + 10", await tab.warten(
        f"allReminders.some(r=>r.id==={entwurf}&&r.status==='versendet'&&r.reminder_date==='{seed['heute_iso']}'"
        f"&&r.new_due_date==='{seed['frist10_iso']}')"), True)

    # Seit 1.8.80: erst mit Versand oder Zustellung erreicht -- Zustellung per Einschreiben nachtragen.
    zugestellt = await tab.js(
        "(()=>{const f=new FormData();f.append('document_type','mahnung');" + f"f.append('document_id','{entwurf}');"
        "f.append('channel','einschreiben');f.append('delivered_on','" + seed["heute_iso"] + "');"
        "f.append('note','Einschreiben RR 2 DE');f.append('dispatch_key','zustellung-klick-0002');"
        "return fetch('/api/email-dispatches/manual',{method:'POST',body:f}).then(r=>r.status)})()")
    p.pruefe("Zustellung der neuen Mahnung nachgetragen", zugestellt, 200)

    # --- Überholte Mahnung: Grund statt E-Mail ---
    sperre = await tab.js(
        f"(()=>{{const r=allReminders.find(x=>x.id==={seed['m5']});return r.send_block}})()")
    p.pruefe("überholte Mahnung: Grund", [sperre.startswith(f"Die Mahnung {seed['m5_nr']} lautet über 476,00 €, mahnfähig "
                                                          "sind inzwischen 376,00 €"), "neue Mahnung" in sperre], [True, True])
    p.pruefe("kein E-Mail-Feld an der überholten Mahnung", await tab.js(
        f"!document.getElementById('reminderEmailInput{seed['m5']}')"), True)
    await tab.fenster(412, 900, mobil=True)
    await _bild(tab, "mahnwesen_412", "dueCard", dunkel=True)
    await tab.fenster(1280, 1000)

    # --- Rechnungsseite: Grund statt Knopf, Aufstellung ---
    await tab.oeffnen(f"/invoices/{seed['a']}", INVOICE_READY)
    p.pruefe("Rechnung A: kein Anlegen, Grund mit Frist", await tab.js(
        "[!!document.querySelector('#reminderActions button'),(document.querySelector('#reminderActions [data-grund]')"
        "?.textContent||'').startsWith('Die 2. Mahnung ist erst ab dem')]"), [False, True])
    p.pruefe("Aufstellung an der Mahnung", await tab.js("document.querySelector('[data-aufstellung]')?.textContent"),
             "Brutto 1.190,00\xa0€ · angemahnt 1.190,00\xa0€")
    await _bild(tab, "rechnung_mahnkarte", "remindersCard", dunkel=True)
    await tab.oeffnen(f"/invoices/{seed['ueberholt']}", INVOICE_READY)
    p.pruefe("Rechnung mit Teilzahlung: Grund an der Mahnung", await tab.js(
        "(document.querySelector('#reminderList [data-sperre]')?.textContent||'').includes('neue Mahnung')"), True)
    await tab.oeffnen(f"/invoices/{seed['nicht_faellig']}", INVOICE_READY)
    grund = await tab.js("document.querySelector('#reminderActions [data-grund]')?.textContent||''")
    p.pruefe("nicht fällige Rechnung: Grund statt Knopf",
             [f"ist erst am {seed['nicht_faellig_am']} fällig" in grund, await tab.js(
                 "!!document.querySelector('#reminderActions button')")], [True, False])
    pdf = await tab.js(f"fetch('/api/reminders/{entwurf}/pdf').then(r=>[r.status,r.headers.get('content-type')])")
    p.pruefe("PDF der Mahnung", pdf, [200, "application/pdf"])

    # --- API: Versand und Zustellung der überholten Mahnung, Kundenwechsel ---
    mail = await tab.js(
        f"fetch('/api/reminders/{seed['m5']}/send-email',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        "body:JSON.stringify({to_email:'mahn@example.com',dispatch_key:'mahnung-klick-0000001'})}).then(r=>r.status)")
    p.pruefe("API: E-Mail der überholten Mahnung 409", mail, 409)
    zustellung = await tab.js(
        "(()=>{const f=new FormData();f.append('document_type','mahnung');f.append('document_id','" + str(seed["m5"]) + "');"
        "f.append('channel','einschreiben');f.append('delivered_on','" + seed["heute_iso"] + "');"
        "f.append('note','Einschreiben RR 1 DE');f.append('dispatch_key','zustellung-klick-0001');"
        "return fetch('/api/email-dispatches/manual',{method:'POST',body:f}).then(async r=>[r.status,(await r.json()).detail])})()")
    p.pruefe("API: Zustellung der überholten Mahnung 409", [zustellung[0], "mahnfähig waren am" in zustellung[1]], [409, True])
    wechsel = await tab.js(
        f"fetch('/api/projects/{seed['projekt_a']}').then(r=>r.json()).then(pr=>fetch('/api/projects/{seed['projekt_a']}',"
        f"{{method:'PUT',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{customer_id:{seed['anderer']},"
        "property_id:pr.property_id,name:pr.name})}).then(async r=>[r.status,(await r.json()).detail]))")  # seit 1.9.125 ohne Status (abgeleitet, mitgeschickt 422)
    p.pruefe("API: Kundenwechsel mit festgeschriebener Rechnung 409",
             [wechsel[0], f"ist die Rechnung {seed['a_nr']} festgeschrieben" in wechsel[1]], [409, True])

    # --- Einstellungen und Dashboard ---
    await tab.oeffnen("/settings#reminder-levels", "reminderLevels.length>0")
    p.pruefe("Einstellungen: kein Schalter, Zahlungsfrist", await tab.js(
        "[!!document.getElementById('autoCreateDraftsCheckbox'),document.getElementById('reminderLevelRows').textContent"
        ".includes('Zahlungsfrist (Tage ab Mahndatum)')]"), [False, True])
    await _bild(tab, "einstellungen_mahnstufen", "settings-reminder-levels")
    await tab.oeffnen("/", "document.getElementById('taskListArea')&&!document.getElementById('taskListArea').textContent"
                           ".startsWith('Lädt')")
    p.pruefe("Dashboard: Mahnungen mit Mitarbeiter", await tab.js(
        "document.querySelectorAll('#taskListArea .task-type.reminder').length>=3"), True)
    p.pruefe("JS-Fehler", tab.fehler, [])

    # --- Monteurin ---
    await tab.anmelden(seed["cookies"]["monteurin"])
    status = await tab.js("Promise.all([fetch('/api/reminders/overdue').then(r=>r.status),fetch('/api/reminders/bulk',"
                          "{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({invoice_ids:[1]})})"
                          ".then(r=>r.status)])")
    p.pruefe("Monteurin: Mahnwesen 403", status, [403, 403])
    print(json.dumps({k: v for k, v in seed.items() if k != "cookies"}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
