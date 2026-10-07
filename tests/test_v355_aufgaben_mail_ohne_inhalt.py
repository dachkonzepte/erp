"""Aufgaben-Mails ohne Inhalt der Aufgabe (1.8.53, Betreibervorgabe 2c-2b Nacharbeiten, Punkt 1).

Eine Benachrichtigung über eine zugewiesene Aufgabe geht an die Adresse im Mitarbeiterprofil (kann privat sein) und
steht im Versandprotokoll. Sie nennt nur die Art (aus dem Ursprung der Aufgabe) und den Link -- nie Titel,
Beschreibung, Projekt, Fälligkeit, Priorität, Ursprungstext oder Checkliste.

Zwei Prüfungen über ALLE Aufgaben-Mails:
- Struktur (AST über app/): jeder dispatch_email()-Aufruf nennt seine Versandart als Konstante (sonst begründete
  Ausnahme); die Versandart "aufgabe" kommt nur aus bekannten Funktionen, und diese lesen an der Aufgabe nur die
  erlaubten Felder (id, source_module, assigned_employee) -- die Aufgabe selbst wird nie weitergereicht.
- Versand: jedes Textfeld der Aufgabe (aus den Spalten des Modells, ein neues kommt automatisch dazu), Projekt,
  Fälligkeit und Checkliste tragen eine Markierung; über alle drei Wege einer Zuweisung (Anlegen, Bearbeiten,
  Übernehmen) erscheint keine in Betreff, Text oder Protokollzeile.
"""

import ast
import email
from datetime import date
from email.header import decode_header, make_header
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import String, Text, select

from app.email_sending import update_smtp_settings
from app.models import AppUser, Customer, EmailDispatch, Employee, EmployeeProfile, Project, Task, TaskChecklistItem
from app.notice_letters import LETTER_KINDS
from app.project_pipeline_columns import default_pipeline_column_id
from app.settings import load_general_settings
from app.tasks import (
    TASK_MAIL_KIND_DEFAULT, TASK_MAIL_KINDS, TASK_MAIL_SUBJECT, claim_task, create_task, task_mail_kind, update_task,
)

APP = Path(__file__).resolve().parent.parent / "app"

# Funktionen, die eine Aufgaben-Mail versenden (Datei::Funktion), und was sie an der Aufgabe lesen dürfen.
TASK_MAIL_SENDERS = {"tasks.py::notify_task_assignment"}
TASK_FIELDS_ALLOWED = {"id", "source_module", "assigned_employee"}
# dispatch_email() mit einer Variablen als Versandart -- begründet: kann nie "aufgabe" sein.
VARIABLE_TYPE_ALLOWED = {
    # seit 1.8.67 gemeinsam für Briefe und Abnahmeprotokoll: document_type ist die Briefart aus LETTER_KINDS
    # (send_notice_letter(), letter_kind() lehnt alles andere ab) bzw. fest "checkliste" (app/protocol_dispatch.py)
    "notice_letters.py::dispatch_to_client",
}

MARK = "MARKE7f3a"
DUE = date(2031, 7, 19)
# Spalten, die keinen frei wählbaren Text tragen (Schlüssel, die die Geschäftslogik prüft).
KEY_COLUMNS = {"status", "source_module", "min_visible_role"}


# --- Struktur ---------------------------------------------------------------------------------

def _functions(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _dispatch_calls():
    """(Datei::Funktion, Versandart-Knoten, Zeile) je dispatch_email()-Aufruf unter app/."""
    for path in sorted(APP.rglob("*.py")):
        rel = path.relative_to(APP).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for func in _functions(tree):
            for node in ast.walk(func):
                if not isinstance(node, ast.Call):
                    continue
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name != "dispatch_email":
                    continue
                kind = next((k.value for k in node.keywords if k.arg == "document_type"), None)
                yield f"{rel}::{func.name}", kind, node.lineno


def test_jede_versandart_ist_konstant_oder_begruendet():
    variable = sorted(f"{where}:{line}" for where, kind, line in _dispatch_calls()
                      if not isinstance(kind, ast.Constant) and where not in VARIABLE_TYPE_ALLOWED)
    assert variable == [], "dispatch_email() mit nicht konstanter Versandart -- kann eine Aufgaben-Mail sein"
    assert "aufgabe" not in LETTER_KINDS


def test_aufgaben_mails_nur_aus_bekannten_funktionen():
    senders = {where for where, kind, _ in _dispatch_calls()
               if isinstance(kind, ast.Constant) and kind.value == "aufgabe"}
    assert senders == TASK_MAIL_SENDERS


def _function_node(where: str):
    rel, name = where.split("::")
    tree = ast.parse((APP / rel).read_text(encoding="utf-8"))
    return next(f for f in _functions(tree) if f.name == name)


@pytest.mark.parametrize("where", sorted(TASK_MAIL_SENDERS))
def test_aufgaben_mail_liest_nur_art_und_link(where):
    """An der Aufgabe nur erlaubte Felder; die Aufgabe selbst geht an keine Hilfsfunktion (die sonst den Titel lesen
    könnte) -- jedes Vorkommen von `task` ist der Anfang eines erlaubten Attributs oder der Parameter."""
    func = _function_node(where)
    parents = {}
    for node in ast.walk(func):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    bad = []
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and node.id == "task":
            parent = parents.get(node)
            if not (isinstance(parent, ast.Attribute) and parent.value is node and parent.attr in TASK_FIELDS_ALLOWED):
                attr = parent.attr if isinstance(parent, ast.Attribute) else type(parent).__name__
                bad.append(f"Zeile {node.lineno}: task -> {attr}")
    assert bad == []
    assert [a.arg for a in func.args.args] == ["db", "task"]


def test_gegenprobe_strukturtest_findet_den_titel():
    """Die alte Fassung (Titel im Betreff) fiele auf."""
    old = ast.parse('def notify_task_assignment(db, task):\n    subject = f"Neue Aufgabe: {task.title}"\n'
                    '    helper(task)\n')
    func = next(_functions(old))
    names = [n for n in ast.walk(func) if isinstance(n, ast.Name) and n.id == "task"]
    parents = {c: n for n in ast.walk(func) for c in ast.iter_child_nodes(n)}
    found = [parents[n].attr if isinstance(parents[n], ast.Attribute) else "Aufruf" for n in names]
    assert sorted(found) == ["Aufruf", "title"]
    assert not all(isinstance(parents[n], ast.Attribute) and parents[n].attr in TASK_FIELDS_ALLOWED for n in names)


# --- Versand ----------------------------------------------------------------------------------

@pytest.fixture
def mails():
    sent = []
    conn = MagicMock()
    conn.sendmail.side_effect = lambda sender, to, raw: sent.append(raw)
    with patch("app.email_sending.smtplib.SMTP", return_value=conn):
        yield sent


def _setup(db, *, base_url="https://erp.example.test/"):
    update_smtp_settings(db, host="smtp.example.com", port=587, username="buero@example.com", encryption="starttls",
                         sender_email="buero@example.com", sender_name="Test GmbH", password="geheim123")
    general = load_general_settings(db)
    general.public_base_url = base_url
    emp = Employee(employee_number="M-1", first_name=f"Vorname{MARK}", last_name="Muster",
                   employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    customer = Customer(name=f"Kunde {MARK}", last_name=f"Kunde {MARK}")
    db.add_all([emp, customer])
    db.flush()
    project = Project(project_number=f"P-{MARK}", name=f"Projekt {MARK}", customer_id=customer.id,
                      pipeline_column_id=default_pipeline_column_id(db))
    db.add(project)
    db.flush()
    db.add(EmployeeProfile(employee_id=emp.id, email="erika@example.com"))
    db.commit()
    return emp, project


def _marked_task(db, project, **values) -> Task:
    """Eine Aufgabe, deren JEDES Textfeld eine Markierung trägt (aus den Spalten des Modells)."""
    fields = {}
    for column in Task.__table__.columns:
        if isinstance(column.type, (String, Text)) and column.name not in KEY_COLUMNS:
            fields[column.name] = f"{column.name}-{MARK}"
    fields.update(status="offen", source_module="maengel", due_date=DUE, project_id=project.id, **values)
    task = Task(**fields)
    db.add(task)
    db.flush()
    db.add(TaskChecklistItem(task_id=task.id, title=f"Punkt {MARK}", sort_order=10))
    db.commit()
    assert {c.name for c in Task.__table__.columns if isinstance(c.type, (String, Text))} - KEY_COLUMNS <= set(fields)
    return task


def _decoded(raw: str) -> tuple[str, str]:
    msg = email.message_from_string(raw)
    subject = str(make_header(decode_header(msg["Subject"])))
    body = "".join(part.get_payload(decode=True).decode("utf-8") for part in msg.walk()
                   if part.get_content_type() == "text/plain")
    return subject, body


def _protocol_text(db) -> str:
    rows = db.scalars(select(EmailDispatch)).all()
    return " ".join(str(getattr(r, c.name)) for r in rows for c in EmailDispatch.__table__.columns
                    if getattr(r, c.name) is not None)


def _assert_without_content(db, mails, task_id: int, kind: str, link: str):
    assert mails, "keine Mail versendet"
    for raw in mails:
        subject, body = _decoded(raw)
        for text in (subject, body):
            assert MARK not in text
            assert DUE.strftime("%d.%m.%Y") not in text and DUE.isoformat() not in text
        assert subject == TASK_MAIL_SUBJECT
        assert f"Art: {kind}" in body
        assert f"Link: {link}" in body
        assert MARK not in raw  # auch nicht unkodiert im Rohtext (Kopfzeilen)
    protocol = _protocol_text(db)
    assert MARK not in protocol and "aufgabe" in protocol


def test_anlegen_mit_zuweisung(db_session, mails):
    db = db_session
    emp, project = _setup(db)
    task = create_task(db, title=f"Titel {MARK}", description=f"Beschreibung {MARK}", priority="dringend",
                       due_date=DUE, assigned_employee_id=emp.id, project_id=project.id, source_module="maengel",
                       source_label=f"Mangel – {MARK}", source_url=f"/orders/1#{MARK}")
    _assert_without_content(db, mails, task["id"], "Mangel", f"https://erp.example.test/tasks?task={task['id']}")
    _, body = _decoded(mails[0])
    assert "dringend" not in body


def test_bearbeiten_mit_neuer_zuweisung(db_session, mails):
    db = db_session
    emp, project = _setup(db)
    task = _marked_task(db, project)
    update_task(db, task.id, assigned_employee_id=emp.id)
    _assert_without_content(db, mails, task.id, "Mangel", f"https://erp.example.test/tasks?task={task.id}")


def test_uebernehmen(db_session, mails):
    db = db_session
    emp, project = _setup(db)
    task = _marked_task(db, project, min_visible_role="buero_auftrag")
    user = AppUser(username="anna", display_name="Anna", role="buero_auftrag", active=True, password_hash="x",
                   employee_id=emp.id)
    db.add(user)
    db.commit()
    claim_task(db, task.id, user)
    _assert_without_content(db, mails, task.id, "Mangel", f"https://erp.example.test/tasks?task={task.id}")


def test_ohne_oeffentliche_adresse_der_pfad(db_session, mails):
    db = db_session
    emp, project = _setup(db, base_url=None)
    task = create_task(db, title=f"Titel {MARK}", assigned_employee_id=emp.id)
    _assert_without_content(db, mails, task["id"], TASK_MAIL_KIND_DEFAULT,
                            f"im ERP unter „Aufgaben“ (/tasks?task={task['id']})")


@pytest.mark.parametrize("source_module", sorted(TASK_MAIL_KINDS) + [None, "unbekannt"])
def test_art_nur_aus_dem_ursprung(source_module):
    kind = task_mail_kind(source_module)
    assert kind == TASK_MAIL_KINDS.get(source_module or "", TASK_MAIL_KIND_DEFAULT)
    assert MARK not in kind


def test_gegenprobe_versand_findet_den_titel(db_session, mails, monkeypatch):
    """Mit einem Betreff, der den Titel nennt, wird die Versandprüfung rot (tasks.py importiert dispatch_email erst
    beim Aufruf -- deshalb am Ursprung ersetzt)."""
    import app.email_dispatch as dispatch_module
    db = db_session
    emp, project = _setup(db)
    original = dispatch_module.dispatch_email

    def leaky(db, **kw):
        task = db.get(Task, kw["document_id"])
        return original(db, **{**kw, "subject": f"Neue Aufgabe: {task.title}"})

    monkeypatch.setattr(dispatch_module, "dispatch_email", leaky)
    task = create_task(db, title=f"Titel {MARK}", assigned_employee_id=emp.id)
    with pytest.raises(AssertionError):
        _assert_without_content(db, mails, task["id"], TASK_MAIL_KIND_DEFAULT,
                                f"https://erp.example.test/tasks?task={task['id']}")
