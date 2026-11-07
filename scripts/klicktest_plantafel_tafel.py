"""Klicktest: die Tafel „Kolonnen“ nach der Zeichnung entwurf-stufe6/plantafel-kolonnen.html (1.9.247, Stufe 6, R4, Punkt 1).

Stehende Uhr Di 03.11.2026 10:00. Befüllt wie die Zeichnung (KW 45–46): Kolonne Nord (Tom KF, Mia, Ole; Tom Urlaub 02.–06.), Kolonne Süd (Kai KF, Lia,
Nele; Nele beantragt 05.–06.), Kran Böcker AHK 36 (UVV bis 03/2027, eigenes Postfach, ein Termin „Müller“ aus Outlook 10.–11.), zwei Pritschen.
Einsätze: Am Wasserturm 4 (Nord, 02.–06., fest, Kai dabei, Kran nur am 02.) und KW 46 (09.–13., Kran nur am 13.), Garage Lindenweg 7 (Süd, 03.–05.,
vorläufig, Kai und Nele -> Warnung „Person doppelt“ und Hinweis „Antrag offen“), Wartung (Süd, 12.), Notdienst (ohne Kolonne, Lia, 10.–11.),
Kranvermietung (Lia, 04.–05.); zwei Aufträge nicht eingeplant.

    Zeilen       Nord, Süd, Ohne Kolonne, dann GERÄTE (Kran, Pritschen); Nord nennt „Tom (KF), Mia, Ole“ und „Tom Urlaub 02.–06.“; der Kran „UVV gültig bis
                 03/2027“ und „mit Outlook-Kalender“
    Balken       fest / vorläufig / Kranvermietung / Termin, Warnung mit rotem Rand und Zeichen, Hinweis mit Punkt; der Kran nur an seinen Tagen
    Maße         14 Tage passen bei 1440 px ohne Bildlauf in der Tafel, Sa/So schmal; kein Balken verdeckt einen anderen; jeder Text im Balken ist
                 sichtbar oder steht im title
    Leiste       „KW 45–46 · 02.11.–15.11.2026“, Knopf „1 Warnung · 1 Hinweis“ filtert (nur Einsätze mit Warnung oder Hinweis) und zurück
    Rückstand    „Nicht eingeplant“ mit 2, einklappbar
    Klick        ein Balken öffnet den Einsatz
    1280 px      die Seite läuft nicht über; hell und dunkel als Bild
    keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_plantafel_tafel.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

HEUTE = "2026-11-03"
UHR_MS = int(datetime(2026, 11, 3, 10, 0, tzinfo=ZoneInfo("Europe/Berlin")).timestamp() * 1000)


def befuellen(db, k):
    from datetime import date, timedelta
    from decimal import Decimal

    from app.models import (AppUser, CalendarEvent, Customer, Employee, EmployeeAbsence, EmployeeAbsenceRequest, OperationalAsset,
                            OperationalAssetInspection, OperationalResource, Project, Quote, QuoteItem, Team, TeamEmployee)
    from app.orders import create_order_from_quote, load_order
    from app.planning import create_slot
    from app.project_pipeline_columns import default_pipeline_column_id

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    kunde = Customer(name="Familie Sommer", last_name="Sommer", street="Lindenweg 7", postal_code="52531", city="Uebach")
    namen = ("Tom Monteur", "Mia Monteurin", "Ole Offen", "Kai Kolb", "Lia Lang", "Nele Neu")
    leute = {n.split()[0]: Employee(employee_number=f"M-{i}", first_name=n.split()[0], last_name=n.split()[1], employee_group="gewerblich",
                                    weekly_hours=Decimal("40"), active=True) for i, n in enumerate(namen, 1)}
    kran = OperationalResource(resource_number="K-1", resource_type="Maschine", name="Kran Böcker AHK 36", identifier="AHK 36", active=True,
                               outlook_mailbox="kran@dachkonzepte.example")
    p202 = OperationalResource(resource_number="F-1", resource_type="Fahrzeug", name="Pritsche HS-DK 202", identifier="HS-DK 202", active=True)
    p204 = OperationalResource(resource_number="F-2", resource_type="Fahrzeug", name="Pritsche HS-DK 204", identifier="HS-DK 204", active=True)
    db.add_all([anna, kunde, *leute.values(), kran, p202, p204]); db.flush()
    asset = OperationalAsset(resource_id=kran.id)
    db.add(asset); db.flush()
    db.add(OperationalAssetInspection(asset_id=asset.id, inspection_type="UVV", next_due_date=date(2027, 3, 31)))

    def kolonne(name, personen):
        team = Team(name=name, active=True)
        db.add(team); db.flush()
        for i, p in enumerate(personen):
            db.add(TeamEmployee(team_id=team.id, employee_id=p.id, is_crew_leader=i == 0))
        db.flush()
        return team

    def auftrag(nummer, name):
        projekt = Project(project_number=f"P-2026-{nummer}", name=name, customer_id=kunde.id, status="angebot", pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-{nummer}", project_id=projekt.id, title=name, vat_rate=Decimal("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Arbeiten", quantity=Decimal("10"), unit="m2", unit_price=Decimal("50")))
        db.commit()
        o = create_order_from_quote(db, quote.id, order_date=date(2026, 10, 1), execution_start=None, execution_end=None, caseworker_employee_id=None,
                                    project_manager_employee_id=None, payment_terms=None, remarks=None)
        return load_order(db, o.id)

    L = leute
    nord, sued = kolonne("Kolonne Nord", [L["Tom"], L["Mia"], L["Ole"]]), kolonne("Kolonne Süd", [L["Kai"], L["Lia"], L["Nele"]])
    wasserturm, garage, wartung, notdienst = (auftrag("0118", "Am Wasserturm 4"), auftrag("0131", "Garage Lindenweg 7"), auftrag("0133", "Wartung"),
                                              auftrag("0135", "Notdienst"))
    auftrag("0140", "Dachfenster Krüger"); auftrag("0144", "Ortgang Lindenweg 9")
    d = lambda n: date(2026, 11, 2) + timedelta(days=n)  # noqa: E731
    db.add(EmployeeAbsence(employee_id=L["Tom"].id, absence_type="Urlaub", absence_category="urlaub", start_date=d(0), end_date=d(4)))
    db.add(EmployeeAbsenceRequest(employee_id=L["Nele"].id, absence_type="Urlaub", absence_category="urlaub", start_date=d(3), end_date=d(4), status="pending"))
    db.add(CalendarEvent(title="Müller", start_at=datetime(2026, 11, 10), end_at=datetime(2026, 11, 11), all_day=True, resource_id=kran.id,
                         external_source="outlook", outlook_postfach="kran@dachkonzepte.example", outlook_event_id="kran-1"))
    db.commit()
    h = Decimal("1")
    werte = {"planned_hours": h, "trotzdem_planen": True}
    create_slot(db, order_id=wasserturm.id, team_id=nord.id, employee_ids=[L["Mia"].id, L["Ole"].id, L["Kai"].id], start_date=d(0), end_date=d(4),
                status="fest", geraete=[{"resource_id": p202.id}, {"resource_id": kran.id, "tage": [d(0)]}], **werte)
    create_slot(db, order_id=garage.id, team_id=sued.id, employee_ids=[L["Kai"].id, L["Nele"].id], start_date=d(1), end_date=d(3), status="vorlaeufig",
                geraete=[{"resource_id": p204.id}], **werte)
    create_slot(db, order_id=wasserturm.id, team_id=nord.id, start_date=d(7), end_date=d(11), status="fest",
                geraete=[{"resource_id": p202.id}, {"resource_id": kran.id, "tage": [d(11)]}], **werte)
    create_slot(db, order_id=wartung.id, team_id=sued.id, employee_ids=[L["Kai"].id], start_date=d(10), end_date=d(10), status="fest",
                geraete=[{"resource_id": p204.id}], **werte)
    create_slot(db, order_id=notdienst.id, team_id=None, employee_ids=[L["Lia"].id], start_date=d(8), end_date=d(9), status="fest", geraete=[], **werte)
    create_slot(db, order_id=None, art="kranvermietung", customer_id=kunde.id, team_id=None, employee_ids=[L["Lia"].id], start_date=d(2), end_date=d(3),
                status="fest", geraete=[{"resource_id": kran.id}], **werte)
    db.commit()
    return {"anna": k.cookies(anna)}


BEREIT = "typeof board!=='undefined'&&board&&board.slots&&board.slots.length===6&&!!document.querySelector('#planner .planner-row')"

ZEILEN = ("[...document.querySelectorAll('#planner .planner-row,#planner .abschnitt')].map(z=>z.classList.contains('abschnitt')?'['+z.textContent.trim()+']'"
          ":z.querySelector('.row-label b').textContent.trim())")
UNTER = ("(n=>[...[...document.querySelectorAll('#planner .planner-row')].find(z=>z.querySelector('.row-label b').textContent.trim()===n)"
         ".querySelectorAll('.row-label .unter')].map(u=>u.textContent.trim()))")
BALKEN = ("[...document.querySelectorAll('#planner .planner-row')].flatMap(z=>[...z.querySelectorAll('.slot')].map(s=>[z.querySelector('.row-label b')"
          ".textContent.trim(),s.querySelector('.slot-text').textContent.trim(),['fest','vorlaeufig','kran','termin','conflict'].filter(c=>s.classList.contains(c))"
          ".join(' '),!!s.querySelector('.hinweis-punkt')]))")
# kein Balken verdeckt einen anderen (je Zeile paarweise, mit 0,5 px Spiel)
VERDECKT = ("[...document.querySelectorAll('#planner .track')].flatMap(t=>{const r=[...t.querySelectorAll('.slot')].map(s=>s.getBoundingClientRect());const f=[];"
            "for(let i=0;i<r.length;i++)for(let j=i+1;j<r.length;j++){const a=r[i],b=r[j];if(a.left<b.right-0.5&&b.left<a.right-0.5&&a.top<b.bottom-0.5"
            "&&b.top<a.bottom-0.5)f.push(t.closest('.planner-row').querySelector('.row-label b').textContent.trim()+' '+i+'/'+j)}return f})")
# jeder Text im Balken: sichtbar (passt) oder im title
TEXTE = ("[...document.querySelectorAll('#planner .slot')].filter(s=>{const t=s.querySelector('.slot-text');const passt=t.scrollWidth<=t.clientWidth+1;"
         "return !passt&&!(s.title||'').includes(t.textContent.trim())}).map(s=>s.querySelector('.slot-text').textContent.trim())")
GEKUERZT = "[...document.querySelectorAll('#planner .slot')].filter(s=>{const t=s.querySelector('.slot-text');return t.scrollWidth>t.clientWidth+1}).length"


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light');localStorage.removeItem('plantafel_rueckstand')}catch(e){}")
    await tab.browser_uhr_fest(UHR_MS)
    await tab.anmelden(seed["anna"])
    await tab.oeffnen("/planning", BEREIT)
    await tab.warte_auf_ruhe()
    p.pruefe("Leiste: Zeitraum", await tab.js("document.getElementById('zeitraum').textContent"), "KW 45–46 · 02.11.–15.11.2026")
    p.pruefe("Zeilen: Kolonnen, Ohne Kolonne, Geräte", await tab.js(ZEILEN),
             ["Kolonne Nord", "Kolonne Süd", "Ohne Kolonne", "[Geräte]", "Kran Böcker AHK 36", "Pritsche HS-DK 202", "Pritsche HS-DK 204"])
    p.pruefe("Nord: Mitglieder mit KF und Urlaub", await tab.js(UNTER + "('Kolonne Nord')"), ["Tom (KF), Mia, Ole", "Tom Urlaub 02.–06.11."])
    p.pruefe("Ohne Kolonne: Satz", await tab.js(UNTER + "('Ohne Kolonne')"), ["Personen einzeln gewählt"])
    p.pruefe("Kran: Prüffrist und Kalender", await tab.js(UNTER + "('Kran Böcker AHK 36')"), ["UVV gültig bis 03/2027", "mit Outlook-Kalender"])
    p.pruefe("Balken: Zeile, Text, Art, Hinweis", await tab.js(BALKEN), [
        ["Kolonne Nord", "Am Wasserturm 4 · Mia, Ole, Kai", "fest conflict", False],
        ["Kolonne Nord", "Am Wasserturm 4 · Tom, Mia, Ole", "fest", False],
        ["Kolonne Süd", "Garage Lindenweg 7 · Kai, Nele", "vorlaeufig conflict", True],
        ["Kolonne Süd", "Wartung · Kai", "fest", False],
        ["Ohne Kolonne", "Notdienst · Lia", "fest", False],
        ["Kran Böcker AHK 36", "Am Wasserturm 4", "fest conflict", False],
        ["Kran Böcker AHK 36", "Vermietung · Lia", "fest kran", False],
        ["Kran Böcker AHK 36", "Am Wasserturm 4", "fest", False],
        ["Kran Böcker AHK 36", "Outlook · Müller", "termin", False],
        ["Pritsche HS-DK 202", "Am Wasserturm 4", "fest conflict", False],
        ["Pritsche HS-DK 202", "Am Wasserturm 4", "fest", False],
        ["Pritsche HS-DK 204", "Garage Lindenweg 7", "vorlaeufig conflict", True],
        ["Pritsche HS-DK 204", "Wartung", "fest", False],
    ])
    p.pruefe("Warnung: rotes Zeichen im Balken", await tab.js("[...document.querySelectorAll('#planner .slot.conflict')].every(s=>!!s.querySelector('svg.warnzeichen'))"), True)
    p.pruefe("Maße: 14 Tage ohne Bildlauf in der Tafel (1440 px)", await tab.js(
        "(()=>{const s=document.getElementById('planner');return [document.querySelectorAll('#planner .tagkopf').length,s.scrollWidth<=s.clientWidth+1]})()"), [14, True])
    p.pruefe("Maße: Sa/So schmal (22 px), Tage gleich breit", await tab.js(
        "(()=>{const k=[...document.querySelectorAll('#planner .tagkopf')];const w=k.filter(x=>!x.classList.contains('we')).map(x=>x.offsetWidth);"
        "return [k.filter(x=>x.classList.contains('we')).map(x=>x.offsetWidth),new Set(w).size===1&&w[0]>=56]})()"), [[22, 22, 22, 22], True])
    p.pruefe("Kein Balken verdeckt einen anderen", await tab.js(VERDECKT), [])
    p.pruefe("Jeder Text im Balken sichtbar oder im title", await tab.js(TEXTE), [])
    print(f"    gekürzt (mit title): {await tab.js(GEKUERZT)} Balken")
    ferien = await tab.js("(board.school_holidays||[]).length>0")  # seit 1.9.247: der Eintrag „Schulferien“ nur mit Ferien im Bild (Testdaten: je nach Bundesland)
    p.pruefe("Legende: acht Einträge (dazu Schulferien, wenn welche im Bild sind)", await tab.js(
        "[...document.querySelectorAll('.legende > span')].filter(s=>!s.hidden).map(s=>s.textContent.trim())"),
             ["fest", "vorläufig", "Kranvermietung", "abwesend", "beantragt", "Termin aus Kalender/Outlook", "Warnung", "Hinweis"]
             + (["Schulferien (nur Anzeige)"] if ferien else []))
    p.pruefe("Filterknopf: 1 Warnung · 1 Hinweis", await tab.js("[document.getElementById('filterText').textContent,document.getElementById('filterKnopf').disabled]"),
             ["1 Warnung · 1 Hinweis", False])
    p.pruefe("Rückstand: zwei nicht eingeplant", await tab.js(
        "[document.getElementById('backlogCount').textContent,[...document.querySelectorAll('#backlog .rk-eintrag b')].map(b=>b.textContent)]"),
        ["2", ["Ortgang Lindenweg 9", "Dachfenster Krüger"]])
    await tab.bild("tafel_kolonnen_1440_hell")

    # --- Filter ---
    await tab.js("document.getElementById('filterKnopf').click()")
    p.pruefe("Filter: nur Einsätze mit Warnung oder Hinweis", await tab.js(
        "[document.getElementById('filterKnopf').getAttribute('aria-pressed'),[...document.querySelectorAll('#planner .slot')].map(s=>s.querySelector('.slot-text').textContent.trim())]"),
        ["true", ["Am Wasserturm 4 · Mia, Ole, Kai", "Garage Lindenweg 7 · Kai, Nele", "Am Wasserturm 4", "Am Wasserturm 4", "Garage Lindenweg 7"]])
    await tab.bild("tafel_filter")
    await tab.js("document.getElementById('filterKnopf').click()")
    p.pruefe("Filter: wieder alle", await tab.js("document.querySelectorAll('#planner .slot').length"), 13)

    # --- Rückstand einklappen ---
    await tab.js("document.getElementById('rkKnopf').click()")
    p.pruefe("Rückstand: eingeklappt", await tab.js(
        "[document.getElementById('rkKnopf').getAttribute('aria-expanded'),Math.round(document.querySelector('.rueckstand').getBoundingClientRect().width),"
        "getComputedStyle(document.getElementById('backlog')).display]"), ["false", 52, "none"])
    await tab.js("document.getElementById('rkKnopf').click()")
    p.pruefe("Rückstand: wieder offen", await tab.js("document.getElementById('rkKnopf').getAttribute('aria-expanded')"), "true")

    # --- Klick öffnet den Einsatz ---
    await tab.js("[...document.querySelectorAll('#planner .slot')].find(s=>s.textContent.includes('Garage Lindenweg 7')).click()")
    p.pruefe("Klick: Einsatz öffnet sich", await tab.warten("document.getElementById('einsatzDialog').open&&document.getElementById('edUnter').textContent.includes('Garage Lindenweg 7')"), True)
    await tab.bild("tafel_einsatz_offen")
    await tab.js("document.getElementById('einsatzDialog').close()")

    # --- 1280 px und dunkel ---
    await tab.fenster(1280, 900)
    await tab.warte_auf_ruhe()
    p.pruefe("1280 px: die Seite läuft nicht über", await tab.ueberlauf(), [])
    p.pruefe("1280 px: kein Balken verdeckt einen anderen", await tab.js(VERDECKT), [])
    p.pruefe("1280 px: jeder Text sichtbar oder im title", await tab.js(TEXTE), [])
    await tab.bild("tafel_kolonnen_1280_hell")
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','dark')}catch(e){}")
    await tab.oeffnen("/planning", BEREIT)
    await tab.warte_auf_ruhe()
    await tab.bild("tafel_kolonnen_1280_dunkel")
    await tab.fenster(1440, 1000)
    await tab.warten("document.querySelector('#planner .tagkopf').offsetWidth>=56")  # neu gezeichnet für 1440 px
    await tab.bild("tafel_kolonnen_1440_dunkel")
    p.pruefe("dunkel: kein Balken verdeckt einen anderen", await tab.js(VERDECKT), [])
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr=f"{HEUTE} 10:00"))
