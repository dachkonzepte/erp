"""Klicktest: „Meine Zeiten“ der Monteurin (seit 1.9.59, Stufe 4, R3) -- /mobil/zeiten nach der Vorlage zeiten-nachtragen.

Stehende Uhr Mi 14.10.2026 10:00 (Server und Browser; die Vorlage zeigt denselben Tag, dort als „Di“). Befüllt: Auftrag A („Halle Nord“) und B, Plantafel
für alle; Kolonne Nord mit Mia (Kolonnenführerin) und Tom; Abschluss bis 30.09.2026. Mia:
    14.10.  Fahrzeit 06:00–06:45 gebucht, Baustelle läuft seit 06:45
    13.10.  Baustelle 07:00–12:00 (5,00 h)                                   -> „+ Nachtragen“ Werkstatt 12:00–16:15 (Tag zusammen)
    10.10.  Baustelle 06:00–13:00 (Pause 30) und 13:00–16:00 (Pause 15)      -> die erste löschen, „Pausen neu rechnen“
    09.10.  Fahrzeit 06:15–07:00, Baustelle 07:00–15:00 (Tätigkeit, Notiz)    -> Ändern: Bis 16:30
    08.10.  Kolonnenbuchung Mia + Tom je 8 h                                  -> „Für die Kolonne ändern“ 7,5 h, dann löschen
    29.09.  Baustelle 7,50 h (abgeschlossen)
    Antrag Urlaub (offen)
Ole: Zeit von gestern seit 06:45 offen. Pia: Konto ohne Mitarbeiter.

Jede Funktion aus dem Befund (docs/archiv/redesign.md, „Stufe 4, R3“, Z1–Z22 und S1–S5) wird hier oder in klicktest_heute.py (Starten,
Stoppen, Zeitart wechseln, Kolonne starten und stoppen, Ende nachtragen) erreicht:
    Reiter         „Heute · Meine Zeiten“, aktiv; /time-tracking?order_id=A und /mobil/stundenzettel leiten hierher (Z21, S4)
    quer           zwei Spalten (rechts 400 px), Kacheln Heute 0,75 / Woche 5,75 / Oktober 31,25 ohne die laufende Zeit (Z11); Tage mit Kopfzeile
                   und Summe (S2), Zeile mit Von–Bis, „Zeitart · Auftrag“, gebucht, zweite Zeile Tätigkeit · Notiz (Z12); laufend „läuft seit
                   06:45“ ohne Stunden und ohne „⋮“ (Z1); Abwesenheit „1 offener Antrag.“, Monat mit Summe, Tagen, Fahrzeit, produktiv (S3);
                   Maße (Zeilen ≥ 64, „⋮“ 48, Knöpfe 52/56); hell und dunkel; Bild neben der Vorlage
    hoch           eine Spalte: Kacheln, Buchungen, Abwesenheit, Monat; hell und dunkel
    Nachtragen     Dialog wie die Vorlage (Felder 52 px, Knöpfe 56 px), Auftrag aus ?order_id vorgewählt, Vorschau „Anwesend 4:15 h · Tag
                   zusammen 9:15 h · Pause nach Zeitregel − 0:45 h“ und „3,50 h“, Knopf „3,50 h nachtragen“ -> gebucht wie die Vorschau,
                   Ergebnis über den Buchungen (Z13, Z14)
    Ändern         vorbelegt, Bis 16:30 -> Vorschau 8,75 h (Tag zusammen 10:15 h), „Pause mindestens“ 60 -> 1:00 h, zurück auf leer;
                   gespeichert, die Fahrzeit des Tags unverändert (Z15, Z3)
    Löschen        Rückfrage auf der Seite (Abbrechen lässt alles), Löschen -> Tag zeigt „Pause abgezogen 0:15 h · nach Zeitregel 0:00 h“,
                   nichts von selbst (Z16); „Pausen neu rechnen“ -> Vorschau alt -> neu, „So buchen“ -> genau die Vorschau (Verlauf)
    Kolonne        „⋮ Für die Kolonne ändern“ (Mitglieder im Dialog) 7,5 h -> Mia und Tom; „⋮ Nachtrag für die Kolonne“ am 07.10.; „⋮ Für die
                   Kolonne löschen“ mit Rückfrage (Z9, Z10); Tom sieht „gebucht von Mia Monteurin“
    Monat          ‹ September: abgeschlossen, kein „⋮“ (Z17), › zurück; PDF des Monats 200 application/pdf (S1, S4)
    Abwesenheit    „+ Antrag“ senden -> „2 offene Anträge.“; „Zurückziehen“ mit Rückfrage in der Zeile -> 1 (Z18, Z19)
    Ole            Zeile „läuft seit 06:45“ mit „Feierabend auf „Heute“ eintragen“ -> /mobil (Z4)
    Pia            Hinweis „Konto ohne Mitarbeiter“ (Z20)
    überall        keine JS-Fehler

Die Bilder (meine_zeiten_*.png) liegen im Ordner der Screenshots.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_meine_zeiten.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD]
        [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date, datetime, time, timedelta
    from decimal import Decimal

    from app.models import (
        AppUser, Customer, Employee, EmployeeAbsenceRequest, Order, OrderItem, PlanningSlot, Project, Property, Team, TeamEmployee,
        WorkPreparationTeamAssignment, WorkPreparationTeamEmployee,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.time_backoffice import set_time_lock
    from app.time_tracking import create_group_manual_entry, create_manual_entry, start_timer, stop_timer
    from app.work_preparation import ensure_preparation

    heute = date(2026, 10, 14)
    leute = {}
    for nr, (vor, nach) in enumerate([("Mia", "Monteurin"), ("Tom", "Mitglied"), ("Ole", "Offen")], 1):
        leute[vor.lower()] = Employee(employee_number=f"E-{nr}", first_name=vor, last_name=nach, employee_group="gewerblich", active=True,
                                      hourly_wage=Decimal("22.00"))
    db.add_all(leute.values()); db.flush()
    benutzer = {n: AppUser(username=n, display_name=f"{e.first_name} {e.last_name}", role="field", employee_id=e.id, password_hash=k.passwort())
                for n, e in leute.items()}
    benutzer["pia"] = AppUser(username="pia", display_name="Pia Ohne", role="field", password_hash=k.passwort())
    db.add_all(benutzer.values())
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    halle = Property(customer_id=kunde.id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Übach-Palenberg")
    db.add(halle); db.flush()

    def auftrag(nr, titel):
        projekt = Project(project_number=f"P-KT-MZ{nr}", name=titel, customer_id=kunde.id, property_id=halle.id,
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        o = Order(order_number=f"AUF-2026-000{nr}", project_id=projekt.id, source_quote_id=950 + nr, quote_number_snapshot=f"A-KT-{nr}",
                  title=titel, customer_name=kunde.name, property_name=halle.name, property_address="Werkstr. 5\n52531 Übach-Palenberg")
        db.add(o); db.flush()
        db.add(OrderItem(order_id=o.id, sort_order=10, position_number="1", short_text="Arbeiten", quantity=Decimal("1"), unit="psch",
                         unit_price=Decimal("1")))
        db.commit()
        return o

    a, b = auftrag(1, "Wartung"), auftrag(2, "Rinne erneuern")
    team = Team(name="Kolonne Nord", active=True)
    db.add(team); db.flush()
    db.add_all([TeamEmployee(team_id=team.id, employee_id=leute["mia"].id, is_crew_leader=True),
                TeamEmployee(team_id=team.id, employee_id=leute["tom"].id)])
    for o in (a, b):
        prep = ensure_preparation(db, o.id)
        zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
        db.add(zuordnung); db.flush()
        for e in leute.values():
            db.add(WorkPreparationTeamEmployee(assignment_id=zuordnung.id, employee_id=e.id, employee_name_snapshot=e.first_name))
        db.add(PlanningSlot(preparation_id=prep.id, team_assignment_id=zuordnung.id, start_date=heute - timedelta(days=20),
                            end_date=heute + timedelta(days=5)))
    db.commit()

    def zeit(emp, tag, von, bis, art="site", **mehr):
        row = start_timer(db, employee_id=emp.id, order_id=a.id, entry_type=art, started_at=datetime.combine(tag, von), **mehr)
        return stop_timer(db, row.id, ended_at=datetime.combine(tag, bis))

    mia = leute["mia"]
    zeit(mia, heute, time(6), time(6, 45), "travel")
    zeit(mia, date(2026, 10, 13), time(7), time(12))
    erste = zeit(mia, date(2026, 10, 10), time(6), time(13))
    zweite = zeit(mia, date(2026, 10, 10), time(13), time(16))
    zeit(mia, date(2026, 10, 9), time(6, 15), time(7), "travel")
    zeit(leute["tom"], date(2026, 10, 7), time(6, 15), time(7), "travel")  # seit 1.9.63: Toms Tag vor dem Kolonnen-Nachtrag
    aendern = zeit(mia, date(2026, 10, 9), time(7), time(15), activity="Dachdeckung")
    aendern.notes = "Rinne geprüft"
    aendern.min_break_minutes = None  # seit 1.9.62: wie eine Buchung von vor 1.9.62 -- „Ändern“ belegt mit der abgezogenen Pause vor
    db.commit()
    gruppe = create_group_manual_entry(db, employee_ids=[mia.id, leute["tom"].id], team_id=team.id, actor_employee_id=mia.id, is_admin=False,
                                       order_id=a.id, work_date=date(2026, 10, 8), hours=Decimal("8"))
    create_manual_entry(db, employee_id=mia.id, order_id=a.id, work_date=date(2026, 9, 29), hours=Decimal("7.5"))
    db.add(EmployeeAbsenceRequest(employee_id=mia.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2026, 11, 2),
                                  end_date=date(2026, 11, 6), status="pending"))
    db.commit()
    set_time_lock(db, date(2026, 9, 30), user_id=None)
    # zuletzt die laufende Zeit von heute (neben einer laufenden legt nichts eine weitere an)
    start_timer(db, employee_id=mia.id, order_id=a.id, started_at=datetime.combine(heute, time(6, 45)))
    start_timer(db, employee_id=leute["ole"].id, order_id=a.id, started_at=datetime.combine(heute - timedelta(days=1), time(6, 45)))
    db.commit()
    return {"a": a.id, "erste": erste.id, "zweite": zweite.id, "aendern": aendern.id, "gruppe": gruppe.id, "mia": mia.id,
            "tom": leute["tom"].id, "uhr_ms": k.uhr_ms(), "cookies": {n: k.cookies(u) for n, u in benutzer.items()}}


BEREIT = "!document.getElementById('tage').classList.contains('laedt')&&document.getElementById('monatName').textContent!==''"
HINWEIS_BEREIT = "!document.getElementById('ladeHinweis').hidden"
VORSCHAU_DA = "document.getElementById('zdVorschauZahl').textContent!==''"

SPALTEN = """(()=>{const r=id=>document.getElementById(id).getBoundingClientRect();const l=r('zeitenLinks'),re=r('zeitenRechts');
return [Math.round(re.width),l.left<re.left&&Math.abs(l.top-re.top)<2]})()"""

REIHENFOLGE = """(()=>{const y=s=>Math.round(document.querySelector(s).getBoundingClientRect().top);
const w=[y('#kacheln'),y('.buchungen'),y('#abwesenheitKarte'),y('#monatKarte')];return w.every((v,i)=>i===0||v>w[i-1])})()"""

# Maße: Zeilen ≥ 64, „⋮“ 48, „+ Nachtragen“ 52, Knöpfe der Karten rechts 56
MASSE = """(()=>{const h=e=>Math.round(e.getBoundingClientRect().height),sicht=e=>e.getClientRects().length>0;
const q=s=>[...document.querySelectorAll(s)].filter(sicht).map(h);
const z=q('#tage .zeile'),m=q('#tage .knopf-symbol'),n=q('#nachtragenKnopf'),r=q('#antragKnopf,#pdfKnopf');
return [[z.length>0&&z.every(x=>x>=64),m.length>0&&m.every(x=>x===48),n[0]===52,r.every(x=>x===56)],{z,m,n,r}]})()"""

TAGE = "[...document.querySelectorAll('#tage .tag-kopf')].map(k=>[k.querySelector('.tag-name').textContent,k.querySelector('.tag-summe').textContent])"


def zeilen_des_tags(tag):
    """Text der Zeilen unter der Kopfzeile von tag ('JJJJ-MM-TT'): [Von–Bis, Titel, zweite Zeile, Stunden, mit „⋮“]."""
    return (f"(()=>{{const k=document.querySelector('#tage .tag-kopf[data-tag=\"{tag}\"]');const out=[];let e=k&&k.nextElementSibling;"
            "while(e&&!e.classList.contains('tag-kopf')){if(e.classList.contains('zeile'))out.push([e.querySelector('.zeile-spanne').textContent,"
            "e.querySelector('.zeile-text span').textContent,(e.querySelector('.zeile-unter')||{}).textContent||'',"
            "e.querySelector('.zeile-stunden').textContent,!!e.querySelector('.knopf-symbol')]);e=e.nextElementSibling}return out})()")


def menue(zeile_id, aktion):
    """Öffnet das „⋮“ der Zeile und klickt den Eintrag mit data-aktion."""
    return (f"(()=>{{const z=document.querySelector('[data-zeile=\"{zeile_id}\"]');z.querySelector('.knopf-symbol').click();"
            f"z.querySelector('[data-aktion=\"{aktion}\"]').click()}})()")


def setze(feld, wert):
    return f"(f=>{{f.value='{wert}';f.dispatchEvent(new Event('input'));f.dispatchEvent(new Event('change'))}})(document.getElementById('{feld}'))"


async def _ansehen(tab, seed, wer, breite, hoehe, thema, pfad="/mobil/zeiten", bereit=BEREIT):
    await tab.anmelden(seed["cookies"][wer])
    await tab.fenster(breite, hoehe)
    await tab.oeffnen(pfad, bereit)
    await tab.js(f"localStorage.setItem('erp_theme','{thema}')")
    await tab.oeffnen(pfad, bereit)


async def _ganze_seite(tab, name, breite, hoehe):
    voll = await tab.js("Math.ceil(document.documentElement.scrollHeight)")
    await tab.fenster(breite, max(hoehe, voll))
    await tab.bild(name)
    await tab.fenster(breite, hoehe)


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.browser_uhr_fest(seed["uhr_ms"])
    a = seed["a"]

    # --- alte Adressen, Reiter --------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(1280, 620)
    await tab.oeffnen(f"/time-tracking?order_id={a}", BEREIT)
    p.pruefe("/time-tracking?order_id= leitet auf „Meine Zeiten“ mit Auftrag", await tab.js("location.pathname+location.search"),
             f"/mobil/zeiten?order_id={a}")
    p.pruefe("Reiter „Heute · Meine Zeiten“, aktiv „Meine Zeiten“", await tab.js(
        "[[...document.querySelectorAll('.mobile-nav-reiter')].map(r=>r.textContent),document.querySelector('.mobile-nav-reiter.active').textContent]"),
        [["Heute", "Meine Zeiten"], "Meine Zeiten"])
    await tab.js("document.getElementById('nachtragenKnopf').click()")
    p.pruefe("Nachtragen: Auftrag aus ?order_id vorgewählt", await tab.js("document.getElementById('zdAuftrag').value"), str(a))
    await tab.js("document.getElementById('zeitDialog').close()")
    await tab.oeffnen("/mobil/stundenzettel", BEREIT)
    p.pruefe("/mobil/stundenzettel leitet auf „Meine Zeiten“", await tab.js("location.pathname"), "/mobil/zeiten")

    # --- quer und hoch, hell und dunkel ------------------------------------------------------------------------------------------
    for breite, hoehe, art in ((1280, 620, "quer"), (800, 1100, "hoch")):
        for thema in ("light", "dark"):
            await _ansehen(tab, seed, "mia", breite, hoehe, thema)
            await _ganze_seite(tab, f"meine_zeiten_{art}_{'hell' if thema == 'light' else 'dunkel'}", breite, hoehe)
    await _ansehen(tab, seed, "mia", 800, 1100, "light")
    p.pruefe("hoch: eine Spalte -- Kacheln, Buchungen, Abwesenheit, Monat", await tab.js(REIHENFOLGE), True)
    await _ansehen(tab, seed, "mia", 1280, 620, "light")
    await tab.bild("meine_zeiten_quer_fenster_hell")  # wie die Vorlage: nur das Fenster 1280 × 620
    p.pruefe("quer: zwei Spalten, rechts 400 px", await tab.js(SPALTEN), [400, True])
    p.pruefe("Kacheln ohne die laufende Zeit", await tab.js(
        "[...document.querySelectorAll('.zahl-karte')].map(k=>k.textContent)"), ["Heute0,75 h", "Diese Woche5,75 h", "Oktober31,25 h"])
    p.pruefe("Tage mit Kopfzeile und Summe, neueste zuerst", await tab.js(TAGE),
             [["Mi 14.10.", "0,75 h"], ["Di 13.10.", "5,00 h"], ["Sa 10.10.", "9,25 h"], ["Fr 09.10.", "8,25 h"], ["Do 08.10.", "8,00 h"]])
    p.pruefe("heute: Fahrzeit und die laufende Zeit „läuft seit 06:45“ ohne Stunden und ohne „⋮“", await tab.js(zeilen_des_tags("2026-10-14")),
             [["06:00–06:45", "Fahrzeit · AUF-2026-0001", "", "0,75 h", True],
              ["", "Baustellenzeit · AUF-2026-0001 · läuft seit 06:45", "", "", False]])
    p.pruefe("Zeile mit Tätigkeit und Notiz in der zweiten Zeile", await tab.js(zeilen_des_tags("2026-10-09")),
             [["06:15–07:00", "Fahrzeit · AUF-2026-0001", "", "0,75 h", True],
              ["07:00–15:00", "Baustellenzeit · AUF-2026-0001", "Dachdeckung · Rinne geprüft", "7,50 h", True]])
    p.pruefe("Abwesenheit und Monat", await tab.js(
        "[document.getElementById('abwText').textContent,document.getElementById('monatTitel').textContent,"
        "document.getElementById('monatSumme').textContent,document.getElementById('monatAnteile').textContent,"
        "document.getElementById('pdfKnopf').getAttribute('href')]"),
        ["Urlaub oder Krankheit beantragen. 1 offener Antrag.", "Oktober 2026", "31,25 h an 5 Tagen",
         "davon Fahrzeit 1,50 h · produktiv 29,75 h", "/api/field-view/timesheet.pdf?year=2026&month=10"])
    masse = await tab.js(MASSE)
    p.pruefe(f"Maße {masse[1]}", masse[0], [True, True, True, True])
    pdf = await tab.js("fetch(document.getElementById('pdfKnopf').href).then(r=>[r.status,r.headers.get('content-type')])")
    p.pruefe("Stundenzettel als PDF", pdf, [200, "application/pdf"])
    p.pruefe("quer: keine JS-Fehler", tab.fehler, [])

    # --- Nachtragen mit „Tag zusammen“ --------------------------------------------------------------------------------------------
    await tab.js("document.getElementById('nachtragenKnopf').click()")
    p.pruefe("Dialog „Zeit nachtragen“: Felder 52 px, Knöpfe 56 px, Schließen 48 px", await tab.js(
        "(h=>[document.getElementById('zdTitel').textContent,[...document.querySelectorAll('#zeitDialog .feld input,#zeitDialog .feld select')]"
        ".filter(e=>e.getClientRects().length).map(h),[...document.querySelectorAll('#zeitDialog .dialog-knoepfe .knopf')].map(h),"
        "h(document.getElementById('zdZu'))])(e=>Math.round(e.getBoundingClientRect().height))"),
        ["Zeit nachtragen", [52, 52, 52, 52, 52], [56, 56], 48])
    await tab.js(setze("zdDatum", "2026-10-13") + ";" + f"document.getElementById('zdAuftrag').value='{a}';"
                 + "document.getElementById('zdZeitart').value='workshop'")
    await tab.js(setze("zdVon", "12:00"))
    await tab.js(setze("zdBis", "16:15"))
    await tab.warten(VORSCHAU_DA)
    p.pruefe("Vorschau vom Server mit „Tag zusammen“", await tab.js(
        "[document.getElementById('zdVorschauZeile').textContent,document.getElementById('zdVorschauZahl').textContent,"
        "document.getElementById('zdSpeichern').textContent]"),
        ["Anwesend 4:15 h · Tag zusammen 9:15 h · Pause nach Zeitregel − 0:45 h", "3,50 h", "3,50 h nachtragen"])
    await tab.bild("meine_zeiten_nachtragen_tag_zusammen_hell")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('zdSpeichern').click()", "#tage")
    p.pruefe("nachgetragen wie die Vorschau, Ergebnis über den Buchungen", await tab.js(
        "[document.getElementById('zeitDialog').open,document.getElementById('ergebnis').textContent]"),
        [False, "Nachgetragen: anwesend 4:15 h · Tag zusammen 9:15 h · Pause nach Zeitregel − 0:45 h · gebucht 3,50 h"])
    p.pruefe("13.10.: zwei Buchungen, Summe 8,50 h", [await tab.js(zeilen_des_tags("2026-10-13")), (await tab.js(TAGE))[1]],
             [[["07:00–12:00", "Baustellenzeit · AUF-2026-0001", "", "5,00 h", True],
               ["12:00–16:15", "Werkstattzeit · AUF-2026-0001", "", "3,50 h", True]], ["Di 13.10.", "8,50 h"]])

    # --- Ändern: Bis 16:30, Mindestpause, die Fahrzeit des Tags bleibt -------------------------------------------------------------
    await tab.js(menue(seed["aendern"], "aendern"))
    p.pruefe("Ändern: vorbelegt", await tab.js(
        "['zdTitel','zdDatum','zdZeitart','zdVon','zdBis','zdAuftrag','zdTaetigkeit','zdNotiz','zdPause'].map(i=>{const e=document.getElementById(i);"
        "return e.tagName==='H2'?e.textContent:e.value})"),
        # seit 1.9.62 „Pause mindestens“ vorbelegt: eine Buchung von vor 1.9.62 mit der abgezogenen Pause (30)
        ["Zeit ändern", "2026-10-09", "site", "07:00", "15:00", str(a), "Dachdeckung", "Rinne geprüft", "30"])
    p.pruefe("Ändern: „Weitere Angaben“ zu, der Knopf nennt Tätigkeit, Notiz und Mindestpause", await tab.js(
        "[document.getElementById('zdWeitereFelder').hidden,document.getElementById('zdWeitere').textContent]"),
        [True, "Weitere Angaben · Dachdeckung · Rinne geprüft · Pause mindestens 0:30 h"])
    await tab.warten(VORSCHAU_DA)
    await tab.js(setze("zdBis", "16:30"))
    await tab.warten("document.getElementById('zdVorschauZahl').textContent==='8,75 h'")
    p.pruefe("Ändern: Vorschau aus dem Tag ohne die alte Fassung", await tab.js(
        "[document.getElementById('zdVorschauZeile').textContent,document.getElementById('zdSpeichern').textContent]"),
        ["Anwesend 9:30 h · Tag zusammen 10:15 h · Pause nach Zeitregel − 0:45 h", "8,75 h speichern"])
    await tab.js(setze("zdPause", "60"))
    await tab.warten("document.getElementById('zdVorschauZahl').textContent==='8,50 h'")
    p.pruefe("Pause mindestens 60 -> 1:00 h", await tab.js("document.getElementById('zdVorschauZeile').textContent"),
             "Anwesend 9:30 h · Tag zusammen 10:15 h · Pause nach Zeitregel − 1:00 h")
    await tab.js(setze("zdPause", ""))
    await tab.warten("document.getElementById('zdVorschauZahl').textContent==='8,75 h'")
    await tab.bild("meine_zeiten_aendern_hell")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('zdSpeichern').click()", "#tage")
    p.pruefe("geändert, die Fahrzeit des Tags unverändert", await tab.js(zeilen_des_tags("2026-10-09")),
             [["06:15–07:00", "Fahrzeit · AUF-2026-0001", "", "0,75 h", True],
              ["07:00–16:30", "Baustellenzeit · AUF-2026-0001", "Dachdeckung · Rinne geprüft", "8,75 h", True]])

    # --- seit 1.9.62: die eingetragene Mindestpause bleibt und belegt „Ändern“ vor -------------------------------------------------
    await tab.js(menue(seed["aendern"], "aendern"))
    p.pruefe("Ändern: „Pause mindestens“ leer gespeichert -> 0 vorbelegt", await tab.js("document.getElementById('zdPause').value"), "0")
    await tab.warten("document.getElementById('zdVorschauZahl').textContent==='8,75 h'")
    await tab.js(setze("zdPause", "60"))
    await tab.warten("document.getElementById('zdVorschauZahl').textContent==='8,50 h'")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('zdSpeichern').click()", "#tage")
    await tab.js(menue(seed["aendern"], "aendern"))
    p.pruefe("Ändern: mit der gemerkten Mindestpause 60 vorbelegt, der Knopf nennt sie", await tab.js(
        "[document.getElementById('zdPause').value,document.getElementById('zdWeitere').textContent,"
        "document.getElementById('zdPauseBisher').textContent]"),
        ["60", "Weitere Angaben · Dachdeckung · Rinne geprüft · Pause mindestens 1:00 h",
         "Bisher abgezogen: 1:00 h. Abgezogen wird die Pause nach Zeitregel, mindestens „Pause mindestens“."])
    await tab.warten("document.getElementById('zdVorschauZahl').textContent==='8,50 h'")
    p.pruefe("Vorschau mit der gemerkten Mindestpause", await tab.js("document.getElementById('zdVorschauZeile').textContent"),
             "Anwesend 9:30 h · Tag zusammen 10:15 h · Pause nach Zeitregel − 1:00 h")
    await tab.js("document.getElementById('zdWeitere').click()")
    await tab.bild("meine_zeiten_aendern_mindestpause_hell")
    await tab.js("document.getElementById('zdAbbrechen').click()")

    # --- Löschen mit Rückfrage, „Pausen neu rechnen“ --------------------------------------------------------------------------------
    await tab.js(menue(seed["erste"], "loeschen"))
    p.pruefe("Rückfrage auf der Seite", await tab.js(
        "[document.getElementById('loeschDialog').open,document.getElementById('ldTitel').textContent,document.getElementById('ldText').textContent]"),
        [True, "Buchung löschen?", "Baustellenzeit · AUF-2026-0001 · Sa 10.10. 06:00–13:00 · 6,50 h"])
    await tab.bild("meine_zeiten_loesch_rueckfrage_hell")
    await tab.js("document.getElementById('ldAbbrechen').click()")
    p.pruefe("Abbrechen lässt alles", await tab.js(f"!!document.querySelector('[data-zeile=\"{seed['erste']}\"]')"), True)
    await tab.js(menue(seed["erste"], "loeschen"))
    await tab.warte_auf_neu_geladene_liste("document.getElementById('ldLoeschen').click()", "#tage")
    await tab.js("document.querySelector('.tag-kopf[data-tag=\"2026-10-10\"]').scrollIntoView({block:'start'});window.scrollBy(0,-80)")
    await tab.bild("meine_zeiten_tag_pause_passt_nicht_hell")
    p.pruefe("nach dem Löschen: Hinweis am Tag, nichts von selbst gerechnet", await tab.js(
        "[document.querySelector('.pause-hinweis[data-pause=\"2026-10-10\"] .pause-text').textContent,"
        + zeilen_des_tags("2026-10-10") + "]"),
        ["Pause abgezogen 0:15 h · nach Zeitregel 0:00 h", [["13:00–16:00", "Baustellenzeit · AUF-2026-0001", "", "2,75 h", True]]])
    await tab.js("document.querySelector('[data-aktion=\"pausen\"][data-tag=\"2026-10-10\"]').click()")
    await tab.warten("!document.getElementById('pv-2026-10-10').hidden&&document.querySelector('#pv-2026-10-10 [data-pv]')")
    p.pruefe("Vorschau je Buchung alt -> neu", await tab.js("[...document.querySelectorAll('#pv-2026-10-10 [data-pv]')].map(e=>e.textContent)"),
             ["Baustellenzeit 13:00–16:00: Pause 0:15 h → 0:00 h · gebucht 2,75 h → 3,00 h"])
    await tab.js("document.querySelector('.tag-kopf[data-tag=\"2026-10-10\"]').scrollIntoView({block:'start'});window.scrollBy(0,-80)")
    await tab.bild("meine_zeiten_pausen_neu_rechnen_hell")
    await tab.warte_auf_neu_geladene_liste("document.querySelector('[data-aktion=\"pausen-buchen\"]').click()", "#tage")
    p.pruefe("genau die Vorschau gebucht, Hinweis weg", await tab.js(
        "[!!document.querySelector('.pause-hinweis[data-pause=\"2026-10-10\"]'),document.getElementById('ergebnis').textContent,"
        + zeilen_des_tags("2026-10-10") + "]"),
        [False, "Pausen am Sa 10.10. neu gerechnet: Pause 0:15 h → 0:00 h",
         [["13:00–16:00", "Baustellenzeit · AUF-2026-0001", "", "3,00 h", True]]])
    verlauf = await tab.js(f"fetch('/api/time-entries?employee_id={seed['mia']}&start_date=2026-10-10&end_date=2026-10-10')"
                           ".then(r=>r.json()).then(l=>l.map(e=>[e.pause,Number(e.hours)]))")
    p.pruefe("Server: Pause 0, gebucht 3,00", verlauf, [[0, 3.0]])

    # --- Kolonne: ändern, Nachtrag, löschen --------------------------------------------------------------------------------------
    # die erste Zeile unter der Kopfzeile des 08.10. (dazwischen kann ein Hinweis zur Pause stehen)
    zeile_gruppe = await tab.js("(()=>{let e=document.querySelector('#tage .tag-kopf[data-tag=\"2026-10-08\"]').nextElementSibling;"
                                "while(e&&!e.classList.contains('zeile'))e=e.nextElementSibling;return e.dataset.zeile})()")
    await tab.js(menue(zeile_gruppe, "kolonne-aendern"))
    # seit 1.9.63 mit Von und Bis (die Kolonnenbuchung der Testdaten ist eine Dauer von 8 h -- Hinweis, Von/Bis leer)
    p.pruefe("Kolonnenbuchung ändern: Mitglieder, vorbelegt", await tab.js(
        "[document.getElementById('kdTitel').textContent,document.getElementById('kdMitgliederText').textContent,"
        "document.getElementById('kdVon').value,document.getElementById('kdBis').value,document.getElementById('kdPause').value,"
        "document.getElementById('kdHinweis').textContent,document.getElementById('kdKolonneFeld').hidden]"),
        ["Kolonnenbuchung ändern", "Kolonne Nord: Mia Monteurin, Tom Mitglied", "", "", "0",
         "Diese Kolonnenbuchung hat keine Uhrzeiten (8,00 h je Person) – trag Von und Bis ein, dann rechnet der Server je Person neu.", True])
    await tab.js(setze("kdVon", "07:00") + ";" + setze("kdBis", "15:00"))
    await tab.warten("document.getElementById('kdVorschauZeile').textContent.includes('Tom')")
    p.pruefe("Kolonnenbuchung ändern: Vorschau je Mitglied", await tab.js("document.getElementById('kdVorschauZeile').textContent"),
             "Mia Monteurin 7,50 h · Tom Mitglied 7,50 h")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('kdSpeichern').click()", "#tage")
    p.pruefe("für die Kolonne geändert", [await tab.js("document.getElementById('ergebnis').textContent"), (await tab.js(TAGE))[4]],
             ["Kolonnenbuchung geändert: Mia Monteurin 7,50 h · Tom Mitglied 7,50 h", ["Do 08.10.", "7,50 h"]])
    await tab.js("document.getElementById('kolonneMenueKnopf').click()")
    await tab.js("document.getElementById('kolonneNachtragen').click()")
    p.pruefe("Nachtrag für die Kolonne: Kolonne Nord, Mia (ich) fest, Tom angehakt", await tab.js(
        "[document.getElementById('kdTitel').textContent,document.getElementById('kdKolonne').selectedOptions[0].textContent,"
        "[...document.querySelectorAll('#kdMitglieder .mitglied')].map(l=>[l.textContent,l.querySelector('input').checked,l.querySelector('input').disabled])]"),
        ["Nachtrag für die Kolonne", "Kolonne Nord", [["Mia Monteurin (ich)", True, True], ["Tom Mitglied", True, False]]])
    # seit 1.9.63: eine Von/Bis-Angabe für alle angehakten, Pause und Rundung je Person nach ihrem Tag (Tom hat am Morgen Fahrzeit)
    await tab.js(setze("kdDatum", "2026-10-07") + f";document.getElementById('kdAuftrag').value='{a}';"
                 + setze("kdVon", "07:00") + ";" + setze("kdBis", "12:30"))
    await tab.warten("document.getElementById('kdVorschauZeile').textContent.includes('Tag zusammen')")
    p.pruefe("Nachtrag für die Kolonne: Vorschau je Mitglied nach seinem Tag", await tab.js("document.getElementById('kdVorschauZeile').textContent"),
             "Mia Monteurin 5,50 h · Tom Mitglied 5,00 h (Tag zusammen 6:15 h)")
    await tab.bild("meine_zeiten_kolonne_nachtrag_vorschau_hell")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('kdSpeichern').click()", "#tage")
    p.pruefe("Nachtrag für die Kolonne gebucht", [await tab.js("document.getElementById('ergebnis').textContent"),
                                                  (await tab.js(TAGE))[-1]],
             ["Für die Kolonne nachgetragen: Mia Monteurin 5,50 h · Tom Mitglied 5,00 h", ["Mi 07.10.", "5,50 h"]])
    await tab.js(menue(zeile_gruppe, "kolonne-loeschen"))
    p.pruefe("Kolonnenbuchung löschen: Rückfrage", await tab.js(
        "[document.getElementById('ldTitel').textContent,document.getElementById('ldFolge').textContent]"),
        ["Kolonnenbuchung löschen?", "Selbst geänderte Buchungen einzelner Mitglieder bleiben bestehen."])
    await tab.warte_auf_neu_geladene_liste("document.getElementById('ldLoeschen').click()", "#tage")
    p.pruefe("Kolonnenbuchung gelöscht", [await tab.js("document.getElementById('ergebnis').textContent"),
                                         any(t[0] == "Do 08.10." for t in await tab.js(TAGE))], ["Kolonnenbuchung gelöscht.", False])

    # --- Monat umschalten: September abgeschlossen --------------------------------------------------------------------------------
    await tab.warte_auf_neu_geladene_liste("document.getElementById('monatZurueck').click()", "#tage")
    p.pruefe("September: abgeschlossen, kein „⋮“, Kachel und Karte des Monats", await tab.js(
        "[document.getElementById('monatName').textContent,"
        + TAGE + ",document.querySelector('#tage .tag-mitte').textContent,document.querySelectorAll('#tage .knopf-symbol').length,"
        "document.getElementById('kachelMonatName').textContent,document.getElementById('monatSumme').textContent]"),
        ["September 2026", [["Di 29.09.", "7,50 h"]], "abgeschlossen", 0, "September", "7,50 h an 1 Tag"])
    await tab.warte_auf_neu_geladene_liste("document.getElementById('monatVor').click()", "#tage")
    p.pruefe("zurück im Oktober, › gesperrt", await tab.js(
        "[document.getElementById('monatName').textContent,document.getElementById('monatVor').disabled]"), ["Oktober 2026", True])

    # --- Abwesenheit: Antrag, Zurückziehen mit Rückfrage ----------------------------------------------------------------------------
    await tab.js("document.getElementById('antragKnopf').click()")
    await tab.js(setze("adVon", "2026-12-21") + ";" + setze("adBis", "2026-12-23"))
    await tab.warten("document.getElementById('adArt').options.length>0")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('adSenden').click()", "#adAntraege")
    p.pruefe("Antrag gesendet", await tab.js(
        "[document.getElementById('adErgebnis').textContent,document.getElementById('abwText').textContent,"
        "document.querySelectorAll('#adAntraege .antrag').length]"),
        ["Antrag wurde gesendet.", "Urlaub oder Krankheit beantragen. 2 offene Anträge.", 2])
    await tab.js("document.querySelector('#adAntraege [data-antrag=\"fragen\"]').click()")
    p.pruefe("Zurückziehen: Rückfrage in der Zeile", await tab.js(
        "[...document.querySelectorAll('#adAntraege [data-antrag]')].map(b=>b.textContent)"), ["Abbrechen", "Zurückziehen", "Zurückziehen"])
    await tab.warte_auf_neu_geladene_liste("document.querySelector('#adAntraege [data-antrag=\"ja\"]').click()", "#adAntraege")
    p.pruefe("zurückgezogen", await tab.js("document.getElementById('abwText').textContent"),
             "Urlaub oder Krankheit beantragen. 1 offener Antrag.")
    await tab.js("document.getElementById('abwDialog').close()")
    p.pruefe("Mia: keine JS-Fehler", tab.fehler, [])

    # --- Tom: „gebucht von“; Ole: Zeit von früher; Pia: ohne Mitarbeiter -------------------------------------------------------------
    await _ansehen(tab, seed, "tom", 1280, 620, "light")
    p.pruefe("Tom: Nachtrag der Kolonne „gebucht von Mia Monteurin“", await tab.js(zeilen_des_tags("2026-10-07")),
             [["06:15–07:00", "Fahrzeit · AUF-2026-0001", "", "0,75 h", True],
              ["07:00–12:30", "Baustellenzeit · AUF-2026-0001", "gebucht von Mia Monteurin", "5,00 h", True]])
    await _ansehen(tab, seed, "ole", 1280, 620, "light")
    p.pruefe("Ole: läuft seit gestern, Weg zu „Heute“", await tab.js(
        "[document.querySelector('.zeile .zeile-text span').textContent,document.querySelector('.zeile a.knopf').textContent,"
        "document.querySelector('.zeile a.knopf').getAttribute('href')]"),
        ["Baustellenzeit · AUF-2026-0001 · läuft seit 06:45", "Feierabend auf „Heute“ eintragen", "/mobil"])
    await tab.bild("meine_zeiten_zeit_von_frueher_hell")
    await _ansehen(tab, seed, "pia", 1280, 620, "light", bereit=HINWEIS_BEREIT)
    p.pruefe("Pia: Hinweis ohne Mitarbeiter", await tab.js("document.getElementById('ladeHinweis').textContent.includes('Mitarbeiter')"), True)
    p.pruefe("Tom/Ole/Pia: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="„Meine Zeiten“ der Monteurin (1.9.59)", uhr="2026-10-14 10:00"))
