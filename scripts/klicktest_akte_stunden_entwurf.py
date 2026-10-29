"""Klicktest: Stunden mit zwei Stellen, „Entwurf öffnen“, Daten mit Jahr in der Akte (1.9.132, Stufe 5, R2 Nachrunde, Punkte 3–5).

    Stunden      Auftrag mit 8 h + 2,75 h (Position 1, Soll 12 h): Übersicht „Stunden“, Phase „Ausführung“, Leistungen (Std. Ist/Soll),
                 Ausführung (Stand der Zeiten) zeigen 10,75 h -- und „Zeiten“ über den Link der Akte dieselbe Summe
    Entwurf      mit einem Abschlag im Entwurf: „Nächste Rechnung“ nennt ihn, „Entwurf öffnen“ führt auf seine Rechnungsseite, kein „Entwurf
                 anlegen“ (Bild); Auftrag ohne Entwurf: „Entwurf anlegen“ wie bisher
    Daten        Auftragsdaten (Reiter Vertrag) mit Jahr: Auftragsdatum, Ausführung von – bis

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_akte_stunden_entwurf.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.invoices import create_abschlag_leistungsstand
    from app.models import AppUser, Customer, Employee, Order, OrderItem, OrderItemCalculationSnapshot, Project
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.time_tracking import create_manual_entry

    heute = berlin_today()
    fiona = AppUser(username="fiona", display_name="Fiona Finanzen", role="buero_finanzen", password_hash=k.passwort())
    mia = Employee(employee_number="E-552", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
    kunde = Customer(name="Bauherr Stunden", last_name="Stunden", city="Uebach")
    db.add_all([fiona, mia, kunde]); db.flush()

    def auftrag(nummer, beginn, ende):
        p = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
        db.add(p); db.flush()
        o = Order(order_number=f"AUF-{nummer}", project_id=p.id, source_quote_id=int(nummer.split("-")[1]), quote_number_snapshot=f"A-{nummer}", title="Sanierung",
                  customer_name=kunde.name, vat_rate=Decimal("19"), order_date=beginn - timedelta(days=11), execution_start=beginn,
                  execution_end=ende)
        db.add(o); db.flush()
        pos = OrderItem(order_id=o.id, sort_order=10, position_number="1", short_text="Eindecken", quantity=Decimal("12"), unit="m²",
                        unit_price=Decimal("50"))
        db.add(pos); db.flush()
        db.add(OrderItemCalculationSnapshot(order_item_id=pos.id, site_time_minutes=Decimal("60"), workshop_time_minutes=Decimal("0")))
        db.commit()
        return p, db.get(Order, o.id), pos

    beginn = heute - timedelta(days=5)
    p1, o1, pos1 = auftrag("552-1", beginn, beginn + timedelta(days=11))
    for tag, stunden in ((beginn, "8"), (beginn + timedelta(days=1), "2.75")):
        create_manual_entry(db, employee_id=mia.id, order_id=o1.id, order_item_id=pos1.id, work_date=tag, hours=Decimal(stunden), entry_type="site")
    entwurf = create_abschlag_leistungsstand(db, db.get(Order, o1.id))
    p2, o2, _ = auftrag("552-2", beginn, beginn + timedelta(days=3))
    return {"mit_entwurf": p1.id, "order": o1.id, "entwurf": entwurf.id, "ohne_entwurf": p2.id, "cookies": {"fiona": k.cookies(fiona)},
            "auftragsdatum": (beginn - timedelta(days=11)).strftime("%d.%m.%Y"),
            "ausfuehrung": f"{beginn.strftime('%d.%m.%Y')} – {(beginn + timedelta(days=11)).strftime('%d.%m.%Y')}"}


AKTE = ("typeof order!=='undefined'&&order&&order.id&&zahlenDaten&&invoices&&document.getElementById('seitenkopfStatus').textContent.length>0"
        "&&document.getElementById('zeitenStand').textContent.includes('h')")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1440, 900)
    await tab.anmelden(seed["cookies"]["fiona"])

    await tab.oeffnen(f"/projects/{seed['mit_entwurf']}", AKTE)
    p.pruefe("Übersicht „Stunden“: Soll, gebucht, Baustelle & Werkstatt mit zwei Stellen", await tab.js(
        "['uSoll','uGebucht','uBw'].map(i=>document.getElementById(i).textContent)"), ["12,00 h", "10,75 h", "10,75 h"])
    p.pruefe("Phase „Ausführung“: 10,75 h gebucht", await tab.js(
        "[...document.querySelectorAll('#phasen li')].find(li=>li.querySelector('.phase-name').textContent.startsWith('Ausführung'))"
        ".querySelector(':scope > .mut').textContent.endsWith('10,75 h gebucht')"), True)
    p.pruefe("Nächste Rechnung: Entwurf genannt, „Entwurf öffnen“ statt „Entwurf anlegen“", await tab.js(
        "[document.getElementById('uNaechste').hidden,document.getElementById('uNaechsteKnopf').hidden,"
        "document.getElementById('uNaechsteLink').hidden,document.getElementById('uNaechsteLink').textContent,"
        "document.getElementById('uNaechsteLink').getAttribute('href'),"
        "document.getElementById('uNaechsteText').textContent.includes('1. Abschlag nach Leistungsstand liegt als Entwurf vor')]"),
        [False, True, False, "Entwurf öffnen", f"/invoices/{seed['entwurf']}", True])
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.bild("uebersicht_mit_entwurf")

    await tab.js("reiterZeigen('leistungen')")
    p.pruefe("Leistungen: Std. Ist/Soll der Position mit zwei Stellen", await tab.js(
        "[...document.querySelectorAll('#lv tr.lv-row')].some(r=>r.textContent.includes('10,75 / 12,00 h'))"), True)
    await tab.js("reiterZeigen('ausfuehrung')")
    p.pruefe("Ausführung: Stand der Zeiten (gebucht, Fahrzeit, Baustelle & Werkstatt)", await tab.js(
        "[...document.querySelectorAll('#zeitenStand .gross')].map(x=>x.textContent)"), ["10,75 h", "0,00 h", "10,75 h"])
    await tab.js("reiterZeigen('vertrag')")
    p.pruefe("Auftragsdaten mit Jahr: Auftragsdatum, Ausführung", await tab.js(
        "(()=>{const dt=[...document.querySelectorAll('#auftragsdatenListe dt')];const w=k=>dt.find(d=>d.textContent===k).nextElementSibling.textContent;"
        "return [w('Auftragsdatum'),w('Ausführung')]})()"), [seed["auftragsdatum"], seed["ausfuehrung"]])
    p.pruefe("JS-Fehler (Akte)", tab.fehler, [])

    await tab.js("document.getElementById('zeitenLink').click()")
    await tab.warten("location.pathname==='/zeiten'&&!!window.B&&B.zeitraum==='alle'&&document.querySelectorAll('#buchungenZeilen tr').length>0", 60)
    p.pruefe("„Zeiten“ über den Link der Akte: dieselbe Summe", await tab.js("document.getElementById('summeAuswahl').textContent"), "10,75 h")

    await tab.oeffnen(f"/projects/{seed['mit_entwurf']}", AKTE)
    await tab.js("document.getElementById('uNaechsteLink').click()")
    p.pruefe("„Entwurf öffnen“ führt auf die Rechnungsseite des Entwurfs",
             await tab.warten(f"location.pathname==='/invoices/{seed['entwurf']}'", 30), True)

    await tab.oeffnen(f"/projects/{seed['ohne_entwurf']}", AKTE)
    p.pruefe("Ohne Entwurf: „Entwurf anlegen“, kein „Entwurf öffnen“", await tab.js(
        "[document.getElementById('uNaechste').hidden,document.getElementById('uNaechsteKnopf').hidden,document.getElementById('uNaechsteKnopf').textContent,"
        "document.getElementById('uNaechsteLink').hidden]"), [False, False, "Entwurf anlegen", True])
    p.pruefe("JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
