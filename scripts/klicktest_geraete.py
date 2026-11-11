"""Klicktest: ein Gerät, ein Formular (Geräte-Runde, seit 1.9.297) -- die Betriebsmittelseite mit dem Haken „Auf der Plantafel einplanbar“.

Testdaten (stehende Uhr Mi 11.11.2026 10:00): Anna (Admin) und Bea (Büro – Auftrag). Geräte mit Plantafel: Pritsche HS-DK 202 (MAN, Kurzname „HS-DK 202“,
Postfach), Autokran (Kurzname „Kran“, eingeplant Fr 13.–Sa 14.11.). Ohne Plantafel: Leiter Alu 6 m, Mein Anhänger, Rüttelplatte Wacker. Ein freies
Plantafel-Gerät ohne Betriebsmittel: Anhänger Humbaur (nur über Umwege möglich). Inaktiv: Kompressor alt (seit 1.9.302).

    Mit Haken   die Angaben oben (aus dem Plantafel-Gerät), der Abschnitt „Plantafel“ mit Kurzname und Postfach (nur lesen, Link in die Einstellungen nur
                für den Admin), keine Auswahl, nirgends das Wort „Ressource“; Kurzname und Bezeichnung ändern -> im Plantafel-Gerät gespeichert, die Seite
                bleibt auf dem Gerät
    Ohne Haken  kein Abschnitt; Haken setzen: Abschnitt und Typ als Pflicht, die Auswahl „Vorhandenes Plantafel-Gerät verknüpfen“ (es gibt ein freies);
                mit Kurzname speichern -> ein neues Plantafel-Gerät mit den Angaben oben
    Verknüpfen  „Mein Anhänger“ mit dem freien Anhänger Humbaur: die Angaben oben wechseln, gespeichert ist die Verknüpfung
    Entfernen   am Kran (noch eingeplant): Rückfrage, abgelehnt -> nichts; bestätigt -> ohne Plantafel, Angaben gewandert, das Plantafel-Gerät inaktiv
    Büro – A.   Postfach zu sehen, kein Link
    Liste       (seit 1.9.298) Stammdaten -> Betriebsmittel: „Plantafel“ an den Geräten mit Haken; ein Plantafel-Gerät ohne Betriebsmittel (hier über die
                Schnittstelle angelegt, „Hubsteiger Genie“) als „nur Plantafel“ mit „Betriebsmittel anlegen“, im Untertitel mitgezählt; nirgends „Ressource“
    Anlegen     „Betriebsmittel anlegen“ öffnet das Formular mit Haken und dem Gerät verknüpft -> gespeichert, auf der Seite des Geräts; „+ Hinzufügen“ mit
                Haken und Kurzname legt ein neues planbares Gerät an (Minibagger, „MB 17“) -> Seite des Geräts; die Suche findet es über „MB 17“
    Aufbau      (seit 1.9.304) „Betriebsmittel anlegen“ wie die Seite des Geräts: dieselben Beschriftungen in derselben Reihenfolge, jede über ihrem Feld,
                bei 1440 und 1280 px zwei Spalten, bei 412 px eine; der Abschnitt „Plantafel“ mit Überschrift; „Im Einsatzbericht auswählbar“ und
                „Bedienungshinweise“ werden mit gespeichert
    Inaktive    (seit 1.9.302) „Inaktive ausblenden“ über der Liste: angehakt (Vorgabe) fehlen der Kompressor (inaktiv) und die Reste ohne Betriebsmittel
                (der Kran nach dem Entfernen des Hakens, ein inaktiver Rüttler über die Schnittstelle), daneben „3 inaktiv“; ohne Haken stehen sie grau da, die
                Reste als „nur Plantafel · inaktiv“; die Wahl bleibt nach dem Neuladen, die Mitarbeiterliste bleibt angehakt; „Betriebsmittel anlegen“ am
                Rüttler: verknüpft, „(inaktiv)“ in der Auswahl, Status Inaktiv -> gespeichert bleiben Gerät und Plantafel-Gerät inaktiv
    Suche       (seit 1.9.303) die Seite „Suche“ findet zu „Autokran“ das Betriebsmittel und den Rest des Krans als „nur Plantafel · inaktiv“; der Klick
                führt ins Anlegen mit dem Gerät (Haken, verknüpft, Status Inaktiv)
    Dokumente   (seit 1.9.307) im Anlegen bei 1440 und 1280 px Art, Datei und „+ Vormerken“ in einer Zeile, bei 412 px untereinander, Auswahl und Dateifeld
                so breit wie die Karte (bis 1.9.306 schnitten sie bei 412 px ihren Text ab); in der Liste steht die Nummer (BM-12) auf einer Zeile
    Rest        (seit 1.9.305) die Auswahl beim Anlegen und auf der Seite des Geräts bietet auch den inaktiven Rest des Krans an („(inaktiv)“); am Kran
                verknüpft -> wieder auf der Plantafel, aktiv wie der Kran. „Löschen“ steht nur an einem Rest, an dem nichts hängt (der Rüttler, die
                Hebebühne -- nicht der eingeplante Kran); nach der Rückfrage ist die Hebebühne weg
    Bilder      Gerät mit und ohne Haken, neues planbares Gerät anlegen (vor dem Speichern), Liste mit und ohne Haken bei „Inaktive ausblenden“ -- bei 1440,
                1280 und 412 px, hell und dunkel; bei 412 px läuft nichts über

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
FORM_BEREIT = "typeof assetResources!=='undefined'&&!!document.getElementById('assetEinplanbar')"
LISTE_BEREIT = "!!document.querySelector('#content tbody tr td')"
KAESTCHEN = "[document.getElementById('bmInaktiveAusblenden').checked,document.getElementById('bmInaktivZahl').textContent]"
# seit 1.9.302: jede inaktive Zeile in der Farbe des Hinweises (grau), eine aktive nicht
GRAU = ("(()=>{const grau=getComputedStyle(document.getElementById('bmInaktivZahl')).color;const z=[...document.querySelectorAll('#content tbody tr')];"
        "return z.filter(r=>r.classList.contains('inaktiv')).every(r=>getComputedStyle(r.cells[2].querySelector('b')).color===grau)"
        "&&z.filter(r=>!r.classList.contains('inaktiv')).every(r=>getComputedStyle(r.cells[2].querySelector('b')).color!==grau)})()")
# seit 1.9.305 der erste Link der letzten Spalte (dort steht an einem Rest ohne alles auch „Löschen“), bis 1.9.304 der Text der ganzen Zelle
LISTE = ("[...document.querySelectorAll('#content tbody tr')].filter(r=>r.cells.length>2).map(r=>[r.cells[2].querySelector('b').textContent,"
         "[...r.cells[2].querySelectorAll('.pill')].map(p=>p.textContent).join(' '),r.cells[r.cells.length-1].querySelector('a')?.textContent||''])")
# seit 1.9.307: die Zeile der Dokumente -- [Art, Datei, Knopf untereinander?, Breite von Art und Datei in px]
DOKUMENTE = ("(()=>{const a=document.getElementById('assetDocType').getBoundingClientRect(),d=document.getElementById('assetDocFile').getBoundingClientRect(),"
             "k=document.querySelector('.dok-zeile>button').getBoundingClientRect();return [a.bottom<=d.top&&d.bottom<=k.top,Math.round(a.width),Math.round(d.width)]})()")
# seit 1.9.307: die Nummer der Leiter (BM-12) -- über wie viele Zeilen ihr Text läuft
NUMMER_ZEILEN = ("(()=>{const r=[...document.querySelectorAll('#content tbody tr')].find(z=>z.querySelector('b')?.textContent==='Leiter Alu 6 m');"
                 "const g=document.createRange();g.selectNodeContents(r.cells[0]);return [r.cells[0].textContent,g.getClientRects().length]})()")
# seit 1.9.305: die Zeilen mit „Löschen“
LOESCHEN = ("[...document.querySelectorAll('#content tbody tr')].filter(r=>[...r.querySelectorAll('a[data-klick=\"geraetLoeschen\"]')]"
            ".some(a=>a.textContent==='Löschen')).map(r=>r.cells[2].querySelector('b').textContent).sort()")
GERAETESEITE = "/^\\/betriebsmittel\\/\\d+$/.test(location.pathname)&&" + BEREIT
# seit 1.9.304: die Beschriftungen der Angaben -- „Betriebsmittel anlegen“ (erster Block) und die Seite des Geräts (Karte „Stammdaten“)
BESCHRIFTUNGEN_ANLEGEN = "[...document.querySelectorAll('#form > .felder-oben:first-child > .field')].map(f=>f.querySelector('label').innerText.trim())"
BESCHRIFTUNGEN_GERAET = "[...document.querySelector('.editor-card').querySelectorAll(':scope > .fields-2col > .field')].map(f=>f.querySelector('label').innerText.trim())"
# jede Beschriftung über ihrem Feld; zwei Spalten, wenn Bezeichnung und Typ nebeneinander stehen
OBEN = ("[...document.querySelectorAll('#form .felder-oben .field')].filter(f=>f.querySelector(':scope>label')&&f.querySelector(':scope>input:not([type=checkbox]),:scope>select,:scope>textarea'))"
        ".every(f=>f.querySelector(':scope>label').getBoundingClientRect().bottom<=f.querySelector(':scope>input:not([type=checkbox]),:scope>select,:scope>textarea').getBoundingClientRect().top+1)")
SPALTEN = "(()=>{const a=document.getElementById('assetName').getBoundingClientRect(),b=document.getElementById('assetType').getBoundingClientRect();return Math.abs(a.top-b.top)<2?2:1})()"
# das Häkchen neben seiner Beschriftung (auf einer Höhe, links davon) -- wie auf der Seite des Geräts
HAKEN_IN_ZEILE = ("(()=>{const h=document.getElementById('assetEinplanbar').getBoundingClientRect(),l=document.querySelector('label[for=assetEinplanbar]').getBoundingClientRect();"
                  "return h.right<=l.left&&Math.abs((h.top+h.bottom)/2-(l.top+l.bottom)/2)<8})()")
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
    alt = OperationalAsset(name="Kompressor alt", asset_type="Maschine", asset_number="BM-9", active=False)  # seit 1.9.302: inaktiv
    db.add_all([bm_p, bm_k, leiter, eigen, platte, alt])
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


async def neues_geraet(tab) -> None:
    """seit 1.9.298: das Anlegen-Formular für ein planbares Gerät ausfüllen (ohne zu speichern)"""
    for feld, wert in (("assetName", "Minibagger Kubota U17"), ("assetType", "Maschine"), ("assetManufacturer", "Kubota"), ("assetNumber", "BM-41"),
                       ("assetSelectable", "1"), ("assetUsageNotes", "Nur mit Einweisung")):  # die letzten beiden seit 1.9.304
        await tab.js(setzen(feld, wert))
    await tab.js("(e=>{if(!e.checked)e.click();return true})(document.getElementById('assetEinplanbar'))")
    await tab.js(setzen("assetKurzname", "MB 17"))


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

    # --- seit 1.9.298 (Punkt 3): Liste, „Betriebsmittel anlegen“, neues planbares Gerät, Suche
    # ein Plantafel-Gerät ohne Betriebsmittel entsteht nur über Umwege -- hier über die Schnittstelle der Ressourcen (die das Formular bei ausgeschaltetem Modul nutzt)
    hub = await tab.js("fetch('/api/resources',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'Hubsteiger Genie',"
                       "resource_type:'Maschine',kurzname:'Hub'})}).then(r=>r.json()).then(r=>r.id)")
    p.pruefe("Liste geladen", await tab.oeffnen("/master-data?n=1#assets", LISTE_BEREIT), True)
    await tab.warte_auf_ruhe()
    liste = await tab.js(LISTE)
    p.pruefe("Liste: Plantafel und nur Plantafel", [z for z in liste if z[0] in ("Pritsche HS-DK 202 MAN", "Leiter Alu 6 m", "Rüttelplatte Wacker", "Hubsteiger Genie")],
             [["Pritsche HS-DK 202 MAN", "Plantafel", "Öffnen"], ["Leiter Alu 6 m", "Plantafel", "Öffnen"], ["Rüttelplatte Wacker", "", "Öffnen"],
              ["Hubsteiger Genie", "nur Plantafel", "Betriebsmittel anlegen"]])
    p.pruefe("Liste: Untertitel zählt „nur Plantafel“, nirgends „Ressource“", [await tab.js("document.getElementById('seitenkopfUntertitel').textContent"),
                                                                             await tab.js(OHNE_WORT)], ["6 inventarisierte Betriebsmittel · 1 nur Plantafel", True])
    await tab.js("[...document.querySelectorAll('#content tbody tr')].find(r=>r.querySelector('b')?.textContent==='Hubsteiger Genie').querySelector('a').click()")
    p.pruefe("Betriebsmittel anlegen: das Formular mit Haken und dem Gerät", await tab.warten(f"location.search==='?ressource={hub}'&&{FORM_BEREIT}&&"
                                                                                             "document.getElementById('assetName').value==='Hubsteiger Genie'", 15), True)
    p.pruefe("Betriebsmittel anlegen: Haken, Abschnitt, Auswahl sichtbar und verknüpft, Kurzname", await tab.js(
        "[document.getElementById('assetEinplanbar').checked,document.getElementById('assetPlantafel').hidden,document.getElementById('assetVerknuepfenWrap').hidden,"
        "document.getElementById('assetVerknuepfen').value,document.getElementById('assetKurzname').value,document.getElementById('assetType').value]"),
             [True, False, False, str(hub), "Hub", "Maschine"])
    await tab.js(setzen("assetNumber", "BM-40"))
    await tab.js("document.getElementById('saveBtn').click()")
    p.pruefe("Betriebsmittel anlegen: gespeichert, auf der Seite des Geräts", await tab.warten(GERAETESEITE, 15), True)
    neu = await api(tab, "/api/operational-assets/" + (await tab.js("location.pathname.split('/').pop()")))
    p.pruefe("Betriebsmittel anlegen: verknüpft", [neu["einplanbar"], neu["resource_id"], neu["name"], neu["asset_number"]], [True, hub, "Hubsteiger Genie", "BM-40"])
    # seit 1.9.304 (Nachrunde, Punkt 4): dieselben Beschriftungen in derselben Reihenfolge wie die Seite des Geräts (ohne Haken: die Rüttelplatte)
    n += 1
    await laden(tab, p, seed["platte"], n, "Rüttelplatte für den Vergleich")
    geraet = await tab.js(BESCHRIFTUNGEN_GERAET)
    p.pruefe("+ Hinzufügen geladen", await tab.oeffnen("/master-data/assets/new", FORM_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Anlegen: Beschriftungen wie auf der Seite des Geräts", [await tab.js(BESCHRIFTUNGEN_ANLEGEN), geraet],
             [["Bezeichnung *", "Typ", "Hersteller", "Modell", "Kennzeichen / Seriennummer", "Betriebsmittelnummer (optional)", "Status",
               "Im Einsatzbericht auswählbar", "Notizen", "Bedienungshinweise (für Monteure sichtbar, z. B. Kurzanleitung, Sicherheitshinweise)",
               "Auf der Plantafel einplanbar"]] * 2)
    # seit 1.9.305 steht der inaktive Rest des Krans in der Auswahl -- bis 1.9.304 war hier „ohne freies Gerät keine Auswahl“ ([True, True, True])
    p.pruefe("+ Hinzufügen: der Rest des Krans in der Auswahl („(inaktiv)“), kein Abschnitt", await tab.js(
        "[document.getElementById('assetVerknuepfenWrap').hidden,document.getElementById('assetPlantafel').hidden,document.getElementById('assetTypPflicht').hidden,"
        "[...document.getElementById('assetVerknuepfen').options].map(o=>o.textContent)]"),
             [False, True, True, ["— neues Plantafel-Gerät —", "Kran · Autokran (inaktiv)"]])
    await neues_geraet(tab)
    p.pruefe("+ Hinzufügen mit Haken: Abschnitt, Typ als Pflicht", await tab.js(
        "[document.getElementById('assetPlantafel').hidden,document.getElementById('assetTypPflicht').hidden]"), [False, False])
    await tab.js("document.getElementById('saveBtn').click()")
    p.pruefe("+ Hinzufügen: gespeichert, auf der Seite des Geräts", await tab.warten(GERAETESEITE, 15), True)
    bagger = await api(tab, "/api/operational-assets/" + (await tab.js("location.pathname.split('/').pop()")))
    p.pruefe("+ Hinzufügen: neues planbares Gerät", [bagger["einplanbar"], bagger["name"], bagger["asset_type"], bagger["manufacturer"], bagger["kurzname"],
                                                     bagger["selectable_in_reports"], bagger["usage_notes"]],
             [True, "Minibagger Kubota U17", "Maschine", "Kubota", "MB 17", True, "Nur mit Einweisung"])  # seit 1.9.304 mit den beiden Feldern der Seite des Geräts
    suche = await tab.js("fetch('/api/search?q='+encodeURIComponent('MB 17')).then(r=>r.json())")
    p.pruefe("Suche über den Kurznamen", [h["title"] for g in suche if g["key"] == "operational_assets" for h in g["hits"]], ["Minibagger Kubota U17"])

    # --- seit 1.9.302 (Nachrunde, Punkt 2): „Inaktive ausblenden“ -- dazu ein inaktiver Rüttler ohne Betriebsmittel (über die Schnittstelle, wie oben)
    ruettler = await tab.js("fetch('/api/resources',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'Rüttler alt',"
                            "resource_type:'Maschine',active:false})}).then(r=>r.json()).then(r=>r.id)")
    p.pruefe("Inaktive: Liste geladen", await tab.oeffnen("/master-data?n=2#assets", LISTE_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Inaktive: angehakt (Vorgabe), Zahl daneben", await tab.js(KAESTCHEN), [True, "3 inaktiv"])
    inaktiv = ("Kompressor alt", "Autokran", "Rüttler alt")
    p.pruefe("Inaktive angehakt: nur das Betriebsmittel Autokran (aktiv, ohne Plantafel)", [z for z in await tab.js(LISTE) if z[0] in inaktiv],
             [["Autokran", "", "Öffnen"]])
    await tab.js("document.getElementById('bmInaktiveAusblenden').click()")
    p.pruefe("Inaktive ohne Haken: drei Zeilen mehr", await tab.warten("document.querySelectorAll('#content tbody tr.inaktiv').length===3", 5), True)
    p.pruefe("Inaktive ohne Haken: Kompressor, die Reste als „nur Plantafel · inaktiv“", sorted(z for z in await tab.js(LISTE) if z[0] in inaktiv),
             [["Autokran", "", "Öffnen"], ["Autokran", "nur Plantafel · inaktiv", "Betriebsmittel anlegen"], ["Kompressor alt", "", "Öffnen"],
              ["Rüttler alt", "nur Plantafel · inaktiv", "Betriebsmittel anlegen"]])
    p.pruefe("Inaktive ohne Haken: „Löschen“ nur am Rüttler (am Kran hängt der Einsatz)", await tab.js(LOESCHEN), ["Rüttler alt"])  # seit 1.9.305
    p.pruefe("Inaktive ohne Haken: grau, Zahl und Untertitel unverändert", [await tab.js(GRAU), await tab.js(KAESTCHEN),
                                                                         await tab.js("document.getElementById('seitenkopfUntertitel').textContent")],
             [True, [False, "3 inaktiv"], "8 inventarisierte Betriebsmittel"])
    p.pruefe("Inaktive: nach dem Neuladen", await tab.oeffnen("/master-data?n=3#assets", LISTE_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Inaktive: die Wahl bleibt", await tab.js("[document.getElementById('bmInaktiveAusblenden').checked,document.querySelectorAll('#content tbody tr.inaktiv').length]"),
             [False, 3])
    p.pruefe("Mitarbeiter geladen", await tab.oeffnen("/master-data?n=4#employees", "!!document.getElementById('inaktiveAusblenden')"), True)
    p.pruefe("Mitarbeiter: eigene Wahl, weiter angehakt", await tab.js("document.getElementById('inaktiveAusblenden').checked"), True)
    p.pruefe("Inaktive: Liste wieder geladen", await tab.oeffnen("/master-data?n=5#assets", LISTE_BEREIT), True)
    await tab.warte_auf_ruhe()
    await tab.js("[...document.querySelectorAll('#content tbody tr')].find(r=>r.querySelector('b')?.textContent==='Rüttler alt').querySelector('a').click()")
    p.pruefe("Rüttler: das Anlegen mit dem Gerät", await tab.warten(f"location.search==='?ressource={ruettler}'&&{FORM_BEREIT}&&"
                                                                   "document.getElementById('assetName').value==='Rüttler alt'", 15), True)
    p.pruefe("Rüttler: Haken, Auswahl mit „(inaktiv)“, Status Inaktiv", await tab.js(
        "[document.getElementById('assetEinplanbar').checked,document.getElementById('assetVerknuepfenWrap').hidden,document.getElementById('assetVerknuepfen').value,"
        "document.getElementById('assetVerknuepfen').selectedOptions[0].textContent,document.getElementById('assetActiveSelect').value]"),
             [True, False, str(ruettler), "Maschine · Rüttler alt (inaktiv)", "0"])
    await tab.js("document.getElementById('saveBtn').click()")
    p.pruefe("Rüttler: gespeichert, auf der Seite des Geräts", await tab.warten(GERAETESEITE, 15), True)
    neu = await api(tab, "/api/operational-assets/" + (await tab.js("location.pathname.split('/').pop()")))
    p.pruefe("Rüttler: verknüpft, beide inaktiv (nicht still wieder aktiv)", [neu["einplanbar"], neu["resource_id"], neu["active"],
                                                                              (await api(tab, f"/api/resources/{ruettler}"))["active"]], [True, ruettler, False, False])

    # --- seit 1.9.303 (Nachrunde, Punkt 3): die Suche findet auch „nur Plantafel“ -- hier den Rest des Krans (inaktiv), Ziel „Betriebsmittel anlegen“
    p.pruefe("Suche „Autokran“ geladen", await tab.oeffnen("/suche?q=Autokran", "document.querySelectorAll('a.result-hit').length>0"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Suche: das Betriebsmittel und das Gerät „nur Plantafel · inaktiv“", await tab.js(
        "[...document.querySelectorAll('a.result-hit')].map(a=>[a.querySelector('.ttl').textContent,a.querySelector('.sub')?.textContent||'',a.getAttribute('href')])"),
             [["Autokran", "Kran · Liebherr", f"/betriebsmittel/{seed['k']}"],
              ["Autokran", "nur Plantafel · inaktiv · Kran · Liebherr", f"/master-data/assets/new?ressource={seed['rk']}"]])
    await tab.js("[...document.querySelectorAll('a.result-hit')].find(a=>a.getAttribute('href').includes('ressource=')).click()")
    p.pruefe("Suche -> Anlegen mit dem Gerät", await tab.warten(f"location.search==='?ressource={seed['rk']}'&&{FORM_BEREIT}&&"
                                                                "document.getElementById('assetName').value==='Autokran'", 15), True)
    p.pruefe("Suche -> Anlegen: Haken, verknüpft, Status Inaktiv", await tab.js(
        "[document.getElementById('assetEinplanbar').checked,document.getElementById('assetVerknuepfen').value,document.getElementById('assetActiveSelect').value]"),
             [True, str(seed["rk"]), "0"])

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
    # seit 1.9.298: neues planbares Gerät anlegen (vor dem Speichern) und die Liste -- dafür noch ein freies Plantafel-Gerät (Zeile „nur Plantafel“, Auswahl)
    await tab.js("fetch('/api/resources',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'Hebebühne JLG',"
                 "resource_type:'Maschine'})}).then(r=>r.json()).then(r=>r.id)")
    for breite, mobil in ((1440, False), (1280, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            n += 1
            p.pruefe(f"anlegen {breite} {name}: geladen", await tab.oeffnen(f"/master-data/assets/new?n={n}", FORM_BEREIT), True)
            await tab.warte_auf_ruhe()
            await neues_geraet(tab)
            p.pruefe(f"anlegen {breite} {name}: Abschnitt da, kein „Ressource“", [await tab.js("document.getElementById('assetPlantafel').hidden"),
                                                                                 await tab.js(OHNE_WORT)], [False, True])
            p.pruefe(f"anlegen {breite} {name}: Beschriftung über dem Feld, {1 if mobil else 2} Spalte(n), Abschnitt mit Überschrift, Häkchen neben „Auf der Plantafel einplanbar“",
                     [await tab.js(OBEN), await tab.js(SPALTEN), await tab.js("document.querySelector('#assetPlantafel > h3')?.textContent"),
                      await tab.js(HAKEN_IN_ZEILE)],
                     [True, 1 if mobil else 2, "Plantafel", True])
            dok = await tab.js(DOKUMENTE)  # seit 1.9.307
            p.pruefe(f"anlegen {breite} {name}: Dokumente {'untereinander, so breit wie die Karte' if mobil else 'in einer Zeile'}",
                     [dok[0], dok[1] >= 300, dok[2] >= 300] if mobil else [dok[0]], [True, True, True] if mobil else [False])
            if breite == 412:
                p.pruefe(f"anlegen 412 {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.bild_ganz(f"anlegen_planbar_{breite}_{name}")
            n += 1
            await tab.js("localStorage.setItem('erp_betriebsmittel_inaktive','ausblenden')")  # seit 1.9.302: angehakt (Vorgabe)
            p.pruefe(f"Liste {breite} {name}: geladen", await tab.oeffnen(f"/master-data?n={n}#assets", LISTE_BEREIT), True)
            await tab.warte_auf_ruhe()
            p.pruefe(f"Liste {breite} {name}: „nur Plantafel“, kein „Ressource“", [[z[1:] for z in await tab.js(LISTE) if z[0] == "Hebebühne JLG"],
                                                                                await tab.js(OHNE_WORT)], [[["nur Plantafel", "Betriebsmittel anlegen"]], True])
            p.pruefe(f"Liste {breite} {name}: die Nummer auf einer Zeile", await tab.js(NUMMER_ZEILEN), ["BM-12", 1])  # seit 1.9.307
            p.pruefe(f"Liste {breite} {name}: angehakt, keine inaktive Zeile", [await tab.js(KAESTCHEN),
                                                                             await tab.js("document.querySelectorAll('#content tbody tr.inaktiv').length")],
                     [[True, "3 inaktiv"], 0])
            if breite == 412:
                p.pruefe(f"Liste 412 {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.bild_ganz(f"liste_{breite}_{name}")
            # seit 1.9.302: dieselbe Liste ohne Haken bei „Inaktive ausblenden“
            n += 1
            await tab.js("localStorage.setItem('erp_betriebsmittel_inaktive','zeigen')")
            p.pruefe(f"Liste ohne Haken {breite} {name}: geladen", await tab.oeffnen(f"/master-data?n={n}#assets", LISTE_BEREIT), True)
            await tab.warte_auf_ruhe()
            p.pruefe(f"Liste ohne Haken {breite} {name}: Kompressor und Kran grau, „nur Plantafel · inaktiv“",
                     [await tab.js(KAESTCHEN), await tab.js(GRAU), [z[1:] for z in await tab.js(LISTE) if z[0] == "Autokran" and z[1]]],
                     [[False, "3 inaktiv"], True, [["nur Plantafel · inaktiv", "Betriebsmittel anlegen"]]])
            p.pruefe(f"Liste ohne Haken {breite} {name}: „Löschen“ nur an der Hebebühne", await tab.js(LOESCHEN), ["Hebebühne JLG"])  # seit 1.9.305
            if breite == 412:
                p.pruefe(f"Liste ohne Haken 412 {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.bild_ganz(f"liste_ohne_haken_{breite}_{name}")

    # --- seit 1.9.305 (Frage 1 der Nachrunde): den Rest des Krans wieder an den Kran; „Löschen“ der Hebebühne
    await tab.fenster(1440, 1000, mobil=False)
    n += 1
    await laden(tab, p, seed["k"], n, "Kran wieder verknüpfen")
    await tab.js("document.getElementById('editEinplanbar').click()")
    p.pruefe("Kran: die Auswahl bietet den Rest an („(inaktiv)“)", await tab.js(
        "[document.getElementById('verknuepfenWrap').hidden,[...document.getElementById('editVerknuepfen').options].map(o=>o.textContent)]"),
             [False, ["— neues Plantafel-Gerät —", "Kran · Autokran (inaktiv)", "Maschine · Hebebühne JLG"]])
    await tab.js(setzen("editVerknuepfen", str(seed["rk"])))
    await speichern(tab, p, "Kran wieder verknüpft")
    kran = await api(tab, f"/api/operational-assets/{seed['k']}")
    p.pruefe("Kran: wieder auf der Plantafel, der Rest aktiv wie der Kran", [kran["einplanbar"], kran["resource_id"], kran["active"],
                                                                           (await api(tab, f"/api/resources/{seed['rk']}"))["active"]], [True, seed["rk"], True, True])
    n += 1
    p.pruefe("Löschen: Liste geladen", await tab.oeffnen(f"/master-data?n={n}#assets", LISTE_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Löschen: nur an der Hebebühne, der Kran ist keine Zeile „nur Plantafel“ mehr",
             [await tab.js(LOESCHEN), [z for z in await tab.js(LISTE) if z[1].startswith("nur Plantafel")]],
             [["Hebebühne JLG"], [["Hebebühne JLG", "nur Plantafel", "Betriebsmittel anlegen"]]])
    await tab.js("window.__fragen=[];window.confirm=m=>{window.__fragen.push(String(m));return true}")
    await tab.js("[...document.querySelectorAll('a[data-klick=\"geraetLoeschen\"]')].find(a=>a.dataset.name==='Hebebühne JLG').click()")
    p.pruefe("Löschen: Rückfrage, danach ist die Hebebühne weg", [await tab.warten(
        "![...document.querySelectorAll('#content tbody b')].some(b=>b.textContent==='Hebebühne JLG')", 10), await tab.js("window.__fragen")],
             [True, ["Plantafel-Gerät „Hebebühne JLG“ löschen? An ihm hängt nichts mehr."]])
    await tab.warte_auf_ruhe()
    p.pruefe("Löschen: gelöscht, nicht nur deaktiviert", [g["name"] for g in await api(tab, "/api/resources") if g["name"] == "Hebebühne JLG"], [])
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-11 10:00"))
