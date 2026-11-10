"""Klicktest: ein Gerät, ein Formular (Geräte-Runde, seit 1.9.297) -- die Betriebsmittelseite mit dem Haken „Auf der Plantafel einplanbar“.

Testdaten (stehende Uhr Mi 11.11.2026 10:00): Anna (Admin) und Bea (Büro – Auftrag). Geräte mit Plantafel: Pritsche HS-DK 202 (MAN, Kurzname „HS-DK 202“,
Postfach), Autokran (Kurzname „Kran“, eingeplant Fr 13.–Sa 14.11.). Ohne Plantafel: Leiter Alu 6 m, Mein Anhänger, Rüttelplatte Wacker. Ein freies
Plantafel-Gerät ohne Betriebsmittel: Anhänger Humbaur (nur über Umwege möglich).

    Mit Haken   die Angaben oben (aus dem Plantafel-Gerät), der Abschnitt „Plantafel“ mit Kurzname und Postfach (nur lesen, Link in die Einstellungen nur
                für den Admin), keine Auswahl, nirgends das Wort „Ressource“; Kurzname und Bezeichnung ändern -> im Plantafel-Gerät gespeichert, die Seite
                bleibt auf dem Gerät
    Ohne Haken  kein Abschnitt; Haken setzen: Abschnitt und Typ als Pflicht, die Auswahl „Vorhandenes Plantafel-Gerät verknüpfen“ (es gibt ein freies);
                mit Kurzname speichern -> ein neues Plantafel-Gerät mit den Angaben oben
    Verknüpfen  „Mein Anhänger“ mit dem freien Anhänger Humbaur: die Angaben oben wechseln, gespeichert ist die Verknüpfung
    Entfernen   am Kran (noch eingeplant): Rückfrage, abgelehnt -> nichts; bestätigt -> ohne Plantafel, Angaben gewandert, das Plantafel-Gerät inaktiv
    Büro – A.   Postfach zu sehen, kein Link
    Bilder      Gerät mit und ohne Haken bei 1440, 1280 und 412 px, hell und dunkel; bei 412 px läuft nichts über

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_geraete.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "typeof asset!=='undefined'&&!!asset&&document.getElementById('editName').value!==''"
FORMULAR = ("[document.getElementById('editName').value,document.getElementById('editType').value,document.getElementById('editManufacturer').value,"
            "document.getElementById('editIdentifier').value,document.getElementById('editEinplanbar').checked,document.getElementById('plantafelAbschnitt').hidden,"
            "document.getElementById('editKurzname').value,document.getElementById('postfachText').textContent,document.getElementById('postfachLink').hidden,"
            "document.getElementById('verknuepfenWrap').hidden]")
OHNE_WORT = "!document.querySelector('main').innerText.includes('Ressource')"
GESPEICHERT = "document.getElementById('editorStatus').textContent==='Gespeichert.'"
DIALOGE = "window.__fragen=[];window.confirm=m=>{window.__fragen.push(String(m));return window.__antwort!==false};"


def setzen(feld: str, wert: str) -> str:
    return f"(e=>{{e.value={json.dumps(wert)};e.dispatchEvent(new Event('input',{{bubbles:true}}));e.dispatchEvent(new Event('change',{{bubbles:true}}));return true}})(document.getElementById({json.dumps(feld)}))"


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.models import AppUser, Customer, Employee, OperationalAsset, OperationalResource, Order, OrderItem, Project, Property
    from app.planning import create_slot
    from app.project_pipeline_columns import default_pipeline_column_id

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    pritsche = OperationalResource(resource_number="F-202", resource_type="Fahrzeug", name="Pritsche HS-DK 202", manufacturer="MAN", identifier="HS-DK 202",
                                   kurzname="HS-DK 202", outlook_mailbox="pritsche202@example.test", active=True)
    kran = OperationalResource(resource_number="K-1", resource_type="Kran", name="Autokran", manufacturer="Liebherr", kurzname="Kran", active=True)
    frei = OperationalResource(resource_number="A-1", resource_type="Anhänger", name="Anhänger Humbaur", identifier="HS-A 77", active=True)
    ute = Employee(employee_number="E-1", first_name="Ute", last_name="Ufer", employee_group="gewerblich", active=True, hourly_wage=Decimal("22.00"))
    db.add_all([anna, bea, pritsche, kran, frei, ute])
    db.flush()
    bm_p = OperationalAsset(resource_id=pritsche.id, notes="TÜV im Mai", active=True)
    bm_k = OperationalAsset(resource_id=kran.id, active=True)
    leiter = OperationalAsset(name="Leiter Alu 6 m", asset_type="Gerät / Werkzeug", asset_number="BM-12", active=True)
    eigen = OperationalAsset(name="Mein Anhänger", asset_type="Anhänger", active=True)
    platte = OperationalAsset(name="Rüttelplatte Wacker", asset_type="Maschine", manufacturer="Wacker Neuson", asset_number="BM-31", active=True)
    db.add_all([bm_p, bm_k, leiter, eigen, platte])
    kunde = Customer(name="Beispielbau GmbH", last_name="Beispielbau GmbH", is_consumer=False)
    db.add(kunde)
    db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Süd", street="Halle Süd", postal_code="52531", city="Übach-Palenberg")
    db.add(objekt)
    db.flush()
    projekt = Project(project_number="P-2026-0201", name="Halle Süd", customer_id=kunde.id, property_id=objekt.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt)
    db.flush()
    auftrag = Order(order_number="AUF-2026-0201", project_id=projekt.id, source_quote_id=901, quote_number_snapshot="A-KT-1", title="Halle Süd",
                    customer_name=kunde.name, property_name="Halle Süd", property_address="Halle Süd\n52531 Übach-Palenberg")
    db.add(auftrag)
    db.flush()
    db.add(OrderItem(order_id=auftrag.id, sort_order=10, position_number="1", short_text="Arbeit", quantity=Decimal("1"), unit="psch", unit_price=Decimal("1")))
    db.commit()
    create_slot(db, order_id=auftrag.id, team_id=None, employee_ids=[ute.id], geraete=[{"resource_id": kran.id, "tage": None}], start_date=date(2026, 11, 13),
                end_date=date(2026, 11, 14), planned_hours=Decimal("8"), trotzdem_planen=True)
    return {"anna": k.cookies(anna), "bea": k.cookies(bea), "p": bm_p.id, "k": bm_k.id, "leiter": leiter.id, "eigen": eigen.id, "platte": platte.id,
            "rp": pritsche.id, "rk": kran.id, "frei": frei.id}


async def laden(tab, p, asset_id: int, n: int, anlass: str) -> None:
    await tab.js("window.__dkVorDemNeuladen=1")
    p.pruefe(f"{anlass}: geladen", await tab.oeffnen(f"/betriebsmittel/{asset_id}?n={n}", BEREIT), True)
    p.pruefe(f"{anlass}: wirklich neu geladen", await tab.js("window.__dkVorDemNeuladen===undefined"), True)
    await tab.warte_auf_ruhe()


async def speichern(tab, p, anlass: str) -> None:
    await tab.js("document.getElementById('editorStatus').textContent=''")
    await tab.js("document.querySelector('.editor-card button[onclick=\"saveAsset()\"]').click()")
    await tab.warte_auf_ruhe()
    p.pruefe(f"{anlass}: gespeichert", await tab.warten(GESPEICHERT, 10), True)


async def api(tab, pfad: str):
    return await tab.js(f"fetch({json.dumps(pfad)}).then(r=>r.json())")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=DIALOGE)
    await tab.fenster(1440, 1000)
    await tab.anmelden(seed["anna"])
    await tab.js("localStorage.setItem('erp_theme','light')")
    n = 0

    # --- mit Haken: die Pritsche
    n += 1
    await laden(tab, p, seed["p"], n, "Pritsche")
    p.pruefe("Pritsche: Angaben oben, Abschnitt Plantafel, Postfach mit Link, keine Auswahl", await tab.js(FORMULAR),
             ["Pritsche HS-DK 202", "Fahrzeug", "MAN", "HS-DK 202", True, False, "HS-DK 202", "pritsche202@example.test", False, True])
    p.pruefe("Pritsche: Typ als Pflicht", await tab.js("document.getElementById('typPflicht').hidden"), False)
    p.pruefe("Pritsche: nirgends „Ressource“", await tab.js(OHNE_WORT), True)
    p.pruefe("Pritsche: Link führt in die Einstellungen", await tab.js("document.querySelector('#postfachLink a').getAttribute('href')"), "/settings#outlook-sync")
    await tab.js(setzen("editKurzname", "HS 202"))
    await tab.js(setzen("editName", "Pritsche HS-DK 202 MAN"))
    await speichern(tab, p, "Pritsche")
    ressource = await api(tab, f"/api/resources/{seed['rp']}")
    p.pruefe("Pritsche: im Plantafel-Gerät gespeichert, die Seite bleibt auf dem Gerät", [ressource["name"], ressource["kurzname"], await tab.js("location.pathname")],
             ["Pritsche HS-DK 202 MAN", "HS 202", f"/betriebsmittel/{seed['p']}"])
    n += 1
    await laden(tab, p, seed["p"], n, "Pritsche neu geladen")
    p.pruefe("Pritsche neu geladen: Werte stehen", await tab.js("[document.getElementById('editName').value,document.getElementById('editKurzname').value]"),
             ["Pritsche HS-DK 202 MAN", "HS 202"])

    # --- ohne Haken: die Leiter -- Haken setzen legt ein Plantafel-Gerät an
    n += 1
    await laden(tab, p, seed["leiter"], n, "Leiter")
    p.pruefe("Leiter: kein Abschnitt, Typ ohne Pflicht", await tab.js("[document.getElementById('plantafelAbschnitt').hidden,document.getElementById('typPflicht').hidden]"),
             [True, True])
    await tab.js("document.getElementById('editEinplanbar').click()")
    p.pruefe("Leiter mit Haken: Abschnitt, Typ als Pflicht, Auswahl mit dem freien Gerät", await tab.js(
        "[document.getElementById('plantafelAbschnitt').hidden,document.getElementById('typPflicht').hidden,document.getElementById('verknuepfenWrap').hidden,"
        "[...document.getElementById('editVerknuepfen').options].map(o=>o.textContent)]"),
             [False, False, False, ["— neues Plantafel-Gerät —", "Anhänger · Anhänger Humbaur"]])
    await tab.js(setzen("editKurzname", "Leiter"))
    await speichern(tab, p, "Leiter")
    leiter = await api(tab, f"/api/operational-assets/{seed['leiter']}")
    p.pruefe("Leiter: neues Plantafel-Gerät mit den Angaben oben", [leiter["einplanbar"], leiter["name"], leiter["asset_type"], leiter["kurzname"],
                                                                    leiter["resource_id"] not in (None, seed["frei"])], [True, "Leiter Alu 6 m", "Gerät / Werkzeug", "Leiter", True])
    p.pruefe("Leiter: danach keine Auswahl mehr", await tab.js("document.getElementById('verknuepfenWrap').hidden"), True)

    # --- verknüpfen: „Mein Anhänger“ mit dem freien Anhänger Humbaur
    n += 1
    await laden(tab, p, seed["eigen"], n, "Mein Anhänger")
    await tab.js("document.getElementById('editEinplanbar').click()")
    await tab.js(setzen("editVerknuepfen", str(seed["frei"])))
    p.pruefe("Verknüpfen: die Angaben oben vom vorhandenen Gerät", await tab.js(
        "[document.getElementById('editName').value,document.getElementById('editIdentifier').value,document.getElementById('editType').value]"),
             ["Anhänger Humbaur", "HS-A 77", "Anhänger"])
    await speichern(tab, p, "Verknüpfen")
    eigen = await api(tab, f"/api/operational-assets/{seed['eigen']}")
    p.pruefe("Verknüpfen: gespeichert", [eigen["resource_id"], eigen["name"]], [seed["frei"], "Anhänger Humbaur"])

    # --- Haken entfernen am Kran: noch eingeplant -> Rückfrage
    n += 1
    await laden(tab, p, seed["k"], n, "Kran")
    await tab.js("window.__antwort=false;window.__fragen=[]")
    await tab.js("document.getElementById('editEinplanbar').click()")
    await tab.js("document.querySelector('.editor-card button[onclick=\"saveAsset()\"]').click()")
    await tab.warte_auf_ruhe()
    p.pruefe("Kran: Rückfrage nennt den Einsatz", await tab.warten("window.__fragen.length===1&&window.__fragen[0].includes('noch eingeplant')"
                                                                    "&&window.__fragen[0].includes('Halle Süd')", 10), True)
    p.pruefe("Kran: abgelehnt, nichts gespeichert", (await api(tab, f"/api/operational-assets/{seed['k']}"))["einplanbar"], True)
    await tab.js("window.__antwort=true;window.__fragen=[]")
    await speichern(tab, p, "Kran bestätigt")
    kran = await api(tab, f"/api/operational-assets/{seed['k']}")
    p.pruefe("Kran: ohne Plantafel, Angaben gewandert, Plantafel-Gerät inaktiv", [kran["einplanbar"], kran["name"], kran["manufacturer"],
                                                                                 (await api(tab, f"/api/resources/{seed['rk']}"))["active"]],
             [False, "Autokran", "Liebherr", False])

    # --- Büro – Auftrag: Postfach zu sehen, kein Link
    await tab.anmelden(seed["bea"])
    n += 1
    await laden(tab, p, seed["p"], n, "Bea")
    p.pruefe("Bea: Postfach ohne Link", await tab.js("[document.getElementById('postfachText').textContent,document.getElementById('postfachLink').hidden]"),
             ["pritsche202@example.test", True])
    await tab.anmelden(seed["anna"])

    # --- Bilder: mit und ohne Haken, 1440 / 1280 / 412 px, hell und dunkel
    for breite, mobil in ((1440, False), (1280, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            for asset_id, was in ((seed["p"], "mit_haken"), (seed["platte"], "ohne_haken")):
                n += 1
                await laden(tab, p, asset_id, n, f"{was} {breite} {name}")
                p.pruefe(f"{was} {breite} {name}: Abschnitt Plantafel {'da' if was == 'mit_haken' else 'weg'}, kein „Ressource“",
                         [await tab.js("document.getElementById('plantafelAbschnitt').hidden"), await tab.js(OHNE_WORT)], [was != "mit_haken", True])
                if breite == 412:
                    p.pruefe(f"{was} 412 {name}: nichts läuft über", await tab.ueberlauf(), [])
                await tab.bild_ganz(f"geraet_{was}_{breite}_{name}")  # die ganze Seite: der Abschnitt „Plantafel“ liegt bei 412 px weit unten
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-11 10:00"))
