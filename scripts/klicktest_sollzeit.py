"""Klicktest: Sollzeit, Eintritt und Austritt in Einstellungen → Zeitregeln und DATEV (1.9.167, Lohn L1a, Punkt 2, E3, E4, E10).

    Büro – Finanzen  Fin: Modelle „8,00 h/Tag Mo–Fr · KW 18–48“ und „7,50 h/Tag Mo–Fr · KW 49–17“; Mia in der Tabelle mit „Tarif“; Eintritt
                     05.11.2026 gespeichert (die Personalnummer bleibt); „Sollzeit ändern“: Dialog „Sollzeit – Mia Monteurin“ ohne eigene Werte,
                     ab 01.12.2026 Di, Mi, Do je 3,00 -> Liste und Tabelle „Di 3,00 · Mi 3,00 · Do 3,00 h“; ab 01.01.2027 „wieder Tarif“ -> zwei
                     Zeilen; die Tarif-Zeile gelöscht; „gültig ab“ im abgeschlossenen Zeitraum -> Meldung des Servers -- Bilder; keine JS-Fehler
    Büro – Auftrag   Bea: Hinweis „… ändern Admin und Büro – Finanzen – du kannst sie lesen.“, Felder gesperrt, kein Knopf zum Speichern, Sollzeit
                     als Text sichtbar; derselbe PUT vom Server 403 -- Bild; keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_sollzeit.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "typeof payroll!=='undefined'&&payroll.length>0&&!!document.querySelector('#payrollRows [data-sollzeit]')&&workModels.length>0"
ZEILEN = "[...document.querySelectorAll('#sollzeitZeilen tr')].map(tr=>[...tr.cells].map(c=>c.innerText.trim()))"


def befuellen(db, k):
    from app.models import AppUser, Employee, EmployeePayrollSettings, TimeTrackingSettings

    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    bea = AppUser(username="bea", display_name="Bea Auftrag", role="buero_auftrag", password_hash=k.passwort())
    mia = Employee(employee_number="M-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True)
    db.add_all([fin, bea, mia])
    db.flush()
    db.add(EmployeePayrollSettings(employee_id=mia.id, datev_personnel_number="91001", payroll_export_enabled=True))
    db.get(TimeTrackingSettings, 1).locked_until = date(2026, 10, 31)
    db.commit()
    return {"fin": k.cookies(fin), "bea": k.cookies(bea), "mia": mia.id}


def _zelle(seed):
    return f"document.querySelector('[data-sollzeit=\"{seed['mia']}\"]').innerText.replace(/\\s+/g,' ').trim()"


async def _setze(tab, werte: dict):
    js = ";".join(f"document.getElementById('{i}').value={v!r}" for i, v in werte.items())
    await tab.js(js)


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    mia = seed["mia"]

    # ---- Büro – Finanzen ---------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["fin"])
    p.pruefe("Fin: Zeitregeln und DATEV geladen", await tab.oeffnen("/settings#time-rules", BEREIT), True)
    p.pruefe("Fin: Modelle mit Tarif", await tab.js(
        "[...document.querySelectorAll('#workModelCards .model-card .muted')].map(d=>d.innerText.split(' · ').slice(0,2).join(' · '))"),
        ["8,00 h/Tag Mo–Fr · KW 18–48", "7,50 h/Tag Mo–Fr · KW 49–17"])
    p.pruefe("Fin: Mia mit Tarif, kein Hinweis „nur lesen“", await tab.js(
        f"[{_zelle(seed)},!!document.querySelector('[data-lohnregeln-hinweis]')]"), ["Tarif Sollzeit ändern", False])
    await _setze(tab, {f"pein-{mia}": "2026-11-05"})
    await tab.warte_auf_neu_geladene_liste(f"document.querySelector('[data-klick=lohn-speichern][data-mitarbeiter=\"{mia}\"]').click()", "#payrollRows")
    p.pruefe("Fin: Eintritt gespeichert, Personalnummer bleibt", await tab.js(
        "fetch('/api/time-backoffice/payroll-employees').then(r=>r.json()).then(l=>l.map(x=>[x.datev_personnel_number,x.eintritt,x.austritt]))"),
        [["91001", "2026-11-05", None]])

    await tab.js(f"document.querySelector('[data-klick=sollzeit-oeffnen][data-mitarbeiter=\"{mia}\"]').click()")
    p.pruefe("Fin: Dialog ohne eigene Werte", await tab.warten(
        "document.getElementById('sollzeitDialog').open&&document.querySelector('#sollzeitZeilen td')&&"
        "document.querySelector('#sollzeitZeilen td').innerText==='Keine eigenen Werte – es gilt der Tarif.'", 10), True)
    p.pruefe("Fin: Titel und Vorbelegung Mo–Fr 8,00", await tab.js(
        "[document.getElementById('sollzeitTitel').innerText,['Montag','Freitag','Samstag'].map(t=>document.getElementById('sz'+t).value)]"),
        ["Sollzeit – Mia Monteurin", ["8,00", "8,00", "0,00"]])
    await _setze(tab, {"szAb": "2026-12-01", "szMontag": "0", "szDienstag": "3", "szMittwoch": "3", "szDonnerstag": "3", "szFreitag": "0"})
    await tab.warte_auf_neu_geladene_liste("saveSollzeit()", "#sollzeitZeilen")
    p.pruefe("Fin: Di–Do 3,00 ab 01.12.2026 in Liste und Tabelle", [await tab.js(ZEILEN), await tab.js(_zelle(seed))],
             [[["01.12.2026", "Di 3,00 · Mi 3,00 · Do 3,00 h", "Löschen"]], "ab 01.12.2026: Di 3,00 · Mi 3,00 · Do 3,00 h Sollzeit ändern"])
    await tab.bild("sollzeit_dialog_teilzeit")
    await _setze(tab, {"szAb": "2027-01-01", "szArt": "tarif"})
    await tab.js("szArtGeaendert()")
    p.pruefe("Fin: „wieder Tarif“ blendet die Wochentage aus", await tab.js("document.getElementById('szTage').hidden"), True)
    await tab.warte_auf_neu_geladene_liste("saveSollzeit()", "#sollzeitZeilen")
    p.pruefe("Fin: zwei Zeilen", await tab.js(ZEILEN),
             [["01.12.2026", "Di 3,00 · Mi 3,00 · Do 3,00 h", "Löschen"], ["01.01.2027", "Tarif", "Löschen"]])
    await tab.warte_auf_neu_geladene_liste("document.querySelectorAll('#sollzeitZeilen [data-klick=sollzeit-loeschen]')[1].click()", "#sollzeitZeilen")
    p.pruefe("Fin: Tarif-Zeile gelöscht", await tab.js(ZEILEN), [["01.12.2026", "Di 3,00 · Mi 3,00 · Do 3,00 h", "Löschen"]])
    await _setze(tab, {"szAb": "2026-10-15", "szArt": "eigen"})
    await tab.js("szArtGeaendert();document.getElementById('sollzeitStatus').textContent=''")
    await tab.js("saveSollzeit()")
    p.pruefe("Fin: im abgeschlossenen Zeitraum abgelehnt", await tab.warten(
        "document.getElementById('sollzeitStatus').textContent.includes('abgeschlossen bis 31.10.2026')", 10), True)
    await tab.bild("sollzeit_dialog_abgeschlossen")
    await tab.js("document.getElementById('sollzeitDialog').close()")
    await tab.js(f"document.querySelector('[data-sollzeit=\"{mia}\"]').scrollIntoView({{block:'center'}})")
    await tab.bild("sollzeit_tabelle_fin")
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])

    # ---- Büro – Auftrag: liest nur ---------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["bea"])
    p.pruefe("Bea: geladen", await tab.oeffnen("/settings?als=bea#time-rules", BEREIT), True)
    p.pruefe("Bea: Hinweis, Felder gesperrt, keine Knöpfe, Sollzeit als Text", await tab.js(
        "[document.querySelector('[data-lohnregeln-hinweis]').innerText,"
        f"document.getElementById('pein-{mia}').disabled,document.getElementById('rounding').disabled,"
        "[...document.querySelectorAll('#settings-time-rules [data-lohnregeln-knopf]')].every(k=>k.hidden),"
        f"{_zelle(seed)}]"),
        ["Arbeitszeitmodelle, Pausenregeln, Sollzeiten und Personalnummern ändern Admin und Büro – Finanzen – du kannst sie lesen.", True, True,
         True, "ab 01.12.2026: Di 3,00 · Mi 3,00 · Do 3,00 h"])
    p.pruefe("Bea: PUT vom Server abgelehnt", await tab.js(
        f"fetch('/api/time-backoffice/payroll-employees/{mia}',{{method:'PUT',headers:{{'Content-Type':'application/json'}},"
        "body:JSON.stringify({austritt:'2027-06-30'})}).then(r=>r.status)"), 403)
    await tab.js(f"document.querySelector('[data-sollzeit=\"{mia}\"]').scrollIntoView({{block:'center'}})")
    await tab.bild("sollzeit_tabelle_bea")
    p.pruefe("Bea: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
