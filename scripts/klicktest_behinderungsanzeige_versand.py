"""Klicktest: Behinderungsanzeige als Brief und Versand (1.8.40, Stufe 2b, Runde 2b-3 Teil 2, Punkte 1–3).

Die Instanz entsteht per create_all() ohne Alembic -- die Startvorlage kommt deshalb im Befüllen über die
Funktion der Migration d6ac03a06d6f, veröffentlicht wie vom Büro. Die Meldung (mit Foto) hat die Monteurin
schon unterschrieben, den Abschnitt Anzeige hat das Büro ausgefüllt, aber noch nicht unterschrieben.
Auftrag mit VOB/B; Vorbehalt für die Behinderungsanzeige bei VOB/B mit Text, aber ungeprüft. Beteiligte:
Architekt ("Kopie bei Anzeigen", empfangsbevollmächtigt, Vollmacht hinterlegt), Hausverwaltung ("Kopie bei
Anzeigen", ohne E-Mail).

    Büro (1400 px, hell)      Karte "Anzeige an den Auftraggeber": Behinderungsanzeige wartet auf die
                              Unterschrift Büro; nach der Unterschrift bereit, deutliche Warnung "Ohne
                              Vorbehalt", An fest der Auftraggeber, CC vorbelegt, Hinweise (ohne E-Mail,
                              Vollmacht); Vorschau als PDF.
    Admin                     Einstellungen → Vorbehalte in Anzeigen: vier Bausteine, VOB/B prüfen.
    Büro                      Warnung weg; Versand an einen SMTP-Empfänger im Skript: Umschlag An + CC,
                              Anhang = abgelegter Brief (SHA-256), Text mit Vorbehalt, "Kopie an:", Anrede;
                              Karte "versendet", Versandverlauf mit festgehaltener Vollmacht; Aufgabe
                              "Behinderungsanzeige versenden" erledigt; Versandprotokoll mit Link und Vollmacht.
    Büro dunkel, 412 px       Karte lesbar, kein waagrechter Scrollbalken.
    Monteurin (412 px)        keine Karte, API 403; Wegfall ausfüllen und unterschreiben.
    Büro                      Anzeige der Wiederaufnahme: "Brief erstellen (für Post oder Fax)", Zustellung
                              per Einschreiben nachtragen.

`confirm()` wird automatisch bestätigt und mitgeschrieben. Feste Uhr 10:00 (cdp_klicktest.py).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_behinderungsanzeige_versand.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID
beenden): siehe scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import hashlib
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_behinderungsanzeige import _eingeben, _feld_ids, _migration  # noqa: E402
from klicktest_checkliste_unterschrift import CONFIRM, _unterschreiben  # noqa: E402
from klicktest_versandprotokoll import POSTFACH, _smtp_starten  # noqa: E402

B = "behinderungsanzeige."
AG = "ag@klicktest.example"
ARCH = "arch@klicktest.example"


def _bild(farbe, groesse=(800, 600), fmt="JPEG") -> bytes:
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", groesse, farbe).save(buf, format=fmt)
    return buf.getvalue()


def befuellen(db, k):
    from decimal import Decimal

    from sqlalchemy import select

    from app.checklist_templates import publish_draft
    from app.checklists import add_attachment, create_checklist, save_answer
    from app.email_sending import update_smtp_settings
    from app.models import (
        AppUser, ChecklistTemplate, Contact, Customer, Employee, Order, Project, Property, WorkPreparationEmployee,
    )
    from app.notice_reservations import update_reservation
    from app.project_participants import add_participant, store_power_of_attorney
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.settings import load_general_settings
    from app.work_preparation import ensure_preparation

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        smtp_port = s.getsockname()[1]
    update_smtp_settings(db, host="127.0.0.1", port=smtp_port, username="buero", encryption="none",
                         sender_email="buero@klicktest.example", sender_name="Klicktest GmbH", password="pw")
    load_general_settings(db).company_name = "Klicktest Dach GmbH"
    # Bis 1.8.41 standen hier labor_rate_settings und die Gemeinkosten-Einstellung vorab (sonst alert() auf der
    # Einstellungsseite, 1.8.40 Nebenbefund 4) -- seit 1.8.42 legt der Start der Instanz sie an.
    ma = {key: Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group="gewerblich", active=True,
                        hourly_wage=Decimal("22.00"))
          for key, nr, vor, nach in (("mia", "E-1", "Mia", "Monteurin"), ("olga", "E-2", "Olga", "Office"))}
    db.add_all(ma.values()); db.flush()
    benutzer = {
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=ma["mia"].id, password_hash=k.passwort()),
        "buero": AppUser(username="olga", display_name="Olga Office", role="buero_auftrag", employee_id=ma["olga"].id, password_hash=k.passwort()),
        "admin": AppUser(username="ada", display_name="Ada Admin", role="admin", password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Herr Max Muster", salutation="Herr", first_name="Max", last_name="Muster", email=AG,
                     street="Kundenweg 3", postal_code="50667", city="Köln", is_consumer=False)
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Nord", street="Weg 1", postal_code="12345", city="Stadt")
    db.add(objekt); db.flush()
    projekt = Project(project_number="P-KT-1", name="Dach Nord", customer_id=kunde.id, property_id=objekt.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-KT-1", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-1",
                    title="Dach Nord", customer_name="Herr Max Muster", property_name="Halle Nord",
                    property_address="Weg 1\n12345 Stadt", caseworker_employee_id=ma["olga"].id, contract_basis="vob_b")
    db.add(auftrag); db.commit()
    prep = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=ma["mia"].id)); db.commit()

    architekt = Contact(kind="firma", company_name="Architekturbüro Plan", email=ARCH)
    verwaltung = Contact(kind="firma", company_name="Hausverwaltung Ohne Mail")
    db.add_all([architekt, verwaltung]); db.flush()
    teilnehmer = add_participant(db, projekt, architekt, role="architekt_planer", copy_on_notices=True,
                                 authorized_recipient=True)
    add_participant(db, projekt, verwaltung, role="hausverwaltung", copy_on_notices=True)
    vollmacht = _bild((255, 255, 255), (60, 60), "PDF")
    store_power_of_attorney(db, teilnehmer, filename="vollmacht.pdf", data=vollmacht, user_name="Olga Office")
    update_reservation(db, "behinderungsanzeige", "vob_b", reservation_text="Wir behalten uns Ansprüche nach § 6 VOB/B vor.",
                       reviewed_on=None, reviewed_by=None)

    neu = _migration("behinderungsanzeige_startvorlage")
    neu.insert_obstruction_template(db.connection())
    db.commit()
    tid = db.scalar(select(ChecklistTemplate.id).where(ChecklistTemplate.label == "Behinderungsanzeige"))
    publish_draft(db, tid)
    c = create_checklist(db, template_id=tid, context_type="auftrag", order_id=auftrag.id,
                         created_by_employee_id=ma["mia"].id, created_by_user_id=benutzer["mia"].id)
    f = {x["field_key"]: x["id"] for x in c["fields"]}
    for key, value in ((B + "bekannt_seit", "2026-10-02T07:45"), (B + "beschreibung", "Gerüst an der Nordseite fehlt.")):
        save_answer(db, c["id"], f[key], value, recorded_by_employee_id=ma["mia"].id)
    add_attachment(db, c["id"], f[B + "fotos"], _bild((180, 40, 40)), created_by_employee_id=ma["mia"].id)
    add_attachment(db, c["id"], f[B + "unterschrift_meldung"], _bild((10, 10, 10), (300, 80), "PNG"),
                   signer_name="Mia Monteurin", created_by_employee_id=ma["mia"].id)
    for key, value in ((B + "ursache", "zugang_geruest"), (B + "ursache_beschreibung", "Gerüstbauer nicht erschienen."),
                       (B + "betroffene_leistungen", "Dachdeckung Nordseite."), (B + "beginn", "2026-10-02"),
                       (B + "dauer", "etwa eine Woche")):
        save_answer(db, c["id"], f[key], value, recorded_by_employee_id=ma["olga"].id)
    return {"smtp_port": smtp_port, "checklist": c["id"], "fields": f, "vollmacht_sha": hashlib.sha256(vollmacht).hexdigest(),
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


async def pruefen(tab, seed, p):
    server = _smtp_starten(seed["smtp_port"])
    try:
        await _pruefen(tab, seed, p)
    finally:
        server.shutdown()


def _sha_js(url: str) -> str:
    return (f"(async()=>{{const r=await fetch('{url}');const h=await crypto.subtle.digest('SHA-256',await r.arrayBuffer());"
            "return [r.status,r.headers.get('content-type'),[...new Uint8Array(h)].map(b=>b.toString(16).padStart(2,'0')).join('')]})()")


def _pdf_text(data: bytes) -> str:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(data)
    try:
        return "\n".join(doc[i].get_textpage().get_text_bounded() for i in range(len(doc)))
    finally:
        doc.close()


KARTE = "document.getElementById('noticeCard')"
BEH = "document.getElementById('notice-behinderungsanzeige')"
WIE = "document.getElementById('notice-wiederaufnahme')"


async def _pruefen(tab, seed, p):
    import asyncio

    cid, f = seed["checklist"], seed["fields"]
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    # Ein alert() hält den headless Chrome an; so landet er als Fehler in tab.fehler.
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")

    # --- Büro: Karte wartet, Unterschrift Büro, danach bereit mit Warnung ---------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    bereit = f"{BEH} && {WIE}"
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    p.pruefe("Büro: Hellmodus", await tab.js("document.documentElement.dataset.theme"), "light")
    p.pruefe("Vor der Unterschrift Büro: Behinderungsanzeige wartet", await tab.js(
        f"[{BEH}.querySelector('.badge').textContent,{BEH}.textContent.includes('„Unterschrift Büro“'),!document.getElementById('notice-behinderungsanzeige-send')]"),
        ["wartet", True, True])
    p.pruefe("Vor dem Wegfall: Wiederaufnahme wartet", await tab.js(f"{WIE}.querySelector('.badge').textContent"), "wartet")
    await _unterschreiben(tab, f[B + "unterschrift_buero"], "Olga Office")
    await tab.warten(f"{BEH} && {BEH}.querySelector('.badge').textContent==='bereit'")
    p.pruefe("Nach der Unterschrift: bereit", await tab.js(f"{BEH}.querySelector('.badge').textContent"), "bereit")
    p.pruefe("Deutliche Warnung ohne geprüften Vorbehalt", await tab.js(
        f"(()=>{{const w={BEH}.querySelector('[data-reservation-warning]');return !!w&&w.textContent.includes('VOB/B')&&w.textContent.includes('unverzüglich')}})()"), True)
    p.pruefe("An fest: der Auftraggeber, kein Eingabefeld", await tab.js(
        f"[{BEH}.querySelector('[data-notice-to]').textContent,{BEH}.querySelectorAll('[data-notice-to] input').length]"),
        [f"Herr Max Muster <{AG}>fest", 0])
    p.pruefe("CC vorbelegt mit 'Kopie bei Anzeigen'", await tab.js(
        "document.getElementById('notice-behinderungsanzeige-cc').value"), ARCH)
    hinweise = await tab.js(f"{BEH}.querySelector('.notice-info').textContent")
    p.pruefe("Hinweise: ohne E-Mail und Vollmacht", ["Hausverwaltung Ohne Mail" in hinweise,
                                                     "Vollmacht wird beim Versand" in hinweise], [True, True])
    vorschau = await tab.js(_sha_js(f"/api/checklists/{cid}/notice-letters/behinderungsanzeige/preview"))
    p.pruefe("Vorschau als PDF", vorschau[:2], [200, "application/pdf"])
    await tab.js(f"{BEH}.scrollIntoView({{block:'start'}})")
    await asyncio.sleep(0.2)
    await tab.bild("1_buero_bereit_warnung")
    p.pruefe("Büro: keine JS-Fehler (Karte)", tab.fehler, [])

    # --- Admin: Vorbehalt prüfen -------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["admin"])
    zeile = "document.querySelector('[data-reservation=\"behinderungsanzeige/vob_b\"]')"
    await tab.oeffnen("/settings#notice-reservations", zeile)
    await tab.js("showSettingsSection('notice-reservations')")
    p.pruefe("Einstellungen: vier Bausteine", await tab.js(
        "[...document.querySelectorAll('[data-reservation]')].map(e=>e.dataset.reservation)"),
        ["behinderungsanzeige/vob_b", "behinderungsanzeige/bgb", "wiederaufnahme/vob_b", "wiederaufnahme/bgb"])
    p.pruefe("Einstellungen: VOB/B noch ungeprüft", await tab.js(f"{zeile}.textContent.includes('Nicht geprüft')"), True)
    await tab.js(f"(()=>{{const r={zeile};r.querySelector('.nrReviewedOn').value=new Date().toISOString().slice(0,10);"
                 "r.querySelector('.nrReviewedBy').value='RA Beispiel'})()")
    await tab.js("saveNoticeReservation('behinderungsanzeige/vob_b')")
    await tab.warten(f"{zeile}.textContent.includes('Rechtlich geprüft')")
    p.pruefe("Einstellungen: geprüft gespeichert", await tab.js(f"{zeile}.textContent.includes('Rechtlich geprüft – wird im Brief gedruckt')"), True)
    await tab.bild("2_admin_vorbehalt")
    p.pruefe("Admin: keine JS-Fehler", tab.fehler, [])

    # --- Büro: senden -------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.oeffnen(f"/checklisten/{cid}", f"document.getElementById('notice-behinderungsanzeige-send')")
    p.pruefe("Warnung nach der Prüfung weg", await tab.js(f"!{BEH}.querySelector('[data-reservation-warning]')"), True)
    await tab.js("document.getElementById('notice-behinderungsanzeige-cc').value+=', ag@klicktest.example';"
                 "noticeCc['behinderungsanzeige']=document.getElementById('notice-behinderungsanzeige-cc').value")
    await tab.js("document.getElementById('notice-behinderungsanzeige-send').click()")
    await tab.warten(f"{BEH} && {BEH}.querySelector('.badge').textContent==='versendet' && document.querySelector('#notice-behinderungsanzeige-history .dh-row')")
    p.pruefe("Versand: eine Mail", len(POSTFACH), 1)
    p.pruefe("Versand: Umschlag An = Auftraggeber, CC entdoppelt", POSTFACH[0]["rcpts"] if POSTFACH else None, [AG, ARCH])
    anhang = None
    for part in (POSTFACH[0]["message"].walk() if POSTFACH else []):
        if part.get_content_disposition() == "attachment":
            anhang = part.get_payload(decode=True)
    brief = await tab.js(f"fetch('/api/checklists/{cid}/notice-letters').then(r=>r.json()).then(s=>s.kinds[0].letters[0])")
    p.pruefe("Anhang = abgelegter Brief (SHA-256)", hashlib.sha256(anhang or b"").hexdigest(), brief["sent_document"]["sha256"])
    abgelegt = await tab.js(_sha_js(f"/api/sent-documents/{brief['sent_document']['id']}/file"))
    p.pruefe("Ablage liefert dieselben Bytes", abgelegt[2], brief["sent_document"]["sha256"])
    text_ = _pdf_text(anhang) if anhang else ""
    p.pruefe("Brief: Anrede, Betreff, Vorbehalt, Kopie an, Anlage", [
        "Sehr geehrter Herr Muster," in text_, "Bauvorhaben: Halle Nord, Weg 1, 12345 Stadt · Auftrag AUF-KT-1" in text_,
        "Wir behalten uns Ansprüche nach § 6 VOB/B vor." in text_,
        "Architekturbüro Plan (Architekt/Planer); Hausverwaltung Ohne Mail (Hausverwaltung)" in text_,
        "1 Foto (verkleinert)" in text_, "Klicktest Dach GmbH" in text_], [True] * 6)
    p.pruefe("Knopf heißt nach dem Versand 'erneut senden'", await tab.js(
        "document.getElementById('notice-behinderungsanzeige-send').textContent"), "Behinderungsanzeige erneut senden")
    p.pruefe("Karte: Brief mit Fassung und PDF-Link", await tab.js(
        f"[{BEH}.querySelector('[data-notice-letter]').textContent.includes('(Fassung 1)'),"
        f"!!{BEH}.querySelector('[data-notice-letter] a[href^=\"/api/sent-documents/\"]')]"), [True, True])
    verlauf = await tab.js("document.querySelector('#notice-behinderungsanzeige-history .dh-row').textContent")
    p.pruefe("Versandverlauf: Vollmacht festgehalten", ["Empfangsbevollmächtigt: Architekturbüro Plan" in verlauf,
                                                        "Vollmacht festgehalten" in verlauf, "Fassung 1" in verlauf], [True, True, True])
    vollmacht = await tab.js(
        f"fetch('/api/email-dispatches?document_type=behinderungsanzeige&document_id={cid}').then(r=>r.json()).then(d=>d.items[0].authorizations[0].sent_document.sha256)")
    p.pruefe("Vollmacht in der Ablage = hinterlegte Vollmacht", vollmacht, seed["vollmacht_sha"])
    aufgabe = await tab.js("fetch('/api/tasks?include_archived=true').then(r=>r.json()).then(l=>l.filter(t=>t.title==='Behinderungsanzeige versenden').map(t=>[t.status,t.status_is_done]))")
    p.pruefe("Aufgabe 'Behinderungsanzeige versenden' erledigt", aufgabe, [["erledigt", True]])
    await tab.js(f"{BEH}.scrollIntoView({{block:'start'}})")
    await asyncio.sleep(0.2)
    await tab.bild("3_buero_versendet")
    p.pruefe("Büro: keine JS-Fehler (Versand)", tab.fehler, [])

    await tab.oeffnen(f"/versandprotokoll?typ=behinderungsanzeige&id={cid}", "!!document.querySelector('#rows tr td') && !document.querySelector('#rows td.empty')")
    p.pruefe("Versandprotokoll: Link auf die Checkliste und Vollmacht", await tab.js(
        f"[!!document.querySelector('#rows a[href=\"/checklisten/{cid}\"]'), document.querySelector('#rows').textContent.includes('Vollmacht Architekturbüro Plan')]"),
        [True, True])
    p.pruefe("Versandprotokoll: Art im Filter", await tab.js(
        "[...document.getElementById('filterType').options].map(o=>o.value).filter(v=>['behinderungsanzeige','wiederaufnahme'].includes(v))"),
        ["behinderungsanzeige", "wiederaufnahme"])
    await tab.bild("4_versandprotokoll")

    # --- Büro dunkel, schmal ------------------------------------------------------------------------
    await tab.fenster(412, 900, mobil=True)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/checklisten/{cid}", f"{BEH} && {BEH}.querySelector('.badge')")
    p.pruefe("Dunkel: aktiv", await tab.js("document.documentElement.dataset.theme"), "dark")
    p.pruefe("412 px: kein waagrechter Scrollbalken", await tab.js("document.documentElement.scrollWidth<=window.innerWidth"), True)
    farben = await tab.js(f"(()=>{{const s=getComputedStyle({BEH}.querySelector('[data-notice-to]'));return [s.color,s.backgroundColor]}})()")
    p.pruefe("Dunkel: Feld 'An' lesbar (Text und Fläche verschieden)", farben[0] != farben[1], True)
    p.pruefe("Dunkel: Links in Akzentfarbe, nicht Browser-Blau/-Lila", await tab.js(
        f"(()=>{{const a=getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();"
        f"const l=[{BEH}.querySelector('[data-notice-letter] a'),document.querySelector('#notice-behinderungsanzeige-history .dh-muted a')];"
        "const c=document.createElement('span');c.style.color=a;document.body.appendChild(c);const soll=getComputedStyle(c).color;c.remove();"
        "return l.map(x=>!!x&&getComputedStyle(x).color===soll)})()"), [True, True])
    await tab.js(f"{BEH}.scrollIntoView({{block:'start'}})")
    await asyncio.sleep(0.2)
    await tab.bild("5_buero_dunkel_412")
    await tab.js("localStorage.setItem('erp_theme','light')")

    # --- Monteurin: keine Karte, API 403, Wegfall unterschreiben -------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.oeffnen(f"/checklisten/{cid}", "document.querySelector('#clMain .q')")
    p.pruefe("Monteurin: keine Karte", await tab.js(f"!{KARTE}"), True)
    p.pruefe("Monteurin: API 403", await tab.js(
        f"Promise.all([fetch('/api/checklists/{cid}/notice-letters'),fetch('/api/checklists/{cid}/notice-letters/behinderungsanzeige/preview'),"
        f"fetch('/api/checklists/{cid}/notice-letters/behinderungsanzeige/send-email',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{dispatch_key:'monteur-versuch-1'}})}})]).then(l=>l.map(r=>r.status))"),
        [403, 403, 403])
    await _eingeben(tab, f[B + "beendet_am"], "2026-10-06", "change")
    await _eingeben(tab, f[B + "wieder_aufgenommen_am"], "2026-10-07", "change")
    await _unterschreiben(tab, f[B + "unterschrift_wegfall"], "Mia Monteurin")
    await tab.warten(f"document.querySelector('#q_{f[B + 'unterschrift_wegfall']} .sig')")
    p.pruefe("Monteurin: keine JS-Fehler", tab.fehler, [])

    # --- Büro: Wiederaufnahme als Brief erstellen, Einschreiben nachtragen ----------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/checklisten/{cid}", f"{WIE} && {WIE}.querySelector('.badge').textContent==='bereit'")
    p.pruefe("Wiederaufnahme bereit, Warnung (kein Vorbehalt dafür)", await tab.js(
        f"[{WIE}.querySelector('.badge').textContent, !!{WIE}.querySelector('[data-reservation-warning]')]"), ["bereit", True])
    await tab.js(f"[...{WIE}.querySelectorAll('button')].find(b=>b.textContent.startsWith('Brief erstellen')).click()")
    await tab.warten(f"{WIE} && {WIE}.querySelector('[data-notice-letter]')")
    p.pruefe("Wiederaufnahme: Brief erstellt (Fassung 1)", await tab.js(
        f"{WIE}.querySelector('[data-notice-letter]').textContent.includes('(Fassung 1)')"), True)
    await tab.js("toggleManualDelivery('notice-wiederaufnahme-history')")
    await tab.js("document.getElementById('notice-wiederaufnahme-history-note').value='Einschreiben RR 123 456 789 DE'")
    await tab.js("document.getElementById('notice-wiederaufnahme-history-save').click()")
    await tab.warten("document.querySelector('#notice-wiederaufnahme-history .dh-row')")
    zeile_ = await tab.js("document.querySelector('#notice-wiederaufnahme-history .dh-row').textContent")
    p.pruefe("Wiederaufnahme: Einschreiben nachgetragen", ["Zugestellt am" in zeile_, "Einschreiben" in zeile_], [True, True])
    p.pruefe("Wiederaufnahme: Zustellung mit dem erstellten Brief", await tab.js(
        f"Promise.all([fetch('/api/checklists/{cid}/notice-letters').then(r=>r.json()),fetch('/api/email-dispatches?document_type=wiederaufnahme&document_id={cid}').then(r=>r.json())])"
        ".then(([s,d])=>s.kinds[1].letters[0].sent_document.id===d.items[0].sent_document.id)"), True)
    await tab.js(f"{WIE}.scrollIntoView({{block:'start'}})")
    await asyncio.sleep(0.2)
    await tab.bild("6_buero_wiederaufnahme")
    p.pruefe("Büro: keine JS-Fehler (Wiederaufnahme)", tab.fehler, [])
    p.pruefe("Rückfragen bestätigt (Unterschrift, Brief erstellen)", await tab.js("window.__confirms.length>=1"), True)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Behinderungsanzeige als Brief und Versand (1.8.40)", uhr="10:00"))
