"""Klicktest: der Einsatz-Dialog nach der Zeichnung entwurf-stufe6/plantafel-einsatz.html (1.9.248, Stufe 6, R4, Punkt 4).

Testdaten wie klicktest_plantafel_tafel (Zeichnung KW 45–46), dazu die Geräte der Kolonne Süd (Pritsche HS-DK 204, Kran). Stehende Uhr Di 03.11.2026 10:00.

    Bearbeiten   Klick auf „Garage Lindenweg 7“: Kopf mit Auftrag und Kunde, Art Baustelle (fest), Status vorläufig, Von/Bis/Stunden/Anfahrt nebeneinander und
                 im Dialog, Kapazität mit Rechnung, Kolonne Süd; Besetzung: Kai „auch bei P-2026-0118 · 03.–05.11.“ (Warnung), Lia nicht gewählt
                 „Kranvermietung 04.–05.11.“, Nele „Urlaub beantragt 05.–06.11.“; Geräte: Pritsche „alle Tage“, Kran nicht gewählt „vermietet 04.–05.11.“;
                 Kasten „1 Warnung · 1 Hinweis“, Knopf „Trotzdem planen“
    Sofort       Kolonne Nord gewählt und gleich gespeichert: erst geprüft, die neuen Warnungen stehen da, nichts ist gespeichert
    Ändern       Kai abwählen -> keine Warnung, „Speichern“, Rechnung mit einer Person; wieder an; „+ Person“ Ole; Tage der Pritsche: nur Di und Mi;
                 „Trotzdem planen“ speichert (Besetzung Kai, Nele, Ole; Pritsche nur 03., 04.11.)
    Kran         Menü „Kranvermietung anlegen“: Art Kranvermietung, Kunde, keine Kolonne, „Bediener“; Kunde, Lia, „+ Gerät“ Kran -> gespeichert, Balken in
                 der Zeile des Krans
    Neu          „+ Einsatz“: „Einsatz planen“, Baustelle, ohne „Einsatz löschen“; Kolonne Süd schlägt Kai, Lia, Nele und ihre Geräte vor, dann Nord Tom, Mia, Ole
                 und die Pritsche 202; Tom von Hand abgewählt, dann Süd: Mia und Ole bleiben, die Geräte schlägt Süd vor
    Maße         1440, 1280 und 412 px: kein Feld ragt aus dem Dialog; hell und dunkel als Bild; dunkel: Dialog dunkel, Hintergrund dahinter
                 abgedunkelt; die Knopfleiste bleibt im Bild, wenn der Dialog rollt
    keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_plantafel_dialog.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_plantafel_tafel import BEREIT, HEUTE, UHR_MS  # noqa: E402
from klicktest_plantafel_tafel import befuellen as tafel_befuellen  # noqa: E402


GEWAEHLT = "[...document.querySelectorAll('#edPersonen .wahl')].filter(l=>l.querySelector('input').checked).map(l=>l.querySelector('.wahl-name').textContent)"
GERAETE_GEWAEHLT = "[...document.querySelectorAll('#edGeraete .wahl')].filter(l=>l.querySelector('input').checked).map(l=>l.querySelector('.wahl-name').textContent)"


def befuellen(db, k):
    from app.models import OperationalResource, Team, TeamResource
    seed = tafel_befuellen(db, k)
    sued = db.query(Team).filter_by(name="Kolonne Süd").one()
    nord = db.query(Team).filter_by(name="Kolonne Nord").one()
    geraet = {r.name: r.id for r in db.query(OperationalResource)}
    db.add_all([TeamResource(team_id=sued.id, resource_id=geraet["Pritsche HS-DK 204"]), TeamResource(team_id=sued.id, resource_id=geraet["Kran Böcker AHK 36"]),
                TeamResource(team_id=nord.id, resource_id=geraet["Pritsche HS-DK 202"])])
    db.commit()
    return seed


PERSONEN = ("[...document.querySelectorAll('#edPersonen .wahl')].map(l=>[l.querySelector('.wahl-name').textContent,l.querySelector('input').checked,"
            "l.querySelector('.wahl-zustand').textContent.trim(),l.querySelector('.wahl-zustand').classList.contains('z-warn')])")
GERAETE = ("[...document.querySelectorAll('#edGeraete .wahl')].map(l=>[l.querySelector('.wahl-name').textContent,l.querySelector('input').checked,"
           "(l.querySelector('.link-knopf')||{}).textContent||'',l.querySelector('.wahl-zustand').textContent.trim()])")
# kein Feld ragt aus dem Dialog (1 px Spiel), die vier Felder stehen nebeneinander (gleiche Höhe oben) oder bei 412 px zu zweit
IM_DIALOG = ("(()=>{const d=document.getElementById('einsatzDialog').getBoundingClientRect();const f=[...document.querySelectorAll('#einsatzDialog input,#einsatzDialog select,"
             "#einsatzDialog textarea,#einsatzDialog button')].filter(x=>x.offsetParent).map(x=>[x.id||x.textContent.trim().slice(0,20),x.getBoundingClientRect()]);"
             "return f.filter(([n,r])=>r.left<d.left-1||r.right>d.right+1).map(([n])=>n)})()")
VIER_TOP = "[...document.querySelectorAll('.ed-vier input')].map(x=>Math.round(x.getBoundingClientRect().top))"


async def _bis_geprueft(tab):
    await tab.warte_auf_ruhe()
    await tab.warten("!!pruefung", 5)


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")
    await tab.browser_uhr_fest(UHR_MS)
    await tab.anmelden(seed["anna"])
    await tab.oeffnen("/planning", BEREIT)
    await tab.warte_auf_ruhe()

    # --- Bearbeiten wie die Zeichnung ---
    await tab.js("[...document.querySelectorAll('.track[data-team-id] .slot')].find(s=>s.textContent.includes('Garage Lindenweg 7')).click()")
    await tab.warten("document.getElementById('einsatzDialog').open")
    await _bis_geprueft(tab)
    p.pruefe("Kopf: Titel und Auftrag", await tab.js("[document.getElementById('edTitel').textContent,document.getElementById('edUnter').textContent]"),
             ["Einsatz bearbeiten", "P-2026-0131 · Garage Lindenweg 7 · Familie Sommer"])
    p.pruefe("Art Baustelle (fest), Status vorläufig", await tab.js(
        "[[...document.querySelectorAll('#edArt button')].map(b=>[b.textContent,b.getAttribute('aria-pressed'),b.disabled]),"
        "[...document.querySelectorAll('#edStatus button')].map(b=>[b.textContent,b.getAttribute('aria-pressed')])]"),
        [[["Baustelle", "true", True], ["Kranvermietung", "false", True]], [["vorläufig", "true"], ["fest", "false"]]])
    p.pruefe("Von, Bis, Stunden, Anfahrt nebeneinander", len(set(await tab.js(VIER_TOP))), 1)
    p.pruefe("1440 px: kein Feld ragt aus dem Dialog", await tab.js(IM_DIALOG), [])
    p.pruefe("Kapazität mit Rechnung", await tab.js("document.getElementById('edRechnung').textContent"),
             "Kapazität 2 Personen × 3 Arbeitstage × 8,00 h = 48,00 h")  # ohne Kalkulation am Auftrag kein „Rest laut Kalkulation“
    p.pruefe("Kolonne Süd mit Vorschlag", await tab.js("document.getElementById('edKolonne').selectedOptions[0].textContent"), "Kolonne Süd – schlägt Kai, Lia, Nele vor")
    p.pruefe("Besetzung mit Zustand je Person", await tab.js(PERSONEN), [
        ["Kai Kolb", True, "auch bei P-2026-0118 · 03.–05.11.", True], ["Nele Neu", True, "Urlaub beantragt 05.–06.11.", False],
        ["Lia Lang", False, "Kranvermietung 04.–05.11.", False]])
    p.pruefe("Geräte mit Tagen und Zustand", await tab.js(GERAETE), [["Pritsche HS-DK 204", True, "alle Tage", ""], ["Kran Böcker AHK 36", False, "", "vermietet 04.–05.11."]])
    p.pruefe("Warnungen und Hinweise, „Trotzdem planen“", await tab.js(
        "[document.querySelector('#edWarnungen .ed-eb').textContent.trim(),document.getElementById('edSpeichern').textContent]"), ["1 Warnung · 1 Hinweis", "Trotzdem planen"])
    await tab.bild("dialog_bearbeiten_1440_hell")

    # --- Kolonne wechseln und sofort speichern: erst prüfen, die neuen Warnungen zeigen, nichts speichern ---
    await tab.js("document.getElementById('edKolonne').value=String(board.teams.find(t=>t.name==='Kolonne Nord').id);void einsatzSpeichern()")
    await tab.warte_auf_ruhe()
    p.pruefe("Kolonne gewechselt und sofort gespeichert: neue Warnungen, nichts gespeichert", await tab.js(
        "[document.getElementById('einsatzDialog').open,document.getElementById('edMeldung').textContent,"
        "board.slots.find(x=>x.project_name==='Garage Lindenweg 7').team_id===board.teams.find(t=>t.name==='Kolonne Süd').id,"
        "pruefung.personen.filter(x=>x.gewaehlt).map(x=>x.name)]"),
        [True, "Bitte die Warnungen prüfen – dann „Trotzdem planen“.", True, ["Tom Monteur", "Mia Monteurin", "Ole Offen"]])
    await tab.js("einsatzDialog.close()")
    await tab.js("[...document.querySelectorAll('.track[data-team-id] .slot')].find(s=>s.textContent.includes('Garage Lindenweg 7')).click()")
    await _bis_geprueft(tab)

    # --- Ändern ---
    await tab.js("document.querySelector('#edPersonen input[data-id]').click()")  # Kai ab
    await tab.warte_auf_ruhe()
    p.pruefe("Kai abgewählt: keine Warnung, „Speichern“, eine Person", await tab.js(
        "[pruefung.warnungen.length,document.getElementById('edSpeichern').textContent,"
        "document.getElementById('edRechnung').textContent.includes('1 Person × 3 Arbeitstage')]"), [0, "Speichern", True])
    await tab.js("[...document.querySelectorAll('#edPersonen input')].find(i=>i.closest('.wahl').textContent.includes('Kai')).click()")
    await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('edPersonPlus').click()")
    await tab.js("{const w=document.getElementById('edPersonWahl');w.value=[...w.options].find(o=>o.textContent==='Ole Offen').value;w.dispatchEvent(new Event('change'))}")
    await tab.warte_auf_ruhe()
    p.pruefe("+ Person: Ole gewählt", await tab.js("[...document.querySelectorAll('#edPersonen .wahl')].filter(l=>l.querySelector('input').checked).map(l=>l.querySelector('.wahl-name').textContent)"),
             ["Kai Kolb", "Nele Neu", "Ole Offen"])
    await tab.js("document.querySelector('#edGeraete .link-knopf').click()")
    p.pruefe("Tage der Pritsche: drei Tage zur Wahl", await tab.js("[...document.querySelectorAll('.tage-wahl .tag-knopf')].map(b=>[b.textContent,b.getAttribute('aria-pressed')])"),
             [["Di 03.11.", "true"], ["Mi 04.11.", "true"], ["Do 05.11.", "true"]])
    await tab.js("[...document.querySelectorAll('.tage-wahl .tag-knopf')][2].click()")
    await tab.warte_auf_ruhe()
    p.pruefe("Tage der Pritsche: nur Di und Mi", await tab.js("document.querySelector('#edGeraete .link-knopf').textContent"), "nur 03., 04.11.")
    await tab.warte_auf_neu_geladene_liste("void einsatzSpeichern()", "#planner")
    await tab.warten("!document.getElementById('einsatzDialog').open", 10)
    p.pruefe("Gespeichert: Besetzung und Tage der Pritsche", await tab.js(
        "(()=>{const s=board.slots.find(x=>x.project_name==='Garage Lindenweg 7');return [s.employees.map(e=>e.vorname),s.resources.map(r=>[r.name,r.tage])]})()"),
        [["Kai", "Nele", "Ole"], [["Pritsche HS-DK 204", ["2026-11-03", "2026-11-04"]]]])

    # --- Kranvermietung anlegen ---
    p.pruefe("Menü: Kranvermietung anlegen steht im Menü", await tab.js(
        "(()=>{const m=document.getElementById('menueKran');return !m.hidden&&m.closest('#seitenkopfMenue')!==null})()"), True)
    await tab.js("document.getElementById('menueKran').click()")
    await tab.warten("document.getElementById('einsatzDialog').open&&einsatz&&einsatz.art==='kranvermietung'")
    await tab.warte_auf_ruhe()
    p.pruefe("Kranvermietung: Art, Kunde, keine Kolonne, Bediener", await tab.js(
        "[document.getElementById('edTitel').textContent,document.querySelector('#edArt [aria-pressed=true]').textContent,document.getElementById('edKundeFeld').hidden,"
        "document.getElementById('edKolonneFeld').hidden,document.getElementById('edPersonenTitel').textContent]"),
        ["Kranvermietung anlegen", "Kranvermietung", False, True, "Bediener"])
    await tab.js("{const k=document.getElementById('edKunde');k.value=[...k.options].find(o=>o.textContent.startsWith('Familie Sommer')).value;k.dispatchEvent(new Event('change'))}")
    await tab.js("document.getElementById('edVon').value='2026-11-12';document.getElementById('edBis').value='2026-11-13';document.getElementById('edVon').dispatchEvent(new Event('change'))")
    await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('edPersonPlus').click();{const w=document.getElementById('edPersonWahl');w.value=[...w.options].find(o=>o.textContent==='Lia Lang').value;w.dispatchEvent(new Event('change'))}")
    await tab.warte_auf_ruhe()
    await tab.js("document.getElementById('edGeraetPlus').click();{const w=document.getElementById('edGeraetWahl');w.value=[...w.options].find(o=>o.textContent==='Kran Böcker AHK 36').value;w.dispatchEvent(new Event('change'))}")
    await tab.warte_auf_ruhe()
    await tab.bild("dialog_kran_1440_hell")
    await tab.warte_auf_neu_geladene_liste("void einsatzSpeichern()", "#planner")
    await tab.warten("!document.getElementById('einsatzDialog').open", 10)
    p.pruefe("Kranvermietung gespeichert, Balken beim Kran", await tab.js(
        "(()=>{const r=[...document.querySelectorAll('#planner .planner-row')].find(z=>z.querySelector('.row-label b').textContent==='Kran Böcker AHK 36');"
        "return [...r.querySelectorAll('.slot.kran')].map(s=>s.querySelector('.slot-text').textContent.trim())})()"), ["Vermietung · Lia", "Vermietung · Lia"])

    # --- Neu ---
    await tab.js("document.getElementById('neuerEinsatz').click()")
    await tab.warten("document.getElementById('einsatzDialog').open")
    await _bis_geprueft(tab)
    p.pruefe("Neu: Einsatz planen, Baustelle, ohne Löschen", await tab.js(
        "[document.getElementById('edTitel').textContent,document.querySelector('#edArt [aria-pressed=true]').textContent,document.getElementById('edLoeschen').hidden]"),
        ["Einsatz planen", "Baustelle", True])

    # --- Neu: eine andere Kolonne schlägt ihre Mitglieder vor, solange die Besetzung nicht von Hand geändert ist (Festlegung 1.9.248 Nr. 7) ---
    async def kolonne(name):
        tid = await tab.js("board.teams.find(t=>t.name===" + repr(name) + ").id")
        await tab.js("{const k=document.getElementById('edKolonne');k.value='" + str(tid) + "';k.dispatchEvent(new Event('change'))}")
        # pruefen() wartet 200 ms: erst wenn die Prüfung zu genau dieser Kolonne zurück ist
        await tab.warten(f"einsatz.team_id==={tid}&&!!pruefung&&pruefStand()===pruefungFuer", 10)
        await tab.warte_auf_ruhe()
        return [sorted(await tab.js(GEWAEHLT)), sorted(await tab.js(GERAETE_GEWAEHLT))]
    p.pruefe("Neu, Kolonne Süd: schlägt Kai, Lia, Nele und ihre Geräte vor", await kolonne("Kolonne Süd"),
             [["Kai Kolb", "Lia Lang", "Nele Neu"], ["Kran Böcker AHK 36", "Pritsche HS-DK 204"]])
    p.pruefe("Neu, dann Kolonne Nord: schlägt Nord vor", await kolonne("Kolonne Nord"), [["Mia Monteurin", "Ole Offen", "Tom Monteur"], ["Pritsche HS-DK 202"]])
    await tab.js("[...document.querySelectorAll('#edPersonen input')].find(i=>i.closest('.wahl').textContent.includes('Tom')).click()")
    await tab.warten("!!pruefung&&pruefStand()===pruefungFuer&&!pruefung.personen.find(x=>x.name==='Tom Monteur'&&x.gewaehlt)", 10)
    await tab.warte_auf_ruhe()
    p.pruefe("Tom von Hand ab, dann Kolonne Süd: die Besetzung von Hand bleibt, die Geräte schlägt Süd vor", await kolonne("Kolonne Süd"),
             [["Mia Monteurin", "Ole Offen"], ["Kran Böcker AHK 36", "Pritsche HS-DK 204"]])
    await tab.js("einsatzDialog.close()")

    # --- Maße und dunkel ---
    for breite, hoehe in ((1280, 900), (412, 900)):
        await tab.fenster(breite, hoehe, mobil=breite < 500)
        await tab.js("openEdit(board.slots.find(x=>x.project_name==='Garage Lindenweg 7').id)")
        await _bis_geprueft(tab)
        p.pruefe(f"{breite} px: kein Feld ragt aus dem Dialog", await tab.js(IM_DIALOG), [])
        await tab.bild(f"dialog_bearbeiten_{breite}_hell")
        await tab.js("einsatzDialog.close()")
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','dark')}catch(e){}")
    await tab.oeffnen("/planning", "typeof board!=='undefined'&&board&&board.slots&&board.slots.length>=6")
    await tab.warte_auf_ruhe()
    await tab.js("openEdit(board.slots.find(x=>x.project_name==='Garage Lindenweg 7').id)")
    await _bis_geprueft(tab)
    await tab.bild("dialog_bearbeiten_1440_dunkel")
    p.pruefe("dunkel: Dialog dunkel, der Hintergrund dahinter abgedunkelt, nicht aufgehellt", await tab.js(
        # Helligkeit 0–255 aus rgb()/rgba() oder color(srgb …) (so liefert Chrome eine mit color-mix gemischte Farbe, Werte 0–1)
        "(()=>{const hell=c=>{const f=c.startsWith('color(')?255:1;const m=c.match(/\\d+(\\.\\d+)?/g).map(Number);return (m[0]*299+m[1]*587+m[2]*114)/1000*f};const d=getComputedStyle(einsatzDialog);"
        "const b=getComputedStyle(einsatzDialog,'::backdrop').backgroundColor;return [document.documentElement.dataset.theme,hell(d.backgroundColor)<80,hell(b)<80]})()"),
        ["dark", True, True])
    p.pruefe("dunkel, 1440 × 1000: die Knopfleiste ganz im Bild, ohne zu rollen", await tab.js(
        # an den Anfang gerollt: ohne klebende Leiste läge der Knopf unter dem sichtbaren Teil des Dialogs
        "(()=>{einsatzDialog.scrollTop=0;const r=document.getElementById('edSpeichern').getBoundingClientRect(),d=einsatzDialog.getBoundingClientRect();"
        "return [einsatzDialog.scrollHeight>einsatzDialog.clientHeight,r.bottom<=d.bottom&&r.bottom<=innerHeight&&r.top>=d.top]})()"),
        [True, True])  # der Dialog rollt (vier Personen), der Knopf bleibt sichtbar
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr=f"{HEUTE} 10:00"))
