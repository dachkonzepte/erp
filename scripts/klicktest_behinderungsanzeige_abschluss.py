"""Klicktest: Behinderungsanzeige abschließen (1.8.41, Stufe 2b, Runde 2b-3 Teil 3).

Befüllt wie klicktest_behinderungsanzeige_versand.py (Auftrag mit VOB/B, Auftraggeber mit E-Mail, Architekt mit
Vollmacht, Hausverwaltung ohne E-Mail), dazu: die Unterschrift Büro unter der ersten Behinderungsanzeige; ein
Gutachter (empfangsbevollmächtigt, ohne E-Mail, Vollmacht hinterlegt); ein zweiter Kunde, der im Projekt schon
Beteiligter ist; eine zweite Behinderungsanzeige, von der nur die Meldung unterschrieben ist.

    Büro (1400 px, hell)   Zeitstrahl: bekannt seit → Meldung → "noch nicht" (wartet seit …); senden → versendet mit
                           Abstand. Im Versandverlauf "Unzustellbar" (ohne Notiz abgewiesen, mit Notiz gespeichert):
                           Stand "unzustellbar", Warnung, Aufgabe wieder offen. "Zustellung nachtragen" mit
                           Empfängerauswahl (Auftraggeber vorgewählt, Gutachter ohne E-Mail): Vollmacht festgehalten,
                           Aufgabe erledigt. "Empfang bestätigt" mit Beleg (Datei-Upload).
    Versandprotokoll        beide Ergebnisse, Beleg in der Ablage-Spalte.
    Büro dunkel, 412 px     Zeitstrahl untereinander, kein waagrechter Scrollbalken.
    Monteurin (412 px)      Wegfall unterschreiben; beide Anzeigen unter "Offene Checklisten".
    Büro                    Wiederaufnahme: Hinweis "i. A.", Brief erstellen -- im PDF "i. A. Olga Office", nicht die
                           Monteurin. Zweite Anzeige "als gegenstandslos abschließen" (ohne Begründung abgewiesen):
                           Badge, Begründung, PDF, keine Brief-Aktionen, Aufgabe erledigt.
    Monteurin               die gegenstandslose fehlt unter "Offene Checklisten", zeigt Begründung, API 403.
    Büro, Projektmappe      Kundenwechsel auf den beteiligten Kunden: Meldung im Dialog, Kunde unverändert.

`confirm()` wird automatisch bestätigt und mitgeschrieben, `alert()` als Fehler gezählt. Feste Uhr 10:00.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_behinderungsanzeige_abschluss.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID
beenden): siehe scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_behinderungsanzeige import _eingeben  # noqa: E402
from klicktest_behinderungsanzeige_versand import (  # noqa: E402
    _bild, _pdf_text, befuellen as befuellen_versand,
)
from klicktest_checkliste_unterschrift import CONFIRM, _unterschreiben  # noqa: E402
from klicktest_versandprotokoll import POSTFACH, _smtp_starten  # noqa: E402

B = "behinderungsanzeige."


def befuellen(db, k):
    from sqlalchemy import select

    from app.checklists import add_attachment, create_checklist, save_answer
    from app.contacts import linked_contact
    from app.models import AppUser, Contact, Customer, Employee, Order, Project
    from app.project_participants import add_participant, store_power_of_attorney

    seed = befuellen_versand(db, k)
    mia = db.scalar(select(Employee).where(Employee.employee_number == "E-1"))
    olga = db.scalar(select(Employee).where(Employee.employee_number == "E-2"))
    mia_user = db.scalar(select(AppUser).where(AppUser.username == "mia"))
    f = seed["fields"]
    add_attachment(db, seed["checklist"], f[B + "unterschrift_buero"], _bild((10, 10, 10), (300, 80), "PNG"),
                   signer_name="Olga Office", created_by_employee_id=olga.id)
    auftrag = db.scalar(select(Order).where(Order.order_number == "AUF-KT-1"))
    projekt = db.get(Project, auftrag.project_id)
    gutachter = Contact(kind="firma", company_name="Gutachter Prüf")
    db.add(gutachter); db.flush()
    teilnehmer = add_participant(db, projekt, gutachter, role="sachverstaendiger", authorized_recipient=True)
    store_power_of_attorney(db, teilnehmer, filename="vollmacht-gutachter.pdf", data=_bild((255, 255, 255), (50, 50), "PDF"),
                            user_name="Olga Office")
    eigentuemer = Customer(name="Eigentümer Süd GmbH", last_name="Eigentümer Süd GmbH", salutation="Firma",
                           email="sued@klicktest.example")
    db.add(eigentuemer); db.flush()
    add_participant(db, projekt, linked_contact(db, customer=eigentuemer), role="eigentuemer")

    # Zweite Anzeige: nur die Meldung -- wird "gegenstandslos".
    tid = seed_template_id(db)
    c2 = create_checklist(db, template_id=tid, context_type="auftrag", order_id=auftrag.id,
                          created_by_employee_id=mia.id, created_by_user_id=mia_user.id)
    f2 = {x["field_key"]: x["id"] for x in c2["fields"]}
    for key, value in ((B + "bekannt_seit", "2026-10-02T06:30"), (B + "beschreibung", "Starker Regen am Morgen.")):
        save_answer(db, c2["id"], f2[key], value, recorded_by_employee_id=mia.id)
    add_attachment(db, c2["id"], f2[B + "unterschrift_meldung"], _bild((10, 10, 10), (300, 80), "PNG"),
                   signer_name="Mia Monteurin", created_by_employee_id=mia.id)
    belegdatei = Path(tempfile.mkdtemp(prefix="klicktest-rueckschein-")) / "Rueckschein.jpg"
    belegdatei.write_bytes(_bild((240, 240, 200), (400, 300)))
    return {**seed, "checklist2": c2["id"], "fields2": f2, "project": projekt.id, "kunde": projekt.customer_id,
            "eigentuemer": eigentuemer.id, "beleg": str(belegdatei)}


def seed_template_id(db):
    from sqlalchemy import select

    from app.models import ChecklistTemplate

    return db.scalar(select(ChecklistTemplate.id).where(ChecklistTemplate.label == "Behinderungsanzeige"))


async def pruefen(tab, seed, p):
    server = _smtp_starten(seed["smtp_port"])
    try:
        await _pruefen(tab, seed, p)
    finally:
        server.shutdown()


BEH = "document.getElementById('notice-behinderungsanzeige')"
WIE = "document.getElementById('notice-wiederaufnahme')"
H = "notice-behinderungsanzeige-history"


async def _datei_setzen(tab, selector: str, pfad: str) -> None:
    doc = await tab.cmd("DOM.getDocument", depth=1)
    node = await tab.cmd("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
    await tab.cmd("DOM.setFileInputFiles", files=[pfad], nodeId=node["nodeId"])


def _aufgaben_js(cid: int) -> str:
    return (f"fetch('/api/tasks?include_archived=true').then(r=>r.json()).then(l=>l.filter(t=>t.title==='Behinderungsanzeige versenden'"
            f"&&t.source_url==='/checklisten/{cid}').map(t=>t.status))")


def _holen(tab, cookies: dict, pfad: str) -> bytes:
    """Datei direkt über HTTP mit den Anmelde-Cookies holen (für den Text des PDFs)."""
    import urllib.request

    req = urllib.request.Request(tab.base + pfad, headers={"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


async def _pruefen(tab, seed, p):
    import asyncio

    cid, cid2 = seed["checklist"], seed["checklist2"]
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")

    # --- Büro: Zeitstrahl, senden ---------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    bereit = f"{BEH} && document.getElementById('noticeTimeline')"
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    schritte = "[...document.querySelectorAll('#noticeTimeline .tl-step')]"
    p.pruefe("Zeitstrahl: drei Schritte", await tab.js(f"{schritte}.map(s=>s.dataset.step)"), ["bekannt_seit", "meldung", "versendet"])
    p.pruefe("Zeitstrahl: bekannt seit aus der Meldung", await tab.js(f"{schritte}[0].querySelector('.tl-at').textContent"),
             "02.10.2026, 07:45 Uhr")
    p.pruefe("Zeitstrahl: noch nicht versendet, wartet", await tab.js(
        f"(()=>{{const s={schritte}[2];return [s.querySelector('.tl-at').textContent,s.classList.contains('open'),s.querySelector('.tl-gap').textContent.startsWith('wartet seit')]}})()"),
        ["noch nicht", True, True])
    await tab.js("document.getElementById('notice-behinderungsanzeige-send').click()")
    await tab.warten(f"{BEH} && {BEH}.dataset.status==='versendet' && document.querySelector('#{H} .dh-row')")
    p.pruefe("Versand: eine Mail an den Auftraggeber", [len(POSTFACH), POSTFACH[0]["rcpts"][0] if POSTFACH else None],
             [1, "ag@klicktest.example"])
    p.pruefe("Zeitstrahl: versendet mit Uhrzeit und Abstand", await tab.js(
        f"(()=>{{const s={schritte}[2];return [/Uhr/.test(s.querySelector('.tl-at').textContent),s.querySelector('.tl-gap').textContent.startsWith('+ ')]}})()"),
        [True, True])
    p.pruefe("Aufgabe nach dem Versand erledigt", await tab.js(_aufgaben_js(cid)), ["erledigt"])
    await tab.bild("1_buero_zeitstrahl_versendet")

    # --- Unzustellbar ----------------------------------------------------------------------------------
    zeile = f"document.querySelector('#{H} .dh-row')"
    p.pruefe("Versandverlauf: Knöpfe Empfang/Unzustellbar", await tab.js(
        f"[...{zeile}.querySelectorAll('.dh-oc-actions button')].map(b=>b.textContent)"), ["Empfang bestätigt", "Unzustellbar"])
    await tab.js(f"[...{zeile}.querySelectorAll('.dh-oc-actions button')][1].click()")
    form = await tab.js(f"{zeile}.querySelector('.dh-form').id")
    p.pruefe("Unzustellbar: Formular sichtbar, Notiz Pflicht", await tab.js(
        f"[getComputedStyle(document.getElementById('{form}')).display,document.getElementById('{form}-notelabel').textContent]"),
        ["grid", "Notiz (Pflicht)"])
    await tab.js(f"document.getElementById('{form}-save').click()")
    p.pruefe("Unzustellbar ohne Notiz: Meldung, nichts gespeichert", await tab.js(
        f"document.getElementById('{form}-msg').textContent"), "Bitte in der Notiz festhalten, warum unzustellbar.")
    await tab.js(f"document.getElementById('{form}-note').value='Unzustellbar: Postfach voll (Antwort des Mailservers)'")
    await tab.js(f"document.getElementById('{form}-save').click()")
    await tab.warten(f"{BEH} && {BEH}.dataset.status==='unzustellbar' && document.querySelector('#{H} [data-outcome]')")
    p.pruefe("Unzustellbar: in der Zeile vermerkt", await tab.js(
        f"(()=>{{const o=document.querySelector('#{H} [data-outcome]');return [o.dataset.outcome,o.textContent.includes('Postfach voll')]}})()"),
        ["unzustellbar", True])
    p.pruefe("Unzustellbar: Stand und Warnung, Knopf 'erneut senden'", await tab.js(
        f"[{BEH}.querySelector('.badge').textContent,!!{BEH}.querySelector('[data-undeliverable]'),"
        "document.getElementById('notice-behinderungsanzeige-send').textContent]"),
        ["unzustellbar", True, "Behinderungsanzeige erneut senden"])
    p.pruefe("Unzustellbar: Aufgabe wieder offen", await tab.js(_aufgaben_js(cid)), ["offen"])
    p.pruefe("Unzustellbar: Zeitstrahl wartet wieder", await tab.js(f"{schritte}[2].querySelector('.tl-at').textContent"), "noch nicht")
    await tab.js(f"{BEH}.scrollIntoView({{block:'start'}})")
    await asyncio.sleep(0.2)
    await tab.bild("2_buero_unzustellbar")

    # --- Zustellung nachtragen mit Empfängerauswahl -------------------------------------------------
    await tab.js(f"toggleManualDelivery('{H}')")
    await tab.warten(f"document.getElementById('{H}-recipients').dataset.loaded==='1'")
    p.pruefe("Nachtragen: Auftraggeber vorgewählt", await tab.js(
        f"[document.getElementById('{H}-client').checked,document.getElementById('{H}-recipients').textContent.includes('Herr Max Muster')]"),
        [True, True])
    namen = await tab.js(f"[...document.querySelectorAll('.{H}-participant')].map(b=>b.closest('label').textContent)")
    p.pruefe("Nachtragen: Beteiligte auch ohne E-Mail", [any("Gutachter Prüf" in n and "ohne E-Mail" in n and "Vollmacht wird festgehalten" in n
                                                           for n in namen),
                                                       any("Hausverwaltung Ohne Mail" in n for n in namen)], [True, True])
    await tab.js(f"[...document.querySelectorAll('.{H}-participant')].find(b=>b.closest('label').textContent.includes('Gutachter Prüf')).checked=true")
    await tab.js(f"document.getElementById('{H}-note').value='Einschreiben RR 987 654 321 DE an Auftraggeber und Gutachter'")
    await tab.js(f"document.getElementById('{H}-save').click()")
    await tab.warten(f"{BEH} && {BEH}.dataset.status==='versendet' && document.querySelectorAll('#{H} .dh-row').length===2")
    neu = await tab.js(f"document.querySelector('#{H} .dh-row').textContent")
    p.pruefe("Nachtragen: Empfänger und festgehaltene Vollmacht", [
        "Herr Max Muster (Auftraggeber); Gutachter Prüf (Sachverständiger/Gutachter)" in neu,
        "Empfangsbevollmächtigt: Gutachter Prüf (Sachverständiger/Gutachter) – ohne E-Mail – Vollmacht festgehalten" in neu],
        [True, True])
    p.pruefe("Nachtragen: Aufgabe wieder erledigt", await tab.js(_aufgaben_js(cid)), ["erledigt"])

    # --- Empfang bestätigt mit Beleg ---------------------------------------------------------------
    manuell = f"document.querySelector('#{H} .dh-row')"
    await tab.js(f"[...{manuell}.querySelectorAll('.dh-oc-actions button')][0].click()")
    form2 = await tab.js(f"{manuell}.querySelector('.dh-form').id")
    await _datei_setzen(tab, f"#{form2}-file", seed["beleg"])
    await tab.js(f"document.getElementById('{form2}-note').value='Rückschein unterschrieben zurück'")
    await tab.js(f"document.getElementById('{form2}-save').click()")
    await tab.warten(f"document.querySelectorAll('#{H} [data-outcome]').length===2")
    p.pruefe("Empfang bestätigt: vermerkt mit Beleg", await tab.js(
        f"(()=>{{const o=document.querySelector('#{H} .dh-row [data-outcome]');return [o.dataset.outcome,o.textContent.includes('Rückschein'),"
        "!!o.querySelector('a[href^=\"/api/sent-documents/\"]')]})()"), ["empfangen", True, True])
    p.pruefe("Nach dem Vermerk keine Knöpfe mehr in diesen Zeilen", await tab.js(f"document.querySelectorAll('#{H} .dh-oc-actions').length"), 0)
    await tab.js(f"{BEH}.scrollIntoView({{block:'start'}})")
    await asyncio.sleep(0.2)
    await tab.bild("3_buero_nachgetragen_empfang")
    p.pruefe("Büro: keine JS-Fehler (Versandergebnis)", tab.fehler, [])

    await tab.oeffnen(f"/versandprotokoll?typ=behinderungsanzeige&id={cid}", "!!document.querySelector('#rows tr td') && !document.querySelector('#rows td.empty')")
    zeilen = await tab.js("document.getElementById('rows').textContent")
    p.pruefe("Versandprotokoll: beide Ergebnisse und Beleg", ["Unzustellbar am" in zeilen, "Empfang bestätigt am" in zeilen,
                                                             "Beleg (Empfang):" in zeilen], [True, True, True])
    await tab.bild("4_versandprotokoll")
    p.pruefe("Versandprotokoll: keine JS-Fehler", tab.fehler, [])

    # --- Büro dunkel, schmal ---------------------------------------------------------------------
    await tab.fenster(412, 900, mobil=True)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    p.pruefe("Dunkel 412 px: kein waagrechter Scrollbalken", await tab.js("document.documentElement.scrollWidth<=window.innerWidth"), True)
    p.pruefe("412 px: Zeitstrahl untereinander", await tab.js(
        f"(()=>{{const t={schritte}.map(s=>s.getBoundingClientRect().top);return t[0]<t[1]&&t[1]<t[2]}})()"), True)
    await tab.js("document.getElementById('noticeTimeline').scrollIntoView({block:'start'})")
    await asyncio.sleep(0.2)
    await tab.bild("5_buero_dunkel_412")
    await tab.js("localStorage.setItem('erp_theme','light')")

    # --- Monteurin: Wegfall, offene Checklisten --------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    f = seed["fields"]
    await tab.oeffnen(f"/checklisten/{cid}", "document.querySelector('#clMain .q')")
    await _eingeben(tab, f[B + "beendet_am"], "2026-10-06", "change")
    await _eingeben(tab, f[B + "wieder_aufgenommen_am"], "2026-10-07", "change")
    await _unterschreiben(tab, f[B + "unterschrift_wegfall"], "Mia Monteurin")
    await tab.warten(f"document.querySelector('#q_{f[B + 'unterschrift_wegfall']} .sig')")
    await tab.oeffnen("/mobil", "document.getElementById('draftChecklistsList') && !document.getElementById('draftChecklistsList').classList.contains('loading')")
    p.pruefe("Monteurin /mobil: beide Anzeigen offen", await tab.js(
        f"[!!document.querySelector('#draftChecklistsList a[href=\"/checklisten/{cid}\"]'),!!document.querySelector('#draftChecklistsList a[href=\"/checklisten/{cid2}\"]')]"),
        [True, True])
    p.pruefe("Monteurin: keine JS-Fehler", tab.fehler, [])

    # --- Büro: Wiederaufnahme i. A., zweite Anzeige gegenstandslos -------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/checklisten/{cid}", f"{WIE} && {WIE}.dataset.status==='bereit'")
    p.pruefe("Wiederaufnahme: Hinweis 'i. A.'", await tab.js(f"{WIE}.querySelector('[data-signoff]').textContent.includes('„i. A.“')"), True)
    await tab.js(f"[...{WIE}.querySelectorAll('button')].find(b=>b.textContent.startsWith('Brief erstellen')).click()")
    await tab.warten(f"{WIE} && {WIE}.querySelector('[data-notice-letter] a')")
    href = await tab.js(f"{WIE}.querySelector('[data-notice-letter] a').getAttribute('href')")
    p.pruefe("Wiederaufnahme: Brief erstellt, Link aufs PDF", bool(href and href.startswith("/api/sent-documents/")), True)
    pdf = _holen(tab, seed["cookies"]["buero"], href or "/")
    text_ = _pdf_text(pdf)
    p.pruefe("Wiederaufnahme-PDF: i. A. Büro-Konto, nicht die Monteurin", ["i. A. Olga Office" in text_, "Mia Monteurin" in text_,
                                                                          b"/Subtype /Image" in pdf], [True, False, False])

    await tab.oeffnen(f"/checklisten/{cid2}", "document.getElementById('voidCard')")
    await tab.js("document.getElementById('voidBtn').click()")
    p.pruefe("Gegenstandslos ohne Begründung abgewiesen", await tab.js("document.getElementById('voidStatus').textContent"),
             "Bitte begründen, warum die Anzeige gegenstandslos ist.")
    await tab.js("document.getElementById('voidReason').value='Übliche Witterung – nach § 6 Abs. 2 VOB/B keine Behinderung.'")
    await tab.js("document.getElementById('voidBtn').click()")
    await tab.warten("document.getElementById('voidInfo')")
    p.pruefe("Gegenstandslos: Rückfrage vor dem Abschluss", await tab.js(
        "window.__confirms.some(t=>t.includes('als gegenstandslos abschließen?'))"), True)
    p.pruefe("Gegenstandslos: Badge, Begründung, PDF, keine Fußleiste", await tab.js(
        "[document.querySelector('.badge.void')?.textContent,document.getElementById('voidInfo').textContent.includes('Übliche Witterung'),"
        "!!document.getElementById('pdfLink'),!document.getElementById('completeBtn'),!document.getElementById('voidCard')]"),
        ["Gegenstandslos", True, True, True, True])
    await tab.warten(f"{BEH} && {BEH}.dataset.status")
    p.pruefe("Gegenstandslos: Anzeige-Karte ohne Brief-Aktionen", await tab.js(
        "[document.getElementById('noticeCard').textContent.includes('Als gegenstandslos abgeschlossen'),"
        "!document.getElementById('notice-behinderungsanzeige-send'),!document.querySelector('#noticeCard .notice-actions')]"),
        [True, True, True])
    p.pruefe("Gegenstandslos: Aufgabe erledigt", await tab.js(_aufgaben_js(cid2)), ["erledigt"])
    p.pruefe("Gegenstandslos: PDF abrufbar", await tab.js(f"fetch('/api/checklists/{cid2}/pdf').then(r=>[r.status,r.headers.get('content-type')])"),
             [200, "application/pdf"])
    await tab.bild("6_buero_gegenstandslos")
    p.pruefe("Büro: keine JS-Fehler (Wiederaufnahme, gegenstandslos)", tab.fehler, [])

    # --- Monteurin: die gegenstandslose ist nicht mehr offen -------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen("/mobil", "document.getElementById('draftChecklistsList') && !document.getElementById('draftChecklistsList').classList.contains('loading')")
    p.pruefe("Monteurin /mobil: gegenstandslose fehlt, die andere bleibt", await tab.js(
        f"[!!document.querySelector('#draftChecklistsList a[href=\"/checklisten/{cid}\"]'),!!document.querySelector('#draftChecklistsList a[href=\"/checklisten/{cid2}\"]')]"),
        [True, False])
    await tab.oeffnen(f"/checklisten/{cid2}", "document.getElementById('voidInfo')")
    p.pruefe("Monteurin: Begründung sichtbar, keine Abschluss-Karte", await tab.js(
        "[document.getElementById('voidInfo').textContent.includes('Übliche Witterung'),!document.getElementById('voidCard')]"), [True, True])
    p.pruefe("Monteurin: gegenstandslos per API 403", await tab.js(
        f"fetch('/api/checklists/{cid}/void',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{reason:'versucht'}})}}).then(r=>r.status)"),
        403)
    await tab.bild("7_monteurin_gegenstandslos")
    p.pruefe("Monteurin: keine JS-Fehler (gegenstandslos)", tab.fehler, [])

    # --- Büro: Kundenwechsel auf einen Beteiligten -------------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/projects/{seed['project']}", "typeof openProjectEdit==='function' && typeof project!=='undefined' && project && project.id")
    await tab.js("openProjectEdit()")
    await tab.warten(f"[...document.getElementById('editCustomer').options].some(o=>o.value==='{seed['eigentuemer']}')")
    await tab.js(f"document.getElementById('editCustomer').value='{seed['eigentuemer']}'")
    await tab.js("loadEditProperties().then(()=>saveProject())")
    await tab.warten("document.getElementById('projectEditStatus').textContent.startsWith('Fehler')")
    p.pruefe("Kundenwechsel: Meldung im Dialog", await tab.js(
        "(()=>{const t=document.getElementById('projectEditStatus').textContent;return [t.includes('Eigentümer Süd GmbH'),t.includes('schon Beteiligter'),t.includes('„Beteiligte“')]})()"),
        [True, True, True])
    p.pruefe("Kundenwechsel: Kunde unverändert", await tab.js(f"fetch('/api/projects/{seed['project']}').then(r=>r.json()).then(x=>x.customer_id)"),
             seed["kunde"])
    await tab.bild("8_kundenwechsel_abgelehnt")
    p.pruefe("Projektmappe: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Behinderungsanzeige abschließen (1.8.41)", uhr="10:00"))
