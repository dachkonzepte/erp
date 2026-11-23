"""Klicktest: Seiten eines Vorgangs im Archiv sind nur lesbar (1.10.24, Antwort F10 vom 23.11.2026) -- nur Musterdaten.

Testdaten: Fina Büro – Finanzen. Zacharias Archiv mit Hauptadresse, Dachfläche, Kundenwissen, einer Anfrage und einem Projekt ohne Auftrag samt Angebot mit
Titel und Position -- alles angelegt, dann ins Archiv. Dazu eine Anfrage der Webseite von vor neun Monaten (Attrappe des Empfangsdienstes in diesem Prozess):
abgeholt und über die Aufbewahrung ins Archiv gelegt.

    je Seite      Kundenakte (jeder Reiter), Objekt, Dachfläche, Akte (jeder Reiter), Angebot (jeder Reiter rechts), Eingang der Webseite: am <body> die Klasse
                  ds-nur-lesen; kein sichtbarer Knopf im Inhalt außer den lesenden (data-lesen: Zurückholen, Filter, PDF-Vorschau, Reiter des Angebots);
                  kein bedienbares Feld; das „⋮“ fehlt; der Hinweis „im Archiv“ steht da
    Zurückholen   an der Akte: Hinweis weg, Klasse weg, „⋮“ wieder da; das Angebot wieder bearbeitbar („Angebot beauftragen“); die Kundenakte (der Kunde kam
                  mit) mit „+ Projekt“; am Eingang der Webseite: „Verwerfen …“ wieder da
    412 px        Akte und Eingang dunkel nur lesbar, der Eingang ohne Überlauf (die Akte eines Projekts ohne Auftrag läuft schon ohne Archiv
                  über: Tabelle „Angebote“ der Übersicht, Befund 1.10.24), Bilder
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_nur_lesen.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from empfangsdienst_attrappe import Attrappe, muster  # noqa: E402

ATTRAPPE = Attrappe()
NR = "R-20260219-0910-0C1D"


def befuellen(db, k):
    from app.models import AppUser, Customer, CustomerExtraInfo, CustomerProfile, Inquiry, Project, Property, Quote, QuoteItem, QuoteSection, RoofArea
    from app.project_pipeline_columns import default_pipeline_column_id

    alt = datetime.utcnow() - timedelta(days=250)
    im_archiv = datetime.utcnow() - timedelta(days=3)
    fina = AppUser(username="fina", display_name="Fina Finanzen", role="buero_finanzen", password_hash=k.passwort())
    z = Customer(name="Zacharias Archiv", first_name="Zacharias", last_name="Archiv", city="Musterstadt", created_at=alt, email="zacharias@example.invalid")
    db.add_all([fina, z])
    db.flush()
    db.add(CustomerProfile(customer_id=z.id, customer_number="K-9001"))
    objekt = Property(customer_id=z.id, name="Hauptadresse", street="Archivweg 1", postal_code="12345", city="Musterstadt", is_primary_address=True)
    db.add(objekt)
    db.flush()
    flaeche = RoofArea(property_id=objekt.id, name="Nordseite", roof_type="Steildach")
    db.add_all([flaeche, CustomerExtraInfo(customer_id=z.id, info_type="hinweis", value="Hund im Hof")])
    anfrage = Inquiry(inquiry_number="AN-2026-0901", customer_id=z.id, title="Undichtes Vordach", created_at=alt)
    projekt = Project(project_number="P-2026-0902", name="Neues Dach", customer_id=z.id, property_id=objekt.id,
                      pipeline_column_id=default_pipeline_column_id(db), created_at=alt)
    db.add_all([anfrage, projekt])
    db.flush()
    angebot = Quote(project_id=projekt.id, quote_number="A-2026-0903", title="Neues Dach", status="versendet")
    db.add(angebot)
    db.flush()
    titel = QuoteSection(quote_id=angebot.id, title="Dacharbeiten")
    db.add(titel)
    db.flush()
    db.add(QuoteItem(quote_id=angebot.id, position_number="1", short_text="Dachrinne erneuern", unit="m"))
    db.flush()
    # erst anlegen, dann ins Archiv (seit 1.10.23 entsteht an einem Vorgang im Archiv nichts mehr)
    z.archiviert_am = anfrage.archiviert_am = im_archiv
    projekt.archived, projekt.archiviert_am = True, im_archiv
    db.commit()
    return {"fina": k.cookies(fina), "kunde": z.id, "objekt": objekt.id, "flaeche": flaeche.id, "projekt": projekt.id, "angebot": angebot.id}


# Was im Inhalt sichtbar und bedienbar ist: Knöpfe (auch Links im Aussehen eines Knopfs) ohne data-lesen, Felder ohne data-lesen, die nicht gesperrt sind
PRUEFEN = """(()=>{const sicht=e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length)&&getComputedStyle(e).visibility!=='hidden';
const knoepfe=[...document.querySelectorAll('main button, main a.ds-knopf, main a.btn, dialog[open] button')].filter(sicht)
  .filter(k=>!k.hasAttribute('data-lesen')).map(k=>(k.textContent||k.getAttribute('aria-label')||'').trim().slice(0,40));
const felder=[...document.querySelectorAll('main input, main select, main textarea')].filter(sicht)
  .filter(f=>!f.disabled&&!f.hasAttribute('data-lesen')&&f.type!=='hidden').map(f=>f.id||f.name||f.type);
const lesen=[...document.querySelectorAll('main [data-lesen]')].filter(sicht).map(k=>k.textContent.trim().slice(0,30));
return {klasse:document.body.classList.contains('ds-nur-lesen'),knoepfe,felder,lesen}})()"""


async def _seite(tab, p, name, pfad, bereit, reiter=(), klicks=(), lesen_soll=()):
    """Öffnet die Seite, prüft sie und jeden Reiter: Klasse, keine Knöpfe, keine Felder; die lesenden Knöpfe, die da sein sollen."""
    p.pruefe(f"{name}: geladen", await tab.oeffnen(pfad, bereit), True)
    await tab.warte_auf_ruhe()
    gesehen, sammeln = [], set()
    for schritt in [None, *reiter, *klicks]:
        if schritt is not None:
            await tab.js(schritt)
            await tab.warte_auf_ruhe()
        stand = await tab.js(PRUEFEN)
        gesehen.append([schritt or "Start", stand["klasse"], stand["knoepfe"], stand["felder"]])
        sammeln |= set(stand["lesen"])
    p.pruefe(f"{name}: nur lesbar -- je Ansicht Klasse, kein Knopf, kein Feld", [g for g in gesehen if g[1] is not True or g[2] or g[3]], [])
    p.pruefe(f"{name}: die lesenden Knöpfe da", sorted(x for x in lesen_soll if x not in sammeln), [])


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);")
    await tab.fenster(1440, 1000)
    await tab.anmelden(seed["fina"])
    await tab.oeffnen("/", "true")
    await tab.js("localStorage.setItem('erp_theme','light')")

    # Eingang der Webseite: abholen und über die Aufbewahrung ins Archiv
    ATTRAPPE.dazu(muster(NR, name="Wilma Muster", email="wilma@example.invalid", eingang=datetime.now() - timedelta(days=270)))
    await tab.oeffnen("/anfragen/webseite", "true")
    p.pruefe("Eingang abgeholt", await tab.js("fetch('/api/webanfragen/abholen',{method:'POST'}).then(r=>r.json()).then(d=>d.neu)"), 1)
    wid = await tab.js(f"fetch('/api/webanfragen').then(r=>r.json()).then(l=>l.find(x=>x.nummer==='{NR}').id)")
    p.pruefe("Eingang ins Archiv (Aufbewahrung)", await tab.js(
        f"fetch('/api/aufbewahrung/eingang/{wid}/archivieren',{{method:'POST'}}).then(r=>r.json()).then(d=>d.archiviert.length)"), 1)

    reiter = lambda namen: [f"document.querySelector('.reiter a[data-reiter={n}]').click()" for n in namen]  # noqa: E731
    await _seite(tab, p, "Kundenakte", f"/customers/{seed['kunde']}", "typeof customer!=='undefined'&&!!customer",
                 reiter(("projekte", "objekte", "anfragen", "zahlungen", "dokumente", "kontakte", "verlauf", "uebersicht")),
                 lesen_soll=("Zurückholen", "Alles", "Änderungen"))
    await tab.bild("kundenakte_im_archiv_1440_hell")
    await tab.js("document.querySelector('.reiter a[data-reiter=dokumente]').click()")
    p.pruefe("Kundenakte: die Ablage zum Hochladen fehlt (data-schreiben)", await tab.js(
        "getComputedStyle(document.getElementById('docUploadZone')).display"), "none")
    await _seite(tab, p, "Objekt", f"/properties/{seed['objekt']}", "typeof property!=='undefined'&&!!property")
    p.pruefe("Objekt: Hinweis mit Weg zur Kundenakte", await tab.js(
        "[!document.getElementById('archivHinweis').hidden,document.getElementById('archivKundeLink').getAttribute('href')]"),
        [True, f"/customers/{seed['kunde']}"])
    await tab.bild("objekt_im_archiv_1440_hell")
    await _seite(tab, p, "Dachfläche", f"/roof-areas/{seed['flaeche']}", "typeof area!=='undefined'&&!!area")
    p.pruefe("Dachfläche: Hinweis mit Weg zur Kundenakte", await tab.js(
        "[!document.getElementById('archivHinweis').hidden,document.getElementById('archivKundeLink').getAttribute('href')]"),
        [True, f"/customers/{seed['kunde']}"])
    await tab.bild("dachflaeche_im_archiv_1440_hell")
    await _seite(tab, p, "Akte", f"/projects/{seed['projekt']}", "typeof project!=='undefined'&&!!project",
                 reiter(("angebote", "dateien", "verlauf", "uebersicht")), lesen_soll=("Zurückholen", "Alles"))
    p.pruefe("Akte: „⋮“ und Hauptaktion fehlen", await tab.js(
        "['seitenkopfMenueKnopf','hauptaktion'].map(id=>{const e=document.getElementById(id);return !!e&&getComputedStyle(e).display})"),
        ["none", "none"])
    await tab.bild("akte_im_archiv_1440_hell")
    await _seite(tab, p, "Angebot", f"/quotes/{seed['angebot']}/edit", "typeof quote!=='undefined'&&!!quote",
                 klicks=["document.getElementById('tabDetails').click()", "document.getElementById('tabEdit').click()",
                         "document.getElementById('tabCatalog').click()"],
                 lesen_soll=("PDF-Vorschau", "Leistungskatalog", "Angebot", "Bearbeiten"))
    p.pruefe("Angebot: „Angebot beauftragen“ fehlt, Hinweis da", await tab.js(
        "[getComputedStyle(document.getElementById('orderButton')).display,!document.getElementById('archivHinweis').hidden]"), ["none", True])
    p.pruefe("Angebot: keine Zeile des LV mehr ziehbar", await tab.js(
        "[document.querySelectorAll('[draggable=\"true\"]').length,document.querySelectorAll('[data-nur-lesen-zug]').length>0]"), [0, True])
    await tab.bild("angebot_im_archiv_1440_hell")
    await _seite(tab, p, "Eingang", f"/anfragen/webseite/{wid}", "!document.getElementById('archivHinweis').hidden", lesen_soll=("Zurückholen",))
    await tab.bild("eingang_im_archiv_1440_hell")

    # 412 px dunkel
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.fenster(412, 900, mobil=True)
    for name, pfad, bereit in (("Akte", f"/projects/{seed['projekt']}", "typeof project!=='undefined'&&!!project"),
                               ("Eingang", f"/anfragen/webseite/{wid}", "!document.getElementById('archivHinweis').hidden")):
        await tab.oeffnen(pfad, bereit)
        await tab.warte_auf_ruhe()
        if name == "Eingang":  # die Akte eines Projekts ohne Auftrag läuft bei 412 px schon ohne Archiv über (Tabelle „Angebote“, Befund 1.10.24)
            p.pruefe(f"{name}: 412 px ohne Überlauf", await tab.ueberlauf(), [])
        p.pruefe(f"{name}: 412 px nur lesbar", (await tab.js(PRUEFEN))["knoepfe"], [])
        await tab.bild(f"{name.lower()}_im_archiv_412_dunkel")
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.fenster(1440, 1000)

    # Zurückholen an der Akte: alles wieder da -- auch am Angebot und am Kunden (kam mit)
    await tab.oeffnen(f"/projects/{seed['projekt']}", "typeof project!=='undefined'&&!!project")
    await tab.warte_auf_ruhe()
    await tab.js("document.querySelector('[data-klick=projekt-zurueckholen]').click()")
    await tab.warten("document.getElementById('archivHinweis').hidden", 15)
    await tab.warte_auf_ruhe()
    p.pruefe("Akte zurückgeholt: Klasse weg, „⋮“ da", await tab.js(
        "[document.body.classList.contains('ds-nur-lesen'),getComputedStyle(document.getElementById('seitenkopfMenueKnopf')).display!=='none']"),
        [False, True])
    await tab.oeffnen(f"/quotes/{seed['angebot']}/edit", "typeof quote!=='undefined'&&!!quote")
    await tab.warte_auf_ruhe()
    p.pruefe("Angebot nach dem Zurückholen: „Angebot beauftragen“ da, Felder bedienbar", await tab.js(
        "[document.body.classList.contains('ds-nur-lesen'),getComputedStyle(document.getElementById('orderButton')).display!=='none',"
        "[...document.querySelectorAll('main input, main select, main textarea')].some(f=>!f.disabled&&(f.offsetWidth||f.offsetHeight))]"),
        [False, True, True])
    await tab.oeffnen(f"/customers/{seed['kunde']}", "typeof customer!=='undefined'&&!!customer")
    await tab.warte_auf_ruhe()
    p.pruefe("Kundenakte nach dem Zurückholen (der Kunde kam mit): „+ Projekt“ da", await tab.js(
        "[document.body.classList.contains('ds-nur-lesen'),getComputedStyle(document.querySelector('[data-klick=neues-projekt]')).display!=='none']"),
        [False, True])

    # Zurückholen am Eingang der Webseite
    await tab.oeffnen(f"/anfragen/webseite/{wid}", "!document.getElementById('archivHinweis').hidden")
    await tab.warte_auf_ruhe()
    await tab.js("document.querySelector('[data-klick=eingang-zurueckholen]').click()")
    await tab.warten("document.getElementById('archivHinweis').hidden", 15)
    await tab.warte_auf_ruhe()
    p.pruefe("Eingang zurückgeholt: Klasse weg, „Verwerfen …“ da, Meldung", await tab.js(
        "[document.body.classList.contains('ds-nur-lesen'),!document.getElementById('verwerfenOeffnenKnopf').hidden&&"
        "getComputedStyle(document.getElementById('verwerfenOeffnenKnopf')).display!=='none',document.getElementById('aktionStatus').textContent]"),
        [False, True, "Zurückgeholt – die 6 Monate zählen ab heute neu."])


if __name__ == "__main__":
    ATTRAPPE.start()
    try:
        rc = klicktest_main(befuellen, pruefen, beschreibung=__doc__,
                            umgebung={"DK_ANFRAGE_URL": ATTRAPPE.adresse, "DK_ANFRAGE_SCHLUESSEL": ATTRAPPE.schluessel})
    finally:
        ATTRAPPE.stop()
    sys.exit(rc)

