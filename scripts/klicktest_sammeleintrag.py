"""Klicktest: Sammeleintrag und halbe Urlaubstage (1.9.171, Lohn L1a, Punkt 6, E9).

    Ada (Admin, 1440)       „Zeiten → Abwesenheiten“ -> „Abwesenheit beantragen“; „Für mehrere Personen“: Kolonne 1 hakt Mia und Tom an, „Alle“
                            alle drei; Urlaub Mo 28.12.–Mi 30.12.2026 für alle -> Kai hat dort schon Urlaub: Meldung mit seinem Namen, nichts
                            eingetragen; nur Kolonne 1 -> „Eingetragen für 2 Personen“; „Halber Tag“ nur bei Urlaub an einem Tag; Mia am 23.12. halber
                            Tag -> in der Liste „halber Tag · 0,5 Arbeitstage“; Urlaub 21.–24.12. zählt 3 (seit 1.9.175 ist der 24.12. für
                            gewerbliche Heiligabend im Arbeitszeitkalender; 1.9.174: 4, 1.9.171–1.9.173: 3,5) -- Bilder
    Fin (Büro – Finanzen)   seit 1.9.205: Kai und Tom 28.–30.12. -> beide schon abwesend, beide genannt, keine Anträge -- Bild; derselbe
                            Dialog für Kai im Januar -> „Anträge gesendet für …“ (offen, nicht genehmigt)
    Mia (Monteurin, 1280)   „Meine Zeiten“ -> „+ Antrag“: „Halber Tag“ bei Urlaub an einem Tag, nicht bei Krankheit
    überall                 keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_sammeleintrag.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD]
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


def befuellen(db, k):
    from datetime import date

    from app.absence_requests import create_request, review_request
    from app.models import AppUser, Employee, Team, TeamEmployee

    leute = {}
    for nr, (vor, nach) in enumerate([("Mia", "Monteurin"), ("Tom", "Monteur"), ("Kai", "Kolonne")], 1):
        leute[vor.lower()] = Employee(employee_number=f"E-{nr}", first_name=vor, last_name=nach, employee_group="gewerblich", active=True)
    db.add_all(leute.values()); db.flush()
    team = Team(team_number="K-1", name="Kolonne 1", active=True)
    db.add(team); db.flush()
    db.add_all([TeamEmployee(team_id=team.id, employee_id=leute["mia"].id), TeamEmployee(team_id=team.id, employee_id=leute["tom"].id)])
    benutzer = {
        "ada": AppUser(username="ada", display_name="Ada Admin", role="admin", password_hash=k.passwort()),
        "fin": AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort()),
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=leute["mia"].id, password_hash=k.passwort()),
    }
    db.add_all(benutzer.values())
    db.commit()
    kai = create_request(db, employee_id=leute["kai"].id, absence_category="urlaub", start_date=date(2026, 12, 29), end_date=date(2026, 12, 29))
    review_request(db, kai.id, decision="approved", reviewed_by_user_id=None)
    return {"cookies": {n: k.cookies(u) for n, u in benutzer.items()}, "ids": {n: e.id for n, e in leute.items()}}


async def _setze(tab, werte: dict):
    await tab.js(";".join(f"{{const f=document.getElementById('{i}');f.value={v!r};f.dispatchEvent(new Event('change'))}}" for i, v in werte.items()))


async def _dialog(tab):
    await tab.js("document.getElementById('abwNeu').click()")
    await tab.js("{const m=document.getElementById('adMehrere');m.checked=true;m.dispatchEvent(new Event('change'))}")


async def _senden(tab) -> str:
    await tab.js("document.getElementById('adStatus').textContent='';document.getElementById('adSenden').click()")
    await tab.warten("document.getElementById('adStatus').textContent!==''||!document.getElementById('abwDialog').open", 10)
    await tab.warte_auf_ruhe()
    return await tab.js("document.getElementById('abwDialog').open?document.getElementById('adStatus').textContent:document.getElementById('ergebnis').textContent")


GEHAKT = "[...document.querySelectorAll('[data-ad-person]:checked')].map(c=>c.parentElement.textContent.trim()).sort()"


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")

    await tab.anmelden(seed["cookies"]["ada"])
    await tab.fenster(1440, 900)
    p.pruefe("Ada: Abwesenheiten geladen", await tab.oeffnen("/zeiten#abwesenheiten", ZEITEN_BEREIT), True)
    await _dialog(tab)
    p.pruefe("Ada: mehrere Personen -- Kolonne und Personen statt einer Auswahl", await tab.js(
        "[document.getElementById('adMitarbeiterFeld').hidden,document.getElementById('adKolonneFeld').hidden,document.getElementById('adPersonenFeld').hidden]"),
        [True, False, False])
    await tab.js("{const s=document.getElementById('adKolonne');s.value=[...s.options].find(o=>o.text==='Kolonne 1').value;s.dispatchEvent(new Event('change'))}")
    p.pruefe("Ada: Kolonne 1 hakt Mia und Tom an", await tab.js(GEHAKT), ["Mia Monteurin", "Tom Monteur"])
    await tab.js("document.getElementById('adAlle').click()")
    p.pruefe("Ada: „Alle“ hakt alle an", await tab.js(GEHAKT), ["Kai Kolonne", "Mia Monteurin", "Tom Monteur"])
    await _setze(tab, {"adKategorie": "urlaub", "adVon": "2026-12-28", "adBis": "2026-12-30"})
    p.pruefe("Ada: „Halber Tag“ nicht bei drei Tagen", await tab.js("document.getElementById('adHalbFeld').hidden"), True)
    # seit 1.9.205 aus belegt(), mit dem Tag (bis 1.9.204 „… Kai Kolonne: Für diesen Mitarbeiter besteht im beantragten Zeitraum bereits eine
    # genehmigte Abwesenheit.“ -- beim Admin erst beim Genehmigen)
    p.pruefe("Ada: Kai schon im Urlaub -- nichts eingetragen", await _senden(tab), "Nicht eingetragen: Kai Kolonne: am 29.12.2026 bereits abwesend.")
    await tab.bild("sammeleintrag_abgelehnt")
    await tab.js("{const s=document.getElementById('adKolonne');s.value=[...s.options].find(o=>o.text==='Kolonne 1').value;s.dispatchEvent(new Event('change'))}")
    p.pruefe("Ada: nur Kolonne 1 eingetragen", await _senden(tab), "Eingetragen für 2 Personen, Mo 28.12.–Mi 30.12.2026")

    await _dialog(tab)
    await tab.js(f"document.querySelector('[data-ad-person=\"{seed['ids']['mia']}\"]').checked=true")
    await _setze(tab, {"adKategorie": "urlaub", "adVon": "2026-12-23", "adBis": "2026-12-23"})
    p.pruefe("Ada: „Halber Tag“ bei Urlaub an einem Tag", await tab.js("document.getElementById('adHalbFeld').hidden"), False)
    await _setze(tab, {"adKategorie": "krankheit"})
    p.pruefe("Ada: nicht bei Krankheit", await tab.js("document.getElementById('adHalbFeld').hidden"), True)
    await _setze(tab, {"adKategorie": "urlaub"})
    await tab.js("document.getElementById('adHalb').checked=true")
    p.pruefe("Ada: halber Tag eingetragen", await _senden(tab), "Eingetragen für 1 Person, Mi 23.12.2026")
    await _dialog(tab)
    await tab.js(f"document.querySelector('[data-ad-person=\"{seed['ids']['tom']}\"]').checked=true")
    await _setze(tab, {"adKategorie": "urlaub", "adVon": "2026-12-21", "adBis": "2026-12-24"})
    p.pruefe("Ada: Tom 21.–24.12. eingetragen", await _senden(tab), "Eingetragen für 1 Person, Mo 21.12.–Do 24.12.2026")
    await tab.warte_auf_neu_geladene_liste("abwesenheitenLaden()", "#abwListe")
    zeilen = await tab.js("[...document.querySelectorAll('#abwListe .zeile-unter')].map(z=>z.innerText.split(' · ').slice(0,3).join(' · '))")
    p.pruefe("Ada: halber Tag und 3 Arbeitstage in der Liste", ["Mi 23.12.2026 · halber Tag · 0,5 Arbeitstage" in zeilen,
                                                                "Mo 21.12.–Do 24.12.2026 · 3 Arbeitstage" in [" · ".join(z.split(" · ")[:2]) for z in zeilen]],
             [True, True])
    await tab.bild("sammeleintrag_liste")
    p.pruefe("Ada: keine JS-Fehler", tab.fehler, [])

    await tab.anmelden(seed["cookies"]["fin"])
    p.pruefe("Fin: geladen", await tab.oeffnen("/zeiten?als=fin#abwesenheiten", ZEITEN_BEREIT), True)
    # seit 1.9.205 (L1a Stufe 4, Punkt 4): auch bei Büro – Finanzen schon beim Anlegen geprüft (bis 1.9.204 zwei offene Anträge)
    await _dialog(tab)
    for wer in ("kai", "tom"):
        await tab.js(f"document.querySelector('[data-ad-person=\"{seed['ids'][wer]}\"]').checked=true")
    await _setze(tab, {"adKategorie": "urlaub", "adVon": "2026-12-28", "adBis": "2026-12-30"})
    p.pruefe("Fin: Kai und Tom schon abwesend -- beide genannt, keine Anträge", await _senden(tab),
             "Nicht eingetragen: Kai Kolonne: am 29.12.2026 bereits abwesend; Tom Monteur: vom 28.12. bis 30.12.2026 bereits abwesend.")
    await tab.bild("sammeleintrag_fin_abgelehnt")
    await tab.js("document.getElementById('abwDialog').close()")
    await _dialog(tab)
    await tab.js(f"document.querySelector('[data-ad-person=\"{seed['ids']['kai']}\"]').checked=true")
    await _setze(tab, {"adKategorie": "urlaub", "adVon": "2027-01-04", "adBis": "2027-01-05"})
    p.pruefe("Fin: Anträge gesendet", await _senden(tab), "Anträge gesendet für 1 Person, Mo 04.01.–Di 05.01.2027")
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])

    await tab.anmelden(seed["cookies"]["mia"])
    await tab.fenster(1280, 620)
    p.pruefe("Mia: Meine Zeiten geladen", await tab.oeffnen("/mobil/zeiten", MEINE_BEREIT), True)
    await tab.js("document.getElementById('antragKnopf').click()")
    p.pruefe("Mia: „Halber Tag“ bei Urlaub an einem Tag", await tab.js("document.getElementById('adHalbFeld').hidden"), False)
    await _setze(tab, {"adKategorie": "krankheit"})
    p.pruefe("Mia: nicht bei Krankheit", await tab.js("document.getElementById('adHalbFeld').hidden"), True)
    await _setze(tab, {"adKategorie": "urlaub"})
    await tab.bild("sammeleintrag_mia_halber_tag")
    p.pruefe("Mia: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-12-07 10:00"))
