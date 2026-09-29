"""Klicktest: Zeitbuchungslisten melden "Liste gekürzt", Summen kommen aus der Datenbank (1.8.9).

Prüft auf acht Seiten, was 1.8.6-1.8.9 gegen stilles Abschneiden von Zeitbuchungen gebaut haben:
Hinweis "Liste gekürzt: X von Y" (Helfer `_time_entries_list.html`) und Summen über
`/api/time-entries/summary` statt aus der gekürzten Liste.

    Büro     Einsatzbericht-Seite (Auftrag A, 501 Buchungen, Liste 500)
             Projektmappe, Reiter Zeiten (Projekt P, 1001 Buchungen, Liste 1000, Kennzahlen)
             Auftragsseite ("Rechnung aus Aufwand" wird angeboten)
             Dashboard ("Meine Stunden (Monat)")
    Admin    Backoffice, Reiter Zeitbuchungen (laufender Monat, über 2000 Buchungen)
             Büro-Zeiterfassung (ein Tag mit 501 Buchungen; "Heute" ohne Hinweis)
    Monteur  Zeiterfassung (Fenster der letzten 14 Tage, über 500 Buchungen), Stundenzettel
             (Vormonat, über 2000 Buchungen), in Handybreite

Die Buchungen liegen relativ zum heutigen Datum (laufender Monat, Vormonat, letzte 14 Tage), die
erwarteten Zahlen rechnet befuellen() aus dem angelegten Datensatz aus -- das Skript läuft also in
jedem Monat. Die älteste Buchung (2,5 Std. Fahrzeit der Monteurin auf Auftrag A) fällt an jeder
Grenze als erste aus der Liste.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_zeitbuchungen_liste.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def _anzahl(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def befuellen(db, k):
    from datetime import date, datetime, timedelta, timezone
    from decimal import Decimal

    from app.models import AppUser, Customer, Employee, Order, OrderItem, Project, TimeEntry
    from app.project_pipeline_columns import default_pipeline_column_id

    heute = date.today()
    heute_utc = datetime.now(timezone.utc).date()  # die Monteur-Seite bildet ihr Fenster in UTC
    monat = heute.replace(day=1)
    vormonat = (monat - timedelta(days=1)).replace(day=1)
    im_monat = lambda i: monat + timedelta(days=i % 28)        # noqa: E731 -- 1.-28., in jedem Monat vorhanden
    im_vormonat = lambda i: vormonat + timedelta(days=i % 28)  # noqa: E731
    anna_tag = next(monat + timedelta(days=i) for i in range(28) if monat + timedelta(days=i) not in (heute, heute_utc))

    col = default_pipeline_column_id(db)
    kunde = Customer(name="Klicktest Kunde", last_name="Klicktest Kunde")
    db.add(kunde); db.flush()
    p, q, r = (Project(project_number=f"P-KT-000{i}", name=n, customer_id=kunde.id, pipeline_column_id=col)
               for i, n in ((1, "Projekt Grenze+1"), (2, "Projekt Q"), (3, "Projekt Monteurin")))
    db.add_all([p, q, r]); db.flush()

    def auftrag(nummer, projekt, quelle):
        o = Order(order_number=nummer, project_id=projekt.id, source_quote_id=quelle, quote_number_snapshot="A-" + nummer,
                  title="Auftrag " + nummer, customer_name="Klicktest Kunde", customer_number="K-1")
        db.add(o); db.flush()
        db.add(OrderItem(order_id=o.id, sort_order=10, position_number="1", short_text="Dacheindeckung",
                         quantity=Decimal("10"), unit="m²", unit_price=Decimal("50")))
        return o

    a, b, c, d = auftrag("AUF-KT-A", p, 1), auftrag("AUF-KT-B", p, 2), auftrag("AUF-KT-C", q, 3), auftrag("AUF-KT-D", r, 4)
    ma = {}
    for key, nr, vor, nach, gruppe in (("anna", "E-1", "Anna", "Admin", "angestellt"), ("karl", "E-2", "Karl", "Kollege", "gewerblich"),
                                       ("mia", "E-3", "Mia", "Monteurin", "gewerblich")):
        ma[key] = Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group=gruppe, active=True, hourly_wage=Decimal("22.00"))
    db.add_all(ma.values()); db.flush()
    benutzer = {
        "anna": AppUser(username="anna", display_name="Anna Admin", role="admin", employee_id=ma["anna"].id, password_hash=k.passwort()),
        "buero": AppUser(username="buero", display_name="Karl Kollege", role="buero_auftrag", employee_id=ma["karl"].id, password_hash=k.passwort()),
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=ma["mia"].id, password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()

    def te(emp, o, day, hours="1.00", entry_type="site", status="booked"):
        return TimeEntry(employee_id=ma[emp].id, project_id=o.project_id, order_id=o.id, work_date=day, entry_type=entry_type,
                         counts_as_productive=entry_type != "travel", hours=Decimal(hours), status=status, source="manual")

    rows = [te("mia", a, monat - timedelta(days=1), "2.50", "travel")]                          # älteste an A und P
    rows += [te("karl", a, im_monat(i)) for i in range(499)] + [te("karl", a, monat + timedelta(days=27), "0", status="running")]
    rows += [te("karl", b, im_monat(i)) for i in range(500)]                                     # P: 1001
    rows += [te("karl", c, im_monat(i)) for i in range(499)]                                     # Karl im Monat: 1498 Std.
    rows += [te("mia", d, heute_utc - timedelta(days=i % 15)) for i in range(501)]               # letzte 14 Tage
    rows += [te("mia", d, im_vormonat(i)) for i in range(2001)]                                  # Vormonat
    rows += [te("anna", d, anna_tag) for _ in range(501)]                                        # ein Tag
    db.add_all(rows); db.commit()

    monatsende = (monat + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    zaehle = lambda bed: sum(1 for x in rows if bed(x))  # noqa: E731
    return {
        "orders": {"A": a.id}, "projects": {"P": p.id}, "employees": {"anna": ma["anna"].id},
        "cookies": {name: k.cookies(u) for name, u in benutzer.items()},
        "anna_tag": anna_tag.isoformat(), "vormonat": vormonat.strftime("%Y-%m"),
        "karl_monat_stunden": sum(x.hours for x in rows if x.employee_id == ma["karl"].id and monat <= x.work_date <= monatsende),
        "backoffice_monat": zaehle(lambda x: monat <= x.work_date <= monatsende),
        "monteurin_14_tage": zaehle(lambda x: x.employee_id == ma["mia"].id and heute_utc - timedelta(days=14) <= x.work_date <= heute_utc),
        "monteurin_vormonat": zaehle(lambda x: x.employee_id == ma["mia"].id and vormonat <= x.work_date < monat),
    }


NOTICE = "(document.querySelector({sel})?.querySelector('.time-entries-truncated')?.textContent||'')"


def _gekuerzt(gezeigt: int, gesamt: int, zusatz: str = "") -> str:
    return f"Liste gekürzt: {_anzahl(gezeigt)} von {_anzahl(gesamt)} Buchungen angezeigt, die ältesten fehlen." + (f" {zusatz}" if zusatz else "")


async def pruefen(tab, seed, p):
    import asyncio

    a, pr = seed["orders"]["A"], seed["projects"]["P"]
    assert seed["backoffice_monat"] > 2000 and seed["monteurin_14_tage"] > 500 and seed["monteurin_vormonat"] > 2000, seed

    await tab.anmelden(seed["cookies"]["buero"])
    await tab.oeffnen(f"/orders/{a}/service-reports", "document.querySelector('#timeEntriesTable table, #timeEntriesTable .status, #timeEntriesTable .empty')")
    await tab.js("document.getElementById('timeEntriesTable').scrollIntoView()")
    p.pruefe("Einsatzbericht: Hinweis", await tab.js(NOTICE.format(sel="'#timeEntriesTable'")),
             _gekuerzt(500, 501, "Die Gesamtsumme enthält alle Buchungen."))
    p.pruefe("Einsatzbericht: Zeilen", await tab.js("document.querySelectorAll('#timeEntriesTable tbody tr').length - 1"), 500)
    p.pruefe("Einsatzbericht: Gesamt", await tab.js("[...document.querySelectorAll('#timeEntriesTable tbody tr')].pop().lastElementChild.textContent.trim()"), "501,50 h")
    p.pruefe("Einsatzbericht: JS-Fehler", tab.fehler, [])
    await tab.bild("einsatzbericht")

    await tab.oeffnen(f"/projects/{pr}", "document.getElementById('kHours')?.textContent.includes('h')")
    await tab.js("document.querySelector('[data-tab=\"sec-times\"], [onclick*=\"sec-times\"]')?.click()")
    await asyncio.sleep(0.3)
    p.pruefe("Projektmappe: Hinweis", await tab.js(NOTICE.format(sel="'#timeTruncated'")),
             _gekuerzt(1000, 1001, "Kennzahlen und Summen enthalten alle Buchungen."))
    p.pruefe("Projektmappe: Kennzahlen", await tab.js("[...document.querySelectorAll('#timeSummary .metric .v')].map(x=>x.textContent)"),
             ["999,00 h", "2,50 h", "1.001,50 h", "2"])
    p.pruefe("Projektmappe: Ist-Stunden (Kopf)", await tab.js("document.getElementById('kHours').textContent"), "999,00 h")
    p.pruefe("Projektmappe: Reiterzahl", await tab.js("document.getElementById('tabCountTimes').textContent"), "1001")
    p.pruefe("Projektmappe: Tabellenzeilen", await tab.js("document.querySelectorAll('#timeRows tr').length"), 999)
    p.pruefe("Projektmappe: JS-Fehler", tab.fehler, [])
    await tab.bild("projektmappe")

    await tab.oeffnen(f"/orders/{a}", "document.querySelector('#newInvoiceType option')")
    p.pruefe("Auftrag: Rechnung aus Aufwand", await tab.js("!!document.querySelector('#newInvoiceType option[value=\"aufwand\"]')"), True)
    p.pruefe("Auftrag: JS-Fehler", tab.fehler, [])

    await tab.oeffnen("/", "[...document.querySelectorAll('.metric small')].some(x=>x.textContent.includes('Meine Stunden'))")
    stunden = f"{float(seed['karl_monat_stunden']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " h"
    p.pruefe("Dashboard: Meine Stunden", await tab.js("[...document.querySelectorAll('.metric')].find(m=>m.querySelector('small')?.textContent.includes('Meine Stunden'))?.querySelector('b')?.textContent"), stunden)
    p.pruefe("Dashboard: JS-Fehler", tab.fehler, [])
    await tab.bild("dashboard")

    await tab.anmelden(seed["cookies"]["anna"])
    await tab.oeffnen("/time-backoffice", "document.querySelectorAll('#entryRows tr').length>1 || document.body.innerText.includes('Fehler')")
    await tab.js("typeof showTab==='function'&&showTab('entries')")
    await asyncio.sleep(0.3)
    p.pruefe("Backoffice: Hinweis", await tab.js(NOTICE.format(sel="'#entriesTruncated'")),
             _gekuerzt(2000, seed["backoffice_monat"], "Stundenübersicht, Stundenzettel und Exporte enthalten alle Buchungen."))
    p.pruefe("Backoffice: Zeilen", await tab.js("document.querySelectorAll('#entryRows tr').length"), 2000)
    p.pruefe("Backoffice: JS-Fehler", tab.fehler, [])
    await tab.bild("backoffice")

    anna = seed["employees"]["anna"]
    await tab.oeffnen(f"/time-tracking?employee_id={anna}", f"document.getElementById('employee')?.value=='{anna}' && document.getElementById('historyEntries')?.children.length>0")
    await tab.js(f"document.getElementById('historyDate').value='{seed['anna_tag']}'; loadEntries()")
    await tab.warten(f"(document.querySelector('#historyEntries .time-entries-truncated')?.textContent||'').includes('501')", 10)
    p.pruefe("Zeiterfassung Büro: Hinweis Tag", await tab.js(NOTICE.format(sel="'#historyEntries'")), _gekuerzt(500, 501))
    p.pruefe("Zeiterfassung Büro: Hinweis heute (keiner)", await tab.js(NOTICE.format(sel="'#todayEntries'")), "")
    p.pruefe("Zeiterfassung Büro: JS-Fehler", tab.fehler, [])
    await tab.bild("zeiterfassung_buero")

    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(390, 844, mobil=True)
    await tab.oeffnen("/time-tracking", "document.getElementById('entriesList')?.children.length>0")
    p.pruefe("Monteurin Zeiterfassung: Hinweis", await tab.js(NOTICE.format(sel="'#entriesList'")), _gekuerzt(500, seed["monteurin_14_tage"]))
    p.pruefe("Monteurin Zeiterfassung: JS-Fehler", tab.fehler, [])
    await tab.js("document.getElementById('entriesList').scrollIntoView()")
    await tab.bild("monteurin_zeiterfassung")
    await tab.oeffnen("/mobil/stundenzettel", "!document.getElementById('entriesArea').classList.contains('loading')")
    await tab.js(f"document.getElementById('monthInput').value='{seed['vormonat']}'; loadMonth('{seed['vormonat']}')")
    await tab.warten("(document.querySelector('#entriesArea .time-entries-truncated')?.textContent||'').includes('2.000')", 15)
    p.pruefe("Monteurin Stundenzettel: Hinweis", await tab.js(NOTICE.format(sel="'#entriesArea'")), _gekuerzt(2000, seed["monteurin_vormonat"]))
    p.pruefe("Monteurin Stundenzettel: JS-Fehler", tab.fehler, [])
    await tab.bild("monteurin_stundenzettel")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
