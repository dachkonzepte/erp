"""Klicktest: die Akzentfarbe ändert nur ein Administrator (1.8.130, Runde 1d, Vorgabe vom 19.10.2026, Punkt 2).

Bis 1.8.129 sah und speicherte jede Büro-Rolle unter Einstellungen -> Erscheinungsbild die Akzentfarbe (PUT /api/settings/appearance ab
Büro – Auftrag), die sofort für alle Benutzer gilt. Seit 1.8.130 nur der Administrator, in Oberfläche und API.

    Büro            Büro – Finanzen und Büro – Auftrag: Erscheinungsbild ohne Akzentfarbe (Feld, Knopf, Menü- und Untertitel), Logos
                    bleiben; kein JS-Fehler (die Listener hängen am Admin); PUT aus der Seite 403; hell und dunkel
    Admin           Feld und Knopf da; Speichern -> "Gespeichert.", nach dem Neuladen gilt die neue Farbe -- auch für das Büro
Seit 1.9.5 färbt die Akzentfarbe die Oberfläche nicht mehr, nur App-Symbol und Leiste des Browsers der Monteursansicht: geprüft wird sie
am Manifest (theme_color); --accent der Seite bleibt beim Tippen und nach dem Speichern --ds-aktion-text (bis 1.9.4 Vorschau beim Tippen
und neue Farbe auf der Seite).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_akzentfarbe.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BEREIT = ("document.getElementById('companyLogoFile')&&document.getElementById('settings-appearance').offsetParent!==null"
          "&&document.getElementById('sidebarLogoHeight')")
AKZENT = "getComputedStyle(document.documentElement).getPropertyValue('--accent').trim().toLowerCase()"
NEU = "#7c3aed"
MANIFEST = "fetch('/manifest.json').then(r=>r.json()).then(d=>d.theme_color.toLowerCase())"
AKTION_TEXT = "getComputedStyle(document.documentElement).getPropertyValue('--ds-aktion-text').trim().toLowerCase()"
PUT = ("fetch('/api/settings/appearance',{method:'PUT',headers:{'Content-Type':'application/json'},"
       f"body:JSON.stringify({{accent_color:'{NEU}'}})}}).then(r=>r.status)")
SICHTBAR = ("(()=>{const m=document.querySelector('[data-settings-section=appearance] .menu-sub');"
            "const s=document.querySelector('#settings-appearance .section-title .muted');"
            "return [!!document.getElementById('accentColorPicker'),!!document.querySelector('[onclick=\"saveAccentColor()\"]'),"
            "m.textContent.includes('Akzentfarbe'),s.textContent.includes('Akzentfarbe'),"
            "!!document.getElementById('companyLogoFile')]})()")


def befuellen(db, k):
    from app.models import AppUser
    from app.settings import load_general_settings

    nutzer = {name: AppUser(username=name, display_name=f"{name.title()} Test", role=rolle, password_hash=k.passwort())
              for name, rolle in (("anna", "admin"), ("bernd", "buero_finanzen"), ("berta", "buero_auftrag"))}
    db.add_all(nutzer.values())
    db.flush()
    return {"cookies": {name: k.cookies(u) for name, u in nutzer.items()}, "vorher": load_general_settings(db).accent_color.lower()}


async def pruefen(tab, seed, p):
    vorher = seed["vorher"]
    for name in ("bernd", "berta"):
        await tab.anmelden(seed["cookies"][name])
        p.pruefe(f"{name}: Einstellungen geladen", await tab.oeffnen("/settings#appearance", BEREIT), True)
        for thema in ("light", "dark"):
            # das Thema erst auf einer Seite des ERP (about:blank hat keinen localStorage), dann eine neue Adresse, damit neu geladen wird
            await tab.js(f"localStorage.setItem('erp_theme','{thema}')")
            p.pruefe(f"{name} {thema}: Erscheinungsbild geladen", await tab.oeffnen(f"/settings?thema={thema}#appearance", BEREIT), True)
            await tab.warte_auf_ruhe()
            p.pruefe(f"{name} {thema}: Akzentfarbe nicht da, Logos schon", await tab.js(SICHTBAR), [False, False, False, False, True])
            p.pruefe(f"{name} {thema}: keine JS-Fehler", tab.fehler, [])
            await tab.bild(f"akzentfarbe_{name}_{thema}")
        p.pruefe(f"{name}: PUT aus der Seite 403", await tab.js(PUT), 403)
        p.pruefe(f"{name}: Farbe unverändert (Manifest)", await tab.js(MANIFEST), vorher)

    await tab.anmelden(seed["cookies"]["anna"])
    await tab.js("localStorage.setItem('erp_theme','light')")
    p.pruefe("Admin: Erscheinungsbild geladen", await tab.oeffnen("/settings?thema=light#appearance", BEREIT), True)
    p.pruefe("Admin: Akzentfarbe da", await tab.warten("document.getElementById('accentColorText').value.length===7", 15), True)
    p.pruefe("Admin: Feld, Knopf, Menü und Untertitel", await tab.js(SICHTBAR), [True, True, True, True, True])
    await tab.js(f"const t=document.getElementById('accentColorText');t.value='{NEU}';t.dispatchEvent(new Event('input'))")
    p.pruefe("Admin: keine Vorschau auf der Seite (--accent bleibt --ds-aktion-text)",
             [await tab.js(AKZENT), await tab.js(AKZENT) == await tab.js(AKTION_TEXT)], [await tab.js(AKTION_TEXT), True])
    await tab.js("document.querySelector('[onclick=\"saveAccentColor()\"]').click()")
    p.pruefe("Admin: gespeichert", await tab.warten("document.getElementById('accentColorStatus').textContent==='Gespeichert.'", 15), True)
    await tab.bild("akzentfarbe_admin")
    p.pruefe("Admin: keine JS-Fehler", tab.fehler, [])
    p.pruefe("Admin nach dem Neuladen: Manifest mit der neuen Farbe, Seite unverändert",
             await tab.oeffnen("/settings?neu=1#appearance", BEREIT) and [await tab.js(MANIFEST), await tab.js(AKZENT) == await tab.js(AKTION_TEXT)],
             [NEU, True])

    await tab.anmelden(seed["cookies"]["bernd"])
    p.pruefe("Büro: Manifest mit der neuen Farbe, Seite unverändert",
             await tab.oeffnen("/settings?neu=2#appearance", BEREIT) and [await tab.js(MANIFEST), await tab.js(AKZENT) == await tab.js(AKTION_TEXT)],
             [NEU, True])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
