"""Klicktest: Beteiligte mit Adressbuch (1.8.37, Stufe 2b, Runde 2b-2).

Prüft Adressbuch und Reiter "Beteiligte" so, wie das Büro sie benutzt:

    Adressbuch     Stammdaten -> Adressbuch: Liste zuerst, archivierte erst mit Häkchen, "Löschen" nur
                   ohne Projekt, Archivieren eines verwendeten Kontakts, Löschen eines unbenutzten
    Projektmappe   Reiter "Beteiligte": Kunde als Auftraggeber oben; Hinzufügen sucht zuerst (Treffer
                   filtern beim Tippen, archivierte fehlen), Rolle und "Kopie bei Anzeigen"; doppelte
                   Zuordnung mit lesbarer Meldung; nicht gefunden -> "Neuen Kontakt anlegen" mit dem
                   Suchtext vorbelegt, nach dem Speichern zurück in den Dialog mit dem neuen Kontakt;
                   Empfangsvollmacht mit Beleg (PDF), Häkchen weg lässt den Beleg stehen; Rolle über
                   die Auswahl ändern; archivierter Kontakt gekennzeichnet; hell/dunkel, 412 px
    dazu           Kontaktformular zeigt "Eingetragen in Projekten", Büro-Suche findet den Kontakt,
                   Monteur 403 auf API und Formularseite

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_beteiligte.py [--app-port N] [--cdp-port N]
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
PDF = "%PDF-1.4\\n1 0 obj<<>>endobj\\ntrailer<<>>\\n%%EOF\\n"


def befuellen(db, k):
    from app.contacts import create_contact, set_contact_archived
    from app.models import AppUser, Customer, Employee, Project
    from app.project_participants import add_participant
    from app.project_pipeline_columns import default_pipeline_column_id

    monteur = Employee(first_name="Max", last_name="Monteur", employee_group="gewerblich", active=True)
    db.add(monteur); db.flush()
    bert = AppUser(username="bert", display_name="Bert Büro", role="buero_auftrag", password_hash=k.passwort())
    max_ = AppUser(username="max", display_name="Max Monteur", role="field", employee_id=monteur.id, password_hash=k.passwort())
    db.add_all([bert, max_]); db.flush()
    kunde = Customer(name="Familie Klar", last_name="Familie Klar")
    db.add(kunde); db.flush()
    spalte = default_pipeline_column_id(db)
    projekt = Project(project_number="P-2026-0101", customer_id=kunde.id, name="Dachsanierung Klar", pipeline_column_id=spalte)
    anderes = Project(project_number="P-2026-0102", customer_id=kunde.id, name="Garage Klar", pipeline_column_id=spalte)
    db.add_all([projekt, anderes]); db.commit()
    anna = create_contact(db, {"kind": "person", "first_name": "Anna", "last_name": "Architekt", "company_name": "Büro Plan",
                               "function": "Planerin", "phone": "0241 100", "email": "anna@example.org", "city": "Aachen"})
    meyer = create_contact(db, {"kind": "firma", "company_name": "Hausverwaltung Meyer GmbH", "phone": "0241 200",
                                "street": "Verwalterweg 2", "postal_code": "52062", "city": "Aachen"})
    alt = create_contact(db, {"kind": "person", "last_name": "Altkontakt"})
    set_contact_archived(db, alt, True)
    add_participant(db, anderes, anna, role="architekt_planer")
    return {"cookies": {"bert": k.cookies(bert), "max": k.cookies(max_)}, "projekt": projekt.id, "anderes": anderes.id,
            "anna": anna.id, "meyer": meyer.id, "alt": alt.id}


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


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.anmelden(seed["cookies"]["bert"])
    projekt = seed["projekt"]
    await tab.oeffnen("/master-data?hell=1", "document.readyState==='complete'")
    await tab.js("localStorage.setItem('erp_theme','light')")  # headless Chrome wählt sonst Dunkel

    # --- Adressbuch ----------------------------------------------------------------------------------------
    await tab.oeffnen("/master-data#contacts", "document.getElementById('title').textContent==='Adressbuch'")
    zeilen = "[...document.querySelectorAll('#content tbody tr')].map(r=>r.cells[0].innerText.split('\\n')[0])"
    p.pruefe("Adressbuch: Liste zuerst, ohne Archivierte", await tab.js(zeilen), ["Anna Architekt", "Hausverwaltung Meyer GmbH"])
    p.pruefe("Adressbuch: Projekte je Kontakt", await tab.js("[...document.querySelectorAll('#content tbody tr')].map(r=>r.cells[5].innerText)"), ["1", "—"])
    p.pruefe("Adressbuch: Löschen nur ohne Projekt", await tab.js("[...document.querySelectorAll('#content tbody tr')].map(r=>r.cells[7].innerText.includes('Löschen'))"), [False, True])
    p.pruefe("Adressbuch: Tabelle ohne seitliches Scrollen", await tab.js("(()=>{const w=document.querySelector('#content .wrap');return w.scrollWidth<=w.clientWidth})()"), True)
    await tab.js("document.getElementById('showArchivedContacts').click()")
    p.pruefe("Adressbuch: mit Archivierten", await tab.js(zeilen), ["Altkontakt", "Anna Architekt", "Hausverwaltung Meyer GmbH"])
    p.pruefe("Adressbuch: Hinzufügen öffnet die Formularseite", await tab.js("document.getElementById('addLink').getAttribute('href')"), "/master-data/contacts/new")
    await tab.bild("adressbuch_liste")
    p.pruefe("Adressbuch: JS-Fehler", tab.fehler, [])

    # --- Reiter Beteiligte -----------------------------------------------------------------------------------
    bereit = "document.getElementById('participantClient')!==null"
    await tab.oeffnen(f"/projects/{projekt}#sec-participants", bereit)
    p.pruefe("Reiter aktiv über die Adresse", await tab.js("document.getElementById('sec-participants').classList.contains('active')"), True)
    p.pruefe("Kunde als Auftraggeber oben", await tab.js("document.getElementById('participantClient').innerText.includes('Familie Klar')&&document.getElementById('participantClient').innerText.includes('Auftraggeber')"), True)
    p.pruefe("Noch keine Beteiligten", await tab.js("document.getElementById('tabCountParticipants').textContent"), "0")

    treffer = "[...document.querySelectorAll('#pmResults .pm-hit b')].map(b=>b.textContent)"
    await tab.js("openParticipantModal()")
    await tab.warten("document.querySelectorAll('#pmResults .pm-hit').length===2")
    p.pruefe("Dialog: erst suchen -- Treffer ohne Archivierte", await tab.js(treffer), ["Anna Architekt", "Hausverwaltung Meyer GmbH"])
    p.pruefe("Dialog: Suchfeld hat den Fokus", await tab.js("document.activeElement.id"), "pmSearch")
    await tab.js(SUCHE % "meyer")
    await tab.warten("document.querySelectorAll('#pmResults .pm-hit').length===1")
    p.pruefe("Dialog: Treffer filtern beim Tippen", await tab.js(treffer), ["Hausverwaltung Meyer GmbH"])
    await tab.js("document.querySelector('#pmResults .pm-hit').click()")
    p.pruefe("Dialog: Kontakt gewählt", await tab.js("document.getElementById('pmChosenStep').style.display===''&&document.getElementById('pmChosenText').innerText.startsWith('Hausverwaltung Meyer GmbH')"), True)
    p.pruefe("Dialog: ohne Rolle abgelehnt", await tab.js("saveParticipant().then(()=>document.getElementById('pmStatus').textContent)"), "Bitte eine Rolle wählen.")
    await tab.js("document.getElementById('pmRole').value='hausverwaltung';document.getElementById('pmCopy').checked=true")
    await tab.js("saveParticipant()")
    await tab.warten("!document.getElementById('participantModal').classList.contains('open')")
    karte = "document.querySelector('[data-participant-id]')"
    p.pruefe("Hinzugefügt: Rolle, Kopie bei Anzeigen, Zähler",
             await tab.js(f"[{karte}.querySelector('.p-role').value,{karte}.querySelector('.p-copy').checked,{karte}.querySelector('.p-authorized').checked,document.getElementById('tabCountParticipants').textContent]"),
             ["hausverwaltung", True, False, "1"])

    # doppelte Zuordnung
    await tab.js("openParticipantModal()")
    await tab.js(SUCHE % "meyer")
    await tab.warten("document.querySelectorAll('#pmResults .pm-hit').length===1&&document.querySelector('#pmResults .pm-hit').innerText.includes('bereits als')")
    p.pruefe("Dialog: Treffer zeigt vorhandene Rolle", "bereits als Hausverwaltung" in (await tab.js("document.querySelector('#pmResults .pm-hit').innerText") or ""), True)
    await tab.js("document.querySelector('#pmResults .pm-hit').click();document.getElementById('pmRole').value='hausverwaltung'")
    meldung = await tab.js("saveParticipant().then(()=>document.getElementById('pmStatus').textContent)")
    p.pruefe("Doppelt: lesbare Meldung, Dialog bleibt offen",
             [meldung, await tab.js("document.getElementById('participantModal').classList.contains('open')")],
             ["Fehler: Hausverwaltung Meyer GmbH ist in diesem Projekt bereits als Hausverwaltung eingetragen.", True])

    # nicht gefunden -> neu anlegen -> zurück in den Dialog
    await tab.js("pmChooseOther()")
    await tab.js(SUCHE % "Lot")
    await tab.warten("document.getElementById('pmResults').innerText.includes('Kein Kontakt gefunden')")
    link = await tab.js("document.getElementById('pmNewContact').getAttribute('href')")
    p.pruefe("Nicht gefunden: Link mit Projekt und Suchtext", link, f"/master-data/contacts/new?projekt={projekt}&name=Lot")
    p.pruefe("Dialog: JS-Fehler", tab.fehler, [])
    await tab.oeffnen(link, "document.getElementById('lastName')!==null")
    p.pruefe("Formular: Nachname aus dem Suchtext", await tab.js("document.getElementById('lastName').value"), "Lot")
    await tab.js("document.getElementById('kindFirma').click()")
    p.pruefe("Formular: Firma blendet die Namen aus", await tab.js("[document.getElementById('lastNameWrap').classList.contains('hidden'),document.getElementById('companyLabel').textContent]"), [True, "Firmenname *"])
    await tab.js("document.getElementById('kindPerson').click()")
    await tab.js("""document.getElementById('firstName').value='Gerd';document.getElementById('companyName').value='Gutachterbüro Lot';
                    document.getElementById('function').value='Sachverständiger Dach';document.getElementById('city').value='Düren';
                    document.getElementById('email').value='lot@example.org';save()""")
    tab.fehler = []
    zurueck = await _warten_ueber_seitenwechsel(tab, "location.pathname==='/projects/%d'&&document.getElementById('participantModal')?.classList.contains('open')&&document.getElementById('pmChosenStep').style.display===''" % projekt)
    p.pruefe("Nach dem Speichern zurück in der Projektmappe", zurueck, True)
    p.pruefe("Zurück in der Projektmappe: neuer Kontakt im Dialog gewählt",
             (await tab.js("document.getElementById('pmChosenText').innerText") or "").startswith("Gerd Lot"), True)
    p.pruefe("Adresse ohne ?kontakt=", await tab.js("location.search+location.hash"), "#sec-participants")
    await tab.js("document.getElementById('pmRole').value='sachverstaendiger';document.getElementById('pmAuthorized').checked=true;saveParticipant()")
    await tab.warten("document.querySelectorAll('[data-participant-id]').length===2")
    p.pruefe("Zwei Beteiligte, Reihenfolge der Rollen", await tab.js("[...document.querySelectorAll('[data-participant-id] .p-role')].map(s=>s.value)"), ["hausverwaltung", "sachverstaendiger"])

    # Vollmacht als Beleg
    lot = "[...document.querySelectorAll('[data-participant-id]')].find(k=>k.innerText.includes('Gerd Lot'))"
    lot_id = await tab.js(f"Number({lot}.dataset.participantId)")
    await tab.js(f"uploadPowerOfAttorney({lot_id},{{files:[new File([\"{PDF}\"],'Vollmacht Lot.pdf',{{type:'application/pdf'}})],value:''}})")
    await tab.warten(f"{lot}?.innerText.includes('Vollmacht Lot.pdf')")
    p.pruefe("Vollmacht: auf der Karte", "Vollmacht Lot.pdf" in (await tab.js(f"{lot}.innerText") or ""), True)
    p.pruefe("Vollmacht: Link liefert das PDF", await tab.js(f"fetch({lot}.querySelector('.p-poa a').href).then(r=>r.text()).then(t=>t.startsWith('%PDF-'))"), True)
    await tab.js(f"{lot}.querySelector('.p-authorized').click()")
    await tab.warten(f"{lot}?.innerText.includes('Empfangsvollmacht nicht gesetzt')")
    p.pruefe("Häkchen weg: Beleg bleibt", [await tab.js(f"{lot}.querySelector('.p-authorized').checked"), "Vollmacht Lot.pdf" in (await tab.js(f"{lot}.innerText") or "")], [False, True])

    # Rolle über die Auswahl ändern
    meyer_karte = "[...document.querySelectorAll('[data-participant-id]')].find(k=>k.innerText.includes('Meyer'))"
    await tab.js(f"(()=>{{const s={meyer_karte}.querySelector('.p-role');s.value='eigentuemer';s.dispatchEvent(new Event('change'))}})()")
    # participants ist der Stand nach der Antwort des Servers (replaceParticipant), nicht der Wert der Auswahl
    await tab.warten("participants.some(b=>b.role==='eigentuemer')")
    p.pruefe("Rolle geändert und gespeichert", await tab.js(f"fetch('/api/projects/{projekt}/participants').then(r=>r.json()).then(l=>l.map(b=>b.role).sort().join())"), "eigentuemer,sachverstaendiger")
    p.pruefe("Projektmappe: JS-Fehler", tab.fehler, [])
    await tab.bild("beteiligte_hell")

    # --- Archivieren eines verwendeten Kontakts, Löschen eines unbenutzten -----------------------------------
    await tab.oeffnen("/master-data?archiv=1#contacts", "document.getElementById('title').textContent==='Adressbuch'")
    await tab.js(f"setContactArchived({seed['meyer']},true)")
    await tab.warten("document.querySelectorAll('#content tbody tr').length===2")
    p.pruefe("Archiviert: fehlt in der Liste", await tab.js(zeilen), ["Anna Architekt", "Gerd Lot"])
    p.pruefe("Gelöscht wird nur ohne Projekt (Server)", await tab.js(f"fetch('/api/contacts/{seed['anna']}',{{method:'DELETE'}}).then(r=>r.status)"), 409)
    await tab.js("document.getElementById('showArchivedContacts').click()")
    await tab.js(f"deleteContact({seed['alt']})")
    await tab.warten("!document.getElementById('content').innerText.includes('Altkontakt')")
    p.pruefe("Unbenutzter Kontakt gelöscht", await tab.js(f"fetch('/api/contacts/{seed['alt']}').then(r=>r.status)"), 404)
    p.pruefe("Adressbuch: JS-Fehler", tab.fehler, [])
    await tab.oeffnen(f"/projects/{projekt}?nach=archiv#sec-participants", bereit)
    p.pruefe("Projektmappe: archivierter Kontakt gekennzeichnet", "archiviert" in (await tab.js(meyer_karte + ".innerText") or ""), True)
    await tab.js("openParticipantModal()")
    await tab.warten("document.querySelectorAll('#pmResults .pm-hit').length>0")
    p.pruefe("Dialog: archivierter Kontakt nicht angeboten", await tab.js(treffer), ["Anna Architekt", "Gerd Lot"])
    await tab.js("closeModal('participantModal')")

    # --- Formular, Suche --------------------------------------------------------------------------------------
    lot_kontakt = await tab.js(f"fetch('/api/projects/{projekt}/participants').then(r=>r.json()).then(l=>l.find(b=>b.role==='sachverstaendiger').contact_id)")
    await tab.oeffnen(f"/master-data/contacts/{lot_kontakt}/edit", "document.getElementById('contactProjects')!==null")
    p.pruefe("Formular: eingetragen in Projekten", (await tab.js("document.getElementById('contactProjects').innerText") or "").replace("\n", " "), "P-2026-0101 · Dachsanierung Klar – Sachverständiger/Gutachter")
    await tab.oeffnen("/suche?q=Gutachterb%C3%BCro", "document.getElementById('resultGroups').innerText.includes('Adressbuch')")
    p.pruefe("Büro-Suche: Gruppe Adressbuch mit Link", await tab.js("[...document.querySelectorAll('#resultGroups a')].some(a=>a.getAttribute('href')==='/master-data/contacts/%d/edit')" % lot_kontakt), True)
    p.pruefe("Formular/Suche: JS-Fehler", tab.fehler, [])

    # --- dunkel und schmal ------------------------------------------------------------------------------------
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/projects/{projekt}?dunkel=1#sec-participants", bereit)
    await tab.bild("beteiligte_dunkel")
    await tab.js("openParticipantModal()")
    await tab.warten("document.querySelectorAll('#pmResults .pm-hit').length>0")
    await tab.bild("dialog_dunkel")
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen(f"/projects/{projekt}?schmal=1#sec-participants", bereit)
    p.pruefe("412 px: kein seitliches Scrollen", await tab.js("document.documentElement.scrollWidth<=window.innerWidth"), True)
    await tab.bild("beteiligte_412")
    await tab.fenster(1400, 1000)

    # --- Monteur ----------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["max"])
    await tab.oeffnen("/mobil", "document.readyState==='complete'")
    p.pruefe("Monteur: API gesperrt", await tab.js(f"Promise.all(['/api/contacts','/api/projects/{projekt}/participants','/api/project-participant-roles'].map(u=>fetch(u).then(r=>r.status))).then(s=>s.join())"), "403,403,403")
    await tab.oeffnen("/master-data/contacts/new", "document.readyState==='complete'")
    p.pruefe("Monteur: Formularseite gesperrt", "nicht verfügbar" in (await tab.js("document.body.innerText") or ""), True)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Beteiligte mit Adressbuch (1.8.37)", uhr="10:00"))
