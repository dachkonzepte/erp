"""Klicktest: gesperrte Felder hell und dunkel erkennbar (1.9.122, Stufe 5, R1 Nachrunde, Punkt 4) -- eine Regel für jede Seite.

Testdaten der Bildgrundlage (scripts/bildgrundlage.py). Je Seite und je hell und dunkel jedes sichtbare gesperrte oder nur lesbare Feld (input
mit Fläche, textarea, select): Fläche = --ds-feld-gesperrt, Schrift = --ds-text-2, Mauszeiger „nicht erlaubt“ -- und die Fläche anders als die
eines offenen Felds (--ds-flaeche). Mindestens so viele gesperrte Felder, wie die Seite zeigen muss:

    Rechnung (Entwurf) als Büro – Auftrag     jedes Feld (bis 1.9.121 ohne eigene Regel: hell weiß wie ein offenes)
    Rechnung (Entwurf) als Büro – Finanzen    Rechnungsdatum und Steuerschlüssel gesperrt, die übrigen offen
    Einstellungen als Büro – Auftrag          Nummernkreise und Mahnstufen (seit 1.9.120 gesperrt)
    Einstellungen als Büro – Finanzen         Zeitregeln und DATEV: Berater- und Mandantennummer (nur Admin)
Bilder: rechnung_buero_auftrag_hell, rechnung_buero_auftrag_dunkel.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_gesperrte_felder.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Stehende Uhr der Bildgrundlage.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bildgrundlage as bg  # noqa: E402
from cdp_klicktest import klicktest_main  # noqa: E402

# Jedes sichtbare gesperrte Feld und ein offenes zum Vergleich; die Tokens über ein Probe-Element aufgelöst (berechnete Farbe).
MESSUNG = r"""(()=>{
  const probe=(eig,wert)=>{const d=document.createElement('div');d.style[eig]=wert;document.body.appendChild(d);
    const r=getComputedStyle(d)[eig];d.remove();return r};
  const soll={flaeche:probe('backgroundColor','var(--ds-feld-gesperrt)'),schrift:probe('color','var(--ds-text-2)'),
              offen:probe('backgroundColor','var(--ds-flaeche)')};
  const OHNE=['checkbox','radio','button','submit','reset','hidden','file','image','range','color'];
  const sichtbar=e=>e.offsetParent!==null&&e.getClientRects().length>0;
  const gesperrt=e=>(e.tagName==='SELECT'?e.disabled:(e.disabled||e.readOnly))&&!(e.tagName==='INPUT'&&OHNE.includes(e.type));
  const felder=[...document.querySelectorAll('input,textarea,select')].filter(sichtbar);
  const abweichend=[];let anzahl=0;
  for(const f of felder.filter(gesperrt)){anzahl++;const s=getComputedStyle(f);
    if(s.backgroundColor!==soll.flaeche||s.color!==soll.schrift||s.cursor!=='not-allowed')
      abweichend.push((f.id||f.className||f.tagName)+': '+s.backgroundColor+' / '+s.color+' / '+s.cursor)}
  const offeneFelder=felder.filter(f=>!gesperrt(f)&&!(f.tagName==='INPUT'&&OHNE.includes(f.type)));
  const offenGleich=offeneFelder.filter(f=>getComputedStyle(f).backgroundColor===soll.flaeche).map(f=>f.id||f.tagName);
  return {anzahl,abweichend,anders:soll.flaeche!==soll.offen,offenGleich}})()"""


async def _thema(tab, thema):
    await tab.js(f"document.documentElement.setAttribute('data-theme','{thema}')")
    await tab.js("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")


async def _messen(tab, p, name, mindestens):
    for thema in ("light", "dark"):
        await _thema(tab, thema)
        m = await tab.js(MESSUNG)
        wort = "hell" if thema == "light" else "dunkel"
        p.pruefe(f"{name} ({wort}): mindestens {mindestens} gesperrte Felder, jedes mit Fläche, Schrift, Mauszeiger der Regel",
                 [m["anzahl"] >= mindestens, m["abweichend"], m["anders"], m["offenGleich"]], [True, [], True, []])


EINSTELLUNGEN = "document.querySelector('.settings-menu')&&typeof sequences!=='undefined'&&sequences.length>0&&document.querySelector('.sequence')"


async def _bereich(tab, schluessel, bedingung):
    await tab.js(f"document.querySelector('[data-settings-section=\"{schluessel}\"]').click()")
    await tab.warten(bedingung, 15)


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1440, 900)
    rechnung = f"/invoices/{seed['rechnung']}"
    bereit = "invoice&&document.getElementById('statusInfo').textContent.length>0"

    await tab.anmelden(seed["cookies"][bg.BUERO_AUFTRAG])
    await tab.oeffnen(rechnung, bereit)
    await _messen(tab, p, "Rechnung als Büro – Auftrag", 8)
    for thema in ("light", "dark"):
        await _thema(tab, thema)
        await tab.bild(f"rechnung_buero_auftrag_{'hell' if thema == 'light' else 'dunkel'}")
    await tab.oeffnen("/settings", EINSTELLUNGEN)
    await _bereich(tab, "numbers", "document.querySelector('.sequence input')")
    await _messen(tab, p, "Einstellungen, Nummernkreise als Büro – Auftrag", 20)
    await _bereich(tab, "reminder-levels", "document.querySelector('#reminderLevelRows input')")
    await _messen(tab, p, "Einstellungen, Mahnwesen als Büro – Auftrag", 6)
    p.pruefe("JS-Fehler (Büro – Auftrag)", tab.fehler, [])

    await tab.anmelden(seed["cookies"][bg.BUERO])
    await tab.oeffnen(rechnung, bereit)
    await _messen(tab, p, "Rechnung als Büro – Finanzen", 1)
    await tab.oeffnen("/settings", EINSTELLUNGEN)
    await _bereich(tab, "time-rules", "document.getElementById('datevBerater')")
    await _messen(tab, p, "Einstellungen, DATEV als Büro – Finanzen", 2)
    p.pruefe("JS-Fehler (Büro – Finanzen)", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(bg.befuellen, pruefen, beschreibung=__doc__, uhr=bg.UHR, zeitlimit_je_schritt=True,
                            chrome_argumente=bg.CHROME_ARGUMENTE))
