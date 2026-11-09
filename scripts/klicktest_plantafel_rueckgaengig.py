"""Klicktest: Leiste „Rückgängig“ über der Tafel (1.9.282, Stufe 6, R5c, Punkt 4, Antwort 5 zu R5b) und Klick in einen freien Tag in „Aufträge“.

Testdaten wie klicktest_plantafel_ziehen (Zeichnung KW 46, dazu die Pritsche HS-DK 204) und ein Auftrag ohne Einsatz, stehende Uhr Mi 11.11.2026 10:00. Echte Mauseingaben über CDP.

    Kolonnen  „Am Wasserturm 4“ einen Arbeitstag weiter -> Rückfrage (vier Personen doppelt), „Trotzdem planen“ -> Leiste „Am Wasserturm 4: 09.–13.11. →
              10.–16.11.“ mit „Rückgängig“ -> wieder wie vorher, Leiste zu
    Personen  Lias „Sturmschaden“ einen Tag weiter -> Leiste mit Name, Auftrag, Tagen und „Rückgängig“ (Bild); ein Klick auf die Seite schließt sie, der Zug
              bleibt; Oles „Sturmschaden“ in Toms Zeile -> Rückfrage, „Trotzdem planen“ -> Leiste „… Ole Offen → Tom Monteur“, „Rückgängig“ -> wie vorher
    Geräte    die Pritsche 202 „Am Wasserturm“ einen Tag weiter -> Leiste, „Rückgängig“; eine andere Ansicht schließt die Leiste
    Aufträge  Klick in einen freien Tag („Kaminverwahrung Schulz“, nicht eingeplant, am Mo) öffnet den Dialog für diesen Auftrag, nur diesen Tag, ohne
              Kolonne; eine Karte („Ortgang Lindenweg 9“) öffnet weiter ihren Einsatz; keine Leiste
    Bilder    die Leiste in „Kolonnen“ und „Personen“ (1440 px hell), in „Personen“ 1280 px dunkel
    keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_plantafel_rueckgaengig.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_plantafel_tage import UHR_MS, _ansicht, bereit  # noqa: E402
from klicktest_plantafel_ziehen import GERAET_TAGE, PERSON_TAGE, STAND, _warte_stand, _ziehen  # noqa: E402
from klicktest_plantafel_ziehen import befuellen as befuellen_ziehen  # noqa: E402

MO, DI, MI = "2026-11-09", "2026-11-10", "2026-11-11"
BAND = "(()=>{const b=document.getElementById('zugBand');return b&&!b.hidden?[...b.children].map(e=>e.textContent.trim()):null})()"
WASSER = "board.slots.find(s=>s.project_name==='Am Wasserturm 4')"
STURM = "board.slots.find(s=>s.project_name.startsWith('Sturm'))"


def befuellen(db, k):
    """wie klicktest_plantafel_ziehen, dazu ein Auftrag ohne Einsatz („Kaminverwahrung Schulz“, steht unter „Nicht eingeplant“)"""
    from decimal import Decimal

    from app.models import Customer, Order, OrderItem, Project, Property
    from app.project_pipeline_columns import default_pipeline_column_id

    seed = befuellen_ziehen(db, k)
    kunde = Customer(name="Peter Schulz", last_name="Schulz", is_consumer=True)
    db.add(kunde); db.flush()
    prop = Property(customer_id=kunde.id, name="Kaminverwahrung Schulz", street="Kirchstraße 3", postal_code="52531", city="Übach-Palenberg")
    db.add(prop); db.flush()
    projekt = Project(project_number="P-2026-0149", name="Kaminverwahrung Schulz", customer_id=kunde.id, property_id=prop.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    o = Order(order_number="AUF-2026-0149", project_id=projekt.id, source_quote_id=949, quote_number_snapshot="A-KT-149", title="Kaminverwahrung Schulz",
              customer_name=kunde.name, property_name=prop.name, property_address="Kirchstraße 3\n52531 Übach-Palenberg")
    db.add(o); db.flush()
    db.add(OrderItem(order_id=o.id, sort_order=10, position_number="1", short_text="Arbeit", quantity=Decimal("1"), unit="psch", unit_price=Decimal("1")))
    db.commit()
    return {**seed, "kamin": o.id}


async def maus_klick(tab, x, y) -> None:
    for art in ("mousePressed", "mouseReleased"):
        await tab.cmd("Input.dispatchMouseEvent", type=art, x=x, y=y, button="left", buttons=1 if art == "mousePressed" else 0, clickCount=1)


async def rueckgaengig(tab, p, anlass: str, vorher: str) -> None:
    await tab.js("document.querySelector('#zugBand button').click()")
    await _warte_stand(tab, f"{STAND}==={vorher!r}")
    p.pruefe(f"{anlass}: Rückgängig -- wieder wie vorher, Leiste zu", [await tab.js(STAND) == vorher, await tab.js(BAND)], [True, None])


async def personen(tab, p, breite: int, thema: str, vorher: str) -> None:
    await _ansicht(tab, "employees")
    await _ziehen(tab, "Lia Lang", "Sturmschaden", 1)
    await _warte_stand(tab, PERSON_TAGE + "('Lia Lang','Sturmschaden Gartenstraße 2')==='alle'&&" + STURM + f".start_date==={MI!r}")
    p.pruefe(f"Personen {breite} {thema}: Leiste", await tab.js(BAND), ["Lia Lang · Sturmschaden Gartenstraße 2: 10.–11.11. → ab Mi 11.11.", "Rückgängig"])
    await tab.bild(f"leiste_personen_{breite}_{thema}")
    await rueckgaengig(tab, p, f"Personen {breite} {thema}", vorher)


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light');localStorage.removeItem('plantafel_rueckstand')}catch(e){}")
    await tab.browser_uhr_fest(UHR_MS)
    await tab.anmelden(seed["anna"])
    await tab.oeffnen("/planning", bereit(4))
    await tab.warte_auf_ruhe()
    vorher = await tab.js(STAND)
    p.pruefe("ohne Zug keine Leiste", await tab.js(BAND), None)

    # Kolonnen: der ganze Einsatz einen Arbeitstag weiter -- Tom, Mia, Ole und Kai wären dann doppelt: erst die Rückfrage, die Leiste erst danach
    await _ziehen(tab, "Kolonne Nord", "Am Wasserturm", 1)
    await tab.warten("konfliktDialog.open", 8)
    await tab.warte_auf_ruhe()
    p.pruefe("Kolonnen: Rückfrage -- noch keine Leiste", await tab.js(BAND), None)
    await tab.js("document.getElementById('konfliktTrotzdem').click()")
    await _warte_stand(tab, "!konfliktDialog.open&&" + WASSER + f".start_date==={DI!r}")
    p.pruefe("Kolonnen: Leiste", await tab.js(BAND), ["Am Wasserturm 4: 09.–13.11. → 10.–16.11.", "Rückgängig"])
    await tab.bild("leiste_kolonnen_1440_hell")
    await rueckgaengig(tab, p, "Kolonnen", vorher)

    # Personen: eigene Zeile, Leiste, Rückgängig
    await personen(tab, p, 1440, "hell", vorher)
    # ein Klick auf die Seite schließt die Leiste, der Zug bleibt
    await _ziehen(tab, "Lia Lang", "Sturmschaden", 1)
    await _warte_stand(tab, STURM + f".start_date==={MI!r}")
    p.pruefe("Personen: Leiste nach dem zweiten Zug", (await tab.js(BAND) or [""])[0].startswith("Lia Lang · Sturmschaden"), True)
    await tab.js("window.__umk=bandUmkehrung")
    titel = await tab.js("(r=>[r.left+20,r.top+r.height/2])(document.querySelector('h1').getBoundingClientRect())")
    await maus_klick(tab, *titel)
    p.pruefe("Personen: ein Klick auf die Seite schließt die Leiste, der Zug bleibt", [await tab.js(BAND), await tab.js(STURM + ".start_date")], [None, MI])
    await tab.js("(async()=>{await speichern('tafel',()=>api(__umk.pfad,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(__umk.body)}));"
                 "await loadBoard();return true})()")
    await _warte_stand(tab, f"{STAND}==={vorher!r}")
    # andere Zeile mit Rückfrage
    await _ziehen(tab, "Ole Offen", "Sturmschaden", 0, "Tom Monteur")
    await tab.warten("konfliktDialog.open", 8)
    await tab.warte_auf_ruhe()
    p.pruefe("Personen: Rückfrage -- noch keine Leiste", await tab.js(BAND), None)
    await tab.js("document.getElementById('konfliktTrotzdem').click()")
    await _warte_stand(tab, "!konfliktDialog.open&&" + PERSON_TAGE + "('Tom Monteur','Sturmschaden Gartenstraße 2')!==null")
    p.pruefe("Personen: Leiste nach „Trotzdem planen“", await tab.js(BAND), ["Sturmschaden Gartenstraße 2 11.11.: Ole Offen → Tom Monteur", "Rückgängig"])
    await rueckgaengig(tab, p, "Personen, andere Zeile", vorher)

    # Geräte: eigene Zeile, eine andere Ansicht schließt die Leiste
    await _ansicht(tab, "resources")
    await _ziehen(tab, "Pritsche HS-DK 202", "Am Wasserturm", 1)
    await _warte_stand(tab, "JSON.stringify(" + GERAET_TAGE + "('Pritsche HS-DK 202','Am Wasserturm 4'))!==" + repr('"alle"') + "&&" + GERAET_TAGE
                       + f"('Pritsche HS-DK 202','Am Wasserturm 4')[0]==={DI!r}")
    p.pruefe("Geräte: Leiste", await tab.js(BAND), ["Pritsche HS-DK 202 · Am Wasserturm 4: 09.–10.11. → ab Di 10.11.", "Rückgängig"])
    await rueckgaengig(tab, p, "Geräte", vorher)
    await _ziehen(tab, "Pritsche HS-DK 202", "Am Wasserturm", 1)
    await _warte_stand(tab, GERAET_TAGE + f"('Pritsche HS-DK 202','Am Wasserturm 4')[0]==={DI!r}")
    await tab.js("window.__umk=bandUmkehrung")
    await tab.js("setView('teams')")
    p.pruefe("Geräte: eine andere Ansicht schließt die Leiste", await tab.js(BAND), None)
    await tab.js("(async()=>{await speichern('tafel',()=>api(__umk.pfad,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(__umk.body)}));"
                 "await loadBoard();return true})()")
    await _warte_stand(tab, f"{STAND}==={vorher!r}")

    # Aufträge: Klick in einen freien Tag
    await _ansicht(tab, "auftraege")
    await tab.warten("typeof auftragsliste!=='undefined'&&auftragsliste&&!!document.querySelector('#planner tr.a-zeile')")
    await tab.warte_auf_ruhe()
    # ein noch nicht eingeplanter Auftrag: ohne „nur dieser Tag“ schlüge der Dialog fünf Tage vor (Vorschlag aus „Nicht eingeplant“)
    zelle = ("[...document.querySelectorAll('#planner tr.a-zeile')].find(r=>r.querySelector('.a-name a').textContent.trim()==='Kaminverwahrung Schulz')"
             f".querySelector('td[data-date=\"{MO}\"]')")
    p.pruefe("Aufträge: der Tag ist frei", await tab.js(f"{zelle}.querySelectorAll('.a-einsatz').length"), 0)
    punkt = await tab.js(f"(td=>{{td.scrollIntoView({{block:'center'}});const r=td.getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]}})({zelle})")
    await maus_klick(tab, *punkt)
    p.pruefe("Aufträge: Klick in einen freien Tag öffnet den Dialog", await tab.warten("document.getElementById('einsatzDialog').open", 8), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Aufträge: für diesen Auftrag, nur diesen Tag, ohne Kolonne", await tab.js(
        f"[einsatz.id,einsatz.order_id==={seed['kamin']},einsatz.start_date,einsatz.end_date,einsatz.team_id]"),
        [None, True, MO, MO, None])
    await tab.js("document.getElementById('einsatzDialog').close()")
    # eine Karte öffnet weiter ihren Einsatz (nicht den Dialog für einen neuen)
    karte = ("[...document.querySelectorAll('#planner tr.a-zeile')].find(r=>r.querySelector('.a-name a').textContent.trim()==='Ortgang Lindenweg 9')"
             f".querySelector('td[data-date=\"{MI}\"] .a-einsatz')")
    punkt = await tab.js(f"(k=>{{const r=k.getBoundingClientRect();return [r.left+r.width-6,r.top+r.height-4]}})({karte})")
    await maus_klick(tab, *punkt)
    await tab.warten("document.getElementById('einsatzDialog').open", 8)
    await tab.warte_auf_ruhe()
    p.pruefe("Aufträge: eine Karte öffnet ihren Einsatz", await tab.js("einsatz.id===board.slots.find(s=>s.project_name==='Ortgang Lindenweg 9').id"), True)
    await tab.js("document.getElementById('einsatzDialog').close()")
    p.pruefe("Aufträge: keine Leiste über der Tafel", await tab.js(BAND), None)
    await _ansicht(tab, "teams")

    # 1280 px dunkel: die Leiste in „Personen“
    await tab.fenster(1280, 900)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','dark')}catch(e){}")
    await tab.oeffnen("/planning", bereit(4))
    await tab.warte_auf_ruhe()
    await personen(tab, p, 1280, "dunkel", vorher)
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-11 10:00"))
