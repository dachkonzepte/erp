"""Seit 1.9.47: die Rückfrage „Prüfpunkt … löschen?“ im Einsatzbericht (rueckfrage(), seit 1.9.67 in service_report.html für jedes
Löschen der Berichtsseite, bis 1.9.66 in service_reports.html) wertet ein close-Ereignis
nur, wenn der Dialog danach wirklich zu ist (Esc).

    Befund         Chrome liefert das close eines früheren Schließens („Abbrechen“) mitunter erst beim nächsten Öffnen aus -- die neue
                   Rückfrage nahm es als Esc und schloss sich sofort mit „nein“, der Klick auf „Löschen“ ging ins Leere
                   (klicktest_monteurin_regeln wackelte, in einer Messkopie 4 von 4 Mal)
    jetzt          ein close bei offenem Dialog zählt nicht; Esc (Dialog zu, dann close) weiter „nein“
"""

import json
import re

from tests import vorlagen_js as vj
from tests.node_lauf import node_ausfuehren

ATTRAPPE = """
const ereignisse={};
const dialog={open:false,addEventListener:(n,f)=>{(ereignisse[n]=ereignisse[n]||[]).push(f)},
  removeEventListener:(n,f)=>{ereignisse[n]=(ereignisse[n]||[]).filter(x=>x!==f)},
  showModal(){this.open=true},close(){this.open=false}};
function feuern(n){(ereignisse[n]||[]).slice().forEach(f=>f())}
const knoepfe={rueckfrageJa:{onclick:null,textContent:''},rueckfrageNein:{onclick:null,focus(){}}};
const document={getElementById:id=>id==='rueckfrageDialog'?dialog:(knoepfe[id]||{textContent:''})};
function el(id){return document.getElementById(id)}
"""


def _rueckfrage() -> str:
    text, _ = vj.seitentext("service_report.html")
    m = re.search(r"function rueckfrage\(titel,text,ja\)\{.*?\n\}\n", text, flags=re.S)
    assert m, "rueckfrage() nicht gefunden"
    return m.group(0)


def _lauf(ablauf: str):
    return node_ausfuehren(ATTRAPPE + _rueckfrage() + "\n(async()=>{" + ablauf + "})()"
                           ".then(e=>process.stdout.write(JSON.stringify(e)))")


def test_altes_close_beim_naechsten_oeffnen_zaehlt_nicht():
    """Angriff: „Abbrechen“ (das close kommt verspätet), neu öffnen, dann trifft das alte close ein -- die Rückfrage bleibt offen,
    „Löschen“ antwortet „ja“."""
    ergebnis = _lauf("""
      const erste=rueckfrage('A','A','Löschen'); knoepfe.rueckfrageNein.onclick(); const a=await erste;
      const zweite=rueckfrage('B','B','Löschen'); feuern('close');   // das verspätete close des ersten Schließens
      const offen=dialog.open; knoepfe.rueckfrageJa.onclick();
      return [a, offen, await zweite];""")
    assert ergebnis == [False, True, True]


def test_esc_antwortet_nein():
    """Gegenprobe: Esc schließt den Dialog (zu, dann close) -- „nein“, wie bisher."""
    ergebnis = _lauf("""
      const p=rueckfrage('C','C','Löschen'); dialog.close(); feuern('close');
      return [dialog.open, await p];""")
    assert ergebnis == [False, False]
    assert json.dumps(ergebnis)  # nur Werte, keine Objekte
