"""Klicktest: „Heute“ für die Monteurin (seit 1.9.45, Stufe 4, R2) -- /mobil nach den Vorlagen heute-quer, heute-hoch, heute-gestern.

Befüllt: Objekt „Halle Nord“ (Hallenbau GmbH, Werkstr. 5, 52531 Übach-Palenberg) mit Dachfläche Nord und Prüfvorlage, Auftrag A
(„Wartung“) und B („Rinne erneuern“); Plantafel: A gestern bis übermorgen (zwei Abschnitte), B in 5–6 Tagen; Kolonne mit Kai
(Kolonnenführer) und Tom. Mia: Zeit läuft seit 06:45 auf A, ihr Wartungsbericht (Entwurf) und eine offene Checkliste an A. Ole: Zeit von
gestern 06:45 offen. Lea: nichts läuft. Kai und Tom: Gruppenzeit seit 07:00. Feste Uhr 10:00.

    Mia quer (1280 × 620)  zwei Spalten, rechts 420 px; Arbeitszeit „Baustellenzeit seit 06:45“, Dauer 3:15 h, Knöpfe 64 px; eine Karte
                           für A (zwei Abschnitte) mit Zeitraum, Route, Bericht mit „Weiter“ 56 px, Checkliste mit Pfeil; Offen: Berichte 1,
                           Checklisten 1, keine Mängel; Nächste Tage: A ab morgen „Fortsetzung“, B; heute nicht; hell und dunkel
    Mia hoch (800 × 1100)  eine Spalte in der Reihenfolge Arbeitszeit, Einsatz, Offen, Nächste Tage; hell und dunkel (Bilder bis zum
                           Seitenende)
    Mia Offen (seit 1.9.49) „Heute“ ohne Listen, endet mit „Nächste Tage“; die Zeilen von „Offen“ (Berichte, Checklisten, Wartungen an
                           meinen Objekten) springen auf /mobil/offen#…; dort Kopf „Heute / Offen“, genau die drei nicht leeren
                           Abschnitte, „Wartung durchführen“; hell und dunkel
    Mia                    Zeitart wechseln -> Fahrzeit seit 10:00, zwei Buchungen ohne Lücke; Feierabend -> nichts läuft
    seit 1.9.50            Checkliste als „Checkliste <Name>“, „Bericht anlegen“ und „Checklisten zum Auftrag“ neutrale Knöpfe 48 px;
                           Ole hoch 16 px zwischen den Karten; Feldrahmen auf der Signalfläche ≥ 3 : 1 hell und dunkel
    Ole                    „Deine Zeit von gestern läuft noch“, Feld 64 px, 15:45 -> Vorschau wie der Server, Feierabend eintragen ->
                           gebucht wie die Vorschau; Karte „Arbeitszeit“ mit gesperrtem „Arbeitsbeginn buchen“; „Heute und nächste Tage“
    Lea                    nichts läuft: Auftrag A vorbelegt, Kacheln 64 px mit „Vorschlag“; seit 1.9.58 quer 3 Spalten, „⋮“ 48 px nur mit
                           „Mit Tätigkeit starten“, Dialog (Felder 52 px, Knöpfe 56 px) mit A und Baustellenzeit, Tätigkeit „Dachdeckung“
                           -> läuft mit Tätigkeit (bis 1.9.57 über die Kachel)
    Ole (seit 1.9.58)      nach dem Ende: Kacheln hoch 2 Spalten, Start über die Kachel -> läuft
    Tom / Kai              Mitglied ohne Knopf mit „stoppt Kai Kolonne“ / Kolonnenführer mit „Feierabend für die Gruppe“; seit 1.9.58
                           Kai danach „⋮ Für die Kolonne starten“: Kolonne Nord, Kai (ich) fest, Tom angehakt -> Gruppenzeit für beide
    überall                Zeilen ≥ 56 px, Knöpfe ≥ 48 px, Hauptknöpfe 64 px; Reiter „Heute“; keine JS-Fehler

Die Bilder (heute_*.png) liegen im Ordner der Screenshots.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_heute.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD]
        [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import re
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
    from app.maintenance_contracts import create_contract
    from app.models import (
        AppUser, Customer, Employee, Order, OrderItem, PlanningSlot, Project, Property, RoofArea, Team, TeamEmployee,
        WorkPreparationTeamAssignment, WorkPreparationTeamEmployee,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.service_reports import create_report
    from app.time_tracking import start_group_timer, start_timer, stop_timer
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
    # Ole: gestern Fahrzeit 06:00–06:45 gebucht (seit 1.9.48: zählt für die Pause des Tages und „Tag zusammen“), Baustelle seit 06:45 offen
    fahrt = start_timer(db, employee_id=leute["ole"].id, order_id=a.id, entry_type="travel",
                        started_at=datetime.combine(heute - timedelta(days=1), time(6)))
    stop_timer(db, fahrt.id, ended_at=datetime.combine(heute - timedelta(days=1), time(6, 45)))
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
    # seit 1.9.49: ein Wartungsvertrag an Halle Nord -- „Wartungen an meinen Objekten“ in „Offen“ und auf „Heute / Offen“
    create_contract(db, kunde.id, halle.id, "Jahreswartung Flachdach", 12, heute + timedelta(days=30))
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

# seit 1.9.50: Kontrast des Feldrahmens zur Signalfläche, gemessen an den berechneten Farben (WCAG 2.x)
KONTRAST_FELD = """(()=>{const f=document.getElementById('endeZeit'),k=f.closest('.signal-karte');
const rgb=s=>s.match(/[\\d.]+/g).slice(0,3).map(Number);
const L=c=>{const v=c.map(x=>{x/=255;return x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4)});return 0.2126*v[0]+0.7152*v[1]+0.0722*v[2]};
const a=L(rgb(getComputedStyle(f).borderTopColor)),b=L(rgb(getComputedStyle(k).backgroundColor));
return Math.round((Math.max(a,b)+0.05)/(Math.min(a,b)+0.05)*100)/100})()"""

# seit 1.9.58: Spalten eines Kachel-Rasters (quer 3, hoch 2)
def spalten(raster):
    return f"getComputedStyle(document.getElementById('{raster}')).gridTemplateColumns.split(' ').length"


REIHENFOLGE = """(()=>{const y=s=>Math.round(document.querySelector(s).getBoundingClientRect().top);
return [y('#arbeitszeit .heute-karte'),y('[data-einsatz]'),y('#offenKarte'),y('#naechsteKarte')]})()"""


async def _ganze_seite(tab, name, breite, hoehe):
    """Bild bis zum Seitenende (seit 1.9.49): das Fenster so hoch wie die Seite, danach wieder wie vorher."""
    voll = await tab.js("Math.ceil(document.documentElement.scrollHeight)")
    await tab.fenster(breite, max(hoehe, voll))
    await tab.bild(name)
    await tab.fenster(breite, hoehe)


OFFEN_BEREIT = "document.getElementById('offenLaedt').hidden"


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
            await _ganze_seite(tab, f"heute_{art}_{'hell' if thema == 'light' else 'dunkel'}", breite, hoehe)
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
         ["Checkliste Sicherheitscheck", "Entwurf · noch 1 offen", None, True, f"/checklisten/{seed['checkliste']}"]])  # seit 1.9.50
    p.pruefe("Einsatz: „Bericht anlegen“ und „Checklisten zum Auftrag“ als neutrale Knöpfe 48 px", await tab.js(
        "[...document.querySelectorAll('[data-einsatz] .einsatz-wege a')].map(x=>[x.textContent,x.className,"
        "Math.round(x.getBoundingClientRect().height)])"),
        [["Bericht anlegen", "knopf knopf-neutral knopf-klein", 48], ["Checklisten zum Auftrag", "knopf knopf-neutral knopf-klein", 48]])
    p.pruefe("Weg zum Anlegen eines Berichts", await tab.js("document.querySelector('.einsatz-wege a').getAttribute('href')"),
             f"/orders/{a}/service-reports")
    # seit 1.9.49: die Zeilen springen auf „Heute / Offen“, dazu „Wartungen an meinen Objekten“ (bis dahin #… auf die Listen darunter)
    p.pruefe("Offen: Berichte 1, Checklisten 1, Wartungen 1, keine leere Gruppe, Zeilen springen auf „Heute / Offen“", await tab.js(
        "[...document.querySelectorAll('#offenZeilen .zeile')].map(z=>[z.querySelector('.zeile-titel').textContent,"
        "z.querySelector('.zahl-pill').textContent,z.getAttribute('href')])"),
        [["Berichte", "1", "/mobil/offen#offene-berichte"], ["Checklisten", "1", "/mobil/offen#offene-checklisten"],
         ["Wartungen an meinen Objekten", "1", "/mobil/offen#wartungen"]])
    p.pruefe("Heute ohne Listen, die letzte Karte ist „Nächste Tage“", await tab.js(
        "[!!document.querySelector('.listen,#draftReportsList,#defectsList,#maintenanceList,#draftChecklistsList'),"
        "[...document.querySelectorAll('main section')].filter(s=>s.getClientRects().length).pop().id]"), [False, "naechsteKarte"])
    p.pruefe("Nächste Tage: A ab morgen in einer Zeile „Fortsetzung“, B; heute nicht", await tab.js(
        "[document.getElementById('naechsteTitel').textContent,[...document.querySelectorAll('#naechsteZeilen .zeile')].map(z=>z.textContent)]"),
        ["Nächste Tage", [f"{spanne(seed['morgen'], seed['uebermorgen'])}Halle Nord · Fortsetzung",
                          f"{spanne(seed['b_von'], seed['b_bis'])}Halle Nord · Rinne erneuern"]])
    masse = await tab.js(MASSE)
    p.pruefe(f"Maße quer {masse[1]}", masse[0], [True, True, True, True])
    p.pruefe("Mia quer: keine JS-Fehler", tab.fehler, [])

    # --- seit 1.9.49: „Heute / Offen“ über die Zeile „Wartungen an meinen Objekten“ (der letzte Abschnitt: die Seite springt) ---
    ziel = await tab.js("document.querySelector('#offenZeilen a[href$=\"#wartungen\"]').getAttribute('href')")
    await tab.fenster(412, 600, mobil=True)  # schmal und niedrig: die Seite ist länger als das Fenster, der Sprung sichtbar
    await tab.oeffnen(ziel, OFFEN_BEREIT)
    p.pruefe("Offen: Kopf „Heute / Offen“, Reiter „Heute“ aktiv", await tab.js(
        "[[...document.querySelectorAll('#seitenkopfPfad a')].map(x=>[x.getAttribute('href'),x.textContent]),"
        "document.getElementById('seitenkopfTitel').textContent,document.querySelector('.mobile-nav-reiter.active').textContent]"),
        [[["/mobil", "Heute"]], "Offen", "Heute"])
    p.pruefe("Offen: genau die nicht leeren Abschnitte, kein „Nichts offen.“", await tab.js(
        "[[...document.querySelectorAll('main section')].filter(s=>!s.hidden).map(s=>s.id),document.getElementById('nichtsOffen').hidden]"),
        [["offene-berichte", "offene-checklisten", "wartungen"], True])
    p.pruefe("Offen: zum Abschnitt gesprungen (Wartungen unter dem Kopf im Bild)", await tab.js(
        "(r=>[scrollY>0,r.top>=64&&r.top<innerHeight])(document.getElementById('wartungen').getBoundingClientRect())"), [True, True])
    p.pruefe("Offen: Bericht, Checkliste, Wartung mit „Wartung durchführen“", await tab.js(
        "[[...document.querySelectorAll('#draftReportsList a')].map(x=>x.getAttribute('href')),"
        "[...document.querySelectorAll('#draftChecklistsList a')].map(x=>x.getAttribute('href')),"
        "[...document.querySelectorAll('#maintenanceList .contract-title,#maintenanceList .perform-btn')].map(x=>x.textContent)]"),
        [[f"/orders/{a}/service-reports?report={seed['bericht']}"], [f"/checklisten/{seed['checkliste']}"],
         ["Jahreswartung Flachdach", "Wartung durchführen"]])
    p.pruefe("Offen: keine JS-Fehler", tab.fehler, [])
    for thema in ("light", "dark"):
        await tab.fenster(800, 1100)
        await tab.js(f"localStorage.setItem('erp_theme','{thema}')")
        await tab.oeffnen("/mobil/offen", OFFEN_BEREIT)
        await _ganze_seite(tab, f"heute_offen_hoch_{'hell' if thema == 'light' else 'dunkel'}", 800, 1100)

    await _ansehen(tab, seed, "mia", 800, 1100, "light")
    p.pruefe("hoch: eine Spalte in der Reihenfolge Arbeitszeit, Einsatz, Offen, Nächste Tage",
             await tab.js(f"(y=>y.every((v,i)=>i===0||v>y[i-1]))({REIHENFOLGE})"), True)

    # --- Mia: Zeitart wechseln, dann Feierabend ---
    await tab.js("document.getElementById('wechselKnopf').click()")
    p.pruefe("hoch: Kacheln „Zeitart wechseln“ in 2 Spalten", await tab.js(spalten("wechselKacheln")), 2)  # seit 1.9.58
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
    # seit 1.9.48: das Ergebnis mit „Tag zusammen“ (zwei Buchungen am Tag: 06:45–10:00 und die Fahrzeit seit dem Wechsel)
    ergebnis = await tab.js("document.getElementById('zeitErgebnis').textContent")
    # seit 1.9.53 wie die Vorschau: anwesend · Tag zusammen (Anwesenheit des Tages) · Pause, dann gebucht
    p.pruefe("Feierabend: Ergebnis mit Tag zusammen", bool(re.fullmatch(
        r"Feierabend gebucht: anwesend 0:00 h · Tag zusammen 3:15 h · Pause nach Zeitregel − 0:00 h · gebucht 0,0\d h", ergebnis or "")),
             True)
    await tab.bild("heute_nach_feierabend_zwei_buchungen_hell")
    p.pruefe("nach dem Feierabend: nichts läuft, Auftrag vorbelegt", await tab.js("document.getElementById('startAuftrag').value"), str(a))
    p.pruefe("Mia: keine JS-Fehler", tab.fehler, [])

    # --- Ole: Zeit von gestern offen ---
    for breite, hoehe, art in ((1280, 620, "quer"), (800, 1100, "hoch")):
        await _ansehen(tab, seed, "ole", breite, hoehe, "light")
        await tab.bild(f"heute_gestern_offen_{art}_hell")
    # seit 1.9.50: der leere Einsatz zählt nicht als zweiter Abstand (bis dahin 32 px)
    p.pruefe("Ole hoch: 16 px zwischen Arbeitszeit und Offen", await tab.js(
        "Math.round(document.getElementById('offenKarte').getBoundingClientRect().top-document.getElementById('arbeitszeit').getBoundingClientRect().bottom)"),
        16)
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
    await tab.js("(f=>{f.value='15:45';f.dispatchEvent(new Event('input'))})(document.getElementById('endeZeit'))")
    await tab.warten("document.querySelector('#endeVorschau .gebucht')")
    vorschau = await tab.js("[...document.querySelectorAll('#endeVorschau span')].map(s=>s.textContent)")
    # seit 1.9.48 je Tag: die Fahrzeit 06:00–06:45 zählt mit -- Baustelle 06:45–15:45 allein genau 9:00 h (je Buchung 30 min), der Tag
    # 9:45 h -> 45 min; seit 1.9.53 steht „Tag zusammen“ (die Anwesenheit des Tages, 9:45 h) zwischen „Anwesend“ und der Pause
    p.pruefe("Ole: Vorschau vom Server", vorschau,
             ["Anwesend 9:00 h · Tag zusammen 9:45 h · Pause nach Zeitregel − 0:45 h", "Gebucht werden 8,25 h"])
    await tab.bild("heute_gestern_offen_vorschau_hell")
    kontrast_hell = await tab.js(KONTRAST_FELD)
    await tab.js("document.documentElement.setAttribute('data-theme','dark')")  # dunkel ohne Neuladen (die Eingabe bleibt)
    await tab.bild("heute_gestern_offen_vorschau_dunkel")
    kontrast_dunkel = await tab.js(KONTRAST_FELD)
    p.pruefe(f"Feldrahmen auf der Signalfläche ≥ 3 : 1 (hell {kontrast_hell}, dunkel {kontrast_dunkel})",
             [kontrast_hell >= 3, kontrast_dunkel >= 3], [True, True])
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('endeKnopf').click()", "#arbeitszeit")
    gebucht = await tab.js(f"fetch('/api/time-entries?employee_id={seed['ole']}&start_date={seed['gestern']}&end_date={seed['gestern']}')"
                           ".then(r=>r.json()).then(l=>l.sort((x,y)=>x.started_at<y.started_at?-1:1).map(e=>[e.status,Number(e.anwesend),e.pause,Number(e.hours)]))")
    p.pruefe("Ole: gebucht wie die Vorschau, die Fahrzeit unverändert", gebucht, [["booked", 0.75, 0, 0.75], ["booked", 9.0, 45, 8.25]])
    p.pruefe("Ole: Ergebnis mit Tag zusammen", await tab.js("document.getElementById('zeitErgebnis').textContent"),
             "Feierabend gestern eingetragen: anwesend 9:00 h · Tag zusammen 9:45 h · Pause nach Zeitregel − 0:45 h · gebucht 8,25 h")
    p.pruefe("Ole: danach startet heute", await tab.js("!!document.getElementById('startKacheln')"), True)
    # seit 1.9.58: hoch 2 Spalten (dieselbe Seite, nur das Fenster schmaler), Start über die Kachel
    await tab.fenster(800, 1100)
    p.pruefe("Ole hoch: Kacheln in 2 Spalten", await tab.js(spalten("startKacheln")), 2)
    await tab.fenster(1280, 620)
    await tab.warte_auf_neu_geladene_liste("document.querySelector('#startKacheln [data-zeitart=\"site\"]').click()", "#arbeitszeit")
    p.pruefe("Ole: über die Kachel gestartet", await tab.js("document.querySelector('#arbeitszeit .zeit-titel').textContent"),
             "Baustellenzeit seit 10:00")
    p.pruefe("Ole: keine JS-Fehler", tab.fehler, [])

    # --- Lea: nichts läuft ---
    await _ansehen(tab, seed, "lea", 1280, 620, "light")
    await tab.bild("heute_nichts_laeuft_quer_hell")
    p.pruefe("Lea: Auftrag A vorbelegt, Kacheln mit Vorschlag", await tab.js(
        "[document.getElementById('startAuftrag').value,document.querySelectorAll('#startKacheln .vorschlag').length]"), [str(a), 1])
    masse = await tab.js(MASSE)
    p.pruefe(f"Maße nichts läuft {masse[1]}", masse[0], [True, True, True, True])
    # seit 1.9.58: Kacheln quer 3 Spalten; „⋮ Mit Tätigkeit starten“ (Lea führt keine Kolonne: nur dieser Eintrag)
    p.pruefe("Lea quer: Kacheln in 3 Spalten", await tab.js(spalten("startKacheln")), 3)
    # auch breiter immer 3 (bei 1280 px ergäbe „so viele wie passen“ zufällig ebenfalls 3 -- Gegenprobe 1.9.58 P2)
    await tab.fenster(1440, 900)
    p.pruefe("Lea 1440 px: Kacheln in 3 Spalten", await tab.js(spalten("startKacheln")), 3)
    await tab.fenster(1280, 620)
    await tab.js("document.getElementById('startMenueKnopf').click()")
    p.pruefe("Lea: „⋮“ 48 px, nur „Mit Tätigkeit starten“ (48 px)", await tab.js(
        "[Math.round(document.getElementById('startMenueKnopf').getBoundingClientRect().height),"
        "[...document.querySelectorAll('#startMenue .ds-menue-eintrag')].map(e=>[e.textContent,Math.round(e.getBoundingClientRect().height)])]"),
        [48, [["Mit Tätigkeit starten", 48]]])
    await tab.bild("heute_menue_starten_quer_hell")
    await tab.js("document.getElementById('startMitTaetigkeit').click()")
    p.pruefe("Lea: Dialog mit Auftrag A, Baustellenzeit, ohne Kolonne", await tab.js(
        "[document.getElementById('startDialog').open,document.getElementById('startDialogTitel').textContent,"
        "document.getElementById('startDialogAuftrag').value,document.getElementById('startZeitart').value,"
        "document.getElementById('startKolonneFeld').hidden,document.getElementById('startTaetigkeit').value]"),
        [True, "Mit Tätigkeit starten", str(a), "site", True, ""])
    p.pruefe("Lea: Dialog Felder 52 px, Knöpfe 56 px, Schließen 48 px", await tab.js(
        "(h=>[[...document.querySelectorAll('#startDialog select')].filter(e=>e.getClientRects().length).map(h),"
        "[...document.querySelectorAll('#startDialog .dialog-knoepfe .knopf')].map(h),h(document.getElementById('startDialogZu'))])"
        "(e=>Math.round(e.getBoundingClientRect().height))"), [[52, 52, 52], [56, 56], 48])
    await tab.js("(s=>{s.value='Dachdeckung';s.dispatchEvent(new Event('change'))})(document.getElementById('startTaetigkeit'))")
    await tab.bild("heute_mit_taetigkeit_starten_quer_hell")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('startDialogStarten').click()", "#arbeitszeit")
    p.pruefe("Lea: gestartet, Dialog zu", await tab.js(
        "[document.querySelector('#arbeitszeit .zeit-titel').textContent,document.getElementById('startDialog').open]"),
        ["Baustellenzeit seit 10:00", False])
    p.pruefe("Lea: die Tätigkeit an der laufenden Zeit", await tab.js(
        "fetch('/api/time-entries/active').then(r=>r.json()).then(e=>[e.entry_type,e.activity])"), ["site", "Dachdeckung"])
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
    # --- seit 1.9.58: Kai stoppt die Gruppe und startet sie über „⋮ Für die Kolonne starten“ neu ---
    await tab.warte_auf_neu_geladene_liste("document.getElementById('feierabendGruppe').click()", "#arbeitszeit")
    await tab.js("document.getElementById('startMenueKnopf').click()")
    p.pruefe("Kai: „⋮“ mit beiden Einträgen", await tab.js(
        "[...document.querySelectorAll('#startMenue .ds-menue-eintrag')].map(e=>e.textContent)"),
        ["Mit Tätigkeit starten", "Für die Kolonne starten"])
    await tab.js("document.getElementById('startFuerKolonne').click()")
    p.pruefe("Kai: Dialog mit Kolonne Nord, Kai (ich) fest, Tom angehakt", await tab.js(
        "[document.getElementById('startDialogTitel').textContent,document.getElementById('startKolonne').selectedOptions[0].textContent,"
        "[...document.querySelectorAll('#startMitglieder .mitglied')].map(l=>[l.textContent,l.querySelector('input').checked,"
        "l.querySelector('input').disabled,Math.round(l.getBoundingClientRect().height)])]"),
        ["Für die Kolonne starten", "Kolonne Nord", [["Kai Kolonne (ich)", True, True, 48], ["Tom Mitglied", True, False, 48]]])
    await tab.bild("heute_fuer_die_kolonne_starten_quer_hell")
    # berlin_now() ist sekundengenau: ein Start in derselben Sekunde wie der Feierabend begänne vor dessen Ende -- erst weiter
    t = await tab.js("performance.now()")
    await tab.warten(f"performance.now()>{t + 1100}")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('startDialogStarten').click()", "#arbeitszeit")
    p.pruefe("Kai: Gruppenzeit läuft wieder für Kai und Tom", await tab.js(
        "Promise.all([document.getElementById('feierabendGruppe').textContent,document.getElementById('startDialog').open,"
        "fetch('/api/time-entry-groups/active').then(r=>r.json()).then(g=>g.member_entries.map(m=>m.employee_name).sort())])"),
        ["Feierabend für die Gruppe", False, ["Kai Kolonne", "Tom Mitglied"]])
    p.pruefe("Tom/Kai: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="„Heute“ für die Monteurin (1.9.45)", uhr="10:00"))
