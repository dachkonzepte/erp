"""Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ (09.10.2026, docs/archiv/befund-vor-echtbetrieb.md), Punkt 5:
Schlüssel von Aufgaben- und Pipelinespalten über 40 bzw. 30 Zeichen unter PostgreSQL.

Der Schlüssel einer neuen Spalte entsteht aus der Bezeichnung (_slugify(): Kleinbuchstaben, alles außer a-z und 0-9 wird "_",
Umlaute auch; bei Gleichheit "_2", "_3" …), ungekürzt. Die Bezeichnung darf 80 Zeichen haben (TaskColumnCreate,
ProjectPipelineColumnCreate). TaskColumn.key und ProjectPipelineColumn.key sind String(40), Task.status -- dort steht der Schlüssel
der Spalte einer Aufgabe -- String(30). Unter SQLite wird jeder Wert still gespeichert; PostgreSQL lehnt einen zu langen ab
(StringDataRightTruncation -> DataError, Router 500). tests/test_v364_feste_werte_spaltenlaenge.py sieht nur feste Werte, diese
Spalten stehen dort als Nutzerwerte in OHNE_FESTE_WERTE.

Seit 1.8.71 behoben: der Schlüssel wird beim Entstehen gekürzt, passend zur kürzesten Spalte, in die er geschrieben wird
(app/spaltenlaenge.py) -- Aufgabenspalte 30 (Task.status), Pipelinespalte 40. Die Tests 5a-5c sind die Abnahmetests (bis dahin
xfail, tests/befund_vor_echtbetrieb.py); ein Abbruch an der Datenbank wird zu AssertionError (_ohne_datenbankfehler()). Ablehnen mit
Meldung (ValueError, Router 400) ist erlaubt."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app import project_pipeline_columns, task_columns
from app.models import ProjectPipelineColumn, Task, TaskColumn
from app.tasks import create_task, update_task
from tests.befund_vor_echtbetrieb import pg_sitzung, vorbedingung
from tests.test_v133_invoices import db_session

# 40 Zeichen Schlüssel ("Rückmeldung" -> "r_ckmeldung"): passt in TaskColumn.key, nicht in Task.status.
LABEL_40 = "Wartet auf Rückmeldung des Auftraggebers"
# 63 Zeichen Schlüssel und Bezeichnung (erlaubt: höchstens 80).
LABEL_63 = "Wartet auf Rückmeldung des Auftraggebers und der Hausverwaltung"


@pytest.fixture
def pg():
    with pg_sitzung("spalten") as db:
        yield db


def _ohne_datenbankfehler(db, fn, *args, **kwargs):
    """Aktion wie über die API; Ablehnen (ValueError) ist erlaubt, ein Abbruch an der Datenbank wird zum AssertionError."""
    try:
        return fn(*args, **kwargs)
    except DBAPIError as exc:
        db.rollback()
        raise AssertionError(f"Datenbank lehnt ab: {type(exc.orig).__name__}: {str(exc.orig).splitlines()[0]}") from exc
    except ValueError:
        db.rollback()
        return None


def test_keys_are_shortened_where_they_arise_also_under_sqlite():
    """Seit 1.8.71 (bis dahin hier grün festgehalten: 40 bzw. 63 Zeichen still gespeichert): auch SQLite bekommt nur gekürzte
    Schlüssel -- Aufgabenspalte höchstens 30 (Task.status), Pipelinespalte höchstens 40."""
    db = db_session()
    vorbedingung(len(task_columns._slugify(LABEL_40)) == 40 and len(task_columns._slugify(LABEL_63)) == 63)
    assert task_columns.create_column(db, LABEL_63)["key"] == "wartet_auf_r_ckmeldung_des_auf"
    assert project_pipeline_columns.create_column(db, LABEL_63)["key"] == "wartet_auf_r_ckmeldung_des_auftraggebers"
    spalte = task_columns.create_column(db, LABEL_40)
    assert spalte["key"] == "wartet_auf_r_ckmeldung_des_a_2"  # gleiche ersten 30 Zeichen: eindeutig, passt trotzdem
    task = create_task(db, "Rückruf", status=spalte["key"])
    assert db.get(Task, task["id"]).status == spalte["key"]


def test_postgresql_task_column_with_a_long_label(pg):
    """5a (seit 1.8.71 behoben): Aufgabenspalte mit erlaubter Bezeichnung, Schlüssel über 40 Zeichen."""
    _ohne_datenbankfehler(pg, task_columns.create_column, pg, LABEL_63)
    assert all(len(k) <= 40 for k in pg.scalars(select(TaskColumn.key)))


def test_postgresql_pipeline_column_with_a_long_label(pg):
    """5b (seit 1.8.71 behoben): Pipelinespalte mit erlaubter Bezeichnung, Schlüssel über 40 Zeichen."""
    _ohne_datenbankfehler(pg, project_pipeline_columns.create_column, pg, LABEL_63)
    assert all(len(k) <= 40 for k in pg.scalars(select(ProjectPipelineColumn.key)))


@pytest.mark.parametrize("weg", ["verschieben", "neu_in_der_spalte", "neu_ohne_status"])
def test_postgresql_task_column_with_a_key_of_31_to_40_characters(pg, weg):
    """5c (seit 1.8.71 behoben): Aufgabenspalte, deren Schlüssel aus der Bezeichnung 40 Zeichen hätte -- eine Aufgabe kommt
    hinein, auch wenn die Spalte vorn steht. Bis 1.8.70 verlangte die Vorbedingung den 40 Zeichen langen Schlüssel (so
    entstand der Fehler); seither nur, dass er aus der Bezeichnung kommt."""
    spalte = _ohne_datenbankfehler(pg, task_columns.create_column, pg, LABEL_40)
    if spalte is None:
        return  # abgelehnt mit Meldung: es gibt die Spalte nicht
    vorbedingung(spalte["key"].startswith("wartet_auf_r_ckmeldung"), spalte["key"])
    if weg == "verschieben":
        task = create_task(pg, "Rückruf")
        _ohne_datenbankfehler(pg, update_task, pg, task["id"], status=spalte["key"])
        pg.expire_all()
        assert pg.get(Task, task["id"]).status == spalte["key"]
    elif weg == "neu_in_der_spalte":
        task = _ohne_datenbankfehler(pg, create_task, pg, "Rückruf", status=spalte["key"])
        assert task is not None and task["status"] == spalte["key"]
    else:
        ids = [c.id for c in pg.scalars(select(TaskColumn).order_by(TaskColumn.sort_order, TaskColumn.id))]
        task_columns.reorder_columns(pg, [spalte["id"]] + [i for i in ids if i != spalte["id"]])
        task = _ohne_datenbankfehler(pg, create_task, pg, "Mangel beseitigen")  # wie die Aufgabe eines Mangels
        assert task is not None and task["status"] == spalte["key"]


def test_today_postgresql_short_keys_work(pg):
    """Grün, Gegenprobe: mit kurzer Bezeichnung entstehen beide Spalten, und eine Aufgabe kommt hinein."""
    spalte = task_columns.create_column(pg, "Wartet auf Kunde")
    task = create_task(pg, "Rückruf", status=spalte["key"])
    assert task["status"] == "wartet_auf_kunde"
    assert project_pipeline_columns.create_column(pg, "Warten auf Material")["key"] == "warten_auf_material"
