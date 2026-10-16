"""Klicktest: Versandprotokoll in Projektmappe und Kundenakte, Mahnung als einzelne, "Mein Konto" mobil, Leistungsformular für
Büro – Auftrag (1.8.113, Vorgabe vom 16.10.2026 Punkte 4–6).

Geprüft wird im echten Browser:

    Projektmappe      Reiter "Versand": nur die Einträge zu Dokumenten dieses Projekts (Angebot, Auftrag, Rechnung, Mahnung),
                      nicht die des anderen Projekts; "Im Versandprotokoll öffnen" -> /versandprotokoll?projekt=…, dort dieselben
                      Einträge und der Hinweis "Nur die Dokumente eines Projekts"
    Kundenakte        Karte "Versand": die Einträge beider Projekte des Kunden, nicht die des anderen Kunden
    Mahnung           der Link der Mahnung im Versandprotokoll führt in ihre Rechnung, die Mahnung ist hervorgehoben
    Mein Konto        die Monteurin findet "Mein Konto" in der Kopfzeile von /mobil, der Link öffnet ihr Konto (412 px)
    Leistungsformular Büro – Auftrag: Bearbeiten lädt mit den Standardwerten aus der Kalkulation der Leistung, Speichern führt in den
                      Leistungskatalog; eine neue Leistung zeigt die Vorschau ohne angenommene Standardwerte mit Hinweis; Admin
                      wie bisher mit den Kalkulationsvorgaben

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_versand_im_kontext.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date, timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.catalogs import create_catalog
    from app.invoices import create_abschlag_pauschal, finalize_and_send_invoice, update_invoice_header
    from app.models import AppUser, Customer, EmailDispatch, Employee, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.reminders import create_reminder, finalize_and_send_reminder
    from app.services import create_manual_service

    heute = berlin_today()
    bea = Employee(employee_number="E-1", first_name="Bea", last_name="Büro", employee_group="angestellt", active=True)
    mia = Employee(employee_number="E-2", first_name="Mia", last_name="Monteurin", employee_group="angestellt", active=True)
    db.add_all([bea, mia]); db.flush()
    nutzer = {"buero": AppUser(username="buero", display_name="Bea Büro", role="buero_auftrag", employee_id=bea.id,
                               password_hash=k.passwort()),
              "admin": AppUser(username="admin", display_name="Ada Admin", role="admin", password_hash=k.passwort()),
              "monteurin": AppUser(username="monteurin", display_name="Mia Monteurin", role="field", employee_id=mia.id,
                                   password_hash=k.passwort())}
    kunde = Customer(name="Bauherr Versand", last_name="Versand")
    anderer = Customer(name="Andere GmbH", last_name="Andere")
    db.add_all([*nutzer.values(), kunde, anderer]); db.flush()

    def auftrag(nummer, wer):
        projekt = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=wer.id, status="angebot",
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
        return projekt, quote, load_order(db, order.id)

    def versand(art, nr, nummer):
        db.add(EmailDispatch(dispatch_key=f"klick-{art}-{nr}", message_ref=f"klick-{art}-{nr}", status="gesendet", channel="smtp",
                             document_type=art, document_id=nr, document_number=nummer, to_recipients="bauherr@example.com",
                             subject=f"{art} {nummer}"))

    p1, q1, o1 = auftrag("V-1", kunde)
    p2, q2, o2 = auftrag("V-2", kunde)
    p3, q3, o3 = auftrag("V-3", anderer)
    rechnung = create_abschlag_pauschal(db, o1, lump_sum_net=Decimal("1000"))
    update_invoice_header(db, rechnung, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 30))
    rechnung = finalize_and_send_invoice(db, rechnung)
    rechnung.due_date = heute - timedelta(days=20)
    db.commit()
    mahnung = finalize_and_send_reminder(db, create_reminder(db, rechnung))
    for art, nr, nummer in (("angebot", q1.id, q1.quote_number), ("auftrag", o1.id, o1.order_number),
                            ("rechnung", rechnung.id, rechnung.invoice_number), ("mahnung", mahnung.id, mahnung.reminder_number),
                            ("auftrag", o2.id, o2.order_number), ("auftrag", o3.id, o3.order_number)):
        versand(art, nr, nummer)
    katalog = create_catalog(db, "Klicktest", None)
    leistung = create_manual_service(
        db, catalog_id=katalog.id, service_type=None, short_text="Rinne reinigen", long_text=None, quantity=Decimal("1"), unit="Stk",
        site_time_raw=Decimal("60"), workshop_time_raw=Decimal("0"), labor_rate_override=None, material_markup_pct_override=None,
        equipment_cost=Decimal("0"), subcontractor_cost=Decimal("0"), other_cost=Decimal("0"), overhead_pct_override=None,
        risk_profit_pct_override=None, manual_sale_price=None)
    db.commit()
    return {"cookies": {n: k.cookies(u) for n, u in nutzer.items()}, "p1": p1.id, "p2": p2.id, "kunde": kunde.id,
            "katalog": katalog.id, "leistung": leistung.id, "rechnung": rechnung.id, "mahnung": mahnung.id,
            "p1_nummern": sorted([q1.quote_number, o1.order_number, rechnung.invoice_number, mahnung.reminder_number]),
            "p2_nummer": o2.order_number, "p3_nummer": o3.order_number}


_NUMMERN = "[...document.querySelectorAll('#{} .dh-doc')].map(x=>x.textContent.trim().split(' ').pop()).sort()"


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1400, 900)
    await tab.anmelden(seed["cookies"]["buero"])
    # --- Projektmappe: Reiter Versand ---
    await tab.oeffnen(f"/projects/{seed['p1']}#sec-dispatch", "document.querySelector('#projectDispatches .dh-head')")
    p.pruefe("Projektmappe: Reiter Versand aktiv", await tab.js("document.querySelector('.tab-btn.active').textContent.trim()"),
             "Versand")
    p.pruefe("Projektmappe: nur die Dokumente des Projekts", await tab.js(_NUMMERN.format("projectDispatches")), seed["p1_nummern"])
    p.pruefe("Projektmappe: Link ins gefilterte Versandprotokoll",
             await tab.js("document.querySelector('#projectDispatches .dh-head a').getAttribute('href')"),
             f"/versandprotokoll?projekt={seed['p1']}")
    p.pruefe("Projektmappe: JS-Fehler", tab.fehler, [])
    await tab.bild("projektmappe_versand")
    await tab.js("document.querySelector('#projectDispatches .dh-head a').click()")
    await tab.warten("location.pathname==='/versandprotokoll'&&document.querySelectorAll('#rows tr td').length>1")
    await tab.warte_auf_neu_geladene_liste()
    nummern = await tab.js("[...document.querySelectorAll('#rows tr')].map(r=>r.children[1].textContent.trim().split(' ').pop()).sort()")
    p.pruefe("Versandprotokoll ?projekt=: dieselben Einträge", nummern, seed["p1_nummern"])
    p.pruefe("Versandprotokoll ?projekt=: Hinweis auf den Filter",
             await tab.js("document.getElementById('docFilter').textContent.startsWith('Nur die Dokumente eines Projekts')"), True)
    # --- Mahnung: Link in ihre Rechnung ---
    href = await tab.js("[...document.querySelectorAll('#rows a.link')].find(a=>a.textContent.startsWith('Mahnung')).getAttribute('href')")
    p.pruefe("Versandprotokoll: Link der Mahnung", href, f"/invoices/{seed['rechnung']}?mahnung={seed['mahnung']}")
    await tab.js("[...document.querySelectorAll('#rows a.link')].find(a=>a.textContent.startsWith('Mahnung')).click()")
    await tab.warten(f"location.pathname==='/invoices/{seed['rechnung']}'&&!!document.querySelector('#reminderList [data-mahnung]')")
    p.pruefe("Rechnung: die Mahnung aus dem Link ist hervorgehoben",
             await tab.js("[...document.querySelectorAll('#reminderList .mahnung-markiert')].map(x=>x.dataset.mahnung)"),
             [str(seed["mahnung"])])
    p.pruefe("Rechnung: JS-Fehler", tab.fehler, [])
    await tab.bild("rechnung_mahnung_markiert")
    # --- Kundenakte: Karte Versand ---
    await tab.oeffnen(f"/customers/{seed['kunde']}", "document.querySelector('#customerDispatches .dh-head')")
    akte = await tab.js(_NUMMERN.format("customerDispatches"))
    p.pruefe("Kundenakte: beide Projekte des Kunden, nicht der andere Kunde",
             akte, sorted(seed["p1_nummern"] + [seed["p2_nummer"]]))
    p.pruefe("Kundenakte: Link ins gefilterte Versandprotokoll",
             await tab.js("document.querySelector('#customerDispatches .dh-head a').getAttribute('href')"),
             f"/versandprotokoll?kunde={seed['kunde']}")
    p.pruefe("Kundenakte: JS-Fehler", tab.fehler, [])
    await tab.js("document.getElementById('versand').scrollIntoView()")
    await tab.bild("kundenakte_versand")
    # --- Leistungsformular als Büro – Auftrag ---
    await tab.oeffnen(f"/services/{seed['leistung']}/edit",
                      "document.getElementById('heading').textContent==='Leistung bearbeiten'&&document.getElementById('calcPreview').children.length>0")
    p.pruefe("Leistung (Büro – Auftrag): Standard-Stundensatz aus der Kalkulation der Leistung",
             await tab.js("/^\\(Standard: [\\d.,]+\\s€\\/h\\)$/.test(document.getElementById('laborRateDefault').textContent)"), True)
    p.pruefe("Leistung (Büro – Auftrag): Vorschau mit Preis, ohne Hinweis",
             await tab.js("[!document.querySelector('[data-vorschau-hinweis]'),!document.getElementById('calcPreview').textContent.includes('—')]"),
             [True, True])
    p.pruefe("Leistung (Büro – Auftrag): JS-Fehler", tab.fehler, [])
    await tab.bild("leistung_bearbeiten_buero_auftrag")
    await tab.js("document.getElementById('shortText').value='Rinne reinigen (Klicktest)'")
    await tab.js("save()")
    await tab.warten("location.pathname==='/leistungskatalog'")
    p.pruefe("Leistung (Büro – Auftrag): gespeichert, zurück im Leistungskatalog", await tab.js("location.pathname"), "/leistungskatalog")
    await tab.oeffnen(f"/services/new?catalog_id={seed['katalog']}", "document.getElementById('calcPreview').children.length>0")
    p.pruefe("Neue Leistung (Büro – Auftrag): Vorschau ohne angenommene Standardwerte, mit Hinweis",
             await tab.js("[document.getElementById('laborRateDefault').textContent,!!document.querySelector('[data-vorschau-hinweis]')]"),
             ["(Standard laut Kalkulationsvorgaben)", True])
    p.pruefe("Neue Leistung (Büro – Auftrag): JS-Fehler", tab.fehler, [])
    await tab.anmelden(seed["cookies"]["admin"])
    await tab.oeffnen(f"/services/new?catalog_id={seed['katalog']}", "document.getElementById('calcPreview').children.length>0")
    p.pruefe("Neue Leistung (Admin): Standardwerte aus den Kalkulationsvorgaben",
             await tab.js("[document.getElementById('laborRateDefault').textContent.startsWith('(Standard: '),!!document.querySelector('[data-vorschau-hinweis]')]"),
             [True, False])
    p.pruefe("Neue Leistung (Admin): JS-Fehler", tab.fehler, [])
    # --- Mein Konto in der mobilen Kopfzeile ---
    await tab.anmelden(seed["cookies"]["monteurin"])
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen("/mobil", "document.querySelector('.mobile-header-account')")
    p.pruefe("/mobil: Mein Konto in der Kopfzeile", await tab.js(
        "(a=>[a.textContent.trim(),a.getAttribute('href'),a.getClientRects().length>0])(document.querySelector('.mobile-header .mobile-header-account'))"),
        ["Mein Konto", "/account", True])
    p.pruefe("/mobil: Kopfzeile ohne waagrechte Scrollleiste",
             await tab.js("document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.bild("mobil_mein_konto_412")
    await tab.js("document.querySelector('.mobile-header-account').click()")
    await tab.warten("location.pathname==='/account'&&!!document.getElementById('currentPassword')")
    p.pruefe("/mobil: Mein Konto öffnet das Konto", await tab.js("location.pathname"), "/account")
    p.pruefe("/account (Monteurin): JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
