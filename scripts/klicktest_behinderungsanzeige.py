"""Klicktest: Behinderungsanzeige erfassen (1.8.38, Stufe 2b, Runde 2b-3 Teil 1).

Die Instanz entsteht per create_all() ohne Alembic -- die Startvorlagen kommen deshalb im Befüllen
über die Funktionen der Migrationen selbst (349704eab07d: 13 Startvorlagen, d6ac03a06d6f:
Behinderungsanzeige und Tagesbericht-Regel mit Link), veröffentlicht wie vom Büro.

    Monteurin (412 px, hell)  am Auftrag "Behinderungsanzeige" starten; drei Abschnitte; Abschnitt
                              Anzeige gesperrt ("füllt das Büro aus", keine Zeichenfläche für
                              "Unterschrift Büro"); Meldung ausfüllen und unterschreiben -- danach
                              gesperrt; Folgen-Endpunkt 403; kein waagrechter Scrollbalken.
    Büro (1400 px, dunkel)    Karte "Folgen" mit der Aufgabe "Behinderungsanzeige versenden";
                              "außergewöhnliche Witterung" zeigt den Hinweis zu § 6 Abs. 2 VOB/B, eine
                              andere Ursache nicht; Anzeige ausfüllen und als Büro unterschreiben.
    Büro, Tagesbericht        die Aufgabe "Behinderungsanzeige anlegen" verlinkt auf den Auftrag mit
                              hervorgehobenem Kasten (schon offene Anzeige genannt), Klick legt an.
    Büro, Editor              Regel des Tagesberichts "Aufgabe verlinkt auf"; Systemfelder "nur Büro".

`confirm()` wird auf jeder Seite automatisch bestätigt und mitgeschrieben (Headless-Chrome blockiert
sonst). Hell- und Dunkelmodus ausdrücklich gesetzt. Feste Uhr 10:00 (cdp_klicktest.py).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_behinderungsanzeige.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_checkliste_unterschrift import CONFIRM, _unterschreiben  # noqa: E402

WEATHER_HINT = "Übliche Witterung ist nach § 6 Abs. 2 VOB/B keine Behinderung."
B = "behinderungsanzeige."


def _migration(name: str):
    import importlib.util

    path = next((Path(__file__).resolve().parent.parent / "alembic" / "versions").glob(f"*_{name}.py"))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def befuellen(db, k):
    from decimal import Decimal

    from sqlalchemy import select

    from app.checklist_templates import publish_draft, start_draft
    from app.checklists import complete_checklist, create_checklist, save_answer
    from app.models import (
        AppUser, ChecklistTemplate, ChecklistTemplateRule, Customer, Employee, Order, Project, Property,
        WorkPreparationEmployee,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.work_preparation import ensure_preparation

    ma = {key: Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group="gewerblich", active=True,
                        hourly_wage=Decimal("22.00"))
          for key, nr, vor, nach in (("mia", "E-1", "Mia", "Monteurin"), ("olga", "E-2", "Olga", "Office"))}
    db.add_all(ma.values()); db.flush()
    benutzer = {
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=ma["mia"].id, password_hash=k.passwort()),
        "buero": AppUser(username="olga", display_name="Olga Office", role="buero_auftrag", employee_id=ma["olga"].id, password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Klicktest Kunde", last_name="Klicktest Kunde")
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Nord", street="Weg 1", postal_code="12345", city="Stadt")
    db.add(objekt); db.flush()
    projekt = Project(project_number="P-KT-1", name="Dach Nord", customer_id=kunde.id, property_id=objekt.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-KT-1", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-1",
                    title="Dach Nord", customer_name="Klicktest Kunde", property_name="Halle", property_address="Weg 1\n12345 Stadt",
                    caseworker_employee_id=ma["olga"].id)
    db.add(auftrag); db.commit()
    prep = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=ma["mia"].id)); db.commit()

    _migration("checklisten_startvorlagen").insert_starter_templates(db.connection())
    neu = _migration("behinderungsanzeige_startvorlage")
    neu.insert_obstruction_template(db.connection())
    neu.link_daily_report_rule(db.connection())
    db.commit()
    tid = {label: db.scalar(select(ChecklistTemplate.id).where(ChecklistTemplate.label == label))
           for label in ("Behinderungsanzeige", "Tagesbericht")}
    publish_draft(db, tid["Behinderungsanzeige"])
    publish_draft(db, tid["Tagesbericht"])

    # Tagesbericht der Monteurin mit "Behinderung = ja" -- die Regel legt die Aufgabe mit Link an.
    tb = create_checklist(db, template_id=tid["Tagesbericht"], context_type="auftrag", order_id=auftrag.id,
                          created_by_employee_id=ma["mia"].id, created_by_user_id=benutzer["mia"].id)
    f = {x["field_key"]: x["id"] for x in tb["fields"]}
    for key, value in (("datum", "2026-10-02"), ("arbeiten", "Dachdeckung Nord"), ("behinderung", "ja")):
        save_answer(db, tb["id"], f[key], value, recorded_by_employee_id=ma["mia"].id)
    complete_checklist(db, tb["id"], completed_by_employee_id=ma["mia"].id)

    entwurf = start_draft(db, tid["Tagesbericht"])["editable_version"]
    regel = db.scalar(select(ChecklistTemplateRule.id).where(ChecklistTemplateRule.version_id == entwurf["id"],
                                                             ChecklistTemplateRule.field_key == "behinderung"))
    return {"auftrag": auftrag.id, "vorlagen": tid, "regel": regel, "tagesbericht": tb["id"],
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


async def _feld_ids(tab) -> dict:
    return await tab.js("Object.fromEntries(cl.fields.map(f=>[f.field_key,f.id]))")


async def _eingeben(tab, feld_id: int, wert: str, art: str = "input") -> None:
    """Wert ins Feld schreiben und so speichern, wie die Seite es tut (input+blur bzw. change)."""
    sel = f"#q_{feld_id} input, #q_{feld_id} textarea"
    if art == "change":
        await tab.js(f"(()=>{{const e=document.querySelector('{sel}');e.value={wert!r};e.dispatchEvent(new Event('change'))}})()")
    else:
        await tab.js(f"(()=>{{const e=document.querySelector('{sel}');e.value={wert!r};e.dispatchEvent(new Event('input'));"
                     f"e.dispatchEvent(new Event('blur'))}})()")
    await tab.warten(f"document.getElementById('st_{feld_id}')?.textContent==='Gespeichert'")


async def pruefen(tab, seed, p):
    import asyncio

    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    auftrag = seed["auftrag"]

    # --- Monteurin: starten, Meldung erfassen und unterschreiben -------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    start_bereit = "document.querySelector('#checklistSection .cl-start-buttons button')"
    await tab.oeffnen(f"/checklisten/auftrag/{auftrag}", start_bereit)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen(f"/checklisten/auftrag/{auftrag}", start_bereit)
    p.pruefe("Monteurin: Hellmodus", await tab.js("document.documentElement.dataset.theme"), "light")
    p.pruefe("Monteurin: Behinderungsanzeige startbar", await tab.js(
        "[...document.querySelectorAll('#checklistSection .cl-start-buttons button')].some(b=>b.textContent==='Behinderungsanzeige')"), True)
    p.pruefe("Monteurin: ohne ?zweck kein hervorgehobener Kasten", await tab.js("!document.getElementById('clFocus')"), True)
    await tab.js("[...document.querySelectorAll('#checklistSection .cl-start-buttons button')].find(b=>b.textContent==='Behinderungsanzeige').click()")
    await tab.warten("/^\\/checklisten\\/\\d+$/.test(location.pathname) && document.querySelector('#clMain .q')")
    cid = await tab.js("checklistId")
    f = await _feld_ids(tab)
    p.pruefe("Abschnitte", await tab.js("[...document.querySelectorAll('.group-title')].map(e=>e.textContent)"),
             ["Meldung", "Anzeige", "Wegfall"])
    p.pruefe("Monteurin: Anzeige als 'füllt das Büro aus' markiert", await tab.js(
        "[...document.querySelectorAll('.office-tag')].map(e=>e.closest('.q').id)"),
        [f"q_{f[B + k]}" for k in ("ursache", "ursache_beschreibung", "betroffene_leistungen", "beginn", "dauer",
                                   "unterschrift_buero")])
    p.pruefe("Monteurin: Ursache nicht wählbar und nicht als fehlend markiert", await tab.js(
        f"[[...document.querySelectorAll('#q_{f[B + 'ursache']} .tile')].every(b=>b.disabled),"
        f"document.getElementById('q_{f[B + 'ursache']}').classList.contains('missing'),"
        f"document.getElementById('q_{f[B + 'beschreibung']}').classList.contains('missing')]"), [True, False, True])
    p.pruefe("Monteurin: keine Zeichenfläche für 'Unterschrift Büro', aber für die Meldung", await tab.js(
        f"[!!document.getElementById('pad_{f[B + 'unterschrift_buero']}'), !!document.getElementById('pad_{f[B + 'unterschrift_meldung']}')]"),
        [False, True])
    await _eingeben(tab, f[B + "bekannt_seit"], "2026-10-02T07:45", "change")
    await _eingeben(tab, f[B + "beschreibung"], "Gerüst an der Nordseite fehlt, Traufe nicht erreichbar.")
    await _unterschreiben(tab, f[B + "unterschrift_meldung"], "Mia Monteurin")
    await tab.warten(f"document.querySelector('#q_{f[B + 'unterschrift_meldung']} .sig')")
    p.pruefe("Rückfrage vor dem Unterschreiben", await tab.js("window.__confirms.length>=1"), True)
    p.pruefe("Monteurin: Meldung danach gesperrt", await tab.js(
        f"[!!document.querySelector('#q_{f[B + 'beschreibung']} .value-ro'), !!document.getElementById('lockCard')]"), [True, True])
    p.pruefe("Monteurin: kein waagrechter Scrollbalken", await tab.js(
        "document.documentElement.scrollWidth<=window.innerWidth"), True)
    p.pruefe("Monteurin: kein Optionstext ragt aus seiner Kachel", await tab.js(
        "[...document.querySelectorAll('.tile')].filter(b=>b.scrollWidth>b.clientWidth).map(b=>b.textContent)"), [])
    p.pruefe("Monteurin: Folgen-Endpunkt 403", await tab.js(
        f"fetch('/api/checklists/{cid}/follow-ups').then(r=>r.status)"), 403)
    p.pruefe("Monteurin: Anzeige per API 403", await tab.js(
        f"fetch('/api/checklists/{cid}/answers/{f[B + 'ursache']}',{{method:'PUT',headers:{{'Content-Type':'application/json'}},"
        f"body:JSON.stringify({{value:'witterung'}})}}).then(r=>r.status)"), 403)
    await tab.bild("1_monteurin_meldung_unterschrieben")
    p.pruefe("Monteurin: keine JS-Fehler", tab.fehler, [])

    # --- Büro: Folge sichtbar, Anzeige mit Witterungs-Hinweis, als Büro unterschreiben ---------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    bereit = "document.querySelector('#followUpsCard .rule-row')"
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    p.pruefe("Büro: Dunkelmodus", await tab.js("document.documentElement.dataset.theme"), "dark")
    folge = await tab.js("document.querySelector('#followUpsCard .rule-row').textContent")  # innerText: Kennzeichen in Großbuchstaben
    p.pruefe("Büro: Folge 'Behinderungsanzeige versenden' erledigt, nach der Unterschrift der Meldung",
             ["Behinderungsanzeige versenden" in folge, "erledigt" in folge,
              "nach der Unterschrift „Unterschrift des Meldenden“" in folge], [True, True, True])
    p.pruefe("Büro: Link auf die Aufgabe", await tab.js(
        "/^\\/tasks\\?task=\\d+$/.test(new URL(document.querySelector('#followUpsCard a').href).pathname+new URL(document.querySelector('#followUpsCard a').href).search)"), True)
    p.pruefe("Büro: Anzeige ohne Sperrmarke", await tab.js("document.querySelectorAll('.office-tag').length"), 0)
    tiles = f"#q_{f[B + 'ursache']} .tile"
    await tab.js(f"[...document.querySelectorAll('{tiles}')].find(b=>b.textContent==='außergewöhnliche Witterung').click()")
    await tab.warten(f"document.querySelector('#q_{f[B + 'ursache']} [data-option-hint]')")
    p.pruefe("Büro: Hinweis bei außergewöhnlicher Witterung", await tab.js(
        f"document.querySelector('#q_{f[B + 'ursache']} [data-option-hint]').textContent"), WEATHER_HINT)
    hint_style = await tab.js(
        f"(()=>{{const e=document.querySelector('#q_{f[B + 'ursache']} [data-option-hint]');const s=getComputedStyle(e);return [s.color,s.backgroundColor]}})()")
    await tab.js(f"document.getElementById('q_{f[B + 'ursache']}').scrollIntoView({{block:'center'}})")
    await asyncio.sleep(0.2)
    await tab.bild("2_buero_witterung_dunkel")
    await tab.js(f"[...document.querySelectorAll('{tiles}')].find(b=>b.textContent==='Zugang oder Gerüst').click()")
    await tab.warten(f"!document.querySelector('#q_{f[B + 'ursache']} [data-option-hint]') && "
                     f"[...document.querySelectorAll('{tiles}')].find(b=>b.textContent==='Zugang oder Gerüst').classList.contains('on')")
    p.pruefe("Büro: andere Ursache ohne Hinweis", await tab.js(
        f"!document.querySelector('#q_{f[B + 'ursache']} [data-option-hint]')"), True)
    p.pruefe("Büro: Hinweis lesbar im Dunkelmodus (Text und Fläche verschieden)", hint_style[0] != hint_style[1], True)
    p.pruefe("Büro: kein Optionstext ragt aus seiner Kachel", await tab.js(
        f"[...document.querySelectorAll('{tiles}')].filter(b=>b.scrollWidth>b.clientWidth).map(b=>b.textContent)"), [])
    await _eingeben(tab, f[B + "ursache_beschreibung"], "Gerüstbauer nicht erschienen.")
    await _eingeben(tab, f[B + "betroffene_leistungen"], "Dachdeckung Nordseite, Rinnen.")
    await _eingeben(tab, f[B + "beginn"], "2026-10-02", "change")
    await _eingeben(tab, f[B + "dauer"], "etwa eine Woche")
    await _unterschreiben(tab, f[B + "unterschrift_buero"], "Olga Office")
    await tab.warten(f"document.querySelector('#q_{f[B + 'unterschrift_buero']} .sig')")
    p.pruefe("Büro: als Büro unterschrieben", await tab.js(
        f"document.querySelector('#q_{f[B + 'unterschrift_buero']} .sig .name').childNodes[0].textContent"), "Olga Office")
    aufgaben = await tab.js("fetch('/api/tasks').then(r=>r.json()).then(l=>l.filter(t=>t.title==='Behinderungsanzeige versenden')"
                            ".map(t=>[t.assigned_employee_name,t.priority,t.source_url]))")
    p.pruefe("Büro: genau eine Aufgabe 'versenden' an die Sachbearbeiterin", aufgaben,
             [["Olga Office", "hoch", f"/checklisten/{cid}"]])
    await tab.bild("3_buero_anzeige_unterschrieben")
    p.pruefe("Büro: keine JS-Fehler (Ausfüllen)", tab.fehler, [])

    # --- Büro: Link aus der Tagesbericht-Aufgabe -----------------------------------------------
    link = await tab.js("fetch('/api/tasks').then(r=>r.json()).then(l=>l.filter(t=>t.title.startsWith('Behinderungsanzeige anlegen')).map(t=>t.source_url))")
    p.pruefe("Tagesbericht: eine Aufgabe 'Behinderungsanzeige anlegen' mit Link", link,
             [f"/checklisten/auftrag/{auftrag}?zweck=behinderungsanzeige"])
    await tab.oeffnen(link[0] if link else "/", "document.getElementById('clFocus')")
    p.pruefe("Kasten: Titel und Knopf", await tab.js(
        "[document.querySelector('#clFocus .cl-start-title').textContent,[...document.querySelectorAll('#clFocus button')].map(b=>b.textContent)]"),
        ["Behinderungsanzeige anlegen", ["Behinderungsanzeige"]])
    p.pruefe("Kasten: schon offene Anzeige genannt", await tab.js(
        f"!!document.querySelector('#clFocus .cl-open a[href=\"/checklisten/{cid}\"]')"), True)
    await tab.bild("4_buero_link_anlegen")
    await tab.js("document.querySelector('#clFocus button').click()")
    await tab.warten(f"/^\\/checklisten\\/\\d+$/.test(location.pathname) && location.pathname!=='/checklisten/{cid}' && document.querySelector('#clMain h1')")
    p.pruefe("Klick legt eine neue Behinderungsanzeige an", await tab.js(
        "[document.querySelector('#clMain h1').textContent, cl.purpose, cl.status]"),
        ["Behinderungsanzeige", "behinderungsanzeige", "entwurf"])
    await tab.oeffnen(f"/checklisten/auftrag/{auftrag}?zweck=gibt_es_nicht", start_bereit)
    p.pruefe("Unbekannter Zweck: kein Kasten", await tab.js("!document.getElementById('clFocus')"), True)
    p.pruefe("Büro: keine JS-Fehler (Link)", tab.fehler, [])

    # --- Büro: Editor ---------------------------------------------------------------------------
    ed_bereit = "document.getElementById('metaPurpose')?.options.length && document.querySelector('#versionRows tr')"
    await tab.oeffnen(f"/checklisten/vorlagen/{seed['vorlagen']['Tagesbericht']}", ed_bereit)
    p.pruefe("Editor: Regel nennt den Link", await tab.js(
        "[...document.querySelectorAll('#ruleList .rule-row')].some(r=>r.innerText.includes('Link: Behinderungsanzeige anlegen'))"), True)
    await tab.js(f"toggleRule({seed['regel']})")
    p.pruefe("Editor: Auswahl 'Aufgabe verlinkt auf'", await tab.js(
        "(()=>{const s=document.querySelector('[data-r=link_purpose]');return [s.value,[...s.options].map(o=>o.textContent)]})()"),
        ["behinderungsanzeige", ["diese Checkliste", "Abnahme am Auftrag anlegen", "Behinderungsanzeige am Auftrag anlegen",
                                 "Bedenkenanzeige am Auftrag anlegen"]])
    await tab.bild("5_editor_regel_link")
    await tab.oeffnen(f"/checklisten/vorlagen/{seed['vorlagen']['Behinderungsanzeige']}", ed_bereit)
    p.pruefe("Editor: sechs Systemfelder 'nur Büro'", await tab.js(
        "[...document.querySelectorAll('#fieldList .frow .lbl .muted')].filter(e=>e.textContent.includes('nur Büro')).length"), 6)
    p.pruefe("Büro: keine JS-Fehler (Editor)", tab.fehler, [])
    await asyncio.sleep(0)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Behinderungsanzeige erfassen (1.8.38)", uhr="10:00"))
