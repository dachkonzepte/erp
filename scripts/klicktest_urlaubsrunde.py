"""Klicktest: die Urlaubsrunde (ab 1.9.365) -- anteiliger Anspruch im Urlaubskonto.

Stehende Uhr Mi 10.02.2027 10:00 (Server und Browser). Nea (Helferin, Eintritt 01.08.2027, Anspruch 2027 26 Tage), Wim (Austritt 31.05.2027, Vorgabe
30, Startwert Resturlaub 0), Mia (ganzes Jahr, Vorgabe 30, Startwert Resturlaub 4,5); Fin (Büro – Finanzen), Bea (Büro – Auftrag, Konto ohne Mitarbeiter).

    Anspruch prüfen   (1.9.365) Zeiten → Abwesenheiten, Karte „Urlaubskonto“ 2027: Nea „Anspruch prüfen“ mit „Vorschlag 11 Tage: 26 ÷ 12 × 5 = 10,8 → 11 ·
                      5 volle Monate (01.08.2027–31.12.2027)“ und „Vorschlag übernehmen“; Wim „30 ÷ 12 × 5 = 12,5 → 12,5“; Mia ohne Vorschlag; Bilder der
                      Karte bei 1440 und 412 px, hell und dunkel (412: nichts läuft über); „Vorschlag übernehmen“ bei Nea -> ohne Neuladen Anspruch 11,
                      „Anspruch anteilig: 26 ÷ 12 × 5 = 10,8 → 11“, kein Knopf mehr; Bea sieht keine Konten anderer und keinen Knopf
    Übertrag zuerst   (1.9.366) Mia (Übertrag 4,5, genehmigter Urlaub 01.–02.02.2027): „davon Übertrag noch 2,5 Tage, verfällt am 31.03.2027“; Dialog für
                      Mia 01.–02.03.2027: „2 Urlaubstage · danach Rest 30,5 Tage · davon Übertrag noch 0,5 Tage, verfällt am 31.03.2027“
    überall           keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_urlaubsrunde.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

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
NEA = "[...document.querySelectorAll('#ukZeilen tr')].find(tr=>tr.innerText.includes('Nea'))"


def befuellen(db, k):
    from datetime import date
    from decimal import Decimal

    from app.models import AppUser, Employee, EmployeeAbsence, EmployeePayrollSettings, LohnStartwert, Urlaubsanspruch

    nea = Employee(employee_number="M-1", first_name="Nea", last_name="Neu", employee_group="gewerblich", active=True)
    wim = Employee(employee_number="M-2", first_name="Wim", last_name="Weg", employee_group="gewerblich", active=True)
    mia = Employee(employee_number="M-3", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
    db.add_all([nea, wim, mia])
    db.flush()
    db.add_all([EmployeePayrollSettings(employee_id=nea.id, eintritt=date(2027, 8, 1)),
                EmployeePayrollSettings(employee_id=wim.id, eintritt=date(2019, 4, 1), austritt=date(2027, 5, 31)),
                EmployeePayrollSettings(employee_id=mia.id, eintritt=date(2018, 3, 1)),
                Urlaubsanspruch(employee_id=nea.id, jahr=2027, urlaubstage=Decimal("26")),
                LohnStartwert(employee_id=mia.id, stichtag=date(2026, 12, 31), resturlaub_tage=Decimal("4.5"), saldo_stunden=Decimal("0"), herkunft="steuerbuero"),
                LohnStartwert(employee_id=wim.id, stichtag=date(2026, 12, 31), resturlaub_tage=Decimal("0"), saldo_stunden=Decimal("0"), herkunft="steuerbuero"),
                # seit 1.9.366: genehmigter Urlaub vor dem Verfall -- verbraucht zuerst den Übertrag
                EmployeeAbsence(employee_id=mia.id, absence_type="Urlaub", absence_category="urlaub", start_date=date(2027, 2, 1), end_date=date(2027, 2, 2))])
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    db.add_all([fin, bea])
    db.commit()
    return {"fin": k.cookies(fin), "bea": k.cookies(bea), "nea_id": nea.id, "mia_id": mia.id, "uhr_ms": k.uhr_ms()}


async def _eingeben(tab, feld: str, wert: str):
    await tab.js(f"(()=>{{const f=document.getElementById('{feld}');f.value={json.dumps(wert)};f.dispatchEvent(new Event('change',{{bubbles:true}}))}})()")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.browser_uhr_fest(seed["uhr_ms"])

    # ---- 1.9.365: Anspruch prüfen mit Vorschlag (Büro – Finanzen) --------------------------------------------------------------------------
    await tab.anmelden(seed["fin"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/zeiten", ZEITEN)
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Fin: Abwesenheiten mit Konto", await tab.oeffnen("/zeiten?n=1#abwesenheiten", KONTO_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Fin: Konto 2027 mit Vorschlägen", [z[:2] for z in await tab.js(UK_ZEILEN)], [
        ["Mia Monteurin davon Übertrag noch 2,5 Tage, verfällt am 31.03.2027", "30 (Vorgabe)"],  # seit 1.9.366
        ["Nea Neu Anspruch prüfen Vorschlag 11 Tage: 26 ÷ 12 × 5 = 10,8 → 11 · 5 volle Monate (01.08.2027–31.12.2027) Vorschlag übernehmen", "26"],
        ["Wim Weg Anspruch prüfen Vorschlag 12,5 Tage: 30 ÷ 12 × 5 = 12,5 → 12,5 · 5 volle Monate (01.01.2027–31.05.2027) Vorschlag übernehmen",
         "30 (Vorgabe)"]])
    n = 1
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
            await tab.bild(f"anspruch_pruefen_vorschlag_{breite}_{name}")
    await tab.fenster(1440, 1000)
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Fin: neu geladen", await tab.oeffnen("/zeiten?n=10#abwesenheiten", KONTO_BEREIT), True)
    await tab.warte_auf_ruhe()
    await tab.warte_auf_neu_geladene_liste(f"{NEA}.querySelector('[data-aktion=uk-anteilig]').click()", "#ukZeilen")
    p.pruefe("Fin: Nea übernommen, ohne Neuladen", await tab.js(f"[{NEA}.cells[0].innerText.replace(/\\s+/g,' ').trim(),{NEA}.cells[1].innerText.trim(),"
                                                               f"!!{NEA}.querySelector('[data-aktion=uk-anteilig]'),document.getElementById('ergebnis').textContent]"),
             ["Nea Neu Anspruch anteilig: 26 ÷ 12 × 5 = 10,8 → 11", "11", False, "Anspruch übernommen."])
    p.pruefe("Fin: nach dem Neuladen bleibt es", await tab.oeffnen("/zeiten?n=11#abwesenheiten", KONTO_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Fin: Nea 11 Tage", await tab.js(f"{NEA}.cells[1].innerText.trim()"), "11")
    # ---- 1.9.366: Übertrag zuerst -- „danach Rest“ im Dialog -------------------------------------------------------------------------------
    await tab.js("document.getElementById('abwNeu').click()")
    await tab.warten("document.getElementById('abwDialog').open", 5)
    await _eingeben(tab, "adMitarbeiter", str(seed["mia_id"]))
    await _eingeben(tab, "adVon", "2027-03-01")
    await _eingeben(tab, "adBis", "2027-03-02")
    p.pruefe("Fin: „danach Rest“ mit dem Übertrag", await tab.warten(
        "document.getElementById('adRest').textContent==='2 Urlaubstage · danach Rest 30,5 Tage · davon Übertrag noch 0,5 Tage, verfällt am 31.03.2027'", 10),
        True)
    await tab.js("document.getElementById('abwDialog').close()")
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])

    # ---- Büro – Auftrag: kein Konto anderer, kein Knopf --------------------------------------------------------------------------------------
    await tab.anmelden(seed["bea"])
    p.pruefe("Bea: Abwesenheiten", await tab.oeffnen("/zeiten?n=20#abwesenheiten", KONTO_BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Bea: keine Konten anderer, kein Knopf", await tab.js(
        "[document.querySelectorAll('#ukZeilen tr').length,document.querySelectorAll('[data-aktion=uk-anteilig]').length]"), [0, 0])
    p.pruefe("Bea: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2027-02-10 10:00"))
