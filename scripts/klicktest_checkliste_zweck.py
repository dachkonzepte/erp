"""Klicktest: Zweck und Systemfelder im Vorlagen-Editor (1.8.16, Stufe 2 Runde 2a-2).

Die Registry kennt in 2a-2 noch keine Systemfelder (kommen in 2b/2c), und die Instanz läuft in
einem eigenen Prozess -- ein Test-Zweck lässt sich dort nicht einhängen. Deshalb:

    Vorlage "Wird Abnahme"   allgemein, Auftrag + Objekt: im Editor den Zweck "Abnahme" wählen --
                             Objekt wird abgewählt und gesperrt, speichern mit Rückfrage, Kennzeichen
                             im Kopf, "Löschen" verschwindet.
    Vorlage "Abnahme mit     Zweck Abnahme, zwei Felder im Befüllen direkt als Systemfeld markiert
    Systemfeldern"           (so, wie 2b sie anlegen wird): feste Eigenschaften gesperrt, kein
                             "Feld löschen", Optionen ohne ×/+, Beschriftung änderbar. Veröffentlichen
                             -- danach ist der Zweck gesperrt; Start-Auswahl nur am Auftrag.
    Vorlage "Altzweck"       Zweck, den die Registry nicht kennt: Hinweis "Systemfelder des Zwecks"
                             mit Knopf "angleichen", der mit der Begründung scheitert.
    Monteurin (Handybreite)  sah die Abnahme bis 1.8.60 am Auftrag in "Checkliste starten"; seit 1.8.61 ist der
                             Zweck "abnahme" nur fürs Büro -- keine Abnahme zum Starten, Anlegen über die API 403.

Seit 1.8.61 trägt der Zweck "abnahme" echte Systemfelder (Abnahmeprotokoll); die beiden hier markierten Felder bleiben
zusätzlich als Beispiel für die Sperren im Editor.

`confirm()` wird auf jeder Seite automatisch bestätigt und mitgeschrieben (Headless-Chrome blockiert
sonst). Hell- und Dunkelmodus werden ausdrücklich gesetzt (sonst gälte die Windows-Einstellung).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_checkliste_zweck.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_checkliste_unterschrift import CONFIRM  # noqa: E402


def befuellen(db, k):
    from decimal import Decimal

    from app.checklist_templates import add_field, add_option, create_template
    from app.models import (
        AppUser, ChecklistTemplate, ChecklistTemplateField, ChecklistTemplateVersion, Customer, Employee, Order,
        Project, Property, WorkPreparationEmployee,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.work_preparation import ensure_preparation

    ma = {key: Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group="gewerblich", active=True,
                        hourly_wage=Decimal("22.00"))
          for key, nr, vor, nach in (("mia", "E-1", "Mia", "Monteurin"), ("karl", "E-2", "Karl", "Kollege"))}
    db.add_all(ma.values()); db.flush()
    benutzer = {
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=ma["mia"].id, password_hash=k.passwort()),
        "buero": AppUser(username="buero", display_name="Karl Kollege", role="buero_auftrag", employee_id=ma["karl"].id, password_hash=k.passwort()),
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
                    title="Dach Nord", customer_name="Klicktest Kunde", property_name="Halle", property_address="Weg 1\n12345 Stadt")
    db.add(auftrag); db.commit()
    prep = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=ma["mia"].id)); db.commit()

    wird = create_template(db, label="Wird Abnahme", contexts=["auftrag", "objekt"])
    add_field(db, wird["draft_version_id"], {"field_type": "text", "label": "Bemerkung", "field_key": "bem"})

    abn = create_template(db, label="Abnahme mit Systemfeldern", contexts=["auftrag"], purpose="abnahme")
    v = abn["draft_version_id"]
    add_field(db, v, {"field_type": "ja_nein", "label": "Abnahme erklärt", "field_key": "abnahme.erklaert",
                      "required": True, "allow_na": True})
    x = add_field(db, v, {"field_type": "auswahl", "label": "Vorbehalt", "field_key": "abnahme.vorbehalt", "required": True})
    vorbehalt = next(f["id"] for f in x["fields"] if f["field_key"] == "abnahme.vorbehalt")
    add_option(db, vorbehalt, "keiner", option_key="keiner")
    add_option(db, vorbehalt, "wegen Mängeln", option_key="maengel")
    add_field(db, v, {"field_type": "text", "label": "Bemerkung", "field_key": "bem"})
    for field in db.query(ChecklistTemplateField).filter(ChecklistTemplateField.version_id == v,
                                                         ChecklistTemplateField.field_key.like("abnahme.%")):
        field.is_system = True  # wie 2b sie anlegen wird -- die Registry kennt sie in 2a-2 noch nicht
    felder = {f.field_key: f.id for f in db.query(ChecklistTemplateField).filter(ChecklistTemplateField.version_id == v)}

    alt = create_template(db, label="Altzweck", contexts=["auftrag"])
    add_field(db, alt["draft_version_id"], {"field_type": "text", "label": "Notiz", "field_key": "notiz"})
    db.get(ChecklistTemplate, alt["id"]).purpose = "zweck_aus_2b"
    db.get(ChecklistTemplateVersion, alt["draft_version_id"]).purpose = "zweck_aus_2b"
    db.commit()

    return {"wird": wird["id"], "abnahme": abn["id"], "alt": alt["id"], "felder": felder, "auftrag": auftrag.id,
            "objekt": objekt.id, "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


async def pruefen(tab, seed, p):
    import asyncio

    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    bereit = "document.getElementById('metaPurpose')?.options.length && document.querySelector('#versionRows tr')"
    api = lambda tid: f"fetch('/api/checklist-templates/{tid}').then(r=>r.json())"  # noqa: E731

    # --- Büro: Zweck wählen ---------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/checklisten/vorlagen/{seed['wird']}", bereit)
    await tab.js("localStorage.setItem('erp_theme','light')")  # erst nach dem ersten Laden: about:blank hat keinen Speicher
    await tab.oeffnen(f"/checklisten/vorlagen/{seed['wird']}", bereit)
    p.pruefe("Hellmodus", await tab.js("document.documentElement.dataset.theme"), "light")
    p.pruefe("Zwecke zur Auswahl", await tab.js("[...document.getElementById('metaPurpose').options].map(o=>o.textContent)"),
             ["Allgemein", "Abnahme", "Behinderungsanzeige", "Bedenkenanzeige"])
    p.pruefe("Vorher: Objekt gewählt, Zweck wählbar", await tab.js(
        "[document.getElementById('ctx_objekt').checked, document.getElementById('metaPurpose').disabled]"), [True, False])
    await tab.js("(()=>{const s=document.getElementById('metaPurpose');s.value='abnahme';s.dispatchEvent(new Event('change'))})()")
    p.pruefe("Abnahme gewählt: Objekt abgewählt und gesperrt, Auftrag bleibt", await tab.js(
        "['auftrag','objekt','betriebsmittel','betrieb'].map(c=>{const b=document.getElementById('ctx_'+c);return [b.checked,b.disabled]})"),
        [[True, False], [False, True], [False, True], [False, True]])
    p.pruefe("Hinweis zum Zweck", await tab.js("document.getElementById('purposeHint').textContent"),
             "nur Auftrag · 11 Systemfelder (fester Schlüssel und Typ, nicht löschbar) · nur Büro – Monteure sehen "
             "Checklisten dieses Zwecks nicht, auch nicht in /mobil · nach der ersten Veröffentlichung nicht mehr änderbar")
    await tab.js("[...document.querySelectorAll('button')].find(b=>b.textContent==='Speichern').click()")
    await tab.warten("document.getElementById('metaStatus').textContent==='Gespeichert.'", 10)
    confirms = await tab.js("window.__confirms")
    p.pruefe("Rückfrage vor dem Zweckwechsel", bool(confirms) and confirms[-1].startswith("Zweck ändern?"), True)
    p.pruefe("Gespeichert: Zweck und Kontexte", await tab.js(f"{api(seed['wird'])}.then(t=>[t.purpose,t.contexts,t.editable_version.purpose])"),
             ["abnahme", ["auftrag"], "abnahme"])
    p.pruefe("Kopf: Kennzeichen, kein Löschen mehr", await tab.js(
        "[document.getElementById('versionBadges').textContent.includes('Zweck: Abnahme'), [...document.querySelectorAll('#heroActions button')].some(b=>b.textContent==='Löschen')]"),
        [True, False])
    p.pruefe("Büro (Zweck): JS-Fehler", tab.fehler, [])
    await tab.bild("zweck_gewaehlt_hell")

    # --- Büro: Systemfelder ---------------------------------------------------------------------
    f = seed["felder"]
    await tab.oeffnen(f"/checklisten/vorlagen/{seed['abnahme']}", bereit)
    p.pruefe("Liste: Systemfelder gekennzeichnet", await tab.js(
        f"[{f['abnahme.erklaert']},{f['abnahme.vorbehalt']},{f['bem']}].map(id=>document.querySelector('#frow_'+id+' .lbl').textContent.includes('Systemfeld'))"),
        [True, True, False])
    await tab.js(f"toggleField({f['abnahme.erklaert']})")
    feld = f"document.querySelector('#frow_{f['abnahme.erklaert']} .frow-body')"
    p.pruefe("Ja/Nein-Systemfeld: fest = gesperrt, Beschriftung frei", await tab.js(
        f"['label','field_type','field_key','required','allow_na','help_text','group_name'].map(k=>{feld}.querySelector('[data-k='+k+']').disabled)"),
        [False, True, True, True, True, False, False])
    p.pruefe("Ja/Nein-Systemfeld: kein 'Feld löschen', Erklärung da", await tab.js(
        f"[[...{feld}.querySelectorAll('button')].some(b=>b.textContent==='Feld löschen'), {feld}.textContent.includes('Systemfeld des Zwecks')]"),
        [False, True])
    await tab.js(f"(()=>{{const i={feld}.querySelector('[data-k=label]');i.value='Abnahme ausdrücklich erklärt'}})()")
    await tab.js(f"saveField({f['abnahme.erklaert']})")
    await tab.warten(f"document.getElementById('fst_{f['abnahme.erklaert']}')?.textContent==='Gespeichert.'", 10)
    p.pruefe("Umbenannt, fest bleibt fest", await tab.js(
        f"{api(seed['abnahme'])}.then(t=>t.editable_version.fields.find(x=>x.id==={f['abnahme.erklaert']})).then(x=>[x.label,x.is_system,x.required,x.allow_na,x.field_key])"),
        ["Abnahme ausdrücklich erklärt", True, True, True, "abnahme.erklaert"])
    await tab.js(f"toggleField({f['abnahme.vorbehalt']})")
    opt = f"document.querySelector('#frow_{f['abnahme.vorbehalt']} .frow-body')"
    p.pruefe("Auswahl-Systemfeld: Optionen fest", await tab.js(
        f"[[...{opt}.querySelectorAll('.opt-row input')].map(i=>i.disabled), {opt}.querySelectorAll('.opt-row .danger').length, !!document.getElementById('newOpt_{f['abnahme.vorbehalt']}'), {opt}.querySelector('[data-k=multiple]').disabled, {opt}.textContent.includes('vom Zweck vorgegeben')]"),
        [[True, True], 0, False, True, True])
    await tab.js(f"toggleField({f['bem']})")
    p.pruefe("Gewöhnliches Feld: löschbar", await tab.js(
        f"[...document.querySelectorAll('#frow_{f['bem']} .frow-body button')].some(b=>b.textContent==='Feld löschen')"), True)
    p.pruefe("Kein Hinweis zu Systemfeldern", await tab.js("document.getElementById('versionNotice').textContent.includes('Systemfelder des Zwecks')"), False)
    await tab.bild("systemfelder_hell")
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/checklisten/vorlagen/{seed['abnahme']}", bereit)
    await tab.js(f"toggleField({f['abnahme.vorbehalt']})")
    p.pruefe("Dunkelmodus", await tab.js("document.documentElement.dataset.theme"), "dark")
    await tab.bild("systemfelder_dunkel")
    await tab.js("localStorage.setItem('erp_theme','light')")

    # Veröffentlichen -- danach ist der Zweck fest
    await tab.oeffnen(f"/checklisten/vorlagen/{seed['abnahme']}", bereit)
    await tab.js("publish()")
    await tab.warten("document.getElementById('versionBadges').textContent.includes('Gültig: Fassung 1')", 10)
    p.pruefe("Nach Veröffentlichen: Zweck gesperrt", await tab.js(
        "[document.getElementById('metaPurpose').disabled, document.getElementById('purposeHint').textContent.includes('seit der ersten Veröffentlichung festgelegt')]"),
        [True, True])
    p.pruefe("Start-Auswahl: am Auftrag ja, am Objekt nein", await tab.js(
        "Promise.all(['auftrag','objekt'].map(c=>fetch('/api/checklists/startable-templates?context='+c).then(r=>r.json()).then(l=>l.filter(t=>t.label==='Abnahme mit Systemfeldern').map(t=>t.purpose_label))))"),
        [["Abnahme"], []])
    p.pruefe("Büro (Systemfelder): JS-Fehler", tab.fehler, [])

    # --- Büro: unbekannter Zweck -> Hinweis und "angleichen" ----------------------------------------
    await tab.oeffnen(f"/checklisten/vorlagen/{seed['alt']}", bereit)
    p.pruefe("Hinweis nennt den unbekannten Zweck", await tab.js(
        "[...document.querySelectorAll('#versionNotice li')].map(li=>li.textContent)"), ["Unbekannter Zweck: zweck_aus_2b"])
    p.pruefe("Auswahl zeigt ihn als unbekannt", await tab.js(
        "document.getElementById('metaPurpose').selectedOptions[0].textContent"), "zweck_aus_2b (unbekannt)")
    await tab.js("syncSystemFields()")
    await tab.warten("document.getElementById('syncStatus')?.textContent", 10)
    p.pruefe("Angleichen scheitert mit Begründung", await tab.js("document.getElementById('syncStatus').textContent"),
             "Fehler: Unbekannter Zweck: zweck_aus_2b")
    await tab.bild("unbekannter_zweck_hell")
    p.pruefe("Büro (unbekannt): JS-Fehler", [x for x in tab.fehler if "400" not in x], [])

    await tab.oeffnen("/checklisten/vorlagen", "document.querySelector('#rows tr td a') || document.querySelector('tbody tr td a')")
    p.pruefe("Vorlagenliste: Zweck als Kennzeichen", await tab.js(
        "[...document.querySelectorAll('tbody tr')].filter(r=>r.textContent.includes('Abnahme')).map(r=>r.querySelector('td').textContent.replace(/\\s+/g,' ').trim())"),
        ["Wird Abnahme Abnahme", "Abnahme mit Systemfeldern Abnahme"])
    await tab.js("localStorage.removeItem('erp_theme')")

    # --- Monteurin: Start am Auftrag ------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(390, 844, mobil=True)
    await tab.oeffnen(f"/checklisten/auftrag/{seed['auftrag']}", "document.querySelector('.cl-start')")
    await asyncio.sleep(0.3)
    p.pruefe("Monteurin: keine Abnahme zum Starten (seit 1.8.61 nur Büro)", await tab.js(
        "[...document.querySelectorAll('.cl-start-buttons button')].map(b=>b.textContent)"), [])
    p.pruefe("Monteurin: Anlegen über die API 403", await tab.js(
        f"fetch('/api/checklists',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify("
        f"{{template_id:{seed['abnahme']},context_type:'auftrag',order_id:{seed['auftrag']}}})}}).then(async r=>[r.status,(await r.json()).detail])"),
        [403, "Diese Checkliste führt das Büro."])
    p.pruefe("Monteurin: JS-Fehler", tab.fehler, [])
    await tab.bild("monteurin_abnahme")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
