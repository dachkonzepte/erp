"""Klicktest: „Im Portal zeigen“ an den Dateien (1.11.39, Stufe P2c; Bauplan P2, B9; Nachtrag 6 des Betriebs).

    Kundenakte      Dokumente: PDF mit Knopf (Dialog mit Titel aus Kategorie und Datum, Hinweis zu PDFs), Bild mit Vorschau im Dialog, ZIP ohne Knopf;
                    nach dem Freigeben das Kennzeichen „Im Portal · wird vorbereitet“ an der Datei und die Zahl am Reiter „Im Portal“
    Akte            Dateien des Projekts: Knopf, Freigeben, Kennzeichen; Abnahme: der Beleg mit Knopf
    Objekt          Dateien des Objekts: Knopf, Freigeben, Kennzeichen
    Einsatzbericht  „Fotos im Portal zeigen …“ in der Zusammenfassung (nur Büro): Auswahl mit Vorschau (echte Testbilder, jede Vorschau lädt), nichts
                    vorgewählt, ohne Kreuz eine Meldung, die mit dem ersten Kreuz verschwindet (seit 1.11.40), zwei angekreuzt -> „2 im Portal zeigen“ -> zwei
                    Freigaben; danach sind beide als „schon im Portal“ nicht mehr ankreuzbar; die Monteurin sieht den Knopf nicht
    Objekt (1.11.40) die Datei eines Projekts eines anderen Kunden auf diesem Objekt hat keinen Knopf (Bauplan A2.2, U2/U3)
    Sonst           keine JS-Fehler

Alles in der Wegwerf-SQLite dieses Laufs (Regel 16); kein Postbote -- „wird vorbereitet“ bleibt so. Stehende Uhr 27.11.2026 10:00.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_kundenportal_an_dateien.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln: siehe scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    import os
    import uuid
    from datetime import date, datetime

    from app.models import (
        AppUser, Customer, CustomerDocument, CustomerProfile, DocumentCategory, Employee, EnabledModule, Order, OrderAcceptance, OrderAcceptanceFile,
        Project, ProjectDocument, Property, PropertyDocument, ServiceReport, ServiceReportPhoto,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from tests.quellangebot import quell_angebot

    monteurin = Employee(employee_number="E-1", first_name="Moni", last_name="Monteurin", employee_group="gewerblich", active=True)
    db.add(monteurin)
    db.flush()
    auf = AppUser(username="auri", display_name="Auri Auftrag", role="buero_auftrag", password_hash=k.passwort())
    mon = AppUser(username="moni", display_name="Moni Monteurin", role="field", password_hash=k.passwort(), employee_id=monteurin.id)
    db.add_all([auf, mon, EnabledModule(module_key="kundenportal", enabled=True)])
    kategorie = db.query(DocumentCategory).order_by(DocumentCategory.id).first()
    c = Customer(name="Herr Max Muster", salutation="Herr", first_name="Max", last_name="Muster", email="kunde@example.invalid", portal_aktiv=True)
    db.add(c)
    db.flush()
    db.add(CustomerProfile(customer_id=c.id, customer_number="K-1001"))
    o = Property(customer_id=c.id, name="Halle", street="Hafenweg 3", postal_code="12345", city="Musterstadt")
    db.add(o)
    db.flush()
    p = Project(project_number="P-2026-0042", name="Interner Titel", customer_id=c.id, property_id=o.id, status="anfrage",
                pipeline_column_id=default_pipeline_column_id(db))
    db.add(p)
    db.flush()
    nr = "A-2026-0042"
    a = Order(order_number=nr, project_id=p.id, source_quote_id=quell_angebot(db, p.id, nr), quote_number_snapshot="Q-42", title="Dach",
              customer_name="Herr Max Muster", customer_id=c.id)
    db.add(a)
    db.flush()

    def kundendok(name, typ):
        d = CustomerDocument(customer_id=c.id, category_id=kategorie.id, category=kategorie.label, original_filename=name, stored_filename=uuid.uuid4().hex,
                             content_type=typ, file_size=1000, document_date=date(2026, 11, 20))
        db.add(d)
        db.flush()
        return d.id

    dok = {"pdf": kundendok("dachplan.pdf", "application/pdf"), "bild": kundendok("schaden.jpg", "image/jpeg"),
           "zip": kundendok("archiv.zip", "application/zip")}
    import io

    from PIL import Image

    from app.customer_documents import document_path
    from app.service_report_photos import photo_path

    def jpeg(farbe):  # erfundene Testbilder -- die Vorschauen sollen wirklich laden (seit 1.11.40)
        aus = io.BytesIO()
        Image.new("RGB", (160, 120), farbe).save(aus, "JPEG")
        return aus.getvalue()

    bild = db.get(CustomerDocument, dok["bild"])
    pfad = document_path(bild)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(jpeg("orange"))
    pd = ProjectDocument(project_id=p.id, category_id=kategorie.id, category=kategorie.label, original_filename="aufmass.pdf", stored_filename=uuid.uuid4().hex,
                         content_type="application/pdf", file_size=10, document_date=date(2026, 11, 21))
    od = PropertyDocument(property_id=o.id, category_id=kategorie.id, original_filename="lageplan.pdf", stored_filename=uuid.uuid4().hex,
                          content_type="application/pdf", file_size=10)
    ab = OrderAcceptance(order_id=a.id, kind="foermlich", accepted_on=date(2026, 11, 22), scope="ganz", result="abgenommen", declared_by="auftraggeber",
                         declared_by_name="Max Muster", content_sha256="0" * 64, created_by_name="Auri Auftrag")
    db.add_all([pd, od, ab])
    db.flush()
    import hashlib

    from app.acceptances import _path_for
    inhalt = b"%PDF-1.4\n% erfundener Beleg\n%%EOF\n"
    echt = OrderAcceptanceFile(acceptance_id=ab.id, kind="beleg", stored_filename=f"{uuid.uuid4().hex}.pdf", content_type="application/pdf",
                               size_bytes=len(inhalt), sha256=hashlib.sha256(inhalt).hexdigest())
    ohne = OrderAcceptanceFile(acceptance_id=ab.id, kind="beleg", stored_filename=f"{uuid.uuid4().hex}.pdf", content_type="application/pdf", size_bytes=10,
                               sha256="0" * 64)  # die Datei fehlt
    db.add_all([echt, ohne])
    db.flush()
    pfad = _path_for(echt.stored_filename)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(inhalt)
    b = ServiceReport(order_id=a.id, report_type="wartung", status="unterschrieben", signed_at=datetime(2026, 11, 26, 9), created_by_employee_id=monteurin.id)
    db.add(b)
    db.flush()
    fotos = [ServiceReportPhoto(service_report_id=b.id, kind="allgemein", file_path=f"{uuid.uuid4().hex}.jpg") for _ in range(3)]
    db.add_all(fotos)
    db.flush()
    for foto, farbe in zip(fotos, ("red", "green", "blue")):
        pfad = photo_path(foto.file_path)
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_bytes(jpeg(farbe))
    # seit 1.11.40: ein Projekt eines anderen Kunden auf diesem Objekt (Bauplan A2.2, U2/U3) mit einer Datei
    andere = Customer(name="Frau Erika Beispiel", salutation="Frau", first_name="Erika", last_name="Beispiel", email="andere@example.invalid")
    db.add(andere)
    db.flush()
    fremdes = Project(project_number="P-2026-0043", name="Fremdes Projekt", customer_id=andere.id, property_id=o.id, status="anfrage",
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(fremdes)
    db.flush()
    fremd_dok = ProjectDocument(project_id=fremdes.id, category_id=kategorie.id, category=kategorie.label, original_filename="fremd.pdf",
                                stored_filename=uuid.uuid4().hex, content_type="application/pdf", file_size=10, document_date=date(2026, 11, 21))
    db.add(fremd_dok)
    db.flush()
    return {"auf": k.cookies(auf), "mon": k.cookies(mon), "kunde": c.id, "projekt": p.id, "auftrag": a.id, "objekt": o.id, "bericht": b.id, "dok": dok,
            "projektdok": pd.id, "objektdok": od.id, "fotos": [f.id for f in fotos], "db_url": os.environ["DATABASE_URL"], "beleg": echt.id,
            "beleg_ohne": ohne.id, "fremd_dok": fremd_dok.id}


def _abfrage(seed, sql, *werte):
    pfad = seed["db_url"].removeprefix("sqlite:///")
    assert Path(pfad).parent.joinpath(".klicktest").exists(), pfad
    with sqlite3.connect(pfad) as c:
        return c.execute(sql, werte).fetchall()


PLATZ = "(q,i)=>document.querySelector(`[data-ip-quelle=\"${q}\"][data-ip-id=\"${i}\"]`)"


async def _platz(tab, quelle, i):
    """(Kennzeichen, Knopf da?) am Platz der Datei."""
    return await tab.js(f"(()=>{{const p=({PLATZ})('{quelle}',{int(i)});if(!p)return null;const c=p.querySelector('.chip');"
                        f"return [c?c.textContent:'',!!p.querySelector('button')]}})()")


async def _freigeben(tab, p, name, quelle, i, *, titel=None):
    await tab.js(f"({PLATZ})('{quelle}',{int(i)}).querySelector('button').click()")
    p.pruefe(f"{name}: Dialog offen", await tab.js("document.getElementById('imPortalDialog').open"), True)
    if titel is not None:
        p.pruefe(f"{name}: Titel vorbelegt", await tab.js("document.getElementById('imPortalTitelFeld').value"), titel)
    ok = await tab.warte_auf_neu_geladene_liste("document.getElementById('imPortalKnopf').click()")
    p.pruefe(f"{name}: freigegeben", ok, True)
    await tab.warte_auf_ruhe()
    p.pruefe(f"{name}: Kennzeichen an der Datei", await _platz(tab, quelle, i), ["Im Portal · wird vorbereitet", False])


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.anmelden(seed["auf"])
    k = seed["kunde"]
    ok = await tab.oeffnen(f"/customers/{k}#dokumente", f"!!({PLATZ})('customer_documents',{seed['dok']['pdf']})?.querySelector('button')")
    p.pruefe("Kundenakte: Knopf an der PDF", ok, True)
    await tab.warte_auf_ruhe()
    p.pruefe("Kundenakte: ZIP ohne Knopf", await _platz(tab, "customer_documents", seed["dok"]["zip"]), ["", False])
    await tab.js(f"({PLATZ})('customer_documents',{seed['dok']['bild']}).querySelector('button').click()")
    p.pruefe("Bild: Vorschau, ohne Hinweis zu PDFs", await tab.js(
        "[document.querySelectorAll('#imPortalVorschau img').length,document.getElementById('imPortalPdf').hidden]"), [1, True])
    p.pruefe("Bild: die Vorschau lädt (echtes Testbild)", await tab.warten(
        "(()=>{const i=document.querySelector('#imPortalVorschau img');return !!i&&i.complete&&i.naturalWidth>0})()", 5), True)
    await tab.js("document.querySelector('[data-klick=\"im-portal-zu\"]').click()")
    await tab.js(f"({PLATZ})('customer_documents',{seed['dok']['pdf']}).querySelector('button').click()")
    p.pruefe("PDF: Hinweis zu PDFs", await tab.js("document.getElementById('imPortalPdf').hidden"), False)
    await tab.bild("dialog_pdf")
    await tab.js("document.querySelector('[data-klick=\"im-portal-zu\"]').click()")
    await _freigeben(tab, p, "Kundenakte PDF", "customer_documents", seed["dok"]["pdf"], titel=None)
    p.pruefe("Kundenakte: Zahl am Reiter", await tab.js("document.getElementById('zahlImPortal').textContent"), "1")
    p.pruefe("Kundenakte: Titel nie der Dateiname", _abfrage(seed, "SELECT titel FROM portal_freigaben WHERE quelle='customer_documents'")[0][0].endswith(
        "vom 20.11.2026"), True)
    await tab.bild("kundenakte_dokumente")

    ok = await tab.oeffnen(f"/projects/{seed['projekt']}?auftrag={seed['auftrag']}#dateien",
                           f"!!({PLATZ})('project_documents',{seed['projektdok']})?.querySelector('button')")
    p.pruefe("Akte: Knopf an der Datei", ok, True)
    await tab.warte_auf_ruhe()
    await _freigeben(tab, p, "Akte Datei", "project_documents", seed["projektdok"])
    ok = await tab.oeffnen(f"/projects/{seed['projekt']}?auftrag={seed['auftrag']}&a=1#abnahme",
                           f"!!({PLATZ})('order_acceptance_files',{seed['beleg']})?.querySelector('button')")
    p.pruefe("Akte: Knopf am Beleg der Abnahme", ok, True)
    await tab.warte_auf_ruhe()
    p.pruefe("Akte: am Beleg ohne Datei kein Platz und kein Knopf", await _platz(tab, "order_acceptance_files", seed["beleg_ohne"]), None)
    await tab.bild("akte_abnahme")

    ok = await tab.oeffnen(f"/properties/{seed['objekt']}", f"!!({PLATZ})('property_documents',{seed['objektdok']})?.querySelector('button')")
    p.pruefe("Objekt: Knopf an der Datei", ok, True)
    await tab.warte_auf_ruhe()
    p.pruefe("Objekt: die Datei des Projekts schon im Portal", await _platz(tab, "project_documents", seed["projektdok"]), ["Im Portal · wird vorbereitet", False])
    p.pruefe("Objekt: Datei eines Projekts eines anderen Kunden ohne Knopf", await _platz(tab, "project_documents", seed["fremd_dok"]), ["", False])
    await _freigeben(tab, p, "Objekt Datei", "property_documents", seed["objektdok"])

    ok = await tab.oeffnen(f"/service-reports/{seed['bericht']}#unterschrift", "!!document.querySelector('[data-klick=\"ip-fotos\"]')")
    p.pruefe("Bericht: „Fotos im Portal zeigen …“ fürs Büro", ok, True)
    await tab.warte_auf_ruhe()
    await tab.warte_auf_neu_geladene_liste("document.querySelector('[data-klick=\"ip-fotos\"]').click()")
    p.pruefe("Bericht: Auswahl mit drei Fotos, nichts vorgewählt", await tab.js(
        "[document.getElementById('imPortalDialog').open,document.querySelectorAll('#imPortalAuswahl input').length,"
        "document.querySelectorAll('#imPortalAuswahl input:checked').length]"), [True, 3, 0])
    p.pruefe("Bericht: jede Vorschau lädt (echte Testbilder)", await tab.warten(
        "[...document.querySelectorAll('#imPortalAuswahl img')].every(i=>i.complete&&i.naturalWidth>0)", 5), True)
    await tab.js("document.getElementById('imPortalKnopf').click()")
    p.pruefe("Bericht: ohne Kreuz eine Meldung", await tab.js("document.getElementById('imPortalStatus').textContent"), "Bitte mindestens ein Foto ankreuzen.")
    await tab.js("const b=[...document.querySelectorAll('#imPortalAuswahl input')];b[0].click();b[2].click()")
    p.pruefe("Bericht: die Meldung geht mit dem ersten Kreuz", await tab.js("document.getElementById('imPortalStatus').textContent"), "")
    p.pruefe("Bericht: Knopf nennt die Zahl", await tab.js("document.getElementById('imPortalKnopf').textContent"), "2 im Portal zeigen")
    await tab.bild("dialog_fotos")
    ok = await tab.warte_auf_neu_geladene_liste("document.getElementById('imPortalKnopf').click()")
    p.pruefe("Bericht: zwei Fotos freigegeben", (ok, _abfrage(seed, "SELECT count(*) FROM portal_freigaben WHERE quelle='service_report_photos'")[0][0]), (True, 2))
    await tab.warte_auf_neu_geladene_liste("document.querySelector('[data-klick=\"ip-fotos\"]').click()")
    p.pruefe("Bericht: danach nur noch eins ankreuzbar", await tab.js(
        "[...document.querySelectorAll('#imPortalAuswahl input')].map(i=>i.disabled)"), [True, False, True])
    p.pruefe("Bericht: „schon im Portal“", await tab.js(
        "document.querySelectorAll('#imPortalAuswahl .ip-wahl')[0].textContent.startsWith('schon im Portal')"), True)
    await tab.js("document.querySelector('[data-klick=\"im-portal-zu\"]').click()")
    p.pruefe("keine JS-Fehler (Büro)", tab.fehler, [])

    await tab.anmelden(seed["mon"])
    ok = await tab.oeffnen(f"/service-reports/{seed['bericht']}?monteurin=1#unterschrift", "!!document.querySelector('.bericht-karte')")
    p.pruefe("Monteurin: Bericht geladen", ok, True)  # eigene Abfrage: dieselbe Adresse mit # lüde nicht neu
    await tab.warte_auf_ruhe()
    p.pruefe("Monteurin: kein Knopf, kein Dialog", await tab.js(
        "[!!document.querySelector('[data-klick=\"ip-fotos\"]'),!!document.getElementById('imPortalDialog')]"), [False, False])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-27 10:00"))
