"""Klicktest: Reiter „Im Portal“ der Kundenakte und „vor dem Einladen“ in der Karte „Kundenportal“ (1.11.38, Stufe P2c; Bauplan P2, B9; Nachtrag 6).

    Vor dem Einladen    Portal aus: die Karte nennt, was der Kunde ab dann sieht (nur das von Hand Freigegebene); „Portal einschalten“ wendet die Regeln
                        an -- danach dazu die angekommene Rechnung; derselbe Satz im Dialog „Link senden“; „Im Portal ansehen“ öffnet den Reiter
    Reiter              Zahl am Reiter, „Der Kunde sieht: …“, Gruppen wie im Portal (Auftrag und Adresse), je Zeile Titel, Angaben, Kennzeichen; „Ruht“ mit
                        Grund (Projekt im Archiv); „Kopie gescheitert“ mit Grund und „Erneut versuchen“; „Zurückgenommen“ eingeklappt mit Zahl;
                        „Vorschläge“ (Angebot an eine andere Adresse) mit „Im Portal zeigen“
    Abläufe             Vorschlag freigeben (Dialog mit Titel, danach „Wird vorbereitet“, Vorschlag weg); Zurücknehmen mit Grund (Zeile wandert nach
                        „Zurückgenommen“); Erneut versuchen (danach „Wird vorbereitet“); im Archiv nur „Zurücknehmen“
    Sonst               dunkel, 412 px ohne Überlauf, Monteurin 403 an der Schnittstelle, keine JS-Fehler

Alles in der Wegwerf-SQLite dieses Laufs (Regel 16); kein Postbote -- „Wird vorbereitet“ bleibt so. Stehende Uhr 27.11.2026 10:00.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_kundenportal_im_portal.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln: siehe scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

EMAIL = "kunde@example.invalid"
GELADEN = "(()=>{const z=document.getElementById('portalZustand');return !!z&&z.textContent!=='Lädt …'&&document.getElementById('ipZahlen').textContent!==''})()"


def befuellen(db, k):
    import uuid
    from datetime import date, datetime

    from app.models import (
        AppUser, Customer, CustomerDocument, CustomerProfile, DocumentCategory, EmailDispatch, EnabledModule, Invoice, Order, PortalFreigabe, Project,
        ProjectDocument, Property, Quote, SentDocument,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from tests.quellangebot import quell_angebot

    auf = AppUser(username="auri", display_name="Auri Auftrag", role="buero_auftrag", password_hash=k.passwort())
    mon = AppUser(username="moni", display_name="Moni Monteurin", role="field", password_hash=k.passwort())
    db.add_all([auf, mon, EnabledModule(module_key="kundenportal", enabled=True)])
    kategorie = db.query(DocumentCategory).order_by(DocumentCategory.id).first()
    jetzt = datetime(2026, 11, 26, 9, 0)

    def kunde(nachname, nummer):
        c = Customer(name=f"Herr Max {nachname}", salutation="Herr", first_name="Max", last_name=nachname, email=EMAIL)
        db.add(c)
        db.flush()
        db.add(CustomerProfile(customer_id=c.id, customer_number=nummer))
        return c

    def projekt(c, *, archiviert=False):
        o = Property(customer_id=c.id, name="Halle", street="Hafenweg 3", postal_code="12345", city="Musterstadt")
        db.add(o)
        db.flush()
        p = Project(project_number=f"P-{o.id}", name="Interner Titel", customer_id=c.id, property_id=o.id, status="anfrage",
                    pipeline_column_id=default_pipeline_column_id(db), archived=archiviert)
        db.add(p)
        db.flush()
        return p

    def freigabe(c, quelle, qid, titel, *, bereit=True, fehler=None, zurueck=None):
        f = PortalFreigabe(customer_id=c.id, art="dokument", quelle=quelle, quelle_id=qid, titel=titel, datum=date(2026, 11, 20),
                           freigegeben_am=jetzt, freigegeben_von_user_id=auf.id, freigegeben_von_name="Auri Auftrag", kopie_fehler=fehler)
        if bereit:
            f.kopie_name, f.kopie_typ, f.kopie_groesse, f.kopie_bereit_am = uuid.uuid4().hex * 2 + ".pdf", "application/pdf", 1000, jetzt
        if zurueck:
            f.zurueckgenommen_am, f.zurueckgenommen_von_name, f.zurueckgenommen_grund = jetzt, "Auri Auftrag", zurueck
        db.add(f)
        db.flush()
        return f

    def dokument(c, titel):
        d = CustomerDocument(customer_id=c.id, category_id=kategorie.id, category=kategorie.label, original_filename=f"{titel}.pdf",
                             stored_filename=uuid.uuid4().hex, content_type="application/pdf", file_size=1000, document_date=date(2026, 11, 20))
        db.add(d)
        db.flush()
        return d

    def versand(art, dok_id, ablage, an):
        db.add(EmailDispatch(dispatch_key=uuid.uuid4().hex, message_ref=uuid.uuid4().hex, status="gesendet", channel="smtp", document_type=art,
                             document_id=dok_id, to_recipients=an, subject="Test", created_by_name="Auri Auftrag", sent_document_id=ablage,
                             created_at=jetzt, finished_at=jetzt))

    def ablage(art, dok_id):
        s = SentDocument(document_type=art, document_id=dok_id, filename="x.pdf", stored_filename=f"2026/11/{uuid.uuid4().hex}.pdf", size_bytes=10,
                         sha256="0" * 64, created_by_name="Auri Auftrag")
        db.add(s)
        db.flush()
        return s.id

    muster = kunde("Muster", "K-1001")
    p = projekt(muster)
    nr = "A-2026-0042"
    auftrag = Order(order_number=nr, project_id=p.id, source_quote_id=quell_angebot(db, p.id, nr), quote_number_snapshot="Q-42", title="Dach",
                    customer_name="x", customer_id=muster.id)
    db.add(auftrag)
    db.flush()
    rechnung = Invoice(order_id=auftrag.id, invoice_type="abschlag", customer_name="x", status="versendet", customer_id=muster.id,
                       invoice_number="R-2026-0101", invoice_date=date(2026, 11, 25))
    db.add(rechnung)
    db.flush()
    versand("rechnung", rechnung.id, None, EMAIL)  # angekommen: die Regel gibt sie beim Einschalten frei
    q = db.query(Quote).filter(Quote.project_id == p.id).first()
    versand("angebot", q.id, ablage("angebot", q.id), "architekt@example.invalid")  # an eine andere Adresse: Vorschlag
    freigabe(muster, "customer_documents", dokument(muster, "dachplan").id, "Dachplan Süd")  # sichtbar
    freigabe(muster, "customer_documents", dokument(muster, "kaputt").id, "Foto vom Schaden", bereit=False, fehler="abbruch")  # gescheitert
    freigabe(muster, "customer_documents", dokument(muster, "alt").id, "Alte Skizze", zurueck="falsches Dokument")  # zurückgenommen
    alt = projekt(muster)
    pd = ProjectDocument(project_id=alt.id, category_id=kategorie.id, category=kategorie.label, original_filename="x.pdf", stored_filename=uuid.uuid4().hex,
                         content_type="application/pdf", file_size=10, document_date=date(2026, 11, 20))
    db.add(pd)
    db.flush()
    freigabe(muster, "project_documents", pd.id, "Aufmaß Halle")
    alt.archived = True  # danach: die Freigabe ruht (Projekt im Archiv)

    archiv = kunde("Archiv", "K-1002")
    freigabe(archiv, "customer_documents", dokument(archiv, "plan").id, "Plan im Archiv")
    archiv.archiviert_am = jetzt  # erst anlegen, dann ins Archiv (Archivschutz)
    db.flush()
    import os
    return {"auf": k.cookies(auf), "mon": k.cookies(mon), "muster": muster.id, "archiv": archiv.id, "db_url": os.environ["DATABASE_URL"]}


async def _bild(tab, name, element="document.getElementById('reiter-importal')"):
    r = await tab.js(f"(()=>{{const b={element}.getBoundingClientRect();return [b.x,b.y+window.scrollY,b.width,b.height]}})()")
    daten = (await tab.cmd("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                           clip={"x": max(r[0] - 8, 0), "y": max(r[1] - 8, 0), "width": r[2] + 16, "height": r[3] + 16, "scale": 1}))["data"]
    tab.ablage(f"{name}.png").write_bytes(base64.b64decode(daten))


ZEILEN = "[...document.querySelectorAll('#ipListe .ip-zeile')].map(z=>[z.querySelector('.ip-titel').textContent,z.querySelector('.chip').textContent])"
GRUPPEN = "[...document.querySelectorAll('#ipListe .ip-gruppe')].map(g=>[g.firstChild.textContent,(g.querySelector('.ip-gruppe-unter')||{}).textContent||''])"
KNOEPFE = "(t=>[...document.querySelectorAll('#ipListe .ip-zeile')].filter(z=>z.querySelector('.ip-titel').textContent===t)[0].querySelectorAll('button'))"


async def _oeffnen(tab, p, seed, schluessel, anker="#uebersicht"):
    ok = await tab.oeffnen(f"/customers/{seed[schluessel]}{anker}", GELADEN)
    p.pruefe(f"{schluessel}: Kundenakte geladen", ok, True)
    await tab.warte_auf_ruhe()


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.anmelden(seed["auf"])
    await _oeffnen(tab, p, seed, "muster")
    await tab.js("localStorage.setItem('erp_theme','light')")  # nach dem ersten Laden (vorher läge der Wert bei einer anderen Seite)
    await _oeffnen(tab, p, seed, "muster", "?hell=1#uebersicht")
    sieht = "(()=>{const s=document.getElementById('portalSieht');return s.hidden?'':document.getElementById('portalSiehtText').textContent})()"
    p.pruefe("vor dem Einladen, Portal aus: nur das von Hand Freigegebene", await tab.js(sieht), "Ab dem Einladen sieht der Kunde: 1 Dokument.")
    p.pruefe("Einschalten", await tab.warte_auf_neu_geladene_liste("document.getElementById('portalEin').click()", "#ipListe"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("vor dem Einladen, Portal an: dazu die Rechnung (Regel)", await tab.js(sieht), "Ab dem Einladen sieht der Kunde: 1 Rechnung · 1 Dokument.")
    await tab.js("document.getElementById('portalZugangNeu').click()")
    await tab.js("document.getElementById('portalZugangEmail').value=" + repr(EMAIL))
    p.pruefe("Zugang angelegt", await tab.warte_auf_neu_geladene_liste("document.querySelector('[data-klick=\"portal-zugang-anlegen\"]').click()"), True)
    p.pruefe("Zugang angelegt: ohne Link", await tab.js("document.getElementById('portalZustand').textContent"), "Ohne Link")
    await tab.js("document.getElementById('portalLinkSenden').click()")
    p.pruefe("Dialog „Link senden“ nennt dasselbe", await tab.js("document.getElementById('portalLinkSieht').textContent"),
             "Ab dem Einladen sieht der Kunde: 1 Rechnung · 1 Dokument.")
    await tab.bild("dialog_link_mit_zahlen")
    await tab.js("document.querySelector('#portalLinkDialog [data-klick=\"dialog-zu\"]').click()")
    await tab.js("document.querySelector('#portalSieht a').click()")
    p.pruefe("„Im Portal ansehen“ öffnet den Reiter", await tab.warten("!document.getElementById('reiter-importal').hidden", 5), True)

    p.pruefe("Zahl am Reiter", await tab.js("document.getElementById('zahlImPortal').textContent"), "2")
    p.pruefe("Der Kunde sieht", await tab.js("document.getElementById('ipZahlen').textContent"), "Der Kunde sieht: 1 Rechnung · 1 Dokument.")
    p.pruefe("Gruppen wie im Portal", await tab.js(GRUPPEN), [["Auftrag A-2026-0042 · Dach", "Hafenweg 3, 12345 Musterstadt"],
                                                                ["Allgemeine Unterlagen", "ohne bestimmten Auftrag"]])
    p.pruefe("Zeilen mit Kennzeichen", sorted(await tab.js(ZEILEN)), sorted([["Rechnung R-2026-0101", "Wird vorbereitet"],
                                                                               ["Dachplan Süd", "Sichtbar"], ["Foto vom Schaden", "Kopie gescheitert"]]))
    p.pruefe("gescheitert: Grund in Worten", await tab.js(
        "[...document.querySelectorAll('#ipListe .ip-zeile')].find(z=>z.textContent.includes('Foto vom Schaden')).querySelector('.ip-angaben').textContent"
        ".endsWith('Bild ließ sich nicht umwandeln')"), True)
    p.pruefe("Ruht mit Grund", await tab.js("document.getElementById('ipRuht').textContent.includes('Projekt im Archiv')"), True)
    p.pruefe("Zurückgenommen eingeklappt mit Zahl", await tab.js("[document.getElementById('ipZurueckBlock').open,document.getElementById('ipZurueckZahl').textContent]"),
             [False, "1"])
    p.pruefe("Vorschlag: Angebot an eine andere Adresse", await tab.js("document.getElementById('ipVorschlaege').textContent.includes('an architekt@example.invalid')"), True)
    await _bild(tab, "reiter_im_portal")

    await tab.js("document.querySelector('#ipVorschlaege [data-klick=\"ip-vorschlag\"]').click()")
    p.pruefe("Vorschlag: Dialog mit Titel", await tab.js("[document.getElementById('imPortalDialog').open,document.getElementById('imPortalTitelFeld').value]"),
             [True, (await tab.js("document.querySelector('#ipVorschlaege .ip-titel').textContent"))])
    await tab.bild("dialog_im_portal_zeigen")
    await tab.js("document.getElementById('imPortalTitelFeld').value='';document.getElementById('imPortalKnopf').click()")
    p.pruefe("Vorschlag: ohne Titel nicht", await tab.js("[document.getElementById('imPortalStatus').textContent,document.getElementById('imPortalDialog').open]"),
             ["Bitte einen Titel angeben.", True])
    await tab.js("document.getElementById('imPortalTitelFeld').value='Angebot Dach'")
    p.pruefe("Vorschlag freigegeben", await tab.warte_auf_neu_geladene_liste("document.getElementById('imPortalKnopf').click()", "#ipListe"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Vorschlag: danach in der Liste", ["Angebot Dach", "Wird vorbereitet"] in await tab.js(ZEILEN), True)
    p.pruefe("Vorschlag: danach keine Vorschläge", await tab.js("document.getElementById('ipVorschlaegeBlock').hidden"), True)

    await tab.js(KNOEPFE + "('Dachplan Süd')[0].click()")
    await tab.js("document.getElementById('ipZurueckGrund').value='nicht mehr aktuell'")
    p.pruefe("Zurücknehmen", await tab.warte_auf_neu_geladene_liste("document.querySelector('[data-klick=\"ip-zuruecknehmen\"]').click()", "#ipListe"), True)
    p.pruefe("Zurücknehmen: aus der Liste", any(z[0] == "Dachplan Süd" for z in await tab.js(ZEILEN)), False)
    p.pruefe("Zurücknehmen: unter „Zurückgenommen“ mit Grund", await tab.js(
        "[document.getElementById('ipZurueckZahl').textContent,document.getElementById('ipZurueck').textContent.includes('nicht mehr aktuell')]"), ["2", True])

    p.pruefe("Erneut versuchen", await tab.warte_auf_neu_geladene_liste(KNOEPFE + "('Foto vom Schaden')[0].click()", "#ipListe"), True)
    p.pruefe("Erneut versuchen: wird vorbereitet", ["Foto vom Schaden", "Wird vorbereitet"] in await tab.js(ZEILEN), True)

    await tab.js("localStorage.setItem('erp_theme','dark')")
    await _oeffnen(tab, p, seed, "muster", "?dunkel=1#importal")  # eigene Abfrage: dieselbe Adresse mit # lüde nicht neu
    await _bild(tab, "reiter_im_portal_dunkel")
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.fenster(412, 900, mobil=True)
    await _oeffnen(tab, p, seed, "muster", "?schmal=1#importal")
    p.pruefe("412 px: Meldung von vorher weg (neu geladen)", await tab.js("document.getElementById('ipStatus').textContent"), "")
    p.pruefe("412 px: nichts ragt über die Gerätebreite", await tab.ueberlauf(), [])
    await _bild(tab, "reiter_im_portal_412")
    await tab.fenster(1440, 1000)

    await _oeffnen(tab, p, seed, "archiv", "#importal")
    p.pruefe("Archiv: Hinweis", await tab.js("document.getElementById('ipHinweis').textContent"),
             "Der Kunde ist im Archiv – er sieht nichts. Zurücknehmen geht weiter.")
    p.pruefe("Archiv: nur „Zurücknehmen“", await tab.js(
        "[...document.querySelectorAll('#reiter-importal button')].filter(b=>b.offsetParent!==null).map(b=>b.textContent)"), ["Zurücknehmen"])
    await tab.anmelden(seed["mon"])
    p.pruefe("Monteurin: Schnittstelle 403", await tab.js(f"fetch('/api/customers/{seed['muster']}/portal/freigaben').then(r=>r.status)"), 403)
    await tab.anmelden(seed["auf"])
    _sql(seed, "UPDATE enabled_modules SET enabled = 0 WHERE module_key = 'kundenportal'")
    vorher = sum(1 for e in tab.netz.verlauf if "/portal/freigaben" in str(e.get("url", "")))
    ok = await tab.oeffnen(f"/customers/{seed['muster']}#importal", "document.getElementById('stammdatenListe').children.length>0")
    p.pruefe("Modul aus: Kundenakte geladen", ok, True)
    await tab.warte_auf_ruhe()
    p.pruefe("Modul aus: kein Reiter, kein Abschnitt, kein Dialog", await tab.js(
        "[!!document.querySelector('[data-reiter=\"importal\"]'),!!document.getElementById('reiter-importal'),!!document.getElementById('imPortalDialog')]"),
        [False, False, False])
    p.pruefe("Modul aus: der Anker öffnet die Übersicht", await tab.js("!document.getElementById('reiter-uebersicht').hidden"), True)
    p.pruefe("Modul aus: keine Anfrage", sum(1 for e in tab.netz.verlauf if "/portal/freigaben" in str(e.get("url", ""))) - vorher, 0)
    p.pruefe("keine JS-Fehler", tab.fehler, [])


def _sql(seed, sql):
    import sqlite3
    pfad = seed["db_url"].removeprefix("sqlite:///")
    assert Path(pfad).parent.joinpath(".klicktest").exists(), pfad
    with sqlite3.connect(pfad) as c:
        return c.execute(sql).rowcount


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-27 10:00"))
