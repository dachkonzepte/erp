"""Klicktest: neue Ordnung von Seitenleiste und Einstellungen, Stufe 1 "Ordnen" (1.8.112).

Geprüft wird im echten Browser, je Rolle (Monteur, Büro – Auftrag, Büro – Finanzen, Admin):

    Seitenleiste      Gruppen mit Überschrift und ihre Einträge (seit 1.8.162 vier: Übersicht, Aufträge, Kaufmännisch mit
                      „Zeiten“ -- bis 1.9.97 Zeiterfassung und Backoffice --, Verwaltung), "Plantafel" und "Befunde" statt "Planung" und "Mängel", kein
                      Versandprotokoll; jeder sichtbare Link
                      liefert als dieselbe Rolle weder 403 noch 404
    Einstellungen     Menü je Rolle (zehn Gruppen; nur für Admin: Anbindungen, Module, Benutzer und Zugriff, Wartungen,
                      Projekt-Pipeline, Aufgaben, Vor Ort; Kalkulation nur Finanzen und Admin), jeder Menüpunkt öffnet seinen
                      Bereich mit der erwarteten Überschrift und Adresse, jeder Link im Menü öffnet ohne 403/404, keine JS-Fehler
    Inhalt            Textbausteine nur die Vor- und Schlusstexte, Auswahllisten ohne sie; Zeit-Listen mit Einträgen; Mahn-
                      Rechtstexte für das Büro lesbar, nicht änderbar; Fristen und Erinnerungen mit den Vorlaufzeiten der Rolle;
                      "Logo im PDF" unter Erscheinungsbild
    Speichern         Zeitregeln (Admin; seit 1.9.61 ohne Standardpause), Zeitart hinzufügen und löschen (Büro – Auftrag), Logo im PDF
                      (Büro – Finanzen),
                      Vorlaufzeit Betriebsmittel (Büro – Auftrag) und Wartungen (Admin) -- je nach dem Neuladen noch da
    Frühere Adressen  #recurring-costs, #incoming-invoices, #operational-assets öffnen "Fristen und Erinnerungen"; ein für die
                      Rolle ausgeblendeter Bereich (#modules, #labor-rate) die Unternehmensdaten; /time-backoffice mit
                      #workmodels, #settings und #options führt (seit 1.9.98 über „Zeiten“) in die Einstellungen, „Zeiten“ hat
                      keine Reiter dafür, verlinkt die Einrichtung im „⋮“

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_neue_ordnung.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

ROLLEN = ("field", "buero_auftrag", "buero_finanzen", "admin")

SEITENLEISTE_BUERO = [
    ["Übersicht", ["Start", "Aufgaben", "Kalender"]],
    ["Aufträge", ["Anfragen", "Projekte", "Plantafel", "Checklisten", "Wartungen", "Befunde"]],
    ["Kaufmännisch", ["Finanzen", "Mahnwesen", "Eingangsrechnungen", "Betriebskosten", "Zeiten"]],  # bis 1.9.97 Zeiterfassung, Backoffice
    ["Verwaltung", ["Stammdaten", "Einstellungen"]],
]  # seit 1.8.162 vier Gruppen (bis dahin dazu Personal, Stammdaten und System)


def seitenleiste(rolle):
    if rolle == "field":
        return [["Übersicht", ["Start"]], ["Kaufmännisch", ["Zeiten"]]]  # bis 1.9.97 „Zeiterfassung“; „Zeiten“ führt sie zu „Meine Zeiten“
    if rolle == "buero_auftrag":
        return [[g, [x for x in e if x not in ("Eingangsrechnungen", "Betriebskosten")]] for g, e in SEITENLEISTE_BUERO]
    return SEITENLEISTE_BUERO


def menue(rolle):
    admin, finanzen = rolle == "admin", rolle in ("admin", "buero_finanzen")
    gruppen = [
        ["Firma", ["Unternehmensdaten", "Erscheinungsbild"]],
        ["Finanzen", ["Nummernkreise", "Steuer", "Zahlungsbedingungen", "Mahnwesen"]],
        ["Kalkulation", ["Stundenverrechnungssatz", "Kalkulationsgrundlagen", "Kontenstamm"]] if finanzen else None,
        ["Vorlagen und Texte", ["Dokumentlayout", "E-Mail-Vorlagen", "Textbausteine", "Checklisten-Vorlagen", "Prüfvorlagen"]],
        ["Rechtstexte", ["Vertragsgrundlagen", "Vertragsvorlagen", "Vorbehalte", "Mahn-Rechtstexte"]],
        ["Listen", ["Auswahllisten", "Dachaufbau", "Bauteilarten", "Dokumentkategorien", "Zeitarten", "Tätigkeiten",
                    "Abwesenheitsarten"]],
        ["Betrieb", ["Arbeitszeit und Kalender", "Fristen und Erinnerungen"]
         + (["Wartungen", "Projekt-Pipeline", "Aufgaben", "Vor Ort"] if admin else [])],
        ["Personal", ["Funktionen", "Zeitregeln und DATEV"]],
        ["Anbindungen", ["E-Mail und Microsoft 365", "Outlook-Kalender", "KI", "Adressimport"]] if admin else None,
        ["System", (["Module", "Benutzer und Zugriff"] if admin else []) + ["Versandprotokoll", "Änderungshistorie", "Changelog"]],
    ]
    return [g for g in gruppen if g]


UEBERSCHRIFTEN = {
    "general": "Unternehmensdaten", "appearance": "Erscheinungsbild", "numbers": "Nummernkreise", "tax-keys": "Steuer",
    "payment-terms": "Zahlungsbedingungen", "reminder-levels": "Mahnwesen", "labor-rate": "Stundenkostenverrechnungssatz",
    "calculation": "Weitere Kalkulationsgrundlagen", "accounts": "Kontenstamm", "document-layout": "Dokumentlayout",
    "email-templates": "E-Mail-Vorlagen", "text-blocks": "Textbausteine", "contract-bases": "Vertragsgrundlagen",
    "contract-templates": "Vertragsvorlagen", "notice-reservations": "Vorbehalte", "dunning-legal-texts": "Mahn-Rechtstexte",
    "option-lists": "Auswahllisten", "roof-layers": "Dachaufbau", "component-types": "Bauteilarten",
    "document-categories": "Dokumentkategorien", "time-entry-types": "Zeitarten", "time-entry-activities": "Tätigkeiten",
    "absence-types": "Abwesenheitsarten", "planning": "Arbeitszeit und Kalender", "deadlines": "Fristen und Erinnerungen",
    "maintenance": "Wartungen", "project-pipeline": "Projekt-Pipeline", "tasks": "Aufgaben", "mobile": "Vor Ort",
    "employee-functions": "Mitarbeiterfunktionen", "time-rules": "Zeitregeln und DATEV",
    "email-settings": "E-Mail und Microsoft 365", "outlook-sync": "Outlook-Kalender", "ai-settings": "KI-Anbieter",
    "modules": "Module",
}
TEXTBAUSTEINE = ["Angebots-Vortexte", "Angebots-Schlusstexte", "Rechnungs-Vortexte", "Rechnungs-Schlusstexte",
                 "Rechnungs-Schlusstexte bei Erstattung"]

_SICHTBAR = "(a=>a.getClientRects().length>0&&getComputedStyle(a).visibility!=='hidden')"
_STATUS = ("(async links=>{const r={};for(const h of [...new Set(links)]){"
           "r[h]=(await fetch(h.split('#')[0],{credentials:'same-origin'})).status}return r})")
# Seitenleiste als [[Gruppe, [Einträge]]] in der Reihenfolge der Seite.
_LEISTE = ("(()=>{const r=[];for(const el of document.querySelectorAll('#appSidebar nav > *')){"
           "if(el.classList.contains('app-sidebar-group'))r.push([el.textContent.trim(),[]]);"
           "else if(el.matches('a.app-sidebar-link')&&r.length)r[r.length-1][1].push(el.querySelector('.app-sidebar-label').textContent.trim())}"
           "return r})()")
_LEISTE_LINKS = (f"[...document.querySelectorAll('#appSidebar a[href]')].filter({_SICHTBAR})"
                 ".map(a=>a.getAttribute('href')).filter(h=>h.startsWith('/'))")
# Menü der Einstellungen: [[Gruppe, [Menüpunkte]]] -- Beschriftung ohne die Unterzeile (.menu-sub).
_MENUE = ("(()=>{const r=[];for(const el of document.querySelectorAll('.settings-sidebar > *')){"
          "if(el.classList.contains('settings-group'))r.push([el.textContent.trim(),[]]);"
          "else if(el.classList.contains('settings-menu')&&r.length)for(const b of el.querySelectorAll('button'))"
          "r[r.length-1][1].push(b.childNodes[0].textContent.trim())}return r})()")
_AKTIV = ("(()=>{const s=[...document.querySelectorAll('.settings-section')].filter(x=>x.classList.contains('active'));"
          "return s.map(x=>({id:x.id,h2:x.querySelector('h2').textContent.trim(),sichtbar:x.offsetHeight>0}))})()")


def befuellen(db, k):
    from decimal import Decimal

    from app.models import AppUser, Employee

    leute = [Employee(employee_number=f"M-{i}", first_name=v, last_name="Ordnung", employee_group="angestellt",
                      weekly_hours=Decimal("40"), active=True) for i, v in enumerate(("Max", "Bea"), start=1)]
    db.add_all(leute); db.flush()
    users = {rolle: AppUser(username=rolle, display_name=rolle, role=rolle, password_hash=k.passwort(),
                            employee_id=leute[0 if rolle == "field" else 1].id) for rolle in ROLLEN}
    db.add_all(users.values())
    db.commit()
    return {"cookies": {rolle: k.cookies(user) for rolle, user in users.items()}}


async def einstellungen_oeffnen(tab, hash_=""):
    ok = await tab.oeffnen(f"/settings{hash_}", "document.querySelector('.settings-menu')&&window.__dkAnfragen")
    return ok and await tab.warte_auf_neu_geladene_liste()


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument",
                  source="window.alert=m=>console.error('alert(): '+m);window.confirm=()=>true")
    await tab.fenster(1400, 900)
    for rolle in ROLLEN:
        await tab.anmelden(seed["cookies"][rolle])
        # --- Seitenleiste ---
        if rolle == "field":
            # seit 1.8.164 hat die Monteurin auch auf der Kontoseite den Monteurskopf (bis dahin die Seitenleiste mit Start, Zeiterfassung)
            if not await tab.oeffnen("/account", "document.getElementById('mobileHeaderWrap')"):
                p.pruefe(f"{rolle} /account: Seite geladen", False, True)
                continue
            p.pruefe(f"{rolle}: Monteurskopf statt Seitenleiste", await tab.js(
                "[!!document.getElementById('appSidebar'),[...document.querySelectorAll('.mobile-nav-reiter')].map(a=>a.textContent.trim())]"),
                [False, ["Heute", "Meine Zeiten"]])  # seit 1.9.59
            status = await tab.js(f"{_STATUS}([...document.querySelectorAll('.mobile-nav-reiter')].map(a=>a.getAttribute('href')))")
            p.pruefe(f"{rolle}: Reiter ohne 403/404", sorted(h for h, s in (status or {}).items() if s in (403, 404)), [])
            p.pruefe(f"{rolle}: JS-Fehler", tab.fehler, [])
            await tab.bild(f"{rolle}_monteurskopf")
            continue
        start = "/"
        if not await tab.oeffnen(start, "document.getElementById('appSidebar')"):
            p.pruefe(f"{rolle} {start}: Seite geladen", False, True)
            continue
        p.pruefe(f"{rolle}: Seitenleiste in Gruppen", await tab.js(_LEISTE), seitenleiste(rolle))
        p.pruefe(f"{rolle}: kein Versandprotokoll in der Seitenleiste",
                 await tab.js("!!document.querySelector('#appSidebar a[href=\"/versandprotokoll\"]')"), False)
        status = await tab.js(f"{_STATUS}({_LEISTE_LINKS})")
        p.pruefe(f"{rolle}: Links der Seitenleiste ohne 403/404 ({len(status or {})})",
                 sorted(h for h, s in (status or {}).items() if s in (403, 404)), [])
        await tab.bild(f"{rolle}_seitenleiste")
        # --- Menü der Einstellungen und jeder Bereich ---
        if not await einstellungen_oeffnen(tab):
            p.pruefe(f"{rolle} /settings: Seite geladen", False, True)
            continue
        p.pruefe(f"{rolle}: Menü der Einstellungen", await tab.js(_MENUE), menue(rolle))
        links = await tab.js(f"[...document.querySelectorAll('.settings-sidebar a[href]')].map(a=>a.getAttribute('href'))")
        status = await tab.js(f"{_STATUS}({json.dumps(links or [])})")
        p.pruefe(f"{rolle}: Links im Menü ohne 403/404 ({len(status or {})})",
                 sorted(h for h, s in (status or {}).items() if s != 200), [])
        schluessel = await tab.js("[...document.querySelectorAll('[data-settings-section]')].map(b=>b.dataset.settingsSection)")
        falsch = []
        for key in schluessel:
            await tab.js(f"document.querySelector('[data-settings-section=\"{key}\"]').click()")
            aktiv = await tab.js(_AKTIV)
            adresse = await tab.js("location.hash")
            if (len(aktiv or []) != 1 or aktiv[0]["h2"] != UEBERSCHRIFTEN.get(key) or not aktiv[0]["sichtbar"]
                    or adresse != f"#{key}"):
                falsch.append((key, adresse, aktiv))
        p.pruefe(f"{rolle}: jeder der {len(schluessel)} Bereiche öffnet mit seiner Überschrift und Adresse", falsch, [])
        await tab.js("document.querySelector('[data-settings-section=\"text-blocks\"]').click()")
        texte = await tab.js("[...document.getElementById('optionGroupSelect').options].map(o=>o.textContent)")
        p.pruefe(f"{rolle}: Textbausteine nur die Vor- und Schlusstexte", texte, TEXTBAUSTEINE)
        await tab.js("document.querySelector('[data-settings-section=\"option-lists\"]').click()")
        listen = await tab.js("[...document.getElementById('optionGroupSelect').options].map(o=>o.textContent)")
        p.pruefe(f"{rolle}: Auswahllisten ohne Textbausteine, mit Mengeneinheiten",
                 ("Mengeneinheiten" in (listen or []), [x for x in (listen or []) if x in TEXTBAUSTEINE]), (True, []))
        for key, titel in (("time-entry-types", "Zeitarten"), ("time-entry-activities", "Tätigkeiten"),
                           ("absence-types", "Abwesenheitsarten")):
            await tab.js(f"document.querySelector('[data-settings-section=\"{key}\"]').click()")
            zeilen = await tab.js("document.querySelectorAll('#timeListRows [data-klick=\"zeitliste-loeschen\"]').length")
            p.pruefe(f"{rolle}: {titel} mit Einträgen", (await tab.js("document.getElementById('timeListHeading').textContent"),
                                                         (zeilen or 0) > 0), (titel, True))
        await tab.js("document.querySelector('[data-settings-section=\"dunning-legal-texts\"]').click()")
        p.pruefe(f"{rolle}: Mahn-Rechtstexte lesbar, Speichern nur für Admin",
                 await tab.js("[!!document.querySelector('#legalTextsBox [data-rechtstext]'),"
                              "document.querySelectorAll('#legalTextsBox [data-klick=\"rechtstext-speichern\"]').length>0]"),
                 [True, rolle == "admin"])
        await tab.js("document.querySelector('[data-settings-section=\"deadlines\"]').click()")
        bloecke = await tab.js("[...document.querySelectorAll('#settings-deadlines .block h3')].map(x=>x.textContent.trim())")
        p.pruefe(f"{rolle}: Fristen und Erinnerungen", bloecke,
                 (["Wartungen"] if rolle == "admin" else []) + ["Betriebsmittel – Prüf- und Wartungsfristen"]
                 + (["Betriebskosten – Kündigungsfristen", "Eingangsrechnungen – Skonto"] if rolle != "buero_auftrag" else []))
        p.pruefe(f"{rolle}: Logo im PDF unter Erscheinungsbild",
                 await tab.js("!!document.querySelector('#settings-appearance #documentLayoutBlockLogo')"
                              "&&!document.querySelector('#settings-document-layout #documentLayoutBlockLogo')"), True)
        await tab.js("document.querySelector('[data-settings-section=\"time-rules\"]').click()")
        p.pruefe(f"{rolle}: Zeitregeln und DATEV geladen (Rundung, Modelle, Personalnummern)",
                 await tab.js("[document.getElementById('rounding').value!=='',document.querySelectorAll('#workModelCards .model-card').length>0,"
                              "document.querySelectorAll('#payrollRows tr').length]"), [True, True, 2])
        # seit 1.9.61 ohne Standardpause (Stufe 4, R3 Nachrunde)
        p.pruefe(f"{rolle}: Zeitregeln ohne Standardpause", await tab.js(
            "[!!document.getElementById('defaultBreak'),document.getElementById('settings-time-rules').innerText.includes('Standardpause')]"),
            [False, False])
        p.pruefe(f"{rolle} /settings: JS-Fehler", tab.fehler, [])
        await tab.bild(f"{rolle}_einstellungen_zeitregeln")
        # --- Frühere Adressen ---
        for alt in ("#recurring-costs", "#incoming-invoices", "#operational-assets"):
            await einstellungen_oeffnen(tab, alt)
            p.pruefe(f"{rolle}: {alt} öffnet Fristen und Erinnerungen", [x["id"] for x in await tab.js(_AKTIV) or []],
                     ["settings-deadlines"])
        if rolle != "admin":
            for versteckt in ("#modules", "#email-settings") + (("#labor-rate",) if rolle == "buero_auftrag" else ()):
                await einstellungen_oeffnen(tab, versteckt)
                p.pruefe(f"{rolle}: ausgeblendeter Bereich {versteckt} öffnet die Unternehmensdaten",
                         [x["id"] for x in await tab.js(_AKTIV) or []], ["settings-general"])
        # --- Speichern je Rolle ---
        if rolle == "buero_auftrag":
            await einstellungen_oeffnen(tab, "#time-entry-types")
            await tab.js("document.getElementById('timeListLabel').value='Klicktest-Zeitart';"
                         "document.getElementById('timeListValue').value='klicktest_zeitart'")
            await tab.warte_auf_neu_geladene_liste("saveTimeListOption()", "#timeListRows")
            p.pruefe(f"{rolle}: Zeitart hinzugefügt", await tab.js(
                "[...document.querySelectorAll('#timeListRows tr')].some(r=>r.textContent.includes('Klicktest-Zeitart'))"), True)
            await tab.warte_auf_neu_geladene_liste(
                "[...document.querySelectorAll('#timeListRows tr')].find(r=>r.textContent.includes('Klicktest-Zeitart'))"
                ".querySelector('[data-klick=\"zeitliste-loeschen\"]').click()", "#timeListRows")
            p.pruefe(f"{rolle}: Zeitart gelöscht", await tab.js(
                "[...document.querySelectorAll('#timeListRows tr')].some(r=>r.textContent.includes('Klicktest-Zeitart'))"), False)
            await einstellungen_oeffnen(tab, "#deadlines")
            await tab.js("document.getElementById('operationalAssetLeadDays').value='21'")
            await tab.warte_auf_neu_geladene_liste("saveOperationalAssetSettings()")
            await einstellungen_oeffnen(tab, "#deadlines")
            p.pruefe(f"{rolle}: Vorlaufzeit Betriebsmittel nach dem Neuladen",
                     await tab.js("document.getElementById('operationalAssetLeadDays').value"), "21")
        if rolle == "buero_finanzen":
            await einstellungen_oeffnen(tab, "#appearance")
            vorher = await tab.js("document.getElementById('documentLayoutBlockLogo').checked")
            await tab.warte_auf_neu_geladene_liste("document.getElementById('documentLayoutBlockLogo').click()")
            await einstellungen_oeffnen(tab, "#appearance")
            p.pruefe(f"{rolle}: Logo im PDF umgeschaltet und gespeichert",
                     await tab.js("document.getElementById('documentLayoutBlockLogo').checked"), not vorher)
        if rolle == "admin":
            await einstellungen_oeffnen(tab, "#time-rules")
            await tab.js("document.getElementById('rounding').value='15';document.getElementById('wageSite').value='1000'")
            await tab.warte_auf_neu_geladene_liste("saveTimeRules()")
            p.pruefe(f"{rolle}: Zeitregeln gespeichert (Meldung)",
                     await tab.js("document.getElementById('timeRulesStatus').textContent"), "Zeitregeln und Lohnarten gespeichert.")
            await einstellungen_oeffnen(tab, "#time-rules")
            p.pruefe(f"{rolle}: Zeitregeln nach dem Neuladen", await tab.js(
                "[document.getElementById('rounding').value,document.getElementById('wageSite').value]"), ["15", "1000"])
            await einstellungen_oeffnen(tab, "#deadlines")
            await tab.js("document.getElementById('maintenanceLeadDays').value='45'")
            await tab.warte_auf_neu_geladene_liste("saveMaintenanceSettings('maintenanceLeadStatus')")
            p.pruefe(f"{rolle}: Vorlaufzeit Wartungen gespeichert (Meldung beim Knopf)",
                     await tab.js("document.getElementById('maintenanceLeadStatus').textContent"), "Gespeichert.")
            await einstellungen_oeffnen(tab, "#deadlines")
            p.pruefe(f"{rolle}: Vorlaufzeit Wartungen nach dem Neuladen",
                     await tab.js("document.getElementById('maintenanceLeadDays').value"), "45")
            # Backoffice: frühere Reiter führen in die Einstellungen (seit 1.9.98 über die Seite „Zeiten“, die das Backoffice ersetzt).
            for alt, ziel in (("#workmodels", "#time-rules"), ("#settings", "#time-rules"), ("#options", "#time-entry-types")):
                await tab.oeffnen(f"/time-backoffice{alt}", "location.pathname==='/settings'&&document.querySelector('.settings-menu')")
                p.pruefe(f"{rolle}: /time-backoffice{alt} führt nach /settings{ziel}",
                         await tab.js("location.pathname+location.hash"), f"/settings{ziel}")
            await tab.oeffnen("/time-backoffice", "!!window.P&&document.getElementById('monatTitel').textContent!==''")
            p.pruefe(f"{rolle}: /time-backoffice führt auf „Zeiten“ mit ihren Reitern", await tab.js(
                "[location.pathname,[...document.querySelectorAll('.reiter a')].map(a=>a.firstChild.textContent.trim())]"),
                ["/zeiten", ["Prüfen", "Buchungen", "Abwesenheiten", "Monat & Lohn"]])
            p.pruefe(f"{rolle}: „Zeiten“ verlinkt die Einrichtung im „⋮“", await tab.js(
                "[...document.querySelectorAll('#seitenkopfMenue a.ds-menue-eintrag')].map(a=>a.getAttribute('href'))"),
                ["/settings#time-rules", "/settings#time-entry-types"])
            p.pruefe(f"{rolle} /zeiten: JS-Fehler", tab.fehler, [])
    # 412 px: das Menü bleibt bedienbar
    await tab.anmelden(seed["cookies"]["buero_auftrag"])
    await tab.fenster(412, 900, mobil=True)
    await einstellungen_oeffnen(tab, "#deadlines")
    p.pruefe("412 px: keine waagrechte Scrollleiste",
             await tab.js("document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"), True)
    await tab.bild("buero_auftrag_412_fristen")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="10:00"))  # seit 1.8.164: der Reiter Einsätze führt nach /mobil
