"""Klicktest: Platzhalter {gewaehrleistung} im Vertrag (1.8.50, Stufe 2c-2a).

Befüllt: geprüfte Vertragsvorlage "BGB mit VOB/C" mit einem Abschnitt "Die Gewährleistung beträgt {gewaehrleistung} ab
Abnahme.", ein Verbraucher-Auftrag ohne festgelegte Gewährleistung (Angebot nie versendet -> Anlage bewusst wählen).

    Büro (1400 px, hell)    Karte "Vertrag": Hinweis "nutzt {gewaehrleistung} … nicht festgelegt", Festschreiben
                            gesperrt. Karte "Gewährleistung": Bauwerk, Vorschlag übernehmen -> Hinweis weg, Knopf frei.
                            Anlage "heutiger Stand", Fassung 1 festschreiben. Danach Karte "Gewährleistung" gesperrt
                            (Hinweis mit Fassung 1, Leistungsart nicht wählbar, kein Vorschlag, keine Abweichung);
                            Festlegen über die API 409.
    Büro (412 px, dunkel)   Gesperrte Karte lesbar, kein waagrechter Scrollbalken.

Feste Uhr 10:00 (cdp_klicktest.py).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_vertrag_gewaehrleistung.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID
beenden): siehe scripts/cdp_klicktest.py. Dauer etwa eine halbe Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.contract_templates import save_template
    from app.models import AppUser, Customer, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id

    bert = AppUser(username="bert", display_name="Bert Büro", role="buero_auftrag", password_hash=k.passwort())
    db.add(bert); db.flush()
    save_template(db, "bgb_vob_c_4_5", title="Bauvertrag {auftragsnummer}", sections=[
        {"heading": "§ 1 Parteien", "body_text": "Zwischen {firmenname} und {kundenname}.", "consumer_only": False,
         "with_checkbox": False},
        {"heading": "§ 2 Gewährleistung", "body_text": "Die Gewährleistung beträgt {gewaehrleistung} ab Abnahme.",
         "consumer_only": False, "with_checkbox": False},
    ], reviewed_on=berlin_today(), reviewed_by="RA Beispiel")
    kunde = Customer(name="Petra Privat", last_name="Privat", is_consumer=True, street="Dachweg 1", postal_code="52531",
                     city="Übach")
    db.add(kunde); db.flush()
    projekt = Project(project_number="P-KT-GEW", name="Dach Privat", customer_id=kunde.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(quote_number="A-KT-GEW", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"),
                    status="versendet")
    db.add(angebot); db.flush()
    db.add(QuoteItem(quote_id=angebot.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"),
                     unit="m²", unit_price=Decimal("50")))
    db.commit()
    auftrag = create_order_from_quote(db, angebot.id, order_date=date(2026, 10, 1), execution_start=None,
                                      execution_end=None, caseworker_employee_id=None, project_manager_employee_id=None,
                                      payment_terms=None, remarks=None)
    return {"auftrag": auftrag.id, "cookies": {"bert": k.cookies(bert)}}


BEREIT = ("document.getElementById('warrantyCurrent').textContent.includes('Leistungsart') && "
          "!!document.getElementById('contractFreezeBtn')")
KARTE = "document.getElementById('contractCard').innerText"


async def pruefen(tab, seed, p):
    import asyncio

    url = f"/orders/{seed['auftrag']}"
    await tab.anmelden(seed["cookies"]["bert"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(url, BEREIT)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen(url, BEREIT)

    p.pruefe("Vertrag: Hinweis auf {gewaehrleistung}, Festschreiben gesperrt", await tab.js(
        f"[{KARTE}.includes('Die Vorlage nutzt {{gewaehrleistung}}, die Gewährleistungsdauer ist am Auftrag aber nicht festgelegt'), "
        "document.getElementById('contractFreezeBtn').disabled]"), [True, True])
    await tab.js("document.getElementById('contractCard').scrollIntoView()")
    await tab.bild("1_vertrag_ohne_dauer_hell")

    await tab.js("(s=>{s.value='bauwerk';s.dispatchEvent(new Event('change'))})(document.getElementById('workKindSelect'))")
    await tab.js("[...document.querySelectorAll('#warrantyProposal button')].find(b=>b.textContent==='Vorschlag übernehmen').click()")
    await tab.warten("document.getElementById('warrantyStatus').textContent==='Vorschlag übernommen.'")
    await tab.warten("!document.getElementById('contractFreezeBtn').disabled && "
                     "!!document.querySelector('input[name=contractAttachment][value=aktuell]')")
    p.pruefe("Nach dem Festlegen: Hinweis weg, Festschreiben frei", await tab.js(
        f"[{KARTE}.includes('{{gewaehrleistung}}'), document.getElementById('contractFreezeBtn').disabled]"), [False, False])

    await tab.js("window.confirm=()=>true;document.querySelector('input[name=contractAttachment][value=aktuell]').click();"
                 "document.getElementById('contractFreezeBtn').click()")
    await tab.warten("document.getElementById('contractStatus').textContent==='Fassung 1 festgeschrieben.'")
    p.pruefe("Fassung 1 festgeschrieben", await tab.js("document.getElementById('contractStatus').textContent"),
             "Fassung 1 festgeschrieben.")

    await tab.oeffnen(url, "document.getElementById('warrantyCurrent').textContent.includes('Leistungsart')")
    sperre = ("[document.getElementById('warrantyLock').hidden, document.getElementById('warrantyLock').textContent, "
              "document.getElementById('workKindSelect').disabled, getComputedStyle(document.getElementById('warrantyProposal')).display, "
              "getComputedStyle(document.getElementById('warrantyDeviate')).display]")
    p.pruefe("Gewährleistung gesperrt: Hinweis, keine Auswahl, kein Vorschlag, keine Abweichung", await tab.js(sperre), [
        False, "Der festgeschriebene Vertrag (Fassung 1) nennt die Gewährleistungsdauer – Leistungsart und Dauer lassen sich "
        "nicht mehr ändern, wie der Kunde des Projekts.", True, "none", "none"])
    p.pruefe("Festlegen über die API: 409", await tab.js(
        f"fetch('/api/orders/{seed['auftrag']}/warranty',{{method:'PUT',headers:{{'Content-Type':'application/json'}},"
        "body:JSON.stringify({work_kind:'bauwerk',warranty_months:48,warranty_days:0,reason:'neu'})}).then(r=>r.status)"), 409)
    await tab.js("document.getElementById('warrantyCard').scrollIntoView()")
    await tab.bild("2_gewaehrleistung_gesperrt_hell")
    p.pruefe("Büro: keine JS-Fehler", tab.fehler, [])

    await tab.fenster(412, 900, mobil=True)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(url, "document.getElementById('warrantyCurrent').textContent.includes('Leistungsart')")
    await tab.js("document.getElementById('warrantyCard').scrollIntoView()")
    await asyncio.sleep(0.2)
    p.pruefe("412 px dunkel: kein waagrechter Scrollbalken", await tab.js(
        "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.bild("3_gewaehrleistung_gesperrt_dunkel_412")
    p.pruefe("412 px: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Platzhalter {gewaehrleistung} (1.8.50)", uhr="10:00"))
