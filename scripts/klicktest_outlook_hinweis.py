"""Klicktest: der Hinweis unter Outlook-Kalender erscheint nur, wenn Zugangsdaten fehlen (1.8.118, Vorgabe vom 16.10.2026, Punkt 4).

Bis 1.8.117 stand "Unter „E-Mail und Microsoft 365“ sind noch keine vollständigen Microsoft-365-Zugangsdaten hinterlegt …" immer da:
settings.html hatte keine CSS-Regel für die Klasse "hidden", mit der loadOutlookSyncSettings() ihn ausblendet.

    ohne Zugangsdaten   Einstellungen -> Outlook-Kalender: Hinweis sichtbar
    eingetragen         unter E-Mail und Microsoft 365 Mandanten-ID, Client-ID, Secret, Postfach gespeichert -- der Hinweis ist ohne
                        Neuladen weg (das Speichern liest ihn neu), auch nach dem Neuladen; hell und dunkel

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_outlook_hinweis.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

HINWEIS = "document.getElementById('outlookGraphMissingHint')"
SICHTBAR = f"(()=>{{const h={HINWEIS};return !!h&&getComputedStyle(h).display!=='none'&&h.offsetParent!==null}})()"
GELADEN = "document.getElementById('outlookSyncEnabled')&&document.getElementById('graphSecretHint').textContent.length>0"


def befuellen(db, k):
    from app.models import AppUser

    anna = AppUser(username="anna", display_name="Anna Admin", role="admin", password_hash=k.passwort())
    db.add(anna); db.flush()
    return {"anna": k.cookies(anna)}


async def pruefen(tab, seed, p):
    await tab.anmelden(seed["anna"])
    p.pruefe("ohne Zugangsdaten: Seite geladen", await tab.oeffnen("/settings#outlook-sync", GELADEN), True)
    await tab.warte_auf_ruhe()
    p.pruefe("ohne Zugangsdaten: Hinweis sichtbar", await tab.js(SICHTBAR), True)
    await tab.bild("outlook_ohne")

    await tab.js("showSettingsSection('email')")
    for feld, wert in (("graphTenantId", "mandant-1"), ("graphClientId", "client-1"), ("graphClientSecret", "geheim-1"),
                       ("graphSenderMailbox", "erp@example.org")):
        await tab.js(f"document.getElementById('{feld}').value='{wert}'")
    await tab.js("saveGraphSettings()")
    p.pruefe("eingetragen: gespeichert", await tab.warten(
        "document.getElementById('emailSettingsStatus').textContent.startsWith('Gespeichert')", 15), True)
    await tab.warte_auf_ruhe()
    await tab.js("showSettingsSection('outlook-sync')")
    p.pruefe("eingetragen: Hinweis ohne Neuladen weg", await tab.js(SICHTBAR), False)

    for thema in ("light", "dark"):
        await tab.js(f"localStorage.setItem('erp_theme','{thema}')")
        # eine andere Adresse (Query), sonst ist es nur ein Sprung im Dokument und nichts lädt neu
        await tab.js("window.__dkVorDemNeuladen=1")
        p.pruefe(f"nach dem Neuladen ({thema}): Seite geladen", await tab.oeffnen(f"/settings?thema={thema}#outlook-sync", GELADEN), True)
        p.pruefe(f"nach dem Neuladen ({thema}): wirklich neu geladen", await tab.js("window.__dkVorDemNeuladen===undefined"), True)
        await tab.warte_auf_ruhe()
        p.pruefe(f"nach dem Neuladen ({thema}): Hinweis weg", await tab.js(SICHTBAR), False)
        await tab.bild(f"outlook_mit_{thema}")
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
