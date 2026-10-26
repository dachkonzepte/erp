"""Klicktest: Berater- und Mandantennummer für den DATEV-Export in Einstellungen → Zeitregeln und DATEV (1.9.92, Stufe 4, R5a, Punkt 5).

    Admin           Ada: beide Felder leer und bearbeitbar, Knopf „Berater- und Mandantennummer speichern“; „123“ -> Meldung mit dem Format, nichts
                    gespeichert; „1234567“ / „12345“ -> „Gespeichert.“, gespeichert; eine ungespeicherte Änderung der Rundung bleibt stehen;
                    nach dem Neuladen stehen die Nummern da; keine JS-Fehler
    Büro – Finanzen Fin: die Nummern sichtbar, nur lesbar, kein Knopf, Hinweis „Ändern kann sie nur ein Administrator.“; derselbe PUT vom
                    Server 403; keine JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_datev_nummern.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = "document.getElementById('datevBerater')&&typeof timeRules!=='undefined'&&!!timeRules"
WERTE = "[document.getElementById('datevBerater').value,document.getElementById('datevMandant').value]"
GESPEICHERT = ("fetch('/api/time-backoffice/settings').then(r=>r.json())"
               ".then(s=>[s.datev_beraternummer,s.datev_mandantennummer])")


def befuellen(db, k):
    from app.models import AppUser

    ada = AppUser(username="ada", display_name="Ada Admin", role="admin", password_hash=k.passwort())
    fin = AppUser(username="fin", display_name="Fin Finanzen", role="buero_finanzen", password_hash=k.passwort())
    db.add_all([ada, fin])
    db.commit()
    return {"ada": k.cookies(ada), "fin": k.cookies(fin)}


async def _speichern(tab, berater: str, mandant: str) -> str:
    await tab.js(f"document.getElementById('datevBerater').value='{berater}';document.getElementById('datevMandant').value='{mandant}';"
                 "document.getElementById('datevNummernStatus').textContent=''")
    await tab.js("document.getElementById('datevNummernSpeichern').click()")
    await tab.warten("document.getElementById('datevNummernStatus').textContent.length>0", 10)
    await tab.warte_auf_ruhe()
    return await tab.js("document.getElementById('datevNummernStatus').textContent")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")

    # ---- Admin ----------------------------------------------------------------------------------------------------------------
    await tab.anmelden(seed["ada"])
    p.pruefe("Ada: Zeitregeln und DATEV geladen", await tab.oeffnen("/settings#time-rules", BEREIT), True)
    p.pruefe("Ada: Felder leer, bearbeitbar, Knopf da", await tab.js(
        f"[...{WERTE},document.getElementById('datevBerater').readOnly,!!document.getElementById('datevNummernSpeichern')]"),
        ["", "", False, True])
    # eine ungespeicherte Änderung der Zeitregeln -- das Speichern der Nummern lässt sie stehen
    await tab.js("document.getElementById('rounding').value='15'")
    p.pruefe("Ada: falsches Format mit Meldung", await _speichern(tab, "123", "1"),
             "Fehler: Bitte die Eingabe prüfen – Beraternummer: 4 bis 7 Ziffern, ab 1001 (DATEV).")
    p.pruefe("Ada: nichts gespeichert", await tab.js(GESPEICHERT), [None, None])
    p.pruefe("Ada: gespeichert", await _speichern(tab, "1234567", "12345"), "Gespeichert.")
    p.pruefe("Ada: auf dem Server", await tab.js(GESPEICHERT), ["1234567", "12345"])
    p.pruefe("Ada: die ungespeicherte Rundung bleibt stehen", await tab.js("document.getElementById('rounding').value"), "15")
    # eine eigene Query: dieselbe Adresse mit #hash lädt nicht neu
    p.pruefe("Ada: nach dem Neuladen", [await tab.oeffnen("/settings?neu=1#time-rules", BEREIT), await tab.js(WERTE)],
             [True, ["1234567", "12345"]])
    await tab.js("document.getElementById('datevBerater').scrollIntoView({block:'center'})")
    await tab.bild("einstellungen_datev_nummern")
    p.pruefe("Ada: keine JS-Fehler", tab.fehler, [])

    # ---- Büro – Finanzen: sieht, ändert nicht --------------------------------------------------------------------------------
    await tab.anmelden(seed["fin"])
    p.pruefe("Fin: Zeitregeln und DATEV geladen", await tab.oeffnen("/settings?als=fin#time-rules", BEREIT), True)
    p.pruefe("Fin: Nummern sichtbar, nur lesbar, kein Knopf, Hinweis", await tab.js(
        f"[...{WERTE},document.getElementById('datevBerater').readOnly,document.getElementById('datevMandant').readOnly,"
        "!!document.getElementById('datevNummernSpeichern'),"
        "document.getElementById('datevNummernHinweis').textContent.includes('Ändern kann sie nur ein Administrator.')]"),
        ["1234567", "12345", True, True, False, True])
    p.pruefe("Fin: derselbe PUT vom Server abgelehnt", await tab.js(
        "fetch('/api/time-backoffice/datev-nummern',{method:'PUT',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({beraternummer:'1001',mandantennummer:'1'})}).then(r=>r.status)"), 403)
    await tab.bild("einstellungen_datev_nummern_buero")
    p.pruefe("Fin: keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
