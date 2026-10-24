"""Klicktest: abschließende Aktion wartet auf laufendes Speichern; Zeitlimit (1.8.96, Baustein app/templates/_speichern.html,
Vorgabe 1.8.96 Punkte 1 und 2).

Einsatzbericht (Wartung) mit einem Pflicht-Prüfpunkt "Freitext" (beantwortet: "vorher") und einem freien Prüfpunkt, als Büro auf der
Berichtsseite (seit 1.9.67 /service-reports/{id}, bis 1.9.66 je Bericht auf der Seite des Auftrags). „Bericht abschließen“ wartet das
Speichern der Seite ab, fragt „Noch offen“ frisch und sendet dann über abschliessen() -- geändert wird deshalb in Schritt 1, danach in
Schritt 5 unterschrieben (bis 1.9.66 während der Kunde unterschrieb):

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


async def _zeichnen(tab, flaeche: str) -> None:
    """Ein Strich mit echten Mausereignissen quer über die Unterschriftsfläche (seit 1.9.64 über Tab.strich())."""
    await tab.strich(f"document.getElementById('{flaeche}')", weite=14)


async def _unterschreiben(tab, bericht: int, zwischen=None) -> None:
    """Seit 1.9.67 auf der Berichtsseite: zwischen() ändert in Schritt 1 einen Prüfpunkt (das Speichern hält der Test zurück), dann Schritt
    „Unterschrift“: beide Flächen, Namen, „Bericht abschließen“ -- die Seite wartet das Speichern ab, fragt „Noch offen“ frisch und sendet
    erst dann über abschliessen() (bis 1.9.66: Monteur, dann Kunde im Unterschriften-Panel der Seite des Auftrags)."""
    if zwischen is not None:
        await zwischen()
    await tab.js("document.getElementById('schritt-unterschrift').click();true")
    await tab.warten("!!document.getElementById('padKunde')", 10)
    await _zeichnen(tab, "padMonteur")
    await _zeichnen(tab, "padKunde")
    await tab.js("(f=>{f.value='Bernd Bauherr';f.dispatchEvent(new Event('input',{bubbles:true}))})(document.getElementById('signKundeName'));true")
    await tab.warten("!document.getElementById('abschliessenKnopf').disabled", 10)
    await tab.js("document.getElementById('abschliessenKnopf').click();true")


def _status(bericht: int, auftrag: int) -> str:
    return (f"fetch('/api/orders/{auftrag}/service-reports').then(r=>r.json()).then(l=>(l.items||l).find(x=>x.id==={bericht}).status)")


def _wert(bericht: int) -> str:
    return f"fetch('/api/service-reports/{bericht}/inspection-items').then(r=>r.json()).then(l=>l[0].notes)"


def _sign_gesendet(bericht: int) -> str:
    return f"performance.getEntriesByType('resource').filter(e=>e.name.endsWith('/service-reports/{bericht}/sign')).length"


VERLASSEN = "(()=>{const e=new Event('beforeunload',{cancelable:true});window.dispatchEvent(e);return e.defaultPrevented})()"


async def _oeffnen_mit_pruefpunkten(tab, p, auftrag: int, bericht: int, punkt: int) -> None:
    """Seit 1.9.67 die Berichtsseite, Schritt 1 (bis 1.9.66 die Seite des Auftrags mit aufgeklapptem Block „Prüfpunkte“)."""
    await tab.oeffnen(f"/service-reports/{bericht}", "typeof PUNKTE!=='undefined'&&PUNKTE.length>0&&!document.getElementById('raster').hidden")
    await tab.warte_auf_ruhe()
    if not await tab.warten(f"!!document.getElementById('text-{punkt}')", 10):
        p.pruefe(f"Prüfpunkt {punkt} sichtbar", False, True)


async def _eintragen(tab, punkt: int, text: str) -> None:
    await tab.js(f"(()=>{{const el=document.getElementById('text-{punkt}');el.value='{text}';"
                 "el.dispatchEvent(new Event('change',{bubbles:true}))})()")


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
    p.pruefe("Warten: keine Meldungen, keine JS-Fehler", [await tab.js("window.__alerts"), await tab.js(
        "document.getElementById('meldung').textContent"), tab.fehler], [[], "", []])
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
    await tab.warten("document.getElementById('signStatus').textContent.startsWith('Nicht ausgeführt')", 10)
    await tab.warte_auf_ruhe()
    # seit 1.9.67 ohne „Fehler: “ davor (die Berichtsseite zeigt die Meldung des Bausteins wörtlich)
    p.pruefe("Scheitern: Meldung an der Unterschrift", await tab.js("document.getElementById('signStatus').textContent"),
             "Nicht ausgeführt: ein Speichern auf der Seite ist gescheitert (Prüfpunkt nicht gefunden.). Bitte prüfen und "
             "erneut versuchen.")
    p.pruefe("Scheitern: Unterschrift nie gesendet, Bericht Entwurf", [await tab.js(_sign_gesendet(bericht)),
             await tab.js(_status(bericht, auftrag))], [0, "entwurf"])
    # seit 1.9.67 in der Meldungszeile der Seite (bis 1.9.66 per alert())
    p.pruefe("Scheitern: das Speichern meldet seinen Fehler", await tab.js("document.getElementById('meldung').textContent"),
             "Prüfpunkt nicht gefunden.")
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
    await tab.warten("document.getElementById('meldung').textContent.length>0", 6)
    meldung = "Keine Antwort vom Server nach 2 Sekunden – unklar, ob gespeichert wurde. Bitte die Seite neu laden und prüfen."
    p.pruefe("Zeitlimit: Meldung des Bereichs", await tab.js("document.getElementById('meldung').textContent"), meldung)
    p.pruefe("Zeitlimit: Hinweis oben mit 'Seite neu laden'", await tab.js(
        "(e=>e&&[e.querySelector('.dk-text').textContent,e.querySelector('button').textContent,getComputedStyle(e).position])"
        "(document.getElementById('dkSpeichernUnklar'))"), [meldung, "Seite neu laden", "fixed"])
    p.pruefe("Zeitlimit: nichts wartet mehr, keine Warnung beim Verlassen", await tab.js(VERLASSEN), False)
    await tab.bild("zeitlimit_hinweis")
    await _unterschreiben(tab, bericht)
    await tab.warten("document.getElementById('signStatus').textContent.startsWith('Nicht ausgeführt')", 6)
    p.pruefe("Zeitlimit: Unterschrift abgelehnt, nicht gesendet", [await tab.js("document.getElementById('signStatus').textContent"),
             await tab.js(_sign_gesendet(bericht)), await tab.js(_status(bericht, auftrag))],
             ["Nicht ausgeführt: bei einem Speichern auf der Seite ist unklar, ob es gespeichert wurde. Bitte die Seite neu "
              "laden und prüfen.", 0, "entwurf"])
    await tab.js("document.querySelector('#dkSpeichernUnklar button').click(); true")
    await asyncio.sleep(1.0)
    await _oeffnen_mit_pruefpunkten(tab, p, auftrag, bericht, punkt)
    p.pruefe("Zeitlimit: nach dem Neuladen steht der gespeicherte Wert da, kein Hinweis", [await tab.js(
        f"document.getElementById('text-{punkt}').value"), await tab.js(
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
