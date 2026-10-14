"""Klicktest: "Alle Sitzungen beenden" meldet auch die vertrauten Geräte ab (1.8.106, Korrektur 103-2 der zweiten Vorgabe vom
14.10.2026).

    Liste           Benutzerverwaltung als Anna (Administratorin): Bert (Administrator) hat keine Sitzung, aber ein vertrautes
                    Gerät -- Spalte "Sitzungen" 0 mit "1 vertrautes Gerät", der Knopf "Alle Sitzungen beenden" steht da; Clara ohne
                    beides ohne Knopf
    Beenden         Klick: die Rückfrage nennt die vertrauten Geräte, danach (neu geladen) kein Gerät und kein Knopf mehr bei Bert;
                    auf dem Server ist das Gerät abgemeldet (GET /api/users von außen)
    Hell/dunkel     Liste in beiden Themes ohne JS-Fehler

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_vertraute_geraete.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402
from klicktest_anmelden import DIALOGE  # noqa: E402
from klicktest_anmeldung_abgelaufen import _anfrage  # noqa: E402


def befuellen(db, k):
    from app import device_trust
    from app.models import AppUser

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    bert = AppUser(username="bert", display_name="Bert Admin", role="admin", password_hash=k.passwort())
    clara = AppUser(username="clara", display_name="Clara Büro", role="buero_auftrag", password_hash=k.passwort())
    db.add_all([anna, bert, clara]); db.flush()
    device_trust.create_trust(db, bert)
    return {"bert": bert.id, "clara": clara.id, "cookies_anna": k.cookies(anna)}


def _zeile(uid: int) -> str:
    return f"document.querySelector('[data-sitzungen=\"{uid}\"]').closest('tr')"


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source=DIALOGE)
    await tab.anmelden(seed["cookies_anna"])
    await tab.fenster(1400, 900)
    b, c = seed["bert"], seed["clara"]
    knopf = f"{_zeile(b)}.querySelector('[data-klick=\"sitzungen-beenden\"]')"
    await tab.oeffnen("/users", f"document.querySelector('[data-sitzungen=\"{b}\"]')")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    p.pruefe("Liste: Bert ohne Sitzung, mit einem vertrauten Gerät",
             await tab.js(f"[document.querySelector('[data-sitzungen=\"{b}\"]').firstChild.textContent.trim(),"
                          f"document.querySelector('[data-geraete=\"{b}\"]')?.textContent.trim()]"),
             ["0", "1 vertrautes Gerät"])
    p.pruefe("Liste: Knopf bei Bert, nicht bei Clara",
             await tab.js(f"[!!{knopf}, !!{_zeile(c)}.querySelector('[data-klick=\"sitzungen-beenden\"]')]"), [True, False])
    await tab.bild("benutzer_vertraute_geraete_hell")

    await tab.warte_auf_neu_geladene_liste(f"{knopf}.click()", "#rows")
    p.pruefe("Beenden: Rückfrage nennt die vertrauten Geräte",
             await tab.js("window.__confirms.length===1 && window.__confirms[0].includes('Auch alle vertrauten Geräte sind danach "
                          "abgemeldet')"), True)
    p.pruefe("Beenden: danach kein Gerät und kein Knopf bei Bert",
             await tab.js(f"[!!document.querySelector('[data-geraete=\"{b}\"]'), !!{knopf}]"), [False, False])
    status, _, liste = _anfrage(tab.base, "/api/users", seed["cookies_anna"])
    p.pruefe("Server: Bert ohne vertrautes Gerät", (status, next(u["trusted_device_count"] for u in liste if u["id"] == b)), (200, 0))

    await tab.js("document.documentElement.setAttribute('data-theme','dark')")
    await tab.bild("benutzer_vertraute_geraete_dunkel")
    p.pruefe("JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
