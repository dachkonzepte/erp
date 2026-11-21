"""Klicktest: das Archiv wiederfinden (1.10.15, Antwort F4 vom 21.11.2026) -- nur Musterdaten.

Testdaten: Bea Büro – Auftrag, Mona Monteurin. Zacharias Archiv (im Archiv) mit Hauptadresse, einer Anfrage und einem Projekt ohne Auftrag samt Angebot im
Archiv; Zora Aktiv mit Hauptadresse.

    Kopfzeile     „Zacharias“: keine Treffer aus dem Archiv, eine Zeile „5 Treffer im Archiv“ -> Suche mit Filter „im Archiv“
    Suche         Gruppe „im Archiv“ (Kunde, Objekt, Anfrage, Projekt, Angebot) ohne Links, je „Zurückholen und öffnen“; die Gruppe „Kunden“ ohne Zacharias;
                  „Zurückholen und öffnen“ am Objekt -> Seite des Objekts, der Kunde ist zurück (Kundenakte ohne Hinweis), die Vorgänge bleiben im Archiv
    412 px        Suche hell und dunkel ohne Überlauf, Bilder
    Monteurin     keine Büro-Suche (403)
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_archiv_wiederfinden.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

SUCHE_BEREIT = "!!document.getElementById('resultGroups').textContent.trim()"
ARCHIV = "document.getElementById('archiv')"


def befuellen(db, k):
    from app.models import AppUser, Customer, CustomerProfile, Inquiry, Project, Property, Quote
    from app.project_pipeline_columns import default_pipeline_column_id

    alt = datetime.utcnow() - timedelta(days=250)
    im_archiv = datetime.utcnow() - timedelta(days=3)
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    mona = AppUser(username="mona", display_name="Mona Monteurin", role="field", password_hash=k.passwort())
    db.add_all([bea, mona])
    kunden = {}
    for vor, nach, archiv in (("Zacharias", "Archiv", im_archiv), ("Zora", "Aktiv", None)):
        c = Customer(name=f"{vor} {nach}", first_name=vor, last_name=nach, city="Musterstadt", created_at=alt, archiviert_am=archiv)
        db.add(c)
        db.flush()
        db.add(CustomerProfile(customer_id=c.id, customer_number=f"K-90{c.id}"))
        db.add(Property(customer_id=c.id, name="Hauptadresse", street=f"{nach}weg 1", postal_code="12345", city="Musterstadt", is_primary_address=True))
        kunden[vor] = c
    z = kunden["Zacharias"]
    anfrage = Inquiry(inquiry_number="AN-2026-0901", customer_id=z.id, title="Undichtes Vordach", created_at=alt, archiviert_am=im_archiv)
    projekt = Project(project_number="P-2026-0902", name="Neues Dach", customer_id=z.id, pipeline_column_id=default_pipeline_column_id(db),
                      created_at=alt, archived=True, archiviert_am=im_archiv)
    db.add_all([anfrage, projekt])
    db.flush()
    db.add(Quote(project_id=projekt.id, quote_number="A-2026-0903", title="Neues Dach", status="versendet"))
    db.commit()
    objekt = db.query(Property).filter(Property.customer_id == z.id).one()
    return {"bea": k.cookies(bea), "mona": k.cookies(mona), "zacharias": z.id, "objekt": objekt.id, "anfrage": anfrage.id, "projekt": projekt.id}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);")
    await tab.fenster(1440, 1000)
    await tab.anmelden(seed["bea"])
    await tab.oeffnen("/", "true")
    await tab.js("localStorage.setItem('erp_theme','light')")

    # Kopfzeile
    p.pruefe("Start geladen", await tab.oeffnen("/?n=1", "!!document.getElementById('appTopbarSearchInput')"), True)
    await tab.warte_auf_ruhe()
    await tab.js("const i=document.getElementById('appTopbarSearchInput');i.focus();i.value='Zacharias';i.dispatchEvent(new Event('input',{bubbles:true}))")
    await tab.warten("[...document.querySelectorAll('.app-topbar-search-hit')].length>0", 10)
    await tab.warte_auf_ruhe()
    zeilen = await tab.js("[...document.querySelectorAll('.app-topbar-search-hit')].map(a=>[a.querySelector('.grp').textContent,"
                          "a.querySelector('.ttl').textContent,a.getAttribute('href')])")
    p.pruefe("Kopfzeile: nur eine Zeile ins Archiv, kein Treffer daraus", zeilen,
             [["im Archiv", "5 Treffer im Archiv", "/suche?q=Zacharias&types=archiv"]])
    await tab.bild("kopfzeile_im_archiv_1440_hell")

    # Suche
    await tab.js("document.querySelector('.app-topbar-search-hit').click()")
    await tab.warten(f"location.pathname==='/suche'&&!!{ARCHIV}", 15)
    await tab.warte_auf_ruhe()
    p.pruefe("Suche: nur die Gruppe „im Archiv“ (Filter aus der Kopfzeile)", await tab.js(
        "[...document.querySelectorAll('#resultGroups h2')].map(h=>h.firstChild.textContent.trim())"), ["im Archiv"])
    p.pruefe("Suche: Filter „im Archiv“ aktiv", await tab.js(
        "[...document.querySelectorAll('#typeFilters button.active')].map(b=>b.textContent)"), ["im Archiv"])
    treffer = await tab.js(f"[...{ARCHIV}.querySelectorAll('.result-archiv')].map(z=>[z.querySelector('.sub').textContent.split(' · ')[0],"
                           "z.querySelector('button').textContent,!!z.querySelector('a')])")
    p.pruefe("Suche: Kunde, Objekt, Anfrage, Projekt, Angebot -- ohne Link, je „Zurückholen und öffnen“", treffer,
             [[a, "Zurückholen und öffnen", False] for a in ("Kunde", "Objekt", "Anfrage", "Projekt", "Angebot")])
    p.pruefe("Suche: Hinweis zum Archiv", await tab.js(f"{ARCHIV}.textContent.includes('Öffnen nur über „Zurückholen und öffnen“')"), True)
    await tab.bild("suche_im_archiv_1440_hell")

    p.pruefe("Suche ohne Filter: Zacharias nicht unter „Kunden“", await tab.oeffnen("/suche?q=Zacharias", f"!!{ARCHIV}"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Suche ohne Filter: Gruppen", await tab.js(
        "[...document.querySelectorAll('#resultGroups h2')].map(h=>h.firstChild.textContent.trim())"), ["im Archiv"])

    for thema, name in (("light", "hell"), ("dark", "dunkel")):
        await tab.fenster(412, 1000, mobil=True)
        await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
        p.pruefe(f"412 px {name}: geladen", await tab.oeffnen(f"/suche?q=Zacharias&types=archiv&n={name}", f"!!{ARCHIV}"), True)
        await tab.warte_auf_ruhe()
        p.pruefe(f"412 px {name}: ohne Überlauf", await tab.ueberlauf(), [])
        await tab.bild(f"suche_im_archiv_412_{name}")
    await tab.fenster(1440, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")

    # Zurückholen und öffnen (am Objekt -> der Kunde kommt zurück)
    p.pruefe("Suche neu geladen", await tab.oeffnen("/suche?q=Zacharias&types=archiv&n=2", f"!!{ARCHIV}"), True)
    await tab.warte_auf_ruhe()
    await tab.js(f"[...{ARCHIV}.querySelectorAll('.result-archiv')].find(z=>z.querySelector('.sub').textContent.startsWith('Objekt'))"
                 ".querySelector('button').click()")
    await tab.warten(f"location.pathname==='/properties/{seed['objekt']}'", 15)
    p.pruefe("Zurückholen und öffnen: Seite des Objekts", await tab.js("location.pathname"), f"/properties/{seed['objekt']}")
    await tab.warte_auf_ruhe()
    p.pruefe("Kundenakte ohne „im Archiv“", await tab.oeffnen(f"/customers/{seed['zacharias']}", "typeof customer!=='undefined'&&!!customer"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Kundenakte: Hinweis verborgen", await tab.js("document.getElementById('archivHinweis').hidden"), True)
    p.pruefe("Suche danach: Kunde unter „Kunden“, die Vorgänge weiter im Archiv", await tab.oeffnen("/suche?q=Zacharias&n=3", f"!!{ARCHIV}"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Suche danach: Gruppen und Arten im Archiv", await tab.js(
        f"[[...document.querySelectorAll('#resultGroups h2')].map(h=>h.firstChild.textContent.trim()),"
        f"[...{ARCHIV}.querySelectorAll('.result-archiv .sub')].map(s=>s.textContent.split(' · ')[0])]"),
        [["Kunden", "Objekte", "im Archiv"], ["Anfrage", "Projekt", "Angebot"]])
    p.pruefe("keine JS-Fehler", tab.fehler, [])

    # Monteurin
    await tab.anmelden(seed["mona"])
    p.pruefe("Monteurin: Büro-Suche 403", await tab.js("fetch('/api/search?q=Zacharias').then(r=>r.status)"), 403)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
