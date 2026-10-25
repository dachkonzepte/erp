"""Klicktest: keine Zeiten der Monteurin auf abgeschlossene Aufträge (seit 1.9.82, Stufe 4, R4 Nachtrag 3, B) -- Seite des Auftrags und
„Meine Zeiten“.

Befüllt: Objekt „Halle Süd“ (Dachbau Süd GmbH); Auftrag A „Dachsanierung“ heute für Mia eingeplant (offen), Z „Flachdach Halle“ gestern für
Mia eingeplant, abgeschlossen, mit Mias Buchung von heute 06:00–07:00 (heute: „Meine Zeiten“ zeigt den laufenden Monat), S „Stornoauftrag“ storniert mit einem Bericht von Mia. Büro –
Auftrag „buero“. Feste Uhr 10:00.

    Seite von Z         Karte „Zeiten“ ohne Text und ohne „Zeit nachtragen“, an ihrer Stelle „Der Auftrag ist abgeschlossen – Zeiten dafür
                        trägt das Büro ein.“ (hoch 800 × 1100, Bild 1); quer ebenso (Bild 1a)
    Seite von S         „Der Auftrag ist storniert – Zeiten dafür trägt das Büro ein.“
    Seite von A         „Zeit nachtragen“ wie bisher (zu „Meine Zeiten“ mit A gewählt), kein Hinweis
    veraltete Seite     Mia auf der Seite von A, das Büro schließt A ab; „Zeit nachtragen“ -> „Meine Zeiten“ mit A gewählt („nicht in der
                        Auswahl“), Von/Bis, „Nachtragen“ -> im Dialog die Meldung, der Dialog bleibt offen, nichts gebucht (Bild 2);
                        seit 1.9.83 steht die Meldung ganz im Bild in der festen Leiste über den Knöpfen, über deren ganze Breite, Ober-
                        und Unterkante unverdeckt (1.9.82: die untere Hälfte unter der Leiste);
                        neu geladen: die Seite von A zeigt den Hinweis
    Ändern              „Meine Zeiten“: Mias Buchung auf Z ändern -> im Dialog die Meldung, die Buchung bleibt
    überall             keine JS-Fehler

Die Bilder liegen im Ordner der Screenshots.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_zeiten_abgeschlossen.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD]
        [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer etwa 15 Sekunden.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import datetime, time, timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.meldungen import AUFTRAG_ABGESCHLOSSEN_ZEITEN, AUFTRAG_STORNIERT_ZEITEN
    from app.models import (
        AppUser, Customer, Employee, Order, OrderItem, PlanningSlot, Project, Property, Team, WorkPreparationTeamAssignment,
        WorkPreparationTeamEmployee,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.service_reports import create_report
    from app.time_tracking import start_timer, stop_timer
    from app.work_preparation import ensure_preparation

    heute = berlin_today()
    gestern = heute - timedelta(days=1)
    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True,
                   hourly_wage=Decimal("22.00"))
    db.add(mia); db.flush()
    benutzer = {"mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id, password_hash=k.passwort()),
                "buero": AppUser(username="buero", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())}
    db.add_all(benutzer.values())
    kunde = Customer(name="Dachbau Süd GmbH", last_name="Dachbau Süd GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    halle = Property(customer_id=kunde.id, name="Halle Süd", street="Südring 2", postal_code="52531", city="Übach-Palenberg")
    db.add(halle); db.flush()

    def auftrag(nr, titel):
        projekt = Project(project_number=f"P-KT-Z{nr}", name=titel, customer_id=kunde.id, property_id=halle.id,
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        o = Order(order_number=f"AUF-2026-020{nr}", project_id=projekt.id, source_quote_id=960 + nr, quote_number_snapshot=f"A-KT-Z{nr}",
                  title=titel, customer_name=kunde.name, property_name=halle.name, property_address="Südring 2\n52531 Übach-Palenberg")
        db.add(o); db.flush()
        db.add(OrderItem(order_id=o.id, sort_order=10, position_number="1", short_text=titel, quantity=Decimal("1"), unit="psch",
                         unit_price=Decimal("1")))
        db.commit()
        return o

    a, z, s = auftrag(1, "Dachsanierung"), auftrag(2, "Flachdach Halle"), auftrag(3, "Stornoauftrag")
    team = Team(name="Kolonne Süd", active=True)
    db.add(team); db.flush()
    for o, tag in ((a, heute), (z, gestern)):
        prep = ensure_preparation(db, o.id)
        zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
        db.add(zuordnung); db.flush()
        db.add(WorkPreparationTeamEmployee(assignment_id=zuordnung.id, employee_id=mia.id, employee_name_snapshot=mia.first_name))
        db.add(PlanningSlot(preparation_id=prep.id, team_assignment_id=zuordnung.id, start_date=tag, end_date=tag))
    db.commit()
    row = start_timer(db, employee_id=mia.id, order_id=z.id, started_at=datetime.combine(heute, time(6)))
    buchung = stop_timer(db, row.id, ended_at=datetime.combine(heute, time(7)))
    create_report(db, s.id, "rapport", "Vor dem Storno", created_by_employee_id=mia.id)  # ihr Zugang zur Seite von S
    z.status, s.status = "abgeschlossen", "storniert"
    db.commit()
    return {"a": a.id, "z": z.id, "s": s.id, "buchung": buchung.id, "heute": heute.isoformat(), "mia": mia.id,
            "abgeschlossen": AUFTRAG_ABGESCHLOSSEN_ZEITEN, "storniert": AUFTRAG_STORNIERT_ZEITEN,
            "cookies": {n: k.cookies(u) for n, u in benutzer.items()}}


AUFTRAG_GELADEN = "typeof orderData!=='undefined'&&!!orderData&&!!document.getElementById('reportList')"
ZEITEN_BEREIT = "!document.getElementById('tage').classList.contains('laedt')&&document.getElementById('monatName').textContent!==''"
ZEITEN_KARTE = ("(()=>{const l=document.getElementById('zeitNachtragen'),h=document.getElementById('zeitenGesperrt');"
                "return [document.getElementById('zeitenText').hidden,l.hidden,Math.round(l.getBoundingClientRect().height),h.hidden,"
                "h.textContent,l.getAttribute('href')]})()")


def _als_buero(tab, cookies, methode, pfad, body):
    """Eine schreibende Anfrage des Büros an der Seite der Monteurin vorbei (Regel 33: mit Origin)."""
    import json
    import urllib.request

    req = urllib.request.Request(tab.base + pfad, data=json.dumps(body).encode("utf-8"), method=methode,
                                 headers={"Cookie": "; ".join(f"{n}={w}" for n, w in cookies.items()), "Origin": tab.base,
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


async def _seite(tab, order_id):
    await tab.oeffnen(f"/orders/{order_id}/service-reports", AUFTRAG_GELADEN)
    await tab.warte_auf_ruhe()


async def pruefen(tab, seed, p):
    a, z, s = seed["a"], seed["z"], seed["s"]
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(800, 1100, mobil=True)
    await tab.oeffnen("/mobil", "document.readyState==='complete'")
    await tab.js("localStorage.setItem('erp_theme','light')")

    # --- Seite eines abgeschlossenen und eines stornierten Auftrags ------------------------------------------------------------------
    await _seite(tab, z)
    p.pruefe("Seite von Z (abgeschlossen): ohne Text und „Zeit nachtragen“, an ihrer Stelle die Meldung", await tab.js(ZEITEN_KARTE),
             [True, True, 0, False, seed["abgeschlossen"], f"/mobil/zeiten?order_id={z}"])
    await tab.js("document.getElementById('zeitenKarte').scrollIntoView({block:'end'})")
    await tab.bild("1_auftragsseite_abgeschlossen_hoch_hell")
    await tab.fenster(1280, 620, mobil=True)
    await _seite(tab, z)
    await tab.js("document.getElementById('zeitenKarte').scrollIntoView({block:'end'})")
    await tab.bild("1a_auftragsseite_abgeschlossen_quer_hell")
    await _seite(tab, s)
    p.pruefe("Seite von S (storniert): die Meldung „storniert“", (await tab.js(ZEITEN_KARTE))[:5], [True, True, 0, False, seed["storniert"]])

    # --- offener Auftrag: wie bisher; dann schließt das Büro ihn, während die Seite offen ist ------------------------------------------
    await _seite(tab, a)
    p.pruefe("Seite von A (offen): „Zeit nachtragen“ zu „Meine Zeiten“ mit A, kein Hinweis", await tab.js(ZEITEN_KARTE),
             [False, False, 48, True, "", f"/mobil/zeiten?order_id={a}"])
    p.pruefe("Das Büro schließt A ab (PUT /api/orders/{id})", _als_buero(tab, seed["cookies"]["buero"], "PUT", f"/api/orders/{a}",
                                                                          {"status": "abgeschlossen"}), 200)
    await tab.js("document.getElementById('zeitNachtragen').click()")
    await tab.warten(f"location.pathname==='/mobil/zeiten'&&location.search==='?order_id={a}'", 15)
    await tab.warten(ZEITEN_BEREIT, 15)
    await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('nachtragenKnopf').click()")
    await tab.warten("document.getElementById('zeitDialog').open")
    p.pruefe("„Zeit nachtragen“: A gewählt, als „nicht in der Auswahl“ gekennzeichnet", await tab.js(
        "(()=>{const s=document.getElementById('zdAuftrag');return [s.value,s.options[s.selectedIndex].textContent.includes('(nicht in der Auswahl)')]})()"),
        [str(a), True])
    for feld, wert in (("zdVon", "07:30"), ("zdBis", "09:00")):
        await tab.js(f"(f=>{{f.value='{wert}';f.dispatchEvent(new Event('input',{{bubbles:true}}))}})(document.getElementById('{feld}'))")
    await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('zdSpeichern').click()")
    await tab.warten("document.getElementById('zdStatus').textContent!==''", 15)
    await tab.warte_auf_ruhe()
    p.pruefe("Nachtragen abgelehnt: die Meldung im Dialog, der Dialog bleibt offen, der Knopf wieder frei", await tab.js(
        "[document.getElementById('zdStatus').textContent,document.getElementById('zeitDialog').open,document.getElementById('zdSpeichern').disabled]"),
        [seed["abgeschlossen"], True, False])
    p.pruefe("Die Meldung ganz im Bild, über den Knöpfen und über die ganze Leiste, Ober- und Unterkante unverdeckt (seit 1.9.83)",
             await tab.js(
        "(()=>{const s=document.getElementById('zdStatus'),r=s.getBoundingClientRect(),"
        "a=document.getElementById('zdAbbrechen').getBoundingClientRect(),k=document.getElementById('zdSpeichern').getBoundingClientRect(),"
        "frei=y=>{const e=document.elementFromPoint(r.left+4,y);return !!e&&s.contains(e)};"
        "return [r.height>0&&r.top>=0&&r.bottom<=innerHeight,r.bottom<=k.top,frei(r.top+2),frei(r.bottom-2),"
        "r.left<=a.left+1&&r.right>=k.right-1]})()"), [True, True, True, True, True])
    await tab.bild("2_nachtrag_abgelehnt_quer_hell")
    await tab.oeffnen("/mobil/zeiten", ZEITEN_BEREIT)
    await tab.warte_auf_ruhe()
    p.pruefe("Nichts gebucht: keine Zeile auf A", await tab.js(
        f"D.tage.flatMap(t=>t.zeilen).filter(z=>z.order_id==={a}).length"), 0)

    # --- Ändern einer Buchung auf dem abgeschlossenen Auftrag -------------------------------------------------------------------------
    await tab.js(f"zeitDialogOeffnen(zeileZu('{seed['buchung']}'))")
    await tab.warten("document.getElementById('zeitDialog').open")
    await tab.warte_auf_ruhe()
    await tab.js("(f=>{f.value='07:15';f.dispatchEvent(new Event('input',{bubbles:true}))})(document.getElementById('zdBis'))")
    await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('zdSpeichern').click()")
    await tab.warten("document.getElementById('zdStatus').textContent!==''", 15)
    await tab.warte_auf_ruhe()
    p.pruefe("Ändern der Buchung auf Z abgelehnt: die Meldung im Dialog", await tab.js(
        "[document.getElementById('zdStatus').textContent,document.getElementById('zeitDialog').open]"), [seed["abgeschlossen"], True])
    await tab.oeffnen("/mobil/zeiten", ZEITEN_BEREIT)
    await tab.warte_auf_ruhe()
    p.pruefe("Die Buchung bleibt 06:00–07:00", await tab.js(
        f"(z=>z&&[z.von,z.bis])(D.tage.flatMap(t=>t.zeilen).find(z=>z.id==={seed['buchung']}))"), ["06:00", "07:00"])

    # --- neu geladen: die Seite von A zeigt jetzt den Hinweis -------------------------------------------------------------------------
    await _seite(tab, a)
    p.pruefe("Seite von A neu geladen: die Meldung statt „Zeit nachtragen“", (await tab.js(ZEITEN_KARTE))[:5],
             [True, True, 0, False, seed["abgeschlossen"]])
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Keine Zeiten auf abgeschlossene Aufträge (1.9.82)", uhr="10:00"))
