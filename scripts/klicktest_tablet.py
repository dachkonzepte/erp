"""Klicktest: der Monteursrahmen setzt .ds-tablet (seit 1.9.88, Stufe 4, R5, Teil 1 Punkt 2; Beschluss aus Stufe 2).

Testdaten und Seiten der Bildgrundlage (scripts/bildgrundlage.py: befuellen(), AUFNAHMEN, stehende Uhr 14.10.2026 10:00). Je Seite der
Monteurin -- Heute, Heute / Offen, Objekt, Meine Zeiten, Einsatzberichte, Bericht, Checkliste, Checklisten zum Auftrag, Betriebsmittel,
Konto -- bei 1280 × 620 und 800 × 1100 (TerraPad quer und hoch), hell:

    Klasse          <body> trägt ds-tablet
    Seitentitel     .ds-kopf-titel (wo es ihn gibt) 26 px
    Ecken           jeder sichtbare Knopf und jedes Feld (button, a.knopf, a.ds-knopf, input, select, textarea; nicht Häkchen, nicht im
                    Monteurskopf) mit 12 px Ecke -- rund (999 px) bleibt rund; ein Textknopf ohne Rahmen und Fläche zählt nicht;
                    eine Segmentgruppe (.segmente) außen 12 px, innen ohne Ecke
    Ziele           dieselben Elemente mindestens 48 px hoch
    Dialog          „Meine Zeiten“ / „Zeit nachtragen“ geöffnet: Ecken und Ziele darin ebenso, die Knopfleiste im Bild
Bilder: je Seite und Größe das Fenster (Ordner der Screenshots).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_tablet.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD]
        [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer etwa eine Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bildgrundlage import AUFNAHMEN, BEREIT, MONTEUR, STILL, UHR, befuellen  # noqa: E402,F401  (befuellen: Testdaten der Bildgrundlage)
from cdp_klicktest import klicktest_main  # noqa: E402

GROESSEN = ((1280, 620), (800, 1100))
SEITEN = [a for a in AUFNAHMEN if MONTEUR in a.rollen and a.vorlage != "access_denied.html"]

# Was an einer Seite gemessen wird -- innerhalb von wurzel (die Seite oder ein offener Dialog)
MESSEN = """(wurzel=>{
const sichtbar=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
const name=e=>e.tagName.toLowerCase()+(e.id?'#'+e.id:'')+(e.classList.length?'.'+[...e.classList].join('.'):'')
  +' „'+(e.textContent||e.value||e.getAttribute('aria-label')||'').trim().replace(/\\s+/g,' ').slice(0,30)+'“';
const ziele=[...wurzel.querySelectorAll('button,a.knopf,a.ds-knopf,input:not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=file]),select,textarea')]
  .filter(e=>sichtbar(e)&&!e.closest('.mobile-header-wrap')&&!e.closest('[hidden]')&&(wurzel.tagName==='DIALOG'||!e.closest('dialog')));
const ecke=e=>getComputedStyle(e).borderTopLeftRadius;
const knopfartig=e=>{const s=getComputedStyle(e);return e.tagName!=='BUTTON'&&!e.classList.contains('knopf')&&!e.classList.contains('ds-knopf')
  ||parseFloat(s.borderTopWidth)>0||(s.backgroundColor!=='rgba(0, 0, 0, 0)'&&s.backgroundColor!=='transparent')};
const gruppen=[...wurzel.querySelectorAll('.segmente')].filter(g=>sichtbar(g)&&(wurzel.tagName==='DIALOG'||!g.closest('dialog')));
const r=(e,k)=>getComputedStyle(e)[k];
const segmentFehler=gruppen.filter(g=>{const k=[...g.children];if(k.length<2)return false;
  return r(k[0],'borderTopLeftRadius')!=='12px'||r(k[0],'borderTopRightRadius')!=='0px'||r(k.at(-1),'borderTopRightRadius')!=='12px'
    ||r(k.at(-1),'borderTopLeftRadius')!=='0px'||k.slice(1,-1).some(m=>r(m,'borderTopLeftRadius')!=='0px'||r(m,'borderTopRightRadius')!=='0px')})
  .map(g=>[...g.children].map(m=>m.textContent.trim()+' '+r(m,'borderTopLeftRadius')+'/'+r(m,'borderTopRightRadius')).join(' | '));
const titel=document.querySelector('.ds-kopf-titel');
return {tablet:document.body.classList.contains('ds-tablet'),titel:titel&&sichtbar(titel)?getComputedStyle(titel).fontSize:null,
  anzahl:ziele.length,
  ecken:ziele.filter(e=>!e.classList.contains('segment')&&knopfartig(e)&&!['12px','999px'].includes(ecke(e))).map(e=>name(e)+' '+ecke(e))
    .concat(segmentFehler.map(s=>'Segmente: '+s)),
  klein:ziele.filter(e=>e.getBoundingClientRect().height<47.5).map(e=>name(e)+' '+Math.round(e.getBoundingClientRect().height)+' px')};
})"""


async def _messen(tab, p, wo, wurzel="document.body"):
    m = await tab.js(MESSEN + f"({wurzel})")
    p.pruefe(f"{wo}: <body> mit ds-tablet", m["tablet"], True)
    if m["titel"] is not None:
        p.pruefe(f"{wo}: Seitentitel 26 px", m["titel"], "26px")
    p.pruefe(f"{wo}: alle {m['anzahl']} Knöpfe und Felder mit 12 px Ecke", m["ecken"], [])
    p.pruefe(f"{wo}: alle Ziele mindestens 48 px hoch", m["klein"], [])
    return m


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=STILL)
    await tab.cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "light"}])  # hell
    await tab.browser_uhr_fest(seed["uhr_ms"])
    await tab.anmelden(seed["cookies"][MONTEUR])
    for breite, hoehe in GROESSEN:
        await tab.fenster(breite, hoehe, mobil=True)
        for a in SEITEN:
            wo = f"{a.name} {breite}×{hoehe}"
            p.pruefe(f"{wo}: geladen", await tab.oeffnen(a.pfad.format(**seed), BEREIT, timeout=45), True)
            await _messen(tab, p, wo)
            await tab.bild(f"{a.name}_{breite}")
        # Dialog „Zeit nachtragen“ in „Meine Zeiten“
        await tab.oeffnen("/mobil/zeiten", BEREIT, timeout=45)
        await tab.js("document.getElementById('nachtragenKnopf').click()")
        await tab.warten("document.getElementById('zeitDialog').open")
        wo = f"Dialog Zeit nachtragen {breite}×{hoehe}"
        await _messen(tab, p, wo, "document.getElementById('zeitDialog')")
        p.pruefe(f"{wo}: Knopfleiste im Bild", await tab.js(
            "(r=>r.top>=0&&r.bottom<=innerHeight)(document.getElementById('zdSpeichern').getBoundingClientRect())"), True)
        await tab.bild(f"dialog_zeit_nachtragen_{breite}")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung="Monteursrahmen mit .ds-tablet (1.9.88)", uhr=UHR))
