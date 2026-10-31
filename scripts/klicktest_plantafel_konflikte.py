"""Klicktest: Konflikte beim Speichern eines Einsatzes (1.9.143, Stufe 6, R1, Punkt 1) -- warnen, trotzdem planbar.

Stehende Uhr 14.10.2026 10:00. Befüllt: Kolonnen Nord (Tom, Kran) und Süd (Tom, Kran), Kolonne West (Sol), zwei Aufträge, Auftrag A eingeplant auf Nord.

    Neu         „+ Einsatz planen“ für Auftrag B auf Süd, derselbe Zeitraum -> Dialog mit Warnliste (Person doppelt, Gerät doppelt, gleichzeitig in Projekt),
                nichts gespeichert; „Abbrechen“ -> zurück im Dialog „Einsatz planen“; „Trotzdem planen“ -> gespeichert, beide Dialoge zu, Tafel neu
    Wochenende  Auftrag C auf West über ein Wochenende -> gespeichert, kein Dialog, kein Hinweis (seit 1.9.150)
    Hinweis     Auftrag E auf Ost über einen betriebsfreien Tag -> kein Dialog, Hinweis über der Tafel
    Bearbeiten  Einsatz B auf West schieben im Dialog -> Warnliste; nur die Notiz ändern -> keine Warnliste
    Ziehen      Einsatz C mit „dropSlot“ auf Nord -> Warnliste, nichts verschoben; „Trotzdem planen“ -> verschoben
    Abgeschlossen  Einsatz eines abgeschlossenen Auftrags auf Ost: ein neuer Einsatz daneben fragt nicht, nichts ist rot, der Balken sagt „Auftrag abgeschlossen“ (seit 1.9.151)
    Antrag offen  Sol hat einen offenen Antrag: ein Einsatz auf West meldet „Antrag offen“ ohne Rückfrage, der Balken ist nicht rot und nennt ihn; Büro – Auftrag sieht die Art nicht (seit 1.9.152)
    L6          /planning?auftrag=<abgeschlossen> und <storniert>: kein Dialog, der Grund; unbekannt: Meldung; Akte des geschlossenen Auftrags ohne „Einsatz planen“, mit dem Grund, der laufende mit (seit 1.9.155)
    Balken      „Auftrag abgeschlossen“, „Auftrag pausiert“, „Antrag offen“ stehen sichtbar im Balken, gemessen, nicht nur im Text (seit 1.9.156)
    Büro–Auftrag die Warnliste nennt bei einer Abwesenheit nur „abwesend“

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_plantafel_konflikte.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

HEUTE = "2026-10-14"
UHR_MS = int(datetime(2026, 10, 14, 10, 0, tzinfo=ZoneInfo("Europe/Berlin")).timestamp() * 1000)


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.absence_requests import create_request
    from app.auftragsstatus import status_aendern
    from app.models import AppUser, Customer, Employee, EmployeeAbsence, OperationalResource, PlanningHoliday, Project, Quote, QuoteItem, Team, TeamEmployee, TeamResource
    from app.orders import create_order_from_quote, load_order
    from app.planning import create_slot
    from app.project_pipeline_columns import default_pipeline_column_id

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    berta = AppUser(username="berta", display_name="Berta Büro", role="buero_auftrag", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Plan", last_name="Plan", street="Dachweg 1", postal_code="52531", city="Uebach")
    tom = Employee(employee_number="M-1", first_name="Tom", last_name="Test", employee_group="gewerblich", weekly_hours=Decimal("40"), active=True)
    sol = Employee(employee_number="M-2", first_name="Sol", last_name="Test", employee_group="gewerblich", weekly_hours=Decimal("40"), active=True)
    mia = Employee(employee_number="M-3", first_name="Mia", last_name="Test", employee_group="gewerblich", weekly_hours=Decimal("40"), active=True)
    kran = OperationalResource(resource_number="K-1", resource_type="Maschine", name="Kran 30 m", identifier="K1", active=True)
    db.add_all([anna, berta, kunde, tom, sol, mia, kran]); db.flush()

    def kolonne(name, *personen, geraet=None):
        team = Team(name=name, active=True)
        db.add(team); db.flush()
        for person in personen:
            db.add(TeamEmployee(team_id=team.id, employee_id=person.id))
        if geraet:
            db.add(TeamResource(team_id=team.id, resource_id=geraet.id))
        db.flush()
        return team

    def auftrag(nummer):
        projekt = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=kunde.id, status="angebot",
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-{nummer}", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2", unit_price=Decimal("50")))
        db.commit()
        order = create_order_from_quote(db, quote.id, order_date=date(2026, 9, 1), execution_start=None, execution_end=None,
                                        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
        return load_order(db, order.id)

    nord, sued, west, ost = kolonne("Nord", tom, geraet=kran), kolonne("Süd", tom, geraet=kran), kolonne("West", sol), kolonne("Ost", mia)
    a, b, c, d, e, f, g = auftrag("A"), auftrag("B"), auftrag("C"), auftrag("D"), auftrag("E"), auftrag("F"), auftrag("G")
    h, s, pa = auftrag("H"), auftrag("S"), auftrag("P")
    create_slot(db, order_id=pa.id, team_id=nord.id, start_date=date(2026, 11, 17), end_date=date(2026, 11, 18))
    status_aendern(db, pa.id, "pausiert", "Gerüst fehlt")
    status_aendern(db, s.id, "storniert", "Kunde abgesprungen")
    create_request(db, employee_id=sol.id, absence_type="Krankheit", absence_category="krankheit", start_date=date(2026, 11, 10), end_date=date(2026, 11, 10))
    create_slot(db, order_id=f.id, team_id=ost.id, start_date=date(2026, 11, 3), end_date=date(2026, 11, 4))
    status_aendern(db, f.id, "abgeschlossen", "ohne Rechnung")
    db.add(PlanningHoliday(holiday_date=date(2026, 10, 28), name="Betriebsausflug", active=True))
    create_slot(db, order_id=a.id, team_id=nord.id, start_date=date(2026, 10, 19), end_date=date(2026, 10, 21))
    db.add(EmployeeAbsence(employee_id=mia.id, absence_type="Krankheit", absence_category="krankheit", start_date=date(2026, 10, 19), end_date=date(2026, 10, 19)))
    db.commit()
    return {"b": b.id, "c": c.id, "d": d.id, "e": e.id, "f": f.id, "g": g.id, "h": h.id, "s": s.id, "projekt_f": f.project_id, "projekt_s": s.project_id, "projekt_b": b.project_id, "nord": nord.id, "sued": sued.id, "west": west.id, "ost": ost.id,
            "anna": k.cookies(anna), "berta": k.cookies(berta)}


BEREIT = "typeof board!=='undefined'&&board&&board.teams&&board.teams.length>0&&typeof orders!=='undefined'"


async def _zeile_im_balken(tab, text):
    """Die Zeile steht ganz im Balken. Der Balken schneidet ab (overflow:hidden): textContent findet auch, was niemand sieht -- so blieb die vierte Zeile unbemerkt (1.9.156)."""
    return await tab.js("(()=>{const m=[...document.querySelectorAll('.slot .slot-meta')].find(x=>x.textContent.includes(" + repr(text) + "));if(!m)return 'fehlt';"
                        "const a=m.getBoundingClientRect(),b=m.closest('.slot').getBoundingClientRect();return a.bottom<=b.bottom&&a.top>=b.top})()")


async def _neu(tab, order, team, von, bis):
    await tab.js(f"void openCreate({order},null,{team})")
    await tab.warten("document.getElementById('createDialog').open")
    await tab.js(f"document.getElementById('newStart').value='{von}';document.getElementById('newEnd').value='{bis}';document.getElementById('newPlannedHours').value='1'")
    await tab.js("void saveNew()")


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")  # Bilder hell
    await tab.browser_uhr_fest(UHR_MS)
    await tab.anmelden(seed["anna"])
    await tab.oeffnen("/planning", BEREIT)
    p.pruefe("Adresse: Woche von heute", await tab.js("iso(periodStart)"), "2026-10-12")
    await tab.js("movePeriod(7)")
    await tab.warten(BEREIT + "&&board.slots.length===1")

    # --- Neuer Einsatz: Warnliste ---
    await _neu(tab, seed["b"], seed["sued"], "2026-10-19", "2026-10-21")
    p.pruefe("Warnliste erscheint", await tab.warten("document.getElementById('konfliktDialog').open"), True)
    text = await tab.js("document.getElementById('konfliktWarnungen').textContent")
    p.pruefe("nennt die Person", "Person doppelt: Tom Test" in text, True)
    p.pruefe("nennt das Gerät", "Gerät doppelt: Kran 30 m" in text, True)
    p.pruefe("nennt das andere Projekt", "gleichzeitig in P-A · Dach A" in text, True)
    p.pruefe("nichts gespeichert", await tab.js("board.slots.length"), 1)
    await tab.bild("warnliste_neu")
    await tab.js("konfliktDialog.close()")
    p.pruefe("Abbrechen: zurück im Dialog", await tab.js("document.getElementById('createDialog').open&&!document.getElementById('konfliktDialog').open"), True)
    await tab.js("void saveNew()")
    await tab.warten("document.getElementById('konfliktDialog').open")
    await tab.js("document.getElementById('konfliktTrotzdem').click()")
    p.pruefe("Trotzdem planen: gespeichert", await tab.warten("!document.getElementById('konfliktDialog').open&&!document.getElementById('createDialog').open&&board.slots.length===2"), True)
    p.pruefe("beide rot", await tab.js("document.querySelectorAll('.slot.conflict').length"), 2)

    # --- Über ein Wochenende: meldet nichts (seit 1.9.150) ---
    await _neu(tab, seed["c"], seed["west"], "2026-10-23", "2026-10-26")
    p.pruefe("Wochenende: gespeichert ohne Rückfrage", await tab.warten("board.slots.length===3&&!document.getElementById('createDialog').open"), True)
    p.pruefe("Wochenende: kein Warn-Dialog", await tab.js("document.getElementById('konfliktDialog').open"), False)
    p.pruefe("Wochenende: kein Hinweis", await tab.js("document.getElementById('einsatzHinweis').textContent"), "")
    p.pruefe("Wochenende: Balken nicht rot", await tab.js(f"board.slots.find(s=>s.order_id==={seed['c']}).conflicts.length"), 0)

    # --- Hinweis ohne Rückfrage ---
    await _neu(tab, seed["e"], seed["ost"], "2026-10-27", "2026-10-29")
    p.pruefe("Hinweis: gespeichert ohne Rückfrage", await tab.warten("board.slots.length===4&&!document.getElementById('createDialog').open"), True)
    p.pruefe("Hinweis: kein Warn-Dialog", await tab.js("document.getElementById('konfliktDialog').open"), False)
    hinweis = await tab.js("document.getElementById('einsatzHinweis').textContent")
    p.pruefe("Hinweis: steht über der Tafel", "Einsatz gespeichert" in hinweis and "Feiertag: Betriebsausflug · 28.10." in hinweis, True)
    await tab.bild("hinweis_betriebsfrei")

    # --- Bearbeiten ---
    einsatz_b = await tab.js(f"board.slots.find(s=>s.order_id==={seed['b']}).id")
    await tab.js(f"openEdit({einsatz_b})")
    await tab.js("document.getElementById('editNotes').value='Kran ab 8 Uhr';void saveEdit()")
    p.pruefe("nur Notiz: keine Warnliste, gespeichert", await tab.warten(f"!document.getElementById('editDialog').open&&board.slots.find(s=>s.id==={einsatz_b}).notes==='Kran ab 8 Uhr'"), True)
    p.pruefe("nur Notiz: kein Warn-Dialog", await tab.js("document.getElementById('konfliktDialog').open"), False)
    einsatz_c = await tab.js(f"board.slots.find(s=>s.order_id==={seed['c']}).id")
    await tab.js(f"openEdit({einsatz_c})")
    await tab.js(f"document.getElementById('editTeam').value='{seed['nord']}';document.getElementById('editStart').value='2026-10-19';document.getElementById('editEnd').value='2026-10-20';void saveEdit()")
    p.pruefe("Kolonne geändert: Warnliste", await tab.warten("document.getElementById('konfliktDialog').open"), True)
    await tab.js("konfliktDialog.close();editDialog.close()")
    p.pruefe("Kolonne geändert: nichts verschoben", await tab.js(f"board.slots.find(s=>s.id==={einsatz_c}).team_id"), seed["west"])

    # --- Ziehen ---
    await tab.js(f"dragData={{id:{einsatz_c},days:2}};void dropSlot({{preventDefault(){{}},clientX:0,currentTarget:Object.assign(document.createElement('div'),{{getBoundingClientRect:()=>({{left:0}})}})}},{seed['nord']})")
    p.pruefe("Ziehen: Warnliste", await tab.warten("document.getElementById('konfliktDialog').open"), True)
    p.pruefe("Ziehen: nichts verschoben", await tab.js(f"board.slots.find(s=>s.id==={einsatz_c}).team_id"), seed["west"])
    await tab.js("document.getElementById('konfliktTrotzdem').click()")
    p.pruefe("Ziehen: Trotzdem planen verschiebt", await tab.warten(f"!document.getElementById('konfliktDialog').open&&board.slots.find(s=>s.id==={einsatz_c}).team_id==={seed['nord']}"), True)

    # --- Einsatz eines abgeschlossenen Auftrags: zählt nicht, bleibt sichtbar (seit 1.9.151) ---
    await tab.js("movePeriod(14)")
    await tab.warten(BEREIT + "&&board.slots.length===1")
    p.pruefe("Abgeschlossen: Balken sagt es", "Auftrag abgeschlossen" in await tab.js("document.querySelector('.slot').textContent"), True)
    p.pruefe("Abgeschlossen: Zeile im Balken zu sehen", await _zeile_im_balken(tab, "Auftrag abgeschlossen"), True)
    await _neu(tab, seed["g"], seed["ost"], "2026-11-03", "2026-11-04")
    p.pruefe("Abgeschlossen: gespeichert ohne Rückfrage", await tab.warten("board.slots.length===2&&!document.getElementById('createDialog').open"), True)
    p.pruefe("Abgeschlossen: kein Warn-Dialog", await tab.js("document.getElementById('konfliktDialog').open"), False)
    p.pruefe("Abgeschlossen: nichts rot", await tab.js("document.querySelectorAll('.slot.conflict').length"), 0)
    await tab.bild("abgeschlossen_zaehlt_nicht")

    # --- Offener Antrag: Hinweis, keine Rückfrage, nicht rot (seit 1.9.152) ---
    await _neu(tab, seed["h"], seed["west"], "2026-11-09", "2026-11-11")
    p.pruefe("Antrag offen: gespeichert ohne Rückfrage", await tab.warten("board.slots.length===3&&!document.getElementById('createDialog').open"), True)
    p.pruefe("Antrag offen: kein Warn-Dialog", await tab.js("document.getElementById('konfliktDialog').open"), False)
    hinweis = await tab.js("document.getElementById('einsatzHinweis').textContent")
    p.pruefe("Antrag offen: steht über der Tafel, mit Art", "Antrag offen: Sol Test · Krankheit · 10.11." in hinweis, True)
    p.pruefe("Antrag offen: Balken nicht rot", await tab.js("document.querySelectorAll('.slot.conflict').length"), 0)
    p.pruefe("Antrag offen: Balken nennt ihn", "Antrag offen: Sol Test · Krankheit" in await tab.js("document.body.textContent"), True)
    p.pruefe("Antrag offen: Zeile im Balken zu sehen", await _zeile_im_balken(tab, "Antrag offen: Sol Test"), True)
    p.pruefe("Antrag offen: zählt nicht als Konflikt", await tab.js("board.conflict_count"), 0)
    await tab.bild("antrag_offen_admin")

    # --- Pausiert: dieselbe Zeile, schon seit 1.9.124 abgeschnitten (seit 1.9.156 zu sehen) ---
    await tab.js("movePeriod(14)")
    await tab.warten(BEREIT + "&&board.slots.length===1")
    p.pruefe("Pausiert: Zeile im Balken zu sehen", await _zeile_im_balken(tab, "Auftrag pausiert · Gerüst fehlt"), True)

    # --- L6: kein „Einsatz planen“, das ins Leere führt (seit 1.9.155) ---
    for name, order, projekt, grund in (("abgeschlossen", seed["f"], seed["projekt_f"], "Der Auftrag ist abgeschlossen"), ("storniert", seed["s"], seed["projekt_s"], "Der Auftrag ist storniert")):
        await tab.oeffnen(f"/planning?auftrag={order}", BEREIT)
        p.pruefe(f"L6 {name}: der Grund über der Tafel", await tab.warten(f"document.getElementById('einsatzHinweis').textContent.includes('{grund}')"), True)
        p.pruefe(f"L6 {name}: kein Dialog", await tab.js("document.getElementById('createDialog').open"), False)
        await tab.bild(f"l6_tafel_{name}")
        await tab.oeffnen(f"/projects/{projekt}?auftrag={order}#ausfuehrung", "typeof akte!=='undefined'&&akte&&akte.ausfuehrung")
        await tab.warte_auf_ruhe()
        await tab.bild_ganz(f"l6_akte_{name}")
        p.pruefe(f"L6 {name}: Akte ohne „Einsatz planen“", await tab.js("getComputedStyle(document.getElementById('einsatzLink')).display"), "none")
        p.pruefe(f"L6 {name}: Akte nennt den Grund", grund in await tab.js("document.getElementById('einsatzGesperrt').textContent"), True)
        p.pruefe(f"L6 {name}: keine Hauptaktion „Einsatz planen“", await tab.js("!!(akte.hauptaktion&&akte.hauptaktion.art==='einsatz')"), False)
    await tab.oeffnen("/planning?auftrag=99999", BEREIT)
    p.pruefe("L6 unbekannt: Meldung", await tab.warten("document.getElementById('einsatzHinweis').textContent.includes('Auftrag wurde nicht gefunden.')"), True)
    p.pruefe("L6 unbekannt: kein Dialog", await tab.js("document.getElementById('createDialog').open"), False)
    await tab.oeffnen(f"/projects/{seed['projekt_b']}?auftrag={seed['b']}", "typeof akte!=='undefined'&&akte&&akte.ausfuehrung")
    await tab.warte_auf_ruhe()
    p.pruefe("L6 laufend: Akte mit „Einsatz planen“", await tab.js("document.getElementById('einsatzLink').hidden"), False)
    p.pruefe("L6 laufend: kein Grund", await tab.js("document.getElementById('einsatzGesperrt').hidden"), True)
    await tab.oeffnen(f"/planning?auftrag={seed['b']}", BEREIT + "&&document.getElementById('createDialog').open")
    p.pruefe("L6 laufend: der Dialog öffnet", await tab.js("document.getElementById('newOrder').value"), str(seed["b"]))
    await tab.js("createDialog.close()")
    p.pruefe("Admin: JS-Fehler", tab.fehler, [])

    # --- Büro – Auftrag: Art der Abwesenheit nicht in der Liste ---
    await tab.anmelden(seed["berta"])
    await tab.oeffnen("/planning", BEREIT)
    await tab.js("movePeriod(7)")
    await tab.warten(BEREIT + "&&board.slots.length===4")
    await _neu(tab, seed["d"], seed["ost"], "2026-10-19", "2026-10-19")
    p.pruefe("Büro – Auftrag: Warnliste", await tab.warten("document.getElementById('konfliktDialog').open"), True)
    text = await tab.js("document.getElementById('konfliktWarnungen').textContent")
    p.pruefe("Büro – Auftrag: nur „abwesend“", "Mia Test · abwesend" in text and "Krankheit" not in text, True)
    await tab.bild("warnliste_buero_auftrag")
    await tab.js("konfliktDialog.close();createDialog.close();movePeriod(21)")
    await tab.warten(BEREIT + "&&board.slots.some(s=>s.order_id===" + str(seed["h"]) + ")")
    p.pruefe("Büro – Auftrag: Antrag offen ohne Art", await tab.js(f"board.slots.find(s=>s.order_id==={seed['h']}).conflicts.map(c=>c.label).join()"), "Sol Test")
    p.pruefe("Büro – Auftrag: Art nicht auf dem Balken", "Krankheit" in await tab.js("[...document.querySelectorAll('.slot')].map(x=>x.textContent).join(' ')"), False)
    p.pruefe("Büro – Auftrag: Balken nennt die Person", "Antrag offen: Sol Test" in await tab.js("[...document.querySelectorAll('.slot')].map(x=>x.textContent).join(' ')"), True)
    await tab.bild("antrag_offen_buero_auftrag")
    p.pruefe("Büro – Auftrag: JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr=f"{HEUTE} 10:00"))
