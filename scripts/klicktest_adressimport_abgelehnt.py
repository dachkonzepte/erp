"""Klicktest: Adressimport lehnt eine Zeile mit zu langem Wert ab, die übrigen gehen durch (1.9.351, Runde V2a, Punkt 2, F7).

Testdaten: Anna Admin (angemeldet). Die Datei (CSV, im Arbeitsordner geschrieben): Zeile 2 Kunde, Zeile 3 Kunde mit PLZ aus 21 Zeichen und Ort aus
121 Zeichen, Zeile 4 Lieferant.

    Hochladen     Kennzahlen Kunden 1, Lieferanten 1, Abgelehnt 1; Liste „Abgelehnte Zeilen“ mit „Zeile 3: PLZ hat 21 Zeichen – höchstens 20.“ und
                  „Zeile 3: Ort hat 121 Zeichen – höchstens 120.“; in der Tabelle Zeile 3 „Abgelehnt“ mit dem Hinweis
    Neuladen      Vorschau samt Liste wieder da (die abgelehnte Zeile steht in der Vorschau, nicht nur in der Antwort)
    Bilder        1440 und 412 px, hell und dunkel; bei 412 px läuft nichts über die Seite
    Bestätigen    Meldung nennt „1 abgelehnt (nicht übernommen)“; auf dem Server nur die Kundin aus Zeile 2 und der Lieferant aus Zeile 4
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_adressimport_abgelehnt.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import csv
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

KOPF = ["Adresse", "Kunde", "Lieferant", "Anrede", "Titel", "Vorname", "Name", "Straße", "Land", "PLZ", "Ort", "Telefon", "Fax", "Mobil", "Mail"]
ZEILEN = [
    {"Adresse": "A-1", "Kunde": "K-1", "Vorname": "Erika", "Name": "Probe", "Straße": "Hauptstraße 1", "PLZ": "12345", "Ort": "Musterstadt"},
    {"Adresse": "A-2", "Kunde": "K-2", "Vorname": "Max", "Name": "Zulang", "Straße": "Nebenweg 2", "PLZ": "1" * 21, "Ort": "o" * 121},
    {"Adresse": "A-3", "Lieferant": "L-1", "Name": "Holz Probe GmbH", "PLZ": "54321", "Ort": "Probedorf"},
]
BEREIT = "document.getElementById('runRows')&&document.getElementById('runRows').textContent.length>0"
VORSCHAU = "!document.getElementById('previewCard').classList.contains('hidden')&&document.getElementById('previewRows').children.length===3"
LISTE = "[...document.querySelectorAll('#rejectedList li')].map(li=>li.textContent)"
ZAHLEN = "['countCustomers','countSuppliers','countRejected'].map(i=>document.getElementById(i).textContent)"
ZEILE3 = ("(()=>{const tr=[...document.querySelectorAll('#previewRows tr')].find(t=>t.cells[0].textContent==='3');"
          "return [tr.cells[4].textContent,tr.cells[5].textContent]})()")


def _datei() -> str:
    puffer = io.StringIO()
    w = csv.DictWriter(puffer, fieldnames=KOPF, delimiter=";", lineterminator="\r\n")
    w.writeheader()
    for z in ZEILEN:
        w.writerow({h: z.get(h, "") for h in KOPF})
    pfad = Path(tempfile.mkdtemp(prefix="erp-adressimport-")) / "adressen.csv"
    pfad.write_bytes(puffer.getvalue().encode("utf-8"))
    return str(pfad)


def befuellen(db, k):
    from app.models import AppUser

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    db.add(anna)
    db.commit()
    return {"anna": k.cookies(anna), "datei": _datei()}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);")
    await tab.anmelden(seed["anna"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/address-import", "true")
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Adressimport geladen", await tab.oeffnen("/address-import?n=1", BEREIT), True)
    await tab.warte_auf_ruhe()

    doc = await tab.cmd("DOM.getDocument", depth=1)
    node = await tab.cmd("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector="#fileInput")
    await tab.cmd("DOM.setFileInputFiles", files=[seed["datei"]], nodeId=node["nodeId"])
    await tab.js("uploadFile()")
    p.pruefe("Vorschau da", await tab.warten(VORSCHAU, 15), True)
    await tab.warte_auf_ruhe()
    erwartet = ["Zeile 3: PLZ hat 21 Zeichen – höchstens 20.", "Zeile 3: Ort hat 121 Zeichen – höchstens 120."]
    p.pruefe("Liste der abgelehnten Zeilen", await tab.js(LISTE), erwartet)
    p.pruefe("Kennzahlen Kunden, Lieferanten, Abgelehnt", await tab.js(ZAHLEN), ["1", "1", "1"])
    p.pruefe("Zeile 3 in der Tabelle", await tab.js(ZEILE3),
             ["Abgelehnt", "Zeile abgelehnt – PLZ hat 21 Zeichen, höchstens 20; Ort hat 121 Zeichen, höchstens 120."])

    p.pruefe("nach dem Neuladen", await tab.oeffnen("/address-import?n=2", VORSCHAU), True)
    await tab.warte_auf_ruhe()
    p.pruefe("nach dem Neuladen: dieselbe Liste", await tab.js(LISTE), erwartet)

    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            p.pruefe(f"Bild {breite} {name}: geladen", await tab.oeffnen(f"/address-import?n=b{breite}{name}", VORSCHAU), True)
            await tab.warte_auf_ruhe()
            if mobil:
                p.pruefe(f"Bild {breite} {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.js("document.getElementById('previewCard').scrollIntoView({block:'start'})")
            await tab.bild(f"adressimport_abgelehnt_{breite}_{name}")

    await tab.fenster(1440, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen("/address-import?n=3", VORSCHAU)
    await tab.warte_auf_ruhe()
    await tab.js("confirmPreview()")
    p.pruefe("Bestätigen: Meldung", await tab.warten("document.getElementById('confirmStatus').textContent.startsWith('Übernommen')", 15), True)
    p.pruefe("Bestätigen: nennt die abgelehnte Zeile", await tab.js("document.getElementById('confirmStatus').textContent"),
             "Übernommen: 1 Kunde(n), 1 Lieferant(en), 0 unzugeordnet, 0 übersprungen, 1 abgelehnt (nicht übernommen).")
    p.pruefe("auf dem Server nur Zeile 2 und 4", await tab.js(
        "Promise.all([fetch('/api/customers').then(r=>r.json()),fetch('/api/suppliers').then(r=>r.ok?r.json():[])])"
        ".then(([k,l])=>[k.map(x=>x.name).sort(),l.map(x=>x.name)])"), [["Erika Probe"], ["Holz Probe GmbH"]])
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
