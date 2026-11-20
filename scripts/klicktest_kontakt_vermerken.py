"""Klicktest: „Kontakt vermerken“ an Anfrage, Projekt und Kunde (1.10.10, Stufe W1c) -- nur Tag und Weg, nie ein Inhalt.

Testdaten: Anna Admin (angemeldet), Mona Monteurin; ein Kunde mit einem Projekt ohne Auftrag und einer Anfrage ohne Projekt (Musterdaten).

    Anfragen      Editor der Anfrage: „Kontakt vermerken …“ öffnet den Dialog mit Tag = heute (Berlin), Weg leer; ohne Weg nichts gesendet; mit Telefon
                  vermerkt, die Liste nennt Tag, Weg und „vermerkt am … von Anna Admin“
    Akte          „⋮ → Kontakt vermerken …“: gestern per Brief, dann heute per E-Mail -- die Liste der jüngste Kontakt zuerst; ein Tag in der Zukunft
                  lehnt der Dialog ab, ohne zu senden (das Feld begrenzt nur die Auswahl; der Server prüft dasselbe)
    Kundenakte    „⋮ → Kontakt vermerken …“ per Gespräch; 412 px ohne Überlauf, Bild hell und dunkel
    Server        je Bezug genau die vermerkten Kontakte; die Monteurin 403
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_kontakt_vermerken.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

OFFEN = "document.getElementById('kontaktDialog').open"
LISTE = "[...document.querySelectorAll('#kontaktListe li')].map(li=>li.textContent)"


def befuellen(db, k):
    from app.models import AppUser, Customer, Inquiry, Project
    from app.project_pipeline_columns import default_pipeline_column_id

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    mona = AppUser(username="mona", display_name="Mona Monteurin", role="field", password_hash=k.passwort())
    kunde = Customer(name="Erika Muster", first_name="Erika", last_name="Muster", street="Musterweg 1", postal_code="12345", city="Musterstadt")
    db.add_all([anna, mona, kunde])
    db.flush()
    projekt = Project(project_number="P-2026-0901", name="Dachrinne Musterweg", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt)
    db.flush()
    anfrage = Inquiry(inquiry_number="AN-2026-0901", customer_id=kunde.id, title="Undichtes Vordach")
    db.add(anfrage)
    db.commit()
    return {"anna": k.cookies(anna), "mona": k.cookies(mona), "kunde": kunde.id, "projekt": projekt.id, "anfrage": anfrage.id}


async def _vermerken(tab, tag_js: str, weg: str):
    """Tag (JS-Ausdruck) und Weg eintragen, „Kontakt vermerken“ klicken, warten, bis die Antwort angewandt ist."""
    await tab.js(f"document.getElementById('kontaktTag').value={tag_js};document.getElementById('kontaktWeg').value={json.dumps(weg)}")
    await tab.js("document.getElementById('kontaktStatus').textContent=''")
    await tab.js("document.getElementById('kontaktSpeichern').click()")
    await tab.warten("document.getElementById('kontaktStatus').textContent!==''", 10)
    await tab.warte_auf_ruhe()
    return await tab.js("document.getElementById('kontaktStatus').textContent")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);")
    await tab.anmelden(seed["anna"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/inquiries", "true")
    await tab.js("localStorage.setItem('erp_theme','light')")

    # Anfragen
    p.pruefe("Anfragen geladen", await tab.oeffnen("/inquiries?n=1", "document.querySelectorAll('.lead').length>=1"), True)
    await tab.warte_auf_ruhe()
    await tab.js(f"openInquiry({seed['anfrage']})")
    await tab.js("document.querySelector('[data-klick=\"kontakt-anfrage\"]').click()")
    await tab.warten(OFFEN, 5)
    await tab.warte_auf_ruhe()
    p.pruefe("Anfrage: Dialog mit Bezug, Tag heute (Berlin) bis heute, Weg leer", await tab.js(
        "[document.getElementById('kontaktBezug').textContent,document.getElementById('kontaktTag').value===berlinToday(),"
        "document.getElementById('kontaktTag').max===berlinToday(),document.getElementById('kontaktWeg').value]"),
        ["AN-2026-0901 · Undichtes Vordach", True, True, ""])
    p.pruefe("Anfrage: ohne Weg nichts gesendet", await _vermerken(tab, "berlinToday()", ""), "Bitte den Weg wählen.")
    p.pruefe("Anfrage: mit Telefon vermerkt", await _vermerken(tab, "berlinToday()", "telefon"), "Vermerkt.")
    zeilen = await tab.js(LISTE)
    p.pruefe("Anfrage: Liste nennt Tag, Weg, wann und wer", [z.split(" · ", 1)[1].split(" · vermerkt am ")[0] for z in zeilen]
             + [z.endswith("von Anna Admin") for z in zeilen], ["Telefon", True])
    await tab.js("document.querySelector('[data-klick=\"kontakt-schliessen\"]').click()")

    # Akte
    p.pruefe("Akte geladen", await tab.oeffnen(f"/projects/{seed['projekt']}", "typeof project!=='undefined'&&!!project"), True)
    await tab.warte_auf_ruhe()
    await tab.js("document.querySelector('[data-klick=\"kontakt-projekt\"]').click()")
    await tab.warten(OFFEN, 5)
    await tab.warte_auf_ruhe()
    p.pruefe("Akte: Dialog nennt das Projekt", await tab.js("document.getElementById('kontaktBezug').textContent"), "P-2026-0901 · Dachrinne Musterweg")
    gestern = "(()=>{const d=new Date(berlinToday()+'T12:00:00Z');d.setUTCDate(d.getUTCDate()-1);return d.toISOString().slice(0,10)})()"
    morgen = "(()=>{const d=new Date(berlinToday()+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+1);return d.toISOString().slice(0,10)})()"
    p.pruefe("Akte: gestern per Brief", await _vermerken(tab, gestern, "brief"), "Vermerkt.")
    p.pruefe("Akte: heute per E-Mail", await _vermerken(tab, "berlinToday()", "email"), "Vermerkt.")
    p.pruefe("Akte: der jüngste Kontakt zuerst", [z.split(" · ")[1] for z in await tab.js(LISTE)], ["E-Mail", "Brief"])
    p.pruefe("Akte: Tag in der Zukunft abgelehnt, nichts gesendet", await _vermerken(tab, morgen, "telefon"),
             "Der Kontakt darf nicht in der Zukunft liegen.")
    p.pruefe("Akte: danach weiter zwei Vermerke", len(await tab.js(LISTE)), 2)
    await tab.bild("kontakt_akte_1440_hell")
    await tab.js("document.querySelector('[data-klick=\"kontakt-schliessen\"]').click()")

    # Kundenakte, 412 px hell und dunkel
    await tab.fenster(412, 1000, mobil=True)
    for thema, name in (("light", "hell"), ("dark", "dunkel")):
        await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
        p.pruefe(f"Kundenakte {name} geladen", await tab.oeffnen(f"/customers/{seed['kunde']}?n={name}", "typeof customer!=='undefined'&&!!customer"),
                 True)
        await tab.warte_auf_ruhe()
        await tab.js("document.querySelector('[data-klick=\"kontakt-kunde\"]').click()")
        await tab.warten(OFFEN, 5)
        await tab.warte_auf_ruhe()
        if name == "hell":
            p.pruefe("Kundenakte: per Gespräch vermerkt", await _vermerken(tab, "berlinToday()", "gespraech"), "Vermerkt.")
        p.pruefe(f"Kundenakte {name}: Liste", [z.split(" · ")[1] for z in await tab.js(LISTE)], ["Gespräch"])
        p.pruefe(f"Kundenakte {name}: 412 px ohne Überlauf", await tab.ueberlauf(), [])
        await tab.bild(f"kontakt_kundenakte_412_{name}")

    # Server
    p.pruefe("Server: je Bezug genau die vermerkten Kontakte", await tab.js(
        f"Promise.all(['/api/inquiries/{seed['anfrage']}','/api/projects/{seed['projekt']}','/api/customers/{seed['kunde']}']"
        ".map(u=>fetch(u+'/kontakte').then(r=>r.json()).then(l=>l.map(v=>v.weg))))"), [["telefon"], ["email", "brief"], ["gespraech"]])
    p.pruefe("keine JS-Fehler", tab.fehler, [])
    await tab.anmelden(seed["mona"])
    p.pruefe("Monteurin: 403", await tab.js(
        f"fetch('/api/customers/{seed['kunde']}/kontakte').then(r=>r.status)"), 403)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
