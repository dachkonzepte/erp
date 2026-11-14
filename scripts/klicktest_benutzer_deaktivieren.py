"""Klicktest: „Deaktivieren“ statt „Löschen“ bei einem verwendeten Konto (1.9.342, Nachrunde V1, Punkt 2).

Testdaten: Anna Admin (angemeldet); Bea Büro (aktiv, hat eine Aufgabe angelegt), Carl Neu (aktiv, nie verwendet), Dora Alt (inaktiv, hat eine Aufgabe
angelegt), Eva Ernst (aktiv, hat eine Aufgabe angelegt -- bleibt aktiv, damit die Bilder „Deaktivieren“ zeigen).

    Anna          Bea und Eva: „Deaktivieren“ (Bea: title „Verwendet in: Aufgaben“), kein „Löschen“; Carl: „Löschen“, kein „Deaktivieren“; Dora und Anna
                  selbst: keins von beiden. „Deaktivieren“ bei Bea mit Rückfrage -> Bea „Inaktiv“, kein Knopf mehr; Rolle und Mitarbeiter unverändert (Server)
    Bilder        die Seite bei 1440 und 412 px, hell und dunkel (412: nichts läuft über die Seite hinaus, die Tabelle rollt in ihrem Rahmen)
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_benutzer_deaktivieren.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "document.querySelectorAll('#rows tr').length>=5&&!document.getElementById('rows').textContent.includes('Noch keine')"
KNOEPFE = ("[...document.querySelectorAll('#rows tr')].map(tr=>[tr.cells[0].textContent,[...tr.querySelectorAll('.actions button')]"
           ".map(b=>b.textContent).filter(t=>t==='Löschen'||t==='Deaktivieren').join('+')||'-'])")


def befuellen(db, k):
    from app.models import AppUser, Employee, Task

    bea_ma = Employee(employee_number="B-1", first_name="Bea", last_name="Büro", employee_group="kaufmaennisch", active=True)
    db.add(bea_ma)
    db.flush()
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", employee_id=bea_ma.id, password_hash=k.passwort())
    carl = AppUser(username="carl", display_name="Carl Neu", role="buero_auftrag", password_hash=k.passwort())
    dora = AppUser(username="dora", display_name="Dora Alt", role="field", active=False, password_hash=k.passwort())
    eva = AppUser(username="eva", display_name="Eva Ernst", role="buero_finanzen", password_hash=k.passwort())
    db.add_all([anna, bea, carl, dora, eva])
    db.flush()
    db.add_all([Task(title="Rückruf Kunde", created_by_user_id=bea.id), Task(title="Altlast", created_by_user_id=dora.id),
                Task(title="Mahnung prüfen", created_by_user_id=eva.id)])
    db.commit()
    return {"anna": k.cookies(anna), "bea_id": bea.id, "bea_ma": bea_ma.id}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=m=>true;")
    await tab.anmelden(seed["anna"])
    await tab.fenster(1440, 1000)
    await tab.oeffnen("/users", "true")
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Anna: Benutzer geladen", await tab.oeffnen("/users?n=1", BEREIT), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Knöpfe je Konto", await tab.js(KNOEPFE), [["anna", "-"], ["bea", "Deaktivieren"], ["carl", "Löschen"], ["dora", "-"], ["eva", "Deaktivieren"]])
    p.pruefe("Deaktivieren nennt, wo das Konto steht", await tab.js(
        "document.querySelector('[data-klick=\"deaktivieren\"]').title"), "Verwendet in: Aufgaben")
    await tab.warte_auf_neu_geladene_liste("document.querySelector('[data-klick=\"deaktivieren\"]').click()", "#rows")
    p.pruefe("nach Deaktivieren: Bea inaktiv, kein Knopf", await tab.js(
        "[...document.querySelectorAll('#rows tr')].filter(tr=>tr.cells[0].textContent==='bea').map(tr=>[tr.cells[4].textContent,"
        "tr.querySelectorAll('[data-klick=\"deaktivieren\"]').length])"), [["Inaktiv", 0]])
    p.pruefe("Rolle und Mitarbeiter unverändert (Server)", await tab.js(
        f"fetch('/api/users').then(r=>r.json()).then(l=>l.filter(u=>u.id==={seed['bea_id']}).map(u=>[u.role,u.employee_id,u.active]))"),
        [["buero_auftrag", seed["bea_ma"], False]])

    for breite, mobil in ((1440, False), (412, True)):
        await tab.fenster(breite, 1000, mobil=mobil)
        for thema, name in (("light", "hell"), ("dark", "dunkel")):
            await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
            p.pruefe(f"Bild {breite} {name}: geladen", await tab.oeffnen(f"/users?n=b{breite}{name}", BEREIT), True)
            await tab.warte_auf_ruhe()
            if mobil:
                p.pruefe(f"Bild {breite} {name}: nichts läuft über", await tab.ueberlauf(), [])
                # Die Tabelle rollt bei 412 px in ihrem Rahmen (wie bisher); fürs Bild nach rechts zu den Knöpfen und die Zeilen ins Bild.
                await tab.js("(()=>{const r=document.getElementById('rows');r.closest('div').scrollLeft=1e6;r.scrollIntoView({block:'center'})})()")
            await tab.bild(f"benutzer_deaktivieren_{breite}_{name}")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
