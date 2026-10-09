"""Klicktest: Abnahmeprotokoll an den Auftraggeber (1.8.67, Stufe 2c-2e, Punkte 2 und 3; seit 1.8.68 CC fest aus der Fassung,
seit 1.8.69 die Personen der Fassung an ihre Adresse von heute).

Befüllt wie scripts/klicktest_abnahmeprotokoll.py (Hallenbau GmbH, Bernd Bau, Petra Plan), der Auftraggeber mit E-Mail, Petra
Plan "Kopie bei Anzeigen" mit E-Mail, Bernd Bau "Kopie bei Anzeigen" ohne E-Mail; SMTP an einen Empfänger im Skript (es verlässt
keine Mail den Rechner). Ein Protokoll, vom Auftraggeber (Folge: Abnahme) und vom Auftragnehmer unterschrieben -> Fassungen 1, 2;
danach bekommt Petra Plan eine neue E-Mail-Adresse.

    Büro (1400 px, dunkel)  Karte "Protokoll an den Auftraggeber": bereit, Fassung 2, An fest der Auftraggeber, Kopie (CC) fest
                            -- Petra Plan mit ihrer Adresse von heute (seit 1.8.69; 1.8.68: die der Fassung), Bernd Bau "keine
                            Mail: keine E-Mail-Adresse", kein Eingabefeld; Hinweis "Beteiligte seit Fassung 2 geändert" mit alter
                            und neuer Adresse; Senden -> Rückfrage, Umschlag Auftraggeber + Petra Plan (neue Adresse), Anhang =
                            Fassung 2 (SHA-256), danach "versendet" und eine Zeile im Versandverlauf mit "Zustellung nachtragen"
                            und "Laut „Kopie an:“ ohne Mail: Bernd Bau". Unterschrift des Auftragnehmers verworfen -> die Karte
                            nennt Fassung 1.
                            Auftragsseite: an der Abnahme "Fassung 1 (PDF)" (Punkt 3), der Link liefert das PDF.
    Büro (412 px, hell)     Protokollseite ohne waagrechten Scrollbalken.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_protokoll_versand.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln: siehe scripts/cdp_klicktest.py. Feste Uhr 10:00.
"""

import hashlib
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_abnahme_aus_protokoll import _unterschrift_png  # noqa: E402
from klicktest_abnahmeprotokoll import befuellen as befuellen_basis  # noqa: E402
from klicktest_checkliste_unterschrift import CONFIRM  # noqa: E402
from klicktest_versandprotokoll import POSTFACH, _smtp_starten  # noqa: E402

A = "abnahme."
AG = "auftraggeber@klicktest.example"
PLAN = "petra.plan@klicktest.example"
PLAN_NEU = "petra.neu@klicktest.example"
KARTE = "document.getElementById('protocolDispatchCard')"


def befuellen(db, k):
    from sqlalchemy import select

    from app import checklists as cl
    from app.email_sending import update_smtp_settings
    from app.models import AppUser, Customer, ProjectParticipant

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        smtp_port = s.getsockname()[1]
    update_smtp_settings(db, host="127.0.0.1", port=smtp_port, username="buero", encryption="none",
                         sender_email="buero@klicktest.example", sender_name="Klicktest GmbH", password="pw")
    seed = befuellen_basis(db, k)
    db.scalar(select(Customer).where(Customer.name == "Hallenbau GmbH")).email = AG
    for p in db.scalars(select(ProjectParticipant)):
        p.copy_on_notices = True
        if p.contact.last_name == "Plan":
            p.contact.email = PLAN
    db.commit()
    olga = db.scalar(select(AppUser).where(AppUser.username == "olga"))
    c = cl.create_checklist(db, template_id=seed["vorlage"], context_type="auftrag", order_id=seed["auftrag"])
    f = {x["field_key"].removeprefix(A): x["id"] for x in c["fields"]}
    for key, wert in (("teilnehmer", "Herbert Halle, Olga Office"), ("umfang", "gesamt"), ("ergebnis", "abgenommen"),
                      ("vorbehalt_maengel", "nein"), ("vorbehalt_vertragsstrafe", "nein")):
        cl.save_answer(db, c["id"], f[key], wert)
    cl.add_attachment(db, c["id"], f["unterschrift_auftraggeber"], _unterschrift_png(), signer_person="Herbert Halle",
                      account_user_id=olga.id, account_name="Olga Office")
    an = cl.add_attachment(db, c["id"], f["unterschrift_auftragnehmer"], _unterschrift_png(), account_user_id=olga.id,
                           account_name="Olga Office")
    an_id = next(a["id"] for a in an["attachments"] if a["field_id"] == f["unterschrift_auftragnehmer"])
    for p in db.scalars(select(ProjectParticipant)):  # seit 1.8.68: nach den Fassungen geändert -> Hinweis, CC bleibt
        if p.contact.last_name == "Plan":
            p.contact.email = PLAN_NEU
    db.commit()
    return {**seed, "smtp_port": smtp_port, "protokoll": c["id"], "an": an_id}


async def pruefen(tab, seed, p):
    server = _smtp_starten(seed["smtp_port"])
    try:
        await _pruefen(tab, seed, p)
    finally:
        server.shutdown()


async def _pruefen(tab, seed, p):
    import asyncio

    cid = seed["protokoll"]
    bereit = "document.querySelector('#clMain .q') && !document.querySelector('#clMain').textContent.includes('Lädt')"
    karte_da = f"{KARTE} && {KARTE}.querySelector('.badge')"
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")

    # --- Büro, 1400 px, dunkel ------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.warten(karte_da, 15)
    p.pruefe("Karte: bereit, Fassung 2", await tab.js(
        f"[{KARTE}.querySelector('.badge').textContent, {KARTE}.querySelector('[data-protocol-version]').textContent.startsWith('Fassung 2 ')]"),
        ["bereit", True])
    p.pruefe("Kopie (CC) fest: Petra Plan mit der Adresse von heute, Bernd Bau ohne Mail, kein Eingabefeld", await tab.js(
        f"(c=>[(t=>t.includes('Petra Plan') && t.includes('<{PLAN_NEU}>'))(c.querySelector('[data-copy-mail]').textContent), "
        f"(t=>t.includes('Bernd Bau') && t.includes('keine Mail: keine E-Mail-Adresse'))(c.querySelector('[data-copy-nomail]').textContent), "
        f"c.querySelectorAll('input').length, !document.getElementById('protocolCc')])({KARTE}.querySelector('[data-protocol-cc]'))"),
        [True, True, 0, True])
    p.pruefe("Hinweis: Beteiligte seit Fassung 2 geändert, mit alter und neuer Adresse", await tab.js(
        f"(w=>!!w && w.textContent.includes('seit Fassung 2 geändert') && w.textContent.includes('heute {PLAN_NEU} statt {PLAN}'))"
        f"({KARTE}.querySelector('[data-copy-changes]'))"), True)
    p.pruefe("An fest der Auftraggeber, kein Eingabefeld", await tab.js(
        f"[{KARTE}.querySelector('[data-notice-to]').textContent.includes('{AG}'), {KARTE}.querySelectorAll('[data-notice-to] input').length]"),
        [True, 0])
    p.pruefe("kein allgemeiner Versand für das Protokoll", await tab.js("!document.getElementById('sendCard')"), True)
    await tab.js(f"{KARTE}.scrollIntoView()")
    await tab.bild("1_protokoll_bereit_dunkel")
    fassung2 = await tab.js(f"fetch('/api/checklists/{cid}/protocol-dispatch').then(r=>r.json()).then(s=>s.version.sent_document.sha256)")
    await tab.js("document.getElementById('protocolSend').click()")
    await tab.warten(f"{KARTE}.querySelector('.badge') && {KARTE}.querySelector('.badge').textContent==='versendet'", 20)
    for _ in range(30):
        if POSTFACH:
            break
        await asyncio.sleep(0.2)
    mail = POSTFACH[0] if POSTFACH else None
    anhang = None
    for part in (mail["message"].walk() if mail else []):
        if part.get_content_disposition() == "attachment":
            anhang = part.get_payload(decode=True)
    p.pruefe("Rückfrage vor dem Senden nennt die Änderung", await tab.js(
        "window.__confirms.some(m=>m.includes('seit Fassung 2 geändert') && m.includes('Kopie an:'))"), True)
    p.pruefe("Versand: Umschlag Auftraggeber + Petra Plan mit der Adresse von heute", mail["rcpts"] if mail else None,
             [AG, PLAN_NEU])
    p.pruefe("Mail: Cc-Kopfzeile = Personen der Fassung, Adresse von heute", (mail["message"]["Cc"] or "") if mail else None,
             PLAN_NEU)
    p.pruefe("Anhang = Fassung 2 aus der Ablage (SHA-256)", hashlib.sha256(anhang or b"").hexdigest(), fassung2)
    await tab.warten("document.querySelector('#protocolDispatchHistory [data-dispatch-row]')", 15)
    p.pruefe("Versandverlauf: Zeile und 'Zustellung nachtragen'", await tab.js(
        "[document.querySelectorAll('#protocolDispatchHistory [data-dispatch-row]').length, "
        "!!document.getElementById('protocolDispatchHistory-toggle')]"), [1, True])
    p.pruefe("Versandverlauf: Bernd Bau laut „Kopie an:“ ohne Mail (seit 1.8.69)", await tab.js(
        "document.querySelector('#protocolDispatchHistory [data-copy-missed]')?.textContent"),
        "Laut „Kopie an:“ ohne Mail: Bernd Bau (Bauleitung des Auftraggebers) – keine E-Mail-Adresse")
    p.pruefe("Büro: keine JS-Fehler", tab.fehler, [])
    await tab.js(f"{KARTE}.scrollIntoView()")
    await tab.bild("2_protokoll_versendet_dunkel")

    # --- Unterschrift des Auftragnehmers verworfen: Fassung 1 --------------------------------------------------------
    status = await tab.js(
        f"fetch('/api/checklists/{cid}/discard-signatures',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        f"body:JSON.stringify({{signature_id:{seed['an']},reason:'falsches Konto'}})}}).then(r=>r.status)")
    p.pruefe("Unterschrift des Auftragnehmers verworfen", status, 200)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.warten(karte_da, 15)
    p.pruefe("Karte nennt jetzt Fassung 1 (2 ist überholt)", await tab.js(
        f"{KARTE}.querySelector('[data-protocol-version]').textContent.startsWith('Fassung 1 ')"), True)

    # --- Auftragsseite: Abnahme verweist auf die Fassung ---------------------------------------------------------------
    await tab.oeffnen(f"/orders/{seed['auftrag']}", "document.getElementById('acceptanceList') && "
                                                     "!document.getElementById('acceptanceList').textContent.includes('Lädt')")
    await tab.warten("document.querySelector('#acceptanceList [data-protocol-version]')", 15)
    p.pruefe("Abnahme: Nachweis mit 'Fassung 1 (PDF)', Link liefert das PDF", await tab.js(
        "(a=>fetch(a.getAttribute('href')).then(r=>[a.textContent, r.status, r.headers.get('content-type')]))"
        "(document.querySelector('#acceptanceList [data-protocol-version]'))"), ["Fassung 1 (PDF)", 200, "application/pdf"])
    p.pruefe("Auftragsseite: keine JS-Fehler", tab.fehler, [])
    await tab.js("document.getElementById('acceptanceCard').scrollIntoView()")
    await tab.bild("3_auftrag_abnahme_fassung_dunkel")

    # --- 412 px, hell -----------------------------------------------------------------------------------------------
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    await tab.warten(karte_da, 15)
    p.pruefe("412 px: kein waagrechter Scrollbalken", await tab.js(
        "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.js(f"{KARTE}.scrollIntoView()")
    await tab.bild("4_protokoll_412_hell")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
