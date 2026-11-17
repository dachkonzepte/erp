"""Klicktest: die Rückfrage bei „Deaktivieren“ und „Löschen“ nennt Anzeigename und Benutzername (1.9.345, Runde ab 1.9.343, Punkt 3).

Bei 412 px rollt die Tabelle in ihrem Rahmen; neben dem Knopf steht kein Name. Die Rückfrage ist ein confirm() des Browsers (Regel 4, Antwort Tobias
17.11.2026) -- der Test fängt ihren Text ab (ein Bildschirmfoto zeigt den Dialog nicht).

Testdaten: Anna Admin (angemeldet), Bea Büro (aktiv, hat eine Aufgabe angelegt), Carl Neu (aktiv, nie verwendet).

    412 px        Tabelle zu den Knöpfen gerollt: Benutzername und Anzeigename der Zeile nicht im Bild, der Knopf schon
    Rückfrage     „Deaktivieren“ bei Bea und „Löschen“ bei Carl, jeweils abgebrochen: die Rückfrage nennt „Bea Büro“ und „bea“ bzw. „Carl Neu“ und
                  „carl“; nichts geändert (Server). Danach „Löschen“ bei Carl bestätigt: Carl ist weg
    Bilder        412 px, hell und dunkel, die Zeilen mit den Knöpfen
    überall       keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_benutzer_rueckfrage.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "document.querySelectorAll('#rows tr').length>=3&&!document.getElementById('rows').textContent.includes('Noch keine')"
# Der Rahmen, in dem die Tabelle rollt, nach rechts zu den Knöpfen; die Zeilen ins Bild.
ZU_DEN_KNOEPFEN = "(()=>{const r=document.getElementById('rows');r.closest('div').scrollLeft=1e6;r.scrollIntoView({block:'center'})})()"
# Je Zeile: steht der Name (Spalten Benutzername und Anzeigename) im sichtbaren Teil des Rahmens? Steht der Knopf dort?
IM_BILD = ("[...document.querySelectorAll('#rows tr')].map(tr=>{const f=tr.closest('table').parentElement.getBoundingClientRect();"
           "const sicht=e=>{const b=e.getBoundingClientRect();return b.right>f.left+1&&b.left<f.right-1};"
           "const k=tr.querySelector('[data-klick=\"deaktivieren\"],[data-klick=\"loeschen\"]');"
           "return [tr.cells[0].textContent,sicht(tr.cells[0]),sicht(tr.cells[1]),k?sicht(k):null]})")


def befuellen(db, k):
    from app.models import AppUser, Task

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    carl = AppUser(username="carl", display_name="Carl Neu", role="buero_auftrag", password_hash=k.passwort())
    db.add_all([anna, bea, carl])
    db.flush()
    db.add(Task(title="Rückruf Kunde", created_by_user_id=bea.id))
    db.commit()
    return {"anna": k.cookies(anna), "bea_id": bea.id, "carl_id": carl.id}


async def _rueckfrage(tab, klick, konto_id):
    """Knopf klicken, die Rückfrage abbrechen, ihren Text zurückgeben."""
    await tab.js("window.__rueckfragen=[];window.__rueckfrageJa=false")
    await tab.js(f"document.querySelector('[data-klick=\"{klick}\"][data-id=\"{konto_id}\"]').click()")
    await tab.warten("window.__rueckfragen.length===1", 5)
    await tab.warte_auf_ruhe()
    return await tab.js("window.__rueckfragen[0]")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=(
        "window.alert=m=>console.error('alert(): '+m);window.__rueckfragen=[];window.__rueckfrageJa=false;"
        "window.confirm=m=>{window.__rueckfragen.push(m);return window.__rueckfrageJa===true};"))
    await tab.anmelden(seed["anna"])
    await tab.fenster(412, 1000, mobil=True)
    await tab.oeffnen("/users", "true")
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("412 px: Benutzer geladen", await tab.oeffnen("/users?n=1", BEREIT), True)
    await tab.warte_auf_ruhe()
    await tab.js(ZU_DEN_KNOEPFEN)
    p.pruefe("412 px: neben dem Knopf kein Name im Bild (Benutzername, Anzeigename, Knopf)", await tab.js(IM_BILD),
             [["anna", False, False, None], ["bea", False, False, True], ["carl", False, False, True]])

    deaktivieren = await _rueckfrage(tab, "deaktivieren", seed["bea_id"])
    p.pruefe("Rückfrage „Deaktivieren“ nennt Anzeigename und Benutzername", deaktivieren.split("\n")[0],
             "Benutzer „Bea Büro“ (Benutzername „bea“) deaktivieren?")
    loeschen = await _rueckfrage(tab, "loeschen", seed["carl_id"])
    p.pruefe("Rückfrage „Löschen“ nennt Anzeigename und Benutzername", loeschen.split("\n")[0],
             "Benutzer „Carl Neu“ (Benutzername „carl“) wirklich löschen?")
    print("Rückfrage Deaktivieren:", json.dumps(deaktivieren, ensure_ascii=False))
    print("Rückfrage Löschen:", json.dumps(loeschen, ensure_ascii=False))
    p.pruefe("abgebrochen: nichts geändert (Server)", await tab.js(
        "fetch('/api/users').then(r=>r.json()).then(l=>l.map(u=>[u.username,u.active]))"), [["anna", True], ["bea", True], ["carl", True]])

    for thema, name in (("light", "hell"), ("dark", "dunkel")):
        await tab.js(f"localStorage.setItem('erp_theme',{json.dumps(thema)})")
        p.pruefe(f"Bild 412 {name}: geladen", await tab.oeffnen(f"/users?n=b{name}", BEREIT), True)
        await tab.warte_auf_ruhe()
        p.pruefe(f"Bild 412 {name}: nichts läuft über", await tab.ueberlauf(), [])
        await tab.js(ZU_DEN_KNOEPFEN)
        await tab.bild(f"benutzer_rueckfrage_412_{name}")

    await tab.js("window.__rueckfragen=[];window.__rueckfrageJa=true")
    await tab.warte_auf_neu_geladene_liste(f"document.querySelector('[data-klick=\"loeschen\"][data-id=\"{seed['carl_id']}\"]').click()", "#rows")
    p.pruefe("bestätigt: Carl gelöscht", await tab.js(
        "fetch('/api/users').then(r=>r.json()).then(l=>l.map(u=>u.username))"), ["anna", "bea"])
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
