"""Klicktest: Abnahme und Gewährleistung (1.8.46, Stufe 2c-1).

Befüllt: Gewerbekunde (VOB/B), Objekt "Halle Nord" mit den Dachflächen Nord und Süd (Süd mit Garantie Dritter),
ein fremdes Objekt mit "Fremd", Auftrag aus einem Angebot, das danach geändert wurde (Abgleich angeboten); Beteiligte:
Architektin ohne Vollmacht, Hausverwaltung mit Vollmacht samt Beleg.

    Büro (1400 px, hell)    Auftrag, Karte "Gewährleistung": "nicht festgelegt", Leistungsart wählen -> Vorschlag
                            48 Monate mit Fundstelle, übernehmen; abweichend 60 Monate ohne Begründung abgelehnt, mit
                            Begründung festgelegt, Hinweis "weicht ab", Historie.
                            Karte "Abnahme": Dialog ohne jede Vorauswahl, Dachflächen nur Nord/Süd, Pflichtangaben
                            fehlen -> Meldung; Teilabnahme mit Vorbehalt Mängel, Architektin -> Warnung "keine
                            Vollmacht" (Hausverwaltung ohne Warnung); SVG abgelehnt (Dialog bleibt offen), PDF
                            gespeichert; Eintrag mit "mit Vorbehalten (Mängel)", Warnung, Beleg (application/pdf,
                            nosniff), Gewährleistung bis 15.09.2031; Abgleich gesperrt (kein Knopf).
                            Verwerfen ohne Begründung abgelehnt, mit Begründung verworfen; Abgleich wieder möglich.
                            Schlüssig + verweigert ohne Beleg mit Begründung; ausdrücklich, gesamt, Süd, Foto.
    Büro (1400 px, hell)    Objekt: Karte "Gewährleistung aus Abnahmen", Spalten "Gewährleistung bis" und
                            "Garantie Dritter bis"; Dachfläche Süd: Karte mit der Abnahme, Feld "Garantie Dritter
                            (Hersteller oder Fremdfirma) bis", Speichern lässt es stehen; Dachfläche Nord: keine.
    Büro (412 px, dunkel)   Auftrag: Karten lesbar, Dialog ohne waagrechten Scrollbalken.
    Monteurin               API der Abnahme 403, Auftragsseite gesperrt.

Feste Uhr 10:00 (cdp_klicktest.py).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_abnahme.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID
beenden): siehe scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
SVG = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><script>alert(1)</script></svg>'


def _bild(fmt: str, farbe=(30, 110, 160), groesse=(320, 200)) -> bytes:
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", groesse, farbe).save(buf, format=fmt)
    return buf.getvalue()


def befuellen(db, k):
    import os
    from datetime import date
    from decimal import Decimal

    from app.contacts import create_contact
    from app.models import AppUser, Customer, Employee, Project, Property, Quote, QuoteItem, RoofArea
    from app.orders import create_order_from_quote
    from app.project_participants import add_participant, store_power_of_attorney
    from app.project_pipeline_columns import default_pipeline_column_id

    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich",
                   active=True, hourly_wage=Decimal("22.00"))
    db.add(mia); db.flush()
    benutzer = {
        "buero": AppUser(username="olga", display_name="Olga Office", role="buero_auftrag", password_hash=k.passwort()),
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id,
                       password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Uebach")
    nachbar = Property(customer_id=kunde.id, name="Nachbarhalle", street="Werkstr. 7", postal_code="52531", city="Uebach")
    db.add_all([objekt, nachbar]); db.flush()
    flaechen = {
        "nord": RoofArea(property_id=objekt.id, name="Nord"),
        "sued": RoofArea(property_id=objekt.id, name="Süd", contractor="Folien-Profi GmbH",
                         third_party_guarantee_until=date(2030, 6, 30)),
        "fremd": RoofArea(property_id=nachbar.id, name="Fremd"),
    }
    db.add_all(flaechen.values()); db.flush()
    projekt = Project(project_number="P-KT-ABN", name="Dachsanierung Halle", customer_id=kunde.id,
                      property_id=objekt.id, status="angebot", pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(quote_number="A-KT-ABN", project_id=projekt.id, title="Dachsanierung Halle", vat_rate=Decimal("19"))
    db.add(angebot); db.flush()
    position = QuoteItem(quote_id=angebot.id, position_number="1", short_text="Abdichtung", quantity=Decimal("850"),
                         unit="m²", unit_price=Decimal("48.90"))
    db.add(position); db.commit()
    auftrag = create_order_from_quote(db, angebot.id, order_date=date(2026, 9, 1), execution_start=None,
                                      execution_end=None, caseworker_employee_id=None, project_manager_employee_id=None,
                                      payment_terms=None, remarks=None)
    position.quantity = Decimal("870")  # Angebot danach geändert -> Abgleich angeboten
    db.commit()
    add_participant(db, projekt, create_contact(db, {"kind": "person", "first_name": "Petra", "last_name": "Plan"}),
                    role="architekt_planer")
    hv = add_participant(db, projekt, create_contact(db, {"kind": "firma", "company_name": "HV Muster"}),
                         role="hausverwaltung", authorized_recipient=True)
    store_power_of_attorney(db, hv, filename="vollmacht.pdf", data=PDF, user_name="Olga Office")

    ordner = Path(os.environ["ERP_DATA_DIR"]) / "klicktest-uploads"  # im Wegwerf-Ordner der Instanz
    ordner.mkdir(parents=True, exist_ok=True)
    dateien = {"pdf": ordner / "Protokoll.pdf", "svg": ordner / "Protokoll.svg", "jpg": ordner / "Foto.jpg"}
    dateien["pdf"].write_bytes(PDF)
    dateien["svg"].write_bytes(SVG)
    dateien["jpg"].write_bytes(_bild("JPEG"))
    return {"auftrag": auftrag.id, "auftragsnummer": auftrag.order_number, "objekt": objekt.id, "flaechen": {n: f.id for n, f in flaechen.items()},
            "dateien": {n: str(p) for n, p in dateien.items()},
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


async def _datei_setzen(tab, selector: str, pfad: str) -> None:
    doc = await tab.cmd("DOM.getDocument", depth=1)
    node = await tab.cmd("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
    await tab.cmd("DOM.setFileInputFiles", files=[pfad], nodeId=node["nodeId"])


def _waehlen(element_id: str, setzen: str) -> str:
    """Auswahl setzen und change auslösen -- in einer eigenen Funktion, sonst kollidiert ein zweites const."""
    return f"(()=>{{const s=document.getElementById('{element_id}');{setzen};s.dispatchEvent(new Event('change'))}})()"


def _radio(name: str, wert: str) -> str:
    return f"document.querySelector('#acceptanceDialog input[name={name}][value={wert}]').click()"


BEREIT = ("document.getElementById('warrantyCurrent').textContent.includes('Leistungsart') && "
          "!document.getElementById('acceptanceList').textContent.includes('Lädt')")
LISTE = "[...document.querySelectorAll('#acceptanceList .acc-item')]"


async def _erfassen(tab, schritte: list[str]) -> None:
    await tab.js("openAcceptanceDialog()")
    await tab.warten("document.getElementById('acceptanceDialog').open")
    for schritt in schritte:
        await tab.js(schritt)


async def pruefen(tab, seed, p):
    import asyncio

    auftrag = seed["auftrag"]
    url = f"/orders/{auftrag}"
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(url, BEREIT)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen(url, BEREIT)

    # --- Gewährleistung -------------------------------------------------------------------------------
    p.pruefe("Gewährleistung: nicht festgelegt, Leistungsart ohne Vorauswahl", await tab.js(
        "[document.getElementById('warrantyCurrent').innerText, document.getElementById('workKindSelect').value]"),
        ["Leistungsart: nicht festgelegt\nGewährleistungsdauer: nicht festgelegt", ""])
    await tab.js(_waehlen("workKindSelect", "s.value='bauwerk'"))
    p.pruefe("Gewährleistung: Vorschlag mit Fundstelle", await tab.js(
        "document.querySelector('#warrantyProposal .proposal').innerText"),
        "Vorschlag bei VOB/B: 48 Monate (4 Jahre)\nFundstelle: § 13 Abs. 4 Nr. 1 VOB/B – Bauwerke: 4 Jahre – eine im Vertrag "
        "vereinbarte Dauer geht vor.")
    await tab.js("[...document.querySelectorAll('#warrantyProposal button')].find(b=>b.textContent==='Vorschlag übernehmen').click()")
    await tab.warten("document.getElementById('warrantyStatus').textContent==='Vorschlag übernommen.'")
    p.pruefe("Gewährleistung: übernommen", await tab.js(
        "document.getElementById('warrantyCurrent').innerText.split('\\n')[1].split(' (')[0]"),
        "Gewährleistungsdauer: 48 Monate")
    await tab.js("document.getElementById('warrantyDeviate').open=true;document.getElementById('warrantyMonths').value='60';"
                 "document.getElementById('warrantyDays').value='0';setWarrantyDeviation()")
    await tab.warten("document.getElementById('warrantyStatus').textContent.startsWith('Fehler')")
    p.pruefe("Gewährleistung: Abweichung ohne Begründung abgelehnt", await tab.js(
        "document.getElementById('warrantyStatus').textContent.includes('bitte eine Begründung angeben')"), True)
    await tab.js("document.getElementById('warrantyReason').value='5 Jahre im Vertrag vereinbart (§ 7)';setWarrantyDeviation()")
    await tab.warten("document.getElementById('warrantyStatus').textContent==='Gewährleistungsdauer festgelegt.'")
    p.pruefe("Gewährleistung: abweichend mit Hinweis und Historie", await tab.js(
        "[document.getElementById('warrantyDeviation').style.display!=='none', "
        "document.getElementById('warrantyDeviation').innerText.includes('Begründung: 5 Jahre im Vertrag vereinbart'), "
        "document.querySelectorAll('#warrantyHistory .revision').length]"), [True, True, 2])
    p.pruefe("Abgleich vor der Abnahme angeboten", await tab.js(
        "!![...document.querySelectorAll('#syncCard button')].find(b=>b.textContent==='Quellangebot in Auftrag übernehmen')"), True)
    await tab.js("document.getElementById('warrantyCard').scrollIntoView()")
    await tab.bild("1_gewaehrleistung_hell")

    # --- Abnahme erfassen -----------------------------------------------------------------------------
    await _erfassen(tab, [])
    p.pruefe("Dialog: keine Vorauswahl", await tab.js(
        "[document.querySelectorAll('#acceptanceDialog input:checked').length, document.getElementById('accDate').value]"),
        [0, ""])
    p.pruefe("Dialog: nur die Dachflächen des Objekts", await tab.js(
        "[...document.querySelectorAll('#accRoofAreas .choice')].map(l=>l.textContent.trim())"), ["Nord", "Süd"])
    await tab.js("saveAcceptance(document.getElementById('accSaveBtn'))")
    p.pruefe("Dialog: fehlende Pflichtangaben", await tab.js("document.getElementById('accDialogStatus').textContent"),
             "Bitte angeben: Art, Datum, Umfang, Ergebnis, Erklärt durch.")
    await tab.js(_radio("accKind", "foermlich"))
    await tab.js("document.getElementById('accDate').value='2026-09-15'")
    await tab.js(_radio("accScope", "teil"))
    await tab.js("document.getElementById('accScopeDesc').value='Dachfläche Nord samt Attika'")
    await tab.js("document.querySelector('#accRoofAreas .acc-area').click()")
    await tab.js(_radio("accResult", "abgenommen"))
    p.pruefe("Dialog: zwei Fragen erst bei 'abgenommen', ohne Vorauswahl", await tab.js(
        "[!document.getElementById('accReservations').hidden, "
        "document.querySelectorAll('#accReservations input:checked').length]"), [True, 0])
    await tab.js(_radio("accDefects", "ja"))
    await tab.js(_radio("accPenalty", "nein"))
    await tab.js(_radio("accDeclarer", "beteiligter"))
    await tab.js("saveAcceptance(document.getElementById('accSaveBtn'))")
    p.pruefe("Dialog: Beteiligter fehlt", await tab.js("document.getElementById('accDialogStatus').textContent"),
             "Bitte angeben: Beteiligter.")
    await tab.js(_waehlen("accParticipant", "s.selectedIndex=2"))
    p.pruefe("Dialog: Hausverwaltung gewählt", await tab.js(
        "document.getElementById('accParticipant').selectedOptions[0].textContent"), "HV Muster (Hausverwaltung)")
    p.pruefe("Dialog: Hausverwaltung mit Vollmacht -- keine Warnung", await tab.js(
        "document.getElementById('accPoaWarning').hidden"), True)
    await tab.js(_waehlen("accParticipant", "s.selectedIndex=1"))
    p.pruefe("Dialog: Architektin ohne Vollmacht -- Warnung", await tab.js(
        "[document.getElementById('accPoaWarning').hidden, document.getElementById('accPoaWarning').textContent.startsWith("
        "'Für Petra Plan ist keine Vollmacht hinterlegt')]"), [False, True])
    await _datei_setzen(tab, "#accFiles", seed["dateien"]["svg"])
    await tab.js("saveAcceptance(document.getElementById('accSaveBtn'))")
    await tab.warten("document.getElementById('accDialogStatus').textContent.startsWith('Fehler')")
    p.pruefe("Dialog: SVG abgelehnt, Dialog bleibt offen", await tab.js(
        "[document.getElementById('accDialogStatus').textContent, document.getElementById('acceptanceDialog').open]"),
        ["Fehler: „Protokoll.svg“: Der Beleg muss ein Foto (JPEG, PNG, WebP) oder ein PDF sein.", True])
    await tab.bild("2_dialog_hell")
    await _datei_setzen(tab, "#accFiles", seed["dateien"]["pdf"])
    await tab.js("saveAcceptance(document.getElementById('accSaveBtn'))")
    await tab.warten(f"!document.getElementById('acceptanceDialog').open && {LISTE}.length===1")
    eintrag = f"{LISTE}[0].innerText"
    p.pruefe("Abnahme: Kopf und Ergebnis", await tab.js(f"{eintrag}.split('\\n').slice(0,3)"), [
        "Teilabnahme · förmlich · 15.09.2026", "Ergebnis: abgenommen mit Vorbehalten (Mängel)",
        "Teil: Dachfläche Nord samt Attika"])
    p.pruefe("Abnahme: Dachfläche, Warnung, Gewährleistung", await tab.js(
        f"[{eintrag}.includes('Dachflächen: Nord'), {eintrag}.includes('Petra Plan (Architekt/Planer) ⚠ ohne hinterlegte Vollmacht'), "
        f"{eintrag}.includes('Gewährleistung bis 15.09.2031 (60 Monate (5 Jahre) ab Abnahme)')]"), [True, True, True])
    p.pruefe("Abnahme: Beleg als PDF mit nosniff", await tab.js(
        f"fetch({LISTE}[0].querySelector('a[href*=\"/files/\"]').href).then(r=>[r.status,r.headers.get('content-type'),"
        "r.headers.get('x-content-type-options')])"), [200, "application/pdf", "nosniff"])
    p.pruefe("Abgleich gesperrt, kein Knopf", await tab.js(
        "[document.getElementById('syncCard').innerText.includes('Abnahme erfasst – der Abgleich mit dem Angebot ist gesperrt'), "
        "document.querySelectorAll('#syncCard button').length]"), [True, 0])
    await tab.js("document.getElementById('acceptanceCard').scrollIntoView()")
    await tab.bild("3_abnahme_gespeichert_hell")

    # --- Verwerfen -------------------------------------------------------------------------------------
    p.pruefe("Verwerfen: Begründungsfeld erst nach dem Klick sichtbar", await tab.js(
        f"getComputedStyle({LISTE}[0].querySelector('.acc-discard')).display"), "none")
    await tab.js(f"{LISTE}[0].querySelector('button').click()")
    p.pruefe("Verwerfen: Begründungsfeld nach dem Klick sichtbar", await tab.js(
        f"getComputedStyle({LISTE}[0].querySelector('.acc-discard')).display"), "flex")
    await tab.js(f"{LISTE}[0].querySelector('.acc-discard .danger').click()")
    p.pruefe("Verwerfen ohne Begründung abgelehnt", await tab.js("document.getElementById('acceptanceStatus').textContent"),
             "Bitte begründen, warum die Abnahme verworfen wird.")
    await tab.js(f"{LISTE}[0].querySelector('textarea').value='Falscher Umfang erfasst';"
                 f"{LISTE}[0].querySelector('.acc-discard .danger').click()")
    await tab.warten(f"{LISTE}[0].classList.contains('discarded')")
    p.pruefe("Verworfen: gekennzeichnet, ohne Gewährleistung", await tab.js(
        f"[{eintrag}.includes('Falscher Umfang erfasst'), {eintrag}.includes('Gewährleistung bis')]"), [True, False])
    await tab.warten("document.querySelectorAll('#syncCard button').length===1")
    p.pruefe("Abgleich nach dem Verwerfen wieder möglich", await tab.js(
        "document.querySelectorAll('#syncCard button').length"), 1)

    # --- schlüssig/verweigert ohne Beleg, ausdrücklich gesamt mit Foto -----------------------------------
    await _erfassen(tab, [_radio("accKind", "schluessig"), "document.getElementById('accDate').value='2026-09-20'",
                          _radio("accScope", "gesamt"), _radio("accResult", "verweigert"),
                          _radio("accDeclarer", "auftraggeber")])
    p.pruefe("Schlüssig: Begründungsfeld statt Pflichtbeleg", await tab.js(
        "[!document.getElementById('accConductBox').hidden, document.getElementById('accReservations').hidden, "
        "document.getElementById('accProofHint').textContent.startsWith('Bei einer schlüssigen Abnahme')]"), [True, True, True])
    await tab.js("document.getElementById('accConductReason').value='Abnahme durch Schreiben vom 20.09. verweigert';"
                 "saveAcceptance(document.getElementById('accSaveBtn'))")
    await tab.warten(f"!document.getElementById('acceptanceDialog').open && {LISTE}.length===2")
    await _erfassen(tab, [_radio("accKind", "ausdruecklich"), "document.getElementById('accDate').value='2026-09-25'",
                          _radio("accScope", "gesamt"),
                          "[...document.querySelectorAll('#accRoofAreas .acc-area')][1].click()",
                          _radio("accResult", "abgenommen"), _radio("accDefects", "nein"), _radio("accPenalty", "nein"),
                          _radio("accDeclarer", "auftraggeber")])
    await _datei_setzen(tab, "#accFiles", seed["dateien"]["jpg"])
    await tab.js("saveAcceptance(document.getElementById('accSaveBtn'))")
    await tab.warten(f"!document.getElementById('acceptanceDialog').open && {LISTE}.length===3")
    p.pruefe("Liste: neueste zuerst, verweigert ohne Gewährleistung", await tab.js(
        f"{LISTE}.map(e=>[e.querySelector('.acc-head').textContent, e.innerText.includes('Gewährleistung bis')])"),
        [["Gesamtabnahme · ausdrücklich · 25.09.2026", True], ["Gesamtabnahme · schlüssig · 20.09.2026", False],
         ["Teilabnahme · förmlich · 15.09.2026", False]])
    p.pruefe("Büro Auftrag: keine JS-Fehler", tab.fehler, [])

    # --- Objekt und Dachflächen -----------------------------------------------------------------------
    await tab.oeffnen(f"/properties/{seed['objekt']}", "document.querySelectorAll('#roofAreaRows tr').length===2 && "
                      "!document.getElementById('acceptanceWarrantyRows').textContent.includes('Lädt')")
    p.pruefe("Objekt: Spalten der Dachflächen", await tab.js(
        "[...document.querySelectorAll('#roofAreaRows')[0].closest('table').querySelectorAll('th')].map(t=>t.textContent)"),
        ["Name", "Dachtyp", "Fläche", "Eindeckung", "Gewährleistung bis", "Garantie Dritter bis", ""])
    p.pruefe("Objekt: Süd mit Gewährleistung und Garantie Dritter, Nord ohne", await tab.js(
        "[...document.querySelectorAll('#roofAreaRows tr')].map(r=>[...r.children].map(c=>c.textContent.trim()).slice(0,6))"),
        [["Nord", "—", "—", "—", "—", "—"], ["Süd", "—", "—", "—", "25.9.2031", "30.6.2030"]])
    p.pruefe("Objekt: Karte nur mit der gültigen, abgenommenen Abnahme", await tab.js(
        "[...document.querySelectorAll('#acceptanceWarrantyRows tr')].map(r=>[...r.children].map(c=>c.innerText.trim()))"),
        [[f"{seed['auftragsnummer']}\nDachsanierung Halle", "gesamt\nDachflächen: Süd", "25.9.2026 · ausdrücklich",
          "abgenommen ohne Vorbehalte", "25.9.2031"]])
    await tab.bild("4_objekt_hell")
    sued = seed["flaechen"]["sued"]
    await tab.oeffnen(f"/roof-areas/{sued}", "!document.getElementById('acceptanceWarrantyList').textContent.includes('Lädt')")
    p.pruefe("Dachfläche Süd: Abnahme mit Gewährleistung", await tab.js(
        "document.getElementById('acceptanceWarrantyList').innerText.includes('Gewährleistung bis 25.09.2031')"), True)
    p.pruefe("Dachfläche Süd: Feld Garantie Dritter", await tab.js(
        "[document.getElementById('editThirdPartyGuarantee').closest('.field').querySelector('label').textContent, "
        "document.getElementById('editThirdPartyGuarantee').value]"),
        ["Garantie Dritter (Hersteller oder Fremdfirma) bis", "2030-06-30"])
    await tab.js("document.getElementById('editNotes').value='Folie geprüft';saveRoofArea()")
    await tab.warten("document.getElementById('areaStatus').textContent==='Gespeichert.'")
    p.pruefe("Dachfläche Süd: Speichern lässt Garantie Dritter stehen", await tab.js(
        f"fetch('/api/roof-areas/{sued}').then(r=>r.json()).then(a=>[a.third_party_guarantee_until,a.notes,a.contractor])"),
        ["2030-06-30", "Folie geprüft", "Folien-Profi GmbH"])
    await tab.bild("5_dachflaeche_sued_hell")
    await tab.oeffnen(f"/roof-areas/{seed['flaechen']['nord']}",
                      "!document.getElementById('acceptanceWarrantyList').textContent.includes('Lädt')")
    p.pruefe("Dachfläche Nord: keine Abnahme (die verworfene zählt nicht)", await tab.js(
        "document.getElementById('acceptanceWarrantyList').innerText"), "Keine Abnahme nennt diese Dachfläche.")
    p.pruefe("Büro Objekt/Dachfläche: keine JS-Fehler", tab.fehler, [])

    # --- 412 px, dunkel ----------------------------------------------------------------------------------
    await tab.fenster(412, 900, mobil=True)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(url, BEREIT)
    p.pruefe("412 px dunkel: Thema", await tab.js("document.documentElement.dataset.theme"), "dark")
    await tab.js("openAcceptanceDialog()")
    await tab.warten("document.getElementById('acceptanceDialog').open")
    await asyncio.sleep(0.3)
    p.pruefe("412 px dunkel: Dialog ohne waagrechten Scrollbalken", await tab.js(
        "(()=>{const d=document.querySelector('#acceptanceDialog .dialog');return d.scrollWidth<=d.clientWidth+1})()"), True)
    p.pruefe("412 px dunkel: Text lesbar", await tab.js(
        "(()=>{const s=getComputedStyle(document.getElementById('acceptanceDialog'));return s.color!==s.backgroundColor})()"), True)
    await tab.bild("6_dialog_dunkel_412")
    await tab.js("closeAcceptanceDialog();document.getElementById('acceptanceCard').scrollIntoView()")
    await asyncio.sleep(0.2)
    await tab.bild("7_abnahmen_dunkel_412")
    p.pruefe("412 px: keine JS-Fehler", tab.fehler, [])

    # --- Monteurin -----------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.oeffnen("/mobil", "document.body && document.readyState==='complete'")
    p.pruefe("Monteurin: API der Abnahme gesperrt", await tab.js(
        f"Promise.all(['/api/orders/{auftrag}/acceptances','/api/orders/{auftrag}/acceptance-options',"
        f"'/api/orders/{auftrag}/warranty-changes','/api/properties/{seed['objekt']}/acceptance-warranties',"
        f"'/api/roof-areas/{sued}/acceptance-warranties'].map(u=>fetch(u).then(r=>r.status)))"), [403] * 5)
    await tab.oeffnen(url, "document.body && document.readyState==='complete'")
    p.pruefe("Monteurin: Auftragsseite gesperrt, keine Abnahme-Karte", await tab.js(
        "[!!document.getElementById('acceptanceCard'), document.title]"), [False, "DACHKONZEPTE ERP – Kein Zugriff"])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Abnahme und Gewährleistung (1.8.46)", uhr="10:00"))
