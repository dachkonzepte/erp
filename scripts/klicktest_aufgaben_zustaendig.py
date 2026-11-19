"""Klicktest: Liste „Zuständig“ im Aufgaben-Editor (1.9.373).

    Admin          /tasks bei 1440 px, hell: „+ Neue Aufgabe“ bietet nur an, wer die Aufgabe sähe (Büro-Konten), nicht den Monteur und nicht die
                   Person ohne Konto; eine Aufgabe aus dem Bestand an den Monteur zeigt ihn gewählt mit „(sieht die Aufgabe nicht)“ (Bild, dazu ein
                   Bild mit aufgeklappter Liste), speichert unverändert (200, Zuweisung bleibt), danach an Otto; eine Finanz-Aufgabe bietet nur
                   Büro – Finanzen an
    Büro – Auftrag GET /api/tasks/zustaendige ohne Büro – Finanzen und Administrator; „+ Neue Aufgabe“ mit sich selbst gewählt

AUFRUF (aus dem Projektordner):

    .venv\\Scripts\\python.exe scripts\\klicktest_aufgaben_zustaendig.py [--app-port N]
        [--cdp-port N] [--arbeitsordner PFAD] [--chrome PFAD] [--offen-lassen]

Optionen, Ablauf, Rückgabecode und Regeln (isolierte Wegwerf-Datenbank, Prozesse nur über die
eigene PID beenden): siehe scripts/cdp_klicktest.py. Erfundene Namen.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp_klicktest import klicktest_main  # noqa: E402


def befuellen(db, k):
    from decimal import Decimal

    from sqlalchemy import select

    from app.models import AppUser, Employee, Task, TaskColumn
    from app.tasks import create_task

    ma = {}
    for key, nr, vor, nach in (("erika", "Z-1", "Erika", "Eins"), ("otto", "Z-2", "Otto", "Zwei"), ("mo", "Z-3", "Mo", "Monteur"),
                               ("olga", "Z-4", "Olga", "Ohnekonto")):
        ma[key] = Employee(employee_number=nr, first_name=vor, last_name=nach, employee_group="angestellt", active=True,
                           hourly_wage=Decimal("22.00"))
    db.add_all(ma.values()); db.flush()
    benutzer = {
        "ada": AppUser(username="ada", display_name="Ada Admin", role="admin", password_hash=k.passwort()),  # ohne Mitarbeiter: das Board zeigt alle
        "erika": AppUser(username="erika", display_name="Erika Eins", role="buero_finanzen", employee_id=ma["erika"].id, password_hash=k.passwort()),
        "otto": AppUser(username="otto", display_name="Otto Zwei", role="buero_auftrag", employee_id=ma["otto"].id, password_hash=k.passwort()),
        "mo": AppUser(username="mo", display_name="Mo Monteur", role="field", employee_id=ma["mo"].id, password_hash=k.passwort()),
    }
    db.add_all(benutzer.values()); db.commit()
    spalte = db.scalar(select(TaskColumn.key).order_by(TaskColumn.sort_order, TaskColumn.id))
    alt = Task(title="Rückruf vorbereiten", status=spalte, priority="normal", assigned_employee_id=ma["mo"].id)  # vor 1.9.371 so zugewiesen
    db.add(alt); db.commit()
    skonto = create_task(db, title="Skonto prüfen", min_visible_role="buero_finanzen")["id"]
    return {"cookies": {name: k.cookies(u) for name, u in benutzer.items()}, "ma": {key: m.id for key, m in ma.items()},
            "alt": alt.id, "skonto": skonto}


BEREIT = "typeof zustaendige!=='undefined'&&zustaendige!==null&&document.querySelectorAll('#board .task-card').length>0"
OPTIONEN = "[...document.getElementById('editEmployee').options].map(o=>o.text)"
GEWAEHLT = "(s=>s.options[s.selectedIndex].text)(document.getElementById('editEmployee'))"
OFFEN = "!document.getElementById('editorCard').classList.contains('hidden')"
ZU = "document.getElementById('editorCard').classList.contains('hidden')"


def _aufgabe(nr: int) -> str:
    return f"fetch('/api/tasks?include_archived=true').then(r=>r.json()).then(l=>l.filter(t=>t.id==={nr}).map(t=>[t.assigned_employee_id,t.priority])[0])"


async def pruefen(tab, seed, p):
    ma = seed["ma"]
    await tab.fenster(1440, 1000)
    await tab.anmelden(seed["cookies"]["ada"])
    await tab.oeffnen("/tasks", BEREIT)
    await tab.js("localStorage.setItem('erp_theme','light')")  # erst auf der Seite des ERP (eigener Speicher je Herkunft), dann neu laden
    p.pruefe("Admin: /tasks geladen", await tab.oeffnen("/tasks?hell=1", BEREIT), True)
    p.pruefe("Admin: hell", await tab.js("document.documentElement.getAttribute('data-theme')"), "light")
    await tab.warte_auf_ruhe()

    # --- neue Aufgabe: nur, wer sie sähe ---
    await tab.js("document.querySelector('[data-klick=\"neue-aufgabe\"]').click()")
    await tab.warten(OFFEN)
    p.pruefe("Neue Aufgabe: Zuständig", await tab.js(OPTIONEN), ["— nicht zugeordnet —", "Erika Eins", "Otto Zwei"])
    p.pruefe("Neue Aufgabe: vorgewählt", await tab.js(GEWAEHLT), "— nicht zugeordnet —")
    await tab.js("closeEditor()")

    # --- Aufgabe aus dem Bestand an den Monteur ---
    await tab.js(f"document.querySelector('#board [data-task-id=\"{seed['alt']}\"]').click()")
    await tab.warten(OFFEN)
    p.pruefe("Bestand: gewählt und gekennzeichnet", await tab.js(GEWAEHLT), "Mo Monteur (sieht die Aufgabe nicht)")
    p.pruefe("Bestand: Liste", await tab.js(OPTIONEN), ["— nicht zugeordnet —", "Erika Eins", "Mo Monteur (sieht die Aufgabe nicht)", "Otto Zwei"])
    p.pruefe("Bestand: JS-Fehler", tab.fehler, [])
    await tab.js("document.getElementById('editorCard').scrollIntoView({block:'start'})")
    await tab.bild("aufgabe_zustaendig_1440_hell")
    # Für das zweite Bild die Liste aufgeklappt (size am select; ein aufgeklapptes select zeichnet headless Chrome nicht) -- danach wieder zu.
    await tab.js("(s=>{s.size=s.options.length})(document.getElementById('editEmployee'))")
    await tab.bild("aufgabe_zustaendig_liste_1440_hell")
    await tab.js("document.getElementById('editEmployee').removeAttribute('size')")

    await tab.js("document.getElementById('editPriority').value='hoch'; saveTask()")
    await tab.warten(ZU)
    await tab.warte_auf_ruhe()
    p.pruefe("Bestand: unverändert gespeichert", await tab.js(_aufgabe(seed["alt"])), [ma["mo"], "hoch"])
    p.pruefe("Bestand: keine Meldung", await tab.js("document.getElementById('editorStatus').textContent"), "")

    await tab.js(f"document.querySelector('#board [data-task-id=\"{seed['alt']}\"]').click()")
    await tab.warten(OFFEN)
    await tab.js(f"document.getElementById('editEmployee').value='{ma['otto']}'; saveTask()")
    await tab.warten(ZU)
    await tab.warte_auf_ruhe()
    p.pruefe("Bestand: an Otto", await tab.js(_aufgabe(seed["alt"])), [ma["otto"], "hoch"])
    await tab.js(f"document.querySelector('#board [data-task-id=\"{seed['alt']}\"]').click()")
    await tab.warten(OFFEN)
    p.pruefe("Bestand: Mo nicht mehr angeboten", await tab.js(OPTIONEN), ["— nicht zugeordnet —", "Erika Eins", "Otto Zwei"])
    await tab.js("closeEditor()")

    # --- Finanz-Aufgabe ---
    await tab.js(f"document.querySelector('#unassignedList [data-task-id=\"{seed['skonto']}\"] .task-title').click()")
    await tab.warten(OFFEN)
    p.pruefe("Finanz-Aufgabe: Zuständig", await tab.js(OPTIONEN), ["— nicht zugeordnet —", "Erika Eins"])
    p.pruefe("Admin: JS-Fehler", tab.fehler, [])

    # --- Büro – Auftrag ---
    await tab.anmelden(seed["cookies"]["otto"])
    p.pruefe("Büro – Auftrag: Mindestrollen", await tab.js(
        "fetch('/api/tasks/zustaendige').then(r=>r.json()).then(l=>l.map(e=>e.min_visible_role))"), [None, "field", "buero_auftrag"])
    p.pruefe("Büro – Auftrag: /tasks geladen", await tab.oeffnen("/tasks", "typeof zustaendige!=='undefined'&&zustaendige!==null&&!!authStatus"), True)
    await tab.warte_auf_ruhe()
    await tab.js("document.querySelector('[data-klick=\"neue-aufgabe\"]').click()")
    await tab.warten(OFFEN)
    p.pruefe("Büro – Auftrag: Zuständig", await tab.js(OPTIONEN), ["— nicht zugeordnet —", "Erika Eins", "Otto Zwei"])
    p.pruefe("Büro – Auftrag: sich selbst vorgewählt", await tab.js(GEWAEHLT), "Otto Zwei")
    p.pruefe("Büro – Auftrag: JS-Fehler", tab.fehler, [])

    # --- Monteur ---
    await tab.anmelden(seed["cookies"]["mo"])
    p.pruefe("Monteur: API 403", await tab.js("fetch('/api/tasks/zustaendige').then(r=>r.status)"), 403)


if __name__ == "__main__":
    sys.exit(klicktest_main(befuellen, pruefen, beschreibung=__doc__))
