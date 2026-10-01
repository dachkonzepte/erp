"""Klicktest: keine Links auf gesperrte Seiten in Seitenleiste und Kopfzeile (1.8.24).

Die Seitenleiste zeigte dem Monteur auf der Berichtsseite "Wartungen", "Mängel", "Anfragen",
"Projekte", "Planung" -- jeder Klick endete auf "Zugriff verweigert". Seit 1.8.24 nur noch für
Büro/Admin. Geprüft wird im echten Browser, nach dem Laden der Seite:

    je Rolle           Berichtsseite (Monteur zusätzlich "Mein Konto"): jeder sichtbare Link in
                       Seitenleiste und Kopfzeile, Kontomenü aufgeklappt, liefert als dieselbe
                       Rolle kein 403
    Monteur            Seitenleiste nur noch "Start" und "Zeiterfassung"
    Büro               die fünf Links unverändert da

Links im Seiteninhalt, die erst das JavaScript aus geladenen Daten baut (z. B. "← Auftrag"), werden
zusätzlich aufgerufen und nur als HINWEIS ausgegeben -- sie sind nicht Teil dieser Runde.

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_monteur_navigation.py [--app-port N] [--cdp-port N]
        [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

ROLLEN = ("field", "buero_auftrag", "buero_finanzen", "admin")
FUENF = ["Wartungen", "Mängel", "Anfragen", "Projekte", "Planung"]

# Sichtbare Links (offsetParent/getClientRects), als Pfad; Navigation = Seitenleiste + Kopfzeile.
_SICHTBAR = "(a=>a.getClientRects().length>0&&getComputedStyle(a).visibility!=='hidden')"
_NAVIGATION = (f"[...document.querySelectorAll('#appSidebar a[href], .app-topbar a[href]')].filter({_SICHTBAR})"
               ".map(a=>a.getAttribute('href')).filter(h=>h.startsWith('/'))")
_INHALT = (f"[...document.querySelectorAll('main a[href]')].filter({_SICHTBAR})"
           ".map(a=>a.getAttribute('href')).filter(h=>h.startsWith('/'))")
_STATUS = ("(async links=>{const r={};for(const h of [...new Set(links)]){"
           "r[h]=(await fetch(h.split('#')[0],{credentials:'same-origin'})).status}return r})")


def befuellen(db, k):
    from decimal import Decimal

    from app.models import AppUser, Customer, Employee, Order, OrderItem, Project, Property, WorkPreparationEmployee
    from app.project_pipeline_columns import default_pipeline_column_id
    from app.work_preparation import ensure_preparation

    max_m = Employee(employee_number="M-1", first_name="Max", last_name="Monteur", employee_group="angestellt",
                     weekly_hours=Decimal("40"), active=True)
    buero = Employee(employee_number="B-1", first_name="Bea", last_name="Büro", employee_group="angestellt",
                     weekly_hours=Decimal("40"), active=True)
    db.add_all([max_m, buero]); db.flush()
    users = {rolle: AppUser(username=rolle, display_name=rolle, role=rolle, password_hash=k.passwort(),
                            employee_id=max_m.id if rolle == "field" else buero.id) for rolle in ROLLEN}
    kunde = Customer(name="Kundin Klar", last_name="Klar")
    db.add_all([*users.values(), kunde]); db.flush()
    objekt = Property(customer_id=kunde.id, name="Halle Süd", street="Werkstr. 5", postal_code="22222", city="Objektstadt")
    db.add(objekt); db.flush()
    projekt = Project(project_number="P-KT-1", name="Sanierung", customer_id=kunde.id, property_id=objekt.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(projekt); db.flush()
    auftrag = Order(order_number="AU-KT-0001", project_id=projekt.id, source_quote_id=1, quote_number_snapshot="A-KT-1",
                    title="Dachsanierung", customer_name=kunde.name, property_name=objekt.name)
    db.add(auftrag); db.flush()
    db.add(OrderItem(order_id=auftrag.id, sort_order=10, position_number="1", short_text="Abdichtung",
                     quantity=Decimal("850"), unit="m²", unit_price=Decimal("48.90")))
    db.commit()
    db.add(WorkPreparationEmployee(preparation_id=ensure_preparation(db, auftrag.id).id, employee_id=max_m.id))
    db.commit()
    return {"auftrag": auftrag.id, "cookies": {rolle: k.cookies(user) for rolle, user in users.items()}}


async def pruefen(tab, seed, p):
    await tab.cmd("Page.addScriptToEvaluateOnNewDocument", source="window.alert=m=>console.error('alert(): '+m)")
    await tab.fenster(1400, 900)
    berichtsseite = f"/orders/{seed['auftrag']}/service-reports"
    for rolle in ROLLEN:
        await tab.anmelden(seed["cookies"][rolle])
        seiten = [(berichtsseite, "authStatus&&authStatus.authenticated&&document.getElementById('breadcrumb').textContent.length>0")]
        if rolle == "field":
            seiten.append(("/account", "document.getElementById('appSidebar')"))
        for pfad, bereit in seiten:
            if not await tab.oeffnen(pfad, bereit):
                p.pruefe(f"{rolle} {pfad}: Seite geladen", False, True)
                continue
            await tab.js("document.getElementById('appTopbarAccountBtn')?.click()")  # Kontomenü aufklappen
            links = await tab.js(_NAVIGATION)
            status = await tab.js(f"{_STATUS}({_NAVIGATION})")
            p.pruefe(f"{rolle} {pfad}: Navigation ohne 403 ({len(links)} Links)",
                     sorted(h for h, s in status.items() if s == 403), [])
            inhalt = await tab.js(f"{_STATUS}({_INHALT})")
            for h, s in sorted(inhalt.items()):
                if s == 403:
                    print(f"HINWEIS  {rolle} {pfad}: Link im Seiteninhalt {h} -> 403")
            beschriftung = await tab.js("[...document.querySelectorAll('#appSidebar .app-sidebar-link .app-sidebar-label')]"
                                        ".map(x=>x.textContent.trim())")
            if rolle == "field":
                p.pruefe(f"{rolle} {pfad}: Seitenleiste", beschriftung, ["Start", "Zeiterfassung"])
            elif pfad == berichtsseite:
                p.pruefe(f"{rolle}: die fünf Links da", [x for x in beschriftung if x in FUENF], FUENF)
            p.pruefe(f"{rolle} {pfad}: JS-Fehler", tab.fehler, [])
            await tab.bild(f"{rolle}_{pfad.strip('/').replace('/', '_')}")


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
