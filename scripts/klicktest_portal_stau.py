"""Klicktest: der Stau-Hinweis des Postboten auf „Start“ (1.11.7, Stufe P1c; Bauplan P1, Abschnitt 4).

    Modul aus           kein Hinweis, keine Anfrage an /api/kundenportal/postbote
    Modul an            ohne Aufträge kein Hinweis
    wartet              ein Auftrag wartet seit 3 Minuten -> Hinweis „wartet seit über 2 Minuten“ (Büro – Finanzen und Büro – Auftrag)
    gescheitert         der zuletzt erledigte Auftrag scheiterte -> Hinweis „ging nicht hinaus“
    wieder gut          danach ein gesendeter -> kein Hinweis
    Monteurin           landet auf /mobil, die Schnittstelle antwortet ihr 403

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
GELADEN = "document.querySelector('#widgets .widget-card')"


def befuellen(db, k):
    from datetime import datetime

    from app.models import AppUser, Customer, PortalSitzung, PortalZugang

    fin = AppUser(username="fina", display_name="Fina Finanzen", role="buero_finanzen", password_hash=k.passwort())
    auf = AppUser(username="auri", display_name="Auri Auftrag", role="buero_auftrag", password_hash=k.passwort())
    mon = AppUser(username="moni", display_name="Moni Monteurin", role="field", password_hash=k.passwort())
    db.add_all([fin, auf, mon])
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
    return {"fin": k.cookies(fin), "auf": k.cookies(auf), "mon": k.cookies(mon), "zugang": zugang.id, "sitzung": sitzung.id,
            "db_url": os.environ["DATABASE_URL"]}


def _sql(seed, sql: str, *werte) -> int:
    pfad = seed["db_url"].removeprefix("sqlite:///")
    assert Path(pfad).parent.joinpath(".klicktest").exists(), pfad
    with sqlite3.connect(pfad) as c:
        return c.execute(sql, werte).rowcount


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

    _sql(seed, "INSERT INTO portal_post (art, zugang_id, sitzung_id, angefordert_am, status) VALUES ('code', ?, ?, '2026-11-24 08:57:00', 'wartet')",
         seed["zugang"], seed["sitzung"])
    await _start(tab, p, "wartet")
    p.pruefe("wartet: Hinweis sichtbar", await tab.js(SICHTBAR), True)
    p.pruefe("wartet: Text", await tab.js(TEXT), "Kundenportal: Ein Anmeldecode wartet seit über 2 Minuten auf den Versand – "
                                                 "bitte prüfen, ob der Postbote läuft (Dienst erp-portalpost).")
    await tab.bild("stau_wartet")
    await tab.anmelden(seed["auf"])
    await _start(tab, p, "wartet_auftrag")
    p.pruefe("wartet, Büro – Auftrag: Hinweis sichtbar", await tab.js(SICHTBAR), True)

    _sql(seed, "UPDATE portal_post SET status = 'fehler', fehler = 'Versand gescheitert', erledigt_am = '2026-11-24 08:58:00'")
    await _start(tab, p, "gescheitert")
    p.pruefe("gescheitert: Hinweis sichtbar", await tab.js(SICHTBAR), True)
    p.pruefe("gescheitert: Text", await tab.js(TEXT), "Kundenportal: Der letzte Anmeldecode ging nicht hinaus – bitte im Versandprotokoll nachsehen.")
    for thema in ("light", "dark"):
        await tab.js(f"localStorage.setItem('erp_theme','{thema}')")
        await _start(tab, p, f"gescheitert_{thema}")
        await tab.bild(f"stau_gescheitert_{thema}")

    _sql(seed, "INSERT INTO portal_post (art, zugang_id, sitzung_id, angefordert_am, status, erledigt_am) VALUES ('code', ?, ?, '2026-11-24 08:59:00', "
               "'gesendet', '2026-11-24 08:59:10')", seed["zugang"], seed["sitzung"])
    await _start(tab, p, "wieder_gut")
    p.pruefe("wieder gut: kein Hinweis", await tab.js(SICHTBAR), False)

    await tab.anmelden(seed["mon"])
    p.pruefe("Monteurin: Start leitet auf /mobil", await tab.oeffnen("/", "location.pathname==='/mobil'"), True)
    antwort = await tab.js("fetch('/api/kundenportal/postbote').then(r=>r.status)")
    p.pruefe("Monteurin: Schnittstelle 403", antwort, 403)
    p.pruefe("keine JS-Fehler", tab.fehler, [])


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__, uhr="2026-11-24 10:00"))
