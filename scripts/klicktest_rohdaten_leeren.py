"""Klicktest: Rohdaten erledigter Zeilen des Adressimports leeren (1.10.21, Antwort F3 vom 21.11.2026) -- nur Musterdaten.

Testdaten: Anna Admin, Fritz Büro – Finanzen. Ein Importlauf mit fünf Zeilen: Kunde (mit angelegtem Kunden), Lieferant (mit angelegtem Lieferanten), bereits
importiert, Arbeitsliste verworfen, Arbeitsliste offen -- alle mit erfundenen Namen, Anschriften, Telefon und Mail.

    Vorschau      Karte „Rohdaten erledigter Zeilen“: „4 erledigte Zeilen tragen noch Rohdaten …“ je Art, „offen in der Arbeitsliste 1“, Knopf da
    Leeren        Rückfrage, danach „4 Zeilen geleert.“, die Karte sagt „Keine erledigte Zeile …“, kein Knopf; die offene Zeile steht mit Namen in der
                  Arbeitsliste; über die Schnittstelle: Vorschau 0, schon leer 4
    412 px        hell und dunkel ohne Überlauf, Bilder
    Büro          die Seite und die Schnittstelle nur für den Admin (403)
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_rohdaten_leeren.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "typeof rohdaten!=='undefined'&&!!rohdaten"
KARTE = "document.getElementById('rohdatenCard')"


def befuellen(db, k):
    from app.models import AppUser, Customer, ImportedAddress, ImportRun, Supplier

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    fritz = AppUser(username="fritz", display_name="Fritz Finanzen", role="buero_finanzen", password_hash=k.passwort())
    db.add_all([anna, fritz])
    lauf = ImportRun(source_filename="adressen.csv", status="completed", row_count_total=5)
    db.add(lauf)
    db.flush()
    kunde = Customer(name="Erika Musterfrau", first_name="Erika", last_name="Musterfrau", legacy_address_number="1001", import_run_id=lauf.id)
    lieferant = Supplier(name="Holz Muster GmbH", supplier_number="L-1", legacy_address_number="1002", import_run_id=lauf.id)
    db.add_all([kunde, lieferant])
    db.flush()
    person = dict(first_name="Erika", last_name="Musterfrau", street="Musterweg 1", postal_code="12345", city="Musterstadt", phone="0000 111",
                  email="erika@example.invalid")
    for n, werte in enumerate([dict(classification="customer", legacy_address_number="1001", created_customer_id=kunde.id),
                               dict(classification="supplier", legacy_address_number="1002", created_supplier_id=lieferant.id),
                               dict(classification="duplicate", legacy_address_number="1001"),
                               dict(classification="unassigned", legacy_address_number="1004", resolution="discarded", resolved_at=datetime(2026, 10, 1)),
                               dict(classification="unassigned", legacy_address_number="1005", last_name="Offenbach")], 2):
        db.add(ImportedAddress(import_run_id=lauf.id, row_number=n, status="confirmed", **{**person, **werte}))
    db.commit()
    return {"anna": k.cookies(anna), "fritz": k.cookies(fritz)}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=(
        "window.alert=m=>console.error('alert(): '+m);window.__rueckfragen=[];window.confirm=m=>{window.__rueckfragen.push(m);return true};"))
    await tab.anmelden(seed["anna"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/address-import", "true")
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Adressimport geladen", await tab.oeffnen("/address-import?n=1", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Vorschau: Text, was bleibt, Knopf", await tab.js(
        "[document.getElementById('rohdatenText').textContent,document.getElementById('rohdatenBleibt').textContent,document.getElementById('rohdatenKnopf').hidden]"),
        ["4 erledigte Zeilen tragen noch Rohdaten aus dem Altsystem (Kunde: 1, Lieferant: 1, Arbeitsliste erledigt: 1, bereits importiert: 1).",
         "Unverändert bleiben: offen in der Arbeitsliste 1 (bis sie erledigt sind); schon leer: 0.", False])
    await tab.js(f"{KARTE}.scrollIntoView({{block:'start'}})")
    await tab.bild("rohdaten_vorschau_1440_hell")

    for thema, name in (("light", "hell"), ("dark", "dunkel")):
        await tab.fenster(412, 1000, mobil=True)
        await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
        p.pruefe(f"412 px {name}: geladen", await tab.oeffnen(f"/address-import?n={name}", BEREIT), True)
        await tab.warte_auf_ruhe()
        p.pruefe(f"412 px {name}: ohne Überlauf", await tab.ueberlauf(), [])
        await tab.js(f"{KARTE}.scrollIntoView({{block:'start'}})")
        await tab.bild(f"rohdaten_vorschau_412_{name}")
    await tab.fenster(1440, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")

    p.pruefe("neu geladen", await tab.oeffnen("/address-import?n=2", BEREIT), True)
    await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('rohdatenStatus').textContent='';document.getElementById('rohdatenKnopf').click()")
    await tab.warten("document.getElementById('rohdatenStatus').textContent!==''", 10)
    await tab.warte_auf_ruhe()
    p.pruefe("Rückfrage", await tab.js("window.__rueckfragen.map(m=>m.split('?')[0])"),
             ["Bei 4 erledigten Zeilen Namen, Anschriften, Telefon, Mail und Nummern aus dem Altsystem leeren"])
    p.pruefe("geleert: Meldung, Karte, kein Knopf", await tab.js(
        "[document.getElementById('rohdatenStatus').textContent,document.getElementById('rohdatenText').textContent,document.getElementById('rohdatenKnopf').hidden]"),
        ["4 Zeilen geleert.", "Keine erledigte Zeile trägt noch Rohdaten aus dem Altsystem.", True])
    await tab.bild("rohdaten_geleert_1440_hell")
    p.pruefe("die offene Zeile steht mit Namen in der Arbeitsliste", await tab.js(
        "document.getElementById('worklistRows').textContent.includes('Offenbach')"), True)
    p.pruefe("Schnittstelle: Vorschau 0, schon leer 4", await tab.js(
        "fetch('/api/address-import/rohdaten').then(r=>r.json()).then(d=>[d.zahl,d.schon_leer,d.offen_arbeitsliste])"), [0, 4, 1])
    p.pruefe("keine JS-Fehler", tab.fehler, [])

    await tab.anmelden(seed["fritz"])
    p.pruefe("Büro – Finanzen: Schnittstelle 403", await tab.js(
        "Promise.all([fetch('/api/address-import/rohdaten').then(r=>r.status),"
        "fetch('/api/address-import/rohdaten/leeren',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stand:'x'})}).then(r=>r.status)])"),
        [403, 403])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
