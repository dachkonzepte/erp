"""Klicktest: Bedenkenanzeige als Brief und Versand (1.8.44, Stufe 2b, Runde 2b-4 Teil 2).

Die Instanz entsteht per create_all() ohne Alembic -- die Startvorlage kommt über die Funktion der Migration
0816ece7159b. Meldung (Monteurin) und Anzeige (Büro) sind im Befüllen unterschrieben. Der Kunde laut Auftrag
(Schnappschuss "Alte Hausverwaltung GmbH") weicht vom Kunden des Projekts ab.

    Büro (1400 px, dunkel)    Karte "Anzeige an den Auftraggeber" mit nur dem Brief "Bedenkenanzeige", Zeitstrahl,
                              Warnung ohne Vorbehalt, Warnung "Abweichender Kunde" mit Bestätigung; Senden ohne
                              Bestätigung abgewiesen (keine Mail); mit Bestätigung an einen SMTP-Empfänger im
                              Skript: An = Auftraggeber, Anhang = abgelegter Brief (SHA-256), Brieftext;
                              Stand "versendet"; Aufgabe "versenden" erledigt, "Antwort des Auftraggebers prüfen"
                              fällig am "Entscheidung erbeten bis"; Versandprotokoll mit Filter "Bedenkenanzeige".
    Büro (412 px, hell)       Karte ohne waagrechten Scrollbalken.
    Monteurin                 Brief-Endpunkte 403.

`confirm()` wird auf jeder Seite automatisch bestätigt und mitgeschrieben. Feste Uhr 10:00 (cdp_klicktest.py).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_bedenkenanzeige_versand.py [--app-port N]
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
from klicktest_behinderungsanzeige import _migration  # noqa: E402
from klicktest_checkliste_unterschrift import CONFIRM  # noqa: E402
from klicktest_versandprotokoll import POSTFACH, _smtp_starten  # noqa: E402

K = "bedenkenanzeige."
AG = "bauherrin@klicktest.example"


def _bild(farbe, groesse=(400, 300), fmt="JPEG") -> bytes:
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
    from app.models import AppUser, ChecklistTemplate, Customer, Employee, Order, Project, Property, WorkPreparationEmployee
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.settings import load_general_settings
    from app.work_preparation import ensure_preparation

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        smtp_port = s.getsockname()[1]
    update_smtp_settings(db, host="127.0.0.1", port=smtp_port, username="buero", encryption="none",
                         sender_email="buero@klicktest.example", sender_name="Klicktest GmbH", password="pw")
    load_general_settings(db).company_name = "Klicktest Dach GmbH"
    ma = {key: Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group="gewerblich", active=True,
                        hourly_wage=Decimal("22.00"))
          for key, nr, vor, nach in (("mia", "E-1", "Mia", "Monteurin"), ("olga", "E-2", "Olga", "Office"))}
    db.add_all(ma.values()); db.flush()
    benutzer = {
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=ma["mia"].id, password_hash=k.passwort()),
        "buero": AppUser(username="olga", display_name="Olga Office", role="buero_auftrag", employee_id=ma["olga"].id, password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Frau Erika Bauherrin", salutation="Frau", first_name="Erika", last_name="Bauherrin", email=AG,
                     street="Bauweg 7", postal_code="50667", city="Köln", is_consumer=False)
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Nord", street="Weg 1", postal_code="12345", city="Stadt")
    db.add(objekt); db.flush()
    projekt = Project(project_number="P-KT-1", name="Dach Nord", customer_id=kunde.id, property_id=objekt.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-KT-1", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-1",
                    title="Dach Nord", customer_name="Alte Hausverwaltung GmbH", property_name="Halle Nord",
                    property_address="Weg 1\n12345 Stadt", caseworker_employee_id=ma["olga"].id, contract_basis="vob_b")
    db.add(auftrag); db.commit()
    prep = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=ma["mia"].id)); db.commit()

    _migration("bedenkenanzeige_startvorlage").insert_concern_template(db.connection())
    db.commit()
    tid = db.scalar(select(ChecklistTemplate.id).where(ChecklistTemplate.label == "Bedenkenanzeige"))
    publish_draft(db, tid)
    c = create_checklist(db, template_id=tid, context_type="auftrag", order_id=auftrag.id,
                         created_by_employee_id=ma["mia"].id, created_by_user_id=benutzer["mia"].id)
    f = {x["field_key"]: x["id"] for x in c["fields"]}
    for key, value in ((K + "bekannt_seit", "2026-10-02T07:45"), (K + "beschreibung", "Gelieferte Dämmplatten sind nass.")):
        save_answer(db, c["id"], f[key], value, recorded_by_employee_id=ma["mia"].id)
    add_attachment(db, c["id"], f[K + "fotos"], _bild((180, 40, 40)), created_by_employee_id=ma["mia"].id)
    add_attachment(db, c["id"], f[K + "unterschrift_meldung"], _bild((10, 10, 10), (300, 80), "PNG"),
                   signer_name="Mia Monteurin", created_by_employee_id=ma["mia"].id)
    for key, value in ((K + "bedenken_gegen", ["stoffe_bauteile"]), (K + "begruendung", "Nasse Dämmung verliert ihre Wirkung."),
                       (K + "moegliche_folgen", "Tauwasser und Schimmel."), (K + "entscheidung_bis", "2026-10-09")):
        save_answer(db, c["id"], f[key], value, recorded_by_employee_id=ma["olga"].id)
    add_attachment(db, c["id"], f[K + "unterschrift_buero"], _bild((10, 10, 10), (300, 80), "PNG"),
                   signer_name="Olga Office", created_by_employee_id=ma["olga"].id)
    return {"smtp_port": smtp_port, "checklist": c["id"], "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


async def pruefen(tab, seed, p):
    server = _smtp_starten(seed["smtp_port"])
    try:
        await _pruefen(tab, seed, p)
    finally:
        server.shutdown()


def _pdf_text(data: bytes) -> str:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(data)
    try:
        return "\n".join(doc[i].get_textpage().get_text_bounded() for i in range(len(doc)))
    finally:
        doc.close()


KARTE = "document.querySelector('#noticeCard #notice-bedenkenanzeige')"


async def _pruefen(tab, seed, p):
    import asyncio

    cid = seed["checklist"]
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/checklisten/{cid}", KARTE)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/checklisten/{cid}", KARTE)
    p.pruefe("Büro: Dunkelmodus", await tab.js("document.documentElement.dataset.theme"), "dark")
    p.pruefe("Karte: nur der Brief 'Bedenkenanzeige', bereit", await tab.js(
        "[[...document.querySelectorAll('#noticeCard .notice-kind')].map(e=>e.dataset.kind),"
        "document.getElementById('notice-bedenkenanzeige').dataset.status]"), [["bedenkenanzeige"], "bereit"])
    p.pruefe("Zeitstrahl: bekannt seit, Meldung, versendet", await tab.js(
        "[...document.querySelectorAll('#noticeTimeline .tl-step')].map(e=>e.dataset.step)"),
        ["bekannt_seit", "meldung", "versendet"])
    p.pruefe("Warnung ohne Vorbehalt", await tab.js("!!document.querySelector('#notice-bedenkenanzeige [data-reservation-warning]')"), True)
    p.pruefe("Warnung 'Abweichender Kunde' mit beiden Kunden und Bestätigung", await tab.js(
        "(()=>{const w=document.querySelector('[data-customer-mismatch]');return [w.textContent.includes('Frau Erika Bauherrin'),"
        "w.textContent.includes('Alte Hausverwaltung GmbH'),!!document.getElementById('noticeConfirmCustomer'),"
        "document.getElementById('noticeConfirmCustomer').checked]})()"), [True, True, True, False])
    farben = await tab.js("(()=>{const s=getComputedStyle(document.querySelector('[data-customer-mismatch]'));return [s.color,s.backgroundColor]})()")
    p.pruefe("Warnung lesbar im Dunkelmodus", farben[0] != farben[1], True)
    await tab.js("document.querySelector('[data-customer-mismatch]').scrollIntoView({block:'center'})")
    await asyncio.sleep(0.2)
    await tab.bild("1_buero_karte_abweichender_kunde_dunkel")

    await tab.js("document.getElementById('notice-bedenkenanzeige-send').click()")
    await tab.warten("document.getElementById('notice-bedenkenanzeige-status').textContent.includes('Abweichung')")
    p.pruefe("Senden ohne Bestätigung abgewiesen, keine Mail", [await tab.js(
        "document.getElementById('notice-bedenkenanzeige-status').textContent"), len(POSTFACH)],
        ["Bitte zuerst oben die Abweichung des Kunden prüfen und bestätigen.", 0])
    await tab.js("const cb=document.getElementById('noticeConfirmCustomer');cb.click()")
    await tab.js("document.getElementById('notice-bedenkenanzeige-send').click()")
    await tab.warten("document.getElementById('notice-bedenkenanzeige')?.dataset.status==='versendet'", timeout=30)
    p.pruefe("Stand 'versendet', Status 'Versendet.'", await tab.js(
        "[document.getElementById('notice-bedenkenanzeige').dataset.status,document.getElementById('notice-bedenkenanzeige-status').textContent]"),
        ["versendet", "Versendet."])
    p.pruefe("Rückfragen (ohne Vorbehalt senden)", await tab.js("window.__confirms.some(t=>t.includes('ohne Vorbehalt'))"), True)
    p.pruefe("Mail: Umschlag nur an den Auftraggeber", POSTFACH[0]["rcpts"] if POSTFACH else None, [AG])
    anhang = next((part.get_payload(decode=True) for part in (POSTFACH[0]["message"].walk() if POSTFACH else [])
                   if part.get_content_type() == "application/pdf"), b"")
    doc = await tab.js(
        f"fetch('/api/email-dispatches?document_type=bedenkenanzeige&document_id={cid}').then(r=>r.json())"
        ".then(d=>d.items.map(x=>[x.status,x.sent_document&&x.sent_document.sha256]))")
    p.pruefe("Anhang = abgelegter Brief (SHA-256)", [hashlib.sha256(anhang).hexdigest()] if anhang else None,
             [d[1] for d in doc] if doc else None)
    text = _pdf_text(anhang) if anhang else ""
    p.pruefe("Brieftext", ["Bedenkenanzeige" in text, "Sehr geehrte Frau Bauherrin," in text,
                           "vom Auftraggeber gelieferte Stoffe oder Bauteile" in text, "09.10.2026" in text,
                           f"Erstellt aus der Bedenkenanzeige Nr. {cid}" in text], [True] * 5)
    aufgaben = await tab.js(
        "fetch('/api/tasks').then(r=>r.json()).then(l=>l.filter(t=>['Bedenkenanzeige versenden','Antwort des Auftraggebers prüfen'].includes(t.title))"
        ".map(t=>[t.title,t.status,t.assigned_employee_name]).sort())")
    p.pruefe("Aufgaben: 'versenden' erledigt, 'Antwort prüfen' offen", aufgaben,
             [["Antwort des Auftraggebers prüfen", "offen", "Olga Office"], ["Bedenkenanzeige versenden", "erledigt", "Olga Office"]])
    p.pruefe("Aufgabe 'Antwort prüfen' fällig am 'Entscheidung erbeten bis'", await tab.js(
        "fetch('/api/tasks').then(r=>r.json()).then(l=>l.filter(t=>t.title==='Antwort des Auftraggebers prüfen').map(t=>t.due_date))"),
        ["2026-10-09"])
    await tab.oeffnen(f"/checklisten/{cid}", "document.getElementById('notice-bedenkenanzeige')?.dataset.status==='versendet'")
    p.pruefe("Zeitstrahl: versendet mit Abstand", await tab.js(
        "(()=>{const s=document.querySelector('#noticeTimeline [data-step=versendet]');return [!s.classList.contains('open'),!!s.querySelector('.tl-gap')]})()"),
        [True, True])
    await tab.bild("2_buero_versendet_dunkel")
    p.pruefe("Büro: keine JS-Fehler (Versand)", tab.fehler, [])

    bereit = "!!document.querySelector('#rows tr td') && !document.querySelector('#rows td.empty')"
    await tab.oeffnen(f"/versandprotokoll?typ=bedenkenanzeige&id={cid}", bereit)
    p.pruefe("Versandprotokoll: Filter 'Bedenkenanzeige' und Eintrag mit Link", await tab.js(
        "[[...document.querySelectorAll('#filterType option')].some(o=>o.value==='bedenkenanzeige'&&o.textContent==='Bedenkenanzeige'),"
        f"!!document.querySelector('#rows a[href=\"/checklisten/{cid}\"]')]"), [True, True])

    await tab.fenster(412, 900, mobil=True)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen(f"/checklisten/{cid}", KARTE)
    await asyncio.sleep(0.3)
    p.pruefe("Büro 412 px hell: kein waagrechter Scrollbalken", await tab.js("document.documentElement.scrollWidth<=window.innerWidth"), True)
    await tab.js("document.getElementById('noticeCard').scrollIntoView()")
    await tab.bild("3_buero_karte_412_hell")
    p.pruefe("Büro: keine JS-Fehler (Ende)", tab.fehler, [])

    await tab.anmelden(seed["cookies"]["mia"])
    p.pruefe("Monteurin: Brief-Endpunkte 403", await tab.js(
        f"Promise.all([fetch('/api/checklists/{cid}/notice-letters').then(r=>r.status),"
        f"fetch('/api/checklists/{cid}/notice-letters/bedenkenanzeige/freeze',{{method:'POST'}}).then(r=>r.status)])"), [403, 403])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Bedenkenanzeige als Brief und Versand (1.8.44)", uhr="10:00"))
