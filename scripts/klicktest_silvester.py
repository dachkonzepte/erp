"""Klicktest: Silvester im Urlaub -- ganzer Urlaubstag oder frei (1.9.176, L1a-Nachtrag, Punkt 3).

    Ada (Admin, 1440)       „Zeiten → Abwesenheiten“: Urlaub Mo 28.12.2026–Fr 08.01.2027 für Mia -> der Server fragt, der Dialog zeigt die
                            Frage (Vorschlag „Ganzer Urlaubstag“ gewählt) -- Bild; „frei“ gewählt -> gesendet, in der Liste „Kalendertag frei,
                            kein Urlaubstag · 8 Arbeitstage“; Sammeleintrag Tom (gewerblich) und Kim (kaufmännisch) 30.–31.12. -> Frage, Vorschlag ->
                            Tom „Kalendertag als Urlaubstag · 2 Arbeitstage“, Kim „2 Arbeitstage“; Plantafel „Abwesenheiten“: Lea 31.12. -> Frage
                            im Dialog, Vorschlag -> „Abwesenheit eingetragen.“; keine JS-Fehler
    Mia (Monteurin, 1280)   „Meine Zeiten“ -> „+ Antrag“: Urlaub 27.–31.12.2027 -> Frage -- Bild; Vorschlag -> „Antrag wurde gesendet.“, in der
                            Liste „Kalendertag als Urlaubstag“; keine JS-Fehler

Stehende Uhr Mi 11.11.2026, 10:00 Uhr.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_silvester.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD]
        [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

ZEITEN_BEREIT = "!!window.P&&document.getElementById('monatTitel').textContent!==''&&!!window.A"
MEINE_BEREIT = "!document.getElementById('tage').classList.contains('laedt')&&document.getElementById('monatName').textContent!==''"
TAFEL_BEREIT = "typeof board!=='undefined'&&board&&board.teams&&board.teams.length>0"
FRAGE = ("[!document.getElementById('adKalenderFrage').hidden,document.querySelector('#adKalenderFrage p')?document.querySelector('#adKalenderFrage p')"
         ".textContent:'',[...document.querySelectorAll('#adKalenderFrage input[type=radio]')].map(r=>r.value+(r.checked?'*':''))]")


def befuellen(db, k):
    from app.models import AppUser, Employee, Team, TeamEmployee

    leute = {}
    for nr, (vor, nach, gruppe) in enumerate([("Mia", "Monteurin", "gewerblich"), ("Tom", "Monteur", "gewerblich"), ("Kim", "Kauffrau", "kaufmaennisch"),
                                             ("Lea", "Dachdeckerin", "gewerblich")], 1):
        leute[vor.lower()] = Employee(employee_number=f"E-{nr}", first_name=vor, last_name=nach, employee_group=gruppe, active=True)
    db.add_all(leute.values())
    db.flush()
    team = Team(team_number="K-1", name="Kolonne 1", active=True)
    db.add(team)
    db.flush()
    db.add_all([TeamEmployee(team_id=team.id, employee_id=leute[n].id) for n in ("mia", "tom", "lea")])
    ada = AppUser(username="ada", display_name="Ada Admin", role="admin", password_hash=k.passwort())
    mia = AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=leute["mia"].id, password_hash=k.passwort())
    db.add_all([ada, mia])
    db.commit()
    return {"ada": k.cookies(ada), "mia": k.cookies(mia), "ids": {n: e.id for n, e in leute.items()}, "uhr_ms": k.uhr_ms()}


async def _setze(tab, werte: dict):
    await tab.js(";".join(f"{{const f=document.getElementById('{i}');f.value={v!r};f.dispatchEvent(new Event('change'))}}" for i, v in werte.items()))


async def _senden(tab) -> str:
    await tab.js("document.getElementById('adStatus').textContent='';document.getElementById('adSenden').click()")
    await tab.warten("document.getElementById('adStatus').textContent!==''||!document.getElementById('abwDialog').open"
                     "||(document.getElementById('adErgebnis')&&document.getElementById('adErgebnis').textContent!=='')", 10)
    await tab.warte_auf_ruhe()
    return await tab.js("document.getElementById('abwDialog').open?(document.getElementById('adStatus').textContent||document.getElementById('adErgebnis')"
                        ".textContent):document.getElementById('ergebnis').textContent")


def _zeilen(tab):
    return tab.js("[...document.querySelectorAll('#abwListe .zeile')].map(z=>z.querySelector('.zeile-name').innerText+' | '"
                  "+z.querySelector('.zeile-unter').innerText.split(' · beantragt')[0])")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.browser_uhr_fest(seed["uhr_ms"])
    ids = seed["ids"]

    await tab.anmelden(seed["ada"])
    await tab.fenster(1440, 900)
    p.pruefe("Ada: Abwesenheiten geladen", await tab.oeffnen("/zeiten#abwesenheiten", ZEITEN_BEREIT), True)
    await tab.js("document.getElementById('abwNeu').click()")
    p.pruefe("Ada: keine Frage beim Öffnen", await tab.js("document.getElementById('adKalenderFrage').hidden"), True)
    await _setze(tab, {"adMitarbeiter": str(ids["mia"]), "adKategorie": "urlaub", "adVon": "2026-12-28", "adBis": "2027-01-08"})
    p.pruefe("Ada: der Server fragt", await _senden(tab), "Bitte wählen und noch einmal senden.")
    p.pruefe("Ada: Frage mit Vorschlag Urlaubstag", await tab.js(FRAGE),
             [True, "Do 31.12.2026 (Silvester) liegt im Urlaub. Wie zählt der Tag?", ["urlaub*", "frei"]])
    await tab.bild("silvester_zeiten_frage")
    await tab.js("document.querySelector('#adKalenderFrage input[value=frei]').click()")
    p.pruefe("Ada: „frei“ gesendet", await _senden(tab), "Antrag gesendet: Mia Monteurin, Mo 28.12.2026–Fr 08.01.2027")
    await tab.warte_auf_neu_geladene_liste("abwesenheitenLaden()", "#abwListe")
    p.pruefe("Ada: Liste nennt „frei“ und 8 Arbeitstage", await _zeilen(tab),
             ["Mia Monteurin · Urlaub | Mo 28.12.2026–Fr 08.01.2027 · Kalendertag frei, kein Urlaubstag · 8 Arbeitstage"])

    await tab.js("document.getElementById('abwNeu').click()")
    await tab.js("{const m=document.getElementById('adMehrere');m.checked=true;m.dispatchEvent(new Event('change'))}")
    await tab.js(f"document.querySelector('[data-ad-person=\"{ids['tom']}\"]').checked=true;document.querySelector('[data-ad-person=\"{ids['kim']}\"]').checked=true")
    await _setze(tab, {"adKategorie": "urlaub", "adVon": "2026-12-30", "adBis": "2026-12-31"})
    p.pruefe("Ada: Sammeleintrag -- der Server fragt", await _senden(tab), "Bitte wählen und noch einmal senden.")
    p.pruefe("Ada: Sammeleintrag mit dem Vorschlag", await _senden(tab), "Eingetragen für 2 Personen, Mi 30.12.–Do 31.12.2026")
    await tab.warte_auf_neu_geladene_liste("abwesenheitenLaden()", "#abwListe")
    zeilen = await _zeilen(tab)
    p.pruefe("Ada: Tom mit Urlaubstag, Kim ohne Frage", sorted(z for z in zeilen if z.startswith(("Tom", "Kim"))),
             ["Kim Kauffrau · Urlaub | Mi 30.12.–Do 31.12.2026 · 2 Arbeitstage",
              "Tom Monteur · Urlaub | Mi 30.12.–Do 31.12.2026 · Kalendertag als Urlaubstag · 2 Arbeitstage"])
    p.pruefe("Ada: keine JS-Fehler in Zeiten", tab.fehler, [])

    p.pruefe("Ada: Plantafel geladen", await tab.oeffnen("/planning", TAFEL_BEREIT), True)
    await tab.js("void openAbsences()")
    await tab.warten("document.getElementById('absenceDialog').open")
    await tab.js(f"document.getElementById('absenceEmployee').value='{ids['lea']}';document.getElementById('absenceCategory').value='urlaub';"
                 "document.getElementById('absenceStart').value='2026-12-31';document.getElementById('absenceEnd').value='2026-12-31';"
                 "document.getElementById('absenceStatus').textContent=''")
    await tab.js("void saveAbsence()")
    await tab.warten("document.getElementById('absenceStatus').textContent.length>0")
    await tab.warte_auf_ruhe()
    p.pruefe("Plantafel: Frage im Dialog", await tab.js(
        "[document.getElementById('absenceStatus').textContent,!document.getElementById('adKalenderFrage').hidden,"
        "[...document.querySelectorAll('#adKalenderFrage input[type=radio]')].map(r=>r.value+(r.checked?'*':''))]"),
        ["Bitte wählen und noch einmal eintragen.", True, ["urlaub*", "frei"]])
    await tab.js("document.getElementById('absenceStatus').textContent='';void saveAbsence()")
    await tab.warten("document.getElementById('absenceStatus').textContent.length>0")
    await tab.warte_auf_ruhe()
    p.pruefe("Plantafel: mit dem Vorschlag eingetragen", await tab.js(
        "[document.getElementById('absenceStatus').textContent,document.getElementById('adKalenderFrage').hidden]"), ["Abwesenheit eingetragen.", True])
    p.pruefe("Ada: keine JS-Fehler auf der Plantafel", tab.fehler, [])

    await tab.anmelden(seed["mia"])
    await tab.fenster(1280, 620)
    p.pruefe("Mia: Meine Zeiten geladen", await tab.oeffnen("/mobil/zeiten", MEINE_BEREIT), True)
    await tab.js("document.getElementById('antragKnopf').click()")
    await _setze(tab, {"adKategorie": "urlaub", "adVon": "2027-12-27", "adBis": "2027-12-31"})
    p.pruefe("Mia: der Server fragt", await _senden(tab), "Bitte wählen und noch einmal senden.")
    p.pruefe("Mia: Frage mit Vorschlag Urlaubstag", await tab.js(FRAGE),
             [True, "Fr 31.12.2027 (Silvester) liegt im Urlaub. Wie zählt der Tag?", ["urlaub*", "frei"]])
    await tab.bild("silvester_meine_zeiten_frage")
    p.pruefe("Mia: gesendet", await _senden(tab), "Antrag wurde gesendet.")
    await tab.warte_auf_ruhe()
    p.pruefe("Mia: Liste nennt den Urlaubstag", await tab.js(
        "[...document.querySelectorAll('[data-antrag-zeile]')].some(z=>z.innerText.includes('Mo 27.12.–Fr 31.12.2027 · Kalendertag als Urlaubstag'))"), True)
    p.pruefe("Mia: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-11 10:00"))
