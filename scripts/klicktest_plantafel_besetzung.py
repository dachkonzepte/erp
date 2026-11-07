"""Klicktest: die Plantafel auf dem neuen Modell bleibt bedienbar (1.9.237, Stufe 6, R3a, Punkt 6) -- Besetzung, Geräte, Status je Einsatz.

Stehende Uhr 14.10.2026 10:00. Befüllt: Kolonne Nord (Tom, Mia, Pritsche), Kolonne Süd (Kai, Kran 30 m mit UVV fällig am 20.10.2026), zwei Aufträge.

    Neu           „+ Einsatz planen“ mit Nord, 19.–21.10. -> gespeichert ohne Rückfrage; Balken in der Zeile Nord; „Mitarbeiter“: bei Tom und Mia,
                  nicht bei Kai; „Fahrzeuge / Maschinen“: bei der Pritsche
    Dialog        „Einsatz bearbeiten“ nennt Besetzung und Geräte, Status nur „vorläufig“ und „fest“ (vorläufig gewählt), Kolonne mit „ohne Kolonne“
    Kolonne       auf Süd -> Rückfrage mit „Prüffrist abgelaufen: Kran 30 m · UVV fällig am 20.10.2026“; „Trotzdem planen“ -> Kai und der Kran
    ohne Kolonne  „ohne Kolonne – die Personen bleiben“ -> Rückfrage (der Kran), „Trotzdem planen“ -> Zeile „Ohne Kolonne“ mit dem Balken, Kai bleibt
    Ziehen        aus „Ohne Kolonne“ in die Zeile Nord -> Tom, Mia und die Pritsche
    Status        „fest“ gespeichert
    keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_plantafel_besetzung.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

HEUTE = "2026-10-14"
UHR_MS = int(datetime(2026, 10, 14, 10, 0, tzinfo=ZoneInfo("Europe/Berlin")).timestamp() * 1000)


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.models import (AppUser, Customer, Employee, OperationalAsset, OperationalAssetInspection, OperationalResource, Project, Quote, QuoteItem, Team,
                            TeamEmployee, TeamResource)
    from app.orders import create_order_from_quote, load_order
    from app.project_pipeline_columns import default_pipeline_column_id

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Plan", last_name="Plan", street="Dachweg 1", postal_code="52531", city="Uebach")
    leute = [Employee(employee_number=f"M-{i}", first_name=n, last_name="Test", employee_group="gewerblich", weekly_hours=Decimal("40"), active=True)
             for i, n in enumerate(("Tom", "Mia", "Kai"), 1)]
    pritsche = OperationalResource(resource_number="F-1", resource_type="Fahrzeug", name="Pritsche", identifier="HS-DK 204", active=True)
    kran = OperationalResource(resource_number="K-1", resource_type="Maschine", name="Kran 30 m", identifier="K1", active=True)
    db.add_all([anna, kunde, *leute, pritsche, kran]); db.flush()
    asset = OperationalAsset(resource_id=kran.id)
    db.add(asset); db.flush()
    db.add(OperationalAssetInspection(asset_id=asset.id, inspection_type="UVV", next_due_date=date(2026, 10, 20)))

    def kolonne(name, personen, geraet):
        team = Team(name=name, active=True)
        db.add(team); db.flush()
        for person in personen:
            db.add(TeamEmployee(team_id=team.id, employee_id=person.id))
        db.add(TeamResource(team_id=team.id, resource_id=geraet.id))
        db.flush()
        return team

    def auftrag(nummer):
        projekt = Project(project_number=f"P-{nummer}", name=f"Dach {nummer}", customer_id=kunde.id, status="angebot",
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        quote = Quote(quote_number=f"A-{nummer}", project_id=projekt.id, title="Dachsanierung", vat_rate=Decimal("19"))
        db.add(quote); db.flush()
        db.add(QuoteItem(quote_id=quote.id, position_number="1", short_text="Eindecken", quantity=Decimal("10"), unit="m2", unit_price=Decimal("50")))
        db.commit()
        order = create_order_from_quote(db, quote.id, order_date=date(2026, 9, 1), execution_start=None, execution_end=None,
                                        caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
        return load_order(db, order.id)

    nord, sued = kolonne("Nord", leute[:2], pritsche), kolonne("Süd", leute[2:], kran)
    a = auftrag("A")
    db.commit()
    return {"a": a.id, "nord": nord.id, "sued": sued.id, "tom": leute[0].id, "mia": leute[1].id, "kai": leute[2].id, "pritsche": pritsche.id,
            "kran": kran.id, "anna": k.cookies(anna)}


BEREIT = "typeof board!=='undefined'&&board&&board.teams&&board.teams.length>0&&typeof orders!=='undefined'"
EINSATZ = "board.slots[0]"


async def _ansicht(tab, name):
    await tab.js(f"setView('{name}')")
    await tab.warten(f"view==='{name}'")


async def _zeilen_mit_balken(tab):
    """Die Beschriftungen der Zeilen, in denen ein Balken steht (die Ansicht, wie sie gezeichnet ist)."""
    return await tab.js("[...document.querySelectorAll('.track')].filter(t=>t.querySelector('.slot')).map(t=>t.closest('.planner-row')"
                        "?.querySelector('.row-label b, .row-label')?.textContent.trim().split('\\n')[0].trim())")


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")
    await tab.browser_uhr_fest(UHR_MS)
    await tab.anmelden(seed["anna"])
    await tab.oeffnen("/planning", BEREIT)
    await tab.warte_auf_neu_geladene_liste("movePeriod(7)", "#planner")
    await tab.warten(BEREIT + "&&board.slots.length===0")

    # --- Neu mit Kolonne Nord ---
    await tab.js(f"void openCreate({seed['a']},null,{seed['nord']})")
    await tab.warten("document.getElementById('einsatzDialog').open")
    await tab.warte_auf_ruhe()
    p.pruefe("Neu: Status vorläufig und fest, vorläufig gewählt", await tab.js(  # seit 1.9.248 Umschalter statt Auswahl
        "[[...document.querySelectorAll('#edStatus button')].map(b=>b.dataset.status),document.querySelector('#edStatus [aria-pressed=true]').dataset.status]"),
        [["vorlaeufig", "fest"], "vorlaeufig"])
    await tab.js("document.getElementById('edVon').value='2026-10-19';document.getElementById('edBis').value='2026-10-21';"
                 "document.getElementById('edStunden').value='1'")
    await tab.warte_auf_neu_geladene_liste("void saveNew()", "#planner")
    await tab.warten(BEREIT + "&&board.slots.length===1&&!document.getElementById('einsatzDialog').open")
    p.pruefe("Neu: ohne Rückfrage gespeichert", await tab.js("document.getElementById('konfliktDialog').open"), False)
    p.pruefe("Neu: Besetzung und Geräte der Kolonne", await tab.js(
        f"[{EINSATZ}.team_id,{EINSATZ}.employees.map(e=>e.name),{EINSATZ}.resources.map(r=>[r.name,r.tage]),{EINSATZ}.status]"),
        [seed["nord"], ["Tom Test", "Mia Test"], [["Pritsche", None]], "vorlaeufig"])
    p.pruefe("Kolonnen: Balken in der Zeile Nord", await tab.js(
        f"!!document.querySelector('.track[data-team-id=\"{seed['nord']}\"] .slot')&&!document.querySelector('.track[data-team-id=\"{seed['sued']}\"] .slot')"),
        True)
    await _ansicht(tab, "employees")
    p.pruefe("Mitarbeiter: bei Tom und Mia, nicht bei Kai", await tab.js(
        "board.employees.filter(e=>slotsForRow(e).length).map(e=>e.name)"), ["Mia Test", "Tom Test"])
    await _ansicht(tab, "resources")
    p.pruefe("Fahrzeuge: bei der Pritsche", await tab.js("board.resources.filter(r=>slotsForRow(r).length).map(r=>r.name)"), ["Pritsche"])
    await _ansicht(tab, "teams")

    # --- Dialog ---
    await tab.js(f"openEdit({EINSATZ}.id)")
    await tab.warte_auf_ruhe()
    p.pruefe("Dialog: Besetzung und Geräte", await tab.js(  # seit 1.9.248 als Listen mit Häkchen (bis 1.9.247 ein Satz)
        "[[...document.querySelectorAll('#edPersonen .wahl')].filter(l=>l.querySelector('input').checked).map(l=>l.querySelector('.wahl-name').textContent),"
        "[...document.querySelectorAll('#edGeraete .wahl')].filter(l=>l.querySelector('input').checked).map(l=>l.querySelector('.wahl-name').textContent)]"),
        [["Tom Test", "Mia Test"], ["Pritsche"]])
    p.pruefe("Dialog: Status und Kolonne", await tab.js(
        "[[...document.querySelectorAll('#edStatus button')].map(b=>b.dataset.status),document.querySelector('#edStatus [aria-pressed=true]').dataset.status,"
        "[...document.getElementById('edKolonne').options].map(o=>o.textContent)[0],document.getElementById('edKolonne').value]"),
        [["vorlaeufig", "fest"], "vorlaeufig", "ohne Kolonne – Personen selbst wählen", str(seed["nord"])])
    await tab.bild("dialog_besetzung")

    # --- Kolonne Süd: Prüffrist des Krans ---
    await tab.js(f"document.getElementById('edKolonne').value='{seed['sued']}';void saveEdit()")
    p.pruefe("Süd: Rückfrage", await tab.warten("document.getElementById('edSpeichern').textContent==='Trotzdem planen'"), True)  # seit 1.9.248 im Dialog („Trotzdem planen“), bis 1.9.247 eine eigene Rückfrage
    p.pruefe("Süd: Prüffrist abgelaufen", await tab.js("[...document.querySelectorAll('#edWarnungen > .conflict-row')].map(x=>x.textContent).join('')"),
             "Prüffrist abgelaufen: Kran 30 m · UVV fällig am 20.10.2026 · 21.10.")
    await tab.bild("rueckfrage_prueffrist")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('edSpeichern').click()", "#planner")
    await tab.warten(BEREIT + f"&&{EINSATZ}.team_id==={seed['sued']}")
    p.pruefe("Süd: Kai und der Kran", await tab.js(f"[{EINSATZ}.employees.map(e=>e.name),{EINSATZ}.resources.map(r=>r.name)]"),
             [["Kai Test"], ["Kran 30 m"]])

    # --- ohne Kolonne ---
    await tab.js(f"openEdit({EINSATZ}.id)")
    await tab.js("document.getElementById('edKolonne').value='';void saveEdit()")
    p.pruefe("ohne Kolonne: fragt wie jeder Wechsel der Kolonne (der Kran)", await tab.warten("document.getElementById('edSpeichern').textContent==='Trotzdem planen'"), True)
    await tab.warte_auf_neu_geladene_liste("document.getElementById('edSpeichern').click()", "#planner")
    await tab.warten(BEREIT + f"&&{EINSATZ}.team_id===null")
    p.pruefe("ohne Kolonne: Kai bleibt, der Kran bleibt", await tab.js(f"[{EINSATZ}.employees.map(e=>e.name),{EINSATZ}.resources.map(r=>r.name)]"),
             [["Kai Test"], ["Kran 30 m"]])
    p.pruefe("ohne Kolonne: Zeile mit dem Balken", await tab.js(
        "(()=>{const t=document.querySelector('.track[data-team-id=\"null\"]');return [!!t,!!(t&&t.querySelector('.slot')),"
        "t?t.closest('.planner-row').textContent.includes('Ohne Kolonne')&&t.closest('.planner-row').textContent.includes('Personen einzeln gewählt'):false]})()"),
        [True, True, True])
    await tab.bild("ohne_kolonne")

    # --- Ziehen in die Zeile Nord ---
    await tab.js(f"void verschieben({EINSATZ}.id,{{dataset:{{zeile:'kolonne',id:'{seed['nord']}'}}}},0)")  # seit 1.9.249 (bis dahin dropSlot); echte Eingaben: klicktest_plantafel_bedienen
    await tab.warten(BEREIT + f"&&{EINSATZ}.team_id==={seed['nord']}", 10)
    p.pruefe("Ziehen nach Nord: Tom, Mia und die Pritsche", await tab.js(
        f"[{EINSATZ}.employees.map(e=>e.name),{EINSATZ}.resources.map(r=>r.name),{EINSATZ}.start_date]"),
        [["Tom Test", "Mia Test"], ["Pritsche"], "2026-10-19"])

    # --- Status fest ---
    await tab.js(f"openEdit({EINSATZ}.id)")
    await tab.warte_auf_ruhe()
    await tab.warte_auf_neu_geladene_liste("document.querySelector('#edStatus [data-status=fest]').click();void saveEdit()", "#planner")
    await tab.warten(BEREIT + f"&&{EINSATZ}.status==='fest'", 10)
    p.pruefe("Status fest gespeichert", await tab.js(f"[{EINSATZ}.status,{EINSATZ}.status_label]"), ["fest", "fest"])
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr=f"{HEUTE} 10:00"))
