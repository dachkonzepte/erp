"""Klicktest: „Heute“ der Monteurin mit der Besetzung je Tag (seit 1.9.262, Stufe 6, R5a, Punkt 3).

Testdaten wie die Zeichnung entwurf-stufe6/plantafel-auftraege-regeln.html (Fundament, KW 46): Kolonne Nord (Tom KF, Mia, Ole). „Am Wasserturm 4“
Mo 09.–Fr 13.11. mit Nord: Tom, Mia und Ole Mo, Di, Do, Fr, Kai nur Do und Fr -- am Mittwoch niemand. „Ortgang Lindenweg 9“ Mi 11.11. ohne Kolonne: Tom und
Mia. „Sturmschaden Gartenstraße 2“ Di–Mi ohne Kolonne: Lia an beiden Tagen, Ole nur am Mi. „Dachfenster Krüger“ Mo 16.–Mi 18.11. ohne Kolonne: Lia an allen
Tagen, Kai nur am Di 17.11. Stehende Uhr Mi 11.11.2026 10:00 in Instanz und Browser.

    Kai (an diesem Tag ohne Einsatz)   „Heute ist nichts eingeplant.“, keine Vorwahl der Zeit; Nächste Tage „Do 12.11.–Fr 13.11. Am Wasserturm 4 · mit Tom,
                                       Mia, Ole“ und nur „Di 17.11. Dachfenster Krüger · mit Lia“; quer (1280 × 620) und hoch (800 × 1100), hell und dunkel
                                       (Bilder bis zum Seitenende)
    Mia                                eine Karte „Ortgang Lindenweg 9“ (nicht der Wasserturm), „Heutiger Einsatz · 11.11.“, „Mit dir“ Tom; Nächste Tage
                                       Wasserturm Do–Fr „mit Tom, Ole, Kai“ (kein „weiter“: heute steht sie dort nicht)
    Ole                                Karte „Sturmschaden“ mit Lia; Nächste Tage Wasserturm Do–Fr „mit Tom, Mia, Kai“
    Lia                                Nächste Tage Dachfenster: „mit Kai“ nur am Di 17.11., Mo und Mi ohne ihn
    überall                            keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_heute_tage.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "document.getElementById('arbeitszeit').innerHTML!==''&&!document.getElementById('naechsteKarte').hidden"
KARTEN = ("[...document.querySelectorAll('[data-einsatz]')].map(k=>[k.querySelector('.eb').textContent,k.querySelector('h2').textContent,"
          "(k.querySelector('[data-angabe=mit] .text')||{}).textContent||null])")
NAECHSTE = "[...document.querySelectorAll('#naechsteZeilen .zeile')].map(z=>z.textContent)"
VORWAHL = "fetch('/api/field-view/today').then(r=>r.json()).then(d=>d.heute.arbeitszeit.vorbelegt)"


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.models import AppUser, Customer, Employee, Order, OrderItem, Project, Property, Team, TeamEmployee
    from app.planning import create_slot
    from app.project_pipeline_columns import default_pipeline_column_id

    leute = {}
    for nr, (vor, nach) in enumerate([("Tom", "Monteur"), ("Mia", "Monteurin"), ("Ole", "Offen"), ("Kai", "Kolb"), ("Lia", "Lang")], 1):
        leute[vor] = Employee(employee_number=f"E-{nr}", first_name=vor, last_name=nach, employee_group="gewerblich", active=True,
                              hourly_wage=Decimal("22.00"))
    db.add_all(leute.values()); db.flush()
    benutzer = {n.lower(): AppUser(username=n.lower(), display_name=f"{e.first_name} {e.last_name}", role="field", employee_id=e.id,
                                   password_hash=k.passwort()) for n, e in leute.items()}
    db.add_all(benutzer.values())
    nord = Team(name="Kolonne Nord", active=True)
    db.add(nord); db.flush()
    db.add_all([TeamEmployee(team_id=nord.id, employee_id=leute["Tom"].id, is_crew_leader=True), TeamEmployee(team_id=nord.id, employee_id=leute["Mia"].id),
                TeamEmployee(team_id=nord.id, employee_id=leute["Ole"].id)])
    db.commit()

    def auftrag(nr, objekt, kunde_name):
        kunde = Customer(name=kunde_name, last_name=kunde_name, is_consumer=False)
        db.add(kunde); db.flush()
        prop = Property(customer_id=kunde.id, name=objekt, street=objekt, postal_code="52531", city="Übach-Palenberg")
        db.add(prop); db.flush()
        projekt = Project(project_number=f"P-2026-01{nr}", name=objekt, customer_id=kunde.id, property_id=prop.id, pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        o = Order(order_number=f"AUF-2026-01{nr}", project_id=projekt.id, source_quote_id=900 + nr, quote_number_snapshot=f"A-KT-{nr}", title=objekt,
                  customer_name=kunde.name, property_name=objekt, property_address=f"{objekt}\n52531 Übach-Palenberg")
        db.add(o); db.flush()
        db.add(OrderItem(order_id=o.id, sort_order=10, position_number="1", short_text="Arbeit", quantity=Decimal("1"), unit="psch", unit_price=Decimal("1")))
        db.commit()
        return o

    wasserturm = auftrag(18, "Am Wasserturm 4", "Wohnbau Kessler GmbH")
    ortgang = auftrag(44, "Ortgang Lindenweg 9", "Familie Becker")
    sturm = auftrag(51, "Sturmschaden Gartenstraße 2", "Notdienst")
    dachfenster = auftrag(40, "Dachfenster Krüger", "Familie Krüger")
    d = lambda n: date(2026, 11, 9 + n)  # noqa: E731 -- Mo 09.11. + n
    ohne_mi = [d(0), d(1), d(3), d(4)]
    create_slot(db, order_id=wasserturm.id, team_id=nord.id, start_date=d(0), end_date=d(4), status="fest", planned_hours=Decimal("46"), trotzdem_planen=True,
                besetzung=[{"employee_id": leute[n].id, "tage": ohne_mi} for n in ("Tom", "Mia", "Ole")]
                + [{"employee_id": leute["Kai"].id, "tage": [d(3), d(4)]}], geraete=[])
    create_slot(db, order_id=ortgang.id, team_id=None, start_date=d(2), end_date=d(2), status="fest", planned_hours=Decimal("8"), trotzdem_planen=True,
                employee_ids=[leute["Tom"].id, leute["Mia"].id])
    create_slot(db, order_id=sturm.id, team_id=None, start_date=d(1), end_date=d(2), status="fest", planned_hours=Decimal("8"), trotzdem_planen=True,
                besetzung=[{"employee_id": leute["Lia"].id, "tage": None}, {"employee_id": leute["Ole"].id, "tage": [d(2)]}])
    # nächste Woche: Kai nur am Di -- „Nächste Tage“ nennt nur seinen Tag, nicht den ganzen Einsatz
    create_slot(db, order_id=dachfenster.id, team_id=None, start_date=d(7), end_date=d(9), status="fest", planned_hours=Decimal("16"), trotzdem_planen=True,
                besetzung=[{"employee_id": leute["Lia"].id, "tage": None}, {"employee_id": leute["Kai"].id, "tage": [d(8)]}])
    return {"cookies": {n: k.cookies(u) for n, u in benutzer.items()}, "uhr_ms": k.uhr_ms()}


async def _ansehen(tab, seed, wer, breite, hoehe, thema):
    """Als wer anmelden, Fenster setzen, /mobil öffnen, Thema setzen (erst auf der Seite des ERP möglich) und neu laden."""
    await tab.anmelden(seed["cookies"][wer])
    await tab.fenster(breite, hoehe)
    await tab.oeffnen("/mobil", BEREIT)
    await tab.js(f"localStorage.setItem('erp_theme','{thema}')")
    await tab.oeffnen("/mobil", BEREIT)
    await tab.warte_auf_ruhe()


async def _ganze_seite(tab, name, breite, hoehe):
    voll = await tab.js("Math.ceil(document.documentElement.scrollHeight)")
    await tab.fenster(breite, max(hoehe, voll))
    await tab.bild(name)
    await tab.fenster(breite, hoehe)


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.browser_uhr_fest(seed["uhr_ms"])

    # --- Kai: heute (Mi) ohne Einsatz, Do und Fr am Wasserturm ---
    for breite, hoehe, art in ((1280, 620, "quer"), (800, 1100, "hoch")):
        for thema in ("light", "dark"):
            await _ansehen(tab, seed, "kai", breite, hoehe, thema)
            await _ganze_seite(tab, f"heute_tage_kai_{art}_{'hell' if thema == 'light' else 'dunkel'}", breite, hoehe)
    await _ansehen(tab, seed, "kai", 1280, 620, "light")
    p.pruefe("Kai: heute keine Karte", await tab.js(
        "[document.querySelectorAll('[data-einsatz]').length,(document.getElementById('keinEinsatzText')||{}).textContent||null]"),
        [0, "Heute ist nichts eingeplant."])
    p.pruefe("Kai: keine Vorwahl der Zeit", await tab.js(VORWAHL), None)
    p.pruefe("Kai: Nächste Tage nur seine Tage, mit den anderen dieser Tage", await tab.js(NAECHSTE),
             ["Do 12.11.–Fr 13.11.Am Wasserturm 4 · mit Tom, Mia, Ole", "Di 17.11.Dachfenster Krüger · mit Lia"])

    # --- Mia: heute am Ortgang, nicht am Wasserturm ---
    await _ansehen(tab, seed, "mia", 1280, 620, "light")
    await tab.bild("heute_tage_mia_quer_hell")
    p.pruefe("Mia: eine Karte Ortgang, ihre Folge, „Mit dir“ Tom", await tab.js(KARTEN),
             [["Heutiger Einsatz · 11.11.", "Ortgang Lindenweg 9", "Tom Monteur"]])
    p.pruefe("Mia: Nächste Tage Wasserturm Do–Fr, ohne „weiter“", await tab.js(NAECHSTE),
             ["Do 12.11.–Fr 13.11.Am Wasserturm 4 · mit Tom, Ole, Kai"])

    # --- Ole: heute beim Sturmschaden (nur Mi), Do–Fr am Wasserturm ---
    await _ansehen(tab, seed, "ole", 800, 1100, "light")
    await tab.bild("heute_tage_ole_hoch_hell")
    p.pruefe("Ole: Karte Sturmschaden mit Lia, nur heute", await tab.js(KARTEN),
             [["Heutiger Einsatz · 11.11.", "Sturmschaden Gartenstraße 2", "Lia Lang"]])
    p.pruefe("Ole: Nächste Tage Wasserturm Do–Fr", await tab.js(NAECHSTE), ["Do 12.11.–Fr 13.11.Am Wasserturm 4 · mit Tom, Mia, Kai"])

    # --- Lia: „mit …“ je Tag -- Kai ist am Dachfenster nur am Di dabei ---
    await _ansehen(tab, seed, "lia", 1280, 620, "light")
    p.pruefe("Lia: Nächste Tage Dachfenster, „mit Kai“ nur am Di", await tab.js(NAECHSTE),
             ["Mo 16.11.Dachfenster Krüger · Dachfenster Krüger", "Di 17.11.Dachfenster Krüger · mit Kai", "Mi 18.11.Dachfenster Krüger · Dachfenster Krüger"])
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="„Heute“ mit der Besetzung je Tag (1.9.262)", uhr="2026-11-11 10:00"))
