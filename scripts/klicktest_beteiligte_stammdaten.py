"""Klicktest: Beteiligte aus den Stammdaten (1.8.39).

Prüft den Dialog "Beteiligten hinzufügen" mit Kunden und Lieferanten so, wie das Büro ihn benutzt:

    Dialog         ohne Suchbegriff nur das Adressbuch mit Hinweis "ab zwei Zeichen"; Treffer nach Herkunft
                   gruppiert (Adressbuch, Kunden, Lieferanten), keine Mitarbeiter; inaktiver Lieferant
                   gekennzeichnet und wählbar; der Kunde des Projekts als Auftraggeber nicht wählbar
    Hinzufügen     Kunde und inaktiver Lieferant: Karte mit "aus Kundenstamm"/"aus Lieferantenstamm",
                   "Lieferant inaktiv", "Kunde öffnen"; derselbe Kunde im zweiten Projekt nutzt denselben
                   Adressbuch-Eintrag; E-Mail im Kunden geändert -> beim Beteiligten sichtbar
    Adressbuch     Liste mit Herkunft; Formular des Eintrags: Hinweis, Stammfelder schreibgeschützt,
                   Funktion speicherbar
    dazu           dunkel, 412 px ohne seitliches Scrollen, Monteur 403

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_beteiligte_stammdaten.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen] [--wanduhr HH:MM]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py. Feste Uhr 10:00, weil der Monteur /mobil öffnet.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

# Tippen ins Suchfeld des Dialogs (in einer Funktion -- ein "const" auf oberster Ebene gälte für die ganze Seite)
SUCHE = "(()=>{const s=document.getElementById('pmSearch');s.value='%s';s.dispatchEvent(new Event('input'))})()"
# Suchen und auf genau diese Antwort warten: pmSearchNow() verwirft ältere Antworten (pmSeq), das Promise endet mit
# der Darstellung -- eine Wartebedingung allein könnte vom Ergebnis der vorigen Suche schon erfüllt sein.
SUCHE_JETZT = "(()=>{const s=document.getElementById('pmSearch');s.value='%s';pmUpdateNewLink();return pmSearchNow().then(()=>true)})()"
GRUPPEN = "[...document.querySelectorAll('#pmResults .pm-group')].map(g=>g.textContent)"
TREFFER = "[...document.querySelectorAll('#pmResults .pm-hit')].map(b=>[b.querySelector('b').textContent,b.disabled])"


def befuellen(db, k):
    from app.contacts import create_contact
    from app.models import AppUser, Customer, Employee, Project, Supplier
    from app.project_pipeline_columns import default_pipeline_column_id

    monteur = Employee(first_name="Max", last_name="Monteur", employee_group="gewerblich", active=True)
    db.add(monteur); db.flush()
    bert = AppUser(username="bert", display_name="Bert Büro", role="buero_auftrag", password_hash=k.passwort())
    max_ = AppUser(username="max", display_name="Max Monteur", role="field", employee_id=monteur.id, password_hash=k.passwort())
    db.add_all([bert, max_]); db.flush()
    klar = Customer(name="Familie Klar", last_name="Familie Klar")
    hof = Customer(name="Hausverwaltung Hof GmbH", last_name="Hausverwaltung Hof GmbH", email="info@hof.example",
                   phone="0241 300", street="Hofweg 1", postal_code="52062", city="Aachen")
    db.add_all([klar, hof]); db.flush()
    stark = Supplier(name="Gerüstbau Stark", city="Köln", phone="0221 1", active=True)
    alt = Supplier(name="Gerüstbau Alt", city="Bonn", active=False)
    db.add_all([stark, alt]); db.flush()
    spalte = default_pipeline_column_id(db)
    projekt = Project(project_number="P-2026-0201", customer_id=klar.id, name="Dachsanierung Klar", pipeline_column_id=spalte)
    zweites = Project(project_number="P-2026-0202", customer_id=klar.id, name="Garage Klar", pipeline_column_id=spalte)
    hofprojekt = Project(project_number="P-2026-0203", customer_id=hof.id, name="Flachdach Hof", pipeline_column_id=spalte)
    db.add_all([projekt, zweites, hofprojekt]); db.commit()
    create_contact(db, {"kind": "person", "first_name": "Anna", "last_name": "Architekt", "city": "Aachen"})
    return {"cookies": {"bert": k.cookies(bert), "max": k.cookies(max_)}, "projekt": projekt.id, "zweites": zweites.id,
            "hofprojekt": hofprojekt.id, "hof": hof.id, "alt": alt.id}


async def _warten_ueber_seitenwechsel(tab, bedingung: str, timeout: float = 20) -> bool:
    """Wie tab.warten(), aber ein Auswerten während der Navigation (Kontext weg) zählt als "noch nicht"."""
    import asyncio
    import time

    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        try:
            if await tab.js(f"(()=>{{try{{return !!({bedingung})}}catch(e){{return false}}}})()"):
                return True
        except RuntimeError:
            pass
        await asyncio.sleep(0.2)
    return False


async def _dialog(tab, suchtext: str, bedingung: str):
    await tab.js(SUCHE_JETZT % suchtext)
    await tab.warten(bedingung)


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.anmelden(seed["cookies"]["bert"])
    projekt, hof = seed["projekt"], seed["hof"]
    await tab.oeffnen("/master-data?hell=1", "document.readyState==='complete'")
    await tab.js("localStorage.setItem('erp_theme','light')")  # headless Chrome wählt sonst Dunkel

    # --- Dialog ----------------------------------------------------------------------------------------------
    bereit = "document.getElementById('participantClient')!==null"
    await tab.oeffnen(f"/projects/{projekt}#sec-participants", bereit)
    await tab.js("openParticipantModal()")
    await tab.warten("document.querySelectorAll('#pmResults .pm-hit').length===1")
    p.pruefe("Ohne Suchbegriff: nur das Adressbuch", [await tab.js(GRUPPEN), await tab.js(TREFFER)], [["Adressbuch"], [["Anna Architekt", False]]])
    p.pruefe("Hinweis auf die Quellen", await tab.js("document.getElementById('pmSources').textContent"),
             "Gesucht in: Adressbuch, Kunden, Lieferanten – Kunden und Lieferanten ab zwei Zeichen")
    await tab.js(SUCHE % "Gerüst")
    await tab.warten("document.getElementById('pmResults').innerText.includes('Gerüstbau Stark')")
    p.pruefe("Tippen: Lieferanten gruppiert", await tab.js(GRUPPEN), ["Lieferanten"])
    p.pruefe("Inaktiver Lieferant gekennzeichnet und wählbar",
             await tab.js("[...document.querySelectorAll('#pmResults .pm-hit')].map(b=>[b.innerText.includes('Lieferant inaktiv'),b.disabled])"),
             [[True, False], [False, False]])
    await _dialog(tab, "Klar", "document.querySelectorAll('#pmResults .pm-hit').length===1")
    p.pruefe("Auftraggeber: gekennzeichnet, nicht wählbar", [await tab.js(GRUPPEN), await tab.js(TREFFER),
             "Auftraggeber dieses Projekts" in (await tab.js("document.querySelector('#pmResults .pm-hit').innerText") or "")],
             [["Kunden"], [["Familie Klar", True]], True])
    await tab.js("document.querySelector('#pmResults .pm-hit').click()")
    p.pruefe("Auftraggeber: Klick wählt nichts", await tab.js("document.getElementById('pmChosenStep').style.display"), "none")
    await _dialog(tab, "Max", "document.getElementById('pmResults').innerText.includes('Kein Treffer.')")
    p.pruefe("Keine Mitarbeiter", await tab.js(GRUPPEN), [])
    await tab.bild("dialog_gruppen_hell")

    # --- Kunde hinzufügen ------------------------------------------------------------------------------------
    await _dialog(tab, "Hof", "document.querySelectorAll('#pmResults .pm-hit').length===1")
    p.pruefe("Kunde gefunden", [await tab.js(GRUPPEN), await tab.js(TREFFER)], [["Kunden"], [["Hausverwaltung Hof GmbH", False]]])
    await tab.js("document.querySelector('#pmResults .pm-hit').click()")
    p.pruefe("Gewählt mit Herkunft", "aus Kundenstamm" in (await tab.js("document.getElementById('pmChosenText').innerText") or ""), True)
    await tab.js("document.getElementById('pmRole').value='hausverwaltung';saveParticipant()")
    await tab.warten("document.querySelectorAll('[data-participant-id]').length===1")
    karte = "[...document.querySelectorAll('[data-participant-id]')].find(k=>k.innerText.includes('Hof GmbH'))"
    text = await tab.js(f"{karte}.innerText") or ""
    p.pruefe("Karte: Herkunft und Werte des Kunden", ["aus Kundenstamm" in text, "info@hof.example" in text, "Hofweg 1" in text], [True, True, True])
    p.pruefe("Karte: Kunde öffnen", await tab.js(f"[...{karte}.querySelectorAll('a')].find(a=>a.textContent==='Kunde öffnen')?.getAttribute('href')"), f"/customers/{hof}")

    # --- inaktiven Lieferanten hinzufügen --------------------------------------------------------------------
    await tab.js("openParticipantModal()")
    await _dialog(tab, "Gerüstbau Alt", "document.querySelectorAll('#pmResults .pm-hit').length===1")
    await tab.js("document.querySelector('#pmResults .pm-hit').click();document.getElementById('pmRole').value='anderes_gewerk';saveParticipant()")
    await tab.warten("document.querySelectorAll('[data-participant-id]').length===2")
    alt_karte = "[...document.querySelectorAll('[data-participant-id]')].find(k=>k.innerText.includes('Gerüstbau Alt'))"
    text = await tab.js(f"{alt_karte}.innerText") or ""
    p.pruefe("Lieferant: Herkunft und inaktiv", ["aus Lieferantenstamm" in text, "Lieferant inaktiv" in text, "Lieferant öffnen" in text], [True, True, True])

    # --- E-Mail im Kunden ändern -> beim Beteiligten sichtbar ------------------------------------------------
    status = await tab.js(f"fetch('/api/customers/{hof}').then(r=>r.json()).then(k=>{{k.email='neu@hof.example';return fetch('/api/customers/{hof}',{{method:'PUT',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(k)}})}}).then(r=>r.status)")
    p.pruefe("Kunde gespeichert", status, 200)
    await tab.oeffnen(f"/projects/{projekt}?neu=1#sec-participants", "document.querySelectorAll('[data-participant-id]').length===2")
    text = await tab.js(f"{karte}.innerText") or ""
    p.pruefe("Geänderte E-Mail beim Beteiligten", ["neu@hof.example" in text, "info@hof.example" in text], [True, False])
    p.pruefe("Projektmappe: JS-Fehler", tab.fehler, [])
    await tab.bild("beteiligte_aus_stammdaten_hell")

    # --- derselbe Kunde im zweiten Projekt: derselbe Eintrag -------------------------------------------------
    await tab.oeffnen(f"/projects/{seed['zweites']}#sec-participants", bereit)
    await tab.js("openParticipantModal()")
    await _dialog(tab, "Hof", "document.querySelectorAll('#pmResults .pm-hit').length===1")
    await tab.js("document.querySelector('#pmResults .pm-hit').click();document.getElementById('pmRole').value='eigentuemer';saveParticipant()")
    await tab.warten("document.querySelectorAll('[data-participant-id]').length===1")
    p.pruefe("Ein Adressbuch-Eintrag für den Kunden, in zwei Projekten",
             await tab.js(f"fetch('/api/contacts').then(r=>r.json()).then(l=>l.filter(c=>c.source==='customer'&&c.source_id==={hof}).map(c=>c.project_count))"), [2])

    # --- Projekt des Kunden: Auftraggeber --------------------------------------------------------------------
    await tab.oeffnen(f"/projects/{seed['hofprojekt']}#sec-participants", bereit)
    await tab.js("openParticipantModal()")
    await _dialog(tab, "Hof", "document.querySelectorAll('#pmResults .pm-hit').length===1")
    p.pruefe("Eigener Kunde (mit Adressbuch-Eintrag) nicht wählbar", await tab.js(TREFFER), [["Hausverwaltung Hof GmbH", True]])
    await tab.js("closeModal('participantModal')")

    # --- Adressbuch -------------------------------------------------------------------------------------------
    await tab.oeffnen("/master-data#contacts", "document.getElementById('title').textContent==='Adressbuch'")
    zeilen = "[...document.querySelectorAll('#content tbody tr')].map(r=>r.cells[0].innerText.replace(/\\n/g,' | '))"
    p.pruefe("Adressbuch: Herkunft in der Liste", await tab.js(zeilen),
             ["Anna Architekt", "Gerüstbau Alt | aus Lieferantenstamm · Lieferant inaktiv", "Hausverwaltung Hof GmbH | aus Kundenstamm"])
    p.pruefe("Adressbuch: Tabelle ohne seitliches Scrollen", await tab.js("(()=>{const w=document.querySelector('#content .wrap');return w.scrollWidth<=w.clientWidth})()"), True)
    eintrag = await tab.js(f"fetch('/api/contacts').then(r=>r.json()).then(l=>l.find(c=>c.source_id==={hof}&&c.source==='customer').id)")
    await tab.oeffnen(f"/master-data/contacts/{eintrag}/edit", "document.getElementById('contactSourceHint')!==null")
    p.pruefe("Formular: Hinweis aus Kundenstamm", (await tab.js("document.getElementById('contactSourceHint').innerText") or "").startswith("aus Kundenstamm"), True)
    p.pruefe("Formular: Stammfelder schreibgeschützt, Funktion frei",
             await tab.js("[...['companyName','email','phone','street','city'].map(i=>document.getElementById(i).readOnly),document.getElementById('function').readOnly,document.getElementById('kindFirma').disabled]"),
             [True, True, True, True, True, False, True])
    p.pruefe("Formular: Werte des Kunden", await tab.js("[document.getElementById('companyName').value,document.getElementById('email').value]"), ["Hausverwaltung Hof GmbH", "neu@hof.example"])
    await tab.bild("eintrag_formular_hell")
    p.pruefe("Formular: JS-Fehler", tab.fehler, [])
    await tab.js("document.getElementById('function').value='Objektbetreuung';save()")
    tab.fehler = []
    p.pruefe("Formular: nach dem Speichern zurück in der Liste",
             await _warten_ueber_seitenwechsel(tab, "location.pathname==='/master-data'&&document.getElementById('title')?.textContent==='Adressbuch'"), True)
    gespeichert = await tab.js(f"fetch('/api/contacts/{eintrag}').then(r=>r.json()).then(c=>[c.function,c.email])")
    p.pruefe("Formular: Funktion gespeichert, E-Mail weiter aus dem Kunden", gespeichert, ["Objektbetreuung", "neu@hof.example"])
    p.pruefe("Adressbuch: JS-Fehler", tab.fehler, [])

    # --- dunkel und schmal ------------------------------------------------------------------------------------
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/projects/{projekt}?dunkel=1#sec-participants", bereit)
    await tab.bild("beteiligte_aus_stammdaten_dunkel")
    await tab.js("openParticipantModal()")
    await _dialog(tab, "Ger", "document.querySelectorAll('#pmResults .pm-group').length===1")
    await tab.bild("dialog_gruppen_dunkel")
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/projects/{projekt}?schmal=1#sec-participants", bereit)
    await tab.js("openParticipantModal()")
    await _dialog(tab, "Gerüst", "document.querySelectorAll('#pmResults .pm-hit').length===2")
    p.pruefe("412 px: kein seitliches Scrollen", await tab.js("document.documentElement.scrollWidth<=window.innerWidth"), True)
    await tab.bild("dialog_412")
    await tab.fenster(1400, 1000)

    # --- Monteur ----------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["max"])
    await tab.oeffnen("/mobil", "document.readyState==='complete'")
    p.pruefe("Monteur: Suche des Dialogs gesperrt", await tab.js(f"fetch('/api/projects/{projekt}/participant-candidates?q=Hof').then(r=>r.status)"), 403)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Beteiligte aus den Stammdaten (1.8.39)", uhr="10:00"))
