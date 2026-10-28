"""Klicktest: Eingaben bleiben beim Neuzeichnen stehen (1.9.116, Stufe 5, R1, Punkt 6, Befund E2/E4).

    Rechnung (Entwurf, pauschaler Abschlag)  Einleitung, Schlusstext, Schlusstext 2 getippt, nicht gespeichert -> Leistungszeitraum ändern (die Seite
                                             zeichnet neu) -> die Texte stehen noch; „Kopfdaten speichern“ -> gespeichert, Stand vom Server
    Rechnung (Pauschalbetrag)                Bezeichnung und Betrag getippt -> Zahlungsbedingung wechseln -> stehen noch
    Rechnung (festgeschrieben)               An/CC getippt -> Leistung nachladen (reload()) -> stehen noch
    Einsatzbericht, Schritt 5                Namen getippt, beide Unterschriften gezeichnet -> Schritt „Arbeiten“ und zurück -> Namen und Unterschriften
                                             noch da („Bericht abschließen“ frei); angefangener „Befund ohne Prüfpunkt“ mit Text und Wiedervorlage ->
                                             Schritt wechseln und zurück -> Text und Datum noch da
    Bilder                                   rechnung_eingaben_nach_neuzeichnen, bericht_unterschriften_nach_schrittwechsel

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_eingaben_bleiben.py [--app-port N] [--cdp-port N]
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

    from app.invoices import create_abschlag_pauschal, finalize_and_send_invoice, update_invoice_header
    from app.models import (AppUser, Customer, Employee, PaymentTerm, Project, Quote, QuoteItem, Team, WorkPreparationTeamAssignment,
                            WorkPreparationTeamEmployee)
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.service_reports import create_report
    from app.work_preparation import ensure_preparation

    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", hourly_wage=Decimal("30"),
                   weekly_hours=Decimal("40"), active=True)
    kunde = Customer(name="Bauherr Eingabe", last_name="Eingabe", city="Uebach", email="eingabe@example.com")
    zweite = PaymentTerm(label="30 Tage netto", days=30)
    db.add_all([mia, kunde, zweite]); db.flush()
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    monteurin = AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id, password_hash=k.passwort())
    db.add_all([fin, monteurin]); db.flush()
    projekt = Project(project_number="P-E-1", name="Dach Eingabe", customer_id=kunde.id, status="angebot",
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    quote = Quote(quote_number="A-E-1", project_id=projekt.id, title="Sanierung", vat_rate=Decimal("19"))
    db.add(quote); db.flush()
    db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2", unit_price=Decimal("50")))
    db.commit()
    order = create_order_from_quote(db, quote.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
                                    caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    entwurf = create_abschlag_pauschal(db, load_order(db, order.id), lump_sum_net=Decimal("100"))
    fest = create_abschlag_pauschal(db, load_order(db, order.id), lump_sum_net=Decimal("200"))
    update_invoice_header(db, fest, service_period_start=date(2026, 9, 1), service_period_end=date(2026, 9, 30))
    fest = finalize_and_send_invoice(db, fest)
    prep = ensure_preparation(db, order.id)
    team = Team(name="Kolonne 1"); db.add(team); db.flush()
    zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
    db.add(zuordnung); db.flush()
    db.add(WorkPreparationTeamEmployee(assignment_id=zuordnung.id, employee_id=mia.id, employee_name_snapshot="Mia Monteurin"))
    db.commit()
    bericht = create_report(db, order.id, report_type="rapport", description="Kehle erneuert", created_by_employee_id=mia.id)
    return {"entwurf": entwurf.id, "fest": fest.id, "bericht": bericht["id"], "zahlung": zweite.id,
            "cookies": {"fin": k.cookies(fin), "mia": k.cookies(monteurin)}}


INVOICE_READY = "invoice&&document.getElementById('statusInfo').textContent.length>0"
BEREIT = "document.getElementById('raster')&&!document.getElementById('raster').hidden&&typeof SCHRITT!=='undefined'&&SCHRITT"


async def _tippen(tab, feld, wert):
    await tab.js(f"(()=>{{const f=document.getElementById('{feld}');f.focus();f.value={json.dumps(wert)};f.dispatchEvent(new Event('input',{{bubbles:true}}));f.blur()}})()")


async def _werte(tab, felder):
    return await tab.js("[" + ",".join(f"document.getElementById('{f}').value" for f in felder) + "]")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1440, 900)
    await tab.anmelden(seed["cookies"]["fin"])

    # --- Rechnung: Texte über ein Neuzeichnen ---
    await tab.oeffnen(f"/invoices/{seed['entwurf']}", INVOICE_READY)
    for feld, wert in (("iIntro", "Neue Einleitung"), ("iOutro", "Neuer Schluss"), ("iOutro2", "Zweiter Block"), ("pDesc", "1. Abschlag Dach"),
                       ("pAmount", "150,00")):
        await _tippen(tab, feld, wert)
    await tab.warte_auf_neu_geladene_liste("(()=>{const f=document.getElementById('iPeriodStart');f.value='2026-09-01';f.dispatchEvent(new Event('change'))})()")
    p.pruefe("Rechnung: neu gezeichnet (Leistungszeitraum gespeichert)", await tab.js("invoice.service_period_start"), "2026-09-01")
    p.pruefe("Rechnung: getippte Texte und Pauschale stehen noch", await _werte(tab, ["iIntro", "iOutro", "iOutro2", "pDesc", "pAmount"]),
             ["Neue Einleitung", "Neuer Schluss", "Zweiter Block", "1. Abschlag Dach", "150,00"])
    await tab.warte_auf_neu_geladene_liste(f"(()=>{{const s=document.getElementById('iPaymentTermSelect');s.value='{seed['zahlung']}';"
                                           "s.dispatchEvent(new Event('change'))})()")
    p.pruefe("Rechnung: nach Zahlungsbedingung stehen sie noch", await _werte(tab, ["iIntro", "pAmount"]), ["Neue Einleitung", "150,00"])
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.bild("rechnung_eingaben_nach_neuzeichnen")
    await tab.js("saveHeader()")
    p.pruefe("Kopfdaten gespeichert: Stand vom Server", await tab.warten("invoice.intro_text==='Neue Einleitung'&&invoice.outro_text_2==='Zweiter Block'"),
             True)
    await tab.js("savePauschal()")
    p.pruefe("Pauschale gespeichert", await tab.warten("Number(invoice.lump_sum_net)===150&&invoice.progress_description==='1. Abschlag Dach'"), True)

    # --- festgeschrieben: An/CC über ein Neuladen ---
    await tab.oeffnen(f"/invoices/{seed['fest']}", INVOICE_READY + "&&document.getElementById('invoiceEmailInput')")
    await _tippen(tab, "invoiceEmailInput", "buchhaltung@example.com")
    await _tippen(tab, "invoiceCcInput", "chef@example.com")
    await tab.warte_auf_neu_geladene_liste("reload()")
    p.pruefe("An/CC stehen nach dem Neuzeichnen noch", await _werte(tab, ["invoiceEmailInput", "invoiceCcInput"]),
             ["buchhaltung@example.com", "chef@example.com"])
    p.pruefe("JS-Fehler (Rechnung)", tab.fehler, [])

    # --- Einsatzbericht: Unterschriften und Namen über den Schrittwechsel, angefangener Befund ---
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(1280, 900)
    await tab.oeffnen(f"/service-reports/{seed['bericht']}#befunde", BEREIT + "&&SCHRITT==='befunde'")
    await _tippen(tab, "befund-text-frei", "Ziegel locker")
    await tab.js("(()=>{const s=document.getElementById('befund-massnahme-frei');s.value='zurueckgestellt';s.dispatchEvent(new Event('change',{bubbles:true}))})()")
    await tab.js("(()=>{const d=document.getElementById('befund-wiedervorlage-frei');d.value='2026-11-15';d.dispatchEvent(new Event('change',{bubbles:true}))})()")
    await tab.js("document.querySelector('[data-klick=\"schritt\"][data-schritt=\"material\"]').click()")
    await tab.warten("SCHRITT==='material'")
    await tab.js("document.querySelector('[data-klick=\"schritt\"][data-schritt=\"befunde\"]').click()")
    await tab.warten("SCHRITT==='befunde'&&!!document.getElementById('befund-text-frei')")
    p.pruefe("Befund ohne Prüfpunkt: Text, Maßnahme, Wiedervorlage noch da", await tab.js(
        "[document.getElementById('befund-text-frei').value,document.getElementById('befund-massnahme-frei').value,"
        "document.getElementById('befund-wiedervorlage-frei').value,document.getElementById('befund-wiedervorlage-frei').hidden]"),
        ["Ziegel locker", "zurueckgestellt", "2026-11-15", False])
    await tab.js("document.querySelector('[data-klick=\"schritt\"][data-schritt=\"unterschrift\"]').click()")
    await tab.warten("SCHRITT==='unterschrift'&&!!document.getElementById('padMonteur')")
    await _tippen(tab, "signMonteurName", "Mia Monteurin")
    await _tippen(tab, "signKundeName", "Karl Kunde")
    p.pruefe("Unterschrift Monteur gezeichnet", await tab.strich("document.getElementById('padMonteur')"), True)
    p.pruefe("Unterschrift Kunde gezeichnet", await tab.strich("document.getElementById('padKunde')"), True)
    await tab.js("document.querySelector('[data-klick=\"schritt\"][data-schritt=\"arbeiten\"]').click()")
    await tab.warten("SCHRITT==='arbeiten'")
    await tab.js("document.querySelector('[data-klick=\"schritt\"][data-schritt=\"unterschrift\"]').click()")
    await tab.warten("SCHRITT==='unterschrift'&&!!document.getElementById('padMonteur')")
    p.pruefe("nach dem Schrittwechsel: Namen und Unterschriften noch da", await tab.js(
        "[document.getElementById('signMonteurName').value,document.getElementById('signKundeName').value,!PAD_MONTEUR.leer(),!PAD_KUNDE.leer(),"
        "fehlt().filter(f=>!f.includes('Noch offen'))]"), ["Mia Monteurin", "Karl Kunde", True, True, []])
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.bild("bericht_unterschriften_nach_schrittwechsel")
    p.pruefe("JS-Fehler (Bericht)", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
