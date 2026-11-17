"""Version 1.9.344 -- jedes Löschen einer Aufgabe steht in der Änderungshistorie (Runde ab 1.9.343, Punkt 2).

Entscheidung Tobias (17.11.2026): nur das Löschen von Aufgaben, jedes -- auch das Mitlöschen mit einem Entwurf --, mit Titel, Konto, Zeitpunkt und
Anlass; sonstige Änderungen an Aufgaben nicht. Die Wege, die eine Aufgabe löschen: von Hand (`DELETE /api/tasks/{id}`), mit dem Berichtsentwurf
(unangetastete Folgeaufgabe, `DELETE /api/service-reports/{id}`), mit dem Wartungsvertrag (seine Erinnerungen, `DELETE /api/maintenance-contracts/{id}`).
Alle gehen über `app/tasks.py::aufgabe_loeschen()`; den Eintrag schreibt `app/audit.py::collect_audit()` im Flush -- auch an `aufgabe_loeschen()` vorbei
(„ohne Angabe“). Ein Löschen über die Tabelle sähe die Historie nicht: verboten, Wächter unten."""

import ast
import json
import re
from datetime import date
from pathlib import Path

from sqlalchemy import func, select

from app.findings import create_finding
from app.maintenance_contracts import check_due_contracts_and_create_reminders
from app.models import AuditLog, Task, TaskChecklistItem
from app.routers.audit import router as audit_router
from app.routers.maintenance_contracts import router as vertraege_router
from app.routers.service_reports import router as berichte_router
from app.routers.tasks import router as aufgaben_router
from app.service_reports import create_report
from app.tasks import add_checklist_item, create_task, set_task_archived, update_task
from tests.test_v133_invoices import make_order_with_item
from tests.test_v153_mahnwesen import db_session
from tests.test_v214_findings_and_photos import _build_extra_order
from tests.test_v333_auswahl_inaktiv import nur_mit_node
from tests.test_v741_vertrag_loeschen import _vertrag

APP = Path(__file__).resolve().parents[1] / "app"
VORLAGEN = APP / "templates"


def _eintraege(db):
    db.expire_all()
    return db.scalars(select(AuditLog).where(AuditLog.entity_type == "Aufgabe").order_by(AuditLog.id)).all()


def _geloescht(db):
    return [e for e in _eintraege(db) if e.action == "gelöscht"]


def test_von_hand_mit_titel_konto_zeitpunkt_und_anlass(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _ = make_order_with_item(db)
    task = create_task(db, "Rückruf Kunde", project_id=order.project_id)
    client = router_test_client(db, aufgaben_router, user_id=901, display_name="Anna Admin")
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 200
    assert db.get(Task, task["id"]) is None
    [e] = _geloescht(db)
    assert (e.entity_id, e.entity_label, e.project_id) == (str(task["id"]), f"Nr. {task['id']} · Rückruf Kunde", order.project_id)
    assert (e.actor_user_id, e.actor_name) == (901, "Anna Admin")
    assert (e.field_name, e.field_label, e.old_value, e.new_value) == ("anlass", "Anlass", None, "von Hand")
    assert e.occurred_at is not None


def test_mit_dem_berichtsentwurf_nur_die_unangetastete(threaded_db_session, router_test_client):
    db = threaded_db_session
    order, _customer, _project = _build_extra_order(db, "9401")
    report = create_report(db, order.id, "rapport", description="Arbeiten laut Testfall")
    weg = create_finding(db, report["id"], "Riss in der Attika", "mittel", "buero_pruefen")["follow_up_task_id"]
    bleibt = create_finding(db, report["id"], "Rinne verstopft", "gering", "buero_pruefen")["follow_up_task_id"]
    update_task(db, bleibt, status="in_arbeit")
    titel = db.get(Task, weg).title
    client = router_test_client(db, berichte_router, user_id=902, display_name="Bea Büro", role="buero_auftrag")
    assert client.delete(f"/api/service-reports/{report['id']}").status_code == 200
    assert db.get(Task, weg) is None and db.get(Task, bleibt) is not None
    [e] = _geloescht(db)  # die angefasste ist nicht gelöscht, ihr Vermerk ist keine Zeile der Historie
    assert (e.entity_id, e.entity_label, e.actor_user_id, e.actor_name) == (str(weg), f"Nr. {weg} · {titel}", 902, "Bea Büro")
    assert e.new_value == f"mit dem Berichtsentwurf Nr. {report['id']} (Auftrag {order.order_number}), unangetastet"


def test_mit_dem_wartungsvertrag_auch_mit_unteraufgabe(threaded_db_session, router_test_client):
    """Bis 1.9.343 löschte delete_contract() die Erinnerungen über die Tabelle (delete(Task)): ohne Eintrag, und mit einer Unteraufgabe scheiterte es
    am Fremdschlüssel (live unter PostgreSQL 500)."""
    db = threaded_db_session
    _kunde, _objekt, vertrag = _vertrag(db, faellig=date(2026, 1, 1))
    check_due_contracts_and_create_reminders(db)
    erinnerungen = db.scalars(select(Task).where(Task.source_url == f"/maintenance-contracts/{vertrag['id']}")).all()
    assert erinnerungen
    add_checklist_item(db, erinnerungen[0].id, "Termin mit dem Kunden abstimmen")
    client = router_test_client(db, vertraege_router, user_id=903, display_name="Anna Admin")
    r = client.delete(f"/api/maintenance-contracts/{vertrag['id']}")
    assert r.status_code == 200, r.text
    assert db.scalar(select(func.count()).select_from(TaskChecklistItem)) == 0
    eintraege = _geloescht(db)
    assert sorted(int(e.entity_id) for e in eintraege) == sorted(t.id for t in erinnerungen)
    assert {e.new_value for e in eintraege} == {"mit dem Wartungsvertrag „Dachwartung“ (Erinnerung)"}
    assert {(e.actor_user_id, e.actor_name) for e in eintraege} == {(903, "Anna Admin")}


def test_an_aufgabe_loeschen_vorbei_steht_es_trotzdem_drin():
    db = db_session()
    task = db.get(Task, create_task(db, "Material bestellen")["id"])
    db.delete(task)
    db.commit()
    [e] = _geloescht(db)
    assert (e.entity_label, e.new_value) == (f"Nr. {task.id} · Material bestellen", "ohne Angabe (ohne Anfrage)")


def test_sonstige_aenderungen_an_aufgaben_nicht():
    db = db_session()
    order, _ = make_order_with_item(db)
    vorher = db.scalar(select(func.count()).select_from(AuditLog))  # alle Einträge, gleich welcher Art (seit der Gegenprobe 344_10)
    tid = create_task(db, "Rückruf Kunde", project_id=order.project_id)["id"]
    update_task(db, tid, priority="hoch", description="Bitte heute", status="in_arbeit")
    add_checklist_item(db, tid, "Nummer suchen")
    set_task_archived(db, tid, True)
    assert db.scalar(select(func.count()).select_from(AuditLog)) == vorher


def test_nur_der_admin_sieht_die_eintraege(threaded_db_session, router_test_client):
    db = threaded_db_session
    tid = create_task(db, "Mahnung prüfen")["id"]
    assert router_test_client(db, aufgaben_router, user_id=904).delete(f"/api/tasks/{tid}").status_code == 200
    for rolle, sichtbar in (("admin", True), ("buero_finanzen", False), ("buero_auftrag", False)):
        zeilen = router_test_client(db, audit_router, role=rolle).get("/api/audit-logs").json()
        assert any(z["entity_type"] == "Aufgabe" and z["action"] == "gelöscht" for z in zeilen) is sichtbar, rolle


def _ist_task(n) -> bool:
    return (isinstance(n, ast.Name) and n.id == "Task") or (isinstance(n, ast.Attribute) and n.attr == "Task")


def _query_task(n) -> bool:
    """Steckt in der Kette ein query(Task)/select(Task)?"""
    return any(isinstance(k, ast.Call) and isinstance(k.func, (ast.Name, ast.Attribute))
               and getattr(k.func, "attr", getattr(k.func, "id", None)) in ("query", "select") and k.args and _ist_task(k.args[0])
               for k in ast.walk(n))


def tabellen_loeschungen(quelle: str) -> list[int]:
    """Zeilen, die Aufgaben über die Tabelle löschen: delete(Task), Task.__table__.delete(), query(Task)….delete(), SQL „DELETE FROM tasks“."""
    zeilen = []
    for node in ast.walk(ast.parse(quelle)):
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)):
            name = getattr(node.func, "attr", getattr(node.func, "id", None))
            if name == "delete" and node.args and _ist_task(node.args[0]):
                zeilen.append(node.lineno)
            elif name == "delete" and isinstance(node.func, ast.Attribute) and (
                    (isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "__table__" and _ist_task(node.func.value.value))
                    or _query_task(node.func.value)):
                zeilen.append(node.lineno)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and re.search(r"delete\s+from\s+\"?tasks\b", node.value, re.I):
            zeilen.append(node.lineno)
    return zeilen


def test_waechter_kein_loeschen_von_aufgaben_ueber_die_tabelle():
    funde = [f"{p.relative_to(APP.parent)}:{z}" for p in sorted(APP.rglob("*.py")) for z in tabellen_loeschungen(p.read_text(encoding="utf-8"))]
    assert funde == [], f"Aufgaben über die Tabelle gelöscht (die Änderungshistorie sieht das nicht) -- app/tasks.py::aufgabe_loeschen() nehmen: {funde}"


def test_waechter_erkennt_jede_form():
    beispiele = ["db.execute(delete(Task).where(Task.id == 1))", "db.execute(sa.delete(models.Task))", "db.execute(Task.__table__.delete())",
                 "db.query(Task).filter(Task.id == 1).delete()", "db.execute(text('DELETE FROM tasks WHERE id = 1'))"]
    assert [bool(tabellen_loeschungen(b)) for b in beispiele] == [True] * len(beispiele)
    assert tabellen_loeschungen("db.delete(task)\ndb.execute(delete(TaskColumn))\ndb.query(Task).filter(Task.id == 1).update({})") == []


@nur_mit_node
def test_historie_zeigt_den_anlass():
    from tests.test_v314_dashboard_month_berlin import _node
    skript = "\n".join(re.findall(r"<script>(.*?)</script>", (VORLAGEN / "_verlauf.html").read_text(encoding="utf-8"), re.S))
    faelle = [{"action": "gelöscht", "field_name": "anlass", "new_value": "von Hand"}, {"action": "gelöscht"},
              {"action": "gelöscht", "field_name": "anlass", "new_value": "<b>x</b>"}]
    ergebnis = _node(skript + f"\nprocess.stdout.write(JSON.stringify({json.dumps(faelle)}.map(verlaufAenderung)));", "Europe/Berlin")
    assert ergebnis == ["Datensatz gelöscht – von Hand", "Datensatz gelöscht", "Datensatz gelöscht – &lt;b&gt;x&lt;/b&gt;"]
