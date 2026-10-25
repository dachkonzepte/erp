"""Klicktest: Bericht anlegen ohne Einsatz (seit 1.9.75, Stufe 4, R4 Nachtrag) -- „Heute“, Dialog „Für welchen Auftrag?“, Seite des Auftrags.

Befüllt: Objekt „Halle Nord“ (Hallenbau GmbH, seit 1.9.80 mit „Dachfläche Nord“); Auftrag A „Notdienst Rinne“ gestern für Mia und Tom eingeplant, B „Attika“ in 5 Tagen für Mia,
C „Wartung“ heute für Tom, F „Fremdauftrag“ für niemanden, G „Altauftrag“ vor 40 Tagen für Mia (zugänglich, nicht in ihrer Liste), seit
1.9.79 S „Stornoauftrag“ storniert mit einem Bericht von Mia. Feste Uhr 10:00.

    Mia (kein Einsatz)  Karte „Heute ist nichts eingeplant.“ mit „Bericht anlegen“ (grün, 56 px), kein „Bericht für einen anderen Auftrag“;
                        Klick -> Dialog „Für welchen Auftrag?“ mit „Deine Aufträge“ = der Liste von „Zeit nachtragen“ (B und A, nicht F),
                        je Zeile ≥ 56 px; „Abbrechen“ schließt; seit 1.9.80 Zeile A -> im Dialog „Bericht anlegen“ (A gewählt, Rapport,
                        Datum heute, Dachfläche zur Wahl, Vorlage erst bei einer Fläche), „Anlegen“ -> der neue Bericht (Auftrag A, Mia;
                        bis 1.9.79 über die Seite des Auftrags mit ?neu=1); quer hell (Bilder 1–3), hoch
                        800 × 1100 mit Dialog; seit 1.9.79 über die API S (storniert) -> 403 mit der Meldung, F (nie zugeordnet) ->
                        angelegt (1.9.74–1.9.78: F 403); Seite von G mit „+ Bericht“, ?neu=1 öffnet den Editor (1.9.77–1.9.78: Hinweis);
                        Seite von S (auch mit ?neu=1): kein „+ Bericht“, an seiner Stelle „Für diesen Auftrag legt das Büro Berichte
                        an.“, kein Editor (Bild 6, ganze Seite); Seite von A mit „+ Bericht“ ohne Hinweis; seit 1.9.78 Zeilen des
                        Dialogs „Nummer · Titel“, darunter
                        „Objekt · Kunde · Adresse“ (A und B am selben Objekt unterscheidbar), Auswahl „Auftrag“ in „Zeit nachtragen“
                        einzeilig mit Titel, höchstens 60 Zeichen (Bild 7, als offene Liste); seit 1.9.80 Suche „auftrag“ im Dialog:
                        Treffer G und F (nicht in ihrer Liste), nie S (storniert) (Bild 8), aus dem Treffer F angelegt -- der Bericht öffnet
                        sich (bis 1.9.79 F über die API)
    Tom (Einsatz C)     „Bericht anlegen“ in der Karte wie bisher (zur Seite von C), darunter „Bericht für einen anderen Auftrag“ (neutral,
                        48 px, außerhalb der Karte); Klick -> Dialog mit C und A (Bild 4)
    überall             keine JS-Fehler

Die Bilder liegen im Ordner der Screenshots.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_bericht_ohne_einsatz.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD]
        [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer etwa 20 Sekunden.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from datetime import timedelta
    from decimal import Decimal

    from app.berlin_time import berlin_today
    from app.meldungen import BERICHT_STORNIERT
    from app.models import (
        AppUser, Customer, Employee, Order, OrderItem, PlanningSlot, Project, Property, RoofArea, Team, WorkPreparationTeamAssignment,
        WorkPreparationTeamEmployee,
    )
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.service_reports import create_report
    from app.work_preparation import ensure_preparation

    heute = berlin_today()
    leute = {}
    for nr, (vor, nach) in enumerate([("Mia", "Monteurin"), ("Tom", "Monteur")], 1):
        leute[vor.lower()] = Employee(employee_number=f"E-{nr}", first_name=vor, last_name=nach, employee_group="gewerblich", active=True,
                                      hourly_wage=Decimal("22.00"))
    db.add_all(leute.values()); db.flush()
    benutzer = {n: AppUser(username=n, display_name=f"{e.first_name} {e.last_name}", role="field", employee_id=e.id, password_hash=k.passwort())
                for n, e in leute.items()}
    db.add_all(benutzer.values())
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    halle = Property(customer_id=kunde.id, name="Halle Nord", street="Werkstr. 5", postal_code="52531", city="Übach-Palenberg")
    db.add(halle); db.flush()
    db.add(RoofArea(property_id=halle.id, name="Dachfläche Nord", roof_type="flachdach"))  # seit 1.9.80: zur Wahl im Dialog
    db.flush()

    def auftrag(nr, titel):
        projekt = Project(project_number=f"P-KT-O{nr}", name=titel, customer_id=kunde.id, property_id=halle.id,
                          pipeline_column_id=default_pipeline_column_id(db))
        db.add(projekt); db.flush()
        o = Order(order_number=f"AUF-2026-010{nr}", project_id=projekt.id, source_quote_id=950 + nr, quote_number_snapshot=f"A-KT-O{nr}",
                  title=titel, customer_name=kunde.name, property_name=halle.name, property_address="Werkstr. 5\n52531 Übach-Palenberg")
        db.add(o); db.flush()
        db.add(OrderItem(order_id=o.id, sort_order=10, position_number="1", short_text=titel, quantity=Decimal("1"), unit="psch",
                         unit_price=Decimal("1")))
        db.commit()
        return o

    a, b, c, f = auftrag(1, "Notdienst Rinne"), auftrag(2, "Attika"), auftrag(3, "Wartung"), auftrag(4, "Fremdauftrag")
    g, s = auftrag(5, "Altauftrag"), auftrag(6, "Stornoauftrag")
    team = Team(name="Kolonne Nord", active=True)
    db.add(team); db.flush()
    for o, wer, von, bis in ((a, ("mia", "tom"), heute - timedelta(days=1), heute - timedelta(days=1)),
                             (b, ("mia",), heute + timedelta(days=5), heute + timedelta(days=5)),
                             (c, ("tom",), heute, heute),
                             (g, ("mia",), heute - timedelta(days=40), heute - timedelta(days=40))):
        prep = ensure_preparation(db, o.id)
        zuordnung = WorkPreparationTeamAssignment(preparation_id=prep.id, team_id=team.id, team_name_snapshot=team.name)
        db.add(zuordnung); db.flush()
        for n in wer:
            db.add(WorkPreparationTeamEmployee(assignment_id=zuordnung.id, employee_id=leute[n].id, employee_name_snapshot=leute[n].first_name))
        db.add(PlanningSlot(preparation_id=prep.id, team_assignment_id=zuordnung.id, start_date=von, end_date=bis))
    db.commit()
    create_report(db, s.id, "rapport", "Vor dem Storno", created_by_employee_id=leute["mia"].id)  # ihr Zugang zur Seite von S
    s.status = "storniert"
    db.commit()
    return {"a": a.id, "b": b.id, "c": c.id, "f": f.id, "g": g.id, "s": s.id, "heute": heute.isoformat(), "mia": leute["mia"].id,
            "meldung": BERICHT_STORNIERT,
            "cookies": {n: k.cookies(u) for n, u in benutzer.items()}}


BEREIT = "document.getElementById('arbeitszeit').innerHTML!==''&&!document.getElementById('naechsteKarte').hidden"
BERICHT_BEREIT = "document.getElementById('raster')&&!document.getElementById('raster').hidden&&typeof SCHRITT!=='undefined'&&SCHRITT"
ZEILEN = ("[document.getElementById('berichtDialog').open,document.getElementById('berichtDialogTitel').textContent,"
          "[...document.querySelectorAll('#berichtAuftraege [data-auftrag]')].map(a=>[Number(a.dataset.auftrag),"
          "Math.round(a.getBoundingClientRect().height)>=56])]")
LISTE = "fetch('/api/field-view/time-tracking/orders').then(r=>r.json()).then(l=>l.map(o=>o.id))"
ZEITEN_BEREIT = "!document.getElementById('tage').classList.contains('laedt')&&document.getElementById('monatName').textContent!==''"
AUFTRAG_GELADEN = "typeof orderData!=='undefined'&&!!orderData&&!!document.getElementById('reportList')"
KNOPF_ODER_HINWEIS = ("[document.getElementById('neuerBericht').hidden,document.getElementById('berichtNurBuero').hidden,"
                      "document.getElementById('berichtNurBuero').textContent,document.getElementById('editorCard').classList.contains('hidden')]")


def _soll(liste):
    return [[i, True] for i in liste]  # seit 1.9.80 Knöpfe (bis 1.9.79 Links mit ?neu=1)


async def _heute(tab, wer, seed, breite=1280, hoehe=620):
    await tab.anmelden(seed["cookies"][wer])
    await tab.fenster(breite, hoehe, mobil=True)
    await tab.oeffnen("/mobil", BEREIT)
    await tab.js("localStorage.setItem('erp_theme','light')")
    await tab.oeffnen("/mobil", BEREIT)


async def pruefen(tab, seed, p):
    a, b, c, f = seed["a"], seed["b"], seed["c"], seed["f"]

    # --- Mia: kein Einsatz heute ---------------------------------------------------------------------------------------------------
    await _heute(tab, "mia", seed)
    p.pruefe("Mia ohne Einsatz: „Heute ist nichts eingeplant.“ mit „Bericht anlegen“ (grün, 56 px), ohne „anderer Auftrag“", await tab.js(
        "(()=>{const k=document.getElementById('berichtOhneEinsatz');if(!k)return null;"
        "return [k.closest('section').textContent.includes('Heute ist nichts eingeplant.'),k.textContent,k.classList.contains('knopf-aktion'),"
        "Math.round(k.getBoundingClientRect().height),!!document.getElementById('berichtAndererAuftrag')]})()"),
        [True, "Bericht anlegen", True, 56, False])
    await tab.bild("1_heute_ohne_einsatz_quer_hell")
    liste = await tab.js(LISTE)
    p.pruefe("Liste von „Zeit nachtragen“: B und A, nicht F", sorted(liste), sorted([a, b]))
    await tab.js("document.getElementById('berichtOhneEinsatz').click()")
    await tab.warten("document.getElementById('berichtDialog').open")
    p.pruefe("Dialog „Für welchen Auftrag?“: „Deine Aufträge“ = genau diese Liste, je Zeile ≥ 56 px", await tab.js(ZEILEN),
             [True, "Für welchen Auftrag?", _soll(liste)])
    # seit 1.9.78: jede Zeile mit dem Titel -- A und B liegen am selben Objekt
    p.pruefe("Dialog: „Nummer · Titel“, darunter „Objekt · Kunde · Adresse“ -- zwei Aufträge am selben Objekt unterscheidbar", await tab.js(
        "[...document.querySelectorAll('#berichtAuftraege [data-auftrag]')].map(a=>[a.querySelector('.zeile-titel').textContent,"
        "a.querySelector('.zeile-sub').textContent])"),
        [["AUF-2026-0102 · Attika", "Halle Nord · Hallenbau GmbH · Werkstr. 5, 52531 Übach-Palenberg"], ["AUF-2026-0101 · Notdienst Rinne", "Halle Nord · Hallenbau GmbH · Werkstr. 5, 52531 Übach-Palenberg"]])
    await tab.bild("2_dialog_quer_hell")
    await tab.js("document.getElementById('berichtDialogAbbrechen').click()")
    p.pruefe("„Abbrechen“ schließt den Dialog", await tab.js("document.getElementById('berichtDialog').open"), False)

    await tab.js("document.getElementById('berichtOhneEinsatz').click()")
    await tab.warten("document.getElementById('berichtDialog').open")
    # seit 1.9.80: angelegt wird im Dialog -- Art, Datum, Dachflächen, Vorlage (erst bei genau einer Fläche), Beschreibung
    await tab.js(f"document.querySelector('#berichtAuftraege [data-auftrag=\"{a}\"]').click()")
    await tab.warten("!document.getElementById('berichtNeu').hidden", 15)
    await tab.warte_auf_ruhe()
    p.pruefe("Zeile A -> im Dialog „Bericht anlegen“: A gewählt, Rapport, Datum heute, Dachfläche zur Wahl, Vorlage noch verborgen", await tab.js(
        "[document.getElementById('berichtDialogTitel').textContent,document.querySelector('#berichtGewaehlt .zeile-titel').textContent,"
        "document.getElementById('neuArt').value,document.getElementById('neuDatum').value,"
        "[...document.querySelectorAll('#neuFlaechen label')].map(l=>l.textContent.trim()),document.getElementById('neuVorlage').hidden,"
        "!document.getElementById('berichtAnlegen').hidden&&!document.getElementById('berichtAnlegen').disabled,location.pathname]"),
        ["Bericht anlegen", "AUF-2026-0101 · Notdienst Rinne", "rapport", seed["heute"], ["Dachfläche Nord"], True, True, "/mobil"])
    fläche = "(c=>{{c.checked={};c.dispatchEvent(new Event('change',{{bubbles:true}}))}})(document.querySelector('#neuFlaechen input'))"
    await tab.js(fläche.format("true"))
    p.pruefe("Eine Fläche gewählt: die Vorlage zur Wahl, der Hinweis weg", await tab.js(
        "[document.getElementById('neuVorlage').hidden,document.getElementById('neuVorlageHinweis').hidden]"), [False, True])
    await tab.bild("3a_dialog_bericht_anlegen_quer_hell")
    await tab.js(fläche.format("false"))
    await tab.js("document.getElementById('neuBeschreibung').value='Notdienst: Rinne abgedichtet.'")
    await tab.js("document.getElementById('berichtAnlegen').click()")
    await tab.warten("location.pathname.startsWith('/service-reports/')", 15)
    await tab.warten(BERICHT_BEREIT, 15)
    await tab.warte_auf_ruhe()
    p.pruefe("Der neue Bericht: Auftrag A, angelegt von Mia, Rapport mit Beschreibung", await tab.js(
        "[R.order_id,R.created_by_employee_id,R.report_type,R.description,R.status]"),
        [a, seed["mia"], "rapport", "Notdienst: Rinne abgedichtet.", "entwurf"])
    await tab.js("window.scrollTo(0,0)")
    await tab.bild("3_neuer_bericht_quer_hell")
    # seit 1.9.79: zu jedem nicht stornierten Auftrag (1.9.74–1.9.78: F 403); zum stornierten 403
    anlegen = ("fetch('/api/orders/{}/service-reports',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
               "body:JSON.stringify({{report_type:'rapport'}})}}).then(async r=>[r.status,(await r.json()).detail||null])")
    p.pruefe("S (storniert) direkt über die API: 403 mit der Meldung", await tab.js(anlegen.format(seed["s"])), [403, seed["meldung"]])

    # seit 1.9.79: Seite von G (nicht in ihrer Liste) mit „+ Bericht“, ?neu=1 öffnet den Editor (1.9.77–1.9.78: der Hinweis); Seite von S
    # (storniert) statt „+ Bericht“ der Hinweis, auch ?neu=1 öffnet keinen Editor; Seite von A mit „+ Bericht“
    await tab.oeffnen(f"/orders/{seed['g']}/service-reports?neu=1", AUFTRAG_GELADEN)
    await tab.warte_auf_ruhe()
    p.pruefe("Seite eines Auftrags außerhalb der Liste (G): „+ Bericht“ da, ?neu=1 öffnet den Editor",
             await tab.js(KNOPF_ODER_HINWEIS), [False, True, "Für diesen Auftrag legt das Büro Berichte an.", False])
    await tab.oeffnen(f"/orders/{seed['s']}/service-reports?neu=1", AUFTRAG_GELADEN)
    await tab.warte_auf_ruhe()
    p.pruefe("Seite eines stornierten Auftrags (S): kein „+ Bericht“, an seiner Stelle der Hinweis, ?neu=1 öffnet nichts",
             await tab.js(KNOPF_ODER_HINWEIS), [True, False, "Für diesen Auftrag legt das Büro Berichte an.", True])
    voll = await tab.js("Math.ceil(document.documentElement.scrollHeight)")
    await tab.fenster(1280, max(620, voll), mobil=True)
    await tab.bild("6_auftragsseite_ohne_bericht_quer_hell")
    await tab.fenster(1280, 620, mobil=True)
    await tab.oeffnen(f"/orders/{a}/service-reports", AUFTRAG_GELADEN)
    await tab.warte_auf_ruhe()
    p.pruefe("Seite eines Auftrags der Liste: „+ Bericht“ da, kein Hinweis", await tab.js(KNOPF_ODER_HINWEIS),
             [False, True, "Für diesen Auftrag legt das Büro Berichte an.", True])

    await _heute(tab, "mia", seed, 800, 1100)
    await tab.js("document.getElementById('berichtOhneEinsatz').click()")
    await tab.warten("document.getElementById('berichtDialog').open")
    p.pruefe("Hoch (800 × 1100): Dialog mit derselben Liste, Knopfleiste im Bild", await tab.js(
        "["+ZEILEN+",(()=>{const r=document.getElementById('berichtDialogAbbrechen').getBoundingClientRect();return r.bottom<=innerHeight&&r.top>=0})()]"),
        [[True, "Für welchen Auftrag?", _soll(liste)], True])
    await tab.bild("2b_dialog_hoch_hell")

    # seit 1.9.78: die Auswahl „Auftrag“ in „Zeit nachtragen“ -- einzeilig mit dem Titel, gekürzt
    await tab.fenster(1280, 620, mobil=True)
    await tab.oeffnen("/mobil/zeiten", ZEITEN_BEREIT)
    await tab.js("document.getElementById('nachtragenKnopf').click()")
    await tab.warten("document.getElementById('zeitDialog').open")
    p.pruefe("„Zeit nachtragen“: Auswahl „Auftrag“ einzeilig mit Titel, höchstens 60 Zeichen, unterscheidbar", await tab.js(
        "(()=>{const t=[...document.querySelectorAll('#zdAuftrag option')].filter(o=>o.value).map(o=>o.textContent);"
        "return [t.map(x=>x.split(' · ').slice(0,2).join(' · ')),t.every(x=>x.length<=60&&!x.includes('\\n')),new Set(t).size===t.length]})()"),
        [["AUF-2026-0102 · Attika", "AUF-2026-0101 · Notdienst Rinne"], True, True])
    await tab.js("(s=>{s.size=3;s.style.height='auto'})(document.getElementById('zdAuftrag'))")  # fürs Bild als offene Liste
    await tab.bild("7_zeit_nachtragen_auswahl_quer_hell")
    # seit 1.9.80 (erst jetzt -- mit dem eigenen Bericht stünde F danach in ihrer Liste): die Suche im Dialog findet Aufträge außerhalb
    # ihrer Liste (G, F), nie den stornierten (S); aus dem Treffer F angelegt, danach öffnet sich der Bericht (eigener Bericht)
    await _heute(tab, "mia", seed)
    await tab.js("document.getElementById('berichtOhneEinsatz').click()")
    await tab.warten("document.getElementById('berichtDialog').open")
    await tab.js("document.getElementById('auftragSuche').focus()")
    await tab.cmd("Input.insertText", text="auftrag")
    await tab.warten("document.getElementById('berichtListeTitel').textContent==='Treffer'", 10)
    await tab.warte_auf_ruhe()
    p.pruefe("Suche „auftrag“: Treffer G und F (nicht in ihrer Liste), nicht S (storniert)", await tab.js(
        "[...document.querySelectorAll('#berichtAuftraege [data-auftrag]')].map(z=>[Number(z.dataset.auftrag),z.querySelector('.zeile-titel').textContent])"),
        [[seed["g"], "AUF-2026-0105 · Altauftrag"], [f, "AUF-2026-0104 · Fremdauftrag"]])
    await tab.bild("8_dialog_suche_treffer_quer_hell")
    await tab.js(f"document.querySelector('#berichtAuftraege [data-auftrag=\"{f}\"]').click()")
    await tab.warten("!document.getElementById('berichtNeu').hidden", 15)
    await tab.js("document.getElementById('berichtAnlegen').click()")
    await tab.warten("location.pathname.startsWith('/service-reports/')", 15)
    await tab.warten(BERICHT_BEREIT, 15)
    await tab.warte_auf_ruhe()
    p.pruefe("Aus dem Treffer angelegt: Bericht zu F von Mia, die Seite öffnet sich", await tab.js("[R.order_id,R.created_by_employee_id]"),
             [f, seed["mia"]])
    p.pruefe("Mia: keine JS-Fehler", tab.fehler, [])

    # --- Tom: Einsatz heute --------------------------------------------------------------------------------------------------------
    await _heute(tab, "tom", seed)
    p.pruefe("Tom mit Einsatz: „Bericht anlegen“ in der Karte wie bisher, darunter „Bericht für einen anderen Auftrag“ (neutral, 48 px)",
             await tab.js(
                 f"(()=>{{const karte=document.querySelector('[data-einsatz=\"{c}\"]'),w=karte&&[...karte.querySelectorAll('.einsatz-wege a')].find(x=>x.textContent==='Bericht anlegen'),"
                 "k=document.getElementById('berichtAndererAuftrag');if(!k||!w)return null;"
                 "return [w.getAttribute('href'),k.textContent,k.classList.contains('knopf-neutral'),Math.round(k.getBoundingClientRect().height),"
                 "!!k.closest('section'),!!document.getElementById('berichtOhneEinsatz')]})()"),
             [f"/orders/{c}/service-reports", "Bericht für einen anderen Auftrag", True, 48, False, False])
    await tab.bild("4_heute_mit_einsatz_quer_hell")
    tom_liste = await tab.js(LISTE)
    p.pruefe("Toms Liste: C und A", sorted(tom_liste), sorted([a, c]))
    await tab.js("document.getElementById('berichtAndererAuftrag').click()")
    await tab.warten("document.getElementById('berichtDialog').open")
    p.pruefe("Dialog für Tom: genau seine Liste", await tab.js(ZEILEN), [True, "Für welchen Auftrag?", _soll(tom_liste)])
    await tab.bild("5_dialog_tom_quer_hell")
    p.pruefe("Tom: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Bericht anlegen ohne Einsatz (1.9.75)", uhr="10:00"))
