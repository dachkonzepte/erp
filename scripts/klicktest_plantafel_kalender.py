"""Klicktest: die Plantafel kennt den Arbeitszeitkalender (seit 1.9.188, Lohn L1a, Stufe 2, Punkt 3).

Stehende Uhr Mo 14.12.2026 10:00. Befüllt: Kolonne Nord mit Mia (Tarif), Tom (Teilzeit Di–Do) und Ben (Teilzeit Mo–Di, am Donnerstag keine
Sollzeit); Auftrag A eingeplant 21.–24.12.2026 auf Nord; Anna (Admin), Berta (Büro – Auftrag). Seit 1.9.194 dazu Kai (ohne Kolonne) mit einer
Fortbildung am Di 22.12. und einer langen Art („Fortbildung Abdichtungstechnik Flachdach mit Herstellerschulung (Teil 2)“).

    Kolonnen     Woche ab 21.12.: in der Zeile Nord „Mia Heiligabend 24.12. · Tom Heiligabend 24.12.“ (seit 1.9.247; bis 1.9.246 „2 abw.“ in der
                 Zelle); der Einsatz A trägt den Punkt eines Hinweises, nicht rot; im Dialog „Freistellung: Heiligabend – Mia Test, Tom Test · 24.12.“ --
                 Bild; seit 1.9.193 nennt der Satz zu Warnungen und Hinweisen auch Freistellungen (seit 1.9.247 am Knopf der Leiste)
    Kapazität    seit 1.9.247 keine Kapazität je Zelle mehr (Vorgabe Stufe 6, R4: sie steht am Einsatz); 1.9.211–1.9.246 prüfte der Klicktest sie hier
    Personen     Mia und Tom am 24.12. ein Balken „Heiligabend“ (abwesend, schraffiert), genau in der Spalte des Tags, Ben keiner (keine Sollzeit am
                 Donnerstag); Bild; Kais lange Art am 22.12. im Balken mit „…“ gekürzt, voller Text im title (seit 1.9.194, bis 1.9.246 in der Zelle)
    Einplanen    Auftrag B auf Nord 28.–31.12.: gespeichert ohne Rückfrage, Hinweis „Einsatz gespeichert – zur Kenntnis: Freistellung: Silvester
                 – Mia Test, Tom Test · 31.12.“ -- wie am betriebsfreien Tag; Bild
    Büro–Auftrag der Balken der Abwesenheit sagt nur „abwesend“ (wie jede Abwesenheit, Krankheitssichtbarkeit), der Hinweis am Einsatz nennt den Tag

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_plantafel_kalender.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.absence_requests import eintragen
    from app.models import AppUser, Customer, Employee, Project, Quote, QuoteItem, Team, TeamEmployee
    from app.orders import create_order_from_quote, load_order
    from app.planning import create_slot
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.sollzeit import zeile_anlegen

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    berta = AppUser(username="berta", display_name="Berta Büro", role="buero_auftrag", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Plan", last_name="Plan", street="Dachweg 1", postal_code="52531", city="Uebach")
    leute = {n: Employee(employee_number=nr, first_name=n, last_name="Test", employee_group="gewerblich", weekly_hours=Decimal("40"), active=True)
             for n, nr in (("Mia", "M-1"), ("Tom", "M-2"), ("Ben", "M-3"))}
    db.add_all([anna, berta, kunde, *leute.values()]); db.flush()
    zeile_anlegen(db, leute["Tom"].id, date(2026, 12, 1), {"dienstag": Decimal("3"), "mittwoch": Decimal("3"), "donnerstag": Decimal("3")})
    zeile_anlegen(db, leute["Ben"].id, date(2026, 12, 1), {"montag": Decimal("8"), "dienstag": Decimal("8")})
    nord = Team(name="Nord", active=True)
    db.add(nord); db.flush()
    db.add_all([TeamEmployee(team_id=nord.id, employee_id=e.id) for e in leute.values()]); db.flush()
    # seit 1.9.194: eine Abwesenheit mit langer Art bei Kai (in keiner Kolonne -- Einsatz A und die Kolonne Nord bleiben unberührt)
    kai = Employee(employee_number="M-4", first_name="Kai", last_name="Test", employee_group="gewerblich", weekly_hours=Decimal("40"), active=True)
    db.add(kai); db.flush()
    eintragen(db, gleich_genehmigt=True, employee_id=kai.id, absence_type=LANGE_ART, absence_category="fortbildung", start_date=date(2026, 12, 22),
              end_date=date(2026, 12, 22), requested_by_user_id=anna.id)

    def auftrag(nummer):
        projekt = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=kunde.id, status="angebot",
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-{nummer}", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2", unit_price=Decimal("50")))
        db.commit()
        order = create_order_from_quote(db, quote.id, order_date=date(2026, 11, 2), execution_start=None, execution_end=None,
                                        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
        return load_order(db, order.id)

    a, b = auftrag("A"), auftrag("B")
    slot = create_slot(db, order_id=a.id, team_id=nord.id, start_date=date(2026, 12, 21), end_date=date(2026, 12, 24))
    db.commit()
    return {"b": b.id, "nord": nord.id, "slot": slot.id, **{n: e.id for n, e in leute.items()}, "anna": k.cookies(anna), "berta": k.cookies(berta),
            "uhr_ms": k.uhr_ms()}


BEREIT = "typeof board!=='undefined'&&board&&board.teams&&board.teams.length>0&&typeof orders!=='undefined'"
LANGE_ART = "Fortbildung Abdichtungstechnik Flachdach mit Herstellerschulung (Teil 2)"


def _zeile(name: str) -> str:
    return ("[...document.querySelectorAll('#planner .planner-row')].find(x=>x.querySelector('.row-label b')&&x.querySelector('.row-label b').textContent==="
            + repr(name) + ")")


def unter(name: str) -> str:
    """Seit 1.9.247: die Zeilen unter dem Namen (Mitglieder, Abwesenheiten im Bild)."""
    return "(()=>{const r=" + _zeile(name) + ";return r?[...r.querySelectorAll('.row-label .unter')].map(u=>u.textContent.trim()):'Zeile fehlt'})()"


def balken(name: str, klasse: str) -> str:
    """Seit 1.9.247: die Texte der Balken mit der Klasse in der Zeile (z. B. „abwesend“ in „Personen“)."""
    return ("(()=>{const r=" + _zeile(name) + ";return r?[...r.querySelectorAll('.slot." + klasse + "')].map(s=>s.querySelector('.slot-text').textContent.trim())"
            ":'Zeile fehlt'})()")


# seit 1.9.247: Mias Balken „Heiligabend“ liegt in der Spalte des 24.12. (mit 3 px Spiel) und sein Text passt
LAGE_24 = ("(()=>{const r=" + _zeile("Mia Test") + ",s=r.querySelector('.slot.abwesend'),c=r.querySelector('.day-cell[data-date=\"2026-12-24\"]'),"
           "a=s.getBoundingClientRect(),z=c.getBoundingClientRect(),t=s.querySelector('.slot-text');return [a.left>=z.left-3&&a.right<=z.right+3,"
           "t.scrollWidth<=t.clientWidth+1||s.title.startsWith('Heiligabend'),s.title.includes('Heiligabend')]})()")
# seit 1.9.194 (seit 1.9.247 im Balken statt in der Zelle): Kais lange Art ist gekürzt, eine Zeile mit „…“, der volle Text im title
GEKUERZT = ("(()=>{const r=" + _zeile("Kai Test") + ",s=r.querySelector('.slot.abwesend'),t=s.querySelector('.slot-text'),st=getComputedStyle(t);"
            "return [t.scrollWidth>t.clientWidth,st.textOverflow,getComputedStyle(s).whiteSpace,s.title.startsWith(" + repr(LANGE_ART) + ")]})()")


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")
    await tab.browser_uhr_fest(seed["uhr_ms"])
    await tab.anmelden(seed["anna"])
    await tab.oeffnen("/planning", BEREIT)
    # seit 1.9.211: warten, bis die Tafel der neuen Woche gezeichnet ist -- „board.slots.length===1“ galt schon für die alte (zwei Wochen ab
    # 14.12. mit demselben Einsatz); Prüfungen und Bild liefen davor (im Bild: Woche ab 14.12., „Lädt …“), die Werte waren nur zufällig gleich
    await tab.warte_auf_neu_geladene_liste("movePeriod(7)", "#planner")
    await tab.warten(BEREIT + "&&iso(periodStart)==='2026-12-21'&&board.start_date==='2026-12-21'&&board.slots.length===1")

    # --- Kolonnen ---
    p.pruefe("Nord: Mia und Tom am 24.12. freigestellt (Zeile der Kolonne)", await tab.js(unter("Nord")),
             ["Mia, Tom, Ben", "Mia Heiligabend 24.12. · Mia Silvester 31.12. · Tom Heiligabend 24.12. · Tom Silvester 31.12."])  # zwei Wochen im Bild
    p.pruefe("Einsatz A mit Hinweis wie am betriebsfreien Tag, nicht rot", await tab.js(
        "(()=>{const s=document.querySelector('.track[data-team-id] .slot');return [!!s.querySelector('.hinweis-punkt'),s.classList.contains('conflict')]})()"),
        [True, False])
    # seit 1.9.193: die Freistellung steht nicht in der Liste „Abwesenheiten“ (Festlegung 1.9.188 Nr. 5) -- der Satz nennt sie (seit 1.9.247 am Knopf)
    p.pruefe("Satz zu Warnungen und Hinweisen nennt Freistellungen", "Freistellungen" in await tab.js("document.getElementById('filterKnopf').title"), True)
    await tab.bild("1_kolonnen_heiligabend")
    await tab.js(f"openEdit({seed['slot']})")
    await tab.warten("document.getElementById('einsatzDialog').open")
    await tab.warten("!!pruefung")
    await tab.warte_auf_ruhe()
    p.pruefe("Dialog des Einsatzes: Freistellung mit Tag und Namen", await tab.js("[...document.querySelectorAll('#edWarnungen .conflict-row')].map(x=>x.textContent)"),
             ["Freistellung: Heiligabend – Mia Test, Tom Test · 24.12."])
    await tab.bild("2_einsatz_freistellung")
    await tab.js("einsatzDialog.close()")

    # --- Personen ---
    await tab.js("document.querySelector('.viewtabs button[data-view=employees]').click()")
    await tab.warten("view==='employees'&&!!document.querySelector('.planner-row')")
    p.pruefe("Personen am 24.12.: Mia und Tom freigestellt, Ben nicht", [await tab.js(balken(f"{n} Test", "abwesend")) for n in ("Mia", "Tom", "Ben")],
             [["Heiligabend", "Silvester"], ["Heiligabend", "Silvester"], []])
    p.pruefe("Personen: der Balken steht in der Spalte des 24.12., der Text passt oder steht im title", await tab.js(LAGE_24), [True, True, True])
    p.pruefe("Kai am 22.12.: lange Art im Balken mit „…“ gekürzt, voller Text im title", await tab.js(GEKUERZT), [True, "ellipsis", "nowrap", True])
    await tab.bild("3_personen_heiligabend")
    await tab.js("document.querySelector('.viewtabs button[data-view=teams]').click()")
    await tab.warten("view==='teams'")

    # --- Einplanen über Silvester: Hinweis, keine Rückfrage ---
    await tab.js(f"void openCreate({seed['b']},null,{seed['nord']})")
    await tab.warten("document.getElementById('einsatzDialog').open")
    await tab.js("document.getElementById('edVon').value='2026-12-28';document.getElementById('edBis').value='2026-12-31';"
                 "document.getElementById('edStunden').value='1'")
    await tab.js("void saveNew()")
    p.pruefe("Silvester: gespeichert ohne Rückfrage", await tab.warten(
        "!document.getElementById('einsatzDialog').open&&!document.getElementById('konfliktDialog').open&&board.slots.length===2", 15), True)
    p.pruefe("Silvester: Hinweis über der Tafel", await tab.js("document.getElementById('einsatzHinweis').textContent"),
             "Einsatz gespeichert – zur Kenntnis:Freistellung: Silvester – Mia Test, Tom Test · 31.12.")
    await tab.bild("4_hinweis_silvester")
    p.pruefe("Anna: keine JS-Fehler", tab.fehler, [])

    # --- Büro – Auftrag ---
    await tab.anmelden(seed["berta"])
    await tab.oeffnen("/planning", BEREIT)
    await tab.warte_auf_neu_geladene_liste("movePeriod(7)", "#planner")  # seit 1.9.211 wie oben
    await tab.warten(BEREIT + "&&iso(periodStart)==='2026-12-21'&&board.start_date==='2026-12-21'&&board.slots.length===2")
    await tab.js("document.querySelector('.viewtabs button[data-view=employees]').click()")
    await tab.warten("view==='employees'&&!!document.querySelector('.planner-row')")
    p.pruefe("Berta: am Mitarbeiter „abwesend“", await tab.js(balken("Mia Test", "abwesend")), ["abwesend", "abwesend"])  # Heiligabend und Silvester
    p.pruefe("Berta: der Hinweis am Einsatz nennt den Tag", await tab.js(
        f"board.slots.find(s=>s.id==={seed['slot']}).conflicts.map(c=>[c.type,c.label])"), [["kalendertag", "Heiligabend – Mia Test, Tom Test"]])
    p.pruefe("Berta: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Plantafel kennt den Arbeitszeitkalender", uhr="2026-12-14 10:00"))
