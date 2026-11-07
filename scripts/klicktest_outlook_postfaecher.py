"""Klicktest: Postfächer in den Einstellungen, der Kran im Kalender und auf der Plantafel (1.9.161/1.9.162, Stufe 6, R2, Punkte 5 und 6). Kein Netz: der Abgleich ist aus, der Stand steht in der Datenbank.

Stehende Uhr 14.10.2026 10:00.

    Einstellungen  als Admin je Postfach Lauf, Fehler als Satz, Wartend; Gerät zuordnen, dieselbe Adresse wie ein Konto mit Meldung abgelehnt, entfernen; 412 px; Bilder hell und dunkel
    Rechte         Büro – Auftrag sieht den Abschnitt nicht
    Kalender       der Kran steht in der Auswahl, ein Termin am Kran zeigt seinen Namen; ein ganztägiger Termin steht an genau einem Tag, ein dreitägiger an dreien
    Plantafel      ein Einsatz mit dem Kran an dem Tag: Warnliste „Gerät doppelt: Kran 30 m · Termin: …“, „Trotzdem planen“ speichert

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_outlook_postfaecher.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

UHR_MS = int(datetime(2026, 10, 14, 10, 0, tzinfo=ZoneInfo("Europe/Berlin")).timestamp() * 1000)
GELADEN = "document.querySelectorAll('#outlookPostfaecher .outlook-postfach').length>0"
BEREIT = "typeof board!=='undefined'&&board&&board.teams&&board.teams.length>0&&typeof orders!=='undefined'"


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.models import (AppUser, CalendarEvent, Customer, Employee, OperationalResource, OutlookCalendarSyncState, Project, Quote, QuoteItem, Team, TeamEmployee, TeamResource)
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort(), outlook_mailbox="anna@x.de")
    berta = AppUser(username="berta", display_name="Berta Büro", role="buero_auftrag", password_hash=k.passwort())
    kran = OperationalResource(resource_number="K-1", resource_type="Maschine", name="Kran 30 m", identifier="K1", active=True, outlook_mailbox="kran@x.de")
    buehne = OperationalResource(resource_number="B-1", resource_type="Maschine", name="Hubbühne", identifier="B1", active=True)
    tom = Employee(employee_number="M-1", first_name="Tom", last_name="Test", employee_group="gewerblich", weekly_hours=Decimal("40"), active=True)
    kunde = Customer(name="Bauherr Plan", last_name="Plan", street="Dachweg 1", postal_code="52531", city="Uebach")
    db.add_all([anna, berta, kran, buehne, tom, kunde]); db.flush()
    db.add(OutlookCalendarSyncState(postfach="anna@x.de", last_synced_at=datetime(2026, 10, 14, 7, 45)))
    db.add(OutlookCalendarSyncState(postfach="kran@x.de", last_synced_at=datetime(2026, 10, 13, 7, 45), last_error_type="OutlookSyncError", last_error_at=datetime(2026, 10, 14, 7, 45), last_error_status=403))
    team = Team(name="Nord", active=True)
    db.add(team); db.flush()
    db.add_all([TeamEmployee(team_id=team.id, employee_id=tom.id), TeamResource(team_id=team.id, resource_id=kran.id)])
    projekt = Project(project_number="P-A", name="Dach A", customer_id=kunde.id, status="angebot", pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    quote = Quote(quote_number="A-A", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"))
    db.add(quote); db.flush()
    db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2", unit_price=Decimal("50")))
    db.commit()
    order = load_order(db, create_order_from_quote(db, quote.id, order_date=date(2026, 9, 1), execution_start=None, execution_end=None,
                                                   caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None).id)
    db.add_all([
        CalendarEvent(title="Vermietung Müller", start_at=datetime(2026, 11, 3, 8), end_at=datetime(2026, 11, 3, 12), resource_id=kran.id),
        CalendarEvent(title="Betriebsausflug", start_at=datetime(2026, 11, 10), end_at=datetime(2026, 11, 10), all_day=True, owner_user_id=anna.id),
        CalendarEvent(title="Messe", start_at=datetime(2026, 11, 17), end_at=datetime(2026, 11, 19), all_day=True, owner_user_id=anna.id),
    ])
    db.commit()
    return {"anna": k.cookies(anna), "berta": k.cookies(berta), "kran": kran.id, "buehne": buehne.id, "team": team.id, "order": order.id}


def _zeile(adresse):
    return f"[...document.querySelectorAll('#outlookPostfaecher .outlook-postfach')].find(z=>z.textContent.includes('{adresse}'))"


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.browser_uhr_fest(UHR_MS)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")
    await tab.anmelden(seed["anna"])

    # --- Einstellungen ---
    p.pruefe("Einstellungen: geladen", await tab.oeffnen("/settings#outlook-sync", GELADEN), True)
    await tab.warte_auf_ruhe()
    konto = await tab.js(f"{_zeile('anna@x.de')}.textContent")
    p.pruefe("Konto: Name", "Konto: Anna Admin" in konto, True)
    p.pruefe("Konto: letzter Lauf in Berlin", "Letzter Lauf: 14.10.2026 09:45" in konto, True)
    p.pruefe("Konto: kein Fehler", "Letzter Fehler: keiner" in konto, True)
    p.pruefe("Konto: wartet", "Wartet auf Senden: 2" in konto, True)
    p.pruefe("Konto: Weg zur Benutzerseite", await tab.js(f"{_zeile('anna@x.de')}.querySelector('a').getAttribute('href')"), "/users")
    geraet = await tab.js(f"{_zeile('kran@x.de')}.textContent")
    p.pruefe("Gerät: Name", "Gerät: Kran 30 m" in geraet, True)
    p.pruefe("Gerät: Fehler als Satz mit Zeit", "Gruppe ERP-Zugriff" in geraet and "14.10.2026 09:45" in geraet, True)
    p.pruefe("Gerät: Fehler rot gesetzt", await tab.js(f"!!{_zeile('kran@x.de')}.querySelector('.outlook-fehler')"), True)
    p.pruefe("Abschnitt im Bild", await tab.js("document.getElementById('settings-outlook-sync').offsetParent!==null"), True)
    p.pruefe("Zeile zu sehen, nicht nur im Text", await tab.js(f"{_zeile('kran@x.de')}.getBoundingClientRect().height>40"), True)
    p.pruefe("Feld Postfach: die Adresse passt hinein", await tab.js("document.getElementById('outlookGeraetPostfach').getBoundingClientRect().width>=240"), True)
    await tab.bild("einstellungen_hell")

    # zuordnen
    p.pruefe("Auswahl: nur das Gerät ohne Postfach", await tab.js("[...document.getElementById('outlookGeraet').options].map(o=>o.textContent)"), ["— Gerät wählen —", "Hubbühne"])
    await tab.js(f"document.getElementById('outlookGeraet').value='{seed['buehne']}';document.getElementById('outlookGeraetPostfach').value='ANNA@x.de'")
    await tab.js("void geraetPostfachZuordnen()")
    p.pruefe("Adresse eines Kontos: abgelehnt", await tab.warten("document.getElementById('outlookPostfachStatus').textContent.includes('Konto')"), True)
    p.pruefe("Adresse eines Kontos: Meldung nennt es", "anna" in await tab.js("document.getElementById('outlookPostfachStatus').textContent"), True)
    p.pruefe("Eingabe bleibt stehen", await tab.js("document.getElementById('outlookGeraetPostfach').value"), "ANNA@x.de")
    await tab.js("document.getElementById('outlookGeraetPostfach').value='Buehne@X.de'")
    await tab.js("void geraetPostfachZuordnen()")
    p.pruefe("Zugeordnet: neue Zeile, klein geschrieben", await tab.warten(f"!!{_zeile('buehne@x.de')}"), True)
    p.pruefe("Zugeordnet: Gerät nicht mehr wählbar", await tab.js("[...document.getElementById('outlookGeraet').options].map(o=>o.textContent)"), ["— Gerät wählen —"])
    # entfernen
    await tab.js("window.confirm=()=>true")
    await tab.js(f"{_zeile('buehne@x.de')}.querySelector('button').click()")
    p.pruefe("Entfernt: Zeile weg", await tab.warten(f"!{_zeile('buehne@x.de')}"), True)
    p.pruefe("Entfernt: wieder wählbar", await tab.js("[...document.getElementById('outlookGeraet').options].map(o=>o.textContent)"), ["— Gerät wählen —", "Hubbühne"])
    await tab.warte_auf_ruhe()

    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','dark')}catch(e){}")
    await tab.oeffnen("/settings?thema=dunkel#outlook-sync", GELADEN)
    await tab.warte_auf_ruhe()
    await tab.bild("einstellungen_dunkel")
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")

    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen("/settings?breite=412#outlook-sync", GELADEN)
    await tab.warte_auf_ruhe()
    p.pruefe("412 px: läuft nicht über", await tab.ueberlauf(412), [])
    await tab.bild("einstellungen_412")
    await tab.fenster(1440, 1000)

    # --- Rechte ---
    await tab.anmelden(seed["berta"])
    await tab.oeffnen("/settings", "document.querySelector('.settings-menu')")
    p.pruefe("Büro – Auftrag: kein Abschnitt", await tab.js("document.getElementById('settings-outlook-sync')"), None)
    await tab.anmelden(seed["anna"])

    # --- Kalender ---
    await tab.oeffnen("/kalender", "document.querySelector('.month-grid')")
    await tab.warte_auf_ruhe()
    await tab.js("navigate(1)")
    p.pruefe("November", await tab.warten("document.getElementById('periodLabel').textContent.includes('November')&&document.querySelectorAll('.event-chip').length>=3"), True)
    await tab.warte_auf_ruhe()
    tage = "(t=>[...document.querySelectorAll('.month-cell:not(.other-month)')].filter(z=>z.textContent.includes(t)).map(z=>z.querySelector('.day-num').textContent))"
    p.pruefe("Ganztägig: genau ein Tag", await tab.js(f"{tage}('Betriebsausflug')"), ["10"])
    p.pruefe("Dreitägig: genau diese Tage", await tab.js(f"{tage}('Messe')"), ["17", "18", "19"])
    p.pruefe("Termin am Kran: nennt das Gerät", "Kran 30 m" in await tab.js("[...document.querySelectorAll('.event-chip')].find(z=>z.textContent.includes('Vermietung')).textContent"), True)
    await tab.bild("kalender_november")

    await tab.js("openCreate()")
    p.pruefe("Dialog: Kran wählbar", await tab.js("[...document.getElementById('eOwner').options].map(o=>o.textContent)"), ["Anna Admin", "Berta Büro", "Kran 30 m (Gerät)"])
    await tab.js(f"document.getElementById('eTitle').value='Vermietung Schmitz';document.getElementById('eOwner').value='g{seed['kran']}';document.getElementById('eStartDate').value='2026-11-05';document.getElementById('eEndDate').value='2026-11-05'")
    await tab.js("void saveEvent()")
    p.pruefe("Gespeichert am Kran", await tab.warten("events.some(e=>e.title==='Vermietung Schmitz'&&e.resource_name==='Kran 30 m')"), True)
    await tab.warte_auf_ruhe()
    einsatz = await tab.js("events.find(e=>e.title==='Vermietung Schmitz').id")
    await tab.js(f"openEdit({einsatz})")
    p.pruefe("Bearbeiten: Kran vorgewählt", await tab.js("document.getElementById('eOwner').value"), f"g{seed['kran']}")
    await tab.js("closeModal()")

    # --- Plantafel ---
    await tab.oeffnen("/planning", BEREIT)
    await tab.js(f"void openCreate({seed['order']},null,{seed['team']})")
    await tab.warten("document.getElementById('einsatzDialog').open")
    await tab.js("document.getElementById('edVon').value='2026-11-02';document.getElementById('edBis').value='2026-11-04';document.getElementById('edStunden').value='1'")
    await tab.js("void saveNew()")
    p.pruefe("Plantafel: Warnliste", await tab.warten("document.getElementById('edSpeichern').textContent==='Trotzdem planen'"), True)  # seit 1.9.248 im Einsatz-Dialog
    text = await tab.js("[...document.querySelectorAll('#edWarnungen > .conflict-row')].map(x=>x.textContent).join('')")
    p.pruefe("Plantafel: nennt Kran und Termin", "Gerät doppelt: Kran 30 m · Termin: Vermietung Müller" in text, True)
    await tab.bild("plantafel_warnliste")
    await tab.js("document.getElementById('edSpeichern').click()")
    p.pruefe("Plantafel: trotzdem geplant", await tab.warten("!document.getElementById('konfliktDialog').open&&!document.getElementById('einsatzDialog').open"), True)
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-10-14 10:00"))
