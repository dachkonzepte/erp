"""Klicktest: Mustervorgang nicht beauftragbar, „Löschen“ nur ohne Auftrag (1.9.117, Stufe 5, R1, Punkt 7, Befund F6/F15).

    Angebots-Editor   Angebot eines Mustervorgangs: kein „Angebot beauftragen“, Hinweis mit dem Weg (Bild); ein Angebot eines gewöhnlichen
                      Projekts: „Angebot beauftragen“ wie bisher; Beauftragen aus der Seite (POST) beim Muster 409 mit dem Weg
    Projektmappe      Mustervorgang mit Kennzeichen „Mustervorgang“ (Bild); „Löschen“ im Menü nur ohne Auftrag
    Projektliste      „Löschen“ im Menü einer Zeile nur ohne Auftrag; in „Nur Mustervorgänge“ beim Muster

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_mustervorgang.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.models import AppUser, Customer, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id

    buero = AppUser(username="berta", display_name="Berta Büro", role="buero_auftrag", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Muster", last_name="Muster", city="Uebach")
    db.add_all([buero, kunde]); db.flush()

    def projekt(nummer, *, muster=False):
        p = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=kunde.id, status="angebot", is_template=muster,
                    pipeline_column_id=default_pipeline_column_id(db))
        db.add(p); db.flush()
        q = Quote(quote_number=f"A-{nummer}", project_id=p.id, title="Sanierung", vat_rate=Decimal("19"))
        db.add(q); db.flush()
        db.add(QuoteItem(quote_id=q.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2", unit_price=Decimal("50")))
        db.commit()
        return p, q

    muster, muster_angebot = projekt("M-1", muster=True)
    mit_auftrag, angebot_mit_auftrag = projekt("M-2")
    create_order_from_quote(db, angebot_mit_auftrag.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
                            caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    ohne_auftrag, angebot_ohne_auftrag = projekt("M-3")
    return {"muster": muster.id, "muster_angebot": muster_angebot.id, "mit_auftrag": mit_auftrag.id, "ohne_auftrag": ohne_auftrag.id,
            "angebot_ohne_auftrag": angebot_ohne_auftrag.id, "cookies": {"berta": k.cookies(buero)}}


EDITOR = "typeof quote!=='undefined'&&quote&&quote.id&&document.getElementById('sumNet').textContent.length>0"
MAPPE = "typeof project!=='undefined'&&project&&project.id&&document.getElementById('projectNumber').textContent.length>0"
LISTE = "typeof projects!=='undefined'&&projects.length>0&&document.getElementById('content').innerHTML.length>0"
BEAUFTRAGEN = ('{"order_date":"2026-10-28","execution_start":null,"execution_end":null,"caseworker_employee_id":null,'
               '"project_manager_employee_id":null,"payment_terms":null,"remarks":null}')


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1440, 900)
    await tab.anmelden(seed["cookies"]["berta"])

    await tab.oeffnen(f"/quotes/{seed['muster_angebot']}/edit", EDITOR)
    p.pruefe("Editor (Muster): kein „Angebot beauftragen“, Hinweis sichtbar", await tab.js(
        "(()=>{const b=document.getElementById('orderSyncBanner');return [document.getElementById('orderButton').hidden,"
        "!b.classList.contains('hidden'),b.textContent.includes('Mustervorgang.'),b.textContent.includes('Neuen Vorgang erstellen')]})()"),
        [True, True, True, True])
    antwort = await tab.js(f"fetch('/api/quotes/{seed['muster_angebot']}/convert-to-order',{{method:'POST',headers:{{'Content-Type':"
                           f"'application/json'}},body:'{BEAUFTRAGEN}'}}).then(async r=>[r.status,(await r.json()).detail.slice(0,44)])")
    p.pruefe("Beauftragen aus der Seite (Muster): 409 mit dem Weg", antwort, [409, "Ein Angebot eines Mustervorgangs wird nicht "])
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.bild("editor_mustervorgang_hinweis")

    await tab.oeffnen(f"/quotes/{seed['angebot_ohne_auftrag']}/edit", EDITOR)
    p.pruefe("Editor (gewöhnlich): „Angebot beauftragen“ wie bisher", await tab.js(
        "[document.getElementById('orderButton').hidden,document.getElementById('orderButton').textContent,"
        "document.getElementById('orderSyncBanner').classList.contains('hidden')]"), [False, "Angebot beauftragen", True])

    await tab.oeffnen(f"/projects/{seed['muster']}", MAPPE)
    p.pruefe("Projektmappe (Muster): Kennzeichen sichtbar, „Löschen“ im Menü", await tab.js(
        "(()=>{const k=document.getElementById('templateBadge');return [!k.hidden&&k.offsetParent!==null,k.textContent,"
        "!document.getElementById('deleteMenuItem').hidden]})()"), [True, "Mustervorgang", True])
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.bild("projektmappe_mustervorgang")
    await tab.oeffnen(f"/projects/{seed['mit_auftrag']}", MAPPE)
    p.pruefe("Projektmappe mit Auftrag: kein Kennzeichen, kein „Löschen“", await tab.js(
        "[document.getElementById('templateBadge').hidden,document.getElementById('deleteMenuItem').hidden]"), [True, True])
    await tab.oeffnen(f"/projects/{seed['ohne_auftrag']}", MAPPE)
    p.pruefe("Projektmappe ohne Auftrag: „Löschen“ im Menü", await tab.js("document.getElementById('deleteMenuItem').hidden"), False)

    await tab.oeffnen("/projects", LISTE)
    p.pruefe("Projektliste: „Löschen“ nur ohne Auftrag", await tab.js(
        "['P-M-2','P-M-3'].map(n=>menuItemsFor(projects.find(x=>x.project_number===n)).includes('deleteProjectRow('))"), [False, True])
    await tab.js("(()=>{const c=document.getElementById('onlyTemplates');c.checked=true;c.dispatchEvent(new Event('change'))})()")
    p.pruefe("Nur Mustervorgänge: Muster mit „Löschen“", await tab.js(
        "onlyTemplates&&menuItemsFor(templates.find(x=>x.project_number==='P-M-1')).includes('deleteProjectRow(')"), True)
    p.pruefe("JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
