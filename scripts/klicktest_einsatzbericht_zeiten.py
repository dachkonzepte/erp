"""Klicktest: Zeiten im Einsatzbericht -- ein Bericht je Tag, mit der Unterschrift gespeichert (seit 1.9.42, Stufe 4, R1 Nachrunde).

Befüllt: Auftrag, Mia (Monteurin) und Tom; heute Mia 06:45–12:00 (Timer), Tom 3 h (Dauer), gestern Mia 2 h; Mias unterschriebener
Bericht von heute (unterschrieben im Befüllen) und ein Entwurf von heute; Anna (Admin).

    Anna (1400 px, hell)  Berichtsseite (seit 1.9.67 je Bericht, Schritt „Unterschrift“): am unterschriebenen Bericht „Zeiten am
                          <heute>“, „Stand der Unterschrift“, mit Mia 06:45–12:00
                          5,25 h und Tom – 3,00 h, ohne die Zeit von gestern; am Entwurf dieselben Zeilen „Stand jetzt“. PDF des
                          unterschriebenen Berichts dieselben Zeilen (pdf_vorher.pdf). Dann eine Zeit heute buchen (Tom 2,75 h über das
                          Formular der Seite) und Mias Zeit ändern (6,5 h): der unterschriebene Bericht und sein PDF (pdf_nachher.pdf)
                          unverändert, der Entwurf zeigt beides.
    Mia (412 px, dunkel)  ihr unterschriebener Bericht mit denselben Zeilen.

Feste Uhr 10:00. Die PDFs landen im Ordner der Screenshots.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_einsatzbericht_zeiten.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import base64
import re
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def _pdf_text(pdf: bytes) -> str:
    """Der Text der Inhaltsströme (ASCII85 + Flate, wie reportlab sie schreibt) -- wie tests/test_v213::_extract_pdf_text()."""
    teile = []
    for treffer in re.finditer(rb">>\s*stream\s*(.*?)\s*endstream", pdf, re.DOTALL):
        daten = treffer.group(1)
        if daten.endswith(b"~>"):
            daten = daten[:-2]
        try:
            teile.append(zlib.decompress(base64.a85decode(daten, adobe=False)))
        except Exception:
            continue
    return b"".join(teile).decode("latin-1")


def befuellen(db, k):
    from datetime import datetime, time, timedelta
    from decimal import Decimal
    from io import BytesIO

    from PIL import Image

    from app.berlin_time import berlin_today
    from app.models import AppUser, Customer, Employee, Project, Quote, QuoteItem, WorkPreparationEmployee
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.service_reports import create_report, sign_report
    from app.time_tracking import create_manual_entry, start_timer, stop_timer
    from app.work_preparation import ensure_preparation

    heute = berlin_today()
    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True,
                   hourly_wage=Decimal("22.00"))
    tom = Employee(employee_number="E-2", first_name="Tom", last_name="Monteur", employee_group="gewerblich", active=True,
                   hourly_wage=Decimal("22.00"))
    db.add_all([mia, tom]); db.flush()
    benutzer = {"mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id, password_hash=k.passwort()),
                "anna": AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())}
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    projekt = Project(project_number="P-KT-EZ", name="Dachsanierung Halle", customer_id=kunde.id, status="angebot",
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(quote_number="A-KT-EZ", project_id=projekt.id, title="Dachsanierung Halle", vat_rate=Decimal("19"))
    db.add(angebot); db.flush()
    db.add(QuoteItem(quote_id=angebot.id, position_number="1", short_text="Abdichtung", quantity=Decimal("850"), unit="m²",
                     unit_price=Decimal("48.90")))
    db.commit()
    auftrag = create_order_from_quote(db, angebot.id, order_date=heute - timedelta(days=30), execution_start=None, execution_end=None,
                                      caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    prep = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=mia.id))
    db.commit()
    zeit = start_timer(db, employee_id=mia.id, order_id=auftrag.id, started_at=datetime.combine(heute, time(6, 45)), activity="Abdichtung")
    stop_timer(db, zeit.id, ended_at=datetime.combine(heute, time(12)))
    create_manual_entry(db, employee_id=tom.id, order_id=auftrag.id, work_date=heute, hours=Decimal("3"), activity="Rinne")
    create_manual_entry(db, employee_id=mia.id, order_id=auftrag.id, work_date=heute - timedelta(days=1), hours=Decimal("2"),
                        activity="Vortag")
    puffer = BytesIO()
    bild = Image.new("RGB", (40, 20), "white")
    bild.putpixel((5, 5), (0, 0, 0))
    bild.save(puffer, format="PNG")
    unterschrieben = create_report(db, auftrag.id, "rapport", performed_at=heute, description="Abdichtung am Anschluss erneuert",
                                   created_by_employee_id=mia.id)
    sign_report(db, unterschrieben["id"], installer_signature_png_bytes=puffer.getvalue(), installer_signature_name="Mia Monteurin",
                customer_signature_png_bytes=puffer.getvalue(), customer_signature_name="Bernd Bauherr")
    entwurf = create_report(db, auftrag.id, "rapport", performed_at=heute, description="Nacharbeit", created_by_employee_id=mia.id)
    return {"auftrag": auftrag.id, "unterschrieben": unterschrieben["id"], "entwurf": entwurf["id"], "mia_zeit": zeit.id, "tom": tom.id,
            "heute": heute.isoformat(), "heute_de": f"{heute:%d.%m.%Y}", "cookies": {n: k.cookies(u) for n, u in benutzer.items()}}


# seit 1.9.67 je Bericht die Berichtsseite, Schritt „Unterschrift“ (bis 1.9.66 alle Berichte auf der Seite des Auftrags)
BEREIT = "typeof ZEITEN!=='undefined'&&ZEITEN&&!!document.getElementById('berichtZeiten')"


def _zeilen() -> str:
    """[Titel, [[Tag, Person · von–bis, Stunden], …]] der Zeiten auf der Berichtsseite."""
    return ("(k=>k?[k.querySelector('.eb').textContent,[...k.querySelectorAll('.zl')].map(z=>[...z.children].map(c=>c.textContent))]:null)"
            "(document.getElementById('berichtZeiten'))")


async def _pdf(tab, bericht: int, name: str) -> str:
    daten = await tab.js(f"fetch('/api/service-reports/{bericht}/pdf').then(r=>r.arrayBuffer()).then(b=>{{let s='';"
                         "new Uint8Array(b).forEach(x=>s+=String.fromCharCode(x));return btoa(s)})")
    pdf = base64.b64decode(daten or "")
    (tab.shots / name).write_bytes(pdf)
    return _pdf_text(pdf)


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    h, s, e = seed["heute_de"], seed["unterschrieben"], seed["entwurf"]
    zeilen = [[h, "Mia Monteurin · 06:45–12:00", "5,25 h"], [h, "Tom Monteur", "3,00 h"]]  # seit 1.9.67: Person · von–bis

    await tab.anmelden(seed["cookies"]["anna"])
    await tab.fenster(1400, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen(f"/service-reports/{s}#unterschrift", BEREIT)
    p.pruefe("Unterschriebener Bericht: Zeiten am Tag, Stand der Unterschrift, ohne Vortag", [await tab.js(_zeilen()), await tab.js(
        "document.getElementById('berichtZeiten').textContent.includes('Stand der Unterschrift.')")], [[f"Zeiten am {h}", zeilen], True])
    await tab.bild("10_bericht_unterschrieben_vorher_hell")
    await tab.oeffnen(f"/service-reports/{e}#unterschrift", BEREIT)
    p.pruefe("Entwurf: dieselben Zeilen, Stand jetzt", [await tab.js(_zeilen()), await tab.js(
        "document.getElementById('berichtZeiten').textContent.includes('mit der Unterschrift wird dieser Stand gespeichert')")],
        [[f"Zeiten am {h}", zeilen], True])
    vorher = await _pdf(tab, s, "pdf_vorher.pdf")
    # seit 1.9.46 (R2 Punkt 7): die Unterschrift auf der Seite in Europe/Berlin -- dieselbe Zeit wie im PDF (bis dahin UTC); seit 1.9.67
    # in der Zeile des Berichts auf der Seite des Auftrags
    await tab.oeffnen(f"/orders/{seed['auftrag']}/service-reports", "typeof reports!=='undefined'&&reports.length===2")
    zeit = await tab.js(rf"((t)=>(t.match(/Kunde: Bernd Bauherr \((\d\d\.\d\d\.\d{{4}} \d\d:\d\d) Uhr\)/)||[])[1]||null)"
                        f"(document.getElementById('bericht-{s}').innerText)")
    p.pruefe("Unterschrift auf der Seite = Zeit im PDF", [bool(zeit), f"am {zeit} Uhr" in vorher], [True, True])
    p.pruefe("PDF vorher: dieselben Zeilen (Personen, von–bis, Stunden), nicht der Vortag",
             [f"Zeiten am {h}" in vorher, "Mia Monteurin" in vorher, "Tom Monteur" in vorher, "06:45" in vorher, "12:00" in vorher,
              "5,25" in vorher, "3,00" in vorher, "2,00" in vorher, "Vortag" in vorher], [True] * 7 + [False, False])

    # nachträglich: eine Zeit heute buchen (Formular der Seite des Auftrags) und Mias Zeit ändern (Schnittstelle)
    await tab.js(f"document.getElementById('teEmployee').value='{seed['tom']}';document.getElementById('teDate').value='{seed['heute']}';"
                 "document.getElementById('teHours').value='2,75'")
    await tab.warte_auf_neu_geladene_liste("saveReportTimeEntry()", "#timeEntriesTable")
    p.pruefe("Zeit gebucht", await tab.js("document.getElementById('teStatus').textContent"), "Gebucht.")
    status = await tab.js(f"fetch('/api/time-entries/{seed['mia_zeit']}',{{method:'PUT',headers:{{'Content-Type':'application/json'}},"
                          "body:JSON.stringify({hours:'6.5'})}).then(r=>r.status)")
    p.pruefe("Mias Zeit geändert (6,5 h)", status, 200)
    await tab.oeffnen(f"/service-reports/{s}#unterschrift", BEREIT)
    p.pruefe("Unterschriebener Bericht nachher: unverändert", await tab.js(_zeilen()), [f"Zeiten am {h}", zeilen])
    await tab.bild("11_bericht_unterschrieben_nachher_hell")
    await tab.oeffnen(f"/service-reports/{e}#unterschrift", BEREIT)
    # seit 1.9.90 (Stufe 4, R5a, Punkt 3): Mias Von/Bis-Buchung als Dauer gespeichert -- ohne Uhrzeiten (bis 1.9.89 blieb „06:45–12:00“
    # neben den 6,50 h stehen)
    p.pruefe("Entwurf nachher: neue und geänderte Zeit (die Dauer ohne Uhrzeiten)", (await tab.js(_zeilen()) or [None, []])[1],
             [[h, "Mia Monteurin", "6,50 h"], [h, "Tom Monteur", "3,00 h"], [h, "Tom Monteur", "2,75 h"]])
    nachher = await _pdf(tab, s, "pdf_nachher.pdf")
    p.pruefe("PDF nachher: dieselben Zeilen wie vorher, nichts Neues", ["5,25" in nachher, "3,00" in nachher, "6,50" in nachher,
             "2,75" in nachher], [True, True, False, False])
    p.pruefe("Anna: keine JS-Fehler", tab.fehler, [])

    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/service-reports/{s}#unterschrift", BEREIT)
    p.pruefe("Mia: ihr unterschriebener Bericht mit denselben Zeilen", await tab.js(_zeilen()), [f"Zeiten am {h}", zeilen])
    await tab.js("document.getElementById('berichtZeiten').scrollIntoView({block:'start'})")
    await tab.bild("12_bericht_unterschrieben_monteurin_dunkel_412")
    p.pruefe("Mia: keine JS-Fehler", tab.fehler, [])

if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Zeiten im Einsatzbericht (1.9.42)", uhr="10:00"))
