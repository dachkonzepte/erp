"""Klicktest: das Urlaubskonto auf den Seiten (1.9.316, Lohn L2b, Punkt 4).

Stehende Uhr Mi 25.11.2026 10:00 (Server und Browser): das laufende Jahr der Konten ist 2027. Mia (gewerblich, Startwert Resturlaub 4,5, genehmigter
Urlaub Mo 04.–Fr 08.01.2027), Tom (gewerblich, ohne Startwert, offener Antrag Mo 12.–Fr 16.04.2027), Ute (inaktiv, Urlaub Mo 11.01.2027); Anna (Admin), Fin
(Büro – Finanzen), Mias Konto (Monteurin); Kolonne „Nord“ mit Mia und Tom.

    Zeiten          Abwesenheiten: Karte „Urlaubskonto“ 2027 -- Mia 30 (Vorgabe) · 4,5 · 5 · 0 · 5 · 0 · 29,5 · 29,5; Tom 30 · 0 · … · 5 beantragt · 30 · 25
                    mit „ohne Übertrag – Startwert folgt“; Ute ausgeblendet, „1 inaktiv“; Haken ab -> Ute grau (nach dem Neuladen gemerkt); Jahr 2028 ->
                    Mia mit Übertrag 0 (von Hand, leer); Toms Antrag mit „danach Rest 25 Tage“; Dialog: Mia 01.–05.02.2027 -> „5 Urlaubstage · danach Rest
                    24,5 Tage“, Krankheit -> weg; Bilder der Karte und des Antrags bei 1440 und 412 px, hell und dunkel (412: nichts läuft über)
    Genehmigen      Anna in „Prüfen“: Toms Antrag mit „danach Rest 25 Tage“; unter „Abwesenheiten“ genehmigt -> ohne Neuladen Toms Konto genehmigt 5,
                    Rest 25
    Plantafel       „Abwesenheit eintragen“: Mia 01.–05.03.2027 -> „5 Urlaubstage · danach Rest 24,5 Tage“
    Meine Zeiten    Mia: Karte „Abwesenheit“ mit „Urlaub 2027“, Rest 29,5 …; Antrag 01.–05.03.2027 -> „danach Rest 24,5 Tage“; Bilder der Karte und des
                    Antrags bei 412 und 1440 px, hell und dunkel
    ohne Startwert  (seit 1.9.318) Tom in „Meine Zeiten“: das Konto mit „ohne Übertrag – Startwert folgt“, im Antrag „5 Urlaubstage · danach Rest 20 Tage ·
                    ohne Übertrag – Startwert folgt“; Bilder bei 412 px, hell und dunkel
    überall         keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_urlaubskonto.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

ZEITEN = "!!window.P&&document.getElementById('monatTitel').textContent!==''"
KONTO_BEREIT = "!!window.UK&&!!window.A&&!document.getElementById('ukKarte').hidden"
UK_ZEILEN = ("[...document.querySelectorAll('#ukZeilen tr')].map(tr=>[...tr.cells].map(c=>c.innerText.trim().replace(/\\s+/g,' ')))")
PLANTAFEL = "typeof board!=='undefined'&&board&&board.teams&&board.teams.length>0"
MEINE = "!document.getElementById('tage').classList.contains('laedt')&&document.getElementById('monatName').textContent!==''"


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.models import AppUser, Employee, EmployeeAbsence, EmployeeAbsenceRequest, LohnStartwert, Team, TeamEmployee

    mia = Employee(employee_number="M-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
    tom = Employee(employee_number="M-2", first_name="Tom", last_name="Monteur", employee_group="gewerblich", active=True)
    ute = Employee(employee_number="M-9", first_name="Ute", last_name="Ehemalig", employee_group="gewerblich", active=False)
    db.add_all([mia, tom, ute])
    db.flush()
    team = Team(name="Nord", active=True)
    db.add(team)
    db.flush()
    db.add_all([TeamEmployee(team_id=team.id, employee_id=mia.id), TeamEmployee(team_id=team.id, employee_id=tom.id)])
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    mia_konto = AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id, password_hash=k.passwort())
    tom_konto = AppUser(username="tom", display_name="Tom Monteur", role="field", employee_id=tom.id, password_hash=k.passwort())  # seit 1.9.318
    db.add_all([anna, fin, mia_konto, tom_konto])
    db.add(LohnStartwert(employee_id=mia.id, stichtag=date(2026, 12, 31), resturlaub_tage=Decimal("4.5"), saldo_stunden=Decimal("0"), herkunft="steuerbuero"))
    db.add(EmployeeAbsence(employee_id=mia.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2027, 1, 4), end_date=date(2027, 1, 8)))
    db.add(EmployeeAbsence(employee_id=ute.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2027, 1, 11), end_date=date(2027, 1, 11)))
    db.add(EmployeeAbsenceRequest(employee_id=tom.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2027, 4, 12),
                                  end_date=date(2027, 4, 16), status="pending"))
    db.commit()
    return {"anna": k.cookies(anna), "fin": k.cookies(fin), "mia": k.cookies(mia_konto), "tom": k.cookies(tom_konto), "mia_id": mia.id, "uhr_ms": k.uhr_ms()}


async def _eingeben(tab, feld: str, wert: str):
    await tab.js(f"(()=>{{const f=document.getElementById('{feld}');f.value={json.dumps(wert)};f.dispatchEvent(new Event('change',{{bubbles:true}}))}})()")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.browser_uhr_fest(seed["uhr_ms"])

    # ---- Zeiten → Abwesenheiten (Büro – Finanzen) ------------------------------------------------------------------------------------------
    await tab.anmelden(seed["fin"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/zeiten", ZEITEN)
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Fin: Abwesenheiten mit Konto", await tab.oeffnen("/zeiten?n=1#abwesenheiten", KONTO_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Fin: Konto 2027, Ute ausgeblendet", [await tab.js("[document.getElementById('ukJahr').value,document.getElementById('ukInaktivZahl').textContent,"
                                                            "document.getElementById('ukInaktive').checked]"), await tab.js(UK_ZEILEN)],
             [["2027", "1 inaktiv", True],
              [["Tom Monteur ohne Übertrag – Startwert folgt", "30 (Vorgabe)", "0", "0", "0", "0", "5", "30", "25"],  # nach Nachnamen: Monteur, Monteurin
               ["Mia Monteurin", "30 (Vorgabe)", "4,5", "5", "0", "5", "0", "29,5", "29,5"]]])
    p.pruefe("Fin: Toms Antrag mit „danach Rest“", await tab.js(
        "[...document.querySelectorAll('#abwListe .zeile')].map(z=>z.innerText).join(' | ').includes('danach Rest 25 Tage')"), True)
    await tab.js("document.getElementById('ukInaktive').click()")
    p.pruefe("Fin: Ute gezeigt, grau", await tab.js(
        "[[...document.querySelectorAll('#ukZeilen tr')].map(tr=>tr.className),getComputedStyle(document.querySelector('#ukZeilen tr.inaktiv td')).color"
        "!==getComputedStyle(document.querySelector('#ukZeilen tr:not(.inaktiv) td')).color]"),
        [["uk-zeile", "uk-zeile", "uk-zeile inaktiv"], True])
    p.pruefe("Fin: nach dem Neuladen gemerkt", await tab.oeffnen("/zeiten?n=2#abwesenheiten", KONTO_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Fin: Ute weiter gezeigt", await tab.js("[document.getElementById('ukInaktive').checked,document.querySelectorAll('#ukZeilen tr').length]"),
             [False, 3])
    await tab.js("document.getElementById('ukInaktive').click()")
    await tab.warte_auf_neu_geladene_liste("(()=>{const s=document.getElementById('ukJahr');s.value='2028';s.dispatchEvent(new Event('change'))})()", "#ukZeilen")
    p.pruefe("Fin: Jahr 2028 -- Übertrag von Hand, leer", [z[:3] for z in await tab.js(UK_ZEILEN)],
             [["Tom Monteur", "30 (Vorgabe)", "0"], ["Mia Monteurin", "30 (Vorgabe)", "0"]])
    await tab.warte_auf_neu_geladene_liste("(()=>{const s=document.getElementById('ukJahr');s.value='2027';s.dispatchEvent(new Event('change'))})()", "#ukZeilen")
    # Dialog „danach Rest“
    await tab.js("document.getElementById('abwNeu').click()")
    await tab.warten("document.getElementById('abwDialog').open", 5)
    await tab.js(f"document.getElementById('adMitarbeiter').value='{seed['mia_id']}'")
    await _eingeben(tab, "adVon", "2027-02-01")
    await _eingeben(tab, "adBis", "2027-02-05")
    p.pruefe("Fin: im Dialog „danach Rest“", await tab.warten(
        "!document.getElementById('adRest').hidden&&document.getElementById('adRest').textContent==='5 Urlaubstage · danach Rest 24,5 Tage'", 10), True)
    await tab.js("(()=>{const s=document.getElementById('adKategorie');s.value='krankheit';s.dispatchEvent(new Event('change'))})()")
    p.pruefe("Fin: Krankheit -- kein Rest", await tab.warten("document.getElementById('adRest').hidden", 10), True)
    await tab.js("document.getElementById('abwDialog').close()")
    n = 2
    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            n += 1
            p.pruefe(f"Bild {breite} {name}: geladen", await tab.oeffnen(f"/zeiten?n={n}#abwesenheiten", KONTO_BEREIT), True)
            await tab.warte_auf_ruhe()
            if mobil:
                p.pruefe(f"Bild 412 {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.js("document.getElementById('ukKarte').scrollIntoView({block:'start'})")
            await tab.bild(f"zeiten_abwesenheiten_urlaubskonto_{breite}_{name}")
            # der Antrag mit „danach Rest“
            await tab.js("document.getElementById('abwNeu').click()")
            await tab.warten("document.getElementById('abwDialog').open", 5)
            await tab.js(f"document.getElementById('adMitarbeiter').value='{seed['mia_id']}'")
            await _eingeben(tab, "adVon", "2027-02-01")
            await _eingeben(tab, "adBis", "2027-02-05")
            p.pruefe(f"Bild {breite} {name}: Antrag mit Rest", await tab.warten(
                "document.getElementById('adRest').textContent==='5 Urlaubstage · danach Rest 24,5 Tage'", 10), True)
            await tab.bild(f"zeiten_antrag_danach_rest_{breite}_{name}")
            await tab.js("document.getElementById('abwDialog').close()")
    await tab.fenster(1440, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])

    # ---- Genehmigen (Admin) --------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["anna"])
    p.pruefe("Anna: Prüfen", await tab.oeffnen("/zeiten?n=20", ZEITEN), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Anna: Toms Antrag mit „danach Rest“", await tab.js(
        "[...document.querySelectorAll('#antragListe .zeile-unter')].map(z=>z.innerText).join(' | ').includes('danach Rest 25 Tage')"), True)
    await tab.bild("zeiten_pruefen_antrag_danach_rest")
    # unter „Abwesenheiten“ genehmigt: das Konto zieht ohne Neuladen nach (abwesenheitenUndPruefen() lädt es mit)
    await tab.js("document.querySelector('.reiter a[data-reiter=abwesenheiten]').click()")
    p.pruefe("Anna: Abwesenheiten mit Konto", await tab.warten(KONTO_BEREIT + "&&document.querySelectorAll('#ukZeilen tr').length===2", 10), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Anna: Tom vorher", [z[3] for z in await tab.js(UK_ZEILEN) if z[0].startswith("Tom")], ["0"])
    await tab.warte_auf_neu_geladene_liste("document.querySelector('#abwListe [data-aktion=abw-entscheiden][data-entscheidung=approved]').click()", "#ukZeilen")
    p.pruefe("Anna: Toms Zeile ohne Neuladen -- genehmigt 5, Rest 25", await tab.warten(
        "[...document.querySelectorAll('#ukZeilen tr')].some(tr=>tr.innerText.startsWith('Tom')&&tr.cells[3].innerText.trim()==='5')", 10), True)
    p.pruefe("Anna: Toms Zeile", [z for z in await tab.js(UK_ZEILEN) if z[0].startswith("Tom")],
             [["Tom Monteur ohne Übertrag – Startwert folgt", "30 (Vorgabe)", "0", "5", "0", "5", "0", "25", "25"]])
    # ---- Plantafel ---------------------------------------------------------------------------------------------------------------------
    p.pruefe("Anna: Plantafel", await tab.oeffnen("/planning?n=1", PLANTAFEL), True)
    await tab.js("void openAbsences()")
    await tab.warten("document.getElementById('absenceDialog').open", 10)
    await _eingeben(tab, "absenceEmployee", str(seed["mia_id"]))
    await _eingeben(tab, "absenceStart", "2027-03-01")
    await _eingeben(tab, "absenceEnd", "2027-03-05")
    p.pruefe("Anna: Plantafel „danach Rest“", await tab.warten(
        "!document.getElementById('absenceRest').hidden&&document.getElementById('absenceRest').textContent==='5 Urlaubstage · danach Rest 24,5 Tage'", 10), True)
    await tab.bild("plantafel_abwesenheit_danach_rest")
    await tab.js("absenceDialog.close()")
    p.pruefe("Anna: keine JS-Fehler", tab.fehler, [])

    # ---- Meine Zeiten (Monteurin) ------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["mia"])
    n = 30
    for breite, hoehe, mobil in ((412, 900, True), (1440, 1000, False)):
        await tab.fenster(breite, hoehe, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            n += 1
            p.pruefe(f"Mia {breite} {name}: Meine Zeiten", await tab.oeffnen(f"/mobil/zeiten?n={n}", MEINE), True)
            await tab.warte_auf_ruhe()
            if mobil:
                p.pruefe(f"Mia 412 {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.js("document.getElementById('abwesenheitKarte').scrollIntoView({block:'start'})")
            await tab.bild(f"meine_zeiten_urlaub_{breite}_{name}")
            await tab.js("document.getElementById('antragKnopf').click()")
            await tab.warten("document.getElementById('abwDialog').open", 5)
            await _eingeben(tab, "adVon", "2027-03-01")
            await _eingeben(tab, "adBis", "2027-03-05")
            p.pruefe(f"Mia {breite} {name}: Antrag mit Rest", await tab.warten(
                "document.getElementById('adRest').textContent==='5 Urlaubstage · danach Rest 24,5 Tage'", 10), True)
            await tab.bild(f"meine_zeiten_antrag_danach_rest_{breite}_{name}")
            await tab.js("document.getElementById('abwDialog').close()")
    p.pruefe("Mia: das eigene Konto", await tab.js("document.getElementById('ukEigen').innerText.replace(/\\s+/g,' ').trim()"),
             "Urlaub 2027 Rest 29,5 Anspruch 30 Übertrag 4,5 Genehmigt 5 davon vorbei 0 Beantragt 0 Rest nach den offenen Anträgen 29,5")
    await tab.js("document.getElementById('antragKnopf').click()")
    await tab.warten("document.getElementById('abwDialog').open", 5)
    await _eingeben(tab, "adVon", "2027-03-01")
    await _eingeben(tab, "adBis", "2027-03-05")
    p.pruefe("Mia: im Antrag „danach Rest“", await tab.warten(
        "!document.getElementById('adRest').hidden&&document.getElementById('adRest').textContent==='5 Urlaubstage · danach Rest 24,5 Tage'", 10), True)
    p.pruefe("Mia: fremder Mitarbeiter vom Server abgelehnt (403)", await tab.js(
        f"fetch('/api/absence-requests/rest-danach?employee_id={seed['mia_id'] + 1}&von=2027-03-01&bis=2027-03-05').then(r=>r.status)"), 403)
    p.pruefe("Mia: keine JS-Fehler", tab.fehler, [])

    # ---- seit 1.9.318 (Nachrunde L2b, Punkt B): „Meine Zeiten“ ohne Startwert -- Tom (sein Antrag ist oben genehmigt: Rest 25) --------------------
    await tab.anmelden(seed["tom"])
    await tab.fenster(412, 900, mobil=True)
    n = 40
    for thema, name in (("light", "hell"), ("dark", "dunkel")):
        await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
        n += 1
        p.pruefe(f"Tom 412 {name}: Meine Zeiten", await tab.oeffnen(f"/mobil/zeiten?n={n}", MEINE), True)
        await tab.warte_auf_ruhe()
        p.pruefe(f"Tom 412 {name}: das Konto mit dem Hinweis", await tab.js("document.getElementById('ukEigen').innerText.replace(/\\s+/g,' ').trim()"),
                 "Urlaub 2027 Rest 25 Anspruch 30 Übertrag 0 Genehmigt 5 davon vorbei 0 Beantragt 0 Rest nach den offenen Anträgen 25 "
                 "ohne Übertrag – Startwert folgt")
        p.pruefe(f"Tom 412 {name}: nichts läuft über", await tab.ueberlauf(), [])
        await tab.js("document.getElementById('abwesenheitKarte').scrollIntoView({block:'start'})")
        await tab.bild(f"meine_zeiten_ohne_startwert_412_{name}")
        await tab.js("document.getElementById('antragKnopf').click()")
        await tab.warten("document.getElementById('abwDialog').open", 5)
        await _eingeben(tab, "adVon", "2027-03-01")
        await _eingeben(tab, "adBis", "2027-03-05")
        p.pruefe(f"Tom 412 {name}: im Antrag „danach Rest“ mit dem Hinweis", await tab.warten(
            "document.getElementById('adRest').textContent==='5 Urlaubstage · danach Rest 20 Tage · ohne Übertrag – Startwert folgt'", 10), True)
        await tab.bild(f"meine_zeiten_ohne_startwert_antrag_412_{name}")
        await tab.js("document.getElementById('abwDialog').close()")
    p.pruefe("Tom: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-25 10:00"))
