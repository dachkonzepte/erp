"""Klicktest: Zeitlimit beim Hochladen erst ab dem Ende der Übertragung (1.8.99, Vorgabe vom 14.10.2026, Vorweg 96-1).

Bis 1.8.98 lief das Zeitlimit des Bausteins (app/templates/_speichern.html) ab dem Senden: eine Datei, deren Übertragung länger dauert als
das Zeitlimit, endete als "unklar", obwohl sie noch lief, und der Bereich nahm bis zum Neuladen nichts mehr an. Seit 1.8.99 geht ein
Hochladen über XMLHttpRequest und die Uhr läuft erst ab dem Ende der Übertragung.

    Kundenakte      Zeitlimit für den Test 2 s (window.__dkZeitlimit vor dem Laden), Upload im Browser auf 100 KB/s gedrosselt
                    (Network.emulateNetworkConditions), eine Datei mit 400 KB über "Dokumente" hochgeladen: die Übertragung dauert
                    rund 4 s -- kein Hinweis "unklar", Meldung "1 Datei(en) hochgeladen.", die Datei in der Liste und am Server mit
                    voller Größe, die Anfrage lief als XHR und dauerte länger als das Zeitlimit; danach ein zweites Dokument ohne
                    Drosselung (der Bereich nimmt weiter an)

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_hochladen.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

ZEITLIMIT = "window.__dkZeitlimit=2000;"
GROESSE = 400_000
DROSSEL = 100_000  # Bytes je Sekunde beim Hochladen


def befuellen(db, k):
    from app.models import AppUser, Customer

    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    kunde = Customer(name="Kunde Hochladen", last_name="Hochladen", city="Uebach")
    db.add_all([bea, kunde]); db.flush()
    return {"kunde": kunde.id, "cookies": k.cookies(bea)}


async def _datei_waehlen(tab, pfad: Path) -> None:
    wurzel = (await tab.cmd("DOM.getDocument"))["root"]["nodeId"]
    knoten = (await tab.cmd("DOM.querySelector", nodeId=wurzel, selector="#docFiles"))["nodeId"]
    await tab.cmd("DOM.setFileInputFiles", files=[str(pfad)], nodeId=knoten)
    await tab.js("showSelectedDocs(); true")


async def pruefen(tab, seed, p):
    kid = seed["kunde"]
    datei = tab.shots.parent / "foto_gross.jpg"
    datei.write_bytes(os.urandom(GROESSE))
    klein = tab.shots.parent / "notiz.txt"
    klein.write_bytes(b"kleine Datei")
    skript = (await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=ZEITLIMIT))["identifier"]
    await tab.anmelden(seed["cookies"])
    await tab.oeffnen(f"/customers/{kid}", "document.getElementById('lastName')?.value==='Hochladen'")
    await tab.warte_auf_neu_geladene_liste()
    p.pruefe("Zeitlimit für den Test 2 s", await tab.js("window.__dkZeitlimit"), 2000)

    await tab.cmd("Network.emulateNetworkConditions", offline=False, latency=0, downloadThroughput=-1, uploadThroughput=DROSSEL)
    await _datei_waehlen(tab, datei)
    marke = len(tab.netz.verlauf)
    await tab.js("void uploadDocuments(); true")
    fertig = await tab.warten("/hochgeladen|Fehler/.test(document.getElementById('docUploadStatus').textContent)", 30)
    await tab.cmd("Network.emulateNetworkConditions", offline=False, latency=0, downloadThroughput=-1, uploadThroughput=-1)
    await tab.warte_auf_ruhe()
    await tab.nachlesen()
    p.pruefe("Hochladen über eine langsame Verbindung: fertig, kein Hinweis 'unklar'", [
        fertig, await tab.js("document.getElementById('docUploadStatus').textContent"),
        await tab.js("!!document.getElementById('dkSpeichernUnklar')")], [True, "1 Datei(en) hochgeladen.", False])
    posts = tab.netz.suche(rf"/api/customers/{kid}/documents$", "POST", ab=marke)
    dauer = (posts[0]["ts_antwort"] - posts[0]["ts_start"]) if posts and posts[0]["ts_antwort"] and posts[0]["ts_start"] else None
    p.pruefe("Hochladen: eine Anfrage als XHR, Status 200, länger als das Zeitlimit unterwegs",
             [len(posts), posts[0]["art"] if posts else None, posts[0]["status"] if posts else None, dauer is not None and dauer > 2.0],
             [1, "XHR", 200, True])
    gespeichert = await tab.js(f"fetch('/api/customers/{kid}/documents').then(r=>r.json())"
                               ".then(d=>d.map(x=>[x.original_filename,x.file_size]))")
    p.pruefe("Hochladen: die Datei am Server mit voller Größe", gespeichert, [["foto_gross.jpg", GROESSE]])
    await tab.bild("hochgeladen_langsam")

    await _datei_waehlen(tab, klein)
    await tab.js("void uploadDocuments(); true")
    fertig = await tab.warten("/hochgeladen|Fehler/.test(document.getElementById('docUploadStatus').textContent)", 15)
    p.pruefe("Danach ein zweites Dokument im selben Bereich", [fertig, await tab.js(
        "document.getElementById('docUploadStatus').textContent")], [True, "1 Datei(en) hochgeladen."])
    p.pruefe("JS-Fehler", tab.fehler, [])
    await tab.cmd("Page.removeScriptToEvaluateOnNewDocument", identifier=skript)
    print("Dateien:", json.dumps(await tab.js(f"fetch('/api/customers/{kid}/documents').then(r=>r.json()).then(d=>d.length)")), flush=True)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
