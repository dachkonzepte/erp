"""Klicktest: Mängel aus der Abnahme (1.8.49, Stufe 2c-2a).

Befüllt: Gewerbekunde (VOB/B), Objekt "Halle Nord" mit Nord, Süd, "Alt" (archiviert), fremdes Objekt mit "Fremd",
Auftrag mit Gewährleistung 48 Monate; drei Abnahmen (vor 20 Tagen mit Vorbehalt Mängel, vor 15 Tagen ohne Vorbehalt,
vor 10 Tagen verweigert); Beteiligte: Architektin ohne Vollmacht, Bauleitung mit Vollmacht zur Abnahme.

    Büro (1400 px, hell)    Karte "Abnahme": Warnung "ohne erfassten Mangel" und "+ Mangel erfassen" nur an der Abnahme
                            mit Vorbehalt und der verweigerten, nicht an der ohne Vorbehalt. Dialog: keine Vorauswahl,
                            Dachflächen nur Nord/Süd, Beschreibung Pflicht, PDF als Foto abgelehnt (Dialog bleibt offen),
                            gespeichert mit Nord, Ort, Frist und Foto -> Sprung zum Mangel, Warnung weg, "Mängel: 1".
                            Haltung "bestritten" ohne Begründung abgelehnt, mit gespeichert; Freigabe trotz "bestritten"
                            nur mit Begründung (Kulanz); Status "beseitigt", dann "Beseitigung abgenommen" durch die
                            Architektin (Warnung ohne Vollmacht) mit Begründung -> erledigt, "Nachbesserung regulär bis",
                            Aufgabe erledigt; Fotos ergänzen, seit 1.8.51 auch Belege (ohne Auswahl abgelehnt); Verlauf;
                            Aufgabentitel mit Kurzfassung; zweiter Mangel verworfen.
    Büro (1400 px, hell)    Aufgaben: die Aufgabe des offenen Mangels ohne Zuständigkeit; ihr Link springt zum Mangel.
    Büro (1400 px, hell)    Seit 1.8.55: dritter Mangel ohne Frist, beseitigt, zurück auf offen -- Feld "Neue
                            Beseitigungsfrist" nur dort; mit Frist gespeichert -> am Mangel "(neu gesetzt; beim Erfassen:
                            keine)", im Verlauf, Aufgabe "Erneut beseitigen" fällig zur neuen Frist.
    Büro (412 px, dunkel)  Auftrag: Karte lesbar, Dialog ohne waagrechten Scrollbalken.
    Monteurin               API der Mängel 403.

Feste Uhr 10:00 (cdp_klicktest.py); die Daten liegen relativ zum heutigen Tag.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_maengel.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID
beenden): siehe scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


def _bild(fmt: str, farbe=(30, 110, 160), groesse=(320, 200)) -> bytes:
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", groesse, farbe).save(buf, format=fmt)
    return buf.getvalue()


def befuellen(db, k):
    import os
    from datetime import timedelta
    from decimal import Decimal

    from app.acceptances import create_acceptance
    from app.berlin_time import berlin_today
    from app.contacts import create_contact
    from app.models import AppUser, Customer, Employee, Project, Property, Quote, QuoteItem, RoofArea
    from app.orders import create_order_from_quote
    from app.project_participants import add_participant, store_power_of_attorney
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.warranty import set_order_warranty

    heute = berlin_today()
    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich",
                   active=True, hourly_wage=Decimal("22.00"))
    olga = Employee(employee_number="E-2", first_name="Olga", last_name="Office", employee_group="angestellt",
                    active=True, hourly_wage=Decimal("25.00"))
    db.add_all([mia, olga]); db.flush()
    benutzer = {  # Olga mit Mitarbeiter -- ohne ihn verweigert GET /api/tasks dem Büro-Konto die Liste
        "buero": AppUser(username="olga", display_name="Olga Office", role="buero_auftrag", employee_id=olga.id,
                         password_hash=k.passwort()),
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id,
                       password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Uebach")
    nachbar = Property(customer_id=kunde.id, name="Nachbarhalle", street="Werkstr. 7", postal_code="52531", city="Uebach")
    db.add_all([objekt, nachbar]); db.flush()
    flaechen = {"nord": RoofArea(property_id=objekt.id, name="Nord"), "sued": RoofArea(property_id=objekt.id, name="Süd"),
                "alt": RoofArea(property_id=objekt.id, name="Alt", archived=True),
                "fremd": RoofArea(property_id=nachbar.id, name="Fremd")}
    db.add_all(flaechen.values()); db.flush()
    projekt = Project(project_number="P-KT-MNG", name="Dachsanierung Halle", customer_id=kunde.id,
                      property_id=objekt.id, status="angebot", pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(quote_number="A-KT-MNG", project_id=projekt.id, title="Dachsanierung Halle", vat_rate=Decimal("19"))
    db.add(angebot); db.flush()
    db.add(QuoteItem(quote_id=angebot.id, position_number="1", short_text="Abdichtung", quantity=Decimal("850"),
                     unit="m²", unit_price=Decimal("48.90")))
    db.commit()
    auftrag = create_order_from_quote(db, angebot.id, order_date=heute - timedelta(days=60), execution_start=None,
                                      execution_end=None, caseworker_employee_id=None, project_manager_employee_id=None,
                                      payment_terms=None, remarks=None)
    set_order_warranty(db, auftrag, work_kind="bauwerk", warranty_months=48, warranty_days=0, reason=None)
    add_participant(db, projekt, create_contact(db, {"kind": "person", "first_name": "Petra", "last_name": "Plan"}),
                    role="architekt_planer")
    bauleitung = add_participant(db, projekt, create_contact(db, {"kind": "person", "first_name": "Bernd",
                                                                   "last_name": "Bau"}),
                                 role="bauleitung_ag", acceptance_authorized=True)
    store_power_of_attorney(db, bauleitung, filename="abnahmevollmacht.pdf", data=PDF, user_name="Olga Office",
                            kind="abnahme")
    basis = {"kind": "ausdruecklich", "scope": "gesamt", "declared_by": "auftraggeber", "conduct_reason": "per E-Mail",
             "roof_area_ids": []}
    tage = {"vorbehalt": 20, "ohne": 15, "verweigert": 10}
    abnahmen = {
        "vorbehalt": create_acceptance(db, auftrag, {**basis, "accepted_on": heute - timedelta(days=20),
                                                     "result": "abgenommen", "reservation_defects": True,
                                                     "reservation_penalty": False}, [], user_id=None,
                                       user_name="Olga Office"),
        "ohne": create_acceptance(db, auftrag, {**basis, "accepted_on": heute - timedelta(days=15),
                                                "result": "abgenommen", "reservation_defects": False,
                                                "reservation_penalty": False}, [], user_id=None,
                                  user_name="Olga Office"),
        "verweigert": create_acceptance(db, auftrag, {**basis, "accepted_on": heute - timedelta(days=10),
                                                      "result": "verweigert", "reservation_defects": None,
                                                      "reservation_penalty": None}, [], user_id=None,
                                        user_name="Olga Office"),
    }
    ordner = Path(os.environ["ERP_DATA_DIR"]) / "klicktest-uploads"
    ordner.mkdir(parents=True, exist_ok=True)
    dateien = {"pdf": ordner / "Ruege.pdf", "jpg": ordner / "Mangel.jpg", "png": ordner / "Nachher.png"}
    dateien["pdf"].write_bytes(PDF)
    dateien["jpg"].write_bytes(_bild("JPEG"))
    dateien["png"].write_bytes(_bild("PNG", (160, 60, 30)))
    from app.warranty import warranty_end
    iso = lambda d: d.isoformat()  # noqa: E731
    # Regelende (Abnahme vor 20 Tagen + 48 Monate) liegt nach der Abnahme der Beseitigung (gestern) + 24 Monate.
    regulaer = warranty_end(heute - timedelta(days=20), 48, 0)
    assert regulaer > warranty_end(heute - timedelta(days=1), 24, 0)
    return {"auftrag": auftrag.id, "auftragsnummer": auftrag.order_number, "flaechen": {n: f.id for n, f in flaechen.items()},
            "abnahmen": {n: a.id for n, a in abnahmen.items()}, "tage": tage,
            "datum": {"frist": iso(heute + timedelta(days=14)), "beseitigt": iso(heute - timedelta(days=3)),
                      "neue_frist": iso(heute + timedelta(days=30)), "heute": iso(heute),
                      "abgenommen": iso(heute - timedelta(days=1)), "regulaer_ende": regulaer.strftime("%d.%m.%Y")},
            "dateien": {n: str(p) for n, p in dateien.items()},
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


async def _datei_setzen(tab, selector: str, pfad: str) -> None:
    doc = await tab.cmd("DOM.getDocument", depth=1)
    node = await tab.cmd("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
    await tab.cmd("DOM.setFileInputFiles", files=[pfad], nodeId=node["nodeId"])


BEREIT = ("!document.getElementById('acceptanceList').textContent.includes('Lädt') && "
          "!document.getElementById('defectList').textContent.includes('Lädt')")
ABNAHME = "(id=>document.querySelector(`#acceptanceList .acc-item[data-acceptance=\"${id}\"]`))"
MANGEL = "(()=>document.querySelector('#defectList .def-item'))()"


def _panel(mangel_id: int) -> str:
    return f"document.getElementById('defPanel{mangel_id}')"


async def pruefen(tab, seed, p):
    import asyncio

    auftrag, ab = seed["auftrag"], seed["abnahmen"]
    url = f"/orders/{auftrag}"
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(url, BEREIT)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen(url, BEREIT)

    # --- Abnahmen: Warnung und Knopf nur, wo Mängel hingehören ------------------------------------------------
    stand = ("[" + ",".join(f"[{ABNAHME}({ab[n]}).innerText.includes('ohne erfassten Mangel'), "
                            f"!!{ABNAHME}({ab[n]}).querySelector('button[onclick^=openDefectDialog]')]"
                            for n in ("vorbehalt", "ohne", "verweigert")) + "]")
    p.pruefe("Abnahmen: Warnung und Knopf an Vorbehalt und Verweigerung, nicht ohne Vorbehalt", await tab.js(stand),
             [[True, True], [False, False], [True, True]])
    p.pruefe("Mängel: noch keiner", await tab.js("document.getElementById('defectList').innerText"),
             "Noch kein Mangel erfasst.")
    await tab.js(f"{ABNAHME}({ab['vorbehalt']}).scrollIntoView()")
    await tab.bild("1_abnahmen_warnung_hell")

    # --- Dialog -----------------------------------------------------------------------------------------------
    await tab.js(f"{ABNAHME}({ab['vorbehalt']}).querySelector('button[onclick^=openDefectDialog]').click()")
    await tab.warten("document.getElementById('defectDialog').open")
    p.pruefe("Dialog: keine Vorauswahl", await tab.js(
        "[document.getElementById('defRoofArea').value, document.getElementById('defDue').value, "
        "document.getElementById('defDescription').value]"), ["", "", ""])
    p.pruefe("Dialog: nur Dachflächen des Objekts der Abnahme, keine archivierte", await tab.js(
        "[...document.getElementById('defRoofArea').options].map(o=>o.textContent)"),
        ["— keine Dachfläche —", "Nord", "Süd"])
    await tab.js("saveDefect(document.getElementById('defSaveBtn'))")
    p.pruefe("Dialog: Beschreibung Pflicht", await tab.js("document.getElementById('defDialogStatus').textContent"),
             "Bitte den Mangel beschreiben.")
    await tab.js("document.getElementById('defDescription').value='Anschluss an der Attika undicht';"
                 f"document.getElementById('defRoofArea').value='{seed['flaechen']['nord']}';"
                 "document.getElementById('defLocation').value='Attika West';"
                 f"document.getElementById('defDue').value='{seed['datum']['frist']}'")
    await _datei_setzen(tab, "#defPhotos", seed["dateien"]["pdf"])
    await tab.js("saveDefect(document.getElementById('defSaveBtn'))")
    await tab.warten("document.getElementById('defDialogStatus').textContent.startsWith('Fehler')")
    p.pruefe("Dialog: PDF als Foto abgelehnt, Dialog bleibt offen", await tab.js(
        "[document.getElementById('defDialogStatus').textContent, document.getElementById('defectDialog').open]"),
        ["Fehler: „Ruege.pdf“: Ein Foto muss JPEG, PNG oder WebP sein – ein PDF bitte als Beleg.", True])
    await _datei_setzen(tab, "#defPhotos", seed["dateien"]["jpg"])
    await _datei_setzen(tab, "#defReceipts", seed["dateien"]["pdf"])
    await tab.bild("2_dialog_hell")
    await tab.js("saveDefect(document.getElementById('defSaveBtn'))")
    await tab.warten("!document.getElementById('defectDialog').open && document.querySelectorAll('#defectList .def-item').length===1")
    mangel_id = await tab.js("Number(document.querySelector('#defectList .def-item').dataset.defect)")
    p.pruefe("Mangel: Kopf, Stand, Frist, Dateien, Aufgabe", await tab.js(
        f"(t=>[t.split('\\n')[0], t.includes('offen'), t.includes('Haltung: offen'), t.includes('nicht freigegeben'), "
        f"t.includes('Beseitigungsfrist: '), (t.match(/SHA-256/g)||[]).length, t.includes('Aufgabe (Mangel beseitigen): Mangel aus Abnahme')])"
        f"({MANGEL}.innerText)"),
        [f"Mangel Nr. {mangel_id} · Nord · Attika West", True, True, True, True, 2, True])
    p.pruefe("Mangel: Sprung zum neuen Eintrag (sichtbar)", await tab.js(
        f"(r=>r.top>=0&&r.bottom<=innerHeight)({MANGEL}.getBoundingClientRect())"), True)
    await tab.warten(f"!{ABNAHME}({ab['vorbehalt']}).innerText.includes('ohne erfassten Mangel')")
    p.pruefe("Abnahme: Warnung weg, 'Mängel: 1 erfasst'", await tab.js(
        f"[{ABNAHME}({ab['vorbehalt']}).innerText.includes('ohne erfassten Mangel'), "
        f"{ABNAHME}({ab['vorbehalt']}).innerText.includes('Mängel: 1 erfasst')]"), [False, True])
    p.pruefe("Datei: Foto mit nosniff", await tab.js(
        f"fetch({MANGEL}.querySelector('a[href*=\"/files/\"]').href).then(r=>[r.status,r.headers.get('content-type'),"
        "r.headers.get('x-content-type-options')])"), [200, "image/jpeg", "nosniff"])
    await tab.bild("3_mangel_gespeichert_hell")

    # --- Haltung, Freigabe -------------------------------------------------------------------------------------
    await tab.js(f"defOpen({mangel_id},'haltung')")
    await tab.js(f"{_panel(mangel_id)}.querySelector('input[value=bestritten]').click();"
                 f"{_panel(mangel_id)}.querySelector('button').click()")
    await tab.warten(f"document.getElementById('defPanelStatus{mangel_id}').textContent.startsWith('Fehler')")
    p.pruefe("Haltung: bestritten ohne Begründung abgelehnt", await tab.js(
        f"document.getElementById('defPanelStatus{mangel_id}').textContent"),
        "Fehler: Bitte begründen, warum der Mangel bestritten wird.")
    await tab.js(f"document.getElementById('defReason{mangel_id}').value='Abnutzung durch den Nutzer';"
                 f"{_panel(mangel_id)}.querySelector('button').click()")
    await tab.warten(f"{MANGEL}.innerText.includes('Haltung: bestritten')")
    await tab.js(f"defOpen({mangel_id},'freigabe')")
    p.pruefe("Freigabe: Hinweis auf 'bestritten'", await tab.js(f"{_panel(mangel_id)}.innerText.includes('Der Mangel ist bestritten')"), True)
    await tab.js(f"{_panel(mangel_id)}.querySelector('button').click()")
    await tab.warten(f"document.getElementById('defPanelStatus{mangel_id}').textContent.startsWith('Fehler')")
    p.pruefe("Freigabe trotz 'bestritten' ohne Begründung abgelehnt", await tab.js(
        f"document.getElementById('defPanelStatus{mangel_id}').textContent.includes('Kulanz')"), True)
    await tab.js(f"document.getElementById('defReason{mangel_id}').value='Kulanz, Stammkunde';"
                 f"{_panel(mangel_id)}.querySelector('button').click()")
    await tab.warten(f"{MANGEL}.innerText.includes('zur Beseitigung freigegeben')")
    p.pruefe("Freigabe: gesetzt, Haltung bleibt 'bestritten'", await tab.js(
        f"[{MANGEL}.innerText.includes('zur Beseitigung freigegeben'), {MANGEL}.innerText.includes('Haltung: bestritten')]"),
        [True, True])

    # --- Status: beseitigt, Beseitigung abgenommen --------------------------------------------------------------
    await tab.js(f"defOpen({mangel_id},'status')")
    await tab.warten(f"document.getElementById('defPart{mangel_id}').options.length>1")
    p.pruefe("Status: Auswahl ohne Vorauswahl, nur mögliche Schritte", await tab.js(
        f"[[...{_panel(mangel_id)}.querySelectorAll('input[name=defNext{mangel_id}]')].map(i=>i.parentElement.textContent.trim()), "
        f"{_panel(mangel_id)}.querySelectorAll('input:checked').length]"),
        [["beseitigt", "erledigt ohne Beseitigung"], 0])
    await tab.js(f"{_panel(mangel_id)}.querySelector('input[value=beseitigt]').click();"
                 f"document.getElementById('defDate{mangel_id}').value='{seed['datum']['beseitigt']}';"
                 f"[...{_panel(mangel_id)}.querySelectorAll('button')].pop().click()")
    await tab.warten(f"{MANGEL}.innerText.split('\\n')[1].startsWith('beseitigt')")
    await tab.js(f"defOpen({mangel_id},'status')")
    await tab.warten(f"document.getElementById('defPart{mangel_id}').options.length>1")
    await tab.js(f"{_panel(mangel_id)}.querySelector('input[value=beseitigung_abgenommen]').click();"
                 f"document.getElementById('defDate{mangel_id}').value='{seed['datum']['abgenommen']}';"
                 f"{_panel(mangel_id)}.querySelector('input[name=defDecl{mangel_id}][value=beteiligter]').click()")
    await tab.js(f"(s=>{{s.selectedIndex=1;s.dispatchEvent(new Event('change'))}})(document.getElementById('defPart{mangel_id}'))")
    p.pruefe("Abgenommen durch Architektin: Warnung ohne Vollmacht", await tab.js(
        f"[document.getElementById('defPart{mangel_id}').selectedOptions[0].textContent, "
        f"document.getElementById('defPoa{mangel_id}').hidden]"), ["Petra Plan (Architekt/Planer)", False])
    await tab.js(f"[...{_panel(mangel_id)}.querySelectorAll('button')].pop().click()")
    await tab.warten(f"document.getElementById('defPanelStatus{mangel_id}').textContent.startsWith('Fehler')")
    p.pruefe("Abgenommen ohne Beleg und Begründung abgelehnt", await tab.js(
        f"document.getElementById('defPanelStatus{mangel_id}').textContent.includes('Nachweis')"), True)
    await tab.js(f"document.getElementById('defReason{mangel_id}').value='Abnahme vor Ort, Protokoll folgt';"
                 f"[...{_panel(mangel_id)}.querySelectorAll('button')].pop().click()")
    await tab.warten(f"{MANGEL}.innerText.split('\\n')[1].startsWith('Beseitigung abgenommen')")
    p.pruefe("Erledigt: Nachbesserung regulär bis (VOB/B), Aufgabe erledigt, keine Freigabe/kein Status mehr", await tab.js(
        f"(t=>[t.includes('Nachbesserung regulär bis'), t.includes('Prüfung: Prüfsumme stimmt'), /Aufgabe \\(Beseitigung abnehmen lassen\\): .* – (Erledigt|erledigt)/.test(t), "
        f"!!{MANGEL}.querySelector('button[onclick*=freigabe]'), !!{MANGEL}.querySelector('button[onclick*=status]')])"
        f"({MANGEL}.innerText)"), [True, True, True, False, False])
    p.pruefe("Nachbesserung: das spätere ist das reguläre Ende", await tab.js(
        f"{MANGEL}.innerText.includes('Nachbesserung regulär bis {seed['datum']['regulaer_ende']}')"), True)

    # --- Fotos ergänzen, Verlauf ---------------------------------------------------------------------------------
    await tab.js(f"defOpen({mangel_id},'fotos')")
    await _datei_setzen(tab, f"#defMorePhotos{mangel_id}", seed["dateien"]["png"])
    await tab.js(f"{_panel(mangel_id)}.querySelector('button').click()")
    await tab.warten(f"{MANGEL}.querySelector('summary').textContent==='Verlauf (5)'")
    # Seit 1.8.51: Belege nachreichen wie Fotos.
    await tab.js(f"defOpen({mangel_id},'belege')")
    await tab.js(f"{_panel(mangel_id)}.querySelector('button').click()")
    p.pruefe("Belege ergänzen: ohne Auswahl abgelehnt", await tab.js(
        f"document.getElementById('defPanelStatus{mangel_id}').textContent"), "Bitte mindestens einen Beleg wählen.")
    await _datei_setzen(tab, f"#defMoreReceipts{mangel_id}", seed["dateien"]["pdf"])
    await tab.js(f"{_panel(mangel_id)}.querySelector('button').click()")
    await tab.warten(f"{MANGEL}.querySelector('summary').textContent==='Verlauf (6)'")
    await tab.js(f"{MANGEL}.querySelector('details').open=true")
    p.pruefe("Verlauf: sechs Einträge in Reihenfolge", await tab.js(
        f"[...{MANGEL}.querySelectorAll('.def-event')].map(e=>e.innerText.split('\\n')[0].split(' am ')[0])"),
        ["Haltung: offen → bestritten", "Freigabe zur Beseitigung: zur Beseitigung freigegeben",
         "Status: offen → beseitigt", "Status: beseitigt → Beseitigung abgenommen", "1 Foto ergänzt",
         "1 Beleg ergänzt"])
    p.pruefe("Verlauf: der nachgereichte Beleg ist abrufbar (PDF, nosniff)", await tab.js(
        f"fetch([...{MANGEL}.querySelectorAll('.def-event')].pop().querySelector('a[href*=\"/files/\"]').href)"
        ".then(r=>[r.status,r.headers.get('content-type'),r.headers.get('x-content-type-options')])"),
        [200, "application/pdf", "nosniff"])
    # Seit 1.8.54 ist die aktuelle Aufgabe nach "beseitigt" die "Beseitigung abnehmen lassen" -- Titel mit Kurzfassung.
    p.pruefe("Aufgabe: Titel mit Kurzfassung", await tab.js(
        f"{MANGEL}.innerText.includes('Aufgabe (Beseitigung abnehmen lassen): Beseitigung abnehmen lassen – "
        f"Mangel aus Abnahme {seed['auftragsnummer']} – Nord: Anschluss an der Attika undicht')"),
        True)
    p.pruefe("Verlauf: Architektin ohne Vollmacht gekennzeichnet", await tab.js(
        f"{MANGEL}.querySelector('details').innerText.includes('Petra Plan (Architekt/Planer) ⚠ ohne Vollmacht zur Abnahme')"), True)
    await tab.js(f"{MANGEL}.scrollIntoView()")
    await tab.bild("4_mangel_erledigt_verlauf_hell")

    # --- zweiter Mangel an der verweigerten Abnahme, verworfen -----------------------------------------------------
    await tab.js(f"{ABNAHME}({ab['verweigert']}).querySelector('button[onclick^=openDefectDialog]').click()")
    await tab.warten("document.getElementById('defectDialog').open")
    await tab.js("document.getElementById('defDescription').value='Rinne Süd fehlt';saveDefect(document.getElementById('defSaveBtn'))")
    await tab.warten("!document.getElementById('defectDialog').open && document.querySelectorAll('#defectList .def-item').length===2")
    zweiter = await tab.js("Number([...document.querySelectorAll('#defectList .def-item')].pop().dataset.defect)")
    await tab.js(f"defOpen({zweiter},'verwerfen');{_panel(zweiter)}.querySelector('button').click()")
    p.pruefe("Verwerfen ohne Begründung abgelehnt", await tab.js(
        f"document.getElementById('defPanelStatus{zweiter}').textContent"), "Bitte begründen, warum der Mangel verworfen wird.")
    await tab.js(f"document.getElementById('defReason{zweiter}').value='doppelt erfasst';{_panel(zweiter)}.querySelector('button').click()")
    await tab.warten(f"document.getElementById('mangel-{zweiter}').classList.contains('discarded')")
    p.pruefe("Verworfen: gekennzeichnet, keine Aktionen, Abnahme warnt wieder", await tab.js(
        f"[document.getElementById('mangel-{zweiter}').innerText.includes('doppelt erfasst'), "
        f"document.getElementById('mangel-{zweiter}').querySelectorAll('.def-actions').length]"), [True, 0])
    await tab.warten(f"{ABNAHME}({ab['verweigert']}).innerText.includes('ohne erfassten Mangel')")
    p.pruefe("Büro Auftrag: keine JS-Fehler", tab.fehler, [])

    # --- Aufgaben: Verweis zurück zum Mangel ------------------------------------------------------------------------
    antwort = await tab.js("fetch('/api/tasks?unassigned_only=true&include_archived=true').then(async r=>[r.status, await r.json()])")
    aufgabe = [[x["assigned_employee_id"], x["status_is_done"], x["source_url"], x["due_date"]]
               for x in (antwort[1] if antwort and antwort[0] == 200 else []) if x.get("source_module") == "maengel"]
    if not aufgabe:
        print("Antwort /api/tasks:", str(antwort)[:500])
    # Seit 1.8.54 drei: "beseitigt" erledigt die erste des ersten Mangels und legt "Beseitigung abnehmen lassen" an.
    reihe = lambda x: (x[2], x[3] or "")  # noqa: E731
    p.pruefe("Aufgaben: drei aus Mängeln, ohne Zuständigkeit, alle erledigt (abgenommen bzw. verworfen)",
             sorted(aufgabe, key=reihe), sorted([
                 [None, True, f"/orders/{auftrag}#mangel-{mangel_id}", seed["datum"]["frist"]],
                 [None, True, f"/orders/{auftrag}#mangel-{mangel_id}", None],
                 [None, True, f"/orders/{auftrag}#mangel-{zweiter}", None]], key=reihe))
    await tab.oeffnen(f"/orders/{auftrag}#mangel-{mangel_id}", BEREIT + " && document.getElementById('mangel-" + str(mangel_id) + "')")
    await asyncio.sleep(0.4)
    p.pruefe("Verweis aus der Aufgabe: springt zum Mangel", await tab.js(
        f"(r=>r.top>=0&&r.bottom<=innerHeight)(document.getElementById('mangel-{mangel_id}').getBoundingClientRect())"), True)

    # --- seit 1.8.55: zurück auf offen mit neuer Frist -------------------------------------------------------------
    dritter = await tab.js(
        f"(()=>{{const f=new FormData();f.append('data',JSON.stringify({{description:'Kehle Ost undicht'}}));"
        f"return fetch('/api/order-acceptances/{ab['vorbehalt']}/defects',{{method:'POST',body:f}}).then(r=>r.json()).then(j=>j.id)}})()")
    await tab.oeffnen(url, BEREIT + f" && document.getElementById('mangel-{dritter}')")
    m3 = f"document.getElementById('mangel-{dritter}')"
    await tab.js(f"defOpen({dritter},'status')")
    await tab.warten(f"document.getElementById('defPart{dritter}').options.length>1")
    await tab.js(f"{_panel(dritter)}.querySelector('input[value=beseitigt]').click();"
                 f"document.getElementById('defDate{dritter}').value='{seed['datum']['heute']}';"
                 f"[...{_panel(dritter)}.querySelectorAll('button')].pop().click()")
    await tab.warten(f"{m3}.innerText.split('\\n')[1].startsWith('beseitigt')")
    await tab.js(f"defOpen({dritter},'status')")
    await tab.warten(f"document.getElementById('defPart{dritter}').options.length>1")
    await tab.js(f"{_panel(dritter)}.querySelector('input[value=beseitigung_abgenommen]').click()")
    sichtbar_abgenommen = await tab.js(f"document.getElementById('defDueBox{dritter}').hidden")
    await tab.js(f"{_panel(dritter)}.querySelector('input[value=offen]').click()")
    p.pruefe("Neue Frist: Feld nur bei 'zurück auf offen', optional, nennt die bisherige", [sichtbar_abgenommen, await tab.js(
        f"[document.getElementById('defDueBox{dritter}').hidden, document.querySelector('label[for=defDue{dritter}]').textContent]")],
        [True, [False, "Neue Beseitigungsfrist (optional – leer: es bleibt ohne Frist)"]])
    await tab.js(f"document.getElementById('defDue{dritter}').value='{seed['datum']['neue_frist']}';"
                 f"document.getElementById('defReason{dritter}').value='Nachbesserung misslungen';"
                 f"[...{_panel(dritter)}.querySelectorAll('button')].pop().click()")
    await tab.warten(f"{m3}.innerText.split('\\n')[1].startsWith('offen')")
    await tab.js(f"{m3}.querySelector('details').open=true")
    neu = "{2}.{1}.{0}".format(*seed["datum"]["neue_frist"].split("-"))
    p.pruefe("Neue Frist: am Mangel mit Hinweis, im Verlauf, Prüfsumme stimmt", await tab.js(
        f"(t=>[t.includes('Beseitigungsfrist: {neu} (neu gesetzt; beim Erfassen: keine)'), "
        f"{m3}.querySelector('[data-neue-frist]').textContent, t.includes('Prüfung: Prüfsumme stimmt') || !t.includes('Prüfung:')])"
        f"({m3}.innerText)"), [True, f"Neue Beseitigungsfrist: {neu}", True])
    antwort = await tab.js("fetch('/api/tasks?unassigned_only=true').then(r=>r.json())")
    erneut = [[x["title"].split(" – ")[0], x["due_date"]] for x in (antwort or [])
              if x.get("source_url") == f"/orders/{auftrag}#mangel-{dritter}" and not x["status_is_done"]]
    p.pruefe("Neue Frist: Aufgabe 'Erneut beseitigen' fällig zur neuen Frist", erneut,
             [["Erneut beseitigen", seed["datum"]["neue_frist"]]])
    await tab.js(f"{m3}.scrollIntoView()")
    await tab.bild("4b_neue_frist_hell")
    p.pruefe("Neue Frist: keine JS-Fehler", tab.fehler, [])

    # --- 412 px, dunkel ----------------------------------------------------------------------------------------------
    await tab.fenster(412, 900, mobil=True)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(url, BEREIT)
    p.pruefe("412 px dunkel: Thema", await tab.js("document.documentElement.dataset.theme"), "dark")
    await tab.js(f"openDefectDialog({ab['vorbehalt']})")
    await tab.warten("document.getElementById('defectDialog').open")
    await asyncio.sleep(0.3)
    p.pruefe("412 px dunkel: Dialog ohne waagrechten Scrollbalken", await tab.js(
        "(()=>{const d=document.querySelector('#defectDialog .dialog');return d.scrollWidth<=d.clientWidth+1})()"), True)
    await tab.bild("5_dialog_dunkel_412")
    await tab.js("closeDefectDialog();document.getElementById('defectCard').scrollIntoView()")
    await asyncio.sleep(0.2)
    p.pruefe("412 px dunkel: Karte ohne waagrechten Scrollbalken", await tab.js(
        "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.bild("6_maengel_dunkel_412")
    p.pruefe("412 px: keine JS-Fehler", tab.fehler, [])

    # --- Monteurin ------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.oeffnen("/mobil", "document.body && document.readyState==='complete'")
    p.pruefe("Monteurin: API der Mängel gesperrt", await tab.js(
        f"Promise.all(['/api/orders/{auftrag}/defects','/api/order-acceptances/{ab['vorbehalt']}/defect-options',"
        f"'/api/defects/{mangel_id}/files/1'].map(u=>fetch(u).then(r=>r.status)))"), [403] * 3)
    p.pruefe("Monteurin: Haltung setzen gesperrt", await tab.js(
        f"fetch('/api/defects/{mangel_id}/stance',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        "body:JSON.stringify({stance:'anerkannt',reason:null})}).then(r=>r.status)"), 403)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Mängel aus der Abnahme (1.8.49, Frist 1.8.55)", uhr="10:00"))
