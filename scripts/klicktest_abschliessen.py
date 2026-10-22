"""Klicktest: abschließende Aktion wartet auf laufendes Speichern; Zeitlimit (1.8.96, Baustein app/templates/_speichern.html,
Vorgabe 1.8.96 Punkte 1 und 2).

Einsatzbericht (Wartung) mit einem Pflicht-Prüfpunkt "Freitext" (beantwortet: "vorher") und einem freien Prüfpunkt, als Büro auf der
Berichtsseite des Auftrags. Seit 1.9.36 öffnet die Unterschrift erst, wenn nichts mehr offen ist (Prüfung nach dem Speichern der Seite),
ebenso der Schritt zum Kunden -- geändert wird deshalb, während der Kunde unterschreibt (bis 1.9.35 vor dem Öffnen der Unterschrift,
mit unbeantwortetem Pflichtpunkt):

    Warten          Monteur unterschreibt; beim Kunden den Prüfpunkt ändern, das Speichern hält zurück (die Anfrage geht noch nicht
                    hinaus); Kunde unterschreibt: die Unterschrift geht nicht hinaus, solange der Prüfpunkt nicht gespeichert ist (Bericht bleibt
                    Entwurf, die Seite warnt beim Verlassen); nach der Freigabe erst der Prüfpunkt, dann die Unterschrift -- der
                    Bericht ist unterschrieben, mit dem eingetragenen Wert. Ohne das Warten käme die Unterschrift vor dem Prüfpunkt an
                    und der Server lehnte sie ab (Pflicht-Prüfpunkt offen).
    Scheitern       Zweiter Bericht: Speichern des freien Prüfpunkts zurückhalten (seit 1.9.36 lässt sich ein Pflichtpunkt nicht
                    löschen), unterschreiben, dann den Prüfpunkt anderswo löschen und
                    freigeben -- das Speichern scheitert (404), die Unterschrift läuft nicht ("Nicht ausgeführt: …"), der Bericht
                    bleibt Entwurf. Ohne die Prüfung wäre er ohne den Pflicht-Prüfpunkt unterschrieben.
    Zeitlimit       Dritter Bericht, Zeitlimit für den Test auf 2 s (window.__dkZeitlimit vor dem Laden der Seite): die Antwort auf das
                    Speichern hält zurück (der Server hat gespeichert) -- nach 2 s Meldung "unklar, ob gespeichert", Hinweis oben mit
                    "Seite neu laden", kein "Speichert …" mehr; die Unterschrift wird abgelehnt (Bereich unklar); nach dem Neuladen
                    zeigt die Seite den gespeicherten Wert.

`confirm()` und `alert()` werden automatisch bestätigt und mitgeschrieben. Feste Uhr 10:00.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_abschliessen.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

# Seit 1.8.108 (klicktest_alle.py --gleichzeitig): Zeitlimit 2 s und Fenster, in denen nichts gesendet werden darf -- unter Last schwächer
ALLEIN = "Zeitlimit 2 s über window.__dkZeitlimit; Fenster von 0,6-1 s, in denen nichts gesendet werden darf"

DIALOGE = ("window.__confirms=[];window.confirm=m=>{window.__confirms.push(String(m));return true};"
           "window.__alerts=[];window.alert=m=>{window.__alerts.push(String(m))};")
ZEITLIMIT = "window.__dkZeitlimit=2000;"


def befuellen(db, k):
    from decimal import Decimal

    from app.models import AppUser, Customer, Employee, Order, Project
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.service_reports import add_inspection_item, create_report, update_inspection_item

    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True,
                   hourly_wage=Decimal("22.00"))
    db.add(mia); db.flush()
    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    kunde = Customer(name="Bauherr Abschluss", last_name="Abschluss")
    db.add_all([anna, kunde]); db.flush()
    projekt = Project(project_number="P-KT-AB", name="Dach Ost", customer_id=kunde.id, pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AUF-KT-AB", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-1", title="Dach Ost",
                    customer_name="Bauherr Abschluss", property_name="Halle", property_address="Weg 1\n12345 Stadt")
    db.add(auftrag); db.commit()
    berichte, punkte, freie = [], [], []
    for nr in (1, 2, 3):
        bericht = create_report(db, auftrag.id, "wartung", description=f"Wartung {nr}", created_by_employee_id=mia.id)
        punkt = add_inspection_item(db, bericht["id"], f"Dachrinne frei ({nr})", "free_text", required=True)
        update_inspection_item(db, punkt["id"], {"notes": "vorher"})  # seit 1.9.36: sonst öffnet die Unterschrift nicht
        frei = add_inspection_item(db, bericht["id"], f"Bemerkung ({nr})", "free_text")
        berichte.append(bericht["id"]); punkte.append(punkt["id"]); freie.append(frei["id"])
    return {"order": auftrag.id, "reports": berichte, "items": punkte, "frei": freie, "cookies": {"anna": k.cookies(anna)}}


async def _zeichnen(tab) -> None:
    """Ein Strich mit echten Mausereignissen quer über die Unterschriftsfläche."""
    await tab.js("document.getElementById('sigCanvas').scrollIntoView({block:'center'}); true")
    await asyncio.sleep(0.2)
    r = await tab.js("(()=>{const r=document.getElementById('sigCanvas').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
    x0, y0 = r[0] + 25, r[1] + r[3] / 2
    await tab.cmd("Input.dispatchMouseEvent", type="mousePressed", x=x0, y=y0, button="left", buttons=1, clickCount=1)
    for i in range(1, 12):
        await tab.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=x0 + i * 14, y=y0 + (12 if i % 2 else -12), button="left", buttons=1)
    await tab.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=x0 + 160, y=y0, button="left", buttons=0, clickCount=1)


async def _unterschreiben(tab, bericht: int, zwischen=None) -> None:
    """Monteur (Schritt 1) und Kunde (Schritt 2); der zweite Klick sendet -- über abschliessen(). Seit 1.9.36 öffnet die Unterschrift
    erst nach der Prüfung „Noch offen“ (GET …/noch-offen nach dem Speichern der Seite), ebenso der Schritt zum Kunden; zwischen() läuft,
    wenn der Schritt des Kunden offen ist (dort ändert der Test einen Prüfpunkt, während unterschrieben wird)."""
    await tab.js(f"void openSignPanel({bericht}); true")
    await tab.warten("!document.getElementById('signCard').classList.contains('hidden')", 10)
    await _zeichnen(tab)
    await tab.js("document.getElementById('signatureName').value='Anna Admin';document.getElementById('signNextBtn').click();true")
    await tab.warten("document.getElementById('signHeading').textContent==='Unterschrift Kunde'", 10)
    if zwischen is not None:
        await zwischen()
    await _zeichnen(tab)
    await tab.js("document.getElementById('signatureName').value='Bernd Bauherr';document.getElementById('signNextBtn').click();true")


def _status(bericht: int, auftrag: int) -> str:
    return (f"fetch('/api/orders/{auftrag}/service-reports').then(r=>r.json()).then(l=>(l.items||l).find(x=>x.id==={bericht}).status)")


def _wert(bericht: int) -> str:
    return f"fetch('/api/service-reports/{bericht}/inspection-items').then(r=>r.json()).then(l=>l[0].notes)"


def _sign_gesendet(bericht: int) -> str:
    return f"performance.getEntriesByType('resource').filter(e=>e.name.endsWith('/service-reports/{bericht}/sign')).length"


VERLASSEN = "(()=>{const e=new Event('beforeunload',{cancelable:true});window.dispatchEvent(e);return e.defaultPrevented})()"


async def _oeffnen_mit_pruefpunkten(tab, p, auftrag: int, bericht: int, punkt: int) -> None:
    await tab.oeffnen(f"/orders/{auftrag}/service-reports", "typeof reports!=='undefined'&&reports.length===3")
    await tab.warte_auf_neu_geladene_liste()
    await tab.js(f"void toggleReportInspectionItems({bericht})")
    await tab.warten(f"(inspectionItemsCache[{bericht}]||[]).length>0", 10)
    await tab.warte_auf_neu_geladene_liste()
    await tab.js(f"toggleReportArea({bericht},'none'); true")  # Block "Prüfpunkte" (ohne Dachfläche) aufklappen
    if not await tab.warten(f"!!document.querySelector('.ictl[data-item=\"{punkt}\"] input')", 10):
        p.pruefe(f"Prüfpunkt {punkt} sichtbar", False, True)


async def _eintragen(tab, punkt: int, text: str) -> None:
    await tab.js(f"(()=>{{const el=document.querySelector('.ictl[data-item=\"{punkt}\"] input');el.value='{text}';"
                 "el.dispatchEvent(new Event('change'))})()")


async def _warten(tab, seed, p):
    auftrag, bericht, punkt = seed["order"], seed["reports"][0], seed["items"][0]
    await _oeffnen_mit_pruefpunkten(tab, p, auftrag, bericht, punkt)
    await tab.zurueckhalten(rf"/api/inspection-items/{punkt}$", "PUT", art="anfrage")

    async def eintragen():
        await _eintragen(tab, punkt, "Dach dicht")
        await tab.warte_bis_gehalten(1, beantwortet=False)
        p.pruefe("Warten: Seite warnt beim Verlassen, solange das Speichern wartet", await tab.js(VERLASSEN), True)
    await _unterschreiben(tab, bericht, eintragen)
    await tab.warten("false", 1.0, melden=False)  # Zeit, in der eine nicht wartende Seite die Unterschrift schon gesendet hätte
    p.pruefe("Warten: Unterschrift nicht gesendet, Bericht Entwurf", [await tab.js(_sign_gesendet(bericht)),
             await tab.js(_status(bericht, auftrag))], [0, "entwurf"])
    await tab.freigeben()
    await tab.warten(f"{_sign_gesendet(bericht)}>0", 10)
    await tab.warte_auf_ruhe()
    p.pruefe("Warten: nach der Freigabe unterschrieben, mit dem Wert des Prüfpunkts",
             [await tab.js(_status(bericht, auftrag)), await tab.js(_wert(bericht))], ["unterschrieben", "Dach dicht"])
    p.pruefe("Warten: Reihenfolge Prüfpunkt, dann Unterschrift", await tab.js(
        "performance.getEntriesByType('resource').map(e=>e.name).filter(n=>/inspection-items\\/\\d+$|\\/sign$/.test(n))"
        ".map(n=>n.endsWith('/sign')?'sign':'pruefpunkt')"), ["pruefpunkt", "sign"])
    p.pruefe("Warten: danach keine Warnung beim Verlassen", await tab.js(VERLASSEN), False)
    p.pruefe("Warten: keine Meldungen, keine JS-Fehler", [await tab.js("window.__alerts"), tab.fehler], [[], []])
    await tab.bild("warten_unterschrieben")


async def _scheitern(tab, seed, p):
    auftrag, bericht, punkt = seed["order"], seed["reports"][1], seed["frei"][1]  # seit 1.9.36 der freie Punkt
    await _oeffnen_mit_pruefpunkten(tab, p, auftrag, bericht, punkt)
    await tab.zurueckhalten(rf"/api/inspection-items/{punkt}$", "PUT", art="anfrage")

    async def eintragen():
        await _eintragen(tab, punkt, "Rinne voll Laub")
        await tab.warte_bis_gehalten(1, beantwortet=False)
    await _unterschreiben(tab, bericht, eintragen)
    await tab.warten("false", 0.6, melden=False)
    # Jemand anderes löscht den Prüfpunkt (Testhandlung, direkt an der API vorbei am Baustein).
    p.pruefe("Scheitern: Prüfpunkt anderswo gelöscht", await tab.js(
        f"fetch('/api/inspection-items/{punkt}',{{method:'DELETE'}}).then(r=>r.status)"), 200)
    await tab.freigeben()
    await tab.warten("document.getElementById('signStatus').textContent.startsWith('Fehler: Nicht ausgeführt')", 10)
    await tab.warte_auf_ruhe()
    p.pruefe("Scheitern: Meldung an der Unterschrift", await tab.js("document.getElementById('signStatus').textContent"),
             "Fehler: Nicht ausgeführt: ein Speichern auf der Seite ist gescheitert (Prüfpunkt nicht gefunden.). Bitte prüfen und "
             "erneut versuchen.")
    p.pruefe("Scheitern: Unterschrift nie gesendet, Bericht Entwurf", [await tab.js(_sign_gesendet(bericht)),
             await tab.js(_status(bericht, auftrag))], [0, "entwurf"])
    p.pruefe("Scheitern: das Speichern meldet seinen Fehler", await tab.js("window.__alerts"), ["Fehler: Prüfpunkt nicht gefunden."])
    p.pruefe("Scheitern: JS-Fehler", tab.fehler, [])
    await tab.bild("scheitern_nicht_unterschrieben")


async def _zeitlimit(tab, seed, p):
    auftrag, bericht, punkt = seed["order"], seed["reports"][2], seed["items"][2]
    skript = (await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=ZEITLIMIT))["identifier"]
    await _oeffnen_mit_pruefpunkten(tab, p, auftrag, bericht, punkt)
    p.pruefe("Zeitlimit: für den Test 2 s", await tab.js("window.__dkZeitlimit"), 2000)
    await tab.zurueckhalten(rf"/api/inspection-items/{punkt}$", "PUT")  # Antwort zurückhalten: der Server speichert
    await _eintragen(tab, punkt, "Rinne gereinigt")
    await tab.warte_bis_gehalten(1)
    p.pruefe("Zeitlimit: vor Ablauf kein Hinweis, Warnung beim Verlassen", [await tab.js(
        "!!document.getElementById('dkSpeichernUnklar')"), await tab.js(VERLASSEN)], [False, True])
    await tab.warten("window.__alerts.length>0", 6)
    meldung = "Keine Antwort vom Server nach 2 Sekunden – unklar, ob gespeichert wurde. Bitte die Seite neu laden und prüfen."
    p.pruefe("Zeitlimit: Meldung des Bereichs", await tab.js("window.__alerts"), ["Fehler: " + meldung])
    p.pruefe("Zeitlimit: Hinweis oben mit 'Seite neu laden'", await tab.js(
        "(e=>e&&[e.querySelector('.dk-text').textContent,e.querySelector('button').textContent,getComputedStyle(e).position])"
        "(document.getElementById('dkSpeichernUnklar'))"), [meldung, "Seite neu laden", "fixed"])
    p.pruefe("Zeitlimit: nichts wartet mehr, keine Warnung beim Verlassen", await tab.js(VERLASSEN), False)
    await tab.bild("zeitlimit_hinweis")
    await _unterschreiben(tab, bericht)
    await tab.warten("document.getElementById('signStatus').textContent.startsWith('Fehler:')", 6)
    p.pruefe("Zeitlimit: Unterschrift abgelehnt, nicht gesendet", [await tab.js("document.getElementById('signStatus').textContent"),
             await tab.js(_sign_gesendet(bericht)), await tab.js(_status(bericht, auftrag))],
             ["Fehler: Nicht ausgeführt: bei einem Speichern auf der Seite ist unklar, ob es gespeichert wurde. Bitte die Seite neu "
              "laden und prüfen.", 0, "entwurf"])
    await tab.js("document.querySelector('#dkSpeichernUnklar button').click(); true")
    await asyncio.sleep(1.0)
    await _oeffnen_mit_pruefpunkten(tab, p, auftrag, bericht, punkt)
    p.pruefe("Zeitlimit: nach dem Neuladen steht der gespeicherte Wert da, kein Hinweis", [await tab.js(
        f"document.querySelector('.ictl[data-item=\"{punkt}\"] input').value"), await tab.js(
        "!!document.getElementById('dkSpeichernUnklar')")], ["Rinne gereinigt", False])
    p.pruefe("Zeitlimit: JS-Fehler", tab.fehler, [])
    await tab.cmd("Page.removeScriptToEvaluateOnNewDocument", identifier=skript)


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=DIALOGE)
    await tab.anmelden(seed["cookies"]["anna"])
    await _warten(tab, seed, p)
    await _scheitern(tab, seed, p)
    await _zeitlimit(tab, seed, p)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
