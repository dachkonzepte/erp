"""Klicktest: Verbraucher-Merkmal und Vertragsgrundlage (1.8.21, Stufe 2b, Runde 2b-1a).

Prüft die fünf geänderten Seiten so, wie ein Nutzer sie sieht:

    Kunde anlegen      Häkchen "Verbraucher (§ 13 BGB)" ist vorbelegt
    Kundenseite        Häkchen zeigt den gespeicherten Wert, Umschalten + Speichern kommt an
    Angebots-Editor    Vorgabe aus dem Kunden, Warnung bei ungeprüfter Klausel, Wechsel ohne
                       Warnung bei geprüfter, Speichern kommt an
    Auftragsseite      Grundlage aus dem Angebot, Ändern ohne Begründung abgelehnt, mit
                       Begründung übernommen, Historie, Warnung bei ungeprüfter Klausel (hell/dunkel)
    Einstellungen      drei Klauseln, Textänderung ohne neue Prüfangaben setzt die Prüfung zurück,
                       Büro sieht die Felder gesperrt und ohne Speichern-Knopf

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_vertragsgrundlage.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

KLAUSEL_VOB = "Es gilt die VOB/B in der bei Vertragsschluss gueltigen Fassung."


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.contract_basis import update_clause
    from app.labor_rate import get_or_create_labor_rate_settings
    from app.models import AppUser, Customer, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id

    # Die Einstellungsseite ruft labor-rate-settings und labor-rate-calculation parallel ab; auf einer
    # frischen Datenbank legen beide denselben Singleton an, einer scheitert (UNIQUE auf id, bekannte
    # offene Fehlerklasse "get_or_create_settings(id=1)", CLAUDE.md) und die Seite zeigt ein alert().
    get_or_create_labor_rate_settings(db)
    db.commit()

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    bert = AppUser(username="bert", display_name="Bert Büro", role="buero_auftrag", password_hash=k.passwort())
    db.add_all([anna, bert]); db.flush()

    def angebot(name, verbraucher, nr):
        kunde = Customer(name=name, last_name=name, is_consumer=verbraucher)
        db.add(kunde); db.flush()
        projekt = Project(project_number=f"P-KT-{nr}", name=f"Dach {nr}", customer_id=kunde.id,
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-KT-{nr}", project_id=projekt.id, title=f"Dachsanierung {nr}", vat_rate=Decimal("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"),
                         unit="m²", unit_price=Decimal("50")))
        db.commit()
        return kunde, quote

    privat, angebot_privat = angebot("Petra Privat", True, "1")
    firma, angebot_firma = angebot("Firma Bau GmbH", False, "2")
    auftrag = create_order_from_quote(
        db, angebot_firma.id, order_date=date(2026, 9, 30), execution_start=None, execution_end=None,
        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None,
    )
    update_clause(db, "vob_b", clause_text=KLAUSEL_VOB, reviewed_on=berlin_today(), reviewed_by="RA Beispiel")
    update_clause(db, "bgb_vob_c_4_5", clause_text="Entwurf, noch nicht geprueft.", reviewed_on=None, reviewed_by=None)
    return {
        "privat": privat.id, "firma": firma.id, "angebot_privat": angebot_privat.id, "auftrag": auftrag.id,
        "cookies": {"anna": k.cookies(anna), "bert": k.cookies(bert)},
    }


async def pruefen(tab, seed, p):
    # Ein alert() hält den headless Chrome an; so landet er als Fehler in tab.fehler.
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.anmelden(seed["cookies"]["anna"])

    # Kunde anlegen: Vorgabe ja
    await tab.oeffnen("/master-data/customers/new", "document.getElementById('isConsumer')")
    p.pruefe("Neuer Kunde: Verbraucher vorbelegt", await tab.js("document.getElementById('isConsumer').checked"), True)
    p.pruefe("Neuer Kunde: JS-Fehler", tab.fehler, [])

    # Kundenseite: gespeicherter Wert, umschalten, speichern
    bereit = "document.getElementById('lastName')?.value==='Firma Bau GmbH'"
    await tab.oeffnen(f"/customers/{seed['firma']}", bereit)
    p.pruefe("Firma: Häkchen aus", await tab.js("document.getElementById('isConsumer').checked"), False)
    await tab.js("document.getElementById('isConsumer').checked=true;saveCustomer()")
    await tab.warten("document.getElementById('customerStatus').textContent==='Gespeichert.'")
    p.pruefe("Firma: nach Speichern Verbraucher", await tab.js(f"fetch('/api/customers/{seed['firma']}').then(r=>r.json()).then(j=>j.is_consumer)"), True)
    await tab.js("document.getElementById('isConsumer').checked=false;saveCustomer()")
    await tab.warten("document.getElementById('customerStatus').textContent==='Gespeichert.'")
    p.pruefe("Firma: zurückgestellt", await tab.js(f"fetch('/api/customers/{seed['firma']}').then(r=>r.json()).then(j=>j.is_consumer)"), False)
    p.pruefe("Kundenseite: JS-Fehler", tab.fehler, [])
    await tab.bild("kunde_verbraucher")

    # Angebots-Editor: Vorgabe aus dem Kunden, Warnung, Wechsel, Speichern
    await tab.oeffnen(f"/quotes/{seed['angebot_privat']}/edit", "document.getElementById('hContractBasis')?.options.length===3")
    await tab.js("showTab('details')")
    p.pruefe("Angebot: Vorgabe Verbraucher", await tab.js("document.getElementById('hContractBasis').value"), "bgb_vob_c_4_5")
    warnung = "(()=>{const w=document.getElementById('contractBasisWarning');return w.classList.contains('hidden')?'':w.textContent})()"
    text = await tab.js(warnung)
    p.pruefe("Angebot: Warnung bei ungeprüfter Klausel", "keine rechtlich geprüfte Klausel" in (text or ""), True)
    await tab.bild("angebot_warnung")
    await tab.js("const s=document.getElementById('hContractBasis');s.value='vob_b';s.dispatchEvent(new Event('change'))")
    p.pruefe("Angebot: keine Warnung bei geprüfter Klausel", await tab.js(warnung), "")
    await tab.js("saveHeader()")
    await tab.warten("document.getElementById('headerStatus').textContent.includes('gespeichert')")
    p.pruefe("Angebot: gespeichert", await tab.js(f"fetch('/api/quotes/{seed['angebot_privat']}').then(r=>r.json()).then(j=>j.document_meta.contract_basis)"), "vob_b")
    p.pruefe("Angebots-Editor: JS-Fehler", tab.fehler, [])

    # Auftragsseite
    bereit = "document.getElementById('contractBasisCurrent')?.textContent.includes('VOB/B')"
    await tab.oeffnen(f"/orders/{seed['auftrag']}", bereit)
    aktuell = "document.getElementById('contractBasisCurrent').textContent"
    p.pruefe("Auftrag: aus dem Angebot übernommen", "aus dem Angebot übernommen" in (await tab.js(aktuell) or ""), True)
    p.pruefe("Auftrag: keine Warnung (VOB/B geprüft)", await tab.js("document.getElementById('contractBasisWarning').style.display"), "none")
    await tab.js("document.getElementById('contractBasisSelect').value='bgb';changeContractBasis()")
    p.pruefe("Auftrag: ohne Begründung abgelehnt", await tab.js("document.getElementById('contractBasisStatus').textContent"), "Bitte eine Begründung angeben.")
    await tab.js("document.getElementById('contractBasisSelect').value='bgb';document.getElementById('contractBasisReason').value='Kunde wünscht BGB ohne VOB';changeContractBasis()")
    await tab.warten("document.getElementById('contractBasisStatus').textContent==='Vertragsgrundlage geändert.'")
    p.pruefe("Auftrag: neue Grundlage", "BGB (ohne VOB)" in (await tab.js(aktuell) or ""), True)
    p.pruefe("Auftrag: am Auftrag geändert", "am Auftrag geändert" in (await tab.js(aktuell) or ""), True)
    p.pruefe("Auftrag: Warnung (BGB ungeprüft)", await tab.js("document.getElementById('contractBasisWarning').style.display"), "")
    historie = await tab.js("document.getElementById('contractBasisHistory').textContent")
    p.pruefe("Auftrag: Historie mit Begründung", "VOB/B → BGB (ohne VOB)" in (historie or "") and "Kunde wünscht BGB ohne VOB" in (historie or ""), True)
    p.pruefe("Auftrag: Begründungsfeld geleert", await tab.js("document.getElementById('contractBasisReason').value"), "")
    p.pruefe("Auftragsseite: JS-Fehler", tab.fehler, [])
    await tab.js("document.getElementById('contractBasisCard').scrollIntoView()")
    await tab.bild("auftrag_vertragsgrundlage_hell")
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/orders/{seed['auftrag']}", "document.getElementById('contractBasisHistory')?.textContent.includes('Kunde')")
    await tab.js("document.getElementById('contractBasisCard').scrollIntoView()")
    await tab.bild("auftrag_vertragsgrundlage_dunkel")
    await tab.js("localStorage.setItem('erp_theme','light')")

    # Einstellungen als Admin
    bereit = "document.querySelectorAll('[data-basis]').length===3"
    await tab.oeffnen("/settings#contract-bases", bereit)
    p.pruefe("Einstellungen: Abschnitt sichtbar", await tab.js("document.getElementById('settings-contract-bases').classList.contains('active')"), True)
    vob = "document.querySelector('[data-basis=\"vob_b\"]')"
    p.pruefe("Einstellungen: VOB/B geprüft", "Rechtlich geprüft" in (await tab.js(f"{vob}.textContent") or ""), True)
    await tab.js(f"{vob}.querySelector('.cbText').value+=' Ergaenzt.';saveContractBasisClause('vob_b')")
    await tab.warten(f"{vob}.querySelector('.cbStatus').textContent.length>0")
    p.pruefe("Einstellungen: Textänderung setzt Prüfung zurück", "gilt nicht mehr" in (await tab.js(f"{vob}.querySelector('.cbStatus').textContent") or ""), True)
    p.pruefe("Einstellungen: jetzt nicht geprüft", "Nicht geprüft" in (await tab.js(f"{vob}.textContent") or ""), True)
    p.pruefe("Einstellungen: Prüfdatum geleert", await tab.js(f"{vob}.querySelector('.cbReviewedOn').value"), "")
    p.pruefe("Einstellungen: JS-Fehler", tab.fehler, [])
    await tab.bild("einstellungen_vertragsgrundlagen")

    # Einstellungen als Büro: nur lesen
    await tab.anmelden(seed["cookies"]["bert"])
    # Andere URL als eben: dieselbe URL mit Hash wäre eine Navigation im Dokument, ohne Neuladen.
    await tab.oeffnen("/settings?als=buero#contract-bases", bereit)
    p.pruefe("Büro: angemeldet als Bert", await tab.js("fetch('/api/auth/status').then(r=>r.json()).then(j=>j.user&&j.user.username)"), "bert")
    p.pruefe("Büro: Felder gesperrt", await tab.js("[...document.querySelectorAll('[data-basis] textarea')].every(t=>t.disabled)"), True)
    p.pruefe("Büro: kein Speichern-Knopf", await tab.js("document.querySelectorAll('[data-basis] button').length"), 0)
    p.pruefe("Büro: JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
