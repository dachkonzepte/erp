"""Klicktest: die Plantafel kennt den Arbeitszeitkalender (seit 1.9.188, Lohn L1a, Stufe 2, Punkt 3).

Stehende Uhr Mo 14.12.2026 10:00. Befüllt: Kolonne Nord mit Mia (Tarif), Tom (Teilzeit Di–Do) und Ben (Teilzeit Mo–Di, am Donnerstag keine
Sollzeit); Auftrag A eingeplant 21.–24.12.2026 auf Nord; Anna (Admin), Berta (Büro – Auftrag). Seit 1.9.194 dazu Kai (ohne Kolonne) mit einer
Fortbildung am Di 22.12. und einer langen Art („Fortbildung Abdichtungstechnik Flachdach mit Herstellerschulung (Teil 2)“).

    Kolonnen     Woche ab 21.12.: in Nord am Do 24.12. „2 abw.“ (Mia und Tom), die Tage davor ohne; der Einsatz A ist markiert wie an einem
                 betriebsfreien Tag, im Dialog „Freistellung: Heiligabend – Mia Test, Tom Test · 24.12.“ -- Bild; seit 1.9.193 nennt der Satz über
                 der Tafel auch Freistellungen (sie stehen nicht in der Liste „Abwesenheiten“)
    Mitarbeiter  Mia und Tom am 24.12. „Heiligabend – bezahlte Freistellung“, Ben nicht (keine Sollzeit am Donnerstag -- wie bisher); Bild;
                 seit 1.9.194 Kais lange Art am 22.12.: in der Zelle rechts neben der Kapazität, mit „…“ gekürzt (text-overflow), voller Text
                 im Tooltip (title) -- die Absicherung des Nachtrags zu 1.9.188 für lange Arten, bis dahin ohne eigenen Test
    Einplanen    Auftrag B auf Nord 28.–31.12.: gespeichert ohne Rückfrage, Hinweis „Einsatz gespeichert – zur Kenntnis: Freistellung: Silvester
                 – Mia Test, Tom Test · 31.12.“ -- wie am betriebsfreien Tag; Bild
    Büro–Auftrag am Mitarbeiter steht „abwesend“ (wie jede Abwesenheit, Krankheitssichtbarkeit), der Hinweis am Einsatz nennt den Tag

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
# seit 1.9.194: Kais Zelle am 22.12. -- die lange Art liegt rechts neben der Kapazität und ganz in der Zelle, ist gekürzt (scrollWidth über der
# sichtbaren Breite, text-overflow „ellipsis“, eine Zeile) und trägt den vollen Text im Tooltip
GEKUERZT = ("(()=>{const r=[...document.querySelectorAll('.planner-row')].find(x=>x.querySelector('.row-label b')&&x.querySelector('.row-label b').textContent==='Kai Test'),"
            "c=r.querySelector('.day-cell[data-date=\"2026-12-22\"]'),m=c.querySelector('.absence-mark'),k=c.querySelector('.capacity-label'),"
            "a=m.getBoundingClientRect(),b=k.getBoundingClientRect(),z=c.getBoundingClientRect(),s=getComputedStyle(m);"
            "return [b.right<=a.left,a.left>=z.left&&a.right<=z.right&&a.top>=z.top&&a.bottom<=z.bottom,m.scrollWidth>m.clientWidth,"
            "s.textOverflow,s.whiteSpace,m.textContent,m.title]})()")
# seit 1.9.188 (Nachtrag): in Mias Zelle am 24.12. liegen Abwesenheit und Kapazität nebeneinander, die Abwesenheit ist nicht abgeschnitten
UEBERLAPPUNG = ("(()=>{const r=[...document.querySelectorAll('.planner-row')].find(x=>x.querySelector('.row-label b').textContent==='Mia Test'),"
                "c=r.querySelector('.day-cell[data-date=\"2026-12-24\"]'),m=c.querySelector('.absence-mark'),k=c.querySelector('.capacity-label'),"
                "a=m.getBoundingClientRect(),b=k.getBoundingClientRect(),z=c.getBoundingClientRect();"
                "return [b.right<=a.left&&a.left>=z.left&&a.right<=z.right,m.scrollWidth<=m.clientWidth,m.title]})()")


def zelle(zeile: str, tag: str) -> str:
    """Text der Markierung „abw.“ bzw. der Abwesenheit in der Zelle der Zeile (Name in der linken Spalte) am Tag -- leer, wenn keine."""
    return ("(()=>{const r=[...document.querySelectorAll('.planner-row')].find(x=>x.querySelector('.row-label b')&&x.querySelector('.row-label b').textContent==="
            + repr(zeile) + ");if(!r)return 'Zeile fehlt';const c=r.querySelector('.day-cell[data-date=\"" + tag + "\"]');if(!c)return 'Tag fehlt';"
            "const m=c.querySelector('.absence-mark');return m?m.textContent:''})()")


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")
    await tab.browser_uhr_fest(seed["uhr_ms"])
    await tab.anmelden(seed["anna"])
    await tab.oeffnen("/planning", BEREIT)
    await tab.js("movePeriod(7)")
    await tab.warten(BEREIT + "&&iso(periodStart)==='2026-12-21'&&board.slots.length===1")

    # --- Kolonnen ---
    p.pruefe("Nord am 24.12.: 2 abwesend, die Tage davor nicht", [await tab.js(zelle("Nord", t)) for t in ("2026-12-22", "2026-12-23", "2026-12-24")],
             ["", "", "2 abw."])
    p.pruefe("Einsatz A markiert wie am betriebsfreien Tag", await tab.js("document.querySelectorAll('.slot.conflict').length"), 1)
    # seit 1.9.193: die Freistellung steht nicht in der Liste „Abwesenheiten“ (Festlegung 1.9.188 Nr. 5) -- der Satz über der Tafel nennt sie
    p.pruefe("Satz über der Tafel nennt Freistellungen", await tab.js("document.querySelector('#conflictBanner .warning').textContent"),
             "⚠ 1 Planeinsatz mit Konflikten. Berücksichtigt werden Doppelbelegungen, Abwesenheiten, Freistellungen, Feiertage und unzureichende "
             "Stundenkapazität.")
    await tab.bild("1_kolonnen_heiligabend")
    await tab.js(f"openEdit({seed['slot']})")
    await tab.warten("document.getElementById('editDialog').open")
    p.pruefe("Dialog des Einsatzes: Freistellung mit Tag und Namen", await tab.js("[...document.querySelectorAll('#editConflicts .conflict-row')].map(x=>x.textContent)"),
             ["Freistellung: Heiligabend – Mia Test, Tom Test · 24.12."])
    await tab.bild("2_einsatz_freistellung")
    await tab.js("editDialog.close()")

    # --- Mitarbeiter ---
    await tab.js("document.querySelector('.viewtabs button[data-view=employees]').click()")
    await tab.warten("view==='employees'&&!!document.querySelector('.planner-row')")
    p.pruefe("Mitarbeiter am 24.12.: Mia und Tom freigestellt, Ben wie bisher", [await tab.js(zelle(f"{n} Test", "2026-12-24")) for n in ("Mia", "Tom", "Ben")],
             ["Heiligabend", "Heiligabend", ""])
    # 1.9.188 (Nachtrag): sichtbar messen, nicht nur den Text -- bis dahin stand die ganze Freistellung in der 120 px schmalen Zelle über der Kapazität
    p.pruefe("Mitarbeiter am 24.12.: Freistellung und Kapazität überlappen nicht, nichts abgeschnitten, voller Text im Tooltip", await tab.js(UEBERLAPPUNG),
             [True, True, "Heiligabend"])
    p.pruefe("Mia am 23.12. ohne", await tab.js(zelle("Mia Test", "2026-12-23")), "")
    # seit 1.9.194: die Kürzung aus dem Nachtrag zu 1.9.188 mit einer langen Art -- Lage, „…“ und Tooltip
    p.pruefe("Kai am 22.12.: lange Art neben der Kapazität, in der Zelle, mit „…“ gekürzt, voller Text im Tooltip", await tab.js(GEKUERZT),
             [True, True, True, "ellipsis", "nowrap", LANGE_ART, LANGE_ART])
    await tab.bild("3_mitarbeiter_heiligabend")
    await tab.js("document.querySelector('.viewtabs button[data-view=teams]').click()")
    await tab.warten("view==='teams'")

    # --- Einplanen über Silvester: Hinweis, keine Rückfrage ---
    await tab.js(f"void openCreate({seed['b']},null,{seed['nord']})")
    await tab.warten("document.getElementById('createDialog').open")
    await tab.js("document.getElementById('newStart').value='2026-12-28';document.getElementById('newEnd').value='2026-12-31';"
                 "document.getElementById('newPlannedHours').value='1'")
    await tab.js("void saveNew()")
    p.pruefe("Silvester: gespeichert ohne Rückfrage", await tab.warten(
        "!document.getElementById('createDialog').open&&!document.getElementById('konfliktDialog').open&&board.slots.length===2", 15), True)
    p.pruefe("Silvester: Hinweis über der Tafel", await tab.js("document.getElementById('einsatzHinweis').textContent"),
             "Einsatz gespeichert – zur Kenntnis:Freistellung: Silvester – Mia Test, Tom Test · 31.12.")
    await tab.bild("4_hinweis_silvester")
    p.pruefe("Anna: keine JS-Fehler", tab.fehler, [])

    # --- Büro – Auftrag ---
    await tab.anmelden(seed["berta"])
    await tab.oeffnen("/planning", BEREIT)
    await tab.js("movePeriod(7)")
    await tab.warten(BEREIT + "&&iso(periodStart)==='2026-12-21'&&board.slots.length===2")
    await tab.js("document.querySelector('.viewtabs button[data-view=employees]').click()")
    await tab.warten("view==='employees'&&!!document.querySelector('.planner-row')")
    p.pruefe("Berta: am Mitarbeiter „abwesend“", await tab.js(zelle("Mia Test", "2026-12-24")), "abwesend")
    p.pruefe("Berta: der Hinweis am Einsatz nennt den Tag", await tab.js(
        f"board.slots.find(s=>s.id==={seed['slot']}).conflicts.map(c=>[c.type,c.label])"), [["kalendertag", "Heiligabend – Mia Test, Tom Test"]])
    p.pruefe("Berta: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Plantafel kennt den Arbeitszeitkalender", uhr="2026-12-14 10:00"))
