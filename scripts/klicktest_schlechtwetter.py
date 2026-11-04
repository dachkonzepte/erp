"""Klicktest: Ausfalltag Schlechtwetter (1.9.170, Lohn L1a, Punkt 5, E5) -- „Meine Zeiten“ und „Zeiten“.

    Kai (Kolonnenführer, 1280 × 620)  „Schlechtwetter“ -> Dialog „Schlechtwetter eintragen“ mit Kolonne und Personen; Kolonne 1 hakt Kai, Mia
                                     und Tom an; Samstag 05.12.2026 -> Meldung des Servers, nichts gespeichert; Montag 07.12.2026 -> „Schlechtwetter
                                     eingetragen: …“ -- Bild
    Tom (Monteur, 1280 × 620)        Dialog „Schlechtwetter beantragen“ ohne Personen und Kolonne; Dienstag 08.12.2026 -> „Schlechtwetter beantragt“,
                                     ein offener Antrag
    Kai                              seit 1.9.204: Kolonne 1 am Montag noch einmal -> „Nicht eingetragen: Kai Kolonne: am 07.12.2026 bereits
                                     abwesend; Tom …; Mia …“ -- Bild; am Dienstag nur Tom „bereits ein offener Antrag“, für Kai und Mia nichts;
                                     Karte „Schlechtwetter bestätigen“ mit Tom · Di 08.12.2026 -> „Bestätigen“ -> die Karte ist leer, Toms Tag
                                     genehmigt -- Bild
    Fin (Büro – Finanzen, 1440)      „Zeiten → Abwesenheiten“: „Schlechtwetter eintragen“; Uwe am 09.12.2026, an dem er Zeit gebucht hat -> Rückfrage
                                     „An diesem Tag ist schon Zeit gebucht: Uwe …“, „Trotzdem eintragen“ -> eingetragen; die Liste zeigt „Schlechtwetter“;
                                     seit 1.9.178 Uwe am Do 10.12.2026, als betriebsfreier Tag eingetragen -> Rückfrage „Der 10.12.2026 ist als
                                     betriebsfreier Tag eingetragen (Betriebsausflug).“, „Trotzdem eintragen“ -> eingetragen -- Bilder
    überall                          keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_schlechtwetter.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD]
        [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

MEINE_BEREIT = ("!document.getElementById('tage').classList.contains('laedt')&&document.getElementById('monatName').textContent!==''"
                "&&typeof SW!=='undefined'&&!!SW")
ZEITEN_BEREIT = "!!window.P&&document.getElementById('monatTitel').textContent!==''&&typeof SW!=='undefined'&&!!SW"


def befuellen(db, k):
    from datetime import date, datetime, time
    from decimal import Decimal

    from app.models import AppUser, Customer, Employee, Order, PlanningHoliday, Project, Team, TeamEmployee, TimeEntry
    from app.project_pipeline_columns import default_pipeline_column_id

    leute = {}
    for nr, (vor, nach) in enumerate([("Kai", "Kolonne"), ("Mia", "Monteurin"), ("Tom", "Monteur"), ("Uwe", "Ohnekolonne")], 1):
        leute[vor.lower()] = Employee(employee_number=f"E-{nr}", first_name=vor, last_name=nach, employee_group="gewerblich", active=True)
    db.add_all(leute.values()); db.flush()
    team = Team(team_number="K-1", name="Kolonne 1", active=True)
    db.add(team); db.flush()
    db.add_all([TeamEmployee(team_id=team.id, employee_id=leute["kai"].id, is_crew_leader=True),
                TeamEmployee(team_id=team.id, employee_id=leute["mia"].id), TeamEmployee(team_id=team.id, employee_id=leute["tom"].id)])
    kunde = Customer(name="Hallenbau GmbH", last_name="Hallenbau GmbH", is_consumer=False)
    db.add(kunde); db.flush()
    projekt = Project(project_number="P-KT-SW1", name="Halle", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-2026-0001", project_id=projekt.id, source_quote_id=951, quote_number_snapshot="A-KT-1", title="Halle",
                    customer_name=kunde.name)
    db.add(auftrag); db.flush()
    tag = date(2026, 12, 9)
    db.add(TimeEntry(employee_id=leute["uwe"].id, project_id=projekt.id, order_id=auftrag.id, work_date=tag, entry_type="site",
                     hours=Decimal("2"), break_minutes=0, status="booked", started_at=datetime.combine(tag, time(7)),
                     ended_at=datetime.combine(tag, time(9))))
    db.add(PlanningHoliday(holiday_date=date(2026, 12, 10), name="Betriebsausflug", active=True))  # seit 1.9.178: Rückfrage statt stiller Annahme
    benutzer = {
        "kai": AppUser(username="kai", display_name="Kai Kolonne", role="field", employee_id=leute["kai"].id, password_hash=k.passwort()),
        "tom": AppUser(username="tom", display_name="Tom Monteur", role="field", employee_id=leute["tom"].id, password_hash=k.passwort()),
        "fin": AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort()),
    }
    db.add_all(benutzer.values())
    db.commit()
    return {"cookies": {n: k.cookies(u) for n, u in benutzer.items()}, "ids": {n: e.id for n, e in leute.items()}}


async def _setze(tab, werte: dict):
    await tab.js(";".join(f"document.getElementById('{i}').value={v!r}" for i, v in werte.items()))


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    ids = seed["ids"]

    # ---- Kai: Kolonnenführer ------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["kai"])
    await tab.fenster(1280, 620)
    p.pruefe("Kai: Meine Zeiten geladen, Knopf da", [await tab.oeffnen("/mobil/zeiten", MEINE_BEREIT),
                                                    await tab.js("document.getElementById('swNeu').hidden")], [True, False])
    await tab.js("document.getElementById('swNeu').click()")
    p.pruefe("Kai: Dialog für andere", await tab.js(
        "[document.getElementById('swDialog').open,document.getElementById('swTitel').textContent,document.getElementById('swKolonneFeld').hidden,"
        "[...document.querySelectorAll('[data-sw-person]')].length]"), [True, "Schlechtwetter eintragen", False, 4])
    await tab.js("{const s=document.getElementById('swKolonne');s.value=[...s.options].find(o=>o.text==='Kolonne 1').value;"
                 "s.dispatchEvent(new Event('change'))}")
    p.pruefe("Kai: Kolonne hakt ihre Mitglieder an", await tab.js(
        "[...document.querySelectorAll('[data-sw-person]:checked')].map(c=>c.parentElement.textContent.trim()).sort()"),
        ["Kai Kolonne", "Mia Monteurin", "Tom Monteur"])
    await _setze(tab, {"swTag": "2026-12-05"})
    await tab.js("document.getElementById('swSenden').click()")
    p.pruefe("Kai: Samstag abgelehnt", await tab.warten(
        "document.getElementById('swStatus').textContent.includes('Samstag 05.12.2026 ist kein Arbeitstag')", 10), True)
    await _setze(tab, {"swTag": "2026-12-07"})
    await tab.js("document.getElementById('swSenden').click()")
    await tab.warten("document.getElementById('ergebnis').textContent.startsWith('Schlechtwetter')", 10)
    await tab.warte_auf_ruhe()
    p.pruefe("Kai: eingetragen (Namen nach Nachname)", [await tab.js("document.getElementById('swDialog').open"),
                                                      await tab.js("document.getElementById('ergebnis').textContent")],
             [False, "Schlechtwetter eingetragen: Kai Kolonne, Tom Monteur, Mia Monteurin, Mo 07.12.2026"])
    await tab.bild("schlechtwetter_kai_eingetragen")
    p.pruefe("Kai: keine JS-Fehler", tab.fehler, [])

    # ---- Tom: beantragt für sich ---------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["tom"])
    p.pruefe("Tom: geladen", await tab.oeffnen("/mobil/zeiten?als=tom", MEINE_BEREIT), True)
    await tab.js("document.getElementById('swNeu').click()")
    p.pruefe("Tom: Dialog nur für sich", await tab.js(
        "[document.getElementById('swTitel').textContent,document.getElementById('swKolonneFeld').hidden,document.getElementById('swPersonenFeld').hidden]"),
        ["Schlechtwetter beantragen", True, True])
    await _setze(tab, {"swTag": "2026-12-08"})
    await tab.js("document.getElementById('swSenden').click()")
    await tab.warten("document.getElementById('ergebnis').textContent.startsWith('Schlechtwetter')", 10)
    await tab.warte_auf_ruhe()
    p.pruefe("Tom: beantragt", await tab.js("document.getElementById('ergebnis').textContent"), "Schlechtwetter beantragt: Tom Monteur, Di 08.12.2026")
    p.pruefe("Tom: keine Karte zum Bestätigen", await tab.js("document.getElementById('swAntraege').hidden"), True)
    p.pruefe("Tom: keine JS-Fehler", tab.fehler, [])

    # ---- Kai bestätigt -----------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["kai"])
    p.pruefe("Kai: geladen", await tab.oeffnen("/mobil/zeiten?als=kai", MEINE_BEREIT), True)
    # seit 1.9.204 (L1a Stufe 4, Punkt 3): schon abwesend oder ein offener Antrag -- jede Person mit Namen und Grund, nichts eingetragen
    await tab.js("document.getElementById('swNeu').click()")
    await tab.js("{const s=document.getElementById('swKolonne');s.value=[...s.options].find(o=>o.text==='Kolonne 1').value;"
                 "s.dispatchEvent(new Event('change'))}")
    await _setze(tab, {"swTag": "2026-12-07"})
    await tab.js("document.getElementById('swSenden').click()")
    p.pruefe("Kai: Montag schon eingetragen -> jede Person mit Grund", await tab.warten(
        "document.getElementById('swStatus').textContent==='Nicht eingetragen: Kai Kolonne: am 07.12.2026 bereits abwesend; Tom Monteur: am "
        "07.12.2026 bereits abwesend; Mia Monteurin: am 07.12.2026 bereits abwesend.'", 10), True)
    await tab.bild("schlechtwetter_kai_schon_abwesend")
    await _setze(tab, {"swTag": "2026-12-08"})
    await tab.js("document.getElementById('swSenden').click()")
    p.pruefe("Kai: Dienstag -> Tom mit offenem Antrag genannt, für Kai und Mia nichts", await tab.warten(
        "document.getElementById('swStatus').textContent==='Nicht eingetragen: Tom Monteur: am 08.12.2026 bereits ein offener Antrag.'", 10), True)
    await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('swAbbrechen').click()")
    p.pruefe("Kai: Antrag zum Bestätigen", await tab.js(
        "[document.getElementById('swAntraege').hidden,[...document.querySelectorAll('[data-sw-antrag] span')].map(s=>s.textContent)]"),
        [False, ["Tom Monteur · Di 08.12.2026"]])
    await tab.js("document.getElementById('swAntraege').scrollIntoView({block:'center'})")
    await tab.bild("schlechtwetter_kai_bestaetigen")
    await tab.warte_auf_neu_geladene_liste("document.querySelector('[data-sw-entscheiden=\"approved\"]').click()", "#swAntraege")
    p.pruefe("Kai: bestätigt, Karte leer", [await tab.js("document.getElementById('swAntraege').hidden"),
                                           await tab.js("document.getElementById('ergebnis').textContent")],
             [True, "Bestätigt: Tom Monteur, Di 08.12.2026"])
    p.pruefe("Kai: keine JS-Fehler", tab.fehler, [])

    # ---- Fin: Zeiten → Abwesenheiten, Rückfrage bei gebuchter Zeit -------------------------------------------------------------------------
    await tab.anmelden(seed["cookies"]["fin"])
    await tab.fenster(1440, 900)
    p.pruefe("Fin: Zeiten geladen", await tab.oeffnen("/zeiten#abwesenheiten", ZEITEN_BEREIT), True)
    p.pruefe("Fin: Knopf „Schlechtwetter eintragen“", await tab.warten("!document.getElementById('swNeu').hidden", 10), True)
    await tab.js("document.getElementById('swNeu').click()")
    await tab.js(f"document.querySelector('[data-sw-person=\"{ids['uwe']}\"]').checked=true")
    await _setze(tab, {"swTag": "2026-12-09"})
    await tab.js("document.getElementById('swSenden').click()")
    p.pruefe("Fin: Rückfrage bei gebuchter Zeit", await tab.warten(
        "!document.getElementById('swTrotzdem').hidden&&document.getElementById('swStatus').textContent.includes('Uwe Ohnekolonne 2,00 h gebucht')", 10), True)
    await tab.bild("schlechtwetter_fin_rueckfrage")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('swTrotzdem').click()", "#abwListe")
    p.pruefe("Fin: eingetragen, in der Liste als Schlechtwetter", [await tab.js("document.getElementById('swDialog').open"),
             await tab.js("[...document.querySelectorAll('#abwListe .zeile-name')].map(z=>z.innerText).filter(t=>t.includes('Schlechtwetter')).length")],
             [False, 5])
    await tab.js("document.getElementById('swNeu').click()")
    await tab.js(f"document.querySelector('[data-sw-person=\"{ids['uwe']}\"]').checked=true")
    await _setze(tab, {"swTag": "2026-12-10"})
    await tab.js("document.getElementById('swSenden').click()")
    p.pruefe("Fin: Rückfrage am betriebsfreien Tag", await tab.warten(
        "!document.getElementById('swTrotzdem').hidden&&document.getElementById('swStatus').textContent==="
        "'Der 10.12.2026 ist als betriebsfreier Tag eingetragen (Betriebsausflug).'", 10), True)
    await tab.bild("schlechtwetter_fin_betriebsfrei")
    await tab.warte_auf_neu_geladene_liste("document.getElementById('swTrotzdem').click()", "#abwListe")
    p.pruefe("Fin: am betriebsfreien Tag eingetragen", [await tab.js("document.getElementById('swDialog').open"),
             await tab.js("[...document.querySelectorAll('#abwListe .zeile-name')].map(z=>z.innerText).filter(t=>t.includes('Schlechtwetter')).length")],
             [False, 6])
    await tab.bild("schlechtwetter_fin_liste")
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-12-07 10:00"))
