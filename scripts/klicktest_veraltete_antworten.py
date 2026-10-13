"""Klicktest: veraltete Antworten (1.8.95, Baustein app/templates/_speichern.html, Vorgabe 1.8.95 Punkt 1).

Je Seite wird eine Antwort gezielt zurückgehalten (Tab.zurueckhalten() in scripts/cdp_klicktest.py: der Server hat sie schon
bearbeitet, die Seite bekommt sie erst später) -- geprüft wird, dass sie nichts überschreibt, was danach schon angewandt ist, und
dass der Erfolgstext erst nach dem Anwenden erscheint:

    Checkliste      (Monteurin, 412 px) Feld "Ende der Arbeiten" per blur, die Antwort hält zurück; sofort danach die Kachel
                    "Nachkontrolle ohne Befund": sie geht erst nach der Antwort des Felds hinaus, beide Felder "Speichert …";
                    nach der Freigabe beide gespeichert, "Vor der Unterschrift fehlen noch" weg (Nebenbefund 1 aus 1.8.94)
    Abnahme         (Auftragsseite) Abnahme A verwerfen, das Neuladen der Abnahmen hält zurück: noch kein "Abnahme verworfen.";
                    Abnahme B verwerfen (lädt neu); das späte Neuladen von A überschreibt nicht -- beide verworfen
    Mahnung         (Rechnungsseite) Zahlungsfrist 10 Tage speichern, das Neuladen der Mahnungen hält zurück: kein
                    "Gespeichert."; erneut mit 20 Tagen -- es bleibt bei 20; ebenso im Mahnwesen mit 30 und 40 Tagen
    Einstellungen   Aufgabenspalte umbenennen, das Neuladen der Spalten hält zurück; neue Spalte anlegen -- das späte Neuladen
                    löscht sie nicht aus der Liste; Nummernkreis speichern, das Neuladen hält zurück: "Gespeichert. Nächste Vorschau …"
                    erst danach

`confirm()` und `alert()` werden auf jeder Seite automatisch bestätigt und mitgeschrieben. Feste Uhr 10:00.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_veraltete_antworten.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

DIALOGE = ("window.__confirms=[];window.confirm=m=>{window.__confirms.push(String(m));return true};"
           "window.__alerts=[];window.alert=m=>{window.__alerts.push(String(m))};")
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def befuellen(db, k):
    from datetime import date, timedelta
    from decimal import Decimal

    from app.acceptances import create_acceptance
    from app.berlin_time import berlin_today
    from app.checklist_templates import add_field, create_template, publish_draft
    from app.checklists import create_checklist
    from app.invoices import create_abschlag_pauschal, finalize_and_send_invoice, update_invoice_header
    from app.models import AppUser, Customer, Employee, Order, Project, Quote, QuoteItem, WorkPreparationEmployee
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.reminders import create_reminder
    from app.work_preparation import ensure_preparation

    heute = berlin_today()
    mia_ma = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True,
                      hourly_wage=Decimal("22.00"))
    db.add(mia_ma); db.flush()
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    mia = AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia_ma.id, password_hash=k.passwort())
    kunde = Customer(name="Bauherr Stand", last_name="Stand", street="Dachweg 1", postal_code="52531", city="Uebach",
                     email="stand@example.com")
    db.add_all([anna, mia, kunde]); db.flush()

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

    # Checkliste am Auftrag 1, Monteurin eingeplant
    a1 = auftrag("V-1")
    prep = ensure_preparation(db, a1.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=mia_ma.id)); db.commit()
    t = create_template(db, label="Nachkontrolle", contexts=["auftrag"])
    for spec in (
        {"field_type": "text", "label": "Ende der Arbeiten", "field_key": "ende", "required": True},
        {"field_type": "ja_nein", "label": "Nachkontrolle ohne Befund", "field_key": "befund", "required": True},
        {"field_type": "unterschrift", "label": "Unterschrift Brandwache", "field_key": "sig", "signer_label": "Brandwache"},
    ):
        add_field(db, t["draft_version_id"], spec)
    vorlage = publish_draft(db, t["id"])
    cl = create_checklist(db, template_id=vorlage["id"], context_type="auftrag", order_id=a1.id,
                          created_by_employee_id=mia_ma.id, created_by_user_id=mia.id)
    felder = {f["field_key"]: f["id"] for f in cl["fields"]}

    # Zwei Abnahmen am Auftrag 2
    a2 = auftrag("V-2")
    abnahmen = []
    for tage in (10, 5):
        daten = {"kind": "foermlich", "accepted_on": heute - timedelta(days=tage), "scope": "gesamt", "result": "abgenommen",
                 "reservation_defects": False, "reservation_penalty": False, "declared_by": "auftraggeber", "roof_area_ids": []}
        abnahmen.append(create_acceptance(db, db.get(Order, a2.id), daten, [("beleg.pdf", PDF)], user_id=anna.id,
                                          user_name="Anna Admin").id)

    # Überfällige Rechnung mit Mahnungsentwurf am Auftrag 3
    invoice = create_abschlag_pauschal(db, auftrag("V-3"), lump_sum_net=Decimal("1000"))
    update_invoice_header(db, invoice, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 30))
    invoice = finalize_and_send_invoice(db, invoice)
    invoice.due_date = heute - timedelta(days=10)
    db.commit()
    mahnung = create_reminder(db, invoice)

    return {"checklist": cl["id"], "fields": felder, "order": a2.id, "acceptances": abnahmen, "invoice": invoice.id,
            "reminder": mahnung.id,
            "frist": {str(n): (heute + timedelta(days=n)).strftime("%d.%m.%Y") for n in (10, 20, 30, 40)},
            "cookies": {"anna": k.cookies(anna), "mia": k.cookies(mia)}}


async def _checkliste(tab, seed, p):
    cid, f = seed["checklist"], seed["fields"]
    api = f"/api/checklists/{cid}"
    hinweis = f"(e=>e&&!e.hidden?e.textContent:null)(document.querySelector('[data-missing-before=\"{f['sig']}\"]'))"
    status = lambda key: f"document.getElementById('st_{f[key]}').textContent"  # noqa: E731
    gesendet = lambda key: f"performance.getEntriesByType('resource').filter(e=>e.name.endsWith('/answers/{f[key]}')).length"  # noqa: E731
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/checklisten/{cid}", "document.querySelector('#clMain .q')")
    p.pruefe("Checkliste: Hinweis vorher nennt beide", await tab.js(hinweis),
             "Vor der Unterschrift fehlen noch: Ende der Arbeiten, Nachkontrolle ohne Befund.")

    await tab.zurueckhalten(f"/answers/{f['ende']}$", "PUT")
    await tab.js(f"(()=>{{const el=document.querySelector('#q_{f['ende']} input');el.value='16:30';"
                 "el.dispatchEvent(new Event('input'));el.dispatchEvent(new Event('blur'))})()")
    await tab.warte_bis_gehalten(1)
    await tab.js(f"document.querySelector('#q_{f['befund']} .tile').click()")
    await tab.warten("false", 0.8)  # Zeit, in der eine nicht wartende Seite die Kachel schon gespeichert hätte
    p.pruefe("Checkliste: Kachel wartet auf die Antwort des Felds (nicht gesendet)", await tab.js(gesendet("befund")), 0)
    p.pruefe("Checkliste: beide Felder 'Speichert …', nichts 'Gespeichert'", [await tab.js(status("ende")), await tab.js(status("befund"))],
             ["Speichert …", "Speichert …"])

    await tab.freigeben()
    await tab.warte_auf_ruhe()
    p.pruefe("Checkliste: nach der Freigabe beide gespeichert", [await tab.js(status("ende")), await tab.js(status("befund"))],
             ["Gespeichert", "Gespeichert"])
    p.pruefe("Checkliste: Kachel markiert", await tab.js(f"!!document.querySelector('#q_{f['befund']} .tile.on')"), True)
    p.pruefe("Checkliste: Hinweis weg (keine ältere Antwort übernommen)", await tab.js(hinweis), None)
    p.pruefe("Checkliste: Stand der Seite = Server", await tab.js(
        f"fetch('{api}').then(r=>r.json()).then(d=>[d.answers['{f['ende']}']?.value,d.answers['{f['befund']}']?.value,"
        f"cl.answers['{f['ende']}']?.value,cl.answers['{f['befund']}']?.value])"), ["16:30", "ja", "16:30", "ja"])
    p.pruefe("Checkliste: JS-Fehler", tab.fehler, [])
    await tab.bild("checkliste_nach_freigabe")


async def _abnahme(tab, seed, p):
    oid, (a, b) = seed["order"], seed["acceptances"]
    status = "document.getElementById('acceptanceStatus').textContent"
    verworfen = "[...document.querySelectorAll('#acceptanceList [data-acceptance]')].map(x=>[Number(x.dataset.acceptance),x.classList.contains('discarded')])"

    async def verwerfen(acc_id):
        await tab.js(f"showDiscard({acc_id});document.getElementById('accDiscardReason{acc_id}').value='falsch erfasst ({acc_id})';"
                     f"document.querySelector('#accDiscard{acc_id} button.danger').click()")

    await tab.oeffnen(f"/orders/{oid}", "document.querySelectorAll('#acceptanceList [data-acceptance]').length===2")
    await tab.warte_auf_neu_geladene_liste()
    await tab.zurueckhalten(rf"/api/orders/{oid}/acceptances$", "GET")
    await verwerfen(a)
    await tab.warte_bis_gehalten(1)
    await tab.warte_auf_ruhe()
    p.pruefe("Abnahme: Neuladen zurückgehalten -- noch kein 'Abnahme verworfen.'", await tab.js(status), "")
    await verwerfen(b)
    await tab.warten(f"{status}==='Abnahme verworfen.'", 10)
    await tab.warte_auf_ruhe()
    p.pruefe("Abnahme: nach B beide verworfen", sorted(await tab.js(verworfen)), sorted([[a, True], [b, True]]))
    await tab.freigeben()
    await tab.warte_auf_ruhe()
    p.pruefe("Abnahme: spätes Neuladen von A überschreibt nicht", sorted(await tab.js(verworfen)), sorted([[a, True], [b, True]]))
    p.pruefe("Abnahme: Text nach dem Anwenden", await tab.js(status), "Abnahme verworfen.")
    p.pruefe("Abnahme: JS-Fehler", tab.fehler, [])
    await tab.js("document.getElementById('acceptanceList').scrollIntoView({block:'center'})")
    await tab.bild("abnahme_nach_freigabe")


async def _mahnung_rechnung(tab, seed, p):
    iid, rid, frist = seed["invoice"], seed["reminder"], seed["frist"]
    status = "document.getElementById('reminderStatusMsg').textContent"
    tage = "currentReminders.map(r=>r.payment_days)"

    async def speichern_mit(tage_zahl):
        await tab.js(f"editReminderNow({rid});document.getElementById('reminderEditorPaymentDays').value='{tage_zahl}';"
                     "void saveReminderEditNow()")

    await tab.oeffnen(f"/invoices/{iid}", "invoice&&document.querySelectorAll('#reminderList > div').length===1")
    await tab.warte_auf_neu_geladene_liste()
    await tab.zurueckhalten(rf"/api/invoices/{iid}/reminders$", "GET")
    await speichern_mit(10)
    await tab.warte_bis_gehalten(1)
    await tab.warte_auf_ruhe()
    p.pruefe("Mahnung (Rechnung): Neuladen zurückgehalten -- kein 'Gespeichert.'", await tab.js(status), "")
    await speichern_mit(20)
    await tab.warten(f"{status}==='Gespeichert.'", 10)
    await tab.warte_auf_ruhe()
    p.pruefe("Mahnung (Rechnung): nach dem zweiten Speichern 20 Tage", [await tab.js(tage),
             await tab.js(f"document.getElementById('reminderList').textContent.includes('{frist["20"]}')")], [[20], True])
    await tab.freigeben()
    await tab.warte_auf_ruhe()
    p.pruefe("Mahnung (Rechnung): spätes Neuladen überschreibt nicht", [await tab.js(tage),
             await tab.js(f"document.getElementById('reminderList').textContent.includes('{frist["20"]}')"),
             await tab.js(f"document.getElementById('reminderList').textContent.includes('{frist["10"]}')")], [[20], True, False])
    p.pruefe("Mahnung (Rechnung): JS-Fehler", tab.fehler, [])
    await tab.js("document.getElementById('reminderList').scrollIntoView({block:'center'})")
    await tab.bild("mahnung_rechnung_nach_freigabe")


async def _mahnung_mahnwesen(tab, seed, p):
    rid, frist = seed["reminder"], seed["frist"]
    tage = f"allReminders.filter(r=>r.id==={rid}).map(r=>r.payment_days)"

    async def speichern_mit(tage_zahl):
        await tab.js(f"editReminder({rid});document.getElementById('editorPaymentDays').value='{tage_zahl}';void saveReminderEdit()")

    await tab.oeffnen("/mahnwesen", "document.getElementById('allRows').innerHTML.length>0")
    await tab.warte_auf_neu_geladene_liste()
    await tab.zurueckhalten(r"/api/reminders$", "GET")
    await speichern_mit(30)
    await tab.warte_bis_gehalten(1)
    await tab.warte_auf_ruhe()
    p.pruefe("Mahnwesen: Editor bleibt offen, bis neu geladen ist", await tab.js("document.getElementById('editorCard').style.display"), "block")
    await speichern_mit(40)
    await tab.warten(f"{tage}[0]===40", 10)
    await tab.warte_auf_ruhe()
    await tab.freigeben()
    await tab.warte_auf_ruhe()
    p.pruefe("Mahnwesen: spätes Neuladen überschreibt nicht", await tab.js(tage), [40])
    p.pruefe("Mahnwesen: Editor danach zu", await tab.js("document.getElementById('editorCard').style.display"), "none")
    p.pruefe("Mahnwesen: wieder geöffnet zeigt der Editor 40 Tage und die Frist dazu", await tab.js(
        f"(()=>{{editReminder({rid});const r=[document.getElementById('editorPaymentDays').value,"
        f"document.getElementById('editorDatesHint').textContent.includes('{frist['40']}')];cancelEditReminder();return r}})()"),
        ["40", True])
    p.pruefe("Mahnwesen: JS-Fehler", tab.fehler, [])


async def _einstellungen(tab, seed, p):
    spalten = "[...document.querySelectorAll('#taskColumnRows input:not([type=checkbox])')].map(x=>x.value)"
    await tab.oeffnen("/settings", "document.querySelectorAll('#taskColumnRows input:not([type=checkbox])').length>0")
    await tab.warte_auf_neu_geladene_liste()
    vorher = await tab.js(spalten)
    await tab.zurueckhalten(r"/api/task-columns$", "GET")
    await tab.js("(()=>{const el=document.querySelector('#taskColumnRows input:not([type=checkbox])');"
                 "el.value='Eingang (umbenannt)';el.dispatchEvent(new Event('blur'))})()")
    await tab.warte_bis_gehalten(1)
    await tab.js("document.getElementById('newTaskColumnLabel').value='Neue Spalte';void addTaskColumn()")
    await tab.warten(f"{spalten}.includes('Neue Spalte')", 10)
    await tab.warte_auf_ruhe()
    erwartet = ["Eingang (umbenannt)"] + vorher[1:] + ["Neue Spalte"]
    p.pruefe("Einstellungen: nach dem Anlegen umbenannt und neue Spalte", await tab.js(spalten), erwartet)
    await tab.freigeben()
    await tab.warte_auf_ruhe()
    p.pruefe("Einstellungen: spätes Neuladen nach dem Umbenennen löscht die neue Spalte nicht", await tab.js(spalten), erwartet)

    # Nummernkreis: "Gespeichert. Nächste Vorschau: …" erst nach dem Neuladen (bis 1.8.94 davor, danach von load() gelöscht)
    erste = "document.querySelector('.sequence')"
    status = f"{erste}.querySelector('.seqStatus').textContent"
    await tab.zurueckhalten(r"/api/settings/number-sequences$", "GET")
    await tab.js(f"(()=>{{const r={erste};r.querySelector('.next').value='5';void saveSequence(r.dataset.key)}})()")
    await tab.warte_bis_gehalten(1)
    await tab.warte_auf_ruhe()
    p.pruefe("Einstellungen: Nummernkreis -- Neuladen zurückgehalten, noch kein 'Gespeichert'",
             (await tab.js(status)).startswith("Gespeichert"), False)
    await tab.freigeben()
    await tab.warte_auf_ruhe()
    p.pruefe("Einstellungen: Nummernkreis -- nach dem Anwenden 'Gespeichert. Nächste Vorschau', neuer Stand",
             [(await tab.js(status)).startswith("Gespeichert. Nächste Vorschau:"), await tab.js(f"{erste}.querySelector('.next').value")],
             [True, "5"])
    p.pruefe("Einstellungen: JS-Fehler", tab.fehler, [])
    await tab.js("document.getElementById('taskColumnRows').scrollIntoView({block:'center'})")
    await tab.bild("einstellungen_aufgabenspalten")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=DIALOGE)
    await _checkliste(tab, seed, p)
    await tab.anmelden(seed["cookies"]["anna"])
    await tab.fenster(1400, 1000)
    await _abnahme(tab, seed, p)
    await _mahnung_rechnung(tab, seed, p)
    await _mahnung_mahnwesen(tab, seed, p)
    await _einstellungen(tab, seed, p)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
