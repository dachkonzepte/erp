"""Klicktest: Feierabend in /mobil als POST (1.8.106, Korrektur 103-3 der zweiten Vorgabe vom 14.10.2026).

Nach der Feierabend-Uhrzeit (Vorgabe 19:00) meldet GET /api/field-view/today nur noch "feierabend" (401) und schreibt nichts -- die
Ausnahme von Regel 23 aus 1.8.103 ist weg. /mobil beendet die Sitzung dann per POST /api/field-view/feierabend über speichern() und geht
zur Anmeldung.

    Ohne Browser    Mias Handy (eigene Sitzung): GET /api/field-view/today -> 401 mit "feierabend", danach gilt die Sitzung weiter
    /mobil          Mias Tablet öffnet /mobil: genau ein POST /api/field-view/feierabend mit 200, die Seite landet auf /login?next=/mobil,
                    das Anmelde-Cookie im Browser ist weg, kein JS-Fehler
    Server          der Wert des Tablets von außen -> 401 (auf dem Server beendet), das Handy bleibt angemeldet (nur dieses Gerät)
    POST scheitert  zweites Tablet, der POST im Browser blockiert (wie ein Netzausfall): /mobil bleibt mit "Abmelden fehlgeschlagen"
                    stehen, kein Weg zu /login (dorthin mit gültiger Sitzung hieße: zurück nach /mobil, im Kreis), ein GET, ein POST

Feste Uhr 20:00 (die Instanz läuft heute ab 20:00 Europe/Berlin).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_feierabend.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_anmeldung_abgelaufen import _anfrage  # noqa: E402


def befuellen(db, k):
    from decimal import Decimal

    from app.models import AppUser, Employee

    mia = Employee(employee_number="E-1", first_name="Mia", last_name="Monteurin", employee_group="gewerblich", active=True,
                   hourly_wage=Decimal("22.00"))
    db.add(mia); db.flush()
    user = AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=mia.id, password_hash=k.passwort())
    db.add(user); db.flush()
    return {"tablet": k.cookies(user), "handy": k.cookies(user), "tablet2": k.cookies(user)}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    status, _, daten = _anfrage(tab.base, "/api/field-view/today", seed["handy"])
    p.pruefe("Ohne Browser: GET meldet den Feierabend", (status, (daten or {}).get("feierabend")), (401, True))
    p.pruefe("Ohne Browser: danach gilt die Sitzung des Handys weiter (der GET schrieb nichts)",
             _anfrage(tab.base, "/api/field-view/upcoming", seed["handy"])[0], 200)

    await tab.fenster(412, 900, mobil=True)

    # POST scheitert (im Browser blockiert): die Seite bleibt stehen, keine Schleife über /login
    await tab.cmd("Network.setBlockedURLs", urls=["*/api/field-view/feierabend*"])
    await tab.anmelden(seed["tablet2"])
    marke = len(tab.netz.verlauf)
    await tab.oeffnen("/mobil", "document.getElementById('assignmentsList').textContent.includes('Abmelden fehlgeschlagen')")
    await tab.warten("false", 1.5, melden=False)
    p.pruefe("POST scheitert: /mobil bleibt mit der Meldung stehen",
             await tab.js("[location.pathname, document.getElementById('assignmentsList').textContent.includes('Abmelden fehlgeschlagen')]"),
             ["/mobil", True])
    p.pruefe("POST scheitert: ein GET und ein POST, kein Kreis über /login",
             [len(tab.netz.suche(r"/api/field-view/today$", "GET", ab=marke)), len(tab.netz.suche(r"/api/field-view/feierabend$", "POST", ab=marke)),
              len(tab.netz.suche(r"/login", None, ab=marke))], [1, 1, 0])
    p.pruefe("POST scheitert: die Sitzung gilt weiter", _anfrage(tab.base, "/api/field-view/upcoming", seed["tablet2"])[0], 200)
    p.pruefe("POST scheitert: JS-Fehler", tab.fehler, [])
    await tab.bild("feierabend_post_gescheitert")
    await tab.cmd("Network.setBlockedURLs", urls=[])

    await tab.anmelden(seed["tablet"])
    marke = len(tab.netz.verlauf)
    await tab.oeffnen("/mobil", "location.pathname==='/login'")
    await tab.warten("document.readyState==='complete'")
    posts = tab.netz.suche(r"/api/field-view/feierabend$", "POST", ab=marke)
    p.pruefe("/mobil: genau ein POST /api/field-view/feierabend mit 200", [e["status"] for e in posts], [200])
    p.pruefe("/mobil: weiter zur Anmeldung", await tab.js("location.pathname+location.search"), "/login?next=%2Fmobil")
    cookies = (await tab.cmd("Network.getCookies", urls=[tab.base]))["cookies"]
    p.pruefe("/mobil: Anmelde-Cookie im Browser gelöscht", sorted(c["name"] for c in cookies if c["name"] == "dk_erp_auth"), [])
    p.pruefe("Server: der Wert des Tablets von außen gilt nicht mehr", _anfrage(tab.base, "/api/field-view/upcoming", seed["tablet"])[0],
             401)
    p.pruefe("Server: das Handy bleibt angemeldet", _anfrage(tab.base, "/api/field-view/upcoming", seed["handy"])[0], 200)
    p.pruefe("JS-Fehler", tab.fehler, [])
    await tab.bild("feierabend_login")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="20:00"))
