"""Klicktest: Abnahmeprotokoll als Checkliste (1.8.61, Stufe 2c-2d, Punkt 2).

Befüllt: Gewerbekunde "Hallenbau GmbH", Objekt "Halle Nord" mit den Dachflächen Nord, Süd und Alt (archiviert), Auftrag aus
einem Angebot, Beteiligte Bernd Bau (Bauleitung des Auftraggebers, Vollmacht zur Abnahme als PDF) und Petra Plan
(Architektin, ohne), die Monteurin Mia über die Arbeitsvorbereitung zugewiesen. Die Startvorlage "Abnahmeprotokoll" kommt über
die Funktion ihrer Migration und wird veröffentlicht; das Büro legt ein Protokoll am Auftrag an.

    Büro (1400 px, dunkel)  Abschnitte Befund, Erklärungen des Auftraggebers, Schluss; nichts vorausgewählt; Dachflächen als
                            Kacheln ohne die archivierte; Mangel erfasst; "Wer unterschreibt?" mit Auftraggeber, Bernd
                            ("Vollmacht zur Abnahme: ja") und Petra ("nein", Warnung beim Wählen); Auftraggeber gewählt ->
                            Person und Funktion; Vorbehalt "Nein" trotz Mangel -> abgelehnt mit Text; Vorbehalt "Ja" ->
                            unterschrieben "– unterschrieben von Herbert Halle (Geschäftsführer)"; Befund gesperrt, kein
                            "Mangel erfassen" mehr; Auftragnehmer (Konto) unterschreibt; Dachflächen als Text.
    Büro (412 px, hell)     kein waagrechter Scrollbalken.
    Editor                  Unterzeichner der beiden Systemunterschriften gesperrt "(vom Zweck vorgegeben)", Zweck "nur Büro".
    Monteurin (412 px)      Start-Auswahl ohne Abnahmeprotokoll, das Protokoll 403, /mobil ohne Abnahmeprotokoll.

`confirm()` wird automatisch bestätigt und mitgeschrieben. Unterschriften mit echten Mausereignissen. Feste Uhr 10:00 (die
Monteurin öffnet /mobil).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_abnahmeprotokoll.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_checkliste_unterschrift import CONFIRM  # noqa: E402
from klicktest_maengel import PDF  # noqa: E402
from klicktest_unterzeichner import _knopf, _zeichnen  # noqa: E402

A = "abnahme."


def _migration():
    path = next((Path(__file__).resolve().parent.parent / "alembic" / "versions").glob("*_abnahmeprotokoll_startvorlage.py"))
    spec = importlib.util.spec_from_file_location("abnahmeprotokoll_startvorlage", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def befuellen(db, k):
    from datetime import timedelta
    from decimal import Decimal

    from sqlalchemy import select

    from app.berlin_time import berlin_today
    from app.checklist_templates import publish_draft
    from app.contacts import create_contact
    from app.models import (AppUser, ChecklistTemplate, Customer, Employee, Project, Property, Quote, QuoteItem,
                            RoofArea, WorkPreparationEmployee)
    from app.orders import create_order_from_quote
    from app.project_participants import add_participant, store_power_of_attorney
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.work_preparation import ensure_preparation

    heute = berlin_today()
    ma = {key: Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group=gruppe, active=True,
                        hourly_wage=Decimal("22.00"))
          for key, nr, vor, nach, gruppe in (("mia", "E-1", "Mia", "Monteurin", "gewerblich"),
                                              ("olga", "E-2", "Olga", "Office", "angestellt"))}
    db.add_all(ma.values()); db.flush()
    benutzer = {
        "buero": AppUser(username="olga", display_name="Olga Office", role="buero_auftrag", employee_id=ma["olga"].id,
                         password_hash=k.passwort()),
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=ma["mia"].id,
                       password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Uebach")
    db.add(objekt); db.flush()
    db.add_all([RoofArea(property_id=objekt.id, name="Nord"), RoofArea(property_id=objekt.id, name="Süd"),
                RoofArea(property_id=objekt.id, name="Alt", archived=True)])
    projekt = Project(project_number="P-KT-AP", name="Dachsanierung Halle", customer_id=kunde.id, property_id=objekt.id,
                      status="angebot", pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(quote_number="A-KT-AP", project_id=projekt.id, title="Dachsanierung Halle", vat_rate=Decimal("19"))
    db.add(angebot); db.flush()
    db.add(QuoteItem(quote_id=angebot.id, position_number="1", short_text="Abdichtung", quantity=Decimal("850"),
                     unit="m²", unit_price=Decimal("48.90")))
    db.commit()
    auftrag = create_order_from_quote(db, angebot.id, order_date=heute - timedelta(days=60), execution_start=None,
                                      execution_end=None, caseworker_employee_id=None, project_manager_employee_id=None,
                                      payment_terms=None, remarks=None)
    prep = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=ma["mia"].id)); db.commit()
    bau = add_participant(db, projekt, create_contact(db, {"kind": "person", "first_name": "Bernd", "last_name": "Bau"}),
                          role="bauleitung_ag", acceptance_authorized=True)
    store_power_of_attorney(db, bau, filename="abnahmevollmacht.pdf", data=PDF, user_name="Olga Office", kind="abnahme")
    add_participant(db, projekt, create_contact(db, {"kind": "person", "first_name": "Petra", "last_name": "Plan"}),
                    role="architekt_planer")

    assert _migration().insert_acceptance_template(db.connection())
    db.commit()
    vorlage = publish_draft(db, db.scalar(select(ChecklistTemplate.id).where(ChecklistTemplate.label == "Abnahmeprotokoll")))
    return {"auftrag": auftrag.id, "vorlage": vorlage["id"],
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    bereit = "document.querySelector('#clMain .q') && !document.querySelector('#clMain').textContent.includes('Lädt')"

    # --- Büro: Protokoll anlegen -------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/orders/{seed['auftrag']}", "document.body && document.readyState==='complete'")
    await tab.js("localStorage.setItem('erp_theme','dark')")
    cid = await tab.js(
        f"fetch('/api/checklists',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify("
        f"{{template_id:{seed['vorlage']},context_type:'auftrag',order_id:{seed['auftrag']}}})}}).then(r=>r.json()).then(d=>d.id)")
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    f = await tab.js("Object.fromEntries(cl.fields.map(x=>[x.field_key.replace('abnahme.',''),x.id]))")
    feld = lambda key: f"document.getElementById('q_{f[key]}')"  # noqa: E731
    p.pruefe("Abschnitte in der Reihenfolge", await tab.js(
        "[...new Set(cl.fields.map(x=>x.group_name).filter(Boolean))]"),
        ["Befund", "Erklärungen des Auftraggebers", "Schluss"])
    p.pruefe("Nichts vorausgewählt", await tab.js(
        "document.querySelectorAll('#clMain .tile.on').length"), 0)
    await tab.warten(f"{feld('dachflaechen')}.querySelectorAll('.tile').length>0", 10)
    p.pruefe("Dachflächen ohne die archivierte", await tab.js(
        f"[...{feld('dachflaechen')}.querySelectorAll('.tile')].map(t=>t.textContent)"), ["Nord", "Süd"])

    # Befund ausfüllen
    await tab.js(f"(t=>{{t.value='Herbert Halle (Auftraggeber), Olga Office (Auftragnehmer)';t.dispatchEvent(new Event('input'))}})"
                 f"({feld('teilnehmer')}.querySelector('textarea'))")
    await tab.js(f"flushSave({f['teilnehmer']})")
    await tab.js(f"[...{feld('umfang')}.querySelectorAll('.tile')].find(t=>t.textContent==='Gesamtabnahme').click()")
    await tab.warten(f"{feld('umfang')}.querySelector('.tile.on')", 10)
    await tab.js(f"[...{feld('dachflaechen')}.querySelectorAll('.tile')].find(t=>t.textContent==='Nord').click()")
    await tab.warten(f"{feld('dachflaechen')}.querySelector('.tile.on')", 10)
    await tab.warten(f"document.getElementById('pdefList_{f['maengel']}') && !document.getElementById('pdefList_{f['maengel']}').textContent.includes('Lädt')", 10)
    await tab.js(f"document.getElementById('pdefDesc_{f['maengel']}').value='Attika West undicht';"
                 f"document.getElementById('pdefSave_{f['maengel']}').click()")
    await tab.warten(f"document.querySelectorAll('#pdefList_{f['maengel']} .pdef').length===1", 15)
    await tab.js(f"[...{feld('ergebnis')}.querySelectorAll('.tile')].find(t=>t.textContent==='Abnahme erklärt').click()")
    await tab.warten(f"{feld('ergebnis')}.querySelector('.tile.on')", 10)
    for key, wert in (("vorbehalt_maengel", "Nein"), ("vorbehalt_vertragsstrafe", "Nein")):
        await tab.js(f"[...{feld(key)}.querySelectorAll('.tile')].find(t=>t.textContent==={wert!r}).click()")
        await tab.warten(f"{feld(key)}.querySelector('.tile.on')", 10)

    # Wer unterschreibt?
    ag = f["unterschrift_auftraggeber"]
    p.pruefe("Wer unterschreibt: Auftraggeber und Beteiligte mit Vollmacht-Angabe", await tab.js(
        f"[...document.getElementById('padWho_{ag}').options].map(o=>o.textContent)"),
        ["– Wer unterschreibt? –", "Hallenbau GmbH (Auftraggeber laut Auftrag)",
         "Bernd Bau (Bauleitung des Auftraggebers) · Vollmacht zur Abnahme: ja",
         "Petra Plan (Architekt/Planer) · Vollmacht zur Abnahme: nein"])
    await tab.js(f"(s=>{{s.selectedIndex=3;s.dispatchEvent(new Event('change'))}})(document.getElementById('padWho_{ag}'))")
    p.pruefe("Petra gewählt: Warnung, keine Personenfelder", await tab.js(
        f"[document.getElementById('padPoa_{ag}').hidden, document.getElementById('padAg_{ag}').hidden]"), [False, True])
    await tab.js(f"(s=>{{s.selectedIndex=1;s.dispatchEvent(new Event('change'))}})(document.getElementById('padWho_{ag}'))")
    p.pruefe("Auftraggeber gewählt: Person und Funktion, keine Warnung", await tab.js(
        f"[document.getElementById('padPoa_{ag}').hidden, document.getElementById('padAg_{ag}').hidden, "
        f"document.getElementById('padPerson_{ag}').value]"), [True, False, ""])
    await tab.js(f"document.getElementById('padPerson_{ag}').value='Herbert Halle';"
                 f"document.getElementById('padFunction_{ag}').value='Geschäftsführer'")
    await _zeichnen(tab, ag)
    await tab.js(_knopf(ag))
    await tab.warten(f"document.getElementById('st_{ag}').classList.contains('err')", 15)
    p.pruefe("Mangel ohne Vorbehalt: abgelehnt mit Text", await tab.js(
        f"document.getElementById('st_{ag}').textContent.includes('aber kein Vorbehalt wegen Mängeln')"), True)
    await tab.js(f"[...{feld('vorbehalt_maengel')}.querySelectorAll('.tile')].find(t=>t.textContent==='Ja').click()")
    await tab.warten(f"[...{feld('vorbehalt_maengel')}.querySelectorAll('.tile.on')].some(t=>t.textContent==='Ja')", 10)
    await tab.js(_knopf(ag))
    await tab.warten(f"document.querySelectorAll('#q_{ag} .sig').length===1", 15)
    p.pruefe("Unterschrieben: Auftraggeber mit Person", await tab.js(
        f"document.querySelector('#q_{ag} .sig').innerText.split('\\n').slice(0,2).join(' | ')"),
        "Hallenbau GmbH | Unterzeichner: Auftraggeber laut Auftrag – unterschrieben von Herbert Halle (Geschäftsführer)")
    p.pruefe("Befund gesperrt: Dachflächen als Text, kein Mangel-Formular", await tab.js(
        f"[{feld('dachflaechen')}.querySelector('.q-body').innerText.trim(), !document.getElementById('pdefForm_{f['maengel']}')]"),
        ["Nord", True])
    an = f["unterschrift_auftragnehmer"]
    await _zeichnen(tab, an)
    await tab.js(_knopf(an))
    await tab.warten(f"document.querySelectorAll('#q_{an} .sig').length===1", 15)
    p.pruefe("Auftragnehmer: angemeldetes Konto", await tab.js(
        f"document.querySelector('#q_{an} .sig').innerText.split('\\n').slice(0,2).join(' | ')"),
        "Olga Office | Unterzeichner: angemeldetes Konto")
    p.pruefe("Beide Unterschriften: Inhalt unverändert", await tab.js(
        f"fetch('/api/checklists/{cid}').then(r=>r.json()).then(d=>d.attachments.filter(a=>a.kind==='unterschrift').map(a=>a.seal.status))"),
        ["unveraendert", "unveraendert"])
    p.pruefe("Büro: keine JS-Fehler", tab.fehler, [])
    await tab.js(f"{feld('ergebnis')}.scrollIntoView()")
    await tab.bild("1_buero_protokoll_dunkel")

    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    p.pruefe("412 px: kein waagrechter Scrollbalken", await tab.js(
        "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.bild("2_buero_protokoll_412_hell")

    # --- Editor ---------------------------------------------------------------------------------------------------
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/checklisten/vorlagen/{seed['vorlage']}", "document.getElementById('purposeHint')")
    await tab.warten("document.getElementById('purposeHint').textContent.length>0", 10)
    p.pruefe("Editor: Zweck nur Büro", await tab.js(
        "document.getElementById('purposeHint').textContent.includes('nur Büro')"), True)
    ids = await tab.js("version.fields.filter(x=>x.field_type==='unterschrift').map(x=>x.id)")
    stand = []
    for fid in ids:
        await tab.js(f"toggleField({fid})")
        await tab.warten(f"document.querySelector('#frow_{fid} .frow-body select[data-k=\"signer_mode\"]')", 10)
        stand.append(await tab.js(
            f"(s=>[s.closest('.field').querySelector('label').textContent, s.value, s.disabled])"
            f"(document.querySelector('#frow_{fid} .frow-body select[data-k=\"signer_mode\"]'))"))
    p.pruefe("Editor: Unterzeichner vom Zweck vorgegeben", stand, [
        ["Unterzeichner (vom Zweck vorgegeben)", "ag_oder_beteiligter", True],
        ["Unterzeichner (vom Zweck vorgegeben)", "konto", True]])
    await tab.bild("2b_editor_unterzeichner")

    # --- Monteurin ---------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen("/mobil", "document.body && document.readyState==='complete'")
    p.pruefe("Monteurin: Start-Auswahl ohne Abnahmeprotokoll, Protokoll 403", [
        await tab.js("fetch('/api/checklists/startable-templates?context=auftrag').then(r=>r.json()).then(l=>l.map(t=>t.label))"),
        await tab.js(f"fetch('/api/checklists/{cid}').then(r=>r.status)"),
        await tab.js(f"fetch('/api/checklists?order_id={seed['auftrag']}').then(r=>r.json()).then(l=>l.length)")],
        [[], 403, 0])
    p.pruefe("Monteurin: /mobil nennt kein Abnahmeprotokoll", await tab.js(
        "document.body.innerText.includes('Abnahmeprotokoll')"), False)
    p.pruefe("Monteurin: keine JS-Fehler", tab.fehler, [])
    await tab.bild("3_monteurin_mobil")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
