"""Klicktest: die Ansicht „Aufträge“ der Plantafel (1.9.280, Stufe 6, R5c, Punkt 2) -- Testdaten nach der Zeichnung entwurf-stufe6/plantafel-auftraege.html
(KW 46, stehende Uhr Mi 11.11.2026 10:00).

Kolonne Nord (Tom KF, Mia, Ole, Pritsche HS-DK 202), Kolonne Süd (Kai KF, Lia, Nele, Pritsche HS-DK 204), der Kran (Typ „Kran“). Kurznamen „HS-DK 202“ und
„HS-DK 204“ (Namen „Pritsche …“). Aufträge: Am Wasserturm 4 (Nord Mo–Fr, am Mi niemand, Kai Do und Fr, der Kran Fr; Soll 54 h, 8 h gebucht), Garage Lindenweg 7
(Kai, Nele, HS-DK 204 Mo–Mi, vorläufig; Soll 32 h), Sturmschaden (Lia Di, Lia und Ole Mi; nach Aufwand), Ortgang Lindenweg 9 (Tom, Mia, HS-DK 202 Mi; Soll 8 h),
Wartung Halle Nord (Lia, Nele, HS-DK 204 Do; aus einem Wartungsvertrag; Nele hat am Do Urlaub beantragt), Kranvermietung (Lia und der Kran Fr, „Kran mit
Bediener“; der Kran ist am Fr doppelt); offen ohne Einsatz: Dachfenster Krüger (nächster Einsatz Mo 16.11., Soll 16 h), Kaminverwahrung Schulz (Soll 6 h).

    Ansicht     Reiter „Aufträge“, Zeitraum 1 Woche (Vorgabe der Ansicht); zurück in „Kolonnen“ 2 Wochen, wieder „Aufträge“ 1 Woche
    Zeilen      eingeplante oben nach ihrem ersten Tag, darunter die offenen; Stunden und Zusatz wie die Akte; der Name verlinkt die Akte
    Zellen      je Einsatz eine Karte (fest, vorläufig, Kran), am Mi beim Wasserturm „niemand“; Chips je Person und Gerät am Tag, Kurzname am Gerät, Kran mit
                eigenem Zeichen, ⚠ am Kran am Fr, Punkt an Nele am Do (Antrag offen)
    Liste       „Zum Einplanen“: Kolonnen, Personen, Geräte mit Wochenleiste (Kai Mo–Do eingeplant, Fr frei; Nele Do beantragt; Kran Fr doppelt)
    Bedienen    Klick auf eine Karte öffnet ihren Einsatz; ab 2 Wochen schmalere Chips mit dem Namen im title; der Filter zeigt nur Aufträge mit Warnung
                oder Hinweis
    Platz       (seit 1.9.283) bei 1440 und 1280 px rollt die Tafel nicht, kein Chip ist gekürzt, „Zum Einplanen“ offen; bei 1280 px der Freitag zu sehen, das
                Kranzeichen da, die Gerätezeichen weg; „Kolonnen“ zu, „Aufträge“ offen, Zuklappen dort merkt nichts, der nächste Wechsel öffnet wieder
    Bilder      „Aufträge“ bei 1440 und 1280 px, hell und dunkel
    keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_plantafel_auftraege.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_plantafel_tage import UHR_MS  # noqa: E402

MO, DI, MI, DO, FR = "2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"
BEREIT = ("typeof board!=='undefined'&&board&&view==='auftraege'&&typeof auftragsliste!=='undefined'&&auftragsliste&&"
          "!!document.querySelector('#planner table.auftraege tbody tr.a-zeile')")
ZEILEN = ("[...document.querySelectorAll('#planner tr.a-zeile, #planner tr.a-abschnitt')].map(z=>z.classList.contains('a-abschnitt')?'# '+z.textContent.trim():"
          "[z.querySelector('.a-name a').textContent.trim(),...[...z.querySelectorAll('.a-name .klein')].map(k=>k.textContent.trim())].join(' | '))")
# Inhalt einer Zelle: je Karte [Klassen, Chips (Text, ⚠, Punkt, Kran)]
ZELLE = ("((name,tag)=>{const z=[...document.querySelectorAll('#planner tr.a-zeile')].find(r=>r.querySelector('.a-name a').textContent.trim()===name);"
         "const c=z&&z.querySelector(`td[data-date=\"${tag}\"]`);if(!c)return null;return [...c.querySelectorAll('.a-einsatz')].map(k=>["
         "['vorlaeufig','kran','niemand'].filter(x=>k.classList.contains(x)).join(' ')||'fest',[...k.querySelectorAll('.chip')].map(ch=>ch.textContent.trim()"
         "+(ch.querySelector('.warnzeichen')?' ⚠':'')+(ch.querySelector('.hinweis-punkt')?' •':'')+(ch.querySelector('.kranzeichen')?' (Kran)':''))"
         ",k.classList.contains('niemand')?k.textContent.trim():null])})")
# seit 1.9.283: rollt die Tafel seitlich? Welche Chips sind gekürzt (Text breiter als der Chip)? Ist die Liste offen?
PLATZ = ("(()=>{const p=document.getElementById('planner');return [p.scrollWidth>p.clientWidth,"
         "[...p.querySelectorAll('.chip')].filter(c=>c.scrollWidth>c.clientWidth).map(c=>c.textContent.trim()),"
         "!document.getElementById('tafelLayout').classList.contains('rk-zu')]})()")
LEISTE = ("((art,name)=>{const c=[...document.querySelectorAll('#backlog .ze-zeile .chip')].find(x=>x.dataset.art===art&&x.textContent.trim()===name);"
          "return c?[...c.closest('.ze-zeile').querySelectorAll('.wl i')].map(i=>i.className||'frei'):null})")


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.models import (AppUser, Customer, Employee, EmployeeAbsenceRequest, OperationalResource, Order, OrderItem, OrderItemCalculationSnapshot,
                            Project, ProjectProfile, Property, Team, TeamEmployee, TeamResource, TimeEntry)
    from app.planning import create_slot
    from app.project_pipeline_columns import default_pipeline_column_id

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    L = {}
    for nr, (vor, nach) in enumerate([("Tom", "Monteur"), ("Mia", "Monteurin"), ("Ole", "Offen"), ("Kai", "Kolb"), ("Lia", "Lang"), ("Nele", "Neu")], 1):
        L[vor] = Employee(employee_number=f"E-{nr}", first_name=vor, last_name=nach, employee_group="gewerblich", active=True, hourly_wage=Decimal("22.00"))
    p202 = OperationalResource(resource_number="F-202", resource_type="Fahrzeug", name="Pritsche HS-DK 202", identifier="HS-DK 202", kurzname="HS-DK 202", active=True)
    p204 = OperationalResource(resource_number="F-204", resource_type="Fahrzeug", name="Pritsche HS-DK 204", identifier="HS-DK 204", kurzname="HS-DK 204", active=True)
    kran = OperationalResource(resource_number="K-1", resource_type="Kran", name="Kran", identifier="Kran", active=True)
    db.add_all([anna, *L.values(), p202, p204, kran]); db.flush()
    nord, sued = Team(name="Kolonne Nord", active=True), Team(name="Kolonne Süd", active=True)
    db.add_all([nord, sued]); db.flush()
    db.add_all([TeamEmployee(team_id=nord.id, employee_id=L["Tom"].id, is_crew_leader=True), TeamEmployee(team_id=nord.id, employee_id=L["Mia"].id),
                TeamEmployee(team_id=nord.id, employee_id=L["Ole"].id), TeamResource(team_id=nord.id, resource_id=p202.id),
                TeamEmployee(team_id=sued.id, employee_id=L["Kai"].id, is_crew_leader=True), TeamEmployee(team_id=sued.id, employee_id=L["Lia"].id),
                TeamEmployee(team_id=sued.id, employee_id=L["Nele"].id), TeamResource(team_id=sued.id, resource_id=p204.id)])
    db.commit()

    def auftrag(nr, objekt, kunde_name, soll_h):
        kunde = Customer(name=kunde_name, last_name=kunde_name, is_consumer=False)
        db.add(kunde); db.flush()
        prop = Property(customer_id=kunde.id, name=objekt, street=objekt, postal_code="52531", city="Übach-Palenberg")
        db.add(prop); db.flush()
        projekt = Project(project_number=f"P-2026-0{nr}", name=objekt, customer_id=kunde.id, property_id=prop.id, pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        o = Order(order_number=f"AUF-2026-0{nr}", project_id=projekt.id, source_quote_id=900 + nr, quote_number_snapshot=f"A-KT-{nr}", title=objekt,
                  customer_name=kunde.name, property_name=objekt, property_address=f"{objekt}\n52531 Übach-Palenberg")
        db.add(o); db.flush()
        item = OrderItem(order_id=o.id, sort_order=10, position_number="1", short_text="Arbeit", quantity=Decimal("1"), unit="psch", unit_price=Decimal("1"))
        db.add(item); db.flush()
        if soll_h:
            db.add(OrderItemCalculationSnapshot(order_item_id=item.id, site_time_minutes=Decimal(soll_h * 60), workshop_time_minutes=Decimal("0")))
        db.commit()
        return o

    d = lambda n: date(2026, 11, 9 + n)  # noqa: E731 -- Mo 09.11. + n
    ohne_mi = [d(0), d(1), d(3), d(4)]
    w = {"planned_hours": Decimal("8"), "trotzdem_planen": True}
    wasserturm = auftrag(118, "Am Wasserturm 4", "Wohnbau Kessler GmbH", 54)
    s_wasser = create_slot(db, order_id=wasserturm.id, team_id=nord.id, start_date=d(0), end_date=d(4), status="fest",
                           besetzung=[{"employee_id": L[n].id, "tage": ohne_mi} for n in ("Tom", "Mia", "Ole")] + [{"employee_id": L["Kai"].id, "tage": [d(3), d(4)]}],
                           geraete=[{"resource_id": p202.id, "tage": ohne_mi}, {"resource_id": kran.id, "tage": [d(4)]}], **w)
    db.add(TimeEntry(employee_id=L["Tom"].id, project_id=wasserturm.project_id, order_id=wasserturm.id, work_date=d(0), entry_type="site", hours=Decimal("8"), status="booked"))
    db.commit()
    s_garage = create_slot(db, order_id=auftrag(131, "Garage Lindenweg 7", "Familie Sommer", 32).id, team_id=None, start_date=d(0), end_date=d(2), status="vorlaeufig",
                           employee_ids=[L["Kai"].id, L["Nele"].id], geraete=[{"resource_id": p204.id, "tage": None}], **w)
    create_slot(db, order_id=auftrag(151, "Sturmschaden Gartenstraße 2", "Notdienst", 0).id, team_id=None, start_date=d(1), end_date=d(2), status="fest",
                besetzung=[{"employee_id": L["Lia"].id, "tage": None}, {"employee_id": L["Ole"].id, "tage": [d(2)]}], **w)
    create_slot(db, order_id=auftrag(144, "Ortgang Lindenweg 9", "Familie Becker", 8).id, team_id=None, start_date=d(2), end_date=d(2), status="fest",
                employee_ids=[L["Tom"].id, L["Mia"].id], geraete=[{"resource_id": p202.id, "tage": None}], **w)
    wartung = auftrag(97, "Wartung Halle Nord", "Hausverwaltung Rhein", 4)
    db.add(ProjectProfile(project_id=wartung.project_id, source_maintenance_contract_id=1)); db.commit()
    create_slot(db, order_id=wartung.id, team_id=None, start_date=d(3), end_date=d(3), status="fest", employee_ids=[L["Lia"].id, L["Nele"].id],
                geraete=[{"resource_id": p204.id, "tage": None}], **w)
    create_slot(db, order_id=auftrag(153, "Kranvermietung", "Beispielbau GmbH", 0).id, team_id=None, start_date=d(4), end_date=d(4), status="fest",
                art="kranvermietung", employee_ids=[L["Lia"].id], geraete=[{"resource_id": kran.id, "tage": None}], **w)
    dachfenster = auftrag(140, "Dachfenster Krüger", "Familie Krüger", 16)
    create_slot(db, order_id=dachfenster.id, team_id=sued.id, start_date=d(7), end_date=d(8), status="vorlaeufig", **w)
    auftrag(149, "Kaminverwahrung Schulz", "Peter Schulz", 6)
    db.add(EmployeeAbsenceRequest(employee_id=L["Nele"].id, absence_type="Urlaub", absence_category="urlaub", start_date=d(3), end_date=d(3), status="pending"))
    db.commit()
    return {"anna": k.cookies(anna), "wasserturm": s_wasser.id, "garage": s_garage.id}


async def laden(tab, p, n: int, thema: str, anlass: str) -> None:
    await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
    await tab.js("window.__dkVorDemNeuladen=1")
    p.pruefe(f"{anlass}: geladen", await tab.oeffnen(f"/planning?n={n}", "typeof board!=='undefined'&&!!board"), True)
    p.pruefe(f"{anlass}: wirklich neu geladen", await tab.js("window.__dkVorDemNeuladen===undefined"), True)
    await tab.warte_auf_ruhe()
    await tab.js("setView('auftraege')")
    await tab.warten(BEREIT)
    await tab.warte_auf_ruhe()


async def pruefen(tab, seed, p):
    zelle = lambda name, tag: tab.js(f"({ZELLE})({json.dumps(name)},{json.dumps(tag)})")  # noqa: E731
    leiste = lambda art, name: tab.js(f"({LEISTE})({json.dumps(art)},{json.dumps(name)})")  # noqa: E731
    await tab.browser_uhr_fest(UHR_MS)
    await tab.fenster(1440, 1000)
    await tab.anmelden(seed["anna"])
    p.pruefe("Plantafel geladen", await tab.oeffnen("/planning", "typeof board!=='undefined'&&!!board"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Start: Kolonnen, 2 Wochen", await tab.js("[view,tageAnzahl()]"), ["teams", 14])
    await laden(tab, p, 1, "light", "1440 hell")
    p.pruefe("Aufträge: 1 Woche", await tab.js("[view,tageAnzahl(),document.querySelector('[data-view=auftraege]').getAttribute('aria-pressed')]"),
             ["auftraege", 7, "true"])
    p.pruefe("Zeilen", await tab.js(ZEILEN), [
        "# Eingeplant in dieser Woche",
        "Am Wasserturm 4 | P-2026-0118 · Wohnbau Kessler GmbH | Rest 46,00 h",
        "Garage Lindenweg 7 | P-2026-0131 · Familie Sommer | Soll 32,00 h · vorläufig",
        "Sturmschaden Gartenstraße 2 | P-2026-0151 · Notdienst | nach Aufwand",
        "Ortgang Lindenweg 9 | P-2026-0144 · Familie Becker | Soll 8,00 h",
        "Wartung Halle Nord | P-2026-097 · Hausverwaltung Rhein | Wartungsvertrag",
        "Kranvermietung | P-2026-0153 · Beispielbau GmbH | Kran mit Bediener",
        "# Offen, ohne Einsatz in dieser Woche",
        "Dachfenster Krüger | P-2026-0140 · Familie Krüger | Soll 16,00 h · ab 16.11.",  # „vorläufig“ nur im Zeitraum
        "Kaminverwahrung Schulz | P-2026-0149 · Peter Schulz | Soll 6,00 h · ohne Termin",
    ])
    p.pruefe("Name verlinkt die Akte", await tab.js("[...document.querySelectorAll('#planner tr.a-zeile .a-name a')].every(a=>/^\\/projects\\/\\d+\\?auftrag=\\d+$/.test(a.getAttribute('href')))"), True)
    p.pruefe("Wasserturm Mo", await zelle("Am Wasserturm 4", MO), [["fest", ["Tom", "Mia", "Ole", "HS-DK 202"], None]])
    p.pruefe("Wasserturm Mi: niemand", await zelle("Am Wasserturm 4", MI), [["niemand", [], "niemand"]])
    p.pruefe("Wasserturm Fr mit Kai und Kran", await zelle("Am Wasserturm 4", FR), [["fest", ["Tom", "Mia", "Ole", "Kai", "HS-DK 202", "Kran ⚠ (Kran)"], None]])
    p.pruefe("Garage vorläufig", await zelle("Garage Lindenweg 7", DI), [["vorlaeufig", ["Kai", "Nele", "HS-DK 204"], None]])
    p.pruefe("Wartung Do: Nele mit Hinweis", await zelle("Wartung Halle Nord", DO), [["fest", ["Lia", "Nele •", "HS-DK 204"], None]])
    p.pruefe("Kranvermietung Fr", await zelle("Kranvermietung", FR), [["kran", ["Lia", "Kran ⚠ (Kran)"], None]])
    p.pruefe("Zum Einplanen: Titel", await tab.js("document.getElementById('rkTitel').textContent"), "Zum Einplanen")
    p.pruefe("Kolonnen in der Liste", await tab.js("[...document.querySelectorAll('#backlog .chip[data-art=kolonne]')].map(c=>c.textContent.trim())"),
             ["Kolonne Nord", "Kolonne Süd"])
    p.pruefe("Wochenleiste Kai", await leiste("person", "Kai Kolb"), ["eingeplant", "eingeplant", "eingeplant", "eingeplant", "eingeplant"])
    p.pruefe("Wochenleiste Nele", await leiste("person", "Nele Neu"), ["eingeplant", "eingeplant", "eingeplant", "beantragt", "frei"])
    p.pruefe("Wochenleiste Kran", await leiste("geraet", "Kran"), ["frei", "frei", "frei", "frei", "doppelt"])
    p.pruefe("Wochenleiste HS-DK 202", await leiste("geraet", "HS-DK 202"), ["eingeplant", "eingeplant", "eingeplant", "eingeplant", "eingeplant"])
    p.pruefe("Kran mit eigenem Zeichen in der Liste", await tab.js("!!document.querySelector('#backlog .chip[data-art=geraet] .kranzeichen')"), True)
    p.pruefe("nichts ragt über das Fenster", await tab.ueberlauf(), [])
    p.pruefe("1440 hell: rollt nicht, kein Chip gekürzt, Liste offen", await tab.js(PLATZ), [False, [], True])
    await tab.bild("auftraege_1440_hell")
    # der Filter „Warnungen · Hinweise“: nur Aufträge mit einem Einsatz mit Warnung oder Hinweis
    await tab.js("document.getElementById('filterKnopf').click()")
    p.pruefe("Filter: nur mit Warnung oder Hinweis", await tab.js("[...document.querySelectorAll('#planner tr.a-zeile .a-name a')].map(a=>a.textContent.trim())"),
             ["Am Wasserturm 4", "Wartung Halle Nord", "Kranvermietung"])
    await tab.js("document.getElementById('filterKnopf').click()")
    p.pruefe("Filter aus: alle", len(await tab.js("[...document.querySelectorAll('#planner tr.a-zeile')]")), 8)

    # Klick auf eine Karte öffnet ihren Einsatz
    await tab.js(f"document.querySelector('#planner tr.a-zeile td[data-date=\"{DI}\"] .a-einsatz[data-id=\"{seed['garage']}\"]').click()")
    await tab.warten("document.getElementById('einsatzDialog').open")
    p.pruefe("Klick auf die Karte öffnet den Einsatz", await tab.js("einsatz&&einsatz.id"), seed["garage"])
    await tab.js("document.getElementById('einsatzDialog').close()")

    # 2 Wochen: schmalere Chips, Name im title
    await tab.js("(()=>{const s=document.getElementById('rangeDays');s.value='14';s.dispatchEvent(new Event('change'));return true})()")
    await tab.warten("tageAnzahl()===14&&auftragsliste&&auftragsliste.end==='2026-11-22'&&!!document.querySelector('#planner tr.a-zeile')")
    await tab.warte_auf_ruhe()
    p.pruefe("2 Wochen: Chip schmal, Name im title", await tab.js(
        f"(()=>{{const c=document.querySelector('#planner td[data-date=\"{MO}\"] .chip[data-art=person]');return [c.textContent.trim(),c.title]}})()"),
             ["To", "Tom Monteur"])
    p.pruefe("2 Wochen gemerkt für Aufträge", await tab.js("JSON.parse(localStorage.getItem('plantafel_zeitraum')).auftraege"), 14)
    await tab.js("(()=>{const s=document.getElementById('rangeDays');s.value='7';s.dispatchEvent(new Event('change'));return true})()")
    await tab.warten("tageAnzahl()===7&&auftragsliste&&auftragsliste.end==='2026-11-15'")
    await tab.warte_auf_ruhe()
    await tab.js("setView('teams')")
    await tab.warten("view==='teams'&&tageAnzahl()===14&&!!document.querySelector('#planner .planner-row')")
    await tab.warte_auf_ruhe()
    p.pruefe("Kolonnen wieder 2 Wochen, „Nicht eingeplant“", await tab.js("[tageAnzahl(),document.getElementById('rkTitel').textContent]"),
             [14, "Nicht eingeplant"])

    await laden(tab, p, 2, "dark", "1440 dunkel")
    p.pruefe("1440 dunkel: Thema", await tab.js("document.documentElement.getAttribute('data-theme')"), "dark")
    await tab.bild("auftraege_1440_dunkel")
    await tab.fenster(1280, 1000)
    for n, thema in ((3, "light"), (4, "dark")):
        name = "hell" if thema == "light" else "dunkel"
        await laden(tab, p, n, thema, f"1280 {name}")
        p.pruefe(f"1280 {name}: Zeilen da", len(await tab.js(ZEILEN)), 10)
        p.pruefe(f"1280 {name}: nichts ragt über das Fenster", await tab.ueberlauf(), [])
        # seit 1.9.283 (R5d, Punkt 1): „Zum Einplanen“ offen, die Tafel rollt nicht seitlich (der Freitag ist zu sehen), kein Chip gekürzt
        p.pruefe(f"1280 {name}: Liste offen, rollt nicht, kein Chip gekürzt", await tab.js(PLATZ), [False, [], True])
        p.pruefe(f"1280 {name}: Freitag zu sehen", await tab.js(
            f"(th=>{{const r=th.getBoundingClientRect(),p=document.getElementById('planner').getBoundingClientRect();return r.right<=p.right+0.5}})"
            f"(document.querySelector('#planner thead th[title^=\"{FR[8:]}.{FR[5:7]}.\"]'))"), True)
        p.pruefe(f"1280 {name}: Kran behält sein Zeichen, Geräte ohne Zeichen", await tab.js(
            "[[...document.querySelectorAll('#planner .kranzeichen')].every(s=>s.getClientRects().length>0),"
            "[...document.querySelectorAll('#planner .geraetzeichen')].every(s=>s.getClientRects().length===0)]"), [True, True])
        await tab.bild(f"auftraege_1280_{name}")
    # 1280 px: in „Kolonnen“ ist die Liste zu (unter 1440 px, nichts gemerkt), in „Aufträge“ offen; Zuklappen dort merkt nichts
    await tab.js("setView('teams')")
    await tab.warten("view==='teams'&&!!document.querySelector('#planner .planner-row')")
    await tab.warte_auf_ruhe()
    p.pruefe("1280 Kolonnen: Liste zu", await tab.js("document.getElementById('tafelLayout').classList.contains('rk-zu')"), True)
    await tab.js("setView('auftraege')")
    await tab.warten(BEREIT)
    await tab.warte_auf_ruhe()
    p.pruefe("1280 Aufträge: Liste offen", await tab.js("document.getElementById('tafelLayout').classList.contains('rk-zu')"), False)
    await tab.js("document.getElementById('rkKnopf').click()")
    p.pruefe("1280 Aufträge: zugeklappt, nichts gemerkt", await tab.js(
        "[document.getElementById('tafelLayout').classList.contains('rk-zu'),localStorage.getItem('plantafel_rueckstand')]"), [True, None])
    await tab.js("setView('teams')")
    await tab.warten("view==='teams'&&!!document.querySelector('#planner .planner-row')")
    await tab.js("setView('auftraege')")
    await tab.warten(BEREIT)
    await tab.warte_auf_ruhe()
    p.pruefe("1280 Aufträge: beim nächsten Wechsel wieder offen", await tab.js("document.getElementById('tafelLayout').classList.contains('rk-zu')"), False)
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-11 10:00", silbentrennung=True))
