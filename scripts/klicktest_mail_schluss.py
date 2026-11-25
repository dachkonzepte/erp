"""Klicktest: der Satz unter den Mailvorlagen (1.11.19, Antwort 1.11.17-F1).

    Admin            Einstellungen → E-Mail-Vorlagen: „Darunter setzt das ERP beim Senden Name, Anschrift und Pflichtangaben aus den Firmendaten.“
                     sichtbar, direkt unter dem Feld „Text“ (Abstand höchstens 12 px, dieselbe linke Kante) -- für das Angebot und für eine
                     Mahnstufe; Einstellungen → Mahnwesen: unter „E-Mail-Text“ jeder Stufe; Bilder hell und dunkel
    Büro – Auftrag   die Mahnstufe gesperrt (Feld gesperrt, Hinweis) -- der Satz bleibt sichtbar; ebenso unter „Mahnwesen“
    Ohne Firmendaten befuellen() leert sie (Name, Anschrift, Pflichtangaben) -- der Satz steht trotzdem

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_mail_schluss.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die eigene PID beenden): siehe
scripts/cdp_klicktest.py. Feste Uhr 10:00.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

SATZ = "Darunter setzt das ERP beim Senden Name, Anschrift und Pflichtangaben aus den Firmendaten."


def befuellen(db, k):
    from app.models import AppUser
    from app.settings import load_general_settings

    s = load_general_settings(db)  # ohne Firmendaten: der Satz steht trotzdem
    for feld in ('company_name', 'street', 'postal_code', 'city', 'register_court', 'register_number', 'managing_director'):
        setattr(s, feld, "")
    admin = AppUser(username="ada", display_name="Ada Admin", role="admin", password_hash=k.passwort())
    berta = AppUser(username="berta", display_name="Berta Auftrag", role="buero_auftrag", password_hash=k.passwort())
    db.add_all([admin, berta])
    db.commit()
    return {"cookies": {"ada": k.cookies(admin), "berta": k.cookies(berta)}}


BEREIT = "document.querySelector('.settings-menu')&&typeof reminderLevels!=='undefined'&&reminderLevels.length>0"
# je Feld: Satz sichtbar, Abstand zum Feld, linke Kanten gleich, Feld gesperrt
LAGE = ("(f=>{const t=document.getElementById(f);const d=t.nextElementSibling;const sichtbar=e=>!!e&&!e.hidden&&e.offsetParent!==null;"
        "const a=t.getBoundingClientRect(),b=d.getBoundingClientRect();"
        "return {satz:d.matches('[data-mail-schluss]')?d.textContent:null,sichtbar:sichtbar(d),"
        "abstand_ok:b.top-a.bottom>=0&&b.top-a.bottom<=12,kante:Math.abs(a.left-b.left)<1,gesperrt:t.disabled}})")


async def _vorlage(tab, art):
    await tab.js("document.querySelector('[data-settings-section=\"email-templates\"]').click()")
    await tab.js(f"(()=>{{const s=document.getElementById('emailTemplateType');s.value='{art}';void loadEmailTemplate()}})()")
    await tab.warte_auf_ruhe()
    return await tab.js(f"{LAGE}('emailTemplateBody')")


async def _mahnstufen(tab):
    await tab.js("document.querySelector('[data-settings-section=\"reminder-levels\"]').click()")
    await tab.warten("document.querySelector('#reminderLevelRows textarea[id$=\"EmailBody\"]')", 15)
    return await tab.js(f"[...document.querySelectorAll('#reminderLevelRows textarea[id$=\"EmailBody\"]')].map(t=>{LAGE}(t.id))")


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1440, 900)
    await tab.anmelden(seed["cookies"]["ada"])
    await tab.oeffnen("/settings", BEREIT)
    p.pruefe("Ohne Firmendaten (in befuellen() geleert)", await tab.js(
        "fetch('/api/settings/general').then(r=>r.json()).then(s=>[s.company_name,s.street,s.postal_code,s.city,s.register_court,s.register_number,"
        "s.managing_director].every(w=>!(w||'').trim()))"), True)

    offen = {"satz": SATZ, "sichtbar": True, "abstand_ok": True, "kante": True, "gesperrt": False}
    gesperrt = {**offen, "gesperrt": True}
    p.pruefe("Admin, E-Mail-Vorlagen, Angebot: Satz direkt unter „Text“", await _vorlage(tab, "quote"), offen)
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    await tab.js("document.getElementById('emailTemplateBody').scrollIntoView({block:'center'})")
    await tab.bild("vorlagen_angebot_hell")
    await tab.js("document.documentElement.setAttribute('data-theme','dark')")
    await tab.bild("vorlagen_angebot_dunkel")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    p.pruefe("Admin, E-Mail-Vorlagen, 1. Mahnung: Satz direkt unter „Text“", await _vorlage(tab, "reminder:1"), offen)
    stufen = await _mahnstufen(tab)
    p.pruefe("Admin, Mahnwesen: unter „E-Mail-Text“ jeder Stufe", [len(stufen) >= 3, all(s == offen for s in stufen)], [True, True])
    await tab.js("document.querySelector('#reminderLevelRows textarea[id$=\"EmailBody\"]').scrollIntoView({block:'center'})")
    await tab.bild("mahnwesen_hell")
    await tab.js("document.documentElement.setAttribute('data-theme','dark')")
    await tab.bild("mahnwesen_dunkel")
    await tab.js("document.documentElement.setAttribute('data-theme','light')")
    p.pruefe("JS-Fehler (Admin)", tab.fehler, [])

    await tab.anmelden(seed["cookies"]["berta"])
    await tab.oeffnen("/settings", BEREIT)
    p.pruefe("Büro – Auftrag, E-Mail-Vorlagen, 1. Mahnung: gesperrt, Satz bleibt", await _vorlage(tab, "reminder:1"), gesperrt)
    p.pruefe("Büro – Auftrag: Hinweis „nur lesen“ sichtbar", await tab.js(
        "document.getElementById('emailTemplateGeldHinweis').offsetParent!==null"), True)
    await tab.js("document.getElementById('emailTemplateBody').scrollIntoView({block:'center'})")
    await tab.bild("vorlagen_mahnstufe_buero_auftrag")
    stufen = await _mahnstufen(tab)
    p.pruefe("Büro – Auftrag, Mahnwesen: gesperrt, Satz bleibt", [len(stufen) >= 3, all(s == gesperrt for s in stufen)], [True, True])
    p.pruefe("JS-Fehler (Büro – Auftrag)", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))
