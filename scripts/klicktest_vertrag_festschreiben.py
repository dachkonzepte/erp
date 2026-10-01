"""Klicktest: Vertrag festschreiben und versenden (1.8.33, Stufe 2b, Runde 2b-1b Teil 2, Punkte 1–3).

Prüft die Karte "Vertrag" der Auftragsseite so, wie das Büro sie benutzt -- drei Aufträge mit
geprüfter Vorlage:

    Petra Privat    Angebot nie versendet: Anlage bitte bewusst wählen (nur "heutiger Stand"),
                    Festschreiben ohne Wahl wird abgewiesen, mit Wahl Fassung 1; Fallfelder danach nur
                    noch lesbar, PDF aus der Ablage (Kopfzeile X-DK-Ablage, SHA-256 wie die Fassung);
                    Versand an einen SMTP-Empfänger im Skript (An vorbelegt, CC), Anhang = abgelegte
                    Fassung, Versandverlauf; neue Fassung, Fallfeld ändern, Fassung 2, Fassung 1
                    abgelöst
    Sven Sender     Angebot versendet und unverändert: Anlage ohne Rückfrage, Hinweis "entspricht dem
                    heutigen Stand"
    Carla Geändert  Angebot nach dem Versand geändert: zwei Möglichkeiten, die versendete gewählt
    dazu            Versandprotokoll verlinkt den Vertrag auf den Auftrag, E-Mail-Vorlage "Vertrag" in
                    den Einstellungen, hell/dunkel, 412 px (Karte ohne seitliches Scrollen), Monteur 403

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_vertrag_festschreiben.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import hashlib
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_versandprotokoll import POSTFACH, _smtp_starten  # noqa: E402


def befuellen(db, k):
    from datetime import date, datetime
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.contract_templates import save_template
    from app.email_sending import update_smtp_settings
    from app.models import AppUser, Customer, EmailDispatch, Project, Quote, QuoteItem
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.projects import load_quote
    from app.quote_framed_pdf import build_quote_framed_pdf
    from app.sent_documents import store_sent_document

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        smtp_port = s.getsockname()[1]
    update_smtp_settings(db, host="127.0.0.1", port=smtp_port, username="buero", encryption="none",
                         sender_email="buero@klicktest.example", sender_name="Klicktest GmbH", password="pw")
    bert = AppUser(username="bert", display_name="Bert Büro", role="buero_auftrag", password_hash=k.passwort())
    max_ = AppUser(username="max", display_name="Max Monteur", role="field", password_hash=k.passwort())
    db.add_all([bert, max_]); db.flush()

    save_template(db, "bgb_vob_c_4_5", title="Bauvertrag {auftragsnummer}", sections=[
        {"heading": "§ 1 Parteien", "body_text": "Zwischen {firmenname} und {kundenname}.", "consumer_only": False, "with_checkbox": False},
        {"heading": "§ 2 Vergütung", "body_text": "Auftragssumme {auftragssumme_brutto}. {abschlagsplan}", "consumer_only": False, "with_checkbox": False},
        {"heading": "§ 3 Zeit", "body_text": "{ausfuehrungszeitraum}\n{besonderheiten}", "consumer_only": False, "with_checkbox": False},
        {"heading": "Widerrufsbelehrung", "body_text": "Sie haben das Recht, binnen vierzehn Tagen …", "consumer_only": True, "with_checkbox": False},
        {"heading": None, "body_text": "Ich verlange ausdrücklich, dass vor Ende der Widerrufsfrist begonnen wird.", "consumer_only": True, "with_checkbox": True},
    ], reviewed_on=berlin_today(), reviewed_by="RA Beispiel")

    def auftrag(name, nr, *, versendet=False, danach_geaendert=False):
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
        db.add(item)
        db.commit()
        if versendet:  # so, wie send_quote_email() es ablegt -- der SMTP-Empfänger läuft erst in pruefen()
            pdf = build_quote_framed_pdf(db, load_quote(db, quote.id))
            abgelegt = store_sent_document(db, document_type="angebot", document_id=quote.id, document_number=quote.quote_number,
                                           filename=f"{quote.quote_number}.pdf", content=pdf, user_id=bert.id, user_name="Bert Büro")
            jetzt = datetime.utcnow()
            db.add(EmailDispatch(dispatch_key=f"angebot-kt-{nr}-00000001", message_ref=f"00000000-0000-0000-0000-00000000000{nr}",
                                 status="gesendet", channel="smtp", document_type="angebot", document_id=quote.id,
                                 document_number=quote.quote_number, to_recipients=kunde.email, subject=f"Angebot {quote.quote_number}",
                                 sent_document_id=abgelegt.id, created_at=jetzt, finished_at=jetzt, created_by_name="Bert Büro"))
            db.commit()
        if danach_geaendert:
            item.unit_price = Decimal("77")
            db.commit()
        return create_order_from_quote(
            db, quote.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None,
            caseworker_employee_id=None, project_manager_employee_id=None, payment_terms="14 Tage netto", remarks=None,
        )

    petra = auftrag("Petra Privat", "1")
    sven = auftrag("Sven Sender", "2", versendet=True)
    carla = auftrag("Carla Geändert", "3", versendet=True, danach_geaendert=True)
    return {"smtp_port": smtp_port, "petra": petra.id, "sven": sven.id, "carla": carla.id,
            "cookies": {"bert": k.cookies(bert), "max": k.cookies(max_)}}


async def pruefen(tab, seed, p):
    server = _smtp_starten(seed["smtp_port"])
    try:
        await _pruefen(tab, seed, p)
    finally:
        server.shutdown()


KARTE = "document.getElementById('contractCard').textContent"
STATUS = "document.getElementById('contractStatus').textContent"


def _sha_js(url: str) -> str:
    return (f"(async()=>{{const r=await fetch('{url}');const h=await crypto.subtle.digest('SHA-256',await r.arrayBuffer());"
            "return [r.status,r.headers.get('X-DK-Ablage'),[...new Uint8Array(h)].map(b=>b.toString(16).padStart(2,'0')).join('')]})()")


async def _pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.confirm=()=>true;window.alert=m=>console.error('alert(): '+m)")
    await tab.anmelden(seed["cookies"]["bert"])
    petra = seed["petra"]
    api = f"fetch('/api/orders/{petra}/contract').then(r=>r.json()).then(d=>d.contract)"

    # --- Petra: nie versendet -> bewusst wählen ------------------------------------------------------
    # Hell ausdrücklich setzen (sonst Farbschema des Rechners) -- erst nach dem ersten Laden, vorher
    # läuft localStorage auf about:blank ins Leere (Klicktest-Falle aus 1.8.16).
    await tab.oeffnen(f"/orders/{petra}", "document.readyState==='complete'")
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen(f"/orders/{petra}?hell=1", "document.querySelector('input[name=contractAttachment]')!==null")
    p.pruefe("Hell: Theme gesetzt", await tab.js("document.documentElement.getAttribute('data-theme')"), "light")
    p.pruefe("Petra: Anlage bitte wählen", "Anlage bitte bewusst wählen" in (await tab.js(KARTE) or ""), True)
    p.pruefe("Petra: Grund 'nie versendet'", "wurde nie versendet" in (await tab.js(KARTE) or ""), True)
    p.pruefe("Petra: nur 'heutiger Stand' wählbar",
             await tab.js("[...document.querySelectorAll('input[name=contractAttachment]')].map(i=>i.value+':'+i.checked).join()"), "aktuell:false")
    await tab.js("document.getElementById('contractFreezeBtn').click()")
    await tab.warten(f"{STATUS}.length>0")
    p.pruefe("Petra: ohne Wahl nicht festgeschrieben", await tab.js(STATUS), "Bitte die Anlage wählen.")
    p.pruefe("Petra: weiterhin Entwurf", await tab.js(f"{api}.then(c=>c.status)"), "entwurf")
    await tab.js("document.getElementById('cPaymentPlan').value='30 % bei Auftrag, Rest nach Abnahme';saveContract()")
    await tab.warten(f"{STATUS}==='Vertragsentwurf gespeichert.'")
    await tab.warten("document.querySelector('input[name=contractAttachment]')!==null")
    await tab.js("document.querySelector('input[name=contractAttachment][value=aktuell]').click();document.getElementById('contractFreezeBtn').click()")
    await tab.warten(f"{STATUS}==='Fassung 1 festgeschrieben.'", timeout=30)
    p.pruefe("Petra: Fassung 1 festgeschrieben", await tab.js(STATUS), "Fassung 1 festgeschrieben.")
    p.pruefe("Petra: Fallfelder nur noch lesbar", await tab.js("document.getElementById('cPaymentPlan')===null&&document.querySelectorAll('#contractBody .contract-ro').length"), 3)
    p.pruefe("Petra: Abschlagsplan eingefroren", "30 % bei Auftrag, Rest nach Abnahme" in (await tab.js(KARTE) or ""), True)
    fassung = await tab.js(f"{api}.then(c=>[c.versions[0].document.sha256,String(c.versions[0].document.id)])")
    pdf = await tab.js(_sha_js(f"/api/orders/{petra}/contract/pdf"))
    p.pruefe("Petra: PDF aus der Ablage, SHA-256 wie die Fassung", pdf, [200, fassung[1] if fassung else None, fassung[0] if fassung else None])
    p.pruefe("Petra: An vorbelegt", await tab.js("document.getElementById('contractEmailInput').value"), "petra@klicktest.example")
    p.pruefe("Petra: JS-Fehler nach Festschreiben", tab.fehler, [])
    await tab.js("document.getElementById('contractCard').scrollIntoView()")
    await tab.bild("petra_festgeschrieben_hell")

    # --- Versand -----------------------------------------------------------------------------------
    await tab.js("document.getElementById('contractCcInput').value='chef@klicktest.example';"
                 "document.querySelector('#contractBody .contract-send button').click()")
    await tab.warten(f"{STATUS}==='Versendet.'", timeout=30)
    p.pruefe("Versand: Statuszeile", await tab.js(STATUS), "Versendet.")
    p.pruefe("Versand: eine Mail", len(POSTFACH), 1)
    anhang = None
    for part in (POSTFACH[0]["message"].walk() if POSTFACH else []):
        if part.get_content_disposition() == "attachment":
            anhang = part.get_payload(decode=True)
    p.pruefe("Versand: Anhang ist die festgeschriebene Fassung", hashlib.sha256(anhang).hexdigest() if anhang else None, fassung[0] if fassung else None)
    p.pruefe("Versand: Umschlag An + CC", POSTFACH[0]["rcpts"] if POSTFACH else None, ["petra@klicktest.example", "chef@klicktest.example"])
    p.pruefe("Versand: Betreff", POSTFACH[0]["message"]["Subject"] if POSTFACH else None, "Vertrag zu Auftrag " + (await tab.js(f"fetch('/api/orders/{petra}').then(r=>r.json()).then(o=>o.order_number)") or ""))
    await tab.warten("document.querySelectorAll('#contractDispatchHistory .dh-row').length===1")
    p.pruefe("Versand: Verlauf zeigt den Versand", await tab.js("document.querySelector('#contractDispatchHistory .dh-row .dh-pill').textContent"), "Gesendet")
    p.pruefe("Versand: Verlauf nennt die Fassung", "· Fassung 1" in (await tab.js("document.querySelector('#contractDispatchHistory .dh-row').textContent") or ""), True)

    # --- Neue Fassung --------------------------------------------------------------------------------
    await tab.js("document.querySelector('button[onclick^=\"startNewContractVersion\"]').click()")
    await tab.warten("document.getElementById('cSpecialTerms')!==null")
    p.pruefe("Neue Fassung: wieder Entwurf", "Entwurf für Fassung 2" in (await tab.js(KARTE) or ""), True)
    p.pruefe("Neue Fassung: Fassung 1 bleibt sichtbar", "zuletzt festgeschrieben" in (await tab.js(KARTE) or ""), True)
    p.pruefe("Neue Fassung: Fallfeld aus Fassung 1", await tab.js("document.getElementById('cPaymentPlan').value"), "30 % bei Auftrag, Rest nach Abnahme")
    await tab.js("document.getElementById('cSpecialTerms').value='Gerüst stellt der Kunde';saveContract()")
    await tab.warten(f"{STATUS}==='Vertragsentwurf gespeichert.'")
    await tab.warten("document.querySelector('input[name=contractAttachment]')!==null")
    await tab.js("document.querySelector('input[name=contractAttachment][value=aktuell]').click();document.getElementById('contractFreezeBtn').click()")
    await tab.warten(f"{STATUS}==='Fassung 2 festgeschrieben.'", timeout=30)
    p.pruefe("Neue Fassung: Fassung 2 gültig, Fassung 1 abgelöst",
             await tab.js(f"{api}.then(c=>c.versions.map(v=>v.version_no+':'+v.current).join())"), "2:true,1:false")
    p.pruefe("Neue Fassung: 'abgelöst am' sichtbar", "abgelöst am" in (await tab.js(KARTE) or ""), True)
    p.pruefe("Petra: JS-Fehler", tab.fehler, [])
    await tab.js("document.getElementById('contractCard').scrollIntoView()")
    await tab.bild("petra_fassung2_hell")
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/orders/{petra}?dunkel=1", "document.querySelector('#contractBody .contract-ro')!==null")
    p.pruefe("Dunkel: Theme gesetzt", await tab.js("document.documentElement.getAttribute('data-theme')"), "dark")
    await tab.js("document.getElementById('contractCard').scrollIntoView()")
    await tab.bild("petra_fassung2_dunkel")
    await tab.js("localStorage.setItem('erp_theme','light')")

    # --- Sven: versendet und unverändert -> ohne Rückfrage --------------------------------------------
    await tab.oeffnen(f"/orders/{seed['sven']}", "document.querySelector('#contractAttachment .notice')!==null")
    p.pruefe("Sven: Anlage ohne Rückfrage", "entspricht dem heutigen Stand" in (await tab.js(KARTE) or ""), True)
    p.pruefe("Sven: keine Auswahl", await tab.js("document.querySelectorAll('input[name=contractAttachment]').length"), 0)
    await tab.js("document.getElementById('contractFreezeBtn').click()")
    await tab.warten(f"{STATUS}==='Fassung 1 festgeschrieben.'", timeout=30)
    p.pruefe("Sven: festgeschrieben mit versendeter Fassung", "versendeten Fassung" in (await tab.js(KARTE) or ""), True)
    p.pruefe("Sven: JS-Fehler", tab.fehler, [])

    # --- Carla: nach dem Versand geändert -> zwei Möglichkeiten ---------------------------------------
    await tab.oeffnen(f"/orders/{seed['carla']}", "document.querySelector('input[name=contractAttachment]')!==null")
    p.pruefe("Carla: Grund 'weicht ab'", "weicht von der" in (await tab.js(KARTE) or ""), True)
    p.pruefe("Carla: zwei Möglichkeiten, keine vorgewählt",
             await tab.js("[...document.querySelectorAll('input[name=contractAttachment]')].map(i=>i.value+':'+i.checked).join()"),
             "versendet:false,aktuell:false")
    await tab.js("document.getElementById('contractCard').scrollIntoView()")
    await tab.bild("carla_auswahl")
    await tab.js("document.querySelector('input[name=contractAttachment][value=versendet]').click();document.getElementById('contractFreezeBtn').click()")
    await tab.warten(f"{STATUS}==='Fassung 1 festgeschrieben.'", timeout=30)
    p.pruefe("Carla: versendete Fassung angehängt",
             await tab.js(f"fetch('/api/orders/{seed['carla']}/contract').then(r=>r.json()).then(d=>d.contract.versions[0].attachment_kind)"), "versendet")
    p.pruefe("Carla: JS-Fehler", tab.fehler, [])

    # --- Versandprotokoll, Einstellungen, 412 px -----------------------------------------------------
    await tab.oeffnen("/versandprotokoll?typ=vertrag", "!!document.querySelector('#rows tr td') && !document.querySelector('#rows td.empty')")
    p.pruefe("Protokoll: Vertrag verlinkt auf den Auftrag",
             await tab.js("document.querySelector('#rows a.link').getAttribute('href')"), f"/orders/{petra}")
    p.pruefe("Protokoll: Art 'Vertrag' im Filter", await tab.js("[...document.querySelectorAll('#filterType option')].some(o=>o.value==='vertrag')"), True)
    await tab.oeffnen("/settings#email-templates", "document.querySelector('#emailTemplateType option[value=contract]')!==null")
    await tab.js("document.getElementById('emailTemplateType').value='contract';loadEmailTemplate()")
    await tab.warten("document.getElementById('emailTemplatePlaceholderHint').textContent.includes('{fassung}')")
    p.pruefe("Einstellungen: Vorlage 'Vertrag' mit Platzhaltern", "{vertragsgrundlage}" in (await tab.js("document.getElementById('emailTemplatePlaceholderHint').textContent") or ""), True)
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/orders/{petra}?schmal=1", "document.querySelector('#contractBody .contract-ro')!==null")
    p.pruefe("412 px: Vertragskarte ohne seitliches Scrollen",
             await tab.js("(()=>{const c=document.getElementById('contractCard');return c.scrollWidth<=c.clientWidth})()"), True)
    await tab.js("document.getElementById('contractCard').scrollIntoView()")
    await tab.bild("petra_412")
    await tab.fenster(1400, 1000)
    p.pruefe("Büro: JS-Fehler", tab.fehler, [])

    # --- Monteur ---------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["max"])
    await tab.oeffnen("/mobil", "document.readyState==='complete'")
    p.pruefe("Monteur: Vertrag per API gesperrt",
             await tab.js(f"Promise.all([fetch('/api/orders/{petra}/contract'),fetch('/api/orders/{petra}/contract/attachment-options'),"
                          f"fetch('/api/orders/{petra}/contract/freeze',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}})]).then(r=>r.map(x=>x.status).join())"),
             "403,403,403")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
