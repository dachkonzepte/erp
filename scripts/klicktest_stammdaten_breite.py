"""Klicktest: Stammdaten bei 412 px ohne Überlauf, die Mitarbeitertabelle bei 1440 px ohne Rollen (1.9.275).

Testdaten mit langen, wirklichkeitsnahen Werten: fünf Mitarbeiter (Doppelname, lange E-Mail-Adressen, Monatsgehalt, Sachbearbeiter mit Bauleitung, ohne
Nummer und Geburtstag, eine inaktive), dazu je Ansicht ein Eintrag mit langem Namen (Kunde, Objekt, Kolonne, Gerät, Lieferant, Adressbuch, Leistungs- und
Materialkatalog); Anna (Admin) und Bert (Büro – Auftrag).

    412 px     keine der neun Ansichten läuft über (eine Tabelle rollt in ihrem Rahmen)
    1440 px    die Mitarbeitertabelle rollt nicht -- „Bearbeiten“ und „Status“ ganz zu sehen, für Admin und Büro – Auftrag, hell und dunkel, auch ohne
               Silbentrennung (nachgestellt)
    1280 px    seit 1.9.278 das Untermenü oben (unter 1400 px): passt auch ohne Silbentrennung, die E-Mail höchstens zweizeilig (bis 1.9.277 nur mit
               Silbentrennung, die E-Mail bis zu sechs Zeilen)
    Untermenü  links bei 1440 px, oben bei 1400 und 1280 px (seit 1.9.278)
    Telefon    die Telefonnummer einzeilig bei 1440 und 1280 px (seit 1.9.278)
    Spalten    Mitarbeiter (Nr. und Geburtstag darunter) · Funktion (Gruppe und Stunden darunter) · Kontakt · Vergütung (nur ab Büro – Finanzen) ·
               Kosten-Zuordnung · Kennzeichen (Sachbearbeiter, Plantafel bzw. Bauleitung) · Status · Bearbeiten
    Bilder     stammdaten_mitarbeiter_{1440|1280|412}_{hell|dunkel}.png (Vorgabe: Inaktive ausgeblendet)

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_stammdaten_breite.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

ANSICHTEN = ["customers", "properties", "employees", "teams", "assets", "suppliers", "contacts", "catalogs", "materialGroups"]
BEREIT = "!!document.getElementById('inaktiveAusblenden')&&document.querySelectorAll('#content tbody tr').length>0"
KOPF = "[...document.querySelectorAll('#content thead th')].map(th=>th.textContent)"
# die Tabelle im Rahmen: rollt sie? sind die letzten beiden Spalten (Status, Bearbeiten) ganz zu sehen?
ROLLEN = """(()=>{const w=document.querySelector('#content .wrap'),t=w.querySelector('table'),r=w.getBoundingClientRect();
const z=[...t.querySelectorAll('tbody tr')].find(x=>x.cells.length>1);const n=z.cells.length;
const ganz=[z.cells[n-2],z.cells[n-1]].every(c=>{const b=c.getBoundingClientRect();return b.left>=r.left-0.5&&b.right<=r.right+0.5});
const alt=t.style.width;t.style.width='min-content';const mindest=t.offsetWidth;t.style.width=alt;
return {rollt:t.scrollWidth>w.clientWidth,tabelle:t.scrollWidth,rahmen:w.clientWidth,mindest:mindest,letzte_ganz:ganz}})()"""
# seit 1.9.278: liegt das Untermenü links neben der Karte oder darüber?
UNTERMENUE = """(()=>{const s=document.querySelector('aside.side').getBoundingClientRect(),c=document.querySelector('section.card').getBoundingClientRect();
return s.right<=c.left?'links':s.bottom<=c.top?'oben':'?'})()"""
# Zeilen je Telefonnummer und je E-Mail (verschiedene Oberkanten der Zeilen)
ZEILEN = """(sel=>[...document.querySelectorAll('#content '+sel)].map(e=>new Set([...e.getClientRects()].map(r=>Math.round(r.top))).size))"""
OHNE_TRENNUNG = ("(()=>{const s=document.createElement('style');s.id='ohneTrennung';s.textContent='td.trennbar{hyphens:manual!important}';"
                 "document.head.appendChild(s);return true})()")
ZEILE = """(name=>{const z=[...document.querySelectorAll('#content tbody tr')].find(r=>r.cells[0].querySelector('b')?.textContent===name);
if(!z)return null;return [...z.cells].map(c=>c.innerText.replace(/\\s+/g,' ').trim())})"""


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from sqlalchemy import select

    from app.catalogs import create_catalog
    from app.contacts import create_contact
    from app.material_groups import create_material_group
    from app.models import (AppUser, Customer, Employee, EmployeeCompensationSettings, EmployeeCostAllocationSettings, EmployeeFunction,
                            EmployeePlanningSettings, EmployeeProfile, EmployeeRoleSettings, Property, Supplier)
    from app.routers.resource_planning import create_resource, create_team
    from app.schemas import OperationalResourceCreate, TeamCreate, TeamEmployeeInput

    def funktion(name, gruppe):
        f = db.scalar(select(EmployeeFunction).where(EmployeeFunction.name == name))
        if f is None:
            f = EmployeeFunction(name=name, employee_group=gruppe, sort_order=100, active=True)
            db.add(f)
            db.flush()
        return f

    def person(nr, vor, nach, gruppe, fn, zuordnung, *, lohn=None, gehalt=None, mail=None, tel=None, geb=True, aktiv=True, sachbearbeiter=False,
               plantafel=None):
        comp = EmployeeCompensationSettings(compensation_type="fixed_salary" if gehalt else "hourly", monthly_salary=Decimal(gehalt) if gehalt else None)
        e = Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group=gruppe, hourly_wage=Decimal(lohn) if lohn else None,
                     weekly_hours=Decimal("40"), active=aktiv, compensation=comp,
                     profile=EmployeeProfile(email=mail, mobile=tel, birthday=date(1984, 3, 12) if geb else None, function=funktion(fn, gruppe)))
        db.add(e)
        db.flush()
        db.add(EmployeeCostAllocationSettings(employee_id=e.id, allocation_type=zuordnung))
        if sachbearbeiter:
            db.add(EmployeeRoleSettings(employee_id=e.id, available_as_caseworker=True))
        if plantafel:
            db.add(EmployeePlanningSettings(employee_id=e.id, plantafel=plantafel))
        return e

    person("10021", "Christina", "Schmidt-Hoffmann", "kaufmaennisch", "Bürokauffrau", "none", gehalt="3850",
           mail="christina.schmidt-hoffmann@dachkonzepte.gmbh", tel="+49 171 2345678", sachbearbeiter=True)
    maxi = person("10022", "Maximilian", "Ziegelmeier", "gewerblich", "Dachdeckermeister", "labor_rate", lohn="24.50",
                  mail="maximilian.ziegelmeier@dachkonzepte.gmbh", tel="+49 160 98765432", sachbearbeiter=True, plantafel="bauleitung")
    kai = person("10023", "Kai-Uwe", "Brandenburger", "gewerblich", "Dachdeckergeselle", "labor_rate", lohn="21.75",
                 mail="kai-uwe.brandenburger@dachkonzepte.gmbh", tel="+49 151 22334455", plantafel="einplanbar")
    person(None, "Leon", "Wolf", "gewerblich", "Auszubildender Dachdecker", "variable_overhead", lohn="9.50", geb=False, plantafel="einplanbar")
    person("10025", "Ina", "Alt", "kaufmaennisch", "Bürokauffrau", "variable_overhead", lohn="18", mail="ina.alt@dachkonzepte.gmbh", aktiv=False)
    db.commit()

    kunde = Customer(name="Hausverwaltung Rheinblick GmbH & Co. KG", last_name="Hausverwaltung Rheinblick GmbH & Co. KG",
                     email="buchhaltung.objektverwaltung@hausverwaltung-rheinblick.de", phone="+49 211 123456789", street="Kaiserswerther Straße 115",
                     postal_code="40474", city="Düsseldorf-Golzheim")
    db.add(kunde)
    db.flush()
    db.add(Property(customer_id=kunde.id, name="Wohnanlage Am Rheinufer, Haus C (Mehrfamilienhaus mit Tiefgarage)", street="Rheinallee 27–31",
                    postal_code="40474", city="Düsseldorf-Golzheim"))
    db.add(Supplier(supplier_number="L-00042", name="Baustoff-Fachhandel Rheinland-Westfalen GmbH & Co. KG", contact_person="Dr. Hans-Joachim Brandenburger",
                    email="auftragsannahme.duesseldorf@baustoff-fachhandel-rheinland.de", phone="+49 211 987654321", city="Mönchengladbach",
                    country="Deutschland"))
    db.commit()
    create_contact(db, {"kind": "firma", "company_name": "Ingenieurbüro für Bauphysik und Brandschutz Dr. Schmidt-Brandenburger",
                        "email": "sekretariat.bauphysik@ingenieurbuero-schmidt-brandenburger.de", "phone": "+49 211 55566677"})
    create_catalog(db, "Leistungskatalog Steildach und Flachdach 2026 (Hauptkatalog mit Zuschlägen)", "Alle Leistungen des Betriebs")
    create_material_group(db, "Dachziegel, Formsteine und Zubehör (Braas, Creaton, Nelskamp)", "Lieferprogramm 2026")
    create_resource(OperationalResourceCreate(resource_number="G-0007", resource_type="Maschine", name="Raupen-Arbeitsbühne Teupen LEO 23 GT Plus",
                                              identifier="G-0007"), db)
    create_team(TeamCreate(team_number="K-NW", name="Kolonne Nord-West Steildach und Sanierung",
                           employees=[TeamEmployeeInput(employee_id=maxi.id, role="Monteur"), TeamEmployeeInput(employee_id=kai.id, role="Monteur")]),
                db)
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    bert = AppUser(username="bert", display_name="Bert Büro", role="buero_auftrag", password_hash=k.passwort())
    db.add_all([anna, bert])
    db.flush()
    return {"anna": k.cookies(anna), "bert": k.cookies(bert)}


async def laden(tab, p, n: int, thema: str, anlass: str) -> None:
    await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
    await tab.js("window.__dkVorDemNeuladen=1")
    p.pruefe(f"{anlass}: Seite geladen", await tab.oeffnen(f"/master-data?n={n}#employees", BEREIT), True)
    p.pruefe(f"{anlass}: wirklich neu geladen", await tab.js("window.__dkVorDemNeuladen===undefined"), True)
    await tab.warte_auf_ruhe()


async def pruefen(tab, seed, p):
    kopf_admin = ["Mitarbeiter", "Funktion", "Kontakt", "Vergütung", "Kosten-Zuordnung", "Kennzeichen", "Status", ""]
    zeile = lambda name: tab.js(f"({ZEILE})({json.dumps(name)})")  # noqa: E731

    # 1440 px, Admin, hell: Spalten, Inhalt, kein Rollen
    await tab.fenster(1440, 900)
    await tab.anmelden(seed["anna"])
    p.pruefe("Seite geladen", await tab.oeffnen("/master-data#employees", BEREIT), True)  # erst eine Seite, dann das Thema in ihren Speicher
    await laden(tab, p, 1, "light", "1440 hell")
    p.pruefe("1440 hell: Thema hell", await tab.js("document.documentElement.getAttribute('data-theme')"), "light")
    p.pruefe("1440: Spalten", await tab.js(KOPF), kopf_admin)
    p.pruefe("Zeile Maximilian", await zeile("Maximilian Ziegelmeier"), [
        "Maximilian Ziegelmeier Nr. 10022 · Geb. 12.3.1984", "Dachdeckermeister Gewerblich · 40 h/Woche",
        "+49 160 98765432 maximilian.ziegelmeier@dachkonzepte.gmbh", "24,50 €/h", "Verrechnungssatz", "Sachbearbeiter Bauleitung", "Aktiv", "Bearbeiten"])
    p.pruefe("Kennzeichen Christina: nur Sachbearbeiter", (await zeile("Christina Schmidt-Hoffmann"))[5], "Sachbearbeiter")
    p.pruefe("Kennzeichen Kai-Uwe: Plantafel", (await zeile("Kai-Uwe Brandenburger"))[5], "Plantafel")
    p.pruefe("Leon ohne Nummer und Geburtstag: nur der Name", (await zeile("Leon Wolf"))[0], "Leon Wolf")
    r = await tab.js(ROLLEN)
    print(f"    1440 hell: Tabelle {r['tabelle']} px im Rahmen {r['rahmen']} px, mindestens {r['mindest']} px")
    p.pruefe("1440 hell: Tabelle rollt nicht", r["rollt"], False)
    p.pruefe("1440 hell: Status und Bearbeiten ganz zu sehen", r["letzte_ganz"], True)
    p.pruefe("1440: Untermenü links", await tab.js(UNTERMENUE), "links")
    p.pruefe("1440: Telefonnummern einzeilig", set(await tab.js(f"({ZEILEN})('.tel')")), {1})
    await tab.bild("stammdaten_mitarbeiter_1440_hell")
    # ohne Haken: auch mit der inaktiven Ina
    await tab.js("document.getElementById('inaktiveAusblenden').click()")
    p.pruefe("1440 ohne Haken: Ina dabei", (await zeile("Ina Alt") or [None])[6], "Inaktiv")
    p.pruefe("1440 ohne Haken: Tabelle rollt nicht", (await tab.js(ROLLEN))["rollt"], False)
    await tab.js("document.getElementById('inaktiveAusblenden').click()")
    # ohne Trenndaten (nachgestellt): bei 1440 px passt die Tabelle trotzdem
    await tab.js(OHNE_TRENNUNG)
    r = await tab.js(ROLLEN)
    print(f"    1440 ohne Silbentrennung: Tabelle {r['tabelle']} px im Rahmen {r['rahmen']} px, mindestens {r['mindest']} px")
    p.pruefe("1440 ohne Silbentrennung: Tabelle rollt nicht", r["rollt"], False)
    await tab.js("document.getElementById('ohneTrennung').remove()")

    await laden(tab, p, 2, "dark", "1440 dunkel")
    r = await tab.js(ROLLEN)
    p.pruefe("1440 dunkel: Tabelle rollt nicht", r["rollt"], False)
    p.pruefe("1440 dunkel: Status und Bearbeiten ganz zu sehen", r["letzte_ganz"], True)
    await tab.bild("stammdaten_mitarbeiter_1440_dunkel")

    # seit 1.9.278: bei 1400 px steht das Untermenü schon oben
    await tab.fenster(1400, 900)
    await laden(tab, p, 8, "light", "1400")
    p.pruefe("1400: Untermenü oben", await tab.js(UNTERMENUE), "oben")

    # 1280 px: das Untermenü oben (seit 1.9.278)
    await tab.fenster(1280, 900)
    for n, thema in ((3, "light"), (4, "dark")):
        name = "hell" if thema == "light" else "dunkel"
        await laden(tab, p, n, thema, f"1280 {name}")
        r = await tab.js(ROLLEN)
        print(f"    1280 {name}: Tabelle {r['tabelle']} px im Rahmen {r['rahmen']} px, mindestens {r['mindest']} px")
        p.pruefe(f"1280 {name}: Untermenü oben", await tab.js(UNTERMENUE), "oben")
        p.pruefe(f"1280 {name}: Tabelle rollt nicht", r["rollt"], False)
        p.pruefe(f"1280 {name}: Status und Bearbeiten ganz zu sehen", r["letzte_ganz"], True)
        p.pruefe(f"1280 {name}: Telefonnummern einzeilig", set(await tab.js(f"({ZEILEN})('.tel')")), {1})
        zeilen = await tab.js(f"({ZEILEN})('.mail')")
        print(f"    1280 {name}: Zeilen je E-Mail {zeilen}")
        p.pruefe(f"1280 {name}: E-Mail höchstens zweizeilig", max(zeilen) <= 2, True)
        await tab.bild(f"stammdaten_mitarbeiter_1280_{name}")
    await tab.js(OHNE_TRENNUNG)
    r = await tab.js(ROLLEN)
    print(f"    1280 ohne Silbentrennung: Tabelle {r['tabelle']} px im Rahmen {r['rahmen']} px, mindestens {r['mindest']} px")
    p.pruefe("1280 ohne Silbentrennung: Tabelle rollt nicht", r["rollt"], False)
    # seit 1.9.278 (Gegenprobe 278_2b blieb zuerst grün: mit den Testdaten ist die Spalte überall breit genug): die Spalte Kontakt eng gezwungen -- die
    # Telefonnummer bleibt trotzdem in einer Zeile (sie ragt dann hinaus, statt umzubrechen)
    await tab.js("(()=>{const s=document.createElement('style');s.id='eng';s.textContent='#content td.kontakt{width:60px;max-width:60px}';"
                 "document.head.appendChild(s);return true})()")
    p.pruefe("eng (Kontakt 60 px): Telefonnummern einzeilig", set(await tab.js(f"({ZEILEN})('.tel')")), {1})
    await tab.js("document.getElementById('eng').remove()")

    # 412 px: keine Ansicht läuft über
    await tab.fenster(412, 900, mobil=True)
    for n, thema in ((5, "light"), (6, "dark")):
        name = "hell" if thema == "light" else "dunkel"
        await laden(tab, p, n, thema, f"412 {name}")
        p.pruefe(f"412 {name}: Telefonnummern einzeilig (seit 1.9.278)", set(await tab.js(f"({ZEILEN})('.tel')")), {1})
        await tab.bild(f"stammdaten_mitarbeiter_412_{name}")
    for ansicht in ANSICHTEN:
        await tab.js(f"(()=>{{showView({json.dumps(ansicht)});return true}})()")
        await tab.warte_auf_ruhe()
        print(f"    412 {ansicht}: {await tab.js("document.querySelectorAll('#content tbody tr').length")} Zeilen")
        p.pruefe(f"412: „{ansicht}“ läuft nicht über", await tab.ueberlauf(), [])

    # Büro – Auftrag bei 1440 px: ohne Vergütung, rollt nicht
    await tab.fenster(1440, 900)
    await tab.anmelden(seed["bert"])
    await laden(tab, p, 7, "light", "Büro – Auftrag")
    p.pruefe("Büro – Auftrag: Spalten ohne Vergütung", await tab.js(KOPF), [k for k in kopf_admin if k != "Vergütung"])
    r = await tab.js(ROLLEN)
    p.pruefe("Büro – Auftrag: Tabelle rollt nicht", r["rollt"], False)
    p.pruefe("Büro – Auftrag: Status ganz zu sehen", r["letzte_ganz"], True)
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, silbentrennung=True))
