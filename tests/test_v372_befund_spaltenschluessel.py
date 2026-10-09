"""Befund „Vor dem Echtbetrieb: Geld und Sicherheit“ (09.10.2026, docs/archiv/befund-vor-echtbetrieb.md), Punkt 5:
Schlüssel von Aufgaben- und Pipelinespalten über 40 bzw. 30 Zeichen unter PostgreSQL.

Der Schlüssel einer neuen Spalte entsteht aus der Bezeichnung (_slugify(): Kleinbuchstaben, alles außer a-z und 0-9 wird "_",
Umlaute auch; bei Gleichheit "_2", "_3" …), ungekürzt. Die Bezeichnung darf 80 Zeichen haben (TaskColumnCreate,
ProjectPipelineColumnCreate). TaskColumn.key und ProjectPipelineColumn.key sind String(40), Task.status -- dort steht der Schlüssel
der Spalte einer Aufgabe -- String(30). Unter SQLite wird jeder Wert still gespeichert; PostgreSQL lehnt einen zu langen ab
(StringDataRightTruncation -> DataError, Router 500). tests/test_v364_feste_werte_spaltenlaenge.py sieht nur feste Werte, diese
Spalten stehen dort als Nutzerwerte in OHNE_FESTE_WERTE.

Fehler als xfail (tests/befund_vor_echtbetrieb.py); ein Abbruch an der Datenbank wird zu AssertionError (_ohne_datenbankfehler()).
Ablehnen mit Meldung (ValueError, Router 400) ist erlaubt."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app import project_pipeline_columns, task_columns
from app.models import ProjectPipelineColumn, Task, TaskColumn
from app.tasks import create_task, update_task
from tests.befund_vor_echtbetrieb import befund, pg_sitzung, vorbedingung
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


def test_today_keys_come_from_the_label_without_shortening():
    """Grün, zur Einordnung (SQLite): die Schlüssel sind 40 bzw. 63 Zeichen lang und werden still gespeichert."""
    db = db_session()
    vorbedingung(len(task_columns._slugify(LABEL_40)) == 40 and len(task_columns._slugify(LABEL_63)) == 63)
    assert len(task_columns.create_column(db, LABEL_63)["key"]) == 63
    assert len(project_pipeline_columns.create_column(db, LABEL_63)["key"]) == 63
    spalte = task_columns.create_column(db, LABEL_40)
    task = create_task(db, "Rückruf", status=spalte["key"])
    assert len(db.get(Task, task["id"]).status) == 40  # String(30)


@befund("5a", "Aufgabenspalte mit erlaubter Bezeichnung, Schlüssel über 40 Zeichen: Anlegen bricht unter PostgreSQL ab (500)")
def test_postgresql_task_column_with_a_long_label(pg):
    _ohne_datenbankfehler(pg, task_columns.create_column, pg, LABEL_63)
    assert all(len(k) <= 40 for k in pg.scalars(select(TaskColumn.key)))


@befund("5b", "Pipelinespalte mit erlaubter Bezeichnung, Schlüssel über 40 Zeichen: Anlegen bricht unter PostgreSQL ab (500)")
def test_postgresql_pipeline_column_with_a_long_label(pg):
    _ohne_datenbankfehler(pg, project_pipeline_columns.create_column, pg, LABEL_63)
    assert all(len(k) <= 40 for k in pg.scalars(select(ProjectPipelineColumn.key)))


@befund("5c", "Aufgabenspalte mit Schlüssel von 31 bis 40 Zeichen entsteht, aber keine Aufgabe kommt hinein (Task.status "
              "String(30)) -- steht sie vorn, scheitert jede neue Aufgabe, auch die automatischen")
@pytest.mark.parametrize("weg", ["verschieben", "neu_in_der_spalte", "neu_ohne_status"])
def test_postgresql_task_column_with_a_key_of_31_to_40_characters(pg, weg):
    spalte = _ohne_datenbankfehler(pg, task_columns.create_column, pg, LABEL_40)
    if spalte is None:
        return  # abgelehnt mit Meldung: es gibt die Spalte nicht
    vorbedingung(len(spalte["key"]) == 40, spalte["key"])
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
