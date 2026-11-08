"""Klicktest: die Plantafel mit der Besetzung je Tag (1.9.264, Stufe 6, R5a, Punkt 5) -- Testdaten nach der Zeichnung
entwurf-stufe6/plantafel-auftraege-regeln.html, Abschnitt „Fundament: Besetzung je Tag“ (KW 46).

Kolonne Nord (Tom KF, Mia, Ole) mit der Pritsche HS-DK 202. „Am Wasserturm 4“ Mo 09.–Fr 13.11. mit Nord: Tom, Mia, Ole und die Pritsche Mo, Di, Do, Fr,
Kai nur Do und Fr -- am Mittwoch niemand. „Sturmschaden Gartenstraße 2“ Di–Mi ohne Kolonne: Lia an beiden Tagen, Ole nur am Mi. „Ortgang Lindenweg 9“ Mi ohne
Kolonne: Tom und Mia. „Garage Lindenweg 7“ Fr ohne Kolonne, vorläufig: Kai. Stehende Uhr Mi 11.11.2026 10:00.

    Kolonnen     Nord: zwei Balken „Am Wasserturm 4 · Tom, Mia, Ole“ (Mo–Di) und „… · Tom, Mia, Ole, Kai“ (Do–Fr), am Mittwoch eine Lücke; die Warnung (Kai
                 doppelt am Fr) nur am Stück Do–Fr. Ohne Kolonne: Sturmschaden, Ortgang, Garage. Kein „Tom doppelt“ (Ortgang am Mi, Wasserturm nicht am Mi).
                 Knopf „1 Warnung“.
    Personen     Ole: Wasserturm Mo–Di und Do–Fr, Sturmschaden nur Mi; Kai: Wasserturm Do–Fr und Garage, „doppelt 13.11.“; Tom ohne „doppelt“
    Dialog       „Einsatz bearbeiten“ (Wasserturm): je Person ihre Tage („nur 09., 10., 12., 13.11.“, Kai „nur 12., 13.11.“), Knöpfe je Tag, Kai am Mi dazu ->
                 gespeichert, danach ein Balken ohne Lücke
    Leer         Garage: Kai abgewählt -> der Dialog sagt es vorher, beim Speichern „Der Einsatz hat dann niemanden mehr.“ -> Behalten -> „Garage Lindenweg 7 ·
                 niemand“; Ortgang: Tom und Mia abgewählt -> Löschen -> weg
    Bilder       Kolonnen, Personen und der Dialog mit den Tagen je Person bei 1440 und 1280 px (1280 neu geladen), hell und dunkel
    keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_plantafel_tage.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

UHR_MS = int(datetime(2026, 11, 11, 10, 0, tzinfo=ZoneInfo("Europe/Berlin")).timestamp() * 1000)
MI = "2026-11-11"


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.models import AppUser, Customer, Employee, OperationalResource, Order, OrderItem, Project, Property, Team, TeamEmployee, TeamResource
    from app.planning import create_slot
    from app.project_pipeline_columns import default_pipeline_column_id

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    L = {}
    for nr, (vor, nach) in enumerate([("Tom", "Monteur"), ("Mia", "Monteurin"), ("Ole", "Offen"), ("Kai", "Kolb"), ("Lia", "Lang")], 1):
        L[vor] = Employee(employee_number=f"E-{nr}", first_name=vor, last_name=nach, employee_group="gewerblich", active=True, hourly_wage=Decimal("22.00"))
    p202 = OperationalResource(resource_number="F-202", resource_type="Fahrzeug", name="Pritsche HS-DK 202", identifier="HS-DK 202", active=True)
    db.add_all([anna, *L.values(), p202]); db.flush()
    nord = Team(name="Kolonne Nord", active=True)
    db.add(nord); db.flush()
    db.add_all([TeamEmployee(team_id=nord.id, employee_id=L["Tom"].id, is_crew_leader=True), TeamEmployee(team_id=nord.id, employee_id=L["Mia"].id),
                TeamEmployee(team_id=nord.id, employee_id=L["Ole"].id), TeamResource(team_id=nord.id, resource_id=p202.id)])
    db.commit()

    def auftrag(nr, objekt, kunde_name):
        kunde = Customer(name=kunde_name, last_name=kunde_name, is_consumer=False)
        db.add(kunde); db.flush()
        prop = Property(customer_id=kunde.id, name=objekt, street=objekt, postal_code="52531", city="Übach-Palenberg")
        db.add(prop); db.flush()
        projekt = Project(project_number=f"P-2026-01{nr}", name=objekt, customer_id=kunde.id, property_id=prop.id, pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        o = Order(order_number=f"AUF-2026-01{nr}", project_id=projekt.id, source_quote_id=900 + nr, quote_number_snapshot=f"A-KT-{nr}", title=objekt,
                  customer_name=kunde.name, property_name=objekt, property_address=f"{objekt}\n52531 Übach-Palenberg")
        db.add(o); db.flush()
        db.add(OrderItem(order_id=o.id, sort_order=10, position_number="1", short_text="Arbeit", quantity=Decimal("1"), unit="psch", unit_price=Decimal("1")))
        db.commit()
        return o

    d = lambda n: date(2026, 11, 9 + n)  # noqa: E731 -- Mo 09.11. + n
    ohne_mi = [d(0), d(1), d(3), d(4)]
    werte = {"planned_hours": Decimal("8"), "trotzdem_planen": True}
    wasserturm = create_slot(db, order_id=auftrag(18, "Am Wasserturm 4", "Wohnbau Kessler GmbH").id, team_id=nord.id, start_date=d(0), end_date=d(4),
                             status="fest", besetzung=[{"employee_id": L[n].id, "tage": ohne_mi} for n in ("Tom", "Mia", "Ole")]
                             + [{"employee_id": L["Kai"].id, "tage": [d(3), d(4)]}], geraete=[{"resource_id": p202.id, "tage": ohne_mi}], **werte)
    create_slot(db, order_id=auftrag(51, "Sturmschaden Gartenstraße 2", "Notdienst").id, team_id=None, start_date=d(1), end_date=d(2), status="fest",
                besetzung=[{"employee_id": L["Lia"].id, "tage": None}, {"employee_id": L["Ole"].id, "tage": [d(2)]}], **werte)
    ortgang = create_slot(db, order_id=auftrag(44, "Ortgang Lindenweg 9", "Familie Becker").id, team_id=None, start_date=d(2), end_date=d(2), status="fest",
                          employee_ids=[L["Tom"].id, L["Mia"].id], **werte)
    garage = create_slot(db, order_id=auftrag(31, "Garage Lindenweg 7", "Familie Sommer").id, team_id=None, start_date=d(4), end_date=d(4), status="vorlaeufig",
                         employee_ids=[L["Kai"].id], **werte)
    return {"anna": k.cookies(anna), "wasserturm": wasserturm.id, "ortgang": ortgang.id, "garage": garage.id, "kai": L["Kai"].id, "tom": L["Tom"].id,
            "mia": L["Mia"].id}


def bereit(n):
    return f"typeof board!=='undefined'&&board&&board.slots&&board.slots.length==={n}&&!!document.querySelector('#planner .planner-row')"


BALKEN_JE_ZEILE = ("(n=>[...[...document.querySelectorAll('#planner .planner-row')].find(z=>z.querySelector('.row-label b').textContent.trim()===n)"
                   ".querySelectorAll('.slot')].map(s=>[s.querySelector('.slot-text').textContent.trim(),"
                   "['abwesend','beantragt','termin','kran','vorlaeufig','fest'].find(c=>s.classList.contains(c))+(s.classList.contains('conflict')?' !':'')]))")
UNTER = ("(n=>[...[...document.querySelectorAll('#planner .planner-row')].find(z=>z.querySelector('.row-label b').textContent.trim()===n)"
         ".querySelectorAll('.row-label .unter')].map(u=>u.textContent.trim()))")
# liegt ein Balken der Zeile über der Spalte des Tags? (Mitte der Spalte)
UEBER_TAG = ("((n,tag)=>{const k=[...document.querySelectorAll('#planner .tagkopf')].find(x=>x.title.startsWith(tag.slice(8,10)+'.'+tag.slice(5,7)+'.'));"
             "const m=(k.getBoundingClientRect().left+k.getBoundingClientRect().right)/2;"
             "const z=[...document.querySelectorAll('#planner .planner-row')].find(z=>z.querySelector('.row-label b').textContent.trim()===n);"
             "return [...z.querySelectorAll('.slot')].filter(s=>{const r=s.getBoundingClientRect();return r.left<m&&r.right>m}).map(s=>s.querySelector('.slot-text').textContent.trim())})")
DIALOG_TAGE = ("[...document.querySelectorAll('#edPersonen .wahl')].filter(l=>l.querySelector('input').checked).map(l=>[l.querySelector('.wahl-name').textContent,"
               "(l.querySelector('[data-klick=personTage]')||{}).textContent||null])")


async def _ansicht(tab, name):
    await tab.js(f"setView('{name}')")
    await tab.warten(f"view==='{name}'")
    await tab.warte_auf_ruhe()


async def _dialog_mit_tagen(tab, seed):
    """Wasserturm öffnen, die Tage von Kai aufklappen."""
    await tab.js(f"openEdit({seed['wasserturm']})")
    await tab.warten("document.getElementById('einsatzDialog').open")
    await tab.warte_auf_ruhe()
    await tab.warten(f"!!document.querySelector('[data-klick=personTage][data-id=\"{seed['kai']}\"]')")
    await tab.js(f"document.querySelector('[data-klick=personTage][data-id=\"{seed['kai']}\"]').click()")
    await tab.warten(f"!document.querySelector('[data-tage-person=\"{seed['kai']}\"]').hidden")


async def _bilder(tab, seed, breite, thema):
    await _ansicht(tab, "teams")
    await tab.bild(f"tage_kolonnen_{breite}_{thema}")
    await _ansicht(tab, "employees")
    await tab.bild(f"tage_personen_{breite}_{thema}")
    await _ansicht(tab, "teams")
    await _dialog_mit_tagen(tab, seed)
    await tab.bild(f"tage_dialog_{breite}_{thema}")
    await tab.js("document.getElementById('einsatzDialog').close()")


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light');localStorage.removeItem('plantafel_rueckstand')}catch(e){}")
    await tab.browser_uhr_fest(UHR_MS)
    await tab.anmelden(seed["anna"])
    await tab.oeffnen("/planning", bereit(4))
    await tab.warte_auf_ruhe()

    # --- Kolonnen: Lücke am Mittwoch, Namen je Stück, Warnung am Stück ---
    p.pruefe("Kolonnen: Nord zwei Stücke, Namen je Stück, Warnung nur Do–Fr", await tab.js(BALKEN_JE_ZEILE + "('Kolonne Nord')"),
             [["Am Wasserturm 4 · Tom, Mia, Ole", "fest"], ["Am Wasserturm 4 · Tom, Mia, Ole, Kai", "fest !"]])
    p.pruefe("Kolonnen: am Mittwoch kein Balken in Nord (Lücke)", await tab.js(UEBER_TAG + f"('Kolonne Nord','{MI}')"), [])
    p.pruefe("Kolonnen: Ohne Kolonne -- Sturmschaden, Ortgang ohne Warnung, Garage mit", await tab.js(BALKEN_JE_ZEILE + "('Ohne Kolonne')"),
             [["Sturmschaden Gartenstraße 2 · Lia, Ole", "fest"], ["Ortgang Lindenweg 9 · Tom, Mia", "fest"], ["Garage Lindenweg 7 · Kai", "vorlaeufig !"]])
    p.pruefe("Knopf: 1 Warnung (Kai am Fr), kein Tom doppelt", await tab.js("document.getElementById('filterText').textContent"), "1 Warnung")

    # --- Personen: je Folge ihrer Tage ---
    await _ansicht(tab, "employees")
    p.pruefe("Personen: Ole Wasserturm Mo–Di und Do–Fr, Sturmschaden nur Mi", await tab.js(BALKEN_JE_ZEILE + "('Ole Offen')"),
             [["Am Wasserturm 4", "fest"], ["Am Wasserturm 4", "fest"], ["Sturmschaden Gartenstraße 2", "fest"]])  # je Einsatz, dann je Folge
    p.pruefe("Personen: Ole am Mi nur beim Sturmschaden", await tab.js(UEBER_TAG + f"('Ole Offen','{MI}')"), ["Sturmschaden Gartenstraße 2"])
    p.pruefe("Personen: Kai Do–Fr und Garage, beide mit Warnung", await tab.js(BALKEN_JE_ZEILE + "('Kai Kolb')"),
             [["Am Wasserturm 4 · mit Nord", "fest !"], ["Garage Lindenweg 7", "vorlaeufig !"]])
    p.pruefe("Personen: Kai „doppelt 13.11.“, Tom ohne", [await tab.js(UNTER + "('Kai Kolb')"), await tab.js(UNTER + "('Tom Monteur')")],
             [["doppelt 13.11."], ["Kolonnenführer"]])
    await _ansicht(tab, "teams")

    # --- Dialog: Tage je Person ---
    await _dialog_mit_tagen(tab, seed)
    p.pruefe("Dialog: je Person ihre Tage", await tab.js(DIALOG_TAGE),
             [["Tom Monteur", "nur 09., 10., 12., 13.11."], ["Mia Monteurin", "nur 09., 10., 12., 13.11."], ["Ole Offen", "nur 09., 10., 12., 13.11."],
              ["Kai Kolb", "nur 12., 13.11."]])
    p.pruefe("Dialog: Kais Tage als Knöpfe, Do und Fr gewählt", await tab.js(
        f"[...document.querySelectorAll('[data-tage-person=\"{seed['kai']}\"] .tag-knopf')].map(b=>[b.textContent,b.getAttribute('aria-pressed')])"),
        [["Mo 09.11.", "false"], ["Di 10.11.", "false"], ["Mi 11.11.", "false"], ["Do 12.11.", "true"], ["Fr 13.11.", "true"]])
    await tab.js("document.getElementById('einsatzDialog').close()")

    # --- Bilder: 1440 hell und dunkel, 1280 hell und dunkel ---
    await _bilder(tab, seed, 1440, "hell")
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','dark')}catch(e){}")
    await tab.oeffnen("/planning", bereit(4))
    await tab.warte_auf_ruhe()
    await _bilder(tab, seed, 1440, "dunkel")
    await tab.fenster(1280, 900)
    await tab.oeffnen("/planning", bereit(4))
    await tab.warte_auf_ruhe()
    await _bilder(tab, seed, 1280, "dunkel")
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")
    await tab.oeffnen("/planning", bereit(4))
    await tab.warte_auf_ruhe()
    await _bilder(tab, seed, 1280, "hell")
    p.pruefe("1280: Nord weiter mit Lücke am Mittwoch", await tab.js(UEBER_TAG + f"('Kolonne Nord','{MI}')"), [])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/planning", bereit(4))
    await tab.warte_auf_ruhe()

    # --- Kai am Mittwoch dazu: keine Lücke mehr ---
    await _dialog_mit_tagen(tab, seed)
    await tab.js(f"document.querySelector('[data-tage-person=\"{seed['kai']}\"] [data-tag=\"{MI}\"]').click()")
    await tab.warte_auf_ruhe()
    p.pruefe("Dialog: Kai danach „nur 11., 12., 13.11.“", await tab.js(DIALOG_TAGE + ".find(x=>x[0]==='Kai Kolb')[1]"), "nur 11., 12., 13.11.")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('edSpeichern').click()", "#planner")
    await tab.warten(bereit(4) + "&&!document.getElementById('einsatzDialog').open", 15)
    p.pruefe("Kolonnen: Nord ein Balken über Mittwoch", await tab.js(UEBER_TAG + f"('Kolonne Nord','{MI}')"), ["Am Wasserturm 4 · Tom, Mia, Ole, Kai"])

    # --- Leer: Garage behalten, Ortgang löschen ---
    await tab.js(f"openEdit({seed['garage']})")
    await tab.warten("document.getElementById('einsatzDialog').open")
    await tab.warte_auf_ruhe()
    await tab.js(f"document.querySelector('#edPersonen input[data-id=\"{seed['kai']}\"]').click()")
    await tab.warte_auf_ruhe()
    p.pruefe("Leer: der Dialog sagt es vorher", await tab.js("document.getElementById('edMeldung').textContent"),
             "Der Einsatz hat dann niemanden mehr – beim Speichern: löschen oder behalten.")
    await tab.js("document.getElementById('edSpeichern').click()")
    p.pruefe("Leer: Rückfrage beim Speichern", await tab.warten("document.getElementById('leerDialog').open&&document.getElementById('ldTitel').textContent==="
                                                                "'Der Einsatz hat dann niemanden mehr.'", 10), True)
    await tab.bild("tage_leer_rueckfrage")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('leerBehalten').click()", "#planner")
    await tab.warten(bereit(4) + "&&!document.getElementById('leerDialog').open&&!document.getElementById('einsatzDialog').open", 15)
    # keine Warnung mehr (Kai ist nicht mehr doppelt); seit 1.9.266 auch kein Hinweis: „niemand“ meldet keine Kapazität (bis 1.9.265 „1 Hinweis“, capacity)
    p.pruefe("Leer: Behalten -> „niemand“, keine Warnung, kein Hinweis", [await tab.js(BALKEN_JE_ZEILE + "('Ohne Kolonne')"),
             await tab.js("document.getElementById('filterText').textContent"),
             await tab.js("board.slots.find(s=>s.project_name==='Garage Lindenweg 7').conflicts.map(c=>c.type)")],
             [[["Sturmschaden Gartenstraße 2 · Lia, Ole", "fest"], ["Ortgang Lindenweg 9 · Tom, Mia", "fest"], ["Garage Lindenweg 7 · niemand", "vorlaeufig"]],
              "Keine Warnungen", []])
    await tab.js(f"openEdit({seed['ortgang']})")
    await tab.warten("document.getElementById('einsatzDialog').open")
    await tab.warte_auf_ruhe()
    for wer in ("tom", "mia"):
        await tab.js(f"document.querySelector('#edPersonen input[data-id=\"{seed[wer]}\"]').click()")
        await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('edSpeichern').click()")
    await tab.warten("document.getElementById('leerDialog').open", 10)
    await tab.warte_auf_neu_geladene_liste("document.getElementById('leerLoeschen').click()", "#planner")
    await tab.warten(bereit(3), 15)
    p.pruefe("Leer: Löschen -> Ortgang weg", await tab.js("board.slots.map(s=>s.project_name).sort()"),
             ["Am Wasserturm 4", "Garage Lindenweg 7", "Sturmschaden Gartenstraße 2"])
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-11 10:00"))
