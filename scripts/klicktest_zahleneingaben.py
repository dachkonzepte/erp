"""Klicktest: Zahleneingaben im deutschen Format, lesbare Fehler, "Festschreiben" (1.8.109, Vorgabe "Vor dem Abnahmetest" Punkte 1–4).

docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.109". Getippt wird wie von Hand (Input.insertText in das fokussierte Feld), nicht
über .value -- bis 1.8.108 machte Chrome in einem Zahlenfeld (type="number") aus "1.250" still 1,25.

    Auftrag          Nachtrag anlegen: Menge "1.250", Preis "1.250,5" -> gespeichert 1250 und 1250,5; Menge "1.25" -> Meldung am
                     Dialog ("nicht eindeutig"), nichts gespeichert, das Feld rot markiert, nach dem Korrigieren nicht mehr
    Einstellungen    Zahlungsbedingung: "Tage bis Fälligkeit" leer -> "fehlt", nichts gespeichert; "1.5" -> Meldung; ein 422 des
                     Servers (Bezeichnung zu lang) lesbar statt "[object Object]"; "30" gespeichert
    Mahnwesen        der Knopf am Entwurf heißt "Festschreiben" (kein "Versenden"); geklickt: festgeschrieben, keine E-Mail
    Plantafel        Anfahrt "1.25" -> Meldung im Dialog; "30" -> der 422 des Servers lesbar ("Anfahrt je MA / Tag ist zu groß")
    Arbeitsvorb.     "Entfernen" an einer Kolonne mit Einsatz in der Plantafel -> der Grund des Servers (409) unter den Teams

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_zahleneingaben.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date, timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.invoices import create_abschlag_pauschal, finalize_and_send_invoice, update_invoice_header
    from app.models import AppUser, Customer, Employee, Project, Quote, QuoteItem, Team, TeamEmployee
    from app.orders import create_order_from_quote, load_order
    from app.planning import create_slot
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.reminders import create_reminder

    heute = berlin_today()
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_finanzen", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Zahl", last_name="Zahl", street="Dachweg 1", postal_code="52531", city="Uebach")
    max_m = Employee(employee_number="M-1", first_name="Max", last_name="Monteur", employee_group="gewerblich", active=True)
    db.add_all([anna, bea, kunde, max_m]); db.flush()

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

    nachtrag = auftrag("Z-1")
    team = Team(name="Kolonne Nord", active=True)
    db.add(team); db.flush()
    db.add(TeamEmployee(team_id=team.id, employee_id=max_m.id)); db.flush()
    slot = create_slot(db, order_id=nachtrag.id, team_id=team.id, start_date=heute + timedelta(days=1),
                       end_date=heute + timedelta(days=3))
    db.commit()

    rechnung = create_abschlag_pauschal(db, auftrag("Z-2"), lump_sum_net=Decimal("1000"))
    update_invoice_header(db, rechnung, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 30))
    rechnung = finalize_and_send_invoice(db, rechnung)
    rechnung.due_date = heute - timedelta(days=10)
    db.commit()
    entwurf = create_reminder(db, rechnung)
    return {"auftrag": nachtrag.id, "team": team.id, "zuordnung": slot.team_assignment_id, "entwurf": entwurf.id,
            "rechnung_nr": rechnung.invoice_number,
            "cookies": {"anna": k.cookies(anna), "bea": k.cookies(bea)}}


async def _tippen(tab, feld: str, text: str) -> None:
    """Wie von Hand: Feld fokussieren, leeren, Text tippen (Input.insertText löst input-Ereignisse aus)."""
    await tab.js(f"(()=>{{const e=document.getElementById('{feld}');e.focus();e.value='';"
                 f"e.dispatchEvent(new Event('input',{{bubbles:true}}))}})()")
    if text:
        await tab.cmd("Input.insertText", text=text)


ORDER_READY = "order&&document.querySelectorAll('.lv-row').length>=1"


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1280, 1000)
    await tab.anmelden(seed["cookies"]["bea"])
    a = seed["auftrag"]

    # --- 1. Auftrag: Nachtrag mit Tausenderpunkten ---
    await tab.oeffnen(f"/orders/{a}", ORDER_READY)
    await tab.js("document.querySelector('#addendumBar button').click()")
    p.pruefe("Menge ist ein Textfeld mit Zifferntastatur und Baustein",
             await tab.js("(e=>[e.type,e.inputMode,e.hasAttribute('data-zahl')])(document.getElementById('iQty'))"),
             ["text", "decimal", True])
    await _tippen(tab, "iShort", "Kaminverblechung")
    await _tippen(tab, "iQty", "1.250")
    await _tippen(tab, "iPrice", "1.250,5")
    await tab.js("document.getElementById('iUnit').selectedIndex=1")
    await tab.bild("nachtrag_tausender")
    await tab.js("saveItemDialog()")
    p.pruefe("Nachtrag gespeichert", await tab.warten("order.items.some(i=>i.is_addendum)"), True)
    p.pruefe("Menge 1.250 = 1250, Preis 1.250,5 = 1250,5",
             await tab.js("(i=>[Number(i.quantity),Number(i.unit_price)])(order.items.find(i=>i.is_addendum))"), [1250, 1250.5])
    await tab.js("document.querySelector('#addendumBar button').click()")
    await _tippen(tab, "iShort", "Dachfenster")
    await _tippen(tab, "iQty", "1.25")
    await _tippen(tab, "iPrice", "300")
    await tab.js("document.getElementById('iUnit').selectedIndex=1")
    await tab.js("saveItemDialog()")
    await tab.warte_auf_ruhe()
    p.pruefe("Menge 1.25: Meldung am Dialog",
             await tab.js("document.getElementById('itemStatus').textContent"),
             "Fehler: Menge: „1.25“ ist nicht eindeutig – Dezimalstellen bitte mit Komma (z. B. 1,25), Tausender mit Punkt vor je "
             "drei Ziffern (z. B. 1.250).")
    p.pruefe("Menge 1.25: nichts gespeichert, Feld markiert",
             await tab.js("[order.items.filter(i=>i.is_addendum).length,document.getElementById('iQty').getAttribute('aria-invalid')]"),
             [1, "true"])
    await tab.bild("nachtrag_mehrdeutig")
    await _tippen(tab, "iQty", "1,25")
    p.pruefe("Korrigiert: Markierung weg", await tab.js("document.getElementById('iQty').getAttribute('aria-invalid')"), None)
    await tab.js("document.getElementById('itemDialog').close()")
    p.pruefe("Auftrag: JS-Fehler", tab.fehler, [])

    # --- 2. Einstellungen: Zahlungsbedingungen ---
    await tab.anmelden(seed["cookies"]["anna"])
    await tab.oeffnen("/settings#payment-terms", "typeof paymentTerms!=='undefined'&&paymentTerms.length>0")
    await tab.js("showSettingsSection('payment-terms');resetPaymentTermForm();showPaymentTermEditor()")
    vorher = await tab.js("paymentTerms.length")
    await _tippen(tab, "ptLabel", "Klicktest 30 Tage")
    await _tippen(tab, "ptDays", "")
    await tab.js("savePaymentTerm()")
    await tab.warte_auf_ruhe()
    p.pruefe("Tage leer: abgelehnt statt 0", await tab.js("document.getElementById('paymentTermStatus').textContent"),
             "Fehler: Tage bis Fälligkeit fehlt.")
    await _tippen(tab, "ptDays", "1.5")
    await tab.js("savePaymentTerm()")
    await tab.warte_auf_ruhe()
    p.pruefe("Tage 1.5: Meldung", (await tab.js("document.getElementById('paymentTermStatus').textContent")).split(" – ")[0],
             "Fehler: Tage bis Fälligkeit: „1.5“ ist nicht eindeutig")
    p.pruefe("Nichts gespeichert", await tab.js(f"paymentTerms.length==={vorher}&&!paymentTerms.some(t=>t.label==='Klicktest 30 Tage')"),
             True)
    await tab.js("document.getElementById('ptLabel').value='" + "x" * 121 + "'")
    await _tippen(tab, "ptDays", "30")
    await tab.js("savePaymentTerm()")
    p.pruefe("422 des Servers lesbar", await tab.warten(
        "document.getElementById('paymentTermStatus').textContent.startsWith('Fehler:')"), True)
    p.pruefe("422: Text", await tab.js("document.getElementById('paymentTermStatus').textContent"),
             "Fehler: Bitte die Eingabe prüfen – Bezeichnung ist zu lang.")
    await tab.bild("zahlungsbedingung_422")
    await _tippen(tab, "ptLabel", "Klicktest 30 Tage")
    await tab.js("savePaymentTerm()")
    p.pruefe("30 Tage gespeichert", await tab.warten("paymentTerms.some(t=>t.label==='Klicktest 30 Tage'&&t.days===30)"), True)
    p.pruefe("Einstellungen: JS-Fehler", tab.fehler, [])

    # --- 3. Mahnwesen: Festschreiben ---
    await tab.anmelden(seed["cookies"]["bea"])
    await tab.oeffnen("/mahnwesen", "allReminders.length>0&&document.getElementById('allRows').innerHTML.length>0")
    knoepfe = await tab.js("[...document.querySelectorAll('button')].map(b=>b.textContent.trim())"
                           ".filter(t=>t==='Festschreiben'||t==='Versenden')")
    p.pruefe("Knopf am Entwurf heißt Festschreiben, kein Versenden", [len(knoepfe) > 0, sorted(set(knoepfe))], [True, ["Festschreiben"]])
    await tab.bild("mahnwesen_festschreiben")
    await tab.js(f"document.querySelector('#allRows button[onclick=\"sendReminder({seed['entwurf']})\"]').click()")
    p.pruefe("Festgeschrieben, keine E-Mail", await tab.warten(
        f"allReminders.some(r=>r.id==={seed['entwurf']}&&r.status!=='entwurf'&&!r.email_sent_at)"), True)
    p.pruefe("Status: Festgeschrieben, noch nicht hinaus",
             await tab.js(f"!!document.querySelector('#allRows [data-status=\"festgeschrieben\"]')"), True)
    p.pruefe("Mahnwesen: JS-Fehler", tab.fehler, [])

    # --- 4. Plantafel ---
    await tab.oeffnen("/planning", "typeof board!=='undefined'&&board&&board.teams&&board.teams.length>0")
    await tab.js(f"openCreate({a},null,{seed['team']})")
    await _tippen(tab, "newTravelHours", "1.25")
    await tab.js("saveNew()")
    await tab.warte_auf_ruhe()
    p.pruefe("Anfahrt 1.25: Meldung", (await tab.js("document.getElementById('newInfo').textContent")).split(" – ")[0],
             "Fehler: Anfahrt je MA / Tag (h): „1.25“ ist nicht eindeutig")
    await _tippen(tab, "newTravelHours", "30")
    await tab.js("saveNew()")
    p.pruefe("Anfahrt 30: 422 lesbar", await tab.warten(
        "document.getElementById('newInfo').textContent.includes('Bitte die Eingabe')"), True)
    p.pruefe("Anfahrt 30: Text", await tab.js("document.getElementById('newInfo').textContent"),
             "Fehler: Bitte die Eingabe prüfen – Anfahrt je MA / Tag ist zu groß.")
    await tab.bild("plantafel_422")
    await tab.js("createDialog.close()")
    p.pruefe("Plantafel: JS-Fehler", tab.fehler, [])

    # --- 5. Arbeitsvorbereitung: Team entfernen ---
    await tab.oeffnen(f"/orders/{a}/work-preparation#team", "prep&&prep.teams.length===1")
    await tab.js(f"removeTeam({seed['zuordnung']})")
    p.pruefe("Ablehnung angezeigt", await tab.warten("document.getElementById('teamRemoveStatus').textContent.length>0"), True)
    p.pruefe("Ablehnung: Text", await tab.js("document.getElementById('teamRemoveStatus').textContent"),
             "Fehler: Diese Kolonne besitzt noch einen Einsatz in der Plantafel. Bitte den Planeinsatz dort zuerst entfernen oder "
             "umplanen.")
    p.pruefe("Team bleibt", await tab.js("prep.teams.length"), 1)
    await tab.bild("arbeitsvorbereitung_team")
    p.pruefe("Arbeitsvorbereitung: JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
