"""Klicktest: ein echter Tag auf „Heute“ (seit 1.9.53, Stufe 4, R2 Nachrunde 2) -- „Tag zusammen“ erklärt die Pause.

Befüllt: Auftrag „Wartung“ an Objekt „Halle Nord“; Ben: Baustelle heute ab 07:00, um 12:00 „Zeitart wechseln“ auf Werkstatt (über
dieselbe Funktion, die der Knopf aufruft -- app/time_tracking.py::zeitart_wechseln(), POST …/zeitart-wechseln); Pia: Baustelle seit gestern
07:00 offen, sonst keine Buchung. Stehende Uhr: 23.10.2026, 16:15 (Instanz und Browser) -- „Feierabend“ bucht genau 16:15.

    Ben (1280 × 620, hell)  vor dem Feierabend: „Werkstattzeit seit 12:00“, 4:15 h; „Feierabend“ -> Ergebnis „Feierabend gebucht: anwesend
                            4:15 h · Tag zusammen 9:15 h · Pause nach Zeitregel − 0:45 h · gebucht 3,50 h“; gebucht (API): Baustelle 5,00 h
                            ohne Pause, Werkstatt 4,25 h anwesend, 45 min, 3,50 h; der Tag 8,50 h gebucht
    Pia (1280 × 620, hell)  Zeit von gestern ohne frühere Buchung: 16:00 -> Vorschau „Anwesend 9:00 h · Pause nach Zeitregel − 0:30 h“ und
                            „Gebucht werden 8,50 h“ -- kein „Tag zusammen“ (der Tag hat keine andere Buchung; 9:00 h ist nicht „mehr als 9 h“)

Die Bilder (echter_tag_*.png) liegen im Ordner der Screenshots.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_echter_tag.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD]
        [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

def befuellen(db, k):
    from datetime import datetime, time, timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.models import AppUser, Customer, Employee, Order, OrderItem, Project, Property
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.time_tracking import start_timer, zeitart_wechseln

    heute = berlin_today()
    leute = {}
    for nr, (vor, nach) in enumerate([("Ben", "Baustelle"), ("Pia", "Gestern")], 1):
        leute[vor.lower()] = Employee(employee_number=f"E-{nr}", first_name=vor, last_name=nach, employee_group="gewerblich", active=True,
                                      hourly_wage=Decimal("22.00"))
    db.add_all(leute.values()); db.flush()
    benutzer = {n: AppUser(username=n, display_name=f"{e.first_name} {e.last_name}", role="field", employee_id=e.id, password_hash=k.passwort())
                for n, e in leute.items()}
    db.add_all(benutzer.values())
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    halle = Property(customer_id=kunde.id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Übach-Palenberg")
    db.add(halle); db.flush()
    projekt = Project(project_number="P-KT-T1", name="Wartung", customer_id=kunde.id, property_id=halle.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-2026-0001", project_id=projekt.id, source_quote_id=901, quote_number_snapshot="A-KT-1", title="Wartung",
                    customer_name=kunde.name, property_name=halle.name, property_address="Werkstr. 5\n52531 Übach-Palenberg")
    db.add(auftrag); db.flush()
    db.add(OrderItem(order_id=auftrag.id, sort_order=10, position_number="1", short_text="Wartung", quantity=Decimal("1"), unit="psch",
                     unit_price=Decimal("1")))
    db.commit()

    # Ben: Baustelle ab 07:00, um 12:00 „Zeitart wechseln“ auf Werkstatt
    baustelle = start_timer(db, employee_id=leute["ben"].id, order_id=auftrag.id, entry_type="site", started_at=datetime.combine(heute, time(7)))
    zeitart_wechseln(db, baustelle.id, "workshop", jetzt=datetime.combine(heute, time(12)))
    # Pia: Baustelle seit gestern 07:00 offen, keine andere Buchung
    start_timer(db, employee_id=leute["pia"].id, order_id=auftrag.id, entry_type="site",
                started_at=datetime.combine(heute - timedelta(days=1), time(7)))
    return {"heute": heute.isoformat(), "gestern": (heute - timedelta(days=1)).isoformat(), "ben": leute["ben"].id, "uhr_ms": k.uhr_ms(),
            "cookies": {n: k.cookies(u) for n, u in benutzer.items()}}


BEREIT = "document.getElementById('arbeitszeit').innerHTML!==''&&!document.getElementById('naechsteKarte').hidden"


async def _ansehen(tab, seed, wer):
    await tab.anmelden(seed["cookies"][wer])
    await tab.fenster(1280, 620)
    await tab.oeffnen("/mobil", BEREIT)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen("/mobil", BEREIT)


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.browser_uhr_fest(seed["uhr_ms"])

    # --- Ben: Werkstatt seit 12:00, Feierabend um 16:15 ---
    await _ansehen(tab, seed, "ben")
    p.pruefe("Ben: Werkstattzeit seit 12:00, 4:15 h", await tab.js(
        "[document.querySelector('#arbeitszeit .zeit-titel').textContent,document.getElementById('zeitDauer').textContent]"),
        ["Werkstattzeit seit 12:00", "4:15 h"])
    await tab.bild("echter_tag_vor_feierabend_hell")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('feierabendKnopf').click()", "#arbeitszeit")
    p.pruefe("Ben: Ergebnis nach dem Feierabend", await tab.js("document.getElementById('zeitErgebnis').textContent"),
             "Feierabend gebucht: anwesend 4:15 h · Tag zusammen 9:15 h · Pause nach Zeitregel − 0:45 h · gebucht 3,50 h")
    await tab.bild("echter_tag_nach_feierabend_hell")
    gebucht = await tab.js(f"fetch('/api/time-entries?employee_id={seed['ben']}&start_date={seed['heute']}&end_date={seed['heute']}')"
                           ".then(r=>r.json()).then(l=>l.sort((x,y)=>x.started_at<y.started_at?-1:1)"
                           ".map(e=>[e.entry_type,e.started_at.slice(11,16),e.ended_at.slice(11,16),Number(e.anwesend),e.pause,Number(e.hours)]))")
    p.pruefe("Ben: gebucht -- Baustelle 5,00 h, Werkstatt 4,25 h anwesend, 45 min, 3,50 h", gebucht,
             [["site", "07:00", "12:00", 5, 0, 5], ["workshop", "12:00", "16:15", 4.25, 45, 3.5]])
    p.pruefe("Ben: der Tag 8,50 h gebucht", round(sum(z[5] for z in gebucht or []), 2), 8.5)
    p.pruefe("Ben: keine JS-Fehler", tab.fehler, [])

    # --- Pia: Zeit von gestern ohne frühere Buchung -- kein „Tag zusammen“ ---
    await _ansehen(tab, seed, "pia")
    await tab.js("(f=>{f.value='16:00';f.dispatchEvent(new Event('input'))})(document.getElementById('endeZeit'))")
    await tab.warten("document.querySelector('#endeVorschau .gebucht')")
    p.pruefe("Pia: Vorschau ohne „Tag zusammen“", await tab.js("[...document.querySelectorAll('#endeVorschau span')].map(s=>s.textContent)"),
             ["Anwesend 9:00 h · Pause nach Zeitregel − 0:30 h", "Gebucht werden 8,50 h"])
    await tab.bild("echter_tag_ohne_fruehere_buchung_vorschau_hell")
    p.pruefe("Pia: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Echter Tag (1.9.53)", uhr="2026-10-23 16:15"))  # stehend: Feierabend um 16:15
