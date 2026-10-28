"""Klicktest: der Verlauf lesbar (1.9.123, Stufe 5, R1 Nachrunde, Punkt 5, Merkliste 7b) -- /history und der Verlauf der Akte.

Testdaten der Bildgrundlage (scripts/bildgrundlage.py). Als Büro – Finanzen die Menge einer Auftragsposition um 1 erhöht (über die Schnittstelle
aus der Seite), dann:

    /history       die Zeile „Auftragsposition · Menge“ zeigt „850 → 851 m²“ (Bild); in der ganzen Tabelle kein „.000000“, kein ISO-Tag
                   („2026-10-14“), kein Zeitartcode („site“), die Zeitbuchungen mit „Baustellenzeit“ und deutschen Stunden
    Akte           Reiter „Verlauf“ (seit 1.9.129 statt des Reiters „Historie“ der Projektmappe; eine Zeile je Aktion, die Änderung in den
                   aufgeklappten Einzelheiten): dieselbe Änderung „850 → 851 m²“, dieselben Prüfungen (ohne Zeitbuchungen -- der Verlauf
                   der Akte führt keine); Bild

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_verlauf_lesbar.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Stehende Uhr der Bildgrundlage.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bildgrundlage as bg  # noqa: E402
from cdp_klicktest import klicktest_main  # noqa: E402

ROH = (r"(()=>{const t=document.querySelector(SEL).innerText;return {nullen:/\.0{4,}/.test(t),iso:/\b\d{4}-\d{2}-\d{2}\b/.test(t),"
       r"code:/(^|[\s·])site([\s·]|$)/m.test(t),baustelle:t.includes('Baustellenzeit')}})()")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1440, 900)
    await tab.anmelden(seed["cookies"][bg.BUERO])
    await tab.oeffnen(f"/orders/{seed['auftrag']}", "order&&order.items&&order.items.length>0", timeout=45)
    geaendert = await tab.js(
        "(async()=>{const i=order.items.find(x=>!x.is_addendum);const r=await fetch(`/api/orders/${order.id}/items/${i.id}`,"
        "{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({quantity:String(Number(i.quantity)+1)})});"
        "return [r.status,Number(i.quantity),i.unit]})()")
    p.pruefe("Menge einer Auftragsposition um 1 erhöht (850 m²)", geaendert, [200, 850, "m²"])

    await tab.oeffnen("/history", "document.querySelectorAll('#rows tr').length>5", timeout=45)
    zeile = await tab.js("[...document.querySelectorAll('#rows tr')].map(t=>t.innerText.replace(/\\s+/g,' '))"
                         ".find(t=>t.includes('Auftragsposition')&&t.includes('Menge'))||''")
    p.pruefe("/history: „850 → 851 m²“", "850 → 851 m²" in zeile, True)
    p.pruefe("/history: kein „.000000“, kein ISO-Tag, kein „site“, Zeitbuchungen mit „Baustellenzeit“",
             await tab.js(ROH.replace("SEL", "'#rows'")), {"nullen": False, "iso": False, "code": False, "baustelle": True})
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.bild("history_lesbar")

    # seit 1.9.129: der Verlauf der Akte (Reiter „Verlauf“, #verlaufListe, eine .vl-zeile je Aktion) statt #historyRows der Projektmappe;
    # die Werte stehen in den Einzelheiten (<details>), aufgeklappt, damit innerText sie liefert
    await tab.oeffnen(f"/projects/{seed['projekt']}#verlauf",
                      "typeof project!=='undefined'&&project&&project.id&&verlaufDaten&&!document.getElementById('reiter-verlauf').hidden"
                      "&&document.querySelectorAll('#verlaufListe .vl-zeile').length>3", timeout=45)
    await tab.js("document.querySelectorAll('#verlaufListe details').forEach(d=>d.open=true)")
    zeile = await tab.js("[...document.querySelectorAll('#verlaufListe .vl-zeile')].map(t=>t.innerText.replace(/\\s+/g,' '))"
                         ".find(t=>t.includes('Auftragsposition')&&t.includes('Menge'))||''")
    p.pruefe("Akte, Verlauf: „850 → 851 m²“", "850 → 851 m²" in zeile, True)
    p.pruefe("Akte, Verlauf: kein „.000000“, kein ISO-Tag, kein „site“",
             {k: v for k, v in (await tab.js(ROH.replace("SEL", "'#verlaufListe'"))).items() if k != "baustelle"},
             {"nullen": False, "iso": False, "code": False})
    await tab.bild("akte_verlauf_lesbar")
    p.pruefe("JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(bg.befuellen, pruefen, beschreibung=__doc__, uhr=bg.UHR, zeitlimit_je_schritt=True,
                            chrome_argumente=bg.CHROME_ARGUMENTE))
