"""Klicktest: Verbindungsprotokoll des Servers und Ausgang hängender Anfragen im Netzprotokoll (1.8.115, Vorgabe vom 16.10.2026, Punkt 2).

Prüft das Werkzeug selbst (scripts/cdp_klicktest.py) mit echtem Chrome und echtem uvicorn:

    Spur            die Instanz schreibt verbindungen.log (uvicorn trace) in ihren Arbeitsordner
    angehalten      GET /api/auth/status der Kundenakte im Netz angehalten: der Bericht nennt sie offen, nicht gesendet, und darunter
                    "Server: nicht angekommen"
    fortgesetzt     danach der Ausgang "fertig, Status 200 nach …" mit der Serverzeile (angekommen, Antwort-Kopf 200, fertig) --
                    einmal, der nächste Bericht nennt ihn nicht wieder
    gescheitert     wieder angehalten und dann am Netz gescheitert (Fetch.failRequest, wie eine abgerissene Verbindung): Ausgang
                    "fehlgeschlagen: net::ERR_CONNECTION_RESET nach …" (Network.loadingFailed), auf dem Server nie angekommen -- auch nicht
                    über die gleiche Anfrage der danach geöffneten Seite
    Seitenwechsel   angehalten, dann eine andere Seite: Chrome meldet für eine im Netz angehaltene Anfrage kein Ende -- sie bleibt "beim
                    Wechsel offen geblieben" und heißt am Ende "noch offen" (ohne fremde Serverzeile)

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_verbindungsprotokoll.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

STATUS = "*/api/auth/status"


def befuellen(db, k):
    from app.models import AppUser, Customer

    bea = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", password_hash=k.passwort())
    kunde = Customer(name="Kundin Spur", last_name="Spur")
    db.add_all([bea, kunde]); db.flush()
    return {"kunde": kunde.id, "cookies": k.cookies(bea)}


def _nach(zeilen: list[str], muster: str) -> tuple[str | None, str | None]:
    """Die erste Zeile, auf die muster passt, und die Zeile danach."""
    for i, zeile in enumerate(zeilen):
        if re.search(muster, zeile):
            return zeile, zeilen[i + 1] if i + 1 < len(zeilen) else None
    return None, None


async def pruefen(tab, seed, p):
    kid = seed["kunde"]
    await tab.anmelden(seed["cookies"])
    p.pruefe("Spur: verbindungen.log im Arbeitsordner der Instanz", bool(tab.verbindungen and tab.verbindungen.exists()
                                                                       and tab.verbindungen.name == "verbindungen.log"), True)

    # angehalten: offen, nicht gesendet, auf dem Server nicht angekommen
    await tab.im_netz_anhalten(STATUS)
    await tab.oeffnen(f"/customers/{kid}", "document.getElementById('appSidebarFoot')")
    p.pruefe("angehalten: im Netz angehalten", await tab.warte_bis_im_netz_angehalten(1), True)
    await tab.nachlesen()
    zeilen = tab.netz.bericht()
    zeile, server = _nach(zeilen, r"GET /api/auth/status \[Fetch\]")
    p.pruefe("angehalten: im Bericht offen, nicht gesendet", bool(zeile and "gesendet: nein" in zeile and "im Netz angehalten" in zeile),
             True)
    p.pruefe("angehalten: darunter die Serverzeile", (server or "").strip(),
             "Server: nicht angekommen (keine passende Anfrage im Verbindungsprotokoll)")

    # fortgesetzt: Ausgang fertig mit Status, Serverzeile mit Antwort
    p.pruefe("fortgesetzt: eine Anfrage weiter", await tab.im_netz_fortsetzen(), 1)
    p.pruefe("fortgesetzt: Seite fertig geladen", await tab.warte_auf_ruhe(), True)
    await tab.nachlesen()
    ausgang = tab.netz.ausgang_bericht(noch_offen=False)
    zeile, server = _nach(ausgang, r"GET /api/auth/status \[Fetch\]")
    p.pruefe("fortgesetzt: Ausgang 'fertig, Status 200'", bool(zeile and re.search(r"-> fertig, Status 200 nach \d+,\d s$", zeile)),
             True)
    p.pruefe("fortgesetzt: Serverzeile angekommen, Antwort-Kopf 200, fertig",
             bool(server and re.search(r"Server: \[\d+\] angekommen \+\d+,\d s, Antwort-Kopf 200 \+.*, fertig \+", server)), True)
    p.pruefe("fortgesetzt: der Ausgang kommt nur einmal", tab.netz.ausgang_bericht(noch_offen=False), [])
    p.pruefe("keine JS-Fehler", tab.fehler, [])

    # gescheitert: loadingFailed als Ausgang
    await tab.im_netz_anhalten(STATUS)
    await tab.oeffnen(f"/customers/{kid}", "document.getElementById('appSidebarFoot')")
    p.pruefe("gescheitert: im Netz angehalten", await tab.warte_bis_im_netz_angehalten(1), True)
    await tab.nachlesen()
    tab.netz.bericht()
    [fetch_id] = list(tab.netz.angehalten)
    await tab.cmd("Fetch.failRequest", requestId=fetch_id, errorReason="ConnectionReset")
    tab.netz.fortgesetzt(fetch_id)
    await tab.cmd("Fetch.disable")
    await tab.oeffnen("/projects", "document.getElementById('appSidebarFoot')")  # dieselbe Anfrage, diesmal gesendet
    await tab.warte_auf_ruhe()
    await tab.nachlesen()
    ausgang = tab.netz.ausgang_bericht(noch_offen=False)
    zeile, server = _nach(ausgang, r"GET /api/auth/status \[Fetch\]")
    p.pruefe("gescheitert: Ausgang 'fehlgeschlagen' mit errorText des Browsers",
             bool(zeile and re.search(r"-> fehlgeschlagen: net::ERR_CONNECTION_RESET nach \d+,\d s$", zeile)), True)
    p.pruefe("gescheitert: auf dem Server nie angekommen (nicht die Anfrage der nächsten Seite)", (server or "").strip(),
             "Server: nicht angekommen (keine passende Anfrage im Verbindungsprotokoll)")

    # Seitenwechsel: kein Ende vom Browser, am Ende "noch offen"
    await tab.im_netz_anhalten(STATUS)
    await tab.oeffnen(f"/customers/{kid}", "document.getElementById('appSidebarFoot')")
    p.pruefe("Seitenwechsel: im Netz angehalten", await tab.warte_bis_im_netz_angehalten(1), True)
    await tab.nachlesen()
    tab.netz.bericht()
    await tab.oeffnen("/projects", "document.getElementById('appSidebarFoot')")  # angehalten wird weiter, auch die neue Anfrage
    await tab.warte_bis_im_netz_angehalten(2)
    await tab.im_netz_fortsetzen()  # die alte ist mit ihrem Dokument verschwunden, die neue geht weiter
    await tab.warte_auf_ruhe()
    await tab.nachlesen()
    ende = tab.netz.ausgang_bericht(noch_offen=True)
    zeile, server = _nach(ende, r"GET /api/auth/status \[Fetch\]")
    p.pruefe("Seitenwechsel: am Ende 'noch offen', ohne fremde Serverzeile",
             [bool(zeile and "-> noch offen nach" in zeile), (server or "").strip()],
             [True, "Server: nicht angekommen (keine passende Anfrage im Verbindungsprotokoll)"])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
