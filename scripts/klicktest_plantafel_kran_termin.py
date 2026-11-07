"""Klicktest: ein Termin aus dem Kran-Postfach -- ein Klick zeigt ihn mit „Als Kranvermietung übernehmen …“ (1.9.251, Stufe 6, R4, Punkt 5).

Testdaten wie klicktest_plantafel_tafel (Zeichnung KW 45–46: Termin „Müller“ ganztägig 10.–11.11. im Postfach des Krans), dazu ein Termin einer Serie
„Wartung Hersteller“ am 13.11. um 09:00. Stehende Uhr Di 03.11.2026 10:00.

    Termin       Klick auf „Outlook · Müller“ in der Zeile des Krans: Dialog mit Titel, „10.–11.11. · ganztägig“ und „Als Kranvermietung übernehmen …“
    Übernehmen   „Termin „Müller“ als Kranvermietung“: Art fest, Von/Bis 10.–11.11. gesperrt, der Kran gewählt und gesperrt, kein „+ Gerät“, Notiz „Müller“;
                 ohne Kunde „Bitte einen Kunden wählen.“; Kunde und Bediener Kai -> Prüfung über …/kran-termine/{id}/pruefen ohne Warnung; Speichern über
                 …/kranvermietung -> in der Zeile des Krans „Vermietung · Kai“ 10.–11.11., der Termin ist kein eigener Balken mehr
    Serie        Klick auf „Outlook · 09:00 Wartung Hersteller“: Hinweis „Termin einer Serie“, kein Knopf zur Übernahme
    Maße         1440 und 1280 px: die Dialoge passen; hell und dunkel als Bild
    keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_plantafel_kran_termin.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_plantafel_dialog import IM_DIALOG  # noqa: E402
from klicktest_plantafel_tafel import BEREIT, HEUTE, UHR_MS  # noqa: E402
from klicktest_plantafel_tafel import befuellen as tafel_befuellen  # noqa: E402


def befuellen(db, k):
    from datetime import datetime

    from app.models import OperationalResource, OutlookSeriesOccurrence

    seed = tafel_befuellen(db, k)
    kran = db.query(OperationalResource).filter_by(name="Kran Böcker AHK 36").one()
    db.add(OutlookSeriesOccurrence(resource_id=kran.id, outlook_postfach="kran@dachkonzepte.example", outlook_event_id="serie-1", occurrence_type="occurrence",
                                   title="Wartung Hersteller", start_at=datetime(2026, 11, 13, 9), end_at=datetime(2026, 11, 13, 11)))
    db.commit()
    return seed


KRAN_BALKEN = ("[...[...document.querySelectorAll('#planner .planner-row')].find(z=>z.querySelector('.row-label b').textContent.trim()==='Kran Böcker AHK 36')"
               ".querySelectorAll('.slot')].map(s=>s.querySelector('.slot-text').textContent.trim())")


def _klick_balken(text):
    return ("[...[...document.querySelectorAll('#planner .planner-row')].find(z=>z.querySelector('.row-label b').textContent.trim()==='Kran Böcker AHK 36')"
            f".querySelectorAll('.slot')].find(s=>s.textContent.includes({text!r})).click()")


async def pruefen(tab, seed, p):
    await tab.fenster(1440, 1000)
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','light')}catch(e){}")
    await tab.browser_uhr_fest(UHR_MS)
    await tab.anmelden(seed["anna"])
    await tab.oeffnen("/planning", BEREIT)
    await tab.warte_auf_ruhe()
    p.pruefe("Kran: Termine als Knöpfe", await tab.js(
        "[...document.querySelectorAll('#planner .slot.termin')].map(s=>[s.tagName,s.dataset.klick,s.title.split('\\n')[1]])"),
        [["BUTTON", "kranTermin", "Aus dem Kalender des Geräts · 10.–11.11. · belegt das Gerät · „Als Kranvermietung übernehmen …“"],
         ["BUTTON", "kranTermin", "Aus dem Kalender des Geräts · 13.11. · belegt das Gerät · Termin einer Serie"]])

    # --- der Termin ---
    await tab.js(_klick_balken("Müller"))
    await tab.warten("terminDialog.open")
    p.pruefe("Termin: Titel, Tage, Knopf zur Übernahme", await tab.js(
        "['tdTitel','tdUnter','tdText','tdZeit'].map(i=>document.getElementById(i).textContent).concat([document.getElementById('tdUebernehmen').hidden])"),
        ["Termin im Kalender des Geräts", "Kran Böcker AHK 36", "Müller", "10.–11.11. · ganztägig", False])
    await tab.bild("termin_1440_hell")

    # --- übernehmen ---
    await tab.js("document.getElementById('tdUebernehmen').click()")
    await tab.warten("einsatzDialog.open&&!terminDialog.open&&!!document.getElementById('edMeldung').textContent")
    await tab.warte_auf_ruhe()
    p.pruefe("Übernehmen: Kopf, Art fest, Zeitraum und Gerät vom Termin, Notiz", await tab.js(
        "[document.getElementById('edTitel').textContent,document.querySelector('#edArt [aria-pressed=true]').textContent,"
        "[...document.querySelectorAll('#edArt button')].every(b=>b.disabled),document.getElementById('edVon').value,document.getElementById('edBis').value,"
        "document.getElementById('edVon').disabled&&document.getElementById('edBis').disabled,document.getElementById('edGeraetPlus').hidden,"
        "[...document.querySelectorAll('#edGeraete .wahl')].map(l=>[l.querySelector('.wahl-name').textContent,l.querySelector('input').checked,l.querySelector('input').disabled]),"
        "document.getElementById('edNotiz').value]"),
        ["Termin „Müller“ als Kranvermietung", "Kranvermietung", True, "2026-11-10", "2026-11-11", True, True, [["Kran Böcker AHK 36", True, True]], "Müller"])
    p.pruefe("ohne Kunde: Meldung, keine Prüfung", await tab.js(
        "[document.getElementById('edMeldung').textContent,performance.getEntriesByType('resource').filter(e=>e.name.includes('/kran-termine/')).length]"),
        ["Bitte einen Kunden wählen.", 0])
    await tab.js("{const k=document.getElementById('edKunde');k.value=[...k.options].find(o=>o.textContent.startsWith('Familie Sommer')).value;k.dispatchEvent(new Event('change'))}")
    await tab.warten("!!pruefung", 10)
    await tab.js("document.getElementById('edPersonPlus').click();{const w=document.getElementById('edPersonWahl');w.value=[...w.options].find(o=>o.textContent==='Kai Kolb').value;w.dispatchEvent(new Event('change'))}")
    await tab.warten("!!pruefung&&pruefStand()===pruefungFuer&&pruefung.personen.some(x=>x.name==='Kai Kolb'&&x.gewaehlt)", 10)
    await tab.warte_auf_ruhe()
    p.pruefe("geprüft über den Weg des Termins, ohne Warnung", await tab.js(
        "[performance.getEntriesByType('resource').some(e=>/\\/api\\/planning\\/kran-termine\\/\\d+\\/pruefen$/.test(e.name)),"
        "performance.getEntriesByType('resource').some(e=>e.name.endsWith('/api/planning/slots/pruefen')),pruefung.warnungen.length,"
        "document.getElementById('edSpeichern').textContent]"), [True, False, 0, "Einsatz speichern"])
    await tab.bild("termin_uebernehmen_1440_hell")
    await tab.warte_auf_neu_geladene_liste("void einsatzSpeichern()", "#planner")
    await tab.warten("!einsatzDialog.open", 10)
    p.pruefe("gespeichert: Vermietung in der Zeile des Krans, kein eigener Termin mehr", [await tab.js(KRAN_BALKEN), await tab.js(
        "(()=>{const s=board.slots.find(x=>x.art==='kranvermietung'&&x.start_date==='2026-11-10');return s?[s.end_date,s.employees.map(e=>e.name),s.notes]:null})()")],
        [["Am Wasserturm 4", "Vermietung · Lia", "Am Wasserturm 4", "Vermietung · Kai", "Outlook · 09:00 Wartung Hersteller"], ["2026-11-11", ["Kai Kolb"], "Müller"]])

    # --- Termin einer Serie ---
    await tab.js(_klick_balken("Wartung Hersteller"))
    await tab.warten("terminDialog.open")
    p.pruefe("Serie: Hinweis, kein Knopf", await tab.js(
        "[document.getElementById('tdHinweis').textContent.startsWith('Ein Termin einer Serie'),document.getElementById('tdUebernehmen').hidden]"), [True, True])
    await tab.bild("termin_serie")
    await tab.js("terminDialog.close()")

    # --- 1280 px, dunkel ---
    await tab.fenster(1280, 900)
    await tab.warte_auf_ruhe()
    await tab.js(_klick_balken("Wartung Hersteller"))
    await tab.warten("terminDialog.open")
    p.pruefe("1280 px: der Dialog des Termins passt", await tab.js(IM_DIALOG.replace("einsatzDialog", "terminDialog")), [])
    await tab.bild("termin_1280_hell")
    await tab.js("terminDialog.close()")
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="try{localStorage.setItem('erp_theme','dark')}catch(e){}")
    await tab.oeffnen("/planning", "typeof board!=='undefined'&&board&&board.slots&&board.slots.length===7&&!!document.querySelector('#planner .planner-row')")
    await tab.warte_auf_ruhe()
    await tab.js(_klick_balken("Wartung Hersteller"))
    await tab.warten("terminDialog.open")
    await tab.bild("termin_1280_dunkel")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr=f"{HEUTE} 10:00"))
