"""Klicktest: Regeln für die Monteurin, Minimal-Anzeige (Stufe 4, Runde 1; seit 1.9.35 vergessener Feierabend, seit 1.9.36
Einsatzbericht: „Noch offen“ vor der Unterschrift, Pflichtpunkte; seit 1.9.41 Löschknopf nur am von Hand ergänzten Punkt).

Befüllt: Auftrag mit Einsatz (Plantafel heute ± 7 Tage) für Mia (Monteurin) und Tom (Monteur); beide haben eine Zeit, die gestern um
06:45 Uhr begann und noch läuft (Feierabend vergessen); Anna (Admin). Seit 1.9.36 dazu am Objekt des Auftrags die Dachfläche „Hauptdach“
(Flachdach, ein Gully) und Mias Rapportbericht mit Prüfvorlage (vier Pflichtpunkte, zwei freie) und einem von Hand ergänzten Punkt.

    Mia (412 px, dunkel)  /mobil: Hinweis „Deine Zeit läuft noch seit <gestern>, 06:45 Uhr“ mit Zeitart, Auftrag und „Ende nachtragen →“.
                          Meine Zeiten (seit 1.9.59 statt der Zeiterfassung): Zeile „läuft seit 06:45“ ohne Stunden mit „Feierabend auf
                          „Heute“ eintragen“; auf „Heute“ Start gesperrt, Ende leer -> „Bitte die Uhrzeit des Feierabends angeben.“, 06:00
                          -> Meldung des Servers (vor dem Start), 16:00 -> „Feierabend gestern eingetragen: anwesend 9:15 h · Pause nach
                          Zeitregel − 0:45 h · gebucht 8,50 h“, danach startet sie über die Kachel neu.
    Anna (1400 px, hell)  Zeiterfassung für Tom: dieselbe offene Anzeige, „Ende nachtragen“ 15:30 -> gebucht mit Pause; im Verlauf (API)
                          steht Anna.
    Mia (412 px, dunkel)  Einsatzbericht (seit 1.9.36): der Rapportbericht zeigt „Prüfpunkte“; am Knopf „Unterschreiben“ die Liste „Noch
                          offen vor der Unterschrift“ mit den vier Pflichtpunkten; Pflichtpunkte mit „*“ und ohne „×“, freie mit „×“;
                          „Unterschreiben“ öffnet die Unterschrift nicht, solange etwas offen ist; Pflichtpunkt löschen 409; nach dem
                          Beantworten öffnet sie, die Liste ist weg. Seit 1.9.41: „×“ nur am von Hand ergänzten Punkt, 48 × 48 px und
                          schmaler als die Zeile; Rückfrage „Prüfpunkt „…“ löschen?“ auf der Seite -- Abbrechen: bleibt, Löschen: weg;
                          Punkt aus der Vorlage löschen (API) 409.

Feste Uhr 10:00 (/mobil meldet ab 19 Uhr ab); die Daten liegen relativ zum heutigen Tag.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_monteurin_regeln.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import datetime, time, timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.inspection_templates import create_template, create_template_item
    from app.models import (
        AppUser, Customer, Employee, PlanningSlot, Project, Property, Quote, QuoteItem, Team, WorkPreparationEmployee,
        WorkPreparationTeamAssignment,
    )
    from app.roof_areas import create_roof_area, create_roof_component
    from app.service_reports import add_inspection_item, create_report
    from app.orders import create_order_from_quote
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.time_tracking import start_timer
    from app.work_preparation import ensure_preparation

    heute = berlin_today()
    gestern = heute - timedelta(days=1)
    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True,
                   hourly_wage=Decimal("22.00"))
    tom = Employee(employee_number="E-2", first_name="Tom", last_name="Monteur", employee_group="gewerblich", active=True,
                   hourly_wage=Decimal("22.00"))
    db.add_all([mia, tom]); db.flush()
    benutzer = {
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id, password_hash=k.passwort()),
        "anna": AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.flush()
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Uebach")
    db.add(objekt); db.flush()
    projekt = Project(project_number="P-KT-MR", name="Dachsanierung Halle", customer_id=kunde.id, status="angebot",
                      property_id=objekt.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    angebot = Quote(quote_number="A-KT-MR", project_id=projekt.id, title="Dachsanierung Halle", vat_rate=Decimal("19"))
    db.add(angebot); db.flush()
    db.add(QuoteItem(quote_id=angebot.id, position_number="1", short_text="Abdichtung", quantity=Decimal("850"), unit="m²",
                     unit_price=Decimal("48.90")))
    db.commit()
    auftrag = create_order_from_quote(db, angebot.id, order_date=heute - timedelta(days=30), execution_start=None, execution_end=None,
                                      caseworker_employee_id=None, project_manager_employee_id=None, payment_terms=None, remarks=None)
    prep = ensure_preparation(db, auftrag.id)
    team = Team(team_number="K-1", name="Kolonne 1")
    db.add(team); db.flush()
    zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
    db.add(zuordnung); db.flush()
    db.add_all([WorkPreparationEmployee(preparation_id=prep.id, employee_id=mia.id),
                WorkPreparationEmployee(preparation_id=prep.id, employee_id=tom.id),
                PlanningSlot(preparation_id=prep.id, team_assignment_id=zuordnung.id, start_date=heute - timedelta(days=7),
                             end_date=heute + timedelta(days=7))])
    db.commit()
    zeiten = {name: start_timer(db, employee_id=emp.id, order_id=auftrag.id, started_at=datetime.combine(gestern, time(6, 45))).id
              for name, emp in (("mia", mia), ("tom", tom))}
    # Seit 1.9.36: Rapportbericht mit Prüfvorlage (vier Pflichtpunkte, zwei freie)
    vorlage = create_template(db, "Flachdach Rapport", roof_type="Flachdach")
    for nr, (text, art, gruppe, bauteil, pflicht) in enumerate((
            ("Zugang und Absturzsicherung geprüft", "ja_nein", "Allgemein", None, True),
            ("Gesamtzustand Dachfläche", "condition_grade", "Allgemein", None, True),
            ("Ablauf frei und funktionsfähig", "ja_nein", "Entwässerung", "Gully", True),
            ("Laubfang vorhanden und intakt", "ja_nein", "Entwässerung", "Gully", False),
            ("Abdichtung auf Blasen, Risse, Falten", "condition_grade", "Fläche", None, True),
            ("Bemerkungen", "free_text", "Abschluss", None, False)), start=1):
        create_template_item(db, vorlage["id"], text, art, group_name=gruppe, component_type=bauteil, required=pflicht, sort_order=10 * nr)
    flaeche = create_roof_area(db, objekt.id, "Hauptdach", roof_type="Flachdach")
    create_roof_component(db, flaeche["id"], "Gully 1", component_type="Gully", sort_order=10)
    bericht = create_report(db, auftrag.id, "rapport", description="Abdichtung am Anschluss erneuert", created_by_employee_id=mia.id,
                            roof_area_ids=[flaeche["id"]], inspection_template_id=vorlage["id"])
    add_inspection_item(db, bericht["id"], "Dachluke geprüft", "ja_nein", roof_area_id=flaeche["id"])  # seit 1.9.41: von Hand ergänzt
    return {"auftrag": auftrag.id, "auftragsnummer": auftrag.order_number, "tom": tom.id, "zeiten": zeiten,
            "bericht": bericht["id"], "flaeche": flaeche["id"],
            "gestern": gestern.isoformat(), "gestern_de": f"{gestern:%d.%m.%Y}",
            "cookies": {name: k.cookies(u) for name, u in benutzer.items()}}


MOBIL_BEREIT = "!document.getElementById('assignmentsList').textContent.includes('Lädt')"
ZEITEN_BEREIT = "typeof D!=='undefined'&&D&&D.tage.length>0"
BUERO_BEREIT = "document.getElementById('activeCard').style.display==='block'"


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    g = seed["gestern_de"]

    # --- Mia: /mobil --------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await tab.oeffnen("/mobil", MOBIL_BEREIT)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen("/mobil", MOBIL_BEREIT)
    # seit 1.9.45 („Heute“): Signalkarte „Wartet auf dich“ mit dem Feld „Feierabend gestern um“ statt Hinweis mit Link zur Zeiterfassung
    await tab.warten("document.querySelector('.signal-karte')")
    text = await tab.js("document.querySelector('.signal-karte').innerText")
    p.pruefe("/mobil: Signalkarte mit Start, Zeitart, Auftrag", ["Deine Zeit von gestern läuft noch" in (text or ""),
             ", 06:45" in (text or ""), "Baustellenzeit" in (text or ""), seed["auftragsnummer"] in (text or "")], [True, True, True, True])
    p.pruefe("/mobil: Feld und Knopf „Feierabend eintragen“", await tab.js(
        "[!!document.getElementById('endeZeit'), document.getElementById('endeKnopf').textContent]"), [True, "Feierabend eintragen"])
    p.pruefe("/mobil: Ecke der Karte 16 px (Monteursrahmen)", await tab.js(
        "getComputedStyle(document.querySelector('.signal-karte')).borderTopLeftRadius"), "16px")
    p.pruefe("/mobil 412 px: kein waagrechter Scrollbalken", await tab.js(
        "document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.bild("1_mobil_offene_zeit_dunkel_412")

    # --- Mia: Meine Zeiten und Heute, offene Zeit (seit 1.9.59; bis dahin die Zeiterfassung der Monteurin) ------------------------
    await tab.oeffnen("/mobil/zeiten", ZEITEN_BEREIT)
    p.pruefe("Meine Zeiten: die offene Zeit „läuft seit 06:45“ ohne Stunden, Weg zu „Heute“", await tab.js(
        "(z=>[z.querySelector('.zeile-text span').textContent,z.querySelector('.zeile-stunden').textContent,"
        "z.querySelector('a.knopf').textContent,z.querySelector('a.knopf').getAttribute('href')])(document.querySelector('#tage .zeile'))"),
        [f"Baustellenzeit · {seed['auftragsnummer']} · läuft seit 06:45", "", "Feierabend auf „Heute“ eintragen", "/mobil"])
    await tab.bild("2_meine_zeiten_offene_zeit_dunkel_412")
    await tab.oeffnen("/mobil", "!!document.getElementById('endeKnopf')")
    p.pruefe("Heute: Start gesperrt, solange gestern offen ist", await tab.js(
        "[document.querySelector('.knopf-gesperrt').disabled,!!document.getElementById('startKacheln')]"), [True, False])
    await tab.js("document.getElementById('endeKnopf').click()")
    p.pruefe("Ende leer: Meldung", await tab.js("document.getElementById('zeitStatus').textContent"),
             "Bitte die Uhrzeit des Feierabends angeben.")
    await tab.js("(f=>{f.value='06:00';f.dispatchEvent(new Event('input'))})(document.getElementById('endeZeit'));"
                 "document.getElementById('endeKnopf').click()")
    await tab.warten("document.getElementById('zeitStatus').textContent.includes('Start')")
    p.pruefe("Ende vor dem Start: Meldung des Servers", await tab.js("document.getElementById('zeitStatus').textContent"),
             "Das Ende muss nach dem Start liegen (06:45 Uhr).")
    await tab.bild("3_ende_vor_start_dunkel_412")
    await tab.js("(f=>{f.value='16:00';f.dispatchEvent(new Event('input'))})(document.getElementById('endeZeit'))")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('endeKnopf').click()", "#arbeitszeit")
    p.pruefe("Ende nachgetragen: anwesend, Pause, gebucht", await tab.js("document.getElementById('zeitErgebnis').textContent"),
             "Feierabend gestern eingetragen: anwesend 9:15 h · Pause nach Zeitregel − 0:45 h · gebucht 8,50 h")
    await tab.bild("4_ende_nachgetragen_dunkel_412")
    await tab.js(f"document.getElementById('startAuftrag').value='{seed['auftrag']}'")
    await tab.warte_auf_neu_geladene_liste("document.querySelector('#startKacheln [data-zeitart=\"site\"]').click()", "#arbeitszeit")
    p.pruefe("Neu gestartet: Baustellenzeit seit 10:00 mit „Feierabend“", await tab.js(
        "[document.querySelector('#arbeitszeit .zeit-titel').textContent,!!document.getElementById('feierabendKnopf')]"),
        ["Baustellenzeit seit 10:00", True])
    p.pruefe("Mia: keine JS-Fehler", tab.fehler, [])

    # --- Anna: Zeiterfassung für Tom -----------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["anna"])
    await tab.fenster(1400, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen(f"/time-tracking?employee_id={seed['tom']}", BUERO_BEREIT)
    p.pruefe("Büro: offene Anzeige für Tom", await tab.js(
        "['offenBlock','endeBtn','stopBtn','activeTime'].map(id=>document.getElementById(id).style.display)"),
        ["block", "block", "none", "none"])
    p.pruefe("Büro: Hinweis", await tab.js("document.getElementById('offenHinweis').textContent"),
             f"Die Zeit vom {g} läuft noch (seit 06:45 Uhr). Ende an diesem Tag nachtragen.")
    await tab.bild("5_buero_offene_zeit_hell")
    await tab.js("document.getElementById('endeZeit').value='15:30';document.getElementById('endeBtn').click()")
    await tab.warten("document.getElementById('quickStatus').textContent.includes('Ende nachgetragen')")
    p.pruefe("Büro: gebucht mit Pause nach der Zeitregel", await tab.js("document.getElementById('quickStatus').textContent"),
             f"Ende nachgetragen ({g}): gebucht 8,25 h · anwesend 8,75 h · Pause 30 min")
    p.pruefe("Büro: keine laufende Zeit mehr", await tab.js("document.getElementById('activeCard').style.display"), "none")
    verlauf = await tab.js(
        f"fetch('/api/audit-logs?entity_id={seed['zeiten']['tom']}&actor=Anna&limit=50').then(r=>r.ok?r.json():null)")
    felder = sorted({e.get("field_name") for e in (verlauf or []) if e.get("actor_name") == "Anna Admin"})
    p.pruefe("Verlauf: Anna hat Toms Zeit geschlossen (Ende, Status)", {"ended_at", "status"} <= set(felder), True)
    p.pruefe("Anna: keine JS-Fehler", tab.fehler, [])

    # --- Mia: Einsatzbericht (seit 1.9.36; seit 1.9.67 auf der Berichtsseite /service-reports/{id}) -----------------------------
    b = seed["bericht"]
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(412, 900, mobil=True)
    await tab.js("localStorage.setItem('erp_theme','dark')")
    await tab.oeffnen(f"/service-reports/{b}", "typeof PUNKTE!=='undefined'&&PUNKTE.length===7&&!document.getElementById('raster').hidden")
    p.pruefe("Rapportbericht: Schritt 1 „Prüfpunkte“ (Vorlage an der Dachfläche)", await tab.js(
        "document.querySelector('#schritte .schritt').textContent.replace(/^\\d/,'')"), "Prüfpunkte")
    offen = ["Pflichtpunkt „Zugang und Absturzsicherung geprüft“ beantworten", "Pflichtpunkt „Gesamtzustand Dachfläche“ beantworten",
             "Pflichtpunkt „Gully 1: Ablauf frei und funktionsfähig“ beantworten",
             "Pflichtpunkt „Abdichtung auf Blasen, Risse, Falten“ beantworten"]
    liste = "[...document.querySelectorAll('#offenListe li')].map(x=>x.textContent)"
    p.pruefe("„Noch offen“ mit den vier Pflichtpunkten", await tab.js(liste), offen)
    zeilen = await tab.js("PUNKTE.map(x=>[x.text,!!document.querySelector('#punkt-kopf-'+x.id+' .pflicht'),"
                          "!!document.querySelector('#punkt-menue-'+x.id+' [data-klick=punkt-loeschen]')])")
    # seit 1.9.41 nur am von Hand ergänzten Punkt (bis 1.9.40 an jedem freien Punkt), seit 1.9.67 im Menü „⋮“ des Punkts statt „×“
    p.pruefe("Prüfpunkte: Pflicht mit „*“, „Prüfpunkt löschen“ nur am von Hand ergänzten Punkt", sorted(zeilen or []),
             sorted([["Zugang und Absturzsicherung geprüft", True, False], ["Gesamtzustand Dachfläche", True, False],
                     ["Gully 1: Ablauf frei und funktionsfähig", True, False], ["Gully 1: Laubfang vorhanden und intakt", False, False],
                     ["Abdichtung auf Blasen, Risse, Falten", True, False], ["Bemerkungen", False, False],
                     ["Dachluke geprüft", False, True]]))
    await tab.js("[...document.querySelectorAll('#schrittInhalt .gruppe')].find(g=>g.textContent.includes('Entwässerung')).scrollIntoView({block:'start'})")
    await tab.bild("6_rapport_pflichtpunkte_dunkel_412")
    await tab.js("document.getElementById('schritt-unterschrift').click()")
    await tab.warte_auf_ruhe()
    p.pruefe("Unterschrift mit offenen Pflichten: „Bericht abschließen“ gesperrt, „Noch offen“ in der Karte", await tab.js(
        "[document.getElementById('abschliessenKnopf').disabled,document.getElementById('fehltText').textContent.startsWith('Fehlt: 4 Punkte unter „Noch offen“'),"
        "[...document.querySelectorAll('#signOffenListe li')].map(x=>x.textContent)]"), [True, True, offen])
    await tab.js("document.getElementById('signOffen').scrollIntoView({block:'center'})")
    await tab.bild("7_noch_offen_dunkel_412")
    punkte = await tab.js(f"fetch('/api/service-reports/{b}/inspection-items').then(r=>r.json())")
    pflicht = [x["id"] for x in punkte if x["required"]]
    vorlage_frei = next(x["id"] for x in punkte if not x["required"] and x["template_item_id"] is not None)
    p.pruefe("Punkt aus der Vorlage löschen (API, Pflicht und frei): 409", await tab.js(
        f"Promise.all([{pflicht[0]},{vorlage_frei}].map(i=>fetch('/api/inspection-items/'+i,{{method:'DELETE'}}).then(async r=>[r.status,(await r.json()).detail])))"),
        [[409, "Ein Prüfpunkt aus der Vorlage lässt sich nicht löschen – trifft er nicht zu, „Entfällt“ wählen."]] * 2)

    # --- seit 1.9.41: Löschen am von Hand ergänzten Punkt, Rückfrage auf der Seite (seit 1.9.67 im Menü „⋮“ des Punkts) -------------
    await tab.js("document.getElementById('schritt-pruefpunkte').click()")
    await tab.warte_auf_ruhe()
    eigen = await tab.js("PUNKTE.find(x=>x.text==='Dachluke geprüft').id")
    menue, eintrag = f"document.getElementById('punkt-menue-{eigen}')", f"document.querySelector('#punkt-menue-{eigen} [data-klick=punkt-loeschen]')"

    async def menue_auf():
        await tab.js(f"document.getElementById('punkt-menue-knopf-{eigen}').click()")
        await tab.warten(f"!{menue}.hidden", 10)
    await menue_auf()
    p.pruefe("Menü am eigenen Punkt: „Prüfpunkt löschen“ 48 px hoch, rot", await tab.js(
        f"(k=>[Math.round(k.getBoundingClientRect().height),k.textContent,k.classList.contains('ds-menue-eintrag-fehler')])({eintrag})"),
        [48, "Prüfpunkt löschen", True])
    await tab.bild("8_loeschknopf_dunkel_412")
    await tab.js(f"{eintrag}.click()")
    await tab.warten("document.getElementById('rueckfrageDialog').open", 10)
    p.pruefe("Rückfrage auf der Seite", await tab.js("document.getElementById('rueckfrageText').textContent"),
             "Prüfpunkt „Dachluke geprüft“ löschen?")
    await tab.bild("9_rueckfrage_loeschen_dunkel_412")
    await tab.js("document.getElementById('rueckfrageNein').click()")
    await tab.warte_auf_ruhe()
    p.pruefe("Abbrechen: Punkt bleibt", [await tab.js("document.getElementById('rueckfrageDialog').open"), await tab.js(
        f"fetch('/api/service-reports/{b}/inspection-items').then(r=>r.json()).then(l=>l.some(x=>x.text==='Dachluke geprüft'))")],
        [False, True])
    await menue_auf()
    await tab.js(f"{eintrag}.click()")
    await tab.warten("document.getElementById('rueckfrageDialog').open", 10)
    await tab.js("document.getElementById('rueckfrageJa').click()")
    await tab.warten(f"!PUNKTE.some(x=>x.id==={eigen})", 10)
    await tab.warte_auf_ruhe()
    p.pruefe("Löschen: Punkt weg", [await tab.js(
        f"fetch('/api/service-reports/{b}/inspection-items').then(r=>r.json()).then(l=>l.some(x=>x.text==='Dachluke geprüft'))"),
        await tab.js(f"!!document.getElementById('punkt-{eigen}')")], [False, False])
    for item_id in pflicht:  # Testhandlung: beantwortet über die API
        await tab.js(f"fetch('/api/inspection-items/{item_id}',{{method:'PUT',headers:{{'Content-Type':'application/json'}},"
                     "body:JSON.stringify({result:'ok',condition_grade:1})}).then(r=>r.status)")
    await tab.oeffnen(f"/service-reports/{b}", "typeof PUNKTE!=='undefined'&&PUNKTE.length===6&&!document.getElementById('raster').hidden")
    p.pruefe("Beantwortet: „Noch offen“ leer", await tab.js(liste), [])
    await tab.js("document.getElementById('schritt-unterschrift').click()")
    await tab.warte_auf_ruhe()
    p.pruefe("Beantwortet: es fehlen nur noch die Unterschriften", await tab.js("document.getElementById('fehltText').textContent"),
             "Fehlt: Unterschrift Monteur, Name Kunde, Unterschrift Kunde")
    p.pruefe("Einsatzbericht: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Regeln für die Monteurin (Stufe 4, R1)", uhr="10:00"))
