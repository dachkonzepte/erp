"""Klicktest: Vertragsvorlagen und Vertragsentwurf (1.8.32, Stufe 2b, Runde 2b-1b Teil 1).

Prüft die zwei geänderten Seiten so, wie ein Nutzer sie sieht:

    Einstellungen      Vertragsvorlagen: drei Grundlagen, Platzhalterliste, Abschnitt anlegen/
                       verschieben ohne Verlust des Getippten, Warnung bei unbekanntem Platzhalter
                       und ungenutzten Fallfeldern, Prüfung eintragen, Textänderung setzt sie zurück;
                       Büro sieht alles gesperrt und ohne Knöpfe; 412 px ohne seitliches Scrollen
    Auftragsseite      Ausführungszeitraum aus dem Angebot in den Auftragsdaten, Speichern lässt
                       die übrigen Felder stehen; Karte "Vertrag" mit vorbelegtem Entwurf, Warnung
                       bei ungeprüfter Vorlage, Fallfelder speichern, PDF; Entwurf von Hand anlegen
                       (hell/dunkel)

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_vertragsvorlagen.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

ZEITRAUM = "KW 42–44, witterungsabhängig"


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.contract_templates import save_template
    from app.labor_rate import load_labor_rate_settings
    from app.models import AppUser, Customer, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.projects import ensure_quote_structure

    # Wie klicktest_vertragsgrundlage.py: Singleton vorab, sonst alert() auf der Einstellungsseite.
    load_labor_rate_settings(db)
    db.commit()

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    bert = AppUser(username="bert", display_name="Bert Büro", role="buero_auftrag", password_hash=k.passwort())
    db.add_all([anna, bert]); db.flush()

    save_template(db, "bgb_vob_c_4_5", title="Bauvertrag {auftragsnummer}", sections=[
        {"heading": "§ 1 Parteien", "body_text": "Zwischen {firmenname} und {kundenname}.", "consumer_only": False, "with_checkbox": False},
        {"heading": "§ 2 Zeit", "body_text": "{ausfuehrungszeitraum}", "consumer_only": False, "with_checkbox": False},
        {"heading": "§ 3 Zahlung", "body_text": "{abschlagsplan}\n{besonderheiten}", "consumer_only": False, "with_checkbox": False},
        {"heading": "Widerrufsbelehrung", "body_text": "Nur für Verbraucher.", "consumer_only": True, "with_checkbox": False},
    ], reviewed_on=None, reviewed_by=None)

    def auftrag(name, verbraucher, nr, zeitraum=None):
        kunde = Customer(name=name, last_name=name, is_consumer=verbraucher, street="Dachweg 1", postal_code="52531", city="Übach")
        db.add(kunde); db.flush()
        projekt = Project(project_number=f"P-KT-{nr}", name=f"Dach {nr}", customer_id=kunde.id,
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-KT-{nr}", project_id=projekt.id, title=f"Dachsanierung {nr}", vat_rate=Decimal("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"),
                         unit="m²", unit_price=Decimal("50")))
        ensure_quote_structure(db, quote)[0].execution_period = zeitraum
        db.commit()
        return create_order_from_quote(
            db, quote.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
            caseworker_employee_id=None, project_manager_employee_id=None, payment_terms="14 Tage netto", remarks="Bemerkung bleibt",
        )

    privat = auftrag("Petra Privat", True, "1", ZEITRAUM)   # Vorlage vorhanden -> Entwurf beim Beauftragen
    firma = auftrag("Firma Bau GmbH", False, "2")          # VOB/B, noch keine Vorlage -> kein Entwurf
    return {"privat": privat.id, "firma": firma.id, "cookies": {"anna": k.cookies(anna), "bert": k.cookies(bert)}}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.anmelden(seed["cookies"]["anna"])

    # --- Einstellungen → Vertragsvorlagen (Admin) --------------------------------------------------
    bereit = "document.querySelectorAll('[data-ct]').length===3"
    await tab.oeffnen("/settings#contract-templates", bereit)
    p.pruefe("Einstellungen: Abschnitt aktiv", await tab.js("document.getElementById('settings-contract-templates').classList.contains('active')"), True)
    p.pruefe("Einstellungen: Platzhalterliste", await tab.js("document.querySelectorAll('#contractPlaceholderRows tr').length"), 22)
    vob = "document.querySelector('[data-ct=\"vob_b\"]')"
    p.pruefe("VOB/B: noch keine Vorlage", "Keine Vorlage" in (await tab.js(f"{vob}.textContent") or ""), True)
    p.pruefe("Verbraucher-Vorlage: nicht geprüft", "Nicht geprüft" in (await tab.js("document.querySelector('[data-ct=\"bgb_vob_c_4_5\"]').textContent") or ""), True)

    # Zwei Abschnitte anlegen, im ersten tippen, dann verschieben -- das Getippte bleibt erhalten.
    await tab.js("ctAdd('vob_b');ctAdd('vob_b')")
    p.pruefe("VOB/B: zwei neue Abschnitte", await tab.js(f"{vob}.querySelectorAll('.ctSection').length"), 2)
    await tab.js(f"{vob}.querySelector('.ctTitle').value='Bauvertrag VOB';"
                 f"const s={vob}.querySelectorAll('.ctSection');"
                 "s[0].querySelector('.ctHeading').value='Erster';s[0].querySelector('.ctBody').value='Text für {kundename}';"
                 "s[1].querySelector('.ctHeading').value='Zweiter';s[1].querySelector('.ctBody').value='Zeitraum {ausfuehrungszeitraum}';"
                 "ctMove('vob_b',0,1)")
    p.pruefe("VOB/B: verschoben, nichts verloren", await tab.js(f"[...{vob}.querySelectorAll('.ctHeading')].map(x=>x.value).join('|')"), "Zweiter|Erster")
    p.pruefe("VOB/B: Hinweis ungespeichert", await tab.js(f"{vob}.querySelector('.ctStatus').textContent"), "Noch nicht gespeichert.")
    await tab.js("saveContractTemplate('vob_b')")
    await tab.warten(f"{vob}.querySelector('.ctStatus').textContent==='Gespeichert.'")
    p.pruefe("VOB/B: gespeichert", await tab.js("fetch('/api/settings/contract-templates').then(r=>r.json()).then(d=>d.templates[0].sections.map(s=>s.heading).join('|'))"), "Zweiter|Erster")
    warnung = await tab.js(f"[...{vob}.querySelectorAll('.hint')].map(h=>h.textContent).join(' ')")
    p.pruefe("VOB/B: Warnung unbekannter Platzhalter", "{kundename}" in (warnung or ""), True)
    p.pruefe("VOB/B: Warnung ungenutzte Fallfelder", "Abschlagsplan" in (warnung or "") and "Besonderheiten" in (warnung or ""), True)
    await tab.bild("einstellungen_vorlage_warnungen")

    # Prüfung eintragen, dann Text ändern mit denselben Prüfangaben -> zurückgesetzt.
    await tab.js(f"{vob}.querySelector('.ctBody').value='Zeitraum {{ausfuehrungszeitraum}}, Abschläge {{abschlagsplan}}, {{besonderheiten}}';"
                 f"{vob}.querySelectorAll('.ctBody')[1].value='Text für {{kundenname}}';"
                 f"{vob}.querySelector('.ctReviewedOn').value=new Date().toLocaleDateString('sv-SE',{{timeZone:'Europe/Berlin'}});"
                 f"{vob}.querySelector('.ctReviewedBy').value='RA Beispiel';saveContractTemplate('vob_b')")
    await tab.warten(f"{vob}.querySelector('.ctStatus').textContent==='Gespeichert.'")
    p.pruefe("VOB/B: geprüft", "Rechtlich geprüft" in (await tab.js(f"{vob}.textContent") or ""), True)
    p.pruefe("VOB/B: keine Warnungen mehr", await tab.js(f"{vob}.querySelectorAll('.hint').length"), 0)
    await tab.js(f"{vob}.querySelector('.ctConsumer').checked=true;saveContractTemplate('vob_b')")
    await tab.warten(f"{vob}.querySelector('.ctStatus').textContent.length>0")
    p.pruefe("VOB/B: Änderung setzt Prüfung zurück", "gilt nicht mehr" in (await tab.js(f"{vob}.querySelector('.ctStatus').textContent") or ""), True)
    p.pruefe("VOB/B: wieder nicht geprüft", "Nicht geprüft" in (await tab.js(f"{vob}.textContent") or ""), True)
    p.pruefe("VOB/B: Prüfdatum geleert", await tab.js(f"{vob}.querySelector('.ctReviewedOn').value"), "")
    await tab.js(f"{vob}.querySelector('.ctConsumer').checked=false;saveContractTemplate('vob_b')")
    await tab.warten(f"{vob}.querySelector('.ctStatus').textContent==='Gespeichert.'")
    p.pruefe("Einstellungen: JS-Fehler", tab.fehler, [])
    await tab.js(f"{vob}.scrollIntoView()")
    await tab.bild("einstellungen_vorlage")

    # --- Auftragsseite: Verbraucher-Auftrag mit Entwurf ------------------------------------------
    bereit = "document.getElementById('cExecutionPeriod')!==null"
    await tab.oeffnen(f"/orders/{seed['privat']}", bereit)
    p.pruefe("Auftrag: Ausführungszeitraum aus dem Angebot", await tab.js("document.getElementById('executionPeriod').value"), "KW 42–44, witterungsabhängig")
    p.pruefe("Vertrag: Zeitraum vorbelegt", await tab.js("document.getElementById('cExecutionPeriod').value"), "KW 42–44, witterungsabhängig")
    karte = "document.getElementById('contractCard').textContent"
    p.pruefe("Vertrag: Warnung ungeprüfte Vorlage", "nicht rechtlich geprüft" in (await tab.js(karte) or ""), True)
    p.pruefe("Vertrag: Verbraucher erkannt", "ist Verbraucher" in (await tab.js(karte) or ""), True)
    await tab.js("document.getElementById('cPaymentPlan').value='30 % bei Auftrag, Rest nach Abnahme';saveContract()")
    await tab.warten("document.getElementById('contractStatus').textContent==='Vertragsentwurf gespeichert.'")
    api = f"fetch('/api/orders/{seed['privat']}/contract').then(r=>r.json()).then(d=>d.contract)"
    gespeichert = await tab.js(f"{api}.then(c=>c.payment_plan+'|'+c.execution_period)")
    p.pruefe("Vertrag: Fallfelder gespeichert", gespeichert, "30 % bei Auftrag, Rest nach Abnahme|KW 42–44, witterungsabhängig")
    pdf = await tab.js(f"fetch('/api/orders/{seed['privat']}/contract/pdf').then(r=>r.status+' '+r.headers.get('content-type'))")
    p.pruefe("Vertrag: PDF", pdf, "200 application/pdf")
    p.pruefe("Vertrag: PDF-Knopf", "Entwurf als PDF" in (await tab.js(karte) or ""), True)

    # Auftragsdaten speichern: Zeitraum ändern, die übrigen Felder bleiben.
    await tab.js("document.getElementById('executionPeriod').value='KW 45';saveOrder()")
    await tab.warten("document.getElementById('saveStatus').textContent==='Auftragsdaten gespeichert.'")
    auftrag = await tab.js(f"fetch('/api/orders/{seed['privat']}').then(r=>r.json()).then(o=>[o.execution_period,o.payment_terms,o.remarks].join('|'))")
    p.pruefe("Auftrag: Zeitraum gespeichert, Rest unverändert", auftrag, "KW 45|14 Tage netto|Bemerkung bleibt")
    p.pruefe("Vertrag: Entwurf behält seinen Zeitraum", await tab.js(f"{api}.then(c=>c.execution_period)"), "KW 42–44, witterungsabhängig")
    p.pruefe("Auftragsseite: JS-Fehler", tab.fehler, [])
    await tab.js("document.getElementById('contractCard').scrollIntoView()")
    await tab.bild("auftrag_vertrag_hell")
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/orders/{seed['privat']}?dunkel=1", bereit)
    await tab.js("document.getElementById('contractCard').scrollIntoView()")
    await tab.bild("auftrag_vertrag_dunkel")
    await tab.js("localStorage.setItem('erp_theme','light')")

    # --- Firmenauftrag: VOB/B-Vorlage gibt es inzwischen, Entwurf von Hand anlegen ---------------
    await tab.oeffnen(f"/orders/{seed['firma']}", "document.getElementById('contractCard').textContent.includes('Vertragsentwurf anlegen')")
    p.pruefe("Firma: kein Entwurf beim Beauftragen", "Noch kein Vertragsentwurf" in (await tab.js(karte) or ""), True)
    await tab.js("createContract()")
    await tab.warten("document.getElementById('cExecutionPeriod')!==null")
    p.pruefe("Firma: Entwurf angelegt", await tab.js("document.getElementById('contractStatus').textContent"), "Vertragsentwurf angelegt.")
    p.pruefe("Firma: kein Verbraucher", "kein Verbraucher" in (await tab.js(karte) or ""), True)
    p.pruefe("Firma: JS-Fehler", tab.fehler, [])

    # --- Büro: Vorlagen nur lesen, Vertrag bearbeiten ------------------------------------------
    await tab.anmelden(seed["cookies"]["bert"])
    await tab.oeffnen("/settings?als=buero#contract-templates", "document.querySelectorAll('[data-ct]').length===3")
    p.pruefe("Büro: angemeldet als Bert", await tab.js("fetch('/api/auth/status').then(r=>r.json()).then(j=>j.user&&j.user.username)"), "bert")
    p.pruefe("Büro: Felder gesperrt", await tab.js("[...document.querySelectorAll('[data-ct] input,[data-ct] textarea')].every(t=>t.disabled)"), True)
    p.pruefe("Büro: keine Knöpfe", await tab.js("document.querySelectorAll('[data-ct] button').length"), 0)
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen("/settings?als=buero&schmal=1#contract-templates", "document.querySelectorAll('[data-ct]').length===3")
    p.pruefe("412 px: kein seitliches Scrollen", await tab.js("document.documentElement.scrollWidth<=window.innerWidth"), True)
    await tab.bild("einstellungen_vorlagen_412")
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/orders/{seed['firma']}?als=buero", "document.getElementById('cSpecialTerms')!==null")
    await tab.js("document.getElementById('cSpecialTerms').value='Gerüst stellt der Kunde';saveContract()")
    await tab.warten("document.getElementById('contractStatus').textContent==='Vertragsentwurf gespeichert.'")
    p.pruefe("Büro: Fallfeld gespeichert", await tab.js(f"fetch('/api/orders/{seed['firma']}/contract').then(r=>r.json()).then(d=>d.contract.special_terms)"), "Gerüst stellt der Kunde")
    p.pruefe("Büro: JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
