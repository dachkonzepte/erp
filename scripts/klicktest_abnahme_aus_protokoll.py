"""Klicktest: Abnahme aus dem Abnahmeprotokoll (1.8.63, Stufe 2c-2d Teil 2, Punkt 3).

Befüllt wie scripts/klicktest_abnahmeprotokoll.py (Hallenbau GmbH, Objekt "Halle Nord" mit Nord, Süd, Alt archiviert, Bernd
Bau mit Vollmacht zur Abnahme), dazu zwei Protokolle, deren Unterschrift des Auftraggebers ohne Folge gespeichert ist (Abbruch
nach dem Commit): "B" ohne Hindernis, "C" mit der Dachfläche Süd, die danach archiviert wurde.

    Büro (1400 px, dunkel)  Protokoll A über die Seite ausgefüllt und vom Auftraggeber unterschrieben (Person, Funktion) ->
                            Karte "Folgen": "Abnahme vom …" erledigt mit Link; Auftragsseite: Abnahme förmlich, "Nachweis:
                            Abnahmeprotokoll Nr. …", "unterschrieben von Herbert Halle (Geschäftsführer)", Prüfung stimmt,
                            statt "+ Mangel erfassen" der Hinweis aufs Protokoll; Mangel mit Aufgabe in der Karte "Mängel".
                            Ausstehend: B und C mit Hinweis, C mit Grund "Süd archiviert"; "Abnahme jetzt anlegen" bei B ->
                            angelegt, Hinweis weg; bei C -> "Nicht angelegt: …".
                            Unterschrift des Auftraggebers in A verwerfen -> abgelehnt (erst die Abnahme verwerfen).
    Büro (412 px, hell)     Auftragsseite ohne waagrechten Scrollbalken.

`confirm()` wird automatisch bestätigt. Unterschrift in A mit echten Mausereignissen. Feste Uhr 10:00.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_abnahme_aus_protokoll.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_abnahmeprotokoll import befuellen as befuellen_basis  # noqa: E402
from klicktest_checkliste_unterschrift import CONFIRM  # noqa: E402
from klicktest_unterzeichner import _knopf, _zeichnen  # noqa: E402

A = "abnahme."


def _unterschrift_png() -> bytes:
    from PIL import Image, ImageDraw

    bild = Image.new("RGB", (600, 200), "white")
    ImageDraw.Draw(bild).line([(40, 150), (200, 60), (320, 140), (560, 50)], fill="black", width=6)
    puffer = io.BytesIO()
    bild.save(puffer, format="PNG")
    return puffer.getvalue()


def befuellen(db, k):
    from sqlalchemy import select

    import app.checklist_follow_ups as folgen
    from app import checklists as cl
    from app.defects import create_protocol_defect
    from app.models import RoofArea

    seed = befuellen_basis(db, k)
    flaechen = {r.name: r.id for r in db.scalars(select(RoofArea))}
    vorher = folgen.run_follow_ups_after_signature
    folgen.run_follow_ups_after_signature = lambda *a, **kw: None  # Abbruch nach dem Commit der Unterschrift
    try:
        protokolle = {}
        for name, flaeche in (("B", "Nord"), ("C", "Süd")):
            c = cl.create_checklist(db, template_id=seed["vorlage"], context_type="auftrag", order_id=seed["auftrag"])
            f = {x["field_key"].removeprefix(A): x["id"] for x in c["fields"]}
            for key, wert in (("teilnehmer", f"Protokoll {name}"), ("umfang", "gesamt"), ("ergebnis", "abgenommen"),
                              ("vorbehalt_maengel", "ja"), ("vorbehalt_vertragsstrafe", "nein")):
                cl.save_answer(db, c["id"], f[key], wert)
            cl.save_answer(db, c["id"], f["dachflaechen"], [flaechen[flaeche]])
            create_protocol_defect(db, c["id"], {"description": f"Mangel aus Protokoll {name}"}, [], user_id=None,
                                   user_name="Olga Office")
            cl.add_attachment(db, c["id"], f["unterschrift_auftraggeber"], _unterschrift_png(),
                              signer_person="Herbert Halle", account_name="Olga Office")
            protokolle[name] = c["id"]
    finally:
        folgen.run_follow_ups_after_signature = vorher
    db.get(RoofArea, flaechen["Süd"]).archived = True
    db.commit()
    return {**seed, "protokolle": protokolle}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    bereit = "document.querySelector('#clMain .q') && !document.querySelector('#clMain').textContent.includes('Lädt')"
    auftrag = seed["auftrag"]
    abnahmen = (f"fetch('/api/orders/{auftrag}/acceptances').then(r=>r.json())")

    # --- Protokoll A über die Seite ------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    await tab.oeffnen(f"/orders/{auftrag}", "document.body && document.readyState==='complete'")
    await tab.js("localStorage.setItem('erp_theme','dark')")
    cid = await tab.js(
        f"fetch('/api/checklists',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify("
        f"{{template_id:{seed['vorlage']},context_type:'auftrag',order_id:{auftrag}}})}}).then(r=>r.json()).then(d=>d.id)")
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    f = await tab.js("Object.fromEntries(cl.fields.map(x=>[x.field_key.replace('abnahme.',''),x.id]))")
    feld = lambda key: f"document.getElementById('q_{f[key]}')"  # noqa: E731
    await tab.js(f"(t=>{{t.value='Herbert Halle, Olga Office';t.dispatchEvent(new Event('input'))}})"
                 f"({feld('teilnehmer')}.querySelector('textarea'))")
    await tab.js(f"flushSave({f['teilnehmer']})")
    for key, wert in (("umfang", "Gesamtabnahme"), ("ergebnis", "Abnahme erklärt"), ("vorbehalt_maengel", "Ja"),
                      ("vorbehalt_vertragsstrafe", "Nein")):
        await tab.js(f"[...{feld(key)}.querySelectorAll('.tile')].find(t=>t.textContent==={wert!r}).click()")
        await tab.warten(f"[...{feld(key)}.querySelectorAll('.tile.on')].some(t=>t.textContent==={wert!r})", 10)
    await tab.warten(f"document.getElementById('pdefList_{f['maengel']}') && !document.getElementById('pdefList_{f['maengel']}').textContent.includes('Lädt')", 10)
    await tab.js(f"document.getElementById('pdefDesc_{f['maengel']}').value='Attika West undicht';"
                 f"document.getElementById('pdefSave_{f['maengel']}').click()")
    await tab.warten(f"document.querySelectorAll('#pdefList_{f['maengel']} .pdef').length===1", 15)
    ag = f["unterschrift_auftraggeber"]
    await tab.js(f"(s=>{{s.selectedIndex=1;s.dispatchEvent(new Event('change'))}})(document.getElementById('padWho_{ag}'))")
    await tab.js(f"document.getElementById('padPerson_{ag}').value='Herbert Halle';"
                 f"document.getElementById('padFunction_{ag}').value='Geschäftsführer'")
    await _zeichnen(tab, ag)
    await tab.js(_knopf(ag))
    await tab.warten(f"document.querySelectorAll('#q_{ag} .sig').length===1", 15)
    await tab.warten("document.querySelector('#followUpsCard .rule-row a')", 15)
    p.pruefe("Folgen: Abnahme angelegt, erledigt, Link auf den Auftrag", await tab.js(
        "(r=>[r.querySelector('a').textContent.startsWith('Abnahme vom '), r.querySelector('a').getAttribute('href'), "
        "r.querySelector('.badge').textContent])(document.querySelector('#followUpsCard .rule-row'))"),
        [True, f"/orders/{auftrag}#acceptanceCard", "erledigt"])
    p.pruefe("Protokoll A: keine JS-Fehler", tab.fehler, [])
    await tab.bild("1_protokoll_folge_dunkel")

    # --- Auftragsseite ---------------------------------------------------------------------------------------------
    await tab.oeffnen(f"/orders/{auftrag}", "document.getElementById('protocolPending') && "
                                             "!document.getElementById('acceptanceList').textContent.includes('Lädt')")
    await tab.warten("document.querySelectorAll('#protocolPending [data-protocol-pending]').length===2", 15)
    eintrag_a = (f"[...document.querySelectorAll('#acceptanceList .acc-item')].find(e=>e.innerText.includes("
                 f"'Abnahmeprotokoll Nr. {cid}'))")
    p.pruefe("Abnahme aus A: förmlich, Nachweis Protokoll, Person, kein '+ Mangel erfassen'", await tab.js(
        f"(e=>[e.querySelector('.acc-head').textContent.includes('förmlich'), !!e.querySelector('[data-protocol-proof] a'), "
        f"e.innerText.includes('unterschrieben von Herbert Halle (Geschäftsführer)'), "
        f"e.innerText.includes('+ Mangel erfassen'), e.innerText.includes('ihre Mängel stehen dort'), "
        f"!e.querySelector('.acc-bad')])({eintrag_a})"), [True, True, True, False, True, True])
    p.pruefe("Mangel aus A an der Abnahme mit Aufgabe", await tab.js(
        f"fetch('/api/orders/{auftrag}/defects').then(r=>r.json()).then(l=>l.filter(d=>d.checklist_id==={cid})"
        f".map(d=>[d.protocol_pending, d.task.exists]))"), [[False, True]])
    b, c = seed["protokolle"]["B"], seed["protokolle"]["C"]
    p.pruefe("Ausstehend: B ohne Grund, C mit Grund 'Süd archiviert'", await tab.js(
        f"[{b},{c}].map(i=>(e=>[!!e, !!e.querySelector('.acc-bad'), e.innerText.includes('„Süd“ ist archiviert')])"
        f"(document.querySelector('[data-protocol-pending=\"'+i+'\"]')))"), [[True, False, False], [True, True, True]])
    await tab.js("document.getElementById('acceptanceCard').scrollIntoView()")
    await tab.bild("2_auftrag_ausstehend_dunkel")
    await tab.js(f"document.querySelector('[data-protocol-pending=\"{c}\"] button').click()")
    await tab.warten(f"document.getElementById('protocolPendingStatus{c}').textContent.startsWith('Nicht angelegt')", 15)
    p.pruefe("C: 'Abnahme jetzt anlegen' -> nicht angelegt mit Grund", await tab.js(
        f"document.getElementById('protocolPendingStatus{c}').textContent.includes('„Süd“ ist archiviert')"), True)
    await tab.js(f"document.querySelector('[data-protocol-pending=\"{b}\"] button').click()")
    await tab.warten(f"!document.querySelector('[data-protocol-pending=\"{b}\"]')", 15)
    p.pruefe("B angelegt: Hinweis weg, zwei Abnahmen aus Protokollen", await tab.js(
        f"{abnahmen}.then(l=>l.filter(a=>a.from_protocol).map(a=>a.protocol.checklist_id).sort((x,y)=>x-y))"),
        sorted([cid, b]))
    p.pruefe("Auftragsseite: keine JS-Fehler", tab.fehler, [])
    await tab.js("document.getElementById('acceptanceCard').scrollIntoView()")
    await tab.bild("3_auftrag_nachgeholt_dunkel")

    # --- Verwerfen der Unterschrift bei gültiger Abnahme ---------------------------------------------------------------
    sig = await tab.js(f"fetch('/api/checklists/{cid}').then(r=>r.json()).then(d=>d.attachments.find(a=>a.field_id==={ag}).id)")
    p.pruefe("Unterschrift des Auftraggebers verwerfen: 409 mit Weg", await tab.js(
        f"fetch('/api/checklists/{cid}/discard-signatures',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        f"body:JSON.stringify({{signature_id:{sig},reason:'neu'}})}}).then(async r=>[r.status,(await r.json()).detail"
        f".includes('erst die Abnahme am Auftrag')])"), [409, True])

    # --- 412 px, hell ---------------------------------------------------------------------------------------------------
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/orders/{auftrag}", "document.getElementById('acceptanceList') && "
                                             "!document.getElementById('acceptanceList').textContent.includes('Lädt')")
    p.pruefe("412 px: kein waagrechter Scrollbalken", await tab.js(
        "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.js("document.getElementById('acceptanceCard').scrollIntoView()")
    await tab.bild("4_auftrag_412_hell")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
