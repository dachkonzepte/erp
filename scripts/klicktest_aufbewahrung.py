"""Klicktest: Seite „Aufbewahrung“, Kachel auf „Start“, Hinweis „im Archiv“ (1.10.12, Stufe W1c) -- nur Musterdaten.

Testdaten: Anna Admin, Bea Büro – Auftrag, Mona Monteurin. Erika Muster (vor 250 Tagen angelegt) mit einer Anfrage von damals, Otto Neu mit einem jungen
Projekt (nicht fällig), ein Altkunde aus dem Adressimport, ein unbearbeiteter Eingang der Webseite von vor 250 Tagen.

    Start         Kachel „Aufbewahrung“: Zahl der fälligen, „unbearbeiteter Eingang“, Weg zur Seite
    Büro–Auftrag  liest Fällig und Archiv, keine Knöpfe zum Archivieren, der Hinweis „Admin und Büro – Finanzen“
    Admin         „Archivieren“ an der Anfrage, „Kunde … archivieren“, „Alle fälligen archivieren“ (Rückfrage) -- danach „Nichts fällig“
    Archiv        Kunde, Anfrage, Eingang mit „im Archiv seit“; Kundenakte zeigt „Im Archiv seit …“, „Zurückholen“ holt ihn zurück; der Eingang sagt
                  „Im Archiv seit …“ ohne Aktion
    412 px        Fällig und Archiv hell und dunkel ohne Überlauf, Bilder
    Monteurin     Seite gesperrt
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_aufbewahrung.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "typeof vorschau!=='undefined'&&!!vorschau"
STATUS = "document.getElementById('aktionStatus').textContent"


def befuellen(db, k):
    from app.models import AppUser, Customer, CustomerProfile, Inquiry, Project, Property, WebAnfrage
    from app.project_pipeline_columns import default_pipeline_column_id

    alt = datetime.utcnow() - timedelta(days=250)
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    mona = AppUser(username="mona", display_name="Mona Monteurin", role="field", password_hash=k.passwort())
    db.add_all([anna, bea, mona])
    kunden = {}
    for name, extra in (("Erika Muster", {}), ("Otto Neu", {}), ("Altkunde Import", {"legacy_address_number": "4711"})):
        c = Customer(name=name, last_name=name.split()[-1], first_name=name.split()[0], city="Musterstadt", created_at=alt, **extra)
        db.add(c)
        db.flush()
        db.add(CustomerProfile(customer_id=c.id, customer_number=f"K-90{c.id}"))
        db.add(Property(customer_id=c.id, name="Hauptadresse", street="Musterweg 1", postal_code="12345", city="Musterstadt", is_primary_address=True))
        kunden[name] = c
    anfrage = Inquiry(inquiry_number="AN-2026-0901", customer_id=kunden["Erika Muster"].id, title="Undichtes Vordach", created_at=alt)
    projekt = Project(project_number="P-2026-0902", name="Neues Dach", customer_id=kunden["Otto Neu"].id, pipeline_column_id=default_pipeline_column_id(db))
    eingang = WebAnfrage(nummer="R-20260301-0900-0A1B", fassung="dk-anfrage/1", art="reparatur", art_name="Reparatur", umschlag="{}",
                         umschlag_sha256="0" * 64, status="neu", eingang_am=alt, abgeholt_am=alt, betreff="Musterweg 1 – Dachrinne")
    db.add_all([anfrage, projekt, eingang])
    db.commit()
    return {"anna": k.cookies(anna), "bea": k.cookies(bea), "mona": k.cookies(mona), "erika": kunden["Erika Muster"].id, "anfrage": anfrage.id,
            "eingang": eingang.id}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=(
        "window.alert=m=>console.error('alert(): '+m);window.__rueckfragen=[];window.confirm=m=>{window.__rueckfragen.push(m);return true};"))
    await tab.fenster(1440, 1000)

    # Büro – Auftrag: lesen, keine Knöpfe
    await tab.anmelden(seed["bea"])
    await tab.oeffnen("/aufbewahrung", "true")
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Büro – Auftrag: Seite geladen", await tab.oeffnen("/aufbewahrung?n=1", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Büro – Auftrag: zwei fällig (Eingang und Anfrage) und der Kunde", await tab.js("vorschau.zahl"), 3)
    p.pruefe("Büro – Auftrag: keine Knöpfe, Hinweis", await tab.js(
        "[document.querySelectorAll('[data-klick=\"archivieren\"]').length,!!document.getElementById('alleKnopf'),"
        "!!document.getElementById('nurLesen')]"), [0, False, True])
    inhalt = await tab.js("document.getElementById('inhalt').textContent")
    p.pruefe("Fällig: Eingang unbearbeitet, Anfrage mit Herkunft, Import und junges Projekt fehlen",
             ["unbearbeitet" in inhalt, "Anfrage AN-2026-0901 angelegt" in inhalt, "Altkunde" in inhalt, "P-2026-0902" in inhalt],
             [True, True, False, False])

    # Start: Kachel
    await tab.anmelden(seed["anna"])
    p.pruefe("Start geladen", await tab.oeffnen("/", "!!document.querySelector('[data-widget=\"aufbewahrung\"]')||document.body.textContent.includes('fällig fürs Archiv')"), True)
    await tab.warte_auf_ruhe()
    text = await tab.js("document.body.textContent")
    p.pruefe("Start: Kachel mit Zahl und unbearbeitetem Eingang", ["3 fällig fürs Archiv" in text, "1 unbearbeiteter Eingang" in text], [True, True])

    # Admin: einzeln, Kunde, gesammelt
    p.pruefe("Admin: Seite geladen", await tab.oeffnen("/aufbewahrung?n=2", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Admin: „Alle fälligen archivieren“ sichtbar", await tab.js("!document.getElementById('alleKnopf').hidden"), True)
    await tab.bild("aufbewahrung_faellig_1440_hell")
    await tab.warte_auf_neu_geladene_liste(f"document.querySelector('[data-klick=\"archivieren\"][data-art=\"anfrage\"][data-id=\"{seed['anfrage']}\"]').click()", "#inhalt")
    p.pruefe("Admin: Anfrage archiviert", await tab.js(STATUS), "1 ins Archiv gegeben.")
    knopf = await tab.js(f"(document.querySelector('[data-klick=\"archivieren\"][data-art=\"kunde\"][data-id=\"{seed['erika']}\"]')||{{}}).textContent")
    p.pruefe("Admin: Kunde geht mit (ohne Vorgang mehr)", knopf, "Kunde archivieren")
    await tab.warte_auf_neu_geladene_liste(f"document.querySelector('[data-klick=\"archivieren\"][data-art=\"kunde\"][data-id=\"{seed['erika']}\"]').click()", "#inhalt")
    p.pruefe("Admin: Kunde archiviert", await tab.js(STATUS), "1 ins Archiv gegeben.")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('alleKnopf').click()", "#inhalt")
    p.pruefe("Admin: gesammelt mit Rückfrage", [await tab.js("window.__rueckfragen.length"), await tab.js(STATUS)], [1, "1 ins Archiv gegeben."])
    p.pruefe("Admin: nichts mehr fällig", await tab.js("document.getElementById('inhalt').textContent.trim()"), "Nichts fällig fürs Archiv.")
    p.pruefe("Admin: ohne Fälliges keine Zahl am Reiter (sichtbar)", await tab.js(
        "getComputedStyle(document.getElementById('zahlFaellig')).display"), "none")
    p.pruefe("Eingang der Webseite: im Archiv nicht gezählt, ohne Zahl am Reiter", await tab.oeffnen(
        "/anfragen/webseite", "typeof stand!=='undefined'&&!!stand&&getComputedStyle(document.getElementById('zahlEingang')).display==='none'"), True)

    # Archiv
    p.pruefe("Archiv geladen", await tab.oeffnen("/aufbewahrung#archiv", "typeof archivDaten!=='undefined'&&!!archivDaten"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Archiv: Kunde, Anfrage, Eingang mit „Zurückholen“", await tab.js(
        "[...document.querySelectorAll('[data-klick=\"zurueckholen\"]')].map(b=>b.dataset.art).sort()"), ["anfrage", "eingang", "kunde"])
    await tab.bild("aufbewahrung_archiv_1440_hell")
    p.pruefe("Eingang im Archiv: Hinweis, keine Aktion", await tab.oeffnen(f"/anfragen/webseite/{seed['eingang']}",
             "document.getElementById('bearbeitungStand').textContent.startsWith('Im Archiv seit')"), True)
    p.pruefe("Eingang im Archiv: Verwerfen verborgen", await tab.js("document.getElementById('verwerfenOeffnenKnopf').hidden"), True)
    p.pruefe("Kundenakte im Archiv: Hinweis", await tab.oeffnen(f"/customers/{seed['erika']}", "!document.getElementById('archivHinweis').hidden"), True)
    await tab.warte_auf_ruhe()
    await tab.js("document.querySelector('[data-klick=\"kunde-zurueckholen\"]').click()")
    p.pruefe("Kundenakte: zurückgeholt, Hinweis weg", await tab.warten("document.getElementById('archivHinweis').hidden", 10), True)
    p.pruefe("Server: Kunde wieder in der Liste", await tab.js(
        f"fetch('/api/customers').then(r=>r.json()).then(l=>l.some(c=>c.id==={seed['erika']}))"), True)

    # 412 px hell und dunkel
    await tab.fenster(412, 1000, mobil=True)
    for thema, name in (("light", "hell"), ("dark", "dunkel")):
        await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
        for ansicht in ("faellig", "archiv"):
            p.pruefe(f"412 {name} {ansicht}: geladen", await tab.oeffnen(f"/aufbewahrung?n={name}{ansicht}#{ansicht}", BEREIT), True)
            await tab.warte_auf_ruhe()
            p.pruefe(f"412 {name} {ansicht}: ohne Überlauf", await tab.ueberlauf(), [])
            await tab.bild(f"aufbewahrung_{ansicht}_412_{name}")
    p.pruefe("keine JS-Fehler", tab.fehler, [])

    # Monteurin
    await tab.anmelden(seed["mona"])
    p.pruefe("Monteurin: Seite gesperrt", await tab.js("fetch('/aufbewahrung').then(r=>r.status)"), 403)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
