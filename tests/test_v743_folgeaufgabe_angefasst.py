"""Version 1.9.343 -- Folgeaufgaben eines gelöschten Berichtsentwurfs (Nachrunde V1, Punkt 3, Variante A).

Eine Folgeaufgabe („Büro prüfen lassen“ an einem Befund) geht mit dem Berichtsentwurf nur, solange niemand sie angefasst hat. Angefasst:
nicht mehr in der Anfangsspalte (auch erledigt), mit Unteraufgaben, mit Vorgang daraus oder sonst seit dem Anlegen geändert. Eine angefasste
bleibt, der Verweis des Befunds entfällt, die Beschreibung trägt vorn den Vermerk mit Datum und Konto. Bis 1.9.342 ging jede mit -- jeder Fall
„angefasst“ unten war vorher rot."""

from datetime import date, timedelta

import pytest
from sqlalchemy import update

from app.berlin_time import berlin_today
from app.findings import create_finding, create_follow_up_project_for_task
from app.models import AppUser, Employee, Finding, Order, Project, ServiceReport, Task
from app.service_reports import create_report, delete_report
from app.tasks import add_checklist_item, claim_task, set_task_archived, update_task
from tests.test_v153_mahnwesen import db_session
from tests.aufgaben_konto import buero_konto  # seit 1.9.371: Aufgaben bekommt nur, wer sie sieht
from tests.test_v214_findings_and_photos import _build_extra_order


def _entwurf_mit_folgeaufgabe(db, suffix="9301", text="Riss in der Attika"):
    order, _customer, _project = _build_extra_order(db, suffix)
    report = create_report(db, order.id, "rapport", description="Arbeiten laut Testfall")
    finding = create_finding(db, report["id"], text, "mittel", "buero_pruefen")
    assert finding["follow_up_task_id"] is not None
    return order, report["id"], finding["id"], finding["follow_up_task_id"]


def _aelter(db, task_id):
    """Die Aufgabe eine Stunde älter machen (beide Zeitpunkte gleich weit zurück) -- eine Änderung danach liegt dann wie im Betrieb
    deutlich nach dem Anlegen, nicht in derselben Sekunde."""
    task = db.get(Task, task_id)
    frueher = task.created_at - timedelta(hours=1)
    db.execute(update(Task).where(Task.id == task_id).values(created_at=frueher, updated_at=frueher + (task.updated_at - task.created_at)))
    db.commit()
    db.expire_all()


def _mitarbeiter(db, vorname="Bea"):
    emp = Employee(first_name=vorname, last_name="Büro", employee_group="angestellt", active=True)
    db.add(emp)
    db.commit()
    if vorname != "Bea":  # Bea bekommt ihr Konto in _uebernehmen(); seit 1.9.371 bekommt eine Aufgabe nur, wer sie sieht
        buero_konto(db, emp)
        db.commit()
    return emp


def _uebernehmen(db, task_id):
    emp = _mitarbeiter(db)
    konto = AppUser(username="bea", display_name="Bea Büro", role="buero_auftrag", active=True, employee_id=emp.id, password_hash="x")
    db.add(konto)
    db.commit()
    assert db.get(Task, task_id).assigned_employee_id is None  # ohne Sachbearbeiter: im Büro-Eingang
    claim_task(db, task_id, konto)


ANGEFASST = {
    "spalte gewechselt": lambda db, t: update_task(db, t, status="in_arbeit"),
    "erledigt": lambda db, t: update_task(db, t, status="erledigt"),
    "mit unteraufgabe": lambda db, t: add_checklist_item(db, t, "Fotos ansehen"),
    "vorgang daraus": lambda db, t: create_follow_up_project_for_task(db, t),
    "prioritaet geaendert": lambda db, t: (_aelter(db, t), update_task(db, t, priority="hoch")),
    "faelligkeit gesetzt": lambda db, t: (_aelter(db, t), update_task(db, t, due_date=date(2026, 12, 1))),
    "beschreibung geaendert": lambda db, t: (_aelter(db, t), update_task(db, t, description="Kunde anrufen")),
    "zugewiesen": lambda db, t: (_aelter(db, t), update_task(db, t, assigned_employee_id=_mitarbeiter(db, "Carl").id)),
    "uebernommen": lambda db, t: (_aelter(db, t), _uebernehmen(db, t)),
    "archiviert": lambda db, t: (_aelter(db, t), set_task_archived(db, t, True)),
}


def test_unangetastete_folgeaufgabe_geht_mit_dem_entwurf():
    db = db_session()
    _order, report_id, finding_id, task_id = _entwurf_mit_folgeaufgabe(db)
    assert delete_report(db, report_id) is True
    assert db.get(ServiceReport, report_id) is None and db.get(Finding, finding_id) is None
    assert db.get(Task, task_id) is None


def test_unangetastete_aeltere_folgeaufgabe_geht_auch():
    """Die beiden Zeitpunkte des Anlegens liegen Mikrosekunden auseinander -- das ist keine Änderung."""
    db = db_session()
    _order, report_id, _finding_id, task_id = _entwurf_mit_folgeaufgabe(db)
    task = db.get(Task, task_id)
    assert task.updated_at != task.created_at  # so legt das Anlegen sie an
    _aelter(db, task_id)
    delete_report(db, report_id)
    assert db.get(Task, task_id) is None


@pytest.mark.parametrize("art", sorted(ANGEFASST))
def test_angefasste_folgeaufgabe_bleibt_mit_vermerk(art, feste_uhr):
    db = db_session()
    _order, report_id, finding_id, task_id = _entwurf_mit_folgeaufgabe(db)
    beschreibung = db.get(Task, task_id).description
    ANGEFASST[art](db, task_id)
    db.expire_all()
    beschreibung = db.get(Task, task_id).description  # „beschreibung geaendert“ hat sie ersetzt
    assert delete_report(db, report_id, AppUser(username="anna", display_name="Anna Admin", role="admin")) is True
    db.expire_all()
    assert db.get(ServiceReport, report_id) is None and db.get(Finding, finding_id) is None
    task = db.get(Task, task_id)
    assert task is not None, f"{art}: die angefasste Folgeaufgabe ging mit dem Entwurf"
    vermerk = f"Der Berichtsentwurf mit diesem Befund wurde am {berlin_today():%d.%m.%Y} von Anna Admin gelöscht – bitte prüfen."
    assert task.description == f"{vermerk}\n\n{beschreibung}"


def test_vorgang_aus_der_aufgabe_bleibt_bestehen(feste_uhr):
    db = db_session()
    _order, report_id, _finding_id, task_id = _entwurf_mit_folgeaufgabe(db)
    vorgang = create_follow_up_project_for_task(db, task_id)
    delete_report(db, report_id)
    assert db.get(Project, vorgang["project_id"]) is not None and db.get(Order, vorgang["order_id"]) is not None
    assert db.get(Task, task_id) is not None


def test_nur_die_angefasste_von_zwei_folgeaufgaben_bleibt(feste_uhr):
    db = db_session()
    _order, report_id, _f1, unangetastet = _entwurf_mit_folgeaufgabe(db)
    zweiter = create_finding(db, report_id, "Rinne verstopft", "gering", "buero_pruefen")
    angefasst = zweiter["follow_up_task_id"]
    add_checklist_item(db, angefasst, "Rinne prüfen")
    delete_report(db, report_id)
    assert db.get(Task, unangetastet) is None
    assert db.get(Task, angefasst) is not None and db.get(Task, angefasst).checklist_items[0].title == "Rinne prüfen"


def test_ueber_die_route_nennt_der_vermerk_das_konto(threaded_db_session, router_test_client, feste_uhr):
    from app.routers.service_reports import router as service_reports_router

    db = threaded_db_session
    _order, report_id, _finding_id, task_id = _entwurf_mit_folgeaufgabe(db, "9302")
    update_task(db, task_id, status="in_arbeit")
    client = router_test_client(db, service_reports_router, role="buero_auftrag", display_name="Bea Büro")
    assert client.delete(f"/api/service-reports/{report_id}").status_code == 200
    db.expire_all()
    assert db.get(Task, task_id).description.startswith(
        f"Der Berichtsentwurf mit diesem Befund wurde am {berlin_today():%d.%m.%Y} von Bea Büro gelöscht – bitte prüfen.\n\n")
