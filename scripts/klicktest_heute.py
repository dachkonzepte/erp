"""Klicktest: „Heute“ für die Monteurin (seit 1.9.45, Stufe 4, R2) -- /mobil nach den Vorlagen heute-quer, heute-hoch, heute-gestern.

Befüllt: Objekt „Halle Nord“ (Hallenbau GmbH, Werkstr. 5, 52531 Übach-Palenberg) mit Dachfläche Nord und Prüfvorlage, Auftrag A
(„Wartung“) und B („Rinne erneuern“); Plantafel: A gestern bis übermorgen (zwei Abschnitte), B in 5–6 Tagen; Kolonne mit Kai
(Kolonnenführer) und Tom. Mia: Zeit läuft seit 06:45 auf A, ihr Wartungsbericht (Entwurf) und eine offene Checkliste an A. Ole: Zeit von
gestern 06:45 offen. Lea: nichts läuft. Kai und Tom: Gruppenzeit seit 07:00. Feste Uhr 10:00.

    Mia quer (1280 × 620)  zwei Spalten, rechts 420 px; Arbeitszeit „Baustellenzeit seit 06:45“, Dauer 3:15 h, Knöpfe 64 px; eine Karte
                           für A (zwei Abschnitte) mit Zeitraum, Route, Bericht mit „Weiter“ 56 px, Checkliste mit Pfeil; Offen: Berichte 1,
                           Checklisten 1, keine Mängel; Nächste Tage: A ab morgen „Fortsetzung“, B; heute nicht; hell und dunkel
    Mia hoch (800 × 1100)  eine Spalte in der Reihenfolge Arbeitszeit, Einsatz, Offen, Nächste Tage; hell und dunkel
    Mia                    Zeitart wechseln -> Fahrzeit seit 10:00, zwei Buchungen ohne Lücke; Feierabend -> nichts läuft
    Ole                    „Deine Zeit von gestern läuft noch“, Feld 64 px, 16:00 -> Vorschau wie der Server, Feierabend eintragen ->
                           gebucht wie die Vorschau; Karte „Arbeitszeit“ mit gesperrtem „Arbeitsbeginn buchen“; „Heute und nächste Tage“
    Lea                    nichts läuft: Auftrag A vorbelegt, Kacheln 64 px mit „Vorschlag“, Start -> läuft
    Tom / Kai              Mitglied ohne Knopf mit „stoppt Kai Kolonne“ / Kolonnenführer mit „Feierabend für die Gruppe“
    überall                Zeilen ≥ 56 px, Knöpfe ≥ 48 px, Hauptknöpfe 64 px; Reiter „Heute“; keine JS-Fehler

Die Bilder (heute_*.png) liegen im Ordner der Screenshots.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_heute.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD]
        [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

WOCHENTAG = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def tag_kurz(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{WOCHENTAG[d.weekday()]} {d:%d.%m.}"


def zeitraum(von: str, bis: str) -> str:
    a, b = date.fromisoformat(von), date.fromisoformat(bis)
    if a == b:
        return f"{a:%d.%m.}"
    if (a.year, a.month) == (b.year, b.month):
        return f"{a:%d}.–{b:%d.%m.}"
    if a.year == b.year:
        return f"{a:%d.%m.}–{b:%d.%m.}"
    return f"{a:%d.%m.%Y}–{b:%d.%m.%Y}"


def spanne(von: str, bis: str) -> str:
    return tag_kurz(von) if von == bis else f"{tag_kurz(von)}–{tag_kurz(bis)}"


def befuellen(db, k):
    from datetime import datetime, time, timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.checklist_templates import add_field, create_template, publish_draft
    from app.checklists import create_checklist
    from app.inspection_templates import create_template as create_inspection_template, create_template_item
    from app.models import (
        AppUser, Customer, Employee, Order, OrderItem, PlanningSlot, Project, Property, RoofArea, Team, TeamEmployee,
        WorkPreparationTeamAssignment, WorkPreparationTeamEmployee,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.service_reports import create_report
    from app.time_tracking import start_group_timer, start_timer
    from app.work_preparation import ensure_preparation

    heute = berlin_today()
    leute = {}
    for nr, (vor, nach) in enumerate([("Mia", "Monteurin"), ("Ole", "Offen"), ("Lea", "Leer"), ("Kai", "Kolonne"), ("Tom", "Mitglied")], 1):
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
    flaeche = RoofArea(property_id=halle.id, name="Dachfläche Nord", roof_type="flachdach")
    db.add(flaeche); db.flush()
    vorlage = create_inspection_template(db, "Flachdach-Wartung", roof_type="flachdach")
    for text in ("Abdichtung Sichtprüfung", "Gully frei", "Attika"):
        create_template_item(db, vorlage["id"], text, "ja_nein", required=True)

    def auftrag(nr, titel):
        projekt = Project(project_number=f"P-KT-H{nr}", name=titel, customer_id=kunde.id, property_id=halle.id,
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        o = Order(order_number=f"AUF-2026-000{nr}", project_id=projekt.id, source_quote_id=900 + nr, quote_number_snapshot=f"A-KT-{nr}",
                  title=titel, customer_name=kunde.name, property_name=halle.name, property_address="Werkstr. 5\n52531 Übach-Palenberg")
        db.add(o); db.flush()
        db.add(OrderItem(order_id=o.id, sort_order=10, position_number="1", short_text="Wartung", quantity=Decimal("1"), unit="psch",
                         unit_price=Decimal("1")))
        db.commit()
        return o

    a, b = auftrag(1, "Wartung"), auftrag(2, "Rinne erneuern")
    team = Team(name="Kolonne Nord", active=True)
    db.add(team); db.flush()
    db.add_all([TeamEmployee(team_id=team.id, employee_id=leute["kai"].id, is_crew_leader=True),
                TeamEmployee(team_id=team.id, employee_id=leute["tom"].id)])
    for o, abschnitte in ((a, [(heute - timedelta(days=1), heute + timedelta(days=1)), (heute, heute + timedelta(days=2))]),
                          (b, [(heute + timedelta(days=5), heute + timedelta(days=6))])):
        prep = ensure_preparation(db, o.id)
        zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
        db.add(zuordnung); db.flush()
        for e in leute.values():
            db.add(WorkPreparationTeamEmployee(assignment_id=zuordnung.id, employee_id=e.id, employee_name_snapshot=e.first_name))
        for von, bis in abschnitte:
            db.add(PlanningSlot(preparation_id=prep.id, team_assignment_id=zuordnung.id, start_date=von, end_date=bis))
    db.commit()

    start_timer(db, employee_id=leute["mia"].id, order_id=a.id, started_at=datetime.combine(heute, time(6, 45)))
    start_timer(db, employee_id=leute["ole"].id, order_id=a.id, started_at=datetime.combine(heute - timedelta(days=1), time(6, 45)))
    start_group_timer(db, employee_ids=[leute["kai"].id, leute["tom"].id], team_id=team.id, actor_employee_id=leute["kai"].id,
                      is_admin=False, order_id=a.id, started_at=datetime.combine(heute, time(7)))
    bericht = create_report(db, a.id, "wartung", created_by_employee_id=leute["mia"].id, roof_area_ids=[flaeche.id], performed_at=heute)
    cl_vorlage = create_template(db, label="Sicherheitscheck", contexts=["auftrag"], field_readable=True)
    add_field(db, cl_vorlage["draft_version_id"], {"field_type": "ja_nein", "label": "Absturzsicherung geprüft", "field_key": "abs",
                                                   "required": True})
    publish_draft(db, cl_vorlage["id"])
    checkliste = create_checklist(db, template_id=cl_vorlage["id"], context_type="auftrag", order_id=a.id,
                                  created_by_employee_id=leute["mia"].id)
    return {"a": a.id, "b": b.id, "bericht": bericht["id"], "checkliste": checkliste["id"], "heute": heute.isoformat(),
            "gestern": (heute - timedelta(days=1)).isoformat(), "morgen": (heute + timedelta(days=1)).isoformat(),
            "uebermorgen": (heute + timedelta(days=2)).isoformat(), "b_von": (heute + timedelta(days=5)).isoformat(),
            "b_bis": (heute + timedelta(days=6)).isoformat(), "mia": leute["mia"].id, "ole": leute["ole"].id,
            "cookies": {n: k.cookies(u) for n, u in benutzer.items()}}


BEREIT = "document.getElementById('arbeitszeit').innerHTML!==''&&!document.getElementById('naechsteKarte').hidden"

# Maße: jede Zeile, jeder Knopf, jeder Link mit Rolle einer Bedienung in „Heute“ (sichtbar)
# [Zeilen ≥ 56, Knöpfe und Links ≥ 48, Hauptknöpfe (und das Feld der Uhrzeit) 64, „Weiter“ 56] -- dazu die gemessenen Werte
MASSE = """(()=>{const h=e=>Math.round(e.getBoundingClientRect().height),sicht=e=>e.getClientRects().length>0;
const q=s=>[...document.querySelectorAll('#heute '+s)].filter(sicht);
const z=q('.zeile').map(h),k=q('.knopf,.route,.einsatz-wege a').map(h),
haupt=q('#feierabendKnopf,#wechselKnopf,#feierabendGruppe,#endeKnopf,.knopf-gesperrt,#startKacheln .knopf,#endeZeit').map(h),
w=q('.zeile-bericht .knopf-aktion').map(h);
return [[z.every(x=>x>=56),k.every(x=>x>=48),haupt.length>0&&haupt.every(x=>x===64),w.every(x=>x===56)],{z,k,haupt,w}]})()"""

SPALTEN = """(()=>{const r=id=>document.getElementById(id).getBoundingClientRect();const l=r('heuteLinks'),re=r('heuteRechts');
return [Math.round(re.width),l.left<re.left&&Math.abs(l.top-re.top)<2]})()"""

REIHENFOLGE = """(()=>{const y=s=>Math.round(document.querySelector(s).getBoundingClientRect().top);
return [y('#arbeitszeit .heute-karte'),y('[data-einsatz]'),y('#offenKarte'),y('#naechsteKarte')]})()"""


async def _ansehen(tab, seed, wer, breite, hoehe, thema):
    """Als wer anmelden, Fenster setzen, /mobil öffnen, Thema setzen (erst auf der Seite des ERP möglich) und neu laden."""
    await tab.anmelden(seed["cookies"][wer])
    await tab.fenster(breite, hoehe)
    await tab.oeffnen("/mobil", BEREIT)
    await tab.js(f"localStorage.setItem('erp_theme','{thema}')")
    await tab.oeffnen("/mobil", BEREIT)
    p_thema = await tab.js("document.documentElement.dataset.theme")
    assert p_thema == thema, (wer, thema, p_thema)


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    a = seed["a"]

    # --- Mia, quer und hoch, hell und dunkel ---
    for breite, hoehe, art in ((1280, 620, "quer"), (800, 1100, "hoch")):
        for thema in ("light", "dark"):
            await _ansehen(tab, seed, "mia", breite, hoehe, thema)
            await tab.bild(f"heute_{art}_{'hell' if thema == 'light' else 'dunkel'}")
    await _ansehen(tab, seed, "mia", 1280, 620, "light")
    p.pruefe("Reiter „Heute“ aktiv", await tab.js("document.querySelector('.mobile-nav-reiter.active').textContent"), "Heute")
    p.pruefe("quer: zwei Spalten, rechts 420 px", await tab.js(SPALTEN), [420, True])
    p.pruefe("Zeitart wechseln: Kacheln erst nach dem Klick", await tab.js("document.getElementById('wechselKacheln').getClientRects().length"), 0)
    p.pruefe("Arbeitszeit läuft", await tab.js(
        "[...document.querySelectorAll('#arbeitszeit .eb,#arbeitszeit .laeuft-pill,#arbeitszeit .zeit-titel,#arbeitszeit .zeit-sub,#zeitDauer')]"
        ".map(e=>e.textContent)"), [f"Arbeitszeit · {tag_kurz(seed['heute'])}", "läuft", "Baustellenzeit seit 06:45",
                                     "AUF-2026-0001 · Halle Nord", "3:15 h"])
    p.pruefe("Einsatz: eine Karte für A mit Zeitraum, Objekt, Kunde · Adresse, Route", await tab.js(
        "[...document.querySelectorAll('[data-einsatz]')].map(k=>[k.querySelector('.eb').textContent,k.querySelector('h2').textContent,"
        "k.querySelector('.einsatz-sub').textContent,k.querySelector('.route').href])"),
        [[f"Heutiger Einsatz · {zeitraum(seed['gestern'], seed['uebermorgen'])}", "Halle Nord",
          "Hallenbau GmbH · Werkstr. 5, 52531 Übach-Palenberg",
          "https://www.google.com/maps/search/?api=1&query=Werkstr.%205%2C%2052531%20%C3%9Cbach-Palenberg"]])
    p.pruefe("Einsatz: Bericht mit „noch 3 offen“ und „Weiter“, Checkliste mit „noch 1 offen“ und Pfeil", await tab.js(
        "[...document.querySelectorAll('[data-einsatz] .zeile')].map(z=>[z.querySelector('.zeile-titel').textContent,"
        "z.querySelector('.zeile-sub').textContent,(z.querySelector('.knopf-aktion')||{}).textContent||null,!!z.querySelector('.pfeil'),"
        "(z.querySelector('a')||z).getAttribute('href')])"),
        [["Wartungsbericht · Dachfläche Nord", "Entwurf · noch 3 offen", "Weiter", False, f"/orders/{a}/service-reports?report={seed['bericht']}"],
         ["Sicherheitscheck", "Entwurf · noch 1 offen", None, True, f"/checklisten/{seed['checkliste']}"]])
    p.pruefe("Weg zum Anlegen eines Berichts", await tab.js("document.querySelector('.einsatz-wege a').getAttribute('href')"),
             f"/orders/{a}/service-reports")
    p.pruefe("Offen: Berichte 1, Checklisten 1, keine leere Gruppe, Zeilen führen zur Liste", await tab.js(
        "[...document.querySelectorAll('#offenZeilen .zeile')].map(z=>[z.querySelector('.zeile-titel').textContent,"
        "z.querySelector('.zahl-pill').textContent,z.getAttribute('href'),!!document.querySelector(z.getAttribute('href'))])"),
        [["Berichte", "1", "#offene-berichte", True], ["Checklisten", "1", "#offene-checklisten", True]])
    p.pruefe("Nächste Tage: A ab morgen in einer Zeile „Fortsetzung“, B; heute nicht", await tab.js(
        "[document.getElementById('naechsteTitel').textContent,[...document.querySelectorAll('#naechsteZeilen .zeile')].map(z=>z.textContent)]"),
        ["Nächste Tage", [f"{spanne(seed['morgen'], seed['uebermorgen'])}Halle Nord · Fortsetzung",
                          f"{spanne(seed['b_von'], seed['b_bis'])}Halle Nord · Rinne erneuern"]])
    masse = await tab.js(MASSE)
    p.pruefe(f"Maße quer {masse[1]}", masse[0], [True, True, True, True])
    p.pruefe("Mia quer: keine JS-Fehler", tab.fehler, [])

    await _ansehen(tab, seed, "mia", 800, 1100, "light")
    p.pruefe("hoch: eine Spalte in der Reihenfolge Arbeitszeit, Einsatz, Offen, Nächste Tage",
             await tab.js(f"(y=>y.every((v,i)=>i===0||v>y[i-1]))({REIHENFOLGE})"), True)

    # --- Mia: Zeitart wechseln, dann Feierabend ---
    await tab.js("document.getElementById('wechselKnopf').click()")
    p.pruefe("Zeitart wechseln zeigt die anderen Zeitarten", await tab.js(
        "[...document.querySelectorAll('#wechselKacheln [data-zeitart]')].map(b=>b.dataset.zeitart).includes('travel')"), True)
    await tab.warte_auf_neu_geladene_liste("document.querySelector('#wechselKacheln [data-zeitart=\"travel\"]').click()", "#arbeitszeit")
    p.pruefe("nach dem Wechsel: Fahrzeit seit 10:00", await tab.js("document.querySelector('#arbeitszeit .zeit-titel').textContent"),
             "Fahrzeit seit 10:00")
    zeilen = await tab.js(f"fetch('/api/time-entries?employee_id={seed['mia']}&start_date={seed['heute']}&end_date={seed['heute']}')"
                          ".then(r=>r.json()).then(l=>l.sort((x,y)=>x.started_at<y.started_at?-1:1).map(e=>[e.entry_type,e.status,e.started_at,e.ended_at]))")
    # die Uhr der Instanz läuft ab 10:00 weiter: „ohne Lücke“ heißt Ende der ersten = Beginn der zweiten
    p.pruefe("zwei Buchungen ohne Lücke und ohne Überschneidung",
             [[z[0], z[1], z[2]] for z in zeilen or []] + [bool(zeilen) and zeilen[0][3] == zeilen[1][2], bool(zeilen) and zeilen[1][3]],
             [["site", "booked", f"{seed['heute']}T06:45:00"], ["travel", "running", (zeilen or [[None] * 4] * 2)[1][2]], True, None])
    # berlin_now() ist sekundengenau: ein Feierabend in derselben Sekunde wie der Wechsel endete vor dem Beginn (422) -- erst weiter
    t = await tab.js("performance.now()")
    await tab.warten(f"performance.now()>{t + 1100}")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('feierabendKnopf').click()", "#arbeitszeit")
    p.pruefe("Feierabend: keine Meldung", await tab.js("(document.getElementById('zeitStatus')||{}).textContent||''"), "")
    p.pruefe("nach dem Feierabend: nichts läuft, Auftrag vorbelegt", await tab.js("document.getElementById('startAuftrag').value"), str(a))
    p.pruefe("Mia: keine JS-Fehler", tab.fehler, [])

    # --- Ole: Zeit von gestern offen ---
    for breite, hoehe, art in ((1280, 620, "quer"), (800, 1100, "hoch")):
        await _ansehen(tab, seed, "ole", breite, hoehe, "light")
        await tab.bild(f"heute_gestern_offen_{art}_hell")
    await _ansehen(tab, seed, "ole", 1280, 620, "light")
    p.pruefe("Ole: Signalkarte mit Titel, Zeile und Feld", await tab.js(
        "[document.querySelector('.signal-eb').textContent,document.getElementById('offenTitelZeit').textContent,"
        "document.querySelector('.signal-sub').textContent,document.querySelector('label[for=endeZeit]').childNodes[0].textContent]"),
        ["Wartet auf dich", "Deine Zeit von gestern läuft noch",
         f"Baustellenzeit seit {tag_kurz(seed['gestern'])}, 06:45 · AUF-2026-0001 · Halle Nord", "Feierabend gestern um"])
    masse = await tab.js(MASSE)
    p.pruefe(f"Maße Zeit von gestern {masse[1]}", masse[0], [True, True, True, True])
    p.pruefe("Ole: Arbeitszeit heute gesperrt, Einsatz in „Heute und nächste Tage“", await tab.js(
        "[document.querySelector('.knopf-gesperrt').disabled,document.querySelector('.zeit-gesperrt .zeit-sub').textContent,"
        "document.querySelectorAll('[data-einsatz]').length,document.getElementById('naechsteTitel').textContent]"),
        [True, "Heute startest du, sobald gestern abgeschlossen ist.", 0, "Heute und nächste Tage"])
    await tab.js("(f=>{f.value='16:00';f.dispatchEvent(new Event('input'))})(document.getElementById('endeZeit'))")
    await tab.warten("document.querySelector('#endeVorschau .gebucht')")
    vorschau = await tab.js("[...document.querySelectorAll('#endeVorschau span')].map(s=>s.textContent)")
    p.pruefe("Ole: Vorschau vom Server", vorschau, ["Anwesend 9:15 h · Pause nach Zeitregel − 0:45 h", "Gebucht werden 8,50 h"])
    await tab.bild("heute_gestern_offen_vorschau_hell")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('endeKnopf').click()", "#arbeitszeit")
    gebucht = await tab.js(f"fetch('/api/time-entries?employee_id={seed['ole']}&start_date={seed['gestern']}&end_date={seed['gestern']}')"
                           ".then(r=>r.json()).then(l=>l.map(e=>[e.status,Number(e.anwesend),e.pause,Number(e.hours)]))")
    p.pruefe("Ole: gebucht wie die Vorschau", gebucht, [["booked", 9.25, 45, 8.5]])
    p.pruefe("Ole: danach startet heute", await tab.js("!!document.getElementById('startKacheln')"), True)
    p.pruefe("Ole: keine JS-Fehler", tab.fehler, [])

    # --- Lea: nichts läuft ---
    await _ansehen(tab, seed, "lea", 1280, 620, "light")
    await tab.bild("heute_nichts_laeuft_quer_hell")
    p.pruefe("Lea: Auftrag A vorbelegt, Kacheln mit Vorschlag", await tab.js(
        "[document.getElementById('startAuftrag').value,document.querySelectorAll('#startKacheln .vorschlag').length]"), [str(a), 1])
    masse = await tab.js(MASSE)
    p.pruefe(f"Maße nichts läuft {masse[1]}", masse[0], [True, True, True, True])
    await tab.warte_auf_neu_geladene_liste("document.querySelector('#startKacheln [data-zeitart=\"site\"]').click()", "#arbeitszeit")
    p.pruefe("Lea: gestartet", await tab.js("document.querySelector('#arbeitszeit .zeit-titel').textContent"), "Baustellenzeit seit 10:00")
    p.pruefe("Lea: keine JS-Fehler", tab.fehler, [])

    # --- Tom (Mitglied) und Kai (Kolonnenführer) ---
    for breite, hoehe, art in ((1280, 620, "quer"), (800, 1100, "hoch")):
        await _ansehen(tab, seed, "tom", breite, hoehe, "light")
        await tab.bild(f"heute_gruppenmitglied_{art}_hell")
    p.pruefe("Tom: ohne Knopf, „stoppt Kai Kolonne“", await tab.js(
        "[document.querySelectorAll('#arbeitszeit button').length,document.getElementById('stopptHinweis').textContent]"),
        [0, "Gruppenzeit · stoppt Kai Kolonne"])
    await _ansehen(tab, seed, "kai", 1280, 620, "light")
    p.pruefe("Kai: Feierabend für die Gruppe, kein Zeitart wechseln", await tab.js(
        "[document.getElementById('feierabendGruppe').textContent,!!document.getElementById('wechselKnopf')]"),
        ["Feierabend für die Gruppe", False])
    p.pruefe("Tom/Kai: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="„Heute“ für die Monteurin (1.9.45)", uhr="10:00"))
