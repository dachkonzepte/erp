"""Klicktest: Speichern des Angebotskopfs lässt die interne Notiz stehen (1.8.23).

Bis 1.8.22 schickte saveHeader() im Angebots-Editor internal_note:null mit, jedes Speichern des
Angebotskopfs leerte die Notiz. Geprüft wird über die echte Seite:

    Angebots-Editor    Zahlungsbedingung und Ausführungszeitraum ändern, "Speichern" -- beide
                       Änderungen kommen an, die interne Notiz bleibt unverändert

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_angebot_interne_notiz.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

NOTIZ = "Kunde will Skonto, nicht zusagen"


def befuellen(db, k):
    from decimal import Decimal

    from app.labor_rate import load_labor_rate_settings
    from app.models import AppUser, Customer, Project, Quote, QuoteItem
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.projects import ensure_quote_structure

    load_labor_rate_settings(db)  # siehe klicktest_vertragsgrundlage.py: Singleton vorab anlegen
    bert = AppUser(username="bert", display_name="Bert Büro", role="buero_auftrag", password_hash=k.passwort())
    kunde = Customer(name="Firma Bau GmbH", last_name="Firma Bau GmbH", is_consumer=False)
    db.add_all([bert, kunde]); db.flush()
    projekt = Project(project_number="P-KT-1", name="Dach", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(quote_number="A-KT-1", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"))
    db.add(angebot); db.flush()
    db.add(QuoteItem(quote_id=angebot.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"),
                     unit="m²", unit_price=Decimal("50")))
    db.commit()
    meta, _, _ = ensure_quote_structure(db, angebot)
    meta.internal_note = NOTIZ
    db.commit()
    return {"angebot": angebot.id, "cookies": {"bert": k.cookies(bert)}}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.anmelden(seed["cookies"]["bert"])
    angebot = seed["angebot"]
    meta = f"fetch('/api/quotes/{angebot}').then(r=>r.json()).then(j=>j.document_meta)"

    await tab.oeffnen(f"/quotes/{angebot}/edit", "document.getElementById('hContractBasis')?.options.length===3")
    p.pruefe("Vorher: Notiz gespeichert", await tab.js(f"{meta}.then(m=>m.internal_note)"), NOTIZ)
    await tab.js("showTab('details')")
    zahlung = await tab.js("(()=>{const s=document.getElementById('hPayment');s.value=s.options[s.options.length-1].value;"
                           "return s.value})()")
    p.pruefe("Zahlungsbedingung zur Auswahl", bool(zahlung), True)
    await tab.js("document.getElementById('hExecution').value='KW 44';saveHeader()")
    await tab.warten("document.getElementById('headerStatus').textContent.includes('gespeichert')")
    p.pruefe("Zahlungsbedingung gespeichert", await tab.js(f"{meta}.then(m=>m.payment_terms)"), zahlung)
    p.pruefe("Ausführungszeitraum gespeichert", await tab.js(f"{meta}.then(m=>m.execution_period)"), "KW 44")
    p.pruefe("Interne Notiz unverändert", await tab.js(f"{meta}.then(m=>m.internal_note)"), NOTIZ)

    await tab.js("document.getElementById('headerStatus').textContent='';saveHeader()")  # zweites Speichern ohne Änderung
    await tab.warten("document.getElementById('headerStatus').textContent.includes('gespeichert')")
    p.pruefe("Nach zweitem Speichern unverändert", await tab.js(f"{meta}.then(m=>m.internal_note)"), NOTIZ)
    p.pruefe("JS-Fehler", tab.fehler, [])
    await tab.bild("angebotskopf_gespeichert")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
