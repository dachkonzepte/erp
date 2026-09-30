"""Klicktest: Aufgaben ohne Zuständigkeit (1.8.18).

    Büro-Auftrag  Dashboard: Widget "Ohne Zuständigkeit" erscheint auch im vor 1.8.18 gespeicherten
                  Layout, zeigt die fremde Aufgabe ohne Zuständigkeit, nicht die finanz-gebundene
                  und nicht die einer Kollegin; "Übernehmen" verschiebt sie nach "Meine Aufgaben"
    Büro-Finanzen /tasks: Abschnitt "Ohne Zuständigkeit" mit beiden Aufgaben, das Board zeigt sie
                  nicht doppelt; ein Kollege übernimmt dieselbe Aufgabe zuerst (zweites Konto über
                  die API), der Klick danach meldet das klar; die Finanz-Aufgabe lässt sich übernehmen
    Admin         Änderungshistorie zeigt die Übernahmen, ein Büro-Konto bekommt sie nicht
    Monteur       /tasks gesperrt, /api/tasks?unassigned_only=true 403

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_aufgaben_ohne_zustaendigkeit.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402

VERGEBEN = "Diese Aufgabe hat bereits jemand anderes übernommen."


def befuellen(db, k):
    from decimal import Decimal

    from app.dashboard import save_widget_layout
    from app.models import AppUser, Employee
    from app.tasks import create_task

    ma = {}
    for key, nr, vor, nach in (("anna", "E-1", "Anna", "Admin"), ("karl", "E-2", "Karl", "Kollege"),
                               ("fiona", "E-3", "Fiona", "Finanz"), ("mia", "E-4", "Mia", "Monteurin")):
        ma[key] = Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group="angestellt",
                           active=True, hourly_wage=Decimal("22.00"))
    db.add_all(ma.values()); db.flush()
    benutzer = {
        "anna": AppUser(username="anna", display_name="Anna Admin", role="admin", employee_id=ma["anna"].id, password_hash=k.passwort()),
        "karl": AppUser(username="karl", display_name="Karl Kollege", role="buero_auftrag", employee_id=ma["karl"].id, password_hash=k.passwort()),
        "fiona": AppUser(username="fiona", display_name="Fiona Finanz", role="buero_finanzen", employee_id=ma["fiona"].id, password_hash=k.passwort()),
        "mia": AppUser(username="mia", display_name="Mia Monteurin", role="field", employee_id=ma["mia"].id, password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.commit()
    # Karl hat sein Layout vor 1.8.18 gespeichert -- ohne Zeile für das neue Widget.
    save_widget_layout(db, benutzer["karl"].id, [
        {"widget_key": "my_tasks", "sort_order": 10, "visible": True},
        {"widget_key": "kpis", "sort_order": 20, "visible": True},
        {"widget_key": "active_projects", "sort_order": 30, "visible": True},
    ])
    anna = benutzer["anna"].id
    t = {
        "rueckruf": create_task(db, title="Rückruf Frau Beispiel", created_by_user_id=anna)["id"],
        "material": create_task(db, title="Material nachbestellen", created_by_user_id=anna)["id"],
        "skonto": create_task(db, title="Skonto nutzen: Rechnung 4711", min_visible_role="buero_finanzen",
                              source_label="Eingangsrechnung 4711")["id"],
        "karl_eigen": create_task(db, title="Karls eigene Aufgabe", assigned_employee_id=ma["karl"].id)["id"],
        "fiona_eigen": create_task(db, title="Fionas eigene Aufgabe", assigned_employee_id=ma["fiona"].id)["id"],
    }
    return {"cookies": {name: k.cookies(u) for name, u in benutzer.items()}, "tasks": t}


WIDGET = "document.getElementById('widget-body-open_office_tasks')"
WIDGET_TITEL = f"[...({WIDGET}?.querySelectorAll('.task-title')||[])].map(x=>x.textContent)"
MEINE = "[...(document.getElementById('widget-body-my_tasks')?.querySelectorAll('.task-title')||[])].map(x=>x.textContent)"
ABSCHNITT = "[...document.querySelectorAll('#unassignedList .task-title')].map(x=>x.textContent)"
BOARD = "[...document.querySelectorAll('#board .task-title')].map(x=>x.textContent)"


async def pruefen(tab, seed, p):
    t = seed["tasks"]

    # --- Büro-Auftrag: Dashboard ---
    await tab.anmelden(seed["cookies"]["karl"])
    await tab.oeffnen("/", f"{WIDGET}?.querySelector('.task-list, .status')")
    p.pruefe("Dashboard: Widget-Titel", await tab.js(
        "[...document.querySelectorAll('.widget-card h2')].map(h=>h.textContent)"), ["Meine Aufgaben", "Ohne Zuständigkeit", "Kennzahlen", "Laufende Projekte"])
    p.pruefe("Dashboard: Ohne Zuständigkeit", sorted(await tab.js(WIDGET_TITEL)), ["Material nachbestellen", "Rückruf Frau Beispiel"])
    await tab.bild("dashboard_vorher")
    await tab.js(f"{WIDGET}.querySelector('[data-unassigned-task=\"{t['material']}\"] button').click()")
    await tab.warten(f"{WIDGET}.querySelector('.status')?.textContent.includes('Übernommen')")
    await tab.warten(f"{MEINE}.includes('Material nachbestellen')")
    p.pruefe("Dashboard: Meldung nach Übernehmen", await tab.js(f"{WIDGET}.querySelector('.status').textContent"),
             "Übernommen – die Aufgabe steht jetzt unter „Meine Aufgaben“.")
    p.pruefe("Dashboard: danach ohne Zuständigkeit", await tab.js(WIDGET_TITEL), ["Rückruf Frau Beispiel"])
    p.pruefe("Dashboard: danach Meine Aufgaben", sorted(await tab.js(MEINE)), ["Karls eigene Aufgabe", "Material nachbestellen"])
    p.pruefe("Dashboard: JS-Fehler", tab.fehler, [])
    await tab.bild("dashboard_nachher")

    # --- Büro-Finanzen: Aufgabenliste, gleichzeitiges Übernehmen ---
    await tab.anmelden(seed["cookies"]["fiona"])
    await tab.oeffnen("/tasks", "document.querySelectorAll('#unassignedList .task-card').length>0")
    p.pruefe("Aufgaben: Abschnitt", sorted(await tab.js(ABSCHNITT)), ["Rückruf Frau Beispiel", "Skonto nutzen: Rechnung 4711"])
    p.pruefe("Aufgaben: Zähler", await tab.js("document.getElementById('count-unassigned').textContent"), "2")
    p.pruefe("Aufgaben: Board", await tab.js(BOARD), ["Fionas eigene Aufgabe"])
    await tab.bild("aufgaben_vorher")

    # Karl übernimmt dieselbe Aufgabe, während Fionas Seite noch den alten Stand zeigt.
    await tab.anmelden(seed["cookies"]["karl"])
    p.pruefe("Karl übernimmt zuerst (API)", await tab.js(f"fetch('/api/tasks/{t['rueckruf']}/claim',{{method:'POST'}}).then(r=>r.status)"), 200)
    await tab.anmelden(seed["cookies"]["fiona"])
    await tab.js(f"document.querySelector('#unassignedList [data-task-id=\"{t['rueckruf']}\"] button').click()")
    await tab.warten("document.getElementById('unassignedStatus').textContent.length>0")
    await tab.warten(f"!{ABSCHNITT}.includes('Rückruf Frau Beispiel')")
    p.pruefe("Aufgaben: Meldung zweiter Klick", await tab.js("document.getElementById('unassignedStatus').textContent"), VERGEBEN)
    p.pruefe("Aufgaben: Meldung ist Fehler", await tab.js("document.getElementById('unassignedStatus').className"), "status err")
    p.pruefe("Aufgaben: Abschnitt danach", await tab.js(ABSCHNITT), ["Skonto nutzen: Rechnung 4711"])
    await tab.bild("aufgaben_zweiter_klick")

    await tab.js(f"document.querySelector('#unassignedList [data-task-id=\"{t['skonto']}\"] .task-title').click()")
    p.pruefe("Editor: Übernehmen sichtbar", await tab.js("!document.getElementById('claimTaskButton').classList.contains('hidden')"), True)
    p.pruefe("Editor: Zurück-Knopf verborgen", await tab.js("document.getElementById('releaseTaskButton').classList.contains('hidden')"), True)
    await tab.js("document.getElementById('claimTaskButton').click()")
    await tab.warten(f"{BOARD}.includes('Skonto nutzen: Rechnung 4711')")
    p.pruefe("Aufgaben: Finanz-Aufgabe übernommen", sorted(await tab.js(BOARD)), ["Fionas eigene Aufgabe", "Skonto nutzen: Rechnung 4711"])
    p.pruefe("Aufgaben: Abschnitt leer", await tab.js("document.querySelector('#unassignedList .empty')?.textContent"), "Keine Aufgaben ohne Zuständigkeit")
    p.pruefe("Aufgaben: Editor geschlossen", await tab.js("document.getElementById('editorCard').classList.contains('hidden')"), True)
    p.pruefe("Aufgaben: JS-Fehler", tab.fehler, [])
    await tab.bild("aufgaben_nachher")

    # --- Änderungshistorie: Admin ja, Büro nein ---
    await tab.anmelden(seed["cookies"]["anna"])
    await tab.oeffnen("/history", "document.querySelectorAll('#rows tr').length>0")
    p.pruefe("Historie (Admin): Übernahmen", await tab.js(
        "[...document.querySelectorAll('#rows tr')].filter(r=>r.textContent.includes('Zuständig (übernommen)'))"
        ".map(r=>r.children[1].textContent+' | '+r.children[3].textContent.replace(/Nr\\. \\d+ · /,'')+' | '+r.children[5].textContent)"),
        ["Fiona Finanz | AufgabeSkonto nutzen: Rechnung 4711 | — → Fiona Finanz",
         "Karl Kollege | AufgabeRückruf Frau Beispiel | — → Karl Kollege",
         "Karl Kollege | AufgabeMaterial nachbestellen | — → Karl Kollege"])
    p.pruefe("Historie: JS-Fehler", tab.fehler, [])
    await tab.bild("historie_admin")
    await tab.anmelden(seed["cookies"]["karl"])
    p.pruefe("Historie (Büro): keine Aufgaben-Einträge", await tab.js(
        "fetch('/api/audit-logs?entity_type=Aufgabe').then(r=>r.json()).then(x=>x.length)"), 0)

    # --- Monteur ---
    await tab.anmelden(seed["cookies"]["mia"])
    await tab.oeffnen("/tasks", "document.readyState==='complete'")
    p.pruefe("Monteur: /tasks gesperrt", await tab.js("document.querySelector('#unassignedList')===null"), True)
    p.pruefe("Monteur: API 403", await tab.js("fetch('/api/tasks?unassigned_only=true').then(r=>r.status)"), 403)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
