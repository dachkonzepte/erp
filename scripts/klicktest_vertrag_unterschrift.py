"""Klicktest: Unterschrift unter dem Vertrag und gemeinsame Zeichenfläche (1.8.34, Stufe 2b, Runde 2b-1b Teil 2b).

Gezeichnet wird mit echten Mausereignissen über CDP auf die Zeichenflächen, im dunklen Theme (die Fläche muss
dort hell mit dunklem Strich sein) und zum Schluss hell:

    Klara Kundin  Auftrag mit Fassung 1, Angebot nach der Beauftragung geändert: vorher "Übernehmen" und
                  "Vertragsgrundlage ändern" sichtbar. Dialog "Auf diesem Gerät unterschreiben": Fläche weiß,
                  Strich dunkel, ohne Zeichnung abgewiesen, Kunde und Betrieb zeichnen, vorzeitiger Beginn
                  angekreuzt. Danach: Karte "Unterschrieben", Ankreuzfeld, Widerrufsfrist mit "verlangt",
                  Unterschriftsblatt (PDF, Prüfsumme wie in der Ablage), kein "Übernehmen", keine Änderung der
                  Grundlage, keine neue Fassung; Monteur 403.
    Paul Papier   Papier-Scan: ohne übertragenes Ankreuzfeld abgewiesen, mit "nicht angekreuzt" eingetragen,
                  Widerrufsfrist "nicht verlangt"; 412 px ohne seitliches Scrollen.
    Checkliste    Unterschrift über die gemeinsame Fläche (Büro, dunkel), danach gespeichert.
    Einsatzbericht  Monteur und Kunde nacheinander auf derselben Fläche (220 px hoch, dunkel weiß), danach
                  unterschrieben.
    Vorlage       Administratorin: Kennzeichen "= Verlangen des vorzeitigen Beginns" am Ankreuzfeld gesetzt, an einem
                  Abschnitt ohne Ankreuzfeld abgewiesen, Ändern des Kennzeichens lässt die Prüfung stehen.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_vertrag_unterschrift.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID
beenden): siehe scripts/cdp_klicktest.py.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.checklist_templates import add_field, create_template, publish_draft
    from app.checklists import create_checklist
    from app.contract_templates import save_template
    from app.contract_versions import freeze_contract
    from app.models import AppUser, Customer, Employee, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.service_reports import create_report

    karl = Employee(employee_number="E-1", first_name="Bert", last_name="Büro", employee_group="gewerblich", active=True,
                    hourly_wage=Decimal("22.00"))
    db.add(karl); db.flush()
    bert = AppUser(username="bert", display_name="Bert Büro", role="buero_auftrag", employee_id=karl.id, password_hash=k.passwort())
    max_ = AppUser(username="max", display_name="Max Monteur", role="field", password_hash=k.passwort())
    ada = AppUser(username="ada", display_name="Ada Admin", role="admin", password_hash=k.passwort())
    db.add_all([bert, max_, ada]); db.flush()
    save_template(db, "bgb_vob_c_4_5", title="Bauvertrag {auftragsnummer}", sections=[
        {"heading": "§ 1 Parteien", "body_text": "Zwischen {firmenname} und {kundenname}."},
        {"heading": "§ 2 Vergütung", "body_text": "Auftragssumme {auftragssumme_brutto}."},
        {"heading": "Widerrufsbelehrung", "body_text": "Sie haben das Recht, binnen vierzehn Tagen …", "consumer_only": True},
        {"heading": "Vorzeitiger Beginn", "body_text": "Ich verlange ausdrücklich, dass vor Ende der Widerrufsfrist begonnen wird.",
         "consumer_only": True, "with_checkbox": True, "early_start": True},
    ], reviewed_on=berlin_today(), reviewed_by="RA Beispiel")

    def auftrag(name, nr, *, angebot_danach_geaendert=False):
        kunde = Customer(name=name, last_name=name, is_consumer=True, email=f"{name.split()[0].lower()}@klicktest.example",
                         street="Dachweg 1", postal_code="52531", city="Übach")
        db.add(kunde); db.flush()
        projekt = Project(project_number=f"P-KT-{nr}", name=f"Dach {nr}", customer_id=kunde.id,
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-KT-{nr}", project_id=projekt.id, title=f"Dachsanierung {nr}",
                      vat_rate=Decimal("19"), status="versendet")
        db.add(quote); db.flush()
        item = QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"),
                         unit="m²", unit_price=Decimal("50"))
        db.add(item); db.commit()
        order = create_order_from_quote(
            db, quote.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
            caseworker_employee_id=None, project_manager_employee_id=None, payment_terms="14 Tage netto", remarks=None,
        )
        freeze_contract(db, load_order(db, order.id), attachment="aktuell", user_name="Bert Büro")
        if angebot_danach_geaendert:
            item.unit_price = Decimal("55")
            db.commit()
        return order

    klara = auftrag("Klara Kundin", "1", angebot_danach_geaendert=True)
    paul = auftrag("Paul Papier", "2")

    t = create_template(db, label="Abnahme light", contexts=["auftrag"])
    add_field(db, t["draft_version_id"], {"field_type": "ja_nein", "label": "Arbeiten fertig", "field_key": "fertig"})
    add_field(db, t["draft_version_id"], {"field_type": "unterschrift", "label": "Unterschrift Kunde", "field_key": "kunde",
                                          "signer_label": "Kunde"})
    vorlage = publish_draft(db, t["id"])
    cl = create_checklist(db, template_id=vorlage["id"], context_type="auftrag", order_id=paul.id,
                          created_by_employee_id=karl.id, created_by_user_id=bert.id)
    bericht = create_report(db, klara.id, "rapport", description="Sturmschaden repariert", created_by_employee_id=karl.id)

    # Seit 1.8.35 ein echtes PDF: der Scan muss sich öffnen lassen, er wird Teil der unterschriebenen Abschrift.
    from reportlab.pdfgen import canvas

    scan = Path(tempfile.mkdtemp(prefix="klicktest-scan-")) / "Vertrag_unterschrieben.pdf"
    pdf = canvas.Canvas(str(scan))
    pdf.drawString(72, 720, "Unterschriebener Vertrag (Klicktest)")
    pdf.showPage()
    pdf.save()
    return {"klara": klara.id, "paul": paul.id, "checklist": cl["id"],
            "fields": {f["field_key"]: f["id"] for f in cl["fields"]}, "report": bericht["id"], "scan": str(scan),
            "cookies": {"bert": k.cookies(bert), "max": k.cookies(max_), "ada": k.cookies(ada)}}


KARTE = "document.getElementById('contractCard').textContent"
WEISS = "rgb(255, 255, 255)"


async def _zeichnen(tab, selector: str) -> None:
    """Zeichnet mit echten Mausereignissen (über CDP, daraus macht Chrome Zeigerereignisse) quer über die Fläche."""
    await tab.js(f"document.querySelector('{selector}').scrollIntoView({{block:'center'}}); true")
    await asyncio.sleep(0.2)
    r = await tab.js(f"(()=>{{const r=document.querySelector('{selector}').getBoundingClientRect();return [r.left,r.top,r.width,r.height]}})()")
    x0, y0 = r[0] + 25, r[1] + r[3] / 2
    await tab.cmd("Input.dispatchMouseEvent", type="mousePressed", x=x0, y=y0, button="left", buttons=1, clickCount=1)
    for i in range(1, 14):
        await tab.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=x0 + i * 14, y=y0 + (14 if i % 2 else -14), button="left", buttons=1)
    await tab.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=x0 + 190, y=y0, button="left", buttons=0, clickCount=1)


def _hell_und_dunkel_strich(selector: str) -> str:
    """Hintergrund der Fläche und Farbe des dunkelsten gezeichneten Pixels (Strich #111 erwartet)."""
    return (f"(()=>{{const c=document.querySelector('{selector}');const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;"
            "let min=255,ink=0;for(let i=0;i<d.length;i+=4){if(d[i+3]>200){ink++;min=Math.min(min,d[i])}}"
            "return [getComputedStyle(c).backgroundColor, ink>20, min<40]})()")


def _sha_js(url: str) -> str:
    return (f"(async()=>{{const r=await fetch('{url}');const h=await crypto.subtle.digest('SHA-256',await r.arrayBuffer());"
            "return [r.status,r.headers.get('content-type'),[...new Uint8Array(h)].map(b=>b.toString(16).padStart(2,'0')).join('')]})()")


async def _datei_setzen(tab, selector: str, pfad: str) -> None:
    doc = await tab.cmd("DOM.getDocument", depth=1)
    node = await tab.cmd("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
    await tab.cmd("DOM.setFileInputFiles", files=[pfad], nodeId=node["nodeId"])


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.__confirms=[];window.confirm=m=>{window.__confirms.push(String(m));return true};"
                         "window.alert=m=>console.error('alert(): '+m)")
    await tab.anmelden(seed["cookies"]["bert"])
    await tab.fenster(1280, 960)
    klara, paul = seed["klara"], seed["paul"]
    api = f"fetch('/api/orders/{klara}/contract').then(r=>r.json()).then(d=>d.contract)"

    # --- Klara: vor der Unterschrift ------------------------------------------------------------------
    await tab.oeffnen(f"/orders/{klara}", "document.readyState==='complete'")
    await tab.js("localStorage.setItem('erp_theme','dark'); true")
    await tab.oeffnen(f"/orders/{klara}", "!!document.getElementById('contractSignBtn')")
    p.pruefe("Dunkel: Theme gesetzt", await tab.js("document.documentElement.getAttribute('data-theme')"), "dark")
    p.pruefe("Vorher: 'Übernehmen' sichtbar", await tab.js("!!document.querySelector('#syncCard button')"), True)
    p.pruefe("Vorher: Vertragsgrundlage änderbar", await tab.js("getComputedStyle(document.getElementById('contractBasisEdit')).display!=='none'"), True)
    karte = await tab.js(KARTE) or ""
    p.pruefe("Vorher: Unterschrift und Papier angeboten",
             all(x in karte for x in ("Auf diesem Gerät unterschreiben", "Auf Papier unterschrieben")), True)

    await tab.js("document.getElementById('contractSignBtn').click(); true")
    await tab.warten("document.getElementById('signDialog').open")
    p.pruefe("Dialog: Ankreuzfeld mit Text", "vor Ende der Widerrufsfrist" in (await tab.js("document.getElementById('signBoxes').textContent") or ""), True)
    p.pruefe("Dialog: Ankreuzfeld nicht vorbelegt", await tab.js("document.querySelector('#signBoxes input').checked"), False)
    p.pruefe("Dialog: Name Betrieb vorbelegt", await tab.js("document.getElementById('signNameCompany').value"), "Bert Büro")
    await tab.js("document.getElementById('signSubmit').click(); true")
    p.pruefe("Ohne Zeichnung abgewiesen", await tab.js("document.getElementById('signStatus').textContent"),
             "Bitte zuerst den Kunden unterschreiben lassen.")
    await _zeichnen(tab, "#signPadCustomer")
    await _zeichnen(tab, "#signPadCompany")
    flaeche = await tab.js(_hell_und_dunkel_strich("#signPadCustomer"))
    p.pruefe("Dunkel: Fläche weiß, Strich dunkel", flaeche, [WEISS, True, True])
    await tab.bild("klara_dialog_dunkel")
    await tab.js("document.getElementById('signNameCustomer').value='Klara Kundin';"
                 "document.querySelector('#signBoxes input').click();"
                 "document.getElementById('signSubmit').click(); true")
    await tab.warten("!document.getElementById('signDialog').open && document.getElementById('contractCard').textContent.includes('Unterschrieben am')", 20)
    confirms = await tab.js("window.__confirms") or []
    p.pruefe("Rückfrage nennt Ankreuzfeld 'angekreuzt'", bool(confirms) and "angekreuzt" in confirms[-1] and "verbindlich" in confirms[-1], True)
    karte = await tab.js(KARTE) or ""
    p.pruefe("Danach: Karte 'Unterschrieben' mit Namen",
             all(x in karte for x in ("Unterschrieben am", "auf dem Gerät", "Kunde: Klara Kundin", "Betrieb: Bert Büro")), True)
    p.pruefe("Danach: Ankreuzfeld angekreuzt", "Vorzeitiger Beginn – Ich verlange ausdrücklich" in karte and "– angekreuzt" in karte, True)
    p.pruefe("Danach: Widerrufsfrist mit 'verlangt'",
             "endet voraussichtlich am" in karte and "Vorzeitiger Beginn wurde verlangt" in karte, True)
    p.pruefe("Danach: kein 'Übernehmen'", await tab.js("!document.querySelector('#syncCard button')"), True)
    p.pruefe("Danach: Quellangebot-Karte erklärt die Sperre", "Abgleich mit dem Angebot ist gesperrt" in (await tab.js("document.getElementById('syncCard').textContent") or ""), True)
    p.pruefe("Danach: Vertragsgrundlage nicht änderbar",
             await tab.js("getComputedStyle(document.getElementById('contractBasisEdit')).display==='none' && document.getElementById('contractBasisLocked').textContent.includes('unterschrieben')"), True)
    p.pruefe("Danach: keine neue Fassung, Abschrift versendbar",
             ["Neue Fassung anlegen" in karte, "Unterschriebene Abschrift (Fassung 1) per E-Mail senden" in karte], [False, True])
    vertrag = await tab.js(api)
    sig = vertrag["signature"]
    blatt = await tab.js(_sha_js(f"/api/sent-documents/{sig['document']['id']}/file"))
    p.pruefe("Unterschriftsblatt: PDF, Prüfsumme wie in der Ablage", blatt, [200, "application/pdf", sig["document"]["sha256"]])
    p.pruefe("Unterschriftsblatt-Link auf der Karte",
             await tab.js(f"!!document.querySelector('#contractCard a[href=\"/api/sent-documents/{sig['document']['id']}/file\"]')"), True)
    p.pruefe("API: Ankreuzfeld im unterschriebenen Inhalt", [(b["key"], b["checked"]) for b in sig["checkboxes"]], [("abschnitt-4", True)])
    p.pruefe("Klara: JS-Fehler", tab.fehler, [])
    await tab.bild("klara_unterschrieben_dunkel")

    # --- Paul: Papier ---------------------------------------------------------------------------------
    await tab.oeffnen(f"/orders/{paul}", "!!document.getElementById('paperDetails')")
    await tab.js("document.getElementById('paperDetails').open=true;"
                 "document.getElementById('paperDate').value=berlinTodayIso(); true")
    await _datei_setzen(tab, "#paperScan", seed["scan"])
    await tab.js("document.querySelector('#paperDetails button').click(); true")
    p.pruefe("Papier ohne Ankreuzfeld abgewiesen", (await tab.js("document.getElementById('contractStatus').textContent") or "").startswith("Bitte jedes Ankreuzfeld übertragen"), True)
    await tab.js("document.querySelector('input[name=\"paper_abschnitt-4\"][value=\"0\"]').click();"
                 "document.querySelector('#paperDetails button').click(); true")
    # Nicht auf "Unterschrieben am" warten: so heißt auch das Datumsfeld im Papier-Formular.
    await tab.warten("document.getElementById('contractCard').textContent.includes('auf Papier (Scan)')", 20)
    karte = await tab.js(KARTE) or ""
    p.pruefe("Papier: eingetragen mit Scan", all(x in karte for x in ("auf Papier (Scan)", "Scan öffnen", "– nicht angekreuzt")), True)
    p.pruefe("Papier: Widerrufsfrist 'nicht verlangt'", "Vorzeitiger Beginn wurde nicht verlangt" in karte, True)
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/orders/{paul}", "document.getElementById('contractCard').textContent.includes('auf Papier (Scan)')")
    p.pruefe("412 px: kein seitliches Scrollen", await tab.js("document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.js("document.getElementById('contractCard').scrollIntoView(); true")
    await tab.bild("paul_papier_412")
    p.pruefe("Paul: JS-Fehler", tab.fehler, [])
    await tab.fenster(1280, 960)

    # --- Checkliste: gemeinsame Fläche ----------------------------------------------------------------
    feld = seed["fields"]["kunde"]
    await tab.oeffnen(f"/checklisten/{seed['checklist']}", f"!!document.getElementById('pad_{feld}')")
    p.pruefe("Checkliste: Fläche aus der gemeinsamen Vorlage", await tab.js(f"document.getElementById('pad_{feld}').classList.contains('dk-unterschrift')"), True)
    await _zeichnen(tab, f"#pad_{feld}")
    p.pruefe("Checkliste dunkel: Fläche weiß, Strich dunkel", await tab.js(_hell_und_dunkel_strich(f"#pad_{feld}")), [WEISS, True, True])
    await tab.js(f"document.getElementById('padName_{feld}').value='Klara Kundin';"
                 f"document.querySelector('#q_{feld} .pad-actions .btn:not(.secondary)').click(); true")
    await tab.warten(f"!document.getElementById('pad_{feld}')", 15)
    gespeichert = await tab.js(f"fetch('/api/checklists/{seed['checklist']}').then(r=>r.json()).then(d=>d.attachments.filter(a=>a.kind==='unterschrift').map(a=>a.signer_name))")
    p.pruefe("Checkliste: Unterschrift gespeichert", gespeichert, ["Klara Kundin"])
    p.pruefe("Checkliste: JS-Fehler", tab.fehler, [])

    # --- Einsatzbericht: Monteur und Kunde nacheinander ------------------------------------------------
    await tab.oeffnen(f"/orders/{klara}/service-reports", f"!!document.querySelector('button[onclick=\"openSignPanel({seed['report']})\"]')")
    await tab.js(f"document.querySelector('button[onclick=\"openSignPanel({seed['report']})\"]').click(); true")
    await tab.warten("!document.getElementById('signCard').classList.contains('hidden')")
    p.pruefe("Bericht: Fläche 220 px hoch", await tab.js("Math.round(document.getElementById('sigCanvas').getBoundingClientRect().height)"), 220)
    await tab.js("document.getElementById('signNextBtn').click(); true")
    p.pruefe("Bericht: ohne Zeichnung abgewiesen", await tab.js("document.getElementById('signStatus').textContent"), "Bitte zuerst unterschreiben.")
    await _zeichnen(tab, "#sigCanvas")
    p.pruefe("Bericht dunkel: Fläche weiß, Strich dunkel", await tab.js(_hell_und_dunkel_strich("#sigCanvas")), [WEISS, True, True])
    await tab.js("document.getElementById('signNextBtn').click(); true")
    p.pruefe("Bericht: Schritt Kunde, Fläche geleert",
             [await tab.js("document.getElementById('signHeading').textContent"), (await tab.js(_hell_und_dunkel_strich("#sigCanvas")))[1]],
             ["Unterschrift Kunde", False])
    await _zeichnen(tab, "#sigCanvas")
    await tab.js("document.getElementById('signatureName').value='Klara Kundin'; document.getElementById('signNextBtn').click(); true")
    await tab.warten("document.getElementById('signCard').classList.contains('hidden')", 15)
    status = await tab.js(f"fetch('/api/orders/{klara}/service-reports').then(r=>r.json()).then(l=>l.filter(d=>d.id==={seed['report']}).map(d=>[d.status,d.signature_name,d.installer_signature_name])[0])")
    p.pruefe("Bericht: unterschrieben (Monteur und Kunde)", status, ["unterschrieben", "Klara Kundin", "Bert Büro"])
    p.pruefe("Bericht: JS-Fehler", tab.fehler, [])

    # --- Hell, Monteur ---------------------------------------------------------------------------------
    await tab.oeffnen(f"/orders/{klara}", "document.readyState==='complete'")
    await tab.js("localStorage.setItem('erp_theme','light'); true")
    await tab.oeffnen(f"/orders/{klara}", "document.getElementById('contractCard').textContent.includes('Unterschrieben am')")
    p.pruefe("Hell: Theme gesetzt", await tab.js("document.documentElement.getAttribute('data-theme')"), "light")
    await tab.js("document.getElementById('contractCard').scrollIntoView(); true")
    await tab.bild("klara_unterschrieben_hell")
    p.pruefe("Hell: JS-Fehler", tab.fehler, [])

    # --- Vorlage: Kennzeichen "vorzeitiger Beginn" (Administratorin) ------------------------------------
    await tab.anmelden(seed["cookies"]["ada"])
    bgb = "document.querySelector('[data-ct=\"bgb_vob_c_4_5\"]')"
    bereit = "document.querySelectorAll('[data-ct]').length===3"
    await tab.oeffnen("/settings#contract-templates", bereit)
    p.pruefe("Vorlage: Ankreuzfeld als vorzeitiger Beginn gekennzeichnet",
             await tab.js(f"[...{bgb}.querySelectorAll('.ctEarly')].map(x=>x.checked)"), [False, False, False, True])
    await tab.js(f"{bgb}.querySelectorAll('.ctEarly')[0].checked=true;saveContractTemplate('bgb_vob_c_4_5'); true")
    await tab.warten(f"{bgb}.querySelector('.ctStatus').textContent.length>0")
    p.pruefe("Vorlage: Kennzeichen ohne Ankreuzfeld abgewiesen",
             "vorzeitigen Beginns" in (await tab.js(f"{bgb}.querySelector('.ctStatus').textContent") or ""), True)
    await tab.oeffnen("/settings#contract-templates", bereit)
    await tab.js(f"{bgb}.querySelectorAll('.ctEarly')[3].checked=false;saveContractTemplate('bgb_vob_c_4_5'); true")
    await tab.warten(f"{bgb}.querySelector('.ctStatus').textContent==='Gespeichert.'")
    p.pruefe("Vorlage: Kennzeichen ändern lässt die Prüfung stehen",
             ["Rechtlich geprüft" in (await tab.js(f"{bgb}.textContent") or ""), await tab.js(f"{bgb}.querySelectorAll('.ctEarly')[3].checked")],
             [True, False])
    p.pruefe("Vorlage: JS-Fehler", tab.fehler, [])
    await tab.anmelden(seed["cookies"]["max"])
    await tab.oeffnen("/mobil", "document.readyState==='complete'")
    antwort = await tab.js(f"fetch('/api/orders/{paul}/contract/sign',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}}).then(r=>r.status)")
    p.pruefe("Monteur: Unterschreiben 403", antwort, 403)


if __name__ == "__main__":
    # Feste Uhr (seit 1.8.36): /mobil meldet den Monteur ab 19 Uhr ab, die 403-Prüfung sähe abends 401.
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Unterschrift unter dem Vertrag (1.8.34)", uhr="10:00"))
