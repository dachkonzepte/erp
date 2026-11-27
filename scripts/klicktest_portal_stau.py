"""Klicktest: der Stau-Hinweis des Postboten auf „Start“ (1.11.7, Stufe P1c; Bauplan P1, Abschnitt 4; seit 1.11.9 überarbeitet, Antwort 1.11.7-1/-3).

    Modul aus           kein Hinweis, keine Anfrage an /api/kundenportal/postbote
    Modul an            ohne Aufträge kein Hinweis
    ohne Webseite       seit 1.11.47: Hinweis „Impressum und Datenschutz fehlen“ mit Link „Unternehmensdaten öffnen“ (/settings#general), für jede
                        Büro-Rolle; mit Webseite (in die Datenbank geschrieben) weg
    wartet              ein Auftrag wartet seit 3 Minuten -> Hinweis „wartet seit über 2 Minuten“: Büro „bitte den Administrator informieren“ (Büro –
                        Finanzen und Büro – Auftrag), der Admin mit dem Dienst; Warnhinweis (Fläche und Rand) mit Link „Versandprotokoll öffnen“,
                        kein „Erledigt“
    gescheitert         der zuletzt erledigte Auftrag scheiterte -> „ging nicht hinaus“; „Erledigt“ nur beim Admin
    Link                „Versandprotokoll öffnen“ führt ins Versandprotokoll, Filter „Art“ = Anmeldecode des Kundenportals
    Erledigt            der Admin klickt -> Hinweis weg, auch nach dem Neuladen; Eintrag in der Änderungshistorie mit seinem Namen
    neuer Fehler        ein weiterer gescheiterter Versand -> Hinweis wieder da
    wieder gut          danach ein gesendeter -> kein Hinweis
    Monteurin           landet auf /mobil, die Schnittstelle antwortet ihr 403 (lesen und erledigen)

Die Aufträge schreibt der Test direkt in die Wegwerf-SQLite dieses Laufs (Regel 16: cdp_klicktest.py setzt DATABASE_URL auf den markierten
Arbeitsordner). Stehende Uhr 24.11.2026 10:00 (09:00 UTC).

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_portal_stau.py [--app-port N] [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln: siehe scripts/cdp_klicktest.py. Dauer unter einer Minute.
"""

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

BOX = "document.getElementById('portalStau')"
SICHTBAR = f"(()=>{{const b={BOX};return !!b&&!b.classList.contains('hidden')&&b.offsetParent!==null}})()"
TEXT = "document.getElementById('portalStauText').textContent"
ERLEDIGT_SICHTBAR = "(()=>{const b=document.getElementById('portalStauErledigt');return !!b&&!b.hidden&&b.offsetParent!==null})()"
LINK = "(()=>{const a=document.querySelector('#portalStau a');return a?[a.textContent,a.getAttribute('href')]:null})()"
GESTALT = ("(()=>{const s=getComputedStyle(document.getElementById('portalStau'));const r=getComputedStyle(document.documentElement);"
           "const f=(n)=>{const d=document.createElement('div');d.style.color=r.getPropertyValue(n);document.body.append(d);"
           "const c=getComputedStyle(d).color;d.remove();return c};"
           "return [s.backgroundColor===f('--ds-warn-hell'),s.borderLeftColor===f('--ds-warn-text'),s.borderLeftWidth]})()")
GELADEN = "document.querySelector('#widgets .widget-card')"
WARTET_BUERO = "Kundenportal: Ein Anmeldecode wartet seit über 2 Minuten auf den Versand – bitte den Administrator informieren."
WARTET_ADMIN = "Kundenportal: Ein Anmeldecode wartet seit über 2 Minuten auf den Versand – bitte prüfen, ob der Postbote läuft (Dienst erp-portalpost)."
FEHLER = "Kundenportal: Der letzte Anmeldecode ging nicht hinaus – bitte im Versandprotokoll nachsehen."
# seit 1.11.47: der Hinweis, wenn Impressum und Datenschutz fehlen (app/kundenportal.py::PFLICHT_HINWEIS)
PFLICHT = ("(()=>{const b=document.getElementById('portalPflicht');const a=b&&b.querySelector('a');"
           "return b?[!b.classList.contains('hidden')&&b.offsetParent!==null,document.getElementById('portalPflichtText').textContent,"
           "a.textContent,a.getAttribute('href')]:null})()")
PFLICHT_TEXT = ("Im Kundenportal fehlen Impressum und Datenschutz: in den Unternehmensdaten steht keine gültige Webseite. Bis dahin zeigt das Portal "
                "statt seiner Seiten „Gerade klappt etwas nicht“, und es geht kein Link hinaus.")


def befuellen(db, k):
    from datetime import datetime

    from app.models import AppUser, Customer, PortalSitzung, PortalZugang

    adm = AppUser(username="adri", display_name="Adri Admin", role="admin", password_hash=k.passwort())
    fin = AppUser(username="fina", display_name="Fina Finanzen", role="buero_finanzen", password_hash=k.passwort())
    auf = AppUser(username="auri", display_name="Auri Auftrag", role="buero_auftrag", password_hash=k.passwort())
    mon = AppUser(username="moni", display_name="Moni Monteurin", role="field", password_hash=k.passwort())
    db.add_all([adm, fin, auf, mon])
    kunde = Customer(name="Herr Max Muster", salutation="Herr", first_name="Max", last_name="Muster", portal_aktiv=True)
    db.add(kunde)
    db.flush()
    zugang = PortalZugang(customer_id=kunde.id, email="max@example.invalid", email_anzeige="m***@example.invalid", link_sha256="a" * 64,
                          gueltig_bis=datetime(2027, 11, 24))
    db.add(zugang)
    db.flush()
    sitzung = PortalSitzung(zugang_id=zugang.id, wert_sha256="b" * 64, angelegt_am=datetime(2026, 11, 24, 8, 55), laeuft_ab=datetime(2026, 11, 24, 9, 10))
    db.add(sitzung)
    db.flush()
    return {"adm": k.cookies(adm), "fin": k.cookies(fin), "auf": k.cookies(auf), "mon": k.cookies(mon), "zugang": zugang.id, "sitzung": sitzung.id,
            "db_url": os.environ["DATABASE_URL"]}


def _sql(seed, sql: str, *werte) -> int:
    pfad = seed["db_url"].removeprefix("sqlite:///")
    assert Path(pfad).parent.joinpath(".klicktest").exists(), pfad
    with sqlite3.connect(pfad) as c:
        return c.execute(sql, werte).rowcount


def _abfrage(seed, sql: str, *werte):
    pfad = seed["db_url"].removeprefix("sqlite:///")
    assert Path(pfad).parent.joinpath(".klicktest").exists(), pfad
    with sqlite3.connect(pfad) as c:
        return c.execute(sql, werte).fetchall()


def _anfragen(tab) -> int:
    return sum(1 for e in tab.netz.verlauf if "/api/kundenportal/postbote" in str(e.get("url", "")))


async def _start(tab, p, name):
    p.pruefe(f"{name}: Start geladen", await tab.oeffnen(f"/?schritt={name}", GELADEN), True)
    await tab.warte_auf_ruhe()


async def pruefen(tab, seed, p):
    await tab.anmelden(seed["fin"])
    await _start(tab, p, "modul_aus")
    p.pruefe("Modul aus: kein Hinweis", await tab.js(SICHTBAR), False)
    p.pruefe("Modul aus: keine Anfrage", _anfragen(tab), 0)

    _sql(seed, "INSERT INTO enabled_modules (module_key, enabled, updated_at) VALUES ('kundenportal', 1, '2026-11-24 09:00:00')")
    await _start(tab, p, "modul_an")
    p.pruefe("Modul an, ohne Aufträge: Anfrage gestellt", _anfragen(tab) >= 1, True)
    p.pruefe("Modul an, ohne Aufträge: kein Hinweis", await tab.js(SICHTBAR), False)
    p.pruefe("Ohne Webseite, Büro – Finanzen: Hinweis zu Impressum und Datenschutz", await tab.js(PFLICHT),
             [True, PFLICHT_TEXT, "Unternehmensdaten öffnen", "/settings#general"])
    await tab.bild("pflicht_ohne_webseite")
    await tab.anmelden(seed["auf"])
    await _start(tab, p, "pflicht_auftrag")
    p.pruefe("Ohne Webseite, Büro – Auftrag: Hinweis sichtbar", (await tab.js(PFLICHT))[0], True)
    _sql(seed, "UPDATE general_settings SET website = 'www.muster-bedachung.example'")
    await _start(tab, p, "mit_webseite")
    p.pruefe("Mit Webseite: kein Hinweis zu Impressum und Datenschutz", (await tab.js(PFLICHT))[0], False)
    await tab.anmelden(seed["fin"])

    _sql(seed, "INSERT INTO portal_post (art, zugang_id, sitzung_id, angefordert_am, status) VALUES ('code', ?, ?, '2026-11-24 08:57:00', 'wartet')",
         seed["zugang"], seed["sitzung"])
    await _start(tab, p, "wartet")
    p.pruefe("wartet, Büro – Finanzen: Hinweis sichtbar", await tab.js(SICHTBAR), True)
    p.pruefe("wartet, Büro – Finanzen: Text ohne den Dienst", await tab.js(TEXT), WARTET_BUERO)
    p.pruefe("wartet: Link ins Versandprotokoll", await tab.js(LINK), ["Versandprotokoll öffnen", "/versandprotokoll?typ=portal_code"])
    p.pruefe("wartet: kein „Erledigt“", await tab.js(ERLEDIGT_SICHTBAR), False)
    p.pruefe("Warnhinweis: Fläche und Rand wie die übrigen", await tab.js(GESTALT), [True, True, "4px"])
    await tab.bild("stau_wartet_buero")
    await tab.anmelden(seed["auf"])
    await _start(tab, p, "wartet_auftrag")
    p.pruefe("wartet, Büro – Auftrag: Text ohne den Dienst", await tab.js(TEXT), WARTET_BUERO)
    await tab.anmelden(seed["adm"])
    await _start(tab, p, "wartet_admin")
    p.pruefe("wartet, Admin: Text mit dem Dienst", await tab.js(TEXT), WARTET_ADMIN)
    p.pruefe("wartet, Admin: kein „Erledigt“", await tab.js(ERLEDIGT_SICHTBAR), False)
    await tab.bild("stau_wartet_admin")

    _sql(seed, "UPDATE portal_post SET status = 'fehler', fehler = 'Versand gescheitert', erledigt_am = '2026-11-24 08:58:00'")
    await tab.anmelden(seed["auf"])
    await _start(tab, p, "gescheitert_auftrag")
    p.pruefe("gescheitert, Büro – Auftrag: Text", await tab.js(TEXT), FEHLER)
    p.pruefe("gescheitert, Büro – Auftrag: kein „Erledigt“", await tab.js(ERLEDIGT_SICHTBAR), False)
    await tab.anmelden(seed["adm"])
    for thema in ("light", "dark"):
        await tab.js(f"localStorage.setItem('erp_theme','{thema}')")
        await _start(tab, p, f"gescheitert_{thema}")
        p.pruefe(f"gescheitert, Admin ({thema}): „Erledigt“ sichtbar", await tab.js(ERLEDIGT_SICHTBAR), True)
        await tab.bild(f"stau_gescheitert_admin_{thema}")
    await tab.js("localStorage.setItem('erp_theme','light')")

    p.pruefe("Link: Versandprotokoll geöffnet",
             await tab.oeffnen("/versandprotokoll?typ=portal_code", "document.getElementById('filterType')"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Link: Filter „Art“ = Anmeldecode", await tab.js("document.getElementById('filterType').value"), "portal_code")
    p.pruefe("Filter „Art“ kennt beide Arten des Portals",
             await tab.js("[...document.querySelectorAll('#filterType option')].map(o=>o.value).filter(v=>v.startsWith('portal_'))"),
             ["portal_link", "portal_code"])

    await _start(tab, p, "erledigen")
    p.pruefe("Erledigt: geklickt und geladen", await tab.warte_auf_neu_geladene_liste("document.getElementById('portalStauErledigt').click()"), True)
    await tab.warte_auf_ruhe()
    p.pruefe("Erledigt: Hinweis weg", await tab.js(SICHTBAR), False)
    await _start(tab, p, "erledigt_neu_geladen")
    p.pruefe("Erledigt: nach dem Neuladen weg", await tab.js(SICHTBAR), False)
    p.pruefe("Erledigt: Änderungshistorie mit Name",
             _abfrage(seed, "SELECT action, actor_name FROM audit_logs WHERE entity_type = 'Kundenportal-Versand'"),
             [("Versandfehler erledigt", "Adri Admin")])
    p.pruefe("Erledigt: am Auftrag vermerkt", _abfrage(seed, "SELECT quittiert_von_name FROM portal_post WHERE status = 'fehler'"), [("Adri Admin",)])

    _sql(seed, "INSERT INTO portal_post (art, zugang_id, sitzung_id, angefordert_am, status, fehler, erledigt_am) VALUES ('code', ?, ?, "
               "'2026-11-24 08:58:30', 'fehler', 'Versand gescheitert', '2026-11-24 08:58:40')", seed["zugang"], seed["sitzung"])
    await _start(tab, p, "neuer_fehler")
    p.pruefe("neuer Fehler: Hinweis wieder da", await tab.js(SICHTBAR), True)

    _sql(seed, "INSERT INTO portal_post (art, zugang_id, sitzung_id, angefordert_am, status, erledigt_am) VALUES ('code', ?, ?, '2026-11-24 08:59:00', "
               "'gesendet', '2026-11-24 08:59:10')", seed["zugang"], seed["sitzung"])
    await _start(tab, p, "wieder_gut")
    p.pruefe("wieder gut: kein Hinweis", await tab.js(SICHTBAR), False)

    await tab.anmelden(seed["mon"])
    p.pruefe("Monteurin: Start leitet auf /mobil", await tab.oeffnen("/", "location.pathname==='/mobil'"), True)
    antwort = await tab.js("fetch('/api/kundenportal/postbote').then(r=>r.status)")
    p.pruefe("Monteurin: Schnittstelle 403", antwort, 403)
    antwort = await tab.js("fetch('/api/kundenportal/postbote/erledigt',{method:'POST',headers:{'Content-Type':'application/json'},"
                           "body:JSON.stringify({post_id:1})}).then(r=>r.status)")
    p.pruefe("Monteurin: Erledigt 403", antwort, 403)
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-24 10:00"))
