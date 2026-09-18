"""Self-Seeding gegen gleichzeitigen ersten Zugriff absichern (seit 1.4.6).

Ausgangspunkt: ein während der Betriebsmittelverwaltung-Stufe-3-Verifikation (1.4.5) gemeldeter
Nebenbefund -- app/option_settings.py::ensure_default_option_groups() konnte bei zwei
gleichzeitigen allerersten Zugriffen (zwei Arbeitsprozesse/Request-Threads auf einer frischen,
noch nie geseedeten Datenbank) mit einer unabgefangenen sqlalchemy.exc.IntegrityError
(UNIQUE-Verletzung auf group_key) scheitern -- beide Prozesse lesen "keine Gruppen vorhanden" und
versuchen dieselben Standardzeilen einzufügen, der zweite kollidiert mit dem, was der erste
inzwischen committet hat.

Geprüft und behoben: JEDES ensure_default_*()-Self-Seeding-Muster im Projekt (Dokumentkategorien,
Pipeline-Spalten, Aufgaben-Spalten, Mitarbeiterfunktionen, Seitenränder, Nummernkreise,
Arbeitszeitmodelle) -- alle wurden auf dasselbe Muster umgestellt: jeder Anlegeversuch läuft in
einem eigenen SAVEPOINT (db.begin_nested()), eine dabei auftretende IntegrityError wird als
"ein anderer Prozess war schneller, schon gesät" behandelt statt als Fehler weitergereicht zu
werden. Bewusst KEIN Sperrmechanismus (Locking) -- ein Advisory-Lock wäre PostgreSQL-spezifisch
und hätte unter SQLite (dem zweiten, gleichberechtigt unterstützten Dialekt dieses Projekts,
siehe CLAUDE.md "PostgreSQL-Umstieg") keine Entsprechung; das Abfangen der UNIQUE-Kollision ist
rein reaktiv, braucht keine neue Infrastruktur und ändert am Erfolgspfad (kein Kollisionsfall)
nichts.

Vier Funktionen im Projekt folgen demselben ensure_default_*()-Muster, haben aber KEINE eigene
UNIQUE-Kollision, gegen die dieselbe Technik greifen könnte (kein Constraint auf der jeweiligen
Tabelle -- ein Wettlauf würde dort NICHT crashen, sondern still doppelte Zeilen anlegen, eine
andere, leisere Fehlerklasse): app/document_layout.py::ensure_default_layout(),
app/payment_terms.py::ensure_default_payment_terms(), app/tax_keys.py::ensure_default_tax_keys(),
app/reminders.py::ensure_default_reminder_levels(). Eine Behebung dieser vier bräuchte zuerst eine
neue, eigene Migration (fehlende UNIQUE-Constraints ergänzen) -- separat gemeldet, nicht Teil
dieser Runde. Ebenso außerhalb dieser Runde: das strukturell verwandte, aber deutlich größere
"get_or_create_settings(id=1)"-Singleton-Muster (GeneralSettings, TaskSettings,
MaintenanceSettings u. v. a.) -- dort kollidiert ein PRIMARY-KEY statt eines Business-Keys, ein
eigener, größerer Sweep, nicht Gegenstand dieser Anfrage.

Testtechnik: zwei unabhängige Session-Objekte auf DIESELBE echte, temporäre SQLite-DATEI
(nicht :memory:, das wäre pro Connection isoliert und könnte den Wettlauf nie sichtbar machen).
Ein before_flush-Hook auf Session 1 lässt -- beim ERSTEN eigenen Flush-Versuch der zu prüfenden
Funktion -- Session 2 dieselbe Funktion vollständig (inklusive commit) durchlaufen, BEVOR Session
1s eigener Flush fortgesetzt wird. Session 1 kollidiert dadurch garantiert mit dem, was Session 2
inzwischen committet hat -- deterministisch, ohne echtes Threading/Timing-Abhängigkeit, mit
bereits im Projekt vorhandenen Mitteln (SQLAlchemys Event-System)."""

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app import (
    document_categories, employees, option_settings, project_pipeline_columns,
    settings as settings_module, task_columns, work_time_models,
)
from app.database import Base
from app.document_page_margins import ensure_default_margins
from app.models import (
    DocumentCategory, DocumentPageMargins, EmployeeFunction, NumberSequence,
    ProjectPipelineColumn, SettingOptionGroup, TaskColumn, WorkTimeBreakRule, WorkTimeModel,
    WorkTimeModelValidity,
)


def _file_sessions(tmp_path):
    """Zwei unabhängige Sessions auf dieselbe echte SQLite-Datei -- Voraussetzung für eine
    tatsächliche, datenebenen-Interleaving-Simulation (siehe Moduldocstring)."""
    db_path = tmp_path / "race.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return Session, Session()


def _race(db1, other_session_factory, seed_fn, *args, **kwargs):
    """Registriert den before_flush-Wettlauf-Hook auf db1 und ruft seed_fn(db1, *args, **kwargs)
    auf -- der Hook lässt beim ersten Flush-Versuch eine ZWEITE, unabhängige Session (auf
    derselben Datei) denselben Aufruf vollständig durchlaufen, bevor db1 fortfährt."""
    fired = {"v": False}
    db2 = other_session_factory()

    @event.listens_for(db1, "before_flush")
    def _inject(session, flush_context, instances):
        if fired["v"]:
            return
        fired["v"] = True
        seed_fn(db2, *args, **kwargs)

    result = seed_fn(db1, *args, **kwargs)
    db2.close()
    return result


def test_ensure_default_option_groups_survives_concurrent_first_access(tmp_path):
    """Der ursprünglich gemeldete Fund: zwei gleichzeitige erste Zugriffe auf die Optionsgruppen
    (group_key='units' war der reale Kollisionspunkt, da erster Dict-Eintrag)."""
    Session, db1 = _file_sessions(tmp_path)
    _race(db1, Session, option_settings.ensure_default_option_groups)

    check = Session()
    keys = check.scalars(select(SettingOptionGroup.group_key)).all()
    assert len(keys) == len(option_settings.DEFAULT_OPTION_GROUPS)
    assert len(keys) == len(set(keys))
    check.close()


def test_ensure_default_categories_survives_concurrent_first_access(tmp_path):
    """Nutzer-benanntes Beispiel "Dokumentkategorien"."""
    Session, db1 = _file_sessions(tmp_path)
    _race(db1, Session, document_categories.ensure_default_categories)

    check = Session()
    keys = check.scalars(select(DocumentCategory.key)).all()
    assert len(keys) == len(document_categories.DEFAULT_CATEGORIES)
    assert len(keys) == len(set(keys))
    check.close()


def test_ensure_default_pipeline_columns_survives_concurrent_first_access(tmp_path):
    """Nutzer-benanntes Beispiel "Pipeline-Spalten"."""
    Session, db1 = _file_sessions(tmp_path)
    _race(db1, Session, project_pipeline_columns.ensure_default_columns)

    check = Session()
    keys = check.scalars(select(ProjectPipelineColumn.key)).all()
    assert len(keys) == len(project_pipeline_columns.DEFAULT_COLUMNS)
    assert len(keys) == len(set(keys))
    check.close()


def test_ensure_default_task_columns_survives_concurrent_first_access(tmp_path):
    """Beim Sweep gefunden -- das Vorbild, nach dem project_pipeline_columns.py gebaut wurde."""
    Session, db1 = _file_sessions(tmp_path)
    _race(db1, Session, task_columns.ensure_default_columns)

    check = Session()
    keys = check.scalars(select(TaskColumn.key)).all()
    assert len(keys) == len(task_columns.DEFAULT_COLUMNS)
    assert len(keys) == len(set(keys))
    check.close()


def test_ensure_default_employee_functions_survives_concurrent_first_access(tmp_path):
    """Beim Sweep gefunden."""
    Session, db1 = _file_sessions(tmp_path)
    _race(db1, Session, employees.ensure_default_employee_functions)

    check = Session()
    names = check.scalars(select(EmployeeFunction.name)).all()
    assert len(names) == len(employees.DEFAULT_EMPLOYEE_FUNCTIONS)
    assert len(names) == len(set(names))
    check.close()


def test_ensure_default_margins_survives_concurrent_first_access(tmp_path):
    """Beim Sweep gefunden -- Einzelzeilen-Variante (nicht mehrere Standardzeilen je Aufruf).
    Auf einer frischen Datenbank ohne jede Zeile fällt resolve_shared_document_type() für JEDEN
    Dokumenttyp auf "default" zurück -- beide Sessions racen deshalb exakt auf dieselbe
    (document_type="default", page_type="first")-Zeile, der reale Fall bei mehreren
    Dokumenttypen, die auf einer frischen Installation gleichzeitig zum ersten Mal gerendert
    werden."""
    Session, db1 = _file_sessions(tmp_path)
    _race(db1, Session, ensure_default_margins, "reminder", "first")

    check = Session()
    rows = check.scalars(
        select(DocumentPageMargins).where(
            DocumentPageMargins.document_type == "default", DocumentPageMargins.page_type == "first"
        )
    ).all()
    assert len(rows) == 1
    check.close()


def test_get_or_create_sequence_survives_concurrent_first_access(tmp_path):
    """Beim Sweep gefunden -- höhere Tragweite als die übrigen (jede Dokumentnummer-Vergabe ruft
    das auf), aber die Race-Window betrifft nur den allerersten Aufruf je sequence_key."""
    Session, db1 = _file_sessions(tmp_path)
    _race(db1, Session, settings_module.get_or_create_sequence, "quote")

    check = Session()
    rows = check.scalars(select(NumberSequence).where(NumberSequence.sequence_key == "quote")).all()
    assert len(rows) == 1
    check.close()


def test_ensure_default_work_time_models_survives_concurrent_first_access(tmp_path):
    """Beim Sweep gefunden -- die komplexeste der acht Fundstellen: ein einziger Anlegeversuch
    umfasst zwei WorkTimeModel-Zeilen samt je einer Gültigkeit und zwei Pausenregeln plus die
    Singleton-Einstellung -- alles muss als EINE Einheit kollidieren/gelingen, sonst blieben
    Modelle ohne ihre Gültigkeits-/Pausenzeilen zurück."""
    Session, db1 = _file_sessions(tmp_path)
    _race(db1, Session, work_time_models.ensure_default_work_time_models)

    check = Session()
    models = check.scalars(select(WorkTimeModel)).all()
    names = [m.name for m in models]
    assert sorted(names) == ["Sommermodell", "Wintermodell"]
    assert len(names) == len(set(names))

    model_ids = [m.id for m in models]
    validities = check.scalars(
        select(WorkTimeModelValidity).where(WorkTimeModelValidity.model_id.in_(model_ids))
    ).all()
    assert len(validities) == 2  # genau eine je Modell, keine Dopplung

    break_rules = check.scalars(
        select(WorkTimeBreakRule).where(WorkTimeBreakRule.model_id.in_(model_ids))
    ).all()
    assert len(break_rules) == 4  # zwei je Modell, keine Dopplung
    check.close()


def test_seeding_still_works_without_any_race_for_option_groups(tmp_path):
    """Regressionsschutz: der ganz normale, unkollidierte Fall (kein zweiter Prozess) bleibt
    unverändert -- die Absicherung darf den Erfolgspfad nicht verändern."""
    Session, db1 = _file_sessions(tmp_path)
    result = option_settings.ensure_default_option_groups(db1)
    assert len(result) == len(option_settings.DEFAULT_OPTION_GROUPS)

    # ein zweiter Aufruf auf derselben, bereits gesäten Session darf nichts mehr verändern
    result_again = option_settings.ensure_default_option_groups(db1)
    assert len(result_again) == len(option_settings.DEFAULT_OPTION_GROUPS)
