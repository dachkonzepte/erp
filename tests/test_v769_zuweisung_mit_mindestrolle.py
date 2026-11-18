"""Version 1.9.369 (Urlaubsrunde, Punkt 5; F2 c aus dem Bericht 1.9.364): die Zuweisung einer Aufgabe an jemanden ohne ihre Mindestrolle; seit 1.9.371
(Nachrunde Urlaub, Punkt 2; F2) auch ohne Mindestrolle.

    Regel        app/tasks.py::zuweisung_grund(): sähe kein aktives Konto der Person die Aufgabe (task_visible_for_user()), der Grund
                 „Diese Aufgabe sieht nur Büro – Finanzen und Administrator – <Name> hat kein Konto mit dieser Rolle.“; ohne Mindestrolle sieht sie nur das
                 Büro (Monteur, Person ohne Konto: „… sieht nur Büro – Auftrag, Büro – Finanzen und Administrator – <Name> …“)
    von Hand     POST /api/tasks und PUT /api/tasks/{id}: 422 mit dem Grund, nichts gespeichert
    Module       create_task() ohne Angabe: die Aufgabe entsteht empfängerlos im Büro-Eingang (wie ohne Sachbearbeiter)
    Bestand      bleibt; scripts/pruefe_aufgaben_zuweisung.py zählt nur (nur lesend, ohne Namen und Titel), seit 1.9.371 jede zugewiesene Aufgabe
    Kommentar    am Modell und im Docstring von create_task() berichtigt: die Mindestrolle gilt auch für eine zugewiesene Aufgabe
"""

import ast
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import AppUser, Employee, Task
from app.routers import tasks as tasks_router
from app.tasks import ZuweisungOhneRolle, create_task, zuweisung_grund
from tests.test_v279_task_visibility import make_employees

ROOT = Path(__file__).resolve().parent.parent
FIN = "Diese Aufgabe sieht nur Büro – Finanzen und Administrator – Otto Zwei hat kein Konto mit dieser Rolle."
BUERO = "Diese Aufgabe sieht nur Büro – Auftrag, Büro – Finanzen und Administrator – {} hat kein Konto mit dieser Rolle."


@pytest.fixture
def welt(threaded_db_session):
    db = threaded_db_session
    erika, otto = make_employees(db, konten=False)  # Erika: Konto Büro – Finanzen; Otto: Konto Büro – Auftrag
    db.add_all([AppUser(username="erika", display_name="Erika", role="buero_finanzen", employee_id=erika.id, active=True, password_hash="-"),
                AppUser(username="otto", display_name="Otto", role="buero_auftrag", employee_id=otto.id, active=True, password_hash="-")])
    ohne = Employee(employee_number="V-3", first_name="Olga", last_name="Ohnekonto", employee_group="gewerblich", hourly_wage="20", weekly_hours="40",
                    active=True)
    mo = Employee(employee_number="V-4", first_name="Mo", last_name="Monteur", employee_group="gewerblich", hourly_wage="20", weekly_hours="40", active=True)
    db.add_all([ohne, mo])
    db.flush()
    db.add(AppUser(username="mo", display_name="Mo", role="field", employee_id=mo.id, active=True, password_hash="-"))
    db.commit()
    return {"db": db, "erika": erika.id, "otto": otto.id, "ohne": ohne.id, "mo": mo.id}


def test_regel(welt):
    db = welt["db"]
    assert zuweisung_grund(db, welt["otto"], "buero_finanzen") == FIN
    assert zuweisung_grund(db, welt["erika"], "buero_finanzen") is None
    assert zuweisung_grund(db, welt["otto"], "buero_auftrag") is None
    assert zuweisung_grund(db, welt["otto"], None) is None and zuweisung_grund(db, None, "admin") is None  # Büro ohne Mindestrolle; ohne Zuweisung
    assert zuweisung_grund(db, welt["erika"], "admin") == "Diese Aufgabe sieht nur Administrator – Erika Eins hat kein Konto mit dieser Rolle."
    assert zuweisung_grund(db, welt["ohne"], "buero_auftrag") == (
        "Diese Aufgabe sieht nur Büro – Auftrag, Büro – Finanzen und Administrator – Olga Ohnekonto hat kein Konto mit dieser Rolle.")
    assert zuweisung_grund(db, welt["ohne"], "field") is not None  # auch „Monteur“: Aufgaben sieht nur das Büro
    assert zuweisung_grund(db, welt["mo"], "field") == (  # dieselbe Regel wie das Lesen: ein Monteur-Konto sieht keine Aufgabe
        "Diese Aufgabe sieht nur Büro – Auftrag, Büro – Finanzen und Administrator – Mo Monteur hat kein Konto mit dieser Rolle.")
    db.scalar(select(AppUser).where(AppUser.username == "erika")).active = False
    db.commit()
    assert zuweisung_grund(db, welt["erika"], "buero_finanzen") is not None  # nur aktive Konten zählen


def test_ohne_mindestrolle_regel(welt):
    """Seit 1.9.371: auch ohne Mindestrolle -- Aufgaben sieht nur das Büro; ein Monteur oder eine Person ohne Konto sähe sie nie."""
    db = welt["db"]
    assert zuweisung_grund(db, welt["mo"], None) == BUERO.format("Mo Monteur")
    assert zuweisung_grund(db, welt["ohne"], None) == BUERO.format("Olga Ohnekonto")
    assert zuweisung_grund(db, welt["otto"], None) is None and zuweisung_grund(db, welt["erika"], None) is None  # jedes Büro-Konto
    db.scalar(select(AppUser).where(AppUser.username == "otto")).active = False
    db.commit()
    assert zuweisung_grund(db, welt["otto"], None) == BUERO.format("Otto Zwei")  # nur aktive Konten zählen


def test_ohne_mindestrolle_von_hand_422(welt, router_test_client):
    db = welt["db"]
    c = router_test_client(db, tasks_router.router, role="admin")
    for wer, name in (("mo", "Mo Monteur"), ("ohne", "Olga Ohnekonto")):
        r = c.post("/api/tasks", json={"title": f"Für {wer}", "assigned_employee_id": welt[wer]})
        assert r.status_code == 422, r.text
        assert r.json()["detail"] == BUERO.format(name)
        assert db.scalar(select(Task).where(Task.title == f"Für {wer}")) is None  # nichts gespeichert
    task = create_task(db, title="Eingang")
    r = c.put(f"/api/tasks/{task['id']}", json={"assigned_employee_id": welt["mo"]})
    assert r.status_code == 422, r.text
    assert r.json()["detail"] == BUERO.format("Mo Monteur")
    db.expire_all()
    assert db.get(Task, task["id"]).assigned_employee_id is None
    assert c.put(f"/api/tasks/{task['id']}", json={"assigned_employee_id": welt["otto"]}).status_code == 200  # Büro wie bisher


def test_bestand_bleibt_bearbeitbar(welt, router_test_client):
    """Seit 1.9.371: das Bearbeiten prüft nur eine NEUE Zuweisung -- der Editor schickt die bisherige bei jedem Speichern mit (tasks.html), eine Aufgabe aus
    dem Bestand (an den Monteur, an Otto mit Mindestrolle Büro – Finanzen) bleibt bearbeitbar."""
    db = welt["db"]
    alt = Task(title="Alt an den Monteur", assigned_employee_id=welt["mo"], status="offen")
    alt2 = Task(title="Alt an Otto", assigned_employee_id=welt["otto"], min_visible_role="buero_finanzen", status="offen")
    db.add_all([alt, alt2])
    db.commit()
    c = router_test_client(db, tasks_router.router, role="admin")
    for t, wer in ((alt, "mo"), (alt2, "otto")):
        r = c.put(f"/api/tasks/{t.id}", json={"title": "Geändert", "assigned_employee_id": welt[wer], "priority": "hoch"})
        assert r.status_code == 200, r.text
        assert r.json()["assigned_employee_id"] == welt[wer]  # bleibt, wie sie war
    r = c.put(f"/api/tasks/{alt.id}", json={"assigned_employee_id": welt["ohne"]})  # eine neue Zuweisung prüft er
    assert r.status_code == 422, r.text


def test_ohne_mindestrolle_module_in_den_eingang(welt):
    db = welt["db"]
    for wer in ("mo", "ohne"):
        t = create_task(db, title="Rechnung erstellen", assigned_employee_id=welt[wer])
        assert (t["assigned_employee_id"], t["min_visible_role"]) == (None, None)  # empfängerlos im Büro-Eingang
    assert create_task(db, title="Für Otto", assigned_employee_id=welt["otto"])["assigned_employee_id"] == welt["otto"]
    with pytest.raises(ZuweisungOhneRolle):
        create_task(db, title="Von Hand", assigned_employee_id=welt["mo"], zuweisung="ablehnen")


def test_von_hand_anlegen_422(welt, router_test_client):
    db = welt["db"]
    c = router_test_client(db, tasks_router.router, role="admin")
    r = c.post("/api/tasks", json={"title": "Skonto ziehen", "assigned_employee_id": welt["otto"], "min_visible_role": "buero_finanzen"})
    assert r.status_code == 422, r.text
    assert r.json()["detail"] == FIN
    assert db.scalar(select(Task).where(Task.title == "Skonto ziehen")) is None  # nichts gespeichert
    assert c.post("/api/tasks", json={"title": "Skonto ziehen", "assigned_employee_id": welt["erika"],
                                      "min_visible_role": "buero_finanzen"}).status_code == 200
    assert c.post("/api/tasks", json={"title": "Für Otto", "assigned_employee_id": welt["otto"]}).status_code == 200  # ohne Mindestrolle wie bisher


def test_von_hand_zuweisen_422(welt, router_test_client):
    db = welt["db"]
    task = create_task(db, title="Finanz-Eingang", min_visible_role="buero_finanzen")
    c = router_test_client(db, tasks_router.router, role="admin")
    r = c.put(f"/api/tasks/{task['id']}", json={"assigned_employee_id": welt["otto"]})
    assert r.status_code == 422, r.text
    assert r.json()["detail"] == FIN
    db.expire_all()
    assert db.get(Task, task["id"]).assigned_employee_id is None
    assert c.put(f"/api/tasks/{task['id']}", json={"assigned_employee_id": welt["erika"]}).status_code == 200
    assert c.put(f"/api/tasks/{task['id']}", json={"assigned_employee_id": None}).status_code == 200  # zurück in den Eingang geht immer
    assert c.put(f"/api/tasks/{task['id']}", json={"priority": "hoch"}).status_code == 200  # andere Felder unberührt


def test_module_legen_in_den_buero_eingang(welt):
    db = welt["db"]
    t = create_task(db, title="Behinderungsanzeige versenden", assigned_employee_id=welt["ohne"], min_visible_role="buero_auftrag")
    assert t["assigned_employee_id"] is None and t["min_visible_role"] == "buero_auftrag"  # empfängerlos, wie ohne Sachbearbeiter
    t = create_task(db, title="Mit Konto", assigned_employee_id=welt["otto"], min_visible_role="buero_auftrag")
    assert t["assigned_employee_id"] == welt["otto"]  # wer sie sieht, bekommt sie
    with pytest.raises(ZuweisungOhneRolle):
        create_task(db, title="Von Hand", assigned_employee_id=welt["ohne"], min_visible_role="buero_auftrag", zuweisung="ablehnen")


def test_nur_der_endpunkt_lehnt_ab():
    """Kein Modul übergibt zuweisung="ablehnen" -- nur der Endpunkt (von Hand)."""
    funde = []
    for pfad in sorted((ROOT / "app").rglob("*.py")):
        for n in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", None)) == "create_task":
                if any(k.arg == "zuweisung" for k in n.keywords):
                    funde.append(pfad.relative_to(ROOT).as_posix())
    assert funde == ["app/routers/tasks.py"]


def test_bestand_bleibt_und_wird_gezaehlt(welt, tmp_path):
    """Was vor 1.9.369 so zugewiesen wurde, bleibt; das Prüfskript zählt es, ohne Namen und Titel."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import pruefe_aufgaben_zuweisung as skript
    db = welt["db"]
    alt = Task(title="Vertraulicher Titel", assigned_employee_id=welt["otto"], min_visible_role="buero_finanzen", status="offen")
    alt2 = Task(title="Noch einer", assigned_employee_id=welt["ohne"], min_visible_role="admin", status="offen", archived=True)
    gut = Task(title="Passt", assigned_employee_id=welt["erika"], min_visible_role="buero_finanzen", status="offen")
    monteur = Task(title="An den Monteur", assigned_employee_id=welt["mo"], status="offen")  # seit 1.9.371: auch ohne Mindestrolle
    gut2 = Task(title="Passt auch", assigned_employee_id=welt["otto"], status="offen")
    db.add_all([alt, alt2, gut, monteur, gut2])
    db.commit()
    zeilen = []
    assert skript.main([], sitzung=db, ausgabe=zeilen.append) == 1
    text = "\n".join(zeilen)
    assert zeilen[0] == "3 von 5 zugewiesenen Aufgaben sieht ihre Person nicht:"
    assert "  Mindestrolle keine: 1" in zeilen and "  Mindestrolle Administrator: 1" in zeilen
    assert f"Aufgabe Nr. {alt.id}: Mindestrolle Büro – Finanzen, Person: Büro – Auftrag" in text
    assert f"Aufgabe Nr. {alt2.id}: Mindestrolle Administrator, Person: kein Konto (archiviert)" in text
    assert f"Aufgabe Nr. {monteur.id}: Mindestrolle keine, Person: Monteur" in text
    assert "Vertraulich" not in text and "An den" not in text and "Otto" not in text and "Olga" not in text and "Mo Monteur" not in text  # ohne Titel, Namen
    db.expire_all()
    assert db.get(Task, alt.id).assigned_employee_id == welt["otto"]  # nichts geändert
    assert skript.main([], sitzung=db, ausgabe=[].append) == 1
    assert skript.main([], umgebung={}, ausgabe=[].append) == 2  # ohne DATABASE_URL


def test_kommentar_und_docstring_berichtigt():
    modelle = (ROOT / "app" / "models.py").read_text(encoding="utf-8")
    assert "eine bereits zugewiesene Aufgabe ignoriert dieses Feld" not in modelle
    assert "Wirkt auf JEDE Aufgabe, auch eine zugewiesene" in modelle
    aufgaben = (ROOT / "app" / "tasks.py").read_text(encoding="utf-8")
    assert "min_visible_role ist dann folgenlos, aber kein Fehler" not in aufgaben
    assert "ist ohnehin nur für diesen selbst oder Admin\n    sichtbar, unabhängig von min_visible_role" not in aufgaben
