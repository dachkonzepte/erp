"""Klicktest: Bedenkenanzeige erfassen und Hinweis "Offene Bedenken" (1.8.43, Stufe 2b, Runde 2b-4 Teil 1).

Die Instanz entsteht per create_all() ohne Alembic -- die Startvorlage kommt im Befüllen über die Funktion
der Migration 0816ece7159b, veröffentlicht wie vom Büro. Die Monteurin hat heute einen Einsatz am Auftrag.

    Monteurin (412 px, hell)  /mobil ohne Hinweis; am Auftrag "Bedenkenanzeige" starten; drei Abschnitte;
                              Anzeige und Entscheidung "füllt das Büro aus"; Meldung ausfüllen und
                              unterschreiben; /mobil zeigt unter dem Einsatz "Offene Bedenken …" mit Link;
                              kein waagrechter Scrollbalken.
    Büro (1400 px, dunkel)    Auftragsseite mit dem Hinweis oben (Text, Link, lesbar); Folge "Bedenkenanzeige
                              versenden"; Anzeige ausfüllen (zwei Bedenken gewählt, "Entscheidung erbeten
                              bis") und unterschreiben -- der Hinweis nennt das Datum; Entscheidung festhalten
                              und unterschreiben -- Hinweis auf dem Auftrag weg.
    Monteurin (412 px, dunkel) /mobil ohne Hinweis.

`confirm()` wird auf jeder Seite automatisch bestätigt und mitgeschrieben. Feste Uhr 10:00 (cdp_klicktest.py).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_bedenkenanzeige.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID
beenden): siehe scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_behinderungsanzeige import _eingeben, _feld_ids, _migration  # noqa: E402
from klicktest_checkliste_unterschrift import CONFIRM, _unterschreiben  # noqa: E402

K = "bedenkenanzeige."
HINWEIS = "Offene Bedenken – vor Ausführung der betroffenen Leistung Entscheidung des Auftraggebers abwarten oder mit dem Büro klären."


def befuellen(db, k):
    from decimal import Decimal

    from sqlalchemy import select

    from app.berlin_time import berlin_today
    from app.checklist_templates import publish_draft
    from app.models import (
        AppUser, ChecklistTemplate, Customer, Employee, Order, PlanningSlot, Project, Property, Team,
        WorkPreparationEmployee, WorkPreparationTeamAssignment,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.work_preparation import ensure_preparation

    ma = {key: Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group="gewerblich", active=True,
                        hourly_wage=Decimal("22.00"))
          for key, nr, vor, nach in (("mia", "E-1", "Mia", "Monteurin"), ("olga", "E-2", "Olga", "Office"))}
    db.add_all(ma.values()); db.flush()
    benutzer = {
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=ma["mia"].id, password_hash=k.passwort()),
        "buero": AppUser(username="olga", display_name="Olga Office", role="buero_auftrag", employee_id=ma["olga"].id, password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Klicktest Kunde", last_name="Klicktest Kunde")
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Nord", street="Weg 1", postal_code="12345", city="Stadt")
    db.add(objekt); db.flush()
    projekt = Project(project_number="P-KT-1", name="Dach Nord", customer_id=kunde.id, property_id=objekt.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-KT-1", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-1",
                    title="Dach Nord", customer_name="Klicktest Kunde", property_name="Halle Nord",
                    property_address="Weg 1\n12345 Stadt", caseworker_employee_id=ma["olga"].id)
    db.add(auftrag); db.commit()
    prep = ensure_preparation(db, auftrag.id)
    db.add(WorkPreparationEmployee(preparation_id=prep.id, employee_id=ma["mia"].id))
    team = Team(name="Kolonne Nord", active=True)
    db.add(team); db.flush()
    zuweisung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
    db.add(zuweisung); db.flush()
    db.add(PlanningSlot(preparation_id=prep.id, team_assignment_id=zuweisung.id, start_date=berlin_today(),
                        end_date=berlin_today()))
    db.commit()

    _migration("bedenkenanzeige_startvorlage").insert_concern_template(db.connection())
    db.commit()
    vorlage = db.scalar(select(ChecklistTemplate.id).where(ChecklistTemplate.label == "Bedenkenanzeige"))
    publish_draft(db, vorlage)
    return {"auftrag": auftrag.id, "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


async def _mobil(tab, p, wer: str, theme: str):
    bereit = "document.querySelector('#assignmentsList .assign-card')"
    await tab.oeffnen("/mobil", bereit)
    await tab.js(f"localStorage.setItem('erp_theme','{theme}')")
    await tab.oeffnen("/mobil", bereit)
    p.pruefe(f"{wer}: /mobil {theme}", await tab.js("document.documentElement.dataset.theme"), theme)


async def pruefen(tab, seed, p):
    import asyncio

    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=CONFIRM)
    auftrag = seed["auftrag"]

    # --- Monteurin: /mobil ohne Hinweis, starten, Meldung -----------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await _mobil(tab, p, "Monteurin", "light")
    p.pruefe("Monteurin: heutiger Einsatz, noch kein Hinweis", await tab.js(
        "[document.querySelectorAll('#assignmentsList .assign-card').length, document.querySelectorAll('.concern-alert').length]"),
        [1, 0])
    start_bereit = "document.querySelector('#checklistSection .cl-start-buttons button')"
    await tab.oeffnen(f"/checklisten/auftrag/{auftrag}", start_bereit)
    await tab.js("[...document.querySelectorAll('#checklistSection .cl-start-buttons button')].find(b=>b.textContent==='Bedenkenanzeige').click()")
    await tab.warten("/^\\/checklisten\\/\\d+$/.test(location.pathname) && document.querySelector('#clMain .q')")
    cid = await tab.js("checklistId")
    f = await _feld_ids(tab)
    p.pruefe("Abschnitte", await tab.js("[...document.querySelectorAll('.group-title')].map(e=>e.textContent)"),
             ["Meldung", "Anzeige", "Entscheidung"])
    p.pruefe("Monteurin: Anzeige und Entscheidung 'füllt das Büro aus'", await tab.js(
        "[...document.querySelectorAll('.office-tag')].map(e=>e.closest('.q').id)"),
        [f"q_{f[K + key]}" for key in ("bedenken_gegen", "begruendung", "moegliche_folgen", "vorschlag_abhilfe",
                                       "entscheidung_bis", "unterschrift_buero", "eingegangen_am", "entscheidung",
                                       "antwort_beleg", "notiz", "unterschrift_entscheidung")])
    await _eingeben(tab, f[K + "bekannt_seit"], "2026-10-02T07:45", "change")
    await _eingeben(tab, f[K + "beschreibung"], "Gelieferte Dämmplatten sind durchnässt.")
    await _unterschreiben(tab, f[K + "unterschrift_meldung"], "Mia Monteurin")
    await tab.warten(f"document.querySelector('#q_{f[K + 'unterschrift_meldung']} .sig')")
    p.pruefe("Monteurin: Meldung unterschrieben", await tab.js(
        f"!!document.querySelector('#q_{f[K + 'beschreibung']} .value-ro')"), True)

    await _mobil(tab, p, "Monteurin", "light")
    await tab.warten("document.querySelector('.concern-alert')")
    p.pruefe("Monteurin: Hinweis unter dem Einsatz", await tab.js(
        "(()=>{const a=document.querySelector('.concern-alert');return [a.previousElementSibling.classList.contains('assign-card'),"
        "a.childNodes[0].textContent, a.querySelector('a').getAttribute('href')]})()"),
        [True, HINWEIS, f"/checklisten/{cid}"])
    p.pruefe("Monteurin: Hinweis deutlich (Rahmen und Text in Warnfarbe)", await tab.js(
        "(()=>{const s=getComputedStyle(document.querySelector('.concern-alert'));return s.borderTopColor===s.color||s.borderLeftColor===s.color})()"),
        True)
    p.pruefe("Monteurin: kein waagrechter Scrollbalken", await tab.js("document.documentElement.scrollWidth<=window.innerWidth"), True)
    await tab.bild("1_monteurin_mobil_hinweis")
    p.pruefe("Monteurin: keine JS-Fehler", tab.fehler, [])

    # --- Büro: Auftragsseite, Anzeige, Entscheidung ----------------------------------------------
    await tab.anmelden(seed["cookies"]["buero"])
    await tab.fenster(1400, 1000)
    hinweis = "!document.getElementById('concernAlert').hidden"
    await tab.oeffnen(f"/orders/{auftrag}", hinweis)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/orders/{auftrag}", hinweis)
    p.pruefe("Büro: Dunkelmodus", await tab.js("document.documentElement.dataset.theme"), "dark")
    p.pruefe("Büro: Hinweis auf dem Auftrag mit Link", await tab.js(
        "[document.getElementById('concernAlert').childNodes[0].textContent, document.querySelector('#concernAlert a').getAttribute('href'),"
        "document.querySelector('#concernAlert a').textContent]"),
        [HINWEIS, f"/checklisten/{cid}", f"Bedenkenanzeige Nr. {cid} →"])
    farben = await tab.js("(()=>{const s=getComputedStyle(document.getElementById('concernAlert'));return [s.color,s.backgroundColor]})()")
    p.pruefe("Büro: Hinweis lesbar im Dunkelmodus (Text und Fläche verschieden)", farben[0] != farben[1], True)
    await tab.bild("2_buero_auftrag_hinweis_dunkel")

    bereit = "document.querySelector('#followUpsCard .rule-row')"
    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    folge = await tab.js("document.querySelector('#followUpsCard .rule-row').textContent")
    p.pruefe("Büro: Folge 'Bedenkenanzeige versenden' erledigt", ["Bedenkenanzeige versenden" in folge, "erledigt" in folge],
             [True, True])
    tiles = f"#q_{f[K + 'bedenken_gegen']} .tile"
    for label in ("vom Auftraggeber gelieferte Stoffe oder Bauteile", "vorgesehene Art der Ausführung"):
        await tab.js(f"[...document.querySelectorAll('{tiles}')].find(b=>b.textContent==={label!r}).click()")
        await tab.warten(f"[...document.querySelectorAll('{tiles}')].find(b=>b.textContent==={label!r}).classList.contains('on')")
    await tab.warten(f"document.getElementById('st_{f[K + 'bedenken_gegen']}')?.textContent==='Gespeichert'")
    p.pruefe("Büro: zwei Bedenken gewählt", await tab.js(
        f"[...document.querySelectorAll('{tiles}.on')].map(b=>b.textContent)"),
        ["vorgesehene Art der Ausführung", "vom Auftraggeber gelieferte Stoffe oder Bauteile"])
    p.pruefe("Büro: kein Optionstext ragt aus seiner Kachel", await tab.js(
        "[...document.querySelectorAll('.tile')].filter(b=>b.scrollWidth>b.clientWidth).map(b=>b.textContent)"), [])
    await _eingeben(tab, f[K + "begruendung"], "Durchfeuchtete Dämmung verliert ihre Wirkung.")
    await _eingeben(tab, f[K + "moegliche_folgen"], "Tauwasser, Schimmel, Mängelansprüche.")
    await _eingeben(tab, f[K + "entscheidung_bis"], "2026-10-09", "change")
    await _unterschreiben(tab, f[K + "unterschrift_buero"], "Olga Office")
    await tab.warten(f"document.querySelector('#q_{f[K + 'unterschrift_buero']} .sig')")
    await tab.bild("3_buero_anzeige_unterschrieben")

    await tab.oeffnen(f"/orders/{auftrag}", hinweis)
    p.pruefe("Büro: Hinweis nennt 'Entscheidung erbeten bis'", await tab.js(
        "document.querySelector('#concernAlert a').textContent"),
        f"Bedenkenanzeige Nr. {cid} – Entscheidung erbeten bis 9.10.2026 →")

    await tab.oeffnen(f"/checklisten/{cid}", bereit)
    tiles = f"#q_{f[K + 'entscheidung']} .tile"
    await tab.js(f"[...document.querySelectorAll('{tiles}')].find(b=>b.textContent==='Ausführung trotz Bedenken angeordnet').click()")
    await tab.warten(f"document.getElementById('st_{f[K + 'entscheidung']}')?.textContent==='Gespeichert'")
    await _eingeben(tab, f[K + "eingegangen_am"], "2026-10-05", "change")
    await _eingeben(tab, f[K + "notiz"], "Schriftlich angeordnet, Beleg folgt.")
    await _unterschreiben(tab, f[K + "unterschrift_entscheidung"], "Olga Office")
    await tab.warten(f"document.querySelector('#q_{f[K + 'unterschrift_entscheidung']} .sig')")
    await tab.oeffnen(f"/orders/{auftrag}", "document.getElementById('orderTitle').textContent.includes('AUF-KT-1')")
    await asyncio.sleep(0.5)  # loadOpenConcerns() läuft nach dem Auftrag
    p.pruefe("Büro: Hinweis nach der Entscheidung weg", await tab.js(
        "[document.getElementById('concernAlert').hidden, document.getElementById('concernAlert').textContent]"), [True, ""])
    p.pruefe("Büro: keine JS-Fehler", tab.fehler, [])

    # --- Monteurin: /mobil ohne Hinweis ------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await _mobil(tab, p, "Monteurin", "dark")
    await asyncio.sleep(0.3)
    p.pruefe("Monteurin: nach der Entscheidung kein Hinweis", await tab.js("document.querySelectorAll('.concern-alert').length"), 0)
    await tab.bild("4_monteurin_mobil_ohne_hinweis_dunkel")
    p.pruefe("Monteurin: keine JS-Fehler (Ende)", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Bedenkenanzeige erfassen (1.8.43)", uhr="10:00"))
