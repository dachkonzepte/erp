"""Klicktest: die Büroseite „Zeiten“ (seit 1.9.96, Stufe 4, R5b) -- Prüfen, Buchungen, Buchung ändern/neu, Löschen.

Befüllt (stehende Uhr Mo 26.10.2026, 10:00, Instanz und Browser; abgeschlossen bis 30.09.2026), Testdaten wie die Vorlagen
bildgrundlage/entwurf-stufe4/zeiten-*.html: Aufträge AUF-2026-0001 „Halle Nord“, AUF-2026-0102 „Attika“, AUF-2026-0105 „Halle Süd“
(abgeschlossen); Tom Monteur Baustelle seit Mo 19.10., 06:45 offen, Ole Offen Fahrzeit seit Fr 16.10., 15:30 offen; Mia Monteurin am
Sa 10.10. ein Tag mit unpassender Pause (12:00–16:15, 45 min abgezogen, nach Zeitregel 0), am 19.10. 07:00–12:00 und 12:00–16:15, am
15.10. eine Dauer von 6,00 h (vom Büro); Tom am 15.10. 06:15–07:00 Fahrzeit und 07:00–16:30 Baustelle (Attika), am 16.10. 07:00–15:45 auf
dem abgeschlossenen Auftrag; Toms Antrag Urlaub 02.–06.11. offen.

    Admin, hell 1440 × 900  Prüfen: Zahl am Reiter 3; „Zeiten von früher“ mit Tom und Ole; Ende um 16:00 -> Vorschau „anwesend 9:15 h ·
                            Pause nach Zeitregel − 0:45 h · gebucht 8,50 h“, Ole ohne Uhrzeit „Ende eintragen“ gesperrt; „Pause passt
                            nicht“ mit Vorschau; Anträge mit Genehmigen/Ablehnen; Monat Oktober 2026 und „Vor dem Abschluss“ -- Bild;
                            „Ende eintragen“ = Vorschau (gebucht 8,50 h, 45 min); „So buchen“ = Vorschau (0 min, 4,25 h)
    Büro – Finanzen         Buchungen: Spalten, „von früher“ mit „Ende eintragen“ (springt zu Prüfen, Fokus im Feld), abgeschlossener Auftrag
                            gekennzeichnet, „Dauer · vom Büro“; Filter Mitarbeiter, Auftrag, Zeitart ändern Liste und „Summe der Auswahl“
                            (= Summe der gezeigten gebuchten Zeilen, die laufende zählt nicht); Ändern mit Von–Bis: Vorschau „Anwesend 9:30
                            h · Tag zusammen 10:15 h · Pause nach Zeitregel − 0:45 h“, Knopf „8,75 h speichern“ -- Bild; Bis 16:00 -> 8,25 h
                            gespeichert; Wechsel zu „Dauer“: Von/Bis leer, Hinweis, 8,00 h gespeichert, Beginn und Ende leer (API); „+ Buchung“
                            für Mia 07:00–11:00 -> 4,00 h; Löschen mit Rückfrage auf der Seite (kein confirm())
    Büro – Auftrag          Prüfen und Buchungen ohne Knöpfe (kein „Ende um“, kein „So buchen“, kein „⋮“, kein „+ Buchung“), seit 1.9.102
                            „Zur Info“ statt „Wartet auf dich“ mit dem Satz, wer das Ende einträgt, keine Zahl am Reiter „Prüfen“ -- Bild; seit
                            1.9.98 aus klicktest_backoffice_buero (das Backoffice gibt es nicht mehr): keine Anfrage an Buchungskontext und
                            Personalnummern, Stundenzettel PDF, CSV und DATEV-Export vom Server 403
    dunkel                  Prüfen und Buchungen; Farbpunkte der Zeitarten aus den Tokens (hell und dunkel verschieden) -- Bilder
    Kolonne (seit 1.9.97)   Büro – Finanzen über „⋮ Kolonne buchen“: Kolonne 1 mit Mia und Tom, 07:00–12:00 -> Vorschau je Person, „Für 2
                            Personen speichern“, beide Buchungen in der Liste
    Abwesenheiten           Admin genehmigt Toms Antrag mit Notiz (Zahl am Reiter weg); Büro – Auftrag beantragt für sich (ohne Feld
                            Mitarbeiter), zieht mit Rückfrage zurück, kein Reiter „Monat & Lohn“ (API 403), für Tom vom Server 403; seit 1.9.101
                            Büro – Finanzen ohne eigenen Mitarbeiter: alle Anträge, „Krank“ für Tom mit „beantragt von“ -- Bild --, entscheiden 403,
                            zieht ihn zurück
    Monat & Lohn            Büro – Finanzen: Lücke (Oles laufende Zeit) -> „Abschließen“ gesperrt, „Fehlt: 1 laufende Zeit“, was DATEV fehlt
                            getrennt bei „DATEV-Export“, DATEV gesperrt -- Bild; Ole geschlossen -> „Abschließen“ frei; eine neue Lücke nach dem
                            Laden -> abgelehnt (409), die Liste auf der Seite; ohne Lücke abgeschlossen; DATEV erst mit Lohnart und
                            Personalnummer -> Datei; seit 1.9.98 (aus klicktest_backoffice_buero): im abgeschlossenen Oktober keine
                            Buchung mit „⋮“, Stundenzettel PDF und CSV 200, im „⋮“ des Kopfs kein „Abschluss aufheben“, zurücknehmen vom
                            Server 403; Admin hebt den Abschluss über „⋮“ auf (zurück auf 30.09.2026)
    412 px                  ohne waagrechte Scrollleiste der Seite

Die Bilder (zeiten_*.png) liegen im Ordner der Screenshots.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_zeiten.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD]
        [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date, datetime, time
    from decimal import Decimal

    from app.models import (AppUser, Customer, Employee, EmployeeAbsenceRequest, EmployeePayrollSettings, Order, OrderItem, Project, Property, Team,
                            TeamEmployee, TimeTrackingSettings)
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.time_tracking import create_manual_entry, delete_entry, start_timer, stop_timer

    leute = {}
    for nr, (vor, nach, gruppe) in enumerate([("Mia", "Monteurin", "gewerblich"), ("Tom", "Monteur", "gewerblich"), ("Ole", "Offen", "gewerblich"),
                                              ("Bea", "Büro", "angestellt")], 1):
        leute[vor.lower()] = Employee(employee_number=f"100{nr}", first_name=vor, last_name=nach, employee_group=gruppe, active=True,
                                      hourly_wage=Decimal("22.00"))
    db.add_all(leute.values()); db.flush()
    admin = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", employee_id=leute["bea"].id, password_hash=k.passwort())
    # seit 1.9.104: Toms Konto (Monteursansicht) -- seine Zeit am 15.10. bucht er selbst (Verlauf für die Unterzeile des Dialogs)
    tom_konto = AppUser(username="tom", display_name="Tom Monteur", role="field", employee_id=leute["tom"].id, password_hash=k.passwort())
    db.add_all([admin, fin, bea, tom_konto]); db.flush()
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    auftraege = {}
    for nr, (nummer, titel, status) in enumerate([("AUF-2026-0001", "Halle Nord", "beauftragt"), ("AUF-2026-0102", "Attika", "beauftragt"),
                                                  ("AUF-2026-0105", "Halle Süd", "abgeschlossen")], 1):
        objekt = Property(customer_id=kunde.id, name=titel, street="Werkstr. 5", postal_code="52531", city="Übach-Palenberg")
        db.add(objekt); db.flush()
        projekt = Project(project_number=f"P-ZT-{nr}", name=titel, customer_id=kunde.id, property_id=objekt.id,
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        o = Order(order_number=nummer, project_id=projekt.id, source_quote_id=900 + nr, quote_number_snapshot=f"A-ZT-{nr}", title=titel,
                  customer_name=kunde.name, property_name=titel, property_address="Werkstr. 5\n52531 Übach-Palenberg", status=status)
        db.add(o); db.flush()
        db.add(OrderItem(order_id=o.id, sort_order=10, position_number="1", short_text="Dacharbeiten", quantity=Decimal("1"), unit="psch",
                         unit_price=Decimal("1")))
        auftraege[titel] = o
    einstellungen = db.get(TimeTrackingSettings, 1)
    einstellungen.locked_until = date(2026, 9, 30)
    # DATEV: Lohnart für Baustelle und Fahrzeit, nicht für Werkstatt; Personalnummern für Mia und Tom, nicht für Ole; Berater und Mandant
    einstellungen.datev_target = "lohn_gehalt"
    einstellungen.datev_wage_type_site, einstellungen.datev_wage_type_travel = "100", "200"
    einstellungen.datev_beraternummer, einstellungen.datev_mandantennummer = "12345", "678"
    for wer, nummer in (("mia", "1001"), ("tom", "1002"), ("ole", None)):
        db.add(EmployeePayrollSettings(employee_id=leute[wer].id, datev_personnel_number=nummer, payroll_export_enabled=True))
    kolonne = Team(name="Kolonne 1", team_number="K-1", active=True)
    db.add(kolonne); db.flush()
    db.add_all([TeamEmployee(team_id=kolonne.id, employee_id=leute["mia"].id, is_crew_leader=True),
                TeamEmployee(team_id=kolonne.id, employee_id=leute["tom"].id)])
    db.commit()

    def zeit(wer, tag, von, bis, auftrag, art="site"):
        row = start_timer(db, employee_id=leute[wer].id, order_id=auftraege[auftrag].id, entry_type=art, started_at=datetime.combine(tag, von))
        return stop_timer(db, row.id, ended_at=datetime.combine(tag, bis))

    # Mia, Sa 10.10.: 07:00–12:00 und 12:00–16:15 (45 min), die erste gelöscht -- abgezogen 45, nach Zeitregel 0
    erste = zeit("mia", date(2026, 10, 10), time(7), time(12), "Halle Nord")
    pause_tag = zeit("mia", date(2026, 10, 10), time(12), time(16, 15), "Halle Nord")
    delete_entry(db, erste.id)
    zeit("mia", date(2026, 10, 19), time(7), time(12), "Halle Nord")
    zeit("mia", date(2026, 10, 19), time(12), time(16, 15), "Halle Nord", art="workshop")
    dauer = create_manual_entry(db, employee_id=leute["mia"].id, order_id=auftraege["Attika"].id, work_date=date(2026, 10, 15), entry_type="site",
                                hours=Decimal("6"), break_minutes=30, created_by_user_id=fin.id)
    zeit("tom", date(2026, 10, 15), time(6, 15), time(7), "Attika", art="travel")
    # Toms Baustelle am 15.10. bucht er selbst, beendet um 16:31 Berlin (14:31 UTC) wie die Vorlage zeiten-aendern.html: der Verlauf mit Konto
    # und Pfad wie in der Anwendung, sein Zeitpunkt auf den 15.10. gesetzt (sonst der Zeitpunkt des Klicktests)
    from types import SimpleNamespace

    from sqlalchemy import update

    from app.audit import reset_audit_context, set_audit_context
    from app.models import AuditLog
    marke = set_audit_context(user=tom_konto, request=SimpleNamespace(url=SimpleNamespace(path="/api/time-entries/start"), method="POST"))
    try:
        attika = start_timer(db, employee_id=leute["tom"].id, order_id=auftraege["Attika"].id, entry_type="site",
                             started_at=datetime(2026, 10, 15, 7, 0), created_by_user_id=tom_konto.id)
    finally:
        reset_audit_context(marke)
    marke = set_audit_context(user=tom_konto, request=SimpleNamespace(url=SimpleNamespace(path=f"/api/time-entries/{attika.id}/stop"), method="POST"))
    try:
        attika = stop_timer(db, attika.id, ended_at=datetime(2026, 10, 15, 16, 30))
    finally:
        reset_audit_context(marke)
    db.execute(update(AuditLog).where(AuditLog.entity_type == "Zeitbuchung", AuditLog.entity_id == str(attika.id))
               .values(occurred_at=datetime(2026, 10, 15, 14, 31)))
    zeit("tom", date(2026, 10, 16), time(7), time(15, 45), "Halle Süd")
    tom = start_timer(db, employee_id=leute["tom"].id, order_id=auftraege["Halle Nord"].id, entry_type="site",
                      started_at=datetime(2026, 10, 19, 6, 45))
    ole = start_timer(db, employee_id=leute["ole"].id, order_id=auftraege["Halle Süd"].id, entry_type="travel",
                      started_at=datetime(2026, 10, 16, 15, 30))
    db.add(EmployeeAbsenceRequest(employee_id=leute["tom"].id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2026, 11, 2),
                                  end_date=date(2026, 11, 6), status="pending", created_at=datetime(2026, 10, 20, 7, 0)))
    db.commit()
    return {"uhr_ms": k.uhr_ms(), "admin": k.cookies(admin), "fin": k.cookies(fin), "bea": k.cookies(bea), "tom": tom.id, "ole": ole.id,
            "pause_tag": pause_tag.id, "attika": attika.id, "dauer": dauer.id, "mia": leute["mia"].id, "tom_ma": leute["tom"].id,
            "halle_nord": auftraege["Halle Nord"].id, "attika_auftrag": auftraege["Attika"].id, "ole_ma": leute["ole"].id,
            "kolonne": kolonne.id}


BEREIT = "!!window.P&&document.getElementById('monatTitel').textContent!==''"
BUCHUNGEN_BEREIT = "!!window.B&&!document.getElementById('reiter-buchungen').hidden"


def _zeilen():
    return ("[...document.querySelectorAll('#buchungenZeilen tr')].map(tr=>[...tr.cells].slice(0,7).map(c=>c.innerText.replace(/\\s+/g,' ').trim()))")


async def _seite(tab, seed, wer, thema="light", breite=1440, hoehe=900, hash=""):
    await tab.anmelden(seed[wer])
    await tab.fenster(breite, hoehe)
    await tab.browser_uhr_fest(seed["uhr_ms"])
    await tab.oeffnen("/zeiten", BEREIT)
    await tab.js(f"localStorage.setItem('erp_theme','{thema}')")
    return await tab.oeffnen(f"/zeiten?neu=1{hash}", BEREIT)


async def _buchungen(tab):
    await tab.js("document.querySelector('.reiter a[data-reiter=buchungen]').click()")
    return await tab.warten(BUCHUNGEN_BEREIT + "&&document.querySelectorAll('#buchungenZeilen tr').length>0", 10)


async def _exporte(tab):
    """Stundenzettel PDF und CSV und DATEV-Export für Oktober 2026 (seit 1.9.98 aus klicktest_backoffice_buero) -- den Körper lesen: sonst
    hält Chrome die Anfrage offen."""
    return await tab.js("Promise.all(['timesheet.pdf','timesheet.csv','datev-export'].map(x=>fetch('/api/time-backoffice/'+x+"
                        "'?start_date=2026-10-01&end_date=2026-10-31').then(r=>r.arrayBuffer().then(()=>r.status))))")


async def _api(tab, url):
    return await tab.js(f"fetch('{url}').then(r=>r.json())")


async def _menue(tab, entry_id, aktion):
    await tab.js(f"document.querySelector('#buchungenZeilen tr[data-buchung=\"{entry_id}\"] .menue-anker button').click()")
    await tab.js(f"document.querySelector('[data-aktion=\"{aktion}\"][data-id=\"{entry_id}\"]').click()")


async def _eingeben(tab, feld, wert):
    await tab.js(f"(()=>{{const f=document.getElementById('{feld}');f.value='{wert}';f.dispatchEvent(new Event('input',{{bubbles:true}}));"
                 f"f.dispatchEvent(new Event('change',{{bubbles:true}}))}})()")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=m=>{console.error('confirm(): '+m);return false};")

    # ---- Admin: Prüfen -----------------------------------------------------------------------------------------------------------
    p.pruefe("Admin: Prüfen geladen", await _seite(tab, seed, "admin"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Admin: Zahl am Reiter Prüfen", await tab.js("document.getElementById('zahlPruefen').innerText"), "3")
    p.pruefe("Admin: „Wartet auf dich“ (Signalkarte)", await tab.js(
        "[document.getElementById('offenKarte').className,document.getElementById('offenEbText').textContent]"), ["karte-signal", "Wartet auf dich"])
    p.pruefe("Admin: Zeiten von früher (Name, Zeile)", await tab.js(
        "[...document.querySelectorAll('#offenListe .zeile')].map(z=>[z.querySelector('.zeile-name').innerText,z.querySelector('.zeile-unter').innerText])"),
        [["Ole Offen", "Fahrzeit seit Fr 16.10., 15:30 · AUF-2026-0105 · Halle Süd (Auftrag abgeschlossen)"],
         ["Tom Monteur", "Baustellenzeit seit Mo 19.10., 06:45 · AUF-2026-0001 · Halle Nord"]])
    await _eingeben(tab, f"ende-{seed['tom']}", "16:00")
    p.pruefe("Admin: Vorschau Ende um 16:00", await tab.warten(
        f"document.getElementById('ende-vorschau-{seed['tom']}').innerText.includes('gebucht')", 10), True)
    p.pruefe("Admin: Vorschau-Zeile und Knöpfe (Tom frei, Ole ohne Uhrzeit gesperrt)", await tab.js(
        f"[document.getElementById('ende-vorschau-{seed['tom']}').innerText,"
        f"document.querySelector('[data-aktion=ende][data-id=\"{seed['tom']}\"]').disabled,"
        f"document.querySelector('[data-aktion=ende][data-id=\"{seed['ole']}\"]').disabled]"),
        ["anwesend 9:15 h · Pause nach Zeitregel − 0:45 h · gebucht 8,50 h", False, True])
    p.pruefe("Admin: Pause passt nicht -- Zeile und Vorschau", await tab.js(
        "[document.querySelector('#pauseListe .zeile-name').innerText,document.querySelector('#pauseListe .zeile-unter').innerText,"
        "document.querySelector('#pauseListe .neu-rechnen-text').innerText.replace(/\\s+/g,' ')]"),
        ["Mia Monteurin · Sa 10.10.", "Pause abgezogen 0:45 h · nach Zeitregel 0:00 h",
         "Neu rechnen: Baustellenzeit 12:00–16:15 · Pause 0:45 → 0:00 h · gebucht 3,50 → 4,25 h"])
    p.pruefe("Admin: Anträge mit Genehmigen und Ablehnen", await tab.js(
        "[document.querySelector('#antragListe .zeile-name').innerText,document.querySelector('#antragListe .zeile-unter').innerText,"
        "[...document.querySelectorAll('#antragListe button')].map(b=>b.innerText)]"),
        ["Tom Monteur · Urlaub", "Mo 02.11.–Fr 06.11.2026 · 5 Arbeitstage · beantragt am 20.10.", ["Ablehnen", "Genehmigen"]])
    p.pruefe("Admin: Monat rechts", await tab.js(
        "[document.getElementById('monatTitel').innerText,document.getElementById('monatStatus').innerText,"
        "[...document.querySelectorAll('#monatZeilen tr')].map(tr=>tr.innerText.replace(/\\s+/g,' ').trim())]"),
        ["Oktober 2026", "offen", ["Mia Monteurin 3 18,00", "Tom Monteur 2 17,75", "Zusammen 35,75"]])  # Ole nur laufend: nicht in der Liste
    p.pruefe("Admin: Vor dem Abschluss", await tab.js("[...document.querySelectorAll('#abschlussListe li')].slice(0,2).map(l=>l.innerText)"),
             ["2 Zeiten laufen noch", "1 Tag mit unpassender Pause"])
    p.pruefe("Admin: keine waagrechte Scrollleiste bei 1440", await tab.js("document.documentElement.scrollWidth<=window.innerWidth+1"), True)
    await tab.bild("zeiten_pruefen_hell")

    await tab.js(f"document.querySelector('[data-aktion=ende][data-id=\"{seed['tom']}\"]').click()")
    p.pruefe("Admin: Ende eingetragen -- die Zeile ist weg", await tab.warten(f"!document.querySelector('[data-offen=\"{seed['tom']}\"]')", 10), True)
    tom = await _api(tab, "/api/zeiten/buchungen?monat=2026-10&mitarbeiter=" + str(seed["tom_ma"]))
    gebucht = [e for e in tom["eintraege"] if e["id"] == seed["tom"]][0]
    p.pruefe("Admin: Ende eintragen = Vorschau (16:00, 45 min, 8,50 h)", [gebucht["ended_at"], gebucht["break_minutes"], float(gebucht["hours"])],
             ["2026-10-19T16:00:00", 45, 8.5])
    p.pruefe("Admin: Meldung", await tab.js("document.getElementById('ergebnis').innerText"),
             "Ende eingetragen: Tom Monteur, Mo 19.10. 06:45–16:00 · gebucht 8,50 h")
    await tab.js("document.querySelector('[data-aktion=pause-buchen]').click()")
    p.pruefe("Admin: So buchen -- der Tag ist weg", await tab.warten("document.getElementById('pauseKarte').hidden", 10), True)
    mia = await _api(tab, "/api/zeiten/buchungen?monat=2026-10&mitarbeiter=" + str(seed["mia"]))
    tag = [e for e in mia["eintraege"] if e["id"] == seed["pause_tag"]][0]
    p.pruefe("Admin: So buchen = Vorschau (0 min, 4,25 h)", [tag["break_minutes"], float(tag["hours"])], [0, 4.25])
    p.pruefe("Admin: Zahl am Reiter jetzt 1", await tab.js("document.getElementById('zahlPruefen').innerText"), "1")
    p.pruefe("Admin: keine JS-Fehler", tab.fehler, [])

    # ---- Büro – Finanzen: Buchungen, Dialog --------------------------------------------------------------------------------------------
    p.pruefe("Fin: Seite geladen", await _seite(tab, seed, "fin"), True)
    p.pruefe("Fin: Buchungen geladen", await _buchungen(tab), True)
    zeilen = await tab.js(_zeilen())
    # seit 1.9.103 (Nachrunde, Punkt 2) die Reihenfolge der Vorlage: Datum absteigend, im Tag nach Mitarbeiter, Von aufsteigend, Dauer zuletzt
    # (bis 1.9.102 die neuesten zuerst: am 15.10. Tom 07:00, Tom 06:15, Mia Dauer)
    p.pruefe("Fin: Zeilen wie die Vorlage (Ausschnitt)", [z for z in zeilen if z[0] in ("Mo 19.10.", "Fr 16.10.", "Do 15.10.")], [
        ["Mo 19.10.", "Mia Monteurin", "07:00–12:00", "Baustellenzeit", "AUF-2026-0001 · Halle Nord", "0:00", "5,00"],
        ["Mo 19.10.", "Mia Monteurin", "12:00–16:15", "Werkstattzeit", "AUF-2026-0001 · Halle Nord", "0:45", "3,50"],
        ["Mo 19.10.", "Tom Monteur", "06:45–16:00", "Baustellenzeit", "AUF-2026-0001 · Halle Nord", "0:45", "8,50"],
        ["Fr 16.10.", "Ole Offen", "15:30 – läuft von früher", "Fahrzeit", "AUF-2026-0105 · Halle Süd abgeschlossen", "—", "—"],
        ["Fr 16.10.", "Tom Monteur", "07:00–15:45", "Baustellenzeit", "AUF-2026-0105 · Halle Süd abgeschlossen", "0:30", "8,25"],
        ["Do 15.10.", "Mia Monteurin", "Dauer · vom Büro", "Baustellenzeit", "AUF-2026-0102 · Attika", "0:30", "6,00"],
        ["Do 15.10.", "Tom Monteur", "06:15–07:00", "Fahrzeit", "AUF-2026-0102 · Attika", "0:00", "0,75"],
        ["Do 15.10.", "Tom Monteur", "07:00–16:30", "Baustellenzeit", "AUF-2026-0102 · Attika", "0:45", "8,75"]])

    async def summe():
        return await tab.js("[document.getElementById('summeAuswahl').innerText,"
                            "[...document.querySelectorAll('#buchungenZeilen tr')].map(tr=>tr.cells[6].innerText).filter(t=>t!=='—')"
                            ".reduce((s,t)=>s+Number(t.replace(',','.')),0).toFixed(2).replace('.',',')+' h',"
                            "document.querySelectorAll('#buchungenZeilen tr').length]")
    alle = await summe()
    p.pruefe("Fin: Summe der Auswahl = gezeigte gebuchte Zeilen (die laufende zählt nicht)", [alle[0] == alle[1], alle[0], alle[2]],
             [True, "45,00 h", 9])
    await tab.warte_auf_neu_geladene_liste(f"(()=>{{const s=document.getElementById('filterMitarbeiter');s.value='{seed['tom_ma']}';"
                                          "s.dispatchEvent(new Event('change',{bubbles:true}))})()", "#buchungenZeilen")
    nur_tom = await summe()
    p.pruefe("Fin: Filter Mitarbeiter Tom -- Liste und Summe", [nur_tom[0] == nur_tom[1], nur_tom[0], nur_tom[2],
             await tab.js("[...document.querySelectorAll('#buchungenZeilen tr')].every(tr=>tr.cells[1].innerText==='Tom Monteur')")],
             [True, "26,25 h", 4, True])
    await tab.warte_auf_neu_geladene_liste("(()=>{const s=document.getElementById('filterZeitart');s.value='travel';"
                                          "s.dispatchEvent(new Event('change',{bubbles:true}))})()", "#buchungenZeilen")
    p.pruefe("Fin: Filter Mitarbeiter und Zeitart Fahrzeit", (await summe())[0::2], ["0,75 h", 1])
    await tab.warte_auf_neu_geladene_liste(f"(()=>{{for(const [i,v] of [['filterMitarbeiter',''],['filterZeitart',''],['filterAuftrag','{seed['attika_auftrag']}']])"
                                          "document.getElementById(i).value=v;document.getElementById('filterAuftrag').dispatchEvent(new Event('change',{bubbles:true}))})()",
                                          "#buchungenZeilen")
    p.pruefe("Fin: Filter Auftrag Attika", (await summe())[0::2], ["15,50 h", 3])
    await tab.warte_auf_neu_geladene_liste("(()=>{document.getElementById('filterAuftrag').value='';"
                                          "document.getElementById('filterAuftrag').dispatchEvent(new Event('change',{bubbles:true}))})()", "#buchungenZeilen")

    await tab.js(f"document.querySelector('[data-aktion=zu-ende][data-id=\"{seed['ole']}\"]').click()")
    p.pruefe("Fin: „Ende eintragen“ springt zu Prüfen, Fokus im Feld", await tab.warten(
        f"!document.getElementById('reiter-pruefen').hidden&&document.activeElement===document.getElementById('ende-{seed['ole']}')", 5), True)
    await _buchungen(tab)

    await _menue(tab, seed["attika"], "aendern")
    p.pruefe("Fin: Dialog Ändern offen, Vorschau vom Server", await tab.warten(
        "document.getElementById('buchungDialog').open&&document.getElementById('bdVorschauZahl').innerText!==''", 10), True)
    p.pruefe("Fin: Dialog -- Kopf, Von/Bis, Vorschau, Knopf", await tab.js(
        "[document.getElementById('bdTitel').innerText,document.getElementById('bdVon').value,document.getElementById('bdBis').value,"
        "document.getElementById('bdVorschauZeile').innerText,document.getElementById('bdSpeichern').innerText,"
        "document.getElementById('bdModusVonBis').getAttribute('aria-pressed')]"),
        ["Buchung ändern", "07:00", "16:30", "Anwesend 9:30 h · Tag zusammen 10:15 h · Pause nach Zeitregel − 0:45 h", "8,75 h speichern", "true"])
    # seit 1.9.104 (Nachrunde, Punkt 5) die Unterzeile wie die Vorlage, aus dem Verlauf (bis 1.9.103 der Anleger mit dem Zeitpunkt des Anlegens)
    p.pruefe("Fin: Dialog -- Unterzeile wie die Vorlage", await tab.js("document.getElementById('bdUnter').innerText"),
             "Tom Monteur · gebucht von Tom Monteur am 15.10., 16:31")
    await tab.bild("zeiten_dialog_hell")
    await _eingeben(tab, "bdBis", "16:00")
    p.pruefe("Fin: Bis 16:00 -> 8,25 h", await tab.warten("document.getElementById('bdSpeichern').innerText==='8,25 h speichern'", 10), True)
    await tab.warte_auf_neu_geladene_liste("document.getElementById('bdSpeichern').click()", "#buchungenZeilen")
    p.pruefe("Fin: gespeichert -- Zeile 07:00–16:00, 8,25", await tab.js(
        f"[...document.querySelector('tr[data-buchung=\"{seed['attika']}\"]').cells].slice(2,7).map(c=>c.innerText)"),
        ["07:00–16:00", "Baustellenzeit", "AUF-2026-0102 · Attika", "0:45", "8,25"])

    await _menue(tab, seed["attika"], "aendern")
    await tab.warten("document.getElementById('buchungDialog').open&&document.getElementById('bdVorschauZahl').innerText!==''", 10)
    p.pruefe("Fin: nach der Änderung -- Unterzeile mit „geändert von“", await tab.js(
        "document.getElementById('bdUnter').innerText.replace(/am \\d\\d\\.\\d\\d\\., \\d\\d:\\d\\d$/,'am …')"),
        "Tom Monteur · gebucht von Tom Monteur am 15.10., 16:31 · geändert von Fin Finanzen am …")
    await tab.js("document.getElementById('bdModusDauer').click()")
    p.pruefe("Fin: Wechsel zu „Dauer“ -- Von/Bis leer und weg, Hinweis, Stunden", await tab.js(
        "[document.getElementById('bdVon').value,document.getElementById('bdBis').value,document.getElementById('bdVonFeld').hidden,"
        "document.getElementById('bdDauerHinweis').hidden,document.getElementById('bdDauerHinweis').innerText,document.getElementById('bdStundenFeld').hidden]"),
        ["", "", True, False, "Mit „Dauer“ entfallen Von und Bis – gespeichert wird nur die Dauer (netto), ohne Pausenregel.", False])
    await _eingeben(tab, "bdStunden", "8")
    p.pruefe("Fin: Dauer 8 -> Knopf", await tab.warten("document.getElementById('bdSpeichern').innerText==='8,00 h speichern'", 5), True)
    await tab.warte_auf_neu_geladene_liste("document.getElementById('bdSpeichern').click()", "#buchungenZeilen")
    p.pruefe("Fin: als Dauer gespeichert -- Zeile", await tab.js(
        f"[...document.querySelector('tr[data-buchung=\"{seed['attika']}\"]').cells].slice(2,7).map(c=>c.innerText)"),
        ["Dauer · vom Büro", "Baustellenzeit", "AUF-2026-0102 · Attika", "0:45", "8,00"])  # seit 1.9.104: die Dauer setzte das Büro (bis 1.9.103 „Dauer“)
    gespeichert = [e for e in (await _api(tab, "/api/zeiten/buchungen?monat=2026-10"))["eintraege"] if e["id"] == seed["attika"]][0]
    p.pruefe("Fin: Beginn und Ende leer (API)", [gespeichert["started_at"], gespeichert["ended_at"], float(gespeichert["hours"])], [None, None, 8.0])

    await tab.js("document.getElementById('neueBuchung').click()")
    await tab.warten("document.getElementById('buchungDialog').open&&document.getElementById('bdMitarbeiter').options.length>1", 10)
    await tab.js(f"document.getElementById('bdMitarbeiter').value='{seed['mia']}';document.getElementById('bdAuftrag').value='{seed['halle_nord']}'")
    await _eingeben(tab, "bdDatum", "2026-10-22")
    await _eingeben(tab, "bdVon", "07:00")
    await _eingeben(tab, "bdBis", "11:00")
    p.pruefe("Fin: Neue Buchung -- Titel und Knopf", await tab.warten(
        "document.getElementById('bdTitel').innerText==='Neue Buchung'&&document.getElementById('bdSpeichern').innerText==='4,00 h speichern'", 10), True)
    await tab.warte_auf_neu_geladene_liste("document.getElementById('bdSpeichern').click()", "#buchungenZeilen")
    neu = await tab.js(_zeilen() + ".filter(z=>z[0]==='Do 22.10.')")
    p.pruefe("Fin: neue Buchung in der Liste", neu, [["Do 22.10.", "Mia Monteurin", "07:00–11:00", "Baustellenzeit", "AUF-2026-0001 · Halle Nord", "0:00",
                                                      "4,00"]])

    await _menue(tab, seed["dauer"], "loeschen")
    p.pruefe("Fin: Rückfrage auf der Seite", await tab.warten("document.getElementById('loeschDialog').open", 5), True)
    p.pruefe("Fin: Rückfrage nennt die Buchung", await tab.js("document.getElementById('ldText').innerText"),
             "Mia Monteurin · Baustellenzeit · Do 15.10. · 6,00 h")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('ldLoeschen').click()", "#buchungenZeilen")
    p.pruefe("Fin: gelöscht", await tab.js(f"!document.querySelector('tr[data-buchung=\"{seed['dauer']}\"]')"), True)
    # ---- Büro – Finanzen: Kolonne buchen (seit 1.9.97) ----------------------------------------------------------------------------
    await tab.js("document.getElementById('seitenkopfMenueKnopf').click()")
    await tab.js("document.getElementById('kolonneBuchen').click()")
    p.pruefe("Fin: Kolonne buchen -- Dialog mit Kolonne 1, Mia und Tom angehakt", await tab.warten(
        "document.getElementById('kolonneDialog').open&&document.querySelectorAll('.kd-mitglied:checked').length===2", 10), True)
    await tab.js(f"document.getElementById('kdAuftrag').value='{seed['halle_nord']}'")
    await _eingeben(tab, "kdDatum", "2026-10-23")
    await _eingeben(tab, "kdVon", "07:00")
    await _eingeben(tab, "kdBis", "12:00")
    p.pruefe("Fin: Kolonne -- Vorschau je Person und Knopf", await tab.warten(
        "document.getElementById('kdSpeichern').innerText==='Für 2 Personen speichern'", 10), True)
    p.pruefe("Fin: Kolonne -- Vorschau", await tab.js("document.getElementById('kdVorschauZeile').innerText"),
             "Mia Monteurin 5,00 h · Tom Monteur 5,00 h")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('kdSpeichern').click()", "#buchungenZeilen")
    p.pruefe("Fin: Kolonne gebucht -- beide in der Liste", await tab.js(_zeilen() + ".filter(z=>z[0]==='Fr 23.10.')"), [
        ["Fr 23.10.", "Mia Monteurin", "07:00–12:00", "Baustellenzeit", "AUF-2026-0001 · Halle Nord", "0:00", "5,00"],
        ["Fr 23.10.", "Tom Monteur", "07:00–12:00", "Baustellenzeit", "AUF-2026-0001 · Halle Nord", "0:00", "5,00"]])
    p.pruefe("Fin: keine JS-Fehler (auch kein alert/confirm)", tab.fehler, [])

    # ---- Büro – Auftrag: ohne Knöpfe ---------------------------------------------------------------------------------------------------
    vorher = len(tab.netz.verlauf)
    p.pruefe("Bea: Seite geladen", await _seite(tab, seed, "bea"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Bea: Prüfen ohne Knöpfe und ohne „+ Buchung“", await tab.js(
        "[document.querySelectorAll('#reiter-pruefen button,#reiter-pruefen input').length,!!document.getElementById('neueBuchung'),"
        "document.querySelectorAll('#offenListe .zeile').length]"), [0, False, 1])
    # seit 1.9.102 (Nachrunde, Punkt 4): „Zur Info“ statt „Wartet auf dich“, wer das Ende einträgt, keine Zahl am Reiter „Prüfen“
    p.pruefe("Bea: „Zur Info“ (ruhige Karte), wer das Ende einträgt, keine Zahl am Reiter Prüfen", await tab.js(
        "[document.getElementById('offenKarte').className,document.getElementById('offenEbText').textContent,"
        "document.querySelector('#offenEb .punkt').hidden,document.getElementById('offenFuss').innerText,document.getElementById('zahlPruefen').hidden]"),
        ["karte", "Zur Info", True, "Das Ende trägt der Admin oder Büro – Finanzen ein.", True])
    await tab.bild("zeiten_pruefen_buero_auftrag")
    p.pruefe("Bea: Buchungen geladen", await _buchungen(tab), True)
    p.pruefe("Bea: Buchungen ohne „⋮“ und ohne „Ende eintragen“", await tab.js(
        "document.querySelectorAll('#buchungenZeilen button').length"), 0)
    await tab.bild("zeiten_buchungen_buero_auftrag")
    # seit 1.9.98 aus klicktest_backoffice_buero (bis 1.9.97 im Backoffice geprüft)
    await tab.nachlesen()
    p.pruefe("Bea: keine Anfrage an Buchungskontext und Personalnummern", [
        tab.netz.suche(r"/api/time-tracking/context", "GET", ab=vorher), tab.netz.suche(r"/api/time-backoffice/payroll-employees", "GET", ab=vorher)],
        [[], []])
    p.pruefe("Bea: Stundenzettel PDF, CSV und DATEV-Export vom Server abgelehnt", await _exporte(tab), [403, 403, 403])
    p.pruefe("Bea: keine JS-Fehler", tab.fehler, [])

    # ---- Admin hell und dunkel: Bilder, Farbpunkte -------------------------------------------------------------------------------------
    p.pruefe("Admin hell: Buchungen", await _seite(tab, seed, "admin", hash="#buchungen"), True)
    await tab.warten(BUCHUNGEN_BEREIT, 10)
    await tab.warte_auf_ruhe()
    hell = await tab.js("['site','travel','workshop'].map(a=>getComputedStyle(document.querySelector('.zeitart-punkt[data-art='+a+']')).backgroundColor)")
    await tab.bild("zeiten_buchungen_hell")
    p.pruefe("Admin dunkel: Prüfen", await _seite(tab, seed, "admin", thema="dark"), True)
    await tab.warte_auf_ruhe()
    await tab.bild("zeiten_pruefen_dunkel")
    await _buchungen(tab)
    await tab.warte_auf_ruhe()
    dunkel = await tab.js("['site','travel','workshop'].map(a=>getComputedStyle(document.querySelector('.zeitart-punkt[data-art='+a+']')).backgroundColor)")
    await tab.bild("zeiten_buchungen_dunkel")
    p.pruefe("Farbpunkte aus den Tokens (hell, dunkel)", [hell, dunkel], [
        ["rgb(54, 115, 55)", "rgb(61, 106, 140)", "rgb(122, 90, 52)"], ["rgb(61, 130, 62)", "rgb(91, 141, 184)", "rgb(168, 128, 79)"]])
    p.pruefe("Admin: keine JS-Fehler", tab.fehler, [])

    # ---- Abwesenheiten (seit 1.9.97) ---------------------------------------------------------------------------------------------------
    p.pruefe("Admin: Seite geladen", await _seite(tab, seed, "admin", hash="#abwesenheiten"), True)
    p.pruefe("Admin: Abwesenheiten -- Toms Antrag, Zahl am Reiter", await tab.warten(
        "!!window.A&&document.querySelectorAll('#abwListe .zeile').length===1", 10), True)
    p.pruefe("Admin: Antrag mit Notiz, Ablehnen, Genehmigen; Zahl 1", await tab.js(
        "[document.querySelector('#abwListe .zeile-name').innerText,!!document.querySelector('#abwListe input.antrag-notiz'),"
        "[...document.querySelectorAll('#abwListe button')].map(b=>b.innerText),document.getElementById('zahlAbwesenheiten').innerText]"),
        ["Tom Monteur · Urlaub", True, ["Ablehnen", "Genehmigen"], "1"])
    await tab.bild("zeiten_abwesenheiten_hell")
    await tab.js("document.querySelector('#abwListe input.antrag-notiz').value='passt'")
    await tab.warte_auf_neu_geladene_liste("document.querySelector('#abwListe [data-entscheidung=approved]').click()", "#abwListe")
    await tab.warte_auf_neu_geladene_liste("(()=>{const s=document.getElementById('abwStatus');s.value='';s.dispatchEvent(new Event('change'))})()",
                                          "#abwListe")
    p.pruefe("Admin: genehmigt mit Notiz, Zahl am Reiter weg", await tab.js(
        "[document.querySelector('#abwListe .chip').innerText,document.querySelector('#abwListe').innerText.includes('Freigabe: passt'),"
        "document.getElementById('zahlAbwesenheiten').hidden]"), ["genehmigt", True, True])

    p.pruefe("Bea: Seite geladen", await _seite(tab, seed, "bea", hash="#abwesenheiten"), True)
    await tab.warten("!!window.A", 10)
    p.pruefe("Bea: Hinweis nur eigene, beantragen, kein Reiter Monat & Lohn, API 403", [
        await tab.js("document.getElementById('abwHinweis').innerText"), await tab.js("document.getElementById('abwNeu').hidden"),
        await tab.js("!!document.querySelector('[data-reiter=monat]')"), await tab.js("fetch('/api/zeiten/monat').then(r=>r.status)")],
        ["Hier stehen nur deine eigenen Anträge – die Anträge aller sehen Admin und Büro – Finanzen.", False, False, 403])
    await tab.js("document.getElementById('abwNeu').click()")
    await tab.warten("document.getElementById('abwDialog').open", 5)
    p.pruefe("Bea: Dialog ohne Feld Mitarbeiter", await tab.js("document.getElementById('adMitarbeiterFeld').hidden"), True)
    await _eingeben(tab, "adVon", "2026-11-09")
    await _eingeben(tab, "adBis", "2026-11-10")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('adSenden').click()", "#abwListe")
    p.pruefe("Bea: Antrag gestellt -- offen, mit „Zurückziehen“", await tab.js(
        "[...document.querySelectorAll('#abwListe .zeile')].map(z=>[z.querySelector('.zeile-name').innerText,z.querySelector('.chip').innerText,"
        "[...z.querySelectorAll('button')].map(b=>b.innerText)])"), [["Bea Büro · Urlaub", "offen", ["Zurückziehen"]]])
    await tab.js("document.querySelector('#abwListe [data-aktion=abw-fragen]').click()")
    p.pruefe("Bea: Rückfrage in der Zeile", await tab.js("document.querySelector('#abwListe .rueckfrage').innerText"), "Antrag zurückziehen?")
    await tab.warte_auf_neu_geladene_liste("document.querySelector('#abwListe [data-aktion=abw-ja]').click()", "#abwListe")
    p.pruefe("Bea: zurückgezogen -- keine offenen mehr", await tab.js("document.querySelectorAll('#abwListe .zeile').length"), 0)
    p.pruefe("Bea: Antrag für Tom vom Server abgelehnt (403)", await tab.js(
        f"fetch('/api/absence-requests',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{employee_id:{seed['tom_ma']},"
        "absence_category:'krankheit',absence_type:'Krankheit',start_date:'2026-11-16',end_date:'2026-11-16'})}).then(r=>r.status)"), 403)
    p.pruefe("Bea: keine JS-Fehler", tab.fehler, [])

    # seit 1.9.101 (Nachrunde, Punkt 1): Büro – Finanzen sieht alle Anträge und stellt sie für andere, entscheidet nicht, zieht zurück, was es
    # gestellt hat (bis 1.9.100 ohne eigenen Mitarbeiter: Hinweis, keine Anträge, kein „beantragen“)
    p.pruefe("Fin: Abwesenheiten ohne eigenen Mitarbeiter", await _seite(tab, seed, "fin", hash="#abwesenheiten"), True)
    await tab.warten("!!window.A", 10)
    await tab.warte_auf_neu_geladene_liste("(()=>{const s=document.getElementById('abwStatus');s.value='';s.dispatchEvent(new Event('change'))})()",
                                          "#abwListe")
    p.pruefe("Fin: alle Anträge (auch Toms und Beas), kein Hinweis, „beantragen“", await tab.js(
        "[[...document.querySelectorAll('#abwListe .zeile')].map(z=>z.querySelector('.zeile-name').innerText+' | '+z.querySelector('.chip').innerText).sort(),"
        "document.getElementById('abwHinweis').innerText,document.getElementById('abwNeu').hidden,document.querySelectorAll('#abwListe button').length]"),
        [["Bea Büro · Urlaub | zurückgezogen", "Tom Monteur · Urlaub | genehmigt"], "", False, 0])
    await tab.js("document.getElementById('abwNeu').click()")
    await tab.warten("document.getElementById('abwDialog').open", 5)
    p.pruefe("Fin: Dialog mit Feld Mitarbeiter (ohne Vorwahl)", await tab.js(
        "[document.getElementById('adMitarbeiterFeld').hidden,document.getElementById('adMitarbeiter').value]"), [False, ""])
    await tab.js(f"document.getElementById('adMitarbeiter').value='{seed['tom_ma']}';auswahlWert(document.getElementById('adKategorie'),'krankheit')")
    await _eingeben(tab, "adVon", "2026-10-27")
    await _eingeben(tab, "adBis", "2026-10-28")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('adSenden').click()", "#abwListe")
    await tab.warte_auf_neu_geladene_liste("(()=>{const s=document.getElementById('abwStatus');s.value='pending';s.dispatchEvent(new Event('change'))})()",
                                          "#abwListe")
    p.pruefe("Fin: „Krank“ für Tom gestellt -- offen, „beantragt von“, nur „Zurückziehen“, Zahl am Reiter 1", await tab.js(
        "[...document.querySelectorAll('#abwListe .zeile')].map(z=>[z.querySelector('.zeile-name').innerText,"
        "z.querySelector('.zeile-unter').innerText.replace(/ am \\d\\d\\.\\d\\d\\.$/,' am …'),"
        "[...z.querySelectorAll('button')].map(b=>b.innerText)]).concat([document.getElementById('zahlAbwesenheiten').innerText])"),
        [["Tom Monteur · Krankheit", "Di 27.10.–Mi 28.10.2026 · 2 Arbeitstage · beantragt von Fin Finanzen am …", ["Zurückziehen"]], "1"])
    await tab.bild("zeiten_abwesenheiten_finanzen")
    krank = await tab.js("A.antraege[0].id")
    p.pruefe("Fin: entscheiden vom Server abgelehnt (403)", await tab.js(
        f"fetch('/api/absence-requests/{krank}/review',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{decision:'approved'}})}})"
        ".then(r=>r.status)"), 403)
    await tab.js("document.querySelector('#abwListe [data-aktion=abw-fragen]').click()")
    await tab.warte_auf_neu_geladene_liste("document.querySelector('#abwListe [data-aktion=abw-ja]').click()", "#abwListe")
    p.pruefe("Fin: zurückgezogen -- keine offenen, Zahl weg", await tab.js(
        "[document.querySelectorAll('#abwListe .zeile').length,document.getElementById('zahlAbwesenheiten').hidden]"), [0, True])
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])

    # ---- Monat & Lohn (seit 1.9.97) -------------------------------------------------------------------------------------------------
    p.pruefe("Fin: Monat & Lohn geladen", await _seite(tab, seed, "fin", hash="#monat"), True)
    p.pruefe("Fin: Oktober 2026", await tab.warten("!!window.M&&document.getElementById('lohnMonat').innerText==='Oktober 2026'", 10), True)
    p.pruefe("Fin: Lücke -- Abschließen gesperrt, Fehlt nur die Zeiten, DATEV getrennt und gesperrt", await tab.js(
        "[document.getElementById('lohnAbschliessen').disabled,document.getElementById('lohnFehlt').innerText,"
        "document.getElementById('lohnDatevFehlt').innerText,document.getElementById('lohnDatev').hidden,"
        "document.getElementById('lohnDatevGesperrt').disabled]"), [True, "Fehlt: 1 laufende Zeit", "Fehlt: 1 Lohnart", True, True])
    p.pruefe("Fin: Schritt Prüfen", await tab.js("[...document.querySelectorAll('#lohnPruefen li')].map(l=>l.innerText.replace(/\\s+/g,' ').trim())"),
             ["1 Zeit läuft noch Prüfen", "Lohnart fehlt: Werkstattzeit Zeitregeln", "Anträge entschieden"])
    p.pruefe("Fin: Tabelle mit Personalnummer", await tab.js(
        "[...document.querySelectorAll('#lohnZeilen tr')].map(tr=>[...tr.cells].map(c=>c.innerText.trim()).join(' | '))"),
        ["Mia Monteurin | 1001 | 4 | 18,25 | 0,00 | 3,50 | 0,00 | 21,75", "Tom Monteur | 1002 | 4 | 29,75 | 0,75 | 0,00 | 0,00 | 30,50",
         "Zusammen |  |  | 48,00 | 0,75 | 3,50 | 0,00 | 52,25"])
    await tab.bild("zeiten_monat_hell")
    await tab.js("document.querySelector('#lohnPruefen a[data-reiter-link=pruefen]').click()")
    await tab.warten(f"!document.getElementById('reiter-pruefen').hidden&&!!document.getElementById('ende-{seed['ole']}')", 10)
    await _eingeben(tab, f"ende-{seed['ole']}", "18:00")
    await tab.warten(f"!document.querySelector('[data-aktion=ende][data-id=\"{seed['ole']}\"]').disabled", 10)
    await tab.js(f"document.querySelector('[data-aktion=ende][data-id=\"{seed['ole']}\"]').click()")
    await tab.warten(f"!document.querySelector('[data-offen=\"{seed['ole']}\"]')", 10)
    await tab.js("document.querySelector('.reiter a[data-reiter=monat]').click()")
    p.pruefe("Fin: ohne Lücke -- Abschließen frei, DATEV nennt jetzt auch die Personalnummer", await tab.warten(
        "!document.getElementById('lohnAbschliessen').disabled&&document.getElementById('lohnDatevFehlt').innerText==='Fehlt: 1 Personalnummer, 1 Lohnart'", 10),
        True)
    # eine neue Lücke nach dem Laden: Mias Zeit läuft seit heute 08:00 -- der Server lehnt den Abschluss ab, die Seite zeigt die Liste
    neu = await tab.js(f"fetch('/api/time-entries/start',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
                       f"body:JSON.stringify({{employee_id:{seed['mia']},order_id:{seed['halle_nord']},started_at:'2026-10-26T08:00'}})}})"
                       ".then(r=>r.json()).then(d=>d.id)")
    await tab.js("document.getElementById('lohnAbschliessen').click()")
    p.pruefe("Fin: abgelehnt -- die Liste auf der Seite", await tab.warten("document.querySelectorAll('#lohnAbgelehnt li').length===1", 10), True)
    p.pruefe("Fin: Liste und Meldung", await tab.js(
        "[document.querySelector('#lohnAbgelehnt li').innerText,document.getElementById('lohnFehlt').innerText.startsWith('Abschließen geht noch nicht: 1 Zeit läuft noch')]"),
        ["Mia Monteurin: Zeit läuft seit 26.10.2026, 08:00", True])
    p.pruefe("Fin: Mias Zeit gestoppt (09:00)", await tab.js(
        f"fetch('/api/time-entries/{neu}/stop',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        "body:JSON.stringify({ended_at:'2026-10-26T09:00'})}).then(r=>r.status)"), 200)
    await tab.js("monatLaden()")
    p.pruefe("Fin: wieder ohne Lücke -- Abschließen frei", await tab.js("document.getElementById('lohnAbschliessen').disabled"), False)
    await tab.warte_auf_neu_geladene_liste("document.getElementById('lohnAbschliessen').click()", "#lohnZeilen")
    p.pruefe("Fin: abgeschlossen -- Status, kein Knopf, DATEV noch gesperrt (Lohnart, Personalnummer)", await tab.js(
        "[document.getElementById('lohnStatus').innerText,document.getElementById('lohnAbschliessen').hidden,document.getElementById('lohnDatev').hidden,"
        "document.getElementById('ergebnis').innerText]"), ["abgeschlossen", True, True, "Oktober 2026 abgeschlossen."])
    # seit 1.9.98 aus klicktest_backoffice_buero: abgeschlossen ändert nur der Admin, zurücknehmen auch
    p.pruefe("Fin: Stundenzettel PDF und CSV 200 (DATEV folgt unten)", (await _exporte(tab))[:2], [200, 200])
    p.pruefe("Fin: Buchungen des abgeschlossenen Oktobers ohne „⋮“", [await _buchungen(tab), await tab.js(
        "[document.querySelectorAll('#buchungenZeilen tr').length>0,document.querySelectorAll('#buchungenZeilen button').length]")],
        [True, [True, 0]])
    p.pruefe("Fin: im „⋮“ des Kopfs kein „Abschluss aufheben“", await tab.js(
        "[!!document.getElementById('abschlussAufheben'),[...document.querySelectorAll('#seitenkopfMenue .ds-menue-eintrag')].map(e=>e.textContent.trim())]"),
        [False, ["Kolonne buchen", "Zeitregeln und DATEV", "Zeit-Listen"]])
    p.pruefe("Fin: zurücknehmen vom Server abgelehnt (403)", await tab.js(
        "fetch('/api/time-backoffice/lock',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({locked_until:'2026-09-30'})})"
        ".then(r=>r.json().then(d=>[r.status,d.detail]))"), [403, "Einen abgeschlossenen Zeitraum wieder öffnen darf nur ein Administrator."])
    await tab.js("document.querySelector('.reiter a[data-reiter=monat]').click()")
    # Lohnart Werkstatt und Oles Personalnummer nachtragen (die Zeitregeln speichert der PUT als Ganzes: erst lesen, dann ergänzen)
    p.pruefe("Fin: Lohnart Werkstatt und Oles Personalnummer gespeichert", [
        await tab.js("fetch('/api/time-backoffice/settings').then(r=>r.json()).then(s=>fetch('/api/time-backoffice/settings',{method:'PUT',"
                     "headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign(s,{datev_wage_type_workshop:'300'}))}))"
                     ".then(r=>r.status)"),
        await tab.js(f"fetch('/api/time-backoffice/payroll-employees/{seed['ole_ma']}',{{method:'PUT',headers:{{'Content-Type':'application/json'}},"
                     f"body:JSON.stringify({{datev_personnel_number:'1003',payroll_export_enabled:true}})}}).then(r=>r.status)")], [200, 200])
    await tab.js("monatLaden()")
    p.pruefe("Fin: vollständig -- DATEV-Export als Link", await tab.js(
        "[document.getElementById('lohnDatev').hidden,document.getElementById('lohnDatevFehlt').innerText]"), [False, ""])
    # r.text() liest ohne das BOM am Anfang der Datei
    datei = await tab.js("fetch(document.getElementById('lohnDatev').href).then(r=>r.text().then(t=>[r.status,r.headers.get('content-disposition'),t.split(String.fromCharCode(13,10))[0]]))")
    p.pruefe("Fin: DATEV-Datei", datei, [200, 'attachment; filename="DATEV_Lohndaten_2026-10.csv"', "Personalnummer;Name;Kalendertag;Stundenanzahl;Lohnart;Zeitart"])
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])

    p.pruefe("Admin: Seite für „Abschluss aufheben“", await _seite(tab, seed, "admin"), True)
    await tab.js("document.getElementById('seitenkopfMenueKnopf').click()")
    await tab.js("document.getElementById('abschlussAufheben').click()")
    p.pruefe("Admin: Dialog -- Stand und Vorschlag", await tab.warten("document.getElementById('aufhebenDialog').open", 5), True)
    p.pruefe("Admin: Dialog -- Text und gewählt", await tab.js(
        "[document.getElementById('ahText').innerText,document.getElementById('ahBis').value,"
        "[...document.getElementById('ahBis').options].slice(-1)[0].text]"), ["Abgeschlossen ist bis 31.10.2026.", "2026-09-30",
                                                                             "nichts – Abschluss ganz aufheben"])
    await tab.warte_auf_neu_geladene_liste("document.getElementById('ahAufheben').click()", "#monatZeilen")
    p.pruefe("Admin: zurück auf 30.09.2026 -- Oktober offen", await tab.js(
        "[document.getElementById('ergebnis').innerText,document.getElementById('monatTitel').innerText,document.getElementById('monatStatus').innerText]"),
        ["Abschluss zurückgenommen: abgeschlossen bis 30.09.2026.", "Oktober 2026", "offen"])
    p.pruefe("Admin: keine JS-Fehler", tab.fehler, [])

    # ---- 412 px ------------------------------------------------------------------------------------------------------------------------
    await tab.fenster(412, 900, mobil=True)
    p.pruefe("412 px: geladen", await tab.oeffnen("/zeiten?neu=2", BEREIT), True)
    p.pruefe("412 px: ohne waagrechte Scrollleiste der Seite", await tab.js("document.documentElement.scrollWidth<=window.innerWidth+1"), True)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-10-26 10:00"))
