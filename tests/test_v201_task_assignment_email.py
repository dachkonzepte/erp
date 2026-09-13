from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.email_sending import update_smtp_settings
from app.models import Employee, EmployeeProfile
from app.tasks import create_task, get_or_create_task_settings, update_task, update_task_settings


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _configure_smtp(db):
    update_smtp_settings(
        db, host="smtp.example.com", port=587, username="buero@example.com",
        encryption="starttls", sender_email="buero@example.com", sender_name="Test GmbH",
        password="geheim123",
    )


def make_employee_with_email(db, email="erika@example.com", number="T-1"):
    emp = Employee(employee_number=number, first_name="Erika", last_name="Eins", employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    db.add(emp); db.commit()
    db.add(EmployeeProfile(employee_id=emp.id, email=email)); db.commit()
    return emp


def make_employee_without_email(db):
    emp = Employee(employee_number="T-2", first_name="Otto", last_name="Zwei", employee_group="angestellt", hourly_wage="30", weekly_hours="40", active=True)
    db.add(emp); db.commit()
    return emp


def test_task_settings_default_to_notifications_enabled():
    db = db_session()
    settings = get_or_create_task_settings(db)
    assert settings.notify_on_assignment is True


@patch("app.email_sending.smtplib.SMTP")
def test_create_task_with_assignee_sends_notification(mock_smtp_cls):
    db = db_session()
    _configure_smtp(db)
    emp = make_employee_with_email(db)
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    create_task(db, title="Neue Aufgabe", assigned_employee_id=emp.id)

    mock_conn.sendmail.assert_called_once()
    sent_message = mock_conn.sendmail.call_args[0][2]
    assert "erika@example.com" in mock_conn.sendmail.call_args[0][1]
    assert "Neue Aufgabe" in sent_message


@patch("app.email_sending.smtplib.SMTP")
def test_create_task_without_assignee_sends_nothing(mock_smtp_cls):
    db = db_session()
    _configure_smtp(db)
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    create_task(db, title="Freistehend")

    mock_conn.sendmail.assert_not_called()


@patch("app.email_sending.smtplib.SMTP")
def test_no_notification_without_employee_profile_email(mock_smtp_cls):
    db = db_session()
    _configure_smtp(db)
    emp = make_employee_without_email(db)
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    created = create_task(db, title="X", assigned_employee_id=emp.id)

    assert created["id"] is not None  # das Anlegen selbst darf trotzdem gelingen
    mock_conn.sendmail.assert_not_called()


@patch("app.email_sending.smtplib.SMTP")
def test_no_notification_when_setting_disabled(mock_smtp_cls):
    db = db_session()
    _configure_smtp(db)
    update_task_settings(db, False)
    emp = make_employee_with_email(db)
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    create_task(db, title="X", assigned_employee_id=emp.id)

    mock_conn.sendmail.assert_not_called()


@patch("app.email_sending.smtplib.SMTP")
def test_update_task_notifies_only_on_actual_reassignment(mock_smtp_cls):
    db = db_session()
    _configure_smtp(db)
    emp1 = make_employee_with_email(db, email="erika@example.com", number="T-1")
    emp2 = make_employee_with_email(db, email="otto@example.com", number="T-2")
    mock_conn = MagicMock()
    mock_smtp_cls.return_value = mock_conn

    task = create_task(db, title="Unassigned")  # kein Versand, keine Zuweisung
    mock_conn.sendmail.assert_not_called()

    update_task(db, task["id"], title="Unassigned", description=None, status="offen",
                priority="normal", due_date=None, assigned_employee_id=emp1.id, project_id=None)
    assert mock_conn.sendmail.call_count == 1  # erste Zuweisung

    update_task(db, task["id"], title="Unassigned", description=None, status="in_arbeit",
                priority="normal", due_date=None, assigned_employee_id=emp1.id, project_id=None)
    assert mock_conn.sendmail.call_count == 1  # unveränderter Mitarbeiter -> keine neue Mail

    update_task(db, task["id"], title="Unassigned", description=None, status="in_arbeit",
                priority="normal", due_date=None, assigned_employee_id=emp2.id, project_id=None)
    assert mock_conn.sendmail.call_count == 2  # andere Person -> neue Mail


def test_create_task_does_not_fail_when_smtp_is_not_configured():
    """notify_task_assignment() fängt den ValueError von send_plain_email() ab -- ein noch
    nicht konfigurierter Mailserver darf das Speichern der Aufgabe nicht verhindern."""
    db = db_session()
    emp = make_employee_with_email(db)
    result = create_task(db, title="Ohne SMTP-Konfiguration", assigned_employee_id=emp.id)
    assert result["id"] is not None
