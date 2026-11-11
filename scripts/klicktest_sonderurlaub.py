"""Klicktest: die Kategorie „Sonderurlaub“ (1.9.313, Lohn L2b, Punkt 1; Antwort 3 des Befunds L2).

Stehende Uhr Mi 25.11.2026 10:00. Mia und Tom (gewerblich, Personalnummern erfunden); Anna (Admin), Fin (Büro – Finanzen), Mias Konto (Monteurin).
Eine selbst angelegte Art „Hochzeit“; genehmigter Sonderurlaub: Mia Mo 16.–Di 17.11. (Hochzeit), Tom Mi 18.11.; die Zuordnung „Kategorie Sonderurlaub“
ist leer (die Lohnart nennt das Steuerbüro).

    Abwesenheitsarten   Einstellungen → Abwesenheitsarten: je Art „Kategorie: …“ vom Server -- Urlaub „Urlaub“, Berufsschule „Fortbildung“, Hochzeit
                        „jede Kategorie“; der Satz „… auch zu Sonderurlaub (zählt nicht gegen den Urlaub)“; „Umzug“ hinzugefügt -> mit „Kategorie: jede
                        Kategorie“ ohne Neuladen; Bilder bei 1440 und 412 px, hell und dunkel (412: nichts läuft über)
    Zuordnung           Zeitregeln und DATEV: „Kategorie Sonderurlaub“ leer, „nicht exportiert“
    Zeiten              Abwesenheiten → „Abwesenheit eintragen“: Kategorie mit „Sonderurlaub“ nach „Urlaub“; Sonderurlaub gewählt -> Art ohne „Urlaub“, mit
                        Hochzeit, Umzug, Sonstiges; Bild des Dialogs. Prüfen → „Vor dem Abschluss“: „Sonderurlaub ohne Zuordnung: 3 Tage nicht in der
                        Lohndatei“ (ohne Namen); Bild
    Plantafel, Meine Zeiten   die Auswahl der Kategorie kennt Sonderurlaub
    überall             keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_sonderurlaub.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

ARTEN_BEREIT = ("typeof artenKategorien!=='undefined'&&artenKategorien.length>0&&document.querySelectorAll('#timeListRows [data-art-kategorie]').length>0"
                "&&document.getElementById('timeListHeading').textContent==='Abwesenheitsarten'")
ARTEN = ("[...document.querySelectorAll('#timeListRows tr')].map(tr=>[tr.cells[0].querySelector('b').innerText,"
         "(tr.cells[0].querySelector('[data-art-kategorie]')||{innerText:''}).innerText])")
ZEITEN_BEREIT = "!!window.A&&!!document.getElementById('abschlussListe')"
PRUEFEN_BEREIT = "!!window.P&&document.getElementById('monatTitel').textContent!==''&&document.querySelectorAll('#abschlussListe li').length>0"


def befuellen(db, k):
    from datetime import date

    from app.models import AppUser, Employee, EmployeeAbsence, EmployeePayrollSettings, SettingOption
    from app.option_settings import get_option_group

    mia = Employee(employee_number="M-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
    tom = Employee(employee_number="M-2", first_name="Tom", last_name="Monteur", employee_group="gewerblich", active=True)
    db.add_all([mia, tom])
    db.flush()
    for e, pnr in ((mia, "00091"), (tom, "00092")):
        db.add(EmployeePayrollSettings(employee_id=e.id, datev_personnel_number=pnr, export_umfang="alles", payroll_export_enabled=True))
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    mia_konto = AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id, password_hash=k.passwort())
    db.add_all([anna, fin, mia_konto])
    gruppe = get_option_group(db, "absence_types")
    db.add(SettingOption(group_id=gruppe.id, value="Hochzeit", label="Hochzeit", sort_order=70, active=True))
    db.add(EmployeeAbsence(employee_id=mia.id, absence_type="Hochzeit", absence_category="sonderurlaub", start_date=date(2026, 11, 16),
                           end_date=date(2026, 11, 17)))
    db.add(EmployeeAbsence(employee_id=tom.id, absence_type="Sonderurlaub", absence_category="sonderurlaub", start_date=date(2026, 11, 18),
                           end_date=date(2026, 11, 18)))
    db.commit()
    return {"anna": k.cookies(anna), "fin": k.cookies(fin), "mia": k.cookies(mia_konto), "uhr_ms": k.uhr_ms()}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.browser_uhr_fest(seed["uhr_ms"])  # dieselbe stehende Uhr wie die Instanz (Daten im Dialog)

    # ---- Einstellungen → Abwesenheitsarten ---------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["fin"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/settings#general", "!!document.getElementById('timeListRows')")
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Fin: Abwesenheitsarten geladen", await tab.oeffnen("/settings?n=1#absence-types", ARTEN_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Fin: je Art die Kategorie vom Server", await tab.js(ARTEN),
             [["Urlaub", "Kategorie: Urlaub"], ["Krankheit", "Kategorie: Krankheit"], ["Weiterbildung", "Kategorie: Fortbildung"],
              ["Berufsschule", "Kategorie: Fortbildung"], ["Freizeitausgleich", "Kategorie: Freizeitausgleich"], ["Sonstiges", "Kategorie: jede Kategorie"],
              ["Hochzeit", "Kategorie: jede Kategorie"]])
    p.pruefe("Fin: der Satz zu Sonderurlaub", await tab.js(
        "document.getElementById('timeListDescription').innerText.includes('eine selbst angelegte Art passt zu jeder Kategorie, auch zu Sonderurlaub "
        "(zählt nicht gegen den Urlaub).')"), True)
    await tab.js("document.getElementById('timeListLabel').value='Umzug';document.getElementById('timeListValue').value='Umzug';"
                 "document.getElementById('timeListSort').value='80'")
    await tab.warte_auf_neu_geladene_liste("saveTimeListOption()", "#timeListRows")
    p.pruefe("Fin: „Umzug“ mit Kategorie, ohne Neuladen", await tab.warten(
        "[...document.querySelectorAll('#timeListRows tr')].some(tr=>tr.cells[0].innerText.includes('Umzug')&&tr.cells[0].innerText.includes('Kategorie: jede Kategorie'))",
        10), True)
    n = 1
    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            n += 1
            p.pruefe(f"Arten {breite} {name}: geladen", await tab.oeffnen(f"/settings?n={n}#absence-types", ARTEN_BEREIT), True)
            await tab.warte_auf_ruhe()
            if mobil:
                p.pruefe(f"Arten 412 {name}: nichts läuft über", await tab.ueberlauf(), [])
            await tab.js("document.getElementById('settings-time-lists').scrollIntoView({block:'start'})")
            await tab.bild(f"abwesenheitsarten_sonderurlaub_{breite}_{name}")
    await tab.fenster(1440, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")

    # ---- Zuordnung -----------------------------------------------------------------------------------------------------------------------
    p.pruefe("Fin: Zeitregeln geladen", await tab.oeffnen("/settings?n=9#time-rules", "typeof lohnarten!=='undefined'&&lohnarten.length>0"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Fin: Zuordnung Sonderurlaub leer, nicht exportiert", await tab.js(
        "(()=>{const z=lohnarten.find(x=>x.schluessel==='kategorie:sonderurlaub');return [z.bezeichnung,z.kennzeichen,z.lohnart,z.wirkt]})()"),
        ["Kategorie Sonderurlaub", None, None, "nicht exportiert"])
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])

    # ---- Zeiten ------------------------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["anna"])
    p.pruefe("Anna: Zeiten geladen", await tab.oeffnen("/zeiten?n=1#abwesenheiten", ZEITEN_BEREIT), True)
    await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('abwNeu').click()")
    await tab.warten("document.getElementById('abwDialog').open", 5)
    p.pruefe("Anna: Kategorie mit Sonderurlaub nach Urlaub", await tab.js(
        "[...document.getElementById('adKategorie').options].map(o=>o.textContent)"),
        ["Urlaub", "Sonderurlaub", "Krankheit", "Fortbildung", "Unbezahlt", "Freizeitausgleich"])
    await tab.js("auswahlWert(document.getElementById('adKategorie'),'sonderurlaub');"
                 "document.getElementById('adKategorie').dispatchEvent(new Event('change',{bubbles:true}))")
    p.pruefe("Anna: Arten zu Sonderurlaub (ohne Urlaub)", await tab.js(
        "[...document.getElementById('adArt').options].map(o=>o.textContent)"), ["— ohne —", "Sonstiges", "Hochzeit", "Umzug"])
    await tab.bild("zeiten_abwesenheit_sonderurlaub_dialog")
    await tab.js("document.getElementById('abwDialog').close()")
    p.pruefe("Anna: Prüfen geladen", await tab.oeffnen("/zeiten?n=2", PRUEFEN_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Anna: „Vor dem Abschluss“ nennt Sonderurlaub ohne Zuordnung", await tab.js(
        "[...document.querySelectorAll('#abschlussListe li[data-art=zuordnung]')].map(l=>l.textContent.trim())"),
        ["Sonderurlaub ohne Zuordnung: 3 Tage nicht in der Lohndatei – keine Lohndatei, bis die Zuordnung steht"])  # seit 1.9.317 mit dem Zusatz
    await tab.js("document.getElementById('abschlussListe').scrollIntoView({block:'center'})")
    await tab.bild("zeiten_pruefen_sonderurlaub")
    # seit 1.9.317 (Nachrunde L2b, Punkt A): „Monat & Lohn“ -- die Zuordnung fehlt wie eine Personalnummer, mit dem Weg zu den Zeitregeln
    p.pruefe("Anna: Monat & Lohn", await tab.oeffnen("/zeiten?n=3#monat", "!!window.M&&document.getElementById('lohnMonat').innerText==='November 2026'"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Anna: Fehlt mit der Zuordnung, Zeile mit Weg", await tab.js(
        "[document.getElementById('lohnDatevFehlt').innerText,[...document.querySelectorAll('#lohnPruefen li')].filter(l=>l.innerText.includes('Zuordnung'))"
        ".map(l=>[l.querySelector('.text').innerText,l.querySelector('a').getAttribute('href')])]"),
        ["Fehlt: 1 Zuordnung, DATEV-Nummern", [["Sonderurlaub ohne Zuordnung: 3 Tage nicht in der Lohndatei – keine Lohndatei, bis die Zuordnung steht",
                                               "/settings#time-rules"]]])
    await tab.bild("zeiten_monat_ohne_zuordnung")
    p.pruefe("Anna: keine JS-Fehler", tab.fehler, [])

    # ---- Plantafel und Meine Zeiten ------------------------------------------------------------------------------------------------------
    p.pruefe("Anna: Plantafel kennt Sonderurlaub", await tab.oeffnen("/planning?n=1", "!!document.getElementById('absenceCategory')"), True)
    p.pruefe("Anna: Kategorie der Plantafel", await tab.js("[...document.getElementById('absenceCategory').options].map(o=>o.textContent)"),
             ["Urlaub", "Sonderurlaub", "Krankheit", "Fortbildung", "Unbezahlt", "Freizeitausgleich"])
    await tab.anmelden(seed["mia"])
    p.pruefe("Mia: Meine Zeiten", await tab.oeffnen("/mobil/zeiten?n=1", "!!document.getElementById('adKategorie')"), True)
    p.pruefe("Mia: Kategorie im Antrag", await tab.js("[...document.getElementById('adKategorie').options].map(o=>o.textContent.trim())"),
             ["Urlaub", "Sonderurlaub", "Krankheit", "Fortbildung", "Unbezahlt", "Freizeitausgleich"])
    p.pruefe("Mia: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-25 10:00"))
