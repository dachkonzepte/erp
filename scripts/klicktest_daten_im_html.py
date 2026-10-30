"""Klicktest: Daten im HTML (1.8.102, Vorgabe vom 14.10.2026 Punkt 2; Befund 1.8.100 Nr. 5–8).

Namen und Titel mit Markup und Anführungszeichen ("><img src=x onerror=…>, ');…//, &quot;…) stehen in Kunde, Unterordnern, Gruppe eines
Prüfpunkts, Projekt, Betriebsmittel. Jedes Skript, das daraus liefe, setzt window.__dkXss. Geprüft wird, dass es auf keiner Seite läuft,
dass die Namen als Text erscheinen und dass die auf data-Attribute umgebauten Knöpfe (_aktionen.html) weiter tun, was sie sollen -- mit
genau dem gespeicherten Wert.

    Kundenakte      Kunde und Unterordner als Text; Kategorie "Sonstiges" und den Unterordner anklicken -> gefiltert auf genau diesen
                    Unterordner
    Projektmappe    dasselbe mit Kategorie und Unterordner der Projektdateien
    Einsatzbericht  Gruppe eines Prüfpunkts (Befund Nr. 5) als Text; Klick klappt die Gruppe zu und wieder auf
    Neues Projekt   Kunde in der Auswahl als Text (Nr. 6); Neues Angebot: Projekt und Kunde als Text (Nr. 6)
    Kalender        Verknüpfungssuche (Nr. 7): Vorschlag mit &quot; im Titel anklicken -> verknüpft, Titel unverändert
    Betriebsmittel  Art als Text, die Badges bleiben HTML
    Einstellungen   Modul-Schalter (data-aenderung) aus und wieder an

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_daten_im_html.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer rund eine Minute.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

SKRIPT = """<img src=x onerror="window.__dkXss='{}'">"""
KUNDE = 'Kunde "><img src=x onerror="window.__dkXss=\'kunde\'">'
ORDNER = """Ordner');window.__dkXss='ordner';//\"><img src=x onerror="window.__dkXss='ordner2'">"""
GRUPPE = """Rinne"><img src=x onerror="window.__dkXss='gruppe'">'"""
PROJEKT = """Dach &quot;});window.__dkXss='kal';//<img src=x onerror="window.__dkXss='projekt'">"""
ART = """Leiter<img src=x onerror="window.__dkXss='art'">"""
DIALOGE = "window.alert=()=>{};window.confirm=()=>true;"


def befuellen(db, k):
    from app.customer_documents import customer_directory
    from app.document_categories import resolve_category_id
    from app.models import (AppUser, Customer, CustomerDocument, Employee, OperationalAsset, Order, Project, ProjectDocument)
    from app.project_documents import project_directory
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.service_reports import add_inspection_item, create_report

    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
    db.add(mia); db.flush()
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    kunde = Customer(name=KUNDE, last_name="Kunde XSS")
    db.add_all([anna, kunde]); db.flush()
    projekt = Project(project_number="P-XSS", name=PROJEKT, customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-XSS", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-1", title="Dach",
                    customer_name=KUNDE, property_name="Halle", property_address="Weg 1\n12345 Stadt")
    sonstiges = resolve_category_id(db, "Sonstiges")
    for ordner, name in ((ORDNER, "im-ordner.txt"), (None, "ohne-ordner.txt")):
        (customer_directory(kunde.id) / name).write_bytes(b"x")
        (project_directory(projekt.id) / name).write_bytes(b"x")
        db.add(CustomerDocument(customer_id=kunde.id, category="Sonstiges", category_id=sonstiges, subfolder=ordner,
                                original_filename=name, stored_filename=name, content_type="application/octet-stream", file_size=1))
        db.add(ProjectDocument(project_id=projekt.id, category="Sonstiges", category_id=sonstiges, subfolder=ordner,
                               original_filename=name, stored_filename=name, content_type="application/octet-stream", file_size=1))
    geraet = OperationalAsset(name="Anlegeleiter", asset_type=ART)
    db.add_all([auftrag, geraet]); db.commit()
    bericht = create_report(db, auftrag.id, "wartung", description="Wartung", created_by_employee_id=mia.id)
    add_inspection_item(db, bericht["id"], "Rinne frei", "free_text", group_name=GRUPPE)
    return {"kunde": kunde.id, "projekt": projekt.id, "auftrag": auftrag.id, "bericht": bericht["id"], "geraet": geraet.id,
            "cookies": k.cookies(anna)}


async def _kein_skript(tab, p, seite: str) -> None:
    p.pruefe(f"{seite}: kein Skript aus den Daten gelaufen", await tab.js("window.__dkXss===undefined"), True)


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=DIALOGE)
    await tab.anmelden(seed["cookies"])

    # --- Kundenakte ---------------------------------------------------------------------------------------------------
    await tab.oeffnen(f"/customers/{seed['kunde']}#dokumente", "typeof customer!=='undefined'&&!!customer&&customer.last_name==='Kunde XSS'"
                      "&&document.querySelectorAll('#customerDocuments .doc').length===2")
    await tab.warte_auf_neu_geladene_liste()
    p.pruefe("Kundenakte: Name als Text im Titel", await tab.js(f"document.body.innerText.includes({json.dumps(KUNDE)})"), True)
    await tab.js("document.querySelector('#docCategoryCards [data-wert=\"Sonstiges\"]').click(); true")
    knopf = await tab.js("(()=>{const b=[...document.querySelectorAll('#docSubfolderCards [data-klick]')].find(b=>b.dataset.wert);"
                         "return b?[b.dataset.wert,b.querySelector('b').textContent,b.getAttributeNames().filter(n=>n.startsWith('on'))]:null})()")
    p.pruefe("Kundenakte: Unterordner als Text, Wert im data-Attribut, kein on…-Attribut", knopf, [ORDNER, ORDNER, []])
    await tab.js("[...document.querySelectorAll('#docSubfolderCards [data-klick]')].find(b=>b.dataset.wert).click(); true")
    p.pruefe("Kundenakte: Klick filtert auf genau diesen Unterordner", await tab.js(
        "[activeDocSubfolder,[...document.querySelectorAll('#customerDocuments .doc-name')].map(e=>e.textContent)]"),
        [ORDNER, ["im-ordner.txt"]])
    await _kein_skript(tab, p, "Kundenakte")

    # --- Projektmappe -------------------------------------------------------------------------------------------------
    await tab.oeffnen(f"/projects/{seed['projekt']}#sec-files", "document.querySelectorAll('#documents .doc').length===2")
    await tab.warte_auf_neu_geladene_liste()
    await tab.js("document.querySelector('#categoryCards [data-wert=\"Sonstiges\"]').click(); true")
    await tab.js("[...document.querySelectorAll('#subfolderCards [data-klick]')].find(b=>b.dataset.wert).click(); true")
    p.pruefe("Projektmappe: Kategorie und Unterordner per Klick, genau dieser Wert", await tab.js(
        "[activeCategory,activeSubfolder,[...document.querySelectorAll('#documents .doc-name')].map(e=>e.textContent)]"),
        ["Sonstiges", ORDNER, ["im-ordner.txt"]])
    p.pruefe("Projektmappe: Projektname als Text", await tab.js(f"document.body.innerText.includes({json.dumps(PROJEKT)})"), True)
    await _kein_skript(tab, p, "Projektmappe")

    # --- Einsatzbericht (Nr. 5) -- seit 1.9.67 auf der Berichtsseite: die Gruppe als Überschrift über ihren Punkten (bis 1.9.66 ein
    # Klappknopf mit dem Namen im data-Attribut auf der Seite des Auftrags) ------------------------------------------------------------
    bericht = seed["bericht"]
    await tab.oeffnen(f"/service-reports/{bericht}", "typeof PUNKTE!=='undefined'&&PUNKTE.length>0&&!!document.querySelector('.punkt')")
    p.pruefe("Einsatzbericht: Gruppe als Text, ohne on…-Attribute", await tab.js(
        f"[...document.querySelectorAll('#schrittInhalt .gruppe')].filter(g=>g.textContent==={json.dumps(GRUPPE)})"
        ".map(g=>[g.textContent,g.children.length,g.getAttributeNames().filter(n=>n.startsWith('on'))])"), [[GRUPPE, 0, []]])
    await _kein_skript(tab, p, "Einsatzbericht")

    # --- Neues Projekt / Neues Angebot (Nr. 6) --------------------------------------------------------------------------
    await tab.oeffnen("/projects/new", "document.getElementById('customer').options.length>0")
    p.pruefe("Neues Projekt: Kunde als Text in der Auswahl", await tab.js(
        "[...document.getElementById('customer').options].map(o=>o.textContent)"), [f" · {KUNDE}"])
    await _kein_skript(tab, p, "Neues Projekt")
    await tab.oeffnen(f"/quotes/new?project_id={seed['projekt']}", "document.getElementById('project').options.length>0")
    p.pruefe("Neues Angebot: Projekt und Kunde als Text", await tab.js(
        "[document.getElementById('project').value,[...document.getElementById('project').options].map(o=>o.textContent)]"),
        [str(seed["projekt"]), [f"P-XSS · {KUNDE} · {PROJEKT}"]])
    await _kein_skript(tab, p, "Neues Angebot")

    # --- Kalender: Verknüpfungssuche (Nr. 7) -----------------------------------------------------------------------------
    await tab.oeffnen("/kalender", "typeof openCreate==='function'&&typeof toDateStr==='function'")
    await tab.js("openCreate(); true")
    await tab.js("document.getElementById('eLinkSearch').value='P-XSS';debouncedLinkSearch(); true")
    da = await tab.warten("document.querySelectorAll('#eLinkSuggestBox .suggest-item').length===1", 10)
    vorschlag = await tab.js("(()=>{const v=document.querySelector('#eLinkSuggestBox .suggest-item');"
                             "return [v.dataset.label,v.getAttributeNames().filter(n=>n.startsWith('on'))]})()")
    p.pruefe("Kalender: Vorschlag mit dem Titel im data-Attribut, ohne on…-Attribut", [da, vorschlag], [True, [f"P-XSS · {PROJEKT}", []]])
    await tab.js("document.querySelector('#eLinkSuggestBox .suggest-item').click(); true")
    p.pruefe("Kalender: Klick verknüpft genau dieses Projekt", await tab.js(
        "[selectedLink.type,selectedLink.id,selectedLink.label,document.getElementById('eLinkSearch').value]"),
        ["project", seed["projekt"], f"P-XSS · {PROJEKT}", f"P-XSS · {PROJEKT}"])
    await _kein_skript(tab, p, "Kalender")

    # --- Betriebsmittel ----------------------------------------------------------------------------------------------------
    await tab.oeffnen(f"/betriebsmittel/{seed['geraet']}", "(document.getElementById('seitenkopfUntertitel')?.textContent||'').length>0")
    p.pruefe("Betriebsmittel: Art als Text", await tab.js("document.getElementById('seitenkopfUntertitel').textContent.startsWith("
                                                         + json.dumps(ART) + ")"), True)
    await _kein_skript(tab, p, "Betriebsmittel")

    # --- Einstellungen: Modul-Schalter (change) ---------------------------------------------------------------------------
    await tab.oeffnen("/settings", "!!document.querySelector('[data-aenderung=\"modul\"][data-schluessel=\"betriebsmittel\"]')")
    schalter = "document.querySelector('[data-aenderung=\"modul\"][data-schluessel=\"betriebsmittel\"]')"
    await tab.js("showSettingsSection('modules'); true")
    status = "fetch('/api/modules').then(r=>r.json()).then(l=>(l.find?l:l.modules).find(m=>m.module_key==='betriebsmittel').enabled)"
    await tab.warte_auf_neu_geladene_liste(f"{schalter}.click()")
    aus = await tab.js(status)
    await tab.warte_auf_neu_geladene_liste(f"{schalter}.click()")
    p.pruefe("Einstellungen: Modul-Schalter schaltet aus und wieder an", [aus, await tab.js(status)], [False, True])
    p.pruefe("JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
